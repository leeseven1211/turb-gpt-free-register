# -*- coding: utf-8 -*-
"""验证优惠事实与查询投影在同一事务中写入。"""
import json
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from core import db
from core.accounts.plans.countries import aggregate_country_results
from core.storage import records as rs
from core.storage.accounts import plan_countries
from core.storage.email.collections import insert_many
from tests.support_pg import PostgresTestCase


_PLUS_OFFER = {
    "plan": "plus", "kind": "discount", "eligible": True,
    "discount_percentage": 50, "duration_num_periods": 1, "duration_period": "month",
}


class PromotionOfferLabelTests(TestCase):
    def test_offer_labels_show_half_price_nonstandard_periods_and_missing_details(self):
        from core.storage.accounts.promotion_offers import offer_label

        def label(**fields):
            return offer_label({**_PLUS_OFFER, "plan": "go", **fields})

        self.assertEqual(label(), "Go 半价 1个月")
        self.assertEqual(label(duration_num_periods=3, duration_period="季度"), "Go 半价 3季度")
        self.assertEqual(label(duration_num_periods=3, duration_period="semester"), "Go 半价 3semester")
        self.assertEqual(label(duration_num_periods=3, duration_period=None), "Go 半价 3（期限单位未返回）")
        self.assertEqual(label(duration_num_periods=None), "Go 半价（期限数量未返回，单位为个月）")
        self.assertEqual(label(
            discount_percentage=None, duration_num_periods=None, duration_period=None,
        ), "Go 折扣比例未返回（期限未返回）")
        self.assertNotIn("合成示例", label(duration_period="password=合成示例"))

    def test_label_distinguishes_recorded_discount_in_free_and_other_offers(self):
        from core.storage.accounts.promotion_offers import offer_label

        def label(kind, percentage):
            return offer_label({**_PLUS_OFFER, "kind": kind, "discount_percentage": percentage})

        self.assertEqual(label("free_trial", 100), "Plus 免费 1个月")
        self.assertEqual(label("free_trial", None), "Plus 免费 1个月（折扣比例未返回）")
        self.assertEqual(label("free_trial", 75), "Plus 免费 1个月（记录折扣 75%）")
        self.assertEqual(label("other_promo", 35), "Plus 其他优惠 1个月（减 35%）")
        self.assertEqual(label("other_promo", 75), "Plus 其他优惠 1个月（减 75%）")


