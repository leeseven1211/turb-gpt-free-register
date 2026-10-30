# -*- coding: utf-8 -*-
import gzip
import importlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


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
        self.assertTrue(callable(cleanup.call_args_list[0].kwargs["archive"]))

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
        self.assertIs(retention.cleanup_once, kwargs["work"])
        self.assertEqual(86400, kwargs["interval_seconds"]())

    def test_periodic_cleanup_starts_at_most_one_worker(self):
        retention = importlib.import_module("core.operations.retention")
        retention.reset_for_tests()
        try:
            with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 7), patch.object(
                retention.threading, "Thread",
            ) as thread:
                self.assertTrue(retention.start_periodic_cleanup())
                self.assertFalse(retention.start_periodic_cleanup())

            thread.assert_called_once_with(
                target=retention._scheduler_loop,
                name="task-center-retention",
                daemon=True,
            )
            thread.return_value.start.assert_called_once_with()
        finally:
            retention.reset_for_tests()

    def test_disabled_policy_still_starts_idle_worker_for_hot_reload(self):
        retention = importlib.import_module("core.operations.retention")
        retention.reset_for_tests()
        try:
            with patch("config.operations.TASK_CENTER_RETENTION_DAYS", 0), patch.object(
                retention.threading, "Thread",
            ) as thread:
                self.assertTrue(retention.start_periodic_cleanup())

            thread.return_value.start.assert_called_once_with()
        finally:
            retention.reset_for_tests()

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
