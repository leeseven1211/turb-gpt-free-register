# -*- coding: utf-8 -*-
from core.task_progress import build_progress_snapshot
from core.task_stages import flow_for


TASK_TYPES = [
    "registration", "registration_resume", "codex_retry", "twofa_retry",
    "account_setup_retry", "password_setup", "password_change", "twofa_setup",
    "twofa_change", "account_completion", "live_check", "token_refresh",
    "codex_token_refresh", "plan_check", "deactivation_mail", "extract_link",
    "email_change",
]


def _event(event_id, stage, state=None, *, message="", detail=None, created_at=None):
    payload = dict(detail or {})
    if state is not None:
        payload.setdefault("step_state", state)
    return {
        "id": event_id, "stage": stage,
        "event_type": f"stage.{state}" if state else "note.info",
        "message": message, "created_at": created_at, "detail": payload,
    }


def _run(status="running", *, progress_stage="", **extra):
    value = {"id": 44422, "status": status, "progress_stage": progress_stage, "result_summary": {}}
    value.update(extra)
    return value


def _step(snapshot, step_id):
    return next(item for item in snapshot["main_steps"] if item["id"] == step_id)


def test_debug_pause_preserves_execution_facts_and_only_marks_current_running_steps():
    events = [
        _event(1, "page", "running", created_at="2026-10-13T10:00:00Z"),
        _event(2, "page", "success", created_at="2026-10-13T10:00:10Z"),
        _event(3, "submit_email", "running", created_at="2026-10-13T10:00:12Z"),
    ]
    pause = {"state": "paused", "paused_at": "2026-10-13T10:00:30Z", "hold_until": "2026-10-13T10:30:30Z", "reason": "不可投影"}
    run = _run(debug_pause=pause)
    snapshot = build_progress_snapshot(1, 2, "registration_resume", run, events)
    auth = _step(snapshot, "authenticate")
    assert run["status"] == "running"
    assert auth["state"] == "running"
    assert auth["display_status"] == "debug_paused"
    assert auth["completed_at"] is None
    assert auth["duration_ms"] is None
    assert [(child["id"], child["display_status"]) for child in auth["children"]] == [("page", "success"), ("submit_email", "debug_paused")]
    assert _step(snapshot, "profile")["display_status"] == "pending"
    assert _step(snapshot, "result")["display_status"] == "pending"
    assert "reason" not in snapshot["debug_pause"]
    assert snapshot["debug_pause"]["paused_at"] == pause["paused_at"]
    resumed = build_progress_snapshot(1, 2, "registration_resume", _run(), events)
    assert _step(resumed, "authenticate")["display_status"] == "running"
    assert snapshot["revision"] != resumed["revision"]
    assert "debug_pause" not in resumed


def test_debug_pause_does_not_override_failed_steps_or_invent_missing_time():
    events = [_event(1, "login_password", "failed", created_at="2026-10-13T10:00:00Z")]
    snapshot = build_progress_snapshot(1, 2, "registration", _run(debug_pause={"state": "paused", "hold_until": "2026-10-13T10:30:00Z"}), events)
    auth = _step(snapshot, "authenticate")
    assert auth["state"] == auth["display_status"] == "failed"
    assert auth["children"][0]["display_status"] == "failed"
    assert snapshot["debug_pause"]["paused_at"] is None
    terminal = build_progress_snapshot(1, 2, "registration", _run("failed", debug_pause={"state": "paused"}), events)
    assert "debug_pause" not in terminal


def test_result_waits_for_its_own_event_while_run_is_active():
    for status in ("queued", "running", "waiting", "settling", "stopping"):
        snapshot = build_progress_snapshot(1, 2, "registration", _run(status), [_event(1, "login", "running")])
        assert _step(snapshot, "result")["display_status"] == "pending"
        assert not _step(snapshot, "result")["active"]
        assert snapshot["outcome"]["status"] == status
    snapshot = build_progress_snapshot(1, 2, "registration", _run(), [_event(1, "complete", "running")])
    assert _step(snapshot, "result")["display_status"] == "running"


def test_registration_disabled_branches_are_skipped_before_execution():
    for task_type in ("registration", "registration_resume"):
        for status in ("queued", "running", "success", "failed"):
            run = _run(status, data={"config_snapshot": {
                "codex_enabled": False, "twofa_enabled": False, "plan_check_enabled": False,
            }})
            snapshot = build_progress_snapshot(1, 2, task_type, run, [])
            for step_id in ("codex", "set_twofa", "plan_check"):
                step = _step(snapshot, step_id)
                assert step["display_status"] == "skipped"
                assert step["evidence"] == "config_snapshot"
                assert not step["event_ids"] and step["started_at"] is None


def test_registration_config_does_not_hide_observed_or_unknown_branches():
    for state in ("running", "success", "failed", None):
        snapshot = build_progress_snapshot(1, 2, "registration", _run(data={"config_snapshot": {"codex_enabled": False}}), [_event(1, "codex", state)])
        assert _step(snapshot, "codex")["display_status"] != "skipped"
    for config in ({}, {"codex_enabled": True}, {"codex_enabled": None}):
        snapshot = build_progress_snapshot(1, 2, "registration", _run(data={"config_snapshot": config}), [])
        assert _step(snapshot, "codex")["display_status"] == "pending"


def test_all_task_types_share_v2_template_and_result_tail():
    for task_type in TASK_TYPES:
        flow = flow_for(task_type)
        snapshot = build_progress_snapshot(1, 2, task_type, _run(), [])
        assert flow and flow[-1]["id"] == "result"
        assert snapshot["flow_version"] == 2
        assert snapshot["main_steps"][-1]["id"] == "result"


def test_observed_order_event_ids_and_children_are_retained():
    events = [
        _event("n", "network", "success", created_at="2026-01-01T00:00:00Z"),
        _event("b", "browser", "running", created_at="2026-01-01T00:00:01Z"),
        _event("l", "login", "success", created_at="2026-01-01T00:00:02Z"),
        _event("o", "email_otp", "running", message="等待验证码", created_at="2026-01-01T00:00:03Z"),
        _event("p", "login_password", "running", created_at="2026-01-01T00:00:04Z"),
    ]
    snapshot = build_progress_snapshot(44430, 44422, "password_setup", _run(progress_stage="login_password"), events)
    assert [item["id"] for item in snapshot["main_steps"]] == ["network", "browser", "authenticate", "set_password", "result"]
    assert _step(snapshot, "browser")["event_ids"] == ["b"]
    assert _step(snapshot, "set_password")["last_event_id"] == "p"
    assert _step(snapshot, "authenticate")["children"][0]["id"] == "login"
    assert _step(snapshot, "authenticate")["children"][1]["id"] == "email_otp"
    assert snapshot["current"]["child_step_id"] == "login_password"
    assert _step(snapshot, "set_password")["started_at"] == "2026-01-01T00:00:04Z"


