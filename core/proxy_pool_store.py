"""独立代理库存与任务租约；容量和领取在 PostgreSQL 中原子协调。"""
from __future__ import annotations

from datetime import datetime, timedelta
import uuid

from core import postgres_store, record_store

RESOURCES = record_store.PROXY_POOL_RESOURCES
LEASES = record_store.PROXY_LEASES
LIVE = ("fetching", "checking", "ready", "leased", "shared")
TERMINAL = ("failed", "retired", "expired")
_HISTORY_RETENTION_SECONDS = 7 * 24 * 60 * 60


def _stamp(seconds: float = 0) -> str:
    return (datetime.now() + timedelta(seconds=seconds)).isoformat(timespec="microseconds")


def reserve_slot(profile_key: str, provider: str, *, max_size: int, timeout: float, reclaim_idle: bool = False) -> dict | None:
    """先占容量再访问供应商；多进程不会各自补满一份池。"""
    record_store.init()
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, "proxy-pool-capacity")
        return _reserve_slot(conn, profile_key, provider, max_size=max_size, timeout=timeout,
                             reclaim_idle=reclaim_idle)


def _reserve_slot(conn, profile_key: str, provider: str, *, max_size: int, timeout: float,
                  reclaim_idle: bool) -> dict | None:
    """调用者持有容量事务锁，预留一个补货槽位。"""
    count = record_store.count_rows(RESOURCES, where='state = ANY(%s)', params=(list(LIVE),), conn=conn)
    if count >= max_size:
        # 有真实等待者时允许退役其他配置的空闲库存，避免旧地区占满全池。
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {postgres_store.qualified(RESOURCES.name)} "
                        "WHERE state = 'ready' AND profile_key <> %s AND %s "
                        "ORDER BY last_used_at FOR UPDATE SKIP LOCKED LIMIT 1", (profile_key, reclaim_idle))
            raw = cur.fetchone()
        if not raw or count > max_size:
            return None
        idle = record_store.merge_row(RESOURCES, raw)
        record_store.patch_row(RESOURCES, idle["id"], {"state": "retired"}, conn=conn)
        _close_anchor(conn, idle, reason="pool_rebalanced")
    token = uuid.uuid4().hex
    row = {"resource_id": uuid.uuid4().hex, "profile_key": profile_key, "provider": provider,
           "state": "fetching", "owner_token": token, "expires_at": _stamp(timeout),
           "last_used_at": _stamp()}
    row["id"] = record_store.insert_row(RESOURCES, row, conn=conn)
    return row


def _available_rows(conn, profile_key: str, *, min_ttl: float, max_age: float,
                    include_stale: bool = False) -> list[dict]:
    """与独占领取相同的准入条件；进行中的供给不计入空闲库存。"""
    from psycopg.rows import dict_row

    resources = postgres_store.qualified(RESOURCES.name)
    leases = postgres_store.qualified(LEASES.name)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT r.id, r.state FROM {resources} r LEFT JOIN {leases} anchor "
            "ON anchor.lease_id = r.anchor_lease_id WHERE r.profile_key = %s AND ("
            "(r.state = 'fetching' AND r.expires_at > %s) OR "
            "(r.state IN ('ready', 'checking') AND r.expires_at > %s "
            "AND anchor.state = 'leased' AND anchor.expires_at > %s "
            "AND NOT EXISTS ("
            f"SELECT 1 FROM {leases} child WHERE child.data->>'pool_anchor_id' = r.anchor_lease_id "
            "AND child.state IN ('pool_leased', 'shared_leased') AND child.expires_at > %s) "
            "AND ((r.state = 'ready' AND (r.checked_at >= %s OR (%s AND r.checked_at IS NOT NULL))) OR "
            "(r.state = 'checking' AND r.data->>'check_deadline' > %s))))",
            (profile_key, _stamp(), _stamp(min_ttl), _stamp(min_ttl), _stamp(), _stamp(-max_age), include_stale, _stamp()),
        )
        return cur.fetchall()


def availability(profile_key: str, *, min_ttl: float, max_age: float, conn=None) -> dict[str, int]:
    """ready 只表示能立即独占领取的线路；fetching/checking 仅抵扣重复补货。"""
    if conn is None:
        record_store.init()
        with postgres_store.connect() as connection:
            return availability(profile_key, min_ttl=min_ttl, max_age=max_age, conn=connection)
    result = {"ready": 0, "fetching": 0, "checking": 0}
    for row in _available_rows(conn, profile_key, min_ttl=min_ttl, max_age=max_age):
        result[row["state"]] += 1
    return result


