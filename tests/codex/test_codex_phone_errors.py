"""手机错误保留真实说明，不改变原有有界换号策略。"""
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

    def test_unknown_conflict_keeps_server_reason_and_original_retry_policy(self):
        failure = self.failure(409, {"error": {"code": "phone_state_conflict", "message": "Verification state conflicts"}})
        self.assertTrue(failure.number_retry_allowed)
        self.assertEqual(failure.diagnostics["server_code"], "phone_state_conflict")
        self.assertIn("Verification state conflicts", str(failure))
        result = failure.as_result()
        self.assertEqual(result["cause_code"], "codex_phone_verification_failed")
        self.assertTrue(result["remote_write_rejected"])
        self.assertEqual(result["http_status"], 409)

    def test_failed_send_responses_keep_original_rotation_regardless_of_reason(self):
        cases = [
            (400, "invalid_phone_number", "Invalid phone number", True),
            (409, "phone_number_already_used", "This phone number is already used", True),
            (400, "fraud_guard", "We've detected suspicious behavior from phone numbers similar to yours.", True),
            (409, "invalid_state", "Your sign-in session is no longer valid.", True),
            (409, "account_limit", "Maximum verification attempts exceeded", True),
            (409, "", "Cannot send an SMS", True),
            (429, "invalid_phone_number", "Invalid phone number", True),
            (500, "invalid_phone_number", "Invalid phone number", True),
            (400, "phone_send_failed", "This phone number has been used too many times", True),
            (429, "phone_number_usage_limit_exceeded", "Too many SMS sent to this phone number", True),
            (400, "", "This number only supports WhatsApp", True),
        ]
        for status, code, message, allowed in cases:
            with self.subTest(status=status, code=code):
                failure = self.failure(status, {"error": {"code": code, "message": message}})
                self.assertEqual(failure.number_retry_allowed, allowed)

    def test_fraud_guard_classification_does_not_require_english_phone_words(self):
        failure = self.failure(400, {"error": {"code": "fraud_guard", "message": "Suspicious activity detected"}})
        self.assertTrue(failure.number_retry_allowed)
        self.assertEqual(failure.diagnostics["failure_kind"], "number_risk")

    def test_code_validation_rejections_keep_original_rotation(self):
        for code in ("invalid_otp", "otp_expired", "invalid_phone_number", "invalid_state"):
            with self.subTest(code=code):
                failure = self.failure(409, {"error": {"code": code}}, operation="phone_validate")
                self.assertTrue(failure.number_retry_allowed)
                self.assertEqual(failure.diagnostics["operation"], "phone_validate")

    def test_retry_does_not_relabel_session_or_unknown_errors_as_bad_numbers(self):
        for status, code, message, kind in (
            (409, "invalid_state", "Your sign-in session is no longer valid.", "session_conflict"),
            (409, "phone_state_conflict", "Verification state conflicts", "send_rejected"),
            (429, "too_many_requests", "Too many requests", "send_limited"),
        ):
            with self.subTest(code=code):
                failure = self.failure(status, {"error": {"code": code, "message": message}})
                self.assertTrue(failure.number_retry_allowed)
                self.assertEqual(failure.diagnostics["failure_kind"], kind)
                self.assertEqual(failure.diagnostics["server_message"], message)

    def test_only_real_http_failures_authorize_rotation(self):
        for operation in ("phone_send", "phone_validate"):
            for status in (100, 199, 200, 204, 302, 400, 409, 429, 500, 599):
                with self.subTest(operation=operation, status=status):
                    failure = self.failure(status, {"error": {"code": "unknown_failure"}}, operation=operation)
                    self.assertTrue(failure.number_retry_allowed)
            for status in (0, 99, 600):
                with self.subTest(operation=operation, status=status):
                    failure = self.failure(status, {"error": {"code": "unknown_failure"}}, operation=operation)
                    self.assertFalse(failure.number_retry_allowed)

    def test_error_messages_are_preserved_across_languages_and_unknown_codes(self):
        cases = (
            ("fraud_guard", "已检测到与该号码相似号码的可疑行为。"),
            ("fraud_guard", "Không thể gửi mã xác minh đến số điện thoại này."),
            ("unknown_failure", "この電話番号に確認コードを送信できません。"),
            ("", "No se puede enviar un código a este número de teléfono."),
            ("", "号码发送次数已达上限，请使用其他号码。"),
        )
        for code, message in cases:
            with self.subTest(code=code, message=message):
                failure = self.failure(400, {"error": {"code": code, "message": message}})
                self.assertTrue(failure.number_retry_allowed)
                self.assertEqual(failure.diagnostics["server_message"], message)
                self.assertIn(message, str(failure))
                if code:
                    self.assertEqual(failure.diagnostics["server_code"], code)

    def test_success_payload_metadata_does_not_become_a_phone_error(self):
        for payload in ({}, {"continue_url": "/phone-verification", "metadata": "invalid phone number"}):
            self.assertIsNone(self.failure(200, payload))
        self.assertIsNone(self.failure(204, {}))
        self.assertTrue(self.failure(200, {"error": {"code": "invalid_state"}}).number_retry_allowed)

    def test_non_json_conflict_is_unknown_and_does_not_copy_html(self):
        self.assertIsNotNone(phone_errors, "手机错误判定尚未实现")
        response = SimpleNamespace(status_code=409, text="<html>private-page-content</html>")
        failure = phone_errors.phone_failure_from_response(response, operation="phone_send", attempt=1, max_attempts=10)
        self.assertTrue(failure.number_retry_allowed)
        self.assertNotIn("private-page-content", json.dumps(failure.as_result()))
        self.assertIn("409", str(failure))

    def test_server_failure_and_missing_response_do_not_claim_confirmed_rejection(self):
        self.assertFalse(self.failure(503, {"error": {"code": "server_error"}}).as_result()["remote_write_rejected"])
        self.assertIsNotNone(phone_errors, "手机错误判定尚未实现")
        failure = phone_errors.CodexPhoneVerificationError(
            operation="phone_send", failure_kind="transport_error", attempt=1, max_attempts=10,
        )
        self.assertFalse(failure.as_result()["remote_write_rejected"])
        self.assertFalse(failure.number_retry_allowed)

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