def test_unknown_explicit_stage_is_inserted_before_result():
    snapshot = build_progress_snapshot(99, 100, "password_setup", _run("running"), [_event("u1", "new_executor_stage", "running"), _event("u2", "new_executor_stage", "success")])
    assert snapshot["main_steps"][-1]["id"] == "result"
    unknown = snapshot["main_steps"][0]
    assert unknown["id"] == "unknown:new_executor_stage"
    assert unknown["raw_stages"] == ["new_executor_stage"]
    assert unknown["event_ids"] == ["u1", "u2"]
    assert snapshot["source"] == "explicit"


def test_twofa_protocol_and_browser_fallback_preserve_attempts():
    events = [
        _event("1", "network", "success"),
        _event("2", "twofa", "running", detail={"driver": "protocol"}),
        _event("3", "twofa", "failed", detail={"driver": "protocol"}),
        _event("4", "twofa", "running", detail={"driver": "browser_fallback"}),
        _event("5", "browser", "running", detail={"driver": "browser_fallback"}),
    ]
    snapshot = build_progress_snapshot(3, 4, "twofa_setup", _run(), events)
    step = _step(snapshot, "set_twofa")
    assert {child["id"] for child in step["children"]} == {"protocol_attempt", "browser_fallback"}
    assert len(step["attempts"]) == 4
    assert snapshot["current"]["step_id"] == "set_twofa"


def test_plan_subset_and_actual_order_do_not_add_unplanned_steps():
    run = _run(progress_stage="plan_check")
    run["result_summary"] = {"planned_steps": ["plan_check"]}
    snapshot = build_progress_snapshot(5, 6, "account_setup_retry", run, [_event("1", "plan_check", "running"), _event("2", "browser", "running")])
    # browser is an explicit late stage and therefore survives the narrow plan
    assert [item["id"] for item in snapshot["main_steps"]][-1] == "result"
    assert snapshot["current"]["step_id"] == "unknown:browser"
    assert "plan_check" in [item["id"] for item in snapshot["main_steps"]]


def test_terminal_success_does_not_mass_close_running_stage():
    events = [_event("1", "network", "success"), _event("2", "browser", "running")]
    snapshot = build_progress_snapshot(11, 12, "password_setup", _run("success", progress_stage="browser"), events)
    browser = _step(snapshot, "browser")
    assert browser["state"] == "pending"
    assert browser["display_status"] == "unconfirmed"
    assert browser["evidence"] == "unconfirmed"
    assert snapshot["current"] is None
    assert snapshot["outcome"]["status"] == "success"


def test_run_status_remains_authoritative_over_complete_event():
    snapshot = build_progress_snapshot(11, 12, "password_setup", _run("request_unknown"), [_event("1", "complete", "success")])
    assert snapshot["outcome"]["status"] == "request_unknown"
    assert snapshot["outcome"]["state"] == "pending"
    assert snapshot["current"] is None


def test_route_projection_keeps_old_route_failure_out_of_current_run_step():
    run = _run("running", route_attempt_no=2, duration_ms=12000)
    events = [
        _event("old-network", "network", "failed", message="旧线路不可用", detail={"route_attempt_no": 1, "started_at": "2026-10-13T01:00:00Z", "completed_at": "2026-10-13T01:00:04Z"}),
        _event("old-login", "login", "failed", message="旧线路登录失败", detail={"route_attempt_no": 1, "started_at": "2026-10-13T01:00:04Z", "completed_at": "2026-10-13T01:00:05Z"}),
        _event("current-network", "network", "running", detail={"route_attempt_no": 2, "started_at": "2026-10-13T01:00:10Z"}),
    ]
    snapshot = build_progress_snapshot(1, 2, "registration", run, events)
    assert snapshot["selected_route_attempt_no"] == 2
    assert _step(snapshot, "network")["state"] == "running"
    assert snapshot["failure"] is None
    assert {route["route_attempt_no"] for route in snapshot["routes"]} == {1, 2}
    assert next(route for route in snapshot["routes"] if route["route_attempt_no"] == 1)["failure"]["step_id"] == "authenticate"
    assert snapshot["time_basis"]["run_duration_ms"] == 12000


def test_projection_ignores_event_from_another_run_even_when_route_matches():
    run = _run("running", route_attempt_no=2)
    events = [
        _event("foreign", "network", "failed", detail={"route_attempt_no": 2}),
        {**_event("current", "network", "running", detail={"route_attempt_no": 2}), "run_id": 2},
    ]
    events[0]["run_id"] = 99
    snapshot = build_progress_snapshot(1, 2, "registration", run, events)
    assert _step(snapshot, "network")["state"] == "running"
    assert _step(snapshot, "network")["event_ids"] == ["current"]


def test_late_old_route_event_cannot_change_current_route_duration_or_state():
    run = _run("running", route_attempt_no=2)
    events = [
        _event("current-start", "login", "running", detail={"route_attempt_no": 2, "started_at": "2026-10-13T02:00:00Z"}),
        _event("old-late", "login", "failed", created_at="2026-10-13T01:00:00Z", detail={"route_attempt_no": 1, "started_at": "2026-10-13T00:59:00Z", "completed_at": "2026-10-13T01:00:00Z"}),
    ]
    snapshot = build_progress_snapshot(1, 2, "registration", run, events)
    login = _step(snapshot, "authenticate")
    assert login["state"] == "running"
    assert login["started_at"] == "2026-10-13T02:00:00Z"
    assert login["event_ids"] == ["current-start"]


