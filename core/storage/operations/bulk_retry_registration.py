"""注册补密码关联的集合收口；不改写注册认证事实或远端结果。"""
from __future__ import annotations

import json
import uuid

from core.accounts.password_evidence import password_is_confirmed
from core.storage import postgres, records
from core.storage.operations import common

_CHUNK_SIZE = 500


def _chunks(values):
    values = list(values)
    for offset in range(0, len(values), _CHUNK_SIZE):
        yield values[offset:offset + _CHUNK_SIZE]


def _enqueue_projections(cur, parents: list[dict]) -> set[int]:
    """先取得全部 queue 锁，再取得 batch 锁，与既有投影 writer 同序。"""
    by_batch = {int(parent["resolved_batch_id"]): str(parent["id"])
                for parent in sorted(parents, key=lambda row: int(row["id"]))
                if parent.get("resolved_batch_id")}
    rows = [{"batch_id": batch_id, "source_id": by_batch[batch_id]} for batch_id in sorted(by_batch)]
    for chunk in _chunks(rows):
        cur.execute(f"""INSERT INTO {common._table('operation_projection_queue')} AS queue
            (batch_id,reason,source_system,source_id,status,requested_at,available_at)
            SELECT s.batch_id,'registration_completion','registration_completion',s.source_id,
                'queued',now(),now()
            FROM jsonb_to_recordset(%s::jsonb) s(batch_id BIGINT,source_id TEXT) ORDER BY s.batch_id
            ON CONFLICT(batch_id) DO UPDATE SET reason=EXCLUDED.reason,
                source_system=EXCLUDED.source_system,source_id=EXCLUDED.source_id,
                requested_at=EXCLUDED.requested_at,
                status=CASE WHEN queue.status='running' THEN 'running' ELSE 'queued' END,
                dirty=CASE WHEN queue.status='running' THEN TRUE ELSE FALSE END,
                available_at=CASE WHEN queue.status='running' THEN queue.available_at ELSE EXCLUDED.available_at END,
                completed_at=CASE WHEN queue.status='running' THEN queue.completed_at ELSE NULL END,
                last_error=CASE WHEN queue.status='running' THEN queue.last_error ELSE NULL END,
                updated_at=now()""", (json.dumps(chunk),))
    for chunk in _chunks(sorted(by_batch)):
        # 即时批次刷新也使用同一 advisory 锁；必须先于 batch 行锁取得。
        cur.execute("SELECT pg_advisory_xact_lock(id) FROM unnest(%s::bigint[]) AS value(id) ORDER BY id",
                    (chunk,))
        cur.fetchall()
        cur.execute(f"""SELECT id FROM {common._table('operation_batches')}
            WHERE id=ANY(%s) ORDER BY id FOR NO KEY UPDATE""", (chunk,))
        cur.fetchall()
        cur.execute(f"""UPDATE {common._table('operation_batches')}
            SET projection_status=CASE WHEN projection_status='running' THEN 'running' ELSE 'queued' END,
                projection_requested_at=now(),projection_next_retry_at=NULL,
                projection_error=CASE WHEN projection_status='running' THEN projection_error ELSE NULL END
            WHERE id=ANY(%s)""", (chunk,))
    return set(by_batch)


