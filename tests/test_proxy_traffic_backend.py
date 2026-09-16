# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from core import postgres_store, proxy_lease_store, proxy_provider, record_store

try:
    from core import browser_traffic
except ImportError:  # RED 阶段：让缺少实现表现为可读的断言失败。
    browser_traffic = None
from tests.support_pg import PostgresTestCase


class BrowserTrafficModuleTests(unittest.TestCase):
    def test_browser_traffic_backend_module_exists(self):
        self.assertIsNotNone(browser_traffic, "core.browser_traffic 尚未实现")

    def test_cdp_summary_counts_bytes_without_persisting_request_contents(self):
        traffic = self._traffic()
        collector = traffic.RoxyCdpTrafficCollector(
            lease_id="lease-1",
            account_id=7,
            purpose="registration",
        )
        collector.observe_cdp_event(
            "Network.requestWillBeSent",
            {
                "requestId": "req-1",
                "request": {
                    "url": "https://chatgpt.com/private?token=secret",
                    "headers": {"Authorization": "Bearer secret"},
                    "postData": "password=secret",
                },
            },
        )
        collector.observe_cdp_event(
            "Network.responseReceived",
            {"requestId": "req-1", "response": {"status": 200}},
        )
        collector.observe_cdp_event(
            "Network.loadingFinished",
            {"requestId": "req-1", "encodedDataLength": 321},
        )

        summary = collector.finish()

        self.assertEqual(summary["download_bytes"], 321)
        self.assertEqual(summary["total_bytes"], 321)
        self.assertEqual(summary["request_count"], 1)
        self.assertEqual(summary["unknown_count"], 0)
        self.assertNotIn("url", summary)
        self.assertNotIn("headers", summary)
        self.assertNotIn("body", summary)
        self.assertNotIn("secret", str(summary))

    def _traffic(self):
        self.assertIsNotNone(browser_traffic, "core.browser_traffic 尚未实现")
        return browser_traffic


