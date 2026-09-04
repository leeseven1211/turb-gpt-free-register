# -*- coding: utf-8 -*-
"""通过支持的邮箱服务缓存扫描 OpenAI 封号邮件信号。

扫描过程不读取或刷新 OpenAI access token，只查询高置信度邮件信号，
并把不含正文和凭据的结果写回本地账号记录。
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone

from core import scheduler_state
from core.operations import task_gateway as account_task_store
from core.storage import accounts as db
from core.cf_temp_mail_client import CFTempMailError
from core.cf_temp_mail_client import scan_openai_deactivation as scan_cloudflare_deactivation
from core.email_butler_client import EmailButlerClientError, scan_openai_deactivation
from core.forward_imap_client import ForwardIMAPError
from core.forward_imap_client import scan_openai_deactivation as scan_hme_deactivation
from core.forward_imap_client import scan_openai_deactivation_bulk as scan_hme_deactivation_bulk
from core.task_reporter import TaskReporter
from core.account_operation_executor import configured_workers
from core.account_operation_executor import executor as _EXECUTOR

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    return max(low, min(value, high))


_INTERVAL_SECONDS = _env_int("EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS", 21600, 900, 604800)
_INITIAL_DELAY_SECONDS = _env_int("EMAIL_BUTLER_RISK_SCAN_INITIAL_DELAY_SECONDS", 90, 5, 3600)
_LOOKBACK_DAYS = _env_int("EMAIL_BUTLER_RISK_SCAN_LOOKBACK_DAYS", 120, 1, 365)
_ENABLED = str(os.environ.get("EMAIL_BUTLER_RISK_SCAN_ENABLED", "1")).strip().lower() not in {
    "0", "false", "no", "off",
}

_LOCK = threading.RLock()
_ICLOUD_SNAPSHOT_LOCK = threading.Lock()
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


def _scan(account_id: int, trigger: str, task_id: int | None = None) -> None:
    reporter = TaskReporter(task_id)
    try:
        account = db.get_account(account_id)
        if not account:
            reporter.finish(
                status="cancelled",
                message="账号已删除，取消封号邮件扫描",
            )
            return
        source = str(account.get("email_source") or "").strip().lower()
        if source not in _SUPPORTED_SOURCES:
            db.update_account_deactivation_mail(account_id, {
                "status": "unsupported",
                "trigger": trigger,
                "error": "该账号邮箱来源暂不支持封号邮件扫描",
            })
            reporter.finish(
                status="unsupported",
                message="该账号邮箱来源暂不支持封号邮件扫描",
                result_summary={"email_source": source},
                validation_method="mailbox_cache",
            )
            return
        db.update_account_deactivation_mail(account_id, {"status": "running", "trigger": trigger})
        reporter.start(message="开始扫描封号邮件信号")
        reporter.stage(
            "mailbox_scan", "running",
            message=f"读取 {source} 邮箱缓存，回溯 {_LOOKBACK_DAYS} 天",
            detail={"email_source": source, "lookback_days": _LOOKBACK_DAYS},
        )
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
        reporter.stage(
            "mailbox_scan", "success",
            "发现高置信度封号邮件" if result.get("detected") else "未发现封号邮件",
            detail={"detected": bool(result.get("detected")), "email_source": source},
        )
        reporter.finish(
            status="success",
            message="发现高置信度封号邮件" if result.get("detected") else "未发现封号邮件",
            result_summary={
                "detected": bool(result.get("detected")),
                "checked_at": result.get("checked_at"),
                "received_at": result.get("received_at"),
                "subject": result.get("subject"),
                "sender": result.get("sender"),
                "confidence": result.get("confidence"),
                "email_source": source,
            },
            validation_method="mailbox_cache",
        )
    except (EmailButlerClientError, CFTempMailError, ForwardIMAPError) as exc:
        db.update_account_deactivation_mail(account_id, {
            "status": "failed", "trigger": trigger, "error": str(exc),
        })
        logger.warning("[DeactivationMail] account=%s scan failed: %s", account_id, exc)
        reporter.stage("mailbox_scan", "failed", "封号邮件扫描失败", level="ERROR", detail={"error": str(exc)})
        reporter.finish(
            status="failed",
            message="封号邮件扫描失败",
            error=str(exc),
            validation_method="mailbox_cache",
        )
    except Exception as exc:
        db.update_account_deactivation_mail(account_id, {
            "status": "failed",
            "trigger": trigger,
            "error": f"{type(exc).__name__}: {exc}",
        })
        logger.exception("[DeactivationMail] account=%s unexpected failure", account_id)
        reporter.stage(
            "mailbox_scan", "failed", "封号邮件扫描异常",
            level="ERROR", detail={"error": f"{type(exc).__name__}: {exc}"},
        )
        reporter.finish(
            status="failed",
            message="封号邮件扫描异常",
            error=f"{type(exc).__name__}: {exc}",
            validation_method="mailbox_cache",
        )
    finally:
        with _LOCK:
            _IN_FLIGHT.discard(int(account_id))


def _finish_enqueue_failure(entry: dict, trigger: str, exc: Exception) -> None:
    account_id = int(entry["account_id"])
    task_id = int(entry["task_id"])
    error = str(exc)
    with _LOCK:
        _IN_FLIGHT.discard(account_id)
    db.update_account_deactivation_mail(account_id, {
        "status": "failed", "trigger": trigger, "error": error,
    })
    account_task_store.finish_task(
        task_id,
        status="failed",
        message="封号邮件扫描任务入队失败",
        error=error,
    )


def _scan_group_failure(entry: dict, trigger: str, exc: Exception) -> None:
    """Finish one account in a failed shared-mailbox scan."""
    account_id = int(entry["account_id"])
    task_id = int(entry["task_id"])
    reporter = TaskReporter(task_id)
    error = str(exc)
    db.update_account_deactivation_mail(account_id, {
        "status": "failed", "trigger": trigger, "error": error,
    })
    logger.warning("[DeactivationMail] account=%s grouped scan failed: %s", account_id, exc)
    reporter.stage("mailbox_scan", "failed", "封号邮件扫描失败", level="ERROR", detail={"error": error})
    reporter.finish(
        status="failed",
        message="封号邮件扫描失败",
        error=error,
        validation_method="mailbox_snapshot",
    )


def _scan_group(entries: list[dict], trigger: str) -> None:
    """Scan one shared iCloud HME inbox and fan out per-account results."""
    started: list[dict] = []
    completed: set[int] = set()
    try:
        for entry in entries:
            account_id = int(entry["account_id"])
            task_id = int(entry["task_id"])
            started.append(entry)
            db.update_account_deactivation_mail(account_id, {"status": "running", "trigger": trigger})
            reporter = TaskReporter(task_id)
            reporter.start(message="开始扫描封号邮件信号")
            reporter.stage(
                "mailbox_scan", "running",
                message=f"读取 iCloud HME 共享邮箱快照，回溯 {_LOOKBACK_DAYS} 天",
                detail={
                    "email_source": "icloud_hide",
                    "lookback_days": _LOOKBACK_DAYS,
                    "scan_mode": "shared_mailbox_snapshot",
                },
            )

        # 同一个配置邮箱只允许一个快照同时运行；其它邮箱来源仍由公共线程池并行处理。
        with _ICLOUD_SNAPSHOT_LOCK:
            results = scan_hme_deactivation_bulk(
                [str(entry.get("email") or "") for entry in entries],
                lookback_days=_LOOKBACK_DAYS,
            )

        for entry in entries:
            account_id = int(entry["account_id"])
            task_id = int(entry["task_id"])
            email = str(entry.get("email") or "").strip().lower()
            result = results.get(email)
            if not isinstance(result, dict):
                raise ForwardIMAPError(f"批量封号邮件扫描未返回账号结果: {account_id}")
            db.update_account_deactivation_mail(account_id, {
                "status": "success",
                "trigger": trigger,
                **result,
            })
            reporter = TaskReporter(task_id)
            detected = bool(result.get("detected"))
            reporter.stage(
                "mailbox_scan", "success",
                "发现高置信度封号邮件" if detected else "未发现封号邮件",
                detail={
                    "detected": detected,
                    "email_source": "icloud_hide",
                    "scan_mode": "shared_mailbox_snapshot",
                },
            )
            reporter.finish(
                status="success",
                message="发现高置信度封号邮件" if detected else "未发现封号邮件",
                result_summary={
                    "detected": detected,
                    "checked_at": result.get("checked_at"),
                    "received_at": result.get("received_at"),
                    "subject": result.get("subject"),
                    "sender": result.get("sender"),
                    "confidence": result.get("confidence"),
                    "email_source": "icloud_hide",
                    "scan_mode": "shared_mailbox_snapshot",
                },
                validation_method="mailbox_snapshot",
            )
            completed.add(account_id)
    except (EmailButlerClientError, CFTempMailError, ForwardIMAPError) as exc:
        for entry in started:
            if int(entry["account_id"]) not in completed:
                _scan_group_failure(entry, trigger, exc)
    except Exception as exc:
        logger.exception("[DeactivationMail] grouped scan unexpected failure")
        for entry in started:
            if int(entry["account_id"]) not in completed:
                _scan_group_failure(entry, trigger, exc)
    finally:
        with _LOCK:
            for entry in entries:
                _IN_FLIGHT.discard(int(entry["account_id"]))


def enqueue_bulk(account_ids: list[int], trigger: str = "manual_bulk", batch_id: str | None = None) -> dict:
    """Queue account scans, grouping iCloud HME accounts by shared mailbox."""
    started: list[dict] = []
    busy: list[dict] = []
    skipped: list[dict] = []
    groups: dict[str, list[dict]] = {}
    seen: set[int] = set()

    for raw_id in account_ids or []:
        try:
            account_id = int(raw_id)
        except (TypeError, ValueError):
            skipped.append({"id": raw_id, "error": "ID 非法"})
            continue
        if account_id in seen:
            continue
        seen.add(account_id)
        account = db.get_account(account_id)
        if not account:
            skipped.append({"id": account_id, "error": "账号不存在"})
            continue
        task_id = account_task_store.create_task(
            task_type="deactivation_mail",
            account_id=account_id,
            email=str(account.get("email") or ""),
            trigger=str(trigger or "manual_bulk"),
            batch_id=batch_id,
        )
        source = str(account.get("email_source") or "").strip().lower()
        if source not in _SUPPORTED_SOURCES:
            db.update_account_deactivation_mail(account_id, {
                "status": "unsupported",
                "trigger": trigger,
                "error": "该账号邮箱来源暂不支持封号邮件扫描",
            })
            account_task_store.finish_task(
                task_id,
                status="unsupported",
                message="该账号邮箱来源不支持邮件扫描",
                result_summary={"email_source": source},
                validation_method="mailbox_cache",
            )
            skipped.append({
                "id": account_id,
                "task_id": task_id,
                "unsupported": True,
                "error": "该账号邮箱来源不支持邮件扫描",
            })
            continue
        with _LOCK:
            if account_id in _IN_FLIGHT:
                account_task_store.finish_task(
                    task_id,
                    status="cancelled",
                    message="同账号封号邮件扫描已在进行",
                )
                busy.append({
                    "id": account_id,
                    "task_id": task_id,
                    "busy": True,
                    "error": "封号邮件扫描正在进行",
                })
                continue
            _IN_FLIGHT.add(account_id)
        db.update_account_deactivation_mail(account_id, {"status": "queued", "trigger": trigger})
        groups.setdefault(source, []).append({
            "account_id": account_id,
            "task_id": task_id,
            "email": str(account.get("email") or ""),
        })

    for source, entries in groups.items():
        if source == "icloud_hide":
            try:
                _EXECUTOR.submit(_scan_group, entries, trigger)
            except Exception as exc:
                for entry in entries:
                    _finish_enqueue_failure(entry, trigger, exc)
                continue
            started.extend(
                {
                    "id": entry["account_id"],
                    "accepted": True,
                    "account_id": entry["account_id"],
                    "task_id": entry["task_id"],
                }
                for entry in entries
            )
            continue
        for entry in entries:
            try:
                _EXECUTOR.submit(_scan, int(entry["account_id"]), trigger, int(entry["task_id"]))
            except Exception as exc:
                _finish_enqueue_failure(entry, trigger, exc)
                continue
            started.append({
                "id": entry["account_id"],
                "accepted": True,
                "account_id": entry["account_id"],
                "task_id": entry["task_id"],
            })
    return {"started": started, "busy": busy, "skipped": skipped}


def enqueue(account_id: int, trigger: str = "manual", batch_id: str | None = None) -> dict:
    result = enqueue_bulk([account_id], trigger=trigger, batch_id=batch_id)
    if result["started"]:
        item = result["started"][0]
        return {
            "accepted": True,
            "account_id": int(item["account_id"]),
            "task_id": int(item["task_id"]),
        }
    if result["busy"]:
        return {"accepted": False, **result["busy"][0]}
    if result["skipped"]:
        return {"accepted": False, **result["skipped"][0]}
    return {"accepted": False, "error": "没有可扫描的账号"}


def enqueue_due_accounts() -> dict:
    now = datetime.now(timezone.utc)
    due_ids: list[int] = []
    skipped = 0
    for account in db.list_accounts(limit=5000, archived=False):
        if str(account.get("email_source") or "").strip().lower() not in _SUPPORTED_SOURCES:
            continue
        checked = _parse_time(account.get("deactivation_mail_checked_at"))
        if checked and (now - checked).total_seconds() < _INTERVAL_SECONDS:
            skipped += 1
            continue
        due_ids.append(int(account.get("id") or 0))
    result = enqueue_bulk(due_ids, trigger="scheduled") if due_ids else {"started": [], "busy": [], "skipped": []}
    skipped += len(result.get("busy") or []) + len(result.get("skipped") or [])
    return {"started": len(result.get("started") or []), "skipped": skipped}


SCHEDULER_TASK = "deactivation_mail_scan"


def scheduler_enabled() -> bool:
    """每轮重新读配置：WebUI 改完走 config.reload_all()，不应要求重启。"""
    from config import email as _email_cfg
    return bool(getattr(_email_cfg, "EMAIL_BUTLER_RISK_SCAN_ENABLED", True))


def scheduler_interval_seconds() -> int:
    from config import email as _email_cfg
    raw = int(getattr(_email_cfg, "EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS", 21600) or 21600)
    return max(900, min(604800, raw))


def _scheduler_loop() -> None:
    scheduler_state.run_periodic(
        task=SCHEDULER_TASK,
        label="DeactivationMail",
        work=enqueue_due_accounts,
        enabled=scheduler_enabled,
        interval_seconds=scheduler_interval_seconds,
        initial_delay_seconds=_INITIAL_DELAY_SECONDS,
    )


def start_periodic_scanner() -> bool:
    global _SCHEDULER_STARTED
    if not scheduler_enabled():
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
        configured_workers(),
    )
    return True


def queue_settings() -> dict:
    with _LOCK:
        in_flight = sorted(_IN_FLIGHT)
    return {
        "enabled": _ENABLED,
        "workers": configured_workers(),
        "interval_seconds": _INTERVAL_SECONDS,
        "lookback_days": _LOOKBACK_DAYS,
        "in_flight": in_flight,
    }
