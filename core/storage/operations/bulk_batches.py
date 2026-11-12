# -*- coding: utf-8 -*-
"""批次、重跑轮次和固定目标分页。"""

from __future__ import annotations

import uuid
from core.operations.presentation import public_result_status
from core.storage.operations import bulk_schema
from core.storage.operations.bulk_common import (
    BulkError,
    counts,
    add_counts,
    connect,
    table,
    dumps,
    digest,
    guard,
    request_guard,
    receipt,
    validate_key,
    require_row,
    public_batch,
    public_round,
    public_target_result,
    target_status_sql,
    public_reason_target_ids,
    preserve_partial_counts,
)
from core.storage.operations.bulk_selections import _source_target_filter, result_predicate, validate_member_scope


def create_batch(
    *,
    request_key: str,
    selection_id: int,
    selection_revision: int,
    operation_key: str,
    parameters: dict,
    config_revision: str,
    name: str = "",
    max_concurrency: int = 1,
    start_paused: bool = False,
) -> dict:
    bulk_schema.init()
    validate_key(request_key)
    if not 1 <= int(max_concurrency) <= 128:
        raise BulkError("invalid_concurrency", "批次并发必须在1到128之间", 422)
    if not isinstance(start_paused, bool):
        raise BulkError("parameter_invalid", "创建后暂停必须为布尔值", 422)
    payload = dict(
        selection_id=int(selection_id),
        selection_revision=selection_revision,
        operation_key=operation_key,
        parameters=parameters,
        config_revision=str(config_revision),
        name=name,
        max_concurrency=int(max_concurrency),
    )
    # 默认执行沿用原请求摘要，升级前已经受理的请求仍能找回。
    if start_paused:
        payload["start_paused"] = True
    hashed = digest(payload)
    with connect() as conn, conn.cursor() as cur:
        request_guard(cur, "batch", request_key)
        cur.execute(f"SELECT * FROM {table('operation_batch_controls')} WHERE request_key=%s", (request_key,))
        previous = receipt(cur.fetchone(), hashed)
        if previous:
            return public_batch(previous)
        selection = require_row(
            cur,
            f"SELECT *,expires_at<=now() AS expired FROM {table('operation_selections')} WHERE id=%s FOR UPDATE",
            (selection_id,),
        )
        if selection["status"] == "consumed":
            raise BulkError(
                "selection_consumed", "该名单已创建批次", detail={"existing_batch_id": selection["consumed_by_batch_id"]}
            )
        if selection["status"] == "expired" or selection["expired"]:
            raise BulkError("selection_expired", "账号范围快照已过期，请重新预览。", 410)
        if selection["status"] != "ready":
            raise BulkError("selection_not_ready", "选择名单未准备完成。")
        if selection["selection_revision"] != int(selection_revision):
            raise BulkError("selection_revision_changed", "选择名单版本不一致")
        if selection["action_key"] != operation_key or selection["parameters_hash"] != digest(parameters):
            raise BulkError("selection_parameters_changed", "功能或参数已改变，请重新预览")
        if selection["config_revision"] != str(config_revision):
            raise BulkError("config_revision_changed", "配置已改变，请重新预览")
        from core.bulk_operations.catalog import capture_settings

        latest = capture_settings(operation_key, parameters)
        if str(latest["config_revision"]) != str(config_revision):
            raise BulkError(
                "config_revision_changed",
                "配置已改变，请重新预览",
                detail={"effective_settings": latest["effective_settings"]},
            )
        availability = latest.get("availability") or {}
        if availability.get("available") is False:
            raise BulkError(
                "operation_unavailable",
                availability.get("reason") or "当前部署无法执行该功能",
                503,
                {"reason_code": availability.get("reason_code")},
            )
        total = int(selection["total_count"])
        if not total:
            raise BulkError("selection_empty", "没有符合条件的账号", 422)
        title = str(name).strip()[:120] or f"{operation_key} 批量任务"
        cur.execute(
            f"""INSERT INTO {table("operation_batches")}
          (batch_uuid,source_system,source_id,batch_type,title,requested_count,created_by,data)
          VALUES (%s,'bulk_manager',%s,%s,%s,%s,'bulk_manager',%s::jsonb) RETURNING id""",
            (uuid.uuid4().hex, request_key, operation_key, title, total, dumps({"manager_version": 1})),
        )
        batch_id = cur.fetchone()["id"]
        cur.execute(
            f"""INSERT INTO {table("operation_batch_controls")}
          (batch_id,manager_version,selection_id,action_key,action_version,result_version,parameters,
           config_snapshot,config_revision,request_key,request_hash,state,desired_workers,counts,is_paused)
          VALUES (%s,1,%s,%s,%s,1,%s::jsonb,%s::jsonb,%s,%s,%s,'active',%s,%s::jsonb,%s)""",
            (
                batch_id,
                selection_id,
                operation_key,
                selection["action_version"],
                dumps(parameters),
                dumps(selection["config_snapshot"]),
                config_revision,
                request_key,
                hashed,
                max_concurrency,
                dumps(counts(total=total)),
                start_paused,
            ),
        )
        cur.execute(
            f"""INSERT INTO {table("operation_batch_rounds")}
          (batch_id,round_no,request_kind,request_key,request_hash,state,member_selection_id,target_count,counts,frozen_at)
          VALUES (%s,1,'initial',%s,%s,'active',%s,%s,%s::jsonb,now()) RETURNING id""",
            (batch_id, request_key, hashed, selection_id, total, dumps(counts(total=total))),
        )
        round_id = cur.fetchone()["id"]
        cur.execute(
            f"UPDATE {table('operation_batch_controls')} SET initial_round_id=%s WHERE batch_id=%s RETURNING *",
            (round_id, batch_id),
        )
        result = public_batch(dict(cur.fetchone()))
        cur.execute(
            f"""UPDATE {table("operation_selections")} SET status='consumed',consumed_by_batch_id=%s,
          updated_at=now() WHERE id=%s""",
            (batch_id, selection_id),
        )
        return dict(result, round_id=round_id, round_no=1, reused=False, expansion_state="pending")


