from __future__ import annotations

import json
import os
from datetime import datetime
from unittest.mock import patch

from core import account_task_store, db
from core.extract_link import service as extract_link_service
from core.storage import records as record_store
from core.storage.extract_link import batches as extract_link_batches, jobs as extract_link_jobs
from core.storage.operations import store as operation
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
            {"email": "plus@example.test", "plan_check_status": "success", "current_plan_type": "plus", "plan_checked_at": "2026-10-23T13:01:00Z"},
            {"email": "free@example.test", "plan_check_status": "success", "current_plan_type": "free", "plan_checked_at": "2026-10-23T13:01:00Z"},
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
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET created_at='2026-10-23T13:00:00Z' WHERE id=ANY(%s)",
                        ([paid_plus["id"], paid_free["id"]],))
        expected = {
            "processing": {paid_free["id"]},
            "running": set(),
            "extraction_succeeded": {legacy["id"], paid_plus["id"], extract_only["id"]},
            "payment_succeeded": {paid_plus["id"], paid_free["id"]},
            "plus_confirmed": {paid_plus["id"], extract_only["id"]},
            "needs_attention": {paid_free["id"], pending["id"]},
        }
        for status, ids in expected.items():
            with self.subTest(status=status):
                result = extract_link_service.list_workbench_tasks(status=status)
                self.assertEqual(ids, {item["task_id"] for item in result["items"]})
                self.assertEqual(len(ids), result["total"])
                self.assertEqual(len(ids), result["counts"][status])
                self.assertEqual(5, result["counts"]["all"])

    def test_unknown_payment_requires_an_active_run_to_remain_processing(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="待确认统计测试", requested_count=12)
        active_ids = set()
        all_ids = set()
        for has_provider_job in (False, True):
            for task_status in ("request_unknown", "attention_required", "failed", "partial_success", "queued", "running"):
                state = {"extraction_state": "pending", "payment_state": "unknown", "plus_status": "not_applicable"}
                task = self.task(provider="huanguang", mode="auto_payment", status=task_status,
                    batch_id=batch["id"], state=state if has_provider_job else None,
                    summary={"extraction_status": "pending", "payment_status": "unknown", "plus_status": "not_applicable"})
                all_ids.add(task["id"])
                if task_status in {"queued", "running"}:
                    active_ids.add(task["id"])
        processing = extract_link_jobs.list_workbench_page(status="processing", batch_id=batch["id"])
        self.assertEqual(active_ids, {row["task_id"] for row in processing["items"]})
        self.assertEqual(len(active_ids), processing["total"])
        self.assertEqual(len(active_ids), processing["counts"]["processing"])
        self.assertEqual(2, processing["counts"]["running"])
        attention = extract_link_jobs.list_workbench_page(status="needs_attention", batch_id=batch["id"])
        self.assertEqual(all_ids, {row["task_id"] for row in attention["items"]})
        batch_counts = extract_link_batches.batch_task_counts([batch["id"]])[batch["id"]]
        self.assertEqual(len(active_ids), batch_counts["processing"])
        self.assertEqual(2, batch_counts["running"])
        self.assertEqual(len(all_ids), batch_counts["needs_attention"])

    def test_terminal_pending_payments_are_attention_not_processing(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="停止查询统计", requested_count=7)
        tasks = {}
        for status in ("attention_required", "request_unknown", "failed", "cancelled", "stopped", "interrupted", "partial_success"):
            tasks[status] = self.task(provider="legacy", mode="auto_payment", status=status, batch_id=batch["id"],
                state={"extraction_state": "running", "payment_state": "pending", "plus_status": "not_applicable"})
        processing = extract_link_jobs.list_workbench_page(status="processing", batch_id=batch["id"])
        self.assertEqual({tasks["partial_success"]["id"]}, {row["task_id"] for row in processing["items"]})
        counts = extract_link_batches.batch_task_counts([batch["id"]])[batch["id"]]
        self.assertEqual(1, counts["processing"])
        attention = extract_link_jobs.list_workbench_page(status="needs_attention", batch_id=batch["id"])
        self.assertTrue({tasks[s]["id"] for s in ("attention_required", "request_unknown", "failed", "cancelled", "stopped", "interrupted")}
                        <= {row["task_id"] for row in attention["items"]})

    def test_old_remote_running_snapshot_does_not_count_as_local_execution(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="同步统计测试", requested_count=10)
        tasks = {status: self.task(provider="huanguang", status=status, batch_id=batch["id"], state={
            "preflight_status": "passed", "extraction_state": "running",
            "payment_state": "not_started", "plus_status": "not_applicable",
        }) for status in ("queued", "running", "waiting", "cancelling", "settling", "stopping",
                         "request_unknown", "failed", "cancelled", "stopped")}
        expected = {
            "processing": {tasks[status]["id"] for status in ("queued", "running", "waiting", "cancelling", "settling", "stopping")},
            "running": {tasks[status]["id"] for status in ("running", "cancelling", "settling", "stopping")},
            "needs_attention": {tasks[status]["id"] for status in ("request_unknown", "failed", "cancelled", "stopped")},
        }
        batch_counts = extract_link_batches.batch_task_counts([batch["id"]])[batch["id"]]
        all_items = extract_link_service.list_workbench_tasks(batch_id=batch["id"])["items"]
        for status, ids in expected.items():
            with self.subTest(status=status):
                page = extract_link_service.list_workbench_tasks(status=status, batch_id=batch["id"])
                self.assertEqual(ids, {item["task_id"] for item in page["items"]})
                self.assertEqual(len(ids), page["counts"][status])
                self.assertEqual(len(ids), batch_counts[status])
                self.assertEqual(ids, {item["task_id"] for item in all_items
                                       if extract_link_service._workbench_status_matches(item, status)})

    def test_new_queue_plus_unknown_is_not_attention_but_paid_unknown_is(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="到账统计测试", requested_count=3)
        queued = self.task(provider="huanguang", status="queued", batch_id=batch["id"])
        paid_unknown = self.task(provider="huanguang", status="success", mode="auto_payment", batch_id=batch["id"], state={
            "extraction_state": "succeeded", "payment_state": "paid", "plus_status": "unknown",
        })
        paid_unconfirmed = self.task(provider="huanguang", status="success", mode="auto_payment", batch_id=batch["id"], state={
            "extraction_state": "succeeded", "payment_state": "paid", "plus_status": "not_confirmed",
        })
        page = extract_link_service.list_workbench_tasks(status="needs_attention", batch_id=batch["id"])
        self.assertEqual({paid_unknown["id"], paid_unconfirmed["id"]}, {item["task_id"] for item in page["items"]})
        self.assertEqual(2, page["counts"]["needs_attention"])
        self.assertEqual(2, extract_link_batches.batch_task_counts([batch["id"]])[batch["id"]]["needs_attention"])
        self.assertFalse(extract_link_service._workbench_status_matches(
            extract_link_service.extract_workbench_task_detail(queued["id"])["item"], "needs_attention"))
        queued_page = extract_link_service.list_workbench_tasks(status="processing", batch_id=batch["id"])
        self.assertIn(queued["id"], {item["task_id"] for item in queued_page["items"]})

    def test_paid_order_does_not_use_older_account_plan_for_arrival_counts(self):
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": "old-plus@example.test", "plan_check_status": "success", "current_plan_type": "plus",
            "plan_checked_at": "2026-10-23T12:59:00Z",
        }])[0]
        batch = operation.create_runtime_batch(batch_type="extract_link", title="旧套餐检查", requested_count=1)
        task = self.task(provider="legacy", mode="auto_payment", status="attention_required", account_id=account_id,
                         batch_id=batch["id"], state={"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "pending"})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET created_at=%s WHERE id=%s",
                        ("2026-10-23T13:00:00Z", task["id"]))
        page = extract_link_jobs.list_workbench_page(status="plus_confirmed", batch_id=batch["id"])
        self.assertEqual(0, page["total"])
        self.assertEqual(0, page["counts"]["plus_confirmed"])
        self.assertEqual(0, extract_link_batches.batch_task_counts([batch["id"]])[batch["id"]]["plus_confirmed"])

    def test_batch_plus_count_uses_same_email_fallback_as_list(self):
        self.seed(record_store.ACCOUNTS, [{"email": "batch-fallback@example.test", "plan_check_status": "success",
            "current_plan_type": "plus", "plan_checked_at": "2026-10-23T13:01:00Z"}])
        batch = operation.create_runtime_batch(batch_type="extract_link", title="批次邮箱回退", requested_count=1)
        task = self.task(provider="legacy", mode="auto_payment", status="attention_required", account_id=None,
            email="batch-fallback@example.test", batch_id=batch["id"],
            state={"extraction_state": "succeeded", "payment_state": "pending", "plus_status": "pending"})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET created_at='2026-10-23T13:00:00Z' WHERE id=%s", (task["id"],))
        self.assertEqual(1, extract_link_jobs.list_workbench_page(status="plus_confirmed", batch_id=batch["id"])["total"])
        self.assertEqual(1, extract_link_batches.batch_task_counts([batch["id"]])[batch["id"]]["plus_confirmed"])

    def test_independent_plus_check_is_visible_before_platform_payment_confirmation(self):
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": "arrival@example.test", "plan_check_status": "success", "current_plan_type": "plus",
            "plan_checked_at": datetime.fromisoformat("2026-10-23T13:01:00+00:00").astimezone().replace(tzinfo=None).isoformat(),
        }])[0]
        task = self.task(provider="huanguang", mode="auto_payment", status="attention_required", account_id=account_id,
                         state={"extraction_state": "succeeded", "payment_state": "unknown", "plus_status": "not_applicable"})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET created_at=%s WHERE id=%s",
                        ("2026-10-23T13:00:00Z", task["id"]))
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET created_at=%s WHERE id=%s",
                        ("2026-10-23T13:30:00Z", task["run"]["id"]))
        detail = extract_link_service.extract_workbench_task_detail(task["id"])
        self.assertEqual("confirmed", detail["item"]["plus_status"])
        self.assertEqual("request_unknown", detail["item"]["payment_status"])
        page = extract_link_service.list_workbench_tasks(status="plus_confirmed", page_size=1)
        self.assertEqual(1, page["total"])
        self.assertEqual(1, page["counts"]["plus_confirmed"])
        self.assertEqual(task["id"], page["items"][0]["task_id"])
        self.assertEqual("confirmed", page["items"][0]["plus_status"])
        self.assertEqual(0, page["counts"]["payment_succeeded"])
        self.assertEqual(0, extract_link_service.list_workbench_tasks(status="payment_succeeded")["total"])

    def test_independent_plus_projection_requires_fresh_successful_plus_evidence(self):
        local_time = datetime.fromisoformat("2026-10-23T13:01:00+00:00").astimezone().replace(tzinfo=None).isoformat()
        old_time = datetime.fromisoformat("2026-10-23T12:59:59+00:00").astimezone().replace(tzinfo=None).isoformat()
        cases = [
            ("local", local_time, "plus", "success", "auto_payment", "succeeded", False, True),
            ("offset", "2026-10-23T21:01:00+08:00", "pro", "success", "manual_payment", "succeeded", False, True),
            ("utc", "2026-10-23T13:01:00Z", "plus", "success", "auto_payment", "succeeded", False, True),
            ("old", old_time, "plus", "success", "auto_payment", "succeeded", False, False),
            ("equal", "2026-10-23T13:00:00Z", "plus", "success", "auto_payment", "succeeded", False, False),
            ("bad", "not-a-time", "plus", "success", "auto_payment", "succeeded", False, False),
            ("bad-date", "2026-02-30T21:01:00", "plus", "success", "auto_payment", "succeeded", False, False),
            ("bad-month", "2026-99-23T13:01:00Z", "plus", "success", "auto_payment", "succeeded", False, False),
            ("bad-hour", "2026-10-23T24:00:00Z", "plus", "success", "auto_payment", "succeeded", False, False),
            ("bad-second", "2026-10-23T13:01:60Z", "plus", "success", "auto_payment", "succeeded", False, False),
            ("bad-zone", "2026-10-23T13:01:00+99:00", "plus", "success", "auto_payment", "succeeded", False, False),
            ("missing", None, "plus", "success", "auto_payment", "succeeded", False, False),
            ("failed-check", "2026-10-23T13:01:00Z", "plus", "failed", "auto_payment", "succeeded", True, False),
            ("go", "2026-10-23T13:01:00Z", "go", "success", "auto_payment", "succeeded", True, False),
            ("subscription-only", "2026-10-23T13:01:00Z", "free", "success", "auto_payment", "succeeded", True, False),
            ("extract-only", "2026-10-23T13:01:00Z", "plus", "success", "extract_only", "succeeded", False, False),
            ("extract-failed", "2026-10-23T13:01:00Z", "plus", "success", "auto_payment", "failed", False, False),
        ]
        expected = set()
        for name, checked_at, plan, check_status, mode, extraction, subscribed, confirmed in cases:
            account_id = self.seed(record_store.ACCOUNTS, [{
                "email": f"{name}@example.test", "plan_check_status": check_status, "current_plan_type": plan,
                "plan_checked_at": checked_at, "has_active_subscription": subscribed,
            }])[0]
            task = self.task(provider="huanguang", mode=mode, status="attention_required", account_id=account_id,
                             state={"extraction_state": extraction, "payment_state": "unknown", "plus_status": "not_applicable"})
            with operation._connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {operation._table('operation_tasks')} SET created_at=%s WHERE id=%s",
                            ("2026-10-23T13:00:00Z", task["id"]))
            with self.subTest(name=name):
                detail = extract_link_service.extract_workbench_task_detail(task["id"])
                self.assertEqual("confirmed" if confirmed else "not_applicable", detail["item"]["plus_status"])
                self.assertEqual("unpaid" if mode == "extract_only" else "request_unknown", detail["item"]["payment_status"])
            if confirmed:
                expected.add(task["id"])
        page = extract_link_service.list_workbench_tasks(status="plus_confirmed", page_size=100)
        self.assertEqual(expected, {item["task_id"] for item in page["items"]})
        self.assertEqual(3, page["total"])
        self.assertEqual(3, page["counts"]["plus_confirmed"])
        self.assertTrue(all(item["plus_status"] == "confirmed" for item in page["items"]))

    def test_independent_plus_check_uses_nonblank_success_timestamp(self):
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": "arrival-fallback@example.test", "plan_check_status": "success", "current_plan_type": "plus",
            "plan_checked_at": "   ", "plan_last_success_at": "2026-10-23T13:01:00Z",
        }])[0]
        task = self.task(provider="huanguang", mode="auto_payment", account_id=account_id,
                         state={"extraction_state": "succeeded", "payment_state": "unknown", "plus_status": "not_applicable"})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET created_at=%s WHERE id=%s",
                        ("2026-10-23T13:00:00Z", task["id"]))
        detail = extract_link_service.extract_workbench_task_detail(task["id"])
        self.assertEqual("confirmed", detail["item"]["plus_status"])
        page = extract_link_service.list_workbench_tasks(status="plus_confirmed")
        self.assertEqual(1, page["total"])
        self.assertEqual("confirmed", page["items"][0]["plus_status"])

    def test_plus_filter_falls_back_to_email_and_preserves_matching_legacy_link(self):
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": "history@example.test", "plan_check_status": "success", "plan_type": "plus",
            "plan_checked_at": "2026-10-23T13:01:00Z", "extract_link_job_id": "old-job",
            "extract_link_long_url": "https://example.test/old-link",
        }])[0]
        task = self.task(provider="legacy", mode="manual_payment", status="success", email=" HISTORY@example.test ",
                         summary={"remote_job_id": "old-job", "payment_status": "succeeded", "plus_status": "pending"})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET created_at='2026-10-23T13:00:00Z' WHERE id=%s", (task["id"],))
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
            "plan_checked_at": "2026-10-23T13:01:00Z",
        }])[0]
        task = self.task(account_id=account_id, email="selected@example.test", mode="manual_payment", state={
            "extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "pending",
        })
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET created_at='2026-10-23T13:00:00Z' WHERE id=%s", (task["id"],))
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

    def test_child_pending_keeps_ever_extracted_fact_in_sql_filters(self):
        from core.extract_link import service as extract_link_service
        task = self.task(status="queued", provider="huanguang", mode="auto_payment", state={
            "extraction_state": "queued", "payment_state": "pending", "preflight_status": "passed",
            "summary": {"extraction_ever_succeeded": True}, "links": [], "payment_artifact": {},
        })
        result = extract_link_service.list_workbench_tasks(status="extraction_succeeded")
        self.assertIn(task["id"], {item["task_id"] for item in result["items"]})
        item = next(item for item in result["items"] if item["task_id"] == task["id"])
        self.assertEqual("success", item["extraction_status"])
        self.assertFalse(item["has_payment_entry"])
        self.assertEqual(1, result["counts"]["extraction_succeeded"])
