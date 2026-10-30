"""密码尚未排队时的单次同页恢复，不放宽未知提交边界。"""
from contextlib import ExitStack, contextmanager
import ast
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.auth.browser import password_auth
from core.auth.browser.browser_submission import BrowserSubmissionReceipt


EMAIL = "owner@example.test"
PASSWORD = "SyntheticPass123!"
PASSWORD_URL = "https://auth.openai.com/create-account/password"


class _Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class _Driver:
    def __init__(self, clock, *, reason="missing_password_input", ready_after_get=True):
        self.clock = clock
        self.current_url = PASSWORD_URL
        self.timeouts = SimpleNamespace(page_load=30, script=30)
        self._browser_submission_receipts = []
        self.reason = reason
        self.ready_after_get = ready_after_get
        self.ready = False
        self.identity_ok = True
        self.blocked = False
        self.ui_receipt = False
        self.get_delay = 0
        self.timeout = 30
        self.gets = []
        self.modes = []
        self.queues = []
        self.queue_identities = []
        self.queue_paths = []
        self.set_page_load_timeout = Mock(side_effect=self.set_timeout)
        self.set_script_timeout = Mock()

    def set_timeout(self, value):
        self.timeout = value

    def get(self, url):
        self.gets.append(url)
        self.clock.sleep(min(self.get_delay, self.timeout))
        self.ready = self.ready_after_get

    def execute_script(self, script, *args):
        if args and args[0] in {"input", "recovery_input"}:
            self.modes.append(args[0])
            if not self.ready:
                return {"ok": False, "reason": self.reason}
            if args[0] == "recovery_input" and not self.identity_ok:
                return {"ok": False, "reason": "login_identity_unconfirmed"}
            return {"ok": True, "reason": "password_input_ready", "input": object()}
        if args and args[0] == "queue":
            self.queues.append(args[1])
            self.queue_identities.append(args[4])
            self.queue_paths.append(args[6])
            self.current_url = "https://auth.openai.com/email-verification"
            return {"ok": True, "reason": "password_submit_queued"}
        return {"url": self.current_url, "identity_conflict": not self.identity_ok,
                "blocked_page": self.blocked, "ui_receipt_present": self.ui_receipt}


@contextmanager
def _flow(driver, clock):
    with ExitStack() as stack:
        for name, value in {
            "_registration_auth_mode": "password", "_registration_password": PASSWORD,
            "_has_access_token": False,
        }.items():
            stack.enter_context(patch.object(password_auth, name, return_value=value))
        stack.enter_context(patch.object(password_auth, "_is_email_verification_page", side_effect=lambda _driver: "email-verification" in driver.current_url))
        stack.enter_context(patch.object(password_auth, "_is_signup_password_page", return_value=True))
        stack.enter_context(patch.object(password_auth, "_is_login_password_page", return_value=False))
        stack.enter_context(patch.object(password_auth, "_password_page_state", side_effect=lambda _driver: {"url": driver.current_url, "inputs": []}))
        for name in ("_checkpoint", "_check_manual_stop", "_human_type_text", "human_delay", "log_submission_diagnostics"):
            stack.enter_context(patch.object(password_auth, name))
        stack.enter_context(patch.object(password_auth, "time", SimpleNamespace(time=clock.time, sleep=clock.sleep)))
        yield


@contextmanager
def _resume_flow(driver, clock):
    driver.current_url = "https://auth.openai.com/log-in/password"
    driver._registration_resume_login = True
    with (_flow(driver, clock),
          patch.object(password_auth, "_is_signup_password_page", return_value=False),
          patch.object(password_auth, "_is_login_password_page", return_value=True)):
        yield


