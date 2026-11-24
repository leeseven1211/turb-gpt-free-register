# -*- coding: utf-8 -*-
"""Sub2API 异常账号巡检；只编排现有刷新、OAuth 和定向同步入口。"""
from __future__ import annotations

import importlib
import json
import logging
import re
import time
import uuid
from collections import Counter
from contextvars import ContextVar
from typing import Any

from config import email as email_config
from config import sub2api as _cfg
from core import db
from core.accounts.credentials import get_account_login_credentials
from core.codex import operation_service, token_refresh_service
from core.integrations.sub2api import client, jobs
from core.runtime import scheduler_state
from core.runtime.periodic import PeriodicThread
from core.storage import sub2api as repair_store
from core.storage.operations import runtime as operation_runtime_store
from core.operations import task_gateway
from core.integrations.sub2api import monitor_collections
from core.storage import sub2api_monitor as collection_store

logger = logging.getLogger(__name__)
_TASK = "sub2api_monitor"
_SCHEDULER = PeriodicThread("sub2api-monitor")
_ACTIVE = {"queued", "running", "cancelling", "settling", "waiting", "retrying", "stopping"}
_SUCCESS = {"success", "succeeded", "completed"}
_WAIT_STAGES = {"refresh_wait", "reauth_wait", "refresh_submitting", "reauth_submitting"}
_CONTINUATION_STAGES = _WAIT_STAGES | {"sync_wait"}
_SCAN = ContextVar("sub2api_monitor_scan", default=None)


def _now() -> float:
    return time.time()


def _enabled() -> bool:
    return bool(getattr(_cfg, "SUB2API_MONITOR_ENABLED", False))


def _periodic_enabled() -> bool:
    """新异常发现只遵守自动巡检开关。"""
    return _enabled()


def _continuation_repairs(backend: str) -> list[dict]:
    enabled = _enabled()
    return [row for row in repair_store.list_repairs(backend, active_only=True)
            if row.get("stage") in _CONTINUATION_STAGES and (enabled or row.get("manual_requested"))]


def _periodic_interval() -> int:
    return _interval()


def _interval() -> int:
    return max(1, int(getattr(_cfg, "SUB2API_MONITOR_INTERVAL_SECONDS", 300) or 300))


def _cooldown() -> int:
    return max(1, int(getattr(_cfg, "SUB2API_MONITOR_COOLDOWN_SECONDS", 300) or 300))


