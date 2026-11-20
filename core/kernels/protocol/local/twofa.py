"""Local HTTP MFA enrollment and reauthentication execution.

Retry configuration, mailbox policy and durable checkpoints are supplied by the
account facade. This module never loads or persists an account.
"""

from __future__ import annotations
import json
import logging
import re
import time
from collections.abc import Mapping
from urllib.parse import urlencode, urlparse
import pyotp
from core.auth.protocol.session import BrowserSession

logger = logging.getLogger("core.account_export")

_TWOFA_PROXY_URL_RE = re.compile(
    r"(?P<scheme>\b[a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@[^\s/]+",
    re.IGNORECASE,
)

_RETRYABLE_REAUTH_HINTS = (
    "403",
    "408",
    "425",
    "429",
    "500",
    "502",
    "503",
    "504",
    "proxy",
    "socks",
    "timeout",
    "timed out",
    "connection",
    "closed",
    "reset",
    "temporarily unavailable",
    "熔断冷却",
)


class TwofaEnrollmentAuthRequired(RuntimeError):
    """The MFA enrollment endpoint requires a fresh authentication step."""

    status_code = 401


class TwofaProtocolHTTPError(RuntimeError):
    """Classified, redacted HTTP failure returned by a protocol MFA endpoint."""

    def __init__(
        self,
        operation: str,
        status_code: int,
        *,
        error_code: str = "",
        error_type: str = "",
        detail: str = "",
        challenge: bool = False,
        business_error: bool = False,
        retry_after: str = "",
    ) -> None:
        self.operation = str(operation or "mfa")
        self.status_code = int(status_code or 0)
        self.error_code = str(error_code or "")[:120]
        self.error_type = str(error_type or "")[:120]
        self.detail = str(detail or "")[:240]
        self.challenge = bool(challenge)
        self.business_error = bool(business_error or error_code or error_type)
        self.retry_after = str(retry_after or "").strip()
        fields = [f"{self.operation} HTTP {self.status_code}"]
        if self.error_code:
            fields.append(f"code={self.error_code}")
        if self.error_type:
            fields.append(f"type={self.error_type}")
        if self.detail:
            fields.append(f"detail={self.detail}")
        super().__init__("; ".join(fields))


class TwofaProtocolTransportError(RuntimeError):
    """Redacted transport failure after the bounded MFA retry is exhausted."""

    def __init__(self, operation: str, cause_type: str) -> None:
        self.operation = str(operation or "mfa")
        self.cause_type = str(cause_type or "TransportError")[:120]
        super().__init__(
            f"{self.operation} transport failed after retry: {self.cause_type} (exception detail redacted)"
        )


class TwofaProtocolStepError(RuntimeError):
    """Redacted non-HTTP failure raised within a protocol MFA step."""

    def __init__(self, operation: str, cause_type: str) -> None:
        self.operation = str(operation or "mfa")
        self.cause_type = str(cause_type or "ProtocolError")[:120]
        super().__init__(f"{self.operation} failed: {self.cause_type} (exception detail redacted)")


def _twofa_error_fields(response, *, sanitize_body=None) -> tuple[str, str, str]:
    """Return only safe diagnostic fields, never the complete response body."""
    try:
        payload = response.json()
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return "", "", ""

    error = payload.get("error")
    source = error if isinstance(error, dict) else payload
    code = str(
        source.get("code") or source.get("error_code") or (error if isinstance(error, str) else "") or ""
    ).strip()
    error_type = str(source.get("type") or source.get("error_type") or "").strip()
    detail = str(source.get("detail") or source.get("message") or source.get("error_description") or "").strip()
    try:
        sanitized, _ = sanitize_body(
            {
                "error_code": code,
                "error_type": error_type,
                "detail": detail,
            }
        )
        if isinstance(sanitized, dict):
            code = str(sanitized.get("error_code") or "")
            error_type = str(sanitized.get("error_type") or "")
            detail = str(sanitized.get("detail") or "")
    except Exception:
        code = error_type = detail = ""
    code = _TWOFA_PROXY_URL_RE.sub(r"\g<scheme><redacted-proxy>", code)
    error_type = _TWOFA_PROXY_URL_RE.sub(r"\g<scheme><redacted-proxy>", error_type)
    detail = _TWOFA_PROXY_URL_RE.sub(r"\g<scheme><redacted-proxy>", detail)
    return code[:120], error_type[:120], detail[:240]


