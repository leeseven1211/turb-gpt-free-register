# -*- coding: utf-8 -*-
"""统一任务进度、阶段快照和失败摘要投影。

任务执行器可以继续写自己的 raw stage，但快照只从
``core.task_stages.flow_for`` 取得业务模板。事件是阶段事实，run status
只决定结果栏的远端状态；它不会把尚未收口的阶段批量涂成成功或失败。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable

from core.task_run_log import redact_text
from core.task_stages import flow_for, normalize_stage, normalize_step_state, resolve_step


_CHILD_LABELS = {
    "login": "打开并提交登录邮箱", "login_password": "账号密码",
    "login_mfa": "登录 MFA", "email_otp": "验证邮箱验证码",
    "mfa_challenge": "验证 TOTP MFA", "session_token": "确认登录会话",
    "password_reset": "重置密码验证", "password_reset_otp": "验证重置验证码",
    "protocol_attempt": "协议尝试", "browser_fallback": "浏览器回退",
    "password_checkpoint": "保存密码检查点", "password_remote_confirm": "确认远端密码结果",
    "twofa_checkpoint": "保存 2FA 检查点", "twofa_remote_confirm": "确认 2FA 已启用",
    "dispatch": "已提交独立任务", "account_setup": "账号配置任务", "change_email_begin": "发送换绑验证码",
    "change_email_verify": "确认新邮箱", "recent_login": "Recent Login 重认证",
    "new_email_otp": "验证新邮箱验证码",
}


def _safe_message(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return redact_text(str(value), 500)


def _event_detail(event: dict[str, Any]) -> dict[str, Any]:
    detail = event.get("detail")
    return detail if isinstance(detail, dict) else {}


def _event_id(event: dict[str, Any]) -> str | None:
    value = event.get("event_id") or event.get("id") or event.get("transition_id") or event.get("event_uuid") or event.get("source_id")
    return str(value) if value is not None else None


def _event_state(event: dict[str, Any]) -> str | None:
    detail = _event_detail(event)
    state = normalize_step_state(detail.get("step_state") or detail.get("state_after"))
    if state:
        return state
    event_type = str(event.get("event_type") or "")
    if event_type.startswith("stage."):
        return normalize_step_state(event_type.removeprefix("stage."))
    return None


def _raw_stage(event: dict[str, Any]) -> str:
    return normalize_stage(_original_stage(event))


def _original_stage(event: dict[str, Any]) -> str:
    return str(_event_detail(event).get("raw_stage") or event.get("raw_stage") or event.get("stage") or "event").strip()


def _event_time(event: dict[str, Any]) -> str | None:
    detail = _event_detail(event)
    for key in ("started_at", "captured_at"):
        if detail.get(key):
            return str(detail[key])
    for key in ("created_at", "captured_at", "timestamp", "ts"):
        if event.get(key):
            return str(event[key])
    for key in ("created_at", "completed_at"):
        if detail.get(key):
            return str(detail[key])
    return None


def _event_order_time(event: dict[str, Any]) -> str | None:
    detail = _event_detail(event)
    value = detail.get("started_at") or event.get("created_at") or event.get("captured_at") or event.get("timestamp") or event.get("ts")
    return str(value) if value else None


def _event_completed_time(event: dict[str, Any]) -> str | None:
    detail = _event_detail(event)
    value = detail.get("completed_at") or event.get("created_at") or event.get("captured_at") or event.get("timestamp") or event.get("ts")
    return str(value) if value else None


def _time_value(value: Any) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, OverflowError):
        return None


def _step(item: dict[str, Any], *, planned: bool = True) -> dict[str, Any]:
    step_id = str(item.get("id") or item.get("step_id") or "result")
    return {
        "id": step_id, "step_id": step_id, "label": item.get("label") or step_id,
        "group": item.get("group", "other"), "raw_stages": list(item.get("raw_stages") or [step_id]),
        "state": "pending", "display_status": "pending", "active": False,
        "reason": "记录不足/未执行" if planned else None, "children": [], "attempts": [],
        "event_ids": [], "last_event_id": None, "started_at": None,
        "completed_at": None, "duration_ms": None, "message": None,
        "evidence": "unobserved" if planned else "explicit", "observed_order": None,
    }


def _child(child_id: str) -> dict[str, Any]:
    return {
        "id": child_id, "step_id": child_id, "label": _CHILD_LABELS.get(child_id, child_id),
        "state": "pending", "display_status": "pending", "active": False,
        "reason": "记录不足/未执行", "attempts": [], "event_ids": [], "last_event_id": None,
        "started_at": None, "completed_at": None, "duration_ms": None, "message": None,
        "evidence": "unobserved", "observed_order": None,
    }


def _template(task_type: str, run: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [_step(item) for item in flow_for(task_type, run)]


def _child_id(raw_stage: str, detail: dict[str, Any]) -> str | None:
    explicit = str(detail.get("child_step_id") or detail.get("child_id") or "").strip()
    if explicit:
        return explicit
    if raw_stage in {"login", "login_password", "login_mfa", "email_otp", "mfa_challenge", "password_reset", "password_reset_otp", "recent_login", "new_email_otp", "credential_confirm", "credential_persist", "account_setup"}:
        return raw_stage
    if raw_stage == "token":
        return "session_token"
    driver = str(detail.get("driver") or "").strip().lower()
    if driver in {"browser_fallback", "browser-fallback"}:
        return "browser_fallback"
    return None


def _find_step(steps: list[dict[str, Any]], step_id: str) -> dict[str, Any] | None:
    return next((item for item in steps if item["id"] == step_id), None)


def _raw_to_main(task_type: str, raw: str, detail: dict[str, Any], steps: list[dict[str, Any]]) -> str | None:
    resolved = resolve_step(task_type, raw, detail)
    return resolved if resolved and _find_step(steps, resolved) else None


def _state(item: dict[str, Any], value: str, *, reason: str | None = None, display: str | None = None) -> None:
    item["state"] = value
    item["display_status"] = display or value
    item["active"] = value == "running"
    if reason:
        item["reason"] = reason


def _state_after_attempt(item: dict[str, Any], value: str) -> None:
    """更新聚合步骤状态，避免 skip 覆盖已确认的失败。"""
    if item.get("state") in {"failed", "success", "running"} and value == "skipped":
        return
    _state(item, value)


def _append_unique(values: list[Any], value: Any) -> None:
    if value is not None and value not in values:
        values.append(value)


def _record(item: dict[str, Any], event: dict[str, Any], state: str, *, raw: str, child_id: str | None, order: int) -> dict[str, Any]:
    detail = _event_detail(event)
    event_id = _event_id(event)
    timestamp = _event_time(event)
    message = _safe_message(detail.get("message") or event.get("message") or detail.get("error_message"))
    evidence = str(detail.get("evidence") or ("explicit" if event_id or detail.get("step_id") else "legacy"))
    observed = evidence not in {"not_executed", "unobserved"}
    if not observed:
        timestamp = None
    attempt = {"event_id": event_id, "event_uuid": event.get("event_uuid"), "transition_id": event.get("transition_id"), "state": state, "raw_stage": raw, "event_type": event.get("event_type"), "created_at": timestamp, "message": message, "evidence": evidence}
    for key in ("duration_ms", "wait_reason", "error_code", "state_before", "state_after", "transition_id", "child_task_id", "child_run_id", "child_task_type", "failure_stage", "failure_event_id", "failure_message"):
        if detail.get(key) is not None:
            attempt[key] = detail[key]
    target = item
    if child_id:
        target = next((child for child in item["children"] if child["id"] == child_id), None)
        if target is None:
            target = _child(child_id)
            item["children"].append(target)
        attempt["step_id"] = child_id
    target["attempts"].append(attempt)
    _append_unique(target["event_ids"], event_id)
    target["last_event_id"] = event_id or target.get("last_event_id")
    target["evidence"] = evidence
    target["reason"] = None if evidence not in {"not_executed", "unconfirmed", "unobserved"} else message or "阶段记录不足，结果未确认"
    if observed:
        target["observed_order"] = order if target.get("observed_order") is None else target["observed_order"]
    if timestamp:
        target["started_at"] = target.get("started_at") or timestamp
        if state in {"success", "failed", "skipped"}:
            target["completed_at"] = _event_completed_time(event) or timestamp
    if detail.get("started_at"):
        candidate_start = str(detail["started_at"])
        previous_time, candidate_time = _time_value(target.get("started_at")), _time_value(candidate_start)
        if previous_time is None or (candidate_time is not None and candidate_time < previous_time):
            target["started_at"] = candidate_start
    if detail.get("completed_at"):
        target["completed_at"] = str(detail["completed_at"])
    if detail.get("duration_ms") is not None:
        target["duration_ms"] = detail.get("duration_ms")
    elif target.get("started_at") and target.get("completed_at"):
        start, end = _time_value(target["started_at"]), _time_value(target["completed_at"])
        if start is not None and end is not None and end > start:
            target["duration_ms"] = max(0, int((end - start) * 1000))
    if message:
        target["message"] = message
    _state_after_attempt(target, state)
    if child_id:
        # 主步骤 attempts 是稳定的审计视图；子阶段转移同时保存在父项，
        # 调用方无需了解分支结构即可检查实际执行。
        item["attempts"].append(dict(attempt))
        item["event_ids"] = list(dict.fromkeys([*item.get("event_ids", []), event_id])) if event_id else item.get("event_ids", [])
        item["last_event_id"] = event_id or item.get("last_event_id")
        item["evidence"] = evidence
        item["reason"] = target["reason"]
        if observed:
            item["observed_order"] = order if item.get("observed_order") is None else item["observed_order"]
        if target.get("started_at"):
            target_start = _time_value(target["started_at"])
            item_start = _time_value(item.get("started_at"))
            if not item.get("started_at") or (target_start is not None and item_start is not None and target_start < item_start):
                item["started_at"] = target["started_at"]
        if target.get("completed_at"):
            target_end = _time_value(target["completed_at"])
            item_end = _time_value(item.get("completed_at"))
            if not item.get("completed_at") or (target_end is not None and item_end is not None and target_end > item_end):
                item["completed_at"] = target["completed_at"]
        if detail.get("duration_ms") is not None:
            item["duration_ms"] = detail.get("duration_ms")
        elif item.get("started_at") and item.get("completed_at"):
            start, end = _time_value(item["started_at"]), _time_value(item["completed_at"])
            if start is not None and end is not None and end > start:
                item["duration_ms"] = max(0, int((end - start) * 1000))
        if message:
            item["message"] = message
        _state_after_attempt(item, state)
    return attempt


def _add_unknown(steps: list[dict[str, Any]], raw: str) -> dict[str, Any]:
    normalized = normalize_stage(raw or "event")
    base = "unknown:" + normalized
    existing = _find_step(steps, base)
    if existing is not None:
        return existing
    step_id, suffix = base, 2
    while _find_step(steps, step_id):
        step_id = f"{base}:{suffix}"
        suffix += 1
    item = _step({"id": step_id, "label": f"未知阶段：{raw or 'event'}", "group": "unknown", "raw_stages": [raw or "event"]}, planned=False)
    item["reason"] = "模板未定义，保留原始阶段"
    item["evidence"] = "explicit"
    result_index = next((index for index, value in enumerate(steps) if value["id"] == "result"), len(steps))
    steps.insert(result_index, item)
    return item


def _status_for_run(run: dict[str, Any]) -> tuple[str, str]:
    status = str(run.get("status") or "").strip().lower()
    if status == "success":
        return "success", "success"
    if status == "partial_success":
        return "success", "partial_success"
    if status in {"request_unknown", "unknown", "manual_reconcile", "password_confirmation_pending", "attention_required"}:
        return "pending", status
    if status in {"cancelled", "canceled", "stopped", "interrupted", "failed", "deactivated", "unsupported"}:
        return "failed", status
    if status in {"queued", "running", "stopping", "cancelling", "settling", "waiting"}:
        return "pending", status or "pending"
    return "pending", status or "pending"


def _child_tasks(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """统一父任务的子任务引用，兼容旧补全流程的命名摘要。"""
    values = summary.get("child_tasks") or []
    values = list(values.values()) if isinstance(values, dict) else values if isinstance(values, list) else []
    children = [dict(value) if isinstance(value, dict) else {"task_id": value} for value in values if isinstance(value, (dict, int, str))]
    for key, task_type in (("refresh_token", "token_refresh"), ("account_setup", "account_setup_retry"), ("codex", "codex_retry")):
        child = summary.get(key)
        if isinstance(child, dict) and child.get("task_id") and not any(str(value.get("task_id")) == str(child["task_id"]) for value in children):
            children.append({"task_type": task_type, **child})
    child = summary.get("child_result")
    if isinstance(child, dict) and child.get("task_id"):
        found = next((value for value in children if str(value.get("task_id")) == str(child["task_id"])), None)
        payload = {"status": summary.get("child_status"), **child}
        if found is None:
            children.append(payload)
        else:
            found.update(payload)
    return children


def _result(steps: list[dict[str, Any]], run: dict[str, Any], observations: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    item = _find_step(steps, "result")
    assert item is not None
    complete = observations.get("result") or []
    run_status = str(run.get("status") or "").strip().lower()
    authoritative = {"success", "partial_success", "failed", "stopped", "cancelled", "canceled", "interrupted", "attention_required", "request_unknown", "unknown", "manual_reconcile", "password_confirmation_pending", "deactivated", "unsupported"}
    if complete and run_status not in authoritative:
        _state(item, complete[-1]["state"])
        item["reason"] = None
    else:
        state, display = _status_for_run(run)
        _state(item, state, display=display)
        item["evidence"] = "run_status" if run.get("status") else "unobserved"
        item["reason"] = "run status 仅描述结果，阶段没有完整事件" if run.get("status") else "记录不足/未执行"
    children = []
    for child in _child_tasks(run.get("result_summary") or {}):
        if isinstance(child, dict):
            children.append({key: _safe_message(child.get(key)) if key == "error_message" else child.get(key) for key in ("task_id", "run_id", "task_type", "status", "accepted", "busy", "failure_stage", "failure_event_id", "error_code", "error_message") if child.get(key) is not None})
        elif isinstance(child, (int, str)):
            children.append({"task_id": child})
    return {"status": item["display_status"], "state": item["state"], "message": _safe_message(run.get("message") or run.get("error_message")) or "", "child_tasks": children}


def _current(steps: list[dict[str, Any]], activity: list[dict[str, Any]], run_status: str = "") -> dict[str, Any] | None:
    if str(run_status or "").lower() in {"success", "partial_success", "failed", "stopped", "cancelled", "canceled", "interrupted", "attention_required", "request_unknown", "unknown", "manual_reconcile", "password_confirmation_pending", "deactivated", "unsupported"}:
        return None
    latest = next((value for value in reversed(activity) if value.get("main_step_id") != "result"), None)
    if not latest:
        return None
    item = _find_step(steps, latest["main_step_id"])
    if item is None:
        return None
    child = next((value for value in item.get("children", []) if value["id"] == latest.get("child_step_id")), None)
    return {"step_id": item["id"], "child_step_id": child["id"] if child else None, "child_label": child["label"] if child else None, "label": child["label"] if child else item["label"], "raw_stage": latest.get("raw_stage"), "event_id": latest.get("event_id"), "state": latest.get("state"), "evidence": latest.get("evidence")}


def _unrecovered_failures(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """保留未恢复的失败；协议回退成功可以关闭同一业务操作的失败。"""
    candidates = []
    for attempt in attempts:
        if attempt.get("state") != "failed" or attempt.get("evidence") not in {"explicit", "unconfirmed"}:
            continue
        confirming = {
            "set_twofa": {"twofa", "twofa_result", "set_twofa", "twofa_remote_confirm"},
            "set_password": {"set_password", "password_remote_confirm"},
        }.get(attempt.get("main_step_id"), {attempt.get("main_step_id")})
        later = [value for value in attempts if value.get("main_step_id") == attempt.get("main_step_id")
                 and value.get("sequence", 0) > attempt.get("sequence", 0)
                 and (value.get("child_step_id") == attempt.get("child_step_id") or value.get("raw_stage") in confirming)]
        if not any(value.get("state") == "success" for value in later):
            candidates.append(attempt)
    return candidates


def _failure(task_type: str, run: dict[str, Any], attempts: list[dict[str, Any]], activity: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = _unrecovered_failures(attempts)
    explicit_failure = bool(candidates)
    chosen = candidates[-1] if candidates else None
    status = str(run.get("status") or "").strip().lower()
    summary = run.get("result_summary") or {}
    data = run.get("data") if isinstance(run.get("data"), dict) else {}
    child_failure = None
    for owner in (summary, data, run):
        for key in ("child_results", "child_tasks", "child_result"):
            values = _child_tasks(owner) if key == "child_tasks" and isinstance(owner, dict) else owner.get(key) if isinstance(owner, dict) else None
            values = [dict(values, status=values.get("status") or owner.get("child_status"))] if key == "child_result" and isinstance(values, dict) else list(values.values()) if isinstance(values, dict) else values if isinstance(values, list) else []
            for child in values:
                if not isinstance(child, dict) or str(child.get("status") or child.get("state") or "").lower() not in {"failed", "error", "attention_required", "request_unknown"}:
                    continue
                child_failure = {
                    "main_step_id": child.get("step_id") or child.get("main_step_id") or ("account_setup_dispatch" if child.get("task_type") in {"account_setup", "account_setup_retry", "password_setup", "password_change", "twofa_setup", "twofa_change", "twofa_retry"} else "refresh_dispatch" if child.get("task_type") in {"token_refresh", "refresh_token"} else "codex_dispatch" if child.get("task_type") == "codex_retry" else "result"),
                    "raw_stage": child.get("failure_stage") or child.get("stage") or child.get("raw_stage") or child.get("task_type") or "child_task",
                    "error_code": child.get("error_code"), "child_task_type": child.get("task_type"), "child_task_id": child.get("task_id"), "child_run_id": child.get("run_id"),
                    "event_id": child.get("event_id") or child.get("failure_event_id"),
                    "state": "failed", "message": _safe_message(child.get("message") or child.get("error_message") or child.get("error")), "evidence": "inferred",
                    "reconcile_required": bool(child.get("reconcile_required") or str(child.get("status") or "").lower() in {"attention_required", "request_unknown"}),
                }
                break
            if child_failure:
                break
        if child_failure:
            break
    reconcile = bool(summary.get("reconcile_required") or summary.get("requires_reconcile") or data.get("reconcile_required") or str(summary.get("outcome") or "").lower() == "request_unknown" or status in {"request_unknown", "unknown", "manual_reconcile", "password_confirmation_pending", "attention_required"})
    terminal = {"failed", "stopped", "cancelled", "canceled", "interrupted", "deactivated", "unsupported", "request_unknown", "unknown", "manual_reconcile", "password_confirmation_pending", "attention_required", "partial_success"}
    if chosen is None and child_failure is None and status not in terminal:
        return None
    if chosen is None and child_failure is None:
        if status == "partial_success" and not any((run.get("error_message"), summary.get("error_code"), summary.get("error_message"), summary.get("plan_check_error"))):
            return None
        if status in {"cancelled", "canceled"} and "started_at" in run and run.get("started_at") is None and not activity:
            return None
    if child_failure is not None and (chosen is None or chosen.get("child_task_id") or chosen.get("main_step_id") in {"plan", "result", "refresh_dispatch", "account_setup_dispatch", "codex_dispatch"}):
        chosen = child_failure
    evidence = chosen.get("evidence") if explicit_failure and chosen else "inferred"
    if evidence not in {"explicit", "inferred", "legacy", "unobserved", "unconfirmed"}:
        evidence = "explicit" if chosen else "inferred"
    if chosen is None:
        saved_stage = run.get("failure_stage") or data.get("failure_stage") or (summary.get("failure_stage") if isinstance(summary, dict) else None)
        saved_event_id = run.get("failure_event_id") or data.get("failure_event_id") or (summary.get("failure_event_id") if isinstance(summary, dict) else None)
        saved_message = run.get("message") or data.get("failure_message") or run.get("error_message")
        if saved_stage or saved_event_id:
            chosen = {"main_step_id": run.get("failure_step_id") or data.get("failure_step_id") or saved_stage or "result", "raw_stage": saved_stage or run.get("progress_stage") or "result", "event_id": saved_event_id, "state": "failed", "message": _safe_message(saved_message), "evidence": "inferred"}
        else:
            last_activity = next((value for value in reversed(activity) if value.get("main_step_id") != "result"), None)
            chosen = last_activity or {"main_step_id": run.get("progress_stage") or "result", "raw_stage": run.get("progress_stage") or "result", "event_id": None, "state": "failed", "message": _safe_message(run.get("message") or run.get("error_message")), "evidence": "inferred"}
    if chosen.get("child_task_id") and chosen.get("failure_stage"):
        chosen = {**chosen, "raw_stage": chosen["failure_stage"], "event_id": chosen.get("failure_event_id") or chosen.get("event_id"), "message": chosen.get("failure_message") or chosen.get("message")}
    reconcile = reconcile or bool(chosen.get("reconcile_required"))
    message = _safe_message(chosen.get("message") or run.get("message") or run.get("error_message"))
    try:
        from core.task_errors import classify_task_error
        error_code = chosen.get("error_code") or summary.get("error_code") or data.get("error_code") or run.get("error_code") or ""
        error_info = classify_task_error(message or str(error_code), stage=chosen.get("raw_stage"), task_type=chosen.get("child_task_type") or task_type, error_code=error_code, result_summary=summary, task_status=status)
    except (ImportError, TypeError):
        error_info = None
    stable_step = chosen.get("main_step_id") if chosen.get("child_task_type") else resolve_step(task_type, chosen.get("raw_stage"), run=run) or chosen.get("main_step_id") or "result"
    stable_label = chosen.get("label")
    if not stable_label:
        stable_label = next((item.get("label") for item in flow_for(task_type, run) if item.get("id") == stable_step), None)
    return {"step_id": stable_step, "stage": chosen.get("raw_stage"), "label": stable_label or chosen.get("raw_stage"), "event_id": chosen.get("event_id"), "evidence": evidence, "message": message or "", "error_info": error_info, "reconcile_required": reconcile, "child_task_id": chosen.get("child_task_id"), "child_run_id": chosen.get("child_run_id")}


def _ordered_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = [value for value in steps if value["id"] == "result"]
    body = [value for value in steps if value["id"] != "result"]
    observed = [value for value in body if value.get("observed_order") is not None]
    planned = [value for value in body if value.get("observed_order") is None]
    observed.sort(key=lambda value: (_time_value(value.get("started_at")) is None, _time_value(value.get("started_at")) or 0, value["observed_order"]))
    for index, value in enumerate(observed, 1):
        value["observed_order"] = index
    return [*observed, *planned, *result]


def _legacy_events(run: dict[str, Any]) -> list[dict[str, Any]]:
    """把旧 progress_steps/occurrences 只读补成投影事件。"""
    sources: list[Any] = []
    data = run.get("data") if isinstance(run.get("data"), dict) else {}
    summary = run.get("result_summary") if isinstance(run.get("result_summary"), dict) else {}
    for owner in (run, data, summary):
        for key in ("progress_steps", "occurrences", "route_attempts"):
            value = owner.get(key)
            if value:
                sources.append(value)
    result: list[dict[str, Any]] = []
    for source in sources:
        entries = list(source.items()) if isinstance(source, dict) else list(source) if isinstance(source, (list, tuple)) else []
        for index, entry in enumerate(entries):
            if isinstance(source, dict):
                stage, value = entry
                item = dict(value) if isinstance(value, dict) else {"state": value}
                item.setdefault("stage", stage)
            elif isinstance(entry, dict):
                item = dict(entry)
            else:
                continue
            stage = item.get("stage") or item.get("raw_stage") or item.get("name")
            state = item.get("step_state") or item.get("state_after") or item.get("state") or item.get("status")
            state = normalize_step_state(state)
            if not stage or not state:
                continue
            raw_detail = item.get("detail")
            detail = dict(raw_detail) if isinstance(raw_detail, dict) else {"message": _safe_message(raw_detail)} if raw_detail else {}
            for key in ("step_id", "main_step_id", "evidence", "started_at", "completed_at", "duration_ms", "message", "error_code", "route_attempt_no"):
                if item.get(key) is not None:
                    detail[key] = item[key]
            result.append({"stage": stage, "event_type": "legacy.progress", "detail": {"step_state": state, **detail}, "message": item.get("message"), "legacy_index": index})
    if any(_event_detail(value).get("started_at") for value in result):
        result.sort(key=lambda value: (_time_value(_event_detail(value).get("started_at")) is None, _time_value(_event_detail(value).get("started_at")) or 0))
    return result


def build_progress_snapshot(task_id: int, run_id: int, task_type: str, run: dict[str, Any] | None, events: Iterable[dict[str, Any]] | None) -> dict[str, Any]:
    """构建安全的 v2 快照，同时保留 raw stage 证据。"""
    run_value = dict(run or {})
    task_key = str(task_type or "").strip().lower()
    steps = _template(task_key, run_value)
    by_id = {item["id"]: item for item in steps}
    observations: dict[str, list[dict[str, Any]]] = {}
    activity: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    explicit = False
    order = 0
    source_events = [dict(value) for value in (events or []) if isinstance(value, dict)]
    source_events.extend(_legacy_events(run_value))
    for event in source_events:
        if not isinstance(event, dict):
            continue
        state = _event_state(event)
        raw = _raw_stage(event)
        detail = _event_detail(event)
        if state is None:
            continue
        if _event_id(event) or any(key in detail for key in ("step_id", "main_step_id", "child_step_id", "instance_id")):
            explicit = True
        main_id = _raw_to_main(task_key, raw, detail, steps)
        if main_id is None:
            item = _add_unknown(steps, _original_stage(event) or raw)
            main_id = item["id"]
        item = by_id.get(main_id) or _find_step(steps, main_id)
        if item is None:
            continue
        by_id[main_id] = item
        if "legacy_index" in event and item.get("evidence") == "explicit":
            # 旧 progress_steps 只补充缺失证据，不能覆盖 transition 事件事实。
            continue
        child_id = _child_id(raw, detail) if main_id != "result" else None
        if main_id == "set_twofa" and raw in {"twofa", "twofa_result"}:
            child_id = "twofa_remote_confirm" if _original_stage(event) == "twofa_result" else ("browser_fallback" if str(detail.get("driver") or "").lower() == "browser_fallback" else "protocol_attempt")
        if main_id == "set_password" and detail.get("checkpoint"):
            child_id = "password_checkpoint"
        attempt = _record(item, event, state, raw=_original_stage(event) or raw, child_id=child_id, order=order)
        record = {**attempt, "main_step_id": main_id, "child_step_id": child_id, "label": item["label"], "sequence": order}
        observations.setdefault(main_id, []).append({"state": state, "event_id": _event_id(event), "raw_stage": _original_stage(event) or raw})
        attempts.append(record)
        activity.append(record)
        order += 1
    ordered = _ordered_steps(steps)
    # 一个登录子步骤成功不能遮住另一个子步骤的失败。
    unresolved = _unrecovered_failures(attempts)
    for item in ordered:
        if item["id"] != "result" and any(value.get("main_step_id") == item["id"] for value in unresolved):
            _state(item, "failed")
        elif item.get("children") and any(child.get("state") == "running" for child in item["children"]):
            last = next((value for value in reversed(attempts) if value.get("main_step_id") == item["id"]), {})
            if not (item["id"] in {"set_twofa", "set_password"} and last.get("state") == "success"):
                _state(item, "running")
        if item.get("state") == "success":
            for child in item.get("children", []):
                if child.get("state") == "failed" and not any(value.get("main_step_id") == item["id"] and value.get("child_step_id") == child["id"] for value in unresolved):
                    child["display_status"] = "recovered"
                    child["reason"] = "此前尝试失败，后续重试已恢复；原失败记录保留"
    outcome = _result(ordered, run_value, observations)
    terminal = {"success", "partial_success", "failed", "stopped", "cancelled", "canceled", "interrupted", "attention_required", "request_unknown", "unknown", "manual_reconcile", "password_confirmation_pending", "deactivated", "unsupported"}
    if str(run_value.get("status") or "").lower() in terminal:
        terminal_status = str(run_value.get("status") or "").lower()
        unresolved_display = "unconfirmed" if terminal_status in {"success", "partial_success"} else terminal_status if terminal_status in {"attention_required", "request_unknown", "unknown", "manual_reconcile", "password_confirmation_pending"} else "interrupted"
        for item in ordered:
            if item["id"] != "result" and item.get("evidence") == "unobserved":
                never_started = "started_at" in run_value and run_value.get("started_at") is None and not activity
                _state(item, "pending", display="not_executed" if never_started else "unconfirmed", reason="本次执行未开始" if never_started else "未发现该阶段的执行记录")
            if item["id"] != "result" and item.get("state") == "running":
                item["state"] = "pending"
                item["display_status"] = unresolved_display
                item["active"] = False
                item["reason"] = "终态已记录但阶段没有收口事件"
                item["evidence"] = "unconfirmed"
            for child in item.get("children", []):
                if child.get("state") == "running":
                    _state(child, "pending", display=unresolved_display, reason="终态已记录但子阶段没有收口事件")
                    child["evidence"] = "unconfirmed"
    source = "explicit" if explicit else "legacy_derived" if activity else "insufficient_evidence"
    failure = _failure(task_key, run_value, attempts, activity)
    payload = {"steps": ordered, "run": {"id": run_value.get("id"), "status": run_value.get("status"), "progress_stage": run_value.get("progress_stage"), "result_summary": run_value.get("result_summary") or {}}, "events": attempts}
    revision = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return {"task_id": int(task_id), "run_id": int(run_id), "flow_version": 2, "revision": revision, "source": source, "main_steps": ordered, "current": _current(ordered, activity, str(run_value.get("status") or "")), "outcome": outcome, "failure": failure}
