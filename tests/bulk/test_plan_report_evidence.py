"""Report facts must stay bound to this round, with missing evidence explicit."""
from copy import deepcopy
import unittest

from core.bulk_operations.plan_report_evidence import normalize_plan_report_evidence, promotion_evidence_complete, plan_report_snapshot


def response(*, go="none", plus="none", truncated=False):
    return {"ok": True, "current_plan_type": "free", "promotion_query_snapshot": {"truncated": truncated},
            "account_promotions": [{"plan": plan, "kind": kind, "eligible": kind != "none"}
                                   for plan, kind in (("go", go), ("plus", plus))]}


class PlanReportEvidenceTests(unittest.TestCase):
    def normalize(self, summary=None, *, refresh=None, state="success", run_id=10, **extra):
        run = {"id": run_id, "relation": "owned_root", "started_at": "2026-11-12T00:00:00Z",
               "result_summary": summary or {}, "data": {"plan_auto_refresh_at": refresh}, **extra}
        return normalize_plan_report_evidence([run], state=state, projected_result={})

    def test_offer_counts_require_current_successful_eligible_facts(self):
        summary = response(plus="free_trial")
        summary["account_promotions"] += [dict(summary["account_promotions"][1], country="JP"),
            {"plan": "go", "kind": "discount", "eligible": True, "stale": True},
            {"plan": "pro", "kind": "discount", "eligible": False}]
        out = self.normalize(summary)
        self.assertEqual(out["plan"], "free")
        self.assertEqual(out["offer"]["by_plan"], [{"plan": "plus", "kinds": ["free_trial"]}])
        self.assertFalse(self.normalize(summary, state="failed")["offer"]["has_offer"])
        self.assertFalse(self.normalize(summary, state="running")["offer"]["has_offer"])

    def test_multiple_offer_plans_and_discount_kinds_remain_distinct(self):
        summary = response(go="free_trial", plus="discount")
        summary["account_promotions"][1]["discount_percentage"] = 50
        summary["account_promotions"].append({"plan": "plus", "kind": "discount", "eligible": True, "discount_percentage": 20})
        out = self.normalize(summary)
        self.assertTrue(out["offer"]["has_offer"])
        self.assertEqual(out["offer"]["by_plan"], [{"plan": "go", "kinds": ["free_trial"]},
            {"plan": "plus", "kinds": ["half_price", "other_discount"]}])

    def test_no_offer_requires_complete_all_country_evidence(self):
        single = response()
        self.assertTrue(promotion_evidence_complete(single))
        self.assertTrue(self.normalize(single)["offer"]["confirmed_none"])
        multi = dict(single, plan_check_countries=["JP", "US"], country_success_count=2,
            plan_check_country_results=[{"country": c, "status": "success", "result": response()} for c in ("JP", "US")])
        self.assertTrue(promotion_evidence_complete(multi))
        self.assertFalse(self.normalize(multi)["offer"]["confirmed_none"], "legacy lead snapshot cannot certify all countries")
        multi["plan_report_evidence"] = plan_report_snapshot(multi)
        self.assertTrue(self.normalize(multi)["offer"]["confirmed_none"])
        truncated = deepcopy(multi)
        truncated["plan_check_country_results"][1]["result"]["promotion_query_snapshot"]["truncated"] = True
        self.assertFalse(promotion_evidence_complete(truncated))
        partial = dict(multi, country_success_count=1, plan_check_partial=True)
        self.assertFalse(promotion_evidence_complete(partial))
        unknown = response();unknown["account_promotions"][0]["kind"] = "unknown"
        self.assertFalse(promotion_evidence_complete(unknown))

    def test_refresh_success_stays_success_when_plan_check_later_fails(self):
        refresh = {"run_id": 10, "attempted": True, "status": "success", "ok": True, "reason": "token_local_expired"}
        at = self.normalize(state="failed", refresh=refresh)["at_refresh"]
        self.assertTrue(at["expired"]);self.assertTrue(at["attempted"]);self.assertTrue(at["succeeded"])
        self.assertFalse(at["failed"])
        refresh["reason"] = "token_http_401"
        at = self.normalize(refresh=refresh)["at_refresh"]
        self.assertFalse(at["expired"]);self.assertTrue(at["invalid"])

    def test_refresh_fenced_to_run_and_unfinished_terminal_not_counted_as_failure(self):
        refresh = {"run_id": 11, "attempted": True, "status": "success", "ok": True}
        self.assertFalse(self.normalize(refresh=refresh)["at_refresh"]["succeeded"])
        refresh.update(run_id=10, ok=False, status="running")
        at = self.normalize(state="failed", refresh=refresh)["at_refresh"]
        self.assertTrue(at["unknown"]);self.assertFalse(at["failed"]);self.assertFalse(at["pending"])
        self.assertTrue(self.normalize(state="running", refresh=refresh)["at_refresh"]["pending"])
        refresh.update(status="failed", reason="token_missing")
        at = self.normalize(state="failed", refresh=refresh)["at_refresh"]
        self.assertTrue(at["failed"]);self.assertTrue(at["missing_token"])

    def test_at_missing_history_is_unknown_and_known_disabled_issues_stay_precise(self):
        self.assertTrue(self.normalize()["at_refresh"]["unknown"])
        summary = {"plan_report_evidence": {"at_refresh_observed": True},
                   "country_failures": [{"code": "token_local_expired"}, {"code": "token_http_401"}]}
        at = self.normalize(summary, state="failed")["at_refresh"]
        self.assertTrue(at["not_needed"]);self.assertTrue(at["expired"]);self.assertTrue(at["invalid"])
        self.assertFalse(at["attempted"])

    def test_report_summary_records_flat_completeness_and_exact_local_issue(self):
        from core.accounts.plans.service import _plan_result_summary
        summary = _plan_result_summary(response())
        self.assertTrue(summary["plan_report_evidence"]["promotion_complete"])
        failed = _plan_result_summary({"ok": False, "error": "AT已过期/失效，请手动查活刷新", "http_status": None, "token_expired": True})
        self.assertEqual(failed["plan_at_issue"], "token_local_expired")
        self.assertTrue(failed["plan_report_evidence"]["at_refresh_observed"])

    def test_no_owned_execution_is_separate_from_unknown(self):
        out = normalize_plan_report_evidence([], state="pending_submit", projected_result={})
        self.assertTrue(out["at_refresh"]["not_executed"])
        self.assertFalse(out["at_refresh"]["unknown"])

    def test_compact_offer_facts_survive_large_summary_truncation(self):
        from core.accounts.plans.service import _plan_result_summary
        from core.storage.operations.store import _scrub
        result = response()
        result["account_promotions"] *= 70
        result["account_promotions"].append({"plan": "plus", "kind": "free_trial", "eligible": True})
        summary = _scrub(_plan_result_summary(result))
        out = self.normalize(summary)
        self.assertTrue(out["offer"]["has_offer"])
        self.assertFalse(out["offer"]["confirmed_none"])

    def test_new_continuation_excludes_old_promotion_result(self):
        runs = [{"id": 1, "generation": 1, "relation": "owned_root", "result_summary": response(plus="free_trial")},
                {"id": 2, "generation": 2, "relation": "owned_continuation", "result_summary": {"ok": False}}]
        result = normalize_plan_report_evidence(runs, state="failed", projected_result={"plus_offer_kind": "free_trial"})
        self.assertFalse(result["offer"]["has_offer"]);self.assertIsNone(result["plan"])
