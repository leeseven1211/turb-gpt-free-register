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


__all__ = ["reconcile_all", "sync_registration_job", "sync_account_task", "mark_registration_jobs_deleted", "verify"]
