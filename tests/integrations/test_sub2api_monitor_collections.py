"""巡检集合受理在真实隔离 PostgreSQL 中保存原修复身份。"""
import importlib
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from psycopg import Cursor

from core.operations import task_gateway
from core.storage import records, sub2api
from core.storage.operations import store as operations
from tests.support_pg import PostgresTestCase
import unittest


class MonitorLoginMaterialTests(unittest.TestCase):
    def test_whitespace_extra_password_falls_back_to_saved_account_password(self):
        from core.integrations.sub2api.monitor_collections import password

        self.assertEqual(password({"extra_json": {"account_password": "  "}, "login_password": "fallback"}), "fallback")


class Sub2ApiMonitorCollectionTests(PostgresTestCase):
    def setUp(self):
        self.monitor = importlib.import_module("core.integrations.sub2api.monitor")
        sub2api.init()
        operations.reset_ready()
        operations.init()
        self.ids, self.names, self.remote = [], [], []
        for index in range(20):
            address = f"monitor-bulk-{index}@example.test"
            account_id = records.insert_row(records.ACCOUNTS, {
                "email": address, "email_source": "outlook", "codex_status": "success",
                "extra_json": {"account_password": "synthetic-login-password"},
            })
            name = f"codex-monitor-{index}.json"
            records.insert_row(records.CODEX_CREDENTIALS, {
                "filename": name, "email": address, "content": {
                    "email": address, "access_token": "synthetic-at", "refresh_token": "synthetic-rt",
                },
            })
            self.ids.append(account_id)
            self.names.append(name)
            self.remote.append({"id": index + 1, "email": address, "error_message": "401 unauthorized"})
        for context in (
            patch.object(task_gateway, "notify_dispatch"),
            patch.object(self.monitor.operation_service, "_dispatch"),
            patch.object(self.monitor.client, "configured_backend_identity", return_value="frozen-backend"),
            patch.object(self.monitor.client, "configured_monitor_group_ids", return_value=[3]),
            patch.object(self.monitor.client, "list_configured_error_accounts", side_effect=lambda **_: self.remote),
            patch.object(self.monitor.operation_service, "_config_snapshot", return_value={"oauth_driver": "protocol"}),
            patch.object(self.monitor.operation_service, "_deployment_unavailable", return_value=None),
            patch.object(self.monitor.operation_service, "_feature_ready", return_value=(True, "")),
            patch.object(self.monitor._cfg, "SUB2API_MONITOR_ENABLED", True),
            patch.object(self.monitor._cfg, "SUB2API_MONITOR_MAX_PER_CYCLE", 500),
        ):
            self.enterContext(context)

    def measured(self, callback):
        statements = []
        execute = Cursor.execute

        def record(cursor, query, *args, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, *args, **kwargs)

        with patch.object(Cursor, "execute", record):
            result = callback()
        return result, statements

    def test_scan_batches_local_reads_repairs_and_oauth_admission(self):
        with (
            patch.object(self.monitor.db, "get_account_by_email", side_effect=AssertionError("single account read")),
            patch.object(self.monitor.db, "get_account", side_effect=AssertionError("single account read")),
            patch.object(self.monitor.db, "read_codex_credential", side_effect=AssertionError("single credential read")),
            patch.object(self.monitor.operation_service, "enqueue_oauth", side_effect=AssertionError("single OAuth admission")),
        ):
            result, statements = self.measured(self.monitor._run_once)
        self.assertEqual(result["reauth_queued"], 20, result)
        self.assertEqual(result["processed"], 20)
        self.assertLess(len(statements), 60, statements)
        self.assertEqual(sum("INSERT INTO" in query and "operation_tasks" in query for query in statements), 1)
        repairs = sub2api.list_repairs("frozen-backend")
        self.assertEqual(len(repairs), 20)
        for state in repairs:
            self.assertEqual(state["stage"], "reauth_wait")
            run = operations.get_run(state["run_id"])
            self.assertEqual(run["task_type"], "codex_retry")
            self.assertEqual(run["trigger"], "sub2api_monitor")
            self.assertEqual(run["data"]["sub2api_targets"], {
                "backend_identity": "frozen-backend", "remote_account_ids": state["remote_account_ids"],
            })
            self.assertNotIn("synthetic-", str(run["data"]))
        again = self.monitor._run_once()
        self.assertEqual(again["reauth_queued"], 0)
        self.assertEqual(again["reasons"]["repair_in_progress"], 20)

    def test_sync_continuation_queues_original_targets_with_collection_writes(self):
        self.remote = []
        for index, account_id in enumerate(self.ids):
            sub2api.save_repair("frozen-backend", account_id, stage="reauth_wait",
                source_generation="old-generation", remote_account_ids=[100 + index, 200 + index])
        with (
            patch.object(self.monitor.jobs, "queue_sync", side_effect=AssertionError("single sync admission")),
            patch.object(self.monitor.db, "read_codex_credential", side_effect=AssertionError("single credential read")),
        ):
            result, statements = self.measured(lambda: self.monitor._run_once(continuation_only=True))
        self.assertEqual(result["sync_queued"], 20, result)
        self.assertLess(len(statements), 70, statements)
        jobs = sub2api.list_jobs(backend="frozen-backend")
        self.assertEqual(len(jobs), 40)
        for job in jobs:
            self.assertEqual(job["backend"], "frozen-backend")
            self.assertIn(job["remote_account_id"], {100 + self.ids.index(job["account_id"]),
                                                    200 + self.ids.index(job["account_id"])})
            self.assertGreater(job["credential_id"], 0)
        # 同账号的第二个远端目标保留为 pending；一次仅占一份账号执行资格。
        self.assertEqual(sum(job["status"] == "queued" for job in jobs), 20)
        self.assertEqual(sum(job["status"] == "pending" for job in jobs), 20)

    def test_task_failure_rolls_back_repair_stage_and_all_children(self):
        from core.storage.operations import bulk_submission

        with patch.object(bulk_submission, "create_specs", side_effect=RuntimeError("synthetic storage failure")):
            result = self.monitor._run_once()
        self.assertEqual(result["reauth_queued"], 0, result)
        self.assertIn("repair_processing_failed", result["reasons"])
        self.assertEqual(sub2api.list_repairs("frozen-backend"), [])
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operations._table('operation_tasks')}")
            self.assertEqual(cur.fetchone()["n"], 0)

    def test_cancelled_run_is_observed_before_new_generation(self):
        account_id = self.ids[0]
        task = operations.create_runtime_task(task_type="codex_retry", account_id=account_id,
            email=self.remote[0]["email"], trigger="sub2api_monitor")
        sub2api.save_repair("frozen-backend", account_id, stage="reauth_wait",
            source_generation="old-generation", remote_account_ids=[99], run_id=task["run"]["id"], task_id=task["id"])
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operations._table('operation_runs')} SET status='cancelled' WHERE id=%s",
                        (task["run"]["id"],))
            cur.execute(f"UPDATE {operations._table('operation_tasks')} SET status='cancelled' WHERE id=%s",
                        (task["id"],))
        self.remote = []
        result = self.monitor._run_once(continuation_only=True)
        self.assertEqual(result["reauth_queued"], 0)
        self.assertEqual(result["sync_queued"], 0)
        self.assertEqual(result["reasons"]["repair_cancelled"], 1)
        self.assertEqual(sub2api.list_jobs(backend="frozen-backend"), [])
        self.assertEqual(sub2api.get_repair("frozen-backend", account_id)["stage"], "waiting_manual")

    def test_other_resource_family_does_not_block_interactive_repair(self):
        operations.create_runtime_task(task_type="account_completion", account_id=self.ids[0],
            email=self.remote[0]["email"], resource_family="completion_coordinator")
        self.remote = self.remote[:1]
        result = self.monitor._run_once()
        self.assertEqual(result["reauth_queued"], 1, result)
        repair = sub2api.get_repair("frozen-backend", self.ids[0])
        self.assertEqual(operations.get_run(repair["run_id"])["resource_family"], "openai_interactive")

    def test_deactivated_sync_owner_is_not_admitted(self):
        from core.storage import sub2api_monitor

        account_id = self.ids[0]
        records.patch_row(records.ACCOUNTS, account_id, {"codex_status": "deactivated"})
        credential = records.get_row_by(records.CODEX_CREDENTIALS, "filename", self.names[0])
        sub2api.queue(self.names[0], backend="frozen-backend",
            generation=sub2api.credential_generation(credential["content"]), credential_id=credential["id"],
            account_id=account_id, email=self.remote[0]["email"], remote_account_ids=[99], trigger="sub2api_monitor")
        result = sub2api_monitor.enqueue_due_many("frozen-backend", include_retries=True)
        self.assertEqual(result["queued"], 0)
        row = sub2api.list_jobs(backend="frozen-backend")[0]
        self.assertEqual(row["error_code"], "account_deactivated")
        self.assertIsNone(row["run_id"])

    def test_busy_account_lock_does_not_wait_while_holding_sync_job(self):
        from core.storage import sub2api_monitor

        credential = records.get_row_by(records.CODEX_CREDENTIALS, "filename", self.names[0])
        sub2api.queue(self.names[0], backend="frozen-backend",
            generation=sub2api.credential_generation(credential["content"]), credential_id=credential["id"],
            account_id=self.ids[0], email=self.remote[0]["email"], remote_account_ids=[99], trigger="sub2api_monitor")
        with ThreadPoolExecutor(max_workers=1) as executor:
            with records.transaction() as conn:
                records.get_row(records.ACCOUNTS, self.ids[0], conn=conn, for_update=True)
                future = executor.submit(sub2api_monitor.enqueue_due_many, "frozen-backend", include_retries=True)
                result = future.result(timeout=3)
                self.assertEqual(result["queued"], 0)
        row = sub2api.list_jobs(backend="frozen-backend")[0]
        self.assertEqual(row["status"], "pending")
        self.assertIsNone(row["run_id"])
        self.assertEqual(sub2api_monitor.enqueue_due_many("frozen-backend", include_retries=True)["queued"], 1)
