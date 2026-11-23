# -*- coding: utf-8 -*-
"""失联执行与依赖恢复，以及跨旧模型恢复的排除查询。有效租约和代际栅栏保持原事务语义。"""
from __future__ import annotations

import uuid
import threading
from datetime import datetime
from typing import Any, Iterable, Mapping
from core.storage import postgres as postgres_store, records as record_store
from core.bulk_operations import execution as bulk_execution
from core.storage.operations import common as _common
from core.storage.operations import schema as _schema
from core.storage.operations import projection as _projection
from core.storage.operations import runtime as _runtime

_SETTLEMENT_RECOVERY_LOCK = threading.RLock()
_SETTLEMENT_RECOVERY_CURSOR: dict[str, str] = {}


def _original_process_exited(owner: Mapping) -> bool:
    """A callback exit/old local marker cannot prove the carrier process died."""
    from core.storage.operations import permits

    process = dict(owner)
    process.pop("thread_id", None)
    if not all(process.get(key) for key in ("host_id", "pid", "process_start")):
        return False
    return permits.owner_liveness(process) == "exited"


def _recovery_result(run: Mapping) -> dict:
    """Use the existing orphan classifier; never reconstruct a lost success."""
    data = _common._decode(run.get("data")) or {}
    intent = data.get("remote_intent") or {}
    receipt_state = intent.get("receipt_state")
    if receipt_state is None:
        receipt_state = intent.get("state")
    if receipt_state is None:
        receipt_state = "started"
    unknown = intent.get("kind") == "remote_write" and receipt_state not in {"rejected", "not_submitted"}
    summary = dict(_common._decode(run.get("result_summary")) or {})
    summary["cause_code"] = summary.get("cause_code") or "worker_interrupted"
    if unknown:
        summary.update(outcome="request_unknown", reconcile_required=True,
                       execution_id=str(run.get("execution_id") or ""),
                       lease_owner=str(run.get("execution_id") or ""),
                       remote_action=intent.get("action"), remote_intent_state=receipt_state)
    else:
        summary.update(outcome="interrupted", recovery_reason="worker_restart")
    return {
        "status": "attention_required" if unknown else "interrupted",
        "result_summary": _common._scrub(summary),
        "error_message": ("执行进程已中断，当前步骤未完成回执核验" if unknown
                          else "执行进程已重启，原 attempt 中断"),
    }


def _recovery_resource_disposition(resources) -> str:
    return "cleanup_pending" if resources else "no_blocking_resources"


def _participating_ticket(row, domain):
    metadata = _common._decode(row.get("metadata")) or {}
    ticket = metadata.get("settlement_ticket")
    if not isinstance(ticket, Mapping) or ticket.get("version") != 1:
        return None
    for key, expected in (("domain_id", domain.domain_id), ("operation_schema", domain.operation_schema),
                          ("permit_schema", domain.permit_schema), ("permit_id", row.get("permit_id")),
                          ("execution_id", row.get("execution_id")), ("run_id", row.get("run_id"))):
        if not expected or str(ticket.get(key) or "") != str(expected):
            return None
    if not all(ticket.get(key) for key in ("ticket_id", "run_uuid", "task_id", "owner")):
        return None
    return dict(ticket)


def _exact_receipt(cur, ticket):
    cur.execute(f"""SELECT id FROM {_common._table('operation_settlement_receipts')}
        WHERE domain_id=%s AND permit_id=%s AND execution_id=%s AND ticket_id=%s
          AND run_id=%s AND run_uuid=%s""",
        tuple(ticket[key] for key in ("domain_id", "permit_id", "execution_id", "ticket_id", "run_id", "run_uuid")))
    return cur.fetchone()


def _recover_terminal_permit(cur, *, run, ticket, leases):
    """原进程退出后补齐终态回收证明，保留既有业务结果和终止事件。"""
    from core.storage.operations import settlements

    cur.execute(f"""SELECT id,event_uuid FROM {_common._table('operation_events')}
        WHERE run_id=%s AND task_id=%s AND event_type=%s AND event_uuid <> ''
        ORDER BY id DESC LIMIT 1""",
        (int(run["id"]), int(run["task_id"]), f"run.{run['status']}"))
    event = cur.fetchone()
    if not event:
        return 0, False
    resources = settlements._resource_snapshot(cur, int(run["id"]))
    for lease in leases:
        cur.execute(f"""DELETE FROM {_common._table('account_operation_leases')}
            WHERE run_id=%s AND lease_token=%s AND expires_at <= now()""",
            (int(run["id"]), str(lease["lease_token"])))
    settlements.write_disposition(cur, ticket=ticket, result={
        "status": str(run["status"]),
        "event_uuid": str(event["event_uuid"]), "event_id": int(event["id"]),
        "original_intent_committed": False, "recovery_reason": "worker_exit_confirmed",
        "terminal_result_preserved": True,
        "resource_disposition": _recovery_resource_disposition(resources),
        "resources": resources,
    })
    return 1, True


