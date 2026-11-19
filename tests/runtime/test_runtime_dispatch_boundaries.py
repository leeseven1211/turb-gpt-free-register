"""Phase 6 T3 dispatch guards use real entry points with all I/O blocked."""
from __future__ import annotations

from contextlib import ExitStack
import threading
import unittest
from unittest.mock import patch

from core.codex import operation_service as codex
from core.operations import concurrency, task_gateway
from core.registration import service as registration
from core.runtime import execution_access
from core.storage import postgres


class RuntimeDispatchBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(
            postgres, "connect", side_effect=AssertionError("real DB forbidden")))
        self.stack.enter_context(patch.object(execution_access, "component_start_allowed", return_value=False))
        self.stack.enter_context(patch.object(execution_access, "execution_allowed", return_value=False))
        self.stack.enter_context(patch.object(
            threading, "Thread", side_effect=AssertionError("closed gate cannot create a thread")))

    def test_web_registration_start_has_no_thread_side_effect(self):
        self.assertFalse(registration.start_dispatcher())

    def test_web_gateway_start_has_no_thread_side_effect(self):
        self.assertFalse(task_gateway.start_dispatcher())

    def test_web_dependency_start_does_not_recover_or_create_thread(self):
        with patch.object(task_gateway, "_operation", side_effect=AssertionError("closed gate cannot recover")):
            self.assertFalse(task_gateway.start_dependency_dispatcher())

    def test_web_codex_start_does_not_register_or_start(self):
        with patch.object(codex, "register_handler", side_effect=AssertionError("closed gate cannot register")):
            self.assertFalse(codex.start_dispatcher())

    def test_web_registration_tick_does_not_create_pool_or_read_jobs(self):
        with patch.object(registration, "get_executor", side_effect=AssertionError("closed gate cannot create a pool")):
            self.assertEqual(registration.dispatch_pending_once(), 0)

    def test_web_gateway_tick_does_not_read_or_submit(self):
        with patch.object(task_gateway, "_operation", side_effect=AssertionError("closed gate cannot read runs")):
            self.assertEqual(task_gateway.dispatch_registered_once(), 0)

    def test_web_dependency_tick_does_not_claim(self):
        with patch.object(task_gateway, "_operation", side_effect=AssertionError("closed gate cannot claim")):
            self.assertEqual(task_gateway._dependency_tick(), 0)

    def test_owner_loss_rejects_before_permit_creation(self):
        result = concurrency.try_admit_and_claim(
            execution_key="task:1", task_type="plan_check",
            claim=lambda *_args: self.fail("closed gate cannot claim"),
        )
        self.assertEqual(result.blocked_by, ("runtime_not_ready",))

    def test_submission_workers_do_not_create_executor(self):
        with patch.object(registration, "_executor_workers", 3), patch.object(
                registration, "_executor", None):
            self.assertEqual(registration.configure_submission_workers(7), 7)
            self.assertEqual(registration._executor_workers, 7)
            self.assertIsNone(registration._executor)


if __name__ == "__main__":
    unittest.main()
