"""Exercise entrypoint resource boundaries without importing product I/O."""
from __future__ import annotations

import argparse
import ast
import logging
import os
from pathlib import Path
import signal
import sys
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger("entrypoint-cleanup-test")
LOGGER.addHandler(logging.NullHandler())
LOGGER.propagate = False


def _entrypoint(relative, namespace):
    """Run the saved main body while replacing its external process resources."""
    path = ROOT / relative
    tree = ast.parse(path.read_text())
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    values = {"__file__": str(path), "argparse": argparse, "Path": Path, "time": time, **namespace}
    exec(compile(ast.Module(body=[main], type_ignores=[]), str(path), "exec"), values)
    return values["main"]


def _module(name, **values):
    module = ModuleType(name)
    module.__dict__.update(values)
    return module


class StartupFailure(RuntimeError):
    pass


class WebEntrypointCleanupTests(unittest.TestCase):
    def _run_web(self, stage=None, *, stop_result=True, stop_error=None, run_error=None,
                 interrupt_start=False):
        state = SimpleNamespace(port_locked=False, installed=False, stop_attempted=False,
                                ran=False, signal_handler=None)
        failure = StartupFailure(stage or "unused")

        def fail_at(name):
            if stage == name:
                raise failure

        def acquire(_port):
            state.port_locked = True
            return state

        def release(_handle):
            state.port_locked = False

        def install(*_args, **_kwargs):
            state.installed = True
            fail_at("install")

        def stop(*, timeout):
            self.assertEqual(timeout, 60.0)
            state.stop_attempted = True
            if stop_error:
                raise stop_error
            state.installed = False
            return stop_result

        def run(**_kwargs):
            state.ran = True
            if run_error:
                raise run_error

        def create_app(**_kwargs):
            fail_at("app")
            return SimpleNamespace(run=run)

        def start(*_args):
            fail_at("start")
            if interrupt_start:
                if state.signal_handler is None:
                    raise StartupFailure("SIGTERM would terminate before cleanup")
                state.signal_handler(signal.SIGTERM, None)

        def register_signal(_signum, handler):
            fail_at("signal")
            state.signal_handler = handler

        bootstrap = SimpleNamespace(mode="combined", prepare_log_environment=lambda: None)
        modules = {
            "config": _module("config"),
            "config.env_loader": _module("config.env_loader", ensure_loaded=lambda: None),
            "config.deployment": _module("config.deployment", browser_enabled=lambda: True),
            "core": _module("core"),
            "core.runtime": _module("core.runtime"),
            "core.runtime.bootstrap": _module("core.runtime.bootstrap",
                RuntimeBootstrap=SimpleNamespace(from_environment=lambda **_kwargs: bootstrap)),
            "core.runtime.assembly": _module("core.runtime.assembly", install=install),
            "core.runtime.process": _module("core.runtime.process",
                start_runtime=start, stop_runtime=stop),
            "core.storage": _module("core.storage",
                postgres=SimpleNamespace(require_ready=lambda: fail_at("db"))),
            "webui": _module("webui"),
            "webui.app": _module("webui.app", create_app=create_app),
            "webui.auth": _module("webui.auth", is_generated_code=lambda: fail_at("auth")),
        }
        local_signal = SimpleNamespace(SIGTERM=signal.SIGTERM,
            signal=register_signal)
        main = _entrypoint("web.py", {
            "logging": SimpleNamespace(getLogger=lambda _name: LOGGER),
            "os": os, "signal": local_signal,
            "_setup_logging": lambda _verbose: None,
            "_acquire_single_instance": acquire, "_release_single_instance": release,
        })
        with patch.dict(sys.modules, modules), patch.object(sys, "argv", ["web.py"]):
            try:
                main()
            except BaseException as exc:
                return state, failure, exc
        return state, failure, None

    def test_database_failure_releases_the_web_port_lock(self):
        state, failure, error = self._run_web("db")
        self.assertIs(error, failure)
        self.assertFalse(state.port_locked)
        self.assertFalse(state.installed)

    def test_partial_install_and_startup_failures_stop_installed_resources(self):
        for stage in ("install", "app", "start", "auth", "signal"):
            with self.subTest(stage=stage):
                state, failure, error = self._run_web(stage)
                self.assertIs(error, failure)
                self.assertFalse(state.port_locked)
                self.assertFalse(state.installed)
                self.assertEqual(state.stop_attempted, stage != 'signal')
                self.assertFalse(state.ran)

    def test_cleanup_exception_keeps_the_original_startup_failure(self):
        state, failure, error = self._run_web("start", stop_error=RuntimeError("cleanup"))
        self.assertIs(error, failure)
        self.assertFalse(state.port_locked)
        self.assertTrue(state.stop_attempted)

    def test_incomplete_cleanup_keeps_the_original_startup_failure(self):
        state, failure, error = self._run_web("start", stop_result=False)
        self.assertIs(error, failure)
        self.assertFalse(state.port_locked)
        self.assertTrue(state.stop_attempted)

    def test_listener_failure_preserves_its_nonzero_exit(self):
        expected = SystemExit(1)
        state, _failure, error = self._run_web(run_error=expected)
        self.assertIs(error, expected)
        self.assertFalse(state.port_locked)
        self.assertFalse(state.installed)

    def test_startup_signal_uses_the_same_cleanup_path(self):
        state, _failure, error = self._run_web(interrupt_start=True)
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 0)
        self.assertFalse(state.port_locked)
        self.assertFalse(state.installed)
        self.assertTrue(state.stop_attempted)
        self.assertFalse(state.ran)

    def test_normal_shutdown_reports_an_incomplete_drain(self):
        state, _failure, error = self._run_web(stop_result=False)
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 3)
        self.assertFalse(state.port_locked)
        self.assertTrue(state.stop_attempted)


