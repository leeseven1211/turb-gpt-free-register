# -*- coding: utf-8 -*-
"""固定账号选择：一个数据库语句快照，不逐账号建执行。"""

from __future__ import annotations

from core.storage import records
from core.storage.operations import bulk_schema
from core.storage.operations.bulk_common import (
    BulkError,
    connect,
    table,
    dumps,
    digest,
    guard,
    request_guard,
    receipt,
    validate_key,
    positive_ids,
    require_row,
    public_selection,
)


_KIND = {
    "query": "account_query",
    "ids": "explicit_ids",
    "account_query": "account_query",
    "explicit_ids": "explicit_ids",
    "batch_targets": "batch_targets",
}


def create_selection(
    *,
    request_key: str,
    source: dict,
    operation_key: str,
    config_revision: str,
    operation_version: int = 1,
    parameters: dict | None = None,
    config_snapshot: dict | None = None,
    query_spec: dict | None = None,
    ttl_seconds: int = 1800,
) -> dict:
    bulk_schema.init()
    validate_key(request_key)
    kind = _KIND.get(source.get("kind"))
    if not kind:
        raise BulkError("invalid_selection_source", "不支持的账号选择来源", 422)
    source = dict(source)
    if kind == "explicit_ids":
        source["ids"] = positive_ids(source.get("ids", source.get("account_ids", [])))
    parameters = parameters or {}
    payload = dict(
        source=source,
        operation_key=operation_key,
        operation_version=operation_version,
        parameters=parameters,
        config_revision=str(config_revision),
        query_spec=query_spec or {},
    )
    hashed = digest(payload)
    with connect() as conn, conn.cursor() as cur:
        request_guard(cur, "selection", request_key)
        cur.execute(f"SELECT * FROM {table('operation_selections')} WHERE request_key=%s", (request_key,))
        previous = receipt(cur.fetchone(), hashed)
        if previous:
            return public_selection(previous)
        cur.execute(
            f"""INSERT INTO {table("operation_selections")}
            (selection_kind,request_key,request_hash,query_version,query_spec,action_key,action_version,
             parameters,parameters_hash,config_revision,config_snapshot,status,expires_at,basis_batch_id)
            VALUES (%s,%s,%s,1,%s::jsonb,%s,%s,%s::jsonb,%s,%s,%s::jsonb,'preparing',
                    now()+(%s * interval '1 second'),%s) RETURNING *""",
            (
                kind,
                request_key,
                hashed,
                dumps({"source": source, "query": query_spec or source.get("query", {})}),
                operation_key,
                operation_version,
                dumps(parameters),
                digest(parameters),
                str(config_revision),
                dumps(config_snapshot or {}),
                max(60, int(ttl_seconds)),
                source.get("batch_id") if kind == "batch_targets" else None,
            ),
        )
        return public_selection(dict(cur.fetchone(), reused=False))


def _account_select(*, plan_baseline: bool = False) -> str:
    columns = """a.email,a.created_at,a.account_promotion_value,a.plan_type,a.current_plan_type,
      a.deactivated,a.archived,a.account_has_password,a.account_totp_enabled,a.account_has_access_token,
      a.codex_credential_state"""
    if not plan_baseline:
        return columns + ",NULL::jsonb AS plan_comparison"
    # 与名单在同一语句快照读取，仅保留比较所需证据，不复制会话或完整响应。
    return columns + """,jsonb_build_object(
      'product','plus','status',a.plan_check_status,'ok',a.plan_check_ok,
      'countries',a.data->'plan_check_countries','partial',a.data->'plan_check_partial',
      'checked_at',COALESCE(NULLIF(a.plan_last_success_at,''),a.data->>'plan_checked_at'),
      'frozen_at',statement_timestamp(),'plus_offer_kind',a.plus_promo_kind,
      'stale',a.data->'plan_check_stale',
      'country_results',(SELECT jsonb_agg(jsonb_build_object(
        'country',item->'country','status',item->'status','checked_at',item->'checked_at',
        'ok',item->'result'->'ok','stale',item->'stale'))
        FROM jsonb_array_elements(CASE WHEN jsonb_typeof(a.data->'plan_check_country_results')='array'
          THEN a.data->'plan_check_country_results' ELSE '[]'::jsonb END) item),
      'promotions',(SELECT jsonb_agg(jsonb_build_object(
        'plan',item->'plan','kind',item->'kind','stale',item->'stale',
        'expired',item->'expired','expires_at',item->'expires_at'))
        FROM jsonb_array_elements(CASE WHEN jsonb_typeof(a.data->'account_promotions')='array'
          THEN a.data->'account_promotions' ELSE '[]'::jsonb END) item)
      ) AS plan_comparison"""


