from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core import registration_debug as debug
from core.task_stages import EVENT_TYPES


class _FakeResponse:
    status_code = 403
    url = "https://auth.openai.com/api/accounts/create?state=secret-state"
    headers = {"content-type": "application/json", "set-cookie": "session=private"}
    text = '{"error":"blocked","access_token":"very-secret-token"}'
    history = []


class _FailureDriver:
    current_url = "https://chatgpt.com/auth/login"

    def save_screenshot(self, path):
        Path(path).write_bytes(b"png")

    def execute_script(self, _script):
        return {
            "url": self.current_url,
            "title": "開始する | ChatGPT",
            "readyState": "complete",
            "bodyText": "登录页面加载完成",
            "htmlLength": 1200,
            "dom": {
                "input_count": 0,
                "inputs": [],
                "action_count": 0,
                "actions": [],
            },
            "resources": [{
                "name": "https://auth.openai.com/assets/app.js?email=user@example.com",
                "initiatorType": "script",
                "duration": 41000,
                "transferSize": 0,
                "encodedBodySize": 0,
                "decodedBodySize": 0,
                "responseStatus": 0,
            }],
            "navigation": {"loadEventEnd": 0},
        }

    def get_log(self, _kind):
        return [{"level": "SEVERE", "message": "resource failed for user@example.com", "timestamp": 1}]


