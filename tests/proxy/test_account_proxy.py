# -*- coding: utf-8 -*-
import unittest
import logging
import tempfile
from datetime import datetime
from unittest.mock import patch

from core.proxy import account_routes as account_proxy
from core.proxy import pool as proxy_pool
from core.operations.runtime import OperationCancelled
from core.proxy.provider import ProxyLease


class AccountProxyTests(unittest.TestCase):
    def test_wait_observes_explicit_cancellation_for_both_builtin_sources(self):
        def cancel():
            raise OperationCancelled("离线模拟用户取消线路等待")

        for source in ("provider:1024proxy", "pool"):
            with (
                self.subTest(source=source),
                patch.object(proxy_pool, "start"),
                patch.object(proxy_pool.store, "claim", return_value=None),
                patch.multiple("config.proxy", ACCOUNT_ACTION_PROXY="http://192.0.2.1:8080",
                               PROXY_1024_API_URL="https://example.test/proxies", PROXY_1024_SESSION_MINUTES=30),
            ):
                with self.assertRaisesRegex(OperationCancelled, "取消线路等待"):
                    account_proxy.acquire_account_proxy(
                        account_id=1, purpose="plan-check", region="US", source=source,
                        cancel=cancel, timeout=1,
                    )

    def test_wait_reports_progress_for_both_builtin_sources(self):
        lease = ProxyLease(
            "waiting-route", "1024proxy", "http://192.0.2.1:8080", "192.0.2.1:8080",
            datetime.now(), exit_ip="198.51.100.1", region="US",
        )
        for source in ("provider:1024proxy", "pool"):
            progress = []
            with (
                self.subTest(source=source),
                patch.object(proxy_pool, "start"),
                patch.object(proxy_pool.store, "claim", return_value=lease),
                patch.object(proxy_pool._stop, "is_set", return_value=False),
                patch.multiple("config.proxy", ACCOUNT_ACTION_PROXY="http://192.0.2.1:8080",
                               PROXY_1024_API_URL="https://example.test/proxies", PROXY_1024_SESSION_MINUTES=30),
            ):
                route = account_proxy.acquire_account_proxy(
                    account_id=1, purpose="plan-check", region="US", source=source,
                    progress_callback=progress.append, timeout=1,
                )
                self.assertIs(route.lease, lease)
                self.assertTrue(any("代理池" in message for message in progress))

    def test_explicit_zero_timeout_is_preserved_for_both_builtin_sources(self):
        for source in ("provider:1024proxy", "pool"):
            with (
                self.subTest(source=source),
                patch.object(proxy_pool, "start"),
                patch.object(proxy_pool.store, "claim", return_value=None),
                patch.multiple("config.proxy", ACCOUNT_ACTION_PROXY="http://192.0.2.1:8080",
                               PROXY_1024_API_URL="https://example.test/proxies", PROXY_1024_SESSION_MINUTES=30),
            ):
                with self.assertRaises(proxy_pool.ProxyPoolTimeout):
                    account_proxy.acquire_account_proxy(
                        account_id=1, purpose="plan-check", region="US", source=source,
                        timeout=0,
                    )

    def test_plan_route_preserves_frozen_reuse_limit_for_provider_and_static_pool(self):
        lease = ProxyLease(
            "limited-route", "1024proxy", "http://192.0.2.1:8080", "192.0.2.1:8080",
            datetime.now(), exit_ip="198.51.100.1", region="US",
        )
        for source in ("provider:1024proxy", "pool"):
            with (
                self.subTest(source=source),
                patch("core.proxy.pool.acquire_proxy", return_value=lease) as acquire,
                patch.multiple("config.proxy", PLAN_CHECK_PROXY_ALLOW_REUSE=True,
                               PLAN_CHECK_PROXY_REUSE_LIMIT=3, ACCOUNT_ACTION_PROXY="http://192.0.2.1:8080",
                               PROXY_POOL_SOURCE="1024proxy", PROXY_1024_API_URL="https://example.test/proxies",
                               create=True),
            ):
                route = account_proxy.acquire_account_proxy(
                    account_id=1, purpose="plan-check", region="US", source=source,
                    allow_reuse=True, reuse_limit=5,
                )
                self.assertEqual("US", route.region)
                self.assertEqual(5, acquire.call_args.kwargs.get("reuse_limit"))

    def test_action_proxy_mode_always_uses_unified_pool(self):
        with (
            patch.multiple(
                "config.account",
                ACCOUNT_PLAN_CHECK_PROXY_MODE="direct",
                ACCOUNT_LIVE_CHECK_PROXY_MODE="pool",
                ACCOUNT_PASSWORD_PROXY_MODE="provider:1024proxy",
            ),
        ):
            self.assertEqual("pool", account_proxy.account_action_proxy_mode("plan-check"))
            self.assertEqual("pool", account_proxy.account_action_proxy_mode("live-check"))
            self.assertEqual("pool", account_proxy.account_action_proxy_mode("password-setup"))

    def test_direct_action_still_acquires_from_unified_pool(self):
        lease = ProxyLease("pool-lease", "1024proxy", "http://192.0.2.1:8080", "192.0.2.1:8080",
                           datetime.now(), exit_ip="198.51.100.1", region="JP")
        with (
            patch.multiple(
                "config.account",
                ACCOUNT_PLAN_CHECK_PROXY_MODE="direct",
            ),
            patch("core.proxy.pool.acquire_proxy", return_value=lease) as acquire,
            patch.multiple("config.proxy", PROXY_POOL_SOURCE="1024proxy", PROXY_1024_API_URL="https://example.test/proxies"),
        ):
            route = account_proxy.acquire_account_proxy(
                account_id=1,
                purpose="plan-check",
            )
        acquire.assert_called_once()
        self.assertEqual("1024proxy", route.provider)
        self.assertEqual("pool", route.mode)

    def test_legacy_provider_alias_normalizes_to_1024_provider(self):
        self.assertEqual(
            "provider:1024proxy",
            account_proxy.normalize_proxy_source("1024"),
        )
        self.assertEqual("direct", account_proxy.normalize_proxy_source("none"))
        self.assertEqual("pool", account_proxy.normalize_proxy_source("static_pool"))

    def test_registration_mode_follows_1024_and_account_country(self):
        lease = ProxyLease(
            lease_id="lease",
            provider="1024proxy",
            proxy_url="http://1.2.3.4:8080",
            endpoint="1.2.3.4:8080",
            acquired_at=datetime.now(),
            exit_ip="1.2.3.4",
            region="JP",
        )
        with (
            patch("core.proxy.account_routes.registration_proxy_mode", return_value="1024"),
            patch("core.proxy.account_routes.resolve_account_region", return_value="JP"),
            patch("core.proxy.pool.acquire_proxy", return_value=lease) as acquire,
            patch.multiple("config.proxy", ACCOUNT_ACTION_PROXY_MODE="registration",
                           PROXY_POOL_SOURCE="1024proxy", PROXY_1024_API_URL="https://example.test/proxies"),
            patch.multiple("config.account", ACCOUNT_PLAN_CHECK_PROXY_MODE="registration"),
        ):
            route = account_proxy.acquire_account_proxy(
                account_id=7,
                email="a@example.com",
                purpose="plan-check",
            )
        self.assertEqual("JP", acquire.call_args.kwargs["country"])
        self.assertEqual("plan-check", acquire.call_args.kwargs["purpose"])
        self.assertEqual(7, acquire.call_args.kwargs["account_id"])
        self.assertNotIn("provider", acquire.call_args.kwargs)
        self.assertEqual(route.provider, "1024proxy")
        self.assertEqual(route.region, "JP")

    def test_1024_account_route_changes_sticky_seed_for_rotation(self):
        lease = ProxyLease(
            lease_id="lease",
            provider="1024proxy",
            proxy_url="http://1.2.3.4:8080",
            endpoint="1.2.3.4:8080",
            acquired_at=datetime.now(),
            exit_ip="1.2.3.4",
            region="JP",
        )
        with (
            patch("core.proxy.account_routes.registration_proxy_mode", return_value="1024"),
            patch("core.proxy.account_routes.resolve_account_region", return_value="JP"),
            patch("core.proxy.pool.acquire_proxy", return_value=lease) as acquire,
            patch.multiple("config.proxy", ACCOUNT_ACTION_PROXY_MODE="registration",
                           PROXY_POOL_SOURCE="1024proxy", PROXY_1024_API_URL="https://example.test/proxies"),
            patch.multiple("config.account", ACCOUNT_PLAN_CHECK_PROXY_MODE="registration"),
        ):
            account_proxy.acquire_account_proxy(
                account_id=7,
                email="a@example.com",
                purpose="plan-check",
                rotation_index=3,
            )
        self.assertEqual("JP", acquire.call_args.kwargs["country"])
        self.assertEqual("plan-check-7-rotation-3", acquire.call_args.kwargs["correlation_id"])
        self.assertNotIn("provider", acquire.call_args.kwargs)

    def test_pool_mode_uses_dedicated_account_proxy_first(self):
        lease = ProxyLease(
            lease_id="pool-lease",
            provider="proxy_pool",
            proxy_url="http://fixed.example:8080",
            endpoint="fixed.example:8080",
            acquired_at=datetime.now(),
            region="US",
        )
        with patch.multiple(
            "config.proxy",
            ACCOUNT_ACTION_PROXY_MODE="pool",
            ACCOUNT_ACTION_PROXY="http://fixed.example:8080",
            PROXY_POOL_SOURCE="manual", PROXY_POOL=["http://fixed.example:8080"],
        ), patch("core.proxy.pool.acquire_proxy", return_value=lease) as acquire:
            route = account_proxy.acquire_account_proxy(account_id=1, purpose="live-check")
        acquire.assert_called_once()
        self.assertEqual("live-check", acquire.call_args.kwargs["purpose"])
        self.assertNotIn("provider", acquire.call_args.kwargs)
        self.assertEqual(route.proxy_url, "http://fixed.example:8080")
        self.assertEqual(route.provider, "proxy_pool")

    def test_pool_refuses_random_country(self):
        with (
            patch.multiple("config.proxy", ACCOUNT_ACTION_PROXY_MODE="1024",
                           PROXY_POOL_SOURCE="1024proxy", PROXY_1024_API_URL="https://example.test/proxies"),
        ):
            with self.assertRaisesRegex(ValueError, "ISO"):
                account_proxy.acquire_account_proxy(account_id=1, purpose="plan-check", region="Rand")

    def test_explicit_registration_proxy_is_not_released_as_platform_lease(self):
        route = account_proxy.acquire_account_proxy(
            account_id=1,
            purpose="registration-plan-check",
            explicit_proxy="http://same-proxy.example:8080",
        )
        self.assertIsNone(route.lease)
        self.assertEqual(route.mode, "request")

    def test_empty_explicit_proxy_does_not_create_direct_route(self):
        lease = ProxyLease("pool", "1024proxy", "http://192.0.2.2:8080", "192.0.2.2:8080",
                           datetime.now(), exit_ip="198.51.100.2", region="JP")
        with patch("core.proxy.pool.acquire_proxy", return_value=lease) as acquire, \
             patch.multiple("config.proxy", PROXY_POOL_SOURCE="1024proxy",
                            PROXY_1024_API_URL="https://proxy.example.test/api"):
            route = account_proxy.acquire_account_proxy(
                account_id=1, purpose="plan-check", explicit_proxy="", region="JP",
            )
        acquire.assert_called_once()
        self.assertEqual("pool", route.mode)
        self.assertEqual("1024proxy", route.provider)


