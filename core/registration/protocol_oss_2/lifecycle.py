"""开源protocol-2 的账号落库、后处理及错误收口。"""
from __future__ import annotations

import logging
import re
from typing import Any

from config import openai_protocol as _upstream_config
from core.auth.challenge import AuthCancelledError, auth_result_for_registration
from core.auth.protocol.openai_auth import AccountUnusableError
from core.auth.protocol.session import BrowserSession
from core.registration.profile_utils import generate_random_birthday

logger = logging.getLogger(__name__)



class ProtocolOssRequestUnknown(RuntimeError):
    """上游写请求已发出，但本地尚未确认远端结果。"""

    def __init__(self, message: str, *, register_response_confirmed: bool = False,
                 cause_diagnostics: dict | None = None, registration_diagnostics: dict | None = None):
        super().__init__(message)
        from core.operations.errors import registration_diagnostic_cause_code, safe_registration_diagnostics

        self.register_response_confirmed = register_response_confirmed is True
        self.registration_diagnostics = safe_registration_diagnostics(registration_diagnostics)
        self.cause_diagnostics = {}
        self.cause_code = registration_diagnostic_cause_code(self.registration_diagnostics)
        if isinstance(cause_diagnostics, dict) and cause_diagnostics.get("operation") == "profile_submit":
            from core.network.response_diagnostics import safe_auth_error

            status = cause_diagnostics.get("http_status")
            if type(status) is int and 400 <= status <= 599:
                self.http_status = status
                self.cause_diagnostics = {
                    "operation": "profile_submit", "http_status": status,
                    "auth_error": safe_auth_error(cause_diagnostics.get("auth_error")),
                }
                if status == 409 and self.cause_diagnostics["auth_error"].get("code") == "invalid_state":
                    self.cause_code = "account_create_invalid_state"
                elif status == 400 and self.cause_diagnostics["auth_error"].get("code") == "user_already_exists":
                    self.cause_code = "account_create_user_already_exists"


class ProtocolOssManualReconcile(RuntimeError):
    """恢复到已有账号的额外验证，但本地没有可复用的凭据。"""


def _safe_twofa_failure_detail(exc: BaseException) -> str:
    """后置失败只保留操作、异常类型和 HTTP 状态，不复制远端正文。"""
    from core.accounts.export import TwofaProtocolHTTPError, TwofaProtocolTransportError

    type_name = type(exc).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", type_name):
        type_name = "Exception"
    operation = getattr(exc, "operation", "")
    operation = operation if isinstance(operation, str) and operation in {"enroll", "activate", "reauth"} else "mfa"
    if isinstance(exc, TwofaProtocolTransportError):
        cause_type = str(getattr(exc, "cause_type", "") or "")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", cause_type):
            cause_type = "TransportError"
        return f"{type_name}: {operation} 传输失败，异常类型={cause_type}"
    if isinstance(exc, TwofaProtocolHTTPError):
        return f"{type_name}: {operation} HTTP {exc.status_code}"
    return f"{type_name}: {operation} 步骤未完成"


