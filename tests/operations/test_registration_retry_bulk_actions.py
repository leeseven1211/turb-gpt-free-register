"""任务中心把可归组的历史注册重试一次交给注册服务。"""
import copy
import unittest
from unittest.mock import Mock, patch

from core.operations import action_service


def task(ident, source=21, **changes):
    return {
        "id": ident, "task_type": "registration", "source_system": "registration_chains",
        "status": "failed", "next_actions": [],
        "runs": [{"source_system": "registration_jobs", "source_id": str(source)}],
        **changes,
    }


class RegistrationRetryBulkActionTests(unittest.TestCase):
    def run_bulk(self, tasks, ids=None, **kwargs):
        with patch.object(action_service.operation_task_store, "get_action_tasks_many", return_value=tasks):
            return action_service.accept_bulk_operation_action("retry", ids or list(tasks), **kwargs)

    def test_sources_are_deduplicated_and_explicit_action_precedes_latest_run(self):
        tasks = {
            41: task(41, 99, next_actions=[{"action": "registration_resume", "source_job_id": 21}]),
            42: task(42, 21),
            43: task(43, 22),
        }
        original = copy.deepcopy(tasks)
        results = {
            21: {"ok": True, "status": 202, "message": "原注册任务已入队"},
            22: {"ok": False, "status": 409, "error": "原注册身份已变化"},
        }
        with (
            patch.object(action_service.task_gateway, "operation_action", return_value=None),
            patch.object(action_service.registration_service, "retry_jobs", return_value=results) as retry,
            patch.object(action_service.registration_service, "retry_job") as single,
        ):
            reply = self.run_bulk(tasks, [43, 42, 41, 999])
        retry.assert_called_once_with([22, 21], workers=1)
        single.assert_not_called()
        self.assertEqual([42, 41], [item["task_id"] for item in reply["accepted"]])
        self.assertEqual([43, 999], [item["task_id"] for item in reply["skipped"]])
        self.assertEqual("原注册身份已变化", reply["skipped"][0]["error"])
        self.assertEqual(tasks, original)
        self.assertEqual(results[21]["status"], 202)

    def test_active_deactivated_managed_and_registered_routes_keep_their_ownership(self):
        tasks = {
            41: task(41),
            42: task(42, status="running"),
            43: task(43, target_status="account_deactivated"),
            44: task(44, _managed_target_round_id=70),
            45: task(45, task_type="fixture_registered"),
            46: task(46, task_type="codex_retry", source_system="native_operations"),
        }
        registered = Mock(return_value={"accepted": True})
        handler = lambda task_type, *_args, **_kwargs: registered if task_type == "fixture_registered" else None
        with (
            patch.object(action_service, "_accept_managed_retries", return_value={
                44: ({"ok": True, "state": "queued"}, 202),
            }),
            patch.object(action_service.task_gateway, "operation_action", side_effect=handler),
            patch.object(action_service.registration_service, "retry_jobs", return_value={21: {"ok": True}}) as retry,
            patch.object(action_service.registration_service, "retry_job") as single,
            patch.object(action_service.codex_operation_service, "retry_task", return_value={"accepted": True}) as codex,
        ):
            reply = self.run_bulk(tasks)
        retry.assert_called_once_with([21], workers=1)
        single.assert_not_called()
        registered.assert_called_once_with(tasks[45])
        codex.assert_called_once_with(46, trigger="manual_retry")
        self.assertEqual([41, 44, 45, 46], [item["task_id"] for item in reply["accepted"]])
        self.assertEqual([42, 43], [item["task_id"] for item in reply["skipped"]])

    def test_overlong_request_key_never_submits_registration(self):
        with (
            patch.object(action_service.registration_service, "retry_jobs") as retry,
            patch.object(action_service.registration_service, "retry_job") as single,
        ):
            reply = self.run_bulk({41: task(41)}, request_key="x" * 129)
        retry.assert_not_called()
        single.assert_not_called()
        self.assertEqual(0, reply["accepted_count"])
        self.assertIn("Idempotency-Key", reply["skipped"][0]["error"])

    def test_collection_failure_is_returned_for_each_selected_task_without_internal_details(self):
        logger = Mock()
        with (
            patch.object(action_service.task_gateway, "operation_action", return_value=None),
            patch.object(action_service.registration_service, "retry_jobs",
                         side_effect=RuntimeError("fixture-private-database-details")),
        ):
            reply = self.run_bulk({41: task(41), 42: task(42, 22)}, operation_logger=logger)
        self.assertEqual(0, reply["accepted_count"])
        self.assertEqual([41, 42], [item["task_id"] for item in reply["skipped"]])
        self.assertNotIn("fixture-private", str(reply))
        logger.exception.assert_called_once()
