"""纯输入/输出验证；不连接数据库或执行账号操作。"""
import copy
import json
from pathlib import Path

from core.operations.progress import build_progress_snapshot
from core.operations.stages import TASK_TEMPLATES, flow_for


def event(number, stage, state, **detail):
    return {"id": number, "run_id": 2, "stage": stage, "event_type": f"stage.{state}",
            "detail": {"step_state": state, **detail}}


def snapshot(task_type="registration", *, events=(), **run):
    return build_progress_snapshot(1, 2, task_type, {"status": "running", **run}, events)


def step(value, step_id):
    return next(item for item in value["main_steps"] if item["id"] == step_id)


def test_every_existing_template_has_display_metadata_without_asserting_parallelism():
    before = copy.deepcopy(TASK_TEMPLATES)
    for task_type in TASK_TEMPLATES:
        value = snapshot(task_type)
        assert value["structure"]["parallelism"] == "unknown", task_type
        for item in value["main_steps"]:
            assert item["execution"]["source"] == "runtime_contract", (task_type, item["id"])
            assert item["execution"]["parallel_group"] is None
            assert item["execution"]["retry"]["state"] == "unknown"
            original = next(entry for entry in flow_for(task_type) if entry["id"] == item["id"])
            assert item["depends_on"] == list(original["depends_on"])
            assert item["raw_stages"] == original["raw_stages"]
    assert TASK_TEMPLATES == before


def test_conditions_use_frozen_config_but_actual_execution_takes_precedence():
    run = {"config_snapshot": {"codex_enabled": False, "twofa_enabled": True}}
    absent = snapshot(**run)
    assert step(absent, "codex")["execution"]["condition"]["state"] == "not_met"
    assert step(absent, "set_twofa")["execution"]["condition"]["state"] == "met"
    assert step(absent, "profile")["execution"]["condition"]["state"] == "unknown"
    observed = snapshot(events=[event(1, "oauth", "running")], **run)
    assert step(observed, "codex")["execution"]["condition"] == {
        "label": "本次任务启用 Codex 授权", "state": "met", "evidence": "explicit"}


def test_codex_sub2api_events_use_one_stable_stage_with_or_without_summary():
    events = [event(1, "sub2api_sync", "running")]
    running = snapshot("codex_retry", events=events)
    complete = snapshot("codex_retry", status="success",
                        result_summary={"sub2api_sync": {"status": "success"}},
                        events=[*events, event(2, "sub2api_sync", "success")])

    for value, state, ids in ((running, "running", ["1"]), (complete, "success", ["1", "2"])):
        sync_steps = [item for item in value["main_steps"] if "sub2api_sync" in item["raw_stages"]]
        assert len(sync_steps) == 1
        assert sync_steps[0]["id"] == "sub2api_sync"
        assert sync_steps[0]["display_status"] == state
        assert sync_steps[0]["event_ids"] == ids


def test_child_dispatch_success_remains_waiting_and_does_not_claim_parallelism():
    summary = {"planned_steps": ["refresh_at", "password", "codex"], "awaiting_steps": ["refresh_at"],
               "continuation_steps": ["password", "codex"], "refresh_at": {"task_id": 30, "accepted": True}}
    value = snapshot("account_completion", status="partial_success", result_summary=summary,
                     events=[event(1, "refresh_token", "success")])
    dispatch = step(value, "refresh_dispatch")
    assert dispatch["state"] == "success"  # 分派成功不是子任务成功
    assert dispatch["execution"]["kind"] == "child_task"
    assert dispatch["execution"]["dependency_state"] == "waiting"
    assert dispatch["execution"]["waits_for"][0]["task_id"] == 30
    assert step(value, "set_password")["execution"]["dependency_state"] == "waiting"
    assert step(value, "result")["execution"]["dependency_state"] == "waiting"
    assert value["outcome"]["child_tasks"][0]["task_id"] == 30
    assert value["structure"]["parallelism"] == "unknown"


