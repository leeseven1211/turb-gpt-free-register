"""Team 管理的认证 HTTP 边界与公开 DTO 投影。"""
from __future__ import annotations

from datetime import date, datetime
import functools
import logging
import uuid

from flask import Blueprint, jsonify, request

from core.teams import service
from core.teams.errors import TeamError
from core.teams.validation import idempotency_key, local_id, validate_payload, validate_query


logger = logging.getLogger(__name__)
_LOCAL_IDS = {
    "id", "team_id", "account_id", "probe_id", "invitation_id", "member_id", "join_request_id",
    "selection_id", "task_id", "run_id", "batch_id", "existing_team_id", "existing_join_request_id",
}
_DETAIL_FIELDS = {
    "existing_team_id", "existing_join_request_id", "revision", "team_id", "account_id", "probe_id",
    "invitation_id", "join_request_id", "selection_id", "workspace_id", "expected_revision",
    "probe_revision", "selection_revision", "fields", "unsupported_fields", "allowed_fields", "minimum", "maximum",
}


def _fields(names):
    return {name: None for name in names.split()}


_ACCOUNT = _fields("id email archived")
_TEAM_REF = _fields("id workspace_id name display_name")
_TASK = _fields("task_id run_id status")
_ERROR_INFO = _fields("code message stage retryable")
_ALLOWED = _fields("enabled reason_code")
_TEAM = {
    **_fields("id workspace_id name display_name role purchased_seats planned_member_limit "
              "confirmed_member_count pending_invite_count processing_count last_synced_at last_sync_status revision"),
    "manager_account": _ACCOUNT,
}
_ACTION = _fields("accepted reused team_id task_id run_id status")
_MEMBER = {
    **_fields("id team_id remote_user_id email role membership_state joined_at last_verified_at"),
    "account": _ACCOUNT, "latest_task": _TASK,
}
_INVITATION = {
    **_fields("id team_id remote_invitation_id email_snapshot invitation_state membership_state updated_at last_verified_at"),
    "account": _ACCOUNT,
    "latest_execution": {
        **_fields("task_id run_id status stage waiting_reason_code"), "error_info": _ERROR_INFO,
    },
    "actions": {"continue": _ALLOWED, "retry": _ALLOWED, "view_task": _ALLOWED},
}
_CANDIDATE = {
    **_fields("category auth_capability has_access_token has_password totp_enabled email_status disabled reason_code"),
    "account": _ACCOUNT, "other_teams": [_TEAM_REF],
}
_CAPACITY = _fields("basis purchased_seats planned_member_limit effective_limit occupied_count available_count "
                    "additional_required can_submit blocking_reason_code")
_JOIN_COUNTS = _fields("requested_count unique_count duplicate_count pending_count accepted_count reused_count "
                       "skipped_count failed_count")
_JOIN = {
    **_fields("id team_id operation accepted reused status waiting_reason_code selection_id selection_revision "
              "batch_id task_id run_id created_at items_url"),
    "counts": _JOIN_COUNTS, "capacity": _CAPACITY,
}
_JOIN_ITEM = _fields("ordinal account_id invitation_id acceptance_status task_id run_id execution_status reason_code message")
_PROBE = {
    **_fields("id revision status stage task_id run_id suggested_workspace_id completed_at expires_at"),
    "manager_account": _ACCOUNT, "error_info": _ERROR_INFO,
    "workspaces": [{
        **_fields("workspace_id workspace_type name role can_manage purchased_seats"),
        "capabilities": _fields("read_members read_invitations invite_members"),
    }],
}
_PREVIEW = {
    **_fields("team_id selection_id selection_revision snapshot_revision snapshot_at team_last_synced_at requires_sync"),
    "counts": _fields("requested_count unique_count duplicate_count unavailable_count another_team_count "
                      "already_member_count same_team_active_count missing_auth_count resume_invite_count "
                      "new_count eligible_count"),
    "capacity": _CAPACITY,
}
_BULK_SYNC = {
    **_fields("accepted batch_id requested_count unique_count duplicate_count reused_count accepted_count skipped_count failed_count"),
    "items": [_fields("team_id task_id run_id acceptance_status execution_status reason_code")],
}
_RESOLVE = {
    **_fields("requested_count unique_count duplicate_count"),
    "items": [{**_fields("input match_status reason_code"), "candidates": [_CANDIDATE]}],
}
_TEAM_DETAIL = {
    "team": _TEAM, "actions": {"sync": _ALLOWED, "reverify": _ALLOWED, "join": _ALLOWED},
    "permission_verified_at": None,
}