def _recover_participating_one(row, *, domain, stale_seconds):
    """One exact transaction; callers release only after this connection commits."""
    from core.storage.operations import permits, settlements

    permit_table = permits._permit_table(domain.permit_schema)
    ready_dependencies = []
    with _common.settlement_scope(domain):
        with _common._connect() as conn, conn.cursor() as cur:
            # Start exclusive: SHARE followed by an upgrade can deadlock two recoverers.
            cur.execute(f"""SELECT * FROM {permit_table}
                WHERE permit_id=%s AND execution_id=%s AND released_at IS NULL
                FOR UPDATE SKIP LOCKED""", (row["permit_id"], row["execution_id"]))
            locked = cur.fetchone()
            if not locked:
                return 0, False
            ticket = _participating_ticket(locked, domain)
            if ticket is None or not _original_process_exited(ticket["owner"]):
                return 0, False
            # Receipts and independent dispositions take precedence even if the
            # same Run has already moved to a newer execution or terminal state.
            if _exact_receipt(cur, ticket):
                return 0, True
            disposition = settlements.read_disposition(ticket, domain=domain, conn=conn)
            if disposition:
                if disposition["result"].get("resource_disposition") == "cleanup_pending":
                    managed = settlements._lock_original_managed_target(cur, ticket)
                    settlements._lock_origin(conn, cur, ticket, managed=managed)
                    settlements.confirm_disposition_resources(ticket, domain=domain, conn=conn)
                return 0, True
            managed = settlements._lock_original_managed_target(cur, ticket)
            settlements._lock_origin(conn, cur, ticket, managed=managed)
            cur.execute(f"SELECT * FROM {_common._table('operation_tasks')} WHERE id=%s FOR UPDATE",
                        (int(ticket["task_id"]),))
            task = cur.fetchone()
            cur.execute(f"""SELECT *, (heartbeat_at IS NULL OR
                heartbeat_at < now()-(%s * interval '1 second')) AS heartbeat_stale
                FROM {_common._table('operation_runs')} WHERE id=%s FOR UPDATE""",
                (stale_seconds, int(ticket["run_id"])))
            run = cur.fetchone()
            if (not task or not run or int(run["task_id"]) != int(ticket["task_id"])
                    or str(run.get("run_uuid")) != str(ticket["run_uuid"])
                    or str(run.get("execution_id") or "") != str(ticket["execution_id"])
                    or run.get("source_system") in {"registration_jobs", "account_action_tasks"}):
                return 0, False
            terminal = str(run.get("status")) in _common._TERMINAL_STATUSES
            if not terminal and (str(run.get("status")) not in {"running", "cancelling", "settling"}
                                 or not run.get("heartbeat_stale")):
                return 0, False
            cur.execute(f"""SELECT lease_token,expires_at > now() AS valid
                FROM {_common._table('account_operation_leases')} WHERE run_id=%s FOR UPDATE""",
                (int(ticket["run_id"]),))
            leases = list(cur.fetchall())
            if any(lease["valid"] for lease in leases) or not _original_process_exited(ticket["owner"]):
                return 0, False
            if _exact_receipt(cur, ticket) or settlements.read_disposition(ticket, domain=domain, conn=conn):
                return 0, True
            if terminal:
                return _recover_terminal_permit(cur, run=run, ticket=ticket, leases=leases)
            result = _recovery_result(run)
            status, summary = result["status"], result["result_summary"]
            category, code, message = _common._error_fields(
                result["error_message"], stage="complete", task_type=str(task.get("task_type") or ""),
                result_summary=summary, task_status=status)
            cur.execute(f"""UPDATE {_common._table('operation_runs')}
                SET status=%s,completed_at=now(),heartbeat_at=now(),progress_stage='complete',
                    error_message=%s,error_category=%s,error_code=%s,result_summary=%s::jsonb
                WHERE id=%s AND run_uuid=%s AND execution_id=%s""",
                (status, message, category, code, _common._json(summary), int(run["id"]),
                 str(ticket["run_uuid"]), str(ticket["execution_id"])))
            cur.execute(f"""UPDATE {_common._table('operation_tasks')}
                SET status=%s,current_stage=%s,completed_at=now(),updated_at=now(),
                    error_message=%s,error_category=%s,error_code=%s,
                    target_status=CASE WHEN %s='attention_required' THEN 'attention_required' ELSE target_status END,
                    next_actions=%s::jsonb WHERE id=%s AND last_run_id=%s""",
                (status, "complete" if status == "attention_required" else "interrupted",
                 message, category, code, status, _common._json([{"action": "retry", "label": "重新执行"}]),
                 int(task["id"]), int(run["id"])))
            current_task = bool(cur.rowcount)
            cur.execute(f"""UPDATE {_common._table('operation_resources')}
                SET state='reconciliation_required',
                    detail=detail || '{{"reason":"worker_restart"}}'::jsonb
                WHERE run_id=%s AND state='acquired'""", (int(run["id"]),))
            resources = settlements._resource_snapshot(cur, int(run["id"]))
            event_uuid = uuid.uuid4().hex
            cur.execute(f"""INSERT INTO {_common._table('operation_events')}
                (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
                VALUES (%s,%s,%s,%s,%s,'WARNING',%s,%s,%s,%s::jsonb)""",
                (event_uuid, int(task["id"]), int(run["id"]), str(task["source_system"]), event_uuid,
                 "complete" if status == "attention_required" else "interrupted", f"run.{status}", message,
                 _common._json({"reason": "worker_restart", "outcome": summary["outcome"],
                                "reconcile_required": status == "attention_required",
                                "original_intent_committed": False})))
            for lease in leases:
                cur.execute(f"""DELETE FROM {_common._table('account_operation_leases')}
                    WHERE run_id=%s AND lease_token=%s AND expires_at <= now()""",
                    (int(run["id"]), str(lease["lease_token"])))
            if current_task:
                if task.get("parent_task_id"):
                    _runtime._reconcile_parent_task_cur(cur, int(task["parent_task_id"]))
                # Keep the logical-child wakeup fenced to this Task's current Run.
                cur.execute(f"""UPDATE {_common._table('operation_task_dependencies')}
                    SET status='ready',child_status=%s,child_result=%s::jsonb,ready_at=now(),
                        next_attempt_at=NULL,last_error=NULL,updated_at=now()
                    WHERE status='waiting' AND child_source_system=%s AND child_source_id=%s
                    RETURNING *""",
                    (status, _common._json(summary), str(task["source_system"]), str(task["id"])))
                ready_dependencies = [_common._row(dict(item)) or {} for item in cur.fetchall()]
                if task.get("task_type") == "codex_retry" and run.get("account_id"):
                    cur.execute(f"""UPDATE {postgres_store.qualified(record_store.ACCOUNTS.name)}
                        SET codex_execution_status='empty',codex_active_run_id=NULL,
                            codex_last_run_status=%s,
                            codex_status=CASE WHEN codex_status='success' THEN codex_status ELSE %s END,
                            updated_at=%s
                        WHERE id=%s AND codex_active_run_id=%s""",
                        (status, status, datetime.now().isoformat(timespec="seconds"),
                         int(run["account_id"]), int(run["id"])))
            _projection._refresh_batches(cur, [run.get("batch_id")])
            if managed:
                from core.storage.operations import bulk
                bulk.record_managed_change(conn, int(managed["id"]), event_kind="recovered")
            settlements.write_disposition(cur, ticket=ticket, result={
                "status": status, "result_summary": summary, "event_uuid": event_uuid,
                "original_intent_committed": False, "recovery_reason": "worker_exit_confirmed",
                "resource_disposition": _recovery_resource_disposition(resources),
                "resources": resources,
            })
    if ready_dependencies:
        from core.operations import task_gateway
        for dependency in ready_dependencies:
            task_gateway.notify_dependency_ready(dependency)
    return 1, True


