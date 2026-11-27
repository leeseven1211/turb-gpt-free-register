# -*- coding: utf-8 -*-
"""协议改密的外围辅助契约。

本模块只负责候选密码、固定邮箱上下文校验和远端响应分类，不驱动改密流程。
"""
from __future__ import annotations

import re
import secrets
import string
from datetime import datetime, timezone
from typing import Any


_PASSWORD_LENGTH = 14
_PASSWORD_SYMBOLS = string.punctuation
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + _PASSWORD_SYMBOLS
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,100}$")
_EMAIL = re.compile(r"^[^\s<>@,;]+@[^\s<>@,;]+$")
_RATE_LIMIT_CODES = frozenset({"http_429", "butler_http_429"})
_SERVER_CODES = frozenset({
    "butler_transport_timeout", "butler_transport_connection", "butler_transport_failed",
})
_PARSE_CODES = frozenset({
    "butler_response_not_json", "butler_response_invalid", "butler_lease_response_invalid",
    "otp_format_invalid",
})
_AUTH_CODES = frozenset({
    "source_authentication_failed", "butler_credentials_missing", "service_not_allowed",
    "unauthorized", "forbidden",
})
_TIMEOUT_CODES = frozenset({"inbound_code_timeout", "email_otp_no_mail", "otp_timeout", "no_mail"})
_PROVIDER_TIMEOUT_MARKERS = (
    ("core.email.gptmail.client", "GPTMailError", "等待 GPTMail 验证码超时", "gptmail_otp_timeout"),
    ("core.email.cloudflare.client", "CFTempMailError", "等待 Cloudflare 验证码超时", "cloudflare_otp_timeout"),
    ("core.email.outlook.client", "OutlookClientError", "等待 ", "outlook_otp_timeout"),
)
_COOLDOWN_DETAIL_KEYS = frozenset({
    "cooldownAction", "cooldown_action", "unlockAt", "unlock_at",
    "retryAfter", "retry_after", "cooldownUntil", "cooldown_until",
})


class ProtocolPasswordResetError(RuntimeError):
    """改密外围错误，字段稳定且消息不携带上游正文。"""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        stage: str,
        category: str = "auth",
        cause_code: str = "",
        retryable: bool = False,
        request_unknown: bool = False,
        detail: dict | None = None,
    ):
        self.code = str(code or "password_reset_failed")
        self.message = _safe_message(message or self.code)
        self.stage = str(stage or "unknown")
        self.category = str(category or "auth")
        self.cause_code = str(cause_code or "")
        self.retryable = bool(retryable)
        self.request_unknown = bool(request_unknown)
        self.detail = dict(detail) if isinstance(detail, dict) else None
        super().__init__(f"{self.code}: {self.message}（阶段={self.stage}）")


def _safe_message(value: Any) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:240] or "改密请求失败"


def _field(value: Any, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def generate_reset_password(old_password: str = "") -> str:
    """生成独立的 14 位强随机候选密码。"""
    old = str(old_password or "")
    while True:
        chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice(_PASSWORD_SYMBOLS),
        ]
        chars.extend(secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH - len(chars)))
        secrets.SystemRandom().shuffle(chars)
        candidate = "".join(chars)
        if candidate != old:
            return candidate


def _error(
    code: str,
    message: str,
    *,
    stage: str,
    category: str = "auth",
    cause_code: str = "",
    retryable: bool = False,
    request_unknown: bool = False,
    detail: dict | None = None,
) -> ProtocolPasswordResetError:
    return ProtocolPasswordResetError(
        code,
        message,
        stage=stage,
        category=category,
        cause_code=cause_code,
        retryable=retryable,
        request_unknown=request_unknown,
        detail=detail,
    )


