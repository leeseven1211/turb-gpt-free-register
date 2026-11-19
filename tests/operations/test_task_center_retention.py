# -*- coding: utf-8 -*-
import gzip
import hashlib
import importlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
from core.runtime.periodic import PeriodicThread
from tests.runtime.test_periodic_lifecycle import FakeThread
from pathlib import Path
from unittest.mock import patch

from psycopg.errors import DeadlockDetected, OperationalError


class TaskCenterRetentionStreamWriterTests(unittest.TestCase):
    def setUp(self):
        self.retention = importlib.import_module("core.operations.retention")
        self.metadata = {
            "version": 1,
            "created_at": "2026-11-19T00:00:00+00:00",
            "cutoff": "2026-11-12T00:00:00+00:00",
            "retention_days": 7,
        }
        self.assertTrue(hasattr(self.retention, "archive_snapshot_stream"), "流式归档入口尚未实现")

    def test_stream_writes_same_v1_json_as_legacy_with_one_shot_iterators(self):
        deep = leaf = {}
        for _ in range(24):
            leaf["next"] = {}
            leaf = leaf["next"]
        sections = {
            "tasks": [{
                "id": 1,
                "data": {"access_token": "synthetic-private-value", "content": "中文\n\\\"", "deep": deep},
                "output": (b"test", "session_id=synthetic-session"),
            }],
            "runs": [],
            "events": [{"id": number} for number in range(125)],
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy = self.retention.archive_snapshot({**self.metadata, **sections}, archive_root=root)
            result = self.retention.archive_snapshot_stream(
                dict(reversed(tuple(self.metadata.items()))),
                {name: iter(rows) for name, rows in sections.items()},
                archive_root=root,
            )
            archive = Path(result["path"])
            compressed = archive.read_bytes()
            payload = gzip.decompress(compressed)
            self.assertEqual(gzip.decompress(Path(legacy["path"]).read_bytes()), payload)
            self.assertEqual(legacy["counts"], result["counts"])
            self.assertEqual({"tasks": 1, "runs": 0, "events": 125}, result["counts"])
            self.assertEqual(hashlib.sha256(compressed).hexdigest(), result["sha256"])
            self.assertEqual(len(compressed), result["size"])
            self.assertNotIn(b"synthetic-private-value", payload)
            self.assertNotIn(b"synthetic-session", payload)
            self.assertIn(b"[truncated]", payload)
            self.assertFalse(list(root.glob("*.tmp")))

    def test_unexpected_decompressed_content_is_not_published(self):
        open_gzip = gzip.open

        def open_for_test(path, mode, **kwargs):
            if mode == "rb":
                with open_gzip(path, mode) as handle:
                    content = handle.read()
                return io.BytesIO(content.replace(b'"id":1', b'"id":2'))
            return open_gzip(path, mode, **kwargs)

        with tempfile.TemporaryDirectory() as td, patch.object(
            self.retention.gzip, "open", side_effect=open_for_test,
        ):
            with self.assertRaisesRegex(RuntimeError, "回读校验不一致"):
                self.retention.archive_snapshot_stream(
                    self.metadata, {"tasks": iter([{"id": 1}])}, archive_root=Path(td),
                )
            self.assertEqual([], list(Path(td).iterdir()))

    def test_stream_removes_temporary_file_if_record_source_fails(self):
        def source():
            yield {"id": 1}
            raise LookupError("synthetic source failed")

        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(LookupError, "synthetic source failed"):
                self.retention.archive_snapshot_stream(
                    self.metadata, {"tasks": source()}, archive_root=Path(td),
                )
            self.assertEqual([], list(Path(td).iterdir()))

    def test_stream_rejects_gzip_footer_corruption_after_reading_multiple_chunks(self):
        open_gzip = gzip.open

        def open_for_test(path, mode, **kwargs):
            if mode == "rb":
                with path.open("r+b") as raw:
                    raw.seek(-8, os.SEEK_END)
                    original = raw.read(1)
                    raw.seek(-1, os.SEEK_CUR)
                    raw.write(bytes([original[0] ^ 1]))
            return open_gzip(path, mode, **kwargs)

        with tempfile.TemporaryDirectory() as td, patch.object(
            self.retention.gzip, "open", side_effect=open_for_test,
        ), patch.object(self.retention, "_ARCHIVE_CHUNK_SIZE", 64):
            with self.assertRaises(gzip.BadGzipFile):
                self.retention.archive_snapshot_stream(
                    self.metadata, {"events": ({"id": number} for number in range(125))},
                    archive_root=Path(td),
                )
            self.assertEqual([], list(Path(td).iterdir()))

    def test_stream_checks_cancellation_before_scrubbing_next_row(self):
        read = []

        def source():
            for id_ in range(3):
                read.append(id_)
                yield {"id": id_}

        def check_cancel():
            if read == [0]:
                raise InterruptedError("synthetic stop")

        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(InterruptedError, "synthetic stop"):
                self.retention.archive_snapshot_stream(
                    self.metadata, {"events": source()},
                    archive_root=Path(td), check_cancel=check_cancel,
                )
            self.assertEqual([0], read)
            self.assertEqual([], list(Path(td).iterdir()))

    def test_stream_does_not_publish_if_cancelled_after_verified_readback(self):
        verified = False
        open_gzip = gzip.open

        class VerifyRead(io.BytesIO):
            def read(self, size=-1):
                nonlocal verified
                data = super().read(size)
                if not data:
                    verified = True
                return data

        def open_for_test(path, mode, **kwargs):
            if mode == "rb":
                with open_gzip(path, mode) as handle:
                    return VerifyRead(handle.read())
            return open_gzip(path, mode, **kwargs)

        def check_cancel():
            if verified:
                raise InterruptedError("synthetic stop")

        with tempfile.TemporaryDirectory() as td, patch.object(
            self.retention.gzip, "open", side_effect=open_for_test,
        ):
            with self.assertRaisesRegex(InterruptedError, "synthetic stop"):
                self.retention.archive_snapshot_stream(
                    self.metadata, {"tasks": [{"id": 1}]},
                    archive_root=Path(td), check_cancel=check_cancel,
                )
            self.assertEqual([], list(Path(td).iterdir()))


class TaskCenterRetentionArchiveTests(unittest.TestCase):
    def test_archive_snapshot_is_gzipped_redacted_and_verified(self):
        try:
            retention = importlib.import_module("core.operations.retention")
        except ModuleNotFoundError:
            retention = None
        if retention is None:
            self.fail("core.operations.retention 尚未实现")

        snapshot = {
            "version": 1,
            "tasks": [{
                "id": 17,
                "email_snapshot": "archive@example.test",
                "data": {"access_token": "never-archive-this-token"},
                "error_message": "Bearer secret-bearer-token-value-1234567890",
            }],
            "runs": [],
            "events": [],
        }
        with tempfile.TemporaryDirectory() as td:
            result = retention.archive_snapshot(snapshot, archive_root=Path(td))
            archive_path = Path(result["path"])

            self.assertTrue(archive_path.is_file())
            self.assertEqual(".gz", archive_path.suffix)
            self.assertEqual(64, len(result["sha256"]))
            with gzip.open(archive_path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("never-archive-this-token", serialized)
        self.assertNotIn("secret-bearer-token-value", serialized)
        self.assertEqual({"tasks": 1, "runs": 0, "events": 0}, result["counts"])
        self.assertEqual(17, payload["tasks"][0]["id"])

    def test_archive_snapshot_never_truncates_candidate_rows(self):
        retention = importlib.import_module("core.operations.retention")
        snapshot = {
            "version": 1,
            "tasks": [{"id": number, "data": {"token": "secret"}} for number in range(125)],
            "runs": [],
            "events": [],
        }
        with tempfile.TemporaryDirectory() as td:
            result = retention.archive_snapshot(snapshot, archive_root=Path(td))
            with gzip.open(result["path"], "rt", encoding="utf-8") as handle:
                payload = json.load(handle)

        self.assertEqual(125, result["counts"]["tasks"])
        self.assertEqual(list(range(125)), [row["id"] for row in payload["tasks"]])

    def test_cleanup_once_drains_bounded_batches_using_configured_days(self):
        retention = importlib.import_module("core.operations.retention")
        with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
            retention.operation_task_store,
            "cleanup_terminal_history",
            side_effect=[
                {"deleted_tasks": 500, "deleted_batches": 2, "has_more": True},
                {"deleted_tasks": 3, "deleted_batches": 1, "has_more": False},
            ],
        ) as cleanup:
            result = retention.cleanup_once()

        self.assertEqual(503, result["deleted_tasks"])
        self.assertEqual(3, result["deleted_batches"])
        self.assertEqual(2, result["batches"])
        self.assertEqual(2, cleanup.call_count)
        self.assertEqual(7, cleanup.call_args_list[0].kwargs["retention_days"])
        self.assertTrue(callable(cleanup.call_args_list[0].kwargs["archive_stream"]))

    def test_deadlock_retries_failed_batch_and_removes_only_its_orphan_archive(self):
        retention = importlib.import_module("core.operations.retention")
        metadata = {
            "version": 1, "created_at": "2026-11-19T00:00:00Z",
            "cutoff": "2026-11-12T00:00:00Z", "retention_days": 7,
        }
        paths = []

        def cleanup(**kwargs):
            attempt = len(paths)
            if attempt == 2:
                self.assertFalse(paths[1].exists())
                self.assertTrue(paths[0].is_file())
            task_id = 10 if attempt == 0 else 20
            result = kwargs["archive_stream"](metadata, {"tasks": iter([{"id": task_id}])})
            paths.append(Path(result["path"]))
            if attempt == 1:
                raise DeadlockDetected("synthetic deadlock after publication")
            return {"archive": result, "deleted_tasks": 1, "has_more": attempt == 0}

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            existing = root / "task-center-20261118T000000Z-aaaaaaaa.json.gz"
            existing.write_bytes(b"archive from another attempt")
            with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
                retention, "_ARCHIVE_ROOT", root,
            ), patch.object(retention, "remove_expired_archives", return_value=0), patch.object(
                retention.operation_task_store, "cleanup_terminal_history", side_effect=cleanup,
            ):
                result = retention.cleanup_once()
            self.assertEqual(2, result["batches"])
            self.assertEqual(2, result["deleted_tasks"])
            self.assertEqual(str(paths[2]), result["last_archive"]["path"])
            self.assertEqual({existing, paths[0], paths[2]}, set(root.iterdir()))

    def test_three_deadlocks_leave_cycle_due(self):
        retention = importlib.import_module("core.operations.retention")
        with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
            retention.operation_task_store, "cleanup_terminal_history",
            side_effect=DeadlockDetected("synthetic deadlock"),
        ) as cleanup, patch.object(retention, "remove_expired_archives") as remove:
            with self.assertRaises(retention.scheduler_state.PeriodicCycleRetry):
                retention.cleanup_once()
        self.assertEqual(3, cleanup.call_count)
        remove.assert_not_called()

    def test_deadlock_then_contended_lock_leaves_cycle_due(self):
        retention = importlib.import_module("core.operations.retention")
        locked_result = {"deleted_tasks": 0, "deleted_batches": 0, "locked": True}
        with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
            retention.operation_task_store, "cleanup_terminal_history",
            side_effect=[DeadlockDetected("synthetic deadlock"), locked_result],
        ) as cleanup, patch.object(retention, "remove_expired_archives") as remove:
            with self.assertRaises(retention.scheduler_state.PeriodicCycleRetry):
                retention.cleanup_once()
        self.assertEqual(2, cleanup.call_count)
        remove.assert_not_called()

    def test_initial_contended_lock_retains_no_op_behavior(self):
        retention = importlib.import_module("core.operations.retention")
        with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
            retention.operation_task_store, "cleanup_terminal_history",
            return_value={"deleted_tasks": 0, "deleted_batches": 0, "locked": True},
        ) as cleanup, patch.object(retention, "remove_expired_archives", return_value=0):
            result = retention.cleanup_once()
        cleanup.assert_called_once()
        self.assertEqual(1, result["batches"])
        self.assertEqual(0, result["deleted_tasks"])

    def test_orphan_unlink_failure_does_not_prevent_retry(self):
        retention = importlib.import_module("core.operations.retention")
        metadata = {
            "version": 1, "created_at": "2026-11-19T00:00:00Z",
            "cutoff": "2026-11-12T00:00:00Z", "retention_days": 7,
        }
        unlink = Path.unlink
        orphan = None
        attempts = 0

        def cleanup(**kwargs):
            nonlocal orphan, attempts
            attempts += 1
            result = kwargs["archive_stream"](metadata, {"tasks": iter([{"id": 1}])})
            if attempts == 1:
                orphan = Path(result["path"])
                raise DeadlockDetected("synthetic deadlock")
            return {"archive": result, "deleted_tasks": 1}

        def unlink_or_raise(path, *args, **kwargs):
            if path == orphan:
                raise PermissionError("synthetic unlink failure")
            return unlink(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as td:
            with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
                retention, "_ARCHIVE_ROOT", Path(td),
            ), patch.object(retention, "remove_expired_archives", return_value=0), patch.object(
                retention.operation_task_store, "cleanup_terminal_history", side_effect=cleanup,
            ), patch.object(Path, "unlink", unlink_or_raise), self.assertLogs(retention.logger, "WARNING"):
                result = retention.cleanup_once()
            self.assertEqual(2, attempts)
            self.assertTrue(orphan.is_file())
            self.assertEqual(1, result["deleted_tasks"])

    def test_deadlock_does_not_unlink_replaced_archive(self):
        retention = importlib.import_module("core.operations.retention")
        metadata = {
            "version": 1, "created_at": "2026-11-19T00:00:00Z",
            "cutoff": "2026-11-12T00:00:00Z", "retention_days": 7,
        }
        path = None

        def cleanup(**kwargs):
            nonlocal path
            if path is not None:
                return {"deleted_tasks": 1}
            result = kwargs["archive_stream"](metadata, {"tasks": iter([{"id": 1}])})
            path = Path(result["path"])
            replacement = path.with_suffix(".replacement")
            replacement.write_bytes(b"replacement")
            replacement.replace(path)
            raise DeadlockDetected("synthetic deadlock")

        with tempfile.TemporaryDirectory() as td:
            with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
                retention, "_ARCHIVE_ROOT", Path(td),
            ), patch.object(retention, "remove_expired_archives", return_value=0), patch.object(
                retention.operation_task_store, "cleanup_terminal_history", side_effect=cleanup,
            ):
                result = retention.cleanup_once()
            self.assertEqual(1, result["deleted_tasks"])
            self.assertEqual(b"replacement", path.read_bytes())

    def test_failed_or_cancelled_transaction_retains_published_archive(self):
        retention = importlib.import_module("core.operations.retention")
        metadata = {
            "version": 1, "created_at": "2026-11-19T00:00:00Z",
            "cutoff": "2026-11-12T00:00:00Z", "retention_days": 7,
        }
        for failure in (OperationalError, retention.scheduler_state.PeriodicCycleCancelled):
            with self.subTest(error=failure.__name__), tempfile.TemporaryDirectory() as td:
                path = None

                def cleanup(**kwargs):
                    nonlocal path
                    result = kwargs["archive_stream"](metadata, {"tasks": iter([{"id": 1}])})
                    path = Path(result["path"])
                    raise failure("synthetic interruption")

                with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
                    retention, "_ARCHIVE_ROOT", Path(td),
                ), patch.object(
                    retention.operation_task_store, "cleanup_terminal_history", side_effect=cleanup,
                ) as store:
                    with self.assertRaises(failure):
                        retention.cleanup_once()
                    store.assert_called_once()
                self.assertTrue(path.is_file())

    def test_wait_between_deadlock_attempts_can_be_cancelled(self):
        retention = importlib.import_module("core.operations.retention")
        stop = threading.Event()

        def cancel_during_wait(_timeout):
            stop.set()
            return True

        with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch(
            "core.runtime.periodic.execution_allowed", return_value=True,
        ), patch.object(stop, "wait", side_effect=cancel_during_wait) as wait, patch.object(
            retention.operation_task_store, "cleanup_terminal_history",
            side_effect=DeadlockDetected("synthetic deadlock"),
        ) as cleanup:
            with self.assertRaises(retention.scheduler_state.PeriodicCycleCancelled):
                retention.cleanup_once(stop=stop)
            wait.assert_called_once()
            cleanup.assert_called_once()

    def test_scheduled_cycle_passes_cancellation_through_to_archive_transaction(self):
        retention = importlib.import_module("core.operations.retention")
        stop = threading.Event()

        def cleanup(**kwargs):
            stop.set()
            kwargs["check_cancel"]()

        with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
            retention.operation_task_store, "cleanup_terminal_history", side_effect=cleanup,
        ), patch.object(retention, "remove_expired_archives") as remove:
            with self.assertRaises(retention.scheduler_state.PeriodicCycleCancelled):
                retention.cleanup_once(stop=stop)
        remove.assert_not_called()

    def test_expired_archive_cleanup_removes_only_managed_files(self):
        retention = importlib.import_module("core.operations.retention")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expired = root / "task-center-20260101T000000Z-deadbeef.json.gz"
            recent = root / "task-center-20260919T000000Z-feedface.json.gz"
            unrelated = root / "keep-me.txt"
            for path in (expired, recent, unrelated):
                path.write_bytes(b"fixture")
            old = time.time() - 31 * 86400
            os.utime(expired, (old, old))
            os.utime(unrelated, (old, old))

            removed = retention.remove_expired_archives(
                retention_days=30, archive_root=root,
            )

            self.assertEqual(1, removed)
            self.assertFalse(expired.exists())
            self.assertTrue(recent.exists())
            self.assertTrue(unrelated.exists())

    def test_expired_archive_cleanup_continues_when_one_file_cannot_be_removed(self):
        retention = importlib.import_module("core.operations.retention")
        with tempfile.TemporaryDirectory() as td:
            expired = Path(td) / "task-center-20260101T000000Z-deadbeef.json.gz"
            expired.write_bytes(b"fixture")
            old = time.time() - 31 * 86400
            os.utime(expired, (old, old))
            with patch.object(Path, "unlink", side_effect=PermissionError("read only")):
                removed = retention.remove_expired_archives(
                    retention_days=30, archive_root=Path(td),
                )

            self.assertEqual(0, removed)
            self.assertTrue(expired.exists())

    def test_cleanup_once_applies_configured_archive_retention(self):
        retention = importlib.import_module("core.operations.retention")
        with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch(
            "config.operations.TASK_CENTER_ARCHIVE_RETENTION_DAYS", 30,
        ), patch.object(
            retention.operation_task_store,
            "cleanup_terminal_history",
            return_value={"deleted_tasks": 0, "deleted_batches": 0, "has_more": False},
        ), patch.object(
            retention, "remove_expired_archives", return_value=2,
        ) as remove_archives:
            result = retention.cleanup_once()

        self.assertEqual(2, result["removed_archives"])
        remove_archives.assert_called_once_with(retention_days=30)

    def test_scheduler_is_daily_and_disabled_by_zero_retention(self):
        retention = importlib.import_module("core.operations.retention")
        with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 0):
            self.assertFalse(retention.scheduler_enabled())
        with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
            retention.scheduler_state, "run_periodic",
        ) as run_periodic:
            self.assertTrue(retention.scheduler_enabled())
            retention._scheduler_loop()

        kwargs = run_periodic.call_args.kwargs
        self.assertEqual("task_center_retention", kwargs["task"])
        with patch.object(retention, "cleanup_once") as cleanup:
            kwargs["work"]()
        cleanup.assert_called_once_with(stop=retention._SCHEDULER.stop_event)
        self.assertEqual(86400, kwargs["interval_seconds"]())

    def test_periodic_cleanup_starts_at_most_one_worker(self):
        retention = importlib.import_module("core.operations.retention")
        with patch.object(retention, "_SCHEDULER", PeriodicThread("test-retention")), \
             patch("core.runtime.process.get_runtime_context", return_value=None), \
             patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), \
             patch.object(retention.threading, "Thread", side_effect=FakeThread) as thread:
            self.assertTrue(retention.start_periodic_cleanup())
            self.assertFalse(retention.start_periodic_cleanup())
            thread.assert_called_once()
            self.assertTrue(retention.scheduler_status()["alive"])

    def test_disabled_policy_still_starts_idle_worker_for_hot_reload(self):
        retention = importlib.import_module("core.operations.retention")
        with patch.object(retention, "_SCHEDULER", PeriodicThread("test-retention")), \
             patch("core.runtime.process.get_runtime_context", return_value=None), \
             patch("config.operations.TASK_CENTER_RETENTION_DAYS", 0), \
             patch.object(retention.threading, "Thread", side_effect=FakeThread):
            self.assertTrue(retention.start_periodic_cleanup())
            status = retention.scheduler_status()
            self.assertTrue(status["alive"])
            self.assertFalse(status["running"])
            self.assertTrue(status["disabled"])

    def test_native_log_cleanup_is_confined_to_managed_run_logs(self):
        retention = importlib.import_module("core.operations.retention")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            task_root = root / "tasks"
            run_log = task_root / "task-1" / "runs" / "1-run" / "run.jsonl"
            unrelated = root / "webui.log"
            run_log.parent.mkdir(parents=True)
            run_log.write_text("{}\n", encoding="utf-8")
            unrelated.write_text("keep", encoding="utf-8")
            with patch.object(retention.task_run_log, "_LOG_ROOT", root), patch.object(
                retention.task_run_log, "_TASK_LOG_ROOT", task_root,
            ):
                removed = retention.remove_native_task_logs([run_log, unrelated])

            self.assertEqual(1, removed)
            self.assertFalse(run_log.exists())
            self.assertFalse((task_root / "task-1").exists())
            self.assertTrue(unrelated.exists())

    def test_native_log_cleanup_continues_when_one_file_cannot_be_removed(self):
        retention = importlib.import_module("core.operations.retention")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            task_root = root / "tasks"
            run_log = task_root / "task-1" / "runs" / "1-run" / "run.jsonl"
            run_log.parent.mkdir(parents=True)
            run_log.write_text("{}\n", encoding="utf-8")
            with patch.object(retention.task_run_log, "_LOG_ROOT", root), patch.object(
                retention.task_run_log, "_TASK_LOG_ROOT", task_root,
            ), patch.object(Path, "unlink", side_effect=PermissionError("read only")):
                removed = retention.remove_native_task_logs([run_log])

            self.assertEqual(0, removed)
            self.assertTrue(run_log.exists())

    def test_cleanup_once_removes_native_logs_only_after_storage_commit(self):
        retention = importlib.import_module("core.operations.retention")
        with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch(
            "config.operations.TASK_CENTER_ARCHIVE_RETENTION_DAYS", 30,
        ), patch.object(
            retention.operation_task_store,
            "cleanup_terminal_history",
            return_value={
                "deleted_tasks": 1,
                "deleted_batches": 0,
                "has_more": False,
                "native_log_files": ["/managed/tasks/a/runs/1/run.jsonl"],
            },
        ), patch.object(
            retention, "remove_native_task_logs", return_value=1,
        ) as remove_logs, patch.object(
            retention, "remove_expired_archives", return_value=0,
        ):
            result = retention.cleanup_once()

        self.assertEqual(1, result["removed_log_files"])
        remove_logs.assert_called_once_with(["/managed/tasks/a/runs/1/run.jsonl"])


if __name__ == "__main__":
    unittest.main()
