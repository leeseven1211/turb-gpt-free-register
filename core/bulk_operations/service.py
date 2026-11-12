"""批量任务受理与可恢复协调；真实执行仍由原任务网关负责。"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Mapping

from core.accounts.query import AccountQueryError, normalize_query, compile_query, query_schema

logger = logging.getLogger(__name__)
_STOP = threading.Event()
_WAKE = threading.Event()
_LOCK = threading.RLock()
_THREADS: dict[str, threading.Thread] = {}
_STATUS: dict[str, dict] = {}
_OWNER = uuid.uuid4().hex
_LAST_MAINTENANCE = 0.0


def _store():
    from core.storage.operations import bulk
    return bulk


def _catalog():
    from core.bulk_operations import catalog
    return catalog


def _error(code: str, message: str, status=422, **detail):
    return _store().BulkError(code, message, status=status, detail=detail)


def catalog() -> dict:
    data = dict(_catalog().catalog())
    data["query_schema"] = query_schema()
    data.setdefault("limits", {"explicit_ids_max": 10000, "target_limit_max": 100000, "page_size_max": 100})
    return data


def _operation(raw: Any) -> tuple[str, int]:
    if not isinstance(raw, Mapping) or set(raw) - {"key", "version"}:
        raise _error("operation_invalid", "请选择有效的批量操作。")
    key, version = raw.get("key"), raw.get("version", 1)
    if not isinstance(key, str) or isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise _error("operation_version_unsupported", "批量操作版本不受支持。")
    return key, version


def _id(value: Any, field: str) -> int:
    if isinstance(value, bool) or not str(value or "").isdigit() or not 0 < int(value) <= 9223372036854775807:
        raise _error("parameter_invalid", "目标标识必须为有效正整数。", field=field)
    return int(value)


def _source(raw: Any) -> dict:
    if not isinstance(raw, Mapping):
        raise _error("query_invalid", "请选择账号范围。")
    source = dict(raw)
    kind = source.get("kind")
    if kind == "query":
        if set(source) - {"kind", "query"}:
            raise _error("field_not_supported", "查询来源包含不支持的字段。")
        source["query"] = normalize_query(source.get("query"))
    elif kind == "ids":
        if set(source) - {"kind", "entity", "ids"} or source.get("entity", "account") != "account":
            raise _error("query_invalid", "显式账号来源无效。")
        ids = source.get("ids")
        if not isinstance(ids, list) or not ids or len(ids) > 10000:
            raise _error("query_invalid", "请选择 1 至 10,000 个账号。")
        source["ids"] = list(dict.fromkeys(_id(value, "ids") for value in ids))
    elif kind == "batch_targets":
        if set(source) - {"kind", "batch_id", "selection", "view", "round_id"}:
            raise _error("field_not_supported", "原批账号来源包含不支持的字段。")
        source["batch_id"] = _id(source.get("batch_id"), "batch_id")
        view = source.get("view", "current")
        if view not in {"current", "round"}:
            raise _error("parameter_invalid", "原批来源视图无效。")
        if view == "round":
            source["round_id"] = _id(source.get("round_id"), "round_id")
        elif source.get("round_id") is not None:
            raise _error("parameter_invalid", "当前结果视图不能指定执行轮次。")
        selection = source.get("selection") or {"kind": "all"}
        _validate_result_selection(selection, allow_all=True)
        source["selection"] = selection
    else:
        raise _error("query_invalid", "账号范围来源不受支持。")
    return source


def _validate_result_selection(selection, *, allow_all=False):
    if not isinstance(selection, Mapping):
        raise _error("parameter_invalid", "重跑范围必须为对象。")
    kind = selection.get("kind")
    if kind == "targets":
        if set(selection) - {"kind", "target_ids"}:
            raise _error("field_not_supported", "目标选择包含不支持的字段。")
        ids = selection.get("target_ids")
        if not isinstance(ids, list) or not ids or len(ids) > 10000:
            raise _error("parameter_invalid", "请选择 1 至 10,000 个固定目标。")
        for value in ids:
            _id(value, "target_ids")
    elif kind == "result_filter":
        if set(selection) - {"kind", "states", "reason_codes", "result_filters"}:
            raise _error("field_not_supported", "结果选择包含不支持的字段。")
        allowed = {"failed", "partial_success", "attention_required", "not_executed", "cancelled"}
        states = selection.get("states")
        if not isinstance(states, list) or not states or any(not isinstance(value, str) or value not in allowed for value in states):
            raise _error("parameter_invalid", "只能按终态未成功结果生成重跑范围。")
        reasons = selection.get("reason_codes")
        if reasons is not None and (not isinstance(reasons, list) or len(reasons) > 100
                                   or any(not isinstance(value, str) or len(value) > 200 for value in reasons)):
            raise _error("parameter_invalid", "错误分类必须为原因码数组。")
        result_filters = selection.get("result_filters")
        if result_filters is not None:
            if not isinstance(result_filters, Mapping) or any(not isinstance(k, str) or not isinstance(v, (str, bool, int)) for k, v in result_filters.items()):
                raise _error("parameter_invalid", "功能结果筛选值必须为文本、整数或布尔值。")
        # 受理前复用仓储的字段白名单和长度限制，不生成必定准备失败的轮次。
        from core.storage.operations.bulk_selections import result_predicate
        result_predicate(selection)
    elif kind != "all" or not allow_all or set(selection) != {"kind"}:
        raise _error("parameter_invalid", "不支持的结果范围。")


def create_selection(payload: dict, request_key: str) -> dict:
    _store().init()
    key, version = _operation(payload.get("operation"))
    parameters = _catalog().normalize_parameters(key, payload.get("parameters") or {})
    source = _source(payload.get("source"))
    expected = payload.get("expected_config_revision")
    previous = _store().find_selection_request(request_key)
    if previous:
        previous_source = (previous.get("query_spec") or {}).get("source", {})
        if (previous["action_key"] != key or previous["action_version"] != version
                or previous["parameters"] != parameters or previous_source != source
                or (expected is not None and str(expected) != str(previous["config_revision"]))):
            raise _error("idempotency_conflict", "该幂等键已经用于不同的账号范围或参数。", 409)
        return dict(previous, reused=True)
    settings = _catalog().capture_settings(key, parameters)
    if expected is not None and str(expected) != str(settings["config_revision"]):
        raise _error("config_revision_changed", "执行设置已变化，请重新查看设置。", 409,
                     config_revision=settings["config_revision"], effective_settings=settings.get("effective_settings", {}))
    result = _store().create_selection(request_key=request_key, source=source,
        operation_key=key, operation_version=version, parameters=settings["parameters"],
        config_revision=settings["config_revision"], config_snapshot=settings["config_snapshot"],
        query_spec=source.get("query") or {})
    wake()
    return result


def create_batch(payload: dict, request_key: str) -> dict:
    key, _version = _operation(payload.get("operation"))
    parameters = _catalog().normalize_parameters(key, payload.get("parameters") or {})
    revision = payload.get("selection_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise _error("parameter_invalid", "请提供有效的名单修订。", field="selection_revision")
    execution = payload.get("execution") or {}
    if not isinstance(execution, Mapping) or set(execution) - {"max_concurrency", "start_paused"}:
        raise _error("parameter_invalid", "批次执行设置无效。")
    start_paused = execution.get("start_paused", False)
    if not isinstance(start_paused, bool):
        raise _error("parameter_invalid", "创建后暂停必须为布尔值。", field="execution.start_paused")
    maximum = execution.get("max_concurrency", 1)
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 128:
        raise _error("parameter_invalid", "本批并发上限必须为 1 至 128 的整数。")
    name = payload.get("name") or ""
    if not isinstance(name, str) or len(name.strip()) > 120:
        raise _error("parameter_invalid", "批次名称不能超过 120 字符。", field="name")
    # 仓储先核验原请求身份；已受理重发不得因当前配置变化破坏幂等回执。
    result = _store().create_batch(request_key=request_key,
        selection_id=_id(payload.get("selection_id"), "selection_id"),
        selection_revision=revision, operation_key=key,
        parameters=parameters, config_revision=str(payload.get("expected_config_revision") or ""),
        name=name.strip() or f"{_catalog().OPERATIONS[key]}批量任务", max_concurrency=maximum,
        start_paused=start_paused)
    wake()
    return result


def create_round(batch_id: int, payload: dict, request_key: str) -> dict:
    source = payload.get("source") or {"view": "current"}
    if not isinstance(source, Mapping) or set(source) - {"view", "round_id", "observed_summary_revision", "observed_target_count"} or source.get("view", "current") not in {"current", "round"}:
        raise _error("parameter_invalid", "重跑来源视图无效。")
    if source.get("view") == "round":
        _id(source.get("round_id"), "round_id")
    elif source.get("round_id") is not None:
        raise _error("parameter_invalid", "当前结果视图不能指定执行轮次。")
    if payload.get("retry_mode", "automatic") != "automatic":
        raise _error("parameter_invalid", "当前重跑方式仅支持 automatic。")
    selection = payload.get("selection") or {"kind": "result_filter", "states": ["failed"]}
    _validate_result_selection(selection)
    result = _store().create_round(batch_id, request_key=request_key, source=dict(source),
        selection=dict(selection), observed_summary_revision=source.get("observed_summary_revision"))
    wake()
    return result


def request_control(batch_id: int, payload: dict, request_key: str) -> dict:
    action = payload.get("action")
    if action not in {"cancel_not_started", "request_stop", "pause", "resume"}:
        raise _error("parameter_invalid", "不支持的批次控制动作。")
    scope = payload.get("scope") or {"kind": "batch"}
    if not isinstance(scope, Mapping) or set(scope) - {"kind", "round_id"} or scope.get("kind") not in {"batch", "round"}:
        raise _error("parameter_invalid", "控制范围无效。")
    round_id = _id(scope.get("round_id"), "round_id") if scope["kind"] == "round" else None
    if action in {"pause", "resume"} and scope["kind"] != "batch":
        raise _error("parameter_invalid", "暂停和继续仅支持整个批次。")
    if scope["kind"] == "batch" and scope.get("round_id") is not None:
        raise _error("parameter_invalid", "整批控制不能同时指定执行轮次。")
    revision = payload.get("expected_control_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise _error("parameter_invalid", "请提供有效的控制修订。")
    result = _store().request_control(batch_id, request_key=request_key, action=action,
        expected_control_revision=revision, round_id=round_id)
    wake()
    return result


def retry_managed_task(task_id: int, *, request_key: str | None = None) -> dict | None:
    """旧任务中心的人工重跑统一生成单目标新轮；非管理任务返回 None。"""
    from core.storage.operations import store
    from psycopg.rows import dict_row
    with store._connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT t.batch_id,t.data,r.data AS run_data FROM {store._table('operation_tasks')} t "
                    f"LEFT JOIN {store._table('operation_runs')} r ON r.id=t.last_run_id WHERE t.id=%s", (int(task_id),))
        task = cur.fetchone()
        if not task:
            return None
        target_round_id = (task.get("run_data") or {}).get("bulk_target_round_id") or (task.get("data") or {}).get("bulk_target_round_id")
        if not target_round_id:
            return None
        cur.execute(f"SELECT batch_id,canonical_target_id FROM {store._table('operation_batch_target_rounds')} WHERE id=%s", (int(target_round_id),))
        target = cur.fetchone()
        if not target:
            raise _error("managed_target_missing", "批量任务归属缺失，已保留原任务，请检查数据。", 409)
    result = create_round(int(target["batch_id"]), {"source": {"view": "current"},
        "selection": {"kind": "targets", "target_ids": [str(target["canonical_target_id"])]}},
        request_key or f"manual-task-retry:{uuid.uuid4().hex}")
    return {"ok": True, "accepted": True, "batch_id": str(target["batch_id"]),
            "round_id": str(result["id"]), "round_no": result["round_no"], "state": result["state"]}


def wake():
    _WAKE.set()


def run_once(kind: str) -> int:
    """单轮有界协调，测试/恢复均可调用，不发出任何领域网络请求。"""
    store = _store()
    work = 0
    if kind == "selection":
        from core.bulk_operations.execution import repair_pending_handoffs
        work += repair_pending_handoffs(limit=50)
        for item in store.claim_work("selection", _OWNER, limit=1):
            try:
                saved = item.get("query_spec") or {}
                spec = saved.get("query", saved) if "source" in saved else saved
                where, params = compile_query(spec) if spec else ("TRUE", [])
                from core.bulk_operations import adapters
                settings = item.get("config_snapshot") or {}
                def preflight(targets, conn):
                    return adapters.preflight_many(targets, operation_key=item["action_key"], settings=settings, conn=conn)
                store.freeze_selection(item["id"], where_sql=where, params=params,
                                       owner_id=item.get("owner_id"), fence=item.get("fence"), preflight=preflight)
            except AccountQueryError:
                store.fail_selection(item["id"], error_code="query_invalid", owner_id=item.get("owner_id"), fence=item.get("fence"))
                raise
            except store.BulkError as exc:
                if exc.code not in {"lease_lost", "bulk_store_unavailable"} and (exc.status < 500 or exc.code in {"invalid_preflight_receipts", "adapter_contract_violation"}):
                    store.fail_selection(item["id"], error_code=exc.code, owner_id=item.get("owner_id"), fence=item.get("fence"))
                raise
            work += 1
        for item in store.claim_work("round", _OWNER, limit=1):
            try:
                store.freeze_round(item["id"], owner_id=item.get("owner_id"), fence=item.get("fence"))
            except store.BulkError as exc:
                if exc.code not in {"lease_lost", "bulk_store_unavailable"} and (exc.status < 500 or exc.code in {"invalid_preflight_receipts", "adapter_contract_violation"}):
                    store.fail_round(item["id"], error_code=exc.code, owner_id=item.get("owner_id"), fence=item.get("fence"))
                raise
            work += 1
        for item in store.claim_work("control", _OWNER, limit=1):
            store.settle_control(item["id"], owner_id=item.get("owner_id"), fence=item.get("fence"))
            work += 1
        global _LAST_MAINTENANCE
        if time.monotonic() - _LAST_MAINTENANCE > 30:
            store.expire_selections(limit=100)
            _LAST_MAINTENANCE = time.monotonic()
    elif kind == "expand":
        from core.bulk_operations.adapters import submit_chunk
        for batch in store.list_active_batches(limit=20):
            result = store.process_batch(batch.get("batch_id", batch.get("id")), submit_chunk, limit=100)
            work += sum(int(result.get(key, 0)) for key in ("submitted", "not_executed", "materialized"))
    elif kind == "project":
        work = store.project_pending(limit=200)
    else:
        raise ValueError("不支持的协调任务类型")
    return work


def _loop(kind: str):
    while not _STOP.is_set():
        started = time.monotonic()
        try:
            count = run_once(kind)
            with _LOCK:
                _STATUS[kind] = {"last_success_at": time.time(), "last_cycle_seconds": time.monotonic() - started,
                                 "last_work_count": count, "error_code": None}
        except Exception as exc:
            logger.exception("批量协调暂不可用，已受理请求保留：worker=%s code=bulk_%s_cycle_failed", kind, kind)
            with _LOCK:
                _STATUS[kind] = {"last_error_at": time.time(), "error_code": f"bulk_{kind}_cycle_failed",
                                 "exception_type": type(exc).__name__}
            count = 0
        if not count:
            _WAKE.wait(1.0)
            _WAKE.clear()


def start_workers() -> bool:
    with _LOCK:
        _store().init()
        _STOP.clear()
        started = False
        for kind in ("selection", "expand", "project"):
            if kind in _THREADS and _THREADS[kind].is_alive():
                continue
            thread = threading.Thread(target=_loop, args=(kind,), name=f"bulk-{kind}", daemon=True)
            _THREADS[kind] = thread
            thread.start()
            started = True
    return started


def stop_workers(timeout: float = 3.0):
    _STOP.set()
    _WAKE.set()
    deadline = time.monotonic() + timeout
    for thread in tuple(_THREADS.values()):
        thread.join(max(0, deadline - time.monotonic()))


def worker_status() -> dict:
    with _LOCK:
        alive = set(_THREADS) == {"selection", "expand", "project"} and all(t.is_alive() for t in _THREADS.values())
        return {"started": bool(_THREADS), "running": alive, "alive": alive,
                "workers": {kind: {"alive": thread.is_alive(), **_STATUS.get(kind, {})} for kind, thread in _THREADS.items()}}
