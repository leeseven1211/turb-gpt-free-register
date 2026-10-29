"""提链批次的轻量候选与摘要仓储，复用统一 operation 批次表。"""
from __future__ import annotations

import json
import uuid
from contextlib import nullcontext
from datetime import date, datetime

from core import admin_repository, record_store
from core.storage import operation


MAX_BATCH_SIZE = 5000
MAX_BATCH_WORKERS = 50
_FILTER_FIELDS = {"query", "source", "date_from", "date_to", "extract_status", "promotion"}
_EXTRACT_STATUSES = {"not_succeeded", "all", "failed", "never", "success"}
_PROMOTION_FILTERS = {"eligible", "free_trial", "half_price", "other_discount", "other_promo", "none"}


def sync_cancelled_account_extraction(run_id: int, *, expected_account_version: str | None = None) -> bool:
    """仅收口被取消 Run 自己的账号占用，不覆盖新任务或已出链事实。

    新取消传入取消前账号快照的版本；历史取消没有快照时，只修复排队时间明确
    早于该 Run 创建及取消时间的占用。同秒或缺失时间无法证明归属，返回 False。
    """
    operation.init()
    with operation._connect() as conn, conn.cursor() as cur:
        # 重跑按 task→account 加锁；不锁 Run，避免和取消的 Run→task 顺序形成环。
        cur.execute(
            f"""SELECT run.id, run.task_id, run.account_id, run.status, run.source_system,
                       run.created_at, run.cancel_requested_at, run.completed_at,
                       task.task_type, task.last_run_id, task.source_system AS task_source,
                       COALESCE(LOWER(job.extraction_state) IN ('succeeded','success')
                           OR LOWER(job.public_state->>'extraction_state') IN ('succeeded','success')
                           OR job.public_state->'summary'->'extraction_ever_succeeded'='true'::jsonb,
                           FALSE) AS extraction_succeeded
                FROM {operation._table('operation_runs')} run
                JOIN {operation._table('operation_tasks')} task ON task.id=run.task_id
                LEFT JOIN {operation._table('extract_link_provider_jobs')} job ON job.run_id=run.id
                WHERE run.id=%s FOR UPDATE OF task""",
            (int(run_id),),
        )
        run = cur.fetchone()
        if not run or (
            run["source_system"] != "native_operations" or run["task_source"] != "native_operations"
            or run["task_type"] != "extract_link" or run["status"] != "cancelled"
            or run["cancel_requested_at"] is None or run["last_run_id"] != int(run_id)
            or not run["account_id"]
        ):
            return True
        account_id = int(run["account_id"])
        account = record_store.get_row(
            record_store.ACCOUNTS, account_id, conn=conn, for_update=True, include_version=True,
        )
        if not account or str(account.get("extract_link_status") or "").lower() not in {"queued", "running"}:
            return True
        cur.execute(
            f"""SELECT 1 FROM {operation._table('operation_tasks')} other
                LEFT JOIN {operation._table('operation_runs')} related ON related.task_id=other.id
                WHERE other.account_id=%s AND other.task_type='extract_link'
                  AND (other.id>%s OR related.id>%s
                       OR (related.id<>%s AND related.status=ANY(%s))
                       OR (other.id<>%s AND other.status=ANY(%s))) LIMIT 1""",
            (account_id, int(run["task_id"]), int(run_id), int(run_id),
             sorted(operation._ACTIVE_RUN_STATUSES), int(run["task_id"]), sorted(operation._ACTIVE_RUN_STATUSES)),
        )
        if cur.fetchone():
            return True

        def account_time(field: str) -> datetime | None:
            try:
                value = datetime.fromisoformat(str(account.get(field) or "").replace("Z", "+00:00"))
                return value.astimezone(run["created_at"].tzinfo)
            except (TypeError, ValueError, OverflowError):
                return None

        queued_at = account_time("extract_link_queued_at")
        if expected_account_version is not None:
            if str(account["__record_version"]) != str(expected_account_version):
                return False
            # 排队已超时后，新 claim 可能先于新 Run 落库；即便快照版本一致也保留它。
            if queued_at is not None and queued_at > run["created_at"]:
                return False
        else:
            cutoff = min(run["created_at"], run["cancel_requested_at"]).replace(microsecond=0)
            if queued_at is None or queued_at >= cutoff:
                return False
            if str(account.get("extract_link_status") or "").lower() == "running":
                started_at = account_time("extract_link_started_at")
                if started_at is None or started_at >= cutoff:
                    return False
        now = datetime.now().isoformat(timespec="seconds")
        succeeded = bool(run["extraction_succeeded"])
        return record_store.patch_row(record_store.ACCOUNTS, account_id, {
            "extract_link_status": "success" if succeeded else "cancelled",
            "extract_link_ok": succeeded,
            "extract_link_error": None,
            "extract_link_message": "已保留提链成功结果" if succeeded else "用户取消提链任务",
            "extract_link_completed_at": now,
            "updated_at": now,
        }, conn=conn)


