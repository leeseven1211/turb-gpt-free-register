"""Durable cache-key acceptance; file leases stay with the execution handler."""
from __future__ import annotations

from contextlib import nullcontext
import re

from core.storage import records
from core.storage.operations import common, schema

_KEY = re.compile(r"^[0-9a-f]{64}$")
_ACTIVE = "'queued','running','cancelling','settling','stopping','waiting'"


def _key(value):
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise ValueError("invalid_sentinel_cache_key")
    return value


def active_check(cache_key, *, conn=None):
    cache_key = _key(cache_key)
    if conn is None:
        schema.init_operation_schema()
    with (nullcontext(conn) if conn is not None else common._connect()) as active, active.cursor() as cur:
        # Filter the Run state, not a potentially lagging Task projection.
        # Read any active run for this cache, including a queued explicit retry.
        cur.execute(f"""
            SELECT r.task_id, r.id AS run_id, r.status
            FROM {common._table('operation_tasks')} AS t
            JOIN {common._table('operation_runs')} AS r ON r.task_id = t.id
            WHERE t.task_type = %s AND r.data->>'cache_key' = %s
              AND r.status IN ({_ACTIVE})
            ORDER BY r.id DESC LIMIT 1
        """, ("sentinel_maintenance_check", cache_key))
        row = cur.fetchone()
        return dict(row) if row else None


def request_check(cache_key, *, create):
    """Serialize one explicit acceptance per trusted cache; no new run on replay."""
    cache_key = _key(cache_key)
    schema.init_operation_schema()
    with common._connect() as conn:
        records.advisory_xact_lock(conn, "sentinel-maintenance:" + cache_key)
        previous = active_check(cache_key, conn=conn)
        if previous is not None:
            return {"accepted": True, "reused": True, **previous}
        result = create(conn)
        if not result.get("accepted") or not result.get("task_id") or not result.get("run_id"):
            raise RuntimeError("sentinel_request_not_accepted")
        return result
