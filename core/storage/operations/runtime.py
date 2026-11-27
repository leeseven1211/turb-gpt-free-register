# -*- coding: utf-8 -*-
"""原生任务创建、执行、资源和依赖状态转换。事务内终态与资源释放由本模块统一拥有。"""
from __future__ import annotations

import logging
import json
import uuid
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from typing import Any, Iterable
from core.storage import records as record_store
from core.operations import run_log as task_run_log
from core.bulk_operations import execution as bulk_execution
from core.operations.runtime import OperationAccountDeactivated
from core.operations.progress import build_progress_snapshot
from core.operations.stages import normalize_stage, normalize_step_state
from core.storage.operations import common as _common
from core.storage.operations import schema as _schema
from core.storage.operations import projection as _projection

logger = logging.getLogger('core.storage.operation')

_REMOTE_INTENT_KINDS = frozenset({"remote_write", "read"})


_REMOTE_RECEIPT_OUTCOMES = frozenset({
    "confirmed", "rejected", "unknown", "response_received",
    "local_commit_required", "not_submitted",
})


def _finish_deactivated_before_execution(
    run_id: int,
    *,
    execution_id: str | None = None,
    lease_token: str | None = None,
) -> dict:
    """将尚未跨越远端边界的 Run 收口为已停用。"""
    return finish_run(
        int(run_id),
        status="deactivated",
        message="账号已确认停用，队列任务未执行",
        error="账号已确认停用，队列任务未执行",
        result_summary={
            "status": "deactivated",
            "requested_status": "deactivated",
            "reason": "account_deactivated_before_execution",
            "remote_request_started": False,
        },
        execution_id=execution_id,
        lease_token=lease_token,
    )


def register_task_dependency(
    *,
    parent_source_system: str,
    parent_source_id: str,
    child_source_system: str,
    child_source_id: str,
    dependency_type: str,
    payload: dict | None = None,
    expected_parent_run_id: int | None = None,
) -> dict:
    """Persist a parent/child handoff without coupling two ID namespaces.

    During the migration window a completion coordinator may still be a
    legacy ``account_action_tasks`` row while its Codex child is a native
    operation.  The dependency table is intentionally source-keyed instead
    of using a misleading cross-table foreign key.  Repeating the registration
    is idempotent and never resets an already-ready/completed child.
    """
    _schema.init_operation_schema()
    parent_system = _common._text(parent_source_system, 120)
    parent_id = _common._text(parent_source_id, 240)
    child_system = _common._text(child_source_system, 120)
    child_id = _common._text(child_source_id, 240)
    dependency = _common._text(dependency_type, 120)
    with _common._connect() as conn, conn.cursor() as cur, bulk_execution.dependency_update(conn, payload=payload):
        if expected_parent_run_id is not None:
            # Existing source ids can be synthetic; the original Run is the
            # unambiguous native parent identity and same-transaction CAS.
            cur.execute(f'''SELECT task.last_run_id,task.source_system,task.source_id,task.id
                FROM {_common._table('operation_tasks')} task
                JOIN {_common._table('operation_runs')} run ON run.task_id=task.id
                WHERE run.id=%s FOR UPDATE OF task''',(int(expected_parent_run_id),))
            parent=cur.fetchone()
            matches_source=(parent and str(parent['source_system'])==parent_system
                and (str(parent['source_id'])==parent_id or str(parent['id'])==parent_id))
            if (not matches_source or int(parent.get('last_run_id') or 0)!=int(expected_parent_run_id)):
                return {'status':'superseded','dependency_stale':True,
                        'expected_parent_run_id':int(expected_parent_run_id)}
        cur.execute(
            f"""
            INSERT INTO {_common._table('operation_task_dependencies')} (
                parent_source_system, parent_source_id, child_source_system,
                child_source_id, dependency_type, payload
            ) VALUES (%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (
                parent_source_system, parent_source_id, child_source_system,
                child_source_id, dependency_type
            ) DO UPDATE SET
                payload=EXCLUDED.payload,
                updated_at=now()
            RETURNING *
            """,
            (parent_system, parent_id, child_system, child_id, dependency, _common._json(payload or {})),
        )
        row = dict(cur.fetchone())
        # A fast child can reach a terminal state before the parent finishes
        # recording this handoff. Resolve that race at registration time so a
        # completed child never leaves a permanent ``waiting`` dependency.
        child = None
        try:
            child_number = int(child_id)
        except (TypeError, ValueError):
            child_number = None
        if child_system in {"native_operations", "webui_runtime"} and child_number is not None:
            cur.execute(
                f"""
                SELECT t.status AS task_status, r.status AS run_status,
                       r.result_summary
                FROM {_common._table('operation_tasks')} t
                LEFT JOIN {_common._table('operation_runs')} r ON r.id=t.last_run_id
                WHERE t.id=%s AND t.source_system=%s
                """,
                (child_number, child_system),
            )
            child = cur.fetchone()
        elif child_system == "account_action_tasks" and child_number is not None:
            cur.execute(
                f"SELECT status, result_summary FROM {_common._table('account_action_tasks')} WHERE id=%s",
                (child_number,),
            )
            child = cur.fetchone()
        else:
            cur.execute(
                f"""
                SELECT t.status AS task_status, r.status AS run_status,
                       r.result_summary
                FROM {_common._table('operation_tasks')} t
                LEFT JOIN {_common._table('operation_runs')} r ON r.id=t.last_run_id
                WHERE t.source_system=%s AND t.source_id=%s
                """,
                (child_system, child_id),
            )
            child = cur.fetchone()
        if child:
            child_status = _common._status(child.get("run_status") or child.get("task_status") or child.get("status"))
            if child_status in _common._TERMINAL_STATUSES and str(row.get("status") or "") == "waiting":
                cur.execute(
                    f"""
                    UPDATE {_common._table('operation_task_dependencies')}
                    SET status='ready', child_status=%s, child_result=%s::jsonb,
                        ready_at=now(), next_attempt_at=NULL, updated_at=now()
                    WHERE id=%s AND status='waiting'
                    RETURNING *
                    """,
                    (
                        child_status,
                        _common._json(_common._decode(child.get("result_summary")) or {}),
                        int(row["id"]),
                    ),
                )
                row = dict(cur.fetchone() or row)
        return _common._row(row) or {}


def mark_task_dependency_ready(
    *,
    child_source_system: str,
    child_source_id: str,
    child_status: str,
    child_result: dict | None = None,
    conn=None,
) -> list[dict]:
    """Make all waiting parents recoverably ready after a child reaches a terminal state."""
    if conn is None:
        _schema.init_operation_schema()
    status_value = _common._status(child_status)
    if status_value not in _common._TERMINAL_STATUSES:
        return []
    with (_common._connect() if conn is None else nullcontext(conn)) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_common._table('operation_task_dependencies')}
            SET status='ready', child_status=%s, child_result=%s::jsonb,
                ready_at=now(), next_attempt_at=NULL, last_error=NULL, updated_at=now()
            WHERE status='waiting' AND child_source_system=%s AND child_source_id=%s
            RETURNING *
            """,
            (
                status_value, _common._json(child_result or {}), _common._text(child_source_system, 120),
                _common._text(child_source_id, 240),
            ),
        )
        return [_common._row(dict(row)) or {} for row in cur.fetchall()]


def list_ready_task_dependencies(*, limit: int = 100, initialize: bool = True) -> list[dict]:
    """Read ready handoffs; callers claim them with :func:`claim_task_dependency`."""
    if initialize:
        _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT * FROM {_common._table('operation_task_dependencies')}
            WHERE status='ready'
              AND (next_attempt_at IS NULL OR next_attempt_at <= now())
            ORDER BY next_attempt_at NULLS FIRST, ready_at NULLS FIRST, id
            LIMIT %s
            """,
            (max(1, min(5000, int(limit or 100))),),
        )
        return [_common._row(dict(row)) or {} for row in cur.fetchall()]


def claim_task_dependency(dependency_id: int, *, initialize: bool = True, conn=None) -> dict | None:
    """Atomically claim one ready handoff so restart/reconcile cannot double-run it."""
    if initialize and conn is None:
        _schema.init_operation_schema()
    with (_common._connect() if conn is None else nullcontext(conn)) as conn, conn.cursor() as cur, bulk_execution.dependency_update(conn, dependency_id=dependency_id):
        cur.execute(
            f"""
            UPDATE {_common._table('operation_task_dependencies')}
            SET status='ready', next_attempt_at=NULL, updated_at=now()
            WHERE status='running' AND updated_at < now() - interval '15 minutes'
              AND NOT EXISTS (SELECT 1 FROM {_common._permit_table()} p
                WHERE p.execution_key='operation_dependency:' || id::text AND p.released_at IS NULL)
            """
        )
        cur.execute(
            f"""
            UPDATE {_common._table('operation_task_dependencies')}
            SET status='running', attempts=attempts + 1, next_attempt_at=NULL, updated_at=now()
            WHERE id=%s AND status='ready'
              AND (next_attempt_at IS NULL OR next_attempt_at <= now())
            RETURNING *
            """,
            (int(dependency_id),),
        )
        row = cur.fetchone()
        return _common._row(dict(row)) if row else None


def complete_task_dependency(
    dependency_id: int,
    *,
    success: bool,
    error: str | None = None,
) -> bool:
    """Ack a claimed handoff; failed continuation remains retryable as ``ready``."""
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur, bulk_execution.dependency_update(conn, dependency_id=dependency_id):
        cur.execute(
            f"""
            UPDATE {_common._table('operation_task_dependencies')}
            SET status=%s, last_error=%s,
                completed_at=CASE WHEN %s THEN now() ELSE NULL END,
                next_attempt_at=CASE WHEN %s THEN NULL ELSE now() + interval '1 second' END,
                ready_at=CASE WHEN %s THEN ready_at ELSE COALESCE(ready_at, now()) END,
                updated_at=now()
            WHERE id=%s AND status='running'
            """,
            (
                "completed" if success else "ready", _common._text(error, 1200) or None,
                bool(success), bool(success), bool(success), int(dependency_id),
            ),
        )
        return cur.rowcount > 0


def apply_task_dependency_result(
    *,
    parent_source_system: str,
    parent_source_id: str,
    child_status: str,
    child_result: dict | None = None,
    expected_parent_run_id: int | None = None,
) -> dict | None:
    """Persist a dependency failure/unknown outcome on its parent task.

    Runtime coordinators use their numeric logical task id as the parent
    source id while the task itself remains in its source namespace.  Other
    adapters may use the normal ``source_system/source_id`` pair.
    """
    _schema.init_operation_schema()
    parent_system = _common._text(parent_source_system, 120)
    parent_id = _common._text(parent_source_id, 240)
    child_status_value = _common._status(child_status)
    child_payload = dict(child_result or {})
    deactivated = child_status_value == "deactivated" or any(
        str(child_payload.get(key) or "").strip().lower() == "deactivated"
        for key in ("status", "requested_status")
    )
    unknown = child_status_value in {"request_unknown", "attention_required"} or (
        str(child_payload.get("outcome") or "").lower() == "request_unknown"
    )
    desired = "deactivated" if deactivated else "attention_required" if unknown else "partial_success"
    target_status = "account_deactivated" if deactivated else "attention_required"
    next_actions = [] if deactivated else (
        [{"action": "reconcile", "label": "确认远端结果后继续"}]
        if unknown else [{"action": "retry", "label": "重试失败子任务"}]
    )
    with _common._connect() as conn, conn.cursor() as cur:
        if parent_system == "webui_runtime" and parent_id.isdigit():
            cur.execute(
                f"SELECT * FROM {_common._table('operation_tasks')} WHERE id=%s",
                (int(parent_id),),
            )
        else:
            cur.execute(
                f"""
                SELECT * FROM {_common._table('operation_tasks')}
                WHERE source_system=%s AND source_id=%s
                """,
                (parent_system, parent_id),
            )
        parent = cur.fetchone()
        if not parent:
            return None
        parent = dict(parent)
        parent_task_id = int(parent["id"])
        observed_run_id = int(parent.get("last_run_id") or 0)
        if expected_parent_run_id is not None and observed_run_id != int(expected_parent_run_id):
            return {**(_common._row(parent) or {}), "dependency_stale": True}
        with bulk_execution.fact_update(conn, observed_run_id):
            # 与准入/终态写回保持 Run→Task 顺序；读取任务身份本身不先持任务行锁。
            cur.execute(
                f"SELECT * FROM {_common._table('operation_runs')} WHERE id=%s FOR UPDATE",
                (observed_run_id,),
            )
            parent_run = cur.fetchone()
            cur.execute(f"SELECT * FROM {_common._table('operation_tasks')} WHERE id=%s FOR UPDATE", (parent_task_id,))
            locked_parent = cur.fetchone()
            if not locked_parent:
                return None
            if int(locked_parent.get("last_run_id") or 0) != observed_run_id:
                return {**(_common._row(dict(locked_parent)) or {}), "dependency_stale": True}
            parent_summary = _common._decode(parent_run.get("result_summary")) if parent_run else {}
            parent_summary = dict(parent_summary) if isinstance(parent_summary, dict) else {}
            parent_summary.update({
                "child_status": child_status_value,
                "child_result": _common._scrub(child_payload),
            })
            if deactivated:
                parent_summary.update({"status": "deactivated", "requested_status": "deactivated"})
            elif unknown:
                parent_summary.update({"outcome": "request_unknown", "reconcile_required": True})
            cur.execute(
                f"""
                UPDATE {_common._table('operation_tasks')}
                SET status=%s, target_status=%s, current_stage='complete',
                    next_actions=%s::jsonb, completed_at=COALESCE(completed_at, now()),
                    updated_at=now(), error_message=%s
                WHERE id=%s
                """,
                (
                    desired, target_status, _common._json(next_actions),
                    _common._text(
                        "子任务已确认废号，父任务停止重跑"
                        if deactivated else "子任务远端结果待核验，父任务禁止自动重做"
                        if unknown else "子任务失败，父任务保留部分成功结果",
                        1400,
                    ),
                    parent_task_id,
                ),
            )
            if parent_run:
                cur.execute(
                    f"""
                    UPDATE {_common._table('operation_runs')}
                    SET status=%s, progress_stage='complete', completed_at=COALESCE(completed_at, now()),
                        heartbeat_at=now(), result_summary=%s::jsonb,
                        error_message=%s
                    WHERE id=%s
                    """,
                    (
                        desired, _common._json(parent_summary),
                        "子任务已确认废号，父任务停止重跑"
                        if deactivated else "子任务远端结果待核验，父任务禁止自动重做"
                        if unknown else "子任务失败，父任务保留部分成功结果",
                        int(parent_run["id"]),
                    ),
                )
            event_uuid = uuid.uuid4().hex
            cur.execute(
                f"""
                INSERT INTO {_common._table('operation_events')} (
                    event_uuid, task_id, run_id, source_system, source_id,
                    level, stage, event_type, message, detail
                ) VALUES (%s,%s,%s,%s,%s,'WARNING','complete',%s,%s,%s::jsonb)
                """,
                (
                    event_uuid, parent_task_id,
                    int(parent_run["id"]) if parent_run else None,
                    parent_system, event_uuid,
                    "task.dependency_deactivated" if deactivated else "task.dependency_unknown" if unknown else "task.dependency_failed",
                    "子任务已确认废号，父任务停止重跑" if deactivated else "子任务结果待核验，父任务暂停续接" if unknown else "子任务失败，父任务保留部分成功结果",
                    _common._json({"child_status": child_status_value, "child_result": child_payload}),
                ),
            )
            return _common._row(parent) or {}


