"""统一代理池：后台准备可用库存，任务仅领取和释放租约。"""
from __future__ import annotations

import atexit
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import json
import logging
import threading
import time
import uuid

from core import proxy_pool_store as store, proxy_lease_store, record_store

logger = logging.getLogger(__name__)
_lock = threading.RLock()
_wake = threading.Event()
_stop = threading.Event()
_threads: list[threading.Thread] = []
_profiles: dict[str, "Profile"] = {}
_prewarm = False
_maintenance_turn = 0


class ProxyPoolTimeout(TimeoutError):
    """在领取期限内没有符合用途和寿命要求的可用代理。"""
    code = "proxy_pool_wait_timeout"


class ProxyPoolConfigurationError(ValueError):
    """供给配置不可能满足库存准入条件，禁止反复向供应商提取。"""
    code = "proxy_pool_invalid_lifetime"


@dataclass
class Profile:
    key: str
    provider: str
    options: dict
    waiting: int = 0
    touched: float = field(default_factory=time.monotonic)
    failures: int = 0
    retry_after: float = 0
    last_served: int = 0


def settings() -> dict:
    from config import proxy as cfg
    maximum = max(1, int(cfg.PROXY_POOL_MAX_SIZE))
    minimum = max(0, int(cfg.PROXY_POOL_MIN_READY))
    if minimum > maximum:
        raise ValueError("代理池最小可用数量不能超过最大容量")
    return {"min_ready": minimum, "max_size": maximum,
            "wait_timeout": float(cfg.PROXY_POOL_WAIT_TIMEOUT), "min_ttl": float(cfg.PROXY_POOL_MIN_TTL),
            "max_age": float(cfg.PROXY_POOL_CHECK_INTERVAL), "max_idle": float(cfg.PROXY_POOL_MAX_IDLE),
            "workers": int(cfg.PROXY_POOL_WORKERS)}


def _profile(provider: str, options: dict) -> Profile:
    key = hashlib.sha256(json.dumps([provider, options], sort_keys=True).encode()).hexdigest()
    with _lock:
        profile = _profiles.setdefault(key, Profile(key, provider, dict(options)))
        profile.touched = time.monotonic()
        return profile


def _provider_options(**kwargs) -> dict:
    from config import proxy as cfg
    return {"api_url": kwargs.get("api_url") if kwargs.get("api_url") is not None else cfg.PROXY_1024_API_URL,
            "protocol": kwargs.get("protocol") or cfg.PROXY_1024_PROTOCOL,
            "region": kwargs.get("region") if kwargs.get("region") is not None else cfg.PROXY_1024_REGION,
            "session_minutes": kwargs.get("session_minutes") or cfg.PROXY_1024_SESSION_MINUTES}


def _validate_lifetime(provider: str, options: dict, policy: dict) -> None:
    if provider == "1024proxy":
        lifetime = max(1, min(120, int(options["session_minutes"]))) * 60
        if lifetime <= policy["min_ttl"]:
            raise ProxyPoolConfigurationError("1024Proxy 会话时长必须大于代理池最短剩余寿命，并为出口检测预留时间")


def start(*, prewarm: bool = False) -> None:
    """显式启动或按首次申请启动；重启先收口失效库存，不复活任务租约。"""
    global _prewarm
    policy = settings()
    record_store.init()
    with _lock:
        _prewarm = _prewarm or prewarm
        _stop.clear()
        _ensure_workers(policy["workers"])
    _wake.set()


def _ensure_workers(count: int) -> None:
    with _lock:
        _threads[:] = [thread for thread in _threads if thread.is_alive()]
        names = {thread.name for thread in _threads}
        for index in range(count):
            name = f"proxy-pool-{index}"
            if name not in names:
                thread = threading.Thread(target=_worker, args=(index,), name=name, daemon=True)
                _threads.append(thread)
                thread.start()


def stop() -> None:
    _stop.set()
    _wake.set()
    for thread in list(_threads):
        if thread is not threading.current_thread():
            thread.join(timeout=1)


atexit.register(stop)


