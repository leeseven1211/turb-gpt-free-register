"""Selenium 登录、OTP、资料和 ChatGPT session 能力的公开边界。

实现位于同领域包的 :mod:`core.registration.roxy`；本模块负责隔离注册、查活和
Codex 调用方与具体驱动实现的私有函数名。
"""
from __future__ import annotations

from typing import Any, Callable

__all__ = [
    "build_driver",
    "center_browser_window",
    "safe_get",
    "page_warmup",
    "find_any",
    "click_any",
    "type_any",
    "human_click",
    "human_type_text",
    "click_email_entry_option",
    "type_email_address",
    "submit_email_step",
    "recover_email_submit_if_stuck",
    "submit_email_via_browser_nextauth",
    "submit_email_and_wait_next",
    "wait_email_submit_next_state",
    "type_otp",
    "email_otp_page_state",
    "clear_otp_inputs",
    "click_resend_email_otp",
    "wait_after_email_otp_submit",
    "click_continue",
    "maybe_accept",
    "has_access_token",
    "is_email_verification_page",
    "is_login_password_page",
    "click_passwordless_signup_if_present",
    "fill_password_page_if_present",
    "complete_profile_page",
    "fetch_chatgpt_session",
    "check_manual_stop",
    "registration_password",
    "set_login_password",
    "setup_roxy_2fa",
]


def _legacy(name: str) -> Callable[..., Any]:
    """Resolve a legacy implementation lazily to avoid registration import cycles."""
    from core.registration import roxy

    return getattr(roxy, name)


def build_driver(opened: Any) -> Any:
    return _legacy("_build_driver")(opened)


def center_browser_window(driver: Any) -> None:
    return _legacy("_center_browser_window")(driver)


def safe_get(driver: Any, url: str, **kwargs: Any) -> None:
    return _legacy("_safe_get")(driver, url, **kwargs)


def page_warmup(driver: Any, **kwargs: Any) -> None:
    return _legacy("_page_warmup")(driver, **kwargs)


def find_any(driver: Any, selectors: list[str], **kwargs: Any) -> Any:
    return _legacy("_find_any")(driver, selectors, **kwargs)


def click_any(driver: Any, selectors: list[str], **kwargs: Any) -> None:
    return _legacy("_click_any")(driver, selectors, **kwargs)


def type_any(driver: Any, selectors: list[str], value: str, **kwargs: Any) -> None:
    return _legacy("_type_any")(driver, selectors, value, **kwargs)


def human_click(driver: Any, element: Any, **kwargs: Any) -> None:
    return _legacy("_human_click")(driver, element, **kwargs)


def human_type_text(driver: Any, element: Any, value: str, **kwargs: Any) -> None:
    return _legacy("_human_type_text")(driver, element, value, **kwargs)


def click_email_entry_option(driver: Any) -> bool:
    return _legacy("_click_email_entry_option")(driver)


def type_email_address(driver: Any, email: str, **kwargs: Any) -> None:
    return _legacy("_type_email_address")(driver, email, **kwargs)


def submit_email_step(driver: Any, email: str | None = None) -> None:
    return _legacy("_submit_email_step")(driver, email)


def recover_email_submit_if_stuck(driver: Any, email: str) -> dict:
    return _legacy("_recover_email_submit_if_stuck")(driver, email)


def submit_email_via_browser_nextauth(driver: Any, email: str) -> dict:
    return _legacy("_submit_email_via_browser_nextauth")(driver, email)


def submit_email_and_wait_next(driver: Any, email: str, **kwargs: Any) -> str:
    return _legacy("_submit_email_and_wait_next")(driver, email, **kwargs)


def wait_email_submit_next_state(driver: Any, email: str, **kwargs: Any) -> str:
    return _legacy("_wait_email_submit_next_state")(driver, email, **kwargs)


def type_otp(driver: Any, code: str, **kwargs: Any) -> None:
    return _legacy("_type_otp")(driver, code, **kwargs)


def email_otp_page_state(driver: Any) -> dict:
    return _legacy("_email_otp_page_state")(driver)


def clear_otp_inputs(driver: Any) -> None:
    return _legacy("_clear_otp_inputs")(driver)


def click_resend_email_otp(driver: Any, **kwargs: Any) -> dict:
    return _legacy("_click_resend_email_otp")(driver, **kwargs)


def wait_after_email_otp_submit(driver: Any, **kwargs: Any) -> str:
    return _legacy("_wait_after_email_otp_submit")(driver, **kwargs)


def click_continue(driver: Any) -> None:
    return _legacy("_click_continue")(driver)


def maybe_accept(driver: Any) -> None:
    return _legacy("_maybe_accept")(driver)


def has_access_token(driver: Any) -> bool:
    return _legacy("_has_access_token")(driver)


def is_email_verification_page(driver: Any) -> bool:
    return _legacy("_is_email_verification_page")(driver)


def is_login_password_page(driver: Any) -> bool:
    return _legacy("_is_login_password_page")(driver)


def click_passwordless_signup_if_present(driver: Any) -> dict:
    return _legacy("_click_passwordless_signup_if_present")(driver)


def fill_password_page_if_present(driver: Any, email: str, **kwargs: Any) -> str | None:
    return _legacy("_fill_password_page_if_present")(driver, email, **kwargs)


def complete_profile_page(driver: Any, name: str, birthday: str, **kwargs: Any) -> bool:
    return _legacy("_complete_profile_page")(driver, name, birthday, **kwargs)


def fetch_chatgpt_session(driver: Any, **kwargs: Any) -> dict:
    return _legacy("_fetch_chatgpt_session")(driver, **kwargs)


def check_manual_stop() -> None:
    return _legacy("_check_manual_stop")()


def registration_password() -> str:
    return _legacy("_registration_password")()


def set_login_password(driver: Any, email: str, password: str, **kwargs: Any) -> str:
    return _legacy("set_roxy_login_password")(driver, email, password, **kwargs)


def setup_roxy_2fa(driver: Any, email: str, **kwargs: Any) -> str:
    return _legacy("setup_roxy_2fa")(driver, email, **kwargs)
