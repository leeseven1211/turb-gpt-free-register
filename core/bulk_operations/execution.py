"""托管 Run 的精确关联与事实事务钩子；普通操作保持原执行路径。"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager


def managed_identity(conn, run_id: int) -> int | None:
    from core.storage.operations import bulk_schema, store
    if bulk_schema._READY_KEY != f"{store.postgres_store.database_url()}::{store._schema_name()}":
        return None
    with conn.cursor() as cur:
        cur.execute(f"SELECT data->>'bulk_target_round_id' AS target FROM {store._table('operation_runs')} WHERE id=%s", (int(run_id),))
        row = cur.fetchone()
    value = str((row or {}).get("target") or "")
    return int(value) if value.isdigit() and int(value) > 0 else None


def attach_context(conn, items, *, run_rows: bool = False) -> None:
    """当前页一次集合关联具体Run，旧列表无需逐条访问批次历史。"""
    from core.storage.operations import bulk_schema, store
    if bulk_schema._READY_KEY != f"{store.postgres_store.database_url()}::{store._schema_name()}":
        return
    ids = {int(item.get("id" if run_rows else "last_run_id") or 0) for item in items}
    ids.discard(0)
    if not ids:
        return
    with conn.cursor() as cur:
        cur.execute(f"""SELECT l.run_id,tr.batch_id,tr.round_id,tr.canonical_target_id
            FROM {store._table('operation_batch_run_links')} l
            JOIN {store._table('operation_batch_target_rounds')} tr ON tr.id=l.target_round_id
            WHERE l.run_id=ANY(%s) AND l.relation IN ('owned_root','owned_child','owned_continuation')""", (sorted(ids),))
        found = {int(row["run_id"]): row for row in cur.fetchall()}
    for item in items:
        row = found.get(int(item.get("id" if run_rows else "last_run_id") or 0))
        if row:
            item.update(bulk_batch_id=str(row["batch_id"]), bulk_round_id=str(row["round_id"]),
                        bulk_target_id=str(row["canonical_target_id"]))


def lock_run(conn, run_id: int, *, claim: bool = False):
    """必须在取得账号、Task、Run 行锁之前调用。"""
    if not managed_identity(conn, run_id):
        return None
    from core.storage.operations import bulk, store
    from core.storage import records
    target = bulk.ensure_managed_claim(conn, int(run_id)) if claim else bulk.lock_managed_target(conn, int(run_id))
    if target:
        with conn.cursor() as cur:
            if claim:
                # 准入锁内不能等待被批量展开或领域写回占住的账号/Task行。
                cur.execute("SET LOCAL lock_timeout = '5ms'")
            cur.execute(f"SELECT account_id,task_id FROM {store._table('operation_runs')} WHERE id=%s", (int(run_id),))
            identity = cur.fetchone()
            if identity:
                if identity.get("account_id"):
                    records.get_row(records.ACCOUNTS, int(identity["account_id"]), conn=conn, for_update=True)
                cur.execute(f"SELECT id FROM {store._table('operation_tasks')} WHERE id=%s FOR UPDATE", (identity["task_id"],))
                cur.fetchone()
    return target


@contextmanager
def fact_update(conn, run_id: int, *, claim: bool = False, emit: bool = True):
    managed = lock_run(conn, run_id, claim=claim)
    yield managed
    if emit:
        changed(conn, managed)


def changed(conn, managed, *, event_kind: str = "fact_changed") -> None:
    if managed:
        from core.storage.operations import bulk
        bulk.record_managed_change(conn, int(managed.get("target_round_id") or managed["id"]), event_kind=event_kind)


def release_cancelled_refresh(conn, run: Mapping) -> None:
    """排队受管AT取消后，仅释放同一排队时间的账号投影，不触碰更新的执行。"""
    data = run.get("data") if isinstance(run.get("data"), Mapping) else {}
    queued_at = data.get("live_check_queued_at")
    if (not data.get("bulk_target_round_id") or data.get("force_refresh") is not True or not queued_at
            or run.get("status") != "cancelled" or run.get("started_at") or data.get("remote_intent")):
        return
    from core.storage import records
    from datetime import datetime, timezone
    records.claim_row(records.ACCOUNTS, int(run["account_id"]), conn=conn,
        guard="live_check_status='queued' AND data->>'live_check_queued_at'=%s AND data->>'live_check_trigger'='manual_bulk'",
        guard_params=(str(queued_at),), changes={"live_check_status": "cancelled", "live_check_ok": False,
            "live_check_error": "批量任务取消未开始", "live_checked_at": datetime.now(timezone.utc).isoformat()})


def source_run_for_creation(*, account_id: int | None, data: Mapping | None) -> int | None:
    """仅同账号当前执行的受管链可传播上下文，不凭时间或邮箱猜归属。"""
    from core.operations.concurrency import current_execution
    execution = current_execution()
    if execution is None:
        return None
    run = execution.claimed_run
    run_data = run.get("data") if isinstance(run.get("data"), Mapping) else {}
    if not run_data.get("bulk_target_round_id") or int(run.get("account_id") or 0) != int(account_id or 0):
        return None
    if data and data.get("bulk_target_round_id") and int(data["bulk_target_round_id"]) != int(run_data["bulk_target_round_id"]):
        return None
    return int(run["id"])


def retry_managed(task: Mapping) -> dict | None:
    """旧手动入口转为新轮次，自动依赖续接不调用此入口。"""
    data = task.get("data") if isinstance(task.get("data"), Mapping) else {}
    if not data.get("bulk_target_round_id"):
        return None
    from core.bulk_operations.service import retry_managed_task
    return retry_managed_task(int(task["id"]))


def repair_pending_handoffs(*, limit: int = 50) -> int:
    """从已提交父Run补登记handoff，不重建子任务，也不发送业务请求。"""
    from core.storage.operations import bulk_schema, store
    if bulk_schema._READY_KEY != f"{store.postgres_store.database_url()}::{store._schema_name()}":
        return 0
    with store._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT r.id,r.task_id,r.account_id,t.email_snapshot,t.source_system,
                r.result_summary,r.data->'config_snapshot' AS config_snapshot
            FROM {store._table('operation_batch_run_links')} l
            JOIN {store._table('operation_batch_target_rounds')} tr ON tr.id=l.target_round_id
            JOIN {store._table('operation_runs')} r ON r.id=l.run_id
            JOIN {store._table('operation_tasks')} t ON t.id=r.task_id
            WHERE tr.chain_state<>'closed' AND r.status='partial_success'
              AND l.relation IN ('owned_root','owned_continuation')
              AND r.result_summary->'completion_handoff' IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM {store._table('operation_task_dependencies')} d
                WHERE d.parent_source_system=t.source_system AND d.parent_source_id=t.id::text
                  AND d.payload->>'parent_run_id'=r.id::text)
            ORDER BY r.id LIMIT %s""", (max(1, min(200, int(limit))),))
        rows = list(cur.fetchall())
    restored = 0
    for row in rows:
        summary = dict(row.get("result_summary") or {})
        handoff = summary.get("completion_handoff") or {}
        child_system, child_id = handoff.get("child_source_system"), handoff.get("child_source_id")
        if not child_system or not child_id:
            continue
        dependency = store.register_task_dependency(
            parent_source_system=row["source_system"], parent_source_id=str(row["task_id"]),
            child_source_system=str(child_system), child_source_id=str(child_id), dependency_type="account_completion",
            payload={"parent_run_id": row["id"], "account_id": row["account_id"], "email": row["email_snapshot"],
                     "task_trigger": "manual_bulk", "remaining_steps": list(handoff.get("remaining_steps") or []),
                     "settings": dict(row.get("config_snapshot") or {}), "result_summary": summary})
        if dependency.get("status") == "ready":
            from core.operations import task_gateway
            task_gateway.notify_dependency_ready(dependency)
        restored += 1
    return restored


@contextmanager
def dependency_update(conn, *, dependency_id: int | None = None, payload: Mapping | None = None):
    from core.storage.operations import store
    if payload is None and dependency_id is not None:
        with conn.cursor() as cur:
            cur.execute(f"SELECT payload FROM {store._table('operation_task_dependencies')} WHERE id=%s", (int(dependency_id),))
            row = cur.fetchone()
            payload = (row or {}).get("payload") or {}
    source_run = int((payload or {}).get("parent_run_id") or 0)
    if source_run:
        with fact_update(conn, source_run) as managed:
            yield managed
    else:
        yield None


def inherit(conn, run_id: int, *, source_run_id: int | None, step_key: str | None = None, parent_task_id: int | None = None):
    if not source_run_id or not managed_identity(conn, source_run_id):
        return None
    from core.storage.operations import bulk, store
    link = bulk.inherit_managed_run(conn, int(run_id), source_run_id=int(source_run_id), step_key=step_key, parent_task_id=parent_task_id)
    if link:
        target_id = int(link.get("target_round_id") or link.get("id") or 0)
        with conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET data=data || %s::jsonb WHERE id=%s", (store._json({"bulk_target_round_id": target_id}), int(run_id)))
    return link
