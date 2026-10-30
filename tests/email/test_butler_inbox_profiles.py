# -*- coding: utf-8 -*-
"""Butler 固定收件路由、版本密钥与库存的隔离数据库测试。"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from config import email as cfg, env_loader
from core.email import derivation as service
from core.runtime import capabilities as feature_availability
from core.email import forward_imap as forward
from core.storage import records as record_store
from core.storage.email import address_allocations as store
from tests.support_pg import PostgresTestCase


class ButlerInboxProfileTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.env_file = patch.object(env_loader, "_ENV_PATH", Path(self.root.name) / ".env")
        self.env_file.start()
        self.addCleanup(self.env_file.stop)
        self.environment = patch.dict(os.environ, {})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.config = patch.multiple(cfg, EMAIL_SOURCE="icloud_hide", EMAIL_DERIVATION_ENABLED=True,
            EMAIL_DERIVATION_SOURCES="icloud_hide", ICLOUD_HME_INBOX_MODE="forward_butler",
            ICLOUD_HME_ACCOUNT_ID="", ICLOUD_HME_API_BASE="http://hme.example.test",
            ICLOUD_HME_FORWARD_IMAP_EMAIL="final@example.test", ICLOUD_HME_FORWARD_IMAP_PASSWORD="",
            EMAIL_BUTLER_API_BASE="https://first.example.test/v1", EMAIL_BUTLER_API_KEY="first-test-key")
        self.config.start()
        self.addCleanup(self.config.stop)
        self.parent = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "alias@icloud.com", "status": "used", "account_id": "apple-test",
            "remote_active": True, "forward_to_email": "relay@example.test"})

    def generate(self, count=1, request="butler-stock"):
        with patch("core.email.icloud_hide.client.sync_aliases", return_value={"synced_account_ids": ["apple-test"]}):
            return service.generate_inventory("icloud_hide", count, request)

    def test_new_profile_keeps_fixed_endpoint_mailbox_and_versioned_key_out_of_pg(self):
        first = service._forward_profile()
        with patch.object(cfg, "EMAIL_BUTLER_API_KEY", "rotated-test-key"):
            rotated = service._forward_profile()
        with patch.object(cfg, "EMAIL_BUTLER_API_BASE", "https://second.example.test/v1"):
            second = service._forward_profile()
        self.assertEqual(first["connector"], "forward_butler")
        self.assertEqual(first["inbox_locator"], {"api_base": "https://first.example.test/v1", "mailbox_email": "final@example.test"})
        self.assertTrue(first["credential_ref"].startswith("EMAIL_DERIVATION_BUTLER_SECRET_"))
        self.assertEqual(first["inbox_key"], rotated["inbox_key"])
        self.assertGreater(rotated["revision"], first["revision"])
        self.assertNotEqual(first["credential_ref"], rotated["credential_ref"])
        self.assertNotEqual(first["inbox_key"], second["inbox_key"])
        self.assertEqual(env_loader.read_env_file()[first["credential_ref"]], "first-test-key")
        self.assertEqual(env_loader.read_env_file()[rotated["credential_ref"]], "rotated-test-key")
        self.assertNotIn("first-test-key", json.dumps(first))
        self.assertNotIn("rotated-test-key", json.dumps(rotated))

    def test_butler_inventory_capacity_availability_claim_and_pinned_fetch(self):
        self.assertEqual(service.generation_capacity_summary("icloud_hide")["remaining"], 3)
        self.assertEqual(self.generate(2)["created"], 2)
        self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 2)
        self.assertTrue(feature_availability.email_source_availability()["icloud_hide"]["enabled"])
        address = service.acquire_address("icloud_hide", acquisition_id="butler-claim", owner_kind="registration_root", owner_id="butler-claim")
        with patch.multiple(cfg, ICLOUD_HME_INBOX_MODE="forward_imap", EMAIL_BUTLER_API_BASE="https://changed.example.test/v1",
                EMAIL_BUTLER_API_KEY="changed-key", ICLOUD_HME_FORWARD_IMAP_EMAIL="changed@example.test"), patch(
                "core.email.email_butler.client.fetch_inbound_otp", return_value="654321") as fetch, patch.object(
                forward, "_connect", side_effect=AssertionError("固定 Butler 路由不能连接 IMAP")):
            self.assertEqual(service.fetch_bound_otp(address, after_ts=100), "654321")
            self.assertEqual(fetch.call_args.kwargs["api_base"], "https://first.example.test/v1")
            self.assertEqual(fetch.call_args.kwargs["api_key"], "first-test-key")
            self.assertEqual(fetch.call_args.kwargs["mailbox_email"], "final@example.test")
        parent_profile = service.inbox_profile_for_address("alias@icloud.com")
        self.assertTrue(parent_profile["strict_family"])
        self.assertEqual(parent_profile["connector"], "forward_butler")

    def test_existing_imap_profile_stays_imap_after_global_butler_switch(self):
        profile = store.create_inbox_profile(inbox_key="imap:old", connector="forward_imap", credential_ref="OLD_TEST_IMAP_KEY",
            inbox_locator={"server": "imap.old.test", "email": "old@example.test", "port": 993})
        os.environ["OLD_TEST_IMAP_KEY"] = "old-test-password"
        child = store.allocate_address(source="icloud_hide", inbox_profile_id=profile["id"],
            max_children=3, acquisition_id="old-child", owner_kind="registration_root", owner_id="old-child")
        with patch.object(forward, "_fetch_latest_otp_local", return_value="123456") as local:
            self.assertEqual(service.fetch_bound_otp(child["address"], after_ts=100), "123456")
        self.assertEqual(local.call_args.args[0], child["address"])
        self.assertEqual(store.get_inbox_profile(profile["id"])["connector"], "forward_imap")


if __name__ == "__main__":
    import unittest
    unittest.main()
