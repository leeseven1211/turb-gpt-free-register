"""提链原单续接的精确受管归属；所有事实加入调用方事务。"""
from __future__ import annotations

from collections import Counter
import json

from core.storage.operations import bulk_runtime, common
from core.storage.operations.bulk_common import BulkError, OWNED


class LockedSources(dict):
    """保留原来源身份比较，同时携带在账号锁前已取得的归属快照。"""

    def __init__(self, identities, managed, *, busy_accounts=(), busy_tasks=()):
        super().__init__(identities)
        self.managed = managed
        self.busy_accounts = set(busy_accounts)
        self.busy_tasks = set(busy_tasks)


def lock_sources_many(conn, source_run_ids):
    """在账号与 Task 锁之前，按 target ID 集合锁定原 Run 的真实归属。"""
    ids = sorted({int(value) for value in source_run_ids if value})
    if not ids or not bulk_runtime._enabled():
        return {}
    with conn.cursor() as cur:
        cur.execute(f"""SELECT target.*,link.run_id AS source_run_id
            FROM {common._table('operation_batch_run_links')} link
            JOIN {common._table('operation_batch_target_rounds')} target ON target.id=link.target_round_id
            WHERE link.run_id=ANY(%s) AND link.relation=ANY(%s)
            ORDER BY target.id,link.run_id FOR UPDATE OF target""", (ids, list(OWNED)))
        return {row["source_run_id"]: dict(row) for row in cur.fetchall()}


def prepare(rows, targets):
    """只使用精确来源 Run 的 owned link，不凭 Task、账号或时间推断归属。"""
    for row in rows:
        if not row["data"].get("bulk_target_round_id"):
            continue
        target = targets.get(int(row["source_run_id"]))
        if target is None:
            row["data"].pop("bulk_target_round_id", None)
            continue
        if target["chain_state"] == "closed":
            raise BulkError("bulk_chain_closed", "已关闭账号链不能追加自动执行")
        row["data"]["bulk_target_round_id"] = int(target["id"])
        row["batch_id"] = target["batch_id"]


def inherit_many(conn, rows, targets):
    selected = [row for row in rows if row["data"].get("bulk_target_round_id")
                and int(row["source_run_id"]) in targets]
    if not selected:
        return
    offsets = Counter()
    links = []
    for row in selected:
        target = targets[int(row["source_run_id"])]
        links.append({"target_id": target["id"], "task_id": row["task_id"], "run_id": row["run_id"],
                      "generation": int(target["next_execution_generation"]) + offsets[target["id"]]})
        offsets[target["id"]] += 1
    with conn.cursor() as cur:
        cur.execute(f"""INSERT INTO {common._table('operation_batch_run_links')}
            (target_round_id,task_id,run_id,task_id_snapshot,run_id_snapshot,step_key,execution_generation,relation)
            SELECT s.target_id,s.task_id,s.run_id,s.task_id,s.run_id,'extract_link',s.generation,'owned_continuation'
            FROM jsonb_to_recordset(%s::jsonb) AS s(target_id bigint,task_id bigint,run_id bigint,generation bigint)""",
                    (json.dumps(links),))
        cur.execute(f"""UPDATE {common._table('operation_batch_target_rounds')} target
            SET next_execution_generation=target.next_execution_generation+s.amount
            FROM jsonb_to_recordset(%s::jsonb) AS s(id bigint,amount bigint) WHERE target.id=s.id""",
                    (json.dumps([{"id": key, "amount": value} for key, value in offsets.items()]),))
    # 原 inherit_managed_run 与外层 changed 各记录一次事实版本，保持旧投影事件边界。
    bulk_runtime.record_managed_changes_many(conn, offsets)
    bulk_runtime.record_managed_changes_many(conn, offsets)


def reconcile_parents(cur, parent_task_ids):
    from core.storage.operations.bulk_retry_reconcile import reconcile_parents_many
    from core.storage.operations.bulk_retry_registration import reconcile_registration_many

    # 原工作台只按 parent 收口，不把提链子任务当作注册自动补密码回执。
    facts = reconcile_parents_many(cur, parent_task_ids)
    batches = set(facts["batch_ids"])
    batches.update(reconcile_registration_many(cur,
                   parent_run_ids=facts["registration_run_ids"]))
    return batches
