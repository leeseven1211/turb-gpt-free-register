"""注册任务的持久队列、驱动分类与共享执行许可适配。"""
from __future__ import annotations

import hashlib
import logging
import threading
from contextlib import contextmanager
from typing import Callable, Mapping

from core import db
from core.operations import concurrency
from core.registration.driver_selection import normalize_registration_driver
from core.storage import records

logger = logging.getLogger(__name__)


def mark_execution_state(state: str) -> None:
    """状态投影失败不改变注册行为，也不提前归还执行许可。"""
    context = concurrency.current_execution()
    if context is not None:
        try:
            concurrency.set_execution_state(context, state)
        except Exception:
            logger.exception("注册执行许可状态暂未同步：%s", state)


def registration_admission_class(job: Mapping | None = None, *, driver: str | None = None) -> str:
    """按实际执行动作分类，历史任务名称不覆盖业务含义。"""
    values = job or {}
    action = str(values.get("job_type") or "registration")
    if action == "codex_retry":
        return "codex_retry"
    if action == "twofa_retry":
        # 这个兼容 worker 会依次补密码、查套餐和设置 2FA。
        return "account_setup_retry"
    if action in {"twofa_setup", "twofa_change"}:
        return action
    snapshot = values.get("config_snapshot")
    if not isinstance(snapshot, Mapping):
        data = values.get("data")
        snapshot = data.get("config_snapshot") if isinstance(data, Mapping) else None
    if driver is None:
        from core.registration.service import configured_registration_driver

        driver = str((snapshot or {}).get("registration_driver") or configured_registration_driver())
    canonical = normalize_registration_driver(driver)
    return {"roxy": "registration_roxy", "protocol_oss_2": "registration_proto2"}[canonical]


def pending_jobs() -> list[dict]:
    """读取全部可派发批次，按类型、批次轮转，避免旧大批次遮挡其他任务。"""
    jobs = records.list_rows(
        records.JOBS,
        where='"status" = %s AND COALESCE(data->>\'registration_dispatch_ready\', '
              'data->\'data\'->>\'registration_dispatch_ready\', \'true\') <> \'false\'',
        params=("pending",), order_by="id",
    )
    for job in jobs:
        job["task_type"] = registration_admission_class(job)
        job["batch_key"] = f"registration:{job.get('batch_id') or job['id']}"
        job["dispatch_position"] = int(job["id"])
    return concurrency.order_dispatch_candidates(jobs)


def try_admit_job(job: Mapping):
    """许可与 legacy pending→running 使用同一事务，worker 不再二次抢占。"""
    records.init()
    job_id = int(job["id"])

    def claim(conn, execution_id):
        if not db.claim_job_for_execution(job_id, execution_id=execution_id, conn=conn):
            return None
        records.patch_row(records.JOBS, job_id, {"concurrency_blocked_by": []}, conn=conn)
        return records.get_row(records.JOBS, job_id, conn=conn)

    batch = str(job.get("batch_id") or job_id)
    attempt = str(job.get("attempt_id") or job.get("root_job_id") or job_id)
    extra_scopes = [{"kind": "registration_attempt", "key": attempt, "limit": 1}]
    if job.get("account_id") is not None:
        extra_scopes.append({"kind": "account", "key": f"{int(job['account_id'])}:openai_interactive", "limit": 1})
    result = concurrency.try_admit_and_claim(
        execution_key=f"registration_job:{job_id}",
        task_type=registration_admission_class(job), claim=claim,
        batch_key=f"registration:{batch}", batch_limit=max(1, int(job.get("batch_workers") or 1)),
        metadata={"source_system": "registration_jobs", "source_id": str(job_id)},
        extra_scopes=extra_scopes,
    )
    reasons = list(result.blocked_by)
    if result.context is None and reasons != list(job.get("concurrency_blocked_by") or []):
        db._patch_job(job_id, {"concurrency_blocked_by": reasons})
    return result


