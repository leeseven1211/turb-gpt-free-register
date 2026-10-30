# -*- coding: utf-8 -*-
"""Pure service projections for workflow C next actions."""
import unittest
from unittest.mock import patch

from core.registration import service as registration_service
from core.registration.service import _build_retry_info


class RegistrationServicePostprocessContractTests(unittest.TestCase):
    def test_request_unknown_keeps_safe_registration_diagnostics(self):
        evidence = {
            "operation": "otp_validate", "failure_kind": "transport_error",
            "exception_type": "TimeoutError", "failure_stage": "email_otp",
            "last_confirmed_stage": "password", "otp_received": True,
            "profile_confirmed": False,
        }
        facts = registration_service._registration_request_unknown_facts({
            "cause_code": "user_register_result_unknown",
            "register_response_confirmed": True,
            "registration_diagnostics": {**evidence, "raw_response": "不可持久化", "email": "unit@example.test"},
        })
        self.assertEqual(evidence, facts.get("registration_diagnostics"))
        self.assertEqual("request_unknown", facts["outcome"])
        self.assertTrue(facts["register_response_confirmed"])

    def test_request_unknown_drops_untrusted_registration_diagnostics(self):
        facts = registration_service._registration_request_unknown_facts({
            "registration_diagnostics": {"email": "unit@example.test", "raw_response": "不可持久化"},
        })
        self.assertNotIn("registration_diagnostics", facts)

    def test_request_unknown_facts_only_keep_fixed_code_and_real_boolean(self):
        facts = registration_service._registration_request_unknown_facts({
            "cause_code": "registration_checkpoint_failed",
            "register_response_confirmed": True,
            "raw_response": "不可持久化",
        })
        self.assertEqual({
            "outcome": "request_unknown",
            "cause_code": "registration_checkpoint_failed",
            "register_response_confirmed": True,
        }, facts)
        self.assertEqual(
            {"outcome": "request_unknown"},
            registration_service._registration_request_unknown_facts({
                "cause_code": "untrusted_remote_body",
                "register_response_confirmed": "true",
            }),
        )

    def test_request_unknown_attempt_keeps_confirmed_register_response(self):
        registration_service._THREAD_CTX.job_id = 99
        registration_service._THREAD_CTX.attempt_id = 7
        registration_service._THREAD_CTX.run_id = 12
        registration_service._THREAD_CTX.execution_id = "test-execution"
        try:
            with patch("core.storage.registration.mark_request_unknown") as mark:
                registration_service._mark_registration_request_unknown(
                    "账号创建后邮箱验证未完成",
                    facts={
                        "cause_code": "email_otp_no_mail",
                        "register_response_confirmed": True,
                        "raw_response": "不可持久化",
                    },
                )
            kwargs = mark.call_args.kwargs
            self.assertTrue(kwargs["identity_response_confirmed"])
            self.assertEqual("email_otp_no_mail", kwargs["detail"]["cause_code"])
            self.assertNotIn("raw_response", kwargs["detail"])
        finally:
            for attr in ("job_id", "attempt_id", "run_id", "execution_id"):
                try:
                    delattr(registration_service._THREAD_CTX, attr)
                except AttributeError:
                    pass

    def test_finish_unknown_run_writes_fence_and_resyncs_projection(self):
        registration_service._THREAD_CTX.job_id = 99
        registration_service._THREAD_CTX.run_id = 12
        try:
            with patch("core.storage.registration.finish_run") as finish, patch(
                "core.operation_task_store.sync_registration_job"
            ) as sync:
                registration_service._finish_registration_run(
                    "request_unknown",
                    error_message="request_unknown",
                    result_summary={"outcome": "request_unknown", "cause_code": "email_otp_no_mail"},
                )
            self.assertEqual("request_unknown", finish.call_args.kwargs["error_code"])
            sync.assert_called_once_with(99)
        finally:
            for attr in ("job_id", "run_id"):
                try:
                    delattr(registration_service._THREAD_CTX, attr)
                except AttributeError:
                    pass

    def test_request_unknown_without_account_cannot_start_new_registration(self):
        info = _build_retry_info(
            {
                "status": "request_unknown",
                "email_source": "icloud_hide",
                "progress_steps": {"auth_redirect": {"state": "failed"}},
            },
            account=None,
            successful_retry=None,
        )

        self.assertFalse(info["retryable"])
        self.assertIsNone(info["retry_action"])
        self.assertEqual([], info["next_actions"])

    def test_request_unknown_with_matching_attempt_can_resume_email_verification(self):
        job = {
            "id": 21, "root_job_id": 21, "attempt_id": 70,
            "status": "request_unknown", "account_id": 44,
            "email": "pending@example.com",
        }
        account = {
            "id": 44, "email": "pending@example.com", "access_token": "",
            "extra_json": '{"registration_checkpoint":"email_verification_pending","registration_password":"example"}',
        }
        attempt = {
            "id": 70, "source_root_job_id": 21, "account_id": 44,
            "email_snapshot": "pending@example.com", "checkpoint": "otp_started",
            "target_status": "request_unknown", "remote_identity_state": "confirmed",
        }
        info = _build_retry_info(job, account=account, successful_retry=None, attempt=attempt)
        self.assertTrue(info["retryable"])
        self.assertEqual("registration_resume", info["retry_action"])
        self.assertEqual("registration_resume", info["next_actions"][0]["action"])

        mismatched = dict(attempt, email_snapshot="other@example.com")
        blocked = _build_retry_info(job, account=account, successful_retry=None, attempt=mismatched)
        self.assertFalse(blocked["retryable"])
        self.assertEqual([], blocked["next_actions"])

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

    def test_codex_unknown_result_does_not_offer_retry(self):
        info = _build_retry_info(
            {"status": "partial_success", "account_id": 42},
            account={
                "id": 42,
                "email": "account@example.com",
                "access_token": "token",
                "codex_status": "attention_required",
                "plan_check_status": "success",
                "totp_secret": "",
                "extra_json": '{"account_password":"Password!123"}',
            },
            successful_retry=None,
        )
        self.assertFalse(info["retryable"])
        self.assertIsNone(info["retry_action"])
        self.assertEqual([], info["next_actions"])
        self.assertIn("待核对", info["retry_reason"])

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
            {
                "id": 21, "root_job_id": 21, "attempt_id": 70,
                "status": "partial_success", "account_id": 44,
                "email": "pending@example.com",
            },
            account={
                "id": 44,
                "email": "pending@example.com",
                "access_token": "",
                "extra_json": '{"registration_checkpoint":"email_verification_pending","registration_password":"Password!123"}',
            },
            successful_retry=None,
            attempt={
                "id": 70, "source_root_job_id": 21, "account_id": 44,
                "email_snapshot": "pending@example.com", "checkpoint": "otp_started",
                "target_status": "email_verification_pending", "remote_identity_state": "confirmed",
            },
        )

        self.assertEqual("registration_resume", info["retry_action"])
        self.assertEqual("registration_resume", info["next_actions"][0]["action"])
        self.assertEqual("failed", info["display_status"])
        self.assertIn("已保存密码", info["retry_reason"])
        self.assertIn("同一账号验证", info["retry_reason"])
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
        self.assertIn("禁止", info["retry_reason"])

    def test_normalized_target_without_account_checkpoint_cannot_resume(self):
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

        self.assertFalse(info["retryable"])
        self.assertIsNone(info["retry_action"])

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
