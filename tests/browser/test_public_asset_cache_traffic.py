"""公共缓存诊断收口及持久化边界测试，不连接浏览器或数据库。"""
from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.browser import traffic as browser_traffic
from core.browser.asset_cache import PublicAssetCache
from core.registration.debug import _RoxyTargetCollector


class PublicAssetCacheTrafficTests(unittest.TestCase):
    def test_late_fulfill_confirmation_corrects_only_its_bytes_and_resource_details_once(self):
        from config import browser as browser_cfg

        cache = PublicAssetCache("127.0.0.1:9222", "/unused-offline-accounting", policy="token_refresh", target_id="page-a")
        opened = SimpleNamespace(profile_id="test-profile", debugger_address="127.0.0.1:9222")
        with patch.object(browser_cfg, "BROWSER_TRAFFIC_DETAIL_LOG", True), patch.object(
            browser_traffic, "_new_roxy_collector", return_value=Mock(),
        ), patch.object(browser_traffic, "persist_summary") as save:
            capture = browser_traffic.RoxyTrafficCapture(opened)
            capture.set_public_asset_cache(cache)
            collector = _RoxyTargetCollector(SimpleNamespace(session=capture.session, public_asset_cache=cache), "page-a", "ws://unused", "page")
            cache._source("net-1", "pending")
            collector._requests["net-1"] = {
                "url": "https://chatgpt.com/cdn/assets/app-12345678.js", "resource_type": "Script",
                "encoded_data_length": 4000000, "request_body_bytes": 11, "status": 200,
            }
            collector._finish_request("net-1")
            self.assertEqual(capture.session.summary()["download_bytes"], 4000000)
            self.assertEqual(capture.session.summary()["unknown_count"], 1)
            capture.record_network({"url": "https://example.test/api", "resource_type": "Fetch", "encoded_data_length": 40, "status": 200})
            cache._reply(("fulfill", "fetch-1", "net-1", 4000000, 1500000), {"result": {}})
            capture.stop()
            capture.stop()
        save.assert_called_once()
        summary = save.call_args.kwargs["summary"]
        self.assertEqual(summary["upload_bytes"], 0)
        self.assertEqual(summary["download_bytes"], 40)
        self.assertEqual(summary["unknown_count"], 0)
        self.assertEqual(summary["cache_local_request_count"], 1)
        self.assertEqual(summary["cache_local_served_bytes"], 4000000)
        self.assertEqual(summary["resource_type_bytes"], {"fetch": 40, "script": 0})
        self.assertEqual([row["url"] for row in summary["resource_details"]], ["example.test/api"])

    def test_unconfirmed_token_replay_retains_observed_bytes_and_diagnostics(self):
        from config import browser as browser_cfg

        cache = SimpleNamespace(policy="token_refresh", request_source=lambda *args, **kwargs: "unknown", snapshot=lambda: {})
        opened = SimpleNamespace(profile_id="test-profile", debugger_address="127.0.0.1:9222")
        with patch.object(browser_cfg, "BROWSER_TRAFFIC_DETAIL_LOG", True), patch.object(
            browser_traffic, "_new_roxy_collector", return_value=Mock(),
        ), patch.object(browser_traffic, "persist_summary") as save:
            capture = browser_traffic.RoxyTrafficCapture(opened)
            capture.set_public_asset_cache(cache)
            capture.record_network({
                "target_id": "page-a", "request_id": "net-1", "cache_source": "unknown",
                "url": "https://chatgpt.com/cdn/assets/app-12345678.js", "resource_type": "Script",
                "encoded_data_length": 500, "status": 200,
            })
            capture.stop()
        summary = save.call_args.kwargs["summary"]
        self.assertEqual(summary["download_bytes"], 500)
        self.assertEqual(summary["unknown_count"], 1)
        self.assertEqual(summary["cache_local_request_count"], 0)
        self.assertEqual(summary["resource_details"][0]["download_bytes"], 500)

    def test_strict_replay_keeps_original_accounting_when_confirmation_is_late(self):
        cache = PublicAssetCache("127.0.0.1:9222", "/unused-offline-accounting", target_id="page-a")
        session = browser_traffic._SummaryOnlyCDPSession("test-profile")
        session.public_asset_cache = cache
        cache._source("net-1", "pending")
        session.record_network({
            "target_id": "page-a", "request_id": "net-1", "cache_source": "unknown",
            "url": "https://chatgpt.com/cdn/assets/app-12345678.js", "resource_type": "Script", "encoded_data_length": 500,
        })
        cache._reply(("fulfill", "fetch-1", "net-1", 500, 100), {"result": {}})
        session.finalize_cache_accounting()
        self.assertEqual(session.summary()["download_bytes"], 500)
        self.assertEqual(session.summary()["unknown_count"], 1)
        self.assertEqual(session.summary()["cache_local_request_count"], 0)

    def test_same_request_id_in_other_target_cannot_be_reimbursed(self):
        cache = PublicAssetCache("127.0.0.1:9222", "/unused-offline-accounting", policy="token_refresh", target_id="page-a")
        session = browser_traffic._SummaryOnlyCDPSession("test-profile")
        session.public_asset_cache = cache
        for target, source, size in (("page-a", "unknown", 500), ("page-b", "network", 600)):
            session.record_network({
                "target_id": target, "request_id": "net-1", "cache_source": source,
                "url": "https://chatgpt.com/cdn/assets/app-12345678.js", "resource_type": "Script", "encoded_data_length": size, "status": 200,
            })
        cache._source("net-1", "local")
        session.finalize_cache_accounting()
        session.finalize_cache_accounting()
        self.assertEqual(session.summary()["download_bytes"], 600)
        self.assertEqual(session.summary()["cache_local_request_count"], 1)
        self.assertEqual(session.summary()["unknown_count"], 0)

    def test_redirect_bytes_sharing_request_id_remain_network_when_final_hop_is_local(self):
        cache = PublicAssetCache("127.0.0.1:9222", "/unused-offline-accounting", policy="token_refresh", target_id="page-a")
        session = browser_traffic._SummaryOnlyCDPSession("test-profile")
        session.public_asset_cache = cache
        for status, size in ((302, 70), (200, 500)):
            session.record_network({
                "target_id": "page-a", "request_id": "net-1", "cache_source": "network",
                "url": "https://chatgpt.com/cdn/assets/app-12345678.js", "resource_type": "Script",
                "encoded_data_length": size, "status": status,
            })
        cache._source("net-1", "local")
        session.finalize_cache_accounting()
        self.assertEqual(session.summary()["download_bytes"], 70)
        self.assertEqual(session.summary()["cache_local_request_count"], 1)

    def test_capture_keeps_cache_reasons_without_changing_transfer_accounting(self):
        cache = Mock()
        cache.snapshot.return_value = {
            "mode": "enabled", "policy": "token_refresh",
            "hits": 1, "stores": 3, "rejected": 2,
            "anonymous_fill_bytes": 13, "anonymous_requests": 1,
            "avoided_upstream_bytes": 400,
            "body_requests": 11, "body_responses": 9, "body_failures": 1,
            "body_timeouts": 1, "body_shutdown_pending": 0,
            "reject_reasons": {"response_vary": 2, "request_failed": 4},
            "error_reasons": {"metadata_timeout": 1},
            "url": "https://private.example/?token=private-secret",
        }
        opened = SimpleNamespace(profile_id="test-profile", debugger_address="127.0.0.1:9222")
        with patch.object(browser_traffic, "_new_roxy_collector", return_value=Mock()), patch.object(
            browser_traffic.record_store, "upsert_row_by", return_value=81,
        ) as save, self.assertLogs("core.browser_traffic", level="INFO") as logs:
            capture = browser_traffic.RoxyTrafficCapture(opened, {"purpose": "token_refresh"})
            capture.set_public_asset_cache(cache)
            capture.record_network({
                "url": "https://example.test/api", "encoded_data_length": 40,
                "request_body_bytes": 7, "status": 200,
            })
            capture.record_network({
                "url": "https://cdn.example.test/app.js", "cache_source": "local",
                "encoded_data_length": 400, "status": 200,
            })
            capture.stop()
            capture.stop()
        save.assert_called_once()
        payload = save.call_args.args[2]
        self.assertEqual(payload["upload_bytes"], 7)
        self.assertEqual(payload["download_bytes"], 53)
        self.assertEqual(payload["total_bytes"], 60)
        self.assertEqual(payload["cache_local_request_count"], 1)
        self.assertEqual(payload["cache_fill_download_bytes"], 13)
        self.assertEqual(payload["cache_avoided_upstream_bytes"], 400)
        diagnostics = payload["public_asset_cache"]
        self.assertEqual(diagnostics["policy"], "token_refresh")
        self.assertEqual(diagnostics["stores"], 3)
        self.assertEqual(diagnostics["reject_reasons"], {"response_vary": 2, "request_failed": 4})
        self.assertEqual(diagnostics["error_reasons"], {"metadata_timeout": 1})
        for key in ("body_requests", "body_responses", "body_failures", "body_timeouts", "body_shutdown_pending"):
            self.assertEqual(diagnostics[key], cache.snapshot.return_value[key])
        encoded = json.dumps(payload) + " ".join(logs.output)
        self.assertNotIn("private-secret", encoded)
        self.assertNotIn("private.example", encoded)
        self.assertIn("公共缓存诊断", " ".join(logs.output))

    def test_persistence_rechecks_fixed_enums_counts_and_reason_allowlist(self):
        with patch.object(browser_traffic.record_store, "upsert_row_by", return_value=82) as save:
            result = browser_traffic.persist_summary(summary_key="cache-reasons", summary={
                "upload_bytes": 3, "download_bytes": 5,
                "public_asset_cache": {
                    "mode": ["private-mode"], "policy": {"private-policy": True},
                    "hits": "4", "stores": -3, "errors": float("inf"),
                    "misses": 2**100, "headers": {"Authorization": "private-secret"},
                    "reject_reasons": {
                        "request_credentials": "7", "response_vary": -3,
                        "body_invalid": {"url": "private-secret"},
                        "https://private.example/?token=private-secret": 10,
                    },
                    "error_reasons": {"command_body": 2, "private-secret": 9},
                },
            })
        self.assertEqual(result, 82)
        payload = save.call_args.args[2]
        self.assertEqual(payload["total_bytes"], 8)
        diagnostics = payload["public_asset_cache"]
        self.assertEqual(diagnostics["mode"], "unknown")
        self.assertEqual(diagnostics["policy"], "unknown")
        self.assertEqual(diagnostics["hits"], 4)
        self.assertEqual(diagnostics["stores"], 0)
        self.assertEqual(diagnostics["errors"], 0)
        self.assertEqual(diagnostics["misses"], 2**63 - 1)
        self.assertEqual(diagnostics["reject_reasons"], {
            "request_credentials": 7, "response_vary": 0, "body_invalid": 0,
        })
        self.assertEqual(diagnostics["error_reasons"], {"command_body": 2})
        encoded = json.dumps(payload)
        for private in ("private-", "private.example", "Authorization", "headers"):
            self.assertNotIn(private, encoded)

    def test_malformed_cache_snapshot_preserves_observed_browser_traffic(self):
        cache = Mock()
        cache.snapshot.return_value = ["private-secret"]
        opened = SimpleNamespace(profile_id="test-profile", debugger_address="127.0.0.1:9222")
        with patch.object(browser_traffic, "_new_roxy_collector", return_value=Mock()), patch.object(
            browser_traffic.record_store, "upsert_row_by", return_value=83,
        ) as save:
            capture = browser_traffic.RoxyTrafficCapture(opened)
            capture.set_public_asset_cache(cache)
            capture.record_network({"url": "https://example.test/api", "encoded_data_length": 30})
            capture.stop()
        payload = save.call_args.args[2]
        self.assertEqual(payload["download_bytes"], 30)
        self.assertEqual(payload["unknown_count"], 1)
        self.assertNotIn("private-secret", json.dumps(payload))

    def test_capture_without_public_cache_keeps_existing_summary_shape(self):
        opened = SimpleNamespace(profile_id="test-profile", debugger_address="127.0.0.1:9222")
        with patch.object(browser_traffic, "_new_roxy_collector", return_value=Mock()), patch.object(
            browser_traffic.record_store, "upsert_row_by", return_value=84,
        ) as save:
            capture = browser_traffic.RoxyTrafficCapture(opened)
            capture.record_network({"url": "https://example.test/api", "encoded_data_length": 30})
            capture.stop()
        payload = save.call_args.args[2]
        self.assertEqual(payload["download_bytes"], 30)
        self.assertNotIn("public_asset_cache", payload)


if __name__ == "__main__":
    unittest.main()
