"""Team HTTP 契约边界；替换服务层，不访问数据库或远端。"""
from __future__ import annotations

from copy import deepcopy
import functools
import importlib
import importlib.util
import json
import logging
from pathlib import Path
import re
from types import SimpleNamespace

from flask import Flask
import pytest

from webui.auth import init_auth, register_auth_routes


AUTH = {"X-Auth-Code": "team-http-test"}
KEY = "team-http-request-0001"
ACCOUNT = {"id": "9007199254740993", "email": "member@example.test", "archived": False}
TEAM = {
    "id": "9007199254740995", "workspace_id": "ws_opaque", "name": None, "display_name": "本地备注",
    "manager_account": ACCOUNT, "role": "admin", "purchased_seats": 0, "planned_member_limit": None,
    "confirmed_member_count": None, "pending_invite_count": None, "processing_count": None,
    "last_synced_at": None, "last_sync_status": "queued", "revision": 1,
}
ACTION = {
    "accepted": True, "reused": False, "team_id": TEAM["id"],
    "task_id": "9007199254740997", "run_id": "9007199254740999", "status": "queued",
}
ALLOWED = {"enabled": True, "reason_code": None}
CAPACITY = {
    "basis": "purchased_seats", "purchased_seats": 0, "planned_member_limit": None,
    "effective_limit": 0, "occupied_count": None, "available_count": None,
    "additional_required": None, "can_submit": True, "blocking_reason_code": None,
}
COUNTS = {
    "requested_count": 1, "unique_count": 1, "duplicate_count": 0, "pending_count": 1,
    "accepted_count": 0, "reused_count": 0, "skipped_count": 0, "failed_count": 0,
}
JOIN = {
    "id": "27", "team_id": TEAM["id"], "operation": "join", "accepted": True, "reused": False,
    "status": "preparing", "waiting_reason_code": None, "selection_id": None, "selection_revision": None,
    "batch_id": "29", "task_id": "31", "run_id": "33", "created_at": "2026-11-27T12:00:00+08:00",
    "counts": COUNTS, "capacity": CAPACITY, "items_url": f"/api/teams/{TEAM['id']}/join-requests/27",
}
LIST = {"items": [TEAM], "total": 1, "page": 1, "page_size": 20, "revision": "team:1"}


def _routes():
    assert importlib.util.find_spec("webui.routes.teams") is not None, "尚未实现 Team HTTP 路由"
    return importlib.import_module("webui.routes.teams")


@functools.lru_cache
def _openapi():
    return json.loads((Path(__file__).resolve().parents[2] / "contracts/teams.openapi.json").read_text())


def _assert_contract(value, schema, location="响应"):
    """运行本契约使用的 JSON Schema 子集，检查类型、字段、枚举及边界。"""
    spec = _openapi()
    if "$ref" in schema:
        child = spec
        for part in schema["$ref"].removeprefix("#/").split("/"):
            child = child[part]
        _assert_contract(value, child, location)
    for branch in schema.get("allOf", []):
        _assert_contract(value, branch, location)
    for keyword in ("anyOf", "oneOf"):
        if keyword not in schema:
            continue
        matches = 0
        for branch in schema[keyword]:
            try:
                _assert_contract(value, branch, location)
                matches += 1
            except AssertionError:
                pass
        assert matches == 1 if keyword == "oneOf" else matches >= 1, f"{location} 不符合 {keyword}"
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    actual = {
        "null": value is None, "object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str), "boolean": type(value) is bool, "integer": type(value) is int,
        "number": type(value) in (int, float),
    }
    assert not types or any(actual[kind] for kind in types), f"{location} 类型错误"
    if "const" in schema:
        assert value == schema["const"], f"{location} 常量错误"
    if "enum" in schema:
        assert value in schema["enum"], f"{location} 枚举错误"
    if isinstance(value, dict):
        assert set(schema.get("required", [])) <= value.keys(), f"{location} 缺少必需字段"
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            assert value.keys() <= properties.keys(), f"{location} 包含额外字段"
        for key, item in value.items():
            child = properties.get(key, schema.get("additionalProperties"))
            if isinstance(child, dict):
                _assert_contract(item, child, f"{location}.{key}")
    if isinstance(value, list):
        assert len(value) >= schema.get("minItems", 0), f"{location} 项数过少"
        assert len(value) <= schema.get("maxItems", len(value)), f"{location} 项数过多"
        for index, item in enumerate(value):
            _assert_contract(item, schema.get("items", {}), f"{location}[{index}]")
    if isinstance(value, str):
        assert len(value) >= schema.get("minLength", 0), f"{location} 过短"
        assert len(value) <= schema.get("maxLength", len(value)), f"{location} 过长"
        if "pattern" in schema:
            assert re.search(schema["pattern"], value), f"{location} 格式错误"
    if type(value) in (int, float):
        assert value >= schema.get("minimum", value), f"{location} 数值过小"
        assert value <= schema.get("maximum", value), f"{location} 数值过大"


