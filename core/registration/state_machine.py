"""Shared registration page states and bounded stage orchestration helpers.

The browser and protocol implementations intentionally keep their I/O code in
their own modules.  This module only owns the state vocabulary and the one
monotonic deadline that a stage may spend across primary, assist, and fallback
actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time
from typing import Any, Callable, Mapping


class PageState(str, Enum):
    EMAIL_FORM = "EMAIL_FORM"
    AUTH_TRANSIENT = "AUTH_TRANSIENT"
    PASSWORD_CREATE = "PASSWORD_CREATE"
    PASSWORD_LOGIN = "PASSWORD_LOGIN"
    OTP_EMAIL = "OTP_EMAIL"
    OTP_ACCEPTED = "OTP_ACCEPTED"
    EMAIL_VERIFIED = "EMAIL_VERIFIED"
    OTP_INVALID = "OTP_INVALID"
    OTP_STUCK = "OTP_STUCK"
    MFA_TOTP = "MFA_TOTP"
    PROFILE = "PROFILE"
    AUTHENTICATED = "AUTHENTICATED"
    AUTH_ERROR = "AUTH_ERROR"
    LOGGED_OUT = "LOGGED_OUT"
    UNKNOWN = "UNKNOWN"


class FlowStateError(RuntimeError):
    """Raised when a page transition would skip or reverse a checkpoint."""


class StageTimeout(TimeoutError):
    """Raised when a stage's shared deadline is exhausted."""


class RegistrationStateMachine:
    """Small, deterministic state machine used by browser-facing adapters."""

    _TERMINAL = {
        PageState.AUTHENTICATED,
        PageState.AUTH_ERROR,
        PageState.LOGGED_OUT,
        PageState.UNKNOWN,
    }
    _TRANSITIONS = {
        PageState.EMAIL_FORM: {
            PageState.AUTH_TRANSIENT,
            PageState.PASSWORD_CREATE,
            PageState.PASSWORD_LOGIN,
            PageState.OTP_EMAIL,
            PageState.AUTHENTICATED,
            PageState.AUTH_ERROR,
            PageState.LOGGED_OUT,
            PageState.UNKNOWN,
        },
        PageState.AUTH_TRANSIENT: {
            PageState.PASSWORD_CREATE,
            PageState.PASSWORD_LOGIN,
            PageState.OTP_EMAIL,
            PageState.MFA_TOTP,
            PageState.PROFILE,
            PageState.AUTHENTICATED,
            PageState.AUTH_ERROR,
            PageState.LOGGED_OUT,
            PageState.UNKNOWN,
        },
        PageState.PASSWORD_CREATE: {
            PageState.OTP_EMAIL,
            PageState.PROFILE,
            PageState.AUTHENTICATED,
            PageState.AUTH_ERROR,
            PageState.UNKNOWN,
        },
        PageState.PASSWORD_LOGIN: {
            PageState.OTP_EMAIL,
            PageState.MFA_TOTP,
            PageState.AUTHENTICATED,
            PageState.AUTH_ERROR,
            PageState.LOGGED_OUT,
            PageState.UNKNOWN,
        },
        PageState.OTP_EMAIL: {
            PageState.OTP_ACCEPTED,
            PageState.EMAIL_VERIFIED,
            PageState.OTP_INVALID,
            PageState.OTP_STUCK,
            PageState.PROFILE,
            PageState.AUTHENTICATED,
            PageState.AUTH_ERROR,
            PageState.LOGGED_OUT,
            PageState.UNKNOWN,
        },
        PageState.OTP_INVALID: {PageState.OTP_EMAIL, PageState.AUTH_ERROR, PageState.UNKNOWN},
        PageState.OTP_STUCK: {PageState.OTP_EMAIL, PageState.AUTH_ERROR, PageState.UNKNOWN},
        PageState.OTP_ACCEPTED: {
            PageState.EMAIL_VERIFIED,
            PageState.MFA_TOTP,
            PageState.PROFILE,
            PageState.AUTHENTICATED,
            PageState.AUTH_ERROR,
            PageState.UNKNOWN,
        },
        PageState.EMAIL_VERIFIED: {
            PageState.PROFILE,
            PageState.MFA_TOTP,
            PageState.AUTHENTICATED,
            PageState.AUTH_ERROR,
            PageState.UNKNOWN,
        },
        PageState.MFA_TOTP: {
            PageState.AUTHENTICATED,
            PageState.AUTH_ERROR,
            PageState.LOGGED_OUT,
            PageState.UNKNOWN,
        },
        PageState.PROFILE: {
            PageState.AUTHENTICATED,
            PageState.AUTH_ERROR,
            PageState.LOGGED_OUT,
            PageState.UNKNOWN,
        },
    }

    def __init__(self, initial: PageState = PageState.EMAIL_FORM):
        self.state = PageState(initial)
        self.history = [self.state]

    def transition(self, state: PageState) -> PageState:
        state = PageState(state)
        if self.state in self._TERMINAL:
            raise FlowStateError(f"cannot transition from terminal state {self.state.value}")
        if state not in self._TRANSITIONS.get(self.state, set()):
            raise FlowStateError(f"invalid registration transition {self.state.value} -> {state.value}")
        self.state = state
        self.history.append(state)
        return state


