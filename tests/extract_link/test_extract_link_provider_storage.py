from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import account_task_store
from core.storage import records as record_store
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class ExtractLinkProviderStorageTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._previous_operation_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        cls._account_schema_patch = patch.object(account_task_store, "_SCHEMA", cls.schema)
        cls._account_ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        cls._account_schema_patch.start()
        cls._account_ready_patch.start()
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
            cls._account_ready_patch.stop()
            cls._account_schema_patch.stop()
            super().tearDownClass()

    def setUp(self):
        operation.init()

    def test_restore_legacy_payment_credential_updates_same_order_and_survives_stale_worker(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="credential@example.test",
            data={"provider_id": "legacy", "mode": "auto_payment"})
        original = task["run"]["id"]
        state = {"extraction_state": "succeeded", "payment_state": "pending"}
        private = {"legacy_payment_order_id": "order-1", "legacy_payment_order_no": "UPI-FIXTURE-1"}
        extract_link_jobs.save_provider_job(original, "legacy", "job-1", state, private)
        operation.finish_run(original, status="attention_required", message="等待原单查询")
        current = operation.retry_runtime_task(task["id"], data={"workbench_action": "sync_status",
            "provider_job_run_id": original})["id"]
        extract_link_jobs.save_provider_job(current, "legacy", "job-1", state, private)
        operation.claim_run(current, execution_id="credential-worker", worker_pid=91)

        result = extract_link_jobs.restore_legacy_payment_query_credential(task["id"],
            expected_run_id=current, provider_job_run_id=original, expected_job_id="job-1",
            expected_order_id="order-1", expected_order_no="UPI-FIXTURE-1", payment_cdk="validated-old-card")
        self.assertTrue(result["updated"])
        for run_id in (original, current):
            self.assertEqual("validated-old-card", extract_link_jobs.get_provider_job_private(run_id)["private_data"]["legacy_payment_cdk"])
        extract_link_jobs.save_provider_job(current, "legacy", "job-1", state,
            {**private, "legacy_payment_cdk": "stale-current-card"})
        self.assertEqual("validated-old-card", extract_link_jobs.get_provider_job_private(current)["private_data"]["legacy_payment_cdk"])
        self.assertNotIn("validated-old-card", repr(operation.get_task(task["id"])))
        self.assertNotIn("validated-old-card", repr(result))
        self.assertEqual("running", operation.get_run(current)["status"])

    def test_restore_legacy_payment_credential_rejects_changed_identity_or_existing_other_card(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="credential@example.test",
            data={"provider_id": "legacy", "mode": "auto_payment"})
        run_id = task["run"]["id"]
        extract_link_jobs.save_provider_job(run_id, "legacy", "job-1", {},
            {"legacy_payment_order_id": "order-1"})
        valid = {"expected_run_id": run_id, "provider_job_run_id": run_id,
            "expected_job_id": "job-1", "expected_order_id": "order-1", "payment_cdk": "validated-old-card"}
        for changed in ({"expected_run_id": run_id + 100}, {"expected_job_id": "other-job"},
                        {"expected_order_id": "other-order"}, {"expected_order_id": ""},
                        {"payment_cdk": "invalid secret\n"}):
            with self.subTest(changed=list(changed)), self.assertRaises((ValueError, LookupError)):
                extract_link_jobs.restore_legacy_payment_query_credential(task["id"], **{**valid, **changed})
        self.assertNotIn("legacy_payment_cdk", extract_link_jobs.get_provider_job_private(run_id)["private_data"])
        extract_link_jobs.save_provider_job(run_id, "legacy", "job-1", {},
            {"legacy_payment_order_id": "order-1", "legacy_payment_cdk": "existing-other-card"})
        with self.assertRaises(ValueError):
            extract_link_jobs.restore_legacy_payment_query_credential(task["id"], **valid)
        self.assertEqual("existing-other-card", extract_link_jobs.get_provider_job_private(run_id)["private_data"]["legacy_payment_cdk"])

    def test_restore_legacy_payment_credential_rejects_foreign_source_and_obsolete_current_run(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        tasks = [operation.create_runtime_task(task_type="extract_link", account_id=None,
                 email="credential@example.test", data={"provider_id": "legacy", "mode": "auto_payment"})
                 for _ in range(2)]
        for task in tasks:
            extract_link_jobs.save_provider_job(task["run"]["id"], "legacy", "same-job", {},
                                               {"legacy_payment_order_id": "same-order"})
        original = tasks[0]["run"]["id"]
        operation.finish_run(original, status="attention_required", message="等待查询")
        current = operation.retry_runtime_task(tasks[0]["id"], data={"workbench_action": "sync_status",
            "provider_job_run_id": tasks[1]["run"]["id"]})["id"]
        with self.assertRaises(ValueError):
            extract_link_jobs.restore_legacy_payment_query_credential(tasks[0]["id"],
                expected_run_id=current, provider_job_run_id=tasks[1]["run"]["id"], expected_job_id="same-job",
                expected_order_id="same-order", payment_cdk="validated-old-card")
        with self.assertRaises(ValueError):
            extract_link_jobs.restore_legacy_payment_query_credential(tasks[0]["id"],
                expected_run_id=original, provider_job_run_id=original, expected_job_id="same-job",
                expected_order_id="same-order", payment_cdk="validated-old-card")
        for task in tasks:
            self.assertNotIn("legacy_payment_cdk", extract_link_jobs.get_provider_job_private(task["run"]["id"])["private_data"])

    def test_saved_legacy_payment_credential_does_not_cross_changed_remote_order(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="credential@example.test",
            data={"provider_id": "legacy", "mode": "auto_payment"})
        run_id = task["run"]["id"]
        extract_link_jobs.save_provider_job(run_id, "legacy", "job-1", {},
            {"legacy_payment_order_id": "order-1", "legacy_payment_cdk": "original-card"})
        extract_link_jobs.save_provider_job(run_id, "legacy", "job-1", {},
            {"legacy_payment_order_id": "order-2"})
        self.assertNotIn("legacy_payment_cdk", extract_link_jobs.get_provider_job_private(run_id)["private_data"])

    def test_platform_order_plus_evidence_is_public_but_credential_is_private(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="credential@example.test",
            data={"provider_id": "legacy", "mode": "auto_payment"})
        extract_link_jobs.save_provider_job(task["run"]["id"], "legacy", "job-1", {
            "summary": {"payment_confirmation_source": "platform_order_check",
                        "platform_plus_checked_at": "2026-10-29T08:00:00Z", "platform_plus_status": "at_invalidated"}},
            {"legacy_payment_cdk": "must-stay-private"})
        public = extract_link_jobs.get_provider_job_public(task["run"]["id"])
        self.assertEqual("platform_order_check", public["public_state"]["summary"]["payment_confirmation_source"])
        self.assertEqual("2026-10-29T08:00:00Z", public["public_state"]["summary"]["platform_plus_checked_at"])
        self.assertNotEqual("confirmed", public["public_state"].get("plus_status"))
        self.assertNotIn("must-stay-private", repr(public))

    def test_provider_private_data_is_not_in_normal_task_or_run_projections(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=None,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "huanguang", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "huanguang",
            "remote-job-1",
            {
                "extraction_state": "running",
                "payment_state": "not_started",
                "job_secret": "test-private-job-secret",
            },
            {"job_secret": "test-private-job-secret"},
        )

        projected_task = operation.get_task(int(task["id"]))
        listed_tasks = operation.list_tasks(task_type="extract_link")["items"]
        self.assertNotIn("test-private-job-secret", repr(projected_task))
        self.assertNotIn("test-private-job-secret", repr(listed_tasks))
        self.assertNotIn("test-private-job-secret", repr(operation.get_run(run_id)))

        private_job = extract_link_jobs.get_provider_job_private(run_id)
        self.assertEqual("remote-job-1", private_job["job_id"])
        self.assertEqual("test-private-job-secret", private_job["private_data"]["job_secret"])
        self.assertNotIn("job_secret", private_job["public_state"])

    def test_provider_state_updates_do_not_replace_private_resume_data(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=None,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "lumen_flow", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "lumen_flow",
            "remote-job-2",
            {"extraction_state": "running", "payment_state": "not_started"},
            {"resume_cursor": "private-cursor"},
        )

        extract_link_jobs.update_provider_job_state(
            run_id,
            {"extraction_state": "success", "payment_state": "not_started", "links": ["https://example.test/result"]},
        )

        saved = extract_link_jobs.get_provider_job_private(run_id)
        self.assertEqual("success", saved["extraction_state"])
        self.assertEqual(["https://example.test/result"], saved["public_state"]["links"])
        self.assertEqual("private-cursor", saved["private_data"]["resume_cursor"])

    def test_payment_artifact_roundtrip_merges_partial_updates_without_truncating_links(self):
        from core.extract_link import service as extract_link_service
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link", account_id=None, email="redacted@example.test", trigger="test",
            data={"provider_id": "lumen_flow", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        page = "https://checkout.example.test/" + "x" * 3000
        qr_data = "upi://pay?pa=synthetic@example.test&tn=Token%2BExact"
        extract_link_jobs.save_provider_job(run_id, "lumen_flow", "artifact-job", {
            "extraction_state": "succeeded", "payment_state": "not_started", "payment_links": [page],
            "payment_artifact": {"payment_page_url": page, "qr_data": qr_data, "amount": 0, "raw": "must-not-project"},
        }, {})
        extract_link_jobs.save_provider_job(run_id, "lumen_flow", "artifact-job", {
            "extraction_state": "succeeded", "payment_state": "not_started", "links": [], "payment_artifact": {},
        }, {})
        extract_link_jobs.update_provider_job_state(run_id, {"payment_artifact": {"currency": "BRL", "amount": None}})
        saved = extract_link_jobs.get_provider_job_public(run_id)["public_state"]
        self.assertEqual({"payment_page_url": page, "qr_data": qr_data, "amount": 0, "currency": "BRL"}, saved["payment_artifact"])
        self.assertEqual([page], saved["payment_links"])
        listed = extract_link_service.list_workbench_tasks()
        self.assertNotIn(qr_data, repr(listed))
        self.assertNotIn(page, repr(listed))
        self.assertTrue(listed["items"][0]["has_qr"])
        self.assertTrue(listed["items"][0]["has_payment_entry"])
        self.assertNotIn(qr_data, repr(operation.get_task(int(task["id"]))))

    def test_workbench_rows_join_current_run_and_return_only_public_state(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=None,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "huanguang", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "huanguang",
            "remote-job-3",
            {
                "extraction_state": "succeeded",
                "payment_state": "not_started",
                "preflight_status": "passed",
                "links": ["https://example.test/result"],
            },
            {"job_secret": "private-resume-secret"},
        )

        rows = extract_link_jobs.list_workbench_rows(provider_id="huanguang", mode="extract_only")

        self.assertEqual(1, len(rows))
        self.assertEqual(int(task["id"]), rows[0]["task_id"])
        self.assertEqual(run_id, rows[0]["run_id"])
        self.assertEqual("remote-job-3", rows[0]["remote_job_id"])
        self.assertEqual("succeeded", rows[0]["extraction_state"])
        self.assertEqual(["https://example.test/result"], rows[0]["public_state"]["links"])
        self.assertNotIn("private-resume-secret", repr(rows))

    def test_unresolved_auto_payment_includes_unknown_payment_without_remote_job_id(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        payment_task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=77,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "lumen_flow", "mode": "auto_payment"},
        )
        extract_link_jobs.save_provider_job(
            int(payment_task["run"]["id"]),
            "lumen_flow",
            None,
            {"extraction_state": "unknown", "payment_state": "unknown"},
            {},
        )

        extraction_task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=78,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "lumen_flow", "mode": "extract_only"},
        )
        extract_link_jobs.save_provider_job(
            int(extraction_task["run"]["id"]),
            "lumen_flow",
            None,
            {"extraction_state": "unknown", "payment_state": "unknown"},
            {},
        )

        self.assertTrue(extract_link_jobs.has_unresolved_auto_payment(77))
        self.assertFalse(extract_link_jobs.has_unresolved_auto_payment(78))

    def test_recoverable_remote_jobs_only_include_interrupted_current_runs(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=77,
            email="redacted@example.test",
            trigger="test",
            source_system="native_operations",
            data={"provider_id": "lumen_flow", "mode": "auto_payment"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "lumen_flow",
            "remote-job-4",
            {"extraction_state": "running", "payment_state": "pending"},
            {},
        )
        operation.finish_run(
            run_id,
            status="attention_required",
            message="worker restarted",
        )

        rows = extract_link_jobs.list_recoverable_workbench_jobs()

        self.assertEqual(1, len(rows))
        self.assertEqual(int(task["id"]), rows[0]["task_id"])
        self.assertEqual(run_id, rows[0]["run_id"])
        self.assertEqual("lumen_flow", rows[0]["provider_id"])
        self.assertEqual("auto_payment", rows[0]["mode"])

    def test_recovery_excludes_explicitly_stopped_batches(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        expected = set()
        for status in ("cancelled", "stopped", "paused", "waiting"):
            batch = operation.create_runtime_batch(batch_type="extract_link", requested_count=1, title="恢复范围")
            task = operation.create_runtime_task(task_type="extract_link", account_id=77, email="test@example.test",
                batch_id=batch["id"], data={"provider_id": "legacy", "mode": "auto_payment", "extract_poll_continuation": True})
            extract_link_jobs.save_provider_job(task["run"]["id"], "legacy", "remote-job",
                {"extraction_state": "running", "payment_state": "pending"}, {})
            operation.finish_run(task["run"]["id"], status="attention_required", message="等待同步")
            with operation._connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {operation._table('operation_batches')} SET status=%s WHERE id=%s", (status, batch["id"]))
            if status == "waiting":
                expected.add(task["id"])
        self.assertEqual(expected, {row["task_id"] for row in extract_link_jobs.list_recoverable_workbench_jobs()})

    def test_recovery_does_not_include_legacy_history_without_continuation(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(task_type="extract_link", account_id=77, email="test@example.test",
            data={"provider_id": "legacy", "mode": "auto_payment"})
        extract_link_jobs.save_provider_job(task["run"]["id"], "legacy", "remote-job",
            {"extraction_state": "running", "payment_state": "pending"}, {})
        operation.finish_run(task["run"]["id"], status="attention_required", message="等待同步")
        self.assertEqual([], extract_link_jobs.list_recoverable_workbench_jobs())

    def test_legacy_initial_monitor_interruption_recovers_only_with_reconcile_metadata(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        expected = set()
        for metadata in ({"started_at": "2026-10-29T00:00:00Z"}, None, "invalid"):
            task = operation.create_runtime_task(task_type="extract_link", account_id=77, email="test@example.test",
                data={"provider_id": "legacy", "mode": "auto_payment"})
            private = {"local_reconcile": metadata} if metadata is not None else {}
            extract_link_jobs.save_provider_job(task["run"]["id"], "legacy", "remote-job",
                {"extraction_state": "running", "payment_state": "pending"}, private)
            with operation._connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {operation._table('operation_runs')} SET status='interrupted' WHERE id=%s", (task["run"]["id"],))
            if isinstance(metadata, dict):
                expected.add(task["id"])
        self.assertEqual(expected, {row["task_id"] for row in extract_link_jobs.list_recoverable_workbench_jobs()})

    def test_legacy_recovery_only_keeps_nonterminal_original_orders(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        cases = [
            ({"extraction_state": "running", "payment_state": "pending"}, "auto_payment", True),
            ({"extraction_state": "succeeded", "payment_state": "pending"}, "auto_payment", True),
            ({"extraction_state": "succeeded", "payment_state": "pending",
              "summary": {"automatic_payment_terminal": True}}, "auto_payment", False),
            ({"extraction_state": "succeeded", "payment_state": "pending"}, "extract_only", False),
            ({"extraction_state": "running", "payment_state": "failed"}, "auto_payment", False),
            ({"extraction_state": "running", "payment_state": "succeeded"}, "auto_payment", False),
            ({"extraction_state": "failed", "payment_state": "pending"}, "auto_payment", False),
            ({"extraction_state": "running", "payment_state": "pending", "summary": {"outcome": "REJECTED"}}, "auto_payment", False),
            ({"extraction_state": "running", "payment_state": "pending", "summary": {"remote_terminal_failure": True}}, "auto_payment", False),
        ]
        expected = set()
        for state, mode, recoverable in cases:
            task = operation.create_runtime_task(task_type="extract_link", account_id=77, email="test@example.test",
                data={"provider_id": "legacy", "mode": mode, "extract_poll_continuation": True})
            extract_link_jobs.save_provider_job(task["run"]["id"], "legacy", "remote-job", state, {})
            operation.finish_run(task["run"]["id"], status="attention_required", message="等待同步")
            if recoverable:
                expected.add(task["id"])
        self.assertEqual(expected, {row["task_id"] for row in extract_link_jobs.list_recoverable_workbench_jobs()})

    def test_legacy_paid_initial_run_recovers_verification_after_worker_exit(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        for receipt in (None, {"kind": "remote_write", "state": "confirmed", "receipt_state": "confirmed"}):
            with self.subTest(confirmed_receipt=bool(receipt)):
                task = operation.create_runtime_task(task_type="extract_link", account_id=77,
                    email="paid-recovery@example.test", data={"provider_id": "legacy", "mode": "auto_payment",
                        **({"remote_intent": receipt} if receipt else {})})
                run_id = task["run"]["id"]
                extract_link_jobs.save_provider_job(run_id, "legacy", "paid-original",
                    {"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "pending",
                     "summary": {"local_plan_check_pending": True, "automatic_payment_status": "COMPLETED"}},
                    {"local_reconcile": {"started_at": "2026-10-29T00:00:00Z"}})
                operation.claim_run(run_id, execution_id=f"paid-crashed-{run_id}", worker_pid=92)
                with operation._connect() as conn, conn.cursor() as cur:
                    cur.execute(f"UPDATE {operation._table('operation_runs')} SET heartbeat_at=now()-interval '1 hour' WHERE id=%s", (run_id,))
                self.assertEqual(1, operation.recover_interrupted_runtime_runs())
                candidates = {row["task_id"]: row for row in extract_link_jobs.list_recoverable_workbench_jobs()}
                self.assertIn(task["id"], candidates)
                self.assertEqual(run_id, candidates[task["id"]]["provider_job_run_id"])

    def test_legacy_paid_recovery_requires_interrupted_verification_and_respects_paused_batch(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        cases = (
            ("pending", {}, {"local_reconcile": {}}, "interrupted", "waiting", True),
            ("pending", {"local_plan_check_pending": True}, {}, "attention_required", "waiting", True),
            ("pending", {}, {"local_reconcile": {}}, "attention_required", "waiting", False),
            ("confirmed", {"local_plan_check_pending": True}, {"local_reconcile": {}}, "interrupted", "waiting", False),
            ("pending", {"local_plan_check_pending": True}, {"local_reconcile": {}}, "interrupted", "paused", False),
            ("pending", {}, {}, "interrupted", "waiting", False),
            ("pending", {"local_plan_check_pending": True, "automatic_payment_status": "FAILED_REFUNDED"},
             {"local_reconcile": {}}, "interrupted", "waiting", False),
        )
        expected = set()
        for plus, summary, private, status, batch_status, allowed in cases:
            with self.subTest(plus=plus, summary=summary, status=status, batch_status=batch_status):
                batch = operation.create_runtime_batch(batch_type="extract_link", title="到账中断恢复", requested_count=1)
                task = operation.create_runtime_task(task_type="extract_link", account_id=77,
                    email="paid-candidate@example.test", batch_id=batch["id"],
                    data={"provider_id": "legacy", "mode": "auto_payment"})
                extract_link_jobs.save_provider_job(task["run"]["id"], "legacy", "paid-original",
                    {"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": plus,
                     "summary": summary}, private)
                operation.finish_run(task["run"]["id"], status=status, message="到账核验中断")
                with operation._connect() as conn, conn.cursor() as cur:
                    cur.execute(f"UPDATE {operation._table('operation_batches')} SET status=%s WHERE id=%s", (batch_status, batch["id"]))
                if allowed:
                    expected.add(task["id"])
        self.assertEqual(expected, {row["task_id"] for row in extract_link_jobs.list_recoverable_workbench_jobs()})

    def test_provider_terminal_failure_evidence_is_preserved_without_private_fields(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link", account_id=None, email="redacted@example.test",
            trigger="test", data={"provider_id": "lumen_flow", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id, "lumen_flow", "failed-job",
            {
                "extraction_state": "failed", "payment_state": "not_started",
                "summary": {
                    "remote_status": "failed", "remote_terminal_failure": True,
                    "failure_message": "平台确认提链失败", "raw_response": "不应保存",
                },
            }, {},
        )
        public = extract_link_jobs.get_provider_job_public(run_id)["public_state"]
        self.assertEqual("FAILED", public["summary"]["remote_status"])
        self.assertIs(True, public["summary"]["remote_terminal_failure"])
        self.assertEqual("平台确认提链失败", public["summary"]["failure_message"])
        self.assertNotIn("raw_response", public["summary"])

        extract_link_jobs.update_provider_job_state(run_id, {
            "extraction_state": "failed", "payment_state": "not_started",
            "summary": {"remote_status": "未识别的原始响应", "remote_terminal_failure": "true"},
        })
        summary = extract_link_jobs.get_provider_job_public(run_id)["public_state"]["summary"]
        self.assertNotIn("remote_status", summary)
        self.assertNotIn("remote_terminal_failure", summary)

    def _finish_provider_failure(
        self, *, provider_state=None, finish_summary=None, receipt_detail=None,
        receipt_state="confirmed", action="extract_link_create", task_type="extract_link",
        save_job=True, job_provider="lumen_flow", job_id="failed-job", mode="extract_only",
    ):
        from core.storage.extract_link import jobs as extract_link_jobs

        email = f"extract-{uuid.uuid4().hex}@example.test"
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": email, "access_token": "synthetic-token",
            "created_at": "2026-10-23T00:00:00", "updated_at": "2026-10-23T00:00:00",
        }])[0]
        task = operation.create_runtime_task(
            task_type=task_type, account_id=account_id, email=email, trigger="test",
            data={"provider_id": "lumen_flow", "mode": mode},
        )
        run_id = int(task["run"]["id"])
        execution_id = f"failed-worker-{run_id}"
        operation.claim_run(run_id, execution_id=execution_id, worker_pid=os.getpid())
        lease_token = operation.acquire_account_lease(account_id=account_id, run_id=run_id)
        self.assertTrue(lease_token)
        fence = {"execution_id": execution_id, "lease_token": lease_token}
        operation.record_remote_intent(
            run_id, **fence, action=action, request_id=f"failed-request-{run_id}",
            detail={"provider_id": "lumen_flow", "mode": mode, "run_id": run_id},
        )
        state = provider_state if provider_state is not None else {
            "extraction_state": "failed", "payment_state": "not_started",
            "summary": {"remote_status": "FAILED", "remote_terminal_failure": True},
        }
        if save_job:
            extract_link_jobs.save_provider_job(run_id, job_provider, job_id, state, {})
        if receipt_state != "started":
            detail = {
                "remote_result_confirmed": True, "local_business_writeback_confirmed": True,
                "local_readback_confirmed": True, "provider_id": "lumen_flow",
                "remote_job_id": "failed-job",
            }
            if receipt_detail is not None:
                detail.update(receipt_detail)
            operation.record_remote_receipt(
                run_id, **fence, outcome=receipt_state, action=action, detail=detail,
            )
        summary = {
            "provider_id": "lumen_flow", "mode": mode,
            "extraction_status": "failed", "payment_status": "not_started",
            "remote_result_state": "failed", "remote_terminal_failure": True,
            "cause_code": "extract_provider_failed",
        }
        summary.update(finish_summary or {})
        return operation.finish_run(
            run_id, **fence, status="failed", message="平台提链失败", error="平台提链失败",
            result_summary=summary,
        )

    def test_terminal_auto_payment_create_intent_does_not_block_retry(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        for receipt, save_job, extraction in (
            ("confirmed", True, "failed"), ("started", True, "failed"),
            ("started", False, "failed"), ("unknown", True, "unknown"),
        ):
            with self.subTest(receipt=receipt, save_job=save_job, extraction=extraction):
                finished = self._finish_provider_failure(
                    mode="auto_payment", receipt_state=receipt, save_job=save_job,
                    provider_state={
                        "extraction_state": extraction, "payment_state": "not_started",
                        "summary": {"remote_status": "FAILED" if extraction == "failed" else "RUNNING",
                                    "remote_terminal_failure": extraction == "failed"},
                    },
                    finish_summary={"extraction_status": extraction, "remote_terminal_failure": extraction == "failed"},
                )
                self.assertEqual("failed" if receipt == "confirmed" else "attention_required", finished["status"])
                self.assertFalse(extract_link_jobs.has_unresolved_auto_payment(finished["account_id"]))
                saved = operation.get_run(finished["id"])
                self.assertEqual(receipt, saved["data"]["remote_intent"]["receipt_state"])

    def test_terminal_auto_payment_still_blocks_actual_payment_from_job_or_summary(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        for source_index, source in enumerate(("job", "summary")):
            for payment_index, payment in enumerate(("pending", "unknown", "succeeded")):
                with self.subTest(source=source, payment=payment):
                    account_id = 77 + source_index * 3 + payment_index
                    task = operation.create_runtime_task(
                        task_type="extract_link", account_id=account_id, email="payment@example.test",
                        data={"provider_id": "huanguang", "mode": "auto_payment"},
                    )
                    run_id = int(task["run"]["id"])
                    if source == "job":
                        extract_link_jobs.save_provider_job(run_id, "huanguang", "payment-job", {
                            "extraction_state": "failed", "payment_state": payment,
                        }, {})
                    operation.finish_run(run_id, status="failed", result_summary={
                        "payment_status": payment if source == "summary" else "not_started",
                    })
                    self.assertTrue(extract_link_jobs.has_unresolved_auto_payment(account_id))

    def test_active_auto_payment_create_intent_still_blocks_retry(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        account_id = self.seed(record_store.ACCOUNTS, [{"email": "active@example.test"}])[0]
        task = operation.create_runtime_task(
            task_type="extract_link", account_id=account_id, email="active@example.test",
            data={"provider_id": "huanguang", "mode": "auto_payment"},
        )
        run_id = int(task["run"]["id"])
        operation.claim_run(run_id, execution_id="active-worker", worker_pid=os.getpid())
        lease_token = operation.acquire_account_lease(account_id=account_id, run_id=run_id)
        operation.record_remote_intent(
            run_id, execution_id="active-worker", lease_token=lease_token,
            action="extract_link_create", request_id="active-create",
        )
        self.assertTrue(extract_link_jobs.has_unresolved_auto_payment(account_id))

    def test_confirmed_matching_provider_terminal_failure_can_finish_failed(self):
        for remote_status in ("FAILED", "ERROR", "CANCELED", "CANCELLED"):
            with self.subTest(remote_status=remote_status):
                finished = self._finish_provider_failure(provider_state={
                    "extraction_state": "failed", "payment_state": "not_started",
                    "summary": {"remote_status": remote_status, "remote_terminal_failure": True},
                })
                self.assertEqual("failed", finished["status"])
                self.assertFalse(finished["result_summary"].get("reconcile_required", False))
                self.assertNotEqual("request_unknown", finished["result_summary"].get("outcome"))
        finished = self._finish_provider_failure(
            provider_state={
                "extraction_state": "failed", "payment_state": "failed",
                "summary": {"remote_status": "FAILED", "remote_terminal_failure": True},
            },
            finish_summary={"payment_status": "failed"},
        )
        self.assertEqual("failed", finished["status"])
        self.assertFalse(finished["result_summary"].get("reconcile_required", False))

    def test_provider_failure_requires_matching_durable_terminal_evidence(self):
        cases = {
            "缺少远端任务": {"save_job": False},
            "缺少远端任务号": {"job_id": None},
            "不同远端任务": {"job_id": "another-job"},
            "不同平台": {"job_provider": "huanguang"},
            "回执平台不符": {"receipt_detail": {"provider_id": "huanguang"}},
            "历史回执缺少任务关联": {"receipt_detail": {"remote_job_id": None}},
            "调用方结果平台不符": {"finish_summary": {"provider_id": "huanguang"}},
            "调用方缺少明确失败标记": {"finish_summary": {"remote_terminal_failure": False}},
            "调用方已标待核实": {"finish_summary": {"reconcile_required": True}},
            "调用方仍标结果不明": {"finish_summary": {"outcome": "request_unknown"}},
            "调用方支付状态格式无效": {"finish_summary": {"payment_status": ["pending"]}},
            "不同远端动作": {"action": "extract_link_payment"},
            "其他任务类型": {"task_type": "synthetic_confirmed_failure"},
            "未取得回执": {"receipt_state": "started"},
            "仅观察响应": {"receipt_state": "response_received"},
            "远端结果不明": {"receipt_state": "unknown"},
            "仅调用方提供失败标记": {"provider_state": {
                "extraction_state": "failed", "payment_state": "not_started",
                "summary": {"remote_status": "FAILED"},
            }},
            "远端并未终止": {"provider_state": {
                "extraction_state": "failed", "payment_state": "not_started",
                "summary": {"remote_status": "RUNNING", "remote_terminal_failure": True},
            }},
        }
        for name, kwargs in cases.items():
            with self.subTest(name=name):
                finished = self._finish_provider_failure(**kwargs)
                self.assertEqual("attention_required", finished["status"])
                self.assertTrue(finished["result_summary"]["reconcile_required"])

    def test_provider_terminal_failure_does_not_hide_pending_or_unknown_payment(self):
        for payment_state in ("pending", "unknown", "succeeded"):
            for summary_payment in (payment_state, "not_started"):
                with self.subTest(payment_state=payment_state, summary_payment=summary_payment):
                    finished = self._finish_provider_failure(
                        provider_state={
                            "extraction_state": "failed", "payment_state": payment_state,
                            "summary": {"remote_status": "FAILED", "remote_terminal_failure": True},
                        },
                        finish_summary={"payment_status": summary_payment},
                    )
                    self.assertEqual("attention_required", finished["status"])
                    self.assertTrue(finished["result_summary"]["reconcile_required"])

    def test_real_operation_context_persists_polled_failure_with_extraction_diagnosis(self):
        from core.extract_link import service as extract_link_service
        from core.operations import run_log as task_run_log
        from core.extract_link.contracts import ProviderJob
        from core.operations.task_gateway import OperationHandlerContext
        from core.storage.extract_link import jobs as extract_link_jobs
        from core.operations.progress import build_progress_snapshot

        email = "extract-flow@example.test"
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": email, "access_token": "synthetic-token",
            "created_at": "2026-10-23T00:00:00", "updated_at": "2026-10-23T00:00:00",
        }])[0]
        account = {"id": account_id, "email": email, "access_token": "synthetic-token"}
        reason = "当前账号不符合优惠条件"
        provider = SimpleNamespace(
            create_job=Mock(return_value=ProviderJob(
                job_id="flow-job", extraction_state="running", summary={"remote_status": "RUNNING"},
            )),
            get_status=Mock(return_value=ProviderJob(
                job_id="flow-job", extraction_state="failed",
                summary={"remote_status": "FAILED", "remote_terminal_failure": True, "failure_message": reason},
            )),
            start_payment=Mock(), get_automatic_payment_status=Mock(),
        )
        with (
            tempfile.TemporaryDirectory() as log_dir,
            patch.object(task_run_log, "_LOG_ROOT", Path(log_dir)),
            patch.object(task_run_log, "_TASK_LOG_ROOT", Path(log_dir) / "tasks"),
            patch.object(extract_link_service.db, "get_account", return_value=account),
            patch.object(extract_link_service.db, "account_is_deactivated", return_value=False),
            patch("core.accounts.plans.promotion.is_extract_link_eligible", return_value=True),
            patch.object(extract_link_service.db, "mark_account_extract_running", return_value=True),
            patch.object(extract_link_service, "_ensure_extract_token", return_value="synthetic-token"),
            patch.object(extract_link_service, "_provider_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_configuration", return_value=SimpleNamespace(
                default_type="momo", event_timeout=10, poll_interval=1, timeout=30,
            )),
            patch.object(extract_link_service, "_provider", return_value=provider),
            patch.object(extract_link_service.db, "update_account_extract") as save_account,
            patch.object(extract_link_service.time, "sleep"),
        ):
            task = operation.create_runtime_task(
                task_type="extract_link", account_id=account_id, email=email, trigger="test",
                data={"provider_id": "lumen_flow", "mode": "extract_only", "link_type": "momo"},
            )
            run_id = int(task["run"]["id"])
            claimed = operation.claim_run(run_id, execution_id="flow-worker", worker_pid=os.getpid())
            self.assertIsNotNone(claimed)
            context = OperationHandlerContext(claimed, execution_id="flow-worker")
            extract_link_service._handle_provider_operation(context)

        run = operation.get_run(run_id)
        task = operation.get_task(int(task["id"]))
        job = extract_link_jobs.get_provider_job_public(run_id)
        self.assertTrue(context.finished)
        self.assertEqual("failed", run["status"])
        self.assertEqual("failed", task["status"])
        self.assertEqual("extraction", run["result_summary"]["failure_stage"])
        self.assertEqual("extraction", task["failure_stage"])
        self.assertEqual("extract_provider_failed", run["error_code"])
        self.assertEqual("confirmed", run["data"]["remote_receipt"]["receipt_state"])
        self.assertEqual("flow-job", run["data"]["remote_receipt"]["detail"]["remote_job_id"])
        self.assertFalse(run["result_summary"].get("reconcile_required", False))
        self.assertEqual(reason, run["result_summary"]["failure_message"])
        self.assertEqual(reason, job["public_state"]["summary"]["failure_message"])
        self.assertEqual("not_started", job["payment_state"])
        self.assertIn(reason, save_account.call_args.args[1]["message"])
        provider.get_status.assert_called_once()
        provider.start_payment.assert_not_called()
        provider.get_automatic_payment_status.assert_not_called()
        snapshot = build_progress_snapshot(int(task["id"]), run_id, "extract_link", run, task["events"])
        self.assertEqual("extraction", snapshot["failure"]["stage"])
        self.assertEqual("explicit", snapshot["failure"]["evidence"])
        self.assertEqual("LINK-FAILED", snapshot["failure"]["error_info"]["display_code"])

    def test_provider_polling_summary_roundtrip_keeps_safe_fields_without_private_payloads(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link", account_id=None, email="summary@example.test", trigger="test",
            data={"provider_id": "lumen_flow", "mode": "auto_payment"},
        )
        summary = {
            "completed_steps": 1, "total_steps": 5, "run_attempt": 2, "step_attempt": 3,
            "failure_code": "remote_read_timeout", "failure_type": "ReadTimeout", "last_event": "step.failed",
            "plus_verification_status": "pending", "automatic_payment_status": "queued",
            "automatic_payment_terminal": False, "automatic_payment_requires_reconcile": True,
            "remote_polling": True, "payment_check_status": "pending", "platform_plus_status": "unknown",
            "entitlement_active": False, "entitlement_inferred": True, "queue_position": 7,
            "max_attempts": 4, "cdk_state": "allocated",
            "payment_confirmation_source": "local_plan_check", "payment_confirmed_plan_checked_at": "2026-10-23T01:00:00Z",
        }
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(run_id, "lumen_flow", "summary-job", {
            "extraction_state": "unknown", "payment_state": "unknown",
            "summary": {**summary, "raw": "raw-private-marker", "job_secret": "summary-private-marker"},
        }, {"job_secret": "private-resume-marker"})

        public = extract_link_jobs.get_provider_job_public(run_id)
        self.assertEqual(summary, {key: public["public_state"]["summary"].get(key) for key in summary})
        self.assertNotIn("raw-private-marker", repr(public))
        self.assertNotIn("summary-private-marker", repr(public))
        self.assertNotIn("private-resume-marker", repr(public))
        self.assertEqual("private-resume-marker", extract_link_jobs.get_provider_job_private(run_id)["private_data"]["job_secret"])

    def test_expired_provider_writer_cannot_replace_private_receipt_or_state(self):
        from core.operations.task_gateway import OperationLeaseLost
        from core.storage.extract_link import jobs as extract_link_jobs
        account_id = record_store.insert_row(record_store.ACCOUNTS, {"email": "fence@example.test", "access_token": "synthetic"})
        task = operation.create_runtime_task(task_type="extract_link", account_id=account_id, email="fence@example.test",
                                             data={"provider_id": "huanguang"})
        run_id = int(task["run"]["id"])
        operation.claim_run(run_id, execution_id="current-worker", worker_pid=123)
        token = operation.acquire_account_lease(account_id=account_id, run_id=run_id)
        fence = {"run_id": run_id, "execution_id": "current-worker", "lease_token": token}
        extract_link_jobs.save_provider_job(run_id, "huanguang", None, {"extraction_state": "unknown"},
            {"batch_receipt_secret": "original-private-receipt"}, execution_fence=fence)
        with self.assertRaises(OperationLeaseLost):
            extract_link_jobs.save_provider_job(run_id, "huanguang", "stale-job", {"extraction_state": "failed"},
                {"batch_receipt_secret": "stale-private-receipt"}, execution_fence={**fence, "execution_id": "expired-worker"})
        saved = extract_link_jobs.get_provider_job_private(run_id)
        self.assertIsNone(saved["job_id"])
        self.assertEqual("original-private-receipt", saved["private_data"]["batch_receipt_secret"])
        self.assertEqual("unknown", saved["extraction_state"])

    def test_child_transition_removes_parent_payment_materials(self):
        from core.storage.extract_link import jobs as extract_link_jobs
        task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="chain@example.test", data={"provider_id": "huanguang"})
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(run_id, "huanguang", "root-job", {
            "extraction_state": "succeeded", "links": ["https://example.test/parent"],
            "payment_links": ["https://example.test/pay-parent"], "payment_artifact": {"qr_data": "parent-qr"},
            "summary": {"remote_chain_length": 1}}, {"active_job_id": "root-job"})
        extract_link_jobs.save_provider_job(run_id, "huanguang", "root-job", {
            "extraction_state": "queued", "links": [], "payment_links": [], "payment_artifact": {},
            "summary": {"remote_chain_length": 2}}, {"active_job_id": "child-job"})
        saved = extract_link_jobs.get_provider_job_public(run_id)["public_state"]
        self.assertEqual([], saved["links"])
        self.assertEqual([], saved["payment_links"])
        self.assertEqual({}, saved["payment_artifact"])
        self.assertEqual(2, saved["summary"]["remote_chain_length"])

    def test_recovery_includes_interrupted_receipt_but_excludes_terminal_review_and_auth_unknown(self):
        from core.storage.extract_link import jobs as extract_link_jobs
        expected = []
        for status, job_id, public, private, recover in [
            ("interrupted", None, {"summary": {"submission_receipt_pending": True}}, {"batch_receipt_pending": True, "batch_receipt_secret": "synthetic"}, True),
            ("attention_required", "running-job", {"extraction_state": "running"}, {}, True),
            ("attention_required", "review-job", {"extraction_state": "succeeded", "payment_state": "unknown", "summary": {"remote_polling": False, "automatic_payment_requires_reconcile": True}}, {}, False),
            ("interrupted", "plan-query-job", {"extraction_state": "succeeded", "payment_state": "unknown", "plus_status": "pending",
                "summary": {"local_plan_check_pending": True, "remote_status": "DONE", "automatic_payment_terminal": True}}, {}, True),
            ("attention_required", "failed-plan-job", {"extraction_state": "succeeded", "payment_state": "unknown", "plus_status": "failed",
                "summary": {"local_plan_check_pending": False, "remote_status": "DONE", "automatic_payment_terminal": True}}, {}, False),
            ("attention_required", None, {"preflight_status": "failed"}, {}, False),
        ]:
            task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="recover@example.test", data={"provider_id": "huanguang"})
            run_id = int(task["run"]["id"])
            extract_link_jobs.save_provider_job(run_id, "huanguang", job_id, public, private)
            operation.finish_run(run_id, status=status)
            if recover:
                expected.append(run_id)
        rows = extract_link_jobs.list_recoverable_workbench_jobs()
        self.assertEqual(expected, [row["run_id"] for row in rows if row["run_id"] in expected or row["provider_id"] == "huanguang"])
        self.assertNotIn("synthetic", repr(rows))

    def test_delayed_receipt_recovery_finishes_same_run_without_unknown_fence(self):
        from contextlib import ExitStack
        from core.extract_link import service as extract_link_service
        from core.extract_link.contracts import ProviderJob
        from core.operations.task_gateway import OperationHandlerContext
        from core.storage.extract_link import jobs as extract_link_jobs
        account_id = record_store.insert_row(record_store.ACCOUNTS, {"email": "delayed@example.test", "access_token": "synthetic"})
        task = operation.create_runtime_task(task_type="extract_link", account_id=account_id, email="delayed@example.test",
            data={"provider_id": "huanguang", "mode": "extract_only", "link_type": "upi"})
        run_id = int(task["run"]["id"])
        claimed = operation.claim_run(run_id, execution_id="first", worker_pid=123)
        first = OperationHandlerContext(claimed, execution_id="first")
        with first.lease():
            first.remote_request_started("extract_link_create", request_id="original-request", detail={"provider_id": "huanguang"})
            extract_link_jobs.save_provider_job(run_id, "huanguang", None, {"extraction_state": "unknown", "preflight_status": "passed",
                "summary": {"submission_receipt_pending": True, "remote_polling": True}},
                {"batch_receipt_pending": True, "batch_receipt_secret": "synthetic-receipt"}, execution_fence=first.execution_fence)
            first.remote_request_receipt(outcome="response_received", action="extract_link_create", request_id="original-request")
            first.defer(delay_seconds=0, reason="等待回执", data={"extract_poll_continuation": True,
                "workbench_action": "sync_status", "provider_job_run_id": run_id})
        claimed = operation.claim_run(run_id, execution_id="second", worker_pid=124)
        second = OperationHandlerContext(claimed, execution_id="second")
        provider = SimpleNamespace(get_status=Mock(return_value=ProviderJob(job_id="recovered-job", extraction_state="failed",
            summary={"remote_status": "FAILED", "remote_terminal_failure": True, "remote_polling": False},
            private_data={"job_secret": "synthetic-job-secret", "batch_receipt_pending": False})), create_job=Mock())
        with ExitStack() as stack:
            for name, value in (("_provider_enabled", True), ("_provider_mode_enabled", True), ("_bool_setting", False)):
                stack.enter_context(patch.object(extract_link_service, name, return_value=value))
            stack.enter_context(patch.object(extract_link_service, "_provider", return_value=provider))
            stack.enter_context(patch.object(extract_link_service, "_provider_configuration", return_value=SimpleNamespace(
                default_type="upi", event_timeout=30, poll_interval=10, timeout=30)))
            stack.enter_context(patch.object(extract_link_service.db, "update_account_extract"))
            extract_link_service._handle_provider_operation(second)
        final = operation.get_run(run_id)
        self.assertEqual("failed", final["status"])
        self.assertEqual("confirmed", final["data"]["remote_receipt"]["outcome"])
        self.assertEqual("original-request", final["data"]["remote_receipt"]["request_id"])
        self.assertEqual(1, len(operation.get_task(task["id"])["runs"]))
        provider.get_status.assert_called_once()
        provider.create_job.assert_not_called()

    def test_recoverable_sync_without_current_job_keeps_actual_source_run(self):
        from core.storage.extract_link import jobs as extract_link_jobs
        task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="old-ref@example.test",
            data={"provider_id": "huanguang", "mode": "extract_only"})
        original_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(original_id, "huanguang", "original-job", {"extraction_state": "running"}, {"job_secret": "synthetic"})
        operation.finish_run(original_id, status="attention_required")
        latest = operation.retry_runtime_task(task["id"], data={"provider_id": "huanguang", "workbench_action": "sync_status",
            "provider_job_run_id": original_id, "extract_poll_continuation": True})
        # 模拟旧版本创建过但未写入当前同步快照的 Run。
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {operation._table('extract_link_provider_jobs')} WHERE run_id=%s", (latest["id"],))
        operation.finish_run(latest["id"], status="interrupted")
        rows = extract_link_jobs.list_recoverable_workbench_jobs()
        row = next(item for item in rows if item["task_id"] == task["id"])
        self.assertEqual(latest["id"], row["run_id"])
        self.assertEqual(original_id, row["provider_job_run_id"])

    def test_verified_parent_material_switch_does_not_merge_child_qr(self):
        from core.storage.extract_link import jobs as extract_link_jobs
        task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="material-owner@example.test", data={"provider_id": "huanguang"})
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(run_id, "huanguang", "root-job", {
            "extraction_state": "succeeded", "payment_artifact": {"qr_data": "child-qr"},
            "links": ["https://example.test/child"]}, {"active_job_id": "child-job", "material_job_id": "child-job"})
        extract_link_jobs.save_provider_job(run_id, "huanguang", "root-job", {
            "extraction_state": "succeeded", "payment_artifact": {"payment_page_url": "https://example.test/parent"},
            "links": ["https://example.test/parent"]}, {"active_job_id": "child-job", "material_job_id": "root-job"})
        saved = extract_link_jobs.get_provider_job_public(run_id)["public_state"]
        self.assertNotIn("qr_data", saved["payment_artifact"])
        self.assertEqual("https://example.test/parent", saved["payment_artifact"]["payment_page_url"])

    def test_sync_retry_keeps_provider_snapshot_while_new_run_is_queued(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link", account_id=None, email="sync-queue@example.test",
            data={"provider_id": "huanguang", "mode": "auto_payment",
                  "remote_intent": {"kind": "remote_write", "action": "extract_link_create"},
                  "remote_receipt": {"outcome": "confirmed"}},
        )
        original_id = int(task["run"]["id"])
        public_state = {
            "extraction_state": "succeeded", "payment_state": "unknown",
            "links": ["https://example.test/original-checkout"],
            "payment_artifact": {"qr_data": "synthetic-original-qr"},
            "summary": {"preflight_status": "passed", "remote_polling": False},
        }
        private_data = {"job_secret": "synthetic-queue-secret", "active_job_id": "original-job"}
        original_job = extract_link_jobs.save_provider_job(
            original_id, "huanguang", "original-job", public_state, private_data,
        )
        operation.finish_run(original_id, status="attention_required")

        queued = operation.retry_runtime_task(
            task["id"], data={"workbench_action": "sync_status"},
        )

        self.assertEqual("queued", queued["status"])
        self.assertEqual(queued["id"], operation.get_task(task["id"])["last_run_id"])
        copied_job = extract_link_jobs.get_provider_job_private(queued["id"])
        self.assertIsNotNone(copied_job)
        self.assertEqual("original-job", copied_job["job_id"])
        self.assertEqual(original_job["public_state"], copied_job["public_state"])
        self.assertEqual(private_data, copied_job["private_data"])
        self.assertNotIn("remote_intent", queued["data"])
        self.assertNotIn("remote_receipt", queued["data"])
        self.assertNotIn("synthetic-queue-secret", repr(operation.get_task(task["id"])))
        self.assertNotIn("synthetic-queue-secret", repr(extract_link_jobs.get_provider_job_public(queued["id"])))

    def test_sync_retry_uses_explicit_same_task_provider_snapshot(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link", account_id=None, email="sync-source@example.test",
            data={"provider_id": "huanguang", "mode": "auto_payment"},
        )
        original_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            original_id, "huanguang", "selected-job", {"extraction_state": "succeeded"},
            {"job_secret": "synthetic-selected-secret"},
        )
        operation.finish_run(original_id, status="attention_required")
        previous = operation.retry_runtime_task(task["id"], data={"workbench_action": "create"})
        extract_link_jobs.save_provider_job(
            previous["id"], "huanguang", "different-job", {"extraction_state": "failed"},
            {"job_secret": "synthetic-different-secret"},
        )
        operation.finish_run(previous["id"], status="failed")

        queued = operation.retry_runtime_task(task["id"], data={
            "workbench_action": "sync_status", "provider_job_run_id": original_id,
        })

        copied_job = extract_link_jobs.get_provider_job_private(queued["id"])
        self.assertIsNotNone(copied_job)
        self.assertEqual("selected-job", copied_job["job_id"])
        self.assertEqual("synthetic-selected-secret", copied_job["private_data"]["job_secret"])

    def test_sync_retry_never_copies_an_unrelated_or_missing_provider_snapshot(self):
        from core.storage.extract_link import jobs as extract_link_jobs

        source = operation.create_runtime_task(
            task_type="extract_link", account_id=None, email="other-source@example.test",
            data={"provider_id": "huanguang"},
        )
        source_id = int(source["run"]["id"])
        extract_link_jobs.save_provider_job(
            source_id, "huanguang", "unrelated-job", {"extraction_state": "succeeded"},
            {"job_secret": "synthetic-unrelated-secret"},
        )
        for case, task_type, provider_id, action, explicit_source in (
            ("other-task", "extract_link", "huanguang", "sync_status", source_id),
            ("other-provider", "extract_link", "lumen_flow", "sync_status", None),
            ("create", "extract_link", "huanguang", "create", None),
            ("other-type", "plan_check", "huanguang", "sync_status", None),
            ("missing", "extract_link", "huanguang", "sync_status", source_id + 1000),
        ):
            with self.subTest(case=case):
                task = operation.create_runtime_task(
                    task_type=task_type, account_id=None, email="unrelated@example.test",
                    data={"provider_id": provider_id},
                )
                run_id = int(task["run"]["id"])
                extract_link_jobs.save_provider_job(
                    run_id, "huanguang", "own-job", {"extraction_state": "succeeded"},
                    {"job_secret": "synthetic-own-secret"},
                )
                operation.finish_run(run_id, status="attention_required")
                data = {"workbench_action": action}
                if explicit_source is not None:
                    data["provider_job_run_id"] = explicit_source
                queued = operation.retry_runtime_task(task["id"], data=data)
                self.assertIsNone(extract_link_jobs.get_provider_job_private(queued["id"]))