def _twofa_http_error(operation: str, response, *, _twofa_error_fields=_twofa_error_fields) -> TwofaProtocolHTTPError:
    code, error_type, detail = _twofa_error_fields(response)
    raw_headers = getattr(response, "headers", None)
    headers = (
        {str(key).lower(): str(value) for key, value in raw_headers.items()} if isinstance(raw_headers, Mapping) else {}
    )
    raw_body = getattr(response, "text", "")
    body = raw_body[:8192].lower() if isinstance(raw_body, str) else ""
    challenge = headers.get("cf-mitigated", "").lower() == "challenge" or any(
        marker in body for marker in ("cf-chl-", "challenge-platform", "captcha")
    )
    try:
        payload = response.json()
    except Exception:
        payload = None
    business_error = bool(code or error_type or (payload.get("error") if isinstance(payload, dict) else False))
    if operation == "reauth_otp_validate":
        # OTP 响应可能回显验证码或凭据，只保留短错误标识和固定中文诊断。
        code = code if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.-]{0,79}", code) else ""
        error_type = error_type if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.-]{0,79}", error_type) else ""
        detail = "需要交互验证" if challenge else "服务端明确拒绝验证" if business_error else "验证码请求临时失败"
    return TwofaProtocolHTTPError(
        operation,
        int(getattr(response, "status_code", 0) or 0),
        error_code=code,
        error_type=error_type,
        detail=detail,
        challenge=challenge,
        business_error=business_error,
        retry_after=headers.get("retry-after", ""),
    )


def _is_retryable_twofa_transport_error(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc or "").lower()
    return any(
        marker in name or marker in text
        for marker in (
            "proxy",
            "ssl",
            "timeout",
            "timed out",
            "connection",
            "connect",
            "reset",
            "closed",
            "curl: (35)",
            "curl: (56)",
            "熔断冷却",
        )
    )


def _activation_400_is_retryable(exc: TwofaProtocolHTTPError) -> bool:
    """Retry a stale code/session once, but not a route or feature rejection."""
    full_text = " ".join((exc.error_code, exc.error_type, exc.detail)).lower()
    if any(
        marker in full_text
        for marker in (
            "invalid url",
            "route",
            "not found",
            "unsupported",
            "not supported",
            "already enabled",
            "already active",
            "duplicate factor",
            "unknown factor",
        )
    ):
        return False
    if not full_text:
        # The affected batch discarded the body. One fresh-code retry is safe,
        # bounded, and supplies diagnostic fields if the second call fails.
        return True
    # ``type=invalid_request`` alone is a generic business rejection.  Only
    # retry when the code/detail specifically identifies the TOTP or enrollment
    # session as the stale input.
    code_detail = " ".join((exc.error_code, exc.detail)).lower()
    return any(
        marker in code_detail
        for marker in (
            "code",
            "otp",
            "totp",
            "verification",
            "enrollment",
            "session",
            "expired",
            "stale",
        )
    )


def _wait_for_next_totp_window(*, clock=time) -> None:
    remaining = 30 - (int(clock.time()) % 30)
    clock.sleep(min(31, remaining + 1))


