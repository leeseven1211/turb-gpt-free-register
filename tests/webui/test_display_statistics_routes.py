"""概览与导航共享展示快照，修改后立即失效；领取仍读取事实。"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from config import email as email_config
from core.email import inventory as local_email_inventory
from core.storage import records as record_store
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

    def test_capabilities_reuses_display_count_without_using_it_for_source_gate(self):
        original = local_email_inventory.summary
        with patch.object(local_email_inventory, "summary", wraps=original) as summary:
            self.client.get("/api/summary", headers=self.headers)
            self.client.get("/api/dashboard", headers=self.headers)
            response = self.client.get("/api/capabilities", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(summary.call_count, 1)

    def test_capabilities_keeps_realtime_enabled_with_stale_zero_display_count(self):
        with patch("config.email.USE_EMAIL_SERVICE", True), patch(
            "core.runtime.capabilities._registration_driver_status",
            return_value={"enabled": True, "reason": ""},
        ), patch(
            "core.runtime.capabilities._registration_proxy_status",
            return_value={"enabled": True, "reason": ""},
        ):
            self.client.get("/api/summary", headers=self.headers)
            record_store.insert_row(
                record_store.GENERIC_API_POOL,
                {"email": "fresh-capability@example.test", "status": "available"},
            )

            response = self.client.get("/api/capabilities", headers=self.headers)

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["features"]["register"]["enabled"])
        self.assertEqual(payload["email_sources"]["generic_api"]["available"], 0)

    def test_email_sources_use_realtime_exists_after_cached_zero_snapshot(self):
        with patch.object(email_config, "USE_EMAIL_SERVICE", True):
            self.client.get("/api/summary", headers=self.headers)
            record_store.insert_row(
                record_store.GENERIC_API_POOL,
                {"email": "fresh@example.test", "status": "available"},
            )
            response = self.client.get("/api/email-sources", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        choices = {row["value"]: row for row in response.get_json()["sources"]}
        self.assertTrue(choices["generic_api"]["enabled"])

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
