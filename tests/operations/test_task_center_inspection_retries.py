"""任务中心巡检重跑按集合受理，同时保留逐请求的全局活动轮次语义。"""
from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

from psycopg import Cursor

from core.accounts.inspection import service
from core.operations import run_log, task_gateway
from core.storage import records
from core.storage.operations import store
from tests.support_pg import PostgresTestCase


def selected(count=1, *, archived="0", workers=3):
    return {index: {"id": index, "task_type": "account_inspection_batch", "source_system": "native_operations",
        "status": "success", "data": {"archived": archived, "workers": workers}}
        for index in range(1, count + 1)}


class TaskCenterInspectionRetryTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        service.register_actions()
        self.notify = self.enterContext(patch.object(task_gateway, "notify_dispatch"))
        self.log = self.enterContext(patch.object(run_log, "append"))
        self.snapshot = self.enterContext(patch.object(service, "get_config_snapshot", return_value={}))

    def account(self, ident=1, **extra):
        return records.insert_row(records.ACCOUNTS, {"id": ident, "email": f"inspection-retry-{ident}@example.test",
            "status": "success", **extra})

    def accept(self, tasks):
        return import_module("core.operations.task_center_inspection").accept_retries(tasks)

    def rows(self, name, *, where="TRUE", params=()):
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {store._table(name)} WHERE {where} ORDER BY id", params)
            return [dict(row) for row in cur.fetchall()]

    def measured(self, tasks):
        queries = []
        execute = Cursor.execute

        def measure(cursor, query, params=None, **kwargs):
            queries.append(str(query))
            return execute(cursor, query, params, **kwargs)

        with patch.object(Cursor, "execute", measure):
            result = self.accept(tasks)
        return result, queries

    def test_twenty_live_requests_create_one_active_parent_and_reuse_rest(self):
        self.account()
        reply, queries = self.measured(selected(20))
        self.assertEqual(len(reply), 20)
        self.assertEqual({status for _, status in reply.values()}, {202})
        payloads = [payload for payload, _ in reply.values()]
        self.assertEqual(sum(bool(payload["created"]) for payload in payloads), 1)
        self.assertEqual(len({payload["task_id"] for payload in payloads}), 1)
        self.assertEqual(len(self.rows("operation_tasks", where="task_type='account_inspection_batch'")), 1)
        self.assertEqual(len(self.rows("operation_tasks", where="task_type='account_inspection'")), 1)
        self.assertLessEqual(len(queries), 24, f"实际 SQL：{len(queries)}")
        self.notify.assert_called_once()
        self.snapshot.assert_called_once()

    def test_twenty_dead_requests_each_create_a_terminal_inspection_with_bounded_sql(self):
        self.account(account_status="deactivated", live_check_error="原废号原因")
        reply, queries = self.measured(selected(20))
        self.assertTrue(all(payload["created"] for payload, _ in reply.values()))
        self.assertEqual(len({payload["task_id"] for payload, _ in reply.values()}), 20)
        parents = self.rows("operation_tasks", where="task_type='account_inspection_batch'")
        children = self.rows("operation_tasks", where="task_type='account_inspection'")
        self.assertEqual((len(parents), len(children)), (20, 20))
        self.assertEqual({row["status"] for row in parents + children}, {"success"})
        self.assertEqual({row["target_status"] for row in parents}, {"completed"})
        self.assertLessEqual(len(queries), 24, f"实际 SQL：{len(queries)}")
        self.notify.assert_called_once()
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT t.parent_task_id,t.root_task_id,r.id,r.status,r.result_summary,i.ordinal,i.run_id
                FROM {store._table('operation_tasks')} t
                JOIN {store._table('operation_runs')} r ON r.id=t.last_run_id
                JOIN {store._table('operation_batch_items')} i ON i.task_id=t.id
                WHERE t.task_type='account_inspection'""")
            facts = list(cur.fetchall())
        self.assertEqual(len(facts), 20)
        for fact in facts:
            self.assertEqual(fact["parent_task_id"], fact["root_task_id"])
            self.assertEqual(fact["id"], fact["run_id"])
            self.assertEqual(fact["ordinal"], 1)
            self.assertEqual(fact["result_summary"]["inspection_outcome"], "deactivated_skipped")
            self.assertIn("原废号原因", fact["result_summary"]["error"])

    def test_empty_requests_each_create_empty_terminal_parent(self):
        reply, queries = self.measured(selected(20))
        self.assertTrue(all(payload["created"] for payload, _ in reply.values()))
        self.assertEqual(len(self.rows("operation_tasks")), 20)
        self.assertEqual({row["status"] for row in self.rows("operation_tasks")}, {"success"})
        self.assertEqual({row["target_status"] for row in self.rows("operation_tasks")}, {"pending"})
        self.assertEqual(len(self.rows("operation_batch_items")), 0)
        self.assertLessEqual(len(queries), 24)

    def test_busy_requests_each_create_terminal_rejected_snapshot(self):
        self.account()
        blocker = store.create_runtime_task(task_type="fixture_busy", account_id=1,
            email="inspection-retry-1@example.test")
        reply, _ = self.measured(selected(20))
        self.assertTrue(all(payload["created"] for payload, _ in reply.values()))
        children = self.rows("operation_tasks", where="task_type='account_inspection'")
        self.assertEqual(len(children), 20)
        self.assertEqual({row["status"] for row in children}, {"failed"})
        self.assertEqual(store.get_run(blocker["run"]["id"])["status"], "queued")

    def test_mixed_scope_workers_follow_request_order_until_active_parent_exists(self):
        self.account(archived=True)
        tasks = selected(3)
        tasks[1]["data"] = {"archived": "0", "workers": "2"}
        tasks[2]["data"] = {"archived": "only", "workers": "7"}
        tasks[3]["data"] = {"archived": "all", "workers": 16}
        reply, _ = self.measured(tasks)
        first, second, third = [reply[index][0] for index in (1, 2, 3)]
        self.assertTrue(first["created"])
        self.assertTrue(second["created"])
        self.assertFalse(third["created"])
        self.assertEqual(second["task_id"], third["task_id"])
        parents = self.rows("operation_tasks", where="task_type='account_inspection_batch'")
        self.assertEqual([row["data"]["workers"] for row in parents], [2, 7])
        self.assertEqual([row["data"]["archived"] for row in parents], ["0", "only"])

    def test_invalid_options_do_not_change_other_handler_or_active_tasks(self):
        tasks = selected(5)
        tasks[1]["data"]["workers"] = "bad"
        tasks[2]["data"]["archived"] = "invalid"
        tasks[3]["status"] = "running"
        tasks[4]["target_status"] = "account_deactivated"
        tasks[5]["task_type"] = "fixture_custom"
        reply = self.accept(tasks)
        self.assertEqual(set(reply), {1, 2})
        self.assertEqual([reply[index][1] for index in (1, 2)], [503, 503])
        self.assertEqual(len(self.rows("operation_tasks")), 0)

    def test_snapshot_failure_rolls_back_all_new_batches_tasks_runs_and_events(self):
        self.account(account_status="deactivated")
        execute = Cursor.execute

        def fail_snapshot(cursor, query, params=None, **kwargs):
            if "INSERT INTO" in str(query) and "operation_batch_items" in str(query):
                raise RuntimeError("isolated snapshot failure")
            return execute(cursor, query, params, **kwargs)

        with patch.object(Cursor, "execute", fail_snapshot):
            reply = self.accept(selected(20))
        self.assertEqual({status for _, status in reply.values()}, {503})
        for table in ("operation_batches", "operation_tasks", "operation_runs", "operation_events", "operation_batch_items"):
            self.assertEqual(self.rows(table), [])
        self.notify.assert_not_called()

    def test_one_and_twenty_terminal_requests_have_equal_sql_count(self):
        self.account(account_status="deactivated")
        one, one_queries = self.measured(selected())
        twenty, twenty_queries = self.measured(selected(20))
        self.assertTrue(one[1][0]["created"])
        self.assertTrue(all(payload["created"] for payload, _ in twenty.values()))
        print(f"巡检重跑 SQL：1 请求={len(one_queries)}，20 请求={len(twenty_queries)}")
        self.assertEqual(len(one_queries), len(twenty_queries))

    def test_terminal_snapshots_and_legacy_batch_match_original_creation(self):
        from core.storage.accounts import inspections
        self.account(1, account_status="deactivated", live_check_error="原废号原因")
        self.account(2)
        store.create_runtime_task(task_type="fixture_busy", account_id=2,
            email="inspection-retry-2@example.test")
        original_id, created = inspections.create_inspection(workers=5, archived="0", config_snapshot={})
        self.assertTrue(created)
        result = self.accept(selected(workers=5))[1][0]
        self.assertTrue(result["created"])
        old_parent = self.rows("operation_tasks", where="id=%s", params=(original_id,))[0]
        new_parent = self.rows("operation_tasks", where="id=%s", params=(result["task_id"],))[0]
        for key in ("status", "target_status", "current_stage", "next_actions", "task_type", "requested_action", "trigger"):
            self.assertEqual(old_parent[key], new_parent[key], key)
        old_run, new_run = [store.get_run(parent["last_run_id"]) for parent in (old_parent, new_parent)]
        for key in ("status", "progress_stage", "result_summary", "error_message", "resource_family"):
            self.assertEqual(old_run[key], new_run[key], key)
        old_children = self.rows("operation_tasks", where="parent_task_id=%s", params=(original_id,))
        new_children = self.rows("operation_tasks", where="parent_task_id=%s", params=(result["task_id"],))
        for old, new in zip(old_children, new_children, strict=True):
            for key in ("status", "target_status", "current_stage", "error_message", "account_id"):
                self.assertEqual(old[key], new[key], key)
            old_child_run, new_child_run = store.get_run(old["last_run_id"]), store.get_run(new["last_run_id"])
            for key in ("status", "progress_stage", "result_summary", "error_message", "resource_family"):
                self.assertEqual(old_child_run[key], new_child_run[key], key)
        old_batch = self.rows("operation_batches", where="id=%s", params=(old_parent["batch_id"],))[0]
        new_batch = self.rows("operation_batches", where="id=%s", params=(new_parent["batch_id"],))[0]
        for key in ("status", "queued_count", "running_count", "success_count", "partial_count",
                    "failed_count", "attention_count", "requested_count"):
            self.assertEqual(old_batch[key], new_batch[key], key)

    def test_task_center_bulk_dispatch_uses_one_inspection_group(self):
        from core.operations import action_service
        self.account(account_status="deactivated")
        tasks = selected(20)
        with patch.object(action_service.operation_task_store, "get_action_tasks_many", return_value=tasks), \
                patch.object(service, "start_inspection", side_effect=AssertionError("不得逐条开始巡检")):
            reply = action_service.accept_bulk_operation_action("retry", list(tasks))
        self.assertEqual(reply["accepted_count"], 20)
        self.assertEqual(reply["skipped_count"], 0)
        self.assertEqual(len(self.rows("operation_tasks", where="task_type='account_inspection_batch'")), 20)

    def test_concurrent_original_and_collection_starts_share_one_active_snapshot(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from core.storage.accounts import inspections
        self.account()
        start = Barrier(2)

        def original():
            start.wait(timeout=10)
            return inspections.create_inspection(workers=2, archived="0", config_snapshot={})

        def collection():
            start.wait(timeout=10)
            return self.accept(selected(20))

        with ThreadPoolExecutor(max_workers=2) as pool:
            old_future, new_future = pool.submit(original), pool.submit(collection)
            original_id, original_created = old_future.result(timeout=15)
            replies = new_future.result(timeout=15)
        payloads = [payload for payload, _ in replies.values()]
        self.assertEqual({payload["task_id"] for payload in payloads}, {original_id})
        self.assertEqual(int(original_created) + sum(int(payload["created"]) for payload in payloads), 1)
        self.assertEqual(len(self.rows("operation_tasks", where="task_type='account_inspection_batch'")), 1)