class PromotionOfferProjectionTests(PostgresTestCase):
    def _offers(self, account_id, *, conn=None):
        if conn is None:
            with rs._connect() as own:
                return self._offers(account_id, conn=own)
        table = rs.postgres_store.qualified("account_promotion_offers")
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s) AS relation", (table,))
            self.assertIsNotNone(cur.fetchone()["relation"], "缺少账号优惠投影表")
            cur.execute(
                f"SELECT *, xmin::text AS row_version FROM {table} "
                "WHERE account_id = %s ORDER BY country, offer_key",
                (account_id,),
            )
            return cur.fetchall()

    def test_insert_projects_offers_and_deduplicates_same_country(self):
        offer = {**_PLUS_OFFER, "discount_percentage": 50.0, "duration_period": "months"}
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "projection@example.test",
            "account_promotions": [
                {**offer, "country": "JP", "campaign_id": "campaign-a", "stale": True},
                {**offer, "country": "JP", "campaign_id": "campaign-b"},
                {**offer, "country": "VN", "campaign_id": "campaign-c", "stale": True},
            ],
        })

        rows = self._offers(account_id)
        self.assertEqual([(r["country"], r["stale"]) for r in rows], [("JP", False), ("VN", True)])
        self.assertEqual(len({r["offer_key"] for r in rows}), 1)
        self.assertRegex(rows[0]["offer_key"], r"^offer_v1_[0-9a-f]{32}$")
        self.assertEqual(
            (rows[0]["plan"], rows[0]["kind"], rows[0]["eligible"],
             rows[0]["discount_percentage"], rows[0]["duration_num_periods"], rows[0]["duration_period"]),
            ("plus", "discount", True, Decimal("50"), Decimal("1"), "month"),
        )

    def test_offer_key_and_label_preserve_fractional_and_missing_fields(self):
        from core.storage.accounts.promotion_offers import offer_key, offer_label

        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "precision@example.test", "registration_country": "JP",
            "account_promotions": [{
                **_PLUS_OFFER, "plan": " PLUS ", "kind": "DISCOUNT",
                "discount_percentage": 12.75, "duration_num_periods": 1.25,
                "duration_period": " 月 ",
            }, {
                "plan": "team", "kind": "free_trial", "eligible": True,
                "duration_num_periods": 1, "duration_period": "month",
            }],
        })
        rows = {r["plan"]: r for r in self._offers(account_id)}
        plus, team = rows["plus"], rows["team"]
        self.assertEqual(
            plus["offer_key"],
            offer_key("plus", "discount", Decimal("12.7500"), Decimal("1.2500"), " MONTHS "),
        )
        self.assertEqual((plus["country"], plus["duration_period"]), ("", "month"))
        self.assertEqual(offer_label(plus), "Plus 减 12.75% 1.25个月")
        self.assertIsNone(team["discount_percentage"])
        self.assertEqual(team["offer_key"], offer_key("team", "free_trial", None, 1.0, "个月"))
        self.assertNotEqual(team["offer_key"], offer_key("team", "free_trial", 100, 1, "month"))
        self.assertEqual(offer_label(team), "Team 免费 1个月（折扣比例未返回）")

    def test_legacy_filter_values_follow_raw_activity_rules_after_normalized_deduplication(self):
        from core.storage.accounts.promotion_offers import offer_key

        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-code-parity@example.test",
            "account_promotions": [
                {**_PLUS_OFFER, "country": "JP", "duration_num_periods": 1.0},
                {**_PLUS_OFFER, "country": "VN", "duration_num_periods": "1", "duration_period": "MONTHS"},
                {**_PLUS_OFFER, "country": "VN", "duration_num_periods": 1, "duration_period": " 个月 "},
                {**_PLUS_OFFER, "country": "US", "discount_percentage": "50"},
                {**_PLUS_OFFER, "country": "ID", "plan": " PLUS "},
                {**_PLUS_OFFER, "country": "TH", "plan": "go", "discount_percentage": 25},
                {**_PLUS_OFFER, "country": "IN", "plan": "team", "discount_percentage": None},
            ],
        })
        rows = {r["country"]: r for r in self._offers(account_id)}
        self.assertEqual({country: row["legacy_filter_values"] for country, row in rows.items()}, {
            "ID": [], "IN": ["team_eligible"], "JP": ["plus_50"], "TH": ["go_other"],
            "US": [], "VN": ["plus_50", "plus_50_1m"],
        })
        self.assertEqual({rows[country]["offer_key"] for country in ("ID", "JP", "US", "VN")}, {
            offer_key("plus", "discount", "50", "1", "months"),
        })

    def test_legacy_filter_tracks_numeric_text_change_on_update(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-code-update@example.test", "account_promotions": [_PLUS_OFFER],
        })
        original = self._offers(account_id)[0]
        self.assertEqual(original["legacy_filter_values"], ["plus_50", "plus_50_1m"])
        self.assertTrue(rs.patch_row(rs.ACCOUNTS, account_id, {
            "account_promotions": [{**_PLUS_OFFER, "duration_num_periods": 1.0}],
        }))
        updated = self._offers(account_id)[0]
        self.assertEqual(updated["offer_key"], original["offer_key"])
        self.assertEqual(updated["legacy_filter_values"], ["plus_50"])

    def test_legacy_filter_fallback_uses_only_original_promoted_columns(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-filter-promoted@example.test", "plus_discount_eligible": True,
            "plus_promo_discount_percentage": 50, "plus_promo_duration_num_periods": 2,
            "plus_promo_duration_period": "months",
        })
        self.assertEqual([r["legacy_filter_values"] for r in self._offers(account_id)], [["plus_50", "plus_50_2m"]])

        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-filter-json@example.test", "plus_trial_discount_percentage": 50,
            "plus_trial_duration_num_periods": 2, "plus_trial_duration_period": "months",
        })
        self.assertEqual([(r["discount_percentage"], r["legacy_filter_values"]) for r in self._offers(account_id)], [(50, [])])

    def test_legacy_filter_keeps_codes_when_normalized_kind_disagrees(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-kind-whitespace@example.test", "plus_promo_kind": " none ",
            "plus_discount_eligible": True, "plus_promo_discount_percentage": 50,
            "plus_promo_duration_num_periods": 1, "plus_promo_duration_period": "month",
        })
        self.assertEqual([
            (r["kind"], r["eligible"], r["legacy_filter_values"]) for r in self._offers(account_id)
        ], [("none", False, ["plus_50", "plus_50_1m"])])

    def test_failed_query_and_legacy_success_preserve_last_offers(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {"email": "success-snapshot@example.test"})
        self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
            "ok": True, "current_plan_type": "free", "account_promotions": [_PLUS_OFFER],
            "plus_promo_kind": "discount", "plus_promo_discount_percentage": 50,
        }))
        rows = self._offers(account_id)
        self.assertEqual(len(rows), 1)
        self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
            "ok": False, "error": "HTTP 503", "account_promotions": [],
        }))
        self.assertEqual(self._offers(account_id), rows)
        self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
            "ok": True, "current_plan_type": "free", "plus_trial_eligible": False,
        }))
        self.assertEqual(self._offers(account_id), rows)

    def test_success_without_promotion_fields_preserves_legacy_promoted_offer(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-success@example.test", "current_plan_type": "free",
            "plus_promo_kind": "discount", "plus_promo_discount_percentage": 50,
            "plus_promo_duration_num_periods": 2, "plus_promo_duration_period": "month",
        })
        rows = self._offers(account_id)
        self.assertEqual(len(rows), 1)
        self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
            "ok": True, "current_plan_type": "free",
        }))
        row = rs.get_row(rs.ACCOUNTS, account_id)
        self.assertEqual((row["plus_promo_kind"], row["plus_promo_discount_percentage"]), ("discount", 50))
        self.assertEqual(self._offers(account_id), rows)
        self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
            "ok": True, "current_plan_type": "free", "plus_trial_discount_percentage": 100,
            "plus_trial_duration_num_periods": 1, "plus_trial_duration_period": "month",
        }))
        current = self._offers(account_id)
        self.assertEqual([(r["kind"], r["discount_percentage"]) for r in current], [("free_trial", 100)])

    def test_plan_success_without_promotion_fields_does_not_invent_none(self):
        from core.storage.accounts.promotion_offers import LEGACY_OFFER_CHECKED_FIELD, TABLE_NAME, ensure_schema

        for name, legacy_fields in [("empty", {}), ("old-default", {
            "plus_promo_kind": "none", "plus_promo_eligible": False,
            "plus_discount_eligible": False, "plus_trial_eligible": False,
        })]:
            with self.subTest(history=name):
                account_id = rs.insert_row(rs.ACCOUNTS, {
                    "email": f"missing-first-offer-{name}@example.test", **legacy_fields,
                })
                self.assertEqual(self._offers(account_id), [])
                self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
                    "ok": True, "current_plan_type": "free",
                }))
                self.assertEqual(self._offers(account_id), [])
                with rs._connect() as conn:
                    ensure_schema(conn)
                self.assertEqual(self._offers(account_id), [])
                self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
                    "ok": True, "current_plan_type": "free", "plus_trial_eligible": False,
                    "checked_at": "2026-11-20T02:00:00+00:00",
                }))
                confirmed = self._offers(account_id)
                self.assertEqual([(r["kind"], r["eligible"]) for r in confirmed], [("none", False)])
                self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
                    "ok": True, "current_plan_type": "free", "checked_at": "2026-11-21T02:00:00+00:00",
                }))
                self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
                    "ok": False, "error": "HTTP 503", "checked_at": "2026-11-22T02:00:00+00:00",
                }))
                self.assertEqual(self._offers(account_id), confirmed)
                account = rs.get_row(rs.ACCOUNTS, account_id)
                self.assertEqual(account[LEGACY_OFFER_CHECKED_FIELD], "2026-11-20T02:00:00+00:00")
                with rs._connect() as conn, conn.cursor() as cur:
                    # 移除投影来验证从保留下来的账号证据恢复，而非跳过已有行。
                    cur.execute(f"DELETE FROM {rs.postgres_store.qualified(TABLE_NAME)} WHERE account_id = %s", (account_id,))
                    ensure_schema(conn)
                self.assertEqual([(r["kind"], r["eligible"]) for r in self._offers(account_id)], [("none", False)])

    def test_explicit_empty_snapshot_clears_offers_even_with_eligible_legacy_fields(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "empty-snapshot@example.test", "account_promotions": [_PLUS_OFFER],
        })
        self.assertEqual(len(self._offers(account_id)), 1)
        self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
            "ok": True, "current_plan_type": "free", "account_promotions": [],
            "plus_promo_kind": "discount", "plus_promo_discount_percentage": 50,
        }))
        self.assertEqual(self._offers(account_id), [])

    def test_none_unknown_and_unqueried_remain_distinct(self):
        checked = rs.insert_row(rs.ACCOUNTS, {
            "email": "states@example.test", "account_promotions": [
                {"plan": "go", "kind": "unknown", "eligible": False},
                {"plan": "plus", "kind": "none", "eligible": False},
            ],
        })
        unqueried = rs.insert_row(rs.ACCOUNTS, {
            "email": "unqueried@example.test", "plus_promo_kind": "none",
        })
        self.assertEqual({(r["plan"], r["kind"], r["eligible"]) for r in self._offers(checked)}, {
            ("go", "unknown", False), ("plus", "none", False),
        })
        self.assertEqual(self._offers(unqueried), [])
        self.assertTrue(db.update_account_plan_check(acc_id=unqueried, result={
            "ok": True, "current_plan_type": "free", "plus_trial_eligible": False,
        }))
        self.assertEqual([(r["plan"], r["kind"]) for r in self._offers(unqueried)], [("plus", "none")])

    def test_direct_success_confirmation_projects_saved_legacy_none(self):
        from core.storage.accounts.promotion_offers import TABLE_NAME, ensure_schema

        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-direct-confirmation@example.test", "plus_promo_kind": "none",
        })
        self.assertEqual(self._offers(account_id), [])
        self.assertTrue(rs.patch_row(rs.ACCOUNTS, account_id, {"plan_check_status": "success"}))
        self.assertEqual([
            (r["plan"], r["kind"], r["eligible"]) for r in self._offers(account_id)
        ], [("plus", "none", False)])
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {rs.postgres_store.qualified(TABLE_NAME)} WHERE account_id = %s", (account_id,))
            ensure_schema(conn)
        self.assertEqual([(r["plan"], r["kind"]) for r in self._offers(account_id)], [("plus", "none")])

    def test_direct_write_of_legacy_offer_evidence_updates_projection(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-direct-offer-evidence@example.test", "plus_promo_kind": "none",
            "plan_check_status": "success",
            "plan_last_success_result_json": json.dumps({"ok": True, "current_plan_type": "free"}),
        })
        self.assertEqual(self._offers(account_id), [])
        self.assertTrue(rs.patch_row(rs.ACCOUNTS, account_id, {
            "plan_last_success_result_json": json.dumps({"ok": True, "plus_trial_eligible": False}),
        }))
        self.assertEqual([(r["plan"], r["kind"]) for r in self._offers(account_id)], [("plus", "none")])

    def test_legacy_none_remains_rebuildable_after_success_without_offer_fields(self):
        from core.storage.accounts.promotion_offers import TABLE_NAME, ensure_schema

        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-none-rebuild@example.test", "plus_promo_kind": "none",
            "plan_check_status": "success",
        })
        self.assertEqual([(r["kind"], r["eligible"]) for r in self._offers(account_id)], [("none", False)])
        self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
            "ok": True, "current_plan_type": "free",
        }))
        self.assertEqual([(r["kind"], r["eligible"]) for r in self._offers(account_id)], [("none", False)])
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {rs.postgres_store.qualified(TABLE_NAME)} WHERE account_id = %s", (account_id,))
            ensure_schema(conn)
        self.assertEqual([(r["kind"], r["eligible"]) for r in self._offers(account_id)], [("none", False)])

    def test_failed_recheck_preserves_legacy_none_without_a_success_timestamp(self):
        evidence = {"status": {"plan_check_status": "success"}, "flag": {"plan_check_ok": True}}
        for source, legacy in evidence.items():
            with self.subTest(source=source):
                account_id = rs.insert_row(rs.ACCOUNTS, {
                    "email": f"legacy-{source}@example.test", "current_plan_type": "free",
                    "plus_promo_kind": "none", **legacy,
                })
                previous = self._offers(account_id)
                self.assertEqual([(r["plan"], r["kind"]) for r in previous], [("plus", "none")])
                self.assertIsNone(rs.get_row(rs.ACCOUNTS, account_id)["plan_last_success_at"])
                self.assertTrue(db.claim_account_plan_check(acc_id=account_id))
                self.assertEqual(self._offers(account_id), previous)
                self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
                    "ok": False, "error": "HTTP 503",
                }))
                self.assertEqual(self._offers(account_id), previous)

    def test_collection_insert_projects_legacy_plus_metadata_without_promoted_columns(self):
        with rs.transaction() as conn:
            by_percentage, by_campaign, by_flag = insert_many(conn, rs.ACCOUNTS, [
                {
                    "email": "legacy-percentage@example.test", "plus_trial_discount_percentage": "50",
                    "plus_trial_duration_num_periods": 1.5, "plus_trial_duration_period": "months",
                    "plus_trial_campaign_id": None, "plus_trial_eligible": False,
                }, {
                    "email": "legacy-campaign@example.test", "plus_trial_discount_percentage": None,
                    "plus_trial_duration_num_periods": 1, "plus_trial_duration_period": "month",
                    "plus_trial_campaign_id": "legacy-plus-trial", "plus_trial_eligible": True,
                }, {
                    "email": "legacy-flag@example.test", "plus_trial_discount_percentage": None,
                    "plus_trial_duration_num_periods": None, "plus_trial_duration_period": None,
                    "plus_trial_campaign_id": None, "plus_trial_eligible": True,
                },
            ])
            for row, kind, eligible, percentage, periods, unit in [
                (by_percentage, "discount", True, 50, Decimal("1.5"), "month"),
                (by_campaign, "free_trial", True, None, 1, "month"),
                (by_flag, "unknown", False, None, None, None),
            ]:
                with self.subTest(kind=kind):
                    self.assertEqual([
                        (o["kind"], o["eligible"], o["discount_percentage"], o["duration_num_periods"], o["duration_period"])
                        for o in self._offers(row["id"], conn=conn)
                    ], [(kind, eligible, percentage, periods, unit)])

    def test_direct_patch_updates_legacy_duration_when_only_json_keeps_the_value(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "legacy-duration-patch@example.test", "plus_promo_kind": "discount",
            "plus_promo_discount_percentage": 50, "plus_trial_duration_num_periods": 1.5,
            "plus_promo_duration_period": "month",
        })
        self.assertTrue(rs.patch_row(rs.ACCOUNTS, account_id, {"plus_trial_duration_num_periods": "2.25"}))
        rows = self._offers(account_id)
        self.assertEqual([r["duration_num_periods"] for r in rows], [Decimal("2.25")])

    def test_legacy_float_key_is_independent_of_session_precision(self):
        from core.storage.accounts.promotion_offers import offer_key

        percentage = 49.99999999999999
        with rs.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL extra_float_digits = 0")
            account_id = rs.insert_row(rs.ACCOUNTS, {
                "email": "legacy-float@example.test", "plus_promo_kind": "discount",
                "plus_promo_discount_percentage": percentage,
            }, conn=conn)
            rows = self._offers(account_id, conn=conn)
            self.assertEqual([r["offer_key"] for r in rows], [offer_key("plus", "discount", percentage, None, None)])
            self.assertEqual(rows[0]["discount_percentage"], Decimal("49.99999999999999"))

    def test_plan_save_preserves_unrounded_legacy_duration_for_dynamic_offer(self):
        from core.storage.accounts.promotion_offers import offer_key

        for index, duration in enumerate((1.5, 2.5)):
            with self.subTest(duration=duration):
                account_id = rs.insert_row(rs.ACCOUNTS, {"email": f"legacy-saved-fraction-{index}@example.test"})
                self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
                    "ok": True, "current_plan_type": "free", "plus_trial_discount_percentage": 50,
                    "plus_trial_duration_num_periods": duration, "plus_trial_duration_period": "month",
                }))
                account = rs.get_row(rs.ACCOUNTS, account_id)
                self.assertIn(account["plus_promo_duration_num_periods"], (2, 3))
                self.assertEqual(account["plus_trial_duration_num_periods"], duration)
                row, = self._offers(account_id)
                self.assertEqual(row["duration_num_periods"], Decimal(str(duration)))
                self.assertEqual(row["offer_key"], offer_key("plus", "discount", 50, duration, "month"))
                legacy_periods = account["plus_promo_duration_num_periods"]
                self.assertEqual(row["legacy_filter_values"], ["plus_50", f"plus_50_{legacy_periods}m"])
                explicit_periods = 1 if duration == 1.5 else 4
                self.assertTrue(rs.patch_row(rs.ACCOUNTS, account_id, {
                    "plus_promo_duration_num_periods": explicit_periods,
                }))
                updated, = self._offers(account_id)
                self.assertEqual(updated["duration_num_periods"], explicit_periods)
                expected = ["plus_50", "plus_50_1m"] if explicit_periods == 1 else ["plus_50"]
                self.assertEqual(updated["legacy_filter_values"], expected)

    def test_plan_save_recovers_positive_fraction_rounded_to_zero(self):
        from core.storage.accounts.promotion_offers import offer_key

        account_id = rs.insert_row(rs.ACCOUNTS, {"email": "legacy-subperiod@example.test"})
        self.assertTrue(db.update_account_plan_check(acc_id=account_id, result={
            "ok": True, "current_plan_type": "free", "plus_trial_discount_percentage": 50,
            "plus_trial_duration_num_periods": 0.25, "plus_trial_duration_period": "month",
        }))
        account = rs.get_row(rs.ACCOUNTS, account_id)
        self.assertEqual(account["plus_promo_duration_num_periods"], 0)
        row, = self._offers(account_id)
        self.assertEqual(row["duration_num_periods"], Decimal("0.25"))
        self.assertEqual(row["offer_key"], offer_key("plus", "discount", 50, 0.25, "month"))
        self.assertEqual(row["legacy_filter_values"], ["plus_50"])

    def test_evidence_only_changes_keep_identical_projection_rows(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "evidence-only@example.test", "account_promotions": [_PLUS_OFFER],
        })
        before = self._offers(account_id)
        self.assertEqual(len(before), 1)
        self.assertTrue(rs.patch_row(rs.ACCOUNTS, account_id, {
            "account_promotions": [{**_PLUS_OFFER, "title": "更新活动名", "checkout_status": "ready"}],
        }))
        self.assertEqual(self._offers(account_id), before)

    def test_unrelated_patch_and_archive_keep_projection_rows(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "archive@example.test", "account_promotions": [_PLUS_OFFER],
        })
        rows = self._offers(account_id)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rs.patch_row(rs.ACCOUNTS, account_id, {"note": "已核对"}))
        self.assertTrue(rs.patch_row(rs.ACCOUNTS, account_id, {"archived": True}))
        self.assertTrue(rs.get_row(rs.ACCOUNTS, account_id)["archived"])
        self.assertEqual(self._offers(account_id), rows)
        self.assertEqual(rs.delete_rows(rs.ACCOUNTS, [account_id]), 1)
        self.assertEqual(self._offers(account_id), [])

    def test_country_checkpoint_does_not_publish_offer_until_summary_is_saved(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "country-checkpoint@example.test", "account_promotions": [_PLUS_OFFER],
        })
        rows = self._offers(account_id)
        plan_countries.initialize_country_checks(account_id, ["JP"])
        countries = plan_countries.record_country_result(account_id, "JP", {
            "ok": True, "current_plan_type": "free", "account_promotions": [{
                **_PLUS_OFFER, "duration_num_periods": 2,
            }],
        })
        self.assertEqual(self._offers(account_id), rows)

        self.assertTrue(plan_countries.save_country_summary(account_id, aggregate_country_results(countries)))
        self.assertEqual([(r["country"], r["duration_num_periods"]) for r in self._offers(account_id)], [("JP", 2)])

    def test_collection_insert_and_versioned_write_are_atomic_with_the_account(self):
        with rs.transaction() as conn:
            account, = insert_many(conn, rs.ACCOUNTS, [{
                "email": "collection@example.test", "account_promotions": [_PLUS_OFFER],
            }])
            account_id = account["id"]
            self.assertEqual(len(self._offers(account_id, conn=conn)), 1)
        previous = self._offers(account_id)
        version = rs.get_row(rs.ACCOUNTS, account_id, include_version=True)["__record_version"]
        with self.assertRaisesRegex(RuntimeError, "模拟回滚"):
            with rs.transaction() as conn:
                self.assertTrue(rs.patch_row_if_version(rs.ACCOUNTS, account_id, {
                    "data": {"account_promotions": []},
                }, version, conn=conn))
                self.assertEqual(self._offers(account_id, conn=conn), [])
                raise RuntimeError("模拟回滚")
        self.assertEqual(self._offers(account_id), previous)
        self.assertEqual(rs.get_row(rs.ACCOUNTS, account_id)["account_promotions"], [_PLUS_OFFER])
        self.assertTrue(rs.patch_row_if_version(rs.ACCOUNTS, account_id, {
            "data": {"account_promotions": []},
        }, version))
        self.assertEqual(self._offers(account_id), [])

    def test_v2_backfill_uses_current_snapshot_and_legacy_fields_without_reapplying_v1(self):
        from core.storage.accounts import promotion_offers
        from core.storage.email import inventory_indexes

        rs.init()
        accounts = rs.postgres_store.qualified(rs.ACCOUNTS.name)
        migrations = rs.postgres_store.qualified(rs._SCHEMA_MIGRATIONS)
        offers = rs.postgres_store.qualified(promotion_offers.TABLE_NAME)
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DROP TRIGGER sync_account_promotion_offers ON {accounts}")
            cur.execute(f"DROP TABLE {offers}")
            cur.execute(f"DELETE FROM {migrations} WHERE version = 3")
            for account_id, periods, snapshot in [
                (10, 2, {}),
                (20, 2, {"account_promotions": []}),
                (30, 2, {"account_promotions": [
                    {**_PLUS_OFFER, "duration_num_periods": 3, "country": "VN", "stale": True},
                ]}),
                (40, None, {"plus_trial_duration_num_periods": 1.5}),
                (50, None, {"plus_trial_duration_num_periods": "不是数字"}),
            ]:
                cur.execute(
                    f"""INSERT INTO {accounts} (
                        id, email, created_at, updated_at, plus_promo_kind,
                        plus_promo_discount_percentage, plus_promo_duration_num_periods,
                        plus_promo_duration_period, data
                    ) VALUES (%s, %s, '', '', 'discount', 50, %s, 'months', %s::jsonb)""",
                    (account_id, f"fixture-{account_id}@example.test", periods, json.dumps(snapshot)),
                )
            cur.execute(f"""INSERT INTO {accounts} (
                    id, email, created_at, updated_at, plan_check_status, plus_promo_kind
                ) VALUES (60, 'legacy-none-backfill@example.test', '', '', 'success', 'none')""")

        rs.reset_ready()
        with (
            patch.object(rs, "_apply_record_schema", side_effect=AssertionError("v1 已完成")),
            patch.object(inventory_indexes, "ensure_indexes", side_effect=AssertionError("v2 已完成")),
        ):
            rs.init()
        legacy = self._offers(10)
        self.assertEqual([(r["country"], r["plan"], r["duration_num_periods"]) for r in legacy], [("", "plus", 2)])
        self.assertEqual(promotion_offers.offer_label(legacy[0]), "Plus 半价 2个月")
        self.assertEqual(self._offers(20), [])
        self.assertEqual([(r["country"], r["duration_num_periods"], r["stale"]) for r in self._offers(30)], [
            ("VN", 3, True),
        ])
        fractional = self._offers(40)
        self.assertEqual(fractional[0]["duration_num_periods"], Decimal("1.5"))
        self.assertEqual(promotion_offers.offer_label(fractional[0]), "Plus 半价 1.5个月")
        self.assertIsNone(self._offers(50)[0]["duration_num_periods"])
        self.assertEqual([(r["kind"], r["eligible"]) for r in self._offers(60)], [("none", False)])
        with rs._connect() as conn:
            self.assertTrue(rs._migration_completed(conn, 3))
            promotion_offers.ensure_schema(conn)
        self.assertEqual(self._offers(10), legacy)

    def test_v2_backfill_accepts_history_containing_json_not_convertible_to_jsonb(self):
        from core.storage.accounts.promotion_offers import TABLE_NAME

        rs.init()
        accounts = rs.postgres_store.qualified(rs.ACCOUNTS.name)
        migrations = rs.postgres_store.qualified(rs._SCHEMA_MIGRATIONS)
        offers = rs.postgres_store.qualified(TABLE_NAME)
        prior_result = json.dumps({"details": chr(0)})
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DROP TRIGGER sync_account_promotion_offers ON {accounts}")
            cur.execute(f"DROP TABLE {offers}")
            cur.execute(f"DELETE FROM {migrations} WHERE version = %s", (rs._PROMOTION_OFFERS_SCHEMA_VERSION,))
            cur.execute(
                f"""INSERT INTO {accounts} (
                    email, created_at, updated_at, plan_check_status, plus_promo_kind, data
                ) VALUES ('legacy-escaped-result@example.test', '', '', 'success', 'none', %s::JSONB)
                RETURNING id""",
                (json.dumps({"plan_last_success_result_json": prior_result}),),
            )
            account_id = cur.fetchone()["id"]

        rs.reset_ready()
        rs.init()
        with rs._connect() as conn:
            self.assertTrue(rs._migration_completed(conn, rs._PROMOTION_OFFERS_SCHEMA_VERSION))
        self.assertEqual([(r["kind"], r["eligible"]) for r in self._offers(account_id)], [("none", False)])
