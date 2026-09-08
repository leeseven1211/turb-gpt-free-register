# -*- coding: utf-8 -*-
from core.task_progress import build_progress_snapshot
from core.task_stages import flow_for


def _event(event_id, stage, state=None, *, message="", detail=None):
    payload = dict(detail or {})
    if state is not None:
        payload.setdefault("step_state", state)
    return {
        "id": event_id,
        "stage": stage,
        "event_type": f"stage.{state}" if state else "note.info",
        "message": message,
        "detail": payload,
    }


def _run(status="running", *, progress_stage=""):
    return {
        "id": 44422,
        "status": status,
        "progress_stage": progress_stage,
        "result_summary": {},
    }


def test_password_setup_keeps_auth_events_before_result():
    events = [
        _event(1, "queued", message="任务已入队"),
        _event(2, "network", "success", message="线路已就绪"),
        _event(3, "browser", "running", message="启动浏览器"),
        _event(4, "login", "running", message="打开 OpenAI 登录授权页"),
        _event(5, "login", "success", message="已提交 OpenAI 登录邮箱"),
        _event(6, "email_otp", "running", message="等待邮箱验证码"),
        _event(7, "token", "success", message="已取得登录 Token"),
        _event(8, "login_password", "running", message="开始设置账号密码"),
    ]

    snapshot = build_progress_snapshot(
        44430, 44422, "password_setup", _run(progress_stage="login_password"), events,
    )

    assert [item["id"] for item in snapshot["main_steps"]] == [
        "network", "browser", "authenticate", "set_password", "result",
    ]
    assert snapshot["main_steps"][-1]["id"] == "result"
    assert snapshot["current"]["step_id"] == "authenticate"
    assert snapshot["current"]["child_step_id"] == "email_otp"
    assert snapshot["main_steps"][1]["state"] == "success"


def test_unknown_event_does_not_append_after_result():
    events = [
        _event(1, "complete", "success", message="任务完成"),
        _event(2, "login", message="诊断日志：登录页面已打开"),
    ]

    snapshot = build_progress_snapshot(
        99, 100, "password_setup", _run("success"), events,
    )

    assert snapshot["main_steps"][-1]["id"] == "result"
    assert all(item["id"] != "login" for item in snapshot["main_steps"])
    assert snapshot["outcome"]["status"] == "success"


def test_protocol_twofa_omits_browser_and_browser_fallback_is_nested():
    direct_events = [
        _event(1, "network", "success"),
        _event(2, "twofa", "running", detail={"driver": "protocol", "browser_opened": False}),
        _event(3, "twofa_result", "success", detail={"driver": "protocol", "browser_opened": False}),
    ]
    fallback_events = [
        _event(1, "network", "success"),
        _event(2, "twofa", "running", detail={"driver": "protocol"}),
        _event(3, "twofa", "failed", detail={"driver": "protocol", "browser_fallback_enabled": True}),
        _event(4, "twofa", "running", detail={"driver": "browser_fallback"}),
        _event(5, "browser", "running", detail={"driver": "browser_fallback"}),
    ]

    direct = build_progress_snapshot(
        1, 2, "twofa_setup", _run("success"), direct_events,
    )
    fallback = build_progress_snapshot(
        3, 4, "twofa_setup", _run(), fallback_events,
    )

    assert [item["id"] for item in direct["main_steps"]] == [
        "network", "set_twofa", "result",
    ]
    assert [item["id"] for item in fallback["main_steps"]] == [
        "network", "set_twofa", "result",
    ]
    assert any(child["step_id"] == "browser_fallback" for child in fallback["main_steps"][1]["children"])


def test_account_setup_only_shows_requested_plan_check_path():
    events = [
        _event(1, "network", "success"),
        _event(2, "plan_check", "running"),
    ]
    run = _run(progress_stage="plan_check")
    run["result_summary"] = {"planned_steps": ["plan_check"]}

    snapshot = build_progress_snapshot(5, 6, "account_setup_retry", run, events)

    assert [item["id"] for item in snapshot["main_steps"]] == [
        "network", "plan_check", "result",
    ]
    assert snapshot["current"]["step_id"] == "plan_check"


def test_account_completion_keeps_deferred_refresh_as_submission_result():
    events = [
        _event(1, "plan", "success"),
        _event(2, "refresh_token", "success", detail={"dispatch": True}),
    ]
    run = _run("partial_success")
    run["result_summary"] = {
        "planned_steps": ["refresh_at"],
        "awaiting_steps": ["refresh_at"],
    }

    snapshot = build_progress_snapshot(7, 8, "account_completion", run, events)

    assert [item["id"] for item in snapshot["main_steps"]] == [
        "plan", "refresh_dispatch", "result",
    ]
    assert snapshot["outcome"]["status"] == "partial_success"


def test_terminal_run_closes_running_checkpoint_before_selecting_current():
    events = [
        _event(1, "network", "success"),
        _event(2, "browser", "running"),
        _event(3, "login", "success"),
        _event(4, "token", "success"),
        _event(5, "login_password", "running", detail={"checkpoint": True}),
        _event(6, "login_password", "success"),
        _event(7, "browser", "success"),
        _event(8, "complete", "success"),
    ]

    snapshot = build_progress_snapshot(
        11, 12, "password_setup", _run("success", progress_stage="complete"), events,
    )

    assert snapshot["current"] is None
    password = next(item for item in snapshot["main_steps"] if item["id"] == "set_password")
    checkpoint = next(child for child in password["children"] if child["step_id"] == "password_checkpoint")
    assert checkpoint["state"] == "success"


def test_legacy_flow_metadata_uses_real_top_level_order():
    assert [item["key"] for item in flow_for("account_setup_retry")] == [
        "network", "plan_check", "browser", "login_password", "twofa", "complete",
    ]
    assert [item["key"] for item in flow_for("twofa_setup")] == [
        "network", "twofa", "complete",
    ]
