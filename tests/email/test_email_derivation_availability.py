# -*- coding: utf-8 -*-
"""子地址容量、功能可用性和台账分页的 PostgreSQL 隔离回归。"""
from unittest.mock import patch
import os

from config import email as cfg
from core.email import derivation as service
from core.runtime import capabilities as feature_availability
from core.storage import records as record_store
from core.storage.email import address_allocations as store
from tests.support_pg import PostgresTestCase
from tests.support_legacy_derivation import seed_legacy_inventory


class EmailDerivationAvailabilityTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.scope = patch.multiple(cfg, USE_EMAIL_SERVICE=True, EMAIL_SOURCE="icloud_hide,outlook",
            EMAIL_DERIVATION_ENABLED=True, EMAIL_DERIVATION_SOURCES="icloud_hide,outlook",
            EMAIL_DERIVATION_MAX_CHILDREN=3, EMAIL_DERIVATION_TAG_LENGTH=6,
            ICLOUD_HME_API_BASE="http://127.0.0.1:8081", ICLOUD_HME_ACCOUNT_ID="",
            ICLOUD_HME_AUTO_CREATE=False, ICLOUD_HME_INBOX_MODE="forward_imap", ICLOUD_HME_BUTLER_BRIDGE_ENABLED=False,
            ICLOUD_HME_FORWARD_IMAP_SERVER="imap.example.test", ICLOUD_HME_FORWARD_IMAP_PORT=993,
            ICLOUD_HME_FORWARD_IMAP_EMAIL="sink@example.test", ICLOUD_HME_FORWARD_IMAP_PASSWORD="test-app-password")
        self.scope.start()
        self.addCleanup(self.scope.stop)
        self.secret_scope = patch.dict(os.environ, {"env:TEST_PASSWORD": "test-inbox-password"})
        self.secret_scope.start()
        self.addCleanup(self.secret_scope.stop)
        self.parent = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "parent@icloud.test", "status": "used", "account_id": "test-apple", "remote_active": True,
            # 合法中转链路不能按最终 IMAP 邮箱不同而误判不可用。
            "forward_to_email": "forwarding-hop@example.test",
        })
        self.profile = store.create_inbox_profile(inbox_key="test-forward", connector="forward_imap",
            credential_ref="env:TEST_PASSWORD", inbox_locator={"server": "imap.example.test", "email": "sink@example.test"})

    def allocate(self, number, **kwargs):
        return store.allocate_address(source="icloud_hide", acquisition_id=f"test:{number}",
            owner_kind="registration_root", owner_id=number, inbox_profile_id=self.profile["id"], **kwargs)

    def seed_stock(self, count=3, request_id="availability-stock", **kwargs):
        return seed_legacy_inventory("icloud_hide", count, request_id, inbox_profile_id=self.profile["id"], **kwargs)

    def test_bridge_readiness_uses_butler_even_without_original_or_child_stock(self):
        with patch.multiple(cfg, ICLOUD_HME_BUTLER_BRIDGE_ENABLED=True,
            EMAIL_BUTLER_API_BASE="https://butler.example.test/v1", EMAIL_BUTLER_API_KEY="fixture-key",
            ICLOUD_HME_API_BASE="", ICLOUD_HME_FORWARD_IMAP_EMAIL="", ICLOUD_HME_FORWARD_IMAP_PASSWORD=""), patch(
            "core.db.icloud_hide_email_pool_summary", side_effect=AssertionError("桥接不读本地库存")
        ), patch("core.email.icloud_hide.client.sync_aliases", side_effect=AssertionError("桥接不访问sidecar")):
            readiness = feature_availability.email_source_availability()["icloud_hide"]
        self.assertTrue(readiness["enabled"], readiness)
        self.assertEqual(store.list_allocations(), [])

    def test_fixed_history_route_restores_when_current_sidecar_and_global_imap_are_empty(self):
        child = self.allocate(1)
        with patch.multiple(cfg, ICLOUD_HME_API_BASE="", ICLOUD_HME_INBOX_MODE="sidecar",
            ICLOUD_HME_FORWARD_IMAP_EMAIL="", ICLOUD_HME_FORWARD_IMAP_PASSWORD="",
            EMAIL_DERIVATION_ENABLED=False), patch.object(service, "_forward_profile", side_effect=AssertionError("历史恢复不能重建路由")):
            route = service.restore_address(child["address"], source="icloud_hide")
            restored = service.acquire_address("icloud_hide", owner_kind="registration_root", owner_id=1, acquisition_id="test:1")
        self.assertEqual(route["profile"]["id"], self.profile["id"])
        self.assertEqual(route["exact_target"], child["address"])
        self.assertEqual(restored, child["address"])

    def test_historical_capacity_estimate_excludes_invalid_mothers_for_both_sources(self):
        self.assertEqual(service.generation_capacity_summary("icloud_hide")["remaining"], 3)
        record_store.patch_row(record_store.ICLOUD_HIDE_POOL, self.parent, {"email_invalid": True})
        self.assertEqual(service.generation_capacity_summary("icloud_hide")["remaining"], 0)
        self.assertEqual(service.generation_capacity_summary("icloud_hide")["parent_count"], 0)

        outlook = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "invalid-parent@example.test", "status": "used",
            "client_id": "synthetic-client", "refresh_token": "synthetic-refresh",
        })
        self.assertEqual(service.generation_capacity_summary("outlook")["remaining"], 3)
        record_store.patch_row(record_store.OUTLOOK_POOL, outlook, {"email_invalid": True})
        self.assertEqual(service.generation_capacity_summary("outlook")["remaining"], 0)

        record_store.patch_row(record_store.ICLOUD_HIDE_POOL, self.parent, {"email_invalid": False})
        self.assertEqual(service.generation_capacity_summary("icloud_hide")["remaining"], 3)

    def test_terminal_history_consumes_quota_but_raising_legacy_limit_does_not_reopen_generation(self):
        children = [self.allocate(number) for number in range(1, 4)]
        store.mark_allocation_state(children[0]["id"], "used")
        store.mark_allocation_state(children[1]["id"], "replaced")
        store.mark_allocation_state(children[2]["id"], "retired")
        self.assertEqual(service.generation_capacity_summary("icloud_hide")["remaining"], 0)
        with patch.object(cfg, "EMAIL_DERIVATION_MAX_CHILDREN", 5):
            self.assertEqual(service.generation_capacity_summary("icloud_hide")["remaining"], 2)
            with self.assertRaisesRegex(service.EmailDerivationError, "Butler"):
                service.generate_inventory("icloud_hide", 1, "no-reopen-after-limit-change")
        store.configure_parent("icloud_hide", self.parent, max_children=4)
        with patch.object(cfg, "EMAIL_DERIVATION_MAX_CHILDREN", 10):
            self.assertEqual(service.generation_capacity_summary("icloud_hide")["remaining"], 1)

    def test_invalid_parent_keeps_address_history_without_available_derivation_slots(self):
        child = self.allocate(1)
        record_store.patch_row(record_store.ICLOUD_HIDE_POOL, self.parent, {"email_invalid": True})

        summary = service.public_summary("icloud_hide")

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["parent_count"], 1)
        self.assertEqual(summary["parents"][0]["remaining"], 0)
        self.assertEqual(store.find_allocation(address=child["address"])["state"], "reserved")

    def test_capacity_excludes_disabled_archived_inactive_tagged_and_missing_account_mothers(self):
        examples = [
            {"status": "disabled"}, {"status": "failed"}, {"archived": True}, {"remote_active": False},
            {"derivation_policy": {"enabled": False}}, {"account_id": ""},
            {"email": "already+tagged@icloud.test"}, {"email": "x" * 59 + "@icloud.test"},
        ]
        for index, values in enumerate(examples):
            record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
                "email": f"unhealthy-{index}@icloud.test", "status": "used", "account_id": "test-apple", **values,
            })
        self.assertEqual(service.generation_capacity_summary("icloud_hide")["remaining"], 3)
        self.assertEqual(service.generation_capacity_summary("icloud_hide")["parent_count"], 1)
        with patch.object(cfg, "ICLOUD_HME_ACCOUNT_ID", "other-apple"):
            self.assertEqual(service.generation_capacity_summary("icloud_hide")["remaining"], 0)

    def test_legacy_route_capacity_requires_complete_exact_receipt_configuration(self):
        for values in ({"ICLOUD_HME_INBOX_MODE": "sidecar"}, {"ICLOUD_HME_FORWARD_IMAP_PASSWORD": ""},
                       {"ICLOUD_HME_FORWARD_IMAP_EMAIL": ""}, {"ICLOUD_HME_FORWARD_IMAP_SERVER": ""},
                       {"ICLOUD_HME_FORWARD_IMAP_PORT": 70000}):
            with self.subTest(values=values), patch.multiple(cfg, **values):
                capacity = service.generation_capacity_summary("icloud_hide")
                self.assertEqual(capacity["remaining"], 0)
                self.assertTrue(capacity["reason"])

    def test_outlook_history_uses_original_oauth_and_child_stock_does_not_enable_new_source(self):
        parent = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "outlook@example.test", "status": "replaced", "client_id": "test-client", "refresh_token": "test-refresh",
        })
        record_store.insert_row(record_store.OUTLOOK_POOL, {"email": "empty@example.test", "status": "used"})
        child = store.allocate_address(source="outlook", acquisition_id="outlook:test", owner_kind="registration_root", owner_id=1,
                                      profile_factory=service._outlook_profile)
        self.assertTrue(child["address"].startswith("outlook+"))
        seed_legacy_inventory("outlook", 2, "outlook-remaining", profile_factory=service._outlook_profile)
        self.assertEqual(service.capacity_summary("outlook")["remaining"], 2)
        self.assertFalse(feature_availability.email_source_availability()["outlook"]["enabled"])

        def fetch(account, **kwargs):
            self.assertEqual((account.email, account.client_id, account.refresh_token),
                ("outlook@example.test", "test-client", "test-refresh"))
            self.assertEqual(kwargs["target_email"], child["address"])
            self.assertEqual(kwargs["after_ts"], 10)
            return "123456"

        with patch("core.email.outlook.client.fetch_otp_with_account", side_effect=fetch):
            self.assertEqual(service.fetch_bound_otp(child["address"], after_ts=10), "123456")
        record_store.patch_row(record_store.OUTLOOK_POOL, parent, {"status": "available"})
        self.assertTrue(feature_availability.email_source_availability()["outlook"]["enabled"])

    def test_legacy_outlook_keys_fallback_when_canonical_values_are_blank(self):
        legacy_id = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "legacy@example.test", "status": "used", "client_id": " ", "refresh_token": "",
            "clientId": "test-legacy-client", "refreshToken": "test-legacy-refresh",
        })
        record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "empty-legacy@example.test", "status": "used", "client_id": " ", "refresh_token": "",
            "clientId": "test-legacy-client", "refreshToken": " ",
        })
        capacity = service.generation_capacity_summary("outlook")
        self.assertEqual(capacity["remaining"], 3)
        self.assertEqual(capacity["parent_count"], 1)
        child = store.allocate_address(source="outlook", acquisition_id="outlook:legacy", owner_kind="registration_root",
            owner_id=1, profile_factory=service._outlook_profile)
        self.assertIsNotNone(child)
        self.assertEqual(child["parent_id"], legacy_id)
        self.assertEqual(service.generation_capacity_summary("outlook")["remaining"], 2)

    def test_legacy_switch_does_not_control_butler_source_readiness(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), patch.multiple(cfg, EMAIL_SOURCE="email_butler,icloud_hide",
                EMAIL_DERIVATION_ENABLED=enabled, EMAIL_DERIVATION_SOURCES="outlook",
                ICLOUD_HME_BUTLER_BRIDGE_ENABLED=True, ICLOUD_HME_API_BASE="",
                EMAIL_BUTLER_API_BASE="https://butler.example.test/v1", EMAIL_BUTLER_API_KEY="fixture-key"):
                readiness = feature_availability.email_source_availability()
                self.assertTrue(readiness["email_butler"]["enabled"])
                self.assertTrue(readiness["icloud_hide"]["enabled"])
                with self.assertRaisesRegex(service.EmailDerivationError, "Butler"):
                    service.acquire_address("outlook", owner_kind="registration_root", owner_id="new", acquisition_id="new")

    def test_retired_explicit_profile_is_not_counted_for_new_allocations(self):
        store.configure_parent("icloud_hide", self.parent, inbox_profile_id=self.profile["id"])
        store.retire_inbox_profile(self.profile["id"])
        self.assertEqual(service.generation_capacity_summary("icloud_hide")["remaining"], 0)

    def test_summary_aggregates_without_loading_children_or_one_query_per_parent(self):
        first = self.allocate(1)
        second_parent = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": "second@icloud.test", "status": "used", "account_id": "test-apple",
        })
        self.allocate(2, parent_id=second_parent)
        with patch.object(store, "list_allocations", side_effect=AssertionError("概况不能拉完整子地址台账")), patch.object(
            store, "get_parent", side_effect=AssertionError("概况不能逐母资源查询")):
            summary = service.public_summary("icloud_hide")
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["parent_count"], 2)
        self.assertEqual(summary["parents"][0]["parent_email"], first["parent_address"])
        self.assertEqual([row["remaining"] for row in summary["parents"]], [2, 2])
        self.assertNotIn("credential_ref", str(summary))

    def test_list_uses_sql_offset_limit_and_total_not_in_memory_pagination(self):
        store.configure_parent("icloud_hide", self.parent, max_children=5)
        children = [self.allocate(number) for number in range(1, 6)]
        with patch.object(store, "list_allocations", wraps=store.list_allocations) as list_rows:
            page = service.list_allocations("icloud_hide", parent_id=self.parent, page=2, page_size=2)
        self.assertEqual(page["total"], 5)
        self.assertEqual([row["email"] for row in page["items"]], [row["address"] for row in children[2:4]])
        self.assertEqual(list_rows.call_args.kwargs["offset"], 2)
        self.assertEqual(list_rows.call_args.kwargs["limit"], 2)
        self.assertEqual(service.list_allocations("icloud_hide", page=4, page_size=2)["items"], [])

    def test_jobs_bridge_submission_has_no_local_capacity_or_sidecar_dependency(self):
        from webui.app import create_app
        self.seed_stock()
        client = create_app(auth_code="test-auth").test_client()
        with patch.multiple(cfg, ICLOUD_HME_API_BASE="", ICLOUD_HME_BUTLER_BRIDGE_ENABLED=True,
            EMAIL_BUTLER_API_BASE="https://butler.example.test/v1", EMAIL_BUTLER_API_KEY="fixture-key"), patch(
            "core.email.icloud_hide.client.sync_aliases", side_effect=AssertionError("桥接任务不应同步sidecar")
        ), patch.object(service, "capacity_summary", side_effect=AssertionError("桥接不读取本地子库存")), patch(
            "core.db.icloud_hide_email_pool_summary", side_effect=AssertionError("桥接不读取本地母库存")
        ), patch("webui.app.svc.submit_registration", return_value=[{"id": 1}]) as submit:
            for count in (3, 4):
                with self.subTest(count=count):
                    response = client.post("/api/jobs", headers={"X-Auth-Code": "test-auth"},
                        json={"count": count, "workers": 1, "email_source": "icloud_hide"})
                    self.assertEqual(response.status_code, 200, response.get_json())
                    self.assertEqual(response.get_json()["warning"], "")
                    submit.assert_called_with(count=count, email_source="icloud_hide", workers=1)
