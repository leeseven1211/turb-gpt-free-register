# -*- coding: utf-8 -*-
"""Sub2API 异常账号巡检；只编排现有刷新、OAuth 和定向同步入口。"""
from __future__ import annotations

import importlib
import json
import re
import threading
import time
from collections import Counter
from typing import Any

from config import email as email_config
from config import sub2api as _cfg
from core import db
from core.accounts.credentials import get_account_login_credentials
from core.codex import operation_service, token_refresh_service
from core.integrations.sub2api import client, jobs
from core.runtime import scheduler_state
from core.storage import sub2api as repair_store
from core.storage.operations import runtime as operation_runtime_store

_TASK = "sub2api_monitor"
_THREAD_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_ACTIVE = {"queued", "running", "cancelling", "settling", "waiting", "retrying", "stopping"}
_SUCCESS = {"success", "succeeded", "completed"}
_WAIT_STAGES = {"refresh_wait", "reauth_wait", "refresh_submitting", "reauth_submitting"}
_CONTINUATION_STAGES = _WAIT_STAGES | {"sync_wait"}


def _now() -> float:
    return time.time()


def _enabled() -> bool:
    return bool(getattr(_cfg, "SUB2API_MONITOR_ENABLED", False))


def _periodic_enabled() -> bool:
    """关闭自动巡检后，只接续曾明确手动请求的未完成修复。"""
    if _enabled():
        return True
    try:
        backend = client.configured_backend_identity()
        return any(row.get("manual_requested") and row.get("stage") in _CONTINUATION_STAGES
                   for row in repair_store.list_repairs(backend, active_only=True))
    except Exception:
        return False


def _periodic_interval() -> int:
    return _interval() if _enabled() else 15


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
    if re.search(r"\b(?:429|5\d\d)\b|rate.?limit|too many requests|timeout|timed out|connection|network", text):
        return "remote_transient_error"
    if re.search(r"account[_ -]deactivated|account[_ -]disabled|user[_ -]deactivated", text):
        return "remote_account_deactivated"
    if re.search(r"\b401\b|unauthori[sz]ed|invalid_grant|invalid[_ -](?:access[_ -])?token|token.+(?:expired|revoked|invalidated)|(?:expired|revoked).+token", text):
        return "remote_oauth_error"
    return "unrecognized_remote_error"


