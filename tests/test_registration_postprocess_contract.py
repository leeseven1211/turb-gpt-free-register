# -*- coding: utf-8 -*-
"""Storage-neutral workflow C contract tests."""
import unittest

from core.registration_postprocess import (
    PLAN_CHECK,
    POSTPROCESS,
    REGISTRATION_NEW,
    REGISTRATION_RECONCILE,
    REGISTRATION_RESUME,
    RETRY_CODEX,
    RETRY_TWOFA,
    PostprocessResult,
    decide_recovery,
    next_actions_for_postprocess,
    summarize_postprocess,
)


class PostprocessContractTests(unittest.TestCase):
    def test_twofa_failure_does_not_roll_back_registration_core(self):
        summary = summarize_postprocess(
            core_success=True,
            password_present=True,
            twofa_required=True,
            codex_enabled=False,
            plan_check_required=False,
            outcomes={
                "twofa": {"status": "failed", "ok": False, "message": "安全设置暂时不可用"},
            },
        )

        self.assertEqual("success", summary.registration_core_status)
        self.assertEqual("incomplete", summary.account_readiness)
        self.assertEqual([RETRY_TWOFA], [item.action for item in summary.next_actions])

    def test_codex_and_plan_failures_become_explicit_actions(self):
        actions = next_actions_for_postprocess(
            core_success=True,
            twofa_required=False,
            codex_enabled=True,
            plan_check_required=True,
            outcomes={
                "codex": {"status": "failed", "message": "OAuth callback failed"},
                "plan_check": {"status": "failed", "error": "HTTP 503"},
            },
        )

        self.assertEqual([RETRY_CODEX, PLAN_CHECK], [item.action for item in actions])
        self.assertEqual("OAuth callback failed", actions[0].reason)
        self.assertEqual("HTTP 503", actions[1].reason)

    def test_running_postprocess_is_not_duplicated(self):
        actions = next_actions_for_postprocess(
            core_success=True,
            twofa_required=False,
            codex_enabled=True,
            plan_check_required=False,
            outcomes={"codex": {"status": "running"}},
        )

        # An active action is reconciled by its owner/recovery worker rather
        # than creating a second action task.
        self.assertEqual([], [item.action for item in actions])

    def test_disabled_capabilities_are_skipped_and_account_can_be_ready(self):
        summary = summarize_postprocess(
            core_success=True,
            password_present=True,
            twofa_required=False,
            codex_enabled=False,
            plan_check_required=False,
        )

        self.assertEqual("ready", summary.account_readiness)
        self.assertEqual([], list(summary.next_actions))
        self.assertTrue(all(result.ok for result in summary.results))

    def test_non_core_failure_does_not_emit_postprocess_retry(self):
        actions = next_actions_for_postprocess(
            core_success=False,
            codex_enabled=True,
            outcomes={"codex": {"status": "failed"}},
        )

        self.assertEqual((), actions)

    def test_result_normalization_keeps_only_compatibility_fields(self):
        result = PostprocessResult.from_value(
            "codex",
            {
                "status": "success",
                "ok": True,
                "message": "done",
                "detail": {"access_token": "must not be copied"},
                "access_token": "must not be copied",
                "callback_url": "must not be copied",
            },
        )

        self.assertEqual("codex", result.stage)
        self.assertTrue(result.completed)
        self.assertNotIn("access_token", result.as_dict())
        self.assertNotIn("callback_url", result.as_dict())


