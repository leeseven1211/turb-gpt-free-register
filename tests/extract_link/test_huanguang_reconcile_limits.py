from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from core.extract_link import service as service
from core.extract_link.contracts import ProviderHTTPError, ProviderJob
from tests.extract_link import test_extract_link_provider_flow as fixtures


class HuanguangReconcileLimitsTests(TestCase):
    _scenario = fixtures.ExtractLinkTerminalFailureFlowTests._scenario

    @contextmanager
    def scenario(self, *, error=None, job=None, age=0, metadata=None, halted=False, continuation=True, materials=False):
        created = datetime.now(timezone.utc) - timedelta(seconds=age)
        state = {"extraction_state": "succeeded" if materials else "running", "payment_state": "pending",
                 "preflight_status": "passed", "plus_status": "pending", "summary": {"remote_polling": True}}
        if materials:
            state["payment_artifact"] = {"qr_data": "upi://pay?pa=fixture", "payment_page_url": "https://checkout.example.test/retained"}
            state["summary"]["extraction_ever_succeeded"] = True
        if halted:
            state["summary"].update(local_reconcile_halted=True, local_reconcile_reason="timeout")
        private = {"job_secret": "fixture-secret"}
        if metadata:
            private["local_reconcile"] = metadata
        prior = {"job_id": "fixture-job", "created_at": created, "private_data": private, "public_state": state}
        job = job or ProviderJob(job_id="fixture-job", extraction_state="running", payment_state="pending",
                                 summary={"remote_polling": True})
        with self._scenario(failed_job=job, poll_error=error) as case:
            case.context.defer = Mock()
            case.context.run.update(created_at=created)
            case.context.run["data"].update(provider_id="huanguang", mode="auto_payment", link_type="upi",
                                            workbench_action="sync_status", provider_job_run_id=811,
                                            extract_poll_continuation=continuation)
            with patch.object(service, "_provider_job_for_sync", return_value=prior):
                yield case

    def test_third_consecutive_404_finishes_as_unknown_without_create_or_payment(self):
        now = datetime.now(timezone.utc).isoformat()
        with self.scenario(error=ProviderHTTPError(404), metadata={
            "started_at": now, "last_progress_at": now, "consecutive_failures": 2, "consecutive_not_found": 2,
        }) as case:
            service._handle_provider_operation(case.context)
        case.context.defer.assert_not_called()
        self.assertEqual("request_unknown", case.context.finish.call_args.kwargs["status"])
        saved = case.save_job.call_args.args[3]
        self.assertEqual("unknown", saved["extraction_state"])
        self.assertEqual("remote_not_found", saved["summary"]["local_reconcile_reason"])
        self.assertEqual("fixture-secret", case.save_job.call_args.args[4]["job_secret"])
        case.provider.create_job.assert_not_called()
        case.provider.start_payment.assert_not_called()

    def test_old_run_stops_after_reading_original_without_restarting_timer(self):
        with self.scenario(age=7200) as case:
            service._handle_provider_operation(case.context)
        case.provider.get_status.assert_called_once()
        case.context.defer.assert_not_called()
        self.assertEqual("timeout", case.save_job.call_args.args[3]["summary"]["local_reconcile_reason"])

    def test_existing_halted_manual_sync_reads_once_and_stays_halted_if_pending(self):
        with self.scenario(age=7200, halted=True, continuation=False) as case:
            service._handle_provider_operation(case.context)
        case.provider.get_status.assert_called_once()
        case.context.defer.assert_not_called()
        self.assertEqual("request_unknown", case.context.finish.call_args.kwargs["status"])

    def test_halted_continuation_cannot_resume_itself(self):
        with self.scenario(halted=True) as case:
            service._handle_provider_operation(case.context)
        case.provider.get_status.assert_not_called()
        case.context.defer.assert_not_called()

    def test_temporary_network_error_persists_failure_count_then_defers(self):
        with self.scenario(error=TimeoutError("fixture timeout")) as case:
            service._handle_provider_operation(case.context)
        case.context.finish.assert_not_called()
        case.context.defer.assert_called_once()
        self.assertEqual(1, case.save_job.call_args.args[4]["local_reconcile"]["consecutive_failures"])

    def test_stale_provider_snapshot_does_not_count_as_successful_query(self):
        now = datetime.now(timezone.utc).isoformat()
        job = ProviderJob(job_id="fixture-job", extraction_state="running", payment_state="pending",
                          private_data={"latest_query_failed": True, "latest_query_http_status": 404},
                          summary={"remote_polling": True})
        with self.scenario(job=job, metadata={
            "started_at": now, "last_progress_at": now, "consecutive_failures": 2, "consecutive_not_found": 2,
        }) as case:
            service._handle_provider_operation(case.context)
        case.context.defer.assert_not_called()
        self.assertEqual("remote_not_found", case.save_job.call_args.args[3]["summary"]["local_reconcile_reason"])

    def test_halted_projection_is_attention_without_erasing_payment_facts(self):
        item = service._workbench_task_item({
            "task_id": 810, "run_status": "attention_required",
            "task_data": {"provider_id": "huanguang", "mode": "auto_payment"},
            "public_state": {"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "confirmed",
                             "summary": {"local_reconcile_halted": True}},
        })
        self.assertFalse(service._workbench_status_matches(item, "processing"))
        self.assertFalse(service._workbench_status_matches(item, "running"))
        self.assertTrue(service._workbench_status_matches(item, "needs_attention"))
        self.assertEqual(("success", "paid", "confirmed"), (item["extraction_status"], item["payment_status"], item["plus_status"]))

    def test_initial_monitor_counts_404_without_counting_prior_cdk_queue_age(self):
        with self._scenario(poll_error=ProviderHTTPError(404)) as case:
            case.context.defer = Mock()
            case.context.run.update(created_at=datetime.now(timezone.utc) - timedelta(days=1))
            case.context.run["data"].update(provider_id="huanguang", mode="auto_payment", link_type="upi")
            service._provider_configuration("huanguang").event_timeout = 120
            with patch.object(service, "_prepare_huanguang_proxies", return_value=({}, [], [])):
                service._handle_provider_operation(case.context)
        self.assertEqual(3, case.provider.get_status.call_count)
        self.assertEqual("remote_not_found", case.save_job.call_args.args[3]["summary"]["local_reconcile_reason"])
        self.assertEqual("request_unknown", case.context.finish.call_args.kwargs["status"])
        case.context.defer.assert_not_called()

    def test_halt_preserves_material_and_successful_extraction_fact(self):
        with self.scenario(age=7200, error=ProviderHTTPError(404), materials=True) as case:
            service._handle_provider_operation(case.context)
        saved = case.save_job.call_args.args[3]
        self.assertEqual("succeeded", saved["extraction_state"])
        self.assertEqual("upi://pay?pa=fixture", saved["payment_artifact"]["qr_data"])
        self.assertEqual("unknown", saved["payment_state"])
        self.assertTrue(saved["summary"]["local_reconcile_halted"])

    def test_manually_synced_terminal_success_clears_old_halt_marker(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="succeeded", payment_state="succeeded",
                          links=("https://checkout.example.test/retained",),
                          summary={"remote_polling": False, "automatic_payment_terminal": True})
        with self.scenario(age=7200, halted=True, continuation=False, job=job) as case:
            service._handle_provider_operation(case.context)
        self.assertEqual("success", case.context.finish.call_args.kwargs["status"])
        self.assertIsNot(True, case.save_job.call_args.args[3]["summary"].get("local_reconcile_halted"))
        case.context.defer.assert_not_called()

    def test_explicit_retry_of_halted_order_can_create_new_run(self):
        task = {"id": 810, "task_type": "extract_link", "source_system": "native_operations",
                "status": "attention_required", "account_id": 77, "last_run_id": 811,
                "data": {"provider_id": "huanguang", "mode": "auto_payment", "link_type": "upi", "options": {"retry_count": 3}},
                "runs": [{"id": 811, "run_no": 1}]}
        prior = {"job_id": "fixture-job", "public_state": {
            "extraction_state": "unknown", "summary": {"local_reconcile_halted": True},
        }}
        with (
            patch("core.storage.operations.store.get_task", return_value=task),
            patch("core.storage.extract_link.jobs.get_provider_job_public", return_value=prior),
            patch("core.storage.operations.store.retry_runtime_task", return_value={"id": 812}) as retry,
            patch.object(service.db, "claim_account_extract", return_value=True),
            patch.object(service, "_bool_setting", return_value=True),
            patch.object(service, "_provider_enabled", return_value=True),
            patch.object(service, "_provider_mode_enabled", return_value=True),
            patch.object(service.account_task_store, "notify_dispatch"),
        ):
            result = service.perform_extract_workbench_action(810, "retry")
            data = dict(retry.call_args.kwargs["data"])
            sync = service.perform_extract_workbench_action(810, "sync_status")
            sync_data = retry.call_args.kwargs["data"]
        self.assertTrue(result["accepted"])
        self.assertEqual("create", data["workbench_action"])
        self.assertFalse(data["extract_poll_continuation"])
        self.assertIsNone(data["provider_job_run_id"])
        self.assertEqual({"retry_count": 3}, data["options"])
        self.assertTrue(sync["accepted"])
        self.assertEqual("sync_status", sync_data["workbench_action"])
        self.assertIs(False, sync_data["extract_poll_continuation"])
        self.assertEqual(811, sync_data["provider_job_run_id"])
