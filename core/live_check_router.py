# -*- coding: utf-8 -*-
"""普通查活驱动路由。

当前默认保持稳定的协议型 AT probe；Roxy 浏览器 probe 已作为独立 adapter
接入，但仍由灰度开关保护，必须完成真实浏览器契约验证后才能开放。这里不
做自动 fallback，也不承载任何登录逻辑。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


DEFAULT_DRIVER = "protocol_current"
CURRENT_PROTOCOL_DRIVER = "protocol_current"
BROWSER_ROXY_DRIVER = "browser_roxy"
SUPPORTED_DRIVERS = frozenset({CURRENT_PROTOCOL_DRIVER, BROWSER_ROXY_DRIVER})


class LiveCheckDriverError(ValueError):
    """普通查活驱动配置非法或尚未开放。"""


def _configured_driver() -> str:
    from config import account as account_config

    return str(
        getattr(account_config, "ACCOUNT_LIVE_CHECK_DRIVER", DEFAULT_DRIVER)
        or DEFAULT_DRIVER
    ).strip().lower()


def _browser_driver_enabled() -> bool:
    from config import account as account_config

    return bool(getattr(account_config, "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", False))


def resolve_driver(requested: str | None = None) -> str:
    """解析本次普通查活的实际驱动，不产生网络或数据库副作用。

    ``protocol``/``current`` 是阶段 1 为已有配置和人工调用保留的兼容别名；
    它们只能解析到当前稳定协议实现，不会悄悄切到新实现。
    """
    value = _configured_driver() if requested is None else str(requested or "").strip().lower()
    value = {
        "": DEFAULT_DRIVER,
        "current": CURRENT_PROTOCOL_DRIVER,
        "protocol": CURRENT_PROTOCOL_DRIVER,
    }.get(value, value)
    if value not in SUPPORTED_DRIVERS:
        supported = ", ".join(sorted(SUPPORTED_DRIVERS))
        raise LiveCheckDriverError(
            f"普通查活驱动 {value!r} 尚未开放；当前仅支持 {supported}"
        )
    if value == BROWSER_ROXY_DRIVER and not _browser_driver_enabled():
        raise LiveCheckDriverError(
            "Roxy 浏览器普通查活 probe 当前未开放，请先完成阶段 2 的真实验证"
        )
    return value


def run_probe(
    *,
    driver: str,
    probe: Callable[..., dict[str, Any]],
    token: str,
    proxy: str | None,
    max_attempts: int,
    browser_probe: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """调用已经选定的普通查活 adapter。

    ``probe`` 由调用方传入，便于 current 路径保持原函数和测试替身不变。
    router 只负责选择边界，不负责登录、刷新 Token 或跨驱动兜底。
    """
    effective_driver = resolve_driver(driver)
    if effective_driver == CURRENT_PROTOCOL_DRIVER:
        result = probe(token, proxy=proxy, max_attempts=max_attempts)
    elif effective_driver == BROWSER_ROXY_DRIVER:
        if browser_probe is None:
            raise LiveCheckDriverError("Roxy 浏览器普通查活 probe 尚未接入")
        result = browser_probe(token=token, proxy=proxy)
    else:
        raise LiveCheckDriverError(f"普通查活驱动未实现: {effective_driver}")
    if not isinstance(result, dict):
        raise TypeError("普通查活 probe 必须返回 dict")
    enriched = dict(result)
    enriched.setdefault("live_check_driver", effective_driver)
    return enriched


__all__ = [
    "CURRENT_PROTOCOL_DRIVER",
    "BROWSER_ROXY_DRIVER",
    "DEFAULT_DRIVER",
    "LiveCheckDriverError",
    "SUPPORTED_DRIVERS",
    "resolve_driver",
    "run_probe",
]
