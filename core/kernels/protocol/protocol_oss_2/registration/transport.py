"""Protocol-2 observed HTTP execution; lease and diagnostic sinks are injected."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

from core.network.response_diagnostics import auth_error_from_body, auth_submission_endpoint
from core.registration.route_recovery import registration_request_operation, registration_route_failure


@dataclass(frozen=True)
class ProtocolTransportCallbacks:
    check_stop: Callable[[], None]
    is_cancelled: Callable[[BaseException], bool]
    context_active: Callable[[], bool]
    current_route_recovery: Callable[..., Any]
    replace_route_capture: Callable[..., None]
    record_protocol_exchange: Callable[..., None]
    vendor_cancelled: type[BaseException]
    vendor_route_recovery: type[BaseException]
    perf_counter: Callable[[], float]


class HeaderOnlyResponse:
    """诊断流式导航时只观察响应头，不读取本来无需下载的正文。"""

    content = b""
    text = ""

    def __init__(self, response):
        self._response = response

    def __getattr__(self, name):
        return getattr(self._response, name)

    def json(self):
        return {}


class ObservedSession:
    """当前动作在业务统一预算内换线，保留会话与停止信号。"""

    def __init__(self, transport, context: dict, *, callbacks: ProtocolTransportCallbacks):
        self._callbacks = callbacks
        self._transport = transport
        self._context = context

    def __getattr__(self, name):
        return getattr(self._transport, name)

    def request(self, method, url, **kwargs):
        while True:
            response = None
            error = None
            try:
                response = self._request_once(method, url, **kwargs)
            except Exception as exc:
                if self._callbacks.is_cancelled(exc):
                    if self._callbacks.context_active():
                        raise self._callbacks.vendor_cancelled(exc) from exc
                    raise
                error = exc
            failure = registration_route_failure(method, url, response=response, error=error)
            context = self._context
            allowed = context.get("route_recovery_operations")
            enabled = context.get("route_recovery_enabled", True)
            callback = self._callbacks.current_route_recovery() if enabled else None
            if failure is None or (allowed is not None and failure.operation not in allowed) or callback is None:
                if error is not None:
                    raise error
                return response
            if response is not None:
                close = getattr(response, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
            try:
                pause = getattr(self._transport, "pause_for_route_recovery", None)
                if callable(pause):
                    pause()
            except Exception as exc:
                raise self._callbacks.vendor_route_recovery(
                    failure, error=exc, method=method, stage="close_previous_connection",
                ) from exc
            try:
                lease = callback(failure, context.get("proxy"))
            except Exception as exc:
                if self._callbacks.is_cancelled(exc):
                    raise self._callbacks.vendor_cancelled(exc) from exc
                raise self._callbacks.vendor_route_recovery(failure, error=exc, method=method) from exc
            if lease is None:
                raise self._callbacks.vendor_route_recovery(failure, error=error, method=method) from error
            try:
                self._replace_route(lease)
            except Exception as exc:
                raise self._callbacks.vendor_route_recovery(failure, error=exc, method=method) from exc
            if not failure.replay_safe:
                raise self._callbacks.vendor_route_recovery(failure, switched=True, error=error, method=method) from error

    def _replace_route(self, lease):
        """只替换连接和租约关联，Cookie Jar、画像和认证栈保持不变。"""
        context = self._context
        proxy = str(getattr(lease, "proxy_url", "") or "").strip()
        if not proxy:
            raise RuntimeError("换线未返回可用代理，已停止当前注册动作")
        capture = context.get("capture")
        correlation = dict(getattr(capture, "correlation", {}) or {})
        if capture is not None:
            capture.flush()
        self._transport.proxies = {"http": proxy, "https": proxy}
        context["proxy"] = proxy
        flow = context.get("flow")
        if flow is not None:
            flow.config.proxy = proxy
            flow._proxy_pool = [proxy]
            flow._proxy_idx = -1
        parent = context.get("parent_session")
        if parent is not None:
            parent.proxy = proxy
        self._callbacks.replace_route_capture(context, capture, lease, correlation)
        if parent is not None:
            parent.protocol_traffic = None if context.get("exclusive_traffic_capture") else context["capture"]

    def _request_once(self, method, url, **kwargs):
        self._callbacks.check_stop()
        context = self._context
        # 旧线路故障属于已保存的恢复审计，不能替代新请求的当前结果。
        context.pop("route_failure", None)
        context["last_request_operation"] = registration_request_operation(method, url)
        context["last_request_http_status"] = None
        context["request_sequence"] = context.get("request_sequence", 0) + 1
        path = urlsplit(url).path
        if path.endswith("/api/auth/session"):
            context["session_response_incomplete"] = False
        if method.upper() == "POST" and path.endswith("/create_account"):
            context["profile_started"] = True
        profile_submit = method.upper() == "POST" and auth_submission_endpoint(url) == "profile_submit"
        password_create = method.upper() == "POST" and path == "/api/accounts/user/register"
        otp_submit = context["last_request_operation"] == "otp_validate"
        if otp_submit:
            context.pop("otp_method_mismatch", None)
        if profile_submit:
            context.pop("profile_diagnostics", None)
        if password_create:
            context.pop("password_diagnostics", None)
        started = self._callbacks.perf_counter()
        response = None
        error = None
        try:
            response = self._transport.request(method, url, **kwargs)
            response._protocol2_streaming = bool(kwargs.get("stream"))
            status = getattr(response, "status_code", None)
            context["last_request_http_status"] = status if type(status) is int else None
            if otp_submit and status == 400 and not kwargs.get("stream"):
                try:
                    context["otp_method_mismatch"] = (
                        auth_error_from_body(response.text).get("code") == "identity_provider_mismatch"
                    )
                except Exception:
                    pass
            if password_create:
                try:
                    status = int(response.status_code)
                    if status != 200:
                        context["password_diagnostics"] = {
                            "operation": "password_submit", "http_status": status,
                            "auth_error": auth_error_from_body(response.text),
                        }
                except Exception:
                    pass
            if profile_submit and not kwargs.get("stream"):
                try:
                    status = int(response.status_code)
                    if 400 <= status <= 599:
                        context["profile_diagnostics"] = {
                            "operation": "profile_submit", "http_status": status,
                            "auth_error": auth_error_from_body(response.text),
                        }
                except Exception:
                    # 诊断提取失败不能覆盖远端响应或读取原始异常正文。
                    pass
            if path.endswith("/api/auth/session") and response.status_code == 200:
                try:
                    payload = response.json()
                except Exception:
                    payload = None
                if isinstance(payload, dict):
                    access_token = str(payload.get("accessToken") or payload.get("access_token") or "").strip()
                    user = payload.get("user")
                    actual_email = str(user.get("email") or "").strip().casefold() if isinstance(user, dict) else ""
                    expected = str(context.get("email") or "").strip().casefold()
                    if ((actual_email and expected and actual_email != expected)
                            or (payload.get("accessToken") and payload.get("access_token")
                                and payload["accessToken"] != payload["access_token"])):
                        context["session_identity_mismatch"] = True
                    if access_token and actual_email:
                        normalized = dict(payload, accessToken=access_token)
                        context["session_info"] = normalized
                    else:
                        # 后续空响应不能抹掉同一认证链已核验的完整 Session。
                        context["session_response_incomplete"] = True
                else:
                    context["session_response_incomplete"] = True
            return response
        except BaseException as exc:
            error = exc
            operation = registration_request_operation(method, url)
            if response is None and method.upper() == "POST" and operation in {
                "password_create", "password_verify", "profile_submit", "email_submit", "otp_validate", "otp_send",
            }:
                context["auth_write_unknown"] = True
            if response is None and operation in {"password_create", "profile_submit"}:
                context["write_unknown"] = True
                context.setdefault("unknown_identity_operations", set()).add(operation)
            raise
        finally:
            current_failure = registration_route_failure(method, url, response=response, error=error)
            if current_failure is not None:
                context["route_failure"] = current_failure
            diagnostics = context.get("registration_diagnostics")
            if diagnostics is not None:
                try:
                    diagnostics.observe_request(
                        method, url, response=response, error=error, stream=bool(kwargs.get("stream")),
                    )
                except Exception:
                    # 外围诊断失败不能改变原响应、异常或后续认证动作。
                    pass
            capture = context.get("capture")
            if context.get("observing", True):
                try:
                    observed = HeaderOnlyResponse(response) if response is not None and kwargs.get("stream") else response
                    if capture is not None:
                        capture.record(started_at=started, response=observed, error=error)
                    self._callbacks.record_protocol_exchange(
                        method=method, url=url, started_at=started,
                        request_headers=kwargs.get("headers"),
                        request_body=kwargs.get("json", kwargs.get("data")),
                        response=observed, error=error,
                    )
                except Exception:
                    # 诊断写入失败不得改变认证结果，也不输出私有响应。
                    pass

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)



def create_observed_http_session(
    *, context, create_transport, observed_factory, check_stop, **kwargs,
):
    """只为当前驱动创建 wreq，会话工厂不修改其他驱动或全局模块。"""
    if context is None:
        raise RuntimeError("开源protocol-2 缺少注册执行上下文")
    check_stop()
    if context.get("identity_recovery") and context["sessions"]:
        # 原身份恢复只允许沿用当前认证现场，不能重建空会话或更换画像。
        return context["sessions"][-1]
    kwargs["proxy"] = context["proxy"]
    transport = observed_factory(create_transport(**kwargs), context)
    if context["sessions"]:
        # 上游换指纹或预热重建会话后，旧认证链的密码接收/校验不能用于新 Token。
        context["password_register_accepted"] = False
        context["password_verified"] = False
        context["session_info"] = {}
        context.pop("session_identity_mismatch", None)
    context["sessions"].append(transport)
    return transport