def get_batch(batch_id: int) -> dict:
    bulk_schema.require_readable()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        row = require_row(
            cur,
            f"""SELECT c.*,b.title AS name,b.created_at,s.query_spec,s.selected_at FROM {table("operation_batch_controls")} c
          JOIN {table("operation_batches")} b ON b.id=c.batch_id
          JOIN {table("operation_selections")} s ON s.id=c.selection_id WHERE c.batch_id=%s""",
            (batch_id,),
        )
        cur.execute(
            f"SELECT * FROM {table('operation_batch_rounds')} WHERE batch_id=%s ORDER BY round_no DESC LIMIT 21",
            (batch_id,),
        )
        rounds = [dict(x) for x in cur.fetchall()]
        result = public_batch(preserve_partial_counts(cur, row))
        result["rounds"] = [public_round(preserve_partial_counts(cur, value, round_id=value["id"])) for value in rounds[:20]]
        result["rounds_has_more"] = len(rounds) > 20
        result["rounds_next_after_no"] = rounds[19]["round_no"] if len(rounds) > 20 else None
        cur.execute(
            f"""SELECT EXTRACT(EPOCH FROM now()-event.created_at) AS lag_seconds,event.error_code,event.attempts,event.available_at
          FROM {table("operation_projection_outbox")} event
          JOIN {table("operation_batch_target_rounds")} target ON target.id=event.target_round_id
          WHERE target.batch_id=%s AND event.consumer_kind='bulk_target' AND event.processed_at IS NULL
          ORDER BY event.id LIMIT 1""",
            (batch_id,),
        )
        pending = cur.fetchone()
        lag = max(0, float(pending["lag_seconds"])) if pending else 0
        result["projection"] = {
            "state": "failed"
            if pending and pending["error_code"]
            else "delayed"
            if lag > 2
            else "syncing"
            if pending
            else "current",
            "lag_seconds": lag,
            "pending": bool(pending),
            "error_code": pending["error_code"] if pending else None,
            "attempts": pending["attempts"] if pending else 0,
            "next_retry_at": pending["available_at"] if pending else None,
        }
        result["selection_id"] = row["selection_id"]
        saved = row.get("query_spec") or {}
        source = saved.get("source", {})
        public_source = {key: source[key] for key in ("kind", "batch_id", "view", "round_id") if key in source}
        result["selection_summary"] = {
            "source": public_source,
            "query": saved.get("query") if saved.get("source", {}).get("kind") in ("query", "account_query") else None,
            "selected_at": row.get("selected_at"),
            "target_count": result["target_count"],
        }
        return result


