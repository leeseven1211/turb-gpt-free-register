# -*- coding: utf-8 -*-
"""WebUI 功能可用性检查；仅检查必要配置/本地素材，不发起外部请求。"""
from __future__ import annotations

from typing import Any

from config.deployment import BROWSER_UNAVAILABLE_CODE, browser_enabled, browser_unavailable_reason
from core.proxy.account_routes import proxy_configuration_status


class BrowserUnavailableError(ValueError):
    """部署缺少浏览器能力，操作尚未开始。"""

    error_code = BROWSER_UNAVAILABLE_CODE

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"{self.error_code}：{reason}")


def browser_operation_unavailable(
    driver: str = "", *, browser_fallback_enabled: bool = False, fallback_setting: str = "",
) -> dict[str, Any] | None:
    """在业务开始前校验实际驱动与兜底，禁止在执行中改变路由。"""
    if browser_enabled():
        return None
    browser_driver = str(driver or "").strip().lower() in {
        "roxy", "roxy_oss", "roxybrowser", "fingerprint", "browser", "browser_roxy",
        "browser_use", "selenium",
    }
    if not browser_driver and not browser_fallback_enabled:
        return None
    reason = browser_unavailable_reason()
    if browser_fallback_enabled and fallback_setting:
        reason += f"；请先关闭 {fallback_setting} 浏览器兜底后再执行协议任务"
    return {
        "accepted": False, "unavailable": True, "error_code": BROWSER_UNAVAILABLE_CODE,
        "error": reason,
    }


def account_setup_unavailable(
    steps: set[str], settings: dict[str, Any], *, force_twofa_change: bool = False,
) -> dict[str, Any] | None:
    """按现有账号配置执行器的实际浏览器需求检查所选步骤。"""
    if browser_enabled():
        return None
    from config import account
    from core.auth.twofa import canonical_twofa_executor

    if "password" in steps or ("twofa" in steps and force_twofa_change):
        return browser_operation_unavailable("browser")
    if "twofa" not in steps:
        return None
    # 组合配置执行器只有单独 twofa 才直接运行协议；补全协调器会单独处理套餐。
    driver = "browser" if len(steps) > 1 else canonical_twofa_executor(settings.get("twofa_driver"))
    return browser_operation_unavailable(
        driver,
        # 账号配置执行器目前从运行配置读取兜底，历史 snapshot 不覆盖此值。
        browser_fallback_enabled=bool(getattr(account, "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED", True)),
        fallback_setting="ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED",
    )


def _feature(ok: bool, reason: str = "") -> dict[str, Any]:
    return {"enabled": bool(ok), "reason": "" if ok else str(reason or "缺少必要配置")}


def _all_present(values: list[tuple[str, Any]]) -> tuple[bool, str]:
    missing = [label for label, value in values if not str(value or "").strip()]
    return (not missing, "、".join(missing) + " 未配置" if missing else "")


def _email_source_features() -> dict[str, dict[str, Any]]:
    from core.email.provider import EMAIL_SOURCE_LABELS
    from core.email import inventory as local_email_inventory

    pools = {row['source']: row for row in local_email_inventory.summary()['sources']}
    results = {}
    for source, label in EMAIL_SOURCE_LABELS.items():
        available = int(pools.get(source, {}).get('available', 0) or 0)
        local = source in local_email_inventory.TABLES
        reason = '本地邮箱库存为空，请先手动导入' if local else '新注册只使用本地邮箱库存；历史账号收码保留'
        results[source] = {'label': label, **_feature(local and available > 0, reason),
                           'available': available if local else 0}
    return results


def email_source_availability() -> dict[str, dict[str, Any]]:
    """Return the current local readiness of every supported mailbox source."""
    return _email_source_features()


def require_email_source(source: str) -> tuple[bool, str]:
    """Validate that a source is configured and currently able to allocate."""
    key = str(source or "").strip().lower()
    item = email_source_availability().get(key)
    if not item:
        return False, f"不支持的邮箱来源: {key or '-'}"
    return bool(item.get("enabled")), str(item.get("reason") or "邮箱来源当前不可用")