def _clear_twofa_session_circuit(session: BrowserSession, *, source: str = "可选预热") -> None:
    """清理可恢复 2FA 请求留下的会话熔断，保留 Cookie 和设备身份。"""
    blocked_reason = str(getattr(session, "blocked_reason", "") or "")
    reset = getattr(session, "reset_circuit_breaker", None)
    if callable(reset):
        reset()
    elif getattr(session, "blocked_until", 0.0):
        # 兼容当前 BrowserSession 以及测试桩；不重建会话，保留 CF Cookie。
        session.blocked_until = 0.0
        session.blocked_reason = ""
    if blocked_reason:
        logger.info("[2FA] 已清理%s产生的熔断状态（原因原文不写日志）", source)


def _is_retryable_reauth_error(exc: BaseException) -> bool:
    """只重试限流、服务端错误和传输故障，不重试普通业务 4xx。"""
    if isinstance(exc, TwofaProtocolTransportError):
        return True
    response = getattr(exc, "response", None)
    try:
        status = int(getattr(exc, "status_code", 0) or getattr(response, "status_code", 0) or 0)
    except (TypeError, ValueError):
        status = 0
    if status:
        return status in (403, 408, 425, 429) or status >= 500
    text = str(exc or "").lower()
    return any(hint in text for hint in _RETRYABLE_REAUTH_HINTS)


def _raise_twofa_http_response(operation: str, response, *, _twofa_http_error=_twofa_http_error) -> None:
    status = int(getattr(response, "status_code", 0) or 0)
    if status >= 400:
        raise _twofa_http_error(operation, response) from None


def _run_reauth_step_with_retry(
    operation: str,
    session: BrowserSession,
    callback,
    *,
    retry_forbidden: bool = True,
    _clear_twofa_session_circuit=_clear_twofa_session_circuit,
    _is_retryable_reauth_error=_is_retryable_reauth_error,
    _twofa_http_error=_twofa_http_error,
    _reauth_retry_settings=lambda: (3, 3.0),
    clock=time,
):
    """Run one protocol reauthentication step with bounded, redacted retries."""
    max_attempts, base_delay = _reauth_retry_settings()
    for attempt in range(1, max_attempts + 1):
        try:
            result = callback()
            if attempt > 1:
                logger.info(
                    "[2FA] %s 重试成功：attempt=%s/%s",
                    operation,
                    attempt,
                    max_attempts,
                )
            return result
        except Exception as exc:
            retryable = _is_retryable_reauth_error(exc)
            response = getattr(exc, "response", None)
            status = int(getattr(exc, "status_code", 0) or getattr(response, "status_code", 0) or 0)
            if status == 403 and not retry_forbidden:
                retryable = False
            if attempt >= max_attempts or not retryable:
                logger.warning(
                    "[2FA] %s 失败且不再重试：attempt=%s/%s retryable=%s error=%s status=%s（异常原文不写日志）",
                    operation,
                    attempt,
                    max_attempts,
                    retryable,
                    type(exc).__name__,
                    status or "-",
                )
                if isinstance(exc, (TwofaProtocolHTTPError, TwofaProtocolStepError)):
                    raise exc from None
                if response is not None and status:
                    raise _twofa_http_error(operation, response) from None
                if retryable:
                    raise TwofaProtocolTransportError(operation, type(exc).__name__) from None
                raise TwofaProtocolStepError(operation, type(exc).__name__) from None
            _clear_twofa_session_circuit(session, source=operation)
            delay = min(120.0, base_delay * (2 ** (attempt - 1)))
            logger.warning(
                "[2FA] %s 临时失败：attempt=%s/%s error=%s status=%s；%.1fs 后重试（异常原文不写日志）",
                operation,
                attempt,
                max_attempts,
                type(exc).__name__,
                status or "-",
                delay,
            )
            if delay > 0:
                clock.sleep(delay)
    raise RuntimeError(f"{operation} 重试耗尽")


