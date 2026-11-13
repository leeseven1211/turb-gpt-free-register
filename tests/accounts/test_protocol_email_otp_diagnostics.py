# -*- coding: utf-8 -*-
"""邮箱 OTP 诊断保留真实根因，同时维持既有认证和重试行为。"""

import json
import unittest
from unittest.mock import MagicMock, call, patch

import requests
from curl_cffi.requests import exceptions as curl_exceptions

from core.email.email_butler.client import EmailButlerClientError


EMAIL = "otp-fixture@example.test"
AUTH = "https://auth.openai.com"
PRIVATE_DETAIL = "fixture-private-value https://fixture.invalid/private?token=fixture-secret"


class OtpFailureDiagnosticsTests(unittest.TestCase):
    def diagnostics(self, error, **kwargs):
        from core.accounts.liveness.protocol.otp_diagnostics import otp_failure_diagnostics

        return otp_failure_diagnostics(error, **kwargs)

    def assert_private_values_absent(self, diagnostics):
        encoded = json.dumps(diagnostics)
        for value in (EMAIL, PRIVATE_DETAIL, "fixture-secret", "fixture.invalid"):
            self.assertNotIn(value, encoded)

    def test_butler_no_mail_keeps_its_code_without_inventing_http_status(self):
        for status in (None, 408):
            with self.subTest(status=status):
                error = EmailButlerClientError(
                    PRIVATE_DETAIL, error_code="inbound_code_timeout", status_code=status,
                )
                diagnostics = self.diagnostics(error)
                self.assertEqual("email_otp", diagnostics["operation"])
                self.assertEqual("no_mail", diagnostics["failure_kind"])
                self.assertEqual("EmailButlerClientError", diagnostics["exception_type"])
                self.assertEqual("inbound_code_timeout", diagnostics["mailbox_error_code"])
                self.assertEqual(status, diagnostics.get("http_status"))
                self.assert_private_values_absent(diagnostics)

    def test_butler_source_and_recipient_rejections_keep_the_specific_cause(self):
        for code in ("source_authentication_failed", "recipient_mismatch", "mailbox_mismatch"):
            with self.subTest(code=code):
                diagnostics = self.diagnostics(EmailButlerClientError(
                    PRIVATE_DETAIL, error_code=code, status_code=408,
                ))
                self.assertEqual("mailbox_error", diagnostics["failure_kind"])
                self.assertEqual(code, diagnostics["mailbox_error_code"])
                self.assertEqual(408, diagnostics["http_status"])
                self.assert_private_values_absent(diagnostics)

    def test_butler_http_failure_is_not_reported_as_no_mail(self):
        diagnostics = self.diagnostics(EmailButlerClientError(
            PRIVATE_DETAIL, error_code="inbound_code_timeout", status_code=503,
        ))
        self.assertNotEqual("no_mail", diagnostics["failure_kind"])
        self.assertEqual(503, diagnostics["http_status"])
        self.assert_private_values_absent(diagnostics)

    def test_v2_mailbox_causes_survive_protocol_and_service_projection(self):
        from core.accounts.liveness.service import _safe_refresh_auth_diagnostics
        from core.operations.errors import classify_task_error

        for code, kind, display in (
            ("butler_transport_timeout", "transport_error", "MAIL-BUTLER-V2-TIMEOUT"),
            ("butler_transport_connection", "transport_error", "MAIL-BUTLER-V2-CONNECT"),
            ("butler_transport_failed", "transport_error", "MAIL-BUTLER-V2-NETWORK"),
            ("lease_expired", "mailbox_error", "MAIL-BUTLER-V2-EXPIRED"),
            ("invalid_api_key", "mailbox_error", "MAIL-BUTLER-V2-AUTH"),
            ("provider_unavailable", "mailbox_error", "MAIL-BUTLER-V2-PROVIDER"),
            ("butler_code_response_invalid", "mailbox_error", "MAIL-BUTLER-V2-CODE"),
            ("butler_http_524", "mailbox_error", "MAIL-OTP-HTTP-524"),
        ):
            with self.subTest(code=code):
                diagnostics = self.diagnostics(EmailButlerClientError(PRIVATE_DETAIL, error_code=code))
                safe = _safe_refresh_auth_diagnostics(diagnostics)
                self.assertEqual(code, safe["mailbox_error_code"])
                self.assertEqual(kind, safe["failure_kind"])
                info = classify_task_error("email_otp_failed", task_type="token_refresh",
                    result_summary={"cause_code": "email_otp_failed", "auth_diagnostics": safe})
                self.assertEqual(display, info["display_code"])
                self.assert_private_values_absent(safe)

    def test_unknown_butler_code_cannot_become_persisted_private_data(self):
        diagnostics = self.diagnostics(EmailButlerClientError(
            PRIVATE_DETAIL, error_code=EMAIL + " " + PRIVATE_DETAIL,
        ))
        self.assertEqual("unknown", diagnostics["mailbox_error_code"])
        self.assertEqual("mailbox_error", diagnostics["failure_kind"])
        self.assert_private_values_absent(diagnostics)

    def test_wrapped_mailbox_transport_keeps_the_underlying_exception_type(self):
        cause = requests.ConnectionError(PRIVATE_DETAIL)
        error = EmailButlerClientError(PRIVATE_DETAIL)
        error.__cause__ = cause
        diagnostics = self.diagnostics(error)
        self.assertEqual("EmailButlerClientError", diagnostics["exception_type"])
        self.assertEqual("ConnectionError", diagnostics["transport_exception_type"])
        self.assert_private_values_absent(diagnostics)

    def test_known_curl_transport_retains_numeric_code_and_action(self):
        error = curl_exceptions.ConnectionError(PRIVATE_DETAIL, code=56)
        diagnostics = self.diagnostics(error, operation="email_otp_send")
        self.assertEqual("email_otp_send", diagnostics["operation"])
        self.assertEqual("transport_error", diagnostics["failure_kind"])
        self.assertEqual(56, diagnostics["curl_error_code"])
        self.assert_private_values_absent(diagnostics)

    def test_runtime_error_message_cannot_claim_a_transport_failure(self):
        diagnostics = self.diagnostics(RuntimeError("timeout connection " + PRIVATE_DETAIL))
        self.assertEqual("otp_error", diagnostics["failure_kind"])
        self.assertNotIn("transport_exception_type", diagnostics)
        self.assertNotIn("curl_error_code", diagnostics)
        self.assert_private_values_absent(diagnostics)

    def test_resend_response_evidence_takes_priority_over_previous_network_context(self):
        from core.auth.protocol.openai_auth import EmailOtpSendError
        from core.operations.errors import classify_task_error

        for reason, status, display in (
            ("http_error", 503, "OA-OTP-SEND-503"),
            ("rejected", 200, "MAIL-SEND-002"),
            ("unconfirmed", 200, "MAIL-SEND-003"),
        ):
            with self.subTest(reason=reason):
                error = EmailOtpSendError(reason, status)
                error.__context__ = requests.ConnectionError(PRIVATE_DETAIL)
                diagnostics = self.diagnostics(error, operation="email_otp_send")
                self.assertEqual(reason, diagnostics["failure_kind"])
                info = classify_task_error("email_otp_failed", task_type="token_refresh",
                    result_summary={"cause_code": "email_otp_failed", "auth_diagnostics": diagnostics})
                self.assertEqual(display, info["display_code"])

    def test_validation_http_response_is_not_overridden_by_old_network_context(self):
        from core.operations.errors import classify_task_error

        response = requests.Response()
        response.status_code = 503
        error = requests.HTTPError(PRIVATE_DETAIL, response=response)
        error.__context__ = requests.ConnectionError(PRIVATE_DETAIL)
        diagnostics = self.diagnostics(error, operation="email_otp_validate")
        self.assertEqual("http_error", diagnostics["failure_kind"])
        self.assertEqual(503, diagnostics["http_status"])
        info = classify_task_error("email_otp_failed", task_type="token_refresh",
            result_summary={"cause_code": "email_otp_failed", "auth_diagnostics": diagnostics})
        self.assertEqual("OA-OTP-VALIDATE-503", info["display_code"])

    def test_service_retains_safe_mailbox_and_fallback_diagnostics_for_presentation(self):
        from core.accounts.liveness.service import _safe_refresh_auth_diagnostics
        from core.operations.errors import classify_task_error

        for operation, code in (("email_otp", "email_otp_failed"),
                                ("password_email_fallback", "password_rejected_email_fallback_failed")):
            with self.subTest(operation=operation):
                diagnostics = {"operation": operation, "failure_kind": "mailbox_error",
                    "mailbox_error_code": "source_authentication_failed", "exception_type": "EmailButlerClientError"}
                if operation == "password_email_fallback":
                    diagnostics.update(cause_code="email_otp_failed", cause_operation="email_otp",
                                       cause_failure_kind="mailbox_error", failure_kind="fallback_failed")
                diagnostics["private_message"] = PRIVATE_DETAIL
                safe = _safe_refresh_auth_diagnostics(diagnostics)
                self.assertEqual("source_authentication_failed", safe["mailbox_error_code"])
                self.assert_private_values_absent(safe)
                info = classify_task_error(code, task_type="token_refresh", task_status="attention_required",
                    result_summary={"cause_code": code, "auth_diagnostics": safe, "outcome": "request_unknown"})
                self.assertEqual("MAIL-SOURCE-002", info["display_code"])
                self.assertTrue(info["reconcile_required"])

        safe = _safe_refresh_auth_diagnostics({"operation": "email_otp_send", "failure_kind": "transport_error",
            "exception_type": "EmailButlerClientError", "transport_exception_type": "ConnectionError", "curl_error_code": 7,
            "mailbox_error_code": PRIVATE_DETAIL})
        self.assertEqual("ConnectionError", safe["transport_exception_type"])
        self.assertEqual(7, safe["curl_error_code"])
        self.assertNotIn("mailbox_error_code", safe)
        self.assert_private_values_absent(safe)

    def test_marking_keeps_the_original_exception_and_message(self):
        from core.accounts.liveness.protocol.otp_diagnostics import mark_otp_failure

        error = requests.ConnectionError(PRIVATE_DETAIL)
        original_message = str(error)
        mark_otp_failure(error, "email_otp_send")
        self.assertIs(type(error), requests.ConnectionError)
        self.assertEqual(original_message, str(error))
        self.assertEqual("email_otp_send", error._otp_operation)
        self.assertEqual("email_otp_send", self.diagnostics(error)["operation"])


