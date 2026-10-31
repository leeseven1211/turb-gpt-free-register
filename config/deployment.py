"""部署能力只由启动环境声明，不属于可热编辑的运行配置。"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

BROWSER_UNAVAILABLE_CODE = "browser_unavailable_on_deployment"
BROWSER_DRIVER_VALUES = frozenset({"roxy", "roxy_oss", "browser", "browser_roxy"})
BROWSER_DRIVER_KEYS = frozenset({
    "REGISTRATION_DRIVER", "ACCOUNT_PASSWORD_DRIVER", "CODEX_OAUTH_DRIVER",
    "ACCOUNT_CODEX_DRIVER", "ACCOUNT_AT_REFRESH_DRIVER", "ACCOUNT_LIVE_CHECK_DRIVER",
    "TWOFA_DRIVER", "ACCOUNT_2FA_DRIVER",
})
BROWSER_ENABLE_KEYS = frozenset({
    "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", "LIVE_CHECK_ROXY_FALLBACK_ENABLED",
    "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED",
})
BROWSER_DEPENDENT_FEATURES = {
    "ACCOUNT_COMPLETION_PASSWORD_ENABLED": ("ACCOUNT_PASSWORD_DRIVER", ""),
    "ACCOUNT_PASSWORD_RESET_ENABLED": ("ACCOUNT_PASSWORD_DRIVER", ""),
    "ENABLE_CODEX_AUTO": ("CODEX_OAUTH_DRIVER", ""),
    "ENABLE_2FA": ("TWOFA_DRIVER", ""),
    "ACCOUNT_COMPLETION_CODEX_ENABLED": ("ACCOUNT_CODEX_DRIVER", ""),
    "ACCOUNT_COMPLETION_2FA_ENABLED": ("ACCOUNT_2FA_DRIVER", "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED"),
    "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED": ("ACCOUNT_AT_REFRESH_DRIVER", "LIVE_CHECK_ROXY_FALLBACK_ENABLED"),
    "AT_AUTO_REFRESH_ENABLED": ("ACCOUNT_AT_REFRESH_DRIVER", "LIVE_CHECK_ROXY_FALLBACK_ENABLED"),
}


def browser_enabled() -> bool:
    """缺省保留本机浏览器能力；拼写错误必须明确失败。"""
    raw = os.getenv("TURB_BROWSER_ENABLED")
    if raw is None:
        return True
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError("TURB_BROWSER_ENABLED 必须为 true/false、1/0、yes/no 或 on/off")


def browser_unavailable_reason() -> str:
    return "" if browser_enabled() else "当前部署未提供浏览器，仅支持纯协议功能"


def browser_config_update_errors(updates: Mapping[str, Any], current_values: Mapping[str, Any]) -> dict[str, str]:
    """拒绝本次提交启用浏览器，历史未启用参数不妨碍无关配置保存。"""
    reason = browser_unavailable_reason()
    if not reason:
        return {}
    candidate = {**current_values, **updates}
    errors = {}
    for key, value in updates.items():
        enabled = key in BROWSER_ENABLE_KEYS and value is True
        driver_key = key if key in BROWSER_DRIVER_KEYS else ""
        if key in BROWSER_DEPENDENT_FEATURES and value is True:
            driver_key, fallback_key = BROWSER_DEPENDENT_FEATURES[key]
            enabled = candidate.get(fallback_key) is True
        if driver_key:
            driver = str(candidate.get(driver_key) or "").strip().lower()
            if driver == "same_as_registration":
                driver = str(candidate.get("REGISTRATION_DRIVER") or "").strip().lower()
            enabled = enabled or driver in BROWSER_DRIVER_VALUES
        if enabled:
            errors[key] = f"{BROWSER_UNAVAILABLE_CODE}：{reason}"
    return errors
