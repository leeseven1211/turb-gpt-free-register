"""Browser Use/Skyvern 登录、OTP 和基础页面能力的公开边界。"""
from __future__ import annotations

from typing import Any, Callable

__all__ = [
    "timeout_ms",
    "page_url",
    "fill_first",
    "click_first",
    "maybe_accept_cookies",
    "type_otp",
    "clear_otp_inputs",
    "wait_after_otp",
    "click_passwordless_signup_if_present",
]


def _legacy(name: str) -> Callable[..., Any]:
    """Resolve a legacy implementation lazily to avoid registration import cycles."""
    from core import browser_use_registration

    return getattr(browser_use_registration, name)


def timeout_ms(seconds: int | None = None) -> int:
    return _legacy("_timeout_ms")(seconds)


def page_url(page: Any) -> str:
    return _legacy("_page_url")(page)


def fill_first(page: Any, selectors: list[str], value: str, **kwargs: Any) -> bool:
    return _legacy("_fill_first")(page, selectors, value, **kwargs)


def click_first(page: Any, selectors: list[str], **kwargs: Any) -> bool:
    return _legacy("_click_first")(page, selectors, **kwargs)


def maybe_accept_cookies(page: Any) -> None:
    return _legacy("_maybe_accept_cookies")(page)


def type_otp(page: Any, code: str) -> None:
    return _legacy("_type_otp")(page, code)


def clear_otp_inputs(page: Any) -> None:
    return _legacy("_clear_otp_inputs")(page)


def wait_after_otp(page: Any, timeout: int = 12) -> str:
    return _legacy("_wait_after_otp")(page, timeout)


def click_passwordless_signup_if_present(page: Any) -> bool:
    return _legacy("_click_passwordless_signup_if_present")(page)
