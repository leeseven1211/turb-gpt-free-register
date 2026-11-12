"""统计仅聚合最新任务结果，且与北京时间日期和筛选条件一致。"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch
from zoneinfo import ZoneInfo

from flask import Flask

from core import account_task_store
from core.operations.errors import classify_task_error
from core.storage.extract_link import analytics, jobs
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase
from webui import runtime
from webui.routes import extract_workbench


class ExtractAnalyticsQueryTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._previous_operation_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        cls._schema_patch = patch.object(account_task_store, "_SCHEMA", cls.schema)
        cls._ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        cls._schema_patch.start()
        cls._ready_patch.start()
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        try:
            operation.reset_ready()
            if cls._previous_operation_schema is None:
                os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
            else:
                os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._previous_operation_schema
        finally:
            cls._ready_patch.stop()
            cls._schema_patch.stop()
            super().tearDownClass()

    def setUp(self):
        operation.init()
        self.now = datetime(2026, 11, 12, 12, tzinfo=ZoneInfo("Asia/Shanghai"))

    def task(self, *, created="2026-11-12T00:00:00+08:00", provider="anguang", mode="auto_payment",
             status="success", extraction="succeeded", payment="succeeded", plus="confirmed",
             error_code="", error_message="", deleted=False):
        task = operation.create_runtime_task(
            task_type="extract_link", account_id=None, email="fixture@example.test", trigger="test",
            data={"provider_id": provider, "mode": mode, "deleted_by_user": deleted},
        )
        summary = {"cause_code": error_code} if error_code else {}
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status=%s, created_at=%s WHERE id=%s",
                        (status, created, task["id"]))
            cur.execute(f"""UPDATE {operation._table('operation_runs')}
                SET status=%s, result_summary=%s::jsonb, error_code=%s, error_message=%s,
                    started_at=%s::timestamptz, completed_at=%s::timestamptz + INTERVAL '120 seconds'
                WHERE id=%s""",
                (status, json.dumps(summary), error_code, error_message, created, created, task["run"]["id"]))
        jobs.save_provider_job(task["run"]["id"], provider, "fixture-job", {
            "extraction_state": extraction, "payment_state": payment, "plus_status": plus,
        }, {"secret": "credential-must-not-leak"})
        return task

    def query(self, **kwargs):
        return analytics.workbench_analytics(now=self.now, **kwargs)

    def test_stage_rates_and_distinct_plus_confirmation(self):
        self.task()
        self.task(plus="pending")
        self.task(status="failed", extraction="failed", payment="not_started", plus="not_applicable",
                  error_code="extract_provider_dns_error")
        self.task(status="failed", payment="failed", plus="not_applicable")
        self.task(status="running", extraction="running", payment="not_started", plus="pending")
        result = self.query()
        totals = result["totals"]
        self.assertEqual((5, 3, 2, 1, 2), tuple(totals[key] for key in (
            "total", "extracted", "paid", "plus_confirmed", "failed")))
        self.assertEqual((1, 1), (totals["extraction_failed"], totals["payment_failed"]))
        self.assertEqual(0.75, totals["extraction_rate"])
        self.assertEqual(0.6667, totals["payment_rate"])
        self.assertEqual(120, totals["avg_seconds"])
        self.assertEqual(2, sum(item["count"] for item in result["failures"]))
        self.assertIn("extract_provider_dns_error", [item["code"] for item in result["failures"]])
        self.assertNotIn("credential-must-not-leak", json.dumps(result))

    def test_beijing_boundaries_zero_days_and_current_backlog(self):
        self.task(created="2026-11-05T15:59:59Z", status="running", extraction="running", payment="not_started")
        self.task(created="2026-11-05T16:00:00Z")
        self.task(created="2026-11-12T15:59:59Z")
        self.task(created="2026-11-12T16:00:00Z")
        result = self.query()
        self.assertEqual(("2026-11-06", "2026-11-12"), (result["date_from"], result["date_to"]))
        self.assertEqual(2, result["totals"]["total"])
        self.assertEqual(7, len(result["daily"]))
        self.assertEqual([1, 0, 0, 0, 0, 0, 1], [day["total"] for day in result["daily"]])
        self.assertEqual(4, result["current"]["all"])
        self.assertEqual(1, result["current"]["processing"])

    def test_provider_filter_and_deleted_tasks(self):
        self.task(provider="anguang")
        self.task(provider="legacy", mode="manual_payment", payment="not_started", plus="not_applicable")
        self.task(provider="anguang", deleted=True)
        result = self.query(provider_id="anguang")
        self.assertEqual(1, result["totals"]["total"])
        self.assertEqual(["anguang"], [item["provider_id"] for item in result["providers"]])
        self.assertEqual(1, result["current"]["all"])

    def test_empty_result_has_null_rates_and_all_dates(self):
        result = self.query(days=30)
        self.assertEqual(0, result["totals"]["total"])
        self.assertIsNone(result["totals"]["extraction_rate"])
        self.assertIsNone(result["totals"]["payment_rate"])
        self.assertIsNone(result["totals"]["avg_seconds"])
        self.assertEqual(30, len(result["daily"]))
        self.assertEqual([], result["providers"])

    def test_historical_failed_runs_do_not_duplicate_latest_success(self):
        task = self.task(status="failed", extraction="failed", payment="not_started", plus="not_applicable",
                         error_code="extract_provider_dns_error")
        with operation._connect() as conn, conn.cursor() as cur:
            latest = operation._insert_runtime_run(
                cur, task_id=task["id"], run_no=2, source_system="native_operations", account_id=None,
                batch_id=None, resource_family="extract_link", data={"provider_id": "anguang"},
            )
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET last_run_id=%s, status='success' WHERE id=%s",
                        (latest["id"], task["id"]))
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET status='success' WHERE id=%s", (latest["id"],))
        jobs.save_provider_job(latest["id"], "anguang", "latest-fixture", {
            "extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "confirmed",
        }, {})
        result = self.query()
        self.assertEqual((1, 1, 0), tuple(result["totals"][key] for key in ("total", "extracted", "failed")))
        self.assertEqual([], result["failures"])

    def test_unrecognized_codes_and_messages_are_fixed_diagnostic_categories(self):
        self.task(status="failed", extraction="failed", payment="not_started", plus="not_applicable",
                  error_code="private-credential-marker", error_message="private-message-marker")
        result = self.query()
        self.assertEqual([{"code": "diagnostics.extraction_missing", "label": "提链失败原因未记录", "count": 1}], result["failures"])
        self.assertNotIn("private-", json.dumps(result))

    def test_generic_provider_code_keeps_specific_failure_distribution(self):
        cases = (
            ("今日应付金额不是 0", "extract_nonzero_amount"),
            ("OpenAI Checkout HTTP 400: billing country must match request country", "extract_country_mismatch"),
            ("UPI 支付确认被支付提供商拒绝", "extract_upi_rejected"),
            ("优惠未生效", "extract_promotion_not_applied"),
            ("上游结账风控拦截", "extract_checkout_risk_blocked"),
            ("支付授权或审批被阻止", "extract_payment_approval_blocked"),
            ("支付确认被拦截", "extract_payment_blocked"),
        )
        for reason, code in cases:
            message = "平台提链失败：" + reason
            info = classify_task_error(message, task_type="extract_link", error_code="extract_provider_failed",
                                       result_summary={"cause_code": "extract_provider_failed"}, task_status="failed")
            self.assertEqual(code, info["code"])
            self.task(status="failed", extraction="failed", payment="not_started", plus="not_applicable",
                      error_code="extract_provider_failed", error_message=message + " private-message-marker")
        failures = {item["code"]: item for item in self.query()["failures"]}
        self.assertEqual({code for _, code in cases}, set(failures))
        self.assertTrue(all(item["count"] == 1 for item in failures.values()))
        self.assertNotIn("private-message-marker", json.dumps(failures))

    def test_provider_raw_evidence_does_not_override_explicit_specific_code(self):
        self.task(status="failed", extraction="failed", payment="not_started", plus="not_applicable",
                  error_code="extract_provider_dns_error", error_message="平台提链失败：今日应付金额不是 0")
        self.task(status="failed", extraction="failed", payment="not_started", plus="not_applicable",
                  error_message="平台提链失败：今日应付金额不是0")
        failures = {item["code"]: item["count"] for item in self.query()["failures"]}
        self.assertEqual({"extract_provider_dns_error": 1, "extract_nonzero_amount": 1}, failures)


class ExtractAnalyticsRouteTests(TestCase):
    def setUp(self):
        app = Flask("extract-analytics-test")
        app.register_blueprint(extract_workbench.create_extract_workbench_blueprint(
            runtime.WebUIContext(app, logging.getLogger("extract-analytics-test"))))
        self.client = app.test_client()

    def test_validated_arguments_and_no_store(self):
        with patch.object(extract_workbench, "workbench_analytics", return_value={"days": 30, "totals": {}}) as query:
            response = self.client.get("/api/extract-workbench/analytics?days=30&provider_id=anguang")
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["Cache-Control"])
        query.assert_called_once_with(days=30, provider_id="anguang")

    def test_invalid_range_or_provider_never_reaches_storage(self):
        with patch.object(extract_workbench, "workbench_analytics") as query:
            for query_string in ("days=1", "days=07", "days=-1", "provider_id=unsafe%20provider"):
                self.assertEqual(400, self.client.get("/api/extract-workbench/analytics?" + query_string).status_code)
        query.assert_not_called()

    def test_service_errors_do_not_expose_internal_context(self):
        with patch.object(extract_workbench, "workbench_analytics", side_effect=RuntimeError("private-marker")):
            response = self.client.get("/api/extract-workbench/analytics")
        self.assertEqual(503, response.status_code)
        self.assertNotIn("private-marker", response.get_data(as_text=True))
