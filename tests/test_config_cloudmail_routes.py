# -*- coding: utf-8 -*-
import unittest
from unittest.mock import call, patch

from config.schema import ConfigValidationError
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class ConfigCloudMailRouteTests(PostgresTestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"

    @patch("webui.routes.config.config_editor.update_config")
    @patch("core.cloudmail_client.requests.post")
    def test_token_route_uses_unified_config_writer_and_returns_revision(
        self, post, update_config
    ):
        response = post.return_value
        response.status_code = 200
        response.json.return_value = {"code": 200, "data": {"token": "token-abc"}}
        update_config.return_value = {
            "env_updated": ["CLOUDMAIL_AUTH_TOKEN", "CLOUDMAIL_API_BASE"],
            "reloaded": True,
            "config_revision": 12,
        }

        result = self.client.post("/api/cloudmail/gen-token", json={
            "api_base": "https://mail.example.com",
            "admin_email": "admin@example.com",
            "password": "pass-123",
            "path": "/api/public/genToken",
        })

        self.assertEqual(200, result.status_code)
        update_config.assert_called_once_with({
            "CLOUDMAIL_AUTH_TOKEN": "token-abc",
            "CLOUDMAIL_API_BASE": "https://mail.example.com",
            "CLOUDMAIL_ADMIN_EMAIL": "admin@example.com",
            "CLOUDMAIL_PASSWORD": "pass-123",
            "CLOUDMAIL_TOKEN_PATH": "/api/public/genToken",
        })
        self.assertEqual(12, result.get_json()["config_revision"])
        self.assertTrue(result.get_json()["reloaded"])

    @patch("webui.routes.config.config_editor.update_config")
    @patch("core.cloudmail_client.requests.post")
    def test_token_route_returns_schema_validation_errors_without_success(
        self, post, update_config
    ):
        response = post.return_value
        response.status_code = 200
        response.json.return_value = {"code": 200, "data": {"token": "token-abc"}}
        update_config.side_effect = ConfigValidationError({
            "CLOUDMAIL_AUTH_TOKEN": "未定义或不可编辑的配置字段",
        })

        result = self.client.post("/api/cloudmail/gen-token", json={
            "api_base": "https://mail.example.com",
            "admin_email": "admin@example.com",
            "password": "pass-123",
        })

        self.assertEqual(400, result.status_code)
        self.assertFalse(result.get_json()["ok"])
        self.assertEqual(
            "未定义或不可编辑的配置字段",
            result.get_json()["fields"]["CLOUDMAIL_AUTH_TOKEN"],
        )

    @patch("webui.routes.config.config_editor.update_config")
    @patch("core.cloudmail_client.fetch_domains", return_value=["mail.example"])
    def test_domains_route_versions_credentials_and_domain_cache_separately(
        self, fetch_domains, update_config
    ):
        update_config.side_effect = [
            {
                "env_updated": ["CLOUDMAIL_API_BASE"],
                "reloaded": True,
                "config_revision": 20,
            },
            {
                "env_updated": ["CLOUDMAIL_DOMAINS"],
                "reloaded": True,
                "config_revision": 21,
            },
        ]

        result = self.client.post("/api/cloudmail/domains", json={
            "api_base": "https://mail.example.com",
            "admin_email": "admin@example.com",
            "password": "pass-123",
            "token": "token-abc",
        })

        self.assertEqual(200, result.status_code)
        self.assertEqual(21, result.get_json()["config_revision"])
        self.assertEqual([
            call({
                "CLOUDMAIL_API_BASE": "https://mail.example.com",
                "CLOUDMAIL_ADMIN_EMAIL": "admin@example.com",
                "CLOUDMAIL_PASSWORD": "pass-123",
                "CLOUDMAIL_AUTH_TOKEN": "token-abc",
            }),
            call({"CLOUDMAIL_DOMAINS": ["mail.example"]}),
        ], update_config.call_args_list)
        fetch_domains.assert_called_once_with(force=True)


if __name__ == "__main__":
    unittest.main()