def _result(parent: dict, child: dict, account: dict | None) -> dict:
    handoff = dict(common._decode(parent.get("data"))["completion_handoff"])
    remaining = str(handoff.get("remaining_error") or "")
    waiting = child["status"] in common._ACTIVE_RUN_STATUSES
    complete = child["status"] == "success" and password_is_confirmed(account)
    error = remaining
    if waiting:
        status, message = "waiting", "注册认证已成功，正在自动补密码"
    elif complete:
        status = "partial_success" if remaining else "success"
        message = "自动补密码已完成，其他注册后处理仍待补齐" if remaining else "注册续跑和自动补密码均已完成"
    else:
        status, message = "partial_success", "自动补密码未完成，账号 Token 已保留"
        error = "; ".join(value for value in (
            remaining, child.get("error_message") or "registration_completion_incomplete: 自动补密码未完成",
        ) if value)
    category, code, safe_error = common._error_fields(
        error or None, task_type="registration_resume", task_status=status)
    if not waiting and not complete and child.get("error_code"):
        category, code = child.get("error_category"), child["error_code"]
    summary = dict(common._decode(parent.get("result_summary")) or {})
    summary["completion_handoff"] = {
        **handoff, "run_id": int(child["run_id"]), "status": str(child["status"]), "message": message}
    summary["child_tasks"] = [{
        "task_id": int(child["id"]), "run_id": int(child["run_id"]), "task_type": child["task_type"],
        "status": child["status"], "error_code": child.get("error_code"),
        "error_message": common._text(child.get("error_message") or "", 500)}]
    actions = ([{"action": "await_child", "label": "等待自动补密码"}] if waiting else []
               if status == "success" else [{"action": "retry", "label": "重试未完成步骤"}])
    event_uuid = uuid.uuid5(uuid.NAMESPACE_URL,
        f"registration-completion:{parent['id']}:{child['run_id']}:{status}").hex
    return {"run_id": int(parent["id"]), "task_id": int(parent["task_id"]),
        "status": status, "stage": "waiting" if waiting else "complete", "waiting": waiting,
        "child_completed_at": child["completed_at"].isoformat() if child.get("completed_at") else None,
        "error_category": category, "error_code": code, "error_message": safe_error,
        "summary": common._scrub(summary), "actions": actions,
        "emit_event": str(parent["status"]) != status or parent.get("error_message") != safe_error,
        "event_uuid": event_uuid, "message": message,
        "level": "INFO" if waiting or status == "success" else "WARNING",
        "detail": {"child_task_id": int(child["id"]), "child_status": str(child["status"])}}


