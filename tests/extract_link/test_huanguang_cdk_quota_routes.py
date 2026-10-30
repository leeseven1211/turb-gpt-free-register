"""幻光已保存 CDK 额度的只读查询接口。"""

import logging
import unittest
from unittest.mock import patch

from flask import Flask

from core.extract_link import service as service
from webui import runtime
from webui.routes import integrations


class HuanguangCdkQuotaRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask("huanguang-cdk-quota")
        context = runtime.WebUIContext(app, logging.getLogger("huanguang-cdk-quota"))
        app.register_blueprint(integrations.create_integrations_blueprint(context))
        self.client = app.test_client()
        self.url = "/api/extract-link/huanguang/cdk-quota"

    def test_queries_saved_configuration_without_arguments_and_never_caches(self):
        quota = {
            "ok": True,
            "extraction": {"required": True, "remaining": 0, "reserved": 0, "active": True},
            "payment": {"required": True, "remaining": 5, "reserved": 2, "active": True},
        }
        with patch.object(service, "query_huanguang_cdk_quota", return_value=quota, create=True) as query:
            response = self.client.get(self.url)
        query.assert_called_once_with()
        self.assertEqual(200, response.status_code)
        self.assertEqual(quota, response.json)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_does_not_accept_draft_credentials_or_an_api_base(self):
        for args in ({"cdk": "draft-secret"}, {"api_key": "draft-secret"}, {"api_base": "https://bad.example"}):
            with self.subTest(args=args), patch.object(service, "query_huanguang_cdk_quota", create=True) as query:
                response = self.client.get(self.url, query_string=args)
                query.assert_not_called()
                self.assertEqual(400, response.status_code)
                self.assertNotIn("draft-secret", response.get_data(as_text=True))
                self.assertIn("no-store", response.headers["Cache-Control"])

    def test_does_not_accept_a_get_body_or_a_post(self):
        with patch.object(service, "query_huanguang_cdk_quota", create=True) as query:
            response = self.client.get(self.url, json={"cdk": "draft-secret"})
            query.assert_not_called()
            self.assertEqual(400, response.status_code)
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.assertEqual(405, self.client.post(self.url, json={}).status_code)

    def test_unknown_or_missing_configuration_is_unavailable_instead_of_zero(self):
        for error in (ValueError("missing secret-cdk"), RuntimeError("upstream secret-cdk https://private.example")):
            with self.subTest(error=type(error).__name__), patch.object(
                service, "query_huanguang_cdk_quota", side_effect=error, create=True,
            ):
                response = self.client.get(self.url)
                self.assertEqual(503, response.status_code)
                self.assertEqual({"ok": False, "error": "无法确认幻光 CDK 剩余次数，请检查已保存的 CDK 或稍后重试"}, response.json)
                self.assertNotIn("secret-cdk", response.get_data(as_text=True))
                self.assertNotIn("remaining", response.json)
                self.assertIn("no-store", response.headers["Cache-Control"])

    def test_unsuccessful_query_result_is_not_reported_as_available(self):
        with patch.object(service, "query_huanguang_cdk_quota", return_value={"ok": False}, create=True):
            response = self.client.get(self.url)
        self.assertEqual(503, response.status_code)
        self.assertFalse(response.json["ok"])
        self.assertIn("no-store", response.headers["Cache-Control"])
