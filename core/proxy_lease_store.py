# -*- coding: utf-8 -*-
"""PostgreSQL-backed cross-process coordination for 1024Proxy leases."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from core import record_store


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


def _find_lease_row_id(lease_id: str) -> int | None:
    row = record_store.get_row_by(PROXY_LEASES, "lease_id", str(lease_id))
    return int(row["id"]) if row else None


def _lease_row_id(lease_id: str) -> int:
    row_id = _find_lease_row_id(lease_id)
    if row_id is None:
        raise RuntimeError(f"代理租约不存在: {lease_id}")
    return row_id
