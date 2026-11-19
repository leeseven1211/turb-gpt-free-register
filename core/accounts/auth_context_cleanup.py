# -*- coding: utf-8 -*-
"""私有认证上下文的周期维护。

关闭时仅保留休眠调度线程，不创建或访问私有上下文表。启动时已启用才执行
一次有上限的清理；周期循环读取最新开关并按数据库中的时间记录继续调度。
"""
from __future__ import annotations

import logging
import threading

from core.runtime import scheduler_state
from core.runtime.periodic import PeriodicThread

logger = logging.getLogger('core.account_auth_context_service')

SCHEDULER_TASK = "account_auth_context_cleanup"
_INTERVAL_SECONDS = 24 * 60 * 60
_INITIAL_DELAY_SECONDS = 60
_LOCK = threading.RLock()
_SCHEDULER = PeriodicThread("account-auth-context-cleanup")


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
    from core.runtime.process import get_runtime_context
    initial = _INITIAL_DELAY_SECONDS
    if get_runtime_context() is not None and scheduler_enabled():
        initial = 0
    scheduler_state.run_periodic(
        task=SCHEDULER_TASK,
        label="AccountAuthContext",
        work=cleanup_once,
        enabled=scheduler_enabled,
        interval_seconds=scheduler_interval_seconds,
        initial_delay_seconds=initial,
        stop=_SCHEDULER.stop_event,
        lifecycle=_SCHEDULER,
    )


def _startup_cleanup() -> None:
    # Preserve the unmanaged CLI's synchronous startup contract. Managed
    # startup delegates all cleanup to the gated persisted scheduler.
    from core.runtime.process import get_runtime_context
    if get_runtime_context() is not None or not scheduler_enabled():
        return
    try:
        cleanup_once()
    except Exception:
        logger.exception("[AccountAuthContext] startup cleanup failed")


def start_periodic_cleanup() -> bool:
    """Start one observable producer; work remains behind runtime admission."""
    try:
        started = _SCHEDULER.start(_scheduler_loop, before_start=_startup_cleanup)
    except Exception:
        logger.exception("Periodic scheduler start failed; it may be retried")
        return False

    return started


def stop_periodic_cleanup(timeout: float = 2.0) -> bool:
    return _SCHEDULER.stop(timeout)


def scheduler_status() -> dict:
    return _SCHEDULER.status(enabled=scheduler_enabled())


def reset_for_tests() -> None:
    if not stop_periodic_cleanup(timeout=2.0):
        raise RuntimeError("periodic_scheduler_still_running")


__all__ = [
    "SCHEDULER_TASK",
    "cleanup_once",
    "reset_for_tests",
    "scheduler_enabled",
    "scheduler_interval_seconds",
    "start_periodic_cleanup",
    "stop_periodic_cleanup",
    "scheduler_status",
]