class LegacyOtpDiagnosticBehaviorTests(unittest.TestCase):
    def setUp(self):
        from core.accounts.liveness.protocol import legacy

        self.legacy = legacy
        self.session = object()

    def test_three_no_mail_waits_keep_retry_count_order_and_time_anchors(self):
        failures = [EmailButlerClientError(
            "inbound_code_timeout: 等待验证码超时", error_code="inbound_code_timeout",
        ) for _ in range(3)]
        trace = []

        def wait(*_args, **_kwargs):
            trace.append("wait")
            raise failures[trace.count("wait") - 1]

        def resend(_session):
            trace.append("send")

        clock = MagicMock()
        clock.time.side_effect = [201.0, 302.0]
        with (
            patch.object(self.legacy, "wait_for_otp", side_effect=wait) as waiter,
            patch.object(self.legacy, "validate_email_otp") as validate,
            patch.object(self.legacy, "send_email_otp", side_effect=resend) as sender,
            patch.object(self.legacy, "time", clock),
            self.assertRaises(EmailButlerClientError) as caught,
        ):
            self.legacy._validate_with_retry(self.session, EMAIL, 100.0)

        self.assertIs(failures[-1], caught.exception)
        self.assertEqual("email_otp", caught.exception._otp_operation)
        self.assertEqual(["wait", "send", "wait", "send", "wait"], trace)
        self.assertEqual([100.0, 201.0, 302.0], [item.kwargs["after_ts"] for item in waiter.call_args_list])
        self.assertEqual([call(self.session), call(self.session)], sender.call_args_list)
        self.assertEqual([call(1), call(1)], clock.sleep.call_args_list)
        validate.assert_not_called()

    def test_source_rejection_keeps_the_existing_no_retry_decision(self):
        error = EmailButlerClientError(
            "等待验证码失败", error_code="source_authentication_failed",
        )
        original_message = str(error)
        with (
            patch.object(self.legacy, "wait_for_otp", side_effect=error) as waiter,
            patch.object(self.legacy, "validate_email_otp") as validate,
            patch.object(self.legacy, "send_email_otp") as sender,
            patch.object(self.legacy.time, "sleep") as sleep,
            self.assertRaises(EmailButlerClientError) as caught,
        ):
            self.legacy._validate_with_retry(self.session, EMAIL, 100.0)

        self.assertIs(error, caught.exception)
        self.assertEqual(original_message, str(caught.exception))
        self.assertEqual("email_otp", caught.exception._otp_operation)
        waiter.assert_called_once()
        validate.assert_not_called()
        sender.assert_not_called()
        sleep.assert_not_called()

    def test_resend_failure_keeps_original_identity_after_both_retry_triggers(self):
        from core.auth.protocol.openai_auth import EmailOtpInvalidError

        for trigger in ("no_mail", "invalid_code"):
            with self.subTest(trigger=trigger):
                error = requests.ConnectionError("connection closed " + PRIVATE_DETAIL)
                original_message = str(error)
                wait_error = EmailButlerClientError(
                    "inbound_code_timeout", error_code="inbound_code_timeout",
                ) if trigger == "no_mail" else None
                with (
                    patch.object(self.legacy, "wait_for_otp", return_value="654321", side_effect=wait_error) as waiter,
                    patch.object(self.legacy, "validate_email_otp", side_effect=EmailOtpInvalidError("验证码无效")) as validate,
                    patch.object(self.legacy, "send_email_otp", side_effect=error) as sender,
                    patch.object(self.legacy.time, "sleep") as sleep,
                    self.assertRaises(requests.ConnectionError) as caught,
                ):
                    self.legacy._validate_with_retry(self.session, EMAIL, 100.0)

                self.assertIs(error, caught.exception)
                self.assertEqual(original_message, str(caught.exception))
                self.assertEqual("email_otp_send", caught.exception._otp_operation)
                waiter.assert_called_once()
                self.assertEqual(trigger == "invalid_code", validate.called)
                sender.assert_called_once_with(self.session)
                sleep.assert_not_called()

    def test_validate_connection_failure_is_not_mislabeled_as_mailbox_wait(self):
        error = requests.ConnectionError("connection closed " + PRIVATE_DETAIL)
        with (
            patch.object(self.legacy, "wait_for_otp", return_value="654321") as waiter,
            patch.object(self.legacy, "validate_email_otp", side_effect=error) as validate,
            patch.object(self.legacy, "send_email_otp") as sender,
            self.assertRaises(requests.ConnectionError) as caught,
        ):
            self.legacy._validate_with_retry(self.session, EMAIL, 100.0, max_otp_attempts=1)

        self.assertIs(error, caught.exception)
        self.assertEqual("email_otp_validate", caught.exception._otp_operation)
        waiter.assert_called_once()
        validate.assert_called_once_with(self.session, "654321", sentinel_header=None, so_header=None)
        sender.assert_not_called()


