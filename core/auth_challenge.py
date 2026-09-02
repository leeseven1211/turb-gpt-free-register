"""Storage-neutral authentication outcomes shared by browser and protocol flows."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class AuthStatus(str, Enum):
    AUTHENTICATED = "authenticated"
    PASSWORD_REQUIRED = "password_required"
    PASSWORD_REJECTED = "password_rejected"
    EMAIL_OTP_REQUIRED = "email_otp_required"
    EMAIL_OTP_INVALID = "email_otp_invalid"
    TOTP_REQUIRED = "totp_required"
    TOTP_REJECTED = "totp_rejected"
    REMOTE_EXISTING = "remote_existing"
    UNSUPPORTED = "unsupported"
    REQUEST_UNKNOWN = "request_unknown"


_NO_FALLBACK_CODES = {
    "password_rejected",
    "password_result_unknown",
    "password_rejected_email_fallback_failed",
    "passwordless_fallback_unavailable",
    "mfa_rejected",
    "mfa_secret_missing",
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

    raw_code = _clean_text(value.get("code") or value.get("error")).lower()
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


__all__ = ["AuthAttemptResult", "AuthStatus", "normalize_auth_result"]
