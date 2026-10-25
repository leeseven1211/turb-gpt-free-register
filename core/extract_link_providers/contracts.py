from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import base64
import binascii
import math
import re
from typing import Literal, Protocol
from urllib.error import HTTPError
from urllib.parse import urlsplit


class ProviderError(RuntimeError):
    """安全的 Provider 错误，不包含远端响应正文或凭据。"""


class ProviderHTTPError(ProviderError):
    """只保留 HTTP 状态码，供原单续查区分失联和临时故障。"""

    def __init__(self, http_status: int):
        if type(http_status) is not int or not 100 <= http_status <= 599:
            raise ValueError("HTTP 状态码无效")
        self.http_status = http_status
        super().__init__(f"平台请求失败（HTTP {http_status}）")


class ProviderUnsupported(ProviderError):
    code = "unsupported"

    def __init__(self):
        super().__init__("Provider 不支持当前操作")


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider_id: str
    api_base: str = field(repr=False)
    cdk: str = field(repr=False)
    capabilities: dict[str, bool] = field(default_factory=dict)
    concurrency: int = 1
    timeout: float = 30.0
    payment_cdk: str = field(default="", repr=False)
    xxsyun_api_key: str = field(default="", repr=False)
    scan_fallback_enabled: bool = False


@dataclass(frozen=True, slots=True)
class ExtractRequest:
    account_id: int
    access_token: str = field(repr=False)
    link_type: str = "pix"
    mode: Literal["extract_only", "manual_payment", "auto_payment"] = "extract_only"
    idempotency_key: str = ""
    options: dict = field(default_factory=dict, repr=False)
    entry_proxy: str | None = field(default=None, repr=False)
    exit_proxy: str | None = field(default=None, repr=False)
    entry_proxies: tuple[str, ...] = field(default=(), repr=False)
    exit_proxies: tuple[str, ...] = field(default=(), repr=False)
    submission_checkpoint: Callable[[dict], None] | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class ProviderJob:
    job_id: str | None = None
    extraction_state: str = "unknown"
    payment_state: str = "not_started"
    links: tuple[str, ...] = field(default=(), repr=False)
    payment_links: tuple[str, ...] = field(default=(), repr=False)
    payment_artifact: dict = field(default_factory=dict, repr=False)
    private_data: dict = field(default_factory=dict, repr=False)
    summary: dict = field(default_factory=dict)


class ExtractLinkProvider(Protocol):
    provider_id: str

    def create_job(self, request: ExtractRequest) -> ProviderJob: ...

    def get_status(self, job_ref: str, *, private_data: dict | None = None) -> ProviderJob: ...

    def start_payment(self, job_ref: str, options: dict) -> ProviderJob: ...


def require_capability(config: ProviderConfig, name: str) -> None:
    if not config.capabilities.get(name, False):
        raise ProviderUnsupported()


def normalize_state(value: object, mapping: dict[str, str]) -> str:
    if not isinstance(value, str):
        return "unknown"
    return mapping.get(value.strip().upper(), "unknown")


def safe_links(*values: object) -> tuple[str, ...]:
    links = []
    for value in values:
        if not isinstance(value, str):
            continue
        if len(value) > 16384 or any(ord(character) < 32 or ord(character) == 127 for character in value):
            continue
        value = value.strip()
        try:
            parsed = urlsplit(value)
            parsed.port
        except ValueError:
            continue
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password and value not in links:
            links.append(value)
    return tuple(links)


def safe_payment_artifact(value: object) -> dict:
    """支付产物使用专门白名单；保留二维码原文，不走日志脱敏或字符串截断。"""
    if not isinstance(value, Mapping):
        return {}
    result = {}
    for name in ("payment_page_url", "payment_url", "qr_image_url_png", "qr_image_url_svg"):
        links = safe_links(value.get(name))
        if links:
            result[name] = links[0]
        elif name == "qr_image_url_png":
            image = value.get(name)
            prefix = "data:image/png;base64,"
            if isinstance(image, str) and image.startswith(prefix) and len(image) <= 2 * 1024 * 1024:
                try:
                    decoded = base64.b64decode(image[len(prefix):], validate=True)
                    if decoded.startswith(b"\x89PNG\r\n\x1a\n"):
                        result[name] = image
                except (ValueError, binascii.Error):
                    pass
    data = value.get("qr_data")
    if isinstance(data, str) and data.strip() and len(data) <= 65536 and "\x00" not in data:
        result["qr_data"] = data
    amount = value.get("amount")
    if type(amount) in (int, float) and 0 <= amount <= 10 ** 18 and math.isfinite(amount):
        result["amount"] = amount
    elif isinstance(amount, str) and re.fullmatch(r"\d{1,16}(?:\.\d{1,8})?", amount.strip()):
        result["amount"] = amount.strip()
    expires = value.get("expires_at")
    if type(expires) in (int, float) and 0 <= expires <= 253402300799 and math.isfinite(expires):
        result["expires_at"] = datetime.fromtimestamp(expires, timezone.utc).isoformat().replace("+00:00", "Z")
    elif isinstance(expires, str) and len(expires) <= 160:
        try:
            parsed_expires = datetime.fromisoformat(expires.strip().replace("Z", "+00:00"))
            if parsed_expires.tzinfo is not None:
                result["expires_at"] = parsed_expires.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except (ValueError, OverflowError, OSError):
            pass
    for name in ("currency", "payment_status", "platform_plus_status"):
        text = value.get(name)
        if isinstance(text, str) and text.strip() and len(text) <= 160 and not any(ord(character) < 32 for character in text):
            result[name] = text.strip()
    return result


def response_dict(response: object) -> dict:
    try:
        data = response.json() if callable(getattr(response, "json", None)) else response
    except Exception:
        raise ProviderError("Provider 返回格式无效") from None
    if not isinstance(data, dict):
        raise ProviderError("Provider 返回格式无效")
    return data


def _http_status(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        status = int(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return status if 100 <= status <= 599 else None


def request(transport, method: str, path: str, *, body=None, headers=None, timeout=30):
    transport_failed = False
    transport_status = None
    try:
        result = transport.request(method, path, json=body, headers=headers or {}, timeout=timeout)
    except ProviderError:
        raise
    except HTTPError as exc:
        transport_failed = True
        transport_status = _http_status(exc.code)
    except Exception as exc:
        transport_failed = True
        transport_status = _http_status(getattr(getattr(exc, "response", None), "status_code", None))
    # 在异常处理块外抛出安全错误，避免保留可能带 URL 或响应正文的原异常链。
    if transport_failed:
        if transport_status is not None and not 200 <= transport_status < 300:
            raise ProviderHTTPError(transport_status)
        raise ProviderError("Provider 请求失败")
    try:
        status_code = getattr(result, "status_code", None)
        if status_code is not None:
            status = _http_status(status_code)
            if status is None:
                raise ProviderError("Provider 请求失败")
            if not 200 <= status < 300:
                raise ProviderHTTPError(status)
        return response_dict(result)
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("Provider 请求失败") from None