def follow_oauth_callback(
    session: BrowserSession,
    continue_url: str,
    referer: str = "https://auth.openai.com/about-you",
    *,
    timeout: float | None = None,
) -> str:
    """
    步骤12.5: 跟随 create_account 返回的 continue_url，完成 OAuth 回调。

    create_account 成功后返回的 continue_url 一般指向
        https://auth.openai.com/authorize/continue?...
    它会再 302 到
        https://chatgpt.com/api/auth/callback/openai?code=...&state=...
    回调请求会让 chatgpt.com 设置 `__Secure-next-auth.session-token` cookie，
    之后 /api/auth/session 才能返回 accessToken。

    Returns:
        重定向链最终落点 URL（一般是 chatgpt.com 站内地址）
    """
    if not continue_url:
        raise ValueError("continue_url 为空，无法完成 OAuth 回调")

    # continue_url 通常是 auth.openai.com/authorize/continue；
    # OTP 后 external_url 分支也可能直接给 chatgpt.com 回调地址。
    # 按目标域名选择导航头，避免 auth step 正确但请求头语义不一致。
    if str(continue_url).startswith("https://chatgpt.com"):
        headers = session.get_chatgpt_navigate_headers(referer=referer)
    else:
        headers = session.get_auth_navigate_headers(referer=referer)

    logger.info(f"[OAuth回调] 跟随 continue_url 完成 OAuth 回调...")
    request_kwargs = {} if timeout is None else {"timeout": timeout}
    resp = session.get(continue_url, headers=headers, allow_redirects=True, **request_kwargs)
    # 必须在本阶段暴露 callback 的 403/429；否则 BrowserSession 虽已熔断，
    # 错误却会延迟到 fetch_session，查活无法针对 callback 原请求重试。
    resp.raise_for_status()
    observe = getattr(session, "observe_chatgpt_document", None)
    if callable(observe):
        observe(resp)
    logger.info("[OAuth回调] 完成（最终落点原值不写日志）")
    return resp.url


def fetch_session(session: BrowserSession, *, timeout: float | None = None) -> dict:
    """
    GET https://chatgpt.com/api/auth/session
    注册成功后立刻调用，拿到 accessToken / user / account / expires。

    Returns:
        完整 session JSON，包含字段:
            - accessToken: str (Bearer token, 用于 backend-api 调用)
            - user: {id, name, email, idp, iat, mfa}
            - account: {id, planType, structure, ...}
            - expires: ISO 时间字符串
    """
    url = "https://chatgpt.com/api/auth/session"
    headers = session.get_nextauth_headers(referer="https://chatgpt.com/")

    logger.info("[Session] 拉取 ChatGPT session 信息...")
    request_kwargs = {} if timeout is None else {"timeout": timeout}
    resp = session.get(url, headers=headers, **request_kwargs)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("accessToken"):
        logger.error("[Session] 响应中没有 accessToken（响应原值不写日志）")
        raise RuntimeError("未拿到 accessToken，登录态可能未建立")

    user = data.get("user") or {}
    account = data.get("account") or {}
    logger.info(
        f"[Session] 成功，user_id={user.get('id')}, email={user.get('email')}, "
        f"plan={account.get('planType')}, mfa={user.get('mfa')}"
    )
    return data


def _trigger_reauth(
    session: BrowserSession, email: str, *, _raise_twofa_http_response=_raise_twofa_http_response
) -> str:
    """
    步骤2-3: 发起重认证，返回 OpenAI authorize URL。
    后续须确认实际认证页面，再显式请求本次邮箱验证码。
    """
    # 重新拿一次 csrf（旧的可能已过期）
    csrf_url = "https://chatgpt.com/api/auth/csrf"
    csrf_resp = session.get(csrf_url, headers=session.get_nextauth_headers(referer="https://chatgpt.com/"))
    _raise_twofa_http_response("reauth_csrf", csrf_resp)
    csrf_token = csrf_resp.json()["csrfToken"]
    logger.info("[2FA] 重认证 CSRF 已获取（原值不写日志）")

    # POST /api/auth/signin/openai 带 reauth 参数
    query = {
        "connection": "password",
        "login_hint": email,
        "reauth": "password",
        "max_age": "0",
        "ext-oai-did": session.device_id,
    }
    signin_url = "https://chatgpt.com/api/auth/signin/openai?" + urlencode(query)

    headers = session.get_nextauth_headers(referer="https://chatgpt.com/")
    headers["content-type"] = "application/x-www-form-urlencoded"
    headers["origin"] = "https://chatgpt.com"

    body = urlencode(
        {
            "callbackUrl": "https://chatgpt.com/?action=enable&factor=totp",
            "csrfToken": csrf_token,
            "json": "true",
        }
    )

    logger.info("[2FA] 发起重认证 signin/openai...")
    resp = session.post(signin_url, headers=headers, data=body)
    _raise_twofa_http_response("reauth_signin", resp)
    auth_url = resp.json().get("url")
    if not auth_url:
        raise RuntimeError("未拿到 reauth authorize URL（原始响应未记录）")
    return auth_url