def recover_participating_executions(*, stale_after_seconds: int = 15 * 60, limit: int = 32) -> dict:
    """Bounded healthy-owner recovery barrier before any permit recovery scan."""
    from core.storage.operations import permits, settlements

    with _SETTLEMENT_RECOVERY_LOCK:
        _schema.init_operation_schema()
        domain = permits._settlement_domain()
        # The ordinary fallback cannot be made faster to manufacture recovery.
        stale_seconds = max(15 * 60, min(7 * 24 * 60 * 60, int(stale_after_seconds or 0)))
        with _common.settlement_scope(domain):
            with _common._connect() as conn, conn.cursor() as cur:
                cursor = _SETTLEMENT_RECOVERY_CURSOR.get(domain.domain_id, "")
                cur.execute(f"""SELECT * FROM {permits._permit_table(domain.permit_schema)}
                    WHERE released_at IS NULL AND metadata ? 'settlement_ticket'
                      AND permit_id > %s
                    ORDER BY permit_id LIMIT %s""", (cursor, max(1, min(256, int(limit)))))
                candidates = list(cur.fetchall())
                if not candidates and cursor:
                    _SETTLEMENT_RECOVERY_CURSOR.pop(domain.domain_id, None)
                    cur.execute(f"""SELECT * FROM {permits._permit_table(domain.permit_schema)}
                        WHERE released_at IS NULL AND metadata ? 'settlement_ticket'
                        ORDER BY permit_id LIMIT %s""", (max(1, min(256, int(limit))),))
                    candidates = list(cur.fetchall())
                if candidates:
                    _SETTLEMENT_RECOVERY_CURSOR[domain.domain_id] = str(candidates[-1]["permit_id"])
        recovered, cleanup_done, released = 0, 0, 0
        for row in candidates:
            ticket = _participating_ticket(row, domain)
            if ticket is None or not _original_process_exited(ticket["owner"]):
                continue
            # Storage also enforces owner-exit/local callback handoff on claim.
            # Never adopt arbitrary domain jobs while their callback is live.
            for _ in range(8):
                job = settlements.run_cleanup_once(domain=domain, permit_id=row["permit_id"],
                                                   execution_id=row["execution_id"])
                if not job or job.get("state") not in {"done", "superseded"}:
                    break
                cleanup_done += 1
            try:
                count, release_ready = _recover_participating_one(
                    row, domain=domain, stale_seconds=stale_seconds)
                recovered += count
            except Exception:
                # A commit may have succeeded before its acknowledgement was
                # lost. Only exact durable proof permits the later release.
                with _common.settlement_scope(domain):
                    proof = settlements.read_disposition(ticket, domain=domain)
                    if proof is None:
                        with _common._connect() as conn, conn.cursor() as cur:
                            proof = _exact_receipt(cur, ticket)
                if proof is None:
                    raise
                release_ready = True
            if release_ready:
                released += int(permits.release(
                    row["permit_id"], row["execution_id"], reason="settlement_recovery_confirmed",
                    schema=domain.permit_schema, database_url=domain.database_url))
        result = permits.recover_execution_permits()
        return {**result, "released": result["released"] + released,
                "recovered": recovered, "cleanup_done": cleanup_done}