@dataclass(frozen=True)
class StageBudget:
    """A monotonic deadline shared by primary, protocol assist and fallback."""

    deadline: float
    clock: Callable[[], float] = time.monotonic

    @classmethod
    def start(cls, timeout: float, *, clock: Callable[[], float] = time.monotonic) -> "StageBudget":
        return cls(clock() + max(0.0, float(timeout)), clock)

    def remaining(self, cap: float | None = None) -> float:
        value = max(0.0, self.deadline - self.clock())
        if cap is not None:
            value = min(value, max(0.0, float(cap)))
        return value

    def expired(self) -> bool:
        return self.remaining() <= 0

    def require(self, action: str = "stage") -> float:
        remaining = self.remaining()
        if remaining <= 0:
            raise StageTimeout(f"{action} exceeded shared stage timeout")
        return remaining

    def child(self, cap: float | None = None) -> "StageBudget":
        return StageBudget(self.clock() + self.remaining(cap), self.clock)


def _text(snapshot: Mapping[str, Any]) -> str:
    fields = [snapshot.get("url"), snapshot.get("title"), snapshot.get("text")]
    for item in snapshot.get("inputs") or []:
        if isinstance(item, Mapping):
            fields.extend(item.get(key) for key in ("name", "id", "type", "autocomplete", "aria", "inputmode"))
    for item in snapshot.get("forms") or []:
        if isinstance(item, Mapping):
            fields.extend(item.get(key) for key in ("action", "method"))
    for item in snapshot.get("buttons") or []:
        if isinstance(item, Mapping):
            fields.extend(item.get(key) for key in ("text", "name", "value", "aria", "action"))
    return " ".join(str(value or "") for value in fields).lower()