def _reconcile_parent_task_cur(cur, parent_task_id: int, *, child_task_id: int | None = None) -> dict | None:
    """Advance a native parent from child states while holding one DB transaction."""
    cur.execute(
        f"SELECT * FROM {_common._table('operation_tasks')} WHERE id=%s",
        (int(parent_task_id),),
    )
    parent = cur.fetchone()
    if not parent:
        return None
    observed_run_id = int(parent.get("last_run_id") or 0)
    terminal_registration_child = False
    if str(parent.get("source_system") or "") == "registration_chains":
        cur.execute(f"SELECT data,status FROM {_common._table('operation_runs')} WHERE id=%s", (observed_run_id,))
        completion_parent = cur.fetchone() or {}
        auto_child = False
        if child_task_id:
            cur.execute(f"SELECT status,data->>'registration_completion' AS automatic FROM {_common._table('operation_tasks')} WHERE id=%s",
                        (int(child_task_id),))
            child_state = cur.fetchone() or {}
            auto_child = child_state.get("automatic") == "true"
            terminal_registration_child = child_state.get("status") in _common._TERMINAL_STATUSES
        if terminal_registration_child and (
            parent.get("status") in {"cancelled", "stopped"}
            or completion_parent.get("status") in {"cancelled", "stopped"}
        ):
            return None
        if auto_child or (_common._decode(completion_parent.get("data")) or {}).get("completion_handoff"):
            from core.storage.operations import registration_completion

            return registration_completion.reconcile(cur, observed_run_id)
    if observed_run_id:
        cur.execute(f"SELECT status FROM {_common._table('operation_runs')} WHERE id=%s FOR UPDATE", (observed_run_id,))
        locked_run = cur.fetchone() or {}
    else:
        locked_run = {}
    cur.execute(f"SELECT * FROM {_common._table('operation_tasks')} WHERE id=%s FOR UPDATE", (int(parent_task_id),))
    parent = cur.fetchone()
    if not parent or int(parent.get("last_run_id") or 0) != observed_run_id:
        return None
    if terminal_registration_child and (
        parent.get("status") in {"cancelled", "stopped"}
        or locked_run.get("status") in {"cancelled", "stopped"}
    ):
        # 迟到的补跑回执保留子任务结果，不撤销用户对原批次的取消或停止。
        return None
    if str(parent.get("task_type") or "") == "account_inspection_batch":
        # 巡检批次用定长聚合摘要，避免每个账号完成都重写全部子任务 JSON。
        from core.storage.accounts.inspections import reconcile_parent_cur

        return reconcile_parent_cur(cur, parent, child_task_id=child_task_id)
    cur.execute(
        f"""
        SELECT t.id, t.status, t.task_type, t.last_run_id,
               r.result_summary, r.error_message, r.error_code, r.data
        FROM {_common._table('operation_tasks')} t
        LEFT JOIN {_common._table('operation_runs')} r ON r.id=t.last_run_id
        WHERE t.parent_task_id=%s
        ORDER BY t.id
        """,
        (int(parent_task_id),),
    )
    children = [dict(row) for row in cur.fetchall()]
    if not children:
        return None
    active = [
        child for child in children
        if str(child.get("status") or "") in _common._ACTIVE_RUN_STATUSES
    ]
    if active:
        desired = "waiting"
        current_stage = "waiting"
        target_status = "pending"
        next_actions = [{"action": "await_child", "label": "等待子任务完成"}]
        completed_at_sql = "NULL"
        event_type = "task.waiting_for_child"
        message = "父任务等待子任务完成，未占用账号操作租约"
        level = "INFO"
    else:
        statuses = {str(child.get("status") or "") for child in children}
        if statuses and statuses <= {"success"}:
            desired = "success"
            target_status = "completed"
            next_actions = []
            message = "所有子任务已完成，父任务自动收口"
            level = "INFO"
        elif "deactivated" in statuses:
            desired = "deactivated"
            target_status = "account_deactivated"
            next_actions = []
            message = "子任务已确认废号，父任务停止重跑"
            level = "WARNING"
        elif "attention_required" in statuses or any(
            str(child.get("status") or "") == "failed"
            and str(child.get("task_type") or "") in {"token_refresh", "live_check"}
            and isinstance(summary := _common._decode(child.get("result_summary")), dict)
            and summary.get("outcome") == "request_unknown"
            and summary.get("cause_code") in {"password_change_required", "password_page_error"}
            for child in children
        ):
            desired = "attention_required"
            target_status = "attention_required"
            next_actions = [{"action": "reconcile", "label": "确认远端结果后继续"}]
            message = "子任务需要确认，父任务保留待对账状态"
            level = "WARNING"
        else:
            desired = "partial_success"
            target_status = "attention_required"
            next_actions = [{"action": "retry", "label": "重试失败子任务"}]
            message = "子任务已结束，父任务保留部分成功结果"
            level = "WARNING"
        current_stage = "complete"
        completed_at_sql = "now()"
        event_type = "task.children_reconciled"
    cur.execute(
        f"""
        UPDATE {_common._table('operation_tasks')}
        SET status=%s, target_status=%s, current_stage=%s,
            next_actions=%s::jsonb, completed_at={completed_at_sql}, updated_at=now()
        WHERE id=%s
        """,
        (desired, target_status, current_stage, _common._json(next_actions), int(parent_task_id)),
    )
    parent_source_system = str(parent.get("source_system") or "native_operations")
    parent_run_id = int(parent.get("last_run_id") or 0) or None
    if parent_run_id:
        cur.execute(
            f"SELECT * FROM {_common._table('operation_runs')} WHERE id=%s FOR UPDATE",
            (parent_run_id,),
        )
        parent_run = cur.fetchone()
        # 协调任务的终态仅表示上一轮子任务已经结束。子任务重跑时建立新的
        # waiting Run，保留旧终态 Run 的审计记录，同时让读模型指向当前协调态。
        if (
            parent_run
            and desired == "waiting"
            and str(parent_run.get("status") or "") in _common._TERMINAL_STATUSES
        ):
            cur.execute(
                f"SELECT COALESCE(MAX(run_no), 0) + 1 AS n FROM {_common._table('operation_runs')} WHERE task_id=%s",
                (int(parent_task_id),),
            )
            replacement = _insert_runtime_run(
                cur,
                task_id=int(parent_task_id),
                run_no=int(cur.fetchone()["n"]),
                source_system=parent_source_system,
                account_id=int(parent["account_id"]) if parent.get("account_id") else None,
                batch_id=parent_run.get("batch_id") or parent.get("batch_id"),
                resource_family=str(parent_run.get("resource_family") or "completion_coordinator"),
                data=_common._decode(parent_run.get("data")) or _common._decode(parent.get("data")) or {},
                initial_status="waiting",
            )
            parent_run = replacement
            parent_run_id = int(replacement["id"])
            cur.execute(
                f"UPDATE {_common._table('operation_tasks')} SET last_run_id=%s WHERE id=%s",
                (parent_run_id, int(parent_task_id)),
            )
        if parent_run and str(parent_run.get("status") or "") not in _common._TERMINAL_STATUSES:
            summary = _common._decode(parent_run.get("result_summary"))
            summary = dict(summary) if isinstance(summary, dict) else {}
            summary["children"] = {
                str(child["id"]): str(child.get("status") or "") for child in children
            }
            summary["child_tasks"] = []
            for child in children:
                child_summary = _common._decode(child.get("result_summary")) or {}
                child_data = _common._decode(child.get("data")) or {}
                summary["child_tasks"].append({
                    "task_id": int(child["id"]), "run_id": child.get("last_run_id"),
                    "task_type": child.get("task_type"), "status": child.get("status"),
                    "failure_stage": child_summary.get("failure_stage") or child_data.get("failure_stage"),
                    "failure_event_id": child_summary.get("failure_event_id") or child_data.get("failure_event_id"),
                    "error_code": child.get("error_code") or child_summary.get("error_code") or child_data.get("error_code"),
                    "error_message": task_run_log.redact_text(child.get("error_message") or child_summary.get("error_message") or child_data.get("failure_message") or "", 500),
                })
            cur.execute(
                f"""
                UPDATE {_common._table('operation_runs')}
                SET status=%s, progress_stage=%s, heartbeat_at=now(),
                    completed_at=CASE WHEN %s THEN now() ELSE NULL END,
                    result_summary=%s::jsonb,
                    duration_ms=CASE WHEN %s THEN GREATEST(0,
                        (EXTRACT(EPOCH FROM (now() - COALESCE(started_at, created_at))) * 1000)::BIGINT)
                        ELSE duration_ms END
                WHERE id=%s
                """,
                (
                    desired, current_stage, desired != "waiting", _common._json(summary),
                    desired != "waiting", parent_run_id,
                ),
            )
            if desired == "waiting":
                # A coordinator must release any accidentally retained account
                # lease before its child can acquire that account/family.
                cur.execute(
                    f"DELETE FROM {_common._table('account_operation_leases')} WHERE run_id=%s",
                    (parent_run_id,),
                )
            event_uuid = uuid.uuid4().hex
            cur.execute(
                f"""
                INSERT INTO {_common._table('operation_events')} (
                    event_uuid, task_id, run_id, source_system, source_id,
                    level, stage, event_type, message, detail
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'{{}}'::jsonb)
                """,
                (
                    event_uuid, int(parent_task_id), parent_run_id, parent_source_system,
                    event_uuid, level,
                    current_stage, event_type, _common._text(message, 1400),
                ),
            )
    batch_id = parent.get("batch_id")
    if batch_id:
        _projection._refresh_batches(cur, [int(batch_id)])
    return {
        "parent_task_id": int(parent_task_id),
        "status": desired,
        "child_task_id": int(child_task_id) if child_task_id else None,
        "children": [{"id": int(child["id"]), "status": child.get("status")} for child in children],
    }


def _reconcile_parent_task(parent_task_id: int) -> dict | None:
    """Public transaction boundary for a native parent/child reconciliation."""
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        return _reconcile_parent_task_cur(cur, int(parent_task_id))


