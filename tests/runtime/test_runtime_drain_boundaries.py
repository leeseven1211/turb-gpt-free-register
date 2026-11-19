"""Phase 6 T3 drain regressions against product functions and offline boundaries."""
from __future__ import annotations

import importlib
from contextlib import ExitStack, contextmanager, nullcontext
import threading
import types
import unittest
from unittest.mock import Mock, patch

from core.operations import concurrency
from core.operations import executor as executor_module
from core.runtime import execution_access
from core.storage import postgres
from core.storage.operations import dependency_handoffs


class DrainTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(postgres, "connect", side_effect=AssertionError("real DB forbidden")))
        self.allowed = False
        self.owner = True
        self.concurrency = types.SimpleNamespace(
            current_execution=Mock(return_value=None),
            execution_scope=lambda _context: nullcontext(),
            release_execution=Mock())
        self.execution = types.SimpleNamespace(
            execution_key="operation_run:9", execution_id="original-execution",
            permit_id="original-permit", claimed_run={"id": 9, "attempts": 2})
        self.store = types.SimpleNamespace(requeue_claimed_run=Mock())
        self.rollback = types.SimpleNamespace(requeue_dependency=Mock())
        self.stack.enter_context(patch.object(execution_access, "execution_allowed", lambda: self.allowed))
        self.stack.enter_context(patch.object(execution_access, "execution_owner_valid", lambda: self.owner))
        for name in ("current_execution", "execution_scope", "release_execution", "try_admit_and_claim"):
            self.stack.enter_context(patch.object(concurrency, name,
                lambda *args, _name=name, **kwargs: getattr(self.concurrency, _name)(*args, **kwargs)))
        self.stack.enter_context(patch.object(dependency_handoffs, "requeue_dependency",
            lambda *args, **kwargs: self.rollback.requeue_dependency(*args, **kwargs)))

    def product(self, relative, names, scope):
        module = importlib.import_module(relative.removesuffix(".py").replace("/", "."))
        for name in names:
            self.assertTrue(callable(getattr(module, name)), name)
        # Keep the actual product globals/function identities, replacing only
        # their side-effect dependencies for this test's lifetime.
        self.stack.enter_context(patch.dict(module.__dict__, scope))
        return module.__dict__

    def gateway(self):
        scope = {"_operation": lambda: self.store, "notify_dispatch": Mock()}
        return self.product("core/operations/task_gateway.py", ["execute_admitted", "rollback_admission"], scope)

    def test_gate_closure_before_callback_requeues_original_run_and_releases_once(self):
        callback = Mock(side_effect=AssertionError("must not execute"))
        scope = self.gateway()
        scope["execute_admitted"](self.execution, callback)
        self.store.requeue_claimed_run.assert_called_once_with(
            9, execution_id="original-execution", reason="runtime_execution_paused", delay_seconds=0)
        self.concurrency.release_execution.assert_called_once()
        callback.assert_not_called()

    def test_gate_closes_while_entering_execution_scope_before_callback(self):
        self.allowed = True
        @contextmanager
        def execution_scope(_context):
            self.allowed = False
            yield
        self.concurrency.execution_scope = execution_scope
        callback = Mock()
        self.gateway()["execute_admitted"](self.execution, callback)
        callback.assert_not_called()
        self.store.requeue_claimed_run.assert_called_once()
        self.concurrency.release_execution.assert_called_once()

    def test_started_callback_closing_gate_is_not_requeued(self):
        self.allowed = True
        def callback():
            self.allowed = False
            return "finished-original"
        self.assertEqual("finished-original", self.gateway()["execute_admitted"](self.execution, callback))
        self.store.requeue_claimed_run.assert_not_called()
        self.concurrency.release_execution.assert_called_once()

    def test_dependency_rollback_uses_permit_fence_and_never_run_id(self):
        self.execution.execution_key = "operation_dependency:9"
        self.gateway()["execute_admitted"](self.execution, Mock())
        self.store.requeue_claimed_run.assert_not_called()
        self.rollback.requeue_dependency.assert_called_once_with(
            9, permit_id="original-permit", execution_id="original-execution",
            attempts=2, reason="runtime_execution_paused")
        self.concurrency.release_execution.assert_called_once()

    def registration(self):
        self.job = {"id": 7, "status": "running", "execution_id": "original-execution", "attempt_id": 91}
        self.db = types.SimpleNamespace(get_job=Mock(return_value={"id": 7, "status": "pending"}), _sync_operation_job=Mock())
        def claim(_table, _id, *, changes, guard, guard_params):
            self.assertIn('"status" = %s', guard)
            self.assertIn('"execution_id" = %s', guard)
            self.assertEqual(("running", "original-execution"), guard_params)
            if self.job["status"] == guard_params[0] and self.job["execution_id"] == guard_params[1]:
                self.job.update(changes)
                return True
            return False
        self.records = types.SimpleNamespace(JOBS=object(), claim_row=Mock(side_effect=claim))
        context = types.SimpleNamespace(execution_key="registration_job:7", execution_id="original-execution")
        def admitted(_job):
            self.allowed = False
            return types.SimpleNamespace(context=context)
        scope = {"concurrency": self.concurrency, "db": self.db, "records": self.records,
                 "try_admit_job": Mock(side_effect=admitted)}
        return self.product("core/registration/admission.py", ["run_job", "_rollback_unstarted_job"], scope)

    def test_registration_gate_loss_after_claim_returns_same_job_without_callback(self):
        self.allowed = True
        scope = self.registration()
        callback = Mock()
        scope["run_job"](7, callback)
        callback.assert_not_called()
        self.assertEqual(("pending", None, 91), (self.job["status"], self.job["execution_id"], self.job["attempt_id"]))
        self.concurrency.release_execution.assert_called_once()

    def test_registration_rollback_cannot_replace_new_execution_or_cancel(self):
        for status, execution_id in (("running", "new-execution"), ("cancelled", "original-execution")):
            scope = self.registration()
            self.job.update(status=status, execution_id=execution_id)
            self.assertFalse(scope["_rollback_unstarted_job"](7, "original-execution"))
            self.assertEqual((status, execution_id), (self.job["status"], self.job["execution_id"]))
            self.db._sync_operation_job.assert_not_called()

    def test_registration_closed_gate_never_claims_pending_job(self):
        scope = self.registration()
        scope["run_job"](7, Mock())
        scope["try_admit_job"].assert_not_called()
        self.records.claim_row.assert_not_called()

    def test_registration_started_callback_is_not_rolled_back_when_gate_closes(self):
        scope = self.registration()
        self.allowed = True
        self.concurrency.current_execution.return_value = types.SimpleNamespace(
            execution_key="registration_job:7", execution_id="original-execution")
        def callback():
            self.allowed = False
            return "original-result"
        self.assertEqual("original-result", scope["run_job"](7, callback))
        self.records.claim_row.assert_not_called()
        self.concurrency.release_execution.assert_not_called()

    def test_runtime_recovery_loop_does_not_run_while_gate_closed(self):
        stop = Mock()
        stop.is_set.side_effect = [False, True]
        scope = self.product("core/operations/task_gateway.py", ["_run_dispatch_loop"], {
            "_RUN_DISPATCH_STOP": stop, "_RUN_DISPATCH_WAKE": Mock(), "_RUN_DISPATCH_INTERVAL_SECONDS": 0,
            "_recover_stale_runtime_runs_if_due": Mock(), "dispatch_registered_once": Mock(),
            "logger": Mock()})
        scope["_run_dispatch_loop"]()
        scope["_recover_stale_runtime_runs_if_due"].assert_not_called()
        scope["dispatch_registered_once"].assert_not_called()

    def bulk(self):
        store = types.SimpleNamespace(
            project_pending=Mock(return_value=2), claim_work=Mock(return_value=[]),
            settle_control=Mock(), list_active_batches=Mock(return_value=[]))
        scope = self.product("core/bulk_operations/service.py", ["run_once", "_settle_controls"], {
            "_store": lambda: store, "_OWNER": "original-owner"})
        return scope, store

    def test_bulk_projection_drains_with_valid_owner_while_admission_closed(self):
        scope, store = self.bulk()
        self.assertEqual(2, scope["run_once"]("project"))
        store.project_pending.assert_called_once()
        store.claim_work.assert_not_called()

    def test_bulk_closed_gate_settles_control_without_selection_or_expansion(self):
        scope, store = self.bulk()
        store.claim_work.return_value = [{"id": "original-control", "owner_id": "original-owner", "fence": 3}]
        self.assertEqual(1, scope["run_once"]("selection"))
        store.claim_work.assert_called_once_with("control", "original-owner", limit=1)
        store.settle_control.assert_called_once_with("original-control", owner_id="original-owner", fence=3)
        self.assertEqual(0, scope["run_once"]("expand"))
        store.list_active_batches.assert_not_called()

    def test_bulk_owner_loss_stops_projection_and_control(self):
        self.owner = False
        scope, store = self.bulk()
        self.assertEqual(0, scope["run_once"]("project"))
        self.assertEqual(0, scope["run_once"]("selection"))
        store.project_pending.assert_not_called()
        store.claim_work.assert_not_called()

    def test_dependency_tick_closure_after_claim_does_not_invoke_handoff(self):
        self.allowed = True
        self.execution.execution_key = "operation_dependency:9"
        def claim(**_kw):
            self.allowed = False
            return types.SimpleNamespace(admitted=True, context=self.execution)
        self.concurrency.try_admit_and_claim = claim
        handler = Mock()
        self.store.list_ready_task_dependencies = Mock(return_value=[{"id": 9}])
        scope = self.gateway()
        scope.update(_dependency_handler=lambda: handler, _executor=lambda: types.SimpleNamespace(available_slots=lambda: 1),
                     _DEPENDENCY_BATCH_SIZE=10, Mapping=dict, logger=Mock())
        self.product("core/operations/task_gateway.py", ["_dependency_tick"], scope)
        self.assertEqual(0, scope["_dependency_tick"]())
        handler.assert_not_called()
        self.rollback.requeue_dependency.assert_called_once()

    def test_dependency_rejected_future_returns_claim_and_releases_via_fenced_path(self):
        gateway = types.SimpleNamespace(execute_admitted=Mock(), rollback_admission=Mock())
        pool = types.SimpleNamespace(try_submit=Mock(return_value=None))
        scope = self.product("core/accounts/completion_dependencies.py", ["submit_ready_completion_dependency"], {
            "task_gateway": gateway, "_ACCOUNT_EXECUTOR": pool, "Mapping": dict,
            "logger": Mock()})
        scope["submit_ready_completion_dependency"]({"id": 9, "_execution_context": self.execution})
        gateway.rollback_admission.assert_called_once_with(self.execution, reason="executor_submit_failed")

    def test_dependency_cancelled_future_returns_claim_and_releases_via_fenced_path(self):
        gateway = types.SimpleNamespace(execute_admitted=Mock(), rollback_admission=Mock())
        future = Mock()
        pool = types.SimpleNamespace(try_submit=Mock(return_value=future))
        scope = self.product("core/accounts/completion_dependencies.py", ["submit_ready_completion_dependency"], {
            "task_gateway": gateway, "_ACCOUNT_EXECUTOR": pool, "Mapping": dict,
            "logger": Mock()})
        scope["submit_ready_completion_dependency"]({"id": 9, "_execution_context": self.execution})
        future.add_done_callback.call_args.args[0](types.SimpleNamespace(cancelled=lambda: True))
        gateway.rollback_admission.assert_called_once_with(self.execution, reason="submission_cancelled")

    def test_executor_runtime_status_is_local_and_does_not_construct_pool(self):
        instance = executor_module.AccountOperationExecutor(Mock(side_effect=AssertionError("policy read forbidden")))
        self.assertTrue(hasattr(instance, "runtime_status"))
        instance._accepted, instance._active = 3, 2
        status = instance.runtime_status()
        self.assertEqual((3, 2, 0, None), (status["accepted"], status["active"], status["generation"], status["current_pool_workers"]))
        self.assertIsNone(instance._executor)

    def test_registration_status_reads_existing_references_without_pool_creation(self):
        scope = self.product("core/registration/service.py", ["dispatcher_status", "registration_executor_status"], {
            "_DISPATCH_LOCK": threading.RLock(), "_DISPATCH_THREAD": None,
            "_DISPATCH_STOP": threading.Event(), "_DISPATCHING_JOBS": {7: {}},
            "_executor_lock": threading.RLock(), "_executor": None})
        self.assertEqual({"started": False, "alive": False, "stopping": False, "in_flight": 1}, scope["dispatcher_status"]())
        self.assertEqual(0, scope["registration_executor_status"]()["accepted"])
        pool = types.SimpleNamespace(runtime_status=Mock(return_value={"accepted": 2, "active": 1}))
        scope["_executor"] = pool
        self.assertEqual(2, scope["registration_executor_status"]()["accepted"])
        pool.runtime_status.assert_called_once()

    def test_bulk_stop_retains_alive_references_and_returns_false(self):
        thread = Mock()
        thread.is_alive.return_value = True
        scope = self.product("core/bulk_operations/service.py", ["stop_workers"], {
            "_LOCK": threading.RLock(), "_STOP": threading.Event(), "_WAKE": threading.Event(),
            "_THREADS": {"project": thread}, "threading": threading,
            "time": types.SimpleNamespace(monotonic=Mock(side_effect=[10, 10]))})
        self.assertIs(False, scope["stop_workers"](timeout=0))
        self.assertIs(thread, scope["_THREADS"]["project"])
        thread.join.assert_called_once_with(0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
