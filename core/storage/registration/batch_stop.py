"""注册批次本地停止标记的集合更新，运行中的资源由原 Worker 收尾。"""
from __future__ import annotations

from core.storage import postgres, records


def retained_sources(addresses: list[str]) -> dict[str, str]:
    """旧 Job 缺来源时一次读取各本地归属，再按原解析优先级纯内存选择。"""
    from core.email import provider
    from core.email.inventory import TABLES
    from core.storage.email import provider_orders

    emails = sorted({str(value or "").strip().lower() for value in addresses if str(value or "").strip()})
    if not emails:
        return {}
    records.init()
    provider_orders.init()
    pools = [
        f"SELECT lower(email) AS email,%s::text AS source,{index + 3} AS priority,id "
        f"FROM {records._qualified(table)} WHERE lower(email)=ANY(%s)"
        for index, table in enumerate(TABLES.values())
    ]
    params = []
    for source in TABLES:
        params.extend((source, emails))
    with records.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT address_norm AS email,source,0 AS priority,id
            FROM {records._qualified(records.EMAIL_ADDRESS_ALLOCATIONS)}
            WHERE address_norm=ANY(%s) AND split_part(address_norm,'@',1) LIKE '%%+%%'
            UNION ALL SELECT lower(email),email_source,1,id FROM {records._qualified(records.ACCOUNTS)}
            WHERE lower(email)=ANY(%s)
            UNION ALL SELECT address_norm,source,2,id FROM {records._qualified(records.LOCAL_EMAIL_CLAIMS)}
            WHERE address_norm=ANY(%s)
            UNION ALL {' UNION ALL '.join(pools)}""", (emails, emails, emails, *params))
        rows = list(cur.fetchall())
        cur.execute(f"""SELECT lower(email) AS email,min(provider) AS source
            FROM {postgres.qualified('mail_provider_orders')} WHERE lower(email)=ANY(%s)
            GROUP BY lower(email) HAVING count(DISTINCT provider)=1""", (emails,))
        durable = {row["email"]: row["source"] for row in cur.fetchall()}
    candidates = {}
    latest_account_ids = {}
    for row in rows:
        if row["priority"] == 1:
            latest_account_ids[row["email"]] = max(latest_account_ids.get(row["email"], 0), int(row["id"]))
    for row in rows:
        if row["priority"] == 1 and int(row["id"]) != latest_account_ids[row["email"]]:
            continue
        raw = str(row["source"] or "").strip()
        if row["priority"] == 1:
            raw = raw.replace(";", ",").replace("|", ",").split(",", 1)[0].strip()
        try:
            source = provider.validate_email_source(raw)
        except ValueError:
            continue
        candidates.setdefault(row["email"], []).append((row["priority"], -int(row["id"]), source))
    getters = []
    for source, module_name in (
        ("gptmail", "core.email.gptmail.client"), ("cloudflare", "core.email.cloudflare.client"),
        ("email_butler", "core.email.email_butler.client"), ("mailnest", "core.email.mailnest.client"),
        ("cloudmail", "core.email.cloudmail.client"), ("remail", "core.email.remail.client"),
    ):
        module = __import__(module_name, fromlist=["get_account_context"])
        getters.append((source, module.get_account_context))
    result = {}
    for email in emails:
        if email in candidates:
            result[email] = min(candidates[email])[2]
            continue
        source = provider._EMAIL_SOURCE_HINTS.get(email) or durable.get(email)
        if source:
            result[email] = source
            continue
        source = next((name for name, getter in getters if getter(email)), None)
        if not source:
            from config import email as email_config

            domain = str(email_config.EMAIL_DOMAIN or "").lower().strip()
            source = "cloudflare_domain" if domain and domain != "-" and email.endswith("@" + domain) else provider.parse_email_sources()[0]
        result[email] = source
    return result


def request_stops(job_ids: list[int], *, active_job_ids: set[int], now_iso: str) -> dict[int, dict]:
    if not job_ids:
        return {}
    from core.storage.operations import common, projection, schema
    from core.storage.registration.bulk_submission import _json

    records.init()
    schema.init_operation_schema()
    with records.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""SELECT DISTINCT task.batch_id FROM {common._table('operation_tasks')} task
                JOIN {common._table('operation_runs')} run ON run.task_id=task.id
                WHERE run.source_system='registration_jobs' AND run.source_id=ANY(%s)
                  AND task.batch_id IS NOT NULL
                UNION SELECT batch.id FROM {common._table('operation_batches')} batch
                JOIN {records._qualified(records.JOBS)} job ON job.batch_id=batch.source_id
                WHERE batch.source_system='registration_batches' AND job.id=ANY(%s)""",
                ([str(ident) for ident in job_ids], job_ids))
            batches = sorted(row["batch_id"] for row in cur.fetchall())
            cur.execute(f"""INSERT INTO {common._table('operation_projection_queue')}
                (batch_id,reason,source_system,status,requested_at,available_at)
                SELECT id,'registration_job_updated','registration_jobs','queued',now(),now()
                FROM {common._table('operation_batches')} WHERE id=ANY(%s) ORDER BY id
                ON CONFLICT (batch_id) DO NOTHING""", (batches,))
            cur.execute(f"""SELECT batch_id FROM {common._table('operation_projection_queue')}
                WHERE batch_id=ANY(%s) ORDER BY batch_id FOR UPDATE""", (batches,))
            cur.fetchall()
            cur.execute(f"""SELECT id FROM {common._table('operation_batches')}
                WHERE id=ANY(%s) ORDER BY id FOR NO KEY UPDATE""", (batches,))
            cur.fetchall()
            cur.execute(f"SELECT * FROM {records._qualified(records.JOBS)} WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
                        (job_ids,))
            rows = [records.merge_row(records.JOBS, row) for row in cur.fetchall()]
        by_id = {int(row["id"]): row for row in rows}
        live = [ident for ident, row in by_id.items()
                if row.get("status") in ("running", "stopping") and ident in active_job_ids]
        orphaned = [ident for ident, row in by_id.items()
                    if row.get("status") in ("running", "stopping") and ident not in active_job_ids]
        changed = {}
        if live:
            changed.update({int(row["id"]): row for row in records.patch_rows_where_returning(
                records.JOBS, changes={"status": "stopping", "error_message": "用户手动停止中"},
                where="id=ANY(%s) AND status='running'", params=(live,), conn=conn,
            )})
        if orphaned:
            changed.update({int(row["id"]): row for row in records.patch_rows_where_returning(
                records.JOBS, changes={
                    "status": "stopped", "completed_at": now_iso, "error_message": "用户手动停止（任务实例不存在）",
                },
                where="id=ANY(%s) AND status IN ('running','stopping')", params=(orphaned,), conn=conn,
            )})
        for ident, row in by_id.items():
            if ident in changed:
                row.update(changed[ident])
            row["_stop_changed"] = ident in changed
        # Keep the compatibility Task/Run projection coherent in the same
        # transaction without reopening per-Job read/write boundaries.
        if changed:
            with conn.cursor() as cur:
                emails = sorted({str(row.get("email") or "").strip().lower() for row in changed.values()
                                 if row.get("email")})
                account_ids = sorted({int(row["account_id"]) for row in changed.values() if row.get("account_id")})
                cur.execute(f"""SELECT * FROM {records._qualified(records.ACCOUNTS)}
                    WHERE id=ANY(%s) OR lower(email)=ANY(%s) ORDER BY id DESC""", (account_ids, emails))
                accounts = [records.merge_row(records.ACCOUNTS, row) for row in cur.fetchall()]
                by_account = {row["id"]: row for row in accounts}
                by_email = {str(row.get("email") or "").strip().lower(): row for row in accounts}
                from core.storage.registration.batch_stop_projection import ensure_missing

                batches = sorted(set(batches) | ensure_missing(cur, list(changed.values()), accounts))
                cur.execute(f"""SELECT run.id AS run_id,run.source_id,task.id AS task_id,task.task_type,
                           attempt.target_status,attempt.remote_identity_state,attempt.remote_account_state
                    FROM {common._table('operation_runs')} run
                    JOIN {common._table('operation_tasks')} task ON task.id=run.task_id
                    LEFT JOIN {common._table('registration_attempts')} attempt ON attempt.id=task.attempt_id
                    WHERE run.source_system='registration_jobs' AND run.source_id=ANY(%s)""",
                    ([str(ident) for ident in sorted(changed)],))
                facts = []
                for selected in cur.fetchall():
                    job = by_id[int(selected["source_id"])]
                    account = by_account.get(job.get("account_id")) or by_email.get(
                        str(job.get("email") or "").strip().lower())
                    state = dict(selected) if selected.get("target_status") else common._account_state(account)
                    category, code, message = common._error_fields(
                        job.get("error_message"), stage=str(job.get("progress_stage") or ""),
                        task_type=selected["task_type"], task_status=common._status(job.get("status")),
                    )
                    facts.append({
                        "run_id": selected["run_id"], "task_id": selected["task_id"],
                        "error_category": category, "error_code": code, "error_message": message,
                        "next_actions": projection._next_registration_actions(
                            job, account, state["target_status"],
                            remote_identity_state=state["remote_identity_state"],
                            remote_account_state=state["remote_account_state"],
                        ),
                    })
                for offset in range(0, len(facts), 500):
                    payload = _json(facts[offset:offset + 500])
                    cur.execute(f"""UPDATE {common._table('operation_runs')} run
                    SET status=job.status,
                        completed_at=CASE WHEN job.status='stopped' THEN %s::timestamptz ELSE run.completed_at END,
                        error_message=f.error_message,error_category=f.error_category,error_code=f.error_code
                    FROM {records._qualified(records.JOBS)} job,
                         jsonb_to_recordset(%s::jsonb) f(run_id bigint,error_message text,error_category text,error_code text)
                    WHERE run.id=f.run_id AND run.source_id=job.id::text""", (now_iso, payload))
                    cur.execute(f"""UPDATE {common._table('operation_tasks')} task
                    SET status=run.status,completed_at=run.completed_at,error_message=f.error_message,
                        error_category=f.error_category,error_code=f.error_code,next_actions=f.next_actions,updated_at=now()
                    FROM {common._table('operation_runs')} run,
                         jsonb_to_recordset(%s::jsonb) f(run_id bigint,task_id bigint,error_message text,
                             error_category text,error_code text,next_actions jsonb)
                    WHERE task.last_run_id=run.id AND run.id=f.run_id AND task.id=f.task_id""", (payload,))
                cur.execute(f"""WITH dirty AS (
                    INSERT INTO {common._table('operation_projection_queue')} AS queue
                        (batch_id,reason,source_system,status,requested_at,available_at)
                    SELECT id,'registration_job_updated','registration_jobs','queued',now(),now()
                    FROM {common._table('operation_batches')} WHERE id=ANY(%s) ORDER BY id
                    ON CONFLICT (batch_id) DO UPDATE SET requested_at=now(),updated_at=now(),
                        status=CASE WHEN queue.status='running' THEN 'running' ELSE 'queued' END,
                        dirty=queue.status='running',
                        available_at=CASE WHEN queue.status='running' THEN queue.available_at ELSE now() END,
                        completed_at=CASE WHEN queue.status='running' THEN queue.completed_at END,
                        last_error=CASE WHEN queue.status='running' THEN queue.last_error END
                    RETURNING batch_id
                ) UPDATE {common._table('operation_batches')} batch
                  SET projection_status=CASE WHEN batch.projection_status='running' THEN 'running' ELSE 'queued' END,
                      projection_requested_at=now(),projection_next_retry_at=NULL,
                      projection_error=CASE WHEN batch.projection_status='running' THEN batch.projection_error END
                  FROM dirty WHERE batch.id=dirty.batch_id""", (batches,))
        return by_id