def _assert_response_contract(response, method, path):
    for template, methods in _openapi()["paths"].items():
        expression = re.sub(r"\{[^}]+\}", "[^/]+", template)
        if re.fullmatch(expression, path) and method in methods:
            schema = methods[method]["responses"][str(response.status_code)]["content"]["application/json"]["schema"]
            _assert_contract(response.get_json(), schema)
            return
    raise AssertionError(f"OpenAPI 未声明 {method} {path}")


def test_team_route_factory_can_be_registered():
    routes = _routes()
    app = Flask(__name__)
    app.register_blueprint(routes.create_teams_blueprint(None))
    assert app.test_client().get("/api/teams?other=1").status_code == 422


def test_application_factory_mounts_team_blueprint(monkeypatch):
    module = importlib.import_module("webui.app")
    monkeypatch.setattr(module, "register_commands", lambda: None)
    web = module.create_app(auth_code=AUTH["X-Auth-Code"]).test_client()
    response = web.get("/api/teams?unpublished=1", headers=AUTH)
    _assert_error(response, 422, "field_not_supported", "unpublished")


@pytest.fixture
def http(monkeypatch):
    routes = _routes()
    boundary = SimpleNamespace(
        list_teams=lambda query: deepcopy(LIST),
        get_team=lambda team_id: {
            "team": deepcopy(TEAM), "actions": {"sync": ALLOWED, "reverify": ALLOWED, "join": ALLOWED},
            "permission_verified_at": None,
        },
        start_probe=lambda payload, key: {"probe_id": "11", "status": "queued", "task_id": "13", "run_id": "15"},
        get_probe=lambda probe_id: {
            "id": probe_id, "revision": 1, "manager_account": ACCOUNT, "status": "queued", "stage": "queued",
            "task_id": "13", "run_id": "15", "workspaces": [], "suggested_workspace_id": None,
            "completed_at": None, "expires_at": None, "error_info": None,
        },
        create_team=lambda payload, key: {"team": deepcopy(TEAM), "sync": deepcopy(ACTION)},
        update_team=lambda team_id, payload, key: {"team": deepcopy(TEAM)},
        sync_team=lambda team_id, payload, key: deepcopy(ACTION),
        sync_bulk=lambda payload, key: {
            "accepted": True, "batch_id": "17", "requested_count": 1, "unique_count": 1,
            "duplicate_count": 0, "reused_count": 0, "accepted_count": 1, "skipped_count": 0,
            "failed_count": 0, "items": [{
                "team_id": TEAM["id"], "task_id": "13", "run_id": "15", "acceptance_status": "accepted",
                "execution_status": "queued", "reason_code": None,
            }],
        },
        reverify=lambda team_id, payload, key: deepcopy(ACTION),
        list_members=lambda team_id, query: {**deepcopy(LIST), "items": []},
        list_invitations=lambda team_id, query: {**deepcopy(LIST), "items": []},
        get_invitation=lambda team_id, invitation_id: {"invitation": {
            "id": invitation_id, "team_id": team_id, "remote_invitation_id": None, "account": ACCOUNT,
            "email_snapshot": ACCOUNT["email"], "invitation_state": "not_sent", "membership_state": "unconfirmed",
            "latest_execution": {
                "task_id": None, "run_id": None, "status": "none", "stage": "queued",
                "waiting_reason_code": None, "error_info": None,
            },
            "updated_at": "2026-11-27T12:00:00+08:00", "last_verified_at": None,
            "actions": {"continue": ALLOWED, "retry": ALLOWED, "view_task": ALLOWED},
        }},
        list_candidates=lambda team_id, query: {**deepcopy(LIST), "items": []},
        resolve_candidates=lambda team_id, payload: {
            "requested_count": 1, "unique_count": 1, "duplicate_count": 0,
            "items": [{"input": "101", "match_status": "not_found", "candidates": [], "reason_code": "account_not_found"}],
        },
        preview_join=lambda team_id, payload: {
            "team_id": team_id, "selection_id": None, "selection_revision": None,
            "snapshot_revision": "local:1", "snapshot_at": "2026-11-27T12:00:00+08:00",
            "team_last_synced_at": None, "requires_sync": True,
            "counts": {
                "requested_count": 1, "unique_count": 1, "duplicate_count": 0, "unavailable_count": 0,
                "another_team_count": 0, "already_member_count": 0, "same_team_active_count": 0,
                "missing_auth_count": 0, "resume_invite_count": 0, "new_count": 1, "eligible_count": 1,
            },
            "capacity": CAPACITY,
        },
        submit_join=lambda team_id, payload, key: deepcopy(JOIN),
        get_join_request=lambda team_id, request_id, query: {
            "request": deepcopy(JOIN), "items": [], "total": 0, "page": 1, "page_size": 20, "revision": "join:1",
        },
        invitation_action=lambda team_id, action, payload, key, invitation_id=None: {
            **deepcopy(JOIN), "operation": action,
        },
    )
    monkeypatch.setattr(routes, "service", boundary)
    app = Flask(__name__)
    init_auth(app, auth_code=AUTH["X-Auth-Code"])
    register_auth_routes(app)
    app.register_blueprint(routes.create_teams_blueprint(SimpleNamespace(logger=logging.getLogger(__name__))))
    return app.test_client(), boundary


