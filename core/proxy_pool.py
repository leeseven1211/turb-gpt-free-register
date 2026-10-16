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


def _normalize_country(value: str | None, *, allow_empty: bool = True) -> str:
    """只接受 ISO 3166-1 alpha-2 国家码，拒绝 Rand/未知两位码。"""
    from config.countries import ISO_3166_ALPHA2

    country = str(value or "").strip().upper()
    if not country and allow_empty:
        return ""
    if country == "RAND" or country not in ISO_3166_ALPHA2:
        raise ValueError(f"代理池国家必须是已知 ISO 3166-1 两位代码：{value}")
    return country


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
    last_supply_error: str | None = None
    last_supply_error_class: str | None = None


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
    key = _profile_key(provider, options)
    with _lock:
        profile = _profiles.setdefault(key, Profile(key, provider, dict(options)))
        profile.touched = time.monotonic()
        return profile


def _profile_key(provider: str, options: dict) -> str:
    """根据完整供应商参数生成 profile 键，保留同地区不同配置的历史 profile。"""
    return hashlib.sha256(json.dumps([provider, options], sort_keys=True).encode()).hexdigest()


def _provider_options(**kwargs) -> dict:
    from config import proxy as cfg
    return {"api_url": kwargs.get("api_url") if kwargs.get("api_url") is not None else cfg.PROXY_1024_API_URL,
            "protocol": kwargs.get("protocol") or cfg.PROXY_1024_PROTOCOL,
            "region": kwargs.get("region") if kwargs.get("region") is not None else cfg.PROXY_1024_REGION,
            "session_minutes": kwargs.get("session_minutes") or cfg.PROXY_1024_SESSION_MINUTES}


def _normalize_pool_source(value: str | None) -> str:
    """将池来源配置归一为当前池内适配器名称。

    业务调用方不应选择供应商。这里保留 ``1024proxy`` 和 ``manual`` 两个
    池内来源，旧配置值只用于迁移，不会把新领取路由回 direct 或固定旧平台。
    """
    raw = str(value or "").strip().lower()
    aliases = {
        "1024": "1024proxy",
        "1024proxy": "1024proxy",
        "provider": "1024proxy",
        "provider:1024proxy": "1024proxy",
        "pool": "manual",
        "static_pool": "manual",
        "proxy_pool": "manual",
        "manual": "manual",
    }
    return aliases.get(raw, "manual" if raw in {"direct", "none"} else raw or "manual")


def pool_source() -> str:
    """返回当前统一代理池来源，不读取任何业务动作的供应商选择。

    新配置不存在时兼容旧 ``REGISTRATION_PROXY_MODE`` 与静态池。即使旧值
    是 direct/none，也不会为新业务请求创建直连线路。
    """
    from config import proxy as cfg

    configured = getattr(cfg, "PROXY_POOL_SOURCE", None)
    if str(configured or "").strip():
        source = _normalize_pool_source(configured)
    else:
        legacy = str(getattr(cfg, "REGISTRATION_PROXY_MODE", "") or "").strip().lower()
        if legacy in {"1024", "1024proxy", "provider"}:
            source = "1024proxy"
        elif legacy in {"pool", "static_pool", "proxy_pool"}:
            source = "manual"
        else:
            # 旧 direct/none 只代表历史快照，不应偷偷回退静态池或直连；
            # 统一池的默认来源仍是 1024Proxy，缺配置时明确报错。
            source = "1024proxy"
    if source not in {"1024proxy", "manual"}:
        raise ValueError(f"不支持的代理池来源: {source!r}")
    return source


def default_country() -> str:
    """返回无目标国家领取时使用的池默认国家。"""
    from config import proxy as cfg

    raw = getattr(cfg, "PROXY_POOL_DEFAULT_COUNTRY", None)
    if not str(raw or "").strip():
        raw = getattr(cfg, "PROXY_1024_REGION", "")
    return _normalize_country(raw)


def _pool_countries() -> list[str]:
    """合并默认国家与预热国家，保持配置顺序并去重。"""
    from config import proxy as cfg
    from config.countries import normalize_plan_check_countries, normalize_proxy_pool_countries

    values: list[str] = []
    default = default_country()
    if default:
        values.append(default)
    values.extend(normalize_proxy_pool_countries(getattr(cfg, "PROXY_POOL_COUNTRIES", [])))
    # 套餐多国是业务目标国家，不是供应商选择；当前池应提前准备这些
    # 国家，避免某个动作配置决定是否建立库存 profile。
    values.extend(normalize_plan_check_countries(getattr(cfg, "PLAN_CHECK_COUNTRIES", [])))
    return list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))


