# -*- coding: utf-8 -*-
"""PostgreSQL-backed storage for JSON-compatible application collections.

PostgreSQL 是唯一事实来源，没有"纯文件模式"回退：DATABASE_URL 缺失或连不上时
调用方应当直接失败，而不是静默改用兼容文件——静默降级会让数据在两份副本之间分叉。
现存的 text/JSON 文件只是兼容导出，以及首次导入时的种子。

所有表都限定在 `TURB_DB_SCHEMA`（默认 public）下，测试通过指向临时 schema 隔离。
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
from copy import deepcopy
from typing import Any

logger = logging.getLogger(__name__)
_LOCK = threading.RLock()
_SCHEMA_READY_KEY = ""
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 1.0
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def database_url() -> str:
    # 在读取 env 的唯一入口收口加载 .env：`ensure_loaded()` 有 _LOADED 标记，重复
    # 调用几乎无成本。否则每个调用方都得记得"先 import config 再用存储层"。
    try:
        from config.env_loader import ensure_loaded
        ensure_loaded()
    except Exception:
        pass
    return str(os.getenv("DATABASE_URL") or "").strip()


def enabled() -> bool:
    return bool(database_url())


# 生产库名单。默认拒绝连接，生产环境必须在自己的 .env 里显式声明
# TURB_ALLOW_PRODUCTION_DB=1 才放行。
#
# 为什么是"默认拒绝"而不是"默认允许"：这条护栏的由来是一次真实事故——未完成的
# 存储层代码被线上服务加载，把 361 条注册任务写成了 5 条。默认拒绝意味着任何新
# 建的 worktree、新 clone、临时脚本天然连不上生产库，忘记配置的后果是启动报错，
# 而不是悄悄写坏真实数据。
_PRODUCTION_DATABASES = {"turb_console"}


def _database_name(url: str) -> str:
    from urllib.parse import urlparse
    try:
        return (urlparse(url).path or "").lstrip("/").strip()
    except Exception:
        return ""


def _guard_production_database(url: str) -> None:
    name = _database_name(url)
    if name not in _PRODUCTION_DATABASES:
        return
    if os.getenv("TURB_ALLOW_PRODUCTION_DB") == "1":
        return
    raise SystemExit(
        f"拒绝连接生产数据库 {name!r}：当前环境没有声明允许。\n"
        "生产环境请在 .env 中加上：TURB_ALLOW_PRODUCTION_DB=1\n"
        "开发/测试请指向独立库，例如：DATABASE_URL=...:55432/turb_dev"
    )


def schema_name() -> str:
    """当前 PostgreSQL schema。测试通过 TURB_DB_SCHEMA 指向临时 schema 做隔离。"""
    return str(os.getenv("TURB_DB_SCHEMA") or "public").strip() or "public"


def _guard_production_schema() -> None:
    """测试进程严禁碰生产 schema。

    这不是"判断数据库是否可用"（那种嗅探会导致静默降级、两份副本分叉），
    而是一道只会响亮报错的护栏：测试要么显式指向临时 schema，要么直接失败。
    """
    if "unittest" not in sys.modules:
        return
    if schema_name() == "public":
        raise RuntimeError(
            "测试进程不允许使用 public schema（会写坏真实账号数据）。\n"
            "请让用到数据库的测试继承 tests.support_pg.PostgresTestCase，"
            "或运行测试时设置 TURB_DB_SCHEMA=test_xxx。"
        )


def quote_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"非法 PostgreSQL 标识符: {name!r}")
    return f'"{name}"'


def qualified(table: str) -> str:
    """把表名限定到当前 schema，供本模块与 record_store 共用。"""
    return f"{quote_identifier(schema_name())}.{quote_identifier(table)}"


def require_ready() -> None:
    """启动自检：DATABASE_URL 缺失或库连不上就直接终止进程。

    本项目不再支持纯文件模式。让它在启动时响亮失败，好过运行中静默把数据写丢。
    """
    url = database_url()
    if not url:
        raise SystemExit(
            "DATABASE_URL 未配置。本项目以 PostgreSQL 为唯一主存储，不再支持纯文件模式。\n"
            "请先启动共享实例并在 .env 配置 DATABASE_URL：\n"
            "  /Users/lihongwei/code/personal/shared-services/postgres/postgres.sh start"
        )
    try:
        ensure_schema()
    except Exception as exc:
        raise SystemExit(f"PostgreSQL 不可用（{type(exc).__name__}: {exc}）；请检查 DATABASE_URL 与共享实例状态") from exc


def connect(url: str | None = None, **kwargs):
    """Open a PostgreSQL connection for storage modules."""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - only possible in incomplete installs
        raise RuntimeError("已配置 DATABASE_URL，但缺少 psycopg；请重新安装 requirements.txt") from exc
    target = str(url or database_url()).strip()
    if not target:
        raise RuntimeError("DATABASE_URL 未配置")
    # 挂在唯一的连接出口上：任何代码路径都绕不过这道检查
    _guard_production_database(target)
    return psycopg.connect(target, connect_timeout=5, **kwargs)


def _connect():
    return connect()


def ensure_schema() -> None:
    global _SCHEMA_READY_KEY
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL 未配置")
    _guard_production_schema()
    ready_key = f"{url}::{schema_name()}"
    with _LOCK:
        if _SCHEMA_READY_KEY == ready_key:
            return
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(schema_name())}")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {qualified("app_collections")} (
                    name text PRIMARY KEY,
                    payload jsonb NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
        _SCHEMA_READY_KEY = ready_key


def _cache_key(name: str) -> str:
    return f"{schema_name()}::{name}"


def load_collection(name: str) -> tuple[bool, Any]:
    ensure_schema()
    key = _cache_key(name)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and time.monotonic() - cached[0] <= _CACHE_TTL_SECONDS:
            return True, deepcopy(cached[1])
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT payload FROM {qualified('app_collections')} WHERE name = %s", (name,))
        row = cur.fetchone()
    if row is None:
        return False, None
    with _LOCK:
        _CACHE[key] = (time.monotonic(), row[0])
    return True, deepcopy(row[0])


def save_collection(name: str, payload: Any) -> None:
    ensure_schema()
    serialized = json.dumps(payload, ensure_ascii=False)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {qualified("app_collections")}(name, payload, updated_at)
            VALUES (%s, %s::jsonb, now())
            ON CONFLICT (name) DO UPDATE
            SET payload = EXCLUDED.payload, updated_at = now()
            """,
            (name, serialized),
        )
    with _LOCK:
        _CACHE[_cache_key(name)] = (time.monotonic(), deepcopy(payload))


def reset_cache() -> None:
    """丢弃集合读缓存。外部直接改库后调用。

    不重置 `_SCHEMA_READY_KEY`：它已经按 `url::schema` 做键，切 schema 会自动失效，
    没必要每次都重跑一遍建表 DDL。
    """
    with _LOCK:
        _CACHE.clear()


def healthcheck() -> dict:
    if not enabled():
        return {"enabled": False, "ok": False, "error": "DATABASE_URL 未配置"}
    try:
        ensure_schema()
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT current_database(), current_user, count(*) FROM {qualified('app_collections')}")
            database, user, collections = cur.fetchone()
        return {"enabled": True, "ok": True, "database": database, "user": user, "collections": collections}
    except Exception as exc:
        return {"enabled": True, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
