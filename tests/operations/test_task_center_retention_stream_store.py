"""任务中心流式归档的 PostgreSQL 事务测试。"""
import gzip
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import account_task_store
from core.operations import retention
from core.runtime import scheduler_state
from core.storage import postgres
from core.storage.operations import history, store
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

    def test_archive_callback_releases_business_tables_and_preserves_v1(self):
        task_id = self._seed_task()
        run_id = self._seed_run(task_id)
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
            # Stop in the middle of an event page, exactly where the original cursor held its transaction.
            first_event = next(sections["events"])
            with postgres.connect() as conn:
                conn.execute("SET LOCAL lock_timeout='200ms'")
                conn.execute(f"LOCK TABLE {postgres.qualified('registration_jobs')} IN ACCESS EXCLUSIVE MODE NOWAIT")
                conn.execute(f"LOCK TABLE {postgres.qualified('operation_events')} IN ACCESS EXCLUSIVE MODE NOWAIT")
                conn.execute(f"SELECT id FROM {postgres.qualified('operation_runs')} WHERE id=%s FOR UPDATE NOWAIT", (run_id,))
                conn.execute(f"SELECT id FROM {postgres.qualified('operation_tasks')} WHERE id=%s FOR UPDATE NOWAIT", (task_id,))
            self.assertEqual((1, 5), self._retained_rows())
            for name, rows in sections.items():
                self.assertIs(iter(rows), rows)
                self.assertEqual(expected[name], [first_event, *rows] if name == "events" else list(rows))
            return {"verified": True}

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

    def _seed_run(self, task_id, number=1):
        with postgres.connect() as conn:
            return conn.execute(
                f"""INSERT INTO {postgres.qualified('operation_runs')}
                    (run_uuid, task_id, run_no, source_system, source_id, status)
                    VALUES (%s, %s, %s, 'retention-test', %s, 'success') RETURNING id""",
                (f"history-run-{number}", task_id, number, str(number)),
            ).fetchone()[0]

    def _seed_tasks(self, count):
        with postgres.connect() as conn:
            return [row[0] for row in conn.execute(f"""INSERT INTO {postgres.qualified('operation_tasks')}
                (task_uuid, source_system, source_id, task_type, target_type, requested_action, status, completed_at)
                SELECT 'history-'||n, 'ordinary', n::text, 'test', 'test', 'test', 'success',
                       now()-interval '8 days' FROM generate_series(1,%s) n RETURNING id""", (count,))]

    def _seed_batch(self):
        with postgres.connect() as conn:
            return conn.execute(f"""INSERT INTO {postgres.qualified('operation_batches')}
                (batch_uuid,source_system,source_id,batch_type,title,status,completed_at)
                VALUES ('batch','history','batch','test','test','success',now()-interval '8 days')
                RETURNING id""").fetchone()[0]

    def test_busy_pages_do_not_starve_other_history_across_scheduler_cycles(self):
        ids = self._seed_tasks(5)
        with TemporaryDirectory() as directory, patch.object(retention, "_ARCHIVE_ROOT", Path(directory)), \
                patch.object(history, "_CANDIDATES", 2), patch.object(retention, "_MAX_BATCHES_PER_RUN", 2):
            with postgres.connect() as holder:
                holder.execute(f"SELECT FROM {postgres.qualified('operation_tasks')} WHERE id=ANY(%s) FOR UPDATE", (ids[:4],))
                with self.assertRaises(scheduler_state.PeriodicCycleRetry):
                    retention.cleanup_once()
                with self.assertRaises(scheduler_state.PeriodicCycleRetry):
                    retention.cleanup_once()
                self.assertEqual((4, 0), self._retained_rows())
            for _ in range(4):
                try:
                    retention.cleanup_once()
                    break
                except scheduler_state.PeriodicCycleRetry:
                    pass
            self.assertEqual((0, 0), self._retained_rows())

    def test_sparse_candidates_advance_past_protected_pages_and_finish_cycle(self):
        ids = self._seed_tasks(5)
        with postgres.connect() as conn:
            conn.execute(f"""UPDATE {postgres.qualified('operation_tasks')}
                SET data='{{"bulk_target_round_id":1}}' WHERE id=ANY(%s)""", (ids[:4],))
        with TemporaryDirectory() as directory, patch.object(retention, "_ARCHIVE_ROOT", Path(directory)), \
                patch.object(history, "_CANDIDATES", 2), patch.object(retention, "_MAX_BATCHES_PER_RUN", 1):
            first = store.cleanup_terminal_history(retention_days=7, archive=self.fail)
            self.assertEqual(0, first["deleted_tasks"])
            self.assertIsNotNone(first["next_cursor"])
            for _ in range(8):
                try:
                    retention.cleanup_once()
                    break
                except scheduler_state.PeriodicCycleRetry:
                    pass
            else:
                self.fail("a completed scan of protected pages kept the scheduler due")
            self.assertEqual((4, 0), self._retained_rows())
            self.assertEqual(1, len(list(Path(directory).glob("*.json.gz"))))

    def test_empty_batch_acquiring_a_task_invalidates_published_file(self):
        self._assert_new_batch_reference_preserved("task")

    def test_empty_batch_acquiring_a_finished_run_invalidates_published_file(self):
        self._assert_new_batch_reference_preserved("run")

    def test_empty_batch_acquiring_a_pending_projection_invalidates_published_file(self):
        self._assert_new_batch_reference_preserved("projection")

    def _assert_new_batch_reference_preserved(self, reference):
        batch_id = self._seed_batch()
        task_id = self._seed_tasks(1)[0]
        run_id = self._seed_run(task_id)
        with postgres.connect() as conn:
            conn.execute(f"UPDATE {postgres.qualified('operation_tasks')} SET status='running' WHERE id=%s", (task_id,))
        write_file = retention.archive_snapshot_stream

        def attach(*args, **kwargs):
            receipt = write_file(*args, **kwargs)
            with postgres.connect() as conn:
                if reference == "projection":
                    conn.execute(f"INSERT INTO {postgres.qualified('operation_projection_queue')} (batch_id) VALUES (%s)", (batch_id,))
                else:
                    table, row_id = ("operation_runs", run_id) if reference == "run" else ("operation_tasks", task_id)
                    conn.execute(f"UPDATE {postgres.qualified(table)} SET batch_id=%s WHERE id=%s", (batch_id, row_id))
            return receipt

        with TemporaryDirectory() as directory, patch.object(retention, "_ARCHIVE_ROOT", Path(directory)), \
                patch.object(retention, "archive_snapshot_stream", side_effect=attach):
            result = retention._cleanup_batch(7, lambda: None)
            self.assertTrue(result.get("retry"))
            self.assertEqual([], list(Path(directory).iterdir()))
        with postgres.connect() as conn:
            self.assertEqual(1, conn.execute(f"SELECT count(*) FROM {postgres.qualified('operation_batches')}").fetchone()[0])

    def test_filesystem_timeout_is_reported_and_does_not_delete_rows(self):
        self._seed_task()
        def timeout(_):
            raise TimeoutError("archive volume timeout")
        with self.assertRaisesRegex(TimeoutError, "archive volume timeout"):
            store.cleanup_terminal_history(retention_days=7, archive=timeout)
        self.assertEqual((1, 5), self._retained_rows())

    def test_task_reassigned_after_candidate_selection_is_read_again_next_time(self):
        task_id = self._seed_task()
        batch_id = self._seed_batch()
        with postgres.connect() as conn:
            conn.execute(f"UPDATE {postgres.qualified('operation_batches')} SET status='running' WHERE id=%s", (batch_id,))
        select_events = history._event_piece

        def attach_to_batch(task_ids):
            with postgres.connect() as conn:
                conn.execute(f"UPDATE {postgres.qualified('operation_tasks')} SET batch_id=%s WHERE id=%s", (batch_id, task_id))
            return select_events(task_ids)

        snapshots = []
        with patch.object(history, "_event_piece", side_effect=attach_to_batch):
            first = store.cleanup_terminal_history(retention_days=7, archive=snapshots.append)
        self.assertTrue(first.get("retry"))
        self.assertEqual([], snapshots)
        self.assertEqual((1, 5), self._retained_rows())
        second = store.cleanup_terminal_history(retention_days=7, archive=snapshots.append)
        self.assertEqual(1, second["deleted_tasks"])
        self.assertEqual([batch_id], [row["id"] for row in snapshots[0]["batches"]])

    def test_single_oversize_event_is_archived_alone_between_smaller_pieces(self):
        self._seed_task()
        with postgres.connect() as conn:
            ids = [r[0] for r in conn.execute(f"SELECT id FROM {postgres.qualified('operation_events')} ORDER BY id")]
            conn.execute(f"UPDATE {postgres.qualified('operation_events')} SET message=repeat('x',8192) WHERE id=%s", (ids[2],))
        with TemporaryDirectory() as directory, patch.object(retention, "_ARCHIVE_ROOT", Path(directory)), \
                patch.object(history, "_PAGE_BYTES", 2048):
            pieces = []
            for _ in range(3):
                result = retention._cleanup_batch(7, lambda: None)
                with gzip.open(result["archive"]["path"], "rt") as handle:
                    pieces.append(json.load(handle))
        self.assertEqual([ids[:2], ids[2:3], ids[3:]], [[row["id"] for row in piece["events"]] for piece in pieces])
        self.assertEqual(8192, len(pieces[1]["events"][0]["message"]))
        self.assertEqual([0, 0, 1], [len(piece["tasks"]) for piece in pieces])
        self.assertEqual((0, 0), self._retained_rows())

    def test_event_growing_between_budget_and_read_invalidates_piece(self):
        self._seed_task()
        with postgres.connect() as conn:
            event_id = conn.execute(f"SELECT min(id) FROM {postgres.qualified('operation_events')}").fetchone()[0]

        def grow_before_read(metadata, sections, **kwargs):
            with postgres.connect() as conn:
                conn.execute(f"UPDATE {postgres.qualified('operation_events')} SET message=repeat('x',8192) WHERE id=%s", (event_id,))
            return write_file(metadata, sections, **kwargs)

        write_file = retention.archive_snapshot_stream
        with TemporaryDirectory() as directory, patch.object(retention, "_ARCHIVE_ROOT", Path(directory)), \
                patch.object(history, "_PAGE_BYTES", 2048), patch.object(retention, "archive_snapshot_stream", side_effect=grow_before_read):
            result = retention._cleanup_batch(7, lambda: None)
            self.assertTrue(result.get("retry"))
            self.assertEqual([], list(Path(directory).iterdir()))
        self.assertEqual((1, 5), self._retained_rows())

    def test_execution_permit_created_during_archive_protects_task_until_release(self):
        task_id = self._seed_task()
        run_id = self._seed_run(task_id)
        permits = postgres.qualified("operation_execution_permits")

        def claim(_):
            with postgres.connect() as conn:
                conn.execute(f"""INSERT INTO {permits} (permit_id,execution_key,execution_id,run_id,task_type,owner)
                    VALUES ('claim','work','exec',%s,'test','{{}}')""", (run_id,))

        result = store.cleanup_terminal_history(retention_days=7, archive=claim)
        self.assertTrue(result.get("retry"))
        self.assertEqual((1, 5), self._retained_rows())
        self.assertEqual(0, store.cleanup_terminal_history(retention_days=7, archive=lambda _: None)["deleted_tasks"])
        with postgres.connect() as conn:
            conn.execute(f"UPDATE {permits} SET released_at=now() WHERE run_id=%s", (run_id,))
        self.assertEqual(1, store.cleanup_terminal_history(retention_days=7, archive=lambda _: None)["deleted_tasks"])

    def test_two_cleaners_commit_only_one_archive(self):
        self._seed_task()
        barrier = threading.Barrier(2)
        first_file = threading.Event()
        writer = retention.archive_snapshot_stream

        def publish(*args, **kwargs):
            result = writer(*args, **kwargs)
            first_file.set()
            barrier.wait(timeout=8)
            return result

        with TemporaryDirectory() as directory, patch.object(retention, "_ARCHIVE_ROOT", Path(directory)), \
                patch.object(retention, "archive_snapshot_stream", side_effect=publish), \
                ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(retention._cleanup_batch, 7, lambda: None)
            self.assertTrue(first_file.wait(timeout=8))
            results = [first, workers.submit(retention._cleanup_batch, 7, lambda: None)]
            self.assertEqual([0, 1], sorted(f.result(timeout=12)["deleted_tasks"] for f in results))
            self.assertEqual(1, len(list(Path(directory).glob("*.json.gz"))))
            self.assertEqual((0, 0), self._retained_rows())

    def test_inconsistent_event_keeps_its_two_owners_without_blocking_unrelated_task(self):
        first, second, normal = self._seed_tasks(3)
        run_id = self._seed_run(first)
        with postgres.connect() as conn:
            conn.execute(f"""INSERT INTO {postgres.qualified('operation_events')}
                (event_uuid,task_id,run_id,source_system,source_id,stage,message)
                VALUES ('cross-link',%s,%s,'legacy','legacy','test','legacy')""", (second,run_id))
        archives = []
        result = store.cleanup_terminal_history(retention_days=7, archive=archives.append)
        self.assertEqual(1, result["deleted_tasks"])
        self.assertEqual([normal], [r["id"] for r in archives[0]["tasks"]])
        self.assertEqual((2, 1), self._retained_rows())

    def test_busy_run_releases_task_and_future_cycle_completes(self):
        task_id = self._seed_task()
        run_id = self._seed_run(task_id)
        with TemporaryDirectory() as directory, patch.object(retention, "_ARCHIVE_ROOT", Path(directory)):
            with postgres.connect() as holder:
                holder.execute(f"SELECT id FROM {postgres.qualified('operation_runs')} WHERE id=%s FOR UPDATE", (run_id,))
                with self.assertRaises(scheduler_state.PeriodicCycleRetry):
                    retention.cleanup_once()
                holder.execute(f"SELECT id FROM {postgres.qualified('operation_tasks')} WHERE id=%s FOR UPDATE NOWAIT", (task_id,))
                self.assertEqual((1, 5), self._retained_rows())
                self.assertEqual([], list(Path(directory).iterdir()))
            result = retention.cleanup_once()
            self.assertEqual(1, result["deleted_tasks"])
            self.assertEqual(5, result["deleted_events"])
            with gzip.open(result["last_archive"]["path"], "rt") as archive:
                self.assertEqual([run_id], [row["id"] for row in json.load(archive)["runs"]])

    def test_same_event_id_updated_during_archive_survives(self):
        task_id = self._seed_task()
        run_id = self._seed_run(task_id)
        def change(snapshot):
            with postgres.connect() as conn:
                conn.execute(f"SELECT id FROM {postgres.qualified('operation_runs')} WHERE id=%s FOR UPDATE NOWAIT", (run_id,))
                conn.execute(f"SELECT id FROM {postgres.qualified('operation_tasks')} WHERE id=%s FOR UPDATE NOWAIT", (task_id,))
                conn.execute(f"UPDATE {postgres.qualified('operation_events')} SET message='new' WHERE id=%s", (snapshot['events'][0]['id'],))
            return {"verified": True}
        result = store.cleanup_terminal_history(retention_days=7, archive=change)
        self.assertTrue(result["retry"])
        self.assertNotIn("archive", result)
        self.assertEqual((1, 5), self._retained_rows())
        committed = []
        self.assertEqual(1, store.cleanup_terminal_history(retention_days=7, archive=committed.append)["deleted_tasks"])
        self.assertEqual("new", committed[0]["events"][0]["message"])

    def test_added_run_and_unfinished_dependency_during_archive_keep_task(self):
        task_id = self._seed_task()
        result = store.cleanup_terminal_history(retention_days=7, archive=lambda _: self._seed_run(task_id))
        self.assertTrue(result["retry"])
        def add_dependency(_):
            with postgres.connect() as conn:
                conn.execute(f"""INSERT INTO {postgres.qualified('operation_task_dependencies')}
                    (parent_source_system,parent_source_id,child_source_system,child_source_id,dependency_type)
                    VALUES ('retention-test','task','other','2','wait')""")
        result = store.cleanup_terminal_history(retention_days=7, archive=add_dependency)
        self.assertTrue(result["retry"])
        self.assertEqual((1, 5), self._retained_rows())

    def test_large_event_history_commits_bounded_pieces_without_gaps(self):
        task_id = self._seed_task()
        with postgres.connect() as conn:
            conn.execute(f"""INSERT INTO {postgres.qualified('operation_events')}
                (event_uuid,task_id,source_system,source_id,stage,message)
                SELECT 'extra-'||n, %s, 'extra', n::text, 'test','history' FROM generate_series(1,2500) n""", (task_id,))
        pieces = []
        def archive(snapshot):
            pieces.append([r['id'] for r in snapshot['events']])
            return {"verified": True}
        first = store.cleanup_terminal_history(retention_days=7, archive=archive)
        self.assertEqual(0, first['deleted_tasks'])
        self.assertTrue(first['has_more'])
        self.assertGreater(first['deleted_events'], 0)
        self.assertEqual((1, 2505-first['deleted_events']), self._retained_rows())
        self.assertFalse(first.get('native_log_files'))
        for _ in range(10):
            if store.cleanup_terminal_history(retention_days=7, archive=archive)['deleted_tasks']:
                break
        self.assertEqual((0, 0), self._retained_rows())
        self.assertEqual(list(range(1,2506)), [i for piece in pieces for i in piece])