def _static_claim_scope(options: dict) -> dict:
    """同一静态来源的国家库存共享端点，不依赖进程内 profile 已恢复。"""
    from config.countries import ISO_3166_ALPHA2

    urls = list(options["urls"])
    # 从同一完整来源稳定推导所有国家键，重启或移除预热国家后仍可领取旧库存。
    keys = [_profile_key("proxy_pool", {"urls": urls})]
    keys.extend(_profile_key("proxy_pool", {"urls": urls, "region": country})
                for country in sorted(ISO_3166_ALPHA2))
    return {"profile_keys": keys, "source_urls": [str(url).strip() for url in urls],
            "required_region": str(options.get("region") or "").strip().upper() or None}


def _configured_profile_options() -> list[tuple[str, dict]]:
    """按当前统一池来源与目标国家建立 profile，不读取业务供应商配置。"""
    from config import proxy as cfg
    source = pool_source()
    countries = _pool_countries()
    profiles: dict[str, tuple[str, dict]] = {}

    def add(provider: str, options: dict) -> None:
        profiles[_profile_key(provider, options)] = (provider, options)

    if source == "1024proxy" and str(getattr(cfg, "PROXY_1024_API_URL", "") or "").strip():
        add("1024proxy", _provider_options(region=default_country() or None))
        for country in countries:
            add("1024proxy", _provider_options(region=country))
    if source == "manual" and list(getattr(cfg, "PROXY_POOL", []) or []):
        urls = list(getattr(cfg, "PROXY_POOL", []) or [])
        add("proxy_pool", {"urls": urls})
        for country in countries:
            add("proxy_pool", {"urls": urls, "region": country})
    return list(profiles.values())


def _public_source_profile(country: str | None) -> tuple[str, dict, dict]:
    """解析一次当前池来源；每次等待轮次都会重新调用以支持热切换。"""
    from config import proxy as cfg

    source = pool_source()
    selected = _normalize_country(country)
    if source == "1024proxy":
        options = _provider_options(region=selected or None)
        if not str(options["api_url"] or "").strip():
            raise ValueError("代理池缺少 1024Proxy 提取配置")
        return "1024proxy", options, {}
    urls = list(getattr(cfg, "PROXY_POOL", []) or [])
    if not urls:
        raise ValueError("统一代理池未配置手动代理地址")
    options = {"urls": urls}
    if selected:
        options["region"] = selected
    return "proxy_pool", options, _static_claim_scope(options)


def _prewarm_plan_country_profiles(policy: dict) -> None:
    """预热当前来源和国家；移除配置后由原有空闲策略回收。"""
    if not _prewarm:
        return
    for provider, options in _configured_profile_options():
        try:
            _validate_lifetime(provider, options, policy)
        except ProxyPoolConfigurationError:
            continue
        _profile(provider, options)


def _current_profile_keys() -> set[str]:
    """只返回当前配置来源的 profile，避免旧来源继续被预热或补货。"""
    try:
        return {_profile_key(provider, options) for provider, options in _configured_profile_options()}
    except (ValueError, TypeError, KeyError):
        # 配置尚未完整时不为历史 profile 补货；领取入口会返回明确配置错误。
        return set()


def _profile_is_current(profile: Profile, configured_keys: set[str] | None = None) -> bool:
    """判断 profile 是否仍属于当前来源和连接配置，国家不参与白名单判断。"""
    if configured_keys and profile.key in configured_keys:
        return True
    try:
        from config import proxy as cfg

        source = pool_source()
        if source == "1024proxy":
            if profile.provider != "1024proxy" or not str(getattr(cfg, "PROXY_1024_API_URL", "") or "").strip():
                return False
            options = _provider_options(region=None)
            if any(profile.options.get(key) != options.get(key)
                   for key in ("api_url", "protocol", "session_minutes")):
                return False
            region = profile.options.get("region")
            _normalize_country(region)
            return True
        urls = [str(url).strip() for url in list(getattr(cfg, "PROXY_POOL", []) or []) if str(url).strip()]
        if profile.provider != "proxy_pool" or not urls:
            return False
        profile_urls = [str(url).strip() for url in profile.options.get("urls", []) if str(url).strip()]
        if profile_urls != urls:
            return False
        _normalize_country(profile.options.get("region"))
        return True
    except (ValueError, TypeError, KeyError):
        return False


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


