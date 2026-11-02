"""暗光原生一条龙编排与原单恢复；全部材料均为隔离测试夹具。"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager, nullcontext
from copy import deepcopy
import os
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from core.extract_link import service
from core.extract_link.contracts import ProviderJob
from core.extract_link.payment_confirmation import payment_scan_completed
from core.storage.extract_link import batches, jobs
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class AnguangConfigurationTests(TestCase):
    def setUp(self):
        self.values = {
            "EXTRACT_LINK_ENABLED": True, "EXTRACT_LINK_ANGUANG_ENABLED": True,
            "EXTRACT_LINK_AUTO_PAYMENT_ENABLED": True, "EXTRACT_LINK_ANGUANG_AUTO_PAYMENT_ENABLED": True,
            "EXTRACT_LINK_EXTRACT_ENABLED": False, "EXTRACT_LINK_ANGUANG_EXTRACT_ENABLED": False,
            "EXTRACT_LINK_ANGUANG_API_BASE": "https://ytc.example.test/openapi/v1",
            "EXTRACT_LINK_ANGUANG_API_KEY": "fixture-dedicated-key",
        }
        setting = patch.object(service, "_runtime_setting", side_effect=lambda key, default=None: self.values.get(key, default))
        setting.start()
        self.addCleanup(setting.stop)

    def test_native_auto_payment_does_not_require_extract_only_capability(self):
        self.assertTrue(service._provider_mode_enabled("anguang", "auto_payment"))
        self.assertFalse(service._provider_mode_enabled("anguang", "extract_only"))
        self.assertFalse(service._provider_mode_enabled("anguang", "manual_payment"))
        self.assertFalse(service._provider_mode_enabled("anguang", "auto_payment", "xxsyun"))
        runtime = service._provider_configuration("anguang")
        self.assertEqual("fixture-dedicated-key", runtime.config.cdk)
        self.assertTrue(runtime.config.capabilities["extract"])
        self.assertEqual("upi", runtime.default_type)
        self.assertEqual(10, runtime.poll_interval)
        self.assertNotIn("fixture-dedicated-key", repr(runtime.config))

    def test_public_platform_has_only_native_upi_automatic_payment(self):
        config = service.workbench_config()
        platform = next(item for item in config["providers"] if item["id"] == "anguang")
        self.assertEqual("暗光（XXSYUN 一条龙）", platform["label"])
        self.assertEqual(["auto_payment"], platform["modes"])
        self.assertEqual(["upi"], platform["link_types"])
        self.assertEqual("native", platform["payment_source"])
        self.assertEqual(["native"], platform["payment_sources"])
        self.assertNotIn("fixture-dedicated-key", repr(config))

    def test_creation_rejects_other_modes_sources_and_link_types(self):
        for mode, link_type, source in (("extract_only", "upi", "native"),
                ("manual_payment", "upi", "native"), ("auto_payment", "pix", "native"),
                ("auto_payment", "upi", "xxsyun")):
            with self.subTest(mode=mode, link_type=link_type, source=source), self.assertRaises(ValueError):
                service._workbench_creation_route("anguang", mode, link_type, {}, source)

    def test_request_options_freeze_validated_platform_defaults(self):
        self.values.update(EXTRACT_LINK_ANGUANG_PROCESSING_MODE="STRICT", EXTRACT_LINK_ANGUANG_PLAN_NAME="chatgptplusplan",
                           EXTRACT_LINK_ANGUANG_AUTO_RETRY=True)
        self.assertEqual({"processing_mode": "STRICT", "plan_name": "chatgptplusplan", "auto_retry": True},
            service._provider_request_options("anguang", {}, mode="auto_payment", link_type="upi"))
        for options in ({"processing_mode": "INVALID"}, {"plan_name": "invalid"}, {"auto_retry": "true"},
                        {"plan_name": "chatgptgoplan"}, {"plan_name": "chatgptprolite"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                service._provider_request_options("anguang", options, mode="auto_payment", link_type="upi")

    def test_never_provider_filter_accepts_anguang(self):
        self.assertEqual("anguang", batches.normalize_filters({"never_provider": "anguang"})["never_provider"])

    def test_original_query_survives_current_key_and_platform_disabled(self):
        self.values.update(EXTRACT_LINK_ENABLED=False, EXTRACT_LINK_ANGUANG_ENABLED=False,
                           EXTRACT_LINK_ANGUANG_API_KEY="", EXTRACT_LINK_ANGUANG_API_BASE="")
        runtime = service._provider_configuration("anguang", for_query=True)
        self.assertTrue(runtime.config.capabilities["extract"])
        self.assertEqual("", runtime.config.cdk)

    def test_registry_uses_dedicated_transport_and_provider(self):
        from core.extract_link.anguang.client import AnguangProvider, AnguangHTTPTransport

        provider = service._provider("anguang")
        self.assertIsInstance(provider, AnguangProvider)
        self.assertIsInstance(provider.transport, AnguangHTTPTransport)

    def test_poll_interval_uses_configured_range_of_ten_to_three_hundred_seconds(self):
        for value, expected in ((1, 10), (180, 180), (999, 300)):
            with self.subTest(value=value):
                self.values["EXTRACT_LINK_ANGUANG_POLL_INTERVAL"] = value
                self.assertEqual(expected, service._provider_configuration("anguang").poll_interval)


class AnguangFlowTests(TestCase):
    @staticmethod
    def private():
        return {"anguang_submission_pending": True, "anguang_request_encrypted": "fixture-encrypted-intent"}

    @contextmanager
    def scenario(self, job=None, *, prior=None, error=None, create=False):
        data = {"provider_id": "anguang", "mode": "auto_payment", "link_type": "upi"}
        if not create:
            data.update(workbench_action="sync_status", provider_job_run_id=810, extract_poll_continuation=True)
        context = SimpleNamespace(account_id=77, email="fixture@example.test", task_id=809, run_id=811,
            config_snapshot={}, run={"data": data, "created_at": "2026-11-01T00:00:00Z"}, finished=False,
            checkpoint=Mock(), report=Mock(), finish=Mock(), defer=Mock(),
            remote_request_started=Mock(), remote_request_receipt=Mock(), lease=lambda **kwargs: nullcontext())
        saved = []
        provider = SimpleNamespace(create_job=Mock(return_value=job), get_status=Mock(return_value=job, side_effect=error),
                                   start_payment=Mock())
        runtime = SimpleNamespace(default_type="upi", timeout=30, poll_interval=10, event_timeout=180,
            config=SimpleNamespace(api_base="https://changed.example.test", cdk="fixture-new-key"))
        def save(*args):
            saved.append(deepcopy(args))
        account = {"id": 77, "email": context.email, "access_token": "fixture-at", "current_plan_type": "free"}
        with ExitStack() as stack:
            for name, value in (("_provider_enabled", True), ("_provider_mode_enabled", True),
                    ("_provider_configuration", runtime), ("_provider", provider), ("_provider_job_for_sync", prior),
                    ("_ensure_extract_token", "fixture-at")):
                stack.enter_context(patch.object(service, name, return_value=value))
            stack.enter_context(patch.object(service, "_runtime_setting", side_effect=lambda key, default=None: default))
            stack.enter_context(patch.object(service, "_update_provider_job", side_effect=save))
            stack.enter_context(patch.object(service.db, "get_account", return_value=account))
            stack.enter_context(patch.object(service.db, "account_is_deactivated", return_value=False))
            stack.enter_context(patch.object(service.db, "mark_account_extract_running", return_value=True))
            stack.enter_context(patch.object(service.db, "update_account_extract"))
            stack.enter_context(patch("core.accounts.plans.promotion.is_extract_link_eligible", return_value=True))
            stack.enter_context(patch("core.storage.operations.store.get_task", return_value={"created_at": "2026-11-01T00:00:00Z"}))
            yield SimpleNamespace(context=context, provider=provider, saved=saved, account=account)

    def prior(self, *, job_id="fixture-job", extraction="running", payment="pending", **summary):
        return {"provider_id": "anguang", "job_id": job_id, "private_data": self.private(),
                "public_state": {"extraction_state": extraction, "payment_state": payment, "summary": summary,
                                 "preflight_status": "passed", "plus_status": "not_applicable"}}

    def test_create_checkpoints_full_intent_then_defers_without_second_payment_or_blocking(self):
        pending = ProviderJob(job_id="fixture-job", extraction_state="queued", payment_state="pending",
                              summary={"remote_polling": True})
        with self.scenario(pending, create=True) as case, patch.object(service.time, "sleep") as sleep:
            def submit(request):
                self.assertIsNotNone(request.submission_checkpoint)
                request.submission_checkpoint(self.private())
                self.assertEqual(self.private(), case.saved[-1][4])
                self.assertTrue(case.saved[-1][3]["summary"]["submission_receipt_pending"])
                return pending
            case.provider.create_job.side_effect = submit
            service._handle_provider_operation(case.context)
        case.context.defer.assert_called_once()
        self.assertEqual(10, case.context.defer.call_args.kwargs["delay_seconds"])
        case.provider.get_status.assert_not_called()
        case.provider.start_payment.assert_not_called()
        case.context.finish.assert_not_called()
        sleep.assert_not_called()

    def test_missing_receipt_recovers_same_intent_without_creating_new_job(self):
        pending = ProviderJob(extraction_state="unknown", payment_state="unknown", private_data=self.private(),
            summary={"submission_receipt_pending": True, "remote_polling": True})
        with self.scenario(pending, prior=self.prior(job_id=None, submission_receipt_pending=True)) as case:
            service._handle_provider_operation(case.context)
        case.provider.get_status.assert_called_once_with("", private_data=self.private())
        case.provider.create_job.assert_not_called()
        case.context.defer.assert_called_once()

    def test_current_run_restart_uses_durable_intent_instead_of_preflight_or_create(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="running", payment_state="pending")
        with self.scenario(job, prior=self.prior(job_id=None, submission_receipt_pending=True), create=True) as case:
            service._handle_provider_operation(case.context)
        case.provider.create_job.assert_not_called()
        case.provider.get_status.assert_called_once_with("", private_data=self.private())
        case.context.defer.assert_called_once()

    def test_known_job_only_queries_original_reference_and_transient_failure_defers(self):
        with self.scenario(prior=self.prior(), error=TimeoutError("fixture timeout")) as case:
            service._handle_provider_operation(case.context)
        case.provider.get_status.assert_called_once_with("fixture-job", private_data=self.private())
        case.provider.create_job.assert_not_called()
        case.provider.start_payment.assert_not_called()
        case.context.finish.assert_not_called()
        case.context.defer.assert_called_once()
        self.assertEqual("fixture-job", case.saved[-1][2])

    def test_submit_exception_keeps_checkpoint_and_schedules_same_identity_replay(self):
        with self.scenario(create=True) as case:
            def timeout(request):
                request.submission_checkpoint(self.private())
                raise TimeoutError("fixture timeout")
            case.provider.create_job.side_effect = timeout
            service._handle_provider_operation(case.context)
        case.context.finish.assert_not_called()
        case.context.defer.assert_called_once()
        self.assertEqual(self.private(), case.saved[-1][4])

    def test_explicit_scan_failure_keeps_previous_successful_checkout(self):
        prior = self.prior(extraction="succeeded")
        prior["public_state"]["links"] = ["https://checkout.example.test/original"]
        failed = ProviderJob(job_id="fixture-job", extraction_state="failed", payment_state="failed",
            summary={"remote_terminal_failure": True, "automatic_payment_terminal": True, "automatic_payment_status": "FAILED"})
        with self.scenario(failed, prior=prior) as case:
            service._handle_provider_operation(case.context)
        self.assertEqual("succeeded", case.saved[-1][3]["extraction_state"])
        self.assertEqual(["https://checkout.example.test/original"], case.saved[-1][3]["links"])
        self.assertEqual("failed", case.saved[-1][3]["payment_state"])
        case.context.defer.assert_not_called()

    def test_payment_success_runs_independent_plus_check_without_claiming_entitlement(self):
        paid = ProviderJob(job_id="fixture-job", extraction_state="succeeded", payment_state="succeeded",
            summary={"automatic_payment_terminal": True, "automatic_payment_status": "COMPLETED", "remote_polling": False})
        with self.scenario(paid, prior=self.prior()) as case, \
                patch.object(service, "_bool_setting", return_value=True), \
                patch.object(service, "_payment_aftercare", return_value=("skipped", "fixture-at", False)), \
                patch("core.accounts.plans.service.run_account_plan_check_inline", return_value={"accepted": True, "result": {"ok": True}}) as check:
            service._handle_provider_operation(case.context)
        check.assert_called_once()
        self.assertEqual("succeeded", case.saved[-1][3]["payment_state"])
        self.assertEqual("not_confirmed", case.saved[-1][3]["plus_status"])
        case.provider.start_payment.assert_not_called()

    def test_startup_and_periodic_recovery_preserve_original_job_reference(self):
        with patch.object(jobs, "reconcile_completed_payments", return_value={"confirmed": 0, "failed": 0}), \
                patch.object(jobs, "list_recoverable_workbench_jobs", return_value=[{"provider_id": "anguang", "mode": "auto_payment", "task_id": 9, "run_id": 11, "provider_job_run_id": 10}]), \
                patch.object(service, "_bool_setting", return_value=True), patch.object(service, "_provider_enabled", return_value=True), \
                patch("core.extract_link.independent_payment.resume_orders", return_value=0), \
                patch("core.storage.operations.store.retry_runtime_task", return_value={"id": 12}) as retry, \
                patch.object(service.account_task_store, "notify_dispatch"):
            self.assertEqual(1, service.resume_known_remote_jobs(continuous_only=True))
        self.assertEqual(10, retry.call_args.kwargs["data"]["provider_job_run_id"])
        self.assertTrue(retry.call_args.kwargs["data"]["extract_poll_continuation"])

    def test_retry_never_creates_another_remote_order_even_when_original_failed(self):
        task = {"task_type": "extract_link", "source_system": "native_operations", "status": "failed",
                "last_run_id": 10, "data": {"provider_id": "anguang", "mode": "auto_payment"}}
        with patch("core.storage.operations.store.get_task", return_value=task), \
                patch.object(jobs, "get_provider_job_public", return_value=self.prior(extraction="failed", payment="failed")), \
                patch.object(service, "_provider_enabled", return_value=True), patch.object(service, "_bool_setting", return_value=True), \
                patch("core.storage.operations.store.retry_runtime_task", return_value={"id": 11}) as retry, \
                patch.object(service.account_task_store, "notify_dispatch"):
            service.perform_extract_workbench_action(9, "retry")
        self.assertEqual("sync_status", retry.call_args.kwargs["data"]["workbench_action"])
        self.assertEqual(10, retry.call_args.kwargs["data"]["provider_job_run_id"])

    def test_payment_confirmation_accepts_scan_completion_without_inventing_plus(self):
        self.assertTrue(payment_scan_completed({"extraction_state": "succeeded", "payment_state": "succeeded"}, provider_id="anguang"))
        self.assertFalse(payment_scan_completed({"extraction_state": "succeeded", "payment_state": "pending"}, provider_id="anguang"))

    def test_platform_skipped_request_is_terminal_rejection_without_replay(self):
        skipped = ProviderJob(extraction_state="failed", payment_state="not_started",
            private_data={**self.private(), "anguang_submission_pending": False},
            summary={"outcome": "SKIPPED", "submission_receipt_pending": False, "automatic_payment_terminal": True})
        with self.scenario(skipped, create=True) as case:
            service._handle_provider_operation(case.context)
        self.assertEqual("failed", case.context.finish.call_args.kwargs["status"])
        self.assertEqual("rejected", case.context.finish.call_args.kwargs["result_summary"]["remote_result_state"])
        case.context.defer.assert_not_called()

    def test_saved_frozen_source_never_routes_anguang_into_independent_payment(self):
        with self.scenario(create=True) as case, patch("core.extract_link.independent_payment.handle") as handle:
            case.context.run["data"]["payment_source"] = "xxsyun"
            service._handle_provider_operation(case.context)
        handle.assert_not_called()
        case.provider.create_job.assert_not_called()

    def test_rate_limit_not_before_defers_original_identity_until_retry_allowed(self):
        private = {**self.private(), "anguang_retry_not_before": 1100}
        with self.scenario(create=True) as case, patch.object(service.time, "time", return_value=1000):
            service._defer_anguang_job(case.context, SimpleNamespace(poll_interval=10), {"summary": {}}, private, job_id="fixture-job")
        self.assertEqual(100, case.context.defer.call_args.kwargs["delay_seconds"])
        self.assertEqual(private, case.saved[-1][4])

    def test_longer_configured_interval_is_observed_when_continuing_original_order(self):
        job = ProviderJob(job_id="fixture-job", extraction_state="running", payment_state="pending")
        with self.scenario(job, prior=self.prior()) as case:
            service._provider_configuration.return_value.poll_interval = 180
            service._handle_provider_operation(case.context)
        self.assertEqual(180, case.context.defer.call_args.kwargs["delay_seconds"])


class AnguangStorageTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.previous_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        operation.reset_ready()
        if cls.previous_schema is None:
            os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
        else:
            os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.previous_schema
        super().tearDownClass()

    def setUp(self):
        operation.init()

    def store(self, *, job_id=None, extraction="unknown", payment="unknown", pending=True):
        task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="anguang@example.test",
            data={"provider_id": "anguang", "mode": "auto_payment"})
        run_id = task["run"]["id"]
        jobs.save_provider_job(run_id, "anguang", job_id, {
            "extraction_state": extraction, "payment_state": payment,
            "summary": {"submission_receipt_pending": pending, "remote_polling": pending},
        }, {"anguang_submission_pending": pending, "anguang_request_encrypted": "fixture-encrypted-intent"})
        operation.finish_run(run_id, status="attention_required", message="等待原单")
        return task, run_id

    def test_no_id_checkpoint_is_recoverable_and_private_intent_is_not_public(self):
        _, run_id = self.store()
        rows = jobs.list_recoverable_workbench_jobs()
        self.assertIn(run_id, {row["run_id"] for row in rows})
        self.assertNotIn("fixture-encrypted-intent", repr(rows))
        self.assertNotIn("fixture-encrypted-intent", repr(jobs.get_provider_job_public(run_id)))

    def test_terminal_scan_failure_is_not_automatically_recovered(self):
        _, run_id = self.store(job_id="fixture-failed", extraction="succeeded", payment="failed", pending=False)
        self.assertNotIn(run_id, {row["run_id"] for row in jobs.list_recoverable_workbench_jobs()})

    def test_running_scan_is_recovered_after_checkout_succeeded(self):
        _, run_id = self.store(job_id="fixture-job", extraction="succeeded", payment="pending", pending=False)
        self.assertIn(run_id, {row["run_id"] for row in jobs.list_recoverable_workbench_jobs()})

    def test_paid_initial_submission_worker_crash_recovers_original_before_plan_check_checkpoint(self):
        from core import account_task_store

        with patch.object(account_task_store, "_SCHEMA", self.schema), patch.object(account_task_store, "_READY_KEY", ""):
            account_task_store.init()
            task = operation.create_runtime_task(task_type="extract_link", account_id=None,
                email="paid-initial-crash@example.test", data={
                    "provider_id": "anguang", "mode": "auto_payment", "workbench_action": "create",
                    "remote_intent": {"kind": "remote_write", "action": "extract_link_create",
                                      "state": "confirmed", "receipt_state": "confirmed"},
                })
            run_id = task["run"]["id"]
            jobs.save_provider_job(run_id, "anguang", "paid-original", {
                "extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "not_applicable",
                "summary": {"automatic_payment_status": "COMPLETED", "automatic_payment_terminal": True,
                            "remote_polling": False, "submission_receipt_pending": False},
            }, {"anguang_submission_pending": False, "anguang_request_encrypted": "fixture-encrypted-intent"})
            operation.claim_run(run_id, execution_id="paid-initial-crash", worker_pid=92)
            with operation._connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {operation._table('operation_runs')} "
                            "SET heartbeat_at=now()-interval '1 hour' WHERE id=%s", (run_id,))

            self.assertEqual(1, operation.recover_interrupted_runtime_runs())
            recovered = operation.get_run(run_id)
            self.assertEqual("attention_required", recovered["status"])
            self.assertEqual("worker_interrupted", recovered["result_summary"]["cause_code"])
            self.assertIsNot(True, recovered["data"].get("extract_poll_continuation"))
            self.assertIsNot(True, jobs.get_provider_job_public(run_id)["public_state"]["summary"].get("local_plan_check_pending"))
            candidates = {row["task_id"]: row for row in jobs.list_recoverable_workbench_jobs()}
            self.assertIn(task["id"], candidates)
            self.assertEqual(run_id, candidates[task["id"]]["provider_job_run_id"])
            self.assertEqual("paid-original", jobs.get_provider_job_private(run_id)["job_id"])
