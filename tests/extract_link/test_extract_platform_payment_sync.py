"""原支付订单的到账证据不能被套餐查询失败或配置换卡覆盖。"""
from contextlib import contextmanager
import unittest
from unittest.mock import Mock, patch

from core.extract_link import service as service
from core.extract_link.contracts import ProviderJob
from tests.extract_link import test_extract_link_provider_flow as fixtures


class PlatformPaymentSyncTests(unittest.TestCase):
    _scenario = fixtures.ExtractLinkTerminalFailureFlowTests._scenario

    def test_manual_sync_existing_order_survives_provider_and_global_disable(self):
        task = {"id": 810, "task_type": "extract_link", "source_system": "native_operations", "status": "success",
            "last_run_id": 811, "data": {"provider_id": "legacy", "mode": "auto_payment"}}
        with patch("core.storage.operations.store.get_task", return_value=task), \
                patch("core.storage.extract_link.jobs.get_provider_job_public", return_value={"job_id": "fixture-job"}), \
                patch("core.storage.operations.store.retry_runtime_task", return_value={"run": {"id": 812}}) as retry, \
                patch.object(service.account_task_store, "notify_dispatch"), \
                patch.object(service, "_bool_setting", return_value=False), \
                patch.object(service, "_provider_enabled", return_value=False):
            result = service.perform_extract_workbench_action(810, "sync_status")
        self.assertTrue(result["accepted"])
        self.assertEqual("sync_status", retry.call_args.kwargs["data"]["workbench_action"])
        self.assertEqual(811, retry.call_args.kwargs["data"]["provider_job_run_id"])

    @contextmanager
    def sync(self, *, platform_status="confirmed", check_status="verified", plus_status="failed"):
        job = ProviderJob(job_id="fixture-job", extraction_state="succeeded", payment_state="succeeded",
            private_data={"legacy_payment_order_id": "fixture-order"}, summary={
                "automatic_payment_status": "COMPLETED", "automatic_payment_terminal": True,
                "platform_plus_status": platform_status, "payment_check_status": check_status,
                "platform_plus_checked_at": "2026-10-29T08:25:53Z",
            })
        prior = {"run_id": 811, "provider_id": "legacy", "job_id": "fixture-job",
            "private_data": {"legacy_payment_order_id": "fixture-order"}, "public_state": {
                "extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": plus_status,
                "preflight_status": "passed", "aftercare_status": "failed", "summary": {},
            }}
        with self._scenario(failed_job=job) as case, \
                patch.object(service, "_provider_job_for_sync", return_value=prior), \
                patch("core.storage.operations.store.get_task", return_value={"created_at": "2026-10-29T07:00:00Z"}):
            case.context.defer = Mock()
            case.context.run["data"].update(provider_id="legacy", mode="auto_payment", link_type="upi",
                workbench_action="sync_status", provider_job_run_id=811, extract_poll_continuation=True)
            case.prior = prior
            yield case

    def test_temporary_direct_query_failure_keeps_previously_confirmed_plus(self):
        with self.sync(plus_status="confirmed") as case:
            case.prior["public_state"]["summary"].update(payment_confirmation_source="platform_order_check",
                platform_plus_status="confirmed", payment_check_status="verified",
                platform_plus_checked_at="2026-10-29T08:25:53Z")
            case.provider.get_automatic_payment_status = Mock(side_effect=TimeoutError("网络暂不可用"))
            service._handle_provider_operation(case.context)
        self.assertEqual("success", case.context.finish.call_args.kwargs["status"])
        self.assertEqual("confirmed", case.save_job.call_args.args[3]["plus_status"])
        self.assertEqual("platform_order_check", case.save_job.call_args.args[3]["summary"]["payment_confirmation_source"])

    def test_official_plus_confirmation_survives_failed_local_plan_and_is_projected(self):
        with self.sync() as case, patch.object(service, "_payment_aftercare") as aftercare, \
                patch("core.accounts.plans.service.run_account_plan_check_inline") as plan:
            service._handle_provider_operation(case.context)
        case.context.defer.assert_not_called()
        plan.assert_not_called()
        aftercare.assert_not_called()
        result = case.context.finish.call_args.kwargs["result_summary"]
        self.assertEqual("confirmed", result["plus_status"])
        self.assertEqual("platform_order_check", result["payment_confirmation_source"])
        self.assertIn("支付平台已核验 Plus 到账", result["message"])
        state = case.save_job.call_args.args[3]
        item = service._workbench_task_item({"task_id": 810, "public_state": state,
            "task_data": {"provider_id": "legacy", "mode": "auto_payment"}})
        self.assertEqual("platform_order_check", item["payment_confirmation_source"])
        self.assertEqual("confirmed", item["plus_status"])

    def test_inferred_payment_settles_without_claiming_plus(self):
        with self.sync(platform_status="inferred") as case, \
                patch("core.accounts.plans.service.run_account_plan_check_inline") as plan:
            service._handle_provider_operation(case.context)
        case.context.defer.assert_not_called()
        plan.assert_not_called()
        result = case.context.finish.call_args.kwargs["result_summary"]
        self.assertEqual("succeeded", result["payment_status"])
        self.assertNotEqual("confirmed", result["plus_status"])

    def test_paid_order_continues_platform_check_after_local_plan_failure(self):
        with self.sync(platform_status="unknown", check_status="pending") as case, \
                patch("core.accounts.plans.service.run_account_plan_check_inline") as plan:
            service._handle_provider_operation(case.context)
        case.context.defer.assert_called_once()
        case.context.finish.assert_not_called()
        plan.assert_not_called()
        self.assertEqual("succeeded", case.save_job.call_args.args[3]["payment_state"])

    def test_platform_check_wait_is_bounded_and_preserves_paid(self):
        with self.sync(platform_status="unknown", check_status="pending") as case, \
                patch.object(service, "_legacy_reconcile_halt_reason", return_value="timeout"):
            service._handle_provider_operation(case.context)
        case.context.defer.assert_not_called()
        result = case.context.finish.call_args.kwargs["result_summary"]
        self.assertEqual("succeeded", result["payment_status"])
        self.assertTrue(result["local_reconcile_halted"])
        self.assertNotEqual("confirmed", result["plus_status"])

    def test_legacy_creation_checkpoints_credentials_without_receipt_flags(self):
        checkpoints = []
        def create(request):
            if request.submission_checkpoint:
                request.submission_checkpoint({"legacy_extract_cdk": "original-extract",
                    "legacy_payment_cdk": "original-payment"})
                checkpoints.append((dict(case.save_job.call_args.args[3]["summary"]), dict(case.save_job.call_args.args[4])))
            return ProviderJob(job_id="fixture-job", extraction_state="failed")
        with self._scenario() as case:
            case.context.run["data"].update(provider_id="legacy", mode="auto_payment", link_type="upi")
            case.provider.create_job.side_effect = create
            service._handle_provider_operation(case.context)
        case.provider.create_job.assert_called_once()
        self.assertEqual(1, len(checkpoints))
        self.assertEqual("original-payment", checkpoints[0][1]["legacy_payment_cdk"])
        self.assertIsNot(True, checkpoints[0][0].get("submission_receipt_pending"))


if __name__ == "__main__":
    unittest.main()