def classify_page(snapshot: Mapping[str, Any] | None, *, access_token: bool = False) -> PageState:
    """Classify a page from URL plus actual visible form signals.

    URL markers are preferred when present, but a stale SPA URL is not enough
    to call a password page.  Login/create intent and autocomplete are used to
    disambiguate otherwise identical password inputs.
    """
    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    text = _text(snapshot)
    url = str(snapshot.get("url") or "").lower()
    if access_token or snapshot.get("accessToken"):
        return PageState.AUTHENTICATED
    if any(marker in url for marker in ("/auth/error", "oauth_error", "callback_error")):
        return PageState.AUTH_ERROR
    if any(marker in text for marker in (
        "callback error", "oauth error", "authentication error", "auth_error", "logged_out",
        "登录失败", "认证失败",
    )):
        return PageState.AUTH_ERROR
    if any(marker in text for marker in (
        "email verified", "email verification complete", "邮箱已验证", "邮箱验证完成", "認証が完了",
    )):
        return PageState.EMAIL_VERIFIED
    if any(marker in url for marker in ("/auth/logout", "/logged-out", "/session-ended")):
        return PageState.LOGGED_OUT

    inputs = [item for item in snapshot.get("inputs") or [] if isinstance(item, Mapping) and item.get("visible", True)]
    password_inputs = [item for item in inputs if (
        str(item.get("type") or "").lower() == "password"
        or "password" in str(item.get("name") or "").lower()
        or "password" in str(item.get("id") or "").lower()
    )]
    forms = " ".join(str(item.get("action") or "").lower() for item in snapshot.get("forms") or [] if isinstance(item, Mapping))
    password_context = url + " " + text + " " + forms
    login_marker = any(marker in password_context for marker in (
        "/log-in/password", "login/password", "current-password", "sign in", "登录密码",
    ))
    create_marker = any(marker in password_context for marker in (
        "/create-account/password", "/signup/password", "new-password", "create password", "设置密码", "注册密码",
    ))
    # A current-password field or an explicit sign-in form is stronger than a
    # stale SPA URL left over from the previous route.
    login_form_marker = any(marker in forms for marker in ("/login", "/log-in", "signin", "sign-in"))
    create_form_marker = any(marker in forms for marker in ("create_account", "create-account", "/signup", "sign-up"))
    if password_inputs and (login_marker or login_form_marker) and (
        "current-password" in password_context
        or "/log-in/password" in password_context
        or "sign in" in password_context
        or login_form_marker
    ):
        return PageState.PASSWORD_LOGIN
    if password_inputs and (create_marker or create_form_marker):
        return PageState.PASSWORD_CREATE

    email_verification_route = "email-verification" in url
    totp_attrs = " ".join(
        " ".join(str(item.get(key) or "") for key in ("name", "id", "autocomplete", "inputmode"))
        for item in inputs
    ).lower()
    totp_marker = any(marker in text or marker in totp_attrs for marker in (
        "authenticator", "totp", "multi-factor", "multifactor", "two-factor", "2fa",
        "身份验证器", "验证器", "二次验证",
    ))
    if not email_verification_route and totp_marker:
        return PageState.MFA_TOTP
    if email_verification_route or any(
        marker in text for marker in ("one-time-code", "otp", "verification code", "验证码", "認証コード")
    ):
        return PageState.OTP_EMAIL
    if any(marker in url for marker in ("about-you", "/profile", "signup/profile", "create-account/profile")):
        return PageState.PROFILE
    if any("@" in str(item.get("value") or "") for item in inputs if isinstance(item, Mapping)) and not password_inputs:
        return PageState.EMAIL_FORM
    if "auth.openai.com" in url and not snapshot.get("inputs"):
        return PageState.AUTH_TRANSIENT
    return PageState.UNKNOWN


def can_resend_otp(state: PageState, *, email_verified: bool = False) -> bool:
    """Resend is valid only on an active OTP page that is not already verified."""
    return PageState(state) == PageState.OTP_EMAIL and not email_verified


def run_with_budget(
    budget: StageBudget,
    primary: Callable[[StageBudget], Any],
    *,
    protocol_assist: Callable[[StageBudget], Any] | None = None,
    roxy_fallback: Callable[[StageBudget], Any] | None = None,
) -> Any:
    """Run primary then optional assist/fallback without resetting the deadline."""
    last_error: Exception | None = None
    for action in (primary, protocol_assist, roxy_fallback):
        if action is None:
            continue
        try:
            budget.require("registration stage")
            result = action(budget)
            if result is not None:
                return result
        except StageTimeout:
            raise
        except Exception as exc:
            last_error = exc
    budget.require("registration stage")
    if last_error is not None:
        raise last_error
    raise FlowStateError("registration stage has no action")


__all__ = [
    "FlowStateError",
    "PageState",
    "RegistrationStateMachine",
    "StageBudget",
    "StageTimeout",
    "can_resend_otp",
    "classify_page",
    "run_with_budget",
]
