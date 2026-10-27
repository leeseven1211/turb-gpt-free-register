"""配置目录只读且不暴露第三方响应中的凭据。"""
import unittest
from unittest.mock import patch

from webui.app import create_app


class ConfigAccountCatalogTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-config-catalog").test_client()
        self.headers = {"X-Auth-Code": "test-config-catalog"}

    def test_account_catalog_is_retired_without_loading_remote_accounts(self):
        with patch("core.icloud_hme_client.list_accounts", return_value=[
            {"id": "a1", "name": "测试账号", "status": "active", "token": "private-test-token", "cookies": {"secret": "value"}},
        ]) as accounts, patch("core.icloud_hme_client.sync_aliases") as sync:
            result = self.client.get("/api/icloud-hme/accounts", headers=self.headers)
        self.assertEqual(result.status_code, 410)
        self.assertEqual(result.get_json()["reason_code"], "email_management_managed_by_service")
        self.assertNotIn("private-test-token", result.get_data(as_text=True))
        accounts.assert_not_called()
        sync.assert_not_called()

    def test_catalog_failure_is_safe_and_authentication_is_required(self):
        self.assertEqual(self.client.get("/api/icloud-hme/accounts").status_code, 401)
        with patch("core.icloud_hme_client.list_accounts", side_effect=RuntimeError("private-url-token")):
            result = self.client.get("/api/icloud-hme/accounts", headers=self.headers)
        self.assertEqual(result.status_code, 410)
        self.assertNotIn("private-url-token", result.get_data(as_text=True))