def _project(value, shape=None, *, key=""):
    """按窄对象白名单序列化，未知内部字段不进入 API。"""
    if value is None:
        return None
    if isinstance(shape, dict):
        return {field: _project(value[field], child, key=field)
                for field, child in shape.items() if field in value}
    if isinstance(shape, list):
        return [_project(item, shape[0]) for item in value]
    if isinstance(value, (dict, list, tuple, set)):
        raise TypeError("Team DTO 标量字段不能包含内部对象。")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if key in _LOCAL_IDS and type(value) is int:
        return str(value)
    return value


def _request_id():
    if not getattr(request, "team_request_id", None):
        request.team_request_id = uuid.uuid4().hex
    return request.team_request_id


def _json(data, shape, status=200):
    return jsonify({"ok": True, "request_id": _request_id(), "data": _project(data, shape)}), status


def _error(code, message, status, *, field=None, retryable=False, details=None):
    safe_details = {}
    for key, value in (details or {}).items():
        if key not in _DETAIL_FIELDS:
            continue
        if key in {"fields", "unsupported_fields", "allowed_fields"}:
            if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
                safe_details[key] = list(value)
        elif key in _LOCAL_IDS:
            if (isinstance(value, str) and value.isascii() and value.isdecimal()) or type(value) is int:
                safe_details[key] = str(value)
        elif key == "workspace_id":
            if isinstance(value, str):
                safe_details[key] = value
        elif type(value) is int:
            safe_details[key] = value
    return jsonify({
        "ok": False, "request_id": _request_id(),
        "error": {"code": code, "message": message, "field": field, "retryable": retryable, "details": safe_details},
    }), status


def _endpoint(fn):
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        _request_id()
        try:
            for field, value in kwargs.items():
                local_id(value, field)
            return fn(*args, **kwargs)
        except TeamError as exc:
            return _error(exc.code, exc.message, exc.status, field=exc.field,
                          retryable=exc.retryable, details=exc.details)
        except Exception as exc:
            logger.error("Team 接口暂不可用：request_id=%s exception=%s", _request_id(), type(exc).__name__)
            return _error("team_store_unavailable", "Team 存储暂不可用，请稍后重试。", 503, retryable=True)
    return wrapped


def _query(kind):
    return validate_query(kind, request.args.to_dict(flat=False))


def _payload(kind, *, write=True):
    _query("empty")
    empty_body = not request.get_data(cache=True)
    body = {} if empty_body and kind in {"sync", "reverify", "invitation"} else request.get_json(silent=True)
    payload = validate_payload(kind, body)
    if write:
        return payload, idempotency_key(request.headers.get("Idempotency-Key"), body)
    return payload


def _page(data, item_shape, *, facets=()):
    shape = {
        **_fields("total page page_size revision"),
        "items": [item_shape],
    }
    if request.args.get("include_facets") == "1":
        shape["facets"] = {field: [_fields("value count")] for field in facets}
        data = {**data, "facets": data.get("facets") or {}}
    if data.get("revision") is not None:
        data = {**data, "revision": str(data["revision"])}
    return _json(data, shape)