def list_batches(*, limit: int = 20, after_id: int | None = None, operation_key=None, **filters) -> dict:
    bulk_schema.require_readable()
    clauses = ["c.purge_started_at IS NULL"]
    params: list = []
    if operation_key:
        clauses.append("c.action_key=ANY(%s)")
        params.append([operation_key] if isinstance(operation_key, str) else list(operation_key))
    if filters.get("control_state"):
        values = filters["control_state"]
        values = [values] if isinstance(values, str) else values
        state_clauses = []
        for value in values:
            if value == "paused":
                state_clauses.append("(c.state='active' AND c.is_paused)")
            elif value == "active":
                state_clauses.append("(c.state='active' AND NOT c.is_paused)")
            else:
                state_clauses.append("c.state=%s")
                params.append(value)
        clauses.append("(" + " OR ".join(state_clauses) + ")")
    for key, op in (("created_from", ">="), ("created_to", "<=")):
        if filters.get(key):
            clauses.append(f"c.created_at {op} %s")
            params.append(filters[key])
    if filters.get("q"):
        clauses.append("(b.title ILIKE %s OR c.batch_id::text=%s)")
        params.extend(["%" + str(filters["q"])[:120] + "%", str(filters["q"])[:120]])
    page_clauses = list(clauses)
    page_params = list(params)
    if after_id:
        page_clauses.append("c.batch_id<%s")
        page_params.append(int(after_id))
    page_size = max(1, min(100, int(limit)))
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT c.*,b.title AS name FROM {table("operation_batch_controls")} c
          JOIN {table("operation_batches")} b ON b.id=c.batch_id WHERE {" AND ".join(page_clauses)}
          ORDER BY c.batch_id DESC LIMIT %s""",
            (*page_params, page_size + 1),
        )
        raw_rows = [dict(x) for x in cur.fetchall()]
        rows = [public_batch(preserve_partial_counts(cur, row)) for row in raw_rows]
        summary = {}
        try:
            cur.execute(
                f"""SELECT count(*) AS total_batches,
              count(*) FILTER (WHERE c.state IN ('active','settling','cancel_requested','stop_requested') AND NOT c.is_paused) AS active_batches,
              count(*) FILTER (WHERE c.state='active' AND c.is_paused) AS paused_batches,
              count(*) FILTER (WHERE c.state='ended') AS ended_batches,
              coalesce(sum(coalesce(nullif(c.counts->>'failed','')::bigint,0)),0) AS failed_targets,
              coalesce(sum(coalesce(nullif(c.counts->>'attention_required','')::bigint,0)),0) AS attention_targets
            FROM {table("operation_batch_controls")} c
          JOIN {table("operation_batches")} b ON b.id=c.batch_id WHERE {" AND ".join(clauses)}""",
                tuple(params),
            )
            row = cur.fetchone() or {}
            summary = {key: int(row.get(key) or 0) for key in (
                "total_batches", "active_batches", "paused_batches", "ended_batches", "failed_targets", "attention_targets")}
            summary["failed_targets"] += summary.pop("attention_targets", 0)
            cur.execute(f"""SELECT c.* FROM {table('operation_batch_controls')} c
              JOIN {table('operation_batches')} b ON b.id=c.batch_id
              WHERE {" AND ".join(clauses)} AND coalesce((c.counts->>'attention_required')::bigint,0)>0""", tuple(params))
            historical = [dict(value) for value in cur.fetchall()]
            for value in historical:
                corrected = preserve_partial_counts(cur, value)
                summary["failed_targets"] -= int(value["counts"].get("attention_required", 0)) - int(corrected["counts"].get("attention_required", 0))
        except Exception:
            summary = {}
        return {
            "items": rows[:page_size],
            "summary": summary,
            "page": {
                "has_more": len(rows) > page_size,
                "next_cursor": rows[page_size - 1]["id"] if len(rows) > page_size else None,
            },
        }


def list_active_batches(*, limit: int = 20) -> list[dict]:
    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT c.* FROM {table("operation_batch_controls")} c WHERE c.purge_started_at IS NULL
          AND NOT c.is_paused
          AND EXISTS(SELECT 1 FROM {table("operation_batch_rounds")} r WHERE r.batch_id=c.batch_id AND r.state IN ('active','settling'))
          ORDER BY c.last_expand_at,c.batch_id LIMIT %s""",
            (max(1, min(512, limit)),),
        )
        return [dict(x) for x in cur.fetchall()]


