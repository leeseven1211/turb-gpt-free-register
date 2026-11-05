"""Roxy AT 网络恢复只采用当前请求证据，不重放已派发的表单。"""
from contextlib import ExitStack
from types import SimpleNamespace
import json
import time
import unittest
from unittest.mock import MagicMock, patch

import requests
from selenium.common.exceptions import TimeoutException, WebDriverException

from core.accounts.liveness.roxy import flow
from core.auth.state_machine import StageTimeout
from core.network.at_transport_recovery import AtRecoveryScope, AtRecoveryTimeout


EMAIL = "roxy-network@example.test"
PRIVATE = "fixture-private https://fixture.invalid/private?token=fixture-secret"


class RoxyNetworkEvidenceTests(unittest.TestCase):
    def diagnose(self, error, stage="login", *, driver=None):
        with AtRecoveryScope().activate():
            return flow._at_network_diagnostics(error, stage, driver)

    def test_inactive_scope_keeps_existing_behavior_without_browser_reads(self):
        driver = MagicMock()
        self.assertEqual({}, flow._at_network_diagnostics(
            WebDriverException("net::ERR_CONNECTION_RESET " + PRIVATE), "login", driver,
        ))
        driver.execute_script.assert_not_called()

    def test_only_real_chrome_error_document_can_supply_a_page_network_code(self):
        driver = MagicMock()
        for url, expected in (("https://auth.openai.com/email-verification", ""),
                              ("chrome-error://chromewebdata/", "ERR_CONNECTION_RESET")):
            with self.subTest(url=url):
                driver.execute_script.return_value = {"url": url, "text": "ERR_CONNECTION_RESET " + PRIVATE}
                diagnostics = self.diagnose(RuntimeError("页面未就绪"), driver=driver)
                self.assertEqual(expected, diagnostics.get("network_error", ""))
                self.assertNotIn("fixture-private", json.dumps(diagnostics))

    def test_chrome_navigation_and_otp_network_errors_keep_only_fixed_facts(self):
        from core.auth.browser.email_otp import EmailOtpNetworkError

        cases = (
            (WebDriverException("net::ERR_CONNECTION_RESET " + PRIVATE), "navigation", "ERR_CONNECTION_RESET", "connection"),
            (WebDriverException("net::ERR_SSL_PROTOCOL_ERROR " + PRIVATE), "navigation", "ERR_SSL_PROTOCOL_ERROR", "tls"),
            (EmailOtpNetworkError("ERR_NAME_NOT_RESOLVED", request_unknown=True), "email_otp", "ERR_NAME_NOT_RESOLVED", "dns"),
            (EmailOtpNetworkError("Failed to fetch", request_unknown=True), "email_otp", "Failed to fetch", "connection"),
            (RuntimeError("mfa_network_error: net::ERR_HTTP2_PING_FAILED"), "login", "ERR_HTTP2_PING_FAILED", "connection"),
        )
        for error, stage, code, kind in cases:
            with self.subTest(code=code):
                diagnostics = self.diagnose(error, stage)
                self.assertEqual("transport_error", diagnostics["failure_kind"])
                self.assertEqual(code, diagnostics["network_error"])
                self.assertEqual(kind, diagnostics["transport_kind"])
                self.assertIs(False, diagnostics["response_observed"])
                self.assertNotIn("fixture-private", json.dumps(diagnostics))
                if isinstance(error, EmailOtpNetworkError):
                    self.assertTrue(error.request_unknown)

    def test_no_network_evidence_does_not_turn_waits_or_driver_errors_into_proxy_faults(self):
        for error in (StageTimeout("阶段预算耗尽"), TimeoutException("renderer timeout"),
                      RuntimeError("等待验证码超时"), WebDriverException("disconnected: not connected to DevTools")):
            with self.subTest(error=type(error).__name__):
                self.assertEqual({}, self.diagnose(error))
        wrapped = RuntimeError("原阶段等待未完成")
        wrapped.__cause__ = StageTimeout("阶段预算耗尽")
        self.assertEqual({}, self.diagnose(wrapped))

    def test_local_roxy_and_driver_connections_cannot_trigger_a_proxy_retry(self):
        for stage in ("open", "driver", "callback"):
            with self.subTest(stage=stage):
                self.assertEqual({}, self.diagnose(requests.ConnectionError(PRIVATE), stage))
        for url in ("http://127.0.0.1:9515/session/fixture", "https://mail.example.test/inbound/code"):
            with self.subTest(url=url):
                error = requests.ConnectionError(PRIVATE)
                error.request = requests.Request("GET", url).prepare()
                self.assertEqual({}, self.diagnose(error))

    def test_mailbox_source_or_transport_error_is_not_browser_proxy_evidence(self):
        from core.email.email_butler.client import EmailButlerClientError

        for code in ("inbound_code_timeout", "source_authentication_failed", "inbound_request_failed"):
            with self.subTest(code=code):
                error = EmailButlerClientError(PRIVATE, error_code=code)
                error.__cause__ = requests.ConnectionError(PRIVATE)
                self.assertEqual({}, self.diagnose(error, "email_otp"))

    def test_current_auth_http_response_and_business_rejection_keep_their_meaning(self):
        for status, network in ((503, True), (403, False)):
            with self.subTest(status=status):
                response = requests.Response()
                response.status_code = status
                response.url = "https://auth.openai.com/api/accounts/email-otp/send"
                response._content = b"{}"
                error = requests.HTTPError(PRIVATE, response=response)
                diagnostics = self.diagnose(error)
                self.assertEqual(network, bool(diagnostics))
                if network:
                    self.assertEqual(503, diagnostics["http_status"])
                    self.assertEqual("http_error", diagnostics["failure_kind"])
                self.assertNotIn("fixture-private", json.dumps(diagnostics))
        error = RuntimeError("net::ERR_CONNECTION_RESET")
        error.code = "password_rejected"
        self.assertEqual({}, self.diagnose(error))


