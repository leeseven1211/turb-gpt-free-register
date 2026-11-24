"""Persist a new registration batch before making it visible to dispatch."""
from __future__ import annotations

import json
import uuid

from core import db
from core.operations.stages import normalize_stage
from core.storage import postgres, records, registration
from core.storage.operations import common, projection, schema


_CHUNK_SIZE = 500


def create_jobs(
    *,
    count: int,
    email_source: str,
    batch_id: str,
    workers: int,
    config_snapshot: dict,
    debug_enabled: bool,
) -> list[dict]:
    """Create ordered jobs, registration facts and task-center projections together."""
    if count <= 0:
        return []
    registration.init()
    schema.init_operation_schema()
    result = []
    same_schema = postgres.schema_name() == common._schema_name()
    projection_config = _json(common._scrub(config_snapshot))
    run_config = _json(registration._json_value({
        "config_snapshot": config_snapshot, "registration_dispatch_ready": False,
    }))
    # Bound each statement and intermediate payload, while keeping the existing
    # route's all-or-nothing visibility and a single projection/dispatcher wake.
    with records.transaction() as conn, conn.cursor() as cur:
        operation_batch = projection._upsert_batch(
            cur, source_system="registration_batches", source_id=batch_id,
            batch_type="registration", title="注册批次", requested_count=count, created_by="webui",
            created_at=common._now(),
            data={"legacy_batch_id": batch_id, "workers": workers},
        )
        for first_index in range(1, count + 1, _CHUNK_SIZE):
            result.extend(_create_chunk(
                cur, operation_batch=operation_batch, first_index=first_index,
                last_index=min(count, first_index + _CHUNK_SIZE - 1), count=count,
                email_source=email_source, batch_id=batch_id, workers=workers,
                config_snapshot=config_snapshot, debug_enabled=debug_enabled,
                projection_config=projection_config, run_config=run_config, same_schema=same_schema,
            ))
        projection._enqueue_batch_projection_cur(
            cur, operation_batch, reason="registration_job_updated",
            source_system="registration_jobs", source_id=str(result[-1]["id"]),
        )
    return result