def _historical_mail_readable() -> bool:
    """已有账号读信能力与新邮箱库存容量独立；不发起网络请求。"""
    from config import email
    from core.email.derivation import _profile_credentials
    from core.storage.email.address_allocations import EmailDerivationError
    from core.storage.email.address_allocations import list_inbox_profiles

    if (getattr(email, 'EMAIL_BUTLER_API_BASE', '') and getattr(email, 'EMAIL_BUTLER_API_KEY', '')):
        return True
    if (getattr(email, 'CLOUDFLARE_API_BASE', '') and
            (getattr(email, 'CLOUDFLARE_SIGNAL_API_KEY', '') or getattr(email, 'CLOUDFLARE_API_KEY', ''))):
        return True
    for profile in list_inbox_profiles(state='active'):
        if profile.get('connector') not in {'forward_butler', 'forward_imap'}:
            continue
        try:
            locator = _profile_credentials(profile)
        except (EmailDerivationError, ValueError, KeyError):
            continue
        if profile['connector'] == 'forward_butler':
            if locator.get('api_base') and '@' in str(locator.get('mailbox_email') or ''):
                return True
        elif locator.get('server') and '@' in str(locator.get('email') or ''):
            return True
    return False


def _registration_driver_status() -> dict[str, Any]:
    from config import roxybrowser as roxy
    driver = str(getattr(roxy, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
    if driver in {"protocol", "protocol_oss", "protocol_oss_2", "api", "http"}:
        return _feature(True) | {"driver": driver}
    if driver in {"roxy", "roxy_oss", "roxybrowser", "fingerprint", "browser"}:
        unavailable = browser_operation_unavailable(driver)
        if unavailable:
            return _feature(False, unavailable["error"]) | {"driver": driver}
        ok, reason = _all_present([
            ("ROXY_API_BASE", getattr(roxy, "ROXY_API_BASE", "")),
            ("ROXY_API_TOKEN", getattr(roxy, "ROXY_API_TOKEN", "")),
            ("ROXY_WORKSPACE_ID", getattr(roxy, "ROXY_WORKSPACE_ID", "")),
        ])
        return _feature(ok, reason) | {"driver": driver}
    return _feature(False, f"不支持的注册驱动 {driver}") | {"driver": driver}


def _registration_proxy_status() -> dict[str, Any]:
    from core.proxy.account_routes import proxy_configuration_status

    status = proxy_configuration_status("registration")
    return _feature(bool(status.get("ok")), str(status.get("reason") or "")) | {
        "mode": "pool",
        "pool_source": status.get("pool_source"),
    }


def _codex_retry_status(driver_override: str | None = None) -> dict[str, Any]:
    from config import codex as codex
    from config import roxybrowser as roxy
    driver = str(driver_override if driver_override is not None else getattr(codex, "CODEX_OAUTH_DRIVER", "protocol") or "protocol").strip().lower()
    if driver == "same_as_registration":
        driver = str(getattr(roxy, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
        driver = {"protocol_oss": "protocol", "protocol_oss_2": "protocol", "roxy_oss": "roxy"}.get(driver, driver)
    unavailable = browser_operation_unavailable(driver)
    if unavailable:
        return _feature(False, unavailable["error"])
    if driver in {"roxy", "roxybrowser", "fingerprint", "browser"}:
        ok, reason = _all_present([
            ("ROXY_API_BASE", getattr(roxy, "ROXY_API_BASE", "")),
            ("ROXY_API_TOKEN", getattr(roxy, "ROXY_API_TOKEN", "")),
            ("ROXY_WORKSPACE_ID", getattr(roxy, "ROXY_WORKSPACE_ID", "")),
        ])
        if ok:
            proxy_status = proxy_configuration_status("codex-oauth")
            ok, reason = bool(proxy_status.get("ok")), str(proxy_status.get("reason") or "")
    else:
        proxy_status = proxy_configuration_status("codex-oauth")
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
    from core.accounts.liveness import service as live_service
    from core.accounts.liveness.router import resolve_driver, LiveCheckDriverError

    plan_proxy = proxy_configuration_status("plan-check")
    live_proxy = proxy_configuration_status("live-check")
    account_proxy_feature = _feature(bool(plan_proxy.get("ok")), str(plan_proxy.get("reason") or ""))
    live_proxy_feature = _feature(bool(live_proxy.get("ok")), str(live_proxy.get("reason") or ""))
    try:
        live_unavailable = browser_operation_unavailable(resolve_driver())
    except LiveCheckDriverError as exc:
        live_unavailable = {"error": str(exc)}
    if live_unavailable:
        live_proxy_feature = _feature(False, live_unavailable["error"])
    refresh_unavailable = browser_operation_unavailable(
        live_service._resolve_refresh_driver(),
        browser_fallback_enabled=live_service._roxy_fallback_enabled(),
        fallback_setting="LIVE_CHECK_ROXY_FALLBACK_ENABLED",
    )
    refresh_proxy = proxy_configuration_status("token-refresh")
    refresh_feature = _feature(
        not refresh_unavailable and bool(refresh_proxy.get("ok")),
        refresh_unavailable["error"] if refresh_unavailable else str(refresh_proxy.get("reason") or ""),
    )
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
    deactivation_ready = _historical_mail_readable()
    roxy_ok, roxy_reason = _all_present([
        ("ROXY_API_BASE", getattr(roxybrowser, "ROXY_API_BASE", "")),
        ("ROXY_API_TOKEN", getattr(roxybrowser, "ROXY_API_TOKEN", "")),
    ])
    if not browser_enabled():
        roxy_ok, roxy_reason = False, browser_unavailable_reason()
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
        "live_check": dict(live_proxy_feature),
        "token_refresh": refresh_feature,
        "password_setup": _feature(browser_enabled(), browser_unavailable_reason()),
        "twofa_change": _feature(browser_enabled(), browser_unavailable_reason()),
        "account_setup": _feature(browser_enabled(), browser_unavailable_reason()),
        "codex_retry": _codex_retry_status(),
        "extract_link": _feature(extract_ok, extract_reason),
        "sub2_upload": _feature(sub2_ok, sub2_reason),
        "cpa_download": _feature(cpa_ok, cpa_reason),
        "deactivation_mail": _feature(deactivation_ready, "没有配置支持封号扫描的 Email Butler / Cloudflare / iCloud 邮箱来源"),
        "proxy_provider_test": _feature(proxy_test_ok, proxy_test_reason),
        "roxy_workspaces": _feature(roxy_ok, roxy_reason),
        "cloudmail_token": _feature(False, "邮箱管理已迁至邮箱服务，请在邮箱服务生成 Token"),
        "cloudmail_domains": _feature(False, "邮箱管理已迁至邮箱服务，请在邮箱服务管理域名"),
        "icloud_hme": _feature(False, "iCloud 管理已迁至邮箱服务，Turb 仅导入及使用"),
        "email_butler_test": _feature(butler_ok, butler_reason),
    }
    return {
        "ok": True,
        "features": features,
        "deployment": {"browser": _feature(browser_enabled(), browser_unavailable_reason())},
        "email_sources": email_sources,
        "proxy": {
            "account_actions": {
                "plan_check": plan_proxy,
                "live_check": live_proxy,
            },
            "registration": registration_proxy,
        },
    }


def require_feature(name: str, *, driver: str | None = None) -> tuple[bool, str]:
    if name == "live_check" and driver is not None:
        unavailable = browser_operation_unavailable(driver)
        if unavailable:
            return False, unavailable["error"]
        proxy = proxy_configuration_status("live-check")
        return bool(proxy.get("ok")), str(proxy.get("reason") or "")
    item = _codex_retry_status(driver) if name == "codex_retry" and driver is not None else feature_availability().get("features", {}).get(str(name), {})
    return bool(item.get("enabled")), str(item.get("reason") or "功能未配置")
