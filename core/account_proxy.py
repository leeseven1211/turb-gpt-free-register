# -*- coding: utf-8 -*-
"""账号相关 OpenAI 功能的统一代理租约。

注册任务、套餐查询、查活和 Codex OAuth 都通过本模块选择线路。
邮箱/短信/CPA/Sub2/提链等第三方或本地服务不应使用这里的付费代理。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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


def account_action_proxy_mode() -> str:
    from config import proxy as cfg

    mode = str(getattr(cfg, "ACCOUNT_ACTION_PROXY_MODE", "registration") or "registration").strip().lower()
    aliases = {
        "auto": "registration",
        "same_as_registration": "registration",
        "provider": "1024",
        "platform": "1024",
        "1024proxy": "1024",
        "none": "direct",
        "off": "direct",
    }
    mode = aliases.get(mode, mode)
    if mode == "registration":
        mode = registration_proxy_mode()
        if mode == "none":
            mode = "direct"
    if mode not in {"1024", "pool", "direct"}:
        raise ValueError(
            f"ACCOUNT_ACTION_PROXY_MODE={mode!r} 无效，可选 registration / 1024 / pool / direct"
        )
    return mode


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


def proxy_configuration_status() -> dict[str, Any]:
    """返回账号功能代理是否已配置，不执行网络请求。"""
    try:
        mode = account_action_proxy_mode()
    except Exception as exc:
        return {"ok": False, "mode": "invalid", "reason": str(exc)}
    from config import proxy as cfg
    if mode == "1024":
        if not str(getattr(cfg, "PROXY_1024_API_URL", "") or "").strip():
            return {"ok": False, "mode": mode, "reason": "未配置 1024Proxy 提取 API"}
        if not bool(getattr(cfg, "PROXY_1024_VALIDATE", True)):
            return {"ok": False, "mode": mode, "reason": "代理平台必须开启使用前出口检测"}
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

    mode = account_action_proxy_mode()
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