def create_runtime_batch(
    *, batch_type: str, title: str, requested_count: int, trigger: str = "manual",
    data: dict | None = None,
) -> dict:
    """创建真正参与调度的批次；批次只持有 run 引用，不预占账号资源。"""
    _schema.init_operation_schema()
    batch_uuid = uuid.uuid4().hex
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {_common._table('operation_batches')} (
                batch_uuid, source_system, source_id, batch_type, title, status,
                requested_count, created_by, data
            ) VALUES (%s, 'native_operations', %s, %s, %s, 'queued', %s, %s, %s::jsonb)
            RETURNING *
            """,
            (
                batch_uuid, batch_uuid, str(batch_type), _common._text(title, 240),
                max(0, int(requested_count or 0)), str(trigger or "manual"), _common._json(data or {}),
            ),
        )
        return _common._row(dict(cur.fetchone())) or {}


def _insert_runtime_run(
    cur,
    *,
    task_id: int,
    run_no: int,
    source_system: str,
    account_id: int | None,
    batch_id: int | None,
    resource_family: str,
    data: dict | None,
    initial_status: str = "queued",
    task_uuid: str | None = None,
) -> dict:
    status_value = "waiting" if str(initial_status or "").strip().lower() == "waiting" else "queued"
    run_uuid = uuid.uuid4().hex
    cancellation_token = uuid.uuid4().hex
    if not task_uuid:
        cur.execute(f"SELECT task_uuid FROM {_common._table('operation_tasks')} WHERE id=%s", (int(task_id),))
        task_row = cur.fetchone()
        if not task_row:
            raise LookupError("任务不存在")
        task_uuid = str(task_row["task_uuid"])
    log_file = task_run_log.build_path(
        task_uuid=str(task_uuid), run_no=int(run_no), run_uuid=run_uuid,
    )
    cur.execute(
        f"""
        INSERT INTO {_common._table('operation_runs')} (
            run_uuid, task_id, run_no, source_system, source_id, status,
            batch_id, account_id, resource_family, cancellation_token, log_file, data
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING *
        """,
        (
            run_uuid, int(task_id), int(run_no), str(source_system), run_uuid, status_value,
            batch_id, account_id,
            str(resource_family or "openai_interactive"), cancellation_token, log_file, _common._json(data or {}),
        ),
    )
    run = dict(cur.fetchone())
    event_uuid = uuid.uuid4().hex
    cur.execute(
        f"""
        INSERT INTO {_common._table('operation_events')} (
            event_uuid, task_id, run_id, source_system, source_id,
            level, stage, event_type, message, detail
        ) VALUES (%s,%s,%s,%s,%s,'INFO',%s,%s,%s,'{{}}'::jsonb)
        """,
        (
            event_uuid, int(task_id), int(run["id"]), str(source_system), event_uuid,
            status_value,
            "run.waiting" if status_value == "waiting" else "run.queued",
            "任务等待子任务完成" if status_value == "waiting" else "任务已加入队列",
        ),
    )
    if not (data or {}).get("bulk_target_round_id"):
        task_run_log.append(
            log_file, level="INFO", message="任务等待子任务完成" if status_value == "waiting" else "任务已加入队列",
            task_id=int(task_id), run_id=int(run["id"]), stage=status_value,
            event_type="run.waiting" if status_value == "waiting" else "run.queued",
        )
    return run


def create_runtime_task(
    *,
    task_type: str,
    account_id: int | None,
    email: str,
    trigger: str = "manual",
    batch_id: int | None = None,
    batch_ordinal: int | None = None,
    parent_task_id: int | None = None,
    resource_family: str = "openai_interactive",
    data: dict | None = None,
    source_system: str = "native_operations",
    source_id: str | None = None,
    idempotency_key: str | None = None,
    account_request: bool = False,
    lock_account_request: bool = False,
    claim_before_create: Callable[[Any], bool] | None = None,
    conn=None,
) -> dict:
    """原子创建逻辑任务和第一次执行。

    ``source_id``/``idempotency_key`` are optional external submission keys.
    When supplied, a retried HTTP request returns the existing logical task and
    current run instead of creating another remote action.  The account/family
    partial unique index remains the second, database-enforced duplicate guard.
    """
    _schema.init_operation_schema()
    task_uuid = uuid.uuid4().hex
    source_system_value = str(source_system or "native_operations").strip()[:120] or "native_operations"
    source_value = str(source_id or idempotency_key or "").strip() or task_uuid
    account_value = int(account_id) if account_id else None
    managed_source_run_id = bulk_execution.source_run_for_creation(account_id=account_value, data=data)
    with (_common._connect() if conn is None else nullcontext(conn)) as conn, conn.cursor() as cur:
        if lock_account_request:
            # 共享邮箱的锚点可能改变，同一个目标集合仍共用一把事务锁。
            record_store.advisory_xact_lock(conn, source_value)
        managed = bulk_execution.lock_run(conn, managed_source_run_id) if managed_source_run_id else None
        if managed:
            data = {**(data or {}), "bulk_target_round_id": int(managed["id"])}
        if account_value:
            account = (_common._settlement_account(cur, account_value, for_update=True)
                       if _common.current_settlement_domain() is not None else record_store.get_row(
                record_store.ACCOUNTS,
                account_value,
                conn=conn,
                for_update=True,
            ))
            if not account_request and _common._account_is_deactivated(account):
                raise OperationAccountDeactivated("账号已废号，禁止创建任务")
        if source_id or idempotency_key:
            cur.execute(
                f"""
                SELECT * FROM {_common._table('operation_tasks')}
                WHERE source_system=%s AND source_id=%s
                FOR UPDATE
                """,
                (source_system_value, source_value),
            )
            existing = cur.fetchone()
            if existing:
                if account_request and _common._task_is_user_deleted(dict(existing)):
                    return {"request_rejected": {"error": "原任务已从任务中心删除，请重新发起操作"}}
                order = "ASC" if account_request else "DESC"
                cur.execute(
                    f"""
                    SELECT * FROM {_common._table('operation_runs')}
                    WHERE task_id=%s ORDER BY run_no {order}, id {order} LIMIT 1
                    """,
                    (int(existing["id"]),),
                )
                current_run = cur.fetchone()
                result = _common._row(dict(existing)) or {}
                result["run"] = _common._row(dict(current_run)) if current_run else None
                result["idempotent"] = True
                return result
        if account_request and account_value and _common._account_is_deactivated(account):
            raise OperationAccountDeactivated("账号已废号，禁止创建任务")
        if claim_before_create is not None and not claim_before_create(conn):
            return {"request_rejected": {"busy": True, "error": "该账号已有排队或运行中的账号操作"}}
        cur.execute(
            f"""
            INSERT INTO {_common._table('operation_tasks')} (
                task_uuid, source_system, source_id, batch_id, parent_task_id,
                task_type, target_type, target_id, account_id, email_snapshot,
                requested_action, status, target_status, current_stage,
                next_actions, trigger, data
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, 'account', %s, %s, %s,
                %s, 'queued', 'pending', 'queued',
                '[]'::jsonb, %s, %s::jsonb
            ) RETURNING *
            """,
            (
                task_uuid, source_system_value, source_value, batch_id, parent_task_id, str(task_type),
                account_value, account_value, str(email or "").strip(), str(task_type),
                str(trigger or "manual"), _common._json(data or {}),
            ),
        )
        task = dict(cur.fetchone())
        if not task.get("parent_task_id"):
            cur.execute(
                f"UPDATE {_common._table('operation_tasks')} SET root_task_id=id WHERE id=%s",
                (int(task["id"]),),
            )
        else:
            cur.execute(
                f"""
                UPDATE {_common._table('operation_tasks')} child
                SET root_task_id=COALESCE(parent.root_task_id, parent.id)
                FROM {_common._table('operation_tasks')} parent
                WHERE child.id=%s AND parent.id=child.parent_task_id
                """,
                (int(task["id"]),),
            )
        run = _insert_runtime_run(
            cur,
            task_id=int(task["id"]),
            run_no=1,
            task_uuid=task_uuid,
            source_system=source_system_value,
            account_id=account_value,
            batch_id=int(batch_id) if batch_id else None,
            resource_family=resource_family,
            data=data,
        )
        if managed:
            bulk_execution.inherit(conn, int(run["id"]), source_run_id=managed_source_run_id, step_key=str(task_type), parent_task_id=int(managed.get("task_id") or 0) or int(task["id"]))
            bulk_execution.changed(conn, managed)
        cur.execute(
            f"UPDATE {_common._table('operation_tasks')} SET last_run_id=%s WHERE id=%s",
            (int(run["id"]), int(task["id"])),
        )
        if batch_id:
            ordinal = int(batch_ordinal or 0)
            if ordinal <= 0:
                cur.execute(
                    f"SELECT COALESCE(MAX(ordinal), 0) + 1 AS n FROM {_common._table('operation_batch_items')} WHERE batch_id=%s",
                    (int(batch_id),),
                )
                ordinal = int(cur.fetchone()["n"])
            cur.execute(
                f"""
                INSERT INTO {_common._table('operation_batch_items')} (batch_id, task_id, run_id, ordinal)
                VALUES (%s, %s, %s, %s)
                """,
                (int(batch_id), int(task["id"]), int(run["id"]), ordinal),
            )
        task = _common._row(task) or {}
        task["run"] = _common._row(run) or {}
        task["idempotent"] = False
        if parent_task_id:
            _reconcile_parent_task_cur(cur, int(parent_task_id), child_task_id=int(task["id"]))
        return task


def create_runtime_tasks_many(specifications: list[dict], *, conn) -> list[dict]:
    """在已持账号锁的批量事务中集合创建 Task、Run 和排队事件。"""
    if not specifications:
        return []
    rows = []
    for spec in specifications:
        data = dict(spec.get("data") or {})
        if not data.get("bulk_target_round_id"):
            raise ValueError("集合提交仅接受带固定批量目标的任务")
        task_uuid, run_uuid = uuid.uuid4().hex, uuid.uuid4().hex
        rows.append({
            "task_uuid": task_uuid, "run_uuid": run_uuid,
            "source_system": str(spec.get("source_system") or "native_operations"),
            "source_id": str(spec["source_id"]), "task_type": str(spec["task_type"]),
            "account_id": int(spec["account_id"]), "email": str(spec.get("email") or ""),
            "resource_family": str(spec.get("resource_family") or "openai_interactive"),
            "trigger": str(spec.get("trigger") or "manual_bulk"), "data": _common._scrub(data),
            "cancellation_token": uuid.uuid4().hex,
            "log_file": str(task_run_log.build_path(task_uuid=task_uuid, run_no=1, run_uuid=run_uuid)),
            "event_uuid": uuid.uuid4().hex,
        })
    with conn.cursor() as cur:
        cur.execute(f"""SELECT t.*,r.id AS owned_run_id FROM {_common._table('operation_tasks')} t
          JOIN jsonb_to_recordset(%s::jsonb) AS s(source_system TEXT,source_id TEXT)
            ON s.source_system=t.source_system AND s.source_id=t.source_id
          LEFT JOIN {_common._table('operation_runs')} r ON r.id=t.last_run_id""", (json.dumps(rows, ensure_ascii=False),))
        existing = {(row["source_system"], row["source_id"]): dict(row) for row in cur.fetchall()}
        fresh = [row for row in rows if (row["source_system"], row["source_id"]) not in existing]
        created = {}
        if fresh:
            payload = json.dumps(fresh, ensure_ascii=False)
            cur.execute(f"""INSERT INTO {_common._table('operation_tasks')}
              (task_uuid,source_system,source_id,task_type,target_type,target_id,account_id,email_snapshot,
               requested_action,status,target_status,current_stage,next_actions,trigger,data)
              SELECT s.task_uuid,s.source_system,s.source_id,s.task_type,'account',s.account_id,s.account_id,s.email,
                     s.task_type,'queued','pending','queued','[]'::jsonb,s.trigger,s.data
              FROM jsonb_to_recordset(%s::jsonb) AS s(task_uuid TEXT,source_system TEXT,source_id TEXT,
                task_type TEXT,account_id BIGINT,email TEXT,trigger TEXT,data JSONB)
              RETURNING id,task_uuid,source_system,source_id""", (payload,))
            tasks = {row["task_uuid"]: dict(row) for row in cur.fetchall()}
            for row in fresh:
                row["task_id"] = int(tasks[row["task_uuid"]]["id"])
            payload = json.dumps(fresh, ensure_ascii=False)
            cur.execute(f"""INSERT INTO {_common._table('operation_runs')}
              (run_uuid,task_id,run_no,source_system,source_id,status,account_id,resource_family,cancellation_token,log_file,data)
              SELECT s.run_uuid,s.task_id,1,s.source_system,s.run_uuid,'queued',s.account_id,s.resource_family,s.cancellation_token,s.log_file,s.data
              FROM jsonb_to_recordset(%s::jsonb) AS s(run_uuid TEXT,task_id BIGINT,source_system TEXT,
                account_id BIGINT,resource_family TEXT,cancellation_token TEXT,log_file TEXT,data JSONB)
              RETURNING id,task_id""", (payload,))
            runs = {int(row["task_id"]): int(row["id"]) for row in cur.fetchall()}
            for row in fresh:
                row["run_id"] = runs[row["task_id"]]
                created[(row["source_system"], row["source_id"])] = row
            payload = json.dumps(fresh, ensure_ascii=False)
            cur.execute(f"""UPDATE {_common._table('operation_tasks')} t SET root_task_id=t.id,last_run_id=s.run_id
              FROM jsonb_to_recordset(%s::jsonb) AS s(task_id BIGINT,run_id BIGINT) WHERE t.id=s.task_id""", (payload,))
            cur.execute(f"""INSERT INTO {_common._table('operation_events')}
              (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
              SELECT s.event_uuid,s.task_id,s.run_id,s.source_system,s.event_uuid,'INFO','queued','run.queued','任务已加入队列','{{}}'::jsonb
              FROM jsonb_to_recordset(%s::jsonb) AS s(event_uuid TEXT,task_id BIGINT,run_id BIGINT,source_system TEXT)""", (payload,))
        output = []
        for row in rows:
            identity = (row["source_system"], row["source_id"])
            prior = existing.get(identity)
            if prior:
                if int(prior.get("account_id") or 0) != row["account_id"] or prior.get("task_type") != row["task_type"]:
                    raise ValueError("幂等任务身份与批量目标不一致")
                output.append({"accepted": True, "task_id": int(prior["id"]), "run_id": int(prior["owned_run_id"]), "reused": True})
            else:
                item = created[identity]
                output.append({"accepted": True, "task_id": item["task_id"], "run_id": item["run_id"], "reused": False})
        return output


def _remote_write_checkpoint(data: Any) -> dict:
    payload = _common._decode(data)
    intent = payload.get("remote_intent") if isinstance(payload, dict) else None
    if isinstance(intent, dict) and intent.get("kind") == "remote_write":
        return intent
    return {}


def retry_runtime_task(task_id: int, *, trigger: str = "manual_retry", data: dict | None = None,
                       expected_previous_run_id: int | None = None, conn=None) -> dict:
    """在同一逻辑任务下新建 attempt；不会制造第二条逻辑任务。"""
    if conn is None:
        _schema.init_operation_schema()
    with (_common._connect() if conn is None else nullcontext(conn)) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT account_id,last_run_id FROM {_common._table('operation_tasks')} WHERE id=%s", (int(task_id),))
        identity = cur.fetchone() or {}
        source_run_id = int(identity.get("last_run_id") or 0)
        # 新轮已有新target锁；依赖续接继续使用原轮target。
        managed = None
        new_target = (data or {}).get("bulk_target_round_id")
        if source_run_id and not new_target:
            managed = bulk_execution.lock_run(conn, source_run_id)
        if (managed or new_target) and identity.get("account_id"):
            record_store.get_row(record_store.ACCOUNTS, int(identity["account_id"]), conn=conn, for_update=True)
        cur.execute(
            f"SELECT * FROM {_common._table('operation_tasks')} WHERE id=%s FOR UPDATE",
            (int(task_id),),
        )
        task = cur.fetchone()
        if not task:
            raise LookupError("任务不存在")
        if expected_previous_run_id is not None and int(task.get("last_run_id") or 0) != int(expected_previous_run_id):
            return {"id": task.get("last_run_id"), "task_id": int(task_id), "dependency_stale": True}
        if str(task.get("source_system") or "") in {"registration_jobs", "account_action_tasks"}:
            raise ValueError("历史兼容任务需先迁移为原生任务后再重跑")
        task_status = str(task.get("status") or "").strip().lower()
        if task_status in _common._ACTIVE_RUN_STATUSES:
            raise ValueError("任务仍在执行")
        cur.execute(
            f"SELECT COALESCE(MAX(run_no), 0) + 1 AS n FROM {_common._table('operation_runs')} WHERE task_id=%s",
            (int(task_id),),
        )
        run_no = int(cur.fetchone()["n"])
        merged_data = dict(_common._decode(task.get("data")) or {})
        merged_data.update(data or {})
        merged_data["retry_trigger"] = str(trigger or "manual_retry")
        cur.execute(
            f"""
            SELECT id, status, resource_family, batch_id, data, result_summary
            FROM {_common._table('operation_runs')}
            WHERE task_id=%s ORDER BY run_no DESC, id DESC LIMIT 1
            """,
            (int(task_id),),
        )
        previous_run = cur.fetchone() or {}
        if str(previous_run.get("status") or "").strip().lower() in _common._ACTIVE_RUN_STATUSES:
            raise ValueError("任务仍在执行")
        summary = _common._decode(previous_run.get("result_summary")) or {}
        account_id = int(task.get("account_id") or 0)
        account = (
            record_store.get_row(
                record_store.ACCOUNTS, account_id, conn=conn, for_update=True,
            )
            if account_id else None
        )
        target_status = str(task.get("target_status") or "").strip().lower()
        summary_statuses = {
            str(summary.get(key) or "").strip().lower()
            for key in ("status", "requested_status")
        } if isinstance(summary, dict) else set()
        if (
            task_status == "deactivated"
            or target_status in {"deactivated", "account_deactivated"}
            or "deactivated" in summary_statuses
            or _common._account_is_deactivated(account)
        ):
            raise ValueError("账号已废号，禁止重跑")
        task_type = str(task.get("task_type") or "").strip()
        if task_type in {"live_check", "token_refresh"} and account_id and account:
            # 持久化重试和账号侧投影必须是同一个状态迁移。否则 worker 可能先收到新 Run，
            # 而 mark_account_live_check_running 仍读到 request_unknown，在发起外部请求前取消任务。
            queued_at = _common._now().isoformat(timespec="seconds")
            record_store.patch_row(
                record_store.ACCOUNTS,
                account_id,
                changes={
                    "live_check_status": "queued",
                    "live_check_ok": False,
                    "live_check_trigger": str(trigger or "manual_retry"),
                    "live_check_queued_at": queued_at,
                    "live_check_started_at": None,
                    "live_checked_at": None,
                    "live_check_error": None,
                    "live_check_http_status": None,
                    "updated_at": queued_at,
                },
                conn=conn,
            )
        elif task_type == "plan_check" and account_id and account:
            # 套餐查询 worker 只接受已排队的账号投影；状态重置与新 Run 必须同事务提交。
            # 只清理本次查询状态，保留之前成功取得的套餐、优惠和额度。
            queued_at = _common._now().isoformat(timespec="seconds")
            record_store.patch_row(
                record_store.ACCOUNTS,
                account_id,
                changes={
                    "plan_check_status": "queued",
                    "plan_check_ok": False,
                    "plan_check_trigger": str(trigger or "manual_retry"),
                    "plan_check_queued_at": queued_at,
                    "plan_check_started_at": None,
                    "plan_check_deadline_at": None,
                    "plan_check_completed_at": None,
                    "plan_check_error": None,
                    "plan_check_http_status": None,
                    "updated_at": queued_at,
                },
                conn=conn,
            )
        previous_data = _common._decode(previous_run.get("data"))
        if isinstance(previous_data, dict):
            previous_data = dict(previous_data)
            previous_data.update(merged_data)
            merged_data = previous_data
        if managed:
            # Task数据保留首轮身份；后轮自动续接必须继承确切上一Run归属。
            merged_data["bulk_target_round_id"] = int(managed["id"])
        # Clear after merging the previous Run, otherwise its checkpoints are
        # copied back into the supposedly fresh attempt.
        merged_data.pop("remote_intent", None)
        merged_data.pop("remote_receipt", None)
        run = _insert_runtime_run(
            cur,
            task_id=int(task_id),
            run_no=run_no,
            source_system=str(task.get("source_system") or "native_operations"),
            account_id=int(task["account_id"]) if task.get("account_id") else None,
            batch_id=previous_run.get("batch_id"),
            resource_family=str(previous_run.get("resource_family") or "openai_interactive"),
            data=merged_data,
        )
        if managed:
            bulk_execution.inherit(conn, int(run["id"]), source_run_id=source_run_id, step_key=task_type)
            bulk_execution.changed(conn, managed)
        if (
            task_type == "extract_link"
            and str(task.get("source_system") or "") == "native_operations"
            and str(merged_data.get("workbench_action") or "") == "sync_status"
        ):
            try:
                source_run_id = int(merged_data.get("provider_job_run_id") or previous_run.get("id") or 0)
            except (TypeError, ValueError, OverflowError):
                source_run_id = 0
            provider_id = str(merged_data.get("provider_id") or "").strip()
            if source_run_id > 0 and provider_id:
                # 同步排队即切换最新 Run，因此必须同时复制原单快照，保留已取得的提链事实。
                # 只复制同一任务、同一平台的 Provider 记录；凭据仍留在私有列中。
                cur.execute(
                    f"""
                    INSERT INTO {_common._table('extract_link_provider_jobs')} (
                        run_id, provider_id, job_id, extraction_state, payment_state,
                        public_state, private_data
                    )
                    SELECT %s, job.provider_id, job.job_id, job.extraction_state,
                           job.payment_state, job.public_state, job.private_data
                    FROM {_common._table('extract_link_provider_jobs')} job
                    JOIN {_common._table('operation_runs')} source_run ON source_run.id=job.run_id
                    WHERE source_run.id=%s AND source_run.task_id=%s AND job.provider_id=%s
                    """,
                    (int(run["id"]), source_run_id, int(task_id), provider_id),
                )
        cur.execute(
            f"""
            UPDATE {_common._table('operation_tasks')}
            SET status='queued', target_status='pending', current_stage='queued',
                last_run_id=%s, error_category=NULL, error_code=NULL, error_message=NULL,
                completed_at=NULL, next_actions='[]'::jsonb, updated_at=now(), trigger=%s
            WHERE id=%s
            """,
            (int(run["id"]), str(trigger or "manual_retry"), int(task_id)),
        )
        refreshed_batch_ids = {
            int(value)
            for value in (task.get("batch_id"), previous_run.get("batch_id"))
            if value
        }
        parent_task_id = int(task.get("parent_task_id") or 0)
        if parent_task_id:
            _reconcile_parent_task_cur(
                cur,
                parent_task_id,
                child_task_id=int(task_id),
            )
            cur.execute(
                f"SELECT batch_id FROM {_common._table('operation_tasks')} WHERE id=%s",
                (parent_task_id,),
            )
            parent_row = cur.fetchone() or {}
            if parent_row.get("batch_id"):
                refreshed_batch_ids.add(int(parent_row["batch_id"]))
        if refreshed_batch_ids:
            _projection._refresh_batches(cur, sorted(refreshed_batch_ids))
        if task_type == "password_setup":
            from core.storage.operations import registration_completion

            registration_completion.reconcile_for_child(cur, int(task_id))
        return _common._row(run) or {}


def get_run(run_id: int) -> dict | None:
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.*, t.task_type, t.email_snapshot, t.trigger, t.parent_task_id
            FROM {_common._table('operation_runs')} r
            JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.id=%s
            """,
            (int(run_id),),
        )
        raw = cur.fetchone()
        result = _common._row(dict(raw)) if raw else None
        if result is not None:
            _common._attach_admission_wait([result], conn=conn, run_rows=True)
        return result


def active_run_for_account(account_id: int, resource_family: str = "openai_interactive", *, conn=None) -> dict | None:
    _schema.init_operation_schema()
    with (_common._connect() if conn is None else nullcontext(conn)) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.*, t.email_snapshot, t.task_type
            FROM {_common._table('operation_runs')} r
            JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.account_id=%s AND r.resource_family=%s
              AND r.status IN ('queued', 'running', 'cancelling', 'settling', 'stopping')
            ORDER BY r.id DESC LIMIT 1
            """,
            (int(account_id), str(resource_family)),
        )
        raw = cur.fetchone()
        return _common._row(dict(raw)) if raw else None


def list_queued_runs(*, limit: int = 500) -> list[dict]:
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.*, t.email_snapshot, t.task_type
            FROM {_common._table('operation_runs')} r
            JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.source_system='native_operations' AND r.status='queued'
              AND r.cancel_requested_at IS NULL
              AND (r.next_attempt_at IS NULL OR r.next_attempt_at <= now())
            ORDER BY r.created_at, r.id LIMIT %s
            """,
            (max(1, min(5000, int(limit or 500))),),
        )
        return [_common._row(dict(row)) or {} for row in cur.fetchall()]


