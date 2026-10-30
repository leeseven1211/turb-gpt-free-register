"""迁移前仓储事实、原子归属与退役服务入口的隔离回归。"""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import threading
import time

from config import email as cfg
from core.email import derivation as service
from core.storage import records as record_store, postgres as postgres_store
from core.storage.email import address_allocations as store
from tests.support_legacy_derivation import seed_legacy_generation_receipt, seed_legacy_inventory
from tests.support_pg import PostgresTestCase


class EmailDerivationInventoryTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.scope = patch.multiple(cfg, EMAIL_DERIVATION_ENABLED=True,
            EMAIL_DERIVATION_SOURCES="icloud_hide,outlook", EMAIL_DERIVATION_MAX_CHILDREN=3,
            EMAIL_DERIVATION_TAG_LENGTH=6, ICLOUD_HME_ACCOUNT_ID="")
        self.scope.start()
        self.addCleanup(self.scope.stop)
        self.parent = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "parent@example.test", "status": "used", "client_id": "client", "refresh_token": "refresh"})

    def seed_stock(self, count=3, request_id="legacy-stock", **kwargs):
        return seed_legacy_inventory("outlook", count, request_id,
            profile_factory=service._outlook_profile, **kwargs)

    def claim_legacy_stock(self, intent="root-1", **kwargs):
        """模拟迁移前仓储事实；生产 acquire_address 仅用于恢复已存在的意图。"""
        row = store.claim_address(source="outlook", owner_kind="registration_root", owner_id=intent,
            acquisition_id=intent, profile_validator=lambda profile: service._inventory_profile_usable(profile, "outlook"), **kwargs)
        return str(row["address"]) if row else None

    def test_old_generation_receipt_restores_after_claim_and_rejects_scope_changes(self):
        rows = self.seed_stock(2, "saved-request")
        self.assertEqual([row["state"] for row in rows], ["available", "available"])
        self.assertTrue(all(row.get("acquisition_id") is None and row.get("owner_kind") is None and row.get("owner_id") is None for row in rows))
        seed_legacy_generation_receipt("outlook", 2, "saved-request",
            {"requested": 2, "created": 2, "reused": 0, "shortfall": 0, "reason_code": "", "reason": ""})
        address = self.claim_legacy_stock()
        with patch.object(store, "allocate_address", side_effect=AssertionError("恢复不能生成新地址")):
            again = service.generate_inventory("outlook", 2, "saved-request")
        self.assertEqual((again["created"], again["reused"]), (0, 2))
        self.assertEqual(store.find_allocation(address=address)["generation_key"], rows[0]["generation_key"])
        self.assertEqual(store.allocation_summary()["total"], 2)
        with self.assertRaises(service.EmailDerivationError) as caught:
            service.generate_inventory("outlook", 3, "saved-request")
        self.assertEqual(caught.exception.code, "email_derivation_request_conflict")

    def test_new_local_claim_is_rejected_even_with_healthy_legacy_stock(self):
        self.seed_stock()
        with patch.object(store, "claim_address", side_effect=AssertionError("新意图不能领取本地库存")):
            with self.assertRaises(service.EmailDerivationError) as caught:
                service.acquire_address("outlook", owner_kind="registration_root", owner_id="new", acquisition_id="new")
        self.assertEqual(caught.exception.code, "email_derivation_source_disabled")
        self.assertIn("Butler", str(caught.exception))
        self.assertEqual(store.allocation_summary()["available"], 3)

    def test_legacy_parallel_claims_and_service_recovery_ignore_current_quota_and_health(self):
        self.seed_stock()
        with patch.object(cfg, "EMAIL_DERIVATION_MAX_CHILDREN", 1):
            with ThreadPoolExecutor(max_workers=3) as pool:
                addresses = list(pool.map(lambda number: self.claim_legacy_stock(f"root-{number}"), range(3)))
        self.assertEqual(len(set(addresses)), 3)
        record_store.patch_row(record_store.OUTLOOK_POOL, self.parent, {"email_invalid": True})
        with patch.object(cfg, "EMAIL_DERIVATION_ENABLED", False):
            restored = service.acquire_address("outlook", owner_kind="registration_root", owner_id="root-0", acquisition_id="root-0")
        self.assertEqual(restored, addresses[0])
        self.assertEqual(service.capacity_summary("outlook")["remaining"], 0)

    def test_parallel_rejected_profiles_release_candidate_locks_before_scanning_next_parent(self):
        second_parent = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "second@example.test", "status": "used", "client_id": "client", "refresh_token": "refresh"})
        for number, parent_id in enumerate((self.parent, second_parent, second_parent, self.parent)):
            self.seed_stock(1, f"interleaved-{number}", parent_id=parent_id)

        def concurrent_claims(prefix, healthy_parent=None):
            barrier, local = threading.Barrier(2), threading.local()

            def validate(profile):
                if not getattr(local, "ready", False):
                    local.ready = True
                    barrier.wait(timeout=5)
                    if str(profile["credential_ref"]).endswith(f":{second_parent}"):
                        time.sleep(.2)
                return (profile.get("inbox_locator") or {}).get("parent_id") == healthy_parent

            def claim(number):
                try:
                    return store.claim_address(source="outlook", acquisition_id=f"{prefix}-{number}",
                        owner_kind="registration_root", owner_id=f"{prefix}-{number}", profile_validator=validate)
                except Exception as exc:
                    return type(exc).__name__

            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(claim, range(2)))

        self.assertEqual(concurrent_claims("rejected"), [None, None])
        healthy_parent = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "healthy@example.test", "status": "used", "client_id": "client", "refresh_token": "refresh"})
        self.seed_stock(2, "healthy-after-rejected", parent_id=healthy_parent)
        results = concurrent_claims("accepted", healthy_parent)
        self.assertTrue(all(isinstance(row, dict) for row in results), str(results))
        self.assertEqual(len({row["id"] for row in results}), 2)
        self.assertTrue(all(row["parent_id"] == healthy_parent for row in results))
        for row in store.list_allocations(limit=4):
            self.assertEqual(row["state"], "available")
            self.assertIsNone(row.get("acquisition_id"))

    def test_legacy_ledger_concurrent_writes_keep_lifetime_quota_and_generation_identity(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda number: self.seed_stock(2, f"parallel-{number}"), range(4)))
        self.assertEqual(len({row["id"] for batch in results for row in batch}), 3)
        self.assertEqual(store.allocation_summary()["available"], 3)
        store.configure_parent("outlook", self.parent, max_children=5)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.seed_stock(2, "parallel-same"), range(4)))
        self.assertEqual(len({row["id"] for batch in results for row in batch}), 2)
        self.assertTrue(all(len(batch) == 2 for batch in results))
        self.assertEqual(store.allocation_summary()["total"], 5)

    def test_same_acquisition_concurrent_recovery_keeps_one_binding_and_job_attempt(self):
        from core.storage import registration
        registration.init()
        self.seed_stock()
        address = self.claim_legacy_stock("same-intent")
        job_id = record_store.insert_row(record_store.JOBS, {"job_uuid": "inventory-job", "batch_id": "inventory-batch", "status": "queued"})
        attempt = registration.ensure_attempt_for_job(job_id)
        with ThreadPoolExecutor(max_workers=4) as pool:
            addresses = list(pool.map(lambda _: service.acquire_address("outlook", owner_kind="registration_root", owner_id="same-intent",
                acquisition_id="same-intent", job_id=job_id, attempt_id=attempt["id"]), range(4)))
        self.assertEqual(set(addresses), {address})
        binding = store.find_allocation(address=address)
        self.assertEqual(record_store.get_row(record_store.JOBS, job_id)["email_address_id"], binding["id"])
        self.assertEqual(registration.get_attempt(attempt["id"])["email_snapshot"], address)
        self.assertEqual(record_store.list_rows(record_store.REGISTRATION_BATCH_EMAIL_CLAIMS)[0]["email"], address)
        self.assertEqual(store.allocation_summary()["available"], 2)

    def test_legacy_warehouse_health_checks_exclude_unhealthy_parent_and_retired_profile(self):
        self.seed_stock()
        self.assertEqual(service.capacity_summary("outlook")["remaining"], 3)
        for changes in ({"email_invalid": True}, {"archived": True}, {"remote_active": False},
                        {"status": "disabled"}, {"derivation_policy": {"enabled": False}}):
            with self.subTest(changes=changes):
                original = store.get_parent("outlook", self.parent)
                record_store.patch_row(record_store.OUTLOOK_POOL, self.parent, changes)
                self.assertEqual(service.capacity_summary("outlook")["remaining"], 0)
                self.assertIsNone(self.claim_legacy_stock())
                record_store.patch_row(record_store.OUTLOOK_POOL, self.parent, {key: original.get(key) for key in changes})
        store.retire_inbox_profile(store.list_allocations()[0]["inbox_profile_id"])
        self.assertEqual(service.capacity_summary("outlook")["remaining"], 0)
        self.assertIsNone(self.claim_legacy_stock())

    def test_legacy_storage_distinguishes_fixed_profile_failure_from_quota(self):
        self.seed_stock(1)
        store.retire_inbox_profile(store.list_allocations()[0]["inbox_profile_id"])
        failure = {}
        self.assertEqual(self.seed_stock(1, "retired-profile", failure=failure), [])
        self.assertEqual(failure["reason_code"], "email_derivation_profile_unavailable")

    def test_legacy_storage_reports_unhealthy_selected_parent(self):
        record_store.patch_row(record_store.OUTLOOK_POOL, self.parent, {"email_invalid": True})
        failure = {}
        self.assertEqual(self.seed_stock(1, parent_id=self.parent, failure=failure), [])
        self.assertEqual(failure["reason_code"], "email_derivation_parent_unavailable")

    def test_partial_old_request_keeps_result_when_more_capacity_is_added(self):
        rows = self.seed_stock(4, "partial-request")
        self.assertEqual(len(rows), 3)
        first = {"requested": 4, "created": 3, "reused": 0, "shortfall": 1,
            "reason_code": "email_derivation_capacity_exhausted", "reason": "历史额度已满"}
        seed_legacy_generation_receipt("outlook", 4, "partial-request", first)
        store.configure_parent("outlook", self.parent, max_children=5)
        with patch.object(store, "allocate_address", side_effect=AssertionError("旧请求不得补发")):
            again = service.generate_inventory("outlook", 4, "partial-request")
        self.assertEqual((again["created"], again["reused"], again["shortfall"]), (0, 3, 1))
        self.assertEqual((again["reason_code"], again["reason"]), (first["reason_code"], first["reason"]))
        with self.assertRaisesRegex(service.EmailDerivationError, "Butler"):
            service.generate_inventory("outlook", 1, "new-request")
        self.assertEqual(store.allocation_summary()["total"], 3)

    def test_zero_old_request_is_frozen_and_rejects_scope_changes(self):
        first = {"requested": 2, "created": 0, "reused": 0, "shortfall": 2,
            "reason_code": "email_derivation_parent_unavailable", "reason": "历史母邮箱不可用"}
        seed_legacy_generation_receipt("outlook", 2, "zero-request", first)
        with patch.object(store, "allocate_address", side_effect=AssertionError("原零结果请求不能再次生成")):
            again = service.generate_inventory("outlook", 2, "zero-request")
        self.assertEqual(again, first)
        with self.assertRaises(service.EmailDerivationError) as caught:
            service.generate_inventory("outlook", 1, "zero-request")
        self.assertEqual(caught.exception.code, "email_derivation_request_conflict")
        with self.assertRaisesRegex(service.EmailDerivationError, "Butler"):
            service.generate_inventory("outlook", 1, "new-zero-request")
        self.assertEqual(store.allocation_summary()["total"], 0)

    def test_saved_hme_profile_without_original_secret_is_never_claimed_by_warehouse(self):
        record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "mother@icloud.test", "status": "used", "account_id": "apple-test"})
        profile = store.create_inbox_profile(inbox_key="invalid-inbox", connector="forward_imap",
            credential_ref="TEST_PROFILE_ABSENT", inbox_locator={"server": "imap.example.test", "email": "old@example.test", "port": 993})
        seed_legacy_inventory("icloud_hide", 1, "missing-profile-secret", inbox_profile_id=profile["id"])
        with patch("config.env_loader.read_env_file", return_value={}), patch.dict("os.environ", {"TEST_PROFILE_ABSENT": ""}):
            self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 0)
            row = store.claim_address(source="icloud_hide", owner_kind="registration_root", owner_id="missing", acquisition_id="missing",
                profile_validator=lambda value: service._inventory_profile_usable(value, "icloud_hide"))
        self.assertIsNone(row)
        self.assertEqual(store.list_allocations()[0]["state"], "available")

    def test_legacy_storage_does_not_use_saved_profile_without_its_original_secret(self):
        record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "mother@icloud.test", "status": "used", "account_id": "apple-test"})
        profile = store.create_inbox_profile(inbox_key="old-inbox", connector="forward_imap",
            credential_ref="TEST_ABSENT_ORIGINAL_SECRET", inbox_locator={"server": "imap.example.test", "email": "old@example.test", "port": 993})
        failure = {}
        with patch("config.env_loader.read_env_file", return_value={}), patch.dict("os.environ", {"TEST_ABSENT_ORIGINAL_SECRET": ""}):
            rows = seed_legacy_inventory("icloud_hide", 1, "old-profile-no-secret", inbox_profile_id=profile["id"], failure=failure,
                profile_validator=lambda value: service._inventory_profile_usable(value, "icloud_hide"))
        self.assertEqual(rows, [])
        self.assertEqual(failure["reason_code"], "email_derivation_profile_unavailable")

    def test_unavailable_saved_route_has_stable_error_code(self):
        self.seed_stock(1)
        address = self.claim_legacy_stock()
        with patch.object(store, "get_inbox_profile", return_value=None):
            with self.assertRaises(service.EmailDerivationError) as caught:
                service.restore_address(address)
        self.assertEqual(caught.exception.code, "email_derivation_profile_unavailable")
        with patch("config.env_loader.read_env_file", return_value={}), patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(service.EmailDerivationError) as caught:
                service._profile_credentials({"credential_ref": "TEST_MISSING"})
        self.assertEqual(caught.exception.code, "email_derivation_profile_unavailable")

    def test_legacy_profile_builder_rejects_invalid_imap_port_before_any_secret_write(self):
        with patch.multiple(cfg, ICLOUD_HME_INBOX_MODE="forward_imap", ICLOUD_HME_FORWARD_IMAP_PORT=70000,
            ICLOUD_HME_FORWARD_IMAP_SERVER="imap.example.test", ICLOUD_HME_FORWARD_IMAP_EMAIL="sink@example.test",
            ICLOUD_HME_FORWARD_IMAP_PASSWORD="test-value"), patch.object(
                service, "_save_profile_secret", side_effect=AssertionError("无效端口不能写密钥")):
            with self.assertRaisesRegex(RuntimeError, "端口"):
                service._forward_profile()
        self.assertEqual(store.list_inbox_profiles(), [])

    def test_legacy_binding_failure_rolls_back_claim(self):
        self.seed_stock(1)
        with patch.object(store, "_bind_business", side_effect=RuntimeError("绑定失败")):
            with self.assertRaisesRegex(RuntimeError, "绑定失败"):
                self.claim_legacy_stock()
        row = store.list_allocations()[0]
        self.assertEqual(row["state"], "available")
        self.assertIsNone(row.get("acquisition_id"))

    def test_legacy_status_changes_never_recycle_assigned_address(self):
        self.assertEqual(len(self.seed_stock(5)), 3)
        rows = store.list_allocations()
        claimed = self.claim_legacy_stock()
        result = store.update_inventory_status([row["id"] for row in rows] + [999999], "disabled")
        self.assertEqual((result["updated"], result["skipped"]), (2, 2))
        self.assertEqual(store.find_allocation(address=claimed)["state"], "reserved")
        result = store.update_inventory_status([row["id"] for row in rows], "available")
        self.assertEqual((result["updated"], result["skipped"]), (2, 1))
        with self.assertRaises(ValueError):
            store.mark_allocation_state(rows[0]["id"], "available")

    def test_history_filters_are_based_on_stored_facts(self):
        self.seed_stock()
        address = self.claim_legacy_stock("root-search")
        rows = store.list_allocations()
        store.update_inventory_status([rows[1]["id"]], "disabled")
        result = service.list_allocations(source="outlook", q="parent+", parent_q="parent@", state="available")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["state"], "available")
        related = service.list_allocations(related_q="root-search")
        self.assertEqual([row["email"] for row in related["items"]], [address])
        self.assertEqual(service.list_allocations(created_from="2099-01-01")["total"], 0)
        self.assertEqual(service.list_allocations(created_to="2000-01-01")["total"], 0)

    def test_legacy_not_null_columns_are_migrated_without_touching_bound_rows(self):
        legacy = store.allocate_address(source="outlook", acquisition_id="legacy", owner_kind="registration_root",
            owner_id="legacy", profile_factory=service._outlook_profile)
        with record_store.transaction() as conn, conn.cursor() as cur:
            for column in ("acquisition_id", "owner_kind", "owner_id"):
                cur.execute(f'ALTER TABLE {postgres_store.qualified(record_store.EMAIL_ADDRESS_ALLOCATIONS.name)} ALTER COLUMN "{column}" SET NOT NULL')
        record_store.reset_ready()
        record_store.init()
        self.assertEqual(len(self.seed_stock(1)), 1)
        self.assertEqual(store.find_allocation(acquisition_id="legacy")["id"], legacy["id"])
        self.assertEqual(store.find_allocation(acquisition_id="legacy")["state"], "reserved")

    def test_hme_old_request_and_acquisition_restore_without_sync_or_current_profile(self):
        record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "mother@icloud.test", "status": "used", "account_id": "apple-test"})
        profile = store.create_inbox_profile(inbox_key="old-inbox", connector="forward_imap",
            credential_ref="TEST_OLD_INBOX", inbox_locator={"server": "imap.example.test", "email": "old@example.test", "port": 993})
        seed_legacy_inventory("icloud_hide", 2, "hme-request", inbox_profile_id=profile["id"])
        seed_legacy_generation_receipt("icloud_hide", 2, "hme-request",
            {"requested": 2, "created": 2, "reused": 0, "shortfall": 0, "reason_code": "", "reason": ""})
        original = store.claim_address(source="icloud_hide", owner_kind="registration_root", owner_id="hme-root", acquisition_id="hme-root")
        with patch.multiple(cfg, ICLOUD_HME_INBOX_MODE="forward_butler", ICLOUD_HME_BUTLER_BRIDGE_ENABLED=True), patch.object(
            service, "_forward_profile", side_effect=AssertionError("不能重建")
        ), patch("core.email.icloud_hide.client.sync_aliases", side_effect=AssertionError("不能同步")):
            again = service.generate_inventory("icloud_hide", 2, "hme-request")
            address = service.acquire_address("icloud_hide", owner_kind="registration_root", owner_id="hme-root", acquisition_id="hme-root")
        self.assertEqual(again["reused"], 2)
        self.assertEqual(address, original["address"])
        saved = record_store.list_rows(record_store.EMAIL_ADDRESS_GENERATION_REQUESTS)
        record_store.delete_rows(record_store.EMAIL_ADDRESS_GENERATION_REQUESTS, [row["id"] for row in saved])
        with patch.object(store, "allocate_address", side_effect=AssertionError("历史库存不能补发")):
            legacy = service.generate_inventory("icloud_hide", 2, "hme-request")
        self.assertEqual((legacy["created"], legacy["reused"]), (0, 2))

    def test_new_inventory_for_every_source_is_rejected_before_profile_or_upstream_calls(self):
        for source in ("icloud_hide", "outlook"):
            for mode, bridge in (("forward_butler", False), ("forward_imap", True), ("forward_imap", False)):
                with self.subTest(source=source, mode=mode, bridge=bridge), patch.multiple(cfg,
                    ICLOUD_HME_INBOX_MODE=mode, ICLOUD_HME_BUTLER_BRIDGE_ENABLED=bridge
                ), patch.object(service, "_forward_profile", side_effect=AssertionError("不能创建本机收件配置")), patch.object(
                    service, "_outlook_profile", side_effect=AssertionError("不能创建Outlook路由")
                ), patch("core.email.icloud_hide.client.sync_aliases", side_effect=AssertionError("不能同步 Apple")):
                    with self.assertRaises(service.EmailDerivationError) as caught:
                        service.generate_inventory(source, 1, f"blocked-{source}-{mode}-{bridge}")
                    self.assertEqual(caught.exception.code, "email_derivation_source_disabled")
                    self.assertIn("Butler", str(caught.exception))
        self.assertEqual(store.list_allocations(), [])
        self.assertEqual(store.list_inbox_profiles(), [])
        self.assertEqual(record_store.count_rows(record_store.EMAIL_ADDRESS_GENERATION_REQUESTS), 0)
