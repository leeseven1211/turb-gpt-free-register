# -*- coding: utf-8 -*-
"""持久outbox增量投影；不扫描或改写注册批次。"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from core.storage.operations import bulk_schema
from core.storage.operations.bulk_common import (
    BUCKETS,
    OWNED,
    BulkError,
    add_counts,
    connect,
    table,
    dumps,
    guard,
    require_row,
)

logger = logging.getLogger(__name__)


def project_pending(*, limit: int = 200) -> int:
    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT tr.batch_id FROM {table("operation_projection_outbox")} e
          JOIN {table("operation_batch_target_rounds")} tr ON tr.id=e.target_round_id
          WHERE e.consumer_kind='bulk_target' AND e.processed_at IS NULL AND e.available_at<=now()
          GROUP BY tr.batch_id ORDER BY min(e.id),tr.batch_id LIMIT 20""")
        batches = [x["batch_id"] for x in cur.fetchall()]
    processed = 0
    for batch_id in batches:
        try:
            processed += project_batch(batch_id, limit=max(1, min(200, limit - processed)))
        except Exception as exc:
            from psycopg import OperationalError, ProgrammingError

            if isinstance(exc, OperationalError):
                # 数据库整体不可用时不伪装成单批数据错误。
                raise
            code = (
                exc.code
                if isinstance(exc, BulkError)
                else ("projection_query_failed" if isinstance(exc, ProgrammingError) else "projection_adapter_failed")
            )
            logger.exception("批次结果投影失败，其他批次继续：batch_id=%s code=%s", batch_id, code)
            with connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {table("operation_projection_outbox")} event
                  SET attempts=event.attempts+1,error_code=%s,
                    available_at=now()+LEAST(300,5*power(2,LEAST(event.attempts,6))) * interval '1 second'
                  FROM {table("operation_batch_target_rounds")} target
                  WHERE event.target_round_id=target.id AND target.batch_id=%s
                    AND event.consumer_kind='bulk_target' AND event.processed_at IS NULL
                    AND event.available_at<=now()""",
                    (code, batch_id),
                )
        if processed >= limit:
            break
    return processed


def project_batch(batch_id: int, *, limit: int = 200) -> int:
    from core.bulk_operations.results import project_many

    bulk_schema.init()
    with connect() as conn, conn.cursor() as cur:
        guard(cur, batch_id)
        controls = require_row(
            cur, f"SELECT * FROM {table('operation_batch_controls')} WHERE batch_id=%s FOR UPDATE", (batch_id,)
        )
        cur.execute(
            f"""SELECT e.id,e.target_round_id FROM {table("operation_projection_outbox")} e
          JOIN {table("operation_batch_target_rounds")} tr ON tr.id=e.target_round_id
          WHERE tr.batch_id=%s AND e.consumer_kind='bulk_target' AND e.processed_at IS NULL AND e.available_at<=now()
          ORDER BY e.id LIMIT %s""",
            (batch_id, max(1, min(200, limit))),
        )
        events = list(cur.fetchall())
        if not events:
            return 0
        target_ids = sorted({x["target_round_id"] for x in events})
        cur.execute(
            f"""SELECT DISTINCT round_id,canonical_target_id FROM {table("operation_batch_target_rounds")} WHERE id=ANY(%s)""",
            (target_ids,),
        )
        pairs = list(cur.fetchall())
        round_ids = sorted({x["round_id"] for x in pairs})
        root_ids = sorted({x["canonical_target_id"] for x in pairs})
        cur.execute(
            f"SELECT * FROM {table('operation_batch_rounds')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE", (round_ids,)
        )
        rounds = {x["id"]: dict(x) for x in cur.fetchall()}
        cur.execute(
            f"SELECT * FROM {table('operation_selection_targets')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE", (root_ids,)
        )
        roots = {x["id"]: dict(x) for x in cur.fetchall()}
        cur.execute(
            f"SELECT * FROM {table('operation_batch_target_rounds')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
            (target_ids,),
        )
        targets = [dict(x) for x in cur.fetchall()]
        cur.execute(
            f"""SELECT l.target_round_id,l.relation,l.execution_generation AS generation,r.id,r.task_id,r.status,
          r.started_at,r.cancel_requested_at,r.progress_stage,r.error_code,r.result_summary,
          jsonb_build_object('required_steps',r.data->'required_steps','configured_steps',r.data->'configured_steps',
            'remote_intent',r.data->'remote_intent','blocked',r.data->'blocked') AS data
          FROM {table("operation_batch_run_links")} l JOIN {table("operation_runs")} r ON r.id=l.run_id
          WHERE l.target_round_id=ANY(%s) AND l.relation=ANY(%s) ORDER BY l.target_round_id,l.execution_generation""",
            (target_ids, list(OWNED)),
        )
        owned = defaultdict(list)
        for row in cur.fetchall():
            owned[row["target_round_id"]].append(dict(row))
        cur.execute(
            f"""SELECT DISTINCT l.target_round_id,d.id,d.status,d.dependency_type,d.child_status,d.child_result,
          d.payload->>'parent_run_id' AS parent_run_id
          FROM {table("operation_batch_run_links")} l JOIN {table("operation_tasks")} t ON t.id=l.task_id
          JOIN {table("operation_task_dependencies")} d ON d.parent_source_system=t.source_system AND (d.parent_source_id=t.source_id OR (d.parent_source_system='webui_runtime' AND d.parent_source_id=t.id::text))
          WHERE l.target_round_id=ANY(%s) AND l.relation=ANY(%s)
            AND (d.payload->>'parent_run_id' IS NULL OR d.payload->>'parent_run_id'=l.run_id_snapshot::text)""",
            (target_ids, list(OWNED)),
        )
        dependencies = defaultdict(list)
        for row in cur.fetchall():
            dependencies[row["target_round_id"]].append(dict(row))
        evidence = [
            dict(
                t,
                target_round_id=t["id"],
                operation_key=controls["action_key"],
                runs=owned[t["id"]],
                dependencies=dependencies[t["id"]],
                baseline=roots[t["canonical_target_id"]]["baseline"],
            )
            for t in targets
        ]
        projections = project_many(
            evidence, operation_key=controls["action_key"], schema_version=controls["result_version"]
        )
        if len(projections) != len(targets) or any(
            int(value.get("target_round_id") or 0) != target["id"] for target, value in zip(targets, projections)
        ):
            raise BulkError("adapter_contract_violation", "结果适配未返回完整且对应的固定目标", 500)
        batch_delta = defaultdict(int)
        round_delta = defaultdict(lambda: defaultdict(int))
        batch_metrics = defaultdict(int)
        round_metrics = defaultdict(lambda: defaultdict(int))
        changed = 0
        target_updates = []
        root_updates = []
        audit_events = []
        for target, projection in zip(targets, projections):
            if target["source_revision"] <= target["applied_revision"]:
                continue
            state = projection["state"]
            if state not in BUCKETS:
                raise BulkError("projection_state_invalid", "投影返回非法状态", 500)
            old = target["applied_contribution"]
            new = {state: 1}
            for bucket in BUCKETS:
                delta = int(new.get(bucket, 0)) - int(old.get(bucket, 0))
                round_delta[target["round_id"]][bucket] += delta
            root = roots[target["canonical_target_id"]]
            current = (root["latest_requested_round_id"] or controls["initial_round_id"]) == target["round_id"]
            if current:
                for bucket in BUCKETS:
                    batch_delta[bucket] += int(new.get(bucket, 0)) - int(root["current_contribution"].get(bucket, 0))
            old_metrics = target["result"].get("_metrics") or {}
            new_metrics = projection.get("contribution", {}).get("dimensions", {})
            for key in set(old_metrics) | set(new_metrics):
                delta = int(new_metrics.get(key, 0)) - int(old_metrics.get(key, 0))
                round_metrics[target["round_id"]][key] += delta
                if current:
                    batch_metrics[key] += delta
            stored = dict(projection, _metrics=new_metrics)
            reason = (projection.get("reason") or {}).get("code")
            target_updates.append(
                {
                    "id": target["id"],
                    "outcome": state,
                    "result": stored,
                    "reason_code": reason,
                    "applied_contribution": new,
                }
            )
            if current:
                root_updates.append({"id": root["id"], "current_contribution": new})
            if (
                target["applied_revision"]
                and target["outcome"]
                in ("success", "partial_success", "failed", "not_executed", "cancelled", "attention_required")
                and (
                    target["outcome"] != state
                    or (target["result"].get("result") or {}) != (projection.get("result") or {})
                )
            ):
                roots_owned = [
                    item for item in owned[target["id"]] if item["relation"] in ("owned_root", "owned_continuation")
                ]
                if roots_owned:
                    source = max(roots_owned, key=lambda item: item["generation"])
                    identity = f"bulk.result_revised:{target['id']}:{target['source_revision']}"
                    audit_events.append(
                        {
                            "event_uuid": hashlib.sha256(identity.encode()).hexdigest(),
                            "task_id": source["task_id"],
                            "run_id": source["id"],
                            "source_id": identity,
                            "detail": {
                                "target_round_id": target["id"],
                                "old_revision": target["applied_revision"],
                                "new_revision": target["source_revision"],
                                "old_state": target["outcome"],
                                "new_state": state,
                                "reason_code": reason,
                            },
                        }
                    )
            changed += 1
        if target_updates:
            cur.execute(
                f"""UPDATE {table("operation_batch_target_rounds")} target SET outcome=x.outcome,result=x.result,
              reason_code=x.reason_code,applied_contribution=x.applied_contribution,
              applied_revision=target.source_revision,projected_at=now()
              FROM jsonb_to_recordset(%s::jsonb) x(id bigint,outcome text,result jsonb,reason_code text,applied_contribution jsonb)
              WHERE target.id=x.id""",
                (dumps(target_updates),),
            )
        if root_updates:
            cur.execute(
                f"""UPDATE {table("operation_selection_targets")} root SET current_contribution=x.current_contribution,
              current_projection_revision=root.current_projection_revision+1
              FROM jsonb_to_recordset(%s::jsonb) x(id bigint,current_contribution jsonb) WHERE root.id=x.id""",
                (dumps(root_updates),),
            )
        if audit_events:
            cur.execute(
                f"""INSERT INTO {table("operation_events")}
              (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
              SELECT event_uuid,task_id,run_id,'bulk_projection',source_id,'INFO','complete','bulk.result_revised',
                '批次历史结果已依据原执行回执修订',detail
              FROM jsonb_to_recordset(%s::jsonb) x(event_uuid text,task_id bigint,run_id bigint,source_id text,detail jsonb)
              ON CONFLICT(source_system,source_id) DO NOTHING""",
                (dumps(audit_events),),
            )
        # 按目标版本确认，较小事件ID晚提交时仍能被下一轮发现。
        cur.execute(
            f"""UPDATE {table("operation_projection_outbox")} event SET processed_at=now()
          FROM {table("operation_batch_target_rounds")} target
          WHERE event.target_round_id=target.id AND target.id=ANY(%s)
            AND event.consumer_kind='bulk_target' AND event.source_revision<=target.source_revision
            AND event.processed_at IS NULL""",
            (target_ids,),
        )
        for rid, delta in round_delta.items():
            values = add_counts(rounds[rid]["counts"], delta)
            metrics = _metric_delta(rounds[rid]["metrics"], round_metrics[rid])
            cur.execute(
                f"""UPDATE {table("operation_batch_rounds")} SET counts=%s::jsonb,metrics=%s::jsonb,
              summary_revision=summary_revision+1 WHERE id=%s""",
                (dumps(values), dumps(metrics), rid),
            )
        if changed:
            values = add_counts(controls["counts"], batch_delta)
            metrics = _metric_delta(controls["metrics"], batch_metrics)
            cur.execute(
                f"""UPDATE {table("operation_batch_controls")} SET counts=%s::jsonb,metrics=%s::jsonb,
              summary_revision=summary_revision+1,projected_at=now() WHERE batch_id=%s""",
                (dumps(values), dumps(metrics), batch_id),
            )
        else:
            values = controls["counts"]
        _complete_rounds(cur, batch_id)
        _sync_legacy(cur, batch_id, values)
        return len(events)


def _metric_delta(original: dict, delta: dict) -> dict:
    result = dict(original)
    for key, value in delta.items():
        result[key] = int(result.get(key, 0)) + value
        if result[key] < 0:
            raise BulkError("projection_metrics_invalid", "结果维度计数出现负数", 500)
    return result


def _complete_rounds(cur, batch_id: int) -> None:
    cur.execute(
        f"""UPDATE {table("operation_batch_rounds")} r SET state='completed',completed_at=now(),completion_reason='finished'
      WHERE r.batch_id=%s AND r.state IN ('active','settling')
        AND (r.materialized_count=r.target_count OR r.unmaterialized_bucket='cancelled')
        AND NOT EXISTS(SELECT 1 FROM {table("operation_batch_target_rounds")} t WHERE t.round_id=r.id
          AND (t.chain_state<>'closed' OR t.source_revision<>t.applied_revision))""",
        (batch_id,),
    )
    cur.execute(
        f"""UPDATE {table("operation_batch_controls")} c SET state='ended'
      WHERE c.batch_id=%s AND NOT EXISTS(SELECT 1 FROM {table("operation_batch_rounds")} r
        WHERE r.batch_id=c.batch_id AND r.state IN ('preparing','active','settling'))""",
        (batch_id,),
    )


def _sync_legacy(cur, batch_id: int, values: dict) -> None:
    running = values.get("running", 0) + values.get("waiting", 0)
    queued = values.get("queued", 0) + values.get("pending_submit", 0) + values.get("waiting_account", 0)
    if running:
        status = "running"
    elif queued:
        status = "queued"
    elif values.get("attention_required", 0):
        status = "attention_required"
    elif values.get("partial_success", 0) or (values.get("failed", 0) and values.get("success", 0)):
        status = "partial_success"
    elif values.get("failed", 0):
        status = "failed"
    elif values.get("success", 0):
        status = "success"
    elif values.get("cancelled", 0):
        status = "cancelled"
    else:
        status = "unsupported"
    cur.execute(
        f"""UPDATE {table("operation_batches")} SET status=%s,queued_count=%s,running_count=%s,
      success_count=%s,partial_count=%s,failed_count=%s,attention_count=%s,cancelled_count=%s,skipped_count=%s,
      completed_at=CASE WHEN %s=0 THEN COALESCE(completed_at,now()) ELSE NULL END WHERE id=%s""",
        (
            status,
            queued,
            running,
            values.get("success", 0),
            values.get("partial_success", 0),
            values.get("failed", 0),
            values.get("attention_required", 0),
            values.get("cancelled", 0),
            values.get("not_executed", 0),
            queued + running,
            batch_id,
        ),
    )
