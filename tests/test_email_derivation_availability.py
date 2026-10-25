# -*- coding: utf-8 -*-
"""子地址容量、功能可用性和台账分页的 PostgreSQL 隔离回归。"""
from unittest.mock import patch

from config import email as cfg
from core import email_derivation as service, feature_availability, record_store
from core.storage import email_address_allocations as store
from tests.support_pg import PostgresTestCase


class EmailDerivationAvailabilityTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.scope = patch.multiple(cfg, USE_EMAIL_SERVICE=True, EMAIL_SOURCE="icloud_hide,outlook",
            EMAIL_DERIVATION_ENABLED=True, EMAIL_DERIVATION_SOURCES="icloud_hide,outlook",
            EMAIL_DERIVATION_MAX_CHILDREN=3, EMAIL_DERIVATION_TAG_LENGTH=6,
            ICLOUD_HME_API_BASE="http://127.0.0.1:8081", ICLOUD_HME_ACCOUNT_ID="",
            ICLOUD_HME_AUTO_CREATE=False, ICLOUD_HME_INBOX_MODE="forward_imap",
            ICLOUD_HME_FORWARD_IMAP_SERVER="imap.example.test", ICLOUD_HME_FORWARD_IMAP_PORT=993,
            ICLOUD_HME_FORWARD_IMAP_EMAIL="sink@example.test", ICLOUD_HME_FORWARD_IMAP_PASSWORD="test-app-password")
        self.scope.start()
        self.addCleanup(self.scope.stop)
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

    def test_used_parent_keeps_source_ready_without_any_original_available_row(self):
        with patch("core.icloud_hme_client.sync_aliases", side_effect=AssertionError("只读容量不能同步")), patch.object(
            service, "_save_profile_secret", side_effect=AssertionError("只读容量不能保存密钥")), patch.object(
            store, "create_inbox_profile", side_effect=AssertionError("只读容量不能创建路由")):
            capacity = service.capacity_summary("icloud_hide")
            readiness = feature_availability.email_source_availability()["icloud_hide"]
        self.assertEqual(capacity["remaining"], 3)
        self.assertEqual(capacity["parent_count"], 1)
        self.assertTrue(readiness["enabled"])

    def test_email_invalid_mothers_are_excluded_from_capacity_for_both_sources(self):
        self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 3)
        record_store.patch_row(record_store.ICLOUD_HIDE_POOL, self.parent, {"email_invalid": True})
        self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 0)
        self.assertEqual(service.capacity_summary("icloud_hide")["parent_count"], 0)

        outlook = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "invalid-parent@example.test", "status": "used",
            "client_id": "synthetic-client", "refresh_token": "synthetic-refresh",
        })
        self.assertEqual(service.capacity_summary("outlook")["remaining"], 3)
        record_store.patch_row(record_store.OUTLOOK_POOL, outlook, {"email_invalid": True})
        self.assertEqual(service.capacity_summary("outlook")["remaining"], 0)

        record_store.patch_row(record_store.ICLOUD_HIDE_POOL, self.parent, {"email_invalid": False})
        self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 3)

    def test_terminal_children_consume_quota_and_increasing_limit_exposes_only_new_slots(self):
        children = [self.allocate(number) for number in range(1, 4)]
        store.mark_allocation_state(children[0]["id"], "used")
        store.mark_allocation_state(children[1]["id"], "replaced")
        store.mark_allocation_state(children[2]["id"], "retired")
        self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 0)
        self.assertFalse(feature_availability.email_source_availability()["icloud_hide"]["enabled"])
        with patch.object(cfg, "EMAIL_DERIVATION_MAX_CHILDREN", 5):
            self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 2)
        store.configure_parent("icloud_hide", self.parent, max_children=4)
        with patch.object(cfg, "EMAIL_DERIVATION_MAX_CHILDREN", 10):
            self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 1)

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
        self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 3)
        self.assertEqual(service.capacity_summary("icloud_hide")["parent_count"], 1)
        with patch.object(cfg, "ICLOUD_HME_ACCOUNT_ID", "other-apple"):
            self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 0)

    def test_hme_requires_exact_route_configuration_even_if_original_pool_has_capacity(self):
        for values in ({"ICLOUD_HME_INBOX_MODE": "sidecar"}, {"ICLOUD_HME_FORWARD_IMAP_PASSWORD": ""},
                       {"ICLOUD_HME_FORWARD_IMAP_EMAIL": ""}, {"ICLOUD_HME_FORWARD_IMAP_SERVER": ""},
                       {"ICLOUD_HME_FORWARD_IMAP_PORT": 70000}):
            with self.subTest(values=values), patch.multiple(cfg, **values):
                capacity = service.capacity_summary("icloud_hide")
                self.assertEqual(capacity["remaining"], 0)
                self.assertTrue(capacity["reason"])
                self.assertFalse(feature_availability.email_source_availability()["icloud_hide"]["enabled"])

    def test_outlook_exact_adapter_uses_oauth_material_without_password(self):
        record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "outlook@example.test", "status": "replaced", "client_id": "test-client", "refresh_token": "test-refresh",
        })
        record_store.insert_row(record_store.OUTLOOK_POOL, {"email": "empty@example.test", "status": "used"})
        capacity = service.capacity_summary("outlook")
        self.assertEqual(capacity["remaining"], 3)
        self.assertEqual(capacity["parent_count"], 1)
        self.assertTrue(feature_availability.email_source_availability()["outlook"]["enabled"])
        child = store.allocate_address(source="outlook", acquisition_id="outlook:test", owner_kind="registration_root", owner_id=1,
                                      profile_factory=service._outlook_profile)
        self.assertTrue(child["address"].startswith("outlook+"))

    def test_legacy_outlook_keys_fallback_when_canonical_values_are_blank(self):
        legacy_id = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "legacy@example.test", "status": "used", "client_id": " ", "refresh_token": "",
            "clientId": "test-legacy-client", "refreshToken": "test-legacy-refresh",
        })
        record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "empty-legacy@example.test", "status": "used", "client_id": " ", "refresh_token": "",
            "clientId": "test-legacy-client", "refreshToken": " ",
        })
        capacity = service.capacity_summary("outlook")
        self.assertEqual(capacity["remaining"], 3)
        self.assertEqual(capacity["parent_count"], 1)
        child = store.allocate_address(source="outlook", acquisition_id="outlook:legacy", owner_kind="registration_root",
            owner_id=1, profile_factory=service._outlook_profile)
        self.assertIsNotNone(child)
        self.assertEqual(child["parent_id"], legacy_id)
        self.assertEqual(service.capacity_summary("outlook")["remaining"], 2)

    def test_disabled_derivation_preserves_original_readiness_rules(self):
        with patch.object(cfg, "EMAIL_DERIVATION_ENABLED", False):
            self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 0)
            self.assertFalse(feature_availability.email_source_availability()["icloud_hide"]["enabled"])
        with patch.object(cfg, "EMAIL_DERIVATION_SOURCES", "icloud_hide"):
            self.assertEqual(service.capacity_summary("outlook")["remaining"], 0)

    def test_retired_explicit_profile_is_not_counted_for_new_allocations(self):
        store.configure_parent("icloud_hide", self.parent, inbox_profile_id=self.profile["id"])
        store.retire_inbox_profile(self.profile["id"])
        self.assertEqual(service.capacity_summary("icloud_hide")["remaining"], 0)

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

    def test_jobs_warning_uses_local_derivation_capacity_and_keeps_submission_contract(self):
        from webui.app import create_app
        client = create_app(auth_code="test-auth").test_client()
        with patch("core.icloud_hme_client.sync_aliases", return_value={"synced_account_ids": ["test-apple"]}), patch(
            "webui.app.svc.submit_registration", return_value=[{"id": 1}],
        ) as submit:
            response = client.post("/api/jobs", headers={"X-Auth-Code": "test-auth"},
                json={"count": 3, "workers": 1, "email_source": "icloud_hide"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["warning"], "")
            submit.assert_called_once_with(count=3, email_source="icloud_hide", workers=1)
            submit.reset_mock()
            response = client.post("/api/jobs", headers={"X-Auth-Code": "test-auth"},
                json={"count": 4, "workers": 1, "email_source": "icloud_hide"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("本地母邮箱剩余派生额度为 3", response.get_json()["warning"])
