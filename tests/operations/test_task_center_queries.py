"""Exercise task reads through the existing Flask endpoints with synthetic records."""
from copy import deepcopy
import logging
import unittest
from unittest.mock import patch

from flask import Flask

from webui.routes import operations
from webui.runtime import WebUIContext


class TaskCenterQueryTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(operations.create_operations_blueprint(
            WebUIContext(app, logging.getLogger(__name__)),
        ))
        self.client = app.test_client()

    def test_list_capabilities_use_internal_status_and_leave_repository_row_intact(self):
        row = {
            "id": 41, "status": "failed", "internal_status": "attention_required",
            "target_status": "failed", "internal_target_status": "request_unknown",
            "result_summary": {"evidence": ["original"]},
        }
        original = deepcopy(row)

        def annotate(rows):
            self.assertEqual(("attention_required", "request_unknown"),
                             (rows[0]["status"], rows[0]["target_status"]))
            rows[0]["result_summary"]["evidence"].append("capability")
            rows[0]["next_actions"] = [{"action": "test_capability"}]

        with (
            patch.object(operations.operation_task_store, "list_tasks", return_value={
                "items": [row], "total": 1, "facets": {"status": []},
            }) as listing,
            patch.object(operations.operation_task_store, "list_batches", return_value=[
                {"id": 3, "status": "attention_required", "data": {"internal": "omitted"}},
            ]) as batches,
            patch.object(operations.svc, "attach_registration_resume_retry_info", side_effect=annotate),
        ):
            result = self.client.get("/api/operations?type=custom&q=%20test%20&batch_id=3").get_json()
            limited = self.client.get(
                "/api/operations?type=custom&q=test&batch_id=3&include_facets=false&include_batches=0"
            ).get_json()
        self.assertEqual(original, row)
        self.assertEqual("failed", result["items"][0]["status"])
        self.assertEqual([{"action": "test_capability"}], result["items"][0]["next_actions"])
        self.assertEqual(["original", "capability"], result["items"][0]["result_summary"]["evidence"])
        self.assertEqual([{"id": 3, "status": "failed"}], result["batches"])
        self.assertEqual(result["revision"], limited["revision"])
        self.assertNotIn("batches", limited)
        self.assertNotIn("facets", limited)
        self.assertEqual(("custom", "test", 3), tuple(listing.call_args.kwargs[key] for key in ("task_type", "q", "batch_id")))
        batches.assert_called_once_with(limit=50)

    def test_detail_keeps_native_debug_links_and_does_not_modify_repository_evidence(self):
        row = {
            "id": 41, "source_system": "native_operations", "task_type": "test", "status": "success",
            "runs": [{"id": 51, "status": "request_unknown"}],
            "parent": {"id": 40, "status": "request_unknown"}, "result_summary": {"evidence": []},
        }
        original = deepcopy(row)
        with (
            patch.object(operations.operation_task_store, "get_task", return_value=row) as read,
            patch.object(operations.svc, "attach_registration_resume_retry_info",
                         side_effect=lambda rows: rows[0]["result_summary"]["evidence"].append("read")),
            patch("core.operations.debug.describe", return_value={
                "available": True, "page_state_available": False, "screenshot_available": True,
            }),
        ):
            result = self.client.get("/api/operations/41?include_events=off").get_json()["task"]
        self.assertEqual(original, row)
        read.assert_called_once_with(41, include_events=False)
        self.assertEqual("failed", result["parent"]["status"])
        run = result["runs"][0]
        self.assertEqual("failed", run["status"])
        self.assertEqual("/api/operations/41/runs/51/debug/har", run["debug_artifacts"]["har_url"])
        self.assertEqual("", run["debug_artifacts"]["page_state_url"])
        self.assertEqual("/api/operations/41/runs/51/debug/screenshot", run["debug_artifacts"]["screenshot_url"])

    def test_legacy_list_and_detail_keep_settings_envelopes_and_repository_record(self):
        row = {"id": 7, "task_type": "test", "status": "interrupted", "error": "WebUI 重启导致任务中断，请重新执行"}
        original = deepcopy(row)
        with (
            patch.object(operations.account_task_store, "list_tasks", return_value={"total": 1, "items": [row]}),
            patch.object(operations.account_task_store, "get_task", side_effect=[row, None]),
            patch("core.accounts.token_refresh.settings", return_value={"enabled": True}),
            patch.object(operations.codex_token_refresh_service, "settings", return_value={"enabled": False}),
        ):
            listing = self.client.get("/api/account-tasks").get_json()
            detail = self.client.get("/api/account-tasks/7").get_json()
            missing = self.client.get("/api/account-tasks/42")
        self.assertEqual(original, row)
        self.assertEqual("SYS-002", listing["items"][0]["error_info"]["display_code"])
        self.assertEqual(listing["items"][0], detail["task"])
        self.assertTrue(listing["token_refresh"]["enabled"])
        self.assertFalse(listing["codex_token_refresh"]["enabled"])
        self.assertEqual({"ok": False, "error": "任务实例不存在"}, missing.get_json())
        self.assertEqual(404, missing.status_code)

    def test_events_distinguish_omitted_cursor_and_zero_and_progress_preserves_evidence(self):
        progress = {"outcome": {"status": "request_unknown"}, "remote_receipt": {"status": "request_unknown"}}
        with (
            patch.object(operations.operation_task_store, "list_task_events",
                         side_effect=lambda task_id, *, run_id, after_id, limit: {"next_after_id": after_id, "limit": limit}),
            patch.object(operations.operation_task_store, "get_run_progress",
                         side_effect=[progress, LookupError("执行实例不存在")]),
        ):
            base = "/api/operations/41/runs/51"
            self.assertEqual({"ok": True, "next_after_id": None, "limit": 200},
                             self.client.get(f"{base}/events").get_json())
            self.assertEqual({"ok": True, "next_after_id": 0, "limit": 8},
                             self.client.get(f"{base}/events?after_id=0&limit=8").get_json())
            result = self.client.get(f"{base}/progress").get_json()["progress"]
            missing = self.client.get(f"{base}/progress")
        self.assertEqual("failed", result["outcome"]["status"])
        self.assertEqual("request_unknown", result["remote_receipt"]["status"])
        self.assertEqual("request_unknown", progress["outcome"]["status"])
        self.assertEqual(404, missing.status_code)
        self.assertEqual({"ok": False, "error": "执行实例不存在"}, missing.get_json())
