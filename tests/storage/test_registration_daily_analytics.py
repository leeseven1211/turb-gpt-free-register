# -*- coding: utf-8 -*-
"""账号首次入库日及完整套餐优惠总览契约。"""
import json
import unittest
from datetime import datetime
from unittest.mock import patch

from core.storage import admin_repository
from core.storage import records as rs
from core.storage.accounts import promotion_offers
from core.storage.registration import analytics
from tests.support_pg import PostgresTestCase


def _offer(plan="plus", kind="discount", *, eligible=True, percentage=50, periods=2,
           period="month", country="", stale=False):
    return {
        "plan": plan, "kind": kind, "eligible": eligible,
        "discount_percentage": percentage, "duration_num_periods": periods,
        "duration_period": period, "country": country, "stale": stale,
    }


def _none_snapshot():
    return {"ok": True, "promotion_query_snapshot": {"truncated": False}, "account_promotions": [
        {"plan": plan, "kind": "none", "eligible": False}
        for plan in ("plus", "team", "go")
    ]}


class RegistrationDailyAnalyticsTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()

    def _account(self, email, **values):
        return rs.insert_row(rs.ACCOUNTS, {
            "email": email, "created_at": "2026-11-26T09:00:00", **values,
        })

    def _job(self, email, created_at, account_id):
        return rs.insert_row(rs.JOBS, {
            "job_uuid": f"{email}-{created_at}", "email": email,
            "created_at": created_at, "status": "success", "job_type": "registration_resume",
            "account_id": account_id,
        })

    def test_accounts_belong_only_to_first_created_date_without_requiring_tasks(self):
        old = self._account("old@example.test", created_at="2026-11-25T15:59:59+00:00")
        current = self._account("current@example.test", created_at="2026-11-25T16:00:00Z")
        self._account("archived@example.test", created_at="2026-11-26T15:59:59+00:00", archived=True)
        self._account("next@example.test", created_at="2026-11-26T16:00:00+00:00")
        self._job("old@example.test", "2026-11-26T01:00:00+00:00", old)
        self._job("current@example.test", "2026-11-27T01:00:00+00:00", current)
        self._job("current@example.test", "2026-11-28T01:00:00+00:00", current)

        with patch.object(admin_repository, "_registration_cohort_source_sql", side_effect=AssertionError("must not read jobs")):
            result = analytics.registration_daily_analytics(date_from="2026-11-26", date_to="2026-11-28")

        self.assertEqual(result["cohort_basis"], "account_created_at")
        self.assertEqual(result["cohort_basis_label"], "按账号首次入库日期统计")
        self.assertEqual([row["accounts_total"] for row in result["rows"]], [2, 1, 0])
        self.assertEqual(result["summary"]["accounts_total"], 3)
        self.assertEqual(result["summary"]["total"], 3)
        self.assertEqual(result["summary"]["counts"], {})
        self.assertEqual(result["rows"][2]["promotion_presence"], {"eligible": 0, "none": 0, "unknown": 0})

    def test_invalid_created_dates_are_ignored_and_naive_dates_use_beijing(self):
        for index, created_at in enumerate((
            "2026-11-26", "2026-11-26T01:00:00+0800", "2026-11-26T02:00:00z",
            "2026-11-26 03:00:00", "2026-11-26T23:59:59.5+08:00",
        )):
            self._account(f"valid-{index}@example.test", created_at=created_at)
        for index, created_at in enumerate(("", "2026-99-99T99:99:99", "2026-02-30", "not-a-date")):
            self._account(f"invalid-{index}@example.test", created_at=created_at)
        result = analytics.registration_daily_analytics(date_from="2026-11-26", date_to="2026-11-26")
        self.assertEqual(result["summary"]["accounts_total"], 5)

    def test_presence_is_mutually_exclusive_and_none_requires_complete_success_snapshot(self):
        self._account("fresh@example.test", account_promotions=[_offer()])
        self._account("none@example.test", plan_last_success_result_json=json.dumps(_none_snapshot()))
        self._account("none-object@example.test", plan_last_success_result_json=_none_snapshot())
        self._account("plus-none@example.test", plus_promo_kind="none", plan_check_ok=True,
                      plan_check_status="success", plan_last_success_result_json=json.dumps({
                          "ok": True, "account_promotions": [{"plan": "plus", "kind": "none", "eligible": False}],
                      }))
        self._account("unqueried@example.test")
        self._account("stale@example.test", account_promotions=[_offer(stale=True)])
        self._account("broken@example.test", plan_last_success_result_json="not-json")
        result = analytics.registration_daily_analytics(date_from="2026-11-26", date_to="2026-11-27")
        for row in (result["rows"][0], result["summary"]):
            self.assertEqual(row["promotion_presence"], {"eligible": 1, "none": 2, "unknown": 4})
            self.assertEqual(row["promoted_accounts_total"], 1)
            self.assertEqual(sum(row["promotion_presence"].values()), row["accounts_total"])

    def test_fresh_offer_counts_all_plans_and_deduplicates_countries_but_excludes_stale_only(self):
        plus = _offer()
        team = _offer("team", "free_trial", percentage=100, periods=1)
        go = _offer("go", percentage=25, periods=1.5)
        self._account("a@example.test", account_promotions=[
            {**plus, "country": "US", "stale": True},
            {**plus, "country": "JP", "duration_period": "months"},
            {**team, "country": "IN"}, {**team, "country": "VN"},
            {**go, "eligible": False},
        ])
        self._account("b@example.test", created_at="2026-11-27T01:00:00", archived=True,
                      account_promotions=[
                          {**plus, "country": "US", "stale": True},
                          {**plus, "country": "JP", "stale": True},
                          {**go, "country": "IN"},
                      ])
        self._account("c@example.test", account_promotions=[
            {**plus, "eligible": False}, {**team, "kind": "none"}, {**go, "kind": "unknown"},
        ])
        result = analytics.registration_daily_analytics(date_from="2026-11-26", date_to="2026-11-28")
        keys = {
            "plus": promotion_offers.offer_key("plus", "discount", 50, 2, "month"),
            "team": promotion_offers.offer_key("team", "free_trial", 100, 1, "month"),
            "go": promotion_offers.offer_key("go", "discount", 25, 1.5, "month"),
        }
        expected = {
            keys["plus"]: {"key": keys["plus"], "plan": "plus", "label": "Plus 半价 2个月", "count": 1, "stale_count": 0},
            keys["team"]: {"key": keys["team"], "plan": "team", "label": "Team 免费 1个月", "count": 1, "stale_count": 0},
            keys["go"]: {"key": keys["go"], "plan": "go", "label": "Go 减 25% 1.5个月", "count": 1, "stale_count": 0},
        }
        self.assertEqual({offer["key"]: offer for offer in result["summary"]["offers"]}, expected)
        self.assertEqual({offer["key"] for offer in result["rows"][0]["offers"]}, {keys["plus"], keys["team"]})
        self.assertEqual({offer["key"] for offer in result["rows"][1]["offers"]}, {keys["go"]})
        self.assertEqual(result["rows"][2]["offers"], [])
        self.assertEqual(result["summary"]["promotion_presence"], {"eligible": 2, "none": 0, "unknown": 1})
        for field in ("accounts_total", "promoted_accounts_total", "unpromoted_count"):
            self.assertEqual(result["summary"][field], sum(row[field] for row in result["rows"]))
        for category in ("eligible", "none", "unknown"):
            self.assertEqual(result["summary"]["promotion_presence"][category], sum(row["promotion_presence"][category] for row in result["rows"]))

    def test_plus_none_batch_query_uses_account_created_dates_and_matches_counts(self):
        for email, fields in (
            ("match@example.test", {}),
            ("utc-match@example.test", {"created_at": "2026-11-25T16:00:00Z"}),
            ("outside@example.test", {"created_at": "2026-11-26T16:00:00Z"}),
            ("archived@example.test", {"archived": True}),
            ("queued@example.test", {"plan_check_status": "Queued"}),
            ("promoted@example.test", {"plus_promo_kind": "free_trial", "plus_trial_eligible": True}),
        ):
            self._account(email, **{
                "current_plan_type": "free", "plus_promo_kind": "none",
                "plan_check_status": "success", "plan_check_ok": True, **fields,
            })
        result = analytics.registration_daily_analytics(date_from="2026-11-26", date_to="2026-11-26")
        summary = result["summary"]
        query = summary["query"]
        self.assertEqual(query["q"], "")
        self.assertEqual((query["date_from"], query["date_to"]), ("2026-11-26", "2026-11-26"))
        self.assertEqual(query["filters"]["promotion"], ["none"])
        self.assertEqual(summary["unpromoted_count"], 2)
        self.assertEqual(admin_repository.account_query_count(query), summary["unpromoted_count"])
        self.assertEqual(result["rows"][0]["unpromoted_count"], summary["unpromoted_count"])

    def test_snapshot_only_positive_offers_are_counted_and_deduplicated(self):
        team = _offer("team", "free_trial", percentage="100.0", periods="1", period="months")
        go = _offer("go", percentage="25", periods="1.5", period="个月")
        self._account("snapshot-top@example.test", plan_last_success_result_json=json.dumps({
            "ok": True,
            "account_promotions": [
                {**team, "country": "US"}, {**team, "country": "JP", "duration_period": "month"},
            ],
        }))
        self._account("snapshot-countries@example.test", plan_last_success_result_json={
            "ok": True, "plan_check_partial": True,
            "plan_check_country_results": [
                {"country": "IN", "status": "success", "result": {"ok": True, "account_promotions": [go]}},
                {"country": "JP", "status": "success", "result": {"ok": True, "account_promotions": [go]}},
                {"country": "US", "status": "failed", "result": {"ok": True, "account_promotions": [team]}},
                {"country": "VN", "status": "success", "result": {
                    "ok": True, "account_promotions": [{**team, "stale": True}, {**team, "expired": True}],
                }},
            ],
        })
        result = analytics.registration_daily_analytics(date_from="2026-11-26", date_to="2026-11-26")
        team_key = promotion_offers.offer_key("team", "free_trial", 100, 1, "month")
        go_key = promotion_offers.offer_key("go", "discount", 25, 1.5, "month")
        expected = {
            team_key: {"key": team_key, "plan": "team", "label": "Team 免费 1个月", "count": 1, "stale_count": 0},
            go_key: {"key": go_key, "plan": "go", "label": "Go 减 25% 1.5个月", "count": 1, "stale_count": 0},
        }
        for row in (result["rows"][0], result["summary"]):
            self.assertEqual(row["promotion_presence"], {"eligible": 2, "none": 0, "unknown": 0})
            self.assertEqual({offer["key"]: offer for offer in row["offers"]}, expected)


