"""Codex 手机验证的错误证据与换号判定，不发起请求或修改业务状态。"""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from core.operations.run_log import redact_text

PHONE_FAILURE_CAUSE = "codex_phone_verification_failed"
_OPERATIONS = {
    "phone_send": ("SEND", "手机验证码发送"),
    "phone_validate": ("VALIDATE", "手机验证码验证"),
    "phone_wait": ("WAIT", "等待手机短信"),
    "phone_provider": ("PROVIDER", "接码平台处理"),
}
_REASONS = {
    "invalid_phone": "当前号码无效",
    "phone_number_used": "当前号码已被使用或达到绑定上限",
    "session_conflict": "认证会话或验证步骤冲突",
    "send_limited": "请求受到限流",
    "delivery_refused": "短信发送被拒绝，未确认是号码问题",
    "whatsapp_channel": "当前验证通道与 SMS 不匹配",
    "server_error": "服务端错误",
    "send_rejected": "发送请求被拒绝，具体原因未确认",
    "code_rejected": "手机验证码被拒绝",
    "sms_timeout": "等待短信超时",
    "provider_error": "接码平台请求失败",
    "provider_no_balance": "接码平台余额不足",
    "provider_price_limit": "号码价格超过已配置上限",
    "provider_no_numbers": "接码平台暂无可用号码",
    "transport_error": "网络请求未取得有效响应",
    "retry_exhausted": "本轮尝试次数已耗尽",
    "budget_exhausted": "本轮手机验证时间已耗尽",
    "unexpected_response": "响应未确认手机验证成功",
}
_NUMBER_INVALID_CODES = {"invalid_phone", "invalid_phone_number", "phone_number_invalid", "invalid_number"}
_NUMBER_USED_CODES = {"phone_number_already_used", "phone_number_already_in_use", "phone_number_usage_limit_exceeded"}
_SESSION_CODES = {"invalid_auth_step", "invalid_state", "missing_session", "session_expired", "session_not_found"}
_RATE_CODES = {"rate_limit_exceeded", "too_many_requests", "too_many_attempts"}
_OTP_CODES = {"invalid_otp", "otp_expired", "invalid_phone_code", "incorrect_code"}
_MACHINE_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,79}\Z")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_LONG_NUMBER = re.compile(r"(?<![A-Za-z0-9])\+?\d[\d ()-]{3,}\d(?![A-Za-z0-9])")
_OPAQUE = re.compile(r"\b[A-Za-z0-9_.-]{32,}\b")


def _safe_message(value: object, sensitive_values=()) -> str:
    if not isinstance(value, str):
        return ""
    text = value[:4096]
    for secret in sensitive_values:
        if isinstance(secret, str) and len(secret) >= 3:
            text = text.replace(secret, "[已隐藏]")
    text = redact_text(text, limit=4096)
    text = _EMAIL.sub("[邮箱]", text)
    text = _LONG_NUMBER.sub("[号码或验证码]", text)
    text = _OPAQUE.sub("[已隐藏]", text)
    return " ".join(text.split())[:400]


def _safe_code(value: object) -> str:
    return value if isinstance(value, str) and _MACHINE_CODE.fullmatch(value) else ""


def safe_phone_diagnostics(value: object) -> dict[str, Any]:
    """保留错误码和简短说明，不透传响应正文、号码或认证上下文。"""
    if not isinstance(value, Mapping):
        return {}
    operation, kind = value.get("operation"), value.get("failure_kind")
    if not isinstance(operation, str) or not isinstance(kind, str) or operation not in _OPERATIONS or kind not in _REASONS:
        return {}
    result = {"operation": value["operation"], "failure_kind": value["failure_kind"], "oauth_driver": "protocol"}
    for key, low, high in (("http_status", 100, 599), ("attempt", 1, 1000), ("max_attempts", 1, 1000)):
        number = value.get(key)
        if type(number) is int and low <= number <= high:
            result[key] = number
    for key in ("number_retry_allowed", "response_received"):
        if type(value.get(key)) is bool:
            result[key] = value[key]
    for key in ("server_code", "server_type"):
        if code := _safe_code(value.get(key)):
            result[key] = code
    if message := _safe_message(value.get("server_message")):
        result["server_message"] = message
    return result


def phone_failure_cause(value: object) -> dict[str, str] | None:
    """将保存的证据投影为任务中心的明确错误，不从 409 猜测号码责任。"""
    diagnostics = safe_phone_diagnostics(value)
    if not diagnostics:
        return None
    short, label = _OPERATIONS[diagnostics["operation"]]
    reason = diagnostics["failure_kind"]
    status = diagnostics.get("http_status")
    description = _REASONS[reason]
    if status == 409 and reason == "send_rejected":
        description = "请求状态冲突，具体原因未确认"
    summary = f"{label}失败" + (f"（HTTP {status}）" if status else "") + f"：{description}"
    if code := diagnostics.get("server_code"):
        summary += f"；服务端错误码：{code}"
    if message := diagnostics.get("server_message"):
        summary += f"；服务端说明：{message}"
    return {
        "cause_code": PHONE_FAILURE_CAUSE,
        "cause_display_code": f"OA-PHONE-{short}-{status or reason.upper().replace('_', '-')}",
        "cause_summary": summary,
    }


