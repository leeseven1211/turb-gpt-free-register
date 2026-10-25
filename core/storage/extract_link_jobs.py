"""提链 Provider 的远端任务状态与私有恢复凭据存储。"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from core import record_store
from core.extract_link_providers.contracts import safe_links, safe_payment_artifact
from core.storage import operation as operation_store


_SUMMARY_FIELDS = frozenset({
    "current_step", "percent", "outcome", "preflight_status", "plus_status",
    "aftercare_status", "message", "remote_status", "remote_terminal_failure",
    "failure_message",
    "completed_steps", "total_steps", "run_attempt", "step_attempt", "failure_code",
    "failure_type", "last_event", "plus_verification_status", "automatic_payment_status",
    "automatic_payment_terminal", "automatic_payment_requires_reconcile", "remote_polling",
    "payment_check_status", "platform_plus_status", "entitlement_active", "entitlement_inferred",
    "payment_confirmation_source", "payment_confirmed_plan_checked_at",
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
            if key == "payment_confirmation_source" and item != "local_plan_check":
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
            if key == "local_reconcile_halted_at":
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
                private_data=stored.private_data || EXCLUDED.private_data,
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


def has_unresolved_auto_payment(account_id: int) -> bool:
    """检查该账号是否有已成功或尚未收敛的自动付款请求。"""
    operation_store.init()
    with operation_store._connect() as conn, conn.cursor() as cur:
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
              AND (job.provider_id<>'huanguang'
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
        OR (mode='auto_payment' AND payment_status IN ('pending_payment','request_unknown'))
        OR (payment_status='paid' AND plus_status IN ('unknown','pending','queued')))""",
    "running": "NOT local_reconcile_halted AND task_status IN ('running','cancelling','settling','stopping')",
    "extraction_succeeded": "extraction_status='success'",
    "payment_succeeded": "payment_status='paid'",
    "plus_confirmed": "plus_status='confirmed'",
    "needs_attention": """local_reconcile_halted OR task_status IN ('failed','request_unknown','cancelled','attention_required','partial_success','stopped')
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
            COALESCE(job.provider_id='huanguang'
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
            WHEN payment_status='paid' AND plus IN ('unknown','pending','queued') AND plan_check_status='success'
            THEN CASE WHEN plan LIKE '%%plus%%' OR plan LIKE '%%pro%%' OR subscribed THEN 'confirmed' ELSE 'not_confirmed' END
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
