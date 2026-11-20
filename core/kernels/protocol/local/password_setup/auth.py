"""Pure passwordless authentication against an explicitly supplied account identity."""

from __future__ import annotations
import logging
from core.auth.challenge import auth_result_for_operation
from core.email.mailbox_wait import use_cooperative_wait

logger = logging.getLogger("core.accounts.password_setup.auth")


def authenticate_passwordless_session(
    session,
    authorize_url,
    *,
    email,
    target,
    secret,
    progress,
    authenticate,
    verify_identity,
    checkpoint,
    now,
    cooperative_wait=use_cooperative_wait,
    project_auth=auth_result_for_operation,
):
    # 此状态机只提交登录挑战；资料创建页面会明确拒绝。
    with cooperative_wait(checkpoint, poll_seconds=5, request_timeout=10):
        info, methods = authenticate(
            session, authorize_url, email=email, target=target, password="", secret=secret, progress=progress
        )
    checkpoint()
    verify_identity(info, email, target)
    result = {
        "ok": True,
        "status": "live",
        "checked_at": now(),
        "access_token": info["accessToken"],
        "session": info,
        "proxy_used": getattr(session, "proxy", None) or None,
        "validation_method": "authenticated_session",
        "auth_method": "_".join(methods),
        "password_auth_status": "skipped",
        "fallback_used": False,
        "live_check_driver": "protocol_password_setup",
        "roxy_fallback_allowed": False,
        "email_otp_status": "success" if "email_otp" in methods else "skipped",
        "mfa_status": "success" if "mfa" in methods else "skipped",
    }
    result["auth"] = project_auth(result, auth_method=result["auth_method"]).as_dict()
    logger.info(
        "[补密码] 已有账号协议认证完成：邮箱验证码=%s，MFA=%s",
        "已通过" if "email_otp" in methods else "无需验证",
        "已通过" if "mfa" in methods else "无需验证",
    )
    return result
