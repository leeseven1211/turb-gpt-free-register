# -*- coding: utf-8 -*-
"""控制请求、后台结算和可恢复租约。"""

from __future__ import annotations

from core.storage.operations import bulk_schema, store
from core.storage.operations.bulk_common import (
    BulkError,
    ACTIVE_RUNS,
    OWNED,
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
)
from core.storage.operations.bulk_batches import _cancel_preparing
from core.storage.operations.bulk_runtime import record_managed_change
from core.storage.operations.bulk_projection import _complete_rounds, _sync_legacy


def request_control(
    batch_id: int, *, request_key: str, action: str, expected_control_revision: int, round_id: int | None = None
) -> dict:
    bulk_schema.init()
    validate_key(request_key)
    if action not in ("cancel_not_started", "request_stop", "pause", "resume"):
        raise BulkError("invalid_control_action", "不支持的批次控制动作", 422)
    if action in ("pause", "resume") and round_id is not None:
        raise BulkError("invalid_control_scope", "暂停和继续仅支持整个批次", 422)
    hashed = digest({"action": action, "expected_control_revision": expected_control_revision, "round_id": round_id})
    with connect() as conn, conn.cursor() as cur:
        request_guard(cur, f"control:{batch_id}", request_key)
        cur.execute(
            f"SELECT * FROM {table('operation_batch_control_commands')} WHERE batch_id=%s AND request_key=%s",
            (batch_id, request_key),
        )
        previous = receipt(cur.fetchone(), hashed)
        if previous:
            return previous
        controls = require_row(
            cur, f"SELECT * FROM {table('operation_batch_controls')} WHERE batch_id=%s FOR UPDATE", (batch_id,)
        )
        if controls["control_revision"] != expected_control_revision:
            raise BulkError(
                "control_revision_changed",
                "批次控制状态已变化，请刷新",
                detail={"control_revision": controls["control_revision"]},
            )
        if action in ("pause", "resume") and controls["state"] != "active":
            raise BulkError("batch_not_active", "仅执行中的批次可以暂停或继续，请刷新批次状态")
        if round_id:
            require_row(
                cur,
                f"SELECT id FROM {table('operation_batch_rounds')} WHERE id=%s AND batch_id=%s",
                (round_id, batch_id),
            )
        revision = controls["control_revision"] + 1
        cur.execute(
            f"""INSERT INTO {table("operation_batch_control_commands")}
          (batch_id,request_key,request_hash,action,scope_kind,scope_round_id,through_round_no,
           expected_control_revision,result_control_revision,state)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'accepted') RETURNING *""",
            (
                batch_id,
                request_key,
                hashed,
                action,
                "round" if round_id else "batch",
                round_id,
                controls["next_round_no"] - 1,
                expected_control_revision,
                revision,
            ),
        )
        command = dict(cur.fetchone(), reused=False)
        if action in ("pause", "resume"):
            # 暂停与派发共用 controls 行锁；返回后不能再开始新的账号链。
            cur.execute(
                f"""UPDATE {table('operation_batch_controls')} SET is_paused=%s,
                control_revision=%s,updated_at=now() WHERE batch_id=%s""",
                (action == "pause", revision, batch_id),
            )
            cur.execute(
                f"""UPDATE {table('operation_batch_control_commands')} SET state='completed',completed_at=now()
                WHERE id=%s RETURNING *""",
                (command["id"],),
            )
            return dict(cur.fetchone(), reused=False)
        cur.execute(
            f"""UPDATE {table("operation_batch_rounds")} SET control_action=CASE WHEN control_action='request_stop'
          THEN control_action ELSE %s END,control_command_id=%s,control_revision=control_revision+1
          WHERE batch_id=%s AND round_no<=%s AND (%s::bigint IS NULL OR id=%s)
            AND state IN ('preparing','active','settling')""",
            (action, command["id"], batch_id, command["through_round_no"], round_id, round_id),
        )
        cur.execute(
            f"""UPDATE {table("operation_batch_controls")} SET control_revision=%s,
          state=CASE WHEN %s::bigint IS NOT NULL THEN state WHEN %s='request_stop' THEN 'stop_requested' ELSE 'cancel_requested' END,
          is_paused=CASE WHEN %s::bigint IS NULL THEN FALSE ELSE is_paused END,
          updated_at=now() WHERE batch_id=%s""",
            (revision, round_id, action, round_id, batch_id),
        )
        return command


