"""提链 Provider 的远端任务状态与私有恢复凭据存储。"""
from __future__ import annotations

from contextlib import nullcontext

import json
import logging
import re
import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from core import record_store
from core.extract_link_providers.contracts import safe_links, safe_payment_artifact
from core.extract_link_providers.payment_confirmation import payment_scan_completed
from core.storage import operation as operation_store


logger = logging.getLogger(__name__)


_SUMMARY_FIELDS = frozenset({
    "current_step", "percent", "outcome", "preflight_status", "plus_status",
    "aftercare_status", "message", "remote_status", "remote_terminal_failure",
    "failure_message",
    "completed_steps", "total_steps", "run_attempt", "step_attempt", "failure_code",
    "failure_type", "last_event", "plus_verification_status", "automatic_payment_status",
    "automatic_payment_terminal", "automatic_payment_requires_reconcile", "remote_polling",
    "payment_check_status", "platform_plus_status", "entitlement_active", "entitlement_inferred", "xxsyun_status",
    "payment_confirmation_source", "payment_confirmed_plan_checked_at", "platform_plus_checked_at",
    "queue_position", "max_attempts", "cdk_state",
    "submission_receipt_pending", "auto_relink_status", "auto_relink_attempt", "remote_chain_length", "remote_chain_error",
    "extraction_ever_succeeded", "local_plan_check_pending",
    "local_reconcile_halted", "local_reconcile_reason", "local_reconcile_halted_at",
})
_REMOTE_STATUSES = frozenset({
    "QUEUED", "RUNNING", "AWAITING_BLIK_CODE", "SUCCEEDED", "FAILED",
    "CANCELED", "CANCELLED", "DONE", "ERROR",
})


def _json_object(value: Any, *, field_name: str) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    raise ValueError(f"{field_name} 必须是对象")


def _public_state(value: Mapping[str, Any]) -> dict:
    if not isinstance(value, Mapping):
        raise ValueError("public_state 必须是对象")
    result: dict[str, Any] = {}
    for field_name in (
        "extraction_state", "payment_state", "preflight_status", "plus_status",
        "aftercare_status", "message",
    ):
        field_value = value.get(field_name)
        if isinstance(field_value, str):
            result[field_name] = field_value[:300]

    for field_name in ("links", "payment_links"):
        links = value.get(field_name)
        if isinstance(links, (list, tuple)):
            safe = list(safe_links(*links[:20]))
            if safe:
                result[field_name] = safe

    artifact = safe_payment_artifact(value.get("payment_artifact"))
    if artifact:
        result["payment_artifact"] = artifact

    summary = value.get("summary")
    if isinstance(summary, Mapping):
        safe_summary: dict[str, Any] = {}
        for key in _SUMMARY_FIELDS:
            item = summary.get(key)
            if key == "payment_confirmation_source" and (
                not isinstance(item, str) or item not in {"local_plan_check", "platform_order_check"}
            ):
                continue
            if key == "remote_status":
                normalized = item.strip().upper() if isinstance(item, str) else ""
                if normalized in _REMOTE_STATUSES:
                    safe_summary[key] = normalized
                continue
            if key in {"remote_terminal_failure", "local_reconcile_halted"}:
                if type(item) is bool:
                    safe_summary[key] = item
                continue
            if key == "local_reconcile_reason":
                if isinstance(item, str) and item in {"remote_not_found", "query_failures", "timeout", "no_progress"}:
                    safe_summary[key] = item
                continue
            if key in {"local_reconcile_halted_at", "platform_plus_checked_at"}:
                if isinstance(item, str) and len(item) <= 64:
                    try:
                        parsed = datetime.fromisoformat(item.replace("Z", "+00:00"))
                        if parsed.tzinfo is not None:
                            safe_summary[key] = item
                    except ValueError:
                        pass
                continue
            if isinstance(item, str):
                safe_summary[key] = item[:160]
            elif isinstance(item, (int, float, bool)) or item is None:
                safe_summary[key] = item
        if safe_summary:
            result["summary"] = safe_summary
    return result


def _private_data(value: Mapping[str, Any]) -> dict:
    if not isinstance(value, Mapping):
        raise ValueError("private_data 必须是对象")
    return dict(value)


