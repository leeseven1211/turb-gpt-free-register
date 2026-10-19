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
            "proxy_allow_reuse": bool(self.lease and self.lease.metadata.get("allow_reuse")),
        }

    def release(self, reason: str = "completed", *, fault: bool | None = None) -> None:
        """释放账号线路；只有调用方明确确认代理传输故障时才隔离线路。"""
        release_proxy(self.lease, reason=reason, fault=fault)


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
    "email-change": "ACCOUNT_EMAIL_CHANGE_PROXY_MODE",
}
_DEFAULT_ACTION_PROXY_MODES = {
    "ACCOUNT_PASSWORD_PROXY_MODE": "registration",
    "ACCOUNT_2FA_PROXY_MODE": "registration",
    "ACCOUNT_PLAN_CHECK_PROXY_MODE": "direct",
    "ACCOUNT_LIVE_CHECK_PROXY_MODE": "direct",
    "ACCOUNT_REFRESH_AT_PROXY_MODE": "registration",
    "ACCOUNT_CODEX_PROXY_MODE": "registration",
    "ACCOUNT_EMAIL_CHANGE_PROXY_MODE": "registration",
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
    # source 可能来自旧任务快照。它只用于兼容解析，不能让新领取固定
    # 旧供应商、静态 URL 或 direct；实际来源由统一代理池当前配置决定。
    normalize_proxy_source(source)
    return "pool"


def account_action_proxy_mode(purpose: str | None = None) -> str:
    return _resolve_proxy_source(_configured_action_source(purpose))


def _region_from_extra(account: dict) -> str:
    from config.countries import ISO_3166_ALPHA2

    raw = account.get("extra_json")
    if not raw:
        return ""
    try:
        extra = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    for provider in ("browser_use", "skyvern"):
        value = str(((extra.get(provider) or {}).get("proxy_country_code") or "")).strip().upper()
        if value in ISO_3166_ALPHA2:
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
        from config.countries import ISO_3166_ALPHA2

        saved = str(account.get("registration_proxy_region") or "").strip().upper()
        if saved in ISO_3166_ALPHA2:
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
            if region in ISO_3166_ALPHA2:
                return region

    from core.proxy_pool import default_country

    return default_country()


def proxy_configuration_status(purpose: str | None = None) -> dict[str, Any]:
    """返回账号功能代理是否已配置，不执行网络请求。"""
    try:
        mode = account_action_proxy_mode(purpose)
    except Exception as exc:
        return {"ok": False, "mode": "invalid", "reason": str(exc)}
    from config import proxy as cfg
    try:
        from core.proxy_pool import pool_source

        source = pool_source()
    except Exception as exc:
        return {"ok": False, "mode": mode, "reason": str(exc)}
    from core.proxy_sources import get_source, is_supply_source
    if is_supply_source(source):
        supplier = get_source(source)
        if not str(supplier.options()["api_url"] or "").strip():
            return {"ok": False, "mode": mode, "reason": f"统一代理池未配置 {supplier.label} 提取 API"}
    if source == "manual" and not list(getattr(cfg, "PROXY_POOL", []) or []):
        return {"ok": False, "mode": mode, "reason": "统一代理池未配置手动代理地址"}
    return {"ok": True, "mode": mode, "pool_source": source, "reason": None}


def acquire_account_proxy(
    *,
    account_id: int | None = None,
    email: str | None = None,
    purpose: str,
    explicit_proxy: str | None = None,
    region: str | None = None,
    source: str | None = None,
    rotation_index: int = 0,
    allow_reuse: bool | None = None,
    reuse_limit: int | None = None,
    cancel: Callable[[], None] | None = None,
    progress_callback: Callable[[str], None] | None = None,
    timeout: float | None = None,
) -> AccountProxyRoute:
    """为一次账号功能调用获取线路；调用方必须在 finally 中 release。"""
    selected = str(explicit_proxy or "").strip()
    if selected and not str(region or "").strip():
        # 显式地址只复用同一链的线路，不能把调用方要求的国家写成实测国家。
        # 有目标国家的业务必须重新从池领取并验证。
        return AccountProxyRoute(
            proxy_url=selected,
            provider="request" if selected else "direct",
            mode="request",
            region=None,
            purpose=purpose,
        )
    # 调用方会把可选快照字段原样传入；空字符串表示没有同链线路，必须
    # 重新从当前统一池领取，不能借空值绕过池回到直连。

    mode = account_action_proxy_mode(purpose) if source is None else _resolve_proxy_source(source)
    if mode == "pool":
        from config import proxy as cfg
        from core.proxy_pool import acquire_proxy
        from core.task_run_log import current_context
        context = current_context()
        selected_region = str(region or "").strip().upper() or resolve_account_region(
            account_id=account_id, email=email,
        )
        pool_kwargs = {
            "purpose": purpose, "country": selected_region or None,
            "account_id": account_id, "operation_task_id": context.get("task_id"),
            "operation_run_id": context.get("run_id"),
            "allow_reuse": purpose == "plan-check" and (
                bool(getattr(cfg, "PLAN_CHECK_PROXY_ALLOW_REUSE", True)) if allow_reuse is None else bool(allow_reuse)
            ),
        }
        if purpose == "plan-check" and reuse_limit is not None:
            pool_kwargs["reuse_limit"] = reuse_limit
        pool_kwargs.update({key: value for key, value in {
            "cancel": cancel, "progress_callback": progress_callback, "timeout": timeout,
        }.items() if value is not None})
        if rotation_index:
            pool_kwargs["correlation_id"] = f"{purpose}-{account_id or email or 'account'}-rotation-{max(0, int(rotation_index))}"
        lease = acquire_proxy(**{key: value for key, value in pool_kwargs.items() if value is not None})
        return AccountProxyRoute(lease.proxy_url, lease.provider, mode, region=lease.region, lease=lease, purpose=purpose)

    raise RuntimeError(f"不支持的统一代理池来源: {mode}")


def _status_1024proxy() -> dict[str, Any]:
    from config import proxy as cfg

    if not str(getattr(cfg, "PROXY_1024_API_URL", "") or "").strip():
        return {"ok": False, "reason": "未配置 1024Proxy 提取 API"}
    # 独立池始终验证候选；旧诊断开关不影响任务的库存准入。
    from core.proxy_pool import _provider_options, _validate_lifetime, settings
    try:
        _validate_lifetime("1024proxy", _provider_options(), settings())
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}
    return {"ok": True, "reason": None}


