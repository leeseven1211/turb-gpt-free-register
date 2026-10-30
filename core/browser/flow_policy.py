# -*- coding: utf-8 -*-
"""浏览器流程省流量策略及窗口规则切换。"""
from __future__ import annotations

import logging
from typing import Any

from config import browser as _cfg

from core.browser.data_saver import BrowserDataSaver, configured_resource_types, configured_url_patterns

logger = logging.getLogger('core.browser_flow_policy')

FLOW_NAMES = frozenset({"registration", "token_refresh", "live_check", "codex_oauth", "account_action"})
AUTH_FLOW_NAMES = frozenset({"token_refresh", "live_check", "codex_oauth", "account_action"})

# 认证页面不能使用注册流程的脚本、认证 CDN、session、sentinel 或 CES 注册规则。
# 这些 URL 仅指向固定的遥测/广告端点，不能携带认证状态。
AUTH_SAFE_URL_PATTERNS = (
    "**://auth.openai.com/awe/api/v2/rum**",
    "**://chatgpt.com/ces/statsc/flush**",
    "**://connect.facebook.net/**",
    "**://analytics.tiktok.com/**",
    "**://snap.licdn.com/**",
    "**://bat.bing.com/**",
    "**://*/favicon.ico**",
)


def _flow_name(flow: str | None) -> str:
    return str(flow or "").strip().lower()


def _configured_auth_flows() -> set[str]:
    raw = getattr(_cfg, "BROWSER_DATA_SAVER_AUTH_FLOWS", AUTH_FLOW_NAMES)
    if isinstance(raw, str):
        values = raw.replace(",", "\n").splitlines()
    elif isinstance(raw, (list, tuple, set)):
        values = raw
    else:
        values = [raw]
    return {_flow_name(item) for item in values if _flow_name(item) in AUTH_FLOW_NAMES}


def flow_enabled(flow: str | None) -> bool:
    """返回流程是否应启用省流量规则；未知流程保留旧的总开关行为。"""
    if not bool(getattr(_cfg, "BROWSER_DATA_SAVER_MODE", False)):
        return False
    name = _flow_name(flow)
    if name in AUTH_FLOW_NAMES:
        return name in _configured_auth_flows()
    return True


def opening_resource_types(flow: str | None) -> list[str]:
    """返回 Roxy /browser/open 启动阶段要关闭的资源类型。"""
    if not flow_enabled(flow):
        return []
    if _flow_name(flow) in AUTH_FLOW_NAMES:
        return ["image", "media"]
    return configured_resource_types()


def _clear_cdp_blocklist(driver: Any) -> None:
    try:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
        except Exception:
            pass
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": []})
    except Exception as exc:
        logger.warning("[浏览器省流量策略] 清除旧 CDP 规则失败：%s: %s", type(exc).__name__, str(exc)[:180])


def install_for_flow(
    flow: str | None,
    opened: Any,
    driver: Any,
    label: str | None = None,
) -> BrowserDataSaver | None:
    """按流程安装规则，并把新的采集器关联到已打开窗口。"""
    name = _flow_name(flow)
    enabled = flow_enabled(name)
    resource_types = opening_resource_types(name)
    url_patterns = list(AUTH_SAFE_URL_PATTERNS) if name in AUTH_FLOW_NAMES else configured_url_patterns()
    saver = BrowserDataSaver(
        label=label or name or "Browser",
        enabled=enabled,
        resource_types=resource_types,
        url_patterns=url_patterns,
    )
    if enabled:
        try:
            saver.install_selenium(driver)
        except Exception as exc:
            logger.warning("[浏览器省流量策略] 安装 %s 规则失败，继续浏览器流程：%s: %s", name or "unknown", type(exc).__name__, str(exc)[:180])
    else:
        _clear_cdp_blocklist(driver)

    capture = getattr(opened, "traffic_capture", None) if opened is not None else None
    if capture is not None:
        setter = getattr(capture, "set_data_saver", None)
        try:
            if callable(setter):
                setter(saver)
            else:
                setattr(capture, "data_saver", saver)
        except Exception as exc:
            logger.warning("[浏览器省流量策略] 关联 %s 采集器失败，继续浏览器流程：%s: %s", name or "unknown", type(exc).__name__, str(exc)[:180])
    return saver


__all__ = [
    "AUTH_FLOW_NAMES",
    "AUTH_SAFE_URL_PATTERNS",
    "FLOW_NAMES",
    "flow_enabled",
    "install_for_flow",
    "opening_resource_types",
]