def test_explicit_step_instances_are_retained_under_selected_route():
    run = _run("running", route_attempt_no=2)
    events = [
        _event("instance-a-start", "login", "running", detail={"route_attempt_no": 2, "step_instance_id": "a", "started_at": "2026-10-13T03:00:00Z"}),
        _event("instance-a-end", "login", "failed", detail={"route_attempt_no": 2, "step_instance_id": "a", "completed_at": "2026-10-13T03:00:01Z"}),
        _event("instance-b-start", "login", "running", detail={"route_attempt_no": 2, "step_instance_id": "b", "started_at": "2026-10-13T03:00:03Z"}),
    ]
    snapshot = build_progress_snapshot(1, 2, "registration", run, events)
    login = _step(snapshot, "authenticate")
    assert [item["step_instance_id"] for item in login["step_instances"]] == ["a", "b"]
    assert login["step_instances"][0]["state"] == "failed"
    assert login["step_instances"][1]["state"] == "running"


def test_late_running_same_step_instance_does_not_reopen_completed_projection():
    run = _run("running", route_attempt_no=2)
    events = [
        _event("network-start", "network", "running", detail={
            "route_attempt_no": 2, "step_instance_id": "network-a",
            "started_at": "2026-10-13T03:00:00Z",
        }),
        _event("network-end", "network", "success", detail={
            "route_attempt_no": 2, "step_instance_id": "network-a",
            "started_at": "2026-10-13T03:00:00Z",
            "completed_at": "2026-10-13T03:00:01Z",
        }),
        _event("network-late", "network", "running", detail={
            "route_attempt_no": 2, "step_instance_id": "network-a",
            "started_at": "2026-10-13T03:00:03Z",
        }),
    ]
    network = _step(build_progress_snapshot(1, 2, "registration", run, events), "network")
    assert network["state"] == "success"
    assert network["completed_at"] == "2026-10-13T03:00:01Z"
    assert network["duration_ms"] == 1000
    assert network["step_instances"][0]["state"] == "success"
    assert network["step_instances"][0]["completed_at"] == "2026-10-13T03:00:01Z"
    assert network["step_instances"][0]["duration_ms"] == 1000
    assert set(network["step_instances"][0]["event_ids"]) == {"network-start", "network-end", "network-late"}


def test_unmarked_late_event_is_history_unknown_when_run_and_route_are_known():
    run = _run("running", route_attempt_no=2)
    events = [
        {**_event("current", "login", "running", detail={"route_attempt_no": 2}), "run_id": 2},
        _event("late-unknown", "login", "failed", detail={"message": "旧回调"}),
    ]
    snapshot = build_progress_snapshot(1, 2, "registration", run, events)
    login = _step(snapshot, "authenticate")
    assert login["state"] == "running"
    assert login["event_ids"] == ["current"]
    assert snapshot["history_unknown"][0]["event_id"] == "late-unknown"
    assert snapshot["history_unknown"][0]["reason"] in {"事件缺少 Run 归属", "事件缺少线路归属"}


def test_known_run_job_level_prepare_event_can_precede_route_assignment():
    run = _run("running", route_attempt_no=2)
    events = [
        {**_event("prepare", "network", "running", detail={"job_level": True}), "run_id": 2},
        {**_event("route", "network", "success", detail={"route_attempt_no": 2}), "run_id": 2},
    ]
    snapshot = build_progress_snapshot(1, 2, "registration", run, events)
    network = _step(snapshot, "network")
    assert network["state"] == "success"
    assert "prepare" in network["event_ids"]
    assert not snapshot.get("history_unknown")


def test_current_authenticate_time_uses_each_child_instance_union():
    run = _run("running", route_attempt_no=2)
    events = [
        _event("login-start", "login", "running", detail={"route_attempt_no": 2, "step_instance_id": "login-a", "started_at": "2026-10-13T03:00:00Z"}),
        _event("login-end", "login", "success", detail={"route_attempt_no": 2, "step_instance_id": "login-a", "completed_at": "2026-10-13T03:00:01Z"}),
        _event("otp-start", "email_otp", "running", detail={"route_attempt_no": 2, "step_instance_id": "otp-a", "started_at": "2026-10-13T03:00:02Z"}),
        _event("otp-end", "email_otp", "success", detail={"route_attempt_no": 2, "step_instance_id": "otp-a", "completed_at": "2026-10-13T03:00:03Z"}),
    ]
    authenticate = _step(build_progress_snapshot(1, 2, "registration", run, events), "authenticate")
    assert authenticate["state"] == "success"
    assert authenticate["started_at"] == "2026-10-13T03:00:00Z"
    assert authenticate["completed_at"] == "2026-10-13T03:00:03Z"
    assert authenticate["duration_ms"] == 3000


def test_registration_page_completion_keeps_authentication_open_and_its_own_duration():
    for task_type in ("registration", "registration_resume"):
        events = [
            _event("page-start", "page", "running", created_at="2026-10-13T08:48:18Z", detail={
                "step_instance_id": "page-a", "started_at": "2026-10-13T08:48:18Z",
            }),
            _event("page-end", "page", "success", created_at="2026-10-13T08:49:09Z", detail={
                "step_instance_id": "page-a", "started_at": "2026-10-13T08:48:18Z",
                "completed_at": "2026-10-13T08:49:09Z",
            }),
        ]
        auth = _step(build_progress_snapshot(1, 2, task_type, _run(), events), "authenticate")
        assert auth["state"] == "running"
        assert auth["completed_at"] is None
        assert auth["children"][0]["state"] == "success"
        assert auth["children"][0]["duration_ms"] == 51000
        assert auth["attempts"][1]["created_at"] == "2026-10-13T08:49:09Z"
        assert auth["attempts"][1]["started_at"] == "2026-10-13T08:48:18Z"
        assert auth["attempts"][1]["raw_stage_label"] == "打开页面"

        events.append(_event("email-start", "submit_email", "running", created_at="2026-10-13T08:49:09Z", detail={
            "step_instance_id": "email-a", "started_at": "2026-10-13T08:49:09Z",
        }))
        auth = _step(build_progress_snapshot(1, 2, task_type, _run(), events), "authenticate")
        assert [child["id"] for child in auth["children"]] == ["page", "submit_email"]
        assert auth["started_at"] == "2026-10-13T08:48:18Z"
        assert auth["children"][0]["duration_ms"] == 51000
        assert auth["children"][1]["started_at"] == "2026-10-13T08:49:09Z"
        assert auth["children"][1]["completed_at"] is None


