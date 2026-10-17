"""提交后的刷新、回退、原回执保留、剩余预算与脱敏接口观测。"""
import json
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.browser_traffic import _SummaryOnlyCDPSession
from core.registration.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from core.registration import submission_recovery as recovery
from core.registration import email_otp, password_auth
from core.registration_debug import _RoxyTargetCollector
from core.registration.state_machine import CancellationRequested, StageBudget
from selenium.common.exceptions import TimeoutException


class _Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def _driver(url="https://auth.openai.com/create-account/password"):
    driver = SimpleNamespace(
        current_url=url, timeouts=SimpleNamespace(page_load=30),
        set_page_load_timeout=Mock(), execute_script=Mock(return_value={"url": url}),
        execute_cdp_cmd=Mock(return_value={"currentIndex": 0, "entries": []}),
        submit=Mock(), refresh=Mock(), back=Mock(),
    )
    driver.get = Mock(side_effect=lambda target: setattr(driver, "current_url", target))
    return driver


class SubmissionPageRecoveryTests(unittest.TestCase):
    def run_recovery(self, driver, clock, observe, **kwargs):
        with patch.object(recovery, "_check_manual_stop"):
            return recovery.recover_submission_page(
                driver, kwargs.pop("stage", "password"), observe,
                budget=StageBudget(kwargs.pop("deadline", 20), clock=clock.time),
                sleeper=clock.sleep, **kwargs,
            )

    def test_refresh_uses_current_auth_get_and_confirms_original_receipt(self):
        driver, clock = _driver(), _Clock()
        receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", phase="ui_dispatched")
        phases = []

        def observe(_budget):
            if driver.get.called:
                record_browser_submission_fact(driver, "confirmed", receipt=receipt, result="success")
                return "otp"
            return None

        original_record = recovery.record_browser_submission_fact
        with patch.object(recovery, "record_browser_submission_fact", side_effect=lambda *a, **k: (
            phases.append(a[1]), original_record(*a, **k)
        )[1]):
            result = self.run_recovery(driver, clock, observe, receipt=receipt)
        self.assertEqual(result, "otp")
        self.assertEqual(phases, ["unknown"])
        self.assertEqual(receipt.phase, "confirmed")
        driver.get.assert_called_once_with("https://auth.openai.com/create-account/password")
        driver.submit.assert_not_called()
        driver.refresh.assert_not_called()
        self.assertEqual(driver.set_page_load_timeout.call_args.args, (30,))

    def test_profile_refresh_then_back_checks_session_without_reposting(self):
        driver, clock = _driver("https://chatgpt.com/auth/error"), _Clock()
        previous = "https://auth.openai.com/about-you"
        driver.execute_cdp_cmd.return_value = {
            "currentIndex": 2, "entries": [{"url": "https://evil.test/"}, {"url": previous},
                                           {"url": driver.current_url}],
        }
        result = self.run_recovery(driver, clock, lambda _budget: (
            "session" if driver.current_url == previous else None
        ), stage="profile", allow_back=True)
        self.assertEqual(result, "session")
        self.assertEqual([call.args[0] for call in driver.get.call_args_list],
                         ["https://chatgpt.com/auth/error", previous])
        self.assertLessEqual(clock.now, 20)
        driver.submit.assert_not_called()
        driver.back.assert_not_called()

    def test_no_progress_keeps_unknown_receipt_and_spends_only_remaining_budget(self):
        driver, clock = _driver(), _Clock()
        receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", phase="ui_dispatched")
        result = self.run_recovery(driver, clock, lambda _budget: None, deadline=4, receipt=receipt)
        self.assertIsNone(result)
        self.assertEqual(clock.now, 4)
        self.assertEqual(receipt.phase, "unknown")
        driver.get.assert_called_once()
        driver.submit.assert_not_called()

    def test_advanced_page_is_accepted_before_navigation(self):
        driver, clock = _driver(), _Clock()
        result = self.run_recovery(driver, clock, lambda _budget: "otp")
        self.assertEqual(result, "otp")
        driver.get.assert_not_called()

    def test_slow_observation_exhausting_budget_cannot_start_navigation(self):
        driver, clock = _driver(), _Clock()

        def observe(_budget):
            clock.sleep(5)
            return None

        self.assertIsNone(self.run_recovery(driver, clock, observe, deadline=5))
        driver.get.assert_not_called()

    def test_foreign_origin_or_expired_budget_does_not_navigate(self):
        for url, deadline in (("https://auth.openai.com.evil.test/", 20),
                              ("https://auth.openai.com/api/accounts/email-otp/send", 20),
                              ("https://chatgpt.com/api/auth/callback?code=private-code", 20),
                              ("https://auth.openai.com/", 0)):
            with self.subTest(url=url, deadline=deadline):
                driver, clock = _driver(url), _Clock()
                self.assertIsNone(self.run_recovery(driver, clock, Mock(), deadline=deadline))
                driver.get.assert_not_called()

    def test_identity_or_fact_errors_propagate_without_more_navigation(self):
        driver, clock = _driver(), _Clock()
        with self.assertRaisesRegex(RuntimeError, "身份不匹配"):
            self.run_recovery(driver, clock, Mock(side_effect=RuntimeError("身份不匹配")))
        driver.get.assert_not_called()

    def test_navigation_timeout_is_observed_and_old_timeout_is_restored(self):
        driver, clock = _driver(), _Clock()
        driver.get.side_effect = TimeoutError("私有错误内容")
        with self.assertLogs(recovery.logger, level="WARNING") as logs:
            result = self.run_recovery(driver, clock, lambda _budget: "otp" if driver.get.called else None)
        self.assertEqual(result, "otp")
        self.assertNotIn("私有错误内容", " ".join(logs.output))
        self.assertEqual(driver.set_page_load_timeout.call_args.args, (30,))

    def test_budget_cancellation_stops_before_get(self):
        driver, clock = _driver(), _Clock()
        with patch.object(recovery, "_check_manual_stop"), self.assertRaises(CancellationRequested):
            recovery.recover_submission_page(driver, "password", Mock(),
                budget=StageBudget(20, clock=clock.time, cancellation=lambda: True), sleeper=clock.sleep)
        driver.get.assert_not_called()

    def test_foreign_redirect_cannot_be_confirmed_as_next_auth_step(self):
        driver, clock = _driver(), _Clock()
        driver.get.side_effect = lambda _url: setattr(driver, "current_url", "https://other.test/about-you")
        observe = Mock(side_effect=lambda _budget: "profile" if driver.get.called else None)
        self.assertIsNone(self.run_recovery(driver, clock, observe))
        self.assertEqual(observe.call_count, 1)