def _extract_batch_workers_sql(alias: str = "b") -> str:
    """旧批次及其他业务不启用提链工作台的每批并发门限。"""
    return f"""CASE WHEN {alias}.batch_type='extract_link'
        AND {alias}.data->>'workbench_batch'='true'
        AND jsonb_typeof({alias}.data->'workers')='number'
        AND ({alias}.data->>'workers') ~ '^([1-9]|[1-4][0-9]|50)$'
        THEN ({alias}.data->>'workers')::integer END"""


def _extract_batch_has_capacity_sql() -> str:
    workers = _extract_batch_workers_sql()
    return f"""(({workers}) IS NULL OR
        (SELECT COUNT(*) FROM {_common._table('operation_runs')} batch_active
         WHERE batch_active.batch_id=r.batch_id
           AND batch_active.status IN ('running','waiting','cancelling','settling','stopping')) < ({workers}))"""


def _claim_extract_batch_capacity(conn, cur, run: dict) -> bool:
    """在认领事务内串行核验同批次，避免多个服务进程同时越过门限。"""
    batch_id = run.get("batch_id")
    if not batch_id:
        return True
    cur.execute(f"SELECT {_extract_batch_workers_sql()} AS workers FROM {_common._table('operation_batches')} b WHERE b.id=%s", (int(batch_id),))
    batch = cur.fetchone()
    workers = (batch or {}).get("workers")
    if workers is None:
        return True
    record_store.advisory_xact_lock(conn, f"{_common._table('operation_batches')}:extract-workers:{int(batch_id)}")
    cur.execute(
        f"""SELECT COUNT(*) AS active FROM {_common._table('operation_runs')}
            WHERE batch_id=%s AND status IN ('running','waiting','cancelling','settling','stopping')""",
        (int(batch_id),),
    )
    return int(cur.fetchone()["active"]) < int(workers)


def list_dispatchable_runs(
    *,
    limit: int = 500,
    task_types: Iterable[str] | None = None,
    source_systems: Iterable[str] | None = None,
    prioritize_continuations: bool = False,
) -> list[dict]:
    """List current queued runs for gateway-registered task handlers.

    Unlike the historical Codex-only query, this is task-type based and only
    applies an optional source allowlist supplied by the gateway. A
    compatibility projection can therefore be migrated one task type at a
    time, while unregistered types remain durable but are not accidentally
    executed by this dispatcher.
    """
    _schema.init_operation_schema()
    values = [str(item).strip() for item in (task_types or ()) if str(item).strip()]
    source_values = (
        [str(item).strip() for item in source_systems if str(item).strip()]
        if source_systems is not None else None
    )
    if source_values is not None and not source_values:
        return []
    clauses = [
        "r.status='queued'",
        "r.cancel_requested_at IS NULL",
        "(r.next_attempt_at IS NULL OR r.next_attempt_at <= now())",
        "t.last_run_id=r.id",
        _extract_batch_has_capacity_sql(),
    ]
    params: list[Any] = []
    if values:
        clauses.append("t.task_type = ANY(%s)")
        params.append(values)
    if source_values is not None:
        clauses.append("t.source_system = ANY(%s)")
        params.append(source_values)
    scan_limit = max(1, min(5000, int(limit or 500)))
    continuation = f"""(t.task_type='extract_link' AND (
        (r.data->>'provider_id' IN ('huanguang', 'legacy', 'anguang')
         AND r.data->'extract_poll_continuation'='true'::jsonb)
        OR (r.data->>'payment_source'='xxsyun'
            AND r.data->>'workbench_action' IN ('sync_status','payment_sync')
            AND EXISTS (SELECT 1 FROM {_common._table('extract_link_payment_orders')} payment
                WHERE payment.task_id=r.task_id AND payment.payment_provider='xxsyun'
                AND NULLIF(payment.remote_order_id,'') IS NOT NULL))))"""
    base_query = f"""
        SELECT r.*, t.email_snapshot, t.task_type, t.source_system,
               CASE WHEN t.task_type='account_inspection' THEN (
                   SELECT CASE WHEN parent.data->>'workers' ~ '^[1-9][0-9]*$'
                       THEN (parent.data->>'workers')::integer END
                   FROM {_common._table('operation_tasks')} parent WHERE parent.id=t.parent_task_id
               ) ELSE {_extract_batch_workers_sql()} END AS batch_workers,
               CASE WHEN {continuation} THEN 'continuation' ELSE 'new' END AS dispatch_lane
        FROM {_common._table('operation_runs')} r
        JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
        LEFT JOIN {_common._table('operation_batches')} b ON b.id=r.batch_id
        WHERE {' AND '.join(clauses)}
    """
    # 先覆盖类型、批次、平台和新任务/续查分组，再扩展每组候选。
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            WITH cursor_state AS (
                SELECT batches FROM {_common._table('operation_execution_dispatch_cursor')} WHERE id=1
            ), candidates AS ({base_query}), ranked AS (
                SELECT candidates.*, ROW_NUMBER() OVER (
                    PARTITION BY task_type, COALESCE(batch_id,0),
                        CASE WHEN task_type='extract_link' THEN data->>'provider_id' ELSE '' END,
                        dispatch_lane
                    ORDER BY next_attempt_at ASC NULLS FIRST, created_at, id
                ) AS dispatch_position
                FROM candidates
            ), lane_ranked AS (
                SELECT ranked.*, ROW_NUMBER() OVER (
                    PARTITION BY task_type, CASE WHEN task_type='extract_link' THEN data->>'provider_id' ELSE '' END, dispatch_lane
                    ORDER BY dispatch_position,
                        ((CASE WHEN batch_id IS NULL THEN '' ELSE 'operation:' || batch_id::text END)
                            > COALESCE((SELECT batches->>ranked.task_type FROM cursor_state),'')) DESC,
                        CASE WHEN batch_id IS NULL THEN '' ELSE 'operation:' || batch_id::text END, created_at, id
                ) AS lane_position FROM ranked
            ), provider_ranked AS (
                SELECT lane_ranked.*, ROW_NUMBER() OVER (
                    PARTITION BY task_type, CASE WHEN task_type='extract_link' THEN data->>'provider_id' ELSE '' END
                    ORDER BY lane_position, ((dispatch_lane='continuation') = %s) DESC,
                        dispatch_position, created_at, id
                ) AS provider_position FROM lane_ranked
            ), type_ranked AS (
                SELECT ranked.*, ROW_NUMBER() OVER (
                    PARTITION BY task_type ORDER BY provider_position, dispatch_position,
                        ((dispatch_lane='continuation') = %s) DESC, created_at, id
                ) AS type_position FROM provider_ranked ranked
            )
            SELECT * FROM type_ranked
            ORDER BY type_position, dispatch_position,
                ((dispatch_lane='continuation') = %s) DESC,
                created_at, id
            LIMIT %s
            """,
            (*params, bool(prioritize_continuations), bool(prioritize_continuations), bool(prioritize_continuations), scan_limit),
        )
        return [_common._row(dict(row)) or {} for row in cur.fetchall()]


def claim_next_queued_run(
    *,
    execution_id: str,
    worker_pid: int,
    source_systems: Iterable[str] | None = None,
    task_types: Iterable[str] | None = None,
) -> dict | None:
    """Atomically claim the oldest durable queue row across workers.

    The row lock is held only for the state transition and event insert.  The
    actual account lease is still acquired by the executor immediately before
    remote work, so a queue claim never reserves an account while waiting for a
    thread-pool slot.
    """
    _schema.init_operation_schema()
    blocked_before_execution = False
    result: dict | None = None
    with _common._connect() as conn, conn.cursor() as cur:
        clauses = [
            "r.status='queued'",
            "NOT (r.data ? 'bulk_target_round_id')",
            "r.cancel_requested_at IS NULL",
            "(r.next_attempt_at IS NULL OR r.next_attempt_at <= now())",
            _extract_batch_has_capacity_sql(),
        ]
        params: list[Any] = []
        sources = [str(item).strip() for item in (source_systems or ()) if str(item).strip()]
        types = [str(item).strip() for item in (task_types or ()) if str(item).strip()]
        if source_systems is None:
            clauses.append("r.source_system='native_operations'")
        elif not sources:
            return None
        else:
            clauses.append("t.source_system = ANY(%s)")
            params.append(sources)
        if task_types is not None:
            if not types:
                return None
            clauses.append("t.task_type = ANY(%s)")
            params.append(types)
        cur.execute(
            f"""
            SELECT r.id
            FROM {_common._table('operation_runs')} r
            JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
            LEFT JOIN {_common._table('operation_batches')} b ON b.id=r.batch_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.created_at, r.id
            FOR UPDATE OF r SKIP LOCKED
            LIMIT 1
            """,
            tuple(params),
        )
        selected = cur.fetchone()
        if not selected:
            return None
        run_id = int(selected["id"])
        cur.execute(
            f"SELECT * FROM {_common._table('operation_runs')} WHERE id=%s FOR UPDATE",
            (run_id,),
        )
        run_meta = cur.fetchone()
        if not run_meta or not _claim_extract_batch_capacity(conn, cur, run_meta):
            return None
        account = (
            record_store.get_row(
                record_store.ACCOUNTS,
                int(run_meta.get("account_id") or 0),
                conn=conn,
                for_update=True,
            )
            if run_meta and run_meta.get("account_id") else None
        )
        if _common._account_is_deactivated(account):
            cur.execute(
                f"""
                UPDATE {_common._table('operation_runs')}
                SET status='settling', execution_id=%s, worker_pid=%s,
                    next_attempt_at=NULL,
                    started_at=COALESCE(started_at, now()), heartbeat_at=now(),
                    progress_stage='preflight'
                WHERE id=%s AND status='queued'
                """,
                (str(execution_id), int(worker_pid), run_id),
            )
            cur.execute(
                f"""
                UPDATE {_common._table('operation_tasks')}
                SET status='settling', current_stage='preflight', updated_at=now()
                WHERE id=%s
                """,
                (int(run_meta["task_id"]),),
            )
            blocked_before_execution = True
        else:
            cur.execute(
                f"""
                UPDATE {_common._table('operation_runs')}
                SET status='running', execution_id=%s, worker_pid=%s,
                    next_attempt_at=NULL,
                    started_at=COALESCE(started_at, now()), heartbeat_at=now(),
                    progress_stage='preflight'
                WHERE id=%s AND status='queued' AND cancel_requested_at IS NULL
                  AND (next_attempt_at IS NULL OR next_attempt_at <= now())
                RETURNING *
                """,
                (str(execution_id), int(worker_pid), run_id),
            )
            raw = cur.fetchone()
            if not raw:
                return None
            run = dict(raw)
        if blocked_before_execution:
            result = None
        else:
            cur.execute(
                f"""
                UPDATE {_common._table('operation_tasks')}
                SET status='running', current_stage='preflight', updated_at=now()
                WHERE id=%s
                """,
                (int(run["task_id"]),),
            )
            event_uuid = uuid.uuid4().hex
            cur.execute(
                f"""
                INSERT INTO {_common._table('operation_events')} (
                    event_uuid, task_id, run_id, source_system, source_id,
                    level, stage, event_type, message, detail
                ) VALUES (%s,%s,%s,%s,%s,'INFO','queued',
                          'run.running','任务开始执行','{{}}'::jsonb)
                """,
                (
                    event_uuid, int(run["task_id"]), run_id,
                    str(run.get("source_system") or "native_operations"), event_uuid,
                ),
            )
            cur.execute(
                f"""
                SELECT r.*, t.task_type, t.email_snapshot, t.trigger, t.parent_task_id
                FROM {_common._table('operation_runs')} r
                JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
                WHERE r.id=%s
                """,
                (run_id,),
            )
            result = _common._row(dict(cur.fetchone())) or {}
    if blocked_before_execution:
        _finish_deactivated_before_execution(run_id, execution_id=str(execution_id))
        return None
    if not result:
        return None
    task_run_log.append(
        result.get("log_file"), level="INFO", message="任务开始执行",
        task_id=int(result["task_id"]), run_id=run_id, stage="queued", event_type="run.running",
    )
    return result


def refresh_runtime_batches(batch_ids: Iterable[int] | None = None) -> None:
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        _projection._refresh_batches(cur, batch_ids)


def mark_runtime_batch_empty(batch_id: int, *, status: str = "failed") -> None:
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_common._table('operation_batches')}
            SET status=%s, completed_at=now(),
                skipped_count=GREATEST(skipped_count, requested_count)
            WHERE id=%s AND NOT EXISTS (
                SELECT 1 FROM {_common._table('operation_batch_items')} item WHERE item.batch_id=%s
            )
            """,
            (str(status), int(batch_id), int(batch_id)),
        )


def set_runtime_batch_skipped(batch_id: int, skipped: list[dict]) -> None:
    """记录提交阶段未创建 run 的条目，避免批次计数看起来凭空少了账号。"""
    _schema.init_operation_schema()
    safe_items = list(skipped or [])[:5000]
    with _common._connect() as conn, conn.cursor() as cur:
        _projection._lock_projection_batch(cur, int(batch_id))
        cur.execute(
            f"""
            UPDATE {_common._table('operation_batches')}
            SET skipped_count=%s,
                data=data || %s::jsonb
            WHERE id=%s
            """,
            (len(safe_items), _common._json({"skipped": safe_items}), int(batch_id)),
        )
        _projection._refresh_batches(cur, [int(batch_id)])


