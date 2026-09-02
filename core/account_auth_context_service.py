# -*- coding: utf-8 -*-
"""Periodic maintenance for private account-authentication context rows.

The raw context feature is deliberately opt-in.  When it is disabled this
module neither creates the private table nor starts a worker.  When enabled,
startup performs one bounded cleanup and a daily database-backed scheduler
continues the same bounded operation across WebUI restarts.
"""
from __future__ import annotations

import logging
import threading

from core import scheduler_state

logger = logging.getLogger(__name__)

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
    from core.storage.account_auth import cleanup_expired_auth_contexts

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
    """Run startup cleanup and start at most one daily maintenance worker."""
    global _SCHEDULER_STARTED
    if not scheduler_enabled():
        logger.info("[AccountAuthContext] cleanup disabled")
        return False
    with _LOCK:
        if _SCHEDULER_STARTED:
            return False
        _SCHEDULER_STARTED = True
    try:
        removed = cleanup_once()
        if removed:
            logger.info("[AccountAuthContext] startup cleanup removed=%s", removed)
    except Exception:
        logger.exception("[AccountAuthContext] startup cleanup failed; scheduler will retry")
    threading.Thread(
        target=_scheduler_loop,
        name="account-auth-context-cleanup",
        daemon=True,
    ).start()
    logger.info("[AccountAuthContext] cleanup enabled interval=%ss", _INTERVAL_SECONDS)
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
