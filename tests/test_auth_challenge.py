import unittest

from core.auth_challenge import (
    StepResult, auth_result_for_operation, normalize_auth_result, normalize_step_result,
    safe_to_start_new_registration,
)


class ConcreteAuthFailureTests(unittest.TestCase):
    def test_normalization_preserves_legacy_and_dispatched_reconciliation_guards(self):
        for evidence in (
            {"request_unknown": True},
            {"manual_reconcile": True},
            {"action_dispatched": True, "remote_response_received": False},
        ):
            with self.subTest(evidence=evidence):
                mapping = {
                    "ok": False, "error_code": "network_error", "remote_identity": "new_candidate",
                    "roxy_fallback_allowed": True, "retryable": True, **evidence,
                }
                auth = normalize_auth_result(mapping)
                self.assertEqual("network_error", auth.code)
                self.assertTrue(auth.reconcile_required)
                self.assertFalse(auth.roxy_fallback_allowed)
                self.assertFalse(auth.retryable)
                self.assertFalse(safe_to_start_new_registration(auth))
                step = normalize_step_result(mapping)
                self.assertEqual("network_error", step.code)
                self.assertTrue(step.reconcile_required)
                self.assertFalse(step.retryable)
                self.assertEqual("manual_reconcile", step.next_action)

    def test_sentinel_failure_keeps_specific_code_without_reconciliation(self):
        result = auth_result_for_operation(
            {"ok": False, "error": "password_sentinel_failed", "mutation_submitted": False,
             "action_dispatched": False, "roxy_fallback_allowed": True},
            auth_method="protocol_v2",
        )
        self.assertEqual("failed", result.status)
        self.assertEqual("password_sentinel_failed", result.code)
        self.assertEqual("stop", result.next_action)
        self.assertTrue(result.roxy_fallback_allowed)

    def test_missing_driver_result_is_failed_without_assuming_remote_submission(self):
        result = normalize_auth_result(None)
        self.assertEqual("failed", result.status)
        self.assertEqual("auth_result_missing", result.code)
        self.assertEqual("stop", result.next_action)

    def test_submitted_step_preserves_timeout_cause_and_reconciliation_guard(self):
        result = StepResult.failure(
            "password_verify", "password_transport_failed", action_dispatched=True,
            remote_response_received=False, retryable=True,
        )
        self.assertEqual("password_transport_failed", result.code)
        self.assertEqual("manual_reconcile", result.next_action)
        self.assertFalse(result.retryable)
        self.assertTrue(result.reconcile_required)

    def test_missing_remote_receipt_cannot_be_projected_as_authenticated(self):
        result = auth_result_for_operation(
            {"ok": True, "action_dispatched": True, "remote_response_received": False},
            auth_method="protocol_v2",
        )
        self.assertEqual("failed", result.status)
        self.assertEqual("remote_response_missing", result.code)
        self.assertTrue(result.reconcile_required)
        self.assertEqual("manual_reconcile", result.next_action)
