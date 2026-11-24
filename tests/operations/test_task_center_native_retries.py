"""任务中心普通任务重跑按既有 handler 语义集合受理。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Event
from unittest.mock import patch

from psycopg import Cursor

from core.accounts import operation_handlers
from core.accounts.plans import service as plans
from core.accounts.liveness import service as liveness
from core.codex import operation_service as codex
from core.operations import action_service, task_gateway
from core.storage import records
from core.storage.operations import store
from tests.support_pg import PostgresTestCase


class TaskCenterNativeRetryTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        self.seed(records.ACCOUNTS, [
            {"id": index, "email": f"center-retry-{index}@example.test", "access_token": "isolated-value",
             "status": "success"} for index in range(1, 111)
        ])
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        from core import account_task_store
        self.stack.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        account_task_store.init()
        self.dispatch = self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        self.stack.enter_context(patch.object(codex, "start_dispatcher"))
        self.stack.enter_context(patch.object(liveness, "deployment_unavailable", return_value=None))
        self.stack.enter_context(patch("core.runtime.capabilities.account_setup_unavailable", return_value=None))
        self.stack.enter_context(patch("core.accounts.operation_settings.completion_deployment_unavailable", return_value=None))
        self.stack.enter_context(patch.object(codex, "_deployment_unavailable", return_value=None))
        self.stack.enter_context(patch.object(codex, "_feature_ready", return_value=(True, "")))
        plans.register_actions()
        liveness.register_actions()
        codex.register_actions()
        operation_handlers.register_actions()
        task_gateway.register_operation_actions("center_test", retry_handler=task_gateway.default_operation_retry,
            source_systems=("native_operations",))

    def tasks(self, count=100, *, kind="center_test", source="native_operations", data=None):
        with store._connect() as conn:
            receipts = []
            for index in range(1, count + 1):
                task = store.create_runtime_task(task_type=kind, account_id=index,
                    email=f"center-retry-{index}@example.test", source_system=source,
                    source_id=f"{kind}:{index}", resource_family="openai_interactive", data=data or {}, conn=conn)
                receipts.append({"task_id": task["id"], "run_id": task["run"]["id"]})
            with conn.cursor() as cur:
                cur.execute(f"""UPDATE {store._table('operation_runs')} SET status='failed',completed_at=now(),
                    data=data || '{{"remote_intent":{{"kind":"remote_write"}},"previous_only":"yes"}}'::jsonb""")
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed',completed_at=now()")
        return receipts

    def test_hundred_default_retries_have_bounded_sql_and_one_dispatch(self):
        original = self.tasks()
        statements = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, params, **kwargs)

        with patch.object(Cursor, "execute", measured):
            reply = action_service.accept_bulk_operation_action("retry", [row["task_id"] for row in original])
        print(f"任务中心 100 个普通重试 SQL：{len(statements)}")
        self.assertEqual(reply["accepted_count"], 100)
        self.assertEqual(reply["skipped_count"], 0)
        self.assertLessEqual(len(statements), 28, f"实际 SQL {len(statements)}")
        self.dispatch.assert_called_once()
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT task_id,run_no,data FROM {store._table('operation_runs')} ORDER BY task_id,run_no")
            runs = list(cur.fetchall())
        self.assertEqual(len(runs), 200)
        for old, new in zip(runs[::2], runs[1::2], strict=True):
            self.assertEqual(old["task_id"], new["task_id"])
            self.assertEqual(new["run_no"], 2)
            self.assertEqual(new["data"]["previous_only"], "yes")
            self.assertEqual(new["data"]["retry_trigger"], "manual_retry")
            self.assertNotIn("remote_intent", new["data"])
            self.assertIn("remote_intent", old["data"])

    def test_plan_retry_only_adds_missing_recovery_settings(self):
        original = self.tasks(2, kind="plan_check", data={"config_snapshot": {
            "countries": ["JP"], "plan_check_timeout": 37,
        }})
        with patch.object(plans, "get_config_snapshot", return_value={
            "auto_refresh_at_enabled": True, "refresh_at_driver": "protocol_v3", "countries": ["US"],
        }), patch.object(task_gateway, "normalize_config_snapshot", side_effect=lambda values, **_: values):
            reply = action_service.accept_bulk_operation_action("retry", [row["task_id"] for row in original])
        self.assertEqual(reply["accepted_count"], 2)
        for row in original:
            task = store.get_task(row["task_id"], include_events=False)
            run = store.get_run(task["last_run_id"])
            self.assertEqual(run["data"]["config_snapshot"]["countries"], ["JP"])
            self.assertEqual(run["data"]["config_snapshot"]["plan_check_timeout"], 37)
            self.assertTrue(run["data"]["config_snapshot"]["auto_refresh_at_enabled"])

    def test_refresh_retry_uses_current_snapshot_and_keeps_old_run(self):
        original = self.tasks(2, kind="token_refresh", data={
            "force_refresh": True, "config_snapshot": {"refresh_at_driver": "protocol_v2"},
        })
        with patch.object(liveness, "get_config_snapshot", return_value={
                "refresh_at_driver": "protocol_v3", "refresh_at_proxy_mode": "pool",
            }), patch.object(liveness, "_resolve_refresh_driver", return_value="protocol_v3"), \
                patch.object(task_gateway, "normalize_config_snapshot", side_effect=lambda values, **_: values):
            reply = action_service.accept_bulk_operation_action("retry", [row["task_id"] for row in original])
        self.assertEqual(reply["accepted_count"], 2)
        for row in original:
            task = store.get_task(row["task_id"], include_events=False)
            run = store.get_run(task["last_run_id"])
            self.assertEqual(run["data"]["refresh_driver"], "v3")
            self.assertEqual(run["data"]["proxy_source"], "pool")
            self.assertEqual(store.get_run(row["run_id"])["data"]["config_snapshot"]["refresh_at_driver"], "protocol_v2")

    def test_mixed_invalid_active_and_deactivated_keep_order(self):
        original = self.tasks(3)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='running' WHERE id=%s",
                (original[1]["task_id"],))
            records.patch_row(records.ACCOUNTS, 3, changes={"account_status": "deactivated"}, conn=conn)
        ids = [999999, original[2]["task_id"], original[0]["task_id"], original[1]["task_id"]]
        reply = action_service.accept_bulk_operation_action("retry", ids)
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [original[0]["task_id"]])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [999999, original[2]["task_id"], original[1]["task_id"]])
        self.assertEqual(store.get_task(original[2]["task_id"], include_events=False)["last_run_id"], original[2]["run_id"])

    def test_codex_hundred_uses_one_snapshot_and_account_projection(self):
        original = self.tasks(kind="codex_retry", data={"config_snapshot": {"codex_driver": "protocol"}})
        statements = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, params, **kwargs)

        with patch.object(codex, "_config_snapshot", return_value={"codex_driver": "roxy"}) as snapshot, \
                patch.object(Cursor, "execute", measured):
            reply = action_service.accept_bulk_operation_action("retry", [row["task_id"] for row in original])
        self.assertEqual(reply["accepted_count"], 100)
        self.assertLessEqual(len(statements), 30)
        snapshot.assert_called_once_with(driver_override=None)
        self.dispatch.assert_called_once()
        for index in (1, 100):
            account = records.get_row(records.ACCOUNTS, index)
            self.assertEqual(account["codex_execution_status"], "queued")
            self.assertEqual(store.get_run(account["codex_active_run_id"])["data"]["config_snapshot"]["codex_driver"], "roxy")

    def test_runtime_setup_deployment_failure_does_not_create_run(self):
        original = self.tasks(3, kind="password_change", source="webui_runtime",
            data={"steps": ["password"], "config_snapshot": {"password_driver": "roxy"}})
        unavailable = {"accepted": False, "unavailable": True, "error": "当前部署不提供浏览器"}
        with patch("core.runtime.capabilities.account_setup_unavailable", return_value=unavailable) as check:
            reply = action_service.accept_bulk_operation_action("retry", [row["task_id"] for row in original])
        self.assertEqual(reply["accepted_count"], 0)
        self.assertEqual(reply["skipped_count"], 3)
        check.assert_called_once()
        self.assertTrue(check.call_args.kwargs["force_password_reset"])
        self.dispatch.assert_not_called()
        for item in original:
            self.assertEqual(store.get_task(item["task_id"], include_events=False)["last_run_id"], item["run_id"])

    def test_registration_wrapper_preflight_reads_sources_in_one_collection(self):
        from core.registration import service as registration
        source_id = records.insert_row(records.JOBS, {"email": "wrapper-source@example.test",
            "status": "failed", "config_snapshot": {"registration_mode": "recorded"}})
        original = self.tasks(3, kind="registration_resume", source="webui_runtime",
            data={"source_job_id": source_id})
        with patch.object(registration, "registration_options_for_job",
                return_value={"driver": "recorded"}) as options, \
                patch.object(registration, "registration_deployment_unavailable", return_value=None) as deployment, \
                patch.object(action_service.db, "get_job", side_effect=AssertionError("禁止逐项读注册来源")):
            reply = action_service.accept_bulk_operation_action("retry", [row["task_id"] for row in original])
        self.assertEqual(reply["accepted_count"], 3)
        options.assert_called_once()
        self.assertEqual(options.call_args.args[0]["id"], source_id)
        deployment.assert_called_once_with({"driver": "recorded"})

    def test_child_retry_does_not_hold_account_while_waiting_for_parent_claim(self):
        parent = store.create_runtime_task(task_type="account_completion", account_id=1,
            email="center-retry-1@example.test", resource_family="completion_coordinator")
        child = store.create_runtime_task(task_type="center_test", account_id=1,
            email="center-retry-1@example.test", parent_task_id=parent["id"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s",
                (child["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s", (child["id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='queued' WHERE id=%s",
                (parent["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='queued' WHERE id=%s", (parent["id"],))
        run_locked, retry_reached_account, release_claim = Event(), Event(), Event()
        execute = Cursor.execute

        def observed(cursor, query, params=None, **kwargs):
            text = str(query)
            result = execute(cursor, query, params, **kwargs)
            if ("operation_runs" in text and "status='queued'" in text and "FOR UPDATE" in text
                    and params == (parent["run"]["id"],)):
                run_locked.set()
                if not release_claim.wait(10):
                    raise RuntimeError("父认领等待超时")
            if ("registered_accounts" in text and "SELECT" in text
                    and params == ([1],)):
                retry_reached_account.set()
            return result

        with patch.object(Cursor, "execute", observed), ThreadPoolExecutor(max_workers=2) as pool:
            claim = pool.submit(store.claim_run, parent["run"]["id"], execution_id="parent-account-race", worker_pid=1)
            try:
                self.assertTrue(run_locked.wait(10))
                retry = pool.submit(action_service.accept_bulk_operation_action, "retry", [child["id"]])
                self.assertTrue(retry_reached_account.wait(10))
            finally:
                release_claim.set()
            self.assertEqual(claim.result(timeout=15)["status"], "running")
            reply = retry.result(timeout=15)
        self.assertEqual(reply["accepted_count"], 1)
        self.assertEqual(store.get_task(parent["id"], include_events=False)["status"], "waiting")
