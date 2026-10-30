"""刷新后补交原验证码，以及明确过期后重发新码的流程回归。"""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from core.registration import roxy
from core.auth.browser.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from core.auth.state_machine import StageBudget, StageTimeout


class RoxyOtpRefreshRetryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.driver = SimpleNamespace(current_url="https://auth.openai.com/email-verification")
        self.budget = StageBudget.start(240)
        self.fill = self.stack.enter_context(patch.object(roxy, "_type_otp"))
        self.stack.enter_context(patch.object(roxy, "_clear_otp_inputs"))
        self.stack.enter_context(patch.object(roxy, "_check_manual_stop"))
        self.stack.enter_context(patch.object(roxy, "human_delay"))
        self.stack.enter_context(patch.object(roxy, "log_submission_diagnostics"))
        self.stack.enter_context(patch.object(roxy, "_email_otp_page_state", return_value={"inputs": []}))
        self.submit = self.stack.enter_context(patch.object(roxy, "_submit_email_otp_current_form", return_value={"clicked": True}))
        self.wait = self.stack.enter_context(patch.object(roxy, "_wait_after_email_otp_submit"))

    def outcomes(self, *values):
        results = iter(values)

        def wait(driver, **_kwargs):
            result = next(results)
            if result in {"retry_previous_otp", "stuck"}:
                record_browser_submission_fact(driver, "unknown", result="unknown")
            return result

        self.wait.side_effect = wait

    def test_refresh_reuses_original_code_once_with_independent_receipt(self):
        self.outcomes("retry_previous_otp", "accepted")
        progress = Mock()
        with self.assertLogs(roxy.logger, level="INFO") as captured:
            outcome, current = roxy._submit_registration_email_otp(
                self.driver, "731842", budget=self.budget,
                expected_email="alias@example.test", on_refresh_retry=progress,
            )
        self.assertEqual(outcome, "accepted")
        self.assertEqual([call.args[1] for call in self.fill.call_args_list], ["731842", "731842"])
        self.assertEqual(self.submit.call_count, 2)
        self.assertEqual([call.kwargs["retry_after_refresh"] for call in self.wait.call_args_list], [True, False])
        self.assertTrue(all(call.kwargs["budget"] is self.budget for call in self.wait.call_args_list))
        original, retry = self.driver._browser_submission_receipts
        self.assertIs(current, retry)
        self.assertNotEqual(original.submission_id, retry.submission_id)
        self.assertEqual(original.phase, "superseded")
        self.assertEqual(original.result, "unknown")
        self.assertEqual(original.error_type, "otp_refresh_retry")
        progress.assert_called_once()
        self.assertNotIn("731842", "\n".join(captured.output))

    def test_original_code_is_not_repeated_without_refreshed_form_result(self):
        for result in ("accepted", "invalid", "stuck", "session_expired"):
            with self.subTest(result=result):
                self.fill.reset_mock()
                self.outcomes(result)
                self.assertEqual(roxy._submit_registration_email_otp(
                    self.driver, "731842", budget=self.budget, expected_email="alias@example.test",
                )[0], result)
                self.fill.assert_called_once()

    def test_late_network_event_is_not_bound_to_retry_receipt_by_guessing(self):
        original = BrowserSubmissionReceipt(kind="otp", stage="email_otp", endpoint_kind="otp_submit")
        record_browser_submission_fact(self.driver, "dispatch_intent", receipt=original)
        record_browser_submission_fact(self.driver, "superseded", receipt=original,
                                       result="unknown", error_type="otp_refresh_retry")
        retry = BrowserSubmissionReceipt(kind="otp", stage="email_otp", endpoint_kind="otp_submit")
        record_browser_submission_fact(self.driver, "dispatch_intent", receipt=retry)
        self.assertIsNone(roxy._unique_submission_receipt_for_endpoint(self.driver, "otp_submit"))

    def test_second_refresh_cannot_repeat_original_code_indefinitely(self):
        self.outcomes("retry_previous_otp", "retry_previous_otp")
        outcome, receipt = roxy._submit_registration_email_otp(
            self.driver, "731842", budget=self.budget, expected_email="alias@example.test",
        )
        self.assertEqual(outcome, "stuck")
        self.assertEqual(receipt.phase, "unknown")
        self.assertEqual(self.fill.call_count, 2)

    def test_refresh_retry_does_not_extend_expired_total_budget(self):
        now = [0.0]
        budget = StageBudget(5, clock=lambda: now[0])

        def expire(driver, **_kwargs):
            record_browser_submission_fact(driver, "unknown", result="unknown")
            now[0] = 5
            return "retry_previous_otp"

        self.wait.side_effect = expire
        with self.assertRaises(StageTimeout):
            roxy._submit_registration_email_otp(
                self.driver, "731842", budget=budget, expected_email="alias@example.test",
            )
        self.fill.assert_called_once()
        self.assertEqual(self.driver._browser_submission_receipt.phase, "unknown")

    def test_expired_original_retry_resends_and_submits_new_code_in_registration(self):
        for source in ("icloud_hide", "remail"):
            with self.subTest(source=source), ExitStack() as stack:
                self.fill.reset_mock()
                self.driver = SimpleNamespace(
                    current_url="https://auth.openai.com/email-verification",
                    timeouts=SimpleNamespace(page_load=45, script=8),
                    set_page_load_timeout=Mock(), set_script_timeout=Mock(),
                    execute_script=Mock(return_value={}),
                )
                self.outcomes("retry_previous_otp", "invalid", "accepted")
                opened = SimpleNamespace(profile_id="test-profile", debugger_address="127.0.0.1:9222",
                                         created_by_run=False, raw={}, traffic_capture=None, account_bound=False)
                for target in (
                    "core.registration.service.report_job_progress", "core.registration.service.report_job_otp_evidence",
                    "core.registration.service.report_registered_account", "core.browser.traffic.bind_roxy_capture",
                    "core.registration.debug.attach_current_roxy", "core.registration.debug.pause_current_failure",
                    "core.browser.data_saver.BrowserDataSaver", "core.registration.plan_capture.install_selenium",
                    "core.email.provider.retain_email",
                ):
                    stack.enter_context(patch(target))
                stack.enter_context(patch("core.registration.service.registration_fact_context", return_value={}))
                stack.enter_context(patch("core.registration.service.is_stop_requested", return_value=False))
                stack.enter_context(patch.object(roxy, "RoxyBrowserClient", return_value=MagicMock()))
                stack.enter_context(patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened))
                stack.enter_context(patch.object(roxy, "_build_driver", return_value=self.driver))
                for name in ("_center_browser_window", "_safe_get", "_page_warmup", "_maybe_accept", "_quit_driver"):
                    stack.enter_context(patch.object(roxy, name))
                stack.enter_context(patch.object(roxy, "_submit_email_and_wait_next", return_value="otp"))
                stack.enter_context(patch.object(roxy, "_fill_password_page_if_present", return_value=None))
                stack.enter_context(patch.object(roxy, "_has_access_token", return_value=False))
                stack.enter_context(patch.object(roxy, "_is_signup_password_page", return_value=False))
                stack.enter_context(patch.object(roxy, "_wait_email_otp_page_ready", return_value="ready"))
                fetch = stack.enter_context(patch.object(roxy, "wait_for_otp", side_effect=["731842", "864203"]))
                resend = stack.enter_context(patch.object(roxy, "_resend_email_otp_after_failure", return_value={
                    "ui_ack": "confirmed", "requested_after_ts": 1234,
                }))
                profile = stack.enter_context(patch.object(roxy, "_complete_profile_page", side_effect=RuntimeError("测试在进入资料页后结束")))
                with self.assertLogs(roxy.logger, level="INFO") as captured:
                    result = roxy.run_roxy_registration(
                        "alias@example.test", "Test User", "2000-01-01", email_source=source,
                        proxy="http://pool.example:8080",
                        registration_options={"password_enabled": False, "twofa_enabled": False,
                                              "codex_enabled": False, "plan_check_enabled": False},
                    )
                self.assertFalse(result["success"])
                self.assertIn("测试在进入资料页后结束", result.get("error", ""))
                profile.assert_called_once()
                self.assertEqual([call.args[1] for call in self.fill.call_args_list], ["731842", "731842", "864203"])
                resend.assert_called_once()
                self.assertEqual(fetch.call_count, 2)
                self.assertEqual(fetch.call_args.kwargs["after_ts"], 1234)
                self.assertEqual(fetch.call_args.kwargs["email_source"], source)
                logs = "\n".join(captured.output)
                self.assertNotIn("731842", logs)
                self.assertNotIn("864203", logs)
