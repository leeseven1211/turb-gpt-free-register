# -*- coding: utf-8 -*-
"""协议改密外围 helper 契约测试。"""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.accounts.password_setup.reset_support import (
    ProtocolPasswordResetError,
    classify_reset_mailbox_error,
    check_reset_mailbox,
    check_reset_response,
    generate_reset_password,
)


class PasswordResetPasswordGenerationTests(unittest.TestCase):
    def test_generates_independent_fourteen_character_password_with_all_classes(self):
        first = generate_reset_password()
        second = generate_reset_password()

        self.assertEqual(14, len(first))
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"[A-Z]")
        self.assertRegex(first, r"[a-z]")
        self.assertRegex(first, r"\d")
        self.assertRegex(first, r"[^A-Za-z0-9]")

    def test_never_reuses_the_old_password_or_fixed_register_password(self):
        with patch("config.register.REGISTER_PASSWORD", "FixedRegisterPassword!", create=True):
            password = generate_reset_password("FixedRegisterPassword!")

        self.assertNotEqual("FixedRegisterPassword!", password)


class PasswordResetResponseTests(unittest.TestCase):
    def test_accepts_json_object_on_success(self):
        response = _Response(200, {"continue_url": "/next"})

        self.assertEqual({"continue_url": "/next"}, check_reset_response(response, stage="validate_otp"))

    def test_allows_empty_reset_success_body(self):
        response = _Response(200, text="")

        self.assertEqual({}, check_reset_response(response, stage="reset"))

    def test_allows_empty_send_otp_success_body(self):
        response = _Response(200, text="")

        self.assertEqual({}, check_reset_response(response, stage="send_otp"))

    def test_requires_json_object_for_empty_validate_otp_success_body(self):
        response = _Response(200, text="")

        with self.assertRaises(ProtocolPasswordResetError) as raised:
            check_reset_response(response, stage="validate_otp")

        self.assertEqual("password_reset_response_invalid", raised.exception.code)

    def test_rejects_malformed_success_body_without_leaking_body(self):
        response = _Response(200, text="otp=123456 password=private-secret")

        with self.assertRaises(ProtocolPasswordResetError) as raised:
            check_reset_response(response, stage="validate_otp")

        self.assertEqual("password_reset_response_invalid", raised.exception.code)
        self.assertEqual("validate_otp", raised.exception.stage)
        self.assertNotIn("123456", str(raised.exception))
        self.assertNotIn("private-secret", str(raised.exception))

    def test_extracts_remote_cooldown_code_and_marks_rate_limit_retryable(self):
        response = _Response(429, {"error": {"code": "sensitive_action_cooldown"}})

        with self.assertRaises(ProtocolPasswordResetError) as raised:
            check_reset_response(response, stage="password_reset")

        self.assertEqual("password_reset_cooldown", raised.exception.code)
        self.assertEqual("sensitive_action_cooldown", raised.exception.cause_code)
        self.assertTrue(raised.exception.retryable)
        self.assertFalse(raised.exception.request_unknown)

    def test_final_reset_cooldown_is_explicit_and_keeps_remote_unlock_fields(self):
        response = _Response(429, {
            "error": {
                "code": "sensitive_action_cooldown",
                "cooldownAction": "wait",
                "unlockAt": "2026-11-27T12:00:00Z",
                "retryAfter": 120,
                "private_token": "must-not-copy",
            },
        })

        with self.assertRaises(ProtocolPasswordResetError) as raised:
            check_reset_response(response, stage="reset", result_unknown=True)

        self.assertEqual("password_reset_cooldown", raised.exception.code)
        self.assertFalse(raised.exception.request_unknown)
        self.assertEqual("wait", raised.exception.detail["cooldownAction"])
        self.assertEqual("2026-11-27T12:00:00Z", raised.exception.detail["unlockAt"])
        self.assertEqual(120, raised.exception.detail["retryAfter"])
        self.assertNotIn("private_token", raised.exception.detail)

    def test_classifies_rate_limit_even_when_error_body_is_not_json(self):
        response = _Response(429, text="gateway unavailable")

        with self.assertRaises(ProtocolPasswordResetError) as raised:
            check_reset_response(response, stage="send_otp")

        self.assertEqual("password_reset_rate_limited", raised.exception.code)
        self.assertEqual("http_429", raised.exception.cause_code)
        self.assertTrue(raised.exception.retryable)

    def test_distinguishes_otp_rejection_from_password_reset_rejection(self):
        otp = _Response(401, {"error": {"code": "invalid_otp"}})
        reset = _Response(403, {"error": {"code": "password_not_allowed"}})

        with self.assertRaises(ProtocolPasswordResetError) as otp_error:
            check_reset_response(otp, stage="validate_otp")
        with self.assertRaises(ProtocolPasswordResetError) as reset_error:
            check_reset_response(reset, stage="reset")

        self.assertEqual("password_reset_otp_rejected", otp_error.exception.code)
        self.assertEqual("invalid_otp", otp_error.exception.cause_code)
        self.assertEqual("password_reset_rejected", reset_error.exception.code)
        self.assertEqual("password_not_allowed", reset_error.exception.cause_code)

    def test_marks_final_server_failure_unknown_without_using_unknown_as_cause(self):
        response = _Response(502, {"error": {"code": "upstream_unavailable"}})

        with self.assertRaises(ProtocolPasswordResetError) as raised:
            check_reset_response(response, stage="reset", result_unknown=True)

        self.assertEqual("password_reset_request_unknown", raised.exception.code)
        self.assertEqual("upstream_unavailable", raised.exception.cause_code)
        self.assertTrue(raised.exception.retryable)
        self.assertTrue(raised.exception.request_unknown)
        self.assertNotEqual("request_unknown", raised.exception.cause_code)


