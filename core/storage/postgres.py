# -*- coding: utf-8 -*-
"""PostgreSQL-backed storage for JSON-compatible application collections.

PostgreSQL 是唯一事实来源，没有"纯文件模式"回退：DATABASE_URL 缺失或连不上时
调用方应当直接失败，而不是静默改用兼容文件——静默降级会让数据在两份副本之间分叉。
现存的 text/JSON 文件只是兼容导出，以及首次导入时的种子。

所有表都限定在 `TURB_DB_SCHEMA`（默认 public）下，测试通过指向临时 schema 隔离。
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import re
import sys
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from typing import Any

from core.runtime.request_timing import current_request_timing

logger = logging.getLogger('core.postgres_store')
_LOCK = threading.RLock()
_SCHEMA_READY_KEY = ""
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 1.0
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCOPED_DOMAIN = ContextVar("postgres_captured_domain", default=None)
_SCOPED_DEADLINE = ContextVar("postgres_settlement_deadline", default=None)


def database_url() -> str:
    domain = _SCOPED_DOMAIN.get()
    if domain is not None:
        return str(domain.database_url)
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
    domain = _SCOPED_DOMAIN.get()
    if domain is not None:
        return str(domain.permit_schema)
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


_POOLS: dict[tuple, Any] = {}
_POOL_LOCK = threading.RLock()
_SLOW_CHECKOUT_SECONDS = 0.25
_SQL_WAIT_ERRORS = {
    "40P01": "db_deadlock",
    "55P03": "db_lock_unavailable",
    "57014": "db_query_cancelled",
}


def _pool_for(target: str, kwargs: dict):
    """按 (库, 连接参数) 复用连接池。

    行级存储把"一次大写入"换成了"多次小查询"，建连接的成本因此成了大头：
    实测建连接 38ms、真正查询只要 2.4ms。不做池化的话，列表页每渲染一行都要
    重新握手一次 TCP + 认证。
    """
    from psycopg_pool import ConnectionPool
    key = (target, tuple(sorted((k, repr(v)) for k, v in kwargs.items())))
    with _POOL_LOCK:
        pool = _POOLS.get(key)
        if pool is None:
            pool = ConnectionPool(
                target,
                min_size=1,
                max_size=int(os.getenv("TURB_DB_POOL_MAX") or 12),
                timeout=10.0,
                max_idle=300.0,
                kwargs={"connect_timeout": 5, **kwargs},
                open=True,
            )
            _POOLS[key] = pool
    return pool


def connect(url: str | None = None, *, deadline: float | None = None, **kwargs):
    """从连接池借一条连接。用法与 psycopg.connect 相同：`with connect() as conn:`。

    退出 with 时连接归还池子而不是关闭。
    """
    inherited = _SCOPED_DEADLINE.get()
    if inherited is not None:
        deadline = min(float(deadline), float(inherited)) if deadline is not None else float(inherited)
    if deadline is not None and deadline <= time.monotonic():
        raise TimeoutError("数据库结算截止时间已到")
    try:
        import psycopg  # noqa: F401  确保驱动存在，错误信息更直白
        import psycopg_pool  # noqa: F401
    except ImportError as exc:  # pragma: no cover - only possible in incomplete installs
        raise RuntimeError("已配置 DATABASE_URL，但缺少 psycopg/psycopg_pool；请重新安装 requirements.txt") from exc
    target = str(url or database_url()).strip()
    if not target:
        raise RuntimeError("DATABASE_URL 未配置")
    # 挂在唯一的连接出口上：任何代码路径都绕不过这道检查
    _guard_production_database(target)
    pool = _pool_for(target, kwargs)
    if deadline is None:
        return _observed_pool_connection(pool)
    return _deadline_connection(pool, deadline)


def _log_connection_delay(message: str, *args) -> None:
    try:
        logger.warning(message, *args)
    except Exception:
        # 日志处理失败不能替换调用方原本收到的数据库结果。
        pass


@contextmanager
def _observed_pool_connection(pool, **kwargs):
    from psycopg import Error
    from psycopg_pool import PoolTimeout

    started = time.monotonic()
    request_timing = current_request_timing.get()
    checked_out = None
    try:
        with pool.connection(**kwargs) as conn:
            checked_out = time.monotonic()
            if request_timing is not None:
                request_timing.pool_seconds += checked_out - started
            yield conn
    except PoolTimeout:
        if checked_out is None:
            elapsed = time.monotonic() - started
            if request_timing is not None:
                request_timing.pool_seconds += elapsed
            _log_connection_delay("数据库连接池等待超时：code=db_pool_checkout_timeout checkout_ms=%.1f",
                                  elapsed * 1000)
        raise
    except Error as exc:
        diagnostic = _SQL_WAIT_ERRORS.get(exc.sqlstate)
        if checked_out is not None and diagnostic:
            _log_connection_delay(
                "数据库事务异常：code=%s sqlstate=%s checkout_ms=%.1f transaction_ms=%.1f",
                diagnostic, exc.sqlstate, (checked_out - started) * 1000,
                (time.monotonic() - checked_out) * 1000)
        raise
    finally:
        if checked_out is not None and checked_out - started >= _SLOW_CHECKOUT_SECONDS:
            _log_connection_delay("数据库连接池等待较长：code=db_pool_checkout_slow checkout_ms=%.1f",
                                  (checked_out - started) * 1000)


@contextmanager
def _deadline_connection(pool, deadline: float):
    """Bound pool checkout and SQL waits without changing pooled connection keys.

    A driver call already in uninterruptible I/O is still owned by its caller.
    This helper never spawns a detached thread or claims to cancel that call.
    """
    remaining = float(deadline) - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("数据库结算截止时间已到")
    with _observed_pool_connection(pool, timeout=remaining) as conn:
        with conn.cursor() as cur:
            _apply_deadline(cur, deadline)
        yield _DeadlineConnection(conn, deadline)


class _DeadlineConnection:
    """Transparent scope wrapper; each SQL command gets the remaining budget."""
    def __init__(self, connection, deadline):
        self._connection = connection
        self._deadline = deadline

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def cursor(self, *args, **kwargs):
        return _DeadlineCursor(self, self._connection.cursor(*args, **kwargs), self._deadline)


class _DeadlineCursor:
    def __init__(self, connection, cursor, deadline):
        self.connection = connection
        self._cursor = cursor
        self._deadline = deadline

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self._cursor.__exit__(*args)

    def __iter__(self):
        return iter(self._cursor)

    def execute(self, *args, **kwargs):
        _apply_deadline(self._cursor, self._deadline)
        self._cursor.execute(*args, **kwargs)
        return self

    def executemany(self, *args, **kwargs):
        _apply_deadline(self._cursor, self._deadline)
        self._cursor.executemany(*args, **kwargs)
        return self


def _apply_deadline(cur, deadline: float) -> None:
    remaining = float(deadline) - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("数据库结算截止时间已到")
    milliseconds = max(1, int(remaining * 1000))
    cur.execute(
        "SELECT set_config('statement_timeout', %s, true), "
        "set_config('lock_timeout', %s, true)",
        (str(milliseconds), str(milliseconds)),
    )


def connect_dedicated(url: str | None = None):
    """Open an owner-held session; caller closes it, never returns it to a pool.

    Session advisory ownership cannot survive a pooled connection checkout.
    Preserve the ordinary database/environment guards and the test schema guard;
    the bounded statement/network settings complement the owner's watchdog.
    """
    target = str(url or database_url()).strip()
    if not target:
        raise RuntimeError("DATABASE_URL 未配置")
    _guard_production_database(target)
    _guard_production_schema()
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - incomplete installation
        raise RuntimeError("缺少 psycopg；请重新安装 requirements.txt") from exc
    return psycopg.connect(
        target, autocommit=True, connect_timeout=5,
        application_name="turb-execution-owner",
        options="-c statement_timeout=2000 -c idle_in_transaction_session_timeout=2000",
        keepalives=1, keepalives_idle=5, keepalives_interval=1, keepalives_count=2,
        tcp_user_timeout=5000,
    )


@atexit.register
def close_pools() -> None:
    """关闭所有连接池。测试销毁临时 schema、或进程退出前调用。"""
    with _POOL_LOCK:
        for pool in _POOLS.values():
            try:
                pool.close()
            except Exception:
                pass
        _POOLS.clear()


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
    from core.storage.task_query_context import readonly_task_query

    if not readonly_task_query():
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