def acquire(*, provider: str = "1024proxy", progress_callback=None, cancel=None, timeout: float | None = None,
            allow_reuse: bool = False, reuse_limit: int | None = None,
            static_urls: list[str] | None = None, **kwargs):
    """任务只等待已校验库存；默认持续等待，可显式限制领取期限。"""
    from core.operation_runtime import check_cancelled

    policy = settings()
    options = _provider_options(**kwargs) if provider == "1024proxy" else {"urls": list(static_urls or [])}
    if provider == "1024proxy" and not str(options["api_url"] or "").strip():
        raise ValueError("代理池缺少 1024Proxy 提取配置")
    if provider == "proxy_pool" and not options["urls"]:
        raise ValueError("静态代理池为空")
    _validate_lifetime(provider, options, policy)
    profile = _profile(provider, options)
    purpose = str(kwargs.get("purpose") or "registration")
    if allow_reuse and purpose != "plan-check":
        raise ValueError("仅套餐查询允许复用代理")
    if allow_reuse:
        from config import proxy as cfg
        reuse_limit = int(getattr(cfg, "PLAN_CHECK_PROXY_REUSE_LIMIT", 3) if reuse_limit is None else reuse_limit)
        if not 1 <= reuse_limit <= 100:
            raise ValueError("套餐查询每 IP 最多查询次数必须为 1 到 100")
    correlation = {key: kwargs.get(key) for key in ("job_id", "account_id", "operation_task_id", "operation_run_id", "registration_job_id", "route_attempt_no")}
    correlation["purpose"] = purpose
    started = time.monotonic()
    budget = max(0, float(policy["wait_timeout"] if timeout is None else timeout))
    # 配置为 0 表示持续等待；调用方显式传 timeout=0 仍表示立即到期。
    deadline = started + budget if timeout is not None or budget > 0 else None
    next_notice = started
    exhausted_message = None

    def checkpoint() -> None:
        check_cancelled("任务在等待代理线路时收到取消请求")
        if cancel:
            cancel()

    def report(message: str) -> None:
        if progress_callback:
            progress_callback(message)
        else:
            logger.info("%s", message)

    with _lock:
        profile.waiting += 1
    try:
        start()
        report("正在从代理池申请已校验线路")
        while True:
            checkpoint()
            if _stop.is_set():
                raise ProxyPoolTimeout("代理池已停止，未分配线路")
            if deadline is not None and time.monotonic() >= deadline:
                raise ProxyPoolTimeout(exhausted_message or "代理池暂时没有符合要求的可用线路，领取等待超时")
            try:
                lease = store.claim(profile.key, min_ttl=policy["min_ttl"], max_age=policy["max_age"],
                                    correlation=correlation, allow_reuse=allow_reuse,
                                    **({"reuse_limit": reuse_limit} if allow_reuse else {}))
            except proxy_lease_store.ProxyReuseLimitError as exc:
                # 次数耗尽后仍等待其他库存；所有轮次共用原来的领取期限。
                message = str(exc)
                if message != exhausted_message:
                    report(message)
                exhausted_message = message
                lease = None
            if lease:
                try:
                    checkpoint()
                    if _stop.is_set() or (deadline is not None and time.monotonic() >= deadline):
                        raise ProxyPoolTimeout("代理池领取已超时或停止，晚到线路已归还")
                except BaseException:
                    # 只领取但未交给调用方，不进入实际使用后的冷却期。
                    store.release(lease, reason="allocation_cancelled", cooldown=0)
                    raise
                _wake.set()
                return lease
            if _stop.is_set():
                raise ProxyPoolTimeout("代理池已停止，未分配线路")
            now = time.monotonic()
            if now >= next_notice:
                report(f"代理池暂无符合要求的可用线路，等待后台补货或线路释放（已等待 {int(now - started)} 秒）")
                next_notice = now + 30
            _wake.set()
            _stop.wait(0.2 if deadline is None else min(0.2, max(0, deadline - time.monotonic())))
    finally:
        with _lock:
            profile.waiting -= 1
            profile.touched = time.monotonic()


def _retire(resource: dict) -> None:
    """清理退役锚点的内存索引；持久收口由库存事务原子完成。"""
    if not resource.get("anchor_lease_id"):
        return
    _forget_anchor(resource["anchor_lease_id"])


