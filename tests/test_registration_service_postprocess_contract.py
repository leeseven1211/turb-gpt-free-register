# -*- coding: utf-8 -*-
"""Pure service projections for workflow C next actions."""
import unittest
from unittest.mock import patch

from core import registration_service
from core.registration_service import _build_retry_info


class RegistrationServicePostprocessContractTests(unittest.TestCase):
    def test_multiple_independent_actions_are_exposed(self):
        info = _build_retry_info(
            {
                "status": "partial_success",
                "account_id": 42,
                "progress_steps": {
                    "codex": {"state": "failed"},
                    "twofa": {"state": "success"},
                },
            },
            account={
                "id": 42,
                "email": "account@example.com",
                "access_token": "token",
                "codex_status": "failed",
                "plan_check_status": "failed",
                "totp_secret": "JBSWY3DPEHPK3PXP",
                "extra_json": '{"account_password":"Password!123"}',
            },
            successful_retry=None,
        )

        self.assertEqual("codex", info["retry_action"])
        self.assertEqual(
            ["retry_codex", "plan_check"],
            [action["action"] for action in info["next_actions"]],
        )

    def test_plan_only_retry_has_dedicated_action(self):
        info = _build_retry_info(
            {
                "status": "partial_success",
                "account_id": 43,
                "progress_steps": {
                    "codex": {"state": "success"},
                    "twofa": {"state": "success"},
                },
            },
            account={
                "id": 43,
                "email": "plan@example.com",
                "access_token": "token",
                "codex_status": "success",
                "plan_check_status": "failed",
                "totp_secret": "JBSWY3DPEHPK3PXP",
                "extra_json": '{"account_password":"Password!123"}',
            },
            successful_retry=None,
        )

        self.assertEqual("plan_check", info["retry_action"])
        self.assertEqual(["plan_check"], [action["action"] for action in info["next_actions"]])

    def test_confirmed_deactivation_suppresses_all_postprocess_actions(self):
        info = _build_retry_info(
            {
                "status": "partial_success",
                "account_id": 44,
                "progress_steps": {
                    "codex": {"state": "failed"},
                    "twofa": {"state": "failed"},
                },
            },
            account={
                "id": 44,
                "email": "deactivated@example.com",
                "access_token": "token",
                "account_status": "deactivated",
                "codex_status": "deactivated",
                "plan_check_status": "failed",
                "extra_json": '{"account_password":"Password!123"}',
            },
            successful_retry=None,
        )

        self.assertFalse(info["retryable"])
        self.assertIsNone(info["retry_action"])
        self.assertEqual([], info["next_actions"])
        self.assertEqual("failed", info["display_status"])
        self.assertIn("永久失效", info["retry_reason"])

    def test_recovery_adapter_passes_deactivated_target_status_to_decision(self):
        attempt = {
            "id": 46,
            "checkpoint": "failed",
            "target_status": "deactivated",
            "remote_identity_state": "confirmed",
            "remote_account_state": "confirmed",
            "local_account_state": "persisted",
            "account_id": 46,
            "data": {"has_access_token": True},
            "active_execution_id": None,
        }
        with patch("core.storage.registration.recover_interrupted_runs"), patch(
            "core.storage.registration.list_attempts", return_value=[attempt]
        ):
            decisions = registration_service.recover_registration_attempts()

        self.assertEqual("none", decisions[0]["decision"]["action"])
        self.assertFalse(decisions[0]["decision"]["safe_to_start_new_registration"])

    def test_pending_email_resume_is_same_attempt_action(self):
        info = _build_retry_info(
            {"status": "partial_success", "account_id": 44},
            account={
                "id": 44,
                "email": "pending@example.com",
                "access_token": "",
                "extra_json": '{"registration_checkpoint":"email_verification_pending","registration_password":"Password!123"}',
            },
            successful_retry=None,
        )

        self.assertEqual("registration_resume", info["retry_action"])
        self.assertEqual("registration_resume", info["next_actions"][0]["action"])
        self.assertEqual("password_confirmation_pending", info["display_status"])
        self.assertIn("密码已提交", info["retry_reason"])
        self.assertIn("远端结果尚未确认", info["retry_reason"])
        self.assertNotIn("密码已创建", info["retry_reason"])

    def test_confirmed_deactivated_account_is_not_retryable_with_stale_codex_projection(self):
        info = _build_retry_info(
            {
                "status": "partial_success",
                "account_id": 46,
                "progress_steps": {"codex": {"state": "failed"}},
            },
            account={
                "id": 46,
                "email": "deactivated@example.com",
                "account_status": "deactivated",
                "codex_status": "failed",
                "plan_check_status": "failed",
                "totp_secret": "",
                "extra_json": "{}",
            },
            successful_retry=None,
        )

        self.assertFalse(info["retryable"])
        self.assertEqual("账号已废号，不能补跑 Codex", info["retry_reason"])

    def test_normalized_attempt_can_make_pending_registration_resumeable(self):
        with patch(
            "core.storage.registration.get_latest_attempt_by_account",
            return_value={"target_status": "email_verification_pending"},
        ):
            account = registration_service._enrich_account_registration_state({
                "id": 45,
                "email": "pending-normalized@example.com",
                "access_token": "",
                "extra_json": '{"account_password":"Password!123"}',
            })
            info = _build_retry_info(
                {"status": "partial_success", "account_id": 45},
                account=account,
                successful_retry=None,
            )

        self.assertEqual("registration_resume", info["retry_action"])

    def test_attempt_run_adapter_uses_existing_attempt_id(self):
        registration_service._THREAD_CTX.job_id = 99
        with patch("core.storage.registration.get_attempt", return_value={"id": 7}) as get_attempt, patch(
            "core.storage.registration.start_run", return_value={"id": 12}
        ) as start_run:
            context = registration_service._ensure_registration_run_context(
                {"attempt_id": 7, "job_type": "twofa_retry"}
            )

        self.assertEqual(7, context["attempt_id"])
        self.assertEqual(12, context["run_id"])
        get_attempt.assert_called_once_with(7)
        self.assertEqual(7, start_run.call_args.args[0])
        self.assertEqual("twofa_retry", start_run.call_args.kwargs["action_type"])
        for attr in ("job_id", "attempt_id", "run_id", "execution_id"):
            try:
                delattr(registration_service._THREAD_CTX, attr)
            except AttributeError:
                pass