def claim_run(run_id: int, *, execution_id: str, worker_pid: int, conn=None) -> dict | None:
    """仅一个进程能把 queued attempt 原子认领为 running。"""
    if conn is None:
        _schema.init_operation_schema()
    external_connection = conn is not None
    blocked_before_execution = False
    result: dict | None = None
    with (_common._connect() if conn is None else nullcontext(conn)) as conn, conn.cursor() as cur, bulk_execution.fact_update(conn, int(run_id), claim=True):
        cur.execute(
            f"""
            SELECT * FROM {_common._table('operation_runs')}
            WHERE id=%s AND status='queued' AND cancel_requested_at IS NULL
              AND (next_attempt_at IS NULL OR next_attempt_at <= now())
            FOR UPDATE
            """,
            (int(run_id),),
        )
        run = cur.fetchone()
        if not run or not _claim_extract_batch_capacity(conn, cur, run):
            return None
        account_id = int(run.get("account_id") or 0)
        if account_id:
            # 准入事务内核验账号互斥，不能认领后才在 worker 中等待账号资源。
            cur.execute(f"""SELECT lease.run_id FROM {_common._table('account_operation_leases')} lease
                WHERE lease.account_id=%s AND lease.resource_family=%s AND lease.run_id<>%s
                  AND (lease.expires_at > now() OR EXISTS (
                      SELECT 1 FROM {_common._permit_table()} p
                      WHERE p.run_id=lease.run_id AND p.released_at IS NULL))""",
                        (account_id, str(run.get("resource_family") or "openai_interactive"), int(run_id)))
            if cur.fetchone():
                from core.storage.operations.permits import ClaimUnavailable

                raise ClaimUnavailable("account_busy")
        account = (
            record_store.get_row(
                record_store.ACCOUNTS,
                account_id,
                conn=conn,
                for_update=True,
            )
            if account_id else None
        )
        if _common._account_is_deactivated(account):
            cur.execute(
                f"""
                UPDATE {_common._table('operation_runs')}
                SET status='settling', execution_id=%s, worker_pid=%s,
                    next_attempt_at=NULL,
                    started_at=COALESCE(started_at, now()), heartbeat_at=now(), progress_stage='preflight'
                WHERE id=%s AND status='queued'
                """,
                (str(execution_id), int(worker_pid), int(run_id)),
            )
            cur.execute(
                f"""
                UPDATE {_common._table('operation_tasks')}
                SET status='settling', current_stage='preflight', updated_at=now()
                WHERE id=%s
                """,
                (int(run["task_id"]),),
            )
            blocked_before_execution = True
            if external_connection:
                cur.execute(f"""SELECT r.*,t.task_type,t.email_snapshot,t.trigger,t.parent_task_id
                    FROM {_common._table('operation_runs')} r JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
                    WHERE r.id=%s""", (int(run_id),))
                result = _common._row(dict(cur.fetchone())) or {}
                result["_deactivated_before_execution"] = True
        else:
            cur.execute(
                f"""
                UPDATE {_common._table('operation_runs')}
                SET status='running', execution_id=%s, worker_pid=%s,
                    next_attempt_at=NULL,
                    started_at=COALESCE(started_at, now()), heartbeat_at=now(), progress_stage='preflight'
                WHERE id=%s AND status='queued' AND cancel_requested_at IS NULL
                RETURNING *
                """,
                (str(execution_id), int(worker_pid), int(run_id)),
            )
            run = cur.fetchone()
            if not run:
                return None
            cur.execute(
                f"""
                UPDATE {_common._table('operation_tasks')}
                SET status='running', current_stage='preflight', updated_at=now()
                WHERE id=%s
                """,
                (int(run["task_id"]),),
            )
            event_uuid = uuid.uuid4().hex
            cur.execute(
                f"""
                INSERT INTO {_common._table('operation_events')} (
                    event_uuid, task_id, run_id, source_system, source_id,
                    level, stage, event_type, message, detail
                ) VALUES (%s,%s,%s,%s,%s,'INFO','queued','run.running','任务开始执行','{{}}'::jsonb)
                """,
                (
                    event_uuid, int(run["task_id"]), int(run_id),
                    str(run.get("source_system") or "native_operations"), event_uuid,
                ),
            )
            cur.execute(
                f"""
                SELECT r.*, t.task_type, t.email_snapshot, t.trigger, t.parent_task_id
                FROM {_common._table('operation_runs')} r
                JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
                WHERE r.id=%s
                """,
                (int(run_id),),
            )
            result = _common._row(dict(cur.fetchone())) or {}
    if external_connection:
        return result
    if blocked_before_execution:
        _finish_deactivated_before_execution(
            int(run_id),
            execution_id=str(execution_id),
        )
        return None
    if not result:
        return None
    task_run_log.append(
        result.get("log_file"), level="INFO", message="任务开始执行",
        task_id=int(result["task_id"]), run_id=int(run_id), stage="queued", event_type="run.running",
    )
    return result


def requeue_claimed_run(
    run_id: int,
    *,
    execution_id: str,
    reason: str,
    delay_seconds: float = 1.0,
    data: Mapping[str, Any] | None = None,
    stage: str = "queued",
    lease_token: str | None = None,
    settlement_intent=None, settlement_domain=None, deadline=None,
    _settlement_conn=None,
) -> dict | None:
    """Return a claimed run to the durable queue without creating an attempt.

    A handler can reach this boundary when its account lease is temporarily
    held by another worker.  The transition is guarded by the execution id,
    so a stale worker cannot put a newer claim back into ``queued``.  A cancel
    request wins over requeue and is left for the normal terminal path.
    """
    if settlement_intent is not None:
        from core.storage.operations import settlements
        if settlement_domain is None:
            raise ValueError("settlement_domain is required")
        return settlements.submit_intent(settlement_intent, domain=settlement_domain, deadline=deadline)
    if _settlement_conn is None:
        _schema.init_operation_schema()
    delay = max(0.0, min(300.0, float(delay_seconds or 0.0)))
    patch = dict(data or {})
    if any(key in patch for key in ("remote_intent", "remote_receipt")):
        raise ValueError("延期数据不能覆盖远端请求回执")
    patch.update({"last_requeue_reason": _common._text(reason, 500), "next_attempt_delay_seconds": delay})
    stage_value = _common._text(stage, 100).strip() or "queued"
    with (_common._connect() if _settlement_conn is None else nullcontext(_settlement_conn)) as conn, conn.cursor() as cur, (bulk_execution.fact_update(conn, int(run_id)) if _settlement_conn is None else nullcontext(None)):
        cur.execute(
            f"""
            SELECT r.*, t.task_type, t.email_snapshot, t.trigger
            FROM {_common._table('operation_runs')} r
            JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.id=%s
            FOR UPDATE OF r
            """,
            (int(run_id),),
        )
        found = cur.fetchone()
        if not found:
            raise LookupError("执行实例不存在")
        if found.get("cancel_requested_at") is not None:
            return None
        if str(found.get("status") or "") not in {"running", "cancelling"}:
            return None
        if str(found.get("execution_id") or "") != str(execution_id):
            raise PermissionError("延期执行的 execution fence 不匹配")
        cur.execute(
            f"SELECT lease_token FROM {_common._table('account_operation_leases')} WHERE run_id=%s",
            (int(run_id),),
        )
        owned_lease = cur.fetchone()
        if lease_token is not None or owned_lease or (found.get("account_id") is not None and data is not None):
            _remote_checkpoint_fence(
                cur, int(run_id), execution_id=str(execution_id),
                lease_token=lease_token, require_lease=True,
            )
        cur.execute(
            f"""
            UPDATE {_common._table('operation_runs')}
            SET status='queued', execution_id=NULL, worker_pid=NULL,
                heartbeat_at=now(), progress_stage=%s,
                started_at=CASE WHEN %s THEN started_at ELSE NULL END,
                next_attempt_at=now() + (%s * interval '1 second'),
                data=data || %s::jsonb
            WHERE id=%s AND status IN ('running','cancelling')
              AND execution_id=%s AND cancel_requested_at IS NULL
            RETURNING *
            """,
            (
                stage_value, data is not None or stage_value != "queued",
                delay,
                _common._json(patch),
                int(run_id), str(execution_id),
            ),
        )
        row = cur.fetchone()
        if not row:
            return None
        run = dict(row)
        cur.execute(
            f"""
            UPDATE {_common._table('operation_tasks')}
            SET status='queued', current_stage=%s, updated_at=now(),
                error_category=NULL, error_code=NULL, error_message=NULL
            WHERE id=%s AND last_run_id=%s
            """,
            (stage_value, int(run["task_id"]), int(run_id)),
        )
        if owned_lease:
            cur.execute(
                f"DELETE FROM {_common._table('account_operation_leases')} WHERE run_id=%s AND lease_token=%s",
                (int(run_id), str(lease_token)),
            )
        event_uuid = uuid.uuid4().hex
        cur.execute(
            f"""
            INSERT INTO {_common._table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id,
                level, stage, event_type, message, detail
            ) VALUES (%s,%s,%s,%s,%s,'INFO',%s,'run.requeued',%s,%s::jsonb) RETURNING id
            """,
            (
                event_uuid, int(run["task_id"]), int(run_id),
                str(run.get("source_system") or "native_operations"), event_uuid,
                stage_value,
                _common._text(f"任务暂回数据库队列：{reason}", 1400),
                _common._json({"delay_seconds": delay}),
            ),
        )
        event_id = int(cur.fetchone()["id"])
        result = _common._row(run) or {}
        result["transition_event_id"] = event_id
        result["transition_event_uuid"] = event_uuid
    if _settlement_conn is not None:
        return result
    task_run_log.append(
        result.get("log_file"), level="INFO", message=f"任务暂回数据库队列：{reason}",
        task_id=int(result["task_id"]), run_id=int(run_id), stage=stage_value,
        event_type="run.requeued",
    )
    return result


def append_runtime_event(
    run_id: int,
    *,
    stage: str,
    message: str,
    state: str | None = None,
    level: str = "INFO",
    event_type: str | None = None,
    detail: dict | None = None,
) -> dict:
    _schema.init_operation_schema()
    event_uuid = uuid.uuid4().hex
    stage_value = normalize_stage(stage)
    state_value = normalize_step_state(state) if state is not None else None
    if state is not None and state_value is None:
        raise ValueError(f"不支持的任务步骤状态: {state!r}")
    level_value = str(level or "INFO").upper()
    event_type_value = str(event_type or "").strip()[:120]
    if not event_type_value:
        event_type_value = (
            f"stage.{state_value}"
            if state_value is not None
            else "note.error" if level_value == "ERROR"
            else "note.warning" if level_value == "WARNING"
            else "note.info"
        )
    if event_type_value.startswith("stage."):
        event_state = normalize_step_state(event_type_value.removeprefix("stage."))
        if event_state is None:
            raise ValueError(f"不支持的阶段事件类型: {event_type_value!r}")
        if state_value is not None and state_value != event_state:
            raise ValueError("任务步骤状态与事件类型不一致")
        state_value = event_state
    clean_detail = dict(detail or {})
    clean_detail.setdefault("raw_stage", str(stage or "event"))
    if state_value is not None:
        clean_detail["step_state"] = state_value
    with _common._connect() as conn, conn.cursor() as cur, bulk_execution.fact_update(conn, int(run_id)):
        cur.execute(
            f"SELECT r.task_id, r.log_file, r.source_system, t.task_type "
            f"FROM {_common._table('operation_runs')} r JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id WHERE r.id=%s",
            (int(run_id),),
        )
        found = cur.fetchone()
        if not found:
            raise LookupError("执行实例不存在")
        task_id = int(found["task_id"])
        category, code, _ = _common._error_fields(
            message if state_value == "failed" or level_value == "ERROR" else None,
            stage=stage_value, task_type=str(found.get("task_type") or ""),
            result_summary=clean_detail,
        )
        cur.execute(
            f"""
            INSERT INTO {_common._table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id,
                level, stage, event_type, message, detail, error_category, error_code
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            RETURNING *
            """,
            (
                event_uuid, task_id, int(run_id), str(found.get("source_system") or "native_operations"),
                event_uuid, level_value,
                stage_value, event_type_value, task_run_log.redact_text(message, 1400), _common._json(clean_detail),
                category, code,
            ),
        )
        event = dict(cur.fetchone())
        if state_value is not None:
            cur.execute(
                f"""
                UPDATE {_common._table('operation_runs')}
                SET progress_stage=%s,
                    progress_steps=jsonb_set(progress_steps, %s, to_jsonb(%s::text), true),
                    heartbeat_at=now()
                WHERE id=%s
                """,
                (stage_value, [stage_value], state_value, int(run_id)),
            )
            cur.execute(
                f"UPDATE {_common._table('operation_tasks')} SET current_stage=%s, updated_at=now() WHERE id=%s",
                (stage_value, task_id),
            )
        else:
            cur.execute(
                f"UPDATE {_common._table('operation_runs')} SET heartbeat_at=now() WHERE id=%s",
                (int(run_id),),
            )
            cur.execute(
                f"UPDATE {_common._table('operation_tasks')} SET updated_at=now() WHERE id=%s",
                (task_id,),
            )
        result = _common._row(event) or {}
        log_file = found.get("log_file")
    task_run_log.append(
        log_file, level=level_value, message=message, task_id=task_id, run_id=int(run_id),
        stage=stage_value, event_type=event_type_value, fields=clean_detail,
        event_id=int(result["id"]), event_uuid=event_uuid,
        created_at=result.get("created_at"),
    )
    return result


def _remote_checkpoint_fence(
    cur,
    run_id: int,
    *,
    execution_id: str,
    lease_token: str | None,
    require_lease: bool,
) -> dict:
    """Load one active run and verify the execution/lease owner.

    Remote intent is a safety checkpoint, not an ordinary progress event.  It
    therefore uses the same fence as terminal result writes and never accepts
    a stale worker's checkpoint after a lease has changed hands.
    """
    execution_value = str(execution_id or "").strip()
    if not execution_value:
        raise ValueError("remote checkpoint 必须携带 execution_id")
    cur.execute(
        f"SELECT * FROM {_common._table('operation_runs')} WHERE id=%s FOR UPDATE",
        (int(run_id),),
    )
    raw = cur.fetchone()
    if not raw:
        raise LookupError("执行实例不存在")
    run = dict(raw)
    if str(run.get("status") or "") not in {"running", "cancelling", "settling"}:
        raise PermissionError("非活动执行实例不能写入 remote checkpoint")
    if str(run.get("execution_id") or "") != execution_value:
        raise PermissionError("remote checkpoint execution fence 不匹配")
    account_id = int(run.get("account_id") or 0)
    if account_id:
        account = (_common._settlement_account(cur, account_id, for_update=True)
                   if _common.current_settlement_domain() is not None else record_store.get_row(
            record_store.ACCOUNTS,
            account_id,
            conn=cur.connection,
            for_update=True,
        ))
        if _common._account_is_deactivated(account):
            raise OperationAccountDeactivated("账号已确认停用，禁止继续远端请求")
    token = str(lease_token or "").strip()
    if require_lease and not token:
        raise PermissionError("remote write 必须持有账号 lease")
    if token:
        cur.execute(
            f"""
            SELECT 1 FROM {_common._table('account_operation_leases')}
            WHERE run_id=%s AND lease_token=%s AND expires_at > now()
            """,
            (int(run_id), token),
        )
        if not cur.fetchone():
            raise PermissionError("remote checkpoint lease owner 不匹配或已过期")
    elif run.get("account_id") is not None and require_lease:
        raise PermissionError("账号 remote write 缺少 lease")
    return run


def fence_execution(cur, run_id: int, *, execution_id: str, lease_token: str) -> dict:
    """在调用方事务中按 Run → 账号顺序锁定并校验结果写入所有权。"""
    return _remote_checkpoint_fence(cur, run_id, execution_id=execution_id, lease_token=lease_token, require_lease=True)


def _remote_checkpoint_event(
    cur,
    run: dict,
    *,
    event_type: str,
    message: str,
    detail: dict[str, Any],
) -> None:
    event_uuid = uuid.uuid4().hex
    cur.execute(
        f"""
        INSERT INTO {_common._table('operation_events')} (
            event_uuid, task_id, run_id, source_system, source_id,
            level, stage, event_type, message, detail
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        """,
        (
            event_uuid, int(run["task_id"]), int(run["id"]),
            str(run.get("source_system") or "native_operations"), event_uuid,
            "WARNING" if "unknown" in event_type else "INFO",
            "reconcile" if "unknown" in event_type else "remote_request",
            event_type, _common._text(message, 1400), _common._json(detail),
        ),
    )