def _forget_anchor(lease_id: str) -> None:
    from core import proxy_provider as provider
    with provider._STATE_LOCK:
        for endpoint, lease in list(provider._ACTIVE_ENDPOINTS.items()):
            if lease.lease_id == lease_id:
                provider._ACTIVE_ENDPOINTS.pop(endpoint, None)


def release(lease, *, reason: str, fault: bool = False) -> None:
    from config import proxy as cfg
    cooldown = max(0, float(cfg.PROXY_1024_RECENT_TTL)) if lease.provider == "1024proxy" else 0
    store.release(lease, reason=reason, fault=fault, cooldown=cooldown)
    lease.state = "released"
    if not lease.metadata.get("allow_reuse") or fault:
        _forget_anchor(lease.metadata["pool_anchor_id"])
    _wake.set()


def _fetch_static(profile: Profile, slot: dict, policy: dict):
    from core.proxy_provider import ProxyLease, _validate_proxy_with_retries
    from core import proxy_lease_store
    from config import proxy as cfg
    urls = profile.options["urls"]
    # 槽位 ID 由数据库单调生成，跨轮补充不会重置候选序号。
    url = urls[(slot["id"] - 1) % len(urls)]
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    endpoint = f"{parsed.hostname}:{parsed.port}"
    lease_id = uuid.uuid4().hex
    acquired = datetime.now()
    expires = acquired + timedelta(seconds=max(policy["min_ttl"] * 2, policy["max_idle"] * 2, 600))
    proxy_lease_store.reserve_pending(lease_id=lease_id, provider="proxy_pool", endpoint=endpoint, proxy_url=url,
                                     acquired_at=acquired.isoformat(), expires_at=expires.isoformat(), purpose="pool-reserve")
    try:
        exit_ip, region = _validate_proxy_with_retries(url, float(cfg.PROXY_1024_API_TIMEOUT), attempts=1)
        proxy_lease_store.activate(lease_id=lease_id, exit_ip=exit_ip, region=region, expires_at=expires.isoformat())
        return ProxyLease(lease_id, "proxy_pool", url, endpoint, acquired, expires_at=expires, exit_ip=exit_ip,
                          region=region, metadata={"persistent_lease": True})
    except BaseException:
        proxy_lease_store.abort(lease_id)
        raise


def _check(resource: dict, policy: dict) -> None:
    from core.proxy_provider import _validate_proxy_with_retries
    from config import proxy as cfg
    anchor = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", resource["anchor_lease_id"])
    good = False
    try:
        if anchor:
            exit_ip, region = _validate_proxy_with_retries(anchor["proxy_url"], float(cfg.PROXY_1024_API_TIMEOUT), attempts=1)
            good = exit_ip == anchor.get("exit_ip") and region == anchor.get("region")
    except Exception:
        good = False
    accepted = store.finish_check(resource, success=good)
    if not good or not accepted:
        _retire(resource)


