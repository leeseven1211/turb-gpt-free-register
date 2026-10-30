# -*- coding: utf-8 -*-
import json
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from core import account_task_store
from core.accounts.liveness import service as live_check_service
from core.storage import postgres as postgres_store, records as record_store
from core.operations import run_log as task_run_log
from core.operations import task_gateway
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase
from webui import runtime


class CompletionDispatchTests(PostgresTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        log_root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(task_run_log, "_LOG_ROOT", log_root))
        self.stack.enter_context(patch.object(task_run_log, "_TASK_LOG_ROOT", log_root / "tasks"))
        self.stack.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        # 只执行本用例显式派发的父任务，子任务保持在持久队列中。
        self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        self.setup_worker = self.stack.enter_context(
            patch.object(runtime.codex_retry_service, "run_twofa_worker"),
        )
        account_task_store.init()
        operation.reset_ready()
        operation.init()
        # 注册会更新多个全局字典，测试结束后完整恢复之前的注册内容。
        for registry_name in (
            "_OPERATION_HANDLERS", "_OPERATION_HANDLER_ALLOWLISTS",
            "_OPERATION_ACTIONS", "_OPERATION_ACTION_SOURCES",
            "_DISPATCH_HANDLERS", "_DISPATCH_CAPACITY_HANDLERS",
        ):
            self.stack.enter_context(patch.dict(getattr(task_gateway, registry_name), {}))
        task_gateway.register_operation_handler(
            "account_completion",
            runtime._handle_native_account_completion,
            source_systems=("webui_runtime",),
            config_allowlist=runtime._RUNTIME_CONFIG_ALLOWLIST,
        )

    def test_coordinator_dispatches_setup_child_with_real_storage(self):
        email = "completion-dispatch@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": email,
            "access_token": "synthetic-access-token",
            "codex_status": "failed",
            "created_at": "2026-10-30T10:00:00",
            "updated_at": "2026-10-30T10:00:00",
        })
        snapshot = {
            "twofa_driver": "browser",
            "codex_driver": "browser",
            "config_snapshot_revision": 37,
        }
        queued = task_gateway.submit_durable_operation(
            task_type="account_completion",
            account_id=account_id,
            email=email,
            source_system="webui_runtime",
            source_id="completion-dispatch-parent",
            trigger="manual_account_completion",
            resource_family="completion_coordinator",
            data={"planned_steps": ["password", "twofa", "codex"]},
            config_snapshot=snapshot,
            config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST),
            dispatch=False,
        )
        self.assertTrue(queued["accepted"])

        result = task_gateway._execute_operation_handler(
            "account_completion", int(queued["run_id"]),
        )

        self.assertEqual("partial_success", result["status"])
        parent = operation.get_run(int(queued["run_id"]))
        self.assertEqual("partial_success", parent["status"])
        self.assertEqual("completion_coordinator", parent["resource_family"])
        child_id = int(parent["result_summary"]["account_setup"]["task_id"])
        child = operation.get_task(child_id, include_events=False)
        self.assertEqual("account_setup_retry", child["task_type"])
        self.assertEqual("queued", child["status"])
        child_run = operation.get_run(int(child["last_run_id"]))
        self.assertEqual("queued", child_run["status"])
        self.assertEqual("openai_interactive", child_run["resource_family"])
        self.assertEqual(["password", "twofa"], child_run["data"]["steps"])
        self.assertTrue(child_run["data"]["completion_auth"])
        self.assertEqual(parent["data"]["config_snapshot"], child_run["data"]["config_snapshot"])
        self.assertEqual("browser", child_run["data"]["config_snapshot"]["twofa_driver"])
        self.assertEqual("browser", child_run["data"]["config_snapshot"]["codex_driver"])
        self.setup_worker.assert_not_called()
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT child_source_system, child_source_id, status, payload "
                f"FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(queued["task_id"])),
            )
            dependencies = cur.fetchall()
            cur.execute(
                f"SELECT COUNT(*) FROM {postgres_store.qualified('account_operation_leases')} "
                "WHERE run_id=%s",
                (int(queued["run_id"]),),
            )
            self.assertEqual(0, cur.fetchone()[0])
        self.assertEqual(1, len(dependencies))
        child_system, child_source, status, payload = dependencies[0]
        self.assertEqual("webui_runtime", child_system)
        self.assertEqual(str(child_id), child_source)
        self.assertEqual("waiting", status)
        self.assertEqual(["codex"], payload["remaining_steps"])

        # 子任务排队期间开始注册时，实际远端操作前仍须退队等待。
        record_store.insert_row(record_store.JOBS, {
            "job_type": "registration", "status": "running",
            "account_id": account_id, "email": email,
        })
        task_gateway.register_operation_handler(
            "account_setup_retry", runtime._handle_native_account_setup,
            source_systems=("webui_runtime",),
            config_allowlist=runtime._RUNTIME_CONFIG_ALLOWLIST,
        )
        blocked = task_gateway._execute_operation_handler("account_setup_retry", int(child["last_run_id"]))
        self.assertEqual("deferred", blocked["status"])
        self.assertEqual("queued", operation.get_run(int(child["last_run_id"]))["status"])
        self.setup_worker.assert_not_called()
        operation.finish_run(int(child["last_run_id"]), status="success", result_summary={"ok": True})
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT status FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(queued["task_id"])),
            )
            self.assertEqual("ready", cur.fetchone()[0])

    def test_registration_starting_during_refresh_handoff_requeues_parent(self):
        email = "completion-race@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {"email": email, "access_token": ""})
        queued = task_gateway.submit_durable_operation(
            task_type="account_completion", account_id=account_id, email=email,
            source_system="webui_runtime", source_id="completion-refresh-race",
            trigger="manual_account_completion", resource_family="completion_coordinator",
            data={"planned_steps": ["refresh_at"]},
            config_snapshot={"refresh_at_enabled": True},
            config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST), dispatch=False,
        )
        with patch("core.accounts.completion.active_registration_job", side_effect=[None, {"id": 836, "status": "running"}]):
            result = task_gateway._execute_operation_handler("account_completion", int(queued["run_id"]))
        self.assertEqual("deferred", result["status"])
        parent = operation.get_run(int(queued["run_id"]))
        self.assertEqual("queued", parent["status"])
        self.assertFalse((parent.get("result_summary") or {}).get("awaiting_steps"))
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(queued["task_id"])),
            )
            self.assertEqual(0, cur.fetchone()[0])

    def test_setup_child_finishing_before_handoff_still_wakes_parent(self):
        email = "completion-fast@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {"email": email, "access_token": "synthetic-at"})
        parent = task_gateway.submit_durable_operation(
            task_type="account_completion", account_id=account_id, email=email,
            source_system="webui_runtime", source_id="completion-fast-parent",
            resource_family="completion_coordinator", data={"planned_steps": ["twofa"]},
            config_snapshot={}, config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST), dispatch=False,
        )
        original_submit = runtime.account_task_store.submit_durable_operation

        def fast_setup(**kwargs):
            child = original_submit(**kwargs)
            operation.finish_run(int(child["run_id"]), status="success", result_summary={"ok": True})
            return child

        with patch.object(runtime.account_task_store, "submit_durable_operation", side_effect=fast_setup):
            result = task_gateway._execute_operation_handler("account_completion", int(parent["run_id"]))
        self.assertEqual("partial_success", result["status"])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT status FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(parent["task_id"])),
            )
            self.assertEqual("ready", cur.fetchone()[0])

    def test_historical_incomplete_account_dispatches_refresh_child_with_real_storage(self):
        email = "completion-refresh@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": email,
            "access_token": "",
            "extra_json": json.dumps({
                "registration_checkpoint": "email_verification_pending",
                "account_password": "synthetic-password",
            }),
            "created_at": "2026-10-30T10:00:00",
            "updated_at": "2026-10-30T10:00:00",
        })
        settings = {
            "refresh_at_enabled": True,
            "password_enabled": False,
            "plan_check_enabled": True,
            "twofa_enabled": False,
            "codex_enabled": False,
        }
        snapshot = {**settings, "at_refresh_driver": "roxy"}
        queued = task_gateway.submit_durable_operation(
            task_type="account_completion",
            account_id=account_id,
            email=email,
            source_system="webui_runtime",
            source_id="completion-refresh-parent",
            trigger="manual_account_completion",
            resource_family="completion_coordinator",
            data={"planned_steps": ["refresh_at", "plan_check"]},
            config_snapshot=snapshot,
            config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST),
            dispatch=False,
        )
        self.assertTrue(queued["accepted"])

        with (
            patch("config.account.completion_settings", return_value=settings),
            patch.object(live_check_service, "get_config_snapshot", return_value={"ACCOUNT_AT_REFRESH_DRIVER": "roxy"}),
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_run_live_check") as remote_worker,
            patch("core.registration.service.retry_job") as registration_retry,
        ):
            result = task_gateway._execute_operation_handler(
                "account_completion", int(queued["run_id"]),
            )

        self.assertEqual("partial_success", result["status"])
        parent = operation.get_run(int(queued["run_id"]))
        self.assertEqual("partial_success", parent["status"])
        child_id = int(parent["result_summary"]["refresh_at"]["task_id"])
        child = operation.get_task(child_id, include_events=False)
        self.assertEqual("token_refresh", child["task_type"])
        self.assertEqual("queued", child["status"])
        child_run = operation.get_run(int(child["last_run_id"]))
        self.assertEqual("queued", child_run["status"])
        self.assertEqual("openai_interactive", child_run["resource_family"])
        # 用真实存储验证补全认证标记经过统一脱敏后仍保留。
        self.assertTrue(child_run["data"]["completion_auth"])
        self.assertTrue(child_run["data"]["force_refresh"])
        registration_retry.assert_not_called()
        remote_worker.assert_not_called()
        self.setup_worker.assert_not_called()

        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT child_source_system, child_source_id, status, payload "
                f"FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(queued["task_id"])),
            )
            dependencies = cur.fetchall()
        self.assertEqual(1, len(dependencies))
        child_system, child_source, status, payload = dependencies[0]
        self.assertEqual("native_operations", child_system)
        self.assertEqual(str(child_id), child_source)
        self.assertEqual("waiting", status)
        self.assertEqual(["plan_check"], payload["remaining_steps"])
        operation.finish_run(int(child["last_run_id"]), status="success", result_summary={"ok": True})
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT status FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(queued["task_id"])),
            )
            self.assertEqual("ready", cur.fetchone()[0])

        # 逐次消费真实依赖，刷新、配置、空计划收口形成完整的持久续接链。
        refresh_dependency = operation.list_ready_task_dependencies()[0]
        runtime._handle_ready_completion_dependency(operation.claim_task_dependency(refresh_dependency["id"]))
        resumed = operation.get_task(int(queued["task_id"]), include_events=False)
        setup_result = task_gateway._execute_operation_handler("account_completion", int(resumed["last_run_id"]))
        self.assertEqual("partial_success", setup_result["status"])
        setup_id = int(operation.get_run(int(resumed["last_run_id"]))["result_summary"]["account_setup"]["task_id"])
        setup = operation.get_task(setup_id, include_events=False)
        self.assertEqual(["plan_check"], operation.get_run(int(setup["last_run_id"]))["data"]["steps"])
        operation.finish_run(int(setup["last_run_id"]), status="success", result_summary={"ok": True})
        setup_dependency = operation.list_ready_task_dependencies()[0]
        runtime._handle_ready_completion_dependency(operation.claim_task_dependency(setup_dependency["id"]))
        closing = operation.get_task(int(queued["task_id"]), include_events=False)
        finished = task_gateway._execute_operation_handler("account_completion", int(closing["last_run_id"]))
        self.assertEqual("success", finished["status"])
        final_parent = operation.get_task(int(queued["task_id"]), include_events=False)
        self.assertEqual("success", final_parent["status"])
        self.assertFalse(final_parent["result_summary"].get("awaiting_steps"))
        self.assertEqual([], operation.list_ready_task_dependencies())
