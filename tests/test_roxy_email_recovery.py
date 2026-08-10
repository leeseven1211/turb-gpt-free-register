# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

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

    def test_repeated_blank_shell_switches_to_nextauth_fallback(self):
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
            side_effect=["blank_shell", "blank_shell", "otp"],
        ), patch.object(roxy_registration, "_reload_blank_chatgpt_auth_shell") as reload_shell, patch.object(
            roxy_registration,
            "_submit_email_via_browser_nextauth",
            return_value={"ok": True, "stage": "redirected"},
        ) as nextauth:
            result = roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

        self.assertEqual(result, "otp")
        self.assertEqual(reload_shell.call_count, 2)
        nextauth.assert_called_once_with(driver, "test@example.com")

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
            side_effect=[True, False],
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


if __name__ == "__main__":
    unittest.main()
