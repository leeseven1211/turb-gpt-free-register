"""注册公开列表的历史失败筛选、统计和恢复事实保持一致。"""

from copy import deepcopy
import logging
from unittest.mock import patch

from flask import Flask

from core.storage import admin_repository as repository, records
from tests.support_pg import PostgresTestCase
from webui.route_helpers import _latest_progress_batch
from webui.routes.jobs import create_jobs_blueprint
from webui.runtime import WebUIContext


class JobPublicStatusTests(PostgresTestCase):
    def setUp(self):
        records.reset_ready()
        records.init()
        self.ids = {}
        for status in ("failed", "request_unknown", "attention_required", "manual_reconcile", "success", "pending"):
            self.ids[status] = records.insert_row(records.JOBS, {
                "job_uuid": f"public-job-{status}", "status": status, "batch_id": "public-jobs",
                "cause_code": "email_otp_failed" if status != "success" else None,
                "auth_diagnostics": {"operation": "email_otp", "failure_kind": "no_mail"},
            })

    def test_public_pagination_filter_and_facets_fold_history_without_changing_retry_inputs(self):
        seen = {}

        def retry(rows):
            seen.update({row["id"]: row["status"] for row in rows})
            return {row["id"]: {"retryable": True, "retry_action": "registration_resume",
                                "display_status": row["status"]} for row in rows}

        with patch("core.registration.service.get_retry_info_bulk", side_effect=retry):
            public = repository.list_jobs(repository.PageRequest(page_size=2, filters={"status": "failed"}),
                                          view="table", public_status=True)
        self.assertEqual(4, public["total"])
        self.assertEqual(2, len(public["items"]))
        self.assertEqual({"failed"}, {row["status"] for row in public["items"]})
        self.assertEqual({"failed"}, {row["display_status"] for row in public["items"]})
        self.assertTrue(all(row["retryable"] and row["retry_action"] == "registration_resume" for row in public["items"]))
        self.assertEqual({"attention_required", "manual_reconcile"}, set(seen.values()))
        self.assertEqual({"failed": 4, "success": 1, "pending": 1, "active": 1}, public["status_counts"])
        self.assertEqual({"failed", "success", "pending"}, {row["value"] for row in public["facets"]["status"]})
        internal = repository.list_jobs(repository.PageRequest(filters={"status": "request_unknown"}), view="table")
        self.assertEqual([self.ids["request_unknown"]], [row["id"] for row in internal["items"]])
        self.assertEqual("request_unknown", internal["items"][0]["status"])
        self.assertEqual("request_unknown", records.get_row(records.JOBS, self.ids["request_unknown"])["status"])

    def test_public_batch_and_dashboard_counts_match_the_job_rows(self):
        public = repository.list_jobs(repository.PageRequest(), progress_batch_id="public-jobs",
                                      view="batch", public_status=True)
        batch = public["progress_batches"][0]
        self.assertEqual(4, batch["status_counts"]["failed"])
        self.assertEqual(1, batch["status_counts"]["pending"])
        self.assertNotIn("request_unknown", batch["status_counts"])
        self.assertNotIn("manual_reconcile", batch["status_counts"])
        self.assertEqual({"failed", "success", "pending"}, {row["status"] for row in public["progress_rows"]})
        dashboard = repository.dashboard_aggregates(public_status=True)
        self.assertEqual({"failed": 4, "success": 1, "pending": 1}, dashboard["jobs"]["counts"])
        self.assertIn("request_unknown", repository.dashboard_aggregates()["jobs"]["counts"])

    def test_saved_partial_result_is_preserved_in_every_public_query(self):
        partial_id = records.insert_row(records.JOBS, {"job_uuid": "saved-partial", "status": "attention_required",
                                                       "requested_status": "partial_success", "batch_id": "partial-batch"})
        listing = repository.list_jobs(repository.PageRequest(filters={"status": "partial_success"}),
                                       view="table", public_status=True)
        self.assertEqual([partial_id], [row["id"] for row in listing["items"]])
        self.assertEqual("partial_success", listing["items"][0]["status"])
        batches = repository.list_jobs(repository.PageRequest(), progress_batch_id="partial-batch", view="batch",
                                       public_status=True)
        self.assertEqual("partial_success", batches["progress_rows"][0]["status"])
        batch = next(item for item in batches["progress_batches"] if item["batch_id"] == "partial-batch")
        self.assertEqual(1, batch["status_counts"]["partial_success"])
        self.assertEqual(1, repository.dashboard_aggregates(public_status=True)["jobs"]["counts"]["partial_success"])
        self.assertEqual("attention_required", records.get_row(records.JOBS, partial_id)["status"])

    def test_jobs_api_enables_public_queries_and_classifies_empty_error_messages(self):
        app = Flask("public-jobs")
        context = WebUIContext(app, logging.getLogger("public-jobs"))
        app.register_blueprint(create_jobs_blueprint(context))
        result = app.test_client().get("/api/jobs?view=table&status=failed")
        self.assertEqual(200, result.status_code)
        payload = result.get_json()
        self.assertEqual(4, payload["total"])
        self.assertEqual({"failed"}, {row["status"] for row in payload["items"]})
        for row in payload["items"]:
            self.assertEqual("MAIL-OTP-002", row["error_info"]["display_code"])
            self.assertEqual("未收到新的验证码邮件", row["error_info"]["summary"])

    def test_public_progress_history_changes_only_display_and_keeps_receipts(self):
        rows = [{"id": 1, "batch_id": "history", "status": "request_unknown", "batch_index": 1,
                 "result_summary": {"outcome": "request_unknown", "remote_intent_state": "unknown"},
                 "progress": {"outcome": {"status": "request_unknown"}, "routes": [
                     {"run_status": "attention_required", "steps": [{"display_status": "unconfirmed"}]}],
                     "remote_intent": {"state": "unknown"}}}]
        before = deepcopy(rows)
        public = _latest_progress_batch(rows, public_status=True)
        self.assertEqual({"failed": 1, "active": 0}, public["status_counts"])
        item = public["items"][0]
        self.assertEqual("failed", item["status"])
        self.assertEqual("failed", item["attempts"][0]["status"])
        self.assertEqual("failed", item["progress"]["outcome"]["status"])
        self.assertEqual("failed", item["progress"]["routes"][0]["run_status"])
        self.assertEqual("unknown", item["progress"]["remote_intent"]["state"])
        self.assertEqual(before, rows)
        self.assertEqual("request_unknown", _latest_progress_batch(rows)["items"][0]["status"])

    def test_job_log_detail_exposes_failed_without_mutating_stored_result(self):
        app = Flask("public-job-log")
        app.register_blueprint(create_jobs_blueprint(WebUIContext(app, logging.getLogger("public-job-log"))))
        job_id = self.ids["request_unknown"]
        with patch("webui.routes.jobs.svc.read_job_log", return_value="历史日志"):
            response = app.test_client().get(f"/api/jobs/{job_id}/log")
        self.assertEqual(200, response.status_code)
        job = response.get_json()["job"]
        self.assertEqual("failed", job["status"])
        self.assertEqual("MAIL-OTP-002", job["error_info"]["display_code"])
        self.assertEqual("request_unknown", records.get_row(records.JOBS, job_id)["status"])