def acquire_proxy(
    *,
    purpose: str = "registration",
    country: str | None = None,
    region: str | None = None,
    timeout: float | None = None,
    budget: float | None = None,
    progress_callback=None,
    cancel=None,
    account_id: int | None = None,
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    registration_job_id: int | None = None,
    route_attempt_no: int | None = None,
    correlation_id: str | int | None = None,
    job_id: str | int | None = None,
    allow_reuse: bool = False,
    reuse_limit: int | None = None,
):
    """统一业务领取入口。

    业务只提交用途、国家、领取预算和关联 ID；当前代理平台或手动来源由
    池配置决定。``provider``、供应商 API 和手工 URL 仅在本模块内部传给
    底层适配器，避免注册、账号动作和套餐查询重新绕过池。
    """
    selected_region = _normalize_country(country or region) or default_country() or None
    correlation = job_id if job_id is not None else correlation_id
    selected_timeout = timeout if timeout is not None else budget
    common = {
        "purpose": purpose,
        "region": selected_region,
        "timeout": selected_timeout,
        "progress_callback": progress_callback,
        "cancel": cancel,
        "account_id": account_id,
        "operation_task_id": operation_task_id,
        "operation_run_id": operation_run_id,
        "registration_job_id": registration_job_id,
        "route_attempt_no": route_attempt_no,
        "allow_reuse": allow_reuse,
        "reuse_limit": reuse_limit,
    }
    if correlation is not None:
        common["job_id"] = correlation
    common = {key: value for key, value in common.items() if value is not None}
    provider, options, claim_scope = _public_source_profile(selected_region)
    return acquire(
        provider=provider,
        static_urls=options.get("urls"),
        _source_resolver=lambda: _public_source_profile(selected_region),
        _claim_scope=claim_scope,
        **common,
    )


