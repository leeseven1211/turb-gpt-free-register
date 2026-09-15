# -*- coding: utf-8 -*-
import logging
import unittest
from contextlib import ExitStack
from types import MappingProxyType
from unittest.mock import patch

from flask import Flask

from webui import runtime


class WebUIRuntimeTests(unittest.TestCase):
    def setUp(self):
        runtime._runtime_started = False
        runtime._runtime_started_at = None
        runtime._RUNTIME_HANDLERS_REGISTERED = False

    def tearDown(self):
        runtime._runtime_started = False
        runtime._runtime_started_at = None
        runtime._RUNTIME_HANDLERS_REGISTERED = False

    def test_start_runtime_recovers_and_starts_periodic_workers_once(self):
        with ExitStack() as stack:
            recover_jobs = stack.enter_context(
                patch.object(runtime.db, "recover_interrupted_registration_jobs", return_value=2)
            )
            recover_accounts = stack.enter_context(
                patch.object(runtime.account_task_store, "recover_interrupted", return_value=1)
            )
            init_operations = stack.enter_context(patch.object(runtime.operation_task_store, "init"))
            start_projection = stack.enter_context(
                patch.object(runtime.operation_task_store, "start_projection_worker")
            )
            recover_operations = stack.enter_context(
                patch.object(runtime.operation_task_store, "recover_interrupted_runtime_runs", return_value=3)
            )
            repair_compatibility = stack.enter_context(
                patch.object(runtime.operation_task_store, "repair_stale_compatibility_projections", return_value=2)
            )
            recovery_exclusions = stack.enter_context(
                patch.object(
                    runtime.operation_task_store,
                    "list_active_runtime_recovery_exclusions",
                    return_value={"account_ids": [], "source_ids": []},
                )
            )
            start_dispatcher = stack.enter_context(
                patch.object(runtime.account_task_store, "start_dispatcher")
            )
            register_handlers = stack.enter_context(patch.object(runtime, "_register_runtime_handlers"))
            cleanup_roxy = stack.enter_context(
                patch("core.roxybrowser_client.cleanup_orphaned_profiles", return_value={"found": 0})
            )
            start_sms = stack.enter_context(patch.object(runtime.sms_provider, "start_cancel_worker"))
            recover_plans = stack.enter_context(
                patch.object(runtime.db, "recover_interrupted_plan_checks", return_value=4)
            )
            recover_links = stack.enter_context(
                patch.object(runtime.db, "recover_interrupted_extract_links", return_value=5)
            )
            recover_live = stack.enter_context(
                patch.object(runtime.db, "recover_interrupted_live_checks", return_value=6)
            )
            backfill_proxy = stack.enter_context(
                patch.object(runtime.db, "backfill_account_registration_proxy_context", return_value=7)
            )
            resume_codex = stack.enter_context(
                patch.object(runtime.codex_operation_service, "resume_queued", return_value=8)
            )
            set_dependency_handler = stack.enter_context(
                patch.object(runtime.account_task_store, "set_dependency_ready_handler")
            )
            start_dependency_dispatcher = stack.enter_context(
                patch.object(runtime.account_task_store, "start_dependency_dispatcher")
            )
            drain_dependencies = stack.enter_context(
                patch.object(runtime.account_task_store, "drain_ready_dependencies", return_value=0)
            )
            start_risk_scan = stack.enter_context(
                patch("core.deactivation_mail_service.start_periodic_scanner")
            )
            start_at_refresh = stack.enter_context(
                patch("core.token_refresh_service.start_periodic_refresher")
            )
            start_codex_refresh = stack.enter_context(
                patch("core.codex_token_refresh_service.start_periodic_refresher")
            )
            start_auth_context_cleanup = stack.enter_context(
                patch("core.account_auth_context_service.start_periodic_cleanup")
            )
            self.assertTrue(runtime.start_runtime(logging.getLogger("test-webui-runtime")))
            self.assertFalse(runtime.start_runtime(logging.getLogger("test-webui-runtime")))

        for mock in (
            recover_jobs,
            recover_accounts,
            start_projection,
            recover_operations,
            repair_compatibility,
            start_dispatcher,
            register_handlers,
            cleanup_roxy,
            start_sms,
            recover_plans,
            recover_links,
            recover_live,
            backfill_proxy,
            resume_codex,
            set_dependency_handler,
            start_dependency_dispatcher,
            drain_dependencies,
            start_risk_scan,
            start_at_refresh,
            start_codex_refresh,
            start_auth_context_cleanup,
        ):
            self.assertEqual(1, mock.call_count, getattr(mock, "_mock_name", "mock"))
        self.assertEqual(5, recovery_exclusions.call_count)
        self.assertGreaterEqual(init_operations.call_count, 1)

    def test_runtime_status_is_read_only_and_contains_release_health_components(self):
        runtime._runtime_started = True
        runtime._runtime_started_at = 123.0
        with (
            patch.object(runtime._ACCOUNT_EXECUTOR, "status", return_value={"available": 2}),
            patch.object(runtime.codex_operation_service, "dispatcher_status", return_value={"alive": True}),
            patch.object(runtime.account_task_store, "dependency_dispatcher_status", return_value={"alive": True}),
            patch.object(runtime.operation_task_store, "projection_worker_status", return_value={"alive": True}),
        ):
            status = runtime.runtime_status()

        self.assertTrue(status["ready"])
        self.assertEqual(123.0, status["started_at"])
        self.assertEqual({"available": 2}, status["executor"])
        self.assertEqual({"alive": True}, status["dependency_dispatcher"])
        self.assertNotIn("email", status)

    def test_runtime_consumes_c_snapshot_uppercase_values_with_revision(self):
        class ConfigSnapshot:
            __slots__ = ("revision", "values", "sources")

            def __init__(self):
                self.revision = 77
                self.values = MappingProxyType({
                    "ACCOUNT_COMPLETION_PASSWORD_ENABLED": False,
                    "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED": True,
                    "ACCOUNT_COMPLETION_2FA_ENABLED": False,
                    "ACCOUNT_COMPLETION_CODEX_ENABLED": False,
                    "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED": False,
                    "ACCOUNT_PASSWORD_RESET_ENABLED": False,
                    "ACCOUNT_PASSWORD_DRIVER": "roxy",
                    "ACCOUNT_PLAN_CHECK_DRIVER": "protocol",
                    "ACCOUNT_2FA_DRIVER": "protocol",
                    "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED": False,
                    "ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED": True,
                    "ACCOUNT_CODEX_DRIVER": "same_as_registration",
                    "OPENAI_PROTOCOL_VERSION": "v2",
                    "UNRELATED_SECRET_LIKE_KEY": "not-persisted",
                })
                self.sources = MappingProxyType({"ACCOUNT_PASSWORD_DRIVER": "test"})

        fallback = {
            "password_enabled": True,
            "plan_check_enabled": False,
            "twofa_enabled": True,
            "codex_enabled": True,
            "refresh_at_enabled": True,
        }
        snapshot = ConfigSnapshot()
        with (
            patch.object(runtime, "_runtime_config_snapshot", return_value=snapshot),
            patch("config.account.completion_settings", return_value=fallback),
        ):
            captured, allowlist, settings = runtime._runtime_execution_settings(fallback)

        self.assertIs(snapshot, captured)
        self.assertEqual(77, snapshot.revision)
        self.assertEqual(False, settings["password_enabled"])
        self.assertEqual(True, settings["plan_check_enabled"])
        self.assertEqual("v2", settings["protocol_version"])
        self.assertEqual("ACCOUNT_COMPLETION_PASSWORD_ENABLED", allowlist["password_enabled"])
        projected = runtime.task_gateway.normalize_config_snapshot(
            captured, allowlist=allowlist,
        )
        self.assertEqual(77, projected["config_snapshot_revision"])
        self.assertNotIn("UNRELATED_SECRET_LIKE_KEY", projected)
        self.assertNotIn("sources", projected)

    def test_native_account_setup_records_remote_intent_and_requires_local_proof(self):
        class FakeContext:
            run = {
                "data": {
                    "steps": ["password"],
                    "task_trigger": "test-account-setup",
                },
                "trigger": "test-account-setup",
                "log_file": "",
            }
            run_id = 71
            task_id = 81
            account_id = 91
            email = "setup@example.test"
            config_snapshot = {
                "password_driver": "roxy",
                "plan_check_driver": "protocol",
                "twofa_driver": "protocol",
            }

            def __init__(self):
                self.finished = False
                self.last_result = None
                self.receipts = []

            def report(self, **_kwargs):
                return {}

            def lease(self, **_kwargs):
                class LeaseContext:
                    def __enter__(self_inner):
                        return self_inner

                    def __exit__(self_inner, _exc_type, _exc, _tb):
                        return False

                return LeaseContext()

            def remote_request_started(self, *args, **kwargs):
                self.started = (args, kwargs)
                return {}

            def remote_request_receipt(self, **kwargs):
                self.receipts.append(kwargs)
                return {}

            def finish(self, result):
                self.finished = True
                self.last_result = result
                return result.as_dict()

        context = FakeContext()
        with (
            patch.object(
                runtime.codex_retry_service,
                "run_twofa_worker",
                return_value={"status": "success", "ok": True, "message": "submitted"},
            ) as worker,
            patch.object(
                runtime,
                "_account_setup_receipt",
                return_value=(
                    "local_commit_required",
                    {
                        "remote_response_received": True,
                        "remote_result_confirmed": True,
                        "local_business_writeback_confirmed": False,
                        "local_readback_confirmed": False,
                        "local_readback_checks": {"password": False},
                    },
                ),
            ),
        ):
            result = runtime._handle_native_account_setup(context)

        self.assertTrue(context.finished)
        self.assertIsNotNone(result)
        self.assertEqual("request_unknown", result.status)
        self.assertEqual("account_setup", context.started[0][0])
        self.assertEqual("remote_write", context.started[1]["intent_kind"])
        self.assertEqual("local_commit_required", context.receipts[0]["outcome"])
        self.assertEqual(0, worker.call_args.kwargs["task_id"])
        self.assertFalse(worker.call_args.kwargs["manage_task"])

    def test_completion_dependency_worker_uses_scanner_claim_without_reclaiming(self):
        dependency = {
            "id": 301,
            "parent_source_system": "webui_runtime",
            "parent_source_id": "401",
            "child_source_system": "live_check_service",
            "child_source_id": "child-1",
            "child_status": "success",
            "payload": {
                "remaining_steps": ["password"],
                "settings": {"password_enabled": True},
                "result_summary": {"awaiting_steps": ["refresh_at"]},
            },
        }
        with (
            patch.object(
                runtime.operation_task_store,
                "get_task",
                return_value={"id": 401, "status": "partial_success"},
            ),
            patch.object(
                runtime.operation_task_store,
                "retry_runtime_task",
                return_value={"id": 402},
            ) as retry,
            patch.object(runtime.operation_task_store, "complete_task_dependency") as complete,
            patch.object(runtime.operation_task_store, "claim_task_dependency") as claim,
            patch.object(runtime.task_gateway, "notify_dispatch") as notify,
        ):
            runtime._handle_ready_completion_dependency(dependency)

        claim.assert_not_called()
        retry.assert_called_once()
        self.assertEqual(401, retry.call_args.args[0])
        self.assertEqual("dependency_resume", retry.call_args.kwargs["trigger"])
        complete.assert_called_once_with(301, success=True)
        notify.assert_called_once()

    def test_completion_setup_is_a_durable_child_before_parent_partial(self):
        class FakeContext:
            run = {
                "data": {},
                "trigger": "manual_account_completion",
                "log_file": "",
            }
            run_id = 711
            task_id = 712
            account_id = 713
            email = "completion@example.test"
            config_snapshot = {
                "password_driver": "roxy",
                "twofa_driver": "protocol",
                "config_snapshot_revision": 19,
            }

            def __init__(self):
                self.finished = False
                self.last_result = None
                self.released = 0

            def report(self, **_kwargs):
                return {}

            def release_lease(self):
                self.released += 1
                return True

            def finish(self, result):
                self.finished = True
                self.last_result = result
                return result.as_dict()

        context = FakeContext()
        with (
            patch.object(
                runtime.account_task_store,
                "submit_durable_operation",
                return_value={
                    "accepted": True,
                    "busy": False,
                    "task_id": 714,
                    "run_id": 715,
                    "source_system": "webui_runtime",
                    "source_id": "account-completion-setup:712:711",
                },
            ) as submit,
            patch.object(runtime.operation_task_store, "register_task_dependency") as register,
            patch.object(runtime.codex_retry_service, "run_twofa_worker") as setup_worker,
        ):
            result = runtime._run_account_completion_worker(
                context.email,
                account_id=context.account_id,
                task_id=context.task_id,
                task_trigger="manual_account_completion",
                planned_steps=["password", "codex"],
                settings={"password_driver": "roxy"},
                context=context,
                reservation_held=False,
            )

        self.assertTrue(context.finished)
        self.assertEqual("partial_success", result.status)
        setup_worker.assert_not_called()
        submit.assert_called_once()
        self.assertEqual("account_setup_retry", submit.call_args.kwargs["task_type"])
        self.assertEqual(["password"], submit.call_args.kwargs["data"]["steps"])
        register.assert_called_once()
        self.assertEqual("webui_runtime", register.call_args.kwargs["child_source_system"])
        self.assertEqual(
            "account-completion-setup:712:711",
            register.call_args.kwargs["child_source_id"],
        )
        self.assertEqual(["codex"], register.call_args.kwargs["payload"]["remaining_steps"])
        self.assertGreaterEqual(context.released, 1)

    def test_legacy_recovery_is_skipped_when_durable_run_is_active(self):
        with patch.object(
            runtime.operation_task_store,
            "list_active_runtime_recovery_exclusions",
            return_value={"account_ids": [591], "source_ids": []},
        ) as recovery_exclusions:
            self.assertFalse(runtime._legacy_recovery_allowed({"live_check", "token_refresh"}))

        recovery_exclusions.assert_called_once_with(
            task_types=("live_check", "token_refresh"),
        )

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
            patch.object(
                runtime.account_task_store,
                "submit_durable_operation",
                return_value={
                    "accepted": True,
                    "busy": False,
                    "reused": False,
                    "task_id": 901,
                    "run_id": 902,
                    "source_system": "webui_runtime",
                    "source_id": "registration-resume:591:836",
                    "status": "queued",
                },
            ) as submit,
            patch("core.registration_service.retry_job") as retry_job,
        ):
            result = context.enqueue_account_completion(591)

        self.assertTrue(result["accepted"])
        self.assertTrue(result["registration_resume"])
        self.assertEqual(836, result["job_id"])
        retry_job.assert_not_called()
        submit.assert_called_once()
        self.assertEqual("registration_resume", submit.call_args.kwargs["task_type"])
        self.assertEqual(836, submit.call_args.kwargs["data"]["source_job_id"])

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

    def test_ready_dependency_submission_uses_shared_budget_without_claiming(self):
        dependency = {"id": 901, "status": "running", "payload": {}}
        with (
            patch.object(runtime._ACCOUNT_EXECUTOR, "try_submit", return_value=object()) as submit,
            patch.object(runtime.operation_task_store, "claim_task_dependency") as claim,
        ):
            result = runtime._submit_ready_completion_dependency(dependency)

        self.assertIsNotNone(result)
        claim.assert_not_called()
        submit.assert_called_once_with(runtime._handle_ready_completion_dependency, dependency)

    def test_busy_ready_dependency_returns_to_durable_queue_without_timer(self):
        dependency = {"id": 902, "status": "running", "payload": {}}
        with (
            patch.object(runtime._ACCOUNT_EXECUTOR, "try_submit", return_value=None),
            patch.object(runtime.operation_task_store, "complete_task_dependency", return_value=True) as complete,
            patch.object(runtime.account_task_store, "notify_dependency_ready") as notify,
        ):
            self.assertIsNone(runtime._submit_ready_completion_dependency(dependency))

        complete.assert_called_once_with(
            902,
            success=False,
            error="账号操作共享并发预算已满",
        )
        notify.assert_called_once_with(dependency)

    def test_stale_password_capability_does_not_block_completion(self):
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
            patch.object(
                runtime.account_task_store,
                "submit_durable_operation",
                return_value={
                    "accepted": True,
                    "busy": False,
                    "reused": False,
                    "task_id": 1004,
                    "run_id": 1005,
                    "status": "queued",
                },
            ) as submit,
        ):
            result = context.enqueue_account_completion(593)

        self.assertTrue(result["accepted"])
        self.assertFalse(result["plan"]["blocked"])
        self.assertEqual(["password", "twofa"], result["plan"]["missing_steps"])
        submit.assert_called_once()
        self.assertEqual("account_completion", submit.call_args.kwargs["task_type"])
        self.assertEqual(
            ["password", "twofa"],
            submit.call_args.kwargs["data"]["planned_steps"],
        )

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
