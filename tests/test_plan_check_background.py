"""离线验证套餐任务等待线路时的取消、lease fence 和进度上报。"""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import plan_check_service
from core.operation_runtime import OperationCancelled


class PlanCheckBackgroundTests(unittest.TestCase):
    def context(self, waiting_error=None):
        checkpoints = [None, None, waiting_error] if waiting_error is not None else None
        return SimpleNamespace(
            task_id=101, run_id=201, checkpoint=Mock(side_effect=checkpoints),
            report=Mock(return_value={}), finish=Mock(),
        )

    def run_query(self, context, acquire):
        with (
            patch.object(plan_check_service.db, "mark_account_plan_check_running", return_value=True),
            patch.object(plan_check_service.db, "update_account_plan_check") as update,
            patch("core.account_proxy.acquire_account_proxy", side_effect=acquire),
            patch.object(plan_check_service, "_query_account_plan", return_value={"ok": True}) as query,
            patch.object(plan_check_service, "_record_promotion_queries"),
            patch.object(plan_check_service, "_log_plan_result"),
        ):
            result = plan_check_service._run_plan_check(
                account_id=1, email="plan-wait@example.test", access_token="synthetic-token",
                trigger="test", proxy=None, timezone_offset_min="-", operation_context=context,
            )
        return result, update, query

    def test_wait_cancellation_remains_cancelled_before_plan_request(self):
        context = self.context(OperationCancelled("离线模拟线路等待被取消"))

        def acquire(**kwargs):
            kwargs["cancel"]()
            raise AssertionError("取消后不能交付线路")

        result, update, query = self.run_query(context, acquire)

        self.assertEqual("cancelled", result.get("status"))
        self.assertTrue(result.get("cancelled"))
        query.assert_not_called()
        self.assertEqual("cancelled", update.call_args.kwargs["result"]["status"])
        self.assertEqual("cancelled", context.finish.call_args.kwargs["status"])

    def test_wait_lease_loss_propagates_to_gateway_without_plan_writeback(self):
        context = self.context(plan_check_service.account_task_store.OperationLeaseLost("离线模拟 lease 丢失"))

        def acquire(**kwargs):
            kwargs["cancel"]()
            raise AssertionError("lease 丢失后不能交付线路")

        with self.assertRaises(plan_check_service.account_task_store.OperationLeaseLost):
            self.run_query(context, acquire)
        context.finish.assert_not_called()

    def test_wait_progress_is_persisted_as_network_note(self):
        context = self.context()
        route = SimpleNamespace(proxy_url="", public_dict=lambda: {"network_route": "direct"}, release=Mock())

        def acquire(**kwargs):
            kwargs["progress_callback"]("离线模拟后台正在补充线路")
            return route

        result, _, query = self.run_query(context, acquire)

        self.assertTrue(result.get("ok"))
        query.assert_called_once()
        events = [call.kwargs for call in context.report.call_args_list]
        self.assertTrue(any(
            event.get("stage") == "network"
            and event.get("message") == "离线模拟后台正在补充线路"
            and "state" not in event
            for event in events
        ))
        route.release.assert_called_once_with(reason="plan-check-1")