def create_round(
    batch_id: int, *, request_key: str, source: dict, selection: dict, observed_summary_revision: int | None = None
) -> dict:
    bulk_schema.init()
    validate_key(request_key)
    hashed = digest({"source": source, "selection": selection, "observed_summary_revision": observed_summary_revision})
    with connect() as conn, conn.cursor() as cur:
        request_guard(cur, f"round:{batch_id}", request_key)
        cur.execute(
            f"SELECT * FROM {table('operation_batch_rounds')} WHERE batch_id=%s AND request_key=%s",
            (batch_id, request_key),
        )
        previous = receipt(cur.fetchone(), hashed)
        if previous:
            return previous
        controls = require_row(
            cur, f"SELECT * FROM {table('operation_batch_controls')} WHERE batch_id=%s FOR UPDATE", (batch_id,)
        )
        if source.get("view") == "round":
            require_row(
                cur,
                f"SELECT id FROM {table('operation_batch_rounds')} WHERE id=%s AND batch_id=%s",
                (source.get("round_id"), batch_id),
            )
        if controls["purge_started_at"]:
            raise BulkError("batch_history_expired", "该批次历史已进入清理，不能重跑")
        query = {"source": source, "selection": selection}
        cur.execute(
            f"""INSERT INTO {table("operation_selections")}
          (selection_kind,request_key,request_hash,query_version,query_spec,action_key,action_version,parameters,
           parameters_hash,config_revision,config_snapshot,status,expires_at,basis_batch_id,observed_summary_revision)
          VALUES ('retry_members',%s,%s,1,%s::jsonb,%s,%s,%s::jsonb,%s,%s,%s::jsonb,'preparing',
                  now()+interval '7 days',%s,%s) RETURNING id""",
            (
                f"round:{batch_id}:{request_key}",
                hashed,
                dumps(query),
                controls["action_key"],
                controls["action_version"],
                dumps(controls["parameters"]),
                digest(controls["parameters"]),
                controls["config_revision"],
                dumps(controls["config_snapshot"]),
                batch_id,
                observed_summary_revision
                if observed_summary_revision is not None
                else source.get("observed_summary_revision"),
            ),
        )
        selection_id = cur.fetchone()["id"]
        cur.execute(
            f"""INSERT INTO {table("operation_batch_rounds")}
          (batch_id,round_no,request_kind,request_key,request_hash,state,member_selection_id)
          VALUES (%s,%s,'manual_retry',%s,%s,'preparing',%s) RETURNING *""",
            (batch_id, controls["next_round_no"], request_key, hashed, selection_id),
        )
        result = dict(cur.fetchone(), reused=False)
        cur.execute(
            f"""UPDATE {table("operation_batch_controls")} SET next_round_no=next_round_no+1,
          state='active',control_revision=control_revision+1,updated_at=now() WHERE batch_id=%s""",
            (batch_id,),
        )
        return result


