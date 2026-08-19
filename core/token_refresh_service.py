# -*- coding: utf-8 -*-
"""ChatGPT accessToken 到期巡检与提前刷新调度。"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone

from core import db, scheduler_state
from core.chatgpt_plan import token_claims

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    return max(low, min(value, high))


_ENABLED = str(os.environ.get("AT_AUTO_REFRESH_ENABLED", "1")).strip().lower() not in {
    "0", "false", "no", "off",
}
_REFRESH_BEFORE_HOURS = _env_int("AT_REFRESH_BEFORE_HOURS", 24, 1, 168)
_SCAN_INTERVAL_SECONDS = _env_int("AT_REFRESH_SCAN_INTERVAL_SECONDS", 3600, 300, 86400)
_INITIAL_DELAY_SECONDS = _env_int("AT_REFRESH_INITIAL_DELAY_SECONDS", 120, 10, 3600)
_MAX_PER_CYCLE = _env_int("AT_REFRESH_MAX_PER_CYCLE", 20, 1, 200)
_LOCK = threading.RLock()
_SCHEDULER_STARTED = False


def _expires_in_seconds(access_token: str) -> tuple[float | None, dict]:
    claims = token_claims(access_token)
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        return None, claims
    return float(exp) - datetime.now(timezone.utc).timestamp(), claims


def enqueue_due_accounts() -> dict:
    """把已过期或进入刷新窗口的 AT 加入邮箱重登录刷新队列。"""
    from core.live_check_service import enqueue_account_live_check

    started = 0
    skipped = 0
    invalid = 0
    threshold = _REFRESH_BEFORE_HOURS * 3600
    metadata_items: list[tuple[int, str]] = []
    for account in db.list_accounts(limit=5000, archived=False):
        if started >= _MAX_PER_CYCLE:
            break
        if db.account_is_deactivated(account):
            skipped += 1
            continue
        if str(account.get("codex_status") or "").lower() == "deactivated":
            skipped += 1
            continue
        access_token = str(account.get("access_token") or "").strip()
        if not access_token:
            skipped += 1
            continue
        seconds_left, claims = _expires_in_seconds(access_token)
        account_id = int(account.get("id") or 0)
        metadata_items.append((account_id, access_token))
        if seconds_left is None:
            invalid += 1
            continue
        if seconds_left > threshold:
            skipped += 1
            continue
        result = enqueue_account_live_check(
            account_id=account_id,
            email=str(account.get("email") or ""),
            trigger="token_refresh_scheduled",
            proxy=None,
            force_refresh=True,
        )
        if result.get("accepted"):
            started += 1
            logger.info(
                "[AT Refresh] 已入队 account_id=%s expires_at=%s",
                account_id,
                claims.get("token_expires_at"),
            )
        else:
            skipped += 1
    db.sync_account_token_metadata(metadata_items)
    return {"started": started, "skipped": skipped, "invalid": invalid}


SCHEDULER_TASK = "at_refresh"


def scheduler_enabled() -> bool:
    """每轮重新读配置：WebUI 改完走 config.reload_all()，不应要求重启。"""
    from config import codex as _codex_cfg
    return bool(getattr(_codex_cfg, "AT_AUTO_REFRESH_ENABLED", True))


def scheduler_interval_seconds() -> int:
    from config import codex as _codex_cfg
    raw = int(getattr(_codex_cfg, "AT_REFRESH_SCAN_INTERVAL_SECONDS", 3600) or 3600)
    return max(300, min(86400, raw))


def _scheduler_loop() -> None:
    scheduler_state.run_periodic(
        task=SCHEDULER_TASK,
        label="AT Refresh",
        work=enqueue_due_accounts,
        enabled=scheduler_enabled,
        interval_seconds=scheduler_interval_seconds,
        initial_delay_seconds=_INITIAL_DELAY_SECONDS,
    )


def start_periodic_refresher() -> bool:
    global _SCHEDULER_STARTED
    if not scheduler_enabled():
        logger.info("[AT Refresh] periodic refresher disabled")
        return False
    with _LOCK:
        if _SCHEDULER_STARTED:
            return False
        _SCHEDULER_STARTED = True
    threading.Thread(target=_scheduler_loop, name="at-refresh-scheduler", daemon=True).start()
    logger.info(
        "[AT Refresh] enabled interval=%ss before=%sh max_per_cycle=%s next_due_in=%ss",
        scheduler_interval_seconds(),
        _REFRESH_BEFORE_HOURS,
        _MAX_PER_CYCLE,
        int(scheduler_state.seconds_until_due(SCHEDULER_TASK, scheduler_interval_seconds())),
    )
    return True


def settings() -> dict:
    return {
        "enabled": scheduler_enabled(),
        "refresh_before_hours": _REFRESH_BEFORE_HOURS,
        "scan_interval_seconds": scheduler_interval_seconds(),
        "max_per_cycle": _MAX_PER_CYCLE,
        "schedule": scheduler_state.describe(SCHEDULER_TASK, scheduler_interval_seconds()),
    }
