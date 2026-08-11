# -*- coding: utf-8 -*-
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core import db
from core import icloud_hme_client as client
from core import email_provider


class ICloudHidePoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pool_path = Path(self.tmp.name) / "icloud-pool.json"
        self.pool_patch = patch.object(db, "_ICLOUD_HIDE_EMAIL_JSON", self.pool_path)
        self.accounts_patch = patch.object(db, "_load_accounts", return_value=[])
        self.pool_patch.start()
        self.accounts_patch.start()

    def tearDown(self):
        self.accounts_patch.stop()
        self.pool_patch.stop()
        self.tmp.cleanup()

    def test_sync_claim_and_release_unconsumed(self):
        result = db.sync_icloud_hide_aliases([
            {"email": "one@example.com", "anonymousId": "anon-1", "label": "One", "active": True},
            {"email": "off@example.com", "anonymousId": "anon-2", "label": "Off", "active": False},
        ], "acc-1")
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(db.icloud_hide_email_pool_summary()["available"], 1)
        self.assertEqual(db.icloud_hide_email_pool_summary()["disabled"], 1)

        claimed = db.claim_next_icloud_hide_email("acc-1")
        self.assertEqual(claimed["email"], "one@example.com")
        self.assertEqual(claimed["status"], "used")
        self.assertTrue(db.release_unconsumed_icloud_hide_email("one@example.com", note="task stopped"))
        self.assertEqual(db.get_icloud_hide_email_by_email("one@example.com")["status"], "available")

    def test_registered_alias_is_not_released(self):
        with patch.object(db, "_load_accounts", return_value=[{"email": "bound@example.com"}]):
            db.sync_icloud_hide_aliases([{"email": "bound@example.com", "active": True}], "acc-1")
            self.assertEqual(db.get_icloud_hide_email_by_email("bound@example.com")["status"], "used")
            self.assertFalse(db.release_unconsumed_icloud_hide_email("bound@example.com"))

    def test_full_sync_disables_missing_alias_but_partial_sync_does_not(self):
        db.sync_icloud_hide_aliases([
            {"email": "keep@example.com", "active": True},
            {"email": "missing@example.com", "active": True},
        ], "acc-1")
        db.sync_icloud_hide_aliases([{"email": "new@example.com", "active": True}], "acc-1", full_snapshot=False)
        self.assertEqual(db.get_icloud_hide_email_by_email("missing@example.com")["status"], "available")

        db.sync_icloud_hide_aliases([
            {"email": "keep@example.com", "active": True},
            {"email": "new@example.com", "active": True},
        ], "acc-1")
        missing = db.get_icloud_hide_email_by_email("missing@example.com")
        self.assertEqual(missing["status"], "disabled")
        self.assertEqual(missing["disabled_reason"], "remote_missing")


