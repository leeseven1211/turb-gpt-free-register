"""认证失败的响应头白名单与保守归因，不保存凭据或任意头值。"""
from __future__ import annotations

from collections.abc import Mapping
from email.utils import format_datetime, parsedate_to_datetime
import re


_SERVERS = frozenset({"cloudflare", "nginx", "envoy", "caddy", "awselb/2.0", "amazons3"})
_CONTENT_TYPES = frozenset({
    "text/html", "text/plain", "application/json", "application/problem+json", "application/xhtml+xml",
})
_RAY = re.compile(r"[0-9a-fA-F]{16,32}(?:-[A-Z]{3})?")
_HTTP_DATE = re.compile(r"[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} GMT")


def safe_response_headers(headers: object) -> dict[str, str]:
    """头名和值均受约束；未知服务只记为其他，不透传私有字符串。"""
    if not isinstance(headers, Mapping):
        return {}
    safe = {}
    for name, raw in headers.items():
        if not isinstance(name, str) or not isinstance(raw, str):
            continue
        if len(raw) > 256 or "\r" in raw or "\n" in raw:
            continue
        name, value = name.strip().lower(), raw.strip()
        if name == "server":
            safe[name] = value.lower() if value.lower() in _SERVERS else "其他"
        elif name == "cf-mitigated" and value.lower() == "challenge":
            safe[name] = "challenge"
        elif name == "cf-ray" and _RAY.fullmatch(value):
            safe[name] = value
        elif name == "content-type":
            mime = value.split(";", 1)[0].strip().lower()
            if mime in _CONTENT_TYPES:
                safe[name] = mime
        elif name == "retry-after":
            if re.fullmatch(r"[0-9]{1,9}", value):
                safe[name] = value
            elif _HTTP_DATE.fullmatch(value):
                try:
                    safe[name] = format_datetime(parsedate_to_datetime(value), usegmt=True)
                except (TypeError, ValueError, OverflowError):
                    pass
    return safe


def response_rejection_diagnostic(status: object, headers: Mapping) -> dict[str, str]:
    """CF 经过标志不能证明挑战，更不能证明代理 IP 不可用。"""
    if status != 403:
        return {}
    if headers.get("cf-mitigated") == "challenge":
        return {"kind": "cloudflare_challenge", "label": "检测到 Cloudflare 挑战"}
    if headers.get("server") == "cloudflare" or headers.get("cf-ray"):
        return {"kind": "cloudflare_unconfirmed", "label": "请求经过 Cloudflare，拒绝原因未确认"}
    return {"kind": "http_403_unconfirmed", "label": "HTTP 403，拒绝来源与原因未确认"}
