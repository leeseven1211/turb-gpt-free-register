"""验证销售 HTTP 契约、鉴权和公开投影。"""
from __future__ import annotations

import logging
from unittest.mock import patch

from flask import Flask

from core.sales import service, store
from tests.sales.test_sales_service import FakeSource, make_account
from tests.support_pg import PostgresTestCase
from webui.auth import init_auth, register_auth_routes
from webui.routes.sales import create_sales_blueprint
from webui.runtime import WebUIContext


class SalesApiTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        app = Flask(__name__)
        init_auth(app, auth_code="fixture-auth")
        register_auth_routes(app)
        app.register_blueprint(create_sales_blueprint(WebUIContext(app=app, logger=logging.getLogger(__name__))))
        self.client = app.test_client()
        self.headers = {"X-Auth-Code": "fixture-auth"}

    def test_requires_shared_webui_authorization(self):
        self.assertEqual(401, self.client.get("/api/sales/items").status_code)
        allowed = self.client.get("/api/sales/items", headers=self.headers)
        self.assertEqual({"ok": True, "items": [], "total": 0, "page": 1, "page_size": 20,
                          "counts": {"all": 0, "for_sale": 0, "listed": 0, "sold": 0}}, allowed.json)

    def test_add_and_status_use_correct_ids_and_expose_no_delivery_material(self):
        source = FakeSource(make_account(961, "api@example.test"))
        with patch.object(service, "account_source", return_value=source):
            added = self.client.post("/api/sales/items/add", headers=self.headers,
                                     json={"source_id": "local", "account_ids": [961]})
        self.assertEqual(200, added.status_code)
        item_id = added.json["items"][0]["id"]
        self.assertNotEqual(961, item_id)
        marked = self.client.post("/api/sales/items/status", headers=self.headers,
                                  json={"item_ids": [item_id], "status": "listed", "note": "人工确认"})
        self.assertEqual(1, marked.json["success_count"])
        visible = self.client.get("/api/sales/items?status=listed", headers=self.headers)
        self.assertEqual("api@example.test", visible.json["items"][0]["email"])
        self.assertTrue(visible.json["items"][0]["archive_pending"])
        events = self.client.get(f"/api/sales/items/{item_id}/events", headers=self.headers)
        self.assertTrue(events.json["events"])
        for response in (added, marked, visible, events):
            body = response.get_data(as_text=True)
            self.assertNotIn("fixture-password", body)
            self.assertNotIn("fingerprint", body)
            self.assertNotIn("delivery_ciphertext", body)

    def test_manual_sale_without_external_evidence_can_be_undone(self):
        item = store.add_item(source_id="local", account_id=42, email="fixture@example.test")
        path = "/api/sales/items/status"
        for status in ("sold", "for_sale"):
            response = self.client.post(path, headers=self.headers, json={"item_ids": [item["id"]], "status": status})
            self.assertEqual(1, response.json["success_count"])
        undone = store.get_item(item["id"])
        self.assertEqual("for_sale", undone["status"])
        self.assertFalse(undone["archive_pending"])

    def test_sources_and_shops_validate_origin_and_reject_credentials_as_fields(self):
        for path, body in (
            ("/api/sales/sources", {"id": "remote", "kind": "remote", "base_url": "ftp://example.test"}),
            ("/api/sales/shops", {"name": "店铺", "base_url": "https://name:pass@example.test"}),
            ("/api/sales/shops", {"name": "店铺", "token": "fake-private-value"}),
        ):
            response = self.client.post(path, headers=self.headers, json=body)
            self.assertEqual(400, response.status_code)
            self.assertFalse(response.json["ok"])
            self.assertTrue(response.json["error_code"])
            self.assertNotIn("fake-private-value", response.get_data(as_text=True))

    def test_sync_returns_persistent_receipt_without_calling_the_shop(self):
        shop = store.save_shop({"name": "测试店铺", "enabled": True})
        with patch.object(service, "executor_id", return_value="local"), \
                patch.object(service, "shop_adapter", side_effect=AssertionError("HTTP 不直接执行同步")):
            response = self.client.post(f"/api/sales/shops/{shop['id']}/sync",
                                        headers=self.headers, json={})
        self.assertEqual(202, response.status_code)
        self.assertTrue(response.json["accepted"])
        jobs = self.client.get("/api/sales/jobs", headers=self.headers)
        self.assertEqual(response.json["task_id"], jobs.json["jobs"][0]["task_id"])
        self.assertEqual("queued", jobs.json["jobs"][0]["status"])

    def test_source_identity_cannot_be_rebound_after_linking_an_account(self):
        data = {"id": "remote", "kind": "remote", "name": "原来源",
                "base_url": "https://original.example.test", "auth_env": "ORIGINAL_AUTH"}
        created = self.client.post("/api/sales/sources", headers=self.headers, json=data)
        self.assertEqual(200, created.status_code)
        store.add_item(source_id="remote", account_id=4, email="owner@example.test")

        moved = self.client.post("/api/sales/sources", headers=self.headers,
                                 json={**data, "base_url": "https://another.example.test"})
        renamed = self.client.post("/api/sales/sources", headers=self.headers,
                                   json={"id": "remote", "name": "新名称"})
        self.assertEqual(409, moved.status_code)
        self.assertEqual("新名称", renamed.json["source"]["name"])
        self.assertEqual(data["base_url"], renamed.json["source"]["base_url"])

    def test_shop_owner_cannot_change_while_its_durable_job_is_queued(self):
        shop = store.save_shop({"name": "测试店铺", "owner_id": "local"})
        with patch.object(service, "executor_id", return_value="local"):
            service.submit_sync(shop["id"])
            moved = self.client.post("/api/sales/shops", headers=self.headers,
                                     json={"id": shop["id"], "owner_id": "oracle"})
        self.assertEqual(409, moved.status_code)
        self.assertEqual("local", store.get_shop(shop["id"])["owner_id"])

    def test_bound_shop_credential_change_requires_identity_check_before_saving(self):
        shop = store.save_shop({"name": "测试店铺", "external_shop_id": "fixture-merchant"})
        from tests.sales.test_sales_service import FakeShop

        merchant = FakeShop()
        merchant.merchant = "different-merchant"
        with patch.object(service, "executor_id", return_value="local"), \
                patch.object(service, "shop_adapter", return_value=merchant):
            changed = self.client.post("/api/sales/shops", headers=self.headers,
                                       json={"id": shop["id"], "token_env": "NEW_SHOP_TOKEN"})
        self.assertEqual(409, changed.status_code)
        self.assertEqual("shop_identity_mismatch", changed.json["error_code"])
        self.assertEqual("", store.get_shop(shop["id"])["token_env"])