def _safe_remote_code(payload: Any) -> str:
    candidates: list[Any] = []

    def visit(value: Any, *, depth: int = 0):
        if depth > 3:
            return
        if isinstance(value, dict):
            for key in ("code", "error_code", "errorCode", "type"):
                if key in value:
                    candidates.append(value[key])
            for key in ("error", "errors", "details"):
                if key in value:
                    visit(value[key], depth=depth + 1)
        elif isinstance(value, list):
            for item in value[:8]:
                visit(item, depth=depth + 1)
        elif isinstance(value, str):
            candidates.append(value)

    visit(payload)
    for value in candidates:
        code = str(value or "").strip().lower()
        if _SAFE_CODE.fullmatch(code):
            return code
    return ""


def _response_payload(response: Any, *, allow_empty: bool) -> dict:
    text = str(getattr(response, "text", "") or "")
    try:
        payload = response.json()
    except Exception:
        if allow_empty and not text.strip():
            return {}
        raise ValueError("响应不是 JSON")
    if payload is None and allow_empty and not text.strip():
        return {}
    if not isinstance(payload, dict):
        raise ValueError("响应 JSON 不是对象")
    return payload


def _stage_is_otp(stage: str) -> bool:
    return str(stage or "").strip().lower() == "validate_otp"


def _stage_allows_empty_success(stage: str) -> bool:
    return str(stage or "").strip().lower() in {"send_otp", "reset"}


def _cooldown_detail(payload: Any) -> dict:
    detail: dict = {}

    def visit(value: Any):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in _COOLDOWN_DETAIL_KEYS and isinstance(item, (str, int, float, bool)):
                    detail[key] = item
                elif isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(value, list):
            for item in value[:8]:
                visit(item)

    visit(payload)
    return detail


def check_reset_response(
    response: Any,
    *,
    stage: str,
    result_unknown: bool = False,
) -> dict:
    """校验一次改密请求响应并把远端错误归一化为稳定异常。"""
    status = getattr(response, "status_code", None)
    try:
        status = int(status)
    except (TypeError, ValueError):
        raise _error(
            "password_reset_response_invalid",
            "远端响应缺少有效 HTTP 状态",
            stage=stage,
            category="network",
            cause_code="http_status_missing",
            retryable=True,
            request_unknown=bool(result_unknown),
        ) from None

    if status == 200:
        try:
            payload = _response_payload(response, allow_empty=_stage_allows_empty_success(stage))
        except ValueError:
            raise _error(
                "password_reset_response_invalid",
                "远端响应格式无效",
                stage=stage,
                category="network",
                cause_code="response_not_json",
                retryable=False,
                request_unknown=bool(result_unknown),
                detail={"http_status": status},
            ) from None
    else:
        try:
            payload = _response_payload(response, allow_empty=True)
        except ValueError:
            payload = {}

    if status == 200:
        return payload

    remote_code = _safe_remote_code(payload)
    cause_code = remote_code or f"http_{status}"
    detail = {"http_status": status}
    if remote_code:
        detail["remote_error_code"] = remote_code

    if status == 429 or remote_code == "sensitive_action_cooldown":
        detail.update(_cooldown_detail(payload))
        raise _error(
            "password_reset_cooldown" if remote_code == "sensitive_action_cooldown" else "password_reset_rate_limited",
            "改密请求被限流或冷却",
            stage=stage,
            category="network",
            cause_code=cause_code,
            retryable=True,
            request_unknown=False,
            detail=detail,
        )

    if status in {401, 403}:
        raise _error(
            "password_reset_otp_rejected" if _stage_is_otp(stage) else "password_reset_rejected",
            "验证码被远端拒绝" if _stage_is_otp(stage) else "改密请求被远端拒绝",
            stage=stage,
            category="auth",
            cause_code=cause_code,
            detail=detail,
        )

    if status >= 500:
        raise _error(
            "password_reset_request_unknown" if result_unknown else "password_reset_network_failed",
            "改密结果待核验" if result_unknown else "远端改密服务暂时不可用",
            stage=stage,
            category="network",
            cause_code=cause_code,
            retryable=True,
            request_unknown=bool(result_unknown),
            detail=detail,
        )

    raise _error(
        "password_reset_otp_rejected" if _stage_is_otp(stage) else "password_reset_rejected",
        "验证码请求被远端拒绝" if _stage_is_otp(stage) else "改密请求被远端拒绝",
        stage=stage,
        category="auth",
        cause_code=cause_code,
        request_unknown=bool(result_unknown),
        detail=detail,
    )


