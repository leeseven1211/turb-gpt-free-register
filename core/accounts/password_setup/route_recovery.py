"""独立账号动作显式交接线路，保留认证栈并阻止未知写入重放。"""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from http.cookiejar import CookieJar
from urllib.parse import parse_qs, urlsplit

from curl_cffi.requests import Cookies, Session

from core.accounts.password_setup.proxy import is_proxy_transport_failure
from core.auth.state_machine import CancellationRequested
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost

_CONTROL = (CancellationRequested, OperationCancelled, OperationLeaseLost)
_CHATGPT = {
    ("GET", "/"): "home", ("GET", "/api/auth/session"): "session",
    ("GET", "/api/auth/csrf"): "csrf", ("POST", "/api/auth/signin/openai"): "signin",
    ("GET", "/api/auth/callback/openai"): "callback",
    ("POST", "/backend-api/accounts/mfa/enroll"): "mfa_enroll",
    ("POST", "/backend-api/accounts/mfa/activate"): "mfa_activate",
    ("POST", "/backend-api/accounts/mfa/user/activate_enrollment"): "mfa_activate",
}
_AUTH = {
    ("GET", "/authorize"): "authorize", ("GET", "/oauth/authorize"): "authorize",
    ("GET", "/api/accounts/authorize"): "authorize",
    ("GET", "/log-in"): "authorize", ("GET", "/email-verification"): "email_page",
    ("GET", "/authorize/continue"): "callback",
    ("GET", "/reset-password/new-password"): "password_page",
    ("GET", "/api/accounts/client_auth_session_dump"): "auth_session",
    ("POST", "/api/accounts/authorize/continue"): "authorize",
    ("POST", "/api/accounts/password/verify"): "password_verify",
    ("POST", "/api/accounts/password/add"): "password_add",
    ("POST", "/api/accounts/email-otp/validate"): "otp_verify",
    ("POST", "/api/accounts/email-otp/verify"): "otp_verify",
    ("POST", "/api/accounts/email-otp/resend"): "otp_send",
    ("POST", "/api/accounts/passwordless/send-otp"): "otp_send",
    ("GET", "/api/accounts/email-otp/send"): "otp_send",
    ("POST", "/api/accounts/email-otp/send"): "otp_send",
    ("POST", "/api/accounts/mfa/issue_challenge"): "mfa_challenge",
    ("POST", "/api/accounts/mfa/verify"): "mfa_verify",
}


@dataclass(frozen=True)
class AccountActionRouteFailure:
    operation: str
    method: str
    http_status: int | None = None
    transport_kind: str = ""
    request_unknown: bool = False
    proxy_fault: bool = False

    def public_dict(self) -> dict:
        return {
            "operation": self.operation, "http_method": self.method,
            "http_status": self.http_status, "transport_kind": self.transport_kind,
            "request_unknown": self.request_unknown,
        }


class AccountActionRouteError(RuntimeError):
    """安全的失败原因供独立动作边界转换，不包含请求内容或代理地址。"""

    def __init__(self, failure: AccountActionRouteFailure, *, code: str):
        reason = f"HTTP {failure.http_status}" if failure.http_status else failure.transport_kind
        super().__init__(f"{code}: 账号动作 {failure.operation} 线路恢复未完成（{reason}）")
        self.code = code
        self.failure = failure
        self.request_unknown = failure.request_unknown
        self.proxy_transport_failed = failure.proxy_fault


class AccountActionRouteHalt(BaseException):
    """穿过共享接口的宽泛有限重试，在独立动作边界收口同一次请求。"""

    def __init__(self, error: AccountActionRouteError):
        self.error = error
        super().__init__(str(error))


class AccountActionControlHalt(BaseException):
    """停止/租约信号穿过旧认证重试后，在独立动作边界恢复原异常。"""

    def __init__(self, reason: Exception):
        self.reason = reason
        super().__init__(str(reason))


def _is_control(error):
    return isinstance(error, _CONTROL) or type(error).__name__ in {
        "CodexRetryStopped", "StopRequested", "AuthCancelledError",
    }


def _operation(method, url):
    try:
        parsed = urlsplit(str(url))
        if (parsed.scheme != "https" or parsed.port not in (None, 443)
                or parsed.username or parsed.password):
            return None
    except (ValueError, TypeError):
        return None
    action = (method, parsed.path.rstrip("/") or "/")
    if parsed.hostname == "chatgpt.com":
        operation = _CHATGPT.get(action)
    elif parsed.hostname == "auth.openai.com":
        operation = _AUTH.get(action)
    elif parsed.hostname == "sentinel.openai.com" and action == ("POST", "/backend-api/sentinel/req"):
        operation = "sentinel"
    else:
        operation = None
    if operation and parse_qs(parsed.query).get("code"):
        return "callback"
    return operation


def _transport(error):
    name, message = type(error).__name__.lower(), str(error).lower()
    if is_proxy_transport_failure(error):
        return "proxy"
    if "timeout" in name or "timed out" in message or "curl: (28)" in message:
        return "timeout"
    if any(s in name or s in message for s in ("ssl", "tls", "curl: (35)")):
        return "tls"
    if any(s in name or s in message for s in ("gaierror", "resolve host", "curl: (6)")):
        return "dns"
    if any(s in name or s in message for s in ("connection", "brokenpipe", "connection reset", "unexpected eof")):
        return "connection"
    return ""