def verify_job_execution(job_id: int) -> bool:
    """只验证已认领身份，取消和停止仍由原 worker 的安全检查点处理。"""
    context = concurrency.current_execution()
    if context is None or context.execution_key != f"registration_job:{int(job_id)}":
        raise RuntimeError("注册 worker 缺少匹配的并发许可")
    job = db.get_job(int(job_id)) or {}
    return bool(job.get("status") == "running" and job.get("execution_id") == context.execution_id)


def run_job(job_id: int, execute: Callable[[], object]):
    """兼容入口统一获准后执行，清理及调试保留都发生在许可归还之前。"""
    context = concurrency.current_execution()
    owns_permit = context is None
    if owns_permit:
        job = db.get_job(int(job_id))
        if not job or job.get("status") != "pending":
            return None
        result = try_admit_job(job)
        context = result.context
        if context is None:
            return None
    elif context.execution_key != f"registration_job:{int(job_id)}":
        raise RuntimeError("注册 worker 不能复用其他任务的执行许可")
    try:
        with concurrency.execution_scope(context):
            # 读模型同步必须在准入事务提交之后，不持有准入锁等待另一连接。
            db._sync_operation_job(int(job_id))
            return execute()
    finally:
        if owns_permit:
            concurrency.release_execution(context, reason="worker_exit")


def try_admit_cli(*, batch_id: str, index: int, batch_workers: int, driver: str):
    """CLI 的批次只提供附加上限，预算域仍是部署使用的同一 PostgreSQL。"""
    key = f"registration_cli:{batch_id}:{int(index)}"
    return concurrency.try_admit_and_claim(
        execution_key=key, task_type=registration_admission_class(driver=driver),
        claim=lambda _conn, execution_id: {"execution_id": execution_id, "batch_id": batch_id, "batch_index": index},
        batch_key=f"registration:{batch_id}", batch_limit=max(1, int(batch_workers)),
        metadata={"source_system": "registration_cli", "source_id": key},
    )


@contextmanager
def cli_execution(*, batch_id: str, index: int, batch_workers: int, driver: str, context=None):
    """串行和兼容 CLI 等待共享空位；容量等待不进入注册驱动或消耗重试。"""
    existing = concurrency.current_execution()
    expected_type = registration_admission_class(driver=driver)
    if existing is not None:
        if existing.task_type != expected_type or not concurrency.validate_execution(existing):
            raise RuntimeError("CLI 注册许可与所选驱动不一致")
        yield existing
        return
    if context is None:
        while True:
            result = try_admit_cli(batch_id=batch_id, index=index, batch_workers=batch_workers, driver=driver)
            context = result.context
            if context is not None:
                break
            if any(reason in {"concurrency_policy_invalid", "concurrency_policy_missing", "scheduler_store_unavailable",
                              "concurrency_policy_migration_required"}
                   for reason in result.blocked_by):
                raise RuntimeError("CLI 注册准入不可用：" + ", ".join(result.blocked_by))
            threading.Event().wait(0.25)
    if context.task_type != expected_type:
        concurrency.release_execution(context, reason="permit_driver_mismatch")
        raise RuntimeError("CLI 注册许可与所选驱动不一致")
    try:
        with concurrency.execution_scope(context):
            yield context
    finally:
        concurrency.release_execution(context, reason="worker_exit")


@contextmanager
def standalone_execution(*, email: str, driver: str, entrypoint: str):
    """独立驱动入口使用稳定身份排队，父入口已经获准时直接复用。"""
    identifier = hashlib.sha256(f"{entrypoint}:{email.strip().casefold()}".encode()).hexdigest()
    with cli_execution(batch_id=f"standalone:{identifier}", index=1, batch_workers=1, driver=driver) as context:
        yield context


__all__ = [
    "registration_admission_class", "pending_jobs", "try_admit_job", "verify_job_execution",
    "run_job", "try_admit_cli", "cli_execution", "standalone_execution",
    "mark_execution_state",
]
