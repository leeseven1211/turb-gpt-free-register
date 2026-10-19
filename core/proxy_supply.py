"""代理池的通用供应商补充流程；不接收任务或注册批次。"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import logging
import time
import uuid

import requests

from core import proxy_lease_store
from core import proxy_provider as provider
from core.proxy_sources import get_source

logger = logging.getLogger(__name__)


class ProxySupplyDuplicateCandidatesError(RuntimeError):
    """供应商本轮返回的候选都已被库存占用。"""

    code = "supply_candidates_duplicate"

    def __init__(self) -> None:
        super().__init__("代理供应本轮候选均已在库存中，等待下一轮候选")


def _remaining(deadline: float, cap: float = 30) -> float:
    value = min(cap, deadline - time.monotonic())
    if value <= 0:
        raise TimeoutError("代理池本轮补充预算已耗尽")
    return value


def _log_candidate_failure(endpoint: str, exc: requests.RequestException) -> None:
    """候选故障只记录安全字段，避免异常正文带出完整代理或请求 URL。"""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    logger.warning(
        "代理池候选出口检测失败：stage=exit_check class=%s status=%s endpoint=%s",
        type(exc).__name__, status if isinstance(status, int) else "-", provider.mask_endpoint(endpoint),
    )


def _parse_candidates(text: str, *, source: str, label: str) -> list[str]:
    """供应商错误正文可能包含密钥，公开异常只保留固定描述。"""
    if source == "711proxy":
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict) and "code" in payload:
            if str(payload["code"]).strip() != "200":
                raise RuntimeError(f"{label} API 返回业务错误，请检查供应商配置或额度")
    try:
        return provider.parse_proxy_responses(text)
    except (RuntimeError, ValueError, TypeError):
        raise RuntimeError(f"{label} API 未返回可用代理地址") from None


@contextmanager
def _request_lock(deadline: float):
    if not provider._ACQUIRE_LOCK.acquire(timeout=_remaining(deadline, 3600)):
        raise TimeoutError("代理池等待提取锁超时")
    try:
        yield
    finally:
        provider._ACQUIRE_LOCK.release()


def fetch_candidates(
    options: dict,
    *,
    count: int,
    candidate_count: int | None = None,
    cancelled=lambda: False,
    source: str = "1024proxy",
):
    """请求有界候选窗口，先做数据库去重，再只验证需要交付的候选。"""
    adapter = get_source(source)
    settings = adapter.settings()
    deadline = time.monotonic() + float(settings["acquire_timeout"])
    try:
        wanted = max(1, int(count))
    except (TypeError, ValueError) as exc:
        raise ValueError("代理供应交付数量必须是正整数") from exc
    try:
        window = wanted if candidate_count is None else max(wanted, int(candidate_count))
    except (TypeError, ValueError) as exc:
        raise ValueError("代理供应候选窗口必须是正整数") from exc
    minutes = max(1, min(adapter.max_session_minutes, int(options["session_minutes"])))
    protocol = adapter.normalize_protocol(options["protocol"])
    region = provider._normalize_region(options["region"])
    # 大窗口可绕过重复候选前缀；502 时逐级退回旧的 64 条和单条请求。
    window = min(adapter.max_candidates, window)
    effective_options = {**options, "session_minutes": minutes, "protocol": protocol, "region": region}
    url = adapter.build_url(effective_options, window)
    request_counts = [window]
    if window > 64:
        request_counts.append(64)
    if window > 1:
        request_counts.append(1)
    # time 仅按供应商会话时长使用，不把更改时长当成已保证的新会话接口。
    with _request_lock(deadline):
        delay = max(0, float(settings["acquire_interval"]) - (time.monotonic() - provider._LAST_ACQUIRE_AT))
        if delay:
            time.sleep(min(delay, _remaining(deadline, delay)))
        if cancelled():
            return
        acquired = datetime.now()
        expires = acquired + timedelta(minutes=minutes)
        try:
            with provider._direct_session() as session:
                for index, request_count in enumerate(request_counts):
                    request_url = url if request_count == window else adapter.build_url(
                        effective_options, request_count,
                    )
                    try:
                        response = session.get(
                            request_url, timeout=_remaining(deadline, float(settings["api_timeout"])),
                            allow_redirects=False, headers={"Accept": "text/plain, application/json"},
                        )
                        provider._LAST_ACQUIRE_AT = time.monotonic()
                        response.raise_for_status()
                    except requests.HTTPError as exc:
                        provider._LAST_ACQUIRE_AT = time.monotonic()
                        status = getattr(getattr(exc, "response", None), "status_code", None)
                        if status != 502 or index == len(request_counts) - 1:
                            raise
                        delay = max(
                            0, float(settings["acquire_interval"])
                            - (time.monotonic() - provider._LAST_ACQUIRE_AT),
                        )
                        if delay:
                            time.sleep(min(delay, _remaining(deadline, delay)))
                        if cancelled():
                            return
                        continue
                    break
                endpoints = _parse_candidates(response.text, source=adapter.name, label=adapter.label)[:window]
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "代理池供应商提取失败：stage=supply_request class=%s status=%s",
                type(exc).__name__, status if isinstance(status, int) else "-",
            )
            raise
    _remaining(deadline)
    delivered = 0
    duplicate_candidates = 0
    for endpoint in endpoints:
        if delivered >= wanted:
            break
        if cancelled():
            return
        lease_id = uuid.uuid4().hex
        proxy_url = f"{protocol}://{endpoint}"
        reserved = False
        try:
            _remaining(deadline)
            try:
                proxy_lease_store.reserve_pending(
                    lease_id=lease_id, provider=adapter.name, endpoint=endpoint,
                    proxy_url=proxy_url, acquired_at=acquired.isoformat(),
                    expires_at=expires.isoformat(), purpose="pool-reserve",
                )
            except proxy_lease_store.DuplicateProxyLeaseError:
                # 重复候选在数据库占用检查阶段丢弃，不能为它发起出口验证。
                duplicate_candidates += 1
                continue
            reserved = True
            try:
                exit_ip, actual_region = provider._validate_proxy_with_retries(
                    proxy_url, _remaining(deadline, float(settings["api_timeout"])),
                    attempts=int(settings["validate_attempts"]), deadline=deadline,
                )
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                # 网络故障只淘汰当前候选；共同预算和取消仍约束整轮补货。
                _log_candidate_failure(endpoint, exc)
                _remaining(deadline)
                if cancelled():
                    return
                continue
            _remaining(deadline)
            if region and region != "Rand" and actual_region != region:
                raise ValueError("代理出口地区与池配置不符")
            if cancelled():
                return
            proxy_lease_store.activate(lease_id=lease_id, exit_ip=exit_ip, region=actual_region,
                                       expires_at=expires.isoformat())
            lease = provider.ProxyLease(lease_id, adapter.name, proxy_url, endpoint, acquired,
                                        expires_at=expires, exit_ip=exit_ip, region=actual_region,
                                        metadata={"persistent_lease": True, "recent_ttl": int(settings["recent_ttl"]),
                                                  "expiry_source": "configured_session"})
            reserved = False
            delivered += 1
            yield lease
        except (proxy_lease_store.DuplicateProxyLeaseError, ValueError):
            # 不可用候选不进入库存；剩余候选仍可以交付。
            continue
        finally:
            if reserved:
                proxy_lease_store.abort(lease_id)
    if endpoints and delivered == 0 and duplicate_candidates == len(endpoints):
        raise ProxySupplyDuplicateCandidatesError()
