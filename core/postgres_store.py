# -*- coding: utf-8 -*-
"""PostgreSQL-backed storage for JSON-compatible application collections.

The existing text/JSON files remain compatibility exports. When DATABASE_URL is
configured, reads prefer PostgreSQL and writes commit there before refreshing the
compatibility file. A missing database row is bootstrapped from the existing file.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from copy import deepcopy
from typing import Any

logger = logging.getLogger(__name__)
_LOCK = threading.RLock()
_SCHEMA_READY_URL = ""
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 1.0


def database_url() -> str:
    if "unittest" in sys.modules and os.getenv("TURB_ALLOW_DATABASE_IN_TESTS") != "1":
        return ""
    return str(os.getenv("DATABASE_URL") or "").strip()


def enabled() -> bool:
    return bool(database_url())


def _connect():
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - only possible in incomplete installs
        raise RuntimeError("已配置 DATABASE_URL，但缺少 psycopg；请重新安装 requirements.txt") from exc
    return psycopg.connect(database_url(), connect_timeout=5)


def ensure_schema() -> None:
    global _SCHEMA_READY_URL
    if not enabled():
        return
    url = database_url()
    with _LOCK:
        if _SCHEMA_READY_URL == url:
            return
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_collections (
                    name text PRIMARY KEY,
                    payload jsonb NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
        _SCHEMA_READY_URL = url


def load_collection(name: str) -> tuple[bool, Any]:
    if not enabled():
        return False, None
    ensure_schema()
    with _LOCK:
        cached = _CACHE.get(name)
        if cached and time.monotonic() - cached[0] <= _CACHE_TTL_SECONDS:
            return True, deepcopy(cached[1])
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT payload FROM app_collections WHERE name = %s", (name,))
        row = cur.fetchone()
    if row is None:
        return False, None
    with _LOCK:
        _CACHE[name] = (time.monotonic(), row[0])
    return True, deepcopy(row[0])


def save_collection(name: str, payload: Any) -> None:
    if not enabled():
        return
    ensure_schema()
    serialized = json.dumps(payload, ensure_ascii=False)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_collections(name, payload, updated_at)
            VALUES (%s, %s::jsonb, now())
            ON CONFLICT (name) DO UPDATE
            SET payload = EXCLUDED.payload, updated_at = now()
            """,
            (name, serialized),
        )
    with _LOCK:
        _CACHE[name] = (time.monotonic(), deepcopy(payload))


def healthcheck() -> dict:
    if not enabled():
        return {"enabled": False, "ok": False, "error": "DATABASE_URL 未配置"}
    try:
        ensure_schema()
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, count(*) FROM app_collections")
            database, user, collections = cur.fetchone()
        return {"enabled": True, "ok": True, "database": database, "user": user, "collections": collections}
    except Exception as exc:
        return {"enabled": True, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
