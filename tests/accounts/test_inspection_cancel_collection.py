"""直接巡检取消入口的运行子项集合预算和领取竞态。"""
from __future__ import annotations

from collections import Counter
from unittest.mock import patch

from psycopg import Cursor

from core.accounts.inspection import service
from core.operations import task_gateway
from core.storage import records
from core.storage.accounts import inspections
from core.storage.operations import bulk_submission, cancellation, common, legacy_task_store, runtime, schema
from tests.support_pg import PostgresTestCase


class InspectionCancelCollectionTests(PostgresTestCase):
    def setUp(self):
        records.init()
        self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
        legacy_task_store.init()
        schema.init_operation_schema()
        self.enterContext(patch.object(task_gateway, "notify_dispatch"))

    def fixture(self, size, *, running):
        parent = runtime.create_runtime_task(
            task_type=inspections.PARENT_TYPE, account_id=None, email="", resource_family="inspection_coordinator")
        with common._connect() as conn, conn.cursor() as cur:
            children = bulk_submission.create_specs([
                {"task_type": inspections.ITEM_TYPE, "account_id": None, "email": "",
                 "source_id": f"inspection-cancel-{parent['id']}-{index}", "resource_family": "inspection_snapshot"}
                for index in range(size)
            ], conn=conn)
            cur.execute(f"UPDATE {common._table('operation_tasks')} SET parent_task_id=%s,root_task_id=%s WHERE id=ANY(%s)",
                        (parent["id"], parent["id"], [child["task_id"] for child in children]))
            if running:
                cur.execute(f"""UPDATE {common._table('operation_runs')} SET status='running',started_at=now()
                    WHERE id=ANY(%s)""", ([child["run_id"] for child in children],))
                cur.execute(f"UPDATE {common._table('operation_tasks')} SET status='running' WHERE id=ANY(%s)",
                            ([child["task_id"] for child in children],))
        return parent["id"], children

    def query_count(self, parent_id):
        queries = []
        execute = Cursor.execute

        def capture(cursor, query, *args, **kwargs):
            queries.append(str(query))
            return execute(cursor, query, *args, **kwargs)

        with patch.object(Cursor, "execute", capture):
            service.cancel_inspection(parent_id)
        return queries

    def test_running_children_use_constant_sql_for_one_and_twenty(self):
        one, first = self.fixture(1, running=True)
        one_queries = self.query_count(one)
        twenty, many = self.fixture(20, running=True)
        many_queries = self.query_count(twenty)
        self.assertLessEqual(len(many_queries), len(one_queries) + 2,
                             "运行子项的本地取消SQL应按集合增长")
        for table in ("operation_runs", "operation_tasks", "operation_events"):
            one_writes = sum(('UPDATE ' in query or 'INSERT INTO ' in query) and f'"{table}"' in query
                             for query in one_queries)
            many_writes = sum(('UPDATE ' in query or 'INSERT INTO ' in query) and f'"{table}"' in query
                              for query in many_queries)
            self.assertEqual(one_writes, many_writes)
        self.assertTrue(all(runtime.get_run(child["run_id"])["status"] == "cancelling" for child in [*first, *many]))

    def test_child_claimed_after_snapshot_is_cancelled_after_fresh_collection_retry(self):
        parent, children = self.fixture(1, running=False)
        read = inspections.active_child_runs
        seen = 0

        def claim_after_snapshot(inspection_id):
            nonlocal seen
            result = read(inspection_id)
            seen += 1
            if seen == 1:
                with common._connect() as conn, conn.cursor() as cur:
                    cur.execute(f"UPDATE {common._table('operation_runs')} SET status='running' WHERE id=%s",
                                (children[0]["run_id"],))
                    cur.execute(f"UPDATE {common._table('operation_tasks')} SET status='running' WHERE id=%s",
                                (children[0]["task_id"],))
            return result

        with patch.object(inspections, "active_child_runs", side_effect=claim_after_snapshot):
            service.cancel_inspection(parent)
        self.assertGreaterEqual(seen, 2, "CAS状态变化必须集合重读，不能退回逐Run控制")
        run = runtime.get_run(children[0]["run_id"])
        self.assertEqual("cancelling", run["status"])
        self.assertIsNotNone(run["cancel_requested_at"])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT count(*) AS n FROM {common._table('operation_events')}
                WHERE run_id=%s AND event_type='run.cancel_requested'""", (run["id"],))
            self.assertEqual(1, cur.fetchone()["n"])

    def test_collection_cancel_failure_rolls_back_children_and_does_not_reconcile_parent(self):
        parent, children = self.fixture(2, running=True)
        execute = Cursor.execute

        def fail_events(cursor, query, *args, **kwargs):
            text = str(query)
            if "INSERT INTO" in text and '"operation_events"' in text:
                raise RuntimeError("synthetic cancellation write failure")
            return execute(cursor, query, *args, **kwargs)

        with patch.object(Cursor, "execute", fail_events):
            with self.assertRaisesRegex(RuntimeError, "write failure"):
                service.cancel_inspection(parent)
        self.assertTrue(all(runtime.get_run(child["run_id"])["status"] == "running" for child in children))

    def test_all_current_child_states_are_kept_in_scope(self):
        parent, children = self.fixture(6, running=True)
        states = ["queued", "running", "waiting", "cancelling", "settling", "stopping"]
        with common._connect() as conn, conn.cursor() as cur:
            for child, state in zip(children, states):
                cur.execute(f"UPDATE {common._table('operation_runs')} SET status=%s WHERE id=%s", (state, child["run_id"]))
        service.cancel_inspection(parent)
        result = Counter(runtime.get_run(child["run_id"])["status"] for child in children)
        self.assertEqual(Counter({"cancelled": 1, "cancelling": 5}), result)
