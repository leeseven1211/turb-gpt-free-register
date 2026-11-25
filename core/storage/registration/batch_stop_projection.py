"""停止历史未投影 Job 时，同事务补齐原有 Task/Run 映射。"""
from __future__ import annotations

import json

from core.operations.stages import normalize_stage
from core.storage import postgres, records
from core.storage.operations import common, projection


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def ensure_missing(cur, jobs: list[dict], accounts: list[dict]) -> set[int]:
    batches = set()
    ordered = sorted(jobs, key=lambda row: int(row["id"]))
    for offset in range(0, len(ordered), 500):
        batches.update(_ensure_chunk(cur, ordered[offset:offset + 500], accounts))
    return batches


def _ensure_chunk(cur, jobs: list[dict], accounts: list[dict]) -> set[int]:
    if not jobs:
        return set()
    ids = [str(row["id"]) for row in jobs]
    cur.execute(f"""SELECT source_id FROM {common._table('operation_runs')}
        WHERE source_system='registration_jobs' AND source_id=ANY(%s)""", (ids,))
    existing = {row["source_id"] for row in cur.fetchall()}
    missing = [row for row in jobs if str(row["id"]) not in existing]
    if not missing:
        return set()
    by_account = {row["id"]: row for row in accounts}
    by_email = {str(row.get("email") or "").strip().lower(): row for row in reversed(accounts)}
    facts = []
    for job in missing:
        ident, root_id = int(job["id"]), int(job.get("root_job_id") or job["id"])
        task_type = projection._registration_task_type(job)
        account = by_account.get(job.get("account_id")) or by_email.get(str(job.get("email") or "").strip().lower())
        state = common._account_state(account)
        created = common._legacy_registration_timestamp(job.get("created_at")) or common._now()
        completed = common._legacy_registration_timestamp(job.get("completed_at"))
        category, code, message = common._error_fields(
            job.get("error_message"), stage=str(job.get("progress_stage") or ""),
            task_type=task_type, task_status=common._status(job.get("status")),
        )
        snapshot = common._scrub(job.get("config_snapshot") or {})
        facts.append({
            "job_id": ident, "root_id": root_id, "task_type": task_type,
            "task_uuid": common._uuid("task", f"registration_chains:{root_id}:{task_type}"),
            "attempt_uuid": common._uuid("attempt", root_id),
            "run_uuid": common._uuid("run", f"registration_jobs:{ident}"),
            "account_id": (account or {}).get("id"),
            "email": str((account or {}).get("email") or job.get("email") or "")[:320],
            "batch_source": str(job.get("batch_id") or "").strip() or None,
            "batch_uuid": common._uuid("batch", f"registration_batches:{job.get('batch_id')}"),
            "batch_size": int(job.get("batch_size") or 1), "workers": job.get("batch_workers"),
            "status": common._status(job.get("status")), **state, "stage": normalize_stage(job.get("progress_stage")),
            "created_at": created, "started_at": common._legacy_registration_timestamp(job.get("started_at")),
            "completed_at": completed, "duration_ms": common._duration(job.get("started_at"), job.get("completed_at")),
            "error_category": category, "error_code": code, "error_message": message,
            "retry_attempt": int(job.get("retry_attempt") or 0),
            "log_file": str(job.get("log_file") or ""), "execution_id": job.get("job_uuid"),
            "trigger": "manual_retry" if job.get("parent_job_id") else "manual",
            "progress_steps": common._scrub(job.get("progress_steps") or {}),
            "task_data": {"legacy_root_job_id": root_id, "latest_legacy_job_id": ident,
                          "route_attempt_no": max(1, int(job.get("route_attempt_no") or 1)),
                          "selected_route_attempt_no": max(1, int(job.get("route_attempt_no") or 1)),
                          "config_snapshot": snapshot},
            "run_data": common._scrub({"legacy_job_id": ident, "parent_job_id": job.get("parent_job_id"),
                         "route_attempt_no": max(1, int(job.get("route_attempt_no") or 1)),
                         "selected_route_attempt_no": max(1, int(job.get("route_attempt_no") or 1)),
                         "route_attempts": job.get("route_attempts") or [], "failure_stage": job.get("failure_stage"),
                         "config_snapshot": snapshot}),
        })
    # One root can have several historical executions selected together.
    roots = {}
    for fact in sorted(facts, key=lambda row: row["job_id"]):
        roots.setdefault(fact["root_id"], fact)
    prior_numbers = {}
    for fact in sorted(facts, key=lambda row: (row["task_uuid"], row["job_id"])):
        fact["min_run_no"] = max(fact["retry_attempt"] + 1, prior_numbers.get(fact["task_uuid"], 0) + 1)
        prior_numbers[fact["task_uuid"]] = fact["min_run_no"]
    attempts = common._table("registration_attempts")
    attempt_root = "COALESCE(a.source_root_job_id,NULLIF(to_jsonb(a)->>'root_job_id','')::bigint)"
    cur.execute(f"""INSERT INTO {attempts}
        (attempt_uuid,source_root_job_id,email_snapshot,account_id,checkpoint,remote_identity_state,
         remote_account_state,local_account_state,target_status,created_at,updated_at,data)
        SELECT attempt_uuid,root_id,email,account_id,checkpoint,remote_identity_state,
               remote_account_state,local_account_state,target_status,created_at,now(),
               jsonb_build_object('legacy_root_job_id',root_id)
        FROM jsonb_to_recordset(%s::jsonb) f(attempt_uuid text,root_id bigint,email text,account_id bigint,
            checkpoint text,remote_identity_state text,remote_account_state text,local_account_state text,
            target_status text,created_at timestamptz)
        WHERE NOT EXISTS(SELECT 1 FROM {attempts} a WHERE {attempt_root}=f.root_id)
        ON CONFLICT (source_root_job_id) DO NOTHING""", (_json(list(roots.values())),))
    checkpoints = list(common._REGISTRATION_CHECKPOINTS)
    # Match the compatibility projector's one-way account facts when an old
    # Attempt exists but its Task/Run mapping does not.
    cur.execute(f"""UPDATE {attempts} a SET
        email_snapshot=COALESCE(NULLIF(f.email,''),a.email_snapshot),account_id=COALESCE(f.account_id,a.account_id),
        checkpoint=CASE WHEN COALESCE(array_position(%s::text[],a.checkpoint),0)>=
                             COALESCE(array_position(%s::text[],f.checkpoint),0)
                        THEN a.checkpoint ELSE f.checkpoint END,
        remote_identity_state=CASE WHEN a.remote_identity_state='confirmed' AND f.remote_identity_state<>'confirmed'
            OR a.remote_identity_state='request_unknown' AND f.remote_identity_state IN ('unknown','','not_started')
            OR f.remote_identity_state IN ('unknown','') THEN a.remote_identity_state ELSE f.remote_identity_state END,
        remote_account_state=CASE WHEN a.remote_account_state='confirmed' AND f.remote_account_state<>'confirmed'
            OR a.remote_account_state='request_unknown' AND f.remote_account_state IN ('unknown','','not_started')
            OR f.remote_account_state IN ('unknown','') THEN a.remote_account_state ELSE f.remote_account_state END,
        local_account_state=CASE WHEN a.local_account_state IN ('persisted','saved')
            AND f.local_account_state IN ('missing','checkpoint_saved') THEN a.local_account_state ELSE f.local_account_state END,
        target_status=CASE WHEN a.target_status='deactivated' THEN a.target_status
            WHEN a.target_status='request_unknown' AND (f.status NOT IN ('success','partial_success')
                OR f.target_status IN ('not_created','attention_required','request_unknown')) THEN a.target_status
            ELSE f.target_status END,
        updated_at=now(),completed_at=COALESCE(
            CASE WHEN f.target_status='account_available' THEN f.completed_at END,a.completed_at),
        data=a.data || jsonb_build_object('legacy_root_job_id',f.root_id)
        FROM jsonb_to_recordset(%s::jsonb) f(root_id bigint,email text,account_id bigint,checkpoint text,
            remote_identity_state text,remote_account_state text,local_account_state text,target_status text,
            status text,completed_at timestamptz)
        WHERE {attempt_root}=f.root_id""", (checkpoints, checkpoints, _json(list(roots.values()))))
    cur.execute(f"SELECT a.*,{attempt_root} AS resolved_root FROM {attempts} a WHERE {attempt_root}=ANY(%s)",
                (list(roots),))
    by_root = {int(row["resolved_root"]): dict(row) for row in cur.fetchall()}
    for fact, job in zip(facts, missing):
        attempt = by_root[fact["root_id"]]
        fact.update(attempt_id=attempt["id"], target_status=attempt["target_status"])
        fact["next_actions"] = projection._next_registration_actions(
            job, by_account.get(fact["account_id"]), attempt["target_status"],
            remote_identity_state=attempt["remote_identity_state"],
            remote_account_state=attempt["remote_account_state"],
        )
    batches = common._table("operation_batches")
    selected_batches = {}
    for fact in facts:
        if fact["batch_source"]:
            selected_batches.setdefault(fact["batch_source"], fact)
    cur.execute(f"""INSERT INTO {batches}
        (batch_uuid,source_system,source_id,batch_type,title,requested_count,created_by,created_at,data)
        SELECT batch_uuid,'registration_batches',batch_source,
               CASE WHEN task_type='registration' THEN 'registration' ELSE 'retry' END,
               CASE WHEN task_type='registration' THEN '注册批次' ELSE '注册补跑批次' END,
               batch_size,'webui',created_at,jsonb_build_object('legacy_batch_id',batch_source,'workers',workers)
        FROM jsonb_to_recordset(%s::jsonb) f(batch_uuid text,batch_source text,task_type text,batch_size integer,
            workers integer,created_at timestamptz)
        ON CONFLICT (source_system,source_id) DO NOTHING""", (_json(list(selected_batches.values())),))
    cur.execute(f"""SELECT id,source_id FROM {batches} WHERE source_system='registration_batches'
        AND source_id=ANY(%s)""", (list(selected_batches),))
    batch_ids = {row["source_id"]: row["id"] for row in cur.fetchall()}
    for fact in facts:
        fact["batch_id"] = batch_ids.get(fact["batch_source"])
    tasks = common._table("operation_tasks")
    task_facts = {}
    for fact in facts:
        task_facts[fact["task_uuid"]] = fact
    cur.execute(f"""INSERT INTO {tasks} AS task
        (task_uuid,source_system,source_id,batch_id,task_type,target_type,target_id,attempt_id,account_id,
         email_snapshot,requested_action,status,target_status,current_stage,next_actions,
         error_category,error_code,error_message,trigger,created_at,updated_at,completed_at,data)
        SELECT task_uuid,'registration_chains',root_id::text || ':' || task_type,batch_id,task_type,
               CASE WHEN task_type IN ('codex_retry','twofa_retry') AND account_id IS NOT NULL
                    THEN 'account' ELSE 'registration_attempt' END,
               CASE WHEN task_type IN ('codex_retry','twofa_retry') AND account_id IS NOT NULL
                    THEN account_id ELSE attempt_id END,
               attempt_id,account_id,email,task_type,status,target_status,stage,next_actions,
               error_category,error_code,error_message,trigger,created_at,now(),completed_at,task_data
        FROM jsonb_to_recordset(%s::jsonb) f(task_uuid text,root_id bigint,task_type text,batch_id bigint,
            account_id bigint,attempt_id bigint,email text,status text,target_status text,stage text,
            next_actions jsonb,error_category text,error_code text,error_message text,trigger text,
            created_at timestamptz,completed_at timestamptz,task_data jsonb)
        ON CONFLICT (source_system,source_id) DO UPDATE SET
            batch_id=COALESCE(EXCLUDED.batch_id,task.batch_id),attempt_id=EXCLUDED.attempt_id,
            account_id=COALESCE(EXCLUDED.account_id,task.account_id),
            email_snapshot=COALESCE(NULLIF(EXCLUDED.email_snapshot,''),task.email_snapshot),
            target_status=EXCLUDED.target_status,data=task.data || EXCLUDED.data,
            updated_at=now()""", (_json(list(task_facts.values())),))
    cur.execute(f"""SELECT id,task_uuid FROM {tasks} WHERE task_uuid=ANY(%s)""", (list(task_facts),))
    task_ids = {row["task_uuid"]: row["id"] for row in cur.fetchall()}
    for fact in facts:
        fact["task_id"] = task_ids[fact["task_uuid"]]
    cur.execute(f"""UPDATE {tasks} task
        SET parent_task_id=CASE WHEN task.task_type='registration' THEN task.parent_task_id
                               ELSE COALESCE(parent.id,task.parent_task_id) END,
            root_task_id=CASE WHEN task.task_type='registration' THEN task.id ELSE COALESCE(parent.id,task.id) END
        FROM jsonb_to_recordset(%s::jsonb) f(task_id bigint,root_id bigint)
        LEFT JOIN {tasks} parent ON parent.source_system='registration_chains'
             AND parent.source_id=f.root_id::text || ':registration'
        WHERE task.id=f.task_id AND (task.task_type<>'registration' OR task.root_task_id IS NULL)""", (_json(facts),))
    cur.execute(f"""UPDATE {attempts} a SET root_task_id=f.task_id
        FROM jsonb_to_recordset(%s::jsonb) f(task_id bigint,attempt_id bigint,task_type text)
        WHERE a.id=f.attempt_id AND f.task_type='registration'""", (_json(facts),))
    if common._schema_name() == postgres.schema_name():
        cur.execute(f"""UPDATE {records._qualified(records.JOBS)} job SET attempt_id=f.attempt_id
            FROM jsonb_to_recordset(%s::jsonb) f(job_id bigint,attempt_id bigint)
            WHERE job.id=f.job_id AND job.attempt_id IS NULL""", (_json(facts),))
    cur.execute(f"""INSERT INTO {common._table('operation_runs')}
            (run_uuid,task_id,run_no,source_system,source_id,status,execution_id,progress_stage,progress_steps,
             started_at,completed_at,duration_ms,error_category,error_code,error_message,result_summary,
             log_file,created_at,data)
        SELECT run_uuid,task_id,GREATEST(min_run_no,COALESCE(prior.max_no,0)+rank),
               'registration_jobs',job_id::text,status,execution_id,stage,progress_steps,started_at,completed_at,
               duration_ms,error_category,error_code,error_message,jsonb_build_object('account_id',account_id),
               log_file,created_at,run_data FROM (
            SELECT f.*,row_number() OVER (PARTITION BY task_id ORDER BY job_id)::int AS rank
            FROM jsonb_to_recordset(%s::jsonb) f(run_uuid text,task_id bigint,min_run_no integer,job_id bigint,
                status text,execution_id text,stage text,progress_steps jsonb,started_at timestamptz,
                completed_at timestamptz,duration_ms bigint,error_category text,error_code text,error_message text,
                account_id bigint,log_file text,created_at timestamptz,run_data jsonb)
        ) f LEFT JOIN LATERAL (
            SELECT MAX(run_no) AS max_no FROM {common._table('operation_runs')} old WHERE old.task_id=f.task_id
        ) prior ON TRUE
        ON CONFLICT (source_system,source_id) DO NOTHING""", (_json(facts),))
    cur.execute(f"""WITH current AS (
        SELECT DISTINCT ON(task_id) id,task_id,status,current_stage,completed_at,
            error_category,error_code,error_message FROM (
            SELECT id,task_id,status,progress_stage AS current_stage,completed_at,run_no,
                error_category,error_code,error_message
            FROM {common._table('operation_runs')} WHERE task_id=ANY(%s)
        ) selected ORDER BY task_id,(status=ANY(%s)) DESC,run_no DESC,id DESC
    ) UPDATE {tasks} task SET last_run_id=current.id,status=current.status,
        current_stage=current.current_stage,completed_at=current.completed_at,
        error_category=current.error_category,error_code=current.error_code,error_message=current.error_message,
        next_actions=CASE WHEN current.status=ANY(%s) THEN '[]'::jsonb ELSE task.next_actions END
      FROM current WHERE task.id=current.task_id""",
      (sorted(set(task_ids.values())), ["queued", "running", "cancelling", "settling"],
       list(common._ACTIVE_RUN_STATUSES)))
    _progress_events(cur, facts, {int(job["id"]): job for job in missing})
    return set(batch_ids.values())


