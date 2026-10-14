# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from core import browser_traffic, operation_task_store, postgres_store, proxy_lease_store, proxy_provider, record_store
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

    @staticmethod
    def _beijing_today_start_utc() -> datetime:
        beijing = ZoneInfo("Asia/Shanghai")
        now = datetime.now(timezone.utc).astimezone(beijing)
        return now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    def _seed_traffic(
        self,
        *,
        summary_key: str,
        started_at: datetime,
        total: int,
        purpose: str = "registration",
        operation_task_id: int | None = None,
        operation_run_id: int | None = None,
        registration_job_id: int | None = None,
        account_id: int | None = None,
    ):
        browser_traffic.persist_summary(
            summary_key=summary_key,
            summary={
                "source": "roxy_cdp",
                "method": "cdp",
                "availability": "available",
                "started_at": started_at.isoformat(),
                "ended_at": (started_at + timedelta(seconds=1)).isoformat(),
                "upload_bytes": 0,
                "download_bytes": total,
                "total_bytes": total,
                "request_count": 1,
            },
            purpose=purpose,
            operation_task_id=operation_task_id,
            operation_run_id=operation_run_id,
            registration_job_id=registration_job_id,
            account_id=account_id,
        )

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

    def test_proxy_pool_snapshot_route_is_authenticated_and_read_only(self):
        app = create_app(auth_code="proxy-page-auth")
        client = app.test_client()
        self.assertEqual(client.get("/api/proxy-pool").status_code, 401)
        snapshot = {
            "policy": {"min_ready": 2, "max_size": 20},
            "counts": {"ready": 2, "leased": 1, "quarantine": 3},
            "items": [{"resource_id": "pool-1", "state": "ready", "endpoint": "***:8080", "exit_ip": "203.0.113.0/24"}],
        }
        with patch("core.proxy_pool.snapshot", return_value=snapshot):
            response = client.get("/api/proxy-pool", headers={"X-Auth-Code": "proxy-page-auth"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["counts"]["ready"], 2)
        self.assertNotIn("proxy_url", json.dumps(payload, ensure_ascii=False))

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

    def test_pool_anchor_is_hidden_from_task_lease_counts_but_child_is_counted(self):
        from core import proxy_pool_store

        now = datetime.now()
        anchor = proxy_provider.ProxyLease(
            "pool-anchor-counts", "1024proxy", "http://10.20.30.60:8080", "10.20.30.60:8080",
            now, expires_at=now + timedelta(minutes=30), exit_ip="203.0.113.60", region="US",
        )
        slot = proxy_pool_store.reserve_slot("default", "1024proxy", max_size=20, timeout=60)
        self.assertIsNotNone(slot)
        proxy_lease_store.reserve_pending(
            lease_id=anchor.lease_id, provider=anchor.provider, endpoint=anchor.endpoint,
            proxy_url=anchor.proxy_url, acquired_at=now.isoformat(),
            expires_at=anchor.expires_at.isoformat(), purpose="pool-reserve",
        )
        proxy_lease_store.activate(
            lease_id=anchor.lease_id, exit_ip=anchor.exit_ip, region=anchor.region,
            expires_at=anchor.expires_at.isoformat(),
        )
        self.assertTrue(proxy_pool_store.publish(slot, anchor))

        # 租约历史使用本地无时区时间；测试范围按本次连接的本地日期计算。
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(proxy_lease_store.count_leases(view="current"), 0)
        self.assertEqual(proxy_lease_store.list_page(view="current"), [])
        self.assertEqual(
            proxy_lease_store.count_leases(
                acquired_since=today_start,
                acquired_before=today_start + timedelta(days=1),
            ),
            0,
        )
        self.assertNotIn("pool-reserve", proxy_lease_store.distinct_filter_values()["purpose"])

        child = proxy_pool_store.claim(
            "default", min_ttl=300, max_age=60,
            correlation={"purpose": "registration", "registration_job_id": 801},
        )
        self.assertIsNotNone(child)
        self.assertEqual(proxy_lease_store.count_leases(view="current"), 1)
        self.assertEqual(len(proxy_lease_store.list_page(view="current")), 1)
        self.assertEqual(
            proxy_lease_store.count_leases(
                acquired_since=today_start,
                acquired_before=today_start + timedelta(days=1),
            ),
            1,
        )

        proxy_pool_store.release(child, reason="completed")
        self.assertEqual(proxy_lease_store.count_leases(view="current"), 0)
        self.assertEqual(proxy_lease_store.count_leases(view="history"), 1)
        self.assertEqual(len(proxy_lease_store.list_page(view="history")), 1)
        self.assertEqual(
            proxy_lease_store.count_leases(
                acquired_since=today_start,
                acquired_before=today_start + timedelta(days=1),
            ),
            1,
        )

    def test_proxy_traffic_summary_uses_full_database_and_beijing_day_boundaries(self):
        today_start = self._beijing_today_start_utc()
        self._seed_traffic(
            summary_key="traffic-summary-today",
            started_at=today_start + timedelta(hours=1),
            total=5,
        )
        self._seed_traffic(
            summary_key="traffic-summary-old",
            started_at=today_start - timedelta(days=1, hours=1),
            total=7,
            purpose="live_check",
        )
        browser_traffic.persist_summary(
            summary_key="traffic-summary-other-available",
            summary={
                "source": "other_observer",
                "method": "summary",
                "availability": "available",
                "started_at": (today_start + timedelta(hours=2)).isoformat(),
                "upload_bytes": 0,
                "download_bytes": 3,
                "total_bytes": 3,
                "request_count": 1,
            },
            purpose="registration",
        )
        browser_traffic.record_unavailable(
            summary_key="traffic-summary-protocol",
            source="email_change",
            method="protocol",
            reason="protocol_no_browser_observation",
            purpose="email_change",
        )
        self._seed_lease(lease_id="lease-summary-today")
        old = today_start - timedelta(days=1, hours=1)
        proxy_lease_store.reserve_pending(
            lease_id="lease-summary-old",
            provider="1024proxy",
            endpoint="10.20.30.41:8080",
            proxy_url="http://private-user:private-password@10.20.30.41:8080",
            acquired_at=old.isoformat(),
            expires_at=(old + timedelta(minutes=30)).isoformat(),
            purpose="live_check",
        )
        app = create_app(auth_code="proxy-page-auth")
        response = app.test_client().get(
            "/api/proxy-traffic/summary",
            headers={"X-Auth-Code": "proxy-page-auth"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            {
                key: payload[key]
                for key in (
                    "total_bytes",
                    "today_bytes",
                    "today_browser_count",
                    "today_route_count",
                )
            },
            {
                "total_bytes": 15,
                "today_bytes": 8,
                "today_browser_count": 2,
                "today_route_count": 1,
            },
        )
        self.assertEqual(payload["purposes"], ["live_check", "registration"])
        self.assertEqual(payload["lease_states"], ["leased", "pending"])

    def test_proxy_traffic_pages_return_filtered_total_but_count_is_page_size(self):
        self._seed_lease(lease_id="lease-page-a")
        self._seed_lease(
            lease_id="lease-page-b",
            endpoint="10.20.30.41:8080",
            exit_ip="203.0.113.42",
        )
        response = create_app(auth_code="proxy-page-auth").test_client().get(
            "/api/proxy-traffic/current?limit=1&offset=0&purpose=registration&search=lease-page",
            headers={"X-Auth-Code": "proxy-page-auth"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["total"], 2)
        self.assertTrue(payload["has_more"])

    def test_paginated_routes_use_combined_page_and_total_reads(self):
        app = create_app(auth_code="proxy-page-auth")
        client = app.test_client()
        with patch.object(
            proxy_lease_store,
            "list_page_with_total",
            return_value=([{"id": 1, "lease_id": "lease-snapshot"}], 19),
        ) as lease_page, patch.object(
            proxy_lease_store,
            "count_leases",
            side_effect=AssertionError("分页接口不应再次打开独立总数查询"),
        ):
            response = client.get(
                "/api/proxy-traffic/current?limit=20",
                headers={"X-Auth-Code": "proxy-page-auth"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total"], 19)
        lease_page.assert_called_once()

        with patch.object(
            browser_traffic,
            "list_summaries_with_total",
            return_value=([{"id": 2, "summary_key": "traffic-snapshot"}], 19),
        ) as traffic_page, patch.object(
            browser_traffic,
            "count_summaries",
            side_effect=AssertionError("分页接口不应再次打开独立总数查询"),
        ):
            response = client.get(
                "/api/proxy-traffic/traffic?limit=20",
                headers={"X-Auth-Code": "proxy-page-auth"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total"], 19)
        traffic_page.assert_called_once()

    def test_lease_page_and_total_share_one_time_window_cutoff(self):
        self._seed_lease(lease_id="lease-one-cutoff")
        now = datetime.now()
        with patch.object(
            proxy_lease_store,
            "_lease_window_cutoff",
            side_effect=[now - timedelta(days=1), now + timedelta(days=1)],
        ) as cutoff:
            response = create_app(auth_code="proxy-page-auth").test_client().get(
                "/api/proxy-traffic/current?window=24h",
                headers={"X-Auth-Code": "proxy-page-auth"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["count"], 1)
        self.assertEqual(response.get_json()["total"], 1)
        cutoff.assert_called_once_with("24h")

    def test_browser_traffic_page_hides_unavailable_rows_and_supports_window_filter(self):
        today_start = self._beijing_today_start_utc()
        self._seed_traffic(
            summary_key="traffic-page-today",
            started_at=today_start + timedelta(hours=1),
            total=5,
        )
        self._seed_traffic(
            summary_key="traffic-page-old",
            started_at=today_start - timedelta(days=2),
            total=7,
        )
        browser_traffic.record_unavailable(
            summary_key="traffic-page-unavailable",
            source="email_change",
            method="protocol",
            reason="protocol_no_browser_observation",
        )
        response = create_app(auth_code="proxy-page-auth").test_client().get(
            "/api/proxy-traffic/traffic?limit=1&offset=0&window=24h",
            headers={"X-Auth-Code": "proxy-page-auth"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["total"], 1)
        self.assertFalse(payload["has_more"])
        self.assertEqual(payload["items"][0]["summary_key"], "traffic-page-today")

    def test_browser_traffic_page_includes_task_types_in_one_batch_without_private_data(self):
        operation_task_store.reset_ready()
        operation_task_store.init()
        plan_task = operation_task_store.create_runtime_task(
            task_type="plan_check",
            account_id=None,
            email="plan-private@example.test",
        )
        live_task = operation_task_store.create_runtime_task(
            task_type="live_check",
            account_id=None,
            email="live-private@example.test",
        )
        deleted_task = operation_task_store.create_runtime_task(
            task_type="token_refresh",
            account_id=None,
            email="deleted-private@example.test",
            data={"deleted_by_user": True},
        )
        started_at = datetime.now(timezone.utc)
        self._seed_traffic(
            summary_key="traffic-task-plan-check",
            started_at=started_at,
            total=11,
            operation_task_id=plan_task["id"],
            operation_run_id=plan_task["run"]["id"],
        )
        self._seed_traffic(
            summary_key="traffic-task-live-check",
            started_at=started_at + timedelta(seconds=1),
            total=12,
            operation_task_id=live_task["id"],
            operation_run_id=live_task["run"]["id"],
        )
        self._seed_traffic(
            summary_key="traffic-task-deleted",
            started_at=started_at + timedelta(seconds=2),
            total=13,
            operation_task_id=deleted_task["id"],
            operation_run_id=deleted_task["run"]["id"],
        )
        self._seed_traffic(
            summary_key="traffic-task-unlinked",
            started_at=started_at + timedelta(seconds=3),
            total=14,
        )
        self._seed_traffic(
            summary_key="traffic-registration-job",
            started_at=started_at + timedelta(seconds=4),
            total=15,
            registration_job_id=1234,
        )

        with patch.object(
            operation_task_store,
            "get_task_types",
            wraps=operation_task_store.get_task_types,
        ) as get_task_types:
            response = create_app(auth_code="proxy-page-auth").test_client().get(
                "/api/proxy-traffic/traffic?limit=20",
                headers={"X-Auth-Code": "proxy-page-auth"},
            )

        self.assertEqual(response.status_code, 200)
        items = {item["summary_key"]: item for item in response.get_json()["items"]}
        self.assertEqual(items["traffic-task-plan-check"]["operation_task_type"], "plan_check")
        self.assertEqual(items["traffic-task-live-check"]["operation_task_type"], "live_check")
        self.assertIsNone(items["traffic-task-deleted"]["operation_task_type"])
        self.assertIsNone(items["traffic-task-unlinked"]["operation_task_type"])
        self.assertEqual(items["traffic-registration-job"]["operation_task_type"], "registration")
        get_task_types.assert_called_once_with([
            plan_task["id"], live_task["id"], deleted_task["id"],
        ])
        response_text = response.get_data(as_text=True)
        self.assertNotIn("plan-private@example.test", response_text)
        self.assertNotIn("live-private@example.test", response_text)
        self.assertNotIn("deleted-private@example.test", response_text)

    def test_run_only_auth_traffic_recovers_visible_task_without_rewriting_history(self):
        task = operation_task_store.create_runtime_task(
            task_type="token_refresh", account_id=41, email="private@example.test",
        )
        deleted = operation_task_store.create_runtime_task(
            task_type="token_refresh", account_id=43, email="deleted@example.test",
            data={"deleted_by_user": True},
        )
        now = datetime.now(timezone.utc)
        examples = (
            ("auth-run-only", "token_refresh", task["run"]["id"], None, 41),
            ("registration-run-collision", "registration", task["run"]["id"], 71, 41),
            ("wrong-task-kind", "live_check", task["run"]["id"], None, 41),
            ("wrong-account", "token_refresh", task["run"]["id"], None, 42),
            ("hidden-task", "token_refresh", deleted["run"]["id"], None, 43),
        )
        for key, purpose, run_id, job_id, account_id in examples:
            self._seed_traffic(
                summary_key=key, started_at=now, total=12, purpose=purpose,
                operation_run_id=run_id, registration_job_id=job_id, account_id=account_id,
            )
        with patch.object(operation_task_store, "get_run_task_links", create=True,
                          wraps=getattr(operation_task_store, "get_run_task_links", None)) as links:
            response = create_app(auth_code="proxy-page-auth").test_client().get(
                "/api/proxy-traffic/traffic?limit=20",
                headers={"X-Auth-Code": "proxy-page-auth"},
            )
        self.assertEqual(response.status_code, 200)
        items = {item["summary_key"]: item for item in response.get_json()["items"]}
        self.assertEqual(items["auth-run-only"]["operation_task_id"], task["id"])
        self.assertEqual(items["auth-run-only"]["operation_task_type"], "token_refresh")
        for key in ("registration-run-collision", "wrong-task-kind", "wrong-account", "hidden-task"):
            self.assertIsNone(items[key]["operation_task_id"])
        links.assert_called_once_with(sorted([task["run"]["id"], deleted["run"]["id"]]))
        rows = {row["summary_key"]: row for row in browser_traffic.list_summaries()}
        self.assertIsNone(rows["auth-run-only"]["operation_task_id"])
        self.assertNotIn("private@example.test", response.get_data(as_text=True))

    def test_roxy_capture_inherits_current_task_without_raw_auth_context(self):
        from core import task_run_log
        opened = SimpleNamespace(profile_id="test", debugger_address="127.0.0.1:9222")
        with task_run_log.stage_context("browser", task_id=501, run_id=601, identifier_namespace="operation"), \
             patch.object(browser_traffic, "_new_roxy_collector"), \
             patch.object(browser_traffic, "persist_summary") as persist:
            browser_traffic.start_roxy_capture(opened, purpose="roxy_browser", operation_task_id=None)
            browser_traffic.bind_roxy_capture(opened, purpose="token_refresh", account_id=41)
            browser_traffic.finish_roxy_capture(opened)
        self.assertEqual(persist.call_args.kwargs.get("operation_task_id"), 501)
        self.assertEqual(persist.call_args.kwargs["operation_run_id"], 601)
        self.assertEqual(persist.call_args.kwargs["purpose"], "token_refresh")

    def test_explicit_other_run_never_borrows_current_task(self):
        from core import task_run_log
        opened = SimpleNamespace(profile_id="test", debugger_address="127.0.0.1:9222")
        with task_run_log.stage_context("browser", task_id=501, run_id=601, identifier_namespace="operation"), \
             patch.object(browser_traffic, "_new_roxy_collector"), \
             patch.object(browser_traffic, "persist_summary") as persist:
            browser_traffic.start_roxy_capture(opened, purpose="live_check", operation_run_id=701)
            browser_traffic.finish_roxy_capture(opened)
        self.assertIsNone(persist.call_args.kwargs.get("operation_task_id"))
        self.assertEqual(persist.call_args.kwargs["operation_run_id"], 701)

    def test_registration_job_context_never_becomes_operation_task_correlation(self):
        from core import task_run_log
        opened = SimpleNamespace(profile_id="test", debugger_address="127.0.0.1:9222")
        with task_run_log.stage_context("registration", task_id=501, run_id=601, identifier_namespace="registration"), \
             patch.object(browser_traffic, "_new_roxy_collector"), \
             patch.object(browser_traffic, "persist_summary") as persist:
            task_run_log.set_current_stage("network")
            browser_traffic.start_roxy_capture(opened, purpose="roxy_browser")
            browser_traffic.bind_roxy_capture(opened, purpose="registration", registration_job_id=501)
            browser_traffic.finish_roxy_capture(opened)
        self.assertIsNone(persist.call_args.kwargs.get("operation_task_id"))
        self.assertIsNone(persist.call_args.kwargs.get("operation_run_id"))
        self.assertEqual(persist.call_args.kwargs["registration_job_id"], 501)

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

    def test_data_saver_blocked_request_is_not_counted_as_browser_failure(self):
        summary = browser_traffic.summarize_cdp_events([
            {
                "kind": "http_request",
                "status": 0,
                "failed": True,
                "_data_saver_blocked": True,
                "request_bytes": 0,
                "response_bytes": 0,
            },
        ])
        self.assertEqual(summary["request_count"], 1)
        self.assertEqual(summary["failed_count"], 0)

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
                lease = proxy_provider.fetch_1024_proxy(
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
