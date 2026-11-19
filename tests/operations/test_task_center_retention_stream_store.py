"""任务中心流式归档的 PostgreSQL 事务测试。"""
import gzip
import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

from psycopg.errors import InsufficientPrivilege, LockNotAvailable

from core import account_task_store
from core.operations import retention
from core.storage import postgres
from core.storage.operations import store
from tests.support_pg import PostgresTestCase


class TaskCenterRetentionStreamStoreTests(PostgresTestCase):
    def setUp(self):
        schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        schema_patch.start()
        self.addCleanup(schema_patch.stop)
        ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        ready_patch.start()
        self.addCleanup(ready_patch.stop)
        account_task_store.init()
        store.init()

    def _seed_task(self):
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {postgres.qualified('operation_tasks')}
                    (task_uuid, source_system, source_id, task_type, target_type,
                     requested_action, status, completed_at)
                VALUES ('retention-task', 'retention-test', 'task', 'live_check',
                    'account', 'live_check', 'success', now() - interval '8 days')
                RETURNING id
                """
            )
            task_id = cur.fetchone()[0]
            cur.execute(
                f"""
                INSERT INTO {postgres.qualified('operation_events')}
                    (event_uuid, task_id, source_system, source_id, stage, message, detail)
                SELECT 'retention-event-' || seq, %s, 'retention-test', seq::text,
                    'test', 'test.event', jsonb_build_object('ordinal', seq)
                FROM generate_series(1, 5) AS seq
                """,
                (task_id,),
            )
        return task_id

    def _retained_rows(self):
        with postgres.connect() as conn, conn.cursor() as cur:
            return tuple(
                cur.execute(f"SELECT count(*) FROM {postgres.qualified(table)}").fetchone()[0]
                for table in ("operation_tasks", "operation_events")
            )

    def test_archive_stream_matches_legacy_snapshot_across_server_cursor_fetches(self):
        task_id = self._seed_task()
        expected = {}

        def observe_legacy(snapshot):
            expected.update(snapshot)
            raise ValueError("读取旧快照后回滚")

        with self.assertRaisesRegex(ValueError, "读取旧快照后回滚"):
            store.cleanup_terminal_history(retention_days=7, archive=observe_legacy)

        def archive_stream(metadata, sections, *, check_cancel):
            self.assertIsNone(check_cancel)
            self.assertEqual(1, metadata["version"])
            self.assertEqual(list(expected)[4:], list(sections))
            # 归档回调开始时候选已经锁定，还没有开始读取关联记录。
            with postgres.connect() as conn, conn.cursor() as cur:
                with self.assertRaises(LockNotAvailable):
                    cur.execute(
                        f"SELECT id FROM {postgres.qualified('operation_tasks')} "
                        "WHERE id=%s FOR UPDATE NOWAIT",
                        (task_id,),
                    )
            for name, rows in sections.items():
                self.assertIs(iter(rows), rows)
                self.assertEqual(expected[name], list(rows))
            return {"verified": True}

        with patch.object(store, "_RETENTION_FETCH_ROWS", 2):
            result = store.cleanup_terminal_history(retention_days=7, archive_stream=archive_stream)

        self.assertEqual(1, result["deleted_tasks"])
        self.assertEqual({"verified": True}, result["archive"])
        self.assertEqual((0, 0), self._retained_rows())

    def test_return_before_consuming_all_sections_rolls_back(self):
        self._seed_task()

        def archive_stream(_metadata, sections, *, check_cancel):
            next(sections["events"])
            return {"verified": True}

        with self.assertRaisesRegex(RuntimeError, "归档分段未完整读取"):
            store.cleanup_terminal_history(retention_days=7, archive_stream=archive_stream)
        self.assertEqual((1, 5), self._retained_rows())

    def test_archive_exception_preserves_candidate_and_its_events(self):
        self._seed_task()

        def archive_stream(_metadata, sections, *, check_cancel):
            next(sections["events"])
            raise OSError("归档写入失败")

        with self.assertRaisesRegex(OSError, "归档写入失败"):
            store.cleanup_terminal_history(retention_days=7, archive_stream=archive_stream)
        self.assertEqual((1, 5), self._retained_rows())

    def test_stop_after_archive_consumption_rolls_back_before_delete(self):
        self._seed_task()
        stopping = False

        def check_cancel():
            if stopping:
                raise InterruptedError("归档已停止")

        def archive_stream(_metadata, sections, *, check_cancel):
            nonlocal stopping
            for rows in sections.values():
                list(rows)
            stopping = True
            return {"verified": True}

        with self.assertRaisesRegex(InterruptedError, "归档已停止"):
            store.cleanup_terminal_history(
                retention_days=7,
                archive_stream=archive_stream,
                check_cancel=check_cancel,
            )
        self.assertEqual((1, 5), self._retained_rows())

    def test_cleanup_retries_real_deadlock_without_leaving_an_extra_archive(self):
        tasks = postgres.qualified("operation_tasks")
        runs = postgres.qualified("operation_runs")
        try:
            with postgres.connect() as conn:
                conn.execute("SET LOCAL deadlock_timeout='100ms'")
        except InsufficientPrivilege:
            self.skipTest("该 PostgreSQL 测试用户无权固定死锁检测顺序")
        task_id = self._seed_task()
        with postgres.connect() as conn:
            run_id = conn.execute(
                f"""INSERT INTO {runs} (run_uuid, task_id, run_no, source_system, source_id, status)
                    VALUES ('history-run', %s, 1, 'retention-test', 'run', 'success')
                    RETURNING id""",
                (task_id,),
            ).fetchone()[0]
        archive_root = Path(mkdtemp(prefix="test-retention-deadlock-"))
        existing_archive = archive_root / "task-center-existing.json.gz"
        existing_archive.write_bytes(b"existing archive")
        archive_paths = []
        task_locked = threading.Event()
        run_lock_owner = Future()
        connection = store._common._connect
        writer = retention.archive_snapshot_stream
        retention_pid = None

        @contextmanager
        def configure_retention_connection():
            nonlocal retention_pid
            with connection() as conn:
                conn.execute("SET LOCAL deadlock_timeout='100ms'")
                conn.execute("SET LOCAL statement_timeout='8s'")
                retention_pid = conn.info.backend_pid
                yield conn

        def hold_run_then_lock_task():
            with postgres.connect() as conn:
                conn.execute("SET LOCAL deadlock_timeout='12s'")
                conn.execute("SET LOCAL statement_timeout='12s'")
                conn.execute(f"SELECT * FROM {runs} WHERE id=%s FOR UPDATE", (run_id,))
                run_lock_owner.set_result(conn.info.backend_pid)
                self.assertTrue(task_locked.wait(5), "归档事务未取得候选锁")
                conn.execute(f"SELECT * FROM {tasks} WHERE id=%s FOR UPDATE", (task_id,))

        def archive_stream(metadata, sections, **kwargs):
            if not archive_paths:
                task_locked.set()
                holder_pid = run_lock_owner.result(timeout=5)
                with postgres.connect() as observer:
                    observer.execute("SET LOCAL statement_timeout='2s'")
                    deadline = time.monotonic() + 4
                    while not observer.execute(
                        "SELECT %s = ANY(pg_blocking_pids(%s))", (retention_pid, holder_pid)
                    ).fetchone()[0]:
                        self.assertLess(time.monotonic(), deadline, "持有 Run 的事务未等待候选锁")
                        time.sleep(0.01)
            result = writer(metadata, sections, **kwargs)
            path = Path(result["path"])
            self.assertTrue(path.is_file())
            archive_paths.append(path)
            return result

        try:
            with (
                patch.object(retention, "_ARCHIVE_ROOT", archive_root),
                patch.object(retention, "archive_snapshot_stream", archive_stream),
                patch.object(store._common, "_connect", configure_retention_connection),
                ThreadPoolExecutor(max_workers=1) as executor,
            ):
                competing_transaction = executor.submit(hold_run_then_lock_task)
                result = retention.cleanup_once()
                competing_transaction.result(timeout=12)
            self.assertEqual(2, len(archive_paths))
            self.assertEqual(1, result["deleted_tasks"])
            self.assertEqual((0, 0), self._retained_rows())
            with postgres.connect() as conn:
                self.assertEqual(0, conn.execute(f"SELECT count(*) FROM {runs}").fetchone()[0])
            self.assertFalse(archive_paths[0].exists())
            self.assertEqual({existing_archive, archive_paths[1]}, set(archive_root.iterdir()))
            self.assertEqual(b"existing archive", existing_archive.read_bytes())
            self.assertEqual(str(archive_paths[1]), result["last_archive"]["path"])
            with gzip.open(archive_paths[1], "rt", encoding="utf-8") as archive:
                payload = json.load(archive)
            self.assertEqual([task_id], [row["id"] for row in payload["tasks"]])
            self.assertEqual([run_id], [row["id"] for row in payload["runs"]])
            self.assertEqual([1, 2, 3, 4, 5], [row["detail"]["ordinal"] for row in payload["events"]])
        finally:
            for path in archive_root.iterdir():
                path.unlink()
            archive_root.rmdir()