class RecoveryDecisionContractTests(unittest.TestCase):
    def test_pre_boundary_attempt_can_start_new_registration(self):
        decision = decide_recovery(
            {
                "checkpoint": "email_claimed",
                "remote_identity_state": "not_started",
                "remote_account_state": "not_started",
                "local_account_state": "none",
                "email_resume_capability": "api_reconnect",
            }
        )

        self.assertEqual(REGISTRATION_NEW, decision.action)
        self.assertTrue(decision.safe_to_start_new_registration)
        self.assertEqual("release", decision.email_lease)
        self.assertEqual("release", decision.proxy_lease)

    def test_password_boundary_resumes_same_attempt_when_email_is_recoverable(self):
        decision = decide_recovery(
            {
                "checkpoint": "password_confirmed",
                "remote_identity_state": "confirmed",
                "remote_account_state": "not_started",
                "local_account_state": "none",
                "email_resume_capability": "durable_reconnect",
                "has_password": True,
            }
        )

        self.assertEqual(REGISTRATION_RESUME, decision.action)
        self.assertFalse(decision.safe_to_start_new_registration)
        self.assertEqual("retain", decision.email_lease)

    def test_irreversible_boundary_without_recovery_context_is_quarantined(self):
        decision = decide_recovery(
            {
                "checkpoint": "password_request_started",
                "remote_identity_state": "request_unknown",
                "remote_account_state": "not_started",
                "local_account_state": "none",
                "email_resume_capability": "process_bound",
                "has_password": False,
            }
        )

        self.assertEqual(REGISTRATION_RECONCILE, decision.action)
        self.assertEqual("quarantine", decision.email_lease)
        self.assertFalse(decision.safe_to_start_new_registration)

    def test_account_request_unknown_never_allows_new_registration(self):
        decision = decide_recovery(
            {
                "checkpoint": "account_request_started",
                "remote_identity_state": "confirmed",
                "remote_account_state": "request_unknown",
                "local_account_state": "none",
                "email_resume_capability": "api_reconnect",
                "has_password": True,
            }
        )

        self.assertEqual(REGISTRATION_RECONCILE, decision.action)
        self.assertFalse(decision.safe_to_start_new_registration)
        self.assertEqual("quarantine", decision.email_lease)

    def test_core_persisted_only_recovers_postprocess(self):
        decision = decide_recovery(
            {
                "checkpoint": "core_persisted",
                "remote_identity_state": "confirmed",
                "remote_account_state": "confirmed",
                "local_account_state": "persisted",
                "account_id": 42,
                "has_access_token": True,
                "email_resume_capability": "manual_only",
            }
        )

        self.assertEqual(POSTPROCESS, decision.action)
        self.assertEqual("retain", decision.email_lease)
        self.assertFalse(decision.safe_to_start_new_registration)

    def test_token_observed_before_core_persistence_requires_reconcile(self):
        decision = decide_recovery(
            {
                "checkpoint": "token_obtained",
                "remote_identity_state": "confirmed",
                "remote_account_state": "confirmed",
                "local_account_state": "token_obtained",
                "has_access_token": True,
                "email_resume_capability": "api_reconnect",
            }
        )

        self.assertEqual(REGISTRATION_RECONCILE, decision.action)
        self.assertEqual("quarantine", decision.email_lease)

    def test_active_execution_does_not_release_resources(self):
        decision = decide_recovery(
            {
                "checkpoint": "postprocessing",
                "remote_identity_state": "confirmed",
                "remote_account_state": "confirmed",
                "local_account_state": "persisted",
                "account_id": 42,
                "has_access_token": True,
                "active_execution": True,
            }
        )

        self.assertEqual("none", decision.action)
        self.assertEqual("retain", decision.email_lease)
        self.assertEqual("retain", decision.proxy_lease)

    def test_missing_or_unknown_state_fails_closed(self):
        decision = decide_recovery({})

        self.assertEqual(REGISTRATION_RECONCILE, decision.action)
        self.assertFalse(decision.safe_to_start_new_registration)
        self.assertEqual("quarantine", decision.email_lease)

    def test_decision_is_pure_and_does_not_mutate_snapshot(self):
        snapshot = {
            "checkpoint": "email_claimed",
            "remote_identity_state": "not_started",
            "remote_account_state": "not_started",
            "local_account_state": "none",
        }
        before = dict(snapshot)

        decide_recovery(snapshot)

        self.assertEqual(before, snapshot)


if __name__ == "__main__":
    unittest.main()
