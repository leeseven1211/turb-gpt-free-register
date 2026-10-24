"""父任务内联套餐核验不能提前结束原任务，也不能创建独立 Run。"""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import plan_check_service as service
from core.operation_runtime import OperationCancelled


class PlanCheckInlineTests(unittest.TestCase):
    def setUp(self):
        self.context = SimpleNamespace(
            account_id=77, task_id=810, run_id=811, checkpoint=Mock(),
            report=Mock(return_value={}), finish=Mock(),
            execution_fence={"run_id": 811, "execution_id": "fixture-execution", "lease_token": "fixture-lease"},
        )
        self.account = {"id": 77, "access_token": "fixture-token"}
        self.config = {
            "PLAN_CHECK_COUNTRIES": ["JP", "VN"], "PLAN_CHECK_TIMEOUT": 7,
            "PLAN_CHECK_MAX_ATTEMPTS": 3, "PLAN_CHECK_RETRY_DELAY": 2,
            "ACCOUNT_PLAN_CHECK_PROXY_MODE": "pool", "PLAN_CHECK_PAYMENT_METHODS_ENABLED": False,
        }

    def execute(self, country_query):
        with (
            patch.object(service, "get_config_snapshot", return_value=self.config),
            patch.object(service.db, "get_account", return_value=self.account),
            patch.object(service.db, "account_is_deactivated", return_value=False),
            patch.object(service.db, "claim_account_plan_check", return_value=True),
            patch("core.storage.plan_countries.mark_country_task_running", return_value=True),
            patch.object(service, "_run_country_plan_checks", side_effect=country_query),
            patch.object(service.account_task_store, "submit_durable_operation") as submit,
        ):
            result = service.run_account_plan_check_inline(
                account_id=77, email="fixture@example.test", access_token="fixture-token",
                trigger="extract_post_payment", operation_context=self.context,
            )
        submit.assert_not_called()
        return result

    def test_inline_uses_full_plan_config_and_parent_fence_without_finishing_parent(self):
        observed = {}
        def country_query(**kwargs):
            observed.update(kwargs)
            kwargs["reporter"].finish(status="success", message="国家套餐核验成功", result_summary={"ok": True})
            return {"ok": True, "current_plan_type": "plus"}

        result = self.execute(country_query)

        self.assertTrue(result["accepted"])
        self.assertEqual("plus", result["result"]["current_plan_type"])
        self.assertEqual(["JP", "VN"], observed["countries"])
        self.assertEqual(7, observed["config_snapshot"]["plan_check_timeout"])
        self.assertEqual(3, observed["config_snapshot"]["plan_check_max_attempts"])
        self.assertEqual(self.context.execution_fence, observed["fence"])
        self.context.finish.assert_not_called()
        self.assertTrue(any(call.kwargs.get("stage") == "plan_check" and call.kwargs.get("state") == "success"
                            for call in self.context.report.call_args_list))

    def test_inline_cancelled_query_does_not_finish_parent(self):
        def country_query(**kwargs):
            kwargs["reporter"].finish(status="cancelled", message="子步骤取消")
            return {"ok": False, "status": "cancelled"}
        result = self.execute(country_query)
        self.assertEqual("cancelled", result["result"]["status"])
        self.context.finish.assert_not_called()

    def test_inline_lease_loss_propagates_without_failure_writeback(self):
        def country_query(**_kwargs):
            raise service.account_task_store.OperationLeaseLost("测试租约失效")
        with self.assertRaises(service.account_task_store.OperationLeaseLost):
            self.execute(country_query)
        self.context.finish.assert_not_called()

    def test_inline_refuses_another_account_before_claiming_or_querying(self):
        with patch.object(service.db, "claim_account_plan_check") as claim:
            result = service.run_account_plan_check_inline(
                account_id=78, email="fixture@example.test", access_token="fixture-token",
                trigger="extract_post_payment", operation_context=self.context,
            )
        self.assertFalse(result["accepted"])
        claim.assert_not_called()

    def test_inline_parent_cancel_is_checked_before_claiming(self):
        self.context.checkpoint.side_effect = OperationCancelled("父任务取消")
        with patch.object(service.db, "claim_account_plan_check") as claim:
            with self.assertRaises(OperationCancelled):
                service.run_account_plan_check_inline(
                    account_id=77, email="fixture@example.test", access_token="fixture-token",
                    trigger="extract_post_payment", operation_context=self.context,
                )
        claim.assert_not_called()
