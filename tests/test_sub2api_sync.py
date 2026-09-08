# -*- coding: utf-8 -*-
import json
import unittest
from unittest.mock import Mock, patch

from core import record_store
from core.sub2api_client import export_configured_accounts
from core.sub2api_sync import (
    build_account_sync_payload,
    build_codex_filename,
    build_sub2api_status,
    merge_sync_metadata,
)
from tests.support_pg import PostgresTestCase


class Sub2ApiSyncMappingTests(unittest.TestCase):
    @patch("core.sub2api_client.requests.get")
    def test_export_configured_accounts_reads_complete_account_list(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {
            "code": 0,
            "data": {"accounts": [{"name": "one@example.com", "credentials": {"refresh_token": "rt"}}]},
        }
        get.return_value = response

        from core.sub2api_client import export_configured_accounts

        result = export_configured_accounts()

        self.assertEqual(result[0]["name"], "one@example.com")
        self.assertIn("x-api-key", get.call_args.kwargs["headers"])
        self.assertIn("/api/v1/admin/accounts/data", get.call_args.args[0])

    def test_build_sub2api_status_extracts_token_revoked_401(self):
        self.assertEqual(
            build_sub2api_status({
                "status": "error",
                "error_message": "Token revoked (401): invalidated oauth token",
            }),
            {"sub2api_status": "error", "sub2api_http_status": 401},
        )

    def test_build_sub2api_status_clears_old_http_status_when_active(self):
        self.assertEqual(
            build_sub2api_status({"status": "active", "error_message": ""}),
            {"sub2api_status": "active", "sub2api_http_status": None},
        )

    def test_build_sub2api_status_does_not_overwrite_when_export_omits_list_status(self):
        self.assertEqual(build_sub2api_status({"name": "export-only@example.test"}), {})

    def test_build_account_sync_payload_marks_new_account_as_email_butler(self):
        payload = build_account_sync_payload(
            {
                "id": 41,
                "name": "new@example.com",
                "platform": "openai",
                "type": "oauth",
                "credentials": {
                    "email": "new@example.com",
                    "access_token": "access-token",
                    "chatgpt_user_id": "user-41",
                    "chatgpt_account_id": "account-41",
                    "plan_type": "free",
                    "expires_at": "2026-10-01T00:00:00Z",
                },
            },
            existing=None,
        )

        self.assertEqual(payload["email"], "new@example.com")
        self.assertEqual(payload["email_source"], "email_butler")
        self.assertEqual(payload["access_token"], "access-token")
        self.assertEqual(payload["user_id"], "user-41")
        self.assertEqual(payload["plan_type"], "free")
        self.assertEqual(payload["registration_proxy_region"], "US")
        self.assertTrue(payload["extra"]["sub2api_account_id"] == 41)
        self.assertTrue(payload["extra"]["account_password_missing"])
        self.assertTrue(payload["extra"]["totp_missing"])

    def test_build_account_sync_payload_does_not_overwrite_local_sensitive_fields(self):
        existing = {
            "id": 7,
            "email": "existing@example.com",
            "email_source": "icloud_hide",
            "password": "mailbox-password",
            "totp_secret": "LOCAL-TOTP",
            "registration_proxy_region": "JP",
            "extra_json": json.dumps({"account_password": "openai-password", "local_note": "keep"}),
        }
        payload = build_account_sync_payload(
            {
                "id": 99,
                "name": "existing@example.com",
                "platform": "openai",
                "type": "oauth",
                "credentials": {
                    "email": "existing@example.com",
                    "access_token": "new-access-token",
                    "chatgpt_user_id": "user-99",
                    "plan_type": "plus",
                },
            },
            existing=existing,
        )

        self.assertNotIn("email_source", payload)
        self.assertNotIn("password", payload)
        self.assertNotIn("totp_secret", payload)
        self.assertEqual(payload["registration_proxy_region"], "US")
        self.assertEqual(payload["access_token"], "new-access-token")
        self.assertEqual(payload["extra"]["local_note"], "keep")
        self.assertEqual(payload["extra"]["account_password"], "openai-password")
        self.assertFalse(payload["extra"]["account_password_missing"])
        self.assertFalse(payload["extra"]["totp_missing"])

    def test_build_codex_filename_is_stable_for_same_email_and_plan(self):
        self.assertEqual(
            build_codex_filename("new@example.com", "free"),
            "codex-new@example.com-free.json",
        )

    def test_merge_sync_metadata_preserves_existing_json(self):
        merged = merge_sync_metadata(
            json.dumps({"local_note": "keep", "account_password": "secret"}),
            {"sub2api_account_id": 41, "import_source": "sub2api"},
        )
        self.assertEqual(merged["local_note"], "keep")
        self.assertEqual(merged["account_password"], "secret")
        self.assertEqual(merged["sub2api_account_id"], 41)


class Sub2ApiSyncStorageTests(PostgresTestCase):
    def test_sync_repairs_identity_sequence_before_inserting_new_account(self):
        self.seed(record_store.ACCOUNTS, [{
            "id": 455,
            "email": "existing@example.test",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }])

        from core.sub2api_sync import sync_sub2api_records

        raw = {
            "name": "new@example.test",
            "platform": "openai",
            "type": "oauth",
            "credentials": {
                "email": "new@example.test",
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "chatgpt_account_id": "account-new",
                "plan_type": "free",
            },
        }
        with patch("core.sub2api_sync.db.list_codex_accounts", return_value=[]):
            result = sync_sub2api_records([raw])

        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["accounts_created"], 1)
        stored = record_store.get_row_by(record_store.ACCOUNTS, "email", "new@example.test", lower=True)
        self.assertIsNotNone(stored)
        self.assertGreater(int(stored["id"]), 455)
        self.assertEqual(stored["registration_proxy_region"], "US")

    def test_sync_persists_sub2api_401_on_codex_credential(self):
        from core.sub2api_sync import sync_sub2api_records

        raw = {
            "name": "revoked@example.test",
            "platform": "openai",
            "type": "oauth",
            "status": "error",
            "error_message": "Token revoked (401): invalidated oauth token",
            "credentials": {
                "email": "revoked@example.test",
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "chatgpt_account_id": "account-revoked",
                "plan_type": "free",
            },
        }
        with patch("core.sub2api_sync.db.list_codex_accounts", return_value=[]):
            result = sync_sub2api_records([raw])

        self.assertEqual(result["failed_count"], 0)
        stored = record_store.get_row_by(
            record_store.CODEX_CREDENTIALS,
            "filename",
            "codex-revoked@example.test-free.json",
        )
        self.assertEqual(stored["sub2api_status"], "error")
        self.assertEqual(stored["sub2api_http_status"], 401)


if __name__ == "__main__":
    unittest.main()