class ICloudHMEClientTests(unittest.TestCase):
    def test_non_icloud_forward_target_is_disabled_for_imap_pool(self):
        prepared, routing = client._prepare_imap_aliases([
            {"email": "bad@icloud.com", "forwardToEmail": "owner@gmail.com", "active": True},
            {"email": "good@icloud.com", "forwardToEmail": "owner@icloud.com", "active": True},
        ])
        self.assertFalse(prepared[0]["active"])
        self.assertTrue(prepared[1]["active"])
        self.assertEqual(routing["forward_domains"], ["gmail.com", "icloud.com"])
        self.assertEqual(routing["forward_incompatible"], 1)
        self.assertEqual(routing["remote_usable"], 1)

    def test_gmail_forward_target_is_enabled_for_matching_forward_imap(self):
        prepared, routing = client._prepare_imap_aliases(
            [{"email": "alias@icloud.com", "forwardToEmail": "owner@gmail.com", "active": True}],
            inbox_mode="forward_imap",
            forward_imap_email="owner@gmail.com",
        )
        self.assertTrue(prepared[0]["active"])
        self.assertEqual(routing["remote_usable"], 1)
        self.assertEqual(routing["forward_incompatible"], 0)

    @patch("core.forward_imap_client.fetch_latest_otp", return_value="123456")
    @patch.object(client, "_inbox_mode", return_value="forward_butler")
    def test_fetch_latest_otp_delegates_to_forward_cache(self, _mode, fetch):
        result = client.fetch_latest_otp("alias@icloud.com", after_ts=123.0, max_wait=10)
        self.assertEqual(result, "123456")
        fetch.assert_called_once()

    def setUp(self):
        client._LAST_SYNC_AT = 0.0
        client._LAST_SYNC_KEY = ""
        client._LAST_ACCOUNT_ID = ""
        self.inbox_mode_patch = patch.object(client, "_inbox_mode", return_value="sidecar")
        self.inbox_mode_patch.start()

    def tearDown(self):
        self.inbox_mode_patch.stop()

    @patch("core.db.sync_icloud_hide_aliases")
    @patch("core.icloud_hme_client._request")
    def test_connection_syncs_aliases_and_checks_imap(self, request_mock, sync_mock):
        request_mock.side_effect = [
            [{"id": "acc-1", "status": "active"}],
            {"aliases": [{"email": "one@example.com", "active": True}]},
            {"method": "imap", "messages": []},
        ]
        sync_mock.return_value = {"inserted": 1, "updated": 0, "total": 1}
        with patch("core.db.icloud_hide_email_pool_summary", return_value={"available": 1, "total": 1}):
            result = client.test_connection(api_base="http://127.0.0.1:8081", account_id="acc-1")

        self.assertEqual(result["account_id"], "acc-1")
        self.assertEqual(result["remote_aliases"], 1)
        self.assertEqual(result["inbox_method"], "imap")
        sync_mock.assert_called_once()

    @patch("core.db.icloud_hide_email_pool_summary", return_value={"available": 0, "disabled": 1, "total": 1})
    @patch("core.db.sync_icloud_hide_aliases", return_value={"inserted": 1, "total": 1})
    @patch("core.icloud_hme_client._request")
    def test_connection_rejects_gmail_forward_with_icloud_imap(self, request_mock, _sync, _summary):
        request_mock.side_effect = [
            [{"id": "acc-1", "status": "active"}],
            {"aliases": [{
                "email": "alias@icloud.com",
                "forwardToEmail": "owner@gmail.com",
                "active": True,
            }]},
            {"method": "imap", "messages": []},
        ]
        with self.assertRaisesRegex(client.ICloudHMEError, "gmail.com"):
            client.test_connection(api_base="http://127.0.0.1:8081", account_id="acc-1")

    @patch("core.db.icloud_hide_email_pool_summary", return_value={"available": 2, "total": 2})
    @patch("core.db.sync_icloud_hide_aliases", return_value={"inserted": 2, "total": 2})
    @patch("core.icloud_hme_client.list_aliases", return_value=("auto-selected", [{"email": "a@example.com"}]))
    def test_cached_sync_keeps_auto_selected_account_id(self, _list, _sync, _summary):
        first = client.sync_aliases(force=True)
        second = client.sync_aliases(force=False)
        self.assertEqual(first["account_id"], "auto-selected")
        self.assertEqual(second["account_id"], "auto-selected")
        self.assertTrue(second["cached"])

    @patch("core.icloud_hme_client.get_account_context", return_value=client.ICloudHMEAccount(
        email="alias@icloud.com", account_id="acc-1"
    ))
    @patch("core.icloud_hme_client._request")
    def test_fetch_latest_otp_reads_new_openai_message(self, request_mock, _context):
        request_mock.return_value = {
            "method": "imap",
            "messages": [{
                "id": "101",
                "from": "OpenAI <noreply@tm.openai.com>",
                "to": "alias@icloud.com",
                "subject": "Your ChatGPT code is 654321",
                "date": "2026-08-10T12:00:01Z",
                "preview": "Your verification code is 654321",
            }],
        }
        otp = client.fetch_latest_otp(
            "alias@icloud.com",
            after_ts=time.mktime((2026, 8, 10, 11, 59, 0, 0, 0, -1)),
            max_wait=2,
            poll_interval=1,
            settle_seconds=0,
        )
        self.assertEqual(otp, "654321")


class ICloudEmailProviderTests(unittest.TestCase):
    def test_source_is_parsed_and_acquired(self):
        self.assertEqual(email_provider.parse_email_sources("icloud_hide,outlook"), ["icloud_hide", "outlook"])
        with patch("core.icloud_hme_client.pick_account", return_value=client.ICloudHMEAccount(
            email="alias@icloud.com", account_id="acc-1"
        )):
            self.assertEqual(email_provider._pick_from_source("icloud_hide"), "alias@icloud.com")

    @patch("core.db.get_icloud_hide_email_by_email", return_value={"email": "alias@icloud.com", "account_id": "acc-1"})
    def test_resolve_and_release_unconsumed_use_icloud_pool(self, _context):
        with patch("core.db.release_unconsumed_icloud_hide_email", return_value=True) as release:
            self.assertEqual(email_provider.resolve_email_source("alias@icloud.com"), "icloud_hide")
            self.assertTrue(email_provider.release_email_if_unconsumed("alias@icloud.com", note="stopped"))
            release.assert_called_once_with("alias@icloud.com", note="stopped")


if __name__ == "__main__":
    unittest.main()
