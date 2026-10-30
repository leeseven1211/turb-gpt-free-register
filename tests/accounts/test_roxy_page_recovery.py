"""已有账号的明确错误页恢复只用一次入口和原剩余预算。"""
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from core.accounts.liveness.roxy import flow
from core.auth.browser.auth_context import current_execution_context
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.page_errors import AuthPageError


class RoxyPageRecoveryTests(unittest.TestCase):
    def test_context_missing_restarts_same_identity_once_and_keeps_original_receipt(self):
        driver = MagicMock()
        receipt = BrowserSubmissionReceipt(kind="password", stage="login_password", phase="ui_dispatched")
        driver._browser_submission_receipt = receipt
        driver._browser_submission_receipts = [receipt]
        now = [100.0]
        deadlines = []

        def login(*_args, **_kwargs):
            deadlines.append(current_execution_context().budget.deadline)
            if len(deadlines) == 1:
                now[0] += 20
                raise AuthPageError("auth_context_missing")
            return "logged_in"

        with (
            patch.object(flow, "time", SimpleNamespace(monotonic=lambda: now[0])),
            patch.object(flow, "_enter_existing_account_otp", side_effect=login) as enter,
            patch.object(driver, "get") as navigate,
            patch.object(flow, "_page_warmup"),
            patch("core.auth.browser.submission_recovery.begin_auth_session"),
        ):
            result = flow._login_existing_account_with_recovery(
                driver, "fixture@example.test", password="saved-password", totp_secret="saved-secret", timeout=60,
            )
        self.assertEqual(result, "logged_in")
        self.assertEqual(deadlines, [160, 160])
        self.assertEqual(enter.call_count, 2)
        self.assertTrue(all(call.args[1] == "fixture@example.test" for call in enter.call_args_list))
        self.assertTrue(all(call.kwargs["password"] == "saved-password" for call in enter.call_args_list))
        navigate.assert_called_once()
        self.assertEqual(navigate.call_args.args[0], "https://chatgpt.com/auth/login")
        self.assertEqual(receipt.phase, "unknown")
        self.assertIn(receipt, driver._browser_submission_receipts)

    def test_second_error_is_returned_without_another_restart(self):
        error = AuthPageError("auth_operation_timeout")
        driver = MagicMock()
        with (
            patch.object(flow, "_enter_existing_account_otp", side_effect=error) as enter,
            patch.object(driver, "get") as navigate,
            patch.object(flow, "_page_warmup"),
            patch("core.auth.browser.submission_recovery.begin_auth_session"),
        ):
            with self.assertRaises(AuthPageError) as caught:
                flow._login_existing_account_with_recovery(driver, "fixture@example.test", password="saved")
        self.assertIs(caught.exception, error)
        self.assertEqual(enter.call_count, 2)
        navigate.assert_called_once()

    def test_recovery_navigation_uses_five_remaining_seconds_and_never_starts_late_second_round(self):
        now = [100.0]
        driver = MagicMock()
        driver.timeouts.page_load = 90
        error = AuthPageError("auth_context_missing")

        def login(*_args, **_kwargs):
            now[0] = 155
            raise error

        def navigate(_url):
            now[0] += driver.set_page_load_timeout.call_args.args[0]

        with (
            patch.object(flow, "time", SimpleNamespace(monotonic=lambda: now[0])),
            patch.object(flow, "_enter_existing_account_otp", side_effect=login) as enter,
            patch.object(driver, "get", side_effect=navigate),
            patch.object(flow, "_page_warmup") as warmup,
            patch("core.auth.browser.submission_recovery.begin_auth_session"),
        ):
            with self.assertRaises(AuthPageError) as caught:
                flow._login_existing_account_with_recovery(driver, "fixture@example.test", timeout=60)
        self.assertIs(caught.exception, error)
        self.assertEqual(driver.set_page_load_timeout.call_args_list[0].args[0], 5)
        self.assertEqual(now[0], 160)
        enter.assert_called_once()
        warmup.assert_not_called()
        self.assertEqual(driver.set_page_load_timeout.call_args.args[0], 90)

    def test_expired_warmup_does_not_start_second_round(self):
        now = [100.0]
        error = AuthPageError("auth_operation_timeout")

        def warmup(*_args, **_kwargs):
            now[0] = 160

        with (
            patch.object(flow, "time", SimpleNamespace(monotonic=lambda: now[0])),
            patch.object(flow, "_enter_existing_account_otp", side_effect=error) as enter,
            patch.object(flow, "_page_warmup", side_effect=warmup),
            patch("core.auth.browser.submission_recovery.begin_auth_session"),
        ):
            with self.assertRaises(AuthPageError) as caught:
                flow._login_existing_account_with_recovery(MagicMock(), "fixture@example.test", timeout=60)
        self.assertIs(caught.exception, error)
        enter.assert_called_once()

    def test_new_document_releases_old_email_barrier_but_keeps_unknown_fact(self):
        driver = MagicMock()
        driver._email_submission_receipt = {"id": "old-submission"}
        receipt = BrowserSubmissionReceipt(kind="email", stage="login_email", phase="ui_dispatched")
        driver._browser_submission_receipt = receipt
        driver._browser_submission_receipts = [receipt]
        driver.execute_script.side_effect = [100.0, 200.0]
        calls = []

        def login(*_args, **_kwargs):
            calls.append(driver._email_submission_receipt)
            if len(calls) == 1:
                raise AuthPageError("auth_context_missing")
            return "logged_in"

        with (
            patch.object(flow, "_enter_existing_account_otp", side_effect=login),
            patch.object(flow, "_page_warmup"),
            patch("core.auth.browser.submission_recovery.begin_auth_session"),
        ):
            result = flow._login_existing_account_with_recovery(driver, "fixture@example.test")
        self.assertEqual(result, "logged_in")
        self.assertEqual(calls, [{"id": "old-submission"}, None])
        self.assertEqual(receipt.phase, "unknown")
        self.assertIn(receipt, driver._browser_submission_receipts)

    def test_same_document_does_not_release_old_email_barrier(self):
        driver = MagicMock()
        driver._email_submission_receipt = {"id": "old-submission"}
        driver.execute_script.return_value = 100.0
        error = AuthPageError("auth_context_missing")
        with (
            patch.object(flow, "_enter_existing_account_otp", side_effect=error) as enter,
            patch.object(flow, "_page_warmup"),
            patch("core.auth.browser.submission_recovery.begin_auth_session"),
        ):
            with self.assertRaises(AuthPageError):
                flow._login_existing_account_with_recovery(driver, "fixture@example.test")
        enter.assert_called_once()
        self.assertEqual(driver._email_submission_receipt, {"id": "old-submission"})

    def test_expired_budget_keeps_concrete_page_error_and_does_not_restart(self):
        now = [100.0]
        error = AuthPageError("auth_context_missing")

        def login(*_args, **_kwargs):
            now[0] = 161
            raise error

        with (
            patch.object(flow, "time", SimpleNamespace(monotonic=lambda: now[0])),
            patch.object(flow, "_enter_existing_account_otp", side_effect=login),
            patch.object(flow, "_safe_get") as navigate,
        ):
            with self.assertRaises(AuthPageError) as caught:
                flow._login_existing_account_with_recovery(MagicMock(), "fixture@example.test", timeout=60)
        self.assertIs(caught.exception, error)
        navigate.assert_not_called()

    def test_other_login_failure_does_not_acquire_page_error_retry(self):
        with (
            patch.object(flow, "_enter_existing_account_otp", side_effect=RuntimeError("原有其他失败")) as enter,
            patch.object(flow, "_safe_get") as navigate,
        ):
            with self.assertRaisesRegex(RuntimeError, "原有其他失败"):
                flow._login_existing_account_with_recovery(MagicMock(), "fixture@example.test")
        enter.assert_called_once()
        navigate.assert_not_called()