def _follow_reauth(
    session: BrowserSession, auth_url: str, *, _raise_twofa_http_response=_raise_twofa_http_response
) -> str:
    """
    步骤3: 跟随 authorize URL，确认已进入邮箱验证码页。
    页面就绪不代表已经发码，调用方必须单独确认发码后再收取邮件。
    """
    headers = session.get_auth_navigate_headers(referer="https://chatgpt.com/")
    logger.info("[2FA] 跟随 authorize URL，确认认证落点...")
    resp = session.get(auth_url, headers=headers, allow_redirects=True)
    _raise_twofa_http_response("reauth_authorize", resp)
    final_url = str(getattr(resp, "url", "") or "")
    try:
        parsed = urlparse(final_url)
        expected_origin = (
            parsed.scheme == "https"
            and parsed.hostname == "auth.openai.com"
            and parsed.port in (None, 443)
            and not parsed.username
            and not parsed.password
        )
        path = parsed.path.rstrip("/")
    except ValueError:
        expected_origin, path = False, ""
    if not expected_origin or path != "/email-verification":
        page_type = (
            {
                "/log-in/password": "password",
                "/create-account/password": "password",
                "/log-in": "login",
                "/error": "error",
            }.get(path, "unknown")
            if expected_origin
            else "unexpected_origin"
        )
        logger.warning("[2FA] 重认证未进入邮箱验证码页，页面类型=%s，交给调用方恢复认证", page_type)
        raise TwofaProtocolStepError("reauth_authorize", f"unexpected_auth_page:{page_type}")
    logger.info("[2FA] 已到达邮箱验证页面（落点 URL 原值不写日志）")
    return final_url


def _trigger_reauth_with_retry(
    session: BrowserSession,
    email: str,
    *,
    _run_reauth_step_with_retry=_run_reauth_step_with_retry,
    _trigger_reauth=_trigger_reauth,
) -> str:
    """对 CSRF + signin 阶段的临时故障执行有限退避重试。"""
    return str(
        _run_reauth_step_with_retry(
            "重认证发起",
            session,
            lambda: _trigger_reauth(session, email),
        )
    )


def _warm_auth_document_for_reauth(
    session: BrowserSession, *, _clear_twofa_session_circuit=_clear_twofa_session_circuit, clock=time
) -> None:
    """预热 auth.openai.com 顶层文档，给 authorize 链建立域 Cookie 上下文。"""
    get_headers = getattr(session, "get_auth_navigate_headers", None)
    request_get = getattr(session, "get", None)
    if not callable(get_headers) or not callable(request_get):
        return
    headers = get_headers(referer="", user_initiated=False)
    for attempt in range(1, 3):
        try:
            resp = request_get(
                "https://auth.openai.com/log-in",
                headers=headers,
                allow_redirects=True,
            )
            status = int(getattr(resp, "status_code", 0) or 0)
            if status < 400:
                logger.info("[2FA] Auth document 预热完成")
                return
            logger.info("[2FA] Auth document 预热返回 HTTP %s，保留响应 Cookie", status)
        except Exception as exc:
            logger.debug(
                "[2FA] Auth document 预热异常：%s（异常原文不写日志）",
                type(exc).__name__,
            )
        _clear_twofa_session_circuit(session, source="Auth document 预热")
        if attempt < 2:
            clock.sleep(float(attempt))
    logger.info("[2FA] Auth document 预热未通过，继续正式 authorize 重试链")


