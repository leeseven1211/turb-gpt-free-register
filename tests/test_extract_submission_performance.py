"""提链批量提交的事务预算与合成基准，仅使用隔离测试账号。"""
from __future__ import annotations

import json
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from core import account_task_store, extract_link_service, postgres_store, record_store
from core.operations import task_gateway
from core.storage import operation
from tests.support_pg import PostgresTestCase, truncate_schema
from tests import test_extract_workbench_batches as fixtures


class ExtractSubmissionPerformanceTests(PostgresTestCase):
    accounts = fixtures.ExtractWorkbenchBatchStorageTests.accounts
    provider_patches = fixtures.ExtractWorkbenchBatchStorageTests.provider_patches

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._old_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        operation.reset_ready()
        if cls._old_schema is None:
            os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
        else:
            os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._old_schema
        super().tearDownClass()

    def setUp(self):
        operation.init()
        with patch.object(account_task_store, "_SCHEMA", self.schema), patch.object(account_task_store, "_READY_KEY", ""):
            account_task_store.init()

    def measure_submission(self, count):
        self.accounts([{} for _ in range(count)])
        queries = []
        original_execute = Cursor.execute
        original_connect = postgres_store.connect

        def execute(cur, query, *args, **kwargs):
            queries.append(str(query))
            return original_execute(cur, query, *args, **kwargs)

        with self.provider_patches(), patch.object(
            extract_link_service, "get_config_snapshot", return_value={"revision": 7, "values": {}},
        ) as snapshot, patch.object(
            Cursor, "execute", execute,
        ), patch.object(
            postgres_store, "connect", wraps=original_connect,
        ) as connections, patch("core.task_run_log.append"), patch("core.task_run_log.build_path", return_value=""):
            started = time.perf_counter()
            result = extract_link_service.create_workbench_batch(
                provider_id="lumen_flow", mode="extract_only", limit=count,
            )
            elapsed = time.perf_counter() - started
        connection_count = connections.call_count
        self.assertEqual(count, result["started"])
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT DISTINCT data->'config_snapshot'->>'config_snapshot_revision' AS revision FROM {operation._table('operation_tasks')} WHERE batch_id=%s", (result["batch_id"],))
            self.assertEqual(["7"], [row["revision"] for row in cur.fetchall()])
        return {
            "count": count, "queries": len(queries), "connections": connection_count,
            "snapshots": snapshot.call_count, "elapsed_ms": round(elapsed * 1000, 2),
            "ordinal_queries": sum("MAX(ordinal)" in query for query in queries),
        }

    def test_batch_preserves_captured_values_in_task_and_run(self):
        self.accounts([{}, {}])
        raw = {"revision": 19, "values": {
            "EXTRACT_LINK_API_BASE": "https://example.test/captured",
            "EXTRACT_LINK_TYPE": "upi",
            "EXTRACT_LINK_REQUEST_TIMEOUT": 47,
            "EXTRACT_LINK_EVENT_TIMEOUT": 83,
            "ACCOUNT_AT_REFRESH_DRIVER": "protocol",
            "OPENAI_PROTOCOL_VERSION": "v2",
            "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED": True,
            "UNRELATED_SECRET": "不得持久化",
        }}
        expected = {"config_snapshot_revision": 19,
            "api_base": "https://example.test/captured", "link_type": "upi",
            "request_timeout": 47, "event_timeout": 83, "refresh_driver": "protocol",
            "refresh_protocol_version": "v2", "refresh_roxy_debug_enabled": True}
        with self.provider_patches(), patch.object(extract_link_service, "get_config_snapshot", return_value=raw) as capture:
            result = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=2)
        self.assertEqual(capture.call_count, 1)
        self.assertEqual(result["started"], 2)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT task.data->'config_snapshot' AS task_config, run.data->'config_snapshot' AS run_config FROM {operation._table('operation_tasks')} task JOIN {operation._table('operation_runs')} run ON run.task_id=task.id WHERE task.batch_id=%s ORDER BY task.id", (result["batch_id"],))
            configs = cur.fetchall()
        self.assertEqual(len(configs), 2)
        for row in configs:
            self.assertEqual(row["task_config"], expected)
            self.assertEqual(row["run_config"], expected)

    def test_batch_captures_one_snapshot_and_avoids_per_item_ordinal_queries(self):
        measured = self.measure_submission(3)
        self.assertEqual(1, measured["snapshots"])
        self.assertLessEqual(measured["ordinal_queries"], 1)
        # 候选、批次与最终汇总为固定开销；每项只借一次事务连接。
        self.assertLessEqual(measured["connections"], 3 + 5)

    def test_qualification_changes_after_snapshot_are_rechecked_under_account_lock(self):
        ids = self.accounts([{}, {}])
        from core.storage import extract_link_batches
        original = extract_link_batches.candidate_accounts

        def changed(**kwargs):
            candidates = original(**kwargs)
            record_store.patch_row(record_store.ACCOUNTS, ids[0], {"current_plan_type": "plus"})
            return candidates

        with self.provider_patches(), patch.object(extract_link_batches, "candidate_accounts", side_effect=changed):
            result = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=2)
        self.assertEqual((1, 1, 0), tuple(result[key] for key in ("started", "skipped", "failed")))
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT ordinal FROM {operation._table('operation_batch_items')} WHERE batch_id=%s", (result["batch_id"],))
            self.assertEqual([1], [row["ordinal"] for row in cur.fetchall()])

    def test_item_sql_failure_rolls_back_task_and_continues_with_same_config_revision(self):
        ids = self.accounts([{}, {}, {}])
        original_insert = operation._insert_runtime_run

        def fail_second(cur, **kwargs):
            if kwargs["account_id"] == ids[1]:
                cur.execute("SELECT 1 / 0")
            return original_insert(cur, **kwargs)

        with self.provider_patches(), patch.object(operation, "_insert_runtime_run", side_effect=fail_second):
            result = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=3)
        self.assertEqual((2, 0, 1), tuple(result[key] for key in ("started", "skipped", "failed")))
        self.assertEqual("failed", record_store.get_row(record_store.ACCOUNTS, ids[1])["extract_link_status"])
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT task.account_id, item.ordinal FROM {operation._table('operation_tasks')} task JOIN {operation._table('operation_batch_items')} item ON item.task_id=task.id WHERE task.batch_id=%s ORDER BY item.ordinal", (result["batch_id"],))
            self.assertEqual([(ids[0], 1), (ids[2], 2)], [(row["account_id"], row["ordinal"]) for row in cur.fetchall()])

    def test_busy_unique_violation_keeps_outer_transaction_usable(self):
        ids = self.accounts([{}, {}])
        operation.create_runtime_task(task_type="live_check", account_id=ids[0], email="busy@example.test")
        from core.storage import extract_link_batches
        with self.provider_patches(), patch.object(extract_link_batches, "candidate_accounts", return_value={
            "items": [{"account_id": value} for value in ids], "filters": {}, "limit": 2,
        }):
            result = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=2)
        self.assertEqual((1, 1, 0), tuple(result[key] for key in ("started", "skipped", "failed")))
        self.assertEqual("failed", record_store.get_row(record_store.ACCOUNTS, ids[0])["extract_link_status"])
        self.assertEqual("queued", record_store.get_row(record_store.ACCOUNTS, ids[1])["extract_link_status"])

    def test_concurrent_busy_submissions_reuse_their_two_outer_connections(self):
        ids = self.accounts([{}, {}])
        for account_id in ids:
            operation.create_runtime_task(task_type="live_check", account_id=account_id,
                                          email="busy-pool@example.test")
        barrier = threading.Barrier(2)
        original_lookup = operation.active_run_for_account

        def lookup(*args, **kwargs):
            barrier.wait(timeout=3)
            return original_lookup(*args, **kwargs)

        # 每个提交都占一条事务连接；冲突查询不得再占第二条，否则小池互等超时。
        # 连接仅替换为同一隔离库的专用真实池，不替换任何业务 SQL 或事务。
        with ConnectionPool(postgres_store.database_url(), min_size=2, max_size=2, timeout=0.5,
                            kwargs={"row_factory": dict_row}) as pool:
            with patch.object(operation, "_connect", side_effect=pool.connection), \
                 patch.object(operation, "active_run_for_account", side_effect=lookup), \
                 ThreadPoolExecutor(max_workers=2) as executor:

                def submit(account_id):
                    with operation._connect() as conn:
                        record_store.get_row(record_store.ACCOUNTS, account_id, conn=conn, for_update=True)
                        result = task_gateway.submit_durable_operation(
                            task_type="extract_link", account_id=account_id, email="busy-pool@example.test",
                            source_id=f"concurrent-busy-{account_id}", dispatch=False, conn=conn,
                        )
                        self.assertTrue(record_store.patch_row(record_store.ACCOUNTS, account_id,
                                                              {"note": "冲突后事务可继续"}, conn=conn))
                        return result

                results = list(executor.map(submit, ids))
        self.assertTrue(all(result["busy"] and not result["accepted"] for result in results))
        self.assertTrue(all(result.get("run_id") and result.get("task_id") for result in results))
        for account_id in ids:
            self.assertEqual(record_store.get_row(record_store.ACCOUNTS, account_id)["note"], "冲突后事务可继续")
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM {operation._table('operation_tasks')}")
            self.assertEqual(cur.fetchone()["n"], 2)

    def test_duplicate_account_ids_are_not_enqueued_twice(self):
        ids = self.accounts([{}, {}])
        from core.storage import extract_link_batches
        with self.provider_patches(), patch.object(extract_link_batches, "candidate_accounts", return_value={
            "items": [{"account_id": value} for value in (ids[0], ids[0], ids[1])], "filters": {}, "limit": 3,
        }):
            result = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=3)
        self.assertEqual(2, result["started"])
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT account_id FROM {operation._table('operation_tasks')} WHERE batch_id=%s ORDER BY id", (result["batch_id"],))
            self.assertEqual(ids, [row["account_id"] for row in cur.fetchall()])

    def test_optional_facets_does_not_run_facet_queries(self):
        with patch.object(Cursor, "execute", autospec=True, side_effect=Cursor.execute) as execute:
            result = operation.list_tasks(include_facets=False)
        self.assertNotIn("facets", result)
        self.assertEqual(2, execute.call_count)
        self.assertFalse(any(" AS facet" in str(call.args[1]) for call in execute.call_args_list))
        with patch.object(Cursor, "execute", autospec=True, side_effect=Cursor.execute) as default_execute:
            default = operation.list_tasks()
        self.assertEqual(7, default_execute.call_count)
        self.assertEqual({"task_type", "status", "target_status", "stage", "run_count"}, set(default["facets"]))
        self.assertEqual(result, {key: value for key, value in default.items() if key != "facets"})

    def test_synthetic_benchmark(self):
        if os.getenv("TURB_EXTRACT_SUBMISSION_BENCHMARK") != "1":
            self.skipTest("通过显式环境变量运行 10/100/500/1000 项隔离基准")
        for count in (10, 100, 500, 1000):
            truncate_schema(self.schema)
            print("EXTRACT_SUBMISSION_BENCHMARK " + json.dumps(self.measure_submission(count)), flush=True)
