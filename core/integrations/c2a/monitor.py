"""巡检 C2A 账号并通过已有批量刷新和定向同步入口修复 AT。"""
from __future__ import annotations

import hashlib
import logging
import math
import re
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from config import c2a as config
from config.concurrency import policy_values
from core import db
from core.accounts.plans.client import normalize_token, token_claims
from core.bulk_operations import service as bulk_service
from core.integrations.c2a import client, manual_sync
from core.operations import concurrency, task_gateway
from core.runtime import scheduler_state
from core.runtime.periodic import PeriodicThread
from core.storage import c2a as store
from core.storage.operations import bulk

logger = logging.getLogger(__name__)
TASK_TYPE = "c2a_scan"
_TASK = "c2a_monitor"
_SCHEDULER = PeriodicThread("c2a-monitor")
_REFRESH = {"key": "token_refresh", "version": 1}
_REFRESH_FAILURE_LIMIT = 2
_ACTIVE = {"pending_submit", "waiting_account", "queued", "running", "waiting", "cancelling", "settling", "stopping"}
_CANCELLED = {"cancelled", "canceled", "stopped", "terminated"}
_TERMINAL_TARGET_CODES = {
    "c2a_remote_account_missing", "c2a_remote_account_disabled",
    "c2a_remote_account_identity_changed", "c2a_remote_token_conflict",
}
_LOCAL_AT_INVALID = {
    "c2a_local_at_expired", "c2a_local_at_unverified", "c2a_local_at_identity_mismatch", "c2a_remote_at_invalid",
}


def _enabled() -> bool:
    return bool(getattr(config, "C2A_MONITOR_ENABLED", False))


def _interval() -> int:
    return max(30, min(86400, int(getattr(config, "C2A_MONITOR_INTERVAL_SECONDS", 300))))


def _cooldown() -> int:
    return max(30, min(86400, int(getattr(config, "C2A_MONITOR_COOLDOWN_SECONDS", 300))))


def _limit() -> int:
    return max(1, min(5000, int(getattr(config, "C2A_MONITOR_MAX_PER_CYCLE", 500))))


def _code(value, fallback: str) -> str:
    value = str(value or "")
    return value if re.fullmatch(r"[a-z][a-z0-9_.-]{0,95}", value) else fallback


def _note(summary: dict, code: str, *, stage: str = "", error: Exception | None = None) -> None:
    summary["reasons"][code] += 1
    if error:
        error_class = type(error).__name__
        detail = {"code": code, "stage": stage, "error_class": error_class}
        if detail not in summary["diagnostics"]:
            summary["diagnostics"].append(detail)
        logger.warning("C2A 巡检阶段失败：阶段=%s 分类=%s 异常=%s", stage, code, error_class)


def _batch_ref(summary: dict, batch_id: int, round_id: int) -> None:
    summary["batch_refs"][(batch_id, round_id)] = {"batch_id": str(batch_id), "round_id": str(round_id)}


