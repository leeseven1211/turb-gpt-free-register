"""原单续查的纯策略；只保存安全元数据，不访问存储或网络。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import math
import re


_HALT_REASONS = {"remote_not_found", "query_failures", "timeout", "no_progress"}
_SUMMARY_FIELDS = (
    "remote_status", "percent", "queue_position", "step_attempt", "auto_relink_attempt",
    "automatic_payment_status", "xxsyun_status", "payment_check_status", "remote_chain_length",
)
_BOOLEAN_FIELDS = ("entitlement_active", "entitlement_inferred", "submission_receipt_pending")
_FINGERPRINT = re.compile(r"[0-9a-f]{64}")
_STEP_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _utc_now(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _date(value: object, fallback: datetime) -> datetime:
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None:
            return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        pass
    return fallback


def _count(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _http_status(value: object) -> int | None:
    return value if type(value) is int and 100 <= value <= 599 else None


def _scalar(value: object) -> str | int | float | bool | None:
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    return None


def _fingerprint(state: object) -> str:
    state = state if isinstance(state, Mapping) else {}
    summary = state.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    progress = {
        "extraction_state": _scalar(state.get("extraction_state")),
        "payment_state": _scalar(state.get("payment_state")),
        **{key: _scalar(summary.get(key)) for key in _SUMMARY_FIELDS},
        **{key: summary.get(key) if type(summary.get(key)) is bool else None for key in _BOOLEAN_FIELDS},
    }
    step = summary.get("current_step")
    # 轮询次数或等待秒数变化不能延长原单的无进展时限。
    progress["current_step"] = " ".join(_STEP_NUMBER.sub("", step).split()) if isinstance(step, str) else ""
    payload = json.dumps(progress, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record_reconcile(
    previous,
    state,
    *,
    now: datetime,
    started_at: object = None,
    query_succeeded: bool | None = None,
    http_status: int | None = None,
) -> dict:
    """累计原单查询证据；只有成功查询中的业务状态变化才算进展。"""
    now = _utc_now(now)
    previous = previous if isinstance(previous, Mapping) else {}
    started = _date(previous.get("started_at", started_at), now)
    last_progress = _date(previous.get("last_progress_at"), now) if "last_progress_at" in previous else started
    previous_fingerprint = previous.get("progress_fingerprint")
    if not isinstance(previous_fingerprint, str) or not _FINGERPRINT.fullmatch(previous_fingerprint):
        previous_fingerprint = ""
    fingerprint = previous_fingerprint or _fingerprint(state)
    failures = _count(previous.get("consecutive_failures"))
    not_found = _count(previous.get("consecutive_not_found"))
    status = _http_status(previous.get("last_http_status"))
    if query_succeeded is True:
        current_fingerprint = _fingerprint(state)
        if previous_fingerprint and current_fingerprint != previous_fingerprint:
            last_progress = now
        fingerprint = current_fingerprint
        failures = not_found = 0
        status = _http_status(http_status)
    elif query_succeeded is False:
        failures += 1
        status = _http_status(http_status)
        not_found = not_found + 1 if status == 404 else 0
    reason = previous.get("halted_reason")
    reason = reason if isinstance(reason, str) and reason in _HALT_REASONS else ""
    return {
        "started_at": started.isoformat(),
        "last_progress_at": last_progress.isoformat(),
        "progress_fingerprint": fingerprint,
        "consecutive_failures": failures,
        "consecutive_not_found": not_found,
        "last_http_status": status,
        "halted_reason": reason,
        "halted_at": _date(previous.get("halted_at"), now).isoformat() if reason else "",
    }


def halt_reason(
    metadata,
    *,
    now: datetime,
    total_timeout: int,
    no_progress_timeout: int,
    max_query_failures: int,
) -> str:
    """按原单不存在、查询故障、总时限和无进展时限判定停止原因。"""
    now = _utc_now(now)
    metadata = metadata if isinstance(metadata, Mapping) else {}
    reason = metadata.get("halted_reason")
    if isinstance(reason, str) and reason in _HALT_REASONS:
        return reason
    if _count(metadata.get("consecutive_not_found")) >= 3:
        return "remote_not_found"
    if _count(metadata.get("consecutive_failures")) >= max_query_failures:
        return "query_failures"
    started = _date(metadata.get("started_at"), now)
    if (now - started).total_seconds() >= total_timeout:
        return "timeout"
    last_progress = _date(metadata.get("last_progress_at"), now) if "last_progress_at" in metadata else started
    if (now - last_progress).total_seconds() >= no_progress_timeout:
        return "no_progress"
    return ""