class CodexCliOwnerTests(unittest.TestCase):
    def _run_cli(self, *, owner_error=None):
        state = SimpleNamespace(owner_checked=False, submitted=False)

        def require_owner():
            state.owner_checked = True
            if owner_error:
                raise owner_error

        def submit(email, *, trigger):
            self.assertTrue(state.owner_checked, "OAuth execution submitted without its standalone owner")
            self.assertEqual((email, trigger), ("fixture@example.test", "cli"))
            state.submitted = True
            return {"accepted": True, "task_id": 1, "run_id": 2}

        main = _entrypoint("tools/maintenance/test_codex_oauth.py", {
            "logger": LOGGER,
            "_setup_logging": lambda _verbose: None,
            "postgres_store": SimpleNamespace(require_ready=lambda: None),
            "codex_operation_service": SimpleNamespace(submit=submit),
            "operation_task_store": SimpleNamespace(get_run=lambda _run_id: {
                "status": "success", "result_summary": {},
            }),
        })
        modules = {
            "core": _module("core"),
            "core.runtime": _module("core.runtime"),
            "core.runtime.standalone": _module("core.runtime.standalone",
                require_standalone_owner=require_owner),
        }
        with patch.dict(sys.modules, modules), patch.object(sys, "argv",
                ["test_codex_oauth.py", "--email", "fixture@example.test"]):
            try:
                result = main()
            except BaseException as exc:
                return state, exc
        return state, result

    def test_owner_conflict_prevents_oauth_task_submission(self):
        expected = RuntimeError("owner_file_busy")
        state, error = self._run_cli(owner_error=expected)
        self.assertIs(error, expected)
        self.assertFalse(state.submitted)

    def test_oauth_task_is_submitted_after_owner_is_acquired(self):
        state, result = self._run_cli()
        self.assertEqual(result, 0)
        self.assertTrue(state.owner_checked)
        self.assertTrue(state.submitted)


class WorkerEntrypointCleanupTests(unittest.TestCase):
    def test_start_or_partial_install_error_survives_failed_runtime_cleanup(self):
        for stage in ("install", "start"):
            for cleanup_raises in (False, True):
                failure = StartupFailure(stage)
                state = SimpleNamespace(cleaned=False)

                def install(_bootstrap):
                    if stage == "install":
                        raise failure

                def start():
                    raise failure

                def stop(*, timeout):
                    self.assertGreater(timeout, 0.0)
                    self.assertLessEqual(timeout, 60.0)
                    state.cleaned = True
                    if cleanup_raises:
                        raise RuntimeError("cleanup")
                    return False

                bootstrap = SimpleNamespace(prepare_log_environment=lambda: None)
                modules = {
                    "config": _module("config"),
                    "config.env_loader": _module("config.env_loader", ensure_loaded=lambda: None),
                    "core": _module("core"),
                    "core.runtime": _module("core.runtime"),
                    "core.runtime.bootstrap": _module("core.runtime.bootstrap",
                        RuntimeBootstrap=SimpleNamespace(from_environment=lambda **_kwargs: bootstrap)),
                    "core.runtime.assembly": _module("core.runtime.assembly", install=install),
                    "core.runtime.process": _module("core.runtime.process",
                        start_runtime=start, stop_runtime=stop),
                    "core.storage": _module("core.storage",
                        postgres=SimpleNamespace(require_ready=lambda: None)),
                }
                main = _entrypoint("worker.py", {
                    "logging": SimpleNamespace(DEBUG=10, INFO=20,
                        basicConfig=lambda **_kwargs: None, getLogger=lambda _name: LOGGER),
                    "os": SimpleNamespace(environ={}),
                    "threading": SimpleNamespace(Event=lambda: object()),
                    "signal": SimpleNamespace(SIGTERM=signal.SIGTERM, SIGINT=signal.SIGINT,
                        signal=lambda *_args: None),
                })
                with self.subTest(stage=stage, cleanup_raises=cleanup_raises), \
                        patch.dict(sys.modules, modules), patch.object(sys, "argv", ["worker.py"]):
                    with self.assertRaises(StartupFailure) as caught:
                        main()
                    self.assertIs(caught.exception, failure)
                    self.assertTrue(state.cleaned)


if __name__ == "__main__":
    unittest.main()
