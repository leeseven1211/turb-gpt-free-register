# -*- coding: utf-8 -*-
"""账号相关 OpenAI 功能的统一代理租约。

注册任务、套餐查询、查活和 Codex OAuth 都通过本模块选择线路。
邮箱/短信/CPA/Sub2/提链等第三方或本地服务不应使用这里的付费代理。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from core import db
from core.proxy_provider import (
    ProxyLease,
    acquire_1024_proxy,
    mask_proxy_url,
    registration_proxy_mode,
    release_proxy,
)


@dataclass
class AccountProxyRoute:
    proxy_url: str
    provider: str
    mode: str
    region: str | None = None
    lease: ProxyLease | None = None
    purpose: str = "account_action"

    def public_dict(self) -> dict[str, Any]:
        return {
            "proxy_mode": self.mode,
            "network_route": "proxy" if self.proxy_url else "direct",
            "proxy_provider": self.provider,
            "proxy_used": mask_proxy_url(self.proxy_url) or None,
            "proxy_region": self.region,
            "proxy_fallback_reason": None,
        }

    def release(self, reason: str = "completed") -> None:
        release_proxy(self.lease, reason=reason)


_ACTION_PROXY_CONFIG = {
    "password-setup": "ACCOUNT_PASSWORD_PROXY_MODE",
    "password-change": "ACCOUNT_PASSWORD_PROXY_MODE",
    "twofa-setup": "ACCOUNT_2FA_PROXY_MODE",
    "twofa-retry": "ACCOUNT_2FA_PROXY_MODE",
    "twofa-change": "ACCOUNT_2FA_PROXY_MODE",
    "plan-check": "ACCOUNT_PLAN_CHECK_PROXY_MODE",
    "live-check": "ACCOUNT_LIVE_CHECK_PROXY_MODE",
    "token-refresh": "ACCOUNT_REFRESH_AT_PROXY_MODE",
    "codex-oauth": "ACCOUNT_CODEX_PROXY_MODE",
}
_DEFAULT_ACTION_PROXY_MODES = {
    "ACCOUNT_PASSWORD_PROXY_MODE": "registration",
    "ACCOUNT_2FA_PROXY_MODE": "registration",
    "ACCOUNT_PLAN_CHECK_PROXY_MODE": "direct",
    "ACCOUNT_LIVE_CHECK_PROXY_MODE": "direct",
    "ACCOUNT_REFRESH_AT_PROXY_MODE": "registration",
    "ACCOUNT_CODEX_PROXY_MODE": "registration",
}

# Providers are registered by id so adding another platform does not require
# changing every account action call site.
PROXY_PROVIDER_REGISTRY: dict[str, dict[str, Callable[..., Any]]] = {}


def register_proxy_provider(
    provider_id: str,
    *,
    acquire: Callable[..., AccountProxyRoute],
    status: Callable[[], dict[str, Any]] | None = None,
) -> None:
    normalized = str(provider_id or "").strip().lower()
    if not normalized or ":" in normalized or " " in normalized:
        raise ValueError(f"代理提供商 ID 无效: {provider_id!r}")
    PROXY_PROVIDER_REGISTRY[normalized] = {"acquire": acquire}
    if status is not None:
        PROXY_PROVIDER_REGISTRY[normalized]["status"] = status


def registered_proxy_providers() -> tuple[str, ...]:
    return tuple(sorted(PROXY_PROVIDER_REGISTRY))


def _action_config_key(purpose: str | None) -> str | None:
    normalized = str(purpose or "").strip().lower()
    if normalized in _ACTION_PROXY_CONFIG:
        return _ACTION_PROXY_CONFIG[normalized]
    for prefix, key in _ACTION_PROXY_CONFIG.items():
        if normalized.startswith(prefix + "-"):
            return key
    return None


def normalize_proxy_source(value: str | None, fallback: str = "registration") -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        raw = str(fallback or "registration").strip().lower() or "registration"
    aliases = {
        "auto": "registration",
        "same_as_registration": "registration",
        "registration": "registration",
        "none": "direct",
        "off": "direct",
        "direct": "direct",
        "pool": "pool",
        "static_pool": "pool",
        "proxy_pool": "pool",
        "provider": "provider:1024proxy",
        "platform": "provider:1024proxy",
        "1024": "provider:1024proxy",
        "1024proxy": "provider:1024proxy",
    }
    normalized = aliases.get(raw, raw)
    if normalized.startswith("provider:"):
        provider_id = normalized.split(":", 1)[1].strip()
        if not provider_id or " " in provider_id:
            raise ValueError(f"代理提供商来源无效: {value!r}")
        return f"provider:{provider_id}"
    if normalized not in {"registration", "direct", "pool"}:
        raise ValueError(
            f"代理来源 {value!r} 无效，可选 registration / direct / pool / provider:<id>"
        )
    return normalized


def _configured_action_source(purpose: str | None) -> str:
    from config import account as account_cfg
    from config import proxy as proxy_cfg

    legacy = str(
        getattr(proxy_cfg, "ACCOUNT_ACTION_PROXY_MODE", "registration") or "registration"
    ).strip()
    key = _action_config_key(purpose)
    if not key:
        return legacy
    configured = getattr(account_cfg, key, None)
    if configured is None:
        return legacy
    # An old .env can still contain only ACCOUNT_ACTION_PROXY_MODE. Let it
    # override the new source-level default until the new key is explicitly set.
    if not str(os.environ.get(key) or "").strip():
        try:
            legacy_source = normalize_proxy_source(legacy)
        except ValueError:
            legacy_source = "registration"
        default = _DEFAULT_ACTION_PROXY_MODES.get(key)
        if legacy_source != "registration" and str(configured).strip().lower() == default:
            return legacy
    return str(configured)


def _resolve_proxy_source(source: str | None) -> str:
    normalized = normalize_proxy_source(source)
    if normalized != "registration":
        return normalized
    registration = str(registration_proxy_mode() or "none").strip().lower()
    if registration in {"none", "direct"}:
        return "direct"
    if registration == "pool":
        return "pool"
    if registration in {"1024", "1024proxy", "provider"}:
        return "provider:1024proxy"
    raise ValueError(f"不支持的注册代理来源: {registration!r}")


def account_action_proxy_mode(purpose: str | None = None) -> str:
    return _resolve_proxy_source(_configured_action_source(purpose))


def _region_from_extra(account: dict) -> str:
    raw = account.get("extra_json")
    if not raw:
        return ""
    try:
        extra = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    for provider in ("browser_use", "skyvern"):
        value = str(((extra.get(provider) or {}).get("proxy_country_code") or "")).strip().upper()
        if len(value) == 2:
            return value
    return ""


def resolve_account_region(*, account_id: int | None = None, email: str | None = None) -> str:
    """返回账号注册时的实际出口国家；历史账号优先从成功注册任务回溯。"""
    account = None
    if account_id is not None:
        account = db.get_account(int(account_id))
    if account is None and email:
        account = db.get_account_by_email(str(email))
    if account:
        saved = str(account.get("registration_proxy_region") or "").strip().upper()
        if len(saved) == 2:
            return saved
        inferred = _region_from_extra(account)
        if inferred:
            return inferred
        target_id = int(account.get("id") or 0)
        target_email = str(account.get("email") or "").strip().lower()
        for job in db.list_jobs(limit=5000):
            same_account = target_id and int(job.get("account_id") or 0) == target_id
            same_email = target_email and str(job.get("email") or "").strip().lower() == target_email
            if not (same_account or same_email):
                continue
            region = str(job.get("proxy_region") or "").strip().upper()
            if len(region) == 2:
                return region

    from config import proxy as cfg
    configured = str(getattr(cfg, "PROXY_1024_REGION", "") or "").strip().upper()
    return configured if len(configured) == 2 else ""


def proxy_configuration_status(purpose: str | None = None) -> dict[str, Any]:
    """返回账号功能代理是否已配置，不执行网络请求。"""
    try:
        mode = account_action_proxy_mode(purpose)
    except Exception as exc:
        return {"ok": False, "mode": "invalid", "reason": str(exc)}
    from config import proxy as cfg
    if mode.startswith("provider:"):
        provider_id = mode.split(":", 1)[1]
        spec = PROXY_PROVIDER_REGISTRY.get(provider_id)
        if spec is None:
            return {"ok": False, "mode": mode, "reason": f"未注册代理提供商: {provider_id}"}
        status = spec.get("status")
        if status is not None:
            return {"mode": mode, **status()}
    elif mode == "pool":
        fixed = str(getattr(cfg, "ACCOUNT_ACTION_PROXY", "") or "").strip()
        if not fixed and not list(getattr(cfg, "PROXY_POOL", []) or []):
            return {"ok": False, "mode": mode, "reason": "账号功能代理池为空"}
    return {"ok": True, "mode": mode, "reason": None}


def acquire_account_proxy(
    *,
    account_id: int | None = None,
    email: str | None = None,
    purpose: str,
    explicit_proxy: str | None = None,
    region: str | None = None,
    source: str | None = None,
) -> AccountProxyRoute:
    """为一次账号功能调用获取线路；调用方必须在 finally 中 release。"""
    if explicit_proxy is not None:
        selected = str(explicit_proxy or "").strip()
        return AccountProxyRoute(
            proxy_url=selected,
            provider="request" if selected else "direct",
            mode="request",
            region=str(region or "").strip().upper() or None,
            purpose=purpose,
        )

    mode = account_action_proxy_mode(purpose) if source is None else _resolve_proxy_source(source)
    if mode == "direct":
        return AccountProxyRoute("", "direct", mode, purpose=purpose)

    from config import proxy as cfg
    if mode == "pool":
        selected = str(getattr(cfg, "ACCOUNT_ACTION_PROXY", "") or "").strip()
        if not selected:
            selected = str(cfg.pick_proxy() or "").strip()
        if not selected:
            raise RuntimeError("账号功能代理来源为 pool，但 ACCOUNT_ACTION_PROXY/PROXY_POOL 均为空")
        return AccountProxyRoute(selected, "proxy_pool", mode, purpose=purpose)

    if not mode.startswith("provider:"):
        raise RuntimeError(f"不支持的账号代理来源: {mode}")
    provider_id = mode.split(":", 1)[1]
    spec = PROXY_PROVIDER_REGISTRY.get(provider_id)
    if spec is None:
        raise RuntimeError(f"未注册代理提供商: {provider_id}")
    return spec["acquire"](
        account_id=account_id,
        email=email,
        purpose=purpose,
        region=region,
        mode=mode,
    )


def _status_1024proxy() -> dict[str, Any]:
    from config import proxy as cfg

    if not str(getattr(cfg, "PROXY_1024_API_URL", "") or "").strip():
        return {"ok": False, "reason": "未配置 1024Proxy 提取 API"}
    if not bool(getattr(cfg, "PROXY_1024_VALIDATE", True)):
        return {"ok": False, "reason": "代理平台必须开启使用前出口检测"}
    return {"ok": True, "reason": None}


def _acquire_1024proxy(
    *,
    account_id: int | None,
    email: str | None,
    purpose: str,
    region: str | None,
    mode: str,
) -> AccountProxyRoute:
    selected_region = str(region or "").strip().upper() or resolve_account_region(
        account_id=account_id,
        email=email,
    )
    if not selected_region:
        raise RuntimeError("无法确定账号注册国家，拒绝使用随机地区代理查询")
    lease = acquire_1024_proxy(
        region=selected_region,
        validate=True,
        job_id=f"{purpose}-{account_id or email or datetime.now().timestamp()}",
    )
    return AccountProxyRoute(
        proxy_url=lease.proxy_url,
        provider=lease.provider,
        mode=mode,
        region=lease.region or selected_region,
        lease=lease,
        purpose=purpose,
    )


register_proxy_provider("1024proxy", acquire=_acquire_1024proxy, status=_status_1024proxy)
