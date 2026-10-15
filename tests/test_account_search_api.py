# -*- coding: utf-8 -*-
from core import record_store as rs
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class AccountSearchApiTests(PostgresTestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    def test_list_returns_removable_conditions_and_status_uses_the_same_query(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "search-api@example.test", "registration_proxy_region": "JP", "note": "a/b 待整理",
        })
        rs.insert_row(rs.JOBS, {
            "job_uuid": "search-api-protocol", "account_id": account_id,
            "data": {"config_snapshot": {"registration_driver": "protocol"}},
        })
        query = '协议/jp 备注:"a/b 待整理"'
        for endpoint in ("/api/accounts", "/api/accounts/plan-check-status"):
            response = self.client.get(endpoint, query_string={"paged": "1", "q": query}, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["total"], 1)
            self.assertEqual(payload["items"][0]["id"], account_id)
            if endpoint == "/api/accounts":
                self.assertEqual(payload["search_terms"][1]["display_value"], "日本 JP")
                self.assertEqual(payload["search_terms"][1]["query_without"], '协议 备注:"a/b 待整理"')

    def test_both_endpoints_report_invalid_search_as_a_client_error(self):
        for endpoint in ("/api/accounts", "/api/accounts/plan-check-status"):
            for query in ("地区:JJ", "错误字段:内容", '备注:"未闭合'):
                with self.subTest(endpoint=endpoint, query=query):
                    response = self.client.get(endpoint, query_string={"paged": "1", "q": query}, headers=self.headers)
                    self.assertEqual(response.status_code, 400)
                    payload = response.get_json()
                    self.assertEqual(payload["code"], "account_search_invalid")
                    self.assertTrue(payload["error"])

    def test_legacy_unpaged_list_still_returns_an_array(self):
        response = self.client.get("/api/accounts", query_string={"q": "协议/jp"}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json(), list)