def settle_control(
    command_id: int, *, cancel_run=None, limit: int = 100, owner_id: str | None = None, fence: int | None = None
) -> dict:
    bulk_schema.init()
    # 先结算隐式名单，释放投影锁后再进入真实执行取消，禁止反向取业务锁。
    with connect() as conn, conn.cursor() as cur:
        command = require_row(
            cur, f"SELECT * FROM {table('operation_batch_control_commands')} WHERE id=%s", (command_id,)
        )
        if command["state"] == "completed":
            return command
        batch_id = command["batch_id"]
        guard(cur, batch_id)
        controls = require_row(
            cur, f"SELECT * FROM {table('operation_batch_controls')} WHERE batch_id=%s FOR UPDATE", (batch_id,)
        )
        command = require_row(
            cur, f"SELECT * FROM {table('operation_batch_control_commands')} WHERE id=%s FOR UPDATE", (command_id,)
        )
        if owner_id is not None and (command["owner_id"] != owner_id or command["fence"] != fence):
            raise BulkError("lease_lost", "控制命令租约已失效")
        if command["state"] == "completed":
            return command
        cur.execute(
            f"""SELECT * FROM {table("operation_batch_rounds")} WHERE batch_id=%s AND round_no<=%s
          AND (%s::bigint IS NULL OR id=%s) ORDER BY id FOR UPDATE""",
            (batch_id, command["through_round_no"], command["scope_round_id"], command["scope_round_id"]),
        )
        rounds = [dict(x) for x in cur.fetchall()]
        delta = {"pending_submit": 0, "cancelled": 0}
        for row in rounds:
            if row["state"] == "preparing":
                _cancel_preparing(cur, row)
                continue
            if row["target_count"] is None or row["unmaterialized_bucket"] == "cancelled":
                continue
            remaining = row["target_count"] - row["materialized_count"]
            if remaining:
                # 当前视图只有仍归属本轮的未物化成员发生变化。
                cur.execute(
                    f"""WITH changed AS (
                  UPDATE {table("operation_selection_targets")} root SET current_contribution='{{"cancelled":1}}'::jsonb,
                    current_projection_revision=root.current_projection_revision+1
                  FROM {table("operation_selection_targets")} m
                  WHERE m.selection_id=%s AND m.ordinal>%s AND root.id=COALESCE(m.canonical_target_id,m.id)
                    AND COALESCE(root.latest_requested_round_id,%s)=%s
                  RETURNING root.id) SELECT count(*) AS total FROM changed""",
                    (
                        row["member_selection_id"],
                        row["materialization_cursor"],
                        controls["initial_round_id"],
                        row["id"],
                    ),
                )
                current = int(cur.fetchone()["total"])
                delta["pending_submit"] -= current
                delta["cancelled"] += current
            revised = add_counts(row["counts"], {"pending_submit": -remaining, "cancelled": remaining})
            cur.execute(
                f"""UPDATE {table("operation_batch_rounds")} SET unmaterialized_bucket='cancelled',
              counts=%s::jsonb,summary_revision=summary_revision+1,state=CASE WHEN state='active' THEN 'settling' ELSE state END
              WHERE id=%s""",
                (dumps(revised), row["id"]),
            )
        values = add_counts(controls["counts"], delta)
        cur.execute(
            f"""UPDATE {table("operation_batch_controls")} SET counts=%s::jsonb,summary_revision=summary_revision+1,
          projected_at=now() WHERE batch_id=%s""",
            (dumps(values), batch_id),
        )
        cur.execute(
            f"""UPDATE {table("operation_batch_control_commands")} SET state='settling' WHERE id=%s""", (command_id,)
        )
        _complete_rounds(cur, batch_id)
        _sync_legacy(cur, batch_id, values)
        round_ids = [x["id"] for x in rounds]
    if cancel_run is None:
        cancel_run = store.request_run_cancel
    with connect() as conn, conn.cursor() as cur:
        # 两个阶段之间可能被新owner接管；必须重读命令和游标，旧worker不得继续执行取消。
        command = require_row(
            cur, f"SELECT * FROM {table('operation_batch_control_commands')} WHERE id=%s FOR UPDATE", (command_id,)
        )
        if owner_id is not None and (command["owner_id"] != owner_id or command["fence"] != fence):
            raise BulkError("lease_lost", "控制命令租约已失效")
        if command["state"] == "completed":
            return command
        cur.execute(
            f"""SELECT t.* FROM {table("operation_batch_target_rounds")} t
          WHERE t.round_id=ANY(%s) AND t.chain_state<>'closed'
            AND (%s='request_stop' OR t.chain_started_at IS NULL)
            AND t.id>%s ORDER BY t.id LIMIT %s FOR UPDATE""",
            (round_ids, command["action"], command["settlement_cursor"], max(1, min(100, limit))),
        )
        targets = [dict(x) for x in cur.fetchall()]
        for target in targets:
            cur.execute(
                f"""SELECT l.run_id FROM {table("operation_batch_run_links")} l
              JOIN {table("operation_runs")} r ON r.id=l.run_id WHERE l.target_round_id=%s
              AND l.relation=ANY(%s) AND r.status=ANY(%s) ORDER BY l.task_id,l.run_id""",
                (target["id"], list(OWNED), list(ACTIVE_RUNS)),
            )
            run_ids = [x["run_id"] for x in cur.fetchall()]
            for run_id in run_ids:
                cancel_run(
                    run_id,
                    reason="批量任务请求停止" if command["action"] == "request_stop" else "批量任务取消未开始",
                    conn=conn,
                )
            if not run_ids:
                cur.execute(
                    f"""UPDATE {table("operation_batch_target_rounds")} SET admission_state='cancelled',
                  reason_code='batch_cancelled' WHERE id=%s""",
                    (target["id"],),
                )
            record_managed_change(conn, target["id"])
        if targets:
            cur.execute(
                f"""UPDATE {table("operation_batch_control_commands")} SET settlement_cursor=%s,
              owner_id=NULL,lease_until=NULL WHERE id=%s RETURNING *""",
                (targets[-1]["id"], command_id),
            )
        else:
            cur.execute(
                f"""UPDATE {table("operation_batch_control_commands")} SET state='completed',completed_at=now(),
              owner_id=NULL,lease_until=NULL WHERE id=%s RETURNING *""",
                (command_id,),
            )
        return dict(cur.fetchone())