class AtOtpRetryBehaviorTests(unittest.TestCase):
    """独立 AT 最多等待两轮，取码超时和网络换线各自保留分类。"""

    def setUp(self):
        from core.accounts.liveness.protocol import legacy
        from core.network.at_transport_recovery import AtRecoveryScope

        self.legacy = legacy
        self.scope = AtRecoveryScope()
        self.session = object()

    def no_mail(self, *, status=None):
        return EmailButlerClientError(
            "inbound_code_timeout: 等待验证码超时",
            error_code="inbound_code_timeout", status_code=status,
        )

    def test_first_no_mail_resends_in_same_session_then_uses_new_time_window(self):
        from core.network.at_transport_recovery import network_failure

        for status in (None, 408):
            with self.subTest(status=status):
                error = self.no_mail(status=status)
                trace = []
                clock = {"now": 100.0}
                result = {"continue_url": AUTH + "/authorize/continue"}

                def wait(*_args, **_kwargs):
                    trace.append("wait")
                    if trace.count("wait") == 1:
                        clock["now"] = 200.0
                        raise error
                    # 重发返回前已投递的邮件仍属于本次挑战窗口。
                    self.assertLessEqual(_kwargs["after_ts"], 200.5)
                    return "654321"

                def resend(session):
                    self.assertIs(self.session, session)
                    trace.append("send")
                    clock["now"] = 201.0

                def validate(session, *_args, **_kwargs):
                    self.assertIs(self.session, session)
                    trace.append("validate")
                    return result

                with (
                    patch.object(self.legacy, "wait_for_otp", side_effect=wait) as waiter,
                    patch.object(self.legacy, "send_email_otp", side_effect=resend) as sender,
                    patch.object(self.legacy, "validate_email_otp", side_effect=validate) as validator,
                    patch.object(self.legacy.time, "time", side_effect=lambda: clock["now"]),
                    patch.object(self.legacy.time, "sleep"),
                    self.scope.activate(),
                ):
                    self.assertIsNone(network_failure(error=error))
                    self.assertIs(result, self.legacy._validate_with_retry(self.session, EMAIL, 100.0))

                self.assertEqual(["wait", "send", "wait", "validate"], trace)
                self.assertEqual([100.0, 200.0], [item.kwargs["after_ts"] for item in waiter.call_args_list])
                sender.assert_called_once_with(self.session)
                validator.assert_called_once_with(self.session, "654321", sentinel_header=None, so_header=None)

    def test_repeated_no_mail_has_two_waits_and_one_resend_even_with_larger_limit(self):
        for options in ({}, {"max_otp_attempts": 5}):
            with self.subTest(options=options):
                failures = [self.no_mail() for _ in range(3)]
                with (
                    patch.object(self.legacy, "wait_for_otp", side_effect=failures) as waiter,
                    patch.object(self.legacy, "send_email_otp") as sender,
                    patch.object(self.legacy, "validate_email_otp") as validate,
                    patch.object(self.legacy.time, "time", return_value=201.0),
                    patch.object(self.legacy.time, "sleep") as sleep,
                    self.scope.activate(),
                    self.assertRaises(EmailButlerClientError) as caught,
                ):
                    self.legacy._validate_with_retry(self.session, EMAIL, 100.0, **options)

                self.assertIs(failures[1], caught.exception)
                self.assertEqual("email_otp", caught.exception._otp_operation)
                self.assertEqual(2, waiter.call_count)
                self.assertEqual([100.0, 201.0], [item.kwargs["after_ts"] for item in waiter.call_args_list])
                sender.assert_called_once_with(self.session)
                sleep.assert_called_once_with(1)
                validate.assert_not_called()

    def test_invalid_codes_also_stop_after_second_wait_and_validation(self):
        from core.auth.protocol.openai_auth import EmailOtpInvalidError

        failures = [EmailOtpInvalidError("验证码无效") for _ in range(3)]
        with (
            patch.object(self.legacy, "wait_for_otp", side_effect=["654321", "123456", "345678"]) as waiter,
            patch.object(self.legacy, "send_email_otp") as sender,
            patch.object(self.legacy, "validate_email_otp", side_effect=failures) as validate,
            patch.object(self.legacy.time, "time", return_value=201.0),
            patch.object(self.legacy.time, "sleep"),
            self.scope.activate(),
            self.assertRaises(EmailOtpInvalidError) as caught,
        ):
            self.legacy._validate_with_retry(self.session, EMAIL, 100.0)

        self.assertIs(failures[1], caught.exception)
        self.assertEqual("email_otp_validate", caught.exception._otp_operation)
        self.assertEqual(2, waiter.call_count)
        self.assertEqual(2, validate.call_count)
        self.assertEqual([100.0, 201.0], [item.kwargs["after_ts"] for item in waiter.call_args_list])
        sender.assert_called_once_with(self.session)

    def test_invalid_code_resend_keeps_mail_delivered_before_send_response(self):
        from core.auth.protocol.openai_auth import EmailOtpInvalidError

        clock = {"now": 100.0}
        reads = []

        def wait(_email, *, after_ts, **_kwargs):
            reads.append(after_ts)
            if len(reads) == 1:
                clock["now"] = 200.0
                return "654321"
            self.assertLessEqual(after_ts, 200.5)
            return "123456"

        def resend(_session):
            clock["now"] = 201.0

        success = {"continue_url": AUTH + "/authorize/continue"}
        with (
            patch.object(self.legacy, "wait_for_otp", side_effect=wait),
            patch.object(self.legacy, "send_email_otp", side_effect=resend) as sender,
            patch.object(self.legacy, "validate_email_otp", side_effect=[EmailOtpInvalidError("验证码无效"), success]),
            patch.object(self.legacy.time, "time", side_effect=lambda: clock["now"]),
            patch.object(self.legacy.time, "sleep"),
            self.scope.activate(),
        ):
            self.assertIs(success, self.legacy._validate_with_retry(self.session, EMAIL, 100.0))

        self.assertEqual([100.0, 200.0], reads)
        sender.assert_called_once_with(self.session)

    def test_mailbox_rejections_ambiguity_and_http_failure_do_not_resend(self):
        for code, status in (
            ("source_authentication_failed", None),
            ("recipient_mismatch", None),
            ("inbound_code_ambiguous", None),
            ("inbound_code_timeout", 503),
            ("inbound_code_timeout", 429),
        ):
            with self.subTest(code=code, status=status):
                error = EmailButlerClientError(
                    "取码失败，timeout", error_code=code, status_code=status,
                )
                with (
                    patch.object(self.legacy, "wait_for_otp", side_effect=error) as waiter,
                    patch.object(self.legacy, "send_email_otp") as sender,
                    patch.object(self.legacy, "validate_email_otp") as validate,
                    patch.object(self.legacy.time, "sleep") as sleep,
                    self.scope.activate(),
                    self.assertRaises(EmailButlerClientError) as caught,
                ):
                    self.legacy._validate_with_retry(self.session, EMAIL, 100.0)

                self.assertIs(error, caught.exception)
                self.assertEqual("email_otp", caught.exception._otp_operation)
                waiter.assert_called_once()
                sender.assert_not_called()
                validate.assert_not_called()
                sleep.assert_not_called()

    def test_no_mail_code_from_validation_cannot_trigger_wait_retry(self):
        error = self.no_mail()
        with (
            patch.object(self.legacy, "wait_for_otp", return_value="654321") as waiter,
            patch.object(self.legacy, "send_email_otp") as sender,
            patch.object(self.legacy, "validate_email_otp", side_effect=error) as validate,
            self.scope.activate(),
            self.assertRaises(EmailButlerClientError) as caught,
        ):
            self.legacy._validate_with_retry(self.session, EMAIL, 100.0)

        self.assertIs(error, caught.exception)
        self.assertEqual("email_otp_validate", caught.exception._otp_operation)
        waiter.assert_called_once()
        validate.assert_called_once()
        sender.assert_not_called()

    def test_resend_failure_keeps_send_classification_and_never_starts_another_wait(self):
        from core.accounts.liveness.protocol.otp_diagnostics import otp_failure_diagnostics
        from core.auth.protocol.openai_auth import EmailOtpInvalidError, EmailOtpSendError

        for trigger in ("no_mail", "invalid_code"):
            for reason, status in (("http_error", 503), ("rejected", 200), ("unconfirmed", 200)):
                with self.subTest(trigger=trigger, reason=reason):
                    error = EmailOtpSendError(reason, status)
                    wait_error = self.no_mail() if trigger == "no_mail" else None
                    with (
                        patch.object(self.legacy, "wait_for_otp", return_value="654321", side_effect=wait_error) as waiter,
                        patch.object(self.legacy, "validate_email_otp", side_effect=EmailOtpInvalidError("验证码无效")) as validate,
                        patch.object(self.legacy, "send_email_otp", side_effect=error) as sender,
                        patch.object(self.legacy.time, "sleep") as sleep,
                        self.scope.activate(),
                        self.assertRaises(EmailOtpSendError) as caught,
                    ):
                        self.legacy._validate_with_retry(self.session, EMAIL, 100.0)

                    self.assertIs(error, caught.exception)
                    diagnostics = otp_failure_diagnostics(caught.exception)
                    self.assertEqual("email_otp_send", diagnostics["operation"])
                    self.assertEqual(reason, diagnostics["failure_kind"])
                    self.assertEqual(status, diagnostics["http_status"])
                    waiter.assert_called_once()
                    self.assertEqual(trigger == "invalid_code", validate.called)
                    sender.assert_called_once_with(self.session)
                    sleep.assert_not_called()

    def test_explicit_one_attempt_keeps_smaller_limit(self):
        from core.auth.protocol.openai_auth import EmailOtpInvalidError

        for trigger in ("no_mail", "invalid_code"):
            with self.subTest(trigger=trigger):
                error = self.no_mail() if trigger == "no_mail" else EmailOtpInvalidError("验证码无效")
                with (
                    patch.object(self.legacy, "wait_for_otp", return_value="654321",
                                 side_effect=error if trigger == "no_mail" else None) as waiter,
                    patch.object(self.legacy, "validate_email_otp", side_effect=error) as validate,
                    patch.object(self.legacy, "send_email_otp") as sender,
                    self.scope.activate(),
                    self.assertRaises(type(error)) as caught,
                ):
                    self.legacy._validate_with_retry(self.session, EMAIL, 100.0, max_otp_attempts=1)

                self.assertIs(error, caught.exception)
                waiter.assert_called_once()
                self.assertEqual(trigger == "invalid_code", validate.called)
                sender.assert_not_called()

    def test_control_timeout_is_propagated_without_resend(self):
        from core.network.at_transport_recovery import AtRecoveryTimeout

        error = AtRecoveryTimeout("AT 网络恢复总预算已耗尽")
        with (
            patch.object(self.legacy, "wait_for_otp", side_effect=error) as waiter,
            patch.object(self.legacy, "send_email_otp") as sender,
            patch.object(self.legacy, "validate_email_otp") as validate,
            self.scope.activate(),
            self.assertRaises(AtRecoveryTimeout) as caught,
        ):
            self.legacy._validate_with_retry(self.session, EMAIL, 100.0)

        self.assertIs(error, caught.exception)
        waiter.assert_called_once()
        sender.assert_not_called()
        validate.assert_not_called()

    def test_control_checkpoint_after_wait_prevents_resend_for_both_retry_triggers(self):
        from core.auth.protocol.openai_auth import EmailOtpInvalidError
        from core.network.at_transport_recovery import AtRecoveryScope, AtRecoveryTimeout

        for trigger in ("no_mail", "invalid_code"):
            with self.subTest(trigger=trigger):
                error = AtRecoveryTimeout("AT 网络恢复总预算已耗尽")
                checkpoint = MagicMock(side_effect=[None, error])
                scope = AtRecoveryScope(checkpoint=checkpoint)
                with (
                    patch.object(self.legacy, "wait_for_otp", return_value="654321",
                                 side_effect=self.no_mail() if trigger == "no_mail" else None) as waiter,
                    patch.object(self.legacy, "validate_email_otp", side_effect=EmailOtpInvalidError("验证码无效")) as validate,
                    patch.object(self.legacy, "send_email_otp") as sender,
                    patch.object(self.legacy.time, "sleep") as sleep,
                    scope.activate(),
                    self.assertRaises(AtRecoveryTimeout) as caught,
                ):
                    self.legacy._validate_with_retry(self.session, EMAIL, 100.0)

                self.assertIs(error, caught.exception)
                self.assertEqual(2, checkpoint.call_count)
                waiter.assert_called_once()
                self.assertEqual(trigger == "invalid_code", validate.called)
                sender.assert_not_called()
                sleep.assert_not_called()


