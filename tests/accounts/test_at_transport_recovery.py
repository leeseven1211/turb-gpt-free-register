"""独立 AT 网络恢复的请求上限、分类边界及共享认证隔离。"""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import requests
from curl_cffi.requests import exceptions as curl_errors

from core.network.at_transport_recovery import (
    AtRecoveryScope, AtRecoveryTimeout, current_scope, exhausted, network_failure,
    recover_request, result_network_failure,
)


URL = "https://auth.openai.com/api/accounts/password/verify?fixture=private"
PRIVATE = "fixture-private-token@example.test"


def response(status=200, body="{}"):
    result = requests.Response()
    result.status_code = status
    result._content = body.encode()
    result.close = Mock()
    return result


class AtTransportScopeTests(unittest.TestCase):
    def test_scope_nesting_and_failure_cleanup_do_not_leak_between_calls(self):
        outer, inner = AtRecoveryScope(), AtRecoveryScope()
        self.assertIsNone(current_scope())
        with outer.activate():
            self.assertTrue(outer.active)
            with outer.suspend():
                self.assertIsNone(current_scope())
                self.assertFalse(outer.active)
            self.assertIs(outer, current_scope())
            with self.assertRaises(ValueError), inner.activate():
                self.assertIs(inner, current_scope())
                raise ValueError("fixture")
            self.assertIs(outer, current_scope())
        self.assertIsNone(current_scope())

    def test_inactive_requests_keep_original_call_count_and_exception(self):
        error = requests.ConnectionError(PRIVATE)
        invoke = Mock(side_effect=error)
        session = SimpleNamespace(reset_transport=Mock())
        with self.assertRaises(requests.ConnectionError) as caught:
            recover_request(session, "POST", URL, invoke)
        self.assertIs(error, caught.exception)
        invoke.assert_called_once()
        session.reset_transport.assert_not_called()
        self.assertFalse(exhausted(error))

    def test_transport_retry_keeps_session_and_request_and_reports_only_safe_fields(self):
        session = SimpleNamespace(reset_transport=Mock(), blocked_until=0)
        success = response()
        invoke = Mock(side_effect=[requests.ConnectionError(PRIVATE), success])
        events = []
        checkpoint = Mock()
        scope = AtRecoveryScope(checkpoint=checkpoint, on_event=events.append)
        with scope.activate():
            returned = recover_request(session, "POST", URL, invoke)
        self.assertIs(success, returned)
        self.assertEqual(2, invoke.call_count)
        session.reset_transport.assert_called_once()
        self.assertEqual(1, scope.same_route_retries)
        self.assertTrue(scope.last_failure["recovered"])
        self.assertEqual("password_verify", events[0]["operation"])
        self.assertEqual(1, events[0]["retry_attempt"])
        self.assertNotIn(PRIVATE, str(events))
        self.assertNotIn("fixture=", str(events))
        self.assertGreater(checkpoint.call_count, 2)

    def test_two_transport_failures_preserve_original_exception_and_exhaustion(self):
        first, final = requests.ConnectionError("first"), requests.ReadTimeout(PRIVATE)
        invoke = Mock(side_effect=[first, final])
        scope = AtRecoveryScope()
        with scope.activate(), self.assertRaises(requests.ReadTimeout) as caught:
            recover_request(SimpleNamespace(blocked_until=0), "POST", URL, invoke)
        self.assertIs(final, caught.exception)
        self.assertEqual(PRIVATE, str(final))
        with scope.activate():
            self.assertTrue(exhausted(final))
            wrapper = RuntimeError("wrapped")
            wrapper.__cause__ = final
            self.assertTrue(exhausted(wrapper))
        self.assertFalse(exhausted(final))
        self.assertEqual(2, invoke.call_count)
        self.assertTrue(scope.last_failure["same_route_retry_exhausted"])

    def test_temporary_http_retries_once_and_marks_final_response(self):
        for status in (408, 500, 502, 503, 504, 520, 521, 522, 523, 524):
            with self.subTest(status=status):
                first, final = response(status), response(status)
                invoke = Mock(side_effect=[first, final])
                session = SimpleNamespace(reset_transport=Mock())
                scope = AtRecoveryScope()
                with scope.activate():
                    self.assertIs(final, recover_request(session, "GET", URL, invoke))
                    self.assertTrue(exhausted(final))
                    error = requests.HTTPError("fixture", response=final)
                    self.assertTrue(exhausted(error))
                first.close.assert_called_once()
                final.close.assert_not_called()
                session.reset_transport.assert_not_called()
                self.assertEqual(2, invoke.call_count)

    def test_business_status_and_business_error_body_never_retry(self):
        for status, body in ((403, "{}"), (429, "{}"), (401, "{}"),
                             (503, '{"error":{"code":"invalid_password","type":"authentication_error"}}'),
                             (503, '{"error":{"code":"invalid_password","type":"server_error"}}')):
            with self.subTest(status=status, body=body):
                original = response(status, body)
                invoke = Mock(return_value=original)
                with AtRecoveryScope().activate():
                    self.assertIs(original, recover_request(SimpleNamespace(), "POST", URL, invoke))
                invoke.assert_called_once()

    def test_scope_does_not_recover_external_services_or_plain_runtime_text(self):
        for url, error in (("https://mailbox.example.test/inbound/code", requests.ConnectionError(PRIVATE)),
                           (URL, RuntimeError("timeout proxy connection " + PRIVATE))):
            with self.subTest(url=url), AtRecoveryScope().activate():
                invoke = Mock(side_effect=error)
                with self.assertRaises(type(error)):
                    recover_request(SimpleNamespace(), "GET", url, invoke)
                invoke.assert_called_once()

    def test_dynamic_path_is_templated_and_cookie_circuit_is_not_cleared(self):
        session = SimpleNamespace(reset_transport=Mock(), blocked_until=99999999999)
        invoke = Mock(side_effect=[requests.ConnectionError(PRIVATE), response()])
        scope = AtRecoveryScope()
        with scope.activate():
            recover_request(session, "GET", "https://auth.openai.com/mfa-challenge/private-factor?code=private", invoke)
        self.assertEqual("/mfa-challenge/<factor>", scope.last_failure["target_path"])
        self.assertNotIn("private-factor", str(scope.last_failure))
        session.reset_transport.assert_not_called()

    def test_budget_expiry_and_cancellation_do_not_retry(self):
        from core.auth.state_machine import StageTimeout

        with patch("core.network.at_transport_recovery.time.monotonic", return_value=10):
            scope = AtRecoveryScope(deadline=9)
            with self.assertRaises(AtRecoveryTimeout):
                with scope.activate():
                    self.fail("已过截止时间的作用域不得执行请求")
        self.assertIsNone(current_scope())
        error = AtRecoveryTimeout("fixture")
        self.assertIsNone(network_failure(error=error))
        stage_error = StageTimeout("fixture-stage-budget")
        wrapper = RuntimeError("fixture-wrapper")
        wrapper.__cause__ = stage_error
        for error in (stage_error, wrapper):
            self.assertIsNone(network_failure(error=error))
            invoke = Mock(side_effect=error)
            with AtRecoveryScope().activate(), self.assertRaises(type(error)):
                recover_request(SimpleNamespace(), "GET", URL, invoke)
            invoke.assert_called_once()
        scope = AtRecoveryScope(checkpoint=Mock(side_effect=ValueError("cancel-fixture")))
        with self.assertRaisesRegex(ValueError, "cancel-fixture"):
            with scope.activate():
                pass
        self.assertIsNone(current_scope())

    def test_browser_session_recalculates_deadline_for_each_actual_attempt(self):
        from core.auth.protocol.session import BrowserSession

        session = BrowserSession.__new__(BrowserSession)
        session.session = SimpleNamespace(timeout=90)
        session.reset_transport = Mock()
        bounded = []

        def actual(*_args, **kwargs):
            bounded.append(session._bounded_request_kwargs(kwargs)["timeout"])
            if len(bounded) == 1:
                raise requests.ConnectionError("fixture")
            return response()

        session._get_once = Mock(side_effect=actual)
        scope = AtRecoveryScope(deadline=30)
        with patch("core.network.at_transport_recovery.time.monotonic", side_effect=[10, 10, 10, 11, 12, 13, 14, 15, 16, 17]), scope.activate():
            self.assertEqual(200, session.get(URL).status_code)
        self.assertEqual(2, len(bounded))
        self.assertGreater(bounded[0], bounded[1])


