"""独立支付意图的跨 Run 身份、并发与密文恢复。"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
import uuid
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from cryptography.fernet import Fernet

from core import account_task_store
from core.storage import records
from core.storage.runtime_config import RuntimeConfigStoreError
from core.storage.operations import store as operation
from core.storage.extract_link import payments
from tests.support_pg import PostgresTestCase

BASE = "https://upi.xxsyun.xyz/api/v1"
BODY = {"items": [{"at": "private-original-at", "link": "https://payments.stripe.com/upi/instructions/private-material"}], "dispatch_mode": "auto"}


class PaymentOrderStorageTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.patches = [patch.dict(os.environ, {"OPERATION_TASK_DB_SCHEMA": cls.schema, "TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()}), patch.object(account_task_store, "_SCHEMA", cls.schema), patch.object(account_task_store, "_READY_KEY", "")]
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

    def task(self, *, claim=False):
        email = f"payment-{uuid.uuid4().hex}@example.test"
        account_id = records.insert_row(records.ACCOUNTS, {"email": email, "access_token": "synthetic"})
        task = operation.create_runtime_task(task_type="extract_link", account_id=account_id, email=email, data={"provider_id": "huanguang", "payment_source": "xxsyun"})
        run_id = task["run"]["id"]
        fence = None
        if claim:
            operation.claim_run(run_id, execution_id="active-worker", worker_pid=123)
            token = operation.acquire_account_lease(account_id=account_id, run_id=run_id)
            fence = {"run_id": run_id, "execution_id": "active-worker", "lease_token": token}
        return task, fence

    def args(self, task, **changes):
        return dict(task_id=task["id"], run_id=task["run"]["id"], account_id=task["account_id"], extract_provider_id="huanguang", extract_job_id="parent", material_job_id="child", payment_provider="xxsyun", material_fingerprint="a" * 64, api_base=BASE, api_key="private-original-key", request_body=deepcopy(BODY), concurrency=1, **changes)

    def test_private_payload_encrypted_and_public_projection_safe(self):
        task, _ = self.task()
        order = payments.reserve_payment_order(**self.args(task))
        self.assertEqual(("reserved", "pending"), (order["submission_state"], order["payment_state"]))
        self.assertNotIn("private", order)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT row_to_json(p)::text AS raw FROM {operation._table('extract_link_payment_orders')} p")
            raw = cur.fetchone()["raw"]
        for secret in ("private-original-at", "private-original-key", "private-material"):
            self.assertNotIn(secret, raw)
            self.assertNotIn(secret, repr(order))
        cipher = Fernet(os.environ["TURB_CONFIG_ENCRYPTION_KEY"].encode())
        self.assertEqual({"api_key": "private-original-key", "body": BODY}, json.loads(cipher.decrypt(json.loads(raw)["private_encrypted"].encode())))
        private = payments.get_payment_order(order["id"], include_private=True)["private"]
        self.assertEqual({"api_key": "private-original-key", "body": BODY}, private)
        with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()}):
            with self.assertRaises(RuntimeConfigStoreError) as caught:
                payments.get_payment_order(order["id"], include_private=True)
            self.assertEqual("decryption_failed", caught.exception.code)

    def test_cross_run_reuses_exact_original_key_body_and_material_identity(self):
        task, _ = self.task()
        first = payments.reserve_payment_order(**self.args(task))
        operation.finish_run(task["run"]["id"], status="attention_required", message="等待原支付单")
        current = operation.retry_runtime_task(task["id"])
        args = self.args(task)
        args.update(run_id=current["id"], api_key="changed-key", request_body={"items": [{"at": "changed-at", "link": BODY["items"][0]["link"]}]}, material_job_id="other-child")
        reused = payments.reserve_payment_order(**args)
        self.assertEqual(first["id"], reused["id"])
        self.assertEqual(first["idempotency_key"], reused["idempotency_key"])
        self.assertEqual(task["run"]["id"], reused["origin_run_id"])
        self.assertEqual("child", reused["material_job_id"])
        self.assertEqual(BODY, payments.get_task_payment_order(task["id"], include_private=True)["private"]["body"])
        payments.update_payment_order(first["id"], run_id=current["id"], remote_order_id="original-order", submission_state="submitted", payment_state="pending")

    def test_shared_capacity_reserved_until_terminal_and_not_per_extract_platform(self):
        first_task, _ = self.task()
        other_task, _ = self.task()
        first = payments.reserve_payment_order(**self.args(first_task))
        args = self.args(other_task)
        args["extract_provider_id"] = "lumen_flow"
        with self.assertRaises(payments.PaymentCapacityUnavailable):
            payments.reserve_payment_order(**args)
        payments.update_payment_order(first["id"], run_id=first_task["run"]["id"], payment_state="succeeded", submission_state="submitted", remote_order_id="one")
        self.assertNotEqual(first["id"], payments.reserve_payment_order(**args)["id"])

    def test_concurrent_reservations_same_task_create_one_stable_intent(self):
        task, _ = self.task()
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(lambda _: payments.reserve_payment_order(**self.args(task)), range(4)))
        self.assertEqual(1, len({row["id"] for row in rows}))
        self.assertEqual(1, len({row["idempotency_key"] for row in rows}))

    def test_concurrent_different_tasks_do_not_exceed_shared_capacity(self):
        tasks = [self.task()[0] for _ in range(4)]
        def reserve(task):
            try:
                return payments.reserve_payment_order(**self.args(task))
            except payments.PaymentCapacityUnavailable:
                return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(reserve, tasks))
        self.assertEqual(1, sum(row is not None for row in rows))

    def test_new_attempt_only_after_explicit_failure_and_has_new_key(self):
        task, _ = self.task()
        args = self.args(task)
        first = payments.reserve_payment_order(**args)
        self.assertEqual(first["id"], payments.reserve_payment_order(**args, new_attempt=True)["id"])
        payments.update_payment_order(first["id"], run_id=task["run"]["id"], submission_state="rejected", payment_state="failed")
        second = payments.reserve_payment_order(**args, new_attempt=True)
        self.assertNotEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(2, second["attempt_no"])
        self.assertEqual("failed", payments.get_payment_order(first["id"])["payment_state"])

    def test_execution_fence_and_cross_task_or_obsolete_run_rejected(self):
        from core.operations.task_gateway import OperationLeaseLost
        task, fence = self.task(claim=True)
        other, _ = self.task()
        first = payments.reserve_payment_order(**self.args(task), execution_fence=fence)
        with self.assertRaises(OperationLeaseLost):
            payments.update_payment_order(first["id"], run_id=task["run"]["id"], execution_fence={**fence, "execution_id": "stale-worker"}, remote_order_id="stale")
        with self.assertRaises((ValueError, LookupError)):
            payments.update_payment_order(first["id"], run_id=other["run"]["id"], payment_state="failed")
        operation.finish_run(task["run"]["id"], status="attention_required", message="等待")
        operation.retry_runtime_task(task["id"])
        with self.assertRaises((ValueError, LookupError, OperationLeaseLost)):
            payments.update_payment_order(first["id"], run_id=task["run"]["id"], payment_state="failed")
        self.assertIsNone(payments.get_payment_order(first["id"])["remote_order_id"])

    def test_foreign_account_and_run_cannot_reserve_another_tasks_order(self):
        task, _ = self.task()
        other, _ = self.task()
        for changes in ({"run_id": other["run"]["id"]}, {"account_id": other["account_id"]}):
            args = self.args(task)
            args.update(changes)
            with self.assertRaises((ValueError, LookupError)):
                payments.reserve_payment_order(**args)

    def test_remote_order_identity_is_unique_and_immutable(self):
        tasks = [self.task()[0] for _ in range(2)]
        orders = []
        for task in tasks:
            args = self.args(task)
            args["concurrency"] = 2
            orders.append(payments.reserve_payment_order(**args))
        payments.update_payment_order(orders[0]["id"], run_id=tasks[0]["run"]["id"], remote_order_id="shared")
        with self.assertRaises(ValueError):
            payments.update_payment_order(orders[1]["id"], run_id=tasks[1]["run"]["id"], remote_order_id="shared")
        with self.assertRaises(ValueError):
            payments.update_payment_order(orders[0]["id"], run_id=tasks[0]["run"]["id"], remote_order_id="different")

    def test_recovery_includes_success_until_plus_confirmed_and_scrubs_summary(self):
        task, _ = self.task()
        order = payments.reserve_payment_order(**self.args(task))
        payments.update_payment_order(order["id"], run_id=task["run"]["id"], payment_state="succeeded", summary={"failure_message": "private-original-key private-original-at", "raw": BODY, "plus_verification_status": "pending"})
        recoverable = payments.list_recoverable_payment_orders()
        self.assertEqual([order["id"]], [item["id"] for item in recoverable])
        self.assertEqual(task["run"]["id"], recoverable[0]["latest_run_id"])
        self.assertNotIn("private-original", repr(recoverable))
        payments.update_payment_order(order["id"], run_id=task["run"]["id"], summary={"plus_verification_status": "confirmed"})
        self.assertEqual([], payments.list_recoverable_payment_orders())

    def test_first_submission_timestamp_and_terminal_payment_state_cannot_regress(self):
        task, _ = self.task()
        order = payments.reserve_payment_order(**self.args(task))
        submitted = datetime.now(timezone.utc)
        payments.update_payment_order(order["id"], run_id=task["run"]["id"], submitted_at=submitted, submission_state="submitting")
        for changes in ({"submitted_at": submitted - timedelta(days=1)}, {"submitted_at": None}, {"request_body": BODY}, {"api_key": "new-key"}):
            with self.subTest(fields=list(changes)), self.assertRaises(ValueError):
                payments.update_payment_order(order["id"], run_id=task["run"]["id"], **changes)
        payments.update_payment_order(order["id"], run_id=task["run"]["id"], payment_state="succeeded")
        with self.assertRaises(ValueError):
            payments.update_payment_order(order["id"], run_id=task["run"]["id"], payment_state="pending")

    def test_payment_without_plan_check_does_not_recover_forever(self):
        task, _ = self.task()
        order = payments.reserve_payment_order(**self.args(task))
        payments.update_payment_order(order["id"], run_id=task["run"]["id"], payment_state="succeeded", summary={"plus_verification_status": "not_applicable"})
        self.assertEqual([], payments.list_recoverable_payment_orders())

    def test_plan_failure_classification_survives_private_summary_filter(self):
        task, _ = self.task()
        order = payments.reserve_payment_order(**self.args(task))
        saved = payments.update_payment_order(order["id"], run_id=task["run"]["id"], summary={"plus_failure_code": "PLAN_CHECK_ERROR", "plus_failure_message": "查询失败 private-original-at"})
        self.assertEqual("PLAN_CHECK_ERROR", saved["summary"]["plus_failure_code"])
        self.assertNotIn("private-original-at", saved["summary"]["plus_failure_message"])

    def test_cancelled_batch_original_order_remains_visible_for_read_only_capacity_recovery(self):
        task, _ = self.task()
        order = payments.reserve_payment_order(**self.args(task))
        batch = operation.create_runtime_batch(batch_type="extract_link", title="测试停止原单回收", requested_count=1)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_batches')} SET status='cancelled' WHERE id=%s", (batch["id"],))
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET batch_id=%s WHERE id=%s", (batch["id"], task["id"]))
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET cancel_requested_at=now() WHERE id=%s", (task["run"]["id"],))
        recoverable = payments.list_recoverable_payment_orders()
        self.assertEqual([order["id"]], [item["id"] for item in recoverable])
        self.assertEqual("cancelled", recoverable[0]["batch_status"])
        self.assertTrue(recoverable[0]["cancel_requested_at"])
