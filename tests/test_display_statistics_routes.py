"""概览与导航共享展示快照，修改后立即失效；领取仍读取事实。"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core import local_email_inventory, record_store
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class DisplayStatisticsRoutesTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.app = create_app(auth_code="test-display")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-display"}

    def test_summary_and_dashboard_share_inventory_snapshot(self):
        original = local_email_inventory.summary
        with patch.object(local_email_inventory, "summary", wraps=original) as summary:
            first = self.client.get("/api/summary", headers=self.headers).get_json()
            second = self.client.get("/api/dashboard", headers=self.headers).get_json()
        self.assertEqual(summary.call_count, 1)
        self.assertEqual(first["email_supply"]["statistics_updated_at"],
                         second["email"]["supply"]["statistics_updated_at"])

    def test_successful_mutation_invalidates_snapshot(self):
        @self.app.post("/test-mutation")
        def mutate():
            record_store.insert_row(record_store.GENERIC_API_POOL,
                                    {"email": "new@example.test", "status": "available"})
            return {"ok": True}

        first = self.client.get("/api/summary", headers=self.headers).get_json()
        self.assertEqual(first["email_supply"]["available"], 0)
        self.assertEqual(self.client.post("/test-mutation", headers=self.headers).status_code, 200)
        second = self.client.get("/api/summary", headers=self.headers).get_json()
        self.assertEqual(second["email_supply"]["available"], 1)

    def test_optional_expiry_boundary_is_safe_for_malformed_and_old_data(self):
        future = datetime.now(timezone.utc) + timedelta(minutes=1)
        for index, expiry in enumerate([future.timestamp(), "bad", -1, 10**16]):
            record_store.insert_row(record_store.GENERIC_API_POOL, {
                "email": f"expiry-{index}@example.test", "status": "available",
                "expires_at_epoch": expiry,
            })
        snapshot = local_email_inventory.summary(include_next_expiry=True)
        self.assertEqual(snapshot["available"], 1)
        self.assertAlmostEqual(snapshot["next_expiry_epoch"], future.timestamp())
        self.assertNotIn("next_expiry_epoch", local_email_inventory.summary())

    def test_display_cache_never_supplies_claim_eligibility(self):
        account_id = record_store.insert_row(record_store.GENERIC_API_POOL, {
            "email": "claim@example.test", "status": "available",
        })
        snapshot = self.client.get("/api/summary", headers=self.headers).get_json()
        self.assertEqual(snapshot["email_supply"]["available"], 1)
        record_store.patch_row(record_store.GENERIC_API_POOL, account_id, {"status": "disabled"})
        self.assertIsNone(local_email_inventory.claim("generic_api", acquisition_id="display-test"))
