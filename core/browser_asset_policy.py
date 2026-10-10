"""Roxy 注册公共静态缓存的配置与生命周期边界。"""
from __future__ import annotations

import logging
from pathlib import Path

from config import browser as _cfg

logger = logging.getLogger(__name__)


def start_registration_asset_cache(opened, *, proxy_url: str | None = None):
    """仅新注册入口启用；匿名填充只能沿本次新建环境的已知线路。"""
    mode = str(getattr(_cfg, "BROWSER_PUBLIC_ASSET_CACHE_MODE", "off") or "off")
    if mode not in {"observe", "enabled"}:
        return None
    cache = None
    try:
        from core.public_asset_cache import PublicAssetCache

        # 已有 Profile 的实际线路可能与本次参数不同，不能猜测并回退直连。
        fill_proxy = proxy_url if getattr(opened, "created_by_run", False) else None
        cache = PublicAssetCache(
            getattr(opened, "debugger_address", ""),
            Path(__file__).resolve().parent.parent / "run" / "public-asset-cache",
            mode=mode,
            max_total_bytes=int(_cfg.BROWSER_PUBLIC_ASSET_CACHE_MAX_MB) * 1024 * 1024,
            proxy_url=fill_proxy,
            allow_direct=False,
        )
        if not cache.start():
            cache.stop()
            return None
        capture = getattr(opened, "traffic_capture", None)
        if capture is not None:
            capture.set_public_asset_cache(cache)
        logger.info("[公共资源缓存] 注册缓存已启动：模式=%s", mode)
        return cache
    except Exception as exc:
        if cache is not None:
            try:
                cache.stop()
            except Exception:
                pass
        logger.warning("[公共资源缓存] 接入失败，继续正常加载：%s", type(exc).__name__)
        return None


def stop_registration_asset_cache(cache) -> None:
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
