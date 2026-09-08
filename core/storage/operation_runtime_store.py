"""统一 operation 原生运行时的 command/query 入口。"""
from __future__ import annotations

from typing import Any


def _operation():
    from core.storage import operation

    return operation


def create_runtime_batch(**kwargs: Any) -> dict:
    return _operation().create_runtime_batch(**kwargs)


def create_runtime_task(**kwargs: Any) -> dict:
    return _operation().create_runtime_task(**kwargs)


def retry_runtime_task(task_id: int, **kwargs: Any) -> dict:
    return _operation().retry_runtime_task(task_id, **kwargs)


def get_run(run_id: int) -> dict | None:
    return _operation().get_run(run_id)


def get_task(task_id: int, **kwargs: Any) -> dict | None:
    return _operation().get_task(task_id, **kwargs)


def active_run_for_account(account_id: int, **kwargs: Any) -> dict | None:
    return _operation().active_run_for_account(account_id, **kwargs)


def list_queued_runs(**kwargs: Any) -> list[dict]:
    return _operation().list_queued_runs(**kwargs)


def recover_interrupted_runtime_runs() -> int:
    return _operation().recover_interrupted_runtime_runs()


def mark_runtime_batch_empty(batch_id: int, **kwargs: Any) -> bool:
    return _operation().mark_runtime_batch_empty(batch_id, **kwargs)


def set_runtime_batch_skipped(batch_id: int, skipped: int) -> bool:
    return _operation().set_runtime_batch_skipped(batch_id, skipped)


def claim_run(run_id: int, **kwargs: Any) -> dict | None:
    return _operation().claim_run(run_id, **kwargs)


def append_runtime_event(run_id: int, **kwargs: Any) -> dict:
    return _operation().append_runtime_event(run_id, **kwargs)


def heartbeat_run(run_id: int, **kwargs: Any) -> bool:
    return _operation().heartbeat_run(run_id, **kwargs)


def acquire_account_lease(account_id: int, run_id: int, **kwargs: Any) -> str | None:
    return _operation().acquire_account_lease(
        account_id=account_id,
        run_id=run_id,
        **kwargs,
    )


def release_account_lease(run_id: int, lease_token: str = "", **kwargs: Any) -> bool:
    return _operation().release_account_lease(
        run_id=run_id,
        lease_token=lease_token,
        **kwargs,
    )


def request_run_cancel(run_id: int, **kwargs: Any) -> dict:
    return _operation().request_run_cancel(run_id, **kwargs)


def is_run_cancel_requested(run_id: int, **kwargs: Any) -> bool:
    return _operation().is_run_cancel_requested(run_id, **kwargs)


def mark_run_settling(run_id: int, **kwargs: Any) -> bool:
    return _operation().mark_run_settling(run_id, **kwargs)


def register_resource(run_id: int, **kwargs: Any) -> dict:
    return _operation().register_resource(run_id, **kwargs)


def release_resource(resource_id: int, **kwargs: Any) -> bool:
    return _operation().release_resource(resource_id, **kwargs)


def finish_run(run_id: int, **kwargs: Any) -> dict:
    return _operation().finish_run(run_id, **kwargs)


__all__ = [
    "create_runtime_batch", "create_runtime_task", "retry_runtime_task", "get_run",
    "get_task", "active_run_for_account", "list_queued_runs", "recover_interrupted_runtime_runs",
    "mark_runtime_batch_empty", "set_runtime_batch_skipped", "claim_run",
    "append_runtime_event", "heartbeat_run", "acquire_account_lease", "release_account_lease",
    "request_run_cancel", "is_run_cancel_requested", "mark_run_settling", "register_resource",
    "release_resource", "finish_run",
]
