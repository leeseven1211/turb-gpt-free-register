# -*- coding: utf-8 -*-
"""批量展开与既有Task/Run执行的事务接缝。"""

from __future__ import annotations

from core.storage import records
from core.storage.operations import bulk_schema, store
from core.storage.operations.bulk_common import (
    BulkError,
    ACTIVE_RUNS,
    OWNED,
    connect,
    table,
    dumps,
    require_row,
)
from core.storage.operations.bulk_batches import materialize_targets


def _enabled() -> bool:
    return bulk_schema._READY_KEY == store.postgres_store.database_url() + "::" + store._schema_name()


def lock_managed_target(conn, run_id: int) -> dict | None:
    """既有入口先定位精确归属，再先锁target；不在这里初始化schema。"""
    if not _enabled():
        return None
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT t.* FROM {table("operation_batch_run_links")} l
          JOIN {table("operation_batch_target_rounds")} t ON t.id=l.target_round_id
          WHERE l.run_id=%s AND l.relation=ANY(%s) FOR UPDATE OF t""",
            (run_id, list(OWNED)),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def ensure_managed_claim(conn, run_id: int) -> dict | None:
    """在准入锁之后使用NOWAIT检查控制；失败由调用者回滚整个准入事务。"""
    if not _enabled():
        return None
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT t.id,t.batch_id FROM {table("operation_batch_run_links")} l
          JOIN {table("operation_batch_target_rounds")} t ON t.id=l.target_round_id
          WHERE l.run_id=%s AND l.relation=ANY(%s)""",
            (run_id, list(OWNED)),
        )
        identity = cur.fetchone()
        if not identity:
            return None
        cur.execute(
            f"SELECT batch_id,is_paused FROM {table('operation_batch_controls')} WHERE batch_id=%s FOR SHARE NOWAIT",
            (identity["batch_id"],),
        )
        controls = cur.fetchone()
        target = require_row(
            cur,
            f"SELECT * FROM {table('operation_batch_target_rounds')} WHERE id=%s FOR UPDATE NOWAIT",
            (identity["id"],),
        )
        cur.execute(f"SELECT control_action FROM {table('operation_batch_rounds')} WHERE id=%s", (target["round_id"],))
        action = cur.fetchone()["control_action"]
        if action == "request_stop" or (action == "cancel_not_started" and target["chain_started_at"] is None):
            raise BulkError("bulk_claim_cancelled", "该轮次已请求取消，不能开始新的执行")
        if controls["is_paused"] and target["chain_started_at"] is None:
            from core.storage.operations.permits import ClaimUnavailable

            raise ClaimUnavailable("batch_paused")
        if target["chain_state"] == "closed":
            raise BulkError("bulk_chain_closed", "该账号链已经结束")
        if _earlier_chain_open(cur, target):
            raise BulkError("earlier_round_pending", "账号仍在执行更早的请求轮次")
        # 只有真正Run认领成功后record_managed_change才写chain_started_at。
        return target


def _earlier_chain_open(cur, target: dict) -> bool:
    cur.execute(
        f"""SELECT 1 FROM {table("operation_batch_rounds")} earlier
      JOIN {table("operation_batch_rounds")} current ON current.id=%s
      JOIN {table("operation_selection_targets")} member ON member.selection_id=earlier.member_selection_id
      LEFT JOIN {table("operation_batch_target_rounds")} tr ON tr.round_id=earlier.id
        AND tr.canonical_target_id=COALESCE(member.canonical_target_id,member.id)
      WHERE earlier.batch_id=current.batch_id AND earlier.round_no<current.round_no
        AND COALESCE(member.canonical_target_id,member.id)=%s
        AND ((tr.id IS NULL AND earlier.unmaterialized_bucket<>'cancelled') OR (tr.id IS NOT NULL AND tr.chain_state<>'closed'))
      LIMIT 1""",
        (target["round_id"], target["canonical_target_id"]),
    )
    return bool(cur.fetchone())