def _assert_error(response, status, code, field=None):
    assert response.status_code == status
    value = response.get_json()
    assert set(value) == {"ok", "request_id", "error"}
    assert value["ok"] is False and value["request_id"]
    assert set(value["error"]) == {"code", "message", "field", "retryable", "details"}
    assert value["error"]["code"] == code
    if field is not None:
        assert value["error"]["field"] == field
    _assert_contract(value, {"$ref": f"#/components/schemas/Http{status}Response"})
    return value["error"]


def test_existing_authentication_gate_uses_team_error_envelope(http):
    web, _ = http
    _assert_error(web.get("/api/teams"), 401, "authentication_required")
    _assert_error(web.post("/api/teams/1/sync", json={}), 401, "authentication_required")


@pytest.mark.parametrize(("method", "path", "body", "status", "data_field"), [
    ("get", "/api/teams", None, 200, "items"),
    ("get", "/api/teams/1", None, 200, "team"),
    ("post", "/api/teams/binding-probes", {"manager_account_id": "1"}, 202, "probe_id"),
    ("get", "/api/teams/binding-probes/11", None, 200, "workspaces"),
    ("post", "/api/teams", {
        "manager_account_id": "1", "workspace_id": "ws_opaque", "probe_id": "11", "probe_revision": 1,
    }, 201, "sync"),
    ("patch", "/api/teams/1", {"expected_revision": 1, "display_name": "备注"}, 200, "team"),
    ("post", "/api/teams/1/sync", {}, 202, "accepted"),
    ("post", "/api/teams/sync-bulk", {"team_ids": ["1"]}, 202, "items"),
    ("post", "/api/teams/1/reverify", {}, 202, "accepted"),
    ("get", "/api/teams/1/members", None, 200, "items"),
    ("get", "/api/teams/1/invitations", None, 200, "items"),
    ("get", "/api/teams/1/invitations/3", None, 200, "invitation"),
    ("get", "/api/teams/1/candidates", None, 200, "items"),
    ("post", "/api/teams/1/candidates/resolve", {"values": ["101"]}, 200, "items"),
    ("post", "/api/teams/1/join-preview", {"account_ids": ["101"]}, 200, "capacity"),
    ("post", "/api/teams/1/join", {"account_ids": ["101"]}, 202, "items_url"),
    ("get", "/api/teams/1/join-requests/27", None, 200, "request"),
    ("post", "/api/teams/1/invitations/3/continue", {}, 202, "operation"),
    ("post", "/api/teams/1/invitations/3/retry", {}, 202, "operation"),
    ("post", "/api/teams/1/invitations/continue-bulk", {"invitation_ids": ["3"]}, 202, "operation"),
    ("post", "/api/teams/1/invitations/retry-bulk", {"invitation_ids": ["3"]}, 202, "operation"),
])
def test_frozen_endpoints_use_their_success_status_and_envelope(http, method, path, body, status, data_field):
    web, _ = http
    response = getattr(web, method)(path, json=body, headers={**AUTH, "Idempotency-Key": KEY})
    assert response.status_code == status, response.get_data(as_text=True)
    value = response.get_json()
    assert set(value) == {"ok", "request_id", "data"}
    assert value["ok"] is True and value["request_id"]
    assert data_field in value["data"]
    _assert_response_contract(response, method, path)