def _follow_reauth_with_retry(
    session: BrowserSession,
    auth_url: str,
    *,
    _follow_reauth=_follow_reauth,
    _run_reauth_step_with_retry=_run_reauth_step_with_retry,
    _warm_auth_document_for_reauth=_warm_auth_document_for_reauth,
) -> str:
    """重试跨站 authorize 导航；保留同一会话中的 CF Cookie 和 OAuth 状态。"""
    _warm_auth_document_for_reauth(session)
    result = _run_reauth_step_with_retry(
        "authorize 导航",
        session,
        lambda: _follow_reauth(session, auth_url),
    )
    return str(result or auth_url)


def _validate_reauth_otp(
    session: BrowserSession, code: str, *, _raise_twofa_http_response=_raise_twofa_http_response
) -> str:
    """
    步骤4: 提交邮箱 OTP 验证。
    返回 continue_url（带 code 参数的 callback URL，用于跳回 chatgpt.com）。
    """
    url = "https://auth.openai.com/api/accounts/email-otp/validate"
    headers = session.get_auth_headers(referer="https://auth.openai.com/email-verification")
    body = json.dumps({"code": code})

    logger.info("[2FA] 提交重认证 OTP（验证码原值不写日志）")
    resp = session.post(url, headers=headers, data=body)
    _raise_twofa_http_response("reauth_otp_validate", resp)
    data = resp.json()
    continue_url = data.get("continue_url")
    if not continue_url:
        raise RuntimeError("OTP 验证响应缺少 continue_url（原始响应未记录）")
    return continue_url


def _validate_reauth_otp_with_retry(
    session: BrowserSession,
    code: str,
    *,
    _clear_twofa_session_circuit=_clear_twofa_session_circuit,
    _is_retryable_twofa_transport_error=_is_retryable_twofa_transport_error,
    _validate_reauth_otp=_validate_reauth_otp,
    _reauth_retry_settings=lambda: (3, 3.0),
    clock=time,
) -> str:
    """对没有业务拒绝或挑战的 403/429 复用原会话、原验证码有限重试。"""
    max_attempts, base_delay = _reauth_retry_settings()
    for attempt in range(1, max_attempts + 1):
        try:
            return str(_validate_reauth_otp(session, code))
        except TwofaProtocolHTTPError as exc:
            if exc.status_code not in (403, 429) or exc.challenge or exc.business_error or attempt >= max_attempts:
                raise
            retry_after = exc.retry_after
            if retry_after and (
                not retry_after.isascii() or not retry_after.isdigit() or len(retry_after) > 3 or int(retry_after) > 120
            ):
                raise
            delay = max(min(120.0, base_delay * 2 ** (attempt - 1)), int(retry_after or 0))
            logger.warning(
                "[2FA] OTP 临时拒绝 HTTP %s，%.1fs 后复用原会话重试（%s/%s），不重新发码",
                exc.status_code,
                delay,
                attempt,
                max_attempts,
            )
            if delay:
                clock.sleep(delay)
            _clear_twofa_session_circuit(session, source="OTP 临时拒绝")
        except Exception as exc:
            # 传输异常无法确认远端是否已验证，不在当前调用里自动重放 POST。
            error_class = (
                TwofaProtocolTransportError if _is_retryable_twofa_transport_error(exc) else TwofaProtocolStepError
            )
            raise error_class("重认证 OTP 校验", type(exc).__name__) from None
    raise RuntimeError("2FA OTP 重试耗尽")