def recover_stale_task_dependencies(*, stale_after_seconds: int = 15 * 60) -> int:
    """Return abandoned dependency claims to the ready queue after restart."""
    _schema.init_operation_schema()
    from core.storage.operations import permits

    recover_participating_executions(stale_after_seconds=stale_after_seconds)
    age = max(1, int(stale_after_seconds))
    with _common._connect() as conn, conn.cursor() as cur:
        permits.admission_lock(conn)
        cur.execute(
            f"""
            UPDATE {_common._table('operation_task_dependencies')}
            SET status='ready', next_attempt_at=now(), updated_at=now(),
                last_error=COALESCE(last_error, 'dispatcher claim timed out')
            WHERE status='running'
              AND updated_at < now() - (%s * interval '1 second')
              AND NOT EXISTS (SELECT 1 FROM {_common._permit_table()} p
                WHERE p.execution_key='operation_dependency:' || id::text AND p.released_at IS NULL)
            """,
            (age,),
        )
        return cur.rowcount


def list_interrupted_runtime_runs(
    *, task_type: str | None = None,
    recovery_reason: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """列出因 worker 中断而收口、仍需业务投影清理的 Run。"""
    _schema.init_operation_schema()
    clauses = [
        "r.status='interrupted'",
        "r.result_summary->>'recovery_reason'=%s",
        "COALESCE(r.result_summary->>'projection_reconciled', 'false') <> 'true'",
    ]
    params: list[Any] = [str(recovery_reason or "worker_restart")]
    if task_type:
        clauses.append("t.task_type=%s")
        params.append(str(task_type))
    params.append(max(1, min(5000, int(limit or 500))))
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.*, t.task_type, t.email_snapshot, t.trigger, t.parent_task_id
            FROM {_common._table('operation_runs')} r
            JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.id
            LIMIT %s
            """,
            tuple(params),
        )
        return [_common._row(dict(row)) or {} for row in cur.fetchall()]


def mark_runtime_run_projection_reconciled(run_id: int, *, repaired_count: int = 0) -> bool:
    """标记一次中断 Run 的业务投影已经收口，避免周期重复扫描。"""
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {_common._table('operation_runs')}
            SET result_summary=COALESCE(result_summary, '{{}}'::jsonb) ||
                jsonb_build_object(
                    'projection_reconciled', true,
                    'projection_reconciled_count', %s
                )
            WHERE id=%s
              AND status='interrupted'
              AND result_summary->>'recovery_reason'='worker_restart'
            RETURNING id
            """,
            (max(0, int(repaired_count or 0)), int(run_id)),
        )
        return cur.fetchone() is not None


