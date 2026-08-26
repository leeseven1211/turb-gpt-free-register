from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core import registration_debug as debug


class _FakeResponse:
    status_code = 403
    url = "https://auth.openai.com/api/accounts/create?state=secret-state"
    headers = {"content-type": "application/json", "set-cookie": "session=private"}
    text = '{"error":"blocked","access_token":"very-secret-token"}'
    history = []


class RegistrationDebugTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.root_patch = patch.object(debug, "_ARTIFACT_ROOT", self.root)
        self.root_patch.start()
        self.db_patch = patch.object(debug.RegistrationDebugSession, "_patch_job")
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.root_patch.stop()
        self.tmp.cleanup()
        debug._CURRENT_SESSION.set(None)
        with debug._ACTIVE_LOCK:
            debug._ACTIVE.clear()

    @staticmethod
    def job(job_id: int, batch_id: str = "batch-1") -> dict:
        return {
            "id": job_id,
            "job_uuid": f"job-{job_id}",
            "batch_id": batch_id,
            "debug_enabled": True,
            "progress_stage": "browser",
        }

    def test_redacts_headers_query_and_json_secrets(self):
        url = debug.sanitize_url("https://example.com/callback?code=abc&email=user%40example.com")
        self.assertIn("code=%3Credacted", url)
        self.assertNotIn("abc", url)
        self.assertNotIn("user%40example.com", url)
        auth_url = debug.sanitize_url("https://private:password@example.com/callback")
        self.assertEqual(auth_url, "https://example.com/callback")

        headers = debug.sanitize_headers({"Authorization": "Bearer secret", "User-Agent": "UA"})
        self.assertIn("<redacted", headers["Authorization"])
        self.assertEqual(headers["User-Agent"], "UA")

        body, truncated = debug.sanitize_body(
            {"password": "pw", "nested": {"access_token": "token"}, "error": "blocked"},
            "application/json",
        )
        self.assertFalse(truncated)
        self.assertIn("<redacted", body["password"])
        self.assertIn("<redacted", body["nested"]["access_token"])
        self.assertEqual(body["error"], "blocked")

    def test_body_limit_is_applied_after_redacting_email(self):
        with patch.object(debug._cfg, "REGISTRATION_DEBUG_BODY_MAX_KB", 1):
            body, truncated = debug.sanitize_body(
                {"email": "person@example.com", "payload": "x" * 3000},
                "application/json",
            )
        self.assertTrue(truncated)
        self.assertNotIn("person@example.com", str(body))
        self.assertEqual(body["truncated"], True)

    def test_failure_hold_is_skipped_when_no_browser_or_cdp_exists(self):
        session = debug.RegistrationDebugSession(self.job(8))
        self.assertEqual(session.pause_failure(None, "driver startup failed"), "hold_skipped")
        self.assertEqual(session.debug_state, "hold_skipped")
        session.finalize("failed")

    @patch("core.record_store.patch_row", return_value=True)
    def test_patch_job_uses_atomic_jsonb_row_patch(self, patch_row):
        self.assertTrue(debug.patch_job(9, debug_enabled=True, debug_state="pending"))
        patch_row.assert_called_once()
        self.assertEqual(patch_row.call_args.args[0].name, "registration_jobs")
        self.assertEqual(patch_row.call_args.args[1], 9)
        self.assertEqual(patch_row.call_args.args[2]["debug_state"], "pending")

    def test_concurrent_sessions_write_isolated_files(self):
        first = debug.RegistrationDebugSession(self.job(1))
        second = debug.RegistrationDebugSession(self.job(2))
        first.record_network({"method": "GET", "url": "https://one.example/path", "status": 200})
        second.record_network({"method": "POST", "url": "https://two.example/path", "status": 500})
        first.finalize("success")
        second.finalize("failed")

        first_job = {**self.job(1), "debug_artifact_dir": str(first.artifact_dir)}
        second_job = {**self.job(2), "debug_artifact_dir": str(second.artifact_dir)}
        first_rows = debug.read_events(first_job)
        second_rows = debug.read_events(second_job)
        self.assertEqual([row["url"] for row in first_rows], ["https://one.example/path"])
        self.assertEqual([row["url"] for row in second_rows], ["https://two.example/path"])
        self.assertEqual(first.summary()["request_count"], 1)
        self.assertEqual(second.summary()["http_error_count"], 1)

    def test_protocol_exchange_is_sanitized_and_recorded(self):
        session = debug.RegistrationDebugSession(self.job(3))
        token = debug._CURRENT_SESSION.set(session)
        try:
            debug.record_protocol_exchange(
                method="POST",
                url="https://auth.openai.com/api/accounts/create?state=raw",
                started_at=time.perf_counter(),
                request_headers={"authorization": "Bearer raw-token", "content-type": "application/json"},
                request_body={"password": "raw-password", "name": "Tester"},
                response=_FakeResponse(),
            )
        finally:
            debug._CURRENT_SESSION.reset(token)
            session.finalize("failed")

        rows = debug.read_events({**self.job(3), "debug_artifact_dir": str(session.artifact_dir)})
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["status"], 403)
        self.assertNotIn("raw-password", str(row))
        self.assertNotIn("very-secret-token", str(row))
        self.assertNotIn("session=private", str(row))
        self.assertIn("blocked", str(row))

    def test_roxy_cdp_events_become_one_isolated_network_record(self):
        session = debug.RegistrationDebugSession(self.job(7))
        owner = type("Owner", (), {"session": session})()
        collector = debug._RoxyTargetCollector(owner, "page-1", "ws://unused", "page")
        collector._handle({
            "method": "Network.requestWillBeSent",
            "params": {
                "requestId": "request-1",
                "timestamp": 10.0,
                "type": "Fetch",
                "documentURL": "https://auth.openai.com/",
                "request": {
                    "method": "POST",
                    "url": "https://auth.openai.com/api/otp?code=123456",
                    "headers": {"authorization": "Bearer secret", "content-type": "application/json"},
                    "postData": '{"otp":"123456"}',
                },
            },
        })
        collector._handle({
            "method": "Network.responseReceived",
            "params": {
                "requestId": "request-1",
                "response": {
                    "status": 429,
                    "statusText": "Too Many Requests",
                    "mimeType": "application/json",
                    "headers": {"set-cookie": "session=private"},
                    "protocol": "h2",
                    "remoteIPAddress": "1.2.3.4",
                },
            },
        })
        collector._handle({
            "method": "Network.loadingFailed",
            "params": {"requestId": "request-1", "errorText": "net::ERR_FAILED"},
        })
        session.finalize("failed")

        rows = debug.read_events({**self.job(7), "debug_artifact_dir": str(session.artifact_dir)})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], 429)
        self.assertIn("ERR_FAILED", rows[0]["failure"])
        self.assertNotIn("123456", str(rows[0]))
        self.assertNotIn("session=private", str(rows[0]))

    def test_failure_hold_can_be_released(self):
        session = debug.RegistrationDebugSession(self.job(4))
        with debug._ACTIVE_LOCK:
            debug._ACTIVE[4] = session
        result_box = {}

        def run_pause():
            result_box["state"] = session.pause_failure(object(), "terminal failure")

        worker = threading.Thread(target=run_pause)
        worker.start()
        deadline = time.time() + 3
        while session.debug_state != "paused" and time.time() < deadline:
            time.sleep(0.02)
        self.assertEqual(session.debug_state, "paused")
        result = debug.release_job(4)
        self.assertTrue(result["ok"])
        worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result_box["state"], "released")
        session.finalize("failed")

    def test_compare_aligns_same_endpoint_and_reports_status_change(self):
        baseline = debug.RegistrationDebugSession(self.job(5))
        target = debug.RegistrationDebugSession(self.job(6))
        baseline.record_network({"stage": "email_otp", "method": "POST", "url": "https://auth.openai.com/api/otp", "status": 200})
        target.record_network({"stage": "email_otp", "method": "POST", "url": "https://auth.openai.com/api/otp", "status": 429})
        baseline.finalize("success")
        target.finalize("failed")
        baseline_job = {**self.job(5), "debug_artifact_dir": str(baseline.artifact_dir)}
        target_job = {**self.job(6), "debug_artifact_dir": str(target.artifact_dir)}
        comparison = debug.compare_jobs(target_job, baseline_job)
        self.assertEqual(comparison["difference_count"], 1)
        self.assertEqual(comparison["differences"][0]["baseline"]["status"], 200)
        self.assertEqual(comparison["differences"][0]["target"]["status"], 429)


if __name__ == "__main__":
    unittest.main()