class LegacyAccountProxyCancellationTests(unittest.TestCase):
    def test_setup_wait_stops_without_starting_browser_or_plan_request(self):
        from core.codex import retry_service as codex_retry_service

        for steps, native_cancel in (({"plan_check"}, False), ({"password"}, False), ({"password"}, True)):
            def acquire(**kwargs):
                if native_cancel:
                    raise OperationCancelled("离线模拟持久任务取消线路等待")
                cancel = kwargs.get("cancel")
                if cancel is None:
                    raise RuntimeError("旧账号配置线路等待未连接取消检查")
                cancel()
                raise AssertionError("取消后不能交付线路")

            with (
                self.subTest(steps=steps, native_cancel=native_cancel),
                tempfile.NamedTemporaryFile(suffix=".log") as output,
                patch.object(codex_retry_service.db, "get_account_by_email", return_value={"id": 1}),
                patch.object(codex_retry_service.account_task_store, "get_task", return_value={}),
                patch.object(codex_retry_service.account_task_store, "append_event"),
                patch.object(codex_retry_service.task_run_log, "TaskRunLogHandler", return_value=logging.NullHandler()),
                patch("config.reload_all"),
                patch.object(codex_retry_service, "is_stop_requested", side_effect=[False, True]),
                patch("core.proxy.account_routes.acquire_account_proxy", side_effect=acquire),
                patch.object(codex_retry_service, "_run_retry_plan_check") as query,
                patch("core.codex.roxy.oauth.run_roxy_chatgpt_account_action") as browser,
                patch.object(codex_retry_service, "_RUNNING_THREADS", {}),
                patch.object(codex_retry_service, "_RESERVED_AT", {}),
                patch.object(codex_retry_service, "_STOP_REQUESTED", set()),
            ):
                result = codex_retry_service.run_twofa_worker(
                    "legacy-wait@example.test", task_id=101, target_log_path=output.name,
                    steps=steps, manage_task=False, password_driver_override="roxy",
                    plan_driver_override="protocol",
                )
                self.assertEqual("stopped", result["status"])
                self.assertFalse(result["ok"])
                query.assert_not_called()
                browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