def record_managed_change(conn, target_round_id: int, *, event_kind: str = "fact_changed") -> int:
    """调用方必须已持target锁；与业务事实同事务追加持久投影事件。"""
    with conn.cursor() as cur:
        target = require_row(
            cur, f"SELECT * FROM {table('operation_batch_target_rounds')} WHERE id=%s FOR UPDATE", (target_round_id,)
        )
        cur.execute(
            f"""SELECT r.id,r.status,r.started_at,r.result_summary,l.relation,l.execution_generation
          FROM {table("operation_batch_run_links")} l
          JOIN {table("operation_runs")} r ON r.id=l.run_id WHERE l.target_round_id=%s AND l.relation=ANY(%s)""",
            (target_round_id, list(OWNED)),
        )
        runs = list(cur.fetchall())
        started = target["chain_started_at"] is not None or any(
            x["started_at"] is not None or x["status"] in ("running", "waiting", "cancelling", "settling", "stopping")
            for x in runs
        )
        active = any(x["status"] in ACTIVE_RUNS for x in runs)
        cur.execute(
            f"""SELECT d.status,d.payload->>'parent_run_id' AS parent_run_id FROM {table("operation_task_dependencies")} d
          JOIN {table("operation_tasks")} task ON task.source_system=d.parent_source_system AND (task.source_id=d.parent_source_id OR (d.parent_source_system='webui_runtime' AND task.id::text=d.parent_source_id))
          JOIN {table("operation_batch_run_links")} l ON l.task_id=task.id AND l.target_round_id=%s
          WHERE (d.payload->>'parent_run_id' IS NULL OR d.payload->>'parent_run_id'=l.run_id_snapshot::text)""",
            (target_round_id,),
        )
        dependency_rows = list(cur.fetchall())
        dependencies = any(item["status"] in ("waiting", "ready", "running") for item in dependency_rows)
        roots = [item for item in runs if item["relation"] in ("owned_root", "owned_continuation")]
        latest = max(roots, key=lambda item: item["execution_generation"]) if roots else None
        if latest and (latest.get("result_summary") or {}).get("awaiting_steps"):
            # 父Run先落partial、再登记handoff，崩溃或快速子任务不得提前关闭账号链。
            completed = any(
                item["status"] == "completed" and item["parent_run_id"] == str(latest["id"]) for item in dependency_rows
            )
            dependencies = dependencies or not completed
        closed = (bool(runs) and not active and not dependencies) or target["admission_state"] in (
            "not_executed",
            "cancelled",
        )
        state = "closed" if closed else "started" if started else target["chain_state"]
        cur.execute(
            f"""UPDATE {table("operation_batch_target_rounds")}
          SET source_revision=source_revision+1,chain_state=%s,
            chain_started_at=CASE WHEN %s THEN COALESCE(chain_started_at,now()) ELSE chain_started_at END,
            chain_closed_at=CASE WHEN %s THEN COALESCE(chain_closed_at,now()) ELSE NULL END
          WHERE id=%s RETURNING source_revision""",
            (state, started, closed, target_round_id),
        )
        revision = int(cur.fetchone()["source_revision"])
        cur.execute(
            f"""INSERT INTO {table("operation_projection_outbox")}
          (event_key,consumer_kind,target_round_id,source_kind,source_id,source_revision,event_kind)
          VALUES (%s,'bulk_target',%s,'target_round',%s,%s,%s) ON CONFLICT(event_key) DO NOTHING""",
            (
                f"bulk_target:target_round:{target_round_id}:{revision}:{event_kind}",
                target_round_id,
                target_round_id,
                revision,
                event_kind,
            ),
        )
        return revision