def _not_sent(error):
    """仅连接建立失败能证明 POST 尚未到达；普通读超时不能作此推断。"""
    message = str(error).lower()
    return any(marker in message for marker in (
        "proxy connect aborted", "connect tunnel failed", "could not resolve proxy",
        "failed to connect to proxy", "err_proxy_connection_failed", "err_tunnel_connection_failed",
        "could not resolve host", "failed to connect", "connection refused", "curl: (5)", "curl: (6)", "curl: (7)",
    ))


def _business_rejection(response):
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        code = error.get("code") if isinstance(error, dict) else error
    except Exception:
        return False
    return isinstance(code, str) and code in {
        "account_deactivated", "account_suspended", "account_deleted", "account_banned",
        "invalid_code", "wrong_email_otp",
        "invalid_otp", "password_already_exists", "password_already_set", "incorrect_password",
    }


class AccountActionSession:
    """显式包装一个动作会话；只有资源所有者的回调能提供已核验新线路。"""

    def __init__(self, session, *, recover, check, observe=None, signal_control=False):
        self._original = session
        self._recover = recover
        self._check = check
        self._observe = observe
        self._terminal = None
        self._signal_control = signal_control
        self.last_mfa_2xx = None

    def __getattr__(self, name):
        return getattr(self._original, name)

    def get(self, url, **kwargs):
        return self._request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, **kwargs)

    def _halt(self, failure, code):
        self._terminal = AccountActionRouteError(failure, code=code)
        raise AccountActionRouteHalt(self._terminal)

    def _call(self, callback, *args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except Exception as exc:
            if self._signal_control and _is_control(exc):
                raise AccountActionControlHalt(exc) from None
            raise

    def _request(self, method, url, **kwargs):
        while True:
            self._call(self._check)
            if self._terminal is not None:
                raise AccountActionRouteHalt(self._terminal)
            operation = _operation(method, url)
            # 只保留紧邻当前请求的成功状态元数据，后继请求一开始即清除，
            # 不保存正文、密钥或旧的 MFA 成功响应作本次失败证明。
            self.last_mfa_2xx = None
            response, error = None, None
            try:
                response = self._call(getattr(self._original, method.lower()), url, **kwargs)
            except _CONTROL:
                raise
            except Exception as exc:
                error = exc
            status = getattr(response, "status_code", None)
            transport = _transport(error) if error is not None else ""
            if operation in {"mfa_enroll", "mfa_activate"} and type(status) is int and 200 <= status < 300:
                self.last_mfa_2xx = AccountActionRouteFailure(
                    operation, method, http_status=status, request_unknown=True,
                )
            if operation and response is not None and type(status) is int:
                write = method != "GET" or operation in {"callback", "otp_send"}
                if write and (status == 408 or status >= 500):
                    failure = AccountActionRouteFailure(
                        operation, method, http_status=status, request_unknown=True,
                    )
                    if callable(self._observe):
                        self._call(self._observe, failure)
                    self._halt(failure, "account_action_request_unknown")
                if status in {425, 429}:
                    self._halt(
                        AccountActionRouteFailure(operation, method, http_status=status),
                        "account_action_rate_limited" if status == 429 else "account_action_http_rejected",
                    )
            if (not operation or response is not None and (status != 403 or _business_rejection(response))
                    or response is None and not transport):
                if error is not None:
                    raise error
                return response
            unknown = operation == "callback" or response is None and (
                operation == "otp_send" or method != "GET"
            ) and not _not_sent(error)
            failure = AccountActionRouteFailure(
                operation, method, http_status=status if type(status) is int else None,
                transport_kind=transport, request_unknown=unknown,
                proxy_fault=bool(error is not None and is_proxy_transport_failure(error)),
            )
            if callable(self._observe):
                self._call(self._observe, failure)
            if unknown:
                self._halt(failure, "account_action_request_unknown")
            # 保存完整 Cookie Jar，坏连接在释放租约之前关闭；只有新 transport
            # 的本地熔断状态归零，不触碰其它账号、会话或全局熔断。
            original = self._original
            old = original.session
            capture = getattr(original, "protocol_traffic", None)
            try:
                jar = CookieJar()
                for cookie in getattr(old.cookies, "jar", old.cookies):
                    jar.set_cookie(copy.copy(cookie))
                cookies = Cookies(jar) if hasattr(old.cookies, "jar") else jar
                if capture is not None:
                    self._call(capture.flush)
                self._call(old.close)
                if response is not None:
                    close = getattr(response, "close", None)
                    if callable(close):
                        self._call(close)
            except Exception as exc:
                if _is_control(exc):
                    raise
                self._halt(failure, "account_action_route_unavailable")
            self._call(self._check)
            try:
                proxy = self._call(self._recover, failure, original.proxy)
            except _CONTROL:
                raise
            except Exception as exc:
                if _is_control(exc):
                    raise
                self._halt(failure, "account_action_route_unavailable")
            if not proxy:
                self._halt(failure, "account_action_route_exhausted")
            self._call(self._check)
            replacement = None
            try:
                replacement = Session(impersonate=original.chrome_identity["impersonate"])
                replacement.proxies = {"http": proxy, "https": proxy}
                replacement.timeout = old.timeout
                replacement.cookies = cookies
            except Exception:
                if replacement is not None:
                    replacement.close()
                # 资源所有者已交付新线路；本地初始化失败不能再隔离它。
                # 原请求的类别仍保留作审计，代理故障只属于已归还的旧租约。
                self._halt(replace(failure, proxy_fault=False), "account_action_route_unavailable")
            original.session = replacement
            original.proxy = proxy
            original.blocked_until = 0.0
            original.blocked_reason = ""
            if capture is not None:
                from core.network.protocol_traffic import ProtocolTrafficCapture, current_correlation

                original.protocol_traffic = ProtocolTrafficCapture(current_correlation())
