"""补密码专用登录适配，补齐无密码账号的邮箱与已有 MFA 挑战。"""
from __future__ import annotations

import logging

from core import db
from core.accounts.credentials import get_account_login_credentials
from core.accounts.liveness.protocol import legacy, v2, v3
from core.accounts.password_setup.protocol import ProtocolPasswordSetupError
from core.accounts.password_setup.proxy import is_proxy_transport_failure
from core.auth.browser.auth_context import checkpoint
from core.auth.challenge import auth_result_for_operation
from core.auth.protocol.openai_auth import AccountUnusableError, AuthorizeRouteRejectedError, EmailOtpSendError
from core.email.mailbox_wait import use_cooperative_wait
from core.network.response_diagnostics import _auth_payload_from_body

logger = logging.getLogger(__name__)
_OTP_REJECTION_CODES = {
    "invalid_code", "wrong_email_otp", "invalid_otp", "email_otp_invalid", "wrong_email_otp_code", "otp_expired",
}
_REMOTE_AUTH_CODES = _OTP_REJECTION_CODES | {"identity_provider_mismatch"}


def _remote_auth_code(error: Exception, diagnostics: dict) -> str:
    """仅在共享诊断未归因时，从有界且无歧义的响应读取固定错误枚举。"""
    remote_error = diagnostics.get("auth_error") if isinstance(diagnostics, dict) else None
    diagnostic_code = remote_error.get("code") if isinstance(remote_error, dict) else None
    if isinstance(diagnostic_code, str) and diagnostic_code not in {"", "unknown"}:
        return diagnostic_code if diagnostic_code in _REMOTE_AUTH_CODES else ""
    pending, seen = [error], set()
    while pending and len(seen) < 16:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        response = getattr(current, "response", None)
        if response is not None:
            try:
                payload = _auth_payload_from_body(getattr(response, "text", ""))
            except Exception as exc:
                v2._reraise_control(exc)
                payload = {}
            remote_error = payload.get("error")
            candidate = remote_error.get("code") if isinstance(remote_error, dict) else None
            if isinstance(candidate, str) and candidate in _REMOTE_AUTH_CODES:
                return candidate
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)
    return ""


def _auth_error(error: Exception) -> ProtocolPasswordSetupError:
    """保留认证原因，远端原始数据与凭据不进入补密码任务结果。"""
    v2._reraise_control(error)
    code = str(getattr(error, "code", "") or "")
    diagnostics = getattr(error, "diagnostics", {}) or {}
    status = diagnostics.get("http_status") if isinstance(diagnostics, dict) else None
    remote_code = _remote_auth_code(error, diagnostics)
    if isinstance(error, (AuthorizeRouteRejectedError, EmailOtpSendError)):
        status = error.status_code
    if status == 403:
        mapped, message = "password_setup_security_check", "补密码登录未通过远端安全检查"
    elif status == 429:
        mapped, message = "password_setup_rate_limited", "补密码登录受到远端限流，请稍后重试"
    elif isinstance(error, EmailOtpSendError):
        mapped, message = "password_setup_otp_send_unconfirmed", "补密码登录验证码发送未得到有效确认"
    elif code in {"mfa_secret_missing", "mfa_factor_missing", "mfa_secret_invalid", "mfa_rejected"}:
        mapped = "password_setup_" + code
        message = {
            "mfa_secret_missing": "补密码登录需要账号已有的 2FA 密钥",
            "mfa_factor_missing": "补密码登录未取得有效的 2FA 挑战",
            "mfa_secret_invalid": "补密码登录使用的 2FA 密钥格式无效",
            "mfa_rejected": "补密码登录 2FA 验证未通过",
        }[code]
    elif code == "email_otp_failed":
        mapped, message = "password_setup_email_otp_failed", "补密码登录未取得有效的本轮邮箱验证码"
    elif code == "email_otp_rejected" or (code == "email_otp_validate_failed" and remote_code in _OTP_REJECTION_CODES):
        mapped, message = "password_setup_otp_rejected", "补密码登录邮箱验证码被远端拒绝"
    elif code == "email_otp_validate_failed" and remote_code == "identity_provider_mismatch":
        mapped, message = "password_setup_auth_failed", "补密码登录方式与账号的身份提供方不匹配"
    elif code == "email_otp_validate_failed" and status is not None:
        mapped, message = "password_setup_http_rejected", f"补密码登录验证码接口拒绝了请求（HTTP {status}）"
    elif code in {"identity_mismatch", "identity_unconfirmed"}:
        mapped, message = "password_setup_auth_failed", "补密码登录会话身份未能与目标账号对应"
    elif code in {"account_profile_required", "auth_page_unknown", "auth_challenge_loop", "password_missing",
                  "workspace_missing", "workspace_ambiguous", "email_verification_required"}:
        mapped, message = "password_setup_page_unexpected", "补密码登录未进入可完成的已有账号认证页面"
    elif code == "untrusted_auth_url":
        mapped, message = "password_setup_untrusted_redirect", "补密码登录返回了不受信任的跳转目标"
    elif code in {"auth_redirect_invalid", "auth_redirect_limit"}:
        mapped = "password_setup_redirect_invalid" if code == "auth_redirect_invalid" else "password_setup_redirect_limit"
        message = "补密码登录跳转未能正常完成"
    elif code == "access_token_missing":
        mapped, message = "password_setup_access_token_missing", "补密码登录未取得有效 Token"
    elif code == "access_token_expired":
        mapped, message = "password_setup_session_expired", "补密码登录返回的会话已失效"
    elif getattr(error, "category", "") == "response" or code.endswith("_invalid_response"):
        mapped, message = "password_setup_response_invalid", "补密码登录返回了无法确认的数据格式"
    else:
        mapped, message = "password_setup_network_failed", "补密码登录请求未完成，请检查连接后重试"
    return ProtocolPasswordSetupError(mapped, message, proxy_transport_failed=is_proxy_transport_failure(error))


