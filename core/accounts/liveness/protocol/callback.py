"""AT 刷新专用回调恢复；保留原会话，最多使用一次恢复机会。"""
from __future__ import annotations

import base64
import json
import logging
import math
import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

from core.auth.state_machine import CancellationRequested
from core.operations.runtime import OperationAccountDeactivated, OperationCancelled, check_cancelled
from core.operations.task_gateway import OperationLeaseLost
from core.network.at_transport_recovery import AtRecoveryTimeout

logger = logging.getLogger("core.at_callback")
_AUTH = "https://auth.openai.com"
_CHAT = "https://chatgpt.com"
_SESSION_URL = _CHAT + "/api/auth/session"
_HOSTS = {"auth.openai.com", "chatgpt.com"}
_REDIRECTS = {301, 302, 303, 307, 308}
_TEMPORARY_HTTP = {502, 503, 504}
_TEMPORARY_CURL = {5, 6, 7, 16, 18, 28, 35, 52, 55, 56, 92, 95, 97}
_CALLBACK_ERROR_CODES = {"OAuthCallback", "OAuthSignin", "Configuration", "AccessDenied", "invalid_state", "invalid_grant"}
_CONTROL_ERRORS = (CancellationRequested, OperationCancelled, OperationLeaseLost, OperationAccountDeactivated, AtRecoveryTimeout)


class CallbackRecoveryError(RuntimeError):
    """向 AT 驱动提供固定原因码与不含凭据的现场。"""

    def __init__(self, code: str, *, category: str = "response", retryable: bool = False, diagnostics: dict | None = None):
        self.code = code
        self.category = category
        self.retryable = bool(retryable)
        self.diagnostics = dict(diagnostics or {})
        super().__init__(code)


@dataclass
class _Recovery:
    used: bool = False

    def claim(self) -> bool:
        if self.used:
            return False
        self.used = True
        return True


def _check(checkpoint) -> None:
    check_cancelled("AT 回调恢复已取消")
    if callable(checkpoint):
        checkpoint()


def _reraise_control(exc: BaseException) -> None:
    pending, visited = [exc], set()
    while pending:
        item = pending.pop()
        if id(item) in visited:
            continue
        visited.add(id(item))
        if isinstance(item, _CONTROL_ERRORS):
            raise item
        pending.extend(value for value in (item.__cause__, item.__context__) if value is not None)


def _target(url: str) -> dict:
    parsed = urlparse(url)
    return {"target_host": parsed.hostname or "", "target_path": (parsed.path or "/")[:240]}