class ProxyTrafficBackendTests(PostgresTestCase):
    def setUp(self):
        record_store.reset_ready()
        record_store.init()

    def _reserve(self, lease_id: str = "lease-1", *, explicit_correlation: bool = True) -> None:
        now = datetime.now()
        values = {
            "lease_id": lease_id,
            "provider": "1024proxy",
            "endpoint": "1.2.3.4:8080",
            "proxy_url": "http://proxy-user:proxy-pass@1.2.3.4:8080",
            "acquired_at": now.isoformat(timespec="seconds"),
            "expires_at": (now + timedelta(minutes=30)).isoformat(timespec="seconds"),
            "job_id": 41,
        }
        if explicit_correlation:
            values.update(
                {
                    "account_id": 7,
                    "purpose": "registration",
                    "operation_task_id": 101,
                    "operation_run_id": 102,
                    "registration_job_id": 41,
                    "registration_attempt_id": 501,
                    "route_attempt_id": "41:1",
                    "route_attempt_no": 1,
                }
            )
        proxy_lease_store.reserve_pending(
            **values,
        )
        proxy_lease_store.activate(
            lease_id=lease_id,
            exit_ip="8.8.8.8",
            region="US",
            expires_at=(now + timedelta(minutes=30)).isoformat(timespec="seconds"),
        )

    def _traffic(self):
        self.assertIsNotNone(browser_traffic, "core.browser_traffic 尚未实现")
        return browser_traffic

    def test_proxy_lease_correlation_columns_are_additive_and_idempotent(self):
        record_store.reset_ready()
        record_store.init()
        record_store.reset_ready()
        record_store.init()

        with record_store._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = 'proxy_leases'",
                (self.schema,),
            )
            columns = {row["column_name"] for row in cur.fetchall()}

        self.assertTrue(
            {
                "account_id",
                "purpose",
                "operation_task_id",
                "operation_run_id",
                "registration_job_id",
                "registration_attempt_id",
                "route_attempt_id",
                "route_attempt_no",
            }.issubset(columns)
        )

    def test_persistent_query_does_not_depend_on_process_memory(self):
        self._reserve()
        proxy_provider._ACTIVE_ENDPOINTS.clear()

        rows = proxy_lease_store.query_leases(view="current")

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["account_id"], 7)
        self.assertEqual(row["purpose"], "registration")
        self.assertEqual(row["operation_task_id"], 101)
        self.assertEqual(row["operation_run_id"], 102)
        self.assertEqual(row["registration_job_id"], 41)
        self.assertEqual(row["registration_attempt_id"], 501)
        self.assertEqual(row["route_attempt_id"], "41:1")
        self.assertEqual(row["route_attempt_no"], 1)
        self.assertEqual(row["exit_ip"], "8.8.8.8")
        self.assertNotIn("proxy_url", row)
        self.assertNotIn("proxy-user", str(row))
        self.assertNotIn("proxy-pass", str(row))

    def test_query_enriches_legacy_job_with_operation_rows(self):
        from core.storage import operation

        operation.init()
        with record_store._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {postgres_store.qualified('operation_tasks')} (
                    task_uuid, source_system, source_id, task_type, target_type,
                    target_id, account_id, email_snapshot, requested_action, status, target_status
                ) VALUES (%s, 'registration_jobs', '41', 'registration', 'registration_attempt',
                          NULL, 7, 'masked@example.test', 'registration', 'queued', 'pending')
                RETURNING id
                """,
                ("task-proxy-traffic",),
            )
            task_id = int(cur.fetchone()["id"])
            cur.execute(
                f"""
                INSERT INTO {postgres_store.qualified('operation_runs')} (
                    run_uuid, task_id, run_no, source_system, source_id, status,
                    account_id, resource_family
                ) VALUES (%s, %s, 1, 'registration_jobs', '41', 'running', 7, 'openai_interactive')
                RETURNING id
                """,
                ("run-proxy-traffic", task_id),
            )
            run_id = int(cur.fetchone()["id"])

        self._reserve(explicit_correlation=False)
        row = proxy_lease_store.query_leases(view="current")[0]

        self.assertEqual(row["account_id"], 7)
        self.assertEqual(row["operation_task_id"], task_id)
        self.assertEqual(row["operation_run_id"], run_id)
        self.assertEqual(len(proxy_lease_store.query_leases(account_id=7)), 1)
        self.assertEqual(len(proxy_lease_store.query_leases(operation_task_id=task_id)), 1)
        self.assertEqual(len(proxy_lease_store.query_leases(operation_run_id=run_id)), 1)

    def test_raw_exit_ip_is_scoped_to_authenticated_proxy_traffic_api(self):
        self._reserve()
        from webui.app import create_app

        app = create_app(auth_code="proxy-traffic-test")
        client = app.test_client()

        unauthorized = client.get("/api/proxy-traffic/current")
        self.assertEqual(unauthorized.status_code, 401)

        response = client.get(
            "/api/proxy-traffic/current",
            headers={"X-Auth-Code": "proxy-traffic-test"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["items"][0]["exit_ip"], "8.8.8.8")
        self.assertNotIn("proxy_url", payload["items"][0])
        self.assertNotIn("proxy-user", response.get_data(as_text=True))
        self.assertNotIn("proxy-pass", response.get_data(as_text=True))

    def test_protocol_summary_is_explicitly_unavailable(self):
        traffic = self._traffic()
        summary = traffic.record_protocol_traffic_unavailable(
            operation_task_id=201,
            operation_run_id=202,
            account_id=7,
            purpose="email-change",
        )

        self.assertEqual(summary["availability"], "unavailable")
        self.assertEqual(summary["source"], "protocol")
        self.assertEqual(summary["total_bytes"], 0)
        self.assertEqual(summary["request_count"], 0)
        self.assertIn("browser", summary["unavailable_reason"])

    def test_traffic_query_aggregates_persisted_summaries(self):
        self._reserve()
        traffic = self._traffic()
        traffic.persist_summary(
            {
                "summary_id": "summary-1",
                "lease_id": "lease-1",
                "source": "roxy",
                "method": "cdp",
                "availability": "available",
                "started_at": "2026-09-16T10:00:00+08:00",
                "finished_at": "2026-09-16T10:01:00+08:00",
                "upload_bytes": 10,
                "download_bytes": 100,
                "request_count": 2,
                "failed_count": 1,
                "unfinished_count": 0,
                "unknown_count": 0,
            }
        )
        traffic.persist_summary(
            {
                "summary_id": "summary-2",
                "lease_id": "lease-1",
                "source": "roxy",
                "method": "cdp",
                "availability": "available",
                "started_at": "2026-09-16T10:02:00+08:00",
                "finished_at": "2026-09-16T10:03:00+08:00",
                "upload_bytes": 20,
                "download_bytes": 200,
                "request_count": 3,
                "failed_count": 0,
                "unfinished_count": 1,
                "unknown_count": 1,
            }
        )

        result = traffic.query_traffic(lease_id="lease-1")

        self.assertEqual(result["total_upload_bytes"], 30)
        self.assertEqual(result["total_download_bytes"], 300)
        self.assertEqual(result["total_bytes"], 330)
        self.assertEqual(result["request_count"], 5)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["unfinished_count"], 1)
        self.assertEqual(result["unknown_count"], 1)
        self.assertEqual(result["summary_count"], 2)

    def test_static_pool_lease_is_not_persisted_as_dynamic_lease(self):
        with patch("config.proxy.REGISTRATION_PROXY_MODE", "pool"), patch(
            "config.proxy.pick_proxy", return_value="http://pool-user:pool-pass@5.6.7.8:9000"
        ), patch.object(proxy_lease_store, "reserve_pending") as reserve_pending:
            lease = proxy_provider.acquire_registration_proxy(job_id=99)

        reserve_pending.assert_not_called()
        self.assertEqual(proxy_lease_store.query_leases(view="current"), [])
        self.assertEqual(lease.provider, "proxy_pool")


if __name__ == "__main__":
    unittest.main()