@pytest.mark.parametrize(("path", "field"), [
    ("/api/teams?other=1", "other"), ("/api/teams?page=0", "page"),
    ("/api/teams?page_size=101", "page_size"), ("/api/teams?role=owner,admin", "role"),
    ("/api/teams?include_facets=true", "include_facets"), ("/api/teams?manager_account_id=0", "manager_account_id"),
    ("/api/teams/1/members?linked=true", "linked"), ("/api/teams/1/members?membership_state=all", "membership_state"),
    ("/api/teams/1/invitations?stage=manager_auth", "stage"),
    ("/api/teams/1/candidates?has_password=1", "has_password"),
    ("/api/teams/1/candidates?archived=1", "archived"),
    ("/api/teams/1/candidates?scope=other", "scope"),
    ("/api/teams/1/join-requests/2?execution_status=unknown", "execution_status"),
    ("/api/teams?page=1&page=2", "page"),
])
def test_query_rejects_unknown_duplicate_and_out_of_contract_values(http, path, field):
    web, _ = http
    code = "field_not_supported" if field == "other" else "parameter_invalid"
    _assert_error(web.get(path, headers=AUTH), 422, code, field)


@pytest.mark.parametrize("path", ["/api/teams/0", "/api/teams/-1", "/api/teams/abc", "/api/teams/1/invitations/0"])
def test_local_path_ids_are_positive_decimal_strings(http, path):
    web, _ = http
    _assert_error(web.get(path, headers=AUTH), 422, "parameter_invalid")


@pytest.mark.parametrize(("body", "headers", "code"), [
    ({}, {}, "idempotency_key_required"),
    ({"idempotency_key": "short"}, {}, "idempotency_key_invalid"),
    ({}, {"Idempotency-Key": "short"}, "idempotency_key_invalid"),
    ({"idempotency_key": KEY + "other"}, {"Idempotency-Key": KEY}, "idempotency_key_mismatch"),
    ({"idempotency_key": 123}, {}, "idempotency_key_invalid"),
    ({"idempotency_key": None}, {"Idempotency-Key": KEY}, "idempotency_key_invalid"),
])
def test_write_requires_valid_matching_idempotency_sources(http, body, headers, code):
    web, _ = http
    _assert_error(web.post("/api/teams/1/sync", json=body, headers={**AUTH, **headers}), 422, code)


def test_body_key_is_trimmed_and_removed_before_service_call(http):
    web, boundary = http
    def sync(team_id, payload, key):
        assert team_id == "9007199254740993"
        assert payload == {}
        assert key == KEY
        return deepcopy(ACTION)
    boundary.sync_team = sync
    result = web.post("/api/teams/9007199254740993/sync", headers=AUTH, json={"idempotency_key": f"  {KEY}  "})
    assert result.status_code == 202


@pytest.mark.parametrize("path", [
    "/api/teams/1/sync", "/api/teams/1/reverify",
    "/api/teams/1/invitations/3/continue", "/api/teams/1/invitations/3/retry",
])
def test_empty_business_payload_allows_header_only_idempotent_write(http, path):
    web, _ = http
    response = web.post(path, headers={**AUTH, "Idempotency-Key": KEY})
    assert response.status_code == 202
    _assert_response_contract(response, "post", path)