def test_registration_authentication_children_finish_only_after_confirmed_verification():
    for explicit_instances in (True, False):
        events = []
        for index, raw_stage in enumerate(("page", "submit_email", "auth_redirect", "login_password", "email_otp")):
            start = f"2026-10-13T09:00:{index * 2:02d}Z"
            end = f"2026-10-13T09:00:{index * 2 + 1:02d}Z"
            detail = {"started_at": start, "completed_at": end}
            if explicit_instances:
                detail["step_instance_id"] = raw_stage + "-a"
            events.append(_event(raw_stage, raw_stage, "success", created_at=end, detail=detail))
            auth = _step(build_progress_snapshot(1, 2, "registration", _run(), events), "authenticate")
            assert auth["state"] == ("success" if raw_stage == "email_otp" else "running")
        assert [child["id"] for child in auth["children"]] == ["page", "submit_email", "auth_redirect", "login_password", "email_otp"]
        assert all(child["duration_ms"] == 1000 for child in auth["children"])
        assert auth["duration_ms"] == 9000
        assert auth["started_at"] == "2026-10-13T09:00:00Z"
        assert auth["completed_at"] == "2026-10-13T09:00:09Z"


def test_registration_redirect_cannot_be_hidden_by_completed_password_child():
    events = [
        _event("password-end", "login_password", "success", detail={
            "step_instance_id": "password-a", "started_at": "2026-10-13T09:00:00Z",
            "completed_at": "2026-10-13T09:00:01Z",
        }),
        _event("redirect-start", "auth_redirect", "running", detail={
            "step_instance_id": "redirect-a", "started_at": "2026-10-13T09:00:02Z",
        }),
    ]
    auth = _step(build_progress_snapshot(1, 2, "registration", _run(), events), "authenticate")
    assert auth["state"] == "running"
    assert auth["completed_at"] is None
    assert [(child["id"], child["state"]) for child in auth["children"]] == [
        ("login_password", "success"), ("auth_redirect", "running"),
    ]


def test_registration_later_phase_start_cannot_confirm_authentication():
    events = [
        _event("password-end", "login_password", "success", created_at="2026-10-13T09:00:01Z"),
        _event("profile-start", "profile", "running", created_at="2026-10-13T09:00:02Z"),
    ]
    auth = _step(build_progress_snapshot(1, 2, "registration", _run(), events), "authenticate")
    assert auth["state"] == "running"
    events.append(_event("token-confirmed", "token", "success", created_at="2026-10-13T09:00:03Z"))
    auth = _step(build_progress_snapshot(1, 2, "registration", _run(), events), "authenticate")
    assert auth["state"] == "success"
    assert auth["completed_at"] == "2026-10-13T09:00:03Z"
    assert auth["reason"] == "已取得登录会话，身份验证已确认"


def test_registration_confirmed_otp_duration_stays_closed_when_token_arrives():
    events = [
        _event("page", "page", "success", detail={
            "step_instance_id": "page-a", "started_at": "2026-10-13T09:23:57Z",
            "completed_at": "2026-10-13T09:24:20Z",
        }),
        _event("otp", "email_otp", "success", detail={
            "step_instance_id": "otp-a", "started_at": "2026-10-13T09:25:54Z",
            "completed_at": "2026-10-13T09:26:23Z",
        }),
    ]
    before = _step(build_progress_snapshot(1, 2, "registration", _run(), events), "authenticate")
    events.append(_event("token", "token", "success", created_at="2026-10-13T09:26:55Z"))
    after = _step(build_progress_snapshot(1, 2, "registration", _run("success"), events), "authenticate")
    for auth in (before, after):
        assert auth["state"] == "success"
        assert auth["completed_at"] == "2026-10-13T09:26:23Z"
        assert auth["duration_ms"] == 146000
        assert auth["reason"] is None


def test_registration_late_running_does_not_reopen_confirmed_authentication():
    events = [
        _event("otp-start", "email_otp", "running", created_at="2026-10-13T09:25:54Z", detail={
            "step_instance_id": "otp-a", "started_at": "2026-10-13T09:25:54Z",
        }),
        _event("otp-end", "email_otp", "success", created_at="2026-10-13T09:26:23Z", detail={
            "step_instance_id": "otp-a", "started_at": "2026-10-13T09:25:54Z",
            "completed_at": "2026-10-13T09:26:23Z",
        }),
        _event("otp-late", "email_otp", "running", created_at="2026-10-13T09:26:25Z", detail={
            "step_instance_id": "otp-a", "started_at": "2026-10-13T09:26:25Z",
        }),
    ]
    for task_type in ("registration", "registration_resume"):
        snapshot = build_progress_snapshot(1, 2, task_type, _run(), events)
        auth = _step(snapshot, "authenticate")
        assert auth["state"] == "success"
        assert auth["completed_at"] == "2026-10-13T09:26:23Z"
        assert auth["duration_ms"] == 29000
        assert len(auth["attempts"]) == 3
        assert auth["last_event_id"] == "otp-end"
        assert snapshot["current"]["state"] == "success"
        new_instance = _event("otp-reentry", "email_otp", "running", created_at="2026-10-13T09:26:30Z", detail={
            "step_instance_id": "otp-b", "started_at": "2026-10-13T09:26:30Z",
        })
        reopened = _step(build_progress_snapshot(1, 2, task_type, _run(), [*events, new_instance]), "authenticate")
        assert reopened["state"] == "running"
        assert reopened["completed_at"] is None


def test_unknown_legacy_event_time_does_not_fall_back_to_stage_start():
    event = _event("old-running", "submit_email", "running", detail={
        "started_at": "2026-10-13T09:24:23Z", "event_time_known": False,
    })
    for run, events in (
        (_run(), [event]),
        (_run(progress_steps={"submit_email": {"state": "running", "started_at": "2026-10-13T09:24:23Z"}}), []),
        (_run(progress_steps={"submit_email": {
            "state": "pending", "evidence": "unconfirmed", "started_at": "2026-10-13T09:24:23Z",
            "occurred_at": "2026-10-13T09:24:53Z",
        }}), []),
    ):
        auth = _step(build_progress_snapshot(1, 2, "registration", run, events), "authenticate")
        assert auth["started_at"] == "2026-10-13T09:24:23Z"
        assert auth["attempts"][0]["created_at"] is None
        assert auth["attempts"][0]["event_time_known"] is False


