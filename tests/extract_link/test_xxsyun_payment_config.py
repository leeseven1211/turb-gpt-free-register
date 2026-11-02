"""独立支付配置与只读积分查询契约。"""

import logging
import sys
import types
import unittest
from unittest.mock import Mock, patch

from flask import Flask

from config import schema
from webui import runtime
from webui.routes import integrations


class XXSYUNPaymentConfigurationTests(unittest.TestCase):
    def test_credential_help_explains_native_scope_and_shared_extraction_cdk(self):
        for key in ("EXTRACT_LINK_LEGACY_PAYMENT_CDK", "EXTRACT_LINK_HUANGUANG_PAYMENT_CDK",
                    "EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY", "EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED"):
            with self.subTest(key=key):
                self.assertIn("平台自带", schema.CONFIG_SCHEMA[key].help)
                self.assertIn("独立", schema.CONFIG_SCHEMA[key].help)
        flow = schema.CONFIG_SCHEMA["EXTRACT_LINK_LUMEN_FLOW_CDK"].help
        self.assertIn("提链", flow)
        self.assertIn("仍需", flow)

    def test_provider_sources_default_to_native_and_only_accept_known_sources(self):
        for provider in ("LEGACY", "LUMEN_FLOW", "HUANGUANG"):
            key = f"EXTRACT_LINK_{provider}_AUTO_PAYMENT_SOURCE"
            with self.subTest(key=key):
                self.assertEqual("native", schema.schema_default(key))
                self.assertEqual("xxsyun", schema.validate_value(key, "xxsyun"))
                self.assertEqual(["native", "xxsyun"], [option.value for option in schema.CONFIG_SCHEMA[key].options])
                with self.assertRaises(schema.ConfigValidationError):
                    schema.validate_value(key, "unknown-payment")

    def test_public_configuration_defaults_and_sensitive_key_metadata(self):
        defaults = {
            "API_BASE": "https://upi.xxsyun.xyz/api/v1", "API_KEY": "",
            "REQUEST_TIMEOUT": 30, "POLL_INTERVAL": 10, "CONCURRENCY": 1,
        }
        from config import extract_link

        for suffix, value in defaults.items():
            key = f"EXTRACT_LINK_PAYMENT_XXSYUN_{suffix}"
            with self.subTest(key=key):
                self.assertEqual(value, schema.schema_default(key))
                self.assertTrue(hasattr(extract_link, key))
                self.assertEqual("safe", schema.CONFIG_SCHEMA[key].hot_edit)
        key = "EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY"
        self.assertTrue(schema.CONFIG_SCHEMA[key].secret)
        self.assertEqual("database", schema.CONFIG_SCHEMA[key].storage)
        self.assertEqual("", schema.validate_value(key, ""))
        self.assertEqual("fixture-draft-key", schema.validate_value(key, "fixture-draft-key"))

    def test_limits_reject_zero_and_polling_faster_than_documented_interval(self):
        for suffix, invalid in (("REQUEST_TIMEOUT", 0), ("POLL_INTERVAL", 9), ("CONCURRENCY", 0)):
            with self.subTest(suffix=suffix), self.assertRaises(schema.ConfigValidationError):
                schema.validate_value(f"EXTRACT_LINK_PAYMENT_XXSYUN_{suffix}", invalid)


class XXSYUNPaymentBalanceRoutesTests(unittest.TestCase):
    def setUp(self):
        app = Flask("xxsyun-payment-balance")
        app.register_blueprint(integrations.create_integrations_blueprint(
            runtime.WebUIContext(app, logging.getLogger("xxsyun-payment-balance"))))
        self.client = app.test_client()
        self.query = Mock(return_value={"ok": True, "payment_provider": "xxsyun", "balance": {
            "available_points": 0, "pending_points": None, "used_points": 12, "cost_points": 2,
        }})
        module = types.ModuleType("core.payments.runtime")
        module.query_xxsyun_balance = self.query
        self.modules = patch.dict(sys.modules, {"core.payments.runtime": module})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_saved_draft_and_explicit_clear_are_distinct_and_not_cached(self):
        for body, expected in (({}, None), ({"api_key": "fixture-draft"}, "fixture-draft"), ({"api_key": ""}, "")):
            with self.subTest(body=body):
                self.query.reset_mock()
                response = self.client.post("/api/extract-link/payments/xxsyun/balance", json=body)
                self.assertEqual(200, response.status_code)
                self.assertEqual(0, response.json["balance"]["available_points"])
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.query.assert_called_once_with(api_key=expected)

    def test_invalid_shapes_query_parameters_and_extra_fields_are_rejected(self):
        for body in ([], None, {"api_key": True}, {"api_key": None}, {"api_key": "x" * 513}, {"api_base": "https://other.test"}):
            with self.subTest(body=body):
                response = self.client.post("/api/extract-link/payments/xxsyun/balance", json=body)
                self.assertEqual(400, response.status_code)
                self.assertEqual("config_invalid", response.json["code"])
        response = self.client.post("/api/extract-link/payments/xxsyun/balance?api_key=unaccepted", json={})
        self.assertEqual(400, response.status_code)
        self.query.assert_not_called()

    def test_classified_error_preserves_code_without_returning_upstream_text(self):
        error = RuntimeError("fixture-key private upstream response")
        error.code = "RATE_LIMITED"
        error.retry_after_seconds = 12
        self.query.side_effect = error
        response = self.client.post("/api/extract-link/payments/xxsyun/balance", json={})
        self.assertEqual(400, response.status_code)
        self.assertEqual("RATE_LIMITED", response.json["code"])
        self.assertEqual(12, response.json["retry_after_seconds"])
        self.assertNotIn("fixture-key", response.get_data(as_text=True))
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_unclassified_exception_and_invalid_response_have_distinct_classifications(self):
        for result, code in ((RuntimeError("private fixture"), "query_failed"), ({"ok": False}, "invalid_response")):
            with self.subTest(result=type(result).__name__):
                self.query.side_effect = result if isinstance(result, Exception) else None
                self.query.return_value = result
                response = self.client.post("/api/extract-link/payments/xxsyun/balance", json={})
                self.assertEqual(400, response.status_code)
                self.assertEqual(code, response.json["code"])
