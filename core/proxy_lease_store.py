# -*- coding: utf-8 -*-
"""PostgreSQL-backed cross-process coordination for 1024Proxy leases."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg.rows import dict_row

from core import record_store
from core import postgres_store


PROXY_LEASES = record_store.PROXY_LEASES
ACTIVE_STATES = ("pending", "leased", "recent")


class DuplicateProxyLeaseError(RuntimeError):
    """Another process already owns the endpoint or exit IP."""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _cleanup_expired() -> None:
    now = _now()
    record_store.init()
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
                "purpose": str(purpose or "").strip()[:80] or None,
                "operation_task_id": _optional_int(operation_task_id),
                "operation_run_id": _optional_int(operation_run_id),
                "registration_job_id": _optional_int(registration_job_id),
                "route_attempt_no": _optional_int(route_attempt_no),
            },
        )
    except Exception as exc:
        text = str(exc).lower()
        if "duplicate key" in text or "unique constraint" in text or "unique index" in text:
            raise DuplicateProxyLeaseError(f"端点已被其他进程占用: {endpoint}") from exc
        raise


def correlate(
    *,
    lease_id: str,
    account_id: int | str | None = None,
    purpose: str | None = None,
    operation_task_id: int | str | None = None,
    operation_run_id: int | str | None = None,
    registration_job_id: int | str | None = None,
    route_attempt_no: int | str | None = None,
) -> bool:
    """Add missing durable correlation facts without rewriting existing facts.

    Batch leases are reserved before a concrete registration job takes one.
    Binding later is therefore a separate, idempotent update. Each field uses
    ``COALESCE(current, incoming)`` so repeated bind attempts can only add a
    value and cannot repoint historical traffic to another job.
    """
    values: dict[str, Any] = {
        "account_id": _optional_int(account_id),
        "purpose": str(purpose or "").strip()[:80] or None,
        "operation_task_id": _optional_int(operation_task_id),
        "operation_run_id": _optional_int(operation_run_id),
        "registration_job_id": _optional_int(registration_job_id),
        "route_attempt_no": _optional_int(route_attempt_no),
    }
    values = {key: value for key, value in values.items() if value is not None}
    if not values:
        return False
    record_store.init()
    assignments = [
        f'{postgres_store.quote_identifier(column)} = COALESCE('
        f'{postgres_store.quote_identifier(column)}, %s)'
        for column in values
    ]
    assignments.append(
        f'{postgres_store.quote_identifier("updated_at")} = %s'
    )
    args = list(values.values()) + [_now(), str(lease_id)]
    sql = (
        f'UPDATE {postgres_store.qualified(PROXY_LEASES.name)} '
        f'SET {", ".join(assignments)} '
        f'WHERE {postgres_store.quote_identifier("lease_id")} = %s'
    )
    with postgres_store.connect() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.rowcount > 0


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


def abort(lease_id: str) -> None:
    """Remove a validation reservation after a failed candidate."""
    row_id = _find_lease_row_id(lease_id)
    if row_id is not None:
        record_store.delete_rows(PROXY_LEASES, [row_id])


def active_rows() -> list[dict]:
    return record_store.list_rows(
        PROXY_LEASES,
        where='"state" IN (\'pending\', \'leased\', \'recent\')',
        order_by='"id" DESC',
    )


_PAGE_COLUMNS = (
    "p.id",
    "p.lease_id",
    "p.provider",
    "p.endpoint",
    "p.exit_ip",
    "p.region",
    "p.state",
    "p.acquired_at",
    "p.expires_at",
    "p.recent_until",
    "p.released_at",
    "p.batch_id",
    "p.job_id",
    "p.account_id",
    "p.purpose",
    "p.operation_task_id",
    "p.operation_run_id",
    "p.registration_job_id",
    "p.route_attempt_no",
    "p.release_reason",
    "p.created_at",
    "p.updated_at",
)


def _optional_int(value: int | str | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def _relation_exists(cur, table_name: str) -> bool:
    cur.execute(
        "SELECT to_regclass(%s) AS relation_name",
        (f"{postgres_store.schema_name()}.{table_name}",),
    )
    return bool(cur.fetchone()["relation_name"])


def _page_query(cur, *, view: str) -> tuple[str, list[Any]]:
    """Build a secret-free page projection from PostgreSQL facts.

    The optional joins are discovered from the current test/runtime schema so
    a partially migrated process can still inspect persisted proxy leases.
    No ``proxy_url`` or JSONB payload is selected here.
    """
    columns = list(_PAGE_COLUMNS)
    joins: list[str] = []
    if _relation_exists(cur, "operation_tasks"):
        operation_tasks = postgres_store.qualified("operation_tasks")
        joins.append(
            f"LEFT JOIN {operation_tasks} ot ON ot.id = p.operation_task_id"
        )
        columns.extend(("ot.task_type AS operation_task_type", "ot.status AS operation_task_status"))
    if _relation_exists(cur, "operation_runs"):
        operation_runs = postgres_store.qualified("operation_runs")
        joins.append(
            f"LEFT JOIN {operation_runs} op_run ON op_run.id = p.operation_run_id"
        )
        columns.extend(("op_run.run_no AS operation_run_no", "op_run.status AS operation_run_status"))
    if _relation_exists(cur, "registration_jobs"):
        registration_jobs = postgres_store.qualified("registration_jobs")
        joins.append(
            f"LEFT JOIN {registration_jobs} reg_job ON reg_job.id = p.registration_job_id"
        )
        columns.extend(("reg_job.job_uuid AS registration_job_uuid", "reg_job.status AS registration_job_status"))
    where = ""
    if view == "current":
        where = "WHERE p.state IN ('pending', 'leased', 'recent')"
    elif view != "history":
        raise ValueError("代理租约视图必须是 current 或 history")
    sql = (
        f"SELECT {', '.join(columns)} FROM {postgres_store.qualified(PROXY_LEASES.name)} p "
        f"{' '.join(joins)} {where} ORDER BY p.id DESC LIMIT %s OFFSET %s"
    )
    return sql, []


def _safe_page_row(row: dict) -> dict[str, Any]:
    from core.proxy_provider import mask_endpoint

    out = {key: row.get(key) for key in row.keys() if key not in {"id", "endpoint", "exit_ip"}}
    out["endpoint"] = mask_endpoint(row.get("endpoint"))
    # The page is the only proxy/traffic API allowed to show the complete exit
    # IP.  The selected projection still excludes the credential-bearing URL.
    out["exit_ip"] = row.get("exit_ip")
    out["id"] = row.get("id")
    return out


def list_page(*, view: str = "current", limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
    """Return a persisted, credential-free proxy page projection."""
    record_store.init()
    page_limit = max(1, min(500, int(limit or 200)))
    page_offset = max(0, int(offset or 0))
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        sql, _ = _page_query(cur, view=view)
        cur.execute(sql, (page_limit, page_offset))
        return [_safe_page_row(row) for row in cur.fetchall()]


def _find_lease_row_id(lease_id: str) -> int | None:
    row = record_store.get_row_by(PROXY_LEASES, "lease_id", str(lease_id))
    return int(row["id"]) if row else None


def _lease_row_id(lease_id: str) -> int:
    row_id = _find_lease_row_id(lease_id)
    if row_id is None:
        raise RuntimeError(f"代理租约不存在: {lease_id}")
    return row_id