def reserve_refill_slots(profile_key: str, provider: str, *, target: int, max_size: int,
                         min_ttl: float, max_age: float, limit: int, timeout: float,
                         reclaim_idle: bool = False) -> list[dict]:
    """在同一容量事务内计算缺口并预留，多个 worker 不会重复补同一份库存。"""
    record_store.init()
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, "proxy-pool-capacity")
        prepared = availability(profile_key, min_ttl=min_ttl, max_age=max_age, conn=conn)
        deficit = max(0, min(target, max_size) - sum(prepared.values()))
        slots = []
        for _ in range(min(max(0, limit), deficit)):
            slot = _reserve_slot(conn, profile_key, provider, max_size=max_size, timeout=timeout,
                                 reclaim_idle=reclaim_idle)
            if slot is None:
                break
            slots.append(slot)
        return slots


def publish(slot: dict, lease) -> bool:
    """晚到结果只能填充自己仍有效的槽位。"""
    with record_store.transaction() as conn:
        row = record_store.get_row_by(RESOURCES, "resource_id", slot["resource_id"], conn=conn, for_update=True)
        if not row or row["state"] != "fetching" or row["owner_token"] != slot["owner_token"]:
            return False
        if str(row["expires_at"]) <= _stamp() or not lease.expires_at:
            return False
        return record_store.patch_row(RESOURCES, row["id"], {
            "state": "ready", "owner_token": None, "anchor_lease_id": lease.lease_id,
            "checked_at": _stamp(), "expires_at": lease.expires_at.isoformat(timespec="microseconds"),
            "last_used_at": _stamp(), "region": lease.region, "endpoint": lease.endpoint,
            "exit_ip": lease.exit_ip, "last_error_code": None,
        }, conn=conn)


def fail_slot(slot: dict, code: str) -> None:
    with record_store.transaction() as conn:
        row = record_store.get_row_by(RESOURCES, "resource_id", slot["resource_id"], conn=conn, for_update=True)
        if row and row.get("owner_token") == slot.get("owner_token") and row["state"] == "fetching":
            record_store.patch_row(RESOURCES, row["id"], {"state": "failed", "owner_token": None,
                                                       "last_error_code": code[:80]}, conn=conn)


def _children(conn, anchor_id: str) -> list[dict]:
    return record_store.list_rows(LEASES, where="data->>'pool_anchor_id' = %s AND state IN ('shared_leased', 'pool_leased') AND expires_at > %s",
                                 params=(anchor_id, _stamp()), conn=conn)


def _close_anchor(conn, resource: dict, *, reason: str) -> None:
    """在资源终态事务中收口独占锚点，不触碰任务子租约。"""
    anchor_id = str(resource.get("anchor_lease_id") or "").strip()
    if not anchor_id:
        return
    anchor = record_store.get_row_by(LEASES, "lease_id", anchor_id, conn=conn, for_update=True)
    if not anchor:
        return
    # 只有资源直接指向的独占锚点可以在这里收口；共享领取的子租约
    # 通过 pool_anchor_id 反向指向它，不能被资源回收误释放。
    if anchor.get("pool_anchor_id"):
        return
    if anchor.get("state") not in {"pending", "leased", "recent"}:
        return
    desired_until = resource.get("expires_at")
    if anchor.get("state") == "recent" and str(anchor.get("recent_until") or "") == str(desired_until or ""):
        return
    record_store.patch_row(LEASES, anchor["id"], {
        "state": "recent",
        "recent_until": desired_until,
        # 已经进入 recent 的历史事实不因每轮维护被重新计时。
        "released_at": anchor.get("released_at") or _stamp(),
        "release_reason": str(reason or "pool_retired")[:120],
    }, conn=conn)


def _terminal_is_old(row: dict) -> bool:
    value = row.get("updated_at") or row.get("expires_at") or row.get("created_at")
    return bool(value and str(value) <= _stamp(-_HISTORY_RETENTION_SECONDS))


def _anchor_is_active(anchor: dict | None) -> bool:
    if not anchor:
        return False
    state = str(anchor.get("state") or "")
    if state == "recent":
        return bool(anchor.get("recent_until") and str(anchor["recent_until"]) > _stamp())
    return state in {"pending", "leased", "shared_pending", "shared_leased", "pool_leased"} and (
        not anchor.get("expires_at") or str(anchor["expires_at"]) > _stamp()
    )


