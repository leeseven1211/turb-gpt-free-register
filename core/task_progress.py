# -*- coding: utf-8 -*-
"""Build a user-facing progress snapshot for one operation Run.

Raw operation stages are intentionally not a UI flow.  Several workers keep a
browser scope open while they perform login, OTP, and account mutations, and
some workers can fall back from protocol to browser execution.  This module
maps those raw events into a small, ordered set of business steps without
using the paginated event timeline as the source of ordering.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from core.task_run_log import redact_text
from core.task_stages import normalize_stage, normalize_step_state


_STEP_LABELS = {
    "network": "分配网络",
    "email": "准备邮箱",
    "browser": "启动浏览器",
    "authenticate": "登录验证",
    "set_password": "设置密码",
    "set_twofa": "设置 2FA",
    "profile": "账号资料",
    "token": "取得登录 Token",
    "codex": "Codex 授权",
    "preflight": "配置预检",
    "auth_url": "准备授权",
    "phone_verify": "手机验证",
    "consent": "确认授权",
    "callback": "接收回调",
    "credential": "凭证处理",
    "plan": "生成补全计划",
    "refresh_dispatch": "提交刷新 AT",
    "codex_dispatch": "提交 Codex 授权",
    "plan_check": "查询套餐",
    "access_token": "校验 Token",
    "refresh_token": "刷新 Token",
    "mailbox_scan": "扫描邮件",
    "result": "结果",
}

_CHILD_LABELS = {
    "login": "打开并提交登录邮箱",
    "email_otp": "验证邮箱验证码",
    "mfa_challenge": "验证 TOTP MFA",
    "session_token": "确认登录会话",
    "password_reset": "重置密码验证",
    "password_reset_otp": "验证重置验证码",
    "protocol_attempt": "协议尝试",
    "browser_fallback": "浏览器回退",
    "password_checkpoint": "保存密码检查点",
    "password_remote_confirm": "确认远端密码结果",
    "twofa_checkpoint": "保存 2FA 检查点",
    "twofa_remote_confirm": "确认 2FA 已启用",
    "dispatch": "已提交独立任务",
}

def _step(step_id: str, *, state: str = "pending", reason: str | None = None) -> dict[str, Any]:
    return {
        "id": step_id,
        "step_id": step_id,
        "label": _STEP_LABELS.get(step_id, step_id),
        "state": state,
        "display_status": state,
        "active": state == "running",
        "reason": reason,
        "children": [],
        "attempts": [],
    }


def _child(step_id: str, *, state: str = "pending", reason: str | None = None) -> dict[str, Any]:
    return {
        "id": step_id,
        "step_id": step_id,
        "label": _CHILD_LABELS.get(step_id, step_id),
        "state": state,
        "display_status": state,
        "active": state == "running",
        "reason": reason,
        "attempts": [],
    }


def _template(task_type: str, run: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result_summary = (run or {}).get("result_summary") or {}
    planned = {
        str(item or "").strip().lower()
        for item in (result_summary.get("planned_steps") or [])
        if str(item or "").strip()
    }
    if task_type in {"password_setup", "twofa_setup", "twofa_retry", "account_setup_retry"} and planned:
        step_ids = ["network"]
        if "plan_check" in planned:
            step_ids.append("plan_check")
        if "password" in planned and task_type != "twofa_setup":
            step_ids.extend(["browser", "authenticate", "set_password"])
        if "twofa" in planned:
            step_ids.append("set_twofa")
        return [_step(step_id) for step_id in [*step_ids, "result"]]
    if task_type == "account_completion" and planned:
        step_ids = ["plan"]
        if "refresh_at" in planned:
            step_ids.append("refresh_dispatch")
        setup_planned = planned & {"password", "plan_check", "twofa"}
        if setup_planned:
            step_ids.append("network")
            if "plan_check" in setup_planned:
                step_ids.append("plan_check")
            if "password" in setup_planned:
                step_ids.extend(["browser", "authenticate", "set_password"])
            if "twofa" in setup_planned:
                step_ids.append("set_twofa")
        if "codex" in planned:
            step_ids.append("codex_dispatch")
        return [_step(step_id) for step_id in [*step_ids, "result"]]
    templates = {
        "password_setup": ["network", "browser", "authenticate", "set_password", "result"],
        "twofa_setup": ["network", "set_twofa", "result"],
        "twofa_retry": ["network", "authenticate", "set_twofa", "plan_check", "result"],
        "account_setup_retry": [
            "network", "plan_check", "browser", "authenticate", "set_password", "set_twofa", "result",
        ],
        "registration": [
            "network", "email", "browser", "authenticate", "profile", "token", "codex", "set_twofa", "plan_check", "result",
        ],
        "registration_resume": [
            "network", "browser", "authenticate", "profile", "token", "codex", "set_twofa", "plan_check", "result",
        ],
        "codex_retry": [
            "preflight", "network", "browser", "auth_url", "authenticate", "phone_verify", "consent", "callback", "credential", "result",
        ],
        "account_completion": [
            "plan", "refresh_dispatch", "network", "authenticate", "set_password", "set_twofa", "codex_dispatch", "result",
        ],
        "live_check": ["network", "access_token", "result"],
        "token_refresh": ["network", "authenticate", "refresh_token", "result"],
        "codex_token_refresh": ["refresh_token", "result"],
        "plan_check": ["network", "plan_check", "result"],
        "deactivation_mail": ["mailbox_scan", "result"],
    }
    return [_step(step_id) for step_id in templates.get(task_type, ["result"])]


def _event_detail(event: dict[str, Any]) -> dict[str, Any]:
    detail = event.get("detail")
    return detail if isinstance(detail, dict) else {}


def _event_state(event: dict[str, Any]) -> str | None:
    detail = _event_detail(event)
    state = normalize_step_state(detail.get("step_state"))
    if state:
        return state
    event_type = str(event.get("event_type") or "")
    if event_type.startswith("stage."):
        return normalize_step_state(event_type.removeprefix("stage."))
    return None


def _raw_stage(event: dict[str, Any]) -> str:
    return normalize_stage(event.get("stage"))


def _child_id(raw_stage: str, detail: dict[str, Any]) -> str | None:
    explicit = str(detail.get("step_id") or "").strip()
    if explicit:
        return explicit
    if raw_stage == "login":
        return "login"
    if raw_stage in {"email_otp", "mfa_challenge", "password_reset", "password_reset_otp"}:
        return raw_stage
    if raw_stage == "token":
        return "session_token"
    driver = str(detail.get("driver") or "").strip().lower()
    if driver in {"browser_fallback", "browser-fallback"}:
        return "browser_fallback"
    return None


def _raw_to_main(task_type: str, raw_stage: str, detail: dict[str, Any]) -> str | None:
    if raw_stage in {"queued", "complete", "interrupted", "cancelling"}:
        return "result" if raw_stage == "complete" else None
    if task_type == "password_setup":
        if raw_stage == "network":
            return "network"
        if raw_stage == "browser":
            return "browser"
        if raw_stage in {"login", "email_otp", "token", "mfa_challenge", "password_reset", "password_reset_otp"}:
            return "authenticate"
        if raw_stage == "login_password":
            return "set_password"
        return None
    if task_type == "twofa_setup":
        if raw_stage == "network":
            return "network"
        if raw_stage in {"twofa", "browser"}:
            return "set_twofa"
        return None
    if task_type in {"twofa_retry", "account_setup_retry"}:
        if raw_stage == "network":
            return "network"
        if raw_stage == "plan_check":
            return "plan_check"
        if raw_stage == "browser":
            return "browser"
        if raw_stage in {"login", "email_otp", "token", "mfa_challenge", "password_reset", "password_reset_otp"}:
            return "authenticate"
        if raw_stage == "login_password":
            return "set_password"
        if raw_stage == "twofa":
            return "set_twofa"
        return None
    if task_type in {"registration", "registration_resume"}:
        if raw_stage == "twofa":
            return "set_twofa"
        if raw_stage in {"login", "email_otp", "login_password", "auth_redirect", "submit_email"}:
            return "authenticate"
        if raw_stage == "token":
            return "token"
        if raw_stage == "codex" or raw_stage == "oauth":
            return "codex"
        if raw_stage == "complete":
            return "result"
        if raw_stage in {"network", "email", "browser", "profile", "plan_check"}:
            return raw_stage
        return None
    if task_type == "codex_retry":
        if raw_stage in {"network", "preflight", "browser", "auth_url", "phone_check", "consent", "callback"}:
            return "phone_verify" if raw_stage == "phone_check" else raw_stage
        if raw_stage in {"login", "email_otp", "phone_otp", "auth_redirect"}:
            return "authenticate"
        if raw_stage in {"credential_confirm", "credential_persist"}:
            return "credential"
        if raw_stage == "complete":
            return "result"
        return None
    if task_type == "account_completion":
        if raw_stage == "plan":
            return "plan"
        if raw_stage == "refresh_token":
            return "refresh_dispatch"
        if raw_stage == "codex":
            return "codex_dispatch"
        if raw_stage in {"login", "email_otp", "token", "login_password", "auth_redirect", "submit_email"}:
            return "authenticate" if raw_stage != "login_password" else "set_password"
        if raw_stage == "twofa":
            return "set_twofa"
        if raw_stage in {"network", "browser", "plan_check"}:
            return raw_stage
        if raw_stage == "complete":
            return "result"
        return None
    if task_type in {"live_check", "token_refresh", "codex_token_refresh", "plan_check", "deactivation_mail"}:
        if raw_stage == "access_token":
            return "access_token"
        if raw_stage == "refresh_token":
            return "refresh_token"
        if raw_stage == "login_password":
            return "authenticate" if task_type == "token_refresh" else "refresh_token"
        if raw_stage in {"login", "email_otp", "mfa_challenge", "reauth"}:
            return "authenticate"
        if raw_stage == "complete":
            return "result"
        if raw_stage in {"network", "plan_check", "mailbox_scan"}:
            return raw_stage
    return None


def _status_for_run(run: dict[str, Any]) -> tuple[str, str]:
    status = str(run.get("status") or "").strip().lower()
    if status == "success":
        return "success", "success"
    if status == "partial_success":
        return "success", "partial_success"
    if status in {"cancelled", "canceled"}:
        return "failed", "cancelled"
    if status in {"attention_required", "interrupted"}:
        return "failed", status
    if status in {"failed", "deactivated", "unsupported"}:
        return "failed", status
    if status in {"queued", "running", "stopping", "cancelling", "settling", "waiting"}:
        return "pending", status or "pending"
    return "pending", status or "pending"


def _set_state(item: dict[str, Any], state: str, *, reason: str | None = None) -> None:
    item["state"] = state
    item["display_status"] = state
    item["active"] = state == "running"
    if reason:
        item["reason"] = reason


def _add_observation(item: dict[str, Any], event: dict[str, Any], state: str, *, child_id: str | None = None) -> None:
    safe = {
        "event_id": event.get("id"),
        "state": state,
    }
    if child_id:
        safe["step_id"] = child_id
    item["attempts"].append(safe)
    if child_id:
        existing = next((child for child in item["children"] if child["step_id"] == child_id), None)
        if existing is None:
            existing = _child(child_id)
            item["children"].append(existing)
        _set_state(existing, state)
        existing["attempts"].append({"event_id": event.get("id"), "state": state})
    else:
        _set_state(item, state)


def _finalize_password_steps(steps: list[dict[str, Any]], observations: dict[str, list[tuple[dict[str, Any], str]]]) -> None:
    browser = next(item for item in steps if item["id"] == "browser")
    authenticate = next(item for item in steps if item["id"] == "authenticate")
    set_password = next(item for item in steps if item["id"] == "set_password")

    auth_events = observations.get("authenticate", [])
    password_events = observations.get("set_password", [])
    if auth_events:
        latest_auth_state = auth_events[-1][1]
        if password_events and password_events[-1][1] in {"running", "success"}:
            _set_state(authenticate, "success", reason="已进入密码设置步骤")
        elif latest_auth_state == "success":
            _set_state(authenticate, "success")
        elif latest_auth_state == "failed":
            _set_state(authenticate, "failed")
        else:
            _set_state(authenticate, "running")
    if password_events:
        _set_state(set_password, password_events[-1][1])
    if auth_events and browser["state"] == "running":
        _set_state(browser, "success", reason="已进入登录验证")


def _finalize_result(steps: list[dict[str, Any]], run: dict[str, Any], observations: dict[str, list[tuple[dict[str, Any], str]]]) -> dict[str, Any]:
    result = next(item for item in steps if item["id"] == "result")
    complete_events = observations.get("result", [])
    if complete_events:
        _set_state(result, complete_events[-1][1])
    else:
        state, display = _status_for_run(run)
        _set_state(result, state)
        result["display_status"] = display
    child_tasks = []
    for child in (run.get("result_summary") or {}).get("child_tasks") or []:
        if isinstance(child, dict):
            child_tasks.append({
                key: child.get(key)
                for key in ("task_id", "run_id", "status", "accepted", "busy")
                if child.get(key) is not None
            })
        elif isinstance(child, (int, str)):
            child_tasks.append({"task_id": child})
    return {
        "status": result["display_status"],
        "state": result["state"],
        "message": redact_text(run.get("message") or run.get("error_message") or "", 500),
        "child_tasks": child_tasks,
    }


def _close_running_evidence(steps: list[dict[str, Any]], outcome_state: str) -> None:
    if outcome_state not in {"success", "failed"}:
        return
    reason = "任务已结束"
    for item in steps:
        for child in item.get("children") or []:
            if child.get("state") == "running":
                _set_state(child, outcome_state, reason=reason)
        if item["id"] != "result" and item.get("state") == "running":
            _set_state(item, outcome_state, reason=reason)


def _current(steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in steps:
        for child in item.get("children") or []:
            if child.get("state") == "running":
                return {
                    "step_id": item["id"],
                    "child_step_id": child["step_id"],
                    "child_label": child["label"],
                    "label": child["label"],
                }
        if item.get("state") == "running":
            return {"step_id": item["id"], "child_step_id": None, "label": item["label"]}
    return None


def _revision_payload(steps: list[dict[str, Any]], run: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    relevant_events = []
    for event in events:
        state = _event_state(event)
        if state is None:
            continue
        detail = _event_detail(event)
        relevant_events.append({
            "id": event.get("id"),
            "stage": _raw_stage(event),
            "event_type": event.get("event_type"),
            "state": state,
            "step_id": detail.get("step_id"),
            "parent_step_id": detail.get("parent_step_id"),
            "branch_id": detail.get("branch_id"),
            "driver": detail.get("driver"),
            "browser_opened": detail.get("browser_opened"),
        })
    return {
        "steps": steps,
        "run": {
            "id": run.get("id"),
            "status": run.get("status"),
            "progress_stage": run.get("progress_stage"),
            "result_summary": run.get("result_summary") or {},
        },
        "events": relevant_events,
    }


def build_progress_snapshot(
    task_id: int,
    run_id: int,
    task_type: str,
    run: dict[str, Any] | None,
    events: Iterable[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Return an ordered, safe presentation snapshot for one operation Run."""
    run_value = dict(run or {})
    event_values = [dict(event) for event in (events or []) if isinstance(event, dict)]
    task_key = str(task_type or "").strip().lower()
    steps = _template(task_key, run_value)
    by_id = {item["id"]: item for item in steps}
    observations: dict[str, list[tuple[dict[str, Any], str]]] = {}
    explicit = False

    for event in event_values:
        state = _event_state(event)
        if state is None:
            continue
        raw_stage = _raw_stage(event)
        detail = _event_detail(event)
        if any(key in detail for key in ("step_id", "parent_step_id", "branch_id", "instance_id")):
            explicit = True
        main_id = _raw_to_main(task_key, raw_stage, detail)
        if main_id is None or main_id not in by_id:
            continue
        item = by_id[main_id]
        child_id = None
        if main_id in {"authenticate", "set_twofa", "credential", "refresh_dispatch", "codex_dispatch"}:
            child_id = _child_id(raw_stage, detail)
            if main_id == "set_twofa" and raw_stage == "twofa":
                driver = str(detail.get("driver") or "").strip().lower()
                child_id = "browser_fallback" if driver == "browser_fallback" else "protocol_attempt"
            if main_id == "set_twofa" and raw_stage == "twofa_result":
                child_id = "twofa_remote_confirm"
            if main_id == "set_password" and detail.get("checkpoint"):
                child_id = "password_checkpoint"
        _add_observation(item, event, state, child_id=child_id)
        observations.setdefault(main_id, []).append((event, state))

        if main_id == "set_twofa" and raw_stage == "browser":
            child_id = "browser_fallback"
            _add_observation(item, event, state, child_id=child_id)
        if main_id == "set_password" and detail.get("checkpoint"):
            child_id = "password_checkpoint"
            _add_observation(item, event, state, child_id=child_id)

    if task_key == "password_setup":
        _finalize_password_steps(steps, observations)
    elif task_key == "twofa_setup":
        set_twofa = by_id["set_twofa"]
        if not observations.get("set_twofa"):
            _set_state(set_twofa, "pending")
    elif task_key in {"twofa_retry", "account_setup_retry"}:
        browser = by_id.get("browser")
        auth = by_id.get("authenticate")
        if browser and observations.get("authenticate") and browser["state"] == "running":
            _set_state(browser, "success", reason="已进入登录验证")
        if auth and observations.get("set_password") and observations["set_password"][-1][1] in {"running", "success"}:
            _set_state(auth, "success", reason="已进入账号配置步骤")

    outcome = _finalize_result(steps, run_value, observations)
    _close_running_evidence(steps, outcome["state"])
    source = "explicit" if explicit else "legacy_derived" if any(_event_state(event) for event in event_values) else "insufficient_evidence"
    payload = _revision_payload(steps, run_value, event_values)
    revision = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return {
        "task_id": int(task_id),
        "run_id": int(run_id),
        "flow_version": 1,
        "revision": revision,
        "source": source,
        "main_steps": steps,
        "current": _current(steps),
        "outcome": outcome,
    }