class RegistrationDailyAnalyticsValidationTests(unittest.TestCase):
    def test_date_range_is_bounded_and_has_stable_error_codes(self):
        cases = (
            ({"date_from": "2026-11-27", "date_to": "2026-11-26"}, "date_range_reversed"),
            ({"date_from": "2026-02-30", "date_to": "2026-02-30"}, "date_invalid"),
            ({"date_from": "2025-01-01", "date_to": "2026-01-02"}, "date_range_too_large"),
            ({"date_to": "0001-01-01"}, "date_invalid"),
            ({"date_from": "9999-12-31"}, "date_invalid"),
        )
        for values, code in cases:
            with self.subTest(values=values):
                with self.assertRaises(analytics.RegistrationDailyAnalyticsError) as raised:
                    analytics.registration_daily_analytics(**values)
                self.assertEqual(raised.exception.error_code, code)

    def test_default_and_one_sided_ranges_use_three_beijing_dates(self):
        self.assertEqual(analytics.normalize_registration_date_range(now=datetime(2026, 11, 26, 1)),
                         ("2026-11-24", "2026-11-26"))
        self.assertEqual(analytics.normalize_registration_date_range(date_to="2026-11-26"),
                         ("2026-11-24", "2026-11-26"))
        self.assertEqual(analytics.normalize_registration_date_range(date_from="2026-11-24"),
                         ("2026-11-24", "2026-11-26"))
