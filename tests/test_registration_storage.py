# -*- coding: utf-8 -*-
"""RegistrationAttempt/Run/Checkpoint storage contract tests."""
from __future__ import annotations

import json
import unittest

from core import db, postgres_store, record_store
from core.storage import operation, registration
from tests.support_pg import PostgresTestCase


class RegistrationFactsTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()

    def _job(self, email: str = "attempt@example.test") -> int:
        return record_store.insert_row(record_store.JOBS, {
            "job_uuid": f"job-{email}", "email": email, "status": "pending",
            "job_type": "registration",
        })

    def test_job_links_one_attempt_and_retries_add_runs(self):
        job_id = self._job()
        attempt = registration.ensure_attempt_for_job(job_id)
        self.assertEqual(attempt["checkpoint"], "created")
        linked = record_store.get_row(record_store.JOBS, job_id)
        self.assertEqual(int(linked["attempt_id"]), int(attempt["id"]))

        first = registration.start_run(int(attempt["id"]), job_id=job_id)
        registration.finish_run(int(first["id"]), status="failed", error_code="network_timeout")
        second = registration.retry_run(int(attempt["id"]), action_type="registration_resume")
        self.assertNotEqual(int(first["id"]), int(second["id"]))
        self.assertEqual(len(registration.list_runs(int(attempt["id"]))), 2)
        self.assertEqual(len({int(item["attempt_id"]) for item in registration.list_runs(int(attempt["id"]))}), 1)

    def test_legacy_create_job_writes_attempt_and_first_run(self):
        job = db.create_job("outlook")
        self.assertIsNotNone(job.get("attempt_id"))
        runs = registration.list_runs(int(job["attempt_id"]))
        self.assertEqual(len(runs), 1)
        self.assertEqual(int(runs[0]["job_id"]), int(job["id"]))

    def test_checkpoint_is_monotonic_and_event_is_idempotent(self):
        attempt = registration.create_attempt("checkpoint@example.test")
        attempt_id = int(attempt["id"])
        registration.advance_checkpoint(attempt_id, "email_claimed", event_uuid="event-1")
        registration.advance_checkpoint(attempt_id, "auth_started", event_uuid="event-2")
        with self.assertRaises(ValueError):
            registration.advance_checkpoint(attempt_id, "created")
        registration.advance_checkpoint(attempt_id, "auth_started", event_uuid="event-2")
        self.assertEqual(len(registration.events(attempt_id)), 2)

    def test_unknown_request_does_not_rewind_and_manual_reconcile_is_terminal(self):
        attempt = registration.create_attempt("unknown@example.test")
        attempt_id = int(attempt["id"])
        with self.assertRaises(ValueError):
            registration.mark_request_unknown(attempt_id, target="account")
        registration.advance_checkpoint(attempt_id, "account_request_started")
        unknown = registration.mark_request_unknown(attempt_id, target="account")
        self.assertEqual(unknown["checkpoint"], "account_request_started")
        self.assertEqual(unknown["remote_account_state"], "request_unknown")
        reconciled = registration.mark_manual_reconcile(attempt_id)
        self.assertEqual(reconciled["checkpoint"], "manual_reconcile")
        self.assertEqual(reconciled["target_status"], "manual_reconcile")

    def test_startup_recovery_only_changes_active_registration_runs(self):
        attempt = registration.create_attempt("recovery@example.test")
        run = registration.start_run(int(attempt["id"]), execution_id="worker-1")
        self.assertEqual(registration.recover_interrupted_runs(), 1)
        self.assertEqual(registration.get_run(int(run["id"]))["status"], "interrupted")
        self.assertEqual(registration.recover_interrupted_runs(), 0)

    def test_token_persists_core_account_immediately_and_repeated_call_is_idempotent(self):
        attempt = registration.create_attempt("token@example.test")
        result = registration.persist_core_account(
            int(attempt["id"]), access_token="at-1", account={"plan_type": "free"},
        )
        self.assertEqual(result["account"]["email"], "token@example.test")
        self.assertEqual(result["account"]["access_token"], "at-1")
        again = registration.persist_core_account(
            int(attempt["id"]), access_token="at-2", account={"plan_type": "plus"},
        )
        self.assertEqual(int(result["account_id"]), int(again["account_id"]))
        self.assertEqual(record_store.count_rows(record_store.ACCOUNTS), 1)
        self.assertEqual(registration.get_attempt(int(attempt["id"]))["local_account_state"], "persisted")

    def test_backfill_and_verify_are_idempotent(self):
        self._job("one@example.test")
        self._job("two@example.test")
        first = registration.backfill(apply=True)
        second = registration.backfill(apply=True)
        self.assertEqual(first["jobs"], 2)
        self.assertEqual(second["attempts"], 0)
        self.assertEqual(second["runs"], 0)
        verified = registration.verify()
        self.assertTrue(verified["ok"], verified)

    def test_legacy_registered_checkpoint_is_mapped_and_audited_once(self):
        attempt = registration.create_attempt("legacy-registered@example.test")
        attempt_id = int(attempt["id"])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified('registration_attempts')}
                SET checkpoint='registered', remote_identity_state='verified',
                    remote_account_state='created', local_account_state='saved',
                    target_status='account_available', data='{{}}'::jsonb
                WHERE id=%s
                """,
                (attempt_id,),
            )

        registration.reset_ready()
        registration.init()
        migrated = registration.get_attempt(attempt_id)
        self.assertEqual("core_persisted", migrated["checkpoint"])
        self.assertEqual("confirmed", migrated["remote_identity_state"])
        self.assertEqual("confirmed", migrated["remote_account_state"])
        self.assertEqual("persisted", migrated["local_account_state"])
        self.assertEqual("registered", migrated["data"]["legacy_registration_checkpoint"])
        self.assertEqual("core_persisted", migrated["data"]["checkpoint_migration"]["to"])
        events = registration.events(attempt_id)
        self.assertEqual(1, len([event for event in events if event["event_type"] == "checkpoint_migrated"]))

        registration.reset_ready()
        registration.init()
        events_again = registration.events(attempt_id)
        self.assertEqual(len(events), len(events_again))
        self.assertEqual(0, registration.verify()["checks"]["legacy_registered_checkpoints"])

    def test_legacy_unknown_defaults_normalize_without_rewinding_checkpoint(self):
        pending = registration.create_attempt("legacy-pending@example.test")
        advanced = registration.create_attempt("legacy-advanced@example.test")
        registration.advance_checkpoint(int(advanced["id"]), "account_confirmed")
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified('registration_attempts')}
                SET checkpoint='unknown', remote_identity_state='unknown',
                    remote_account_state='unknown', local_account_state='missing',
                    target_status='email_verification_pending', data='{{}}'::jsonb
                WHERE id=%s
                """,
                (int(pending["id"]),),
            )
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified('registration_attempts')}
                SET remote_identity_state='unknown', remote_account_state='unknown',
                    local_account_state='missing'
                WHERE id=%s
                """,
                (int(advanced["id"]),),
            )
        registration.reset_ready()
        registration.init()
        normalized = registration.get_attempt(int(pending["id"]))
        self.assertEqual("account_request_started", normalized["checkpoint"])
        self.assertEqual("confirmed", normalized["remote_identity_state"])
        self.assertEqual("request_unknown", normalized["remote_account_state"])
        self.assertEqual("none", normalized["local_account_state"])
        preserved = registration.get_attempt(int(advanced["id"]))
        self.assertEqual("account_confirmed", preserved["checkpoint"])

    def test_historical_child_jobs_get_unique_runs_and_stale_active_runs_reconcile(self):
        root_id = self._job("historical-root@example.test")
        child_ids = [
            record_store.insert_row(record_store.JOBS, {
                "job_uuid": f"historical-child-{index}",
                "email": "historical-root@example.test",
                "status": "failed", "job_type": "registration_resume",
                "root_job_id": root_id, "parent_job_id": root_id,
            })
            for index in range(32)
        ]
        registration.create_attempt("historical-root@example.test", root_job_id=root_id)
        first = registration.backfill(apply=True)
        self.assertEqual(33, first["runs"])
        self.assertEqual(0, registration.verify()["checks"]["jobs_without_run"])
        attempt = registration.get_attempt_by_job(root_id)
        runs = registration.list_runs(int(attempt["id"]), limit=100)
        self.assertEqual(33, len(runs))
        self.assertEqual(33, len({int(run["job_id"]) for run in runs}))
        self.assertEqual("queued", next(run for run in runs if int(run["job_id"]) == root_id)["status"])

        # Reproduce a stale queued child after the worker has released the root.
        root_run = next(run for run in runs if int(run["job_id"]) == root_id)
        registration.finish_run(int(root_run["id"]), status="success")
        child_run = next(run for run in runs if int(run["job_id"]) == child_ids[0])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('registration_runs')} SET status='queued', completed_at=NULL WHERE id=%s",
                (int(child_run["id"]),),
            )
        record_store.patch_row(record_store.JOBS, root_id, {"status": "success"})
        second = registration.backfill(apply=True)
        self.assertEqual(0, second["runs"])
        self.assertEqual("failed", registration.get_run(int(child_run["id"]))["status"])
        verified = registration.verify()
        self.assertTrue(verified["ok"], verified)
        self.assertEqual(0, verified["checks"]["terminal_jobs_with_active_run"])

    def test_operation_projection_emits_legal_checkpoint_and_preserves_legacy_value(self):
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": "runtime-registered@example.test", "access_token": "token-1",
            "extra_json": json.dumps({"registration_checkpoint": "registered"}),
        })
        job_id = self._job("runtime-registered@example.test")
        record_store.patch_row(record_store.JOBS, job_id, {"account_id": account_id, "status": "success"})
        operation.reset_ready()
        operation.sync_registration_job(job_id)
        attempt = registration.get_attempt_by_job(job_id)
        self.assertEqual("core_persisted", attempt["checkpoint"])
        self.assertEqual("registered", attempt["data"]["legacy_registration_checkpoint"])
        self.assertEqual(0, registration.verify()["checks"]["invalid_checkpoints"])


if __name__ == "__main__":
    unittest.main()