def acquire(*, provider: str = "1024proxy", progress_callback=None, cancel=None, timeout: float | None = None,
            allow_reuse: bool = False, reuse_limit: int | None = None,
            static_urls: list[str] | None = None, _source_resolver=None,
            _claim_scope: dict | None = None, **kwargs):
    """任务只等待已校验库存；默认持续等待，可显式限制领取期限。"""
    from core.operation_runtime import check_cancelled

    policy = settings()
    if _source_resolver is not None:
        provider, options, claim_scope = _source_resolver()
    elif provider == "1024proxy":
        options = _provider_options(**kwargs)
        claim_scope = {}
    else:
        options = {"urls": list(static_urls or [])}
        # 只有调用方明确提供目标国家时才分裂静态池 profile；保持注册和
        # 单国家旧路径的 key 与候选选择不变。
        selected_region = str(kwargs.get("region") or "").strip().upper()
        if selected_region:
            options["region"] = selected_region
        claim_scope = _claim_scope or _static_claim_scope(options)
    if provider == "1024proxy" and not str(options["api_url"] or "").strip():
        raise ValueError("代理池缺少 1024Proxy 提取配置")
    if provider == "proxy_pool" and not options["urls"]:
        raise ValueError("静态代理池为空")
    _validate_lifetime(provider, options, policy)
    profile = _profile(provider, options)
    if _source_resolver is None and provider == "proxy_pool":
        claim_scope = _claim_scope or _static_claim_scope(options)
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

    def switch_profile(next_provider: str, next_options: dict, next_scope: dict) -> None:
        """校验并完成等待计数的原子迁移，失败时保留原 profile 计数。"""
        nonlocal provider, options, claim_scope, profile
        _validate_lifetime(next_provider, next_options, policy)
        next_profile = _profile(next_provider, next_options)
        if next_profile.key == profile.key:
            return
        with _lock:
            profile.waiting -= 1
            next_profile.waiting += 1
        provider, options, claim_scope, profile = next_provider, next_options, next_scope, next_profile

    try:
        start()
        report("正在从代理池申请已校验线路")
        while True:
            checkpoint()
            if _source_resolver is not None:
                # 来源热切换只影响后续实际领取；原 deadline 与关联信息保持不变。
                next_provider, next_options, next_scope = _source_resolver()
                next_key = _profile_key(next_provider, next_options)
                if next_key != profile.key:
                    switch_profile(next_provider, next_options, next_scope)
            if _stop.is_set():
                raise ProxyPoolTimeout("代理池已停止，未分配线路")
            if deadline is not None and time.monotonic() >= deadline:
                raise ProxyPoolTimeout(exhausted_message or "代理池暂时没有符合要求的可用线路，领取等待超时")
            try:
                lease = store.claim(profile.key, min_ttl=policy["min_ttl"], max_age=policy["max_age"],
                                    correlation=correlation, allow_reuse=allow_reuse,
                                    **claim_scope,
                                    **({"reuse_limit": reuse_limit} if allow_reuse else {}))
            except proxy_lease_store.ProxyReuseLimitError as exc:
                # 次数耗尽后仍等待其他库存；所有轮次共用原来的领取期限。
                message = str(exc)
                if message != exhausted_message:
                    report(message)
                exhausted_message = message
                lease = None
            if lease:
                confirming_delivery = False
                lease_returned = False
                try:
                    # 配置可能在数据库领取期间切换；解析异常也必须经过
                    # 下面的补偿路径，不能让已领取租约悬空。
                    if _source_resolver is not None:
                        next_provider, next_options, next_scope = _source_resolver()
                        if _profile_key(next_provider, next_options) != profile.key:
                            store.release(lease, reason="allocation_cancelled", cooldown=0,
                                          before_delivery=True)
                            lease_returned = True
                            switch_profile(next_provider, next_options, next_scope)
                            continue
                    checkpoint()
                    if _stop.is_set() or (deadline is not None and time.monotonic() >= deadline):
                        raise ProxyPoolTimeout("代理池领取已超时或停止，晚到线路已归还")
                    metadata = getattr(lease, "metadata", {})
                    if isinstance(metadata, dict) and metadata.get("pool_resource_id"):
                        confirming_delivery = True
                        if not store.mark_delivered(lease):
                            raise ProxyPoolTimeout("代理池租约已经结束，未交付线路")
                        # 确认事务也可能等待锁或提交；返回调用方前再次检查原期限和取消。
                        checkpoint()
                        if _stop.is_set() or (deadline is not None and time.monotonic() >= deadline):
                            raise ProxyPoolTimeout("代理池领取已超时或停止，晚到线路已归还")
                except BaseException:
                    # 事务确认已提交但尚未返回的线路也可补偿；真实交付后的普通释放不返还次数。
                    if not lease_returned:
                        store.release(lease, reason="allocation_cancelled", cooldown=0,
                                      **({"before_delivery": True} if confirming_delivery else {}))
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
    urls = [str(url).strip() for url in profile.options["urls"] if str(url).strip()]
    if not urls:
        raise RuntimeError("静态代理池为空")
    target_region = str(profile.options.get("region") or "").strip().upper()
    # 槽位 ID 由数据库单调生成，跨轮补充不会重置候选序号。无目标地区时
    # 保持旧行为，只验证一个候选，不引入新的总预算或停止检查。
    start = (int(slot["id"]) - 1) % len(urls)
    from urllib.parse import urlsplit

    if not target_region:
        url = urls[start]
        lease_id = uuid.uuid4().hex
        try:
            parsed = urlsplit(url)
            endpoint = f"{parsed.hostname}:{parsed.port}"
            acquired = datetime.now()
            expires = acquired + timedelta(seconds=max(policy["min_ttl"] * 2, policy["max_idle"] * 2, 600))
            proxy_lease_store.reserve_pending(lease_id=lease_id, provider="proxy_pool", endpoint=endpoint, proxy_url=url,
                                             acquired_at=acquired.isoformat(), expires_at=expires.isoformat(), purpose="pool-reserve")
            exit_ip, region = _validate_proxy_with_retries(url, float(cfg.PROXY_1024_API_TIMEOUT), attempts=1)
            proxy_lease_store.activate(lease_id=lease_id, exit_ip=exit_ip, region=region,
                                       expires_at=expires.isoformat())
            return ProxyLease(lease_id, "proxy_pool", url, endpoint, acquired, expires_at=expires, exit_ip=exit_ip,
                              region=region, metadata={"persistent_lease": True})
        except BaseException:
            proxy_lease_store.abort(lease_id)
            raise

    # 多国家 profile 的候选检测共享一次有界提取预算，避免混合池在每个
    # URL 上重复消耗完整等待时间。每次检测前都检查停止状态。
    candidate_indexes = [(start + offset) % len(urls) for offset in range(len(urls))]
    budget = max(0.0, float(cfg.PROXY_1024_ACQUIRE_TIMEOUT))
    deadline = time.monotonic() + budget
    last_error = None
    for index in candidate_indexes:
        url = urls[index]
        if _stop.is_set():
            raise ProxyPoolTimeout("代理池已停止，未检测后续静态候选")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProxyPoolTimeout("静态代理池候选检测等待超时")
        candidate_timeout = min(float(cfg.PROXY_1024_API_TIMEOUT), remaining)
        lease_id = uuid.uuid4().hex
        try:
            parsed = urlsplit(url)
            endpoint = f"{parsed.hostname}:{parsed.port}"
            acquired = datetime.now()
            expires = acquired + timedelta(seconds=max(policy["min_ttl"] * 2, policy["max_idle"] * 2, 600))
            proxy_lease_store.reserve_pending(lease_id=lease_id, provider="proxy_pool", endpoint=endpoint, proxy_url=url,
                                             acquired_at=acquired.isoformat(), expires_at=expires.isoformat(), purpose="pool-reserve")
            exit_ip, region = _validate_proxy_with_retries(url, candidate_timeout, attempts=1)
        except Exception as exc:
            proxy_lease_store.abort(lease_id)
            last_error = exc
            continue
        except BaseException:
            proxy_lease_store.abort(lease_id)
            raise
        if _stop.is_set():
            proxy_lease_store.abort(lease_id)
            raise ProxyPoolTimeout("代理池已停止，未发布静态候选")
        if time.monotonic() >= deadline:
            proxy_lease_store.abort(lease_id)
            raise ProxyPoolTimeout("静态代理池候选检测等待超时")
        actual_region = str(region or "").strip().upper()
        if actual_region != target_region:
            proxy_lease_store.abort(lease_id)
            continue
        try:
            proxy_lease_store.activate(lease_id=lease_id, exit_ip=exit_ip, region=actual_region,
                                       expires_at=expires.isoformat())
            return ProxyLease(lease_id, "proxy_pool", url, endpoint, acquired, expires_at=expires, exit_ip=exit_ip,
                              region=actual_region, metadata={"persistent_lease": True})
        except Exception as exc:
            proxy_lease_store.abort(lease_id)
            last_error = exc
            continue
        except BaseException:
            proxy_lease_store.abort(lease_id)
            raise
    if target_region:
        raise RuntimeError("静态代理池没有符合目标国家的可用线路") from last_error
    if last_error is not None:
        raise last_error
    raise RuntimeError("静态代理池为空")


