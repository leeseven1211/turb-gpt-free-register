"""每日注册优惠统计的纯证据分类。"""
from __future__ import annotations

from copy import deepcopy
from importlib import import_module
import json
import unittest


def no_offer_result() -> dict:
    return {
        "ok": True,
        "account_promotions": [
            {"plan": "go", "kind": "none", "eligible": False},
            {"plan": "plus", "kind": "none", "eligible": False},
            {"plan": "team", "kind": "none", "eligible": False},
        ],
        "promotion_query_snapshot": {"truncated": False},
    }


def country_result(country: str, result: dict | None = None) -> dict:
    return {
        "country": country,
        "status": "success",
        "result": no_offer_result() if result is None else result,
    }


def multi_country_result() -> dict:
    return {
        **no_offer_result(),
        "plan_check_countries": ["JP", "US"],
        "plan_check_partial": False,
        "plan_check_country_results": [country_result("JP"), country_result("US")],
    }


class RegistrationPromotionPresenceTests(unittest.TestCase):
    def setUp(self):
        try:
            module = import_module("core.storage.registration.promotion_presence")
        except ModuleNotFoundError as exc:
            if exc.name != "core.storage.registration.promotion_presence":
                raise
            self.fail("promotion_presence_from_snapshot is not implemented")
        self.classify = module.promotion_presence_from_snapshot

    def test_any_supported_plan_with_a_known_fresh_offer_is_eligible(self):
        for plan in ("go", "plus", "team"):
            for kind in ("free_trial", "discount", "other_promo"):
                with self.subTest(plan=plan, kind=kind):
                    result = {
                        "ok": True,
                        "account_promotions": [{"plan": plan, "kind": kind, "eligible": True}],
                    }
                    self.assertEqual(self.classify(result), "eligible")

    def test_positive_evidence_precedes_incomplete_or_contradictory_other_items(self):
        result = {
            "ok": True,
            "account_promotions": [
                {"plan": [], "kind": "none", "eligible": False},
                {"plan": "team", "kind": "free_trial", "eligible": True},
                {"plan": "go", "kind": "unknown", "eligible": False},
                {"plan": "plus", "kind": "none", "eligible": True},
                None,
            ],
            "promotion_query_snapshot": {"truncated": True},
        }
        self.assertEqual(self.classify(result), "eligible")

    def test_complete_single_country_without_offers_is_none(self):
        self.assertEqual(self.classify(no_offer_result()), "none")

    def test_json_object_string_has_the_same_contract(self):
        self.assertEqual(self.classify(json.dumps(no_offer_result())), "none")
        result = no_offer_result()
        result["account_promotions"][2].update(kind="discount", eligible=True)
        self.assertEqual(self.classify(json.dumps(result)), "eligible")

    def test_unknown_or_malformed_input_is_unknown(self):
        for value in (None, False, 1, [], "", "{broken", "[]", "null", "true", '"{}"', {}):
            with self.subTest(value=value):
                self.assertEqual(self.classify(value), "unknown")

    def test_success_must_be_the_boolean_true(self):
        for ok in (None, False, 0, 1, "true", "success"):
            with self.subTest(ok=ok):
                result = no_offer_result()
                result["ok"] = ok
                result["account_promotions"][2].update(kind="discount", eligible=True)
                self.assertEqual(self.classify(result), "unknown")

    def test_legacy_plus_none_or_missing_team_cannot_prove_none(self):
        cases = [
            {"ok": True, "plus_promo_kind": "none", "plus_promo_eligible": False},
            {**no_offer_result(), "account_promotions": no_offer_result()["account_promotions"][:2]},
            {**no_offer_result(), "account_promotions": []},
            {**no_offer_result(), "account_promotions": None},
        ]
        for result in cases:
            with self.subTest(result=result):
                self.assertEqual(self.classify(result), "unknown")

    def test_none_requires_a_complete_nontruncated_query_snapshot(self):
        for evidence in (None, {}, {"truncated": True}, {"truncated": 0}, {"truncated": "false"}):
            with self.subTest(evidence=evidence):
                result = no_offer_result()
                result["promotion_query_snapshot"] = evidence
                self.assertEqual(self.classify(result), "unknown")

    def test_stale_or_expired_items_cannot_prove_an_offer_or_none(self):
        for field in ("stale", "expired"):
            for marker in (True, 1, "false"):
                for kind, eligible in (("none", False), ("discount", True)):
                    with self.subTest(field=field, marker=marker, kind=kind):
                        result = no_offer_result()
                        result["account_promotions"][2].update(
                            kind=kind, eligible=eligible, **{field: marker},
                        )
                        self.assertEqual(self.classify(result), "unknown")

    def test_false_or_absent_freshness_markers_are_compatible(self):
        result = no_offer_result()
        result["account_promotions"][2].update(stale=False, expired=False)
        self.assertEqual(self.classify(result), "none")
        result["account_promotions"][2].update(kind="free_trial", eligible=True)
        self.assertEqual(self.classify(result), "eligible")

    def test_unknown_kinds_and_inconsistent_eligible_values_are_unknown(self):
        for kind, eligible in (
            ("unknown", True), ("unknown", False), ("none", True), ("none", 0),
            ("none", None), ("discount", False), ("discount", 1), ("discount", "true"),
        ):
            with self.subTest(kind=kind, eligible=eligible):
                result = no_offer_result()
                result["account_promotions"][2].update(kind=kind, eligible=eligible)
                self.assertEqual(self.classify(result), "unknown")

    def test_all_campaigns_of_each_plan_must_prove_none(self):
        result = no_offer_result()
        result["account_promotions"].append({"plan": "team", "kind": "unknown", "eligible": False})
        self.assertEqual(self.classify(result), "unknown")
        result["account_promotions"][-1].update(kind="none")
        self.assertEqual(self.classify(result), "none")

    def test_malformed_or_unsupported_campaign_cannot_certify_none(self):
        for item in (
            None, "none", {},
            {"plan": "other", "kind": "none", "eligible": False},
            {"plan": [], "kind": "none", "eligible": False},
            {"plan": "team", "kind": {}, "eligible": False},
        ):
            with self.subTest(item=item):
                result = no_offer_result()
                result["account_promotions"].append(item)
                self.assertEqual(self.classify(result), "unknown")
                self.assertEqual(self.classify(json.dumps(result)), "unknown")

    def test_complete_multicountry_none_uses_each_country_result(self):
        result = multi_country_result()
        result["account_promotions"] = []
        result.pop("promotion_query_snapshot")
        self.assertEqual(self.classify(result), "none")

    def test_multicountry_lead_none_does_not_cover_failed_or_missing_country(self):
        for mutate in (
            lambda r: r["plan_check_country_results"].pop(),
            lambda r: r["plan_check_country_results"][1].update(status="failed"),
            lambda r: r.update(plan_check_partial=True),
            lambda r: r["plan_check_country_results"][1].update(result=None),
            lambda r: r["plan_check_country_results"][1]["result"].update(ok=False),
        ):
            result = multi_country_result()
            mutate(result)
            with self.subTest(result=result):
                self.assertEqual(self.classify(result), "unknown")

    def test_multicountry_none_rejects_duplicate_or_unexpected_countries(self):
        cases = [
            (["JP", "JP"], [country_result("JP"), country_result("JP")]),
            (["JP", "US"], [country_result("JP"), country_result("JP")]),
            (["JP", "US"], [country_result("JP"), country_result("DE")]),
            (["JP", "US"], [country_result("JP"), country_result("US"), country_result("DE")]),
            (["JP", "jp"], [country_result("JP"), country_result("jp")]),
        ]
        for countries, rows in cases:
            with self.subTest(countries=countries, rows=rows):
                result = multi_country_result()
                result.update(plan_check_countries=countries, plan_check_country_results=rows)
                self.assertEqual(self.classify(result), "unknown")

    def test_each_country_must_cover_three_plans_without_truncation(self):
        for mutate in (
            lambda r: r["account_promotions"].pop(),
            lambda r: r["promotion_query_snapshot"].update(truncated=True),
            lambda r: r.pop("promotion_query_snapshot"),
            lambda r: r["account_promotions"][2].update(kind="unknown"),
            lambda r: r["account_promotions"][2].update(stale=True),
        ):
            result = multi_country_result()
            mutate(result["plan_check_country_results"][1]["result"])
            with self.subTest(result=result):
                self.assertEqual(self.classify(result), "unknown")

    def test_multicountry_markers_cannot_fall_back_to_single_country_none(self):
        for country_list in (None, [], "JP", ["JP", None]):
            with self.subTest(country_list=country_list):
                result = multi_country_result()
                if country_list is None:
                    result.pop("plan_check_countries")
                else:
                    result["plan_check_countries"] = country_list
                self.assertEqual(self.classify(result), "unknown")
        result = no_offer_result()
        result["account_promotions"][0]["country"] = "JP"
        self.assertEqual(self.classify(result), "unknown")

    def test_fresh_multicountry_positive_precedes_partial_failure(self):
        result = multi_country_result()
        result["plan_check_partial"] = True
        result["plan_check_country_results"][1]["status"] = "failed"
        result["account_promotions"] = [
            {"plan": "team", "kind": "free_trial", "eligible": True, "country": "JP", "stale": False},
        ]
        self.assertEqual(self.classify(result), "eligible")

    def test_successful_country_can_supply_positive_when_top_level_is_missing(self):
        result = multi_country_result()
        result["account_promotions"] = []
        result["plan_check_country_results"][0]["result"]["account_promotions"][2].update(
            kind="free_trial", eligible=True,
        )
        result["plan_check_country_results"][1]["status"] = "failed"
        result["plan_check_partial"] = True
        self.assertEqual(self.classify(result), "eligible")

    def test_failed_country_retained_positive_is_not_current_positive(self):
        result = multi_country_result()
        result["account_promotions"] = []
        result["plan_check_country_results"][1]["status"] = "failed"
        result["plan_check_country_results"][1]["result"]["account_promotions"][2].update(
            kind="free_trial", eligible=True,
        )
        result["plan_check_partial"] = True
        self.assertEqual(self.classify(result), "unknown")

    def test_current_account_stage_fields_do_not_override_last_success_snapshot(self):
        for status in ("queued", "running", "failed"):
            with self.subTest(status=status):
                result = no_offer_result()
                result.update(plan_check_status=status, plan_check_ok=False)
                self.assertEqual(self.classify(result), "none")

    def test_classifier_does_not_mutate_snapshot(self):
        result = multi_country_result()
        before = deepcopy(result)
        self.assertEqual(self.classify(result), "none")
        self.assertEqual(result, before)