def reconcile_registration_many(cur, *, child_task_ids=(), parent_run_ids=()) -> set[int]:
    """同事务集合刷新准确代次的注册父任务，返回已登记投影的批次 ID。

    调用方拥有账号和正在重试的子 Task 锁。本函数按 queue→batch→父 Run→父
    Task 顺序取得附加锁，并在取得父 Task 锁后重检 last_run_id。
    """
    child_ids = sorted({str(int(value)) for value in child_task_ids if int(value) > 0})
    explicit_ids = sorted({int(value) for value in parent_run_ids if int(value) > 0})
    if not child_ids and not explicit_ids:
        return set()
    parents = {}
    size = max(len(child_ids), len(explicit_ids))
    for offset in range(0, size, _CHUNK_SIZE):
        cur.execute(f"""SELECT r.*,t.last_run_id,t.task_type,
                t.account_id AS resolved_account_id,t.batch_id AS resolved_batch_id
            FROM {common._table('operation_runs')} r
            JOIN {common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE t.task_type='registration_resume' AND t.last_run_id=r.id
                AND (r.id=ANY(%s) OR (r.data ? 'completion_handoff'
                    AND r.data->'completion_handoff'->>'task_id'=ANY(%s)))
            ORDER BY r.id""", (explicit_ids[offset:offset + _CHUNK_SIZE],
                              child_ids[offset:offset + _CHUNK_SIZE]))
        for raw in cur.fetchall():
            row = dict(raw)
            handoff = (common._decode(row.get("data")) or {}).get("completion_handoff")
            if isinstance(handoff, dict) and handoff.get("task_id"):
                parents[int(row["id"])] = row
    if not parents:
        return set()
    jobs = {}
    for chunk in _chunks(sorted({int(parent["source_id"]) for parent in parents.values()})):
        cur.execute(f"SELECT id,status FROM {postgres.qualified(records.JOBS.name)} WHERE id=ANY(%s)", (chunk,))
        jobs.update({int(row["id"]): row["status"] for row in cur.fetchall()})
    parents = {run_id: parent for run_id, parent in parents.items()
               if jobs.get(int(parent["source_id"])) in {"success", "partial_success"}}
    if not parents:
        return set()
    batch_ids = _enqueue_projections(cur, list(parents.values()))
    for chunk in _chunks(sorted(parents)):
        cur.execute(f"SELECT id FROM {common._table('operation_runs')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
                    (chunk,))
        cur.fetchall()
    locked_tasks = {}
    for chunk in _chunks(sorted({int(parent["task_id"]) for parent in parents.values()})):
        cur.execute(f"""SELECT id,last_run_id FROM {common._table('operation_tasks')}
            WHERE id=ANY(%s) ORDER BY id FOR UPDATE""", (chunk,))
        locked_tasks.update({int(row["id"]): int(row["last_run_id"] or 0) for row in cur.fetchall()})
    parents = {run_id: parent for run_id, parent in parents.items()
               if locked_tasks.get(int(parent["task_id"])) == run_id}
    if not parents:
        return batch_ids
    children = {}
    handoffs = {run_id: common._decode(parent["data"])["completion_handoff"]
                for run_id, parent in parents.items()}
    for chunk in _chunks(sorted({int(handoff["task_id"]) for handoff in handoffs.values()})):
        cur.execute(f"""SELECT t.id,t.task_type,r.id AS run_id,r.status,r.error_category,r.error_code,
                r.error_message,r.result_summary,r.completed_at
            FROM {common._table('operation_tasks')} t
            JOIN {common._table('operation_runs')} r ON r.id=t.last_run_id
            WHERE t.id=ANY(%s)""", (chunk,))
        children.update({int(row["id"]): dict(row) for row in cur.fetchall()})
    accounts = {}
    for chunk in _chunks(sorted({int(parent.get("resolved_account_id") or parent.get("account_id"))
                                for parent in parents.values()
                                if parent.get("resolved_account_id") or parent.get("account_id")})):
        cur.execute(f"SELECT * FROM {postgres.qualified(records.ACCOUNTS.name)} WHERE id=ANY(%s)", (chunk,))
        accounts.update({int(row["id"]): records.merge_row(records.ACCOUNTS, row) for row in cur.fetchall()})
    results = []
    for run_id, parent in parents.items():
        child = children.get(int(handoffs[run_id]["task_id"]))
        if child:
            results.append(_result(parent, child, accounts.get(
                int(parent.get("resolved_account_id") or parent.get("account_id") or 0))))
    for chunk in _chunks(results):
        payload = json.dumps(chunk, ensure_ascii=False)
        shape = """run_id BIGINT,task_id BIGINT,status TEXT,stage TEXT,waiting BOOLEAN,
            child_completed_at TIMESTAMPTZ,error_category TEXT,error_code TEXT,error_message TEXT,
            summary JSONB,actions JSONB,event_uuid TEXT,level TEXT,message TEXT,detail JSONB,emit_event BOOLEAN"""
        cur.execute(f"""UPDATE {common._table('operation_runs')} r
            SET status=s.status,progress_stage=s.stage,
                completed_at=CASE WHEN s.waiting THEN NULL ELSE COALESCE(s.child_completed_at,now()) END,
                error_category=s.error_category,error_code=s.error_code,error_message=s.error_message,
                result_summary=s.summary
            FROM jsonb_to_recordset(%s::jsonb) s({shape}) WHERE r.id=s.run_id""", (payload,))
        cur.execute(f"""UPDATE {common._table('operation_tasks')} t
            SET status=s.status,current_stage=s.stage,target_status='account_available',
                completed_at=CASE WHEN s.waiting THEN NULL ELSE COALESCE(s.child_completed_at,now()) END,
                error_category=s.error_category,error_code=s.error_code,error_message=s.error_message,
                next_actions=s.actions,updated_at=now()
            FROM jsonb_to_recordset(%s::jsonb) s({shape})
            WHERE t.id=s.task_id AND t.last_run_id=s.run_id""", (payload,))
        cur.execute(f"""INSERT INTO {common._table('operation_events')}
            (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
            SELECT s.event_uuid,s.task_id,s.run_id,'registration_completion',s.event_uuid,s.level,
                s.stage,'task.completion_updated',s.message,s.detail
            FROM jsonb_to_recordset(%s::jsonb) s({shape}) WHERE s.emit_event ON CONFLICT DO NOTHING""", (payload,))
    return batch_ids
