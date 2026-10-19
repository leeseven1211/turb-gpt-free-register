"""开源 Roxy 页面辅助与本地注册生命周期适配。"""
from __future__ import annotations

from core.registration.roxy_oss.upstream import browser_helpers as _upstream


class RoxyOssBrowserHelpers:
    """按阶段注入固定上游的 DOM 辅助，每次调用独立收口覆盖范围。"""

    driver_name = "roxy_oss"

    def submit_email_and_wait_next(self, driver, email: str, **kwargs) -> str:
        from core.registration.roxy import _call_shared_capability

        return _call_shared_capability(
            "_submit_email_and_wait_next",
            driver,
            email,
            _helper_overrides={
                "_email_entry_state": _upstream._email_entry_state,
                "_find_visible_email_input_js": _upstream._find_visible_email_input_js,
                "_is_oauth_consent_like": _upstream._is_oauth_consent_like,
                "_click_email_entry_option": _upstream._click_email_entry_option,
            },
            **kwargs,
        )

    def complete_profile_page(self, driver, name: str, birthday: str, **kwargs) -> bool:
        from core.registration.roxy import _call_shared_capability

        return _call_shared_capability(
            "_complete_profile_page",
            driver,
            name,
            birthday,
            _helper_overrides={
                "_is_profile_like": _upstream._is_profile_like,
                "_set_element_value": _upstream._set_element_value,
                "_select_or_type": _upstream._select_or_type,
                "_fill_birthday_or_age": _upstream._fill_birthday_or_age,
                "_accept_profile_consents": _upstream._accept_profile_consents,
            },
            **kwargs,
        )


def run_roxy_oss_registration(
    email: str,
    name: str,
    birthday: str,
    proxy: str | None = None,
    otp_code: str | None = None,
    existing_password: str | None = None,
    existing_totp_secret: str | None = None,
    profile_id: str | None = None,
    registration_options: dict | None = None,
    email_source: str | None = None,
) -> dict:
    """运行开源页面辅助，沿用本地代理、密码/验证码提交、检查点和后处理。"""
    from core.registration.roxy import run_roxy_registration

    return run_roxy_registration(
        email=email,
        name=name,
        birthday=birthday,
        proxy=proxy,
        otp_code=otp_code,
        existing_password=existing_password,
        existing_totp_secret=existing_totp_secret,
        profile_id=profile_id,
        registration_options=registration_options,
        email_source=email_source,
        _browser_helpers=RoxyOssBrowserHelpers(),
    )


__all__ = ["run_roxy_oss_registration"]