def test_native_setup_child_keeps_stable_dispatch_id_despite_legacy_plan_filter():
    value = snapshot("account_completion", status="waiting", result_summary={
        "planned_steps": ["password", "twofa"], "awaiting_steps": ["account_setup"],
        "account_setup": {"task_id": 40, "run_id": 41},
    }, events=[event(1, "account_setup", "success")])
    item = step(value, "account_setup_dispatch")
    assert item["execution"]["dependency_state"] == "waiting"
    assert item["execution"]["waits_for"][0]["run_id"] == 41
    assert not any(item["id"] == "unknown:account_setup" for item in value["main_steps"])


def test_real_child_reference_overrides_incomplete_plan_without_fabricating_stage_evidence():
    for child_summary in (
        {"account_setup": {"task_id": 40, "run_id": 41}},
        {"child_tasks": [{"task_id": 40, "run_id": 41, "task_type": "account_setup_retry"}]},
    ):
        value = snapshot("account_completion", status="waiting", result_summary={
            "planned_steps": ["codex"], "awaiting_steps": ["account_setup"], **child_summary,
        })
        item = step(value, "account_setup_dispatch")
        assert item["execution"]["condition"]["state"] == "met"
        assert item["execution"]["condition"]["evidence"] == "result_summary"
        assert item["execution"]["dependency_state"] == "waiting"
        assert item["state"] == "pending"
        assert item["observed_order"] is None
        assert item["started_at"] is None
        assert item["completed_at"] is None
        assert item["event_ids"] == []
        assert item["attempts"] == []


def test_wait_marker_without_child_reference_does_not_confirm_dispatch_condition():
    value = snapshot("account_completion", status="waiting", result_summary={
        "planned_steps": [], "awaiting_steps": ["account_setup"],
    })
    item = step(value, "account_setup_dispatch")
    assert item["execution"]["condition"]["state"] == "not_met"
    assert item["execution"]["condition"]["evidence"] == "planned_steps"


def test_child_terminal_status_overrides_stale_awaiting_marker():
    for status, expected in [("success", "satisfied"), ("failed", "blocked"), ("attention_required", "blocked")]:
        value = snapshot("account_completion", status="partial_success", result_summary={
            "awaiting_steps": ["codex"], "child_tasks": [{"task_id": 10, "task_type": "codex_retry", "status": status}]})
        assert step(value, "codex_dispatch")["execution"]["dependency_state"] == expected


def test_child_relationship_alone_does_not_assert_parent_waiting():
    value = snapshot("account_completion", result_summary={
        "child_tasks": [{"task_id": 10, "task_type": "codex_retry", "status": "running"}]})
    assert step(value, "codex_dispatch")["execution"]["dependency_state"] == "unknown"


def test_explicit_wait_without_child_id_stays_visible_without_inventing_a_target():
    value = snapshot("account_completion", status="partial_success", result_summary={"awaiting_steps": ["codex"]})
    execution = step(value, "codex_dispatch")["execution"]
    assert execution["dependency_state"] == "waiting"
    assert execution["waits_for"][0]["task_id"] is None


def test_dependency_wait_is_unknown_without_child_or_wait_evidence():
    value = snapshot("token_refresh", events=[event(1, "preflight", "success")])
    assert step(value, "network")["execution"]["dependency_state"] == "satisfied"
    assert step(value, "authenticate")["execution"]["dependency_state"] == "unknown"
    assert value["structure"]["parallelism"] == "unknown"


def test_observed_stage_is_not_reclassified_as_blocked_by_later_dependency_failure():
    value = snapshot("token_refresh", events=[event(1, "preflight", "success"),
        event(2, "network", "success"), event(3, "preflight", "failed")])
    item = step(value, "network")
    assert item["state"] == "success"
    assert item["execution"]["dependency_state"] == "unknown"


def test_unobserved_markers_do_not_supply_parallel_evidence():
    value = snapshot(events=[event(1, "codex", "skipped", parallel_group="synthetic", evidence="not_executed"),
                             event(2, "twofa", "skipped", parallel_group="synthetic", evidence="not_executed")])
    assert value["structure"]["parallelism"] == "unknown"
    assert step(value, "codex")["execution"]["parallel_group"] is None


def test_normal_substeps_and_multiple_running_records_do_not_become_retries():
    value = snapshot("token_refresh", events=[event(1, "login", "running"), event(2, "login", "running"),
        event(3, "login", "success"), event(4, "email_otp", "success")])
    assert step(value, "authenticate")["execution"]["retry"] == {
        "state": "unknown", "attempt_count": None, "event_ids": []}


