# -*- coding: utf-8 -*-
"""WebUI 功能可用性检查；仅检查必要配置/本地素材，不发起外部请求。"""
from __future__ import annotations

from typing import Any

from core import db
from core.account_proxy import proxy_configuration_status


def _feature(ok: bool, reason: str = "") -> dict[str, Any]:
    return {"enabled": bool(ok), "reason": "" if ok else str(reason or "缺少必要配置")}


def _all_present(values: list[tuple[str, Any]]) -> tuple[bool, str]:
    missing = [label for label, value in values if not str(value or "").strip()]
    return (not missing, "、".join(missing) + " 未配置" if missing else "")


def _email_source_features() -> dict[str, dict[str, Any]]:
    from config import email as cfg
    from core.email_provider import EMAIL_SOURCE_LABELS, parse_email_sources

    configured = set(parse_email_sources(getattr(cfg, "EMAIL_SOURCE", "outlook")))
    results: dict[str, dict[str, Any]] = {}

    def add(source: str, ok: bool, reason: str = "") -> None:
        enabled = source in configured and ok
        if source not in configured:
            reason = "未在 EMAIL_SOURCE 中启用"
        results[source] = {
            "label": EMAIL_SOURCE_LABELS.get(source, source),
            **_feature(enabled, reason),
        }

    add("outlook", db.outlook_pool_summary().get("available", 0) > 0, "邮箱池没有可用 Outlook 素材")
    add("generic_api", db.generic_api_email_pool_summary().get("available", 0) > 0, "通用 API 邮箱池为空")
    ok, reason = _all_present([
        ("EMAIL_DOMAIN", getattr(cfg, "EMAIL_DOMAIN", "")),
        ("QQ_EMAIL", getattr(cfg, "QQ_EMAIL", "")),
        ("QQ_IMAP_PASSWORD", getattr(cfg, "QQ_IMAP_PASSWORD", "")),
    ])
    add("cloudflare_domain", ok, reason)
    ok, reason = _all_present([("CLOUDFLARE_API_BASE", getattr(cfg, "CLOUDFLARE_API_BASE", ""))])
    if ok:
        auth_mode = str(getattr(cfg, "CLOUDFLARE_AUTH_MODE", "none") or "none").lower()
        path = str(getattr(cfg, "CLOUDFLARE_PATH_ACCOUNTS", "") or "").lower()
        needs_key = auth_mode in {"x-admin-auth", "bearer", "x-api-key", "query-key"} or path.rstrip("/").endswith("/admin/new_address")
        if needs_key and not str(getattr(cfg, "CLOUDFLARE_API_KEY", "") or "").strip():
            ok, reason = False, "Cloudflare API Key 未配置"
    add("cloudflare", ok, reason)
    ok, reason = _all_present([
        ("EMAIL_BUTLER_API_BASE", getattr(cfg, "EMAIL_BUTLER_API_BASE", "")),
        ("EMAIL_BUTLER_API_KEY", getattr(cfg, "EMAIL_BUTLER_API_KEY", "")),
    ])
    add("email_butler", ok, reason)
    ok, reason = _all_present([("GPTMAIL_API_KEY", getattr(cfg, "GPTMAIL_API_KEY", ""))])
    add("gptmail", ok, reason)
    ok, reason = _all_present([
        ("MAIL_NEST_API_KEY", getattr(cfg, "MAIL_NEST_API_KEY", "")),
        ("MAIL_NEST_PROJECT_CODE", getattr(cfg, "MAIL_NEST_PROJECT_CODE", "")),
    ])
    add("mailnest", ok, reason)
    ok, reason = _all_present([
        ("CLOUDMAIL_API_BASE", getattr(cfg, "CLOUDMAIL_API_BASE", "")),
        ("CLOUDMAIL_AUTH_TOKEN", getattr(cfg, "CLOUDMAIL_AUTH_TOKEN", "")),
    ])
    add("cloudmail", ok, reason)
    ok, reason = _all_present([
        ("ICLOUD_HME_API_BASE", getattr(cfg, "ICLOUD_HME_API_BASE", "")),
        ("ICLOUD_HME_ACCOUNT_ID", getattr(cfg, "ICLOUD_HME_ACCOUNT_ID", "")),
    ])
    add("icloud_hide", ok, reason)
    return results