def _timestamp(value) -> float | None:
    try:
        if isinstance(value, bool) or value is None:
            return None
        try:
            stamp = float(value)
        except (ValueError, TypeError):
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            stamp = (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
        if stamp > 10 ** 11:
            stamp /= 1000
        return stamp if math.isfinite(stamp) and stamp > 0 else None
    except (ValueError, OverflowError, OSError):
        return None


def _email(value) -> str:
    email = str(value or "").strip().casefold()
    return email if "@" in email and not any(char.isspace() for char in email) else ""


def _at(account: dict) -> tuple[str, float | None, float | None]:
    """摘要用于比较代际，本地 AT 的身份和期限用现有 JWT 读模型判断。"""
    token = normalize_token(str(account.get("access_token") or ""))
    if not token:
        return "", None, None
    generation = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if len(token.split(".")) != 3 or any(not part for part in token.split(".")):
        return generation, None, None
    try:
        claims = token_claims(token)
        if _email(claims.get("email")) == _email(account.get("email")):
            return generation, _timestamp(claims["payload"].get("iat")), _timestamp(claims.get("exp"))
    except (AttributeError, TypeError, ValueError, OverflowError, OSError):
        pass
    return generation, None, None


def _remote_disposition(row: dict, now: float) -> tuple[bool, str | None]:
    """按 C2A 状态区分凭据故障和不可通过重登录处理的状态。"""
    reason = str(row.get("status_reason_code") or "").strip().lower()
    category = str(row.get("status_category") or "").strip().lower()
    backend_status = str(row.get("backend_status") or "").strip().lower()
    token_status = str(row.get("access_token_status") or "").strip().lower()
    availability = str(row.get("credential_availability") or "").strip().lower()
    facts = {reason, category, backend_status}
    expiry = _timestamp(row.get("access_token_expires_at"))
    credential_issue = (
        token_status in {"invalid", "missing", "expired", "revoked", "unavailable"}
        or availability in {"invalid", "missing", "unavailable", "expired"}
        or bool(facts & {"auth_invalid", "at_invalid", "token_expired", "invalid_token", "credentials_unavailable",
                         "access_token_expired", "access_token_invalid", "access_token_missing", "unauthorized"})
        or (expiry is not None and expiry <= now)
    )
    if facts & {"account_deactivated", "account_deleted", "account_suspended", "account_banned",
                "user_deactivated", "deactivated", "suspended", "banned"}:
        return False, "c2a_remote_account_deactivated"
    if row.get("enabled") is False or facts & {"disabled", "manual_disabled", "account_disabled", "user_disabled", "禁用"}:
        return False, "c2a_remote_account_disabled"
    if facts & {"image_quota_exhausted", "quota_exhausted", "quota_exceeded", "insufficient_quota",
                "quota_limited", "usage_limit_reached"}:
        return False, "c2a_remote_quota_exhausted"
    if facts & {"rate_limited", "rate_limit", "too_many_requests", "rate_limit_exceeded", "limited", "限流"}:
        return False, "c2a_remote_rate_limited"
    if credential_issue and row.get("enabled") is True:
        return True, None
    if facts & {"remote_check_failed", "service_unavailable", "network_error", "server_error", "timeout",
                "temporary_unavailable", "sync_failed"}:
        return False, "c2a_remote_temporarily_unavailable"
    if reason == "verification_pending":
        return False, "c2a_remote_verification_pending"
    if credential_issue or facts & {"abnormal", "error", "failed", "invalid", "unavailable", "异常"}:
        return False, "c2a_remote_diagnostic_missing"
    return False, None


def _newer_at(remote: dict, issued: float | None, expires: float | None, now: float) -> bool:
    if expires is None or expires <= now:
        return False
    if remote.get("access_token_status") == "missing":
        return True
    remote_issued = _timestamp(remote.get("access_token_issued_at"))
    if issued is not None and remote_issued is not None:
        return issued > remote_issued
    remote_expires = _timestamp(remote.get("access_token_expires_at"))
    return remote_expires is not None and expires > remote_expires


def _local_skip(account: dict | None, expected_email: str) -> str | None:
    if account is None:
        return "c2a_local_account_missing"
    if _email(account.get("email")) != expected_email:
        return "c2a_local_identity_changed"
    if account.get("archived"):
        return "c2a_local_account_archived"
    if account.get("deactivated") or db.account_is_deactivated(account):
        return "c2a_account_deactivated"
    if not str(account.get("access_token") or "").strip():
        return "c2a_local_at_missing"
    return None


def _cool(row: dict, reason: str, now: float, *, stage="refresh_retry") -> None:
    row.update(stage=stage, last_code=reason, next_attempt_at=now + _cooldown())


def _refresh_failed(row: dict, reason: str, now: float, *, count_failure: bool) -> None:
    if count_failure:
        row["refresh_failure_count"] = int(row.get("refresh_failure_count") or 0) + 1
    exhausted = int(row.get("refresh_failure_count") or 0) >= _REFRESH_FAILURE_LIMIT
    _cool(row, reason, now, stage="refresh_exhausted" if exhausted else "refresh_retry")


def _refresh_workers() -> int:
    limits = policy_values()
    return min(128, limits["GLOBAL_TASK_WORKERS"], limits["ACCOUNT_TOKEN_REFRESH_WORKERS"])


def _reserve_refresh(backend: str, rows: list[dict]) -> None:
    key = f"c2a-refresh:{uuid.uuid4().hex}"
    workers = _refresh_workers()
    for row in rows:
        row.update(stage="refresh_pending", refresh_key=key, refresh_workers=workers, selection_id=None,
                   batch_id=None, round_id=None, refresh_task_id=None, refresh_run_id=None,
                   next_attempt_at=0, last_code=None, attempt_count=int(row.get("attempt_count") or 0) + 1)
    store.save_repairs(backend, rows)


def _submit_refresh(backend: str, rows: list[dict], summary: dict, now: float, checkpoint, scheduled: set[int]) -> None:
    first = rows[0]
    key = first["refresh_key"]
    checkpoint()
    try:
        if first.get("selection_id"):
            selection = bulk.get_selection(first["selection_id"], limit=1)
        else:
            scheduled.update(row["account_id"] for row in rows)
            selection = bulk_service.create_selection(
                {"operation": _REFRESH, "source": {"kind": "ids", "entity": "account",
                 "ids": sorted(row["account_id"] for row in rows)}}, f"{key}:selection",
            )
    except Exception as exc:
        code = _code(getattr(exc, "code", None), "c2a_refresh_selection_failed")
        _note(summary, code, stage="refresh_selection", error=exc)
        if isinstance(exc, bulk.BulkError) and exc.status < 500:
            for row in rows:
                _cool(row, code, now)
            store.save_repairs(backend, rows)
        return

    state = selection.get("status")
    for row in rows:
        row["selection_id"] = selection["id"]
    if state in {"failed", "expired"}:
        code = _code(selection.get("error_code"), "c2a_refresh_selection_failed")
        for row in rows:
            _cool(row, code, now)
            _note(summary, code)
        store.save_repairs(backend, rows)
        return

    checkpoint()
    try:
        if state == "consumed" and selection.get("consumed_by_batch_id"):
            batch = bulk.get_batch(selection["consumed_by_batch_id"])
        elif state == "ready":
            scheduled.update(row["account_id"] for row in rows)
            batch = bulk_service.create_batch({
                "operation": _REFRESH,
                "selection_id": selection["id"], "selection_revision": selection["selection_revision"],
                "expected_config_revision": selection["config_revision"],
                "execution": {"max_concurrency": first["refresh_workers"]}, "name": "C2A 异常巡检刷新 AT",
            }, f"{key}:batch")
        else:
            store.save_repairs(backend, rows)
            return
    except Exception as exc:
        detail = getattr(exc, "detail", {}) or {}
        code = _code(detail.get("reason_code") or getattr(exc, "code", None), "c2a_refresh_batch_failed")
        _note(summary, code, stage="refresh_batch", error=exc)
        if isinstance(exc, bulk.BulkError) and exc.status < 500 and exc.code != "selection_not_ready":
            for row in rows:
                _cool(row, code, now)
        store.save_repairs(backend, rows)
        return
    for row in rows:
        row.update(stage="refresh_wait", batch_id=batch["id"], round_id=batch["initial_round_id"])
    store.save_repairs(backend, rows)
    _batch_ref(summary, batch["id"], batch["initial_round_id"])
    summary["refresh_queued"] += len(rows)


def _batch_results(batch_id: int, account_ids: set[int], checkpoint) -> dict[int, dict]:
    cursor = 0
    targets = {}
    while True:
        checkpoint()
        page = bulk.list_targets(batch_id, limit=100, after_ordinal=cursor)
        targets.update({item["account_id"]: item for item in page["items"] if item["account_id"] in account_ids})
        cursor = page["page"]["next_cursor"]
        if cursor is None or account_ids <= targets.keys():
            return targets


def _after_refresh(
    row: dict, target: dict | None, account: dict | None, cancelled: set[int], summary: dict, now: float,
) -> None:
    if target is None:
        if row["stage"] == "refresh_retry" and row["last_code"] == "c2a_refresh_result_missing":
            return
        _cool(row, "c2a_refresh_result_missing", now)
        _note(summary, "c2a_refresh_result_missing")
        return
    state = target["outcome"]
    run_id = target.get("run_id")
    round_id = target.get("round_id") or row["round_id"]
    if state not in _ACTIVE:
        if run_id and row.get("refresh_observed_run_id") == run_id:
            return
        if (not run_id and row["stage"] == "refresh_retry"
                and row["round_id"] == round_id and not row.get("refresh_run_id")):
            return
    row.update(round_id=round_id, refresh_task_id=target.get("task_id"), refresh_run_id=run_id)
    if state in _ACTIVE:
        row["stage"] = "refresh_wait"
        return
    if run_id:
        row["refresh_observed_run_id"] = run_id
    if state in _CANCELLED or run_id in cancelled:
        row.update(stage="cancelled", last_code="c2a_repair_cancelled")
        _note(summary, "c2a_repair_cancelled")
        return
    if state != "success" or not target.get("run_id"):
        reason = _code(target.get("reason_code"), "c2a_refresh_result_missing")
        _refresh_failed(row, reason, now, count_failure=bool(run_id) and state != "not_executed")
        _note(summary, reason)
        return
    reason = _local_skip(account, row["email"])
    if reason:
        _cool(row, reason, now, stage="done")
        _note(summary, reason)
        return
    generation, _, expiry = _at(account)
    if generation == row["source_generation"] or expiry is None or expiry <= now:
        reason = "c2a_refresh_token_unchanged" if generation == row["source_generation"] else "c2a_local_at_unverified"
        _refresh_failed(row, reason, now, count_failure=True)
        _note(summary, reason)
        return
    row.update(stage="sync_wait", source_generation=generation, next_attempt_at=0, last_code=None,
               refresh_failure_count=0)


def _advance_refresh(
    backend: str, repairs: list[dict], accounts: dict, summary: dict, now: float, checkpoint, limit: int,
) -> set[int]:
    selections = defaultdict(list)
    batches = defaultdict(list)
    for row in repairs:
        if row["stage"] == "refresh_pending":
            selections[row["refresh_key"]].append(row)
        elif row["stage"] in {"refresh_wait", "refresh_retry", "refresh_exhausted"} and row.get("batch_id"):
            batches[row["batch_id"]].append(row)
    scheduled = set()
    for rows in selections.values():
        if scheduled and len(scheduled) + len(rows) > limit:
            _note(summary, "c2a_scan_cycle_limit")
            break
        _submit_refresh(backend, rows, summary, now, checkpoint, scheduled)
    observed = []
    cancelled_ids = set()
    successful = {}
    for batch_id, rows in batches.items():
        try:
            targets = _batch_results(batch_id, {row["account_id"] for row in rows}, checkpoint)
        except (task_gateway.OperationCancelled, task_gateway.OperationLeaseLost):
            raise
        except Exception as exc:
            code = _code(getattr(exc, "code", None), "c2a_refresh_result_missing")
            _note(summary, code, stage="refresh_result", error=exc)
            if isinstance(exc, bulk.BulkError) and exc.status == 404:
                for row in rows:
                    if row["stage"] != "refresh_retry":
                        _cool(row, code, now)
                store.save_repairs(backend, rows)
            continue
        for row in rows:
            target = targets.get(row["account_id"])
            _batch_ref(summary, batch_id, (target or {}).get("round_id") or row["round_id"])
            observed.append((row, target))
            if target and target.get("run_id") and target["outcome"] not in _ACTIVE:
                run_id = target["run_id"]
                cancelled_ids.add(run_id)
                if target["outcome"] == "success":
                    successful[row["account_id"]] = run_id
    cancelled = store.cancelled_refresh_runs(cancelled_ids)
    # AT 的提交可发生在最初的账号读取和刷新回执之间。读到成功后再整批读取账号。
    succeeded = {account_id for account_id, run_id in successful.items() if run_id not in cancelled}
    if succeeded:
        checkpoint()
        for account_id in succeeded:
            accounts.pop(account_id, None)
        accounts.update({account["id"]: account for account in store.account_material(succeeded, [])})
    for row, target in observed:
        _after_refresh(row, target, accounts.get(row["account_id"]), cancelled, summary, now)
    store.save_repairs(backend, (row for row, _ in observed))
    return scheduled


def _settle_target(backend: str, row: dict, remote_id: str, target: dict, runs: dict, summary: dict, now: float) -> bool:
    """返回目标是否仍有活动任务。已观察的终态不再次延长冷却。"""
    if not target.get("task_id"):
        return False
    run = runs.get(target["task_id"])
    if not run or not (
        run["account_id"] == row["account_id"] and _email(run["email_snapshot"]) == row["email"]
        and run["backend"] == backend and run["remote_id"] == remote_id and run["monitor_managed"] is True
    ):
        target.update(task_id=None, run_id=None, next_attempt_at=now + _cooldown(),
                      last_code="c2a_upload_result_missing")
        _note(summary, "c2a_upload_result_missing")
        return False
    run_id, state = run["id"], run["status"]
    if target.get("observed_run_id") == run_id:
        return False
    target["run_id"] = run_id
    if state in _ACTIVE:
        return True
    target["observed_run_id"] = run_id
    result = run.get("result_summary") or {}
    code = _code(result.get("cause_code") or result.get("error_code") or run.get("error_code"),
                 "c2a_upload_request_unknown" if result.get("outcome") == "request_unknown" or state == "attention_required"
                 else "c2a_upload_result_missing")
    if state in _CANCELLED or run.get("cancel_requested_at") or result.get("requested_status") in _CANCELLED:
        target.update(state="cancelled", last_code="c2a_repair_cancelled")
        _note(summary, "c2a_repair_cancelled")
    elif state == "success" and result.get("ok") is True:
        target.update(state="done", last_code=None)
    elif code in _TERMINAL_TARGET_CODES:
        target.update(state="done", last_code=code)
        _note(summary, code)
    else:
        target.update(key=None, next_attempt_at=now + _cooldown(), last_code=code)
        if code in _LOCAL_AT_INVALID:
            _cool(row, code, now)
        _note(summary, code)
    return False


def _advance_uploads(backend: str, repairs: list[dict], accounts: dict, summary: dict, now: float) -> list[tuple]:
    waiting = [row for row in repairs if row["stage"] == "sync_wait"]
    runs = store.upload_runs({
        target["task_id"] for row in waiting for target in row["targets"].values() if target.get("task_id")
    })
    submissions = []
    for row in waiting:
        account = accounts.get(row["account_id"])
        busy = False
        for remote_id, target in row["targets"].items():
            busy = _settle_target(backend, row, remote_id, target, runs, summary, now) or busy
        if busy or row["stage"] != "sync_wait":
            continue
        pending = [(remote_id, target) for remote_id, target in row["targets"].items() if target["state"] == "pending"]
        if not pending:
            cancelled = any(target["state"] == "cancelled" for target in row["targets"].values())
            reason = next((target["last_code"] for target in row["targets"].values() if target.get("last_code")), None)
            _cool(row, "c2a_repair_cancelled" if cancelled else reason or "c2a_sync_complete", now,
                  stage="cancelled" if cancelled else "done")
            continue
        reason = _local_skip(account, row["email"])
        if reason:
            _cool(row, reason, now, stage="done")
            _note(summary, reason)
            continue
        generation, _, expiry = _at(account)
        if expiry is None or expiry <= now:
            _cool(row, "c2a_local_at_expired" if expiry else "c2a_local_at_unverified", now)
            _note(summary, row["last_code"])
            continue
        row["source_generation"] = generation
        for remote_id, target in pending:
            if float(target.get("next_attempt_at") or 0) <= now:
                submissions.append((row, account, remote_id, target))
                break
    store.save_repairs(backend, waiting)
    return submissions


def _submit_uploads(backend: str, submissions: list[tuple], summary: dict, now: float, checkpoint) -> None:
    for row, _, _, target in submissions:
        if not target.get("key"):
            target.update(key=f"c2a-upload:{uuid.uuid4().hex}", token_generation=row["source_generation"])
    store.save_repairs(backend, (row for row, _, _, _ in submissions))
    changed = []
    for row, account, remote_id, target in submissions:
        checkpoint()
        try:
            queued = manual_sync.queue_target(account, remote_id, expected_backend=backend,
                                              idempotency_key=target["key"], trigger=_TASK)
        except Exception as exc:
            code = _code(getattr(exc, "code", None), "c2a_upload_queue_failed")
            _note(summary, code, stage="sync_submit", error=exc)
            target.update(last_code=code, next_attempt_at=now + _cooldown())
        else:
            if queued.get("accepted") and queued.get("task_id") and queued.get("run_id"):
                target.update(task_id=queued["task_id"], run_id=queued["run_id"], last_code=None, next_attempt_at=0)
                summary["child_tasks"].append({
                    "task_id": str(queued["task_id"]), "run_id": str(queued["run_id"]),
                    "task_type": manual_sync.TASK_TYPE, "status": queued.get("status") or "queued",
                })
                summary["sync_queued"] += 1
            else:
                code = _code(queued.get("error_code"), "account_busy" if queued.get("busy") else "c2a_upload_queue_failed")
                _note(summary, code)
                target.update(last_code=code, next_attempt_at=now + _cooldown())
        changed.append(row)
    store.save_repairs(backend, changed)


def _abnormal_accounts(remote: list[dict], summary: dict, now: float) -> dict[str, list[dict]]:
    by_email = defaultdict(list)
    for item in remote:
        eligible, reason = _remote_disposition(item, now)
        if eligible or reason:
            summary["remote_errors"] += 1
        if reason:
            _note(summary, reason)
        if not eligible:
            continue
        email = _email(item.get("email"))
        if not email or not item.get("id"):
            _note(summary, "c2a_scan_response_invalid")
            continue
        by_email[email].append(item)
    return by_email


def _discover(by_email: dict, matched: dict, repairs: dict, summary: dict, now: float, *, force: bool) -> list[dict]:
    discovered = []
    for email, items in by_email.items():
        accounts = matched.get(email, [])
        if len(accounts) > 1:
            _note(summary, "c2a_local_account_ambiguous")
            continue
        account = accounts[0] if accounts else None
        reason = _local_skip(account, email)
        if reason:
            _note(summary, reason)
            continue
        account_id = account["id"]
        row = repairs.get(account_id, {})
        stage = row.get("stage")
        if stage in (*store.ACTIVE_STAGES, "refresh_exhausted"):
            continue
        if stage == "cancelled" and not force:
            _note(summary, "c2a_repair_cancelled")
            continue
        if not force and float(row.get("next_attempt_at") or 0) > now:
            _note(summary, "c2a_repair_cooldown")
            continue
        if len(discovered) >= _limit():
            _note(summary, "c2a_scan_cycle_limit")
            break
        generation, issued, expiry = _at(account)
        failure_count = int(row.get("refresh_failure_count") or 0)
        if generation != row.get("source_generation") and expiry is not None and expiry > now:
            failure_count = 0
        if failure_count >= _REFRESH_FAILURE_LIMIT:
            _note(summary, "c2a_refresh_attempts_exhausted")
            continue
        blocked = {} if force else {
            remote_id: target for remote_id, target in (row.get("targets") or {}).items()
            if target.get("last_code") == "c2a_remote_token_conflict" and target.get("token_generation") == generation
        }
        pending = [item for item in items if item["id"] not in blocked]
        if not pending:
            _note(summary, "c2a_remote_token_conflict")
            continue
        can_sync = all(_newer_at(item, issued, expiry, now) for item in pending)
        discovered.append({
            "account_id": account_id, "email": email, "source_generation": generation,
            "stage": "sync_wait" if can_sync else "refresh_retry", "next_attempt_at": 0,
            "targets": {**blocked, **{item["id"]: {"state": "pending"} for item in pending}},
            "attempt_count": 0,
            "refresh_failure_count": failure_count,
            "refresh_observed_run_id": row.get("refresh_observed_run_id"),
        })
    return discovered


def _refresh_due(backend: str, repairs: list[dict], accounts: dict, summary: dict, now: float) -> list[dict]:
    due = []
    changed = []
    for row in repairs:
        if row["stage"] not in {"refresh_retry", "refresh_exhausted"}:
            continue
        account = accounts.get(row["account_id"])
        reason = _local_skip(account, row["email"])
        if reason:
            _cool(row, reason, now, stage="done")
            _note(summary, reason)
            changed.append(row)
            continue
        generation, _, expiry = _at(account)
        if generation != row["source_generation"] and expiry is not None and expiry > now:
            row.update(stage="sync_wait", source_generation=generation, next_attempt_at=0, last_code=None,
                       refresh_failure_count=0)
            changed.append(row)
        elif int(row.get("refresh_failure_count") or 0) >= _REFRESH_FAILURE_LIMIT:
            if row["stage"] != "refresh_exhausted":
                row["stage"] = "refresh_exhausted"
                changed.append(row)
            _note(summary, "c2a_refresh_attempts_exhausted")
        elif float(row.get("next_attempt_at") or 0) <= now:
            row["source_generation"] = generation
            due.append(row)
    store.save_repairs(backend, changed)
    return due


def _scan(backend: str, *, force: bool = False, continuation_only: bool = False, context=None) -> dict:
    checkpoint = context.checkpoint if context else lambda: None
    continuation_only = continuation_only or (not force and not _enabled())
    summary = {"ok": True, "enabled": _enabled(), "continuation_only": continuation_only,
               "remote_errors": 0, "accounts": 0, "processed": 0, "refresh_queued": 0, "sync_queued": 0,
               "reasons": Counter(), "diagnostics": [], "batch_refs": {}, "child_tasks": []}
    with store.scan_lock(backend) as acquired:
        if not acquired:
            _note(summary, "c2a_scan_in_progress")
            return dict(summary, ok=False, error_code="c2a_scan_in_progress", stage="c2a_scan", batch_refs=[])
        repairs = {row["account_id"]: row for row in store.list_repairs(backend)}
        # 耗尽行只观察人工重跑或本地新 AT，不作为待办持续唤醒已关闭的巡检。
        active = [row for row in repairs.values() if row["stage"] in (*store.ACTIVE_STAGES, "refresh_exhausted")]
        by_email = {}
        if not continuation_only:
            try:
                remote = client.list_configured_accounts(expected_backend=backend, checkpoint=checkpoint)
                by_email = _abnormal_accounts(remote, summary, time.time())
            except (task_gateway.OperationCancelled, task_gateway.OperationLeaseLost):
                raise
            except Exception as exc:
                code = _code(getattr(exc, "code", None), "c2a_scan_response_invalid")
                _note(summary, code, stage="c2a_scan", error=exc)
                summary.update(ok=False, error_code=code, stage="c2a_scan")
                if code == "c2a_backend_changed":
                    return dict(summary, batch_refs=[])
        checkpoint()
        if client.configured_backend_identity() != backend:
            _note(summary, "c2a_backend_changed")
            return dict(summary, ok=False, error_code="c2a_backend_changed", stage="c2a_scan", batch_refs=[])
        accounts = store.account_material([row["account_id"] for row in active], by_email.keys())
        matched = defaultdict(list)
        for account in accounts:
            matched[_email(account["email"])].append(account)
        by_id = {account["id"]: account for account in accounts}
        if context:
            context.report(stage="c2a_repair", message="正在推进已受理修复并汇总新异常")
        now = time.time()
        limit = _limit()
        discovered = _discover(by_email, matched, repairs, summary, now, force=force)
        scheduled = _advance_refresh(backend, active, by_id, summary, now, checkpoint, limit)
        store.save_repairs(backend, discovered)
        active.extend(discovered)
        summary.update(accounts=len(by_email), processed=len(active))
        due = _refresh_due(backend, active, by_id, summary, now)
        submissions = _advance_uploads(backend, active, by_id, summary, now)
        candidates = {row["account_id"] for row in due} | {item[0]["account_id"] for item in submissions}
        ordered = [row["account_id"] for row in active if row["account_id"] in candidates - scheduled]
        remaining = max(0, limit - len(scheduled))
        selected = set(ordered[:remaining])
        if len(ordered) > remaining:
            _note(summary, "c2a_scan_cycle_limit")
        _submit_uploads(backend, [item for item in submissions if item[0]["account_id"] in selected], summary, now, checkpoint)
        due = [row for row in due if row["account_id"] in selected]
        if due:
            checkpoint()
            _reserve_refresh(backend, due)
            _submit_refresh(backend, due, summary, now, checkpoint, scheduled)
    return dict(summary, batch_refs=list(summary["batch_refs"].values()))


def register_actions() -> None:
    task_gateway.register_operation_actions(
        TASK_TYPE, retry_handler=task_gateway.default_operation_retry,
        cancel_handler=task_gateway.default_operation_cancel, terminate_handler=task_gateway.default_operation_terminate,
    )


def register_handler() -> None:
    concurrency.register_admission_alias(TASK_TYPE, "maintenance_check")
    task_gateway.register_operation_handler(TASK_TYPE, _handle_scan, config_allowlist=())
    register_actions()


def _handle_scan(context):
    context.checkpoint()
    data = context.run.get("data") or {}
    backend = str(data.get("backend_identity") or "")
    try:
        if not backend or client.configured_backend_identity() != backend:
            return task_gateway.OperationResult.failed("C2A 巡检目标已变化", {"error_code": "c2a_backend_changed"})
        context.report(stage="c2a_scan", message="正在读取 C2A 账号和巡检进度")
        result = _scan(backend, force=bool(data.get("force")), continuation_only=bool(data.get("continuation_only")),
                       context=context)
    except (task_gateway.OperationCancelled, task_gateway.OperationLeaseLost):
        raise
    except Exception as exc:
        code = _code(getattr(exc, "code", None), "c2a_scan_storage_unavailable")
        logger.warning("C2A 巡检无法继续：分类=%s 异常=%s", code, type(exc).__name__)
        result = {"ok": False, "error_code": code, "stage": "c2a_scan", "error_class": type(exc).__name__}
    # 原因码作为值写入，避免任务摘要脱敏规则把含 token、OTP 等字样的键移除。
    if "reasons" in result:
        result["reasons"] = [{"code": code, "count": count} for code, count in result["reasons"].most_common()]
    if not result["ok"]:
        return task_gateway.OperationResult.failed("C2A 异常巡检未完成，请查看分类和任务回执", result)
    return task_gateway.OperationResult.success(result, message="C2A 异常巡检完成，修复结果在各任务回执更新")


def run_once(*, force: bool = False, continuation_only: bool = False) -> dict:
    try:
        backend = client.configured_backend_identity()
        return task_gateway.submit_durable_operation(
            task_type=TASK_TYPE, account_id=None, email="",
            trigger="manual" if force else _TASK, source_id=f"c2a-scan:{uuid.uuid4().hex}",
            resource_family=TASK_TYPE,
            data={"backend_identity": backend, "force": bool(force), "continuation_only": bool(continuation_only)},
        )
    except Exception as exc:
        code = _code(getattr(exc, "code", None), "c2a_scan_queue_failed")
        logger.warning("C2A 巡检入队失败：分类=%s 异常=%s", code, type(exc).__name__)
        return {"ok": False, "accepted": False, "error_code": code, "error_class": type(exc).__name__}


def status() -> dict:
    result = {"enabled": _enabled(), "interval_seconds": _interval(), "cooldown_seconds": _cooldown(),
              "max_per_cycle": _limit(), "repair_stages": {}, "last_run_at": None, "next_run_at": None,
              "seconds_until_due": None, "state_available": False, "error_code": None}
    try:
        backend = client.configured_backend_identity()
    except client.C2AError as exc:
        backend = None
        result["error_code"] = exc.code
    try:
        stages, last_run_at = store.status_facts(backend, _TASK)
        previous = datetime.fromisoformat(last_run_at) if last_run_at else None
        remaining = scheduler_state._remaining(previous, result["interval_seconds"])
        result.update(repair_stages=stages, last_run_at=last_run_at, state_available=True,
                      next_run_at=(datetime.now() + timedelta(seconds=remaining)).isoformat(timespec="seconds"),
                      seconds_until_due=int(remaining))
    except Exception as exc:
        result.update(error_code="c2a_scan_storage_unavailable", error_class=type(exc).__name__)
    return result


def _periodic_enabled() -> bool:
    if _enabled():
        return True
    try:
        return store.has_pending(client.configured_backend_identity())
    except client.C2AError:
        return False


def _scheduler_loop() -> None:
    scheduler_state.run_periodic(
        task=_TASK, label="C2A 异常巡检", work=run_once, enabled=_periodic_enabled, interval_seconds=_interval,
        stop=_SCHEDULER.stop_event, lifecycle=_SCHEDULER,
    )


def start_periodic_monitor() -> bool:
    return _SCHEDULER.start(_scheduler_loop, before_start=register_handler)


def stop_periodic_monitor(timeout: float = 2.0) -> bool:
    return _SCHEDULER.stop(timeout)


def scheduler_status() -> dict:
    return _SCHEDULER.status(enabled=_enabled())