def freeze_selection(
    selection_id: int,
    *,
    where_sql: str = "TRUE",
    params=(),
    owner_id: str | None = None,
    fence: int | None = None,
    preflight=None,
) -> dict:
    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        # 来源批的投影锁必须早于selection锁；普通选择不争批次控制锁。
        row = require_row(cur, f"SELECT * FROM {table('operation_selections')} WHERE id=%s", (selection_id,))
        if row["selection_kind"] == "retry_members":
            raise BulkError("retry_selection_owned_by_round", "重跑选择须由所属轮次固定")
        if row["basis_batch_id"]:
            guard(cur, row["basis_batch_id"])
            basis = require_row(
                cur,
                f"SELECT * FROM {table('operation_batch_controls')} WHERE batch_id=%s FOR UPDATE",
                (row["basis_batch_id"],),
            )
        else:
            basis = None
        row = require_row(cur, f"SELECT * FROM {table('operation_selections')} WHERE id=%s FOR UPDATE", (selection_id,))
        if row["status"] in ("ready", "consumed"):
            return public_selection(row)
        if row["status"] != "preparing":
            raise BulkError("selection_not_preparing", "选择请求已结束")
        if owner_id is not None and (row["owner_id"] != owner_id or row["fence"] != fence):
            raise BulkError("lease_lost", "选择准备租约已失效")
        source = row["query_spec"]["source"]
        account_table = records._qualified(records.ACCOUNTS)
        account_select = _account_select(plan_baseline=row["action_key"] == "plan_check")
        args: list = []
        limit = source.get("limit", source.get("query", {}).get("limit"))
        if limit is not None and (isinstance(limit, bool) or int(limit) <= 0):
            raise BulkError("invalid_selection_limit", "选择数量必须大于零", 422)
        if row["selection_kind"] == "explicit_ids":
            query = f"""SELECT requested.id,requested.ordinal,{account_select}
                FROM unnest(%s::bigint[]) WITH ORDINALITY requested(id,ordinal)
                LEFT JOIN {account_table} a ON a.id=requested.id"""
            args = [source["ids"]]
        elif row["selection_kind"] == "batch_targets":
            scope = dict(source.get("selection", {"kind": "all"}))
            if source.get("view") == "round":
                scope["round_id"] = source.get("round_id")
            validate_member_scope(cur, scope, basis)
            subset, subset_args = _source_target_filter(scope, basis)
            query = f"""SELECT root.target_id AS id,row_number() OVER(ORDER BY root.ordinal) AS ordinal,{account_select}
                FROM {table("operation_selection_targets")} root
                LEFT JOIN {account_table} a ON a.id=root.target_id
                WHERE root.selection_id=%s AND ({subset}) ORDER BY root.ordinal"""
            args = [basis["selection_id"], *subset_args]
        else:
            # 仅接收服务端AccountQuerySpec编译器生成的谓词，禁止客户端SQL拼接。
            if ";" in where_sql or "--" in where_sql or "/*" in where_sql:
                raise BulkError("invalid_query_predicate", "账号查询谓词不合法", 422)
            query = f"""SELECT a.id,row_number() OVER(ORDER BY a.id DESC) AS ordinal,{account_select}
                FROM {account_table} a WHERE ({where_sql}) ORDER BY a.id DESC LIMIT %s"""
            args = [*params, min(int(limit), 100001) if limit is not None else 100001]
        cur.execute(
            f"""WITH candidates AS MATERIALIZED ({query}), inserted AS (
          INSERT INTO {table("operation_selection_targets")}
            (selection_id,target_kind,target_id,ordinal,display_snapshot,match_evidence,baseline)
          SELECT %s,'account',id,ordinal,
            jsonb_build_object('email',COALESCE(email,''),'created_at',created_at),
            jsonb_build_object('created_at',created_at,'promotion',account_promotion_value,
              'reason_code',CASE WHEN email IS NULL THEN 'account_missing' WHEN deactivated THEN 'account_deactivated' ELSE NULL END),
            jsonb_build_object('plan_type',plan_type,'current_plan_type',current_plan_type,
              'promotion',account_promotion_value,'has_password',account_has_password,'totp_enabled',account_totp_enabled,
              'has_access_token',account_has_access_token,'codex_credential_state',codex_credential_state,
              'plan_check',plan_comparison)
          FROM candidates RETURNING id)
          UPDATE {table("operation_selections")} SET total_count=(SELECT count(*) FROM inserted),
            selected_at=statement_timestamp(),selection_revision=1,status='preparing',owner_id=NULL,lease_until=NULL,
            basis_summary_revision=%s,updated_at=now() WHERE id=%s RETURNING *""",
            (*args, selection_id, basis["summary_revision"] if basis else None, selection_id),
        )
        frozen = dict(cur.fetchone())
        if int(frozen["total_count"]) > 100000:
            raise BulkError("selection_capacity_exceeded", "匹配范围超过100,000个账号，请设置数量上限或缩小条件", 422)
        # 预检可追加固定目标的有限证据，必须纯数据库操作，不能发远端请求。
        if preflight is not None:
            summary = {"ready": 0, "waiting_account": 0, "not_executable": 0}
            cursor = 0
            while True:
                cur.execute(
                    f"""SELECT id,target_id,target_id AS account_id,ordinal,display_snapshot,baseline,match_evidence
                  FROM {table("operation_selection_targets")} WHERE selection_id=%s AND ordinal>%s
                  ORDER BY ordinal LIMIT 5000""",
                    (selection_id, cursor),
                )
                targets = [dict(value) for value in cur.fetchall()]
                if not targets:
                    break
                checks = list(preflight(targets, conn))
                identities = {int(value["id"]) for value in targets}
                if len(checks) != len(targets) or {int(value["target_id"]) for value in checks} != identities:
                    raise BulkError("invalid_preflight_receipts", "预检未返回完整目标回执", 500)
                for check in checks:
                    status = check.get("status", "not_executable")
                    summary[status] = summary.get(status, 0) + 1
                cur.execute(
                    f"""UPDATE {table("operation_selection_targets")} target
                  SET match_evidence=match_evidence || jsonb_build_object('preflight',data.value)
                  FROM jsonb_array_elements(%s::jsonb) data(value)
                  WHERE target.id=(data.value->>'target_id')::bigint AND target.selection_id=%s""",
                    (dumps(checks), selection_id),
                )
                cursor = targets[-1]["ordinal"]
            cur.execute(
                f"UPDATE {table('operation_selections')} SET preflight_summary=%s::jsonb,preflight_at=now() WHERE id=%s RETURNING *",
                (dumps(summary), selection_id),
            )
            frozen = dict(cur.fetchone())
        cur.execute(
            f"UPDATE {table('operation_selections')} SET status='ready' WHERE id=%s RETURNING *", (selection_id,)
        )
        frozen = dict(cur.fetchone())
        return public_selection(frozen)


