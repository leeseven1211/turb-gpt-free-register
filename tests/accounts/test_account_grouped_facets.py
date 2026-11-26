# -*- coding: utf-8 -*-
"""Regressions for the narrowly routed account-facet aggregation.

Breaks caught:
* Routing a filtered or noncanonical archive request through the measured
  unfiltered GROUPING SETS shape instead of the existing self-excluded query.
* Missing the default UI request because its column filters contain empty keys.
* Changing any repository or real HTTP payload field, revision included.
* Reporting equivalence while both responses are empty or the helper is unused.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch

from core.storage import admin_repository as admin
from core.storage.accounts import promotion_offers
from core.storage import records as rs
from tests.support_pg import PostgresTestCase
from webui.app import create_app


_EMPTY_ROUTE_FILTERS = {
    key: ""
    for key in (
        "id", "email", "source", "registration_driver", "token", "password",
        "promotion", "trial", "totp", "risk", "codex", "account_status",
        "email_status",
    )
}


class _SqlCaptureCursor:
    """记录列表的只读 SQL，并模拟共用查询返回的总数行。"""

    def __init__(self, statements):
        self.statements = statements

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        text = str(sql)
        if not text.lstrip().upper().startswith(("SELECT", "WITH")):
            raise AssertionError("account list capture emitted a non-SELECT")
        self.statements.append((text, deepcopy(list(params))))

    def fetchone(self):
        return {"total": 0, "latest": None}

    def fetchall(self):
        if "FULL JOIN summary ON FALSE" in self.statements[-1][0]:
            return [{"id": None, "facet": None, "value": None, "count": 0, "latest": None}]
        return []


class _SqlCaptureConnection:
    def __init__(self, statements):
        self.statements = statements

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self, *_args, **_kwargs):
        return _SqlCaptureCursor(self.statements)


class AccountGroupedFacetRoutingTests(unittest.TestCase):
    """Exercise real repository SQL construction without opening a database."""

    def _capture(self, *, filters=None, **kwargs):
        statements = []
        connection = _SqlCaptureConnection(statements)
        with (
            patch.object(admin, "_connect", return_value=connection),
            patch.object(
                admin.postgres_store, "connect",
                side_effect=AssertionError("offline routing test opened PostgreSQL"),
            ),
            patch.object(
                rs, "init",
                side_effect=AssertionError("offline routing test initialized storage"),
            ),
            patch.object(
                admin, "_account_list_grouped_facets_sql",
                wraps=admin._account_list_grouped_facets_sql,
            ) as grouped,
        ):
            result = admin.list_accounts(
                admin.PageRequest(page=1, page_size=50, filters=filters or {}),
                **kwargs,
            )
        self.assertEqual(result["total"], 0)
        facet_queries = [sql for sql, _ in statements if "GROUP BY GROUPING SETS" in sql or
                         "CROSS JOIN LATERAL (VALUES" in sql]
        self.assertEqual(len(facet_queries), 0 if kwargs.get("include_facets") is False else 1)
        return statements, facet_queries[0] if facet_queries else "", grouped.call_count

    def test_default_and_all_unfiltered_requests_use_grouping_with_empty_ui_keys(self):
        for kwargs in ({}, {"archived": "0"}, {"archived": "all"}):
            for filters in ({}, _EMPTY_ROUTE_FILTERS):
                with self.subTest(kwargs=kwargs, filters=filters):
                    statements, sql, helper_calls = self._capture(filters=filters, **kwargs)
                    self.assertEqual(len(statements), 3)
                    self.assertEqual(helper_calls, 1)
                    self.assertIn("GROUP BY GROUPING SETS", sql)
                    self.assertNotIn("CROSS JOIN LATERAL (VALUES", sql)

    def test_noncanonical_archive_literals_keep_existing_lateral_facets(self):
        for archived in (
            "only", "1", "true", "yes", "include", "ALL", " all ", "0 ",
            "", " ", "false", "00", None,
        ):
            with self.subTest(archived=archived):
                statements, sql, helper_calls = self._capture(archived=archived)
                self.assertEqual(len(statements), 3)
                self.assertEqual(helper_calls, 0)
                self.assertIn("CROSS JOIN LATERAL (VALUES", sql)
                self.assertNotIn("GROUP BY GROUPING SETS", sql)

    def test_every_nonempty_query_dimension_keeps_self_excluded_lateral_facets(self):
        # Ten enum filter keys plus the independent plan argument cover all
        # eleven facets; id/email, trial alias, search, dates and future keys
        # must also keep the original route even when a key is ignored today.
        filtered_requests = (
            ("source", {"source": "outlook,icloud_hide"}, {}),
            ("registration_driver", {"registration_driver": "roxy,protocol"}, {}),
            ("token", {"token": "has,expired"}, {}),
            ("password", {"password": "has,none"}, {}),
            ("promotion", {"promotion": "eligible,discount"}, {}),
            ("totp", {"totp": "enabled,disabled"}, {}),
            ("risk", {"risk": "detected,clear"}, {}),
            ("codex", {"codex": "success,skipped"}, {}),
            ("account_status", {"account_status": "active,deactivated"}, {}),
            ("email_status", {"email_status": "invalid,unmarked"}, {}),
            ("plan", {}, {"plan": "free,plus"}),
            ("search", {}, {"q": "备注:fixture"}),
            ("id", {"id": "42"}, {}),
            ("email", {"email": "fixture@example.test"}, {}),
            ("date_from", {}, {"date_from": "2026-11-01"}),
            ("date_to", {}, {"date_to": "2026-11-18"}),
            ("trial_alias", {"trial": "discount"}, {}),
            ("unknown_filter", {"future_dimension": "recorded-value"}, {}),
            ("unknown_filter_space", {"future_dimension": " "}, {}),
            ("plan_space", {}, {"plan": " "}),
            ("search_space", {}, {"q": " "}),
        )
        for archived in ("0", "all"):
            for name, filters, kwargs in filtered_requests:
                with self.subTest(archived=archived, dimension=name):
                    statements, sql, helper_calls = self._capture(
                        archived=archived, filters=filters, **kwargs,
                    )
                    self.assertEqual(len(statements), 1 if name in {"search", "search_space"} else 3)
                    self.assertEqual(helper_calls, 0)
                    self.assertIn("CROSS JOIN LATERAL (VALUES", sql)
                    self.assertNotIn("GROUP BY GROUPING SETS", sql)

    def test_selected_promotion_match_is_projected_once_before_facet_fanout(self):
        _, sql, helper_calls = self._capture(
            filters={"promotion": "plus_50", "source": "outlook"},
        )
        self.assertEqual(helper_calls, 0)
        self.assertEqual(sql.count("AS __promotion_matches"), 1)
        self.assertEqual(sql.count("EXISTS (SELECT 1 FROM"), 1)
        self.assertIn("OR b.__promotion_matches", sql)

    def test_search_without_facets_uses_separate_count_and_page(self):
        statements, _, helper_calls = self._capture(q="备注:fixture", include_facets=False)
        self.assertEqual(len(statements), 2)
        self.assertEqual(helper_calls, 0)
        self.assertIn("COUNT(*) AS total", statements[0][0])


class AccountGroupedFacetPayloadTests(PostgresTestCase):
    """One focused native test compares entire repository and real API objects."""

    def setUp(self):
        rs.reset_ready()
        rs.init()
        fixed = {
            "created_at": "2026-11-17T08:00:00+00:00",
            "updated_at": "2026-11-17T08:00:00+00:00",
            "plan_check_status": "success",
        }
        samples = {
            "live": {
                "email_source": "outlook", "registration_driver": " ROXY ",
                "current_plan_type": "free", "plus_promo_kind": "free_trial",
                "plus_trial_eligible": True, "access_token": "fixture-live-token",
                "token_expires_at": "2999-01-01T00:00:00+00:00",
                "password": "fixture-password", "totp_enabled": True,
                "deactivation_mail_detected": True, "codex_status": "success",
                "account_status": "active",
            },
            "historical": {
                "email_source": "icloud_hide", "current_plan_type": "plus",
                "extra_json": {"registration_driver": "protocol_oss"},
                "access_token": "fixture-expired-token",
                "token_expires_at": "2000-01-01T00:00:00+00:00",
                "deactivation_mail_scan_status": "success", "codex_status": "failed",
                "account_status": "deactivated", "email_invalid": True,
            },
            "blank": {
                "email_source": None, "codex_status": None,
                "current_plan_type": " ", "plan_type": "free",
            },
            "dynamic": {
                "email_source": "fixture_new_provider", "codex_status": "skipped",
                "current_plan_type": None, "plan_type": None,
                "extra_json": "{invalid-json",
            },
            "archived": {
                "archived": True, "email_source": "outlook",
                "registration_driver": "cloakbrowser", "current_plan_type": "pro",
                "codex_status": "success", "access_token": "fixture-invalid-token",
                "token_expires_at": "2999-01-01T00:00:00+00:00",
                "live_check_status": "failed", "live_check_http_status": " 403 ",
            },
        }
        self.ids = {
            name: rs.insert_row(rs.ACCOUNTS, {
                **fixed, "email": f"grouped-{name}@example.test", **values,
            })
            for name, values in samples.items()
        }
        # Fixed distant expiry dates keep sequential baseline/candidate calls
        # away from CURRENT_TIMESTAMP boundaries. No state is patched between.
        self.app = create_app(auth_code="grouped-facets-test")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "grouped-facets-test"}

    def test_unfiltered_statistics_execute_in_read_only_transactions(self):
        connect = admin._connect

        @contextmanager
        def read_only_connection():
            with connect() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                yield conn

        # PostgreSQL itself rejects any write from either list query shape.
        # Seed writes happened in setUp and are outside these read transactions.
        with patch.object(admin, "_connect", side_effect=read_only_connection):
            for archived, expected_total in (("0", 4), ("all", 5)):
                with self.subTest(archived=archived):
                    request = admin.PageRequest(
                        page_size=2, filters=dict(_EMPTY_ROUTE_FILTERS),
                    )
                    with patch.object(
                        admin, "_account_list_grouped_facets_eligible",
                        return_value=False,
                    ):
                        baseline = admin.list_accounts(request, archived=archived)
                    actual = admin.list_accounts(request, archived=archived)
                    self.assertEqual(actual, baseline)
                    self.assertEqual(actual["total"], expected_total)
                    self.assertEqual(len(actual["items"]), 2)

    def test_repository_and_real_http_preserve_every_payload_field(self):
        active_counts = {
            "source": {"outlook": 1, "icloud_hide": 1, "fixture_new_provider": 1},
            "registration_driver": {"unknown": 2, "roxy": 1, "protocol_oss": 1},
            "token": {"none": 2, "has": 1, "expired": 1},
            "password": {"none": 3, "has": 1},
            "plan": {"free": 2, "plus": 1, "unqueried": 1},
            "promotion": {
                "not_applicable": 2, "free_trial": 1,
                promotion_offers.offer_key("plus", "free_trial", None, None, None): 1,
                "pending": 1,
            },
            "totp": {"disabled": 3, "enabled": 1},
            "risk": {"pending": 2, "detected": 1, "clear": 1},
            "codex": {"success": 1, "failed": 1, "skipped": 1},
            "account_status": {"active": 3, "deactivated": 1},
            "email_status": {"unmarked": 3, "invalid": 1},
        }
        all_counts = {
            "source": {"outlook": 2, "icloud_hide": 1, "fixture_new_provider": 1},
            "registration_driver": {
                "unknown": 2, "roxy": 1, "protocol_oss": 1, "cloakbrowser": 1,
            },
            "token": {"none": 2, "has": 1, "expired": 1, "invalid_403": 1},
            "password": {"none": 4, "has": 1},
            "plan": {"free": 2, "plus": 1, "unqueried": 1, "pro": 1},
            "promotion": {
                "not_applicable": 3, "free_trial": 1,
                promotion_offers.offer_key("plus", "free_trial", None, None, None): 1,
                "pending": 1,
            },
            "totp": {"disabled": 4, "enabled": 1},
            "risk": {"pending": 3, "detected": 1, "clear": 1},
            "codex": {"success": 2, "failed": 1, "skipped": 1},
            "account_status": {"active": 4, "deactivated": 1},
            "email_status": {"unmarked": 4, "invalid": 1},
        }
        scopes = (
            ({}, {}, [self.ids[name] for name in ("dynamic", "blank", "historical", "live")],
             active_counts),
            ({"archived": "all"}, {"archived": "all"},
             sorted(self.ids.values(), reverse=True), all_counts),
        )
        for repository_kwargs, http_kwargs, expected_ids, expected_counts in scopes:
            with self.subTest(archived=repository_kwargs.get("archived", "default")):
                request = admin.PageRequest(
                    page=1, page_size=50, filters=dict(_EMPTY_ROUTE_FILTERS),
                )
                with (
                    patch.object(admin, "_account_list_grouped_facets_eligible", return_value=False),
                    patch.object(
                        admin, "_account_list_grouped_facets_sql",
                        wraps=admin._account_list_grouped_facets_sql,
                    ) as baseline_helper,
                ):
                    baseline = admin.list_accounts(request, **repository_kwargs)
                baseline_helper.assert_not_called()
                with patch.object(
                    admin, "_account_list_grouped_facets_sql",
                    wraps=admin._account_list_grouped_facets_sql,
                ) as grouped:
                    actual = admin.list_accounts(request, **repository_kwargs)
                grouped.assert_called_once()
                self.assertEqual(actual, baseline)
                self.assertEqual(actual["total"], len(expected_ids))
                self.assertEqual([item["id"] for item in actual["items"]], expected_ids)
                self.assertTrue(actual["revision"])
                self.assertEqual(
                    {
                        facet: {item["value"]: item["count"] for item in values}
                        for facet, values in actual["facets"].items()
                    },
                    expected_counts,
                )
                query = {"paged": "1", "page_size": 50, **http_kwargs}
                with (
                    patch.object(admin, "_account_list_grouped_facets_eligible", return_value=False),
                    patch.object(
                        admin, "_account_list_grouped_facets_sql",
                        wraps=admin._account_list_grouped_facets_sql,
                    ) as http_baseline_helper,
                ):
                    baseline_response = self.client.get(
                        "/api/accounts", query_string=query, headers=self.headers,
                    )
                http_baseline_helper.assert_not_called()
                self.assertEqual(baseline_response.status_code, 200)
                baseline_json = baseline_response.get_json()
                with patch.object(
                    admin, "_account_list_grouped_facets_sql",
                    wraps=admin._account_list_grouped_facets_sql,
                ) as http_grouped:
                    actual_response = self.client.get(
                        "/api/accounts", query_string=query, headers=self.headers,
                    )
                http_grouped.assert_called_once()
                self.assertEqual(actual_response.status_code, 200)
                actual_json = actual_response.get_json()
                self.assertEqual(actual_json, baseline_json)
                self.assertEqual(actual_json["total"], len(expected_ids))
                self.assertEqual([item["id"] for item in actual_json["items"]], expected_ids)
                self.assertEqual(actual_json["revision"], actual["revision"])
                self.assertEqual(actual_json["facets"], actual["facets"])
                self.assertTrue(actual_json["compact"])
                self.assertEqual(actual_json["search_terms"], [])
