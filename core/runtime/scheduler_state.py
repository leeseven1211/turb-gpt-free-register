# -*- coding: utf-8 -*-
"""Persisted scheduler cadence, with per-task transactional updates.

The existing JSON collection remains readable. Each mutation locks its task
inside the same PostgreSQL transaction, and updates only that task's JSON path.
An unknown database state never authorizes a new managed periodic cycle.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timedelta

from core.runtime.periodic import execution_allowed
from core.storage import postgres as postgres_store

logger = logging.getLogger("core.scheduler_state")
_COLLECTION = "scheduler_state"
_POLL_CAP_SECONDS = 60.0


def _task_key(task: str) -> str:
    key = str(task)
    if not key:
        raise ValueError("scheduler_task_required")
    return key


def _lock_key(task: str) -> int:
    namespace = json.dumps(
        ["turb.scheduler_state.v1", postgres_store.schema_name(), task],
        ensure_ascii=False, separators=(",", ":"),
    )
    return int.from_bytes(hashlib.sha256(namespace.encode()).digest()[:8], "big", signed=True)


def _read_entry(cur, task: str) -> dict:
    cur.execute(
        f"SELECT payload -> %s, jsonb_typeof(payload) "
        f"FROM {postgres_store.qualified('app_collections')} WHERE name = %s",
        (task, _COLLECTION),
    )
    row = cur.fetchone()
    if row is None:
        return {}
    if row[1] != "object":
        raise ValueError("scheduler_state_invalid")
    entry = row[0]
    if entry is None:
        return {}
    if not isinstance(entry, dict):
        raise ValueError("scheduler_entry_invalid")
    return dict(entry)


def last_run_at(task: str) -> datetime | None:
    task = _task_key(task)
    from core.storage.task_query_context import readonly_task_query

    if not readonly_task_query():
        postgres_store.ensure_schema()
    # No collection cache: a reset/mark in another process must be visible.
    with postgres_store.connect() as conn, conn.cursor() as cur:
        entry = _read_entry(cur, task)
    raw = str(entry.get("last_run_at") or "").strip()
    return datetime.fromisoformat(raw) if raw else None


def mark_ran(task: str) -> None:
    task = _task_key(task)
    postgres_store.ensure_schema()
    with postgres_store.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_lock_key(task),))
        entry = _read_entry(cur, task)
        entry["last_run_at"] = datetime.now().isoformat(timespec="seconds")
        entry["run_count"] = int(entry.get("run_count") or 0) + 1
        cur.execute(
            f"INSERT INTO {postgres_store.qualified('app_collections')}(name, payload) "
            "VALUES (%s, '{}'::jsonb) ON CONFLICT (name) DO NOTHING",
            (_COLLECTION,),
        )
        # SQL reads the current row after any row-lock wait, preserving another
        # task's write. Never serialize and replace the whole collection here.
        cur.execute(
            f"UPDATE {postgres_store.qualified('app_collections')} "
            "SET payload = jsonb_set(payload, %s::text[], %s::jsonb, true), updated_at = now() "
            "WHERE name = %s",
            ([task], json.dumps(entry, ensure_ascii=False), _COLLECTION),
        )


def reset(task: str) -> None:
    task = _task_key(task)
    postgres_store.ensure_schema()
    with postgres_store.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_lock_key(task),))
        # Invalid storage is an error, never an implicit destructive reset.
        _read_entry(cur, task)
        cur.execute(
            f"UPDATE {postgres_store.qualified('app_collections')} "
            "SET payload = payload - %s, updated_at = now() WHERE name = %s",
            (task, _COLLECTION),
        )


def _remaining(previous: datetime | None, interval_seconds: float) -> float:
    interval = max(0.0, float(interval_seconds))
    if previous is None:
        return 0.0
    elapsed = (datetime.now(tz=previous.tzinfo) - previous).total_seconds()
    # Preserve the established backward-clock policy.
    return 0.0 if elapsed < 0 else max(0.0, interval - elapsed)


def seconds_until_due(task: str, interval_seconds: float) -> float:
    return _remaining(last_run_at(task), interval_seconds)


def describe(task: str, interval_seconds: float) -> dict:
    result = {"task": str(task), "interval_seconds": int(interval_seconds)}
    try:
        previous = last_run_at(task)
        remaining = _remaining(previous, interval_seconds)
    except Exception:
        return {**result, "last_run_at": None, "next_run_at": None,
                "seconds_until_due": None, "state_available": False,
                "error_code": "scheduler_state_unavailable"}
    return {
        **result,
        "last_run_at": previous.isoformat(timespec="seconds") if previous else None,
        "next_run_at": (datetime.now() + timedelta(seconds=remaining)).isoformat(timespec="seconds"),
        "seconds_until_due": int(remaining),
        "state_available": True,
        "error_code": None,
    }


def run_periodic(
    *, task: str, label: str, work, enabled, interval_seconds,
    initial_delay_seconds: float = 60.0,
    stop: threading.Event | None = None,
    lifecycle=None,
) -> None:
    """Read current configuration each cycle and obey managed execution admission."""
    ticker = stop if stop is not None else threading.Event()
    if ticker.wait(max(0.0, float(initial_delay_seconds))):
        return
    # If persisting completion fails, retry that write before another cycle.
    # This is not a replacement for durable state and never grants permission
    # on restart. It prevents a transient write failure from hammering services.
    pending_completion = False
    local_not_before = 0.0
    while not ticker.is_set():
        try:
            if pending_completion:
                mark_ran(task)
                pending_completion = False
            if not execution_allowed() or not enabled():
                if ticker.wait(_POLL_CAP_SECONDS):
                    return
                continue
            interval = max(0.0, float(interval_seconds()))
            remaining = max(
                seconds_until_due(task, interval),
                local_not_before - time.monotonic(),
            )
            if remaining > 0:
                if lifecycle:
                    lifecycle.record_error(None)
                if ticker.wait(min(remaining, _POLL_CAP_SECONDS)):
                    return
                continue
            # Admission can close while PostgreSQL or configuration was read.
            if ticker.is_set() or not execution_allowed():
                if ticker.wait(_POLL_CAP_SECONDS):
                    return
                continue
            if lifecycle:
                lifecycle.work_started()
            try:
                result = work()
                logger.info("[%s] scheduled run: %s", label, result)
            except Exception:
                logger.exception("[%s] scheduled cycle failed", label)
                if lifecycle:
                    lifecycle.record_error("scheduler_cycle_failed")
            finally:
                if lifecycle:
                    lifecycle.work_finished()
            # Failed cycles also advance cadence. Record even if stop was
            # requested during the work; join must wait for this final write.
            local_not_before = time.monotonic() + max(interval, 0.05)
            pending_completion = True
            mark_ran(task)
            pending_completion = False
        except Exception:
            logger.exception("[%s] scheduler state or loop unavailable", label)
            if lifecycle:
                lifecycle.record_error("scheduler_state_unavailable")
            if ticker.wait(_POLL_CAP_SECONDS):
                return
