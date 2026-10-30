"""失败后保留原窗口的只读恢复与原提交围栏。"""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.registration import retained_resume
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.state_machine import PageState


EMAIL = "resume@example.test"
FACTS = {"attempt_id": 41, "run_id": 71, "job_id": 31}
PASSWORD = "unit-original-password"


def snapshot(path="/email-verification", *, text="", inputs=None, **values):
    return {"url": f"https://auth.openai.com{path}", "text": text,
            "inputs": inputs if inputs is not None else [{"name": "code", "autocomplete": "one-time-code"}],
            **values}


def fact(kind, submission_id, *, phase="unknown", endpoint=None):
    endpoint = endpoint or {"email": "email_submit", "password": "password_submit", "otp": "otp_submit"}.get(kind, kind)
    return {"kind": kind, "stage": kind, "submission_id": submission_id, "phase": phase,
            "endpoint_kind": endpoint, "http_method": "POST"}


class RetainedResumeTests(unittest.TestCase):
    @contextmanager
    def context(self, *, snapshots=None, private=None):
        driver = SimpleNamespace(current_url="https://auth.openai.com/email-verification",
                                 refresh=Mock(), get=Mock(), execute_script=Mock())
        tick = [0.0]
        private = private if private is not None else {"password": PASSWORD, "submission_facts": []}
        snapshots = list(snapshots or [snapshot()])
        def observe(_driver):
            value = snapshots.pop(0) if len(snapshots) > 1 else snapshots[0]
            driver.current_url = value.get("url") or driver.current_url
            return value
        with ExitStack() as stack:
            read = stack.enter_context(patch("core.storage.registration.get_private_resume_context", return_value=private))
            observe_mock = stack.enter_context(patch.object(retained_resume, "_email_otp_page_state", side_effect=observe))
            write = stack.enter_context(patch.object(retained_resume, "record_browser_submission_fact"))
            stack.enter_context(patch.object(retained_resume, "_check_manual_stop"))
            stack.enter_context(patch.object(retained_resume.time, "monotonic", side_effect=lambda: tick[0]))
            stack.enter_context(patch.object(retained_resume.time, "sleep", side_effect=lambda seconds: tick.__setitem__(0, tick[0] + seconds)))
            yield driver, read, observe_mock, write, tick
        driver.refresh.assert_not_called()
        driver.get.assert_not_called()
        driver.execute_script.assert_not_called()

    def prepare(self, driver, **kwargs):
        return retained_resume.prepare_retained_resume(driver, email=EMAIL, existing_password=PASSWORD,
                                                      facts=FACTS, **kwargs)

    def test_existing_account_profile_rejection_restarts_original_identity_login(self):
        rejected = {**fact("profile", "original-profile", phase="rejected", endpoint="profile_submit"),
                    "http_status": 400, "error_type": "account_create_user_already_exists"}
        private = {"password": PASSWORD, "submission_facts": [rejected]}
        with self.context(private=private, snapshots=[snapshot("/about-you", inputs=[
            {"name": "name", "type": "text"}, {"name": "age", "type": "number"},
        ])]) as (driver, read, _, write, _):
            driver._registration_resume_login = True
            result = self.prepare(driver)
            self.assertTrue(result.restart_login)
            self.assertEqual(result.password, PASSWORD)
            self.assertEqual(result.page_state, PageState.PROFILE)
            read.assert_called_once_with(41, email=EMAIL)
            write.assert_not_called()
        self.assertEqual(private["submission_facts"], [rejected])

    def test_existing_profile_rejection_with_old_unknown_actions_still_restarts_login(self):
        rejected = {**fact("profile", "original-profile", phase="rejected", endpoint="profile_submit"),
                    "http_status": 400, "error_type": "account_create_user_already_exists"}
        unknown = [fact("password", "old-password-1"), fact("password", "old-password-2")]
        private = {"password": PASSWORD, "submission_facts": [*unknown, rejected]}
        with self.context(private=private, snapshots=[snapshot("/about-you", inputs=[
            {"name": "name", "type": "text"}, {"name": "age", "type": "number"},
        ])]) as (driver, _, _, write, _):
            driver._registration_resume_login = True
            result = self.prepare(driver)
            self.assertTrue(result.restart_login)
            write.assert_not_called()
        self.assertEqual(private["submission_facts"], [*unknown, rejected])

    def test_original_otp_form_keeps_private_password_without_navigation(self):
        with self.context() as (driver, read, _, write, _):
            result = self.prepare(driver)
            self.assertEqual(result.page_state, PageState.OTP_EMAIL)
            self.assertEqual(result.password, PASSWORD)
            self.assertIsNone(result.pending_otp)
            read.assert_called_once_with(41, email=EMAIL)
            write.assert_not_called()
            self.assertFalse(getattr(driver, "_registration_resume_login", False))

    def test_pending_otp_restores_original_id_and_original_receipt_object(self):
        private = {"password": PASSWORD, "submission_facts": [fact("otp", "original-otp")]}
        with self.context(private=private) as (driver, _, _, write, _):
            receipt = BrowserSubmissionReceipt(**fact("otp", "original-otp"))
            driver._browser_submission_receipt = receipt
            driver._browser_submission_receipts = [receipt]
            result = self.prepare(driver)
            self.assertIs(result.pending_otp, receipt)
            self.assertIs(driver._browser_submission_receipt, receipt)
            self.assertEqual(receipt.phase, "unknown")
            write.assert_not_called()

    def test_pending_otp_without_memory_receipt_is_restored_from_attempt(self):
        private = {"password": PASSWORD, "submission_facts": [fact("otp", "original-otp")]}
        with self.context(private=private) as (driver, _, _, write, _):
            result = self.prepare(driver)
            self.assertEqual(result.pending_otp.submission_id, "original-otp")
            self.assertIs(driver._browser_submission_receipt, result.pending_otp)
            write.assert_not_called()

    def test_current_receipt_object_wins_over_duplicate_history_copy(self):
        original = fact("otp", "original-otp")
        with self.context(private={"password": PASSWORD, "submission_facts": [original]}) as (driver, _, _, write, _):
            receipt = BrowserSubmissionReceipt(**original)
            driver._browser_submission_receipt = receipt
            driver._browser_submission_receipts = [receipt, BrowserSubmissionReceipt(**original)]
            self.assertIs(self.prepare(driver).pending_otp, receipt)
            write.assert_not_called()

    def test_late_lower_phase_does_not_downgrade_restored_unknown_receipt(self):
        original = [fact("otp", "original-otp"), fact("otp", "original-otp", phase="ui_queued")]
        with self.context(private={"password": PASSWORD, "submission_facts": original}) as (driver, _, _, write, _):
            self.assertEqual(self.prepare(driver).pending_otp.phase, "unknown")
            write.assert_not_called()

    def test_downstream_profile_confirms_original_email_password_and_otp_ids(self):
        facts = [fact("email", "email-old"), fact("password", "password-old"), fact("otp", "otp-old")]
        with self.context(snapshots=[snapshot("/about-you", inputs=[])], private={"password": PASSWORD, "submission_facts": facts}) as (driver, _, _, write, _):
            result = self.prepare(driver)
            self.assertEqual(result.page_state, PageState.PROFILE)
            self.assertIsNone(result.pending_otp)
            self.assertEqual({call.kwargs["receipt"].submission_id for call in write.call_args_list},
                             {"email-old", "password-old", "otp-old"})
            self.assertTrue(all(call.args[1] == "confirmed" for call in write.call_args_list))

    def test_original_totp_and_verified_pages_confirm_pending_otp(self):
        private = {"password": PASSWORD, "submission_facts": [fact("otp", "otp-old")]}
        states = [(snapshot("/mfa-challenge/totp", text="Authenticator code", inputs=[{"name": "totp"}]), PageState.MFA_TOTP),
                  (snapshot("/email-verification", text="Email verified", inputs=[]), PageState.EMAIL_VERIFIED)]
        for page, expected in states:
            with self.subTest(expected=expected), self.context(snapshots=[page], private=private) as (driver, _, _, write, _):
                result = self.prepare(driver)
                self.assertEqual(result.page_state, expected)
                write.assert_called_once()
                self.assertEqual(write.call_args.kwargs["receipt"].submission_id, "otp-old")

    def test_pending_password_only_observes_until_otp_then_confirms_original(self):
        password_page = snapshot("/create-account/password", inputs=[{"type": "password", "autocomplete": "new-password"}])
        private = {"password": PASSWORD, "submission_facts": [fact("password", "password-old")]}
        with self.context(snapshots=[password_page, snapshot()], private=private) as (driver, _, observer, write, tick):
            result = self.prepare(driver)
            self.assertEqual(result.page_state, PageState.OTP_EMAIL)
            self.assertGreaterEqual(observer.call_count, 2)
            self.assertGreater(tick[0], 0)
            write.assert_called_once()
            self.assertEqual(write.call_args.kwargs["receipt"].submission_id, "password-old")

    def test_pending_password_without_transition_stops_after_bounded_observation(self):
        password_page = snapshot("/create-account/password", inputs=[{"type": "password", "autocomplete": "new-password"}])
        private = {"password": PASSWORD, "submission_facts": [fact("password", "password-old")]}
        with self.context(snapshots=[password_page], private=private) as (driver, _, _, write, tick):
            with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                self.prepare(driver)
            self.assertGreaterEqual(tick[0], 25)
            self.assertLessEqual(tick[0], 25.01)
            write.assert_not_called()

    def test_explicit_resume_restarts_login_for_unknown_password_or_otp_without_waiting(self):
        cases = [
            (snapshot("/create-account/password", inputs=[{"type": "password"}]), "password"),
            (snapshot(), "otp"),
        ]
        for page, kind in cases:
            with self.subTest(kind=kind), self.context(snapshots=[page], private={
                "password": PASSWORD, "submission_facts": [fact(kind, "old-unknown")],
            }) as (driver, _, _, write, tick):
                driver._registration_resume_login = True
                result = self.prepare(driver)
                self.assertTrue(result.restart_login)
                self.assertEqual(result.password, PASSWORD)
                self.assertIsNone(result.pending_otp)
                self.assertEqual(tick[0], 0)
                write.assert_not_called()

    def test_explicit_resume_can_restart_after_two_unknown_password_attempts(self):
        page = snapshot("/log-in/password", inputs=[{"type": "password"}])
        private = {"password": PASSWORD, "submission_facts": [
            fact("password", "original-password"),
            fact("resume_login", "resumed-password", endpoint="password_submit"),
        ]}
        with self.context(snapshots=[page], private=private) as (driver, _, _, write, tick):
            driver._registration_resume_login = True
            self.assertTrue(self.prepare(driver).restart_login)
            self.assertEqual(tick[0], 0)
            write.assert_not_called()

    def test_explicit_resume_still_rejects_wrong_browser_identity(self):
        private = {"password": PASSWORD, "submission_facts": [fact("password", "original-password")]}
        page = snapshot("/create-account/password", text="other@example.test", inputs=[{"type": "password"}])
        with self.context(snapshots=[page], private=private) as (driver, _, _, write, _):
            driver._registration_resume_login = True
            with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                self.prepare(driver)
            write.assert_not_called()

    def test_explicit_resume_restarts_from_email_form_or_known_blank_auth_page(self):
        pages = [snapshot("/log-in", inputs=[{"type": "email", "value": EMAIL}]),
                 snapshot("/email-verification", text="", inputs=[]),
                 snapshot(url="https://chatgpt.com/auth/login", text="", inputs=[])]
        private = {"password": PASSWORD, "submission_facts": [fact("password", "original-password")]}
        for page, reconnected in ((page, flag) for page in pages for flag in (False, True)):
            with self.subTest(page=page, reconnected=reconnected), self.context(
                snapshots=[page], private=private,
            ) as (driver, _, _, write, _):
                driver._registration_resume_login = True
                driver._registration_retained_identity_required = reconnected
                self.assertTrue(self.prepare(driver).restart_login)
                write.assert_not_called()

    def test_explicit_resume_restarts_from_exact_native_start_pages(self):
        private = {"password": PASSWORD, "submission_facts": [fact("password", "original-password")]}
        for native_url in ("chrome-error://chromewebdata/", "about:blank"):
            with self.subTest(native_url=native_url), self.context(
                snapshots=[snapshot(url=native_url, text="页面加载失败", inputs=[])], private=private,
            ) as (driver, _, _, write, _):
                driver._registration_resume_login = True
                driver._registration_retained_identity_required = True
                result = self.prepare(driver)
                self.assertEqual(result.page_state, PageState.AUTH_TRANSIENT)
                self.assertTrue(result.restart_login)
                self.assertEqual(result.password, PASSWORD)
                write.assert_not_called()

    def test_native_start_pages_still_require_scope_password_and_matching_identity(self):
        cases = [
            ("chrome-error://chromewebdata/", False, PASSWORD, ""),
            ("about:blank", True, None, ""),
            ("chrome-error://chromewebdata/", True, PASSWORD, "other@example.test"),
            ("about:blank", True, PASSWORD, "account_deactivated"),
            ("chrome-error://other/", True, PASSWORD, ""),
            ("about:blank?redirect=other", True, PASSWORD, ""),
            ("https://other.example.test/", True, PASSWORD, ""),
        ]
        for native_url, explicit_resume, password, text in cases:
            with self.subTest(native_url=native_url, explicit_resume=explicit_resume, text=text), self.context(
                snapshots=[snapshot(url=native_url, text=text, inputs=[])],
                private={"password": password, "submission_facts": []},
            ) as (driver, _, _, write, _):
                driver._registration_resume_login = explicit_resume
                with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                    retained_resume.prepare_retained_resume(driver, email=EMAIL, existing_password=password, facts=FACTS)
                write.assert_not_called()

    def test_explicit_resume_does_not_confirm_old_password_from_new_otp_page(self):
        private = {"password": PASSWORD, "submission_facts": [fact("password", "original-password")]}
        with self.context(snapshots=[snapshot()], private=private) as (driver, _, _, write, _):
            driver._registration_resume_login = True
            result = self.prepare(driver)
            self.assertEqual(result.page_state, PageState.OTP_EMAIL)
            self.assertFalse(result.restart_login)
            write.assert_not_called()

    def test_explicit_resume_with_unknown_original_mail_time_starts_fresh_login(self):
        private = {"password": PASSWORD, "submission_facts": [fact("password", "original-password")]}
        for timestamp in (None, "invalid", float("nan"), float("inf"), -1, True):
            with self.subTest(timestamp=timestamp), self.context(private=private) as (driver, _, _, write, _):
                driver._registration_resume_login = True
                result = self.prepare(driver, otp_after_ts=timestamp)
                self.assertEqual(result.page_state, PageState.OTP_EMAIL)
                self.assertTrue(result.restart_login)
                self.assertIsNone(result.pending_otp)
                self.assertEqual(result.password, PASSWORD)
                write.assert_not_called()

    def test_explicit_resume_with_original_mail_time_can_continue_current_otp_page(self):
        with self.context() as (driver, _, _, write, _):
            driver._registration_resume_login = True
            result = self.prepare(driver, otp_after_ts=125.5)
            self.assertEqual(result.page_state, PageState.OTP_EMAIL)
            self.assertFalse(result.restart_login)
            write.assert_not_called()

    def test_unknown_mail_time_does_not_reopen_verified_session(self):
        with self.context() as (driver, _, observer, write, _):
            driver._registration_resume_login = True
            result = self.prepare(driver, otp_after_ts=None,
                                  verified_session={"accessToken": "unit-session", "user": {"email": EMAIL}})
            self.assertEqual(result.page_state, PageState.AUTHENTICATED)
            self.assertFalse(result.restart_login)
            observer.assert_not_called()
            write.assert_not_called()

    def test_explicit_resume_can_leave_original_oauth_callback_error_page(self):
        private = {"password": PASSWORD, "submission_facts": [fact("password", "original-password")]}
        page = snapshot(url="https://chatgpt.com/auth/error?error=OAuthCallback", text="Authentication error", inputs=[])
        with self.context(snapshots=[page], private=private) as (driver, _, _, write, tick):
            driver._registration_resume_login = True
            driver._registration_retained_identity_required = True
            result = self.prepare(driver, otp_after_ts=None)
            self.assertTrue(result.restart_login)
            self.assertEqual(result.password, PASSWORD)
            self.assertEqual(result.page_state, PageState.AUTH_TRANSIENT)
            self.assertEqual(tick[0], 0)
            write.assert_not_called()

    def test_oauth_callback_error_requires_explicit_resume_and_same_identity(self):
        pages = [snapshot(url="https://chatgpt.com/auth/error?error=OAuthCallback", inputs=[]),
                 snapshot(url="https://chatgpt.com/auth/error?error=OAuthCallback", text="other@example.test", inputs=[])]
        for page, resume in ((pages[0], False), (pages[1], True)):
            with self.subTest(resume=resume), self.context(snapshots=[page]) as (driver, _, _, write, _):
                driver._registration_resume_login = resume
                with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                    self.prepare(driver)
                write.assert_not_called()

    def test_explicit_resume_unknown_resend_uses_new_login_without_replaying_resend(self):
        private = {"password": PASSWORD, "submission_facts": [fact("otp_resend", "original-resend")]}
        with self.context(snapshots=[snapshot()], private=private) as (driver, _, _, write, _):
            driver._registration_resume_login = True
            self.assertTrue(self.prepare(driver).restart_login)
            write.assert_not_called()

    def test_password_form_without_pending_submission_returns_original_password(self):
        for path, expected in (("/create-account/password", PageState.PASSWORD_CREATE), ("/log-in/password", PageState.PASSWORD_LOGIN)):
            with self.subTest(path=path), self.context(snapshots=[snapshot(path, inputs=[{"type": "password"}])]) as (driver, _, _, write, _):
                result = self.prepare(driver)
                self.assertEqual(result.page_state, expected)
                self.assertEqual(result.password, PASSWORD)
                write.assert_not_called()

    def test_password_conflict_and_private_read_failure_stop_without_page_writes(self):
        with self.context(private={"password": "different-private-password", "submission_facts": []}) as (driver, _, observer, write, _):
            with self.assertRaisesRegex(RuntimeError, "request_unknown") as raised:
                self.prepare(driver)
            self.assertNotIn("different-private-password", str(raised.exception))
            observer.assert_not_called()
            write.assert_not_called()
        with self.context() as (driver, read, observer, write, _):
            read.side_effect = RuntimeError("private detail")
            with self.assertRaisesRegex(RuntimeError, "request_unknown") as raised:
                self.prepare(driver)
            self.assertNotIn("private detail", str(raised.exception))
            observer.assert_not_called()
            write.assert_not_called()

    def test_mismatched_email_hints_in_text_and_visible_email_input_fail_closed(self):
        pages = [snapshot(text="Check your inbox other@example.test"),
                 snapshot(inputs=[{"name": "code"}, {"type": "email", "value": "other@example.test"}])]
        for page in pages:
            with self.subTest(page=page), self.context(snapshots=[page]) as (driver, _, _, write, _):
                with self.assertRaisesRegex(RuntimeError, "request_unknown") as raised:
                    self.prepare(driver)
                self.assertNotIn("other@example.test", str(raised.exception))
                write.assert_not_called()

    def test_foreign_origin_port_and_unknown_route_cannot_be_resumed(self):
        pages = [snapshot(url="http://auth.openai.com/email-verification"),
                 snapshot(url="https://auth.openai.com.other.test/email-verification"),
                 snapshot(url="https://auth.openai.com:444/email-verification"),
                 snapshot(url="https://person@auth.openai.com/email-verification"),
                 snapshot("/unexpected-route")]
        for page in pages:
            with self.subTest(url=page["url"]), self.context(snapshots=[page]) as (driver, _, _, write, _):
                with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                    self.prepare(driver)
                write.assert_not_called()

    def test_logged_out_auth_error_and_failed_snapshot_cannot_be_resumed(self):
        for page in (snapshot("/auth/error", text="Authentication error", inputs=[]),
                     snapshot("/auth/logout", inputs=[]), snapshot(error="private browser detail")):
            with self.subTest(page=page), self.context(snapshots=[page]) as (driver, _, _, write, _):
                with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                    self.prepare(driver)
                write.assert_not_called()

    def test_unknown_resend_or_unrecognized_post_blocks_even_on_downstream_page(self):
        for pending in (fact("otp_resend", "unknown-resend"), fact("new_kind", "unknown-new")):
            with self.subTest(kind=pending["kind"]), self.context(snapshots=[snapshot("/about-you", inputs=[])],
                    private={"password": PASSWORD, "submission_facts": [pending]}) as (driver, _, _, write, _):
                with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                    self.prepare(driver)
                write.assert_not_called()

    def test_late_unknown_fact_does_not_reopen_confirmed_original_submission(self):
        facts = [fact("otp", "otp-old", phase="confirmed"), fact("otp", "otp-old", phase="unknown")]
        with self.context(private={"password": PASSWORD, "submission_facts": facts}) as (driver, _, _, write, _):
            result = self.prepare(driver)
            self.assertIsNone(result.pending_otp)
            write.assert_not_called()

    def test_multiple_pending_otp_submissions_block_without_partial_confirmation(self):
        facts = [fact("email", "email-old"), fact("otp", "otp-1"), fact("otp", "otp-2")]
        with self.context(private={"password": PASSWORD, "submission_facts": facts}) as (driver, _, _, write, _):
            with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                self.prepare(driver)
            write.assert_not_called()

    def test_reconnected_window_requires_visible_original_email_hint(self):
        with self.context() as (driver, _, _, write, _):
            driver._registration_retained_identity_required = True
            with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                self.prepare(driver)
            write.assert_not_called()

    def test_reconnected_window_accepts_matching_visible_email_hint(self):
        with self.context(snapshots=[snapshot(text=f"Check your inbox {EMAIL}")]) as (driver, _, _, write, _):
            driver._registration_retained_identity_required = True
            self.assertEqual(self.prepare(driver).page_state, PageState.OTP_EMAIL)
            write.assert_not_called()

    def test_verified_original_session_confirms_pending_receipts_without_dom_read(self):
        original = [fact("email", "email-old"), fact("password", "password-old"), fact("otp", "otp-old")]
        private = {"password": PASSWORD, "submission_facts": original}
        with self.context(private=private) as (driver, _, observer, write, _):
            result = self.prepare(driver, verified_session={"accessToken": "unit-session", "user": {"email": EMAIL}})
            self.assertEqual(result.page_state, PageState.AUTHENTICATED)
            self.assertEqual(result.password, PASSWORD)
            self.assertIsNone(result.pending_otp)
            observer.assert_not_called()
            self.assertEqual({call.kwargs["receipt"].submission_id for call in write.call_args_list},
                             {"email-old", "password-old", "otp-old"})

    def test_verified_session_identity_mismatch_blocks_without_dom_or_confirmations(self):
        with self.context() as (driver, _, observer, write, _):
            with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                self.prepare(driver, verified_session={"accessToken": "unit-session", "user": {"email": "other@example.test"}})
            observer.assert_not_called()
            write.assert_not_called()

    def test_resume_login_receipt_uses_actual_endpoint_and_keeps_original_kind(self):
        pending = fact("resume_login", "original-login-otp", endpoint="otp_submit")
        with self.context(private={"password": PASSWORD, "submission_facts": [pending]}) as (driver, _, _, write, _):
            result = self.prepare(driver)
            self.assertEqual(result.pending_otp.submission_id, "original-login-otp")
            self.assertEqual(result.pending_otp.kind, "resume_login")
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