def _purge_old_terminal(conn, resource: dict) -> bool:
    """有界清理已保留足够久且没有活跃关联的资源历史。"""
    anchor_id = str(resource.get("anchor_lease_id") or "").strip()
    if anchor_id and _children(conn, anchor_id):
        return False
    anchor = record_store.get_row_by(LEASES, "lease_id", anchor_id, conn=conn, for_update=True) if anchor_id else None
    if _anchor_is_active(anchor):
        return False
    if anchor:
        record_store.delete_rows(LEASES, [anchor["id"]], conn=conn)
    return bool(record_store.delete_rows(RESOURCES, [resource["id"]], conn=conn))


def _lease_object(row: dict, resource: dict, *, shared: bool):
    from core.proxy_provider import ProxyLease
    return ProxyLease(
        lease_id=row["lease_id"], provider=row["provider"], proxy_url=row["proxy_url"],
        endpoint=row["endpoint"], acquired_at=datetime.fromisoformat(row["acquired_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]), exit_ip=row.get("exit_ip"), region=row.get("region"),
        metadata={"pool_resource_id": resource["resource_id"], "pool_anchor_id": resource["anchor_lease_id"],
                  "persistent_lease": True, "allow_reuse": shared,
                  **{key: row.get(key) for key in ("purpose", "account_id", "operation_task_id", "operation_run_id",
                                                 "registration_job_id", "route_attempt_no")}},
    )


def claim(profile_key: str, *, min_ttl: float, max_age: float, correlation: dict, allow_reuse: bool = False):
    """只领取已检查且寿命足够的库存；此路径不执行任何网络操作。"""
    if allow_reuse and correlation.get("purpose") != "plan-check":
        raise ValueError("只有套餐查询允许共享代理")
    record_store.init()
    with record_store.transaction() as conn, conn.cursor() as cur:
        states = ["ready", "shared"] if allow_reuse else ["ready"]
        cur.execute(f"SELECT * FROM {postgres_store.qualified(RESOURCES.name)} "
                    "WHERE profile_key = %s AND state = ANY(%s) AND expires_at > %s AND checked_at >= %s "
                    "ORDER BY expires_at, id FOR UPDATE SKIP LOCKED LIMIT 1",
                    (profile_key, states, _stamp(min_ttl), _stamp(-max_age)))
        raw = cur.fetchone()
        resource = record_store.merge_row(RESOURCES, raw) if raw else None
        if not resource:
            return None
        anchor = record_store.get_row_by(LEASES, "lease_id", resource["anchor_lease_id"], conn=conn, for_update=True)
        if not anchor or anchor["state"] != "leased" or str(anchor["expires_at"]) <= _stamp(min_ttl):
            record_store.patch_row(RESOURCES, resource["id"], {"state": "expired"}, conn=conn)
            _close_anchor(conn, resource, reason="pool_anchor_stale")
            return None
        if not allow_reuse and _children(conn, anchor["lease_id"]):
            return None
        allowed = {key: value for key, value in correlation.items() if key in {
            "job_id", "account_id", "purpose", "operation_task_id", "operation_run_id",
            "registration_job_id", "route_attempt_no"}}
        # 锚点负责跨池去重，任务租约单独保存；再次领取不能改写上次任务的关联。
        row = {key: anchor.get(key) for key in ("provider", "endpoint", "proxy_url", "exit_ip", "region", "expires_at")}
        row.update(allowed)
        row.update(lease_id=uuid.uuid4().hex, state="shared_leased" if allow_reuse else "pool_leased", acquired_at=_stamp(),
                   allow_reuse=allow_reuse, pool_resource_id=resource["resource_id"], pool_anchor_id=anchor["lease_id"])
        record_store.insert_row(LEASES, row, conn=conn)
        record_store.patch_row(RESOURCES, resource["id"], {"state": "shared" if allow_reuse else "leased",
                                                        "last_used_at": _stamp()}, conn=conn)
        return _lease_object(row, resource, shared=allow_reuse)


def release(lease, *, reason: str, fault: bool = False, cooldown: float = 0) -> None:
    """任务释放只改变本租约；共享任务不会释放其他任务的租约。"""
    with record_store.transaction() as conn:
        resource = record_store.get_row_by(RESOURCES, "resource_id", lease.metadata["pool_resource_id"], conn=conn, for_update=True)
        row = record_store.get_row_by(LEASES, "lease_id", lease.lease_id, conn=conn, for_update=True)
        if not row or row["state"] not in {"pool_leased", "shared_leased"}:
            return
        shared = row["state"] == "shared_leased"
        record_store.patch_row(LEASES, row["id"], {
            "state": "released", "released_at": _stamp(),
            "release_reason": reason[:120],
        }, conn=conn)
        if not resource:
            return
        if fault:
            record_store.patch_row(RESOURCES, resource["id"], {"state": "quarantine", "last_error_code": "transport_failure"}, conn=conn)
            anchor = record_store.get_row_by(LEASES, "lease_id", resource["anchor_lease_id"], conn=conn, for_update=True)
            if anchor and anchor["state"] == "leased":
                record_store.patch_row(LEASES, anchor["id"], {"state": "recent", "recent_until": resource["expires_at"],
                                                           "release_reason": "pool_fault", "released_at": _stamp()}, conn=conn)
        elif not shared and resource["state"] == "leased":
            record_store.patch_row(RESOURCES, resource["id"], {
                "state": "cooldown" if cooldown else "ready", "cooldown_until": _stamp(cooldown),
                "last_used_at": _stamp(),
            }, conn=conn)
        elif resource["state"] == "shared" and not _children(conn, resource["anchor_lease_id"]):
            record_store.patch_row(RESOURCES, resource["id"], {"state": "ready", "last_used_at": _stamp()}, conn=conn)


def maintenance(*, max_age: float, max_idle: float, min_ready: int, min_ttl: float = 0,
                max_size: int | None = None, warm_profiles: set[str] | None = None) -> list[dict]:
    """回收过期/空闲库存，并恢复中断的检查；绝不将失联任务租约再次分配。"""
    record_store.init()
    retired = []
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, "proxy-pool-capacity")
        rows = record_store.list_rows(
            RESOURCES,
            where="state = ANY(%s)",
            params=(list(LIVE) + ["cooldown", "quarantine"],),
            conn=conn,
        )
        # 终态只做有界的 anchor 修复和历史清理，避免每轮维护全表扫描。
        terminal_repair = record_store.list_rows(
            RESOURCES,
            where="state = ANY(%s) AND anchor_lease_id IN ("
                  f"SELECT lease_id FROM {postgres_store.qualified(LEASES.name)} "
                  "WHERE state IN ('pending', 'leased'))",
            params=(list(TERMINAL),), conn=conn, limit=200, order_by="id",
        )
        terminal_cleanup = record_store.list_rows(
            RESOURCES,
            where="state = ANY(%s) AND updated_at <= %s",
            params=(list(TERMINAL), _stamp(-_HISTORY_RETENTION_SECONDS)),
            conn=conn, limit=200, order_by="updated_at, id",
        )
        terminal_rows = {int(row["id"]): row for row in (*terminal_repair, *terminal_cleanup)}
        live_count = sum(row["state"] in LIVE for row in rows)
        for candidate in (*rows, *terminal_rows.values()):
            row = record_store.get_row_by(RESOURCES, "resource_id", candidate["resource_id"], conn=conn, for_update=True)
            if row["state"] not in (*LIVE, "cooldown", "quarantine"):
                if row["state"] in TERMINAL:
                    _close_anchor(conn, row, reason="pool_terminal_reconcile")
                    if int(row["id"]) in terminal_rows and _terminal_is_old(row):
                        _purge_old_terminal(conn, row)
                continue
            expired = row["expires_at"] <= _stamp()
            if row["state"] in {"cooldown", "quarantine"}:
                if expired:
                    record_store.patch_row(RESOURCES, row["id"], {"state": "expired"}, conn=conn)
                    _close_anchor(conn, row, reason="pool_expired")
                    retired.append(row)
                elif row["state"] == "cooldown" and row.get("cooldown_until", "") <= _stamp():
                    state = "ready" if max_size is None or live_count < max_size else "retired"
                    record_store.patch_row(RESOURCES, row["id"], {"state": state}, conn=conn)
                    if state == "ready":
                        live_count += 1
                    else:
                        _close_anchor(conn, row, reason="pool_capacity_retired")
                        retired.append(row)
                continue
            if row["state"] == "shared" and not _children(conn, row["anchor_lease_id"]) and not expired:
                # 子租约仅在显式释放后结束；进程失联仍保留至自然到期。
                record_store.patch_row(RESOURCES, row["id"], {"state": "ready"}, conn=conn)
                row["state"] = "ready"
            if row["state"] == "checking" and str(row.get("check_deadline") or row["expires_at"]) <= _stamp():
                record_store.patch_row(RESOURCES, row["id"], {"state": "quarantine", "last_error_code": "check_interrupted"}, conn=conn)
                _close_anchor(conn, row, reason="check_interrupted")
                retired.append(row)
                live_count -= 1
                continue
            idle = row["state"] == "ready" and row["last_used_at"] < _stamp(-max_idle)
            if idle:
                available = {item["id"] for item in _available_rows(
                    conn, row["profile_key"], min_ttl=min_ttl, max_age=max_age,
                ) if item["state"] == "ready"}
                minimum = min_ready if warm_profiles is None or row["profile_key"] in warm_profiles else 0
                if row["id"] in available:
                    idle = len(available) > minimum
                else:
                    recoverable = {item["id"] for item in _available_rows(
                        conn, row["profile_key"], min_ttl=min_ttl, max_age=max_age, include_stale=True,
                    ) if item["state"] == "ready"}
                    # 检测过期的底数库存先保留供复检，不让供给故障期间丢掉健康旧线路。
                    idle = row["id"] not in recoverable or len(recoverable) > minimum
            too_short = row["state"] == "ready" and row["expires_at"] <= _stamp(min_ttl)
            over_capacity = max_size is not None and live_count > max_size and row["state"] == "ready"
            if expired or idle or too_short or over_capacity:
                state = "expired" if expired else "retired"
                record_store.patch_row(RESOURCES, row["id"], {"state": state, "owner_token": None}, conn=conn)
                _close_anchor(conn, row, reason="pool_expired" if expired else "pool_retired")
                retired.append(row)
                live_count -= 1
    return retired


def take_check(profile_key: str, *, max_age: float, timeout: float) -> dict | None:
    with record_store.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {postgres_store.qualified(RESOURCES.name)} WHERE profile_key = %s "
                    "AND state = 'ready' AND checked_at < %s AND expires_at > %s "
                    "ORDER BY checked_at FOR UPDATE SKIP LOCKED LIMIT 1", (profile_key, _stamp(-max_age), _stamp()))
        raw = cur.fetchone()
        if not raw:
            return None
        row = record_store.merge_row(RESOURCES, raw)
        token = uuid.uuid4().hex
        record_store.patch_row(RESOURCES, row["id"], {"state": "checking", "owner_token": token, "check_deadline": _stamp(timeout)}, conn=conn)
        row["owner_token"] = token
        return row