def has_active_runtime_operations(
    *,
    task_types: Iterable[str] | None = None,
    source_systems: Iterable[str] | None = None,
) -> bool:
    """Return whether durable active Runs cover a legacy recovery category."""
    _schema.init_operation_schema()
    clauses = [f"r.status IN ({_common._ACTIVE_RUN_STATUS_SQL})"]
    params: list[Any] = []
    if task_types is not None:
        values = [str(item).strip() for item in task_types if str(item).strip()]
        if not values:
            return False
        clauses.append("t.task_type = ANY(%s)")
        params.append(values)
    if source_systems is not None:
        values = [str(item).strip() for item in source_systems if str(item).strip()]
        if not values:
            return False
        clauses.append("t.source_system = ANY(%s)")
        params.append(values)
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT 1
            FROM {_common._table('operation_runs')} r
            JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE {' AND '.join(clauses)}
            LIMIT 1
            """,
            tuple(params),
        )
        return cur.fetchone() is not None


def list_active_runtime_recovery_exclusions(
    *,
    task_types: Iterable[str] | None = None,
    source_systems: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return row-level legacy recovery fences for active durable Runs.

    Startup recovery must not turn a category-wide boolean into a category-wide
    skip: one native task for account A must not leave an unrelated legacy row
    for account B running forever.  The result is deliberately limited to
    account/source identifiers so callers can pass it to their legacy storage
    recovery predicates without copying task payloads or credentials.
    """
    _schema.init_operation_schema()
    clauses = [f"r.status IN ({_common._ACTIVE_RUN_STATUS_SQL})"]
    params: list[Any] = []
    if task_types is not None:
        values = [str(item).strip() for item in task_types if str(item).strip()]
        if not values:
            return {"account_ids": [], "source_fences": []}
        clauses.append("t.task_type = ANY(%s)")
        params.append(values)
    if source_systems is not None:
        values = [str(item).strip() for item in source_systems if str(item).strip()]
        if not values:
            return {"account_ids": [], "source_fences": []}
        clauses.append("t.source_system = ANY(%s)")
        params.append(values)
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT t.account_id, t.source_system, t.source_id,
                            t.task_type,
                            NULLIF(t.data->>'source_job_id', '') AS source_job_id
            FROM {_common._table('operation_runs')} r
            JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE {' AND '.join(clauses)}
            """,
            tuple(params),
        )
        rows = cur.fetchall()
    account_ids = sorted({
        int(row["account_id"])
        for row in rows
        if row.get("account_id") is not None
    })
    source_fences: set[tuple[str, str]] = set()
    for row in rows:
        source_system = str(row.get("source_system") or "").strip()
        source_id = str(row.get("source_id") or "").strip()
        task_type = str(row.get("task_type") or "").strip()
        # A compatibility projection owns the corresponding legacy row, so
        # its source pair is safe to pass back to that same legacy namespace.
        # A native task's arbitrary source_id is not: the same numeric value
        # can independently exist in another source table.
        if source_system in {"registration_jobs", "account_action_tasks"} and source_id:
            source_fences.add((source_system, source_id))
        # registration_resume is a native WebUI task, but it explicitly points
        # at the legacy registration job it is continuing. Preserve only that
        # declared cross-model mapping, never the native task's own source_id.
        source_job_id = str(row.get("source_job_id") or "").strip()
        if task_type == "registration_resume" and source_job_id:
            source_fences.add(("registration_jobs", source_job_id))
    return {
        "account_ids": account_ids,
        "source_fences": [
            {"source_system": source_system, "source_id": source_id}
            for source_system, source_id in sorted(source_fences)
        ],
    }


def list_reconciliation_accounts(
    *,
    task_type: str,
    account_ids: Iterable[int] | None = None,
    source_systems: Iterable[str] | None = ("native_operations",),
    limit: int = 5000,
) -> list[dict]:
    """List accounts whose current/recent attempt must be reconciled first.

    This is a read-only safety gate for producers that have another durable
    credential source. It treats every non-rejected remote-write checkpoint as
    fenced, including ``started``, ``response_received``,
    ``local_commit_required`` and ``confirmed`` while the attempt is not
    terminal. Explicit ``rejected`` is deliberately not returned.

    已确认未提交的 ``not_submitted`` 回执也不会阻止下一次认证。
    """
    _schema.init_operation_schema()
    clauses = [
        "t.task_type=%s",
        # Only the task's current Run can fence a new producer submission.
        # A prior request_unknown Run remains in history for audit/reconcile,
        # but a successful or queued retry replaces it as the active safety
        # decision for this logical task.
        "r.id=t.last_run_id",
        "("
        "t.status='attention_required' OR r.status='attention_required' "
        "OR COALESCE(r.result_summary->>'outcome','')='request_unknown' "
        "OR COALESCE(r.result_summary->>'reconcile_required','false')='true' "
        "OR ("
        "r.status NOT IN ('success','partial_success','failed','stopped','cancelled',"
        "'interrupted','deactivated','unsupported','attention_required') "
        "AND r.data->'remote_intent'->>'kind'='remote_write' "
        "AND COALESCE(r.data->'remote_intent'->>'receipt_state',"
        "r.data->'remote_intent'->>'state','started') NOT IN ('rejected','not_submitted')"
        ")"
        ")",
    ]
    params: list[Any] = [str(task_type or "").strip()]
    requested_account_ids: list[int] | None = None
    if account_ids is not None:
        requested_account_ids = list(dict.fromkeys(int(item) for item in account_ids))
        if not requested_account_ids:
            return []
        clauses.append("t.account_id = ANY(%s)")
        params.append(requested_account_ids)
    if source_systems is not None:
        values = [str(item).strip() for item in source_systems if str(item).strip()]
        if not values:
            return []
        clauses.append("t.source_system = ANY(%s)")
        params.append(values)
    requested_limit = max(1, int(limit or 5000))
    # A caller that supplies an explicit candidate set is using this as a
    # safety gate, not pagination. Return every requested account even when a
    # small default limit was passed; otherwise a producer could silently
    # skip an account whose older rows happen to sort ahead of it.
    effective_limit = (
        max(requested_limit, len(requested_account_ids))
        if requested_account_ids is not None
        else min(5000, requested_limit)
    )
    params.append(effective_limit)
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            WITH candidates AS (
                SELECT DISTINCT ON (t.account_id)
                       t.account_id, t.id AS task_id, t.status AS task_status,
                       r.id AS run_id, r.status AS run_status,
                       r.data->'remote_intent'->>'action' AS remote_action,
                       COALESCE(r.data->'remote_intent'->>'receipt_state',
                                r.data->'remote_intent'->>'state') AS remote_intent_state,
                       r.result_summary
                FROM {_common._table('operation_tasks')} t
                JOIN {_common._table('operation_runs')} r ON r.task_id=t.id
                WHERE {' AND '.join(clauses)}
                ORDER BY t.account_id, r.id DESC
            )
            SELECT account_id, task_id, task_status, run_id, run_status,
                   remote_action, remote_intent_state, result_summary
            FROM candidates
            ORDER BY account_id
            LIMIT %s
            """,
            tuple(params),
        )
        rows = []
        seen_accounts: set[int] = set()
        for raw in cur.fetchall():
            row = dict(raw)
            account_id = int(row["account_id"]) if row.get("account_id") else None
            if account_id is None or account_id in seen_accounts:
                continue
            seen_accounts.add(account_id)
            summary = _common._decode(row.get("result_summary"))
            summary = dict(summary) if isinstance(summary, dict) else {}
            row["result_summary"] = _common._scrub(summary)
            row["reconcile_required"] = bool(
                str(summary.get("outcome") or "").lower() == "request_unknown"
                or summary.get("reconcile_required")
                or str(row.get("run_status") or "") == "attention_required"
                or str(row.get("task_status") or "") == "attention_required"
                or (
                    str(row.get("remote_intent_state") or "") != "rejected"
                    and str(row.get("remote_intent_state") or "") != ""
                    and str(row.get("run_status") or "") not in _common._TERMINAL_STATUSES
                )
            )
            rows.append(_common._row(row) or {})
        return rows