def freeze_round(round_id: int, *, owner_id: str | None = None, fence: int | None = None) -> dict:
    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        identity = require_row(cur, f"SELECT batch_id FROM {table('operation_batch_rounds')} WHERE id=%s", (round_id,))
        batch_id = identity["batch_id"]
        guard(cur, batch_id)
        controls = require_row(
            cur, f"SELECT * FROM {table('operation_batch_controls')} WHERE batch_id=%s FOR UPDATE", (batch_id,)
        )
        row = require_row(cur, f"SELECT * FROM {table('operation_batch_rounds')} WHERE id=%s FOR UPDATE", (round_id,))
        if row["state"] != "preparing":
            return row
        if owner_id is not None and (row["owner_id"] != owner_id or row["fence"] != fence):
            raise BulkError("lease_lost", "轮次准备租约已失效")
        cur.execute(
            f"""SELECT 1 FROM {table("operation_batch_rounds")} WHERE batch_id=%s
          AND round_no<%s AND state='preparing' LIMIT 1""",
            (batch_id, row["round_no"]),
        )
        if cur.fetchone():
            cur.execute(
                f"""UPDATE {table("operation_batch_rounds")} SET owner_id=NULL,lease_until=NULL,
              next_attempt_at=now()+interval '1 second' WHERE id=%s""",
                (round_id,),
            )
            return dict(row, deferred=True)
        if row["control_action"] != "none":
            return _cancel_preparing(cur, row)
        selected = require_row(
            cur, f"SELECT * FROM {table('operation_selections')} WHERE id=%s FOR UPDATE", (row["member_selection_id"],)
        )
        spec = dict(selected["query_spec"]["selection"])
        src = selected["query_spec"].get("source", {})
        if src.get("view") == "round":
            spec["round_id"] = src.get("round_id")
        validate_member_scope(cur, spec, controls)
        predicate, args = _source_target_filter(spec, controls, cur=cur)
        # 原轮查询和当前视图均在同一投影锁下固定；固定成功之前不切换current指针。
        cur.execute(
            f"""WITH members AS MATERIALIZED (
          SELECT root.*,CASE WHEN %s::bigint IS NOT NULL THEN %s::bigint ELSE COALESCE(root.latest_requested_round_id,%s) END AS source_round_id
          FROM {table("operation_selection_targets")} root
          WHERE root.selection_id=%s AND ({predicate}) ORDER BY root.id FOR UPDATE OF root
        ), inserted AS (
          INSERT INTO {table("operation_selection_targets")}
            (selection_id,target_kind,target_id,ordinal,canonical_target_id,source_target_round_id,
             source_run_id_snapshot,display_snapshot,match_evidence,baseline)
          SELECT %s,m.target_kind,m.target_id,row_number() OVER(ORDER BY m.ordinal),m.id,tr.id,
            (SELECT l.run_id_snapshot FROM {table("operation_batch_run_links")} l WHERE l.target_round_id=tr.id
              AND l.relation IN ('owned_root','owned_continuation') ORDER BY l.execution_generation DESC,l.id DESC LIMIT 1),
            m.display_snapshot,m.match_evidence,m.baseline
          FROM members m LEFT JOIN {table("operation_batch_target_rounds")} tr
            ON tr.round_id=m.source_round_id AND tr.canonical_target_id=m.id RETURNING canonical_target_id)
          SELECT count(*) AS total FROM inserted""",
            (
                int(src["round_id"]) if src.get("view") == "round" else None,
                int(src["round_id"]) if src.get("view") == "round" else None,
                controls["initial_round_id"],
                controls["selection_id"],
                *args,
                row["member_selection_id"],
            ),
        )
        total = int(cur.fetchone()["total"])
        cur.execute(
            f"""SELECT e.key,SUM(e.value::bigint)::bigint AS total
          FROM {table("operation_selection_targets")} root
          JOIN {table("operation_selection_targets")} member ON member.canonical_target_id=root.id
          CROSS JOIN LATERAL jsonb_each_text(root.current_contribution) e
          WHERE member.selection_id=%s GROUP BY e.key""",
            (row["member_selection_id"],),
        )
        delta = {x["key"]: -int(x["total"]) for x in cur.fetchall()}
        delta["pending_submit"] = delta.get("pending_submit", 0) + total
        new_counts = add_counts(controls["counts"], delta)
        cur.execute(
            f"""SELECT metric.key,SUM(metric.value::bigint)::bigint AS total
          FROM {table("operation_selection_targets")} member
          JOIN {table("operation_selection_targets")} root ON root.id=member.canonical_target_id
          JOIN {table("operation_batch_target_rounds")} current_target ON current_target.canonical_target_id=root.id
            AND current_target.round_id=COALESCE(root.latest_requested_round_id,%s)
          CROSS JOIN LATERAL jsonb_each_text(COALESCE(current_target.result->'_metrics','{{}}'::jsonb)) metric
          WHERE member.selection_id=%s GROUP BY metric.key""",
            (controls["initial_round_id"], row["member_selection_id"]),
        )
        new_metrics = dict(controls["metrics"])
        for metric in cur.fetchall():
            new_metrics[metric["key"]] = int(new_metrics.get(metric["key"], 0)) - int(metric["total"])
            if new_metrics[metric["key"]] < 0:
                raise BulkError("projection_metrics_invalid", "重跑维度统计出现负数", 500)

        cur.execute(
            f"""UPDATE {table("operation_selection_targets")} root SET latest_requested_round_id=%s,
          current_contribution='{{"pending_submit":1}}'::jsonb,current_projection_revision=root.current_projection_revision+1
          FROM {table("operation_selection_targets")} member WHERE member.canonical_target_id=root.id AND member.selection_id=%s""",
            (round_id, row["member_selection_id"]),
        )
        observed = selected["observed_summary_revision"]
        cur.execute(
            f"""UPDATE {table("operation_selections")} SET status='consumed',selection_revision=1,total_count=%s,
          selected_at=now(),consumed_by_round_id=%s,basis_summary_revision=%s,counts_changed_since_request=%s,
          owner_id=NULL,lease_until=NULL WHERE id=%s""",
            (
                total,
                round_id,
                controls["summary_revision"],
                observed is not None and observed != controls["summary_revision"],
                row["member_selection_id"],
            ),
        )
        cur.execute(
            f"""UPDATE {table("operation_batch_rounds")} SET state=%s,target_count=%s,counts=%s::jsonb,
          frozen_at=now(),owner_id=NULL,lease_until=NULL,completion_reason=%s,
          completed_at=CASE WHEN %s=0 THEN now() ELSE NULL END WHERE id=%s RETURNING *""",
            (
                "active" if total else "completed",
                total,
                dumps(counts(total=total)),
                "empty" if not total else None,
                total,
                round_id,
            ),
        )
        result = dict(cur.fetchone())
        cur.execute(
            f"""UPDATE {table("operation_batch_controls")} SET counts=%s::jsonb,metrics=%s::jsonb,summary_revision=summary_revision+1,
          projected_at=now(),updated_at=now() WHERE batch_id=%s""",
            (dumps(new_counts), dumps(new_metrics), batch_id),
        )
        from core.storage.operations.bulk_projection import _complete_rounds

        _complete_rounds(cur, batch_id)
        return result