class SubmissionDiagnosticsTests(unittest.TestCase):
    def test_readonly_driver_adapter_does_not_fail_when_diagnostics_cannot_be_attached(self):
        safe = recovery.log_submission_diagnostics(object(), "otp", "waiting")
        self.assertEqual(safe['capture_error'], 'AttributeError')
        self.assertFalse(recovery.auth_session_unavailable(object()))

    def test_diagnostic_capture_has_short_timeout_and_restores_original_setting(self):
        driver = _driver()
        driver.timeouts.script = 30
        driver.set_script_timeout = Mock()
        driver.execute_script.side_effect = TimeoutError("private-token")
        safe = recovery.log_submission_diagnostics(driver, "password", "waiting")
        self.assertEqual([call.args[0] for call in driver.set_script_timeout.call_args_list], [2.0, 30])
        self.assertEqual(safe["capture_error"], "TimeoutError")
        self.assertNotIn("private-token", json.dumps(safe))

    def test_snapshot_and_network_keep_only_non_private_metadata(self):
        driver = _driver()
        driver.execute_script.return_value = {
            "url": "https://auth.openai.com/create-account/password?email=private@example.test&token=private-token",
            "ready_state": "complete", "text_length": 145, "html_length": 5000,
            "text": "private@example.test private-password", "title": "private-token",
            "controls": [{"type": "password", "value": "private-password", "disabled": True,
                          "read_only": False, "value_present": True, "valid": True}],
            "error_markers": ["invalid_auth_step", "private-token"],
            "resources": [{"url": "https://auth.openai.com/api/accounts/password?code=private-code", "duration_ms": 321, "status": 0}],
        }
        diagnostics = recovery.diagnostics_for(driver)
        diagnostics.observe_network({
            "url": "https://auth.openai.com/api/accounts/password?token=private-token", "method": "POST",
            "request_id": "request", "target_id": "target", "status": 400,
            "request_body": "private-password", "request_headers": {"Cookie": "private-cookie"},
        }, phase="response")
        with self.assertLogs(recovery.logger, level="INFO") as logs:
            safe = recovery.log_submission_diagnostics(driver, "password", "waiting",
                ui={"phase": "dispatched", "input_matches": True, "password": "private-password"})
        encoded = json.dumps(safe) + " ".join(logs.output)
        for private in ("private@example.test", "private-password", "private-token", "private-code", "private-cookie"):
            self.assertNotIn(private, encoded)
        self.assertIsNone(safe["resources"][0]["status"])
        self.assertEqual(safe["network"][0]["status"], 400)
        self.assertEqual(safe["controls"][0]["disabled"], True)

    def test_network_buffer_is_bounded_and_ignores_foreign_origins(self):
        diagnostics = recovery.SubmissionDiagnostics()
        for index in range(45):
            diagnostics.observe_network({"url": "https://auth.openai.com/api/accounts/authorize",
                "method": "POST", "request_id": str(index)}, phase="request")
        diagnostics.observe_network({"url": "https://other.test/api/auth/signin", "method": "POST"}, phase="request")
        self.assertEqual(len(diagnostics.network), 40)
        self.assertEqual(len(diagnostics.recent_network()), 20)

    def test_auth_session_failure_is_superseded_by_a_new_pending_or_successful_request(self):
        driver = _driver()
        diagnostics = recovery.diagnostics_for(driver)
        record = {"url": "https://auth.openai.com/api/accounts/client_auth_session_dump", "method": "GET",
                  "request_id": "old", "status": 404}
        diagnostics.observe_network(record, phase="response")
        self.assertTrue(recovery.auth_session_unavailable(driver))
        diagnostics.observe_network({**record, "request_id": "new", "status": None}, phase="request")
        self.assertFalse(recovery.auth_session_unavailable(driver))
        diagnostics.observe_network({**record, "request_id": "new", "status": 200}, phase="response")
        self.assertFalse(recovery.auth_session_unavailable(driver))
        diagnostics.observe_network(record, phase="complete")
        self.assertFalse(recovery.auth_session_unavailable(driver))

    def test_new_login_preserves_old_diagnostics_without_reusing_their_session_failure(self):
        driver = _driver()
        diagnostics = recovery.diagnostics_for(driver)
        record = {"url": "https://auth.openai.com/api/accounts/client_auth_session_dump", "method": "GET",
                  "request_id": "old", "status": 404}
        diagnostics.observe_network(record, phase="response")
        recovery.begin_auth_session(driver)
        diagnostics.observe_network(record, phase="complete")
        self.assertFalse(recovery.auth_session_unavailable(driver))
        self.assertEqual(diagnostics.recent_network()[0]["status"], 404)
        diagnostics.observe_network({**record, "request_id": "new"}, phase="response")
        self.assertTrue(recovery.auth_session_unavailable(driver))

    def test_other_origin_auth_session_failure_cannot_stop_this_auth_flow(self):
        driver = _driver()
        recovery.diagnostics_for(driver).observe_network({
            "url": "https://chatgpt.com/api/accounts/client_auth_session_dump", "method": "GET",
            "request_id": "other", "status": 404,
        }, phase="response")
        self.assertFalse(recovery.auth_session_unavailable(driver))

    def test_shared_cdp_records_unknown_auth_endpoints_and_response_headers(self):
        diagnostics = recovery.SubmissionDiagnostics()
        session = _SummaryOnlyCDPSession("unit-profile")
        session.auth_diagnostic_observer = diagnostics.observe_network
        record = {"url": "https://auth.openai.com/api/accounts/user/register", "method": "POST",
                  "request_id": "request", "target_id": "target"}
        session._observe_submission(record)
        self.assertEqual(diagnostics.recent_network()[0]["phase"], "request")
        record["status"] = 503
        session._observe_auth_diagnostic(record, phase="response")
        self.assertEqual(diagnostics.recent_network()[0]["status"], 503)
        session._observe_submission({**record, "duration_ms": 2000, "failure": "net::ERR_TIMED_OUT private-token"}, response=True)
        summary = diagnostics.recent_network()[0]
        self.assertEqual(summary["duration_ms"], 2000)
        self.assertEqual(summary["network_error"], "net::ERR_TIMED_OUT")
        self.assertEqual(summary["phase"], "complete")

    def test_cdp_header_event_is_recorded_while_response_body_is_pending(self):
        diagnostics = recovery.SubmissionDiagnostics()
        session = _SummaryOnlyCDPSession("unit-profile")
        session.auth_diagnostic_observer = diagnostics.observe_network
        collector = _RoxyTargetCollector(SimpleNamespace(session=session), "target", "ws://unit-only", "page")
        collector._handle({"method": "Network.requestWillBeSent", "params": {
            "requestId": "request", "type": "Fetch", "request": {
                "url": "https://auth.openai.com/api/accounts/password", "method": "POST",
            },
        }})
        collector._handle({"method": "Network.responseReceived", "params": {
            "requestId": "request", "response": {"status": 504},
        }})
        self.assertEqual(diagnostics.recent_network()[0]["status"], 504)
        self.assertEqual(diagnostics.recent_network()[0]["phase"], "response")
        self.assertIn("request", collector._requests)

    def test_tokens_in_path_are_fingerprinted(self):
        safe = recovery._safe_location("https://auth.openai.com/api/accounts/privatelettertoken")
        self.assertNotIn("privatelettertoken", json.dumps(safe))
        self.assertEqual(safe["path"], "其他认证路径")

    def test_long_diagnostics_remain_valid_json_after_task_log_limit(self):
        from core.task_run_log import redact_text

        driver = _driver()
        driver.execute_script.return_value = {
            "controls": [{"type": "password", "value_present": True, "disabled": True}] * 20,
            "resources": [{"url": "https://auth.openai.com/api/accounts/authorize", "status": 200}] * 10,
        }
        diagnostics = recovery.diagnostics_for(driver)
        for index in range(20):
            diagnostics.observe_network({"url": "https://auth.openai.com/api/accounts/email-otp/resend",
                "method": "POST", "request_id": str(index), "status": 409, "duration_ms": 9000}, phase="response")
        with self.assertLogs(recovery.logger, level="INFO") as logs:
            safe = recovery.log_submission_diagnostics(driver, "otp", "final_failure")
        records = []
        for record in logs.records:
            message = record.getMessage()
            self.assertLess(len(message), 3000)
            records.append(json.loads(redact_text(message).split("认证提交诊断：", 1)[1]))
        self.assertEqual(len({record["capture_id"] for record in records}), 1)
        network = [item for record in records if record["section"] == "network" for item in record["items"]]
        self.assertEqual(network, safe["network"])
        self.assertEqual(len(network), 20)
        self.assertTrue(all(item["status"] == 409 for item in network))