def _registration_driver_status() -> dict[str, Any]:
    from config import roxybrowser as roxy
    driver = str(getattr(roxy, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
    if driver in {"protocol", "api", "http"}:
        return _feature(True) | {"driver": driver}
    if driver in {"roxy", "roxybrowser", "fingerprint", "browser"}:
        ok, reason = _all_present([
            ("ROXY_API_BASE", getattr(roxy, "ROXY_API_BASE", "")),
            ("ROXY_API_TOKEN", getattr(roxy, "ROXY_API_TOKEN", "")),
            ("ROXY_WORKSPACE_ID", getattr(roxy, "ROXY_WORKSPACE_ID", "")),
        ])
        return _feature(ok, reason) | {"driver": driver}
    return _feature(False, f"不支持的注册驱动 {driver}") | {"driver": driver}


def _registration_proxy_status() -> dict[str, Any]:
    from config import proxy as cfg
    mode = str(getattr(cfg, "REGISTRATION_PROXY_MODE", "pool") or "pool").strip().lower()
    if mode in {"1024", "1024proxy", "provider"}:
        ok, reason = _all_present([("1024Proxy 提取 API", getattr(cfg, "PROXY_1024_API_URL", ""))])
        if ok and not bool(getattr(cfg, "PROXY_1024_VALIDATE", True)):
            ok, reason = False, "代理平台必须开启使用前出口检测"
        return _feature(ok, reason) | {"mode": "1024"}
    if mode == "pool":
        ok = bool(list(getattr(cfg, "PROXY_POOL", []) or []))
        return _feature(ok, "代理池为空") | {"mode": mode}
    if mode in {"none", "direct"}:
        return _feature(True) | {"mode": "direct"}
    return _feature(False, f"不支持的注册代理来源 {mode}") | {"mode": mode}


def _codex_retry_status() -> dict[str, Any]:
    from config import codex as codex
    from config import roxybrowser as roxy
    driver = str(getattr(codex, "CODEX_OAUTH_DRIVER", "protocol") or "protocol").strip().lower()
    if driver == "same_as_registration":
        driver = str(getattr(roxy, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
    if driver in {"roxy", "roxybrowser", "fingerprint", "browser"}:
        ok, reason = _all_present([
            ("ROXY_API_BASE", getattr(roxy, "ROXY_API_BASE", "")),
            ("ROXY_API_TOKEN", getattr(roxy, "ROXY_API_TOKEN", "")),
            ("ROXY_WORKSPACE_ID", getattr(roxy, "ROXY_WORKSPACE_ID", "")),
        ])
        if ok:
            proxy_status = proxy_configuration_status()
            ok, reason = bool(proxy_status.get("ok")), str(proxy_status.get("reason") or "")
    else:
        proxy_status = proxy_configuration_status()
        ok, reason = bool(proxy_status.get("ok")), str(proxy_status.get("reason") or "")
    if not ok:
        return _feature(False, reason)

    auth_source = str(getattr(codex, "CODEX_AUTH_URL_SOURCE", "cpa") or "cpa").strip().lower()
    if auth_source == "cpa":
        ok, reason = _all_present([
            ("CPA_MANAGEMENT_URL", getattr(codex, "CPA_MANAGEMENT_URL", "")),
            ("CPA_MANAGEMENT_KEY", getattr(codex, "CPA_MANAGEMENT_KEY", "")),
        ])
    elif auth_source == "sub2":
        from config import sub2api
        ok, reason = _all_present([
            ("SUB2API_API_BASE", getattr(sub2api, "SUB2_CODEX_API_BASE", "") or getattr(sub2api, "SUB2API_API_BASE", "")),
            ("SUB2API_API_KEY", getattr(sub2api, "SUB2_CODEX_API_TOKEN", "") or getattr(sub2api, "SUB2API_API_KEY", "")),
        ])
    elif auth_source == "local":
        ok, reason = True, ""
    else:
        ok, reason = False, f"不支持的 CODEX_AUTH_URL_SOURCE={auth_source}"
    if not ok:
        return _feature(False, reason)

    provider = str(getattr(codex, "SMS_PROVIDER", "grizzly") or "grizzly").strip().lower()
    if provider == "grizzly":
        ok, reason = _all_present([("SMS_API_KEY", getattr(codex, "SMS_API_KEY", ""))])
    elif provider == "h":
        ok, reason = _all_present([
            ("H_API_BASE", getattr(codex, "H_API_BASE", "")),
            ("H_ADMIN_AUTH_CODE", getattr(codex, "H_ADMIN_AUTH_CODE", "")),
        ])
    elif provider == "l":
        ok, reason = _all_present([
            ("L_API_BASE", getattr(codex, "L_API_BASE", "")),
            ("L_ADMIN_AUTH_CODE", getattr(codex, "L_ADMIN_AUTH_CODE", "")),
        ])
    else:
        ok, reason = False, f"不支持的 SMS_PROVIDER={provider}"
    return _feature(ok, reason)


def feature_availability() -> dict[str, Any]:
    from config import codex, email, extract_link, sub2api, roxybrowser

    account_proxy = proxy_configuration_status()
    account_proxy_feature = _feature(bool(account_proxy.get("ok")), str(account_proxy.get("reason") or ""))
    email_sources = _email_source_features()
    driver = _registration_driver_status()
    registration_proxy = _registration_proxy_status()
    manual_mode = not bool(getattr(email, "USE_EMAIL_SERVICE", True))
    if manual_mode:
        manual_ok, manual_reason = _all_present([("REGISTER_EMAIL", __import__("config.register", fromlist=["REGISTER_EMAIL"]).REGISTER_EMAIL)])
        email_ready = manual_ok
        email_reason = manual_reason
    else:
        enabled_sources = [item for item in email_sources.values() if item.get("enabled")]
        email_ready = bool(enabled_sources)
        email_reason = "没有已配置且可用的邮箱来源"
    register_ok = bool(driver.get("enabled") and registration_proxy.get("enabled") and email_ready)
    register_reason = next((
        reason for ready, reason in (
            (driver.get("enabled"), driver.get("reason")),
            (registration_proxy.get("enabled"), registration_proxy.get("reason")),
            (email_ready, email_reason),
        ) if not ready
    ), "")

    extract_ok, extract_reason = _all_present([
        ("EXTRACT_LINK_API_BASE", getattr(extract_link, "EXTRACT_LINK_API_BASE", "")),
        ("EXTRACT_LINK_CDK", getattr(extract_link, "EXTRACT_LINK_CDK", "")),
    ])
    sub2_ok, sub2_reason = _all_present([
        ("SUB2API_API_BASE", getattr(sub2api, "SUB2API_API_BASE", "") or getattr(sub2api, "SUB2API_API_URL", "")),
    ])
    cpa_ok, cpa_reason = _all_present([
        ("CPA_MANAGEMENT_URL", getattr(codex, "CPA_MANAGEMENT_URL", "")),
        ("CPA_MANAGEMENT_KEY", getattr(codex, "CPA_MANAGEMENT_KEY", "")),
    ])
    deactivation_ready = any(
        email_sources.get(name, {}).get("enabled") for name in ("email_butler", "cloudflare", "icloud_hide")
    )
    roxy_ok, roxy_reason = _all_present([
        ("ROXY_API_BASE", getattr(roxybrowser, "ROXY_API_BASE", "")),
        ("ROXY_API_TOKEN", getattr(roxybrowser, "ROXY_API_TOKEN", "")),
    ])
    cloudmail_tool_ok, cloudmail_tool_reason = _all_present([
        ("CLOUDMAIL_API_BASE", getattr(email, "CLOUDMAIL_API_BASE", "")),
        ("CLOUDMAIL_ADMIN_EMAIL", getattr(email, "CLOUDMAIL_ADMIN_EMAIL", "")),
        ("CLOUDMAIL_PASSWORD", getattr(email, "CLOUDMAIL_PASSWORD", "")),
    ])
    cloudmail_domains_ok = bool(str(getattr(email, "CLOUDMAIL_API_BASE", "") or "").strip()) and bool(
        str(getattr(email, "CLOUDMAIL_AUTH_TOKEN", "") or "").strip()
        or (
            str(getattr(email, "CLOUDMAIL_ADMIN_EMAIL", "") or "").strip()
            and str(getattr(email, "CLOUDMAIL_PASSWORD", "") or "").strip()
        )
    )
    cloudmail_domains_reason = "CLOUDMAIL_API_BASE 以及 Token（或管理员账号/密码）未配置"
    icloud_tool_ok, icloud_tool_reason = _all_present([
        ("ICLOUD_HME_API_BASE", getattr(email, "ICLOUD_HME_API_BASE", "")),
        ("ICLOUD_HME_ACCOUNT_ID", getattr(email, "ICLOUD_HME_ACCOUNT_ID", "")),
    ])
    butler_ok, butler_reason = _all_present([
        ("EMAIL_BUTLER_API_BASE", getattr(email, "EMAIL_BUTLER_API_BASE", "")),
        ("EMAIL_BUTLER_API_KEY", getattr(email, "EMAIL_BUTLER_API_KEY", "")),
    ])
    from config import proxy as proxy_cfg
    proxy_test_ok, proxy_test_reason = _all_present([
        ("1024Proxy 提取 API", getattr(proxy_cfg, "PROXY_1024_API_URL", "")),
    ])

    features = {
        "register": _feature(register_ok, register_reason),
        "plan_check": dict(account_proxy_feature),
        "live_check": dict(account_proxy_feature),
        "codex_retry": _codex_retry_status(),
        "extract_link": _feature(extract_ok, extract_reason),
        "sub2_upload": _feature(sub2_ok, sub2_reason),
        "cpa_download": _feature(cpa_ok, cpa_reason),
        "deactivation_mail": _feature(deactivation_ready, "没有配置支持封号扫描的 Email Butler / Cloudflare / iCloud 邮箱来源"),
        "proxy_provider_test": _feature(proxy_test_ok, proxy_test_reason),
        "roxy_workspaces": _feature(roxy_ok, roxy_reason),
        "cloudmail_token": _feature(cloudmail_tool_ok, cloudmail_tool_reason),
        "cloudmail_domains": _feature(cloudmail_domains_ok, cloudmail_domains_reason),
        "icloud_hme": _feature(icloud_tool_ok, icloud_tool_reason),
        "email_butler_test": _feature(butler_ok, butler_reason),
    }
    return {
        "ok": True,
        "features": features,
        "email_sources": email_sources,
        "proxy": {
            "account_actions": account_proxy,
            "registration": registration_proxy,
        },
    }


def require_feature(name: str) -> tuple[bool, str]:
    item = feature_availability().get("features", {}).get(str(name), {})
    return bool(item.get("enabled")), str(item.get("reason") or "功能未配置")