def _run_local_postprocessing(
    *,
    session,
    email: str,
    access_token: str,
    account_id: int,
    session_info: dict,
    registration_password: str | None,
    email_source: str | None,
    options: dict[str, Any],
    existing_totp_secret: str | None = None,
    password_confirmed: bool = False,
) -> dict[str, Any]:
    from config import codex as codex_cfg
    from config import twofa as twofa_cfg
    from core import db
    from core.email.provider import wait_for_otp
    from core.registration.checkpoints import save_protocol_totp_checkpoint
    from core.registration.service import StopRequested, report_job_progress
    from core.registration.postprocess import summarize_postprocess

    password_required = bool(options.get("password_enabled", False))
    twofa_enabled = bool(options.get("twofa_enabled", twofa_cfg.ENABLE_2FA))
    codex_enabled = bool(options.get("codex_enabled", codex_cfg.ENABLE_CODEX_AUTO))
    plan_check_enabled = bool(options.get("plan_check_enabled", True))
    from core.registration.service import codex_driver_for_registration

    codex_driver = codex_driver_for_registration(options)
    bootstrap_error = None

    if bool(getattr(_upstream_config, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", True)):
        from core.auth.protocol.chatgpt_bootstrap import authenticated_bootstrap

        try:
            authenticated_bootstrap(
                session,
                access_token,
                strict=bool(getattr(_upstream_config, "CHATGPT_BOOTSTRAP_STRICT", False)),
            )
        except (AuthCancelledError, StopRequested):
            raise
        except Exception as exc:
            logger.warning("登录态预热失败，核心账号已保存：%s", type(exc).__name__)
            if bool(getattr(_upstream_config, "CHATGPT_BOOTSTRAP_STRICT", False)):
                bootstrap_error = f"登录态预热未完成：{type(exc).__name__}"

    plan_result = {"status": "skipped", "ok": True, "message": "未启用注册后自动查套餐"}
    if plan_check_enabled:
        try:
            from core.accounts.plans.service import check_registration_account_plan

            report_job_progress("plan_check", "running", "正在复用注册会话与代理查询套餐")
            plan_result = dict(check_registration_account_plan(
                account_id=account_id,
                email=email,
                access_token=access_token,
                proxy=session.proxy or "",
                session=session,
            ) or {})
            plan_result["ok"] = bool(plan_result.get("ok"))
            plan_result["status"] = "success" if plan_result["ok"] else "failed"
            plan_result["message"] = "套餐查询完成" if plan_result["ok"] else str(plan_result.get("error") or "套餐查询失败")
            report_job_progress(
                "plan_check",
                "success" if plan_result["ok"] else "failed",
                plan_result["message"][:300],
            )
        except (AuthCancelledError, StopRequested):
            raise
        except Exception as exc:
            plan_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
            report_job_progress("plan_check", "failed", plan_result["message"])

    totp_secret = existing_totp_secret or None
    twofa_error = None
    if twofa_enabled and totp_secret:
        report_job_progress("twofa", "success", "已复用原任务确认的 Authenticator 2FA")
    elif twofa_enabled:
        report_job_progress("twofa", "running", "正在设置 Authenticator 2FA")
        try:
            if twofa_cfg.get_twofa_driver_for_options(options) != "protocol":
                raise RuntimeError("开源协议注册只支持 protocol 2FA；browser 模式请切换到 RoxyBrowser")
            from core.accounts.export import setup_2fa_protocol

            candidate_secret = setup_2fa_protocol(
                session,
                access_token,
                on_secret=lambda secret: save_protocol_totp_checkpoint(
                    email=email,
                    secret=secret,
                    confirmed=False,
                ),
            )
            save_protocol_totp_checkpoint(email=email, secret=candidate_secret, confirmed=True)
            totp_secret = candidate_secret
            report_job_progress("twofa", "success", "协议 2FA 已启用")
        except (AuthCancelledError, StopRequested):
            raise
        except Exception as exc:
            twofa_error = f"2FA 未完成：{_safe_twofa_failure_detail(exc)}"
            logger.error("开源 Protocol %s", twofa_error)
            report_job_progress("twofa", "failed", twofa_error)
    else:
        report_job_progress("twofa", "skipped", "未启用 Authenticator 2FA")

    codex_result = {"status": "skipped", "ok": True, "message": "ENABLE_CODEX_AUTO=False，跳过 Codex"}
    if codex_enabled:
        try:
            from core.codex.oauth import run_codex_oauth

            report_job_progress("codex", "running", "正在执行 Codex OAuth")
            codex_kwargs = {"proxy": session.proxy, "driver_override": codex_driver}
            if email_source:
                codex_kwargs["otp_provider"] = lambda address, **kwargs: wait_for_otp(
                    address,
                    email_source=email_source,
                    **kwargs,
                )
            codex_result = run_codex_oauth(
                email,
                login_password=registration_password if password_confirmed else None,
                login_totp_secret=totp_secret,
                **codex_kwargs,
            )
            report_job_progress(
                "codex",
                "success" if codex_result.get("ok") else "skipped" if codex_result.get("status") == "skipped" else "failed",
                str(codex_result.get("message") or "Codex OAuth 已完成")[:300],
            )
        except (AuthCancelledError, StopRequested):
            raise
        except Exception as exc:
            codex_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
            report_job_progress("codex", "failed", codex_result["message"])

    if codex_result.get("status") in {"success", "failed", "skipped", "attention_required"}:
        status = "success" if codex_result.get("ok") and codex_result.get("status") != "skipped" else codex_result.get("status")
        db.update_account_codex_status(
            email,
            status,
            None if status in {"success", "skipped"} else str(codex_result.get("message") or "")[:500],
        )

    flow_result = {"status": "skipped", "ok": False, "message": "未触发"}
    try:
        from core.integrations.flow_trigger import trigger_flow

        flow_result = trigger_flow(access_token)
    except Exception as exc:
        flow_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {exc}"}

    codex_ok = bool(codex_result.get("ok") or codex_result.get("status") == "skipped")
    twofa_ok = (not twofa_enabled) or bool(totp_secret)
    password_ok = not password_required or password_confirmed
    postprocess_success = bool(
        codex_ok and twofa_ok and plan_result.get("ok") and password_ok and not bootstrap_error
    )
    error_parts = [
        None if codex_ok else f"Codex 未完成：{codex_result.get('message') or '未知'}",
        None if twofa_ok else twofa_error or "2FA 未完成",
        None if plan_result.get("ok") else "套餐查询待重试",
        None if password_ok else "原密码尚未确认生效",
        bootstrap_error,
    ]
    readiness = summarize_postprocess(
        core_success=True,
        password_present=password_confirmed,
        password_required=password_required,
        outcomes={
            "twofa": {"status": "success" if twofa_ok else "failed", "ok": twofa_ok},
            "codex": codex_result,
            "plan_check": plan_result,
        },
        twofa_required=twofa_enabled,
        codex_enabled=codex_enabled,
        plan_check_required=plan_check_enabled,
    )
    return {
        "postprocess_success": postprocess_success,
        "totp_secret": totp_secret,
        "flow": flow_result,
        "codex": codex_result,
        "plan_check": plan_result,
        "next_actions": [action.as_dict() for action in readiness.next_actions],
        "account_readiness": readiness.account_readiness,
        "warnings": [bootstrap_error] if bootstrap_error else [],
        "error": "; ".join(item for item in error_parts if item) or None,
    }


def run_protocol_oss_2_lifecycle(
    email: str,
    name: str,
    birthday: str | None = None,
    proxy: str | None = None,
    otp_code: str | None = None,
    existing_password: str | None = None,
    existing_totp_secret: str | None = None,
    profile_id: str | None = None,
    registration_options: dict | None = None,
    email_source: str | None = None,
    *,
    _flow_runner=None,
    _driver_name: str = "protocol_oss_2",
    _label: str = "开源protocol-2",
    _session_factory=None,
) -> dict:
    """运行固定上游注册流程，并把结果交给本地任务和存储体系。"""
    if not str(proxy or "").strip():
        raise RuntimeError("开源protocol-2 注册必须使用统一代理池已领取线路，禁止无代理或直连")

    from core.email.provider import mark_email_permanently_unusable, resolve_email_source, retain_email, validate_email_source
    from core.registration.service import StopRequested, persist_registration_core, report_job_progress

    options = dict(registration_options or {})
    selected_source = validate_email_source(email_source) if email_source else resolve_email_source(email)
    session = (_session_factory or BrowserSession)(proxy=proxy)
    account_id = None
    core_persistence_started = False
    flow_result = None
    try:
        report_job_progress("browser", "running", f"正在启动{_label}注册")
        flow_result = _flow_runner(
            session,
            email=email,
            name=name,
            birthday=birthday or generate_random_birthday(),
            otp_code=otp_code,
            email_source=selected_source,
            existing_password=existing_password,
            existing_totp_secret=existing_totp_secret,
            options=options,
        )
        access_token = str(flow_result["access_token"])
        session_info = dict(flow_result["session_info"])
        registration_password = flow_result.get("registration_password")
        from core.accounts.password_evidence import registration_password_extra

        password_confirmed = flow_result.get("password_validated") is True
        core_persistence_started = True
        account_id = persist_registration_core(
            email=email,
            access_token=access_token,
            chatgpt_session=session_info,
            email_source=selected_source,
            proxy_used=session.proxy or proxy,
            extra={
                "user": session_info.get("user"),
                "account": session_info.get("account"),
                "expires": session_info.get("expires"),
                "device_id": session.device_id,
                "sentinel_sid": getattr(session, "sentinel_sid", None),
                "browser_profile": getattr(session, "browser_profile", None),
                **registration_password_extra(registration_password, confirmed=password_confirmed),
                "registration_checkpoint": "core_persisted",
                "registration_driver": _driver_name,
            },
        )
        report_job_progress("token", "success", f"{_label}核心账号已写入 PostgreSQL")
        local_result = _run_local_postprocessing(
            session=session,
            email=email,
            access_token=access_token,
            account_id=int(account_id),
            session_info=session_info,
            registration_password=registration_password,
            email_source=selected_source,
            options=options,
            password_confirmed=password_confirmed,
            **({"existing_totp_secret": existing_totp_secret} if existing_totp_secret else {}),
        )
        postprocess_success = bool(local_result.get("postprocess_success"))
        return {
            "success": True,
            "registration_success": True,
            "core_persisted": True,
            "postprocess_success": postprocess_success,
            "partial_success": not postprocess_success,
            "email": email,
            "account_id": int(account_id),
            "access_token": access_token,
            "totp_secret": local_result.get("totp_secret"),
            "flow": local_result.get("flow"),
            "codex": local_result.get("codex"),
            "plan_check": local_result.get("plan_check"),
            "postprocess_warnings": local_result.get("warnings") or [],
            "next_actions": local_result.get("next_actions") or [],
            "account_readiness": local_result.get("account_readiness"),
            "remote_identity": flow_result.get("remote_identity") or "new",
            "remote_identity_state": "confirmed",
            "registration_intent": "reconcile" if flow_result.get("remote_identity") == "existing" else "new",
            "auth": auth_result_for_registration(
                {"success": True},
                auth_method=_driver_name,
                remote_identity=flow_result.get("remote_identity") or "new",
                challenge_chain=flow_result.get("challenge_chain") or [],
            ).as_dict(),
            "error": local_result.get("error"),
        }
    except StopRequested:
        raise
    except AuthCancelledError as exc:
        raise StopRequested("用户停止开源protocol-2 注册") from exc
    except Exception as exc:
        from core.registration.errors import (
            _protocol_registration_cause_code,
            _safe_protocol_registration_error,
        )
        from core.operations.errors import registration_diagnostic_cause_code, safe_registration_diagnostics

        registration_diagnostics = safe_registration_diagnostics(getattr(exc, "registration_diagnostics", None))
        diagnostic_cause = registration_diagnostic_cause_code(registration_diagnostics)
        request_unknown = isinstance(exc, ProtocolOssRequestUnknown)
        manual_reconcile = isinstance(exc, ProtocolOssManualReconcile)
        if request_unknown:
            # A started write or incomplete session is not evidence of a local
            # persistence failure, nor of a confirmed registration response.
            cause_code = exc.cause_code or diagnostic_cause or "user_register_result_unknown"
        elif core_persistence_started and account_id is None:
            cause_code = "registration_checkpoint_failed"
        else:
            cause_code = diagnostic_cause or _protocol_registration_cause_code(
                exc,
                str(exc),
                register_accepted=False,
                checkpoint_account_id=account_id,
                otp_send_in_flight=False,
            )
        password_entry_cause = getattr(exc, "cause_code", "")
        if password_entry_cause in {
            "password_entry_navigation_failed", "password_entry_navigation_timeout", "password_entry_not_offered", "identity_mismatch",
        }:
            cause_code = password_entry_cause
        missing_module = str(getattr(exc, "name", "") or "")
        if isinstance(exc, ModuleNotFoundError) and len(missing_module) <= 160 and re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*",
            missing_module,
        ):
            cause_code = "python_module_missing"
            error = f"{_label} 缺少 Python 依赖：{missing_module}"
        else:
            error = _safe_protocol_registration_error(exc, cause_code)
        try:
            if isinstance(exc, AccountUnusableError):
                mark_email_permanently_unusable(
                    email,
                    source=selected_source,
                    note=f"上游明确确认账号永久失效：{error[:180]}",
                )
            else:
                retain_email(
                    email,
                    source=selected_source,
                    note=f"开源协议注册中途失败，保留原任务身份：{error[:180]}",
                )
        except Exception:
            logger.exception("开源protocol-2 邮箱状态收口失败")
        return {
            "success": False,
            "core_persisted": bool(account_id),
            "email": email,
            "account_id": account_id,
            "request_unknown": request_unknown,
            "manual_reconcile": manual_reconcile,
            "registration_pending": bool(request_unknown and flow_result is None),
            "register_response_confirmed": core_persistence_started or (
                request_unknown and exc.register_response_confirmed
            ),
            "remote_identity": "existing" if manual_reconcile else "unknown",
            "remote_identity_state": "confirmed" if manual_reconcile else "request_unknown" if request_unknown else "not_started",
            "remote_account_state": "confirmed" if manual_reconcile else "request_unknown" if request_unknown else "not_started",
            "error_code": "manual_reconcile" if manual_reconcile else "request_unknown" if request_unknown else "registration_failed",
            "cause_code": "remote_identity_existing" if manual_reconcile else cause_code,
            **({"cause_diagnostics": exc.cause_diagnostics} if request_unknown and exc.cause_diagnostics else {}),
            **({"registration_diagnostics": registration_diagnostics} if registration_diagnostics else {}),
            "error": error,
        }
    finally:
        close = getattr(session, "close", None)
        if callable(close):
            try:
                close()
            except Exception as exc:
                logger.warning("开源protocol-2 会话收口失败：%s", type(exc).__name__)
