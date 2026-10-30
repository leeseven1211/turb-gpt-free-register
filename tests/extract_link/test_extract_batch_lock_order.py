from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core.storage.extract_link import batches as extract_link_batches
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class ExtractBatchLockOrderTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._operation_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        try:
            operation.reset_ready()
            if cls._operation_schema is None:
                os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
            else:
                os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._operation_schema
        finally:
            super().tearDownClass()

    def setUp(self):
        operation.init()

    def test_new_run_foreign_key_does_not_deadlock_batch_refresh(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="并发测试", requested_count=1)
        task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="lock@example.test",
                                             batch_id=batch["id"], data={"provider_id": "legacy"})
        batch_id = int(batch["id"])
        locked = threading.Event()

        def refresh():
            with operation._connect() as conn, conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout='5s'")
                operation._lock_projection_batch(cur, batch_id)
                locked.set()
                operation._refresh_batches(cur, [batch_id])

        with ThreadPoolExecutor(max_workers=1) as pool:
            with operation._connect() as conn, conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout='5s'")
                with patch("core.operations.run_log.append"), patch("core.operations.run_log.build_path", return_value=""):
                    operation._insert_runtime_run(cur, task_id=task["id"], run_no=2, source_system="native_operations",
                                                  account_id=None, batch_id=batch_id,
                                                  resource_family="openai_interactive", data={})
                future = pool.submit(refresh)
                self.assertTrue(locked.wait(3))
                operation._refresh_batches(cur, [batch_id])
                future.result(timeout=5)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT queued_count FROM {operation._table('operation_batches')} WHERE id=%s", (batch_id,))
            self.assertEqual(1, cur.fetchone()["queued_count"])

    def test_submission_and_skipped_updates_acquire_advisory_before_batch_row(self):
        for action in ("submission", "skipped"):
            with self.subTest(action=action):
                batch = operation.create_runtime_batch(batch_type="extract_link", title="锁顺序测试", requested_count=1)
                batch_id = int(batch["id"])
                attempted = threading.Event()
                original_lock = operation._lock_projection_batch

                def observed_lock(cur, target):
                    if threading.current_thread().name.startswith("batch-writer"):
                        attempted.set()
                    return original_lock(cur, target)

                def write():
                    if action == "submission":
                        return extract_link_batches.finish_submission(batch_id, skipped=0, failed=0, complete=True)
                    return operation.set_runtime_batch_skipped(batch_id, [{"reason": "测试"}])

                with patch.object(operation, "_lock_projection_batch", side_effect=observed_lock):
                    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="batch-writer") as pool:
                        with operation._connect() as conn, conn.cursor() as cur:
                            cur.execute("SET LOCAL statement_timeout='5s'")
                            original_lock(cur, batch_id)
                            future = pool.submit(write)
                            self.assertTrue(attempted.wait(3))
                            operation._refresh_batches(cur, [batch_id])
                        future.result(timeout=5)
