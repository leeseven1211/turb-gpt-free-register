# -*- coding: utf-8 -*-
"""统一任务查询与历史兼容出口。写入、恢复、统计投影分别由对应仓储模块拥有。"""
from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, Iterable
from core.operations import run_log as task_run_log
from core.bulk_operations import execution as bulk_execution
from core.operations.progress import build_progress_snapshot
from core.operations.presentation import public_result_status, public_result_status_sql
from core.operations.stages import flow_for, stage_label
from core.storage.operations import common as _common
from core.storage.operations import schema as _schema
from core.storage.operations import recovery as _recovery
from core.storage.operations import runtime as _runtime
from core.storage.operations import projection as _projection

_PROGRESS_SNAPSHOT_CACHE: dict[int, tuple[float, tuple, dict]] = {}


_PROGRESS_SNAPSHOT_CACHE_LOCK = threading.RLock()


_PROGRESS_SNAPSHOT_CACHE_MAX = 2048


_PROGRESS_SNAPSHOT_CACHE_TTL = 300.0


def list_batches(*, limit: int = 50) -> list[dict]:
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT b.*, q.status AS projection_queue_status,
                   q.attempts AS projection_queue_attempts,
                   CASE WHEN q.status='failed' THEN q.available_at ELSE NULL END AS projection_queue_next_retry_at,
                   q.last_error AS projection_queue_error,
                   CASE WHEN q.requested_at IS NULL THEN NULL
                        ELSE GREATEST(0, EXTRACT(EPOCH FROM (COALESCE(q.completed_at, now()) - q.requested_at)) * 1000)::BIGINT
                   END AS projection_lag_ms
            FROM {_common._table('operation_batches')} b
            LEFT JOIN {_common._table('operation_projection_queue')} q ON q.batch_id=b.id
            ORDER BY b.created_at DESC, b.id DESC LIMIT %s
            """,
            (max(1, min(200, int(limit or 50))),),
        )
        batches = []
        for raw in cur.fetchall():
            batch = _common._row(dict(raw)) or {}
            projection_status = str(batch.get("projection_status") or "synced")
            batch["projection_delayed"] = projection_status not in {"synced", "succeeded"}
            batches.append(batch)
        return batches


def _operation_task_where(
    *, task_type: str = "", status: str = "", source: str = "", q: str = "",
    batch_id: int | None = None, task_id: str = "", target: str = "",
    target_status: str = "", batch: str = "", run_count: str = "",
    stage: str = "", created_from: str = "", created_to: str = "", result: str = "",
    exclude: str = "", run_count_expression: str | None = None, public_status: bool = False,
) -> tuple[list[str], list[Any]]:
    """Build the shared task-list predicate, optionally leaving one facet unfiltered."""
    where: list[str] = ["COALESCE(t.data->>'deleted_by_user','false') <> 'true'"]
    params: list[Any] = []

    def add(name: str, expression: str, *values: Any) -> None:
        if exclude != name:
            where.append(expression)
            params.extend(values)

    if task_type:
        # 并发分类可涵盖多个真实任务类型，保持单值兼容且始终参数化查询。
        selected_types = list(dict.fromkeys(part.strip() for part in str(task_type).split(",") if part.strip()))[:20]
        if selected_types:
            add("task_type", "t.task_type = ANY(%s)", selected_types)
    # ``r`` is the current run selected by the list query below.  Filtering on
    # it keeps a logical task out of terminal facets while a retry is active.
    status_expression = "COALESCE(r.effective_status, t.status)"
    target_expression = "t.target_status"
    if public_status:
        status_expression = public_result_status_sql(status_expression, "r.result_summary")
        target_expression = public_result_status_sql(target_expression, "r.result_summary")
    add("status", f"({status_expression})=%s", public_result_status(status) if public_status else str(status)) if status else None
    add("source", "t.source_system=%s", str(source)) if source else None
    add("batch_id", "t.batch_id=%s", int(batch_id)) if batch_id else None

    if q:
        needle = f"%{str(q).strip()}%"
        add(
            "q",
            "("
            "t.email_snapshot ILIKE %s OR CAST(t.account_id AS TEXT) ILIKE %s "
            "OR CAST(t.attempt_id AS TEXT) ILIKE %s OR CAST(t.target_id AS TEXT) ILIKE %s "
            "OR CAST(t.id AS TEXT) ILIKE %s OR COALESCE(t.error_message, '') ILIKE %s "
            "OR COALESCE(b.title, '') ILIKE %s OR COALESCE(t.trigger, '') ILIKE %s "
            "OR COALESCE(r.effective_error_message, '') ILIKE %s "
            "OR COALESCE(r.result_summary::text, '') ILIKE %s"
            ")",
            needle, needle, needle, needle, needle, needle, needle, needle, needle, needle,
        )
    if task_id:
        value = str(task_id).strip().lstrip("#")
        add("task_id", "CAST(t.id AS TEXT) ILIKE %s", f"%{value}%") if value else None
    if target:
        needle = f"%{str(target).strip()}%"
        add(
            "target",
            "("
            "COALESCE(t.email_snapshot, '') ILIKE %s OR CAST(t.account_id AS TEXT) ILIKE %s "
            "OR CAST(t.attempt_id AS TEXT) ILIKE %s OR CAST(t.target_id AS TEXT) ILIKE %s"
            ")",
            needle, needle, needle, needle,
        )
    if target_status:
        add("target_status", f"({target_expression})=%s", public_result_status(target_status) if public_status else str(target_status))
    if batch:
        needle = f"%{str(batch).strip()}%"
        add(
            "batch",
            "(COALESCE(b.title, '') ILIKE %s OR COALESCE(b.batch_uuid, '') ILIKE %s OR COALESCE(t.trigger, '') ILIKE %s)",
            needle, needle, needle,
        )
    if run_count:
        value = str(run_count).strip().lower()
        run_count_expr = run_count_expression or (
            f"(SELECT COUNT(*) FROM {_common._table('operation_runs')} rr WHERE rr.task_id=t.id)"
        )
        if value in {"4+", "4plus", "4_plus"}:
            add("run_count", f"{run_count_expr} >= %s", 4)
        elif value.isdigit():
            add("run_count", f"{run_count_expr} = %s", int(value))
    if stage:
        add(
            "stage",
            "LOWER(COALESCE(r.effective_progress_stage, CASE WHEN r.effective_status='queued' THEN 'queued' ELSE t.current_stage END, ''))=%s",
            str(stage).lower(),
        )
    if created_from:
        add("created_from", "t.created_at::date >= %s", str(created_from)[:10])
    if created_to:
        add("created_to", "t.created_at::date <= %s", str(created_to)[:10])
    if result:
        needle = f"%{str(result).strip()}%"
        add(
            "result",
            "(COALESCE(t.error_message, '') ILIKE %s OR COALESCE(r.effective_error_message, '') ILIKE %s "
            "OR COALESCE(r.result_summary::text, '') ILIKE %s)",
            needle, needle, needle,
        )
    return where, params


_TASK_LIST_RUN_FIELDS = (
    "id", "task_id", "run_no", "source_system", "source_id", "result_summary",
    "duration_ms", "error_category", "error_code", "effective_status",
    "effective_progress_stage", "effective_created_at", "effective_completed_at",
    "effective_created_at_sort", "effective_error_message", "effective_debug_pause",
)


def _operation_task_run_columns_sql(fields: tuple[str, ...] | None = None) -> str:
    """Only internal callers supply field names; source expressions stay shared."""
    if fields is None:
        return f"rr.*, {_common._compatibility_run_projection_sql()}"
    raw_fields = [f"rr.{field}" for field in fields if not field.startswith("effective_")]
    projected_fields = tuple(field for field in fields if field.startswith("effective_"))
    if projected_fields:
        raw_fields.append(_common._compatibility_run_projection_sql(fields=projected_fields))
    return ", ".join(raw_fields)


def _operation_task_indexed_run_join_sql(*, sort_only: bool = False) -> str:
    """仅在候选任务/当前页内按索引取Run，排序口径与历史查询相同。"""
    status_sql = _common._compatibility_run_status_sql()
    # 原生任务的有效排序时间恒为task.created_at；兼容任务才读取来源时间。
    predicate = " AND t.source_system IN ('registration_jobs','registration_chains','account_action_tasks')" if sort_only else ""
    fields = ("effective_created_at_sort",) if sort_only else _TASK_LIST_RUN_FIELDS
    return (
        f"LEFT JOIN LATERAL ("
        f"SELECT {_operation_task_run_columns_sql(fields)} "
        f"FROM {_common._table('operation_runs')} rr {_common._compatibility_run_joins_sql()} "
        f"WHERE rr.task_id=t.id{predicate} "
        f"ORDER BY CASE WHEN ({status_sql}) IN ({_common._ACTIVE_RUN_STATUS_SQL}) THEN 0 ELSE 1 END, "
        f"rr.run_no DESC, rr.id DESC LIMIT 1"
        f") {'sort_run' if sort_only else 'r'} ON TRUE "
    )


def _operation_task_running_candidates_cte_sql() -> str:
    """保守收集可能公开显示running的任务，再按原规则选其全部Run。"""
    return (
        "running_task_candidates AS MATERIALIZED ("
        f"SELECT rr.task_id AS id FROM {_common._table('operation_runs')} rr "
        f"WHERE rr.status IN ({_common._ACTIVE_RUN_STATUS_SQL}) OR "
        "LOWER(BTRIM(COALESCE(rr.status::text,'')))='running' OR "
        "rr.source_system IN ('registration_jobs','account_action_tasks') "
        f"UNION SELECT t.id FROM {_common._table('operation_tasks')} t WHERE "
        "LOWER(BTRIM(COALESCE(t.status::text,'')))='running')"
    )


def _operation_task_current_run_relation_sql(
    *, fields: tuple[str, ...] | None = None, running_candidates: bool = False,
) -> str:
    """Run相关筛选保留有效活跃优先的集合投影。"""
    candidate_join = (
        "JOIN running_task_candidates running_runs ON running_runs.id=rr.task_id "
        if running_candidates else ""
    )
    return (
        f"SELECT DISTINCT ON (rr.task_id) {_operation_task_run_columns_sql(fields)} "
        f"FROM {_common._table('operation_runs')} rr {candidate_join}{_common._compatibility_run_joins_sql()} "
        f"ORDER BY rr.task_id, "
        f"CASE WHEN ({_common._compatibility_run_status_sql()}) IN ({_common._ACTIVE_RUN_STATUS_SQL}) THEN 0 ELSE 1 END, "
        f"rr.run_no DESC, rr.id DESC"
    )


def _operation_task_current_run_join_sql(
    *, fields: tuple[str, ...] | None = None, running_candidates: bool = False,
) -> str:
    relation = _operation_task_current_run_relation_sql(
        fields=fields, running_candidates=running_candidates,
    )
    return f"LEFT JOIN ({relation}) r ON r.task_id=t.id"


def _operation_task_query_base(
    *, include_current_run: bool, include_run_count: bool, facet_cte: bool = False,
    current_run_fields: tuple[str, ...] | None = None, running_candidates: bool = False,
) -> str:
    """Build the read-only task-list relation with only needed derived joins."""
    candidate_join = (
        "JOIN running_task_candidates running_tasks ON running_tasks.id=t.id "
        if running_candidates else ""
    )
    query = (
        f"FROM {_common._table('operation_tasks')} t "
        f"{candidate_join}"
        f"LEFT JOIN {_common._table('operation_batches')} b ON b.id=t.batch_id "
    )
    if include_run_count:
        if facet_cte:
            query += "LEFT JOIN facet_run_counts run_counts ON run_counts.task_id=t.id "
        else:
            query += (
                f"LEFT JOIN (SELECT rr.task_id, COUNT(*) AS run_count "
                f"FROM {_common._table('operation_runs')} rr GROUP BY rr.task_id"
                f") run_counts ON run_counts.task_id=t.id "
            )
    if include_current_run:
        query += (
            "LEFT JOIN facet_current_runs r ON r.task_id=t.id "
            if facet_cte else _operation_task_current_run_join_sql(
                fields=current_run_fields, running_candidates=running_candidates,
            )
        )
    return query


def _attach_plan_failure_summaries(items: list[dict], *, conn, run_rows: bool = False) -> None:
    """一次批量恢复旧套餐 Run 的逐国错误，仅补读模型而不回写历史事实。"""
    from core.accounts.plans.errors import country_failures_from_events

    by_run: dict[int, list[dict]] = {}
    for item in items:
        if item.get("task_type") != "plan_check" or item.get("status") not in {"failed", "partial_success"}:
            continue
        summary = item.get("result_summary") if isinstance(item.get("result_summary"), dict) else {}
        if isinstance(summary.get("country_failures"), list):
            continue
        run_id = item.get("id" if run_rows else "last_run_id")
        if run_id:
            by_run.setdefault(int(run_id), []).append(item)
    if not by_run:
        return
    with conn.cursor() as cur:
        # 正式回执和旧 warning 分别取最后一条，成功回执也必须读取，避免复现已恢复的旧错误。
        cur.execute(
            f"""
            SELECT DISTINCT ON (run_id, detail->>'country', event_type)
                   id, run_id, stage, event_type, detail, created_at
            FROM {_common._table('operation_events')}
            WHERE run_id=ANY(%s) AND stage IN ('plan_check', 'plan_check_result')
              AND event_type IN ('promotion.query.recorded', 'note.warning')
              AND detail->'ok' IN ('true'::jsonb, 'false'::jsonb)
              AND detail->>'country' IS NOT NULL
            ORDER BY run_id, detail->>'country', event_type, created_at DESC, id DESC
            """,
            (list(by_run),),
        )
        events_by_run: dict[int, list[dict]] = {}
        for row in cur.fetchall():
            event = _common._row(dict(row)) or {}
            events_by_run.setdefault(int(event["run_id"]), []).append(event)
    for run_id, events in events_by_run.items():
        events.sort(key=_common._event_time_sort_key)
        failures = country_failures_from_events(events)
        for item in by_run[run_id]:
            summary = item.get("result_summary") if isinstance(item.get("result_summary"), dict) else {}
            item["result_summary"] = {**summary, "country_failures": failures}


def list_tasks(
    *, page: int = 1, page_size: int = 50, task_type: str = "", status: str = "",
    source: str = "", q: str = "", batch_id: int | None = None, task_id: str = "",
    target: str = "", target_status: str = "", batch: str = "", run_count: str = "",
    stage: str = "", created_from: str = "", created_to: str = "", result: str = "",
    include_facets: bool = True, public_status: bool = False,
) -> dict:
    _schema.init_operation_schema()
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 50)))
    running_candidates = (
        public_status
        and status == "running"
        and not include_facets
        and batch_id is None
        and not any((
            task_type, source, q, task_id, target, target_status, batch,
            run_count, stage, created_from, created_to, result,
        ))
    )
    running_candidates_cte = (
        _operation_task_running_candidates_cte_sql() if running_candidates else ""
    )
    count_cte = f"WITH {running_candidates_cte} " if running_candidates else ""
    where, params = _operation_task_where(
        task_type=task_type, status=status, source=source, q=q, batch_id=batch_id,
        task_id=task_id, target=target, target_status=target_status, batch=batch,
        run_count=run_count, stage=stage, created_from=created_from,
        created_to=created_to, result=result,
        run_count_expression="COALESCE(run_counts.run_count, 0)",
        public_status=public_status,
    )
    clause = f" WHERE {' AND '.join(where)}" if where else ""

    def uses_current_run(*, exclude: str = "", facet_name: str = "") -> bool:
        return bool(
            q
            or result
            or (status and exclude != "status")
            or (stage and exclude != "stage")
            or (public_status and target_status and exclude != "target_status")
            or (public_status and facet_name == "target_status")
            or facet_name in {"status", "stage"}
        )

    run_count_expression = "COALESCE(run_counts.run_count, 0)"
    filter_run_fields = ("task_id", "effective_status", "effective_progress_stage", "result_summary")
    if q or result:
        filter_run_fields += ("effective_error_message",)
    count_from_sql = _operation_task_query_base(
        include_current_run=uses_current_run(),
        include_run_count=bool(run_count),
        current_run_fields=filter_run_fields,
        running_candidates=running_candidates,
    )
    page_from_sql = _operation_task_query_base(
        include_current_run=True, include_run_count=bool(run_count),
        current_run_fields=_TASK_LIST_RUN_FIELDS,
    )
    page_run_count_expression = run_count_expression
    page_cte = ""
    page_clause = clause
    page_params = (*params, page_size, (page - 1) * page_size)
    page_order = "COALESCE(r.effective_created_at_sort, t.created_at) DESC, t.id DESC LIMIT %s OFFSET %s"
    if not uses_current_run() and not run_count:
        # 先确定50个任务ID，再加载这些任务的Run/次数/结果。原生任务按任务创建时间，
        # 兼容任务仍按其有效Run来源时间排序，不以last_run_id替代活跃优先选择。
        candidate_from = (f"FROM {_common._table('operation_tasks')} t "
                          f"LEFT JOIN {_common._table('operation_batches')} b ON b.id=t.batch_id ")
        ordinary_clause = (clause + " AND " if clause else " WHERE ") + "t.source_system NOT IN ('registration_jobs','registration_chains','account_action_tasks')"
        legacy_clause = (clause + " AND " if clause else " WHERE ") + "t.source_system IN ('registration_jobs','registration_chains','account_action_tasks')"
        page_cte = (f"WITH page_ids AS MATERIALIZED (SELECT * FROM ("
                    f"SELECT t.id,t.created_at AS sort_at {candidate_from}{ordinary_clause} "
                    f"UNION ALL SELECT t.id,COALESCE(sort_run.effective_created_at_sort,t.created_at) AS sort_at "
                    f"{candidate_from}{_operation_task_indexed_run_join_sql(sort_only=True)}{legacy_clause}"
                    f") candidates ORDER BY sort_at DESC,id DESC LIMIT %s OFFSET %s) ")
        page_params = (*params, *params, page_size, (page - 1) * page_size)
        page_from_sql = (f"FROM page_ids selected JOIN {_common._table('operation_tasks')} t ON t.id=selected.id "
                         f"LEFT JOIN {_common._table('operation_batches')} b ON b.id=t.batch_id "
                         + _operation_task_indexed_run_join_sql())
        page_clause = ""
        page_order = "selected.sort_at DESC,t.id DESC"
    else:
        # The same statement chooses/filter/sorts the winning Run once. Load
        # display fields only for selected page IDs, never last_run_id or a
        # second active-priority lookup that could select a different Run.
        candidate_fields = (*filter_run_fields, "id", "effective_created_at_sort")
        candidate_from = _operation_task_query_base(
            include_current_run=True, include_run_count=bool(run_count),
            current_run_fields=candidate_fields,
            running_candidates=running_candidates,
        )
        page_cte_prefix = f"{running_candidates_cte}, " if running_candidates else ""
        page_cte = (
            f"WITH {page_cte_prefix}page_ids AS MATERIALIZED ("
            f"SELECT t.id,r.id AS current_run_id,"
            f"COALESCE(r.effective_created_at_sort,t.created_at) AS sort_at,"
            f"{run_count_expression if run_count else 'NULL::bigint'} AS run_count "
            f"{candidate_from}{clause} ORDER BY sort_at DESC,t.id DESC LIMIT %s OFFSET %s) "
        )
        page_from_sql = (
            f"FROM page_ids selected JOIN {_common._table('operation_tasks')} t ON t.id=selected.id "
            f"LEFT JOIN {_common._table('operation_batches')} b ON b.id=t.batch_id "
            f"LEFT JOIN LATERAL (SELECT {_operation_task_run_columns_sql(_TASK_LIST_RUN_FIELDS)} "
            f"FROM {_common._table('operation_runs')} rr {_common._compatibility_run_joins_sql()} "
            f"WHERE rr.id=selected.current_run_id LIMIT 1) r ON TRUE "
        )
        page_clause = ""
        page_order = "selected.sort_at DESC,t.id DESC"
        page_run_count_expression = "selected.run_count"
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"{count_cte}SELECT COUNT(*) AS n {count_from_sql}{clause}", params)
        total = int(cur.fetchone()["n"])
        cur.execute(
            f"""
            {page_cte}
            SELECT t.*, b.batch_uuid, b.title AS batch_title, b.batch_type,
                   r.id AS __current_run_id, r.effective_status AS __current_run_status,
                   r.effective_progress_stage AS __current_run_stage,
                   r.effective_created_at AS __current_run_created_at,
                   r.effective_completed_at AS __current_run_completed_at,
                   r.effective_debug_pause AS __current_run_debug_pause,
                   r.error_category AS __current_run_error_category,
                   r.error_code AS __current_run_error_code,
                   r.effective_error_message AS __current_run_error_message,
                   r.run_no AS last_run_no, r.duration_ms, r.result_summary,
                   r.source_system AS run_source_system, r.source_id AS run_source_id,
                   {page_run_count_expression if run_count else 'NULL::bigint'} AS run_count
            {page_from_sql}
            {page_clause}
            ORDER BY {page_order}
            """,
            page_params,
        )
        items = []
        for raw_row in cur.fetchall():
            item = _common._row(dict(raw_row)) or {}
            current_run = {
                "id": item.pop("__current_run_id", None),
                "source_system": item.pop("run_source_system", None),
                "source_id": item.pop("run_source_id", None),
                "status": item.pop("__current_run_status", None),
                "progress_stage": item.pop("__current_run_stage", None),
                "effective_created_at": item.pop("__current_run_created_at", None),
                "effective_completed_at": item.pop("__current_run_completed_at", None),
                "effective_debug_pause": item.pop("__current_run_debug_pause", None),
                "error_category": item.pop("__current_run_error_category", None),
                "error_code": item.pop("__current_run_error_code", None),
                "error_message": item.pop("__current_run_error_message", None),
                "result_summary": item.get("result_summary"),
            }
            if current_run["id"] is not None:
                current_run = _common._normalize_compatibility_run(current_run)
                _common._apply_current_run_projection(item, current_run)
            if public_status:
                for key in ("status", "target_status"):
                    original = item.get(key)
                    projected = public_result_status(original, item.get("result_summary"))
                    if original is not None and projected != original:
                        item[f"internal_{key}"] = original
                        item[key] = projected
            items.append(item)
        if items and not run_count:
            # 显示次数只需当前页；不为50条响应聚合所有历史Run。
            cur.execute(f"SELECT task_id,COUNT(*) AS n FROM {_common._table('operation_runs')} "
                        "WHERE task_id=ANY(%s) GROUP BY task_id", ([int(item["id"]) for item in items],))
            page_run_counts = {int(row["task_id"]): int(row["n"]) for row in cur.fetchall()}
            for item in items:
                item["run_count"] = page_run_counts.get(int(item["id"]), 0)
        public_status_expression = public_result_status_sql("COALESCE(r.effective_status, t.status)", "r.result_summary")
        public_target_expression = public_result_status_sql("t.target_status", "r.result_summary")
        facet_specs = (
            ("task_type", "t.task_type", "task_type"),
            ("status", public_status_expression if public_status else "COALESCE(r.effective_status, t.status)", "status"),
            ("target_status", public_target_expression if public_status else "t.target_status", "target_status"),
            (
                "stage",
                "LOWER(COALESCE(r.effective_progress_stage, CASE WHEN r.effective_status='queued' THEN 'queued' ELSE t.current_stage END, ''))",
                "stage",
            ),
            (
                "run_count",
                f"CASE WHEN {run_count_expression} >= 4 "
                f"THEN '4+' ELSE CAST({run_count_expression} AS TEXT) END",
                "run_count",
            ),
        )
        facets: dict[str, list[dict[str, Any]]] = {}
        facet_columns = []
        facet_rows = []
        facet_query_params = []
        for facet_name, expression, exclude in (facet_specs if include_facets else ()):
            facet_where, facet_params = _operation_task_where(
                task_type=task_type, status=status, source=source, q=q, batch_id=batch_id,
                task_id=task_id, target=target, target_status=target_status, batch=batch,
                run_count=run_count, stage=stage, created_from=created_from,
                created_to=created_to, result=result, exclude=exclude,
                run_count_expression=run_count_expression,
                public_status=public_status,
            )
            # Every facet retains its own complete self-excluded predicate.
            # SQL NULL behaves exactly as WHERE: only TRUE contributes a row.
            facet_columns.extend((f"{expression} AS value_{facet_name}",
                                  f"({' AND '.join(facet_where)}) AS matches_{facet_name}"))
            facet_rows.append(
                f"({facet_name!r},candidate.value_{facet_name},candidate.matches_{facet_name})")
            facet_query_params.extend(facet_params)
            facets[facet_name] = []
        if facet_rows:
            error_column = "effective_error_message" if q or result else "NULL::text AS effective_error_message"
            result_column = "result_summary" if q or result or public_status else "NULL::jsonb AS result_summary"
            candidate_from = _operation_task_query_base(
                include_current_run=True, include_run_count=True, facet_cte=True,
            )
            cur.execute(
                f"WITH facet_current_runs AS MATERIALIZED ("
                f"SELECT task_id,effective_status,effective_progress_stage,{error_column},{result_column} "
                f"FROM ({_operation_task_current_run_relation_sql(fields=filter_run_fields)}) projected), "
                f"facet_run_counts AS MATERIALIZED (SELECT task_id,COUNT(*) AS run_count "
                f"FROM {_common._table('operation_runs')} GROUP BY task_id), "
                f"facet_candidates AS MATERIALIZED (SELECT {','.join(facet_columns)} {candidate_from}) "
                f"SELECT expanded.facet,expanded.value,COUNT(*) AS count "
                f"FROM facet_candidates candidate CROSS JOIN LATERAL "
                f"(VALUES {','.join(facet_rows)}) expanded(facet,value,matches) "
                f"WHERE expanded.matches AND NULLIF(expanded.value,'') IS NOT NULL "
                f"GROUP BY 1,2 ORDER BY 1,2", facet_query_params)
            for row in cur.fetchall():
                name = str(row["facet"])
                facets[name].append({"value": str(row["value"] or ""), "count": int(row["count"] or 0),
                                     **({"label": stage_label(row["value"])} if name == "stage" else {})})
        _attach_plan_failure_summaries(items, conn=conn)
        _common._attach_admission_wait(items, conn=conn)
        bulk_execution.attach_context(conn, items)
    return {"ok": True, "items": items, "total": total, "page": page, "page_size": page_size,
            **({"facets": facets} if include_facets else {})}


def get_task_types(task_ids: Iterable[int]) -> dict[int, str]:
    """批量读取未隐藏任务的类型，不加载任务详情或账号信息。"""
    normalized: set[int] = set()
    for value in task_ids or ():
        try:
            task_id = int(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if task_id > 0:
            normalized.add(task_id)
    if not normalized:
        return {}

    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, task_type
            FROM {_common._table('operation_tasks')}
            WHERE id=ANY(%s)
              AND lower(COALESCE(data->>'deleted_by_user', '')) <> 'true'
            """,
            (sorted(normalized),),
        )
        return {
            int(row["id"]): str(row.get("task_type") or "")
            for row in cur.fetchall()
        }


