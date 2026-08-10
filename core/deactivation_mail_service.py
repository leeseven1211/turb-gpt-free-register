# -*- coding: utf-8 -*-
"""通过支持的邮箱服务缓存扫描 OpenAI 封号邮件信号。

扫描过程不读取或刷新 OpenAI access token，只查询高置信度邮件信号，
并把不含正文和凭据的结果写回本地账号记录。
"""
from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from core import db
from core.cf_temp_mail_client import CFTempMailError
from core.cf_temp_mail_client import scan_openai_deactivation as scan_cloudflare_deactivation
from core.email_butler_client import EmailButlerClientError, scan_openai_deactivation
from core.forward_imap_client import ForwardIMAPError
from core.forward_imap_client import scan_openai_deactivation as scan_hme_deactivation

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    return max(low, min(value, high))


_WORKERS = _env_int("EMAIL_BUTLER_RISK_SCAN_WORKERS", 2, 1, 8)
_INTERVAL_SECONDS = _env_int("EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS", 21600, 900, 604800)
_INITIAL_DELAY_SECONDS = _env_int("EMAIL_BUTLER_RISK_SCAN_INITIAL_DELAY_SECONDS", 90, 5, 3600)
_LOOKBACK_DAYS = _env_int("EMAIL_BUTLER_RISK_SCAN_LOOKBACK_DAYS", 120, 1, 365)
_ENABLED = str(os.environ.get("EMAIL_BUTLER_RISK_SCAN_ENABLED", "1")).strip().lower() not in {
    "0", "false", "no", "off",
}

_EXECUTOR = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix="deactivation-mail")
_LOCK = threading.RLock()
_IN_FLIGHT: set[int] = set()
_SCHEDULER_STARTED = False
_SUPPORTED_SOURCES = {"email_butler", "cloudflare", "icloud_hide"}


def _parse_time(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _scan(account_id: int, trigger: str) -> None:
    try:
        account = db.get_account(account_id)
        if not account:
            return
        source = str(account.get("email_source") or "").strip().lower()
        if source not in _SUPPORTED_SOURCES:
            db.update_account_deactivation_mail(account_id, {
                "status": "unsupported",
                "trigger": trigger,
                "error": "该账号邮箱来源暂不支持封号邮件扫描",
            })
            return
        db.update_account_deactivation_mail(account_id, {"status": "running", "trigger": trigger})
        if source == "email_butler":
            result = scan_openai_deactivation(account.get("email") or "", lookback_days=_LOOKBACK_DAYS)
        elif source == "icloud_hide":
            result = scan_hme_deactivation(account.get("email") or "", lookback_days=_LOOKBACK_DAYS)
        else:
            result = scan_cloudflare_deactivation(account.get("email") or "", lookback_days=_LOOKBACK_DAYS)
        db.update_account_deactivation_mail(account_id, {
            "status": "success",
            "trigger": trigger,
            **result,
        })
    except (EmailButlerClientError, CFTempMailError, ForwardIMAPError) as exc:
        db.update_account_deactivation_mail(account_id, {
            "status": "failed", "trigger": trigger, "error": str(exc),
        })
        logger.warning("[DeactivationMail] account=%s scan failed: %s", account_id, exc)
    except Exception as exc:
        db.update_account_deactivation_mail(account_id, {
            "status": "failed",
            "trigger": trigger,
            "error": f"{type(exc).__name__}: {exc}",
        })
        logger.exception("[DeactivationMail] account=%s unexpected failure", account_id)
    finally:
        with _LOCK:
            _IN_FLIGHT.discard(int(account_id))


def enqueue(account_id: int, trigger: str = "manual") -> dict:
    account = db.get_account(account_id)
    if not account:
        return {"accepted": False, "error": "账号不存在"}
    if str(account.get("email_source") or "").strip().lower() not in _SUPPORTED_SOURCES:
        db.update_account_deactivation_mail(account_id, {
            "status": "unsupported",
            "trigger": trigger,
            "error": "该账号邮箱来源暂不支持封号邮件扫描",
        })
        return {"accepted": False, "unsupported": True, "error": "该账号邮箱来源不支持邮件扫描"}
    with _LOCK:
        if int(account_id) in _IN_FLIGHT:
            return {"accepted": False, "busy": True, "error": "封号邮件扫描正在进行"}
        _IN_FLIGHT.add(int(account_id))
    db.update_account_deactivation_mail(account_id, {"status": "queued", "trigger": trigger})
    try:
        _EXECUTOR.submit(_scan, int(account_id), trigger)
    except Exception as exc:
        with _LOCK:
            _IN_FLIGHT.discard(int(account_id))
        db.update_account_deactivation_mail(account_id, {
            "status": "failed", "trigger": trigger, "error": str(exc),
        })
        return {"accepted": False, "error": "扫描任务入队失败"}
    return {"accepted": True, "account_id": int(account_id)}


def enqueue_due_accounts() -> dict:
    now = datetime.now(timezone.utc)
    started = 0
    skipped = 0
    for account in db.list_accounts(limit=5000, archived=False):
        if str(account.get("email_source") or "").strip().lower() not in _SUPPORTED_SOURCES:
            continue
        checked = _parse_time(account.get("deactivation_mail_checked_at"))
        if checked and (now - checked).total_seconds() < _INTERVAL_SECONDS:
            skipped += 1
            continue
        result = enqueue(int(account.get("id") or 0), trigger="scheduled")
        if result.get("accepted"):
            started += 1
        else:
            skipped += 1
    return {"started": started, "skipped": skipped}


def _scheduler_loop() -> None:
    stop = threading.Event()
    if stop.wait(_INITIAL_DELAY_SECONDS):
        return
    while True:
        try:
            result = enqueue_due_accounts()
            logger.info("[DeactivationMail] scheduled scan: %s", result)
        except Exception:
            logger.exception("[DeactivationMail] scheduled cycle failed")
        stop.wait(_INTERVAL_SECONDS)


def start_periodic_scanner() -> bool:
    global _SCHEDULER_STARTED
    if not _ENABLED:
        logger.info("[DeactivationMail] periodic scanner disabled")
        return False
    with _LOCK:
        if _SCHEDULER_STARTED:
            return False
        _SCHEDULER_STARTED = True
    threading.Thread(target=_scheduler_loop, name="deactivation-mail-scheduler", daemon=True).start()
    logger.info(
        "[DeactivationMail] scanner enabled interval=%ss lookback=%sd workers=%s",
        _INTERVAL_SECONDS,
        _LOOKBACK_DAYS,
        _WORKERS,
    )
    return True


def queue_settings() -> dict:
    with _LOCK:
        in_flight = sorted(_IN_FLIGHT)
    return {
        "enabled": _ENABLED,
        "workers": _WORKERS,
        "interval_seconds": _INTERVAL_SECONDS,
        "lookback_days": _LOOKBACK_DAYS,
        "in_flight": in_flight,
    }
