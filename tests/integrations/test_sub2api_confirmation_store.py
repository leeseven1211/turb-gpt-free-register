"""Sub2API 成功回执与失效目标对账的隔离存储测试。"""

from __future__ import annotations

from unittest.mock import Mock, patch

from core.storage import records
from core.storage import sub2api as store
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class Sub2ApiConfirmationStoreTests(PostgresTestCase):
    def setUp(self):
        operation.reset_ready()
        operation.init()
        store.init()
        self.backend = "backend-confirmation"
        self.email = "confirm@example.test"
        self.filename = "codex-confirm@example.test-plus.json"
        self.provider_account_id = "provider-confirm-1"
        self.local_account_id = records.insert_row(
            records.ACCOUNTS,
            {"email": self.email, "account_status": "active"},
        )
        self.credential_id = records.insert_row(
            records.CODEX_CREDENTIALS,
            {
                "filename": self.filename,
                "email": self.email,
                "account_id": self.provider_account_id,
                "archived": False,
                "content": {
                    "email": self.email,
                    "account_id": self.provider_account_id,
                    "access_token": "fixture-access",
                    "refresh_token": "fixture-refresh",
                },
            },
        )
        credential = records.get_row(records.CODEX_CREDENTIALS, self.credential_id)
        self.generation = store.credential_generation(credential["content"])
        self.run_id = operation.create_runtime_task(
            task_type="sub2api_sync", account_id=self.local_account_id, email=self.email,
        )["run"]["id"]

    def _queue(self, remote_id: int, *, trigger: str = "monitor"):
        rows = store.queue(
            self.filename,
            backend=self.backend,
            generation=self.generation,
            account_id=self.local_account_id,
            email=self.email,
            credential_id=self.credential_id,
            remote_account_ids=[remote_id],
            trigger=trigger,
        )
        return rows[0]

    def _set_job(self, job_id: int, **changes):
        from core.storage import postgres

        assignments = ", ".join(f"{key}=%s" for key in changes)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres.qualified('sub2api_sync_jobs')} "
                f"SET {assignments} WHERE id=%s",
                (*changes.values(), job_id),
            )

    def _save_repair(self, targets, *, stage="sync_wait"):
        return store.save_repair(
            self.backend,
            self.local_account_id,
            stage=stage,
            remote_account_ids=list(targets),
            source_generation=self.generation,
        )

    def test_confirm_sync_records_one_success_for_same_target_idempotently(self):
        self.assertTrue(
            store.confirm_sync(
                credential_id=self.credential_id,
                backend=self.backend,
                generation=self.generation,
                remote_account_id=1544,
                count_upload=True,
            )
        )
        self.assertTrue(
            store.confirm_sync(
                credential_id=self.credential_id,
                backend=self.backend,
                generation=self.generation,
                remote_account_id=1544,
                count_upload=True,
            )
        )

        rows = store.list_jobs(backend=self.backend)
        self.assertEqual(1, len(rows))
        self.assertEqual(("success", "complete", 1544), (rows[0]["status"], rows[0]["stage"], rows[0]["remote_account_id"]))
        credential = records.get_row(records.CODEX_CREDENTIALS, self.credential_id)
        self.assertEqual(1, credential["sub2_uploaded_count"])

    def test_confirm_replacement_supersedes_old_job_and_closes_repair(self):
        old = self._queue(1534)
        self._set_job(
            old["id"],
            status="pending",
            stage="resolve_account",
            error_code="sub2api_account_missing",
            error="目标账号已不存在",
            run_id=self.run_id,
        )
        self._save_repair([1534])

        self.assertTrue(
            store.confirm_sync(
                credential_id=self.credential_id,
                backend=self.backend,
                generation=self.generation,
                remote_account_id=1544,
                replaced_job_id=old["id"],
                replaced_run_id=self.run_id,
            )
        )

        jobs = {row["id"]: row for row in store.list_jobs(backend=self.backend)}
        self.assertEqual(("superseded", "superseded", 1534), (
            jobs[old["id"]]["status"],
            jobs[old["id"]]["stage"],
            jobs[old["id"]]["remote_account_id"],
        ))
        replacement = next(row for row in jobs.values() if row["remote_account_id"] == 1544)
        self.assertEqual(("success", "complete"), (replacement["status"], replacement["stage"]))
        repair = store.get_repair(self.backend, self.local_account_id)
        self.assertEqual(("idle", [1544]), (repair["stage"], repair["remote_account_ids"]))

    def test_confirmation_reuses_initial_upload_job_with_zero_target_key(self):
        initial = store.queue(
            self.filename, backend=self.backend, generation=self.generation,
            account_id=self.local_account_id, email=self.email,
            credential_id=self.credential_id,
        )[0]
        self._set_job(initial["id"], remote_account_id=1544, status="running", run_id=self.run_id)
        self.assertTrue(store.confirm_sync(
            credential_id=self.credential_id, backend=self.backend, generation=self.generation,
            remote_account_id=1544, count_upload=True,
        ))
        jobs = store.list_jobs(backend=self.backend)
        self.assertEqual(1, len(jobs))
        self.assertEqual(initial["id"], jobs[0]["id"])
        self.assertEqual("success", jobs[0]["status"])
        self.assertIsNone(jobs[0]["run_id"])

    def test_cancelled_run_prevents_replacement_even_before_job_cancellation(self):
        old = self._queue(1534)
        self._set_job(old["id"], status="running", run_id=self.run_id)
        self._save_repair([1534])
        operation.request_run_cancel(self.run_id, reason="用户取消补传")
        self.assertFalse(store.confirm_sync(
            credential_id=self.credential_id, backend=self.backend, generation=self.generation,
            remote_account_id=1544, replaced_job_id=old["id"], replaced_run_id=self.run_id,
        ))
        jobs = store.list_jobs(backend=self.backend)
        self.assertEqual([(1534, "running")], [
            (row["remote_account_id"], row["status"]) for row in jobs
        ])
        self.assertEqual([1534], store.get_repair(self.backend, self.local_account_id)["remote_account_ids"])

    def test_readonly_confirmation_counts_first_real_upload_once(self):
        arguments = dict(
            credential_id=self.credential_id, backend=self.backend, generation=self.generation,
            remote_account_id=1544,
        )
        self.assertTrue(store.confirm_sync(**arguments))
        self.assertTrue(store.confirm_sync(**arguments, count_upload=True))
        self.assertTrue(store.confirm_sync(**arguments, count_upload=True))
        credential = records.get_row(records.CODEX_CREDENTIALS, self.credential_id)
        self.assertEqual(1, credential["sub2_uploaded_count"])

    def test_replacement_clears_only_resolved_missing_target_error_without_counting_upload(self):
        old = self._queue(1534)
        self._set_job(old["id"], status="running", run_id=self.run_id)
        records.patch_row(
            records.CODEX_CREDENTIALS, self.credential_id,
            {"sub2_sync_error": "sub2api_account_missing: 目标账号已不存在"},
        )
        self.assertTrue(store.confirm_sync(
            credential_id=self.credential_id, backend=self.backend, generation=self.generation,
            remote_account_id=1544, replaced_job_id=old["id"], replaced_run_id=self.run_id,
        ))
        credential = records.get_row(records.CODEX_CREDENTIALS, self.credential_id)
        self.assertIsNone(credential.get("sub2_sync_error"))
        self.assertEqual(0, int(credential.get("sub2_uploaded_count") or 0))

    def test_busy_job_lock_rolls_back_confirmation_without_blocking(self):
        from core.storage import postgres

        old = self._queue(1534)
        self._set_job(old["id"], status="running", run_id=self.run_id)
        with postgres.connect() as blocker, blocker.cursor() as blocked:
            blocked.execute(
                f"SELECT 1 FROM {postgres.qualified('sub2api_sync_jobs')} WHERE id=%s FOR UPDATE",
                (old["id"],),
            )
            self.assertFalse(store.confirm_sync(
                credential_id=self.credential_id, backend=self.backend, generation=self.generation,
                remote_account_id=1544, replaced_job_id=old["id"], replaced_run_id=self.run_id,
            ))
        self.assertEqual([(1534, "running")], [
            (row["remote_account_id"], row["status"]) for row in store.list_jobs(backend=self.backend)
        ])

    def test_busy_monitor_lock_does_not_overwrite_repair_snapshot(self):
        old = self._queue(1534)
        self._set_job(old["id"], status="running", run_id=self.run_id)
        self._save_repair([1534])
        with store.repair_lock(self.backend, self.local_account_id) as acquired:
            self.assertTrue(acquired)
            self.assertFalse(store.confirm_sync(
                credential_id=self.credential_id, backend=self.backend, generation=self.generation,
                remote_account_id=1544, replaced_job_id=old["id"], replaced_run_id=self.run_id,
            ))
        self.assertEqual([1534], store.get_repair(self.backend, self.local_account_id)["remote_account_ids"])

    def test_confirm_replacement_keeps_other_targets_until_all_are_successful(self):
        old = self._queue(1534)
        other = self._queue(1550)
        self._set_job(old["id"], status="pending", stage="resolve_account", run_id=self.run_id)
        self._set_job(other["id"], status="pending", stage="resolve_account", run_id=self.run_id)
        self._save_repair([1534, 1550])
        records.patch_row(
            records.CODEX_CREDENTIALS, self.credential_id,
            {"sub2_sync_error": "sub2api_account_missing: 其他目标仍然不存在"},
        )

        self.assertTrue(
            store.confirm_sync(
                credential_id=self.credential_id,
                backend=self.backend,
                generation=self.generation,
                remote_account_id=1544,
                replaced_job_id=old["id"],
                replaced_run_id=self.run_id,
            )
        )
        repair = store.get_repair(self.backend, self.local_account_id)
        self.assertEqual(("sync_wait", [1544, 1550]), (repair["stage"], repair["remote_account_ids"]))
        credential = records.get_row(records.CODEX_CREDENTIALS, self.credential_id)
        self.assertEqual("sub2api_account_missing: 其他目标仍然不存在", credential["sub2_sync_error"])

    def test_orphan_credential_uses_content_email_for_success_receipt(self):
        content = {"email": "orphan@example.test", "access_token": "fixture-orphan"}
        credential_id = records.insert_row(
            records.CODEX_CREDENTIALS,
            {"filename": "codex-orphan@example.test-free.json", "content": content},
        )
        self.assertTrue(store.confirm_sync(
            credential_id=credential_id, backend=self.backend, generation=store.credential_generation(content),
            remote_account_id=1560, count_upload=True,
        ))
        job = store.list_jobs(filename="codex-orphan@example.test-free.json")[0]
        self.assertEqual("orphan@example.test", job["email"])
        self.assertIsNone(job["account_id"])

    def test_metadata_failure_rolls_back_success_job_and_counter_together(self):
        arguments = dict(
            credential_id=self.credential_id, backend=self.backend, generation=self.generation,
            remote_account_id=1544, count_upload=True,
        )
        with patch.object(records, "patch_row", side_effect=RuntimeError("模拟元数据写入失败")):
            with self.assertRaises(RuntimeError):
                store.confirm_sync(**arguments)
        self.assertEqual([], store.list_jobs(backend=self.backend))
        self.assertTrue(store.confirm_sync(**arguments))
        credential = records.get_row(records.CODEX_CREDENTIALS, self.credential_id)
        self.assertEqual(1, credential["sub2_uploaded_count"])

    def test_confirm_sync_rejects_stale_generation_but_allows_orphan_success(self):
        self.assertFalse(
            store.confirm_sync(
                credential_id=self.credential_id,
                backend=self.backend,
                generation="stale-generation",
                remote_account_id=1544,
            )
        )
        newer = {
            **records.get_row(records.CODEX_CREDENTIALS, self.credential_id)["content"],
            "account_id": "",
        }
        records.patch_row(records.CODEX_CREDENTIALS, self.credential_id, {"content": newer})
        self.assertTrue(
            store.confirm_sync(
                credential_id=self.credential_id,
                backend=self.backend,
                generation=store.credential_generation(newer),
                remote_account_id=1544,
            )
        )

    def test_replacement_requires_provider_identity_and_local_account(self):
        old = self._queue(1534)
        self._set_job(old["id"], status="pending", stage="resolve_account", run_id=self.run_id)
        self._save_repair([1534])
        records.patch_row(
            records.CODEX_CREDENTIALS,
            self.credential_id,
            {"content": {**records.get_row(records.CODEX_CREDENTIALS, self.credential_id)["content"], "account_id": ""}},
        )
        self.assertFalse(
            store.confirm_sync(
                credential_id=self.credential_id,
                backend=self.backend,
                generation=store.credential_generation(
                    records.get_row(records.CODEX_CREDENTIALS, self.credential_id)["content"]
                ),
                remote_account_id=1544,
                replaced_job_id=old["id"],
                replaced_run_id=self.run_id,
            )
        )

    def test_replacement_uses_execution_fence_and_cannot_replace_cancelled_job(self):
        old = self._queue(1534)
        self._set_job(old["id"], status="pending", stage="resolve_account", run_id=self.run_id)
        self._save_repair([1534])
        fence = {"execution_id": "execution-1", "lease_token": "lease-1"}
        with patch.object(operation, "fence_execution") as fence_execution:
            self.assertTrue(
                store.confirm_sync(
                    credential_id=self.credential_id,
                    backend=self.backend,
                    generation=self.generation,
                    remote_account_id=1544,
                    replaced_job_id=old["id"],
                    replaced_run_id=self.run_id,
                    fence=fence,
                )
            )
        fence_execution.assert_called_once()

        cancelled = self._queue(1551)
        self._set_job(cancelled["id"], status="cancelled", stage="cancelled", run_id=self.run_id)
        self.assertFalse(
            store.confirm_sync(
                credential_id=self.credential_id,
                backend=self.backend,
                generation=self.generation,
                remote_account_id=1552,
                replaced_job_id=cancelled["id"],
                replaced_run_id=self.run_id,
            )
        )

    def test_finish_does_not_let_superseded_worker_write_metadata_or_pending(self):
        old = self._queue(1534)
        self._set_job(old["id"], status="superseded", stage="superseded", run_id=self.run_id)
        metadata = Mock()

        self.assertFalse(
            store.finish(
                old["id"],
                generation=self.generation,
                run_id=self.run_id,
                status="pending",
                stage="resolve_account",
                error_code="late-error",
                write_metadata=metadata,
            )
        )
        metadata.assert_not_called()
        self.assertEqual("superseded", store.list_jobs(backend=self.backend)[0]["status"])

    def test_queue_does_not_revive_superseded_target_without_manual_trigger(self):
        old = self._queue(1534)
        self._set_job(old["id"], status="superseded", stage="superseded")

        rows = store.queue(
            self.filename,
            backend=self.backend,
            generation=self.generation,
            account_id=self.local_account_id,
            email=self.email,
            credential_id=self.credential_id,
            remote_account_ids=[1534],
            trigger="sub2api_monitor",
        )
        self.assertEqual("superseded", rows[0]["status"])
        self.assertEqual("superseded", store.list_jobs(backend=self.backend)[0]["status"])

        manual = store.queue(
            self.filename,
            backend=self.backend,
            generation=self.generation,
            account_id=self.local_account_id,
            email=self.email,
            credential_id=self.credential_id,
            remote_account_ids=[1534],
            trigger="manual",
        )
        self.assertEqual("pending", manual[0]["status"])

    def test_queue_does_not_revive_superseded_target_for_new_generation(self):
        old = self._queue(1534)
        self._set_job(old["id"], status="superseded", stage="superseded")
        newer = {**records.get_row(records.CODEX_CREDENTIALS, self.credential_id)["content"], "access_token": "new-access"}
        records.patch_row(records.CODEX_CREDENTIALS, self.credential_id, {"content": newer})
        new_generation = store.credential_generation(newer)

        rows = store.queue(
            self.filename,
            backend=self.backend,
            generation=new_generation,
            account_id=self.local_account_id,
            email=self.email,
            credential_id=self.credential_id,
            remote_account_ids=[1534],
            trigger="sub2api_monitor",
        )
        self.assertEqual("superseded", rows[0]["status"])
        self.assertEqual("superseded", store.list_jobs(backend=self.backend)[0]["status"])

    def test_save_repair_applies_confirmed_replacement_mapping_to_stale_snapshot(self):
        self._save_repair([1534, 1550])
        store.save_repair(
            self.backend,
            self.local_account_id,
            superseded_targets={"1534": 1544},
        )
        repair = store.save_repair(
            self.backend,
            self.local_account_id,
            stage="sync_wait",
            remote_account_ids=[1534, 1550],
        )
        self.assertEqual([1544, 1550], repair["remote_account_ids"])
        self.assertEqual({"1534": 1544}, repair["superseded_targets"])
        store.save_repair(self.backend, self.local_account_id, superseded_targets={"1544": 1560})
        repair = store.save_repair(
            self.backend, self.local_account_id, remote_account_ids=[1534, 1544, 1550],
        )
        self.assertEqual([1560, 1550], repair["remote_account_ids"])
