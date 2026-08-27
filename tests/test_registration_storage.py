# -*- coding: utf-8 -*-
"""RegistrationAttempt/Run/Checkpoint storage contract tests."""
from __future__ import annotations

import unittest

from core import db, record_store
from core.storage import registration
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


if __name__ == "__main__":
    unittest.main()
