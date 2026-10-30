"""公共资源缓存与注册生命周期、线路和流量口径的接入测试。"""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from core.browser import asset_policy as browser_asset_policy, traffic as browser_traffic
from core.registration.debug import _RoxyTargetCollector


class BrowserAssetPolicyTests(TestCase):
    def test_auth_cache_uses_current_target_without_anonymous_network_fill(self):
        capture = SimpleNamespace(public_asset_cache=None, set_public_asset_cache=Mock())
        opened = SimpleNamespace(debugger_address="127.0.0.1:9222", created_by_run=True, traffic_capture=capture)
        driver = Mock()
        driver.execute_cdp_cmd.return_value = {"targetInfo": {"targetId": "current-page", "type": "page"}}
        start = getattr(browser_asset_policy, "start_auth_asset_cache", lambda *args, **kwargs: None)
        with patch.object(browser_asset_policy._cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "enabled"), patch(
            "core.browser.asset_cache.PublicAssetCache"
        ) as cls:
            result = start(opened, driver, flow="token_refresh")
        self.assertIs(result, cls.return_value)
        self.assertEqual(cls.call_args.kwargs["target_id"], "current-page")
        self.assertIsNone(cls.call_args.kwargs["proxy_url"])
        self.assertFalse(cls.call_args.kwargs["allow_direct"])
        self.assertNotIn("anonymous_fetcher", cls.call_args.kwargs)
        capture.set_public_asset_cache.assert_called_once_with(result)

    def test_auth_cache_does_not_take_ownership_of_registration_cache(self):
        parent = Mock()
        opened = SimpleNamespace(traffic_capture=SimpleNamespace(public_asset_cache=parent))
        start = getattr(browser_asset_policy, "start_auth_asset_cache", lambda *args, **kwargs: None)
        with patch.object(browser_asset_policy._cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "enabled"), patch(
            "core.browser.asset_cache.PublicAssetCache"
        ) as cls:
            self.assertIsNone(start(opened, Mock(), flow="codex_oauth"))
        cls.assert_not_called()
        parent.stop.assert_not_called()

    def test_auth_cache_without_current_page_target_keeps_normal_network(self):
        opened = SimpleNamespace(traffic_capture=None)
        driver = Mock()
        driver.execute_cdp_cmd.return_value = {}
        start = getattr(browser_asset_policy, "start_auth_asset_cache", lambda *args, **kwargs: None)
        with patch.object(browser_asset_policy._cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "enabled"), patch(
            "core.browser.asset_cache.PublicAssetCache"
        ) as cls:
            self.assertIsNone(start(opened, driver, flow="token_refresh"))
        cls.assert_not_called()

    def test_off_does_not_open_cache_or_browser_connection(self):
        with patch.object(browser_asset_policy._cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "off"), patch(
            "core.browser.asset_cache.PublicAssetCache"
        ) as cls:
            self.assertIsNone(browser_asset_policy.start_registration_asset_cache(SimpleNamespace()))
        cls.assert_not_called()

    def test_new_profile_fill_uses_its_explicit_proxy_and_binds_capture(self):
        capture = Mock()
        opened = SimpleNamespace(debugger_address="127.0.0.1:9222", created_by_run=True, traffic_capture=capture)
        with patch.object(browser_asset_policy._cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "enabled"), patch(
            "core.browser.asset_cache.PublicAssetCache"
        ) as cls:
            result = browser_asset_policy.start_registration_asset_cache(opened, proxy_url="http://127.0.0.1:7897")
        self.assertIs(result, cls.return_value)
        self.assertEqual(cls.call_args.kwargs["proxy_url"], "http://127.0.0.1:7897")
        self.assertFalse(cls.call_args.kwargs["allow_direct"])
        capture.set_public_asset_cache.assert_called_once_with(result)

    def test_registration_cache_binds_current_driver_page(self):
        opened = SimpleNamespace(debugger_address="127.0.0.1:9222", created_by_run=True, traffic_capture=None)
        driver = Mock()
        driver.execute_cdp_cmd.return_value = {"targetInfo": {"targetId": "registration-page", "type": "page"}}
        with patch.object(browser_asset_policy._cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "enabled"), patch(
            "core.browser.asset_cache.PublicAssetCache"
        ) as cls:
            result = browser_asset_policy.start_registration_asset_cache(opened, driver, proxy_url="http://127.0.0.1:7897")
        self.assertIs(result, cls.return_value)
        driver.execute_cdp_cmd.assert_called_once_with("Target.getTargetInfo", {})
        self.assertEqual(cls.call_args.kwargs["target_id"], "registration-page")
        self.assertEqual(cls.call_args.kwargs["proxy_url"], "http://127.0.0.1:7897")

    def test_registration_cache_does_not_guess_page_when_driver_target_is_unknown(self):
        for target in ({}, {"targetInfo": {"targetId": "worker", "type": "service_worker"}}):
            with self.subTest(target=target):
                driver = Mock()
                driver.execute_cdp_cmd.return_value = target
                with patch.object(browser_asset_policy._cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "enabled"), patch(
                    "core.browser.asset_cache.PublicAssetCache"
                ) as cls:
                    self.assertIsNone(browser_asset_policy.start_registration_asset_cache(SimpleNamespace(), driver))
                cls.assert_not_called()

    def test_registration_cache_driver_failure_keeps_normal_network(self):
        driver = Mock()
        driver.execute_cdp_cmd.side_effect = OSError("测试页面已关闭")
        with patch.object(browser_asset_policy._cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "enabled"), patch(
            "core.browser.asset_cache.PublicAssetCache"
        ) as cls:
            self.assertIsNone(browser_asset_policy.start_registration_asset_cache(SimpleNamespace(), driver))
        cls.assert_not_called()

    def test_existing_profile_never_guesses_its_proxy_for_anonymous_fill(self):
        opened = SimpleNamespace(debugger_address="127.0.0.1:9222", created_by_run=False, traffic_capture=None)
        with patch.object(browser_asset_policy._cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "enabled"), patch(
            "core.browser.asset_cache.PublicAssetCache"
        ) as cls:
            browser_asset_policy.start_registration_asset_cache(opened, proxy_url="http://127.0.0.1:7897")
        self.assertIsNone(cls.call_args.kwargs["proxy_url"])
        self.assertFalse(cls.call_args.kwargs["allow_direct"])

    def test_start_failure_stops_partial_interception_and_returns_none(self):
        with patch.object(browser_asset_policy._cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "enabled"), patch(
            "core.browser.asset_cache.PublicAssetCache"
        ) as cls:
            cls.return_value.start.side_effect = OSError("测试连接失败")
            result = browser_asset_policy.start_registration_asset_cache(SimpleNamespace())
        self.assertIsNone(result)
        cls.return_value.stop.assert_called_once()

    def test_local_fulfill_bytes_excluded_but_fill_network_download_included(self):
        opened = SimpleNamespace(profile_id="test", debugger_address="127.0.0.1:9222")
        cache = Mock()
        cache.snapshot.return_value = {"anonymous_fill_bytes": 70, "anonymous_requests": 1, "avoided_upstream_bytes": 120}
        with patch.object(browser_traffic, "_new_roxy_collector"), patch.object(browser_traffic, "persist_summary") as save:
            capture = browser_traffic.RoxyTrafficCapture(opened)
            capture.set_public_asset_cache(cache)
            capture.record_network({"url": "https://cdn.example/app.js", "cache_source": "local", "encoded_data_length": 4000, "status": 200})
            capture.record_network({"url": "https://cdn.example/page.css", "cache_source": "native", "encoded_data_length": 0, "status": 200})
            capture.record_network({"url": "https://example/api", "encoded_data_length": 30, "status": 200})
            capture.stop()
            capture.stop()
        save.assert_called_once()
        summary = save.call_args.kwargs["summary"]
        self.assertEqual(summary["download_bytes"], 100)
        self.assertEqual(summary["cache_local_served_bytes"], 4000)
        self.assertEqual(summary["cache_local_request_count"], 1)
        self.assertEqual(summary["cache_native_request_count"], 1)
        self.assertEqual(summary["cache_fill_request_count"], 1)
        self.assertEqual(summary["cache_avoided_upstream_bytes"], 120)

    def test_bad_cache_snapshot_does_not_discard_browser_traffic(self):
        opened = SimpleNamespace(profile_id="test", debugger_address="127.0.0.1:9222")
        cache = Mock()
        cache.snapshot.side_effect = ValueError("测试快照失败")
        with patch.object(browser_traffic, "_new_roxy_collector"), patch.object(browser_traffic, "persist_summary") as save:
            capture = browser_traffic.RoxyTrafficCapture(opened)
            capture.set_public_asset_cache(cache)
            capture.record_network({"url": "https://example/api", "encoded_data_length": 30, "status": 200})
            capture.stop()
        self.assertEqual(save.call_args.kwargs["summary"]["download_bytes"], 30)
        self.assertEqual(save.call_args.kwargs["summary"]["unknown_count"], 1)

    def test_incomplete_fill_keeps_observed_bytes_and_marks_unknown(self):
        cache = Mock()
        cache.snapshot.return_value = {"anonymous_fill_bytes": 70, "anonymous_accounting_complete": False}
        opened = SimpleNamespace(profile_id="test", debugger_address="127.0.0.1:9222")
        with patch.object(browser_traffic, "_new_roxy_collector"), patch.object(browser_traffic, "persist_summary") as save:
            capture = browser_traffic.RoxyTrafficCapture(opened)
            capture.set_public_asset_cache(cache)
            capture.record_network({"url": "https://example/api", "encoded_data_length": 30, "status": 200})
            capture.stop()
        self.assertEqual(save.call_args.kwargs["summary"]["download_bytes"], 100)
        self.assertEqual(save.call_args.kwargs["summary"]["unknown_count"], 1)

    def test_unconfirmed_replay_never_deducts_observed_network_bytes(self):
        session = browser_traffic._SummaryOnlyCDPSession("test")
        session.record_network({"url": "https://cdn.example/app.js", "cache_source": "unknown", "encoded_data_length": 4000, "status": 200})
        summary = session.summary()
        self.assertEqual(summary["download_bytes"], 4000)
        self.assertEqual(summary["cache_local_request_count"], 0)
        self.assertEqual(summary["unknown_count"], 1)

    def test_collector_preserves_target_scoped_replay_confirmation(self):
        for source, expected_bytes, unknown in (("local", 0, 0), ("unknown", 4000, 1), ("network", 4000, 0)):
            with self.subTest(source=source):
                session = browser_traffic._SummaryOnlyCDPSession("test")
                cache = Mock()
                cache.request_source.return_value = source
                collector = _RoxyTargetCollector(SimpleNamespace(session=session, public_asset_cache=cache), "page-1", "ws://unused", "page")
                collector._requests["request-1"] = {"url": "https://cdn.example/app.js", "encoded_data_length": 4000, "status": 200}
                collector._finish_request("request-1")
                cache.request_source.assert_called_once_with("request-1", target_id="page-1")
                self.assertEqual(session.summary()["download_bytes"], expected_bytes)
                self.assertEqual(session.summary()["unknown_count"], unknown)
