"""真实 PostgreSQL 覆盖统一重试波次与旧单项反向锁顺序的并发。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread
import uuid
from unittest.mock import patch

from psycopg import Cursor
from psycopg.errors import DeadlockDetected, LockNotAvailable, QueryCanceled

from core.operations import task_center_retry_wave, task_gateway
from core.storage import records
from core.storage.operations import legacy_task_store, store
from tests.support_pg import PostgresTestCase


class TaskCenterRetryWaveLockTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
        legacy_task_store.init()
        self.seed(records.ACCOUNTS, [
            {"id": number, "email": f"wave-lock-{number}@example.test",
             "access_token": "isolated-access", "status": "success"}
            for number in (1, 2)
        ])
        task_gateway.register_operation_actions("wave_locks_native",
            retry_handler=task_gateway.default_operation_retry, source_systems=("native_operations",))
        self.notify = self.enterContext(patch.object(task_gateway, "notify_dispatch"))

    def _targets(self):
        with store._connect() as conn, conn.cursor() as cur:
            parent = store.create_runtime_task(task_type="account_completion", account_id=None,
                email="wave-parent@example.test", resource_family="completion_coordinator", conn=conn)
            child = store.create_runtime_task(task_type="wave_locks_native", account_id=1,
                email="wave-lock-1@example.test", parent_task_id=parent["id"], conn=conn)
            cur.execute(f"""INSERT INTO {legacy_task_store._table('account_action_tasks')}
                (task_uuid,task_type,account_id,email_snapshot,trigger,status,queued_at,result_summary)
                VALUES (%s,'plan_check',2,'wave-lock-2@example.test','manual','failed',now()::text,'{{}}')
                RETURNING id""", (uuid.uuid4().hex,))
            legacy_id = cur.fetchone()["id"]
            legacy = store.create_runtime_task(task_type="plan_check", account_id=2,
                email="wave-lock-2@example.test", source_system="account_action_tasks",
                source_id=str(legacy_id), conn=conn)
            cur.execute(f"UPDATE {store._table('operation_runs')} SET source_id=%s WHERE id=%s",
                (str(legacy_id), legacy["run"]["id"]))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed'")
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed'")
        return parent, child, legacy

    def _snapshot(self):
        with store._connect() as conn, conn.cursor() as cur:
            facts = {}
            for table in ("operation_tasks", "operation_runs", "operation_events"):
                cur.execute(f"SELECT * FROM {store._table(table)} ORDER BY id")
                facts[table] = list(cur.fetchall())
            cur.execute(f"SELECT * FROM {records._qualified(records.ACCOUNTS)} ORDER BY id")
            facts["accounts"] = list(cur.fetchall())
            return facts

    def test_single_account_then_parent_run_does_not_deadlock_mixed_retry_wave(self):
        parent, child, legacy = self._targets()
        targets = store.get_action_tasks_many([child["id"], legacy["id"]])
        before = self._snapshot()
        account_locked, wave_parent_locked, single_requests_parent = Event(), Event(), Event()
        execute = Cursor.execute
        database_lock_failures = []
        wave_lock_count = []

        def single_retry_order():
            with store._connect() as conn, conn.cursor() as cur:
                # 旧单项可能先持有账号，再收口父 Run。
                cur.execute(f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=1 FOR UPDATE")
                account_locked.set()
                if not wave_parent_locked.wait(10):
                    raise RuntimeError("批量波次未锁定父 Run")
                single_requests_parent.set()
                cur.execute(f"SELECT id FROM {store._table('operation_runs')} WHERE id=%s FOR UPDATE",
                    (parent["run"]["id"],))
                return cur.fetchone()["id"]

        def observed(cursor, query, params=None, **kwargs):
            sql = str(query)
            try:
                result = execute(cursor, query, params, **kwargs)
            except (DeadlockDetected, LockNotAvailable, QueryCanceled) as exc:
                database_lock_failures.append(type(exc).__name__)
                raise
            if (not current_thread().name.startswith("single-retry")
                    and "operation_runs" in sql and "FOR UPDATE" in sql):
                wave_lock_count.append(True)
                wave_parent_locked.set()
                if not single_requests_parent.wait(10):
                    raise RuntimeError("旧单项未进入父 Run 竞争")
            return result

        with patch.object(Cursor, "execute", observed), ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="single-retry") as pool:
            single = pool.submit(single_retry_order)
            self.assertTrue(account_locked.wait(10))
            try:
                replies = task_center_retry_wave.accept_retries(targets)
            finally:
                wave_parent_locked.set()
                single_requests_parent.set()
            self.assertEqual(single.result(timeout=10), parent["run"]["id"])
        self.assertTrue(wave_lock_count)
        self.assertEqual(database_lock_failures, [], "批量入口不能靠数据库死锁检测或超时恢复")
        self.assertEqual(set(replies), {child["id"], legacy["id"]})
        statuses = [replies[task_id][1] for task_id in (child["id"], legacy["id"])]
        self.assertIn(statuses, ([202, 202], [503, 503]))
        if statuses == [503, 503]:
            self.assertEqual(self._snapshot(), before)
            self.notify.assert_not_called()
        else:
            self.assertTrue(all(payload["accepted"] for payload, _ in replies.values()))
            self.assertNotEqual(store.get_task(child["id"], include_events=False)["last_run_id"],
                                child["run"]["id"])
            self.assertEqual(records.get_row(records.ACCOUNTS, 2)["plan_check_status"], "queued")
            self.notify.assert_called_once()