def inherit_managed_run(
    conn,
    run_id: int,
    *,
    source_run_id: int | None = None,
    parent_task_id: int | None = None,
    step_key: str | None = None,
) -> dict | None:
    if not _enabled():
        return None
    with conn.cursor() as cur:
        if source_run_id is None:
            # 只有来源Task仍只有一个活动归属时才接受；绝不按邮箱或时间猜测。
            cur.execute(
                f"""SELECT l.run_id FROM {table("operation_batch_run_links")} l
              JOIN {table("operation_batch_target_rounds")} t ON t.id=l.target_round_id
              WHERE l.task_id=%s AND l.relation=ANY(%s) AND t.chain_state<>'closed'
              ORDER BY l.execution_generation DESC LIMIT 2""",
                (parent_task_id, list(OWNED)),
            )
            refs = list(cur.fetchall())
            if not refs:
                return None
            source_run_id = refs[0]["run_id"]
        target = lock_managed_target(conn, source_run_id)
        if not target:
            return None
        cur.execute(f"SELECT task_id FROM {table('operation_runs')} WHERE id=%s", (run_id,))
        run = cur.fetchone()
        if not run:
            raise BulkError("managed_run_missing", "新执行不存在", 500)
        cur.execute(
            f"""SELECT * FROM {table("operation_batch_run_links")} WHERE run_id=%s AND relation=ANY(%s)""",
            (run_id, list(OWNED)),
        )
        existing = cur.fetchone()
        if existing:
            if existing["target_round_id"] != target["id"]:
                raise BulkError("managed_ownership_conflict", "执行已属于其他目标", 500)
            return dict(existing)
        if target["chain_state"] == "closed":
            raise BulkError("bulk_chain_closed", "已关闭账号链不能追加自动执行")
        generation = target["next_execution_generation"]
        relation = "owned_child" if parent_task_id else "owned_continuation"
        cur.execute(
            f"""INSERT INTO {table("operation_batch_run_links")}
          (target_round_id,task_id,run_id,task_id_snapshot,run_id_snapshot,step_key,execution_generation,relation)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (
                target["id"],
                run["task_id"],
                run_id,
                run["task_id"],
                run_id,
                step_key or "continuation",
                generation,
                relation,
            ),
        )
        result = dict(cur.fetchone())
        cur.execute(
            f"UPDATE {table('operation_batch_target_rounds')} SET next_execution_generation=next_execution_generation+1 WHERE id=%s",
            (target["id"],),
        )
        cur.execute(f"UPDATE {table('operation_runs')} SET batch_id=%s WHERE id=%s", (target["batch_id"], run_id))
        record_managed_change(conn, target["id"])
        return result


def prepare_targets(batch_id: int, *, limit: int = 100) -> list[dict]:
    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT tr.*,tr.id AS target_round_id,m.target_id,m.target_id AS account_id,
          m.display_snapshot,m.baseline,m.source_run_id_snapshot,source.task_id AS source_task_id,
          root.ordinal AS root_ordinal
          FROM {table("operation_batch_target_rounds")} tr
          JOIN {table("operation_batch_rounds")} r ON r.id=tr.round_id
          JOIN {table("operation_batch_controls")} c ON c.batch_id=tr.batch_id
          JOIN {table("operation_selection_targets")} m ON m.id=tr.member_target_id
          JOIN {table("operation_selection_targets")} root ON root.id=tr.canonical_target_id
          LEFT JOIN {table("operation_runs")} source ON source.id=m.source_run_id_snapshot
          WHERE tr.batch_id=%s AND tr.admission_state IN ('pending_submit','waiting_account')
            AND tr.chain_state='not_started' AND tr.next_prepare_at<=now() AND r.control_action='none' AND NOT c.is_paused
          ORDER BY tr.next_prepare_at,tr.id LIMIT %s""",
            (batch_id, max(1, min(1000, limit))),
        )
        return [dict(x) for x in cur.fetchall()]


def submit_targets(target_round_ids, submitter) -> list[dict]:
    ids = sorted(set(int(x) for x in target_round_ids))
    if not ids:
        return []
    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        # 只协调新批量根任务的准备窗口；不参与原业务准入或注册调度。
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"bulk_submit_window:{store._schema_name()}",)
        )
        cur.execute(f"SELECT DISTINCT batch_id FROM {table('operation_batch_target_rounds')} WHERE id=ANY(%s)", (ids,))
        batches = [x["batch_id"] for x in cur.fetchall()]
        if len(batches) != 1:
            raise BulkError("mixed_submission_batch", "一个提交事务只能处理一个批次", 422)
        context = require_row(
            cur, f"SELECT * FROM {table('operation_batch_controls')} WHERE batch_id=%s FOR SHARE", (batches[0],)
        )
        if context["is_paused"]:
            return []
        capacity = _submission_capacity(cur, context["batch_id"], context["desired_workers"])
        cur.execute(
            f"""SELECT tr.*,tr.id AS target_round_id,m.target_id,m.target_id AS account_id,m.baseline,
          m.display_snapshot,m.source_run_id_snapshot,source.task_id AS source_task_id,r.control_action
          FROM {table("operation_batch_target_rounds")} tr JOIN {table("operation_batch_rounds")} r ON r.id=tr.round_id
          JOIN {table("operation_selection_targets")} m ON m.id=tr.member_target_id
          LEFT JOIN {table("operation_runs")} source ON source.id=m.source_run_id_snapshot
          WHERE tr.id=ANY(%s) ORDER BY tr.id FOR UPDATE OF tr""",
            (ids,),
        )
        candidates = [dict(x) for x in cur.fetchall()]
        eligible = [
            x
            for x in candidates
            if x["admission_state"] in ("pending_submit", "waiting_account") and x["control_action"] == "none"
        ]
        if not eligible:
            return []
        cur.execute(
            f"""SELECT DISTINCT current.id FROM {table("operation_batch_target_rounds")} current
          JOIN {table("operation_batch_rounds")} own_round ON own_round.id=current.round_id
          JOIN {table("operation_batch_rounds")} earlier ON earlier.batch_id=current.batch_id AND earlier.round_no<own_round.round_no
          JOIN {table("operation_selection_targets")} member ON member.selection_id=earlier.member_selection_id
            AND COALESCE(member.canonical_target_id,member.id)=current.canonical_target_id
          LEFT JOIN {table("operation_batch_target_rounds")} old ON old.round_id=earlier.id AND old.canonical_target_id=current.canonical_target_id
          WHERE current.id=ANY(%s) AND ((old.id IS NULL AND earlier.unmaterialized_bucket<>'cancelled')
            OR (old.id IS NOT NULL AND old.chain_state<>'closed'))""",
            ([x["id"] for x in eligible],),
        )
        blocked = {x["id"] for x in cur.fetchall()}
        ready = [x for x in eligible if x["id"] not in blocked][:capacity]
        blocked_receipts = [
            {"target_round_id": x["id"], "disposition": "waiting_account", "reason_code": "earlier_round_pending"}
            for x in eligible
            if x["id"] in blocked
        ]
        receipts = []
        if ready:
            cur.execute(
                f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
                (sorted({x["account_id"] for x in ready}),),
            )
            cur.fetchall()
            context["operation_key"] = context["action_key"]
            receipts = list(submitter(conn, ready, context))
            expected = {x["id"]: x for x in ready}
            if {int(x["target_round_id"]) for x in receipts} != set(expected) or len(receipts) != len(expected):
                raise BulkError("invalid_submission_receipts", "领域提交未为每个固定目标返回唯一回执", 500)
        receipts.extend(blocked_receipts)
        valid = {"created", "idempotent_owned", "waiting_account", "not_executed"}
        if any(item.get("disposition") not in valid for item in receipts):
            raise BulkError("invalid_submission_receipts", "不支持的领域提交回执", 500)
        _save_receipts(cur, receipts, context)
        return receipts


