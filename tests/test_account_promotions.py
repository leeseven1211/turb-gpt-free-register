# -*- coding: utf-8 -*-
"""Go / Plus 活动分类与脱敏证据的纯解析回归。"""
import json
import unittest

from core.plus_promotion import (
    MAX_CAMPAIGNS_PER_PLAN,
    classify_campaign,
    classify_plus_campaign,
    normalize_percentage,
    parse_account_promotions,
    primary_plan_promotion,
    promotion_kind_from_record,
)


class AccountPromotionsTests(unittest.TestCase):
    @staticmethod
    def _campaign(percentage=100, *, campaign_id="go-free"):
        return {
            "id": campaign_id,
            "metadata": {
                "title": "One month free trial",
                "summary": "Promotion description",
                "discount": {"percentage": percentage},
                "duration": {"num_periods": 1, "period": "month"},
                "promotion_type": "free_trial",
                "promotion_type_label": "Free trial",
            },
        }

    def test_missing_campaigns_have_complete_none_entries_for_both_plans(self):
        expected_fields = {
            "plan", "kind", "eligible", "campaign_id", "title", "summary",
            "discount_percentage", "duration_num_periods", "duration_period",
            "promotion_type", "promotion_type_label",
        }
        for campaigns in (None, {}, {"go": []}, {"go": None, "plus": {}}):
            with self.subTest(campaigns=campaigns):
                promotions, snapshot = parse_account_promotions(campaigns, is_free=True)
                self.assertEqual([entry["plan"] for entry in promotions], ["go", "plus"])
                self.assertEqual([entry["kind"] for entry in promotions], ["none", "none"])
                self.assertTrue(all(set(entry) == expected_fields for entry in promotions))
                self.assertFalse(any(entry["eligible"] for entry in promotions))
                self.assertEqual(snapshot["version"], 1)

    def test_percentage_wins_over_free_words_and_zero_is_not_free(self):
        for value, expected in ((100, "free_trial"), (50, "discount"), (99.999, "discount"), (0.00001, "discount"), (0, "none"), ("50", "discount")):
            with self.subTest(value=value):
                campaign = self._campaign(value)
                self.assertEqual(classify_campaign(campaign), expected)
                self.assertEqual(classify_plus_campaign(campaign), expected)

    def test_invalid_percentage_cannot_fall_back_to_free_words(self):
        for value in (float("nan"), float("inf"), float("-inf"), "NaN", "Infinity", -1, 101, True, None, [], {}, "unknown"):
            with self.subTest(value=value):
                self.assertIsNone(normalize_percentage(value))
                self.assertEqual(classify_campaign(self._campaign(value)), "unknown")
                self.assertEqual(classify_plus_campaign(self._campaign(value)), "unknown")
                promotions, snapshot = parse_account_promotions({"go": self._campaign(value)}, is_free=True)
                self.assertFalse(promotions[0]["eligible"])
                json.dumps(snapshot, allow_nan=False)

    def test_legacy_invalid_percentage_cannot_enable_plus_trial(self):
        for value in (float("nan"), "Infinity", True, 101):
            with self.subTest(value=value):
                self.assertEqual(promotion_kind_from_record({"plus_trial_campaign_id": "plus-free-trial", "plus_trial_discount_percentage": value}), "unknown")

    def test_partial_metadata_can_still_classify_explicit_free_activity(self):
        promotions, _ = parse_account_promotions({"go": {"id": "go-one-month-free"}}, is_free=True)
        self.assertEqual(promotions[0]["kind"], "free_trial")
        self.assertIsNone(promotions[0]["duration_num_periods"])
        self.assertIsNone(promotions[0]["title"])

    def test_go_does_not_inherit_ambiguous_plus_trial_identifier(self):
        campaign = {"id": "go-trial"}
        self.assertNotEqual(classify_campaign(campaign), "free_trial")
        self.assertEqual(classify_plus_campaign({"id": "plus-trial"}), "free_trial")

    def test_unsupported_shapes_are_unknown_without_free_guess(self):
        campaigns = (
            "go-free", [self._campaign()],
            {"go": "go-free"},
            {"go": {"campaigns": [self._campaign()]}},
            {"go": {"id": "go-free", "metadata": "unsupported"}},
            {"go": {"id": "go-free", "metadata": {"discount": []}}},
            {"go": {"id": "go-free", "metadata": {"duration": []}}},
            {"go": {"id": 123, "metadata": {"title": "free trial"}}},
        )
        for value in campaigns:
            with self.subTest(value=value):
                promotions, snapshot = parse_account_promotions(value, is_free=True)
                self.assertEqual(promotions[0]["kind"], "unknown")
                self.assertFalse(promotions[0]["eligible"])
                self.assertTrue(snapshot["campaign_shapes"])

    def test_finite_activity_arrays_preserve_each_supported_campaign(self):
        campaigns = {"go": [self._campaign(), self._campaign(50), "unsupported"]}
        promotions, snapshot = parse_account_promotions(campaigns, is_free=True)
        self.assertEqual([entry["kind"] for entry in promotions], ["free_trial", "discount", "unknown", "none"])
        self.assertEqual([entry["index"] for entry in snapshot["campaigns"]], [0, 1])
        self.assertEqual(snapshot["campaign_shapes"][0], {"plan": "go", "type": "array", "length": 3})

    def test_oversized_arrays_and_text_evidence_are_bounded(self):
        campaign = self._campaign()
        campaign["metadata"]["summary"] = "文" * 1000
        promotions, snapshot = parse_account_promotions({"go": [campaign] * 100}, is_free=True)
        self.assertEqual(len(promotions), MAX_CAMPAIGNS_PER_PLAN + 1)
        self.assertEqual(len(snapshot["campaigns"]), MAX_CAMPAIGNS_PER_PLAN)
        self.assertLessEqual(len(snapshot["campaigns"][0]["summary"]), 512)
        self.assertTrue(snapshot["truncated"])

    def test_flat_evidence_preserves_scalar_types_and_discards_private_fields(self):
        campaign = self._campaign("100")
        campaign["metadata"]["duration"]["num_periods"] = "1"
        campaign["account_id"] = "secret-account-id"
        campaign["email"] = "private@example.com"
        campaign["token"] = "secret-access-token"
        campaign["metadata"]["password"] = "secret-password"
        campaign["metadata"]["discount"]["access_token"] = "secret-nested-token"
        promotions, snapshot = parse_account_promotions({"go": campaign}, is_free=True)
        evidence = snapshot["campaigns"][0]
        self.assertEqual(evidence["discount_percentage"], "100")
        self.assertEqual(evidence["duration_num_periods"], "1")
        self.assertEqual(promotions[0]["discount_percentage"], 100)
        self.assertTrue(all(not isinstance(value, (dict, list)) for value in evidence.values()))
        serialized = json.dumps(snapshot)
        for private_value in ("secret-account-id", "private@example.com", "secret-access-token", "secret-password", "secret-nested-token"):
            self.assertNotIn(private_value, serialized)
        self.assertIn("account_id", snapshot["campaign_shapes"][0]["fields"])
        self.assertIn("password", snapshot["campaign_shapes"][0]["metadata_fields"])

    def test_duration_rejects_boolean_and_invalid_counts_without_hiding_free_activity(self):
        for value in (True, False, 0, -1, float("nan"), float("inf"), "NaN", "Infinity", "bad", [], {}):
            with self.subTest(value=value):
                campaign = self._campaign()
                campaign["metadata"]["duration"]["num_periods"] = value
                promotions, snapshot = parse_account_promotions({"go": campaign}, is_free=True)
                self.assertEqual(promotions[0]["kind"], "free_trial")
                self.assertIsNone(promotions[0]["duration_num_periods"])
                if isinstance(value, (bool, int, str)):
                    self.assertEqual(snapshot["campaigns"][0]["duration_num_periods"], value)
                json.dumps(snapshot, allow_nan=False)

    def test_positive_numeric_duration_and_string_period_are_normalized(self):
        for value, expected in ((1, 1), ("2", 2), (1.5, 1.5)):
            with self.subTest(value=value):
                campaign = self._campaign()
                campaign["metadata"]["duration"] = {"num_periods": value, "period": " month "}
                promotions, snapshot = parse_account_promotions({"go": campaign}, is_free=True)
                self.assertEqual(promotions[0]["duration_num_periods"], expected)
                self.assertEqual(promotions[0]["duration_period"], "month")
                self.assertEqual(snapshot["campaigns"][0]["duration_num_periods"], value)
                self.assertEqual(snapshot["campaigns"][0]["duration_period"], " month ")

    def test_duration_period_rejects_nonstring_values(self):
        for value in (True, False, 1, float("inf"), [], {}, "", "   "):
            with self.subTest(value=value):
                campaign = self._campaign()
                campaign["metadata"]["duration"]["period"] = value
                promotions, _ = parse_account_promotions({"go": campaign}, is_free=True)
                self.assertEqual(promotions[0]["kind"], "free_trial")
                self.assertIsNone(promotions[0]["duration_period"])

    def test_huge_integer_evidence_does_not_overflow_parser(self):
        campaign = self._campaign()
        campaign["metadata"]["duration"]["num_periods"] = 10 ** 1000
        promotions, snapshot = parse_account_promotions({"go": campaign}, is_free=True)
        self.assertEqual(promotions[0]["kind"], "free_trial")
        self.assertIsNone(promotions[0]["duration_num_periods"])
        self.assertIsNone(snapshot["campaigns"][0]["duration_num_periods"])

    def test_sensitive_values_in_allowed_text_fields_are_redacted(self):
        campaign = self._campaign()
        campaign["metadata"]["summary"] = "private@example.com Bearer demo-token token=secret-token https://demo:password@example.com/path"
        promotions, snapshot = parse_account_promotions({"go": campaign}, is_free=True)
        for value in (promotions[0]["summary"], snapshot["campaigns"][0]["summary"]):
            self.assertNotIn("private@example.com", value)
            self.assertNotIn("demo-token", value)
            self.assertNotIn("secret-token", value)
            self.assertNotIn("demo:password", value)

    def test_unknown_campaign_keys_keep_only_safe_field_evidence(self):
        campaigns = {"unrecognized": {"custom": {"token": "secret-value"}}, "private@example.com": {"id": "private"}}
        promotions, snapshot = parse_account_promotions(campaigns, is_free=True)
        self.assertEqual([item["kind"] for item in promotions], ["none", "none"])
        self.assertEqual(snapshot["campaign_keys"], ["unrecognized"])
        self.assertEqual(snapshot["campaigns"], [{"plan": "unrecognized"}])
        self.assertNotIn("secret-value", json.dumps(snapshot))
        self.assertNotIn("private@example.com", json.dumps(snapshot))

    def test_nonfree_campaigns_leave_evidence_but_do_not_enable_eligibility(self):
        promotions, snapshot = parse_account_promotions({"go": self._campaign(), "plus": self._campaign()}, is_free=False)
        self.assertEqual([item["kind"] for item in promotions], ["none", "none"])
        self.assertEqual(len(snapshot["campaigns"]), 2)
        self.assertFalse(any(item["eligible"] for item in promotions))

    def test_legacy_plus_primary_never_uses_go_activity(self):
        promotions, _ = parse_account_promotions({"go": self._campaign(), "plus": ["unsupported", self._campaign(50, campaign_id="plus-half-price")]}, is_free=True)
        primary = primary_plan_promotion(promotions, "plus")
        self.assertEqual(primary["kind"], "discount")
        self.assertEqual(primary["campaign_id"], "plus-half-price")


if __name__ == "__main__":
    unittest.main()