def _dump(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def save_provider_job(
    run_id: int,
    provider_id: str,
    job_id: str | None,
    public_state: Mapping[str, Any],
    private_data: Mapping[str, Any],
    *,
    execution_fence: dict | None = None,
) -> dict:
    """保存远端任务；公开摘要与只供 worker 恢复的凭据分列存放。"""
    operation_store.init()
    run_value = int(run_id)
    provider_value = str(provider_id or "").strip()
    if run_value <= 0 or not provider_value:
        raise ValueError("run_id 和 provider_id 必须有效")
    public_value = _public_state(public_state)
    private_value = _private_data(private_data)
    extraction_state = public_value.get("extraction_state", "unknown")
    payment_state = public_value.get("payment_state", "not_started")
    job_value = str(job_id).strip() if job_id not in (None, "") else None
    material_changed = """COALESCE(NULLIF(EXCLUDED.private_data->>'material_job_id', ''),
            NULLIF(EXCLUDED.private_data->>'active_job_id', '')) IS NOT NULL
        AND COALESCE(NULLIF(EXCLUDED.private_data->>'material_job_id', ''),
            NULLIF(EXCLUDED.private_data->>'active_job_id', '')) IS DISTINCT FROM
            COALESCE(NULLIF(stored.private_data->>'material_job_id', ''),
                NULLIF(stored.private_data->>'active_job_id', ''), stored.job_id)"""
    same_payment_order = """stored.provider_id='legacy' AND EXCLUDED.provider_id='legacy'
        AND stored.job_id IS NOT DISTINCT FROM COALESCE(EXCLUDED.job_id, stored.job_id)
        AND NOT EXISTS (
            SELECT 1 FROM (VALUES ('legacy_payment_order_id'), ('legacy_payment_order_no')) identity(key)
            WHERE NULLIF(EXCLUDED.private_data->>identity.key, '') IS NOT NULL
              AND NULLIF(stored.private_data->>identity.key, '') IS NOT NULL
              AND EXCLUDED.private_data->>identity.key IS DISTINCT FROM stored.private_data->>identity.key
        )"""
    with operation_store._connect() as conn, conn.cursor() as cur:
        if execution_fence is not None:
            from core.operations.task_gateway import OperationLeaseLost
            try:
                if int(execution_fence.get("run_id") or 0) != run_value:
                    raise PermissionError("执行围栏与远端任务不匹配")
                operation_store.fence_execution(cur, **execution_fence)
            except (PermissionError, LookupError) as exc:
                raise OperationLeaseLost("当前执行或租约失效，平台状态未写入") from exc
        cur.execute(
            f"""
            INSERT INTO {operation_store._table('extract_link_provider_jobs')} AS stored (
                run_id, provider_id, job_id, extraction_state, payment_state,
                public_state, private_data
            ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
            ON CONFLICT(run_id) DO UPDATE SET
                provider_id=EXCLUDED.provider_id,
                job_id=COALESCE(EXCLUDED.job_id, stored.job_id),
                extraction_state=EXCLUDED.extraction_state,
                payment_state=EXCLUDED.payment_state,
                public_state=EXCLUDED.public_state || jsonb_build_object(
                    'links', CASE WHEN {material_changed} THEN COALESCE(EXCLUDED.public_state->'links', '[]'::jsonb)
                        ELSE COALESCE(EXCLUDED.public_state->'links', stored.public_state->'links', '[]'::jsonb) END,
                    'payment_links', CASE WHEN {material_changed} THEN COALESCE(EXCLUDED.public_state->'payment_links', '[]'::jsonb)
                        ELSE COALESCE(EXCLUDED.public_state->'payment_links', stored.public_state->'payment_links', '[]'::jsonb) END,
                    'payment_artifact',
                    CASE WHEN {material_changed} THEN COALESCE(EXCLUDED.public_state->'payment_artifact', '{{}}'::jsonb)
                        ELSE COALESCE(stored.public_state->'payment_artifact', '{{}}'::jsonb)
                        || COALESCE(EXCLUDED.public_state->'payment_artifact', '{{}}'::jsonb) END
                ),
                private_data=CASE WHEN stored.provider_id='legacy' THEN
                    (CASE WHEN {same_payment_order} THEN stored.private_data
                        ELSE stored.private_data - 'legacy_payment_cdk' END) || EXCLUDED.private_data
                    || CASE WHEN {same_payment_order}
                            AND NULLIF(BTRIM(stored.private_data->>'legacy_payment_cdk'), '') IS NOT NULL
                        THEN jsonb_build_object('legacy_payment_cdk', stored.private_data->'legacy_payment_cdk')
                        ELSE '{{}}'::jsonb END
                    ELSE stored.private_data || EXCLUDED.private_data END,
                updated_at=now()
            """,
            (
                run_value,
                provider_value,
                job_value,
                extraction_state,
                payment_state,
                _dump(public_value),
                _dump(private_value),
            ),
        )
    saved = get_provider_job_private(run_value)
    if saved is None:
        raise RuntimeError("提链 Provider 任务保存后不可读取")
    return saved


def restore_legacy_payment_query_credential(
    task_id: int, *, expected_run_id: int, provider_job_run_id: int, expected_job_id: str,
    payment_cdk: str, expected_order_id: str = "", expected_order_no: str = "",
) -> dict:
    """仅补齐已由服务验证的原单查询凭据；不创建订单，也不改变任务状态。"""
    identifiers = (task_id, expected_run_id, provider_job_run_id)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in identifiers):
        raise ValueError("原单任务标识无效")
    if not isinstance(payment_cdk, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,255}", payment_cdk) is None:
        raise ValueError("支付查询凭据格式无效")
    if (not isinstance(expected_job_id, str) or not expected_job_id
            or not all(isinstance(value, str) and len(value) <= 256 for value in (expected_order_id, expected_order_no))
            or not (expected_order_id or expected_order_no)):
        raise ValueError("原单身份信息不足")
    operation_store.init()
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {operation_store._table('operation_runs')} WHERE id=%s FOR UPDATE", (expected_run_id,))
        current = cur.fetchone()
        if not current or current["task_id"] != task_id or current["source_system"] != "native_operations":
            raise LookupError("当前任务执行记录已变化")
        cur.execute(f"SELECT * FROM {operation_store._table('operation_tasks')} WHERE id=%s FOR UPDATE", (task_id,))
        task = cur.fetchone()
        if (not task or task["last_run_id"] != expected_run_id or task["task_type"] != "extract_link"
                or task["source_system"] != "native_operations"):
            raise ValueError("当前原单任务已变化")
        task_data = _json_object(task["data"], field_name="任务数据")
        current_data = _json_object(current["data"], field_name="执行数据")
        if (current_data.get("provider_id", task_data.get("provider_id")) != "legacy"
                or current_data.get("mode", task_data.get("mode")) not in {"auto_payment", "manual_payment"}):
            raise ValueError("当前任务不支持恢复支付查询凭据")
        chain = [expected_run_id]
        row = current
        while chain[-1] != provider_job_run_id and len(chain) < 20:
            data = _json_object(row["data"], field_name="执行数据")
            parent = data.get("provider_job_run_id")
            if (data.get("workbench_action") != "sync_status" or isinstance(parent, bool)
                    or not isinstance(parent, int) or parent < 1 or parent in chain):
                raise ValueError("当前执行与待恢复原单不一致")
            cur.execute(f"SELECT * FROM {operation_store._table('operation_runs')} WHERE id=%s FOR UPDATE", (parent,))
            row = cur.fetchone()
            if not row or row["task_id"] != task_id or row["source_system"] != "native_operations":
                raise ValueError("当前执行与待恢复原单不一致")
            chain.append(parent)
        if chain[-1] != provider_job_run_id:
            raise ValueError("原单执行关联过深")
        cur.execute(f"SELECT * FROM {operation_store._table('extract_link_provider_jobs')} WHERE run_id=ANY(%s) ORDER BY run_id FOR UPDATE", (chain,))
        jobs = list(cur.fetchall())
        source = next((job for job in jobs if job["run_id"] == provider_job_run_id), None)
        if not source or source["provider_id"] != "legacy" or source["job_id"] != expected_job_id:
            raise ValueError("待恢复的远端原单已变化")
        for job in jobs:
            if job["provider_id"] != "legacy" or job["job_id"] != expected_job_id:
                raise ValueError("当前执行包含其他远端原单")
            private = _json_object(job["private_data"], field_name="平台恢复数据")
            for key, expected in (("legacy_payment_order_id", expected_order_id), ("legacy_payment_order_no", expected_order_no)):
                if expected and private.get(key) != expected:
                    raise ValueError("待恢复的支付订单已变化")
            existing = private.get("legacy_payment_cdk")
            if existing not in (None, "", payment_cdk):
                raise ValueError("原单已保存其他支付查询凭据")
        # 查询凭据补齐不代表远端状态发生变化，保留原有观测时间供到账归因使用。
        cur.execute(f"UPDATE {operation_store._table('extract_link_provider_jobs')} "
                    "SET private_data=private_data || %s::jsonb WHERE run_id=ANY(%s)",
                    (_dump({"legacy_payment_cdk": payment_cdk}), [job["run_id"] for job in jobs]))
    return {"task_id": task_id, "run_id": expected_run_id, "provider_job_run_id": provider_job_run_id, "updated": True}


