# -*- coding: utf-8 -*-
"""PostgreSQL-backed cross-process coordination for 1024Proxy leases."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from core import postgres_store, record_store


PROXY_LEASES = record_store.PROXY_LEASES
ACTIVE_STATES = ("pending", "leased", "recent")
CORRELATION_FIELDS = (
    "account_id",
    "purpose",
    "operation_task_id",
    "operation_run_id",
    "registration_job_id",
    "registration_attempt_id",
    "route_attempt_id",
    "route_attempt_no",
)


class DuplicateProxyLeaseError(RuntimeError):
    """Another process already owns the endpoint or exit IP."""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"代理租约关联 ID 必须是整数: {value!r}")


def _optional_text(value: Any, *, limit: int = 160) -> str | None:
    text = str(value or "").strip()
    return text[:limit] or None


def _legacy_job_id(job_id: Any) -> int | None:
    try:
        return _optional_int(job_id)
    except ValueError:
        return None


def _cleanup_expired() -> None:
    migrate()
    now = _now()
    with record_store.transaction() as conn:
        record_store.patch_rows_where(
            PROXY_LEASES,
            changes={"state": "released", "released_at": now},
            where='"state" IN (\'pending\', \'leased\') AND "expires_at" IS NOT NULL AND "expires_at" <= %s',
            params=(now,),
            conn=conn,
        )
        record_store.patch_rows_where(
            PROXY_LEASES,
            changes={"state": "released"},
            where='"state" = \'recent\' AND "recent_until" IS NOT NULL AND "recent_until" <= %s',
            params=(now,),
            conn=conn,
        )


def reserve_pending(
    *,
    lease_id: str,
    provider: str,
    endpoint: str,
    proxy_url: str,
    acquired_at: str,
    expires_at: str,
    batch_id: str | None = None,
    job_id: int | str | None = None,
    account_id: int | None = None,
    purpose: str | None = None,
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    registration_job_id: int | None = None,
    registration_attempt_id: int | None = None,
    route_attempt_id: str | None = None,
    route_attempt_no: int | None = None,
) -> None:
    """Reserve an endpoint before network validation.

    The partial endpoint index makes this operation mutually exclusive across
    WebUI/CLI processes. A duplicate is reported separately from database errors
    so the provider can fetch another endpoint.
    """
    _cleanup_expired()
    try:
        record_store.insert_row(
            PROXY_LEASES,
            {
                "lease_id": lease_id,
                "provider": provider,
                "endpoint": endpoint,
                "proxy_url": proxy_url,
                "state": "pending",
                "acquired_at": acquired_at,
                "expires_at": expires_at,
                "batch_id": batch_id,
                "job_id": str(job_id) if job_id is not None else None,
                "account_id": _optional_int(account_id),
                "purpose": _optional_text(purpose),
                "operation_task_id": _optional_int(operation_task_id),
                "operation_run_id": _optional_int(operation_run_id),
                "registration_job_id": _optional_int(registration_job_id),
                "registration_attempt_id": _optional_int(registration_attempt_id),
                "route_attempt_id": _optional_text(route_attempt_id),
                "route_attempt_no": _optional_int(route_attempt_no),
            },
        )
    except Exception as exc:
        text = str(exc).lower()
        if "duplicate key" in text or "unique constraint" in text or "unique index" in text:
            raise DuplicateProxyLeaseError(f"端点已被其他进程占用: {endpoint}") from exc
        raise


def activate(
    *,
    lease_id: str,
    exit_ip: str | None,
    region: str | None,
    expires_at: str,
) -> None:
    """Promote a pending lease after exit validation."""
    try:
        if not record_store.patch_row(
            PROXY_LEASES,
            _lease_row_id(lease_id),
            {
                "state": "leased",
                "exit_ip": exit_ip,
                "region": region,
                "expires_at": expires_at,
            },
        ):
            raise RuntimeError(f"代理租约不存在或已失效: {lease_id}")
    except Exception as exc:
        text = str(exc).lower()
        if "duplicate key" in text or "unique constraint" in text or "unique index" in text:
            raise DuplicateProxyLeaseError(f"出口 IP 已被其他进程占用: {exit_ip or '-'}") from exc
        raise


def release(
    *,
    lease_id: str,
    recent_until: str | None,
    reason: str,
) -> None:
    row_id = _find_lease_row_id(lease_id)
    if row_id is None:
        return
    changes: dict[str, Any] = {
        "state": "recent" if recent_until else "released",
        "recent_until": recent_until,
        "released_at": _now(),
        "release_reason": str(reason or "completed")[:120],
    }
    record_store.patch_row(PROXY_LEASES, row_id, changes)


def bind(
    *,
    lease_id: str,
    account_id: int | None = None,
    purpose: str | None = None,
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    registration_job_id: int | None = None,
    registration_attempt_id: int | None = None,
    route_attempt_id: str | None = None,
    route_attempt_no: int | None = None,
) -> bool:
    """Add correlation facts to an existing lease without replacing its row."""
    row_id = _find_lease_row_id(lease_id)
    if row_id is None:
        return False
    values = {
        "account_id": _optional_int(account_id),
        "purpose": _optional_text(purpose),
        "operation_task_id": _optional_int(operation_task_id),
        "operation_run_id": _optional_int(operation_run_id),
        "registration_job_id": _optional_int(registration_job_id),
        "registration_attempt_id": _optional_int(registration_attempt_id),
        "route_attempt_id": _optional_text(route_attempt_id),
        "route_attempt_no": _optional_int(route_attempt_no),
    }
    changes = {key: value for key, value in values.items() if value is not None}
    return bool(changes) and record_store.patch_row(PROXY_LEASES, row_id, changes)


def abort(lease_id: str) -> None:
    """Remove a validation reservation after a failed candidate."""
    row_id = _find_lease_row_id(lease_id)
    if row_id is not None:
        record_store.delete_rows(PROXY_LEASES, [row_id])


def active_rows() -> list[dict]:
    return query_leases(view="current")


def migrate() -> None:
    """Apply the additive lease migration without guessing legacy ownership."""
    record_store.init()


def _safe_lease_row(row: dict) -> dict:
    """Return the fields allowed by the proxy/traffic API.

    In particular, the credentialed proxy URL is deliberately omitted even in
    masked form.  Raw exit IPs are only exposed through this new API boundary.
    """
    from core.proxy_provider import mask_endpoint

    registration_job_id = row.get("registration_job_id") or row.get("joined_registration_job_id")
    account_id = row.get("account_id")
    if account_id is not None:
        account_id = int(account_id)
    return {
        "id": row.get("id"),
        "lease_id": row.get("lease_id"),
        "provider": row.get("provider"),
        "endpoint": mask_endpoint(row.get("endpoint")),
        "exit_ip": row.get("exit_ip"),
        "region": row.get("region"),
        "state": row.get("state"),
        "purpose": row.get("purpose"),
        "account_id": account_id,
        "operation_task_id": row.get("operation_task_id") or row.get("joined_operation_task_id"),
        "operation_run_id": row.get("operation_run_id") or row.get("joined_operation_run_id"),
        "registration_job_id": registration_job_id,
        "registration_attempt_id": (
            row.get("registration_attempt_id")
            or row.get("joined_registration_attempt_id")
            or row.get("joined_operation_attempt_id")
        ),
        "route_attempt_id": row.get("route_attempt_id"),
        "route_attempt_no": row.get("route_attempt_no") or row.get("joined_route_attempt_no"),
        "acquired_at": row.get("acquired_at"),
        "expires_at": row.get("expires_at"),
        "recent_until": row.get("recent_until"),
        "released_at": row.get("released_at"),
        "release_reason": row.get("release_reason"),
    }


def _relation_flags(cur) -> dict[str, bool]:
    schema = postgres_store.schema_name()
    names = {
        "operation_tasks": f"{schema}.operation_tasks",
        "operation_runs": f"{schema}.operation_runs",
        "registration_jobs": f"{schema}.registration_jobs",
        "registration_attempts": f"{schema}.registration_attempts",
    }
    cur.execute(
        "SELECT to_regclass(%s) AS operation_tasks, "
        "to_regclass(%s) AS operation_runs, "
        "to_regclass(%s) AS registration_jobs, "
        "to_regclass(%s) AS registration_attempts",
        tuple(names.values()),
    )
    row = cur.fetchone()
    return {key: bool(row[key]) for key in names}


def query_leases(
    *,
    view: str = "current",
    account_id: int | None = None,
    purpose: str | None = None,
    registration_job_id: int | None = None,
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    limit: int = 200,
) -> list[dict]:
    """Query durable lease facts, enriching IDs from PostgreSQL operation rows."""
    migrate()
    selected_view = str(view or "current").strip().lower()
    if selected_view not in {"current", "history", "all"}:
        raise ValueError("租约视图必须是 current / history / all")
    params: list[Any] = []
    where: list[str] = []
    if selected_view == "current":
        where.append('l."state" IN (\'pending\', \'leased\', \'recent\')')
    account_filter = _optional_int(account_id)
    purpose_filter = str(purpose).strip()[:160] if purpose else None
    registration_job_filter = _optional_int(registration_job_id)
    operation_task_filter = _optional_int(operation_task_id)
    operation_run_filter = _optional_int(operation_run_id)
    bounded_limit = max(1, min(1000, int(limit or 200)))

    lease_table = postgres_store.qualified(PROXY_LEASES.name)
    with postgres_store.connect(row_factory=_dict_row_factory()) as conn, conn.cursor() as cur:
        flags = _relation_flags(cur)
        select_extra: list[str] = []
        joins: list[str] = []
        if flags["operation_runs"] and flags["operation_tasks"]:
            operation_runs = postgres_store.qualified("operation_runs")
            operation_tasks = postgres_store.qualified("operation_tasks")
            joins.extend(
                [
                    f"LEFT JOIN LATERAL (SELECT candidate.* FROM {operation_runs} candidate WHERE "
                    f"candidate.id = l.\"operation_run_id\" OR ("
                    f"l.\"operation_run_id\" IS NULL AND candidate.source_system = 'registration_jobs' "
                    f"AND candidate.source_id = COALESCE(l.\"registration_job_id\"::text, "
                    f"CASE WHEN l.\"job_id\" ~ '^[0-9]+$' THEN l.\"job_id\" END)) "
                    f"ORDER BY CASE WHEN candidate.id = l.\"operation_run_id\" THEN 0 ELSE 1 END, "
                    f"candidate.id DESC LIMIT 1) op_run ON TRUE",
                    f"LEFT JOIN {operation_tasks} op_task ON op_task.id = COALESCE(l.\"operation_task_id\", op_run.task_id)",
                ]
            )
            select_extra.extend(
                [
                    'op_task.id AS "joined_operation_task_id"',
                    'op_run.id AS "joined_operation_run_id"',
                    'COALESCE(op_run.account_id, op_task.account_id) AS "joined_operation_account_id"',
                    'op_task.attempt_id AS "joined_operation_attempt_id"',
                ]
            )
        if flags["registration_jobs"]:
            jobs = postgres_store.qualified("registration_jobs")
            joins.append(
                f"LEFT JOIN {jobs} reg_job ON reg_job.id = COALESCE(l.\"registration_job_id\", "
                f"CASE WHEN l.\"job_id\" ~ '^[0-9]+$' THEN l.\"job_id\"::bigint END)"
            )
            select_extra.extend(
                [
                    'reg_job.id AS "joined_registration_job_id"',
                    'reg_job.account_id AS "joined_account_id"',
                    'reg_job.attempt_id AS "joined_registration_attempt_id"',
                    "CASE WHEN COALESCE(reg_job.data->>'route_attempt_no', '') ~ '^[0-9]+$' "
                    "THEN (reg_job.data->>'route_attempt_no')::integer END AS \"joined_route_attempt_no\"",
                ]
            )
        if flags["registration_attempts"] and flags["registration_jobs"]:
            attempts = postgres_store.qualified("registration_attempts")
            joins.append(
                f"LEFT JOIN {attempts} reg_attempt ON reg_attempt.id = COALESCE(l.\"registration_attempt_id\", reg_job.attempt_id)"
            )
        if account_filter is not None:
            account_sources = ['l."account_id"']
            if flags["registration_jobs"]:
                account_sources.append("reg_job.account_id")
            if flags["operation_runs"] and flags["operation_tasks"]:
                account_sources.append("COALESCE(op_run.account_id, op_task.account_id)")
            where.append(f"COALESCE({', '.join(account_sources)}) = %s")
            params.append(account_filter)
        if purpose_filter:
            where.append('l."purpose" = %s')
            params.append(purpose_filter)
        if registration_job_filter is not None:
            if flags["registration_jobs"]:
                where.append('COALESCE(l."registration_job_id", reg_job.id) = %s')
            else:
                where.append('l."registration_job_id" = %s')
            params.append(registration_job_filter)
        if operation_task_filter is not None:
            if flags["operation_runs"] and flags["operation_tasks"]:
                where.append('COALESCE(l."operation_task_id", op_task.id) = %s')
            else:
                where.append('l."operation_task_id" = %s')
            params.append(operation_task_filter)
        if operation_run_filter is not None:
            if flags["operation_runs"] and flags["operation_tasks"]:
                where.append('COALESCE(l."operation_run_id", op_run.id) = %s')
            else:
                where.append('l."operation_run_id" = %s')
            params.append(operation_run_filter)
        selected = "l.*"
        if select_extra:
            selected += ", " + ", ".join(select_extra)
        sql = f"SELECT {selected} FROM {lease_table} l {' '.join(joins)}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY l.\"id\" DESC LIMIT %s"
        params.append(bounded_limit)
        cur.execute(sql, params)
        result: list[dict] = []
        for raw in cur.fetchall():
            row = record_store.merge_row(PROXY_LEASES, dict(raw)) or {}
            if row.get("account_id") is None:
                row["account_id"] = raw.get("joined_account_id") or raw.get("joined_operation_account_id")
            result.append(_safe_lease_row({**dict(raw), **row}))
        return result


def operation_correlation_for_registration_job(job_id: int | str | None) -> dict[str, int | None]:
    """Resolve the current operation task/run for a legacy registration job."""
    value = _legacy_job_id(job_id)
    if value is None:
        return {"operation_task_id": None, "operation_run_id": None}
    record_store.init()
    with postgres_store.connect(row_factory=_dict_row_factory()) as conn, conn.cursor() as cur:
        flags = _relation_flags(cur)
        if not (flags["operation_runs"] and flags["operation_tasks"]):
            return {"operation_task_id": None, "operation_run_id": None}
        cur.execute(
            f"""
            SELECT op_task.id AS operation_task_id, op_run.id AS operation_run_id
            FROM {postgres_store.qualified('operation_runs')} op_run
            JOIN {postgres_store.qualified('operation_tasks')} op_task ON op_task.id=op_run.task_id
            WHERE op_run.source_system='registration_jobs' AND op_run.source_id=%s
            ORDER BY op_run.id DESC LIMIT 1
            """,
            (str(value),),
        )
        row = cur.fetchone()
        if not row:
            return {"operation_task_id": None, "operation_run_id": None}
        return {
            "operation_task_id": int(row["operation_task_id"]),
            "operation_run_id": int(row["operation_run_id"]),
        }


def _dict_row_factory():
    from psycopg.rows import dict_row

    return dict_row


def _find_lease_row_id(lease_id: str) -> int | None:
    row = record_store.get_row_by(PROXY_LEASES, "lease_id", str(lease_id))
    return int(row["id"]) if row else None


def _lease_row_id(lease_id: str) -> int:
    row_id = _find_lease_row_id(lease_id)
    if row_id is None:
        raise RuntimeError(f"代理租约不存在: {lease_id}")
    return row_id
