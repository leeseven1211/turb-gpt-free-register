"""独立套餐查询后的本地支付事实补齐，不触发提链或再次支付。"""
from __future__ import annotations

import json
import os
import uuid
from unittest.mock import patch

from core import account_task_store, record_store
from core.storage import extract_link_batches, extract_link_jobs, operation
from core.task_progress import build_progress_snapshot
from tests.support_pg import PostgresTestCase


class ExtractPaymentReconcileStorageTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._previous_operation_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        cls._schema_patch = patch.object(account_task_store, "_SCHEMA", cls.schema)
        cls._ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        cls._schema_patch.start()
        cls._ready_patch.start()
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        try:
            operation.reset_ready()
            if cls._previous_operation_schema is None:
                os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
            else:
                os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._previous_operation_schema
        finally:
            cls._ready_patch.stop()
            cls._schema_patch.stop()
            super().tearDownClass()

    def setUp(self):
        operation.init()

    def account(self, **changes):
        return self.seed(record_store.ACCOUNTS, [{
            "email": f"payment-reconcile-{uuid.uuid4().hex}@example.test", "plan_check_status": "success",
            "current_plan_type": "plus", "plan_checked_at": "2026-10-28T16:01:00Z",
            **changes,
        }])[0]

    def completed_state(self):
        return {
            "extraction_state": "succeeded", "payment_state": "unknown", "plus_status": "failed",
            "links": ["https://example.test/checkout"],
            "payment_artifact": {"payment_status": "completed", "platform_plus_status": "inferred",
                "payment_page_url": "https://example.test/checkout", "qr_data": "fixture-qr"},
            "summary": {
                "remote_status": "DONE", "automatic_payment_terminal": True, "remote_polling": False,
                "automatic_payment_status": "COMPLETED", "platform_plus_status": "inferred",
                "entitlement_active": True, "entitlement_inferred": True, "payment_check_status": "completed",
                "automatic_payment_requires_reconcile": True, "local_plan_check_pending": False,
            },
        }

    def task(self, account_id, *, status="attention_required", provider="huanguang", mode="auto_payment", state=None,
             run_data=None, cancelled=False):
        batch = operation.create_runtime_batch(batch_type="extract_link", requested_count=1,
            title="支付事实补齐", data={"workbench_batch": True, "submission_complete": True})
        task = operation.create_runtime_task(task_type="extract_link", account_id=account_id,
            email="payment-reconcile@example.test", batch_id=batch["id"],
            data={"provider_id": provider, "mode": mode, **(run_data or {})})
        state = self.completed_state() if state is None else state
        extract_link_jobs.save_provider_job(task["run"]["id"], provider, "fixture-original-job", state,
            {"job_secret": "fixture-private", "active_job_id": "fixture-original-job"})
        summary = {"payment_status": "unknown", "plus_status": "failed", "outcome": "request_unknown",
            "reconcile_required": True, "failure_stage": "plan_check", "remote_job_id": "fixture-original-job"}
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {operation._table('operation_tasks')}
                SET status=%s, created_at='2026-10-28T15:00:00Z', completed_at='2026-10-28T16:00:01Z',
                    error_category='authentication', error_code='token_invalid', error_message='旧套餐核验失败',
                    next_actions='[{{"action":"retry"}}]'::jsonb WHERE id=%s""", (status, task["id"]))
            cur.execute(f"""UPDATE {operation._table('operation_runs')}
                SET status=%s, created_at='2026-10-28T15:00:00Z', completed_at='2026-10-28T16:00:01Z',
                    duration_ms=12000, error_category='authentication', error_code='token_invalid',
                    error_message='旧套餐核验失败', result_summary=%s::jsonb,
                    cancel_requested_at=CASE WHEN %s THEN now() ELSE NULL END WHERE id=%s""",
                (status, json.dumps(summary), cancelled, task["run"]["id"]))
            cur.execute(f"UPDATE {operation._table('extract_link_provider_jobs')} SET updated_at='2026-10-28T16:00:00Z' WHERE run_id=%s",
                (task["run"]["id"],))
        return task

    def failed_stage_events(self, task):
        with operation._connect() as conn, conn.cursor() as cur:
            for stage, state in (("plan_check", "failed"), ("payment", "pending"), ("plus", "failed")):
                event_id = uuid.uuid4().hex
                cur.execute(f"""INSERT INTO {operation._table('operation_events')}
                    (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail,created_at)
                    VALUES (%s,%s,%s,'native_operations',%s,'ERROR',%s,%s,'旧套餐核验失败',%s::jsonb,'2026-10-28T16:00:01Z')""",
                    (event_id, task["id"], task["run"]["id"], event_id, stage, f"stage.{state}", json.dumps({"step_state": state})))

    def test_completed_scan_and_later_plus_atomically_complete_job_run_task_and_batch(self):
        task = self.task(self.account())
        self.failed_stage_events(task)
        before_job = extract_link_jobs.get_provider_job_private(task["run"]["id"])
        before_run = operation.get_run(task["run"]["id"])
        result = extract_link_jobs.reconcile_completed_payments()
        self.assertEqual({"confirmed": 1, "skipped": 0, "failed": 0}, result)
        job = extract_link_jobs.get_provider_job_private(task["run"]["id"])
        run = operation.get_run(task["run"]["id"])
        current = operation.get_task(task["id"], include_events=True)
        self.assertEqual("succeeded", job["payment_state"])
        self.assertEqual("succeeded", job["public_state"]["payment_state"])
        self.assertEqual("confirmed", job["public_state"]["plus_status"])
        self.assertEqual(before_job["public_state"]["payment_artifact"], job["public_state"]["payment_artifact"])
        self.assertEqual(before_job["private_data"], job["private_data"])
        self.assertEqual("local_plan_check", job["public_state"]["summary"]["payment_confirmation_source"])
        self.assertFalse(job["public_state"]["summary"]["automatic_payment_requires_reconcile"])
        self.assertEqual(100, job["public_state"]["summary"]["percent"])
        self.assertIn("确认 Plus 到账", job["public_state"]["summary"]["current_step"])
        self.assertEqual("success", run["status"])
        self.assertEqual("success", current["status"])
        self.assertEqual("completed", current["target_status"])
        self.assertEqual([], current["next_actions"])
        self.assertFalse(current["error_message"])
        self.assertFalse(run["error_message"])
        self.assertEqual(before_run["completed_at"], run["completed_at"])
        self.assertEqual(before_run["duration_ms"], run["duration_ms"])
        self.assertEqual("success", run["result_summary"]["outcome"])
        self.assertFalse(run["result_summary"]["reconcile_required"])
        self.assertNotIn("failure_stage", run["result_summary"])
        self.assertEqual(1, extract_link_batches.batch_task_counts([task["batch_id"]])[task["batch_id"]]["payment_succeeded"])
        events = [event for event in current["events"] if event.get("event_type") == "payment.local_reconciled"]
        self.assertEqual(1, len(events))
        snapshot = build_progress_snapshot(task["id"], run["id"], "extract_link", run, current["events"])
        self.assertIsNone(snapshot["failure"])
        for stage in ("payment", "plus", "plan_check"):
            step = next(step for step in snapshot["main_steps"] if stage in step["raw_stages"])
            self.assertEqual("success", step["state"])
        self.assertEqual({"confirmed": 0, "skipped": 0, "failed": 0}, extract_link_jobs.reconcile_completed_payments())

    def test_missing_or_incomplete_remote_evidence_does_not_infer_payment_from_plus(self):
        cases = [
            ("scan-pending", {"automatic_payment_status": "WAITING_SCAN"}, {}),
            ("polling", {"remote_polling": True}, {}),
            ("remote-running", {"remote_status": "RUNNING"}, {}),
            ("refund", {"automatic_payment_status": "FAILED_REFUNDED"}, {"payment_state": "failed"}),
            ("remote-failure", {"remote_terminal_failure": True}, {}),
            ("chain-error", {"remote_chain_error": "原单后续失败"}, {}),
            ("no-scan-receipt", {}, {"payment_artifact": {}}),
            ("no-extract", {}, {"extraction_state": "failed"}),
        ]
        for name, summary_changes, changes in cases:
            with self.subTest(name=name):
                state = self.completed_state()
                state["summary"].update(summary_changes)
                state.update(changes)
                task = self.task(self.account(), state=state)
                extract_link_jobs.reconcile_completed_payments(account_id=task["account_id"])
                self.assertEqual("attention_required", operation.get_run(task["run"]["id"])["status"])
                self.assertNotEqual("succeeded", extract_link_jobs.get_provider_job_public(task["run"]["id"])["payment_state"])

    def test_plan_check_must_succeed_with_plus_after_remote_result_and_run_finished(self):
        cases = [
            {"plan_check_status": "failed"}, {"current_plan_type": "free"},
            {"plan_checked_at": "2026-10-28T14:59:00Z"},
            {"plan_checked_at": "2026-10-28T15:59:59Z"},
            {"plan_checked_at": "2026-10-28T16:00:01Z"},
            {"plan_checked_at": "bad-time"},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                task = self.task(self.account(**changes))
                result = extract_link_jobs.reconcile_completed_payments(account_id=task["account_id"])
                self.assertEqual(0, result["confirmed"])
                self.assertEqual("attention_required", operation.get_run(task["run"]["id"])["status"])

    def test_active_cancelled_other_provider_and_extract_only_tasks_are_preserved(self):
        cases = [
            {"status": "running"}, {"status": "queued"}, {"status": "cancelled"},
            {"cancelled": True}, {"provider": "lumen_flow"}, {"mode": "extract_only"},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                task = self.task(self.account(), **changes)
                before = operation.get_run(task["run"]["id"])
                self.assertEqual(0, extract_link_jobs.reconcile_completed_payments()["confirmed"])
                self.assertEqual(before, operation.get_run(task["run"]["id"]))

    def test_unknown_remote_write_receipt_is_not_bypassed(self):
        task = self.task(self.account(), run_data={"remote_intent": {
            "kind": "remote_write", "action": "extract_link_create", "state": "started",
        }})
        result = extract_link_jobs.reconcile_completed_payments()
        self.assertEqual(0, result["confirmed"])
        self.assertEqual("attention_required", operation.get_run(task["run"]["id"])["status"])

    def test_confirmed_remote_write_receipt_and_private_data_are_preserved(self):
        intent = {"kind": "remote_write", "action": "extract_link_create", "state": "confirmed", "receipt_state": "confirmed"}
        task = self.task(self.account(), run_data={"remote_intent": intent})
        self.assertEqual(1, extract_link_jobs.reconcile_completed_payments()["confirmed"])
        self.assertEqual(intent, operation.get_run(task["run"]["id"])["data"]["remote_intent"])

    def test_account_scope_only_reconciles_selected_account(self):
        first = self.task(self.account())
        second = self.task(self.account())
        self.assertEqual(1, extract_link_jobs.reconcile_completed_payments(account_id=first["account_id"])["confirmed"])
        self.assertEqual("attention_required", operation.get_run(second["run"]["id"])["status"])

    def test_archived_account_can_reconcile_existing_history_without_starting_a_task(self):
        task = self.task(self.account(archived=True))
        self.assertEqual(1, extract_link_jobs.reconcile_completed_payments()["confirmed"])
        self.assertEqual("success", operation.get_run(task["run"]["id"])["status"])

    def test_later_extract_task_on_same_account_protects_old_payment_attribution(self):
        account_id = self.account()
        older = self.task(account_id)
        newer = self.task(account_id, state={"extraction_state": "failed", "payment_state": "not_started"})
        result = extract_link_jobs.reconcile_completed_payments(account_id=account_id)
        self.assertEqual(0, result["confirmed"])
        self.assertEqual("attention_required", operation.get_run(older["run"]["id"])["status"])
        self.assertEqual("attention_required", operation.get_run(newer["run"]["id"])["status"])

    def test_old_run_is_not_reconciled_after_task_has_a_retry(self):
        task = self.task(self.account())
        retried = operation.retry_runtime_task(task["id"])
        self.assertEqual(0, extract_link_jobs.reconcile_completed_payments()["confirmed"])
        self.assertEqual("attention_required", operation.get_run(task["run"]["id"])["status"])
        self.assertEqual("queued", operation.get_run(retried["id"])["status"])

    def test_xxsyun_completed_receipt_uses_same_independent_plus_confirmation(self):
        state = self.completed_state()
        state["summary"].update(automatic_payment_status="XXSYUN_COMPLETED", xxsyun_status="completed")
        state["payment_artifact"]["payment_status"] = "verification_unavailable"
        task = self.task(self.account(), state=state)
        self.assertEqual(1, extract_link_jobs.reconcile_completed_payments()["confirmed"])
        self.assertEqual("succeeded", extract_link_jobs.get_provider_job_public(task["run"]["id"])["payment_state"])

    def test_legacy_confirmed_payment_and_later_plus_complete_the_task(self):
        state = {"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "failed"}
        task = self.task(self.account(), provider="legacy", state=state)
        self.assertEqual(1, extract_link_jobs.reconcile_completed_payments()["confirmed"])
        self.assertEqual("success", operation.get_run(task["run"]["id"])["status"])
        self.assertEqual("confirmed", extract_link_jobs.get_provider_job_public(task["run"]["id"])["public_state"]["plus_status"])
        counts = extract_link_batches.batch_task_counts([task["batch_id"]])[task["batch_id"]]
        self.assertEqual(1, counts["payment_succeeded"])
        self.assertEqual(1, counts["plus_confirmed"])
        self.assertEqual(1, extract_link_jobs.list_workbench_page(batch_id=task["batch_id"], status="plus_confirmed")["total"])

    def test_legacy_pending_and_explicit_failure_do_not_confirm_payment_from_plus(self):
        for state in (
            {"extraction_state": "succeeded", "payment_state": "pending"},
            {"extraction_state": "failed", "payment_state": "succeeded", "summary": {"remote_terminal_failure": True}},
            {"extraction_state": "succeeded", "payment_state": "succeeded", "summary": {"automatic_payment_status": "CANCELLED"}},
        ):
            with self.subTest(state=state):
                task = self.task(self.account(), provider="legacy", state=state)
                self.assertEqual(0, extract_link_jobs.reconcile_completed_payments(account_id=task["account_id"])["confirmed"])
                self.assertEqual("attention_required", operation.get_run(task["run"]["id"])["status"])

    def test_new_sync_run_reuses_later_account_check_with_confirmed_original_payment(self):
        state = {"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "pending"}
        task = self.task(self.account(), provider="legacy", state=state)
        sync = operation.retry_runtime_task(task["id"], data={"workbench_action": "sync_status", "provider_job_run_id": task["run"]["id"]})
        extract_link_jobs.save_provider_job(sync["id"], "legacy", "fixture-original-job", state, {})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status='attention_required' WHERE id=%s", (task["id"],))
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET status='attention_required', completed_at='2026-10-28T16:02:00Z' WHERE id=%s", (sync["id"],))
            cur.execute(f"UPDATE {operation._table('extract_link_provider_jobs')} SET updated_at='2026-10-28T16:02:00Z' WHERE run_id=%s", (sync["id"],))
        self.assertEqual(1, extract_link_jobs.reconcile_completed_payments(account_id=task["account_id"])["confirmed"])
        self.assertEqual("success", operation.get_run(sync["id"])["status"])
        self.assertEqual("attention_required", operation.get_run(task["run"]["id"])["status"])

    def test_finished_manual_paid_order_with_failed_arrival_is_reconciled_once(self):
        state = {"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "failed"}
        task = self.task(self.account(), status="success", provider="legacy", mode="manual_payment", state=state)
        self.assertEqual(1, extract_link_jobs.reconcile_completed_payments(account_id=task["account_id"])["confirmed"])
        job = extract_link_jobs.get_provider_job_public(task["run"]["id"])
        self.assertEqual("confirmed", job["public_state"]["plus_status"])
        self.assertEqual(0, extract_link_jobs.reconcile_completed_payments(account_id=task["account_id"])["confirmed"])

    def test_paid_running_extraction_is_completed_with_independent_arrival(self):
        state = {"extraction_state": "running", "payment_state": "succeeded", "plus_status": "pending"}
        task = self.task(self.account(), provider="legacy", state=state)
        self.assertEqual(1, extract_link_jobs.reconcile_completed_payments(account_id=task["account_id"])["confirmed"])
        job = extract_link_jobs.get_provider_job_public(task["run"]["id"])
        self.assertEqual("succeeded", job["extraction_state"])
        self.assertEqual("succeeded", job["public_state"]["extraction_state"])

    def test_item_failure_rolls_back_all_changes_and_continues_other_items(self):
        first = self.task(self.account())
        second = self.task(self.account())
        refresh = operation._refresh_batches
        calls = []
        def fail_first(cur, batch_ids):
            calls.append(batch_ids)
            if len(calls) == 1:
                raise RuntimeError("fixture-private-error")
            return refresh(cur, batch_ids)
        with patch.object(operation, "_refresh_batches", side_effect=fail_first):
            result = extract_link_jobs.reconcile_completed_payments()
        self.assertEqual({"confirmed": 1, "skipped": 0, "failed": 1}, result)
        self.assertEqual("attention_required", operation.get_run(first["run"]["id"])["status"])
        self.assertEqual("unknown", extract_link_jobs.get_provider_job_public(first["run"]["id"])["payment_state"])
        self.assertEqual("success", operation.get_run(second["run"]["id"])["status"])