def maintain_once() -> bool:
    """一轮检查一条或补充小窗口，逐条交付，不等待整批。"""
    from config import proxy as cfg
    from core import proxy_provider as provider
    global _maintenance_turn
    policy = settings()
    if _prewarm:
        mode = str(cfg.REGISTRATION_PROXY_MODE)
        if mode in {"1024", "1024proxy"} and str(cfg.PROXY_1024_API_URL or "").strip():
            _profile("1024proxy", _provider_options())
        elif mode == "pool" and cfg.PROXY_POOL:
            _profile("proxy_pool", {"urls": list(cfg.PROXY_POOL)})
    with _lock:
        warm = {item.key for item in _profiles.values() if item.waiting or time.monotonic() - item.touched <= policy["max_idle"]}
    for resource in store.maintenance(max_age=policy["max_age"], max_idle=policy["max_idle"], min_ready=policy["min_ready"],
                                      min_ttl=policy["min_ttl"], max_size=policy["max_size"], warm_profiles=warm):
        _retire(resource)
    with _lock:
        profiles = sorted(_profiles.values(), key=lambda item: (
            not bool(item.waiting), item.last_served, -item.waiting, item.touched,
        ))
        # 排序与首个维护机会的预留在同一锁内，两个 worker 不反复抢同一地区。
        if profiles:
            _maintenance_turn += 1
            profiles[0].last_served = _maintenance_turn
    for index, profile in enumerate(profiles):
        if not profile.waiting and time.monotonic() - profile.touched > policy["max_idle"]:
            continue
        if index:
            with _lock:
                _maintenance_turn += 1
                profile.last_served = _maintenance_turn
        try:
            _validate_lifetime(profile.provider, profile.options, policy)
        except ProxyPoolConfigurationError as exc:
            if profile.retry_after <= time.monotonic():
                profile.retry_after = time.monotonic() + 60
                logger.warning("代理池供给配置不兼容，暂停补货：%s", exc)
            continue
        # 先复检已有线路，避免新供应失败时健康旧库存一直无法恢复可领取状态。
        check = store.take_check(profile.key, max_age=policy["max_age"], timeout=float(cfg.PROXY_1024_ACQUIRE_TIMEOUT) + 30)
        if check:
            _check(check, policy)
            return True
        if profile.retry_after > time.monotonic():
            continue
        # 等待任务获得线路后，仍保留配置的空闲底数；占用线路不计入底数。
        target = policy["min_ready"] + profile.waiting
        if profile.provider == "proxy_pool":
            target = min(target, len(profile.options["urls"]))
        slots = store.reserve_refill_slots(
            profile.key, profile.provider, target=target, max_size=policy["max_size"],
            min_ttl=policy["min_ttl"], max_age=policy["max_age"],
            limit=policy["workers"] if profile.provider == "1024proxy" else 1,
            timeout=float(cfg.PROXY_1024_ACQUIRE_TIMEOUT) + 60,
            reclaim_idle=profile.waiting > 0,
        )
        if not slots:
            continue
        delivered = 0
        failure_code = "supply_unavailable"
        try:
            if profile.provider == "1024proxy":
                from core.proxy_supply import fetch_candidates
                # 白名单粘性窗口可能重复返回相同前缀；请求一份有界候选列表，
                # 适配器跳过已占用线路，只检测并交付预留槽位所需的数量。
                candidates = fetch_candidates(profile.options, count=len(slots),
                                              candidate_count=policy["max_size"], cancelled=_stop.is_set)
            else:
                candidates = iter([_fetch_static(profile, slots[0], policy)])
            for lease in candidates:
                if delivered >= len(slots):
                    provider.release_proxy(lease, reason="pool_candidate_unused")
                    continue
                if not lease.expires_at or (lease.expires_at - datetime.now()).total_seconds() <= policy["min_ttl"]:
                    provider.release_proxy(lease, reason="pool_candidate_too_short")
                    continue
                if _stop.is_set() or not store.publish(slots[delivered], lease):
                    provider.release_proxy(lease, reason="pool_candidate_unused")
                    continue
                delivered += 1
                _wake.set()
            if not delivered:
                raise RuntimeError("本轮没有可用候选")
            profile.failures = 0
            profile.retry_after = 0
            return True
        except Exception as exc:
            if getattr(exc, "code", None) == "supply_candidates_duplicate":
                failure_code = "supply_candidates_duplicate"
            profile.failures += 1
            profile.retry_after = time.monotonic() + min(60, 2 ** min(profile.failures, 6))
            logger.warning("代理池补充失败，退避后重试：provider=%s error=%s", profile.provider, type(exc).__name__)
            return bool(delivered)
        finally:
            for unused in slots[delivered:]:
                store.fail_slot(unused, failure_code)
    return False


def _worker(index: int) -> None:
    while not _stop.is_set():
        try:
            workers = settings()["workers"]
            if index >= workers:
                return
            if index == 0:
                _ensure_workers(workers)
            worked = maintain_once()
        except Exception as exc:
            logger.warning("代理池维护暂不可用：%s", type(exc).__name__)
            worked = False
        if not worked:
            _wake.wait(1)
            _wake.clear()


def snapshot() -> dict:
    with _lock:
        waiting = sum(profile.waiting for profile in _profiles.values())
        workers = sum(thread.is_alive() for thread in _threads)
    return {"policy": settings(), "counts": store.counts(), "waiting_local": waiting,
            "workers_local": workers, "items": store.public_items()}