def _automatic_login_ready(account: dict) -> bool:
    """只读检查已保存的登录/收件资料；不申请邮箱或改动认证设置。"""
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
    if not newly_queued:
        items = [row for row in repair_store.list_jobs(filename=filename, backend=backend)
                 if row.get("generation") == generation and row.get("remote_account_id") in targets]
    if {row.get("remote_account_id") for row in items} == set(targets):
        # 已经排队的目标由补传生产者继续投递；查询状态不能重新启用失败重试。
        result = {"accepted": True, "items": items}
    else:
        result = jobs.queue_sync(filename, remote_account_ids=targets, trigger=_TASK, expected_backend=backend)
        items = result.get("items") or []
    complete = bool(items) and all(str(item.get("status") or "").lower() in _SUCCESS for item in items)
    if complete:
        _save(backend, account_id, state, stage="idle", last_sync_generation=generation,
              last_sync_at=_now(), next_attempt_at=_now() + _cooldown(), last_code="sync_complete", manual_requested=False)
    elif not _enabled() and any(item.get("status") in {"cancelled", "blocked_archived", "blocked_missing_credential"}
                               or (item.get("status") == "pending" and item.get("error_code") and not item.get("dispatch_requested"))
                               for item in items):
        _cool(backend, account_id, state, "sync_requires_manual_review", stage="waiting_manual")
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
    state = repair_store.get_repair(backend, account_id) or {}
    previous_targets = set(state.get("remote_account_ids") or [])
    targets = sorted(previous_targets | {int(row["id"]) for row in remote if str(row.get("id") or "").isdigit() and int(row["id"]) > 0})
    changes = {"remote_account_ids": targets}
    if set(targets) - previous_targets:
        # 同邮箱新增远端账号也需要同步；已成功的旧目标由补传队列幂等保留。
        changes["last_sync_generation"] = ""
    state = _save(backend, account_id, state, **changes)
    def skip(code):
        if state.get("manual_requested"):
            _save(backend, account_id, state, manual_requested=False, last_code=code)
        _reason(summary, code)
    if not targets:
        skip("remote_account_id_missing")
        return
    if db.account_is_deactivated(account):
        skip("account_deactivated")
        return
    if account.get("archived"):
        skip("account_archived")
        return
    available = [row for row in rows if str(row.get("email") or "").strip().lower() == str(account.get("email") or "").strip().lower() and not row.get("archived")]
    if not available:
        skip("local_credential_missing")
        return
    row = available[0]
    if str(row.get("oauth_account_status") or "").lower() == "deactivated":
        skip("account_deactivated")
        return
    filename = str(row.get("filename") or "")
    try:
        content = _object(db.read_codex_credential(filename)[0])
        if not content or (content.get("email") and str(content["email"]).lower() != str(account["email"]).lower()):
            raise ValueError("credential_identity_mismatch")
        generation = jobs.credential_generation(content)
    except Exception:
        skip("local_credential_unreadable")
        return
    stage = str(state.get("stage") or "")
    source = str(state.get("source_generation") or "")
    if stage in _WAIT_STAGES or stage == "waiting_manual":
        run_id = int(state.get("run_id") or 0)
        run = operation_runtime_store.get_run(run_id) if run_id else None
        sync_receipt = _object(_object((run or {}).get("result_summary")).get("sub2api_sync"))
        if str(sync_receipt.get("status") or "").lower() == "cancelled":
            # OAuth 已成功也可能被明确停止后续同步；取消回执优先于凭据代际变化。
            _save(backend, account_id, state, stage="waiting_manual", source_generation=generation,
                  manual_requested=False, last_code="sub2api_sync_cancelled")
            _reason(summary, "sub2api_sync_cancelled")
            return
        if source and source != generation:
            _queue_sync(backend, account_id, state, filename, generation, summary)
            return
        if stage == "waiting_manual":
            _reason(summary, str(state.get("last_code") or "repair_requires_manual_review"))
            return
        if not run:
            active = operation_runtime_store.active_run_for_account(account_id)
            if active:
                _save(backend, account_id, state, stage=stage.replace("submitting", "wait"), run_id=active.get("id"), task_id=active.get("task_id"))
            else:
                _cool(backend, account_id, state, "repair_submission_unconfirmed", stage="waiting_manual")
            _reason(summary, "repair_in_progress")
            return
        if str(run.get("status") or "").lower() in _ACTIVE:
            _reason(summary, "repair_in_progress")
            return
        if str(run.get("status") or "").lower() in _SUCCESS:
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
    if operation_runtime_store.active_run_for_account(account_id):
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
    if "remote_oauth_error" not in codes and "remote_transient_error" in codes:
        _cool(backend, account_id, state, "remote_transient_error")
        _reason(summary, "remote_transient_error")
        return
    if "remote_oauth_error" not in codes:
        _reason(summary, "unrecognized_remote_error")
        if state.get("last_sync_generation") != generation:
            _queue_sync(backend, account_id, state, filename, generation, summary)
        else:
            _cool(backend, account_id, state, "unrecognized_remote_error")
        return
    # 已有不同于远端的本地新凭据时先补传，上传失败不触发重复授权。
    remote_stale = any(_object(item.get("credentials")).get("access_token") and
                       _object(item.get("credentials"))["access_token"] != content.get("access_token") for item in remote)
    if remote_stale and state.get("last_sync_generation") != generation:
        _queue_sync(backend, account_id, state, filename, generation, summary)
        return
    state = _save(backend, account_id, state, stage="refresh_submitting", source_generation=generation,
                  run_id=None, task_id=None, last_code="refresh_submitting", next_attempt_at=_now() + _cooldown(),
                  attempt_count=int(state.get("attempt_count") or 0) + 1)
    refreshed = token_refresh_service.enqueue_refresh(filename, trigger=_TASK)
    if refreshed.get("accepted") or refreshed.get("busy"):
        _save(backend, account_id, state, stage="refresh_wait", run_id=refreshed.get("run_id"), task_id=refreshed.get("task_id"), last_code="refresh_pending")
        summary["refresh_queued"] += int(bool(refreshed.get("accepted")))
    elif refreshed.get("error_code") == "reauth_required":
        _start_reauth(backend, account, state, generation, summary)
    elif refreshed.get("error_code") in {"needs_reconciliation", "request_unknown", "request_pending"}:
        _cool(backend, account_id, state, "needs_reconciliation", stage="waiting_manual")
        _reason(summary, "needs_reconciliation")
    else:
        _cool(backend, account_id, state, "refresh_queue_failed")
        _reason(summary, "refresh_queue_failed")


