# -*- coding: utf-8 -*-
"""通过支持的邮箱服务缓存扫描 OpenAI 封号邮件信号。

扫描过程不读取或刷新 OpenAI access token，只查询高置信度邮件信号，
并把不含正文和凭据的结果写回本地账号记录。
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import datetime, timezone

from config.schema import get_config_snapshot
from core import scheduler_state
from core.operation_runtime import OperationCancelled
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
_SCHEDULER_STARTED = False
_SUPPORTED_SOURCES = {"email_butler", "cloudflare", "icloud_hide"}
_HME_SCAN_MODE = "shared_mailbox_recipient_search"
_HME_VALIDATION_METHOD = "mailbox_recipient_search"
_PERMANENT_EMAIL_BUTLER_SCAN_ERRORS = (
    ("http 404", "email account not found"),
    ("http 403", "email is not registered for openai"),
)

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
    lookback_days = _snapshot_lookback_days(config_snapshot)
    try:
        _checkpoint(operation_context)
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
        reporter.finish(status="cancelled", message="封号邮件扫描任务已取消", error=error)
    except (EmailButlerClientError, CFTempMailError, ForwardIMAPError) as exc:
        if source == "email_butler" and _is_permanent_email_butler_scan_error(exc):
            error = str(exc)
            db.update_account_deactivation_mail(account_id, {
                "status": "unsupported", "trigger": trigger, "error": error,
            })
            logger.info(
                "[DeactivationMail] account=%s Butler mailbox is unavailable; scan unsupported: %s",
                account_id, exc,
            )
            reporter.stage(
                "mailbox_scan", "skipped", "Email Butler 中不存在可扫描邮箱",
                level="WARNING", detail={"error": error, "permanent": True},
            )
            reporter.finish(
                status="unsupported",
                message="Email Butler 中不存在可扫描邮箱",
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
    entries = _normalise_hme_entries(entries)
    lookback_days = _snapshot_lookback_days(config_snapshot)
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
        try:
            context.report(
                stage="mailbox_scan",
                state="success" if status == "success" else "failed",
                message=message,
                detail=detail,
            )
        except Exception:
            # A reporting failure must not prevent the remaining aliases from
            # receiving their independent database result.
            logger.exception("[DeactivationMail] HME 账号事件写入失败: account_id=%s", account_id)

    def mark_remaining(status: str, error: str) -> int:
        count = 0
        for entry in entries:
            account_id = int(entry["account_id"])
            if account_id in processed:
                continue
            safe_error = str(error or "封号邮件扫描未完成")[:500]
            try:
                db.update_account_deactivation_mail(account_id, {
                    "status": status,
                    "trigger": trigger,
                    "error": safe_error,
                })
            except Exception:
                logger.exception(
                    "[DeactivationMail] HME 未完成账号状态写入失败: account_id=%s status=%s",
                    account_id,
                    status,
                )
            processed[account_id] = status
            report_account(
                account_id,
                status,
                "封号邮件扫描已取消" if status == "cancelled" else "封号邮件扫描失败",
                error=safe_error,
            )
            count += 1
        return count

    if not entries:
        context.finish(
            status="failed",
            message="iCloud HME 批量扫描缺少有效账号",
            error="iCloud HME 批量扫描缺少有效账号",
            result_summary={"account_count": 0, "scan_mode": _HME_SCAN_MODE},
        )
        return

    try:
        _checkpoint(context, "批量读取 HME 邮箱前检查取消状态")
        for entry in entries:
            db.update_account_deactivation_mail(int(entry["account_id"]), {
                "status": "running",
                "trigger": trigger,
            })
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

        for entry in entries:
            account_id = int(entry["account_id"])
            email = entry["email"]
            _checkpoint(context, "写回 HME 账号结果前检查取消状态")
            result = results.get(email)
            if not isinstance(result, dict):
                status = "failed"
                error = f"批量封号邮件扫描未返回账号结果: {account_id}"
                payload = {"ok": False, "status": status, "error": error}
            elif result.get("ok", True) is False:
                status = "failed"
                error = str(result.get("error") or "该别名扫描失败")[:500]
                payload = dict(result)
                payload.update({"ok": False, "status": status, "error": error})
            else:
                status = "success"
                error = ""
                payload = dict(result)
                payload.update({"ok": True, "status": status})
            payload["trigger"] = trigger
            try:
                db.update_account_deactivation_mail(account_id, payload)
            except Exception as exc:
                status = "failed"
                error = f"账号结果写回失败: {type(exc).__name__}: {str(exc)[:300]}"
                try:
                    db.update_account_deactivation_mail(account_id, {
                        "status": status,
                        "trigger": trigger,
                        "error": error,
                    })
                except Exception:
                    logger.exception(
                        "[DeactivationMail] HME 账号失败状态也无法写回: account_id=%s",
                        account_id,
                    )
            processed[account_id] = status
            report_account(
                account_id,
                status,
                "发现高置信度封号邮件" if payload.get("detected") else
                "未发现封号邮件" if status == "success" else "封号邮件扫描失败",
                error=error or None,
            )

        failed_count = sum(status == "failed" for status in processed.values())
        summary = {
            "account_count": len(entries),
            "completed_count": len(processed),
            "success_count": len(entries) - failed_count,
            "failed_count": failed_count,
            "partial_failure": bool(failed_count),
            "email_source": "icloud_hide",
            "scan_mode": _HME_SCAN_MODE,
            "validation_method": _HME_VALIDATION_METHOD,
        }
        if failed_count:
            error = f"{failed_count}/{len(entries)} 个 HME 别名扫描失败"
            context.finish(status="failed", message=error, error=error, result_summary=summary)
        else:
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
    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)[:500]}"
        failed_count = mark_remaining("failed", error)
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
        context.finish(status="failed", message="封号邮件扫描缺少账号", error="封号邮件扫描缺少账号")
        return None
    data = context.run.get("data")
    if not isinstance(data, dict):
        data = {}
    trigger = str(context.run.get("trigger") or "manual")
    with context.lease(resource_family="mailbox_scan"):
        if bool(data.get("bulk")):
            _scan_hme_group(
                context,
                data.get("accounts"),
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
    return True


def start_dispatcher() -> bool:
    if not register_operation_handlers():
        return False
    starter = getattr(account_task_store, "start_dispatcher", None)
    return bool(starter()) if callable(starter) else False


def _submit_native_scan(
    *, account_id: int, email: str, trigger: str, batch_id: str | None,
    idempotency_key: str | None,
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
) -> dict:
    """Persist one durable coordinator Run for one shared HME bulk search."""
    register_operation_handlers()
    normalized = _normalise_hme_entries(entries)
    if not normalized:
        raise ValueError("iCloud HME 批量扫描缺少有效账号")
    key = str(idempotency_key or "").strip() or None
    source_id = (
        f"maintenance:deactivation_mail:bulk:{key}"
        if key else f"maintenance:deactivation_mail:bulk:{uuid.uuid4().hex}"
    )
    return account_task_store.submit_durable_operation(
        task_type="deactivation_mail",
        account_id=int(anchor_account_id),
        email=str(anchor_email or normalized[0]["email"]),
        trigger=trigger,
        source_system="native_operations",
        source_id=source_id,
        idempotency_key=key,
        batch_id=_numeric_batch_id(batch_id),
        resource_family="mailbox_scan",
        data={
            "bulk": True,
            "scan_mode": _HME_SCAN_MODE,
            "lookback_days": _LOOKBACK_DAYS,
            "accounts": normalized,
        },
        config_snapshot_provider=_config_snapshot_provider,
        config_allowlist=DEACTIVATION_CONFIG_ALLOWLIST,
        dispatch=True,
    )


def _enqueue_native_bulk(
    account_ids: list[int], trigger: str = "manual_bulk", batch_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    started: list[dict] = []
    busy: list[dict] = []
    skipped: list[dict] = []
    hme_entries: list[dict] = []
    seen: set[int] = set()
    trigger = str(trigger or "manual_bulk")
    request_key = str(idempotency_key or "").strip() or None
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
        source = str(account.get("email_source") or "").strip().lower()
        if source not in _SUPPORTED_SOURCES:
            db.update_account_deactivation_mail(account_id, {
                "status": "unsupported", "trigger": trigger,
                "error": "该账号邮箱来源暂不支持封号邮件扫描",
            })
            skipped.append({
                "id": account_id, "unsupported": True,
                "error": "该账号邮箱来源不支持邮件扫描",
            })
            continue
        if source == "icloud_hide":
            email = str(account.get("email") or "").strip().lower()
            if "@" not in email:
                skipped.append({
                    "id": account_id,
                    "error": "待扫描隐藏邮箱地址无效",
                })
                continue
            hme_entries.append({"account_id": account_id, "email": email})
            continue
        key = None
        if request_key:
            key = f"{request_key}:{account_id}"
        try:
            submitted = _submit_native_scan(
                account_id=account_id,
                email=str(account.get("email") or ""),
                trigger=trigger,
                batch_id=batch_id,
                idempotency_key=key,
            )
        except Exception as exc:
            skipped.append({
                "id": account_id,
                "error": f"封号邮件扫描持久化失败: {type(exc).__name__}: {str(exc)[:240]}",
            })
            continue
        item = _native_response(
            submitted,
            account_id=account_id,
            email=str(account.get("email") or ""),
            trigger=trigger,
        )
        if item["accepted"]:
            if not submitted.get("reused"):
                db.update_account_deactivation_mail(account_id, {"status": "queued", "trigger": trigger})
            started.append({
                "id": account_id,
                "accepted": True,
                "account_id": account_id,
                "task_id": item.get("task_id"),
                "run_id": item.get("run_id"),
                "reused": item.get("reused", False),
            })
        elif item.get("busy"):
            busy.append({
                "id": account_id,
                "task_id": item.get("task_id"),
                "run_id": item.get("run_id"),
                "busy": True,
                "error": item.get("error") or "封号邮件扫描正在进行",
            })
        else:
            skipped.append({"id": account_id, "error": item.get("error") or "封号邮件扫描未接受"})

    if hme_entries:
        account_ids_key = ",".join(str(entry["account_id"]) for entry in sorted(hme_entries, key=lambda item: item["account_id"]))
        group_key = f"{request_key}:accounts:{account_ids_key}" if request_key else None
        anchor_account_id, anchor_email = _hme_anchor(hme_entries)
        try:
            submitted = _submit_native_hme_group(
                anchor_account_id=anchor_account_id,
                anchor_email=anchor_email,
                entries=hme_entries,
                trigger=trigger,
                batch_id=batch_id,
                idempotency_key=group_key,
            )
        except Exception as exc:
            error = f"封号邮件批量扫描持久化失败: {type(exc).__name__}: {str(exc)[:240]}"
            skipped.extend({"id": entry["account_id"], "error": error} for entry in hme_entries)
        else:
            for entry in hme_entries:
                account_id = int(entry["account_id"])
                item = _native_response(
                    submitted,
                    account_id=account_id,
                    email=entry["email"],
                    trigger=trigger,
                )
                if item["accepted"]:
                    if not submitted.get("reused"):
                        db.update_account_deactivation_mail(
                            account_id,
                            {"status": "queued", "trigger": trigger},
                        )
                    started.append({
                        "id": account_id,
                        "accepted": True,
                        "account_id": account_id,
                        "task_id": item.get("task_id"),
                        "run_id": item.get("run_id"),
                        "reused": item.get("reused", False),
                        "shared_scan": True,
                    })
                elif item.get("busy"):
                    busy.append({
                        "id": account_id,
                        "task_id": item.get("task_id"),
                        "run_id": item.get("run_id"),
                        "busy": True,
                        "error": item.get("error") or "封号邮件扫描正在进行",
                        "shared_scan": True,
                    })
                else:
                    skipped.append({
                        "id": account_id,
                        "error": item.get("error") or "封号邮件扫描未接受",
                    })
    return {"started": started, "busy": busy, "skipped": skipped}


def enqueue_bulk(
    account_ids: list[int], trigger: str = "manual_bulk", batch_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Submit mailbox scans to the durable queue; the scheduler remains a producer."""
    return _enqueue_native_bulk(
        account_ids, trigger=trigger, batch_id=batch_id, idempotency_key=idempotency_key,
    )


def enqueue(
    account_id: int, trigger: str = "manual", batch_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    result = enqueue_bulk(
        [account_id], trigger=trigger, batch_id=batch_id, idempotency_key=idempotency_key,
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
    return {
        "enabled": _ENABLED,
        "workers": configured_workers(),
        "interval_seconds": _INTERVAL_SECONDS,
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
register_operation_handlers()