def _submission_capacity(cur, batch_id: int, desired_workers: int) -> int:
    """在新批量窗口锁内重检；多进程不能各自读到相同空位后过量展开。"""
    cur.execute(
        f"""SELECT count(*) AS total,count(*) FILTER(WHERE tr.batch_id=%s) AS own_count
      FROM {table("operation_batch_run_links")} l JOIN {table("operation_runs")} r ON r.id=l.run_id
      JOIN {table("operation_batch_target_rounds")} tr ON tr.id=l.target_round_id
      WHERE l.relation=ANY(%s) AND r.status=ANY(%s)""",
        (batch_id, list(OWNED), list(ACTIVE_RUNS)),
    )
    usage = cur.fetchone()
    return min(max(0, min(128, max(8, desired_workers * 2)) - usage["own_count"]), max(0, 384 - usage["total"]))


def _save_receipts(cur, receipts: list[dict], context: dict) -> None:
    """一次集合保存链接、准入事实和outbox，正常块SQL次数不随目标数增长。"""
    body = dumps(receipts)
    record = "jsonb_to_recordset(%s::jsonb) AS x(target_round_id bigint,disposition text,task_id bigint,run_id bigint,step_key text,relation text,reason_code text,blocker_run_id bigint)"
    cur.execute(
        f"""SELECT 1 FROM {record} JOIN {table("operation_batch_run_links")} l ON l.run_id_snapshot=x.run_id
      WHERE x.disposition IN ('created','idempotent_owned') AND l.relation=ANY(%s)
        AND l.target_round_id<>x.target_round_id LIMIT 1""",
        (body, list(OWNED)),
    )
    if cur.fetchone():
        raise BulkError("managed_ownership_conflict", "复用执行属于其他轮次，禁止接管", 500)
    cur.execute(
        f"""INSERT INTO {table("operation_batch_run_links")}
      (target_round_id,task_id,run_id,task_id_snapshot,run_id_snapshot,step_key,execution_generation,relation)
      SELECT x.target_round_id,x.task_id,x.run_id,x.task_id,x.run_id,COALESCE(x.step_key,%s),
        tr.next_execution_generation,COALESCE(x.relation,'owned_root')
      FROM {record} JOIN {table("operation_batch_target_rounds")} tr ON tr.id=x.target_round_id
      WHERE x.disposition IN ('created','idempotent_owned')
        AND NOT EXISTS(SELECT 1 FROM {table("operation_batch_run_links")} l WHERE l.run_id_snapshot=x.run_id AND l.relation=ANY(%s))""",
        (context["action_key"], body, list(OWNED)),
    )
    cur.execute(
        f"""UPDATE {table("operation_runs")} r SET batch_id=%s FROM {record}
      WHERE r.id=x.run_id AND x.disposition IN ('created','idempotent_owned')""",
        (context["batch_id"], body),
    )
    cur.execute(
        f"""UPDATE {table("operation_tasks")} t SET batch_id=%s FROM {record}
      WHERE t.id=x.task_id AND x.disposition IN ('created','idempotent_owned')""",
        (context["batch_id"], body),
    )
    cur.execute(
        f"""WITH incoming AS MATERIALIZED (
      SELECT x.*,ROW(tr.admission_state,tr.reason_code,tr.blocker_run_id_snapshot) IS DISTINCT FROM
        ROW(CASE WHEN x.disposition IN ('created','idempotent_owned') THEN 'submitted' ELSE x.disposition END,
            x.reason_code,x.blocker_run_id) AS fact_changed
      FROM {record} JOIN {table("operation_batch_target_rounds")} tr ON tr.id=x.target_round_id
    ), changed AS (
      UPDATE {table("operation_batch_target_rounds")} tr SET
        admission_state=CASE WHEN x.disposition IN ('created','idempotent_owned') THEN 'submitted' ELSE x.disposition END,
        reason_code=x.reason_code,blocker_run_id_snapshot=x.blocker_run_id,
        next_prepare_at=CASE WHEN x.disposition='waiting_account' THEN
          now()+(CASE WHEN tr.prepare_attempts=0 THEN 2 WHEN tr.prepare_attempts=1 THEN 5
                     WHEN tr.prepare_attempts=2 THEN 10 ELSE 30 END
                 + (tr.id %% 5)*0.1)*interval '1 second' ELSE now() END,
        prepare_attempts=CASE WHEN x.disposition='waiting_account' THEN LEAST(tr.prepare_attempts+1,1000) ELSE 0 END,
        owner_id=NULL,lease_until=NULL,
        chain_state=CASE WHEN x.disposition='not_executed' THEN 'closed' ELSE tr.chain_state END,
        chain_closed_at=CASE WHEN x.disposition='not_executed' THEN now() ELSE tr.chain_closed_at END,
        next_execution_generation=CASE WHEN x.disposition IN ('created','idempotent_owned') THEN
          (SELECT COALESCE(max(l.execution_generation),0)+1 FROM {table("operation_batch_run_links")} l WHERE l.target_round_id=tr.id)
          ELSE tr.next_execution_generation END,
        source_revision=source_revision+CASE WHEN x.fact_changed THEN 1 ELSE 0 END
      FROM incoming x WHERE tr.id=x.target_round_id RETURNING tr.id,tr.source_revision,x.fact_changed)
      INSERT INTO {table("operation_projection_outbox")}
        (event_key,consumer_kind,target_round_id,source_kind,source_id,source_revision,event_kind)
      SELECT 'bulk_target:target_round:'||id||':'||source_revision||':submitted','bulk_target',id,'target_round',id,source_revision,'submitted'
      FROM changed WHERE fact_changed ON CONFLICT(event_key) DO NOTHING""",
        (body,),
    )


