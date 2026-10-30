# -*- coding: utf-8 -*-
import json
import threading
import time
import unittest
from unittest.mock import Mock, patch

from config import sub2api as sub2api_config
from core.storage import records as record_store
from core.integrations.sub2api.client import export_configured_accounts
from core.integrations.sub2api.sync import build_account_sync_payload, build_codex_filename, build_sub2api_status, merge_sync_metadata
from tests.support_pg import PostgresTestCase


class Sub2ApiSyncMappingTests(unittest.TestCase):
    @patch("core.integrations.sub2api.client.requests.get")
    def test_export_configured_accounts_reads_complete_account_list(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {
            "code": 0,
            "data": {"accounts": [{"name": "one@example.com", "credentials": {"refresh_token": "rt"}}]},
        }
        get.return_value = response

        from core.integrations.sub2api.client import export_configured_accounts

        with patch.object(
            sub2api_config,
            "SUB2API_API_BASE",
            "http://example.test",
            create=True,
        ), patch.object(
            sub2api_config,
            "SUB2API_API_KEY",
            "test-key",
            create=True,
        ):
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
    def _sync_record(self, email, **extra):
        return {
            "name": email, "platform": "openai", "type": "oauth",
            "credentials": {"email": email, "access_token": "synthetic-sync-token", "plan_type": "free"},
            **extra,
        }

    def test_new_sync_accounts_inherit_parent_and_full_address_ledger_failures(self):
        from core.integrations.sub2api.sync import sync_sub2api_records

        parent_id = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "invalid-parent@example.test", "account_id": "test-subaccount",
            "status": "used", "email_invalid": True, "email_invalid_reason": "母邮箱失效",
            "email_invalid_source": "manual", "email_invalid_at": "2026-10-25T10:00:00Z",
        })
        child = "valid-parent+invalid-child@example.test"
        record_store.insert_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, {
            "address": child, "address_norm": child, "source": "icloud_hide",
            "parent_kind": record_store.ICLOUD_HIDE_POOL.name, "parent_id": parent_id,
            "parent_address": "invalid-parent@example.test", "inbox_profile_id": 1,
            "strategy": "plus_tag", "tag": "invalid-child", "acquisition_id": "test-sync-ledger",
            "owner_kind": "registration_root", "owner_id": "test-sync-root", "state": "used",
            "email_invalid": True, "email_invalid_reason": "完整地址失效",
            "email_invalid_source": "manual", "email_invalid_at": "2026-10-25T11:00:00Z",
        })
        with patch("core.integrations.sub2api.sync.db.list_codex_accounts", return_value=[]):
            result = sync_sub2api_records([
                self._sync_record("invalid-parent@example.test", email_invalid=False),
                self._sync_record(child, email_invalid=False),
            ], email_source="icloud_hide", sync_codex=False)
        self.assertEqual(0, result["failed_count"])
        self.assertEqual(2, result["accounts_created"])
        for email, reason in (("invalid-parent@example.test", "母邮箱失效"), (child, "完整地址失效")):
            with self.subTest(email=email):
                row = record_store.get_row_by(record_store.ACCOUNTS, "email", email)
                self.assertIs(row["email_invalid"], True)
                self.assertEqual(reason, row["email_invalid_reason"])
                self.assertEqual(email, row["email_invalid_email"])

    def test_sync_existing_account_preserves_local_email_fact_and_ignores_external_marker(self):
        from core.integrations.sub2api.sync import sync_sub2api_records

        for invalid in (False, True):
            email = f"existing-{invalid}@example.test"
            record_store.insert_row(record_store.ACCOUNTS, {
                "email": email, "email_source": "outlook", "email_invalid": invalid,
                "email_invalid_reason": "本地依据" if invalid else None,
                "email_invalid_source": "manual", "email_invalid_at": "2026-10-25T10:00:00Z",
                "email_invalid_email": email,
            })
            with patch("core.integrations.sub2api.sync.db.list_codex_accounts", return_value=[]):
                result = sync_sub2api_records([
                    self._sync_record(email, email_invalid=not invalid, email_invalid_reason="外部字段"),
                ], email_source="icloud_hide", sync_codex=False)
            self.assertEqual(0, result["failed_count"])
            self.assertEqual(1, result["accounts_updated"])
            row = record_store.get_row_by(record_store.ACCOUNTS, "email", email)
            self.assertIs(row["email_invalid"], invalid)
            self.assertEqual("本地依据" if invalid else None, row.get("email_invalid_reason"))
            self.assertEqual("outlook", row["email_source"])

    def test_new_sync_uses_actual_email_source_and_ignores_untrusted_external_marker(self):
        from core.integrations.sub2api.sync import sync_sub2api_records

        email = "different-source@example.test"
        record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": email, "status": "used", "email_invalid": True,
        })
        with patch("core.integrations.sub2api.sync.db.list_codex_accounts", return_value=[]):
            result = sync_sub2api_records([
                self._sync_record(email, email_invalid=True, email_invalid_reason="外部字段"),
            ], email_source="email_butler", sync_codex=False)
        self.assertEqual(0, result["failed_count"])
        row = record_store.get_row_by(record_store.ACCOUNTS, "email", email)
        self.assertIs(row["email_invalid"], False)
        self.assertNotEqual("外部字段", row.get("email_invalid_reason"))

    def test_sync_waits_for_email_facts_before_taking_account_lock_and_inherits_commit(self):
        from core.storage.email.validity import lock_email_validity
        from core.integrations.sub2api.sync import sync_sub2api_records

        email = "locked-sync@example.test"
        parent_id = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": email, "status": "used",
        })
        results, failures = [], []

        def synchronize():
            try:
                results.append(sync_sub2api_records([self._sync_record(email)], email_source="icloud_hide", sync_codex=False))
            except BaseException as error:
                failures.append(error)

        worker = threading.Thread(target=synchronize, daemon=True)
        observed_wait = False
        with patch("core.integrations.sub2api.sync.db.list_codex_accounts", return_value=[]):
            try:
                with record_store.transaction() as blocker, blocker.cursor() as cur:
                    lock_email_validity(blocker)
                    cur.execute("SELECT pg_backend_pid() AS pid")
                    blocker_pid = cur.fetchone()["pid"]
                    worker.start()
                    with record_store._connect() as observer, observer.cursor() as poll:
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline and worker.is_alive():
                            poll.execute(
                                "SELECT count(*) AS n FROM pg_locks WHERE NOT granted "
                                "AND %s=ANY(pg_blocking_pids(pid))", (blocker_pid,),
                            )
                            if poll.fetchone()["n"]:
                                observed_wait = True
                                break
                            time.sleep(0.01)
                    cur.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS acquired", (f"registered-account:{email}",))
                    account_lock_available = cur.fetchone()["acquired"]
                    record_store.patch_row(record_store.ICLOUD_HIDE_POOL, parent_id, {
                        "email_invalid": True, "email_invalid_reason": "事务内确认失效",
                    }, conn=blocker)
                worker.join(10)
            finally:
                if worker.ident is not None:
                    worker.join(10)
        self.assertTrue(observed_wait, "同步绕过邮箱事实共享锁")
        self.assertTrue(account_lock_available, "等待邮箱事实时已提前取得账号锁")
        self.assertFalse(worker.is_alive())
        self.assertEqual([], failures)
        self.assertEqual(0, results[0]["failed_count"])
        row = record_store.get_row_by(record_store.ACCOUNTS, "email", email)
        self.assertIs(row["email_invalid"], True)
        self.assertEqual("事务内确认失效", row["email_invalid_reason"])

    def test_sync_repairs_identity_sequence_before_inserting_new_account(self):
        self.seed(record_store.ACCOUNTS, [{
            "id": 455,
            "email": "existing@example.test",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }])

        from core.integrations.sub2api.sync import sync_sub2api_records

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
        with patch("core.integrations.sub2api.sync.db.list_codex_accounts", return_value=[]):
            result = sync_sub2api_records([raw])

        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["accounts_created"], 1)
        stored = record_store.get_row_by(record_store.ACCOUNTS, "email", "new@example.test", lower=True)
        self.assertIsNotNone(stored)
        self.assertGreater(int(stored["id"]), 455)
        self.assertEqual(stored["registration_proxy_region"], "US")

    def test_sync_persists_sub2api_401_on_codex_credential(self):
        from core.integrations.sub2api.sync import sync_sub2api_records

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
        with patch("core.integrations.sub2api.sync.db.list_codex_accounts", return_value=[]):
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