def finish_check(resource: dict, *, success: bool) -> bool:
    with record_store.transaction() as conn:
        row = record_store.get_row_by(RESOURCES, "resource_id", resource["resource_id"], conn=conn, for_update=True)
        if (not row or row["state"] != "checking" or row["owner_token"] != resource["owner_token"]
                or row["expires_at"] <= _stamp() or str(row.get("check_deadline") or "") <= _stamp()):
            return False
        updated = record_store.patch_row(RESOURCES, row["id"], {
            "state": "ready" if success else "quarantine",
            "owner_token": None, "checked_at": _stamp(),
            "last_error_code": None if success else "health_check_failed",
        }, conn=conn)
        if updated and not success:
            _close_anchor(conn, row, reason="health_check_failed")
        return updated


def counts(profile_key: str | None = None) -> dict[str, int]:
    record_store.init()
    with postgres_store.connect() as conn, conn.cursor() as cur:
        where = " WHERE profile_key = %s" if profile_key else ""
        cur.execute(f"SELECT state, count(*) FROM {postgres_store.qualified(RESOURCES.name)}{where} GROUP BY state",
                    (profile_key,) if profile_key else ())
        return {state: int(count) for state, count in cur.fetchall()}


def public_items(limit: int = 200) -> list[dict]:
    from core.proxy_provider import mask_endpoint, mask_ip
    return [{"resource_id": row["resource_id"], "provider": row["provider"], "state": row["state"],
             "region": row.get("region"), "endpoint": mask_endpoint(row.get("endpoint")), "exit_ip": mask_ip(row.get("exit_ip")),
             "checked_at": row.get("checked_at"), "expires_at": row["expires_at"],
             "cooldown_until": row.get("cooldown_until"),
             "last_error_code": row.get("last_error_code")} for row in record_store.list_rows(RESOURCES, limit=min(500, max(1, limit)))]