def _progress_events(cur, facts: list[dict], jobs: dict[int, dict]) -> None:
    events = {}
    for fact in facts:
        for raw_stage, current in (jobs[fact["job_id"]].get("progress_steps") or {}).items():
            current = current if isinstance(current, dict) else {}
            steps = [dict(row) for row in current.get("transitions") or [] if isinstance(row, dict)]
            if not steps or current.get("transition_id") not in {row.get("transition_id") for row in steps}:
                steps.append(current)
            for step in steps:
                state, stage = str(step.get("state") or "pending"), normalize_stage(raw_stage)
                level = "ERROR" if state in {"failed", "stopped"} else "INFO"
                category, code, _ = common._error_fields(
                    step.get("detail") if level == "ERROR" else None, stage=stage, task_type=fact["task_type"],
                )
                transition = str(step.get("transition_id") or "")
                source_system = "registration_progress_events" if transition else "registration_progress"
                source_id = f"{fact['job_id']}:stage:{raw_stage}" + (f":{transition}" if transition else "")
                occurred = common._registration_progress_occurrence(step, state)
                events[source_system, source_id] = {
                    "job_id": fact["job_id"], "task_id": fact["task_id"],
                    "event_uuid": transition or common._uuid("event", f"registration_progress:{source_id}"),
                    "source_system": source_system, "source_id": source_id,
                    "created_at": occurred or common._legacy_registration_timestamp(step.get("started_at"))
                                  or fact["created_at"],
                    "level": level, "stage": stage, "event_type": f"stage.{state}",
                    "error_category": category, "error_code": code,
                    "message": common._text(step.get("detail") or state, 1200),
                    "detail": common._scrub({"state": state, "step_state": state, "raw_stage": raw_stage,
                               "started_at": step.get("started_at"), "completed_at": step.get("completed_at"),
                               "occurred_at": step.get("occurred_at"), "event_time_known": occurred is not None,
                               "evidence": step.get("evidence") or "legacy_derived",
                               "route_attempt_no": step.get("route_attempt_no"),
                               "step_instance_id": step.get("step_instance_id") or step.get("transition_id")}),
                }
    if events:
        rows = list(events.values())
        for offset in range(0, len(rows), 500):
            _insert_events(cur, rows[offset:offset + 500])


