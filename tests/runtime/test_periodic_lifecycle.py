"""Periodic scheduling and lifecycle contracts; no real DB or threads."""
from __future__ import annotations

import importlib
import json
import threading
import types
import unittest
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from core.runtime import periodic, scheduler_state as scheduler, process
from core.storage.operations import projection

CONTEXT = None
ADMITTED = False
load = importlib.import_module


class RuntimeContextTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self._runtime_patches = ExitStack()
        self.addCleanup(self._runtime_patches.close)
        self._runtime_patches.enter_context(patch.object(
            process, "get_runtime_context", lambda: CONTEXT))
        self._runtime_patches.enter_context(patch.object(
            process, "execution_admitted", lambda: ADMITTED))
        self._runtime_patches.enter_context(patch.object(scheduler.logger, "disabled", True))

    def tearDown(self):
        global CONTEXT, ADMITTED
        CONTEXT, ADMITTED = None, False
        super().tearDown()


class ScriptedStop:
    def __init__(self, on_wait=None):
        self.stopped = False
        self.waits = []
        self.on_wait = on_wait

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, seconds):
        self.waits.append(seconds)
        if self.on_wait:
            self.on_wait(self, len(self.waits))
        return self.stopped


class FakeThread:
    def __init__(self, *, target=None, name="fake", daemon=None, args=(), kwargs=None):
        self.target, self.name, self.args = target, name, args
        self.kwargs = kwargs or {}
        self.alive = False
        self.join_calls = []
        self.exit_on_join = False

    def start(self):
        self.alive = True

    def is_alive(self):
        return self.alive

    def join(self, timeout):
        self.join_calls.append(timeout)
        if self.exit_on_join:
            self.alive = False


class FakeDatabase:
    """Checks our SQL protocol; root must separately verify real PG semantics."""
    def __init__(self):
        self.entries = {"other": {"last_run_at": "2026-01-01T00:00:00", "run_count": 9}}
        self.calls = []
        self.transactions = []
        self.active = None
        self.row = None

    @contextmanager
    def connect(self):
        token = object()
        assert self.active is None
        self.active = token
        self.transactions.append(token)
        try:
            yield self
        finally:
            self.active = None

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, args=()):
        normalized = " ".join(sql.split())
        self.calls.append((self.active, normalized, args))
        if "pg_advisory_xact_lock" in normalized:
            self.row = (None,)
        elif normalized.startswith("SELECT"):
            self.row = (self.entries.get(args[0]), "object")
        elif normalized.startswith("INSERT"):
            pass
        elif "jsonb_set" in normalized:
            self.entries[args[0][0]] = json.loads(args[1])
        elif normalized.startswith("UPDATE") and "payload - " in normalized:
            self.entries.pop(args[0], None)
        else:
            raise AssertionError(f"Unexpected SQL: {normalized}")

    def fetchone(self):
        return self.row