def fail_round(round_id: int, *, error_code: str, owner_id: str | None = None, fence: int | None = None) -> bool:
    """准备契约失败持久收口，不能留下永久 preparing；数据库故障由调用方重试。"""
    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        identity = require_row(cur, f"SELECT batch_id FROM {table('operation_batch_rounds')} WHERE id=%s", (round_id,))
        guard(cur, identity["batch_id"])
        require_row(
            cur,
            f"SELECT batch_id FROM {table('operation_batch_controls')} WHERE batch_id=%s FOR UPDATE",
            (identity["batch_id"],),
        )
        row = require_row(cur, f"SELECT * FROM {table('operation_batch_rounds')} WHERE id=%s FOR UPDATE", (round_id,))
        if row["state"] != "preparing":
            return False
        if owner_id is not None and (row["owner_id"] != owner_id or row["fence"] != fence):
            return False
        cur.execute(
            f"""UPDATE {table("operation_selections")} SET status='failed',error_code=%s,
          owner_id=NULL,lease_until=NULL,updated_at=now() WHERE id=%s""",
            (error_code, row["member_selection_id"]),
        )
        cur.execute(
            f"""UPDATE {table("operation_batch_rounds")} SET state='failed',preparation_error_code=%s,
          owner_id=NULL,lease_until=NULL,completed_at=now() WHERE id=%s""",
            (error_code, round_id),
        )
        from core.storage.operations.bulk_projection import _complete_rounds

        _complete_rounds(cur, identity["batch_id"])
        return True


def _cancel_preparing(cur, row: dict) -> dict:
    cur.execute(
        f"""UPDATE {table("operation_selections")} SET status='failed',error_code='selection_cancelled',
      owner_id=NULL,lease_until=NULL WHERE id=%s AND status='preparing' """,
        (row["member_selection_id"],),
    )
    cur.execute(
        f"""UPDATE {table("operation_batch_rounds")} SET state='completed',completion_reason='cancelled_before_freeze',
      completed_at=now(),owner_id=NULL,lease_until=NULL,target_count=NULL WHERE id=%s RETURNING *""",
        (row["id"],),
    )
    return dict(cur.fetchone())


