# -*- coding: utf-8 -*-
"""人工确认账号恢复后的存储状态与旧停用证据回归。"""
from datetime import datetime, timedelta
from unittest.mock import patch

from core import db
from core.storage import records as record_store
from core.storage import accounts
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class AccountReactivationStorageTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        operation.init()

    def _account(self, **overrides):
        payload = {
            "email": "restored@example.test",
            "account_status": "deactivated",
            "account_status_reason": "account_deactivated",
            "account_status_source": "token_refresh",
            "account_status_at": "2026-10-19T01:00:00Z",
            "codex_status": "deactivated",
            "codex_credential_state": "deactivated",
            "live_check_status": "deactivated",
            "live_check_error": "account_deactivated",
            "live_check_http_status": 401,
            "access_token": "synthetic-private-access",
            "password": "synthetic-private-password",
            "deactivation_mail_detected": True,
            "deactivation_mail_message_id": "old-signal",
            "deactivation_mail_received_at": "2026-10-19T01:00:00Z",
            "deactivation_mail_subject": "账号停用通知",
            "deactivation_mail_sender": "noreply@openai.com",
        }
        payload.update(overrides)
        return record_store.insert_row(record_store.ACCOUNTS, payload)

    def _credential(self, status="deactivated"):
        return record_store.insert_row(record_store.CODEX_CREDENTIALS, {
            "filename": "codex-restored@example.test-free.json",
            "email": "restored@example.test",
            "oauth_status": status,
            "oauth_account_status": status,
            "oauth_account_status_reason": "account_deactivated",
            "oauth_account_status_at": "2026-10-19T01:00:00Z",
            "content": {"refresh_token": "synthetic-private-refresh", "access_token": "synthetic-private-codex"},
        })

    def _restore(self, account_id):
        return accounts.restore_account_after_deactivation(account_id, reason="OpenAI 已确认申诉成功")

    def test_restore_clears_current_guards_and_preserves_low_sensitive_history(self):
        account_id = self._account()
        self.assertTrue(self._restore(account_id))
        row = db.get_account(account_id)
        self.assertFalse(db.account_is_deactivated(row))
        self.assertEqual(0, record_store.count_rows(record_store.ACCOUNTS, where="deactivated"))
        self.assertEqual("active", row["account_status"])
        self.assertEqual("failed", row["codex_status"])
        self.assertEqual("reauth_required", row["codex_credential_state"])
        self.assertNotEqual("deactivated", row.get("live_check_status"))
        self.assertIsNone(row.get("live_check_error"))
        self.assertIsNone(row.get("live_check_http_status"))
        self.assertFalse(row["deactivation_mail_detected"])
        self.assertEqual(timedelta(0), datetime.fromisoformat(row["account_restored_at"]).utcoffset())
        self.assertEqual("OpenAI 已确认申诉成功", row["account_restored_reason"])
        self.assertEqual("manual", row["account_restored_source"])
        history = row["account_deactivation_history"]
        self.assertEqual(1, len(history))
        self.assertEqual("account_deactivated", history[0]["reason"])
        self.assertEqual("token_refresh", history[0]["source"])
        self.assertEqual("deactivated", history[0]["codex_credential_state"])
        self.assertEqual("old-signal", history[0]["deactivation_mail"]["message_id"])
        self.assertNotIn("synthetic-private", str(history))
        self.assertEqual("synthetic-private-access", row["access_token"])
        self.assertEqual("synthetic-private-password", row["password"])
        self.assertTrue(db.claim_account_live_check(account_id))

    def test_restore_requires_new_codex_authorization_without_touching_credential_content(self):
        account_id = self._account()
        credential_id = self._credential()
        before = record_store.get_row(record_store.CODEX_CREDENTIALS, credential_id)
        self.assertTrue(self._restore(account_id))
        after = record_store.get_row(record_store.CODEX_CREDENTIALS, credential_id)
        self.assertEqual(before["content"], after["content"])
        self.assertEqual("active", after["oauth_account_status"])
        self.assertEqual("reauth_required", after["oauth_status"])
        self.assertTrue(after["oauth_reauth_required"])
        self.assertEqual("account_deactivated", after["oauth_deactivation_history"][0]["reason"])
        self.assertTrue(db.list_codex_accounts()[0]["oauth_reauth_required"])

    def test_restore_also_requires_reauthorization_for_previously_valid_credentials(self):
        account_id = self._account(codex_credential_state="valid")
        credential_id = self._credential(status="valid")
        self._restore(account_id)
        row = record_store.get_row(record_store.CODEX_CREDENTIALS, credential_id)
        self.assertEqual("reauth_required", row["oauth_status"])
        self.assertTrue(row["oauth_reauth_required"])

    def test_absent_and_idempotent_restore_do_not_rewrite_history(self):
        self.assertFalse(self._restore(999999))
        account_id = self._account()
        self._restore(account_id)
        before = db.get_account(account_id)
        self.assertTrue(self._restore(account_id))
        self.assertEqual(before, db.get_account(account_id))

    def test_credential_failure_rolls_back_account_and_history(self):
        account_id = self._account()
        credential_id = self._credential()
        original = record_store.patch_row

        def fail_credential(table, *args, **kwargs):
            if table is record_store.CODEX_CREDENTIALS:
                raise RuntimeError("凭证写回失败")
            return original(table, *args, **kwargs)

        with patch.object(record_store, "patch_row", side_effect=fail_credential):
            with self.assertRaisesRegex(RuntimeError, "凭证写回失败"):
                self._restore(account_id)
        self.assertTrue(db.account_is_deactivated(db.get_account(account_id)))
        self.assertNotIn("account_deactivation_history", db.get_account(account_id))
        self.assertEqual("deactivated", record_store.get_row(record_store.CODEX_CREDENTIALS, credential_id)["oauth_status"])

    def test_active_operation_run_prevents_restore(self):
        account_id = self._account(account_status="active", codex_status="failed", codex_credential_state="none")
        operation.create_runtime_task(task_type="token_refresh", account_id=account_id, email="restored@example.test")
        db.mark_account_deactivated(account_id)
        with self.assertRaisesRegex(ValueError, "任务.*执行|任务.*进行"):
            self._restore(account_id)
        self.assertTrue(db.account_is_deactivated(db.get_account(account_id)))

    def test_mail_deactivation_and_credential_failure_roll_back_together(self):
        account_id = self._account()
        credential_id = self._credential()
        self._restore(account_id)
        before = db.get_account(account_id)
        original = record_store.patch_row

        def fail_credential(table, *args, **kwargs):
            if table is record_store.CODEX_CREDENTIALS:
                raise RuntimeError("邮件停用凭证写回失败")
            return original(table, *args, **kwargs)

        with patch.object(record_store, "patch_row", side_effect=fail_credential):
            with self.assertRaisesRegex(RuntimeError, "邮件停用凭证写回失败"):
                db.update_account_deactivation_mail(account_id, {
                    "status": "success", "detected": True, "message_id": "fresh-signal",
                })
        self.assertEqual(before, db.get_account(account_id))
        self.assertEqual("active", record_store.get_row(record_store.CODEX_CREDENTIALS, credential_id)["oauth_account_status"])

    def test_active_business_projection_prevents_restore(self):
        for key in ("live_check_status", "plan_check_status", "codex_execution_status", "deactivation_mail_scan_status", "extract_link_status", "email_change_status"):
            with self.subTest(key=key):
                account_id = self._account(email=f"{key}@example.test", **{key: "running"})
                with self.assertRaisesRegex(ValueError, "任务.*执行|任务.*进行"):
                    self._restore(account_id)

    def test_replayed_old_mail_is_ignored_but_new_mail_deactivates_again(self):
        account_id = self._account()
        self._restore(account_id)
        restored_at = datetime.fromisoformat(db.get_account(account_id)["account_restored_at"])
        signals = [
            {"message_id": "old-signal"},
            {"message_id": "different-copy", "received_at": (restored_at - timedelta(days=1)).isoformat()},
        ]
        for signal in signals:
            db.update_account_deactivation_mail(account_id, {"status": "success", "detected": True, **signal})
            self.assertFalse(db.account_is_deactivated(db.get_account(account_id)))
            self.assertFalse(db.get_account(account_id)["deactivation_mail_detected"])
        db.update_account_deactivation_mail(account_id, {
            "status": "success", "detected": True, "message_id": "new-signal",
            "received_at": (restored_at + timedelta(seconds=1)).isoformat(),
        })
        self.assertTrue(db.account_is_deactivated(db.get_account(account_id)))

    def test_mail_without_reliable_timestamp_or_known_message_id_still_deactivates(self):
        account_id = self._account()
        self._restore(account_id)
        db.update_account_deactivation_mail(account_id, {"status": "success", "detected": True})
        self.assertTrue(db.account_is_deactivated(db.get_account(account_id)))

    def test_fresh_upstream_deactivation_and_empty_rescan_keep_normal_protection(self):
        account_id = self._account()
        self._restore(account_id)
        db.update_account_liveness(account_id, {"status": "deactivated", "ok": False, "error": "account_deactivated"})
        self.assertTrue(db.account_is_deactivated(db.get_account(account_id)))
        db.update_account_deactivation_mail(account_id, {"status": "success", "detected": True, "message_id": "unconfirmed-new"})
        db.update_account_deactivation_mail(account_id, {"status": "success", "detected": False})
        self.assertTrue(db.get_account(account_id)["deactivation_mail_detected"])