class RoxyNetworkRecoveryLifecycleTests(unittest.TestCase):
    def run_refresh(self, *, error=None, scope=True, full_debug=True, stage="login", callback=None,
                    after_open=None, after_session=None):
        driver = MagicMock(current_url="https://auth.openai.com/email-verification")
        driver.execute_script.return_value = {"url": driver.current_url, "text": ""}
        opened = SimpleNamespace(profile_id="fixture-current-profile", account_bound=True,
                                 created_by_run=False, debugger_address="127.0.0.1:9999")
        client = MagicMock()
        client.open_profile_for_account.return_value = opened
        if after_open is not None:
            client.open_profile_for_account.side_effect = lambda **_kwargs: after_open(opened) or opened
        debug = SimpleNamespace(capture_mode="full") if full_debug else None
        events = []
        navigation = MagicMock(side_effect=error if stage == "navigation" else None)
        login = MagicMock(side_effect=error if stage == "login" else None, return_value="logged_in")
        driver._fixture_navigation = navigation
        driver._fixture_login = login

        def fetch_session(*_args, **_kwargs):
            if stage == "session" and error is not None:
                raise error
            if callable(after_session):
                after_session()
            return {"accessToken": "fixture-at", "user": {"email": EMAIL}}

        with ExitStack() as stack:
            for item in (
                patch.object(flow, "available", return_value=True),
                patch.object(flow, "check_cancelled"),
                patch.object(flow, "current_token", return_value=None),
                patch.object(flow, "RoxyBrowserClient", return_value=client),
                patch.object(flow, "_build_driver", return_value=driver),
                patch.object(flow, "_center_browser_window"),
                patch.object(flow, "_safe_get", navigation),
                patch.object(flow, "_page_warmup"),
                patch.object(flow, "_maybe_accept"),
                patch.object(flow, "_page_account_unusable_code", return_value=""),
                patch.object(flow, "_login_existing_account_with_recovery", login),
                patch.object(flow, "_fetch_chatgpt_session", side_effect=fetch_session),
                patch.object(flow, "_quit_driver", side_effect=lambda _driver: events.append("quit")),
                patch.object(flow, "password_receipt_ids", return_value=frozenset()),
                patch.object(flow, "password_evidence", return_value={"credential_check": "unverified", "submitted": False}),
                patch.object(flow.cfg, "ROXY_KEEP_BROWSER_OPEN", True),
                patch("core.browser.roxy.profile_binding.account_profile_id_by_email", return_value=opened.profile_id),
                patch("core.codex.roxy.oauth._account_login_credentials", return_value=("fixture-password", "")),
                patch("core.browser.flow_policy.install_for_flow"),
                patch("core.browser.asset_policy.start_auth_asset_cache"),
                patch("core.browser.asset_policy.stop_asset_cache"),
                patch("core.browser.traffic.bind_roxy_capture"),
                patch("core.browser.traffic.finish_roxy_capture"),
                patch("core.registration.debug.current_session", return_value=debug),
                patch("core.registration.debug.attach_current_roxy"),
                patch("core.registration.debug.capture_current_failure", side_effect=lambda *_args: events.append("capture")),
                patch.object(flow, "_authenticated_browser_session", return_value=MagicMock()),
            ):
                stack.enter_context(item)
            if scope:
                stack.enter_context((scope if isinstance(scope, AtRecoveryScope) else AtRecoveryScope()).activate())
            try:
                result = flow.refresh_access_token(EMAIL, proxy="http://fixture-proxy.invalid:8080", on_authenticated=callback)
            except AtRecoveryTimeout as exc:
                self.timeout_lifecycle = (client, driver, events)
                raise exc
        return result, client, driver, events

    def test_active_network_failure_captures_then_closes_only_this_profile(self):
        result, client, driver, events = self.run_refresh(error=WebDriverException("net::ERR_CONNECTION_RESET"))
        self.assertEqual("roxy_login_failed", result["error_code"])
        self.assertEqual("ERR_CONNECTION_RESET", result["auth_diagnostics"]["network_error"])
        self.assertEqual("roxy_login", result["auth_diagnostics"]["operation"])
        self.assertNotIn("debug_browser_kept", result)
        self.assertLess(events.index("capture"), events.index("quit"))
        client.close_profile.assert_called_once_with("fixture-current-profile")
        client.cleanup_profile.assert_called_once_with(client.open_profile_for_account.return_value)
        client.delete_profile.assert_not_called()
        driver.find_element.assert_not_called()
        driver._fixture_login.assert_called_once()

    def test_inactive_network_failure_preserves_debug_and_keep_open_preference(self):
        result, client, _, events = self.run_refresh(error=WebDriverException("net::ERR_CONNECTION_RESET"), scope=False)
        self.assertEqual("runtime_exception", result["auth_diagnostics"]["failure_kind"])
        self.assertNotIn("network_error", result["auth_diagnostics"])
        self.assertTrue(result["debug_browser_kept"])
        self.assertNotIn("quit", events)
        client.close_profile.assert_not_called()
        client.cleanup_profile.assert_not_called()

    def test_generic_stage_timeout_keeps_the_failure_window_for_diagnosis(self):
        result, client, _, events = self.run_refresh(error=StageTimeout("页面等待预算耗尽"))
        self.assertEqual("runtime_exception", result["auth_diagnostics"]["failure_kind"])
        self.assertTrue(result["debug_browser_kept"])
        self.assertNotIn("quit", events)
        client.close_profile.assert_not_called()

    def test_navigation_failure_does_not_submit_or_repeat_the_login_form(self):
        result, client, driver, _ = self.run_refresh(
            error=WebDriverException("net::ERR_NAME_NOT_RESOLVED"), stage="navigation",
        )
        self.assertEqual("roxy_navigation_failed", result["error_code"])
        self.assertEqual("dns", result["auth_diagnostics"]["transport_kind"])
        self.assertIs(False, result["remote_request_started"])
        self.assertIs(False, result["action_dispatched"])
        driver.find_element.assert_not_called()
        driver._fixture_login.assert_not_called()
        driver._fixture_navigation.assert_called_once()
        self.assertEqual(2, driver._fixture_navigation.call_args.kwargs["attempts"])
        client.close_profile.assert_called_once_with("fixture-current-profile")

    def test_callback_failure_after_at_was_acquired_does_not_restart_login(self):
        def callback(_result, _session):
            raise requests.ConnectionError(PRIVATE)

        result, client, _, _ = self.run_refresh(stage="callback", callback=callback)
        self.assertEqual("roxy_authenticated_callback_failed", result["error_code"])
        self.assertNotIn("network_error", result["auth_diagnostics"])
        self.assertTrue(result["auth_facts"]["session_acquired"])
        client.close_profile.assert_not_called()

    def test_deadline_reached_after_session_read_does_not_discard_the_acquired_at(self):
        scope = AtRecoveryScope(deadline=time.monotonic() + 60)
        callback = MagicMock(side_effect=lambda result, _session: result)
        result, _, driver, _ = self.run_refresh(
            scope=scope, callback=callback, after_session=lambda: setattr(scope, "deadline", 0),
        )
        self.assertTrue(result["ok"])
        self.assertEqual("fixture-at", result["access_token"])
        callback.assert_called_once()
        driver._fixture_login.assert_called_once()

    def test_expired_scope_after_profile_open_propagates_and_cleans_this_profile(self):
        scope = AtRecoveryScope(deadline=time.monotonic() + 60)

        def expire(_opened):
            scope.deadline = time.monotonic() - 1

        with self.assertRaises(AtRecoveryTimeout):
            self.run_refresh(scope=scope, after_open=expire)
        client, _, events = self.timeout_lifecycle
        self.assertNotIn("capture", events)
        client.close_profile.assert_called_once_with("fixture-current-profile")
        client.cleanup_profile.assert_called_once_with(client.open_profile_for_account.return_value)
        client.delete_profile.assert_not_called()

    def test_scope_timeout_during_session_read_closes_driver_and_profile(self):
        with self.assertRaises(AtRecoveryTimeout):
            self.run_refresh(error=AtRecoveryTimeout("AT 总预算耗尽"), stage="session")
        client, _, events = self.timeout_lifecycle
        self.assertIn("quit", events)
        client.close_profile.assert_called_once_with("fixture-current-profile")
        client.cleanup_profile.assert_called_once_with(client.open_profile_for_account.return_value)