def normalize_filters(filters: dict | None) -> dict[str, str]:
    """只接受业务筛选字段，不把任意请求数据放入批次快照。"""
    if filters is None:
        filters = {}
    if not isinstance(filters, dict) or set(filters) - _FILTER_FIELDS:
        raise ValueError("账号筛选条件包含不支持的字段")
    result = {}
    for key in _FILTER_FIELDS:
        value = filters.get(key, "")
        if not isinstance(value, str):
            raise ValueError("账号筛选条件必须是文本")
        result[key] = value.strip()
    if len(result["query"]) > 200 or len(result["source"]) > 80:
        raise ValueError("账号搜索或邮箱来源过长")
    result["extract_status"] = result["extract_status"] or "not_succeeded"
    if result["extract_status"] not in _EXTRACT_STATUSES:
        raise ValueError("提链状态筛选无效")
    result["promotion"] = result["promotion"] or "eligible"
    if result["promotion"] not in _PROMOTION_FILTERS:
        raise ValueError("套餐优惠筛选无效")
    for key in ("date_from", "date_to"):
        if result[key]:
            try:
                parsed = date.fromisoformat(result[key])
            except ValueError as exc:
                raise ValueError("注册日期必须使用 YYYY-MM-DD 格式") from exc
            if parsed.isoformat() != result[key]:
                raise ValueError("注册日期必须使用 YYYY-MM-DD 格式")
    if result["date_from"] and result["date_to"] and result["date_from"] > result["date_to"]:
        raise ValueError("开始日期不能晚于结束日期")
    return result


def normalize_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_BATCH_SIZE:
        raise ValueError(f"本批数量必须在 1 至 {MAX_BATCH_SIZE} 之间")
    return limit


def normalize_workers(workers: int) -> int:
    """每批并发只接受整数，不把布尔值或小数隐式转为并发数。"""
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= MAX_BATCH_WORKERS:
        raise ValueError(f"本批并发必须在 1 至 {MAX_BATCH_WORKERS} 之间")
    return workers


def candidate_accounts(*, filters: dict | None = None, limit: int = 100, conn=None) -> dict:
    """在 SQL 中筛选可提链账号，只读取身份引用与安全列表字段。"""
    selected_filters = normalize_filters(filters)
    selected_limit = normalize_limit(limit)
    operation.init()
    where, params = admin_repository._account_where(
        "0", "free", selected_filters["query"], selected_filters["date_from"],
        selected_filters["date_to"], {"source": selected_filters["source"]},
    )
    where.extend((
        "a.deactivated IS FALSE",
        "a.account_has_access_token IS TRUE",
        "LOWER(COALESCE(a.extract_link_status, '')) NOT IN ('queued', 'running')",
        f"""NOT EXISTS (SELECT 1 FROM {operation._table('operation_runs')} active
            WHERE active.account_id=a.id AND active.resource_family='openai_interactive'
              AND active.status IN ('queued','running','waiting','cancelling','settling','stopping'))""",
    ))
    status = "LOWER(COALESCE(a.extract_link_status, ''))"
    requested_status = selected_filters["extract_status"]
    if requested_status == "not_succeeded":
        where.append(f"{status} <> 'success'")
    elif requested_status == "failed":
        where.append(f"{status} IN ('failed', 'request_unknown', 'stopped', 'cancelled')")
    elif requested_status == "never":
        where.append(f"{status} = ''")
    elif requested_status == "success":
        where.append(f"{status} = 'success'")
    if selected_filters["promotion"] == "eligible":
        where.append("a.account_promotion_value IN ('free_trial', 'half_price', 'other_discount', 'other_promo')")
    else:
        where.append("a.account_promotion_value=%s")
        params.append(selected_filters["promotion"])
    accounts = admin_repository._q(record_store.ACCOUNTS)
    clause = " AND ".join(where)
    with (admin_repository._connect() if conn is None else nullcontext(conn)) as selected_conn, selected_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM {accounts} a WHERE {clause}", tuple(params))
        total = int((cur.fetchone() or {}).get("total") or 0)
        cur.execute(
            f"""SELECT a.id AS account_id, a.email, a.created_at, a.email_source,
                       a.extract_link_status, a.account_promotion_value
                FROM {accounts} a WHERE {clause} ORDER BY a.id LIMIT %s""",
            (*params, selected_limit),
        )
        items = [dict(row) for row in cur.fetchall()]
    return {"total": total, "items": items, "filters": selected_filters, "limit": selected_limit}


