"""提链 Provider 的远端任务状态与私有恢复凭据存储。"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from core.storage import operation as operation_store


_SUMMARY_FIELDS = frozenset({
    "current_step", "percent", "outcome", "preflight_status", "plus_status",
    "aftercare_status", "message",
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
            safe = []
            for link in links[:20]:
                if not isinstance(link, str):
                    continue
                candidate = link.strip()[:2000]
                try:
                    parsed = urlsplit(candidate)
                except ValueError:
                    continue
                if (
                    parsed.scheme in {"http", "https"}
                    and parsed.hostname
                    and not parsed.username
                    and not parsed.password
                ):
                    safe.append(candidate)
            if safe:
                result[field_name] = safe

    summary = value.get("summary")
    if isinstance(summary, Mapping):
        safe_summary: dict[str, Any] = {}
        for key in _SUMMARY_FIELDS:
            item = summary.get(key)
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
    with operation_store._connect() as conn, conn.cursor() as cur:
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
                public_state=EXCLUDED.public_state,
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
                   COALESCE(job.provider_id, run.data->>'provider_id', task.data->>'provider_id', 'legacy') AS provider_id,
                   COALESCE(run.data->>'mode', task.data->>'mode', 'extract_only') AS mode
            FROM {operation_store._table('operation_tasks')} task
            JOIN {operation_store._table('operation_runs')} run ON run.id=task.last_run_id
            JOIN {operation_store._table('extract_link_provider_jobs')} job ON job.run_id=run.id
            WHERE task.task_type='extract_link'
              AND task.source_system='native_operations'
              AND run.status='attention_required'
              AND NULLIF(BTRIM(job.job_id), '') IS NOT NULL
            ORDER BY job.updated_at, run.id
            """
        )
        return [operation_store._row(dict(row)) or {} for row in cur.fetchall()]


def list_workbench_rows(
    *, provider_id: str | None = None, mode: str | None = None, query: str = "",
) -> list[dict]:
    """批量读取提链工作台公开任务与当前 Run 状态。"""
    operation_store.init()
    clauses = [
        "t.task_type='extract_link'",
        "lower(COALESCE(t.data->>'deleted_by_user', '')) <> 'true'",
    ]
    params: list[Any] = []
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
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT t.id AS task_id, t.account_id, t.email_snapshot AS email, t.data AS task_data,
                   t.status AS task_status, t.target_status, t.current_stage,
                   t.created_at AS task_created_at, t.updated_at AS task_updated_at,
                   t.last_run_id, COUNT(all_runs.id) AS run_count,
                   r.id AS run_id, r.status AS run_status, r.progress_stage,
                   r.created_at AS run_created_at, r.completed_at AS run_completed_at,
                   r.result_summary, r.error_message,
                   job.provider_id AS job_provider_id,
                   job.job_id AS remote_job_id,
                   job.extraction_state, job.payment_state, job.public_state
            FROM {operation_store._table('operation_tasks')} t
            LEFT JOIN {operation_store._table('operation_runs')} r ON r.id=t.last_run_id
            LEFT JOIN {operation_store._table('operation_runs')} all_runs ON all_runs.task_id=t.id
            LEFT JOIN {operation_store._table('extract_link_provider_jobs')} job ON job.run_id=r.id
            WHERE {' AND '.join(clauses)}
            GROUP BY t.id, r.id, job.run_id
            ORDER BY COALESCE(r.created_at, t.created_at) DESC, t.id DESC
            """,
            tuple(params),
        )
        rows = [operation_store._row(dict(row)) or {} for row in cur.fetchall()]
    for row in rows:
        row["task_data"] = _json_object(row.get("task_data") or {}, field_name="task_data")
        row["result_summary"] = _json_object(row.get("result_summary") or {}, field_name="result_summary")
        row["public_state"] = _json_object(row.get("public_state") or {}, field_name="public_state")
    return rows


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
        merged.update(incoming)
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
