# -*- coding: utf-8 -*-
"""PostgreSQL 运行配置仓库：所有原始字符串及历史值均以 Fernet 密文保存。"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

import psycopg
from cryptography.fernet import Fernet, InvalidToken
from psycopg.rows import dict_row
from psycopg_pool import PoolTimeout

from core import postgres_store

_CURRENT_CONNECTION: ContextVar[object | None] = ContextVar("runtime_config_connection", default=None)
_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_LOCK_NAME = "runtime-config-write"


class RuntimeConfigStoreError(RuntimeError):
    """仅暴露稳定错误类别，禁止携带原配置或数据库连接信息。"""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"运行配置存储失败：{code}")


@contextmanager
def _database_errors() -> Iterator[None]:
    try:
        yield
    except (psycopg.Error, PoolTimeout) as exc:
        code = f"database_{getattr(exc, 'sqlstate', None) or type(exc).__name__}"
        raise RuntimeConfigStoreError(code) from None


@contextmanager
def _connection(conn=None):
    selected = conn if conn is not None else _CURRENT_CONNECTION.get()
    if selected is not None:
        with _database_errors():
            yield selected
        return
    try:
        connection_context = postgres_store.connect()
    except Exception:
        raise RuntimeConfigStoreError("database_unavailable") from None
    with _database_errors(), connection_context as own:
        yield own


def _cipher() -> Fernet:
    key = str(os.getenv("TURB_CONFIG_ENCRYPTION_KEY") or "").strip()
    if not key:
        raise RuntimeConfigStoreError("encryption_key_missing")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeError):
        raise RuntimeConfigStoreError("encryption_key_invalid") from None


def _decrypt(cipher: Fernet, encrypted: str) -> str:
    try:
        return cipher.decrypt(encrypted.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError, AttributeError):
        raise RuntimeConfigStoreError("decryption_failed") from None


def _encrypt(cipher: Fernet, raw: str) -> str:
    try:
        return cipher.encrypt(raw.encode("utf-8")).decode("ascii")
    except (ValueError, UnicodeError):
        raise RuntimeConfigStoreError("encryption_failed") from None


def _metadata(conn) -> dict | None:
    table = postgres_store.qualified("runtime_config_meta")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT to_regclass(%s) AS relation", (table,))
        if cur.fetchone()["relation"] is None:
            return None
        cur.execute(f"SELECT active, revision FROM {table} WHERE id = 1")
        return cur.fetchone()


def is_active(*, conn=None) -> bool:
    """只查激活标记，不依赖主密钥、不创建任何表。"""
    with _connection(conn) as current:
        metadata = _metadata(current)
        return bool(metadata and metadata["active"])


def current_revision(*, conn=None) -> int:
    """缺表或尚无元信息时版本为零。"""
    with _connection(conn) as current:
        metadata = _metadata(current)
        return int(metadata["revision"]) if metadata else 0


def read_values(*, conn=None) -> dict[str, str] | None:
    """未激活返回 None；已激活时任何密钥或数据库异常都明确失败。"""
    with _connection(conn) as current:
        metadata = _metadata(current)
        if not metadata or not metadata["active"]:
            return None
        cipher = _cipher()
        table = postgres_store.qualified("runtime_config_values")
        with current.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT key, value_encrypted FROM {table} ORDER BY key")
            return {row["key"]: _decrypt(cipher, row["value_encrypted"]) for row in cur.fetchall()}


def _require_transaction(conn) -> None:
    if conn.autocommit:
        raise RuntimeConfigStoreError("transaction_required")


def _lock(conn) -> None:
    _require_transaction(conn)
    # schema 之间相互独立；与当前运行配置的所有写入进程共用同一把事务锁。
    key = f"{_LOCK_NAME}:{postgres_store.schema_name()}"
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (key,))


@contextmanager
def transaction():
    """持跨进程写锁，并让 reload 等嵌套调用读到同一未提交候选。"""
    existing = _CURRENT_CONNECTION.get()
    if existing is not None:
        yield existing
        return
    with _connection() as conn:
        _lock(conn)
        token = _CURRENT_CONNECTION.set(conn)
        try:
            yield conn
        finally:
            _CURRENT_CONNECTION.reset(token)


def ensure_tables(conn) -> None:
    """仅显式写入/迁移入口建表；正常读取不会触发 DDL。"""
    _require_transaction(conn)
    postgres_store._guard_production_schema()
    with _database_errors(), conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {postgres_store.quote_identifier(postgres_store.schema_name())}")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {postgres_store.qualified('runtime_config_meta')} (
                id SMALLINT PRIMARY KEY CHECK (id = 1),
                active BOOLEAN NOT NULL DEFAULT FALSE,
                revision BIGINT NOT NULL DEFAULT 0 CHECK (revision >= 0)
            )
        """)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {postgres_store.qualified('runtime_config_values')} (
                key TEXT PRIMARY KEY,
                value_encrypted TEXT NOT NULL,
                updated_revision BIGINT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {postgres_store.qualified('runtime_config_history')} (
                revision BIGINT NOT NULL,
                key TEXT NOT NULL,
                old_value_encrypted TEXT,
                new_value_encrypted TEXT NOT NULL,
                source TEXT NOT NULL,
                changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (revision, key)
            )
        """)
        cur.execute(f"INSERT INTO {postgres_store.qualified('runtime_config_meta')} (id) VALUES (1) ON CONFLICT DO NOTHING")


def write_values(updates, *, conn=None, activate=False, source="webui") -> list[str]:
    """原子合并显式字符串；相同原值不会增加版本或历史。"""
    if not isinstance(updates, dict) or any(
        not isinstance(key, str) or not _KEY_PATTERN.fullmatch(key) or not isinstance(value, str)
        for key, value in updates.items()
    ):
        raise RuntimeConfigStoreError("invalid_updates")
    if not isinstance(source, str) or not _SOURCE_PATTERN.fullmatch(source):
        raise RuntimeConfigStoreError("invalid_source")
    cipher = _cipher()
    if conn is None and _CURRENT_CONNECTION.get() is None:
        with transaction() as current:
            return write_values(updates, conn=current, activate=activate, source=source)
    with _connection(conn) as current:
        _lock(current)
        ensure_tables(current)
        values_table = postgres_store.qualified("runtime_config_values")
        meta_table = postgres_store.qualified("runtime_config_meta")
        history_table = postgres_store.qualified("runtime_config_history")
        with current.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT active, revision FROM {meta_table} WHERE id = 1 FOR UPDATE")
            metadata = cur.fetchone()
            cur.execute(f"SELECT key, value_encrypted FROM {values_table}")
            encrypted = {row["key"]: row["value_encrypted"] for row in cur.fetchall()}
            # 激活前也核验全部现存密文，避免用另一把密钥制造混合配置。
            previous = {key: _decrypt(cipher, value) for key, value in encrypted.items()}
            changed = sorted(key for key, value in updates.items() if key not in previous or value != previous[key])
            becoming_active = bool(activate) and not metadata["active"]
            if not changed and not becoming_active:
                return []
            revision = int(metadata["revision"]) + 1
            for key in changed:
                ciphertext = _encrypt(cipher, updates[key])
                cur.execute(
                    f"INSERT INTO {history_table} (revision, key, old_value_encrypted, new_value_encrypted, source) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (revision, key, encrypted.get(key), ciphertext, source),
                )
                cur.execute(
                    f"INSERT INTO {values_table} (key, value_encrypted, updated_revision) VALUES (%s, %s, %s) "
                    "ON CONFLICT (key) DO UPDATE SET value_encrypted = EXCLUDED.value_encrypted, "
                    "updated_revision = EXCLUDED.updated_revision, updated_at = now()",
                    (key, ciphertext, revision),
                )
            cur.execute(
                f"UPDATE {meta_table} SET active = active OR %s, revision = %s WHERE id = 1",
                (bool(activate), revision),
            )
            return changed
