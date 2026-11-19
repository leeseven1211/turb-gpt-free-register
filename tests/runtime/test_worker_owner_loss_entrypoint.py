"""独立 Worker 丢失执行归属后的退出与原停止预算。"""
from __future__ import annotations

from contextlib import ExitStack
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _module(name, **values):
    module = ModuleType(name)
    module.__dict__.update(values)
    return module


def _exercise(*, owner=True, runtime_clean=True, stop_failure=None, log_delay=0, total=55):
    spec = importlib.util.spec_from_file_location("worker_owner_loss_entry", ROOT / "worker.py")
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    now = [100.0]
    calls, receipts, diagnostics, handlers = [], [], [], {}

    def owner_valid():
        calls.append("owner")
        return owner

    def stop_runtime(*, timeout):
        calls.append(("stop", timeout))
        return runtime_clean

    def error(message, *args):
        diagnostics.append(message % args if args else message)
        now[0] += log_delay

    def manager_status():
        if isinstance(stop_failure, Exception):
            raise stop_failure
        return {"state": "stop_incomplete", "error_code": stop_failure}

    def install(_bootstrap):
        calls.append("install")
        return SimpleNamespace(manager=SimpleNamespace(status=manager_status))

    class Event:
        def __init__(self):
            self.waits = 0

        def set(self):
            pass

        def wait(self, _timeout):
            self.waits += 1
            if self.waits <= 2:
                return False
            handlers[entry.signal.SIGTERM](entry.signal.SIGTERM, None)
            return True

    bootstrap = SimpleNamespace(prepare_log_environment=lambda: None)
    modules = {
        "config": _module("config"),
        "config.env_loader": _module("config.env_loader", ensure_loaded=lambda: None),
        "core": _module("core"),
        "core.runtime": _module("core.runtime"),
        "core.runtime.bootstrap": _module(
            "core.runtime.bootstrap",
            RuntimeBootstrap=SimpleNamespace(from_environment=lambda **_kwargs: bootstrap),
        ),
        "core.runtime.assembly": _module(
            "core.runtime.assembly", install=install,
        ),
        "core.runtime.process": _module(
            "core.runtime.process", start_runtime=lambda: calls.append("start"),
            stop_runtime=stop_runtime, execution_owner_valid=owner_valid,
            execution_admitted=lambda: False,
        ),
        "core.runtime.role_launcher": _module(
            "core.runtime.role_launcher",
            publish_managed_identity=lambda _bootstrap: calls.append("identity"),
            write_exit_receipt=lambda **value: receipts.append(value),
        ),
        "core.storage": _module(
            "core.storage", postgres=SimpleNamespace(require_ready=lambda: None),
        ),
    }
    logger = SimpleNamespace(error=error, exception=error)
    with ExitStack() as stack:
        stack.enter_context(patch.dict(sys.modules, modules))
        stack.enter_context(patch.dict(entry.os.environ, {
            "TURB_RUNTIME_MANAGER": "launchd",
            "TURB_ROLE_EXIT_PATH": "/synthetic/unused-worker-exit",
        }, clear=True))
        stack.enter_context(patch.object(sys, "argv", [
            "worker.py", "--shutdown-timeout", str(total),
        ]))
        stack.enter_context(patch.object(entry.time, "monotonic", side_effect=lambda: now[0]))
        stack.enter_context(patch.object(entry.threading, "Event", Event))
        stack.enter_context(patch.object(entry.signal, "signal",
            side_effect=lambda number, handler: handlers.__setitem__(number, handler)))
        stack.enter_context(patch.object(entry.logging, "basicConfig"))
        stack.enter_context(patch.object(entry.logging, "getLogger", return_value=logger))
        try:
            entry.main()
        except BaseException as exc:
            failure = exc
        else:
            failure = None
    return calls, receipts, diagnostics, failure


def test_worker_with_owner_keeps_running_when_admission_is_temporarily_closed():
    calls, receipts, diagnostics, failure = _exercise()
    assert failure is None
    assert calls.count("owner") == 2
    assert calls == ["install", "start", "identity", "owner", "owner", ("stop", 55)]
    assert receipts == [{"role": "worker", "clean": True, "code": 0}]
    assert diagnostics == []


@pytest.mark.parametrize("runtime_clean", [True, False])
def test_owner_loss_runs_existing_cleanup_and_exits_nonzero(runtime_clean):
    calls, receipts, diagnostics, failure = _exercise(
        owner=False, runtime_clean=runtime_clean,
    )
    assert isinstance(failure, SystemExit)
    assert failure.code == 1
    assert calls == ["install", "start", "identity", "owner", ("stop", 55)]
    assert receipts == [{"role": "worker", "clean": False, "code": 1}]
    assert any("runtime_execution_owner_lost" in message for message in diagnostics)


@pytest.mark.parametrize("total", [55, 60])
def test_owner_loss_preserves_one_stop_deadline_including_diagnostic_time(total):
    calls, _receipts, _diagnostics, failure = _exercise(
        owner=False, total=total, log_delay=9,
    )
    assert isinstance(failure, SystemExit)
    assert failure.code == 1
    assert calls[-1] == ("stop", total - 9)


def test_failed_drain_logs_the_runtime_stage_with_original_owner_loss_exit():
    _calls, receipts, diagnostics, failure = _exercise(
        owner=False, runtime_clean=False, stop_failure="runtime_settlement_drain_timeout",
    )
    assert "后台排空未完成：code=runtime_settlement_drain_timeout" in diagnostics
    assert isinstance(failure, SystemExit)
    assert failure.code == 1
    assert receipts == [{"role": "worker", "clean": False, "code": 1}]


@pytest.mark.parametrize("stop_failure", [
    "runtime_unapproved_detail",
    RuntimeError("private diagnostic"),
    None,
])
def test_failed_drain_uses_fixed_fallback_if_stage_is_unknown_or_unavailable(stop_failure):
    _calls, receipts, diagnostics, failure = _exercise(
        runtime_clean=False, stop_failure=stop_failure,
    )
    assert diagnostics == ["后台排空未完成：code=runtime_stop_failed"]
    assert isinstance(failure, SystemExit)
    assert failure.code == 3
    assert receipts == [{"role": "worker", "clean": False, "code": 3}]