def process_batch(batch_id: int, submitter, *, limit: int = 100) -> dict:
    bulk_schema.init()
    # 仅此独立短事务touch公平游标；不能在target持锁事务升级controls SHARE锁。
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE {table('operation_batch_controls')} SET last_expand_at=clock_timestamp() WHERE batch_id=%s",
            (batch_id,),
        )
    materialized = materialize_targets(batch_id, limit=limit)
    with connect() as conn, conn.cursor() as cur:
        controls = require_row(
            cur, f"SELECT desired_workers FROM {table('operation_batch_controls')} WHERE batch_id=%s", (batch_id,)
        )
        cur.execute(
            f"""SELECT count(*) AS total,count(*) FILTER(WHERE tr.batch_id=%s) AS own_count
          FROM {table("operation_batch_run_links")} l JOIN {table("operation_runs")} r ON r.id=l.run_id
          JOIN {table("operation_batch_target_rounds")} tr ON tr.id=l.target_round_id
          WHERE l.relation=ANY(%s) AND r.status=ANY(%s)""",
            (batch_id, list(OWNED), list(ACTIVE_RUNS)),
        )
        usage = cur.fetchone()
    capacity = min(
        max(0, min(128, max(8, controls["desired_workers"] * 2)) - usage["own_count"]),
        max(0, 384 - usage["total"]),
        max(1, min(100, limit)),
    )
    targets = prepare_targets(batch_id, limit=capacity) if capacity else []
    receipts = submit_targets([x["id"] for x in targets], submitter) if targets else []
    return {
        "materialized": len(materialized),
        "submitted": sum(x["disposition"] in ("created", "idempotent_owned") for x in receipts),
        "waiting": sum(x["disposition"] == "waiting_account" for x in receipts),
        "not_executed": sum(x["disposition"] == "not_executed" for x in receipts),
    }