def _exchange_new_token(
    session: BrowserSession,
    continue_url: str,
    *,
    _raise_twofa_http_response=_raise_twofa_http_response,
    fetch_session=fetch_session,
) -> str:
    """
    步骤5: 跟随 continue_url 完成回调，再次拉 /api/auth/session 拿到新 accessToken
    （此时 token 内嵌的 pwd_auth_time 是新鲜的，2FA enroll 才会接受）。
    """
    headers = session.get_auth_navigate_headers(referer="https://auth.openai.com/email-verification")
    logger.info("[2FA] 跟随 continue_url，刷新 session-token cookie...")
    response = session.get(continue_url, headers=headers, allow_redirects=True)
    _raise_twofa_http_response("reauth_token_callback", response)

    # 拿新的 accessToken
    new_session = fetch_session(session)
    new_token = new_session["accessToken"]
    logger.info("[2FA] 新 accessToken 已获取（原值不写日志）")
    return new_token


def _exchange_new_token_with_retry(
    session: BrowserSession,
    continue_url: str,
    *,
    _exchange_new_token=_exchange_new_token,
    _run_reauth_step_with_retry=_run_reauth_step_with_retry,
) -> str:
    """完成回调并刷新 token；临时网络/HTTP 故障复用当前会话重试。"""
    return str(
        _run_reauth_step_with_retry(
            "重认证 token 交换",
            session,
            lambda: _exchange_new_token(session, continue_url),
        )
    )


def _enroll_totp(
    session: BrowserSession,
    access_token: str,
    *,
    _clear_twofa_session_circuit=_clear_twofa_session_circuit,
    _is_retryable_twofa_transport_error=_is_retryable_twofa_transport_error,
    _twofa_http_error=_twofa_http_error,
    clock=time,
) -> tuple[str, str]:
    """
    步骤6: 注册 TOTP，返回 (secret, session_id)
    """
    url = "https://chatgpt.com/backend-api/accounts/mfa/enroll"
    headers = session.get_chatgpt_headers(referer="https://chatgpt.com/")
    headers["authorization"] = f"Bearer {access_token}"
    headers["oai-device-id"] = session.device_id
    headers["oai-language"] = session.navigator_language()

    body = json.dumps({"factor_type": "totp"})

    logger.info("[2FA] 注册 TOTP...")
    for attempt in range(1, 3):
        try:
            resp = session.post(url, headers=headers, data=body)
        except Exception as exc:
            if _is_retryable_twofa_transport_error(exc):
                if attempt < 2:
                    _clear_twofa_session_circuit(session, source="MFA enroll")
                    logger.warning(
                        "[2FA] enroll 临时网络错误，1.5s 后重试：%s（异常原文不写日志）",
                        type(exc).__name__,
                    )
                    clock.sleep(1.5)
                    continue
                raise TwofaProtocolTransportError("enroll", type(exc).__name__) from None
            raise TwofaProtocolStepError("enroll", type(exc).__name__) from None
        status = int(resp.status_code or 0)
        if status == 200:
            break
        if status == 401:
            logger.error("[2FA] enroll 失败 HTTP 401：需要近期重新认证")
            raise TwofaEnrollmentAuthRequired("MFA enroll 要求近期重新认证，当前 access_token 不能直接开通")
        if attempt < 2 and (status in (408, 425, 429) or status >= 500):
            _clear_twofa_session_circuit(session, source="MFA enroll")
            logger.warning("[2FA] enroll 临时 HTTP %s，1.5s 后重试", status)
            clock.sleep(1.5)
            continue
        error = _twofa_http_error("enroll", resp)
        logger.error("[2FA] %s", error)
        raise error
    else:
        raise RuntimeError("MFA enroll 重试耗尽")

    data = resp.json()
    secret = data.get("secret")
    session_id = data.get("session_id")
    if not secret or not session_id:
        raise RuntimeError("enroll 响应字段缺失（原始响应未记录）")
    logger.info("[2FA] TOTP secret 已获取（原值不写日志）")
    return secret, session_id


