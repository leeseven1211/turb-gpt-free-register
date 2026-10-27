# -*- coding: utf-8 -*-
"""受控收件路由迁移只改变路由，保留业务身份和使用状态。"""
import unittest
import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from core import record_store
from core.storage import email_address_allocations as allocations
from tests.support_pg import PostgresTestCase


class EmailInboxCutoverTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.old = allocations.create_inbox_profile(inbox_key="old", connector="forward_imap", credential_ref="OLD_KEY",
            inbox_locator={"email": "old@example.test", "server": "imap.example.test"})
        self.parent = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "parent@icloud.com", "status": "used", "account_id": "apple-stable"})
        self.child = allocations.allocate_address(source="icloud_hide", parent_id=self.parent,
            inbox_profile_id=self.old["id"], acquisition_id="original-intent", owner_kind="registration_root", owner_id="original-owner")
        self.unowned = allocations.allocate_address(source="icloud_hide", parent_id=self.parent,
            inbox_profile_id=self.old["id"], generation_key="free-stock", acquisition_id=None, owner_kind=None, owner_id=None)

    def plan(self):
        from core.storage.email_inbox_cutover import plan_cutover
        return plan_cutover(api_base="https://butler.example.test/v1", mailbox_email="final@example.test",
            credential_ref="EMAIL_DERIVATION_BUTLER_SECRET_TEST")

    def test_dry_run_makes_no_profile_or_business_changes(self):
        before_profiles = allocations.list_inbox_profiles()
        before_child = allocations.get_allocation(self.child["id"])
        plan = self.plan()
        self.assertEqual(plan["allocation_count"], 2)
        self.assertEqual(plan["parent_count"], 1)
        self.assertEqual(allocations.list_inbox_profiles(), before_profiles)
        self.assertEqual(allocations.get_allocation(self.child["id"]), before_child)

    def test_apply_and_rollback_preserve_states_owners_addresses_and_old_profile(self):
        from core.storage.email_inbox_cutover import apply_cutover, rollback_cutover
        before_child = allocations.get_allocation(self.child["id"])
        before_free = allocations.get_allocation(self.unowned["id"])
        receipt = apply_cutover(self.plan())
        self.assertEqual(receipt["allocation_count"], 2)
        current = allocations.get_allocation(self.child["id"])
        self.assertNotEqual(current["inbox_profile_id"], before_child["inbox_profile_id"])
        for key in before_child:
            if key != "inbox_profile_id":
                self.assertEqual(current[key], before_child[key], key)
        self.assertEqual(allocations.get_allocation(self.unowned["id"])["state"], before_free["state"])
        self.assertEqual(allocations.get_inbox_profile(self.old["id"]), self.old)
        self.assertEqual(allocations.get_parent("icloud_hide", self.parent)["derivation_policy"]["inbox_profile_id"], receipt["new_profile_id"])
        self.assertEqual(self.plan()["allocation_count"], 0)
        rollback_cutover(receipt)
        self.assertEqual(allocations.get_allocation(self.child["id"]), before_child)
        self.assertEqual(allocations.get_allocation(self.unowned["id"]), before_free)
        self.assertEqual(allocations.get_parent("icloud_hide", self.parent)["derivation_policy"]["inbox_profile_id"], self.old["id"])
        rollback_cutover(receipt)

    def test_stale_plan_rejects_concurrent_route_change_without_partial_updates(self):
        from core.storage.email_inbox_cutover import apply_cutover
        plan = self.plan()
        another = allocations.create_inbox_profile(inbox_key="other", connector="forward_imap", credential_ref="OTHER_KEY", inbox_locator={"email": "other@example.test", "server": "imap.example.test"})
        record_store.patch_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, self.child["id"], {"inbox_profile_id": another["id"]})
        with self.assertRaisesRegex(RuntimeError, "email_cutover_route_changed"):
            apply_cutover(plan)
        self.assertEqual(allocations.get_allocation(self.unowned["id"])["inbox_profile_id"], self.old["id"])
        self.assertEqual(len(allocations.list_inbox_profiles()), 2)

    def test_invalid_plan_or_receipt_is_rejected_before_any_route_change(self):
        from core.storage.email_inbox_cutover import apply_cutover, rollback_cutover
        plan = self.plan()
        plan["locator"]["api_base"] = "invalid"
        with self.assertRaisesRegex(ValueError, "email_cutover_target_invalid"):
            apply_cutover(plan)
        with self.assertRaisesRegex(ValueError, "email_cutover_target_invalid"):
            rollback_cutover({"version": 9})
        self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], self.old["id"])

    def test_cli_defaults_to_read_only_without_writing_secret_or_profile(self):
        from config import email as cfg
        from core import email_derivation
        from core.storage import email_inbox_cutover as cutover
        from tools.migrate_hme_inbox_to_butler import main
        original_plan = cutover.plan_cutover

        def checked_plan(**kwargs):
            self.assertEqual(kwargs["conn"].execute("SHOW transaction_read_only").fetchone()["transaction_read_only"], "on")
            return original_plan(**kwargs)

        output = io.StringIO()
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE="https://butler.test/v1", EMAIL_BUTLER_API_KEY="test-key",
                ICLOUD_HME_FORWARD_IMAP_EMAIL="final@example.test"), patch.object(
                email_derivation, "_save_profile_secret", side_effect=AssertionError("预览不能写密钥")), patch.object(
                record_store, "init", side_effect=AssertionError("预览不能初始化表")), patch.object(
                cutover, "plan_cutover", side_effect=checked_plan), contextlib.redirect_stdout(output):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(output.getvalue()), {"dry_run": True, "allocation_count": 2, "parent_count": 1})
        self.assertEqual(len(allocations.list_inbox_profiles()), 1)

    def test_cli_apply_writes_private_receipt_and_explicit_rollback_restores_routes(self):
        from config import email as cfg
        from core import email_derivation
        from tools.migrate_hme_inbox_to_butler import main
        with tempfile.TemporaryDirectory() as directory, patch.multiple(cfg, EMAIL_BUTLER_API_BASE="https://butler.test/v1",
                EMAIL_BUTLER_API_KEY="test-key", ICLOUD_HME_FORWARD_IMAP_EMAIL="final@example.test"), patch.object(
                email_derivation, "_save_profile_secret"), contextlib.redirect_stdout(io.StringIO()):
            receipt = Path(directory) / "receipt.json"
            self.assertEqual(main(["--apply", "--receipt", str(receipt)]), 0)
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
            current = allocations.get_allocation(self.child["id"])["inbox_profile_id"]
            self.assertNotEqual(current, self.old["id"])
            self.assertEqual(main(["--rollback", str(receipt)]), 0)
            self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], current)
            self.assertEqual(main(["--apply", "--rollback", str(receipt)]), 0)
            self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], self.old["id"])


if __name__ == "__main__":
    unittest.main()
