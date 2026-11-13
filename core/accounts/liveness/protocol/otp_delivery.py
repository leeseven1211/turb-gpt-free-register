"""独立 AT 的邮箱验证码投递，不改变注册及共享认证入口。"""
from __future__ import annotations

import logging
import time
import uuid

from core.auth.protocol.openai_auth import EmailOtpSendError, build_sentinel_header, request_sentinel_token
from core.network.response_diagnostics import _auth_payload_from_body, auth_error_from_body


logger = logging.getLogger(__name__)
_AUTH = "https://auth.openai.com"
_EMAIL_PAGE = _AUTH + "/email-verification"
_INITIAL_MODES = {"passwordless_login", "passwordless_signup"}


class _ContextReadFailure(BaseException):
    """复用会话校验时保留 AT 原始网络和控制异常。"""

    def __init__(self, error: Exception):
        self.error = error


class _ContextReadSession:
    def __init__(self, session):
        self.session = session

    def get_auth_headers(self, **kwargs):
        return self.session.get_auth_headers(**kwargs)

    def get(self, *args, **kwargs):
        try:
            return self.session.get(*args, **kwargs)
        except Exception as exc:
            # 补密码请求包装器会改写网络异常；AT 继续使用本身的预算及恢复分类。
            raise _ContextReadFailure(exc) from exc


def _check(checkpoint) -> None:
    if callable(checkpoint):
        checkpoint()


def _restore_timeout(error: Exception) -> None:
    """旧能力可能包装超时，AT 原有截止时间不能变成普通发码失败。"""
    from core.auth.state_machine import StageTimeout
    from core.network.at_transport_recovery import AtRecoveryTimeout

    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, (StageTimeout, AtRecoveryTimeout)):
            raise current
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)


def _read_context(session, email: str, *, checkpoint=None) -> dict:
    # 补密码模块依赖 v2；只在运行时读取其已有校验器，避免初始化循环。
    from core.accounts.password_setup import protocol as password_setup

    try:
        return password_setup._email_verification_context(
            _ContextReadSession(session), email, referer=_EMAIL_PAGE, checkpoint=checkpoint,
            # AT 自己记录来源；复用校验器不输出“补密码”的阶段日志。
            operation="at_otp_context",
        )
    except _ContextReadFailure as exc:
        raise exc.error
    except password_setup.ProtocolPasswordSetupError as exc:
        _restore_timeout(exc)
        _check(checkpoint)
        logger.warning("[查活][AT] 邮箱验证码会话未确认，尚未派发验证码请求")
        raise EmailOtpSendError("unconfirmed") from exc


def _sentinel_headers(session, *, checkpoint=None) -> dict:
    _check(checkpoint)
    challenge = request_sentinel_token(session, "authorize_continue")
    _check(checkpoint)
    token, observer = build_sentinel_header(session, challenge, "authorize_continue")
    _check(checkpoint)
    if not token:
        logger.warning("[查活][AT] 邮箱验证码初发的安全令牌未确认，尚未派发请求")
        raise EmailOtpSendError("unconfirmed")
    headers = {"openai-sentinel-token": token}
    if observer:
        headers["openai-sentinel-so-token"] = observer
    return headers


def _send_headers(session) -> dict:
    headers = session.get_auth_headers(referer=_EMAIL_PAGE)
    # 无正文 POST 用 None 禁止 libcurl 自动补成表单 Content-Type。
    headers["content-type"] = None
    headers["x-access-flow-invocation-id"] = str(uuid.uuid4())
    return headers


def _confirm_response(response, *, initial: bool) -> None:
    status = int(getattr(response, "status_code", 0) or 0)
    body = getattr(response, "text", "")
    payload = _auth_payload_from_body(body)
    remote_error = auth_error_from_body(body)
    code = remote_error.get("code", "missing")
    logger.info(
        "[查活][AT] 验证码%s接口响应：status=%s remote.error.code=%s",
        "初发" if initial else "重发", status,
        "other" if code == "unknown" else code,
    )
    if not 200 <= status < 300:
        raise EmailOtpSendError("http_error" if status >= 400 else "unconfirmed", status)
    if payload.get("error") or payload.get("success") is False:
        raise EmailOtpSendError("rejected", status)
    if initial:
        page = payload.get("page")
        details = page.get("payload") if isinstance(page, dict) else None
        if (not isinstance(page, dict) or page.get("type") != "email_otp_verification"
                or isinstance(details, dict) and details.get("errors")):
            raise EmailOtpSendError("unconfirmed", status)
    # 已有网页重发契约以 HTTP ok 收口，允许空响应；页面导航不会被当成接口回执。


def ensure_initial_otp_sent(session, email: str, after_ts: float, *, checkpoint=None) -> float:
    """仅明确存在待初发状态时发送；已有挑战沿用原收件窗口。"""
    context = _read_context(session, email, checkpoint=checkpoint)
    pending = context.get("passwordless_email_otp_send_pending")
    if pending is not True:
        logger.info("[查活][AT] 验证页无待初发标记，沿原时间窗等待已有验证码")
        return after_ts
    mode = context.get("email_verification_mode")
    if "email_verification_mode" in context and mode not in _INITIAL_MODES:
        logger.warning("[查活][AT] 验证页待初发模式不受支持，尚未派发验证码请求")
        raise EmailOtpSendError("unconfirmed")
    headers = _send_headers(session)
    headers.update(_sentinel_headers(session, checkpoint=checkpoint))
    current = _read_context(session, email, checkpoint=checkpoint)
    if any(context.get(key) != current.get(key) or (key in context) != (key in current)
           for key in ("session_id", "email", "email_verification_mode")):
        logger.warning("[查活][AT] 验证码初发前认证会话发生变化，尚未派发请求")
        raise EmailOtpSendError("unconfirmed")
    if current.get("passwordless_email_otp_send_pending") is not True:
        logger.info("[查活][AT] 验证码待初发标记已清除，沿原时间窗等待邮件")
        return after_ts
    _check(checkpoint)
    requested_at = time.time()
    response = session.post(_AUTH + "/api/accounts/passwordless/send-otp", headers=headers,
                            allow_redirects=False)
    _check(checkpoint)
    _confirm_response(response, initial=True)
    logger.info("[查活][AT] 验证码初发已由接口接受，等待邮件")
    return requested_at


def resend_otp(session, *, checkpoint=None) -> float:
    """同一 AT 会话明确重发一次，调用方负责沿用原轮数和总预算。"""
    headers = _send_headers(session)
    headers.pop("openai-sentinel-token", None)
    headers.pop("openai-sentinel-so-token", None)
    _check(checkpoint)
    requested_at = time.time()
    response = session.post(_AUTH + "/api/accounts/email-otp/resend", headers=headers,
                            allow_redirects=False)
    _check(checkpoint)
    _confirm_response(response, initial=False)
    logger.info("[查活][AT] 验证码重发已由接口接受，等待邮件")
    return requested_at
