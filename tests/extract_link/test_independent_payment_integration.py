"""使用真实隔离 PostgreSQL 和执行围栏验证提链到独立支付。"""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid

from cryptography.fernet import Fernet

from core import account_task_store, db
from core.extract_link import service, independent_payment as routing
from core.extract_link.contracts import ProviderJob
from core.operations.task_gateway import OperationHandlerContext
from core.storage import records
from core.storage.extract_link import payments, jobs, batches
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class IndependentPaymentIntegrationTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema_patches = [patch.dict(os.environ, {"OPERATION_TASK_DB_SCHEMA": cls.schema,
            "TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()}),
            patch.object(account_task_store, "_SCHEMA", cls.schema), patch.object(account_task_store, "_READY_KEY", "")]
        for item in cls.schema_patches:
            item.start()
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        operation.reset_ready()
        for item in reversed(cls.schema_patches):
            item.stop()
        super().tearDownClass()

    def setUp(self):
        operation.init()

    def account(self):
        return records.insert_row(records.ACCOUNTS, {"email": f"independent-{uuid.uuid4().hex}@example.test",
            "access_token": "synthetic-original-at", "plan_type": "free", "current_plan_type": "free",
            "plus_promo_kind": "free_trial", "plan_check_status": "success", "plan_check_ok": True})

    def context(self, run_id):
        execution_id = uuid.uuid4().hex
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET next_attempt_at=NULL WHERE id=%s", (run_id,))
        claimed = operation.claim_run(run_id, execution_id=execution_id, worker_pid=os.getpid())
        self.assertIsNotNone(claimed)
        return OperationHandlerContext(claimed, execution_id=execution_id)

    def settings(self, key, default=None):
        if key.endswith("_AUTO_PAYMENT_SOURCE"):
            return "xxsyun"
        if key.endswith("API_BASE"):
            return "https://upi.xxsyun.xyz/api/v1"
        if key.endswith("_API_KEY"):
            return "synthetic-original-key"
        if key.endswith("_CDK"):
            return "synthetic-extract-key"
        if key.endswith("_ENABLED"):
            return key not in {"EXTRACT_LINK_PREFLIGHT_ENABLED", "EXTRACT_LINK_POST_PAYMENT_PLAN_CHECK_ENABLED"}
        return default

    def patches(self, provider=None):
        stack = ExitStack()
        stack.enter_context(patch.object(service, "_runtime_setting", side_effect=self.settings))
        stack.enter_context(patch.object(service, "get_config_snapshot", return_value={}))
        stack.enter_context(patch.object(service.account_task_store, "notify_dispatch"))
        stack.enter_context(patch.object(service.account_task_store, "start_dispatcher", return_value=False))
        stack.enter_context(patch("core.operations.task_gateway.notify_dispatch"))
        stack.enter_context(patch("core.accounts.plans.promotion.is_extract_link_eligible", return_value=True))
        stack.enter_context(patch.object(routing, "configuration", return_value=SimpleNamespace(
            api_base="https://upi.xxsyun.xyz/api/v1", api_key="synthetic-original-key", timeout=30, poll_interval=10, concurrency=5)))
        stack.enter_context(patch.object(service, "_ensure_extract_token", return_value="synthetic-original-at"))
        if provider:
            stack.enter_context(patch.object(service, "_provider", return_value=provider))
            stack.enter_context(patch.object(service, "_prepare_huanguang_proxies", return_value=({}, [], [])))
            stack.enter_context(patch.object(service, "query_huanguang_cdk_quota", return_value={
                "ok": True, "extraction": {"required": True, "remaining": 100, "active": True},
                "payment": {"required": False, "remaining": None, "active": True}}))
        return stack

    def test_three_sources_freeze_batch_task_run_and_submit_extract_only(self):
        for provider_id in ("legacy", "lumen_flow", "huanguang"):
            with self.subTest(provider_id=provider_id):
                account_id = self.account()
                material = ProviderJob(job_id=f"extract-{provider_id}", extraction_state="succeeded",
                    payment_artifact={"payment_url": f"https://payments.stripe.com/upi/instructions/{provider_id}"},
                    private_data={"material_job_id": f"child-{provider_id}"})
                provider = SimpleNamespace(create_job=Mock(return_value=material), get_status=Mock(return_value=material),
                    start_payment=Mock(), get_automatic_payment_status=Mock())
                client = Mock()
                client.submit.return_value = {"order_id": f"payment-{provider_id}", "state": "pending", "summary": {}}
                with self.patches(provider), patch.object(routing, "XXSYUNClient", return_value=client), \
                     patch.object(batches, "candidate_accounts", return_value={"items": [{"account_id": account_id}], "filters": {}, "limit": 1}):
                    created = service.create_workbench_batch(provider_id=provider_id, mode="auto_payment", type="upi", limit=1)
                    task = operation.list_tasks(batch_id=created["batch_id"])["items"][0]
                    full = operation.get_task(task["id"])
                    self.assertEqual("xxsyun", full["data"]["payment_source"])
                    self.assertEqual("xxsyun", full["runs"][0]["data"]["payment_source"])
                    self.assertEqual("xxsyun", service.workbench_batch_detail(created["batch_id"])["payment_source"])
                    context = self.context(full["last_run_id"])
                    service._handle_provider_operation(context)
                self.assertTrue(context.deferred)
                self.assertFalse(context.finished)
                request = provider.create_job.call_args.args[0]
                self.assertEqual("extract_only", request.mode)
                provider.start_payment.assert_not_called()
                provider.get_automatic_payment_status.assert_not_called()
                order = payments.get_task_payment_order(task["id"])
                self.assertEqual(f"child-{provider_id}", order["material_job_id"])
                self.assertEqual("pending", order["payment_state"])
                row = service.list_workbench_tasks(batch_id=created["batch_id"])["items"][0]
                self.assertEqual("xxsyun", row["payment_source"])
                self.assertEqual("queued", row["task_status"])
                self.assertEqual(order["id"], row["payment_order"]["id"])

    def test_original_order_survives_restart_cross_run_and_stale_plus_does_not_confirm(self):
        account_id = self.account()
        task = operation.create_runtime_task(task_type="extract_link", account_id=account_id,
            email="synthetic@example.test", data={"provider_id": "lumen_flow", "mode": "auto_payment", "payment_source": "xxsyun", "link_type": "upi"})
        run_id = task["run"]["id"]
        jobs.save_provider_job(run_id, "lumen_flow", "original-extract", {"extraction_state": "succeeded",
            "payment_artifact": {"payment_url": "https://payments.stripe.com/upi/instructions/original"}}, {})
        order = payments.reserve_payment_order(task_id=task["id"], run_id=run_id, account_id=account_id,
            extract_provider_id="lumen_flow", extract_job_id="original-extract", material_job_id="original-extract",
            payment_provider="xxsyun", material_fingerprint="a"*64, api_base="https://upi.xxsyun.xyz/api/v1",
            api_key="synthetic-original-key", request_body={"items": [{"at": "synthetic-original-at", "link": "original-link"}], "dispatch_mode": "auto"}, concurrency=1)
        anchor = datetime.now(timezone.utc)
        payments.update_payment_order(order["id"], run_id=run_id, submitted_at=anchor,
            remote_order_id="original-order", submission_state="submitted", payment_state="pending")
        operation.finish_run(run_id, status="attention_required", message="进程中断待恢复")
        client = Mock()
        client.get_order.return_value = {"order_id": "original-order", "state": "succeeded", "summary": {}}
        def setting(key, default=None):
            return True if key == "EXTRACT_LINK_POST_PAYMENT_PLAN_CHECK_ENABLED" else self.settings(key, default)
        records.patch_row(records.ACCOUNTS, account_id, {"current_plan_type": "plus", "plan_check_status": "success",
            "plan_checked_at": (anchor-timedelta(minutes=1)).isoformat()})
        with self.patches(), patch.object(service, "_runtime_setting", side_effect=setting), \
             patch.object(routing, "XXSYUNClient", return_value=client), \
             patch("core.accounts.plans.service.run_account_plan_check_inline", return_value={"result": {"ok": True}}):
            self.assertEqual(1, routing.resume_orders(service))
            new_run_id = operation.get_task(task["id"])["last_run_id"]
            self.assertNotEqual(run_id, new_run_id)
            context = self.context(new_run_id)
            service._handle_provider_operation(context)
        self.assertTrue(context.deferred)
        self.assertEqual("pending", jobs.get_provider_job_public(new_run_id)["public_state"]["plus_status"])
        self.assertEqual(order["id"], payments.get_task_payment_order(task["id"])["id"])
        client.submit.assert_not_called()
        client.get_order.assert_called_once_with("original-order")
        records.patch_row(records.ACCOUNTS, account_id, {"plan_checked_at": (anchor+timedelta(minutes=1)).isoformat()})
        with self.patches(), patch.object(service, "_runtime_setting", side_effect=setting), patch.object(routing, "XXSYUNClient", return_value=client):
            context = self.context(new_run_id)
            service._handle_provider_operation(context)
        self.assertTrue(context.finished)
        self.assertEqual("success", operation.get_run(new_run_id)["status"])
        self.assertEqual("confirmed", jobs.get_provider_job_public(new_run_id)["public_state"]["plus_status"])

    def ready_task(self, *, provider_id="huanguang", child="child-original"):
        account_id = self.account()
        task = operation.create_runtime_task(task_type="extract_link", account_id=account_id,
            email="synthetic@example.test", data={"provider_id": provider_id, "mode": "auto_payment", "payment_source": "xxsyun", "link_type": "upi"})
        jobs.save_provider_job(task["run"]["id"], provider_id, "parent-original", {"extraction_state": "succeeded",
            "payment_artifact": {"payment_url": "https://payments.stripe.com/upi/instructions/"+child}},
            {"material_job_id": child})
        return task

    def test_timeout_same_run_replays_exact_persisted_intent_without_overwriting_checkpoint(self):
        from core.payments import PaymentError
        task = self.ready_task()
        client = Mock()
        client.submit.side_effect = [PaymentError("REQUEST_TIMEOUT", retryable=True, submission_unknown=True),
            {"order_id": "recovered-payment", "state": "pending", "summary": {}}]
        with self.patches(), patch.object(routing, "XXSYUNClient", return_value=client):
            first = self.context(task["run"]["id"])
            service._handle_provider_operation(first)
            saved = payments.get_task_payment_order(task["id"], include_private=True)
            self.assertEqual("unknown", saved["payment_state"])
            self.assertTrue(first.deferred)
            self.assertEqual("started", operation.get_run(first.run_id)["data"]["remote_intent"]["receipt_state"])
            records.patch_row(records.ACCOUNTS, task["account_id"], {"access_token": "changed-at-must-not-use"})
            payments.update_payment_order(saved["id"], run_id=first.run_id, next_poll_at=datetime.now(timezone.utc)-timedelta(seconds=1))
            second = self.context(task["run"]["id"])
            service._handle_provider_operation(second)
        self.assertTrue(second.deferred)
        self.assertEqual(2, client.submit.call_count)
        self.assertEqual(client.submit.call_args_list[0], client.submit.call_args_list[1])
        self.assertEqual(saved["private"]["body"], client.submit.call_args.args[0])
        self.assertEqual(saved["idempotency_key"], client.submit.call_args.args[1])
        self.assertEqual("confirmed", operation.get_run(second.run_id)["data"]["remote_intent"]["receipt_state"])
        self.assertEqual("recovered-payment", payments.get_task_payment_order(task["id"])["remote_order_id"])

    def test_failed_order_retry_preserves_new_attempt_through_capacity_wait_and_material_node(self):
        from core.payments import PaymentError
        task = self.ready_task(child="old-child")
        client = Mock()
        client.submit.side_effect = PaymentError("ACCOUNT_MISMATCH")
        with self.patches(), patch.object(routing, "XXSYUNClient", return_value=client):
            context = self.context(task["run"]["id"])
            service._handle_provider_operation(context)
        old = payments.get_task_payment_order(task["id"])
        self.assertEqual("failed", old["payment_state"])
        other = self.ready_task(provider_id="legacy", child="other-child")
        blocked = payments.reserve_payment_order(task_id=other["id"], run_id=other["run"]["id"], account_id=other["account_id"],
            extract_provider_id="legacy", extract_job_id="other-parent", material_job_id="other-child",
            payment_provider="xxsyun", material_fingerprint="b"*64, api_base="https://upi.xxsyun.xyz/api/v1",
            api_key="synthetic-original-key", request_body={"items": [{"at": "other-at", "link": "other-link"}], "dispatch_mode": "auto"}, concurrency=1)
        with self.patches(), patch.object(routing, "configuration", return_value=SimpleNamespace(
            api_base="https://upi.xxsyun.xyz/api/v1", api_key="synthetic-original-key", timeout=30, poll_interval=10, concurrency=1)):
            retry = service.perform_extract_workbench_action(task["id"], "retry")
            self.assertTrue(retry["accepted"])
            waiting = self.context(retry["run_id"])
            service._handle_provider_operation(waiting)
            self.assertTrue(waiting.deferred)
            self.assertTrue(operation.get_run(waiting.run_id)["data"]["independent_payment_new_attempt"])
            payments.update_payment_order(blocked["id"], run_id=other["run"]["id"], payment_state="failed", submission_state="rejected")
            client.submit.side_effect = None
            client.submit.return_value = {"order_id": "new-payment", "state": "pending", "summary": {}}
            with patch.object(routing, "XXSYUNClient", return_value=client):
                resumed = self.context(waiting.run_id)
                service._handle_provider_operation(resumed)
        new = payments.get_task_payment_order(task["id"])
        self.assertEqual(2, new["attempt_no"])
        self.assertNotEqual(old["idempotency_key"], new["idempotency_key"])
        self.assertEqual("old-child", new["material_job_id"])
        self.assertEqual("failed", payments.get_payment_order(old["id"])["payment_state"])
        self.assertFalse(operation.get_run(waiting.run_id)["data"]["independent_payment_new_attempt"])

    def test_expired_failed_order_reextracts_and_binds_new_material_node(self):
        from core.payments import PaymentError
        task = self.ready_task(child="child-expired")
        client = Mock()
        client.submit.side_effect = PaymentError("LINK_EXPIRED")
        with self.patches(), patch.object(routing, "XXSYUNClient", return_value=client):
            service._handle_provider_operation(self.context(task["run"]["id"]))
        old = payments.get_task_payment_order(task["id"], include_private=True)
        fresh = ProviderJob(job_id="new-parent", extraction_state="succeeded",
            payment_artifact={"payment_url": "https://payments.stripe.com/upi/instructions/new-child"},
            private_data={"material_job_id": "new-child"})
        provider = SimpleNamespace(create_job=Mock(return_value=fresh), get_status=Mock(return_value=fresh),
            start_payment=Mock(), get_automatic_payment_status=Mock())
        client.submit.side_effect = None
        client.submit.return_value = {"order_id": "new-material-payment", "state": "pending", "summary": {}}
        with self.patches(provider), patch.object(routing, "XXSYUNClient", return_value=client):
            retry = service.perform_extract_workbench_action(task["id"], "retry")
            self.assertTrue(retry["accepted"])
            service._handle_provider_operation(self.context(retry["run_id"]))
        new = payments.get_task_payment_order(task["id"], include_private=True)
        self.assertEqual("new-child", new["material_job_id"])
        self.assertEqual("child-expired", payments.get_payment_order(old["id"])["material_job_id"])
        self.assertNotEqual(old["private"]["body"], new["private"]["body"])
        self.assertIn("new-child", new["private"]["body"]["items"][0]["link"])
        self.assertEqual("extract_only", provider.create_job.call_args.args[0].mode)
        provider.get_automatic_payment_status.assert_not_called()

    def test_long_retry_after_survives_segmented_defer_and_restart(self):
        from core.payments import PaymentError
        task = self.ready_task()
        client = Mock()
        client.submit.side_effect = PaymentError("RATE_LIMITED", retryable=True, retry_after_seconds=900)
        with self.patches(), patch.object(routing, "XXSYUNClient", return_value=client):
            first = self.context(task["run"]["id"])
            service._handle_provider_operation(first)
            order = payments.get_task_payment_order(task["id"])
            due = jobs._workbench_timestamp(order["next_poll_at"])
            self.assertGreater((due-datetime.now(timezone.utc)).total_seconds(), 890)
            self.assertEqual(300, operation.get_run(first.run_id)["data"]["next_attempt_delay_seconds"])
            segment = self.context(first.run_id)
            service._handle_provider_operation(segment)
            self.assertTrue(segment.deferred)
            self.assertEqual(1, client.submit.call_count)
            operation.finish_run(first.run_id, status="attention_required", message="模拟进程重启")
            self.assertEqual(1, routing.resume_orders(service))
            latest = operation.get_task(task["id"])["last_run_id"]
            restarted = self.context(latest)
            service._handle_provider_operation(restarted)
            self.assertTrue(restarted.deferred)
            self.assertEqual(1, client.submit.call_count)
            self.assertEqual(order["next_poll_at"], payments.get_task_payment_order(task["id"])["next_poll_at"])
            payments.update_payment_order(order["id"], run_id=latest, next_poll_at=datetime.now(timezone.utc)-timedelta(seconds=1))
            client.submit.side_effect = None
            client.submit.return_value = {"order_id": "after-cooldown", "state": "pending", "summary": {}}
            service._handle_provider_operation(self.context(latest))
        self.assertEqual(2, client.submit.call_count)
        self.assertEqual(client.submit.call_args_list[0], client.submit.call_args_list[1])

    def test_duplicate_remote_order_follows_same_account_material_without_second_capacity_or_post(self):
        import hashlib
        original = self.ready_task(child="shared-child")
        link = "https://payments.stripe.com/upi/instructions/shared-child"
        canonical = payments.reserve_payment_order(task_id=original["id"], run_id=original["run"]["id"], account_id=original["account_id"],
            extract_provider_id="huanguang", extract_job_id="parent-original", material_job_id="shared-child",
            payment_provider="xxsyun", material_fingerprint=hashlib.sha256(link.encode()).hexdigest(),
            api_base="https://upi.xxsyun.xyz/api/v1", api_key="canonical-original-key",
            request_body={"items": [{"at": "canonical-at", "link": link}], "dispatch_mode": "auto"}, concurrency=2)
        payments.update_payment_order(canonical["id"], run_id=original["run"]["id"], remote_order_id="shared-remote",
            submission_state="submitted", payment_state="pending", submitted_at=datetime.now(timezone.utc))
        operation.finish_run(original["run"]["id"], status="partial_success", message="等待原单")
        follower = operation.create_runtime_task(task_type="extract_link", account_id=original["account_id"], email="synthetic@example.test",
            data={"provider_id": "lumen_flow", "mode": "auto_payment", "payment_source": "xxsyun", "link_type": "upi"})
        jobs.save_provider_job(follower["run"]["id"], "lumen_flow", "new-extract", {"extraction_state": "succeeded",
            "payment_artifact": {"payment_url": link}}, {"material_job_id": "shared-child"})
        client = Mock()
        client.submit.return_value = {"order_id": "shared-remote", "state": "pending", "summary": {}}
        with self.patches(), patch.object(routing, "XXSYUNClient", return_value=client) as client_type:
            context = self.context(follower["run"]["id"])
            service._handle_provider_operation(context)
            alias = payments.get_task_payment_order(follower["id"])
            self.assertIsNone(alias["remote_order_id"])
            self.assertEqual(canonical["id"], alias["summary"]["related_payment_order_id"])
            self.assertEqual("confirmed", operation.get_run(context.run_id)["data"]["remote_intent"]["receipt_state"])
            other = self.ready_task(child="other-node")
            payments.reserve_payment_order(task_id=other["id"], run_id=other["run"]["id"], account_id=other["account_id"],
                extract_provider_id="huanguang", extract_job_id="parent-other", material_job_id="other-node",
                payment_provider="xxsyun", material_fingerprint="c"*64, api_base="https://upi.xxsyun.xyz/api/v1",
                api_key="other-key", request_body={"items": [{"at": "other-at", "link": "other-link"}]}, concurrency=2)
            payments.update_payment_order(alias["id"], run_id=context.run_id, next_poll_at=datetime.now(timezone.utc)-timedelta(seconds=1))
            operation.finish_run(context.run_id, status="attention_required", message="模拟别名跨 Run 恢复")
            with patch.object(routing.payments, "list_recoverable_payment_orders", return_value=[
                {**alias, "latest_run_id": context.run_id, "latest_run_status": "attention_required", "task_status": "attention_required"}]):
                self.assertEqual(1, routing.resume_orders(service))
            latest = operation.get_task(follower["id"])["last_run_id"]
            client.get_order.return_value = {"order_id": "shared-remote", "state": "succeeded", "summary": {}}
            service._handle_provider_operation(self.context(latest))
        client.submit.assert_called_once()
        client.get_order.assert_called_once_with("shared-remote")
        self.assertEqual("canonical-original-key", client_type.call_args.args[1])
        self.assertEqual("succeeded", payments.get_task_payment_order(follower["id"])["payment_state"])
        self.assertEqual("pending", payments.get_payment_order(canonical["id"])["payment_state"])
        item = next(row for row in service.list_workbench_tasks()["items"] if row["task_id"] == follower["id"])
        self.assertEqual("shared-remote", item["payment_order"]["remote_order_id"])
        self.assertNotIn("related_payment_order_id", repr(item))

    def test_cross_account_duplicate_is_local_conflict_and_same_material_cannot_repost(self):
        import hashlib
        original, follower = self.ready_task(child="conflict"), self.ready_task(child="conflict")
        link = "https://payments.stripe.com/upi/instructions/conflict"
        canonical = payments.reserve_payment_order(task_id=original["id"], run_id=original["run"]["id"], account_id=original["account_id"],
            extract_provider_id="huanguang", extract_job_id="parent-original", material_job_id="conflict",
            payment_provider="xxsyun", material_fingerprint=hashlib.sha256(link.encode()).hexdigest(),
            api_base="https://upi.xxsyun.xyz/api/v1", api_key="canonical-key",
            request_body={"items": [{"at": "canonical-at", "link": link}]}, concurrency=2)
        payments.update_payment_order(canonical["id"], run_id=original["run"]["id"], remote_order_id="cross-account-original")
        client = Mock()
        client.submit.return_value = {"order_id": "cross-account-original", "state": "pending", "summary": {}}
        with self.patches(), patch.object(routing, "XXSYUNClient", return_value=client):
            context = self.context(follower["run"]["id"])
            service._handle_provider_operation(context)
        failed = payments.get_task_payment_order(follower["id"])
        self.assertEqual("partial_success", operation.get_run(context.run_id)["status"],
                         {key: operation.get_run(context.run_id).get(key) for key in ("result_summary", "error_message", "data")})
        self.assertEqual("LOCAL_PAYMENT_IDENTITY_CONFLICT", failed["summary"]["failure_code"])
        self.assertEqual("failed", failed["payment_state"])
        self.assertEqual("pending", payments.get_payment_order(canonical["id"])["payment_state"])
        same = payments.reserve_payment_order(task_id=follower["id"], run_id=context.run_id, account_id=follower["account_id"],
            extract_provider_id="huanguang", extract_job_id="parent-original", material_job_id="conflict",
            payment_provider="xxsyun", material_fingerprint=failed["material_fingerprint"], api_base=failed["api_base"],
            api_key="new-key", request_body={"items": [{"at": "new-at", "link": link}]}, concurrency=2, new_attempt=True)
        self.assertEqual(failed["id"], same["id"])
        client.submit.assert_called_once()
