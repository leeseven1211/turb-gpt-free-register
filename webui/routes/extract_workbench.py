# -*- coding: utf-8 -*-
"""提链工作台安全 API。"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from flask import jsonify, request

from core import extract_link_service
from webui.blueprint import LegacyEndpointBlueprint
from webui.runtime import WebUIContext

logger = logging.getLogger(__name__)

_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_MODES = {"extract_only", "manual_payment", "auto_payment"}
_ACTIONS = {"sync_status", "retry", "manual_payment", "auto_payment"}
_LINK_KINDS = {"extract", "payment"}
_MAX_ACCOUNT_IDS = 500
_MAX_PAGE_SIZE = 200
_MAX_BATCH_SIZE = 5000
_MAX_BATCH_WORKERS = 16
_CANDIDATE_FILTER_FIELDS = {"query", "source", "date_from", "date_to", "extract_status"}
_EXTRACT_STATUSES = {"not_succeeded", "all", "failed", "never", "success"}
_BATCH_COUNT_FIELDS = (
    "all", "processing", "running", "extraction_succeeded", "payment_succeeded",
    "plus_confirmed", "needs_attention",
)
_ITEM_FIELDS = (
    "task_id", "run_id", "account_id", "batch_id", "email", "provider_id", "mode", "link_type", "task_status",
    "preflight_status", "extraction_status", "payment_status", "plus_status",
    "run_count", "progress", "created_at", "updated_at", "message", "error",
    "has_extract_link", "has_payment_link",
)
_PRIVATE_KEY_NAMES = {
    "accesstoken", "refreshtoken", "idtoken", "at", "token", "authorization",
    "cdk", "jobsecret", "privatedata", "apikey", "clientsecret", "credential",
}


def _error(message: str, status: int):
    return jsonify({"ok": False, "error": message}), status


def _valid_identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER_RE.fullmatch(value) is not None


def _contains_private_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = re.sub(r"[_-]", "", str(key)).lower()
            if (
                normalized in _PRIVATE_KEY_NAMES
                or "token" in normalized
                or "secret" in normalized
                or "credential" in normalized
                or _contains_private_key(nested)
            ):
                return True
    elif isinstance(value, list):
        return any(_contains_private_key(item) for item in value)
    return False


def _safe_tree(value: Any) -> Any:
    """从服务投影中剔除任何意外混入的凭据字段。"""
    if isinstance(value, dict):
        result = {}
        for key, nested in value.items():
            normalized = re.sub(r"[_-]", "", str(key)).lower()
            if (
                normalized in _PRIVATE_KEY_NAMES
                or "token" in normalized
                or "secret" in normalized
                or "credential" in normalized
            ):
                continue
            result[key] = _safe_tree(nested)
        return result
    if isinstance(value, list):
        return [_safe_tree(item) for item in value]
    return value


def _public_item(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return _safe_tree({key: value[key] for key in _ITEM_FIELDS if key in value})


def _safe_count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _public_batch(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or _safe_count(value.get("batch_id")) < 1:
        return None
    workers = value.get("workers")
    result = {"batch_id": value["batch_id"], "workers": workers if _valid_batch_workers(workers) else None}
    for field in ("title", "provider_id", "mode", "status", "created_at"):
        if field in value:
            result[field] = value[field]
    for field in ("requested_count", "started_count", "skipped_count", "submission_failed_count"):
        result[field] = _safe_count(value.get(field))
    result["submission_incomplete"] = value.get("submission_incomplete") is True
    counts = value.get("counts") if isinstance(value.get("counts"), dict) else {}
    result["counts"] = {field: _safe_count(counts.get(field)) for field in _BATCH_COUNT_FIELDS}
    return _safe_tree(result)


def _candidate_filters(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict) or set(value) - _CANDIDATE_FILTER_FIELDS:
        return None
    result = {}
    for field, maximum in (("query", 200), ("source", 80), ("date_from", 10), ("date_to", 10), ("extract_status", 20)):
        raw = value.get(field, "")
        if not isinstance(raw, str) or len(raw) > maximum:
            return None
        result[field] = raw.strip()
    result["extract_status"] = result["extract_status"] or "not_succeeded"
    if result["extract_status"] not in _EXTRACT_STATUSES:
        return None
    for field in ("date_from", "date_to"):
        if result[field]:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", result[field]):
                return None
            try:
                date.fromisoformat(result[field])
            except ValueError:
                return None
    if result["date_from"] and result["date_to"] and result["date_from"] > result["date_to"]:
        return None
    return result


def _valid_batch_workers(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= _MAX_BATCH_WORKERS


def _public_config(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or not isinstance(value.get("providers"), list):
        return None
    providers = []
    for provider in value["providers"]:
        if not isinstance(provider, dict) or not _valid_identifier(provider.get("id")):
            continue
        modes = provider.get("modes")
        if not isinstance(modes, list):
            modes = []
        providers.append({
            "id": provider["id"],
            "label": provider.get("label") if isinstance(provider.get("label"), str) else provider["id"],
            "default_type": provider.get("default_type") if isinstance(provider.get("default_type"), str) else "",
            "modes": [mode for mode in modes if isinstance(mode, str) and mode in _MODES],
        })
    default_provider = value.get("default_provider")
    default_mode = value.get("default_mode")
    return {
        "default_provider": default_provider if _valid_identifier(default_provider) else "",
        "default_mode": default_mode if isinstance(default_mode, str) and default_mode in _MODES else "",
        "providers": providers,
        "batch_workers_default": value.get("batch_workers_default") if _valid_batch_workers(value.get("batch_workers_default")) else 1,
        "batch_workers_max": _MAX_BATCH_WORKERS,
    }


def _pagination_arg(name: str, default: int, maximum: int) -> int | None:
    raw = request.args.get(name)
    if raw is None:
        return default
    if not re.fullmatch(r"[0-9]+", raw):
        return None
    value = int(raw)
    if value < 1 or value > maximum:
        return None
    return value


def _parse_object_body(allowed_keys: set[str]) -> tuple[dict[str, Any] | None, Any | None]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, _error("请求体必须是 JSON 对象", 400)
    if set(data) - allowed_keys:
        return None, _error("请求包含不支持的字段", 400)
    if _contains_private_key(data):
        return None, _error("请求不能包含账号凭据或平台密钥", 400)
    return data, None


def _service_error(operation: str, exc: Exception):
    # 异常文本可能包含远端响应或认证信息，因此日志和响应都只保留类型。
    logger.warning("提链工作台%s失败：%s", operation, type(exc).__name__)
    return _error("提链工作台暂时不可用，请稍后重试", 503)


def create_extract_workbench_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("extract_workbench", __name__)

    @bp.get("/api/extract-workbench/config")
    def extract_workbench_config():
        try:
            result = extract_link_service.workbench_config()
        except Exception as exc:
            return _service_error("配置读取", exc)
        public = _public_config(result)
        if public is None:
            return _error("提链工作台配置暂不可用", 503)
        return jsonify(public)

    @bp.get("/api/extract-workbench/candidates")
    def extract_workbench_candidates():
        if set(request.args) - (_CANDIDATE_FILTER_FIELDS | {"limit"}):
            return _error("筛选条件包含不支持的字段", 400)
        filters = _candidate_filters({key: request.args[key] for key in _CANDIDATE_FILTER_FIELDS if key in request.args})
        limit = _pagination_arg("limit", 100, _MAX_BATCH_SIZE)
        if filters is None or limit is None:
            return _error("账号筛选条件或运行数量无效", 400)
        try:
            result = extract_link_service.preview_workbench_candidates(filters=filters, limit=limit)
        except ValueError:
            return _error("账号筛选条件或运行数量无效", 400)
        except Exception as exc:
            return _service_error("候选账号读取", exc)
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            return _error("候选账号暂不可用", 503)
        items = []
        for item in result["items"]:
            if not isinstance(item, dict) or _safe_count(item.get("account_id")) < 1:
                continue
            items.append(_safe_tree({
                key: item[key] for key in ("account_id", "email", "created_at", "email_source", "extract_link_status")
                if key in item
            }))
        return jsonify({
            "total": _safe_count(result.get("total")),
            "selected_count": _safe_count(result.get("selected_count")),
            "limit": limit,
            "max_batch_size": _MAX_BATCH_SIZE,
            "items": items,
        })

    @bp.get("/api/extract-workbench/batches")
    def extract_workbench_batches():
        page = _pagination_arg("page", 1, 1_000_000)
        page_size = _pagination_arg("page_size", 20, _MAX_PAGE_SIZE)
        if page is None or page_size is None:
            return _error("分页参数无效", 400)
        try:
            result = extract_link_service.list_workbench_batches(page=page, page_size=page_size)
        except Exception as exc:
            return _service_error("批次读取", exc)
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            return _error("提链批次暂不可用", 503)
        items = [_public_batch(item) for item in result["items"]]
        return jsonify({
            "items": [item for item in items if item is not None],
            "total": _safe_count(result.get("total")),
            "page": page,
            "page_size": page_size,
        })

    @bp.get("/api/extract-workbench/batches/<int:batch_id>")
    def extract_workbench_batch_detail(batch_id: int):
        if batch_id < 1:
            return _error("batch_id 参数无效", 400)
        try:
            result = extract_link_service.workbench_batch_detail(batch_id)
        except Exception as exc:
            return _service_error("批次详情读取", exc)
        if result is None:
            return _error("批次不存在", 404)
        item = _public_batch(result)
        if item is None:
            return _error("提链批次详情暂不可用", 503)
        return jsonify({"item": item})

    @bp.post("/api/extract-workbench/batches")
    def create_extract_workbench_batch():
        data, error = _parse_object_body({"title", "provider_id", "mode", "type", "options", "filters", "limit", "submission_id", "workers"})
        if error is not None:
            return error
        title = data.get("title", "")
        submission_id = data.get("submission_id")
        if not isinstance(submission_id, str) or len(submission_id) != 36:
            return _error("submission_id 必须是标准 UUID", 400)
        try:
            canonical_submission_id = str(UUID(submission_id))
        except ValueError:
            return _error("submission_id 必须是标准 UUID", 400)
        if canonical_submission_id != submission_id.lower():
            return _error("submission_id 必须是标准 UUID", 400)
        provider_id, mode = data.get("provider_id"), data.get("mode")
        filters = _candidate_filters(data.get("filters", {}))
        limit = data.get("limit", 100)
        link_type, options = data.get("type"), data.get("options", {})
        if "workers" in data and not _valid_batch_workers(data["workers"]):
            return _error("批次并发必须是 1 到 16 的整数", 400)
        if not isinstance(title, str) or len(title) > 120:
            return _error("批次名称最多 120 个字符", 400)
        if not _valid_identifier(provider_id) or not isinstance(mode, str) or mode not in _MODES:
            return _error("平台或运行模式无效", 400)
        if filters is None or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_BATCH_SIZE:
            return _error("账号筛选条件或运行数量无效", 400)
        if link_type is not None and (not isinstance(link_type, str) or len(link_type) > 80):
            return _error("type 参数无效", 400)
        if not isinstance(options, dict):
            return _error("options 必须是 JSON 对象", 400)
        payload = {
            "title": title.strip(), "provider_id": provider_id, "mode": mode,
            "filters": filters, "limit": limit, "options": options,
            "submission_id": canonical_submission_id,
        }
        if link_type is not None:
            payload["type"] = link_type
        if "workers" in data:
            payload["workers"] = data["workers"]
        try:
            result = extract_link_service.create_workbench_batch(**payload)
        except ValueError:
            return _error("批次未创建，请检查筛选条件、平台能力和运行数量", 400)
        except Exception as exc:
            return _service_error("批次提交", exc)
        if not isinstance(result, dict) or _safe_count(result.get("batch_id")) < 1:
            return _error("提链工作台未能创建批次", 503)
        counts = {name: _safe_count(result.get(name)) for name in ("requested", "started", "skipped", "failed")}
        return jsonify({"ok": True, "batch_id": result["batch_id"], **counts}), 202 if counts["started"] else 200

    @bp.get("/api/extract-workbench/tasks")
    def extract_workbench_tasks():
        provider_id = request.args.get("provider_id") or None
        mode = request.args.get("mode") or None
        status = request.args.get("status") or None
        query = request.args.get("query", "")
        page = _pagination_arg("page", 1, 1_000_000)
        page_size = _pagination_arg("page_size", 50, _MAX_PAGE_SIZE)
        batch_id = _pagination_arg("batch_id", 0, 2**63 - 1) if "batch_id" in request.args else None
        if "batch_id" in request.args and batch_id is None:
            return _error("batch_id 参数无效", 400)
        if page is None or page_size is None:
            return _error("分页参数无效", 400)
        if provider_id is not None and not _valid_identifier(provider_id):
            return _error("provider_id 参数无效", 400)
        if mode is not None and mode not in _MODES:
            return _error("mode 参数无效", 400)
        if status is not None and not _valid_identifier(status):
            return _error("status 参数无效", 400)
        if len(query) > 200:
            return _error("query 最多 200 个字符", 400)
        try:
            payload = dict(
                provider_id=provider_id,
                mode=mode,
                status=status,
                query=query,
                page=page,
                page_size=page_size,
            )
            if batch_id is not None:
                payload["batch_id"] = batch_id
            result = extract_link_service.list_workbench_tasks(**payload)
        except Exception as exc:
            return _service_error("任务读取", exc)
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            return _error("提链工作台任务暂不可用", 503)
        items = [_public_item(item) for item in result["items"]]
        counts = result.get("counts")
        if not isinstance(counts, dict):
            counts = {}
        safe_counts = {
            str(key): count for key, count in counts.items()
            if (
                _valid_identifier(key)
                and isinstance(count, int)
                and not isinstance(count, bool)
                and count >= 0
            )
        }
        total = result.get("total")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            total = 0
        return jsonify({
            "items": [item for item in items if item is not None],
            "total": total,
            "page": page,
            "page_size": page_size,
            "counts": safe_counts,
        })

    @bp.post("/api/extract-workbench/tasks")
    def create_extract_workbench_tasks():
        data, error = _parse_object_body({"account_ids", "provider_id", "mode", "type", "options"})
        if error is not None:
            return error
        raw_account_ids = data.get("account_ids")
        provider_id = data.get("provider_id")
        mode = data.get("mode")
        link_type = data.get("type")
        options = data.get("options", {})
        if (
            not isinstance(raw_account_ids, list)
            or not raw_account_ids
            or len(raw_account_ids) > _MAX_ACCOUNT_IDS
        ):
            return _error("account_ids 必须是 1 至 500 个不重复的正整数", 400)
        account_ids = []
        for value in raw_account_ids:
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                account_ids.append(value)
            elif isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value):
                account_ids.append(int(value))
            else:
                return _error("account_ids 必须是 1 至 500 个不重复的正整数", 400)
        if len(set(account_ids)) != len(account_ids):
            return _error("account_ids 必须是 1 至 500 个不重复的正整数", 400)
        if not _valid_identifier(provider_id):
            return _error("provider_id 参数无效", 400)
        if not isinstance(mode, str) or mode not in _MODES:
            return _error("mode 参数无效", 400)
        if link_type is not None and (not isinstance(link_type, str) or len(link_type) > 80):
            return _error("type 参数无效", 400)
        if not isinstance(options, dict):
            return _error("options 必须是 JSON 对象", 400)
        payload: dict[str, Any] = {
            "account_ids": account_ids,
            "provider_id": provider_id,
            "mode": mode,
            "options": options,
        }
        if link_type is not None:
            payload["type"] = link_type
        try:
            result = extract_link_service.create_workbench_tasks(**payload)
        except Exception as exc:
            return _service_error("任务提交", exc)
        if not isinstance(result, dict):
            return _error("提链工作台未能提交任务", 503)
        counts = {}
        for name in ("started", "skipped", "failed"):
            value = result.get(name, 0)
            counts[name] = value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
        return jsonify({"ok": True, **counts}), 202 if counts["started"] else 200

    @bp.get("/api/extract-workbench/tasks/<int:task_id>")
    def extract_workbench_task_detail(task_id: int):
        if task_id < 1:
            return _error("task_id 参数无效", 400)
        try:
            result = extract_link_service.extract_workbench_task_detail(task_id)
        except Exception as exc:
            return _service_error("任务详情读取", exc)
        if result is None:
            return _error("任务不存在", 404)
        if not isinstance(result, dict):
            return _error("提链工作台任务详情暂不可用", 503)
        item = _public_item(result.get("item"))
        if item is None:
            return _error("任务不存在", 404)
        history = result.get("history", [])
        events = result.get("events", [])
        if not isinstance(history, list):
            history = []
        if not isinstance(events, list):
            events = []
        return jsonify({
            "item": item,
            "history": _safe_tree(history),
            "events": _safe_tree(events),
        })

    @bp.post("/api/extract-workbench/tasks/<int:task_id>/actions")
    def perform_extract_workbench_action(task_id: int):
        if task_id < 1:
            return _error("task_id 参数无效", 400)
        data, error = _parse_object_body({"action"})
        if error is not None:
            return error
        action = data.get("action")
        if not isinstance(action, str) or action not in _ACTIONS:
            return _error("action 参数无效", 400)
        try:
            result = extract_link_service.perform_extract_workbench_action(task_id, action)
        except Exception as exc:
            return _service_error("任务操作", exc)
        if not isinstance(result, dict):
            return _error("提链工作台未能接受该操作", 503)
        accepted = result.get("accepted") is True
        payload = {
            "ok": accepted,
            "accepted": accepted,
            "task_id": result.get("task_id")
            if isinstance(result.get("task_id"), int) and not isinstance(result.get("task_id"), bool)
            else task_id,
            "run_id": result.get("run_id")
            if isinstance(result.get("run_id"), int) and not isinstance(result.get("run_id"), bool)
            else None,
        }
        if not accepted:
            payload["error"] = "操作未接受，请刷新任务状态并检查配置"
        return jsonify(payload), 202 if accepted else 409

    @bp.post("/api/extract-workbench/tasks/<int:task_id>/links")
    def extract_workbench_task_link(task_id: int):
        if task_id < 1:
            return _error("task_id 参数无效", 400)
        data, error = _parse_object_body({"kind"})
        if error is not None:
            return error
        kind = data.get("kind")
        if not isinstance(kind, str) or kind not in _LINK_KINDS:
            return _error("kind 参数无效", 400)
        try:
            result = extract_link_service.extract_workbench_task_link(task_id, kind)
        except Exception as exc:
            return _service_error("链接读取", exc)
        if result is None:
            return _error("当前任务没有可用链接", 404)
        url = result.get("url") if isinstance(result, dict) else result
        if not isinstance(url, str):
            return _error("当前任务没有可用链接", 404)
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            return _error("当前任务链接格式无效", 502)
        return jsonify({"ok": True, "url": url})

    return bp
