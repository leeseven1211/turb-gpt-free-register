"""提链取消写回只释放当前占用，保留重跑与已出链事实。"""
from __future__ import annotations

import os
import uuid
from unittest.mock import patch

from core import account_task_store, db
from core.storage import records as record_store
from core.storage.extract_link import batches as extract_link_batches, jobs as extract_link_jobs
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class ExtractBatchCancelAccountTests(PostgresTestCase):
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
            "email": f"cancel-{uuid.uuid4().hex}@example.test", "created_at": "2026-10-14T10:00:00",
            "updated_at": "2026-10-14T10:00:00", "current_plan_type": "free",
            "plan_type": "free", "access_token": "fixture-at", "plus_promo_kind": "free_trial",
            "plan_check_status": "success", "plan_check_ok": True,
            "extract_link_status": "queued", "extract_link_queued_at": "2026-10-14T10:00:00",
            **changes,
        }])[0]

    def task(self, account_id, **kwargs):
        return operation.create_runtime_task(
            task_type="extract_link", account_id=account_id, email="cancel-fixture@example.test",
            data={"provider_id": "huanguang", "mode": "extract_only"}, **kwargs,
        )

    def version(self, account_id):
        return record_store.get_row(record_store.ACCOUNTS, account_id, include_version=True)["__record_version"]

    def cancel(self, task):
        operation.request_run_cancel(task["run"]["id"])

    def test_cancel_releases_queued_account_for_candidates_and_next_claim(self):
        account_id = self.account(extract_link_error="旧错误")
        task = self.task(account_id)
        version = self.version(account_id)
        self.cancel(task)

        self.assertTrue(extract_link_batches.sync_cancelled_account_extraction(
            task["run"]["id"], expected_account_version=version,
        ))
        account = record_store.get_row(record_store.ACCOUNTS, account_id)
        self.assertEqual("cancelled", account["extract_link_status"])
        self.assertFalse(account["extract_link_ok"])
        self.assertIsNone(account["extract_link_error"])
        self.assertTrue(account["extract_link_completed_at"])
        self.assertEqual([account_id], [row["account_id"] for row in extract_link_batches.candidate_accounts()["items"]])
        self.assertTrue(db.claim_account_extract(account_id))
        self.assertEqual("queued", record_store.get_row(record_store.ACCOUNTS, account_id)["extract_link_status"])

    def test_repeated_cancel_repairs_old_queued_or_running_projection(self):
        for status in ("queued", "running"):
            with self.subTest(status=status):
                account_id = self.account(extract_link_status=status, extract_link_started_at="2026-10-14T10:01:00")
                task = self.task(account_id)
                self.cancel(task)
                self.assertTrue(extract_link_batches.sync_cancelled_account_extraction(task["run"]["id"]))
                self.assertEqual("cancelled", record_store.get_row(record_store.ACCOUNTS, account_id)["extract_link_status"])
                self.assertTrue(extract_link_batches.sync_cancelled_account_extraction(task["run"]["id"]))
                record_store.delete_rows(record_store.ACCOUNTS, [account_id])

    def test_new_claim_without_run_is_protected_by_snapshot_version(self):
        account_id = self.account()
        task = self.task(account_id)
        version = self.version(account_id)
        self.cancel(task)
        self.assertTrue(db.claim_account_extract(account_id, trigger="新提链", link_type="upi"))

        self.assertFalse(extract_link_batches.sync_cancelled_account_extraction(
            task["run"]["id"], expected_account_version=version,
        ))
        account = record_store.get_row(record_store.ACCOUNTS, account_id)
        self.assertEqual("queued", account["extract_link_status"])
        self.assertEqual("新提链", account["extract_link_trigger"])
        self.assertEqual("upi", account["extract_link_type"])

    def test_claim_after_old_run_created_is_kept_even_when_snapshot_version_matches(self):
        account_id = self.account()
        task = self.task(account_id)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET created_at=now()-interval '5 minutes' WHERE id=%s", (task["run"]["id"],))
        self.assertTrue(db.claim_account_extract(account_id, trigger="快照之前的新占用"))
        version = self.version(account_id)
        self.cancel(task)
        self.assertFalse(extract_link_batches.sync_cancelled_account_extraction(
            task["run"]["id"], expected_account_version=version,
        ))
        self.assertEqual("快照之前的新占用", record_store.get_row(record_store.ACCOUNTS, account_id)["extract_link_trigger"])

    def test_old_cancel_does_not_overwrite_retry_or_newer_task(self):
        for retry in (True, False):
            with self.subTest(retry=retry):
                account_id = self.account()
                task = self.task(account_id)
                self.cancel(task)
                if retry:
                    operation.retry_runtime_task(task["id"])
                else:
                    self.task(account_id)
                self.assertTrue(extract_link_batches.sync_cancelled_account_extraction(task["run"]["id"]))
                self.assertEqual("queued", record_store.get_row(record_store.ACCOUNTS, account_id)["extract_link_status"])
                record_store.delete_rows(record_store.ACCOUNTS, [account_id])

    def test_other_older_active_extract_operation_keeps_account_running(self):
        account_id = self.account(extract_link_status="running")
        self.task(account_id, resource_family="fixture_other_extract")
        task = self.task(account_id)
        version = self.version(account_id)
        self.cancel(task)
        self.assertTrue(extract_link_batches.sync_cancelled_account_extraction(
            task["run"]["id"], expected_account_version=version,
        ))
        self.assertEqual("running", record_store.get_row(record_store.ACCOUNTS, account_id)["extract_link_status"])

    def test_provider_success_restores_success_and_keeps_existing_material(self):
        for state, summary in (("succeeded", {}), ("unknown", {"extraction_ever_succeeded": True})):
            with self.subTest(state=state):
                account_id = self.account(
                    extract_link_long_url="https://example.test/checkout", extract_link_copy_paste="fixture-material",
                    extract_link_result_json='{"long_url":"https://example.test/checkout"}',
                )
                task = self.task(account_id)
                version = self.version(account_id)
                extract_link_jobs.save_provider_job(task["run"]["id"], "huanguang", "fixture-job", {
                    "extraction_state": state, "summary": summary,
                    "links": ["https://example.test/checkout"], "payment_artifact": {"copy_paste": "fixture-material"},
                }, {})
                self.cancel(task)
                self.assertTrue(extract_link_batches.sync_cancelled_account_extraction(
                    task["run"]["id"], expected_account_version=version,
                ))
                account = record_store.get_row(record_store.ACCOUNTS, account_id)
                self.assertEqual("success", account["extract_link_status"])
                self.assertTrue(account["extract_link_ok"])
                self.assertEqual("https://example.test/checkout", account["extract_link_long_url"])
                self.assertEqual("fixture-material", account["extract_link_copy_paste"])
                self.assertEqual(["https://example.test/checkout"], extract_link_jobs.get_provider_job_public(task["run"]["id"])["public_state"]["links"])
                record_store.delete_rows(record_store.ACCOUNTS, [account_id])

    def test_terminal_account_and_missing_account_need_no_writeback(self):
        account_id = self.account(extract_link_status="success", extract_link_ok=True, extract_link_message="已有链接")
        task = self.task(account_id)
        self.cancel(task)
        version = self.version(account_id)
        self.assertTrue(extract_link_batches.sync_cancelled_account_extraction(task["run"]["id"], expected_account_version="0"))
        self.assertEqual(version, self.version(account_id))
        self.assertEqual("已有链接", record_store.get_row(record_store.ACCOUNTS, account_id)["extract_link_message"])
        record_store.delete_rows(record_store.ACCOUNTS, [account_id])
        self.assertTrue(extract_link_batches.sync_cancelled_account_extraction(task["run"]["id"]))

    def test_ambiguous_historical_claim_time_is_not_overwritten(self):
        account_id = self.account()
        task = self.task(account_id)
        self.cancel(task)
        cancelled_at = operation.get_run(task["run"]["id"])["cancel_requested_at"]
        for queued_at in (None, "不是时间", cancelled_at):
            with self.subTest(queued_at=queued_at):
                record_store.patch_row(record_store.ACCOUNTS, account_id, {"extract_link_queued_at": queued_at})
                self.assertFalse(extract_link_batches.sync_cancelled_account_extraction(task["run"]["id"]))
                self.assertEqual("queued", record_store.get_row(record_store.ACCOUNTS, account_id)["extract_link_status"])

    def test_only_latest_native_cancelled_run_with_cancel_request_can_write(self):
        account_id = self.account()
        task = self.task(account_id)
        self.assertTrue(extract_link_batches.sync_cancelled_account_extraction(task["run"]["id"]))
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET status='cancelled' WHERE id=%s", (task["run"]["id"],))
        self.assertTrue(extract_link_batches.sync_cancelled_account_extraction(task["run"]["id"]))
        self.assertEqual("queued", record_store.get_row(record_store.ACCOUNTS, account_id)["extract_link_status"])
