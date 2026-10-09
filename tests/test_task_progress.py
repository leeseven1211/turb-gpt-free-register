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
    assert _step(snapshot, 'profile')['display_status'] == 'unconfirmed'


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