def test_same_route_authenticate_reentry_closes_parent_only_for_current_children():
    run = _run("running", route_attempt_no=2)
    events = [
        _event("login-old", "login", "success", detail={"route_attempt_no": 2, "step_instance_id": "login-old", "started_at": "2026-10-13T03:00:00Z", "completed_at": "2026-10-13T03:00:01Z"}),
        _event("otp-current", "email_otp", "success", detail={"route_attempt_no": 2, "step_instance_id": "otp-current", "started_at": "2026-10-13T03:00:01Z", "completed_at": "2026-10-13T03:00:02Z"}),
        _event("login-new", "login", "running", detail={"route_attempt_no": 2, "step_instance_id": "login-new", "started_at": "2026-10-13T03:00:03Z"}),
    ]
    authenticate = _step(build_progress_snapshot(1, 2, "registration", run, events), "authenticate")
    login = next(child for child in authenticate["children"] if child["id"] == "login")
    assert authenticate["state"] == "running"
    assert authenticate["completed_at"] is None
    assert [item["step_instance_id"] for item in login["step_instances"]] == ["login-old", "login-new"]
    assert login["state"] == "running"


def test_legacy_progress_steps_preserve_evidence_without_events():
    run = _run("running")
    run["progress_steps"] = {
        "network": {"state": "success", "evidence": "explicit"},
        "browser": {"state": "pending", "evidence": "not_executed"},
    }
    snapshot = build_progress_snapshot(1, 2, "password_setup", run, [])
    assert _step(snapshot, "network")["evidence"] == "explicit"
    assert _step(snapshot, "browser")["evidence"] == "not_executed"


def test_failure_prefers_unrecovered_event_and_classifies_unknown_reconcile():
    events = [
        _event("1", "network", "failed", message="线路失败"),
        _event("2", "network", "success"),
        _event("3", "login", "failed", message="远端请求结果待确认"),
    ]
    snapshot = build_progress_snapshot(1, 2, "password_setup", _run("request_unknown", progress_stage="login", result_summary={"outcome": "request_unknown", "error_code": "request_unknown"}), events)
    assert snapshot["failure"]["event_id"] == "3"
    assert snapshot["failure"]["evidence"] == "explicit"
    assert snapshot["failure"]["reconcile_required"] is True
    assert snapshot["failure"]["error_info"]["error_code"] == "request_unknown"


def test_failed_run_without_failed_event_uses_inferred_last_activity():
    snapshot = build_progress_snapshot(1, 2, "plan_check", _run("failed", progress_stage="plan_check", message="执行结束但阶段记录不足"), [_event("1", "preflight", "running")])
    assert snapshot["failure"]["evidence"] == "inferred"
    assert snapshot["failure"]["event_id"] is None or snapshot["failure"]["event_id"] == "1"
    assert snapshot["failure"]["step_id"] in {"preflight", "result"}


def test_flow_for_exposes_stable_business_ids_and_raw_stage_projection():
    flow = flow_for("account_setup_retry")
    assert [item["id"] for item in flow] == ["network", "plan_check", "browser", "authenticate", "set_password", "set_twofa", "result"]
    assert flow[-1]["key"] == "complete"
    assert flow[-1]["id"] == "result"
    assert "login_password" in next(item for item in flow if item["id"] == "set_password")["raw_stages"]


def test_special_terminal_states_close_unfinished_children_without_success():
    for status in ('unknown', 'deactivated', 'unsupported', 'cancelled'):
        snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run(status), [_event(1, 'email_otp', 'running')])
        assert snapshot['current'] is None
        assert _step(snapshot, 'authenticate')['state'] == 'pending'
        assert _step(snapshot, 'authenticate')['children'][0]['state'] == 'pending'
        assert snapshot['outcome']['status'] == status


def test_child_failure_keeps_child_location_under_parent_dispatch():
    child = {'task_id': 3, 'run_id': 4, 'task_type': 'account_setup_retry', 'status': 'failed', 'failure_stage': 'email_otp', 'failure_event_id': 9, 'error_code': 'email_otp_timeout', 'error_message': '邮箱验证码超时'}
    snapshot = build_progress_snapshot(1, 2, 'account_completion', _run('partial_success', result_summary={'child_tasks': [child]}), [])
    assert snapshot['failure']['step_id'] == 'account_setup_dispatch'
    assert snapshot['failure']['stage'] == 'email_otp'
    assert snapshot['failure']['child_task_id'] == 3
    assert snapshot['outcome']['child_tasks'][0]['failure_event_id'] == 9
    single = build_progress_snapshot(1, 2, 'account_completion', _run('partial_success', result_summary={'child_result': child, 'child_status': 'failed'}), [])
    assert single['failure']['child_run_id'] == 4


def test_normalized_event_keeps_original_stage_and_database_id():
    event = _event(7, 'credential', 'success', detail={'raw_stage': 'credential_persist'})
    event['event_uuid'] = 'different-uuid'
    snapshot = build_progress_snapshot(1, 2, 'codex_retry', _run('success'), [event])
    step = _step(snapshot, 'credential')
    assert step['children'][0]['id'] == 'credential_persist'
    assert step['event_ids'] == ['7']
    assert step['reason'] is None


def test_legacy_node_order_uses_start_time_not_completion_time():
    events = [_event(1, 'login', 'success', created_at='2026-01-01T00:00:02Z'), _event(2, 'browser', 'success', detail={'started_at': '2026-01-01T00:00:01Z'}, created_at='2026-01-01T00:00:05Z')]
    snapshot = build_progress_snapshot(1, 2, 'codex_retry', _run('success'), events)
    assert [step['id'] for step in snapshot['main_steps']][:2] == ['browser', 'authenticate']


def test_fallback_success_recovers_business_failure_without_masking_login_failure():
    snapshot = build_progress_snapshot(1, 2, 'twofa_setup', _run('success'), [_event(1, 'twofa', 'failed', detail={'driver': 'protocol'}), _event(2, 'twofa', 'success', detail={'driver': 'browser_fallback'})])
    assert snapshot['failure'] is None
    assert _step(snapshot, 'set_twofa')['state'] == 'success'
    assert _step(snapshot, 'set_twofa')['children'][0]['display_status'] == 'recovered'
    auth = build_progress_snapshot(1, 2, 'codex_retry', _run('failed'), [_event(1, 'email_otp', 'failed'), _event(2, 'login_password', 'success')])
    assert _step(auth, 'authenticate')['state'] == 'failed'
    assert auth['failure']['stage'] == 'email_otp'