class SchedulerStorageTests(RuntimeContextTestCase):
    def test_storage_read_failure_is_unknown_not_a_fresh_task(self):
        with patch.object(scheduler.postgres_store, "load_collection", side_effect=OSError("unavailable")), \
             patch.object(scheduler.postgres_store, "ensure_schema", side_effect=OSError("unavailable")):
            with self.assertRaises(OSError):
                scheduler.last_run_at("task")

    def test_mark_only_changes_requested_task_and_locks_same_transaction(self):
        database = FakeDatabase()
        with patch.object(scheduler.postgres_store, "ensure_schema"), \
             patch.object(scheduler.postgres_store, "connect", database.connect), \
             patch.object(scheduler.postgres_store, "load_collection", return_value=(True, database.entries.copy())), \
             patch.object(scheduler.postgres_store, "save_collection") as legacy_save:
            scheduler.mark_ran("target")
            scheduler.mark_ran("target")
        self.assertEqual(database.entries["other"]["run_count"], 9)
        self.assertEqual(database.entries.get("target", {}).get("run_count"), 2)
        legacy_save.assert_not_called()
        for transaction in database.transactions:
            calls = [call for call in database.calls if call[0] is transaction]
            self.assertIn("pg_advisory_xact_lock", calls[0][1])
            self.assertTrue(any("jsonb_set" in call[1] for call in calls))
        self.assertEqual(database.calls[0][2], database.calls[4][2])

    def test_reset_and_mark_share_task_lock_and_preserve_other_tasks(self):
        database = FakeDatabase()
        with patch.object(scheduler.postgres_store, "ensure_schema"), \
             patch.object(scheduler.postgres_store, "connect", database.connect), \
             patch.object(scheduler.postgres_store, "load_collection", return_value=(True, database.entries.copy())), \
             patch.object(scheduler.postgres_store, "save_collection"):
            scheduler.mark_ran("target")
            scheduler.reset("target")
        self.assertNotIn("target", database.entries)
        self.assertEqual(database.entries["other"]["run_count"], 9)
        locks = [call for call in database.calls if "pg_advisory_xact_lock" in call[1]]
        self.assertEqual(len(locks), 2)
        self.assertEqual(locks[0][2], locks[1][2])

    def test_describe_unknown_state_does_not_invent_next_run(self):
        with patch.object(scheduler, "last_run_at", side_effect=OSError("unavailable")):
            try:
                result = scheduler.describe("task", 3600)
            except OSError:
                self.fail("describe must expose unavailable state without inventing a due time")
        self.assertIsNone(result["last_run_at"])
        self.assertIsNone(result["next_run_at"])
        self.assertIsNone(result["seconds_until_due"])
        self.assertFalse(result["state_available"])

    def test_malformed_timestamp_does_not_become_due(self):
        database = FakeDatabase()
        database.entries["target"] = {"last_run_at": "broken", "run_count": 4}
        with patch.object(scheduler.postgres_store, "ensure_schema"), \
             patch.object(scheduler.postgres_store, "connect", database.connect), \
             patch.object(scheduler.postgres_store, "load_collection", return_value=(True, database.entries)):
            with self.assertRaises(ValueError):
                scheduler.seconds_until_due("target", 3600)

    def test_lock_namespace_separates_tasks_and_schemas(self):
        self.assertTrue(callable(getattr(scheduler, "_lock_key", None)))
        with patch.object(scheduler.postgres_store, "schema_name", return_value="test_a"):
            first = scheduler._lock_key("target")
            self.assertEqual(first, scheduler._lock_key("target"))
            self.assertNotEqual(first, scheduler._lock_key("other"))
        with patch.object(scheduler.postgres_store, "schema_name", return_value="test_b"):
            self.assertNotEqual(first, scheduler._lock_key("target"))

    def test_mark_preserves_existing_task_metadata(self):
        database = FakeDatabase()
        database.entries["target"] = {"run_count": 3, "last_run_at": "2026-01-01T00:00:00",
                                      "custom_metadata": "keep"}
        with patch.object(scheduler.postgres_store, "ensure_schema"), \
             patch.object(scheduler.postgres_store, "connect", database.connect), \
             patch.object(scheduler.postgres_store, "load_collection", return_value=(True, database.entries)), \
             patch.object(scheduler.postgres_store, "save_collection"):
            scheduler.mark_ran("target")
        self.assertEqual(database.entries["target"]["run_count"], 4)
        self.assertEqual(database.entries["target"]["custom_metadata"], "keep")

    def test_mark_storage_failure_is_not_swallowed(self):
        with patch.object(scheduler.postgres_store, "ensure_schema", side_effect=OSError("unavailable")), \
             patch.object(scheduler.postgres_store, "load_collection", side_effect=OSError("unavailable")), \
             patch.object(scheduler.postgres_store, "save_collection", side_effect=OSError("unavailable")):
            with self.assertRaises(OSError):
                scheduler.mark_ran("target")