class AtTransportClassificationTests(unittest.TestCase):
    def test_curl_transport_failure_after_partial_success_headers_recovers_once(self):
        for status in (200, 302, 503):
            with self.subTest(status=status):
                partial = response(status)
                error = curl_errors.Timeout("离线复现：已收到响应头但正文尚未完成", code=28, response=partial)
                invoke = Mock(side_effect=error)
                scope = AtRecoveryScope()
                with scope.activate(), self.assertRaises(curl_errors.Timeout):
                    recover_request(SimpleNamespace(), "GET", "https://chatgpt.com/auth/login", invoke)
                self.assertEqual(2, invoke.call_count)
                self.assertEqual(1, scope.same_route_retries)
                self.assertEqual("transport_error", scope.last_failure["failure_kind"])
                self.assertEqual(28, scope.last_failure["curl_error_code"])
                self.assertEqual(status, scope.last_failure["http_status"])
                self.assertIs(True, scope.last_failure["response_observed"])

    def test_partial_response_keeps_business_and_restriction_exclusions(self):
        for status, body in (
            (400, "{}"), (401, "{}"), (403, "{}"), (409, "{}"), (422, "{}"), (429, "{}"),
            (200, '{"error":{"code":"invalid_password","type":"server_error"}}'),
            (503, '{"error":{"code":"invalid_password","type":"server_error"}}'),
        ):
            with self.subTest(status=status, body=body):
                error = curl_errors.Timeout("离线业务边界", code=28, response=response(status, body))
                self.assertIsNone(network_failure(error=error))
                invoke = Mock(side_effect=error)
                scope = AtRecoveryScope()
                with scope.activate(), self.assertRaises(curl_errors.Timeout):
                    recover_request(SimpleNamespace(), "GET", URL, invoke)
                invoke.assert_called_once()
                self.assertEqual(0, scope.same_route_retries)
                self.assertIsNone(scope.pending_network_failure)

    def test_v2_runtime_wrapper_keeps_partial_200_timeout_available_for_route_recovery(self):
        partial = response(200)
        error = curl_errors.Timeout("离线复现真实预检包装", code=28, response=partial)
        scope = AtRecoveryScope()
        with scope.activate():
            with self.assertRaises(curl_errors.Timeout):
                recover_request(SimpleNamespace(), "GET", "https://chatgpt.com/auth/login", Mock(side_effect=error))
            wrapped = {"ok": False, "error": "network_preflight_failed", "auth_diagnostics": {
                "operation": "network_preflight", "failure_kind": "runtime_exception",
                "exception_type": "Timeout", "http_status": 200, "response_observed": True,
            }}
            failure = result_network_failure(wrapped)
            self.assertEqual("transport_error", failure["failure_kind"])
            self.assertEqual(200, failure["http_status"])
            self.assertIs(True, failure["response_observed"])
            self.assertEqual(28, failure["curl_error_code"])
            self.assertEqual(1, scope.same_route_retries)
            self.assertTrue(failure["same_route_retry_exhausted"])

    def test_structured_transport_diagnostics_preserve_partial_response_evidence(self):
        for status in (200, 302, 503):
            with self.subTest(status=status):
                failure = result_network_failure({"ok": False, "error": "session_fetch_failed", "auth_diagnostics": {
                    "operation": "session_fetch", "failure_kind": "transport_error", "exception_type": "Timeout",
                    "curl_error_code": 28, "http_status": status, "response_observed": True,
                }})
                self.assertEqual("transport_error", failure["failure_kind"])
                self.assertEqual(status, failure["http_status"])
                self.assertIs(True, failure["response_observed"])

    def test_network_classification_uses_real_error_types_and_numeric_curl_codes(self):
        for error in (requests.ConnectionError(PRIVATE), requests.ReadTimeout(PRIVATE),
                      ConnectionRefusedError(PRIVATE), curl_errors.ConnectionError(PRIVATE, code=56)):
            with self.subTest(error=type(error).__name__):
                diagnostic = network_failure(error=error)
                self.assertEqual("transport_error", diagnostic["failure_kind"])
                self.assertNotIn(PRIVATE, str(diagnostic))
        for error in (RuntimeError("curl: (56) connection timeout"), ValueError("proxy failure")):
            self.assertIsNone(network_failure(error=error))

    def test_mailbox_failures_never_trigger_openai_proxy_recovery(self):
        from core.email.email_butler.client import EmailButlerClientError

        for code in ("inbound_code_timeout", "source_authentication_failed", "inbound_request_failed"):
            error = EmailButlerClientError(PRIVATE, error_code=code)
            error.__cause__ = requests.ReadTimeout(PRIVATE)
            self.assertIsNone(network_failure(error=error))
            wrapped = RuntimeError("wrapped mailbox failure")
            wrapped.__cause__ = error
            self.assertIsNone(network_failure(error=wrapped))
            send_failure = requests.ConnectionError("current OpenAI send failure")
            send_failure.__context__ = error
            self.assertEqual("transport_error", network_failure(error=send_failure)["failure_kind"])
            with AtRecoveryScope(last_failure={"failure_kind": "transport_error"}).activate():
                self.assertIsNone(result_network_failure({"ok": False, "error": "email_otp_failed", "auth_diagnostics": {
                    "operation": "email_otp", "failure_kind": "transport_error", "mailbox_error_code": code,
                    "exception_type": "ReadTimeout",
                }}))

    def test_safe_roxy_network_evidence_is_supported_including_otp_submission(self):
        for operation, network_error in (("roxy_login", "ERR_CONNECTION_RESET"),
                                         ("roxy_email_otp", "Failed to fetch"),
                                         ("roxy_session", "ERR_CERT_DATE_INVALID")):
            with self.subTest(operation=operation):
                info = result_network_failure({"ok": False, "error_code": "roxy_login_failed", "auth_diagnostics": {
                    "operation": operation, "failure_kind": "transport_error", "network_error": network_error,
                }})
                self.assertIsNotNone(info)
                self.assertEqual(network_error, info["network_error"])

    def test_v3_cached_session_http_failure_uses_the_actual_driver_contract(self):
        from core.accounts.liveness.protocol import v3

        for status in (503, 403, 429):
            with self.subTest(status=status):
                session = SimpleNamespace(get=Mock(return_value=response(status)),
                                          get_nextauth_headers=lambda **_kwargs: {})
                with AtRecoveryScope().activate(), self.assertRaises(v3.ProtocolV2AuthError) as caught:
                    v3._read_session(session, cached=True)
                error = caught.exception
                self.assertEqual("cached_session_http_failed", error.code)
                self.assertNotIn("failure_kind", error.diagnostics)
                result = {"ok": False, "error": error.code, "auth_diagnostics": error.diagnostics}
                failure = result_network_failure(result)
                if status == 503:
                    self.assertEqual(503, failure["http_status"])
                else:
                    self.assertIsNone(failure)

    def test_driver_generic_http_wrapper_preserves_latest_business_response_exclusion(self):
        from core.accounts.liveness.protocol import v3

        for later_kind in ("http_error", "transport_error"):
            with self.subTest(later_kind=later_kind):
                original = response(503, '{"error":{"code":"invalid_password","type":"server_error"}}')
                invoke = Mock(return_value=original)
                transport = SimpleNamespace()
                session = SimpleNamespace(
                    get=lambda url, **_kwargs: recover_request(transport, "GET", url, invoke),
                    get_nextauth_headers=lambda **_kwargs: {},
                )
                scope = AtRecoveryScope()
                with scope.activate():
                    with self.assertRaises(v3.ProtocolV2AuthError) as caught:
                        v3._read_session(session, cached=True)
                    error = caught.exception
                    self.assertEqual("cached_session_http_failed", error.code)
                    self.assertEqual(503, error.diagnostics["http_status"])
                    self.assertNotIn("auth_error", error.diagnostics)
                    self.assertIsNone(result_network_failure({
                        "ok": False, "error": error.code, "auth_diagnostics": error.diagnostics,
                    }))
                    invoke.assert_called_once()

                    if later_kind == "http_error":
                        invoke.side_effect = [response(503), response(503)]
                    else:
                        invoke.side_effect = [requests.ConnectionError("fixture-first"),
                                              requests.ConnectionError("fixture-final")]
                    with self.assertRaises(v3.ProtocolV2AuthError) as caught:
                        v3._read_session(session, cached=True)
                    error = caught.exception
                    failure = result_network_failure({
                        "ok": False, "error": error.code, "auth_diagnostics": error.diagnostics,
                    })
                    self.assertEqual(later_kind, failure["failure_kind"])
                    self.assertEqual(3, invoke.call_count)

    def test_business_and_invalid_response_override_old_scope_network_failure(self):
        scope = AtRecoveryScope(last_failure={"failure_kind": "transport_error", "exception_type": "ConnectionError"})
        with scope.activate():
            for code in ("password_rejected", "mfa_rejected", "source_authentication_failed", "session_invalid_response",
                         "roxy_profile_open_failed", "unknown_business_fixture"):
                with self.subTest(code=code):
                    self.assertIsNone(result_network_failure({"ok": False, "error": code}))
            self.assertIsNotNone(result_network_failure({"ok": False, "error": "protocol_v3_unknown_error"}))
            self.assertIsNone(result_network_failure({"ok": True}))
            self.assertIsNone(result_network_failure({"ok": False, "error": "protocol_network_error", "http_status": 429}))
            self.assertIsNone(result_network_failure({"ok": False, "error": "unknown_business_fixture", "http_status": 503}))
            self.assertIsNone(result_network_failure({"ok": False, "error": "password_result_unknown", "auth_diagnostics": {
                "operation": "password_verify", "failure_kind": "http_error", "http_status": 503,
                "auth_error": {"code": "invalid_password", "type": "server_error"},
            }}))
            scope.last_failure["recovered"] = True
            self.assertIsNone(result_network_failure({"ok": False, "error": "protocol_v3_unknown_error"}))

    def test_later_success_or_business_response_prevents_stale_network_evidence(self):
        for later in (response(200), response(403)):
            with self.subTest(status=later.status_code):
                scope = AtRecoveryScope()
                with scope.activate():
                    with self.assertRaises(requests.ConnectionError):
                        recover_request(SimpleNamespace(), "POST", URL,
                                        Mock(side_effect=requests.ConnectionError("fixture-optional-bootstrap")))
                    previous = dict(scope.last_failure)
                    self.assertIsNotNone(scope.pending_network_failure)
                    self.assertIsNotNone(result_network_failure({"ok": False, "error": "protocol_v2_unknown_error"}))
                    recover_request(SimpleNamespace(), "GET", "https://chatgpt.com/api/auth/csrf", Mock(return_value=later))
                    self.assertEqual(previous, scope.last_failure)
                    self.assertIsNone(scope.pending_network_failure)
                    self.assertIsNone(result_network_failure({"ok": False, "error": "protocol_v2_unknown_error"}))


