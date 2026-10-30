# -*- coding: utf-8 -*-
"""账号枚举列的真实选项、多选组合及轻量轮询回归。"""
import json

from core.storage import admin_repository as repo
from core.storage import records as rs
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

    def test_facets_follow_other_columns_but_exclude_their_own_multiselection(self):
        for page in (1, 2):
            result = repo.list_accounts(
                repo.PageRequest(page=page, page_size=1, filters={
                    "source": "outlook,icloud_hide", "codex": "success,skipped",
                }), plan="free",
            )
            with self.subTest(page=page):
                self.assertEqual(result["total"], 2)
                self.assertEqual(len(result["items"]), 1)
                counts = {key: {item["value"]: item["count"] for item in rows}
                          for key, rows in result["facets"].items()}
                self.assertEqual(counts["source"], {"outlook": 1, "icloud_hide": 1})
                self.assertEqual(counts["plan"], {"free": 2, "unqueried": 1})
                self.assertEqual(counts["codex"], {"success": 2})
                self.assertEqual(counts["password"], {"has": 1, "none": 1})

    def test_empty_results_still_show_alternatives_only_for_the_conflicting_column(self):
        result = repo.list_accounts(repo.PageRequest(filters={"source": "missing-source"}), plan="free")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["facets"]["source"], [
            {"value": "icloud_hide", "count": 1}, {"value": "outlook", "count": 1},
        ])
        self.assertEqual(result["facets"].get("plan", []), [])
        self.assertEqual(result["facets"].get("token", []), [])

    def test_each_enum_facet_excludes_only_its_own_condition(self):
        rs.patch_row(rs.ACCOUNTS, self.ids["free"], {
            "registration_driver": "roxy", "deactivation_mail_detected": True,
        })
        rs.patch_row(rs.ACCOUNTS, self.ids["empty"], {
            "registration_driver": "protocol", "account_status": "deactivated", "email_invalid": True,
        })
        cases = {
            "registration_driver": ("roxy", {"roxy": 1, "protocol": 1}),
            "token": ("has", {"has": 1, "none": 1}),
            "password": ("has", {"has": 1, "none": 1}),
            "plan": ("free", {"free": 1, "unqueried": 1}),
            "promotion": ("free_trial", {"free_trial": 1, "pending": 1}),
            "totp": ("enabled", {"enabled": 1, "disabled": 1}),
            "risk": ("detected", {"detected": 1, "pending": 1}),
            "codex": ("success", {"success": 1, "skipped": 1}),
            "account_status": ("active", {"active": 1, "deactivated": 1}),
            "email_status": ("unmarked", {"unmarked": 1, "invalid": 1}),
        }
        for key, (selected, expected) in cases.items():
            filters = {"source": "outlook"}
            kwargs = {"plan": selected} if key == "plan" else {}
            if key != "plan":
                filters[key] = selected
            result = repo.list_accounts(repo.PageRequest(filters=filters), **kwargs)
            with self.subTest(column=key):
                self.assertEqual(result["total"], 1)
                self.assertEqual({row["value"]: row["count"] for row in result["facets"][key]}, expected)
                if key != "password":
                    self.assertEqual(result["facets"]["password"], [{"value": "has", "count": 1}])

    def test_facets_preserve_search_dates_email_and_email_status(self):
        for name, day in (("free", "01"), ("fallback", "02"), ("empty", "03")):
            rs.patch_row(rs.ACCOUNTS, self.ids[name], {
                "note": "目标账号", "created_at": f"2026-10-{day}T08:00:00",
            })
        rs.patch_row(rs.ACCOUNTS, self.ids["free"], {"email_invalid": True})
        result = repo.list_accounts(repo.PageRequest(filters={
            "email": "example.test", "email_status": "invalid", "source": "outlook",
        }), q="备注:目标账号", date_from="2026-10-01", date_to="2026-10-02")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["facets"]["source"], [{"value": "outlook", "count": 1}])
        self.assertEqual(result["facets"]["plan"], [{"value": "free", "count": 1}])
        changed = repo.list_accounts(repo.PageRequest(filters={
            "email": "fallback@", "email_status": "invalid", "source": "outlook",
        }), q="备注:目标账号", date_from="2026-10-01", date_to="2026-10-02")
        self.assertEqual(changed["facets"].get("source", []), [])
        by_id = repo.list_accounts(repo.PageRequest(filters={
            "id": str(self.ids["free"]), "source": "icloud_hide",
        }))
        self.assertEqual(by_id["total"], 0)
        self.assertEqual(by_id["facets"]["source"], [{"value": "outlook", "count": 1}])

    def test_plus_variants_and_promotion_aliases_restrict_other_facets(self):
        rs.insert_row(rs.ACCOUNTS, {
            "email": "plus-variant@example.test", "current_plan_type": "chatgpt_plus",
            "email_source": "generic_api",
        })
        rs.insert_row(rs.ACCOUNTS, {
            "email": "discount@example.test", "current_plan_type": "free",
            "email_source": "generic_api", "plan_check_status": "success",
            "plus_promo_kind": "discount", "plus_discount_eligible": True,
            "plus_promo_discount_percentage": 50,
        })
        plus = repo.list_accounts(repo.PageRequest(), plan="plus")
        self.assertEqual({row["value"]: row["count"] for row in plus["facets"]["source"]},
                         {"icloud_hide": 1, "generic_api": 1})
        for key in ("promotion", "trial"):
            for value, expected in (("eligible", {"outlook": 1}),
                                    ("discount", {"generic_api": 1})):
                result = repo.list_accounts(repo.PageRequest(filters={key: value}))
                with self.subTest(key=key, value=value):
                    self.assertEqual({row["value"]: row["count"] for row in result["facets"]["source"]}, expected)
                    self.assertGreater(len(result["facets"]["promotion"]), 1)


class AccountRegistrationDriverFilterTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.app = create_app(auth_code="driver-filter-test")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "driver-filter-test"}
        self.ids = {}
        samples = (
            ("roxy", {"registration_driver": " ROXY ", "extra_json": {"registration_driver": "protocol_oss"}, "email_source": "outlook"}, ["protocol"]),
            ("roxy_public", {"extra_json": {"registration_driver": "roxy_oss"}}, ["protocol"]),
            ("proto_local", {"extra_json": json.dumps({"registration_driver": "protocol"})}, ["roxy"]),
            ("proto_public", {}, ["protocol", "protocol_oss"]),
            ("proto_sso", {"extra_json": json.dumps({"registration_driver": "protocol_oss_2"})}, []),
            ("cloakbrowser_history", {"registration_driver": " CLOAKBROWSER "}, []),
            ("missing", {}, []),
            ("invalid_json", {"extra_json": "{invalid-json", "email_source": "outlook"}, ["protocol_oss"]),
            ("unsupported", {"registration_driver": "future_driver", "extra_json": {"registration_driver": "roxy"}}, ["protocol"]),
            ("blank", {"registration_driver": " ", "extra_json": {"registration_driver": ""}}, ["roxy_oss"]),
            ("latest_unknown", {}, ["protocol", None]),
            ("archived", {"archived": True, "registration_driver": "protocol_oss_2"}, []),
        )
        for name, metadata, drivers in samples:
            account_id = rs.insert_row(rs.ACCOUNTS, {
                "email": f"driver-{name}@example.test", "email_source": "icloud_hide", **metadata,
            })
            self.ids[name] = account_id
            for index, driver in enumerate(drivers):
                rs.insert_row(rs.JOBS, {
                    "job_uuid": f"driver-filter-{name}-{index}", "account_id": account_id,
                    "job_type": "registration_resume" if index else "registration",
                    "data": {"config_snapshot": {"registration_driver": driver}},
                })
            rs.insert_row(rs.JOBS, {
                "job_uuid": f"driver-filter-{name}-setup", "account_id": account_id,
                "job_type": "account_setup", "data": {"config_snapshot": {"registration_driver": "roxy"}},
            })

    def _get(self, endpoint, **filters):
        response = self.client.get(endpoint, query_string={"paged": "1", "page_size": 50, **filters}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_each_driver_and_unknown_use_the_same_projection_as_the_display(self):
        cases = {
            "roxy": {"roxy"}, "roxy_oss": {"roxy_public", "blank"},
            "protocol": {"proto_local"}, "protocol_oss": {"proto_public", "invalid_json"},
            "protocol_oss_2": {"proto_sso"}, "cloakbrowser": {"cloakbrowser_history"},
            "unknown": {"missing", "unsupported", "latest_unknown"},
        }
        for driver, names in cases.items():
            expected = {self.ids[name] for name in names}
            for query in (repo.list_accounts, repo.list_account_statuses):
                with self.subTest(driver=driver, query=query.__name__):
                    result = query(repo.PageRequest(page_size=50, filters={"registration_driver": driver}))
                    self.assertEqual(result["total"], len(expected))
                    self.assertEqual({row["id"] for row in result["items"]}, expected)

    def test_driver_multiselect_intersects_other_columns_and_preserves_both_api_pages(self):
        expected = {self.ids["roxy"], self.ids["invalid_json"]}
        endpoint_pages = {}
        for endpoint in ("/api/accounts", "/api/accounts/plan-check-status"):
            page_ids = []
            for page in (1, 2):
                result = self._get(endpoint, page=page, page_size=1,
                                   registration_driver=" ROXY ,protocol_oss,roxy ", source="outlook")
                self.assertEqual(result["total"], 2)
                self.assertEqual(len(result["items"]), 1)
                page_ids.append(result["items"][0]["id"])
            self.assertEqual(set(page_ids), expected)
            endpoint_pages[endpoint] = page_ids
        self.assertEqual(endpoint_pages["/api/accounts"], endpoint_pages["/api/accounts/plan-check-status"])

    def test_driver_facets_exclude_own_filter_and_follow_other_filters_before_pagination(self):
        expected = {"roxy": 1, "roxy_oss": 2, "protocol": 1,
                    "protocol_oss": 2, "protocol_oss_2": 1, "cloakbrowser": 1, "unknown": 3}
        result = self._get("/api/accounts", page_size=1, registration_driver="roxy", source="outlook")
        self.assertEqual(result["total"], 1)
        self.assertEqual({item["value"]: item["count"] for item in result["facets"]["registration_driver"]},
                         {"roxy": 1, "protocol_oss": 1})
        archived = self._get("/api/accounts", archived="only", registration_driver="unknown")
        self.assertEqual(archived["total"], 0)
        self.assertEqual(archived["facets"]["registration_driver"], [{"value": "protocol_oss_2", "count": 1}])
        included = self._get("/api/accounts", archived="all", page_size=1)
        self.assertEqual({item["value"]: item["count"] for item in included["facets"]["registration_driver"]},
                         {**expected, "protocol_oss_2": 2})

    def test_unknown_can_combine_with_known_drivers_in_both_archive_scopes(self):
        for endpoint in ("/api/accounts", "/api/accounts/plan-check-status"):
            result = self._get(endpoint, registration_driver="unknown,protocol_oss_2")
            self.assertEqual({row["id"] for row in result["items"]},
                             {self.ids[name] for name in ("missing", "unsupported", "latest_unknown", "proto_sso")})
            archived = self._get(endpoint, archived="only", registration_driver="unknown,protocol_oss_2")
            self.assertEqual([row["id"] for row in archived["items"]], [self.ids["archived"]])
