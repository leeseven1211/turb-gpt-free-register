"""幻光备用扫码的运行时配置与只读次数查询。"""

import io
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from core import extract_link_service as service
from core.extract_link_providers.contracts import ProviderJob
from webui import runtime
from webui.routes import integrations


class HuanguangXxsyunServiceTests(unittest.TestCase):
    def setUp(self):
        self.values = {
            "EXTRACT_LINK_ENABLED": True,
            "EXTRACT_LINK_HUANGUANG_ENABLED": True,
            "EXTRACT_LINK_HUANGUANG_API_BASE": "https://huanguang.example.test",
            "EXTRACT_LINK_HUANGUANG_CDK": "fixture-extract-cdk",
            "EXTRACT_LINK_HUANGUANG_PAYMENT_CDK": "fixture-payment-cdk",
            "EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY": "fixture-xxsyun-api-key",
            "EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED": True,
        }
        setting = patch.object(service, "_runtime_setting", side_effect=lambda name, default=None: self.values.get(name, default))
        setting.start()
        self.addCleanup(setting.stop)

    def test_provider_runtime_injects_fallback_without_public_or_other_provider_secret(self):
        config = service._provider_configuration("huanguang").config
        self.assertTrue(config.scan_fallback_enabled)
        self.assertEqual("fixture-xxsyun-api-key", config.xxsyun_api_key)
        self.assertNotIn("fixture-xxsyun-api-key", repr(config))
        self.assertNotIn("fixture-xxsyun-api-key", repr(service.workbench_config()))
        self.values.update({
            "EXTRACT_LINK_LUMEN_FLOW_ENABLED": True,
            "EXTRACT_LINK_LUMEN_FLOW_API_BASE": "https://lumen.example.test",
            "EXTRACT_LINK_LUMEN_FLOW_CDK": "fixture-lumen-cdk",
        })
        other = service._provider_configuration("lumen_flow").config
        self.assertEqual("", other.xxsyun_api_key)
        self.assertFalse(other.scan_fallback_enabled)

    def _quota(self, payload, *, api_key=None, status=200):
        response = SimpleNamespace(status_code=status, json=lambda: payload)
        with patch.object(service._ProviderHTTPTransport, "request", return_value=response) as request:
            result = service.query_huanguang_xxsyun_quota(api_key)
        return result, request

    def test_optional_fallback_key_never_disables_primary_automatic_payment(self):
        self.values.update({
            "EXTRACT_LINK_EXTRACT_ENABLED": True, "EXTRACT_LINK_AUTO_PAYMENT_ENABLED": True,
            "EXTRACT_LINK_HUANGUANG_EXTRACT_ENABLED": True, "EXTRACT_LINK_HUANGUANG_AUTO_PAYMENT_ENABLED": True,
        })
        for key, enabled in [("", True), ("fixture-key", False), ("fixture-key", True)]:
            with self.subTest(key=bool(key), enabled=enabled):
                self.values["EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY"] = key
                self.values["EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED"] = enabled
                self.assertTrue(service._provider_mode_enabled("huanguang", "auto_payment"))

    def test_quota_uses_saved_key_without_requiring_enabled_platform_or_extract_cdk(self):
        self.values["EXTRACT_LINK_ENABLED"] = False
        self.values["EXTRACT_LINK_HUANGUANG_CDK"] = ""
        result, request = self._quota({"remainingUses": 0, "totalUses": None, "reservedUses": None})
        self.assertEqual({"ok": True, "remainingUses": 0, "totalUses": None, "reservedUses": None}, result)
        self.assertEqual(("POST", "/api/xxsyun-quota"), request.call_args.args)
        self.assertEqual({"api_key": "fixture-xxsyun-api-key"}, request.call_args.kwargs["json"])

    def test_quota_draft_key_does_not_change_saved_setting_or_subtract_reservations(self):
        result, request = self._quota({"remainingUses": 2, "totalUses": 25, "reservedUses": 3, "api_key": "raw-secret"}, api_key="draft-api-key")
        self.assertEqual({"ok": True, "remainingUses": 2, "totalUses": 25, "reservedUses": 3}, result)
        self.assertEqual({"api_key": "draft-api-key"}, request.call_args.kwargs["json"])
        self.assertEqual("fixture-xxsyun-api-key", self.values["EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY"])

    def test_explicit_empty_key_does_not_reuse_saved_secret_or_contact_platform(self):
        with patch.object(service._ProviderHTTPTransport, "request") as request:
            with self.assertRaisesRegex(ValueError, "未配置"):
                service.query_huanguang_xxsyun_quota("")
        request.assert_not_called()

    def test_quota_urllib_fallback_posts_json_with_explicit_content_type(self):
        response = io.BytesIO(b'{"remainingUses": 4}')
        with patch.object(service, "curl_requests", None), patch.object(service, "urlopen", return_value=response) as send:
            result = service.query_huanguang_xxsyun_quota()
        sent_request = send.call_args.args[0]
        self.assertEqual("application/json", sent_request.get_header("Content-type"))
        self.assertEqual("https://huanguang.example.test/api/xxsyun-quota", sent_request.full_url)
        self.assertEqual(4, result["remainingUses"])

    def test_quota_invalid_or_failed_response_never_exposes_raw_text_or_secret(self):
        invalid = [
            {"error": "fixture-xxsyun-api-key"}, {"remainingUses": True},
            {"remainingUses": -1}, {"remainingUses": "0"}, {"remainingUses": 2**53},
            {"remainingUses": 2, "totalUses": -1}, {"remainingUses": 2, "reservedUses": False},
            {"ok": False, "remainingUses": 0, "error": "fixture-xxsyun-api-key"},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError) as error:
                    self._quota(payload)
                self.assertNotIn("fixture-xxsyun-api-key", str(error.exception))
        with self.assertRaises(ValueError) as error:
            self._quota({"error": "raw-secret"}, status=502)
        self.assertNotIn("raw-secret", str(error.exception))

    def test_safe_summary_allows_only_known_xxsyun_and_fallback_states(self):
        job = ProviderJob(summary={
            "xxsyun_status": "awaiting_worker", "scan_fallback_status": "submitted",
            "scan_fallback_provider": "xxsyun", "xxsyun_polling": True, "scan_fallback_polling": False,
            "fallback_xxsyun_api_key": "raw-secret",
        })
        projected = service._safe_provider_job_state(job, mode="auto_payment")["summary"]
        self.assertEqual({key: value for key, value in job.summary.items() if key != "fallback_xxsyun_api_key"}, projected)
        unsafe = ProviderJob(summary={"xxsyun_status": "raw-secret", "scan_fallback_provider": "raw-secret"})
        self.assertEqual({}, service._safe_provider_job_state(unsafe, mode="auto_payment")["summary"])


class HuanguangXxsyunQuotaRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask("huanguang-xxsyun-quota")
        context = runtime.WebUIContext(app, logging.getLogger("huanguang-xxsyun-quota"))
        app.register_blueprint(integrations.create_integrations_blueprint(context))
        self.client = app.test_client()

    def test_saved_draft_and_explicit_clear_are_distinct_and_never_cached(self):
        for body, expected in [({}, None), ({"api_key": "draft-key"}, "draft-key"), ({"api_key": ""}, "")]:
            with self.subTest(body=body), patch.object(service, "query_huanguang_xxsyun_quota", return_value={
                "ok": True, "remainingUses": 0, "totalUses": None, "reservedUses": None,
            }, create=True) as query:
                response = self.client.post("/api/extract-link/huanguang/xxsyun-quota", json=body)
                self.assertEqual(200, response.status_code)
                self.assertEqual(0, response.json["remainingUses"])
                self.assertIn("no-store", response.headers["Cache-Control"])
                query.assert_called_once_with(api_key=expected)

    def test_invalid_json_shapes_are_rejected_before_query(self):
        for body in ([], ["secret"], None, {"api_key": True}, {"api_key": None}, {"api_key": "x" * 513}, {"api_base": "https://bad.example"}):
            with self.subTest(body=body), patch.object(service, "query_huanguang_xxsyun_quota", create=True) as query:
                response = self.client.post("/api/extract-link/huanguang/xxsyun-quota", json=body)
                self.assertEqual(400, response.status_code)
                self.assertIn("no-store", response.headers["Cache-Control"])
                query.assert_not_called()

    def test_failure_never_returns_exception_text_or_key(self):
        with patch.object(service, "query_huanguang_xxsyun_quota", side_effect=RuntimeError("raw-secret upstream body"), create=True):
            response = self.client.post("/api/extract-link/huanguang/xxsyun-quota", json={})
        self.assertEqual(400, response.status_code)
        self.assertFalse(response.json["ok"])
        self.assertNotIn("raw-secret", response.get_data(as_text=True))
        self.assertIn("no-store", response.headers["Cache-Control"])
