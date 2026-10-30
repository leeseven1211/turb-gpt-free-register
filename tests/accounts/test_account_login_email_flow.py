"""账号补全登录必须等待真实邮箱跳转，不能吞掉未提交错误。"""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.codex.roxy import oauth as oauth
from core.auth.browser import email_otp


class AccountLoginEmailFlowTests(unittest.TestCase):
    def _context(self, driver):
        stack = ExitStack()
        for name in ("check_cancelled", "report_stage", "human_delay", "_safe_get", "_maybe_accept"):
            stack.enter_context(patch.object(oauth, name))
        stack.enter_context(patch.object(oauth, "_select_existing_account_if_present", return_value=False))
        stack.enter_context(patch.object(oauth, "_account_login_credentials", return_value=("saved-password", "")))
        stack.enter_context(patch.object(oauth, "_login_challenge_state", return_value={"url": driver.current_url}))
        for name in ("_is_login_password_page", "_is_totp_login_page", "_is_email_verification_page", "_is_login_advanced"):
            stack.enter_context(patch.object(oauth, name, return_value=False))
        return stack

    def test_account_login_reuses_bounded_registration_email_flow(self):
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login")
        events = []
        with self._context(driver) as stack:
            flow = stack.enter_context(patch.object(email_otp, "_submit_email_and_wait_next", return_value="login_password"))
            typed = stack.enter_context(patch.object(oauth, "_type_email_address"))
            submit = stack.enter_context(patch.object(oauth, "_submit_email_step"))
            resolve = stack.enter_context(patch.object(oauth, "complete_openai_login_challenge", return_value="advanced"))
            oauth._fill_email_and_otp(driver, "unit@example.test", Mock(), driver.current_url,
                                      stage_reporter=lambda **event: events.append(event))
        flow.assert_called_once()
        self.assertIs(flow.call_args.args[0], driver)
        self.assertTrue(flow.call_args.kwargs["allow_login_password"])
        self.assertTrue(callable(flow.call_args.kwargs["on_progress"]))
        typed.assert_not_called()
        submit.assert_not_called()
        resolve.assert_called_once()
        self.assertTrue(any(event["state"] == "success" for event in events))

    def test_failed_account_email_flow_does_not_report_submission_or_continue_to_session(self):
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login")
        events = []
        error = email_otp._EmailFrontendNotReady("email_frontend_not_ready")
        with self._context(driver) as stack:
            stack.enter_context(patch.object(email_otp, "_submit_email_and_wait_next", side_effect=error))
            stack.enter_context(patch.object(oauth, "_type_email_address", side_effect=error))
            resolve = stack.enter_context(patch.object(oauth, "complete_openai_login_challenge"))
            with self.assertRaises(email_otp._EmailFrontendNotReady):
                oauth._fill_email_and_otp(driver, "unit@example.test", Mock(), driver.current_url,
                                          stage_reporter=lambda **event: events.append(event))
        resolve.assert_not_called()
        self.assertFalse(any(event["state"] == "success" for event in events))

    def test_oauth_email_preparation_error_is_preserved_when_page_has_not_advanced(self):
        driver = SimpleNamespace(current_url="https://auth.openai.com/log-in")
        error = email_otp._EmailFrontendNotReady("email_frontend_not_ready")
        with self._context(driver) as stack:
            stack.enter_context(patch.object(oauth, "_type_email_address"))
            stack.enter_context(patch.object(oauth, "_submit_email_step", side_effect=error))
            resolve = stack.enter_context(patch.object(oauth, "complete_openai_login_challenge"))
            with self.assertRaises(email_otp._EmailFrontendNotReady):
                oauth._fill_email_and_otp(driver, "unit@example.test", Mock(),
                                          "https://auth.openai.com/oauth/authorize")
        resolve.assert_not_called()
