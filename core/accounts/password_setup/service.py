"""账号页纯协议补密码：独立认证、私有候选与明确回执确认。"""
from __future__ import annotations

import secrets
from dataclasses import replace

from core import db
from core.accounts.credentials import get_account_totp_secret_candidate
from core.accounts.password_setup.auth import refresh_access_token
from core.accounts.password_setup.protocol import ProtocolPasswordSetupError, add_password
from core.accounts.password_setup.session import cache_authenticated_session, try_reuse_session
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
                                checkpoint=None, report=None, proxy_supplier=None, on_network_failure=None) -> dict:
    """登录后按远端结果补密码；本地保存值只用于认证，不阻止再次补全。"""
    email = str(email or "").strip().casefold()
    cp = None
    owner = None
    dispatched = False
    confirmed = False
    existing_password_valid = False
    session_reused = False
    callback_error = None
    checkpoint_error = None
    active_stage = "login"

    def result(ok: bool, message: str, *, status: str = "failed", error: str = "", receipt: str = "none"):
        return {"ok": ok, "status": status, "message": message, "error": error, "error_code": error,
                "password_driver": "protocol", "browser_opened": False,
                "mutation_submitted": dispatched, "action_dispatched": dispatched,
                "remote_receipt_state": receipt, "password_added": confirmed and not existing_password_valid,
                "password_verified": existing_password_valid,
                "session_reused": session_reused,
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
            report(stage=stage, state=state, message=message,
                   detail={"driver": "protocol", "session_reused": session_reused})

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
        nonlocal callback_error, cp, confirmed, existing_password_valid, session_reused
        try:
            check()
            cp = validate_owner()
            token = str(auth.get("access_token") or "").strip()
            session_info = auth.get("session")
            if not token:
                raise ProtocolPasswordSetupError("password_setup_session_missing", "登录后未取得有效会话")
            if auth.get("ok") is not True:
                raise ProtocolPasswordSetupError("password_setup_auth_failed", "登录尚未完成有效会话确认")
            password_verified = auth.get("ok") is True and auth.get("password_auth_status") == "verified" and bool(cp.old_password)
            pending_submission = password_verified and cp.state in {"started", "unknown"}
            saved = recovery.save_password_recovery_session(cp.recovery_id, **owner, access_token=token,
                session_info=session_info if isinstance(session_info, dict) else {},
                **({"verified_password": cp.old_password, "auth_method": str(auth.get("auth_method") or ""),
                    "password_auth_status": str(auth.get("password_auth_status") or "")}
                   if password_verified and not pending_submission else {}))
            if password_verified and not pending_submission:
                cp = saved
                existing_password_valid = confirmed = True
            session_reused = auth.get("session_reused") is True
            cache_authenticated_session(session, session_info, account_id=int(account["id"]), email=email)
            emit("login", "已有会话校验通过，已复用登录状态" if session_reused
                 else "纯协议登录已完成，新会话已保存", state="success")
            if pending_submission:
                raise ProtocolPasswordSetupError("password_setup_previous_result_unknown",
                    "原密码验证已通过，但上次密码提交结果仍需核验", True)
            if existing_password_valid:
                emit("set_password", "原密码有效，已验证", state="success")
                return result(True, "原密码有效", status="success", receipt="confirmed")
            emit("set_password", "已登录，正在通过纯协议添加账号密码")
            add_password(session, email, cp.password, checkpoint=check,
                         on_dispatched=mark_dispatched, on_confirmed=mark_confirmed,
                         totp_secret=get_account_totp_secret_candidate(db.get_account_by_email(email)))
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

        def network_failed(error):
            check()
            if callable(on_network_failure):
                on_network_failure(error)

        with execution_context(auth_context):
            emit("login", "正在校验已有会话，准备添加账号密码")
            with try_reuse_session(account, email, proxy=proxy, checkpoint=check,
                                   proxy_supplier=proxy_supplier) as reused:
                if reused is not None:
                    auth_result = authenticated(*reused)
                    if checkpoint_error is not None:
                        raise checkpoint_error
                    if callback_error is None:
                        return auth_result
                    if (isinstance(callback_error, ProtocolPasswordSetupError)
                            and callback_error.code == "password_setup_session_expired" and not dispatched):
                        callback_error = None
                        session_reused = False
                        emit("login", "已有会话无法进入添加密码流程，正在重新登录")
                    else:
                        raise callback_error
            emit("login", "正在通过纯协议登录，准备添加账号密码")
            auth_result = refresh_access_token(email, proxy=proxy, on_authenticated=authenticated,
                allow_password_email_fallback=True,
                **({"proxy_supplier": proxy_supplier} if callable(proxy_supplier) else {}),
                **({"on_network_failure": network_failed} if callable(on_network_failure) else {}))
        if checkpoint_error is not None:
            raise checkpoint_error
        if callback_error is not None:
            raise callback_error
        if confirmed:
            return result(True, "原密码有效" if existing_password_valid else "账号密码已通过纯协议补全",
                          status="success", receipt="confirmed")
        if isinstance(auth_result, dict) and auth_result.get("status") == "deactivated":
            close_stage("failed", "账号已停用，已停止补密码")
            return result(False, "账号已停用，已停止补密码", status="deactivated", error="account_deactivated")
        errors = {
            "password_reset_required": "远端要求重置密码，原密码当前无法用于登录",
            "password_rejected": "原密码被拒绝，需要找回或重置密码",
            "email_otp_failed": "登录邮箱验证码验证未完成",
            "mfa_rejected": "登录 2FA 验证未通过",
            "mfa_secret_missing": "登录需要账号已有的 2FA 密钥",
            "oauth_callback_failed": "登录回调未完成，尚未取得新会话",
            "access_token_missing": "登录未取得有效 Token",
            "protocol_network_error": "登录网络请求未完成，请稍后重试",
        }
        auth_result = auth_result if isinstance(auth_result, dict) else {}
        diagnostic = auth_result.get("auth_diagnostics") or {}
        remote_error = diagnostic.get("auth_error") if isinstance(diagnostic, dict) else {}
        code = remote_error.get("code") if isinstance(remote_error, dict) else None
        code = code if isinstance(code, str) and code in errors else auth_result.get("error")
        code = code if isinstance(code, str) else ""
        message = errors.get(code, "纯协议登录未完成，请检查邮箱验证码、2FA 和网络")
        close_stage("failed", message)
        return result(False, message, error=f"password_setup_{code}" if code in errors else "password_setup_auth_failed")
    except (OperationCancelled, OperationLeaseLost, CancellationRequested):
        if confirmed:
            return {**result(True, "原密码有效" if existing_password_valid else "账号密码已通过纯协议补全；后续步骤已停止", status="success", receipt="confirmed"),
                    "stop_requested": True}
        mark_unknown()
        raise
    except ProtocolPasswordSetupError as exc:
        if exc.request_unknown:
            mark_unknown()
        close_stage("failed", str(exc))
        return {**result(False, str(exc), error=exc.code,
                        receipt="unknown" if exc.request_unknown else "rejected"),
                **({"proxy_transport_failed": True} if exc.proxy_transport_failed else {})}
    except recovery.PasswordRecoveryError as exc:
        mark_unknown()
        message = {
            "session_context_invalid": "登录会话或 Token 尚未与目标邮箱对应，已保留恢复候选",
            "password_login_confirmation_unverified": "缺少本轮密码验证证据，已保留恢复候选",
        }.get(exc.code, "密码检查点或执行租约校验未通过，请重新运行账号任务")
        close_stage("failed", message)
        return result(False, message,
                      error=f"password_recovery_{exc.code}",
                      receipt="unknown" if dispatched or cp is not None and cp.state in {"started", "unknown"} else "none")
    except Exception as exc:
        mark_unknown()
        if checkpoint_error is exc:
            raise
        if confirmed:
            return result(True, "原密码有效" if existing_password_valid else "账号密码已通过纯协议补全", status="success", receipt="confirmed")
        close_stage("failed", "纯协议补密码未完成")
        return result(False, "纯协议补密码未完成，请稍后重试", error="password_setup_runtime_failed",
                      receipt="unknown" if dispatched else "none")