def _error_from_mailbox_exception(exc: Exception, *, stage: str) -> ProtocolPasswordResetError:
    code = str(getattr(exc, "error_code", "") or getattr(exc, "code", "") or "").strip().lower()
    if not _SAFE_CODE.fullmatch(code):
        code = "email_check_failed"
    retryable = bool(getattr(exc, "retryable", False))
    if code in {"email_resource_expired", "email_resource_expiry_invalid"}:
        retryable = False
    if getattr(exc, "identity_locked", False):
        code = "email_identity_missing" if code in {"", "email_check_failed"} else code
        retryable = False
    return _error(
        code,
        "原注册邮箱不可用或缺少固定身份",
        stage=stage,
        category="email",
        cause_code=code,
        retryable=retryable,
        request_unknown=bool(getattr(exc, "request_unknown", False)),
    )


def classify_reset_mailbox_error(
    exc: Exception,
    *,
    stage: str = "wait_otp",
) -> ProtocolPasswordResetError:
    """把已有邮箱 provider 异常归类为改密取码异常。"""
    if isinstance(exc, ProtocolPasswordResetError):
        return exc

    original_code = str(
        getattr(exc, "error_code", "")
        or getattr(exc, "code", "")
        or ""
    ).strip().lower()
    status = getattr(exc, "status_code", None)
    try:
        status = int(status) if status is not None else None
    except (TypeError, ValueError):
        status = None
    code_text = original_code.replace("-", "_")
    retryable = bool(getattr(exc, "retryable", False))
    request_unknown = bool(getattr(exc, "request_unknown", False))

    for module_name, class_name, marker, cause_code in _PROVIDER_TIMEOUT_MARKERS:
        provider_module = __import__(module_name, fromlist=[class_name])
        provider_error = getattr(provider_module, class_name)
        text = str(exc or "")
        is_timeout = marker in text and (
            class_name != "OutlookClientError" or " OTP 超时" in text
        )
        if isinstance(exc, provider_error) and is_timeout:
            return _error(
                "password_reset_otp_timeout",
                "等待邮箱验证码超时",
                stage=stage,
                category="email",
                cause_code=cause_code,
                retryable=True,
                request_unknown=request_unknown,
            )

    if original_code in {"email_resource_expired", "email_resource_expiry_invalid"}:
        return _error(
            original_code,
            "原邮箱资源已过期或有效期无效",
            stage=stage,
            category="email",
            cause_code=original_code,
        )

    if status == 429 or code_text in _RATE_LIMIT_CODES or code_text.endswith("_rate_limited"):
        return _error(
            "password_reset_rate_limited",
            "邮箱取码服务被限流",
            stage=stage,
            category="network",
            cause_code=original_code or "http_429",
            retryable=True,
            request_unknown=request_unknown,
        )

    if (status is not None and status >= 500) or code_text in _SERVER_CODES:
        return _error(
            "password_reset_otp_mailbox_unavailable",
            "邮箱取码服务暂时不可用",
            stage=stage,
            category="network",
            cause_code=original_code or f"http_{status}",
            retryable=True,
            request_unknown=request_unknown,
        )

    if code_text in _PARSE_CODES:
        return _error(
            "password_reset_otp_parse_failed",
            "邮箱取码响应格式无效",
            stage=stage,
            category="email",
            cause_code=original_code or "response_parse_failed",
            retryable=True,
            request_unknown=request_unknown,
        )

    if original_code in _AUTH_CODES or status in {401, 403}:
        return _error(
            "password_reset_otp_auth_failed",
            "邮箱取码服务认证失败",
            stage=stage,
            category="auth",
            cause_code=original_code or f"http_{status}",
            retryable=False,
            request_unknown=request_unknown,
        )

    if original_code in _TIMEOUT_CODES or isinstance(exc, TimeoutError):
        return _error(
            "password_reset_otp_timeout",
            "等待邮箱验证码超时",
            stage=stage,
            category="email",
            cause_code=original_code or "otp_timeout",
            retryable=True,
            request_unknown=request_unknown,
        )

    return _error(
        "password_reset_otp_failed",
        "邮箱取码失败",
        stage=stage,
        category="email",
        cause_code=original_code or type(exc).__name__.lower(),
        retryable=retryable,
        request_unknown=request_unknown,
    )