def record_remote_intent(
    run_id: int,
    *,
    execution_id: str,
    lease_token: str | None = None,
    action: str,
    intent_kind: str = "remote_write",
    request_id: str | None = None,
    detail: dict | None = None,
) -> dict:
    """Persist the start of a remote request before crossing the API boundary.

    ``remote_write`` checkpoints are lease-fenced.  The payload deliberately
    contains only an action, a caller-supplied correlation id and scrubbed
    metadata; credentials and full remote responses never belong here.
    """
    kind = str(intent_kind or "remote_write").strip().lower()
    if kind not in _REMOTE_INTENT_KINDS:
        raise ValueError(f"不支持的 remote intent 类型: {kind!r}")
    action_value = _common._text(action, 160).strip() or "remote_operation"
    request_value = _common._text(request_id, 240).strip() if request_id else ""
    safe_detail = _common._scrub(detail or {})
    with _common._connect() as conn, conn.cursor() as cur, bulk_execution.fact_update(conn, int(run_id)):
        run = _remote_checkpoint_fence(
            cur, int(run_id), execution_id=execution_id, lease_token=lease_token,
            require_lease=kind == "remote_write",
        )
        previous_intent = _remote_write_checkpoint(run.get("data"))
        previous_receipt = str(
            previous_intent.get("receipt_state") or previous_intent.get("state") or "started"
        )
        previous_data = _common._decode(run.get("data"))
        previous_receipt_row = (
            previous_data.get("remote_receipt")
            if isinstance(previous_data, dict) else None
        )
        previous_receipt_detail = (
            previous_receipt_row.get("detail")
            if isinstance(previous_receipt_row, dict) else None
        )
        phase_complete = isinstance(previous_receipt_detail, dict) and any(
            value is True or str(value).strip().lower() in {"1", "true", "yes", "confirmed"}
            for key, value in previous_receipt_detail.items()
            if key in {"phase_complete", "allow_next_intent"}
        )
        if previous_intent and previous_receipt not in {"confirmed", "rejected", "not_submitted"} and not (
            previous_receipt == "response_received" and phase_complete
        ):
            raise ValueError("前一个远端写请求尚未核验，不能覆盖其 checkpoint")
        intent = {
            "action": action_value,
            "kind": kind,
            "state": "started",
            "receipt_state": "started",
            "started_at": _common._now().isoformat(),
        }
        if request_value:
            intent["request_id"] = request_value
        if safe_detail:
            intent["detail"] = safe_detail
        cur.execute(
            f"""
            UPDATE {_common._table('operation_runs')}
            SET data=data || %s::jsonb, heartbeat_at=now()
            WHERE id=%s AND execution_id=%s
            RETURNING *
            """,
            (_common._json({"remote_intent": intent}), int(run_id), str(execution_id)),
        )
        updated = dict(cur.fetchone())
        _remote_checkpoint_event(
            cur, updated,
            event_type="remote.request_started",
            message=f"远端请求边界已记录：{action_value}",
            detail={
                "action": action_value,
                "intent_kind": kind,
                "request_id": request_value or None,
                "execution_id": str(execution_id),
            },
        )
    return _common._row(updated) or {}


def record_remote_receipt(
    run_id: int,
    *,
    execution_id: str,
    lease_token: str | None = None,
    outcome: str | None = None,
    receipt_state: str | None = None,
    action: str | None = None,
    request_id: str | None = None,
    detail: dict | None = None,
) -> dict:
    """Persist a remote response without closing the Run.

    ``response_received`` (with ``received``/``response_observed``/``accepted``
    aliases) means only that an HTTP response was observed.  A positive
    response whose local writeback has not completed is represented by
    ``local_commit_required``.  ``confirmed`` is accepted only when the caller
    explicitly proves remote confirmation, local business writeback, and a
    local readback.  A crash before :func:`finish_run` still requires
    reconciliation for every non-rejected write checkpoint, including
    ``confirmed``; the receipt never makes a Run terminal by itself.

    ``not_submitted`` 只接受明确的未派发、未提交证据，允许前置失败结束当前
    认证边界；已有响应或未确认结果不能被改写成未提交。
    """
    outcome_value = str(receipt_state or outcome or "unknown").strip().lower()
    outcome_value = {
        "received": "response_received",
        "response_observed": "response_received",
        "accepted": "response_received",
    }.get(outcome_value, outcome_value)
    if outcome_value not in _REMOTE_RECEIPT_OUTCOMES:
        raise ValueError(f"不支持的 remote receipt outcome: {outcome_value!r}")
    action_value = _common._text(action, 160).strip() if action else ""
    request_value = _common._text(request_id, 240).strip() if request_id else ""
    raw_detail = dict(detail or {})
    if outcome_value == "not_submitted" and not (
        raw_detail.get("mutation_submitted") is False
        and raw_detail.get("action_dispatched") is False
    ):
        raise ValueError("未提交回执必须明确证明 mutation_submitted=false 和 action_dispatched=false")
    if outcome_value == "confirmed":
        def _confirmed_marker(*names: str) -> bool:
            for name in names:
                value = raw_detail.get(name)
                if value is True:
                    return True
                if isinstance(value, str) and value.strip().lower() in {
                    "1", "true", "yes", "confirmed",
                }:
                    return True
            return False

        if not _confirmed_marker(
            "remote_result_confirmed", "remote_response_confirmed", "remote_confirmed",
        ):
            raise ValueError(
                "confirmed receipt 必须明确 remote_result_confirmed=true"
            )
        if not _confirmed_marker(
            "local_business_writeback_confirmed", "local_writeback_confirmed",
            "local_commit_confirmed",
        ):
            raise ValueError(
                "confirmed receipt 必须明确 local_business_writeback_confirmed=true"
            )
        if not _confirmed_marker("local_readback_confirmed", "local_readback"):
            raise ValueError(
                "confirmed receipt 必须明确 local_readback_confirmed=true"
            )
    safe_detail = _common._scrub(raw_detail)
    with _common._connect() as conn, conn.cursor() as cur, bulk_execution.fact_update(conn, int(run_id)):
        run = _remote_checkpoint_fence(
            cur, int(run_id), execution_id=execution_id, lease_token=lease_token,
            require_lease=False,
        )
        data = _common._decode(run.get("data"))
        data = dict(data) if isinstance(data, dict) else {}
        intent = data.get("remote_intent")
        if not isinstance(intent, dict):
            raise ValueError("remote receipt 缺少对应的 remote_request_started")
        intent = dict(intent)
        if intent.get("kind") == "remote_write" and not str(lease_token or "").strip():
            raise PermissionError("remote write receipt 必须持有账号 lease")
        intent_action = str(intent.get("action") or "")
        if action_value and intent_action and action_value != intent_action:
            raise ValueError("remote receipt action 与 intent 不匹配")
        action_value = action_value or intent_action or "remote_operation"
        if request_value and intent.get("request_id") and request_value != str(intent["request_id"]):
            raise ValueError("remote receipt request_id 与 intent 不匹配")
        if not request_value:
            request_value = str(intent.get("request_id") or "")
        previous_receipt = str(intent.get("receipt_state") or intent.get("state") or "started")
        if previous_receipt == "confirmed" and outcome_value != "confirmed":
            raise ValueError("已确认的远端写回执不能降级或改为 rejected")
        if outcome_value == "not_submitted" and previous_receipt not in {
            "started", "not_submitted",
        }:
            raise ValueError("已记录响应或未确认结果的请求不能改成未提交回执")
        intent["state"] = outcome_value
        intent["receipt_state"] = outcome_value
        intent["receipt_at"] = _common._now().isoformat()
        receipt = {
            "action": action_value,
            "outcome": outcome_value,
            "receipt_state": outcome_value,
            "received_at": _common._now().isoformat(),
        }
        if request_value:
            receipt["request_id"] = request_value
        if safe_detail:
            receipt["detail"] = safe_detail
        cur.execute(
            f"""
            UPDATE {_common._table('operation_runs')}
            SET data=data || %s::jsonb, heartbeat_at=now()
            WHERE id=%s AND execution_id=%s
            RETURNING *
            """,
            (
                _common._json({"remote_intent": intent, "remote_receipt": receipt}),
                int(run_id), str(execution_id),
            ),
        )
        updated = dict(cur.fetchone())
        _remote_checkpoint_event(
            cur, updated,
            event_type=(
                "remote.receipt_unknown"
                if outcome_value == "unknown" else "remote.receipt_received"
            ),
            message=(
                f"远端请求回执待核验：{action_value}"
                if outcome_value == "unknown"
                else f"已记录远端请求回执：{action_value}/{outcome_value}"
            ),
            detail={
                "action": action_value,
                "outcome": outcome_value,
                "request_id": request_value or None,
                "execution_id": str(execution_id),
            },
        )
    return _common._row(updated) or {}


def heartbeat_run(run_id: int, lease_token: str = "", *, ttl_seconds: int = 600) -> bool:
    _schema.init_operation_schema()
    ttl = max(60, min(24 * 60 * 60, int(ttl_seconds or 600)))
    with _common._connect() as conn, conn.cursor() as cur, bulk_execution.fact_update(conn, int(run_id), emit=False):
        token = str(lease_token or "").strip()
        if token:
            cur.execute(
                f"""
                UPDATE {_common._table('operation_runs')} AS run
                SET heartbeat_at=now()
                WHERE run.id=%s AND run.status IN ('running','cancelling','settling')
                  AND EXISTS (
                      SELECT 1 FROM {_common._table('account_operation_leases')} lease
                      WHERE lease.run_id=run.id AND lease.lease_token=%s
                        AND lease.expires_at > now()
                  )
                """,
                (int(run_id), token),
            )
            changed = cur.rowcount > 0
            if changed:
                cur.execute(
                    f"""
                    UPDATE {_common._table('account_operation_leases')}
                    SET heartbeat_at=now(), expires_at=now() + (%s * interval '1 second')
                    WHERE run_id=%s AND lease_token=%s AND expires_at > now()
                    """,
                    (ttl, int(run_id), token),
                )
                changed = cur.rowcount > 0
            return changed
        cur.execute(
            f"""
            UPDATE {_common._table('operation_runs')}
            SET heartbeat_at=now()
            WHERE id=%s AND account_id IS NULL
              AND status IN ('running','cancelling','settling')
            """,
            (int(run_id),),
        )
        return cur.rowcount > 0


def _acquire_account_lease(
    *, account_id: int, run_id: int, resource_family: str = "openai_interactive",
    ttl_seconds: int = 600,
) -> str | None:
    _schema.init_operation_schema()
    lease_token = uuid.uuid4().hex
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT status, account_id, resource_family, data
            FROM {_common._table('operation_runs')}
            WHERE id=%s
            FOR UPDATE
            """,
            (int(run_id),),
        )
        run = cur.fetchone()
        if not run or str(run.get("status") or "") not in {"running", "cancelling", "settling"}:
            return None
        if int(run.get("account_id") or 0) != int(account_id):
            return None
        family = str(run.get("resource_family") or "openai_interactive")
        data = _common._decode(run.get("data")) or {}
        completion_lease = (
            family == "registration_completion" and resource_family == "openai_interactive"
            and data.get("registration_completion") is True and data.get("steps") == ["password"]
        )
        if family != str(resource_family) and not completion_lease:
            return None
        account = (
            _common._settlement_account(cur, int(account_id), for_update=True)
            if _common.current_settlement_domain() is not None
            else record_store.get_row(
                record_store.ACCOUNTS, int(account_id), conn=conn, for_update=True,
            )
        )
        if _common._account_is_deactivated(account):
            raise OperationAccountDeactivated("账号已确认停用，禁止申请任务 lease")
        cur.execute(
            f"""DELETE FROM {_common._table('account_operation_leases')} lease WHERE expires_at < now()
                AND NOT EXISTS (SELECT 1 FROM {_common._permit_table()} p
                    WHERE p.run_id=lease.run_id AND p.released_at IS NULL)""",
        )
        cur.execute(
            f"""
            INSERT INTO {_common._table('account_operation_leases')} (
                account_id, resource_family, run_id, lease_token, expires_at
            ) VALUES (%s, %s, %s, %s, now() + (%s * interval '1 second'))
            ON CONFLICT (account_id, resource_family) DO NOTHING
            RETURNING lease_token
            """,
            (int(account_id), str(resource_family), int(run_id), lease_token, max(60, int(ttl_seconds))),
        )
        row = cur.fetchone()
        return str(row["lease_token"]) if row else None


def release_account_lease(run_id: int, lease_token: str = "") -> bool:
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        if lease_token:
            cur.execute(
                f"DELETE FROM {_common._table('account_operation_leases')} WHERE run_id=%s AND lease_token=%s",
                (int(run_id), str(lease_token)),
            )
        else:
            cur.execute(
                f"DELETE FROM {_common._table('account_operation_leases')} WHERE run_id=%s",
                (int(run_id),),
            )
        return cur.rowcount > 0


def request_run_cancel(
    run_id: int,
    *,
    reason: str = "用户手动停止",
    expected_status: str | None = None,
    conn=None,
) -> dict:
    """协作式取消：排队任务立即取消；运行任务进入 cancelling 等待检查点收口。"""
    if conn is None:
        _schema.init_operation_schema()
    with (_common._connect() if conn is None else nullcontext(conn)) as conn, conn.cursor() as cur, bulk_execution.fact_update(conn, int(run_id)):
        cur.execute(
            f"SELECT * FROM {_common._table('operation_runs')} WHERE id=%s FOR UPDATE",
            (int(run_id),),
        )
        run = cur.fetchone()
        if not run:
            raise LookupError("执行实例不存在")
        status = str(run.get("status") or "")
        if expected_status and status != str(expected_status):
            return {
                "id": int(run["id"]),
                "task_id": int(run["task_id"]),
                "status": status,
                "state": status,
                "cancel_skipped": True,
                "message": "任务状态已变化，请刷新后重试",
            }
        if status in _common._TERMINAL_STATUSES:
            return _common._row(dict(run)) or {}
        target = "cancelled" if status == "queued" else "cancelling"
        completed_sql = ", completed_at=now()" if target == "cancelled" else ""
        cur.execute(
            f"""
            UPDATE {_common._table('operation_runs')}
            SET status=%s, cancel_requested_at=COALESCE(cancel_requested_at, now()),
                cancel_reason=%s, heartbeat_at=now(){completed_sql}
            WHERE id=%s RETURNING *
            """,
            (target, _common._text(reason, 500), int(run_id)),
        )
        updated = dict(cur.fetchone())
        task_status = "cancelled" if target == "cancelled" else "cancelling"
        task_stage = "complete" if target == "cancelled" else "cancelling"
        cur.execute(
            f"""
            UPDATE {_common._table('operation_tasks')}
            SET status=%s, current_stage=%s, updated_at=now(),
                completed_at=CASE WHEN %s='cancelled' THEN now() ELSE completed_at END
            WHERE id=%s
            """,
            (task_status, task_stage, task_status, int(run["task_id"])),
        )
        cur.execute(
            f"UPDATE {_common._table('account_operation_leases')} SET cancel_requested_at=now() WHERE run_id=%s",
            (int(run_id),),
        )
        event_uuid = uuid.uuid4().hex
        cur.execute(
            f"""
            INSERT INTO {_common._table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id,
                level, stage, event_type, message, detail
            ) VALUES (%s, %s, %s, %s, %s,
                      'WARNING', %s, 'run.cancel_requested', %s, %s::jsonb)
            """,
            (
                event_uuid, int(run["task_id"]), int(run_id),
                str(run.get("source_system") or "native_operations"), event_uuid,
                task_stage, _common._text(reason, 1400),
                _common._json({"previous_status": status, "status": target}),
            ),
        )
        if run.get("batch_id"):
            _projection._refresh_batches(cur, [int(run["batch_id"])])
        if target == "cancelled":
            bulk_execution.release_cancelled_refresh(conn, updated)
        return _common._row(updated) or {}


def terminate_run(run_id: int, *, reason: str = "用户手动终止任务") -> dict:
    """强制收口一个活动 Run；排队任务按取消处理，运行任务按终止处理。

    这里不会尝试杀掉进程内线程或外部浏览器。终态写入仍由 ``finish_run``
    统一执行，因此远端写入 checkpoint、资源对账、lease 清理和父任务收口
    与 worker 正常结束时保持同一套安全规则。
    """
    safe_reason = _common._text(reason, 500).strip() or "用户手动终止任务"
    return finish_run(
        int(run_id),
        status="stopped",
        message=safe_reason,
        result_summary={
            "termination": "manual",
            "forced": True,
            "cancel_reason": safe_reason,
        },
        force_terminate=True,
    )


def is_run_cancel_requested(run_id: int, cancellation_token: str = "") -> bool:
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        params: list[Any] = [int(run_id)]
        token_clause = ""
        if cancellation_token:
            token_clause = " AND cancellation_token=%s"
            params.append(str(cancellation_token))
        cur.execute(
            f"""
            SELECT cancel_requested_at IS NOT NULL OR status IN ('cancelling','cancelled') AS requested
            FROM {_common._table('operation_runs')} WHERE id=%s{token_clause}
            """,
            params,
        )
        row = cur.fetchone()
        return not row or bool(row["requested"])


def mark_run_settling(run_id: int) -> bool:
    """Callback 已交给远端后进入有界对账阶段；保留 cancel_requested_at。"""
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur, bulk_execution.fact_update(conn, int(run_id)):
        cur.execute(
            f"""
            UPDATE {_common._table('operation_runs')}
            SET status='settling', settling_at=COALESCE(settling_at, now()),
                progress_stage='credential_confirm', heartbeat_at=now()
            WHERE id=%s AND status IN ('running', 'cancelling')
            RETURNING task_id
            """,
            (int(run_id),),
        )
        row = cur.fetchone()
        if not row:
            return False
        cur.execute(
            f"""
            UPDATE {_common._table('operation_tasks')}
            SET status='settling', current_stage='credential_confirm', updated_at=now()
            WHERE id=%s
            """,
            (int(row["task_id"]),),
        )
        return True


def register_resource(
    run_id: int, *, resource_type: str, provider: str = "", external_id: str = "",
    detail: dict | None = None,
) -> dict:
    _schema.init_operation_schema()
    resource_uuid = uuid.uuid4().hex
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {_common._table('operation_resources')} (
                resource_uuid, run_id, resource_type, provider, external_id, detail
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (run_id, resource_type, external_id) DO UPDATE
            SET state='acquired', released_at=NULL, detail=EXCLUDED.detail
            RETURNING *
            """,
            (
                resource_uuid, int(run_id), str(resource_type), str(provider),
                _common._text(external_id, 300), _common._json(detail or {}),
            ),
        )
        return _common._row(dict(cur.fetchone())) or {}