def _acquire_1024proxy(
    *,
    account_id: int | None,
    email: str | None,
    purpose: str,
    region: str | None,
    mode: str,
    rotation_index: int = 0,
    allow_reuse: bool | None = None,
    reuse_limit: int | None = None,
    cancel: Callable[[], None] | None = None,
    progress_callback: Callable[[str], None] | None = None,
    timeout: float | None = None,
) -> AccountProxyRoute:
    from config import proxy as cfg
    from core.task_run_log import current_context

    selected_region = str(region or "").strip().upper() or resolve_account_region(
        account_id=account_id,
        email=email,
    )
    if not selected_region:
        raise RuntimeError("无法确定账号注册国家，拒绝使用随机地区代理查询")
    seed = f"{purpose}-{account_id or email or datetime.now().timestamp()}"
    normalized_rotation = max(0, int(rotation_index or 0))
    if normalized_rotation:
        seed = f"{seed}-rotation-{normalized_rotation}"
    reuse = purpose == "plan-check" and bool(
        getattr(cfg, "PLAN_CHECK_PROXY_ALLOW_REUSE", True) if allow_reuse is None else allow_reuse
    )
    correlation = current_context()
    lease = acquire_1024_proxy(
        region=selected_region,
        validate=True,
        job_id=seed,
        account_id=account_id,
        purpose=purpose,
        operation_task_id=correlation.get("task_id"),
        operation_run_id=correlation.get("run_id"),
        **({"allow_reuse": True, "reuse_limit": int(
            getattr(cfg, "PLAN_CHECK_PROXY_REUSE_LIMIT", 3) if reuse_limit is None else reuse_limit,
        )} if reuse else {}),
        **{key: value for key, value in {
            "cancel": cancel, "progress_callback": progress_callback, "timeout": timeout,
        }.items() if value is not None},
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
