# -*- coding: utf-8 -*-
"""通过支持的邮箱服务缓存扫描 OpenAI 封号邮件信号。

扫描过程不读取或刷新 OpenAI access token，只查询高置信度邮件信号，
并把不含正文和凭据的结果写回本地账号记录。
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import uuid
from datetime import datetime, timezone

from config.schema import get_config_snapshot
from core.runtime import scheduler_state
from core.runtime.periodic import PeriodicThread
from core.operations.runtime import OperationCancelled
from core.operations import task_gateway as account_task_store
from core.storage import accounts as db
from core.storage.operations import runtime as operation_runtime_store
from core.storage.accounts import deactivation_mail as mail_store
from core.storage import records as record_store
from core.storage.operations import bulk_submission, common, schema
from core.operations.account_receipts import source_prefix
from core.email.cloudflare.client import CFTempMailError
from core.email.cloudflare.client import scan_openai_deactivation as scan_cloudflare_deactivation
from core.email.email_butler.client import EmailButlerClientError, scan_openai_deactivation
from core.email.forward_imap import ForwardIMAPError
from core.email.forward_imap import scan_openai_deactivation as scan_hme_deactivation
from core.email.forward_imap import scan_openai_deactivation_bulk as scan_hme_deactivation_bulk
from core.operations.reporter import TaskReporter
from core.operations.executor import configured_workers

logger = logging.getLogger('core.deactivation_mail_service')


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
_SCHEDULER = PeriodicThread("deactivation-mail-scheduler")
_SUPPORTED_SOURCES = {"email_butler", "cloudflare", "icloud_hide"}
_HME_SCAN_MODE = "shared_mailbox_recipient_search"
_HME_VALIDATION_METHOD = "mailbox_recipient_search"
# operation 存储会把单层列表限制为 120 项。这里用更小的分块嵌套保存目标，
# 既保留通用存储的限流边界，也避免大批 HME 账号只持久化前 120 个。
# 调度器单轮最多读取 5000 个账号，因此 100 x 50 的两层结构足够覆盖当前上限。
_HME_PAYLOAD_CHUNK_SIZE = 100
_HME_PAYLOAD_MAX_ACCOUNTS = 5000
_ACCEPTANCE_CHUNK_SIZE = 500
_INTERRUPTED_SCAN_ERROR = "WebUI 重启导致封号邮件扫描中断，请重新扫描"
_PERMANENT_EMAIL_BUTLER_SCAN_ERRORS = (
    ("http 404", "email account not found"),
    ("http 403", "email is not registered for openai"),
)
_BUTLER_SCAN_ERROR = "signal_scan_unsupported: Email Butler v2 仅提供验证码接口，暂不支持封号邮件扫描"

# The lookback setting predates C's canonical schema and is still a local
# compatibility setting.  Keep it in the same durable snapshot envelope as
# the canonical revision so a queued scan does not change its time window when
# process configuration is reloaded.  Mailbox endpoints, API keys, IMAP
# passwords, and sidecar credentials stay on-demand in their clients.
DEACTIVATION_CONFIG_ALLOWLIST = {
    "lookback_days": "EMAIL_BUTLER_RISK_SCAN_LOOKBACK_DAYS",
}


def _config_snapshot_provider():
    snapshot = get_config_snapshot()
    values = snapshot.as_dict()
    values["EMAIL_BUTLER_RISK_SCAN_LOOKBACK_DAYS"] = _LOOKBACK_DAYS
    return {"revision": snapshot.revision, "values": values}


def _snapshot_lookback_days(config_snapshot: dict | None = None) -> int:
    value = _LOOKBACK_DAYS
    if isinstance(config_snapshot, dict) and config_snapshot.get("lookback_days") is not None:
        value = config_snapshot.get("lookback_days")
    try:
        value = int(value or 120)
    except (TypeError, ValueError):
        value = 120
    return max(1, min(value, 365))

class _ReporterAdapter:
    """Route mailbox scan progress through the shared operation context."""

    def __init__(self, task_id: int | None, context=None):
        self._legacy = TaskReporter(task_id) if context is None else None
        self._context = context

    def start(self, message: str = "开始执行") -> None:
        if self._context is None:
            self._legacy.start(message)
            self._legacy.stage("preflight", "running", message)
        else:
            self._context.report(stage="preflight", state="running", message=message)

    def stage(self, stage: str, state: str, message: str, **kwargs) -> None:
        if self._context is None:
            self._legacy.stage(stage, state, message, **kwargs)
        else:
            self._context.report(stage=stage, state=state, message=message, **kwargs)

    def note(self, message: str, *, stage: str = "event", **kwargs) -> None:
        if self._context is None:
            self._legacy.note(message, stage=stage, **kwargs)
        else:
            self._context.report(stage=stage, message=message, **kwargs)

    def finish(self, *, status: str, message: str, **kwargs) -> None:
        if self._context is None:
            self._legacy.finish(status=status, message=message, **kwargs)
            return
        summary = dict(kwargs.get("result_summary") or {})
        for key in ("route", "validation_method"):
            if kwargs.get(key) is not None:
                summary[key] = kwargs[key]
        self._context.finish(
            status=status,
            message=message,
            error=kwargs.get("error"),
            result_summary=summary,
        )


def _checkpoint(context, message: str = "用户手动停止封号邮件扫描") -> None:
    if context is not None:
        context.checkpoint(message)
        # ``CancellationToken`` deliberately rate-limits ordinary polls. A
        # maintenance checkpoint immediately after the shared IMAP call must
        # force a fresh read before fanout, otherwise a cancellation arriving
        # during that call could be silently missed by the cached result.
        if context.is_cancel_requested(force=True):
            raise OperationCancelled(message)


def _is_permanent_email_butler_scan_error(exc: BaseException) -> bool:
    """Return whether a Butler scan error cannot be fixed by retrying."""
    if not isinstance(exc, EmailButlerClientError):
        return False
    if getattr(exc, 'error_code', '') in {'signal_scan_unsupported', 'api_version_retired'}:
        return True
    message = str(exc).lower()
    return any(
        status_marker in message and error_marker in message
        for status_marker, error_marker in _PERMANENT_EMAIL_BUTLER_SCAN_ERRORS
    )


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


def _scan(
    account_id: int,
    trigger: str,
    task_id: int | None = None,
    operation_context=None,
    config_snapshot: dict | None = None,
) -> None:
    reporter = _ReporterAdapter(task_id, operation_context)
    source = ""
    active_stage = "preflight"
    lookback_days = _snapshot_lookback_days(config_snapshot)
    try:
        _checkpoint(operation_context)
        reporter.start(message="校验封号邮件扫描账号与邮箱来源")
        account = db.get_account(account_id)
        if not account:
            reporter.note("账号已删除，取消封号邮件扫描", stage="preflight", detail={"cancelled": True})
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
                "preserve_checked_at": True,
                "error": "该账号邮箱来源暂不支持封号邮件扫描",
            })
            reporter.stage("preflight", "skipped", "该账号邮箱来源暂不支持封号邮件扫描")
            reporter.finish(
                status="unsupported",
                message="该账号邮箱来源暂不支持封号邮件扫描",
                result_summary={"email_source": source},
                validation_method="mailbox_cache",
            )
            return
        email = str(account.get("email") or "").strip()
        if "@" not in email:
            raise ValueError("封号邮件扫描缺少有效邮箱")
        db.update_account_deactivation_mail(account_id, {"status": "running", "trigger": trigger})
        _checkpoint(operation_context, "封号邮件扫描预检完成前检查取消状态")
        reporter.stage(
            "preflight", "success", "封号邮件扫描预检通过",
            detail={"email_source": source, "lookback_days": lookback_days},
        )
        active_stage = "mailbox_scan"
        reporter.stage(
            "mailbox_scan", "running",
            message=f"读取 {source} 邮箱缓存，回溯 {lookback_days} 天",
            detail={"email_source": source, "lookback_days": lookback_days},
        )
        _checkpoint(operation_context, "读取邮箱缓存前检查取消状态")
        if source == "email_butler":
            result = scan_openai_deactivation(account.get("email") or "", lookback_days=lookback_days)
        elif source == "icloud_hide":
            email = str(account.get("email") or "").strip().lower()
            result = scan_hme_deactivation_bulk([email], lookback_days=lookback_days).get(email)
            if not isinstance(result, dict):
                raise ForwardIMAPError(f"批量封号邮件扫描未返回账号结果: {account_id}")
        else:
            result = scan_cloudflare_deactivation(account.get("email") or "", lookback_days=lookback_days)
        if not isinstance(result, dict):
            raise ForwardIMAPError("邮件信号扫描未返回有效结果")
        if result.get("ok", True) is False:
            raise ForwardIMAPError(str(result.get("error") or result.get("error_code") or "邮件信号扫描未返回有效结果"))
        _checkpoint(operation_context, "邮箱扫描完成后确认取消状态")
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
    except account_task_store.OperationLeaseLost:
        # Let the gateway preserve the attempt as request_unknown when a lease
        # heartbeat/fence is lost while the mailbox client may still be active.
        raise
    except OperationCancelled as exc:
        error = str(exc) or "封号邮件扫描任务已取消"
        db.update_account_deactivation_mail(account_id, {
            "status": "cancelled", "trigger": trigger, "error": error,
        })
        reporter.note(error, stage=active_stage, level="WARNING", detail={"cancelled": True})
        reporter.finish(status="cancelled", message="封号邮件扫描任务已取消", error=error)
    except (EmailButlerClientError, CFTempMailError, ForwardIMAPError) as exc:
        if _is_permanent_email_butler_scan_error(exc) or 'signal_scan_unsupported' in str(exc):
            error = str(exc)
            db.update_account_deactivation_mail(account_id, {
                "status": "unsupported", "trigger": trigger, "error": error, "preserve_checked_at": True,
            })
            logger.info(
                "[DeactivationMail] account=%s Butler mailbox is unavailable; scan unsupported: %s",
                account_id, exc,
            )
            reporter.stage(
                "mailbox_scan", "skipped", "Email Butler 当前不支持该邮件扫描",
                level="WARNING", detail={"error": error, "permanent": True},
            )
            reporter.finish(
                status="unsupported",
                message="Email Butler 当前不支持该邮件扫描",
                error=error,
                result_summary={
                    "email_source": source,
                    "permanent": True,
                },
                validation_method="mailbox_cache",
            )
            return
        db.update_account_deactivation_mail(account_id, {
            "status": "failed", "trigger": trigger, "error": str(exc),
        })
        logger.warning("[DeactivationMail] account=%s scan failed: %s", account_id, exc)
        reporter.stage(active_stage, "failed", "封号邮件扫描失败", level="ERROR", detail={"error": str(exc)})
        reporter.finish(
            status="failed",
            message="封号邮件扫描失败",
            error=str(exc),
            validation_method="mailbox_cache",
        )
    except (account_task_store.OperationSettlementPending, account_task_store.OperationSettlementConflict, account_task_store.OperationSettlementFenced):
        raise
    except Exception as exc:
        db.update_account_deactivation_mail(account_id, {
            "status": "failed",
            "trigger": trigger,
            "error": f"{type(exc).__name__}: {exc}",
        })
        logger.exception("[DeactivationMail] account=%s unexpected failure", account_id)
        reporter.stage(
            active_stage, "failed", "封号邮件扫描预检失败" if active_stage == "preflight" else "封号邮件扫描异常",
            level="ERROR", detail={"error": f"{type(exc).__name__}: {exc}"},
        )
        reporter.finish(
            status="failed",
            message="封号邮件扫描异常",
            error=f"{type(exc).__name__}: {exc}",
            validation_method="mailbox_cache",
        )


def _normalise_hme_entries(entries) -> list[dict]:
    """Validate the alias snapshot carried by one durable bulk Run."""
    normalized: list[dict] = []
    seen: set[int] = set()
    for raw in entries or []:
        if not isinstance(raw, dict):
            continue
        try:
            account_id = int(raw.get("account_id") or 0)
        except (TypeError, ValueError):
            continue
        email = str(raw.get("email") or "").strip().lower()
        if account_id <= 0 or account_id in seen or "@" not in email:
            continue
        seen.add(account_id)
        normalized.append({"account_id": account_id, "email": email})
    return normalized


def _pack_hme_entries(entries) -> list[list[dict]]:
    """把 HME 目标编码成不会触发 operation 单层列表截断的持久化结构。"""
    normalized = _normalise_hme_entries(entries)
    return [
        normalized[index:index + _HME_PAYLOAD_CHUNK_SIZE]
        for index in range(0, len(normalized), _HME_PAYLOAD_CHUNK_SIZE)
    ]


def _hme_entries_from_run_data(data: dict | None) -> list[dict]:
    """读取新版分块结构，并兼容已经入库的旧版 ``accounts`` 列表。"""
    payload = data if isinstance(data, dict) else {}
    batches = payload.get("account_batches")
    flattened: list[dict] = []
    if isinstance(batches, list):
        for batch in batches:
            if isinstance(batch, list):
                flattened.extend(item for item in batch if isinstance(item, dict))
    if flattened:
        return _normalise_hme_entries(flattened)
    return _normalise_hme_entries(payload.get("accounts"))


def _local_time(value: object) -> datetime | None:
    """把账号兼容投影里的本地无时区时间转换成 UTC。"""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone(timezone.utc)


def _projection_was_requeued_after_recovery(account: dict, run: dict) -> bool:
    """避免旧 Run 的恢复结果覆盖恢复后重新入队的扫描。"""
    recovered_at = _parse_time(run.get("completed_at"))
    if recovered_at is None:
        return False
    return any(
        (timestamp := _local_time(account.get(key))) is not None and timestamp > recovered_at
        for key in (
            "deactivation_mail_scan_queued_at",
            "deactivation_mail_scan_started_at",
        )
    )


def reconcile_interrupted_scans(*, limit: int = 500) -> int:
    """清理 worker 重启留下的封号邮件扫描投影，不覆盖后续新任务。"""
    runs = operation_runtime_store.list_interrupted_runtime_runs(
        task_type="deactivation_mail",
        recovery_reason="worker_restart",
        limit=limit,
    )
    repaired = 0
    for run in runs:
        run_repaired = 0
        data = run.get("data") if isinstance(run.get("data"), dict) else {}
        if bool(data.get("bulk")):
            entries = _hme_entries_from_run_data(data)
        elif run.get("account_id") is not None:
            entries = [{"account_id": int(run["account_id"])}]
        else:
            entries = []
        for offset in range(0, len(entries), _HME_PAYLOAD_CHUNK_SIZE):
            block = entries[offset:offset + _HME_PAYLOAD_CHUNK_SIZE]
            with record_store.transaction() as conn:
                accounts = mail_store.load_many([int(entry["account_id"]) for entry in block], conn=conn)
                changes = {}
                for account_id, account in accounts.items():
                    if str(account.get("deactivation_mail_scan_status") or "") not in {"queued", "running"}:
                        continue
                    if _projection_was_requeued_after_recovery(account, run):
                        continue
                    changes[account_id] = {"status": "failed", "trigger": str(run.get("trigger") or "scheduled"),
                        "error": _INTERRUPTED_SCAN_ERROR, "preserve_checked_at": True}
                count = len(mail_store.update_many(changes, conn=conn, accounts=accounts))
            repaired += count
            run_repaired += count
        operation_runtime_store.mark_runtime_run_projection_reconciled(
            int(run["id"]), repaired_count=run_repaired,
        )
    if repaired:
        logger.warning(
            "[DeactivationMail] 已收口 %s 个因 WebUI 重启中断的扫描投影",
            repaired,
        )
    return repaired


def _scan_hme_group(
    context,
    entries: list[dict],
    trigger: str,
    config_snapshot: dict | None = None,
) -> None:
    """Scan all HME aliases once and fan out terminal business results.

    The durable Run owns the shared mailbox lease through its anchor account.
    This function intentionally contains no queue or worker thread: one
    operation handler performs one read-only bulk IMAP search and records each
    alias independently so a missing result or a write error cannot erase the
    other aliases' evidence.
    """
    submitted_entries = entries
    entries = []
    active_stage = "preflight"
    processed: dict[int, str] = {}

    def report_account(account_id: int, status: str, message: str, *, error: str | None = None) -> None:
        detail = {
            "account_id": account_id,
            "email_source": "icloud_hide",
            "scan_mode": _HME_SCAN_MODE,
            "result_status": status,
        }
        if error:
            detail["error"] = error[:500]
        level = "INFO" if status == "success" else "WARNING" if status in {"cancelled", "unsupported"} else "ERROR"
        # 单个别名的结果不代表共享扫描已完成；主阶段只由批次汇总收口。
        event = {
            "stage": active_stage, "message": message, "detail": detail,
            "event_type": f"note.{level.lower()}", "level": level,
        }
        try:
            context.report(**event)
        except (account_task_store.OperationLeaseLost, account_task_store.OperationSettlementPending, account_task_store.OperationSettlementConflict, account_task_store.OperationSettlementFenced):
            raise
        except Exception:
            # A reporting failure must not prevent the remaining aliases from
            # receiving their independent database result.
            logger.exception("[DeactivationMail] HME 账号事件写入失败: account_id=%s", account_id)

    def mark_remaining(status: str, error: str) -> int:
        remaining = [entry for entry in entries if int(entry["account_id"]) not in processed]
        count = 0
        for offset in range(0, len(remaining), _HME_PAYLOAD_CHUNK_SIZE):
            block = remaining[offset:offset + _HME_PAYLOAD_CHUNK_SIZE]
            safe_error = str(error or "封号邮件扫描未完成")[:500]
            try:
                committed = mail_store.update_many({int(entry["account_id"]): {
                    "status": status, "trigger": trigger, "error": safe_error,
                } for entry in block})
            except (account_task_store.OperationLeaseLost, account_task_store.OperationSettlementPending,
                    account_task_store.OperationSettlementConflict, account_task_store.OperationSettlementFenced):
                raise
            except Exception:
                logger.exception("[DeactivationMail] HME 未完成账号集合状态写入失败")
                continue
            for account_id in committed:
                processed[account_id] = status
                report_account(account_id, status,
                    "封号邮件扫描已取消" if status == "cancelled" else "封号邮件扫描失败", error=safe_error)
                count += 1
        return count

    try:
        context.report(stage="preflight", state="running", message="校验 HME 批量扫描账号与邮箱")
        entries = _normalise_hme_entries(submitted_entries)
        lookback_days = _snapshot_lookback_days(config_snapshot)
        _checkpoint(context, "批量读取 HME 邮箱前检查取消状态")
        if not entries:
            error = "iCloud HME 批量扫描缺少有效账号"
            context.report(stage="preflight", state="failed", message=error, level="ERROR")
            context.finish(
                status="failed", message=error, error=error,
                result_summary={"account_count": 0, "scan_mode": _HME_SCAN_MODE},
            )
            return
        for offset in range(0, len(entries), _HME_PAYLOAD_CHUNK_SIZE):
            _checkpoint(context, "写入 HME 批量运行状态前检查取消状态")
            mail_store.update_many({int(entry["account_id"]): {"status": "running", "trigger": trigger}
                for entry in entries[offset:offset + _HME_PAYLOAD_CHUNK_SIZE]})
        _checkpoint(context, "HME 批量扫描预检完成前检查取消状态")
        context.report(
            stage="preflight", state="success", message="HME 批量扫描预检通过",
            detail={"account_count": len(entries), "email_source": "icloud_hide", "lookback_days": lookback_days},
        )
        active_stage = "mailbox_scan"
        context.report(
            stage="mailbox_scan",
            state="running",
            message=f"一次读取 iCloud HME 共享邮箱并检索 {len(entries)} 个别名",
            detail={
                "account_count": len(entries),
                "email_source": "icloud_hide",
                "lookback_days": lookback_days,
                "scan_mode": _HME_SCAN_MODE,
            },
        )
        _checkpoint(context, "批量 HME 检索前检查取消状态")
        results = scan_hme_deactivation_bulk(
            [entry["email"] for entry in entries],
            lookback_days=lookback_days,
        )
        if not isinstance(results, dict):
            raise ForwardIMAPError("批量封号邮件扫描未返回结果映射")
        _checkpoint(context, "批量 HME 检索完成后确认取消状态")

        for offset in range(0, len(entries), _HME_PAYLOAD_CHUNK_SIZE):
            _checkpoint(context, "写回 HME 账号结果前检查取消状态")
            payloads = {}
            for entry in entries[offset:offset + _HME_PAYLOAD_CHUNK_SIZE]:
                account_id = int(entry["account_id"])
                result = results.get(entry["email"])
                if not isinstance(result, dict):
                    payload = {"status": "failed", "error": f"批量封号邮件扫描未返回账号结果: {account_id}"}
                elif result.get("ok", True) is False:
                    status = "unsupported" if result.get("error_code") == "signal_scan_unsupported" else "failed"
                    payload = {**result, "status": status, "error": str(result.get("error") or "该别名扫描失败")[:500]}
                    if status == "unsupported":
                        payload["preserve_checked_at"] = True
                else:
                    payload = {**result, "status": "success", "ok": True}
                payloads[account_id] = {**payload, "trigger": trigger}
            try:
                committed = mail_store.update_many(payloads)
            except (account_task_store.OperationLeaseLost, account_task_store.OperationSettlementPending,
                    account_task_store.OperationSettlementConflict, account_task_store.OperationSettlementFenced):
                raise
            except Exception as exc:
                error = f"账号结果写回失败: {type(exc).__name__}: {str(exc)[:300]}"
                payloads = {account_id: {"status": "failed", "trigger": trigger, "error": error} for account_id in payloads}
                committed = mail_store.update_many(payloads)
            for account_id in committed:
                payload = payloads[account_id]
                status = payload["status"]
                processed[account_id] = status
                report_account(account_id, status,
                    "发现高置信度封号邮件" if payload.get("detected") else
                    "未发现封号邮件" if status == "success" else
                    "当前邮箱服务不支持封号邮件扫描" if status == "unsupported" else "封号邮件扫描失败",
                    error=payload.get("error") or None)
            if len(committed) != len(payloads):
                raise RuntimeError("部分 HME 账号不存在，未写入扫描结果")

        failed_count = sum(status == "failed" for status in processed.values())
        unsupported_count = sum(status == "unsupported" for status in processed.values())
        summary = {
            "account_count": len(entries),
            "completed_count": len(processed),
            "success_count": len(entries) - failed_count - unsupported_count,
            "failed_count": failed_count,
            "unsupported_count": unsupported_count,
            "partial_failure": bool(failed_count),
            "email_source": "icloud_hide",
            "scan_mode": _HME_SCAN_MODE,
            "validation_method": _HME_VALIDATION_METHOD,
        }
        if failed_count:
            error = f"{failed_count}/{len(entries)} 个 HME 别名扫描失败"
            context.report(stage="mailbox_scan", state="failed", message=error, level="ERROR", detail=summary)
            context.finish(status="failed", message=error, error=error, result_summary=summary)
        elif unsupported_count:
            context.report(stage="mailbox_scan", state="skipped",
                message=f"{unsupported_count} 个账号的邮箱服务不支持封号邮件扫描", level="WARNING", detail=summary)
            context.finish(status="unsupported" if unsupported_count == len(entries) else "partial_success",
                message="部分或全部邮箱服务不支持封号邮件扫描", result_summary=summary)
        else:
            context.report(
                stage="mailbox_scan", state="success", message=f"已完成 {len(entries)} 个 HME 别名扫描",
                detail=summary,
            )
            context.finish(
                status="success",
                message=f"已完成 {len(entries)} 个 HME 别名扫描",
                result_summary=summary,
            )
    except account_task_store.OperationLeaseLost:
        raise
    except OperationCancelled as exc:
        reason = str(exc) or "封号邮件扫描任务已取消"
        cancelled_count = mark_remaining("cancelled", reason)
        context.report(stage=active_stage, message=reason, event_type="note.warning", detail={"cancelled": True})
        context.finish(
            status="cancelled",
            message="封号邮件扫描任务已取消",
            error=reason,
            result_summary={
                "account_count": len(entries),
                "completed_count": len(processed) - cancelled_count,
                "cancelled_count": cancelled_count,
                "email_source": "icloud_hide",
                "scan_mode": _HME_SCAN_MODE,
            },
        )
    except (account_task_store.OperationSettlementPending, account_task_store.OperationSettlementConflict, account_task_store.OperationSettlementFenced):
        raise
    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)[:500]}"
        failed_count = mark_remaining("failed", error)
        context.report(
            stage=active_stage, state="failed",
            message="HME 批量扫描预检失败" if active_stage == "preflight" else "iCloud HME 批量扫描失败",
            level="ERROR", detail={"error": error},
        )
        context.finish(
            status="failed",
            message="iCloud HME 批量扫描失败",
            error=error,
            result_summary={
                "account_count": len(entries),
                "completed_count": len(processed) - failed_count,
                "failed_count": failed_count,
                "partial_failure": bool(failed_count and failed_count < len(entries)),
                "email_source": "icloud_hide",
                "scan_mode": _HME_SCAN_MODE,
                "validation_method": _HME_VALIDATION_METHOD,
            },
        )


def _numeric_batch_id(value: str | int | None) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip().isdigit() else None
    except (TypeError, ValueError):
        return None


def _hme_anchor(entries: list[dict]) -> tuple[int, str]:
    """Choose one real HME account as the durable shared-mailbox anchor.

    ``operation_runs`` can fence an account/resource pair, not an arbitrary
    mailbox configuration.  All iCloud HME submissions therefore use the
    lowest current HME account as their stable anchor, so two disjoint alias
    requests cannot start two simultaneous full shared-mailbox scans.  The
    submitted aliases remain the fanout set; the anchor is only a lease key.
    """
    fallback = min(
        ((int(entry["account_id"]), str(entry.get("email") or "").strip().lower()) for entry in entries),
        key=lambda item: item[0],
    )
    candidates: list[tuple[int, str]] = []
    try:
        for account in db.list_accounts(limit=50000, archived=False):
            if str(account.get("email_source") or "").strip().lower() != "icloud_hide":
                continue
            try:
                account_id = int(account.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if account_id > 0:
                candidates.append((
                    account_id,
                    str(account.get("email") or "").strip().lower(),
                ))
    except Exception:
        # The submitted aliases are already enough to make a valid lease. A
        # scheduling inventory failure must not turn a user request into a
        # silent drop; it only weakens the global-anchor serialization for
        # this one submission.
        logger.exception("[DeactivationMail] HME lease anchor inventory failed")
    if not candidates:
        return fallback
    anchor_id, anchor_email = min(candidates, key=lambda item: item[0])
    return anchor_id, anchor_email or fallback[1]


def _native_response(submitted: dict, *, account_id: int, email: str, trigger: str) -> dict:
    accepted = bool(submitted.get("accepted"))
    response = {
        "accepted": accepted,
        "busy": bool(submitted.get("busy")) and not accepted,
        "account_id": account_id,
        "email": email,
        "status": submitted.get("status") or ("queued" if accepted else "failed"),
        "trigger": trigger,
        "task_id": submitted.get("task_id"),
        "run_id": submitted.get("run_id"),
        "reused": bool(submitted.get("reused")),
    }
    if submitted.get("error"):
        response["error"] = submitted["error"]
    return response


def _handle_deactivation_operation(context):
    if context.account_id is None:
        context.report(stage="preflight", state="failed", message="封号邮件扫描缺少账号", level="ERROR")
        context.finish(status="failed", message="封号邮件扫描缺少账号", error="封号邮件扫描缺少账号")
        return None
    data = context.run.get("data")
    if not isinstance(data, dict):
        data = {}
    trigger = str(context.run.get("trigger") or "manual")
    with context.lease(resource_family="mailbox_scan", scope_kind="final"):
        if bool(data.get("bulk")):
            _scan_hme_group(
                context,
                _hme_entries_from_run_data(data),
                trigger,
                context.config_snapshot,
            )
        else:
            account = db.get_account(int(context.account_id))
            source = str((account or {}).get("email_source") or "").strip().lower()
            if source == "icloud_hide":
                _scan_hme_group(
                    context,
                    [{
                        "account_id": int(context.account_id),
                        "email": str((account or {}).get("email") or context.email),
                    }],
                    trigger,
                    context.config_snapshot,
                )
            else:
                _scan(
                    int(context.account_id),
                    trigger,
                    task_id=int(context.task_id),
                    operation_context=context,
                    config_snapshot=context.config_snapshot,
                )
    return None


def register_actions() -> None:
    account_task_store.register_operation_actions(
        "deactivation_mail",
        retry_handler=account_task_store.default_operation_retry,
        cancel_handler=account_task_store.default_operation_cancel,
        terminate_handler=account_task_store.default_operation_terminate,
    )


def register_operation_handlers() -> bool:
    register = getattr(account_task_store, "register_operation_handler", None)
    if not callable(register):
        return False
    register(
        "deactivation_mail",
        _handle_deactivation_operation,
        source_systems=("native_operations",),
        config_allowlist=DEACTIVATION_CONFIG_ALLOWLIST,
    )
    register_actions()
    return True


def start_dispatcher() -> bool:
    if not register_operation_handlers():
        return False
    starter = getattr(account_task_store, "start_dispatcher", None)
    return bool(starter()) if callable(starter) else False


def _submit_native_scan(
    *, account_id: int, email: str, trigger: str, batch_id: str | None,
    idempotency_key: str | None,
    account_request_key: str | None = None,
) -> dict:
    register_operation_handlers()
    key = str(idempotency_key or "").strip() or None
    source_id = (
        f"maintenance:deactivation_mail:{account_id}:{key}"
        if key else f"maintenance:deactivation_mail:{account_id}:{uuid.uuid4().hex}"
    )
    return account_task_store.submit_durable_operation(
        task_type="deactivation_mail",
        account_id=account_id,
        email=email,
        trigger=trigger,
        source_system="native_operations",
        source_id=source_id,
        idempotency_key=key,
        **({"account_request_key": account_request_key} if account_request_key else {}),
        batch_id=_numeric_batch_id(batch_id),
        resource_family="mailbox_scan",
        data={
            "email_source": "mailbox_cache",
            "lookback_days": _LOOKBACK_DAYS,
        },
        config_snapshot_provider=_config_snapshot_provider,
        config_allowlist=DEACTIVATION_CONFIG_ALLOWLIST,
        dispatch=True,
    )


def _submit_native_hme_group(
    *, anchor_account_id: int, anchor_email: str, entries: list[dict], trigger: str,
    batch_id: str | None, idempotency_key: str | None,
    account_request_key: str | None = None,
) -> dict:
    """Persist one durable coordinator Run for one shared HME bulk search."""
    register_operation_handlers()
    normalized = _normalise_hme_entries(entries)
    if not normalized:
        raise ValueError("iCloud HME 批量扫描缺少有效账号")
    if len(normalized) > _HME_PAYLOAD_MAX_ACCOUNTS:
        raise ValueError(
            f"iCloud HME 单次批量扫描最多 {_HME_PAYLOAD_MAX_ACCOUNTS} 个账号"
        )
    packed_entries = _pack_hme_entries(normalized)
    key = str(idempotency_key or "").strip() or None
    source_id = (
        f"maintenance:deactivation_mail:bulk:{key}"
        if key else f"maintenance:deactivation_mail:bulk:{uuid.uuid4().hex}"
    )
    request_fields = {}
    if account_request_key:
        targets = ",".join(str(account_id) for account_id in sorted(item["account_id"] for item in normalized))
        request_fields = {
            "account_request_key": account_request_key,
            "account_request_target": "hme:" + hashlib.sha256(targets.encode("ascii")).hexdigest(),
        }
    return account_task_store.submit_durable_operation(
        task_type="deactivation_mail",
        account_id=int(anchor_account_id),
        email=str(anchor_email or normalized[0]["email"]),
        trigger=trigger,
        source_system="native_operations",
        source_id=source_id,
        idempotency_key=key,
        **request_fields,
        batch_id=_numeric_batch_id(batch_id),
        resource_family="mailbox_scan",
        data={
            "bulk": True,
            "scan_mode": _HME_SCAN_MODE,
            "lookback_days": _LOOKBACK_DAYS,
            "account_count": len(normalized),
            "account_batches": packed_entries,
        },
        config_snapshot_provider=_config_snapshot_provider,
        config_allowlist=DEACTIVATION_CONFIG_ALLOWLIST,
        dispatch=True,
    )


def _enqueue_native_bulk(
    account_ids: list[int], trigger: str = "manual_bulk", batch_id: str | None = None,
    idempotency_key: str | None = None,
    account_request_key: str | None = None,
) -> dict:
    from core.accounts.bulk_submission import _ids
    ids, invalid = _ids(account_ids)
    skipped = [{"id": item.get("id"), "error": "ID 非法"} for item in invalid]
    started, busy = [], []
    trigger = str(trigger or "manual_bulk")
    request_key = str(idempotency_key or "").strip() or None
    snapshot = _config_snapshot_provider()
    record_store.init()
    schema.init_operation_schema()
    batch_value = _numeric_batch_id(batch_id)
    fresh_count = 0
    with common._connect() as conn, conn.cursor() as cur:
        # HME uses one stable global anchor even for disjoint selected aliases.
        # Find it first to keep every account lock in ID order.
        anchor = mail_store.hme_anchor(conn=conn)
        lock_ids = sorted(set(ids) | ({int(anchor["id"])} if anchor else set()))
        accounts = mail_store.load_many(lock_ids, conn=conn)
        hme, ordinary, projections = [], [], {}
        for account_id in ids:
            account = accounts.get(account_id)
            if not account:
                skipped.append({"id": account_id, "error": "账号不存在"})
                continue
            source = str(account.get("email_source") or "").strip().lower()
            if source not in _SUPPORTED_SOURCES or source == "email_butler":
                error = _BUTLER_SCAN_ERROR if source == "email_butler" else "该账号邮箱来源暂不支持封号邮件扫描"
                projections[account_id] = {"status": "unsupported", "trigger": trigger, "error": error, "preserve_checked_at": True}
                skipped.append({"id": account_id, "unsupported": True, "error": error,
                    "error_code": "signal_scan_unsupported" if source == "email_butler" else "email_scan_connector_unsupported"})
                continue
            email = str(account.get("email") or "").strip()
            if source == "icloud_hide":
                if "@" not in email:
                    skipped.append({"id": account_id, "error": "待扫描隐藏邮箱地址无效"})
                else:
                    hme.append({"account_id": account_id, "email": email.lower()})
            else:
                ordinary.append({"account_id": account_id, "email": email})
        if len(hme) > _HME_PAYLOAD_MAX_ACCOUNTS:
            raise ValueError(f"iCloud HME 单次批量扫描最多 {_HME_PAYLOAD_MAX_ACCOUNTS} 个账号")
        groups = []
        for entry in ordinary:
            account_id = entry["account_id"]
            source = (f"{source_prefix(account_request_key)}:deactivation_mail:{trigger}:{account_id}" if account_request_key else
                f"maintenance:deactivation_mail:{account_id}:{request_key + ':' + str(account_id) if request_key else uuid.uuid4().hex}")
            groups.append(({"task_type": "deactivation_mail", "account_id": account_id, "email": entry["email"],
                "source_system": "native_operations", "source_id": source, "trigger": trigger,
                "resource_family": "mailbox_scan", "data": {"email_source": "mailbox_cache", "lookback_days": _LOOKBACK_DAYS},
                "config_snapshot": snapshot, "config_allowlist": DEACTIVATION_CONFIG_ALLOWLIST}, [entry]))
        if hme:
            target_ids = ",".join(str(item["account_id"]) for item in sorted(hme, key=lambda item: item["account_id"]))
            source = (f"{source_prefix(account_request_key)}:deactivation_mail:{trigger}:hme:" + hashlib.sha256(target_ids.encode("ascii")).hexdigest()
                if account_request_key else f"maintenance:deactivation_mail:bulk:{request_key + ':accounts:' + target_ids if request_key else uuid.uuid4().hex}")
            chosen = anchor or min(hme, key=lambda item: item["account_id"])
            groups.append(({"task_type": "deactivation_mail", "account_id": int(chosen.get("id") or chosen["account_id"]),
                "email": chosen["email"], "source_system": "native_operations", "source_id": source,
                "trigger": trigger, "resource_family": "mailbox_scan", "data": {"bulk": True,
                    "scan_mode": _HME_SCAN_MODE, "lookback_days": _LOOKBACK_DAYS, "account_count": len(hme),
                    "account_batches": _pack_hme_entries(hme)}, "config_snapshot": snapshot,
                "config_allowlist": DEACTIVATION_CONFIG_ALLOWLIST}, hme))
        prior = {}
        if groups:
            cur.execute(f"""SELECT t.source_id,t.data,t.batch_id,t.id AS task_id,r.id AS run_id,r.status
                FROM {common._table('operation_tasks')} t LEFT JOIN LATERAL (SELECT id,status
                    FROM {common._table('operation_runs')} WHERE task_id=t.id
                    ORDER BY run_no {'ASC' if account_request_key else 'DESC'},id {'ASC' if account_request_key else 'DESC'} LIMIT 1) r ON TRUE
                WHERE t.source_system='native_operations' AND t.source_id=ANY(%s)""", ([spec["source_id"] for spec, _ in groups],))
            prior = {row["source_id"]: dict(row) for row in cur.fetchall()}
        cur.execute(f"""SELECT account_id,task_id,id AS run_id,status FROM {common._table('operation_runs')}
            WHERE account_id=ANY(%s) AND resource_family='mailbox_scan' AND status=ANY(%s) ORDER BY id""",
            (lock_ids, list(common._ACTIVE_RUN_STATUSES)))
        active = {int(row["account_id"]): dict(row) for row in cur.fetchall()}
        fresh = []
        def append_receipts(submitted, entries, *, shared=False):
            for entry in entries:
                started.append({"id": entry["account_id"], "account_id": entry["account_id"], "accepted": True,
                    "task_id": submitted["task_id"], "run_id": submitted["run_id"], "reused": bool(submitted.get("reused")),
                    **({"shared_scan": True} if shared else {})})
        for spec, entries in groups:
            shared = bool(spec["data"].get("bulk"))
            owned = prior.get(spec["source_id"])
            if not account_request_key and common._account_is_deactivated(accounts.get(spec["account_id"])):
                skipped.extend({"id": item["account_id"], "error": "账号已废号，禁止创建任务", "error_code": "account_deactivated"}
                    for item in entries)
            elif owned:
                if account_request_key and common._task_is_user_deleted({"data": owned.get("data") or {}}):
                    skipped.extend({"id": item["account_id"], "error": "原任务已从任务中心删除，请重新发起操作"} for item in entries)
                else:
                    append_receipts({**owned, "reused": True}, entries, shared=shared)
                    batch_value = batch_value or owned.get("batch_id")
            elif common._account_is_deactivated(accounts.get(spec["account_id"])):
                skipped.extend({"id": item["account_id"], "error": "账号已废号，禁止创建任务", "error_code": "account_deactivated"}
                    for item in entries)
            elif spec["account_id"] in active:
                existing = active[spec["account_id"]]
                busy.extend({"id": item["account_id"], "task_id": existing["task_id"], "run_id": existing["run_id"],
                    "busy": True, "error": "封号邮件扫描正在进行", **({"shared_scan": True} if shared else {})} for item in entries)
            else:
                fresh.append((spec, entries))
        if fresh:
            if batch_value is None:
                batch_value = int(bulk_submission.create_batch(conn=conn, task_type="deactivation_mail",
                    requested_count=len(ids), trigger=trigger, title="批量封号邮件扫描")["id"])
            for ordinal, (spec, _) in enumerate(fresh, 1):
                spec.update(batch_id=batch_value, batch_ordinal=ordinal)
            receipts = []
            for offset in range(0, len(fresh), _ACCEPTANCE_CHUNK_SIZE):
                receipts.extend(bulk_submission.create_specs(
                    [spec for spec, _ in fresh[offset:offset + _ACCEPTANCE_CHUNK_SIZE]], conn=conn,
                ))
            for receipt, (spec, entries) in zip(receipts, fresh):
                append_receipts(receipt, entries, shared=bool(spec["data"].get("bulk")))
                if not receipt.get("reused"):
                    fresh_count += 1
                    projections.update({item["account_id"]: {"status": "queued", "trigger": trigger} for item in entries})
        projection_ids = list(projections)
        for offset in range(0, len(projection_ids), _ACCEPTANCE_CHUNK_SIZE):
            mail_store.update_many(
                {value: projections[value] for value in projection_ids[offset:offset + _ACCEPTANCE_CHUNK_SIZE]},
                conn=conn, accounts=accounts,
            )
    if fresh_count:
        account_task_store.notify_dispatch()
    order = {account_id: index for index, account_id in enumerate(ids)}
    started.sort(key=lambda item: order[item["account_id"]])
    return {"started": started, "busy": busy, "skipped": skipped, "batch_id": batch_value}


def enqueue_bulk(
    account_ids: list[int], trigger: str = "manual_bulk", batch_id: str | None = None,
    idempotency_key: str | None = None,
    account_request_key: str | None = None,
) -> dict:
    """Submit mailbox scans to the durable queue; the scheduler remains a producer."""
    return _enqueue_native_bulk(
        account_ids, trigger=trigger, batch_id=batch_id, idempotency_key=idempotency_key,
        **({"account_request_key": account_request_key} if account_request_key else {}),
    )


def enqueue(
    account_id: int, trigger: str = "manual", batch_id: str | None = None,
    idempotency_key: str | None = None,
    account_request_key: str | None = None,
) -> dict:
    result = enqueue_bulk(
        [account_id], trigger=trigger, batch_id=batch_id, idempotency_key=idempotency_key,
        **({"account_request_key": account_request_key} if account_request_key else {}),
    )
    if result["started"]:
        item = result["started"][0]
        return {
            "accepted": True,
            "account_id": int(item["account_id"]),
            "task_id": int(item["task_id"]),
            "run_id": item.get("run_id"),
            "reused": bool(item.get("reused")),
        }
    if result["busy"]:
        return {"accepted": False, **result["busy"][0]}
    if result["skipped"]:
        return {"accepted": False, **result["skipped"][0]}
    return {"accepted": False, "error": "没有可扫描的账号"}


def enqueue_due_accounts() -> dict:
    if not scheduler_enabled():
        return {"started": 0, "skipped": 0}
    now = datetime.now(timezone.utc)
    interval_seconds = scheduler_interval_seconds()
    due_ids: list[int] = []
    unsupported_projections = {}
    skipped = 0
    accounts = db.list_accounts(limit=5000, archived=False)
    unsupported = _butler_scan_account_ids(accounts)
    for account in accounts:
        if str(account.get("email_source") or "").strip().lower() not in _SUPPORTED_SOURCES:
            continue
        if int(account.get('id') or 0) in unsupported:
            skipped += 1
            if (account.get('deactivation_mail_scan_status') != 'unsupported'
                    or account.get('deactivation_mail_error') != _BUTLER_SCAN_ERROR):
                unsupported_projections[int(account['id'])] = {
                    'status': 'unsupported', 'trigger': 'scheduled', 'error': _BUTLER_SCAN_ERROR,
                    'preserve_checked_at': True}
            continue
        checked = _parse_time(account.get("deactivation_mail_checked_at"))
        if checked and (now - checked).total_seconds() < interval_seconds:
            skipped += 1
            continue
        due_ids.append(int(account.get("id") or 0))
    projection_ids = list(unsupported_projections)
    for offset in range(0, len(projection_ids), _ACCEPTANCE_CHUNK_SIZE):
        mail_store.update_many({
            value: unsupported_projections[value]
            for value in projection_ids[offset:offset + _ACCEPTANCE_CHUNK_SIZE]
        })
    result = enqueue_bulk(due_ids, trigger="scheduled") if due_ids else {"started": [], "busy": [], "skipped": []}
    skipped += len(result.get("busy") or []) + len(result.get("skipped") or [])
    return {"started": len(result.get("started") or []), "skipped": skipped}


def _butler_scan_account_ids(accounts: list[dict]) -> set[int]:
    """按原固定连接批量识别 v2，避免周期任务重复排入不支持的扫描。"""
    from config import email as config
    from core.email.email_butler.bridge import inbox_profiles_for_addresses

    hme = [row for row in accounts if str(row.get('email_source') or '').lower() == 'icloud_hide']
    profiles = inbox_profiles_for_addresses([row.get('email') or '' for row in hme]) if hme else {}
    default_butler = str(getattr(config, 'ICLOUD_HME_INBOX_MODE', '') or '').lower() == 'forward_butler'
    ids = {int(row['id']) for row in accounts if str(row.get('email_source') or '').lower() == 'email_butler'}
    for row in hme:
        profile = profiles.get(str(row.get('email') or '').strip().lower())
        if ((profile or {}).get('connector') == 'forward_butler'
                or profile is None and default_butler):
            ids.add(int(row['id']))
    return ids


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
        stop=_SCHEDULER.stop_event,
        lifecycle=_SCHEDULER,
    )


def start_periodic_scanner() -> bool:
    """Start one observable producer; work remains behind runtime admission."""
    try:
        started = _SCHEDULER.start(_scheduler_loop)
    except Exception:
        logger.exception("Periodic scheduler start failed; it may be retried")
        return False

    return started


def stop_periodic_scanner(timeout: float = 2.0) -> bool:
    return _SCHEDULER.stop(timeout)


def scheduler_status() -> dict:
    return _SCHEDULER.status(enabled=scheduler_enabled())


def queue_settings() -> dict:
    return {
        "enabled": scheduler_enabled(),
        "workers": configured_workers(),
        "interval_seconds": scheduler_interval_seconds(),
        "lookback_days": _LOOKBACK_DAYS,
        # The durable operation store is the authority for active scans; keep
        # the historical response key without exposing a process-local list.
        "in_flight": [],
        # The old in-process HME queue was removed; queued work is now visible
        # through operation_runs and is therefore restart-safe.
        "icloud_pending": 0,
    }


# Register with the shared dispatcher when the runtime imports this service.
# The runtime owns the single dispatcher thread; this call only installs the
# task-type handler and its allowlist.
register_actions()