def release_resource(resource_id: int, *, state: str = "released", detail: dict | None = None) -> bool:
    if _common.current_settlement_domain() is None:
        _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_common._table('operation_resources')}
            SET state=%s, released_at=now(),
                detail=CASE WHEN %s::jsonb = '{{}}'::jsonb THEN detail ELSE detail || %s::jsonb END
            WHERE id=%s
            """,
            (str(state), _common._json(detail or {}), _common._json(detail or {}), int(resource_id)),
        )
        return cur.rowcount > 0


def _confirmed_extract_terminal_failure(cur, run: dict, result_summary: dict) -> bool:
    """仅对持久化证据一致、没有支付悬置的提链终态允许正常失败收口。"""
    if (
        str(run.get("task_type") or "") != "extract_link"
        or result_summary.get("remote_result_state") != "failed"
        or result_summary.get("remote_terminal_failure") is not True
        or result_summary.get("cause_code") != "extract_provider_failed"
        or result_summary.get("extraction_status") != "failed"
        or result_summary.get("payment_status") not in ("not_started", "failed")
        or result_summary.get("reconcile_required") is True
        or str(result_summary.get("outcome") or "").lower() in {"unknown", "request_unknown"}
    ):
        return False
    data = _common._decode(run.get("data"))
    data = data if isinstance(data, dict) else {}
    intent = _remote_write_checkpoint(data)
    receipt = data.get("remote_receipt")
    receipt = receipt if isinstance(receipt, dict) else {}
    if (
        intent.get("action") != "extract_link_create"
        or (intent.get("receipt_state") or intent.get("state")) != "confirmed"
        or receipt.get("action") != "extract_link_create"
        or (receipt.get("receipt_state") or receipt.get("outcome")) != "confirmed"
        or not intent.get("request_id")
        or receipt.get("request_id") != intent.get("request_id")
    ):
        return False
    intent_detail = intent.get("detail")
    intent_detail = intent_detail if isinstance(intent_detail, dict) else {}
    receipt_detail = receipt.get("detail")
    receipt_detail = receipt_detail if isinstance(receipt_detail, dict) else {}
    cur.execute(
        f"""
        SELECT provider_id, job_id, extraction_state, payment_state, public_state
        FROM {_common._table('extract_link_provider_jobs')}
        WHERE run_id=%s
        FOR SHARE
        """,
        (int(run["id"]),),
    )
    row = cur.fetchone()
    if not row:
        return False
    job = dict(row)
    provider_id = str(job.get("provider_id") or "").strip()
    job_id = str(job.get("job_id") or "").strip()
    public_state = _common._decode(job.get("public_state"))
    public_state = public_state if isinstance(public_state, dict) else {}
    summary = public_state.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    return bool(
        provider_id and job_id
        and provider_id == str(data.get("provider_id") or "")
        and provider_id == str(result_summary.get("provider_id") or "")
        and provider_id == str(intent_detail.get("provider_id") or "")
        and provider_id == str(receipt_detail.get("provider_id") or "")
        and job_id == str(receipt_detail.get("remote_job_id") or "")
        and job.get("extraction_state") == "failed"
        and public_state.get("extraction_state") == "failed"
        and job.get("payment_state") in {"not_started", "failed"}
        and public_state.get("payment_state") == job.get("payment_state")
        and result_summary.get("payment_status") == job.get("payment_state")
        and summary.get("remote_terminal_failure") is True
        and summary.get("remote_status") in {"FAILED", "ERROR", "CANCELED", "CANCELLED"}
    )


def _confirmed_independent_payment_partial(cur, run: dict, result_summary: dict) -> bool:
    """外接付款外围失败已有完整事实时，保留提链成功的部分完成终态。"""
    data = _common._decode(run.get("data"))
    data = data if isinstance(data, dict) else {}
    if (str(run.get("task_type") or "") != "extract_link"
            or data.get("payment_source") != "xxsyun" or data.get("mode") != "auto_payment"
            or result_summary.get("payment_source") != "xxsyun"
            or result_summary.get("extraction_status") != "succeeded"
            or result_summary.get("payment_status") not in {"not_started", "failed"}):
        return False
    cur.execute(f"SELECT extraction_state, payment_state, public_state FROM {_common._table('extract_link_provider_jobs')} WHERE run_id=%s FOR SHARE", (int(run["id"]),))
    job = cur.fetchone()
    if (not job or job["extraction_state"] != "succeeded"
            or job["payment_state"] != result_summary.get("payment_status")):
        return False
    public = _common._decode(job["public_state"])
    summary = public.get("summary") if isinstance(public, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    if summary.get("payment_order_id"):
        cur.execute(f"SELECT task_id, payment_state FROM {_common._table('extract_link_payment_orders')} WHERE id=%s FOR SHARE", (int(summary["payment_order_id"]),))
        order = cur.fetchone()
        return bool(order and int(order["task_id"]) == int(run["task_id"])
                    and order["payment_state"] == "failed" and job["payment_state"] == "failed")
    return (summary.get("failure_code") == result_summary.get("failure_code")
            and summary.get("failure_code") in {"MATERIAL_MISSING", "MATERIAL_UNSUPPORTED", "INVALID_AT"})


def _confirmed_plan_refresh(run: dict, result_summary: dict) -> bool:
    """独立套餐后续查询失败不能推翻本 Run 已三证确认的 AT 刷新。"""
    refresh = result_summary.get("auto_refresh_at")
    if (run.get("task_type") != "plan_check" or run.get("source_system") != "native_operations"
            or run.get("resource_family") != "openai_interactive"
            or not isinstance(refresh, dict) or refresh.get("attempted") is not True
            or refresh.get("ok") is not True or refresh.get("reconcile_required") is True
            or result_summary.get("reconcile_required") is True
            or result_summary.get("manual_reconcile") is True
            or result_summary.get("outcome") in {"unknown", "request_unknown"}):
        return False
    data = _common._decode(run.get("data"))
    data = data if isinstance(data, dict) else {}
    intent = _remote_write_checkpoint(data)
    receipt = data.get("remote_receipt")
    receipt = receipt if isinstance(receipt, dict) else {}
    request_id = str(intent.get("request_id") or "")
    detail = receipt.get("detail")
    detail = detail if isinstance(detail, dict) else {}
    return bool(
        intent.get("action") == "token_refresh"
        and (intent.get("receipt_state") or intent.get("state")) == "confirmed"
        and receipt.get("action") == "token_refresh"
        and (receipt.get("receipt_state") or receipt.get("outcome")) == "confirmed"
        and request_id.startswith(f"token-refresh:{int(run['id'])}:")
        and receipt.get("request_id") == request_id
        and all(detail.get(key) is True for key in (
            "remote_result_confirmed", "local_business_writeback_confirmed", "local_readback_confirmed",
        ))
    )


def _confirmed_account_setup_partial(cur, run: dict, result_summary: dict) -> bool:
    """仅为步骤回执完整且成功项本地读回一致的协议补密码保留部分成功。"""
    if (run.get("source_system") != "webui_runtime" or run.get("task_type") not in {"account_setup_retry", "password_setup"}
            or run.get("resource_family") != "openai_interactive" or result_summary.get("password_driver") != "protocol"
            or result_summary.get("reconcile_required") is True or result_summary.get("manual_reconcile") is True
            or result_summary.get("outcome") in {"unknown", "request_unknown"}):
        return False
    data = _common._decode(run.get("data"))
    data = data if isinstance(data, dict) else {}
    steps = data.get("steps")
    if (not isinstance(steps, list) or not steps or "password" not in steps
            or any(step not in {"password", "twofa", "plan_check"} for step in steps)):
        return False
    intent = _remote_write_checkpoint(data)
    receipt = data.get("remote_receipt")
    receipt = receipt if isinstance(receipt, dict) else {}
    detail = receipt.get("detail")
    detail = detail if isinstance(detail, dict) else {}
    evidence = detail.get("setup_step_receipts")
    if (intent.get("action") != "account_setup" or receipt.get("action") != "account_setup"
            or receipt.get("receipt_state") != "confirmed" or not intent.get("request_id")
            or receipt.get("request_id") != intent.get("request_id") or not isinstance(evidence, list)
            or evidence != result_summary.get("setup_step_receipts") or len(evidence) != len(set(steps))):
        return False
    completed = set()
    failed = set()
    for item in evidence:
        if not isinstance(item, dict) or item.get("step") not in set(steps):
            return False
        if item.get("ok") is True and item.get("receipt_state") == "confirmed":
            completed.add(item["step"])
        elif item.get("ok") is False and item.get("receipt_state") in {"rejected", "not_submitted"}:
            failed.add(item["step"])
        else:
            return False
    if not completed or not failed or completed & failed or completed | failed != set(steps):
        return False
    account = (_common._settlement_account(cur, int(run.get("account_id") or 0))
               if _common.current_settlement_domain() is not None else
               record_store.get_row(record_store.ACCOUNTS, int(run.get("account_id") or 0), conn=cur.connection))
    if not account:
        return False
    extra = _common._decode(account.get("extra_json"))
    extra = extra if isinstance(extra, dict) else {}
    for step in completed:
        if step == "password" and not any(str(extra.get(key) or account.get(key) or "").strip() for key in (
                "account_password", "login_password", "registration_password")):
            return False
        if step == "twofa" and (not str(account.get("totp_secret") or "").strip() or extra.get("totp_setup_pending")):
            return False
        if step == "plan_check" and account.get("plan_check_status") != "success":
            return False
    return True


def _password_change_pending_closeout(run: dict, result_summary: dict) -> bool:
    """识别已确认密码但收尾未完成的手动改密结果。

    只有本 Run 已持久化、且与 remote intent 关联的密码回执才能改变
    password_change 的终态收口。其它账号配置、注册和远端写入仍必须遵守
    通用的未知回执保护。
    """
    if str(run.get("task_type") or "") != "password_change":
        return False

    def _pending(value: Any) -> bool:
        if not isinstance(value, Mapping):
            return False
        remote_confirmed = value.get("remote_password_confirmed") is True or (
            str(value.get("password_reset") or "").strip().lower() == "confirmed"
            and value.get("password_confirmed") is True
        )
        return remote_confirmed and value.get("completion_pending") is True

    def _candidates(value: Any) -> list[Mapping[str, Any]]:
        found: list[Mapping[str, Any]] = []
        if not isinstance(value, Mapping):
            return found
        found.append(value)
        password_setup = value.get("password_setup")
        if isinstance(password_setup, Mapping):
            found.append(password_setup)
        step_results = value.get("step_results")
        if isinstance(step_results, Mapping):
            password = step_results.get("password")
            if isinstance(password, Mapping):
                found.append(password)
        setup_step_results = value.get("setup_step_results")
        if isinstance(setup_step_results, (list, tuple)):
            for item in setup_step_results:
                if (
                    isinstance(item, Mapping)
                    and str(item.get("step") or "") == "password"
                    and isinstance(item.get("result"), Mapping)
                ):
                    found.append(item["result"])
        return found

    if not any(_pending(value) for value in _candidates(result_summary)):
        return False
    data = _common._decode(run.get("data"))
    data = data if isinstance(data, Mapping) else {}
    intent = _remote_write_checkpoint(data)
    receipt = data.get("remote_receipt")
    if not isinstance(receipt, Mapping):
        return False
    receipt_state = str(
        receipt.get("receipt_state") or receipt.get("outcome") or ""
    ).strip().lower()
    if receipt_state not in {"local_commit_required", "confirmed"}:
        return False
    intent_action = str(intent.get("action") or "").strip()
    receipt_action = str(receipt.get("action") or "").strip()
    intent_request_id = str(intent.get("request_id") or "").strip()
    receipt_request_id = str(receipt.get("request_id") or "").strip()
    if (
        not intent_action
        or not receipt_action
        or receipt_action != intent_action
        or not intent_request_id
        or not receipt_request_id
        or receipt_request_id != intent_request_id
        or str(intent.get("receipt_state") or intent.get("state") or "").strip().lower()
        != receipt_state
    ):
        return False
    detail = receipt.get("detail")
    if not isinstance(detail, Mapping) or not _pending(detail):
        return False
    if receipt_state == "confirmed" and not all(
        detail.get(key) is True
        for key in ("local_business_writeback_confirmed", "local_readback_confirmed")
    ):
        return False
    return True


def finish_run(
    run_id: int,
    *,
    status: str,
    message: str = "",
    result_summary: dict | None = None,
    error: str | None = None,
    execution_id: str | None = None,
    lease_token: str | None = None,
    force_terminate: bool = False,
    settlement_intent=None, settlement_domain=None, deadline=None,
    _settlement_conn=None,
) -> dict:
    if settlement_intent is not None:
        from core.storage.operations import settlements
        if settlement_domain is None:
            raise ValueError("settlement_domain is required")
        return settlements.submit_intent(settlement_intent, domain=settlement_domain, deadline=deadline)
    if _settlement_conn is None:
        _schema.init_operation_schema()
    status_value = _common._status(status)
    if status_value not in _common._TERMINAL_STATUSES:
        raise ValueError(f"非法终态: {status_value}")
    parent_task_id: int | None = None
    dependency_result = dict(result_summary or {})
    requested_terminal_status = status_value
    cancel_reason = _common._text(
        dependency_result.get("cancel_reason") or message or error or "任务被终止",
        500,
    ).strip() or "任务被终止"
    idempotent = False
    with (_common._connect() if _settlement_conn is None else nullcontext(_settlement_conn)) as conn, conn.cursor() as cur, (bulk_execution.fact_update(conn, int(run_id)) if _settlement_conn is None else nullcontext(None)):
        cur.execute(
            f"""
            SELECT r.*, t.task_type, t.parent_task_id, t.email_snapshot, t.trigger
            FROM {_common._table('operation_runs')} r
            JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.id=%s
            FOR UPDATE OF r
            """,
            (int(run_id),),
        )
        found = cur.fetchone()
        if not found:
            raise LookupError("执行实例不存在")
        found = dict(found)
        parent_task_id = int(found["parent_task_id"]) if found.get("parent_task_id") else None
        found_status = str(found.get("status") or "").strip().lower()
        if force_terminate and found_status not in _common._TERMINAL_STATUSES:
            # 在锁定 Run 行时决定终态，避免 worker 抢到排队 Run 后与取消语义竞争。
            requested_terminal_status = "cancelled" if found_status == "queued" else "stopped"
            status_value = requested_terminal_status
        if execution_id and str(found.get("execution_id") or "") != str(execution_id):
            raise PermissionError("执行实例 fence 不匹配，拒绝覆盖其他 worker 的结果")
        if lease_token:
            cur.execute(
                f"""
                SELECT 1 FROM {_common._table('account_operation_leases')}
                WHERE run_id=%s AND lease_token=%s AND expires_at > now()
                """,
                (int(run_id), str(lease_token)),
            )
            if not cur.fetchone():
                raise PermissionError("账号 lease owner 不匹配，拒绝写入结果")
        if str(found.get("status") or "") in _common._TERMINAL_STATUSES:
            result = _common._row(found) or {}
            idempotent = True
        else:
            intent = _remote_write_checkpoint(found.get("data"))
            receipt = str(intent.get("receipt_state") or intent.get("state") or "started")
            explicit_remote_rejection = (
                str(found.get("task_type") or "") == "extract_link"
                and status_value in {"failed", "unsupported"}
                and str(dependency_result.get("remote_result_state") or "").lower() == "rejected"
            )
            confirmed_extract_failure = (
                status_value == "failed"
                and _confirmed_extract_terminal_failure(cur, found, dependency_result)
            )
            password_page_failure = (
                str(found.get("task_type") or "") in {"token_refresh", "live_check"}
                and status_value == "failed"
                and str(dependency_result.get("cause_code") or "") in {
                    "password_change_required", "password_page_error",
                }
            )
            confirmed_independent_partial = (
                status_value == "partial_success" and receipt == "confirmed"
                and (_confirmed_independent_payment_partial(cur, found, dependency_result)
                     or _confirmed_account_setup_partial(cur, found, dependency_result))
            )
            confirmed_plan_refresh = (
                status_value in {"failed", "partial_success", "cancelled", "stopped"}
                and _confirmed_plan_refresh(found, dependency_result)
            )
            password_change_pending_closeout = _password_change_pending_closeout(
                found, dependency_result,
            )
            if password_change_pending_closeout and status_value in {"success", "partial_success"}:
                status_value = "failed"
                if not error:
                    error = str(
                        dependency_result.get("cause_code")
                        or dependency_result.get("error")
                        or "password_change_completion_pending"
                    )
            if status_value != "deactivated" and intent and receipt not in {"rejected", "not_submitted"} and (
                not (
                    explicit_remote_rejection
                    or confirmed_extract_failure
                    or confirmed_independent_partial
                    or confirmed_plan_refresh
                    or password_change_pending_closeout
                )
                and (status_value != "success" or receipt != "confirmed")
            ):
                # 未确认的远端写入保留在当前 Run，人工重跑会创建新的 Run，
                # 不会覆盖这条用于排障与审计的远端请求证据。
                dependency_result.update({
                    "outcome": "request_unknown",
                    "reconcile_required": True,
                    "requested_status": status_value,
                    "remote_action": intent.get("action"),
                    "remote_intent_state": receipt,
                })
                if not password_page_failure:
                    status_value = "attention_required"
                # 回执是否完整独立保留，不覆盖驱动已经报告的具体失败。
                if not error:
                    error = message or f"{intent.get('action') or '远端请求'}未保存完整回执"
            task_type = str(found.get("task_type") or "")
            dependency_result.update({
                "task_type": task_type, "task_id": int(found["task_id"]), "run_id": int(run_id),
            })
            # 终态仍叫 complete；失败位置独立保存，不能被收口阶段覆盖。
            cur.execute(
                f"SELECT * FROM {_common._table('operation_events')} WHERE run_id=%s ORDER BY created_at, id",
                (int(run_id),),
            )
            failure_snapshot = build_progress_snapshot(
                int(found["task_id"]), int(run_id), task_type,
                {**(_common._row(found) or {}), "status": status_value, "error_message": error or "", "result_summary": dependency_result},
                [_common._normalize_compatibility_event(_common._read_event(dict(row))) for row in cur.fetchall()],
            )
            failure = failure_snapshot.get("failure") or {}
            failure_stage = failure.get("stage") or (
                found.get("progress_stage") if status_value != "success" and error else None
            )
            failure_context = {
                "failure_stage": failure_stage,
                "failure_event_id": failure.get("event_id"),
                "failure_evidence": failure.get("evidence"),
            } if failure_stage and failure_stage not in {"complete", "queued"} else {}
            dependency_result.update(failure_context)
            category, code, error_message = _common._error_fields(
                error or "", stage=str(failure_stage or "complete"), task_type=task_type,
                result_summary=dependency_result, task_status=status_value,
            )
            if password_change_pending_closeout:
                # P1 收尾失败已经有结构化具体原因；不要让通用阶段兜底码
                # 覆盖 token_revoked 等可重跑原因。
                specific_cause = str(
                    dependency_result.get("cause_code")
                    or dependency_result.get("error_code")
                    or ""
                ).strip()
                if specific_cause:
                    code = specific_cause
            cur.execute(
                f"""
                UPDATE {_common._table('operation_runs')}
            SET status=%s,
                cancel_requested_at=CASE WHEN %s IN ('cancelled', 'stopped')
                    THEN COALESCE(cancel_requested_at, now()) ELSE cancel_requested_at END,
                cancel_reason=CASE WHEN %s IN ('cancelled', 'stopped')
                    THEN COALESCE(cancel_reason, %s) ELSE cancel_reason END,
                completed_at=now(), heartbeat_at=now(), progress_stage='complete',
                duration_ms=GREATEST(0, (EXTRACT(EPOCH FROM (now() - COALESCE(started_at, created_at))) * 1000)::BIGINT),
                error_category=%s, error_code=%s, error_message=%s, result_summary=%s::jsonb,
                data=data || %s::jsonb
                WHERE id=%s RETURNING *
                """,
                (
                    status_value, requested_terminal_status, requested_terminal_status,
                    cancel_reason, category, code, error_message,
                    _common._json(dependency_result), _common._json(failure_context), int(run_id),
                ),
            )
            run = dict(cur.fetchone())
            target_status = {
                "success": "credential_valid" if task_type == "codex_retry" else "completed",
                "attention_required": "credential_pending_confirmation" if task_type == "codex_retry" else "attention_required",
                "deactivated": "account_deactivated",
                "cancelled": "cancelled",
                "stopped": "cancelled",
            }.get(status_value, "failed")
            if task_type == "extract_link" and status_value in {"failed", "unsupported"}:
                target_status = "account_available"
            cur.execute(
                f"""
                UPDATE {_common._table('operation_tasks')}
                SET status=%s, target_status=%s, current_stage='complete', updated_at=now(),
                    completed_at=now(), error_category=%s, error_code=%s, error_message=%s,
                    next_actions=%s::jsonb, data=data || %s::jsonb
                WHERE id=%s AND last_run_id=%s
                """,
                (
                    status_value, target_status, category, code, error_message,
                    _common._json(
                        [] if status_value in {"success", "deactivated"}
                        else [{"action": "retry", "label": "重新执行"}]
                    ),
                    _common._json(failure_context),
                    int(run["task_id"]), int(run_id),
                ),
            )
            event_uuid = uuid.uuid4().hex
            final_message = message or error_message or {
                "success": "Codex 凭证已确认并保存",
                "attention_required": "OAuth callback 已提交，凭证仍待确认",
                "cancelled": "执行已在安全检查点取消",
                "deactivated": "账号已确认不可用",
            }.get(status_value, f"执行结束：{status_value}")
            cur.execute(
                f"""
                INSERT INTO {_common._table('operation_events')} (
                    event_uuid, task_id, run_id, source_system, source_id,
                    level, stage, event_type, error_category, error_code, message, detail
                ) VALUES (%s, %s, %s, %s, %s, %s, 'complete', %s,
                          %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    event_uuid, int(run["task_id"]), int(run_id),
                    str(run.get("source_system") or "native_operations"), event_uuid,
                    "INFO" if status_value == "success" else "WARNING",
                    f"run.{status_value}", category, code, _common._text(final_message, 1400),
                    _common._json({"status": status_value}),
                ),
            )
            terminal_event_id = int(cur.fetchone()["id"])
            cur.execute(
                f"""
                UPDATE {_common._table('operation_resources')}
                SET state='reconciliation_required',
                    detail=detail || %s::jsonb
                WHERE run_id=%s AND state='acquired'
                """,
                (_common._json({"terminal_run_status": status_value}), int(run_id)),
            )
            if _settlement_conn is None:
                cur.execute(f"DELETE FROM {_common._table('account_operation_leases')} WHERE run_id=%s", (int(run_id),))
            elif lease_token:
                cur.execute(f"DELETE FROM {_common._table('account_operation_leases')} WHERE run_id=%s AND lease_token=%s", (int(run_id), str(lease_token)))
            if run.get("batch_id"):
                _projection._refresh_batches(cur, [int(run["batch_id"])])
            result = _common._row(run) or {}
            result["task_type"] = task_type
            result["parent_task_id"] = parent_task_id
            result["terminal_event_id"] = terminal_event_id
            result["terminal_event_uuid"] = event_uuid
        if parent_task_id:
            # Child terminal state is reflected in the same transaction.  The
            # helper is idempotent and also works when finish_run is retried.
            _reconcile_parent_task_cur(cur, parent_task_id, child_task_id=int(found["task_id"]))
        if str(found.get("task_type") or "") == "password_setup":
            from core.storage.operations import registration_completion

            registration_completion.reconcile_for_child(cur, int(found["task_id"]))
        if (str(result.get("status") or status_value) == "success"
                and str(found.get("source_system") or "") == "registration_jobs"):
            # 直接来源于旧注册 Job 的 Run 仍沿用原有收口入口。
            from core.storage.operations import registration_completion

            registration_completion.reconcile_parent_registration_job(
                cur, int(found.get("source_id") or 0), account_id=found.get("account_id"),
            )
        elif (str(result.get("status") or status_value) == "success"
              and str(found.get("source_system") or "") == "webui_runtime"
              and str(found.get("task_type") or "") in {"account_setup_retry", "password_setup"}):
            # 账号配置子 Run 成功后，按当前父链在同一事务内回写原注册 Job。
            from core.storage.operations import registration_completion

            registration_completion.reconcile_parent_registration_job_for_child(
                cur, int(found["task_id"]), child_run_id=int(run_id),
            )
        elif (str(result.get("status") or status_value) == "success"
              and str(found.get("source_system") or "") == "native_operations"
              and str(found.get("task_type") or "") in {"plan_check", "codex_retry"}):
            # 套餐及 Codex 补跑按冻结的原 Job 关联完成收口。
            from core.storage.operations import registration_completion

            registration_completion.reconcile_parent_registration_job_for_child(
                cur, int(found["task_id"]), child_run_id=int(run_id),
            )
    if _settlement_conn is not None:
        return result
    task_run_log.append(
        result.get("log_file"),
        level="INFO" if str(result.get("status") or status_value) == "success" else "WARNING",
        message=message or result.get("error_message") or f"执行结束：{result.get('status') or status_value}",
        task_id=int(result["task_id"]),
        run_id=int(run_id),
        stage="complete",
        event_type=f"run.{result.get('status') or status_value}",
        fields={"status": result.get("status") or status_value, "idempotent": idempotent},
        event_id=result.get("terminal_event_id"), event_uuid=result.get("terminal_event_uuid"),
    )
    try:
        ready_dependencies = mark_task_dependency_ready(
            child_source_system=str(result.get("source_system") or "native_operations"),
            child_source_id=str(result["task_id"]),
            child_status=str(result.get("status") or status_value),
            child_result=dependency_result,
        )
        if ready_dependencies:
            from core.operations import task_gateway

            for dependency in ready_dependencies:
                task_gateway.notify_dependency_ready(dependency)
    except Exception:
        # A dependency projection is a follow-up; never turn a completed
        # remote operation into a failure merely because its wakeup failed.
        logger.exception("写入父任务依赖 ready 状态失败：run_id=%s", run_id)
    return result


