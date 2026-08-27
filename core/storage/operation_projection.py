"""旧注册/账号任务到统一 operation 的投影入口。"""
from __future__ import annotations

from typing import Any, Iterable


def reconcile_all() -> dict[str, int]:
    from core.storage import operation

    return operation.reconcile_all()


def sync_registration_job(job_id: int) -> None:
    from core.storage import operation

    return operation.sync_registration_job(job_id)


def sync_account_task(task_id: int) -> None:
    from core.storage import operation

    return operation.sync_account_task(task_id)


def mark_registration_jobs_deleted(job_ids: Iterable[int]) -> None:
    from core.storage import operation

    return operation.mark_registration_jobs_deleted(job_ids)


def verify() -> dict[str, Any]:
    from core.storage import operation

    return operation.verify()


def enqueue_batch_projection(batch_id: int, **kwargs: Any) -> dict:
    from core.storage import operation

    return operation.enqueue_batch_projection(batch_id, **kwargs)


def claim_projection(**kwargs: Any) -> dict | None:
    from core.storage import operation

    return operation.claim_projection(**kwargs)


def run_projection_once(**kwargs: Any) -> dict | None:
    from core.storage import operation

    return operation.run_projection_once(**kwargs)


def drain_projection_queue(**kwargs: Any) -> list[dict]:
    from core.storage import operation

    return operation.drain_projection_queue(**kwargs)


def start_projection_worker(**kwargs: Any) -> bool:
    from core.storage import operation

    return operation.start_projection_worker(**kwargs)


def stop_projection_worker(**kwargs: Any) -> bool:
    from core.storage import operation

    return operation.stop_projection_worker(**kwargs)


__all__ = [
    "reconcile_all", "sync_registration_job", "sync_account_task", "mark_registration_jobs_deleted", "verify",
    "enqueue_batch_projection", "claim_projection", "run_projection_once", "drain_projection_queue",
    "start_projection_worker", "stop_projection_worker",
]
