# -*- coding: utf-8 -*-
"""RegistrationAttempt/Run/Checkpoint storage contract tests."""
from __future__ import annotations

import json
import unittest

from core import db, postgres_store, record_store
from core.storage import operation, registration
from core.registration.browser_submission import (
    BrowserSubmissionReceipt,
    record_browser_submission_fact,
    unresolved_submission_ids,
)
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

    def test_refreshed_otp_supersedes_original_fact_before_same_run_retry(self):
        from types import SimpleNamespace

        attempt = registration.create_attempt("otp-refresh@example.test")
        run = registration.start_run(int(attempt["id"]), execution_id="otp-refresh", initial_status="running")
        driver = SimpleNamespace(_registration_fact_context={
            "attempt_id": int(attempt["id"]), "run_id": int(run["id"]), "execution_id": "otp-refresh",
        })
        original = BrowserSubmissionReceipt(kind="otp", stage="email_otp", endpoint_kind="otp_submit")
        retry = BrowserSubmissionReceipt(kind="otp", stage="email_otp", endpoint_kind="otp_submit")
        record_browser_submission_fact(driver, "dispatch_intent", receipt=original)
        record_browser_submission_fact(driver, "unknown", receipt=original, result="unknown")
        with self.assertRaisesRegex(ValueError, "未决浏览器"):
            record_browser_submission_fact(driver, "dispatch_intent", receipt=retry)
        record_browser_submission_fact(
            driver, "superseded", receipt=original, result="unknown", error_type="otp_refresh_retry",
        )
        record_browser_submission_fact(driver, "dispatch_intent", receipt=retry)
        record_browser_submission_fact(driver, "unknown", receipt=retry, result="unknown")
        resend = BrowserSubmissionReceipt(kind="otp_resend", stage="otp_resend", endpoint_kind="otp_resend")
        with self.assertRaisesRegex(ValueError, "未决浏览器"):
            record_browser_submission_fact(driver, "dispatch_intent", receipt=resend)
        record_browser_submission_fact(driver, "rejected", receipt=retry, result="failure")
        record_browser_submission_fact(driver, "dispatch_intent", receipt=resend)
        private = registration.get_private_resume_context(int(attempt["id"]), email="otp-refresh@example.test")
        facts = private["submission_facts"]
        self.assertTrue(any(x["submission_id"] == original.submission_id and x["phase"] == "unknown" for x in facts))
        self.assertTrue(any(x["submission_id"] == original.submission_id and x["phase"] == "superseded"
                            and x["result"] == "unknown" for x in facts))
        self.assertEqual(unresolved_submission_ids(facts), {resend.submission_id})

    def test_superseding_is_limited_to_explicit_otp_refresh_retry(self):
        for kind, stage, endpoint, marker in (
            ("password", "password_create", "password_submit", "otp_refresh_retry"),
            ("otp", "email_otp", "otp_submit", ""),
            ("otp_resend", "otp_resend", "otp_resend", "otp_refresh_retry"),
        ):
            with self.subTest(kind=kind, marker=marker):
                receipt = BrowserSubmissionReceipt(kind=kind, stage=stage, endpoint_kind=endpoint)
                with self.assertRaisesRegex(ValueError, "只有验证码刷新后补交"):
                    receipt.safe_fact(phase="superseded", result="unknown", error_type=marker)

    def test_attempt_checkpoint_stays_monotonic_while_run_event_can_resume_earlier_stage(self):
        attempt = registration.create_attempt("checkpoint@example.test")
        attempt_id = int(attempt["id"])
        registration.advance_checkpoint(attempt_id, "email_claimed", event_uuid="event-1")
        registration.advance_checkpoint(attempt_id, "auth_started", event_uuid="event-2")
        preserved = registration.advance_checkpoint(attempt_id, "created", event_uuid="event-3")
        self.assertEqual(preserved["checkpoint"], "auth_started")
        registration.advance_checkpoint(attempt_id, "auth_started", event_uuid="event-2")
        events = registration.events(attempt_id)
        self.assertEqual(len(events), 3)
        resumed = next(item for item in events if item["event_uuid"] == "event-3")
        self.assertEqual(resumed["detail"]["attempt_checkpoint_preserved"], "auth_started")
        self.assertEqual(resumed["detail"]["run_checkpoint"], "created")

    def test_submission_fence_preserves_unresolved_fact_beyond_history_window(self):
        attempt = registration.create_attempt("submission-fence@example.test")
        attempt_id = int(attempt["id"])
        run = registration.start_run(
            attempt_id,
            execution_id="submission-fence-execution",
            initial_status="running",
        )
        run_id = int(run["id"])
        historical = [{
            "submission_id": "old-unknown", "kind": "email", "stage": "submit_email",
            "phase": "dispatch_intent", "endpoint_kind": "email_submit",
        }]
        historical.extend({
            "submission_id": f"closed-{index}", "kind": "email", "stage": "submit_email",
            "phase": "confirmed", "endpoint_kind": "email_submit",
        } for index in range(140))
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('registration_attempts')} "
                "SET private_context=%s::jsonb WHERE id=%s",
                (json.dumps({"submission_facts": historical}, ensure_ascii=False), attempt_id),
            )

        registration.record_submission_fact(
            attempt_id,
            submission_id="old-unknown",
            kind="email", stage="submit_email", phase="unknown",
            endpoint_kind="email_submit", result="unknown", run_id=run_id,
            execution_id="submission-fence-execution",
        )
        private = registration.get_private_resume_context(
            attempt_id, email="submission-fence@example.test",
        )
        facts = private.get("submission_facts") or []
        self.assertIn("old-unknown", unresolved_submission_ids(facts))

        registration.record_submission_fact(
            attempt_id,
            submission_id="old-unknown",
            kind="email", stage="submit_email", phase="confirmed",
            endpoint_kind="email_submit", result="success", run_id=run_id,
            execution_id="submission-fence-execution",
        )
        registration.record_submission_fact(
            attempt_id,
            submission_id="old-unknown",
            kind="email", stage="submit_email", phase="request_observed",
            endpoint_kind="email_submit", run_id=run_id,
            execution_id="submission-fence-execution",
        )
        loaded = registration.get_attempt(attempt_id)
        self.assertEqual("confirmed", (loaded.get("data") or {}).get("last_submission_phase"))

    def test_browser_submission_helper_persists_before_advancing_receipt_phase(self):
        attempt = registration.create_attempt("receipt-helper@example.test")
        attempt_id = int(attempt["id"])
        run = registration.start_run(
            attempt_id,
            execution_id="receipt-helper-execution",
            initial_status="running",
        )
        driver = type("Driver", (), {})()
        driver._registration_fact_context = {
            "attempt_id": attempt_id,
            "run_id": int(run["id"]),
            "execution_id": "receipt-helper-execution",
            "job_id": None,
        }
        receipt = BrowserSubmissionReceipt(
            kind="otp", stage="email_otp", endpoint_kind="otp_submit", http_method="POST",
        )
        driver._browser_submission_receipt = receipt
        record_browser_submission_fact(driver, "prepared", receipt=receipt)
        record_browser_submission_fact(driver, "dispatch_intent", receipt=receipt)
        self.assertEqual(receipt.phase, "dispatch_intent")
        record_browser_submission_fact(driver, "confirmed", receipt=receipt, result="success")
        record_browser_submission_fact(driver, "request_observed", receipt=receipt)
        self.assertEqual(receipt.phase, "confirmed")
        private = registration.get_private_resume_context(
            attempt_id, email="receipt-helper@example.test",
        )
        phases = [
            item["phase"] for item in private.get("submission_facts", [])
            if item.get("submission_id") == receipt.submission_id
        ]
        self.assertIn("dispatch_intent", phases)
        self.assertIn("confirmed", phases)

    def test_explicit_resume_login_can_create_new_email_submission_after_unknown(self):
        attempt = registration.create_attempt("resume-login@example.test")
        attempt_id = int(attempt["id"])
        run = registration.start_run(
            attempt_id,
            execution_id="resume-login-execution",
            initial_status="running",
            action_type="registration_resume",
        )
        run_id = int(run["id"])
        registration.save_password_checkpoint(
            attempt_id,
            email="resume-login@example.test",
            password="SavedPass123!",
            state="started",
            run_id=run_id,
            execution_id="resume-login-execution",
        )
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('registration_attempts')} "
                "SET private_context = private_context || %s::jsonb WHERE id=%s",
                (json.dumps({"submission_facts": [{
                    "submission_id": "old", "kind": "email", "stage": "submit_email",
                    "phase": "unknown", "endpoint_kind": "email_submit",
                }]}), attempt_id),
            )

        registration.record_submission_fact(
            attempt_id,
            submission_id="resume-new",
            kind="resume_login",
            stage="submit_email",
            phase="dispatch_intent",
            endpoint_kind="email_submit",
            http_method="POST",
            run_id=run_id,
            execution_id="resume-login-execution",
        )
        for submission_id, stage, endpoint_kind in (
            ("resume-new", "submit_email", "email_submit"),
            ("resume-password", "login_password", "password_submit"),
            ("resume-otp", "email_otp", "otp_submit"),
        ):
            registration.record_submission_fact(
                attempt_id,
                submission_id=submission_id,
                kind="resume_login",
                stage=stage,
                phase="confirmed" if submission_id == "resume-new" else "dispatch_intent",
                endpoint_kind=endpoint_kind,
                http_method="POST",
                run_id=run_id,
                execution_id="resume-login-execution",
            )
            if submission_id != "resume-new":
                registration.record_submission_fact(
                    attempt_id,
                    submission_id=submission_id,
                    kind="resume_login",
                    stage=stage,
                    phase="confirmed",
                    endpoint_kind=endpoint_kind,
                    http_method="POST",
                    result="success",
                    run_id=run_id,
                    execution_id="resume-login-execution",
                )
        private = registration.get_private_resume_context(
            attempt_id, email="resume-login@example.test",
        )
        self.assertIn(
            "resume-new",
            {item.get("submission_id") for item in private.get("submission_facts") or []},
        )
        self.assertEqual(
            {"old"},
            unresolved_submission_ids(private.get("submission_facts") or []),
        )

    def test_private_password_resume_can_continue_fresh_create_form_after_unknown(self):
        address = "resume-create-form@example.test"
        attempt = registration.create_attempt(address)
        attempt_id = int(attempt["id"])
        original = registration.start_run(
            attempt_id, execution_id="original-create", initial_status="running",
        )
        registration.save_password_checkpoint(
            attempt_id, email=address, password="OriginalSavedPass123!", state="started",
            run_id=original["id"], execution_id="original-create",
        )
        registration.record_submission_fact(
            attempt_id, submission_id="original-password", kind="password",
            stage="password_create", phase="unknown", endpoint_kind="password_submit",
            http_method="POST", run_id=original["id"], execution_id="original-create",
        )
        registration.finish_run(original["id"], status="failed")
        resumed = registration.start_run(
            attempt_id, action_type="registration_resume", execution_id="resume-create",
            initial_status="running",
        )
        registration.record_submission_fact(
            attempt_id, submission_id="resume-password", kind="resume_login",
            stage="password_create", phase="dispatch_intent", endpoint_kind="password_submit",
            http_method="POST", run_id=resumed["id"], execution_id="resume-create",
        )
        private = registration.get_private_resume_context(attempt_id, email=address)
        self.assertEqual(private["password"], "OriginalSavedPass123!")
        self.assertEqual(unresolved_submission_ids(private["submission_facts"]),
                         {"original-password", "resume-password"})
        self.assertIsNone(registration.get_attempt(attempt_id)["account_id"])

    def test_plain_registration_run_cannot_use_resume_kind_to_bypass_unknown(self):
        attempt = registration.create_attempt("plain-registration-fence@example.test")
        attempt_id = int(attempt["id"])
        run = registration.start_run(
            attempt_id,
            execution_id="plain-registration-execution",
            initial_status="running",
            action_type="registration",
        )
        registration.save_password_checkpoint(
            attempt_id,
            email="plain-registration-fence@example.test",
            password="SavedPass123!",
            state="started",
            run_id=int(run["id"]),
            execution_id="plain-registration-execution",
        )
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('registration_attempts')} "
                "SET private_context = private_context || %s::jsonb WHERE id=%s",
                (json.dumps({"submission_facts": [{
                    "submission_id": "old-plain", "kind": "email", "stage": "submit_email",
                    "phase": "unknown", "endpoint_kind": "email_submit",
                }]}), attempt_id),
            )
        with self.assertRaises(ValueError):
            registration.record_submission_fact(
                attempt_id,
                submission_id="new-plain",
                kind="resume_login",
                stage="submit_email",
                phase="dispatch_intent",
                endpoint_kind="email_submit",
                run_id=int(run["id"]),
                execution_id="plain-registration-execution",
            )

    def test_resume_run_cannot_repeat_unknown_otp_resend_within_same_run(self):
        attempt = registration.create_attempt("resume-resend-fence@example.test")
        attempt_id = int(attempt["id"])
        run = registration.start_run(
            attempt_id,
            execution_id="resume-resend-execution",
            initial_status="running",
            action_type="registration_resume",
        )
        registration.save_password_checkpoint(
            attempt_id,
            email="resume-resend-fence@example.test",
            password="SavedPass123!",
            state="started",
            run_id=int(run["id"]),
            execution_id="resume-resend-execution",
        )
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('registration_attempts')} "
                "SET private_context = private_context || %s::jsonb WHERE id=%s",
                (json.dumps({"submission_facts": [{
                    "submission_id": "old-resend", "kind": "resume_login", "stage": "otp_resend",
                    "phase": "unknown", "endpoint_kind": "otp_resend", "run_id": int(run["id"]),
                }]}), attempt_id),
            )
        with self.assertRaises(ValueError):
            registration.record_submission_fact(
                attempt_id,
                submission_id="new-resend",
                kind="resume_login",
                stage="otp_resend",
                phase="dispatch_intent",
                endpoint_kind="otp_resend",
                run_id=int(run["id"]),
                execution_id="resume-resend-execution",
            )

    def test_existing_queued_job_run_is_started_by_worker(self):
        job_id = self._job("queued-run@example.test")
        attempt = registration.ensure_attempt_for_job(job_id)
        queued = registration.start_run(int(attempt["id"]), job_id=job_id)

        running = registration.start_run(
            int(attempt["id"]),
            job_id=job_id,
            initial_status="running",
            started_at="2026-08-28T12:00:00+08:00",
            execution_id="worker-execution",
            worker_pid=123,
        )

        self.assertEqual(running["id"], queued["id"])
        self.assertEqual(running["status"], "running")
        self.assertIsNotNone(running["started_at"])
        self.assertEqual(running["execution_id"], "worker-execution")

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

    def test_confirmed_register_response_stays_confirmed_when_later_result_is_unknown(self):
        attempt = registration.create_attempt("confirmed-response@example.test")
        attempt_id = int(attempt["id"])
        registration.advance_checkpoint(attempt_id, "password_confirmed", remote_identity_state="confirmed")
        unknown = registration.mark_request_unknown(
            attempt_id,
            target="identity",
            identity_response_confirmed=True,
            detail={"cause_code": "email_otp_no_mail"},
        )
        self.assertEqual("confirmed", unknown["remote_identity_state"])
        self.assertEqual("request_unknown", unknown["remote_account_state"])
        self.assertEqual("request_unknown", unknown["target_status"])
        self.assertEqual("password_confirmed", unknown["checkpoint"])

    def test_startup_recovery_only_changes_active_registration_runs(self):
        attempt = registration.create_attempt("recovery@example.test")
        run = registration.start_run(int(attempt["id"]), execution_id="worker-1")
        self.assertEqual(registration.recover_interrupted_runs(), 1)
        self.assertEqual(registration.get_run(int(run["id"]))["status"], "interrupted")
        self.assertEqual(registration.recover_interrupted_runs(), 0)

    def test_terminal_run_only_clears_its_own_active_execution(self):
        attempt = registration.create_attempt("terminal-run@example.test")
        attempt_id = int(attempt["id"])
        first = registration.start_run(attempt_id, execution_id="worker-old")
        registration.advance_checkpoint(
            attempt_id,
            "email_claimed",
            run_id=int(first["id"]),
            execution_id="worker-old",
        )
        self.assertEqual("worker-old", registration.get_attempt(attempt_id)["active_execution_id"])

        registration.finish_run(int(first["id"]), status="failed")
        self.assertIsNone(registration.get_attempt(attempt_id)["active_execution_id"])

        second = registration.retry_run(attempt_id, execution_id="worker-new")
        registration.advance_checkpoint(
            attempt_id,
            "auth_started",
            run_id=int(second["id"]),
            execution_id="worker-new",
        )
        registration.finish_run(int(first["id"]), status="failed")
        self.assertEqual("worker-new", registration.get_attempt(attempt_id)["active_execution_id"])

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

    def test_core_registration_inherits_invalid_mailbox_and_token_update_keeps_marker(self):
        email = "invalid-core@icloud.test"
        record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": email, "account_id": "invalid-apple", "status": "used",
        })
        db.set_accounts_email_invalid(invalid=True, icloud_account_id="invalid-apple", reason="副号失效")
        attempt = registration.create_attempt(email)

        result = registration.persist_core_account(
            int(attempt["id"]), access_token="synthetic-first", account={"email_source": "icloud_hide"},
        )

        self.assertIs(result["account"]["email_invalid"], True)
        self.assertEqual(result["account"]["email_invalid_reason"], "副号失效")
        again = registration.persist_core_account(
            int(attempt["id"]), access_token="synthetic-next",
            account={"email_invalid": False, "email_invalid_reason": "旧快照"},
        )
        self.assertIs(again["account"]["email_invalid"], True)
        self.assertEqual(again["account"]["email_invalid_reason"], "副号失效")

    def test_confirmed_password_checkpoint_inherits_invalid_mailbox(self):
        email = "invalid-checkpoint@icloud.test"
        record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": email, "account_id": "invalid-apple", "status": "used",
        })
        db.set_accounts_email_invalid(invalid=True, icloud_account_id="invalid-apple", reason="副号失效")
        attempt = registration.create_attempt(email)
        run = registration.start_run(int(attempt["id"]), execution_id="invalid-mailbox-run", initial_status="running")

        result = registration.save_password_checkpoint(
            int(attempt["id"]), email=email, password="SyntheticPassword!", state="confirmed",
            run_id=int(run["id"]), execution_id="invalid-mailbox-run",
            account={"email_source": "icloud_hide", "email_invalid": False},
        )

        saved = record_store.get_row(record_store.ACCOUNTS, int(result["account_id"]))
        self.assertIs(saved["email_invalid"], True)
        self.assertEqual(saved["email_invalid_reason"], "副号失效")

    def test_core_registration_keeps_existing_case_insensitive_mailbox_marker(self):
        existing_id = db.insert_account(email="MixedCase@icloud.test", access_token="synthetic-old")
        db.set_accounts_email_invalid([existing_id], invalid=True, reason="邮箱失效")
        attempt = registration.create_attempt("mixedcase@icloud.test")

        result = registration.persist_core_account(int(attempt["id"]), access_token="synthetic-next")

        self.assertEqual(result["account_id"], existing_id)
        self.assertIs(result["account"]["email_invalid"], True)
        self.assertEqual(record_store.count_rows(record_store.ACCOUNTS), 1)

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

    def test_legacy_job_update_preserves_deactivated_attempt_without_account(self):
        job = db.create_job("outlook")
        attempt_id = int(job["attempt_id"])
        registration.advance_checkpoint(
            attempt_id,
            "failed",
            remote_identity_state="confirmed",
            remote_account_state="confirmed",
            local_account_state="none",
            target_status="deactivated",
        )

        self.assertIsNone(db.get_job(int(job["id"])).get("account_id"))
        db.update_job(int(job["id"]), status="failed", error="账号已明确永久失效")

        attempt = registration.get_attempt(attempt_id)
        task = operation.find_task_by_source("registration_chains", f"{job['id']}:registration")
        self.assertEqual("deactivated", attempt["target_status"])
        self.assertEqual("deactivated", task["target_status"])
        self.assertEqual([], task["next_actions"])


if __name__ == "__main__":
    unittest.main()