def refresh_access_token(email: str, *, proxy=None, on_authenticated=None, allow_password_email_fallback=True,
                         proxy_supplier=None, on_network_failure=None) -> dict:
    """有密码沿用 v2；无密码只完成已有账号的邮箱、MFA 与回调。"""
    password, secret = get_account_login_credentials(email)
    if password:
        return v2.refresh_access_token(email, proxy=proxy, on_authenticated=on_authenticated,
            allow_password_email_fallback=allow_password_email_fallback,
            **({"proxy_supplier": proxy_supplier} if callable(proxy_supplier) else {}),
            **({"on_network_failure": on_network_failure} if callable(on_network_failure) else {}))

    session = None
    progress = {"methods": [], "attempted": ""}
    try:
        try:
            checkpoint()
            target = db.get_account_by_email(email) or {}
            session, authorize_url = legacy._network_preflight_with_retry(email, proxy or "",
                **({"proxy_supplier": proxy_supplier} if callable(proxy_supplier) else {}),
                **({"on_preflight_failure": on_network_failure} if callable(on_network_failure) else {}))
            checkpoint()
            # 此状态机只提交登录挑战；资料创建页面会明确拒绝。
            with use_cooperative_wait(checkpoint, poll_seconds=5, request_timeout=10):
                info, methods = v3._authenticate(session, authorize_url, email=email, target=target,
                    password="", secret=secret, progress=progress)
            checkpoint()
            v3._verify_identity(info, email, target)
            result = {"ok": True, "status": "live", "checked_at": v2._now(),
                "access_token": info["accessToken"], "session": info,
                "proxy_used": getattr(session, "proxy", None) or None,
                "validation_method": "authenticated_session", "auth_method": "_".join(methods),
                "password_auth_status": "skipped", "fallback_used": False,
                "live_check_driver": "protocol_password_setup", "roxy_fallback_allowed": False,
                "email_otp_status": "success" if "email_otp" in methods else "skipped",
                "mfa_status": "success" if "mfa" in methods else "skipped"}
            result["auth"] = auth_result_for_operation(result, auth_method=result["auth_method"]).as_dict()
            logger.info("[补密码] 已有账号协议认证完成：邮箱验证码=%s，MFA=%s",
                "已通过" if "email_otp" in methods else "无需验证", "已通过" if "mfa" in methods else "无需验证")
        except Exception as exc:
            v2._reraise_control(exc)
            if isinstance(exc, AccountUnusableError) or getattr(exc, "code", "") == "account_deactivated":
                return {"ok": False, "status": "deactivated", "error": "account_deactivated"}
            if callable(on_network_failure):
                on_network_failure(exc)
            raise _auth_error(exc) from None
        checkpoint()
        return on_authenticated(result, session) if callable(on_authenticated) else result
    finally:
        if session is not None:
            try:
                session.session.close()
            except Exception as exc:
                v2._reraise_control(exc)
                logger.warning("[补密码] 登录协议会话关闭失败")
