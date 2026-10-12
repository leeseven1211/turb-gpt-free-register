# -*- coding: utf-8 -*-
"""Go/Plus 优惠成功快照的持久化与兼容更新边界。"""
import json

from core import db, record_store as rs
from tests.support_pg import PostgresTestCase


class AccountPromotionStorageTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "promotions@example.test", "current_plan_type": "free",
        })
        self.promotions = [{
            "plan": "go", "kind": "free_trial", "eligible": True,
            "campaign_id": "go-free-1-month", "title": "Go 免费试用",
            "summary": "免费1个月", "discount_percentage": 100,
            "duration_num_periods": 1, "duration_period": "month",
            "promotion_type": "free_trial", "promotion_type_label": "免费试用",
        }, {
            "plan": "plus", "kind": "discount", "eligible": True,
            "campaign_id": "plus-50-off-2-months", "title": "Plus 折扣",
            "summary": "50%折扣2个月", "discount_percentage": 50,
            "duration_num_periods": 2, "duration_period": "month",
            "promotion_type": "discount", "promotion_type_label": "折扣",
        }]
        self.snapshot = {
            "version": 1,
            "source": "accounts_check",
            "campaign_keys": ["go", "plus"],
            "campaigns": [
                {"plan": "go", "campaign_id": "go-free-1-month", "discount_percentage": 100},
                {"plan": "plus", "campaign_id": "plus-50-off-2-months", "discount_percentage": 50},
            ],
        }

    def _save_success(self):
        result = {
            "ok": True,
            "checked_at": "2026-10-12T08:00:00+00:00",
            "current_plan_type": "free",
            "account_promotions": self.promotions,
            "promotion_query_snapshot": self.snapshot,
        }
        self.assertTrue(db.update_account_plan_check(acc_id=self.account_id, result=result))
        return result

    def test_success_saves_both_plans_in_data_and_plan_snapshot(self):
        result = self._save_success()
        row = db.get_account(self.account_id)
        self.assertEqual(row["account_promotions"], self.promotions)
        self.assertEqual(row["promotion_query_snapshot"], self.snapshot)
        self.assertEqual(json.loads(row["plan_last_success_result_json"]), result)
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT data FROM {rs._qualified(rs.ACCOUNTS)} WHERE id=%s",
                (self.account_id,),
            )
            stored = cur.fetchone()["data"]
        self.assertEqual(stored["account_promotions"], self.promotions)
        self.assertEqual(stored["promotion_query_snapshot"], self.snapshot)

    def test_failed_query_keeps_successful_promotions_and_snapshot(self):
        successful = self._save_success()
        self.assertTrue(db.update_account_plan_check(acc_id=self.account_id, result={
            "ok": False, "error": "HTTP 503", "http_status": 503,
            "account_promotions": [],
            "promotion_query_snapshot": {
                "version": 1, "source": "accounts_check", "campaign_keys": [], "campaigns": [],
            },
        }))
        row = db.get_account(self.account_id)
        self.assertEqual(row["plan_check_status"], "failed")
        self.assertEqual(row["plan_check_error"], "HTTP 503")
        self.assertEqual(row["account_promotions"], self.promotions)
        self.assertEqual(row["promotion_query_snapshot"], self.snapshot)
        self.assertEqual(json.loads(row["plan_last_success_result_json"]), successful)

    def test_legacy_success_does_not_clear_new_promotion_fields(self):
        self._save_success()
        self.assertTrue(db.update_account_plan_check(acc_id=self.account_id, result={
            "ok": True, "current_plan_type": "free", "plus_trial_eligible": False,
        }))
        row = db.get_account(self.account_id)
        self.assertEqual(row["account_promotions"], self.promotions)
        self.assertEqual(row["promotion_query_snapshot"], self.snapshot)

    def test_successful_empty_result_clears_previous_promotions(self):
        self._save_success()
        empty_snapshot = {
            "version": 1, "source": "accounts_check", "campaign_keys": [], "campaigns": [],
        }
        self.assertTrue(db.update_account_plan_check(acc_id=self.account_id, result={
            "ok": True, "current_plan_type": "free",
            "account_promotions": [], "promotion_query_snapshot": empty_snapshot,
        }))
        row = db.get_account(self.account_id)
        self.assertEqual(row["account_promotions"], [])
        self.assertEqual(row["promotion_query_snapshot"], empty_snapshot)
