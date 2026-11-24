"""集合刷新重试涉及的传统批次即时计数；受管批次保留 outbox 投影。"""
from __future__ import annotations

from core.storage.operations import bulk_schema, common

_CHUNK_SIZE = 500


def refresh_batches_many(cur, batch_ids) -> None:
    """复现旧批次 root/latest-child 统计；按升序锁定且不逐批发出 SQL。"""
    ids = sorted({int(value) for value in batch_ids if value is not None})
    if not ids:
        return
    managed_enabled = bulk_schema._READY_KEY == f"{common.postgres_store.database_url()}::{common._schema_name()}"
    for offset in range(0, len(ids), _CHUNK_SIZE):
        selected = ids[offset:offset + _CHUNK_SIZE]
        if managed_enabled:
            cur.execute(f"SELECT batch_id FROM {common._table('operation_batch_controls')} WHERE batch_id=ANY(%s)",
                        (selected,))
            managed = {int(row["batch_id"]) for row in cur.fetchall()}
            selected = [batch_id for batch_id in selected if batch_id not in managed]
        if not selected:
            continue
        # 与既有 writer 同样使用 batch ID advisory lock，跨批次始终递增。
        cur.execute("SELECT pg_advisory_xact_lock(id) FROM unnest(%s::bigint[]) AS value(id) ORDER BY id",
                    (selected,))
        cur.fetchall()
        cur.execute(f"""SELECT id FROM {common._table('operation_batches')}
            WHERE id=ANY(%s) ORDER BY id FOR NO KEY UPDATE""", (selected,))
        existing = [int(row["id"]) for row in cur.fetchall()]
        if not existing:
            continue
        cur.execute(f"""WITH task_rows AS MATERIALIZED (
                SELECT batch_id,id,COALESCE(root_task_id,id) AS root_id,status,updated_at
                FROM {common._table('operation_tasks')} WHERE batch_id=ANY(%s)
            ), roots AS (
                SELECT DISTINCT ON (batch_id,root_id) batch_id,root_id,status
                FROM task_rows ORDER BY batch_id,root_id,(id=root_id) DESC,updated_at DESC,id DESC
            ), children AS (
                SELECT DISTINCT ON (batch_id,root_id) batch_id,root_id,status
                FROM task_rows WHERE id<>root_id
                ORDER BY batch_id,root_id,updated_at DESC,id DESC
            ), effective AS (
                SELECT roots.batch_id,CASE WHEN children.status IS NULL THEN roots.status
                    WHEN children.status='failed' AND roots.status IN ('success','partial_success')
                    THEN 'partial_success' ELSE children.status END AS status
                FROM roots LEFT JOIN children USING(batch_id,root_id)
            ), totals AS (
                SELECT batch.id,
                    count(*) FILTER(WHERE effective.status='queued') AS queued,
                    count(*) FILTER(WHERE effective.status IN ('running','stopping','cancelling','settling','waiting')) AS running,
                    count(*) FILTER(WHERE effective.status='success') AS success,
                    count(*) FILTER(WHERE effective.status='partial_success') AS partial,
                    count(*) FILTER(WHERE effective.status IN ('failed','deactivated','unsupported')) AS failed,
                    count(*) FILTER(WHERE effective.status IN ('attention_required','interrupted','request_unknown','manual_reconcile')) AS attention,
                    count(*) FILTER(WHERE effective.status='stopped') AS stopped,
                    count(*) FILTER(WHERE effective.status='cancelled') AS cancelled,
                    batch.skipped_count AS skipped
                FROM {common._table('operation_batches')} batch
                LEFT JOIN effective ON effective.batch_id=batch.id WHERE batch.id=ANY(%s)
                GROUP BY batch.id,batch.skipped_count
            ), desired AS (
                SELECT totals.*,CASE WHEN running>0 THEN 'running' WHEN queued>0 THEN 'queued'
                    WHEN failed>0 OR attention>0 OR skipped<>0
                        THEN CASE WHEN success>0 OR partial>0 THEN 'partial_success' ELSE 'failed' END
                    WHEN partial>0 THEN 'partial_success' WHEN success>0 THEN 'success'
                    WHEN stopped>0 OR cancelled>0 THEN 'stopped' ELSE 'queued' END AS status
                FROM totals
            ) UPDATE {common._table('operation_batches')} batch
            SET status=desired.status,queued_count=desired.queued,running_count=desired.running,
                success_count=desired.success,partial_count=desired.partial,failed_count=desired.failed,
                attention_count=desired.attention,stopped_count=desired.stopped,cancelled_count=desired.cancelled,
                completed_at=CASE WHEN desired.status IN ('queued','running') THEN NULL ELSE clock_timestamp() END
            FROM desired WHERE batch.id=desired.id""", (existing, existing))