class AtExistingRetryIntegrationTests(unittest.TestCase):
    def test_shared_authorize_retry_budget_is_only_replaced_inside_at_scope(self):
        from core.auth.protocol import openai_auth

        with patch.object(openai_auth._protocol_cfg, "OPENAI_PROXY_RETRY_MAX_ATTEMPTS", 3):
            self.assertEqual(3, openai_auth._proxy_retry_config()[0])
            with AtRecoveryScope().activate():
                self.assertEqual((1, 0.0), openai_auth._proxy_retry_config())
            self.assertEqual(3, openai_auth._proxy_retry_config()[0])

    def test_preflight_does_not_add_another_route_loop_in_at_scope(self):
        from core.accounts.liveness.protocol import legacy

        session = SimpleNamespace(session=SimpleNamespace(close=Mock()), proxy="fixture")
        supplier = Mock(return_value="fixture")
        with (
            patch.object(legacy, "BrowserSession", return_value=session),
            patch.object(legacy, "_warm_protocol_login_context", side_effect=requests.ConnectionError("connection")),
            AtRecoveryScope().activate(), self.assertRaises(requests.ConnectionError),
        ):
            legacy._network_preflight_with_retry("fixture@example.test", "fixture", proxy_supplier=supplier)
        supplier.assert_called_once_with(1)

    def test_exhausted_otp_request_does_not_resend_and_restart_the_step(self):
        from core.accounts.liveness.protocol import legacy

        error = requests.ConnectionError("connection closed")
        scope = AtRecoveryScope()
        with scope.activate():
            with self.assertRaises(requests.ConnectionError):
                recover_request(SimpleNamespace(), "POST", URL, Mock(side_effect=error))
            with (
                patch.object(legacy, "_ensure_at_otp_sent", return_value=1),
                patch.object(legacy, "wait_for_otp", return_value="654321"),
                patch.object(legacy, "validate_email_otp", side_effect=error),
                patch.object(legacy, "_resend_at_otp") as send,
                self.assertRaises(requests.ConnectionError),
            ):
                legacy._validate_with_retry(object(), "fixture@example.test", 1)
            send.assert_not_called()

    def test_oauth_callback_is_not_replayed_by_the_low_level_request_wrapper(self):
        error = requests.ConnectionError("connection closed")
        invoke = Mock(side_effect=error)
        with AtRecoveryScope().activate():
            with self.assertRaises(requests.ConnectionError):
                recover_request(SimpleNamespace(), "GET", "https://chatgpt.com/api/auth/callback/openai?code=private", invoke)
            self.assertFalse(exhausted(error))
        invoke.assert_called_once()

    def test_callback_probes_session_then_has_only_one_original_route_recovery(self):
        from core.accounts.liveness.protocol import callback

        callback_url = "https://chatgpt.com/api/auth/callback/openai?code=private"
        info = {"accessToken": "fixture"}
        callback_response = response(302)
        callback_response.headers["Location"] = "/"
        replies = iter([requests.ConnectionError("connection closed"), response(401), callback_response, response(200)])
        requests_seen = []
        session = SimpleNamespace(session=SimpleNamespace(cookies=[]), blocked_until=0,
                                  get_nextauth_headers=lambda **_kwargs: {}, get_chatgpt_navigate_headers=lambda **_kwargs: {})

        def invoke(url, **_kwargs):
            requests_seen.append(url)
            reply = next(replies)
            if isinstance(reply, BaseException):
                raise reply
            return reply

        session.get = lambda url, **kwargs: recover_request(session, "GET", url, lambda: invoke(url, **kwargs))
        scope = AtRecoveryScope()
        with scope.activate(), patch.object(callback, "_verify_session", return_value=info):
            self.assertIs(info, callback.complete_callback(session, callback_url, referer="fixture", email="fixture@example.test"))
        self.assertEqual([callback_url, callback._SESSION_URL, callback_url, callback._SESSION_URL], requests_seen)
        self.assertEqual(1, scope.same_route_retries)

    def test_callback_session_does_not_repeat_an_already_exhausted_http_request(self):
        from core.accounts.liveness.protocol import callback

        invoke = Mock(side_effect=[response(503), response(503)])
        session = SimpleNamespace(get_nextauth_headers=lambda **_kwargs: {})
        session.get = lambda url, **_kwargs: recover_request(session, "GET", url, invoke)
        with AtRecoveryScope().activate(), self.assertRaises(callback.CallbackRecoveryError):
            callback._read_session(session, "fixture@example.test", recovery=callback._Recovery(), hop=1, checkpoint=None)
        self.assertEqual(2, invoke.call_count)

    def test_active_callback_uses_the_at_network_statuses_without_changing_legacy_policy(self):
        from core.accounts.liveness.protocol import callback

        url = "https://chatgpt.com/api/auth/callback/openai?code=private"
        for status in (408, 500, 520, 521, 522, 523, 524):
            with self.subTest(status=status):
                failed = response(status)
                args = {"kind": "http_error", "hop": 1, "attempt": 0, "response": failed}
                self.assertFalse(callback._failure("oauth_callback_failed", "oauth_callback", url, **args).retryable)
                with AtRecoveryScope().activate():
                    self.assertTrue(callback._failure("oauth_callback_failed", "oauth_callback", url, **args).retryable)

    def test_callback_deadline_signal_escapes_without_probe_or_replay(self):
        from core.accounts.liveness.protocol import callback

        session = SimpleNamespace(get=Mock(side_effect=AtRecoveryTimeout("fixture-deadline")),
                                  get_nextauth_headers=lambda **_kwargs: {}, get_chatgpt_navigate_headers=lambda **_kwargs: {})
        with AtRecoveryScope().activate(), self.assertRaises(AtRecoveryTimeout):
            callback.complete_callback(session, "https://chatgpt.com/api/auth/callback/openai?code=private",
                                       referer="fixture", email="fixture@example.test")
        session.get.assert_called_once()

    def test_callback_with_existing_cookie_probes_without_replaying_the_code(self):
        from core.accounts.liveness.protocol import callback

        cookie = SimpleNamespace(name="__Secure-next-auth.session-token", domain="chatgpt.com", value="fixture")
        seen = []
        replies = iter([requests.ConnectionError("connection closed"), response(401)])
        session = SimpleNamespace(session=SimpleNamespace(cookies=[cookie]), blocked_until=0,
                                  get_nextauth_headers=lambda **_kwargs: {}, get_chatgpt_navigate_headers=lambda **_kwargs: {})

        def invoke(url):
            seen.append(url)
            reply = next(replies)
            if isinstance(reply, BaseException):
                raise reply
            return reply

        session.get = lambda url, **_kwargs: recover_request(session, "GET", url, lambda: invoke(url))
        url = "https://chatgpt.com/api/auth/callback/openai?code=private"
        with AtRecoveryScope().activate(), self.assertRaises(callback.CallbackRecoveryError):
            callback.complete_callback(session, url, referer="fixture", email="fixture@example.test")
        self.assertEqual([url, callback._SESSION_URL], seen)


if __name__ == "__main__":
    unittest.main()
