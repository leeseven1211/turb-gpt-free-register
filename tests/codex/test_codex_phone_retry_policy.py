"""Codex 协议手机失败必须有明确号码证据才能继续购买号码。"""
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.codex import oauth


def _response(status, payload=None):
    return SimpleNamespace(status_code=status, json=lambda: payload or {}, text="")


class CodexPhoneRetryPolicyTests(unittest.TestCase):
    def _phone_flow(self, *, responses, acquire_error=None, sms_error=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        http = SimpleNamespace(close=Mock())
        stack.enter_context(patch.object(oauth.sms_provider, "_http", return_value=http))
        stack.enter_context(patch.object(oauth._cfg, "SMS_MAX_RETRIES", 3))
        stack.enter_context(patch.object(oauth._cfg, "CODEX_PHONE_TOTAL_TIMEOUT", 300))
        stack.enter_context(patch.object(oauth, "_ensure_phone_verification_enabled"))
        stack.enter_context(patch.object(oauth, "check_cancelled"))
        stack.enter_context(patch.object(oauth, "_sms_provider_name", return_value="grizzly"))
        stack.enter_context(patch.object(oauth, "_sleep_before_phone_retry"))
        flow = SimpleNamespace(http=http)
        for name in ("cancel", "set_status", "complete", "report_activation_failure"):
            setattr(flow, name, stack.enter_context(patch.object(oauth.sms_provider, name)))
        flow.acquire = stack.enter_context(patch.object(
            oauth.sms_provider, "acquire_number",
            side_effect=acquire_error,
            return_value=("synthetic-activation", "synthetic-number"),
        ))
        flow.wait = stack.enter_context(patch.object(
            oauth.sms_provider, "wait_for_sms_code",
            side_effect=sms_error, return_value="synthetic-sms-code",
        ))
        flow.post = stack.enter_context(patch.object(oauth, "_post_json", side_effect=responses))
        flow.stage = stack.enter_context(patch.object(oauth, "report_stage"))
        return flow

    def test_unknown_send_409_stops_after_first_number(self):
        flow = self._phone_flow(responses=[_response(409), _response(409), _response(409)])

        with self.assertRaises(RuntimeError):
            oauth._do_phone_verification(object())

        self.assertEqual(1, flow.acquire.call_count)
        flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)
        flow.wait.assert_not_called()
        flow.report_activation_failure.assert_not_called()
        flow.http.close.assert_called_once_with()

    def test_non_number_send_failures_stop_without_country_penalty(self):
        for status, payload in (
            (409, {"error": {"code": "invalid_state"}}),
            (400, {"error": {"message": "Unable to send SMS"}}),
            (429, {"error": {"message": "Too many requests"}}),
            (500, {}),
            (400, {"error": {"message": "WhatsApp is required"}}),
            (400, {"error": {"message": "Maximum verification attempts"}}),
        ):
            with self.subTest(status=status, payload=payload):
                flow = self._phone_flow(responses=[_response(status, payload)] * 3)
                with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
                    oauth._do_phone_verification(object())
                self.assertEqual(1, flow.acquire.call_count)
                self.assertEqual(status, raised.exception.http_status)
                self.assertEqual("phone_send", raised.exception.diagnostics["operation"])
                flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)
                flow.wait.assert_not_called()
                flow.report_activation_failure.assert_not_called()
                self.assertEqual("phone_otp", flow.stage.call_args.args[0])
                self.assertEqual("failed", flow.stage.call_args.kwargs["state"])

    def test_explicit_number_rejection_can_rotate_then_complete(self):
        flow = self._phone_flow(responses=[
            _response(400, {"error": {"code": "invalid_phone_number", "message": "Invalid phone number"}}),
            _response(204),
            _response(200, {"continue_url": "/sign-in-with-chatgpt/codex/consent"}),
        ])
        flow.acquire.side_effect = [
            ("rejected-activation", "rejected-number"),
            ("accepted-activation", "accepted-number"),
        ]

        result = oauth._do_phone_verification(object())

        self.assertEqual("/sign-in-with-chatgpt/codex/consent", result["continue_url"])
        self.assertEqual(2, flow.acquire.call_count)
        flow.cancel.assert_called_once_with("rejected-activation", flow.http, background=True)
        self.assertEqual(1, flow.report_activation_failure.call_count)
        flow.complete.assert_called_once_with("accepted-activation", flow.http)

    def test_validate_error_never_buys_another_number(self):
        for status, payload in (
            (400, {"error": {"code": "invalid_otp"}}),
            (409, {"error": {"code": "invalid_state"}}),
            (500, {}),
            (400, {"error": {"code": "invalid_phone_number", "message": "Invalid phone number"}}),
        ):
            with self.subTest(status=status):
                flow = self._phone_flow(responses=[_response(200), _response(status, payload)] * 3)
                with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
                    oauth._do_phone_verification(object())
                self.assertEqual(1, flow.acquire.call_count)
                self.assertEqual("phone_validate", raised.exception.diagnostics["operation"])
                flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)
                flow.report_activation_failure.assert_not_called()
                flow.complete.assert_not_called()

    def test_sms_timeout_cancels_without_buying_another_number(self):
        flow = self._phone_flow(responses=[_response(200)] * 3, sms_error=oauth.sms_provider.SmsCodeTimeout("private-timeout"))
        with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
            oauth._do_phone_verification(object())
        self.assertEqual(1, flow.acquire.call_count)
        self.assertEqual("phone_wait", raised.exception.diagnostics["operation"])
        self.assertEqual("sms_timeout", raised.exception.diagnostics["failure_kind"])
        self.assertNotIn("private-timeout", str(raised.exception))
        flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)
        flow.report_activation_failure.assert_not_called()

    def test_send_transport_exception_cleans_order_and_preserves_uncertainty(self):
        flow = self._phone_flow(responses=OSError("private-network-context"))
        with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
            oauth._do_phone_verification(object())
        self.assertEqual(1, flow.acquire.call_count)
        self.assertEqual("transport_error", raised.exception.diagnostics["failure_kind"])
        self.assertFalse(raised.exception.as_result()["remote_write_rejected"])
        self.assertNotIn("private-network-context", str(raised.exception))
        flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)
        flow.http.close.assert_called_once_with()

    def test_value_error_is_unexpected_response_without_private_exception_text(self):
        flow = self._phone_flow(responses=ValueError("private-parser-context"))
        with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
            oauth._do_phone_verification(object())
        self.assertEqual("unexpected_response", raised.exception.diagnostics["failure_kind"])
        self.assertEqual("ValueError", raised.exception.diagnostics["server_message"])
        self.assertNotIn("private-parser-context", str(raised.exception))
        self.assertFalse(raised.exception.as_result()["remote_write_rejected"])
        self.assertEqual(1, flow.acquire.call_count)
        flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)

    def test_cancel_queue_failure_does_not_replace_primary_send_error(self):
        flow = self._phone_flow(responses=[_response(409, {"error": {"code": "invalid_state"}})])
        flow.cancel.side_effect = RuntimeError("private-cancel-context")
        with self.assertLogs(oauth.logger, level="WARNING") as logged:
            with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
                oauth._do_phone_verification(object())
        self.assertEqual(409, raised.exception.http_status)
        self.assertEqual("session_conflict", raised.exception.diagnostics["failure_kind"])
        self.assertNotIn("private-cancel-context", str(raised.exception))
        self.assertIn("RuntimeError", " ".join(logged.output))
        self.assertNotIn("private-cancel-context", " ".join(logged.output))
        self.assertEqual(1, flow.acquire.call_count)
        flow.http.close.assert_called_once_with()

    def test_provider_error_after_acquisition_cleans_order_and_stops(self):
        """拿号后的平台确认失败仍属于短信流程阶段。"""
        flow = self._phone_flow(responses=[_response(200)] * 3)
        flow.set_status.side_effect = oauth.sms_provider.SmsProviderError("private-provider-context")
        with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
            oauth._do_phone_verification(object())
        self.assertEqual(1, flow.acquire.call_count)
        self.assertEqual("phone_provider", raised.exception.diagnostics["operation"])
        self.assertEqual("provider_error", raised.exception.diagnostics["failure_kind"])
        self.assertEqual("phone_otp", flow.stage.call_args.args[0])
        flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)
        flow.report_activation_failure.assert_not_called()

    def test_cancelled_after_acquisition_cleans_order_once(self):
        flow = self._phone_flow(responses=oauth.OperationCancelled("cancelled"))
        with self.assertRaises(oauth.OperationCancelled):
            oauth._do_phone_verification(object())
        self.assertEqual(1, flow.acquire.call_count)
        flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)
        flow.http.close.assert_called_once_with()

    def test_provider_failure_before_acquisition_keeps_bounded_retries(self):
        flow = self._phone_flow(responses=[], acquire_error=oauth.sms_provider.SmsProviderError("private-provider-context"))
        with self.assertRaises(oauth.CodexPhoneVerificationError):
            oauth._do_phone_verification(object())
        self.assertEqual(3, flow.acquire.call_count)
        flow.cancel.assert_not_called()
        flow.post.assert_not_called()
        flow.http.close.assert_called_once_with()

    def test_no_balance_before_acquisition_does_not_repeat_purchase(self):
        flow = self._phone_flow(responses=[], acquire_error=oauth.sms_provider.SmsNoBalanceError("private-provider-context"))
        with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
            oauth._do_phone_verification(object())
        self.assertEqual(1, flow.acquire.call_count)
        self.assertEqual("provider_no_balance", raised.exception.diagnostics["failure_kind"])
        flow.cancel.assert_not_called()

    def test_price_limit_before_acquisition_keeps_specific_failure(self):
        flow = self._phone_flow(responses=[], acquire_error=oauth.sms_provider.SmsPriceLimitError("private-price-context"))
        with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
            oauth._do_phone_verification(object())
        self.assertEqual(1, flow.acquire.call_count)
        self.assertEqual("provider_price_limit", raised.exception.diagnostics["failure_kind"])
        self.assertNotIn("private-price-context", str(raised.exception))
        flow.cancel.assert_not_called()

    def test_no_numbers_retries_are_bounded_and_keep_specific_failure(self):
        flow = self._phone_flow(responses=[], acquire_error=oauth.sms_provider.SmsNoNumbersError("private-no-numbers-context"))
        with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
            oauth._do_phone_verification(object())
        self.assertEqual(3, flow.acquire.call_count)
        self.assertEqual("provider_no_numbers", raised.exception.diagnostics["failure_kind"])
        self.assertNotIn("private-no-numbers-context", str(raised.exception))
        flow.cancel.assert_not_called()

    def test_explicit_number_rejections_remain_bounded_and_keep_last_response(self):
        flow = self._phone_flow(responses=[_response(400, {"error": {"code": "invalid_phone_number"}})] * 3)
        with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
            oauth._do_phone_verification(object())
        self.assertEqual(3, flow.acquire.call_count)
        self.assertEqual(3, flow.cancel.call_count)
        self.assertEqual(400, raised.exception.http_status)
        self.assertEqual("invalid_phone_number", raised.exception.diagnostics["server_code"])
        self.assertEqual(3, raised.exception.diagnostics["attempt"])

    def test_explicit_rejection_remains_primary_when_budget_expires(self):
        """次数耗尽或下一轮预算耗尽均不能覆盖已收到的号码拒绝回执。"""
        for max_attempts in (1, 3):
            with self.subTest(max_attempts=max_attempts):
                flow = self._phone_flow(responses=[_response(400, {"error": {"code": "invalid_phone_number"}})])
                with patch.object(oauth._cfg, "SMS_MAX_RETRIES", max_attempts), patch.object(
                    oauth.time, "monotonic", side_effect=[0, 0, 301]
                ):
                    with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
                        oauth._do_phone_verification(object())
                self.assertEqual("invalid_phone", raised.exception.diagnostics["failure_kind"])
                self.assertEqual(400, raised.exception.http_status)
                self.assertEqual("invalid_phone_number", raised.exception.diagnostics["server_code"])
                self.assertTrue(raised.exception.as_result()["remote_write_rejected"])
                self.assertEqual("phone_otp", flow.stage.call_args.args[0])
                self.assertEqual(1, flow.acquire.call_count)
                flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)

    def test_no_numbers_after_rejected_number_reports_acquire_stage(self):
        """历史拿过号码不应让当前取号失败误报为短信验证失败。"""
        flow = self._phone_flow(responses=[_response(400, {"error": {"code": "invalid_phone_number"}})])
        flow.acquire.side_effect = [
            ("synthetic-activation", "synthetic-number"),
            oauth.sms_provider.SmsNoNumbersError("private-no-numbers-context"),
            oauth.sms_provider.SmsNoNumbersError("private-no-numbers-context"),
        ]
        with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
            oauth._do_phone_verification(object())
        self.assertEqual("provider_no_numbers", raised.exception.diagnostics["failure_kind"])
        self.assertEqual("phone_acquire", flow.stage.call_args.args[0])
        self.assertEqual("failed", flow.stage.call_args.kwargs["state"])
        self.assertEqual(3, flow.acquire.call_count)
        flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)

    def test_budget_exhaustion_after_acquisition_does_not_start_sms_wait(self):
        flow = self._phone_flow(responses=[_response(200)])
        with patch.object(oauth.time, "monotonic", side_effect=[0, 0, 301]):
            with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
                oauth._do_phone_verification(object())
        self.assertEqual(1, flow.acquire.call_count)
        self.assertEqual("budget_exhausted", raised.exception.diagnostics["failure_kind"])
        flow.cancel.assert_called_once_with("synthetic-activation", flow.http, background=True)
        flow.wait.assert_not_called()

    def test_success_keeps_payload_and_external_call_order(self):
        flow = self._phone_flow(responses=[_response(200), _response(200, {"next": "workspace"})])
        calls = Mock()
        for name, target in (("acquire", flow.acquire), ("post", flow.post), ("set_status", flow.set_status), ("wait", flow.wait), ("complete", flow.complete)):
            calls.attach_mock(target, name)
        session = object()
        self.assertEqual({"next": "workspace"}, oauth._do_phone_verification(session))
        self.assertEqual(["acquire", "post", "set_status", "wait", "post", "complete"], [call[0] for call in calls.mock_calls])
        self.assertEqual({"phone_number": "+synthetic-number", "channel": "sms"}, flow.post.call_args_list[0].args[2])
        self.assertEqual({"code": "synthetic-sms-code"}, flow.post.call_args_list[1].args[2])
        flow.cancel.assert_not_called()

    def test_failure_diagnostics_do_not_expose_acquired_resource_or_code(self):
        flow = self._phone_flow(responses=[
            _response(200),
            _response(409, {"error": {"message": "synthetic-number synthetic-activation synthetic-sms-code"}}),
        ] * 3)
        with self.assertRaises(oauth.CodexPhoneVerificationError) as raised:
            oauth._do_phone_verification(object())
        serialized = json.dumps({"result": raised.exception.as_result(), "events": [str(item) for item in flow.stage.call_args_list]})
        for sensitive in ("synthetic-number", "synthetic-activation", "synthetic-sms-code"):
            self.assertNotIn(sensitive, serialized)

    def test_protocol_entry_preserves_phone_failure_result_without_callback(self):
        error = oauth.CodexPhoneVerificationError(
            operation="phone_send", failure_kind="session_conflict", http_status=409,
            attempt=1, max_attempts=3, server_code="invalid_state", response_received=True,
        )
        with ExitStack() as stack:
            for name in ("BrowserSession", "network_preflight", "_bootstrap_authorize", "human_delay", "report_stage", "check_cancelled"):
                stack.enter_context(patch.object(oauth, name))
            stack.enter_context(patch.object(oauth, "_codex_auth_url_source", return_value="local"))
            stack.enter_context(patch.object(oauth, "_generate_pkce", return_value=("verifier", "challenge")))
            stack.enter_context(patch.object(oauth, "_generate_state", return_value="state"))
            stack.enter_context(patch.object(oauth, "_submit_email", return_value=("phone", "/add-phone", 0)))
            stack.enter_context(patch.object(oauth, "_do_phone_verification", side_effect=error))
            exchange = stack.enter_context(patch.object(oauth, "exchange_codex_token"))
            save = stack.enter_context(patch.object(oauth, "save_codex_credential"))
            result = oauth.run_codex_oauth(
                "synthetic-account@example.test", otp_provider=Mock(), proxy="", force=True,
                driver_override="protocol", phone_enabled=True,
            )
        self.assertEqual("failed", result["status"])
        self.assertEqual("codex_phone_verification_failed", result["cause_code"])
        self.assertEqual(409, result["http_status"])
        self.assertEqual("phone_send", result["auth_diagnostics"]["operation"])
        self.assertEqual("invalid_state", result["auth_diagnostics"]["server_code"])
        self.assertTrue(result["remote_write_rejected"])
        self.assertFalse(result["callback_submitted"])
        self.assertFalse(result["credential_confirmed"])
        self.assertNotIn("reconcile_required", result)
        exchange.assert_not_called()
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
