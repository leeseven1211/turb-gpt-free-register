# -*- coding: utf-8 -*-
"""PostgreSQL-backed cross-process coordination for 1024Proxy leases."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from psycopg.rows import dict_row

from core.storage import records as record_store
from core.storage import postgres as postgres_store


PROXY_LEASES = record_store.PROXY_LEASES
ACTIVE_STATES = ("pending", "leased", "recent", "shared_pending", "shared_leased", "pool_leased")
LEASE_WINDOWS = frozenset({"all", "1h", "24h", "7d"})
REUSE_LIMIT_DEFAULT = 3
REUSE_LIMIT_MIN = 1
REUSE_LIMIT_MAX = 100


class DuplicateProxyLeaseError(RuntimeError):
    """Another process already owns the endpoint or exit IP."""


class ProxyReuseLimitError(DuplicateProxyLeaseError):
    """套餐查询出口 IP 已达到持久化复用上限。"""

    def __init__(self, exit_ip: str, limit: int):
        self.exit_ip = str(exit_ip)
        self.limit = int(limit)
        super().__init__("当前线路已达到查询次数上限，等待其他可用线路")


def normalize_reuse_limit(value: int = REUSE_LIMIT_DEFAULT) -> int:
    """在存储边界校验有界的套餐查询复用次数。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("套餐查询复用次数必须是 1 到 100 的整数")
    if not REUSE_LIMIT_MIN <= value <= REUSE_LIMIT_MAX:
        raise ValueError("套餐查询复用次数必须在 1 到 100 之间")
    return value


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def plan_check_exit_ip_count(
    conn,
    exit_ip: str,
    *,
    now: str | None = None,
    exclude_lease_id: str | None = None,
) -> int:
    """统计当前事务中某出口 IP 的已交付及领取预留套餐查询租约。

    调用方必须先持有 ``proxy-exit-ip:<exit_ip>`` 锁。释放记录在原始过期前仍计数，
    pending 和确定未交付的记录不计数；旧记录缺少交付字段按已交付。
    """
    timestamp = now or _now()
    clauses = (
        '"purpose" = \'plan-check\'',
        '"exit_ip" = %s',
        '"expires_at" IS NOT NULL',
        '"expires_at" > %s',
        '"state" NOT IN (\'pending\', \'shared_pending\')',
        "COALESCE(data->>'delivery_state', 'delivered') <> 'not_delivered'",
    )
    params: list[Any] = [exit_ip, timestamp]
    if exclude_lease_id is not None:
        clauses += ('"lease_id" <> %s',)
        params.append(str(exclude_lease_id))
    return record_store.count_rows(PROXY_LEASES, where=" AND ".join(clauses), params=params, conn=conn)


def _cleanup_expired() -> None:
    now = _now()
    record_store.init()
    with record_store.transaction() as conn:
        record_store.patch_rows_where(
            PROXY_LEASES,
            changes={"state": "released", "released_at": now},
            where='"state" IN (\'pending\', \'leased\', \'shared_pending\', \'shared_leased\', \'pool_leased\') AND "expires_at" IS NOT NULL AND "expires_at" <= %s',
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
    allow_reuse: bool = False,
) -> None:
    """Reserve an endpoint before network validation.

    The partial endpoint index makes this operation mutually exclusive across
    WebUI/CLI processes. A duplicate is reported separately from database errors
    so the provider can fetch another endpoint.
    """
    if allow_reuse and purpose != "plan-check":
        raise ValueError("仅套餐查询允许建立共享代理租约")
    _cleanup_expired()
    try:
        with record_store.transaction() as conn:
            # 两类租约按端点串行检查和创建；严格模式不能绕过已活跃的共享查询。
            record_store.advisory_xact_lock(conn, f"proxy-endpoint:{endpoint}")
            if not allow_reuse and record_store.count_rows(
                PROXY_LEASES,
                where='"endpoint" = %s AND "endpoint_owner" = TRUE AND "state" IN (\'shared_pending\', \'shared_leased\', \'pool_leased\') '
                      'AND ("expires_at" IS NULL OR "expires_at" > %s)',
                params=(endpoint, _now()),
                conn=conn,
            ):
                raise DuplicateProxyLeaseError(f"端点已被其他进程占用: {endpoint}")
            record_store.insert_row(
                PROXY_LEASES,
                {
                    "lease_id": lease_id,
                    "provider": provider,
                    "endpoint": endpoint,
                    "proxy_url": proxy_url,
                    # 共享状态不进入端点/出口 IP 独占索引，但每个查询仍有独立租约。
                    "state": "shared_pending" if allow_reuse else "pending",
                    "allow_reuse": bool(allow_reuse),
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
                conn=conn,
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


def bind_browser_relay(*, proxy_url: str, profile_id: str, listen_port: int,
                       blocked_hosts: list[str], lease_id: str | None = None,
                       operation_task_id: int | None = None) -> str | None:
    """把中继恢复元数据附在已有私有租约中，不改变租约状态或复制代理凭据。"""
    if not lease_id and operation_task_id is None:
        return None
    if not profile_id or isinstance(listen_port, bool) or not 1 <= int(listen_port) <= 65535:
        raise ValueError("浏览器中继恢复资料无效")
    clauses, params = ['"proxy_url" = %s'], [str(proxy_url)]
    if lease_id:
        clauses.append('"lease_id" = %s')
        params.append(str(lease_id))
    else:
        clauses.append('"operation_task_id" = %s')
        params.append(int(operation_task_id))
    record_store.init()
    with record_store.transaction() as conn:
        rows = record_store.list_rows(PROXY_LEASES, where=" AND ".join(clauses), params=params,
                                      order_by="id DESC", limit=1, conn=conn)
        if not rows:
            return None
        row = rows[0]
        # 同一 Profile 只有最后一次绑定可恢复；旧租约保留历史、退出恢复清单。
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified(PROXY_LEASES.name)} "
                "SET data=jsonb_set(data, '{browser_relay,open}', 'false'::jsonb) "
                "WHERE data->'browser_relay'->>'profile_id'=%s AND id<>%s",
                (str(profile_id), row["id"]),
            )
        record_store.patch_row(PROXY_LEASES, row["id"], {"browser_relay": {
            "profile_id": str(profile_id), "listen_port": int(listen_port),
            "blocked_hosts": list(blocked_hosts), "open": True,
        }}, conn=conn)
        return str(row["lease_id"])