def normalize_submission_id(value: str | None) -> str:
    """界面提交使用 UUID，旧的内部调用可以不提供。"""
    if value is None or value == "":
        return ""
    if not isinstance(value, str) or len(value) != 36:
        raise ValueError("批次提交标识必须是有效 UUID")
    try:
        normalized = str(uuid.UUID(value))
    except ValueError as exc:
        raise ValueError("批次提交标识必须是有效 UUID") from exc
    if normalized != value.lower():
        raise ValueError("批次提交标识必须是有效 UUID")
    return normalized


def _submission_result(cur, submission_id: str) -> dict | None:
    cur.execute(
        f"""SELECT b.id AS batch_id, b.requested_count AS requested,
                   COALESCE(b.data->>'submission_skipped', '0')::integer AS skipped,
                   COALESCE(b.data->>'submission_failed', '0')::integer AS failed,
                   (SELECT COUNT(*) FROM {operation._table('operation_tasks')} task
                    WHERE task.batch_id=b.id AND task.task_type='extract_link') AS started
            FROM {operation._table('operation_batches')} b
            WHERE b.source_system='native_operations' AND b.source_id=%s
              AND b.batch_type='extract_link' AND b.data->>'workbench_batch'='true'""",
        (f"extract-workbench-submission:{submission_id}",),
    )
    row = cur.fetchone()
    return {key: int(row[key] or 0) for key in ("batch_id", "requested", "started", "skipped", "failed")} if row else None


def submission_result(submission_id: str) -> dict | None:
    """响应丢失后的重试只读原批次，不再次筛选下一批账号。"""
    operation.init()
    with operation._connect() as conn, conn.cursor() as cur:
        return _submission_result(cur, submission_id)


def reserve_submission(*, submission_id: str, title: str, provider_id: str, mode: str,
                       link_type: str, filters: dict | None, limit: int, workers: int | None = None) -> dict:
    """锁定提交标识，原子保存候选快照与批次身份，再由提交者创建子任务。"""
    operation.init()
    with operation._connect() as conn, conn.cursor() as cur:
        record_store.advisory_xact_lock(conn, f"{operation._table('operation_batches')}:extract-submit:{submission_id}")
        existing = _submission_result(cur, submission_id)
        if existing is not None:
            return {"created": False, "result": existing}
        candidates = candidate_accounts(filters=filters, limit=limit, conn=conn)
        ids = [int(item["account_id"]) for item in candidates["items"]]
        if not ids:
            raise ValueError("当前筛选没有符合提链条件的账号")
        metadata = {
            "workbench_batch": True, "provider_id": provider_id, "mode": mode,
            "link_type": link_type, "filters": candidates["filters"], "limit": candidates["limit"],
            "submission_id": submission_id, "submission_account_ids": ids,
            "submission_complete": False,
            **({"workers": normalize_workers(workers)} if workers is not None else {}),
        }
        cur.execute(
            f"""INSERT INTO {operation._table('operation_batches')}
                (batch_uuid, source_system, source_id, batch_type, title, status,
                 requested_count, created_by, data)
                VALUES (%s, 'native_operations', %s, 'extract_link', %s, 'queued',
                        %s, 'extract_workbench_batch', %s::jsonb) RETURNING id""",
            (uuid.uuid4().hex, f"extract-workbench-submission:{submission_id}", title,
             len(ids), json.dumps(metadata, ensure_ascii=False)),
        )
        return {"created": True, "batch_id": int(cur.fetchone()["id"]), "account_ids": ids}


