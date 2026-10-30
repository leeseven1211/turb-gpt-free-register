"""原窗口关联落库后，进程缓存丢失仍从同一 Attempt 找回连接。"""
from unittest.mock import patch

from core.storage import records as record_store
from core.registration import retained_browser
from core.storage import registration
from tests.support_pg import PostgresTestCase


class BrowserResumeFlowTests(PostgresTestCase):
    def test_failed_window_without_account_survives_empty_process_cache(self):
        registration.reset_ready()
        registration.init()
        address = "window-resume@example.test"
        root_id = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "window-resume-root", "email": address,
            "status": "running", "job_type": "registration",
        })
        attempt = registration.ensure_attempt_for_job(root_id)
        source_run = registration.start_run(
            attempt["id"], job_id=root_id, initial_status="running", execution_id="original-window",
        )
        registration.save_browser_resume_context(
            attempt["id"], email=address, run_id=source_run["id"], execution_id="original-window",
            job_id=root_id, profile_id="same-window", debugger_address="127.0.0.1:9222",
            driver_path="/tmp/test-driver", otp_after_ts=123.5,
        )
        registration.finish_run(source_run["id"], status="failed")
        record_store.patch_row(record_store.JOBS, root_id, {"status": "failed"})
        child_id = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "window-resume-child", "email": address,
            "status": "running", "job_type": "registration_resume",
            "parent_job_id": root_id, "root_job_id": root_id, "attempt_id": attempt["id"],
        })
        with retained_browser._LOCK:
            retained_browser._RETAINED.clear()
        facts = {"job_id": child_id, "attempt_id": attempt["id"]}
        self.assertIsNone(retained_browser.take_failed_browser(email=address, profile_id=None, facts=facts))
        with patch("core.registration.service.is_job_worker_active", return_value=False), patch(
            "core.browser.roxy.client.RoxyBrowserClient.request", side_effect=AssertionError("找回关联无需新开环境"),
        ):
            candidate = retained_browser.recover_attempt_failed_browser(email=address, profile_id=None, facts=facts)
        self.assertIsNotNone(candidate)
        self.assertIsNone(candidate.driver)
        self.assertEqual(candidate.opened.profile_id, "same-window")
        self.assertEqual(candidate.opened.debugger_address, "127.0.0.1:9222")
        self.assertEqual(candidate.opened.raw, {"data": {"http": "127.0.0.1:9222", "driver": "/tmp/test-driver"}})
        self.assertEqual(candidate.otp_after_ts, 123.5)
        self.assertEqual(candidate.attempt_id, attempt["id"])
        self.assertEqual(candidate.root_job_id, root_id)
        self.assertIsNone(registration.get_attempt(attempt["id"])["account_id"])
