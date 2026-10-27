"""开源 Protocol 注册主链路及本地任务适配。"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from core.auth_challenge import AuthCancelledError, auth_result_for_registration
from core.registration.protocol_oss.upstream.config import openai_protocol as _upstream_config
from core.registration.protocol_oss.upstream.core import (
    chatgpt_auth as _chatgpt_auth,
    openai_auth as _openai_auth,
)
from core.profile_utils import generate_random_birthday
from core.session import BrowserSession

logger = logging.getLogger(__name__)


class ProtocolOssRequestUnknown(RuntimeError):
    """上游写请求已发出，但本地尚未确认远端结果。"""

    def __init__(self, message: str, *, register_response_confirmed: bool = False):
        super().__init__(message)
        self.register_response_confirmed = register_response_confirmed is True


class ProtocolOssManualReconcile(RuntimeError):
    """恢复到已有账号的额外验证，但本地没有可复用的凭据。"""


def _continue_url(result: object) -> str:
    if not isinstance(result, dict):
        return ""
    page = result.get("page") if isinstance(result.get("page"), dict) else {}
    return str(
        result.get("continue_url")
        or result.get("external_url")
        or result.get("url")
        or page.get("continue_url")
        or page.get("external_url")
        or page.get("url")
        or ""
    )


def _classify_upstream_continuation(page_type: str, continue_url: str | None) -> str:
    """在上游页面响应中区分已有账号、新注册资料页和未知状态。"""
    normalized_type = str(page_type or "").strip().lower()
    normalized_url = str(continue_url or "").strip().lower()
    if normalized_type in {
        "login_password",
        "password_login",
        "log_in_password",
        "password_login_required",
    } or "/log-in/password" in normalized_url:
        return "existing"
    if normalized_type == "external_url" or (
        normalized_url
        and "about-you" not in normalized_url
        and (
            "chatgpt.com/api/auth/callback" in normalized_url
            or "auth.openai.com/authorize/continue" in normalized_url
        )
    ):
        return "existing"
    if normalized_type in {"about_you", "about-you"} or "about-you" in normalized_url:
        return "new_candidate"
    return "unknown"


def _finalize_session(session, continue_url: str, *, email: str, referer: str) -> tuple[dict, str]:
    from core.account_export import fetch_session, follow_oauth_callback
    from core.humanize import delay as human_delay
    from core.registration_service import check_stop_requested, report_job_progress

    last_error: Exception | None = None
    for attempt in range(1, 6):
        check_stop_requested()
        report_job_progress("token", "running", "正在完成上游 OAuth 回调并读取会话")
        try:
            follow_oauth_callback(session, continue_url, referer=referer)
            human_delay("post_auth")
            session_info = fetch_session(session)
            access_token = str(session_info.get("accessToken") or "").strip()
            if not access_token:
                raise RuntimeError("session 响应缺少 accessToken")
            return session_info, access_token
        except (AuthCancelledError,):
            raise
        except Exception as exc:
            last_error = exc
            if attempt < 5:
                time.sleep(min(8, 2 ** (attempt - 1)))
    raise RuntimeError(
        f"OAuth callback/session 重试耗尽：{type(last_error).__name__ if last_error else 'Unknown'}"
    ) from last_error


def _run_upstream_protocol(
    session,
    *,
    email: str,
    name: str,
    birthday: str,
    otp_code: str | None,
    email_source: str | None,
    existing_password: str | None,
    existing_totp_secret: str | None,
    options: dict[str, Any],
) -> dict[str, Any]:
    """执行上游认证/注册序列，只返回会话事实，不做上游存储或后处理。"""
    from core.email_provider import wait_for_otp
    from core.humanize import delay as human_delay
    from core.registration.checkpoints import save_protocol_password_checkpoint
    from core.protocol_v2_liveness import _is_mfa
    from core.registration_service import (
        StopRequested,
        check_stop_requested,
        report_job_progress,
    )

    password_request_started = False
    password_register_accepted = bool(existing_password)
    register_response_confirmed = False
    profile_request_started = False
    challenge_chain: list[str] = []

    def checkpoint() -> None:
        check_stop_requested()

    def progress(stage: str, state: str, detail: str) -> None:
        checkpoint()
        report_job_progress(stage, state, detail)

    try:
        progress("browser", "running", "正在初始化开源 Protocol 会话")
        progress("browser", "success", "开源 Protocol 会话已初始化")
        if not birthday:
            birthday = generate_random_birthday()

        _openai_auth.network_preflight(session)
        human_delay("navigate")
        if bool(getattr(_upstream_config, "CHATGPT_ANON_BOOTSTRAP_ENABLED", True)):
            from core.chatgpt_bootstrap import anonymous_bootstrap

            anonymous_bootstrap(
                session,
                strict=bool(getattr(_upstream_config, "CHATGPT_BOOTSTRAP_STRICT", False)),
            )
            human_delay("navigate")

        progress("submit_email", "running", "正在按上游流程建立认证状态")
        _chatgpt_auth.get_providers(session)
        human_delay("api")
        csrf_token = _chatgpt_auth.get_csrf_token(session)
        human_delay("api")
        authorize_url = _chatgpt_auth.signin_openai(session, csrf_token, email)
        progress("submit_email", "success", "邮箱认证入口已建立")

        progress("auth_redirect", "running", "正在跟随上游授权流程")
        authorize_final_url = _openai_auth.follow_authorize(session, authorize_url)
        progress("auth_redirect", "success", "已进入上游认证下一步")
        human_delay("navigate")

        remote_identity = "new"
        registration_password = str(existing_password or "").strip() or None
        password_validated = bool(registration_password)
        otp_after_ts = time.time()
        resume_totp_result = None

        if registration_password:
            from core.registration.protocol import (
                _complete_protocol_resume_mfa,
                _protocol_resume_otp_continue_url,
                _run_protocol_existing_password_stage,
                _send_protocol_resume_email_otp,
            )

            remote_identity = "existing"
            progress("login_password", "running", "正在使用原 Attempt 密码继续开源协议认证")
            password_result = _run_protocol_existing_password_stage(
                session, email, registration_password,
            )
            register_response_confirmed = True
            progress("login_password", "success", "原 Attempt 密码已通过认证")
            password_continue_url = _continue_url(password_result)
            if _is_mfa(password_result, password_continue_url):
                if not existing_totp_secret:
                    raise ProtocolOssManualReconcile("已有账号需要 TOTP，但原 Attempt 没有可复用密钥")
                resume_totp_result = _complete_protocol_resume_mfa(
                    session,
                    password_result,
                    password_continue_url,
                    existing_totp_secret,
                )
            else:
                otp_continue_url = _protocol_resume_otp_continue_url(password_result)
                otp_after_ts = _send_protocol_resume_email_otp(
                    session,
                    after_ts=otp_after_ts,
                    auth_final_url=authorize_final_url,
                    continue_url=otp_continue_url,
                    otp_page_ready=otp_continue_url is None,
                )
        else:
            progress("password", "running", "正在进入上游密码注册流程")
            _openai_auth.navigate_create_account_password(session, authorize_final_url)
            human_delay("navigate")
            registration_password = _openai_auth.generate_registration_password()
            save_protocol_password_checkpoint(
                email=email,
                password=registration_password,
                state="prepared",
                proxy=session.proxy,
                email_source=email_source,
            )
            checkpoint()
            save_protocol_password_checkpoint(
                email=email,
                password=registration_password,
                state="started",
                proxy=session.proxy,
                email_source=email_source,
            )
            password_request_started = True
            password_bundle = _openai_auth.request_password_sentinel_bundle(session)
            password_header, password_so_header = _openai_auth.build_sentinel_header(
                session, password_bundle, "username_password_create",
            )
            human_delay("challenge")
            register_result = _openai_auth.register_user(
                session,
                email,
                registration_password,
                password_header,
                password_so_header,
            )
            password_request_started = False
            password_register_accepted = True
            register_response_confirmed = True
            password_validated = True
            save_protocol_password_checkpoint(
                email=email,
                password=registration_password,
                state="confirmed",
                proxy=session.proxy,
                email_source=email_source,
            )
            challenge_chain.append("password")
            progress("password", "success", "上游已确认密码注册请求")
            otp_after_ts = time.time()
            progress("email_otp", "running", "正在请求上游邮箱验证码")
            _openai_auth.navigate_email_otp_send(
                session,
                _continue_url(register_result) or None,
            )

        if resume_totp_result is not None:
            session_info, access_token = resume_totp_result
            challenge_chain.append("totp")
        else:
            progress("email_otp", "running", "正在等待并验证所选邮箱来源的验证码")
            validate_result = None
            current_otp = otp_code
            max_attempts = 3
            for otp_attempt in range(1, max_attempts + 1):
                checkpoint()
                if current_otp is None:
                    current_otp = wait_for_otp(
                        email,
                        after_ts=otp_after_ts,
                        email_source=email_source,
                    )
                human_delay("otp_input")
                try:
                    sentinel_header = None
                    so_header = None
                    if bool(getattr(_upstream_config, "SEND_SENTINEL_ON_EMAIL_OTP_VALIDATE", False)):
                        sentinel_result = _openai_auth.request_sentinel_token(
                            session, "authorize_continue",
                        )
                        sentinel_header, so_header = _openai_auth.build_sentinel_header(
                            session, sentinel_result, "authorize_continue",
                        )
                        human_delay("challenge")
                    validate_result = _openai_auth.validate_email_otp(
                        session,
                        current_otp,
                        sentinel_header,
                        so_header,
                    )
                    challenge_chain.append("email_otp")
                    break
                except _openai_auth.EmailOtpInvalidError:
                    if otp_attempt >= max_attempts:
                        raise
                    otp_after_ts = time.time()
                    _openai_auth.send_email_otp(session)
                    current_otp = None
                    human_delay("api")

            if validate_result is None:
                raise RuntimeError("上游邮箱验证码验证未完成")
            progress("email_otp", "success", "上游邮箱验证码已通过")
            human_delay("api")

            page = validate_result.get("page") if isinstance(validate_result.get("page"), dict) else {}
            page_type = str(page.get("type") or "")
            next_url = _continue_url(validate_result)
            next_path = str(next_url or "").lower()
            continuation_identity = _classify_upstream_continuation(page_type, next_url)
            if continuation_identity == "unknown":
                raise RuntimeError("上游 OTP 返回未知认证状态，已停止提交注册资料")
            if continuation_identity == "existing":
                remote_identity = "existing"
                if page_type.lower() in {
                    "login_password", "password_login", "log_in_password", "password_login_required",
                } or "/log-in/password" in next_path:
                    raise ProtocolOssManualReconcile(
                        "上游确认邮箱属于已有账号，但当前流程无法安全重用登录密码"
                    )
                if not next_url:
                    raise ProtocolOssManualReconcile("上游确认已有账号，但没有可继续的 OAuth 地址")
                session_info, access_token = _finalize_session(
                    session,
                    next_url,
                    email=email,
                    referer="https://auth.openai.com/email-verification",
                )
            else:
                remote_identity = "existing" if existing_password else "new"
                progress("profile", "running", "正在提交上游注册资料")
                _openai_auth.navigate_about_you(
                    session,
                    next_url if "about-you" in next_path else None,
                )
                human_delay("navigate")
                profile_sentinel = _openai_auth.request_sentinel_token(
                    session, "oauth_create_account",
                )
                profile_header, profile_so_header = _openai_auth.build_sentinel_header(
                    session, profile_sentinel, "oauth_create_account",
                )
                human_delay("challenge")
                human_delay("form")
                profile_request_started = True
                create_result = _openai_auth.create_account(
                    session,
                    name,
                    birthday,
                    profile_header,
                    profile_so_header,
                )
                progress("profile", "success", "上游已确认注册资料")
                human_delay("post_auth")
                continue_url = _continue_url(create_result)
                if not continue_url:
                    raise RuntimeError("上游资料提交响应缺少 OAuth 继续地址")
                session_info, access_token = _finalize_session(
                    session,
                    continue_url,
                    email=email,
                    referer="https://auth.openai.com/about-you",
                )

        progress("token", "success", "已取得上游协议会话")
        return {
            "session_info": session_info,
            "access_token": access_token,
            "registration_password": registration_password,
            "password_validated": password_validated,
            "remote_identity": remote_identity,
            "challenge_chain": challenge_chain,
        }
    except ProtocolOssRequestUnknown:
        raise
    except ProtocolOssManualReconcile:
        raise
    except (AuthCancelledError, StopRequested) as exc:
        if password_request_started or password_register_accepted or profile_request_started:
            raise ProtocolOssRequestUnknown(
                "上游注册写入已开始，当前结果待同一 Attempt 恢复",
                register_response_confirmed=register_response_confirmed,
            ) from exc
        raise
    except Exception as exc:
        if password_request_started or password_register_accepted or profile_request_started:
            raise ProtocolOssRequestUnknown(
                f"上游写入后未取得确认：{type(exc).__name__}",
                register_response_confirmed=register_response_confirmed,
            ) from exc
        raise


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
) -> dict[str, Any]:
    from config import codex as codex_cfg
    from config import twofa as twofa_cfg
    from core import db
    from core.email_provider import wait_for_otp
    from core.registration.checkpoints import save_protocol_totp_checkpoint
    from core.registration_service import StopRequested, report_job_progress
    from core.registration_postprocess import summarize_postprocess

    password_required = bool(options.get("password_enabled", False))
    twofa_enabled = bool(options.get("twofa_enabled", twofa_cfg.ENABLE_2FA))
    codex_enabled = bool(options.get("codex_enabled", codex_cfg.ENABLE_CODEX_AUTO))
    plan_check_enabled = bool(options.get("plan_check_enabled", True))
    from core.registration_service import codex_driver_for_registration

    codex_driver = codex_driver_for_registration(options)
    bootstrap_error = None

    if bool(getattr(_upstream_config, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", True)):
        from core.chatgpt_bootstrap import authenticated_bootstrap

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
            from core.plan_check_service import check_registration_account_plan

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
    if twofa_enabled and totp_secret:
        report_job_progress("twofa", "success", "已复用原任务确认的 Authenticator 2FA")
    elif twofa_enabled:
        report_job_progress("twofa", "running", "正在设置 Authenticator 2FA")
        try:
            if twofa_cfg.get_twofa_driver_for_options(options) != "protocol":
                raise RuntimeError("开源协议注册只支持 protocol 2FA；browser 模式请切换到 RoxyBrowser")
            from core.account_export import setup_2fa_protocol

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
            logger.error("开源 Protocol 2FA 未完成：%s", type(exc).__name__)
            report_job_progress("twofa", "failed", f"2FA 设置未完成：{type(exc).__name__}")
    else:
        report_job_progress("twofa", "skipped", "未启用 Authenticator 2FA")

    codex_result = {"status": "skipped", "ok": True, "message": "ENABLE_CODEX_AUTO=False，跳过 Codex"}
    if codex_enabled:
        try:
            from core.codex_oauth import run_codex_oauth

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
                login_password=registration_password,
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
        from core.flow_trigger import trigger_flow

        flow_result = trigger_flow(access_token)
    except Exception as exc:
        flow_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {exc}"}

    codex_ok = bool(codex_result.get("ok") or codex_result.get("status") == "skipped")
    twofa_ok = (not twofa_enabled) or bool(totp_secret)
    password_ok = not password_required or bool(registration_password)
    postprocess_success = bool(
        codex_ok and twofa_ok and plan_result.get("ok") and password_ok and not bootstrap_error
    )
    error_parts = [
        None if codex_ok else f"Codex 未完成：{codex_result.get('message') or '未知'}",
        None if twofa_ok else "2FA 未完成",
        None if plan_result.get("ok") else "套餐查询待重试",
        None if password_ok else "原密码尚未确认生效",
        bootstrap_error,
    ]
    readiness = summarize_postprocess(
        core_success=True,
        password_present=bool(registration_password),
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


def run_protocol_oss_registration(
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
    _driver_name: str = "protocol_oss",
    _label: str = "开源 Protocol",
    _session_factory=None,
) -> dict:
    """运行固定上游注册流程，并把结果交给本地任务和存储体系。"""
    if not str(proxy or "").strip():
        raise RuntimeError("Protocol OSS 注册必须使用统一代理池已领取线路，禁止无代理或直连")

    from core.email_provider import (
        mark_email_permanently_unusable,
        resolve_email_source,
        retain_email,
        validate_email_source,
    )
    from core.registration_service import (
        StopRequested,
        persist_registration_core,
        report_job_progress,
    )

    options = dict(registration_options or {})
    selected_source = validate_email_source(email_source) if email_source else resolve_email_source(email)
    session = (_session_factory or BrowserSession)(proxy=proxy)
    account_id = None
    core_persistence_started = False
    flow_result = None
    try:
        report_job_progress("browser", "running", f"正在启动{_label}注册")
        flow_result = (_flow_runner or _run_upstream_protocol)(
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
                **({"account_password": registration_password} if flow_result.get("password_validated") else {}),
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
        raise StopRequested("用户停止开源 Protocol 注册") from exc
    except Exception as exc:
        from core.registration.protocol import (
            _protocol_registration_cause_code,
            _safe_protocol_registration_error,
        )

        request_unknown = isinstance(exc, ProtocolOssRequestUnknown)
        manual_reconcile = isinstance(exc, ProtocolOssManualReconcile)
        if request_unknown:
            # A started write or incomplete session is not evidence of a local
            # persistence failure, nor of a confirmed registration response.
            cause_code = "user_register_result_unknown"
        elif core_persistence_started and account_id is None:
            cause_code = "registration_checkpoint_failed"
        else:
            cause_code = _protocol_registration_cause_code(
                exc,
                str(exc),
                register_accepted=False,
                checkpoint_account_id=account_id,
                otp_send_in_flight=False,
            )
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
            if isinstance(exc, _openai_auth.AccountUnusableError):
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
            logger.exception("开源 Protocol 邮箱状态收口失败")
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
            "error": error,
        }
    finally:
        close = getattr(session, "close", None)
        if callable(close):
            try:
                close()
            except Exception as exc:
                logger.warning("开源 Protocol 会话收口失败：%s", type(exc).__name__)
