# -*- coding: utf-8 -*-
"""行级记录存储。

与 `core.postgres_store` 的对照关系：
    postgres_store  —— 一个集合 = app_collections 里的一行 JSONB blob
    record_store    —— 一条业务记录 = 一行，可行级 UPDATE、可跨进程原子抢占

blob 方案的代价是改一个字段要读全量、写全量：并发下互相覆盖，`threading.RLock`
只保进程内，CLI 与 WebUI 是两个进程，抢占语义实际失效。本模块把四个核心集合
换成真正的表来解决这两件事。

字段策略是"提升列 + JSONB"混合：账号有 85 个字段且高度稀疏（live_check_* 只覆盖
11/233，codex_agent_* 只有 1 条），还在持续新增。全部拆成列会让"加个功能"变成
"写一次 migration"，所以只把进 WHERE / ORDER BY / 抢占条件的字段提升为真列，
其余留在 `data jsonb` 里。

schema 跟随 `postgres_store.schema_name()`（TURB_DB_SCHEMA，默认 public），
测试因此可以指向临时 schema。
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from core import postgres_store

_LOCK = threading.RLock()
_READY_KEY = ""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ============================================================
# 表定义
# ============================================================

@dataclass(frozen=True)
class TableSpec:
    """一张表的结构。

    promoted: 列名 -> SQL 类型。这些列同时也是 payload 里的同名字段，读出来时
              会合并回扁平 dict，调用方感知不到拆分。
    derived:  列名 -> (来源字段, 计算函数)。用于 payload 里没有同名字段、但需要
              索引的列（例如 deactivated 由 account_status 推导）。部分更新时，
              只有来源字段出现在本次改动里才重算，避免无关更新把它连带清零。
    """
    name: str
    promoted: dict[str, str]
    unique: tuple[str, ...] = ()
    indexes: tuple[tuple[str, ...], ...] = ()
    partial_unique: tuple[tuple[tuple[str, ...], str], ...] = ()
    derived: dict[str, tuple[tuple[str, ...], Any]] = field(default_factory=dict)


def _is_deactivated(payload: dict) -> bool:
    return str(payload.get("account_status") or "").strip().lower() == "deactivated"


ACCOUNTS = TableSpec(
    name="registered_accounts",
    promoted={
        "email": "TEXT NOT NULL",
        "created_at": "TEXT NOT NULL",
        "updated_at": "TEXT NOT NULL",
        "archived": "BOOLEAN NOT NULL DEFAULT FALSE",
        "email_source": "TEXT",
        "plan_type": "TEXT",
        "current_plan_type": "TEXT",
        "plus_trial_eligible": "BOOLEAN",
        "codex_status": "TEXT",
        "plan_check_status": "TEXT",
        "live_check_status": "TEXT",
        "extract_link_status": "TEXT",
        "deactivation_mail_scan_status": "TEXT",
        "token_expires_at": "TEXT",
        # 抢占条件要用，但 payload 里叫 account_status，故为派生列
        "deactivated": "BOOLEAN NOT NULL DEFAULT FALSE",
    },
    unique=("email",),
    indexes=(
        ("archived", "id"),
        ("plan_check_status",),
        ("live_check_status",),
        ("extract_link_status",),
        ("token_expires_at",),
    ),
    derived={"deactivated": (("account_status",), _is_deactivated)},
)

JOBS = TableSpec(
    name="registration_jobs",
    promoted={
        "job_uuid": "TEXT",
        "email": "TEXT",
        "created_at": "TEXT NOT NULL",
        "updated_at": "TEXT NOT NULL",
        "status": "TEXT",
        "job_type": "TEXT",
        "batch_id": "TEXT",
        "account_id": "BIGINT",
        "root_job_id": "BIGINT",
        "parent_job_id": "BIGINT",
    },
    unique=("job_uuid",),
    indexes=(("status", "id"), ("batch_id",), ("account_id",), ("root_job_id",)),
)

_POOL_PROMOTED = {
    "email": "TEXT NOT NULL",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL",
    "status": "TEXT",
    "used_at": "TEXT",
    "registered_account_id": "BIGINT",
}

OUTLOOK_POOL = TableSpec(
    name="email_pool_outlook",
    promoted=dict(_POOL_PROMOTED),
    unique=("email",),
    indexes=(("status", "id"),),
)

GENERIC_API_POOL = TableSpec(
    name="email_pool_generic_api",
    promoted=dict(_POOL_PROMOTED),
    unique=("email",),
    indexes=(("status", "id"),),
)

DOMAIN_POOL = TableSpec(
    name="email_pool_domain",
    promoted=dict(_POOL_PROMOTED),
    unique=("email",),
    indexes=(("status", "id"),),
)

ICLOUD_HIDE_POOL = TableSpec(
    name="email_pool_icloud_hide",
    promoted={
        **_POOL_PROMOTED,
        "account_id": "TEXT",
    },
    unique=("email",),
    indexes=(("status", "id"), ("account_id", "id")),
)

CODEX_CREDENTIALS = TableSpec(
    name="codex_credentials",
    promoted={
        "filename": "TEXT NOT NULL",
        "email": "TEXT",
        "plan": "TEXT",
        "account_id": "TEXT",
        "created_at": "TEXT NOT NULL",
        "updated_at": "TEXT NOT NULL",
        "mtime": "TEXT",
        "archived": "BOOLEAN NOT NULL DEFAULT FALSE",
        "exported_count": "BIGINT NOT NULL DEFAULT 0",
        "oauth_status": "TEXT",
        "oauth_expires_at": "TEXT",
    },
    unique=("filename",),
    indexes=(("archived", "id"), ("email",), ("account_id",), ("oauth_status",)),
)

PROXY_LEASES = TableSpec(
    name="proxy_leases",
    promoted={
        "lease_id": "TEXT NOT NULL",
        "provider": "TEXT NOT NULL",
        "endpoint": "TEXT NOT NULL",
        "proxy_url": "TEXT",
        "exit_ip": "TEXT",
        "region": "TEXT",
        "state": "TEXT NOT NULL",
        "acquired_at": "TEXT NOT NULL",
        "expires_at": "TEXT",
        "recent_until": "TEXT",
        "released_at": "TEXT",
        "batch_id": "TEXT",
        "job_id": "TEXT",
        "release_reason": "TEXT",
        "created_at": "TEXT NOT NULL",
        "updated_at": "TEXT NOT NULL",
    },
    unique=("lease_id",),
    indexes=(("state", "recent_until"), ("batch_id",), ("job_id",)),
    partial_unique=(
        (("endpoint",), '"state" IN (\'pending\', \'leased\', \'recent\')'),
        (("exit_ip",), '"exit_ip" IS NOT NULL AND "state" IN (\'leased\', \'recent\')'),
    ),
)

ALL_TABLES: tuple[TableSpec, ...] = (
    ACCOUNTS,
    JOBS,
    OUTLOOK_POOL,
    GENERIC_API_POOL,
    DOMAIN_POOL,
    ICLOUD_HIDE_POOL,
    CODEX_CREDENTIALS,
    PROXY_LEASES,
)
_BY_NAME = {spec.name: spec for spec in ALL_TABLES}


# ============================================================
# 连接与建表
# ============================================================

def _connect():
    from psycopg.rows import dict_row
    return postgres_store.connect(row_factory=dict_row)


def _qualified(spec: TableSpec) -> str:
    return postgres_store.qualified(spec.name)


def init() -> None:
    """幂等建表。schema 变了会重新执行一次。"""
    global _READY_KEY
    url = postgres_store.database_url()
    if not url:
        raise RuntimeError("record_store 需要配置可用的 DATABASE_URL")
    ready_key = f"{url}::{postgres_store.schema_name()}"
    with _LOCK:
        if _READY_KEY == ready_key:
            return
        postgres_store.ensure_schema()   # 建 schema，并触发测试 schema 护栏
        with _connect() as conn, conn.cursor() as cur:
            for spec in ALL_TABLES:
                columns = ["id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"]
                columns += [f"{postgres_store.quote_identifier(col)} {sql}"
                            for col, sql in spec.promoted.items()]
                columns.append("data JSONB NOT NULL DEFAULT '{}'::jsonb")
                cur.execute(f"CREATE TABLE IF NOT EXISTS {_qualified(spec)} ({', '.join(columns)})")
                # CREATE TABLE IF NOT EXISTS 不会给已存在的表补新提升列。存储层允许
                # 稀疏字段后续提升为可筛选列，因此这里必须把 schema 演进也做成幂等。
                for col, column_sql in spec.promoted.items():
                    cur.execute(
                        f"ALTER TABLE {_qualified(spec)} ADD COLUMN IF NOT EXISTS "
                        f"{postgres_store.quote_identifier(col)} {column_sql}"
                    )
                for col in spec.unique:
                    idx = postgres_store.quote_identifier(f"uq_{spec.name}_{col}")
                    cur.execute(
                        f"CREATE UNIQUE INDEX IF NOT EXISTS {idx} ON {_qualified(spec)} "
                        f"({postgres_store.quote_identifier(col)}) "
                        f"WHERE {postgres_store.quote_identifier(col)} IS NOT NULL"
                    )
                for cols in spec.indexes:
                    idx = postgres_store.quote_identifier(f"idx_{spec.name}_{'_'.join(cols)}")
                    rendered = ", ".join(postgres_store.quote_identifier(c) for c in cols)
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON {_qualified(spec)} ({rendered})")
                for cols, predicate in spec.partial_unique:
                    idx = postgres_store.quote_identifier(
                        f"uq_{spec.name}_{'_'.join(cols)}_partial"
                    )
                    rendered = ", ".join(postgres_store.quote_identifier(c) for c in cols)
                    cur.execute(
                        f"CREATE UNIQUE INDEX IF NOT EXISTS {idx} ON {_qualified(spec)} ({rendered}) "
                        f"WHERE {predicate}"
                    )
                gin = postgres_store.quote_identifier(f"idx_{spec.name}_data_gin")
                cur.execute(f"CREATE INDEX IF NOT EXISTS {gin} ON {_qualified(spec)} USING gin(data)")
        _READY_KEY = ready_key


def reset_ready() -> None:
    """强制下次 init() 重新建表检查。切 schema 后（测试）调用。"""
    global _READY_KEY
    with _LOCK:
        _READY_KEY = ""


# ============================================================
# 行 <-> 扁平 dict
# ============================================================

# 读时现算的派生字段，永不入库。在这里统一拦掉，好过指望十几个调用点都记得
# 不要把它塞进来；它们仍会把值放在返回给接口的 dict 上，那是对的。
_NEVER_PERSIST = {"copy_line", "account_copy_line"}


def _split(spec: TableSpec, payload: dict, *, partial: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """把扁平 payload 拆成 (提升列, data)。

    partial=True 表示这是一次部分更新：payload 里没出现的字段一律不碰。
    """
    promoted: dict[str, Any] = {}
    for col in spec.promoted:
        if col in spec.derived:
            sources, fn = spec.derived[col]
            if partial and not any(s in payload for s in sources):
                continue
            promoted[col] = fn(payload)
        elif col in payload:
            promoted[col] = payload[col]
    rest = {k: v for k, v in payload.items()
            if k not in spec.promoted and k not in ("id", "data") and k not in _NEVER_PERSIST}
    return promoted, rest


def _build_set_clause(spec: TableSpec, changes: dict, *, partial: bool) -> tuple[list[str], list[Any]]:
    """把一次改动翻译成 SET 片段。JSONB `||` 走服务端合并，不需要先读全量。"""
    promoted, rest = _split(spec, dict(changes or {}), partial=partial)
    sets: list[str] = []
    args: list[Any] = []
    for col, value in promoted.items():
        sets.append(f"{postgres_store.quote_identifier(col)} = %s")
        args.append(value)
    if rest:
        sets.append("data = data || %s::jsonb")
        args.append(json.dumps(rest, ensure_ascii=False))
    if "updated_at" not in promoted:
        sets.append(f"{postgres_store.quote_identifier('updated_at')} = %s")
        args.append(_now())
    return sets, args


def _merge(spec: TableSpec, row: dict | None) -> dict | None:
    """把一行还原成调用方看到的扁平 dict。"""
    if row is None:
        return None
    data = row.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (TypeError, ValueError):
            data = {}
    out: dict[str, Any] = dict(data or {})
    out["id"] = row.get("id")
    for col in spec.promoted:
        # 派生列只服务查询，不回灌到 payload，避免制造 payload 里本不存在的字段
        if col in spec.derived:
            continue
        out[col] = row.get(col)
    return out


def merge_row(table: str | TableSpec, row: dict | None) -> dict | None:
    """把 SQL 返回行恢复成业务扁平字典，供只读仓储复用。"""
    return _merge(_resolve(table), row)


def _resolve(table: str | TableSpec) -> TableSpec:
    if isinstance(table, TableSpec):
        return table
    spec = _BY_NAME.get(str(table))
    if spec is None:
        raise ValueError(f"未知表: {table!r}")
    return spec


# ============================================================
# 读
# ============================================================

def list_rows(
    table: str | TableSpec,
    *,
    where: str = "",
    params: Iterable[Any] = (),
    order_by: str = "id DESC",
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    spec = _resolve(table)
    init()
    sql = f"SELECT * FROM {_qualified(spec)}"
    if where:
        sql += f" WHERE {where}"
    sql += f" ORDER BY {order_by}"
    args = list(params)
    if limit is not None:
        sql += " LIMIT %s"
        args.append(int(limit))
    if offset:
        sql += " OFFSET %s"
        args.append(int(offset))
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return [_merge(spec, row) for row in cur.fetchall()]


def get_row(table: str | TableSpec, row_id: int) -> dict | None:
    spec = _resolve(table)
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {_qualified(spec)} WHERE id = %s", (int(row_id),))
        return _merge(spec, cur.fetchone())


def get_row_by(table: str | TableSpec, column: str, value: Any, *, lower: bool = False) -> dict | None:
    spec = _resolve(table)
    if column not in spec.promoted:
        raise ValueError(f"{spec.name} 没有提升列 {column!r}，无法按它查询")
    init()
    col = postgres_store.quote_identifier(column)
    clause = f"lower({col}) = lower(%s)" if lower else f"{col} = %s"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {_qualified(spec)} WHERE {clause} LIMIT 1", (value,))
        return _merge(spec, cur.fetchone())


def count_rows(table: str | TableSpec, *, where: str = "", params: Iterable[Any] = ()) -> int:
    spec = _resolve(table)
    init()
    sql = f"SELECT count(*) AS n FROM {_qualified(spec)}"
    if where:
        sql += f" WHERE {where}"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, list(params))
        return int(cur.fetchone()["n"])


# ============================================================
# 写
# ============================================================

def insert_row(table: str | TableSpec, payload: dict, *, conn=None) -> int:
    spec = _resolve(table)
    init()
    body = dict(payload or {})
    now = _now()
    # 两个都用 setdefault：调用方给了就尊重它。迁移要保留历史时间戳，
    # 无条件盖成 now() 会把"这条记录上次何时变动"这个信息抹掉。
    body.setdefault("created_at", now)
    body.setdefault("updated_at", body["created_at"])
    promoted, rest = _split(spec, body, partial=False)
    explicit_id = body.get("id")
    cols, vals = [], []
    if explicit_id is not None:
        cols.append("id")
        vals.append(int(explicit_id))
    for col, value in promoted.items():
        cols.append(col)
        vals.append(value)
    cols.append("data")
    vals.append(json.dumps(rest, ensure_ascii=False))
    rendered = ", ".join(postgres_store.quote_identifier(c) for c in cols)
    placeholders = ", ".join("%s::jsonb" if c == "data" else "%s" for c in cols)
    sql = f"INSERT INTO {_qualified(spec)} ({rendered}) VALUES ({placeholders}) RETURNING id"

    def _run(cur):
        cur.execute(sql, vals)
        return int(cur.fetchone()["id"])

    if conn is not None:
        with conn.cursor() as cur:
            return _run(cur)
    with _connect() as own, own.cursor() as cur:
        return _run(cur)


def upsert_row_by(
    table: str | TableSpec,
    key: str,
    payload: dict,
    *,
    conn=None,
) -> int:
    """按唯一提升列原子新增或合并一行，返回行 ID。

    更新分支只覆盖本次 payload 明确给出的提升列，JSONB 则在数据库端合并；
    ``created_at`` 保留原值。它用于凭证、邮箱导入等天然幂等的写路径，避免
    ``SELECT`` 后 ``INSERT`` 的竞态窗口。
    """
    spec = _resolve(table)
    if key not in spec.unique:
        raise ValueError(f"{spec.name} 的 {key!r} 不是唯一提升列")
    init()
    body = dict(payload or {})
    if body.get(key) is None:
        raise ValueError(f"{key} 不能为空")
    now = _now()
    body.setdefault("created_at", now)
    body.setdefault("updated_at", now)
    promoted, rest = _split(spec, body, partial=False)

    cols = list(promoted) + ["data"]
    vals = [promoted[col] for col in promoted] + [json.dumps(rest, ensure_ascii=False)]
    rendered = ", ".join(postgres_store.quote_identifier(col) for col in cols)
    placeholders = ", ".join("%s::jsonb" if col == "data" else "%s" for col in cols)
    target = postgres_store.quote_identifier("target")
    updates = []
    for col in promoted:
        if col in {key, "created_at"}:
            continue
        quoted = postgres_store.quote_identifier(col)
        updates.append(f"{quoted} = EXCLUDED.{quoted}")
    updates.append(f"data = {target}.data || EXCLUDED.data")
    quoted_key = postgres_store.quote_identifier(key)
    sql = (
        f"INSERT INTO {_qualified(spec)} AS {target} ({rendered}) VALUES ({placeholders}) "
        f"ON CONFLICT ({quoted_key}) WHERE {quoted_key} IS NOT NULL DO UPDATE SET "
        f"{', '.join(updates)} RETURNING id"
    )

    def _run(cur):
        cur.execute(sql, vals)
        return int(cur.fetchone()["id"])

    if conn is not None:
        with conn.cursor() as cur:
            return _run(cur)
    with _connect() as own, own.cursor() as cur:
        return _run(cur)


def insert_row_if_absent(
    table: str | TableSpec,
    key: str,
    payload: dict,
    *,
    conn=None,
) -> int | None:
    """按唯一提升列新增；已存在时返回 ``None``，不会覆盖原记录。"""
    spec = _resolve(table)
    if key not in spec.unique:
        raise ValueError(f"{spec.name} 的 {key!r} 不是唯一提升列")
    init()
    body = dict(payload or {})
    if body.get(key) is None:
        raise ValueError(f"{key} 不能为空")
    now = _now()
    body.setdefault("created_at", now)
    body.setdefault("updated_at", body["created_at"])
    promoted, rest = _split(spec, body, partial=False)
    cols = list(promoted) + ["data"]
    vals = [promoted[col] for col in promoted] + [json.dumps(rest, ensure_ascii=False)]
    rendered = ", ".join(postgres_store.quote_identifier(col) for col in cols)
    placeholders = ", ".join("%s::jsonb" if col == "data" else "%s" for col in cols)
    quoted_key = postgres_store.quote_identifier(key)
    sql = (
        f"INSERT INTO {_qualified(spec)} ({rendered}) VALUES ({placeholders}) "
        f"ON CONFLICT ({quoted_key}) WHERE {quoted_key} IS NOT NULL DO NOTHING RETURNING id"
    )

    def _run(cur):
        cur.execute(sql, vals)
        row = cur.fetchone()
        return int(row["id"]) if row else None

    if conn is not None:
        with conn.cursor() as cur:
            return _run(cur)
    with _connect() as own, own.cursor() as cur:
        return _run(cur)


def patch_row(table: str | TableSpec, row_id: int, changes: dict, *, conn=None) -> bool:
    """只更新 changes 里出现的字段。

    JSONB `||` 是服务端合并：两个线程改不同字段不会互相覆盖，也不需要先读全量。
    """
    spec = _resolve(table)
    init()
    sets, args = _build_set_clause(spec, changes, partial=True)
    args.append(int(row_id))
    sql = f"UPDATE {_qualified(spec)} SET {', '.join(sets)} WHERE id = %s"

    def _run(cur):
        cur.execute(sql, args)
        return cur.rowcount > 0

    if conn is not None:
        with conn.cursor() as cur:
            return _run(cur)
    with _connect() as own, own.cursor() as cur:
        return _run(cur)


def patch_rows_where(
    table: str | TableSpec,
    *,
    changes: dict,
    where: str,
    params: Iterable[Any] = (),
    conn=None,
) -> int:
    """Update rows matching a trusted SQL predicate and return affected count."""
    spec = _resolve(table)
    init()
    sets, args = _build_set_clause(spec, changes, partial=True)
    args.extend(params)
    sql = f"UPDATE {_qualified(spec)} SET {', '.join(sets)} WHERE {where}"

    def _run(cur):
        cur.execute(sql, args)
        return int(cur.rowcount)

    if conn is not None:
        with conn.cursor() as cur:
            return _run(cur)
    with _connect() as own, own.cursor() as cur:
        return _run(cur)


def patch_rows_where_returning(
    table: str | TableSpec,
    *,
    changes: dict,
    where: str,
    params: Iterable[Any] = (),
    conn=None,
) -> list[dict]:
    """批量部分更新并返回真正命中的业务行。"""
    spec = _resolve(table)
    init()
    sets, args = _build_set_clause(spec, changes, partial=True)
    args.extend(params)
    sql = f"UPDATE {_qualified(spec)} SET {', '.join(sets)} WHERE {where} RETURNING *"

    def _run(cur):
        cur.execute(sql, args)
        return [_merge(spec, row) for row in cur.fetchall()]

    if conn is not None:
        with conn.cursor() as cur:
            return _run(cur)
    with _connect() as own, own.cursor() as cur:
        return _run(cur)


def claim_row(
    table: str | TableSpec,
    row_id: int,
    *,
    changes: dict,
    guard: str,
    guard_params: Iterable[Any] = (),
    conn=None,
) -> bool:
    """条件更新实现原子抢占：guard 不成立就不改，返回 False。

    取代"读出来判断状态再写回"的两步写法——那种写法在两个进程之间没有互斥，
    两边都会读到 idle 然后都以为抢到了。
    """
    spec = _resolve(table)
    init()
    sets, args = _build_set_clause(spec, changes, partial=True)
    args.append(int(row_id))
    args.extend(guard_params)
    sql = (f"UPDATE {_qualified(spec)} SET {', '.join(sets)} "
           f"WHERE id = %s AND ({guard}) RETURNING id")

    def _run(cur):
        cur.execute(sql, args)
        return cur.fetchone() is not None

    if conn is not None:
        with conn.cursor() as cur:
            return _run(cur)
    with _connect() as own, own.cursor() as cur:
        return _run(cur)


def claim_next_row(
    table: str | TableSpec,
    *,
    changes: dict,
    where: str,
    params: Iterable[Any] = (),
    order_by: str = "id",
) -> dict | None:
    """用 ``FOR UPDATE SKIP LOCKED`` 原子领取一个符合条件的最早记录。"""
    spec = _resolve(table)
    init()
    sets, set_args = _build_set_clause(spec, changes, partial=True)
    args = [*params, *set_args]
    sql = (
        f"WITH candidate AS (SELECT id FROM {_qualified(spec)} WHERE {where} "
        f"ORDER BY {order_by} FOR UPDATE SKIP LOCKED LIMIT 1) "
        f"UPDATE {_qualified(spec)} AS target SET {', '.join(sets)} "
        "FROM candidate WHERE target.id = candidate.id RETURNING target.*"
    )
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return _merge(spec, cur.fetchone())


def delete_rows(table: str | TableSpec, ids: Iterable[int], *, conn=None) -> int:
    spec = _resolve(table)
    init()
    wanted = [int(i) for i in ids]
    if not wanted:
        return 0
    sql = f"DELETE FROM {_qualified(spec)} WHERE id = ANY(%s)"

    def _run(cur):
        cur.execute(sql, (wanted,))
        return cur.rowcount

    if conn is not None:
        with conn.cursor() as cur:
            return _run(cur)
    with _connect() as own, own.cursor() as cur:
        return _run(cur)


def delete_rows_where_returning(
    table: str | TableSpec,
    *,
    where: str,
    params: Iterable[Any] = (),
    conn=None,
) -> list[dict]:
    """删除命中行并返回删除前内容，便于 API 准确报告和清理单个附属文件。"""
    spec = _resolve(table)
    init()
    sql = f"DELETE FROM {_qualified(spec)} WHERE {where} RETURNING *"

    def _run(cur):
        cur.execute(sql, list(params))
        return [_merge(spec, row) for row in cur.fetchall()]

    if conn is not None:
        with conn.cursor() as cur:
            return _run(cur)
    with _connect() as own, own.cursor() as cur:
        return _run(cur)


def transaction():
    """跨表事务。

    insert_account 之类的操作要同时改账号和邮箱池，必须在一个事务里提交，
    否则会出现"账号建好了但邮箱没标记 used"。用法：

        with record_store.transaction() as conn:
            record_store.patch_row(ACCOUNTS, acc_id, {...}, conn=conn)
            record_store.patch_row(OUTLOOK_POOL, pool_id, {...}, conn=conn)
    """
    init()
    return _connect()


def sync_identity(table: str | TableSpec) -> int:
    """把 id 序列推到当前 max(id) 之后。

    迁移时保留了原有 id（被 codex_accounts 文件名和 account_action_tasks.account_id
    引用，不能重排），所以导入完必须复位序列，否则下一次插入会撞主键。
    """
    spec = _resolve(table)
    init()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COALESCE(max(id), 0) AS m FROM {_qualified(spec)}")
        current = int(cur.fetchone()["m"])
        cur.execute(
            f"SELECT setval(pg_get_serial_sequence(%s, 'id'), %s, true) AS v",
            (f"{postgres_store.schema_name()}.{spec.name}", max(current, 1)),
        )
        return current