def _insert_events(cur, events: list[dict]) -> None:
        cur.execute(f"""INSERT INTO {common._table('operation_events')} AS event
            (event_uuid,task_id,run_id,source_system,source_id,created_at,level,stage,event_type,
             error_category,error_code,message,detail)
            SELECT f.event_uuid,f.task_id,run.id,f.source_system,f.source_id,f.created_at,f.level,
                   f.stage,f.event_type,f.error_category,f.error_code,f.message,f.detail
            FROM jsonb_to_recordset(%s::jsonb) f(event_uuid text,task_id bigint,job_id bigint,source_system text,
                source_id text,created_at timestamptz,level text,stage text,event_type text,
                error_category text,error_code text,message text,detail jsonb)
            JOIN {common._table('operation_runs')} run ON run.source_system='registration_jobs'
                AND run.source_id=f.job_id::text
            ON CONFLICT (source_system,source_id) DO UPDATE SET
                task_id=EXCLUDED.task_id,run_id=EXCLUDED.run_id,
                created_at=CASE WHEN EXCLUDED.detail->>'event_time_known'='true'
                    THEN EXCLUDED.created_at ELSE event.created_at END,
                level=EXCLUDED.level,stage=EXCLUDED.stage,event_type=EXCLUDED.event_type,
                error_category=EXCLUDED.error_category,error_code=EXCLUDED.error_code,
                message=EXCLUDED.message,detail=EXCLUDED.detail""", (_json(events),))