def _source_target_filter(selection: dict, basis: dict, alias: str = "root") -> tuple[str, list]:
    kind = selection.get("kind", "all")
    round_id = selection.get("round_id")
    round_scope = (
        f"""EXISTS(SELECT 1 FROM {table("operation_batch_rounds")} source_round
          JOIN {table("operation_selection_targets")} source_member ON source_member.selection_id=source_round.member_selection_id
          WHERE source_round.id=%s AND source_round.batch_id=%s
            AND COALESCE(source_member.canonical_target_id,source_member.id)={alias}.id)"""
        if round_id
        else "TRUE"
    )
    scope_args = [int(round_id), basis["batch_id"]] if round_id else []
    if kind in ("all", "all_targets"):
        return round_scope, scope_args
    if kind in ("targets", "ids"):
        return f"({alias}.id=ANY(%s::bigint[]) AND ({round_scope}))", [
            positive_ids(selection.get("target_ids", selection.get("ids", []))),
            *scope_args,
        ]
    if kind == "result_filter":
        outcomes = selection.get("states", selection.get("outcomes", selection.get("outcome", [])))
        if isinstance(outcomes, str):
            outcomes = [outcomes]
        if not outcomes:
            raise BulkError("invalid_result_filter", "必须选择结果分类", 422)
        result_conditions, result_args = result_predicate(selection, "tr")
        if round_id:
            return (
                f"""EXISTS(SELECT 1 FROM {table("operation_batch_rounds")} source_round
                  JOIN {table("operation_selection_targets")} source_member
                    ON source_member.selection_id=source_round.member_selection_id
                  LEFT JOIN {table("operation_batch_target_rounds")} tr
                    ON tr.round_id=source_round.id
                    AND tr.canonical_target_id=COALESCE(source_member.canonical_target_id,source_member.id)
                  WHERE source_round.id=%s AND source_round.batch_id=%s
                    AND COALESCE(source_member.canonical_target_id,source_member.id)={alias}.id
                    AND COALESCE(tr.outcome,source_round.unmaterialized_bucket)=ANY(%s)
                    AND ({result_conditions}))""",
                [int(round_id), basis["batch_id"], outcomes, *result_args],
            )
        if result_args:
            return (
                f"""EXISTS(SELECT 1 FROM {table("operation_batch_target_rounds")} tr
              WHERE tr.canonical_target_id={alias}.id AND tr.round_id=COALESCE({alias}.latest_requested_round_id,%s)
              AND tr.outcome=ANY(%s) AND ({result_conditions}))""",
                [basis["initial_round_id"], outcomes, *result_args],
            )
        return (
            f"EXISTS(SELECT 1 FROM jsonb_each_text({alias}.current_contribution) e WHERE e.key=ANY(%s) AND e.value::bigint>0)",
            [outcomes],
        )
    raise BulkError("invalid_result_filter", "不支持的批次成员筛选", 422)


