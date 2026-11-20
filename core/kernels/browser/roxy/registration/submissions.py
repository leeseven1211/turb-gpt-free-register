"""Pair Roxy registration network events with the current submission receipt."""
from dataclasses import dataclass
import math
import re
from typing import Any, Callable

from core.auth.browser.password_auth import ProfileAccountAlreadyExistsError


@dataclass(frozen=True)
class SubmissionCallbacks:
    record_submission: Callable[..., Any]
    accepts_endpoint: Callable[..., bool]
    unique_receipt: Callable[..., Any]
    response_fact: Callable[..., tuple[str, str]]
    wall_time: Callable[[], float]


def make_submission_observer(driver, *, monitor_otp_network: bool = False, callbacks: SubmissionCallbacks):
    """为当前浏览器连接配对请求与响应，不发起任何认证请求。"""
    submission_requests = {}
    otp_target = ""
    if monitor_otp_network:
        try:
            handle = driver.current_window_handle
            target = handle.removeprefix("CDwindow-") if isinstance(handle, str) else ""
            if re.fullmatch(r"[A-Za-z0-9_-]{1,160}", target):
                otp_target = target
        except Exception:
            pass

    def observe(meta):
        request_key = (
            str(meta.get("target_id") or ""),
            str(meta.get("request_id") or ""),
        )
        endpoint_kind = str(meta.get("endpoint_kind") or "")
        if endpoint_kind == "password_submit" and meta.get("http_method") != "POST":
            return
        if (monitor_otp_network and endpoint_kind == "otp_submit"
                and (not otp_target or request_key[0] != otp_target)):
            return
        # 没有 CDP requestId 时无法把 response 与同端点提交绑定。
        if not request_key[1]:
            return
        if meta.get("response"):
            receipt = submission_requests.get(request_key)
            if receipt is None:
                # 响应必须沿用请求时已绑定的回执，不重选当前提交或处理重复响应。
                return
            if receipt.endpoint_kind == "profile_submit" and endpoint_kind != "profile_submit":
                return
            if receipt.endpoint_kind == "password_submit" and (
                    endpoint_kind != "password_submit" or receipt.request_binding != request_key):
                return
            if receipt.endpoint_kind == "otp_resend" and (
                    endpoint_kind != "otp_resend" or receipt.request_binding != request_key):
                return
            if monitor_otp_network and receipt.endpoint_kind == "otp_submit" and endpoint_kind != "otp_submit":
                return
            if (monitor_otp_network and receipt.endpoint_kind == "otp_submit"
                    and receipt.request_binding != request_key):
                # 已观察到新的当前请求；旧响应不能给它写拒绝或成功事实。
                submission_requests.pop(request_key, None)
                return
            submission_requests.pop(request_key, None)
        else:
            if endpoint_kind == "otp_resend":
                history = getattr(driver, "_browser_submission_receipts", None)
                if any(callbacks.accepts_endpoint(item, endpoint_kind)
                       and getattr(item, "request_binding", None) == request_key
                       for item in (history if isinstance(history, list) else ())):
                    # 已绑定旧请求的重复事件不能冒充下一次独立重发。
                    return
            receipt = callbacks.unique_receipt(driver, endpoint_kind)
            if receipt is None:
                return
            if endpoint_kind in {"otp_resend", "password_submit"} and (
                    not receipt.dispatch_target_id or receipt.dispatch_target_id != request_key[0]):
                return
            if endpoint_kind == "password_submit":
                # CDP 回调可能排队到下一次动作之后；只用真实请求 wallTime
                # 与本机派发 wall clock 比较，不混用 Chrome 和 Python 的 monotonic。
                started, dispatched = meta.get("started_wall_time"), receipt.dispatch_wall_time
                if not (type(started) in {int, float} and math.isfinite(started)
                        and type(dispatched) in {int, float} and math.isfinite(dispatched)
                        and 0 < dispatched <= started <= callbacks.wall_time() + 1.0):
                    return
            if endpoint_kind in {"profile_submit", "otp_resend", "password_submit", "email_submit", "nextauth_signin"}:
                # 一个资料、密码或重发动作只接一个请求；迟到请求不能替换已绑定动作。
                if receipt.request_binding not in (None, request_key):
                    return
                receipt.request_binding = request_key
            elif monitor_otp_network and endpoint_kind == "otp_submit":
                # 当前验证码请求更新后，旧响应不再解释当前表单的拒绝原因。
                receipt.request_binding = request_key
                receipt.response_binding = None
                receipt.auth_error = {}
                receipt._otp_network_request_unknown = True
                receipt._otp_network_http_status = None
            submission_requests[request_key] = receipt
        if (meta.get("response") and (endpoint_kind in {
                "profile_submit", "password_submit", "email_submit", "nextauth_signin",
        } or (
                monitor_otp_network and endpoint_kind == "otp_submit"
                and receipt.endpoint_kind == "otp_submit" and receipt.request_binding == request_key))):
            from core.network.response_diagnostics import safe_auth_error

            receipt.response_binding = request_key
            receipt.auth_error = safe_auth_error(meta.get("auth_error"))
            if monitor_otp_network and endpoint_kind == "otp_submit":
                receipt._otp_network_http_status = meta.get("http_status")
                status = receipt._otp_network_http_status
                # 页面成功可能先于响应正文到达；迟到响应不能重开已收口的未知标记。
                receipt._otp_network_request_unknown = receipt._otp_network_request_unknown is True and not (
                    isinstance(status, int) and 400 <= status < 500
                    and receipt.auth_error.get("code") == "wrong_email_otp_code"
                )
        phase, response_result = callbacks.response_fact(endpoint_kind, meta.get("http_status"))
        if (meta.get("response") and endpoint_kind == "otp_resend"
                and receipt.endpoint_kind == "otp_resend" and receipt.request_binding == request_key
                and meta.get("otp_resend_success") is True
                and type(meta.get("http_status")) in {int, float} and 200 <= meta["http_status"] < 300):
            # 仅确认当前配对重发响应的明确业务成功，不根据后续 OTP accepted
            # 推测其他旧提交的结果，也不放宽任何 dispatch 围栏。
            receipt.response_binding = request_key
            phase, response_result = "confirmed", "success"
        error_type = ""
        if (endpoint_kind == "profile_submit" and meta.get("response")
                and meta.get("http_status") == 400
                and receipt.auth_error.get("code") == "user_already_exists"):
            # 同一 phase 的事实只保存一次，首次拒绝落库时就写入精确安全枚举。
            error_type = ProfileAccountAlreadyExistsError.error_type
        if not meta.get("response"):
            phase, response_result = "request_observed", ""
        callbacks.record_submission(
            driver, phase, receipt=receipt,
            endpoint_kind=endpoint_kind,
            http_method=meta.get("http_method"),
            http_status=meta.get("http_status"),
            duration_ms=meta.get("duration_ms"),
            result=response_result,
            **({"error_type": error_type} if error_type else {}),
        )
        if (meta.get("response") and endpoint_kind == "password_submit"
                and receipt.request_binding == receipt.response_binding == request_key):
            # DOM 确认可能早于 CDP 正文；只合并已配对的安全元数据，绝不回退已收口阶段。
            safe = receipt.safe_fact(http_method=meta.get("http_method"), http_status=meta.get("http_status"))
            if safe["http_status"] is not None:
                receipt.http_status = safe["http_status"]
            if safe["http_method"]:
                receipt.http_method = safe["http_method"]

    return observe
