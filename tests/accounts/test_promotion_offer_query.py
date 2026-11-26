# -*- coding: utf-8 -*-
"""优惠投影查询、旧值兼容和动态分面回归。"""
from __future__ import annotations

from decimal import Decimal

from core.accounts import query
from core.storage import admin_repository as repo
from core.storage import postgres
from core.storage import records as rs
from core.storage.accounts import promotion_offers
from tests.support_pg import PostgresTestCase


class PromotionOfferQueryTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        with postgres.connect() as conn:
            promotion_offers.ensure_schema(conn)
        self.ids = {}

    def _account(self, name: str, **values) -> int:
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": f"promotion-query-{name}@example.test",
            "created_at": "2026-11-26T08:00:00",
            "updated_at": "2026-11-26T08:00:00",
            "plan_check_status": "success",
            "plan_check_ok": True,
            "current_plan_type": "plus",
            **values,
        })
        self.ids[name] = account_id
        return account_id

    @staticmethod
    def _offer(
        *, country: str = "", plan: str, kind: str, eligible: bool = True,
        percentage=None, periods=None, period=None,
    ) -> dict:
        return {
            "country": country,
            "plan": plan,
            "kind": kind,
            "eligible": eligible,
            "discount_percentage": percentage,
            "duration_num_periods": periods,
            "duration_period": period,
        }

    def test_dynamic_offer_is_shared_by_list_count_status_and_bulk_facets(self):
        plus_offer = self._offer(
            country="US", plan="plus", kind="discount",
            percentage=50, periods=2, period="month",
        )
        plus_offer_jp = self._offer(
            country="JP", plan="plus", kind="discount",
            percentage=50, periods=2, period="months",
        )
        team_offer = self._offer(
            plan="team", kind="free_trial", periods=1, period="month",
        )
        go_offer = self._offer(
            plan="go", kind="discount", percentage=25, periods=1, period="month",
        )
        plus_id = self._account("plus", email_source="outlook", account_promotions=[plus_offer, plus_offer_jp])
        team_id = self._account("team", email_source="outlook", current_plan_type="free", account_promotions=[team_offer])
        go_id = self._account("go", email_source="icloud_hide", current_plan_type="go", account_promotions=[go_offer])
        plus_key = promotion_offers.offer_key("plus", "discount", 50, 2, "month")
        team_key = promotion_offers.offer_key("team", "free_trial", None, 1, "month")
        go_key = promotion_offers.offer_key("go", "discount", 25, 1, "month")

        spec = query.normalize_query({"filters": {"promotion": [plus_key]}})
        listed = repo.list_accounts(repo.PageRequest(page_size=50, filters={"promotion": plus_key}))
        counted = repo.account_query_count(spec)
        statuses = repo.list_account_statuses(
            repo.PageRequest(page_size=50, filters={"promotion": plus_key}),
        )
        facets = repo.account_query_facets(spec)

        self.assertEqual([row["id"] for row in listed["items"]], [plus_id])
        self.assertEqual(listed["total"], counted)
        self.assertEqual(statuses["total"], counted)
        self.assertEqual([row["id"] for row in statuses["items"]], [plus_id])
        promotion_facets = {
            item["value"]: item for item in listed["facets"]["promotion"]
        }
        self.assertEqual(promotion_facets[plus_key]["count"], 1)
        self.assertEqual(promotion_facets[team_key]["count"], 1)
        self.assertEqual(promotion_facets[go_key]["count"], 1)
        self.assertEqual(
            {item["value"]: item["count"] for item in facets["source"]},
            {"outlook": 1},
        )
        facet_counts = {item["value"]: item["count"] for item in facets["promotion"]}
        self.assertEqual(
            {key: facet_counts[key] for key in (plus_key, team_key, go_key)},
            {plus_key: 1, team_key: 1, go_key: 1},
        )
        self.assertEqual(promotion_facets[plus_key]["group"], "plus")
        self.assertTrue(promotion_facets[plus_key]["label"])

    def test_legacy_values_keep_plus_none_numeric_details_and_team_kind_semantics(self):
        none_id = self._account(
            "none", current_plan_type="plus", plus_promo_kind="none",
            account_promotions=[self._offer(plan="plus", kind="none", eligible=False)],
        )
        plus_id = self._account(
            "plus-50", current_plan_type="free",
            account_promotions=[self._offer(
                plan="plus", kind="discount", percentage=50, periods=2.0, period="month",
            )],
        )
        plus_text_id = self._account(
            "plus-50-text", current_plan_type="free",
            account_promotions=[self._offer(
                plan="plus", kind="discount", percentage=50, periods="2", period="month",
            )],
        )
        plus_chinese_period_id = self._account(
            "plus-50-chinese-period", current_plan_type="free",
            account_promotions=[self._offer(
                plan="plus", kind="discount", percentage=50, periods="2", period="个月",
            )],
        )
        go_numeric_id = self._account(
            "go-100", current_plan_type="free",
            account_promotions=[self._offer(
                plan="go", kind="free_trial", percentage=100, periods=1, period="month",
            )],
        )
        go_text_id = self._account(
            "go-text", current_plan_type="free",
            account_promotions=[self._offer(
                plan="go", kind="free_trial", percentage="100", periods=1, period="month",
            )],
        )
        team_trial_id = self._account(
            "team-trial", current_plan_type="free",
            account_promotions=[self._offer(plan="team", kind="free_trial", periods=1, period="month")],
        )
        team_unknown_id = self._account(
            "team-unknown", current_plan_type="free",
            account_promotions=[self._offer(plan="team", kind="unknown", periods=1, period="month")],
        )
        team_unknown_key = promotion_offers.offer_key("team", "unknown", None, 1, "month")

        def ids(value: str) -> set[int]:
            result = repo.list_accounts(
                repo.PageRequest(page_size=50, filters={"promotion": value}),
            )
            return {row["id"] for row in result["items"]}

        expected_none = {
            plus_id, plus_text_id, plus_chinese_period_id,
            go_numeric_id, go_text_id, team_trial_id, team_unknown_id,
        }
        self.assertEqual(ids("none"), expected_none)
        self.assertEqual(ids("ineligible"), expected_none)
        self.assertEqual(ids("plus_50"), {
            plus_id, plus_text_id, plus_chinese_period_id,
        })
        self.assertEqual(ids("plus_50_2m"), {plus_text_id})
        self.assertEqual(ids("go_100"), {go_numeric_id})
        self.assertEqual(ids("team_eligible"), {team_trial_id})
        self.assertNotIn(go_text_id, ids("go_100"))
        self.assertNotIn(team_unknown_id, ids("team_eligible"))
        unknown_result = repo.list_accounts(
            repo.PageRequest(page_size=50, filters={"promotion": team_unknown_key}),
        )
        self.assertEqual(unknown_result["total"], 0)
        self.assertNotIn(
            team_unknown_key,
            {item["value"] for item in unknown_result["facets"].get("promotion", [])},
        )

    def test_selected_zero_dynamic_offer_keeps_label_and_group_metadata(self):
        selected = self._offer(
            plan="plus", kind="discount", percentage=50, periods=3, period="month",
        )
        selected_key = promotion_offers.offer_key("plus", "discount", 50, 3, "month")
        self._account("out-of-scope", email_source="icloud_hide", account_promotions=[selected])
        result = repo.list_accounts(
            repo.PageRequest(page_size=50, filters={
                "promotion": selected_key,
                "source": "missing-source",
            }),
        )

        self.assertEqual(result["total"], 0)
        selected_rows = [
            item for item in result["facets"].get("promotion", [])
            if item["value"] == selected_key
        ]
        self.assertEqual(len(selected_rows), 1)
        self.assertEqual(selected_rows[0]["count"], 0)
        self.assertEqual(selected_rows[0]["group"], "plus")
        self.assertTrue(selected_rows[0]["label"])

    def test_selected_legacy_and_dynamic_facets_bind_other_filters_in_order(self):
        selected = self._offer(
            plan="plus", kind="discount", percentage=50, periods="2", period="month",
        )
        account_id = self._account(
            "mixed-selected", email_source="outlook", current_plan_type="free",
            account_promotions=[selected],
        )
        self._account(
            "mixed-other-source", email_source="icloud_hide", current_plan_type="free",
            account_promotions=[selected],
        )
        selected_key = promotion_offers.offer_key("plus", "discount", 50, 2, "month")
        filters = {
            "promotion": f"plus_50_2m,{selected_key}",
            "source": "outlook",
        }

        listed = repo.list_accounts(repo.PageRequest(page_size=50, filters=filters))
        self.assertEqual(listed["total"], 1)
        self.assertEqual([row["id"] for row in listed["items"]], [account_id])
        listed_promotion = {
            item["value"]: item["count"] for item in listed["facets"]["promotion"]
        }
        self.assertEqual(listed_promotion["plus_50_2m"], 1)
        self.assertEqual(listed_promotion[selected_key], 1)

        spec = query.normalize_query({
            "filters": {"promotion": ["plus_50_2m", selected_key], "source": ["outlook"]},
        })
        facets = repo.account_query_facets(spec)
        self.assertEqual(
            {item["value"]: item["count"] for item in facets["source"]},
            {"outlook": 1, "icloud_hide": 1},
        )
        batch_promotion = {
            item["value"]: item["count"] for item in facets["promotion"]
        }
        self.assertEqual(batch_promotion["plus_50_2m"], 1)
        self.assertEqual(batch_promotion[selected_key], 1)