class PasswordPreSubmitRecoveryTests(unittest.TestCase):
    def test_blank_or_unhydrated_form_recovers_once_then_submits_original_password(self):
        for reason in ("missing_password_input", "missing_password_form", "password_frontend_not_ready"):
            clock = _Clock()
            driver = _Driver(clock, reason=reason)
            prepared, submitted = [], []
            with self.subTest(reason=reason), _flow(driver, clock):
                result = password_auth._fill_password_page_if_present(
                    driver, EMAIL, timeout=30, on_password_prepared=prepared.append,
                    on_password_submitted=submitted.append,
                )
            self.assertEqual(result, PASSWORD)
            self.assertEqual(driver.gets, [PASSWORD_URL])
            self.assertGreaterEqual(clock.now, 10)
            self.assertIn("recovery_input", driver.modes)
            self.assertEqual(prepared, [PASSWORD])
            self.assertEqual(submitted, [PASSWORD])
            self.assertEqual(driver.queues, [PASSWORD])
            self.assertEqual(driver.queue_identities, [EMAIL])
            self.assertEqual(driver.queue_paths, ["/create-account/password"])

    def test_persistently_unready_form_uses_one_get_and_original_deadline(self):
        clock = _Clock()
        driver = _Driver(clock, ready_after_get=False)
        with _flow(driver, clock), self.assertRaisesRegex(RuntimeError, "password_form_not_ready"):
            password_auth._fill_password_page_if_present(driver, EMAIL, timeout=20)
        self.assertEqual(driver.gets, [PASSWORD_URL])
        self.assertLessEqual(clock.now, 20.4)
        self.assertEqual(driver.queues, [])
        self.assertEqual(driver._browser_submission_receipt.phase, "not_dispatched")

    def test_short_budget_never_reaches_recovery_grace(self):
        clock = _Clock()
        driver = _Driver(clock)
        with _flow(driver, clock), self.assertRaisesRegex(RuntimeError, "password_form_not_ready"):
            password_auth._fill_password_page_if_present(driver, EMAIL, timeout=3)
        self.assertEqual(driver.gets, [])
        self.assertEqual(driver.queues, [])

    def test_get_spending_remaining_budget_cannot_type_or_submit_after_deadline(self):
        clock = _Clock()
        driver = _Driver(clock)
        driver.get_delay = 100
        with _flow(driver, clock), self.assertRaisesRegex(RuntimeError, "password_form_not_ready"):
            password_auth._fill_password_page_if_present(driver, EMAIL, timeout=14)
        self.assertEqual(driver.gets, [PASSWORD_URL])
        self.assertLessEqual(clock.now, 14)
        self.assertNotIn("recovery_input", driver.modes)
        self.assertEqual(driver.queues, [])
        self.assertLessEqual(driver.set_page_load_timeout.call_args_list[0].args[0], 4)
        self.assertEqual(driver.set_page_load_timeout.call_args.args, (30,))

    def test_changed_identity_after_get_cannot_submit_or_refresh_again(self):
        clock = _Clock()
        driver = _Driver(clock)
        original_get = driver.get

        def changed(url):
            original_get(url)
            driver.identity_ok = False

        driver.get = changed
        with _flow(driver, clock), self.assertRaisesRegex(RuntimeError, "password_form_not_ready"):
            password_auth._fill_password_page_if_present(driver, EMAIL, timeout=20)
        self.assertEqual(driver.gets, [PASSWORD_URL])
        self.assertEqual(driver.queues, [])

    def test_unexpected_redirect_after_get_cannot_submit(self):
        clock = _Clock()
        driver = _Driver(clock)
        original_get = driver.get

        def redirected(url):
            original_get(url)
            driver.current_url = "https://other.test/create-account/password"

        driver.get = redirected
        with _flow(driver, clock), self.assertRaisesRegex(RuntimeError, "恢复后原身份密码页未确认"):
            password_auth._fill_password_page_if_present(driver, EMAIL, timeout=20)
        self.assertEqual(driver.queues, [])

    def helper(self, driver, receipt, *, expected_url=PASSWORD_URL):
        driver._browser_submission_receipt = receipt
        with _flow(driver, driver.clock):
            return password_auth._refresh_unsubmitted_password_form(
                driver, receipt=receipt, email=EMAIL, expected_url=expected_url, deadline=20,
            )

    def test_every_nonprepared_phase_refuses_get(self):
        for phase in ("dispatch_intent", "ui_queued", "ui_dispatched", "request_observed", "response_observed", "unknown", "confirmed", "not_dispatched"):
            driver = _Driver(_Clock())
            receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", endpoint_kind="password_submit", phase=phase)
            with self.subTest(phase=phase):
                self.assertFalse(self.helper(driver, receipt))
                self.assertEqual(driver.gets, [])
                self.assertEqual(driver.queues, [])

    def test_unknown_dom_receipt_identity_conflict_or_challenge_refuses_get(self):
        for attribute in ("ui_receipt", "blocked", "identity_ok"):
            driver = _Driver(_Clock())
            setattr(driver, attribute, attribute != "identity_ok")
            receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", endpoint_kind="password_submit")
            with self.subTest(attribute=attribute):
                self.assertFalse(self.helper(driver, receipt))
                self.assertEqual(driver.gets, [])

    def test_unresolved_previous_password_receipt_refuses_get(self):
        driver = _Driver(_Clock())
        driver._browser_submission_receipts = [BrowserSubmissionReceipt(
            kind="password", stage="password_create", endpoint_kind="password_submit", phase="unknown",
        )]
        receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", endpoint_kind="password_submit")
        self.assertFalse(self.helper(driver, receipt))
        self.assertEqual(driver.gets, [])

    def test_unresolved_previous_other_auth_receipt_refuses_get(self):
        driver = _Driver(_Clock())
        driver._browser_submission_receipts = [BrowserSubmissionReceipt(
            kind="email", stage="email", endpoint_kind="email_submit", phase="ui_queued",
        )]
        receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", endpoint_kind="password_submit")
        self.assertFalse(self.helper(driver, receipt))
        self.assertEqual(driver.gets, [])

    def resumed_email_history(self, *, status=403, phase="unknown"):
        failed = BrowserSubmissionReceipt(
            kind="resume_login", stage="submit_email", endpoint_kind="email_submit", http_method="POST",
            phase=phase, http_status=status, result="failure",
        )
        confirmed = BrowserSubmissionReceipt(
            kind="resume_login", stage="submit_email", endpoint_kind="nextauth_signin", http_method="POST",
            phase="confirmed", http_status=200, result="success",
        )
        return [failed, confirmed]

    def test_confirmed_later_resume_login_allows_get_preserving_old_403_or_429_fact(self):
        for status in (403, 429):
            for phase in ("unknown", "response_observed"):
                driver = _Driver(_Clock())
                driver._registration_resume_login = True
                driver._browser_submission_receipts = self.resumed_email_history(status=status, phase=phase)
                old, confirmed = driver._browser_submission_receipts
                receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password", endpoint_kind="password_submit")
                with self.subTest(status=status, phase=phase):
                    self.assertTrue(self.helper(driver, receipt))
                    self.assertEqual(driver.gets, [PASSWORD_URL])
                    self.assertEqual((old.phase, old.http_status, old.result), (phase, status, "failure"))
                    self.assertEqual(confirmed.phase, "confirmed")
                    self.assertEqual(receipt.phase, "prepared")

    def test_actual_resume_sequence_recovers_prepared_login_form_and_queues_once(self):
        clock = _Clock()
        driver = _Driver(clock)
        driver.current_url = "https://auth.openai.com/log-in/password"
        driver._registration_resume_login = True
        driver._browser_submission_receipts = self.resumed_email_history()
        old, confirmed = driver._browser_submission_receipts
        with _flow(driver, clock), patch.object(password_auth, "_is_signup_password_page", return_value=False), patch.object(password_auth, "_is_login_password_page", return_value=True):
            result = password_auth._fill_password_page_if_present(
                driver, EMAIL, timeout=30, existing_password=PASSWORD,
            )
        self.assertEqual(result, PASSWORD)
        self.assertEqual(driver.gets, ["https://auth.openai.com/log-in/password"])
        self.assertEqual(driver.queues, [PASSWORD])
        self.assertEqual(driver.queue_identities, [EMAIL])
        self.assertEqual(old.phase, "unknown")
        self.assertEqual(confirmed.phase, "confirmed")
        self.assertEqual(driver._browser_submission_receipt.phase, "confirmed")

    def test_failed_email_history_without_explicit_resume_or_later_confirmation_blocks_get(self):
        for variant in ("ordinary", "no_later", "wrong_order", "only_response", "new_failed", "same_submission"):
            driver = _Driver(_Clock())
            driver._registration_resume_login = variant != "ordinary"
            history = self.resumed_email_history()
            if variant == "no_later":
                history.pop()
            elif variant == "wrong_order":
                history.reverse()
            elif variant == "only_response":
                history[1].phase = "response_observed"
            elif variant == "new_failed":
                history[1].result = "failure"
            elif variant == "same_submission":
                history[1].submission_id = history[0].submission_id
            driver._browser_submission_receipts = history
            receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password", endpoint_kind="password_submit")
            with self.subTest(variant=variant):
                self.assertFalse(self.helper(driver, receipt))
                self.assertEqual(driver.gets, [])

    def test_unverified_email_failure_status_or_result_cannot_allow_get(self):
        for status, result in ((None, "failure"), (401, "failure"), (500, "failure"), (403, "unknown"), (429, "")):
            driver = _Driver(_Clock())
            driver._registration_resume_login = True
            driver._browser_submission_receipts = self.resumed_email_history(status=status)
            driver._browser_submission_receipts[0].result = result
            receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password", endpoint_kind="password_submit")
            with self.subTest(status=status, result=result):
                self.assertFalse(self.helper(driver, receipt))
                self.assertEqual(driver.gets, [])

    def test_password_otp_or_profile_unknown_still_blocks_after_confirmed_email(self):
        for endpoint in ("password_submit", "otp_submit", "otp_resend", "profile_submit"):
            driver = _Driver(_Clock())
            driver._registration_resume_login = True
            history = self.resumed_email_history()
            unresolved = BrowserSubmissionReceipt(kind="resume_login", stage="login_password", phase="unknown", http_method="POST", http_status=403, result="failure")
            unresolved.endpoint_kind = endpoint
            history.insert(1, unresolved)
            driver._browser_submission_receipts = history
            receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password", endpoint_kind="password_submit")
            with self.subTest(endpoint=endpoint):
                self.assertFalse(self.helper(driver, receipt))
                self.assertEqual(driver.gets, [])

    def test_foreign_unexpected_or_changed_route_refuses_get(self):
        for url in ("https://auth.openai.com.evil.test/create-account/password", "https://auth.openai.com/api/accounts/user/register", "https://auth.openai.com/email-verification", "https://user@auth.openai.com/create-account/password", "https://auth.openai.com:444/create-account/password"):
            driver = _Driver(_Clock())
            driver.current_url = url
            receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", endpoint_kind="password_submit")
            with self.subTest(url=url):
                self.assertFalse(self.helper(driver, receipt, expected_url=url))
                self.assertEqual(driver.gets, [])

    def test_missing_snapshot_fields_cannot_prove_no_dispatch(self):
        driver = _Driver(_Clock())
        driver.execute_script = Mock(return_value={"url": PASSWORD_URL})
        receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", endpoint_kind="password_submit")
        self.assertFalse(self.helper(driver, receipt))
        self.assertEqual(driver.gets, [])

    def test_snapshot_spending_remaining_budget_cannot_start_get(self):
        driver = _Driver(_Clock())
        driver.clock.now = 18.5
        original = driver.execute_script

        def slow(script, *args):
            driver.clock.sleep(1.5)
            return original(script, *args)

        driver.execute_script = slow
        receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", endpoint_kind="password_submit")
        self.assertFalse(self.helper(driver, receipt))
        self.assertEqual(driver.gets, [])
        self.assertEqual(driver.clock.now, 20)
        self.assertEqual([call.args[0] for call in driver.set_script_timeout.call_args_list], [1.5, 30])

    def test_late_dispatch_fact_before_get_cannot_be_ignored(self):
        driver = _Driver(_Clock())
        receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", endpoint_kind="password_submit")
        driver._browser_submission_receipt = receipt
        with _flow(driver, driver.clock), patch.object(password_auth, "log_submission_diagnostics", side_effect=lambda *_args, **_kw: receipt.transition("dispatch_intent")):
            result = password_auth._refresh_unsubmitted_password_form(
                driver, receipt=receipt, email=EMAIL, expected_url=PASSWORD_URL, deadline=20,
            )
        self.assertFalse(result)
        self.assertEqual(driver.gets, [])

    def test_missing_session_closes_prepared_receipt_and_submits_new_form_once_with_saved_password(self):
        clock, prepared, submitted, old_receipts = _Clock(), [], [], []
        driver = _Driver(clock)
        driver._browser_submission_receipts = self.resumed_email_history()
        old_failure = driver._browser_submission_receipts[0]

        def restart(_driver, email, *, budget, allow_password_route):
            self.assertEqual(email, EMAIL)
            self.assertTrue(allow_password_route)
            self.assertEqual(budget.deadline, 180)
            old_receipts.append(driver._browser_submission_receipt)
            self.assertEqual(old_receipts[-1].phase, "not_dispatched")
            self.assertEqual(driver.queues, [])
            self.assertEqual(submitted, [])
            driver._registration_auth_restart_count = 1
            driver.ready = True
            return True

        with (_resume_flow(driver, clock),
              patch.object(password_auth, "auth_session_missing", side_effect=[True, False, False]),
              patch.object(password_auth, "_restart_expired_resume_auth", side_effect=restart) as restarted,
              patch.object(password_auth, "_registration_password") as generated):
            result = password_auth._fill_password_page_if_present(
                driver, EMAIL, timeout=30, existing_password=PASSWORD,
                on_password_prepared=prepared.append, on_password_submitted=submitted.append,
            )
        self.assertEqual(result, PASSWORD)
        restarted.assert_called_once()
        generated.assert_not_called()
        self.assertEqual((driver.gets, driver.queues), ([], [PASSWORD]))
        self.assertEqual(driver.queue_identities, [EMAIL])
        self.assertEqual(driver.queue_paths, ["/log-in/password"])
        self.assertEqual((prepared, submitted), ([PASSWORD], [PASSWORD]))
        self.assertIsNot(old_receipts[0], driver._browser_submission_receipt)
        self.assertEqual(old_receipts[0].phase, "not_dispatched")
        self.assertEqual(old_failure.phase, "unknown")

    def test_missing_session_new_ready_otp_does_not_revisit_password_or_claim_password_submission(self):
        clock = _Clock()
        driver = _Driver(clock)
        submitted = []

        def restart(*_args, **_kwargs):
            self.assertEqual(driver._browser_submission_receipt.phase, "not_dispatched")
            driver._registration_auth_restart_count = 1
            driver._registration_resume_password_attempted = False
            driver.current_url = "https://auth.openai.com/email-verification"
            return True

        with (_resume_flow(driver, clock),
              patch.object(password_auth, "auth_session_missing", return_value=True),
              patch.object(password_auth, "_restart_expired_resume_auth", side_effect=restart),
              patch.object(password_auth, "_wait_email_otp_page_ready", return_value="ready") as ready,
              patch.object(password_auth, "_resume_login_password_url") as offered):
            result = password_auth._fill_password_page_if_present(
                driver, EMAIL, existing_password=PASSWORD, on_password_submitted=submitted.append,
            )
        self.assertEqual(result, PASSWORD)
        ready.assert_called_once()
        offered.assert_not_called()
        self.assertTrue(driver._registration_resume_password_attempted)
        self.assertEqual((driver.gets, driver.queues, submitted), ([], [], []))
        self.assertEqual(driver._browser_submission_receipt.phase, "not_dispatched")

    def test_missing_session_arriving_after_typing_restarts_before_first_dispatch_then_submits_once(self):
        clock = _Clock()
        driver = _Driver(clock)
        driver.ready = True
        missing, events, submitted, old_receipts = [False], [], [], []

        def delay(*_args, **_kwargs):
            if "missing_arrived" not in events:
                missing[0] = True
                events.append("missing_arrived")

        def restart(_driver, email, **_kwargs):
            self.assertEqual(driver.queues, [])
            self.assertEqual(submitted, [])
            old_receipts.append(driver._browser_submission_receipt)
            self.assertEqual(old_receipts[-1].phase, "not_dispatched")
            events.append("restarted")
            driver._registration_auth_restart_count = 1
            missing[0] = False
            return True

        with (_resume_flow(driver, clock),
              patch.object(password_auth, "auth_session_missing", side_effect=lambda _driver: missing[0]),
              patch.object(password_auth, "_human_type_text", side_effect=lambda *_args, **_kw: events.append("typed")),
              patch.object(password_auth, "human_delay", side_effect=delay),
              patch.object(password_auth, "_restart_expired_resume_auth", side_effect=restart) as restarted):
            result = password_auth._fill_password_page_if_present(
                driver, EMAIL, existing_password=PASSWORD, on_password_submitted=submitted.append,
            )
        self.assertEqual(result, PASSWORD)
        self.assertEqual(events, ["typed", "missing_arrived", "restarted", "typed"])
        restarted.assert_called_once()
        self.assertEqual(driver.queues, [PASSWORD])
        self.assertEqual(submitted, [PASSWORD])
        self.assertEqual(driver.modes, ["input", "recovery_input"])
        self.assertIsNot(old_receipts[0], driver._browser_submission_receipt)
        self.assertEqual(old_receipts[0].phase, "not_dispatched")

    def test_missing_session_restarts_at_most_twice_without_renewing_initial_deadline(self):
        clock = _Clock()
        driver = _Driver(clock)
        deadlines, remaining = [], []

        def restart(*_args, budget, **_kwargs):
            self.assertEqual(driver._browser_submission_receipt.phase, "not_dispatched")
            deadlines.append(budget.deadline)
            remaining.append(budget.remaining())
            driver._registration_auth_restart_count = len(deadlines)
            clock.sleep(20)
            return True

        with (_resume_flow(driver, clock),
              patch.object(password_auth, "auth_session_missing", return_value=True),
              patch.object(password_auth, "_restart_expired_resume_auth", side_effect=restart) as restarted,
              self.assertRaisesRegex(RuntimeError, "auth_session_unavailable")):
            password_auth._fill_password_page_if_present(driver, EMAIL, existing_password=PASSWORD)
        self.assertEqual(restarted.call_count, 2)
        self.assertEqual(deadlines, [180, 180])
        self.assertEqual(remaining, [180, 160])
        self.assertEqual(clock.now, 40)
        self.assertEqual((driver.gets, driver.queues), ([], []))
        self.assertEqual(driver._browser_submission_receipt.phase, "not_dispatched")

    def test_missing_session_restart_spending_fixed_budget_cannot_wait_or_submit_afterward(self):
        clock = _Clock()
        driver = _Driver(clock)

        def restart(*_args, budget, **_kwargs):
            clock.sleep(budget.remaining())
            driver.ready = True
            return True

        with (_resume_flow(driver, clock),
              patch.object(password_auth, "auth_session_missing", return_value=True),
              patch.object(password_auth, "_restart_expired_resume_auth", side_effect=restart) as restarted,
              self.assertRaisesRegex(RuntimeError, "auth_session_unavailable")):
            password_auth._fill_password_page_if_present(driver, EMAIL, existing_password=PASSWORD)
        restarted.assert_called_once()
        self.assertEqual(clock.now, 180)
        self.assertEqual((driver.gets, driver.queues), ([], []))

    def test_missing_session_cannot_bypass_ui_receipt_identity_challenge_history_or_origin(self):
        for variant in ("ui_receipt", "identity", "challenge", "history", "foreign", "other_route"):
            clock = _Clock()
            driver = _Driver(clock)
            with self.subTest(variant=variant), _resume_flow(driver, clock):
                if variant == "ui_receipt":
                    driver.ui_receipt = True
                elif variant == "identity":
                    driver.identity_ok = False
                elif variant == "challenge":
                    driver.blocked = True
                elif variant == "history":
                    driver._browser_submission_receipts = [BrowserSubmissionReceipt(
                        kind="resume_login", stage="email_otp", endpoint_kind="otp_submit", phase="unknown",
                    )]
                elif variant == "foreign":
                    driver.current_url = "https://other.test/log-in/password"
                else:
                    driver.current_url = PASSWORD_URL
                with (patch.object(password_auth, "auth_session_missing", return_value=True),
                      patch.object(password_auth, "_restart_expired_resume_auth") as restarted,
                      self.assertRaisesRegex(RuntimeError, "auth_session_unavailable")):
                    password_auth._fill_password_page_if_present(driver, EMAIL, existing_password=PASSWORD)
            restarted.assert_not_called()
            self.assertEqual((driver.gets, driver.queues), ([], []))

    def test_missing_session_cannot_recover_queued_dispatched_or_unknown_current_receipt(self):
        for phase in ("dispatch_intent", "ui_queued", "ui_dispatched", "unknown"):
            clock = _Clock()
            driver = _Driver(clock)

            def advanced(_driver, _stage, point, *, receipt=None):
                if point == "before_submit":
                    receipt.transition(phase)

            with (self.subTest(phase=phase), _resume_flow(driver, clock),
                  patch.object(password_auth, "auth_session_missing", return_value=True),
                  patch.object(password_auth, "log_submission_diagnostics", side_effect=advanced),
                  patch.object(password_auth, "_restart_expired_resume_auth") as restarted,
                  self.assertRaisesRegex(RuntimeError, "password_form_not_ready")):
                password_auth._fill_password_page_if_present(driver, EMAIL, existing_password=PASSWORD)
            restarted.assert_not_called()
            self.assertEqual((driver.gets, driver.queues), ([], []))
            self.assertEqual(driver._browser_submission_receipt.phase, phase)

    def test_plain_404_stale_missing_or_newer_success_does_not_restart_password_login(self):
        from core.auth.browser.submission_recovery import SubmissionDiagnostics, begin_auth_session

        for variant in ("plain_404", "old_session", "newer_success"):
            clock = _Clock()
            driver = _Driver(clock)
            diagnostics = SubmissionDiagnostics()
            driver._registration_submission_diagnostics = diagnostics
            item = {"url": "https://auth.openai.com/api/accounts/client_auth_session_dump",
                    "method": "GET", "request_id": "old", "target_id": "target", "status": 404}
            if variant != "plain_404":
                item["auth_error"] = {"code": "missing_session"}
            diagnostics.observe_network(item, phase="request")
            diagnostics.observe_network(item, phase="complete")
            if variant == "old_session":
                begin_auth_session(driver)
            elif variant == "newer_success":
                current = {**item, "request_id": "current", "status": 200, "auth_error": {}}
                diagnostics.observe_network(current, phase="request")
                diagnostics.observe_network(current, phase="complete")
            driver.ready = True
            with (self.subTest(variant=variant), _resume_flow(driver, clock),
                  patch.object(password_auth, "_restart_expired_resume_auth") as restarted):
                result = password_auth._fill_password_page_if_present(driver, EMAIL, existing_password=PASSWORD)
            self.assertEqual(result, PASSWORD)
            restarted.assert_not_called()
            self.assertEqual(driver.queues, [PASSWORD])