def _requeue_stale_extract_continuations(cur, stale_seconds: int) -> list[dict]:
    """恢复已有原单或幂等提交回执的续查，保持同 Run 和原请求。"""
    cur.execute(
        f"""
        SELECT run.* FROM {_common._table('operation_runs')} run
        JOIN {_common._table('operation_tasks')} task ON task.id=run.task_id AND task.last_run_id=run.id
        WHERE task.task_type='extract_link' AND task.source_system='native_operations'
          AND run.data->>'provider_id' IN ('huanguang', 'legacy', 'anguang')
          AND run.data->'extract_poll_continuation'='true'::jsonb
          AND EXISTS (
              SELECT 1 FROM {_common._table('operation_runs')} source_run
              JOIN {_common._table('extract_link_provider_jobs')} job ON job.run_id=source_run.id
              WHERE source_run.task_id=run.task_id AND job.provider_id=run.data->>'provider_id'
                AND (source_run.id=run.id OR source_run.id=CASE
                    WHEN run.data->>'provider_job_run_id' ~ '^[0-9]{{1,19}}$'
                    THEN (run.data->>'provider_job_run_id')::numeric END)
                AND (NULLIF(BTRIM(job.job_id), '') IS NOT NULL OR (job.provider_id='huanguang' AND
                    job.private_data->'batch_receipt_pending'='true'::jsonb
                    AND NULLIF(BTRIM(job.private_data->>'batch_receipt_secret'), '') IS NOT NULL
                ) OR (job.provider_id='anguang' AND
                    job.private_data->'anguang_submission_pending'='true'::jsonb
                    AND NULLIF(BTRIM(job.private_data->>'anguang_request_encrypted'), '') IS NOT NULL
                ))
          )
          AND run.status='running' AND run.cancel_requested_at IS NULL
          AND NOT EXISTS (SELECT 1 FROM {_common._permit_table()} p
              WHERE p.run_id=run.id AND p.released_at IS NULL)
          AND (run.heartbeat_at IS NULL OR run.heartbeat_at < now() - (%s * interval '1 second'))
          AND NOT EXISTS (
              SELECT 1 FROM {_common._table('account_operation_leases')} lease
              WHERE lease.run_id=run.id AND lease.expires_at > now()
          )
        FOR UPDATE OF run SKIP LOCKED
        """,
        (stale_seconds,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    for run in rows:
        run_id = int(run['id'])
        cur.execute(
            f"""UPDATE {_common._table('operation_runs')}
                SET status='queued', execution_id=NULL, worker_pid=NULL,
                    heartbeat_at=now(), next_attempt_at=now(), progress_stage='remote_sync',
                    completed_at=NULL
                WHERE id=%s""",
            (run_id,),
        )
        cur.execute(
            f"""UPDATE {_common._table('operation_tasks')}
                SET status='queued', current_stage='remote_sync', updated_at=now(), completed_at=NULL
                WHERE id=%s AND last_run_id=%s""",
            (int(run['task_id']), run_id),
        )
        cur.execute(f"DELETE FROM {_common._table('account_operation_leases')} WHERE run_id=%s", (run_id,))
        event_uuid = uuid.uuid4().hex
        cur.execute(
            f"""INSERT INTO {_common._table('operation_events')} (
                event_uuid, task_id, run_id, source_system, source_id,
                level, stage, event_type, message, detail
            ) VALUES (%s,%s,%s,%s,%s,'INFO','remote_sync','run.requeued',%s,%s::jsonb)""",
            (event_uuid, int(run['task_id']), run_id, str(run.get('source_system') or 'native_operations'),
             event_uuid, '续查进程已中断，原单已重新排队同步', _common._json({'reason': 'worker_restart'})),
        )
    return rows


def recover_interrupted_runtime_runs(*, stale_after_seconds: int = 15 * 60) -> int:
    """收口真正失去 worker 的 attempt；有效租约和新鲜心跳均保留。

    WebUI 可能只是一个进程，原生 worker 也可能来自另一个进程。启动时
    不能把所有 ``running`` 行当成自己的；只有心跳已经过期且不存在有效
    account lease 的行才属于可恢复的孤儿执行。
    """
    _schema.init_operation_schema()
    from core.storage.operations import permits

    settlement_recovery = recover_participating_executions(stale_after_seconds=stale_after_seconds)
    stale_seconds = max(1, min(7 * 24 * 60 * 60, int(stale_after_seconds or 0)))
    ready_dependencies: list[dict] = []
    with _common._connect() as conn, conn.cursor() as cur:
        permits.admission_lock(conn)
        requeued_continuations = _requeue_stale_extract_continuations(cur, stale_seconds)
        cur.execute(f"""SELECT r.id,(r.data->>'bulk_target_round_id')::bigint AS target_id
            FROM {_common._table('operation_runs')} r WHERE r.data->>'bulk_target_round_id' ~ '^[0-9]+$'
              AND r.status IN ('running','cancelling','settling')
              AND (r.heartbeat_at IS NULL OR r.heartbeat_at < now() - (%s * interval '1 second'))
              AND NOT EXISTS (SELECT 1 FROM {_common._permit_table()} p WHERE p.run_id=r.id AND p.released_at IS NULL)
            ORDER BY target_id,r.id""", (stale_seconds,))
        managed_candidates = list(cur.fetchall())
        managed_targets = {}
        for candidate in managed_candidates:
            managed = bulk_execution.lock_run(conn, int(candidate["id"]))
            if managed:
                managed_targets[int(managed["id"])] = managed
        cur.execute(
            f"""
            UPDATE {_common._table('operation_runs')} AS run
            SET status=CASE
                    WHEN run.data->'remote_intent'->>'kind'='remote_write'
                     AND COALESCE(
                         run.data->'remote_intent'->>'receipt_state',
                         run.data->'remote_intent'->>'state', 'started'
                     )
                         NOT IN ('rejected', 'not_submitted')
                    THEN 'attention_required'
                    ELSE 'interrupted'
                END,
                completed_at=now(), heartbeat_at=now(),
                progress_stage='complete',
                error_message=CASE
                    WHEN run.data->'remote_intent'->>'kind'='remote_write'
                     AND COALESCE(
                         run.data->'remote_intent'->>'receipt_state',
                         run.data->'remote_intent'->>'state', 'started'
                     )
                         NOT IN ('rejected', 'not_submitted')
                    THEN '执行进程已中断，当前步骤未完成回执核验'
                    ELSE '执行进程已重启，原 attempt 中断'
                END,
                result_summary=CASE
                    WHEN run.data->'remote_intent'->>'kind'='remote_write'
                     AND COALESCE(
                         run.data->'remote_intent'->>'receipt_state',
                         run.data->'remote_intent'->>'state', 'started'
                     )
                         NOT IN ('rejected', 'not_submitted')
                    THEN COALESCE(run.result_summary, '{{}}'::jsonb) || jsonb_build_object(
                        'outcome', 'request_unknown',
                        'reconcile_required', true,
                        'cause_code', COALESCE(run.result_summary->>'cause_code', 'worker_interrupted'),
                        'execution_id', COALESCE(run.execution_id, ''),
                        'lease_owner', COALESCE(run.execution_id, ''),
                        'remote_action', run.data->'remote_intent'->>'action',
                        'remote_intent_state', COALESCE(
                            run.data->'remote_intent'->>'receipt_state',
                            run.data->'remote_intent'->>'state', 'started'
                        )
                    )
                    ELSE COALESCE(run.result_summary, '{{}}'::jsonb) || jsonb_build_object(
                        'outcome', 'interrupted',
                        'cause_code', COALESCE(run.result_summary->>'cause_code', 'worker_interrupted'),
                        'recovery_reason', 'worker_restart'
                    )
                END
            FROM {_common._table('operation_tasks')} task
            WHERE run.task_id=task.id
              AND run.source_system NOT IN ('registration_jobs', 'account_action_tasks')
              AND run.status IN ('running', 'cancelling', 'settling')
              AND NOT EXISTS (SELECT 1 FROM {_common._permit_table()} p
                  WHERE p.run_id=run.id AND p.released_at IS NULL)
              AND (run.heartbeat_at IS NULL OR run.heartbeat_at < now() - (%s * interval '1 second'))
              AND NOT EXISTS (
                  SELECT 1 FROM {_common._table('account_operation_leases')} lease
                  WHERE lease.run_id=run.id AND lease.expires_at > now()
              )
            RETURNING run.id, run.task_id, run.account_id, run.batch_id,
                      run.status, run.data, run.execution_id, task.source_system,
                      run.result_summary, run.error_message, task.task_type
            """,
            (stale_seconds,),
        )
        recovered = list(cur.fetchall())
        run_ids = [int(row["id"]) for row in recovered]
        task_ids = [int(row["task_id"]) for row in recovered]
        current_task_ids: list[int] = []
        source_by_task: dict[int, str] = {}
        status_by_task: dict[int, str] = {
            int(row["task_id"]): str(row.get("status") or "interrupted")
            for row in recovered
        }
        if task_ids:
            cur.execute(
                f"SELECT id, source_system FROM {_common._table('operation_tasks')} WHERE id = ANY(%s)",
                (task_ids,),
            )
            source_by_task = {
                int(row["id"]): str(row.get("source_system") or "native_operations")
                for row in cur.fetchall()
            }
            for row in recovered:
                recovered_status = status_by_task[int(row["task_id"])]
                category, code, error_message = _common._error_fields(
                    row.get("error_message"), stage="complete", task_type=str(row.get("task_type") or ""),
                    result_summary=_common._decode(row.get("result_summary")), task_status=recovered_status,
                )
                cur.execute(
                    f"UPDATE {_common._table('operation_runs')} SET error_category=%s, error_code=%s WHERE id=%s",
                    (category, code, int(row["id"])),
                )
                cur.execute(
                    f"""
                    UPDATE {_common._table('operation_tasks')}
                    SET status=%s,
                        current_stage=%s,
                        completed_at=now(),
                        updated_at=now(),
                        error_message=%s, error_category=%s, error_code=%s,
                        target_status=CASE WHEN %s='attention_required'
                            THEN 'attention_required' ELSE target_status END,
                        next_actions=%s::jsonb
                    WHERE id=%s AND last_run_id=%s
                    """,
                    (
                        recovered_status,
                        "complete" if recovered_status == "attention_required" else "interrupted",
                        error_message, category, code,
                        recovered_status,
                        _common._json([{"action": "retry", "label": "重新执行"}]),
                        int(row["task_id"]), int(row["id"]),
                    ),
                )
                if cur.rowcount:
                    current_task_ids.append(int(row["task_id"]))
            cur.execute(
                f"""
                UPDATE {_common._table('operation_resources')}
                SET state='reconciliation_required',
                    detail=detail || '{{"reason":"worker_restart"}}'::jsonb
                WHERE run_id = ANY(%s) AND state='acquired'
                """,
                (run_ids,),
            )
            for row in recovered:
                recovered_status = status_by_task[int(row["task_id"])]
                event_uuid = uuid.uuid4().hex
                cur.execute(
                    f"""
                    INSERT INTO {_common._table('operation_events')} (
                        event_uuid, task_id, run_id, source_system, source_id,
                        level, stage, event_type, message, detail
                    ) VALUES (%s, %s, %s, %s, %s,
                              'WARNING', %s, %s, %s, %s::jsonb)
                    """,
                    (
                        event_uuid, int(row["task_id"]), int(row["id"]),
                        source_by_task.get(int(row["task_id"]), "native_operations"),
                        event_uuid,
                        "complete" if recovered_status == "attention_required" else "interrupted",
                        "run.attention_required" if recovered_status == "attention_required" else "run.interrupted",
                        str(row.get("error_message") or "执行进程已中断，当前步骤未完成"),
                        _common._json({
                            "reason": "worker_restart",
                            "outcome": "request_unknown"
                            if recovered_status == "attention_required" else "interrupted",
                            "reconcile_required": recovered_status == "attention_required",
                        }),
                    ),
                )
            if current_task_ids:
                cur.execute(
                    f"""
                    SELECT DISTINCT parent_task_id
                    FROM {_common._table('operation_tasks')}
                    WHERE id = ANY(%s) AND parent_task_id IS NOT NULL
                    """,
                    (current_task_ids,),
                )
                for parent in cur.fetchall():
                    _runtime._reconcile_parent_task_cur(cur, int(parent["parent_task_id"]))
                from core.storage.operations import registration_completion

                for row in recovered:
                    if str(row.get("task_type") or "") == "password_setup" and int(row["task_id"]) in current_task_ids:
                        registration_completion.reconcile_for_child(cur, int(row["task_id"]))
                # A dependency is keyed to the logical child task, but an old
                # attempt must not wake it after a newer retry has become the
                # task's last_run_id. Only tasks whose current attempt was
                # actually interrupted are eligible here.
                for recovered_status in ("interrupted", "attention_required"):
                    for source_system in sorted({source_by_task.get(task_id, "native_operations") for task_id in current_task_ids}):
                        source_task_ids = [
                            str(task_id) for task_id in current_task_ids
                            if status_by_task.get(task_id) == recovered_status
                            and source_by_task.get(task_id, "native_operations") == source_system
                        ]
                        if not source_task_ids:
                            continue
                        cur.execute(
                            f"""
                            UPDATE {_common._table('operation_task_dependencies')} dependency
                            SET status='ready', child_status=%s,
                                child_result=%s::jsonb, ready_at=now(),
                                next_attempt_at=NULL, last_error=NULL, updated_at=now()
                            WHERE dependency.status='waiting'
                              AND dependency.child_source_system=%s
                              AND dependency.child_source_id = ANY(%s)
                            RETURNING dependency.*
                            """,
                            (
                                recovered_status,
                                _common._json({
                                    "status": recovered_status,
                                    "reason": "worker_restart",
                                    "outcome": "request_unknown"
                                    if recovered_status == "attention_required" else "interrupted",
                                    "reconcile_required": recovered_status == "attention_required",
                                }),
                                source_system, source_task_ids,
                            ),
                        )
                        ready_dependencies.extend(
                            _common._row(dict(dependency)) or {} for dependency in cur.fetchall()
                        )
        if run_ids:
            cur.execute(
                f"DELETE FROM {_common._table('account_operation_leases')} WHERE run_id = ANY(%s)",
                (run_ids,),
            )
        # Only the Codex adapter owns these legacy account columns.  A stale
        # live/refresh/setup run must not clear Codex or other business state
        # merely because the generic durable recovery pass saw its account id.
        codex_status_by_account: dict[int, str] = {}
        for row in recovered:
            if row.get("account_id") and str(row.get("task_type") or "") == "codex_retry":
                account_number = int(row["account_id"])
                codex_status_by_account[account_number] = (
                    "attention_required"
                    if str(row.get("status") or "") == "attention_required"
                    else "interrupted"
                )
        for account_number, last_status in codex_status_by_account.items():
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified(record_store.ACCOUNTS.name)}
                SET codex_execution_status='empty', codex_active_run_id=NULL,
                    codex_last_run_status=%s,
                    codex_status=CASE
                        WHEN codex_status='success' THEN codex_status
                        ELSE %s
                    END,
                    updated_at=%s
                WHERE id=%s
                """,
                (
                    last_status, last_status,
                    datetime.now().isoformat(timespec="seconds"), account_number,
                ),
            )
        _projection._refresh_batches(cur, [row.get("batch_id") for row in recovered + requeued_continuations])
        for managed in managed_targets.values():
            bulk_execution.changed(conn, managed, event_kind="recovered")
    if ready_dependencies:
        from core.operations import task_gateway

        for dependency in ready_dependencies:
            task_gateway.notify_dependency_ready(dependency)
    return len(task_ids) + len(requeued_continuations) + settlement_recovery["recovered"]