def materialize_targets(batch_id: int, *, limit: int = 100) -> list[dict]:
    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        guard(cur, batch_id)
        controls = require_row(
            cur, f"SELECT * FROM {table('operation_batch_controls')} WHERE batch_id=%s FOR UPDATE", (batch_id,)
        )
        cur.execute(
            f"""SELECT * FROM {table("operation_batch_rounds")} WHERE batch_id=%s AND state IN ('active','settling')
          AND materialized_count<target_count ORDER BY round_no LIMIT 1 FOR UPDATE""",
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            return []
        cancelled = row["unmaterialized_bucket"] == "cancelled"
        cur.execute(
            f"""WITH members AS (
          SELECT * FROM {table("operation_selection_targets")} WHERE selection_id=%s AND ordinal>%s
          ORDER BY ordinal LIMIT %s), inserted AS (
          INSERT INTO {table("operation_batch_target_rounds")}
            (batch_id,round_id,member_target_id,canonical_target_id,ordinal,admission_state,chain_state,
             chain_closed_at,result_version,outcome,applied_contribution,retry_from_target_round_id)
          SELECT %s,%s,id,COALESCE(canonical_target_id,id),ordinal,%s,%s,
            CASE WHEN %s THEN now() ELSE NULL END,%s,%s,%s::jsonb,source_target_round_id FROM members
          ON CONFLICT(round_id,canonical_target_id) DO NOTHING RETURNING *) SELECT * FROM inserted ORDER BY ordinal""",
            (
                row["member_selection_id"],
                row["materialization_cursor"],
                max(1, min(100, limit)),
                batch_id,
                row["id"],
                "cancelled" if cancelled else "pending_submit",
                "closed" if cancelled else "not_started",
                cancelled,
                controls["result_version"],
                "cancelled" if cancelled else "pending_submit",
                dumps({"cancelled" if cancelled else "pending_submit": 1}),
            ),
        )
        result = [dict(x) for x in cur.fetchall()]
        if result:
            cur.execute(
                f"""UPDATE {table("operation_batch_rounds")} SET materialized_count=materialized_count+%s,
              materialization_cursor=%s WHERE id=%s""",
                (len(result), max(x["ordinal"] for x in result), row["id"]),
            )
        return result


def list_targets(
    batch_id: int,
    *,
    round_id: int | None = None,
    limit: int = 50,
    after_ordinal: int = 0,
    outcomes=None,
    q: str = "",
    reason_codes=None,
    result_filters=None,
) -> dict:
    bulk_schema.require_readable()
    size = max(1, min(100, int(limit)))
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        controls = require_row(cur, f"SELECT * FROM {table('operation_batch_controls')} WHERE batch_id=%s", (batch_id,))
        if round_id:
            rnd = require_row(
                cur,
                f"SELECT * FROM {table('operation_batch_rounds')} WHERE id=%s AND batch_id=%s",
                (round_id, batch_id),
            )
            selection_id = rnd["member_selection_id"]
            join_round = "%s"
            join_args = [round_id]
            outcome = f"COALESCE(tr.outcome,'{rnd['unmaterialized_bucket']}')"
        else:
            selection_id = controls["selection_id"]
            join_round = "COALESCE(m.latest_requested_round_id,%s)"
            join_args = [controls["initial_round_id"]]
            outcome = "COALESCE(tr.outcome,(SELECT e.key FROM jsonb_each_text(m.current_contribution) e WHERE e.value::bigint=1 LIMIT 1),'pending_submit')"
        outcome = target_status_sql(outcome)
        clauses = ["m.selection_id=%s", "m.ordinal>%s"]
        args = [*join_args, selection_id, after_ordinal]
        if outcomes:
            clauses.append(f"{outcome}=ANY(%s)")
            args.append([public_result_status(value) for value in ([outcomes] if isinstance(outcomes, str) else outcomes)])
        if q:
            clauses.append("(m.display_snapshot->>'email' ILIKE %s OR m.target_id::text=%s)")
            args.extend(["%" + str(q)[:120] + "%", str(q)[:120]])
        reason_ids = public_reason_target_ids(cur, batch_id, reason_codes) if reason_codes else None
        extra, extra_args = result_predicate({"reason_codes": reason_codes, "result_filters": result_filters},
                                             reason_target_ids=reason_ids)
        clauses.append(extra)
        args.extend(extra_args)
        cur.execute(
            f"""SELECT COALESCE(m.canonical_target_id,m.id) AS id,m.target_id AS account_id,m.target_id,
          m.ordinal,m.display_snapshot,m.baseline,m.match_evidence,tr.id AS target_round_id,tr.round_id,
          {outcome} AS outcome,COALESCE(tr.result,'{{}}'::jsonb) AS result,tr.reason_code,
          tr.chain_state,tr.chain_started_at,tr.chain_closed_at,tr.applied_revision AS result_revision
          FROM {table("operation_selection_targets")} m LEFT JOIN {table("operation_batch_target_rounds")} tr
            ON tr.canonical_target_id=COALESCE(m.canonical_target_id,m.id) AND tr.round_id={join_round}
          WHERE {" AND ".join(clauses)} ORDER BY m.ordinal LIMIT %s""",
            (*args, size + 1),
        )
        rows = [dict(x) for x in cur.fetchall()]
        target_ids = [x["target_round_id"] for x in rows[:size] if x["target_round_id"]]
        if target_ids:
            cur.execute(
                f"""SELECT DISTINCT ON(link.target_round_id) link.target_round_id,link.task_id_snapshot AS task_id,
              link.run_id_snapshot AS run_id,r.result_summary AS source_summary,r.error_message AS source_message,
              r.error_code AS source_error_code
              FROM {table("operation_batch_run_links")} link LEFT JOIN {table("operation_runs")} r ON r.id=link.run_id_snapshot
              WHERE link.target_round_id=ANY(%s) AND link.relation IN ('owned_root','owned_continuation')
              ORDER BY link.target_round_id,link.execution_generation DESC,link.id DESC""",
                (target_ids,),
            )
            links = {x["target_round_id"]: dict(x) for x in cur.fetchall()}
            for item in rows:
                item.update(links.get(item["target_round_id"], {}))
        for item in rows:
            source_summary = item.pop("source_summary", None)
            item["result"] = public_target_result(dict(item["result"], state=item["outcome"]),
                summary=source_summary, message=item.pop("source_message", None),
                error_code=item.pop("source_error_code", None))
            if item["result"].get("reason"):
                item["reason_code"] = item["result"]["reason"]["code"]
        return {
            "items": rows[:size],
            "summary_revision": controls["summary_revision"],
            "page": {
                "has_more": len(rows) > size,
                "next_cursor": rows[size - 1]["ordinal"] if len(rows) > size else None,
            },
        }


def get_round(batch_id: int, round_id: int) -> dict:
    bulk_schema.require_readable()
    with connect() as conn, conn.cursor() as cur:
        row = require_row(
            cur, f"SELECT * FROM {table('operation_batch_rounds')} WHERE id=%s AND batch_id=%s", (round_id, batch_id)
        )
        return public_round(preserve_partial_counts(cur, row, round_id=round_id))


def list_rounds(batch_id: int, *, limit: int = 100, after_round_no: int | None = None) -> dict:
    bulk_schema.require_readable()
    size = max(1, min(100, limit))
    with connect() as conn, conn.cursor() as cur:
        require_row(cur, f"SELECT batch_id FROM {table('operation_batch_controls')} WHERE batch_id=%s", (batch_id,))
        cur.execute(
            f"""SELECT * FROM {table("operation_batch_rounds")} WHERE batch_id=%s
          AND (%s::bigint IS NULL OR round_no<%s) ORDER BY round_no DESC LIMIT %s""",
            (batch_id, after_round_no, after_round_no, size + 1),
        )
        raw_rows = [dict(row) for row in cur.fetchall()]
        rows = [public_round(preserve_partial_counts(cur, row, round_id=row["id"])) for row in raw_rows]
        return {
            "items": rows[:size],
            "page": {
                "has_more": len(rows) > size,
                "next_cursor": rows[size - 1]["round_no"] if len(rows) > size else None,
            },
        }