@unittest.skipUnless(shutil.which("node"), "需要 Node 执行实际恢复前只读脚本")
class PasswordPreSubmitSnapshotScriptTests(unittest.TestCase):
    def recovery_target(self, mode, identities):
        module = ast.parse(Path(password_auth.__file__).read_text())
        script = next(node.value for node in ast.walk(module) if isinstance(node, ast.Constant)
                      and isinstance(node.value, str) and "missing_password_input" in node.value
                      and "password_targets" in node.value)
        source = r"""
        const fixture = FIXTURE;
        const window = {}, timers = [];
        const setTimeout = callback => timers.push(callback);
        const location = {protocol:'https:',hostname:'auth.openai.com',port:'',pathname:'/create-account/password'};
        const getComputedStyle = () => ({visibility:'visible',display:'block'});
        const form = {isConnected:true, __reactProps$test:{onSubmit(){}}, checkValidity:()=>true,
          addEventListener(){}, removeEventListener(){}};
        const input = {id:'password',type:'password',name:'password',autocomplete:'new-password',
          isConnected:true,offsetWidth:100,offsetHeight:30,disabled:false,readOnly:false,
          matches:()=>false,getClientRects:()=>[{}],getAttribute:()=>'',closest:()=>form,form,
          value:'SyntheticPass123!',validity:{valid:true}};
        const button = {isConnected:true,offsetWidth:100,offsetHeight:30,disabled:false,
          readOnly:false,type:'submit',form,textContent:'Continue',matches:()=>false,
          getClientRects:()=>[{}],getAttribute:()=>'',scrollIntoView(){},contains:el=>el===button,
          getBoundingClientRect:()=>({left:0,top:0,width:100,height:30}),click(){}};
        form.querySelectorAll = selector => selector === 'input' ? fixture.identities.concat([input]) : [button];
        const document = {querySelectorAll:()=>[input],elementFromPoint:()=>button};
        const execute = function(){SCRIPT};
        const result = execute(fixture.mode,'SyntheticPass123!',input,'test-id','owner@example.test',true,'/create-account/password');
        console.log(JSON.stringify({ok:result.ok,reason:result.reason,
          phase:window.__turbPasswordSubmissionReceipt?.phase || null}));
        """.replace("FIXTURE", json.dumps({"mode": mode, "identities": identities})).replace("SCRIPT", script)
        result = subprocess.run([shutil.which("node"), "-e", source], capture_output=True, text=True, check=True, timeout=10)
        return json.loads(result.stdout)

    def test_recovery_input_and_queue_reject_mixed_hidden_and_readonly_identities(self):
        for mode in ("recovery_input", "queue"):
            for conflicting in (
                {"type": "email", "name": "email", "readOnly": True, "value": "other@example.test"},
                {"type": "email", "name": "contact", "value": "other@example.test"},
                {"type": "text", "name": "contact", "autocomplete": "username", "value": "other@example.test"},
            ):
                result = self.recovery_target(mode, [
                    {"type": "hidden", "name": "username", "value": EMAIL}, conflicting,
                ])
                with self.subTest(mode=mode, conflicting=conflicting):
                    self.assertEqual(result, {"ok": False, "reason": "login_identity_unconfirmed", "phase": None})

    def test_recovery_input_and_queue_require_nonempty_consistent_identity(self):
        for mode in ("recovery_input", "queue"):
            for identities in ([], [{"name": "username", "value": " "}]):
                with self.subTest(mode=mode, identities=identities):
                    self.assertEqual(self.recovery_target(mode, identities),
                                     {"ok": False, "reason": "login_identity_unconfirmed", "phase": None})
            accepted = self.recovery_target(mode, [
                {"type": "hidden", "name": "username", "value": EMAIL},
                {"type": "email", "name": "email", "readOnly": True, "value": " OWNER@EXAMPLE.TEST "},
                {"type": "email", "name": "email", "value": " "},
            ])
            self.assertTrue(accepted["ok"])
            self.assertEqual(accepted["phase"], "dispatched" if mode == "queue" else None)

    def evaluate(self, **fixture):
        module = ast.parse(Path(password_auth.__file__).read_text())
        script = next(node.value for node in ast.walk(module) if isinstance(node, ast.Constant)
                      and isinstance(node.value, str) and "identity_conflict:" in node.value
                      and "ui_receipt_present:" in node.value)
        source = r"""
        const fixture = FIXTURE;
        const window = {};
        if (fixture.receipt) window.__turbPasswordSubmissionReceipt = {};
        const location = {href:'https://auth.openai.com/create-account/password'};
        const getComputedStyle = () => ({visibility:'visible',display:'block'});
        const document = {body:{innerText:fixture.text || ''},querySelectorAll:selector => {
          if (selector === 'input') return (fixture.identities || []).map(value =>
            ({readOnly:true,value,type:'text',name:'username',autocomplete:'username'}));
          return fixture.challengeFrame ? [{offsetWidth:100,offsetHeight:100}] : [];
        }};
        const execute = function(){SCRIPT};
        console.log(JSON.stringify(execute('owner@example.test')));
        """.replace("FIXTURE", json.dumps(fixture)).replace("SCRIPT", script)
        result = subprocess.run([shutil.which("node"), "-e", source], capture_output=True, text=True, check=True, timeout=10)
        return json.loads(result.stdout)

    def test_actual_script_distinguishes_original_and_conflicting_identity(self):
        self.assertFalse(self.evaluate(identities=[EMAIL])["identity_conflict"])
        self.assertFalse(self.evaluate(identities=[])["identity_conflict"])
        self.assertTrue(self.evaluate(identities=["other@example.test"])["identity_conflict"])

    def test_actual_script_preserves_challenge_and_unknown_receipt_boundaries(self):
        self.assertTrue(self.evaluate(text="Verify you are human")["blocked_page"])
        self.assertTrue(self.evaluate(text="Enable JavaScript and cookies to continue")["blocked_page"])
        self.assertTrue(self.evaluate(challengeFrame=True)["blocked_page"])
        self.assertTrue(self.evaluate(receipt=True)["ui_receipt_present"])

    def test_actual_queue_script_refuses_changed_recovery_origin_or_path(self):
        module = ast.parse(Path(password_auth.__file__).read_text())
        script = next(node.value for node in ast.walk(module) if isinstance(node, ast.Constant)
                      and isinstance(node.value, str) and "missing_password_input" in node.value
                      and "password_targets" in node.value)
        for location in (
            {"protocol": "https:", "hostname": "other.test", "port": "", "pathname": "/create-account/password"},
            {"protocol": "http:", "hostname": "auth.openai.com", "port": "", "pathname": "/create-account/password"},
            {"protocol": "https:", "hostname": "auth.openai.com", "port": "444", "pathname": "/create-account/password"},
            {"protocol": "https:", "hostname": "auth.openai.com", "port": "", "pathname": "/email-verification"},
        ):
            source = "const location=" + json.dumps(location) + "; const execute=function(){" + script + "};console.log(JSON.stringify(execute('queue','SyntheticPass123!',null,'id','owner@example.test',false,'/create-account/password')));"
            result = subprocess.run([shutil.which("node"), "-e", source], capture_output=True, text=True, check=True, timeout=10)
            with self.subTest(location=location):
                self.assertEqual(json.loads(result.stdout), {"ok": False, "reason": "password_recovery_route_unconfirmed"})