def run_once(*, force: bool = False) -> dict:
    """先补传，再归并远端异常并推进持久阶段；返回不含身份或凭据的计数。"""
    summary = {"enabled": _enabled(), "remote_errors": 0, "accounts": 0, "processed": 0,
               "refresh_queued": 0, "reauth_queued": 0, "sync_queued": 0, "reasons": {}}
    try:
        jobs.enqueue_due()
    except Exception:
        _reason(summary, "sync_retry_scan_failed")
    continuation_only = not summary["enabled"] and not force
    try:
        backend = client.configured_backend_identity()
        if not backend:
            _reason(summary, "backend_not_configured")
            return summary
        rows = db.list_codex_accounts(archived="all")
        repairs = repair_store.list_repairs(backend, active_only=True)
        if continuation_only:
            repairs = [row for row in repairs if row.get("manual_requested") and row.get("stage") in _CONTINUATION_STAGES]
            if not repairs:
                return summary
    except Exception:
        _reason(summary, "local_state_unavailable")
        return summary
    remote = []
    if not continuation_only:
        try:
            remote = client.list_configured_error_accounts(
                group_ids=client.configured_upload_options().get("group_ids"), expected_backend=backend)
        except Exception:
            _reason(summary, "remote_scan_failed")
    summary["remote_errors"] = len(remote)
    by_account: dict[int, tuple[dict, list[dict]]] = {}
    for item in remote:
        email = _remote_email(item)
        if not email:
            _reason(summary, "remote_email_missing")
            continue
        account = db.get_account_by_email(email)
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
            account = db.get_account(account_id)
            if account:
                by_account[account_id] = (account, [])
            elif repair.get("manual_requested"):
                _save(backend, account_id, repair, manual_requested=False, last_code="local_account_missing")
    summary["accounts"] = len(by_account)
    limit = max(1, int(getattr(_cfg, "SUB2API_MONITOR_MAX_PER_CYCLE", 20) or 20))
    # 待续阶段优先，不让长异常列表挤占已完成授权后的补传。
    pending_ids = {int(item.get("account_id") or 0) for item in repairs}
    for account_id, (account, items) in sorted(by_account.items(), key=lambda pair: (pair[0] not in pending_ids, pair[0])):
        if summary["refresh_queued"] + summary["reauth_queued"] + summary["sync_queued"] >= limit:
            _reason(summary, "cycle_limit")
            break
        try:
            with repair_store.repair_lock(backend, account_id) as acquired:
                if not acquired:
                    _reason(summary, "account_busy")
                    continue
                if force:
                    _save(backend, account_id, repair_store.get_repair(backend, account_id) or {}, manual_requested=True)
                _process(backend, account, rows, items, summary)
                if force:
                    current = repair_store.get_repair(backend, account_id) or {}
                    if current.get("manual_requested") and current.get("stage") not in _CONTINUATION_STAGES:
                        _save(backend, account_id, current, manual_requested=False)
                summary["processed"] += 1
        except Exception:
            # 不把原始异常写入摘要，第三方异常可能带 Token 或邮箱。
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
    return {"enabled": _enabled(), "running": bool(_THREAD and _THREAD.is_alive()),
            "interval_seconds": _interval(), "cooldown_seconds": _cooldown(),
            "max_per_cycle": max(1, int(getattr(_cfg, "SUB2API_MONITOR_MAX_PER_CYCLE", 20) or 20)),
            "repair_stages": states, **scheduler_state.describe(_TASK, _interval())}


def start_periodic_monitor() -> bool:
    """启动可热加载开关的周期生产者；不在此线程执行远端修复请求。"""
    global _THREAD
    with _THREAD_LOCK:
        if _THREAD and _THREAD.is_alive():
            return False
        _THREAD = threading.Thread(target=scheduler_state.run_periodic, kwargs={
            "task": _TASK, "label": "Sub2API 异常巡检", "work": run_once,
            "enabled": _periodic_enabled, "interval_seconds": _periodic_interval,
        }, name="sub2api-monitor", daemon=True)
        _THREAD.start()
        return True