class _PasswordFailureDriver(_FailureDriver):
    def execute_script(self, _script):
        state = super().execute_script(_script)
        state["dom"] = {
            "input_count": 1,
            "inputs": [{
                "type": "password",
                "name": "new-password",
                "text": "NeverPersistThisPassword!",
                "value": "NeverPersistThisPassword!",
            }],
            "action_count": 1,
            "actions": [{"type": "submit", "text": "Continue"}],
        }
        return state


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

    def test_failure_only_session_is_lazy_and_captures_raw_page_snapshot(self):
        session = debug.RegistrationDebugSession(self.job(10), capture_mode="failure_only")
        self.assertFalse((self.root / "job-10").exists())
        session.update_stage("page")
        session.record_network({"method": "GET", "url": "https://chatgpt.com/app.js", "status": 200})
        session.record_network({
            "method": "GET",
            "url": "https://chatgpt.com/app.js",
            "status": 503,
            "failure": "upstream unavailable",
        })
        self.assertEqual(session.request_count, 1)
        session.pause_failure(_FailureDriver(), "找不到邮箱输入框")
        session.finalize("failed")

        artifact_dir = self.root / "job-10"
        self.assertTrue((artifact_dir / "last-page.png").exists())
        self.assertTrue((artifact_dir / "last-page.json").exists())
        self.assertTrue((artifact_dir / "manifest.json").exists())
        state = json.loads((artifact_dir / "last-page.json").read_text(encoding="utf-8"))
        self.assertEqual(state["failure_category"], "network_or_proxy")
        self.assertEqual(state["dom"]["input_count"], 0)
        self.assertIn("user@example.com", json.dumps(state, ensure_ascii=False))
        rows = debug.read_events({**self.job(10), "failure_diagnostics_artifact_dir": str(artifact_dir)}, errors_only=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], 503)

    def test_failure_only_success_does_not_create_artifact(self):
        session = debug.RegistrationDebugSession(self.job(11), capture_mode="failure_only")
        session.finalize("success")
        self.assertFalse((self.root / "job-11").exists())

    def test_page_snapshot_redacts_password_input_values(self):
        session = debug.RegistrationDebugSession(self.job(14), capture_mode="failure_only")
        session.pause_failure(_PasswordFailureDriver(), "密码提交结果待确认")
        session.finalize("failed")

        state = json.loads((self.root / "job-14" / "last-page.json").read_text(encoding="utf-8"))
        serialized = json.dumps(state, ensure_ascii=False)
        self.assertNotIn("NeverPersistThisPassword!", serialized)
        self.assertEqual(state["dom"]["inputs"][0]["text"], "<redacted:password>")
        self.assertNotIn("value", state["dom"]["inputs"][0])

    def test_activation_arms_failure_diagnostics_without_full_capture(self):
        job = self.job(13)
        job["debug_enabled"] = False
        token = debug.activate_for_job(job)
        try:
            session = debug.current_session()
            self.assertIsNotNone(session)
            self.assertEqual(session.capture_mode, "failure_only")
            self.assertFalse(session.capture_started)
            session.attach_roxy("127.0.0.1:9222")
            self.assertEqual(session._collectors, [])
        finally:
            debug.deactivate_for_job(token, status="success")
        self.assertFalse((self.root / "job-13").exists())

    def test_failure_only_protocol_capture_ignores_success(self):
        session = debug.RegistrationDebugSession(self.job(12), capture_mode="failure_only")
        token = debug._CURRENT_SESSION.set(session)
        try:
            successful = _FakeResponse()
            successful.status_code = 200
            debug.record_protocol_exchange(
                method="GET",
                url="https://auth.openai.com/session",
                started_at=time.perf_counter(),
                response=successful,
            )
            self.assertEqual(session.request_count, 0)
            failed = _FakeResponse()
            failed.status_code = 503
            debug.record_protocol_exchange(
                method="GET",
                url="https://auth.openai.com/session",
                started_at=time.perf_counter(),
                response=failed,
            )
            self.assertEqual(session.request_count, 1)
            session.pause_failure(None, "协议请求失败")
        finally:
            debug._CURRENT_SESSION.reset(token)
            session.finalize("failed")
        rows = debug.read_events({**self.job(12), "failure_diagnostics_artifact_dir": str(session.artifact_dir)}, errors_only=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], 503)

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

    def test_protocol_exchange_is_raw_and_recorded(self):
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
        self.assertIn("raw-password", str(row))
        self.assertIn("very-secret-token", str(row))
        self.assertIn("session=private", str(row))
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
        self.assertIn("123456", str(rows[0]))
        self.assertIn("session=private", str(rows[0]))

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

    def test_partial_success_finalization_captures_context_evidence_and_timings(self):
        job = self.job(14)
        job.update({
            "debug_enabled": False,
            "attempt_id": 41,
            "run_id": 42,
            "email_evidence": {
                "email": "person@example.com",
                "source": "gptmail",
                "otp_received": True,
                "account_created": True,
                "persisted": True,
                "release_result": "released",
            },
            "error": "2FA post-processing failed",
        })
        session = debug.RegistrationDebugSession(job, capture_mode="failure_only")
        session.update_stage("email_otp", wait_reason="email_wait")
        session.update_stage("twofa", state="failed", wait_reason="driver_command")
        session.finalize("partial_success")

        artifact_dir = self.root / "job-14"
        manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["attempt_id"], 41)
        self.assertEqual(manifest["run_id"], 42)
        self.assertEqual(manifest["trigger_stage"], "twofa")
        self.assertEqual(manifest["email_evidence"]["email"], "person@example.com")
        timings = manifest["summary"]["stage_timings"]
        self.assertTrue(any(item["stage"] == "email_otp" and item["wait_reason"] == "email_wait" for item in timings))
        self.assertTrue(any(item["stage"] == "twofa" and item["duration_ms"] >= 0 for item in timings))
        stage_event = next(item for item in debug.read_timeline({**job, "failure_diagnostics_artifact_dir": str(artifact_dir)}) if item.get("event_type") == "stage" and item.get("stage") == "twofa")
        self.assertEqual(stage_event["state_before"], "pending")
        self.assertEqual(stage_event["state_after"], "failed")
        self.assertIn(stage_event["wait_reason"], {"driver_command"})
        self.assertIn(stage_event["event_type"], EVENT_TYPES)
        timeline = debug.read_timeline({**job, "failure_diagnostics_artifact_dir": str(artifact_dir)})
        self.assertTrue(any(item.get("kind") == "failure_diagnostics" and item.get("status") == "partial_success" for item in timeline))

    def test_unknown_state_is_captured_and_no_network_error_is_explicit(self):
        job = self.job(15)
        job.update({"debug_enabled": False, "attempt_id": 51, "run_id": 52})
        session = debug.RegistrationDebugSession(job, capture_mode="failure_only")
        session.update_context(last_confirmed_state="UNKNOWN")
        session.update_stage("auth_redirect", wait_reason="page_transition")
        session.finalize("failed")
        summary = session.summary()
        self.assertFalse(summary["network_error_observed"])
        self.assertEqual(summary["last_confirmed_state"], "UNKNOWN")
        timeline = debug.read_timeline({**job, "failure_diagnostics_artifact_dir": str(session.artifact_dir)})
        event = next(item for item in timeline if item.get("kind") == "failure_diagnostics")
        self.assertEqual(event["last_confirmed_state"], "UNKNOWN")
        self.assertFalse(event["network_error_observed"])

    def test_b_attempt_run_and_execution_aliases_are_carried_by_events(self):
        job = self.job(16)
        job.update({
            "debug_enabled": False,
            "attempt_id": 61,
            "active_run_id": 62,
            "execution_id": "exec-62",
        })
        session = debug.RegistrationDebugSession(job, capture_mode="failure_only")
        session.update_stage("account_request_started", wait_reason="driver_command")
        session.pause_failure(None, "remote account request returned unknown")
        session.finalize("failed")
        timeline = debug.read_timeline({**job, "failure_diagnostics_artifact_dir": str(session.artifact_dir)})
        event = next(item for item in timeline if item.get("event_type") == "failure_diagnostics")
        self.assertEqual(event["attempt_id"], 61)
        self.assertEqual(event["run_id"], 62)
        self.assertEqual(event["execution_id"], "exec-62")


if __name__ == "__main__":
    unittest.main()
