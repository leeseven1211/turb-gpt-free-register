"""补全续接只消费剩余计划，并清理已完成子任务的等待标记。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import account_completion_service
from core.operations import task_gateway
from webui import runtime


class CompletionContinuationTests(unittest.TestCase):
    def setUp(self):
        active = patch.object(account_completion_service, "active_registration_job", return_value=None)
        active.start()
        self.addCleanup(active.stop)
        settings = patch.object(runtime, "_completion_settings_from_snapshot", return_value={})
        settings.start()
        self.addCleanup(settings.stop)

    def _context(self, data):
        context = SimpleNamespace(
            account_id=41,
            task_id=42,
            run_id=43,
            email="completion@example.test",
            run={"data": data},
            config_snapshot={},
            finished=False,
            last_result=None,
            report=lambda **_event: None,
            release_lease=lambda: None,
        )

        def finish(result):
            context.finished = True
            context.last_result = result
            return result.as_dict()

        context.finish = finish
        return context

    def _capture_worker_plan(self, data, *, missing_steps):
        context = self._context(data)
        context.last_result = task_gateway.OperationResult.success()
        with (
            patch.object(runtime, "_run_account_completion_worker") as worker,
            patch.object(runtime.db, "get_account", return_value={"id": 41}),
            patch.object(account_completion_service, "completion_plan", return_value={"missing_steps": missing_steps}) as plan,
        ):
            runtime._handle_native_account_completion(context)
        return worker.call_args.kwargs, plan

    def test_explicit_empty_continuation_does_not_restart_original_plan(self):
        kwargs, plan = self._capture_worker_plan({
            "planned_steps": ["refresh_at", "password", "codex"],
            "continuation_payload": {"remaining_steps": []},
        }, missing_steps=["refresh_at", "password", "codex"])

        self.assertEqual([], kwargs["planned_steps"])
        plan.assert_not_called()

    def test_explicit_empty_original_plan_does_not_recompute(self):
        kwargs, plan = self._capture_worker_plan({"planned_steps": []}, missing_steps=["refresh_at"])

        self.assertEqual([], kwargs["planned_steps"])
        plan.assert_not_called()

    def test_nonempty_continuation_executes_only_remaining_steps(self):
        kwargs, plan = self._capture_worker_plan({
            "planned_steps": ["refresh_at", "password", "codex"],
            "continuation_payload": {"remaining_steps": ["codex"]},
        }, missing_steps=["refresh_at", "password", "codex"])

        self.assertEqual(["codex"], kwargs["planned_steps"])
        plan.assert_not_called()

    def test_historical_task_without_plan_fields_recomputes_missing_steps(self):
        kwargs, plan = self._capture_worker_plan({}, missing_steps=["password", "codex"])

        self.assertEqual(["password", "codex"], kwargs["planned_steps"])
        plan.assert_called_once()

    def test_consumed_child_waiting_markers_are_cleared_and_evidence_survives(self):
        summary = {
            "awaiting_steps": ["account_setup"],
            "deferred_steps": ["password", "twofa"],
            "continuation_steps": [],
            "refresh_at": {"accepted": True, "task_id": 11},
            "account_setup": {"accepted": True, "task_id": 12, "run_id": 13},
        }
        context = self._context({
            "continuation_payload": {"remaining_steps": [], "result_summary": summary},
        })
        with (
            patch.object(runtime.db, "get_account", return_value={"id": 41}),
            patch.object(account_completion_service, "completion_plan", return_value={"missing_steps": []}),
        ):
            result = runtime._handle_native_account_completion(context)

        self.assertEqual("success", result.status)
        self.assertEqual([], result.summary["planned_steps"])
        self.assertEqual({"accepted": True, "task_id": 11}, result.summary["refresh_at"])
        self.assertEqual({"accepted": True, "task_id": 12, "run_id": 13}, result.summary["account_setup"])
        for key in ("awaiting_steps", "deferred_steps", "continuation_steps"):
            self.assertNotIn(key, result.summary)
        self.assertEqual(["account_setup"], summary["awaiting_steps"])
