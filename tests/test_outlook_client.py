# -*- coding: utf-8 -*-
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import outlook_client


class OutlookClientContextTests(unittest.TestCase):
    def setUp(self):
        outlook_client._CONTEXT_CACHE.clear()

    @patch("core.db.get_account_by_email")
    @patch("core.db.get_outlook_by_email", return_value=None)
    def test_restores_context_from_registered_account_after_pool_missing(
        self,
        get_outlook_by_email,
        get_account_by_email,
    ):
        get_account_by_email.return_value = {
            "email": "Registered@outlook.test",
            "email_source": "outlook",
            "password": "mail-password",
            "client_id": "client-id",
            "refresh_token": "refresh-token",
            "recovery_email": "recovery@example.test",
            "recovery_code": "recovery-code",
        }

        account = outlook_client.get_account_context("  registered@OUTLOOK.test ")

        self.assertIsNotNone(account)
        self.assertEqual(account.email, "Registered@outlook.test")
        self.assertEqual(account.password, "mail-password")
        self.assertEqual(account.client_id, "client-id")
        self.assertEqual(account.refresh_token, "refresh-token")
        self.assertEqual(account.recovery_email, "recovery@example.test")
        self.assertEqual(account.recovery_code, "recovery-code")

    @patch("core.db.get_account_by_email", return_value={
        "email": "registered@outlook.test",
        "email_source": "cloudmail",
        "password": "saved-password",
        "client_id": "saved-client",
        "refresh_token": "saved-refresh",
    })
    @patch("core.db.get_outlook_by_email", return_value={
        "email": "registered@outlook.test",
        "password": "pool-password",
        "client_id": "pool-client",
        "refresh_token": "pool-refresh",
    })
    def test_non_outlook_registered_source_does_not_read_outlook_pool(
        self,
        get_outlook_by_email,
        get_account_by_email,
    ):
        self.assertIsNone(outlook_client.get_account_context("registered@outlook.test"))

        get_outlook_by_email.assert_called_once_with("registered@outlook.test")
        get_account_by_email.assert_called_once_with("registered@outlook.test")


class OutlookExplicitImportTests(unittest.TestCase):
    def test_pick_account_does_not_auto_import_a_file(self):
        with patch("core.db.claim_next_outlook", return_value=None), patch(
            "core.db.outlook_pool_summary", return_value={"available": 0}
        ), patch("core.outlook_client.import_outlook_from_file") as importer:
            with self.assertRaises(outlook_client.OutlookClientError):
                outlook_client.pick_account()
        importer.assert_not_called()

    def test_file_import_is_explicit_and_does_not_rewrite_source(self):
        source = (
            "first@example.test----password----client----refresh\n"
            "second@example.test====password2====client2====refresh2\n"
        ).encode()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "outlook.txt"
            path.write_bytes(source)
            with patch("core.db.import_outlook_accounts", return_value=(2, 0)) as importer:
                result = outlook_client.import_outlook_from_file(path)
            self.assertEqual(result, (2, 0))
            self.assertEqual(path.read_bytes(), source)
        importer.assert_called_once_with([
            {"email": "first@example.test", "password": "password", "client_id": "client", "refresh_token": "refresh"},
            {"email": "second@example.test", "password": "password2", "client_id": "client2", "refresh_token": "refresh2"},
        ])

    def test_file_import_requires_a_path(self):
        with self.assertRaises(TypeError):
            outlook_client.import_outlook_from_file(None)


if __name__ == "__main__":
    unittest.main()
