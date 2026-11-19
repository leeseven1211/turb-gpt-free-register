"""任务动作应用层保留入口优先级、兼容来源及批量状态竞争语义。"""
from __future__ import annotations

from contextlib import ExitStack
import logging
import unittest
from unittest.mock import Mock, patch

from core.operations import action_service


class TaskCenterActionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.read = self.stack.enter_context(patch.object(action_service.operation_task_store, "get_task"))
        self.managed = self.stack.enter_context(patch("core.bulk_operations.service.retry_managed_task", return_value=None))
        self.registered = self.stack.enter_context(patch.object(action_service.task_gateway, "operation_action", return_value=None))
        self.task = {
            "id": 41, "task_type": "codex_retry", "source_system": "native_operations",
            "status": "failed", "account_id": 7, "runs": [], "next_actions": [],
        }
        self.read.return_value = self.task

    def test_managed_retry_precedes_driver_ownership_and_terminal_checks(self):
        self.task.update(task_type="plan_check", status="running", target_status="account_deactivated")
        self.managed.return_value = {"ok": True, "accepted": True, "round_id": "90", "state": "queued"}
        payload, status = action_service.perform_operation_action(41, "retry", driver_override="roxy", request_key="key")
        self.assertEqual(202, status)
        self.assertEqual("90", payload["round_id"])
        self.managed.assert_called_once_with(41, request_key="operations-retry:key:41")
        self.registered.assert_not_called()

    def test_invalid_key_is_checked_only_after_task_existence_and_expected_status(self):
        for task, expected, want in ((None, None, 404), (self.task, "queued", 409), (self.task, None, 422)):
            with self.subTest(expected=expected, want=want):
                self.read.return_value = task
                payload, status = action_service.perform_operation_action(
                    41, "retry", expected_status=expected, request_key="x" * 129,
                )
                self.assertEqual(want, status)
                self.assertFalse(payload["ok"])
        self.managed.assert_not_called()

    def test_managed_error_preserves_classified_response(self):
        failure = ValueError("轮次不能重跑")
        failure.code, failure.status = "round_conflict", 422
        self.managed.side_effect = failure
        payload, status = action_service.perform_operation_action(41, "retry")
        self.assertEqual(("round_conflict", 422), (payload["error_code"], status))
        self.registered.assert_not_called()

    def test_registration_next_action_precedes_latest_run_source(self):
        self.task.update(
            task_type="account_completion", source_system="account_action_tasks",
            next_actions=[{"action": "registration_resume", "source_job_id": 81}],
            runs=[{"source_system": "registration_jobs", "source_id": "82"}],
        )
        with patch.object(action_service.registration_service, "retry_job", return_value={"ok": True, "status": 202, "job": {"id": 81}}) as retry:
            payload, status = action_service.perform_operation_action(41, "retry")
        self.assertEqual((202, 81), (status, payload["job"]["id"]))
        self.assertNotIn("status", payload)
        retry.assert_called_once_with(81)

    def test_latest_account_run_uses_legacy_retry_response_unchanged(self):
        self.task.update(task_type="plan_check", source_system="account_action_tasks", runs=[{"source_system": "account_action_tasks", "source_id": "82"}])
        with patch.object(action_service, "retry_legacy_account_task", return_value=({"ok": False, "error": "关联账号不存在"}, 404)) as retry:
            payload, status = action_service.perform_operation_action(41, "retry")
        self.assertEqual(404, status)
        self.assertEqual("关联账号不存在", payload["error"])
        self.assertEqual(82, retry.call_args.args[0])

    def test_registered_handler_exception_retains_log_and_response_contract(self):
        self.registered.return_value = Mock(side_effect=RuntimeError("fixture failure"))
        action_logger = Mock(spec=logging.Logger)
        payload, status = action_service.perform_operation_action(41, "retry", operation_logger=action_logger)
        self.assertEqual(503, status)
        self.assertEqual("重试入口异常：RuntimeError: fixture failure", payload["error"])
        action_logger.exception.assert_called_once()

    def test_cancel_keeps_light_reads_and_expected_run_status_without_mutating_projection(self):
        self.task.update(status="queued", runs=[{"id": 61, "status": "queued"}])
        cancel = Mock(return_value={"ok": True, "state": "cancelled"})
        self.registered.return_value = cancel
        payload = action_service.perform_bulk_action([41], "cancel")
        self.assertEqual((1, 0), (payload["accepted_count"], payload["skipped_count"]))
        self.assertEqual("queued", cancel.call_args.args[0]["_expected_run_status"])
        self.assertNotIn("_expected_run_status", self.task)
        self.assertEqual(2, self.read.call_count)
        self.assertTrue(all(call.kwargs == {"include_events": False} for call in self.read.call_args_list))

    def test_bulk_cancel_skips_task_that_starts_between_selection_and_action(self):
        self.read.side_effect = [{**self.task, "status": "queued"}, {**self.task, "status": "running"}]
        payload = action_service.perform_bulk_action([41], "cancel")
        self.assertEqual((0, 1), (payload["accepted_count"], payload["skipped_count"]))
        self.assertIn("状态已变化", payload["skipped"][0]["error"])
        self.registered.assert_not_called()

    def test_bulk_empty_stop_is_skipped_and_retry_key_is_scoped_per_task(self):
        self.task.update(status="queued")
        self.registered.return_value = Mock(return_value={"ok": True, "state": "empty", "message": "没有活跃 attempt"})
        payload = action_service.perform_bulk_action([41], "cancel")
        self.assertEqual((0, 1), (payload["accepted_count"], payload["skipped_count"]))
        self.task.update(status="failed")
        self.managed.return_value = {"ok": True, "accepted": True, "state": "queued"}
        payload = action_service.perform_bulk_action([41, 42], "retry", request_key="shared")
        self.assertEqual(2, payload["accepted_count"])
        self.assertEqual(["operations-retry:shared:41", "operations-retry:shared:42"], [call.kwargs["request_key"] for call in self.managed.call_args_list])


class LegacyAccountActionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.task = {"id": 701, "status": "failed", "task_type": "plan_check", "account_id": 7}
        self.stack.enter_context(patch.object(action_service.account_task_store, "get_task", return_value=self.task))
        self.managed = self.stack.enter_context(patch("core.bulk_operations.execution.retry_managed", return_value=None))
        self.account = {"id": 7, "email": "fixture@example.test", "access_token": "fixture-token"}
        self.read_account = self.stack.enter_context(patch.object(action_service.db, "get_account", return_value=self.account))

    def test_managed_legacy_retry_precedes_account_and_active_checks(self):
        self.task["status"] = "running"
        self.managed.return_value = {"accepted": True, "round_id": "901"}
        payload, status = action_service.retry_legacy_account_task(701)
        self.assertEqual((202, "901"), (status, payload["round_id"]))
        self.read_account.assert_not_called()

    def test_refresh_retry_retains_force_flag_and_trigger(self):
        self.task["task_type"] = "token_refresh"
        with patch.object(action_service.live_check_service, "enqueue_account_live_check", return_value={"accepted": True, "task_id": 702}) as enqueue:
            payload, status = action_service.retry_legacy_account_task(701)
        self.assertEqual((202, 702), (status, payload["task_id"]))
        enqueue.assert_called_once_with(account_id=7, email="fixture@example.test", trigger="token_refresh_manual_retry", proxy=None, force_refresh=True)

    def test_codex_refresh_prefers_recorded_filename_and_preserves_unknown_retry(self):
        self.task.update(task_type="codex_token_refresh", result_summary={"filename": "recorded.json"}, data={"credential_filename": "older.json"})
        with patch.object(action_service.codex_token_refresh_service, "enqueue_refresh", return_value={"accepted": True, "task_id": 702}) as enqueue:
            payload, status = action_service.retry_legacy_account_task(701)
        self.assertEqual((202, 702), (status, payload["task_id"]))
        enqueue.assert_called_once_with("recorded.json", trigger="manual_task_center_retry", allow_unknown_manual_retry=True)

    def test_legacy_setup_preserves_snapshot_capture_and_force_operation(self):
        self.task["task_type"] = "twofa_change"
        bundle = ({"revision": "fixture"}, {"twofa_driver": "ACCOUNT_2FA_DRIVER"}, {"twofa_driver": "protocol"})
        from core.accounts import operation_coordinator, operation_handlers
        with (
            patch.object(action_service.operation_settings, "runtime_execution_settings", return_value=bundle),
            patch.object(operation_coordinator, "enqueue_account_setup", return_value={"accepted": True, "task_id": 702}) as enqueue,
        ):
            payload, status = action_service.retry_legacy_account_task(701)
        self.assertEqual((202, 702), (status, payload["task_id"]))
        self.assertEqual("twofa_change", enqueue.call_args.kwargs["operation"])
        self.assertEqual({"twofa"}, enqueue.call_args.kwargs["steps"])
        self.assertIs(bundle, enqueue.call_args.kwargs["snapshot_bundle"])
        self.assertIs(operation_handlers.register_runtime_handlers, enqueue.call_args.kwargs["register_handlers"])


if __name__ == "__main__":
    unittest.main()
