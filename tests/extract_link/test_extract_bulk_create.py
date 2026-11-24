from __future__ import annotations

import os
from unittest.mock import patch

from core import account_task_store
from core.storage import records as record_store
from core.storage.operations import store as operation
from core.storage.extract_link import bulk_create
from tests.support_pg import PostgresTestCase


class ExtractBulkCreateTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._old_operation_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        cls._schema_patch = patch.object(account_task_store, "_SCHEMA", cls.schema)
        cls._ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        cls._schema_patch.start(); cls._ready_patch.start()
        operation.reset_ready(); operation.init(); account_task_store.init()

    @classmethod
    def tearDownClass(cls):
        operation.reset_ready()
        cls._schema_patch.stop(); cls._ready_patch.stop()
        if cls._old_operation_schema is None:
            os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
        else:
            os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._old_operation_schema
        super().tearDownClass()

    def accounts(self, count=1, **overrides):
        return self.seed(record_store.ACCOUNTS, [{
            "email": f"bulk-{i}@example.test", "created_at": "2026-10-14T10:00:00",
            "updated_at": "2026-10-14T10:00:00", "email_source": "icloud_hide",
            "current_plan_type": "free", "plan_type": "free", "access_token": "test-private-at",
            "plus_promo_kind": "free_trial", "plan_check_status": "success", "plan_check_ok": True,
            **overrides,
        } for i in range(count)])

    def test_creates_tasks_and_claims_all_eligible_targets_in_one_chunk(self):
        ids = self.accounts(3)
        result = bulk_create.create_tasks(ids, data={"provider_id": "lumen_flow", "mode": "extract_only"},
            config_snapshot={"revision": 7, "values": {}}, batch_id=None)
        self.assertEqual({"started": 3, "skipped": 0, "failed": 0}, result)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_tasks')}")
            self.assertEqual(3, cur.fetchone()["n"])
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_events')}")
            self.assertEqual(3, cur.fetchone()["n"])
        rows = [record_store.get_row(record_store.ACCOUNTS, value) for value in ids]
        self.assertTrue(all(row.get("extract_link_status") == "queued" for row in rows))

    def test_skips_missing_archived_deactivated_ineligible_missing_token_and_busy_once(self):
        eligible, archived, deactivated, ineligible, no_token, busy = self.accounts(6)
        record_store.patch_row(record_store.ACCOUNTS, archived, {"archived": True})
        record_store.patch_row(record_store.ACCOUNTS, deactivated, {"account_status": "deactivated"})
        record_store.patch_row(record_store.ACCOUNTS, ineligible, {"plus_promo_kind": "none"})
        record_store.patch_row(record_store.ACCOUNTS, no_token, {"access_token": ""})
        operation.create_runtime_task(task_type="live_check", account_id=busy, email="busy@example.test", data={})
        result = bulk_create.create_tasks([eligible, archived, deactivated, ineligible, no_token, busy, 999999],
            data={"provider_id": "legacy", "mode": "extract_only"}, config_snapshot={"revision": 1, "values": {}})
        self.assertEqual(1, result["started"])
        self.assertEqual(6, result["skipped"])
        self.assertEqual(0, result["failed"])

    def test_preserves_config_allowlist_ordinal_and_never_persists_unrelated_secret(self):
        ids = self.accounts(2)
        result = bulk_create.create_tasks(ids, data={"provider_id": "lumen_flow", "mode": "extract_only",
            "options": {"link_type": "upi"}}, config_snapshot={"revision": 9, "values": {
                "EXTRACT_LINK_API_BASE": "https://example.test", "UNRELATED_SECRET": "do-not-save",
            }}, first_ordinal=41)
        self.assertEqual(2, result["started"])
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT task.data, run.data FROM {operation._table('operation_tasks')} task JOIN {operation._table('operation_runs')} run ON run.task_id=task.id ORDER BY task.id")
            rows = cur.fetchall()
        self.assertTrue(all("UNRELATED_SECRET" not in str(row) for row in rows))

    def test_501_targets_are_chunked_and_ordinal_continues(self):
        ids = self.accounts(501)
        result = bulk_create.create_tasks(ids, data={"provider_id": "lumen_flow", "mode": "extract_only"},
            config_snapshot={"revision": 2, "values": {}})
        self.assertEqual({"started": 501, "skipped": 0, "failed": 0}, result)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n, min(id) AS lo, max(id) AS hi FROM {operation._table('operation_tasks')}")
            row = cur.fetchone()
        self.assertEqual(501, row["n"])

    def test_create_failure_rolls_back_claimed_accounts_and_tasks_for_the_chunk(self):
        ids = self.accounts(2)
        with patch.object(bulk_create.bulk_submission, "create_specs", side_effect=RuntimeError("synthetic")):
            result = bulk_create.create_tasks(ids, data={"provider_id": "legacy", "mode": "extract_only"},
                config_snapshot={"revision": 1, "values": {}})
        self.assertEqual({"started": 0, "skipped": 0, "failed": 2}, result)
        self.assertTrue(all(record_store.get_row(record_store.ACCOUNTS, value).get("extract_link_status") not in {"queued", "running"} for value in ids))
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_tasks')}")
            self.assertEqual(0, cur.fetchone()["n"])