class FreshPromotionOffersTests(unittest.TestCase):
    def setUp(self):
        module = import_module("core.storage.registration.promotion_presence")
        self.assertTrue(
            hasattr(module, "fresh_promotion_offers_from_snapshot"),
            "fresh_promotion_offers_from_snapshot is not implemented",
        )
        self.extract = module.fresh_promotion_offers_from_snapshot

    def test_returns_all_supported_fresh_positive_items_without_rewriting_them(self):
        items = [
            {"plan": "team", "kind": "free_trial", "eligible": True, "title": "Team offer"},
            {"plan": "plus", "kind": "discount", "eligible": True, "discount_percentage": 50},
            {"plan": "go", "kind": "other_promo", "eligible": True, "country": "JP"},
        ]
        result = self.extract({"ok": True, "account_promotions": items})
        self.assertEqual(result, items)
        self.assertTrue(all(actual is original for actual, original in zip(result, items)))

    def test_rejects_stale_expired_unknown_contradictory_and_malformed_items(self):
        invalid = [
            None, {}, {"plan": [], "kind": "discount", "eligible": True},
            {"plan": "team", "kind": {}, "eligible": True},
            {"plan": "other", "kind": "discount", "eligible": True},
            {"plan": "team", "kind": "none", "eligible": True},
            {"plan": "team", "kind": "unknown", "eligible": True},
            {"plan": "team", "kind": "discount", "eligible": False},
            {"plan": "team", "kind": "discount", "eligible": 1},
            {"plan": "team", "kind": "discount", "eligible": "true"},
            {"plan": "team", "kind": "discount", "eligible": True, "stale": True},
            {"plan": "team", "kind": "discount", "eligible": True, "expired": True},
            {"plan": "team", "kind": "discount", "eligible": True, "expired": "false"},
        ]
        valid = {"plan": "team", "kind": "discount", "eligible": True, "stale": False, "expired": False}
        result = self.extract({"ok": True, "account_promotions": [*invalid, valid]})
        self.assertEqual(result, [valid])

    def test_successful_country_offers_follow_top_level_items(self):
        top = {"plan": "team", "kind": "free_trial", "eligible": True}
        country_offer = {"plan": "go", "kind": "discount", "eligible": True}
        failed_offer = {"plan": "plus", "kind": "discount", "eligible": True}
        result = {
            "ok": True,
            "account_promotions": [top],
            "plan_check_partial": True,
            "plan_check_country_results": [
                {"country": "JP", "status": "success", "result": {
                    "ok": True, "account_promotions": [country_offer],
                }},
                {"country": "US", "status": "failed", "result": {
                    "ok": True, "account_promotions": [failed_offer],
                }},
                {"country": "DE", "status": "success", "result": {
                    "ok": False, "account_promotions": [failed_offer],
                }},
                None,
            ],
        }
        self.assertEqual(self.extract(result), [top, country_offer])

    def test_duplicates_are_retained_for_the_consumer_to_group(self):
        item = {"plan": "team", "kind": "free_trial", "eligible": True}
        result = {
            "ok": True,
            "account_promotions": [item, item],
            "plan_check_country_results": [
                {"country": "JP", "status": "success", "result": {
                    "ok": True, "account_promotions": [item],
                }},
            ],
        }
        self.assertEqual(self.extract(result), [item, item, item])

    def test_json_object_string_is_supported_without_mutating_input(self):
        result = multi_country_result()
        result["plan_check_country_results"][0]["result"]["account_promotions"][2].update(
            kind="free_trial", eligible=True,
        )
        original = deepcopy(result)
        expected = [{"plan": "team", "kind": "free_trial", "eligible": True}]
        self.assertEqual(self.extract(result), expected)
        self.assertEqual(self.extract(json.dumps(result)), expected)
        self.assertEqual(result, original)

    def test_malformed_or_unsuccessful_snapshot_has_no_confirmed_offers(self):
        for value in (None, [], False, 1, "", "{broken", "[]", "null", '"{}"'):
            with self.subTest(value=value):
                self.assertEqual(self.extract(value), [])
        for ok in (None, False, 0, 1, "true"):
            with self.subTest(ok=ok):
                result = {"ok": ok, "account_promotions": [
                    {"plan": "team", "kind": "free_trial", "eligible": True},
                ]}
                self.assertEqual(self.extract(result), [])


if __name__ == "__main__":
    unittest.main()