def _check(resource: dict, policy: dict) -> None:
    from core.proxy_provider import _validate_proxy_with_retries
    from config import proxy as cfg
    anchor = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", resource["anchor_lease_id"])
    good = False
    exit_ip = region = None
    try:
        if anchor:
            exit_ip, region = _validate_proxy_with_retries(anchor["proxy_url"], float(cfg.PROXY_1024_API_TIMEOUT), attempts=1)
            good = bool(exit_ip) and region == anchor.get("region")
    except Exception:
        good = False
    accepted = store.finish_check(resource, success=good, exit_ip=exit_ip, region=region,
                                  min_ttl=policy["min_ttl"], check_interval=policy["max_age"])
    if not good or not accepted or (anchor and exit_ip != anchor.get("exit_ip")):
        _retire(resource)


def maintain_once(*, role: str = "all") -> bool:
    """一轮检查一条或补充小窗口，逐条交付，不等待整批。"""
    from config import proxy as cfg
    from core import proxy_provider as provider
    global _maintenance_turn
    policy = settings()
    _prewarm_plan_country_profiles(policy)
    current_keys = _current_profile_keys()
    with _lock:
        warm = {item.key for item in _profiles.values()
                if _profile_is_current(item, current_keys)
                and (item.waiting or time.monotonic() - item.touched <= policy["max_idle"])}
    for resource in store.maintenance(max_age=policy["max_age"], max_idle=policy["max_idle"], min_ready=policy["min_ready"],
                                      min_ttl=policy["min_ttl"], max_size=policy["max_size"], warm_profiles=warm):
        _retire(resource)
    with _lock:
        profiles = sorted(_profiles.values(), key=lambda item: (
            not bool(item.waiting), item.last_served, -item.waiting, item.touched,
        ))
        profiles = [item for item in profiles if _profile_is_current(item, current_keys)]
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
        if role != "supply":
            check = store.take_check(profile.key, max_age=policy["max_age"],
                                     timeout=float(cfg.PROXY_1024_ACQUIRE_TIMEOUT) + 30,
                                     min_ttl=policy["min_ttl"])
            if check:
                _check(check, policy)
                return True
        if role == "check":
            continue
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
            **(_static_claim_scope(profile.options) if profile.provider == "proxy_pool" else {}),
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
            profile.last_supply_error = None
            profile.last_supply_error_class = None
            return True
        except Exception as exc:
            if getattr(exc, "code", None) == "supply_candidates_duplicate":
                failure_code = "supply_candidates_duplicate"
            profile.failures += 1
            profile.last_supply_error = failure_code
            profile.last_supply_error_class = type(exc).__name__
            profile.retry_after = time.monotonic() + min(60, 2 ** min(profile.failures, 6))
            logger.warning("代理池补充失败，退避后重试：provider=%s error=%s", profile.provider, type(exc).__name__)
            return bool(delivered)
        finally:
            for unused in slots[delivered:]:
                store.fail_slot(unused, failure_code)
    return False