def test_canonical_ids_have_chinese_labels_and_resolve_directly():
    from core.task_stages import resolve_step
    for task_type in TASK_TYPES:
        for step in flow_for(task_type):
            assert resolve_step(task_type, step['id']) == step['id']
            assert step['label'] != step['id']


def test_legacy_registration_text_detail_is_safe_and_remains_readable():
    run = _run('failed', progress_steps={'email_otp': {'state': 'failed', 'detail': '等待验证码超时', 'started_at': '2026-10-09T12:00:00+08:00'}})
    snapshot = build_progress_snapshot(1, 2, 'registration', run, [])
    assert _step(snapshot, 'authenticate')['message'] == '等待验证码超时'
    assert snapshot['outcome']['status'] == 'failed'


def test_optional_skipped_child_does_not_erase_observed_success():
    snapshot = build_progress_snapshot(1, 2, 'registration', _run('success'), [_event(1, 'login', 'success'), _event(2, 'email_otp', 'skipped')])
    assert _step(snapshot, 'authenticate')['state'] == 'success'


def test_group_success_does_not_hide_unclosed_sibling_or_change_first_start():
    events = [_event(1, 'login_password', 'running', created_at='2026-10-09T01:00:01Z'), _event(2, 'email_otp', 'success', created_at='2026-10-09T01:00:02Z')]
    snapshot = build_progress_snapshot(1, 2, 'codex_retry', _run(), events)
    assert _step(snapshot, 'authenticate')['state'] == 'running'
    repeat = build_progress_snapshot(1, 2, 'plan_check', _run(), [_event(1, 'network', 'failed', detail={'started_at': '2026-10-09T01:00:00Z'}), _event(2, 'network', 'running', detail={'started_at': '2026-10-09T01:00:05Z'})])
    assert _step(repeat, 'network')['started_at'] == '2026-10-09T01:00:00Z'


def test_parent_plan_failure_links_to_actual_child_failure():
    child = {'task_type': 'token_refresh', 'task_id': 3, 'run_id': 4, 'status': 'failed', 'failure_stage': 'email_otp', 'failure_event_id': 9, 'error_message': '验证码超时'}
    event = _event(1, 'plan', 'failed', detail={'child_task_id': 3})
    snapshot = build_progress_snapshot(1, 2, 'account_completion', _run('partial_success', result_summary={'child_result': child, 'child_status': 'failed'}), [event])
    assert snapshot['failure']['step_id'] == 'refresh_dispatch'
    assert snapshot['failure']['stage'] == 'email_otp'


def test_unexecuted_generated_steps_have_no_actual_order_or_fake_time():
    events = [_event(1, 'email', 'skipped', detail={'evidence': 'not_executed'}, created_at='2026-10-09T01:00:05Z'), _event(2, 'network', 'success', created_at='2026-10-09T01:00:01Z')]
    snapshot = build_progress_snapshot(1, 2, 'registration', _run('success'), events)
    email = _step(snapshot, 'email')
    assert email['observed_order'] is None
    assert email['started_at'] is None
    assert snapshot['main_steps'][0]['id'] == 'network'
    assert _step(snapshot, 'profile')['display_status'] == 'record_incomplete'


def test_cancelled_before_start_has_explicit_unexecuted_template():
    snapshot = build_progress_snapshot(1, 2, 'plan_check', _run('cancelled', started_at=None), [])
    assert _step(snapshot, 'network')['display_status'] == 'not_executed'


def test_named_parent_summary_exposes_child_run_reference():
    snapshot = build_progress_snapshot(1, 2, 'account_completion', _run('waiting', result_summary={'codex': {'task_id': 3, 'run_id': 4, 'accepted': True}}), [])
    assert snapshot['outcome']['child_tasks'][0]['task_type'] == 'codex_retry'
    assert snapshot['outcome']['child_tasks'][0]['run_id'] == 4


def test_waiting_for_child_partial_result_does_not_invent_failure():
    snapshot = build_progress_snapshot(1, 2, 'account_completion', _run('partial_success', result_summary={'awaiting_steps': ['codex'], 'codex': {'task_id': 3, 'run_id': 4, 'accepted': True}}), [_event(1, 'codex', 'success')])
    assert snapshot['failure'] is None
    assert snapshot['outcome']['status'] == 'partial_success'


def test_unknown_child_reconciliation_is_retained_by_parent_snapshot():
    snapshot = build_progress_snapshot(1, 2, 'account_completion', _run('partial_success', result_summary={'child_tasks': [{'task_id': 3, 'run_id': 4, 'task_type': 'token_refresh', 'status': 'attention_required', 'failure_stage': 'email_otp'}]}), [])
    assert snapshot['failure']['reconcile_required'] is True


def test_all_registered_raw_stages_have_shared_chinese_labels():
    from core.task_stages import TASK_FLOWS, stage_label
    for stages in TASK_FLOWS.values():
        for stage in stages:
            assert stage_label(stage) != stage


def test_historical_success_with_open_preflight_is_neutral_without_fabricated_success():
    events = [_event(1, 'preflight', 'running'), _event(2, 'network', 'success'), _event(3, 'plan_check', 'success')]
    snapshot = build_progress_snapshot(1, 2, 'plan_check', _run('success'), events)
    preflight = _step(snapshot, 'preflight')
    assert preflight['state'] == 'pending'
    assert preflight['display_status'] == 'record_incomplete'
    assert preflight['event_ids'] == ['1']
    assert preflight['completed_at'] is None
    assert _step(snapshot, 'plan_check')['state'] == 'success'


def test_failed_authentication_leaves_unentered_token_steps_unexecuted():
    events = [_event(1, 'preflight', 'running'), _event(2, 'network', 'success'), _event(3, 'email_otp', 'failed', message='本次认证未使用邮箱验证码')]
    snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run('failed'), events)
    for step_id in ('refresh_token', 'token'):
        step = _step(snapshot, step_id)
        assert step['display_status'] == 'not_executed'
        assert step['started_at'] is None
        assert step['attempts'] == []
        assert '失败' in step['reason']
    assert _step(snapshot, 'preflight')['display_status'] == 'record_incomplete'
    assert _step(snapshot, 'authenticate')['state'] == 'failed'


