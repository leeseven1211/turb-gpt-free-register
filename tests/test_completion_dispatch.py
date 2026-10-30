# -*- coding: utf-8 -*-
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from core import account_task_store, postgres_store, record_store, task_run_log
from core.operations import task_gateway
from core.storage import operation
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
        self.assertEqual(child["source_id"], child_source)
        self.assertEqual("waiting", status)
        self.assertEqual(["codex"], payload["remaining_steps"])
