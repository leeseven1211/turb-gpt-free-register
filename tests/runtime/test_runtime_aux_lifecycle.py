"""Auxiliary runtime regressions against product modules and offline dependencies.

The Phase 6 auxiliary candidate cases now call the normal product imports. The
fixture patches module state and runtime context, never copies function bodies.
"""
from __future__ import annotations

import logging
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from core.email.email_butler import service_facts, usage_reports
from core.proxy import pool as proxy_pool
from core.runtime.context import RuntimeContext
from core.runtime import process
from core.sms import provider as sms_provider
from core.storage import postgres


MODULES = {
    "core/email/email_butler/usage_reports.py": usage_reports,
    "core/email/email_butler/service_facts.py": service_facts,
    "core/proxy/pool.py": proxy_pool,
    "core/sms/provider.py": sms_provider,
}


class ProductModuleTests(unittest.TestCase):
    def setUp(self):
        for guard in (
            patch.object(postgres, "connect", side_effect=AssertionError("real database forbidden")),
            patch.object(threading, "Thread", side_effect=AssertionError("unexpected worker creation")),
            patch.object(sms_provider, "_http", side_effect=AssertionError("real SMS request forbidden")),
        ):
            guard.start()
            self.addCleanup(guard.stop)

    def product_scope(self, file, names, namespace=None):
        module = MODULES[file]
        for name in names:
            self.assertTrue(callable(getattr(module, name)), name)
        managed = {"allowed": False}
        web = RuntimeContext("web")
        worker = RuntimeContext("worker")
        worker.admission.unblock("startup")
        for guard in (
            patch.object(process, "get_runtime_context", side_effect=lambda: worker if managed["allowed"] else web),
            patch.object(process, "execution_admitted", side_effect=lambda: managed["allowed"]),
            patch.object(process, "execution_owner_valid", side_effect=lambda: managed["allowed"]),
        ):
            guard.start()
            self.addCleanup(guard.stop)
        for name, value in (namespace or {}).items():
            guard = patch.object(module, name, value, create=True)
            guard.start()
            self.addCleanup(guard.stop)
        # Mutations in restart/exit handoff cases target the actual product
        # global, whose original value is restored by the patches above.
        return vars(module), managed

    def product_function(self, file, name, namespace=None):
        scope, managed = self.product_scope(file, [name], namespace)
        return scope[name], managed, scope


class FakeThread:
    def __init__(self, alive=True):
        self.alive = alive
        self.joins = []
        self.name = "fake"
        self.on_join = None
    def is_alive(self):
        return self.alive
    def join(self, timeout=None):
        self.joins.append(timeout)
        if self.on_join:
            self.on_join()