def test_unknown_auth_receipt_keeps_result_unknown_and_later_local_steps_unexecuted():
    events = [
        _event(1, 'network', 'success'), _event(2, 'login_password', 'running'),
        _event(3, 'login_password', detail={'remote_request_started': True}),
        _event(4, 'login_password', detail={'remote_receipt': 'unknown'}),
        _event(5, 'email_otp', 'failed', message='本次认证未使用邮箱验证码'),
    ]
    snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run('attention_required'), events)
    assert snapshot['outcome']['status'] == 'attention_required'
    assert snapshot['failure']['reconcile_required'] is True
    assert _step(snapshot, 'authenticate')['state'] == 'failed'
    assert _step(snapshot, 'authenticate')['children'][0]['display_status'] == 'attention_required'
    assert _step(snapshot, 'refresh_token')['display_status'] == 'not_executed'
    assert _step(snapshot, 'token')['display_status'] == 'not_executed'


def test_started_or_noted_later_stage_is_not_falsely_marked_unexecuted():
    for event in (_event(2, 'refresh_token', 'running'), _event(2, 'refresh_token', message='刷新请求回执待确认')):
        snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run('request_unknown'), [_event(1, 'email_otp', 'failed'), event])
        refresh = _step(snapshot, 'refresh_token')
        assert refresh['display_status'] != 'not_executed'
        if refresh['started_at'] or refresh['attempts']:
            assert refresh['display_status'] == 'request_unknown'


def test_terminal_without_explicit_failure_does_not_guess_unexecuted_steps():
    for status in ('success', 'failed', 'attention_required'):
        snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run(status), [])
        assert _step(snapshot, 'refresh_token')['display_status'] == 'record_incomplete'
        assert _step(snapshot, 'refresh_token')['state'] == 'pending'


def test_parent_parallel_child_summary_does_not_infer_unexecuted_by_template_order():
    summary = {'child_tasks': [{'task_id': 3, 'run_id': 4, 'task_type': 'codex_retry', 'status': 'running', 'accepted': True}]}
    snapshot = build_progress_snapshot(1, 2, 'account_completion', _run('failed', result_summary=summary), [_event(1, 'plan', 'failed')])
    assert _step(snapshot, 'codex_dispatch')['display_status'] != 'not_executed'


def test_declared_dependencies_propagate_failed_preflight_without_order_guessing():
    for task_type, downstream in (
        ('live_check', ('network', 'access_token')),
        ('plan_check', ('network', 'plan_check')),
        ('token_refresh', ('network', 'authenticate', 'refresh_token', 'token')),
        ('codex_token_refresh', ('refresh_token', 'credential')),
    ):
        snapshot = build_progress_snapshot(1, 2, task_type, _run('failed'), [_event(1, 'preflight', 'failed')])
        assert _step(snapshot, 'preflight')['state'] == 'failed'
        for step_id in downstream:
            assert _step(snapshot, step_id)['display_status'] == 'not_executed'


def test_recovered_dependency_failure_does_not_block_unobserved_or_executed_steps():
    events = [_event(1, 'network', 'failed'), _event(2, 'network', 'success'), _event(3, 'login_password', 'success')]
    snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run('success'), events)
    assert snapshot['failure'] is None
    assert _step(snapshot, 'refresh_token')['display_status'] == 'record_incomplete'
    assert _step(snapshot, 'authenticate')['state'] == 'success'


def test_dependency_cannot_overwrite_actual_reverse_order_or_started_later_step():
    events = [
        _event(1, 'token', 'success', created_at='2026-10-09T01:00:00Z'),
        _event(2, 'email_otp', 'failed', created_at='2026-10-09T01:00:01Z'),
        _event(3, 'refresh_token', 'running', created_at='2026-10-09T01:00:02Z'),
    ]
    snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run('failed'), events)
    assert [value['id'] for value in snapshot['main_steps']][:3] == ['token', 'authenticate', 'refresh_token']
    assert _step(snapshot, 'token')['state'] == 'success'
    assert _step(snapshot, 'refresh_token')['display_status'] == 'unconfirmed'


def test_child_submission_evidence_blocks_unexecuted_inference():
    summary = {'child_tasks': [{'task_id': 3, 'run_id': 4, 'step_id': 'refresh_token', 'status': 'running'}]}
    snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run('failed', result_summary=summary), [_event(1, 'email_otp', 'failed')])
    assert _step(snapshot, 'refresh_token')['display_status'] == 'record_incomplete'
    assert _step(snapshot, 'token')['display_status'] == 'record_incomplete'


def test_unknown_failures_and_undeclared_branches_do_not_block_by_template_order():
    unknown = build_progress_snapshot(1, 2, 'token_refresh', _run('failed'), [_event(1, 'new_driver_stage', 'failed')])
    assert _step(unknown, 'refresh_token')['display_status'] == 'record_incomplete'
    branch = build_progress_snapshot(1, 2, 'password_setup', _run('failed'), [_event(1, 'network', 'failed')])
    assert _step(branch, 'set_password')['display_status'] == 'record_incomplete'


def test_multiple_dependencies_only_block_on_unrecovered_failed_prerequisite(monkeypatch):
    from core import task_stages
    template = tuple(dict(value, depends_on=('network', 'preflight')) if value['id'] == 'plan_check' else dict(value) for value in task_stages.TASK_TEMPLATES['plan_check'])
    monkeypatch.setitem(task_stages.TASK_TEMPLATES, 'plan_check', template)
    events = [_event(1, 'preflight', 'failed'), _event(2, 'network', 'success')]
    snapshot = build_progress_snapshot(1, 2, 'plan_check', _run('failed'), events)
    assert _step(snapshot, 'plan_check')['display_status'] == 'not_executed'
    recovered = build_progress_snapshot(1, 2, 'plan_check', _run('failed'), [*events, _event(3, 'preflight', 'success')])
    assert _step(recovered, 'plan_check')['display_status'] == 'record_incomplete'


def test_template_dependency_contract_uses_independent_immutable_values():
    original = flow_for('token_refresh')
    assert next(value for value in original if value['id'] == 'refresh_token')['depends_on'] == ('authenticate',)
    next(value for value in original if value['id'] == 'refresh_token')['depends_on'] = ('unrelated',)
    assert next(value for value in flow_for('token_refresh') if value['id'] == 'refresh_token')['depends_on'] == ('authenticate',)


