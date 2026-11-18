"""Product Sentinel repository regressions against fake transactions only."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from core.storage import postgres
from core.storage.operations import sentinel_checks as store


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, args):
        self.conn.queries.append((sql, args))
    def fetchone(self):
        return self.conn.active


class FakeConnection:
    def __init__(self):
        self.active = None
        self.queries = []
        self.events = []
        self.in_transaction = False
    def cursor(self):
        return FakeCursor(self)
    def __enter__(self):
        self.in_transaction = True
        self.events.append("begin")
        return self
    def __exit__(self, kind, *args):
        self.events.append("rollback" if kind else "commit")
        self.in_transaction = False


class SentinelStoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConnection()
        self.store = store
        self.key = "a" * 64
        self.schema = type("Schema", (), {"init_operation_schema": Mock()})()

        def lock(conn, name):
            self.assertIs(self.conn, conn)
            self.assertTrue(conn.in_transaction)
            conn.events.append(("lock", name))

        for guard in (
            patch.object(postgres, "connect", side_effect=AssertionError("real database forbidden")),
            patch.object(store.common, "_connect", return_value=self.conn),
            patch.object(store.common, "_table", side_effect=lambda name: '"fixture"."' + name + '"'),
            patch.object(store.records, "advisory_xact_lock", side_effect=lock),
            patch.object(store.schema, "init_operation_schema", self.schema.init_operation_schema),
        ):
            guard.start()
            self.addCleanup(guard.stop)

    def test_invalid_key_rejected_before_any_storage_access(self):
        for key in ("../cache", "", "g" * 64, None):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.store.active_check(key)
        self.assertEqual([], self.conn.queries)

    def test_request_holds_cache_lock_and_commits_task_run_on_same_connection(self):
        def create(conn):
            self.assertIs(self.conn, conn)
            self.assertTrue(conn.in_transaction)
            self.assertEqual(("lock", "sentinel-maintenance:" + self.key), conn.events[-1])
            return {"accepted": True, "task_id": 5, "run_id": 9, "status": "queued"}
        result = self.store.request_check(self.key, create=create)
        self.assertEqual((5, 9), (result["task_id"], result["run_id"]))
        self.assertEqual("commit", self.conn.events[-1])
        sql, args = self.conn.queries[0]
        self.assertIn("operation_runs", sql)
        self.assertIn("operation_tasks", sql)
        self.assertEqual(("sentinel_maintenance_check", self.key), args)

    def test_existing_active_run_is_reused_without_invoking_submission(self):
        self.conn.active = {"task_id": 5, "run_id": 9, "status": "waiting"}
        create = Mock(side_effect=AssertionError("must reuse existing task/run"))
        result = self.store.request_check(self.key, create=create)
        self.assertEqual({"accepted": True, "reused": True, "task_id": 5, "run_id": 9, "status": "waiting"}, result)
        create.assert_not_called()

    def test_failed_acceptance_rolls_back_instead_of_acknowledging(self):
        with self.assertRaisesRegex(RuntimeError, "sentinel_request_not_accepted"):
            self.store.request_check(self.key, create=lambda conn: {"accepted": False})
        self.assertEqual("rollback", self.conn.events[-1])

    def test_status_query_does_not_acquire_execution_or_cache_lock(self):
        self.conn.active = {"task_id": 5, "run_id": 9, "status": "queued"}
        self.assertEqual(self.conn.active, self.store.active_check(self.key))
        self.assertEqual(["begin", "commit"], self.conn.events)

    def test_first_web_read_initializes_schema_before_queue_query(self):
        def connect():
            self.schema.init_operation_schema.assert_called_once_with()
            return self.conn
        with patch.object(store.common, "_connect", side_effect=connect):
            self.store.active_check(self.key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
