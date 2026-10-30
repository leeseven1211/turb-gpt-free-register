"""页面错误与真实登录分支变化应及时交回调度，不重复等待旧表单。"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from core.auth.browser import password_auth
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.page_errors import AuthPageError
from core.codex.roxy import oauth
from tests.auth.test_password_pre_submit_recovery import _Clock, _Driver, _flow


EMAIL = "owner@example.test"
PASSWORD = "SyntheticPass123!"
PASSWORD_URL = "https://auth.openai.com/log-in/password"
ERROR_PAGE = {"url": PASSWORD_URL, "text": "Operation timed out", "inputs": [], "buttons": []}


def _error():
    return AuthPageError("auth_operation_timeout")


class AuthPageReactionTests(unittest.TestCase):
    def test_password_wait_checks_error_even_when_password_route_detector_is_false(self):
        clock = _Clock()
        driver = _Driver(clock)
        driver.current_url = PASSWORD_URL
        error = _error()
        with (_flow(driver, clock),
              patch.object(password_auth, "auth_page_error", return_value=error, create=True),
              patch.object(password_auth, "_password_page_state", return_value=ERROR_PAGE),
              patch.object(password_auth, "_is_signup_password_page", return_value=False)):
            with self.assertRaises(RuntimeError) as caught:
                password_auth._fill_password_page_if_present(driver, EMAIL, timeout=2, existing_password=PASSWORD)
        self.assertIs(caught.exception, error)
        self.assertEqual(clock.now, 0)
        self.assertEqual(driver.queues, [])
        self.assertEqual(driver.gets, [])

    def test_password_error_after_dispatch_retains_unknown_submission(self):
        clock = _Clock()
        driver = _Driver(clock)
        driver.current_url = PASSWORD_URL
        driver.ready = True
        error = _error()

        def state(_driver):
            if driver.queues:
                return ERROR_PAGE
            return {"url": PASSWORD_URL, "inputs": [{"type": "password", "visible": True}]}

        with (_flow(driver, clock),
              patch.object(password_auth, "auth_page_error", side_effect=lambda s: error if s.get("text") else None, create=True),
              patch.object(password_auth, "_password_page_state", side_effect=state),
              patch.object(password_auth, "_is_login_password_page", side_effect=lambda _d: not driver.queues),
              patch.object(password_auth, "_is_signup_password_page", return_value=False),
              patch.object(password_auth, "_is_email_verification_page", return_value=False),
              patch.object(password_auth, "_password_submission_snapshot", return_value={"phase": "dispatched"})):
            with self.assertRaises(RuntimeError) as caught:
                password_auth._fill_password_page_if_present(driver, EMAIL, timeout=5, existing_password=PASSWORD)
        self.assertIs(caught.exception, error)
        self.assertEqual(len(driver.queues), 1)
        self.assertEqual(driver._browser_submission_receipt.phase, "unknown")
        self.assertEqual(driver.gets, [])
        self.assertLess(clock.now, 5)

    def test_actual_totp_page_exits_password_wait_without_typing_or_submitting(self):
        clock = _Clock()
        driver = _Driver(clock)
        driver.current_url = PASSWORD_URL
        state = {"url": PASSWORD_URL, "text": "Authenticator app", "inputs": [{"name": "totp", "type": "text", "visible": True}]}
        with (_flow(driver, clock),
              patch.object(password_auth, "_password_page_state", return_value=state),
              patch.object(password_auth, "_is_signup_password_page", return_value=False)):
            result = password_auth._fill_password_page_if_present(driver, EMAIL, timeout=2, existing_password=PASSWORD)
        self.assertEqual(result, PASSWORD)
        self.assertEqual(clock.now, 0)
        self.assertEqual(driver.queues, [])

    def test_bare_consent_route_does_not_prove_login_advanced(self):
        self.assertFalse(oauth._is_login_advanced(MagicMock(), {
            "url": "https://auth.openai.com/consent", "inputs": [], "buttons": [], "text": "",
        }))

    def test_advanced_route_rejects_explicit_error_text(self):
        with patch.object(oauth, "auth_page_error", return_value=_error(), create=True):
            self.assertFalse(oauth._is_login_advanced(MagicMock(), {
                "url": "https://auth.openai.com/consent", "inputs": [], "buttons": [],
                "text": "Operation timed out",
            }))

    def test_consent_route_with_live_button_hands_off_to_authorization(self):
        self.assertTrue(oauth._is_login_advanced(MagicMock(), {
            "url": "https://auth.openai.com/consent", "inputs": [],
            "buttons": [{"type": "submit", "text": "Authorize"}],
        }))

    def test_chatgpt_home_requires_session_evidence_before_handoff(self):
        state = {"url": "https://chatgpt.com/", "inputs": [], "buttons": []}
        with patch.object(oauth, "_has_access_token", return_value=False):
            self.assertFalse(oauth._is_login_advanced(MagicMock(), state))

    def test_explicit_error_is_not_an_empty_auth_shell(self):
        self.assertFalse(oauth._is_empty_auth_challenge_state(ERROR_PAGE))

    def test_page_error_keeps_older_unknown_when_latest_receipt_is_prepared(self):
        clock = _Clock()
        driver = _Driver(clock)
        driver.current_url = PASSWORD_URL
        old = BrowserSubmissionReceipt(kind="resume_login", stage="login_password")
        old.transition("unknown", result="unknown")
        current = BrowserSubmissionReceipt(kind="resume_login", stage="login_password")
        driver._browser_submission_receipts = [old]
        driver._browser_submission_receipt = current
        with (_flow(driver, clock),
              patch.object(password_auth, "_password_page_state", return_value=ERROR_PAGE)):
            with self.assertRaises(AuthPageError) as caught:
                password_auth._fill_password_page_if_present(driver, EMAIL, timeout=2, existing_password=PASSWORD)
        self.assertTrue(caught.exception.submission_unknown)
        self.assertFalse(caught.exception.not_submitted)
        self.assertEqual(old.phase, "unknown")
        self.assertEqual(current.phase, "not_dispatched")

    def test_page_error_keeps_confirmed_submission_distinct_from_unsent(self):
        clock = _Clock()
        driver = _Driver(clock)
        driver.current_url = PASSWORD_URL
        receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password")
        receipt.transition("confirmed", result="success")
        driver._browser_submission_receipt = receipt
        with (_flow(driver, clock),
              patch.object(password_auth, "_password_page_state", return_value=ERROR_PAGE)):
            with self.assertRaises(AuthPageError) as caught:
                password_auth._fill_password_page_if_present(driver, EMAIL, timeout=2, existing_password=PASSWORD)
        self.assertFalse(caught.exception.not_submitted)
        self.assertFalse(caught.exception.submission_unknown)
        self.assertEqual(receipt.phase, "confirmed")

    def test_challenge_raises_page_error_before_submitting_or_refreshing(self):
        clock = _Clock()
        driver = MagicMock(current_url=PASSWORD_URL)
        with (patch.object(oauth, "_login_challenge_state", return_value=ERROR_PAGE),
              patch.object(oauth, "_is_login_password_page", return_value=True),
              patch.object(oauth, "_is_totp_login_page", return_value=False),
              patch.object(oauth, "_fill_password_page_if_present", side_effect=RuntimeError("不应提交")) as fill,
              patch.object(oauth, "time", SimpleNamespace(time=clock.time, monotonic=clock.time, sleep=clock.sleep))):
            with self.assertRaises(AuthPageError):
                oauth._complete_login_challenge_after_email(driver, EMAIL, PASSWORD, "", timeout=2)
        self.assertEqual(clock.now, 0)
        fill.assert_not_called()
        driver.refresh.assert_not_called()

    def test_password_timeout_checks_page_error_before_and_after_refresh(self):
        password_page = {"url": PASSWORD_URL, "inputs": [{"type": "password"}], "errors": []}
        for error_after_refresh in (False, True):
            driver = MagicMock(current_url=PASSWORD_URL)
            driver._browser_submission_receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password")
            driver._browser_submission_receipt.transition("unknown", result="unknown")
            states = [password_page, password_page, ERROR_PAGE] if error_after_refresh else [password_page, ERROR_PAGE]
            snapshots = iter(states)
            with (self.subTest(error_after_refresh=error_after_refresh),
                  patch.object(oauth, "_login_challenge_state", side_effect=lambda _driver: next(snapshots, ERROR_PAGE)),
                  patch.object(oauth, "_is_login_password_page", return_value=True),
                  patch.object(oauth, "_is_totp_login_page", return_value=False),
                  patch.object(oauth, "_fill_password_page_if_present", side_effect=password_auth._PasswordTransitionTimeout("request_unknown")) as fill,
                  patch.object(oauth, "_refresh_auth_challenge_after_submit") as refresh):
                with self.assertRaises(AuthPageError):
                    oauth._complete_login_challenge_after_email(driver, EMAIL, PASSWORD, "", timeout=2)
            fill.assert_called_once()
            self.assertEqual(refresh.call_count, int(error_after_refresh))
            self.assertEqual(driver._browser_submission_receipt.phase, "unknown")
