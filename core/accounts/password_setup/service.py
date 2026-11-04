"""账号页纯协议补密码：独立认证、私有候选与明确回执确认。"""
from __future__ import annotations

import secrets
from dataclasses import replace

from core import db
from core.accounts.liveness.protocol.v2 import refresh_access_token
from core.accounts.password_setup.protocol import ProtocolPasswordSetupError, add_password
from core.auth.browser.auth_context import (
    AuthExecutionContext, CancellationRequested, current_execution_context, execution_context,
)
from core.auth.email_guard import serialize_email_auth
from core.operations.runtime import OperationCancelled, check_cancelled
from core.operations.task_gateway import OperationLeaseLost
from core.storage.accounts import password_recovery as recovery


def _generate_password() -> str:
    groups = ("ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghjkmnpqrstuvwxyz", "23456789", "!@#$%^&*?_-+=")
    characters = [secrets.choice(group) for group in groups]
    characters.extend(secrets.choice("".join(groups)) for _ in range(10))
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)


@serialize_email_auth
def run_protocol_password_setup(email: str, *, proxy: str | None, execution_fence: dict | None,
                                checkpoint=None, report=None) -> dict:
    """登录后按远端结果补密码；本地保存值只用于认证，不阻止再次补全。"""
    email = str(email or "").strip().casefold()
    cp = None
    owner = None
    dispatched = False
    confirmed = False
    callback_error = None
    checkpoint_error = None
    active_stage = "login"

    def result(ok: bool, message: str, *, status: str = "failed", error: str = "", receipt: str = "none"):
        return {"ok": ok, "status": status, "message": message, "error": error, "error_code": error,
                "password_driver": "protocol", "browser_opened": False,
                "mutation_submitted": dispatched, "action_dispatched": dispatched,
                "remote_receipt_state": receipt, "password_added": confirmed,
                **({"request_unknown": True, "outcome": "request_unknown"} if receipt == "unknown" else {})}

    def check():
        nonlocal checkpoint_error
        try:
            check_cancelled()
            if checkpoint is not None:
                checkpoint()
        except Exception as exc:
            checkpoint_error = exc
            raise

    def emit(stage: str, message: str, *, state: str = "running"):
        nonlocal active_stage
        check()
        active_stage = stage
        if report is not None:
            report(stage=stage, state=state, message=message, detail={"driver": "protocol"})

    def close_stage(state: str, message: str):
        try:
            emit(active_stage, message, state=state)
        except (OperationCancelled, OperationLeaseLost, CancellationRequested):
            raise
        except Exception:
            if checkpoint_error is not None:
                raise
            # 进度记录失败不覆盖已经保存的密码事实或原始远端回执。
            pass

    def validate_owner():
        return recovery.get_password_recovery(cp.recovery_id, **owner)

    def mark_dispatched():
        nonlocal cp, dispatched
        check()
        # 对未知回执的重试保持原候选和 unknown 状态，不能生成第二个密码。
        cp = validate_owner()
        if cp.state == "prepared":
            cp = recovery.transition_password_recovery(cp.recovery_id, **owner,
                expected_version=cp.version, state="started")
        dispatched = True

    def mark_confirmed():
        nonlocal cp, confirmed
        cp = recovery.transition_password_recovery(cp.recovery_id, **owner,
            expected_version=cp.version, state="confirmed", confirmation="password_add_response")
        confirmed = True
        close_stage("success", "账号密码已通过纯协议补全并保存")

    def mark_unknown():
        nonlocal cp
        if cp is not None and dispatched and not confirmed and cp.state == "started":
            try:
                cp = recovery.transition_password_recovery(cp.recovery_id, **owner,
                    expected_version=cp.version, state="unknown")
            except recovery.PasswordRecoveryError:
                # 租约或执行已失效时保留 started；新执行仍会复用这一候选。
                pass

    def authenticated(auth: dict, session):
        nonlocal callback_error
        try:
            check()
            validate_owner()
            token = str(auth.get("access_token") or "").strip()
            session_info = auth.get("session")
            if not token:
                raise ProtocolPasswordSetupError("password_setup_session_missing", "登录后未取得有效会话")
            recovery.save_password_recovery_session(cp.recovery_id, **owner, access_token=token,
                session_info=session_info if isinstance(session_info, dict) else {})
            emit("login", "纯协议登录已完成，新会话已保存", state="success")
            emit("set_password", "已登录，正在通过纯协议添加账号密码")
            add_password(session, email, cp.password, checkpoint=check,
                         on_dispatched=mark_dispatched, on_confirmed=mark_confirmed)
            if not confirmed:
                raise ProtocolPasswordSetupError("password_setup_unconfirmed", "密码提交结果尚未确认", dispatched)
            return result(True, "账号密码已通过纯协议补全", status="success", receipt="confirmed")
        except Exception as exc:
            # 共享登录适配器会捕获回调异常；在本层保留后再抛，避免丢失取消和提交结果。
            callback_error = exc
            return {"ok": False, "status": "failed"}

    try:
        check()
        account = db.get_account_by_email(email) or {}
        if not account.get("id"):
            return result(False, "账号不存在", error="account_not_found")
        fence = execution_fence or {}
        if not all(fence.get(key) for key in ("run_id", "execution_id", "lease_token")):
            return result(False, "补密码需要有效的账号任务执行租约", error="password_setup_execution_fence_missing")
        owner = dict(email=email, account_id=int(account["id"]), purpose="manual",
            operation_run_id=fence["run_id"], operation_execution_id=fence["execution_id"],
            operation_lease_token=fence["lease_token"], attempt_id=None,
            registration_run_id=None, registration_execution_id=None)
        cp = recovery.prepare_password_recovery(**owner, candidate_factory=_generate_password, intent="password_add")
        emit("login", "正在通过纯协议登录，准备添加账号密码")
        parent = current_execution_context()

        def probe():
            nonlocal checkpoint_error
            if parent is not None:
                try:
                    parent.checkpoint()
                except Exception as exc:
                    checkpoint_error = exc
                    raise
            check()
            return False

        auth_context = replace(parent, cancellation=probe) if parent is not None else AuthExecutionContext(cancellation=probe)
        with execution_context(auth_context):
            auth_result = refresh_access_token(email, proxy=proxy, on_authenticated=authenticated,
                                               allow_password_email_fallback=True)
        if checkpoint_error is not None:
            raise checkpoint_error
        if callback_error is not None:
            raise callback_error
        if confirmed:
            return result(True, "账号密码已通过纯协议补全", status="success", receipt="confirmed")
        if isinstance(auth_result, dict) and auth_result.get("status") == "deactivated":
            close_stage("failed", "账号已停用，已停止补密码")
            return result(False, "账号已停用，已停止补密码", status="deactivated", error="account_deactivated")
        close_stage("failed", "纯协议登录未完成")
        return result(False, "纯协议登录未完成，请检查邮箱验证码、MFA 和网络后重试",
                      error="password_setup_auth_failed")
    except (OperationCancelled, OperationLeaseLost, CancellationRequested):
        if confirmed:
            return {**result(True, "账号密码已通过纯协议补全；后续步骤已停止", status="success", receipt="confirmed"),
                    "stop_requested": True}
        mark_unknown()
        raise
    except ProtocolPasswordSetupError as exc:
        if exc.request_unknown:
            mark_unknown()
        close_stage("failed", str(exc))
        return result(False, str(exc), error=exc.code,
                      receipt="unknown" if exc.request_unknown else "rejected")
    except recovery.PasswordRecoveryError as exc:
        mark_unknown()
        close_stage("failed", "密码检查点或执行租约校验未通过")
        return result(False, "密码检查点或执行租约校验未通过，请重新运行账号任务",
                      error=f"password_recovery_{exc.code}", receipt="unknown" if dispatched else "none")
    except Exception as exc:
        mark_unknown()
        if checkpoint_error is exc:
            raise
        if confirmed:
            return result(True, "账号密码已通过纯协议补全", status="success", receipt="confirmed")
        close_stage("failed", "纯协议补密码未完成")
        return result(False, "纯协议补密码未完成，请稍后重试", error="password_setup_runtime_failed",
                      receipt="unknown" if dispatched else "none")
