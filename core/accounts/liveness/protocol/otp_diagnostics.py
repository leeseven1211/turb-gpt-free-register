"""账号协议取码的安全失败事实，不参与认证、重试或回执决策。"""
from __future__ import annotations

from core.email.email_butler.client import EmailButlerClientError


OTP_OPERATIONS = frozenset({"email_otp", "email_otp_send", "email_otp_validate"})
MAILBOX_ERROR_CODES = frozenset({
    "source_untrusted", "source_authentication_failed", "recipient_contract_unsupported",
    "recipient_evidence_missing", "recipient_ambiguous", "recipient_mismatch", "mailbox_mismatch",
    "inbound_code_timeout", "inbound_code_ambiguous", "inbound_request_failed", "inbound_storage_error",
    "invalid_key", "service_not_authorized", "invalid_request", "unknown",
})
TRANSPORT_EXCEPTION_TYPES = frozenset({
    "Timeout", "ReadTimeout", "ConnectTimeout", "TimeoutError", "SSLError",
    "SSLCertVerificationError", "ProxyError", "ConnectionError", "ConnectionResetError",
    "ConnectionAbortedError", "ConnectionRefusedError", "ProxyConnectionError", "BrokenPipeError", "CurlError",
    "RequestException", "ChunkedEncodingError", "IncompleteRead",
})
_EXCEPTION_TYPES = TRANSPORT_EXCEPTION_TYPES | {
    "Exception", "RuntimeError", "ValueError", "TypeError", "HTTPError",
    "EmailButlerClientError", "ForwardIMAPNoMailTimeout", "ForwardIMAPError",
    "EmailOtpInvalidError", "EmailOtpSendError",
}
_CURL_CODES = frozenset({5, 6, 7, 18, 28, 35, 52, 55, 56, 60, 97})


def mark_otp_failure(error: BaseException, operation: str) -> None:
    """只标记原异常发生的动作，原对象、消息和传播方式均由调用方保留。"""
    if isinstance(operation, str) and operation in OTP_OPERATIONS:
        try:
            error._otp_operation = operation
        except Exception:
            # 诊断标记不可写时仍传播原异常。
            pass


def otp_failure_diagnostics(error: BaseException, *, operation: str = "email_otp") -> dict:
    """只导出固定原因码及数值，不保存异常原文、邮箱、验证码或请求内容。"""
    from core.auth.protocol.openai_auth import EmailOtpSendError

    marked = getattr(error, "_otp_operation", None)
    if isinstance(marked, str) and marked in OTP_OPERATIONS:
        operation = marked
    elif not isinstance(operation, str) or operation not in OTP_OPERATIONS:
        operation = "email_otp"
    name = type(error).__name__
    result = {
        "operation": operation,
        "failure_kind": "otp_error",
        "exception_type": name if name in _EXCEPTION_TYPES else "Exception",
    }
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    if type(status) is int and 100 <= status <= 599:
        result["http_status"] = status

    chain: list[BaseException] = []
    cause = error
    while isinstance(cause, BaseException) and len(chain) < 8 and not any(cause is item for item in chain):
        chain.append(cause)
        cause = cause.__cause__ or (None if cause.__suppress_context__ else cause.__context__)
    for cause in chain:
        cause_name = type(cause).__name__
        if "transport_exception_type" not in result and cause_name in TRANSPORT_EXCEPTION_TYPES:
            result["transport_exception_type"] = cause_name
        curl_code = getattr(cause, "code", None)
        if "curl_error_code" not in result and type(curl_code) is int and curl_code in _CURL_CODES:
            result["curl_error_code"] = curl_code

    if isinstance(error, EmailButlerClientError):
        code = error.error_code if isinstance(error.error_code, str) else "unknown"
        result["mailbox_error_code"] = code if code in MAILBOX_ERROR_CODES else "unknown"
        if code == "inbound_code_timeout" and status in (None, 408):
            result["failure_kind"] = "no_mail"
        elif code in {"", "unknown", "inbound_request_failed"} and (
            "transport_exception_type" in result or "curl_error_code" in result
        ):
            result["failure_kind"] = "transport_error"
        else:
            result["failure_kind"] = "mailbox_error"
    elif isinstance(error, EmailOtpSendError):
        if error.reason in {"http_error", "rejected", "unconfirmed"}:
            result["failure_kind"] = error.reason
    elif name in {"ForwardIMAPNoMailTimeout", "ForwardIMAPError", "EmailOtpInvalidError"}:
        result["failure_kind"] = {
            "ForwardIMAPNoMailTimeout": "no_mail",
            "ForwardIMAPError": "imap_error",
            "EmailOtpInvalidError": "invalid_code",
        }[name]
    elif name == "TimeoutError" and operation == "email_otp":
        result["failure_kind"] = "manual_timeout"
    elif type(status) is int and 400 <= status <= 599:
        result["failure_kind"] = "http_error"
    elif "transport_exception_type" in result or "curl_error_code" in result:
        result["failure_kind"] = "transport_error"
    return result
