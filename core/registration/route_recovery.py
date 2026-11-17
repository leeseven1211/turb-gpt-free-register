"""注册当前动作的线路事实与作用域；供应商和日志不参与业务许可。"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
import time
from typing import Callable
from urllib.parse import urlsplit


@dataclass(frozen=True)
class RegistrationRouteFailure:
    operation: str
    http_status: int | None = None
    transport_kind: str = ""
    response_received: bool = False
    replay_safe: bool = False

    @property
    def is_transport(self) -> bool:
        return bool(self.transport_kind)


_RECOVERY: ContextVar[Callable | None] = ContextVar("registration_route_recovery", default=None)
_MANAGED_LEASE: ContextVar[object | None] = ContextVar("registration_managed_lease", default=None)


@dataclass
class ManagedRegistrationProxy:
    lease: object | None
    fault: bool = False


def current_route_recovery() -> Callable | None:
    return _RECOVERY.get()


def current_managed_registration_lease():
    owner = _MANAGED_LEASE.get()
    return owner.lease if isinstance(owner, ManagedRegistrationProxy) else None


def current_managed_registration_owner() -> ManagedRegistrationProxy | None:
    return _MANAGED_LEASE.get()


@contextmanager
def managed_registration_proxy(lease):
    """仅资源所有者声明受管线路，显式外部 proxy 不会被暗中替换。"""
    owner = ManagedRegistrationProxy(lease)
    token = _MANAGED_LEASE.set(owner)
    try:
        yield owner
    finally:
        _MANAGED_LEASE.reset(token)


@contextmanager
def registration_route_recovery(callback: Callable | None):
    token = _RECOVERY.set(callback)
    try:
        yield
    finally:
        _RECOVERY.reset(token)


class RegistrationRouteCoordinator:
    """同一次业务执行共用额度；驱动提供当前故障，资源选择不看供应商。"""

    def __init__(
        self, lease, *, limit: int, delay: float, acquire: Callable,
        release: Callable, check_stop: Callable, begin_route: Callable,
        on_lease: Callable | None = None,
    ):
        self.lease = lease
        self.limit = max(0, int(limit))
        self.delay = max(0.0, float(delay))
        self.used = 0
        self.acquire = acquire
        self.release = release
        self.check_stop = check_stop
        self.begin_route = begin_route
        self.on_lease = on_lease
        self.last_failure: RegistrationRouteFailure | None = None
        self.last_failure_proxy = ""

    @property
    def current_lease_transport_failure(self) -> bool:
        return bool(
            self.lease is not None and self.last_failure is not None
            and self.last_failure.is_transport and self.last_failure_proxy == str(self.lease.proxy_url or "")
        )

    def observe_result(self, result: object) -> None:
        """耗尽时驱动不再切线，但仍保留实际使用当前租约的故障事实。"""
        if not isinstance(result, dict) or result.get("current_lease_route_verified") is not True:
            return
        failure = result_route_failure(result)
        if failure is not None and self.lease is not None:
            self.last_failure = failure
            self.last_failure_proxy = str(self.lease.proxy_url or "")

    def __call__(self, failure: RegistrationRouteFailure, proxy_url: str):
        if (not isinstance(failure, RegistrationRouteFailure) or self.lease is None
                or str(self.lease.proxy_url or "") != str(proxy_url or "")):
            return None
        self.last_failure = failure
        self.last_failure_proxy = str(proxy_url or "")
        if self.used >= self.limit:
            return None
        self.check_stop()
        old = self.lease
        old_ip = str(old.exit_ip or "").strip()
        if not old_ip:
            raise RuntimeError("registration_route_exit_unknown: 原出口未知，无法确认新出口差异")
        reason = (
            f"{failure.operation} HTTP {failure.http_status}"
            if failure.response_received else f"{failure.operation} {failure.transport_kind} 传输失败"
        )
        self.used += 1
        self.release(old, reason=reason, fault=failure.is_transport)
        self.lease = None
        route_no = self.begin_route(reason)
        if self.delay:
            time.sleep(self.delay)
        self.check_stop()
        new = self.acquire(excluded_exit_ip=old_ip, route_attempt_no=route_no)
        try:
            self.check_stop()
            new_ip = str(new.exit_ip or "").strip()
            if not new_ip or new_ip == old_ip:
                raise RuntimeError("registration_route_exit_unverified: 换线未取得可核验的新出口")
            if str(new.region or "").upper() != str(old.region or "").upper():
                raise RuntimeError("registration_route_country_mismatch: 新线路国家与原线路不一致")
            self.lease = new
            self.last_failure = None
            self.last_failure_proxy = ""
            if self.on_lease is not None:
                self.on_lease(new, route_no)
            return new
        except BaseException:
            self.lease = None
            self.release(new, reason="registration_route_not_delivered", fault=False)
            raise


def registration_request_operation(method: str, url: object) -> str | None:
    """只分类注册关键端点，不让邮箱/供应商/静态资源触发线路恢复。"""
    try:
        parsed = urlsplit(str(url or ""))
        if (parsed.scheme != "https" or parsed.port not in (None, 443)
                or parsed.username or parsed.password):
            return None
    except (ValueError, TypeError):
        return None
    action = (str(method).upper(), parsed.path)
    if parsed.hostname in {"chatgpt.com", "chat.openai.com"}:
        if action == ("GET", "/api/auth/session"):
            return "session"
        if action in {
            ("GET", "/api/auth/callback/openai"), ("GET", "/api/auth/callback/auth0"),
        }:
            return "callback"
        if action in {
            ("GET", "/"), ("GET", "/api/auth/csrf"), ("GET", "/auth/login"),
            ("GET", "/auth/login_with"), ("POST", "/api/auth/signin/openai"),
            ("POST", "/api/auth/signin/auth0"),
        }:
            return "preauth"
        return {
            ("POST", "/backend-api/accounts/mfa/enroll"): "twofa_enroll",
            ("POST", "/backend-api/accounts/mfa/activate"): "twofa_activate",
            ("POST", "/backend-api/accounts/mfa/user/activate_enrollment"): "twofa_activate",
        }.get(action)
    if parsed.hostname == "sentinel.openai.com":
        return "preauth" if action == ("POST", "/backend-api/sentinel/req") else None
    if parsed.hostname != "auth.openai.com":
        return None
    return {
        ("GET", "/authorize"): "preauth",
        ("GET", "/api/accounts/authorize"): "preauth",
        ("GET", "/oauth/authorize"): "preauth",
        ("GET", "/log-in"): "preauth",
        ("GET", "/log-in/password"): "preauth",
        ("GET", "/create-account/password"): "preauth",
        ("POST", "/api/accounts/authorize"): "email_submit",
        ("POST", "/api/accounts/authorize/continue"): "email_submit",
        ("POST", "/api/accounts/user/register"): "password_create",
        ("POST", "/api/accounts/password/verify"): "password_verify",
        ("POST", "/api/accounts/email-otp/validate"): "otp_validate",
        ("POST", "/api/accounts/email-otp/verify"): "otp_validate",
        ("GET", "/api/accounts/email-otp/send"): "otp_send",
        ("POST", "/api/accounts/email-otp/send"): "otp_send",
        ("POST", "/api/accounts/email-otp/resend"): "otp_send",
        ("POST", "/api/accounts/passwordless/send-otp"): "otp_send",
        ("POST", "/api/accounts/create_account"): "profile_submit",
        ("GET", "/api/accounts/client_auth_session_dump"): "auth_session",
    }.get(action)


def registration_request_diagnostics(method: str, url: object) -> dict[str, str]:
    """仅输出稳定请求分类，未知域名、路径及查询参数不进入诊断。"""
    normalized_method = str(method or "").upper()
    if normalized_method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        normalized_method = "OTHER"
    host_class = "invalid"
    path_class = "invalid"
    try:
        parsed = urlsplit(str(url or ""))
        if (parsed.scheme == "https" and parsed.hostname and parsed.port in (None, 443)
                and not parsed.username and not parsed.password):
            host_class = {
                "auth.openai.com": "auth",
                "chatgpt.com": "chatgpt",
                "chat.openai.com": "chatgpt",
                "sentinel.openai.com": "sentinel",
            }.get(parsed.hostname, "other")
            path_class = registration_request_operation(normalized_method, url) or "unmapped"
    except (ValueError, TypeError):
        pass
    return {
        "request_method": normalized_method,
        "request_host_class": host_class,
        "request_path_class": path_class,
    }


def safe_registration_recovery_audit(value) -> list[dict]:
    """恢复历史只保留受控诊断与已验证的线路事实。"""
    from core.operations.errors import safe_registration_diagnostics

    result = []
    for item in value[-4:] if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        entry = {}
        diagnostics = safe_registration_diagnostics(item.get("registration_diagnostics"))
        if diagnostics:
            entry["registration_diagnostics"] = diagnostics
        raw_failure = item.get("route_failure")
        if isinstance(raw_failure, RegistrationRouteFailure):
            raw_failure = asdict(raw_failure)
        failure = result_route_failure({"route_failure": raw_failure})
        if failure is not None:
            entry["route_failure"] = asdict(failure)
        if entry:
            result.append(entry)
    return result


def _transport_kind(error: BaseException | None) -> str:
    """异常类型优先；兼容旧驱动只提供的固定网络错误标记。"""
    seen: set[int] = set()
    current = error
    chain = []
    while isinstance(current, BaseException) and id(current) not in seen and len(seen) < 8:
        seen.add(id(current))
        if type(current).__name__ in {
            "StageTimeout", "CancellationRequested", "OperationCancelled", "OperationAccountDeactivated",
            "OperationLeaseLost", "StopRequested", "AuthCancelledError",
        }:
            return ""
        chain.append(current)
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    for current in chain:
        name = type(current).__name__.lower()
        text = str(current).lower()
        if "timeout" in name or "timed out" in text or any(marker in text for marker in (
            "err_timed_out", "err_connection_timed_out",
        )):
            return "timeout"
        if any(marker in name for marker in ("proxy", "tunnel")) or any(marker in text for marker in (
            "err_proxy_connection_failed", "err_tunnel_connection_failed", "proxy connection",
        )):
            return "proxy"
        if any(marker in name for marker in ("ssl", "tls")) or any(marker in text for marker in (
            "ssl handshake", "tls handshake", "err_ssl_protocol_error", "err_cert_authority_invalid",
            "err_cert_date_invalid", "err_ssl_version_or_cipher_mismatch",
        )):
            return "tls"
        if any(marker in name for marker in ("gaierror", "dnserror")) or "err_name_not_resolved" in text:
            return "dns"
        if any(marker in name for marker in ("connection", "brokenpipe")) or any(marker in text for marker in (
            "err_connection_reset", "err_connection_closed", "connection aborted", "unexpected eof",
            "err_connection_refused", "err_http2_ping_failed", "err_http2_protocol_error", "failed to fetch",
        )):
            return "connection"
    return ""


def registration_route_failure(
    method: str, url: object, *, response=None, error: BaseException | None = None,
) -> RegistrationRouteFailure | None:
    operation = registration_request_operation(method, url)
    if operation is None:
        return None
    raw_status = getattr(response, "status_code", None)
    status = raw_status if type(raw_status) is int else None
    if response is not None:
        if status != 403:
            return None
        return RegistrationRouteFailure(
            operation=operation, http_status=403, response_received=True,
            replay_safe=operation != "callback",
        )
    transport = _transport_kind(error)
    if not transport:
        return None
    return RegistrationRouteFailure(
        operation=operation, transport_kind=transport,
        replay_safe=operation in {"preauth", "session", "auth_session"},
    )


def result_route_failure(result: object) -> RegistrationRouteFailure | None:
    """兼容单线路驱动结果；只消费本次结构化原因，不扫描历史错误文本。"""
    if (not isinstance(result, dict) or result.get("success")
            or result.get("route_recovery_blocked") is True
            or result.get("cause_code") == "registration_route_close_failed"):
        return None
    direct = result.get("route_failure")
    if isinstance(direct, RegistrationRouteFailure):
        return direct
    if isinstance(direct, dict):
        operations = {
            "preauth", "email_submit", "password_create", "password_verify", "otp_send", "otp_validate",
            "profile_submit", "callback", "session", "auth_session", "twofa_enroll", "twofa_activate",
        }
        operation = direct.get("operation")
        transport = direct.get("transport_kind")
        response_received = direct.get("response_received")
        status = direct.get("http_status")
        if (operation in operations and type(response_received) is bool
                and type(direct.get("replay_safe")) is bool
                and ((response_received and type(status) is int and status == 403 and transport == "")
                     or (not response_received and status is None
                         and transport in {"proxy", "connection", "tls", "dns", "timeout"}))):
            return RegistrationRouteFailure(
                operation=operation, http_status=status, transport_kind=transport,
                response_received=response_received, replay_safe=direct["replay_safe"],
            )
    diagnostic = result.get("registration_diagnostics")
    if not isinstance(diagnostic, dict):
        return None
    operation = diagnostic.get("operation")
    if operation not in {
        "preauth", "email_submit", "password_submit", "otp_send", "otp_validate",
        "profile_submit", "callback", "session", "auth_session",
    }:
        return None
    if type(diagnostic.get("http_status")) is int and diagnostic["http_status"] == 403:
        return RegistrationRouteFailure(
            operation=operation, http_status=403, response_received=True,
            replay_safe=operation != "callback",
        )
    if diagnostic.get("failure_kind") != "transport_error":
        return None
    kind = ""
    for name in [diagnostic.get("exception_type"), *(diagnostic.get("exception_chain") or [])]:
        if not isinstance(name, str):
            continue
        if name in {"Timeout", "TimeoutError", "ReadTimeout", "ConnectTimeout"}:
            kind = "timeout"
        elif name in {"ProxyError", "ProxyConnectionError"}:
            kind = "proxy"
        elif name in {"SSLError", "TlsError"}:
            kind = "tls"
        elif name in {"ConnectionError", "ConnectionResetError", "ConnectionAbortedError", "BrokenPipeError"}:
            kind = "connection"
        if kind:
            break
    return RegistrationRouteFailure(
        operation=operation, transport_kind=kind, replay_safe=operation in {"preauth", "session", "auth_session"},
    ) if kind else None
