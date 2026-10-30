# -*- coding: utf-8 -*-
"""统一操作路由的来源/任务类型边界回归。"""
from __future__ import annotations

import logging
import unittest
from unittest.mock import Mock, patch

from flask import Flask

from core.operations import task_gateway
from core.storage.operations import store as operation
from webui import runtime
from webui.routes import operations


class OperationRouteMigrationPhase2Tests(unittest.TestCase):
    def _client(self):
        app = Flask("operation-route-migration")
        context = runtime.WebUIContext(app, logging.getLogger("operation-route-migration"))
        app.register_blueprint(operations.create_operations_blueprint(context))
        return app.test_client()

    @staticmethod
    def _task(**overrides):
        task = {
            "id": 41,
            "task_type": "codex_retry",
            "source_system": "native_operations",
            "status": "failed",
            "result_summary": {},
            "next_actions": [{"action": "retry", "label": "重新执行"}],
            "runs": [],
        }
        task.update(overrides)
        return task

    def test_native_codex_retry_keeps_codex_service_contract(self):
        client = self._client()
        queued = {
            "accepted": True,
            "busy": False,
            "reused": False,
            "task_id": 41,
            "run_id": 51,
            "status": "queued",
        }
        with (
            patch.object(operations.operation_task_store, "get_task", return_value=self._task()),
            patch.object(
                operations.codex_operation_service,
                "retry_task",
                return_value=queued,
            ) as retry_task,
        ):
            response = client.post("/api/operations/41/retry")

        self.assertEqual(202, response.status_code)
        self.assertTrue(response.get_json()["ok"])
        retry_task.assert_called_once_with(41, trigger="manual_retry")

    def test_native_codex_retry_passes_driver_to_codex_service(self):
        client = self._client()
        queued = {"accepted": True, "busy": False, "task_id": 41, "run_id": 52, "status": "queued"}
        with (
            patch.object(operations.operation_task_store, "get_task", return_value=self._task()),
            patch.object(task_gateway, "operation_action") as action,
            patch.object(operations.codex_operation_service, "retry_task", return_value=queued) as retry_task,
        ):
            response = client.post("/api/operations/41/retry", json={"driver": "roxy"})

        self.assertEqual(202, response.status_code)
        self.assertEqual(52, response.get_json()["run_id"])
        retry_task.assert_called_once_with(41, trigger="manual_retry", driver="roxy")
        action.assert_not_called()

    def test_driver_override_rejects_other_task_types_and_sources(self):
        client = self._client()
        for task in (
            self._task(task_type="live_check"),
            self._task(source_system="account_action_tasks"),
        ):
            with self.subTest(task=task["task_type"], source=task["source_system"]):
                with (
                    patch.object(operations.operation_task_store, "get_task", return_value=task),
                    patch.object(operations.codex_operation_service, "retry_task") as retry_task,
                ):
                    response = client.post("/api/operations/41/retry", json={"driver": "roxy"})
                self.assertEqual(400, response.status_code)
                retry_task.assert_not_called()

    def test_driver_override_rejects_unknown_values(self):
        client = self._client()
        with (
            patch.object(operations.operation_task_store, "get_task") as get_task,
            patch.object(operations.codex_operation_service, "retry_task") as retry_task,
        ):
            response = client.post("/api/operations/41/retry", json={"driver": "api"})
        self.assertEqual(400, response.status_code)
        get_task.assert_not_called()
        retry_task.assert_not_called()

    def test_unregistered_native_maintenance_type_cannot_fall_through_to_oauth(self):
        client = self._client()
        task = self._task(task_type="live_check")
        with (
            patch.object(operations.operation_task_store, "get_task", return_value=task),
            patch.object(operations.codex_operation_service, "retry_task") as retry_task,
        ):
            response = client.post("/api/operations/41/retry")

        self.assertEqual(409, response.status_code)
        self.assertIn("历史任务", response.get_json()["error"])
        retry_task.assert_not_called()

    def test_real_native_maintenance_types_use_shared_default_retry(self):
        client = self._client()
        task_types = (
            "live_check", "token_refresh", "plan_check", "deactivation_mail",
            "extract_link", "codex_token_refresh",
        )
        registered = []
        try:
            for index, task_type in enumerate(task_types, start=1):
                task_gateway.register_operation_handler(
                    task_type,
                    lambda _context: task_gateway.OperationResult.success(),
                    source_systems=("native_operations",),
                )
                registered.append(task_type)
                task = self._task(task_type=task_type)
                with (
                    patch.object(operations.operation_task_store, "get_task", return_value=task),
                    patch.object(operation, "retry_runtime_task", return_value={"id": 100 + index}) as retry,
                    patch.object(task_gateway, "notify_dispatch") as notify,
                ):
                    response = client.post("/api/operations/41/retry")
                self.assertEqual(202, response.status_code)
                self.assertTrue(response.get_json()["accepted"])
                self.assertFalse(response.get_json()["busy"])
                retry.assert_called_once_with(
                    41,
                    trigger="manual_retry",
                    data={"retry_action": "manual_retry"},
                )
                notify.assert_called_once()
        finally:
            for task_type in registered:
                task_gateway.unregister_operation_handler(task_type)

    def test_native_registered_action_is_not_visible_to_legacy_source(self):
        client = self._client()
        retry = lambda _task: {"accepted": True, "busy": False}
        task_gateway.register_operation_handler(
            "live_check",
            lambda _context: task_gateway.OperationResult.success(),
            source_systems=("native_operations",),
            retry_handler=retry,
        )
        try:
            task = self._task(
                task_type="live_check",
                source_system="account_action_tasks",
            )
            with (
                patch.object(operations.operation_task_store, "get_task", return_value=task),
                patch.object(operation, "retry_runtime_task") as durable_retry,
            ):
                response = client.post("/api/operations/41/retry")
        finally:
            task_gateway.unregister_operation_handler("live_check")

        self.assertEqual(409, response.status_code)
        self.assertIn("历史任务", response.get_json()["error"])
        durable_retry.assert_not_called()

    def test_request_unknown_dispatches_registered_retry_as_a_new_run(self):
        client = self._client()
        task_type = "token_refresh"
        retry = Mock(return_value={"accepted": True, "busy": False, "run_id": 52})
        task_gateway.register_operation_handler(
            task_type,
            lambda _context: task_gateway.OperationResult.success(),
            source_systems=("native_operations",),
            retry_handler=retry,
        )
        try:
            task = self._task(
                task_type=task_type,
                source_system="native_operations",
                status="attention_required",
                result_summary={"outcome": "request_unknown", "reconcile_required": True},
            )
            with (
                patch.object(operations.operation_task_store, "get_task", return_value=task),
                patch.object(task_gateway, "operation_action", wraps=task_gateway.operation_action) as action,
            ):
                response = client.post("/api/operations/41/retry")
        finally:
            task_gateway.unregister_operation_handler(task_type)

        self.assertEqual(202, response.status_code)
        self.assertTrue(response.get_json()["accepted"])
        action.assert_called_once()
        retry.assert_called_once_with(task)

    def test_deactivated_task_is_rejected_before_registered_retry(self):
        client = self._client()
        task_type = "token_refresh"
        retry = Mock(return_value={"accepted": True, "busy": False, "run_id": 52})
        task_gateway.register_operation_handler(
            task_type,
            lambda _context: task_gateway.OperationResult.success(),
            source_systems=("native_operations",),
            retry_handler=retry,
        )
        try:
            task = self._task(
                task_type=task_type,
                status="deactivated",
                target_status="account_deactivated",
            )
            with patch.object(operations.operation_task_store, "get_task", return_value=task):
                response = client.post("/api/operations/41/retry")
        finally:
            task_gateway.unregister_operation_handler(task_type)

        self.assertEqual(409, response.status_code)
        self.assertTrue(response.get_json()["deactivated"])
        retry.assert_not_called()

    def test_deactivated_legacy_account_task_is_rejected_before_its_retry_service(self):
        client = self._client()
        task = self._task(
            task_type="plan_check",
            source_system="account_action_tasks",
            account_id=7,
        )
        with (
            patch.object(operations.account_task_store, "get_task", return_value=task),
            patch.object(
                runtime.db,
                "get_account",
                return_value={"id": 7, "email": "deactivated@example.test", "account_status": "deactivated"},
            ),
            patch.object(runtime.plan_check_service, "enqueue_account_plan_check") as enqueue,
        ):
            response = client.post("/api/account-tasks/41/retry")

        self.assertEqual(409, response.status_code)
        self.assertTrue(response.get_json()["deactivated"])
        enqueue.assert_not_called()

    def test_oauth_deactivated_projection_rejects_legacy_account_task_retry(self):
        client = self._client()
        task = self._task(
            task_type="plan_check",
            source_system="account_action_tasks",
            account_id=7,
        )
        with (
            patch.object(operations.account_task_store, "get_task", return_value=task),
            patch.object(
                runtime.db,
                "get_account",
                return_value={
                    "id": 7,
                    "email": "deactivated@example.test",
                    "codex_credential_state": "deactivated",
                },
            ),
            patch.object(runtime.plan_check_service, "enqueue_account_plan_check") as enqueue,
        ):
            response = client.post("/api/account-tasks/41/retry")

        self.assertEqual(409, response.status_code)
        self.assertTrue(response.get_json()["deactivated"])
        enqueue.assert_not_called()

    def test_registered_maintenance_cancel_action_and_native_codex_cancel_are_separate(self):
        maintenance_type = "deactivation_mail"
        task_gateway.register_operation_handler(
            maintenance_type,
            lambda _context: task_gateway.OperationResult.success(),
            source_systems=("native_operations",),
        )
        try:
            client = self._client()
            maintenance_task = self._task(
                task_type=maintenance_type,
                source_system="native_operations",
                runs=[{"id": 53, "status": "running"}],
            )
            with (
                patch.object(operations.operation_task_store, "get_task", return_value=maintenance_task),
                patch.object(
                    operation,
                    "request_run_cancel",
                    return_value={"id": 53, "status": "cancelling"},
                ) as request_run_cancel,
                patch.object(task_gateway, "notify_dispatch") as notify,
            ):
                response = client.post("/api/operations/41/cancel")
            self.assertEqual(200, response.status_code)
            self.assertEqual("cancelling", response.get_json()["state"])
            request_run_cancel.assert_called_once_with(
                53,
                reason="用户手动停止统一 durable operation",
            )
            notify.assert_called_once()
        finally:
            task_gateway.unregister_operation_handler(maintenance_type)

        native_task = self._task(
            runs=[{"id": 54, "status": "running"}],
        )
        with (
            patch.object(operations.operation_task_store, "get_task", return_value=native_task),
            patch.object(
                operations.codex_operation_service,
                "request_cancel",
                return_value={"ok": True, "run_id": 54, "state": "cancelling"},
            ) as request_cancel,
        ):
            response = client.post("/api/operations/41/cancel")

        self.assertEqual(200, response.status_code)
        request_cancel.assert_called_once_with(run_id=54)

    def test_registered_maintenance_terminate_action_and_native_codex_terminate_are_separate(self):
        maintenance_type = "deactivation_mail"
        task_gateway.register_operation_handler(
            maintenance_type,
            lambda _context: task_gateway.OperationResult.success(),
            source_systems=("native_operations",),
        )
        try:
            client = self._client()
            maintenance_task = self._task(
                task_type=maintenance_type,
                source_system="native_operations",
                runs=[{"id": 63, "status": "running"}],
            )
            with (
                patch.object(operations.operation_task_store, "get_task", return_value=maintenance_task),
                patch.object(
                    operation,
                    "terminate_run",
                    return_value={"id": 63, "status": "stopped"},
                ) as terminate_run,
                patch.object(task_gateway, "notify_dispatch") as notify,
            ):
                response = client.post("/api/operations/41/terminate")
            self.assertEqual(200, response.status_code)
            self.assertEqual("stopped", response.get_json()["state"])
            terminate_run.assert_called_once_with(
                63,
                reason="用户手动终止统一 durable operation",
            )
            notify.assert_called_once()
        finally:
            task_gateway.unregister_operation_handler(maintenance_type)

        native_task = self._task(
            runs=[{"id": 64, "status": "running"}],
        )
        with (
            patch.object(operations.operation_task_store, "get_task", return_value=native_task),
            patch.object(
                operations.codex_operation_service,
                "terminate",
                return_value={"ok": True, "run_id": 64, "state": "stopped"},
            ) as terminate,
        ):
            response = client.post("/api/operations/41/terminate")

        self.assertEqual(200, response.status_code)
        terminate.assert_called_once_with(run_id=64)

    def test_bulk_operation_action_reuses_registered_handler_and_skips_active_task(self):
        task_type = "bulk_live_check"
        retry = Mock(return_value={"accepted": True, "busy": False, "run_id": 71})
        task_gateway.register_operation_handler(
            task_type,
            lambda _context: task_gateway.OperationResult.success(),
            source_systems=("native_operations",),
            retry_handler=retry,
        )
        tasks = {
            41: self._task(task_type=task_type, status="failed"),
            42: self._task(task_type=task_type, status="running"),
        }
        try:
            client = self._client()
            with patch.object(
                operations.operation_task_store,
                "get_task",
                side_effect=lambda task_id: tasks.get(int(task_id)),
            ):
                response = client.post(
                    "/api/operations/bulk",
                    json={"action": "retry", "task_ids": [41, 42]},
                )
        finally:
            task_gateway.unregister_operation_handler(task_type)

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual(1, payload["accepted_count"])
        self.assertEqual(1, payload["skipped_count"])
        self.assertEqual(41, payload["accepted"][0]["task_id"])
        self.assertEqual(42, payload["skipped"][0]["task_id"])
        self.assertIn("执行", payload["skipped"][0]["error"])
        retry.assert_called_once_with(tasks[41])

    def test_bulk_operation_rejects_unknown_action_and_excessive_task_ids(self):
        client = self._client()

        with patch.object(
            operations.operation_task_store,
            "delete_tasks",
            create=True,
            return_value={
                "deleted": [41],
                "deleted_count": 1,
                "skipped": [],
                "skipped_count": 0,
            },
        ) as delete_tasks:
            delete = client.post(
                "/api/operations/bulk",
                json={"action": "delete", "task_ids": [41]},
            )
        self.assertEqual(200, delete.status_code)
        self.assertEqual("delete", delete.get_json()["action"])
        delete_tasks.assert_called_once_with([41])

        invalid = client.post(
            "/api/operations/bulk",
            json={"action": "unsupported", "task_ids": [41]},
        )
        self.assertEqual(400, invalid.status_code)

        excessive = client.post(
            "/api/operations/bulk",
            json={"action": "retry", "task_ids": list(range(1, 102))},
        )
        self.assertEqual(400, excessive.status_code)

        for invalid_id in (1.9, True):
            response = client.post(
                "/api/operations/bulk",
                json={"action": "retry", "task_ids": [invalid_id]},
            )
            self.assertEqual(400, response.status_code)

    def test_single_delete_uses_task_store_and_returns_deleted_task(self):
        client = self._client()
        with patch.object(
            operations.operation_task_store,
            "delete_tasks",
            create=True,
            return_value={
                "deleted": [41],
                "deleted_count": 1,
                "skipped": [],
                "skipped_count": 0,
            },
        ) as delete_tasks:
            response = client.post("/api/operations/41/delete")

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.get_json()["deleted"])
        delete_tasks.assert_called_once_with([41])

    def test_single_delete_reports_active_task_without_hiding_it(self):
        client = self._client()
        with patch.object(
            operations.operation_task_store,
            "delete_tasks",
            create=True,
            return_value={
                "deleted": [],
                "deleted_count": 0,
                "skipped": [{"task_id": 41, "error": "任务仍在执行，不能删除"}],
                "skipped_count": 1,
            },
        ):
            response = client.post("/api/operations/41/delete")

        self.assertEqual(409, response.status_code)
        self.assertFalse(response.get_json()["deleted"])
        self.assertIn("执行", response.get_json()["error"])

    def test_bulk_cancel_rechecks_queued_state_before_dispatch(self):
        client = self._client()
        queued = self._task(status="queued", runs=[{"id": 55, "status": "queued"}])
        running = self._task(status="running", runs=[{"id": 55, "status": "running"}])
        with (
            patch.object(
                operations.operation_task_store,
                "get_task",
                side_effect=[queued, running],
            ),
            patch.object(operations.codex_operation_service, "request_cancel") as request_cancel,
        ):
            response = client.post(
                "/api/operations/bulk",
                json={"action": "cancel", "task_ids": [41]},
            )

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual(0, payload["accepted_count"])
        self.assertEqual(1, payload["skipped_count"])
        self.assertIn("状态", payload["skipped"][0]["error"])
        request_cancel.assert_not_called()

    def test_bulk_cancel_does_not_load_selected_tasks_event_history(self):
        client = self._client()
        tasks = {
            task_id: self._task(
                id=task_id, task_type="account_completion", source_system="webui_runtime",
                status="queued", runs=[{"id": task_id + 100, "status": "queued"}],
            )
            for task_id in (41, 42)
        }
        reads = []

        def read_without_events(task_id, *, include_events=True):
            reads.append(task_id)
            if include_events:
                raise AssertionError("取消任务不应加载历史事件")
            return tasks[task_id]

        cancel = Mock(side_effect=lambda task: {"ok": True, "state": "cancelled"})
        with (
            patch.object(operations.operation_task_store, "get_task", side_effect=read_without_events),
            patch.object(task_gateway, "operation_action", return_value=cancel),
        ):
            response = client.post(
                "/api/operations/bulk", json={"action": "cancel", "task_ids": [41, 42]},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.get_json()["accepted_count"])
        self.assertEqual(0, response.get_json()["skipped_count"])
        self.assertEqual({41, 42}, set(reads))
        self.assertEqual([41, 42], [call.args[0]["id"] for call in cancel.call_args_list])

    def test_single_cancel_and_terminate_do_not_load_event_history(self):
        client = self._client()
        task = self._task(status="queued", runs=[{"id": 55, "status": "queued"}])

        def read_without_events(task_id, *, include_events=True):
            if include_events:
                raise AssertionError("停止任务不应加载历史事件")
            return task

        for action in ("cancel", "terminate"):
            with (
                self.subTest(action=action),
                patch.object(operations.operation_task_store, "get_task", side_effect=read_without_events),
                patch.object(task_gateway, "operation_action", return_value=lambda task: {
                    "ok": True, "state": "cancelled",
                }),
            ):
                response = client.post(f"/api/operations/41/{action}")
                self.assertEqual(200, response.status_code)
                self.assertEqual("cancelled", response.get_json()["state"])

    def test_bulk_terminate_skips_queued_task(self):
        client = self._client()
        queued = self._task(status="queued", runs=[{"id": 56, "status": "queued"}])
        with (
            patch.object(operations.operation_task_store, "get_task", return_value=queued),
            patch.object(operations.codex_operation_service, "terminate") as terminate,
        ):
            response = client.post(
                "/api/operations/bulk",
                json={"action": "terminate", "task_ids": [41]},
            )

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual(0, payload["accepted_count"])
        self.assertEqual(1, payload["skipped_count"])
        self.assertIn("执行中", payload["skipped"][0]["error"])
        terminate.assert_not_called()

    def test_operation_list_exposes_short_error_code_and_summary(self):
        client = self._client()
        with (
            patch.object(
                operations.operation_task_store,
                "list_tasks",
                return_value={
                    "ok": True,
                    "items": [{
                        "id": 41,
                        "task_type": "codex_token_refresh",
                        "current_stage": "complete",
                        "error_message": "TokenRefreshReauthRequiredError: reauth_required: refresh_token_reused",
                    }],
                    "total": 1,
                    "facets": {},
                },
            ),
            patch.object(operations.operation_task_store, "list_batches", return_value=[]),
        ):
            response = client.get("/api/operations")

        self.assertEqual(200, response.status_code)
        info = response.get_json()["items"][0]["error_info"]
        self.assertEqual("AUTH-002", info["display_code"])
        self.assertEqual("授权已失效，请重新登录", info["summary"])

    def test_operation_list_keeps_remote_fence_and_shows_specific_cause(self):
        client = self._client()
        row = {
            "id": 41,
            "task_type": "token_refresh",
            "status": "attention_required",
            "current_stage": "complete",
            "error_code": "request_unknown",
            "error_message": "远端结果待确认：查活失败",
            "result_summary": {
                "outcome": "request_unknown",
                "cause_code": "email_otp_failed",
                "auth_diagnostics": {"operation": "email_otp", "failure_kind": "no_mail"},
            },
        }
        with (
            patch.object(operations.operation_task_store, "list_tasks", return_value={
                "ok": True, "items": [row], "total": 1, "facets": {},
            }),
            patch.object(operations.operation_task_store, "list_batches", return_value=[]),
        ):
            response = client.get("/api/operations")

        self.assertEqual(200, response.status_code)
        info = response.get_json()["items"][0]["error_info"]
        self.assertEqual("MAIL-OTP-002", info["display_code"])
        self.assertEqual("MAIL-OTP-002", info["cause_display_code"])

    def test_operation_detail_projects_each_historical_run_error(self):
        client = self._client()
        task = self._task(
            task_type="token_refresh", status="success", error_message=None,
            runs=[{
                "id": 51,
                "run_no": 1,
                "status": "attention_required",
                "progress_stage": "complete",
                "error_code": "request_unknown",
                "error_message": "远端结果待确认：查活失败",
                "result_summary": {
                    "outcome": "request_unknown", "error_category": "email",
                    "auth_method": "email_otp",
                },
            }, {
                "id": 52,
                "run_no": 2,
                "status": "success",
                "error_message": None,
            }],
        )
        with patch.object(operations.operation_task_store, "get_task", return_value=task):
            response = client.get("/api/operations/41?include_events=0")

        self.assertEqual(200, response.status_code)
        projected = response.get_json()["task"]
        self.assertNotIn("error_info", projected)
        self.assertEqual("MAIL-RECEIPT", projected["runs"][0]["error_info"]["display_code"])
        self.assertEqual("MAIL-RECEIPT", projected["runs"][0]["error_info"]["cause_display_code"])
        self.assertNotIn("error_info", projected["runs"][1])

    def test_legacy_account_tasks_api_uses_shared_error_classification(self):
        client = self._client()
        row = {
            "id": 7,
            "task_type": "deactivation_mail",
            "status": "interrupted",
            "error": "WebUI 重启导致任务中断，请重新执行",
        }
        with (
            patch.object(operations.account_task_store, "list_tasks", return_value={
                "items": [row], "total": 1,
            }),
            patch("core.accounts.token_refresh.settings", return_value={}),
            patch.object(operations.codex_token_refresh_service, "settings", return_value={}),
        ):
            response = client.get("/api/account-tasks")

        self.assertEqual(200, response.status_code)
        info = response.get_json()["items"][0]["error_info"]
        self.assertEqual("service.interrupted", info["code"])
        self.assertEqual("SYS-002", info["display_code"])


if __name__ == "__main__":
    unittest.main()
