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
