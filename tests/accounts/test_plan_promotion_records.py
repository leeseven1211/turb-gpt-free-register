# -*- coding: utf-8 -*-
"""验证 Go / Plus 活动证据随每次查询保存，且历史任务不会被覆盖。"""
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import db
from core.accounts.plans import service as plan_check_service
from core.storage import records as record_store
from core.operations import run_log as task_run_log
from core.accounts.plans.client import parse_accounts_check
from core.operations import task_gateway
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class PlanPromotionRecordsTests(PostgresTestCase):
    def setUp(self):
        log_dir = tempfile.TemporaryDirectory()
        self.addCleanup(log_dir.cleanup)
        for name, value in (
            ("_LOG_ROOT", Path(log_dir.name)),
            ("_TASK_LOG_ROOT", Path(log_dir.name) / "tasks"),
        ):
            log_patch = patch.object(task_run_log, name, value)
            log_patch.start()
            self.addCleanup(log_patch.stop)
        task_gateway.init()
        operation.reset_ready()
        operation.init()
        plan_check_service.register_operation_handlers()
        self.account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": "promotion-records@example.test", "access_token": "synthetic-token",
            "current_plan_type": "free", "plan_check_status": "success",
        })

    def _execute(self, campaigns, *, query_result=None):
        result = parse_accounts_check({"accounts": {"default": {
            "account": {"account_id": "synthetic-account", "plan_type": "free"},
            "eligible_promo_campaigns": campaigns,
        }}})
        result["http_status"] = 200
        if query_result is not None:
            result = query_result
        self.assertTrue(db.claim_account_plan_check(acc_id=self.account_id, trigger="test_records"))
        task = operation.create_runtime_task(
            task_type="plan_check", account_id=self.account_id,
            email="promotion-records@example.test", trigger="test_records",
        )
        route = SimpleNamespace(
            proxy_url=None, public_dict=lambda: {"network_route": "direct"}, release=Mock(),
        )
        with (
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
            patch.object(plan_check_service, "_query_account_plan", return_value=result),
        ):
            outcome = task_gateway._execute_operation_handler("plan_check", int(task["id"]))
        self.assertEqual(outcome["status"], "success")
        return operation.get_run(int(task["run"]["id"]))

    def test_registration_recheck_saves_initial_go_offer_in_separate_event(self):
        first = parse_accounts_check({"accounts": {"default": {
            "account": {"plan_type": "free"},
            "eligible_promo_campaigns": {"go": {"id": "go-free", "metadata": {
                "discount": {"percentage": 100},
                "duration": {"num_periods": 1, "period": "month"},
            }}},
        }}})
        second = parse_accounts_check({"accounts": {"default": {
            "account": {"plan_type": "free"}, "eligible_promo_campaigns": {},
        }}})
        first["http_status"] = second["http_status"] = 200
        with (
            patch.object(plan_check_service, "check_account_plan", side_effect=[first, second]),
            patch.object(plan_check_service, "_registration_recheck_delay", return_value=1),
            patch.object(plan_check_service, "_wait_for_rate_slot"),
            patch.object(plan_check_service.time, "sleep"),
        ):
            result = plan_check_service._query_account_plan(
                email="promotion-records@example.test", access_token="synthetic-token",
                trigger="registration_auto", proxy=None, timezone_offset_min="-",
            )
        self.assertEqual(result["promotion_query_history"][0]["account_promotions"][0]["kind"], "free_trial")
        self.assertEqual(result["promotion_query_history"][1]["account_promotions"][0]["kind"], "none")
        run = self._execute({}, query_result=result)
        events = operation.list_task_events(int(run["task_id"]), run_id=int(run["id"]))["items"]
        records = [event["detail"] for event in events if event["event_type"] == "promotion.query.recorded"]
        self.assertEqual([record["phase"] for record in records], ["initial", "registration_recheck"])
        self.assertEqual(records[0]["campaigns"][0]["discount_percentage"], 100)
        self.assertEqual(records[0]["account_promotions"][0]["kind"], "free_trial")
        self.assertEqual(records[1]["account_promotions"][0]["kind"], "none")
        self.assertNotIn("[truncated]", str(records))

    def test_history_preserves_each_response_and_untruncated_campaign_numbers(self):
        campaigns = {
            "go": {"id": "go-1-month-free", "metadata": {
                "discount": {"percentage": 100},
                "duration": {"num_periods": 1, "period": "month"},
            }},
            "plus": {"id": "plus-50-pct-off", "metadata": {
                "discount": {"percentage": 50},
                "duration": {"num_periods": 2, "period": "month"},
            }},
        }
        first = self._execute(campaigns)
        saved = first["result_summary"]
        self.assertEqual([p["kind"] for p in saved["account_promotions"]], ["free_trial", "discount"])
        self.assertNotIn("[truncated]", str(saved["promotion_query_snapshot"]))
        self.assertIn("100", str(saved["promotion_query_snapshot"]))
        self.assertIn("50", str(saved["promotion_query_snapshot"]))
        second = self._execute({})
        self.assertTrue(all(p["kind"] == "none" for p in second["result_summary"]["account_promotions"]))
        self.assertEqual(operation.get_run(int(first["id"]))["result_summary"], saved)
        self.assertEqual(db.get_account(self.account_id)["account_promotions"], second["result_summary"]["account_promotions"])

    def test_summary_drops_unrelated_credentials_and_reports_both_plans(self):
        result = {
            "ok": True, "http_status": 200,
            "account_promotions": [{"plan": "go", "kind": "none"}],
            "promotion_query_snapshot": {"version": 1, "campaigns": []},
            "access_token": "synthetic-secret", "email": "private@example.test",
        }
        summary = plan_check_service._plan_result_summary(result)
        self.assertEqual(summary["account_promotions"], result["account_promotions"])
        self.assertEqual(summary["promotion_query_snapshot"], result["promotion_query_snapshot"])
        self.assertNotIn("access_token", summary)
        self.assertNotIn("email", summary)

    def test_failed_recheck_preserves_initial_offer_and_redacted_failure_record(self):
        first = parse_accounts_check({"accounts": {"default": {
            "account": {"plan_type": "free"},
            "eligible_promo_campaigns": {"go": {"id": "go-free", "metadata": {
                "discount": {"percentage": 100},
            }}},
        }}})
        second = {
            "ok": False, "http_status": None,
            "error": "DNS 超时 https://user:secret@proxy.test password=private private@example.test",
        }
        with (
            patch.object(plan_check_service, "check_account_plan", side_effect=[first, second]),
            patch.object(plan_check_service, "_registration_recheck_delay", return_value=1),
            patch.object(plan_check_service, "_wait_for_rate_slot"),
            patch.object(plan_check_service.time, "sleep"),
        ):
            result = plan_check_service._query_account_plan(
                email="promotion-records@example.test", access_token="synthetic-token",
                trigger="registration_auto", proxy=None, timezone_offset_min="-",
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["account_promotions"][0]["kind"], "free_trial")
        run = self._execute({}, query_result=result)
        events = operation.list_task_events(int(run["task_id"]), run_id=int(run["id"]))["items"]
        records = [event["detail"] for event in events if event["event_type"] == "promotion.query.recorded"]
        error = records[1]["error"]
        self.assertIn("DNS 超时", error)
        for private in ("user:secret", "password=private", "private@example.test"):
            self.assertNotIn(private, error)