def get_provider_job_private(run_id: int) -> dict | None:
    """仅供内部 worker 恢复远端 job，不用于 API 或 WebUI 投影。"""
    operation_store.init()
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT run_id, provider_id, job_id, extraction_state, payment_state,
                   public_state, private_data, created_at, updated_at
            FROM {operation_store._table('extract_link_provider_jobs')}
            WHERE run_id=%s
            """,
            (int(run_id),),
        )
        row = cur.fetchone()
    if row is None:
        return None
    result = dict(row)
    result["public_state"] = _json_object(result["public_state"], field_name="public_state")
    result["private_data"] = _json_object(result["private_data"], field_name="private_data")
    return result


def get_provider_job_public(run_id: int) -> dict | None:
    """读取工作台可展示状态，不返回 job_secret 等恢复凭据。"""
    operation_store.init()
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT run_id, provider_id, job_id, extraction_state, payment_state,
                   public_state, created_at, updated_at
            FROM {operation_store._table('extract_link_provider_jobs')}
            WHERE run_id=%s
            """,
            (int(run_id),),
        )
        row = cur.fetchone()
    if row is None:
        return None
    result = dict(row)
    result["public_state"] = _json_object(result["public_state"], field_name="public_state")
    return result


def has_unresolved_auto_payment(account_id: int, *, conn=None) -> bool:
    """检查真实付款状态及活动提链意向，终态未付款的历史请求允许重跑。"""
    operation_store.init()
    with (operation_store._connect() if conn is None else nullcontext(conn)) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM {operation_store._table('operation_tasks')} task
                JOIN {operation_store._table('operation_runs')} run ON run.task_id=task.id
                LEFT JOIN {operation_store._table('extract_link_provider_jobs')} job ON job.run_id=run.id
                WHERE task.task_type='extract_link'
                  AND task.account_id=%s
                  AND COALESCE(run.data->>'mode', task.data->>'mode')='auto_payment'
                  AND (
                      job.payment_state IN ('pending', 'unknown', 'succeeded')
                      OR run.result_summary->>'payment_status' IN ('pending', 'unknown', 'succeeded')
                      OR (
                          run.data->'remote_intent'->>'action'='extract_link_create'
                          AND run.status IN ('queued','running','waiting','cancelling','settling','stopping')
                          AND COALESCE(
                              run.data->'remote_intent'->>'receipt_state',
                              run.data->'remote_intent'->>'state', 'started'
                          ) NOT IN ('rejected', 'not_submitted')
                          AND COALESCE(job.payment_state, run.result_summary->>'payment_status', 'not_started')
                              NOT IN ('failed', 'succeeded')
                      )
                  )
            ) AS unresolved
            """,
            (int(account_id),),
        )
        row = cur.fetchone() or {}
    return bool(row.get("unresolved"))


def list_recoverable_workbench_jobs() -> list[dict]:
    """读取重启后需要继续同步的原生提链任务，不包含远端私有凭据。"""
    operation_store.init()
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT task.id AS task_id,
                   run.id AS run_id,
                   job.run_id AS provider_job_run_id,
                   COALESCE(job.provider_id, run.data->>'provider_id', task.data->>'provider_id', 'legacy') AS provider_id,
                   COALESCE(run.data->>'mode', task.data->>'mode', 'extract_only') AS mode
            FROM {operation_store._table('operation_tasks')} task
            JOIN {operation_store._table('operation_runs')} run ON run.id=task.last_run_id
            LEFT JOIN {operation_store._table('operation_batches')} batch ON batch.id=task.batch_id
            JOIN LATERAL (
                SELECT original.* FROM {operation_store._table('extract_link_provider_jobs')} original
                JOIN {operation_store._table('operation_runs')} source_run
                  ON source_run.id=original.run_id AND source_run.task_id=task.id
                WHERE original.run_id=run.id OR (
                    run.data->>'workbench_action'='sync_status'
                    AND original.run_id=CASE WHEN run.data->>'provider_job_run_id' ~ '^[0-9]{{1,18}}$'
                        THEN (run.data->>'provider_job_run_id')::bigint END
                )
                ORDER BY (original.run_id=run.id) DESC LIMIT 1
            ) job ON true
            WHERE task.task_type='extract_link'
              AND task.source_system='native_operations'
              AND run.status IN ('attention_required', 'interrupted')
              AND run.cancel_requested_at IS NULL
              AND (batch.id IS NULL OR batch.status NOT IN ('cancelled', 'stopped', 'paused'))
              AND (job.provider_id<>'legacy' OR run.data->>'extract_poll_continuation'='true'
                   OR jsonb_typeof(job.private_data->'local_reconcile')='object'
                   OR job.public_state->'summary'->'local_plan_check_pending'='true'::jsonb)
              AND (job.provider_id<>'legacy' OR (
                  job.extraction_state <> 'failed'
                  AND COALESCE(job.public_state->'summary'->>'outcome', '') <> 'REJECTED'
                  AND job.public_state->'summary'->'remote_terminal_failure' IS DISTINCT FROM 'true'::jsonb
                  AND (
                      (job.payment_state NOT IN ('failed', 'succeeded')
                       AND (job.extraction_state IN ('pending', 'queued', 'running', 'unknown')
                            OR (COALESCE(run.data->>'mode', task.data->>'mode', 'extract_only')='auto_payment'
                                AND job.payment_state IN ('pending', 'not_started', 'unknown')
                                AND job.public_state->'summary'->'automatic_payment_terminal' IS DISTINCT FROM 'true'::jsonb)))
                      OR (job.payment_state='succeeded'
                          AND COALESCE(run.data->>'mode', task.data->>'mode', 'extract_only') IN ('auto_payment', 'manual_payment')
                          AND job.public_state->>'plus_status' IS DISTINCT FROM 'confirmed'
                          AND COALESCE(job.public_state->'summary'->>'remote_chain_error', '')=''
                          AND UPPER(COALESCE(job.public_state->'summary'->>'automatic_payment_status', ''))
                              NOT IN ('FAILED', 'FAILED_REFUNDED', 'CANCELLED', 'CANCELED', 'EXPIRED', 'NEED_REUPLOAD')
                          AND (run.status='interrupted' OR run.result_summary->>'cause_code'='worker_interrupted'
                               OR job.public_state->'summary'->'local_plan_check_pending'='true'::jsonb))
                  )
              ))
              AND (job.provider_id NOT IN ('huanguang', 'legacy')
                   OR job.public_state->'summary'->'local_reconcile_halted' IS DISTINCT FROM 'true'::jsonb)
              AND (
                  (job.provider_id<>'huanguang' AND NULLIF(BTRIM(job.job_id), '') IS NOT NULL)
                  OR (job.provider_id='huanguang' AND (
                      (job.private_data->>'batch_receipt_pending'='true'
                       AND NULLIF(job.private_data->>'batch_receipt_secret', '') IS NOT NULL)
                      OR (NULLIF(BTRIM(job.job_id), '') IS NOT NULL
                          AND COALESCE(job.public_state->'summary'->>'remote_chain_error', '')=''
                          AND (job.public_state->'summary'->>'remote_polling'='true'
                               OR (job.public_state->'summary'->>'local_plan_check_pending'='true'
                                   AND job.extraction_state='succeeded'
                                   AND job.public_state->>'plus_status'='pending'
                                   AND job.public_state->'summary'->>'remote_status'='DONE'
                                   AND job.public_state->'summary'->>'automatic_payment_terminal'='true')
                               OR (job.extraction_state IN ('pending', 'queued', 'running', 'unknown')
                                   AND COALESCE(job.public_state->'summary'->>'automatic_payment_requires_reconcile', '')<>'true'
                                   AND COALESCE(job.public_state->'summary'->>'remote_terminal_failure', '')<>'true')))
                  ))
              )
            ORDER BY job.updated_at, run.id
            """
        )
        return [operation_store._row(dict(row)) or {} for row in cur.fetchall()]