def create_teams_blueprint(_context):
    bp = Blueprint("teams", __name__)

    @bp.after_request
    def normalize_auth_error(response):
        if response.status_code in {401, 403}:
            value = response.get_json(silent=True)
            if not isinstance(value, dict) or not isinstance(value.get("error"), dict):
                code = "authentication_required" if response.status_code == 401 else "access_denied"
                message = "请先登录或提供有效授权码。" if response.status_code == 401 else "没有访问此接口的权限。"
                normalized, status = _error(code, message, response.status_code)
                normalized.status_code = status
                return normalized
        return response

    @bp.get("/api/teams")
    @_endpoint
    def list_teams():
        return _page(service.list_teams(_query("teams")), _TEAM, facets=("role", "last_sync_status"))

    @bp.get("/api/teams/<team_id>")
    @_endpoint
    def get_team(team_id):
        _query("empty")
        return _json(service.get_team(team_id), _TEAM_DETAIL)

    @bp.post("/api/teams/binding-probes")
    @_endpoint
    def start_probe():
        payload, key = _payload("probe")
        return _json(service.start_probe(payload, key), _fields("probe_id status task_id run_id"), 202)

    @bp.get("/api/teams/binding-probes/<probe_id>")
    @_endpoint
    def get_probe(probe_id):
        _query("empty")
        return _json(service.get_probe(probe_id), _PROBE)

    @bp.post("/api/teams")
    @_endpoint
    def create_team():
        payload, key = _payload("create")
        return _json(service.create_team(payload, key), {"team": _TEAM, "sync": _ACTION}, 201)

    @bp.patch("/api/teams/<team_id>")
    @_endpoint
    def update_team(team_id):
        payload, key = _payload("update")
        return _json(service.update_team(team_id, payload, key), {"team": _TEAM})

    @bp.post("/api/teams/<team_id>/sync")
    @_endpoint
    def sync_team(team_id):
        payload, key = _payload("sync")
        return _json(service.sync_team(team_id, payload, key), _ACTION, 202)

    @bp.post("/api/teams/sync-bulk")
    @_endpoint
    def sync_bulk():
        payload, key = _payload("sync_bulk")
        return _json(service.sync_bulk(payload, key), _BULK_SYNC, 202)

    @bp.post("/api/teams/<team_id>/reverify")
    @_endpoint
    def reverify(team_id):
        payload, key = _payload("reverify")
        return _json(service.reverify(team_id, payload, key), _ACTION, 202)

    @bp.get("/api/teams/<team_id>/members")
    @_endpoint
    def list_members(team_id):
        return _page(service.list_members(team_id, _query("members")), _MEMBER,
                     facets=("membership_state", "role", "linked"))

    @bp.get("/api/teams/<team_id>/invitations")
    @_endpoint
    def list_invitations(team_id):
        return _page(service.list_invitations(team_id, _query("invitations")), _INVITATION,
                     facets=("invitation_state", "membership_state", "execution_status", "stage"))

    @bp.get("/api/teams/<team_id>/invitations/<invitation_id>")
    @_endpoint
    def get_invitation(team_id, invitation_id):
        _query("empty")
        return _json(service.get_invitation(team_id, invitation_id), {"invitation": _INVITATION})

    @bp.get("/api/teams/<team_id>/candidates")
    @_endpoint
    def list_candidates(team_id):
        return _page(service.list_candidates(team_id, _query("candidates")), _CANDIDATE)

    @bp.post("/api/teams/<team_id>/candidates/resolve")
    @_endpoint
    def resolve_candidates(team_id):
        return _json(service.resolve_candidates(team_id, _payload("resolve", write=False)), _RESOLVE)

    @bp.post("/api/teams/<team_id>/join-preview")
    @_endpoint
    def preview_join(team_id):
        return _json(service.preview_join(team_id, _payload("preview", write=False)), _PREVIEW)

    @bp.post("/api/teams/<team_id>/join")
    @_endpoint
    def submit_join(team_id):
        payload, key = _payload("join")
        return _json(service.submit_join(team_id, payload, key), _JOIN, 202)

    @bp.get("/api/teams/<team_id>/join-requests/<join_request_id>")
    @_endpoint
    def get_join_request(team_id, join_request_id):
        query = _query("join_items")
        data = service.get_join_request(team_id, join_request_id, query)
        if data.get("revision") is not None:
            data = {**data, "revision": str(data["revision"])}
        if query["include_facets"]:
            data = {**data, "facets": {}}
        return _json(data, {
            "request": _JOIN, "items": [_JOIN_ITEM], **_fields("total page page_size revision"),
            **({"facets": {}} if query["include_facets"] else {}),
        })

    @bp.post("/api/teams/<team_id>/invitations/<invitation_id>/continue")
    @_endpoint
    def continue_invitation(team_id, invitation_id):
        payload, key = _payload("invitation")
        return _json(service.invitation_action(team_id, "continue", payload, key, invitation_id=invitation_id), _JOIN, 202)

    @bp.post("/api/teams/<team_id>/invitations/<invitation_id>/retry")
    @_endpoint
    def retry_invitation(team_id, invitation_id):
        payload, key = _payload("invitation")
        return _json(service.invitation_action(team_id, "retry", payload, key, invitation_id=invitation_id), _JOIN, 202)

    @bp.post("/api/teams/<team_id>/invitations/continue-bulk")
    @_endpoint
    def continue_bulk(team_id):
        payload, key = _payload("invitation_bulk")
        return _json(service.invitation_action(team_id, "continue", payload, key), _JOIN, 202)

    @bp.post("/api/teams/<team_id>/invitations/retry-bulk")
    @_endpoint
    def retry_bulk(team_id):
        payload, key = _payload("invitation_bulk")
        return _json(service.invitation_action(team_id, "retry", payload, key), _JOIN, 202)

    return bp
