"""账号邮箱验证码重登必须复用共享提交，并继续消耗原总预算。"""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import roxy_codex_oauth as oauth
from core.registration import email_otp
from core.registration import roxy as registration_roxy
from core.registration.auth_context import current_execution_context
from core.registration.browser_submission import record_browser_submission_fact
from core.registration.state_machine import StageTimeout


class AccountLoginOtpRestartTests(unittest.TestCase):
    @contextmanager
    def context(self):
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login", get=Mock())
        tick = [0.0]
        mocks = {}
        with ExitStack() as stack:
            for name in ("check_cancelled", "report_stage", "human_delay", "_maybe_accept", "_wait_for_otp_input",
                         "_clear_otp_inputs", "_type_otp", "_install_email_otp_validate_hook"):
                mocks[name] = stack.enter_context(patch.object(oauth, name))
            stack.enter_context(patch.object(oauth.time, "monotonic", side_effect=lambda: tick[0]))
            stack.enter_context(patch.object(oauth.time, "time", side_effect=lambda: 1000.0 + tick[0]))
            stack.enter_context(patch.object(oauth, "_configured_email_otp_budget", return_value=240))
            stack.enter_context(patch.object(oauth, "_select_existing_account_if_present", return_value=False))
            stack.enter_context(patch.object(oauth, "_account_login_credentials", return_value=("saved-password", "")))
            stack.enter_context(patch.object(oauth, "_login_challenge_state", return_value={"url": driver.current_url}))
            for name in ("_is_login_password_page", "_is_totp_login_page", "_is_email_verification_page", "_is_login_advanced"):
                stack.enter_context(patch.object(oauth, name, return_value=False))
            mocks["navigate"] = stack.enter_context(patch.object(oauth, "_safe_get"))
            mocks["legacy_type"] = stack.enter_context(patch.object(oauth, "_type_email_address", side_effect=AssertionError("重登不得绕过共享邮箱流程")))
            mocks["legacy_submit"] = stack.enter_context(patch.object(oauth, "_submit_email_step", side_effect=AssertionError("重登不得直接提交旧邮箱表单")))
            mocks["email"] = stack.enter_context(patch.object(email_otp, "_submit_email_and_wait_next", return_value="otp"))
            mocks["challenge"] = stack.enter_context(patch.object(oauth, "complete_openai_login_challenge", side_effect=["email_otp", "advanced"]))
            mocks["wait"] = stack.enter_context(patch.object(oauth, "_wait_for_fresh_email_otp", return_value="unit-code"))
            mocks["click"] = stack.enter_context(patch.object(oauth, "_click_if_present", return_value=True))
            mocks["prepare"] = stack.enter_context(patch.object(registration_roxy, "_prepare_email_otp_current_form"))
            mocks["form_submit"] = stack.enter_context(patch.object(registration_roxy, "_submit_email_otp_current_form", return_value={"clicked": True}))
            mocks["_type_otp"].side_effect = lambda current, _code, **kwargs: kwargs["before_input"]([Mock()])
            mocks["outcome"] = stack.enter_context(patch.object(oauth, "_wait_after_email_otp_submit", return_value="invalid"))
            yield driver, tick, mocks

    def run_login(self, driver):
        oauth._fill_email_and_otp(driver, "unit@example.test", Mock(), "https://chatgpt.com/auth/login")

    def test_failed_code_relogin_uses_shared_email_flow_and_original_deadline(self):
        with self.context() as (driver, tick, mocks):
            def after_submit(*_args, **_kwargs):
                tick[0] = 80
                return "invalid"
            mocks["outcome"].side_effect = after_submit
            observed = []
            def shared_email(*_args, **kwargs):
                if mocks["email"].call_count == 2:
                    observed.append((kwargs, current_execution_context()))
                return "otp"
            mocks["email"].side_effect = shared_email
            self.run_login(driver)
            self.assertEqual(mocks["email"].call_count, 2)
            kwargs, context = observed[0]
            self.assertTrue(kwargs["allow_login_password"])
            self.assertLessEqual(kwargs["total_timeout"], 160)
            self.assertEqual(context.deadline, 240)
            self.assertEqual(mocks["challenge"].call_args.args[2], "saved-password")
            self.assertLessEqual(mocks["challenge"].call_args.kwargs["timeout"], 160)
            self.assertEqual(driver._registration_otp_after_ts, 1080)
            mocks["legacy_type"].assert_not_called()
            mocks["legacy_submit"].assert_not_called()
            driver.get.assert_not_called()
            mocks["_type_otp"].assert_called_once()
            mocks["click"].assert_not_called()
            self.assertTrue(mocks["prepare"].call_args.kwargs["capture_responses"])

    def test_exhausted_original_budget_cannot_start_another_email_login(self):
        with self.context() as (driver, tick, mocks):
            def wait_timeout(*_args, **_kwargs):
                tick[0] = 240
                raise TimeoutError("本轮未收到验证码")
            mocks["wait"].side_effect = wait_timeout
            with self.assertRaisesRegex(RuntimeError, "预算"):
                self.run_login(driver)
            mocks["email"].assert_called_once()
            mocks["navigate"].assert_called_once()
            driver.get.assert_not_called()

    def test_unconfirmed_otp_keeps_receipt_and_does_not_restart_or_retype(self):
        with self.context() as (driver, _tick, mocks):
            mocks["outcome"].return_value = "stuck"
            with self.assertRaisesRegex(email_otp._EmailSubmissionUnknown, "otp_request_unconfirmed"):
                self.run_login(driver)
            self.assertEqual(driver._browser_submission_receipt.phase, "unknown")
            mocks["email"].assert_called_once()
            mocks["navigate"].assert_called_once()
            mocks["_type_otp"].assert_called_once()
            mocks["form_submit"].assert_called_once()
            mocks["click"].assert_not_called()
            driver.get.assert_not_called()

    def test_request_observation_is_prepared_before_code_input(self):
        with self.context() as (driver, _tick, mocks):
            mocks["outcome"].return_value = "accepted"
            observed = []
            def prepare(current, _inputs, **kwargs):
                observed.append((current._browser_submission_receipt.phase, kwargs["capture_responses"]))
                self.assertEqual(mocks["form_submit"].call_count, 0)
            mocks["prepare"].side_effect = prepare
            self.run_login(driver)
            self.assertEqual(observed, [("dispatch_intent", True)])
            self.assertEqual(driver._browser_submission_receipt.phase, "confirmed")

    def test_stage_timeout_after_dispatch_intent_preserves_unknown_without_replay(self):
        for timeout_at in ("typing", "before_submit", "after_submit"):
            with self.subTest(timeout_at=timeout_at), self.context() as (driver, tick, mocks):
                if timeout_at == "typing":
                    mocks["_type_otp"].side_effect = StageTimeout("输入时已可能自动提交")
                elif timeout_at == "before_submit":
                    def delay(kind, *_args, **_kwargs):
                        if kind == "otp_input":
                            tick[0] = 240
                    mocks["human_delay"].side_effect = delay
                else:
                    def submit(*_args, **_kwargs):
                        tick[0] = 240
                        return {"clicked": True}
                    mocks["form_submit"].side_effect = submit

                with self.assertRaisesRegex(email_otp._EmailSubmissionUnknown, "otp_request_unconfirmed"):
                    self.run_login(driver)

                self.assertEqual(driver._browser_submission_receipt.phase, "unknown")
                self.assertEqual(driver._browser_submission_receipt.error_type, "StageTimeout")
                mocks["email"].assert_called_once()
                mocks["navigate"].assert_called_once()
                mocks["_type_otp"].assert_called_once()
                self.assertEqual(mocks["form_submit"].call_count, int(timeout_at == "after_submit"))
                mocks["outcome"].assert_not_called()

    def test_explicit_not_dispatched_form_timeout_stays_cancelled(self):
        with self.context() as (driver, _tick, mocks):
            def prepare(current, _inputs, **_kwargs):
                record_browser_submission_fact(current, "not_dispatched", result="cancelled")
                raise StageTimeout("输入前表单已确认不可提交")
            mocks["prepare"].side_effect = prepare

            with self.assertRaises(StageTimeout):
                self.run_login(driver)

            self.assertEqual(driver._browser_submission_receipt.phase, "not_dispatched")
            self.assertEqual(driver._browser_submission_receipt.result, "cancelled")
            mocks["form_submit"].assert_not_called()
            mocks["outcome"].assert_not_called()

    def test_timeout_before_otp_dispatch_does_not_create_unknown_receipt(self):
        with self.context() as (driver, _tick, mocks):
            mocks["_wait_for_otp_input"].side_effect = StageTimeout("输入框等待预算已耗尽")

            with self.assertRaises(StageTimeout):
                self.run_login(driver)

            self.assertFalse(hasattr(driver, "_browser_submission_receipt"))
            mocks["_type_otp"].assert_not_called()
            mocks["form_submit"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
