"""仅供独立 AT 刷新的网络恢复作用域，普通认证入口保持原有行为。"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import socket
import ssl
import time
from urllib.parse import urlsplit


_SCOPE = ContextVar("at_transport_recovery", default=None)
_HTTP = frozenset({408, 500, 502, 503, 504, 520, 521, 522, 523, 524})
_CURL = frozenset({5, 6, 7, 16, 18, 28, 35, 52, 55, 56, 60, 92, 95, 97})
_HOSTS = frozenset({"auth.openai.com", "chatgpt.com", "chat.openai.com", "sentinel.openai.com"})
_TRANSPORT_TYPES = frozenset({
    "Timeout", "ReadTimeout", "ConnectTimeout", "TimeoutError", "SSLError", "SSLCertVerificationError",
    "ProxyError", "ConnectionError", "ConnectionResetError", "ConnectionAbortedError", "ConnectionRefusedError",
    "ProxyConnectionError", "BrokenPipeError", "CurlError", "RequestsError", "RequestException",
    "ChunkedEncodingError", "IncompleteRead", "gaierror",
})
_BUSINESS_CODES = frozenset({
    "password_rejected", "password_change_required", "password_page_error", "password_missing",
    "passwordless_fallback_unavailable", "password_login_unavailable",
    "mfa_rejected", "mfa_secret_missing", "mfa_secret_invalid", "mfa_factor_missing", "mfa_code_missing",
    "account_deactivated", "account_deleted", "account_banned", "account_profile_required", "profile_completion_required",
    "email_verification_required", "email_otp_no_mail", "email_otp_code_rejected", "email_otp_send_rejected",
    "email_otp_send_unconfirmed", "auth_route_rejected", "auth_cloudflare_challenge", "oauth_callback_rejected",
    "session_identity_mismatch", "access_token_expired", "workspace_missing", "workspace_ambiguous",
    "source_untrusted", "source_authentication_failed", "recipient_mismatch", "recipient_ambiguous",
    "recipient_evidence_missing", "recipient_contract_unsupported", "mailbox_mismatch", "inbound_code_timeout",
    "invalid_key", "service_not_authorized", "cancelled", "stopped", "refresh_cancelled",
    "session_invalid_response", "cached_session_invalid_response", "email_otp_validate_invalid_response",
    "password_verify_invalid_response", "mfa_verify_invalid_response", "auth_redirect_invalid", "auth_redirect_limit",
    "untrusted_auth_url", "auth_context_ambiguous", "roxy_profile_open_failed", "roxy_driver_attach_failed",
})
_NETWORK_WRAPPERS = frozenset({
    "protocol_v2_unknown_error", "protocol_v3_unknown_error", "network_preflight_failed", "protocol_network_error",
    "email_otp_failed", "email_otp_send_failed", "email_otp_validate_failed", "password_result_unknown",
    "password_sentinel_failed", "password_verify_failed", "mfa_issue_challenge_failed", "mfa_verify_failed",
    "oauth_callback_failed", "session_fetch_failed", "auth_navigation_failed", "cached_session_network_failed",
    "cached_session_http_failed",
    "refresh_driver_exception", "roxy_login_failed", "roxy_navigation_failed", "roxy_session_fetch_failed",
    "password_rejected_email_fallback_failed",
})


class AtRecoveryTimeout(TimeoutError):
    """独立 AT 恢复总预算耗尽，不作为线路故障再次重试。"""


def current_scope():
    return _SCOPE.get()


def _chain(error):
    pending, seen = [error], set()
    while pending and len(seen) < 16:
        item = pending.pop(0)
        if item is None or id(item) in seen:
            continue
        seen.add(id(item))
        yield item
        if isinstance(item, BaseException):
            pending.append(item.__cause__)
            if not item.__suppress_context__:
                pending.append(item.__context__)
            pending.append(getattr(item, "response", None))


def exhausted(error) -> bool:
    """沿原异常和响应寻找当前 AT 作用域的耗尽标记。"""
    scope = current_scope()
    return bool(scope and any(getattr(item, "_at_recovery_exhausted", None) is scope for item in _chain(error)))


def _mark(item, scope):
    try:
        item._at_recovery_exhausted = scope
    except Exception:
        pass


def _status(value):
    value = getattr(value, "status_code", None)
    return value if type(value) is int and 100 <= value <= 599 else None


def _curl_code(value):
    # curl_cffi 使用 IntEnum；只接受整数及其枚举子类，不接受 bool 或数字字符串。
    return int(value) if isinstance(value, int) and not isinstance(value, bool) and int(value) in _CURL else None


def _business_response(response) -> bool:
    if response is None:
        return False
    try:
        from core.network.response_diagnostics import auth_error_from_body
        error = auth_error_from_body(getattr(response, "text", ""))
        return bool(error and error.get("category") not in {None, "unknown"})
    except Exception:
        return False


def _transport_error(error) -> bool:
    if isinstance(error, (ConnectionError, TimeoutError, socket.gaierror, ssl.SSLError)):
        return True
    try:
        from requests import exceptions as requests_errors
        if isinstance(error, (requests_errors.ConnectionError, requests_errors.Timeout,
                              requests_errors.ChunkedEncodingError)):
            return True
    except ImportError:
        pass
    try:
        from curl_cffi.curl import CurlError
        if isinstance(error, CurlError):
            return _curl_code(getattr(error, "code", None)) is not None
    except ImportError:
        pass
    return False


def _control_failure(error) -> bool:
    from core.auth.state_machine import CancellationRequested, StageTimeout
    from core.operations.runtime import OperationCancelled, OperationAccountDeactivated
    from core.operations.task_gateway import OperationLeaseLost

    return isinstance(error, (AtRecoveryTimeout, StageTimeout, CancellationRequested, OperationCancelled,
                              OperationAccountDeactivated, OperationLeaseLost))


def network_failure(error=None, response=None) -> dict | None:
    """只接受真实传输异常和明确临时 HTTP 状态，不读取异常文案猜测网络故障。"""
    chain = []
    current = error
    while current is not None and len(chain) < 16 and not any(current is item for item in chain):
        chain.append(current)
        # 显式 cause 才属于当前请求；隐式 context 可能是触发重发的上一封无邮件异常。
        current = getattr(current, "__cause__", None)
    if any(_control_failure(item) for item in chain):
        return None
    error_code = getattr(error, "code", None) or getattr(error, "error_code", None)
    if isinstance(error_code, str) and error_code in _BUSINESS_CODES:
        return None
    # 收件服务不经过 OpenAI 代理，不能由它的超时、来源拒绝或读信错误触发换线。
    if any(type(item).__module__.startswith("core.email") for item in chain):
        return None
    response = response if response is not None else getattr(error, "response", None)
    status = _status(response)
    if status is not None:
        if status not in _HTTP or _business_response(response):
            return None
        return {"failure_kind": "http_error", "http_status": status, "response_observed": True}
    for item in chain:
        if isinstance(item, AtRecoveryTimeout):
            return None
        if isinstance(item, BaseException) and _transport_error(item):
            name = type(item).__name__
            result = {"failure_kind": "transport_error", "response_observed": False,
                      "exception_type": name if name in _TRANSPORT_TYPES else "RequestException"}
            code = _curl_code(getattr(item, "code", None))
            if code is not None:
                result["curl_error_code"] = code
            return result
    return None


@dataclass
class AtRecoveryScope:
    checkpoint: object = None
    on_event: object = None
    deadline: float | None = None
    last_failure: dict | None = None
    same_route_retries: int = 0
    _active_depth: int = field(default=0, init=False)
    _last_request_failed: bool = field(default=False, init=False)
    _last_request_business_error: bool = field(default=False, init=False)

    def __post_init__(self):
        self._last_request_failed = bool(self.last_failure and not self.last_failure.get("recovered"))

    @property
    def active(self):
        return current_scope() is self

    @property
    def pending_network_failure(self):
        """只返回最后实际请求尚未恢复的故障，历史失败事实仍保留在 last_failure。"""
        return dict(self.last_failure) if (
            self._last_request_failed and self.last_failure and not self.last_failure.get("recovered")
        ) else None

    def check(self):
        if callable(self.checkpoint):
            self.checkpoint()
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise AtRecoveryTimeout("AT 网络恢复总预算已耗尽")

    def remaining(self):
        self.check()
        return None if self.deadline is None else max(0.001, self.deadline - time.monotonic())

    def emit(self, event):
        if callable(self.on_event):
            self.on_event(dict(event))

    @contextmanager
    def suspend(self):
        """后置套餐等独立动作不继承 AT 的重试策略和总预算。"""
        marker = _SCOPE.set(None)
        try:
            yield
        finally:
            _SCOPE.reset(marker)

    @contextmanager
    def activate(self):
        marker = _SCOPE.set(self)
        self._active_depth += 1
        try:
            self.check()
            yield self
        finally:
            self._active_depth -= 1
            _SCOPE.reset(marker)


def _target(url):
    try:
        parsed = urlsplit(str(url))
        if parsed.hostname in _HOSTS and parsed.scheme == "https" and parsed.port in (None, 443):
            path = parsed.path or "/"
            fixed_paths = {
                "/", "/auth/login", "/login", "/log-in", "/log-in/password", "/email-verification", "/error",
                "/api/auth/session", "/api/auth/csrf", "/api/auth/providers", "/api/auth/signin/openai",
                "/api/auth/callback/openai", "/api/auth/error", "/api/accounts/authorize", "/api/accounts/password/verify",
                "/api/accounts/email-otp/send", "/api/accounts/email-otp/validate", "/api/accounts/mfa/challenge",
                "/api/accounts/mfa/verify", "/api/accounts/workspace/select", "/backend-api/sentinel/req",
            }
            safe_path = path if path in fixed_paths else "/mfa-challenge/<factor>" if path.startswith("/mfa-challenge/") else "/<auth-path>"
            operation = {
                "/api/accounts/password/verify": "password_verify", "/api/accounts/email-otp/send": "email_otp_send",
                "/api/accounts/email-otp/validate": "email_otp_validate", "/api/accounts/mfa/challenge": "mfa_issue_challenge",
                "/api/accounts/mfa/verify": "mfa_verify", "/api/accounts/workspace/select": "workspace_select",
                "/api/auth/callback/openai": "oauth_callback", "/api/auth/session": "session_fetch",
            }.get(path, "at_transport")
            return {"target_host": parsed.hostname, "target_path": safe_path, "operation": operation}
    except (ValueError, TypeError):
        pass
    return None


def _close(response):
    try:
        response.close()
    except Exception:
        pass


def recover_request(session, method: str, url: str, invoke):
    """同线路、同 Cookie、同请求最多恢复一次；回调 code 交给专用恢复器。"""
    scope = current_scope()
    target = _target(url)
    if scope is None or target is None:
        return invoke()
    oauth_callback = target["target_host"] == "chatgpt.com" and target["target_path"] == "/api/auth/callback/openai"
    for attempt in range(2):
        scope.check()
        response = None
        try:
            response = invoke()
        except BaseException as error:
            failure = network_failure(error=error)
            scope._last_request_business_error = failure is None and _business_response(getattr(error, "response", None))
            if failure is None:
                scope._last_request_failed = False
                raise
            details = {**failure, **target, "method": method.upper(), "same_route_retry_exhausted": attempt == 1,
                       "recovered": False}
            scope.last_failure = details
            scope._last_request_failed = True
            if attempt or oauth_callback:
                if not oauth_callback:
                    _mark(error, scope)
                raise
        else:
            failure = network_failure(response=response)
            scope._last_request_business_error = failure is None and _business_response(response)
            if failure is None:
                scope._last_request_failed = False
                if attempt and scope.last_failure is not None:
                    scope.last_failure = {**scope.last_failure, "recovered": True}
                return response
            details = {**failure, **target, "method": method.upper(), "same_route_retry_exhausted": attempt == 1,
                       "recovered": False}
            scope.last_failure = details
            scope._last_request_failed = True
            if attempt or oauth_callback:
                if not oauth_callback:
                    _mark(response, scope)
                return response
            _close(response)
        scope.check()
        scope.same_route_retries += 1
        scope.emit({**details, "event": "same_route_retry", "attempt": 1, "retry_attempt": 1})
        # 不得通过重建连接清除 403/429 的业务熔断。
        if not getattr(session, "blocked_until", 0) or getattr(session, "blocked_until", 0) <= time.time():
            reset = getattr(session, "reset_transport", None)
            if callable(reset) and failure["failure_kind"] == "transport_error":
                reset()


def result_network_failure(result) -> dict | None:
    """结果码仅辅助排除业务拒绝；换线必须有结构化网络证据。"""
    if not isinstance(result, dict) or result.get("ok"):
        return None
    codes = {str(result.get(key) or "") for key in ("error_code", "error", "status")}
    if codes & _BUSINESS_CODES or result.get("status") in {"deactivated", "cancelled", "stopped"}:
        return None
    diagnostics = result.get("auth_diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    from core.network.response_diagnostics import safe_auth_error

    if safe_auth_error(diagnostics.get("auth_error")).get("category") not in {None, "unknown"}:
        return None
    inner_code = diagnostics.get("cause_code")
    if isinstance(inner_code, str) and inner_code in _BUSINESS_CODES:
        return None
    scope = current_scope()
    # 驱动可能只保留 HTTP 状态而丢弃业务响应体，不能把已确认的业务拒绝重新解释成网络故障。
    if scope and scope._last_request_business_error:
        return None
    operation = diagnostics.get("cause_operation") or diagnostics.get("operation")
    kind = diagnostics.get("cause_failure_kind") or diagnostics.get("failure_kind")
    if (operation == "email_otp" or diagnostics.get("mailbox_error_code")
            or kind in {"no_mail", "mailbox_error", "imap_error", "manual_timeout", "invalid_code", "rejected"}):
        return None
    status = diagnostics.get("http_status", result.get("http_status"))
    if type(status) is int and status in {400, 401, 403, 409, 422, 429}:
        return None
    proven_operation = isinstance(operation, str) and operation in {
        "network_preflight", "password_sentinel", "password_verify", "email_otp_send", "email_otp_validate",
        "mfa_issue_challenge", "mfa_verify", "workspace_select", "oauth_callback", "session_fetch",
        "protocol_v2_auth", "protocol_v3_auth", "session_reuse", "roxy_navigation", "roxy_login",
        "roxy_email_otp", "roxy_session",
    }
    if type(status) is int and status in _HTTP and (codes & _NETWORK_WRAPPERS or kind == "http_error" and proven_operation):
        return {"failure_kind": "http_error", "http_status": status, "response_observed": True}
    if kind == "transport_error":
        name = diagnostics.get("transport_exception_type") or diagnostics.get("exception_type")
        code = _curl_code(diagnostics.get("curl_error_code"))
        if proven_operation and (isinstance(name, str) and name in _TRANSPORT_TYPES or code is not None):
            result = {"failure_kind": kind, "response_observed": False}
            if isinstance(name, str) and name in _TRANSPORT_TYPES:
                result["exception_type"] = name
            if code is not None:
                result["curl_error_code"] = code
            return result
        network_error = diagnostics.get("network_error") or result.get("network_error")
        browser_kind = {
            "ERR_CONNECTION_RESET": "connection", "ERR_CONNECTION_CLOSED": "connection",
            "ERR_CONNECTION_REFUSED": "connection", "ERR_CONNECTION_TIMED_OUT": "timeout",
            "ERR_TIMED_OUT": "timeout", "ERR_NAME_NOT_RESOLVED": "dns", "ERR_DNS_TIMED_OUT": "dns",
            "ERR_TUNNEL_CONNECTION_FAILED": "proxy", "ERR_PROXY_CONNECTION_FAILED": "proxy",
            "ERR_SSL_PROTOCOL_ERROR": "tls", "ERR_CERT_AUTHORITY_INVALID": "certificate",
            "ERR_CERT_DATE_INVALID": "certificate", "Failed to fetch": "connection",
            "ERR_HTTP2_PROTOCOL_ERROR": "connection", "ERR_HTTP2_PING_FAILED": "connection",
        }.get(network_error) if isinstance(network_error, str) else None
        if browser_kind:
            return {"failure_kind": kind, "network_error": network_error, "transport_kind": browser_kind,
                    "response_observed": False}
    if (scope and scope._last_request_failed and codes & _NETWORK_WRAPPERS
            and scope.last_failure and not scope.last_failure.get("recovered")):
        return dict(scope.last_failure)
    return None
