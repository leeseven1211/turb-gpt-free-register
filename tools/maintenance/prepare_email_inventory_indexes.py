#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查或在线预建邮箱库存资格查询的 v2 表达式索引。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from dotenv.main import DotEnv


class IndexPreparationError(RuntimeError):
    """维护工具错误，只保留稳定分类。"""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _database_name(url: str) -> str:
    return (urlparse(str(url)).path or "").lstrip("/").strip()


def _bootstrap_values(source_root: Path) -> dict[str, str]:
    """按现有 bootstrap 规则读配置，工具不写入任何配置文件。"""
    configured = str(os.getenv("TURB_BOOTSTRAP_ENV_FILE") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            raise IndexPreparationError("bootstrap_env_file_absolute_required")
        path = path.resolve()
    else:
        path = (source_root / ".env").resolve()
    if not path.is_file():
        raise IndexPreparationError("bootstrap_env_file_missing")
    return {
        str(key): str(value)
        for key, value in DotEnv(
            dotenv_path=path,
            encoding="utf-8",
            interpolate=True,
            override=False,
        ).dict().items()
        if value is not None
    }


@contextmanager
def _target_environment(values: dict[str, str]):
    keys = ("DATABASE_URL", "TURB_ALLOW_PRODUCTION_DB", "TURB_DB_SCHEMA", "PYTHON_DOTENV_DISABLED")
    missing = object()
    previous = {key: os.environ.get(key, missing) for key in keys}
    effective = dict(values)
    for key in keys:
        if key == "PYTHON_DOTENV_DISABLED":
            value = "1"
        elif key in os.environ:
            # 与 load_env(override=False) 一致：显式进程值优先于 bootstrap 文件。
            value = os.environ[key]
            effective[key] = value
        else:
            value = values.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(value)
    try:
        yield effective
    finally:
        for key, value in previous.items():
            if value is missing:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _connect(values: dict[str, str], *, readonly: bool = False):
    url = str(values.get("DATABASE_URL") or "").strip()
    if not url:
        raise IndexPreparationError("database_url_missing")
    from core.storage import postgres as postgres_store

    postgres_store._guard_production_database(url)
    options = "-c statement_timeout=30min -c lock_timeout=5s"
    if readonly:
        options += " -c default_transaction_read_only=on"
    return psycopg.connect(
        url,
        autocommit=True,
        connect_timeout=5,
        application_name="turb-email-inventory-indexes",
        options=options,
    )


def _validate_target(conn, values: dict[str, str]) -> None:
    from core.storage import postgres as postgres_store

    expected_database = _database_name(values["DATABASE_URL"])
    expected_schema = str(values.get("TURB_DB_SCHEMA") or "public").strip() or "public"
    with conn.cursor() as cur:
        cur.execute(
            "SELECT current_database() AS database, "
            "EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s) AS schema_exists",
            (expected_schema,),
        )
        row = cur.fetchone()
    current_database = row["database"] if isinstance(row, dict) else row[0]
    schema_exists = row["schema_exists"] if isinstance(row, dict) else row[1]
    if current_database != expected_database:
        raise IndexPreparationError("target_database_mismatch")
    if not schema_exists:
        raise IndexPreparationError("target_schema_missing")
    if postgres_store.schema_name() != expected_schema:
        raise IndexPreparationError("target_schema_mismatch")


def _migration_marker(conn, version: int) -> bool:
    from core.storage import postgres as postgres_store

    table = postgres_store.qualified("record_store_schema_migrations")
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (table,))
        if cur.fetchone()[0] is None:
            return False
        cur.execute(f"SELECT 1 FROM {table} WHERE version = %s", (version,))
        return cur.fetchone() is not None


def _mark_v2(conn) -> None:
    from core.storage import postgres as postgres_store

    table = postgres_store.qualified("record_store_schema_migrations")
    with conn.cursor() as cur:
        cur.execute(f"CREATE TABLE IF NOT EXISTS {table} (version INTEGER PRIMARY KEY)")
        cur.execute(f"INSERT INTO {table} (version) VALUES (2) ON CONFLICT DO NOTHING")


def _session_lock(conn):
    from core.storage import postgres as postgres_store

    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
            (f"record-store-schema:{postgres_store.schema_name()}",),
        )
        row = cur.fetchone()
    return bool(row[0] if not isinstance(row, dict) else row["pg_try_advisory_lock"])


def _session_unlock(conn):
    from core.storage import postgres as postgres_store

    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
            (f"record-store-schema:{postgres_store.schema_name()}",),
        )


def _try_online_gate(conn) -> bool:
    from core.storage import postgres as postgres_store

    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
            (f"record-store-schema-online-gate:{postgres_store.schema_name()}",),
        )
        row = cur.fetchone()
    return bool(row[0] if not isinstance(row, dict) else row["pg_try_advisory_lock"])


def _unlock_online_gate(conn) -> None:
    from core.storage import postgres as postgres_store

    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
            (f"record-store-schema-online-gate:{postgres_store.schema_name()}",),
        )


def run(source_root: Path | str, *, apply: bool = False) -> dict:
    root = Path(source_root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    values = _bootstrap_values(root)
    with _target_environment(values) as effective_values:
        from core.storage.email import inventory_indexes

        with _connect(effective_values, readonly=not apply) as conn:
            _validate_target(conn, effective_values)
            if not apply:
                return inventory_indexes.summarize_indexes(conn)
            if not _migration_marker(conn, 1):
                raise IndexPreparationError("record_schema_v1_required")
            if not _try_online_gate(conn):
                raise IndexPreparationError("schema_migration_busy")
            if not _session_lock(conn):
                _unlock_online_gate(conn)
                raise IndexPreparationError("schema_migration_busy")
            try:
                result = inventory_indexes.ensure_indexes(conn, concurrent=True, analyze=True)
                _mark_v2(conn)
            finally:
                _session_unlock(conn)
                _unlock_online_gate(conn)
            result.update({"ok": True, "schema": str(effective_values.get("TURB_DB_SCHEMA") or "public")})
            return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path.cwd(), help="部署源码目录")
    parser.add_argument("--apply", action="store_true", help="在线逐个并发创建缺失索引并标记 v2")
    args = parser.parse_args(argv)
    try:
        result = run(args.source_root, apply=args.apply)
    except IndexPreparationError as exc:
        print(json.dumps({"ok": False, "error_code": exc.code}, ensure_ascii=False))
        return 1
    except Exception as exc:
        payload = {
            "ok": False,
            "error_code": str(getattr(exc, "code", "") or "index_prepare_" + type(exc).__name__.lower()),
        }
        index_name = getattr(exc, "index_name", None)
        if index_name:
            payload["index"] = str(index_name)
        print(json.dumps(payload, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