class QueuePathTests(ProductModuleTests):
    def scope(self, path):
        return self.product_scope("core/sms/provider.py", [
            "configure_cancel_queue_path", "_load_cancel_queue_locked", "_save_cancel_queue_locked",
        ], {
            "_CANCEL_QUEUE_LOCK": threading.RLock(),
            "_CANCEL_QUEUE_PATH": Path(path),
            "_CANCEL_QUEUE_INITIALIZED": False,
            "_CANCEL_QUEUE_ERROR": None,
        })[0]

    def test_relative_path_is_rejected_before_any_file_access(self):
        scope = self.scope("/tmp/legacy/sms.json")
        with self.assertRaisesRegex(ValueError, "absolute"):
            scope["configure_cancel_queue_path"]("logs/sms.json")
        self.assertEqual(scope["_CANCEL_QUEUE_PATH"], Path("/tmp/legacy/sms.json"))

    def test_bootstrap_setter_is_absolute_idempotent_and_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder).resolve() / "stable" / "sms_cancel_queue.json"
            scope = self.scope("/tmp/legacy/sms.json")
            scope["configure_cancel_queue_path"](target)
            scope["configure_cancel_queue_path"](target)
            self.assertEqual(scope["_CANCEL_QUEUE_PATH"], target)
            self.assertFalse(target.parent.exists())
            self.assertFalse(scope["_CANCEL_QUEUE_INITIALIZED"])

    def test_first_read_freezes_path_even_when_queue_file_is_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "sms_cancel_queue.json"
            scope = self.scope(target)
            self.assertEqual(scope["_load_cancel_queue_locked"](), [])
            self.assertTrue(scope["_CANCEL_QUEUE_INITIALIZED"])
            scope["configure_cancel_queue_path"](target)
            with self.assertRaisesRegex(RuntimeError, "initialized"):
                scope["configure_cancel_queue_path"](Path(folder) / "other.json")

    def test_first_write_freezes_path(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "sms_cancel_queue.json"
            scope = self.scope(target)
            scope["os"] = __import__("os")
            scope["_save_cancel_queue_locked"]([])
            self.assertTrue(scope["_CANCEL_QUEUE_INITIALIZED"])
            with self.assertRaisesRegex(RuntimeError, "initialized"):
                scope["configure_cancel_queue_path"](Path(folder) / "other.json")

    def test_default_path_is_preserved_until_explicitly_configured(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / "legacy_sms.json"
            original.write_text('{"items":[{"activation_id":"test-order"}]}')
            scope = self.scope(original)
            self.assertEqual(scope["_load_cancel_queue_locked"](), [{"activation_id": "test-order"}])
            self.assertEqual(scope["_CANCEL_QUEUE_PATH"], original)


class StopTests(ProductModuleTests):
    CASES = (
        ("core/email/email_butler/usage_reports.py", "stop_worker", "_worker", "_worker_lock", "_stop"),
        ("core/email/email_butler/service_facts.py", "stop_worker", "_worker", "_lock", "_stop"),
        ("core/sms/provider.py", "stop_cancel_worker", "_CANCEL_WORKER", "_CANCEL_WORKER_LOCK", "_CANCEL_STOP"),
    )
    def scope(self, case, thread):
        file, function, worker, lock, stop = case
        scope, _ = self.product_scope(file, [function], {
            worker: thread, lock: threading.RLock(), stop: threading.Event(),
            "_CANCEL_WAKE_EVENT": threading.Event(),
        })
        return scope

    def test_current_thread_cannot_be_reported_as_stopped(self):
        for case in self.CASES:
            thread = FakeThread()
            scope = self.scope(case, thread)
            with self.subTest(file=case[0]), patch("threading.current_thread", return_value=thread):
                self.assertFalse(scope[case[1]](0))
                self.assertEqual(thread.joins, [])
                self.assertIs(scope[case[2]], thread)

    def test_zero_budget_never_gets_a_minimum_join_delay(self):
        for case in self.CASES:
            thread = FakeThread()
            scope = self.scope(case, thread)
            with self.subTest(file=case[0]):
                self.assertFalse(scope[case[1]](0))
                self.assertEqual(thread.joins, [0.0])
                self.assertIs(scope[case[2]], thread)

    def test_budget_includes_waiting_for_lifecycle_lock(self):
        for case in self.CASES:
            thread = FakeThread()
            scope = self.scope(case, thread)
            with self.subTest(file=case[0]), patch("time.monotonic", side_effect=[10, 10.4, 10.8]):
                self.assertFalse(scope[case[1]](1))
                self.assertAlmostEqual(thread.joins[0], 0.2)

    def test_concurrent_restart_never_reports_stopped(self):
        for case in self.CASES:
            old = FakeThread()
            new = FakeThread()
            scope = self.scope(case, old)
            def restart():
                old.alive = False
                scope[case[2]] = new
            old.on_join = restart
            with self.subTest(file=case[0]):
                self.assertFalse(scope[case[1]](1))
                self.assertIs(scope[case[2]], new)

    def test_proxy_stop_tracks_threads_created_during_wait(self):
        old = FakeThread()
        new = FakeThread()
        threads = [old]
        scope, _ = self.product_scope("core/proxy/pool.py", ["stop"], {
            "_threads": threads, "_lock": threading.RLock(),
            "_stop": threading.Event(), "_wake": threading.Event(),
        })
        def restart():
            old.alive = False
            threads.append(new)
        old.on_join = restart
        self.assertFalse(scope["stop"](1))


class StatusTests(ProductModuleTests):
    def test_email_status_is_local_and_distinguishes_stopping(self):
        for file, lock in (
            ("core/email/email_butler/usage_reports.py", "_worker_lock"),
            ("core/email/email_butler/service_facts.py", "_lock"),
        ):
            stop = threading.Event()
            scope, _ = self.product_scope(file, ["worker_runtime_status"], {
                "_worker": FakeThread(), lock: threading.RLock(), "_stop": stop,
            })
            with self.subTest(file=file):
                before = scope["worker_runtime_status"]()
                self.assertTrue(before["alive"])
                self.assertEqual(before["state"], "running")
                stop.set()
                after = scope["worker_runtime_status"]()
                self.assertTrue(after["stopping"])
                self.assertEqual(after["state"], "stopping")

    def test_proxy_status_is_local_without_inventory_queries(self):
        scope, _ = self.product_scope("core/proxy/pool.py", ["worker_status"], {
            "_threads": [FakeThread()], "_lock": threading.RLock(),
            "_stop": threading.Event(),
        })
        result = scope["worker_status"]()
        self.assertTrue(result["alive"])
        self.assertEqual(result["workers_alive"], 1)

    def test_sms_queue_read_error_is_unhealthy_not_idle(self):
        scope, _ = self.product_scope("core/sms/provider.py", ["cancel_worker_status"], {
            "_CANCEL_WORKER": None, "_CANCEL_WORKER_LOCK": threading.RLock(),
            "_CANCEL_QUEUE_LOCK": threading.RLock(), "_CANCEL_STOP": threading.Event(),
            "_load_cancel_queue_locked": lambda: [],
            "_CANCEL_QUEUE_ERROR": "sms_cancel_queue_unavailable",
        })
        result = scope["cancel_worker_status"]()
        self.assertEqual(result["state"], "error")
        self.assertFalse(result["healthy"])


class SmsExitHandoffTests(ProductModuleTests):
    def scope(self, thread, items):
        return self.product_scope("core/sms/provider.py", [
            "_cancel_worker_loop", "start_cancel_worker", "stop_cancel_worker",
        ], {
            "_CANCEL_WORKER": thread, "_CANCEL_WORKER_LOCK": threading.RLock(),
            "_CANCEL_QUEUE_LOCK": threading.RLock(), "_CANCEL_STOP": threading.Event(),
            "_CANCEL_WAKE_EVENT": threading.Event(), "_CANCEL_EXITING": False,
            "_CANCEL_QUEUE_INITIALIZED": False, "_CANCEL_QUEUE_ERROR": None,
            "_load_cancel_queue_locked": lambda: items,
        })

    def test_empty_queue_exits_without_clearing_a_live_thread_reference(self):
        worker = FakeThread()
        scope, managed = self.scope(worker, [])
        managed["allowed"] = True
        scope["_cancel_worker_loop"]()
        self.assertIs(scope["_CANCEL_WORKER"], worker)
        self.assertTrue(scope["_CANCEL_EXITING"])
        self.assertFalse(scope["stop_cancel_worker"](0))

    def test_enqueue_start_waits_for_exiting_tail_before_replacing_worker(self):
        old = FakeThread()
        scope, managed = self.scope(old, [])
        managed["allowed"] = True
        scope["_CANCEL_EXITING"] = True
        new = FakeThread(alive=False)
        order = []
        def leave():
            order.append("old exited")
            old.alive = False
        old.on_join = leave
        def create(**kwargs):
            order.append("new created")
            self.assertFalse(old.is_alive())
            return new
        new.start = lambda: setattr(new, "alive", True)
        with patch("threading.Thread", side_effect=create):
            scope["start_cancel_worker"]()
        self.assertEqual(order, ["old exited", "new created"])
        self.assertIs(scope["_CANCEL_WORKER"], new)
        self.assertFalse(scope["_CANCEL_EXITING"])
        self.assertTrue(scope["_CANCEL_QUEUE_INITIALIZED"])

    def test_busy_worker_is_woken_and_never_replaced(self):
        old = FakeThread()
        scope, managed = self.scope(old, [])
        managed["allowed"] = True
        with patch("threading.Thread", side_effect=AssertionError("duplicate worker")):
            scope["start_cancel_worker"]()
        self.assertIs(scope["_CANCEL_WORKER"], old)
        self.assertEqual(old.joins, [])
        self.assertTrue(scope["_CANCEL_WAKE_EVENT"].is_set())

    def test_web_cannot_initialize_queue_or_create_worker(self):
        scope, _ = self.scope(None, [])
        with patch("threading.Thread", side_effect=AssertionError("web worker")):
            scope["start_cancel_worker"]()
        self.assertIsNone(scope["_CANCEL_WORKER"])
        self.assertFalse(scope["_CANCEL_QUEUE_INITIALIZED"])


class WebDiagnosticTests(ProductModuleTests):
    def test_proxy_diagnostic_fetches_and_releases_without_pool_start(self):
        from flask import Flask
        from core.proxy import provider, sources, supply
        from webui.routes.integrations import create_integrations_blueprint

        calls = []
        lease = types.SimpleNamespace(public_dict=lambda: {"exit_ip": "192.0.2.1"})
        source = types.SimpleNamespace(name="fake", label="Fake", options=lambda **kw: kw)

        def candidates(*args, **kwargs):
            calls.append(("fetch", kwargs["count"]))
            yield lease

        app = Flask("runtime-aux-diagnostic")
        app.register_blueprint(create_integrations_blueprint(
            types.SimpleNamespace(logger=logging.getLogger("runtime-aux-diagnostic"))))
        with patch.object(provider, "release_proxy", side_effect=lambda value, **kw: calls.append(("release", kw["reason"]))), \
                patch.object(sources, "get_source", return_value=source), \
                patch.object(supply, "fetch_candidates", side_effect=candidates), \
                patch.object(proxy_pool, "start", side_effect=AssertionError("diagnostic must not start pool")):
            response = app.test_client().post("/api/proxy-provider/test", json={"provider": "fake"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        self.assertEqual(calls, [("fetch", 1), ("release", "webui_test")])


class AuxiliaryBoundaryTests(ProductModuleTests):
    def test_email_web_start_and_dispatch_are_side_effect_free(self):
        for file in ("core/email/email_butler/usage_reports.py", "core/email/email_butler/service_facts.py"):
            for name in ("start_worker", "dispatch_once"):
                with self.subTest(file=file, name=name):
                    function, _, _ = self.product_function(file, name)
                    self.assertFalse(function())

    def test_email_stop_truth_retains_live_thread(self):
        for file, lock in (
            ("core/email/email_butler/usage_reports.py", "_worker_lock"),
            ("core/email/email_butler/service_facts.py", "_lock"),
        ):
            for alive in (True, False):
                with self.subTest(file=file, alive=alive):
                    thread = FakeThread(alive)
                    function, _, scope = self.product_function(file, "stop_worker", {
                        "_worker": thread, lock: threading.Lock(), "_stop": threading.Event(),
                    })
                    self.assertEqual(function(0), not alive)
                    self.assertEqual(scope["_worker"], thread if alive else None)

    def test_proxy_stop_has_one_budget_and_actual_truth(self):
        thread = FakeThread(True)
        stop = threading.Event()
        function, _, _ = self.product_function("core/proxy/pool.py", "stop", {
            "_threads": [thread], "_lock": threading.RLock(),
            "_stop": stop, "_wake": threading.Event(),
        })
        self.assertFalse(function(0))
        self.assertTrue(stop.is_set())
        self.assertEqual(thread.joins, [0.0])

    def test_proxy_web_start_does_not_read_configuration(self):
        function, _, _ = self.product_function("core/proxy/pool.py", "start")
        self.assertIsNone(function())

    def test_proxy_web_acquire_fails_before_read_or_lease(self):
        function, _, _ = self.product_function("core/proxy/pool.py", "acquire")
        with self.assertRaisesRegex(RuntimeError, "web_execution_forbidden"):
            function()

    def test_sms_web_start_or_enqueue_cannot_spawn_or_touch_file(self):
        function, _, _ = self.product_function("core/sms/provider.py", "start_cancel_worker")
        self.assertIsNone(function())
        function, _, _ = self.product_function("core/sms/provider.py", "_enqueue_grizzly_cancel")
        with self.assertRaisesRegex(RuntimeError, "web_execution_forbidden"):
            function("fake-order")

    def test_sms_idle_is_healthy_but_pending_without_worker_is_not(self):
        function, _, scope = self.product_function("core/sms/provider.py", "cancel_worker_status", {
            "_CANCEL_WORKER": None, "_CANCEL_WORKER_LOCK": threading.Lock(),
            "_CANCEL_QUEUE_LOCK": threading.RLock(), "_CANCEL_STOP": threading.Event(),
            "_CANCEL_QUEUE_ERROR": None, "_load_cancel_queue_locked": lambda: [],
        })
        self.assertEqual(function()["state"], "idle")
        self.assertTrue(function()["healthy"])
        scope["_load_cancel_queue_locked"] = lambda: [{}]
        self.assertFalse(function()["healthy"])

    def test_sms_stop_timeout_retains_worker_and_reports_false(self):
        thread = FakeThread(True)
        function, _, scope = self.product_function("core/sms/provider.py", "stop_cancel_worker", {
            "_CANCEL_WORKER": thread, "_CANCEL_WORKER_LOCK": threading.Lock(),
            "_CANCEL_STOP": threading.Event(), "_CANCEL_WAKE_EVENT": threading.Event(),
        })
        self.assertFalse(function(0))
        self.assertIs(scope["_CANCEL_WORKER"], thread)


if __name__ == "__main__":
    unittest.main(verbosity=2)
