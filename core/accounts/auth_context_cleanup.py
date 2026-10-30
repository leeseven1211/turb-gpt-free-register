# -*- coding: utf-8 -*-
"""私有认证上下文的周期维护。

关闭时仅保留休眠调度线程，不创建或访问私有上下文表。启动时已启用才执行
一次有上限的清理；周期循环读取最新开关并按数据库中的时间记录继续调度。
"""
from __future__ import annotations

import logging
import threading

from core.runtime import scheduler_state

logger = logging.getLogger('core.account_auth_context_service')

SCHEDULER_TASK = "account_auth_context_cleanup"
_INTERVAL_SECONDS = 24 * 60 * 60
_INITIAL_DELAY_SECONDS = 60
_LOCK = threading.RLock()
_SCHEDULER_STARTED = False


def scheduler_enabled() -> bool:
    from config import account as account_config

    return bool(
        getattr(account_config, "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", False)
        and int(getattr(account_config, "ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS", 30) or 0) > 0
    )


def scheduler_interval_seconds() -> int:
    return _INTERVAL_SECONDS


def cleanup_once(*, limit: int = 500) -> int:
    """Delete one bounded batch of expired private contexts."""
    if not scheduler_enabled():
        return 0
    from core.storage.accounts.auth import cleanup_expired_auth_contexts

    return int(cleanup_expired_auth_contexts(limit=limit))


def _scheduler_loop() -> None:
    scheduler_state.run_periodic(
        task=SCHEDULER_TASK,
        label="AccountAuthContext",
        work=cleanup_once,
        enabled=scheduler_enabled,
        interval_seconds=scheduler_interval_seconds,
        initial_delay_seconds=_INITIAL_DELAY_SECONDS,
    )


def start_periodic_cleanup() -> bool:
    """启动唯一调度线程，仅在已启用时执行启动清理。"""
    global _SCHEDULER_STARTED
    with _LOCK:
        if _SCHEDULER_STARTED:
            return False
        if scheduler_enabled():
            try:
                removed = cleanup_once()
                if removed:
                    logger.info("[AccountAuthContext] 启动清理完成 removed=%s", removed)
            except Exception:
                logger.exception("[AccountAuthContext] 启动清理失败，后续按周期重试")
        try:
            threading.Thread(
                target=_scheduler_loop,
                name="account-auth-context-cleanup",
                daemon=True,
            ).start()
        except Exception:
            logger.exception("[AccountAuthContext] 调度线程启动失败，可再次启动")
            return False
        _SCHEDULER_STARTED = True
    logger.info(
        "[AccountAuthContext] 调度器已启动 enabled=%s interval=%ss",
        scheduler_enabled(), _INTERVAL_SECONDS,
    )
    return True


def reset_for_tests() -> None:
    global _SCHEDULER_STARTED
    with _LOCK:
        _SCHEDULER_STARTED = False


__all__ = [
    "SCHEDULER_TASK",
    "cleanup_once",
    "reset_for_tests",
    "scheduler_enabled",
    "scheduler_interval_seconds",
    "start_periodic_cleanup",
]
