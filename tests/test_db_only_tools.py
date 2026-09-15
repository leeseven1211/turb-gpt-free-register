import unittest
from unittest.mock import patch

from tools import migrate_collections_to_tables as migration
from tools import test_chatgpt_curl_cffi as token_tool


class DatabaseOnlyToolTests(unittest.TestCase):
    def test_migration_source_requires_postgres_collection(self):
        with patch.object(migration, "load_collection_readonly", return_value=(False, None)), self.assertRaisesRegex(
            RuntimeError, "缺少 PostgreSQL 集合: 注册成功的邮箱.json"
        ):
            migration.load_source("注册成功的邮箱.json", "注册成功的邮箱.json")

    def test_database_token_selector_uses_account_id(self):
        account = {"id": 17, "access_token": "Bearer database-token"}
        with patch.object(token_tool.db, "get_account", return_value=account) as get_account:
            self.assertEqual(token_tool._resolve_database_token(account_id=17), "database-token")
        get_account.assert_called_once_with(17)

    def test_database_token_selector_uses_email(self):
        account = {"id": 17, "access_token": "database-token"}
        with patch.object(token_tool.db, "get_account_by_email", return_value=account) as get_account:
            self.assertEqual(token_tool._resolve_database_token(email=" user@example.test "), "database-token")
        get_account.assert_called_once_with("user@example.test")

    def test_database_token_selector_rejects_missing_token(self):
        with patch.object(token_tool.db, "get_account", return_value={"id": 17, "access_token": ""}), self.assertRaisesRegex(
            RuntimeError, "没有可用 access_token"
        ):
            token_tool._resolve_database_token(account_id=17)

    def test_token_file_interface_is_removed(self):
        with self.assertRaises(SystemExit):
            token_tool.build_parser().parse_args(["--token-file", "注册成功的token.txt"])

    def test_subscriptions_can_still_use_explicit_chatgpt_account_id(self):
        url, path, route = token_tool._build_url(
            "subscriptions", "header.payload.signature", "chatgpt-acct", "-"
        )
        self.assertIn("account_id=chatgpt-acct", url)
        self.assertEqual(path, "/backend-api/subscriptions")
        self.assertEqual(route, path)


if __name__ == "__main__":
    unittest.main()
