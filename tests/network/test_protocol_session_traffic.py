"""协议会话画像、预算与聚合流量的离线契约。"""
from __future__ import annotations

import gzip
import json
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock, patch

from config.browser import build_browser_environment, resolve_chrome_identity
from core.browser import traffic as browser_traffic
from core.network import protocol_traffic
from core.operations import run_log as task_run_log
from core.auth.state_machine import StageBudget, StageTimeout
from core.auth.protocol.session import BrowserSession
from tests.support_pg import PostgresTestCase
from webui.app import create_app


def response(status=200, **fields):
    return SimpleNamespace(status_code=status, upload_size=0, download_size=4,
                           redirect_count=0, content=b"test", **fields)


class ProtocolSessionContractTests(unittest.TestCase):
    def setUp(self):
        # 离线会话契约不属于实际 worker；显式空范围避免测试顺序带入业务归属。
        log_scope = task_run_log.stage_context("test", inherit=False)
        log_scope.__enter__()
        self.addCleanup(log_scope.__exit__, None, None, None)
        traffic_scope = protocol_traffic.correlation_context(inherit=False)
        traffic_scope.__enter__()
        self.addCleanup(traffic_scope.__exit__, None, None, None)

    def _session(self):
        return BrowserSession(proxy="", detect_exit_geo=False)

    def test_high_entropy_headers_use_resolved_session_profile(self):
        with patch("config.browser.resolve_impersonate", return_value="chrome146"):
            identity = resolve_chrome_identity("chrome999")
        session = BrowserSession.__new__(BrowserSession)
        session.browser_profile = build_browser_environment(chrome_identity=identity)
        session.browser_profile.update(sec_ch_ua_platform_version='"17.1.0"',
                                       sec_ch_ua_arch='"x86"', sec_ch_ua_bitness='"32"',
                                       sec_ch_ua_model='"test-model"')
        with patch("core.auth.protocol.session.SEND_HIGH_ENTROPY_CLIENT_HINTS", True):
            headers = session._get_common_headers()
        self.assertIn("Chrome/146.0.0.0", headers["User-Agent"])
        self.assertIn('v="146"', headers["sec-ch-ua"])
        self.assertEqual(identity["sec_ch_ua_full_version_list"], headers["sec-ch-ua-full-version-list"])
        self.assertEqual('"17.1.0"', headers["sec-ch-ua-platform-version"])
        self.assertEqual('"x86"', headers["sec-ch-ua-arch"])
        self.assertEqual('"32"', headers["sec-ch-ua-bitness"])
        self.assertEqual('"test-model"', headers["sec-ch-ua-model"])

    def test_high_entropy_disabled_and_non_chromium_do_not_send_headers(self):
        session = BrowserSession.__new__(BrowserSession)
        session.browser_profile = build_browser_environment()
        with patch("core.auth.protocol.session.SEND_HIGH_ENTROPY_CLIENT_HINTS", False):
            self.assertNotIn("sec-ch-ua-full-version-list", session._get_common_headers())
        session.browser_profile["send_client_hints"] = False
        with patch("core.auth.protocol.session.SEND_HIGH_ENTROPY_CLIENT_HINTS", True):
            self.assertFalse(any(key.startswith("sec-ch-") for key in session._get_common_headers()))

    def test_bare_session_never_starts_database_accounting(self):
        with patch.object(browser_traffic, "persist_summary") as persist:
            session = self._session()
            self.assertIsNone(session.protocol_traffic)
            session.close()
        persist.assert_not_called()

    def test_request_budget_caps_actual_io_and_restores_scope(self):
        session = self._session()
        clock = [10.0]
        budget = StageBudget.start(8, clock=lambda: clock[0])
        with patch.object(session.session, "get", return_value=response()) as get, patch(
            "core.registration.debug.record_protocol_exchange"
        ):
            with session.request_budget(budget):
                clock[0] = 13
                session.get("http://localhost/test", timeout=12)
                self.assertEqual(5, get.call_args.kwargs["timeout"])
                with session.request_budget(budget.child(2)):
                    session.get("http://localhost/test", timeout=(4, 4))
                    self.assertEqual((2, 0), get.call_args.kwargs["timeout"])
                session.get("http://localhost/test", timeout=(1, 10))
                self.assertEqual((1, 4), get.call_args.kwargs["timeout"])
                session.get("http://localhost/test", timeout=0)
                self.assertEqual(5, get.call_args.kwargs["timeout"])
            session.get("http://localhost/test", timeout=12)
            self.assertEqual(12, get.call_args.kwargs["timeout"])
        session.close()

    def test_expired_and_cancelled_budget_stop_before_io(self):
        session = self._session()
        with patch.object(session.session, "get") as get:
            with session.request_budget(StageBudget.start(0)):
                with self.assertRaises(StageTimeout):
                    session.get("http://localhost/test")
            with session.request_budget(StageBudget.start(0.0005)):
                with self.assertRaises(StageTimeout):
                    session.get("http://localhost/test")
            with session.request_budget(StageBudget.start(10, cancel=lambda: True)):
                with self.assertRaises(Exception):
                    session.get("http://localhost/test")
        get.assert_not_called()
        session.close()

    def test_session_meters_success_http_failure_and_transport_failure(self):
        with protocol_traffic.correlation_context(operation_task_id=101, operation_run_id=201):
            session = self._session()
        with patch.object(browser_traffic, "persist_summary"), patch(
            "core.registration.debug.record_protocol_exchange"
        ), patch.object(session.session, "get", side_effect=[response(), response(500), TimeoutError("private")]):
            session.get("http://localhost/test")
            session.get("http://localhost/test")
            with self.assertRaises(TimeoutError):
                session.get("http://localhost/test")
            session.close()
        summary = session.protocol_traffic.snapshot()
        self.assertEqual(3, summary["request_count"])
        self.assertEqual(2, summary["failed_count"])
        self.assertEqual(1, summary["unfinished_count"])
        self.assertEqual(1, summary["status_families"]["2xx"])
        self.assertEqual(1, summary["status_families"]["5xx"])
        self.assertEqual(1, summary["status_families"]["unknown"])

    def test_meter_failure_does_not_change_business_response(self):
        session = self._session()
        session.protocol_traffic = Mock()
        session.protocol_traffic.record.side_effect = RuntimeError("private data")
        session.protocol_traffic.flush.side_effect = RuntimeError("private data")
        expected = response()
        with patch.object(session.session, "get", return_value=expected), patch(
            "core.registration.debug.record_protocol_exchange"
        ):
            self.assertIs(expected, session.get("http://localhost/test"))
            session.close()

    def test_statistics_throttle_and_final_flush_are_idempotent(self):
        clock = [100.0]
        capture = protocol_traffic.ProtocolTrafficCapture({"operation_task_id": 1}, clock=lambda: clock[0])
        with patch.object(browser_traffic, "persist_summary") as persist:
            capture.record(started_at=time.perf_counter(), response=response())
            capture.record(started_at=time.perf_counter(), response=response())
            self.assertEqual(1, persist.call_count)
            clock[0] = 105
            capture.record(started_at=time.perf_counter(), response=response())
            self.assertEqual(2, persist.call_count)
            capture.record(started_at=time.perf_counter(), response=response())
            capture.flush()
            capture.flush()
            self.assertEqual(3, persist.call_count)
            self.assertEqual(4, persist.call_args.kwargs["summary"]["request_count"])
            self.assertEqual(1, len({call.kwargs["summary_key"] for call in persist.call_args_list}))

    def test_persistence_failure_is_retried_on_close_without_losing_counts(self):
        capture = protocol_traffic.ProtocolTrafficCapture({"operation_task_id": 1})
        with patch.object(browser_traffic, "persist_summary", side_effect=[RuntimeError("private"), 1]) as persist:
            capture.record(started_at=time.perf_counter(), response=response())
            capture.record(started_at=time.perf_counter(), error=TimeoutError())
            capture.flush()
        self.assertEqual(2, persist.call_count)
        self.assertEqual(2, persist.call_args.kwargs["summary"]["request_count"])
        self.assertEqual(1, persist.call_args.kwargs["summary"]["failed_count"])

    def test_concurrent_task_contexts_do_not_share_capture_or_correlation(self):
        def worker(task_id):
            with task_run_log.stage_context("registration", task_id=task_id, run_id=task_id + 100), \
                    protocol_traffic.correlation_context(registration_job_id=task_id, proxy_lease_id=f"lease-{task_id}"):
                capture = protocol_traffic.ProtocolTrafficCapture.for_current_context()
                capture.record(started_at=time.perf_counter(), response=response())
                return capture.correlation, capture.summary_key
        with patch.object(browser_traffic, "persist_summary"), ThreadPoolExecutor(max_workers=2) as executor:
            values = list(executor.map(worker, (10, 20)))
        self.assertEqual([10, 20], [item[0]["operation_task_id"] for item in values])
        self.assertEqual([110, 120], [item[0]["operation_run_id"] for item in values])
        self.assertEqual(2, len({item[1] for item in values}))
        self.assertIsNone(protocol_traffic.ProtocolTrafficCapture.for_current_context())

    def test_missing_transport_counters_do_not_use_decoded_length_as_wire_bytes(self):
        capture = protocol_traffic.ProtocolTrafficCapture({"operation_task_id": 1})
        with patch.object(browser_traffic, "persist_summary"):
            capture.record(started_at=time.perf_counter(), response=SimpleNamespace(status_code=200, content=b"decoded"))
        summary = capture.snapshot()
        self.assertEqual(0, summary["download_bytes"])
        self.assertEqual(7, summary["decoded_response_bytes"])
        self.assertEqual(1, summary["byte_unknown_count"])

    def test_backend_measurement_property_error_preserves_failed_count(self):
        class BrokenResponse:
            @property
            def status_code(self):
                raise ValueError("private")
        capture = protocol_traffic.ProtocolTrafficCapture({"operation_task_id": 1})
        with patch.object(browser_traffic, "persist_summary"):
            for _ in range(2):
                capture.record(started_at=time.perf_counter(), response=BrokenResponse(), error=TimeoutError())
        self.assertEqual(2, capture.snapshot()["failed_count"])
        self.assertEqual(2, capture.snapshot()["unknown_count"])
        self.assertEqual(2, capture.snapshot()["status_families"]["unknown"])

    def test_native_cli_correlation_does_not_invent_operation_task_or_run(self):
        with task_run_log.stage_context("legacy", task_id=11, run_id=12), \
                protocol_traffic.correlation_context(operation_task_id=11, operation_run_id=12):
            with task_run_log.stage_context("registration", inherit=False), \
                    protocol_traffic.correlation_context(inherit=False, purpose="registration", registration_attempt_id=41, registration_run_id=42):
                capture = protocol_traffic.ProtocolTrafficCapture.for_current_context()
            restored = protocol_traffic.ProtocolTrafficCapture.for_current_context()
            self.assertEqual(11, restored.correlation["operation_task_id"])
            self.assertEqual(12, restored.correlation["operation_run_id"])
            self.assertEqual("legacy", task_run_log.current_context()["stage"])
        self.assertEqual(41, capture.correlation["registration_attempt_id"])
        self.assertEqual(42, capture.correlation["registration_run_id"])
        self.assertNotIn("operation_task_id", capture.correlation)
        self.assertNotIn("operation_run_id", capture.correlation)
        with patch.object(browser_traffic, "persist_summary") as persist:
            capture.record(started_at=time.perf_counter(), response=response())
        self.assertEqual(42, persist.call_args.kwargs["summary"]["registration_run_id"])
        self.assertNotIn("registration_run_id", {key for key in persist.call_args.kwargs if key != "summary"})


