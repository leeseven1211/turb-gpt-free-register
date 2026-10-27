"""派生邮箱与原任务、账号及收件配置的集成回归。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from config import email as cfg
from core import db, email_derivation as service, email_provider, record_store
from core.storage import email_address_allocations as store
from tests.support_pg import PostgresTestCase


class EmailDerivationIntegrationTests(PostgresTestCase):
    def setUp(self):
        self.parent_id = self.seed(record_store.ICLOUD_HIDE_POOL, [{
            "email": "parent@icloud.com", "status": "used", "account_id": "test-apple",
            "remote_active": True, "forward_to_email": "sink@gmail.com",
        }])[0]
        self.profile = store.create_inbox_profile(
            inbox_key="test-inbox", connector="forward_imap", credential_ref="TEST_DERIVATION_SECRET",
            inbox_locator={"server": "imap.example.test", "port": 993, "email": "sink@gmail.com"},
        )
        self.scope = patch.multiple(cfg, USE_EMAIL_SERVICE=True, EMAIL_DERIVATION_ENABLED=True, EMAIL_DERIVATION_SOURCES="icloud_hide",
                                    EMAIL_DERIVATION_MAX_CHILDREN=3, EMAIL_DERIVATION_TAG_LENGTH=6, ICLOUD_HME_ACCOUNT_ID="")
        self.scope.start()
        self.addCleanup(self.scope.stop)
        self.secret_scope = patch.dict(os.environ, {"TEST_DERIVATION_SECRET": "test-inbox-password"})
        self.secret_scope.start()
        self.addCleanup(self.secret_scope.stop)
        self.addCleanup(patch.stopall)
        with patch.object(service, "_forward_profile", return_value=self.profile), patch(
            "core.icloud_hme_client.sync_aliases", return_value={"synced_account_ids": ["test-apple"]}):
            service.generate_inventory("icloud_hide", 3, "integration-stock")

    def acquire(self, number=1, **kwargs):
        with patch.object(service, "_forward_profile", return_value=self.profile), patch(
            "core.icloud_hme_client.sync_aliases", return_value={"synced_account_ids": ["test-apple"]},
        ):
            return service.acquire_address(
                "icloud_hide", owner_kind="registration_root", owner_id=number,
                acquisition_id=f"registration:{number}", **kwargs,
            )

    def test_three_children_and_raising_limit_only_adds_new_addresses(self):
        first = [self.acquire(index) for index in range(1, 4)]
        self.assertEqual(len(set(first)), 3)
        self.assertTrue(all(len(address.split("+")[1].split("@")[0]) == 6 for address in first))
        with self.assertRaisesRegex(RuntimeError, "库存"):
            self.acquire(4)
        with patch.object(cfg, "EMAIL_DERIVATION_MAX_CHILDREN", 4), patch.object(
            service, "_forward_profile", return_value=self.profile), patch(
            "core.icloud_hme_client.sync_aliases", return_value={"synced_account_ids": ["test-apple"]}):
            with self.assertRaisesRegex(RuntimeError, "库存"):
                self.acquire(4)
            service.generate_inventory("icloud_hide", 1, "integration-more")
            fourth = self.acquire(4)
        self.assertNotIn(fourth, first)
        self.assertEqual(self.acquire(1), first[0])
        self.assertEqual(db.get_icloud_hide_email_by_email("parent@icloud.com")["status"], "used")

    def test_disabled_generation_keeps_original_acquisition_and_recovery(self):
        address = self.acquire()
        with patch.object(cfg, "EMAIL_DERIVATION_ENABLED", False), patch.object(cfg, "EMAIL_SOURCE", "outlook"):
            self.assertEqual(self.acquire(), address)
            self.assertEqual(email_provider.resolve_email_source(address), "icloud_hide")
            self.assertEqual(email_provider.restore_email_context(address, source="icloud_hide"), "icloud_hide")
            self.assertEqual(email_provider.acquire_email(
                "icloud_hide", owner_kind="registration_root", owner_id=1, acquisition_id="registration:1",
            ), address)

    def test_releasing_child_never_recycles_parent_or_changes_sibling(self):
        address, sibling = self.acquire(1), self.acquire(2)
        email_provider.release_email(address, status="available")
        self.assertFalse(email_provider.release_email_if_unconsumed(address))
        self.assertEqual(service.find_binding(address)["state"], "reserved")
        email_provider.mark_email_permanently_unusable(address, source="icloud_hide")
        self.assertEqual(service.find_binding(address)["state"], "retired")
        self.assertEqual(service.find_binding(sibling)["state"], "reserved")
        self.assertEqual(db.get_icloud_hide_email_by_email("parent@icloud.com")["status"], "used")

    def test_account_writeback_updates_same_allocation(self):
        address = self.acquire()
        account_id = db.insert_account(email=address, access_token="test-account-token", email_source="icloud_hide")
        account = db.get_account_by_email(address)
        binding = service.find_binding(address)
        self.assertEqual(account["email_address_id"], binding["id"])
        self.assertEqual(binding["state"], "used")
        self.assertEqual(binding["account_id"], account_id)
        self.assertFalse(account.get("password"))

    def test_binding_failure_rolls_back_account_write(self):
        address = self.acquire()
        with patch.object(store, "mark_allocation_state", side_effect=RuntimeError("模拟绑定写回失败")):
            with self.assertRaisesRegex(RuntimeError, "模拟"):
                db.insert_account(email=address, access_token="test-account-token", email_source="icloud_hide")
        self.assertIsNone(db.get_account_by_email(address))
        self.assertEqual(service.find_binding(address)["state"], "reserved")

    def test_parent_deletion_archives_credentials_without_removing_recovery(self):
        address = self.acquire()
        self.assertTrue(db.delete_icloud_hide_email("parent@icloud.com"))
        parent = store.get_parent("icloud_hide", self.parent_id)
        self.assertTrue(parent["archived"])
        self.assertFalse(parent["derivation_policy"]["enabled"])
        self.assertIsNotNone(service.restore_address(address))
        with self.assertRaisesRegex(RuntimeError, "库存"):
            self.acquire(2)

    def test_child_cannot_be_reimported_as_a_second_direct_resource(self):
        address = self.acquire()
        self.assertEqual(db.import_outlook_accounts([{
            "email": address, "password": "p", "client_id": "c", "refresh_token": "r",
        }]), (0, 1))
        self.assertEqual(db.import_generic_api_emails([{"email": address, "code_url": "https://example.test/code"}]), (0, 1))
        self.assertIsNone(db.get_outlook_by_email(address))
        self.assertIsNone(db.get_generic_api_email_by_email(address))

    def test_child_uses_original_inbox_even_after_global_mailbox_changes(self):
        address = self.acquire()
        from core import forward_imap_client

        def fetch(target, **_kwargs):
            self.assertEqual(target, address)
            self.assertEqual(forward_imap_client._settings(), ("imap.example.test", 993, "sink@gmail.com", "old-password"))
            return "345678"

        with patch.dict(os.environ, {"TEST_DERIVATION_SECRET": "old-password"}), patch.object(
            cfg, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "different@gmail.com",
        ), patch.object(forward_imap_client, "fetch_latest_otp", side_effect=fetch):
            self.assertEqual(email_provider.wait_for_otp(address, after_ts=1, email_source="icloud_hide"), "345678")

    def test_profile_secrets_only_persist_in_env_and_old_reference_is_retained(self):
        from config import env_loader

        with tempfile.TemporaryDirectory() as tmp, patch.object(env_loader, "_ENV_PATH", Path(tmp) / ".env"):
            with patch.multiple(cfg, ICLOUD_HME_INBOX_MODE="forward_imap", ICLOUD_HME_FORWARD_IMAP_SERVER="imap.example.test",
                                ICLOUD_HME_FORWARD_IMAP_EMAIL="one@example.test", ICLOUD_HME_FORWARD_IMAP_PASSWORD="first-private-value"):
                first = service._forward_profile()
            with patch.multiple(cfg, ICLOUD_HME_INBOX_MODE="forward_imap", ICLOUD_HME_FORWARD_IMAP_SERVER="imap.example.test",
                                ICLOUD_HME_FORWARD_IMAP_EMAIL="two@example.test", ICLOUD_HME_FORWARD_IMAP_PASSWORD="second-private-value"):
                second = service._forward_profile()
            self.assertNotEqual(first["id"], second["id"])
            self.assertNotEqual(first["credential_ref"], second["credential_ref"])
            persisted = env_loader.read_env_file()
            self.assertEqual(persisted[first["credential_ref"]], "first-private-value")
            self.assertNotIn("first-private-value", json.dumps(first))
            self.assertNotIn("second-private-value", json.dumps(second))

            with patch.multiple(cfg, ICLOUD_HME_INBOX_MODE="forward_imap", ICLOUD_HME_FORWARD_IMAP_SERVER="imap.example.test",
                                ICLOUD_HME_FORWARD_IMAP_EMAIL="one@example.test", ICLOUD_HME_FORWARD_IMAP_PASSWORD="rotated-private-value"):
                rotated = service._forward_profile()
            self.assertEqual(rotated["inbox_key"], first["inbox_key"])
            self.assertGreater(rotated["revision"], first["revision"])
            self.assertNotEqual(rotated["credential_ref"], first["credential_ref"])
            self.assertEqual(env_loader.read_env_file()[first["credential_ref"]], "first-private-value")

    def test_email_change_restores_frozen_derivation_policy(self):
        from types import SimpleNamespace
        from core import email_change_service

        context = SimpleNamespace(
            task_id=42, checkpoint=lambda: None,
            run={"data": {"remail_acquisition_id": "change:42"}},
            config_snapshot={"email_derivation_enabled": True, "email_derivation_sources": ["icloud_hide"],
                             "email_derivation_max_children": 3, "email_derivation_tag_length": 6},
        )
        with patch.object(cfg, "EMAIL_DERIVATION_ENABLED", False), patch.object(
            service, "_forward_profile", return_value=self.profile,
        ), patch("core.icloud_hme_client.sync_aliases", return_value={"synced_account_ids": ["test-apple"]}):
            address, failure = email_change_service._acquire_email_change_target(
                context, account_id=11, source="icloud_hide", current_email="old@example.test",
            )
        self.assertIsNone(failure)
        self.assertEqual(service.find_binding(address)["owner_id"], "42")
        context.config_snapshot = {}
        with patch.object(cfg, "EMAIL_DERIVATION_ENABLED", False):
            restored, failure = email_change_service._acquire_email_change_target(
                context, account_id=11, source="icloud_hide", current_email="old@example.test",
            )
        self.assertEqual(restored, address)
        self.assertIsNone(failure)

    def test_otp_cannot_attach_to_another_address_auth_session(self):
        from types import SimpleNamespace
        from core import email_auth_guard

        address, sibling = self.acquire(1), self.acquire(2)
        with patch.object(email_auth_guard, "current_session", return_value=SimpleNamespace(email=sibling)), patch.object(
            service, "fetch_bound_otp",
        ) as fetch:
            with self.assertRaisesRegex(store.StaleOtpFence, "不一致"):
                email_provider.wait_for_otp(address, after_ts=1, email_source="icloud_hide")
        fetch.assert_not_called()

    def test_public_projection_has_no_credentials_and_keeps_complete_child(self):
        address = self.acquire()
        page = service.list_allocations(source="icloud_hide")
        self.assertEqual(page["items"][0]["email"], address)
        summary = service.public_summary("icloud_hide")
        self.assertEqual(summary["parents"][0]["remaining"], 0)
        self.assertEqual(summary["available"], 2)
        self.assertNotIn("credential_ref", json.dumps(page))
        self.assertNotIn("TEST_DERIVATION_SECRET", json.dumps(summary))

    def test_frozen_policy_does_not_follow_hot_reload(self):
        frozen = {"enabled": False, "sources": ["icloud_hide"], "max_children": 3, "tag_length": 6}
        with service.use_policy(frozen):
            self.assertFalse(service.enabled_for("icloud_hide"))
        self.assertTrue(service.enabled_for("icloud_hide"))

    def test_unsupported_adapter_is_not_assumed_to_support_children(self):
        with self.assertRaisesRegex(RuntimeError, "连接器"):
            service.acquire_address("generic_api", owner_kind="registration_root", owner_id=1,
                                    acquisition_id="unsupported:1", policy={"enabled": True, "sources": ["generic_api"]})