def _workbench_where(*, provider_id=None, mode=None, query="", batch_id=None, batch_ids=None):
    clauses = [
        "t.task_type='extract_link'",
        "lower(COALESCE(t.data->>'deleted_by_user', '')) <> 'true'",
    ]
    params: list[Any] = []
    if batch_id is not None:
        clauses.append("t.batch_id=%s")
        params.append(int(batch_id))
    if batch_ids is not None:
        clauses.append("t.batch_id = ANY(%s)")
        params.append([int(value) for value in batch_ids])
    if provider_id:
        clauses.append("COALESCE(t.data->>'provider_id', 'legacy')=%s")
        params.append(str(provider_id))
    if mode:
        clauses.append("COALESCE(t.data->>'mode', 'extract_only')=%s")
        params.append(str(mode))
    if query:
        clauses.append("(t.email_snapshot ILIKE %s OR CAST(t.id AS TEXT) ILIKE %s)")
        pattern = f"%{str(query)[:200]}%"
        params.extend((pattern, pattern))
    return clauses, params


def _workbench_columns() -> str:
    return f"""t.id AS task_id, t.account_id, t.batch_id, t.email_snapshot AS email, t.data AS task_data,
                   t.status AS task_status, t.target_status, t.current_stage,
                   t.created_at AS task_created_at, t.updated_at AS task_updated_at,
                   t.last_run_id,
                   (SELECT COUNT(*) FROM {operation_store._table('operation_runs')} history
                    WHERE history.task_id=t.id) AS run_count,
                   r.id AS run_id, r.status AS run_status, r.progress_stage,
                   r.created_at AS run_created_at, r.completed_at AS run_completed_at,
                   r.result_summary, r.error_message,
                   job.provider_id AS job_provider_id,
                   job.job_id AS remote_job_id,
                   job.extraction_state, job.payment_state, job.public_state,
                   job.updated_at AS job_updated_at"""


def _workbench_joins() -> str:
    return f"""FROM {operation_store._table('operation_tasks')} t
        LEFT JOIN {operation_store._table('operation_runs')} r ON r.id=t.last_run_id
        LEFT JOIN {operation_store._table('extract_link_provider_jobs')} job ON job.run_id=r.id"""


def _workbench_rows(rows) -> list[dict]:
    rows = [operation_store._row(dict(row)) or {} for row in rows]
    for row in rows:
        row["task_data"] = _json_object(row.get("task_data") or {}, field_name="task_data")
        row["result_summary"] = _json_object(row.get("result_summary") or {}, field_name="result_summary")
        row["public_state"] = _json_object(row.get("public_state") or {}, field_name="public_state")
    return rows