def batch_rows(*, page: int = 1, page_size: int = 20, batch_id: int | None = None) -> dict:
    """只读取提链工作台创建的批次，不载入其他业务的批次和任务事件。"""
    operation.init()
    where = ["b.batch_type='extract_link'", "b.source_system='native_operations'", "b.data->>'workbench_batch'='true'"]
    params = []
    if batch_id is not None:
        where.append("b.id=%s")
        params.append(int(batch_id))
    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))
    clause = " AND ".join(where)
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM {operation._table('operation_batches')} b WHERE {clause}", tuple(params))
        total = int((cur.fetchone() or {}).get("total") or 0)
        cur.execute(
            f"""SELECT b.id, b.title, b.status, b.requested_count, b.skipped_count,
                       b.created_at, jsonb_build_object(
                           'provider_id', b.data->'provider_id', 'mode', b.data->'mode',
                           'workers', b.data->'workers',
                           'submission_complete', b.data->'submission_complete',
                           'submission_skipped', b.data->'submission_skipped',
                           'submission_failed', b.data->'submission_failed'
                       ) AS data
                FROM {operation._table('operation_batches')} b WHERE {clause}
                ORDER BY b.created_at DESC, b.id DESC LIMIT %s OFFSET %s""",
            (*params, page_size, (page - 1) * page_size),
        )
        items = [operation._row(dict(row)) or {} for row in cur.fetchall()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def batch_task_counts(batch_ids: list[int]) -> dict[int, dict]:
    """按每个逻辑任务的最新 Run 聚合，不载入账号令牌、任务配置或历史 Run。"""
    if not batch_ids:
        return {}
    from core.storage.extract_link_jobs import _workbench_timestamp_sql

    operation.init()
    accounts = admin_repository._q(record_store.ACCOUNTS)
    checked_at_sql = _workbench_timestamp_sql("COALESCE(NULLIF(BTRIM(account.data->>'plan_checked_at'), ''), NULLIF(BTRIM(account.plan_last_success_at), ''), NULLIF(BTRIM(fallback.data->>'plan_checked_at'), ''), NULLIF(BTRIM(fallback.plan_last_success_at), ''))")
    with operation._connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""WITH raw AS (
                SELECT task.batch_id, task.created_at AS task_created_at,
                    LOWER(COALESCE(NULLIF(run.status, ''), NULLIF(task.status, ''), 'queued')) AS task_status,
                    COALESCE(NULLIF(task.data->>'provider_id', ''), NULLIF(job.provider_id, ''), 'legacy') AS provider_id,
                    COALESCE(NULLIF(task.data->>'mode', ''), 'extract_only') AS mode,
                    COALESCE(job.provider_id='huanguang'
                        AND job.public_state->'summary'->'local_reconcile_halted'='true'::jsonb, FALSE) AS local_reconcile_halted,
                    CASE WHEN job.provider_id='huanguang' AND job.public_state->'summary'->'extraction_ever_succeeded'='true'::jsonb
                        THEN 'succeeded' ELSE LOWER(COALESCE(NULLIF(job.public_state->>'extraction_state', ''),
                            NULLIF(run.result_summary->>'extraction_status', ''), '')) END AS extraction,
                    LOWER(COALESCE(NULLIF(job.public_state->>'payment_state', ''),
                        NULLIF(run.result_summary->>'payment_status', ''), 'not_started')) AS payment,
                    LOWER(COALESCE(NULLIF(job.public_state->>'plus_status', ''),
                        NULLIF(run.result_summary->>'plus_status', ''), 'unknown')) AS plus,
                    COALESCE((run.result_summary->>'has_link')::boolean, FALSE)
                        OR COALESCE(run.result_summary->>'remote_job_id', '') <> '' AS legacy_succeeded,
                    LOWER(COALESCE(account.plan_check_status, fallback.plan_check_status, '')) AS plan_check_status,
                    LOWER(COALESCE(NULLIF(account.current_plan_type, ''), account.plan_type,
                        NULLIF(fallback.current_plan_type, ''), fallback.plan_type, '')) AS plan,
                    {checked_at_sql} AS plan_checked_at
                FROM {operation._table('operation_tasks')} task
                LEFT JOIN {operation._table('operation_runs')} run ON run.id=task.last_run_id
                LEFT JOIN {operation._table('extract_link_provider_jobs')} job ON job.run_id=run.id
                LEFT JOIN {accounts} account ON account.id=task.account_id
                LEFT JOIN LATERAL (SELECT candidate.* FROM {accounts} candidate
                    WHERE account.id IS NULL AND BTRIM(task.email_snapshot) <> ''
                      AND LOWER(candidate.email)=LOWER(BTRIM(task.email_snapshot))
                    ORDER BY candidate.id LIMIT 1) fallback ON TRUE
                WHERE task.task_type='extract_link' AND task.batch_id=ANY(%s)
                  AND LOWER(COALESCE(task.data->>'deleted_by_user', '')) <> 'true'
            ), normalized AS (
                SELECT *, CASE
                    WHEN extraction IN ('succeeded', 'success') THEN 'success'
                    WHEN extraction IN ('queued', 'running', 'failed', 'pending', 'unknown', 'not_started') THEN extraction
                    WHEN extraction='' AND provider_id='legacy' AND task_status='success' AND legacy_succeeded THEN 'success'
                    WHEN extraction='' AND provider_id='legacy' AND task_status IN
                        ('failed','request_unknown','attention_required','cancelled','stopped') THEN 'failed'
                    WHEN extraction='' THEN 'pending' ELSE 'unknown' END AS extraction_status,
                    CASE WHEN mode='extract_only' THEN 'unpaid'
                        WHEN payment IN ('succeeded','success','paid') THEN 'paid'
                        WHEN payment='not_started' THEN 'unpaid'
                        WHEN payment='failed' THEN 'failed'
                        WHEN payment='unknown' THEN 'request_unknown'
                        ELSE 'pending_payment' END AS payment_status
                FROM raw
            ), projected AS (
                SELECT *, CASE WHEN mode IN ('auto_payment','manual_payment') AND extraction_status='success'
                    AND plan_check_status='success' AND BTRIM(plan) IN ('plus','pro') AND plan_checked_at > task_created_at
                    THEN 'confirmed'
                    ELSE plus END AS plus_status
                FROM normalized
            )
            SELECT batch_id, COUNT(*) AS all,
                COUNT(*) FILTER (WHERE NOT local_reconcile_halted AND (task_status IN ('queued','running','waiting','cancelling','settling','stopping')
                    OR (mode='auto_payment' AND payment_status='pending_payment'
                        AND task_status NOT IN ('attention_required','request_unknown','failed','cancelled','stopped','interrupted'))
                    OR (payment_status='paid' AND plus_status IN ('unknown','pending','queued')))) AS processing,
                COUNT(*) FILTER (WHERE NOT local_reconcile_halted AND task_status IN ('running','cancelling','settling','stopping')) AS running,
                COUNT(*) FILTER (WHERE extraction_status='success') AS extraction_succeeded,
                COUNT(*) FILTER (WHERE payment_status='paid') AS payment_succeeded,
                COUNT(*) FILTER (WHERE plus_status='confirmed') AS plus_confirmed,
                COUNT(*) FILTER (WHERE local_reconcile_halted OR task_status IN ('failed','request_unknown','cancelled','attention_required','partial_success','stopped','interrupted')
                    OR extraction_status IN ('unknown','failed') OR payment_status IN ('request_unknown','failed')
                    OR plus_status IN ('failed','not_confirmed') OR (payment_status='paid' AND plus_status='unknown')) AS needs_attention,
                COUNT(*) FILTER (WHERE task_status='success') AS task_succeeded,
                COUNT(*) FILTER (WHERE task_status='queued') AS task_queued
            FROM projected GROUP BY batch_id""",
            ([int(value) for value in batch_ids],),
        )
        return {int(row["batch_id"]): {key: int(value or 0) for key, value in row.items() if key != "batch_id"}
                for row in cur.fetchall()}


def finish_submission(batch_id: int, *, skipped: int, failed: int, complete: bool) -> int:
    """保存提交阶段计数；中断时保留事实，由实际子任务推导批次结果。"""
    operation.init()
    metadata = {"submission_skipped": int(skipped), "submission_failed": int(failed), "submission_complete": bool(complete)}
    with operation._connect() as conn, conn.cursor() as cur:
        operation._lock_projection_batch(cur, int(batch_id))
        cur.execute(
            f"""UPDATE {operation._table('operation_batches')}
                SET skipped_count=%s, data=data || %s::jsonb WHERE id=%s""",
            (int(skipped) + int(failed), json.dumps(metadata, ensure_ascii=False), int(batch_id)),
        )
        operation._refresh_batches(cur, [int(batch_id)])
        cur.execute(
            f"""UPDATE {operation._table('operation_batches')} b
                SET status='failed', completed_at=now()
                WHERE b.id=%s AND NOT EXISTS (
                    SELECT 1 FROM {operation._table('operation_batch_items')} item WHERE item.batch_id=b.id
                )""",
            (int(batch_id),),
        )
        cur.execute(
            f"SELECT COUNT(*) AS total FROM {operation._table('operation_tasks')} WHERE batch_id=%s AND task_type='extract_link'",
            (int(batch_id),),
        )
        return int((cur.fetchone() or {}).get("total") or 0)
