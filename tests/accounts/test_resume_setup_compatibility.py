"""注册续跑补密码在核心 handler 中保留取消、凭据与冻结设置契约。"""
from contextlib import ExitStack
import unittest
from unittest.mock import patch

from core import db
from core.accounts import completion, operation_results, setup_execution
from core.codex import retry_service
from core.operations import task_gateway
from core.runtime import capabilities
from core.storage import registration
from tests.accounts.test_completion_execution_boundaries import execution_context


class ResumeSetupCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.context = execution_context(data={
            "steps": ["password"],
            "registration_completion": True,
            "registration_run_id": 51,
            "completion_auth": True,
            "task_trigger": "registration_resume_completion",
        })
        self.context.task_type = "password_setup"
        self.context.config_snapshot.update(
            password_enabled=True, password_proxy_mode="pool",
            auth_raw_context_enabled=False,
        )
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.source_run = self.stack.enter_context(patch.object(
            registration, "get_run", return_value={"id": 51, "job_id": 61, "status": "partial_success"},
        ))
        self.source_job = self.stack.enter_context(patch.object(
            db, "get_job", return_value={"id": 61, "status": "partial_success"},
        ))
        self.account = self.stack.enter_context(patch.object(
            db, "get_account", return_value={
                "id": 41, "access_token": "fixture-access-token", "extra_json": {
                    "account_password": "fixture-candidate", "account_password_state": "candidate",
                },
            },
        ))
        self.stack.enter_context(patch.object(capabilities, "account_setup_unavailable", return_value=None))
        self.active_registration = self.stack.enter_context(patch.object(
            completion, "active_registration_job", return_value=None,
        ))
        self.remote = self.stack.enter_context(patch.object(
            retry_service, "run_twofa_worker", return_value={"ok": True, "status": "success"},
        ))
        self.stack.enter_context(patch.object(
            operation_results, "account_setup_receipt", return_value=("confirmed", {}),
        ))

    def test_stopped_or_cancelled_source_never_acquires_lease_or_starts_remote_write(self):
        for run_status, job_status in (
            ("stopped", "partial_success"), ("cancelled", "success"),
            ("partial_success", "stopping"), ("partial_success", "stopped"),
            ("partial_success", "cancelled"),
        ):
            with self.subTest(run_status=run_status, job_status=job_status):
                self.context.finished = False
                self.source_run.return_value["status"] = run_status
                self.source_job.return_value["status"] = job_status
                result = setup_execution.handle_native_account_setup(self.context)
                self.assertEqual("cancelled", result.status)
        self.context.lease.assert_not_called()
        self.context.remote_request_started.assert_not_called()
        self.remote.assert_not_called()

    def test_confirmed_password_short_circuits_inside_final_lease(self):
        self.account.return_value["extra_json"]["account_password_state"] = "confirmed"
        result = setup_execution.handle_native_account_setup(self.context)
        self.assertEqual("success", result.status)
        self.assertTrue(result.summary["already_confirmed"])
        self.context.lease.assert_called_once_with(resource_family="openai_interactive", scope_kind="final")
        self.context.remote_request_started.assert_not_called()
        self.remote.assert_not_called()

    def test_registration_completion_executes_frozen_settings_and_country(self):
        self.context.run["data"]["proxy_country_override"] = "JP"
        result = setup_execution.handle_native_account_setup(self.context)
        self.assertEqual("success", result.status)
        settings = self.remote.call_args.kwargs["execution_settings"]
        self.assertEqual("protocol", settings["password_driver"])
        self.assertEqual("pool", settings["password_proxy_mode"])
        self.assertIs(settings["auth_raw_context_enabled"], False)
        self.assertEqual("JP", self.remote.call_args.kwargs["proxy_country_override"])
        self.assertEqual(self.context.execution_fence, self.remote.call_args.kwargs["execution_fence"])
        self.context.remote_request_receipt.assert_called_once()

    def test_invalid_country_never_submits_remote_request(self):
        self.context.run["data"]["proxy_country_override"] = "jp"
        result = setup_execution.handle_native_account_setup(self.context)
        self.assertEqual("failed", result.status)
        self.context.lease.assert_not_called()
        self.remote.assert_not_called()

    def test_active_registration_requeues_before_remote_write(self):
        self.active_registration.return_value = {"id": 61, "status": "running"}
        with self.assertRaises(task_gateway.OperationLeaseUnavailable):
            setup_execution.handle_native_account_setup(self.context)
        self.context.remote_request_started.assert_not_called()
        self.remote.assert_not_called()
