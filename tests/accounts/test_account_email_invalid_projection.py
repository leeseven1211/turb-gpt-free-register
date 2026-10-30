# -*- coding: utf-8 -*-
"""邮箱失效独立过滤及轻量状态清除回归。"""
from unittest import TestCase

from core.storage import admin_repository as repo
from core.storage import records as rs
from tests.support_pg import PostgresTestCase
from webui.app import create_app
from webui.route_helpers import _compact_account_for_list


class AccountEmailInvalidCompactTests(TestCase):
    def test_compact_defaults_to_unmarked_and_clears_display_metadata_explicitly(self):
        result = _compact_account_for_list({"id": 1, "email": "a@example.test"})
        self.assertIs(result.get("email_invalid"), False)
        self.assertIn("email_invalid_reason", result)
        self.assertIsNone(result["email_invalid_reason"])
        self.assertIsNone(result["email_invalid_at"])

    def test_compact_exposes_only_public_email_marker_without_reclassifying_account(self):
        result = _compact_account_for_list({
            "id": 1, "email": "a@example.test", "email_invalid": True,
            "email_invalid_reason": "邮箱失效", "email_invalid_at": "2026-10-25T10:00:00Z",
            "email_invalid_source": "manual", "email_invalid_email": "old@example.test",
            "account_status": "active", "access_token": "private",
        })
        self.assertIs(result.get("email_invalid"), True)
        self.assertEqual("邮箱失效", result.get("email_invalid_reason"))
        self.assertEqual("active", result["account_status"])
        self.assertNotIn("email_invalid_email", result)
        self.assertNotIn("access_token", result)


class AccountEmailInvalidProjectionTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.client = create_app(auth_code="email-status-test").test_client()
        self.headers = {"X-Auth-Code": "email-status-test"}
        self.invalid = rs.insert_row(rs.ACCOUNTS, {
            "email": "invalid@example.test", "email_invalid": True,
            "email_invalid_reason": "副号邮箱失效", "email_invalid_at": "2026-10-25T10:00:00Z",
            "email_invalid_source": "manual", "email_invalid_email": "invalid@example.test",
            "account_status": "active", "updated_at": "2026-10-25T10:00:00Z",
        })
        self.deactivated = rs.insert_row(rs.ACCOUNTS, {
            "email": "deactivated@example.test", "account_status": "deactivated",
        })
        self.unmarked = rs.insert_row(rs.ACCOUNTS, {"email": "unmarked@example.test"})
        self.archived = rs.insert_row(rs.ACCOUNTS, {
            "email": "archived@example.test", "archived": True, "email_invalid": True,
        })

    def test_both_endpoints_filter_email_state_independently_from_openai_deactivation(self):
        for endpoint in ("/api/accounts", "/api/accounts/plan-check-status"):
            for filters, ids in (
                ({"email_status": "invalid"}, {self.invalid}),
                ({"email_status": "unmarked"}, {self.deactivated, self.unmarked}),
                ({"email_status": "invalid", "account_status": "deactivated"}, set()),
                ({"email_status": "invalid", "archived": "only"}, {self.archived}),
            ):
                with self.subTest(endpoint=endpoint, filters=filters):
                    response = self.client.get(endpoint, query_string={"paged": "1", **filters}, headers=self.headers)
                    self.assertEqual(200, response.status_code)
                    self.assertEqual(ids, {row["id"] for row in response.get_json()["items"]})

    def test_poll_explicit_false_and_null_fields_clear_previous_marker_and_change_revision(self):
        before = repo.list_account_statuses(repo.PageRequest(page_size=10))
        rs.patch_row(rs.ACCOUNTS, self.invalid, {
            "email_invalid": False, "email_invalid_reason": None, "email_invalid_at": None,
            "email_invalid_source": None, "updated_at": "2026-10-25T10:00:00Z",
        })
        after = repo.list_account_statuses(repo.PageRequest(page_size=10))
        row = next(item for item in after["items"] if item["id"] == self.invalid)
        self.assertIs(row.get("email_invalid"), False)
        for key in ("email_invalid_reason", "email_invalid_at", "email_invalid_source"):
            self.assertIn(key, row)
            self.assertIsNone(row[key])
        self.assertNotEqual(before["revision"], after["revision"])
        self.assertNotIn("email_invalid_email", row)