def close_browser_relay(*, lease_id: str, profile_id: str, listen_port: int) -> None:
    """确认窗口关闭后撤销对应端口恢复资格，不覆盖后续 Profile 新绑定。"""
    record_store.init()
    with postgres_store.connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE {postgres_store.qualified(PROXY_LEASES.name)} "
            "SET data=jsonb_set(data, '{browser_relay,open}', 'false'::jsonb) "
            "WHERE lease_id=%s AND data->'browser_relay'->>'profile_id'=%s "
            "AND data->'browser_relay'->>'listen_port'=%s",
            (str(lease_id), str(profile_id), str(listen_port)),
        )


def private_browser_relays(profile_id: str | None = None) -> list[dict[str, Any]]:
    """仅供本机窗口恢复读取；普通租约列表不选择此 JSONB 或 proxy_url。"""
    where = "data->'browser_relay'->>'open' = 'true'"
    params = []
    if profile_id is not None:
        where += " AND data->'browser_relay'->>'profile_id' = %s"
        params.append(str(profile_id))
    return record_store.list_rows(PROXY_LEASES, where=where, params=params, order_by="id DESC", limit=10000)


def activate(
    *,
    lease_id: str,
    exit_ip: str | None,
    region: str | None,
    expires_at: str,
    reuse_limit: int = REUSE_LIMIT_DEFAULT,
) -> None:
    """Promote a pending lease after exit validation."""
    try:
        with record_store.transaction() as conn:
            row = record_store.get_row_by(
                PROXY_LEASES, "lease_id", str(lease_id), conn=conn, for_update=True,
            )
            if row is None:
                raise RuntimeError(f"代理租约不存在: {lease_id}")
            now = _now()
            shared = bool(row.get("allow_reuse"))
            if shared and row.get("purpose") != "plan-check":
                raise ValueError("仅套餐查询允许建立共享代理租约")
            if shared:
                if not exit_ip:
                    raise ValueError("共享代理租约必须确认实际出口 IP")
                limit = normalize_reuse_limit(reuse_limit)
            elif exit_ip:
                # 严格租约保留原有行为；reuse_limit 只对共享套餐查询生效。
                limit = None
            else:
                limit = None
            if exit_ip:
                record_store.advisory_xact_lock(conn, f"proxy-exit-ip:{exit_ip}")
            if (
                row.get("state") not in {"pending", "leased", "shared_pending", "shared_leased"}
                or (row.get("expires_at") and str(row["expires_at"]) <= now)
            ):
                raise RuntimeError(f"代理租约已结束，不能恢复为使用中: {lease_id}")
            if row.get("state") in {"leased", "shared_leased"}:
                if str(row.get("exit_ip") or "") != str(exit_ip or ""):
                    raise RuntimeError(f"代理租约已经绑定其他出口 IP，不能改写: {lease_id}")
                return
            if exit_ip:
                # 出口尚未被唯一索引保护的共享租约也参与严格模式的重复检查。
                if shared and plan_check_exit_ip_count(conn, exit_ip, now=now) >= int(limit):
                    raise ProxyReuseLimitError(exit_ip, int(limit))
                if not shared and record_store.count_rows(
                    PROXY_LEASES,
                    where='"exit_ip" = %s AND "id" <> %s AND "state" IN (\'shared_leased\', \'pool_leased\') '
                          'AND ("expires_at" IS NULL OR "expires_at" > %s)',
                    params=(exit_ip, int(row["id"]), _now()),
                    conn=conn,
                ):
                    raise DuplicateProxyLeaseError(f"出口 IP 已被其他进程占用: {exit_ip}")
            if not record_store.patch_row(
                PROXY_LEASES,
                int(row["id"]),
                {
                    "state": "shared_leased" if row.get("allow_reuse") else "leased",
                    "exit_ip": exit_ip,
                    "region": region,
                    "expires_at": expires_at,
                },
                conn=conn,
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
    with record_store.transaction() as conn:
        row = record_store.get_row_by(
            PROXY_LEASES, "lease_id", str(lease_id), conn=conn, for_update=True,
        )
        if row is None or row.get("state") not in ACTIVE_STATES:
            return
        now = _now()
        expired_at = row.get("recent_until") if row.get("state") == "recent" else row.get("expires_at")
        if row.get("allow_reuse") or (expired_at and str(expired_at) <= now):
            # 共享查询没有独占冷却期；已过期租约不能因迟到的释放再次占用线路。
            recent_until = None
        changes: dict[str, Any] = {
            "state": "recent" if recent_until else "released",
            "recent_until": recent_until,
            "released_at": now,
            "release_reason": str(reason or "completed")[:120],
        }
        record_store.patch_row(PROXY_LEASES, int(row["id"]), changes, conn=conn)


def abort(lease_id: str) -> None:
    """Remove a validation reservation after a failed candidate."""
    row_id = _find_lease_row_id(lease_id)
    if row_id is not None:
        record_store.delete_rows(PROXY_LEASES, [row_id])


def active_rows() -> list[dict]:
    return record_store.list_rows(
        PROXY_LEASES,
        where='"state" IN (\'pending\', \'leased\', \'recent\', \'shared_pending\', \'shared_leased\', \'pool_leased\')',
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


def _lease_window_cutoff(window: str | None) -> datetime | None:
    value = str(window or "all").strip().lower()
    if value not in LEASE_WINDOWS:
        raise ValueError("线路时间范围必须是 all、1h、24h 或 7d")
    hours = {"1h": 1, "24h": 24, "7d": 24 * 7}.get(value)
    # 代理租约时间历史上按北京时间本地无时区 ISO 字符串保存，筛选沿用该表示。
    return datetime.now() - timedelta(hours=hours) if hours else None


def _lease_where(
    *,
    view: str,
    window: str = "all",
    state: str = "all",
    purpose: str = "",
    search: str = "",
) -> tuple[str, list[Any]]:
    # 独立代理池的 leased 锚点只用于库存去重，不是业务任务租约。
    # 使用 IS DISTINCT FROM 保留旧记录中 purpose 为 NULL 的线路。
    conditions: list[str] = ["p.purpose IS DISTINCT FROM 'pool-reserve'"]
    params: list[Any] = []
    if view == "current":
        conditions.append("p.state IN ('pending', 'leased', 'shared_pending', 'shared_leased', 'pool_leased')")
    elif view == "history":
        conditions.append("p.state NOT IN ('pending', 'leased', 'shared_pending', 'shared_leased', 'pool_leased')")
    else:
        raise ValueError("代理租约视图必须是 current 或 history")
    state_value = str(state or "all").strip().lower()[:40]
    if state_value and state_value != "all":
        conditions.append("p.state = %s")
        params.append(state_value)
    purpose_value = str(purpose or "").strip()[:80]
    if purpose_value and purpose_value.lower() != "all":
        conditions.append("p.purpose = %s")
        params.append(purpose_value)
    search_value = str(search or "").strip()[:160]
    if search_value:
        pattern = f"%{search_value}%"
        conditions.append(
            "(" + " OR ".join(
                f"CAST(p.{column} AS TEXT) ILIKE %s"
                for column in (
                    "lease_id", "provider", "endpoint", "exit_ip", "account_id", "purpose",
                    "operation_task_id", "operation_run_id", "registration_job_id",
                )
            ) + ")"
        )
        params.extend([pattern] * 9)
    cutoff = _lease_window_cutoff(window)
    if cutoff is not None:
        conditions.append(
            "(NULLIF(p.acquired_at, '')::timestamp >= %s "
            "OR NULLIF(p.released_at, '')::timestamp >= %s)"
        )
        params.extend([cutoff, cutoff])
    return " AND ".join(conditions), params


def _page_query(
    cur,
    *,
    view: str,
    window: str = "all",
    state: str = "all",
    purpose: str = "",
    search: str = "",
) -> tuple[str, list[Any], str]:
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
    where, params = _lease_where(
        view=view,
        window=window,
        state=state,
        purpose=purpose,
        search=search,
    )
    sql = (
        f"SELECT {', '.join(columns)} FROM {postgres_store.qualified(PROXY_LEASES.name)} p "
        f"{' '.join(joins)} WHERE {where} ORDER BY p.id DESC LIMIT %s OFFSET %s"
    )
    return sql, params, where


def _safe_page_row(row: dict) -> dict[str, Any]:
    from core.proxy.provider import mask_endpoint

    out = {key: row.get(key) for key in row.keys() if key not in {"id", "endpoint", "exit_ip"}}
    out["endpoint"] = mask_endpoint(row.get("endpoint"))
    # 只有代理页面允许展示完整出口 IP，投影仍然排除带凭据的代理地址。
    out["exit_ip"] = row.get("exit_ip")
    out["id"] = row.get("id")
    return out


def list_page(
    *,
    view: str = "current",
    limit: int = 200,
    offset: int = 0,
    window: str = "all",
    state: str = "all",
    purpose: str = "",
    search: str = "",
) -> list[dict[str, Any]]:
    """Return a persisted, credential-free proxy page projection."""
    items, _ = list_page_with_total(
        view=view,
        limit=limit,
        offset=offset,
        window=window,
        state=state,
        purpose=purpose,
        search=search,
    )
    return items


def list_page_with_total(
    *,
    view: str = "current",
    limit: int = 200,
    offset: int = 0,
    window: str = "all",
    state: str = "all",
    purpose: str = "",
    search: str = "",
) -> tuple[list[dict[str, Any]], int]:
    """在同一事务快照内读取代理页面和筛选后总数。"""
    record_store.init()
    page_limit = max(1, min(500, int(limit or 200)))
    page_offset = max(0, int(offset or 0))
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        # 列表和总数必须读取同一数据库快照，避免租约变化造成页数与总数不一致。
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        sql, params, where = _page_query(
            cur,
            view=view,
            window=window,
            state=state,
            purpose=purpose,
            search=search,
        )
        cur.execute(sql, (*params, page_limit, page_offset))
        items = [_safe_page_row(row) for row in cur.fetchall()]
        cur.execute(
            f"SELECT count(*) AS n FROM {postgres_store.qualified(PROXY_LEASES.name)} p WHERE {where}",
            params,
        )
        total = int(cur.fetchone()["n"])
        return items, total


def count_leases(
    *,
    view: str | None = None,
    window: str = "all",
    state: str = "all",
    purpose: str = "",
    search: str = "",
    acquired_since: datetime | None = None,
    acquired_before: datetime | None = None,
) -> int:
    """按页面使用的限长筛选条件统计持久化租约。"""
    record_store.init()
    if acquired_since is not None or acquired_before is not None:
        conditions = ["p.purpose IS DISTINCT FROM 'pool-reserve'"]
        params: list[Any] = []
        if acquired_since is not None:
            conditions.append("NULLIF(p.acquired_at, '')::timestamp >= %s")
            params.append(acquired_since)
        if acquired_before is not None:
            conditions.append("NULLIF(p.acquired_at, '')::timestamp < %s")
            params.append(acquired_before)
        where = " AND ".join(conditions)
    else:
        if view is None:
            raise ValueError("统计线路总数需要指定视图或获取时间范围")
        where, params = _lease_where(
            view=view,
            window=window,
            state=state,
            purpose=purpose,
            search=search,
        )
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT count(*) AS n FROM {postgres_store.qualified(PROXY_LEASES.name)} p WHERE {where}",
            params,
        )
        return int(cur.fetchone()["n"])


def distinct_filter_values() -> dict[str, list[str]]:
    """返回代理表筛选器使用的全库限长去重值。"""
    record_store.init()
    table = postgres_store.qualified(PROXY_LEASES.name)
    result: dict[str, list[str]] = {}
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        for key in ("purpose", "state"):
            cur.execute(
                f"SELECT DISTINCT {postgres_store.quote_identifier(key)} AS value "
                f"FROM {table} WHERE purpose IS DISTINCT FROM 'pool-reserve' "
                f"AND NULLIF(BTRIM({postgres_store.quote_identifier(key)}), '') IS NOT NULL "
                f"ORDER BY value LIMIT %s",
                (500,),
            )
            result[key] = [str(row["value"])[:80] for row in cur.fetchall()]
    return result


def _find_lease_row_id(lease_id: str) -> int | None:
    row = record_store.get_row_by(PROXY_LEASES, "lease_id", str(lease_id))
    return int(row["id"]) if row else None


def _lease_row_id(lease_id: str) -> int:
    row_id = _find_lease_row_id(lease_id)
    if row_id is None:
        raise RuntimeError(f"代理租约不存在: {lease_id}")
    return row_id
