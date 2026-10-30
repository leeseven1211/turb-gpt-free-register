"""独立代理库存与任务租约；容量和领取在 PostgreSQL 中原子协调。"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import threading
import time
import uuid

from core.storage import postgres as postgres_store, records as record_store
from core.storage.proxy import leases as proxy_lease_store

RESOURCES = record_store.PROXY_POOL_RESOURCES
LEASES = record_store.PROXY_LEASES
LIVE = ("fetching", "checking", "ready", "leased", "shared", "rotation_wait")
TERMINAL = ("failed", "retired", "expired")
_HISTORY_RETENTION_SECONDS = 7 * 24 * 60 * 60
_maintenance_lock = threading.Lock()
logger = logging.getLogger('core.proxy_pool_store')


def _stamp(seconds: float = 0) -> str:
    return (datetime.now() + timedelta(seconds=seconds)).isoformat(timespec="microseconds")


def _inventory_scope(profile_key: str, *, profile_keys: list[str] | None = None,
                     source_urls: list[str] | None = None, required_region: str | None = None) -> tuple[str, list]:
    """领取、补货与满池回收共用同源及实际国家条件。"""
    scope = "r.profile_key = %s"
    scope_params = [profile_key]
    if profile_keys is not None:
        from config.countries import ISO_3166_ALPHA2

        if not source_urls:
            raise ValueError("跨国家静态库存领取必须指定相同来源")
        regions = [required_region] if required_region else sorted(ISO_3166_ALPHA2)
        if required_region and required_region not in ISO_3166_ALPHA2:
            raise ValueError("静态库存目标国家必须为已知 ISO 3166-1 两位代码")
        # profile 键限定完整 URL 来源，锚点的 provider、URL 和实际国家再做 SQL 校验。
        scope = ("r.profile_key = ANY(%s) AND r.provider = 'proxy_pool' "
                 "AND r.data->>'region' = ANY(%s) AND EXISTS (SELECT 1 FROM "
                 + postgres_store.qualified(LEASES.name) + " candidate_anchor "
                 "WHERE candidate_anchor.lease_id = r.anchor_lease_id "
                 "AND candidate_anchor.provider = 'proxy_pool' AND candidate_anchor.proxy_url = ANY(%s) "
                 "AND candidate_anchor.region = r.data->>'region')")
        scope_params = [list(dict.fromkeys([profile_key, *profile_keys])), regions, source_urls]
    return scope, scope_params


def reserve_slot(profile_key: str, provider: str, *, max_size: int, timeout: float, reclaim_idle: bool = False) -> dict | None:
    """先占容量再访问供应商；多进程不会各自补满一份池。"""
    record_store.init()
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, "proxy-pool-capacity")
        return _reserve_slot(conn, profile_key, provider, max_size=max_size, timeout=timeout,
                             reclaim_idle=reclaim_idle)


def _reserve_slot(conn, profile_key: str, provider: str, *, max_size: int, timeout: float,
                  reclaim_idle: bool, protected_scope: tuple[str, list] | None = None) -> dict | None:
    """调用者持有容量事务锁，预留一个补货槽位。"""
    count = record_store.count_rows(RESOURCES, where='state = ANY(%s)', params=(list(LIVE),), conn=conn)
    if count >= max_size:
        # 有真实等待者时允许退役其他配置的空闲库存，避免旧地区占满全池。
        protected, protected_params = protected_scope or ("FALSE", [])
        with conn.cursor() as cur:
            cur.execute(f"SELECT r.* FROM {postgres_store.qualified(RESOURCES.name)} r "
                        "WHERE %s AND ((r.state = 'ready' AND r.profile_key <> %s) OR r.state = 'rotation_wait') "
                        f"AND NOT (r.state = 'ready' AND ({protected})) "
                        "AND NOT EXISTS (SELECT 1 FROM " + postgres_store.qualified(LEASES.name) + " child "
                        "WHERE child.data->>'pool_anchor_id' = r.anchor_lease_id "
                        "AND child.state IN ('shared_leased', 'pool_leased') AND child.expires_at > %s) "
                        "ORDER BY CASE WHEN r.state = 'rotation_wait' THEN 0 ELSE 1 END, r.last_used_at "
                        "FOR UPDATE OF r SKIP LOCKED LIMIT 1", (reclaim_idle, profile_key, *protected_params, _stamp()))
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
                    include_stale: bool = False, profile_keys: list[str] | None = None,
                    source_urls: list[str] | None = None, required_region: str | None = None) -> list[dict]:
    """与独占领取相同的准入条件；进行中的供给不计入空闲库存。"""
    from psycopg.rows import dict_row

    resources = postgres_store.qualified(RESOURCES.name)
    leases = postgres_store.qualified(LEASES.name)
    scope, scope_params = _inventory_scope(profile_key, profile_keys=profile_keys,
                                           source_urls=source_urls, required_region=required_region)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT r.id, r.state, r.checked_at, r.anchor_lease_id, r.expires_at, "
            f"anchor.expires_at AS anchor_expires_at FROM {resources} r LEFT JOIN {leases} anchor "
            "ON anchor.lease_id = r.anchor_lease_id WHERE ("
            "(r.profile_key = %s AND r.state = 'fetching' AND r.expires_at > %s) OR "
            f"(({scope}) AND r.state IN ('ready', 'checking') AND r.expires_at > %s "
            "AND anchor.state = 'leased' AND anchor.endpoint_owner = TRUE AND anchor.expires_at > %s "
            "AND COALESCE(r.data->>'reuse_exhausted', 'false') <> 'true' "
            "AND NOT EXISTS ("
            f"SELECT 1 FROM {leases} child WHERE child.data->>'pool_anchor_id' = r.anchor_lease_id "
            "AND child.state IN ('pool_leased', 'shared_leased') AND child.expires_at > %s) "
            "AND ((r.state = 'ready' AND (r.checked_at >= %s OR (%s AND r.checked_at IS NOT NULL))) OR "
            "(r.state = 'checking' AND r.data->>'check_deadline' > %s))))",
            (profile_key, _stamp(), *scope_params, _stamp(min_ttl), _stamp(min_ttl), _stamp(), _stamp(-max_age), include_stale, _stamp()),
        )
        return cur.fetchall()


def availability(profile_key: str, *, min_ttl: float, max_age: float, conn=None,
                 profile_keys: list[str] | None = None, source_urls: list[str] | None = None,
                 required_region: str | None = None) -> dict[str, int]:
    """ready 只表示能立即独占领取的线路；fetching/checking 仅抵扣重复补货。"""
    if conn is None:
        record_store.init()
        with postgres_store.connect() as connection:
            return availability(profile_key, min_ttl=min_ttl, max_age=max_age, conn=connection,
                                profile_keys=profile_keys, source_urls=source_urls, required_region=required_region)
    result = {"ready": 0, "fetching": 0, "checking": 0}
    for row in _available_rows(conn, profile_key, min_ttl=min_ttl, max_age=max_age,
                               profile_keys=profile_keys, source_urls=source_urls, required_region=required_region):
        result[row["state"]] += 1
    return result


def reserve_refill_slots(profile_key: str, provider: str, *, target: int, max_size: int,
                         min_ttl: float, max_age: float, limit: int, timeout: float,
                         reclaim_idle: bool = False, profile_keys: list[str] | None = None,
                         source_urls: list[str] | None = None, required_region: str | None = None) -> list[dict]:
    """在同一容量事务内计算缺口并预留，多个 worker 不会重复补同一份库存。"""
    record_store.init()
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, "proxy-pool-capacity")
        prepared = availability(profile_key, min_ttl=min_ttl, max_age=max_age, conn=conn,
                                profile_keys=profile_keys, source_urls=source_urls, required_region=required_region)
        protected_scope = _inventory_scope(profile_key, profile_keys=profile_keys,
                                            source_urls=source_urls, required_region=required_region) if profile_keys is not None else None
        deficit = max(0, min(target, max_size) - sum(prepared.values()))
        slots = []
        for _ in range(min(max(0, limit), deficit)):
            slot = _reserve_slot(conn, profile_key, provider, max_size=max_size, timeout=timeout,
                                 reclaim_idle=reclaim_idle, protected_scope=protected_scope)
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


def _mark_reuse_exhausted(conn, resource: dict, anchor: dict) -> list[dict]:
    """保留次数耗尽标记，不提前收口其他任务的子租约。"""
    children = _children(conn, anchor["lease_id"])
    record_store.patch_row(RESOURCES, resource["id"], {
        "reuse_exhausted": True,
        "reuse_exhausted_at": _stamp(),
        "state": "shared" if children else "rotation_wait",
        "next_probe_at": _stamp(),
    }, conn=conn)
    resource["reuse_exhausted"] = True
    resource["state"] = "shared" if children else "rotation_wait"
    record_store.patch_row(LEASES, anchor["id"], {"reuse_exhausted": True,
                                                "reuse_exhausted_at": _stamp()}, conn=conn)
    return children


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
    from core.proxy.provider import ProxyLease
    return ProxyLease(
        lease_id=row["lease_id"], provider=row["provider"], proxy_url=row["proxy_url"],
        endpoint=row["endpoint"], acquired_at=datetime.fromisoformat(row["acquired_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]), exit_ip=row.get("exit_ip"), region=row.get("region"),
        metadata={"pool_resource_id": resource["resource_id"], "pool_anchor_id": resource["anchor_lease_id"],
                  "persistent_lease": True, "allow_reuse": shared,
                  **{key: row.get(key) for key in ("purpose", "account_id", "operation_task_id", "operation_run_id",
                                                 "registration_job_id", "route_attempt_no")}},
    )


def claim(profile_key: str, *, min_ttl: float, max_age: float, correlation: dict,
          allow_reuse: bool = False,
          reuse_limit: int = proxy_lease_store.REUSE_LIMIT_DEFAULT,
          profile_keys: list[str] | None = None, source_urls: list[str] | None = None,
          required_region: str | None = None):
    """只领取已检查且寿命足够的库存；此路径不执行任何网络操作。"""
    if allow_reuse and correlation.get("purpose") != "plan-check":
        raise ValueError("只有套餐查询允许共享代理")
    if allow_reuse or correlation.get("purpose") == "plan-check":
        reuse_limit = proxy_lease_store.normalize_reuse_limit(reuse_limit)
    record_store.init()
    scope, scope_params = _inventory_scope(profile_key, profile_keys=profile_keys,
                                           source_urls=source_urls, required_region=required_region)
    reuse_limit_error = None
    with record_store.transaction() as conn, conn.cursor() as cur:
        states = ["ready", "shared"] if allow_reuse else ["ready"]
        exhausted_exit_ip = None
        seen_ids = []
        while True:
            # 每次只锁一个候选，其他并发领取仍可取得其余库存。
            cur.execute(f"SELECT r.* FROM {postgres_store.qualified(RESOURCES.name)} r "
                        f"WHERE {scope} AND r.state = ANY(%s) AND r.expires_at > %s AND r.checked_at >= %s "
                        "AND NOT (r.id = ANY(%s)) ORDER BY r.expires_at, r.id FOR UPDATE OF r SKIP LOCKED LIMIT 1",
                        (*scope_params, states, _stamp(min_ttl), _stamp(-max_age), seen_ids))
            raw = cur.fetchone()
            if raw is None:
                break
            resource = record_store.merge_row(RESOURCES, raw)
            seen_ids.append(resource["id"])
            anchor = record_store.get_row_by(LEASES, "lease_id", resource["anchor_lease_id"], conn=conn, for_update=True)
            if profile_keys is not None and anchor and (
                    anchor.get("provider") != "proxy_pool" or anchor.get("proxy_url") not in source_urls
                    or anchor.get("region") != resource.get("region")):
                continue
            if anchor and anchor["state"] == "recent":
                record_store.patch_row(RESOURCES, resource["id"], {"state": "retired"}, conn=conn)
                continue
            if (not anchor or not anchor.get("endpoint_owner", True) or anchor["state"] != "leased"
                    or str(anchor["expires_at"]) <= _stamp(min_ttl)):
                record_store.patch_row(RESOURCES, resource["id"], {"state": "expired"}, conn=conn)
                _close_anchor(conn, resource, reason="pool_anchor_stale")
                continue
            if not allow_reuse and _children(conn, anchor["lease_id"]):
                continue
            if correlation.get("purpose") == "plan-check" and anchor.get("exit_ip"):
                # 严格套餐查询也会计入后续共享上限；与共享领取共用同一出口锁，
                # 确保计数和插入之间不会被另一个进程穿插。
                record_store.advisory_xact_lock(conn, f"proxy-exit-ip:{anchor['exit_ip']}")
            exit_ip = str(anchor.get("exit_ip") or "").strip()
            if allow_reuse and not exit_ip:
                raise ValueError("共享代理租约必须确认实际出口 IP")
            if (correlation.get("purpose") == "plan-check" and exit_ip
                    and proxy_lease_store.plan_check_exit_ip_count(conn, exit_ip) >= reuse_limit):
                _mark_reuse_exhausted(conn, resource, anchor)
                exhausted_exit_ip = exit_ip
                continue
            allowed = {key: value for key, value in correlation.items() if key in {
                "job_id", "account_id", "purpose", "operation_task_id", "operation_run_id",
                "registration_job_id", "route_attempt_no"}}
            # 锚点负责跨池去重，任务租约单独保存；再次领取不能改写上次任务的关联。
            row = {key: anchor.get(key) for key in ("provider", "endpoint", "proxy_url", "exit_ip", "region", "expires_at")}
            row.update(allowed)
            row.update(lease_id=uuid.uuid4().hex, state="shared_leased" if allow_reuse else "pool_leased", acquired_at=_stamp(),
                       allow_reuse=allow_reuse, pool_resource_id=resource["resource_id"], pool_anchor_id=anchor["lease_id"],
                       delivery_state="reserved", reuse_limit=reuse_limit, claim_max_age=max_age, claim_min_ttl=min_ttl)
            record_store.insert_row(LEASES, row, conn=conn)
            record_store.patch_row(RESOURCES, resource["id"], {"state": "shared" if allow_reuse else "leased",
                                                            "last_used_at": _stamp(), "reuse_limit": reuse_limit}, conn=conn)
            if correlation.get("purpose") == "plan-check" and anchor.get("exit_ip"):
                if proxy_lease_store.plan_check_exit_ip_count(conn, anchor["exit_ip"]) >= reuse_limit:
                    _mark_reuse_exhausted(conn, resource, anchor)
            return _lease_object(row, resource, shared=allow_reuse)
        if correlation.get("purpose") == "plan-check" and not exhausted_exit_ip:
            cur.execute(f"SELECT r.* FROM {postgres_store.qualified(RESOURCES.name)} r "
                        f"WHERE {scope} AND r.state = 'rotation_wait' AND r.expires_at > %s "
                        "AND r.data->>'reuse_exhausted' = 'true' LIMIT 1",
                        (*scope_params, _stamp(min_ttl)))
            waiting = cur.fetchone()
            if waiting:
                exhausted_exit_ip = record_store.merge_row(RESOURCES, waiting).get("exit_ip")
        if exhausted_exit_ip:
            # 先提交耗尽标记，再向调用方报告等待其他线路。
            reuse_limit_error = proxy_lease_store.ProxyReuseLimitError(exhausted_exit_ip, reuse_limit)
    if reuse_limit_error:
        raise reuse_limit_error
    return None


def mark_delivered(lease) -> bool:
    """原子确认任务已收到预留，迟到确认不能复活已取消租约。"""
    with record_store.transaction() as conn:
        row = record_store.get_row_by(LEASES, "lease_id", lease.lease_id, conn=conn, for_update=True)
        if (not row or row["state"] not in {"pool_leased", "shared_leased"}
                or str(row.get("expires_at") or "") <= _stamp()):
            return False
        state = row.get("delivery_state", "delivered")
        if state == "not_delivered":
            return False
        if state == "reserved":
            return record_store.patch_row(LEASES, row["id"], {"delivery_state": "delivered"}, conn=conn)
        return state == "delivered"


def release(lease, *, reason: str, fault: bool = False, cooldown: float = 0,
            before_delivery: bool = False) -> None:
    """任务释放只改变本租约；确定未交付的预留取消才返还额度。"""
    with record_store.transaction() as conn:
        resource = record_store.get_row_by(RESOURCES, "resource_id", lease.metadata["pool_resource_id"], conn=conn, for_update=True)
        row = record_store.get_row_by(LEASES, "lease_id", lease.lease_id, conn=conn, for_update=True)
        if not row or row["state"] not in {"pool_leased", "shared_leased"}:
            return
        shared = row["state"] == "shared_leased"
        # before_delivery 仅由 acquire 返回前的异常路径明确声明，用于确认事务迟到的补偿。
        refundable = row.get("delivery_state") == "reserved" or (
            before_delivery and row.get("delivery_state") == "delivered")
        refund = refundable and reason in {
            "allocation_cancelled", "cancelled_before_delivery", "cancelled", "canceled"}
        current_anchor = None
        if resource and resource.get("anchor_lease_id") == row.get("pool_anchor_id"):
            current_anchor = record_store.get_row_by(LEASES, "lease_id", resource["anchor_lease_id"], conn=conn, for_update=True)
        if row.get("exit_ip") and row.get("purpose") == "plan-check":
            record_store.advisory_xact_lock(conn, f"proxy-exit-ip:{row['exit_ip']}")
        record_store.patch_row(LEASES, row["id"], {
            "state": "released", "released_at": _stamp(), "release_reason": reason[:120],
            "delivery_state": "not_delivered" if refund else row.get("delivery_state", "delivered"),
        }, conn=conn)
        # 旧任务的迟到释放只更新自己的历史，不能隔离或发布当前代。
        if not resource or resource.get("anchor_lease_id") != row.get("pool_anchor_id"):
            return
        if refund and resource.get("reuse_exhausted") and row.get("exit_ip"):
            count = proxy_lease_store.plan_check_exit_ip_count(conn, row["exit_ip"])
            if count < int(row.get("reuse_limit") or proxy_lease_store.REUSE_LIMIT_DEFAULT):
                record_store.patch_row(RESOURCES, resource["id"], {"reuse_exhausted": False,
                    "reuse_exhausted_at": None}, conn=conn)
                resource["reuse_exhausted"] = False
                if current_anchor:
                    record_store.patch_row(LEASES, current_anchor["id"], {"reuse_exhausted": False,
                        "reuse_exhausted_at": None}, conn=conn)
        if fault and not refund:
            record_store.patch_row(RESOURCES, resource["id"], {"state": "quarantine", "last_error_code": "transport_failure"}, conn=conn)
            _close_anchor(conn, resource, reason="pool_fault")
        elif resource["state"] in {"leased", "shared", "rotation_wait"} and not _children(conn, resource["anchor_lease_id"]):
            if resource.get("reuse_exhausted"):
                record_store.patch_row(RESOURCES, resource["id"], {"state": "rotation_wait", "next_probe_at": _stamp()}, conn=conn)
            elif refund and (str(resource["expires_at"]) <= _stamp(float(row.get("claim_min_ttl") or 0))
                             or str(resource.get("checked_at") or "") < _stamp(-float(row.get("claim_max_age") or 60))):
                record_store.patch_row(RESOURCES, resource["id"], {"state": "rotation_wait", "next_probe_at": _stamp()}, conn=conn)
            else:
                record_store.patch_row(RESOURCES, resource["id"], {
                    "state": "cooldown" if not shared and cooldown and not refund else "ready",
                    "cooldown_until": _stamp(cooldown), "last_used_at": _stamp(),
                }, conn=conn)


def maintenance(*, max_age: float, max_idle: float, min_ready: int, min_ttl: float = 0,
                max_size: int | None = None, warm_profiles: set[str] | None = None) -> list[dict]:
    """回收过期/空闲库存，并恢复中断的检查；绝不将失联任务租约再次分配。"""
    # 直接调用存储维护也先合并，避免同进程的重复调用先借连接再竞争锁。
    if not _maintenance_lock.acquire(blocking=False):
        return []
    try:
        record_store.init()
        retired = _maintain_active(
            max_age=max_age, max_idle=max_idle, min_ready=min_ready, min_ttl=min_ttl,
            max_size=max_size, warm_profiles=warm_profiles,
        )
        try:
            _maintain_terminal_history()
        except Exception as exc:
            # 活动状态已提交；历史整理失败留待下一轮，仍交付本轮的内存索引收口。
            logger.warning("代理池历史维护失败：code=proxy_pool_history_maintenance_failed error=%s", type(exc).__name__)
        return retired
    finally:
        _maintenance_lock.release()


def _maintain_active(*, max_age: float, max_idle: float, min_ready: int, min_ttl: float,
                     max_size: int | None, warm_profiles: set[str] | None) -> list[dict]:
    """容量状态使用短事务；忙碌的重复维护不等待容量锁或业务资源行锁。"""
    retired = []
    started = time.monotonic()
    with record_store.transaction() as conn:
        connected = time.monotonic()
        if not record_store.try_advisory_xact_lock(conn, "proxy-pool-capacity"):
            return retired
        locked = time.monotonic()
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {postgres_store.qualified(RESOURCES.name)} "
                "WHERE state IN ('fetching','checking','ready','leased','shared','rotation_wait','cooldown','quarantine') "
                "ORDER BY id DESC FOR UPDATE SKIP LOCKED",
            )
            rows = [record_store.merge_row(RESOURCES, row) for row in cur.fetchall()]
            anchor_ids = list({row["anchor_lease_id"] for row in rows if row.get("anchor_lease_id")})
            cur.execute(
                "WITH locked AS MATERIALIZED (SELECT lease_id FROM "
                f"{postgres_store.qualified(LEASES.name)} WHERE lease_id = ANY(%s) "
                "ORDER BY id FOR UPDATE SKIP LOCKED) "
                "SELECT anchor.lease_id, locked.lease_id IS NOT NULL AS locked FROM "
                f"{postgres_store.qualified(LEASES.name)} anchor LEFT JOIN locked USING (lease_id) "
                "WHERE anchor.lease_id = ANY(%s)", (anchor_ids, anchor_ids),
            )
            busy_anchors = {anchor["lease_id"] for anchor in cur.fetchall() if not anchor["locked"]}
        # 与领取一致先锁资源再锁锚点；跳过忙碌锚点，不在持有容量锁时等待业务租约。
        rows = [row for row in rows if row.get("anchor_lease_id") not in busy_anchors]
        locked_resource_ids = {row["id"] for row in rows}
        # 被其他任务锁定的资源仍计入容量，跳过维护不允许产生额外槽位。
        live_count = record_store.count_rows(RESOURCES, where="state = ANY(%s)", params=(list(LIVE),), conn=conn)
        ready_by_profile: dict[str, list[dict]] = {}
        closed_ready_ids: set[int] = set()
        anchor_resource_ids: dict[str, set[int]] = {}
        for row in rows:
            if row.get("anchor_lease_id"):
                anchor_resource_ids.setdefault(row["anchor_lease_id"], set()).add(row["id"])

        def remove_closed(row):
            ids = anchor_resource_ids.get(row.get("anchor_lease_id"), {row["id"]})
            closed_ready_ids.update(ids)

        for row in rows:
            expired = row["expires_at"] <= _stamp()
            if row["state"] in {"cooldown", "quarantine"}:
                if expired:
                    record_store.patch_row(RESOURCES, row["id"], {"state": "expired"}, conn=conn)
                    _close_anchor(conn, row, reason="pool_expired")
                    remove_closed(row)
                    retired.append(row)
                elif (row["state"] == "quarantine" and row["expires_at"] > _stamp(min_ttl)
                      and not _children(conn, row.get("anchor_lease_id", ""))):
                    record_store.patch_row(RESOURCES, row["id"], {
                        "state": "rotation_wait", "probe_return_state": "quarantine", "next_probe_at": _stamp(),
                    }, conn=conn)
                    live_count += 1
                elif row["state"] == "cooldown" and row.get("cooldown_until", "") <= _stamp():
                    state = "ready" if max_size is None or live_count < max_size else "retired"
                    record_store.patch_row(RESOURCES, row["id"], {"state": state}, conn=conn)
                    if state == "ready":
                        live_count += 1
                        ready_by_profile.pop(row["profile_key"], None)
                    else:
                        _close_anchor(conn, row, reason="pool_capacity_retired")
                        remove_closed(row)
                        retired.append(row)
                continue
            if row["state"] == "shared" and not _children(conn, row["anchor_lease_id"]) and not expired:
                # 子租约仅在显式释放后结束；进程失联仍保留至自然到期。
                if row.get("reuse_exhausted"):
                    record_store.patch_row(RESOURCES, row["id"], {"state": "rotation_wait", "next_probe_at": _stamp()}, conn=conn)
                    row["state"] = "rotation_wait"
                else:
                    record_store.patch_row(RESOURCES, row["id"], {"state": "ready"}, conn=conn)
                    row["state"] = "ready"
                    ready_by_profile.pop(row["profile_key"], None)
            if row["state"] == "checking" and str(row.get("check_deadline") or row["expires_at"]) <= _stamp():
                record_store.patch_row(RESOURCES, row["id"], {
                    "state": "rotation_wait", "owner_token": None, "check_deadline": None,
                    "next_probe_at": _stamp(), "last_error_code": row.get("last_error_code") or "check_interrupted",
                }, conn=conn)
                row["state"] = "rotation_wait"
            idle = row["state"] == "ready" and row["last_used_at"] < _stamp(-max_idle)
            if idle:
                if row["profile_key"] not in ready_by_profile:
                    ready = [item for item in _available_rows(
                        conn, row["profile_key"], min_ttl=min_ttl, max_age=max_age, include_stale=True,
                    ) if item["state"] == "ready" and item["id"] in locked_resource_ids]
                    for item in ready:
                        anchor_resource_ids.setdefault(item["anchor_lease_id"], set()).add(item["id"])
                    ready_by_profile[row["profile_key"]] = ready
                ttl_cutoff, health_cutoff = _stamp(min_ttl), _stamp(-max_age)
                ready = ready_by_profile[row["profile_key"]]
                # 只复用已锁定的状态；绝对寿命和健康期限仍在每次使用时判定。
                recoverable = {item["id"] for item in ready if item["id"] not in closed_ready_ids
                               and item["expires_at"] > ttl_cutoff and item["anchor_expires_at"] > ttl_cutoff}
                available = {item["id"] for item in ready if item["id"] in recoverable
                             and str(item.get("checked_at") or "") >= health_cutoff}
                minimum = min_ready if warm_profiles is None or row["profile_key"] in warm_profiles else 0
                if row["id"] in available:
                    idle = len(available) > minimum
                else:
                    # 检测过期的底数库存先保留供复检，不让供给故障期间丢掉健康旧线路。
                    idle = row["id"] not in recoverable or len(recoverable) > minimum
            too_short = row["state"] in {"ready", "rotation_wait"} and row["expires_at"] <= _stamp(min_ttl)
            over_capacity = (max_size is not None and live_count > max_size
                             and row["state"] in {"ready", "rotation_wait"}
                             and not _children(conn, row.get("anchor_lease_id", "")))
            if expired or idle or too_short or over_capacity:
                state = "expired" if expired else "retired"
                record_store.patch_row(RESOURCES, row["id"], {"state": state, "owner_token": None}, conn=conn)
                _close_anchor(conn, row, reason="pool_expired" if expired else "pool_retired")
                # 同锚点的库存同时失去准入；在本轮集合中扣除，避免逐行重复查询。
                remove_closed(row)
                retired.append(row)
                live_count -= 1
    finished = time.monotonic()
    logger.debug("代理池活动维护：资源=%s 连接等待=%.2fms 容量锁获取=%.2fms 持锁及提交=%.2fms",
                 len(rows), (connected - started) * 1000, (locked - connected) * 1000, (finished - locked) * 1000)
    return retired


def _maintain_terminal_history() -> None:
    """历史修复与清理独立于容量锁，有界处理且保留活跃子租约。"""
    with record_store.transaction() as conn:
        if not record_store.try_advisory_xact_lock(conn, "proxy-pool-history"):
            return
        terminal_repair = record_store.list_rows(
            RESOURCES,
            where="state IN ('failed','retired','expired') AND anchor_lease_id IN ("
                  f"SELECT lease_id FROM {postgres_store.qualified(LEASES.name)} "
                  "WHERE state IN ('pending', 'leased'))",
            conn=conn, limit=200, order_by="id",
        )
        terminal_cleanup = record_store.list_rows(
            RESOURCES, where="state IN ('failed','retired','expired') AND updated_at <= %s",
            params=(_stamp(-_HISTORY_RETENTION_SECONDS),), conn=conn, limit=200, order_by="updated_at, id",
        )
        ids = list({int(row["id"]) for row in (*terminal_repair, *terminal_cleanup)})
        if not ids:
            return
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {postgres_store.qualified(RESOURCES.name)} "
                        "WHERE id = ANY(%s) AND state IN ('failed','retired','expired') "
                        "ORDER BY id FOR UPDATE SKIP LOCKED", (ids,))
            rows = [record_store.merge_row(RESOURCES, row) for row in cur.fetchall()]
        for row in rows:
            _close_anchor(conn, row, reason="pool_terminal_reconcile")
            if _terminal_is_old(row):
                _purge_old_terminal(conn, row)


def take_check(profile_key: str, *, max_age: float, timeout: float, min_ttl: float = 0) -> dict | None:
    """取得健康复检或轮换探测所有权，网络请求由事务外的池执行。"""
    record_store.init()
    with record_store.transaction() as conn, conn.cursor() as cur:
        seen = []
        while True:
            cur.execute(f"SELECT * FROM {postgres_store.qualified(RESOURCES.name)} r WHERE profile_key = %s "
                        "AND ((state = 'ready' AND checked_at < %s) OR "
                        "(state = 'rotation_wait' AND COALESCE(data->>'next_probe_at', '') <= %s)) "
                        "AND NOT (id = ANY(%s)) AND NOT EXISTS (SELECT 1 FROM "
                        f"{postgres_store.qualified(LEASES.name)} child WHERE child.data->>'pool_anchor_id' = r.anchor_lease_id "
                        "AND child.state IN ('pool_leased', 'shared_leased') AND child.expires_at > %s) "
                        "ORDER BY COALESCE(data->>'next_probe_at', checked_at), id "
                        "FOR UPDATE SKIP LOCKED LIMIT 1", (profile_key, _stamp(-max_age), _stamp(), seen, _stamp()))
            raw = cur.fetchone()
            if not raw:
                return None
            row = record_store.merge_row(RESOURCES, raw)
            seen.append(row["id"])
            if row["expires_at"] <= _stamp(min_ttl):
                record_store.patch_row(RESOURCES, row["id"], {"state": "expired" if row["expires_at"] <= _stamp() else "retired"}, conn=conn)
                _close_anchor(conn, row, reason="pool_insufficient_ttl")
                continue
            token = uuid.uuid4().hex
            return_state = row.get("probe_return_state") or row["state"]
            record_store.patch_row(RESOURCES, row["id"], {
                "state": "checking", "owner_token": token, "check_deadline": _stamp(timeout),
                "probe_return_state": return_state,
            }, conn=conn)
            row["owner_token"] = token
            row["probe_return_state"] = return_state
            return row


def _defer_probe(conn, row: dict, *, code: str | None, check_interval: float,
                 max_failures: int, failed: bool) -> bool:
    attempts = int(row.get("probe_attempts") or 0) + 1 if failed else 0
    retired = failed and attempts >= max(1, max_failures)
    updated = record_store.patch_row(RESOURCES, row["id"], {
        "state": "retired" if retired else "rotation_wait", "owner_token": None,
        "check_deadline": None, "next_probe_at": _stamp(max(0, check_interval)),
        "probe_attempts": attempts, "last_error_code": code or row.get("last_error_code"),
    }, conn=conn)
    if retired:
        _close_anchor(conn, row, reason=code or "rotation_failed")
    return updated


def finish_check(resource: dict, *, success: bool, exit_ip: str | None = None,
                 region: str | None = None, min_ttl: float = 0,
                 check_interval: float = 60, max_failures: int = 3) -> bool:
    """接受带所有权的检测结果；出口变化时原子保留旧代并发布新代。"""
    proxy_lease_store._cleanup_expired()
    with record_store.transaction() as conn:
        row = record_store.get_row_by(RESOURCES, "resource_id", resource["resource_id"], conn=conn, for_update=True)
        if (not row or row["state"] != "checking" or row["owner_token"] != resource["owner_token"]
                or row.get("anchor_lease_id") != resource.get("anchor_lease_id")
                or row["expires_at"] <= _stamp() or str(row.get("check_deadline") or "") <= _stamp()):
            return False
        anchor = record_store.get_row_by(LEASES, "lease_id", row["anchor_lease_id"], conn=conn, for_update=True)
        if not anchor or _children(conn, row["anchor_lease_id"]):
            return False
        if row["expires_at"] <= _stamp(min_ttl):
            updated = record_store.patch_row(RESOURCES, row["id"], {"state": "retired", "owner_token": None,
                "last_error_code": "pool_insufficient_ttl"}, conn=conn)
            _close_anchor(conn, row, reason="pool_insufficient_ttl")
            return updated
        observed_ip = str(exit_ip if exit_ip is not None else anchor.get("exit_ip") or "").strip()
        expected_region = str(anchor.get("region") or row.get("region") or "").upper()
        observed_region = str(region if region is not None else expected_region).upper()
        if not success or (expected_region and observed_region != expected_region) or not observed_ip:
            _close_anchor(conn, row, reason="health_check_failed")
            code = "health_check_failed" if not success else "region_mismatch" if observed_ip else "exit_ip_missing"
            return _defer_probe(conn, row, code=code, check_interval=check_interval,
                                max_failures=max_failures, failed=True)
        same_ip = observed_ip == str(anchor.get("exit_ip") or "")
        if same_ip:
            isolated = row.get("probe_return_state") == "quarantine" or row.get("last_error_code") in {
                "transport_failure", "health_check_failed", "region_mismatch", "exit_ip_conflict"}
            if row.get("reuse_exhausted") or isolated:
                return _defer_probe(conn, row, code=None, check_interval=check_interval,
                                    max_failures=max_failures, failed=False)
            return record_store.patch_row(RESOURCES, row["id"], {
                "state": "ready", "owner_token": None, "checked_at": _stamp(), "last_error_code": None,
            }, remove_data_keys=("next_probe_at", "probe_attempts", "probe_return_state", "check_deadline"), conn=conn)
        # 锚点行先锁，随后 endpoint 与按字典序排列的 IP 锁；换代不会等待其他锚点行。
        record_store.advisory_xact_lock(conn, f"proxy-endpoint:{anchor['endpoint']}")
        for ip in sorted({str(anchor.get("exit_ip") or ""), observed_ip} - {""}):
            record_store.advisory_xact_lock(conn, f"proxy-exit-ip:{ip}")
        conflict = record_store.count_rows(LEASES,
            where="exit_ip = %s AND id <> %s AND ((state = 'recent' AND recent_until > %s) OR "
                  "(state IN ('leased', 'shared_leased', 'pool_leased') AND expires_at > %s))",
            params=(observed_ip, anchor["id"], _stamp(), _stamp()), conn=conn)
        exhausted = proxy_lease_store.plan_check_exit_ip_count(conn, observed_ip) >= int(
            row.get("reuse_limit") or proxy_lease_store.REUSE_LIMIT_DEFAULT)
        if conflict or exhausted:
            return _defer_probe(conn, row, code="exit_ip_conflict" if conflict else "exit_ip_reuse_exhausted",
                                check_interval=check_interval, max_failures=max_failures, failed=True)
        if not anchor.get("endpoint_owner", True) or anchor["state"] not in {"leased", "recent"}:
            return False
        record_store.patch_row(LEASES, anchor["id"], {
            "state": "recent", "endpoint_owner": False, "recent_until": row["expires_at"],
            "released_at": anchor.get("released_at") or _stamp(), "release_reason": "pool_rotated",
        }, conn=conn)
        new_anchor_id = uuid.uuid4().hex
        new_anchor = {key: anchor.get(key) for key in ("provider", "endpoint", "proxy_url")}
        new_anchor.update(lease_id=new_anchor_id, state="leased", endpoint_owner=True, purpose="pool-reserve",
                          acquired_at=_stamp(), expires_at=row["expires_at"], exit_ip=observed_ip,
                          region=observed_region)
        record_store.insert_row(LEASES, new_anchor, conn=conn)
        return record_store.patch_row(RESOURCES, row["id"], {
            "anchor_lease_id": new_anchor_id, "state": "ready", "owner_token": None,
            "checked_at": _stamp(), "exit_ip": observed_ip, "region": observed_region,
            "last_error_code": None,
        }, remove_data_keys=("reuse_exhausted", "reuse_exhausted_at", "next_probe_at", "probe_attempts",
                             "probe_return_state", "check_deadline"), conn=conn)


def counts(profile_key: str | None = None) -> dict[str, int]:
    record_store.init()
    with postgres_store.connect() as conn, conn.cursor() as cur:
        where = " WHERE profile_key = %s" if profile_key else ""
        cur.execute(f"SELECT state, count(*) FROM {postgres_store.qualified(RESOURCES.name)}{where} GROUP BY state",
                    (profile_key,) if profile_key else ())
        return {state: int(count) for state, count in cur.fetchall()}


def public_items(limit: int = 200) -> list[dict]:
    from core.proxy.provider import mask_endpoint, mask_ip
    return [{"resource_id": row["resource_id"], "provider": row["provider"], "state": row["state"],
             "region": row.get("region"), "endpoint": mask_endpoint(row.get("endpoint")), "exit_ip": mask_ip(row.get("exit_ip")),
             "checked_at": row.get("checked_at"), "expires_at": row["expires_at"],
             "cooldown_until": row.get("cooldown_until"),
             "next_probe_at": row.get("next_probe_at"), "probe_attempts": int(row.get("probe_attempts") or 0),
             "last_error_code": row.get("last_error_code")} for row in record_store.list_rows(RESOURCES, limit=min(500, max(1, limit)))]
