"""Storage-neutral authentication outcomes shared by browser and protocol flows."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from urllib.parse import urlsplit


class AuthErrorCode(str, Enum):
    """认证步骤之间允许传播的稳定错误码。"""

    NONE = ""
    UNSUPPORTED = "unsupported"
    REQUEST_UNKNOWN = "request_unknown"
    REMOTE_EXISTING = "remote_existing"
    PASSWORD_REQUIRED = "password_required"
    PASSWORD_REJECTED = "password_rejected"
    PASSWORD_RESULT_UNKNOWN = "password_result_unknown"
    EMAIL_OTP_REQUIRED = "email_otp_required"
    EMAIL_OTP_INVALID = "email_otp_invalid"
    EMAIL_OTP_DELIVERY_MISSING = "email_otp_delivery_missing"
    TOTP_REQUIRED = "totp_required"
    TOTP_REJECTED = "totp_rejected"
    MFA_SECRET_MISSING = "mfa_secret_missing"
    ACCOUNT_DEACTIVATED = "account_deactivated"
    NETWORK_ERROR = "network_error"
    PROTOCOL_NETWORK_ERROR = "protocol_network_error"
    CANCELLED = "cancelled"


class AuthCancelledError(RuntimeError):
    """认证步骤在安全检查点响应了协作式取消。"""

    code = AuthErrorCode.CANCELLED.value


_SAFE_STEP_EVIDENCE_KEYS = {
    "attempt",
    "button_count",
    "checkpoint",
    "driver",
    "form_count",
    "http_status",
    "input_count",
    "next_state",
    "page_state",
    "protocol_version",
    "remote_response_received",
    "response_observed",
    "route_attempt",
    "stage",
    "status",
    "url_path",
}


def _safe_step_evidence(value: Any) -> dict[str, Any]:
    """只保留步骤诊断白名单，拒绝 URL 查询串和原始响应。"""
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key or "").strip().lower()
        if key == "url":
            try:
                parsed = urlsplit(str(raw_value or ""))
                result["url_path"] = parsed.path[:240]
            except Exception:
                pass
            continue
        if key not in _SAFE_STEP_EVIDENCE_KEYS:
            continue
        if isinstance(raw_value, bool) or raw_value is None:
            result[key] = raw_value
        elif isinstance(raw_value, (int, float)):
            result[key] = raw_value
        elif isinstance(raw_value, (list, tuple)):
            result[key] = [str(item)[:80] for item in raw_value[:8]]
        else:
            result[key] = str(raw_value)[:240]
    return result


@dataclass(frozen=True)
class StepResult:
    """一个可审计认证动作的非敏感结果。

    ``action_dispatched`` 与 ``remote_response_received`` 必须分开保存：已发出
    密码、OTP 或 MFA 请求但没有收到结果时，步骤是 ``request_unknown``，不能
    被上层改写成密码错误、成功或新的自动重试。
    """

    stage: str
    ok: bool
    code: str = AuthErrorCode.NONE.value
    next_state: str = ""
    checkpoint: str = ""
    retryable: bool = False
    remote_response_received: bool = False
    action_dispatched: bool = False
    remote_identity: str = "unknown"
    next_action: str = "continue"
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        stage = str(self.stage or "unknown").strip().lower()
        code = self.code.value if isinstance(self.code, Enum) else str(self.code or "").strip().lower()
        identity = str(self.remote_identity or "unknown").strip().lower()
        next_state = str(self.next_state or "").strip().lower()
        checkpoint = str(self.checkpoint or "").strip().lower()
        next_action = str(self.next_action or "continue").strip().lower()
        # A dispatched request without a response is always an unknown result,
        # even if a caller supplied a generic timeout or transport code.
        if self.action_dispatched and not self.remote_response_received:
            code = AuthErrorCode.REQUEST_UNKNOWN.value
            next_action = "manual_reconcile"
            retryable = False
        else:
            retryable = bool(self.retryable)
        if code == AuthErrorCode.REQUEST_UNKNOWN.value:
            next_action = "manual_reconcile"
            retryable = False
        ok = bool(self.ok) and code != AuthErrorCode.REQUEST_UNKNOWN.value
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "ok", ok)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "next_state", next_state)
        object.__setattr__(self, "checkpoint", checkpoint)
        object.__setattr__(self, "remote_identity", identity)
        object.__setattr__(self, "next_action", next_action)
        object.__setattr__(self, "retryable", retryable)
        object.__setattr__(self, "evidence", _safe_step_evidence(self.evidence))

    @property
    def error_code(self) -> str:
        """兼容任务层使用的命名。"""
        return self.code

    @property
    def request_unknown(self) -> bool:
        return self.code == AuthErrorCode.REQUEST_UNKNOWN.value

    @classmethod
    def success(cls, stage: str, *, next_state: str = "", checkpoint: str = "", **kwargs: Any) -> "StepResult":
        return cls(stage, True, next_state=next_state, checkpoint=checkpoint, **kwargs)

    @classmethod
    def failure(cls, stage: str, code: str, *, next_action: str = "stop", **kwargs: Any) -> "StepResult":
        return cls(stage, False, code=code, next_action=next_action, **kwargs)

    def as_dict(self) -> dict[str, Any]:
        """返回可写入任务事件的摘要；不复制 credentials/detail/raw body。"""
        return {
            "stage": self.stage,
            "ok": bool(self.ok),
            "code": self.code,
            "error_code": self.code,
            "next_state": self.next_state,
            "checkpoint": self.checkpoint,
            "retryable": bool(self.retryable),
            "remote_response_received": bool(self.remote_response_received),
            "action_dispatched": bool(self.action_dispatched),
            "remote_identity": self.remote_identity,
            "next_action": self.next_action,
            "evidence": dict(self.evidence),
        }


# The implementation design and a few downstream adapters use the more
# explicit name. Keep both names pointing to the same immutable contract.
AuthStepResult = StepResult


def normalize_step_result(value: Any, *, stage: str = "unknown", default_code: str = "request_unknown") -> StepResult:
    """把旧 mapping/异常边界投影到 ``StepResult``，不透传敏感字段。"""
    if isinstance(value, StepResult):
        return value
    if not isinstance(value, Mapping):
        return StepResult.failure(stage, default_code, next_action="manual_reconcile")
    raw_code = value.get("code") or value.get("error_code") or value.get("status") or default_code
    code = raw_code.value if isinstance(raw_code, Enum) else str(raw_code or default_code).strip().lower()
    ok = bool(value.get("ok"))
    if ok:
        code = ""
    return StepResult(
        stage=str(value.get("stage") or stage),
        ok=ok,
        code=code,
        next_state=str(value.get("next_state") or value.get("state") or ""),
        checkpoint=str(value.get("checkpoint") or ""),
        retryable=bool(value.get("retryable", False)),
        remote_response_received=bool(value.get("remote_response_received", value.get("response_observed", False))),
        action_dispatched=bool(value.get("action_dispatched", False)),
        remote_identity=str(value.get("remote_identity") or "unknown"),
        next_action=str(value.get("next_action") or ("continue" if ok else "stop")),
        evidence=value.get("evidence") or {},
    )


class AuthStatus(str, Enum):
    AUTHENTICATED = "authenticated"
    PASSWORD_REQUIRED = "password_required"
    PASSWORD_REJECTED = "password_rejected"
    EMAIL_OTP_REQUIRED = "email_otp_required"
    EMAIL_OTP_INVALID = "email_otp_invalid"
    TOTP_REQUIRED = "totp_required"
    TOTP_REJECTED = "totp_rejected"
    REMOTE_EXISTING = "remote_existing"
    ACCOUNT_DEACTIVATED = "account_deactivated"
    UNSUPPORTED = "unsupported"
    REQUEST_UNKNOWN = "request_unknown"


class RemoteExistingAccountError(RuntimeError):
    """The registration entry point reached a known existing remote account."""

    code = "remote_existing"


class PasswordRejectedError(RuntimeError):
    """The remote login explicitly rejected the saved account password."""

    code = "password_rejected"


class PasswordSetupUnsupportedError(RuntimeError):
    """The account is authenticated but the remote password setup is unavailable."""

    code = "password_setup_unsupported"


class PasswordSetupNotReadyError(RuntimeError):
    """The settings shell was observed before its security controls mounted."""

    code = "password_setup_not_ready"


class MfaSecretMissingError(RuntimeError):
    """The remote requested TOTP but no local authenticator secret is available."""

    code = "mfa_secret_missing"


_NO_FALLBACK_CODES = {
    "password_rejected",
    "password_result_unknown",
    "password_rejected_email_fallback_failed",
    "passwordless_fallback_unavailable",
    "mfa_rejected",
    "mfa_secret_missing",
    "account_deactivated",
    "remote_existing",
}
_RETRYABLE_CODES = {
    "protocol_network_error",
    "network_error",
    "email_otp_delivery_missing",
}
_SAFE_STATUS_VALUES = {item.value for item in AuthStatus}


def _clean_text(value: Any) -> str:
    if isinstance(value, Enum):
        value = value.value
    return str(value or "").strip()


def _clean_chain(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = ()
    return tuple(item for item in (_clean_text(item) for item in values) if item)


def _result_code(value: Mapping[str, Any]) -> str:
    """Read a stable code without exposing or persisting the full error text."""
    raw = _clean_text(value.get("code") or value.get("error_code") or value.get("error")).lower()
    if raw in _SAFE_STATUS_VALUES or raw in _NO_FALLBACK_CODES or raw in _RETRYABLE_CODES:
        return raw
    text = raw
    candidates = sorted(
        _SAFE_STATUS_VALUES | _NO_FALLBACK_CODES | _RETRYABLE_CODES,
        key=len,
        reverse=True,
    )
    return next((candidate for candidate in candidates if candidate in text), "")


@dataclass(frozen=True)
class AuthAttemptResult:
    """Safe cross-driver result for one authentication attempt.

    Provider-specific payloads are intentionally not part of this model.  The
    browser/protocol adapters may retain their private data locally, but the
    task layer receives only these compatibility fields.
    """

    status: str
    code: str = ""
    auth_method: str = ""
    challenge_chain: tuple[str, ...] = ()
    remote_identity: str = "unknown"
    retryable: bool = False
    roxy_fallback_allowed: bool = True
    next_action: str = "continue"

    def __post_init__(self) -> None:
        status = _clean_text(self.status).lower() or AuthStatus.REQUEST_UNKNOWN.value
        code = _clean_text(self.code).lower()
        auth_method = _clean_text(self.auth_method).lower()
        remote_identity = _clean_text(self.remote_identity).lower() or "unknown"
        next_action = _clean_text(self.next_action).lower() or "continue"
        if code in _NO_FALLBACK_CODES:
            object.__setattr__(self, "roxy_fallback_allowed", False)
            if next_action == "continue":
                next_action = "stop"
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "auth_method", auth_method)
        object.__setattr__(self, "challenge_chain", _clean_chain(self.challenge_chain))
        object.__setattr__(self, "remote_identity", remote_identity)
        object.__setattr__(self, "next_action", next_action)

    def as_dict(self) -> dict[str, Any]:
        """Return only non-sensitive fields suitable for task events/UI."""
        return {
            "status": self.status,
            "code": self.code,
            "auth_method": self.auth_method,
            "challenge_chain": list(self.challenge_chain),
            "remote_identity": self.remote_identity,
            "retryable": bool(self.retryable),
            "roxy_fallback_allowed": bool(self.roxy_fallback_allowed),
            "next_action": self.next_action,
        }


def normalize_auth_result(value: Any, *, default_status: str = "request_unknown") -> AuthAttemptResult:
    """Normalize a driver mapping without copying provider payloads."""
    if isinstance(value, AuthAttemptResult):
        return value
    if not isinstance(value, Mapping):
        return AuthAttemptResult(status=default_status, code=default_status, next_action="manual_reconcile")

    raw_code = _result_code(value)
    raw_status = _clean_text(value.get("status") or value.get("auth_status")).lower()
    if not raw_status:
        if raw_code in _SAFE_STATUS_VALUES or raw_code in _NO_FALLBACK_CODES:
            raw_status = raw_code
        elif value.get("ok"):
            raw_status = AuthStatus.AUTHENTICATED.value
        else:
            raw_status = default_status
    if not raw_code and raw_status in _SAFE_STATUS_VALUES:
        raw_code = raw_status

    retryable = bool(value.get("retryable", raw_code in _RETRYABLE_CODES))
    fallback = bool(value.get("roxy_fallback_allowed", raw_code not in _NO_FALLBACK_CODES))
    next_action = _clean_text(value.get("next_action")).lower()
    if not next_action:
        if raw_code == "unsupported":
            next_action = "roxy_fallback"
        elif raw_code in _NO_FALLBACK_CODES:
            next_action = "stop"
        elif raw_code == "request_unknown":
            next_action = "manual_reconcile"
        else:
            next_action = "continue"

    return AuthAttemptResult(
        status=raw_status,
        code=raw_code,
        auth_method=_clean_text(value.get("auth_method")),
        challenge_chain=_clean_chain(value.get("challenge_chain")),
        remote_identity=_clean_text(value.get("remote_identity")) or "unknown",
        retryable=retryable,
        roxy_fallback_allowed=fallback,
        next_action=next_action,
    )


def classify_registration_identity(state: Any) -> str:
    """Classify the remote identity from an observed registration page state."""
    value = _clean_text(state).lower()
    if value in {"login_password", "logged_in", "authenticated", "external_url", "callback", "existing"}:
        return "existing"
    if value in {"password", "password_create", "otp", "email_otp", "profile", "about_you", "new_candidate"}:
        return "new_candidate"
    return "unknown"


def safe_to_start_new_registration(value: Any) -> bool:
    """Return whether a result is safe to send through a new-registration retry."""
    if isinstance(value, AuthAttemptResult):
        identity = value.remote_identity
        status = value.status
        return identity not in {"existing", "unknown"} and status not in {
            AuthStatus.REMOTE_EXISTING.value,
            AuthStatus.REQUEST_UNKNOWN.value,
        }
    if not isinstance(value, Mapping):
        return False
    identity = _clean_text(value.get("remote_identity")).lower()
    status = _clean_text(value.get("status")).lower()
    return not bool(value.get("request_unknown") or value.get("manual_reconcile")) and identity not in {
        "existing", "unknown",
    } and status not in {AuthStatus.REMOTE_EXISTING.value, AuthStatus.REQUEST_UNKNOWN.value}


def auth_result_for_operation(
    value: Any,
    *,
    auth_method: str,
    remote_identity: str = "existing",
) -> AuthAttemptResult:
    """Build a safe authentication projection for an operation result."""
    mapping = value if isinstance(value, Mapping) else {}
    method = _clean_text(mapping.get("auth_method") or auth_method).lower()
    ok = bool(mapping.get("ok"))
    code = _result_code(mapping)
    if ok:
        status = AuthStatus.AUTHENTICATED.value
    elif code in _NO_FALLBACK_CODES or code in _SAFE_STATUS_VALUES:
        status = code
    else:
        status = AuthStatus.REQUEST_UNKNOWN.value
        code = code or AuthStatus.REQUEST_UNKNOWN.value

    chain: list[str] = list(_clean_chain(mapping.get("challenge_chain")))
    password_verified = str(mapping.get("password_auth_status") or "").lower() == "verified"
    if not chain and (password_verified or (ok and "password" in method and "fallback" not in method)):
        chain.append("password")
    if "email" in method or method == "legacy_email_otp":
        if "email_otp" not in chain:
            chain.append("email_otp")
    if "mfa" in method or "totp" in method:
        if "totp" not in chain:
            chain.append("totp")

    return AuthAttemptResult(
        status=status,
        code=code,
        auth_method=method,
        challenge_chain=tuple(chain),
        remote_identity=remote_identity,
        retryable=bool(mapping.get("retryable", False)),
        roxy_fallback_allowed=bool(mapping.get("roxy_fallback_allowed", code not in _NO_FALLBACK_CODES)),
        next_action="continue" if ok else "manual_reconcile" if status == AuthStatus.REQUEST_UNKNOWN.value else "stop",
    )


def auth_result_for_registration(
    value: Any,
    *,
    auth_method: str,
    remote_identity: str,
    challenge_chain: Any = (),
) -> AuthAttemptResult:
    """Project a registration result onto the shared authentication contract."""
    mapping = dict(value) if isinstance(value, Mapping) else {}
    if "ok" not in mapping:
        mapping["ok"] = bool(mapping.get("success") or mapping.get("registration_success"))
    if "error" not in mapping and mapping.get("error_code"):
        mapping["error"] = mapping.get("error_code")
    mapping["auth_method"] = auth_method
    mapping["remote_identity"] = remote_identity
    if challenge_chain:
        mapping["challenge_chain"] = challenge_chain
    return auth_result_for_operation(
        mapping,
        auth_method=auth_method,
        remote_identity=remote_identity,
    )


__all__ = [
    "AuthErrorCode",
    "AuthCancelledError",
    "AuthStepResult",
    "AuthAttemptResult",
    "AuthStatus",
    "StepResult",
    "RemoteExistingAccountError",
    "PasswordRejectedError",
    "PasswordSetupUnsupportedError",
    "PasswordSetupNotReadyError",
    "MfaSecretMissingError",
    "auth_result_for_operation",
    "auth_result_for_registration",
    "classify_registration_identity",
    "normalize_auth_result",
    "normalize_step_result",
    "safe_to_start_new_registration",
]