def test_normalized_defaults_and_exact_ids_reach_read_service(http):
    web, boundary = http
    def members(team_id, query):
        assert team_id == "9007199254740993"
        assert query == {"page": 1, "page_size": 20, "include_facets": False, "membership_state": "joined"}
        return {**deepcopy(LIST), "items": []}
    boundary.list_members = members
    assert web.get("/api/teams/9007199254740993/members", headers=AUTH).status_code == 200
    def candidates(team_id, query):
        assert query == {
            "page": 1, "page_size": 20, "include_facets": True, "scope": "unassigned", "archived": "0",
            "has_password": False,
        }
        return {**deepcopy(LIST), "items": [], "facets": {}}
    boundary.list_candidates = candidates
    assert web.get("/api/teams/1/candidates?include_facets=1&has_password=false", headers=AUTH).status_code == 200


@pytest.mark.parametrize(("suffix", "action", "invitation_id", "body"), [
    ("3/continue", "continue", "3", {}),
    ("3/retry", "retry", "3", {}),
    ("continue-bulk", "continue", None, {"invitation_ids": ["3", "3", "5"]}),
    ("retry-bulk", "retry", None, {"invitation_ids": ["3", "3", "5"]}),
])
def test_invitation_execution_targets_and_operation_stay_bound_to_request(http, suffix, action, invitation_id, body):
    web, boundary = http
    def execute(team_id, actual_action, payload, key, invitation_id=None):
        assert team_id == "9007199254740993"
        assert actual_action == action and payload == body and key == KEY
        expected_id = "3" if suffix.startswith("3/") else None
        assert invitation_id == expected_id
        return {**deepcopy(JOIN), "operation": actual_action}
    boundary.invitation_action = execute
    response = web.post(f"/api/teams/9007199254740993/invitations/{suffix}",
                        json=body, headers={**AUTH, "Idempotency-Key": KEY})
    assert response.status_code == 202
    assert response.get_json()["data"]["operation"] == action


def test_read_posts_need_no_idempotency_key_and_do_not_accept_execution_options(http):
    web, _ = http
    assert web.post("/api/teams/1/join-preview", json={"account_ids": ["101"]}, headers=AUTH).status_code == 200
    assert web.post("/api/teams/1/candidates/resolve", json={"values": ["101"]}, headers=AUTH).status_code == 200
    _assert_error(web.post("/api/teams/1/join-preview", json={"account_ids": ["101"], "force": True},
                           headers=AUTH), 422, "field_not_supported", "force")


def test_facets_only_expose_endpoint_business_scope_when_requested(http):
    web, boundary = http
    boundary.list_teams = lambda query: {
        **deepcopy(LIST), "facets": {
            "role": [{"value": "admin", "count": 1, "access_token": "private-token"}],
            "last_sync_status": [{"value": "queued", "count": 1}],
            "email": [{"value": "private-email", "count": 1}],
        },
    }
    hidden = web.get("/api/teams", headers=AUTH)
    assert "facets" not in hidden.get_json()["data"]
    requested = web.get("/api/teams?include_facets=1", headers=AUTH)
    assert requested.get_json()["data"]["facets"] == {
        "role": [{"value": "admin", "count": 1}], "last_sync_status": [{"value": "queued", "count": 1}],
    }
    assert "private-" not in requested.get_data(as_text=True)
    _assert_response_contract(requested, "get", "/api/teams")


def test_member_list_projects_nonempty_nested_account_and_task_dtos(http):
    web, boundary = http
    boundary.list_members = lambda team_id, query: {**deepcopy(LIST), "items": [{
        "id": 9007199254740993, "team_id": 1, "remote_user_id": "remote:opaque",
        "email": "member@example.test", "account": {**ACCOUNT, "id": 9007199254740995, "password": "private-password"},
        "role": "member", "membership_state": "joined", "joined_at": None, "last_verified_at": None,
        "latest_task": {"task_id": 9007199254740997, "run_id": 9007199254740999, "status": "success",
                        "cookie": "private-cookie"},
        "access_token": "private-token",
    }]}
    response = web.get("/api/teams/1/members", headers=AUTH)
    item = response.get_json()["data"]["items"][0]
    assert item["id"] == "9007199254740993" and item["remote_user_id"] == "remote:opaque"
    assert item["account"]["id"] == "9007199254740995"
    assert item["latest_task"]["task_id"] == "9007199254740997"
    assert "private-" not in response.get_data(as_text=True)
    _assert_response_contract(response, "get", "/api/teams/1/members")


