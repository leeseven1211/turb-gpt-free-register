# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch

from core import roxy_registration


class _FakeDriver:
    def __init__(self):
        self.current_url = "https://chatgpt.com/auth/login"
        self.refresh_count = 0

    def refresh(self):
        self.refresh_count += 1

    def execute_script(self, *_args):
        return False


class RoxyEmailRecoveryTests(unittest.TestCase):
    def test_type_otp_waits_for_delayed_input(self):
        field = Mock()
        field.is_displayed.return_value = True
        field.is_enabled.return_value = True

        class DelayedOtpDriver(_FakeDriver):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def find_elements(self, *_args):
                self.calls += 1
                return [field] if self.calls == 6 else []

        driver = DelayedOtpDriver()
        with patch.object(
            roxy_registration.time, "monotonic", side_effect=[100.0, 100.0, 101.0]
        ), patch.object(roxy_registration.time, "sleep"), patch.object(
            roxy_registration, "_human_type_text"
        ) as type_text:
            roxy_registration._type_otp(driver, "123456", timeout=2)

        type_text.assert_called_once_with(driver, field, "123456", clear=True)

    def test_blank_auth_shell_uses_logged_dom_state_as_fallback(self):
        driver = _FakeDriver()
        state = {
            "url": "https://chatgpt.com/auth/login",
            "title": "Get started | ChatGPT",
            "inputs": [],
            "actions": [
                {"attrs": "/?slm=1", "tag": "A", "type": ""},
                {"attrs": "dismiss-welcome #", "tag": "A", "type": ""},
            ],
        }

        self.assertTrue(roxy_registration._is_blank_chatgpt_auth_shell(driver, state))

    def test_submit_wait_returns_blank_shell_without_waiting_for_timeout(self):
        driver = _FakeDriver()
        with patch.object(roxy_registration, "_has_access_token", return_value=False), patch.object(
            roxy_registration, "_is_login_password_page", return_value=False
        ), patch.object(roxy_registration, "_is_email_verification_page", return_value=False), patch.object(
            roxy_registration, "_is_signup_password_page", return_value=False
        ), patch.object(
            roxy_registration,
            "_email_input_value_state",
            return_value={"url": driver.current_url, "inputs": []},
        ), patch.object(roxy_registration, "_is_blank_chatgpt_auth_shell", return_value=True):
            result = roxy_registration._wait_email_submit_next_state(driver, "test@example.com", timeout=20)

        self.assertEqual(result, "blank_shell")

    def test_submit_wait_ignores_transient_shell_until_otp_arrives(self):
        driver = _FakeDriver()
        with patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            side_effect=[None, "otp"],
        ), patch.object(
            roxy_registration,
            "_email_input_value_state",
            return_value={"url": driver.current_url, "inputs": []},
        ), patch.object(
            roxy_registration,
            "_is_blank_chatgpt_auth_shell",
            return_value=True,
        ), patch.object(roxy_registration.time, "sleep"):
            result = roxy_registration._wait_email_submit_next_state(
                driver,
                "test@example.com",
                timeout=20,
                wait_through_transient=True,
            )

        self.assertEqual(result, "otp")

    def test_submit_settle_does_not_resubmit_cleared_email_form(self):
        driver = _FakeDriver()
        fake_time = Mock()
        fake_time.time.side_effect = [100.0, 100.0, 103.0, 104.0, 106.0, 107.0]
        cleared_state = {
            "url": "https://chatgpt.com/auth/login?email=test%40example.com",
            "inputs": [{"value": ""}],
        }
        with patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            side_effect=[None, None, "otp"],
        ), patch.object(
            roxy_registration,
            "_email_input_value_state",
            return_value=cleared_state,
        ), patch.object(
            roxy_registration,
            "_is_blank_chatgpt_auth_shell",
            return_value=False,
        ), patch.object(
            roxy_registration,
            "_recover_email_submit_if_stuck",
        ) as recover, patch.object(roxy_registration, "time", fake_time):
            result = roxy_registration._wait_email_submit_next_state(
                driver,
                "test@example.com",
                timeout=20,
                wait_through_transient=True,
            )

        self.assertEqual(result, "otp")
        recover.assert_not_called()

    def test_stuck_email_page_uses_nextauth_fallback(self):
        driver = _FakeDriver()
        email_state = {
            "url": "https://chatgpt.com/auth/login?email=test%40example.com",
            "inputs": [{"value": "test@example.com"}],
        }
        with patch.object(roxy_registration, "_type_email_address"), patch.object(
            roxy_registration, "_email_input_value_state", return_value=email_state
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration, "_submit_email_step"
        ), patch.object(
            roxy_registration,
            "_wait_email_submit_next_state",
            side_effect=["email_page", "otp"],
        ), patch.object(
            roxy_registration,
            "_submit_email_via_browser_nextauth",
            return_value={"ok": True, "stage": "redirected"},
        ) as nextauth:
            result = roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

        self.assertEqual(result, "otp")
        nextauth.assert_called_once_with(driver, "test@example.com")

    def test_first_blank_shell_switches_to_nextauth_without_reload(self):
        driver = _FakeDriver()
        email_state = {
            "url": "https://chatgpt.com/auth/login",
            "inputs": [{"value": "test@example.com"}],
        }
        with patch.object(roxy_registration, "_type_email_address"), patch.object(
            roxy_registration, "_email_input_value_state", return_value=email_state
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration, "_submit_email_step"
        ), patch.object(
            roxy_registration,
            "_wait_email_submit_next_state",
            side_effect=["blank_shell", "otp"],
        ), patch.object(
            roxy_registration,
            "_log_blank_auth_shell_diagnostics",
        ), patch.object(roxy_registration, "_reload_blank_chatgpt_auth_shell") as reload_shell, patch.object(
            roxy_registration,
            "_submit_email_via_browser_nextauth",
            return_value={"ok": True, "stage": "redirected"},
        ) as nextauth:
            result = roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

        self.assertEqual(result, "otp")
        reload_shell.assert_not_called()
        nextauth.assert_called_once_with(driver, "test@example.com")

    def test_nextauth_fallback_accepts_otp_that_arrived_during_race(self):
        driver = _FakeDriver()
        email_state = {
            "url": "https://chatgpt.com/auth/login",
            "inputs": [{"value": "test@example.com"}],
        }
        with patch.object(roxy_registration, "_type_email_address"), patch.object(
            roxy_registration, "_email_input_value_state", return_value=email_state
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration, "_submit_email_step"
        ), patch.object(
            roxy_registration,
            "_wait_email_submit_next_state",
            return_value="blank_shell",
        ) as wait_next, patch.object(
            roxy_registration,
            "_log_blank_auth_shell_diagnostics",
        ), patch.object(
            roxy_registration,
            "_submit_email_via_browser_nextauth",
            return_value={"ok": True, "stage": "already_advanced", "state": "otp"},
        ):
            result = roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

        self.assertEqual(result, "otp")
        wait_next.assert_called_once_with(driver, "test@example.com", timeout=20)

    def test_retry_stops_when_page_reaches_otp_before_email_refill(self):
        driver = _FakeDriver()
        with patch.object(
            roxy_registration,
            "_type_email_address",
            return_value="otp",
        ) as type_email, patch.object(
            roxy_registration,
            "_submit_email_step",
        ) as submit_email:
            result = roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

        self.assertEqual(result, "otp")
        type_email.assert_called_once_with(
            driver,
            "test@example.com",
            timeout=20,
            stop_on_advanced=True,
        )
        submit_email.assert_not_called()

    def test_new_registration_rejects_existing_login_password_page(self):
        driver = _FakeDriver()
        driver.current_url = "https://auth.openai.com/log-in/password"
        with patch.object(
            roxy_registration,
            "_type_email_address",
            return_value="login_password",
        ):
            with self.assertRaisesRegex(RuntimeError, "已注册/不可用邮箱"):
                roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

    def test_pending_account_resume_accepts_login_password_page(self):
        driver = _FakeDriver()
        driver.current_url = "https://auth.openai.com/log-in/password"
        with patch.object(
            roxy_registration,
            "_type_email_address",
            return_value="login_password",
        ):
            result = roxy_registration._submit_email_and_wait_next(
                driver,
                "test@example.com",
                allow_login_password=True,
            )

        self.assertEqual(result, "login_password")

    def test_nextauth_skips_navigation_when_page_already_reached_otp(self):
        driver = _FakeDriver()
        driver.current_url = "https://auth.openai.com/email-verification"
        with patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            return_value="otp",
        ):
            result = roxy_registration._submit_email_via_browser_nextauth(
                driver,
                "test@example.com",
            )

        self.assertEqual(result["state"], "otp")
        self.assertEqual(result["stage"], "already_advanced")
        self.assertTrue(result["ok"])

    def test_nextauth_does_not_treat_chatgpt_login_as_final_landing(self):
        driver = _FakeDriver()
        driver.set_script_timeout = lambda _timeout: None
        driver.execute_async_script = lambda *_args: {
            "ok": True,
            "url": "https://chatgpt.com/api/auth/signin?csrf=true",
        }

        def _land_back_on_login(current_driver, *_args, **_kwargs):
            current_driver.current_url = "https://chatgpt.com/auth/login?callbackUrl=https%3A%2F%2Fchatgpt.com%2F"

        with patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            return_value=None,
        ), patch.object(
            roxy_registration,
            "_safe_get",
            side_effect=_land_back_on_login,
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration,
            "_page_warmup",
        ):
            result = roxy_registration._submit_email_via_browser_nextauth(
                driver,
                "test@example.com",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "redirect_not_landed")
        self.assertEqual(result["url"], "https://chatgpt.com/auth/login")
        self.assertEqual(result["target_url"], "https://chatgpt.com/api/auth/signin")

    def test_submit_callback_runs_once_when_ui_is_retried(self):
        driver = _FakeDriver()
        email_state = {
            "url": "https://chatgpt.com/auth/login?email=test%40example.com",
            "inputs": [{"value": "test@example.com"}],
        }
        submitted = []
        with patch.object(roxy_registration, "_type_email_address"), patch.object(
            roxy_registration, "_email_input_value_state", return_value=email_state
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration, "_submit_email_step"
        ), patch.object(
            roxy_registration,
            "_wait_email_submit_next_state",
            side_effect=["email_page", "otp"],
        ), patch.object(
            roxy_registration,
            "_submit_email_via_browser_nextauth",
            return_value={"ok": False, "stage": "signin"},
        ):
            result = roxy_registration._submit_email_and_wait_next(
                driver,
                "test@example.com",
                on_submitted=lambda: submitted.append(True),
            )

        self.assertEqual(result, "otp")
        self.assertEqual(submitted, [True])

    def test_missing_email_form_reloads_blank_auth_shell_once(self):
        driver = _FakeDriver()
        email_input = object()

        with patch.object(
            roxy_registration,
            "_find_visible_email_input_js",
            side_effect=[None, email_input],
        ), patch.object(
            roxy_registration,
            "_email_entry_state",
            return_value={"url": driver.current_url, "inputs": [], "actions": []},
        ), patch.object(
            roxy_registration,
            "_is_blank_chatgpt_auth_shell",
            side_effect=[True, True, False],
        ), patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            return_value=None,
        ), patch.object(
            roxy_registration,
            "_click_email_entry_option",
            return_value=False,
        ), patch.object(
            roxy_registration,
            "_page_warmup",
        ) as page_warmup, patch.object(
            roxy_registration,
            "human_delay",
        ), patch.object(
            roxy_registration,
            "_human_type_text",
        ) as type_text:
            roxy_registration._type_email_address(driver, "test@example.com", timeout=2)

        self.assertEqual(driver.refresh_count, 1)
        page_warmup.assert_called_once_with(driver, reason="reload_blank_auth_shell")
        type_text.assert_called_once_with(driver, email_input, "test@example.com", clear=True)

    def test_otp_submit_timeout_is_stuck_not_accepted(self):
        driver = _FakeDriver()
        with patch.object(
            roxy_registration, "_is_email_verification_page", return_value=True
        ), patch.object(
            roxy_registration,
            "_email_otp_page_state",
            return_value={"inputs": [], "errors": []},
        ):
            outcome = roxy_registration._wait_after_email_otp_submit(driver, timeout=0)

        self.assertEqual(outcome, "stuck")

    def test_otp_submit_timeout_with_error_is_invalid(self):
        driver = _FakeDriver()
        with patch.object(
            roxy_registration, "_is_email_verification_page", return_value=True
        ), patch.object(
            roxy_registration,
            "_email_otp_page_state",
            return_value={"inputs": [{"ariaInvalid": "true"}], "errors": []},
        ):
            outcome = roxy_registration._wait_after_email_otp_submit(driver, timeout=0)

        self.assertEqual(outcome, "invalid")


if __name__ == "__main__":
    unittest.main()
