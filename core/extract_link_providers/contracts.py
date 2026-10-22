from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol
from urllib.parse import urlsplit


class ProviderError(RuntimeError):
    """安全的 Provider 错误，不包含远端响应正文或凭据。"""


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


@dataclass(frozen=True, slots=True)
class ProviderJob:
    job_id: str | None = None
    extraction_state: str = "unknown"
    payment_state: str = "not_started"
    links: tuple[str, ...] = field(default=(), repr=False)
    payment_links: tuple[str, ...] = field(default=(), repr=False)
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
        value = value.strip()
        try:
            parsed = urlsplit(value)
        except ValueError:
            continue
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password and value not in links:
            links.append(value)
    return tuple(links)


def response_dict(response: object) -> dict:
    try:
        data = response.json() if callable(getattr(response, "json", None)) else response
    except Exception:
        raise ProviderError("Provider 返回格式无效") from None
    if not isinstance(data, dict):
        raise ProviderError("Provider 返回格式无效")
    return data


def request(transport, method: str, path: str, *, body=None, headers=None, timeout=30):
    try:
        result = transport.request(method, path, json=body, headers=headers or {}, timeout=timeout)
        status_code = getattr(result, "status_code", None)
        if status_code is not None and not 200 <= int(status_code) < 300:
            raise ProviderError(f"Provider 请求失败（HTTP {int(status_code)}）")
        return response_dict(result)
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("Provider 请求失败") from None
