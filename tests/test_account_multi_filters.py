# -*- coding: utf-8 -*-
"""账号枚举列的真实选项、多选组合及轻量轮询回归。"""
from core import admin_repository as repo
from core import record_store as rs
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class AccountMultiFilterTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.app = create_app(auth_code="filter-test")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "filter-test"}
        self.ids = {}
        samples = {
            "free": {"current_plan_type": "free", "email_source": "outlook", "codex_status": "success", "access_token": "test-token", "password": "test-password", "totp_enabled": True, "plan_check_status": "success", "plus_promo_kind": "free_trial", "plus_trial_eligible": True},
            "plus": {"current_plan_type": "plus", "email_source": "icloud_hide", "codex_status": "failed", "deactivation_mail_scan_status": "success"},
            "empty": {"email_source": "outlook", "codex_status": "skipped"},
            "fallback": {"current_plan_type": "", "plan_type": "free", "email_source": "icloud_hide", "codex_status": "success"},
            "blank": {"current_plan_type": "  ", "plan_type": " ", "email_source": "generic_api", "codex_status": "failed", "account_status": "deactivated"},
            "archived": {"archived": True, "current_plan_type": "pro", "email_source": "outlook"},
        }
        for name, values in samples.items():
            self.ids[name] = rs.insert_row(rs.ACCOUNTS, {"email": f"{name}@example.test", **values})

    def get_pages(self, **filters):
        for endpoint in ("/api/accounts", "/api/accounts/plan-check-status"):
            response = self.client.get(endpoint, query_string={"paged": "1", "page_size": 50, **filters}, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            yield endpoint, response.get_json()

    def test_plan_options_include_empty_records_and_skip_absent_values(self):
        result = repo.list_accounts(repo.PageRequest(page_size=1))
        self.assertEqual(result["total"], 5)
        self.assertEqual({item["value"]: item["count"] for item in result["facets"]["plan"]}, {"free": 2, "plus": 1, "unqueried": 2})
        archived = repo.list_accounts(repo.PageRequest(), archived="only")
        self.assertEqual(archived["facets"]["plan"], [{"value": "pro", "count": 1}])

    def test_empty_and_fallback_plans_match_the_display_in_both_endpoints(self):
        for endpoint, result in self.get_pages(plan="unqueried"):
            with self.subTest(endpoint=endpoint):
                self.assertEqual({row["id"] for row in result["items"]}, {self.ids["empty"], self.ids["blank"]})
        for endpoint, result in self.get_pages(plan="free"):
            with self.subTest(endpoint=endpoint):
                self.assertEqual({row["id"] for row in result["items"]}, {self.ids["free"], self.ids["fallback"]})

    def test_all_enum_columns_accept_multiple_values(self):
        cases = {
            "source": ("outlook,icloud_hide", {"free", "plus", "empty", "fallback"}),
            "token": ("has,none", {"free", "plus", "empty", "fallback", "blank"}),
            "password": ("has,none", {"free", "plus", "empty", "fallback", "blank"}),
            "totp": ("enabled,disabled", {"free", "plus", "empty", "fallback", "blank"}),
            "risk": ("pending,clear", {"free", "plus", "empty", "fallback", "blank"}),
            "codex": ("success,skipped", {"free", "empty", "fallback"}),
            "account_status": ("active,deactivated", {"free", "plus", "empty", "fallback", "blank"}),
            "promotion": ("free_trial,not_applicable", {"free", "plus", "blank"}),
            "plan": ("free,unqueried", {"free", "empty", "fallback", "blank"}),
        }
        for key, (value, names) in cases.items():
            for endpoint, result in self.get_pages(**{key: value}):
                with self.subTest(column=key, endpoint=endpoint):
                    self.assertEqual({row["id"] for row in result["items"]}, {self.ids[name] for name in names})

    def test_same_column_uses_or_and_different_columns_use_and_across_pages(self):
        for page in (1, 2):
            for endpoint, result in self.get_pages(page=page, page_size=1, plan=" FREE ,unqueried,free ", source="outlook,icloud_hide", codex="success,skipped", account_status="active"):
                with self.subTest(page=page, endpoint=endpoint):
                    self.assertEqual(result["total"], 3)
                    self.assertEqual(len(result["items"]), 1)
                    self.assertIn(result["items"][0]["id"], {self.ids[name] for name in ("free", "empty", "fallback")})

    def test_pending_promotion_filter_has_the_same_precedence_as_its_options(self):
        rs.patch_row(rs.ACCOUNTS, self.ids["free"], {"plan_check_status": "running"})
        for endpoint, result in self.get_pages(promotion="free_trial"):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(result["total"], 0)
        for endpoint, result in self.get_pages(promotion="pending,not_applicable"):
            with self.subTest(endpoint=endpoint):
                self.assertIn(self.ids["free"], {row["id"] for row in result["items"]})
        result = repo.list_accounts(repo.PageRequest())
        self.assertNotIn("free_trial", {item["value"] for item in result["facets"]["promotion"]})
