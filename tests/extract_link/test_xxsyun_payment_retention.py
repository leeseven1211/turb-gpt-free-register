"""历史清理保留尚待恢复及被其他任务引用的独立支付。"""
import os
from unittest.mock import patch

from cryptography.fernet import Fernet

from core import account_task_store
from core.storage import records
from core.storage.extract_link import payments
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class PaymentOrderRetentionTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.patches = [patch.dict(os.environ, {"OPERATION_TASK_DB_SCHEMA": cls.schema,
            "TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()}),
            patch.object(account_task_store, "_SCHEMA", cls.schema),
            patch.object(account_task_store, "_READY_KEY", "")]
        for item in cls.patches:
            item.start()
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        operation.reset_ready()
        for item in reversed(cls.patches):
            item.stop()
        super().tearDownClass()

    def setUp(self):
        operation.init()
        self.account_id = records.insert_row(records.ACCOUNTS, {"email": "retention@example.test"})

    def order(self):
        task = operation.create_runtime_task(task_type="extract_link", account_id=self.account_id,
            email="retention@example.test", data={"provider_id": "huanguang", "payment_source": "xxsyun"})
        order = payments.reserve_payment_order(task_id=task["id"], run_id=task["run"]["id"],
            account_id=self.account_id, extract_provider_id="huanguang", extract_job_id="parent",
            material_job_id="child", payment_provider="xxsyun", material_fingerprint="a" * 64,
            api_base="https://upi.xxsyun.xyz/api/v1", api_key="synthetic-retention-key",
            request_body={"items": [{"at": "synthetic-retention-at", "link": "original-link"}]}, concurrency=5)
        operation.finish_run(task["run"]["id"], status="cancelled", message="隔离历史夹具")
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET completed_at=now()-interval '10 days' WHERE id=%s", (task["id"],))
        return task, order

    def test_pending_unknown_and_unverified_success_survive_history_cleanup(self):
        for state in ("pending", "unknown", "succeeded"):
            task, order = self.order()
            payments.update_payment_order(order["id"], run_id=task["run"]["id"], payment_state=state)
        snapshots = []
        result = operation.cleanup_terminal_history(retention_days=7, archive=snapshots.append)
        self.assertEqual(0, result["deleted_tasks"])
        self.assertFalse(snapshots)

    def test_canonical_survives_alias_then_terminal_orders_are_archived(self):
        canonical_task, canonical = self.order()
        payments.update_payment_order(canonical["id"], run_id=canonical_task["run"]["id"],
            remote_order_id="canonical-original", payment_state="succeeded", summary={"plus_verification_status": "confirmed"})
        alias_task, alias = self.order()
        payments.update_payment_order(alias["id"], run_id=alias_task["run"]["id"], payment_state="succeeded",
            summary={"related_payment_order_id": canonical["id"], "plus_verification_status": "confirmed"})
        snapshots = []
        first = operation.cleanup_terminal_history(retention_days=7, archive=snapshots.append)
        self.assertEqual(1, first["deleted_tasks"])
        self.assertIsNotNone(payments.get_payment_order(canonical["id"]))
        self.assertIsNone(payments.get_payment_order(alias["id"]))
        second = operation.cleanup_terminal_history(retention_days=7, archive=snapshots.append)
        self.assertEqual(1, second["deleted_tasks"])
        archived = [row for snapshot in snapshots for row in snapshot["extract_link_payment_orders"]]
        self.assertEqual({canonical["id"], alias["id"]}, {row["id"] for row in archived})
        self.assertTrue(all(row["private_encrypted"].startswith("gAAAA") for row in archived))
        self.assertNotIn("synthetic-retention-at", repr(archived))