class ProtocolOtpDiagnosticIntegrationTests(unittest.TestCase):
    def test_at_scope_and_v2_callback_recovery_resend_after_first_no_mail(self):
        from core.accounts.liveness.protocol import legacy, v2
        from core.network.at_transport_recovery import AtRecoveryScope

        session = MagicMock()
        error = EmailButlerClientError(
            "inbound_code_timeout: 等待验证码超时", error_code="inbound_code_timeout",
        )
        continue_url = AUTH + "/authorize/continue"
        # 保留真实 v2 邮箱阶段和重试循环，仅替换外部认证、取码及会话读取。
        with (
            patch.object(v2, "get_account_login_credentials", return_value=("fixture-password", "")),
            patch.object(v2, "account_email_is_invalid", return_value=False),
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, AUTH + "/authorize")),
            patch.object(v2, "follow_authorize", return_value=AUTH + "/email-verification"),
            patch.object(v2, "_open_offered_password_login", return_value=AUTH + "/email-verification"),
            patch.object(v2, "_password_verify") as password,
            patch.object(v2, "_start_email_session") as restart,
            patch.object(v2, "send_email_otp") as initial_send,
            patch.object(legacy, "wait_for_otp", side_effect=[error, "654321"]) as waiter,
            patch.object(legacy, "send_email_otp") as retry_send,
            patch.object(legacy, "validate_email_otp", return_value={"continue_url": continue_url}) as validate,
            patch.object(v2, "_follow_and_fetch", return_value={"accessToken": "fixture-fresh"}) as fetch,
            patch.object(legacy.time, "sleep"),
            AtRecoveryScope().activate(),
        ):
            result = v2.refresh_access_token(EMAIL, proxy="", callback_recovery=True)

        self.assertTrue(result["ok"])
        self.assertEqual("email_otp", result["auth_method"])
        self.assertEqual("success", result["email_otp_status"])
        self.assertEqual(["email_otp"], result["challenge_chain"])
        self.assertEqual(2, waiter.call_count)
        retry_send.assert_called_once_with(session)
        validate.assert_called_once_with(session, "654321", sentinel_header=None, so_header=None)
        fetch.assert_called_once_with(session, continue_url, referer=AUTH + "/email-verification")
        initial_send.assert_not_called()
        password.assert_not_called()
        restart.assert_not_called()
        session.session.close.assert_called_once()

    def test_v2_failure_result_keeps_mailbox_cause_and_original_behavior_flags(self):
        from core.accounts.liveness.protocol import legacy, v2

        session = MagicMock()
        error = EmailButlerClientError(
            PRIVATE_DETAIL, error_code="source_authentication_failed", status_code=408,
        )
        with (
            patch.object(v2, "get_account_login_credentials", return_value=("fixture-password", "")),
            patch.object(v2, "account_email_is_invalid", return_value=False),
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, AUTH + "/authorize")),
            patch.object(v2, "follow_authorize", return_value=AUTH + "/email-verification"),
            patch.object(v2, "_open_offered_password_login", return_value=AUTH + "/email-verification"),
            patch.object(v2, "send_email_otp") as initial_send,
            patch.object(legacy, "wait_for_otp", side_effect=error) as waiter,
            patch.object(legacy, "send_email_otp") as retry_send,
            patch.object(legacy, "validate_email_otp") as validate,
        ):
            result = v2.refresh_access_token(EMAIL, proxy="", callback_recovery=True)

        self.assertFalse(result["ok"])
        self.assertEqual("email_otp_failed", result["error"])
        self.assertFalse(result["retryable"])
        self.assertFalse(result["roxy_fallback_allowed"])
        self.assertEqual("source_authentication_failed", result["auth_diagnostics"]["mailbox_error_code"])
        self.assertEqual("mailbox_error", result["auth_diagnostics"]["failure_kind"])
        self.assertEqual(408, result["auth_diagnostics"]["http_status"])
        self.assertNotIn("fixture-secret", json.dumps(result))
        initial_send.assert_not_called()
        waiter.assert_called_once()
        retry_send.assert_not_called()
        validate.assert_not_called()
        session.session.close.assert_called_once()

    def test_v3_wait_failure_keeps_mailbox_diagnostics_without_new_auth_requests(self):
        from core.accounts.liveness.protocol import v3

        for code, kind in (("inbound_code_timeout", "no_mail"), ("source_authentication_failed", "mailbox_error")):
            with self.subTest(code=code):
                session = MagicMock()
                target = {"id": 7, "email": EMAIL}
                error = EmailButlerClientError(PRIVATE_DETAIL, error_code=code)
                with (
                    patch.object(v3.db, "get_account", return_value=target),
                    patch.object(v3.protocol_sessions, "load_session", return_value=None),
                    patch.object(v3, "get_account_login_credentials", return_value=("fixture-password", "")),
                    patch.object(v3, "account_email_is_invalid", return_value=False),
                    patch.object(v3, "_network_preflight_with_retry", return_value=(session, AUTH + "/authorize")),
                    patch.object(v3, "_follow", return_value=AUTH + "/email-verification"),
                    patch.object(v3, "_client_auth_context", return_value={}),
                    patch.object(v3, "send_email_otp") as sender,
                    patch.object(v3, "wait_for_otp", side_effect=error) as waiter,
                    patch.object(v3, "_post_json") as submit,
                ):
                    result = v3.refresh_access_token(EMAIL, account_id=7, proxy="")

                self.assertFalse(result["ok"])
                self.assertEqual("email_otp_failed", result["error"])
                self.assertFalse(result["retryable"])
                self.assertFalse(result["roxy_fallback_allowed"])
                self.assertEqual(code, result["auth_diagnostics"]["mailbox_error_code"])
                self.assertEqual(kind, result["auth_diagnostics"]["failure_kind"])
                self.assertNotIn("fixture-secret", json.dumps(result))
                sender.assert_called_once_with(session)
                waiter.assert_called_once()
                submit.assert_not_called()
                session.session.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
