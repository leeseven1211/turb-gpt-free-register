# -*- coding: utf-8 -*-
"""受控收件路由迁移只改变路由，保留业务身份和使用状态。"""
import unittest
import contextlib
import io
import json
import tempfile
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from core.storage import records as record_store
from core.storage.email import address_allocations as allocations
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

    def plan(self, **kwargs):
        from core.storage.email.inbox_cutover import plan_cutover
        return plan_cutover(api_base="https://butler.example.test/v1", mailbox_email="final@example.test",
            credential_ref="EMAIL_DERIVATION_BUTLER_SECRET_TEST", **kwargs)

    def test_opt_in_pins_only_unpinned_parents_and_restores_missing_or_null_routes_exactly(self):
        from core.storage.email.inbox_cutover import apply_cutover, rollback_cutover
        unpinned = []
        for index, extra in enumerate(({}, {"derivation_policy": None},
                {"derivation_policy": {"enabled": False, "max_children": 7}},
                {"derivation_policy": {"inbox_profile_id": None, "custom": {"keep": [1, 2]}}})):
            unpinned.append(record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
                "email": f"unprofiled{index}@icloud.com", "status": "used", "account_id": "old-source",
                "registered_services": ["openai"], "email_invalid": True, "private_metadata": {"keep": True}, **extra}))
        protected = []
        for connector in ("forward_butler", "imap"):
            profile = allocations.create_inbox_profile(inbox_key=f"protected-{connector}", connector=connector,
                credential_ref="KEEP_KEY", inbox_locator={"email": "keep@example.test"})
            protected.append(record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
                "email": f"protected-{connector}@icloud.com", "status": "used",
                "derivation_policy": {"inbox_profile_id": profile["id"], "custom": "keep"}}))
        before = {row_id: allocations.get_parent("icloud_hide", row_id) for row_id in unpinned + protected}
        self.assertEqual(self.plan()["parent_count"], 1, "默认不能扩大迁移范围")
        plan = self.plan(include_unpinned_parents=True)
        self.assertEqual(plan["parent_count"], 5)
        self.assertEqual(plan["allocation_count"], 2)
        self.assertEqual({row["id"] for row in plan["parents"]}, {self.parent, *unpinned})
        receipt = apply_cutover(plan)
        for row_id in unpinned:
            current = allocations.get_parent("icloud_hide", row_id)
            self.assertEqual(current["derivation_policy"]["inbox_profile_id"], receipt["new_profile_id"])
            for key, value in before[row_id].items():
                if key != "derivation_policy":
                    self.assertEqual(current[key], value, key)
            old_policy = before[row_id].get("derivation_policy") or {}
            for key, value in old_policy.items():
                if key != "inbox_profile_id":
                    self.assertEqual(current["derivation_policy"][key], value, key)
        for row_id in protected:
            self.assertEqual(allocations.get_parent("icloud_hide", row_id), before[row_id])
        rollback_cutover(receipt)
        rollback_cutover(receipt)
        for row_id, value in before.items():
            self.assertEqual(allocations.get_parent("icloud_hide", row_id), value)

    def test_unpinned_snapshot_rejects_missing_to_null_route_change_before_writing(self):
        from core.storage.email.inbox_cutover import apply_cutover
        parent = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "unpinned@icloud.com", "derivation_policy": {"custom": "keep"}})
        plan = self.plan(include_unpinned_parents=True)
        record_store.patch_row(record_store.ICLOUD_HIDE_POOL, parent,
            {"derivation_policy": {"custom": "keep", "inbox_profile_id": None}})
        with self.assertRaisesRegex(RuntimeError, "email_cutover_route_changed"):
            apply_cutover(plan)
        self.assertEqual(len(allocations.list_inbox_profiles()), 1)
        self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], self.old["id"])

    def test_rollback_does_not_remove_concurrent_policy_fields_when_original_policy_was_missing(self):
        from core.storage.email.inbox_cutover import apply_cutover, rollback_cutover
        parent = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {"email": "unpinned@icloud.com"})
        receipt = apply_cutover(self.plan(include_unpinned_parents=True))
        record_store.patch_row(record_store.ICLOUD_HIDE_POOL, parent,
            {"derivation_policy": {"inbox_profile_id": receipt["new_profile_id"], "new_setting": True}})
        with self.assertRaisesRegex(RuntimeError, "email_cutover_route_changed"):
            rollback_cutover(receipt)
        self.assertTrue(allocations.get_parent("icloud_hide", parent)["derivation_policy"]["new_setting"])
        self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], receipt["new_profile_id"])

    def test_cli_unpinned_opt_in_is_read_only_and_preserves_default_scope(self):
        from config import email as cfg
        from core.email import derivation as email_derivation
        from tools.migrations.migrate_hme_inbox_to_butler import main
        parent = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {"email": "unpinned@icloud.com"})
        before = allocations.get_parent("icloud_hide", parent)
        output = io.StringIO()
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE="https://butler.test/v1", EMAIL_BUTLER_API_KEY="test-key",
                ICLOUD_HME_FORWARD_IMAP_EMAIL="final@example.test"), patch.object(
                email_derivation, "_save_profile_secret", side_effect=AssertionError("预览不能写密钥")), patch.object(
                record_store, "init", side_effect=AssertionError("预览不能初始化表")), contextlib.redirect_stdout(output):
            self.assertEqual(main(["--include-unpinned-parents"]), 0)
        self.assertEqual(json.loads(output.getvalue()), {"dry_run": True, "allocation_count": 2, "parent_count": 2})
        self.assertEqual(allocations.get_parent("icloud_hide", parent), before)

    def test_unpinned_receipt_requires_exact_original_route_metadata(self):
        from core.storage.email.inbox_cutover import apply_cutover, rollback_cutover
        record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {"email": "unpinned@icloud.com"})
        receipt = apply_cutover(self.plan(include_unpinned_parents=True))
        for missing in ("old_policy_state", "old_profile_present", "old_profile_id"):
            with self.subTest(missing=missing):
                invalid = json.loads(json.dumps(receipt))
                del invalid["parents"][-1][missing]
                with self.assertRaisesRegex(ValueError, "email_cutover_target_invalid"):
                    rollback_cutover(invalid)
                self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], receipt["new_profile_id"])

    def test_dry_run_makes_no_profile_or_business_changes(self):
        before_profiles = allocations.list_inbox_profiles()
        before_child = allocations.get_allocation(self.child["id"])
        plan = self.plan()
        self.assertEqual(plan["allocation_count"], 2)
        self.assertEqual(plan["parent_count"], 1)
        self.assertEqual(allocations.list_inbox_profiles(), before_profiles)
        self.assertEqual(allocations.get_allocation(self.child["id"]), before_child)

    def test_apply_and_rollback_preserve_states_owners_addresses_and_old_profile(self):
        from core.storage.email.inbox_cutover import apply_cutover, rollback_cutover
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
        from core.storage.email.inbox_cutover import apply_cutover
        plan = self.plan()
        another = allocations.create_inbox_profile(inbox_key="other", connector="forward_imap", credential_ref="OTHER_KEY", inbox_locator={"email": "other@example.test", "server": "imap.example.test"})
        record_store.patch_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, self.child["id"], {"inbox_profile_id": another["id"]})
        with self.assertRaisesRegex(RuntimeError, "email_cutover_route_changed"):
            apply_cutover(plan)
        self.assertEqual(allocations.get_allocation(self.unowned["id"])["inbox_profile_id"], self.old["id"])
        self.assertEqual(len(allocations.list_inbox_profiles()), 2)

    def test_invalid_plan_or_receipt_is_rejected_before_any_route_change(self):
        from core.storage.email.inbox_cutover import apply_cutover, rollback_cutover
        plan = self.plan()
        plan["locator"]["api_base"] = "invalid"
        with self.assertRaisesRegex(ValueError, "email_cutover_target_invalid"):
            apply_cutover(plan)
        with self.assertRaisesRegex(ValueError, "email_cutover_target_invalid"):
            rollback_cutover({"version": 9})
        self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], self.old["id"])

    def test_cli_defaults_to_read_only_without_writing_secret_or_profile(self):
        from config import email as cfg
        from core.email import derivation as email_derivation
        from core.storage.email import inbox_cutover as cutover
        from tools.migrations.migrate_hme_inbox_to_butler import main
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
        from core.email import derivation as email_derivation
        from tools.migrations.migrate_hme_inbox_to_butler import main
        with tempfile.TemporaryDirectory() as directory, patch.multiple(cfg, EMAIL_BUTLER_API_BASE="https://butler.test/v1",
                EMAIL_BUTLER_API_KEY="test-key", ICLOUD_HME_FORWARD_IMAP_EMAIL="final@example.test"), patch.object(
                email_derivation, "_save_profile_secret"), contextlib.redirect_stdout(io.StringIO()):
            receipt = Path(directory) / "receipt.json"
            self.assertEqual(main(["--apply", "--receipt", str(receipt)]), 0)
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
            current = allocations.get_allocation(self.child["id"])["inbox_profile_id"]
            self.assertNotEqual(current, self.old["id"])
            with patch.object(record_store, "init", side_effect=AssertionError("回滚预览不能初始化表")):
                self.assertEqual(main(["--rollback", str(receipt)]), 0)
            self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], current)
            self.assertEqual(main(["--apply", "--rollback", str(receipt)]), 0)
            self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], self.old["id"])

    def test_cold_cli_process_previews_applies_and_rolls_back_without_self_locking(self):
        """每次真实 CLI 都是新进程，不能依赖测试进程已预热的 ready 缓存。"""
        script = Path(__file__).resolve().parents[2] / "tools/migrations/migrate_hme_inbox_to_butler.py"
        runner = (
            "import runpy,sys; from pathlib import Path; from config import env_loader; "
            "env_loader._ENV_PATH=Path(sys.argv[1]); sys.argv=sys.argv[2:]; "
            "runpy.run_path(sys.argv[0],run_name='__main__')"
        )
        environment = dict(os.environ, PYTHON_DOTENV_DISABLED="1", EMAIL_BUTLER_API_BASE="https://butler.test/v1",
            EMAIL_BUTLER_API_KEY="test-key", ICLOUD_HME_FORWARD_IMAP_EMAIL="final@example.test",
            PGOPTIONS=f"-c search_path={self.schema} -c lock_timeout=1500 -c statement_timeout=6000")
        unpinned = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {"email": "unpinned@icloud.com"})
        before_unpinned = allocations.get_parent("icloud_hide", unpinned)
        with tempfile.TemporaryDirectory() as directory:
            temporary_env = Path(directory) / "isolated.env"
            receipt = Path(directory) / "receipt.json"

            def run(*arguments):
                completed = subprocess.run([sys.executable, "-c", runner, str(temporary_env), str(script), *arguments],
                    cwd=script.parents[2], env=environment, capture_output=True, text=True, timeout=25)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                return json.loads(completed.stdout)

            self.assertEqual(run(), {"dry_run": True, "allocation_count": 2, "parent_count": 1})
            self.assertFalse(temporary_env.exists(), "冷预览不能创建密钥文件")
            self.assertEqual(len(allocations.list_inbox_profiles()), 1)
            self.assertEqual(run("--apply", "--receipt", str(receipt)),
                {"dry_run": False, "allocation_count": 2, "parent_count": 1})
            self.assertTrue(receipt.exists())
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
            new_profile_id = allocations.get_allocation(self.child["id"])["inbox_profile_id"]
            self.assertNotEqual(new_profile_id, self.old["id"])
            self.assertEqual(run("--rollback", str(receipt)),
                {"dry_run": True, "rollback_allocations": 2, "rollback_parents": 1})
            self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], new_profile_id)
            self.assertEqual(run("--apply", "--rollback", str(receipt)),
                {"restored_allocations": 2, "restored_parents": 1})
            self.assertEqual(allocations.get_allocation(self.child["id"])["inbox_profile_id"], self.old["id"])
            self.assertEqual(run("--include-unpinned-parents"), {"dry_run": True, "allocation_count": 2, "parent_count": 2})
            self.assertEqual(allocations.get_parent("icloud_hide", unpinned), before_unpinned)
            receipt_v2 = Path(directory) / "receipt-v2.json"
            self.assertEqual(run("--include-unpinned-parents", "--apply", "--receipt", str(receipt_v2)),
                {"dry_run": False, "allocation_count": 2, "parent_count": 2})
            self.assertEqual(json.loads(receipt_v2.read_text())["version"], 2)
            self.assertEqual(run("--apply", "--rollback", str(receipt_v2)),
                {"restored_allocations": 2, "restored_parents": 2})
            self.assertEqual(allocations.get_parent("icloud_hide", unpinned), before_unpinned)


if __name__ == "__main__":
    unittest.main()