def get_run_task_links(run_ids: Iterable[int]) -> dict[int, dict[str, Any]]:
    """批量读取可见运行的任务归属，不返回账号凭据或任务详情。"""
    normalized: set[int] = set()
    for value in run_ids or ():
        try:
            run_id = int(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if run_id > 0:
            normalized.add(run_id)
    if not normalized:
        return {}
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.id AS run_id, t.id AS task_id, t.task_type, t.account_id
            FROM {_common._table('operation_runs')} r
            JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id
            WHERE r.id=ANY(%s)
              AND lower(COALESCE(t.data->>'deleted_by_user', '')) <> 'true'
            """,
            (sorted(normalized),),
        )
        return {int(row["run_id"]): dict(row) for row in cur.fetchall()}


def get_task(task_id: int, *, include_events: bool = True) -> dict | None:
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT t.*, b.batch_uuid, b.title AS batch_title, b.batch_type
            FROM {_common._table('operation_tasks')} t
            LEFT JOIN {_common._table('operation_batches')} b ON b.id=t.batch_id
            WHERE t.id=%s
            """,
            (int(task_id),),
        )
        task = cur.fetchone()
        if not task or _common._task_is_user_deleted(dict(task)):
            return None
        cur.execute(
            f"SELECT rr.*, {_common._compatibility_run_projection_sql()} "
            f"FROM {_common._table('operation_runs')} rr {_common._compatibility_run_joins_sql()} "
            f"WHERE rr.task_id=%s ORDER BY rr.run_no, rr.id",
            (int(task_id),),
        )
        runs = [_common._normalize_compatibility_run(_common._row(dict(row)) or {}) for row in cur.fetchall()]
        events: list[dict] = []
        if include_events:
            cur.execute(
                f"""
                SELECT e.*, r.run_no
                FROM {_common._table('operation_events')} e
                LEFT JOIN {_common._table('operation_runs')} r ON r.id=e.run_id
                WHERE e.task_id=%s ORDER BY e.created_at, e.id
                """,
                (int(task_id),),
            )
            events = [_common._normalize_compatibility_event(_common._read_event(dict(row))) for row in cur.fetchall()]
            events.sort(key=_common._event_time_sort_key)
        cur.execute(
            f"""
            SELECT resource.*
            FROM {_common._table('operation_resources')} resource
            JOIN {_common._table('operation_runs')} run ON run.id=resource.run_id
            WHERE run.task_id=%s ORDER BY resource.acquired_at, resource.id
            """,
            (int(task_id),),
        )
        resources = [_common._row(dict(row)) or {} for row in cur.fetchall()]
        attempt = None
        if task.get("attempt_id"):
            cur.execute(f"SELECT * FROM {_common._table('registration_attempts')} WHERE id=%s", (int(task["attempt_id"]),))
            raw_attempt = cur.fetchone()
            attempt = _common._row(dict(raw_attempt)) if raw_attempt else None
        parent = None
        if task.get("parent_task_id"):
            cur.execute(
                f"SELECT id, task_uuid, task_type, status, target_status FROM {_common._table('operation_tasks')} WHERE id=%s",
                (int(task["parent_task_id"]),),
            )
            raw_parent = cur.fetchone()
            parent = _common._row(dict(raw_parent)) if raw_parent else None
        if task.get("task_type") == "plan_check":
            for run in runs:
                run["task_type"] = "plan_check"
            _attach_plan_failure_summaries(runs, conn=conn, run_rows=True)
    result = _common._row(dict(task)) or {}
    _common._apply_current_run_projection(result, _common._select_current_run(runs))
    result.update({
        "runs": runs,
        "events": events,
        "resources": resources,
        "attempt": attempt,
        "parent": parent,
        "flow": flow_for(result.get("task_type"), _common._select_current_run(runs)),
    })
    with _common._connect() as conn:
        _common._attach_admission_wait(runs, conn=conn, run_rows=True)
        _common._attach_admission_wait([result], conn=conn)
        bulk_execution.attach_context(conn, runs, run_rows=True)
        bulk_execution.attach_context(conn, [result])
    return result