def test_invitation_list_keeps_business_facts_separate_from_execution_and_drops_internal_material(http):
    web, boundary = http
    invitation = boundary.get_invitation("1", "3")["invitation"]
    invitation["remote_invitation_id"] = "remote-invitation:opaque"
    invitation["latest_execution"].update(task_id=9007199254740993, run_id=9007199254740995,
                                         status="waiting", stage="accept", waiting_reason_code="waiting_remote")
    invitation["latest_execution"]["raw_response"] = {"access_token": "private-token"}
    invitation["actions"]["continue"]["session"] = "private-session"
    boundary.list_invitations = lambda team_id, query: {**deepcopy(LIST), "items": [invitation]}
    response = web.get("/api/teams/1/invitations", headers=AUTH)
    item = response.get_json()["data"]["items"][0]
    assert item["invitation_state"] == "not_sent" and item["membership_state"] == "unconfirmed"
    assert item["latest_execution"]["status"] == "waiting"
    assert item["latest_execution"]["task_id"] == "9007199254740993"
    assert item["remote_invitation_id"] == "remote-invitation:opaque"
    assert "private-" not in response.get_data(as_text=True)
    _assert_response_contract(response, "get", "/api/teams/1/invitations")


def test_candidate_list_only_returns_public_local_material_flags_and_team_refs(http):
    web, boundary = http
    boundary.list_candidates = lambda team_id, query: {**deepcopy(LIST), "items": [{
        "account": {**ACCOUNT, "access_token": "private-token"}, "category": "new", "auth_capability": "unknown",
        "has_access_token": True, "has_password": False, "totp_enabled": False, "email_status": "unmarked",
        "other_teams": [{"id": 9007199254740993, "workspace_id": "ws:opaque", "name": None,
                         "display_name": "备注", "manager_password": "private-password"}],
        "disabled": False, "reason_code": None, "raw_session": "private-session",
    }]}
    response = web.get("/api/teams/1/candidates?include_facets=1", headers=AUTH)
    data = response.get_json()["data"]
    assert data["items"][0]["other_teams"][0]["id"] == "9007199254740993"
    assert data["items"][0]["auth_capability"] == "unknown" and data["items"][0]["disabled"] is False
    assert data["facets"] == {}
    assert "private-" not in response.get_data(as_text=True)
    _assert_response_contract(response, "get", "/api/teams/1/candidates")


@pytest.mark.parametrize(("path", "body", "field", "code"), [
    ("/api/teams/1/sync", {"workspace_id": "secret"}, "workspace_id", "field_not_supported"),
    ("/api/teams/binding-probes", {"manager_account_id": 1}, "manager_account_id", "parameter_invalid"),
    ("/api/teams/binding-probes", {"manager_account_id": "0"}, "manager_account_id", "parameter_invalid"),
    ("/api/teams", {"manager_account_id": "1", "workspace_id": "ws", "probe_id": "2", "probe_revision": True}, "probe_revision", "parameter_invalid"),
    ("/api/teams/1/join", {"account_ids": []}, "account_ids", "parameter_invalid"),
    ("/api/teams/1/join", {"account_ids": [1]}, "account_ids", "parameter_invalid"),
    ("/api/teams/1/join", {"account_ids": ["1"], "selection_id": "2", "selection_revision": 1}, None, "parameter_invalid"),
    ("/api/teams/1/join", {"selection_id": "2"}, "selection_revision", "parameter_invalid"),
    ("/api/teams/1/join", {"selection_id": "2", "selection_revision": 1, "expected_emails": {"2": "a@example.test"}}, "expected_emails", "parameter_invalid"),
    ("/api/teams/1/join-preview", {"account_ids": ["1"], "expected_emails": {"2": "a@example.test"}}, "expected_emails", "parameter_invalid"),
    ("/api/teams/1/join-preview", {"account_ids": ["1"], "expected_emails": {"1": ""}}, "expected_emails", "parameter_invalid"),
    ("/api/teams/1/candidates/resolve", {"values": [""]}, "values", "parameter_invalid"),
    ("/api/teams/sync-bulk", {"team_ids": ["1"] * 101}, "team_ids", "parameter_invalid"),
])
def test_payload_rejects_unknown_fields_wrong_types_and_invalid_target_modes(http, path, body, field, code):
    web, _ = http
    _assert_error(web.post(path, json=body, headers={**AUTH, "Idempotency-Key": KEY}), 422, code, field)


