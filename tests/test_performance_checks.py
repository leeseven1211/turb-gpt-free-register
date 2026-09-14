"""Pure checks for the reproducible performance benchmark boundaries."""
import os

import pytest

from tools.test_performance import percentile, run_benchmark


def test_percentile_uses_nearest_rank_for_small_sample():
    assert percentile([1, 2, 3, 4], 95) == 4
    assert percentile([4, 1, 3, 2], 50) == 2


def test_percentile_rejects_empty_or_invalid_input():
    with pytest.raises(ValueError):
        percentile([], 95)
    with pytest.raises(ValueError):
        percentile([1], 0)


def test_benchmark_requires_terminal_history_pressure():
    with pytest.raises(ValueError, match="2000"):
        run_benchmark(history_rows=1999)


def test_benchmark_restores_environment_when_cleanup_fails(monkeypatch):
    """Executor/schema cleanup errors must not leak benchmark process settings."""
    from core import postgres_store
    from core.account_operation_executor import executor
    from core.storage import operation

    original = {
        "TURB_DB_SCHEMA": "caller_schema",
        "ACCOUNT_BATCH_WORKERS": "caller_workers",
        "OPERATION_TASK_DB_SCHEMA": "caller_operation_schema",
        "ACCOUNT_TASK_DB_SCHEMA": "caller_account_task_schema",
    }
    for name, value in original.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://127.0.0.1:55432/turb_opt_20260914",
    )

    monkeypatch.setattr(
        "tools.test_performance._seed_accounts", lambda **_kwargs: [1],
    )
    monkeypatch.setattr("tools.test_performance._seed_terminal_operation_history", lambda **_kwargs: {
        "batch_id": 1, "tasks": 2000, "runs": 2000, "linked_runs": 2000,
    })
    monkeypatch.setattr("tools.test_performance._measure_account_list", lambda **_kwargs: {
        "query_count": {"max": 1}, "latency_ms": {"p95": 1},
    })
    monkeypatch.setattr("tools.test_performance._measure_operation_list", lambda **_kwargs: {
        "query_count": {"max": 1}, "latency_ms": {"p95": 1},
    })
    monkeypatch.setattr("tools.test_performance._run_dispatch_benchmark", lambda **_kwargs: {
        "concurrency": {"within_limit": True},
        "congestion": {"observed": True},
        "restart_recovery": {"all_completed": True},
        "errors": [],
    })
    monkeypatch.setattr(operation, "init", lambda: None)
    monkeypatch.setattr(executor, "status", lambda: {"budget": 3})

    def fail_shutdown(*, wait=True):
        raise RuntimeError("shutdown failed")

    monkeypatch.setattr(executor, "shutdown", fail_shutdown)
    monkeypatch.setattr(
        postgres_store,
        "connect",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("drop failed")),
    )
    monkeypatch.setattr(postgres_store, "close_pools", lambda: None)

    with pytest.raises(RuntimeError, match="drop failed"):
        run_benchmark(rows=1000, samples=5, workers=3, queue_tasks=32)

    for name, value in original.items():
        assert os.environ[name] == value