def list_workbench_rows(
    *, provider_id: str | None = None, mode: str | None = None, query: str = "",
    batch_id: int | None = None, batch_ids: list[int] | None = None,
) -> list[dict]:
    """批量读取公开状态；交互列表应使用数据库分页入口。"""
    operation_store.init()
    clauses, params = _workbench_where(provider_id=provider_id, mode=mode, query=query, batch_id=batch_id, batch_ids=batch_ids)
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT {_workbench_columns()} {_workbench_joins()}
                WHERE {' AND '.join(clauses)}
                ORDER BY COALESCE(r.created_at, t.created_at) DESC, t.id DESC""",
            tuple(params),
        )
        return _workbench_rows(cur.fetchall())


_WORKBENCH_STATUS_SQL = {
    "processing": """NOT local_reconcile_halted AND (task_status IN ('queued','running','waiting','cancelling','settling','stopping')
        OR (mode='auto_payment' AND payment_status='pending_payment'
            AND task_status NOT IN ('attention_required','request_unknown','failed','cancelled','stopped','interrupted'))
        OR (payment_status='paid' AND plus_status IN ('unknown','pending','queued')))""",
    "running": "NOT local_reconcile_halted AND task_status IN ('running','cancelling','settling','stopping')",
    "extraction_succeeded": "extraction_status='success'",
    "payment_succeeded": "payment_status='paid'",
    "plus_confirmed": "plus_status='confirmed'",
    "needs_attention": """local_reconcile_halted OR task_status IN ('failed','request_unknown','cancelled','attention_required','partial_success','stopped','interrupted')
        OR extraction_status IN ('unknown','failed') OR payment_status IN ('request_unknown','failed')
        OR plus_status IN ('failed','not_confirmed') OR (payment_status='paid' AND plus_status='unknown')""",
}


_WORKBENCH_TIMESTAMP_PATTERN = (
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[T ](0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"([.][0-9]{1,6})?(Z|[+-](0[0-9]|1[0-4]):[0-5][0-9])?$"
)


def _workbench_timestamp(value: Any) -> datetime | None:
    """兼容本地无时区快照与显式时区，坏时间不能影响任务列表。"""
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value or "").strip(" ")
            if not re.fullmatch(_WORKBENCH_TIMESTAMP_PATTERN, text):
                return None
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return operation_store._legacy_timestamp(parsed)
    except (TypeError, ValueError, OverflowError):
        return None


def independent_plus_is_confirmed(account: dict | None, *, task_created_at: Any) -> bool:
    """本任务创建后的独立套餐事实只确认到账，不改写平台支付结果。"""
    if not account or str(account.get("plan_check_status") or "").lower() != "success":
        return False
    plan = str(account.get("current_plan_type") or account.get("plan_type") or "").strip(" ").lower()
    if plan not in {"plus", "pro"}:
        return False
    checked_at = _workbench_timestamp(
        str(account.get("plan_checked_at") or "").strip(" ") or account.get("plan_last_success_at")
    )
    created_at = _workbench_timestamp(task_created_at)
    return checked_at is not None and created_at is not None and checked_at > created_at


def _reconcile_completed_payment(run_id: int, *, expected_job_id: str) -> bool:
    """在同一事务内核实最新终态与套餐事实，再补齐本地任务记录。"""
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {operation_store._table('operation_runs')} WHERE id=%s FOR UPDATE", (run_id,))
        run = cur.fetchone()
        if not run or run["source_system"] != "native_operations" or run["status"] not in {"attention_required", "request_unknown", "partial_success", "success", "interrupted"}:
            return False
        if run["cancel_requested_at"] is not None:
            return False
        intent = operation_store._remote_write_checkpoint(run.get("data"))
        if intent and str(intent.get("receipt_state") or intent.get("state") or "started") != "confirmed":
            return False
        cur.execute(f"SELECT * FROM {operation_store._table('operation_tasks')} WHERE id=%s FOR UPDATE", (run["task_id"],))
        task = cur.fetchone()
        if not task or task["last_run_id"] != run_id or task["source_system"] != "native_operations" or task["task_type"] != "extract_link":
            return False
        if task["status"] not in {"attention_required", "request_unknown", "partial_success", "success", "interrupted"} or not task["account_id"]:
            return False
        data = _json_object(task["data"], field_name="任务数据")
        if data.get("mode") not in {"auto_payment", "manual_payment"}:
            return False
        cur.execute(f"SELECT * FROM {operation_store._table('extract_link_provider_jobs')} WHERE run_id=%s FOR UPDATE", (run_id,))
        job = cur.fetchone()
        if not job or job["provider_id"] != data.get("provider_id") or job["job_id"] != expected_job_id or not job["job_id"]:
            return False
        state = _json_object(job["public_state"], field_name="平台公开状态")
        if run["status"] == "success" and state.get("plus_status") == "confirmed":
            return False
        if data.get("mode") == "manual_payment" and job["payment_state"] != "succeeded":
            return False
        if job["payment_state"] not in {"unknown", "succeeded"} or not payment_scan_completed(state, provider_id=job["provider_id"]):
            return False
        summary = state.get("summary") or {}
        private = _json_object(job["private_data"], field_name="平台恢复数据")
        result_summary = _json_object(run.get("result_summary") or {}, field_name="执行摘要")
        interrupted_verification = (
            job["provider_id"] == "legacy" and job["payment_state"] == "succeeded"
            and (run["status"] == "interrupted" or result_summary.get("cause_code") == "worker_interrupted")
            and (isinstance(private.get("local_reconcile"), dict) or summary.get("local_plan_check_pending") is True)
        )
        if (run["status"] == "interrupted" or task["status"] == "interrupted") and not interrupted_verification:
            return False
        if interrupted_verification and task["batch_id"]:
            cur.execute(f"SELECT status FROM {operation_store._table('operation_batches')} WHERE id=%s", (task["batch_id"],))
            batch = cur.fetchone()
            if batch and batch["status"] in {"paused", "stopped", "cancelled"}:
                return False
        saved_arrival = (interrupted_verification and state.get("plus_status") == "confirmed"
                         and summary.get("payment_confirmation_source") == "local_plan_check")
        account = record_store.get_row(record_store.ACCOUNTS, int(task["account_id"]), conn=conn, for_update=True)
        cur.execute(f"""SELECT 1 FROM {operation_store._table('operation_tasks')} newer
            LEFT JOIN {operation_store._table('operation_runs')} related ON related.task_id=newer.id
            WHERE newer.account_id=%s AND newer.task_type='extract_link'
              AND (newer.id>%s OR related.id>%s) LIMIT 1""", (task["account_id"], task["id"], run_id))
        if cur.fetchone() and not saved_arrival:
            return False
        if saved_arrival:
            account = {"plan_check_status": "success", "current_plan_type": "plus",
                       "plan_checked_at": summary.get("payment_confirmed_plan_checked_at")}
        if not independent_plus_is_confirmed(account, task_created_at=task["created_at"]):
            return False
        checked_at = str(account.get("plan_checked_at") or "").strip(" ") or str(account.get("plan_last_success_at") or "").strip(" ")
        checked_time = _workbench_timestamp(checked_at)
        boundary_job, boundary_run = job, run
        run_data = _json_object(run.get("data") or {}, field_name="执行数据")
        source_id = run_data.get("provider_job_run_id")
        if (job["payment_state"] == "succeeded" and run_data.get("workbench_action") == "sync_status"
                and isinstance(source_id, int) and not isinstance(source_id, bool)):
            cur.execute(f"""SELECT source.*, original.completed_at AS original_completed_at
                FROM {operation_store._table('extract_link_provider_jobs')} source
                JOIN {operation_store._table('operation_runs')} original ON original.id=source.run_id
                WHERE source.run_id=%s AND original.task_id=%s FOR UPDATE OF source, original""", (source_id, task["id"]))
            original = cur.fetchone()
            if (original and original["job_id"] == job["job_id"] and original["provider_id"] == job["provider_id"]
                    and payment_scan_completed(_json_object(original["public_state"], field_name="原单公开状态"), provider_id=job["provider_id"])):
                boundary_job = original
                boundary_run = {"completed_at": original["original_completed_at"]}
        boundaries = [_workbench_timestamp(value) for value in (task["created_at"], boundary_job["updated_at"], boundary_run["completed_at"])]
        if interrupted_verification:
            # 重启收口时间不是付款时间；已写入的独立到账证据不能因此失效。
            boundaries = [_workbench_timestamp(task["created_at"])]
            if not saved_arrival:
                boundaries.append(_workbench_timestamp(boundary_job["updated_at"]))
        # 普通终态只接受结束后的独立查询；中断核验仍须晚于任务及已支付快照。
        if any(value is None for value in boundaries) or checked_time <= max(boundaries):
            return False
        summary = dict(state.get("summary") or {})
        message = "原单扫码已完成，后续独立套餐查询确认 Plus 到账"
        for key in ("local_reconcile_reason", "local_reconcile_halted_at", "failure_message", "failure_code", "failure_type"):
            summary.pop(key, None)
        summary.update({
            "payment_confirmation_source": "local_plan_check", "payment_confirmed_plan_checked_at": checked_at,
            "automatic_payment_requires_reconcile": False, "local_plan_check_pending": False,
            "local_reconcile_halted": False, "current_step": message, "percent": 100,
            "outcome": "success", "plus_status": "confirmed",
        })
        state.update(extraction_state="succeeded", payment_state="succeeded", plus_status="confirmed", summary=summary, message=message)
        result_summary = _json_object(run.get("result_summary") or {}, field_name="执行摘要")
        for key in ("failure_stage", "failure_event_id", "failure_evidence", "requested_status"):
            result_summary.pop(key, None)
        result_summary.update({
            "extraction_status": "succeeded", "payment_status": "succeeded", "plus_status": "confirmed",
            "payment_confirmation_source": "local_plan_check", "payment_confirmed_plan_checked_at": checked_at,
            "outcome": "success", "reconcile_required": False, "message": message,
        })
        cur.execute(f"""UPDATE {operation_store._table('extract_link_provider_jobs')}
            SET extraction_state='succeeded', payment_state='succeeded', public_state=%s::jsonb, updated_at=now() WHERE run_id=%s""", (_dump(state), run_id))
        failure_keys = ['failure_stage', 'failure_event_id', 'failure_evidence']
        cur.execute(f"""UPDATE {operation_store._table('operation_runs')}
            SET status='success', progress_stage='complete', error_category=NULL, error_code=NULL,
                error_message=NULL, result_summary=%s::jsonb, data=data - %s::text[] WHERE id=%s""",
            (_dump(result_summary), failure_keys, run_id))
        cur.execute(f"""UPDATE {operation_store._table('operation_tasks')}
            SET status='success', target_status='completed', current_stage='complete', updated_at=now(),
                error_category=NULL, error_code=NULL, error_message=NULL, next_actions='[]'::jsonb,
                data=data - %s::text[] WHERE id=%s AND last_run_id=%s""", (failure_keys, task["id"], run_id))
        event_id = uuid.uuid4().hex
        cur.execute(f"""INSERT INTO {operation_store._table('operation_events')}
            (event_uuid, task_id, run_id, source_system, source_id, level, stage, event_type, message, detail)
            VALUES (%s,%s,%s,'native_operations',%s,'INFO','payment','payment.local_reconciled',%s,%s::jsonb)""",
            (event_id, task["id"], run_id, event_id, message, _dump({
                "previous_status": run["status"], "payment_confirmation_source": "local_plan_check",
                "payment_confirmed_plan_checked_at": checked_at, "payment_status": "succeeded", "plus_status": "confirmed",
                "step_state": "success", "percent": 100,
            })))
        # 同一 Run 的后续独立证据解除原失败阶段；历史事件继续保留用于排查。
        for stage, stage_message in (("plan_check", "后续独立套餐查询已确认 Plus 到账"), ("plus", "Plus 到账已由独立套餐查询核实")):
            stage_event_id = uuid.uuid4().hex
            cur.execute(f"""INSERT INTO {operation_store._table('operation_events')}
                (event_uuid, task_id, run_id, source_system, source_id, level, stage, event_type, message, detail)
                VALUES (%s,%s,%s,'native_operations',%s,'INFO',%s,'stage.success',%s,%s::jsonb)""",
                (stage_event_id, task["id"], run_id, stage_event_id, stage, stage_message, _dump({
                    "step_state": "success", "payment_confirmation_source": "local_plan_check",
                    "payment_confirmed_plan_checked_at": checked_at,
                })))
        if task["batch_id"]:
            operation_store._refresh_batches(cur, [int(task["batch_id"])])
        return True


def reconcile_completed_payments(*, account_id: int | None = None) -> dict[str, int]:
    """用已保存的原单及后续 Plus 查询补齐支付状态，不发起网络请求或重跑。"""
    if account_id is not None and (isinstance(account_id, bool) or not isinstance(account_id, int) or account_id < 1):
        raise ValueError("account_id 参数无效")
    operation_store.init()
    where = [
        "task.source_system='native_operations'", "task.task_type='extract_link'",
        "task.data->>'mode' IN ('auto_payment','manual_payment')",
        "run.source_system='native_operations'", "run.status IN ('attention_required','request_unknown','partial_success','success','interrupted')",
        "task.status IN ('attention_required','request_unknown','partial_success','success','interrupted')", "run.cancel_requested_at IS NULL",
        "job.provider_id IN ('huanguang','legacy','lumen_flow')", "job.payment_state IN ('unknown','succeeded')", "COALESCE(job.job_id,'')<>''",
        "(run.status<>'success' OR job.public_state->>'plus_status' IS DISTINCT FROM 'confirmed')",
    ]
    params = []
    if account_id is not None:
        where.append("task.account_id=%s")
        params.append(account_id)
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT run.id, job.job_id FROM {operation_store._table('operation_tasks')} task
            JOIN {operation_store._table('operation_runs')} run ON run.id=task.last_run_id
            JOIN {operation_store._table('extract_link_provider_jobs')} job ON job.run_id=run.id
            WHERE {' AND '.join(where)} ORDER BY run.id""", tuple(params))
        candidates = [dict(row) for row in cur.fetchall()]
    result = {"confirmed": 0, "skipped": 0, "failed": 0}
    for candidate in candidates:
        try:
            confirmed = _reconcile_completed_payment(int(candidate["id"]), expected_job_id=str(candidate["job_id"]))
        except Exception as exc:
            result["failed"] += 1
            logger.warning("[提链] 本地支付状态补齐失败：run_id=%s error_type=%s", candidate["id"], type(exc).__name__)
        else:
            result["confirmed" if confirmed else "skipped"] += 1
    return result