class ProtocolTrafficPersistenceTests(PostgresTestCase):
    def test_protocol_aggregate_is_visible_in_normal_api_with_private_fields_discarded(self):
        capture = protocol_traffic.ProtocolTrafficCapture({
            "operation_task_id": 501, "operation_run_id": 601, "registration_attempt_id": 701,
            "registration_run_id": 901,
            "registration_job_id": 801, "proxy_lease_id": "lease-protocol", "purpose": "registration",
            "url": "https://localhost/private?token=secret", "password": "secret",
        })
        capture.record(started_at=time.perf_counter(), response=response())
        capture.record(started_at=time.perf_counter(), error=TimeoutError("secret"))
        capture.flush()
        app = create_app(auth_code="test-protocol")
        client = app.test_client()
        payload = client.get("/api/proxy-traffic/traffic", headers={"X-Auth-Code": "test-protocol"}).get_json()
        self.assertEqual(1, payload["total"])
        row = payload["items"][0]
        self.assertEqual("protocol_http", row["source"])
        self.assertEqual(501, row["operation_task_id"])
        self.assertEqual(601, row["operation_run_id"])
        self.assertEqual(701, row["registration_attempt_id"])
        self.assertEqual(901, row["registration_run_id"])
        self.assertEqual(2, row["request_count"])
        self.assertEqual(1, row["failed_count"])
        self.assertEqual(4, row["total_bytes"])
        self.assertNotIn("secret", json.dumps(payload))
        metrics = client.get("/api/proxy-traffic/summary", headers={"X-Auth-Code": "test-protocol"}).get_json()
        self.assertEqual(4, metrics["total_bytes"])
        self.assertEqual(1, metrics["today_request_count"])
        self.assertEqual(1, metrics["today_protocol_count"])
        self.assertEqual(0, metrics["today_browser_count"])

    def test_persist_allowlist_rejects_unapproved_status_family_and_raw_metadata(self):
        browser_traffic.persist_summary(summary_key="protocol-allowlist", summary={
            "source": "protocol_http", "request_count": 1, "upload_bytes": 4,
            "status_families": {"2xx": 1, "secret": "private"},
            "headers": {"Cookie": "private"}, "body": "private", "url": "private",
            "byte_semantics": "private", "duration_ms": 12,
        })
        row = browser_traffic.list_summaries()[0]
        self.assertEqual(1, row["status_families"]["2xx"])
        self.assertEqual(12, row["duration_ms"])
        self.assertNotIn("private", json.dumps(row))


