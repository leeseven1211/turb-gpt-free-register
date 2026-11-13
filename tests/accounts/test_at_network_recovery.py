"""AT 网络恢复保持同一逻辑回执，换线与原线恢复均有界。"""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

import requests

from core.accounts.liveness import service
from core.network.at_transport_recovery import AtRecoveryTimeout, current_scope
from core.operations.runtime import OperationCancelled


EMAIL = "at-network@example.test"


class _Context:
    run_id = 27

    def __init__(self):
        self.started = []
        self.receipts = []
        self.state = ""

    def remote_request_started(self, action, **kwargs):
        self.started.append((action, kwargs))
        self.state = "started"

    def remote_request_receipt(self, **kwargs):
        if kwargs["outcome"] == "not_submitted" and self.state not in {"started", "not_submitted"}:
            raise AssertionError("不能把前次未知请求改成未提交")
        self.receipts.append(kwargs)
        self.state = kwargs["outcome"]


class AtNetworkRecoveryTests(unittest.TestCase):
    def network_result(self, operation="email_otp_send"):
        return {"ok": False, "status": "failed", "error": "email_otp_failed",
                "auth_diagnostics": {"operation": operation, "failure_kind": "transport_error",
                                     "exception_type": "SSLError", "curl_error_code": 35}}

    def success(self):
        return {"ok": True, "status": "live", "access_token": "fixture-fresh", "session": {}}

    def no_mail_result(self):
        return {"ok": False, "status": "failed", "error": "email_otp_failed",
                "roxy_fallback_allowed": False, "remote_request_started": True,
                "auth_diagnostics": {"operation": "email_otp", "failure_kind": "no_mail",
                                     "mailbox_error_code": "inbound_code_timeout"}}

    def run_worker(self, outcomes, *, proxy=None, retries=2, context=None, driver="v2", completion_auth=False,
                   acquisition_error=None, writeback=True, on_authenticated=None, roxy_fallback=False,
                   roxy_available=True):
        routes, acquisitions = [], []
        reporter = MagicMock()
        account = {"id": 7, "email": EMAIL, "access_token": "fixture-old"}
        iterator = iter(outcomes)
        calls = []

        def acquire(**kwargs):
            acquisitions.append(kwargs)
            if acquisition_error is not None and len(acquisitions) > 1:
                raise acquisition_error
            route = SimpleNamespace(proxy_url=kwargs.get("explicit_proxy") or f"fixture-route-{len(routes)}", release=Mock())
            route.public_dict = lambda: {"network_route": "proxy", "proxy_region": kwargs.get("region")}
            routes.append(route)
            return route

        def refresh(_email, **kwargs):
            calls.append(kwargs)
            if kwargs.get("proxy_supplier"):
                kwargs["proxy_supplier"](1)
            if kwargs.get("on_remote_request_started"):
                kwargs["on_remote_request_started"]()
            outcome = next(iterator)
            if callable(outcome):
                return outcome(kwargs)
            if isinstance(outcome, BaseException):
                raise outcome
            return dict(outcome)

        def write(_account_id, result):
            if writeback:
                account.update(access_token=result.get("access_token"), live_check_ok=result.get("ok"),
                               live_check_status=result.get("status"))
            return writeback

        snapshot = {"refresh_at_country": "JP", "network_retry_limit": retries, "network_timeout_seconds": 900,
                    "auth_raw_context_enabled": False, "roxy_fallback_enabled": roxy_fallback,
                    "proxy_retry_limit": 0, "proxy_retry_delay": 0}
        with ExitStack() as stack:
            for item in (
                patch.object(service.db, "mark_account_live_check_running", return_value=True),
                patch.object(service.db, "get_account", side_effect=lambda _id: dict(account)),
                patch.object(service.db, "update_account_liveness", side_effect=write),
                patch.object(service, "_reporter", return_value=reporter),
                patch.object(service, "_append_log"), patch.object(service, "_checkpoint"),
                patch.object(service, "token_claims", return_value={}),
                patch.object(service, "_resolve_protocol_identity", return_value=None),
                patch("core.proxy.account_routes.acquire_account_proxy", side_effect=acquire),
                patch("core.accounts.liveness.protocol.v2.refresh_access_token", side_effect=refresh),
                patch("core.accounts.liveness.protocol.v3.refresh_access_token", side_effect=refresh),
                patch("core.accounts.liveness.roxy.flow.refresh_access_token", side_effect=refresh),
                patch("core.accounts.liveness.roxy.flow.available", return_value=roxy_available),
            ):
                stack.enter_context(item)
            result = service._run_live_check(account_id=7, email=EMAIL, proxy=proxy, trigger="fixture",
                force_refresh=True, refresh_driver=driver, operation_context=context, config_snapshot=snapshot,
                completion_auth=completion_auth, on_authenticated=on_authenticated)
        return result, calls, routes, acquisitions, reporter

    def test_network_failure_isolated_then_new_route_succeeds_for_all_drivers(self):
        for driver in ("v2", "v3", "browser_roxy"):
            with self.subTest(driver=driver):
                result, calls, routes, acquisitions, reporter = self.run_worker([self.network_result(), self.success()], driver=driver)
                self.assertTrue(result["ok"])
                self.assertEqual(2, len(calls))
                self.assertEqual(["JP", "JP"], [item["region"] for item in acquisitions])
                self.assertTrue(routes[0].release.call_args.kwargs["fault"])
                self.assertEqual(1, routes[0].release.call_count)
                self.assertEqual(1, result["network_recovery"]["route_retries"])
                self.assertEqual(2, result["network_recovery"]["attempts"])
                self.assertFalse(result["network_recovery"]["exhausted"])
                self.assertEqual(result["network_recovery"], reporter.finish.call_args.kwargs["result_summary"]["network_recovery"])
                self.assertTrue(all(0 < item["timeout"] <= 900 for item in acquisitions))

    def test_same_route_scope_recovers_without_rotating(self):
        def recovered(_kwargs):
            scope = current_scope()
            self.assertIsNotNone(scope)
            scope.same_route_retries += 1
            scope.emit({"event": "same_route_retry", "operation": "email_otp_send",
                        "failure_kind": "transport_error", "curl_error_code": 35})
            return self.success()

        result, _, routes, _, reporter = self.run_worker([recovered])
        self.assertTrue(result["ok"])
        self.assertEqual(1, len(routes))
        self.assertEqual(1, result["network_recovery"]["same_route_retries"])
        self.assertEqual(0, result["network_recovery"]["route_retries"])
        self.assertTrue(any(call.kwargs.get("detail", {}).get("same_route_retry") for call in reporter.note.call_args_list))

    def partial_response_preflight_failure(self, *, cause_wrapper=False):
        from curl_cffi.requests.exceptions import Timeout
        from core.auth.protocol.session import BrowserSession

        partial = SimpleNamespace(status_code=200, headers={}, text="")
        session = SimpleNamespace(blocked_until=0, reset_transport=Mock(), _get_once=Mock(side_effect=[
            Timeout("fixture-partial-body-timeout", code=28, response=partial),
            Timeout("fixture-partial-body-timeout", code=28, response=partial),
        ]))

        def preflight(_kwargs):
            try:
                BrowserSession.get(session, "https://auth.openai.com/authorize?fixture-private-query=secret")
            except Timeout:
                diagnostics = {"operation": "network_preflight", "failure_kind": "runtime_exception",
                               "exception_type": "Timeout", "http_status": 200, "source": "fixture-driver"}
                if cause_wrapper:
                    diagnostics.update(operation="protocol_v2_auth", cause_operation="network_preflight",
                                       cause_failure_kind="runtime_exception")
                return {"ok": False, "status": "failed", "error": "network_preflight_failed",
                        "mutation_submitted": False, "action_dispatched": False,
                        "auth_diagnostics": diagnostics}
            self.fail("离线 transport 应连续两次超时")

        return preflight, session

    def test_partial_response_timeout_retries_current_request_then_new_route(self):
        preflight, session = self.partial_response_preflight_failure()
        result, calls, routes, _, _ = self.run_worker([preflight, self.success()])
        self.assertTrue(result["ok"])
        self.assertEqual(2, session._get_once.call_count)
        session.reset_transport.assert_called_once()
        self.assertEqual(2, len(calls))
        self.assertEqual(2, len(routes))
        self.assertTrue(routes[0].release.call_args.kwargs["fault"])
        recovery = result["network_recovery"]
        self.assertEqual(1, recovery["same_route_retries"])
        self.assertEqual(1, recovery["route_retries"])
        self.assertFalse(recovery["exhausted"])
        failure = next(item for item in recovery["history"] if item["event"] == "route_failure")
        self.assertEqual("Timeout", failure["exception_type"])
        self.assertEqual(28, failure["curl_error_code"])
        self.assertEqual(200, failure["http_status"])
        self.assertTrue(failure["response_observed"])
        self.assertNotIn("auth_diagnostics", result)
        self.assertNotIn("fixture-private-query", str(recovery))

    def test_exhausted_generic_wrapper_keeps_confirmed_transport_diagnostics(self):
        for cause_wrapper in (False, True):
            with self.subTest(cause_wrapper=cause_wrapper):
                preflight, session = self.partial_response_preflight_failure(cause_wrapper=cause_wrapper)
                result, calls, routes, _, reporter = self.run_worker([preflight], retries=0)
                self.assertFalse(result["ok"])
                self.assertEqual("network_preflight_failed", result["error"])
                self.assertEqual(2, session._get_once.call_count)
                self.assertEqual(1, len(calls))
                self.assertTrue(routes[0].release.call_args.kwargs["fault"])
                self.assertTrue(result["network_recovery"]["exhausted"])
                diagnostic = result["auth_diagnostics"]
                self.assertEqual("protocol_v2_auth" if cause_wrapper else "network_preflight", diagnostic["operation"])
                self.assertEqual("fixture-driver", diagnostic["source"])
                if cause_wrapper:
                    self.assertEqual("network_preflight", diagnostic["cause_operation"])
                    self.assertEqual("transport_error", diagnostic["cause_failure_kind"])
                self.assertEqual("transport_error", diagnostic["failure_kind"])
                self.assertEqual("Timeout", diagnostic["exception_type"])
                self.assertEqual(28, diagnostic["curl_error_code"])
                self.assertEqual(200, diagnostic["http_status"])
                self.assertTrue(diagnostic["response_observed"])
                self.assertNotIn("fixture-private-query", str(diagnostic))
                summary = reporter.finish.call_args.kwargs["result_summary"]["auth_diagnostics"]
                self.assertEqual("transport_error", summary["failure_kind"])
                self.assertEqual(28, summary["curl_error_code"])

    def test_explicit_route_never_silently_switches_proxy(self):
        result, calls, routes, _, _ = self.run_worker([self.network_result()], proxy="fixture-explicit")
        self.assertFalse(result["ok"])
        self.assertEqual(1, len(calls))
        self.assertEqual("fixture-explicit", calls[0]["proxy"])
        self.assertEqual(0, result["network_recovery"]["route_retries"])
        self.assertTrue(result["network_recovery"]["exhausted"])
        self.assertTrue(routes[0].release.call_args.kwargs["fault"])

    def test_zero_retries_allows_original_scope_but_no_route_rotation(self):
        result, calls, routes, _, _ = self.run_worker([self.network_result()], retries=0)
        self.assertEqual(1, len(calls))
        self.assertEqual(0, result["network_recovery"]["route_retries"])
        self.assertTrue(result["network_recovery"]["exhausted"])
        self.assertEqual("email_otp_failed", result["error"])
        self.assertTrue(routes[0].release.call_args.kwargs["fault"])

    def test_two_route_retries_stop_after_three_failed_attempts(self):
        result, calls, routes, _, _ = self.run_worker([self.network_result() for _ in range(3)], retries=2)
        self.assertFalse(result["ok"])
        self.assertEqual(3, len(calls))
        self.assertEqual(3, len(routes))
        self.assertEqual(2, result["network_recovery"]["route_retries"])
        self.assertEqual(3, result["network_recovery"]["attempts"])
        self.assertTrue(result["network_recovery"]["exhausted"])
        self.assertTrue(all(route.release.call_count == 1 and route.release.call_args.kwargs["fault"] for route in routes))
        self.assertIsNone(current_scope())

    def test_mailbox_and_business_failures_do_not_rotate(self):
        for result in (
            {"ok": False, "status": "failed", "error": "email_otp_failed",
             "auth_diagnostics": {"operation": "email_otp", "failure_kind": "no_mail", "mailbox_error_code": "inbound_code_timeout"}},
            {"ok": False, "status": "failed", "error": "password_rejected"},
        ):
            with self.subTest(error=result["error"]):
                actual, calls, routes, _, _ = self.run_worker([result])
                self.assertFalse(actual["ok"])
                self.assertEqual(1, len(calls))
                self.assertNotEqual(True, routes[0].release.call_args.kwargs.get("fault"))
                self.assertFalse(actual["network_recovery"]["exhausted"])

    def test_confirmed_no_mail_enters_roxy_once_and_confirms_the_same_intent(self):
        for driver, proxy in (("v2", None), ("v3", None), ("v2", "fixture-explicit")):
            with self.subTest(driver=driver, explicit_proxy=bool(proxy)):
                deadlines = []

                def no_mail(_kwargs):
                    deadlines.append(current_scope().deadline)
                    return self.no_mail_result()

                def roxy(_kwargs):
                    deadlines.append(current_scope().deadline)
                    return self.success()

                context = _Context()
                result, calls, routes, acquisitions, reporter = self.run_worker(
                    [no_mail, roxy], driver=driver, proxy=proxy, context=context, roxy_fallback=True)
                self.assertTrue(result["ok"])
                self.assertTrue(result["fallback_used"])
                self.assertEqual("browser_roxy", result["live_check_driver"])
                self.assertEqual(2, len(calls))
                self.assertEqual(1, len(context.started))
                self.assertEqual(["unknown", "response_received", "confirmed"],
                                 [item["outcome"] for item in context.receipts])
                self.assertEqual(1, len({item["request_id"] for item in context.receipts}))
                self.assertEqual(deadlines[0], deadlines[1])
                self.assertEqual(0, result["network_recovery"]["route_retries"])
                self.assertEqual(1, sum(call.kwargs.get("detail", {}).get("no_mail_fallback", False)
                                        for call in reporter.note.call_args_list))
                if proxy:
                    self.assertEqual(1, len(routes))
                    self.assertEqual(proxy, calls[0]["proxy"])
                    self.assertEqual(proxy, calls[1]["proxy"])
                else:
                    self.assertEqual(["JP", "JP"], [item["region"] for item in acquisitions])
                    self.assertTrue(0 < acquisitions[1]["timeout"] <= acquisitions[0]["timeout"] <= 900)
                    self.assertNotEqual(True, routes[0].release.call_args.kwargs.get("fault"))
                    self.assertEqual(routes[1].proxy_url, calls[1]["proxy"])

    def test_failed_no_mail_roxy_fallback_keeps_previous_unknown(self):
        for later in (self.no_mail_result(), {"ok": False, "status": "failed", "error": "password_rejected"},
                      {"ok": False, "status": "failed", "error": "password_missing",
                       "mutation_submitted": False, "action_dispatched": False}):
            with self.subTest(later=later["error"]):
                context = _Context()
                result, calls, _, _, _ = self.run_worker(
                    [self.no_mail_result(), later], context=context, roxy_fallback=True)
                self.assertFalse(result["ok"])
                self.assertEqual(2, len(calls))
                self.assertTrue(result["fallback_used"])
                self.assertTrue(result["reconcile_required"])
                self.assertEqual(1, len(context.started))
                self.assertEqual("unknown", context.state)
                self.assertFalse(any(item["outcome"] in {"not_submitted", "rejected", "confirmed"}
                                     for item in context.receipts))

    def test_mailbox_transport_failure_uses_roxy_once_without_openai_network_retries(self):
        from core.accounts.liveness.protocol.otp_diagnostics import otp_failure_diagnostics
        from core.email.email_butler.client import EmailButlerClientError

        for driver in ("v2", "v3"):
            for code in ("butler_transport_timeout", "butler_transport_connection", "butler_transport_failed"):
                with self.subTest(driver=driver, code=code):
                    candidate = self.no_mail_result()
                    candidate["auth_diagnostics"] = otp_failure_diagnostics(
                        EmailButlerClientError("测试收件请求故障", error_code=code))
                    context = _Context()
                    result, calls, routes, _, reporter = self.run_worker(
                        [candidate, self.success()], driver=driver, context=context, roxy_fallback=True)
                    self.assertTrue(result["ok"])
                    self.assertTrue(result["fallback_used"])
                    self.assertEqual("browser_roxy", result["live_check_driver"])
                    self.assertEqual(2, len(calls))
                    self.assertEqual(0, result["network_recovery"]["route_retries"])
                    self.assertEqual(1, len(context.started))
                    self.assertEqual("confirmed", context.state)
                    self.assertNotEqual(True, routes[0].release.call_args.kwargs.get("fault"))
                    self.assertEqual(1, sum(call.kwargs.get("detail", {}).get("mailbox_failure_fallback", False)
                                            for call in reporter.note.call_args_list))

    def test_mailbox_transport_fallback_respects_switch_and_preserves_unknown_when_roxy_fails(self):
        candidate = self.no_mail_result()
        candidate["auth_diagnostics"] = {"operation": "email_otp", "failure_kind": "transport_error",
                                         "mailbox_error_code": "butler_transport_timeout"}
        for enabled, available in ((False, True), (True, False)):
            with self.subTest(enabled=enabled, available=available):
                result, calls, _, _, _ = self.run_worker([candidate], context=_Context(),
                    roxy_fallback=enabled, roxy_available=available)
                self.assertFalse(result["ok"])
                self.assertEqual(1, len(calls))
                self.assertNotIn("fallback_used", result)
        context = _Context()
        result, calls, _, _, _ = self.run_worker(
            [candidate, candidate], context=context, roxy_fallback=True)
        self.assertEqual(2, len(calls))
        self.assertFalse(result["ok"])
        self.assertTrue(result["fallback_used"])
        self.assertEqual("unknown", context.state)

    def test_no_mail_fallback_still_requires_enabled_and_available_roxy(self):
        for enabled, available in ((False, True), (True, False)):
            with self.subTest(enabled=enabled, available=available):
                result, calls, _, _, _ = self.run_worker([self.no_mail_result()], context=_Context(),
                    roxy_fallback=enabled, roxy_available=available)
                self.assertFalse(result["ok"])
                self.assertEqual(1, len(calls))
                self.assertNotIn("fallback_used", result)

    def test_no_mail_exception_does_not_allow_other_mailbox_or_business_failures(self):
        for changes in (
            {"failure_kind": "mailbox_error", "mailbox_error_code": "source_authentication_failed"},
            {"failure_kind": "imap_error"}, {"failure_kind": "manual_timeout"},
            {"operation": "email_otp_send"}, {"mailbox_error_code": "recipient_mismatch"},
        ):
            with self.subTest(changes=changes):
                candidate = self.no_mail_result()
                candidate["auth_diagnostics"].update(changes)
                result, calls, _, _, _ = self.run_worker([candidate], context=_Context(), roxy_fallback=True)
                self.assertFalse(result["ok"])
                self.assertEqual(1, len(calls))
        for code in ("password_rejected", "password_rejected_email_fallback_failed", "mfa_rejected"):
            with self.subTest(code=code):
                candidate = {**self.no_mail_result(), "error": code, "password_auth_status": "rejected"}
                result, calls, _, _, _ = self.run_worker([candidate], context=_Context(), roxy_fallback=True)
                self.assertFalse(result["ok"])
                self.assertEqual(1, len(calls))

    def test_unknown_then_success_uses_one_intent_and_confirms_only_after_writeback(self):
        context = _Context()
        result, _, _, _, _ = self.run_worker([self.network_result(), self.success()], context=context)
        self.assertTrue(result["ok"])
        self.assertEqual(1, len(context.started))
        self.assertEqual(["unknown", "response_received", "confirmed"], [item["outcome"] for item in context.receipts])
        self.assertEqual(1, len({item["request_id"] for item in context.receipts}))
        self.assertNotIn("manual_reconcile", result)
        self.assertNotIn("reconcile_required", result)

    def test_raw_transport_exception_with_native_context_rotates_and_confirms(self):
        context = _Context()
        result, calls, routes, _, _ = self.run_worker([requests.ConnectionError("fixture-connection"), self.success()], context=context)
        self.assertTrue(result["ok"])
        self.assertEqual(2, len(calls))
        self.assertEqual("confirmed", context.state)
        self.assertTrue(routes[0].release.call_args.kwargs["fault"])
        self.assertEqual("ConnectionError", result["network_recovery"]["history"][0]["exception_type"])

    def test_unknown_is_preserved_when_the_next_attempt_is_not_submitted_or_rejected(self):
        for later in (
            {"ok": False, "status": "failed", "error": "network_preflight_failed", "mutation_submitted": False,
             "action_dispatched": False},
            {"ok": False, "status": "failed", "error": "password_rejected"},
        ):
            with self.subTest(error=later["error"]):
                context = _Context()
                result, calls, _, _, _ = self.run_worker([self.network_result(), later], context=context)
                self.assertFalse(result["ok"])
                self.assertTrue(result["reconcile_required"])
                self.assertEqual(2, len(calls))
                self.assertEqual(1, len(context.started))
                self.assertEqual("unknown", context.state)
                self.assertFalse(any(item["outcome"] in {"not_submitted", "rejected"} for item in context.receipts))

    def test_new_token_is_not_confirmed_when_local_writeback_failed(self):
        context = _Context()
        result, _, _, _, _ = self.run_worker([self.network_result(), self.success()], context=context, writeback=False)
        self.assertFalse(result["ok"])
        self.assertEqual("local_commit_required", context.state)
        self.assertEqual("refresh_local_commit_failed", result["error_code"])

    def test_completed_token_is_not_overwritten_by_deadline_crossed_in_postprocess(self):
        def completed_after_deadline(_kwargs):
            current_scope().deadline = 0
            return self.success()

        context = _Context()
        result, calls, _, _, _ = self.run_worker([completed_after_deadline], context=context)
        self.assertTrue(result["ok"])
        self.assertEqual(1, len(calls))
        self.assertEqual("confirmed", context.state)
        self.assertFalse(result["network_recovery"]["timeout"])

    def test_authenticated_postprocess_is_outside_network_recovery_scope(self):
        original_scope = []

        def postprocess(result, _session):
            self.assertIsNone(current_scope())
            original_scope[0].deadline = 0
            return result

        def authenticate(kwargs):
            original_scope.append(current_scope())
            self.assertIsNotNone(original_scope[0])
            return kwargs["on_authenticated"](self.success(), object())

        result, calls, _, _, _ = self.run_worker([authenticate], on_authenticated=postprocess)
        self.assertTrue(result["ok"])
        self.assertEqual(1, len(calls))
        self.assertFalse(result["network_recovery"]["timeout"])
        self.assertIsNone(current_scope())

    def test_authenticated_callback_keeps_at_when_deadline_expired_before_callback(self):
        def authenticate(kwargs):
            current_scope().deadline = 0
            return kwargs["on_authenticated"](self.success(), object())

        postprocess = Mock(side_effect=lambda result, _session: result)
        context = _Context()
        result, calls, _, _, _ = self.run_worker([authenticate], context=context, on_authenticated=postprocess)
        self.assertTrue(result["ok"])
        self.assertEqual("fixture-fresh", result["access_token"])
        self.assertEqual(1, len(calls))
        self.assertEqual("confirmed", context.state)
        self.assertFalse(result["network_recovery"]["timeout"])
        postprocess.assert_called_once()

    def test_unconfirmed_callback_still_checks_expired_authentication_budget(self):
        for candidate in ({"ok": True}, {"ok": False, "access_token": "fixture-fresh"},
                          {"ok": True, "access_token": " "}):
            with self.subTest(candidate=candidate):
                def authenticate(kwargs):
                    current_scope().deadline = 0
                    return kwargs["on_authenticated"](candidate, object())

                postprocess = Mock(side_effect=lambda result, _session: result)
                result, calls, _, _, _ = self.run_worker([authenticate], on_authenticated=postprocess)
                self.assertFalse(result["ok"])
                self.assertTrue(result["network_recovery"]["timeout"])
                self.assertEqual(1, len(calls))
                postprocess.assert_not_called()

    def test_v3_session_cache_write_crossing_deadline_keeps_the_acquired_at(self):
        from core.accounts.liveness.protocol import v3

        session = SimpleNamespace(proxy=None, device_id="fixture-device", browser_profile={},
                                  session=SimpleNamespace(cookies=[]))
        info = {"accessToken": "fixture-fresh", "user": {"email": EMAIL}, "account": {}}

        def cache_session(*_args):
            current_scope().deadline = 0
            return True

        def authenticate(kwargs):
            return v3._success(session, info, email=EMAIL, target={"id": 7, "email": EMAIL},
                               account_id=7, checked_at="fixture", methods=["session_cookie"],
                               on_authenticated=kwargs["on_authenticated"])

        postprocess = Mock(side_effect=lambda result, _session: result)
        context = _Context()
        with patch.object(v3.protocol_sessions, "save_session", side_effect=cache_session) as saved:
            result, calls, _, _, _ = self.run_worker([authenticate], driver="v3", context=context,
                                                    on_authenticated=postprocess)
        self.assertTrue(result["ok"])
        self.assertEqual("fixture-fresh", result["access_token"])
        self.assertEqual("saved", result["session_cache_status"])
        self.assertEqual("confirmed", context.state)
        self.assertEqual(1, len(calls))
        self.assertFalse(result["network_recovery"]["timeout"])
        saved.assert_called_once()
        postprocess.assert_called_once()

    def test_timeout_on_new_route_preserves_previous_unknown(self):
        context = _Context()
        result, calls, _, _, _ = self.run_worker([self.network_result(), self.success()], context=context,
            acquisition_error=AtRecoveryTimeout("fixture-budget"))
        self.assertFalse(result["ok"])
        self.assertEqual(2, len(calls))
        self.assertEqual("at_refresh_network_budget_exhausted", result["error"])
        self.assertTrue(result["network_recovery"]["timeout"])
        self.assertEqual("unknown", context.state)

    def test_old_network_failure_followed_by_successful_request_does_not_quarantine_on_timeout(self):
        from core.network.at_transport_recovery import recover_request

        def late_timeout(_kwargs):
            scope = current_scope()
            scope.last_failure = {"failure_kind": "transport_error", "exception_type": "ConnectionError", "recovered": False}
            response = SimpleNamespace(status_code=200)
            recover_request(SimpleNamespace(), "GET", "https://auth.openai.com/authorize", lambda: response)
            self.assertIsNone(scope.pending_network_failure)
            self.assertIsNotNone(scope.last_failure)
            raise AtRecoveryTimeout("fixture-budget")

        result, calls, routes, _, _ = self.run_worker([late_timeout])
        self.assertEqual(1, len(calls))
        self.assertTrue(result["network_recovery"]["timeout"])
        self.assertNotEqual(True, routes[0].release.call_args.kwargs.get("fault"))

    def test_completion_at_child_uses_the_same_recovery_contract(self):
        result, calls, _, _, _ = self.run_worker([self.network_result(), self.success()], completion_auth=True)
        self.assertTrue(result["ok"])
        self.assertEqual(2, len(calls))

    def test_cancellation_does_not_acquire_another_route(self):
        result, calls, routes, _, _ = self.run_worker([OperationCancelled("fixture-cancel")])
        self.assertEqual("cancelled", result["status"])
        self.assertEqual(1, len(calls))
        self.assertEqual(1, len(routes))

    def test_browser_diagnostics_keep_only_fixed_network_values(self):
        safe = service._safe_refresh_auth_diagnostics({"operation": "roxy_login", "failure_kind": "transport_error",
            "network_error": "ERR_TUNNEL_CONNECTION_FAILED", "transport_kind": "proxy", "private": "fixture-private"})
        self.assertEqual("ERR_TUNNEL_CONNECTION_FAILED", safe["network_error"])
        self.assertEqual("proxy", safe["transport_kind"])
        self.assertNotIn("private", safe)


if __name__ == "__main__":
    unittest.main()