def _create_chunk(
    cur, *, operation_batch: int, first_index: int, last_index: int, count: int,
    email_source: str, batch_id: str, workers: int, config_snapshot: dict,
    debug_enabled: bool, projection_config: str, run_config: str, same_schema: bool,
) -> list[dict]:
    jobs = postgres.qualified(records.JOBS.name)
    attempts = postgres.qualified("registration_attempts")
    tasks = common._table("operation_tasks")
    runs = common._table("operation_runs")
    rows = []
    columns = {}
    for index in range(first_index, last_index + 1):
        row = db._new_job_row(
            email_source=email_source, batch_id=batch_id, batch_index=index,
            batch_size=count, batch_workers=workers,
            data={"config_snapshot": dict(config_snapshot), "registration_dispatch_ready": False},
        )
        row["updated_at"] = row["created_at"]
        if debug_enabled:
            row.update(
                debug_enabled=True, debug_state="pending",
                debug_policy={
                    "capture_network": True, "hold_on_failure": True,
                    "preserve_success_browser": False,
                },
            )
        promoted, data = records._split(records.JOBS, row, partial=False)
        columns = {key: records.JOBS.promoted[key].split()[0] for key in promoted}
        rows.append({**promoted, "data": data})
    names = ", ".join(postgres.quote_identifier(name) for name in (*columns, "data"))
    record_type = ", ".join(f"{postgres.quote_identifier(name)} {kind}" for name, kind in columns.items())
    cur.execute(
        f"""INSERT INTO {jobs} ({names})
            SELECT {names} FROM jsonb_to_recordset(%s::jsonb) AS source({record_type}, data jsonb)
            ORDER BY (source.data->>'batch_index')::int
            RETURNING id,data,created_at,job_uuid""",
        (_json(rows),),
    )
    inserted = sorted(cur.fetchall(), key=lambda item: item["data"]["batch_index"])
    facts = [
        {
            "job_id": row["id"],
            "job_uuid": row["job_uuid"],
            "created_at": row["created_at"],
            "log_file": row["data"]["log_file"],
            "attempt_uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"turb-registration-attempt:{row['id']}")),
            "projection_attempt_uuid": common._uuid("attempt", row["id"]),
            "registration_run_uuid": str(uuid.uuid4()),
            "task_uuid": common._uuid("task", f"registration_chains:{row['id']}:registration"),
            "run_uuid": common._uuid("run", f"registration_jobs:{row['id']}"),
        }
        for row in inserted
    ]
    payload = _json(facts)
    cur.execute(
        f"""INSERT INTO {attempts}
                (attempt_uuid,source_root_job_id,root_job_id,email_source,checkpoint,
                 remote_identity_state,remote_account_state,local_account_state,target_status,data)
            SELECT attempt_uuid,job_id,job_id,%s,'created','not_started','not_started','none',%s,
                   jsonb_build_object('legacy_root_job_id', job_id) || %s::jsonb
            FROM jsonb_to_recordset(%s::jsonb) AS f(job_id bigint,attempt_uuid text)""",
        (email_source, "not_created" if same_schema else "pending", run_config, payload),
    )
    cur.execute(
        f"""INSERT INTO {postgres.qualified('registration_runs')}
                (run_uuid,attempt_id,job_id,run_no,action_type,status,heartbeat_at,data)
            SELECT f.registration_run_uuid,a.id,f.job_id,1,'registration','queued',now(),%s::jsonb
            FROM jsonb_to_recordset(%s::jsonb) AS f(job_id bigint,registration_run_uuid text)
            JOIN {attempts} a ON a.source_root_job_id=f.job_id""",
        (run_config, payload),
    )
    operation_attempts = common._table("registration_attempts")
    if not same_schema:
        cur.execute(
            f"""INSERT INTO {operation_attempts}
                    (attempt_uuid,source_root_job_id,checkpoint,remote_identity_state,
                     remote_account_state,local_account_state,target_status,created_at,updated_at,data)
                SELECT projection_attempt_uuid,job_id,'created','not_started','not_started','none',
                       'not_created',created_at,created_at,jsonb_build_object('legacy_root_job_id',job_id)
                FROM jsonb_to_recordset(%s::jsonb)
                     AS f(job_id bigint,projection_attempt_uuid text,created_at timestamptz)""",
            (payload,),
        )
    stage = normalize_stage(None)
    cur.execute(
        f"""INSERT INTO {tasks}
                (task_uuid,source_system,source_id,batch_id,task_type,target_type,target_id,
                 attempt_id,requested_action,status,target_status,current_stage,created_at,updated_at,data)
            SELECT f.task_uuid,'registration_chains',f.job_id::text || ':registration',%s,
                   'registration','registration_attempt',a.id,a.id,'registration','queued',
                   'not_created',%s,f.created_at,f.created_at,
                   jsonb_build_object('legacy_root_job_id',f.job_id,'latest_legacy_job_id',f.job_id,
                                      'route_attempt_no',1,'selected_route_attempt_no',1,
                                      'config_snapshot',%s::jsonb)
            FROM jsonb_to_recordset(%s::jsonb) AS f(job_id bigint,task_uuid text,created_at timestamptz)
            JOIN {operation_attempts} a ON a.source_root_job_id=f.job_id""",
        (operation_batch, stage, projection_config, payload),
    )
    cur.execute(
        f"""INSERT INTO {runs}
                (run_uuid,task_id,run_no,source_system,source_id,status,execution_id,
                 progress_stage,result_summary,log_file,created_at,data)
            SELECT f.run_uuid,t.id,1,'registration_jobs',f.job_id::text,'queued',f.job_uuid,
                   %s,'{{"account_id":null,"retry_action":null}}'::jsonb,f.log_file,f.created_at,
                   jsonb_build_object('legacy_job_id',f.job_id,'parent_job_id',null,
                                      'route_attempt_no',1,'selected_route_attempt_no',1,
                                      'route_attempts','[]'::jsonb,'failure_stage',null,
                                      'config_snapshot',%s::jsonb)
            FROM jsonb_to_recordset(%s::jsonb)
                 AS f(job_id bigint,job_uuid text,task_uuid text,run_uuid text,log_file text,created_at timestamptz)
            JOIN {tasks} t ON t.task_uuid=f.task_uuid""",
        (stage, projection_config, payload),
    )
    cur.execute(
        f"""WITH linked AS (
                UPDATE {tasks} t SET root_task_id=t.id,last_run_id=r.id
                FROM {runs} r
                WHERE t.batch_id=%s AND r.task_id=t.id AND r.source_system='registration_jobs'
                     AND r.source_id=ANY(%s)
                RETURNING t.id,t.attempt_id
            )
            UPDATE {operation_attempts} a SET root_task_id=linked.id
            FROM linked WHERE a.id=linked.attempt_id""",
        (operation_batch, [str(row["id"]) for row in inserted]),
    )
    cur.execute(
        f"""UPDATE {jobs} j SET attempt_id=a.id,
                data=j.data || '{{"registration_dispatch_ready":true,"registration_account_task_id":null}}'::jsonb
            FROM {attempts} a
            WHERE j.id = ANY(%s) AND a.source_root_job_id=j.id
            RETURNING j.*""",
        ([row["id"] for row in inserted],),
    )
    merged = [records.merge_row(records.JOBS, row) for row in cur.fetchall()]
    return sorted(merged, key=lambda item: item["batch_index"])


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
