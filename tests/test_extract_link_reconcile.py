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
        self.assertEqual("fixture-secret", case.save_job.call_args.args[4]["job_secret"])
        self.assertEqual(1, case.save_job.call_args.args[4]["local_reconcile"]["consecutive_failures"])
        case.provider.create_job.assert_not_called()

    def test_pending_receipt_with_empty_job_id_is_queried_and_retained(self):
        pending = ProviderJob(extraction_state="unknown", private_data={"batch_receipt_secret": "fixture-receipt", "batch_receipt_pending": True},
                              summary={"remote_polling": True, "submission_receipt_pending": True})
        with self.continuation(pending, receipt=True) as case:
            service._handle_provider_operation(case.context)
        case.provider.get_status.assert_called_once()
        self.assertEqual(("",), case.provider.get_status.call_args.args)
        for key, value in pending.private_data.items():
            self.assertEqual(value, case.provider.get_status.call_args.kwargs["private_data"][key])
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

    def test_sync_supplies_previous_material_as_private_seed_for_legacy_job(self):
        with self.continuation(ProviderJob(job_id="fixture-job", extraction_state="failed")) as case:
            prior = service._provider_job_for_sync.return_value
            prior["public_state"].update({"extraction_state": "succeeded", "links": ["https://example.test/original"]})
            service._handle_provider_operation(case.context)
        private = case.provider.get_status.call_args.kwargs["private_data"]
        self.assertEqual(["https://example.test/original"], private["previous_public_state"]["links"])
        self.assertEqual("fixture-secret", private["job_secret"])

    def test_past_extraction_success_remains_visible_without_enabling_old_payment_entry(self):
        item = service._workbench_task_item({"task_id": 11, "task_data": {"provider_id": "huanguang", "mode": "auto_payment"},
            "run_status": "queued", "public_state": {"extraction_state": "queued", "payment_state": "pending",
                "summary": {"extraction_ever_succeeded": True}, "links": [], "payment_artifact": {}}})
        self.assertEqual("success", item["extraction_status"])
        self.assertFalse(item["has_payment_entry"])
        self.assertTrue(service._workbench_status_matches(item, "extraction_succeeded"))

    def test_completed_scan_with_only_old_plan_evidence_runs_independent_verification(self):
        from core.extract_link_providers.huanguang import HuanguangProvider
        scan = HuanguangProvider._job({"status": "DONE", "result": {
            "checkout_url": "https://example.test/result", "payment_status": "completed",
            "entitlement_active": True, "entitlement_inferred": True, "payment_check_status": "completed",
            "chongyun_status": "completed", "chongyun_order_status": "COMPLETED",
        }}, "fixture-job", "fixture-secret")
        with self.continuation(scan) as case:
            with (patch.object(service, "_bool_setting", return_value=True),
                  patch.object(service, "_payment_aftercare", return_value=("succeeded", "fresh-token", False)),
                  patch("core.storage.operation.get_task", return_value={"created_at": "2026-10-24T00:00:00Z"}),
                  patch("core.plan_check_service.run_account_plan_check_inline", create=True,
                        return_value={"accepted": True, "result": {"ok": True, "current_plan_type": "free"}}) as inline,
                  patch("core.plan_check_service.enqueue_account_plan_check") as enqueue):
                service._handle_provider_operation(case.context)
        inline.assert_called_once()
        enqueue.assert_not_called()
        self.assertEqual("not_confirmed", case.save_job.call_args.args[3]["plus_status"])
        self.assertEqual("unknown", case.save_job.call_args.args[3]["payment_state"])
        case.provider.start_payment.assert_not_called()
        case.provider.create_job.assert_not_called()

    def test_completed_xxsyun_and_fresh_independent_plus_can_confirm_same_order(self):
        from core.extract_link_providers.huanguang import HuanguangProvider
        scan = HuanguangProvider._job({"status": "DONE", "result": {
            "checkout_url": "https://example.test/result", "payment_status": "verification_unavailable",
            "xxsyun_status": "completed", "scan_fallback_status": "submitted", "entitlement_inferred": False,
        }}, "fixture-job", "fixture-secret")
        state = service._safe_provider_job_state(scan, mode="auto_payment", preflight_status="passed")
        with (patch("core.storage.operation.get_task", return_value={"created_at": "2026-10-24T00:00:00Z"}),
              patch.object(service.db, "get_account", return_value={"plan_check_status": "success", "current_plan_type": "plus", "plan_last_success_at": "2026-10-24T04:00:00Z"})):
            confirmed = service._reconcile_huanguang_automatic_payment(type("Context", (), {"task_id": 1, "account_id": 2})(), state,
                provider_id="huanguang", mode="auto_payment", prior_state={})
        self.assertTrue(confirmed)
        self.assertEqual("succeeded", state["payment_state"])
        self.assertEqual("confirmed", state["plus_status"])

    def test_xxsyun_confirmation_rejects_incomplete_scan_and_unverified_plan(self):
        from core.extract_link_providers.huanguang import HuanguangProvider
        for changes, account in [
            ({"xxsyun_status": "awaiting_worker"}, {"plan_check_status": "success", "current_plan_type": "plus"}),
            ({"xxsyun_status": "failed"}, {"plan_check_status": "success", "current_plan_type": "plus"}),
            ({"xxsyun_polling": True}, {"plan_check_status": "success", "current_plan_type": "plus"}),
            ({"payment_status": "pending"}, {"plan_check_status": "success", "current_plan_type": "plus"}),
            ({"payment_status": "awaiting_payment"}, {"plan_check_status": "success", "current_plan_type": "plus"}),
            ({"payment_status": "failed"}, {"plan_check_status": "success", "current_plan_type": "plus"}),
            ({}, {"plan_check_status": "failed", "current_plan_type": "plus"}),
            ({}, {"plan_check_status": "success", "current_plan_type": "free"}),
        ]:
            with self.subTest(changes=changes, account=account):
                scan = HuanguangProvider._job({"status": "DONE", "result": {
                    "checkout_url": "https://example.test/result", "payment_status": "completed",
                    "xxsyun_status": "completed", **changes,
                }}, "fixture-job", "fixture-secret")
                state = service._safe_provider_job_state(scan, mode="auto_payment", preflight_status="passed")
                with (patch("core.storage.operation.get_task", return_value={"created_at": "2026-10-24T00:00:00Z"}),
                      patch.object(service.db, "get_account", return_value={**account, "plan_last_success_at": "2026-10-24T04:00:00Z"})):
                    self.assertFalse(service._reconcile_huanguang_automatic_payment(
                        type("Context", (), {"task_id": 1, "account_id": 2})(), state,
                        provider_id="huanguang", mode="auto_payment", prior_state={}))
                self.assertNotEqual("succeeded", state["payment_state"])

    def test_scan_completion_respects_disabled_independent_plan_check(self):
        from core.extract_link_providers.huanguang import HuanguangProvider
        scan = HuanguangProvider._job({"status": "DONE", "result": {
            "checkout_url": "https://example.test/result", "payment_status": "completed", "xxsyun_status": "completed",
        }}, "fixture-job", "fixture-secret")
        with self.continuation(scan) as case:
            with (patch.object(service, "_bool_setting", return_value=False),
                  patch.object(service, "_payment_aftercare") as aftercare,
                  patch("core.storage.operation.get_task", return_value={"created_at": "2026-10-24T00:00:00Z"}),
                  patch("core.plan_check_service.enqueue_account_plan_check") as enqueue):
                service._handle_provider_operation(case.context)
        aftercare.assert_not_called()
        enqueue.assert_not_called()
        self.assertEqual("unknown", case.save_job.call_args.args[3]["payment_state"])

    @staticmethod
    def _inline_scan_job():
        from core.extract_link_providers.huanguang import HuanguangProvider
        return HuanguangProvider._job({"status": "DONE", "result": {
            "checkout_url": "https://example.test/result", "payment_status": "completed",
            "entitlement_active": True, "entitlement_inferred": True, "payment_check_status": "completed",
            "chongyun_status": "completed", "chongyun_order_status": "COMPLETED",
        }}, "fixture-job", "fixture-secret")

    def test_inline_plan_plus_finishes_original_run_after_pending_marker_is_saved(self):
        account = {"id": 77, "email": "fixture@example.test", "access_token": "fixture-token",
                   "plan_check_status": "success", "current_plan_type": "free",
                   "plan_checked_at": "2026-09-01T00:00:00Z"}
        with self.continuation(self._inline_scan_job()) as case:
            def inline(**kwargs):
                self.assertIs(case.context, kwargs["operation_context"])
                self.assertNotIn("config_snapshot", kwargs)
                self.assertIs(True, case.save_job.call_args.args[3]["summary"]["local_plan_check_pending"])
                case.context.finish.assert_not_called()
                account.update(current_plan_type="plus", plan_checked_at="2026-10-24T04:00:00Z")
                return {"accepted": True, "result": {"ok": True, "current_plan_type": "plus"}}
            with (patch.object(service, "_bool_setting", return_value=True),
                  patch.object(service.db, "get_account", side_effect=lambda *_args: account),
                  patch.object(service, "_payment_aftercare", return_value=("succeeded", "fixture-token", False)),
                  patch("core.storage.operation.get_task", return_value={"created_at": "2026-10-24T00:00:00Z"}),
                  patch("core.plan_check_service.run_account_plan_check_inline", create=True, side_effect=inline) as query,
                  patch("core.plan_check_service.enqueue_account_plan_check") as enqueue):
                service._handle_provider_operation(case.context)
        query.assert_called_once()
        enqueue.assert_not_called()
        case.context.defer.assert_not_called()
        case.context.finish.assert_called_once()
        result = case.context.finish.call_args.kwargs
        self.assertEqual("success", result["status"])
        self.assertEqual("succeeded", result["result_summary"]["payment_status"])
        self.assertEqual("confirmed", result["result_summary"]["plus_status"])
        self.assertIs(False, case.save_job.call_args.args[3]["summary"]["local_plan_check_pending"])
        case.provider.start_payment.assert_not_called()
        case.provider.create_job.assert_not_called()

    def test_inline_plan_failure_or_free_finishes_without_waiting_forever(self):
        for reply, expected_plus in (
            ({"accepted": True, "result": {"ok": False, "error": "HTTP 401"}}, "failed"),
            ({"accepted": False, "busy": True}, "failed"),
            ({"accepted": True, "result": {"ok": True, "current_plan_type": "free"}}, "not_confirmed"),
        ):
            with self.subTest(reply=reply), self.continuation(self._inline_scan_job()) as case:
                with (patch.object(service, "_bool_setting", return_value=True),
                      patch.object(service, "_payment_aftercare", return_value=("skipped", "", False)),
                      patch("core.storage.operation.get_task", return_value={"created_at": "2026-10-24T00:00:00Z"}),
                      patch("core.plan_check_service.run_account_plan_check_inline", create=True, return_value=reply) as inline,
                      patch("core.plan_check_service.enqueue_account_plan_check") as enqueue):
                    service._handle_provider_operation(case.context)
                inline.assert_called_once()
                enqueue.assert_not_called()
                case.context.finish.assert_called_once()
                case.context.defer.assert_not_called()
                self.assertEqual(expected_plus, case.save_job.call_args.args[3]["plus_status"])
                self.assertEqual("unknown", case.save_job.call_args.args[3]["payment_state"])
                self.assertIs(False, case.save_job.call_args.args[3]["summary"]["local_plan_check_pending"])

    def test_inline_plan_lease_loss_keeps_pending_marker_for_restart_recovery(self):
        with self.continuation(self._inline_scan_job()) as case:
            with (patch.object(service, "_bool_setting", return_value=True),
                  patch.object(service, "_payment_aftercare", return_value=("skipped", "", False)),
                  patch("core.storage.operation.get_task", return_value={"created_at": "2026-10-24T00:00:00Z"}),
                  patch("core.plan_check_service.run_account_plan_check_inline", create=True,
                        side_effect=OperationLeaseLost("测试租约失效"))):
                with self.assertRaises(OperationLeaseLost):
                    service._handle_provider_operation(case.context)
        case.context.finish.assert_not_called()
        self.assertIs(True, case.save_job.call_args.args[3]["summary"]["local_plan_check_pending"])

    def test_inline_plan_cancellation_cancels_original_run(self):
        with self.continuation(self._inline_scan_job()) as case:
            with (patch.object(service, "_bool_setting", return_value=True),
                  patch.object(service, "_payment_aftercare", return_value=("skipped", "", False)),
                  patch("core.storage.operation.get_task", return_value={"created_at": "2026-10-24T00:00:00Z"}),
                  patch("core.plan_check_service.run_account_plan_check_inline", create=True,
                        return_value={"accepted": True, "result": {"ok": False, "status": "cancelled"}})):
                service._handle_provider_operation(case.context)
        self.assertEqual("cancelled", case.context.finish.call_args.kwargs["status"])
        self.assertNotEqual("succeeded", case.save_job.call_args.args[3]["payment_state"])
