"""幻光额度查询的安全分类与单项查询回归。"""

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from core import extract_link_service as service
from core.extract_link_providers.contracts import ProviderConfig, ProviderError
from core.extract_link_providers.huanguang import HuanguangProvider
from webui import runtime
from webui.routes import integrations


class HuanguangQuotaQueryTests(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "EXTRACT_LINK_ENABLED": False,
            "EXTRACT_LINK_HUANGUANG_ENABLED": False,
            "EXTRACT_LINK_HUANGUANG_API_BASE": "https://quota.example.test",
            "EXTRACT_LINK_HUANGUANG_CDK": "fixture-extraction-secret",
            "EXTRACT_LINK_HUANGUANG_PAYMENT_CDK": "fixture-payment-secret",
            "EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY": "fixture-key-secret",
        }
        setting = patch.object(service, "_runtime_setting", side_effect=lambda name, default=None: self.settings.get(name, default))
        setting.start()
        self.addCleanup(setting.stop)

    def _response(self, payload, status=200):
        return SimpleNamespace(status_code=status, json=lambda: payload)

    def _assert_error(self, callback, code):
        with self.assertRaises((ProviderError, ValueError)) as caught:
            callback()
        self.assertEqual(code, getattr(caught.exception, "error_code", None))
        self.assertNotIn("fixture-", str(caught.exception))
        self.assertNotIn("private-body", str(caught.exception))
        self.assertIsNone(caught.exception.__context__)
        return caught.exception

    def test_real_xxsyun_502_key_rejection_is_classified_without_returning_upstream_body(self):
        response = self._response({"error": "API Key 无效或已失效", "error_code": "request_failed"}, 502)
        with patch.object(service._ProviderHTTPTransport, "request", return_value=response):
            error = self._assert_error(service.query_huanguang_xxsyun_quota, "key_invalid")
        self.assertIn("无效或已失效", str(error))

    def test_xxsyun_unknown_502_is_not_mislabeled_as_invalid_key(self):
        with patch.object(service._ProviderHTTPTransport, "request", return_value=self._response({"error": "private-body fixture-key-secret"}, 502)):
            self._assert_error(service.query_huanguang_xxsyun_quota, "upstream_http_error")

    def test_xxsyun_rate_limit_network_and_invalid_response_are_distinct(self):
        for status, payload, code in (
            (429, {"error": "private-body"}, "rate_limited"),
            (200, None, "invalid_response"),
            (200, {"remainingUses": -1}, "invalid_response"),
            (200, {"ok": False, "error": "private-body"}, "query_failed"),
        ):
            with self.subTest(code=code, payload=payload), patch.object(service._ProviderHTTPTransport, "request", return_value=self._response(payload, status)):
                self._assert_error(service.query_huanguang_xxsyun_quota, code)
        for error in (TimeoutError("private-body fixture-key-secret"), ConnectionError("private-body")):
            with self.subTest(error=type(error).__name__), patch.object(service._ProviderHTTPTransport, "request", side_effect=error):
                self._assert_error(service.query_huanguang_xxsyun_quota, "network_error")

    def test_xxsyun_invalid_json_is_classified_without_exception_chain(self):
        def invalid_json():
            raise ValueError("private-body fixture-key-secret")
        with patch.object(service._ProviderHTTPTransport, "request", return_value=SimpleNamespace(status_code=200, json=invalid_json)):
            self._assert_error(service.query_huanguang_xxsyun_quota, "invalid_response")

    def test_xxsyun_missing_key_and_invalid_api_base_never_contact_upstream(self):
        with patch.object(service._ProviderHTTPTransport, "request") as send:
            self._assert_error(lambda: service.query_huanguang_xxsyun_quota(""), "key_missing")
            self.settings["EXTRACT_LINK_HUANGUANG_API_BASE"] = "invalid-url"
            self._assert_error(service.query_huanguang_xxsyun_quota, "config_invalid")
        send.assert_not_called()

    def test_saved_single_cdk_queries_are_independent_of_other_cdk_and_enable_switches(self):
        for kind, missing_setting, expected_path, payload, remaining in (
            ("extraction", "EXTRACT_LINK_HUANGUANG_PAYMENT_CDK", "/api/cdk-status", {"ok": True, "remaining_uses": 3, "enabled": True}, 3),
            ("payment", "EXTRACT_LINK_HUANGUANG_CDK", "/api/chongyun-cdk-status", {"remainingUses": 0, "status": "ACTIVE"}, 0),
        ):
            with self.subTest(kind=kind):
                original = self.settings[missing_setting]
                self.settings[missing_setting] = ""
                with patch.object(service._ProviderHTTPTransport, "request", return_value=self._response(payload)) as send:
                    result = service.query_huanguang_saved_cdk_quota(kind)
                self.settings[missing_setting] = original
                self.assertEqual({"ok": True, "quota": {"required": True, "remaining": remaining, "reserved": None, "active": True}}, result)
                self.assertEqual(("POST", expected_path), send.call_args.args)
                self.assertEqual(1, send.call_count)

    def test_missing_single_cdk_does_not_use_other_cdk(self):
        self.settings["EXTRACT_LINK_HUANGUANG_PAYMENT_CDK"] = ""
        with patch.object(service._ProviderHTTPTransport, "request") as send:
            self._assert_error(lambda: service.query_huanguang_saved_cdk_quota("payment"), "cdk_missing")
        send.assert_not_called()

    def test_cdk_queries_classify_known_rejection_and_unknown_http_failures(self):
        config = ProviderConfig("huanguang", "https://quota.example.test", "fixture-extraction-secret")
        for status, payload, code in (
            (400, {"error": "CDK 无效或不存在"}, "cdk_invalid"),
            (502, {"error": "private-body fixture-extraction-secret"}, "upstream_http_error"),
            (429, {"error": "private-body"}, "rate_limited"),
            (200, {"ok": True, "remaining_uses": -1}, "invalid_response"),
        ):
            with self.subTest(code=code):
                transport = SimpleNamespace(request=lambda *args, **kwargs: self._response(payload, status))
                provider = HuanguangProvider(config, transport)
                self._assert_error(lambda: provider.query_cdk_quota(config.cdk), code)


class HuanguangSingleQuotaRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask("huanguang-single-quota")
        context = runtime.WebUIContext(app, logging.getLogger("huanguang-single-quota"))
        app.register_blueprint(integrations.create_integrations_blueprint(context))
        self.client = app.test_client()
        self.url = "/api/extract-link/huanguang/cdk-quota/"

    def test_single_cdk_route_returns_only_the_requested_quota_and_disables_caching(self):
        result = {"ok": True, "quota": {"required": True, "remaining": 0, "reserved": None, "active": True}}
        for kind in ("extraction", "payment"):
            with self.subTest(kind=kind), patch.object(service, "query_huanguang_saved_cdk_quota", return_value=result, create=True) as query:
                response = self.client.get(self.url + kind)
                self.assertEqual(200, response.status_code)
                self.assertEqual(result, response.json)
                self.assertIn("no-store", response.headers["Cache-Control"])
                query.assert_called_once_with(kind)

    def test_single_cdk_route_rejects_unknown_kind_parameters_and_all_get_bodies(self):
        cases = (
            ("unknown", {}),
            ("payment", {"query_string": {"cdk": "fixture-draft-secret"}}),
            ("payment", {"data": b"fixture-draft-secret"}),
            ("payment", {"json": {}}),
        )
        for kind, options in cases:
            with self.subTest(kind=kind, options=options), patch.object(service, "query_huanguang_saved_cdk_quota", create=True) as query:
                response = self.client.get(self.url + kind, **options)
                self.assertEqual(400, response.status_code)
                self.assertEqual("config_invalid", response.json["error_code"])
                self.assertEqual(response.json["error_code"], response.json["code"])
                query.assert_not_called()

    def test_unexpected_single_query_failure_is_safe_and_classified(self):
        with patch.object(service, "query_huanguang_saved_cdk_quota", side_effect=RuntimeError("private-body fixture-secret"), create=True):
            response = self.client.get(self.url + "payment")
        self.assertEqual(503, response.status_code)
        self.assertEqual("query_failed", response.json["error_code"])
        self.assertEqual(response.json["error_code"], response.json["code"])
        self.assertNotIn("private-body", response.get_data(as_text=True))

    def test_classified_xxsyun_failure_survives_route_boundary(self):
        response = SimpleNamespace(status_code=502, json=lambda: {"error": "API Key 无效或已失效", "error_code": "request_failed"})
        settings = {"EXTRACT_LINK_HUANGUANG_API_BASE": "https://quota.example.test", "EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY": "fixture-key-secret"}
        with patch.object(service, "_runtime_setting", side_effect=lambda name, default=None: settings.get(name, default)), patch.object(service._ProviderHTTPTransport, "request", return_value=response):
            result = self.client.post("/api/extract-link/huanguang/xxsyun-quota", json={})
        self.assertEqual(400, result.status_code)
        self.assertEqual("key_invalid", result.json["error_code"])
        self.assertEqual("key_invalid", result.json["code"])
        self.assertIn("无效或已失效", result.json["error"])