@pytest.mark.parametrize(("body", "field"), [
    ({"expected_revision": 1}, None),
    ({"expected_revision": 1, "planned_member_limit": 0}, "planned_member_limit"),
    ({"expected_revision": 1, "display_name": "备" * 121}, "display_name"),
    ({"expected_revision": 1, "manager_account_id": "2"}, "probe_id"),
    ({"expected_revision": 1, "display_name": "备注", "probe_id": "2", "probe_revision": 1}, "probe_id"),
    ({"expected_revision": 1, "workspace_id": "ws"}, "workspace_id"),
])
def test_patch_only_accepts_supported_editable_fields_and_valid_probe_pair(http, body, field):
    web, _ = http
    code = "field_not_supported" if field == "workspace_id" else "parameter_invalid"
    _assert_error(web.patch("/api/teams/1", json=body, headers={**AUTH, "Idempotency-Key": KEY}), 422, code, field)


@pytest.mark.parametrize("body", [[], None, "secret", 12])
def test_nonobject_json_is_rejected_without_echoing_input(http, body):
    web, _ = http
    response = web.post("/api/teams/1/sync", data=json.dumps(body), content_type="application/json",
                        headers={**AUTH, "Idempotency-Key": KEY})
    _assert_error(response, 400, "invalid_json")
    assert "secret" not in response.get_data(as_text=True)


def test_malformed_json_and_write_query_options_are_rejected(http):
    web, _ = http
    _assert_error(web.post("/api/teams/1/sync", data="{", content_type="application/json",
                           headers={**AUTH, "Idempotency-Key": KEY}), 400, "invalid_json")
    _assert_error(web.post("/api/teams/1/sync?refresh=1", json={},
                           headers={**AUTH, "Idempotency-Key": KEY}), 422, "field_not_supported", "refresh")


def test_ids_remain_strings_unknown_facts_remain_null_and_credentials_are_not_exposed(http):
    web, boundary = http
    def listing(query):
        row = deepcopy(TEAM)
        row["manager_account"]["password"] = "private-password"
        row["access_token"] = "private-token"
        row["raw_session"] = {"cookie": "private-cookie"}
        return {**deepcopy(LIST), "items": [row]}
    boundary.list_teams = listing
    response = web.get("/api/teams", headers=AUTH)
    value = response.get_json()["data"]["items"][0]
    assert value["id"] == "9007199254740995"
    assert value["manager_account"]["id"] == "9007199254740993"
    assert value["purchased_seats"] == 0 and value["confirmed_member_count"] is None
    assert set(value) == set(TEAM)
    assert set(value["manager_account"]) == {"id", "email", "archived"}
    assert "private-" not in response.get_data(as_text=True)


def test_unexpected_nested_internal_object_cannot_escape_through_a_scalar_dto_field(http):
    web, boundary = http
    boundary.list_teams = lambda query: {
        **deepcopy(LIST), "items": [{**deepcopy(TEAM), "name": {"access_token": "private-token"}}],
    }
    response = web.get("/api/teams", headers=AUTH)
    _assert_error(response, 503, "team_store_unavailable")
    assert "private-token" not in response.get_data(as_text=True)


def test_domain_error_keeps_structured_safe_details_and_unexpected_error_is_classified(http):
    web, boundary = http
    from core.teams.errors import TeamError
    def conflict(team_id, payload, key):
        raise TeamError("revision_conflict", "记录版本已变化。", status=409, field="expected_revision",
                        details={"revision": 2, "access_token": "private-token"})
    boundary.update_team = conflict
    response = web.patch("/api/teams/1", json={"expected_revision": 1, "display_name": "备注"},
                         headers={**AUTH, "Idempotency-Key": KEY})
    error = _assert_error(response, 409, "revision_conflict", "expected_revision")
    assert error["details"] == {"revision": 2}
    def crash(query):
        raise RuntimeError("password=private-password token=private-token")
    boundary.list_teams = crash
    response = web.get("/api/teams", headers=AUTH)
    error = _assert_error(response, 503, "team_store_unavailable")
    assert error["retryable"] is True
    assert "private-" not in response.get_data(as_text=True)
