from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import account_task_store, record_store
from core.storage import operation
from tests.support_pg import PostgresTestCase


class ExtractLinkProviderStorageTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._previous_operation_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        cls._account_schema_patch = patch.object(account_task_store, "_SCHEMA", cls.schema)
        cls._account_ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        cls._account_schema_patch.start()
        cls._account_ready_patch.start()
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        try:
            operation.reset_ready()
            if cls._previous_operation_schema is None:
                os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
            else:
                os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._previous_operation_schema
        finally:
            cls._account_ready_patch.stop()
            cls._account_schema_patch.stop()
            super().tearDownClass()

    def setUp(self):
        operation.init()

    def test_provider_private_data_is_not_in_normal_task_or_run_projections(self):
        from core.storage import extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=None,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "huanguang", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "huanguang",
            "remote-job-1",
            {
                "extraction_state": "running",
                "payment_state": "not_started",
                "job_secret": "test-private-job-secret",
            },
            {"job_secret": "test-private-job-secret"},
        )

        projected_task = operation.get_task(int(task["id"]))
        listed_tasks = operation.list_tasks(task_type="extract_link")["items"]
        self.assertNotIn("test-private-job-secret", repr(projected_task))
        self.assertNotIn("test-private-job-secret", repr(listed_tasks))
        self.assertNotIn("test-private-job-secret", repr(operation.get_run(run_id)))

        private_job = extract_link_jobs.get_provider_job_private(run_id)
        self.assertEqual("remote-job-1", private_job["job_id"])
        self.assertEqual("test-private-job-secret", private_job["private_data"]["job_secret"])
        self.assertNotIn("job_secret", private_job["public_state"])

    def test_provider_state_updates_do_not_replace_private_resume_data(self):
        from core.storage import extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=None,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "lumen_flow", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "lumen_flow",
            "remote-job-2",
            {"extraction_state": "running", "payment_state": "not_started"},
            {"resume_cursor": "private-cursor"},
        )

        extract_link_jobs.update_provider_job_state(
            run_id,
            {"extraction_state": "success", "payment_state": "not_started", "links": ["https://example.test/result"]},
        )

        saved = extract_link_jobs.get_provider_job_private(run_id)
        self.assertEqual("success", saved["extraction_state"])
        self.assertEqual(["https://example.test/result"], saved["public_state"]["links"])
        self.assertEqual("private-cursor", saved["private_data"]["resume_cursor"])

    def test_workbench_rows_join_current_run_and_return_only_public_state(self):
        from core.storage import extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=None,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "huanguang", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "huanguang",
            "remote-job-3",
            {
                "extraction_state": "succeeded",
                "payment_state": "not_started",
                "preflight_status": "passed",
                "links": ["https://example.test/result"],
            },
            {"job_secret": "private-resume-secret"},
        )

        rows = extract_link_jobs.list_workbench_rows(provider_id="huanguang", mode="extract_only")

        self.assertEqual(1, len(rows))
        self.assertEqual(int(task["id"]), rows[0]["task_id"])
        self.assertEqual(run_id, rows[0]["run_id"])
        self.assertEqual("remote-job-3", rows[0]["remote_job_id"])
        self.assertEqual("succeeded", rows[0]["extraction_state"])
        self.assertEqual(["https://example.test/result"], rows[0]["public_state"]["links"])
        self.assertNotIn("private-resume-secret", repr(rows))

    def test_unresolved_auto_payment_includes_unknown_payment_without_remote_job_id(self):
        from core.storage import extract_link_jobs

        payment_task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=77,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "lumen_flow", "mode": "auto_payment"},
        )
        extract_link_jobs.save_provider_job(
            int(payment_task["run"]["id"]),
            "lumen_flow",
            None,
            {"extraction_state": "unknown", "payment_state": "unknown"},
            {},
        )

        extraction_task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=78,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "lumen_flow", "mode": "extract_only"},
        )
        extract_link_jobs.save_provider_job(
            int(extraction_task["run"]["id"]),
            "lumen_flow",
            None,
            {"extraction_state": "unknown", "payment_state": "unknown"},
            {},
        )

        self.assertTrue(extract_link_jobs.has_unresolved_auto_payment(77))
        self.assertFalse(extract_link_jobs.has_unresolved_auto_payment(78))

    def test_recoverable_remote_jobs_only_include_interrupted_current_runs(self):
        from core.storage import extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=77,
            email="redacted@example.test",
            trigger="test",
            source_system="native_operations",
            data={"provider_id": "lumen_flow", "mode": "auto_payment"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "lumen_flow",
            "remote-job-4",
            {"extraction_state": "running", "payment_state": "pending"},
            {},
        )
        operation.finish_run(
            run_id,
            status="attention_required",
            message="worker restarted",
        )

        rows = extract_link_jobs.list_recoverable_workbench_jobs()

        self.assertEqual(1, len(rows))
        self.assertEqual(int(task["id"]), rows[0]["task_id"])
        self.assertEqual(run_id, rows[0]["run_id"])
        self.assertEqual("lumen_flow", rows[0]["provider_id"])
        self.assertEqual("auto_payment", rows[0]["mode"])

    def test_provider_terminal_failure_evidence_is_preserved_without_private_fields(self):
        from core.storage import extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link", account_id=None, email="redacted@example.test",
            trigger="test", data={"provider_id": "lumen_flow", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id, "lumen_flow", "failed-job",
            {
                "extraction_state": "failed", "payment_state": "not_started",
                "summary": {
                    "remote_status": "failed", "remote_terminal_failure": True,
                    "failure_message": "平台确认提链失败", "raw_response": "不应保存",
                },
            }, {},
        )
        public = extract_link_jobs.get_provider_job_public(run_id)["public_state"]
        self.assertEqual("FAILED", public["summary"]["remote_status"])
        self.assertIs(True, public["summary"]["remote_terminal_failure"])
        self.assertEqual("平台确认提链失败", public["summary"]["failure_message"])
        self.assertNotIn("raw_response", public["summary"])

        extract_link_jobs.update_provider_job_state(run_id, {
            "extraction_state": "failed", "payment_state": "not_started",
            "summary": {"remote_status": "未识别的原始响应", "remote_terminal_failure": "true"},
        })
        summary = extract_link_jobs.get_provider_job_public(run_id)["public_state"]["summary"]
        self.assertNotIn("remote_status", summary)
        self.assertNotIn("remote_terminal_failure", summary)

    def _finish_provider_failure(
        self, *, provider_state=None, finish_summary=None, receipt_detail=None,
        receipt_state="confirmed", action="extract_link_create", task_type="extract_link",
        save_job=True, job_provider="lumen_flow", job_id="failed-job",
    ):
        from core.storage import extract_link_jobs

        email = f"extract-{uuid.uuid4().hex}@example.test"
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": email, "access_token": "synthetic-token",
            "created_at": "2026-10-23T00:00:00", "updated_at": "2026-10-23T00:00:00",
        }])[0]
        task = operation.create_runtime_task(
            task_type=task_type, account_id=account_id, email=email, trigger="test",
            data={"provider_id": "lumen_flow", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        execution_id = f"failed-worker-{run_id}"
        operation.claim_run(run_id, execution_id=execution_id, worker_pid=os.getpid())
        lease_token = operation.acquire_account_lease(account_id=account_id, run_id=run_id)
        self.assertTrue(lease_token)
        fence = {"execution_id": execution_id, "lease_token": lease_token}
        operation.record_remote_intent(
            run_id, **fence, action=action, request_id=f"failed-request-{run_id}",
            detail={"provider_id": "lumen_flow", "mode": "extract_only", "run_id": run_id},
        )
        state = provider_state if provider_state is not None else {
            "extraction_state": "failed", "payment_state": "not_started",
            "summary": {"remote_status": "FAILED", "remote_terminal_failure": True},
        }
        if save_job:
            extract_link_jobs.save_provider_job(run_id, job_provider, job_id, state, {})
        if receipt_state != "started":
            detail = {
                "remote_result_confirmed": True, "local_business_writeback_confirmed": True,
                "local_readback_confirmed": True, "provider_id": "lumen_flow",
                "remote_job_id": "failed-job",
            }
            if receipt_detail is not None:
                detail.update(receipt_detail)
            operation.record_remote_receipt(
                run_id, **fence, outcome=receipt_state, action=action, detail=detail,
            )
        summary = {
            "provider_id": "lumen_flow", "mode": "extract_only",
            "extraction_status": "failed", "payment_status": "not_started",
            "remote_result_state": "failed", "remote_terminal_failure": True,
            "cause_code": "extract_provider_failed",
        }
        summary.update(finish_summary or {})
        return operation.finish_run(
            run_id, **fence, status="failed", message="平台提链失败", error="平台提链失败",
            result_summary=summary,
        )

    def test_confirmed_matching_provider_terminal_failure_can_finish_failed(self):
        for remote_status in ("FAILED", "ERROR", "CANCELED", "CANCELLED"):
            with self.subTest(remote_status=remote_status):
                finished = self._finish_provider_failure(provider_state={
                    "extraction_state": "failed", "payment_state": "not_started",
                    "summary": {"remote_status": remote_status, "remote_terminal_failure": True},
                })
                self.assertEqual("failed", finished["status"])
                self.assertFalse(finished["result_summary"].get("reconcile_required", False))
                self.assertNotEqual("request_unknown", finished["result_summary"].get("outcome"))
        finished = self._finish_provider_failure(
            provider_state={
                "extraction_state": "failed", "payment_state": "failed",
                "summary": {"remote_status": "FAILED", "remote_terminal_failure": True},
            },
            finish_summary={"payment_status": "failed"},
        )
        self.assertEqual("failed", finished["status"])
        self.assertFalse(finished["result_summary"].get("reconcile_required", False))

    def test_provider_failure_requires_matching_durable_terminal_evidence(self):
        cases = {
            "缺少远端任务": {"save_job": False},
            "缺少远端任务号": {"job_id": None},
            "不同远端任务": {"job_id": "another-job"},
            "不同平台": {"job_provider": "huanguang"},
            "回执平台不符": {"receipt_detail": {"provider_id": "huanguang"}},
            "历史回执缺少任务关联": {"receipt_detail": {"remote_job_id": None}},
            "调用方结果平台不符": {"finish_summary": {"provider_id": "huanguang"}},
            "调用方缺少明确失败标记": {"finish_summary": {"remote_terminal_failure": False}},
            "调用方已标待核实": {"finish_summary": {"reconcile_required": True}},
            "调用方仍标结果不明": {"finish_summary": {"outcome": "request_unknown"}},
            "调用方支付状态格式无效": {"finish_summary": {"payment_status": ["pending"]}},
            "不同远端动作": {"action": "extract_link_payment"},
            "其他任务类型": {"task_type": "synthetic_confirmed_failure"},
            "未取得回执": {"receipt_state": "started"},
            "仅观察响应": {"receipt_state": "response_received"},
            "远端结果不明": {"receipt_state": "unknown"},
            "仅调用方提供失败标记": {"provider_state": {
                "extraction_state": "failed", "payment_state": "not_started",
                "summary": {"remote_status": "FAILED"},
            }},
            "远端并未终止": {"provider_state": {
                "extraction_state": "failed", "payment_state": "not_started",
                "summary": {"remote_status": "RUNNING", "remote_terminal_failure": True},
            }},
        }
        for name, kwargs in cases.items():
            with self.subTest(name=name):
                finished = self._finish_provider_failure(**kwargs)
                self.assertEqual("attention_required", finished["status"])
                self.assertTrue(finished["result_summary"]["reconcile_required"])

    def test_provider_terminal_failure_does_not_hide_pending_or_unknown_payment(self):
        for payment_state in ("pending", "unknown", "succeeded"):
            for summary_payment in (payment_state, "not_started"):
                with self.subTest(payment_state=payment_state, summary_payment=summary_payment):
                    finished = self._finish_provider_failure(
                        provider_state={
                            "extraction_state": "failed", "payment_state": payment_state,
                            "summary": {"remote_status": "FAILED", "remote_terminal_failure": True},
                        },
                        finish_summary={"payment_status": summary_payment},
                    )
                    self.assertEqual("attention_required", finished["status"])
                    self.assertTrue(finished["result_summary"]["reconcile_required"])

    def test_real_operation_context_persists_polled_failure_with_extraction_diagnosis(self):
        from core import extract_link_service, task_run_log
        from core.extract_link_providers.contracts import ProviderJob
        from core.operations.task_gateway import OperationHandlerContext
        from core.storage import extract_link_jobs
        from core.task_progress import build_progress_snapshot

        email = "extract-flow@example.test"
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": email, "access_token": "synthetic-token",
            "created_at": "2026-10-23T00:00:00", "updated_at": "2026-10-23T00:00:00",
        }])[0]
        account = {"id": account_id, "email": email, "access_token": "synthetic-token"}
        reason = "当前账号不符合优惠条件"
        provider = SimpleNamespace(
            create_job=Mock(return_value=ProviderJob(
                job_id="flow-job", extraction_state="running", summary={"remote_status": "RUNNING"},
            )),
            get_status=Mock(return_value=ProviderJob(
                job_id="flow-job", extraction_state="failed",
                summary={"remote_status": "FAILED", "remote_terminal_failure": True, "failure_message": reason},
            )),
            start_payment=Mock(), get_automatic_payment_status=Mock(),
        )
        with (
            tempfile.TemporaryDirectory() as log_dir,
            patch.object(task_run_log, "_LOG_ROOT", Path(log_dir)),
            patch.object(task_run_log, "_TASK_LOG_ROOT", Path(log_dir) / "tasks"),
            patch.object(extract_link_service.db, "get_account", return_value=account),
            patch.object(extract_link_service.db, "account_is_deactivated", return_value=False),
            patch("core.plus_promotion.is_free_trial_record", return_value=True),
            patch.object(extract_link_service.db, "mark_account_extract_running", return_value=True),
            patch.object(extract_link_service, "_ensure_extract_token", return_value="synthetic-token"),
            patch.object(extract_link_service, "_provider_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_configuration", return_value=SimpleNamespace(
                default_type="momo", event_timeout=10, poll_interval=1,
            )),
            patch.object(extract_link_service, "_provider", return_value=provider),
            patch.object(extract_link_service.db, "update_account_extract") as save_account,
            patch.object(extract_link_service.time, "sleep"),
        ):
            task = operation.create_runtime_task(
                task_type="extract_link", account_id=account_id, email=email, trigger="test",
                data={"provider_id": "lumen_flow", "mode": "extract_only", "link_type": "momo"},
            )
            run_id = int(task["run"]["id"])
            claimed = operation.claim_run(run_id, execution_id="flow-worker", worker_pid=os.getpid())
            self.assertIsNotNone(claimed)
            context = OperationHandlerContext(claimed, execution_id="flow-worker")
            extract_link_service._handle_provider_operation(context)

        run = operation.get_run(run_id)
        task = operation.get_task(int(task["id"]))
        job = extract_link_jobs.get_provider_job_public(run_id)
        self.assertTrue(context.finished)
        self.assertEqual("failed", run["status"])
        self.assertEqual("failed", task["status"])
        self.assertEqual("extraction", run["result_summary"]["failure_stage"])
        self.assertEqual("extraction", task["failure_stage"])
        self.assertEqual("extract_provider_failed", run["error_code"])
        self.assertEqual("confirmed", run["data"]["remote_receipt"]["receipt_state"])
        self.assertEqual("flow-job", run["data"]["remote_receipt"]["detail"]["remote_job_id"])
        self.assertFalse(run["result_summary"].get("reconcile_required", False))
        self.assertEqual(reason, run["result_summary"]["failure_message"])
        self.assertEqual(reason, job["public_state"]["summary"]["failure_message"])
        self.assertEqual("not_started", job["payment_state"])
        self.assertIn(reason, save_account.call_args.args[1]["message"])
        provider.get_status.assert_called_once()
        provider.start_payment.assert_not_called()
        provider.get_automatic_payment_status.assert_not_called()
        snapshot = build_progress_snapshot(int(task["id"]), run_id, "extract_link", run, task["events"])
        self.assertEqual("extraction", snapshot["failure"]["stage"])
        self.assertEqual("explicit", snapshot["failure"]["evidence"])
        self.assertEqual("LINK-FAILED", snapshot["failure"]["error_info"]["display_code"])
