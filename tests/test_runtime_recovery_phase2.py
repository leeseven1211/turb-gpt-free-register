# -*- coding: utf-8 -*-
"""Cross-model startup recovery fences for the phase-two migration."""
from __future__ import annotations

from unittest.mock import patch

from core import db, postgres_store, record_store
from core.operations import legacy_task_store
from core.storage import operation, registration
from tests.support_pg import PostgresTestCase
from webui import runtime


class RuntimeRecoveryFenceTests(PostgresTestCase):
    """A durable row for one account must not suppress unrelated legacy rows."""

    def setUp(self):
        operation.reset_ready()
        operation.init()
        registration.reset_ready()
        registration.init()
        self.legacy_schema = patch.object(legacy_task_store, "_SCHEMA", self.schema)
        self.legacy_ready = patch.object(legacy_task_store, "_READY_KEY", "")
        self.legacy_sync = patch.object(legacy_task_store, "_sync_operation_task")
        self.legacy_schema.start()
        self.legacy_ready.start()
        self.legacy_sync.start()
        legacy_task_store.init()

    def tearDown(self):
        self.legacy_sync.stop()
        self.legacy_ready.stop()
        self.legacy_schema.stop()
        operation.reset_ready()
        registration.reset_ready()

    def _account(self, label: str) -> int:
        return record_store.insert_row(record_store.ACCOUNTS, {
            "email": f"recovery-{label}@example.test",
            "live_check_status": "running",
            "created_at": "2026-09-14T10:00:00",
            "updated_at": "2026-09-14T10:00:00",
        })

    def test_native_queued_account_fences_only_matching_legacy_rows(self):
        account_a = self._account("a")
        account_b = self._account("b")
        native = operation.create_runtime_task(
            task_type="live_check",
            account_id=account_a,
            email="recovery-a@example.test",
            source_system="native_operations",
            source_id="native-live-recovery-a",
        )

        fence = runtime._legacy_recovery_exclusions(
            ("live_check", "token_refresh"),
            legacy_source_systems=(),
        )
        self.assertFalse(fence["skip_all"])
        self.assertEqual([account_a], fence["account_ids"])
        self.assertEqual([], fence["source_ids"])

        recovered_accounts = db.recover_interrupted_live_checks(
            excluded_account_ids=fence["account_ids"],
        )
        self.assertEqual(1, recovered_accounts)
        self.assertEqual("running", record_store.get_row(record_store.ACCOUNTS, account_a)["live_check_status"])
        self.assertEqual("failed", record_store.get_row(record_store.ACCOUNTS, account_b)["live_check_status"])
        self.assertEqual("queued", operation.get_run(int(native["run"]["id"]))["status"])

        legacy_a = legacy_task_store.create_task(
            task_type="live_check", account_id=account_a,
            email="recovery-a@example.test", trigger="startup",
        )
        legacy_b = legacy_task_store.create_task(
            task_type="live_check", account_id=account_b,
            email="recovery-b@example.test", trigger="startup",
        )
        legacy_task_store.start_task(legacy_a)
        legacy_task_store.start_task(legacy_b)
        recovered_tasks = legacy_task_store.recover_interrupted(
            excluded_account_ids=fence["account_ids"],
        )
        self.assertEqual(1, recovered_tasks)
        self.assertEqual("running", legacy_task_store.get_task(legacy_a)["status"])
        self.assertEqual("interrupted", legacy_task_store.get_task(legacy_b)["status"])

    def test_native_numeric_source_id_does_not_fence_other_legacy_source_namespace(self):
        account_a = self._account("native-source-a")
        account_b = self._account("legacy-source-b")
        legacy_b = legacy_task_store.create_task(
            task_type="live_check", account_id=account_b,
            email="recovery-legacy-source-b@example.test", trigger="startup",
        )
        legacy_task_store.start_task(legacy_b)
        native = operation.create_runtime_task(
            task_type="live_check",
            account_id=account_a,
            email="recovery-native-source-a@example.test",
            source_system="native_operations",
            source_id=str(legacy_b),
        )

        fence = runtime._legacy_recovery_exclusions(
            ("live_check",),
            legacy_source_systems=("account_action_tasks",),
        )
        self.assertEqual([account_a], fence["account_ids"])
        self.assertEqual([], fence["source_ids"])

        recovered = legacy_task_store.recover_interrupted(
            excluded_account_ids=fence["account_ids"],
            excluded_source_ids=fence["source_ids"],
        )
        self.assertEqual(1, recovered)
        self.assertEqual("interrupted", legacy_task_store.get_task(legacy_b)["status"])
        self.assertEqual("queued", operation.get_run(int(native["run"]["id"]))["status"])

    def test_native_registration_source_id_requires_explicit_job_mapping(self):
        account_a = self._account("native-registration-source-a")
        account_b = self._account("legacy-registration-source-b")
        job_b = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "namespace-registration-b",
            "email": "recovery-legacy-registration-b@example.test",
            "status": "running",
            "job_type": "registration_resume",
            "account_id": account_b,
        })
        native = operation.create_runtime_task(
            task_type="registration_resume",
            account_id=account_a,
            email="recovery-native-registration-a@example.test",
            source_system="webui_runtime",
            source_id=str(job_b),
        )

        fence = runtime._legacy_recovery_exclusions(
            ("registration_resume",),
            legacy_source_systems=("registration_jobs",),
        )
        self.assertEqual([account_a], fence["account_ids"])
        self.assertEqual([], fence["source_ids"])

        with patch.object(db, "_sync_operation_job"):
            recovered = db.recover_interrupted_registration_jobs(
                excluded_account_ids=fence["account_ids"],
                excluded_source_ids=fence["source_ids"],
            )
        self.assertEqual(1, recovered)
        self.assertEqual("interrupted", record_store.get_row(record_store.JOBS, job_b)["status"])
        self.assertEqual("queued", operation.get_run(int(native["run"]["id"]))["status"])

    def test_registration_recovery_excludes_native_account_but_closes_other_account(self):
        account_a = self._account("registration-a")
        account_b = self._account("registration-b")
        job_a = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "recovery-registration-a",
            "email": "recovery-registration-a@example.test",
            "status": "running",
            "job_type": "registration_resume",
            "account_id": account_a,
        })
        job_b = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "recovery-registration-b",
            "email": "recovery-registration-b@example.test",
            "status": "running",
            "job_type": "registration_resume",
            "account_id": account_b,
        })
        attempt_a = registration.ensure_attempt_for_job(job_a)
        attempt_b = registration.ensure_attempt_for_job(job_b)
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('registration_attempts')} SET account_id=%s WHERE id=%s",
                (account_a, int(attempt_a["id"])),
            )
            cur.execute(
                f"UPDATE {postgres_store.qualified('registration_attempts')} SET account_id=%s WHERE id=%s",
                (account_b, int(attempt_b["id"])),
            )
        run_a = registration.start_run(int(attempt_a["id"]), job_id=job_a)
        run_b = registration.start_run(int(attempt_b["id"]), job_id=job_b)
        native = operation.create_runtime_task(
            task_type="registration_resume",
            account_id=account_a,
            email="recovery-registration-a@example.test",
            source_system="webui_runtime",
            source_id="registration-resume-a",
            data={"source_job_id": str(job_a)},
        )
        fence = runtime._legacy_recovery_exclusions(
            ("registration_resume",),
            legacy_source_systems=("registration_jobs",),
        )
        self.assertEqual([account_a], fence["account_ids"])
        self.assertIn(str(job_a), fence["source_ids"])

        with patch.object(db, "_sync_operation_job"):
            recovered = db.recover_interrupted_registration_jobs(
                excluded_account_ids=fence["account_ids"],
                excluded_source_ids=fence["source_ids"],
            )

        self.assertEqual(1, recovered)
        self.assertEqual("running", record_store.get_row(record_store.JOBS, job_a)["status"])
        self.assertEqual("interrupted", record_store.get_row(record_store.JOBS, job_b)["status"])
        self.assertEqual("queued", registration.get_run(int(run_a["id"]))["status"])
        self.assertEqual("interrupted", registration.get_run(int(run_b["id"]))["status"])
        self.assertEqual("queued", operation.get_run(int(native["run"]["id"]))["status"])


if __name__ == "__main__":
    import unittest

    unittest.main()