class SchedulerLoopTests(RuntimeContextTestCase):
    def tearDown(self):
        global CONTEXT, ADMITTED
        CONTEXT, ADMITTED = None, False

    def run_loop(self, work, stop, enabled=lambda: True):
        scheduler.run_periodic(task="task", label="Test", work=work, enabled=enabled,
                               interval_seconds=lambda: 3600, initial_delay_seconds=0, stop=stop)

    def test_managed_closed_gate_never_reads_schedule_or_runs_work(self):
        global CONTEXT, ADMITTED
        CONTEXT, ADMITTED = types.SimpleNamespace(executes=True), False
        stop = ScriptedStop(lambda event, n: event.set() if n >= 2 else None)
        calls = []
        with patch.object(scheduler, "seconds_until_due", side_effect=lambda *a: 3600 if stop.is_set() else 0) as read, \
             patch.object(scheduler, "mark_ran"):
            self.run_loop(lambda: (calls.append("ran"), stop.set()), stop)
        self.assertEqual(calls, [])
        read.assert_not_called()

    def test_gate_closing_during_schedule_read_prevents_cycle(self):
        global CONTEXT, ADMITTED
        CONTEXT, ADMITTED = types.SimpleNamespace(executes=True), True
        stop = ScriptedStop(lambda event, n: event.set() if n >= 2 else None)
        calls = []
        def due(*args):
            global ADMITTED
            ADMITTED = False
            return 3600 if stop.is_set() else 0
        with patch.object(scheduler, "seconds_until_due", side_effect=due), \
             patch.object(scheduler, "mark_ran"):
            self.run_loop(lambda: (calls.append("ran"), stop.set()), stop)
        self.assertEqual(calls, [])

    def test_storage_read_failure_backs_off_without_work(self):
        stop = ScriptedStop(lambda event, n: event.set() if n >= 2 else None)
        calls = []
        with patch.object(scheduler, "seconds_until_due", side_effect=OSError("unavailable")), \
             patch.object(scheduler, "mark_ran") as mark:
            self.run_loop(lambda: calls.append("ran"), stop)
        self.assertEqual(calls, [])
        mark.assert_not_called()
        self.assertEqual(stop.waits, [0.0, 60.0])

    def test_work_failure_still_records_attempt_even_when_stop_requested(self):
        stop = ScriptedStop()
        def work():
            stop.set()
            raise RuntimeError("expected")
        with patch.object(scheduler, "seconds_until_due", side_effect=lambda *a: 3600 if stop.is_set() else 0), \
             patch.object(scheduler, "mark_ran") as mark:
            self.run_loop(work, stop)
        mark.assert_called_once_with("task")

    def test_write_failure_does_not_repeat_cycle_after_sixty_seconds(self):
        stop = ScriptedStop(lambda event, n: event.set() if n >= 4 else None)
        calls = []
        with patch.object(scheduler, "seconds_until_due", return_value=0), \
             patch.object(scheduler, "mark_ran", side_effect=OSError("unavailable")), \
             patch("time.monotonic", side_effect=[100.0] * 30):
            self.run_loop(lambda: calls.append("ran"), stop)
        self.assertEqual(calls, ["ran"])

    def test_unmanaged_legacy_call_still_runs(self):
        stop = ScriptedStop()
        calls = []
        def work():
            calls.append("ran")
            stop.set()
        with patch.object(scheduler, "seconds_until_due", side_effect=lambda *a: 3600 if stop.is_set() else 0), \
             patch.object(scheduler, "mark_ran"):
            self.run_loop(work, stop)
        self.assertEqual(calls, ["ran"])

    def test_disabled_service_never_reads_schedule(self):
        stop = ScriptedStop(lambda event, n: event.set() if n >= 2 else None)
        calls = []
        with patch.object(scheduler, "seconds_until_due") as read:
            self.run_loop(lambda: calls.append("ran"), stop, enabled=lambda: False)
        self.assertEqual(calls, [])
        read.assert_not_called()

    def test_pending_completion_write_recovers_without_repeating_work(self):
        stop = ScriptedStop(lambda event, n: event.set() if n >= 3 else None)
        calls = []
        with patch.object(scheduler, "seconds_until_due", return_value=0), \
             patch.object(scheduler, "mark_ran", side_effect=[OSError("unavailable"), None]) as mark, \
             patch("time.monotonic", return_value=100):
            self.run_loop(lambda: calls.append("ran"), stop)
        self.assertEqual(calls, ["ran"])
        self.assertEqual(mark.call_count, 2)


class ProjectionStopTests(RuntimeContextTestCase):
    def test_stop_timeout_keeps_thread_reference_and_returns_false(self):
        worker = FakeThread()
        worker.alive = True
        with patch.object(projection, "_PROJECTION_WORKER", worker):
            self.assertFalse(projection.stop_projection_worker(timeout=0))
            self.assertIs(projection._PROJECTION_WORKER, worker)
            self.assertTrue(projection.projection_worker_status()["alive"])
            self.assertEqual(worker.join_calls, [0.0])

    def test_already_stopped_is_success(self):
        with patch.object(projection, "_PROJECTION_WORKER", None):
            self.assertTrue(projection.stop_projection_worker(timeout=0))

    def test_actual_thread_exit_clears_reference(self):
        worker = FakeThread()
        worker.alive = True
        worker.exit_on_join = True
        with patch.object(projection, "_PROJECTION_WORKER", worker):
            self.assertTrue(projection.stop_projection_worker(timeout=1))
            self.assertIsNone(projection._PROJECTION_WORKER)

    def test_current_thread_never_joins_itself(self):
        worker = FakeThread()
        worker.alive = True
        with patch.object(projection, "_PROJECTION_WORKER", worker), \
             patch.object(projection.threading, "current_thread", return_value=worker):
            self.assertFalse(projection.stop_projection_worker(timeout=1))
        self.assertEqual(worker.join_calls, [])

    def test_join_budget_includes_time_waiting_for_lifecycle_lock(self):
        worker = FakeThread()
        worker.alive = True
        with patch.object(projection, "_PROJECTION_WORKER", worker), \
             patch("time.monotonic", side_effect=[10.0, 10.0, 10.8]):
            self.assertFalse(projection.stop_projection_worker(timeout=1))
        self.assertAlmostEqual(worker.join_calls[0], 0.2)


