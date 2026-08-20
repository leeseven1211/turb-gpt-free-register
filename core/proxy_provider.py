# -*- coding: utf-8 -*-
"""注册任务的账号级代理租约管理。"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

logger = logging.getLogger(__name__)

_ACQUIRE_LOCK = threading.RLock()
_STATE_LOCK = threading.RLock()
_ACTIVE_ENDPOINTS: dict[str, "ProxyLease"] = {}
_RECENT_ENDPOINTS: dict[str, float] = {}
_PENDING_ENDPOINTS: set[str] = set()
_LAST_ACQUIRE_AT = 0.0
_BATCH_LOCK = threading.RLock()
_BATCH_CONDITION = threading.Condition(_BATCH_LOCK)
_BATCH_STATES: dict[str, "RegistrationProxyBatch"] = {}


class DuplicateProxyError(RuntimeError):
    """平台返回了正在使用或仍处隔离期的重复代理；应快速重取，不做出口检测。"""


@dataclass
class ProxyLease:
    lease_id: str
    provider: str
    proxy_url: str
    endpoint: str
    acquired_at: datetime
    expires_at: datetime | None = None
    exit_ip: str | None = None
    region: str | None = None
    state: str = "leased"
    metadata: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "provider": self.provider,
            "proxy": mask_proxy_url(self.proxy_url),
            "endpoint": mask_endpoint(self.endpoint),
            "exit_ip": mask_ip(self.exit_ip),
            "region": self.region,
            "state": self.state,
            "acquired_at": self.acquired_at.isoformat(timespec="seconds"),
            "expires_at": self.expires_at.isoformat(timespec="seconds") if self.expires_at else None,
        }


@dataclass
class RegistrationProxyBatch:
    batch_id: str
    total_jobs: int
    workers: int
    remaining_jobs: int
    leases: list[ProxyLease] = field(default_factory=list)
    loading: bool = False
    completed_jobs: int = 0
    fetch_count: int = 0


def registration_proxy_mode() -> str:
    from config import proxy as cfg

    mode = str(getattr(cfg, "REGISTRATION_PROXY_MODE", "pool") or "pool").strip().lower()
    aliases = {"1024proxy": "1024", "provider": "1024", "direct": "none", "off": "none"}
    return aliases.get(mode, mode)


def mask_ip(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        ip = ipaddress.ip_address(text)
        if ip.version == 4:
            parts = text.split(".")
            return f"{parts[0]}.{parts[1]}.*.*"
        return f"{ip.exploded.split(':')[0]}:{ip.exploded.split(':')[1]}:***"
    except ValueError:
        return text[:3] + "***" if len(text) > 3 else "***"


def mask_endpoint(endpoint: str | None) -> str:
    text = str(endpoint or "").strip()
    if not text:
        return ""
    host, sep, port = text.rpartition(":")
    if not sep:
        return mask_ip(text) or ""
    return f"{mask_ip(host)}:{port}"


def mask_proxy_url(proxy_url: str | None) -> str:
    text = str(proxy_url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    auth = "***:***@" if parsed.username or parsed.password else ""
    return f"{parsed.scheme}://{auth}{mask_ip(host) or host}{port}"


def _normalize_protocol(value: str) -> str:
    protocol = str(value or "http").strip().lower()
    if protocol not in {"http", "https", "socks5", "socks5h"}:
        raise ValueError(f"1024Proxy 代理协议不支持: {protocol!r}")
    return protocol


def _normalize_region(value: str | None) -> str:
    region = str(value or "").strip()
    if not region:
        return ""
    if region.lower() in {"rand", "random"}:
        return "Rand"
    if not re.fullmatch(r"[A-Za-z]{2}", region):
        raise ValueError("1024Proxy 地区必须是 ISO 两位代码（例如 US / JP），或 Rand")
    return region.upper()


def _build_api_url(
    api_url: str,
    session_minutes: int,
    region: str | None = None,
    *,
    count: int = 1,
) -> str:
    text = str(api_url or "").strip()
    if not text:
        raise RuntimeError("未配置 PROXY_1024_API_URL，请先在 WebUI 的“代理平台”中填写")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("PROXY_1024_API_URL 必须是完整的 http(s) URL")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    configured_region = _normalize_region(region)
    if configured_region:
        query["region"] = configured_region
    query["num"] = str(max(1, min(64, int(count or 1))))
    query["time"] = str(max(1, min(120, int(session_minutes or 30))))
    return urlunparse(parsed._replace(query=urlencode(query)))


def _candidate_from_json(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        for item in payload:
            candidate = _candidate_from_json(item)
            if candidate:
                return candidate
        return ""
    if isinstance(payload, dict):
        ip = payload.get("ip") or payload.get("host") or payload.get("server")
        port = payload.get("port")
        if ip and port:
            return f"{ip}:{port}"
        for key in ("data", "result", "proxy", "proxies", "list"):
            if key in payload:
                candidate = _candidate_from_json(payload[key])
                if candidate:
                    return candidate
    return ""


def _candidates_from_json(payload: Any) -> list[str]:
    if isinstance(payload, str):
        return [payload.strip()] if payload.strip() else []
    if isinstance(payload, list):
        candidates: list[str] = []
        for item in payload:
            candidates.extend(_candidates_from_json(item))
        return candidates
    if isinstance(payload, dict):
        ip = payload.get("ip") or payload.get("host") or payload.get("server")
        port = payload.get("port")
        if ip and port:
            return [f"{ip}:{port}"]
        candidates = []
        for key in ("data", "result", "proxy", "proxies", "list"):
            if key in payload:
                candidates.extend(_candidates_from_json(payload[key]))
        return candidates
    return []


def parse_proxy_response(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        raise RuntimeError("1024Proxy API 返回为空")
    if raw[:1] in "[{":
        try:
            candidate = _candidate_from_json(json.loads(raw))
        except json.JSONDecodeError:
            candidate = ""
    else:
        candidate = ""
    if not candidate:
        candidate = next((line.strip() for line in raw.splitlines() if line.strip()), "")
    candidate = candidate.split(",", 1)[0].strip()
    if "://" in candidate:
        parsed = urlparse(candidate)
        host, port = parsed.hostname, parsed.port
    else:
        match = re.fullmatch(r"\s*([^\s:]+)\s*:\s*(\d{1,5})\s*", candidate)
        if not match:
            raise RuntimeError(f"无法解析 1024Proxy API 响应: {raw[:160]}")
        host, port = match.group(1), int(match.group(2))
    if not host or not port or not (1 <= int(port) <= 65535):
        raise RuntimeError(f"1024Proxy API 返回了非法代理地址: {candidate[:120]}")
    return f"{host}:{int(port)}"


def parse_proxy_responses(text: str) -> list[str]:
    """Parse all proxy endpoints returned by a text or JSON batch response."""
    raw = str(text or "").strip()
    if not raw:
        raise RuntimeError("1024Proxy API 返回为空")
    candidates: list[str]
    if raw[:1] in "[{":
        try:
            candidates = _candidates_from_json(json.loads(raw))
        except json.JSONDecodeError:
            candidates = []
    else:
        candidates = [line.strip() for line in raw.splitlines() if line.strip()]

    parsed: list[str] = []
    errors = 0
    for candidate in candidates:
        try:
            parsed.append(parse_proxy_response(candidate))
        except Exception:
            errors += 1
    parsed = list(dict.fromkeys(parsed))
    if not parsed:
        raise RuntimeError(f"无法解析 1024Proxy 批量响应: {raw[:160]}")
    if errors:
        logger.warning("[代理平台] 批量响应中有 %s 个端点无法解析", errors)
    return parsed


def _direct_session() -> requests.Session:
    session = requests.Session()
    # 白名单 API 必须看到本机真实公网出口，不能继承 HTTP_PROXY/HTTPS_PROXY。
    session.trust_env = False
    return session


def _validate_proxy(proxy_url: str, timeout: float) -> tuple[str | None, str | None]:
    session = _direct_session()
    response = session.get(
        "https://ipinfo.io/json",
        proxies={"http": proxy_url, "https": proxy_url},
        timeout=max(3.0, min(float(timeout or 12.0), 30.0)),
        headers={"Accept": "application/json", "User-Agent": "turb-gpt-free-register/proxy-check"},
    )
    response.raise_for_status()
    payload = response.json()
    exit_ip = str(payload.get("ip") or "").strip() or None
    region = str(payload.get("country") or "").strip().upper() or None
    if not exit_ip:
        raise RuntimeError("代理检测成功但未解析到出口 IP")
    try:
        from core.session import seed_exit_geo

        seed_exit_geo(proxy_url, payload)
    except Exception:
        # GeoIP 缓存是优化项，不能让缓存失败影响代理本身的可用性。
        logger.debug("[代理平台] 写入 BrowserSession GeoIP 缓存失败", exc_info=True)
    return exit_ip, region


def _validate_proxy_with_retries(
    proxy_url: str,
    timeout: float,
    *,
    attempts: int = 2,
) -> tuple[str | None, str | None]:
    """同一端点的瞬时网络/SSL 校验失败先原地重试，避免立刻浪费一条新代理。"""
    attempts = max(1, min(3, int(attempts or 1)))
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _validate_proxy(proxy_url, timeout)
        except Exception as exc:
            last_error = exc
            text = str(exc).lower()
            transient = isinstance(
                exc,
                (requests.Timeout, requests.ConnectionError),
            ) or any(marker in text for marker in (
                "timed out", "timeout", "connection reset", "connection aborted",
                "remote disconnected", "ssl", "temporarily unavailable",
            ))
            if not transient or attempt >= attempts:
                raise
            delay = min(1.0, 0.35 * attempt)
            logger.warning(
                "[代理平台] 出口检测瞬时失败，同一端点 %.2fs 后重试（%s/%s）：%s",
                delay,
                attempt + 1,
                attempts,
                f"{type(exc).__name__}: {str(exc)[:140]}",
            )
            time.sleep(delay)
    raise last_error or RuntimeError("代理出口检测失败")


def _cleanup_recent(now: float) -> None:
    expired = [endpoint for endpoint, until in _RECENT_ENDPOINTS.items() if until <= now]
    for endpoint in expired:
        _RECENT_ENDPOINTS.pop(endpoint, None)


def _persistent_lease_enabled() -> bool:
    from config import proxy as cfg

    return bool(getattr(cfg, "PROXY_1024_PERSIST_LEASES", True))


def _persistent_lease_abort(lease_id: str) -> None:
    try:
        from core import proxy_lease_store

        proxy_lease_store.abort(lease_id)
    except Exception:
        logger.exception("[代理平台] 清理持久化代理租约失败: lease_id=%s", lease_id)


def acquire_1024_proxy(
    *,
    api_url: str | None = None,
    protocol: str | None = None,
    region: str | None = None,
    session_minutes: int | None = None,
    validate: bool | None = None,
    job_id: int | str | None = None,
    progress_callback=None,
) -> ProxyLease:
    from config import proxy as cfg

    configured_url = api_url if api_url is not None else getattr(cfg, "PROXY_1024_API_URL", "")
    configured_region = region if region is not None else getattr(cfg, "PROXY_1024_REGION", "")
    configured_protocol = protocol if protocol is not None else getattr(cfg, "PROXY_1024_PROTOCOL", "http")
    minutes = max(1, min(120, int(session_minutes if session_minutes is not None else getattr(cfg, "PROXY_1024_SESSION_MINUTES", 30) or 30)))
    rotate_session_time = bool(getattr(cfg, "PROXY_1024_ROTATE_SESSION_TIME", True))
    timeout = float(getattr(cfg, "PROXY_1024_API_TIMEOUT", 12.0) or 12.0)
    attempts = max(1, min(10, int(getattr(cfg, "PROXY_1024_MAX_ATTEMPTS", 3) or 3)))
    validate_attempts = max(1, min(3, int(getattr(cfg, "PROXY_1024_VALIDATE_ATTEMPTS", 2) or 2)))
    acquire_timeout = max(timeout, float(getattr(cfg, "PROXY_1024_ACQUIRE_TIMEOUT", 60.0) or 60.0))
    should_validate = bool(getattr(cfg, "PROXY_1024_VALIDATE", True)) if validate is None else bool(validate)
    recent_ttl = max(0, int(getattr(cfg, "PROXY_1024_RECENT_TTL", minutes * 60) or 0))
    interval = max(0.0, float(getattr(cfg, "PROXY_1024_ACQUIRE_INTERVAL", 0.6) or 0.0))
    proxy_protocol = _normalize_protocol(configured_protocol)
    persist_lease = _persistent_lease_enabled()

    def request_minutes_for_attempt(attempt_number: int) -> int:
        if not rotate_session_time or not job_id or minutes >= 120:
            return minutes
        try:
            seed = int(job_id)
        except (TypeError, ValueError):
            seed = int(hashlib.sha256(str(job_id).encode("utf-8")).hexdigest()[:8], 16)
        span = 121 - minutes
        return minutes + ((seed + max(0, attempt_number - 1)) % span)

    global _LAST_ACQUIRE_AT
    errors: list[str] = []
    # 重复端点是平台粘性会话碰撞，不应消耗真正的失败次数；给它额外的快速重取额度，
    # 但仍受整段获取超时约束，避免无限占用 worker。
    max_requests = max(attempts, min(30, attempts * 3))
    substantive_failures = 0
    deadline = time.monotonic() + acquire_timeout
    for attempt in range(1, max_requests + 1):
        if time.monotonic() >= deadline:
            break
        endpoint = ""
        proxy_url = ""
        endpoint_reserved = False
        persistent_reserved = False
        lease_id = str(uuid.uuid4())
        request_minutes = request_minutes_for_attempt(attempt)
        request_url = _build_api_url(configured_url, request_minutes, configured_region)
        try:
            # 只串行化平台提取请求和全局请求间隔。出口检测可能耗时十几秒，
            # 放在锁外并行执行，避免一个慢代理阻塞所有注册任务。
            with _ACQUIRE_LOCK:
                wait_for = interval - (time.monotonic() - _LAST_ACQUIRE_AT)
                if wait_for > 0:
                    time.sleep(wait_for)
                response = _direct_session().get(
                    request_url,
                    timeout=max(3.0, min(timeout, 30.0)),
                    headers={"Accept": "text/plain, application/json", "User-Agent": "turb-gpt-free-register/1024proxy"},
                )
                _LAST_ACQUIRE_AT = time.monotonic()
                response.raise_for_status()
                endpoint = parse_proxy_response(response.text)
                proxy_url = f"{proxy_protocol}://{endpoint}"
                # 端点在检测前先占位。下一任务如果拿到相同粘性代理，可立即
                # 重试，不再浪费一次 IPInfo 检测，也不会并发验证同一端点。
                with _STATE_LOCK:
                    _cleanup_recent(time.time())
                    endpoint_duplicate = (
                        endpoint in _ACTIVE_ENDPOINTS
                        or endpoint in _RECENT_ENDPOINTS
                        or endpoint in _PENDING_ENDPOINTS
                    )
                    if endpoint_duplicate:
                        raise DuplicateProxyError(f"提取到正在使用或隔离期内的重复代理: {mask_endpoint(endpoint)}")
                    _PENDING_ENDPOINTS.add(endpoint)
                    endpoint_reserved = True
                    if persist_lease:
                        from core import proxy_lease_store

                        try:
                            acquired_at = datetime.now()
                            expires_at = acquired_at + timedelta(minutes=request_minutes)
                            proxy_lease_store.reserve_pending(
                                lease_id=lease_id,
                                provider="1024proxy",
                                endpoint=endpoint,
                                proxy_url=proxy_url,
                                acquired_at=acquired_at.isoformat(timespec="seconds"),
                                expires_at=expires_at.isoformat(timespec="seconds"),
                                batch_id=None,
                                job_id=job_id,
                            )
                            persistent_reserved = True
                        except proxy_lease_store.DuplicateProxyLeaseError as exc:
                            raise DuplicateProxyError(str(exc)) from exc
                        except Exception:
                            _persistent_lease_abort(lease_id)
                            raise

            exit_ip = region = None
            if should_validate:
                exit_ip, region = _validate_proxy_with_retries(
                    proxy_url,
                    timeout,
                    attempts=validate_attempts,
                )
                expected_region = _normalize_region(configured_region)
                if expected_region and expected_region != "Rand" and region != expected_region:
                    raise RuntimeError(
                        f"代理实际出口地区不匹配：请求 {expected_region}，检测到 {region or '-'} "
                        f"({mask_ip(exit_ip) or '-'})"
                    )

            now = time.time()
            uniqueness_key = exit_ip or endpoint
            with _STATE_LOCK:
                _cleanup_recent(now)
                duplicate = (
                    endpoint in _ACTIVE_ENDPOINTS
                    or uniqueness_key in _RECENT_ENDPOINTS
                    or any(exit_ip and lease.exit_ip == exit_ip for lease in _ACTIVE_ENDPOINTS.values())
                )
                if duplicate:
                    raise DuplicateProxyError(f"提取到正在使用或隔离期内的重复代理: {mask_endpoint(endpoint)}")
                acquired_at = datetime.now()
                expires_at = acquired_at + timedelta(minutes=request_minutes)
                if persist_lease:
                    from core import proxy_lease_store

                    try:
                        proxy_lease_store.activate(
                            lease_id=lease_id,
                            exit_ip=exit_ip,
                            region=region,
                            expires_at=expires_at.isoformat(timespec="seconds"),
                        )
                    except proxy_lease_store.DuplicateProxyLeaseError as exc:
                        raise DuplicateProxyError(str(exc)) from exc
                lease = ProxyLease(
                    lease_id=lease_id,
                    provider="1024proxy",
                    proxy_url=proxy_url,
                    endpoint=endpoint,
                    exit_ip=exit_ip,
                    region=region,
                    acquired_at=acquired_at,
                    expires_at=expires_at,
                    metadata={
                        "job_id": job_id,
                        "persistent_lease": persist_lease,
                        "recent_ttl": recent_ttl,
                        "uniqueness_key": uniqueness_key,
                        "session_minutes": request_minutes,
                    },
                )
                _ACTIVE_ENDPOINTS[endpoint] = lease
                _PENDING_ENDPOINTS.discard(endpoint)
                endpoint_reserved = False
                persistent_reserved = False
            logger.info(
                "[代理平台] 已获取 1024Proxy 租约：job=%s endpoint=%s exit=%s region=%s expires=%s",
                job_id or "-", mask_endpoint(endpoint), mask_ip(exit_ip) or "-", region or "-",
                lease.expires_at.isoformat(timespec="seconds") if lease.expires_at else "-",
            )
            return lease
        except Exception as exc:
            if persistent_reserved:
                _persistent_lease_abort(lease_id)
                persistent_reserved = False
            if endpoint_reserved:
                with _STATE_LOCK:
                    _PENDING_ENDPOINTS.discard(endpoint)
            # Codex 补跑通过异步异常立即停止线程。它属于控制流信号，不能被代理平台的
            # 普通重试捕获，否则用户点停止后任务仍会继续申请代理并打开登录页。
            if type(exc).__name__ == "CodexRetryStopped" and type(exc).__module__ == "core.codex_retry_service":
                raise
            safe_error = str(exc)
            for secret, replacement in (
                (request_url, "<1024Proxy API>"),
                (str(configured_url or ""), "<1024Proxy API>"),
                (proxy_url, mask_proxy_url(proxy_url)),
                (endpoint, mask_endpoint(endpoint)),
            ):
                if secret:
                    safe_error = safe_error.replace(secret, replacement)
            errors.append(f"{type(exc).__name__}: {safe_error[:180]}")
            duplicate_error = isinstance(exc, DuplicateProxyError)
            if not duplicate_error:
                substantive_failures += 1
            remaining = max(0, int(deadline - time.monotonic()))
            logger.warning(
                "[代理平台] 第 %s/%s 次提取失败（有效失败 %s/%s，剩余约 %ss）：%s",
                attempt,
                max_requests,
                substantive_failures,
                attempts,
                remaining,
                errors[-1],
            )
            if progress_callback is not None:
                try:
                    progress_callback(
                        f"正在获取代理：提取 {attempt}/{max_requests}，"
                        f"有效失败 {substantive_failures}/{attempts}，剩余约 {remaining} 秒"
                    )
                except Exception:
                    logger.debug("[代理平台] 进度上报失败", exc_info=True)
            can_retry = (
                attempt < max_requests
                and time.monotonic() < deadline
                and (duplicate_error or substantive_failures < attempts)
            )
            if not can_retry:
                break
            delay = min(0.5 if duplicate_error else 2.0, 0.2 * attempt if duplicate_error else 0.4 * substantive_failures)
            time.sleep(max(0.05, delay))
    raise RuntimeError("1024Proxy 获取失败：" + "；".join(errors[-3:]))


def acquire_1024_proxy_batch(
    *,
    count: int,
    api_url: str | None = None,
    protocol: str | None = None,
    region: str | None = None,
    session_minutes: int | None = None,
    validate: bool | None = None,
    job_id: int | str | None = None,
    rotation_index: int = 0,
    _refill_depth: int = 0,
    progress_callback=None,
) -> list[ProxyLease]:
    """Fetch and validate a batch of independent 1024Proxy leases."""
    from config import proxy as cfg

    requested_count = max(1, min(64, int(count or 1)))
    configured_url = api_url if api_url is not None else getattr(cfg, "PROXY_1024_API_URL", "")
    configured_region = region if region is not None else getattr(cfg, "PROXY_1024_REGION", "")
    configured_protocol = protocol if protocol is not None else getattr(cfg, "PROXY_1024_PROTOCOL", "http")
    minutes = max(
        1,
        min(
            120,
            int(session_minutes if session_minutes is not None else getattr(cfg, "PROXY_1024_SESSION_MINUTES", 30) or 30),
        ),
    )
    rotate_session_time = bool(getattr(cfg, "PROXY_1024_ROTATE_SESSION_TIME", True))
    timeout = float(getattr(cfg, "PROXY_1024_API_TIMEOUT", 12.0) or 12.0)
    validate_attempts = max(1, min(3, int(getattr(cfg, "PROXY_1024_VALIDATE_ATTEMPTS", 2) or 2)))
    should_validate = bool(getattr(cfg, "PROXY_1024_VALIDATE", True)) if validate is None else bool(validate)
    proxy_protocol = _normalize_protocol(configured_protocol)
    persist_lease = _persistent_lease_enabled()

    if rotate_session_time and job_id and minutes < 120:
        try:
            seed = int(job_id)
        except (TypeError, ValueError):
            seed = int(hashlib.sha256(str(job_id).encode("utf-8")).hexdigest()[:8], 16)
        request_minutes = minutes + ((seed + max(0, int(rotation_index or 0))) % (121 - minutes))
    else:
        request_minutes = minutes

    request_url = _build_api_url(
        configured_url,
        request_minutes,
        configured_region,
        count=requested_count,
    )
    reserved: list[str] = []
    lease_ids: dict[str, str] = {}
    accepted: list[ProxyLease] = []
    errors: list[str] = []
    try:
        global _LAST_ACQUIRE_AT
        with _ACQUIRE_LOCK:
            interval = max(0.0, float(getattr(cfg, "PROXY_1024_ACQUIRE_INTERVAL", 0.6) or 0.0))
            wait_for = interval - (time.monotonic() - _LAST_ACQUIRE_AT)
            if wait_for > 0:
                time.sleep(wait_for)
            response = _direct_session().get(
                request_url,
                timeout=max(3.0, min(timeout, 30.0)),
                headers={"Accept": "text/plain, application/json", "User-Agent": "turb-gpt-free-register/1024proxy-batch"},
            )
            _LAST_ACQUIRE_AT = time.monotonic()
            response.raise_for_status()
            endpoints = parse_proxy_responses(response.text)

        with _STATE_LOCK:
            _cleanup_recent(time.time())
            for endpoint in endpoints:
                if (
                    endpoint in _ACTIVE_ENDPOINTS
                    or endpoint in _RECENT_ENDPOINTS
                    or endpoint in _PENDING_ENDPOINTS
                ):
                    continue
                lease_id = str(uuid.uuid4())
                _PENDING_ENDPOINTS.add(endpoint)
                if persist_lease:
                    from core import proxy_lease_store

                    acquired_at = datetime.now()
                    expires_at = acquired_at + timedelta(minutes=request_minutes)
                    try:
                        proxy_lease_store.reserve_pending(
                            lease_id=lease_id,
                            provider="1024proxy",
                            endpoint=endpoint,
                            proxy_url=f"{proxy_protocol}://{endpoint}",
                            acquired_at=acquired_at.isoformat(timespec="seconds"),
                            expires_at=expires_at.isoformat(timespec="seconds"),
                            batch_id=str(job_id) if job_id is not None else None,
                            job_id=job_id,
                        )
                    except proxy_lease_store.DuplicateProxyLeaseError:
                        _PENDING_ENDPOINTS.discard(endpoint)
                        continue
                    except Exception:
                        _PENDING_ENDPOINTS.discard(endpoint)
                        _persistent_lease_abort(lease_id)
                        raise
                lease_ids[endpoint] = lease_id
                reserved.append(endpoint)
                if len(reserved) >= requested_count:
                    break

        if not reserved:
            raise DuplicateProxyError("1024Proxy 批量返回的端点均已在使用或隔离期内")
        if progress_callback is not None:
            progress_callback(f"批量获取代理：返回 {len(endpoints)} 个，准备并行检测 {len(reserved)} 个")

        expected_region = _normalize_region(configured_region)

        def validate_endpoint(endpoint: str) -> tuple[str, str | None, str | None, str | None]:
            proxy_url = f"{proxy_protocol}://{endpoint}"
            if not should_validate:
                return endpoint, None, None, None
            try:
                exit_ip, actual_region = _validate_proxy_with_retries(
                    proxy_url,
                    timeout,
                    attempts=validate_attempts,
                )
                if expected_region and expected_region != "Rand" and actual_region != expected_region:
                    raise RuntimeError(
                        f"代理实际出口地区不匹配：请求 {expected_region}，检测到 {actual_region or '-'} "
                        f"({mask_ip(exit_ip) or '-'})"
                    )
                return endpoint, exit_ip, actual_region, None
            except Exception as exc:
                return endpoint, None, None, f"{type(exc).__name__}: {str(exc)[:180]}"

        worker_count = max(1, min(len(reserved), 16))
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="proxy-validate") as executor:
            validation_results = list(executor.map(validate_endpoint, reserved))

        now = time.time()
        recent_ttl = max(0, int(getattr(cfg, "PROXY_1024_RECENT_TTL", minutes * 60) or 0))
        accepted_exit_ips: set[str] = set()
        with _STATE_LOCK:
            _cleanup_recent(now)
            for endpoint, exit_ip, actual_region, error in validation_results:
                if error:
                    errors.append(f"{mask_endpoint(endpoint)}: {error}")
                    _PENDING_ENDPOINTS.discard(endpoint)
                    continue
                uniqueness_key = exit_ip or endpoint
                duplicate = (
                    endpoint in _ACTIVE_ENDPOINTS
                    or uniqueness_key in _RECENT_ENDPOINTS
                    or uniqueness_key in accepted_exit_ips
                    or any(exit_ip and lease.exit_ip == exit_ip for lease in _ACTIVE_ENDPOINTS.values())
                )
                if duplicate:
                    errors.append(f"{mask_endpoint(endpoint)}: DuplicateProxyError")
                    _PENDING_ENDPOINTS.discard(endpoint)
                    continue
                acquired_at = datetime.now()
                expires_at = acquired_at + timedelta(minutes=request_minutes)
                if persist_lease:
                    from core import proxy_lease_store

                    try:
                        proxy_lease_store.activate(
                            lease_id=lease_ids[endpoint],
                            exit_ip=exit_ip,
                            region=actual_region,
                            expires_at=expires_at.isoformat(timespec="seconds"),
                        )
                    except proxy_lease_store.DuplicateProxyLeaseError as exc:
                        errors.append(f"{mask_endpoint(endpoint)}: {exc}")
                        _PENDING_ENDPOINTS.discard(endpoint)
                        continue
                lease = ProxyLease(
                    lease_id=lease_ids[endpoint],
                    provider="1024proxy",
                    proxy_url=f"{proxy_protocol}://{endpoint}",
                    endpoint=endpoint,
                    acquired_at=acquired_at,
                    expires_at=expires_at,
                    exit_ip=exit_ip,
                    region=actual_region,
                    metadata={
                        "job_id": job_id,
                        "batch_id": job_id,
                        "persistent_lease": persist_lease,
                        "recent_ttl": recent_ttl,
                        "uniqueness_key": uniqueness_key,
                        "session_minutes": request_minutes,
                    },
                )
                _ACTIVE_ENDPOINTS[endpoint] = lease
                _PENDING_ENDPOINTS.discard(endpoint)
                accepted.append(lease)
                if exit_ip:
                    accepted_exit_ips.add(exit_ip)

        if not accepted:
            raise RuntimeError("1024Proxy 批量检测后没有可用代理：" + "；".join(errors[-3:]))
        if len(accepted) < requested_count and _refill_depth < 2:
            deficit = requested_count - len(accepted)
            try:
                refill = acquire_1024_proxy_batch(
                    count=deficit,
                    api_url=configured_url,
                    protocol=configured_protocol,
                    region=configured_region,
                    session_minutes=minutes,
                    validate=should_validate,
                    job_id=job_id,
                    rotation_index=rotation_index + 1,
                    _refill_depth=_refill_depth + 1,
                    progress_callback=progress_callback,
                )
                accepted.extend(refill)
            except Exception as refill_error:
                logger.warning(
                    "[代理平台] 批量验证后补取 %s 个代理失败，先返回已验证的 %s 个：%s",
                    deficit,
                    len(accepted),
                    str(refill_error)[:180],
                )
        logger.info(
            "[代理平台] 已批量获取 1024Proxy 租约：batch=%s requested=%s accepted=%s region=%s",
            job_id or "-",
            requested_count,
            len(accepted),
            expected_region or "-",
        )
        return accepted
    except Exception as exc:
        safe_error = str(exc)
        for secret, replacement in (
            (request_url, "<1024Proxy API>"),
            (str(configured_url or ""), "<1024Proxy API>"),
        ):
            if secret:
                safe_error = safe_error.replace(secret, replacement)
        raise RuntimeError(f"1024Proxy 批量获取失败：{safe_error[:300]}") from exc
    finally:
        if reserved:
            with _STATE_LOCK:
                for endpoint in reserved:
                    if endpoint not in _ACTIVE_ENDPOINTS:
                        _PENDING_ENDPOINTS.discard(endpoint)
                        if persist_lease and endpoint in lease_ids:
                            _persistent_lease_abort(lease_ids[endpoint])


def _acquire_registration_proxy_from_batch(
    *,
    batch_id: str,
    batch_size: int,
    batch_workers: int,
    job_id: int | str | None,
    progress_callback=None,
) -> ProxyLease:
    batch_key = str(batch_id or "").strip()
    if not batch_key:
        return acquire_1024_proxy(job_id=job_id, progress_callback=progress_callback)
    total_jobs = max(1, int(batch_size or 1))
    workers = max(1, min(16, int(batch_workers or 1)))

    while True:
        with _BATCH_CONDITION:
            state = _BATCH_STATES.get(batch_key)
            if state is None:
                state = RegistrationProxyBatch(
                    batch_id=batch_key,
                    total_jobs=total_jobs,
                    workers=workers,
                    remaining_jobs=total_jobs,
                )
                _BATCH_STATES[batch_key] = state
            if state.leases:
                lease = state.leases.pop(0)
                state.remaining_jobs = max(0, state.remaining_jobs - 1)
                lease.metadata["job_id"] = job_id
                return lease
            if state.remaining_jobs <= 0:
                raise RuntimeError(f"注册批次 {batch_key} 没有可分配的 1024Proxy 租约")
            if state.loading:
                _BATCH_CONDITION.wait(timeout=1.0)
                continue
            state.loading = True
            state.fetch_count += 1
            fetch_count = state.fetch_count
            request_count = min(state.remaining_jobs, 64)

        try:
            leases = acquire_1024_proxy_batch(
                count=request_count,
                job_id=batch_key,
                rotation_index=fetch_count,
                progress_callback=progress_callback,
            )
        except Exception:
            with _BATCH_CONDITION:
                state.loading = False
                _BATCH_CONDITION.notify_all()
            raise

        with _BATCH_CONDITION:
            state.leases.extend(leases)
            state.loading = False
            _BATCH_CONDITION.notify_all()


def finalize_registration_proxy_batch(batch_id: str | None) -> None:
    """Release prefetched but unassigned leases after all batch jobs finish."""
    batch_key = str(batch_id or "").strip()
    if not batch_key:
        return
    leftovers: list[ProxyLease] = []
    with _BATCH_CONDITION:
        state = _BATCH_STATES.get(batch_key)
        if state is None:
            return
        state.completed_jobs += 1
        if state.completed_jobs < state.total_jobs or state.loading:
            return
        leftovers = list(state.leases)
        state.leases.clear()
        _BATCH_STATES.pop(batch_key, None)
        _BATCH_CONDITION.notify_all()
    for lease in leftovers:
        release_proxy(lease, reason="registration_batch_unused")


def discard_registration_proxy_batch(batch_id: str | None) -> None:
    """Drop a batch that stopped before all planned jobs were submitted."""
    batch_key = str(batch_id or "").strip()
    if not batch_key:
        return
    with _BATCH_CONDITION:
        state = _BATCH_STATES.pop(batch_key, None)
        if state is None:
            return
        leftovers = list(state.leases)
        state.leases.clear()
        state.remaining_jobs = 0
        _BATCH_CONDITION.notify_all()
    for lease in leftovers:
        release_proxy(lease, reason="registration_batch_discarded")


def acquire_registration_proxy(
    *,
    job_id: int | str | None = None,
    batch_id: str | None = None,
    batch_size: int = 1,
    batch_workers: int = 1,
    progress_callback=None,
) -> ProxyLease:
    from config import proxy as cfg

    mode = registration_proxy_mode()
    if mode == "1024":
        from config import roxybrowser as roxy_cfg

        driver = str(getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
        if driver in {"browser_use", "browseruse", "browser-use", "bu", "skyvern", "sv"}:
            raise RuntimeError("1024Proxy 暂不支持 Browser Use/Skyvern 云端浏览器，请改用 protocol、cloak 或 roxy")
        if batch_id and int(batch_size or 1) > 1:
            return _acquire_registration_proxy_from_batch(
                batch_id=batch_id,
                batch_size=batch_size,
                batch_workers=batch_workers,
                job_id=job_id,
                progress_callback=progress_callback,
            )
        return acquire_1024_proxy(job_id=job_id, progress_callback=progress_callback)
    if mode == "none":
        return ProxyLease(str(uuid.uuid4()), "direct", "", "", datetime.now(), state="leased")
    if mode != "pool":
        raise RuntimeError(f"不支持的 REGISTRATION_PROXY_MODE={mode!r}，可选 pool / 1024 / none")
    proxy_url = str(cfg.pick_proxy() or "").strip()
    endpoint = proxy_url.rsplit("@", 1)[-1].split("://", 1)[-1] if proxy_url else ""
    return ProxyLease(str(uuid.uuid4()), "proxy_pool" if proxy_url else "direct", proxy_url, endpoint, datetime.now())


def release_proxy(lease: ProxyLease | None, *, reason: str = "completed") -> None:
    if lease is None or lease.state == "released":
        return
    lease.state = "released"
    if lease.provider != "1024proxy":
        return
    now = time.time()
    recent_ttl = max(0, int(lease.metadata.get("recent_ttl") or 0))
    uniqueness_key = str(lease.metadata.get("uniqueness_key") or lease.exit_ip or lease.endpoint)
    if lease.metadata.get("persistent_lease"):
        try:
            from core import proxy_lease_store

            recent_until = None
            if recent_ttl > 0:
                recent_until = datetime.now() + timedelta(seconds=recent_ttl)
            proxy_lease_store.release(
                lease_id=lease.lease_id,
                recent_until=recent_until.isoformat(timespec="seconds") if recent_until else None,
                reason=reason,
            )
        except Exception:
            logger.exception("[代理平台] 写入持久化代理释放状态失败: lease_id=%s", lease.lease_id)
    with _STATE_LOCK:
        _ACTIVE_ENDPOINTS.pop(lease.endpoint, None)
        if recent_ttl > 0:
            _RECENT_ENDPOINTS[lease.endpoint] = now + recent_ttl
            _RECENT_ENDPOINTS[uniqueness_key] = now + recent_ttl
    logger.info("[代理平台] 已释放本地租约：endpoint=%s reason=%s", mask_endpoint(lease.endpoint), reason)


def active_proxy_leases() -> list[dict[str, Any]]:
    with _STATE_LOCK:
        return [lease.public_dict() for lease in _ACTIVE_ENDPOINTS.values()]
