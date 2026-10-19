import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.registration import email_otp, submission_recovery
from core.registration.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from core.registration.state_machine import PageState, StageBudget


class _LoginDriver:
    def __init__(self):
        self.current_url = "https://chatgpt.com/auth/login"
        self.document = 0
        self.submission_document = 0
        self.submission_id = ""
        self.gets = []
        self.timeouts = SimpleNamespace(page_load=60)

    def execute_script(self, script, *_args):
        if script == "return performance.timeOrigin;":
            return 1000.0 + self.document
        if "window.__turbEmailSubmission" in script and self.document == self.submission_document:
            return {"id": self.submission_id, "phase": "dispatched"}
        return None

    def get(self, url):
        self.gets.append(url)
        self.current_url = url
        self.document += 1

    def set_page_load_timeout(self, _timeout):
        pass


class SavedLoginEmailRecoveryTests(unittest.TestCase):
    def _run_login(self, *, allow_login_password=True, second_unknown=False, remaining=180):
        driver = _LoginDriver()
        receipts = []
        waits = [email_otp._EmailSubmissionUnknown("request_unknown: 模拟旧页面停滞")]
        waits.append(email_otp._EmailSubmissionUnknown("request_unknown: 再次停滞") if second_unknown else "otp")
        budgets = []

        def submit(current_driver, _email):
            budgets.append(current_driver._registration_before_email_dispatch())
            receipt = BrowserSubmissionReceipt(kind="resume_login", stage="submit_email", endpoint_kind="email_submit")
            current_driver._browser_submission_receipt = receipt
            current_driver._email_submission_receipt = {"id": receipt.submission_id}
            current_driver.submission_id = receipt.submission_id
            current_driver.submission_document = current_driver.document
            record_browser_submission_fact(current_driver, "dispatch_intent", receipt=receipt)
            record_browser_submission_fact(current_driver, "ui_dispatched", receipt=receipt)
            receipts.append(receipt)

        confirmed = Mock()
        outer = StageBudget.start(remaining)
        patches = (
            patch.object(email_otp.StageBudget, "start", return_value=outer),
            patch.object(email_otp, "_type_email_address", return_value="email"),
            patch.object(email_otp, "_email_input_value_state", return_value={"inputs": [{"value": "fixture@example.test"}]}),
            patch.object(email_otp, "human_delay"),
            patch.object(email_otp, "_submit_email_step", side_effect=submit),
            patch.object(email_otp, "_wait_email_submit_next_state", side_effect=waits),
            patch.object(email_otp, "_page_snapshot", return_value={"url": driver.current_url, "inputs": [{"type": "email", "value": ""}]}),
            patch.object(email_otp, "_email_submit_advanced_state", return_value=None),
            patch.object(submission_recovery, "log_submission_diagnostics"),
        )
        from contextlib import ExitStack

        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            if second_unknown or not allow_login_password:
                with self.assertRaises(email_otp._EmailSubmissionUnknown):
                    email_otp._submit_email_and_wait_next(driver, "fixture@example.test", allow_login_password=allow_login_password, on_submitted=confirmed)
                result = None
            else:
                result = email_otp._submit_email_and_wait_next(driver, "fixture@example.test", allow_login_password=True, on_submitted=confirmed)
        return driver, receipts, budgets, outer, confirmed, result

    def test_saved_login_refreshes_then_starts_one_new_submission(self):
        driver, receipts, budgets, outer, confirmed, result = self._run_login()
        self.assertEqual(result, "otp")
        self.assertEqual(driver.gets, ["https://chatgpt.com/auth/login"])
        self.assertEqual(len(receipts), 2)
        self.assertNotEqual(receipts[0].submission_id, receipts[1].submission_id)
        self.assertEqual(receipts[0].phase, "unknown")
        self.assertEqual(driver._browser_submission_receipts, receipts)
        self.assertTrue(all(budget.deadline <= outer.deadline for budget in budgets))
        confirmed.assert_called_once_with()

    def test_ordinary_registration_does_not_restart_unknown_email(self):
        driver, receipts, _, _, confirmed, _ = self._run_login(allow_login_password=False)
        self.assertEqual(driver.gets, [])
        self.assertEqual(len(receipts), 1)
        confirmed.assert_not_called()

    def test_saved_login_cannot_loop_after_second_stall(self):
        driver, receipts, _, _, confirmed, _ = self._run_login(second_unknown=True)
        self.assertEqual(len(driver.gets), 1)
        self.assertEqual(len(receipts), 2)
        confirmed.assert_not_called()

    def test_fresh_email_page_requires_old_document_receipt_to_disappear(self):
        driver = _LoginDriver()
        driver._registration_resume_login = True
        driver._email_submission_receipt = {"id": "old"}
        driver.submission_id = "old"
        with (
            patch.object(email_otp, "_page_snapshot", return_value={"url": driver.current_url, "inputs": [{"type": "email", "value": ""}]}),
            patch.object(email_otp, "_email_submit_advanced_state", return_value=None),
            patch.object(email_otp, "recover_submission_page", side_effect=lambda _driver, _stage, observe, **kwargs: observe(kwargs["budget"])),
        ):
            self.assertIsNone(email_otp._recover_saved_login_email_page(driver, budget=StageBudget.start(20)))
            driver.document += 1
            self.assertIsNone(email_otp._recover_saved_login_email_page(driver, budget=StageBudget.start(20)))

    def test_failed_receipt_read_does_not_make_old_document_ready(self):
        driver = _LoginDriver()
        driver._registration_resume_login = True
        driver._email_submission_receipt = {"id": "old"}
        original_execute = driver.execute_script

        def execute(script, *args):
            if "window.__turbEmailSubmission" in script:
                raise RuntimeError("模拟回执读取失败")
            return original_execute(script, *args)

        driver.execute_script = execute
        with (
            patch.object(email_otp, "_page_snapshot", return_value={"url": driver.current_url, "inputs": [{"type": "email", "value": ""}]}),
            patch.object(email_otp, "_email_submit_advanced_state", return_value=None),
            patch.object(email_otp, "recover_submission_page", side_effect=lambda _driver, _stage, observe, **kwargs: observe(kwargs["budget"])),
        ):
            self.assertIsNone(email_otp._recover_saved_login_email_page(driver, budget=StageBudget.start(20)))
        self.assertEqual(driver.gets, [])

    def test_blank_otp_route_is_not_confirmed_as_next_step(self):
        driver = _LoginDriver()
        driver._registration_resume_login = True
        with (
            patch.object(email_otp, "_page_snapshot", return_value={"url": "https://auth.openai.com/email-verification"}),
            patch.object(email_otp, "classify_page", return_value=PageState.OTP_EMAIL),
            patch.object(email_otp, "has_visible_auth_inputs", return_value=False),
            patch.object(email_otp, "_email_submit_advanced_state", return_value="otp") as advanced,
            patch.object(email_otp, "recover_submission_page", side_effect=lambda _driver, _stage, observe, **kwargs: observe(kwargs["budget"])),
        ):
            self.assertIsNone(email_otp._recover_saved_login_email_page(driver, budget=StageBudget.start(20)))
        advanced.assert_not_called()

    def test_known_http_failure_is_reported_without_waiting_for_ui_timeout(self):
        driver = _LoginDriver()
        driver._email_submission_receipt = {"id": "old"}
        driver.submission_id = "old"
        receipt = BrowserSubmissionReceipt(kind="resume_login", stage="submit_email", endpoint_kind="email_submit")
        receipt.transition("response_observed", http_status=403, result="failure")
        driver._browser_submission_receipt = receipt
        with (
            patch.object(email_otp, "_email_submit_advanced_state", return_value=None),
            patch.object(email_otp, "log_submission_diagnostics"),
            patch.object(email_otp.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(email_otp._EmailSubmissionUnknown, "email_auth_http_403"):
                email_otp._wait_email_submit_next_state(driver, "fixture@example.test", budget=StageBudget.start(30))
        sleep.assert_not_called()
        self.assertEqual(receipt.http_status, 403)


if __name__ == "__main__":
    unittest.main()