class PeriodicLifecycleTests(RuntimeContextTestCase):
    def setUp(self):
        super().setUp()
        self.assertIsNotNone(periodic, "periodic lifecycle owner must exist")
        self.owner = periodic.PeriodicThread("test-producer")

    def tearDown(self):
        global CONTEXT, ADMITTED
        CONTEXT, ADMITTED = None, False

    def test_disabled_live_thread_is_not_reported_as_running(self):
        with patch("threading.Thread", FakeThread):
            self.owner.start(lambda: None)
        status = self.owner.status(enabled=False)
        self.assertTrue(status["alive"])
        self.assertFalse(status["running"])
        self.assertEqual(status["state"], "disabled")

    def test_idle_and_working_are_distinct(self):
        with patch("threading.Thread", FakeThread):
            self.owner.start(lambda: None)
        self.assertEqual(self.owner.status(enabled=True)["state"], "idle")
        self.owner.work_started()
        self.assertEqual(self.owner.status(enabled=True)["state"], "running")
        self.owner.work_finished()
        self.assertEqual(self.owner.status(enabled=True)["state"], "idle")

    def test_unexpected_thread_exit_reports_stopped_and_can_restart(self):
        with patch("threading.Thread", FakeThread):
            self.owner.start(lambda: None)
            old = self.owner._thread
            old.alive = False
            self.assertEqual(self.owner.status(enabled=True)["state"], "stopped")
            self.assertTrue(self.owner.start(lambda: None))
        self.assertIsNot(old, self.owner._thread)

    def test_failed_thread_start_can_retry(self):
        class FailsOnce(FakeThread):
            def start(self):
                raise RuntimeError("cannot start")
        with patch("threading.Thread", FailsOnce):
            with self.assertRaises(RuntimeError):
                self.owner.start(lambda: None)
        self.assertFalse(self.owner.status(enabled=True)["started"])
        with patch("threading.Thread", FakeThread):
            self.assertTrue(self.owner.start(lambda: None))

    def test_web_mode_never_creates_thread_or_registers_handlers(self):
        global CONTEXT
        CONTEXT = types.SimpleNamespace(executes=False)
        calls = []
        with patch("threading.Thread", side_effect=AssertionError("web thread started")):
            self.assertFalse(self.owner.start(lambda: None, before_start=lambda: calls.append("register")))
        self.assertEqual(calls, [])

    def test_managed_startup_can_create_idle_thread_but_cannot_execute(self):
        global CONTEXT, ADMITTED
        CONTEXT, ADMITTED = types.SimpleNamespace(executes=True), False
        with patch("threading.Thread", FakeThread):
            self.assertTrue(self.owner.start(lambda: None))
        self.assertEqual(self.owner.status(enabled=True)["state"], "blocked")

    def test_stop_timeout_keeps_stop_event_and_prevents_duplicate_thread(self):
        with patch("threading.Thread", FakeThread):
            self.owner.start(lambda: None)
            original = self.owner._thread
            self.assertFalse(self.owner.stop(0))
            self.assertFalse(self.owner.start(lambda: None))
        self.assertIs(self.owner._thread, original)
        self.assertTrue(self.owner.stop_event.is_set())
        self.assertEqual(self.owner.status(enabled=True)["state"], "stopping")

    def test_stop_current_thread_preserves_reference(self):
        with patch("threading.Thread", FakeThread):
            self.owner.start(lambda: None)
        with patch("threading.current_thread", return_value=self.owner._thread):
            self.assertFalse(self.owner.stop(0))
        self.assertIsNotNone(self.owner._thread)

    def test_already_stopped_is_idempotent_success(self):
        self.assertTrue(self.owner.stop(0))
        self.assertTrue(self.owner.stop(0))

    def test_stop_cannot_report_success_if_concurrent_restart_occurs(self):
        with patch("threading.Thread", FakeThread):
            self.owner.start(lambda: None)
            original = self.owner._thread
            def join(timeout):
                original.alive = False
                self.assertTrue(self.owner.start(lambda: None))
            original.join = join
            self.assertFalse(self.owner.stop(1))
        self.assertTrue(self.owner.status(enabled=True)["alive"])