class RoxyAtExecutionDeadlineTests(unittest.TestCase):
    def test_active_scope_installs_deadline_with_and_without_native_token(self):
        from core.auth.browser.auth_context import current_execution_context

        for token in (None, SimpleNamespace(requested=lambda: False)):
            with self.subTest(native_token=token is not None):
                scope = AtRecoveryScope(deadline=time.monotonic() + 60)
                seen = []

                @flow._with_refresh_execution_context
                def operation():
                    context = current_execution_context()
                    self.assertIsNotNone(context)
                    self.assertEqual(scope.deadline, context.deadline)
                    seen.append(context.remaining(300))
                    scope.deadline = time.monotonic() - 1
                    context.checkpoint()

                with patch("core.operations.runtime.current_token", return_value=token), scope.activate():
                    with self.assertRaises(AtRecoveryTimeout):
                        operation()
                self.assertTrue(0 < seen[0] <= 60)

    def test_inactive_scope_without_token_preserves_the_existing_context(self):
        from core.auth.browser.auth_context import AuthExecutionContext, current_execution_context, execution_context

        original = AuthExecutionContext(metadata={"fixture": "original"})

        @flow._with_refresh_execution_context
        def operation():
            self.assertIs(original, current_execution_context())

        with patch("core.operations.runtime.current_token", return_value=None), execution_context(original):
            operation()

    def test_native_cancel_and_scope_lease_loss_keep_the_original_control_error(self):
        from core.auth.browser.auth_context import current_execution_context
        from core.operations.runtime import OperationCancelled
        from core.operations.task_gateway import OperationLeaseLost

        @flow._with_refresh_execution_context
        def operation():
            current_execution_context().checkpoint()

        token = SimpleNamespace(requested=lambda: True)
        with patch("core.operations.runtime.current_token", return_value=token), AtRecoveryScope().activate():
            with self.assertRaises(OperationCancelled):
                operation()
        error = OperationLeaseLost("fixture-lease-lost")
        scope = AtRecoveryScope()
        with patch("core.operations.runtime.current_token", return_value=None), scope.activate():
            scope.checkpoint = MagicMock(side_effect=error)
            with self.assertRaises(OperationLeaseLost) as caught:
                operation()
        self.assertIs(error, caught.exception)


if __name__ == "__main__":
    unittest.main()