class ProtocolTrafficLocalHttpTests(unittest.TestCase):
    def test_real_local_compression_redirect_and_application_retry_contract(self):
        compressed = gzip.compress(b"local response " * 100)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/gzip")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Content-Length", str(len(compressed)))
                    self.end_headers()
                    self.wfile.write(compressed)

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(400)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        session = BrowserSession(proxy="", detect_exit_geo=False)
        session.bind_protocol_traffic(operation_task_id=1, operation_run_id=2)
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with patch.object(browser_traffic, "persist_summary"), patch("core.registration.debug.record_protocol_exchange"):
                first = session.get(base + "/redirect", allow_redirects=True)
                second = session.get(base + "/gzip")  # 业务重试各自计数。
                posted = session.post(base + "/post", data=b"local-body")
                session.close()
            summary = session.protocol_traffic.snapshot()
            self.assertEqual(3, summary["request_count"])
            self.assertEqual(1, summary["redirect_count"])
            self.assertEqual(1, summary["failed_count"])
            self.assertEqual(first.download_size + second.download_size + posted.download_size, summary["download_bytes"])
            self.assertEqual(posted.upload_size, summary["upload_bytes"])
            self.assertEqual(len(first.content) + len(second.content) + len(posted.content), summary["decoded_response_bytes"])
            self.assertLess(summary["download_bytes"], summary["decoded_response_bytes"])
            self.assertEqual(0, summary["byte_unknown_count"])
        finally:
            session.session.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