def get_selection(selection_id: int, *, limit: int = 50, after_ordinal: int = 0) -> dict:
    bulk_schema.require_readable()
    with connect() as conn, conn.cursor() as cur:
        row = require_row(cur, f"SELECT * FROM {table('operation_selections')} WHERE id=%s", (selection_id,))
        page_size = max(1, min(100, int(limit)))
        cur.execute(
            f"""SELECT id,target_kind,target_id,ordinal,display_snapshot,match_evidence,baseline
          FROM {table("operation_selection_targets")} WHERE selection_id=%s AND ordinal>%s
          ORDER BY ordinal LIMIT %s""",
            (selection_id, after_ordinal, page_size + 1),
        )
        items = [dict(x) for x in cur.fetchall()]
        result = public_selection(row)
        result.update(
            targets=items[:page_size],
            items=items[:page_size],
            sample=items[:page_size],
            page={
                "has_more": len(items) > page_size,
                "next_cursor": items[page_size - 1]["ordinal"] if len(items) > page_size else None,
            },
        )
        return result


def find_selection_request(request_key: str) -> dict | None:
    """服务层先恢复已受理意图，重发不依赖此刻生效配置。"""
    bulk_schema.require_readable()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {table('operation_selections')} WHERE request_key=%s", (request_key,))
        row = cur.fetchone()
        return public_selection(dict(row)) if row else None


