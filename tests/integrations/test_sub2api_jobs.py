"""Sub2API 补传使用隔离 PostgreSQL，所有远端客户端均为模拟。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core.storage import codex, records
from core.storage.operations import store as operation
from core.operations import task_gateway
from tests.support_pg import PostgresTestCase


class Sub2ApiJobTests(PostgresTestCase):
    def setUp(self):
        from core.integrations.sub2api import jobs
        from core.storage import sub2api as store

        self.jobs, self.store = jobs, store
        operation.reset_ready()
        operation.init()
        store.init()
        self.account_id = records.insert_row(
            records.ACCOUNTS,
            {
                "email": "sync-job@example.test",
                "created_at": "2026-11-03T00:00:00Z",
                "updated_at": "2026-11-03T00:00:00Z",
                "access_token": "local-original",
            },
        )
        self.filename = "codex-sync-job@example.test-free.json"
        self.credential = {
            "email": "sync-job@example.test",
            "access_token": "fixture-at-1",
            "refresh_token": "fixture-rt-1",
            "id_token": "fixture-id-1",
        }
        codex.save_codex_credential_record(self.filename, self.credential)
        for mocked in (
            patch.object(jobs.client, "configured_backend_identity", return_value="backend-a", create=True),
            patch.object(task_gateway, "notify_dispatch"),
        ):
            mocked.start()
            self.addCleanup(mocked.stop)

    def execute(self, run_id):
        return task_gateway._execute_operation_handler("sub2api_sync", run_id)

    def rows(self):
        return self.store.list_jobs(filename=self.filename)

    def test_busy_parent_leaves_pending_then_runs_without_openai(self):
        parent = task_gateway.submit_durable_operation(
            task_type="codex_token_refresh", account_id=self.account_id, email=self.credential["email"], dispatch=False
        )
        result = self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        self.assertTrue(result["pending"])
        self.assertIn(self.rows()[0]["status"], ("pending", "blocked_backend"))
        operation.finish_run(parent["run_id"], status="success")
        self.jobs.enqueue_due()
        queued = self.rows()[0]
        self.assertEqual("queued", queued["status"])
        with patch.object(
            self.jobs.client,
            "update_and_enable_configured_account",
            create=True,
            return_value={"uploaded": True, "enabled": True, "sub2api_account_id": 41},
        ) as update:
            self.assertTrue(self.execute(queued["run_id"])["ok"])
        self.assertEqual(41, update.call_args.args[1])
        self.assertEqual("backend-a", update.call_args.kwargs["expected_backend"])
        self.assertEqual("success", self.rows()[0]["status"])
        self.assertEqual("local-original", codex.get_account_by_email(self.credential["email"])["access_token"])

    def test_each_remote_target_is_preserved_and_processed(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41, 42, 41])
        with patch.object(
            self.jobs.client,
            "update_and_enable_configured_account",
            create=True,
            side_effect=lambda auth, remote_id, **kw: {
                "uploaded": True,
                "enabled": True,
                "sub2api_account_id": remote_id,
            },
        ) as update:
            for _ in range(3):
                self.jobs.enqueue_due()
                for row in self.rows():
                    if row["status"] == "queued":
                        self.execute(row["run_id"])
        self.assertEqual({41, 42}, {call.args[1] for call in update.call_args_list})
        self.assertEqual(["success", "success"], [row["status"] for row in self.rows()])

    def test_failure_retries_fixed_target_with_bounded_backoff(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        with patch.object(
            self.jobs.client,
            "update_and_enable_configured_account",
            create=True,
            side_effect=self.jobs.client.Sub2ApiSyncError(
                "reset_error", "sub2api_timeout", "模拟超时", uploaded=True, sub2api_account_id=41
            ),
        ):
            self.assertFalse(self.execute(self.rows()[0]["run_id"])["ok"])
        failed = self.rows()[0]
        self.assertEqual(
            ("pending", 41, 1, "sub2api_timeout"),
            (failed["status"], failed["remote_account_id"], failed["attempt_count"], failed["error_code"]),
        )
        self.assertGreater(failed["retry_in_seconds"], 0)
        self.assertLessEqual(failed["retry_in_seconds"], 300)
        self.assertEqual(0, self.jobs.enqueue_due()["queued"])
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        self.assertEqual("queued", self.rows()[0]["status"])

    def test_new_credential_generation_rejects_old_worker_result(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        previous = self.rows()[0]

        def replace(auth, remote_id, **kwargs):
            self.credential["access_token"] = "fixture-at-2"
            codex.save_codex_credential_record(self.filename, self.credential)
            self.jobs.queue_sync(self.filename, remote_account_ids=[41])
            return {"uploaded": True, "enabled": True, "sub2api_account_id": remote_id}

        with patch.object(self.jobs.client, "update_and_enable_configured_account", create=True, side_effect=replace):
            self.execute(previous["run_id"])
        current = self.rows()[0]
        self.assertNotEqual(previous["generation"], current["generation"])
        self.assertEqual("pending", current["status"])
        self.assertEqual(0, codex.list_codex_accounts()[0]["sub2_uploaded_count"])

    def test_backend_change_keeps_old_remote_id_off_new_backend(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41], delay_seconds=60)
        with patch.object(self.jobs.client, "configured_backend_identity", return_value="backend-b"):
            self.jobs.enqueue_due()
            new = self.jobs.queue_sync(self.filename)
        rows = self.rows()
        self.assertEqual(2, len(rows))
        self.assertEqual([41], [r["remote_account_id"] for r in rows if r["backend"] == "backend-a"])
        self.assertEqual([None], [r["remote_account_id"] for r in rows if r["backend"] == "backend-b"])
        self.assertTrue(new["accepted"])

    def test_failure_receipt_remembers_request_backend_and_remote_id(self):
        result = self.jobs.record_sync_failure(
            self.filename,
            {
                "backend_identity": "backend-old",
                "sub2api_account_id": 51,
                "stage": "enable_scheduling",
                "error_code": "sub2api_timeout",
                "error": "模拟超时",
            },
        )
        self.assertEqual("backend-old", result["items"][0]["backend"])
        self.assertEqual(51, result["items"][0]["remote_account_id"])
        self.assertEqual("pending", self.rows()[0]["status"])

    def test_restart_recovers_terminal_run_and_preserves_live_run(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        row = self.rows()[0]
        self.jobs.enqueue_due()
        self.assertEqual(row["run_id"], self.rows()[0]["run_id"])
        operation.finish_run(row["run_id"], status="failed")
        self.assertTrue(self.jobs._scheduler_ready())
        self.jobs.enqueue_due()
        recovered = self.rows()[0]
        self.assertEqual("queued", recovered["status"])
        self.assertNotEqual(row["run_id"], recovered["run_id"])

    def test_parallel_enqueue_has_one_active_run_and_no_credential_copy(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: self.jobs.queue_sync(self.filename, remote_account_ids=[41]), range(3)))
        rows = self.rows()
        self.assertEqual(1, len(rows))
        stored = json.dumps(rows, default=str)
        run = operation.get_run(rows[0]["run_id"])
        for secret in self.credential.values():
            if secret.startswith("fixture-"):
                self.assertNotIn(secret, stored)
                self.assertNotIn(secret, json.dumps(run["data"]))

    def test_initial_upload_saves_resolved_id_for_next_retry(self):
        self.jobs.queue_sync(self.filename)
        with patch.object(
            self.jobs.client,
            "upload_and_enable_configured_codex_oauth_credential",
            return_value={"uploaded": True, "enabled": True, "sub2api_account_id": 61},
        ):
            self.assertTrue(self.execute(self.rows()[0]["run_id"])["ok"])
        self.credential["access_token"] = "fixture-at-2"
        codex.save_codex_credential_record(self.filename, self.credential)
        self.jobs.queue_sync(self.filename)
        with patch.object(
            self.jobs.client,
            "update_and_enable_configured_account",
            create=True,
            return_value={"uploaded": True, "enabled": True, "sub2api_account_id": 61},
        ) as update:
            self.execute(self.rows()[0]["run_id"])
        self.assertEqual(61, update.call_args.args[1])

    def test_monitor_state_is_persistent_and_rejects_secret_fields(self):
        self.store.save_repair(
            "backend-a",
            self.account_id,
            stage="sync_wait",
            remote_account_ids=[41, 42],
            source_generation="digest",
            last_sync_generation="digest",
            next_attempt_at=None,
        )
        self.assertEqual([41, 42], self.store.get_repair("backend-a", self.account_id)["remote_account_ids"])
        self.assertEqual(1, len(self.store.list_repairs("backend-a")))
        with self.assertRaises(ValueError):
            self.store.save_repair("backend-a", self.account_id, access_token="must-not-persist")

    def test_failure_after_credential_changes_keeps_new_generation_pending(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        old = self.rows()[0]

        def replace_then_fail(*args, **kwargs):
            self.credential["access_token"] = "fixture-at-2"
            codex.save_codex_credential_record(self.filename, self.credential)
            raise self.jobs.client.Sub2ApiSyncError("upload", "sub2api_timeout", "模拟超时")

        with patch.object(
            self.jobs.client, "update_and_enable_configured_account", create=True, side_effect=replace_then_fail
        ):
            self.execute(old["run_id"])
        row = self.rows()[0]
        self.assertEqual(self.jobs.credential_generation(self.credential), row["generation"])
        self.assertIsNone(row["error_code"])
        self.assertFalse(codex.list_codex_accounts()[0].get("sub2_sync_error"))

    def test_expected_old_backend_blocks_new_backend_upload(self):
        result = self.jobs.queue_sync(self.filename, remote_account_ids=[41], expected_backend="backend-old")
        self.assertEqual("blocked_backend", result["items"][0]["status"])
        self.assertIsNone(result["run_id"])

    def test_completed_generation_is_idempotent_for_monitor(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        with patch.object(
            self.jobs.client,
            "update_and_enable_configured_account",
            create=True,
            return_value={"uploaded": True, "enabled": True, "sub2api_account_id": 41},
        ):
            self.execute(self.rows()[0]["run_id"])
        before = self.rows()[0]
        result = self.jobs.queue_sync(self.filename, remote_account_ids=[41], trigger="monitor")
        self.assertFalse(result["pending"])
        self.assertEqual(before["run_id"], result["run_id"])
        self.assertEqual("success", self.rows()[0]["status"])

    def test_status_only_exposes_safe_aggregate(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        current = self.jobs.status()
        self.assertEqual({"queued": 1}, current["counts"])
        self.assertEqual(1, current["total"])
        self.assertNotIn("items", current)
        self.assertNotIn(self.credential["email"], json.dumps(current))

    def test_local_account_temporarily_missing_can_resume_same_generation(self):
        with patch.object(self.jobs.codex, "get_account_by_email", return_value=None):
            self.jobs.queue_sync(self.filename, remote_account_ids=[41], trigger="monitor")
        pending = self.rows()[0]
        self.assertEqual("sub2api_local_account_missing", pending["error_code"])
        self.jobs.queue_sync(self.filename, remote_account_ids=[41], trigger="monitor")
        self.assertEqual("queued", self.rows()[0]["status"])

    def test_monitor_switch_keeps_retry_producer_enabled(self):
        from config import sub2api as cfg

        with patch.object(cfg, "SUB2API_SYNC_RETRY_ENABLED", False), patch.object(cfg, "SUB2API_MONITOR_ENABLED", True):
            self.assertTrue(self.jobs._enabled())
        with (
            patch.object(cfg, "SUB2API_SYNC_RETRY_ENABLED", False),
            patch.object(cfg, "SUB2API_MONITOR_ENABLED", False),
        ):
            self.assertFalse(self.jobs._enabled())

    def test_repair_lock_is_exclusive_and_released(self):
        with self.store.repair_lock("backend-a", self.account_id) as acquired:
            self.assertTrue(acquired)
            with ThreadPoolExecutor(max_workers=1) as pool:

                def attempt():
                    with self.store.repair_lock("backend-a", self.account_id) as nested:
                        return nested

                self.assertFalse(pool.submit(attempt).result())
        with self.store.repair_lock("backend-a", self.account_id) as acquired:
            self.assertTrue(acquired)

    def test_cancelled_worker_stays_cancelled_until_manual_retry(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        run_id = self.rows()[0]["run_id"]

        def cancel_before_request(auth, remote_id, **kwargs):
            operation.request_run_cancel(run_id, reason="用户取消补传")
            kwargs["checkpoint"]()

        with patch.object(
            self.jobs.client, "update_and_enable_configured_account", create=True, side_effect=cancel_before_request
        ):
            self.execute(run_id)
        self.jobs.enqueue_due()
        self.assertEqual("cancelled", self.rows()[0]["status"])
        self.assertEqual(run_id, self.rows()[0]["run_id"])
        self.jobs.queue_sync(self.filename, remote_account_ids=[41], trigger="manual")
        self.assertEqual("queued", self.rows()[0]["status"])
        self.assertNotEqual(run_id, self.rows()[0]["run_id"])

    def test_terminal_cancelled_run_is_not_recovered_as_pending(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        operation.finish_run(self.rows()[0]["run_id"], status="cancelled")
        self.jobs.enqueue_due()
        self.assertEqual("cancelled", self.rows()[0]["status"])

    def test_explicit_pending_drains_with_global_switches_off_without_repeating_failure(self):
        from config import sub2api as cfg
        from core.storage import postgres

        parent = task_gateway.submit_durable_operation(
            task_type="codex_token_refresh", account_id=self.account_id, email=self.credential["email"], dispatch=False
        )
        with (
            patch.object(cfg, "SUB2API_SYNC_RETRY_ENABLED", False),
            patch.object(cfg, "SUB2API_MONITOR_ENABLED", False),
        ):
            self.jobs.queue_sync(self.filename, remote_account_ids=[41])
            self.assertTrue(self.jobs._scheduler_ready())
            operation.finish_run(parent["run_id"], status="success")
            self.jobs.enqueue_due()
            row = self.rows()[0]
            with patch.object(
                self.jobs.client,
                "update_and_enable_configured_account",
                create=True,
                side_effect=self.jobs.client.Sub2ApiSyncError("upload", "sub2api_timeout", "模拟超时"),
            ):
                self.execute(row["run_id"])
            self.assertFalse(self.jobs._scheduler_ready())
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {postgres.qualified('sub2api_sync_jobs')} SET next_attempt_at=now()")
            self.assertEqual(0, self.jobs.enqueue_due()["queued"])
            self.jobs.queue_sync(self.filename, remote_account_ids=[41], trigger="manual")
            self.assertEqual("queued", self.rows()[0]["status"])

    def test_archived_account_is_blocked_before_dispatch_even_for_manual(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {"archived": True})
        result = self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        self.assertEqual("blocked_archived", result["items"][0]["status"])
        self.assertIsNone(result["run_id"])

    def test_archived_credential_is_rechecked_by_worker(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        codex.archive_codex(self.filename, True)
        with patch.object(self.jobs.client, "update_and_enable_configured_account", create=True) as update:
            self.execute(self.rows()[0]["run_id"])
        update.assert_not_called()
        self.assertEqual("blocked_archived", self.rows()[0]["status"])
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        self.assertEqual("blocked_archived", self.rows()[0]["status"])

    def test_renamed_credential_uses_stable_reference(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        row = self.rows()[0]
        credential = records.get_row_by(records.CODEX_CREDENTIALS, "filename", self.filename)
        new_name = "codex-sync-job@example.test-plus.json"
        records.patch_row(records.CODEX_CREDENTIALS, credential["id"], {"filename": new_name})
        with patch.object(
            self.jobs.client,
            "update_and_enable_configured_account",
            create=True,
            return_value={"uploaded": True, "enabled": True, "sub2api_account_id": 41},
        ) as update:
            self.assertTrue(self.execute(row["run_id"])["ok"])
        self.assertEqual(self.credential, update.call_args.args[0])
        current = self.store.list_jobs()[0]
        self.assertEqual((new_name, "success"), (current["filename"], current["status"]))

    def test_deleted_credential_is_blocked_without_infinite_recovery(self):
        self.jobs.queue_sync(self.filename, remote_account_ids=[41])
        row = self.rows()[0]
        credential = records.get_row_by(records.CODEX_CREDENTIALS, "filename", self.filename)
        records.delete_rows(records.CODEX_CREDENTIALS, [credential["id"]])
        with patch.object(self.jobs.client, "update_and_enable_configured_account", create=True) as update:
            self.execute(row["run_id"])
        update.assert_not_called()
        self.jobs.enqueue_due()
        self.assertEqual("blocked_missing_credential", self.rows()[0]["status"])
        self.assertEqual(row["run_id"], self.rows()[0]["run_id"])

    def test_invalid_configuration_does_not_interrupt_runtime_startup(self):
        with (
            patch.object(self.jobs, "_STARTED", False),
            patch.object(self.jobs, "_enabled", return_value=True),
            patch.object(
                self.jobs,
                "enqueue_due",
                side_effect=self.jobs.client.Sub2ApiSyncError(
                    "configuration", "sub2api_config_invalid", "模拟配置为空"
                ),
            ),
            patch.object(self.jobs.threading, "Thread") as thread,
            self.assertLogs(self.jobs.logger, level="WARNING") as logged,
        ):
            self.assertTrue(self.jobs.start_periodic_sync())
            thread.return_value.start.assert_called_once()
            self.assertTrue(self.jobs._STARTED)
            self.assertIn("sub2api_config_invalid", " ".join(logged.output))
            self.assertIn("sub2api_sync", task_gateway.registered_operation_types())
