"""代理供给来源注册表；供应商参数与统一库存生命周期分开维护。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class Source:
    name: str
    label: str
    config_prefix: str
    max_candidates: int
    max_session_minutes: int
    url_builder: Callable[[dict, int], str]
    http_connect_only: bool = False

    def normalize_protocol(self, value: str) -> str:
        from core.proxy import provider as proxy_provider

        try:
            protocol = proxy_provider._normalize_protocol(value)
        except (TypeError, ValueError):
            raise ValueError("代理供应协议配置无效") from None
        # 711 的 HTTP/HTTPS 指通过 HTTP CONNECT 访问 HTTPS 目标，网关仍使用 HTTP。
        return "http" if self.http_connect_only and protocol == "https" else protocol

    def options(self, **overrides) -> dict:
        from config import proxy as cfg

        def value(key, suffix, fallback=None):
            override = overrides.get(key)
            return override if override is not None else getattr(cfg, f"{self.config_prefix}_{suffix}", fallback)

        return {
            "api_url": value("api_url", "API_URL", ""),
            "protocol": value("protocol", "PROTOCOL", "http") or "http",
            "region": value("region", "REGION", getattr(cfg, "PROXY_POOL_DEFAULT_COUNTRY", "")),
            "session_minutes": value("session_minutes", "SESSION_MINUTES", 30),
        }

    def settings(self) -> dict:
        from config import proxy as cfg

        return {
            "acquire_timeout": float(getattr(cfg, f"{self.config_prefix}_ACQUIRE_TIMEOUT")),
            "api_timeout": float(getattr(cfg, f"{self.config_prefix}_API_TIMEOUT")),
            "validate_attempts": int(getattr(cfg, f"{self.config_prefix}_VALIDATE_ATTEMPTS")),
            "recent_ttl": int(getattr(cfg, f"{self.config_prefix}_RECENT_TTL")),
            "acquire_interval": float(getattr(cfg, f"{self.config_prefix}_ACQUIRE_INTERVAL")),
        }

    def build_url(self, options: dict, count: int) -> str:
        from core.proxy import provider as proxy_provider

        try:
            minutes = max(1, min(self.max_session_minutes, int(options["session_minutes"])))
            count = max(1, min(self.max_candidates, int(count)))
        except (TypeError, ValueError):
            raise ValueError("代理供应数量和会话时长必须是整数") from None
        text = str(options.get("api_url") or "").strip()
        if not text:
            raise ValueError(f"未配置 {self.config_prefix}_API_URL，请先填写供应商提取 API")
        parsed = urlsplit(text)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"{self.label} 提取 API 必须是完整的 http(s) URL")
        try:
            region = proxy_provider._normalize_region(options.get("region"))
            protocol = self.normalize_protocol(options.get("protocol", "http"))
        except (TypeError, ValueError):
            raise ValueError("代理供应协议或国家配置无效") from None
        return self.url_builder({**options, "api_url": text, "protocol": protocol, "region": region,
                                 "session_minutes": minutes}, count)


def _build_1024_url(options: dict, count: int) -> str:
    from core.proxy.provider import _build_api_url

    return _build_api_url(options["api_url"], options["session_minutes"], options["region"],
                          count=count, count_limit=1000)


def _build_711_url(options: dict, count: int) -> str:
    parsed = urlsplit(options["api_url"])
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    # 保留面板所选网关、资源池、套餐和授权参数；统一池控制国家、数量和粘性寿命。
    region = options["region"]
    if region and region != "Rand":
        query["region"] = region
    elif region == "Rand":
        query.pop("region", None)
    query.update({
        "count": str(count), "proto": "socks5" if options["protocol"].startswith("socks5") else "http",
        "stype": "text", "split": r"\r\n", "sessType": "sticky", "sessTime": str(options["session_minutes"]),
    })
    # 不允许供应商在粘性窗口内主动换 IP，否则检测结果无法约束后续业务线路。
    query.pop("sessAuto", None)
    return urlunsplit(parsed._replace(query=urlencode(query)))


SOURCES = {
    "1024proxy": Source("1024proxy", "1024Proxy", "PROXY_1024", 1000, 120, _build_1024_url),
    "711proxy": Source("711proxy", "711Proxy", "PROXY_711", 900, 180, _build_711_url, http_connect_only=True),
}


def get_source(name: str = "1024proxy") -> Source:
    source = SOURCES.get(str(name).strip().lower())
    if source is None:
        raise ValueError("不支持的代理供给来源")
    return source


def is_supply_source(name: str) -> bool:
    return name in SOURCES
