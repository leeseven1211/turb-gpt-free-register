"""任务中心流式归档的 PostgreSQL 事务测试。"""
from unittest.mock import patch

from psycopg.errors import LockNotAvailable

from core import account_task_store
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