def fail_selection(
    selection_id: int, *, error_code: str, owner_id: str | None = None, fence: int | None = None
) -> bool:
    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {table("operation_selections")} SET status='failed',error_code=%s,
          owner_id=NULL,lease_until=NULL,updated_at=now() WHERE id=%s AND status='preparing'
          AND (%s::text IS NULL OR (owner_id=%s AND fence=%s))""",
            (error_code, selection_id, owner_id, owner_id, fence),
        )
        return bool(cur.rowcount)


_RESULT_FILTERS = {
    "query_outcome",
    "account_plan_type",
    "plus_offer_kind",
    "confirmed_no_offer",
    "comparison",
    "confirmation",
    "material_state",
    "attempt_outcome",
    "credential_confirmation",
    "goal_satisfied",
}


def result_predicate(spec: dict, alias: str = "tr") -> tuple[str, list]:
    clauses = []
    args = []
    reasons = spec.get("reason_codes")
    if reasons:
        if (
            not isinstance(reasons, (list, tuple))
            or len(reasons) > 30
            or any(not isinstance(value, str) or not value or len(value) > 120 for value in reasons)
        ):
            raise BulkError("invalid_result_filter", "错误分类必须是最多30项的字符串数组", 422)
        clauses.append(f"{alias}.reason_code=ANY(%s)")
        args.append(list(reasons))
    filters = spec.get("result_filters") or {}
    if not isinstance(filters, dict) or set(filters) - _RESULT_FILTERS:
        raise BulkError("invalid_result_filter", "包含不支持的结果字段", 422)
    for key, raw in filters.items():
        values = raw if isinstance(raw, list) else [raw]
        if not values or len(values) > 30:
            raise BulkError("invalid_result_filter", "结果条件数量无效", 422)
        if any(not isinstance(value, (str, int, float, bool)) or len(str(value)) > 200 for value in values):
            raise BulkError("invalid_result_filter", "结果条件必须为有限长度的标量值", 422)
        clauses.append(f"{alias}.result->'result'->>%s=ANY(%s)")
        args.extend([key, [str(x).lower() if isinstance(x, bool) else str(x) for x in values]])
    return " AND ".join(clauses) if clauses else "TRUE", args


def validate_member_scope(cur, selection: dict, basis: dict) -> None:
    source_round = None
    if selection.get("round_id"):
        source_round = require_row(
            cur,
            f"SELECT id,member_selection_id,target_count FROM {table('operation_batch_rounds')} WHERE id=%s AND batch_id=%s",
            (int(selection["round_id"]), basis["batch_id"]),
        )
        if source_round["target_count"] is None:
            raise BulkError("source_round_not_ready", "来源轮次尚未固定账号范围，不能复制或重跑", 409)
    if selection.get("kind") in ("targets", "ids"):
        ids = positive_ids(selection.get("target_ids", selection.get("ids", [])))
        cur.execute(
            f"SELECT count(*) AS total FROM {table('operation_selection_targets')} WHERE selection_id=%s AND id=ANY(%s)",
            (basis["selection_id"], ids),
        )
        if int(cur.fetchone()["total"]) != len(ids):
            raise BulkError("target_outside_batch", "显式目标不属于来源批次", 422)
        if source_round:
            cur.execute(
                f"""SELECT count(*) AS total FROM {table("operation_selection_targets")} member
              WHERE member.selection_id=%s AND COALESCE(member.canonical_target_id,member.id)=ANY(%s)""",
                (source_round["member_selection_id"], ids),
            )
            if int(cur.fetchone()["total"]) != len(ids):
                raise BulkError("target_outside_round", "显式目标不属于指定来源轮次", 422)