def test_distinct_instances_without_failure_are_not_assumed_to_be_retries():
    value = snapshot("plan_check", events=[event(1, "plan_check", "success", step_instance_id="country-one"),
                                          event(2, "plan_check", "success", step_instance_id="country-two")])
    assert step(value, "plan_check")["execution"]["retry"]["state"] == "unknown"


def test_multiple_countries_and_late_running_do_not_become_retries():
    value = snapshot("plan_check", events=[event(1, "plan_check", "failed", country="US"),
                                          event(2, "plan_check", "running", country="IN"),
                                          event(3, "plan_check", "success", country="IN")])
    assert step(value, "plan_check")["execution"]["retry"]["state"] == "unknown"
    value = snapshot("token_refresh", events=[event(1, "email_otp", "failed", step_instance_id="same"),
                                              event(2, "email_otp", "running", step_instance_id="same")])
    assert step(value, "authenticate")["execution"]["retry"]["state"] == "unknown"


def test_retry_recovery_preserves_original_failure_and_event_ids():
    value = snapshot("token_refresh", events=[event(1, "email_otp", "failed", step_instance_id="first"),
        event(2, "email_otp", "running", step_instance_id="second"), event(3, "email_otp", "success", step_instance_id="second")])
    item = step(value, "authenticate")
    assert item["execution"]["retry"] == {"state": "recovered", "attempt_count": 2, "event_ids": ["1", "2", "3"]}
    assert any(attempt["state"] == "failed" for attempt in item["attempts"])


def test_overlap_and_order_never_prove_parallelism_but_explicit_groups_do():
    events = [event(1, "codex", "running", started_at="2026-11-13T10:00:00Z"),
              event(2, "twofa", "running", started_at="2026-11-13T10:00:00Z")]
    value = snapshot(events=events)
    assert value["structure"]["parallelism"] == "unknown"
    assert step(value, "codex")["observed_order"] < step(value, "set_twofa")["observed_order"]
    for item in events:
        item["detail"]["parallel_group"] = "explicit-branch-1"
    value = snapshot(events=events)
    assert value["structure"]["parallelism"] == "explicit"
    assert step(value, "codex")["execution"]["parallel_group"] == "explicit-branch-1"


def test_other_run_and_other_route_do_not_supply_execution_relationships():
    foreign = {**event(1, "codex", "failed", parallel_group="other"), "run_id": 99}
    events = [foreign, event(2, "twofa", "failed", route_attempt_no=1),
              event(3, "twofa", "success", route_attempt_no=2)]
    value = snapshot(events=events, route_attempt_no=2)
    assert value["structure"]["parallelism"] == "unknown"
    assert step(value, "set_twofa")["execution"]["retry"]["state"] == "unknown"


def test_unknown_runtime_type_retains_events_and_unknown_semantics():
    value = snapshot("unregistered_task", events=[event(1, "some_stage", "running")])
    item = step(value, "unknown:some_stage")
    assert item["execution"]["kind"] == "unknown"
    assert item["execution"]["source"] == "event"
    assert item["raw_stages"] == ["some_stage"]


def test_progress_structure_matches_public_contract_and_does_not_mutate_inputs():
    source = {"status": "waiting", "result_summary": {"child_tasks": [{"task_id": 3, "task_type": "codex_retry", "status": "running"}]}}
    original = copy.deepcopy(source)
    value = build_progress_snapshot(1, 2, "account_completion", source, [])
    contract = json.loads((Path(__file__).resolve().parents[2] / "contracts/task-center.openapi.json").read_text())
    schemas = contract["components"]["schemas"]
    assert set(schemas["OperationProgress"]["required"]) <= value.keys()
    assert set(schemas["ProgressStructure"]["required"]) <= value["structure"].keys()
    for item in value["main_steps"]:
        execution = item["execution"]
        assert set(schemas["ProgressExecution"]["required"]) <= execution.keys()
        for key in ("kind", "source", "dependency_state"):
            assert execution[key] in schemas["ProgressExecution"]["properties"][key]["enum"]
        assert execution["retry"]["state"] in schemas["ProgressRetry"]["properties"]["state"]["enum"]
    assert source == original