def _status(response) -> int:
    try:
        status = int(getattr(response, "status_code", 0) or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    return status if 100 <= status <= 599 else 0


def _diagnostics(operation: str, url: str, *, kind: str, hop: int, attempt: int, response=None, exc=None) -> dict:
    response = response if response is not None else getattr(exc, "response", None)
    status = _status(response)
    result = {
        "operation": operation, "failure_kind": kind, "response_observed": 100 <= status <= 599,
        "redirect_hop": hop, "retry_attempt": attempt, **_target(url),
    }
    if 100 <= status <= 599:
        result["http_status"] = status
    if exc is not None:
        result["exception_type"] = type(exc).__name__[:80]
        curl_code = getattr(exc, "code", None)
        if isinstance(curl_code, bool):
            curl_code = None
        try:
            curl_code = int(curl_code) if curl_code is not None else None
        except (TypeError, ValueError, OverflowError):
            curl_code = None
        if curl_code is None:
            match = re.search(r"\bcurl\s*:\s*\((\d{1,3})\)", str(exc), re.IGNORECASE)
            curl_code = int(match.group(1)) if match else None
        if curl_code is not None and 0 <= curl_code <= 999:
            result["curl_error_code"] = curl_code
    return result


def _failure(code: str, operation: str, url: str, *, kind: str, hop: int, attempt: int, response=None, exc=None) -> CallbackRecoveryError:
    diagnostics = _diagnostics(operation, url, kind=kind, hop=hop, attempt=attempt, response=response, exc=exc)
    curl_code = diagnostics.get("curl_error_code")
    exception_type = str(diagnostics.get("exception_type") or "").lower()
    temporary_transport = kind == "transport_error" and (
        curl_code in _TEMPORARY_CURL
        or (curl_code is None and any(part in exception_type for part in ("timeout", "connection", "ssl", "proxy")))
    )
    failure = CallbackRecoveryError(
        code, category="network" if kind in {"transport_error", "http_error"} else "response",
        retryable=temporary_transport or (kind == "http_error" and diagnostics.get("http_status") in _TEMPORARY_HTTP),
        diagnostics=diagnostics,
    )
    from core.network.at_transport_recovery import current_scope, exhausted, network_failure

    if exhausted(exc) or exhausted(response):
        failure._at_recovery_exhausted = current_scope()
    if current_scope() is not None:
        failure.retryable = network_failure(error=exc, response=response) is not None
    return failure


def _trusted_url(value: str, *, base: str = _AUTH) -> str:
    try:
        target = urljoin(base, str(value or ""))
        parsed = urlparse(target)
        if (not value or parsed.scheme != "https" or parsed.hostname not in _HOSTS
                or parsed.port not in (None, 443) or parsed.username or parsed.password):
            raise ValueError
        return urlunparse(parsed._replace(fragment=""))
    except (TypeError, ValueError):
        # 非法输入不进入诊断，避免 URL 解析异常回显私有参数。
        raise CallbackRecoveryError("auth_redirect_invalid", diagnostics={
            "operation": "oauth_callback", "failure_kind": "redirect_invalid",
            "response_observed": False, "redirect_hop": 0, "retry_attempt": 0,
        }) from None


def _close(response) -> None:
    close = getattr(response, "close", None)
    if callable(close):
        try:
            close()
        except Exception as exc:
            _reraise_control(exc)
            logger.debug("[AT回调] 关闭响应失败：%s", type(exc).__name__)


def _callback_rejection(url: str) -> str:
    """仅识别可信错误页中的固定上游码，不保存或转述原始 query。"""
    parsed = urlparse(url)
    if (parsed.hostname, parsed.path) not in {("chatgpt.com", "/api/auth/error"), ("auth.openai.com", "/error")}:
        return ""
    try:
        codes = parse_qs(parsed.query, max_num_fields=100).get("error") or []
    except ValueError:
        return ""
    return codes[0] if len(codes) == 1 and codes[0] in _CALLBACK_ERROR_CODES else ""


def _has_session_cookie(session) -> bool:
    cookies = getattr(getattr(session, "session", None), "cookies", None)
    jar = getattr(cookies, "jar", cookies)
    try:
        for cookie in jar or ():
            name = str(getattr(cookie, "name", ""))
            domain = str(getattr(cookie, "domain", "")).lstrip(".").lower()
            if domain == "chatgpt.com" and name.startswith("__Secure-next-auth.session-token") and getattr(cookie, "value", ""):
                return True
    except (TypeError, AttributeError):
        pass
    return False


def _verify_session(info, email: str, *, hop: int, attempt: int) -> dict:
    def rejected(code, kind):
        return _failure(code, "session_fetch", _SESSION_URL, kind=kind, hop=hop, attempt=attempt)

    if not isinstance(info, dict):
        raise rejected("session_invalid_response", "invalid_response")
    token = info.get("accessToken")
    if not isinstance(token, str) or not token.strip():
        raise rejected("access_token_missing", "missing_token")
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        expiry = payload.get("exp")
        if not isinstance(expiry, (int, float)) or isinstance(expiry, bool) or not math.isfinite(expiry):
            raise ValueError
    except (ValueError, TypeError, AttributeError, UnicodeError, OverflowError):
        raise rejected("session_invalid_response", "invalid_response") from None
    if expiry <= time.time():
        raise rejected("access_token_expired", "token_expired")
    user = info.get("user")
    if not isinstance(user, dict) or str(user.get("email") or "").strip().lower() != email.strip().lower():
        raise rejected("session_identity_mismatch", "identity_mismatch")
    profile = payload.get("https://api.openai.com/profile") or {}
    auth = payload.get("https://api.openai.com/auth") or {}
    if not isinstance(profile, dict) or not isinstance(auth, dict):
        raise rejected("session_invalid_response", "invalid_response")
    claim_email = profile.get("email") or payload.get("email")
    claim_user = auth.get("chatgpt_user_id") or auth.get("user_id")
    account = info.get("account") or {}
    if (claim_email and str(claim_email).strip().lower() != email.strip().lower()
            or claim_user and user.get("id") and str(claim_user) != str(user["id"])
            or auth.get("chatgpt_account_id") and isinstance(account, dict) and account.get("id")
            and str(auth["chatgpt_account_id"]) != str(account["id"])):
        raise rejected("session_identity_mismatch", "identity_mismatch")
    return info


def _read_session(session, email: str, *, recovery: _Recovery, hop: int, checkpoint, probe: bool = False) -> dict:
    attempt = 0
    while True:
        _check(checkpoint)
        response = None
        try:
            try:
                response = session.get(_SESSION_URL, headers=session.get_nextauth_headers(referer=_CHAT + "/"), allow_redirects=False)
            except Exception as exc:
                _reraise_control(exc)
                raise _failure("session_fetch_failed", "session_fetch", _SESSION_URL, kind="transport_error", hop=hop, attempt=attempt, exc=exc) from None
            _check(checkpoint)
            status = _status(response)
            logger.info("[AT回调] 读取 Session host=chatgpt.com path=/api/auth/session status=%s retry=%s", status, attempt)
            if not status:
                raise _failure("session_invalid_response", "session_fetch", _SESSION_URL, kind="invalid_response", hop=hop, attempt=attempt, response=response)
            if probe and status == 401:
                raise _failure("access_token_missing", "session_fetch", _SESSION_URL, kind="missing_token", hop=hop, attempt=attempt, response=response)
            if not 200 <= status < 300:
                raise _failure("session_fetch_failed", "session_fetch", _SESSION_URL, kind="http_error", hop=hop, attempt=attempt, response=response)
            try:
                info = response.json()
            except Exception as exc:
                _reraise_control(exc)
                raise _failure("session_invalid_response", "session_fetch", _SESSION_URL, kind="invalid_response", hop=hop, attempt=attempt, response=response, exc=exc) from None
            try:
                result = _verify_session(info, email, hop=hop, attempt=attempt)
            except CallbackRecoveryError as exc:
                exc.diagnostics.update(http_status=status, response_observed=True)
                raise
            _check(checkpoint)
            return result
        except CallbackRecoveryError as exc:
            from core.network.at_transport_recovery import exhausted

            if exc.retryable and not exhausted(exc) and attempt == 0 and recovery.claim():
                logger.warning("[AT回调] Session 临时失败，沿用原会话重读一次 failure_kind=%s", exc.diagnostics["failure_kind"])
                attempt = 1
                continue
            raise
        finally:
            if response is not None:
                _close(response)


def complete_callback(session, continue_url: str, *, referer: str, email: str, checkpoint=None) -> dict:
    """逐跳完成 AT 回调；确认会话优先，整个链路最多恢复一次。"""
    current = _trusted_url(continue_url)
    recovery = _Recovery()
    for hop in range(1, 13):
        parsed = urlparse(current)
        # 回调已种 Cookie 后直接读取 Session，不下载应用首页正文。
        if parsed.hostname == "chatgpt.com" and parsed.path in {"", "/"}:
            return _read_session(session, email, recovery=recovery, hop=hop, checkpoint=checkpoint)
        attempt = 0
        while True:
            _check(checkpoint)
            response = None
            try:
                method = session.get_chatgpt_navigate_headers if parsed.hostname == "chatgpt.com" else session.get_auth_navigate_headers
                headers = method(referer=referer, user_initiated=False)
                target = _target(current)
                logger.info("[AT回调] 导航 hop=%s host=%s path=%s retry=%s", hop, target["target_host"], target["target_path"], attempt)
                try:
                    response = session.get(current, headers=headers, allow_redirects=False, stream=True)
                except Exception as exc:
                    _reraise_control(exc)
                    raise _failure("oauth_callback_failed", "oauth_callback", current, kind="transport_error", hop=hop, attempt=attempt, exc=exc) from None
                _check(checkpoint)
                status = _status(response)
                logger.info("[AT回调] 响应 hop=%s host=%s path=%s status=%s session_cookie=%s", hop, target["target_host"], target["target_path"], status, _has_session_cookie(session))
                if not status:
                    raise _failure("oauth_callback_failed", "oauth_callback", current, kind="invalid_response", hop=hop, attempt=attempt, response=response)
                if status not in _REDIRECTS and not 200 <= status < 300:
                    raise _failure("oauth_callback_failed", "oauth_callback", current, kind="http_error", hop=hop, attempt=attempt, response=response)
                location = ""
                if status in _REDIRECTS:
                    raw_headers = getattr(response, "headers", {}) or {}
                    location = str(next((value for key, value in raw_headers.items() if str(key).lower() == "location"), ""))
                    if not location:
                        raise _failure("auth_redirect_invalid", "oauth_callback", current, kind="redirect_invalid", hop=hop, attempt=attempt, response=response)
                    try:
                        location = _trusted_url(location, base=current)
                    except CallbackRecoveryError:
                        raise _failure("auth_redirect_invalid", "oauth_callback", current, kind="redirect_invalid", hop=hop, attempt=attempt, response=response) from None
                rejection = _callback_rejection(location or current)
                if rejection:
                    failure = _failure("oauth_callback_rejected", "oauth_callback", current, kind="rejected", hop=hop, attempt=attempt, response=response)
                    failure.diagnostics["auth_error"] = {"code": rejection}
                    logger.warning("[AT回调] 服务端返回明确错误跳转 code=%s，先核验当前 Session", rejection)
                    _close(response)
                    response = None
                    try:
                        return _read_session(session, email, recovery=recovery, hop=hop, checkpoint=checkpoint, probe=True)
                    except CallbackRecoveryError as probe:
                        logger.warning("[AT回调] 错误跳转后 Session 未确认 code=%s；保留回调拒绝 code=%s", probe.code, rejection)
                        raise failure from None
                is_callback = parsed.hostname == "chatgpt.com" and parsed.path == "/api/auth/callback/openai"
                if is_callback or status not in _REDIRECTS:
                    _close(response)
                    response = None
                    return _read_session(session, email, recovery=recovery, hop=hop, checkpoint=checkpoint)
                referer, current = current, location
                break
            except CallbackRecoveryError as failure:
                if failure.code != "oauth_callback_failed":
                    raise
                details = failure.diagnostics
                logger.warning(
                    "[AT回调] 导航失败 hop=%s host=%s path=%s failure_kind=%s exception_type=%s status=%s curl=%s retry=%s",
                    hop, details.get("target_host"), details.get("target_path"), details.get("failure_kind"),
                    details.get("exception_type", "-"), details.get("http_status", "-"),
                    details.get("curl_error_code", "-"), attempt,
                )
                if response is not None:
                    _close(response)
                    response = None
                # 403/429 的原始原因保留，不能通过清理熔断继续派发请求。
                if getattr(session, "blocked_until", 0.0) > time.time():
                    raise
                try:
                    return _read_session(session, email, recovery=recovery, hop=hop, checkpoint=checkpoint, probe=True)
                except CallbackRecoveryError as probe:
                    logger.warning(
                        "[AT回调] 当前 Session 未确认 code=%s failure_kind=%s status=%s curl=%s retry=%s",
                        probe.code, probe.diagnostics.get("failure_kind"), probe.diagnostics.get("http_status", "-"),
                        probe.diagnostics.get("curl_error_code", "-"), probe.diagnostics.get("retry_attempt", 0),
                    )
                    if probe.code == "session_fetch_failed":
                        # Session 无法读取时不能据此重放 code，也不能盖掉原始回调故障。
                        raise failure from None
                    if probe.code != "access_token_missing":
                        raise
                    # 已有 Session Cookie 时只核验，不重放可能已消费的 code。
                    if _has_session_cookie(session):
                        raise
                    from core.network.at_transport_recovery import current_scope, exhausted

                    if failure.retryable and not exhausted(failure) and attempt == 0 and recovery.claim():
                        scope = current_scope()
                        if scope is not None:
                            scope.check()
                            scope.same_route_retries += 1
                            scope.emit({"event": "same_route_retry", "operation": "oauth_callback", "retry_attempt": 1})
                        logger.warning("[AT回调] 当前 Session 尚未建立，沿用原会话恢复失败导航一次 hop=%s", hop)
                        attempt = 1
                        continue
                    raise failure from None
            finally:
                if response is not None:
                    _close(response)
    raise _failure("auth_redirect_limit", "oauth_callback", current, kind="redirect_limit", hop=12, attempt=0)
