from __future__ import annotations

import os
from unittest.mock import patch

from core import account_task_store
from core.storage import extract_link_batches, extract_link_jobs, operation
from tests.support_pg import PostgresTestCase


class ExtractReconcileHaltedStorageTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._old_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
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
            if cls._old_schema is None:
                os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
            else:
                os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._old_schema
        finally:
            cls._ready_patch.stop()
            cls._schema_patch.stop()
            super().tearDownClass()

    def setUp(self):
        operation.init()

    def task(self, *, summary=None, status="attention_required", provider="huanguang", batch_id=None,
             extraction="unknown", payment="unknown", plus="unknown", artifact=None):
        task = operation.create_runtime_task(
            task_type="extract_link", account_id=None, email="fixture@example.test", trigger="test",
            batch_id=batch_id, data={"provider_id": provider, "mode": "auto_payment"},
        )
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status=%s WHERE id=%s", (status, task["id"]))
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET status=%s WHERE id=%s", (status, task["run"]["id"]))
        state = {"extraction_state": extraction, "payment_state": payment, "plus_status": plus, "summary": summary or {}}
        if artifact:
            state["payment_artifact"] = artifact
        extract_link_jobs.save_provider_job(task["run"]["id"], provider, "synthetic-remote", state, {"job_secret": "private-fixture"})
        return task

    def test_halt_metadata_roundtrips_without_exposing_private_resume_data(self):
        summary = {
            "local_reconcile_halted": True, "local_reconcile_reason": "remote_not_found",
            "local_reconcile_halted_at": "2026-10-25T09:45:00+00:00", "remote_polling": True,
        }
        task = self.task(summary=summary)
        saved = extract_link_jobs.get_provider_job_public(task["run"]["id"])
        for key, value in summary.items():
            self.assertEqual(value, saved["public_state"]["summary"].get(key))
        self.assertNotIn("private-fixture", repr(saved))

    def test_halt_metadata_rejects_untyped_flags_unknown_reasons_and_invalid_times(self):
        for flag in ("true", "false", 1, 0, {}, None):
            with self.subTest(flag=flag):
                task = self.task(summary={"local_reconcile_halted": flag})
                saved = extract_link_jobs.get_provider_job_public(task["run"]["id"])["public_state"]
                self.assertNotIn("local_reconcile_halted", saved.get("summary", {}))
        for value in ("raw-secret", 10, None):
            with self.subTest(reason=value):
                task = self.task(summary={"local_reconcile_reason": value})
                saved = extract_link_jobs.get_provider_job_public(task["run"]["id"])["public_state"]
                self.assertNotIn("local_reconcile_reason", saved.get("summary", {}))
        for value in ("2026-10-25", "2026-10-25T09:45:00", "invalid-date", 20):
            with self.subTest(time=value):
                task = self.task(summary={"local_reconcile_halted_at": value})
                saved = extract_link_jobs.get_provider_job_public(task["run"]["id"])["public_state"]
                self.assertNotIn("local_reconcile_halted_at", saved.get("summary", {}))

    def test_halted_original_orders_are_not_automatically_recovered(self):
        halted = self.task(summary={"local_reconcile_halted": True, "remote_polling": True})
        active = self.task(summary={"local_reconcile_halted": False, "remote_polling": True})
        unmarked = self.task(summary={"remote_polling": True})
        other = self.task(provider="lumen_flow", summary={"local_reconcile_halted": True, "remote_polling": True})
        ids = {row["task_id"] for row in extract_link_jobs.list_recoverable_workbench_jobs()}
        self.assertNotIn(halted["id"], ids)
        self.assertTrue({active["id"], unmarked["id"], other["id"]}.issubset(ids))

    def test_halted_waiting_payments_leave_processing_but_keep_payment_facts(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="续查收口", requested_count=4)
        halted = self.task(batch_id=batch["id"], summary={"local_reconcile_halted": True, "remote_polling": True})
        unhalted = self.task(batch_id=batch["id"], summary={"local_reconcile_halted": False, "remote_polling": True})
        paid = self.task(batch_id=batch["id"], summary={"local_reconcile_halted": True, "extraction_ever_succeeded": True},
                         extraction="succeeded", payment="succeeded", plus="confirmed",
                         artifact={"qr_data": "upi://pay?pa=fixture", "payment_page_url": "https://checkout.example.test/retained"})
        running = self.task(batch_id=batch["id"], status="running", summary={"local_reconcile_halted": True})
        processing = extract_link_jobs.list_workbench_page(status="processing")
        self.assertEqual({unhalted["id"]}, {row["task_id"] for row in processing["items"]})
        self.assertEqual(1, processing["counts"]["processing"])
        self.assertEqual(0, processing["counts"]["running"])
        self.assertEqual(1, processing["counts"]["extraction_succeeded"])
        self.assertEqual(1, processing["counts"]["payment_succeeded"])
        self.assertEqual(1, processing["counts"]["plus_confirmed"])
        attention = extract_link_jobs.list_workbench_page(status="needs_attention")
        self.assertTrue({halted["id"], paid["id"], running["id"]}.issubset({row["task_id"] for row in attention["items"]}))
        preserved = extract_link_jobs.get_provider_job_public(paid["run"]["id"])["public_state"]
        self.assertEqual("upi://pay?pa=fixture", preserved["payment_artifact"]["qr_data"])
        self.assertEqual("confirmed", preserved["plus_status"])
        counts = extract_link_batches.batch_task_counts([batch["id"]])[batch["id"]]
        self.assertEqual(1, counts["processing"])
        self.assertEqual(0, counts["running"])
        self.assertEqual(1, counts["extraction_succeeded"])
        self.assertEqual(1, counts["payment_succeeded"])
        self.assertEqual(1, counts["plus_confirmed"])

    def test_halt_marker_does_not_change_other_provider_processing(self):
        task = self.task(provider="lumen_flow", summary={"local_reconcile_halted": True})
        processing = extract_link_jobs.list_workbench_page(status="processing")
        self.assertEqual([task["id"]], [row["task_id"] for row in processing["items"]])
        self.assertEqual(1, processing["counts"]["processing"])
