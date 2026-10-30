"""虾扯蛋链原单持续同步与到账收口回归。"""
from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import Mock, patch

from core.extract_link import service as service
from core.extract_link.contracts import ProviderError, ProviderJob
from tests.extract_link import test_extract_link_provider_flow as fixtures


class LegacyContinuationTests(TestCase):
    _scenario = fixtures.ExtractLinkTerminalFailureFlowTests._scenario

    @contextmanager
    def scenario(self, job=None, *, error=None, initial=False, prior_state=None):
        prior = {"job_id": "fixture-job", "private_data": {"mode": "auto_payment", "link_type": "upi"},
                 "public_state": {"extraction_state": "running", "payment_state": "pending",
                                  "preflight_status": "passed", "summary": {}}}
        if prior_state is not None:
            prior["public_state"].update(prior_state)
        with self._scenario(failed_job=job, poll_error=error) as case:
            case.context.defer = Mock()
            case.context.run["data"].update({"provider_id": "legacy", "mode": "auto_payment", "link_type": "upi"})
            if not initial:
                case.context.run["data"].update({"extract_poll_continuation": True,
                    "workbench_action": "sync_status", "provider_job_run_id": 811})
            with patch.object(service, "_provider_job_for_sync", return_value=prior):
                yield case

    def test_initial_budget_expiry_defers_original_job(self):
        with self.scenario(ProviderJob(job_id="fixture-job", extraction_state="running", payment_state="pending"), initial=True) as case:
            service._handle_provider_operation(case.context)
        case.provider.create_job.assert_called_once()
        case.context.defer.assert_called_once()
        case.context.finish.assert_not_called()

    def test_paid_link_still_waits_for_automatic_payment_without_remote_polling_flag(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="succeeded", payment_state="pending")
        with self.scenario(job) as case:
            service._handle_provider_operation(case.context)
        case.provider.get_status.assert_called_once()
        case.provider.create_job.assert_not_called()
        case.provider.start_payment.assert_not_called()
        case.context.defer.assert_called_once()
        case.context.finish.assert_not_called()

    def test_transient_failure_keeps_original_job_and_schedules_retry(self):
        with self.scenario(error=TimeoutError("查询超时")) as case:
            service._handle_provider_operation(case.context)
        case.context.finish.assert_not_called()
        case.context.defer.assert_called_once()
        self.assertEqual("running", case.save_job.call_args.args[3]["extraction_state"])
        self.assertEqual("fixture-job", case.save_job.call_args.args[2])
        case.provider.create_job.assert_not_called()

    def test_manual_sync_query_failure_preserves_pending_snapshot_and_continues(self):
        for extraction, payment in (("running", "pending"), ("succeeded", "succeeded")):
            with self.subTest(extraction=extraction, payment=payment), self.scenario(
                error=ProviderError("Provider TLS 连接失败（异常类型：SSLError）"),
                prior_state={"extraction_state": extraction, "payment_state": payment},
            ) as case:
                case.context.run["data"].pop("extract_poll_continuation")
                service._handle_provider_operation(case.context)
                case.context.finish.assert_not_called()
                case.context.defer.assert_called_once()
                self.assertTrue(case.context.defer.call_args.kwargs["data"]["extract_poll_continuation"])
                self.assertEqual(extraction, case.save_job.call_args.args[3]["extraction_state"])
                self.assertEqual(payment, case.save_job.call_args.args[3]["payment_state"])
                case.provider.create_job.assert_not_called()
                case.provider.start_payment.assert_not_called()

    def test_manual_sync_query_failure_does_not_resume_known_failed_order(self):
        with self.scenario(error=ProviderError("Provider TLS 连接失败（异常类型：SSLError）"),
                prior_state={"extraction_state": "failed", "payment_state": "not_started",
                    "summary": {"remote_terminal_failure": True}}) as case:
            case.context.run["data"].pop("extract_poll_continuation")
            service._handle_provider_operation(case.context)
        case.context.defer.assert_not_called()
        self.assertEqual("failed", case.context.finish.call_args.kwargs["status"])
        self.assertTrue(case.save_job.call_args.args[3]["summary"]["remote_terminal_failure"])

    def test_terminal_failure_finishes_without_defer(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="failed", payment_state="failed",
                          summary={"remote_terminal_failure": True})
        with self.scenario(job) as case:
            service._handle_provider_operation(case.context)
        case.context.defer.assert_not_called()
        self.assertEqual("failed", case.context.finish.call_args.kwargs["status"])

    def test_explicit_payment_failure_settles_stale_running_extraction(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="running", payment_state="failed",
                          summary={"automatic_payment_terminal": True, "failure_message": "订单已过期退款"})
        with self.scenario(job) as case:
            service._handle_provider_operation(case.context)
        case.context.defer.assert_not_called()
        self.assertEqual("failed", case.context.finish.call_args.kwargs["status"])
        self.assertEqual("订单已过期退款", case.context.finish.call_args.kwargs["message"])

    def test_confirmed_payment_and_saved_plus_finish_without_another_plan_check(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="running", payment_state="succeeded",
                          summary={"automatic_payment_status": "COMPLETED", "automatic_payment_terminal": True})
        with self.scenario(job) as case, \
                patch("core.storage.operations.store.get_task", return_value={"created_at": "2026-10-29T01:00:00+00:00"}), \
                patch.object(service.db, "get_account", return_value={"id": 77, "email": "fixture@example.test",
                    "plan_check_status": "success", "current_plan_type": "plus", "plan_checked_at": "2026-10-29T02:00:00+00:00"}), \
                patch.object(service, "_payment_aftercare") as aftercare, \
                patch("core.accounts.plans.service.run_account_plan_check_inline") as plan:
            service._handle_provider_operation(case.context)
        case.context.defer.assert_not_called()
        result = case.context.finish.call_args.kwargs["result_summary"]
        self.assertEqual("success", case.context.finish.call_args.kwargs["status"])
        self.assertEqual("succeeded", result["extraction_status"])
        self.assertEqual("confirmed", result["plus_status"])
        self.assertEqual("succeeded", result["payment_status"])
        self.assertEqual("local_plan_check", result["payment_confirmation_source"])
        aftercare.assert_not_called()
        plan.assert_not_called()

    def test_recovered_paid_original_without_saved_plus_runs_independent_verification(self):
        account = {"id": 77, "email": "fixture@example.test", "access_token": "fixture-at",
                   "plan_check_status": "success", "current_plan_type": "free"}

        def verify(**_kwargs):
            account.update(current_plan_type="plus", plan_checked_at="2026-10-29T02:00:00+00:00")
            return {"accepted": True, "result": {"ok": True}}

        job = ProviderJob(job_id="fixture-job", extraction_state="succeeded", payment_state="succeeded",
                          summary={"automatic_payment_status": "COMPLETED", "automatic_payment_terminal": True})
        with self.scenario(job, prior_state={"extraction_state": "succeeded", "payment_state": "succeeded",
                "plus_status": "pending", "summary": {"local_plan_check_pending": True}}) as case, \
                patch("core.storage.operations.store.get_task", return_value={"created_at": "2026-10-29T01:00:00+00:00"}), \
                patch.object(service.db, "get_account", return_value=account), \
                patch.object(service, "_bool_setting", return_value=True), \
                patch.object(service, "_payment_aftercare", return_value=("skipped", "fixture-at", False)), \
                patch("core.accounts.plans.service.run_account_plan_check_inline", side_effect=verify) as plan:
            service._handle_provider_operation(case.context)
        plan.assert_called_once()
        case.provider.get_status.assert_called_once()
        case.provider.create_job.assert_not_called()
        case.provider.start_payment.assert_not_called()
        self.assertEqual("confirmed", case.context.finish.call_args.kwargs["result_summary"]["plus_status"])
        self.assertEqual("success", case.context.finish.call_args.kwargs["status"])

    def test_unknown_payment_is_not_confirmed_by_account_plus_alone(self):
        state = {"extraction_state": "succeeded", "payment_state": "pending", "summary": {}}
        context = Mock(task_id=810, account_id=77)
        with patch.object(service.db, "get_account") as account:
            self.assertFalse(service._reconcile_huanguang_automatic_payment(
                context, state, provider_id="legacy", mode="auto_payment", prior_state={}))
        account.assert_not_called()