def _workbench_timestamp_sql(value_sql: str) -> str:
    # 无时区时间沿用账号快照的进程本地语义，与 Python 的兼容时间解析一致。
    offset = datetime.now().astimezone().utcoffset()
    offset_seconds = int(offset.total_seconds()) if offset is not None else 0
    # PostgreSQL 16 的输入校验会拒绝非法日期，避免合法外形的坏快照使分页报错。
    return f"""CASE WHEN {value_sql} ~ '{_WORKBENCH_TIMESTAMP_PATTERN}'
        AND pg_input_is_valid({value_sql}, 'timestamp with time zone')
        THEN CASE WHEN {value_sql} ~ '(Z|[+-][0-9]{{2}}:[0-9]{{2}})$'
            THEN {value_sql}::timestamptz
            ELSE ({value_sql}::timestamp AT TIME ZONE INTERVAL '{offset_seconds} seconds') END
        ELSE NULL END"""


def _workbench_projection_sql(clauses: list[str]) -> str:
    """仅归一化筛选所需标量，不载入账号凭据、付款内容和历史 Run。"""
    accounts = record_store._qualified(record_store.ACCOUNTS)
    # 与账号投影保持 account_id 优先、找不到时按规范化邮箱回填的规则。
    account_columns = """id, plan_check_status, current_plan_type, plan_type,
        COALESCE(NULLIF(BTRIM(data->>'plan_checked_at'), ''), NULLIF(BTRIM(plan_last_success_at), '')) AS plan_checked_at,
        COALESCE(data->'has_active_subscription' NOT IN
            ('null'::jsonb, 'false'::jsonb, '0'::jsonb, '\"\"'::jsonb, '[]'::jsonb, '{}'::jsonb), FALSE) AS subscribed"""
    checked_at_sql = _workbench_timestamp_sql("COALESCE(by_id.plan_checked_at, by_email.plan_checked_at)")
    return f"""filtered_tasks AS MATERIALIZED (
        SELECT t.id, t.account_id, t.email_snapshot, t.last_run_id, t.created_at, t.status,
            t.data->>'provider_id' AS task_provider_id, t.data->>'mode' AS task_mode
        FROM {operation_store._table('operation_tasks')} t WHERE {' AND '.join(clauses)}
    ), missing_account_emails AS MATERIALIZED (
        SELECT DISTINCT LOWER(BTRIM(t.email_snapshot)) AS email_key
        FROM filtered_tasks t WHERE BTRIM(t.email_snapshot) <> ''
            AND NOT EXISTS (SELECT 1 FROM {accounts} known WHERE known.id=t.account_id)
    ), account_emails AS (
        SELECT LOWER(fallback_account.email) AS email_key, MIN(fallback_account.id) AS account_id
        FROM {accounts} fallback_account
        WHERE EXISTS (SELECT 1 FROM missing_account_emails)
            AND LOWER(fallback_account.email) IN (SELECT email_key FROM missing_account_emails)
        GROUP BY LOWER(fallback_account.email)
    ), raw AS (
        SELECT t.id AS task_id, t.created_at AS task_created_at,
            COALESCE(r.created_at, t.created_at) AS sort_created_at,
            CASE WHEN LOWER(COALESCE(NULLIF(r.status, ''), NULLIF(t.status, ''), 'queued'))='attention_required'
                THEN 'request_unknown' ELSE LOWER(COALESCE(NULLIF(r.status, ''), NULLIF(t.status, ''), 'queued')) END AS task_status,
            COALESCE(NULLIF(t.task_provider_id, ''), NULLIF(job.provider_id, ''), 'legacy') AS provider_id,
            COALESCE(NULLIF(t.task_mode, ''), 'extract_only') AS mode,
            COALESCE(job.provider_id IN ('huanguang', 'legacy')
                AND job.public_state->'summary'->'local_reconcile_halted'='true'::jsonb, FALSE) AS local_reconcile_halted,
            CASE WHEN job.provider_id='huanguang' AND job.public_state->'summary'->'extraction_ever_succeeded'='true'::jsonb
                THEN 'succeeded' ELSE LOWER(COALESCE(NULLIF(job.public_state->>'extraction_state', ''),
                    NULLIF(r.result_summary->>'extraction_status', ''), '')) END AS extraction,
            LOWER(COALESCE(NULLIF(job.public_state->>'payment_state', ''), NULLIF(r.result_summary->>'payment_status', ''), 'not_started')) AS payment,
            LOWER(COALESCE(NULLIF(job.public_state->>'plus_status', ''), NULLIF(r.result_summary->>'plus_status', ''), 'unknown')) AS plus,
            COALESCE(r.result_summary->'has_link' NOT IN
                ('null'::jsonb, 'false'::jsonb, '0'::jsonb, '\"\"'::jsonb, '[]'::jsonb, '{{}}'::jsonb), FALSE)
                OR COALESCE(r.result_summary->>'remote_job_id', '') <> '' AS legacy_succeeded,
            LOWER(COALESCE(by_id.plan_check_status, by_email.plan_check_status, '')) AS plan_check_status,
            LOWER(COALESCE(NULLIF(by_id.current_plan_type, ''), by_id.plan_type,
                NULLIF(by_email.current_plan_type, ''), by_email.plan_type, '')) AS plan,
            COALESCE(by_id.subscribed, by_email.subscribed, FALSE) AS subscribed,
            {checked_at_sql} AS plan_checked_at
        FROM filtered_tasks t
        LEFT JOIN {operation_store._table('operation_runs')} r ON r.id=t.last_run_id
        LEFT JOIN {operation_store._table('extract_link_provider_jobs')} job ON job.run_id=r.id
        LEFT JOIN (SELECT {account_columns} FROM {accounts}) by_id ON by_id.id=t.account_id
        LEFT JOIN account_emails email_match ON by_id.id IS NULL AND BTRIM(t.email_snapshot) <> ''
            AND email_match.email_key=LOWER(BTRIM(t.email_snapshot))
        LEFT JOIN LATERAL (
            SELECT {account_columns} FROM {accounts} WHERE id=email_match.account_id LIMIT 1
        ) by_email ON TRUE
    ), normalized AS (
        SELECT *, CASE
            WHEN extraction IN ('succeeded','success') THEN 'success'
            WHEN extraction IN ('queued','running','failed','pending','unknown','not_started') THEN extraction
            WHEN extraction='' AND provider_id='legacy' AND task_status='success' AND legacy_succeeded THEN 'success'
            WHEN extraction='' AND provider_id='legacy' AND task_status IN ('failed','request_unknown','cancelled','stopped') THEN 'failed'
            WHEN extraction='' THEN 'pending' ELSE 'unknown' END AS extraction_status,
            CASE WHEN mode='extract_only' THEN 'unpaid'
                WHEN payment IN ('succeeded','success','paid') THEN 'paid'
                WHEN payment='not_started' THEN 'unpaid' WHEN payment='failed' THEN 'failed'
                WHEN payment='unknown' THEN 'request_unknown' ELSE 'pending_payment' END AS payment_status
        FROM raw
    ), projected AS (
        SELECT *, CASE WHEN mode IN ('auto_payment','manual_payment') AND extraction_status='success'
            AND plan_check_status='success' AND BTRIM(plan) IN ('plus','pro') AND plan_checked_at > task_created_at
            THEN 'confirmed'
            ELSE plus END AS plus_status
        FROM normalized
    )"""


