# -*- coding: utf-8 -*-
import logging
import unittest
from unittest.mock import patch

from flask import Flask

from webui import runtime


class WebUIRuntimeTests(unittest.TestCase):
    def setUp(self):
        runtime._runtime_started = False

    def tearDown(self):
        runtime._runtime_started = False

    def test_start_runtime_recovers_and_starts_periodic_workers_once(self):
        with (
            patch.object(runtime.db, "recover_interrupted_registration_jobs", return_value=2) as recover_jobs,
            patch.object(runtime.account_task_store, "recover_interrupted", return_value=1) as recover_accounts,
            patch.object(runtime.operation_task_store, "init") as init_operations,
            patch.object(runtime.operation_task_store, "start_projection_worker") as start_projection,
            patch.object(runtime.operation_task_store, "recover_interrupted_runtime_runs", return_value=3) as recover_operations,
            patch.object(runtime.operation_task_store, "repair_stale_compatibility_projections", return_value=2) as repair_compatibility,
            patch("core.roxybrowser_client.cleanup_orphaned_profiles", return_value={"found": 0}) as cleanup_roxy,
            patch.object(runtime.sms_provider, "start_cancel_worker") as start_sms,
            patch.object(runtime.db, "recover_interrupted_plan_checks", return_value=4) as recover_plans,
            patch.object(runtime.db, "recover_interrupted_extract_links", return_value=5) as recover_links,
            patch.object(runtime.db, "recover_interrupted_live_checks", return_value=6) as recover_live,
            patch.object(runtime.db, "backfill_account_registration_proxy_context", return_value=7) as backfill_proxy,
            patch.object(runtime.codex_operation_service, "resume_queued", return_value=8) as resume_codex,
            patch("core.deactivation_mail_service.start_periodic_scanner") as start_risk_scan,
            patch("core.token_refresh_service.start_periodic_refresher") as start_at_refresh,
            patch("core.codex_token_refresh_service.start_periodic_refresher") as start_codex_refresh,
            patch("core.account_auth_context_service.start_periodic_cleanup") as start_auth_context_cleanup,
        ):
            self.assertTrue(runtime.start_runtime(logging.getLogger("test-webui-runtime")))
            self.assertFalse(runtime.start_runtime(logging.getLogger("test-webui-runtime")))

        for mock in (
            recover_jobs,
            recover_accounts,
            init_operations,
            start_projection,
            recover_operations,
            repair_compatibility,
            cleanup_roxy,
            start_sms,
            recover_plans,
            recover_links,
            recover_live,
            backfill_proxy,
            resume_codex,
            start_risk_scan,
            start_at_refresh,
            start_codex_refresh,
            start_auth_context_cleanup,
        ):
            self.assertEqual(1, mock.call_count)

    def test_completion_routes_pending_registration_to_resume_job(self):
        context = runtime.WebUIContext(Flask("test-runtime"), logging.getLogger("test-runtime"))
        account = {
            "id": 591,
            "email": "pending@example.test",
            "access_token": "",
            "extra_json": '{"account_password":"Password!123"}',
        }
        attempt = {
            "target_status": "email_verification_pending",
            "remote_account_state": "request_unknown",
            "checkpoint": "account_request_started",
        }
        resume_result = {
            "ok": True,
            "created": True,
            "source_job_id": 836,
            "job": {"id": 861, "job_type": "registration_resume"},
            "message": "已继续原注册任务，不执行 AT 刷新",
        }
        with (
            patch.object(runtime.db, "get_account", return_value=account),
            patch("core.storage.registration.get_latest_attempt_by_account", return_value=attempt),
            patch.object(runtime.db, "get_latest_registration_job_for_account", return_value={"id": 836}),
            patch("core.registration_service.retry_job", return_value=resume_result) as retry_job,
        ):
            result = context.enqueue_account_completion(591)

        self.assertTrue(result["accepted"])
        self.assertTrue(result["registration_resume"])
        self.assertEqual(861, result["job_id"])
        retry_job.assert_called_once_with(836)

    def test_old_refresh_plan_is_stopped_when_switch_is_now_off(self):
        account = {
            "id": 591,
            "email": "pending@example.test",
            "access_token": "",
            "extra_json": '{"registration_checkpoint":"email_verification_pending","account_password":"Password!123"}',
        }
        with (
            patch.object(runtime.account_task_store, "start_task"),
            patch.object(runtime.account_task_store, "append_event"),
            patch.object(runtime.account_task_store, "finish_task") as finish_task,
            patch.object(runtime.db, "get_account", return_value=account),
            patch("config.account.completion_settings", return_value={
                "password_enabled": True,
                "plan_check_enabled": True,
                "twofa_enabled": True,
                "codex_enabled": False,
                "refresh_at_enabled": False,
            }),
            patch.object(runtime.live_check_service, "enqueue_account_live_check") as enqueue_live,
            patch.object(runtime.codex_retry_service, "release"),
        ):
            runtime._run_account_completion_worker(
                "pending@example.test",
                account_id=591,
                task_id=999,
                task_trigger="manual_account_completion",
                planned_steps=["refresh_at"],
                settings={"refresh_at_enabled": True},
            )

        enqueue_live.assert_not_called()
        self.assertEqual("cancelled", finish_task.call_args.kwargs["status"])
        self.assertTrue(finish_task.call_args.kwargs["result_summary"]["stale_plan"])

    def test_refresh_submission_is_partial_until_child_finishes(self):
        account = {
            "id": 592,
            "email": "registered@example.test",
            "access_token": "",
            "extra_json": "{}",
        }
        queued = {"accepted": True, "busy": False, "task_id": 1001}
        with (
            patch.object(runtime.account_task_store, "start_task"),
            patch.object(runtime.account_task_store, "append_event"),
            patch.object(runtime.account_task_store, "finish_task") as finish_task,
            patch.object(runtime.db, "get_account", return_value=account),
            patch("config.account.completion_settings", return_value={
                "password_enabled": False,
                "plan_check_enabled": False,
                "twofa_enabled": False,
                "codex_enabled": False,
                "refresh_at_enabled": True,
            }),
            patch.object(runtime.live_check_service, "enqueue_account_live_check", return_value=queued),
            patch.object(runtime.codex_retry_service, "release"),
        ):
            runtime._run_account_completion_worker(
                "registered@example.test",
                account_id=592,
                task_id=1000,
                task_trigger="manual_account_completion",
                planned_steps=["refresh_at"],
                settings={"refresh_at_enabled": True},
            )

        self.assertEqual("partial_success", finish_task.call_args.kwargs["status"])

    def test_password_block_does_not_prevent_twofa_completion(self):
        context = runtime.WebUIContext(Flask("test-runtime"), logging.getLogger("test-runtime"))
        account = {
            "id": 593,
            "email": "mixed@example.test",
            "access_token": "at",
            "plan_check_status": "success",
            "totp_secret": "",
            "extra_json": '{"account_password_capability":{"eligible":false}}',
            "codex_status": "success",
        }
        settings = {
            "password_enabled": True,
            "plan_check_enabled": True,
            "twofa_enabled": True,
            "codex_enabled": False,
            "refresh_at_enabled": False,
        }
        with (
            patch.object(runtime.db, "get_account", return_value=account),
            patch("core.storage.registration.get_latest_attempt_by_account", return_value=None),
            patch("config.account.completion_settings", return_value=settings),
            patch.object(runtime.codex_retry_service, "reserve", return_value=True),
            patch.object(runtime.account_task_store, "create_task", return_value=1004),
            patch.object(runtime._ACCOUNT_EXECUTOR, "submit") as submit,
        ):
            result = context.enqueue_account_completion(593)

        self.assertTrue(result["accepted"])
        self.assertEqual("password", result["plan"]["blocked"][0]["step"])
        self.assertEqual(["twofa"], result["plan"]["missing_steps"])
        submit.assert_called_once()

    def test_plan_check_failure_keeps_completed_account_steps_as_partial(self):
        with (
            patch.object(runtime.account_task_store, "start_task"),
            patch.object(runtime.account_task_store, "append_event"),
            patch.object(runtime.account_task_store, "finish_task") as finish_task,
            patch.object(
                runtime.codex_retry_service,
                "run_twofa_worker",
                return_value={
                    "status": "success",
                    "ok": True,
                    "message": "Authenticator 2FA 已启用",
                    "plan_check": {"status": "failed", "ok": False, "message": "AT 已过期"},
                },
            ),
            patch.object(runtime.codex_retry_service, "release"),
        ):
            runtime._run_account_completion_worker(
                "mixed@example.test",
                account_id=593,
                task_id=1005,
                task_trigger="manual_account_completion",
                planned_steps=["plan_check", "twofa"],
                settings={},
            )

        self.assertEqual("partial_success", finish_task.call_args.kwargs["status"])
        self.assertEqual(["plan_check"], finish_task.call_args.kwargs["result_summary"]["pending_steps"])

    def test_unsupported_account_setup_finishes_parent_as_unsupported(self):
        with (
            patch.object(runtime.account_task_store, "start_task"),
            patch.object(runtime.account_task_store, "append_event"),
            patch.object(runtime.account_task_store, "finish_task") as finish_task,
            patch.object(
                runtime.codex_retry_service,
                "run_twofa_worker",
                return_value={
                    "status": "unsupported",
                    "ok": False,
                    "message": "密码资格接口 eligible=false",
                },
            ),
            patch.object(runtime.codex_retry_service, "release"),
        ):
            runtime._run_account_completion_worker(
                "unsupported@example.test",
                account_id=591,
                task_id=1002,
                task_trigger="manual_account_completion",
                planned_steps=["password"],
                settings={},
            )

        self.assertEqual("unsupported", finish_task.call_args.kwargs["status"])
        self.assertIn("eligible=false", finish_task.call_args.kwargs["error"])

    def test_deactivated_account_setup_finishes_parent_as_deactivated(self):
        with (
            patch.object(runtime.account_task_store, "start_task"),
            patch.object(runtime.account_task_store, "append_event"),
            patch.object(runtime.account_task_store, "finish_task") as finish_task,
            patch.object(
                runtime.codex_retry_service,
                "run_twofa_worker",
                return_value={
                    "status": "deactivated",
                    "ok": False,
                    "message": "账号已废（account_deactivated）",
                    "account_status_persisted": True,
                },
            ),
            patch.object(runtime.codex_retry_service, "release"),
        ):
            runtime._run_account_completion_worker(
                "deactivated@example.test",
                account_id=591,
                task_id=1003,
                task_trigger="manual_account_completion",
                planned_steps=["password"],
                settings={},
            )

        self.assertEqual("deactivated", finish_task.call_args.kwargs["status"])
        self.assertIn("账号已废", finish_task.call_args.kwargs["message"])


if __name__ == "__main__":
    unittest.main()