CASES = (
    ("core.accounts.token_refresh", "start_periodic_refresher", "stop_periodic_refresher"),
    ("core.codex.token_refresh_service", "start_periodic_refresher", "stop_periodic_refresher"),
    ("core.accounts.deactivation.mail_scan", "start_periodic_scanner", "stop_periodic_scanner"),
    ("core.accounts.auth_context_cleanup", "start_periodic_cleanup", "stop_periodic_cleanup"),
    ("core.operations.retention", "start_periodic_cleanup", "stop_periodic_cleanup"),
    ("core.integrations.sub2api.jobs", "start_periodic_sync", "stop_periodic_sync"),
    ("core.integrations.sub2api.monitor", "start_periodic_monitor", "stop_periodic_monitor"),
)


class PeriodicModuleTests(RuntimeContextTestCase):
    def test_monitor_start_failure_returns_false_and_logs_the_original_failure(self):
        service = load("core.integrations.sub2api.monitor")
        with patch.object(service._SCHEDULER, "start", side_effect=RuntimeError("synthetic_start_failure")):
            with self.assertLogs("core.integrations.sub2api.monitor", level="ERROR") as logged:
                self.assertFalse(service.start_periodic_monitor())
        self.assertIn("synthetic_start_failure", "\n".join(logged.output))

    def test_all_periodic_modules_expose_truthful_bounded_lifecycle(self):
        global CONTEXT, ADMITTED
        CONTEXT, ADMITTED = types.SimpleNamespace(executes=True), False
        try:
            for module_name, start_name, stop_name in CASES:
                with self.subTest(module=module_name):
                    service = load(module_name)
                    self.assertTrue(callable(getattr(service, stop_name, None)),
                                    "a real bounded stop hook must exist")
                    self.assertTrue(callable(getattr(service, "scheduler_status", None)))
                    with ExitStack() as stack:
                        stack.enter_context(patch.object(
                            service, "_SCHEDULER", periodic.PeriodicThread(service._SCHEDULER.name)))
                        stack.enter_context(patch("threading.Thread", FakeThread))
                        for register in ("_register_worker", "register_handler"):
                            if hasattr(service, register):
                                stack.enter_context(patch.object(service, register))
                        stack.enter_context(patch("core.operations.task_gateway.register_operation_handler"))
                        self.assertTrue(getattr(service, start_name)())
                        self.assertFalse(getattr(service, start_name)())
                        self.assertTrue(service.scheduler_status()["alive"])
                        self.assertFalse(getattr(service, stop_name)(timeout=0))
                        self.assertTrue(service.scheduler_status()["alive"])
                        self.assertTrue(service.scheduler_status()["stopping"])
                        self.assertFalse(getattr(service, start_name)())
                        service._SCHEDULER._thread.exit_on_join = True
                        self.assertTrue(getattr(service, stop_name)(timeout=1))
                        self.assertFalse(service.scheduler_status()["alive"])
        finally:
            CONTEXT, ADMITTED = None, False

    def test_managed_startup_has_no_synchronous_cleanup_or_enqueue(self):
        global CONTEXT, ADMITTED
        CONTEXT, ADMITTED = types.SimpleNamespace(executes=True), False
        try:
            for module_name, start_name, work_name in (
                ("core.accounts.auth_context_cleanup", "start_periodic_cleanup", "cleanup_once"),
                ("core.integrations.sub2api.jobs", "start_periodic_sync", "enqueue_due"),
            ):
                with self.subTest(module=module_name):
                    service = load(module_name)
                    with ExitStack() as stack:
                        stack.enter_context(patch.object(
                            service, "_SCHEDULER", periodic.PeriodicThread(service._SCHEDULER.name)))
                        stack.enter_context(patch("threading.Thread", FakeThread))
                        stack.enter_context(patch("core.operations.task_gateway.register_operation_handler"))
                        work = stack.enter_context(patch.object(service, work_name))
                        self.assertTrue(getattr(service, start_name)())
                        work.assert_not_called()
        finally:
            CONTEXT, ADMITTED = None, False


if __name__ == "__main__":
    unittest.main(verbosity=2)