class SubmissionRecoveryIntegrationTests(unittest.TestCase):
    def _resume_with_offered_password(self, *, navigation_timeout=False, visible_password=True, expired_once=False,
                                     create_password=False):
        driver, clock = _driver("https://auth.openai.com/email-verification"), _Clock()
        driver._registration_resume_login = True
        queues = []
        target = "https://auth.openai.com/" + ("create-account/password" if create_password else "log-in/password")

        if navigation_timeout:
            def navigate(target):
                driver.current_url = target
                if target == "about:blank":
                    return
                raise TimeoutException("模拟页面已有表单但其余资源仍在加载")
            driver.get.side_effect = navigate

        def execute(_script, *args):
            if args and args[0] == "queue":
                queues.append(True)
                driver.current_url = "https://auth.openai.com/email-verification"
                return {"ok": True, "reason": "password_submit_queued"}
            if args and args[0] == "input":
                return {"ok": True, "input": object()}
            return {"phase": "dispatched", "click_called": True, "submit_event_observed": True,
                    "submit_default_prevented": True, "submitter_matches": True}

        driver.execute_script.side_effect = execute
        with ExitStack() as stack:
            stack.enter_context(patch.object(password_auth, "time", clock))
            stack.enter_context(patch.object(password_auth, "_registration_auth_mode", return_value="password"))
            generate = stack.enter_context(patch.object(password_auth, "_registration_password"))
            stack.enter_context(patch.object(password_auth, "_password_transition_timeout_seconds", return_value=30))
            stack.enter_context(patch.object(password_auth, "_password_page_state", side_effect=lambda _d: {
                "url": driver.current_url,
                "inputs": [{"type": "text", "name": "code", "visible": True}] if "email-verification" in driver.current_url else (
                    [{"type": "password", "visible": True}] if visible_password else []),
            }))
            stack.enter_context(patch.object(password_auth, "_wait_email_otp_page_ready",
                                            side_effect=["session_expired", "ready"] if expired_once else None,
                                            return_value="ready"))
            def submit_email(*_args, **_kwargs):
                driver.current_url = "https://auth.openai.com/email-verification"
                return "otp"
            stack.enter_context(patch.object(email_otp, "_submit_email_and_wait_next", side_effect=submit_email))
            stack.enter_context(patch.object(password_auth, "_resume_login_password_url", return_value=None if create_password else target))
            if create_password:
                stack.enter_context(patch.object(password_auth, "_offered_password_url", return_value=target))
            stack.enter_context(patch.object(password_auth, "_is_signup_password_page",
                                            side_effect=lambda _d: "create-account/password" in driver.current_url))
            stack.enter_context(patch.object(password_auth, "_is_login_password_page", side_effect=lambda _d: "log-in/password" in driver.current_url))
            stack.enter_context(patch.object(password_auth, "_is_email_verification_page", side_effect=lambda _d: "email-verification" in driver.current_url))
            stack.enter_context(patch.object(password_auth, "_has_access_token", return_value=False))
            for name in ("human_delay", "_human_type_text", "_check_manual_stop"):
                stack.enter_context(patch.object(password_auth, name))
            result = password_auth._fill_password_page_if_present(driver, "unit@example.test", timeout=60,
                                                                 existing_password="SavedPassword123!")
        self.assertEqual(result, "SavedPassword123!")
        generate.assert_not_called()
        self.assertEqual(len(queues), 1)
        self.assertEqual([call.args[0] for call in driver.get.call_args_list], (
            ["about:blank", "https://chatgpt.com/auth/login", target] if expired_once else [target]
        ))
        self.assertEqual(driver._browser_submission_receipt.phase, "confirmed")

    def test_saved_identity_resume_uses_only_the_offered_login_password_link_once(self):
        self._resume_with_offered_password()

    def test_expired_resume_session_restarts_login_once_before_using_original_password(self):
        self._resume_with_offered_password(expired_once=True)

    def test_expired_resume_gets_bounded_budget_for_one_fresh_email_login(self):
        driver, clock = _driver("https://auth.openai.com/email-verification"), _Clock()
        driver._registration_resume_login = True
        ready_states = iter(("session_expired", "ready"))

        def wait_for_page(*_args, **_kwargs):
            state = next(ready_states)
            if state == "session_expired":
                clock.now = 50
            return state

        def restart_with_recovery_budget(_driver, _email, *, budget):
            self.assertGreaterEqual(budget.remaining(), 100)
            clock.now = 150
            return True

        with (
            patch.object(password_auth, "time", clock),
            patch.object(password_auth, "_registration_auth_mode", return_value="password"),
            patch.object(password_auth, "_is_email_verification_page", return_value=True),
            patch.object(password_auth, "_wait_email_otp_page_ready", side_effect=wait_for_page),
            patch.object(password_auth, "_restart_expired_resume_auth", side_effect=restart_with_recovery_budget),
            patch.object(password_auth, "_resume_login_password_url", return_value=None),
            patch.object(password_auth, "_offered_password_url", return_value=None),
        ):
            result = password_auth._fill_password_page_if_present(
                driver, "unit@example.test", timeout=60, existing_password="SavedPassword123!",
            )

        self.assertEqual(result, "SavedPassword123!")

    def test_saved_password_form_waits_up_to_resume_page_budget_before_failing(self):
        driver, clock = _driver("https://auth.openai.com/log-in/password"), _Clock()
        driver._registration_resume_login = True
        driver.execute_script.side_effect = lambda _script, mode, *_args: (
            {"ok": False, "reason": "missing_password_input"} if mode == "input" else {}
        )
        phases = []
        with (
            patch.object(password_auth, "time", SimpleNamespace(time=clock.time, sleep=clock.sleep)),
            patch.object(password_auth, "_registration_auth_mode", return_value="password"),
            patch.object(password_auth, "_is_email_verification_page", return_value=False),
            patch.object(password_auth, "_is_signup_password_page", return_value=False),
            patch.object(password_auth, "_is_login_password_page", return_value=True),
            patch.object(password_auth, "_has_access_token", return_value=False),
            patch.object(password_auth, "_password_page_state", return_value={
                "url": driver.current_url, "inputs": [], "buttons": [],
            }),
            patch.object(password_auth, "_check_manual_stop"),
            patch.object(password_auth, "log_submission_diagnostics"),
            patch.object(password_auth, "record_browser_submission_fact",
                         side_effect=lambda _driver, phase, **_kwargs: phases.append(phase)),
        ):
            with self.assertRaisesRegex(RuntimeError, "missing_password_input"):
                password_auth._fill_password_page_if_present(
                    driver, "unit@example.test", timeout=60, existing_password="SavedPassword123!",
                )

        self.assertGreaterEqual(clock.now, 120)
        self.assertLess(clock.now, 121)
        self.assertEqual(phases, [])

    def test_resume_uses_original_password_when_server_still_offers_creating_one(self):
        self._resume_with_offered_password(create_password=True)

    def test_offered_create_password_navigation_timeout_accepts_mounted_form(self):
        self._resume_with_offered_password(create_password=True, navigation_timeout=True)

    def test_expired_resume_can_continue_when_new_login_document_load_times_out(self):
        self._resume_with_offered_password(expired_once=True, navigation_timeout=True)

    def test_expired_session_login_is_limited_to_once_and_original_budget(self):
        driver, clock = _driver("https://auth.openai.com/email-verification"), _Clock()
        driver._registration_resume_login = True
        receipt = BrowserSubmissionReceipt(kind="resume_login", stage="email_otp", phase="unknown")
        driver._browser_submission_receipt = receipt
        before = vars(receipt).copy()
        budget = StageBudget(5, clock=clock.time)
        with (patch.object(password_auth, "time", clock),
              patch.object(password_auth, "_check_manual_stop"),
              patch.object(email_otp, "_submit_email_and_wait_next", return_value="otp") as email_submit):
            self.assertTrue(password_auth._restart_expired_resume_auth(driver, "unit@example.test", budget=budget))
            self.assertFalse(password_auth._restart_expired_resume_auth(driver, "unit@example.test", budget=budget))
        self.assertEqual([call.args[0] for call in driver.get.call_args_list],
                         ["about:blank", "https://chatgpt.com/auth/login"])
        self.assertEqual(email_submit.call_args.kwargs["total_timeout"], 5)
        self.assertEqual(vars(receipt), before)
        self.assertEqual(driver._registration_otp_after_ts, 0)
        for allowed, deadline in ((False, 5), (True, 0)):
            driver = _driver("https://auth.openai.com/email-verification")
            driver._registration_resume_login = allowed
            with self.subTest(allowed=allowed, deadline=deadline):
                self.assertFalse(password_auth._restart_expired_resume_auth(
                    driver, "unit@example.test", budget=StageBudget(deadline, clock=clock.time),
                ))
                driver.get.assert_not_called()

    def test_expired_auth_navigation_cannot_accept_the_previous_otp_document(self):
        driver, clock = _driver("https://auth.openai.com/email-verification"), _Clock()
        driver._registration_resume_login = True
        detached = [False]

        def navigate(target):
            if target == "about:blank":
                detached[0] = True
                driver.current_url = target
            elif detached[0]:
                driver.current_url = target
            # 模拟旧页仍活跃时取消新导航，WebDriver 没有抛错且仍停在旧 OTP 页。

        def submit(*_args, **_kwargs):
            self.assertEqual(driver.current_url, "https://chatgpt.com/auth/login")
            return "otp"

        driver.get.side_effect = navigate
        with (patch.object(password_auth, "time", clock), patch.object(password_auth, "_check_manual_stop"),
              patch.object(email_otp, "_submit_email_and_wait_next", side_effect=submit)):
            self.assertTrue(password_auth._restart_expired_resume_auth(
                driver, "unit@example.test", budget=StageBudget(30, clock=clock.time),
            ))

    def test_cancelled_new_login_navigation_never_submits_from_blank_document(self):
        driver, clock = _driver("https://auth.openai.com/email-verification"), _Clock()
        driver._registration_resume_login = True
        driver.get.side_effect = lambda target: setattr(driver, "current_url", "about:blank")
        with (patch.object(password_auth, "time", clock), patch.object(password_auth, "_check_manual_stop"),
              patch.object(email_otp, "_submit_email_and_wait_next") as submit):
            with self.assertRaisesRegex(RuntimeError, "新登录页面尚未确认"):
                password_auth._restart_expired_resume_auth(
                    driver, "unit@example.test", budget=StageBudget(30, clock=clock.time),
                )
        submit.assert_not_called()

    def test_expired_auth_login_navigation_retries_once_from_blank_document(self):
        driver, clock = _driver("https://auth.openai.com/email-verification"), _Clock()
        driver._registration_resume_login = True
        login_navigations = 0

        def navigate(target):
            nonlocal login_navigations
            if target == "about:blank":
                driver.current_url = target
                return
            login_navigations += 1
            driver.current_url = (
                "https://chatgpt.com/auth/login" if login_navigations == 2 else "about:blank"
            )

        driver.get.side_effect = navigate
        with (patch.object(password_auth, "time", clock), patch.object(password_auth, "_check_manual_stop"),
              patch.object(email_otp, "_submit_email_and_wait_next", return_value="otp") as submit):
            self.assertTrue(password_auth._restart_expired_resume_auth(
                driver, "unit@example.test", budget=StageBudget(30, clock=clock.time),
            ))

        self.assertEqual(login_navigations, 2)
        self.assertEqual([call.args[0] for call in driver.get.call_args_list], [
            "about:blank", "https://chatgpt.com/auth/login", "https://chatgpt.com/auth/login",
        ])
        submit.assert_called_once()

    def test_resume_navigation_timeout_continues_when_password_form_is_already_visible(self):
        self._resume_with_offered_password(navigation_timeout=True)

    def test_resume_navigation_timeout_keeps_failure_when_no_password_form_appears(self):
        with self.assertRaises(TimeoutException):
            self._resume_with_offered_password(navigation_timeout=True, visible_password=False)

    def test_login_password_target_cannot_be_guessed_or_cross_origin(self):
        for target in (None, "https://evil.test/log-in/password", "https://auth.openai.com/create-account/password",
                       "https://auth.openai.com:8443/log-in/password", "https://name:private@auth.openai.com/log-in/password"):
            driver = _driver("https://auth.openai.com/email-verification")
            driver.execute_script.return_value = target
            with self.subTest(target=target):
                self.assertIsNone(password_auth._resume_login_password_url(driver))
                driver.get.assert_not_called()
        driver.execute_script.return_value = "https://auth.openai.com/log-in/password"
        self.assertEqual(password_auth._resume_login_password_url(driver), driver.execute_script.return_value)

    def _profile_session_failure(self, error_code, *, slow_first_read=False):
        driver, clock = _driver("https://auth.openai.com/about-you"), _Clock()
        profile_url = driver.current_url
        driver.execute_script.return_value = {"valid": True, "fields": []}

        def submit(_driver):
            driver.current_url = "https://chatgpt.com/"
            return True

        def session_read(_driver, **kwargs):
            if driver.get.called:
                return {"accessToken": "test-session"}
            if slow_first_read:
                clock.sleep(kwargs["timeout"])
            raise RuntimeError(f"request_unknown: {error_code}: 测试会话未确认")

        with ExitStack() as stack:
            stack.enter_context(patch.object(password_auth, "time", clock))
            stack.enter_context(patch.object(password_auth, "_page_snapshot", side_effect=lambda _d: {
                "url": driver.current_url, "inputs": [{"name": "name"}, {"name": "age"}] if driver.current_url == profile_url else [],
            }))
            for name in ("human_delay", "_accept_profile_consents", "_check_manual_stop"):
                stack.enter_context(patch.object(password_auth, name))
            stack.enter_context(patch.object(recovery, "_check_manual_stop"))
            stack.enter_context(patch.object(password_auth, "_fill_birthday_or_age", return_value="age"))
            stack.enter_context(patch.object(password_auth, "_select_or_type", return_value=True))
            click = stack.enter_context(patch.object(password_auth, "_click_if_enabled_submit", side_effect=submit))
            stack.enter_context(patch.object(password_auth, "_read_profile_session_once", side_effect=session_read))
            if error_code == "session_identity_mismatch":
                with self.assertRaisesRegex(RuntimeError, error_code):
                    password_auth._complete_profile_page(driver, "Unit User", "2000-01-02", timeout=60,
                                                         expected_email="unit@example.test")
                driver.get.assert_not_called()
            else:
                self.assertTrue(password_auth._complete_profile_page(driver, "Unit User", "2000-01-02", timeout=60,
                                                                    expected_email="unit@example.test"))
                driver.get.assert_called_once_with("https://chatgpt.com/")
            click.assert_called_once()
            self.assertLess(clock.now, 60)

    def test_profile_read_failure_and_missing_token_trigger_get_recovery(self):
        for error_code in ("profile_session_read_failed", "profile_session_unconfirmed"):
            with self.subTest(error_code=error_code):
                self._profile_session_failure(error_code)

    def test_profile_slow_session_read_reserves_time_for_recovery(self):
        self._profile_session_failure("profile_session_read_failed", slow_first_read=True)

    def test_profile_identity_mismatch_cannot_be_recovered_as_success(self):
        self._profile_session_failure("session_identity_mismatch")

    def test_otp_stalled_submission_refreshes_after_pre_form_refresh_without_resubmit(self):
        driver, clock = _driver("https://auth.openai.com/email-verification"), _Clock()
        receipt = BrowserSubmissionReceipt(kind="otp", stage="email_otp", endpoint_kind="otp_submit", phase="ui_dispatched")
        driver._browser_submission_receipt = receipt
        driver._email_otp_page_refresh_done = True
        driver.get.side_effect = lambda _url: setattr(driver, "current_url", "https://auth.openai.com/about-you")
        with ExitStack() as stack:
            stack.enter_context(patch.object(email_otp, "time", clock))
            stack.enter_context(patch.object(email_otp, "_email_otp_page_state", side_effect=lambda _d: {
                "url": driver.current_url, "inputs": [{"type": "text", "name": "code" if "email-verification" in driver.current_url else "name"}],
                "errors": [],
            }))
            stack.enter_context(patch.object(email_otp, "_is_email_verification_page", side_effect=lambda _d: "email-verification" in driver.current_url))
            stack.enter_context(patch.object(email_otp, "_has_access_token", return_value=False))
            stack.enter_context(patch.object(email_otp, "_check_manual_stop"))
            stack.enter_context(patch.object(recovery, "_check_manual_stop"))
            retype = stack.enter_context(patch.object(email_otp, "_type_otp"))
            resend = stack.enter_context(patch.object(email_otp, "_click_resend_email_otp"))
            self.assertEqual(email_otp._wait_after_email_otp_submit(driver, timeout=60,
                                                                  budget=StageBudget(80, clock=clock.time)), "accepted")
        driver.get.assert_called_once_with("https://auth.openai.com/email-verification")
        driver.submit.assert_not_called()
        retype.assert_not_called()
        resend.assert_not_called()
        self.assertGreaterEqual(clock.now, 40)
        self.assertLessEqual(clock.now, 60)
        self.assertIs(driver._browser_submission_receipt, receipt)
        self.assertEqual(receipt.phase, "unknown")

    def test_otp_refresh_to_profile_shell_keeps_original_submission_unknown(self):
        driver, clock = _driver("https://auth.openai.com/email-verification"), _Clock()
        receipt = BrowserSubmissionReceipt(kind="otp", stage="email_otp", endpoint_kind="otp_submit", phase="unknown")
        driver._browser_submission_receipt = receipt
        driver.get.side_effect = lambda _url: setattr(driver, "current_url", "https://auth.openai.com/about-you")
        with (
            patch.object(email_otp, "time", clock),
            patch.object(email_otp, "_email_otp_page_state", side_effect=lambda _d: {
                "url": driver.current_url, "inputs": [], "text": "Loading", "errors": [],
            }),
            patch.object(email_otp, "_is_email_verification_page", side_effect=lambda _d: "email-verification" in driver.current_url),
            patch.object(email_otp, "_has_access_token", return_value=False),
            patch.object(email_otp, "_check_manual_stop"),
            patch.object(recovery, "_check_manual_stop"),
        ):
            self.assertEqual(email_otp._wait_after_email_otp_submit(driver, timeout=60,
                                                                  budget=StageBudget(70, clock=clock.time)), "stuck")
        driver.get.assert_called_once()
        self.assertEqual(receipt.phase, "unknown")
        self.assertLessEqual(clock.now, 60)

    def test_otp_same_submission_reentry_does_not_refresh_twice(self):
        driver, clock = _driver("https://auth.openai.com/email-verification"), _Clock()
        receipt = BrowserSubmissionReceipt(kind="otp", stage="email_otp", endpoint_kind="otp_submit", phase="unknown")
        driver._browser_submission_receipt = receipt
        driver._email_otp_submission_recovery_id = receipt.submission_id
        with (
            patch.object(email_otp, "time", clock),
            patch.object(email_otp, "_email_otp_page_state", return_value={
                "url": driver.current_url, "inputs": [{"name": "code", "type": "text"}], "errors": [],
            }),
            patch.object(email_otp, "_is_email_verification_page", return_value=True),
            patch.object(email_otp, "_has_access_token", return_value=False),
            patch.object(email_otp, "_check_manual_stop"),
        ):
            self.assertEqual(email_otp._wait_after_email_otp_submit(driver, timeout=10,
                                                                  budget=StageBudget(60, clock=clock.time)), "stuck")
        driver.get.assert_not_called()
        self.assertEqual(receipt.phase, "unknown")
        self.assertLessEqual(clock.now, 10)

    def test_password_pending_refresh_reaches_otp_with_one_password_submission(self):
        driver, clock = _driver(), _Clock()
        queues = []

        def execute(_script, *args):
            if args and args[0] == "queue":
                queues.append(args[3])
                return {"ok": True, "reason": "password_submit_queued"}
            if args and args[0] == "input":
                return {"ok": True, "input": object()}
            return {"phase": "dispatched", "click_called": True, "submit_event_observed": True,
                    "submit_default_prevented": True, "submitter_matches": True}

        driver.execute_script.side_effect = execute
        driver.get.side_effect = lambda _target: setattr(driver, "current_url", "https://auth.openai.com/email-verification")
        with ExitStack() as stack:
            stack.enter_context(patch.object(password_auth, "time", SimpleNamespace(time=clock.time, sleep=clock.sleep)))
            stack.enter_context(patch.object(password_auth, "_registration_auth_mode", return_value="password"))
            stack.enter_context(patch.object(password_auth, "_registration_password", return_value="UnitPassword123!"))
            stack.enter_context(patch.object(password_auth, "_password_transition_timeout_seconds", return_value=30))
            stack.enter_context(patch.object(password_auth, "_password_page_state", side_effect=lambda _d: {
                "url": driver.current_url,
                "inputs": [{"type": "text", "name": "code", "visible": True}] if "email-verification" in driver.current_url else [],
            }))
            stack.enter_context(patch.object(password_auth, "_is_signup_password_page", return_value=True))
            stack.enter_context(patch.object(password_auth, "_is_login_password_page", return_value=False))
            stack.enter_context(patch.object(password_auth, "_is_email_verification_page", side_effect=lambda _d: "email-verification" in driver.current_url))
            stack.enter_context(patch.object(password_auth, "_has_access_token", return_value=False))
            for name in ("human_delay", "_human_type_text", "_check_manual_stop"):
                stack.enter_context(patch.object(password_auth, name))
            stack.enter_context(patch.object(recovery, "_check_manual_stop"))
            result = password_auth._fill_password_page_if_present(driver, "unit@example.test", timeout=5)
        self.assertEqual(result, "UnitPassword123!")
        self.assertEqual(len(queues), 1)
        driver.get.assert_called_once()
        self.assertEqual(driver._browser_submission_receipt.phase, "confirmed")
        self.assertLess(clock.now, 30)

    def test_email_pending_refresh_reaches_next_page_with_original_receipt(self):
        driver, clock = _driver("https://chatgpt.com/auth/login"), _Clock()
        driver.execute_script.side_effect = lambda *_args: {
            "url": driver.current_url, "inputs": [{"type": "text", "name": "code", "visible": True}]
            if "email-verification" in driver.current_url else [],
        }
        driver._email_submission_receipt = {"id": "original"}
        receipt = BrowserSubmissionReceipt(kind="email", stage="submit_email", phase="ui_dispatched")
        driver._browser_submission_receipt = receipt
        driver.get.side_effect = lambda _url: setattr(driver, "current_url", "https://auth.openai.com/email-verification")

        def advanced(_driver, **_kwargs):
            if "email-verification" in driver.current_url:
                email_otp._confirm_email_submission_fact(driver)
                email_otp._clear_confirmed_email_submission(driver)
                return "otp"
            return None

        with (
            patch.object(email_otp, "time", clock),
            patch.object(email_otp, "_email_submit_advanced_state", side_effect=advanced),
            patch.object(email_otp, "_email_ui_submission_state", return_value="dispatched"),
            patch.object(email_otp, "_check_manual_stop"),
            patch.object(recovery, "_check_manual_stop"),
        ):
            result = email_otp._wait_email_submit_next_state(driver, "unit@example.test", timeout=20,
                                                           budget=StageBudget(60, clock=clock.time))
        self.assertEqual(result, "otp")
        driver.get.assert_called_once_with("https://chatgpt.com/auth/login")
        driver.submit.assert_not_called()
        self.assertEqual(receipt.phase, "confirmed")
        self.assertLess(clock.now, 60)

    def test_empty_next_route_and_hidden_inputs_do_not_confirm_recovery(self):
        for snapshot in ({"url": "https://auth.openai.com/email-verification", "inputs": []},
                         {"inputs": [{"type": "hidden", "visible": True}]},
                         {"inputs": [{"type": "text", "visible": False}]},
                         {"inputs": [{"type": "password", "visible": True}]}):
            with self.subTest(snapshot=snapshot):
                self.assertFalse(recovery.has_visible_auth_inputs(snapshot, allow_password=False))

    def _wait_nextauth_blank_verification(self, *, deadline=20, mounted_after_refresh=True, ui_state=None):
        driver, clock = _driver("https://auth.openai.com/email-verification"), _Clock()
        receipt = BrowserSubmissionReceipt(kind="email", stage="submit_email", phase="unknown")
        driver._browser_submission_receipt = receipt
        if ui_state:
            driver._email_submission_receipt = {"id": "original"}

        def snapshot(_driver):
            mounted = mounted_after_refresh and driver.get.called
            return {"url": driver.current_url, "text": "Verification code" if mounted else "",
                    "inputs": [{"type": "text", "name": "code", "visible": True}] if mounted else [],
                    "buttons": [], "errors": []}

        with ExitStack() as stack:
            stack.enter_context(patch.object(email_otp, "time", clock))
            stack.enter_context(patch.object(email_otp, "_check_manual_stop"))
            stack.enter_context(patch.object(recovery, "_check_manual_stop"))
            stack.enter_context(patch.object(email_otp, "_is_login_password_page", return_value=False))
            stack.enter_context(patch.object(email_otp, "_is_signup_password_page", return_value=False))
            stack.enter_context(patch.object(email_otp, "_has_access_token", return_value=False))
            stack.enter_context(patch.object(email_otp, "_email_ui_submission_state", return_value=ui_state))
            stack.enter_context(patch.object(email_otp, "_email_otp_page_state", side_effect=snapshot))
            stack.enter_context(patch.object(email_otp, "_email_input_value_state", side_effect=snapshot))
            stack.enter_context(patch.object(email_otp, "_is_blank_chatgpt_auth_shell", return_value=False))
            stack.enter_context(patch.object(email_otp, "_is_email_login_page_still_present", return_value=False))
            stack.enter_context(patch.object(email_otp, "log_submission_diagnostics"))
            try:
                result = email_otp._wait_email_submit_next_state(
                    driver, "unit@example.test", timeout=deadline, wait_through_transient=True,
                    budget=StageBudget(deadline, clock=clock.time),
                )
            except email_otp._EmailSubmissionUnknown:
                result = "request_unknown"
        self.assertIs(driver._browser_submission_receipt, receipt)
        driver.submit.assert_not_called()
        return result, driver, clock

    def test_nextauth_landing_blank_verification_refreshes_before_waiting_for_otp(self):
        result, driver, clock = self._wait_nextauth_blank_verification()
        self.assertEqual(result, "otp")
        driver.get.assert_called_once_with("https://auth.openai.com/email-verification")
        self.assertEqual(driver._browser_submission_receipt.phase, "confirmed")
        self.assertGreaterEqual(clock.now, 3)
        self.assertLess(clock.now, 20)

    def test_nextauth_blank_verification_never_extends_short_submission_budget(self):
        result, driver, clock = self._wait_nextauth_blank_verification(deadline=2)
        self.assertEqual(result, "unknown")
        driver.get.assert_not_called()
        self.assertEqual(clock.now, 2)
        self.assertEqual(driver._browser_submission_receipt.phase, "unknown")

    def test_pending_email_blank_verification_uses_only_one_refresh(self):
        result, driver, clock = self._wait_nextauth_blank_verification(
            mounted_after_refresh=False, ui_state="dispatched",
        )
        self.assertEqual(result, "request_unknown")
        driver.get.assert_called_once_with("https://auth.openai.com/email-verification")
        self.assertEqual(clock.now, 20)
        self.assertEqual(driver._browser_submission_receipt.phase, "unknown")

    def test_email_refresh_to_blank_otp_route_keeps_unknown_result(self):
        driver, clock = _driver("https://chatgpt.com/auth/login"), _Clock()
        driver._email_submission_receipt = {"id": "original"}
        driver._browser_submission_receipt = BrowserSubmissionReceipt(kind="email", stage="submit_email", phase="ui_dispatched")
        driver.get.side_effect = lambda _url: setattr(driver, "current_url", "https://auth.openai.com/email-verification")
        driver.execute_script.side_effect = lambda *_args: {"url": driver.current_url, "inputs": []}
        with (
            patch.object(email_otp, "time", clock),
            patch.object(email_otp, "_email_submit_advanced_state", side_effect=lambda _d, **_kw: "otp" if driver.get.called else None),
            patch.object(email_otp, "_email_ui_submission_state", return_value="dispatched"),
            patch.object(email_otp, "_check_manual_stop"),
            patch.object(recovery, "_check_manual_stop"),
        ):
            with self.assertRaises(email_otp._EmailSubmissionUnknown):
                email_otp._wait_email_submit_next_state(driver, "unit@example.test", timeout=20,
                                                       budget=StageBudget(60, clock=clock.time))
        self.assertEqual(driver._browser_submission_receipt.phase, "unknown")
        driver.get.assert_called_once()

    def test_profile_auth_error_refresh_and_back_recover_verified_session(self):
        driver, clock = _driver("https://auth.openai.com/about-you"), _Clock()
        error_url = "https://chatgpt.com/auth/error"
        profile_url = driver.current_url
        driver.execute_cdp_cmd.return_value = {
            "currentIndex": 1, "entries": [{"url": profile_url}, {"url": error_url}],
        }
        driver.execute_script.return_value = {"valid": True, "fields": []}
        driver.get.side_effect = lambda url: setattr(driver, "current_url", "https://chatgpt.com/" if url == profile_url else url)

        def submit(_driver):
            driver.current_url = error_url
            return True

        with ExitStack() as stack:
            stack.enter_context(patch.object(password_auth, "time", SimpleNamespace(time=clock.time, sleep=clock.sleep)))
            stack.enter_context(patch.object(password_auth, "_page_snapshot", side_effect=lambda _d: {
                "url": driver.current_url, "inputs": [{"name": "name"}, {"name": "age"}] if driver.current_url == profile_url else [],
            }))
            for name in ("human_delay", "_accept_profile_consents", "_check_manual_stop"):
                stack.enter_context(patch.object(password_auth, name))
            stack.enter_context(patch.object(recovery, "_check_manual_stop"))
            stack.enter_context(patch.object(password_auth, "_fill_birthday_or_age", return_value="age"))
            stack.enter_context(patch.object(password_auth, "_select_or_type", return_value=True))
            click = stack.enter_context(patch.object(password_auth, "_click_if_enabled_submit", side_effect=submit))
            session = stack.enter_context(patch.object(password_auth, "_read_profile_session_once", return_value={"accessToken": "test-session"}))
            result = password_auth._complete_profile_page(driver, "Unit User", "2000-01-02", timeout=60,
                                                          expected_email="unit@example.test")
        self.assertTrue(result)
        self.assertEqual([call.args[0] for call in driver.get.call_args_list], [error_url, profile_url])
        click.assert_called_once()
        session.assert_called_once()
        self.assertEqual(session.call_args.kwargs["expected_email"], "unit@example.test")
        self.assertLess(clock.now, 60)
