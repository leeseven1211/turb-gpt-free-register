"""独立支付编排：来源冻结、回执恢复与支付后核验。"""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch


class IndependentPaymentRoutingTests(TestCase):
    def context(self):
        return SimpleNamespace(
            task_id=11, run_id=22, account_id=33, email="synthetic@example.test",
            run={"data": {"provider_id": "lumen_flow", "mode": "auto_payment", "payment_source": "xxsyun"}},
            config_snapshot={}, execution_fence={"owner": "synthetic"},
            checkpoint=Mock(), report=Mock(), finish=Mock(), defer=Mock(),
            lease=lambda **kwargs: nullcontext(),
        )

    def order(self, **changes):
        return {"id": 7, "task_id": 11, "origin_run_id": 20, "extract_provider_id": "lumen_flow",
                "extract_job_id": "extract-original", "material_job_id": "extract-original",
                "api_base": "https://pay.example.test/api/v1", "idempotency_key": "stable-key",
                "remote_order_id": "remote-original", "submission_state": "submitted", "payment_state": "pending",
                "submitted_at": "2026-11-02T00:00:00+00:00", "summary": {},
                "private": {"api_key": "original-key", "body": {"items": [{"at": "original-at", "link": "original-link"}], "dispatch_mode": "auto"}},
                **changes}

    def test_old_tasks_always_resolve_native(self):
        from core.extract_link import independent_payment as routing
        self.assertEqual("native", routing.frozen_source({}))
        self.assertEqual("xxsyun", routing.frozen_source({"payment_source": "xxsyun"}))

    def test_extraction_proxy_buffers_finish_and_keeps_fence(self):
        from core.extract_link import independent_payment as routing
        context = self.context()
        proxy = routing.ExtractionContext(context)
        proxy.finish(status="success", message="提链成功")
        self.assertTrue(proxy.finished)
        context.finish.assert_not_called()
        self.assertEqual("extract_only", proxy.run["data"]["mode"])
        self.assertEqual("native", proxy.run["data"]["payment_source"])
        self.assertIs(proxy.execution_fence, context.execution_fence)

    def test_pending_order_uses_original_identity_and_defers_without_success(self):
        from core.extract_link import independent_payment as routing
        context, order = self.context(), self.order()
        client = Mock()
        client.get_order.return_value = {"order_id": "remote-original", "state": "pending", "remote_status": "claimed", "summary": {}}
        with patch.object(routing, "XXSYUNClient", return_value=client) as cls, \
             patch.object(routing.payments, "get_task_payment_order", return_value=order), \
             patch.object(routing.payments, "update_payment_order", side_effect=lambda *a, **k: {**order, **k}), \
             patch.object(routing, "configuration", return_value=SimpleNamespace(timeout=30, poll_interval=10, concurrency=1)), \
             patch.object(routing, "_save_state"), patch.object(routing, "_saved_extraction", return_value={}):
            routing.handle(context, Mock())
        cls.assert_called_once_with(order["api_base"], "original-key", timeout=30)
        client.get_order.assert_called_once_with("remote-original")
        client.submit.assert_not_called()
        context.defer.assert_called_once()
        context.finish.assert_not_called()
        self.assertEqual("xxsyun", context.defer.call_args.kwargs["data"]["payment_source"])

    def test_missing_receipt_replays_exact_saved_body_and_key(self):
        from core.extract_link import independent_payment as routing
        context, order = self.context(), self.order(remote_order_id=None, submission_state="unknown")
        client = Mock()
        client.submit.return_value = {"order_id": "recovered-original", "state": "pending", "summary": {}}
        with patch.object(routing, "XXSYUNClient", return_value=client), \
             patch.object(routing.payments, "get_task_payment_order", return_value=order), \
             patch.object(routing.payments, "update_payment_order", side_effect=lambda *a, **k: {**order, **k}), \
             patch.object(routing, "configuration", return_value=SimpleNamespace(timeout=30, poll_interval=10, concurrency=1)), \
             patch.object(routing, "_save_state"), patch.object(routing, "_saved_extraction", return_value={}):
            routing.handle(context, Mock())
        client.submit.assert_called_once_with(order["private"]["body"], "stable-key")
        client.get_order.assert_not_called()
        context.finish.assert_not_called()

    def test_projection_uses_payment_submission_as_plus_freshness_anchor(self):
        from core.extract_link.workbench_queries import workbench_task_item
        row = {"task_id": 11, "task_created_at": "2026-11-01T00:00:00Z",
               "task_data": {"provider_id": "lumen_flow", "mode": "auto_payment", "payment_source": "xxsyun"},
               "public_state": {"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "pending",
                   "summary": {"payment_submitted_at": "2026-11-02T00:00:00Z"}}}
        account = {"plan_check_status": "success", "current_plan_type": "plus", "plan_checked_at": "2026-11-01T12:00:00Z"}
        item = workbench_task_item(row, account=account)
        self.assertEqual("pending", item["plus_status"])
        self.assertEqual("xxsyun", item["payment_source"])

    def test_cancelled_known_order_only_queries_and_reclaims_terminal_capacity(self):
        from core.extract_link import independent_payment as routing
        order = self.order(latest_run_id=22)
        client = Mock()
        client.get_order.return_value = {"state": "succeeded", "summary": {}, "remote_status": "completed"}
        with patch.object(routing.payments, "get_payment_order", return_value=order), \
             patch.object(routing.payments, "update_payment_order") as update, \
             patch.object(routing, "configuration", return_value=SimpleNamespace(timeout=30, poll_interval=10)), \
             patch.object(routing, "XXSYUNClient", return_value=client):
            routing._reconcile_cancelled_order(order)
        client.get_order.assert_called_once_with("remote-original")
        client.submit.assert_not_called()
        self.assertEqual("succeeded", update.call_args.kwargs["payment_state"])

    def test_cancelled_unknown_receipt_keeps_original_intent_without_post(self):
        from core.extract_link import independent_payment as routing
        order = self.order(latest_run_id=22, remote_order_id=None, submission_state="unknown")
        with patch.object(routing.payments, "update_payment_order") as update, patch.object(routing, "XXSYUNClient") as client:
            routing._reconcile_cancelled_order(order)
        client.assert_not_called()
        self.assertEqual("unknown", update.call_args.kwargs["payment_state"])
        self.assertIn("原幂等意图", update.call_args.kwargs["summary"]["failure_message"])

    def test_cancelled_unsent_reservation_is_released(self):
        from core.extract_link import independent_payment as routing
        order = self.order(latest_run_id=22, remote_order_id=None, submitted_at=None, submission_state="reserved")
        with patch.object(routing.payments, "update_payment_order") as update, patch.object(routing, "XXSYUNClient") as client:
            routing._reconcile_cancelled_order(order)
        client.assert_not_called()
        self.assertEqual("failed", update.call_args.kwargs["payment_state"])

    def test_xxsyun_respects_both_automatic_payment_switches(self):
        from core.extract_link import service
        for disabled in ("EXTRACT_LINK_AUTO_PAYMENT_ENABLED", "EXTRACT_LINK_LUMEN_FLOW_AUTO_PAYMENT_ENABLED"):
            with self.subTest(disabled=disabled):
                with patch.object(service, "_provider_enabled", return_value=True), \
                     patch.object(service, "_bool_setting", side_effect=lambda key, default=False: key != disabled), \
                     patch("core.payments.runtime.configuration", return_value=SimpleNamespace(api_key="synthetic")):
                    self.assertFalse(service._provider_mode_enabled("lumen_flow", "auto_payment", "xxsyun"))

    def test_failed_attempt_intent_survives_shared_capacity_defer(self):
        from core.extract_link import independent_payment as routing
        context, order = self.context(), self.order(payment_state="failed")
        context.run["data"]["independent_payment_new_attempt"] = True
        extraction = {"job_id": "original-extract", "public_state": {"extraction_state": "succeeded",
            "payment_artifact": {"payment_url": "https://payments.stripe.com/upi/instructions/new"}}, "private_data": {}}
        runtime = SimpleNamespace(api_base=order["api_base"], api_key="original-key", timeout=30, poll_interval=10, concurrency=1)
        with patch.object(routing.payments, "get_task_payment_order", return_value=order), \
             patch.object(routing.payments, "reserve_payment_order", side_effect=routing.payments.PaymentCapacityUnavailable), \
             patch.object(routing, "_saved_extraction", return_value=extraction), patch.object(routing, "_save_state"), \
             patch.object(routing.db, "get_account", return_value={"access_token": "synthetic"}), \
             patch.object(routing, "configuration", return_value=runtime):
            routing.handle(context, Mock())
        self.assertTrue(context.defer.call_args.kwargs["data"]["independent_payment_new_attempt"])
        context.finish.assert_not_called()

    def test_terminal_unsupported_material_finishes_partial_and_retry_reextracts(self):
        from core.extract_link import independent_payment as routing, service
        context = self.context()
        extraction = {"job_id": "original-extract", "public_state": {"extraction_state": "succeeded",
            "links": ["https://checkout.example.test/display"], "summary": {"remote_polling": False}}, "private_data": {}}
        with patch.object(routing.payments, "get_task_payment_order", return_value=None), \
             patch.object(routing, "_saved_extraction", return_value=extraction), patch.object(routing, "_save_state"):
            routing.handle(context, service)
        context.defer.assert_not_called()
        self.assertEqual("partial_success", context.finish.call_args.kwargs["status"])
        self.assertEqual("succeeded", context.finish.call_args.kwargs["result_summary"]["extraction_status"])
        self.assertEqual("MATERIAL_UNSUPPORTED", context.finish.call_args.kwargs["result_summary"]["failure_code"])
        task = {"id": 11, "account_id": 33, "data": {"provider_id": "lumen_flow", "mode": "auto_payment", "payment_source": "xxsyun", "link_type": "upi"}}
        with patch("core.storage.operations.store.retry_runtime_task", return_value={"id": 23}) as retry, \
             patch.object(routing.payments, "get_task_payment_order", return_value=None), \
             patch.object(service, "_provider_mode_enabled", return_value=True), \
             patch.object(routing.db, "claim_account_extract", return_value=True), \
             patch.object(service.account_task_store, "notify_dispatch"):
            routing.perform_action(task, action="retry", latest_run_id=22, prior_job=extraction, service=service)
            self.assertEqual("create", retry.call_args.kwargs["data"]["workbench_action"])
            routing.perform_action(task, action="sync_status", latest_run_id=22, prior_job=extraction, service=service)
            self.assertTrue(retry.call_args.kwargs["data"]["independent_payment_refresh_material"])
