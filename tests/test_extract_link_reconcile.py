"""幻光原单续查的服务行为回归。"""
from contextlib import contextmanager
import unittest
from unittest.mock import Mock, patch

from core import extract_link_service as service
from core.extract_link_providers.contracts import ProviderJob
from core.operations.task_gateway import OperationLeaseLost
from tests import test_extract_link_provider_flow as fixtures


class ExtractReconcileFlowTests(unittest.TestCase):
    _scenario = fixtures.ExtractLinkTerminalFailureFlowTests._scenario
    @contextmanager
    def continuation(self, job=None, *, poll_error=None, receipt=False):
        private = {"batch_receipt_secret": "fixture-receipt", "batch_receipt_pending": True} if receipt else {"job_secret": "fixture-secret"}
        prior = {"job_id": None if receipt else "fixture-job", "private_data": private,
                 "public_state": {"extraction_state": "unknown" if receipt else "running", "payment_state": "pending",
                                  "preflight_status": "passed", "summary": {"remote_polling": True, "submission_receipt_pending": receipt}}}
        with self._scenario(failed_job=job, poll_error=poll_error) as case:
            case.context.defer = Mock(return_value={"status": "deferred"})
            case.context.run["data"].update({"provider_id": "huanguang", "mode": "auto_payment", "link_type": "upi",
                "extract_poll_continuation": True, "workbench_action": "sync_status", "provider_job_run_id": 811})
            with patch.object(service, "_provider_job_for_sync", return_value=prior):
                yield case

    def test_continuation_queries_once_then_defers_same_run_without_create_or_finish(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="running", payment_state="pending", summary={"remote_polling": True})
        with self.continuation(job) as case:
            service._handle_provider_operation(case.context)
        case.provider.get_status.assert_called_once()
        case.provider.create_job.assert_not_called()
        case.provider.start_payment.assert_not_called()
        case.context.finish.assert_not_called()
        self.assertEqual(811, case.context.defer.call_args.kwargs["data"]["provider_job_run_id"])
        self.assertTrue(case.context.defer.call_args.kwargs["data"]["extract_poll_continuation"])
        self.assertGreater(case.context.defer.call_args.kwargs["delay_seconds"], 0)

    def test_transient_get_failure_preserves_last_state_and_defers(self):
        with self.continuation(poll_error=TimeoutError("fixture timeout")) as case:
            service._handle_provider_operation(case.context)
        case.context.finish.assert_not_called()
        case.context.defer.assert_called_once()
        self.assertEqual("running", case.save_job.call_args.args[3]["extraction_state"])
        self.assertEqual({"job_secret": "fixture-secret"}, case.save_job.call_args.args[4])
        case.provider.create_job.assert_not_called()

    def test_pending_receipt_with_empty_job_id_is_queried_and_retained(self):
        pending = ProviderJob(extraction_state="unknown", private_data={"batch_receipt_secret": "fixture-receipt", "batch_receipt_pending": True},
                              summary={"remote_polling": True, "submission_receipt_pending": True})
        with self.continuation(pending, receipt=True) as case:
            service._handle_provider_operation(case.context)
        case.provider.get_status.assert_called_once_with("", private_data=pending.private_data)
        case.context.defer.assert_called_once()
        case.context.finish.assert_not_called()
        case.provider.create_job.assert_not_called()

    def test_receipt_recovers_job_id_and_terminal_state_updates_account(self):
        job = ProviderJob(job_id="receipt-job", extraction_state="failed", payment_state="failed", summary={"remote_terminal_failure": True})
        with self.continuation(job, receipt=True) as case:
            service._handle_provider_operation(case.context)
        self.assertEqual("receipt-job", case.save_job.call_args.args[2])
        self.assertEqual("failed", case.context.finish.call_args.kwargs["status"])
        case.context.defer.assert_not_called()
        self.assertEqual("receipt-job", case.save_account.call_args.args[1]["job_id"])

    def test_expired_worker_is_not_converted_to_business_failure_or_deferred(self):
        with self.continuation(poll_error=OperationLeaseLost("fixture lease lost")) as case:
            with self.assertRaises(OperationLeaseLost):
                service._handle_provider_operation(case.context)
        case.context.finish.assert_not_called()
        case.context.defer.assert_not_called()
        self.assertEqual(1, case.save_job.call_count)
        self.assertEqual("running", case.save_job.call_args.args[3]["extraction_state"])

    def test_initial_monitor_timeout_saves_then_yields_to_dispatcher(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="running", summary={"remote_polling": True})
        with self._scenario(failed_job=job) as case:
            case.context.defer = Mock()
            case.context.run["data"].update({"provider_id": "huanguang", "mode": "auto_payment", "link_type": "upi"})
            with patch.object(service, "_prepare_huanguang_proxies", return_value=({}, [], [])):
                service._handle_provider_operation(case.context)
        case.provider.create_job.assert_called_once()
        self.assertGreater(case.provider.get_status.call_count, 1)
        case.context.defer.assert_called_once()
        case.context.finish.assert_not_called()

    def test_receipt_secret_is_saved_before_create_submission(self):
        def create(request):
            request.submission_checkpoint({"batch_receipt_secret": "fixture-receipt", "batch_receipt_pending": True})
            self.assertEqual("fixture-receipt", case.save_job.call_args.args[4]["batch_receipt_secret"])
            self.assertTrue(case.save_job.call_args.args[3]["summary"]["submission_receipt_pending"])
            return ProviderJob(job_id="fixture-job", extraction_state="failed")
        with self._scenario() as case:
            case.context.run["data"].update({"provider_id": "huanguang", "mode": "auto_payment", "link_type": "upi"})
            case.provider.create_job.side_effect = create
            with patch.object(service, "_prepare_huanguang_proxies", return_value=({}, [], [])):
                service._handle_provider_operation(case.context)
        self.assertEqual("failed", case.context.finish.call_args.kwargs["status"])
        case.provider.create_job.assert_called_once()

    def test_recovered_receipt_confirms_original_write_before_terminal_finish(self):
        job = ProviderJob(job_id="receipt-job", extraction_state="failed", payment_state="failed",
                          summary={"remote_terminal_failure": True})
        with self.continuation(job, receipt=True) as case:
            case.context.run["data"]["remote_intent"] = {"action": "extract_link_create", "request_id": "original-request"}
            service._handle_provider_operation(case.context)
        case.context.remote_request_receipt.assert_called_once()
        receipt = case.context.remote_request_receipt.call_args.kwargs
        self.assertEqual("confirmed", receipt["outcome"])
        self.assertEqual("original-request", receipt["request_id"])
        self.assertTrue(receipt["detail"]["local_readback_confirmed"])

    def test_rejected_receipt_settles_original_write_without_new_submission(self):
        job = ProviderJob(extraction_state="failed", summary={"outcome": "REJECTED", "remote_polling": False})
        with self.continuation(job, receipt=True) as case:
            case.context.run["data"]["remote_intent"] = {"action": "extract_link_create", "request_id": "original-request"}
            service._handle_provider_operation(case.context)
        self.assertEqual("rejected", case.context.remote_request_receipt.call_args.kwargs["outcome"])
        case.context.defer.assert_not_called()
        self.assertEqual("failed", case.context.finish.call_args.kwargs["status"])
        case.provider.create_job.assert_not_called()

    def test_terminal_continuation_releases_original_unified_pool_resources(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="failed", payment_state="failed",
                          summary={"remote_terminal_failure": True})
        with self.continuation(job) as case:
            case.context.release_resource = Mock()
            prior = service._provider_job_for_sync.return_value
            prior["private_data"]["huanguang_proxy_leases"] = [{"lease_id": "original-pool-lease", "provider": "static",
                "resource_id": 123, "pool_resource_id": "original-pool-resource", "pool_anchor_id": "original-anchor"}]
            with patch("core.proxy_provider.release_proxy") as release:
                service._handle_provider_operation(case.context)
        self.assertEqual("original-pool-lease", release.call_args.args[0].lease_id)
        self.assertEqual("original-pool-resource", release.call_args.args[0].metadata["pool_resource_id"])
        case.context.release_resource.assert_called_once_with(123, state="released")

    def test_crash_between_job_save_and_receipt_confirmation_can_repair_checkpoint(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="failed", summary={"remote_terminal_failure": True})
        with self.continuation(job) as case:
            case.context.run["data"]["remote_intent"] = {"action": "extract_link_create", "request_id": "original-request", "receipt_state": "response_received"}
            service._handle_provider_operation(case.context)
        self.assertEqual("confirmed", case.context.remote_request_receipt.call_args.kwargs["outcome"])
        case.provider.create_job.assert_not_called()
