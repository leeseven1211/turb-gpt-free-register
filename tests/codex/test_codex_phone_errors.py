"""手机验证响应决定是否允许再次购买号码。"""
import json
import unittest
from types import SimpleNamespace

from core.codex import phone_errors


class CodexPhoneErrorTests(unittest.TestCase):
    def failure(self, status, payload, *, operation="phone_send"):
        self.assertIsNotNone(phone_errors, "手机错误判定尚未实现")
        response = SimpleNamespace(status_code=status, text=json.dumps(payload), json=lambda: payload)
        return phone_errors.phone_failure_from_response(
            response, operation=operation, attempt=1, max_attempts=10,
            sensitive_values=("activation-private", "15550001234", "123456"),
        )

    def test_unknown_conflict_keeps_server_reason_without_authorizing_new_number(self):
        failure = self.failure(409, {"error": {"code": "phone_state_conflict", "message": "Verification state conflicts"}})
        self.assertFalse(failure.number_retry_allowed)
        self.assertEqual(failure.diagnostics["server_code"], "phone_state_conflict")
        self.assertIn("Verification state conflicts", str(failure))
        result = failure.as_result()
        self.assertEqual(result["cause_code"], "codex_phone_verification_failed")
        self.assertTrue(result["remote_write_rejected"])
        self.assertEqual(result["http_status"], 409)

    def test_only_explicit_number_errors_authorize_rotation(self):
        cases = [
            (400, "invalid_phone_number", "Invalid phone number", True),
            (409, "phone_number_already_used", "This phone number is already used", True),
            (409, "invalid_state", "Invalid phone number in this session", False),
            (409, "account_limit", "Maximum verification attempts exceeded", False),
            (409, "", "Cannot send an SMS", False),
            (429, "invalid_phone_number", "Invalid phone number", False),
            (500, "invalid_phone_number", "Invalid phone number", False),
        ]
        for status, code, message, allowed in cases:
            with self.subTest(status=status, code=code):
                failure = self.failure(status, {"error": {"code": code, "message": message}})
                self.assertEqual(failure.number_retry_allowed, allowed)

    def test_code_validation_never_authorizes_purchase_of_another_number(self):
        for code in ("invalid_otp", "otp_expired", "invalid_phone_number", "invalid_state"):
            with self.subTest(code=code):
                failure = self.failure(409, {"error": {"code": code}}, operation="phone_validate")
                self.assertFalse(failure.number_retry_allowed)
                self.assertEqual(failure.diagnostics["operation"], "phone_validate")

    def test_success_payload_metadata_does_not_become_a_phone_error(self):
        for payload in ({}, {"continue_url": "/phone-verification", "metadata": "invalid phone number"}):
            self.assertIsNone(self.failure(200, payload))
        self.assertIsNone(self.failure(204, {}))
        self.assertIsNotNone(self.failure(200, {"error": {"code": "invalid_state"}}))

    def test_non_json_conflict_is_unknown_and_does_not_copy_html(self):
        self.assertIsNotNone(phone_errors, "手机错误判定尚未实现")
        response = SimpleNamespace(status_code=409, text="<html>private-page-content</html>")
        failure = phone_errors.phone_failure_from_response(response, operation="phone_send", attempt=1, max_attempts=10)
        self.assertFalse(failure.number_retry_allowed)
        self.assertNotIn("private-page-content", json.dumps(failure.as_result()))
        self.assertIn("409", str(failure))

    def test_server_failure_and_missing_response_do_not_claim_confirmed_rejection(self):
        self.assertFalse(self.failure(503, {"error": {"code": "server_error"}}).as_result()["remote_write_rejected"])
        self.assertIsNotNone(phone_errors, "手机错误判定尚未实现")
        failure = phone_errors.CodexPhoneVerificationError(
            operation="phone_send", failure_kind="transport_error", attempt=1, max_attempts=10,
        )
        self.assertFalse(failure.as_result()["remote_write_rejected"])

    def test_diagnostics_keep_error_fields_and_remove_private_context(self):
        self.assertIsNotNone(phone_errors, "手机错误判定尚未实现")
        diagnostics = phone_errors.safe_phone_diagnostics({
            "operation": "phone_send", "failure_kind": "session_conflict", "http_status": 409,
            "attempt": 1, "max_attempts": 10, "number_retry_allowed": False, "response_received": True,
            "server_code": "invalid_state", "server_type": "invalid_request_error",
            "server_message": "Contact alice@example.test phone +15550001234 otp=123456 token=private-token",
            "response_body": "private-body", "access_token": "private-context",
        })
        self.assertEqual(diagnostics["server_code"], "invalid_state")
        serialized = json.dumps(diagnostics)
        for private in ("alice@example.test", "15550001234", "123456", "private-token", "private-body", "private-context"):
            self.assertNotIn(private, serialized)
        cause = phone_errors.phone_failure_cause(diagnostics)
        self.assertEqual(cause["cause_display_code"], "OA-PHONE-SEND-409")
        self.assertIn("invalid_state", cause["cause_summary"])
        self.assertEqual(phone_errors.safe_phone_diagnostics({"operation": "unknown", "failure_kind": "session_conflict"}), {})

    def test_malformed_diagnostic_values_do_not_break_task_projection(self):
        for operation, kind in (([], "send_rejected"), ("phone_send", {})):
            with self.subTest(operation=operation, failure_kind=kind):
                self.assertEqual(phone_errors.safe_phone_diagnostics({"operation": operation, "failure_kind": kind}), {})

    def test_resource_identifier_in_error_code_is_not_persisted(self):
        response = SimpleNamespace(
            status_code=409, text="",
            json=lambda: {"error": {"code": "PrivateActivation", "type": "PrivatePhone"}},
        )
        failure = phone_errors.phone_failure_from_response(
            response, operation="phone_send", attempt=1, max_attempts=10,
            sensitive_values=("PrivateActivation", "PrivatePhone"),
        )
        serialized = json.dumps(failure.as_result())
        self.assertNotIn("PrivateActivation", serialized)
        self.assertNotIn("PrivatePhone", serialized)
