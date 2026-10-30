"""注册外围的安全失败事实；不参与请求、认证分支或重试决策。"""
from __future__ import annotations

from urllib.parse import urlsplit

from core.network.response_diagnostics import auth_error_from_body


_EXCEPTION_TYPES = frozenset({
    "Exception", "RuntimeError", "ValueError", "TypeError", "KeyError", "AttributeError",
    "OSError", "TimeoutError", "ConnectionError", "ConnectionResetError", "ConnectionAbortedError",
    "ConnectionRefusedError", "BrokenPipeError", "HTTPError", "RequestException", "Timeout",
    "ConnectTimeout", "ReadTimeout", "ProxyError", "SSLError", "TlsError", "ProxyConnectionError",
    "JSONDecodeError", "ProtocolOssRequestUnknown", "ModuleNotFoundError", "ImportError",
})
_STAGES = frozenset({
    "browser", "submit_email", "auth_redirect", "password", "login_password", "email_otp", "profile", "token",
})


def _exception_chain(error: BaseException) -> list[BaseException]:
    chain = []
    while isinstance(error, BaseException) and len(chain) < 8 and not any(error is item for item in chain):
        chain.append(error)
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return chain


def _exception_type(error: BaseException) -> str:
    name = type(error).__name__
    return name if name in _EXCEPTION_TYPES else "Exception"


def _operation(method: str, url: object) -> str:
    """URL 只用于匹配固定类别；地址、参数和凭据均不进入诊断。"""
    try:
        parsed = urlsplit(str(url or ""))
        if (parsed.scheme != "https" or parsed.port not in (None, 443)
                or parsed.username or parsed.password):
            return "other"
        route = (str(method).upper(), parsed.path)
        if parsed.hostname in {"chatgpt.com", "chat.openai.com"}:
            if route == ("GET", "/api/auth/session"):
                return "session"
            if route in {("GET", "/api/auth/callback/openai"), ("GET", "/api/auth/callback/auth0")}:
                return "callback"
            if route in {
                ("GET", "/"), ("GET", "/api/auth/csrf"), ("GET", "/auth/login"),
                ("GET", "/auth/login_with"), ("POST", "/api/auth/signin/openai"),
                ("POST", "/api/auth/signin/auth0"),
            }:
                return "preauth"
        if parsed.hostname == "sentinel.openai.com" and route == ("POST", "/backend-api/sentinel/req"):
            return "preauth"
        if parsed.hostname != "auth.openai.com":
            return "other"
        return {
            ("POST", "/api/accounts/authorize"): "email_submit",
            ("POST", "/api/accounts/authorize/continue"): "email_submit",
            ("POST", "/api/accounts/user/register"): "password_submit",
            ("POST", "/api/accounts/password/verify"): "password_submit",
            ("POST", "/api/accounts/email-otp/validate"): "otp_validate",
            ("POST", "/api/accounts/email-otp/verify"): "otp_validate",
            ("GET", "/api/accounts/email-otp/send"): "otp_send",
            ("POST", "/api/accounts/email-otp/send"): "otp_send",
            ("POST", "/api/accounts/email-otp/resend"): "otp_send",
            ("POST", "/api/accounts/passwordless/send-otp"): "otp_send",
            ("POST", "/api/accounts/create_account"): "profile_submit",
            ("GET", "/api/accounts/client_auth_session_dump"): "auth_session",
            ("GET", "/authorize"): "preauth",
            ("GET", "/log-in"): "preauth",
            ("GET", "/create-account/password"): "preauth",
        }.get(route, "other")
    except (TypeError, ValueError):
        return "other"


class RegistrationFailureDiagnostics:
    """在当前执行内关联请求异常对象，只导出固定字段和枚举。"""

    def __init__(self):
        self.stage = "browser"
        self.last_confirmed_stage = ""
        self.otp_received = False
        self.profile_confirmed = False
        self.sequence = 0
        self._response_count = 0
        self._events: list[tuple[int, dict, BaseException | None]] = []
        self._bound: list[tuple[BaseException, dict]] = []

    def progress(self, stage: str, state: str) -> None:
        if stage not in _STAGES:
            return
        self.stage = stage
        if state == "success":
            self.last_confirmed_stage = stage
        if stage == "profile" and state == "success":
            self.profile_confirmed = True

    def received_otp(self) -> None:
        self.otp_received = True

    def observe_request(self, method: str, url: object, *, response=None, error=None, stream=False) -> None:
        operation = _operation(method, url)
        status = getattr(response, "status_code", None) if response is not None else None
        status = status if type(status) is int and 100 <= status <= 599 else None
        auth_error = {}
        if not stream and operation not in {"other", "preauth", "callback", "session"} and status is not None and status >= 400:
            try:
                auth_error = auth_error_from_body(response.text)
            except Exception:
                # 正文不可读时仍保留已确认的端点类别与状态码。
                pass
        data = {
            "operation": operation, "http_status": status, "auth_error": auth_error,
            "failure_kind": "transport_error" if error is not None else "http_error" if status is not None and status >= 400 else "unknown",
        }
        self.sequence += 1
        if status is not None:
            self._response_count += 1
        self._events.append((self.sequence, data, error))
        self._events = self._events[-16:]

    def bind_failure(self, error: BaseException, operation: str, since: int | None) -> None:
        """只有原动作实际抛出的同一异常才能关联该动作的最后错误响应。"""
        data = {"operation": operation, "http_status": None, "auth_error": {}, "failure_kind": "unknown"}
        if self._events:
            sequence, observed, request_error = self._events[-1]
            if since is not None and sequence > since and observed["operation"] == operation and (
                request_error is not None or observed["failure_kind"] == "http_error"
            ):
                data = dict(observed)
        self._bound.append((error, data))
        self._bound = self._bound[-8:]

    def failure(self, error: BaseException) -> dict:
        chain = _exception_chain(error)
        selected = None
        fallback = None
        for cause in chain:
            selected = next((data for _, data, observed in reversed(self._events) if observed is cause), None)
            if selected is not None:
                break
            bound = next((data for observed, data in reversed(self._bound) if observed is cause), None)
            if bound is not None:
                if bound["failure_kind"] != "unknown":
                    selected = bound
                    break
                if fallback is None:
                    fallback = bound
        if selected is None:
            # 预认证可能把网络异常吞掉后返回 False；全程没有任何 HTTP 响应才
            # 能把这类最终失败归为传输，不能拿早期拒绝或瞬时错误代替最终原因。
            only_transport = self._events and self._response_count == 0 and all(row[2] is not None for row in self._events)
            selected = dict(self._events[-1][1]) if only_transport else fallback or {
                "operation": "session" if self.profile_confirmed else "other",
                "http_status": None, "auth_error": {},
                "failure_kind": "missing_session" if self.profile_confirmed else "unknown",
            }
        return {
            **selected,
            "exception_type": _exception_type(error),
            "exception_chain": [_exception_type(cause) for cause in chain],
            "failure_stage": self.stage, "last_confirmed_stage": self.last_confirmed_stage,
            "otp_received": self.otp_received, "profile_confirmed": self.profile_confirmed,
        }
