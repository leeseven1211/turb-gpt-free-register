from __future__ import annotations

import json
import os
from unittest.mock import patch

from core import account_task_store, db, extract_link_service, record_store
from core.storage import extract_link_jobs, operation
from tests.support_pg import PostgresTestCase


class ExtractWorkbenchQueryTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._previous_operation_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        cls._account_schema_patch = patch.object(account_task_store, "_SCHEMA", cls.schema)
        cls._account_ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        cls._account_schema_patch.start()
        cls._account_ready_patch.start()
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        try:
            operation.reset_ready()
            if cls._previous_operation_schema is None:
                os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
            else:
                os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._previous_operation_schema
        finally:
            cls._account_ready_patch.stop()
            cls._account_schema_patch.stop()
            super().tearDownClass()

    def setUp(self):
        operation.init()

    def task(self, *, status="queued", provider="lumen_flow", mode="extract_only", state=None,
             summary=None, account_id=None, email="fixture@example.test", task_type="extract_link", batch_id=None):
        task = operation.create_runtime_task(
            task_type=task_type, account_id=account_id, email=email, trigger="test",
            batch_id=batch_id, data={"provider_id": provider, "mode": mode},
        )
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status=%s WHERE id=%s", (status, task["id"]))
            cur.execute(
                f"UPDATE {operation._table('operation_runs')} SET status=%s, result_summary=%s::jsonb WHERE id=%s",
                (status, json.dumps(summary or {}), task["run"]["id"]),
            )
        if state is not None:
            extract_link_jobs.save_provider_job(task["run"]["id"], provider, "synthetic-job", state, {"secret": "private-marker"})
        return task

    def test_page_projects_only_selected_accounts_and_keeps_unfiltered_counts(self):
        tasks = [self.task(status=status) for status in ("queued", "running", "settling", "waiting", "success")]
        with patch.object(db, "get_accounts_for_jobs", wraps=db.get_accounts_for_jobs) as project_accounts:
            result = extract_link_service.list_workbench_tasks(status="running", page=2, page_size=1)
        self.assertEqual(2, result["total"])
        self.assertEqual(5, result["counts"]["all"])
        self.assertEqual(4, result["counts"]["processing"])
        self.assertEqual(2, result["counts"]["running"])
        self.assertEqual([tasks[1]["id"]], [item["task_id"] for item in result["items"]])
        self.assertEqual(1, len(project_accounts.call_args.args[0]))
        empty = extract_link_service.list_workbench_tasks(status="running", page=20, page_size=1)
        self.assertEqual(2, empty["total"])
        self.assertEqual([], empty["items"])
        self.assertEqual(result["counts"], empty["counts"])

    def test_sql_filters_preserve_independent_payment_plus_and_legacy_states(self):
        plus_account, free_account = self.seed(record_store.ACCOUNTS, [
            {"email": "plus@example.test", "plan_check_status": "success", "current_plan_type": "plus"},
            {"email": "free@example.test", "plan_check_status": "success", "current_plan_type": "free"},
        ])
        legacy = self.task(provider="legacy", status="success", summary={"has_link": True, "remote_job_id": "old-job"})
        paid_plus = self.task(status="success", mode="manual_payment", account_id=plus_account, state={
            "extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "pending",
        })
        paid_free = self.task(status="success", mode="auto_payment", account_id=free_account, state={
            "extraction_state": "failed", "payment_state": "paid", "plus_status": "unknown",
        })
        pending = self.task(status="attention_required", mode="auto_payment", state={
            "extraction_state": "unknown", "payment_state": "unknown", "plus_status": "pending",
        })
        extract_only = self.task(status="success", state={
            "extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "confirmed",
        })
        expected = {
            "processing": {pending["id"]},
            "running": set(),
            "extraction_succeeded": {legacy["id"], paid_plus["id"], extract_only["id"]},
            "payment_succeeded": {paid_plus["id"], paid_free["id"]},
            "plus_confirmed": {paid_plus["id"], extract_only["id"]},
            "needs_attention": {legacy["id"], paid_free["id"], pending["id"]},
        }
        for status, ids in expected.items():
            with self.subTest(status=status):
                result = extract_link_service.list_workbench_tasks(status=status)
                self.assertEqual(ids, {item["task_id"] for item in result["items"]})
                self.assertEqual(len(ids), result["total"])
                self.assertEqual(len(ids), result["counts"][status])
                self.assertEqual(5, result["counts"]["all"])

    def test_plus_filter_falls_back_to_email_and_preserves_matching_legacy_link(self):
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": "history@example.test", "plan_check_status": "success", "plan_type": "free",
            "has_active_subscription": True, "extract_link_job_id": "old-job",
            "extract_link_long_url": "https://example.test/old-link",
        }])[0]
        task = self.task(provider="legacy", mode="manual_payment", status="success", email=" HISTORY@example.test ",
                         summary={"remote_job_id": "old-job", "payment_status": "succeeded", "plus_status": "pending"})
        result = extract_link_service.list_workbench_tasks(status="plus_confirmed")
        self.assertEqual(1, result["total"])
        self.assertEqual(task["id"], result["items"][0]["task_id"])
        self.assertTrue(result["items"][0]["has_extract_link"])
        detail = extract_link_service.extract_workbench_task_detail(task["id"])
        self.assertEqual("confirmed", detail["item"]["plus_status"])
        self.assertTrue(detail["item"]["has_extract_link"])
        self.assertNotIn("old-link", repr(detail))
        self.assertGreater(account_id, 0)

    def test_base_filters_and_hidden_tasks_keep_empty_page_counts(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="测试批次", requested_count=2)
        target = self.task(provider="huanguang", mode="manual_payment", email="target@example.test", batch_id=batch["id"])
        self.task(provider="huanguang", mode="extract_only", email="target@example.test")
        hidden = self.task(provider="huanguang", mode="manual_payment", email="target@example.test", batch_id=batch["id"])
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET data=data || %s::jsonb WHERE id=%s", ('{"deleted_by_user":true}', hidden["id"]))
        result = extract_link_service.list_workbench_tasks(provider_id="huanguang", mode="manual_payment", query="target@", batch_id=batch["id"], page=2, page_size=1)
        self.assertEqual(1, result["total"])
        self.assertEqual(1, result["counts"]["all"])
        self.assertEqual([], result["items"])
        self.assertIsNone(extract_link_service.extract_workbench_task_detail(hidden["id"]))
        self.assertIsNotNone(extract_link_service.extract_workbench_task_detail(target["id"]))
        self.assertEqual(0, extract_link_service.list_workbench_tasks(status="not-a-status")["total"])

    def test_detail_bounds_events_and_joins_run_history_without_full_task_hydration(self):
        task = self.task(status="failed", state={"extraction_state": "failed"})
        first_run = task["run"]["id"]
        second = operation.retry_runtime_task(task["id"])
        second_run = second["id"]
        extract_link_jobs.save_provider_job(second_run, "huanguang", "second-job", {"extraction_state": "succeeded", "payment_state": "pending"}, {"secret": "private-marker"})
        other = self.task(task_type="check_plan")
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {operation._table('operation_events')} WHERE task_id=%s", (task["id"],))
            cur.execute(
                f"""INSERT INTO {operation._table('operation_events')}
                    (event_uuid, task_id, run_id, source_system, source_id, stage, message, created_at)
                    SELECT 'event-' || n, %s, %s, 'test', 'event-' || n, 'extract', '事件 ' || n,
                        '2026-01-01'::timestamptz + n * interval '1 second'
                    FROM generate_series(1, 205) n""", (task["id"], second_run),
            )
        with (
            patch.object(operation, "get_task", side_effect=AssertionError("详情不得读取通用完整任务")),
            patch.object(extract_link_jobs, "list_workbench_rows", side_effect=AssertionError("详情不得扫描工作台全量任务")),
            patch.object(extract_link_jobs, "get_provider_job_public", side_effect=AssertionError("详情不得逐 Run 查询 Provider")),
        ):
            detail = extract_link_service.extract_workbench_task_detail(task["id"])
        self.assertEqual([first_run, second_run], [run["run_id"] for run in detail["history"]])
        self.assertEqual("huanguang", detail["history"][-1]["provider_id"])
        self.assertEqual("succeeded", detail["history"][-1]["extraction_status"])
        self.assertEqual(200, len(detail["events"]))
        self.assertEqual("事件 6", detail["events"][0]["message"])
        self.assertEqual("事件 205", detail["events"][-1]["message"])
        self.assertEqual(2, detail["item"]["run_count"])
        self.assertNotIn("private-marker", repr(detail))
        self.assertIsNone(extract_link_service.extract_workbench_task_detail(999999))
        self.assertIsNone(extract_link_service.extract_workbench_task_detail(other["id"]))

    def test_workbench_row_exposes_provider_update_timestamp(self):
        task = self.task(state={"extraction_state": "running"})
        rows = extract_link_jobs.list_workbench_rows()
        self.assertEqual(task["id"], rows[0]["task_id"])
        self.assertTrue(rows[0].get("job_updated_at"))

    def test_detail_history_keeps_legacy_source_status_and_timestamps(self):
        legacy_id = account_task_store.create_task(task_type="extract_link", account_id=None,
                                                  email="legacy@example.test", trigger="test")
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {operation._table('operation_tasks')} WHERE source_system='account_action_tasks' AND source_id=%s", (str(legacy_id),))
            task_id = cur.fetchone()["id"]
            cur.execute(
                f"UPDATE {operation._table('account_action_tasks')} SET status='failed', queued_at=%s, finished_at=%s, error='历史失败' WHERE id=%s",
                ("2026-09-08T02:05:46+00:00", "2026-09-08T02:06:46+00:00", legacy_id),
            )
        detail = extract_link_service.extract_workbench_task_detail(task_id)
        self.assertEqual("failed", detail["history"][0]["status"])
        self.assertEqual("2026-09-08T02:05:46+00:00", detail["history"][0]["created_at"])
        self.assertEqual("2026-09-08T02:06:46+00:00", detail["history"][0]["completed_at"])
        self.assertEqual("历史失败", detail["history"][0]["message"])

    def test_email_fallback_aggregates_only_missing_accounts_in_filtered_tasks(self):
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": "selected@example.test", "plan_check_status": "success", "current_plan_type": "plus",
        }])[0]
        task = self.task(account_id=account_id, email="selected@example.test", mode="manual_payment", state={
            "extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "pending",
        })
        self.task(provider="huanguang", email="unrelated-1@example.test")
        accounts = record_store._qualified(record_store.ACCOUNTS)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {accounts} (email, created_at, updated_at, data)
                    SELECT 'unrelated-' || n || '@example.test', '', '', '{{}}'::jsonb
                    FROM generate_series(1, 1000) n""",
            )
            cur.execute(f"ANALYZE {accounts}")

        def fallback_plan_counts():
            clauses, params = extract_link_jobs._workbench_where(provider_id="lumen_flow")
            projection = extract_link_jobs._workbench_projection_sql(clauses)
            with operation._connect() as conn, conn.cursor() as cur:
                cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) WITH {projection} SELECT COUNT(*) FILTER (WHERE plus_status='confirmed') FROM projected", tuple(params))
                plan = cur.fetchone()["QUERY PLAN"][0]["Plan"]
            def walk(node):
                yield node
                for child in node.get("Plans", []):
                    yield from walk(child)
            nodes = list(walk(plan))
            groups = sum(int(node.get("Actual Rows", 0)) * int(node.get("Actual Loops", 0))
                         for node in nodes
                         if any("lower(" in key.lower() and "email" in key.lower() and "email_snapshot" not in key.lower()
                                for key in node.get("Group Key", [])))
            scanned = sum((int(node.get("Actual Rows", 0)) + int(node.get("Rows Removed by Filter", 0)))
                          * int(node.get("Actual Loops", 0)) for node in nodes if node.get("Alias") == "fallback_account")
            return groups, scanned

        # 所选任务都有可关联的 account_id 时，不应聚合 1001 个账号邮箱。
        self.assertEqual((0, 0), fallback_plan_counts())
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET account_id=NULL WHERE id=%s", (task["id"],))
        groups, scanned = fallback_plan_counts()
        self.assertEqual(1, groups)
        self.assertLessEqual(scanned, 1001)
        result = extract_link_service.list_workbench_tasks(provider_id="lumen_flow", status="plus_confirmed")
        self.assertEqual(1, result["total"])
        self.assertEqual(task["id"], result["items"][0]["task_id"])
