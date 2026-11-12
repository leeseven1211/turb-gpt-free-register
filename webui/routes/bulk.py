"""批量任务的受控 HTTP 边界，GET 只读本地事实。"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import uuid
import threading
import time
from datetime import datetime, date
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, URLSafeSerializer

from core.accounts.query import AccountQueryError
from core.bulk_operations import service
from core.storage.operations import bulk as store

logger = logging.getLogger(__name__)
_PRIVATE = {"config_snapshot", "request_key", "request_hash", "owner_id", "lease_until", "fence", "query_spec"}
_FACET_CACHE = {}
_FACET_LOCK = threading.Lock()
_ID_KEYS = {"id", "task_id", "run_id", "account_id", "batch_id", "round_id", "selection_id", "target_id",
            "target_round_id", "canonical_target_id", "command_id", "initial_round_id", "member_selection_id",
            "source_run_id_snapshot", "source_task_id", "blocker_run_id", "blocker_task_id", "owned_run_id",
            "latest_requested_round_id", "existing_batch_id"}


def _safe(value, key=""):
    if isinstance(value, dict):
        return {k: _safe(v, k) for k, v in value.items() if k not in _PRIVATE}
    if isinstance(value, (list, tuple)):
        return [_safe(item, key) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if value is not None and (key in _ID_KEYS or key.endswith(("_id", "_ids", "_id_snapshot"))) and isinstance(value, int):
        return str(value)
    return value


def _json(data, status=200):
    payload = {"ok": True, "request_id": getattr(request, "bulk_request_id", uuid.uuid4().hex), "data": _safe(data)}
    response = jsonify(payload)
    response.status_code = status
    if request.method == "GET":
        signature = hashlib.sha256(json.dumps(_safe(data), sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
        response.set_etag(signature)
        response.make_conditional(request)
        response.headers["Cache-Control"] = "private, no-cache"
    return response


def _endpoint(fn):
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        request.bulk_request_id = uuid.uuid4().hex
        try:
            return fn(*args, **kwargs)
        except (store.BulkError, AccountQueryError) as exc:
            status = getattr(exc, "status", 422)
            code = getattr(exc, "code", "query_invalid")
            detail = getattr(exc, "detail", {})
            return jsonify({"ok": False, "request_id": request.bulk_request_id, "error": {
                "code": code, "message": str(exc), "field": getattr(exc, "field", None),
                "retryable": status >= 500, "details": _safe(detail)}}), status
        except ValueError as exc:
            return jsonify({"ok": False, "request_id": request.bulk_request_id,
                            "error": {"code": getattr(exc, "code", "parameter_invalid"), "message": str(exc), "retryable": False}}), 422
        except Exception as exc:
            logger.exception("批量接口暂不可用：request_id=%s exception=%s", request.bulk_request_id, type(exc).__name__)
            return jsonify({"ok": False, "request_id": request.bulk_request_id,
                            "error": {"code": "bulk_store_unavailable", "message": "批量任务存储暂不可用，请稍后重试。", "retryable": True}}), 503
    return wrapped


def _body(allowed):
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise store.BulkError("invalid_json", "请求体必须是 JSON 对象。", 400)
    extra = set(value) - set(allowed)
    if extra:
        raise store.BulkError("field_not_supported", "请求包含不支持的字段。", 422, {"fields": sorted(extra)})
    return value


def _key():
    key = request.headers.get("Idempotency-Key", "").strip()
    if not 16 <= len(key) <= 128:
        raise store.BulkError("invalid_idempotency_key", "必须提供 16 至 128 字符的 Idempotency-Key。", 422)
    return key


def _size(default=50):
    raw = request.args.get("page_size", str(default))
    if not raw.isdigit() or not 1 <= int(raw) <= 100:
        raise store.BulkError("parameter_invalid", "分页大小必须为 1 至 100。", 422)
    return int(raw)


def _serializer():
    return URLSafeSerializer(current_app.secret_key, salt="bulk-pagination-v1")


def _cursor_scope(path, values):
    filters = sorted((key, tuple(value)) for key, value in values.items() if key not in {"cursor", "page_size"})
    return hashlib.sha256(json.dumps([path, filters], ensure_ascii=False).encode()).hexdigest()


def _scope():
    return _cursor_scope(request.path, {key: request.args.getlist(key) for key in request.args})


def _after():
    token = request.args.get("cursor")
    if not token:
        return 0
    try:
        value = _serializer().loads(token)
        if value.get("scope") != _scope():
            raise ValueError
        return int(value["after"])
    except (BadSignature, ValueError, KeyError, TypeError):
        raise store.BulkError("cursor_scope_mismatch", "分页游标不属于当前范围，请刷新列表。", 422) from None


def _page(data):
    data = dict(data)
    page = dict(data.get("page") or {})
    if page.get("next_cursor") is not None:
        page["next_cursor"] = _serializer().dumps({"scope": _scope(), "after": int(page["next_cursor"])})
    page["page_size"] = _size(20 if request.path.endswith("batches") else 50)
    data["page"] = page
    return data


def _selection(data):
    data = dict(data)
    data["selection_at"] = data.get("selection_at") or data.get("selected_at")
    data["preflight"] = {**(data.get("preflight_summary") or {}), "checked_at": data.get("preflight_at")}
    data["effective_settings"] = {**(data.get("config_snapshot") or {}), "config_revision": data.get("config_revision")}
    data["items"] = [dict(row, account_id=row.get("target_id"), target_id=row["id"],
                          display=row.get("display_snapshot") or {}, preflight=(row.get("match_evidence") or {}).get("preflight", {}))
                     for row in data.get("items", data.get("targets", []))]
    data.pop("targets", None)
    data.pop("sample", None)
    return data


def _batch(data, *, round_id=None):
    data = dict(data)
    if round_id is not None:
        round_row = next((item for item in data.get("rounds", []) if int(item["id"]) == round_id), None)
        if round_row is None:
            round_row = store.get_round(int(data["id"]), round_id)
        data.update(counts=round_row.get("counts") or {}, metrics=round_row.get("metrics") or {},
                    target_count=round_row.get("target_count"), summary_revision=round_row.get("summary_revision", 0))
        data["selected_round"] = round_row
    data["summary"] = data.get("counts") or {}
    if data.get("selection_summary"):
        summary = dict(data["selection_summary"])
        summary["selection_at"] = summary.get("selection_at") or summary.get("selected_at")
        data["selection_summary"] = summary
    data["business_summary"] = data.get("metrics") or {}
    data["control"] = {"state": data.get("control_state", data.get("state")), "revision": data.get("control_revision", 1),
                       "paused": bool(data.get("is_paused")),
                       "pending": data.get("control_state", data.get("state")) in {"cancel_requested", "stop_requested"}}
    data["view"] = {"kind": "round" if round_id else "current", "round_id": round_id}
    data["effective_settings"] = {**(data.get("config_snapshot") or {}), "config_revision": data.get("config_revision")}
    data["rounds_head"] = data.get("rounds", [])[:20]
    if data.get("rounds_has_more") and data["rounds_head"]:
        rounds_path = f"/api/bulk/batches/{data['id']}/rounds"
        data["rounds_next_cursor"] = _serializer().dumps({"scope": _cursor_scope(rounds_path, {}),
                                                         "after": data["rounds_head"][-1]["round_no"]})
    data.pop("rounds", None)
    data.setdefault("projection", {"state": "current", "lag_seconds": None})
    return data


def create_bulk_blueprint(_context):
    bp = Blueprint("bulk", __name__)

    @bp.get("/api/bulk/catalog")
    @_endpoint
    def catalog():
        return _json(service.catalog())

    @bp.get("/api/bulk/query-facets")
    @_endpoint
    def query_facets():
        from core.accounts.query import normalize_query, query_hash
        from core.storage import admin_repository, postgres
        try:
            spec = normalize_query(json.loads(request.args.get("query", "{}")))
        except json.JSONDecodeError:
            raise store.BulkError("query_invalid", "查询条件不是有效 JSON。", 422) from None
        cache_key = (postgres.database_url(), postgres.schema_name(), query_hash(spec))
        with _FACET_LOCK:
            cached = _FACET_CACHE.get(cache_key)
        if cached and time.monotonic() - cached[0] < 30:
            data = cached[1]
        else:
            data = {"facets": admin_repository.account_query_facets(spec), "as_of": datetime.now().astimezone().isoformat()}
            try:
                data["matched"] = admin_repository.account_query_count(spec)
            except Exception:
                data["matched"] = None
            with _FACET_LOCK:
                if len(_FACET_CACHE) >= 128:
                    _FACET_CACHE.clear()
                _FACET_CACHE[cache_key] = (time.monotonic(), data)
        return _json(data)

    @bp.post("/api/bulk/selections")
    @_endpoint
    def create_selection():
        return _json(_selection(service.create_selection(_body({"operation", "source", "parameters", "expected_config_revision"}), _key())), 202)

    @bp.get("/api/bulk/selections/<int:selection_id>")
    @bp.get("/api/bulk/selections/<int:selection_id>/targets")
    @_endpoint
    def get_selection(selection_id):
        return _json(_page(_selection(store.get_selection(selection_id, limit=_size(20), after_ordinal=_after()))))

    @bp.post("/api/bulk/batches")
    @_endpoint
    def create_batch():
        return _json(_batch(service.create_batch(_body({"name", "selection_id", "selection_revision", "operation", "expected_config_revision", "parameters", "execution"}), _key())), 202)

    @bp.get("/api/bulk/batches")
    @_endpoint
    def list_batches():
        data = store.list_batches(limit=_size(20), after_id=_after() or None,
            operation_key=request.args.getlist("operation_key[]") or request.args.get("operation_key"),
            control_state=request.args.getlist("control_state[]") or request.args.get("control_state"),
            q=request.args.get("q", ""), created_from=request.args.get("created_from"), created_to=request.args.get("created_to"))
        data["items"] = [_batch(item) for item in data["items"]]
        return _json(_page(data))

    @bp.get("/api/bulk/batches/<int:batch_id>")
    @_endpoint
    def get_batch(batch_id):
        view = request.args.get("view", "current")
        if view not in {"current", "round"}:
            raise store.BulkError("parameter_invalid", "结果视图无效。", 422)
        round_id = service._id(request.args.get("round_id"), "round_id") if view == "round" else None
        return _json(_batch(store.get_batch(batch_id), round_id=round_id))

    @bp.get("/api/bulk/batches/<int:batch_id>/targets")
    @_endpoint
    def targets(batch_id):
        round_id = service._id(request.args.get("round_id"), "round_id") if request.args.get("view") == "round" else None
        states = request.args.getlist("state[]") or request.args.getlist("state")
        result_filters = request.args.get("result_filters")
        try:
            result_filters = json.loads(result_filters) if result_filters else None
        except json.JSONDecodeError:
            raise store.BulkError("parameter_invalid", "结果筛选不是有效 JSON。", 422) from None
        data = store.list_targets(batch_id, round_id=round_id, limit=_size(), after_ordinal=_after(), outcomes=states,
                                  q=request.args.get("q", ""), reason_codes=request.args.getlist("reason_code[]"),
                                  result_filters=result_filters)
        data["items"] = [dict(row, canonical_target_id=row["id"], target_id=row["id"], state=row["outcome"],
                              display=row.get("display_snapshot") or {}) for row in data["items"]]
        return _json(_page(data))

    @bp.get("/api/bulk/batches/<int:batch_id>/rounds")
    @_endpoint
    def rounds(batch_id):
        return _json(_page(store.list_rounds(batch_id, limit=_size(20), after_round_no=_after() or None)))

    @bp.post("/api/bulk/batches/<int:batch_id>/rounds")
    @_endpoint
    def create_round(batch_id):
        return _json(service.create_round(batch_id, _body({"source", "selection", "retry_mode", "name"}), _key()), 202)

    @bp.post("/api/bulk/batches/<int:batch_id>/control")
    @_endpoint
    def control(batch_id):
        return _json(service.request_control(batch_id, _body({"action", "expected_control_revision", "scope"}), _key()), 202)

    return bp