def _worker(index: int) -> None:
    turn = 0
    while not _stop.is_set():
        try:
            workers = settings()["workers"]
            if index >= workers:
                return
            if index == 0:
                _ensure_workers(workers)
            role = "check" if (workers > 1 and index < workers // 2) else "supply"
            if workers == 1:
                role = "supply" if turn % 2 == 0 else "check"
                turn += 1
            worked = maintain_once(role=role)
        except Exception as exc:
            logger.warning("代理池维护暂不可用：%s", type(exc).__name__)
            worked = False
        if not worked:
            _wake.wait(1)
            _wake.clear()


def snapshot() -> dict:
    policy = settings()
    configured_keys = {_profile_key(provider, options) for provider, options in _configured_profile_options()}
    with _lock:
        waiting = sum(profile.waiting for profile in _profiles.values())
        workers = sum(thread.is_alive() for thread in _threads)
        country_profiles = []
        for profile in _profiles.values():
            if profile.provider not in {"1024proxy", "proxy_pool"}:
                continue
            region = str(profile.options.get("region") or "").strip().upper()
            if not region:
                continue
            counts = dict(store.counts(profile.key))
            active = sum(counts.get(state, 0) for state in ("fetching", "checking", "ready", "leased", "shared", "rotation_wait"))
            configured = profile.key in configured_keys
            # 配置移除后保留仍有等待或活跃库存的历史 profile；仅有空闲索引的 profile 不再展示。
            if configured or profile.waiting > 0 or active > 0:
                country_profiles.append((profile, region, counts, configured))
        country_profiles.sort(key=lambda item: (item[1], not item[3], item[0].provider, item[0].key))
    country_pools = []
    for profile, region, counts, configured in country_profiles:
        country_pools.append({
            "provider": profile.provider,
            "region": region,
            "counts": counts,
            "waiting_local": profile.waiting,
            "target_ready": min(policy["max_size"], profile.waiting + (policy["min_ready"] if configured else 0)),
            "configured": configured,
            "last_supply_error": profile.last_supply_error,
            "last_supply_error_class": profile.last_supply_error_class,
            "retry_after_seconds": max(0, int(profile.retry_after - time.monotonic() + 0.999)),
        })
    required = len(configured_keys) * policy["min_ready"]
    warning = f"各国及来源空闲底数合计 {required}，超过全池容量 {policy['max_size']}" if required > policy["max_size"] else None
    return {"policy": policy, "counts": store.counts(), "waiting_local": waiting,
            "workers_local": workers, "items": store.public_items(), "country_pools": country_pools,
            "min_ready_total": required, "capacity_warning": warning,
            "worker_budget_local": {"supply": (policy["workers"] + 1) // 2,
                                    "check": policy["workers"] // 2,
                                    "alternating": policy["workers"] == 1}}