def has_active_runtime_operations(
    *,
    task_types: Iterable[str] | None = None,
    source_systems: Iterable[str] | None = None,
) -> bool:
    from core.storage.operations import recovery

    return recovery.has_active_runtime_operations(task_types=task_types, source_systems=source_systems)


def list_active_runtime_recovery_exclusions(
    *,
    task_types: Iterable[str] | None = None,
    source_systems: Iterable[str] | None = None,
) -> dict[str, Any]:
    from core.storage.operations import recovery

    return recovery.list_active_runtime_recovery_exclusions(task_types=task_types, source_systems=source_systems)


def list_interrupted_runtime_runs(
    *, task_type: str | None = None,
    recovery_reason: str | None = None,
    limit: int = 500,
) -> list[dict]:
    from core.storage.operations import recovery

    return recovery.list_interrupted_runtime_runs(task_type=task_type, recovery_reason=recovery_reason, limit=limit)


def list_reconciliation_accounts(
    *,
    task_type: str,
    account_ids: Iterable[int] | None = None,
    source_systems: Iterable[str] | None = ("native_operations",),
    limit: int = 5000,
) -> list[dict]:
    from core.storage.operations import recovery

    return recovery.list_reconciliation_accounts(task_type=task_type, account_ids=account_ids, source_systems=source_systems, limit=limit)


def mark_runtime_run_projection_reconciled(run_id: int, *, repaired_count: int = 0) -> bool:
    from core.storage.operations import recovery

    return recovery.mark_runtime_run_projection_reconciled(run_id, repaired_count=repaired_count)


def recover_interrupted_runtime_runs(*, stale_after_seconds: int = 15 * 60) -> int:
    from core.storage.operations import recovery

    return recovery.recover_interrupted_runtime_runs(stale_after_seconds=stale_after_seconds)


def recover_stale_task_dependencies(*, stale_after_seconds: int = 15 * 60) -> int:
    from core.storage.operations import recovery

    return recovery.recover_stale_task_dependencies(stale_after_seconds=stale_after_seconds)


def projection_worker_status() -> dict[str, object]:
    from core.storage.operations import projection

    return projection.projection_worker_status()


def get_task(task_id: int, *, include_events: bool = True) -> dict | None:
    from core.storage.operations import store

    return store.get_task(task_id, include_events=include_events)


__all__ = ['acquire_account_lease', 'active_run_for_account', 'append_runtime_event', 'apply_task_dependency_result', 'claim_next_queued_run', 'claim_run', 'claim_task_dependency', 'complete_task_dependency', 'create_runtime_batch', 'create_runtime_task', 'create_runtime_tasks_many', 'fence_execution', 'finish_run', 'get_run', 'get_task', 'has_active_runtime_operations', 'heartbeat_run', 'is_run_cancel_requested', 'list_active_runtime_recovery_exclusions', 'list_dispatchable_runs', 'list_interrupted_runtime_runs', 'list_queued_runs', 'list_ready_task_dependencies', 'list_reconciliation_accounts', 'mark_run_settling', 'mark_runtime_batch_empty', 'mark_runtime_run_projection_reconciled', 'mark_task_dependency_ready', 'projection_worker_status', 'reconcile_parent_task', 'record_remote_intent', 'record_remote_receipt', 'recover_interrupted_runtime_runs', 'recover_stale_task_dependencies', 'refresh_runtime_batches', 'register_resource', 'register_task_dependency', 'release_account_lease', 'release_resource', 'request_run_cancel', 'requeue_claimed_run', 'retry_runtime_task', 'set_runtime_batch_skipped', 'terminate_run']


def acquire_account_lease(account_id: int, run_id: int, **kwargs: Any) -> str | None:
    return _acquire_account_lease(account_id=account_id, run_id=run_id, **kwargs)


def reconcile_parent_task(task_id: int) -> dict | None:
    return _reconcile_parent_task(task_id)


def link_registration_setup_parent(*, task_id: int, job_id: int, parent_task_id: int) -> None:
    """仅在明确重跑原注册补全时，补齐该来源子任务的父关联。"""
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {_common._table('operation_tasks')} child
                SET parent_task_id=parent.id, root_task_id=COALESCE(parent.root_task_id,parent.id)
                FROM {_common._table('operation_tasks')} parent
                WHERE child.id=%s AND parent.id=%s AND child.id<>parent.id
                  AND child.source_system='webui_runtime' AND child.source_id=%s
                  AND child.task_type='account_setup_retry'
                  AND (child.parent_task_id IS NULL OR child.parent_task_id=parent.id)
                  AND (parent.account_id IS NULL OR parent.account_id=child.account_id)
                  AND (
                    EXISTS (SELECT 1 FROM {_common._table('operation_runs')} r
                            WHERE r.task_id=parent.id AND r.source_system='registration_jobs'
                              AND r.source_id=%s)
                    OR (parent.source_system='registration_jobs' AND parent.source_id=%s)
                  )
                RETURNING child.id""",
            (int(task_id), int(parent_task_id), f"registration-account-setup:{int(job_id)}",
             str(int(job_id)), str(int(job_id))),
        )
        if cur.fetchone() is None:
            raise ValueError("注册补全任务来源或父任务关联不匹配")
        _reconcile_parent_task_cur(cur, int(parent_task_id), child_task_id=int(task_id))
