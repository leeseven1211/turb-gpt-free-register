"""通过真实任务激活与隔离 PostgreSQL 验证调试上下文跟随当前 Run。"""
import gzip
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from core.registration import debug, service
from core.storage import registration
from core.storage.registration import jobs
from tests.support_pg import PostgresTestCase


class RegistrationDebugRunContextTests(PostgresTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        root_patch = patch.object(debug, "_ARTIFACT_ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.active_job_id = None
        self.addCleanup(self._deactivate)

    def _deactivate(self):
        if self.active_job_id is not None:
            service._deactivate_job(self.active_job_id)
            self.active_job_id = None

    def _activate_and_claim(self, *, debug_enabled=True):
        job = jobs.create_job("outlook", data={
            "registration_driver": "roxy", "debug_enabled": debug_enabled,
        })
        self.active_job_id = int(job["id"])
        self.assertIsNone(jobs.get_job(self.active_job_id).get("execution_id"))
        service._activate_job(self.active_job_id)
        self.assertTrue(jobs.claim_job_for_execution(self.active_job_id))
        return jobs.get_job(self.active_job_id)

    def _assert_real_run(self, context):
        self.assertIsNotNone(context)
        run = registration.get_run(context["run_id"])
        self.assertEqual(self.active_job_id, run["job_id"])
        self.assertEqual("running", run["status"])
        self.assertEqual(context["attempt_id"], run["attempt_id"])
        self.assertEqual(context["execution_id"], run["execution_id"])
        self.assertTrue(context["execution_id"])
        self.assertEqual({**context, "job_id": self.active_job_id}, service.registration_fact_context())

    def test_activation_then_real_run_binding_reaches_saved_network_and_summary(self):
        job = self._activate_and_claim()
        session = debug.current_session()
        self.assertIsNone(session.execution_id)
        context = service._ensure_registration_run_context(job)
        self._assert_real_run(context)
        session.record_network({
            "target_id": "test-target", "request_id": "after-run-binding", "stage": "email_otp",
            "method": "POST", "url": "https://auth.openai.com/api/accounts/email-otp/resend", "status": 200,
        })
        self._deactivate()
        with gzip.open(session.events_path, "rt", encoding="utf-8") as stream:
            events = [json.loads(line) for line in stream]
        request = next(event for event in events if event.get("request_id") == "after-run-binding")
        for key, value in context.items():
            self.assertEqual(value, request[key])
            self.assertEqual(value, session.summary()[key])
        saved = jobs.get_job(int(job["id"]))["debug_capture_summary"]
        self.assertEqual(context["run_id"], saved["run_id"])
        self.assertEqual(context["execution_id"], saved["execution_id"])

    def test_debug_off_failure_only_session_stays_lazy_with_real_context(self):
        with patch.object(debug._cfg, "REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED", True):
            job = self._activate_and_claim(debug_enabled=False)
        session = debug.current_session()
        self.assertEqual("failure_only", session.capture_mode)
        context = service._ensure_registration_run_context(job)
        self._assert_real_run(context)
        self.assertEqual(context["run_id"], session.run_id)
        self.assertEqual(context["execution_id"], session.execution_id)
        self.assertFalse(session.capture_started)
        self.assertFalse(session.artifact_dir.exists())

    def test_all_diagnostics_disabled_keeps_real_run_binding_without_session(self):
        with patch.object(debug._cfg, "REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED", False):
            job = self._activate_and_claim(debug_enabled=False)
        self.assertIsNone(debug.current_session())
        self._assert_real_run(service._ensure_registration_run_context(job))
        self.assertEqual([], list(self.root.iterdir()))

    def test_diagnostic_sync_failure_preserves_run_and_worker_context(self):
        job = self._activate_and_claim()
        with patch.object(debug, "update_current_context", side_effect=RuntimeError("测试诊断同步失败")) as sync:
            context = service._ensure_registration_run_context(job)
        self._assert_real_run(context)
        sync.assert_called_once_with(**context)
        self.assertEqual("running", jobs.get_job(self.active_job_id)["status"])

