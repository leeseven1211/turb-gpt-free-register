# -*- coding: utf-8 -*-
"""统一操作路由的来源/任务类型边界回归。"""
from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

from flask import Flask

from core.operations import task_gateway
from core.storage import operation
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

    def test_request_unknown_blocks_registered_retry_without_invoking_adapter(self):
        client = self._client()
        task_type = "token_refresh"
        retry = lambda _task: {"accepted": True, "busy": False}
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

        self.assertEqual(409, response.status_code)
        self.assertTrue(response.get_json()["reconcile_required"])
        action.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
