"""任务中心应用查询和 HTTP 契约回归；不运行任何业务 worker。"""
from __future__ import annotations

from copy import deepcopy
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

from flask import Flask

from core import operation_task_store
from core.operations import query_service, run_log
from core.operations.contracts import OperationQuery
from core.storage.operations import legacy_task_store
from tests.support_pg import PostgresTestCase
from webui.routes import operations
from webui.runtime import WebUIContext


class TaskCenterOwnershipRegressionTests(unittest.TestCase):
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
            patch.object(query_service.operation_task_store, "list_tasks", return_value={
                "items": [row], "total": 1, "facets": {"status": []},
            }) as listing,
            patch.object(query_service.operation_task_store, "list_batches", return_value=[
                {"id": 3, "status": "attention_required", "data": {"internal": "omitted"}},
            ]) as batches,
            patch.object(query_service.svc, "attach_registration_resume_retry_info", side_effect=annotate),
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
            patch.object(query_service.operation_task_store, "get_task", return_value=row) as read,
            patch.object(query_service.svc, "attach_registration_resume_retry_info",
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
            patch.object(query_service.account_task_store, "list_tasks", return_value={"total": 1, "items": [row]}),
            patch.object(query_service.account_task_store, "get_task", side_effect=[row, None]),
            patch("core.accounts.token_refresh.settings", return_value={"enabled": True}),
            patch.object(query_service.codex_token_refresh_service, "settings", return_value={"enabled": False}),
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
            patch.object(query_service.operation_task_store, "list_task_events",
                         side_effect=lambda task_id, *, run_id, after_id, limit: {"next_after_id": after_id, "limit": limit}),
            patch.object(query_service.operation_task_store, "get_run_progress",
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


def client():
    app = Flask(__name__)
    app.register_blueprint(operations.create_operations_blueprint(WebUIContext(app, logging.getLogger(__name__))))
    return app.test_client()


def assert_contract(value, spec, schemas, path="响应"):
    """验证本契约使用的结构与类型；领域扩展属性保持开放。"""
    if "$ref" in spec:
        return assert_contract(value, schemas[spec["$ref"].rsplit("/", 1)[-1]], schemas, path)
    if "anyOf" in spec:
        for branch in spec["anyOf"]:
            try:
                assert_contract(value, branch, schemas, path)
                return
            except AssertionError:
                continue
        raise AssertionError(f"{path} 不符合任何允许类型：{type(value).__name__}")
    if "const" in spec:
        assert value == spec["const"], f"{path} 常量不匹配"
    types = spec.get("type", [])
    types = [types] if isinstance(types, str) else types
    matches = {"null": value is None, "string": isinstance(value, str),
               "integer": isinstance(value, int) and not isinstance(value, bool),
               "number": isinstance(value, (int, float)) and not isinstance(value, bool),
               "boolean": isinstance(value, bool), "array": isinstance(value, list), "object": isinstance(value, dict)}
    assert not types or any(matches.get(name, False) for name in types), f"{path} 应为 {types}，实际 {type(value).__name__}"
    if isinstance(value, dict):
        for key in spec.get("required", []):
            assert key in value, f"{path} 缺少 {key}"
        properties = spec.get("properties", {})
        for key, item in value.items():
            child = properties.get(key, spec.get("additionalProperties"))
            if isinstance(child, dict):
                assert_contract(item, child, schemas, f"{path}.{key}")
    if isinstance(value, list) and "items" in spec:
        for index, item in enumerate(value):
            assert_contract(item, spec["items"], schemas, f"{path}[{index}]")


class TaskCenterQueryTests(unittest.TestCase):
    def test_bulk_context_identifiers_match_public_contract(self):
        from core.bulk_operations.execution import attach_context
        from core.storage.operations import bulk_schema, store

        rows = [{"id": 41, "last_run_id": 51, "task_type": "token_refresh", "status": "success"}]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchall.return_value = [
            {"run_id": 51, "batch_id": 3, "round_id": 9, "canonical_target_id": "account:7"},
        ]
        with patch.object(store.postgres_store, "database_url", return_value="test"), \
                patch.object(store, "_schema_name", return_value="test"), \
                patch.object(bulk_schema, "_READY_KEY", "test::test"):
            attach_context(connection, rows)
        with patch.object(operation_task_store, "list_tasks", return_value={"ok": True, "items": rows, "total": 1, "page": 1, "page_size": 20}):
            response = client().get("/api/operations?include_facets=0&include_batches=0").get_json()
        self.assertEqual("3", response["items"][0]["bulk_batch_id"])
        self.assertEqual("9", response["items"][0]["bulk_round_id"])
        schemas = json.loads((Path(__file__).resolve().parents[2] / "contracts/task-center.openapi.json").read_text())["components"]["schemas"]
        assert_contract(response, schemas["OperationList"], schemas)

    def test_http_filters_keep_existing_names_defaults_and_values(self):
        args = {
            "page": "2", "page_size": "20", "type": "token_refresh", "status": "failed,success",
            "source": "native_operations", "q": " 查询 ", "batch_id": "4", "task_id": "41",
            "target": "example.test", "target_status": "account_available", "batch": "测试批次",
            "run_count": "4+", "stage": "email_otp", "created_from": "2026-11-01",
            "created_to": "2026-11-13", "result": "超时", "include_facets": "0", "include_batches": "no",
        }
        with patch.object(operation_task_store, "list_tasks", return_value={"ok": True, "items": [], "total": 0}) as listing, \
                patch.object(operation_task_store, "list_batches") as batches:
            response = client().get("/api/operations", query_string=args)
        self.assertEqual(200, response.status_code)
        expected = OperationQuery(page=2, page_size=20, task_type="token_refresh", status="failed,success",
                                  source="native_operations", q="查询", batch_id=4, task_id="41", target="example.test",
                                  target_status="account_available", batch="测试批次", run_count="4+", stage="email_otp",
                                  created_from="2026-11-01", created_to="2026-11-13", result="超时", include_facets=False,
                                  include_batches=False)
        listing.assert_called_once_with(**expected.store_arguments(), public_status=True)
        batches.assert_not_called()
        self.assertNotIn("facets", response.get_json())
        self.assertNotIn("batches", response.get_json())

    def test_registration_capability_uses_internal_state_without_mutating_source(self):
        row = {"id": 41, "task_type": "registration", "status": "failed", "internal_status": "attention_required",
               "target_status": "failed", "internal_target_status": "request_unknown", "source_system": "registration_chains",
               "result_summary": {}, "next_actions": []}
        original = deepcopy(row)
        observed = []

        def attach(rows):
            observed.append((rows[0]["status"], rows[0]["target_status"]))
            rows[0]["next_actions"] = [{"action": "registration_retry", "label": "重跑", "source_job_id": 17}]
            rows[0]["retryable"] = True

        with patch.object(operation_task_store, "list_tasks", return_value={"ok": True, "items": [row], "total": 1}), \
                patch.object(query_service.svc, "attach_registration_resume_retry_info", side_effect=attach):
            result = query_service.list_operations(OperationQuery(include_facets=False, include_batches=False))
        self.assertEqual([("attention_required", "request_unknown")], observed)
        self.assertEqual(original, row)
        self.assertEqual("failed", result["items"][0]["status"])
        self.assertEqual("attention_required", result["items"][0]["internal_status"])
        self.assertEqual("registration_retry", result["items"][0]["next_actions"][0]["action"])

    def test_metadata_does_not_change_list_revision_and_batches_are_compact(self):
        listing = {"ok": True, "items": [{"id": 1, "task_type": "live_check", "status": "success"}], "total": 1,
                   "facets": {"status": [{"value": "success", "count": 1}]}}
        with patch.object(operation_task_store, "list_tasks", return_value=listing), \
                patch.object(operation_task_store, "list_batches", return_value=[{
                    "id": 2, "title": "测试", "status": "attention_required", "data": {"request": "large"},
                }]) as batches:
            first = query_service.list_operations(OperationQuery())
            second = query_service.list_operations(OperationQuery(include_facets=False, include_batches=False))
        self.assertEqual(first["revision"], second["revision"])
        self.assertEqual({"id": 2, "title": "测试", "status": "failed"}, first["batches"][0])
        self.assertNotIn("facets", second)
        batches.assert_called_once_with(limit=50)

    def test_detail_omits_events_only_when_requested_and_classifies_historical_run(self):
        record = {"id": 41, "task_type": "token_refresh", "source_system": "account_action_tasks", "status": "success",
                  "runs": [{"id": 51, "status": "attention_required", "progress_stage": "complete",
                            "error_code": "request_unknown", "error_message": "远端结果待确认：查活失败",
                            "result_summary": {"outcome": "request_unknown", "error_category": "email", "auth_method": "email_otp"}}],
                  "parent": {"id": 40, "status": "request_unknown"}}
        original = deepcopy(record)
        with patch.object(operation_task_store, "get_task", return_value=record) as get_task:
            response = client().get("/api/operations/41?include_events=0")
            get_task.assert_called_once_with(41, include_events=False)
            get_task.reset_mock()
            client().get("/api/operations/41")
            get_task.assert_called_once_with(41, include_events=True)
        result = response.get_json()["task"]
        self.assertEqual("failed", result["runs"][0]["status"])
        self.assertEqual("MAIL-RECEIPT", result["runs"][0]["error_info"]["display_code"])
        self.assertEqual("failed", result["parent"]["status"])
        self.assertEqual(original, record)

    def test_detail_response_owns_nested_events_runs_parent_and_capability_edits(self):
        record = {"id": 41, "task_type": "registration", "status": "attention_required",
                  "result_summary": {"evidence": ["original"]},
                  "events": [{"id": 1, "detail": {"trace": ["original"]}}],
                  "runs": [{"id": 51, "status": "attention_required", "data": {"trace": ["original"]}}],
                  "parent": {"id": 40, "status": "request_unknown", "data": {"trace": ["original"]}}}
        original = deepcopy(record)

        def attach(rows):
            rows[0]["result_summary"]["evidence"].append("capability")

        with patch.object(operation_task_store, "get_task", return_value=record), \
                patch.object(query_service.svc, "attach_registration_resume_retry_info", side_effect=attach):
            result = query_service.get_operation(41)
        self.assertEqual("failed", result["status"])
        self.assertEqual("failed", result["runs"][0]["status"])
        self.assertEqual("failed", result["parent"]["status"])
        self.assertEqual(["original", "capability"], result["result_summary"]["evidence"])
        result["events"][0]["detail"]["trace"].append("response")
        result["runs"][0]["data"]["trace"].append("response")
        result["parent"]["data"]["trace"].append("response")
        self.assertEqual(original, record)

    def test_list_items_and_public_record_keep_nested_input_ownership(self):
        row = {"id": 41, "task_type": "token_refresh", "status": "attention_required",
               "data": {"trace": ["original"]}, "result_summary": {"evidence": ["original"]}}
        original = deepcopy(row)

        def attach(rows):
            rows[0]["data"]["trace"].append("capability")

        with patch.object(operation_task_store, "list_tasks", return_value={"items": [row], "total": 1}), \
                patch.object(query_service.svc, "attach_registration_resume_retry_info", side_effect=attach):
            result = query_service.list_operations(OperationQuery(include_facets=False, include_batches=False))
        self.assertEqual("failed", result["items"][0]["status"])
        result["items"][0]["result_summary"]["evidence"].append("response")
        standalone = query_service.public_operation_record(row)
        standalone["data"]["trace"].append("standalone")
        standalone["result_summary"]["evidence"].append("standalone")
        self.assertEqual(original, row)

    def test_missing_detail_and_read_errors_keep_404_shape(self):
        with patch.object(operation_task_store, "get_task", return_value=None):
            result = client().get("/api/operations/41")
        self.assertEqual(404, result.status_code)
        self.assertEqual({"ok": False, "error": "任务不存在"}, result.get_json())
        for route, method in (("progress", "get_run_progress"), ("events", "list_task_events"), ("logs", "read_task_run_log")):
            with self.subTest(route=route), patch.object(operation_task_store, method, side_effect=LookupError("执行实例不存在")):
                result = client().get(f"/api/operations/41/runs/51/{route}")
                self.assertEqual(404, result.status_code)
                self.assertEqual({"ok": False, "error": "执行实例不存在"}, result.get_json())

    def test_progress_projects_status_without_rewriting_receipt_evidence(self):
        progress = {"outcome": {"status": "attention_required"}, "main_steps": [{"state": "request_unknown"}],
                    "remote_receipt": {"status": "request_unknown"}}
        with patch.object(operation_task_store, "get_run_progress", return_value=progress) as read:
            result = client().get("/api/operations/41/runs/51/progress").get_json()["progress"]
        read.assert_called_once_with(41, 51, public_status=True)
        self.assertEqual("failed", result["outcome"]["status"])
        self.assertEqual("request_unknown", result["remote_receipt"]["status"])
        self.assertEqual("attention_required", progress["outcome"]["status"])

    def test_progress_contract_preserves_fractional_event_duration(self):
        from core.operations.progress import build_progress_snapshot

        progress = build_progress_snapshot(41, 51, "token_refresh", {"status": "running"}, [{
            "id": 1, "run_id": 51, "stage": "network", "event_type": "stage.running", "message": "阶段计时",
            "created_at": "2026-11-13T00:00:00Z", "detail": {"step_state": "running", "duration_ms": 12.75},
        }])
        with patch.object(operation_task_store, "get_run_progress", return_value=progress):
            response = client().get("/api/operations/41/runs/51/progress").get_json()
        self.assertIn(12.75, [item.get("duration_ms") for item in response["progress"]["main_steps"]])
        schemas = json.loads((Path(__file__).resolve().parents[2] / "contracts/task-center.openapi.json").read_text())["components"]["schemas"]
        assert_contract(response, schemas["ProgressResponse"], schemas)

    def test_public_progress_keeps_unknown_condition_and_retry_distinct_from_task_failure(self):
        from core.operations.progress import build_progress_snapshot

        progress = build_progress_snapshot(41, 51, "account_completion", {
            "status": "partial_success", "result_summary": {"child_tasks": [
                {"task_id": 99, "task_type": "codex_retry", "status": "attention_required"}]},
        }, [])
        original = deepcopy(progress)
        with patch.object(operation_task_store, "get_run_progress", return_value=progress):
            response = client().get("/api/operations/41/runs/51/progress").get_json()["progress"]
        browser = next(item for item in response["main_steps"] if item["id"] == "browser")
        codex = next(item for item in response["main_steps"] if item["id"] == "codex_dispatch")
        self.assertEqual("unknown", browser["execution"]["condition"]["state"])
        self.assertEqual("unknown", browser["execution"]["retry"]["state"])
        self.assertEqual("failed", codex["execution"]["waits_for"][0]["status"])
        self.assertEqual(original, progress)

    def test_event_and_log_cursors_keep_zero_distinct_from_omitted(self):
        for route, method, field, default_limit in (("events", "list_task_events", "after_id", 200), ("logs", "read_task_run_log", "cursor", 500)):
            for cursor in (None, 0, 17):
                with self.subTest(route=route, cursor=cursor), patch.object(operation_task_store, method, return_value={"items": []}) as read:
                    args = {} if cursor is None else {field: cursor, "limit": 19}
                    result = client().get(f"/api/operations/41/runs/51/{route}", query_string=args)
                    self.assertEqual(200, result.status_code)
                    expected = {field: cursor, "limit": default_limit if cursor is None else 19}
                    if route == "events":
                        read.assert_called_once_with(41, run_id=51, **expected)
                    else:
                        read.assert_called_once_with(41, 51, **expected)


class LegacyAccountTaskQueryTests(unittest.TestCase):
    def test_list_keeps_filters_defaults_complete_response_and_source_ownership(self):
        source = {"ok": True, "items": [{"id": 7, "task_type": "live_check", "status": "success",
                                         "result_summary": {"evidence": ["原始回执"]}}],
                  "total": 12, "page": 2, "page_size": 20, "extra": {"source": "legacy"}}
        original = deepcopy(source)
        refresh = {"enabled": True, "refresh_before_hours": 24}
        codex_refresh = {"enabled": False, "durable_tasks": True}
        expected = {**original, "token_refresh": refresh, "codex_token_refresh": codex_refresh}
        cases = [
            ({}, {"page": 1, "page_size": 50, "task_type": "", "status": "", "q": ""}),
            ({"page": "2", "page_size": "20", "type": " live_check ", "status": " success ", "q": " 查询 "},
             {"page": 2, "page_size": 20, "task_type": "live_check", "status": "success", "q": "查询"}),
            ({"page": "invalid", "page_size": "invalid"},
             {"page": 1, "page_size": 50, "task_type": "", "status": "", "q": ""}),
        ]
        for args, filters in cases:
            with self.subTest(args=args), \
                    patch.object(legacy_task_store, "list_tasks", return_value=source) as listing, \
                    patch("core.accounts.token_refresh.settings", return_value=refresh), \
                    patch("core.codex.token_refresh_service.settings", return_value=codex_refresh), \
                    patch.object(query_service.svc, "attach_registration_resume_retry_info") as capabilities:
                response = client().get("/api/account-tasks", query_string=args)
            self.assertEqual(200, response.status_code)
            self.assertEqual(expected, response.get_json())
            listing.assert_called_once_with(public_status=True, **filters)
            capabilities.assert_not_called()
            self.assertEqual(original, source)

        with patch.object(legacy_task_store, "list_tasks", return_value=source), \
                patch("core.accounts.token_refresh.settings", return_value=refresh), \
                patch("core.codex.token_refresh_service.settings", return_value=codex_refresh):
            result = query_service.list_legacy_account_tasks()
        result["items"][0]["result_summary"]["evidence"].append("响应副本")
        self.assertEqual(original, source)

    def test_list_and_detail_keep_legacy_classification_inputs_and_public_priority(self):
        source = {"id": 7, "task_type": "token_refresh", "status": "failed",
                  "internal_status": "attention_required", "error": "旧错误", "error_message": "当前错误",
                  "error_code": "request_unknown", "failure_stage": "network", "result_summary": {"evidence": [1]}}
        original = deepcopy(source)
        legacy_info, public_info = {"code": "legacy"}, {"code": "public"}
        expected_task = {**original, "error_info": public_info}
        for detail in (False, True):
            with self.subTest(detail=detail), \
                    patch.object(legacy_task_store, "list_tasks", return_value={"items": [source], "total": 1}), \
                    patch.object(legacy_task_store, "get_task", return_value=source) as get_task, \
                    patch("core.accounts.token_refresh.settings", return_value={}), \
                    patch("core.codex.token_refresh_service.settings", return_value={}), \
                    patch.object(query_service, "classify_task_error", side_effect=[legacy_info, public_info]) as classify:
                response = client().get("/api/account-tasks/7" if detail else "/api/account-tasks")
            expected = {"ok": True, "task": expected_task} if detail else {
                "items": [expected_task], "total": 1, "token_refresh": {}, "codex_token_refresh": {},
            }
            self.assertEqual(200, response.status_code)
            self.assertEqual(expected, response.get_json())
            self.assertEqual([
                call("旧错误", stage="complete", task_type="token_refresh", error_code="request_unknown",
                     result_summary={"evidence": [1]}, task_status="failed" if detail else "attention_required"),
                call("当前错误", stage="network", task_type="token_refresh", error_code="request_unknown",
                     result_summary={"evidence": [1]}, task_status="attention_required", cancel_reason=""),
            ], classify.call_args_list)
            if detail:
                get_task.assert_called_once_with(7)
            self.assertEqual(original, source)

    def test_detail_preserves_legacy_id_nested_evidence_and_status_projection(self):
        source = {"id": 7, "task_type": "live_check", "status": "attention_required", "error": "检查失败",
                  "result_summary": {"evidence": ["原始回执"]},
                  "events": [{"id": 9, "detail": {"trace": ["原始事件"]}}]}
        original = deepcopy(source)
        expected_task = {**original, "status": "failed", "internal_status": "attention_required"}
        with patch.object(legacy_task_store, "get_task", return_value=source) as get_task, \
                patch.object(query_service, "classify_task_error", return_value=None), \
                patch.object(query_service.svc, "attach_registration_resume_retry_info") as capabilities, \
                patch("core.accounts.token_refresh.settings") as refresh, \
                patch("core.codex.token_refresh_service.settings") as codex_refresh:
            response = client().get("/api/account-tasks/7")
            self.assertEqual(200, response.status_code)
            self.assertEqual({"ok": True, "task": expected_task}, response.get_json())
            get_task.assert_called_once_with(7)
            result = query_service.get_legacy_account_task(7)
        capabilities.assert_not_called()
        refresh.assert_not_called()
        codex_refresh.assert_not_called()
        result["result_summary"]["evidence"].append("响应副本")
        result["events"][0]["detail"]["trace"].append("响应副本")
        self.assertEqual(original, source)

    def test_empty_list_and_missing_detail_keep_envelope_and_404_message(self):
        source = {"ok": True, "items": None, "total": 0, "page": 3, "page_size": 20}
        with patch.object(legacy_task_store, "list_tasks", return_value=source), \
                patch.object(legacy_task_store, "get_task", return_value=None), \
                patch("core.accounts.token_refresh.settings", return_value={"enabled": True}), \
                patch("core.codex.token_refresh_service.settings", return_value={"enabled": False}), \
                patch.object(query_service, "classify_task_error") as classify:
            listing = client().get("/api/account-tasks?page=3&page_size=20")
            missing = client().get("/api/account-tasks/999")
        self.assertEqual(200, listing.status_code)
        self.assertEqual({**source, "items": [], "token_refresh": {"enabled": True},
                          "codex_token_refresh": {"enabled": False}}, listing.get_json())
        self.assertEqual(404, missing.status_code)
        self.assertEqual({"ok": False, "error": "任务实例不存在"}, missing.get_json())
        classify.assert_not_called()


class TaskCenterQueryStoreTests(PostgresTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.patches = [patch.object(run_log, "_LOG_ROOT", root), patch.object(run_log, "_TASK_LOG_ROOT", root / "tasks"),
                        patch.object(legacy_task_store, "_SCHEMA", self.schema)]
        for item in self.patches:
            item.start()
        legacy_task_store.init()
        operation_task_store.reset_ready()
        operation_task_store.init()
        self.http = client()

    def tearDown(self):
        run_log.clear_current_context()
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def create(self, account_id):
        return operation_task_store.create_runtime_task(task_type="token_refresh", account_id=account_id,
                                                       email=f"sample-{account_id}@example.test", trigger="test")

    def test_cross_task_run_has_no_events_and_cannot_read_progress_or_logs(self):
        first, second = self.create(1), self.create(2)
        operation_task_store.append_runtime_event(second["run"]["id"], stage="network", state="success", message="其他任务事件")
        base = f"/api/operations/{first['id']}/runs/{second['run']['id']}"
        for suffix in ("progress", "logs"):
            self.assertEqual(404, self.http.get(f"{base}/{suffix}").status_code)
        events = self.http.get(f"{base}/events").get_json()
        self.assertEqual([], events["items"])

    def test_event_and_log_pages_keep_order_without_duplicate_records(self):
        task = self.create(3)
        task_id, run_id = task["id"], task["run"]["id"]
        for state in ("running", "success", "running", "failed"):
            operation_task_store.append_runtime_event(run_id, stage="network", state=state, message=f"测试阶段 {state}")
        base = f"/api/operations/{task_id}/runs/{run_id}"
        first = self.http.get(f"{base}/events?after_id=0&limit=2").get_json()
        second = self.http.get(f"{base}/events?after_id={first['next_after_id']}&limit=2").get_json()
        ids = [row["id"] for row in first["items"] + second["items"]]
        self.assertEqual(sorted(set(ids)), ids)
        self.assertTrue(first["has_more"])
        first_log = self.http.get(f"{base}/logs?cursor=0&limit=2").get_json()
        second_log = self.http.get(f"{base}/logs?cursor={first_log['next_cursor']}&limit=2").get_json()
        self.assertGreater(second_log["next_cursor"], first_log["next_cursor"])
        first_events = {row.get("event_uuid") for row in first_log["items"]}
        self.assertTrue(first_events.isdisjoint({row.get("event_uuid") for row in second_log["items"]}))

    def test_real_payloads_match_contract_types_and_required_fields(self):
        task = self.create(4)
        schema = json.loads((Path(__file__).resolve().parents[2] / "contracts/task-center.openapi.json").read_text())["components"]["schemas"]
        base = f"/api/operations/{task['id']}/runs/{task['run']['id']}"
        cases = [('/api/operations?include_facets=0&include_batches=0', 'OperationList'),
                 (f"/api/operations/{task['id']}?include_events=0", 'OperationDetail'),
                 (f"{base}/progress", 'ProgressResponse'), (f"{base}/events", 'EventsResponse'), (f"{base}/logs", 'LogsResponse')]
        for url, name in cases:
            with self.subTest(name=name):
                response = self.http.get(url)
                self.assertEqual(200, response.status_code)
                assert_contract(response.get_json(), schema[name], schema)