def test_cancellation_after_started_or_completed_preflight_does_not_invent_failure():
    for status in ('cancelled', 'canceled', 'stopped', 'interrupted'):
        for phase_state in ('running', 'success'):
            run = _run(status, started_at='2026-10-09T01:00:00Z')
            events = [_event(1, 'preflight', phase_state, message='套餐查询预检通过' if phase_state == 'success' else '开始查询账号套餐'), _event(2, 'preflight', detail={'cancelled': True})]
            snapshot = build_progress_snapshot(1, 2, 'plan_check', run, events)
            assert snapshot['failure'] is None
            assert _step(snapshot, 'preflight')['display_status'] == ('success' if phase_state == 'success' else 'interrupted')


def test_cancellation_keeps_real_unrecovered_failure_and_child_failure():
    snapshot = build_progress_snapshot(1, 2, 'plan_check', _run('interrupted'), [_event(1, 'network', 'failed', message='网络线路申请失败')])
    assert snapshot['failure']['stage'] == 'network'
    assert snapshot['failure']['evidence'] == 'explicit'
    child = {'task_id': 3, 'run_id': 4, 'task_type': 'token_refresh', 'status': 'failed', 'failure_stage': 'email_otp'}
    parent = build_progress_snapshot(1, 2, 'account_completion', _run('cancelled', result_summary={'child_tasks': [child]}), [])
    assert parent['failure']['child_task_id'] == 3


def test_not_executed_evidence_never_copies_detail_timing_or_duration():
    for evidence in ('not_executed', 'unobserved'):
        event = _event(1, 'browser', 'skipped', detail={
            'evidence': evidence, 'started_at': '2026-10-09T01:00:00Z',
            'completed_at': '2026-10-09T01:00:01Z', 'duration_ms': 1000,
        }, created_at='2026-10-09T01:00:02Z')
        snapshot = build_progress_snapshot(1, 2, 'password_setup', _run('failed'), [event])
        browser = _step(snapshot, 'browser')
        assert browser['started_at'] is None
        assert browser['completed_at'] is None
        assert browser['duration_ms'] is None
        assert browser['observed_order'] is None
        assert browser['attempts'][0]['created_at'] is None
        assert browser['attempts'][0].get('duration_ms') is None


def test_missing_run_start_does_not_overwrite_resource_or_remote_activity_evidence():
    for event_type in ('resource.acquired', 'remote.request_started', 'note.warning'):
        event = _event(1, 'network', message='阶段已有实际活动记录')
        event['event_type'] = event_type
        snapshot = build_progress_snapshot(1, 2, 'plan_check', _run('cancelled', started_at=None), [event])
        assert _step(snapshot, 'network')['display_status'] != 'not_executed'
        assert snapshot['failure'] is None


def test_unmapped_remote_or_dynamic_stage_activity_prevents_unexecuted_inference():
    for event in (_event(2, 'future_driver_step', 'running'), _event(2, 'event', message='远端请求已发出')):
        if event['stage'] == 'event':
            event['event_type'] = 'remote.request_started'
        snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run('request_unknown'), [_event(1, 'email_otp', 'failed'), event])
        assert _step(snapshot, 'refresh_token')['display_status'] == 'record_incomplete'
        cancelled = build_progress_snapshot(1, 2, 'token_refresh', _run('cancelled', started_at=None), [event])
        assert _step(cancelled, 'refresh_token')['display_status'] != 'not_executed'


def test_real_token_refresh_boundary_events_bind_to_started_authentication():
    started = _event(4, 'remote_request', detail={'action': 'token_refresh', 'intent_kind': 'remote_write'})
    started['event_type'] = 'remote.request_started'
    unknown = _event(5, 'reconcile', detail={'action': 'token_refresh', 'outcome': 'unknown', 'response_observed': False})
    unknown['event_type'] = 'remote.receipt_unknown'
    events = [
        _event(1, 'preflight', 'running'), _event(2, 'network', 'success'),
        _event(3, 'login_password', 'running'), started, unknown,
        _event(6, 'login_password', 'skipped'), _event(7, 'mfa_challenge', 'skipped'),
        _event(8, 'email_otp', 'failed', message='本次认证未使用邮箱验证码'),
    ]
    snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run('attention_required'), events)
    assert snapshot['outcome']['status'] == 'attention_required'
    assert snapshot['failure']['reconcile_required'] is True
    assert snapshot['failure']['stage'] == 'email_otp'
    authenticate = _step(snapshot, 'authenticate')
    assert authenticate['state'] == 'failed'
    assert {'4', '5'} <= set(authenticate['event_ids'])
    assert {'remote_request', 'reconcile'} <= set(authenticate['raw_stages'])
    assert all(attempt['event_id'] not in {'4', '5'} for attempt in authenticate['attempts'])
    assert _step(snapshot, 'refresh_token')['display_status'] == 'not_executed'
    assert _step(snapshot, 'token')['display_status'] == 'not_executed'


def test_remote_boundary_without_matching_action_or_auth_context_stays_conservative():
    for action, raw, context in (
        ('other_action', 'remote_request', [_event(1, 'login_password', 'running')]),
        ('token_refresh', 'remote_request', [_event(1, 'network', 'success')]),
        ('token_refresh', 'future_driver_stage', [_event(1, 'login_password', 'running')]),
    ):
        remote = _event(2, raw, detail={'action': action})
        remote['event_type'] = 'remote.request_started'
        snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run('attention_required'), [*context, remote, _event(3, 'email_otp', 'failed')])
        assert _step(snapshot, 'refresh_token')['display_status'] == 'record_incomplete'
        assert _step(snapshot, 'token')['display_status'] == 'record_incomplete'


def test_explicit_remote_trigger_stage_can_associate_without_text_inference():
    remote = _event(1, 'reconcile', detail={'action': 'token_refresh', 'trigger_stage': 'login_password'})
    remote['event_type'] = 'remote.receipt_unknown'
    snapshot = build_progress_snapshot(1, 2, 'token_refresh', _run('attention_required'), [remote, _event(2, 'email_otp', 'failed')])
    assert _step(snapshot, 'authenticate')['event_ids'] == ['1', '2']
    assert _step(snapshot, 'refresh_token')['display_status'] == 'not_executed'
