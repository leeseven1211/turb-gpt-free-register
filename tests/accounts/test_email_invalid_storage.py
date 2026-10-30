"""邮箱失效独立事实、关联范围与事务竞态回归。"""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

from core import db
from core.storage import records as rs
from tests.support_pg import PostgresTestCase


class EmailInvalidStorageTests(PostgresTestCase):
    def setUp(self):
        rs.init()

    def command(self, *args, **kwargs):
        command = getattr(db, "set_accounts_email_invalid", None)
        self.assertTrue(callable(command), "缺少独立邮箱失效存储命令")
        return command(*args, **kwargs)

    def pool(self, email="parent@example.test", *, group="old-subaccount-4", **extra):
        return rs.insert_row(rs.ICLOUD_HIDE_POOL, {
            "email": email, "account_id": group, "status": "used", "remote_active": True, **extra,
        })

    def allocation(self, parent_id, address="parent+child@example.test", **extra):
        parent = rs.get_row(rs.ICLOUD_HIDE_POOL, parent_id)
        return rs.insert_row(rs.EMAIL_ADDRESS_ALLOCATIONS, {
            "address": address, "address_norm": address.lower(), "source": "icloud_hide",
            "parent_kind": rs.ICLOUD_HIDE_POOL.name, "parent_id": parent_id,
            "parent_address": parent["email"], "inbox_profile_id": 1,
            "strategy": "plus_tag", "tag": address.split("+")[1].split("@")[0],
            "acquisition_id": "test:" + address, "owner_kind": "registration_root",
            "owner_id": address, "state": "reserved", **extra,
        })

    def account(self, email, **extra):
        return rs.insert_row(rs.ACCOUNTS, {
            "email": email, "email_source": "icloud_hide", "access_token": "synthetic-old", **extra,
        })

    def test_new_accounts_have_independent_false_default(self):
        account_id = self.account("default@example.test")
        self.assertIs(rs.get_row(rs.ACCOUNTS, account_id).get("email_invalid"), False)

    def test_group_marks_actual_family_and_preserves_business_states(self):
        parent_id = self.pool()
        unused_id = self.pool("unused@example.test", status="available")
        other_parent = self.pool("other@example.test", group="other-subaccount")
        direct_id = self.account("parent@example.test", account_status="deactivated", codex_status="deactivated")
        child_id = self.account("parent+child@example.test", account_status="active", codex_status="success")
        binding_id = self.allocation(parent_id, account_id=child_id, state="used")
        changed_id = self.account("changed@example.test", email_source="outlook")
        old_binding = self.allocation(parent_id, "parent+old@example.test", account_id=changed_id, state="replaced")
        guessed_id = self.account("parent+unrecorded@example.test")

        result = self.command(invalid=True, icloud_account_id="old-subaccount-4", reason="副号已失效")

        self.assertEqual(result["account_ids"], [direct_id, child_id])
        self.assertEqual(result["updated_count"], 2)
        self.assertEqual(result["pool_updated_count"], 2)
        self.assertEqual(result["allocation_updated_count"], 2)
        self.assertEqual(result["matched_account_count"], 2)
        self.assertNotIn("@example.test", str(result))
        for account_id in (direct_id, child_id):
            row = rs.get_row(rs.ACCOUNTS, account_id)
            self.assertIs(row["email_invalid"], True)
            self.assertEqual(row["email_invalid_email"], row["email"])
            self.assertEqual(row["access_token"], "synthetic-old")
        self.assertEqual(rs.get_row(rs.ACCOUNTS, direct_id)["account_status"], "deactivated")
        self.assertEqual(rs.get_row(rs.ACCOUNTS, child_id)["codex_status"], "success")
        for account_id in (changed_id, guessed_id):
            self.assertIs(rs.get_row(rs.ACCOUNTS, account_id)["email_invalid"], False)
        self.assertEqual(rs.get_row(rs.ICLOUD_HIDE_POOL, parent_id)["status"], "used")
        self.assertEqual(rs.get_row(rs.ICLOUD_HIDE_POOL, unused_id)["status"], "available")
        self.assertFalse(rs.get_row(rs.ICLOUD_HIDE_POOL, other_parent).get("email_invalid"))
        self.assertEqual(rs.get_row(rs.EMAIL_ADDRESS_ALLOCATIONS, binding_id)["state"], "used")
        self.assertEqual(rs.get_row(rs.EMAIL_ADDRESS_ALLOCATIONS, old_binding)["state"], "replaced")

    def test_clear_changes_only_email_facts(self):
        account_id = self.account("clear@example.test", account_status="deactivated", codex_status="deactivated")
        self.command([account_id], invalid=True, reason="邮箱失效")
        result = self.command([account_id], invalid=False)
        row = rs.get_row(rs.ACCOUNTS, account_id)
        self.assertEqual(result["updated_count"], 1)
        self.assertIs(row["email_invalid"], False)
        self.assertEqual(row["account_status"], "deactivated")
        self.assertEqual(row["codex_status"], "deactivated")
        self.assertEqual(row["access_token"], "synthetic-old")

    def test_expected_email_rejects_stale_identity(self):
        account_id = self.account("new@example.test")
        result = self.command([account_id], invalid=True, expected_emails={account_id: "old@example.test"})
        self.assertEqual(result["updated_count"], 0)
        self.assertEqual(result["skipped"], [{"id": account_id, "reason": "账号邮箱已变更"}])
        self.assertIs(rs.get_row(rs.ACCOUNTS, account_id)["email_invalid"], False)

    def test_new_token_writes_preserve_email_marker(self):
        account_id = self.account("token@example.test")
        self.command([account_id], invalid=True, reason="仍未恢复")
        db.insert_account(email="token@example.test", access_token="synthetic-second")
        db.update_account_session("token@example.test", "synthetic-third")
        db.update_account_token_metadata(account_id, "synthetic-third")
        row = rs.get_row(rs.ACCOUNTS, account_id)
        self.assertIs(row["email_invalid"], True)
        self.assertEqual(row["email_invalid_reason"], "仍未恢复")

    def test_confirmed_change_uses_target_validity_and_keeps_old_pool_fact(self):
        parent_id = self.pool()
        account_id = self.account("parent@example.test")
        self.command(invalid=True, icloud_account_id="old-subaccount-4", reason="旧邮箱失效")
        self.assertTrue(db.finish_account_email_change(
            account_id, ok=True, new_email="new@example.test", source="outlook", access_token="synthetic-new",
        ))
        row = rs.get_row(rs.ACCOUNTS, account_id)
        self.assertIs(row["email_invalid"], False)
        self.assertEqual(row["email"], "new@example.test")
        self.assertTrue(rs.get_row(rs.ICLOUD_HIDE_POOL, parent_id)["email_invalid"])

    def test_new_registration_inherits_parent_and_existing_allocation_marker(self):
        parent_id = self.pool()
        binding_id = self.allocation(parent_id)
        self.command(invalid=True, icloud_account_id="old-subaccount-4", reason="副号失效")
        parent_account = db.insert_account(email="parent@example.test", access_token="synthetic-parent", email_source="icloud_hide")
        child_account = db.insert_account(email="parent+child@example.test", access_token="synthetic-child", email_source="icloud_hide")
        for account_id in (parent_account, child_account):
            self.assertIs(rs.get_row(rs.ACCOUNTS, account_id)["email_invalid"], True)
        self.assertEqual(rs.get_row(rs.EMAIL_ADDRESS_ALLOCATIONS, binding_id)["state"], "used")

    def test_single_clear_keeps_broader_group_parent_marker(self):
        parent_id = self.pool()
        child_id = self.account("parent+child@example.test")
        self.allocation(parent_id, account_id=child_id, state="used")
        self.command(invalid=True, icloud_account_id="old-subaccount-4", reason="副号失效")
        self.command([child_id], invalid=False)
        self.assertIs(rs.get_row(rs.ACCOUNTS, child_id)["email_invalid"], False)
        self.assertIs(rs.get_row(rs.ICLOUD_HIDE_POOL, parent_id)["email_invalid"], True)

    def test_pool_failure_rolls_back_accounts_and_allocations(self):
        parent_id = self.pool()
        account_id = self.account("parent+child@example.test")
        binding_id = self.allocation(parent_id, account_id=account_id, state="used")
        original = rs.patch_row

        def fail_pool(spec, *args, **kwargs):
            if spec is rs.ICLOUD_HIDE_POOL:
                raise RuntimeError("模拟母邮箱写入失败")
            return original(spec, *args, **kwargs)

        with patch.object(rs, "patch_row", side_effect=fail_pool):
            with self.assertRaisesRegex(RuntimeError, "模拟母邮箱"):
                self.command(invalid=True, icloud_account_id="old-subaccount-4")
        self.assertIs(rs.get_row(rs.ACCOUNTS, account_id)["email_invalid"], False)
        self.assertFalse(rs.get_row(rs.EMAIL_ADDRESS_ALLOCATIONS, binding_id).get("email_invalid"))
        self.assertFalse(rs.get_row(rs.ICLOUD_HIDE_POOL, parent_id).get("email_invalid"))

    def test_invalid_parent_cannot_be_claimed_for_a_new_original_address(self):
        self.pool(status="available")
        self.command(invalid=True, icloud_account_id="old-subaccount-4")
        self.assertIsNone(db.claim_next_icloud_hide_email(account_id="old-subaccount-4"))
        summary = db.icloud_hide_email_pool_summary()
        self.assertEqual(summary["available"], 0)
        self.assertEqual(summary["email_invalid_count"], 1)
        self.assertEqual(summary["total"], 1)
        grouped = db.icloud_hide_email_pool_summary_by_account(["old-subaccount-4"])
        self.assertEqual(grouped[0]["available"], 0)

    def test_input_validation_is_strict_and_does_not_write(self):
        account_id = self.account("validation@example.test")
        for invalid in ("false", 1, None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.command([account_id], invalid=invalid)
        with self.assertRaises(ValueError):
            self.command([account_id], invalid=True, reason="失" * 301)
        with self.assertRaises(ValueError):
            self.command([account_id], invalid=True, icloud_account_id="old-subaccount-4")
        self.assertIs(rs.get_row(rs.ACCOUNTS, account_id)["email_invalid"], False)

    def test_invalid_outlook_parent_is_excluded_from_new_claims(self):
        self.seed(rs.OUTLOOK_POOL, [{"email": "outlook@example.test", "status": "available"}])
        account_id = self.account("outlook@example.test", email_source="outlook")
        self.command([account_id], invalid=True)
        self.assertIsNone(db.claim_next_outlook())

    def test_invalid_generic_parent_is_excluded_from_new_claims(self):
        pool_id = self.seed(rs.GENERIC_API_POOL, [{"email": "generic@example.test", "status": "available"}])[0]
        account_id = self.account("generic@example.test", email_source="generic_api")
        self.command([account_id], invalid=True)
        self.assertIs(rs.get_row(rs.GENERIC_API_POOL, pool_id).get("email_invalid"), True)
        self.assertIsNone(db.claim_next_generic_api_email())

    def test_invalid_domain_cannot_be_newly_claimed_but_original_context_recovers(self):
        from core.email import provider as email_provider

        pool_id = self.seed(rs.DOMAIN_POOL, [{"email": "domain@example.test", "status": "used"}])[0]
        account_id = self.account("domain@example.test", email_source="cloudflare_domain")
        self.command([account_id], invalid=True)
        self.assertIs(rs.get_row(rs.DOMAIN_POOL, pool_id).get("email_invalid"), True)
        with self.assertRaisesRegex(ValueError, "失效"):
            db.claim_next_domain_email("domain@example.test")
        self.assertEqual(email_provider.restore_email_context("domain@example.test", source="cloudflare_domain"), "cloudflare_domain")
        self.assertEqual(rs.get_row(rs.DOMAIN_POOL, pool_id)["status"], "used")

    def test_registered_material_import_inherits_parent_failure(self):
        for source, spec, material in (
            ("outlook", rs.OUTLOOK_POOL, {"password": "synthetic-password", "client_id": "synthetic-client", "refresh_token": "synthetic-refresh"}),
            ("generic_api", rs.GENERIC_API_POOL, {"code_url": "https://example.test/inbox"}),
        ):
            with self.subTest(source=source):
                email = source + "-import@example.test"
                self.seed(spec, [{"email": email, "status": "used", "email_invalid": True,
                                  "email_invalid_reason": "母邮箱不可用", "email_invalid_source": "manual"}])
                result = db.import_registered_email_accounts([{"email": email, **material}], source)
                self.assertEqual(result, (1, 0))
                self.assertIs(db.get_account_by_email(email)["email_invalid"], True)
                self.assertEqual(db.get_account_by_email(email)["email_invalid_reason"], "母邮箱不可用")

    def test_new_hme_alias_inherits_existing_group_scope_on_sync(self):
        self.pool()
        self.command(invalid=True, icloud_account_id="old-subaccount-4", reason="副号失效")
        db.sync_icloud_hide_aliases([{"email": "new-alias@example.test", "active": True}],
                                   "old-subaccount-4", full_snapshot=False)
        new_parent = db.get_icloud_hide_email_by_email("new-alias@example.test")
        self.assertIs(new_parent.get("email_invalid"), True)
        self.assertEqual(new_parent["email_invalid_email"], "new-alias@example.test")
        self.assertEqual(new_parent["email_invalid_reason"], "副号失效")
        self.assertIsNone(db.claim_next_icloud_hide_email(account_id="old-subaccount-4"))

    def test_single_account_scope_does_not_spread_to_new_hme_alias(self):
        self.pool()
        account_id = self.account("parent@example.test")
        self.command([account_id], invalid=True, reason="仅此邮箱失效")
        db.sync_icloud_hide_aliases([{"email": "new-alias@example.test", "active": True}],
                                   "old-subaccount-4", full_snapshot=False)
        self.assertFalse(db.get_icloud_hide_email_by_email("new-alias@example.test").get("email_invalid"))
        self.assertTrue(db.get_icloud_hide_email_by_email("parent@example.test")["email_invalid"])

    def test_expected_email_is_rechecked_after_waiting_for_account_lock(self):
        account_id = self.account("old@example.test")
        results, failures = [], []

        def mark():
            try:
                results.append(self.command([account_id], invalid=True, expected_emails={account_id: "old@example.test"}))
            except BaseException as exc:
                failures.append(exc)

        worker = threading.Thread(target=mark, daemon=True)
        waiting = False
        with rs.transaction() as blocker, blocker.cursor() as cur:
            cur.execute("SELECT pg_backend_pid() AS pid")
            blocker_pid = cur.fetchone()["pid"]
            rs.get_row(rs.ACCOUNTS, account_id, conn=blocker, for_update=True)
            worker.start()
            with rs._connect() as observer, observer.cursor() as poll:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    poll.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() "
                                 "AND %s=ANY(pg_blocking_pids(pid))", (blocker_pid,))
                    if poll.fetchone()["n"]:
                        waiting = True
                        break
                    time.sleep(0.01)
            rs.patch_row(rs.ACCOUNTS, account_id, {"email": "new@example.test"}, conn=blocker)
        worker.join(10)
        self.assertTrue(waiting, "标记线程未到达账号行锁")
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(results[0]["updated_count"], 0)
        self.assertEqual(rs.get_row(rs.ACCOUNTS, account_id)["email"], "new@example.test")
        self.assertIs(rs.get_row(rs.ACCOUNTS, account_id)["email_invalid"], False)

    def test_group_commit_precedes_confirmed_change_to_invalid_target(self):
        parent_id = self.pool()
        self.allocation(parent_id)
        account_id = self.account("old@example.test", email_source="outlook")
        paused, resume, changed = threading.Event(), threading.Event(), threading.Event()
        failures = []
        original = rs.patch_row

        def pause_pool(spec, *args, **kwargs):
            if spec is rs.ICLOUD_HIDE_POOL and threading.current_thread().name == "换绑标记线程":
                paused.set()
                if not resume.wait(8):
                    raise RuntimeError("等待测试放行超时")
            return original(spec, *args, **kwargs)

        def mark():
            try:
                self.command(invalid=True, icloud_account_id="old-subaccount-4")
            except BaseException as exc:
                failures.append(exc)

        def change():
            try:
                db.finish_account_email_change(account_id, ok=True, new_email="parent+child@example.test",
                                               source="icloud_hide", access_token="synthetic-new")
                changed.set()
            except BaseException as exc:
                failures.append(exc)

        with patch.object(rs, "patch_row", side_effect=pause_pool):
            marker = threading.Thread(target=mark, name="换绑标记线程", daemon=True)
            writer = threading.Thread(target=change, daemon=True)
            marker.start()
            try:
                self.assertTrue(paused.wait(8))
                writer.start()
                self.assertFalse(changed.wait(0.15), "打标事务提交前换绑绕过了共享锁")
            finally:
                resume.set()
                marker.join(10)
                if writer.ident is not None:
                    writer.join(10)
        self.assertFalse(marker.is_alive())
        self.assertFalse(writer.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(db.get_account(account_id)["email"], "parent+child@example.test")
        self.assertTrue(db.get_account(account_id)["email_invalid"])

    def test_group_commit_precedes_new_account_writeback(self):
        self.pool()
        paused, resume, inserted = threading.Event(), threading.Event(), threading.Event()
        failures = []
        original = rs.patch_row

        def pause_pool(spec, *args, **kwargs):
            if spec is rs.ICLOUD_HIDE_POOL and threading.current_thread().name == "标记线程":
                paused.set()
                if not resume.wait(8):
                    raise RuntimeError("等待测试放行超时")
            return original(spec, *args, **kwargs)

        def mark():
            try:
                self.command(invalid=True, icloud_account_id="old-subaccount-4")
            except BaseException as exc:
                failures.append(exc)

        def register():
            try:
                db.insert_account(email="parent@example.test", access_token="synthetic-new", email_source="icloud_hide")
                inserted.set()
            except BaseException as exc:
                failures.append(exc)

        with patch.object(rs, "patch_row", side_effect=pause_pool):
            marker = threading.Thread(target=mark, name="标记线程", daemon=True)
            writer = threading.Thread(target=register, daemon=True)
            marker.start()
            try:
                self.assertTrue(paused.wait(8))
                writer.start()
                self.assertFalse(inserted.wait(0.15), "打标事务提交前写回绕过了共享锁")
            finally:
                resume.set()
                marker.join(10)
                if writer.ident is not None:
                    writer.join(10)
        self.assertFalse(marker.is_alive())
        self.assertFalse(writer.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(db.get_account_by_email("parent@example.test")["email_invalid"])
