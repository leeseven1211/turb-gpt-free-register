"""配置目录只读且不暴露第三方响应中的凭据。"""
import unittest
from unittest.mock import patch

from webui.app import create_app


class ConfigAccountCatalogTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-config-catalog").test_client()
        self.headers = {"X-Auth-Code": "test-config-catalog"}

    def test_account_catalog_filters_private_fields(self):
        with patch("core.icloud_hme_client.list_accounts", return_value=[
            {"id": "a1", "name": "测试账号", "status": "active", "token": "private-test-token", "cookies": {"secret": "value"}},
        ]), patch("core.icloud_hme_client.sync_aliases") as sync:
            result = self.client.get("/api/icloud-hme/accounts", headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()["items"], [{"id": "a1", "label": "测试账号", "status": "active"}])
        sync.assert_not_called()

    def test_catalog_failure_is_safe_and_authentication_is_required(self):
        self.assertEqual(self.client.get("/api/icloud-hme/accounts").status_code, 401)
        with patch("core.icloud_hme_client.list_accounts", side_effect=RuntimeError("private-url-token")):
            result = self.client.get("/api/icloud-hme/accounts", headers=self.headers)
        self.assertEqual(result.status_code, 400)
        self.assertNotIn("private-url-token", result.get_data(as_text=True))