class CodexPhoneVerificationError(RuntimeError):
    """带有限诊断的手机失败；换号许可必须由明确号码证据产生。"""

    def __init__(self, *, operation: str, failure_kind: str, http_status: int | None = None,
                 attempt: int = 1, max_attempts: int = 1, server_code: str = "",
                 server_type: str = "", server_message: str = "",
                 number_retry_allowed: bool = False, response_received: bool = False):
        self.diagnostics = safe_phone_diagnostics({
            "operation": operation, "failure_kind": failure_kind, "http_status": http_status,
            "attempt": attempt, "max_attempts": max_attempts, "server_code": server_code,
            "server_type": server_type, "server_message": server_message,
            "number_retry_allowed": number_retry_allowed, "response_received": response_received,
        })
        if not self.diagnostics:
            raise ValueError("手机验证错误包含无效的操作或分类")
        self.number_retry_allowed = bool(self.diagnostics.get("number_retry_allowed"))
        self.http_status = self.diagnostics.get("http_status")
        super().__init__(phone_failure_cause(self.diagnostics)["cause_summary"])

    def as_result(self) -> dict[str, Any]:
        """只有明确收到 4xx 才记录拒绝；5xx、超时和断连仍保留不确定事实。"""
        rejected = self.diagnostics.get("response_received") is True and 400 <= (self.http_status or 0) < 500
        return {
            "ok": False, "status": "failed", "message": str(self),
            "cause_code": PHONE_FAILURE_CAUSE, "error_category": "external",
            "http_status": self.http_status, "auth_diagnostics": dict(self.diagnostics),
            "remote_write_rejected": rejected,
        }


def phone_failure_from_response(response, *, operation: str, attempt: int, max_attempts: int,
                                sensitive_values=()) -> CodexPhoneVerificationError | None:
    """只读取响应的错误字段；成功数据里的任意文字不作为失败或买号依据。"""
    status = int(getattr(response, "status_code", 0) or 0)
    try:
        payload = response.json()
    except (AttributeError, TypeError, ValueError):
        payload = {}
    payload = payload if isinstance(payload, Mapping) else {}
    error = payload.get("error")
    explicit_error = isinstance(error, (Mapping, str)) and bool(error)
    accepted = status in ({200, 204} if operation == "phone_send" else {200})
    if accepted and not explicit_error:
        return None
    fields = error if isinstance(error, Mapping) else payload
    code = _safe_code(fields.get("code") or fields.get("error_code"))
    error_type = _safe_code(fields.get("type"))
    if code in sensitive_values:
        code = ""
    if error_type in sensitive_values:
        error_type = ""
    raw_message = fields.get("message") or fields.get("error_description") or (error if isinstance(error, str) else "")
    if not raw_message and not payload:
        plain = str(getattr(response, "text", "") or "")[:4096]
        if "<" not in plain and ">" not in plain:
            raw_message = plain
    low = str(raw_message or "").lower()
    if status >= 500:
        reason = "server_error"
    elif status == 429 or code in _RATE_CODES:
        reason = "send_limited"
    elif code in _SESSION_CODES:
        reason = "session_conflict"
    elif code in _OTP_CODES:
        reason = "code_rejected"
    elif code in _NUMBER_INVALID_CODES or (not code and any(text in low for text in (
        "invalid phone number", "phone number is not valid", "invalid_number", "手机号无效", "电话号码无效",
    ))):
        reason = "invalid_phone"
    elif code in _NUMBER_USED_CODES or (not code and "phone number" in low and any(text in low for text in (
        "already used", "already in use", "used too many times",
    ))):
        reason = "phone_number_used"
    elif "whatsapp" in low or "whats app" in low:
        reason = "whatsapp_channel"
    elif any(text in low for text in ("rate limit", "too many", "throttle", "限流", "频繁")):
        reason = "send_limited"
    elif any(text in low for text in ("cannot send", "unable to send", "cannot deliver", "无法发送")):
        reason = "delivery_refused"
    else:
        reason = "code_rejected" if operation == "phone_validate" else "send_rejected"
    may_rotate = operation == "phone_send" and 400 <= status < 500 and reason in {"invalid_phone", "phone_number_used"}
    return CodexPhoneVerificationError(
        operation=operation, failure_kind=reason, http_status=status or None, attempt=attempt,
        max_attempts=max_attempts, server_code=code, server_type=error_type,
        server_message=_safe_message(raw_message, sensitive_values), number_retry_allowed=may_rotate,
        response_received=True,
    )
