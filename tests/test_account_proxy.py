# -*- coding: utf-8 -*-
import unittest
from datetime import datetime
from unittest.mock import patch

from core import account_proxy
from core.proxy_provider import ProxyLease


class AccountProxyTests(unittest.TestCase):
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
            patch("core.account_proxy.acquire_1024_proxy", return_value=lease) as acquire,
            patch.multiple("config.proxy", ACCOUNT_ACTION_PROXY_MODE="registration"),
        ):
            route = account_proxy.acquire_account_proxy(
                account_id=7,
                email="a@example.com",
                purpose="plan-check",
            )
        acquire.assert_called_once_with(region="JP", validate=True, job_id="plan-check-7")
        self.assertEqual(route.provider, "1024proxy")
        self.assertEqual(route.region, "JP")

    def test_pool_mode_uses_dedicated_account_proxy_first(self):
        with patch.multiple(
            "config.proxy",
            ACCOUNT_ACTION_PROXY_MODE="pool",
            ACCOUNT_ACTION_PROXY="http://fixed.example:8080",
        ):
            route = account_proxy.acquire_account_proxy(account_id=1, purpose="live-check")
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
