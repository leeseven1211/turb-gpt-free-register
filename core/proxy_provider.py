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


def _build_api_url(api_url: str, session_minutes: int, region: str | None = None) -> str:
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
    query["num"] = "1"
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
    return exit_ip, region


def _cleanup_recent(now: float) -> None:
    expired = [endpoint for endpoint, until in _RECENT_ENDPOINTS.items() if until <= now]
    for endpoint in expired:
        _RECENT_ENDPOINTS.pop(endpoint, None)


def acquire_1024_proxy(
    *,
    api_url: str | None = None,
    protocol: str | None = None,
    region: str | None = None,
    session_minutes: int | None = None,
    validate: bool | None = None,
    job_id: int | str | None = None,
) -> ProxyLease:
    from config import proxy as cfg

    configured_url = api_url if api_url is not None else getattr(cfg, "PROXY_1024_API_URL", "")
    configured_region = region if region is not None else getattr(cfg, "PROXY_1024_REGION", "")
    configured_protocol = protocol if protocol is not None else getattr(cfg, "PROXY_1024_PROTOCOL", "http")
    minutes = max(1, min(120, int(session_minutes if session_minutes is not None else getattr(cfg, "PROXY_1024_SESSION_MINUTES", 30) or 30)))
    rotate_session_time = bool(getattr(cfg, "PROXY_1024_ROTATE_SESSION_TIME", True))
    timeout = float(getattr(cfg, "PROXY_1024_API_TIMEOUT", 12.0) or 12.0)
    attempts = max(1, min(10, int(getattr(cfg, "PROXY_1024_MAX_ATTEMPTS", 3) or 3)))
    should_validate = bool(getattr(cfg, "PROXY_1024_VALIDATE", True)) if validate is None else bool(validate)
    recent_ttl = max(0, int(getattr(cfg, "PROXY_1024_RECENT_TTL", minutes * 60) or 0))
    interval = max(0.0, float(getattr(cfg, "PROXY_1024_ACQUIRE_INTERVAL", 0.6) or 0.0))
    proxy_protocol = _normalize_protocol(configured_protocol)

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
    for attempt in range(1, attempts + 1):
        endpoint = ""
        proxy_url = ""
        endpoint_reserved = False
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
                        raise RuntimeError(f"提取到正在使用或隔离期内的重复代理: {mask_endpoint(endpoint)}")
                    _PENDING_ENDPOINTS.add(endpoint)
                    endpoint_reserved = True

            exit_ip = region = None
            if should_validate:
                exit_ip, region = _validate_proxy(proxy_url, timeout)
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
                    raise RuntimeError(f"提取到正在使用或隔离期内的重复代理: {mask_endpoint(endpoint)}")
                lease = ProxyLease(
                    lease_id=str(uuid.uuid4()),
                    provider="1024proxy",
                    proxy_url=proxy_url,
                    endpoint=endpoint,
                    exit_ip=exit_ip,
                    region=region,
                    acquired_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(minutes=request_minutes),
                    metadata={
                        "job_id": job_id,
                        "recent_ttl": recent_ttl,
                        "uniqueness_key": uniqueness_key,
                        "session_minutes": request_minutes,
                    },
                )
                _ACTIVE_ENDPOINTS[endpoint] = lease
                _PENDING_ENDPOINTS.discard(endpoint)
                endpoint_reserved = False
            logger.info(
                "[代理平台] 已获取 1024Proxy 租约：job=%s endpoint=%s exit=%s region=%s expires=%s",
                job_id or "-", mask_endpoint(endpoint), mask_ip(exit_ip) or "-", region or "-",
                lease.expires_at.isoformat(timespec="seconds") if lease.expires_at else "-",
            )
            return lease
        except Exception as exc:
            if endpoint_reserved:
                with _STATE_LOCK:
                    _PENDING_ENDPOINTS.discard(endpoint)
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
            logger.warning("[代理平台] 第 %s/%s 次获取 1024Proxy 失败：%s", attempt, attempts, errors[-1])
            if attempt < attempts:
                time.sleep(min(2.0, 0.4 * attempt))
    raise RuntimeError("1024Proxy 获取失败：" + "；".join(errors[-3:]))


def acquire_registration_proxy(*, job_id: int | str | None = None) -> ProxyLease:
    from config import proxy as cfg

    mode = registration_proxy_mode()
    if mode == "1024":
        from config import roxybrowser as roxy_cfg

        driver = str(getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
        if driver in {"browser_use", "browseruse", "browser-use", "bu", "skyvern", "sv"}:
            raise RuntimeError("1024Proxy 暂不支持 Browser Use/Skyvern 云端浏览器，请改用 protocol、cloak 或 roxy")
        return acquire_1024_proxy(job_id=job_id)
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
    with _STATE_LOCK:
        _ACTIVE_ENDPOINTS.pop(lease.endpoint, None)
        if recent_ttl > 0:
            _RECENT_ENDPOINTS[lease.endpoint] = now + recent_ttl
            _RECENT_ENDPOINTS[uniqueness_key] = now + recent_ttl
    logger.info("[代理平台] 已释放本地租约：endpoint=%s reason=%s", mask_endpoint(lease.endpoint), reason)


def active_proxy_leases() -> list[dict[str, Any]]:
    with _STATE_LOCK:
        return [lease.public_dict() for lease in _ACTIVE_ENDPOINTS.values()]
