# -*- coding: utf-8 -*-
import unittest
from datetime import datetime
from unittest.mock import patch

from core import account_proxy
from core.proxy_provider import ProxyLease


class AccountProxyTests(unittest.TestCase):
    def test_plan_route_preserves_frozen_reuse_limit_for_provider_and_static_pool(self):
        lease = ProxyLease(
            "limited-route", "1024proxy", "http://192.0.2.1:8080", "192.0.2.1:8080",
            datetime.now(), exit_ip="198.51.100.1", region="US",
        )
        for source in ("provider:1024proxy", "pool"):
            with (
                self.subTest(source=source),
                patch("core.proxy_pool.acquire", return_value=lease) as acquire,
                patch.multiple("config.proxy", PLAN_CHECK_PROXY_ALLOW_REUSE=True,
                               PLAN_CHECK_PROXY_REUSE_LIMIT=3, ACCOUNT_ACTION_PROXY="http://192.0.2.1:8080",
                               create=True),
            ):
                route = account_proxy.acquire_account_proxy(
                    account_id=1, purpose="plan-check", region="US", source=source,
                    allow_reuse=True, reuse_limit=5,
                )
                self.assertEqual("US", route.region)
                self.assertEqual(5, acquire.call_args.kwargs.get("reuse_limit"))

    def test_action_proxy_mode_uses_action_specific_config(self):
        with (
            patch.multiple(
                "config.account",
                ACCOUNT_PLAN_CHECK_PROXY_MODE="direct",
                ACCOUNT_LIVE_CHECK_PROXY_MODE="pool",
                ACCOUNT_PASSWORD_PROXY_MODE="provider:1024proxy",
            ),
        ):
            self.assertEqual("direct", account_proxy.account_action_proxy_mode("plan-check"))
            self.assertEqual("pool", account_proxy.account_action_proxy_mode("live-check"))
            self.assertEqual("provider:1024proxy", account_proxy.account_action_proxy_mode("password-setup"))

    def test_direct_action_does_not_acquire_1024_lease(self):
        with (
            patch.multiple(
                "config.account",
                ACCOUNT_PLAN_CHECK_PROXY_MODE="direct",
            ),
            patch("core.proxy_pool.acquire") as acquire,
        ):
            route = account_proxy.acquire_account_proxy(
                account_id=1,
                purpose="plan-check",
            )
        acquire.assert_not_called()
        self.assertEqual("direct", route.provider)
        self.assertEqual("", route.proxy_url)
        self.assertEqual("direct", route.mode)

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
            patch("core.account_proxy.registration_proxy_mode", return_value="1024"),
            patch("core.account_proxy.resolve_account_region", return_value="JP"),
            patch("core.proxy_pool.acquire", return_value=lease) as acquire,
            patch.multiple("config.proxy", ACCOUNT_ACTION_PROXY_MODE="registration"),
            patch.multiple("config.account", ACCOUNT_PLAN_CHECK_PROXY_MODE="registration"),
        ):
            route = account_proxy.acquire_account_proxy(
                account_id=7,
                email="a@example.com",
                purpose="plan-check",
            )
        acquire.assert_called_once_with(
            provider="1024proxy",
            region="JP", validate=True, job_id="plan-check-7", account_id=7,
            purpose="plan-check", operation_task_id=None, operation_run_id=None, allow_reuse=True, reuse_limit=3,
        )
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
            patch("core.account_proxy.registration_proxy_mode", return_value="1024"),
            patch("core.account_proxy.resolve_account_region", return_value="JP"),
            patch("core.proxy_pool.acquire", return_value=lease) as acquire,
            patch.multiple("config.proxy", ACCOUNT_ACTION_PROXY_MODE="registration"),
            patch.multiple("config.account", ACCOUNT_PLAN_CHECK_PROXY_MODE="registration"),
        ):
            account_proxy.acquire_account_proxy(
                account_id=7,
                email="a@example.com",
                purpose="plan-check",
                rotation_index=3,
            )
        acquire.assert_called_once_with(
            provider="1024proxy",
            region="JP",
            validate=True,
            job_id="plan-check-7-rotation-3",
            account_id=7,
            purpose="plan-check",
            operation_task_id=None,
            operation_run_id=None,
            allow_reuse=True,
            reuse_limit=3,
        )

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
        ), patch("core.proxy_pool.acquire", return_value=lease) as acquire:
            route = account_proxy.acquire_account_proxy(account_id=1, purpose="live-check")
        acquire.assert_called_once_with(
            provider="proxy_pool",
            static_urls=["http://fixed.example:8080"],
            purpose="live-check",
            account_id=1,
            operation_task_id=None,
            operation_run_id=None,
            allow_reuse=False,
        )
        self.assertEqual(route.proxy_url, "http://fixed.example:8080")
        self.assertEqual(route.provider, "proxy_pool")

    def test_1024_refuses_unknown_random_country(self):
        with (
            patch("core.account_proxy.resolve_account_region", return_value=""),
            patch.multiple("config.proxy", ACCOUNT_ACTION_PROXY_MODE="1024"),
        ):
            with self.assertRaisesRegex(RuntimeError, "无法确定账号注册国家"):
                account_proxy.acquire_account_proxy(account_id=1, purpose="plan-check")

    def test_explicit_registration_proxy_is_not_released_as_platform_lease(self):
        route = account_proxy.acquire_account_proxy(
            account_id=1,
            purpose="registration-plan-check",
            explicit_proxy="http://same-proxy.example:8080",
        )
        self.assertIsNone(route.lease)
        self.assertEqual(route.mode, "request")


if __name__ == "__main__":
    unittest.main()