def delete_tasks(task_ids: Iterable[int]) -> dict[str, Any]:
    """隐藏非执行中的任务，保留任务、运行和事件供审计查询。"""
    normalized: list[int] = []
    for raw_id in task_ids:
        try:
            task_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if task_id > 0 and task_id not in normalized:
            normalized.append(task_id)
    normalized = normalized[:100]
    if not normalized:
        return {"deleted": [], "deleted_count": 0, "skipped": [], "skipped_count": 0}

    _schema.init_operation_schema()
    deleted: list[int] = []
    skipped: list[dict[str, Any]] = []
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT t.id, t.status, t.data,
                   EXISTS (
                     SELECT 1 FROM {_common._table('operation_runs')} active_run
                     WHERE active_run.task_id=t.id
                       AND active_run.status IN ({_common._ACTIVE_RUN_STATUS_SQL})
                   ) AS has_active_run
            FROM {_common._table('operation_tasks')} t
            WHERE t.id = ANY(%s)
            FOR UPDATE OF t
            """,
            (normalized,),
        )
        rows = {int(row["id"]): dict(row) for row in cur.fetchall()}
        for task_id in normalized:
            row = rows.get(task_id)
            if not row:
                skipped.append({"task_id": task_id, "error": "任务不存在"})
                continue
            if _common._task_is_user_deleted(row):
                skipped.append({"task_id": task_id, "error": "任务已删除"})
                continue
            status = str(row.get("status") or "").strip().lower()
            if status in _common._ACTIVE_RUN_STATUSES or bool(row.get("has_active_run")):
                skipped.append({"task_id": task_id, "error": "任务仍在执行，不能删除"})
                continue
            cur.execute(
                f"""
                UPDATE {_common._table('operation_tasks')}
                SET data=COALESCE(data, '{{}}'::jsonb)
                          || jsonb_build_object('deleted_by_user', true, 'deleted_at', now()),
                    updated_at=now()
                WHERE id=%s
                RETURNING id
                """,
                (task_id,),
            )
            if cur.fetchone():
                deleted.append(task_id)
    return {
        "deleted": deleted,
        "deleted_count": len(deleted),
        "skipped": skipped,
        "skipped_count": len(skipped),
    }


def get_run_progress(task_id: int, run_id: int, *, public_status: bool = False) -> dict:
    """Build progress from the complete selected Run, independent of event pages."""
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT id, task_type FROM {_common._table('operation_tasks')} WHERE id=%s",
            (int(task_id),),
        )
        task = cur.fetchone()
        if not task:
            raise LookupError("任务不存在")
        cur.execute(
            f"SELECT rr.*, {_common._compatibility_run_projection_sql()} "
            f"FROM {_common._table('operation_runs')} rr {_common._compatibility_run_joins_sql()} "
            f"WHERE rr.id=%s AND rr.task_id=%s",
            (int(run_id), int(task_id)),
        )
        run_row = cur.fetchone()
        if not run_row:
            raise LookupError("执行实例不存在")
        cur.execute(
            f"""
            SELECT e.*, r.run_no
            FROM {_common._table('operation_events')} e
            LEFT JOIN {_common._table('operation_runs')} r ON r.id=e.run_id
            WHERE e.task_id=%s AND e.run_id=%s
            ORDER BY e.created_at, e.id
            """,
            (int(task_id), int(run_id)),
        )
        events = [_common._normalize_compatibility_event(_common._read_event(dict(row))) for row in cur.fetchall()]
        events.sort(key=_common._event_time_sort_key)
    run = _common._normalize_compatibility_run(_common._row(dict(run_row)) or {})
    internal_status = run.get("status")
    if public_status:
        run["status"] = public_result_status(internal_status, run.get("result_summary"))
    result = build_progress_snapshot(
        int(task["id"]),
        int(run["id"]),
        str(task["task_type"] or ""),
        run,
        events,
    )
    if public_status and internal_status != run.get("status"):
        result["outcome"]["internal_status"] = internal_status
    return result


def _progress_cache_key(run: dict, last_event_id: int) -> tuple:
    return (
        str(run.get("run_uuid") or ""),
        int(run.get("id") or 0),
        int(last_event_id or 0),
        str(run.get("status") or ""),
        str(run.get("progress_stage") or ""),
        str(run.get("completed_at") or ""),
    )


def clear_progress_snapshot_cache() -> None:
    """清空终态 Run 的进度快照缓存；测试或外部直接改事件后使用。"""
    with _PROGRESS_SNAPSHOT_CACHE_LOCK:
        _PROGRESS_SNAPSHOT_CACHE.clear()


def get_registration_progress(job_ids: Iterable[int]) -> dict[int, dict]:
    """批量读取注册页所需的统一 Run 快照，避免每个卡片分别查询数据库。

    注册页每 5 秒轮询一次，而终态 Run 的事件不会继续增长。这里只缓存终态
    Run：活跃 Run 仍每次重算，终态 Run 以 ``最后事件 id + 状态`` 为版本键。
    这样批次里几百个已完成任务不再被重复解析上万条事件。
    """
    ids = sorted({int(value) for value in job_ids if int(value) > 0})
    if not ids:
        return {}
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT rr.*, t.task_type, {_common._compatibility_run_projection_sql()} "
            f"FROM {_common._table('operation_runs')} rr JOIN {_common._table('operation_tasks')} t ON t.id=rr.task_id "
            f"{_common._compatibility_run_joins_sql()} "
            "WHERE rr.source_system='registration_jobs' AND rr.source_id=ANY(%s) "
            "AND COALESCE(t.data->>'deleted_by_user', 'false') <> 'true'",
            ([str(value) for value in ids],),
        )
        runs = [_common._normalize_compatibility_run(_common._row(dict(row)) or {}) for row in cur.fetchall()]
        if not runs:
            return {}
        run_ids = [int(run["id"]) for run in runs]
        cur.execute(
            f"SELECT run_id, MAX(id) AS last_event_id "
            f"FROM {_common._table('operation_events')} WHERE run_id=ANY(%s) GROUP BY run_id",
            (run_ids,),
        )
        last_event_ids = {
            int(row["run_id"]): int(row["last_event_id"] or 0)
            for row in cur.fetchall()
        }

        now = time.monotonic()
        cached: dict[int, dict] = {}
        pending: list[dict] = []
        with _PROGRESS_SNAPSHOT_CACHE_LOCK:
            for run in runs:
                run_id = int(run["id"])
                key = _progress_cache_key(run, last_event_ids.get(run_id, 0))
                entry = _PROGRESS_SNAPSHOT_CACHE.get(run_id)
                if (
                    str(run.get("status") or "") in _common._TERMINAL_STATUSES
                    and entry is not None
                    and entry[1] == key
                    and now - entry[0] <= _PROGRESS_SNAPSHOT_CACHE_TTL
                ):
                    cached[run_id] = entry[2]
                else:
                    pending.append(run)

        by_run: dict[int, list[dict]] = {}
        pending_ids = [int(run["id"]) for run in pending]
        if pending_ids:
            cur.execute(
                f"SELECT * FROM {_common._table('operation_events')} "
                "WHERE run_id=ANY(%s) ORDER BY created_at, id",
                (pending_ids,),
            )
            for raw in cur.fetchall():
                event = _common._normalize_compatibility_event(_common._read_event(dict(raw)))
                by_run.setdefault(int(event["run_id"]), []).append(event)

    result: dict[int, dict] = {}
    for run in runs:
        task_id, run_id = int(run["task_id"]), int(run["id"])
        if run_id in cached:
            result[int(run["source_id"])] = cached[run_id]
            continue
        events = by_run.get(run_id, [])
        events.sort(key=_common._event_time_sort_key)
        payload = {
            "operation_task_id": task_id,
            "operation_run_id": run_id,
            "progress": build_progress_snapshot(task_id, run_id, str(run["task_type"]), run, events),
        }
        if str(run.get("status") or "") in _common._TERMINAL_STATUSES:
            key = _progress_cache_key(run, last_event_ids.get(run_id, 0))
            with _PROGRESS_SNAPSHOT_CACHE_LOCK:
                _PROGRESS_SNAPSHOT_CACHE[run_id] = (now, key, payload)
                if len(_PROGRESS_SNAPSHOT_CACHE) > _PROGRESS_SNAPSHOT_CACHE_MAX:
                    oldest = min(_PROGRESS_SNAPSHOT_CACHE, key=lambda item: _PROGRESS_SNAPSHOT_CACHE[item][0])
                    _PROGRESS_SNAPSHOT_CACHE.pop(oldest, None)
        result[int(run["source_id"])] = payload
    return result


def list_task_events(
    task_id: int,
    *,
    run_id: int | None = None,
    after_id: int | None = None,
    limit: int = 200,
) -> dict:
    """Return one bounded event page; omitted ``after_id`` means latest page."""
    _schema.init_operation_schema()
    page_size = max(1, min(1000, int(limit or 200)))
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT id, task_type FROM {_common._table('operation_tasks')} WHERE id=%s", (int(task_id),))
        task = cur.fetchone()
        if not task:
            raise LookupError("任务不存在")
        params: list[Any] = [int(task_id)]
        where = ["e.task_id=%s"]
        if run_id is not None:
            where.append("e.run_id=%s")
            params.append(int(run_id))
        if after_id is not None:
            where.append("e.id>%s")
            params.append(max(0, int(after_id)))
            order = "e.id ASC"
        else:
            order = "e.id DESC"
        cur.execute(
            f"""
            SELECT e.*, r.run_no
            FROM {_common._table('operation_events')} e
            LEFT JOIN {_common._table('operation_runs')} r ON r.id=e.run_id
            WHERE {' AND '.join(where)}
            ORDER BY {order}
            LIMIT %s
            """,
            (*params, page_size + 1),
        )
        rows = list(cur.fetchall())
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    if after_id is None:
        rows.reverse()
    items = [_common._annotate_stage(_common._normalize_compatibility_event(_common._read_event(dict(row))), str(task["task_type"])) for row in rows]
    return {
        "items": items,
        "next_after_id": max([int(item["id"]) for item in items] or [int(after_id or 0)]),
        "has_more": has_more,
    }


def read_task_run_log(
    task_id: int,
    run_id: int,
    *,
    cursor: int | None = None,
    limit: int = 500,
) -> dict:
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT r.log_file, r.status, r.result_summary, t.task_type FROM {_common._table('operation_runs')} r "
            f"JOIN {_common._table('operation_tasks')} t ON t.id=r.task_id WHERE r.id=%s AND r.task_id=%s",
            (int(run_id), int(task_id)),
        )
        run = cur.fetchone()
        if not run:
            raise LookupError("执行实例不存在")
    result = task_run_log.read_incremental(run.get("log_file"), cursor=cursor, limit=limit)
    items = result.get("items") or []
    event_uuids = [str(item["event_uuid"]) for item in items if item.get("event_uuid")]
    correlations = {}
    if event_uuids:
        with _common._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT id, event_uuid FROM {_common._table('operation_events')} WHERE run_id=%s AND event_uuid=ANY(%s)",
                (int(run_id), event_uuids),
            )
            correlations = {str(row["event_uuid"]): int(row["id"]) for row in cur.fetchall()}
    for item in items:
        _common._annotate_stage(item, str(run["task_type"]), dict(run))
        item["task_id"], item["run_id"] = int(task_id), int(run_id)
        if str(item.get("event_uuid") or "") in correlations:
            item["event_id"] = correlations[str(item["event_uuid"])]
    result["run_terminal"] = str(run.get("status") or "") in _common._TERMINAL_STATUSES
    return result


def find_task_by_source(source_system: str, source_id: str) -> dict | None:
    _schema.init_operation_schema()
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {_common._table('operation_tasks')} WHERE source_system=%s AND source_id=%s",
            (str(source_system), str(source_id)),
        )
        raw = cur.fetchone()
        return _common._row(dict(raw)) if raw else None


def cleanup_terminal_history(
    *,
    retention_days: int,
    limit: int = 500,
    archive,
) -> dict[str, Any]:
    """Archive and delete one bounded batch of expired task-center history.

    The archive callback runs inside the transaction after candidates are
    locked and before any row is deleted.  Raising from the callback aborts
    the transaction, so a task is never removed without a verified archive.
    """
    _schema.init_operation_schema()
    days = int(retention_days or 0)
    if days <= 0:
        return {"deleted_tasks": 0, "deleted_batches": 0, "disabled": True}
    if not callable(archive):
        raise ValueError("任务中心清理必须提供归档回调")
    row_limit = max(1, min(5000, int(limit or 500)))
    cutoff = _common._now() - timedelta(days=days)
    with _common._connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS locked",
            ("task_center_retention",),
        )
        if not bool(cur.fetchone()["locked"]):
            return {"deleted_tasks": 0, "deleted_batches": 0, "locked": True}
        # 与订单预约、关联写入共用锁，避免候选选出后出现新的原单引用。
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"{_common._schema_name()}:independent-payment:xxsyun",))
        cur.execute(
            f"""
            SELECT task.*
            FROM {_common._table('operation_tasks')} task
            WHERE task.status IN ({_common._TERMINAL_STATUS_SQL})
              AND NOT (task.data ? 'bulk_target_round_id')
              AND task.completed_at IS NOT NULL
              AND task.completed_at < %s
              AND NOT EXISTS (
                  SELECT 1 FROM {_common._table('extract_link_payment_orders')} payment
                  WHERE payment.task_id=task.id
                    AND (payment.payment_state IN ('pending','unknown')
                      OR (payment.payment_state='succeeded'
                        AND COALESCE(payment.summary->>'plus_verification_status', '')
                            NOT IN ('confirmed','not_applicable')))
              )
              AND NOT EXISTS (
                  SELECT 1 FROM {_common._table('extract_link_payment_orders')} original
                  JOIN {_common._table('extract_link_payment_orders')} linked
                    ON linked.summary->>'related_payment_order_id'=original.id::text
                  WHERE original.task_id=task.id AND linked.task_id<>task.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM {_common._table('operation_runs')} uncertain_run
                  WHERE uncertain_run.task_id=task.id
                    AND task.task_type IN ('token_refresh', 'live_check')
                    AND uncertain_run.status='failed'
                    AND uncertain_run.result_summary->>'cause_code' IN ('password_change_required', 'password_page_error')
                    AND uncertain_run.result_summary->>'outcome'='request_unknown'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM {_common._table('operation_runs')} run
                  WHERE run.task_id=task.id
                    AND run.status IN ({_common._ACTIVE_RUN_STATUS_SQL})
              )
              AND NOT (
                  task.source_system='registration_jobs'
                  AND EXISTS (
                      SELECT 1 FROM {_common._table('registration_jobs')} source_task
                      WHERE source_task.id::text=task.source_id
                        AND source_task.status IN ({_common._ACTIVE_RUN_STATUS_SQL})
                  )
              )
              AND NOT (
                  task.source_system='account_action_tasks'
                  AND EXISTS (
                      SELECT 1 FROM {_common._table('account_action_tasks')} source_task
                      WHERE source_task.id::text=task.source_id
                        AND source_task.status IN ({_common._ACTIVE_RUN_STATUS_SQL})
                  )
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM {_common._table('account_operation_leases')} lease
                  JOIN {_common._table('operation_runs')} run ON run.id=lease.run_id
                  WHERE run.task_id=task.id AND lease.expires_at >= now()
              )
              AND NOT EXISTS (
                  SELECT 1 FROM {_common._table('operation_tasks')} child
                  WHERE child.id<>task.id
                    AND (child.parent_task_id=task.id OR child.root_task_id=task.id)
              )
              AND NOT EXISTS (
                  SELECT 1 FROM {_common._table('operation_task_dependencies')} dependency
                  WHERE dependency.status<>'completed'
                    AND (
                      (
                        dependency.parent_source_system=task.source_system
                        AND dependency.parent_source_id IN (task.source_id, task.id::text)
                      ) OR (
                        dependency.child_source_system=task.source_system
                        AND dependency.child_source_id IN (task.source_id, task.id::text)
                      )
                    )
              )
            ORDER BY task.completed_at, task.id
            LIMIT %s
            FOR UPDATE OF task
            """,
            (cutoff, row_limit),
        )
        tasks = [dict(row) for row in cur.fetchall()]
        cur.execute(
            f"""
            SELECT batch.*
            FROM {_common._table('operation_batches')} batch
            WHERE batch.status IN ({_common._TERMINAL_STATUS_SQL})
              AND batch.source_system <> 'bulk_manager'
              AND batch.completed_at IS NOT NULL
              AND batch.completed_at < %s
              AND NOT EXISTS (
                  SELECT 1 FROM {_common._table('operation_tasks')} task
                  WHERE task.batch_id=batch.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM {_common._table('operation_runs')} run
                  WHERE run.batch_id=batch.id
                    AND run.status IN ({_common._ACTIVE_RUN_STATUS_SQL})
              )
              AND NOT EXISTS (
                  SELECT 1 FROM {_common._table('operation_projection_queue')} queue
                  WHERE queue.batch_id=batch.id
                    AND queue.status IN ('queued', 'running')
              )
            ORDER BY batch.created_at, batch.id
            LIMIT %s
            FOR UPDATE OF batch
            """,
            (cutoff, row_limit),
        )
        empty_batches = [dict(row) for row in cur.fetchall()]
        if not tasks and not empty_batches:
            return {
                "deleted_tasks": 0,
                "deleted_batches": 0,
                "cutoff": cutoff.isoformat(),
            }
        task_ids = [int(row["id"]) for row in tasks]
        task_batch_ids = sorted({int(row["batch_id"]) for row in tasks if row.get("batch_id")})
        empty_batch_ids = [int(row["id"]) for row in empty_batches]
        batch_ids = sorted(set(task_batch_ids) | set(empty_batch_ids))

        def fetch(sql: str, params=()) -> list[dict]:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

        runs = (
            fetch(
                f"SELECT * FROM {_common._table('operation_runs')} WHERE task_id=ANY(%s) ORDER BY id",
                (task_ids,),
            ) if task_ids else []
        )
        run_ids = [int(row["id"]) for row in runs]
        native_task_ids = {
            int(row["id"]) for row in tasks
            if str(row.get("source_system") or "") == "native_operations"
        }
        native_log_files = sorted({
            str(row.get("log_file") or "").strip()
            for row in runs
            if int(row["task_id"]) in native_task_ids
            and str(row.get("log_file") or "").strip()
        })
        events = (
            fetch(
                f"SELECT * FROM {_common._table('operation_events')} WHERE task_id=ANY(%s) ORDER BY id",
                (task_ids,),
            ) if task_ids else []
        )
        resources = (
            fetch(
                f"SELECT * FROM {_common._table('operation_resources')} WHERE run_id=ANY(%s) ORDER BY id",
                (run_ids,),
            ) if run_ids else []
        )
        leases = (
            fetch(
                f"SELECT * FROM {_common._table('account_operation_leases')} WHERE run_id=ANY(%s) ORDER BY run_id",
                (run_ids,),
            ) if run_ids else []
        )
        batch_items = (
            fetch(
                f"SELECT * FROM {_common._table('operation_batch_items')} WHERE task_id=ANY(%s) ORDER BY id",
                (task_ids,),
            ) if task_ids else []
        )
        batches = (
            fetch(
                f"SELECT * FROM {_common._table('operation_batches')} WHERE id=ANY(%s) ORDER BY id",
                (batch_ids,),
            ) if batch_ids else []
        )
        projection_queue = (
            fetch(
                f"SELECT * FROM {_common._table('operation_projection_queue')} WHERE batch_id=ANY(%s) ORDER BY id",
                (batch_ids,),
            ) if batch_ids else []
        )
        dependencies = (
            fetch(
                f"""
                SELECT dependency.*
                FROM {_common._table('operation_task_dependencies')} dependency
                WHERE EXISTS (
                    SELECT 1 FROM {_common._table('operation_tasks')} task
                    WHERE task.id=ANY(%s)
                      AND (
                        (
                          dependency.parent_source_system=task.source_system
                          AND dependency.parent_source_id IN (task.source_id, task.id::text)
                        ) OR (
                          dependency.child_source_system=task.source_system
                          AND dependency.child_source_id IN (task.source_id, task.id::text)
                        )
                      )
                )
                ORDER BY dependency.id
                """,
                (task_ids,),
            ) if task_ids else []
        )
        payment_orders = (
            fetch(f"SELECT * FROM {_common._table('extract_link_payment_orders')} WHERE task_id=ANY(%s) ORDER BY id",
                  (task_ids,)) if task_ids else []
        )
        snapshot = {
            "version": 1,
            "created_at": _common._now().isoformat(),
            "cutoff": cutoff.isoformat(),
            "retention_days": days,
            "tasks": [_common._row(row) or {} for row in tasks],
            "runs": [_common._row(row) or {} for row in runs],
            "events": [_common._row(row) or {} for row in events],
            "resources": [_common._row(row) or {} for row in resources],
            "leases": [_common._row(row) or {} for row in leases],
            "batch_items": [_common._row(row) or {} for row in batch_items],
            "batches": [_common._row(row) or {} for row in batches],
            "projection_queue": [_common._row(row) or {} for row in projection_queue],
            "dependencies": [_common._row(row) or {} for row in dependencies],
            "extract_link_payment_orders": [_common._row(row) or {} for row in payment_orders],
        }
        archive_result = archive(snapshot)

        completed_dependency_ids = [
            int(row["id"]) for row in dependencies
            if str(row.get("status") or "") == "completed"
        ]
        if completed_dependency_ids:
            cur.execute(
                f"DELETE FROM {_common._table('operation_task_dependencies')} WHERE id=ANY(%s)",
                (completed_dependency_ids,),
            )
        deleted_tasks = 0
        if task_ids:
            cur.execute(
                f"DELETE FROM {_common._table('operation_tasks')} WHERE id=ANY(%s)",
                (task_ids,),
            )
            deleted_tasks = int(cur.rowcount)
        deleted_batches = 0
        if empty_batch_ids:
            cur.execute(
                f"""
                DELETE FROM {_common._table('operation_batches')} batch
                WHERE batch.id=ANY(%s)
                  AND batch.status IN ({_common._TERMINAL_STATUS_SQL})
                  AND batch.completed_at IS NOT NULL
                  AND batch.completed_at < %s
                  AND NOT EXISTS (
                      SELECT 1 FROM {_common._table('operation_tasks')} task
                      WHERE task.batch_id=batch.id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM {_common._table('operation_runs')} run
                      WHERE run.batch_id=batch.id
                        AND run.status IN ({_common._ACTIVE_RUN_STATUS_SQL})
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM {_common._table('operation_projection_queue')} queue
                      WHERE queue.batch_id=batch.id
                        AND queue.status IN ('queued', 'running')
                  )
                """,
                (empty_batch_ids, cutoff),
            )
            deleted_batches += int(cur.rowcount)
        if task_batch_ids:
            cur.execute(
                f"""
                DELETE FROM {_common._table('operation_batches')} batch
                WHERE batch.id=ANY(%s)
                  AND batch.completed_at IS NOT NULL
                  AND batch.completed_at < %s
                  AND batch.status IN ({_common._TERMINAL_STATUS_SQL})
                  AND NOT EXISTS (
                      SELECT 1 FROM {_common._table('operation_tasks')} task
                      WHERE task.batch_id=batch.id
                  )
                """,
                (task_batch_ids, cutoff),
            )
            deleted_batches += int(cur.rowcount)
        return {
            "deleted_tasks": deleted_tasks,
            "deleted_batches": deleted_batches,
            "cutoff": cutoff.isoformat(),
            "archive": archive_result,
            "native_log_files": native_log_files,
            # Deleting a leaf can make its expired parent eligible.  Force one
            # more bounded pass after any deletion; an empty pass terminates
            # the daily drain without guessing from the current batch size.
            "has_more": deleted_tasks > 0 or deleted_batches > 0,
        }


# 旧模块保留同签名委托；运行状态、线程和 SQL 实现只存在于职责模块中。


def _run_projection_write_with_retry(write, *, operation_name: str = "projection"):
    return _projection._run_projection_write_with_retry(write, operation_name=operation_name)


def _schema_name() -> str:
    return _common._schema_name()


def _quote(value: str) -> str:
    return _common._quote(value)


def _table(name: str) -> str:
    return _common._table(name)


def _connect():
    return _common._connect()


def _now() -> datetime:
    return _common._now()


def _legacy_timestamp(value: Any) -> datetime | None:
    return _common._legacy_timestamp(value)


def _legacy_account_timestamp(value: Any) -> datetime | None:
    return _common._legacy_account_timestamp(value)


def _legacy_registration_timestamp(value: Any) -> datetime | None:
    return _common._legacy_registration_timestamp(value)


def _uuid(kind: str, source: object) -> str:
    return _common._uuid(kind, source)


def _text(value: Any, limit: int = 1200) -> str:
    return _common._text(value, limit)


def _scrub(value: Any, depth: int = 0) -> Any:
    return _common._scrub(value, depth)


def _json(value: Any) -> str:
    return _common._json(value)


def _decode(value: Any) -> Any:
    return _common._decode(value)


def _row(row: dict | None) -> dict | None:
    return _common._row(row)


def _task_is_user_deleted(row: dict | None) -> bool:
    return _common._task_is_user_deleted(row)


def _legacy_event_type_for_read(event: dict) -> str:
    return _common._legacy_event_type_for_read(event)


def _read_event(row: dict) -> dict:
    return _common._read_event(row)


def _annotate_stage(record: dict, task_type: str, run: dict | None = None) -> dict:
    return _common._annotate_stage(record, task_type, run)


def _registration_progress_occurrence(detail: dict, state: str) -> datetime | None:
    return _common._registration_progress_occurrence(detail, state)


def _normalize_compatibility_event(event: dict) -> dict:
    return _common._normalize_compatibility_event(event)


def _event_time_sort_key(event: dict) -> tuple[datetime, int]:
    return _common._event_time_sort_key(event)


def reset_ready() -> None:
    return _schema.reset_operation_ready()


def init() -> None:
    return _schema.init_operation_schema()


def _account_extra(account: dict | None) -> dict:
    return _common._account_extra(account)


def _account_state(account: dict | None) -> dict[str, str]:
    return _common._account_state(account)


def _account_is_deactivated(account: dict | None) -> bool:
    return _common._account_is_deactivated(account)


def _finish_deactivated_before_execution(
    run_id: int,
    *,
    execution_id: str | None = None,
    lease_token: str | None = None,
) -> dict:
    return _runtime._finish_deactivated_before_execution(run_id, execution_id=execution_id, lease_token=lease_token)


def _error_fields(
    message: Any, *, stage: str = "", task_type: str = "",
    result_summary: dict | None = None, task_status: str = "",
) -> tuple[str | None, str | None, str | None]:
    return _common._error_fields(message, stage=stage, task_type=task_type, result_summary=result_summary, task_status=task_status)


def _status(value: Any) -> str:
    return _common._status(value)


def _select_current_run(runs: Iterable[dict]) -> dict | None:
    return _common._select_current_run(runs)


def _compatibility_run_status_sql(
    *, run_alias: str = "rr", registration_alias: str = "registration_job",
    account_alias: str = "account_task",
) -> str:
    return _common._compatibility_run_status_sql(run_alias=run_alias, registration_alias=registration_alias, account_alias=account_alias)


def _compatibility_run_projection_sql(
    *, run_alias: str = "rr", registration_alias: str = "registration_job",
    account_alias: str = "account_task",
) -> str:
    return _common._compatibility_run_projection_sql(run_alias=run_alias, registration_alias=registration_alias, account_alias=account_alias)


def _compatibility_run_joins_sql(*, run_alias: str = "rr") -> str:
    return _common._compatibility_run_joins_sql(run_alias=run_alias)


def _normalize_compatibility_run(run: dict) -> dict:
    return _common._normalize_compatibility_run(run)


def _normalize_legacy_registration_progress_steps(value: Any) -> Any:
    return _common._normalize_legacy_registration_progress_steps(value)


def _apply_current_run_projection(task: dict, run: dict | None) -> dict:
    return _common._apply_current_run_projection(task, run)


def _duration(started: Any, completed: Any, explicit: Any = None) -> int | None:
    return _common._duration(started, completed, explicit)


def _upsert_batch(
    cur,
    *,
    source_system: str,
    source_id: str,
    batch_type: str,
    title: str,
    requested_count: int,
    created_by: str,
    created_at: Any,
    completed_at: Any = None,
    data: dict | None = None,
) -> int:
    return _projection._upsert_batch(cur, source_system=source_system, source_id=source_id, batch_type=batch_type, title=title, requested_count=requested_count, created_by=created_by, created_at=created_at, completed_at=completed_at, data=data)


def _upsert_attempt(cur, *, root_job_id: int, job: dict, account: dict | None) -> int:
    return _projection._upsert_attempt(cur, root_job_id=root_job_id, job=job, account=account)


def _registration_task_type(job: dict) -> str:
    return _projection._registration_task_type(job)


def _next_registration_actions(
    job: dict,
    account: dict | None,
    target_status: str,
    *,
    remote_identity_state: str = "not_started",
    remote_account_state: str = "not_started",
) -> list[dict[str, Any]]:
    return _projection._next_registration_actions(job, account, target_status, remote_identity_state=remote_identity_state, remote_account_state=remote_account_state)


def _lookup_task(cur, source_system: str, source_id: str) -> int | None:
    return _projection._lookup_task(cur, source_system, source_id)


def _registration_run_cause_summary(cur, job_id: int, *, job_status: str) -> dict[str, Any]:
    return _projection._registration_run_cause_summary(cur, job_id, job_status=job_status)


def _upsert_registration_job(cur, job: dict, accounts_by_id: dict[int, dict], accounts_by_email: dict[str, dict]) -> int:
    return _projection._upsert_registration_job(cur, job, accounts_by_id, accounts_by_email)


def _upsert_account_batch(cur, batch: dict) -> int:
    return _projection._upsert_account_batch(cur, batch)


def _upsert_account_task(
    cur,
    task: dict,
    batch_map: dict[str, int],
    accounts_by_id: dict[int, dict] | None = None,
) -> int:
    return _projection._upsert_account_task(cur, task, batch_map, accounts_by_id)


def _upsert_account_event(cur, event: dict, task_map: dict[int, int]) -> None:
    return _projection._upsert_account_event(cur, event, task_map)


def _lock_projection_batch(cur, batch_id: int) -> None:
    return _projection._lock_projection_batch(cur, batch_id)


def _effective_batch_status_counts(cur, batch_id: int) -> dict[str, int]:
    return _projection._effective_batch_status_counts(cur, batch_id)


def _lock_existing_projection_queue(cur, batch_id: int) -> dict | None:
    return _projection._lock_existing_projection_queue(cur, batch_id)


def _refresh_batch(cur, batch_id: int) -> None:
    return _projection._refresh_batch(cur, batch_id)


def _refresh_batches(cur, batch_ids: Iterable[int] | None = None) -> None:
    return _projection._refresh_batches(cur, batch_ids)


def _projection_backoff(attempts: int) -> int:
    return _projection._projection_backoff(attempts)


def _enqueue_batch_projection_cur(
    cur,
    batch_id: int,
    *,
    reason: str = "event",
    source_system: str = "",
    source_id: str = "",
    requested_at: Any = None,
) -> dict:
    return _projection._enqueue_batch_projection_cur(cur, batch_id, reason=reason, source_system=source_system, source_id=source_id, requested_at=requested_at)


def enqueue_batch_projection(
    batch_id: int,
    *,
    reason: str = "event",
    source_system: str = "",
    source_id: str = "",
    requested_at: Any = None,
) -> dict:
    return _projection.enqueue_batch_projection(batch_id, reason=reason, source_system=source_system, source_id=source_id, requested_at=requested_at)


def _claim_projection_cur(cur, *, worker_id: str) -> dict | None:
    # Fixed lock order: projection_queue row -> operation_batches row.
    # A process crash can leave a queue row in ``running`` forever.  Reclassify
    # only expired leases before claiming so a later worker can retry it.
    return _projection._claim_projection_cur(cur, worker_id=worker_id)


def claim_projection(*, worker_id: str | None = None) -> dict | None:
    return _projection.claim_projection(worker_id=worker_id)


def _complete_projection(batch_id: int, queue_id: int) -> dict:
    return _projection._complete_projection(batch_id, queue_id)


def _fail_projection(batch_id: int, queue_id: int, error: BaseException) -> dict:
    return _projection._fail_projection(batch_id, queue_id, error)


def _compat_registration_event_detail(event: dict) -> tuple[str, str, dict, str | None, str | None]:
    return _projection._compat_registration_event_detail(event)


def _project_registration_fact_events(cur, batch_id: int) -> int:
    return _projection._project_registration_fact_events(cur, batch_id)


def _repair_terminal_task_projection(cur, batch_id: int) -> int:
    return _projection._repair_terminal_task_projection(cur, batch_id)


def _project_claimed_batch(claimed: dict) -> None:
    return _projection._project_claimed_batch(claimed)


def run_projection_once(*, worker_id: str | None = None) -> dict | None:
    return _projection.run_projection_once(worker_id=worker_id)


def drain_projection_queue(*, limit: int = 100, worker_id: str | None = None) -> list[dict]:
    return _projection.drain_projection_queue(limit=limit, worker_id=worker_id)


def _projection_worker_loop(interval_seconds: float) -> None:
    return _projection._projection_worker_loop(interval_seconds)


def start_projection_worker(*, interval_seconds: float = 1.0) -> bool:
    return _projection.start_projection_worker(interval_seconds=interval_seconds)


def stop_projection_worker(*, timeout: float = 2.0) -> bool:
    return _projection.stop_projection_worker(timeout=timeout)


def projection_worker_status() -> dict[str, object]:
    return _projection.projection_worker_status()


def reconcile_all() -> dict[str, int]:
    return _projection.reconcile_all()


def repair_stale_compatibility_projections(*, limit: int = 500) -> int:
    return _projection.repair_stale_compatibility_projections(limit=limit)


def _correct_registration_failure_projection(
    cur, *, job_id: int, error_message: str, diagnostic_summary: dict,
) -> None:
    return _projection._correct_registration_failure_projection(cur, job_id=job_id, error_message=error_message, diagnostic_summary=diagnostic_summary)


def sync_registration_job(job_id: int) -> None:
    return _projection.sync_registration_job(job_id)


def sync_account_task(task_id: int) -> None:
    return _projection.sync_account_task(task_id)


def mark_registration_jobs_deleted(job_ids: Iterable[int]) -> None:
    return _projection.mark_registration_jobs_deleted(job_ids)


def register_task_dependency(
    *,
    parent_source_system: str,
    parent_source_id: str,
    child_source_system: str,
    child_source_id: str,
    dependency_type: str,
    payload: dict | None = None,
    expected_parent_run_id: int | None = None,
) -> dict:
    return _runtime.register_task_dependency(parent_source_system=parent_source_system, parent_source_id=parent_source_id, child_source_system=child_source_system, child_source_id=child_source_id, dependency_type=dependency_type, payload=payload, expected_parent_run_id=expected_parent_run_id)


def mark_task_dependency_ready(
    *,
    child_source_system: str,
    child_source_id: str,
    child_status: str,
    child_result: dict | None = None,
) -> list[dict]:
    return _runtime.mark_task_dependency_ready(child_source_system=child_source_system, child_source_id=child_source_id, child_status=child_status, child_result=child_result)


def list_ready_task_dependencies(*, limit: int = 100, initialize: bool = True) -> list[dict]:
    return _runtime.list_ready_task_dependencies(limit=limit, initialize=initialize)


def claim_task_dependency(dependency_id: int, *, initialize: bool = True, conn=None) -> dict | None:
    return _runtime.claim_task_dependency(dependency_id, initialize=initialize, conn=conn)


def recover_stale_task_dependencies(*, stale_after_seconds: int = 15 * 60) -> int:
    return _recovery.recover_stale_task_dependencies(stale_after_seconds=stale_after_seconds)


def complete_task_dependency(
    dependency_id: int,
    *,
    success: bool,
    error: str | None = None,
) -> bool:
    return _runtime.complete_task_dependency(dependency_id, success=success, error=error)


def apply_task_dependency_result(
    *,
    parent_source_system: str,
    parent_source_id: str,
    child_status: str,
    child_result: dict | None = None,
    expected_parent_run_id: int | None = None,
) -> dict | None:
    return _runtime.apply_task_dependency_result(parent_source_system=parent_source_system, parent_source_id=parent_source_id, child_status=child_status, child_result=child_result, expected_parent_run_id=expected_parent_run_id)


def _reconcile_parent_task_cur(cur, parent_task_id: int, *, child_task_id: int | None = None) -> dict | None:
    return _runtime._reconcile_parent_task_cur(cur, parent_task_id, child_task_id=child_task_id)


def reconcile_parent_task(parent_task_id: int) -> dict | None:
    return _runtime._reconcile_parent_task(parent_task_id)


def create_runtime_batch(
    *, batch_type: str, title: str, requested_count: int, trigger: str = "manual",
    data: dict | None = None,
) -> dict:
    return _runtime.create_runtime_batch(batch_type=batch_type, title=title, requested_count=requested_count, trigger=trigger, data=data)


def _insert_runtime_run(
    cur,
    *,
    task_id: int,
    run_no: int,
    source_system: str,
    account_id: int | None,
    batch_id: int | None,
    resource_family: str,
    data: dict | None,
    initial_status: str = "queued",
    task_uuid: str | None = None,
) -> dict:
    return _runtime._insert_runtime_run(cur, task_id=task_id, run_no=run_no, source_system=source_system, account_id=account_id, batch_id=batch_id, resource_family=resource_family, data=data, initial_status=initial_status, task_uuid=task_uuid)


def create_runtime_task(
    *,
    task_type: str,
    account_id: int | None,
    email: str,
    trigger: str = "manual",
    batch_id: int | None = None,
    batch_ordinal: int | None = None,
    parent_task_id: int | None = None,
    resource_family: str = "openai_interactive",
    data: dict | None = None,
    source_system: str = "native_operations",
    source_id: str | None = None,
    idempotency_key: str | None = None,
    conn=None,
) -> dict:
    return _runtime.create_runtime_task(task_type=task_type, account_id=account_id, email=email, trigger=trigger, batch_id=batch_id, batch_ordinal=batch_ordinal, parent_task_id=parent_task_id, resource_family=resource_family, data=data, source_system=source_system, source_id=source_id, idempotency_key=idempotency_key, conn=conn)


def create_runtime_tasks_many(specifications: list[dict], *, conn) -> list[dict]:
    return _runtime.create_runtime_tasks_many(specifications, conn=conn)


def _remote_write_checkpoint(data: Any) -> dict:
    return _runtime._remote_write_checkpoint(data)


def retry_runtime_task(task_id: int, *, trigger: str = "manual_retry", data: dict | None = None,
                       expected_previous_run_id: int | None = None, conn=None) -> dict:
    return _runtime.retry_runtime_task(task_id, trigger=trigger, data=data, expected_previous_run_id=expected_previous_run_id, conn=conn)


def get_run(run_id: int) -> dict | None:
    return _runtime.get_run(run_id)


def _attach_admission_wait(rows: list[dict], *, conn, run_rows: bool = False) -> None:
    return _common._attach_admission_wait(rows, conn=conn, run_rows=run_rows)


def list_interrupted_runtime_runs(
    *, task_type: str | None = None,
    recovery_reason: str | None = None,
    limit: int = 500,
) -> list[dict]:
    return _recovery.list_interrupted_runtime_runs(task_type=task_type, recovery_reason=recovery_reason, limit=limit)


def mark_runtime_run_projection_reconciled(run_id: int, *, repaired_count: int = 0) -> bool:
    return _recovery.mark_runtime_run_projection_reconciled(run_id, repaired_count=repaired_count)


def active_run_for_account(account_id: int, resource_family: str = "openai_interactive", *, conn=None) -> dict | None:
    return _runtime.active_run_for_account(account_id, resource_family, conn=conn)


def has_active_runtime_operations(
    *,
    task_types: Iterable[str] | None = None,
    source_systems: Iterable[str] | None = None,
) -> bool:
    return _recovery.has_active_runtime_operations(task_types=task_types, source_systems=source_systems)


def list_active_runtime_recovery_exclusions(
    *,
    task_types: Iterable[str] | None = None,
    source_systems: Iterable[str] | None = None,
) -> dict[str, Any]:
    return _recovery.list_active_runtime_recovery_exclusions(task_types=task_types, source_systems=source_systems)


def list_reconciliation_accounts(
    *,
    task_type: str,
    account_ids: Iterable[int] | None = None,
    source_systems: Iterable[str] | None = ("native_operations",),
    limit: int = 5000,
) -> list[dict]:
    return _recovery.list_reconciliation_accounts(task_type=task_type, account_ids=account_ids, source_systems=source_systems, limit=limit)


def list_queued_runs(*, limit: int = 500) -> list[dict]:
    return _runtime.list_queued_runs(limit=limit)


def _extract_batch_workers_sql(alias: str = "b") -> str:
    return _runtime._extract_batch_workers_sql(alias)


def _extract_batch_has_capacity_sql() -> str:
    return _runtime._extract_batch_has_capacity_sql()


def _claim_extract_batch_capacity(conn, cur, run: dict) -> bool:
    return _runtime._claim_extract_batch_capacity(conn, cur, run)


def list_dispatchable_runs(
    *,
    limit: int = 500,
    task_types: Iterable[str] | None = None,
    source_systems: Iterable[str] | None = None,
    prioritize_continuations: bool = False,
) -> list[dict]:
    return _runtime.list_dispatchable_runs(limit=limit, task_types=task_types, source_systems=source_systems, prioritize_continuations=prioritize_continuations)


def claim_next_queued_run(
    *,
    execution_id: str,
    worker_pid: int,
    source_systems: Iterable[str] | None = None,
    task_types: Iterable[str] | None = None,
) -> dict | None:
    return _runtime.claim_next_queued_run(execution_id=execution_id, worker_pid=worker_pid, source_systems=source_systems, task_types=task_types)


def _requeue_stale_extract_continuations(cur, stale_seconds: int) -> list[dict]:
    return _recovery._requeue_stale_extract_continuations(cur, stale_seconds)


def recover_interrupted_runtime_runs(*, stale_after_seconds: int = 15 * 60) -> int:
    return _recovery.recover_interrupted_runtime_runs(stale_after_seconds=stale_after_seconds)


def refresh_runtime_batches(batch_ids: Iterable[int] | None = None) -> None:
    return _runtime.refresh_runtime_batches(batch_ids)


def mark_runtime_batch_empty(batch_id: int, *, status: str = "failed") -> None:
    return _runtime.mark_runtime_batch_empty(batch_id, status=status)


def set_runtime_batch_skipped(batch_id: int, skipped: list[dict]) -> None:
    return _runtime.set_runtime_batch_skipped(batch_id, skipped)


def claim_run(run_id: int, *, execution_id: str, worker_pid: int, conn=None) -> dict | None:
    return _runtime.claim_run(run_id, execution_id=execution_id, worker_pid=worker_pid, conn=conn)


def requeue_claimed_run(
    run_id: int,
    *,
    execution_id: str,
    reason: str,
    delay_seconds: float = 1.0,
    data: Mapping[str, Any] | None = None,
    stage: str = "queued",
    lease_token: str | None = None,
    settlement_intent=None, settlement_domain=None, deadline=None,
) -> dict | None:
    return _runtime.requeue_claimed_run(run_id, execution_id=execution_id, reason=reason, delay_seconds=delay_seconds, data=data, stage=stage, lease_token=lease_token, settlement_intent=settlement_intent, settlement_domain=settlement_domain, deadline=deadline)


def append_runtime_event(
    run_id: int,
    *,
    stage: str,
    message: str,
    state: str | None = None,
    level: str = "INFO",
    event_type: str | None = None,
    detail: dict | None = None,
) -> dict:
    return _runtime.append_runtime_event(run_id, stage=stage, message=message, state=state, level=level, event_type=event_type, detail=detail)


def _remote_checkpoint_fence(
    cur,
    run_id: int,
    *,
    execution_id: str,
    lease_token: str | None,
    require_lease: bool,
) -> dict:
    return _runtime._remote_checkpoint_fence(cur, run_id, execution_id=execution_id, lease_token=lease_token, require_lease=require_lease)


def fence_execution(cur, run_id: int, *, execution_id: str, lease_token: str) -> dict:
    return _runtime.fence_execution(cur, run_id, execution_id=execution_id, lease_token=lease_token)


def _remote_checkpoint_event(
    cur,
    run: dict,
    *,
    event_type: str,
    message: str,
    detail: dict[str, Any],
) -> None:
    return _runtime._remote_checkpoint_event(cur, run, event_type=event_type, message=message, detail=detail)


def record_remote_intent(
    run_id: int,
    *,
    execution_id: str,
    lease_token: str | None = None,
    action: str,
    intent_kind: str = "remote_write",
    request_id: str | None = None,
    detail: dict | None = None,
) -> dict:
    return _runtime.record_remote_intent(run_id, execution_id=execution_id, lease_token=lease_token, action=action, intent_kind=intent_kind, request_id=request_id, detail=detail)


def record_remote_receipt(
    run_id: int,
    *,
    execution_id: str,
    lease_token: str | None = None,
    outcome: str | None = None,
    receipt_state: str | None = None,
    action: str | None = None,
    request_id: str | None = None,
    detail: dict | None = None,
) -> dict:
    return _runtime.record_remote_receipt(run_id, execution_id=execution_id, lease_token=lease_token, outcome=outcome, receipt_state=receipt_state, action=action, request_id=request_id, detail=detail)


def heartbeat_run(run_id: int, lease_token: str = "", *, ttl_seconds: int = 600) -> bool:
    return _runtime.heartbeat_run(run_id, lease_token, ttl_seconds=ttl_seconds)


def acquire_account_lease(
    *, account_id: int, run_id: int, resource_family: str = "openai_interactive",
    ttl_seconds: int = 600,
) -> str | None:
    return _runtime._acquire_account_lease(account_id=account_id, run_id=run_id, resource_family=resource_family, ttl_seconds=ttl_seconds)


def release_account_lease(run_id: int, lease_token: str = "") -> bool:
    return _runtime.release_account_lease(run_id, lease_token)


def request_run_cancel(
    run_id: int,
    *,
    reason: str = "用户手动停止",
    expected_status: str | None = None,
    conn=None,
) -> dict:
    return _runtime.request_run_cancel(run_id, reason=reason, expected_status=expected_status, conn=conn)


def terminate_run(run_id: int, *, reason: str = "用户手动终止任务") -> dict:
    return _runtime.terminate_run(run_id, reason=reason)


def is_run_cancel_requested(run_id: int, cancellation_token: str = "") -> bool:
    return _runtime.is_run_cancel_requested(run_id, cancellation_token)


def mark_run_settling(run_id: int) -> bool:
    return _runtime.mark_run_settling(run_id)


def register_resource(
    run_id: int, *, resource_type: str, provider: str = "", external_id: str = "",
    detail: dict | None = None,
) -> dict:
    return _runtime.register_resource(run_id, resource_type=resource_type, provider=provider, external_id=external_id, detail=detail)


def release_resource(resource_id: int, *, state: str = "released", detail: dict | None = None) -> bool:
    return _runtime.release_resource(resource_id, state=state, detail=detail)


def _confirmed_extract_terminal_failure(cur, run: dict, result_summary: dict) -> bool:
    return _runtime._confirmed_extract_terminal_failure(cur, run, result_summary)


def _confirmed_independent_payment_partial(cur, run: dict, result_summary: dict) -> bool:
    return _runtime._confirmed_independent_payment_partial(cur, run, result_summary)


def _confirmed_plan_refresh(run: dict, result_summary: dict) -> bool:
    return _runtime._confirmed_plan_refresh(run, result_summary)


def _confirmed_account_setup_partial(cur, run: dict, result_summary: dict) -> bool:
    return _runtime._confirmed_account_setup_partial(cur, run, result_summary)


def finish_run(
    run_id: int,
    *,
    status: str,
    message: str = "",
    result_summary: dict | None = None,
    error: str | None = None,
    execution_id: str | None = None,
    lease_token: str | None = None,
    force_terminate: bool = False,
    settlement_intent=None, settlement_domain=None, deadline=None,
) -> dict:
    return _runtime.finish_run(run_id, status=status, message=message, result_summary=result_summary, error=error, execution_id=execution_id, lease_token=lease_token, force_terminate=force_terminate, settlement_intent=settlement_intent, settlement_domain=settlement_domain, deadline=deadline)


def submit_intent(intent, *, domain, deadline=None):
    from core.storage.operations import settlements
    return settlements.submit_intent(intent, domain=domain, deadline=deadline)


def read_receipt(intent, *, domain, deadline=None):
    from core.storage.operations import settlements
    return settlements.read_receipt(intent, domain=domain, deadline=deadline)


def pending_cleanup(*, domain, limit=32, deadline=None):
    from core.storage.operations import settlements
    return settlements.pending_cleanup(domain=domain, limit=limit, deadline=deadline)


def run_cleanup_once(*, domain, deadline=None, permit_id=None, execution_id=None):
    from core.storage.operations import settlements
    return settlements.run_cleanup_once(domain=domain, deadline=deadline, permit_id=permit_id, execution_id=execution_id)


def cleanup_blocks_permit(permit_id, execution_id, *, domain, conn=None, deadline=None):
    from core.storage.operations import settlements
    return settlements.cleanup_blocks_permit(permit_id, execution_id, domain=domain, conn=conn, deadline=deadline)


def verify() -> dict[str, Any]:
    return _projection.verify()


# 兼容读取的无状态常量；不复制 READY_KEY 或投影线程状态。
from core.storage.operations.common import (
    _IDENTIFIER_RE as _IDENTIFIER_RE,
    _SCHEMA_ENV as _SCHEMA_ENV,
    _TERMINAL_STATUSES as _TERMINAL_STATUSES,
    _ACTIVE_RUN_STATUSES as _ACTIVE_RUN_STATUSES,
    _ACTIVE_RUN_STATUS_SQL as _ACTIVE_RUN_STATUS_SQL,
    _TERMINAL_STATUS_SQL as _TERMINAL_STATUS_SQL,
    _REGISTRATION_CHECKPOINTS as _REGISTRATION_CHECKPOINTS,
    _LEGACY_REGISTRATION_CHECKPOINT_MAP as _LEGACY_REGISTRATION_CHECKPOINT_MAP,
    _SECRET_PARTS as _SECRET_PARTS,
    _JWT_RE as _JWT_RE,
    _PROXY_RE as _PROXY_RE,
)
from core.storage import postgres as postgres_store, records as record_store