def list_workbench_page(
    *, provider_id: str | None = None, mode: str | None = None, query: str = "",
    status: str = "", page: int = 1, page_size: int = 20, batch_id: int | None = None,
) -> dict:
    """数据库内统计、筛选和分页，仅返回当前页的公开任务明细。"""
    operation_store.init()
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))
    clauses, params = _workbench_where(provider_id=provider_id, mode=mode, query=query, batch_id=batch_id)
    projection = _workbench_projection_sql(clauses)
    predicate = _WORKBENCH_STATUS_SQL.get(status, "FALSE") if status else "TRUE"
    count_columns = [f"COUNT(*) FILTER (WHERE {condition}) AS {name}" for name, condition in _WORKBENCH_STATUS_SQL.items()]
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""WITH {projection} SELECT COUNT(*) AS all,
                {', '.join(count_columns)}, COUNT(*) FILTER (WHERE {predicate}) AS total FROM projected""",
            tuple(params),
        )
        totals = dict(cur.fetchone() or {})
        cur.execute(
            f"""WITH {projection}, selected AS (
                SELECT task_id FROM projected WHERE {predicate}
                ORDER BY sort_created_at DESC, task_id DESC LIMIT %s OFFSET %s
            )
            SELECT {_workbench_columns()} {_workbench_joins()}
            JOIN selected ON selected.task_id=t.id
            ORDER BY COALESCE(r.created_at, t.created_at) DESC, t.id DESC""",
            (*params, page_size, (page - 1) * page_size),
        )
        items = _workbench_rows(cur.fetchall())
    return {"items": items, "total": int(totals.pop("total", 0) or 0), "page": page, "page_size": page_size,
            "counts": {key: int(value or 0) for key, value in totals.items()}}


def get_workbench_detail_rows(task_id: int) -> dict | None:
    """精确读取提链任务、批量历史 Run，以及最近 200 条事件。"""
    operation_store.init()
    clauses, _ = _workbench_where()
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {_workbench_columns()} {_workbench_joins()} WHERE {' AND '.join(clauses)} AND t.id=%s",
            (int(task_id),),
        )
        row = cur.fetchone()
        if row is None:
            return None
        item = _workbench_rows([row])[0]
        cur.execute(
            f"""SELECT r.id AS run_id, r.run_no, r.status, r.source_system,
                COALESCE(NULLIF(job.provider_id, ''), NULLIF(r.data->>'provider_id', ''), 'legacy') AS provider_id,
                COALESCE(NULLIF(job.public_state->>'extraction_state', ''), 'unknown') AS extraction_status,
                COALESCE(NULLIF(job.public_state->>'payment_state', ''), 'not_started') AS payment_status,
                r.created_at, r.completed_at, r.error_message,
                {operation_store._compatibility_run_projection_sql(run_alias='r')}
                FROM {operation_store._table('operation_runs')} r
                {operation_store._compatibility_run_joins_sql(run_alias='r')}
                LEFT JOIN {operation_store._table('extract_link_provider_jobs')} job ON job.run_id=r.id
                WHERE r.task_id=%s ORDER BY r.run_no, r.id""",
            (int(task_id),),
        )
        history = [operation_store._normalize_compatibility_run(operation_store._row(dict(row)) or {})
                   for row in cur.fetchall()]
        cur.execute(
            f"""SELECT e.*, r.run_no FROM {operation_store._table('operation_events')} e
                LEFT JOIN {operation_store._table('operation_runs')} r ON r.id=e.run_id
                WHERE e.task_id=%s ORDER BY e.created_at DESC, e.id DESC LIMIT 200""",
            (int(task_id),),
        )
        events = [operation_store._normalize_compatibility_event(operation_store._read_event(dict(row)))
                  for row in reversed(cur.fetchall())]
    return {"item": item, "history": history, "events": events}


def update_provider_job_state(run_id: int, public_state: Mapping[str, Any]) -> bool:
    """更新受控公开状态；保留 Huanguang 等 Provider 的私有恢复字段。"""
    operation_store.init()
    run_value = int(run_id)
    incoming = _public_state(public_state)
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT public_state
            FROM {operation_store._table('extract_link_provider_jobs')}
            WHERE run_id=%s
            FOR UPDATE
            """,
            (run_value,),
        )
        row = cur.fetchone()
        if row is None:
            return False
        merged = _json_object(row["public_state"], field_name="public_state")
        artifact = {**safe_payment_artifact(merged.get("payment_artifact")), **incoming.get("payment_artifact", {})}
        merged.update(incoming)
        if artifact:
            merged["payment_artifact"] = artifact
        cur.execute(
            f"""
            UPDATE {operation_store._table('extract_link_provider_jobs')}
            SET extraction_state=%s, payment_state=%s, public_state=%s::jsonb, updated_at=now()
            WHERE run_id=%s
            """,
            (
                str(merged.get("extraction_state") or "unknown")[:80],
                str(merged.get("payment_state") or "not_started")[:80],
                _dump(merged),
                run_value,
            ),
        )
        return cur.rowcount == 1