class PasswordResetMailboxTests(unittest.TestCase):
    def test_classifies_no_mail_as_retryable_otp_timeout(self):
        from core.email.generic_api.client import GenericApiMailError

        raised = classify_reset_mailbox_error(
            GenericApiMailError("无新邮件", error_code="email_otp_no_mail"),
        )

        self.assertEqual("password_reset_otp_timeout", raised.code)
        self.assertEqual("email_otp_no_mail", raised.cause_code)
        self.assertEqual("wait_otp", raised.stage)
        self.assertTrue(raised.retryable)

    def test_classifies_gptmail_timeout_exception_as_retryable_otp_timeout(self):
        from core.email.gptmail.client import GPTMailError

        raised = classify_reset_mailbox_error(
            GPTMailError("等待 GPTMail 验证码超时: unit@example.test"),
        )

        self.assertEqual("password_reset_otp_timeout", raised.code)
        self.assertTrue(raised.retryable)

    def test_classifies_cloudflare_timeout_exception_as_retryable_otp_timeout(self):
        from core.email.cloudflare.client import CFTempMailError

        raised = classify_reset_mailbox_error(
            CFTempMailError("等待 Cloudflare 验证码超时: unit@example.test"),
        )

        self.assertEqual("password_reset_otp_timeout", raised.code)
        self.assertTrue(raised.retryable)

    def test_classifies_outlook_timeout_exception_as_retryable_otp_timeout(self):
        from core.email.outlook.client import OutlookClientError

        raised = classify_reset_mailbox_error(
            OutlookClientError("等待 unit@example.test 的 OTP 超时（>180s）。"),
        )

        self.assertEqual("password_reset_otp_timeout", raised.code)
        self.assertTrue(raised.retryable)

    def test_classifies_rate_limit_server_parse_and_auth_without_raw_details(self):
        cases = [
            (SimpleNamespace(error_code="butler_http_429", status_code=429), "password_reset_rate_limited", True),
            (SimpleNamespace(error_code="butler_transport_failed", status_code=503), "password_reset_otp_mailbox_unavailable", True),
            (SimpleNamespace(error_code="butler_response_not_json", status_code=200), "password_reset_otp_parse_failed", True),
            (SimpleNamespace(error_code="source_authentication_failed", status_code=401), "password_reset_otp_auth_failed", False),
        ]
        for original, expected_code, retryable in cases:
            with self.subTest(expected_code=expected_code):
                raised = classify_reset_mailbox_error(original, stage="wait_otp")
                self.assertEqual(expected_code, raised.code)
                self.assertEqual(original.error_code, raised.cause_code)
                self.assertEqual(retryable, raised.retryable)
                self.assertNotIn("butler-secret", str(raised))

    def test_preserves_expired_resource_classification(self):
        from core.email.generic_api.client import GenericApiMailError

        raised = classify_reset_mailbox_error(
            GenericApiMailError("过期", error_code="email_resource_expired"),
            stage="mailbox",
        )

        self.assertEqual("email_resource_expired", raised.code)
        self.assertFalse(raised.retryable)
        self.assertEqual("mailbox", raised.stage)

    def test_generic_api_context_is_checked_without_claiming_or_networking(self):
        account = SimpleNamespace(email="unit@example.test", expires_at=None, expires_at_epoch=None)
        with (
            patch("core.email.provider.resolve_email_source", return_value="generic_api"),
            patch("core.email.generic_api.client.get_account_context", return_value=account) as get_context,
            patch("core.email.resource_lifetime.require_usable") as require_usable,
            patch("core.email.email_butler.client.get_account_context", side_effect=AssertionError("不应检查 Butler")),
        ):
            self.assertIsNone(check_reset_mailbox("unit@example.test"))

        get_context.assert_called_once_with("unit@example.test")
        require_usable.assert_called_once_with(account)

    def test_expired_generic_api_context_is_a_known_non_retryable_mailbox_error(self):
        from core.email.generic_api.client import GenericApiMailError

        error = GenericApiMailError("expired", error_code="email_resource_expired")
        with (
            patch("core.email.provider.resolve_email_source", return_value="generic_api"),
            patch("core.email.generic_api.client.get_account_context", side_effect=error),
        ):
            with self.assertRaises(ProtocolPasswordResetError) as raised:
                check_reset_mailbox("unit@example.test")

        self.assertEqual("email_resource_expired", raised.exception.code)
        self.assertFalse(raised.exception.retryable)

    def test_butler_context_requires_original_identity_and_accepts_future_lease(self):
        account = SimpleNamespace(
            email="unit@example.test",
            acquisition_id="original-acquisition",
            lease_id="lse_original",
            leased_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        )
        with (
            patch("core.email.provider.resolve_email_source", return_value="email_butler"),
            patch("core.email.generic_api.client.get_account_context", return_value=None),
            patch("core.email.email_butler.client.get_account_context", return_value=account),
        ):
            self.assertIsNone(check_reset_mailbox("unit@example.test"))

    def test_missing_butler_identity_is_rejected_without_new_lease(self):
        account = SimpleNamespace(email="unit@example.test", acquisition_id="", lease_id="")
        with (
            patch("core.email.provider.resolve_email_source", return_value="email_butler"),
            patch("core.email.generic_api.client.get_account_context", return_value=None),
            patch("core.email.email_butler.client.get_account_context", return_value=account),
            patch("core.email.email_butler.client.restore_account_context") as restore,
        ):
            with self.assertRaises(ProtocolPasswordResetError) as raised:
                check_reset_mailbox("unit@example.test")

        self.assertEqual("email_identity_missing", raised.exception.code)
        restore.assert_not_called()

    def test_other_original_mailbox_source_is_left_to_its_provider(self):
        with (
            patch("core.email.provider.resolve_email_source", return_value="outlook") as resolve,
            patch("core.email.generic_api.client.get_account_context") as generic,
            patch("core.email.email_butler.client.get_account_context") as butler,
            patch("core.email.email_butler.client.restore_account_context") as restore,
        ):
            self.assertIsNone(check_reset_mailbox("unit@example.test"))

        resolve.assert_called_once_with("unit@example.test", fallback=False)
        generic.assert_not_called()
        butler.assert_not_called()
        restore.assert_not_called()

    def test_unknown_original_mailbox_source_is_left_to_existing_provider(self):
        with patch("core.email.provider.resolve_email_source", return_value=None) as resolve:
            self.assertIsNone(check_reset_mailbox("unit@example.test"))

        resolve.assert_called_once_with("unit@example.test", fallback=False)


class _Response:
    def __init__(self, status_code, payload=None, *, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if self._payload is RuntimeError:
            raise ValueError("invalid json")
        if self._payload is None:
            raise ValueError("empty")
        return self._payload