def _object(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            pass
    return {}


def _remote_email(row: dict) -> str:
    for value in (_object(row.get("credentials")).get("email"), _object(row.get("extra")).get("email"), row.get("email"), row.get("name")):
        address = str(value or "").strip().lower()
        if address.startswith("oauth---"):
            address = address[len("oauth---"):]
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", address):
            return address
    return ""


def _remote_error(row: dict) -> str:
    """分类只用于选择修复动作，绝不据 401 推断账号停用。"""
    text = " ".join(str(row.get(key) or "") for key in ("error_message", "error", "error_code", "http_status", "last_error")).lower()
    if re.search(r"account[_ -]deactivated|account[_ -]disabled|user[_ -]deactivated", text):
        return "remote_account_deactivated"
    if re.search(r"\b(?:429|5\d\d)\b|rate.?limit|too many requests|timeout|timed out|connection|network", text):
        return "remote_transient_error"
    if re.search(r"\b401\b|unauthori[sz]ed|invalid_grant|invalid[_ -](?:access[_ -])?token|token.+(?:expired|revoked|invalidated)|(?:expired|revoked).+token", text):
        return "remote_oauth_error"
    return "unrecognized_remote_error"


def _automatic_login_ready(account: dict) -> bool:
    """只读检查已保存的登录/收件资料；不申请邮箱或改动认证设置。"""
    scan = _SCAN.get()
    if scan is not None:
        return scan.login_ready(account)
    if account.get("email_invalid"):
        return False
    email = str(account.get("email") or "")
    password, secret = get_account_login_credentials(email)
    if str(account.get("twofa_status") or "").lower() in {"success", "enabled"} and not secret:
        return False
    if password:
        return True
    if not bool(getattr(email_config, "USE_EMAIL_SERVICE", True)):
        return False
    source = str(account.get("email_source") or "").strip()
    if not source:
        return False
    from core.email.derivation import find_binding
    if find_binding(email):
        return True
    if source == "cloudflare_domain":
        return bool(db.get_domain_email_by_email(email))
    if source == "email_butler":
        from core.email.email_butler.client import get_account_context, restore_local_account
        return bool(get_account_context(email) or restore_local_account(email))
    if source in {"outlook", "generic_api", "icloud_hide", "gptmail", "cloudflare", "mailnest", "cloudmail", "remail", "mailcode", "xigua"}:
        module = importlib.import_module(f"core.email.{source}.client")
        return bool(module.get_account_context(email))
    return False


def _save(backend: str, account_id: int, state: dict, **changes) -> dict:
    scan = _SCAN.get()
    if scan is not None:
        return scan.save(account_id, state, **changes)
    fields = {key: value for key, value in state.items() if key in {
        "stage", "remote_account_ids", "source_generation", "run_id", "task_id", "next_attempt_at",
        "last_code", "attempt_count", "last_sync_generation", "last_sync_at", "manual_requested",
    }}
    fields.update(changes)
    return repair_store.save_repair(backend, account_id, **fields)


def _reason(summary: dict, code: str) -> None:
    summary["reasons"][code] = summary["reasons"].get(code, 0) + 1


def _cool(backend: str, account_id: int, state: dict, code: str, *, stage="cooldown") -> dict:
    return _save(backend, account_id, state, stage=stage, last_code=code,
                 manual_requested=False, next_attempt_at=_now() + _cooldown())


def _queue_sync(backend: str, account_id: int, state: dict, filename: str, generation: str, summary: dict) -> None:
    targets = list(state.get("remote_account_ids") or [])
    newly_queued = state.get("stage") != "sync_wait" or state.get("source_generation") != generation
    # 先持久化阶段。即使排队完成后进程退出，下轮也只会幂等补传。
    state = _save(backend, account_id, state, stage="sync_wait", source_generation=generation, last_code="sync_pending")
    items = []
    scan = _SCAN.get()
    if not newly_queued and scan is None:
        items = [row for row in repair_store.list_jobs(filename=filename, backend=backend)
                 if row.get("generation") == generation and row.get("remote_account_id") in targets]
    if scan is not None:
        result = scan.queue_sync(account_id, state, filename, generation)
        items = result.get("items") or []
    elif {row.get("remote_account_id") for row in items} == set(targets):
        # 已经排队的目标由补传生产者继续投递；查询状态不能重新启用失败重试。
        result = {"accepted": True, "items": items}
    else:
        result = jobs.queue_sync(filename, remote_account_ids=targets, trigger=_TASK, expected_backend=backend)
        items = result.get("items") or []
    complete = bool(items) and all(str(item.get("status") or "").lower() in _SUCCESS for item in items)
    if complete:
        _save(backend, account_id, state, stage="idle", last_sync_generation=generation,
              last_sync_at=_now(), next_attempt_at=_now() + _cooldown(), last_code="sync_complete", manual_requested=False)
    elif any(item.get("status") in {"cancelled", "blocked_archived", "blocked_missing_credential", "blocked_credential_identity"}
             or (not _enabled() and item.get("status") == "pending" and item.get("error_code") and not item.get("dispatch_requested"))
             for item in items):
        code = "sub2api_sync_cancelled" if any(item.get("status") == "cancelled" for item in items) else "sync_requires_manual_review"
        _cool(backend, account_id, state, code, stage="waiting_manual")
    if result.get("accepted") and newly_queued:
        summary["sync_queued"] += 1
    elif not result.get("accepted"):
        _reason(summary, "sync_queue_failed")


def _start_reauth(backend: str, account: dict, state: dict, generation: str, summary: dict) -> None:
    account_id = int(account["id"])
    try:
        ready = _automatic_login_ready(account)
    except Exception:
        ready = False
    if not ready:
        _cool(backend, account_id, state, "automatic_login_material_missing")
        _reason(summary, "automatic_login_material_missing")
        return
    scan = _SCAN.get()
    if scan is not None:
        scan.start_reauth(account, state, generation)
        return
    state = _save(backend, account_id, state, stage="reauth_submitting", source_generation=generation,
                  run_id=None, task_id=None, last_code="reauth_submitting", next_attempt_at=_now() + _cooldown())
    result = operation_service.enqueue_oauth(account_id, trigger=_TASK,
                                             remote_account_ids=state["remote_account_ids"], backend_identity=backend)
    if result.get("accepted") or result.get("busy"):
        _save(backend, account_id, state, stage="reauth_wait", run_id=result.get("run_id"), task_id=result.get("task_id"), last_code="reauth_pending")
        summary["reauth_queued"] += int(bool(result.get("accepted")))
    else:
        _cool(backend, account_id, state, "reauth_queue_failed")
        _reason(summary, "reauth_queue_failed")


def _run_failure_code(run: dict, row: dict) -> str:
    result = _object(run.get("result_summary"))
    text = " ".join(str(value or "") for value in (
        result.get("error_code"), result.get("code"), result.get("error"), result.get("reason"), row.get("oauth_refresh_error"),
    ))
    if "reauth_required" in text or token_refresh_service.refresh_error_requires_reauth(text):
        return "reauth_required"
    if any(word in text for word in ("request_unknown", "needs_reconciliation", "request_pending")):
        return "needs_reconciliation"
    return "repair_failed"


def _process(backend: str, account: dict, rows: list[dict], remote: list[dict], summary: dict) -> None:
    account_id = int(account["id"])
    scan = _SCAN.get()
    state = (scan.states.get(account_id) if scan is not None else repair_store.get_repair(backend, account_id)) or {}
    stage = str(state.get("stage") or "")
    scoped_scan = bool(summary.get("group_ids"))
    if stage not in _CONTINUATION_STAGES and not remote:
        return
    previous_targets = set(state.get("remote_account_ids") or [])
    current_targets = {int(row["id"]) for row in remote if str(row.get("id") or "").isdigit() and int(row["id"]) > 0}
    # 已提交修复保留原目标；新的分组巡检只使用本轮范围内的远端账号。
    targets = sorted(current_targets if scoped_scan and stage not in _CONTINUATION_STAGES else previous_targets | current_targets)
    changes = {"remote_account_ids": targets}
    if set(targets) - previous_targets:
        # 同邮箱新增远端账号也需要同步；已成功的旧目标由补传队列幂等保留。
        changes["last_sync_generation"] = ""
    state = _save(backend, account_id, state, **changes)
    def skip(code):
        if stage in _CONTINUATION_STAGES and code in {
            "remote_account_id_missing", "account_deactivated", "codex_credential_archived", "local_credential_missing",
        }:
            _cool(backend, account_id, state, code, stage="waiting_manual")
        elif stage not in _CONTINUATION_STAGES and state.get("manual_requested"):
            _save(backend, account_id, state, manual_requested=False, last_code=code)
        _reason(summary, code)
    if not targets:
        skip("remote_account_id_missing")
        return
    if db.account_is_deactivated(account):
        skip("account_deactivated")
        return
    credentials = [row for row in rows if str(row.get("email") or "").strip().lower() == str(account.get("email") or "").strip().lower()]
    available = [row for row in credentials if not row.get("archived")]
    if not available:
        skip("codex_credential_archived" if credentials else "local_credential_missing")
        return
    row = available[0]
    if str(row.get("oauth_account_status") or "").lower() == "deactivated":
        skip("account_deactivated")
        return
    filename = str(row.get("filename") or "")
    try:
        content = (_object((scan.by_filename.get(filename) or {}).get("content")) if scan is not None
                   else _object(db.read_codex_credential(filename)[0]))
        if not content or (content.get("email") and str(content["email"]).lower() != str(account["email"]).lower()):
            raise ValueError("credential_identity_mismatch")
        generation = jobs.credential_generation(content)
    except Exception:
        skip("local_credential_unreadable")
        return
    source = str(state.get("source_generation") or "")
    run_id = int(state.get("run_id") or 0)
    run = ((scan.runs.get(run_id) if scan is not None else operation_runtime_store.get_run(run_id))
           if run_id else None)
    run_status = str((run or {}).get("status") or "").lower()
    sync_receipt = _object(_object((run or {}).get("result_summary")).get("sub2api_sync"))
    stopped_code = str(state.get("last_code") or "")
    if str(sync_receipt.get("status") or "").lower() == "cancelled" or stopped_code == "sub2api_sync_cancelled":
        stopped_code = "sub2api_sync_cancelled"
    elif run_status in {"cancelled", "canceled", "cancelling", "stopping", "stopped", "terminated"} or (run or {}).get("cancel_requested_at") or stopped_code == "repair_cancelled":
        stopped_code = "repair_cancelled"
    else:
        stopped_code = ""
    if stopped_code:
        # 用户停止请求优先于凭据代际变化及新一轮异常扫描。
        _save(backend, account_id, state, stage="waiting_manual", source_generation=generation,
              manual_requested=False, last_code=stopped_code)
        _reason(summary, stopped_code)
        return
    if stage in _WAIT_STAGES:
        if source and source != generation:
            _queue_sync(backend, account_id, state, filename, generation, summary)
            return
        if not run:
            active = (scan.active.get(account_id) if scan is not None
                      else operation_runtime_store.active_run_for_account(account_id))
            if active:
                _save(backend, account_id, state, stage=stage.replace("submitting", "wait"), run_id=active.get("id"), task_id=active.get("task_id"))
            else:
                _cool(backend, account_id, state, "repair_submission_unconfirmed", stage="waiting_manual")
            _reason(summary, "repair_in_progress")
            return
        if run_status in _ACTIVE:
            _reason(summary, "repair_in_progress")
            return
        if run_status in _SUCCESS:
            _queue_sync(backend, account_id, state, filename, generation, summary)
            return
        code = _run_failure_code(run, row)
        if stage.startswith("refresh") and code == "reauth_required":
            _start_reauth(backend, account, state, generation, summary)
        else:
            _cool(backend, account_id, state, code, stage="waiting_manual")
            _reason(summary, code)
        return
    if stage == "sync_wait":
        _queue_sync(backend, account_id, state, filename, generation, summary)
        return
    if (scan.active.get(account_id) if scan is not None else operation_runtime_store.active_run_for_account(account_id)):
        _reason(summary, "account_busy")
        return
    if float(state.get("next_attempt_at") or 0) > _now():
        _reason(summary, "cooldown")
        return
    if not remote:
        return
    codes = {_remote_error(item) for item in remote}
    if "remote_account_deactivated" in codes:
        _cool(backend, account_id, state, "remote_account_deactivated")
        _reason(summary, "remote_account_deactivated")
        return
    _start_reauth(backend, account, state, generation, summary)


def register_actions() -> None:
    task_gateway.register_operation_actions(
        "sub2api_scan",
        retry_handler=task_gateway.default_operation_retry,
        cancel_handler=task_gateway.default_operation_cancel,
        terminate_handler=task_gateway.default_operation_terminate,
    )


def register_handler() -> None:
    """启动时恢复已排队扫描，注册本身不读取远端。"""
    task_gateway.register_operation_handler("sub2api_scan", _handle_scan, config_allowlist=())


def _handle_scan(context):
    context.checkpoint()
    data = context.run.get("data") or {}
    result = _run_once(force=bool(data.get("force")), continuation_only=bool(data.get("continuation_only")))
    reasons = result.get("reasons") or {}
    if any(reasons.get(code) for code in ("backend_not_configured", "local_state_unavailable", "remote_scan_failed")):
        return task_gateway.OperationResult.failed("Sub2API 异常扫描未完成", result)
    message = "Sub2API 待续修复已推进" if result.get("continuation_only") else "Sub2API 异常扫描完成，修复任务分别入队"
    return task_gateway.OperationResult.success(result, message=message)


def run_once(*, force: bool = False, continuation_only: bool = False) -> dict:
    """手动与定时扫描统一持久入队，子任务等待不占用扫描许可。"""
    register_handler()
    result = task_gateway.submit_durable_operation(
        task_type="sub2api_scan", account_id=None, email="",
        trigger="manual" if force else "scheduled_continuation" if continuation_only else "scheduled",
        source_id=f"sub2api-scan:{uuid.uuid4().hex}", data={"force": bool(force), "continuation_only": bool(continuation_only)},
        resource_family="sub2api_scan",
    )
    return {"ok": bool(result.get("accepted")), **result}


def _run_once(*, force: bool = False, continuation_only: bool = False) -> dict:
    """先补传，再归并远端异常并推进持久阶段；返回不含身份或凭据的计数。"""
    enabled = _enabled()
    continuation_only = bool(continuation_only or (not enabled and not force))
    summary = {"enabled": enabled, "continuation_only": continuation_only, "group_ids": [], "remote_errors": 0, "accounts": 0, "processed": 0,
               "refresh_queued": 0, "reauth_queued": 0, "sync_queued": 0, "reasons": {}}
    try:
        summary["group_ids"] = client.configured_monitor_group_ids()
    except client.Sub2ApiSyncError:
        _reason(summary, "remote_scan_failed")
        return summary
    try:
        backend = client.configured_backend_identity()
        if not backend:
            _reason(summary, "backend_not_configured")
            return summary
        collection_store.initialize()
        jobs.register_handler()
        try:
            collection_store.enqueue_due_many(backend, include_retries=jobs._enabled())
            task_gateway.notify_dispatch()
        except Exception:
            _reason(summary, "sync_retry_scan_failed")
        repairs = _continuation_repairs(backend) if continuation_only else repair_store.list_repairs(backend, active_only=True)
        if continuation_only:
            if not repairs:
                return summary
    except Exception:
        _reason(summary, "local_state_unavailable")
        return summary
    remote = []
    if not continuation_only:
        try:
            remote = client.list_configured_error_accounts(
                group_ids=summary["group_ids"], expected_backend=backend)
        except Exception:
            _reason(summary, "remote_scan_failed")
    summary["remote_errors"] = len(remote)
    by_account: dict[int, tuple[dict, list[dict]]] = {}
    try:
        selected = collection_store.accounts(
            [int(row.get("account_id") or 0) for row in repairs],
            {_remote_email(row) for row in remote if _remote_email(row)},
        )
    except Exception:
        _reason(summary, "local_state_unavailable")
        return summary
    by_id = {row["id"]: row for row in selected}
    by_email = {str(row.get("email") or "").lower(): row for row in selected}
    for item in remote:
        email = _remote_email(item)
        if not email:
            _reason(summary, "remote_email_missing")
            continue
        account = by_email.get(email)
        if not account:
            _reason(summary, "local_account_missing")
            continue
        account_id = int(account.get("id") or 0)
        if not account_id:
            _reason(summary, "local_account_missing")
            continue
        by_account.setdefault(account_id, (account, []))[1].append(item)
    for repair in repairs:
        account_id = int(repair.get("account_id") or 0)
        if account_id and account_id not in by_account:
            account = by_id.get(account_id)
            if account:
                by_account[account_id] = (account, [])
    summary["accounts"] = len(by_account)
    limit = max(1, int(getattr(_cfg, "SUB2API_MONITOR_MAX_PER_CYCLE", 20) or 20))
    # 待续阶段优先，不让长异常列表挤占已完成授权后的补传。
    pending_ids = {int(item.get("account_id") or 0) for item in repairs}
    try:
        candidate_ids = set(by_account) | pending_ids
        with collection_store.repair_locks(backend, candidate_ids) as acquired:
            facts = collection_store.snapshot(backend, acquired)
            scan = monitor_collections.Scan(backend, by_id, facts)
            token = _SCAN.set(scan)
            try:
                for repair in repairs:
                    account_id = int(repair.get("account_id") or 0)
                    if account_id not in acquired or account_id in by_id:
                        continue
                    state = scan.states.get(account_id) or repair
                    if state.get("stage") in _CONTINUATION_STAGES:
                        _cool(backend, account_id, state, "local_account_missing", stage="waiting_manual")
                        _reason(summary, "local_account_missing")
                    elif state.get("manual_requested"):
                        _save(backend, account_id, state, manual_requested=False, last_code="local_account_missing")
                for account_id, (account, items) in sorted(by_account.items(), key=lambda pair: (pair[0] not in pending_ids, pair[0])):
                    if summary["refresh_queued"] + len(scan.oauth) + summary["sync_queued"] >= limit:
                        _reason(summary, "cycle_limit")
                        break
                    if account_id not in acquired:
                        _reason(summary, "account_busy")
                        continue
                    if force:
                        _save(backend, account_id, scan.states.get(account_id) or {}, manual_requested=True)
                    before = dict(scan.states.get(account_id) or {})
                    try:
                        _process(backend, account, scan.credentials, items, summary)
                    except Exception:
                        # 单目标决策错误不把半份阶段留在整批提交中。
                        scan.states[account_id] = before
                        scan.changed.pop(account_id, None)
                        _reason(summary, "repair_processing_failed")
                        continue
                    if force:
                        current = scan.states.get(account_id) or {}
                        if current.get("manual_requested") and current.get("stage") not in _CONTINUATION_STAGES:
                            _save(backend, account_id, current, manual_requested=False)
                    summary["processed"] += 1
                scan.flush(summary, include_retries=jobs._enabled(), now=_now(), cooldown=_cooldown())
            finally:
                _SCAN.reset(token)
    except Exception:
        # 集合事实和子任务共享事务，存储故障不能返回已受理数量。
        summary.update(reauth_queued=0, sync_queued=0)
        _reason(summary, "repair_processing_failed")
    return summary


def status() -> dict:
    """可公开的安全状态；修复记录只聚合阶段数，不返回账号信息。"""
    states: dict[str, int] = {}
    try:
        backend = client.configured_backend_identity()
        if backend:
            states = dict(Counter(str(item.get("stage") or "idle") for item in repair_store.list_repairs(backend, active_only=True)))
    except Exception:
        pass
    return {**scheduler_status(),
            "group_ids": client.configured_monitor_group_ids(),
            "interval_seconds": _interval(), "cooldown_seconds": _cooldown(),
            "max_per_cycle": max(1, int(getattr(_cfg, "SUB2API_MONITOR_MAX_PER_CYCLE", 20) or 20)),
            "repair_stages": states, **scheduler_state.describe(_TASK, _interval())}


def _scheduler_loop() -> None:
    scheduler_state.run_periodic(
        task=_TASK, label="Sub2API 异常巡检", work=run_once,
        enabled=_periodic_enabled, interval_seconds=_periodic_interval,
        stop=_SCHEDULER.stop_event, lifecycle=_SCHEDULER,
    )


def start_periodic_monitor() -> bool:
    """启动一个可观测的周期巡检，保留运行时准入边界。"""
    try:
        started = _SCHEDULER.start(_scheduler_loop, before_start=register_handler)
    except Exception:
        logger.exception("周期巡检启动失败，可稍后重试")
        return False

    return started


def stop_periodic_monitor(timeout: float = 2.0) -> bool:
    return _SCHEDULER.stop(timeout)


def scheduler_status() -> dict:
    return _SCHEDULER.status(enabled=_enabled())
