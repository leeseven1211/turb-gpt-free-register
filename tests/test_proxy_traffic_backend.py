# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import browser_traffic, postgres_store, proxy_lease_store, proxy_provider, record_store
from core import registration_service as registration_svc
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class _FakeResponse:
    text = "10.20.30.40:8080\n"

    def raise_for_status(self):
        return None


class _FakeSession:
    def get(self, *_args, **_kwargs):
        return _FakeResponse()


class ProxyTrafficBackendTests(PostgresTestCase):
    def setUp(self):
        proxy_provider._ACTIVE_ENDPOINTS.clear()
        proxy_provider._RECENT_ENDPOINTS.clear()
        proxy_provider._PENDING_ENDPOINTS.clear()

    def tearDown(self):
        proxy_provider._ACTIVE_ENDPOINTS.clear()
        proxy_provider._RECENT_ENDPOINTS.clear()
        proxy_provider._PENDING_ENDPOINTS.clear()

    def _seed_lease(
        self,
        *,
        lease_id="lease-page-1",
        state="leased",
        endpoint="10.20.30.40:8080",
        exit_ip="203.0.113.41",
    ):
        now = datetime.now()
        proxy_lease_store.reserve_pending(
            lease_id=lease_id,
            provider="1024proxy",
            endpoint=endpoint,
            proxy_url=f"http://private-user:private-password@{endpoint}",
            acquired_at=now.isoformat(timespec="seconds"),
            expires_at=(now + timedelta(minutes=30)).isoformat(timespec="seconds"),
            batch_id="batch-page-1",
            job_id=lease_id,
            account_id=41,
            purpose="registration",
            operation_task_id=501,
            operation_run_id=601,
            registration_job_id=701,
            route_attempt_no=2,
        )
        proxy_lease_store.activate(
            lease_id=lease_id,
            exit_ip=exit_ip,
            region="US",
            expires_at=(now + timedelta(minutes=30)).isoformat(timespec="seconds"),
        )
        if state != "leased":
            proxy_lease_store.release(lease_id=lease_id, recent_until=None, reason="test-history")

    def test_proxy_lease_migration_adds_nullable_correlation_columns_idempotently(self):
        record_store.init()
        record_store.init()

        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, is_nullable
                  FROM information_schema.columns
                 WHERE table_schema = %s
                   AND table_name = 'proxy_leases'
                   AND column_name = ANY(%s)
                """,
                (
                    self.schema,
                    [
                        "account_id",
                        "purpose",
                        "operation_task_id",
                        "operation_run_id",
                        "registration_job_id",
                        "route_attempt_no",
                    ],
                ),
            )
            columns = {row[0]: row[1] for row in cur.fetchall()}

        self.assertEqual(
            columns,
            {
                "account_id": "YES",
                "purpose": "YES",
                "operation_task_id": "YES",
                "operation_run_id": "YES",
                "registration_job_id": "YES",
                "route_attempt_no": "YES",
            },
        )

    def test_persistent_page_query_survives_process_memory_absence_and_masks_proxy_secrets(self):
        self._seed_lease()

        with patch.dict(proxy_provider._ACTIVE_ENDPOINTS, {}, clear=True):
            rows = proxy_lease_store.list_page(view="current")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["exit_ip"], "203.0.113.41")
        self.assertEqual(rows[0]["account_id"], 41)
        self.assertEqual(rows[0]["operation_task_id"], 501)
        self.assertEqual(rows[0]["registration_job_id"], 701)
        self.assertEqual(rows[0]["route_attempt_no"], 2)
        self.assertNotIn("proxy_url", rows[0])
        self.assertNotIn("username", rows[0])
        self.assertNotIn("password", rows[0])

        app = create_app(auth_code="proxy-page-auth")
        response = app.test_client().get(
            "/api/proxy-traffic/current",
            headers={"X-Auth-Code": "proxy-page-auth"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["items"][0]["exit_ip"], "203.0.113.41")
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("private-user", encoded)
        self.assertNotIn("private-password", encoded)
        self.assertNotIn("proxy_url", encoded)

    def test_proxy_traffic_api_is_authenticated_and_history_is_separate_from_current(self):
        self._seed_lease(lease_id="lease-history-1", state="released")
        app = create_app(auth_code="proxy-page-auth")
        client = app.test_client()

        unauthorized = client.get("/api/proxy-traffic/current")
        self.assertEqual(unauthorized.status_code, 401)

        current = client.get(
            "/api/proxy-traffic/current",
            headers={"X-Auth-Code": "proxy-page-auth"},
        )
        history = client.get(
            "/api/proxy-traffic/history",
            headers={"X-Auth-Code": "proxy-page-auth"},
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(current.get_json()["items"], [])
        self.assertEqual(len(history.get_json()["items"]), 1)
        self.assertEqual(history.get_json()["items"][0]["exit_ip"], "203.0.113.41")

    def test_proxy_traffic_aggregate_route_is_authenticated_and_returns_ui_arrays(self):
        self._seed_lease(lease_id="lease-aggregate-current")
        self._seed_lease(
            lease_id="lease-aggregate-history",
            state="released",
            endpoint="10.20.30.41:8080",
            exit_ip="203.0.113.42",
        )
        browser_traffic.persist_summary(
            summary_key="traffic-aggregate-1",
            summary=browser_traffic.summarize_cdp_events(
                [{"kind": "http_request", "request_bytes": 2, "response_bytes": 3}],
            ),
            proxy_lease_id="lease-aggregate-current",
        )

        app = create_app(auth_code="proxy-page-auth")
        client = app.test_client()
        self.assertEqual(client.get("/api/proxy-traffic").status_code, 401)

        response = client.get(
            "/api/proxy-traffic",
            headers={"X-Auth-Code": "proxy-page-auth"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsInstance(payload["current_leases"], list)
        self.assertIsInstance(payload["lease_history"], list)
        self.assertIsInstance(payload["browser_traffic"], list)
        self.assertEqual(payload["current_leases"][0]["exit_ip"], "203.0.113.41")
        self.assertEqual(payload["browser_traffic"][0]["total_bytes"], 5)
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("proxy_url", encoded)
        self.assertNotIn("private-user", encoded)
        self.assertNotIn("private-password", encoded)

    def test_lease_correlation_is_idempotent_and_only_adds_missing_values(self):
        self._seed_lease(lease_id="lease-correlate-1")

        self.assertTrue(
            proxy_lease_store.correlate(
                lease_id="lease-correlate-1",
                account_id=99,
                purpose="registration",
                operation_task_id=901,
                operation_run_id=902,
                registration_job_id=903,
                route_attempt_no=3,
            )
        )
        self.assertTrue(
            proxy_lease_store.correlate(
                lease_id="lease-correlate-1",
                account_id=100,
                purpose="email_change",
                operation_task_id=999,
                operation_run_id=998,
                registration_job_id=997,
                route_attempt_no=4,
            )
        )
        row = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", "lease-correlate-1")
        self.assertEqual(row["account_id"], 41)
        self.assertEqual(row["purpose"], "registration")
        self.assertEqual(row["operation_task_id"], 501)
        self.assertEqual(row["operation_run_id"], 601)
        self.assertEqual(row["registration_job_id"], 701)
        self.assertEqual(row["route_attempt_no"], 2)

    def test_roxy_cdp_summary_aggregates_bytes_without_raw_request_content(self):
        summary = browser_traffic.summarize_cdp_events(
            [
                {
                    "kind": "http_request",
                    "request_id": "http-1",
                    "request_bytes": 10,
                    "response_bytes": 20,
                    "status": 200,
                    "finished": True,
                    "url": "https://private.example.test/should-not-persist",
                    "request_headers": {"Authorization": "secret"},
                    "response_body": "private-body",
                },
                {
                    "kind": "http_request",
                    "request_id": "http-2",
                    "request_bytes": 4,
                    "response_bytes": 0,
                    "status": 502,
                    "failed": True,
                },
                {
                    "kind": "http_request",
                    "request_id": "http-3",
                    "request_bytes": 7,
                    "response_bytes": 0,
                    "unfinished": True,
                },
                {"kind": "websocket_frame", "direction": "outgoing", "bytes": 3},
                {"kind": "websocket_frame", "direction": "incoming", "bytes": 6},
            ],
            source="roxy_cdp",
            method="cdp",
            started_at="2026-09-16T00:00:00+00:00",
            ended_at="2026-09-16T00:00:03+00:00",
        )
        browser_traffic.persist_summary(
            summary_key="traffic-roxy-1",
            summary=summary,
            proxy_lease_id="lease-page-1",
            account_id=41,
            purpose="registration",
        )

        rows = browser_traffic.list_summaries()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["upload_bytes"], 24)
        self.assertEqual(row["download_bytes"], 26)
        self.assertEqual(row["total_bytes"], 50)
        self.assertEqual(row["request_count"], 3)
        self.assertEqual(row["failed_count"], 1)
        self.assertEqual(row["unfinished_count"], 1)
        self.assertNotIn("url", row)
        self.assertNotIn("request_headers", row)
        self.assertNotIn("response_body", row)

    def test_protocol_traffic_is_explicitly_unavailable(self):
        browser_traffic.record_unavailable(
            summary_key="traffic-protocol-1",
            source="email_change",
            method="protocol",
            reason="protocol_no_browser_observation",
            operation_task_id=801,
            operation_run_id=802,
        )

        rows = browser_traffic.list_summaries()
        self.assertEqual(rows[0]["availability"], "unavailable")
        self.assertEqual(rows[0]["source"], "email_change")
        self.assertEqual(rows[0]["method"], "protocol")
        self.assertEqual(rows[0]["total_bytes"], 0)
        self.assertEqual(rows[0]["unknown_count"], 1)
        self.assertEqual(rows[0]["operation_task_id"], 801)

    def test_roxy_capture_reduces_live_cdp_records_without_retaining_raw_content(self):
        opened = SimpleNamespace(
            profile_id="profile-traffic-1",
            debugger_address="127.0.0.1:9222",
            traffic_capture=None,
        )
        collector = Mock()
        with patch.object(browser_traffic, "_new_roxy_collector", return_value=collector), patch.object(
            browser_traffic, "persist_summary", return_value=1,
        ) as persist:
            capture = browser_traffic.start_roxy_capture(
                opened,
                account_id=41,
                purpose="live_check",
                operation_run_id=601,
            )
            capture.record_network({
                "url": "https://private.example.test/account",
                "request_headers": {"Authorization": "Bearer secret"},
                "request_body": {"password": "private-password"},
                "response_body": "private-response",
                "encoded_data_length": 29,
                "status": 200,
            })
            capture.record({
                "kind": "websocket_frame",
                "direction": "sent",
                "payload": "private-frame",
            })
            browser_traffic.finish_roxy_capture(opened)

        collector.start.assert_called_once_with()
        collector.stop.assert_called_once_with()
        saved = persist.call_args.kwargs
        self.assertEqual(saved["account_id"], 41)
        self.assertEqual(saved["purpose"], "live_check")
        self.assertEqual(saved["operation_run_id"], 601)
        self.assertEqual(saved["summary"]["request_count"], 1)
        self.assertEqual(saved["summary"]["download_bytes"], 29)
        self.assertGreater(saved["summary"]["upload_bytes"], 0)
        encoded = json.dumps(saved, ensure_ascii=False)
        self.assertNotIn("private.example.test", encoded)
        self.assertNotIn("private-password", encoded)
        self.assertNotIn("private-response", encoded)
        self.assertNotIn("private-frame", encoded)

    def test_roxy_capture_without_debugger_persists_explicit_unavailable_row(self):
        opened = SimpleNamespace(
            profile_id="profile-no-cdp",
            debugger_address=None,
            traffic_capture=None,
        )
        with patch.object(browser_traffic, "record_unavailable", return_value=1) as unavailable:
            browser_traffic.start_roxy_capture(opened, purpose="codex_oauth")
            browser_traffic.finish_roxy_capture(opened)

        self.assertEqual(unavailable.call_args.kwargs["purpose"], "codex_oauth")
        self.assertEqual(
            unavailable.call_args.kwargs["reason"],
            "roxy_debugger_address_unavailable",
        )

    def test_provider_persists_lease_correlation_without_changing_masked_public_shape(self):
        with patch("core.proxy_provider._direct_session", return_value=_FakeSession()), patch(
            "core.proxy_provider._validate_proxy", return_value=("203.0.113.42", "US")
        ), patch("core.proxy_lease_store.reserve_pending") as reserve, patch(
            "core.proxy_lease_store.activate"
        ):
            with patch.multiple(
                "config.proxy",
                PROXY_1024_PERSIST_LEASES=True,
                PROXY_1024_API_TIMEOUT=5.0,
                PROXY_1024_MAX_ATTEMPTS=1,
                PROXY_1024_VALIDATE_ATTEMPTS=1,
                PROXY_1024_RECENT_TTL=0,
                PROXY_1024_ACQUIRE_INTERVAL=0.0,
                PROXY_1024_ROTATE_SESSION_TIME=False,
            ):
                lease = proxy_provider.acquire_1024_proxy(
                    api_url="https://proxy.example.test/api?type=txt",
                    protocol="http",
                    region="US",
                    validate=True,
                    job_id="registration-701",
                    account_id=41,
                    purpose="registration",
                    operation_task_id=501,
                    operation_run_id=601,
                    registration_job_id=701,
                    route_attempt_no=2,
                )

        self.assertEqual(reserve.call_args.kwargs["account_id"], 41)
        self.assertEqual(reserve.call_args.kwargs["purpose"], "registration")
        self.assertEqual(reserve.call_args.kwargs["operation_task_id"], 501)
        self.assertEqual(reserve.call_args.kwargs["operation_run_id"], 601)
        self.assertEqual(reserve.call_args.kwargs["registration_job_id"], 701)
        self.assertEqual(reserve.call_args.kwargs["route_attempt_no"], 2)
        public = lease.public_dict()
        self.assertNotEqual(public["exit_ip"], "203.0.113.42")
        self.assertNotIn("private-password", json.dumps(public))

    def test_registration_acquisition_passes_durable_correlation(self):
        captured = {}

        def acquire_proxy(**kwargs):
            captured.update(kwargs)
            return "lease"

        result = registration_svc._acquire_registration_proxy_with_retries(
            acquire_proxy=acquire_proxy,
            job_id=701,
            batch_id=None,
            batch_size=1,
            batch_workers=1,
            progress_callback=None,
            log_logger=registration_svc.logger,
            account_id=41,
            operation_task_id=501,
            operation_run_id=601,
            registration_job_id=701,
            route_attempt_no=2,
        )

        self.assertEqual(result, "lease")
        self.assertEqual(captured["purpose"], "registration")
        self.assertEqual(captured["account_id"], 41)
        self.assertEqual(captured["operation_task_id"], 501)
        self.assertEqual(captured["operation_run_id"], 601)
        self.assertEqual(captured["registration_job_id"], 701)
        self.assertEqual(captured["route_attempt_no"], 2)


if __name__ == "__main__":
    unittest.main()