def _activate_totp(
    session: BrowserSession,
    access_token: str,
    secret: str,
    session_id: str,
    *,
    _activation_400_is_retryable=_activation_400_is_retryable,
    _clear_twofa_session_circuit=_clear_twofa_session_circuit,
    _is_retryable_twofa_transport_error=_is_retryable_twofa_transport_error,
    _twofa_http_error=_twofa_http_error,
    _wait_for_next_totp_window=_wait_for_next_totp_window,
    clock=time,
    totp_factory=pyotp.TOTP,
) -> bool:
    """
    步骤7: 用 secret 生成 6 位 TOTP 码，激活 2FA。
    """
    url = "https://chatgpt.com/backend-api/accounts/mfa/user/activate_enrollment"
    headers = session.get_chatgpt_headers(referer="https://chatgpt.com/")
    headers["authorization"] = f"Bearer {access_token}"
    headers["oai-device-id"] = session.device_id
    headers["oai-language"] = session.navigator_language()

    totp_code = totp_factory(secret).now()
    body = json.dumps(
        {
            "code": totp_code,
            "factor_type": "totp",
            "session_id": session_id,
        }
    )

    logger.info("[2FA] 激活 enrollment（TOTP 原值不写日志）")
    wait_for_fresh_totp = False
    for attempt in range(1, 3):
        if attempt > 1:
            if wait_for_fresh_totp:
                _wait_for_next_totp_window()
            body = json.dumps(
                {
                    "code": totp_factory(secret).now(),
                    "factor_type": "totp",
                    "session_id": session_id,
                }
            )
        try:
            resp = session.post(url, headers=headers, data=body)
        except Exception as exc:
            if _is_retryable_twofa_transport_error(exc):
                if attempt < 2:
                    _clear_twofa_session_circuit(session, source="MFA activate")
                    logger.warning(
                        "[2FA] activate 临时网络错误，1.5s 后重试：%s（异常原文不写日志）",
                        type(exc).__name__,
                    )
                    clock.sleep(1.5)
                    continue
                raise TwofaProtocolTransportError("activate", type(exc).__name__) from None
            raise TwofaProtocolStepError("activate", type(exc).__name__) from None

        status = int(resp.status_code or 0)
        if status == 200:
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError("激活返回 success=false（原始响应未记录）")
            return True

        if attempt < 2 and (status in (408, 425, 429) or status >= 500):
            _clear_twofa_session_circuit(session, source="MFA activate")
            logger.warning("[2FA] activate 临时 HTTP %s，1.5s 后重试", status)
            clock.sleep(1.5)
            continue

        error = _twofa_http_error("activate", resp)
        logger.error("[2FA] %s", error)
        if attempt < 2 and error.status_code == 400 and _activation_400_is_retryable(error):
            wait_for_fresh_totp = True
            logger.warning("[2FA] activate 400 属于验证码/会话候选错误，等待新 TOTP 窗口重试一次")
            continue
        raise error

    raise RuntimeError("MFA activate 重试耗尽")


def setup_2fa_protocol(
    session: BrowserSession,
    access_token: str,
    *,
    on_secret=None,
    enroll_totp=None,
    activate_totp=None,
    totp_factory=pyotp.TOTP,
    clock=time,
) -> str:
    """Enroll and activate with the checkpoint emitted before the final POST."""
    token = str(access_token or "").strip()
    if not token:
        raise ValueError("协议开通 2FA 缺少 accessToken")
    enroll = enroll_totp or (lambda current, value: _enroll_totp(current, value, clock=clock))
    activate = activate_totp or (
        lambda current, value, secret, enrollment: _activate_totp(
            current, value, secret, enrollment, totp_factory=totp_factory, clock=clock
        )
    )
    secret, session_id = enroll(session, token)
    if on_secret is not None:
        on_secret(secret)
    remaining = 30 - (int(clock.time()) % 30)
    if remaining < 6:
        clock.sleep(remaining + 1)
    activate(session, token, secret, session_id)
    logger.info("[2FA] 协议模式设置完成")
    return secret
