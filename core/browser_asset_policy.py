"""Roxy 公共静态缓存的流程、线路与生命周期边界。"""
from __future__ import annotations

import logging
from pathlib import Path

from config import browser as _cfg

logger = logging.getLogger(__name__)


def start_registration_asset_cache(opened, driver=None, *, proxy_url: str | None = None):
    """注册匿名填充只能沿本次新建环境的已知线路。"""
    mode = str(getattr(_cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "off") or "off")
    if mode not in {"observe", "enabled"}:
        return None
    target_id = _current_page_target(driver, flow="注册") if driver is not None else None
    if driver is not None and target_id is None:
        return None
    fill_proxy = proxy_url if getattr(opened, "created_by_run", False) else None
    return _start_asset_cache(opened, flow="registration", proxy_url=fill_proxy, target_id=target_id)


def _current_page_target(driver, *, flow: str):
    """只绑定调用方正在操作的页面，不能猜测多窗口中的第一个页面。"""
    try:
        info = driver.execute_cdp_cmd("Target.getTargetInfo", {}).get("targetInfo", {})
        target_id = info.get("targetId")
        if isinstance(target_id, str) and target_id and info.get("type") == "page":
            return target_id
    except Exception as exc:
        logger.warning("[公共资源缓存] 无法确认当前%s页面，继续正常加载：%s", flow, type(exc).__name__)
    return None


def start_auth_asset_cache(opened, driver, *, flow: str):
    """认证只复用公共响应，不额外下载；不接管父注册流程的缓存。"""
    from core.browser_flow_policy import AUTH_FLOW_NAMES

    mode = str(getattr(_cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "off") or "off")
    if mode not in {"observe", "enabled"} or flow not in AUTH_FLOW_NAMES:
        return None
    capture = getattr(opened, "traffic_capture", None)
    if getattr(capture, "public_asset_cache", None) is not None:
        return None
    target_id = _current_page_target(driver, flow="认证")
    if target_id is None:
        return None
    return _start_asset_cache(opened, flow=flow, target_id=target_id)


def _start_asset_cache(opened, *, flow: str, proxy_url: str | None = None, target_id: str | None = None):
    mode = str(getattr(_cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "off") or "off")
    if mode not in {"observe", "enabled"}:
        return None
    cache = None
    try:
        from core.public_asset_cache import PublicAssetCache

        cache = PublicAssetCache(
            getattr(opened, "debugger_address", ""),
            Path(__file__).resolve().parent.parent / "run" / "public-asset-cache",
            mode=mode,
            max_total_bytes=int(_cfg.BROWSER_PUBLIC_ASSET_CACHE_MAX_MB) * 1024 * 1024,
            proxy_url=proxy_url,
            allow_direct=False,
            target_id=target_id,
        )
        if not cache.start():
            cache.stop()
            return None
        capture = getattr(opened, "traffic_capture", None)
        if capture is not None:
            capture.set_public_asset_cache(cache)
        logger.info("[公共资源缓存] 缓存已启动：流程=%s，模式=%s", flow, mode)
        return cache
    except Exception as exc:
        if cache is not None:
            try:
                cache.stop()
            except Exception:
                pass
        logger.warning("[公共资源缓存] 接入失败，继续正常加载：%s", type(exc).__name__)
        return None


def stop_asset_cache(cache) -> None:
    """停止回放与后台填充，保留摘要供稍后的流量采集收口。"""
    if cache is None:
        return
    try:
        result = cache.stop()
        logger.info(
            "[公共资源缓存] 已停止：命中=%s，写入=%s，填充下载=%s 字节",
            result.get("hits", 0), result.get("stores", 0), result.get("anonymous_fill_bytes", 0),
        )
    except Exception as exc:
        logger.warning("[公共资源缓存] 停止异常：%s", type(exc).__name__)


def stop_registration_asset_cache(cache) -> None:
    """兼容注册入口，由持有缓存的外层流程停止。"""
    stop_asset_cache(cache)