def _check_expiry(account: Any, *, stage: str) -> None:
    leased_until = _field(account, "leased_until", "")
    if not leased_until:
        return
    try:
        parsed = datetime.fromisoformat(str(leased_until).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except (TypeError, ValueError):
        raise _error(
            "email_resource_expiry_invalid",
            "原邮箱有效期无效",
            stage=stage,
            category="email",
            cause_code="email_resource_expiry_invalid",
        ) from None
    if parsed <= datetime.now(timezone.utc):
        raise _error(
            "email_resource_expired",
            "原邮箱租约已过期",
            stage=stage,
            category="email",
            cause_code="email_resource_expired",
        )


def _check_butler_identity(account: Any, *, stage: str) -> None:
    if not (_field(account, "acquisition_id", "") or _field(account, "lease_id", "")):
        raise _error(
            "email_identity_missing",
            "原 Email Butler 租约身份缺失",
            stage=stage,
            category="email",
            cause_code="lease_identity_missing",
        )
    _check_expiry(account, stage=stage)


def check_reset_mailbox(email: str) -> None:
    """只校验并复用原邮箱上下文，不发信、领新邮箱或永久标记邮箱。"""
    address = str(email or "").strip()
    stage = "mailbox"
    if not _EMAIL.fullmatch(address):
        raise _error(
            "email_invalid",
            "改密邮箱地址无效",
            stage=stage,
            category="configuration",
            cause_code="email_invalid",
        )

    try:
        from core.email.provider import resolve_email_source
        source = resolve_email_source(address, fallback=False)
    except Exception:
        raise _error(
            "email_source_check_failed",
            "原注册邮箱来源无法确认",
            stage=stage,
            category="network",
            cause_code="email_source_check_failed",
            retryable=True,
        ) from None

    if source not in {"generic_api", "email_butler"}:
        return None

    if source == "generic_api":
        from core.email.generic_api import client as generic_client
        from core.email.resource_lifetime import EmailResourceLifetimeError, require_usable

        try:
            generic = generic_client.get_account_context(address)
        except (EmailResourceLifetimeError, generic_client.GenericApiMailError) as exc:
            raise _error_from_mailbox_exception(exc, stage=stage) from None
        except Exception:
            raise _error(
                "email_check_failed",
                "通用 API 邮箱检查失败",
                stage=stage,
                category="network",
                cause_code="generic_api_context_failed",
                retryable=True,
            ) from None
        if generic is None:
            raise _error(
                "email_identity_missing",
                "原通用 API 邮箱上下文缺失",
                stage=stage,
                category="email",
                cause_code="generic_api_context_missing",
            )
        try:
            require_usable(generic)
        except EmailResourceLifetimeError as exc:
            raise _error_from_mailbox_exception(exc, stage=stage) from None
        return None

    from core.email.email_butler import client as butler_client

    try:
        butler = butler_client.get_account_context(address)
        if butler is None:
            butler = butler_client.restore_account_context(address, purpose="password_reset")
    except Exception as exc:
        raise _error_from_mailbox_exception(exc, stage=stage) from None
    if butler is None or str(_field(butler, "email", "")).strip().lower() != address.lower():
        raise _error(
            "email_identity_missing",
            "原 Email Butler 租约身份缺失",
            stage=stage,
            category="email",
            cause_code="lease_identity_missing",
        )
    _check_butler_identity(butler, stage=stage)
    return None


__all__ = [
    "ProtocolPasswordResetError",
    "classify_reset_mailbox_error",
    "check_reset_mailbox",
    "check_reset_response",
    "generate_reset_password",
]
