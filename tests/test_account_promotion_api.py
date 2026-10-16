# -*- coding: utf-8 -*-
"""验证实际账号 API 的二次投影保留 Go / Plus 优惠与查询证据。"""
from core import db, record_store as rs
from core.chatgpt_plan import parse_accounts_check
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class AccountPromotionApiTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.app = create_app(auth_code="promotion-api-test")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "promotion-api-test"}
        self.account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "promotion-api@example.test", "current_plan_type": "free",
            "access_token": "synthetic-access-token", "password": "synthetic-password",
        })
        self.result = parse_accounts_check({"accounts": {"default": {
            "account": {"account_id": "synthetic-account", "plan_type": "free"},
            "eligible_promo_campaigns": {
                "go": {"id": "go-1-month-free", "metadata": {
                    "discount": {"percentage": 100},
                    "duration": {"num_periods": 1, "period": "month"},
                }},
                "plus": {"id": "plus-50-pct-off", "metadata": {
                    "discount": {"percentage": 50},
                    "duration": {"num_periods": 2, "period": "month"},
                }},
            },
        }}})
        self.result.update({"proxy_region": "JP", "proxy_provider": "1024proxy"})
        self.assertTrue(db.update_account_plan_check(acc_id=self.account_id, result=self.result))

    def _assert_promotions(self, item):
        self.assertEqual(item["id"], self.account_id)
        self.assertEqual(item["account_promotions"], self.result["account_promotions"])
        self.assertEqual(item["promotion_query_snapshot"], self.result["promotion_query_snapshot"])
        self.assertEqual(
            [campaign["discount_percentage"] for campaign in item["promotion_query_snapshot"]["campaigns"]],
            [100, 50],
        )
        self.assertTrue(item["has_access_token"])
        self.assertEqual("JP", item["plan_promotion_country"])
        self.assertTrue(item.get("updated_at"))
        self.assertNotIn("access_token", item)
        self.assertNotIn("password", item)

    def test_default_and_paged_accounts_api_keep_promotions_in_compact_rows(self):
        for url in ("/api/accounts", "/api/accounts?paged=1&page=1&page_size=20"):
            with self.subTest(url=url):
                response = self.client.get(url, headers=self.headers)
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                if isinstance(payload, dict):
                    self.assertTrue(payload["compact"])
                    items = payload["items"]
                else:
                    items = payload
                self.assertEqual(len(items), 1)
                self._assert_promotions(items[0])

    def test_plan_status_api_keeps_same_promotions_and_snapshot(self):
        response = self.client.get("/api/accounts/plan-check-status", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        self.assertEqual(len(items), 1)
        self._assert_promotions(items[0])

    def test_plan_status_poll_clears_stale_single_country_after_multi_country_result(self):
        rs.patch_row(rs.ACCOUNTS, self.account_id, {
            "plan_promotion_country": "JP",
            "plan_check_status": "success",
            "plan_check_ok": True,
            "plan_check_countries": ["JP", "US"],
            "plan_check_country_results": [
                {"country": "JP", "status": "success", "result": {"proxy_region": "JP"}},
                {"country": "US", "status": "success", "result": {"proxy_region": "US"}},
            ],
            "account_promotions": [
                {"plan": "plus", "kind": "none", "country": "JP"},
                {"plan": "plus", "kind": "free_trial", "country": "US"},
            ],
        })

        response = self.client.get("/api/accounts/plan-check-status", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["items"][0]
        self.assertIsNone(item["plan_promotion_country"])
