"""显式补密码可在候选被拒绝后用邮箱登录，注册和重置候选保持原约束。"""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.auth.challenge import PasswordRejectedError
from core.codex.roxy import oauth


@contextmanager
def rejected_candidate_flow(*, create_page=False):
    clock = [100.0]
    route = "/create-account/password" if create_page else "/log-in/password"
    driver = SimpleNamespace(current_url="https://auth.openai.com" + route)

    def snapshot(_driver):
        password_page = driver.current_url.endswith("password")
        return {"url": driver.current_url, "inputs": [{
            "type": "password" if password_page else "text",
            "name": "password" if password_page else "code",
            "autocomplete": "new-password" if create_page else "current-password", "visible": True,
        }], "errors": [], "buttons": []}

    def open_otp(_driver):
        driver.current_url = "https://auth.openai.com/email-verification"
        return {"ok": True}

    with ExitStack() as stack:
        for name in ("check_cancelled", "_auth_checkpoint", "human_delay", "report_stage"):
            stack.enter_context(patch.object(oauth, name))
        values = {
            "_login_challenge_state": {"side_effect": snapshot},
            "_is_totp_login_page": {"return_value": False},
            "_is_browser_error_page_state": {"return_value": False},
            "_is_terminal_auth_error_page": {"return_value": False},
            "_is_login_password_page": {"side_effect": lambda _driver: driver.current_url.endswith("/log-in/password")},
            "_is_email_verification_page": {"side_effect": lambda _driver: driver.current_url.endswith("email-verification")},
            "_is_login_advanced": {"return_value": False},
            "_has_access_token": {"return_value": False},
            "_email_ui_submission_state": {"return_value": ""},
            "_submit_saved_login_password": {"side_effect": PasswordRejectedError("候选密码被明确拒绝")},
            "_click_passwordless_signup_if_present": {"side_effect": open_otp},
            "open_offered_password_entry": {"return_value": "/log-in/password"},
            "_reset_password_via_email": {},
        }
        mocks = {name: stack.enter_context(patch.object(oauth, name, **kwargs)) for name, kwargs in values.items()}
        stack.enter_context(patch.object(oauth, "time", SimpleNamespace(
            time=lambda: clock[0], monotonic=lambda: clock[0],
            sleep=lambda duration: clock.__setitem__(0, clock[0] + duration),
        )))
        yield driver, mocks


@pytest.mark.parametrize("allow_reset", [False, True])
def test_explicit_setup_falls_back_to_real_otp_without_reset_or_retrying_password(allow_reset):
    with rejected_candidate_flow() as (driver, mocks):
        assert oauth.complete_openai_login_challenge(
            driver, "setup@example.test", "OriginalCandidate!", "", otp_provider=Mock(),
            allow_passwordless_fallback=True, allow_password_reset=allow_reset,
        ) == "email_otp"
    mocks["_submit_saved_login_password"].assert_called_once()
    mocks["_click_passwordless_signup_if_present"].assert_called_once()
    mocks["open_offered_password_entry"].assert_not_called()
    mocks["_reset_password_via_email"].assert_not_called()
    assert driver._account_passwordless_fallback_active is True


@pytest.mark.parametrize("extra", [{}, {"allow_passwordless_fallback": True, "on_candidate_password_confirmed": Mock()}])
def test_registration_and_reset_candidate_cannot_use_setup_email_fallback(extra):
    with rejected_candidate_flow() as (driver, mocks):
        with pytest.raises(PasswordRejectedError):
            oauth._complete_login_challenge_after_email(
                driver, "setup@example.test", "OriginalCandidate!", "", **extra,
            )
    mocks["_click_passwordless_signup_if_present"].assert_not_called()
    mocks["_reset_password_via_email"].assert_not_called()


def test_create_password_rejection_does_not_become_passwordless_login():
    with rejected_candidate_flow(create_page=True) as (driver, mocks):
        with pytest.raises(PasswordRejectedError):
            oauth.complete_openai_login_challenge(
                driver, "setup@example.test", "OriginalCandidate!", "", allow_passwordless_fallback=True,
            )
    mocks["_click_passwordless_signup_if_present"].assert_not_called()


def test_same_account_setup_does_not_reopen_password_after_email_branch_restart():
    with rejected_candidate_flow() as (driver, mocks):
        driver._account_passwordless_fallback_active = True
        assert oauth.complete_openai_login_challenge(
            driver, "setup@example.test", "OriginalCandidate!", "", allow_passwordless_fallback=True,
            allow_password_reset=True,
        ) == "email_otp"
    mocks["_submit_saved_login_password"].assert_not_called()
    mocks["open_offered_password_entry"].assert_not_called()
