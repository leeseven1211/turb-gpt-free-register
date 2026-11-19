"""历史代理上下文维护的启动、准入和停止边界。"""
from __future__ import annotations

from contextlib import ExitStack
import threading
from types import SimpleNamespace
from unittest.mock import patch

from core.operations import reconciliation
from core.runtime import assembly
from core.runtime.composition import ComponentHooks, RuntimeController
from core.runtime.context import RuntimeContext
from core.runtime.managed import ManagedRuntime
from core.runtime.manifest import COMPONENTS
from core.runtime.periodic import PeriodicThread


def test_backfill_start_returns_before_work_and_stop_reports_a_live_thread():
    entered, release, exited = (threading.Event() for _ in range(3))
    lifecycle = PeriodicThread("test-registration-proxy-backfill")

    def work(*_args, **_kwargs):
        entered.set()
        try:
            release.wait(2)
            return 0
        finally:
            exited.set()

    with patch.object(reconciliation, "_PROXY_BACKFILL", lifecycle), patch.object(
        reconciliation, "execution_allowed", return_value=True,
    ), patch.object(reconciliation, "run_deferred_account_proxy_backfill", side_effect=work):
        try:
            assert reconciliation.start_periodic_account_proxy_backfill()
            assert entered.wait(1)
            assert not exited.is_set()
            assert not reconciliation.stop_periodic_account_proxy_backfill(timeout=0)
            assert reconciliation.account_proxy_backfill_status()["alive"]
        finally:
            release.set()
            assert reconciliation.stop_periodic_account_proxy_backfill(timeout=1)
        assert exited.is_set()
        assert not reconciliation.account_proxy_backfill_status()["alive"]


def test_backfill_waits_for_execution_admission_and_passes_stop_and_budget():
    checked, entered = threading.Event(), threading.Event()
    context = RuntimeContext("worker")
    lifecycle = PeriodicThread("test-registration-proxy-backfill")
    calls = []

    def admitted():
        checked.set()
        return context.admission.is_open()

    def work(*_args, **kwargs):
        calls.append(kwargs)
        entered.set()
        return 0

    with ExitStack() as stack:
        stack.enter_context(patch.object(reconciliation, "_PROXY_BACKFILL", lifecycle))
        stack.enter_context(patch.object(reconciliation, "time", SimpleNamespace(monotonic=lambda: 100.0)))
        stack.enter_context(patch("core.runtime.process.get_runtime_context", return_value=context))
        stack.enter_context(patch("core.runtime.process.execution_admitted", side_effect=admitted))
        stack.enter_context(patch.object(reconciliation, "run_deferred_account_proxy_backfill", side_effect=work))
        try:
            assert reconciliation.start_periodic_account_proxy_backfill()
            assert checked.wait(1)
            assert not entered.is_set()
            context.admission.unblock("startup")
            assert entered.wait(1.5)
            assert calls[0]["limit"] == 100
            assert calls[0]["deadline"] == 105.0
            assert calls[0]["cancelled"]() is False
            lifecycle.stop_event.set()
            assert calls[0]["cancelled"]() is True
        finally:
            assert reconciliation.stop_periodic_account_proxy_backfill(timeout=1)


def test_backfill_wrapper_preserves_deadline_and_cancellation():
    observed = []
    cancellation = threading.Event().is_set

    def backfill(**kwargs):
        observed.append(kwargs)
        return 7

    with patch.object(reconciliation.db, "backfill_account_registration_proxy_context", side_effect=backfill):
        assert reconciliation.run_deferred_account_proxy_backfill(
            limit=13, deadline=123.0, cancelled=cancellation,
        ) == 7
    assert observed == [{"limit": 13, "deadline": 123.0, "cancelled": cancellation}]


def test_managed_shutdown_joins_backfill_before_claimers_and_drain():
    calls = []
    owner = SimpleNamespace(start=lambda: None, require_owner=lambda: None,
                            close=lambda **_kwargs: True)
    context = RuntimeContext("worker")
    hooks = {}
    for spec in COMPONENTS:
        def stop(_context, _budget, name=spec.name):
            calls.append(name)
            return True
        hooks[spec.name] = ComponentHooks(lambda _context: None, stop)
    controller = RuntimeController(context, hooks, owner=owner)
    runtime = ManagedRuntime(
        controller=controller,
        heartbeat=SimpleNamespace(start=lambda: None, stop=lambda **_kwargs: True),
        producer_names=assembly._PRODUCERS,
        claim_names=assembly._CLAIMERS,
        active_counts=lambda: {"accepted": 0},
        settle=lambda _budget: calls.append("settle") or True,
        flush=lambda _budget: True,
        close_connections=lambda _budget: calls.append("close-connections") or True,
        close_executors=lambda _budget: calls.append("drain") or True,
    )
    runtime.start()
    assert runtime.stop(timeout=1)
    assert calls.index("registration_proxy_backfill") < calls.index("registration_dispatcher")
    assert calls.index("registration_proxy_backfill") < calls.index("drain")
    assert calls.index("registration_proxy_backfill") < calls.index("close-connections")