def claim_work(kind: str, owner_id: str, *, limit: int = 1, lease_seconds: int = 30) -> list[dict]:
    bulk_schema.init()
    options = {
        "selection": (
            "operation_selections",
            "status='preparing' AND selection_kind<>'retry_members'",
            "next_attempt_at",
        ),
        "round": ("operation_batch_rounds", "state='preparing'", "next_attempt_at"),
        "control": ("operation_batch_control_commands", "state IN ('accepted','settling')", None),
    }
    if kind not in options:
        raise BulkError("invalid_worker_kind", "不支持的协调任务类型", 422)
    name, predicate, due = options[kind]
    if due:
        predicate += f" AND {due}<=now()"
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""WITH picked AS (SELECT id FROM {table(name)} WHERE {predicate}
          AND (lease_until IS NULL OR lease_until<=now()) ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED)
          UPDATE {table(name)} target SET owner_id=%s,lease_until=now()+(%s*interval '1 second'),fence=fence+1
          FROM picked WHERE target.id=picked.id RETURNING target.*""",
            (max(1, min(100, limit)), owner_id, max(5, min(300, lease_seconds))),
        )
        return [dict(x) for x in cur.fetchall()]


def renew_work(kind: str, resource_id: int, owner_id: str, fence: int, *, lease_seconds: int = 30) -> bool:
    names = {
        "selection": "operation_selections",
        "round": "operation_batch_rounds",
        "control": "operation_batch_control_commands",
    }
    if kind not in names:
        raise BulkError("invalid_worker_kind", "不支持的协调任务类型", 422)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {table(names[kind])} SET lease_until=now()+(%s*interval '1 second')
          WHERE id=%s AND owner_id=%s AND fence=%s""",
            (lease_seconds, resource_id, owner_id, fence),
        )
        return bool(cur.rowcount)


def expire_selections(*, limit: int = 100) -> int:
    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""WITH picked AS (SELECT id FROM {table("operation_selections")}
          WHERE status IN ('ready','failed') AND expires_at<=now() AND consumed_by_batch_id IS NULL
            AND consumed_by_round_id IS NULL ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED)
          UPDATE {table("operation_selections")} s SET status='expired',updated_at=now()
          FROM picked WHERE s.id=picked.id RETURNING s.id""",
            (max(1, min(100, limit)),),
        )
        ids = [x["id"] for x in cur.fetchall()]
        if ids:
            cur.execute(f"DELETE FROM {table('operation_selection_targets')} WHERE selection_id=ANY(%s)", (ids,))
        return len(ids)
