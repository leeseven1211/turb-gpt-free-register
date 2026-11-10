"""套餐变化依据固定的同国家成功证据，统计与轮次归属保持一致。"""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
import uuid

from core.bulk_operations import adapters, results
from core.storage import records
from core.storage.operations import bulk, store
from tests.support_pg import PostgresTestCase


def history(kind="none"):
    return {
        "product": "plus", "status": "success", "ok": True, "partial": False,
        "countries": ["JP", "US"], "checked_at": "2026-10-15T10:00:00+00:00",
        "frozen_at": "2026-11-10T10:00:00+00:00", "plus_offer_kind": kind,
        "country_results": [
            {"country": country, "status": "success", "ok": True,
             "checked_at": "2026-10-15T10:00:00+00:00"}
            for country in ("JP", "US")
        ],
        "promotions": [],
    }


def summary(kind="free_trial", countries=None):
    return {"ok": True, "plan_check_countries": countries or ["US", "JP"],
            "country_total_count": 2, "country_success_count": 2,
            "plus_promo_kind": kind, "current_plan_type": "free"}


class PlanComparisonTests(TestCase):
    def test_same_country_set_compares_confirmed_offer_kind(self):
        for before, after, expected in (
            ("none", "free_trial", "new_offer"), ("free_trial", "none", "offer_removed"),
            ("free_trial", "free_trial", "unchanged"), ("free_trial", "discount", "changed"),
        ):
            with self.subTest(before=before, after=after):
                value = results.project_one({"baseline": {"plan_check": history(before)},
                    "run": {"status": "success", "result_summary": summary(after)}}, operation_key="plan_check")
                self.assertEqual(value["result"]["comparison"], expected)
                self.assertEqual(value["contribution"]["dimensions"][f"account.comparison.{expected}"], 1)

    def test_missing_failed_partial_stale_expired_or_different_country_is_not_comparable(self):
        invalid = [None, {}, {**history(), "status": "failed"}, {**history(), "ok": False},
                   {**history(), "partial": True}, {**history(), "stale": True},
                   {**history(), "checked_at": "invalid"}, {**history(), "country_results": []},
                   {**history(), "promotions": [{"plan": "plus", "stale": True}]},
                   {**history(), "promotions": [{"plan": "plus", "expired": True}]},
                   {**history(), "promotions": [{"plan": "plus", "expires_at": "2026-11-01T00:00:00Z"}]}]
        bad_country = deepcopy(history())
        bad_country["country_results"][0]["status"] = "failed"
        invalid.append(bad_country)
        for basis in invalid:
            with self.subTest(basis=basis):
                value = results.project_one({"baseline": {"plan_check": basis},
                    "run": {"status": "success", "result_summary": summary()}}, operation_key="plan_check")
                self.assertEqual(value["result"]["comparison"], "not_comparable")
        for countries in (["JP", "GB"], []):
            value = results.project_one({"baseline": {"plan_check": history()},
                "run": {"status": "success", "result_summary": {**summary(), "plan_check_countries": countries}}},
                operation_key="plan_check")
            self.assertEqual(value["result"]["comparison"], "not_comparable")

    def test_partial_current_result_does_not_claim_new_offer(self):
        value = results.project_one({"baseline": {"plan_check": history()}, "run": {
            "status": "partial_success", "result_summary": {**summary(), "country_success_count": 1,
                                                                 "plan_check_partial": True}}}, operation_key="plan_check")
        self.assertEqual(value["result"]["comparison"], "not_comparable")


class PlanComparisonStorageTests(PostgresTestCase):
    def setUp(self):
        bulk.reset_ready()
        bulk.init()
        self.settings = patch("core.bulk_operations.catalog.capture_settings",
                              return_value={"config_revision": "comparison-test", "effective_settings": {}})
        self.settings.start()
        self.addCleanup(self.settings.stop)

    def test_frozen_success_basis_and_late_round_metrics_remain_independent(self):
        evidence = history()
        ids = self.seed(records.ACCOUNTS, [{
            "email": "comparison@example.test", "created_at": "2026-10-15T10:00:00+00:00",
            "updated_at": "2026-10-15T10:00:00+00:00", "access_token": "isolated-test-value",
            "plan_check_status": "success", "plan_check_ok": True, "plus_promo_kind": "none",
            "current_plan_type": "free", "plan_last_success_at": evidence["checked_at"],
            "plan_check_countries": evidence["countries"], "plan_check_partial": False,
            "plan_check_country_results": [
                {"country": row["country"], "status": row["status"], "checked_at": row["checked_at"],
                 "result": {"ok": row["ok"]}} for row in evidence["country_results"]],
        }])
        selection = bulk.create_selection(request_key=uuid.uuid4().hex, source={"kind": "ids", "ids": ids},
            operation_key="plan_check", config_revision="comparison-test")
        frozen = bulk.freeze_selection(selection["id"])
        target = bulk.get_selection(frozen["id"])["targets"][0]
        self.assertEqual(target["baseline"]["plan_check"]["countries"], ["JP", "US"])
        self.assertNotIn("access_token", target["baseline"]["plan_check"])
        batch = bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=frozen["id"], selection_revision=1,
            operation_key="plan_check", parameters={}, config_revision="comparison-test")
        bulk.process_batch(batch["id"], adapters.submit_chunk)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {store._table('operation_runs')} ORDER BY id")
            old_run_id = cur.fetchone()["id"]
        store.finish_run(old_run_id, status="success", result_summary=summary())
        bulk.project_pending()
        self.assertEqual(bulk.get_batch(batch["id"])["metrics"]["account.comparison.new_offer"], 1)
        records.patch_row(records.ACCOUNTS, ids[0], changes={"plan_check_status": "failed", "plan_check_ok": False,
            "plus_promo_kind": "discount", "plan_check_countries": ["GB"]})
        retry = bulk.create_round(batch["id"], request_key=uuid.uuid4().hex, source={"view": "current"},
            selection={"kind": "targets", "target_ids": [target["id"]]})
        bulk.freeze_round(retry["id"])
        self.assertEqual(bulk.get_batch(batch["id"])["metrics"]["account.comparison.new_offer"], 0)
        bulk.process_batch(batch["id"], adapters.submit_chunk)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {store._table('operation_runs')} ORDER BY id DESC LIMIT 1")
            new_run_id = cur.fetchone()["id"]
        store.finish_run(new_run_id, status="success", result_summary=summary("none"))
        bulk.project_pending()
        self.assertEqual(bulk.get_batch(batch["id"])["metrics"]["account.comparison.unchanged"], 1)
        store.finish_run(old_run_id, status="success", result_summary=summary("discount"))
        bulk.project_pending()
        current = bulk.get_batch(batch["id"])["metrics"]
        self.assertEqual(current["account.comparison.unchanged"], 1)
        self.assertEqual(current.get("account.comparison.new_offer", 0), 0)
        original = bulk.get_round(batch["id"], batch["round_id"])
        self.assertEqual(original["metrics"]["account.comparison.new_offer"], 1)
        self.assertEqual(bulk.get_selection(frozen["id"])["targets"][0]["baseline"], target["baseline"])
