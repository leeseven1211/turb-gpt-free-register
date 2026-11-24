"""Admit validated registration retries under the same fences as the single-item path."""
from __future__ import annotations

from dataclasses import dataclass
import uuid

from core import db
from core.operations.stages import normalize_stage
from core.storage import postgres, records, registration
from core.storage.operations import common, schema
from core.storage.registration.bulk_submission import _json


@dataclass(frozen=True)
class RetryAdmission:
    source: dict
    root: dict
    attempt: dict | None
    action: str
    email: str | None
    email_source: str
    account: dict | None
    batch_id: str | None
    batch_index: int | None
    batch_size: int | None
    workers: int
    config_snapshot: dict
    debug_enabled: bool

    @property
    def source_id(self) -> int:
        return int(self.source['id'])

    @property
    def root_id(self) -> int:
        return int(self.root['id'])

    @property
    def account_id(self) -> int | None:
        return int(self.account['id']) if self.account and self.account.get('id') is not None else None


_TERMINAL = ('success', 'failed', 'partial_success', 'stopped', 'cancelled', 'interrupted',
             'request_unknown', 'manual_reconcile')
_ACTIVE = ('pending', 'running', 'stopping')
_CHANGED = '原注册任务状态或身份已变化，请刷新后重试'


def _error(message: str, status: int = 409) -> dict:
    return {'ok': False, 'error': message, 'status': status}


def _advisory_locks(cur, keys: list[str]) -> None:
    if keys:
        cur.execute('''SELECT pg_advisory_xact_lock(hashtextextended(key, 0))
                       FROM (SELECT unnest(%s::text[]) AS key ORDER BY 1) AS ordered''', (keys,))


def _normalized_address(address) -> str:
    return str(address or '').strip().lower()


def _deleted_addresses(cur, addresses: list[str]) -> set[str]:
    from core.email.inventory import TABLES

    if not addresses:
        return set()
    queries = [f"""SELECT lower(email) AS email FROM {postgres.qualified(spec.name)}
        WHERE lower(email)=ANY(%s) AND (status='tombstone' OR COALESCE(data->>'pool_deleted_at','')<>'')"""
        for spec in TABLES.values()]
    cur.execute(' UNION '.join(queries), [addresses] * len(queries))
    return {row['email'] for row in cur.fetchall()}


def admit(plans: list[RetryAdmission]) -> dict[int, tuple[dict, bool] | dict | None]:
    """Return created/reused Jobs, validation errors, or a historical compatibility fallback."""
    if not plans:
        return {}
    registration.init()
    schema.init_operation_schema()
    jobs = postgres.qualified('registration_jobs')
    attempts = postgres.qualified('registration_attempts')
    runs = postgres.qualified('registration_runs')
    tasks = common._table('operation_tasks')
    op_attempts = common._table('registration_attempts')
    batches = common._table('operation_batches')
    queue = common._table('operation_projection_queue')
    ids = sorted({ident for p in plans for ident in (p.source_id, p.root_id)})
    roots = sorted({p.root_id for p in plans})
    with records.transaction() as conn, conn.cursor() as cur:
        _advisory_locks(cur, [f'registration-retry:{root}' for root in roots])
        cur.execute(f"""SELECT id,source_id FROM {batches}
                        WHERE source_system='registration_batches' AND source_id=ANY(%s)""",
                    (sorted({p.batch_id for p in plans if p.batch_id}),))
        batch_ids = {row['source_id']: row['id'] for row in cur.fetchall()}
        # The projection writer also locks queue rows before changing any projected facts.
        cur.execute(f'SELECT batch_id FROM {queue} WHERE batch_id=ANY(%s) ORDER BY batch_id FOR UPDATE',
                    (sorted(batch_ids.values()),))
        cur.fetchall()
        cur.execute(f'SELECT * FROM {attempts} WHERE source_root_job_id=ANY(%s) ORDER BY id FOR UPDATE', (roots,))
        locked_attempts = {row['source_root_job_id']: registration._row(row) for row in cur.fetchall()}
        cur.execute(f'SELECT * FROM {jobs} WHERE id=ANY(%s) ORDER BY id FOR NO KEY UPDATE', (ids,))
        locked_jobs = {row['id']: records.merge_row(records.JOBS, row) for row in cur.fetchall()}
        cur.execute(f"""SELECT DISTINCT ON (root_job_id) * FROM {jobs}
                       WHERE root_job_id=ANY(%s) AND status=ANY(%s) ORDER BY root_job_id,id""", (roots, list(_ACTIVE)))
        active_children = {row['root_job_id']: records.merge_row(records.JOBS, row) for row in cur.fetchall()}
        cur.execute(f"""SELECT COALESCE(root_job_id,id) AS root,
                       MAX(CASE WHEN data->>'retry_attempt' ~ '^[0-9]{{1,9}}$'
                                THEN (data->>'retry_attempt')::int ELSE 0 END) AS retry_no,
                       array_agg(id) FILTER (WHERE status='success' AND root_job_id IS NOT NULL) AS succeeded
                       FROM {jobs} WHERE id=ANY(%s) OR root_job_id=ANY(%s)
                       GROUP BY COALESCE(root_job_id,id)""", (roots, roots))
        history = {row['root']: row for row in cur.fetchall()}
        cur.execute(f"""SELECT attempt_id,MAX(run_no)+1 AS next_run_no,
                       bool_or(status IN ('queued','running')) AS active
                       FROM {runs} WHERE attempt_id=ANY(%s) GROUP BY attempt_id""",
                    ([a['id'] for a in locked_attempts.values()],))
        run_state = {row['attempt_id']: row for row in cur.fetchall()}
        cur.execute(f"""SELECT a.id,a.source_root_job_id,a.target_status,t.id AS root_task_id
                       FROM {op_attempts} a JOIN {tasks} t ON t.attempt_id=a.id
                       AND t.source_system='registration_chains'
                       AND t.source_id=a.source_root_job_id::text || ':registration'
                       WHERE a.source_root_job_id=ANY(%s)""", (roots,))
        projected = {row['source_root_job_id']: row for row in cur.fetchall()}
        addresses = sorted({address for p in plans for address in (
            _normalized_address(p.email),
            _normalized_address((locked_attempts.get(p.root_id) or {}).get('email')
                                or (locked_attempts.get(p.root_id) or {}).get('email_snapshot')),
        ) if address})
        _advisory_locks(cur, [f'registered-account:{a}' for a in addresses])
        deleted = _deleted_addresses(cur, addresses)
        account_ids = sorted({p.account_id for p in plans if p.account_id is not None})
        cur.execute(f"""SELECT id,email,updated_at FROM {postgres.qualified(records.ACCOUNTS.name)}
                        WHERE id=ANY(%s) ORDER BY id FOR NO KEY UPDATE""", (account_ids,))
        current_accounts = {row['id']: row for row in cur.fetchall()}

        results = {}
        to_create = {}
        to_reuse = []
        for plan in plans:
            ident, root = plan.source_id, plan.root_id
            source = locked_jobs.get(ident)
            attempt = locked_attempts.get(root)
            if source is None:
                results[ident] = _error('任务不存在', 404)
            elif source['status'] not in _TERMINAL:
                results[ident] = _error(f"当前状态不支持重试：{source['status']}")
            elif (source != plan.source or locked_jobs.get(root) != plan.root or
                  attempt is not None and plan.attempt is not None and attempt != plan.attempt):
                results[ident] = _error(_CHANGED)
            elif any(sibling != ident for sibling in history[root]['succeeded'] or ()):
                results[ident] = _error('同一任务链已有成功任务')
            elif (_normalized_address(plan.email) in deleted or
                  _normalized_address((attempt or {}).get('email') or (attempt or {}).get('email_snapshot')) in deleted):
                results[ident] = _error('原邮箱已删除，不能继续注册')
            elif root in active_children:
                active = active_children[root]
                results[ident] = ((active, False) if active['job_type'] == plan.action else
                                  _error(f"已有其他类型重试任务 #{active['id']} 在排队或运行中"))
            elif (attempt is None or plan.attempt is None or root not in projected or plan.batch_id not in batch_ids
                  or source.get('attempt_id') != attempt['id'] or plan.root.get('attempt_id') != attempt['id']
                  or attempt.get('root_job_id') != root or attempt['id'] not in run_state):
                # The old entry point can backfill pre-Attempt Jobs and missing projections.
                results[ident] = None
            elif run_state[attempt['id']]['active']:
                results[ident] = _error('同一 Attempt 已有运行在排队或执行中')
            elif plan.account_id is not None and (
                    not (current_account := current_accounts.get(plan.account_id)) or
                    current_account['updated_at'] != plan.account.get('updated_at') or
                    _normalized_address(current_account['email']) != _normalized_address(plan.email)
            ):
                results[ident] = _error(_CHANGED)
            elif root in to_create:
                to_reuse.append(plan)
            else:
                to_create[root] = plan

        if to_create:
            inserted = _insert_facts(cur, list(to_create.values()), locked_attempts, run_state, history,
                                     projected, batch_ids)
            for plan in to_create.values():
                results[plan.source_id] = (inserted[plan.root_id], True)
            for plan in to_reuse:
                job = inserted[plan.root_id]
                results[plan.source_id] = ((job, False) if job['job_type'] == plan.action else
                                          _error(f"已有其他类型重试任务 #{job['id']} 在排队或运行中"))
    return results


def _insert_facts(cur, plans, attempts, run_state, history, projected, batch_ids):
    jobs = postgres.qualified('registration_jobs')
    registration_attempts = postgres.qualified('registration_attempts')
    registration_runs = postgres.qualified('registration_runs')
    tasks = common._table('operation_tasks')
    runs = common._table('operation_runs')
    queue = common._table('operation_projection_queue')
    batches = common._table('operation_batches')
    serialized = []
    columns = {}
    stage = normalize_stage(None)
    for p in plans:
        retry_no = history[p.root_id]['retry_no'] + 1
        row = db._new_job_row(job_type=p.action, parent_job_id=p.source_id, root_job_id=p.root_id,
                             retry_attempt=retry_no, retry_action=p.action, email=p.email,
                             email_source=p.email_source, account_id=p.account_id, batch_id=p.batch_id,
                             batch_index=p.batch_index, batch_size=p.batch_size, batch_workers=p.workers,
                             data={'config_snapshot': p.config_snapshot, 'registration_dispatch_ready': False})
        row.update(attempt_id=attempts[p.root_id]['id'], updated_at=row['created_at'])
        if p.debug_enabled:
            row.update(debug_enabled=True, debug_state='pending', debug_policy=dict(p.source.get('debug_policy') or {
                'capture_network': True, 'hold_on_failure': True, 'preserve_success_browser': False,
            }))
        promoted, data = records._split(records.JOBS, row, partial=False)
        columns = {key: records.JOBS.promoted[key].split()[0] for key in promoted}
        serialized.append({**promoted, 'data': data})
    names = ', '.join(postgres.quote_identifier(name) for name in (*columns, 'data'))
    record_type = ', '.join(f'{postgres.quote_identifier(name)} {kind}' for name, kind in columns.items())
    cur.execute(f"""INSERT INTO {jobs} ({names})
                  SELECT {names} FROM jsonb_to_recordset(%s::jsonb) AS src({record_type},data jsonb)
                  RETURNING *""", (_json(serialized),))
    inserted = {row['root_job_id']: records.merge_row(records.JOBS, row) for row in cur.fetchall()}
    facts = []
    for p in plans:
        job = inserted[p.root_id]
        fact = projected[p.root_id]
        snapshot = registration._json_value({'config_snapshot': p.config_snapshot, 'registration_dispatch_ready': False})
        facts.append({
            'job_id': job['id'], 'root_id': p.root_id, 'parent_id': p.source_id, 'job_uuid': job['job_uuid'],
            'created_at': job['created_at'], 'log_file': job['log_file'], 'action': p.action,
            'attempt_id': job['attempt_id'], 'projection_attempt_id': fact['id'], 'root_task_id': fact['root_task_id'],
            'account_id': p.account_id, 'email': p.email or '', 'batch_id': batch_ids[p.batch_id],
            'run_no': run_state[job['attempt_id']]['next_run_no'], 'retry_attempt': job['retry_attempt'],
            'registration_uuid': str(uuid.uuid4()), 'run_uuid': common._uuid('run', f"registration_jobs:{job['id']}"),
            'task_uuid': common._uuid('task', f'registration_chains:{p.root_id}:{p.action}'),
            'projection_config': common._scrub(p.config_snapshot), 'registration_config': snapshot,
            'attempt_config': {k: v for k, v in snapshot.items() if not (
                k == 'config_snapshot' and p.config_snapshot.get('retry_proxy_country_override'))},
            'target_status': fact['target_status'],
        })
    payload = _json(facts)
    fact_type = '''job_id bigint,root_id bigint,parent_id bigint,job_uuid text,created_at timestamptz,
        log_file text,action text,attempt_id bigint,projection_attempt_id bigint,root_task_id bigint,
        account_id bigint,email text,batch_id bigint,run_no integer,retry_attempt integer,
        registration_uuid text,run_uuid text,task_uuid text,projection_config jsonb,registration_config jsonb,
        attempt_config jsonb,target_status text'''
    source = f'jsonb_to_recordset(%s::jsonb) AS f({fact_type})'
    cur.execute(f"""INSERT INTO {registration_runs}
        (run_uuid,attempt_id,job_id,run_no,action_type,status,heartbeat_at,data)
        SELECT registration_uuid,attempt_id,job_id,run_no,action,'queued',now(),registration_config
        FROM {source}""", (payload,))
    cur.execute(f"""UPDATE {registration_attempts} a SET updated_at=now(),
        email_snapshot=CASE WHEN a.email_snapshot='' THEN f.email ELSE a.email_snapshot END,
        email=COALESCE(NULLIF(a.email,''),f.email),data=a.data || f.attempt_config
        FROM {source} WHERE a.id=f.attempt_id""", (payload,))
    cur.execute(f"""INSERT INTO {tasks} AS task
        (task_uuid,source_system,source_id,batch_id,root_task_id,parent_task_id,task_type,target_type,target_id,
         attempt_id,account_id,email_snapshot,requested_action,status,target_status,current_stage,trigger,
         created_at,updated_at,data)
        SELECT task_uuid,'registration_chains',root_id::text || ':' || action,batch_id,root_task_id,
               CASE WHEN action='registration_resume' THEN root_task_id END,action,'registration_attempt',
               projection_attempt_id,projection_attempt_id,account_id,left(email,320),action,'queued',
               target_status,%s,'manual_retry',created_at,created_at,
               jsonb_build_object('legacy_root_job_id',root_id,'latest_legacy_job_id',job_id,
                                  'route_attempt_no',1,'selected_route_attempt_no',1,'config_snapshot',projection_config)
        FROM {source}
        ON CONFLICT (source_system,source_id) DO UPDATE SET
          batch_id=EXCLUDED.batch_id,account_id=COALESCE(EXCLUDED.account_id,task.account_id),
          email_snapshot=COALESCE(NULLIF(EXCLUDED.email_snapshot,''),task.email_snapshot),
          target_status=EXCLUDED.target_status,data=task.data || EXCLUDED.data""", (stage, payload))
    cur.execute(f"""WITH added AS (
        INSERT INTO {runs}
            (run_uuid,task_id,run_no,source_system,source_id,status,execution_id,progress_stage,
             result_summary,log_file,created_at,data)
        SELECT f.run_uuid,t.id,GREATEST(f.retry_attempt+1,COALESCE(prior.max_no,0)+1),
               'registration_jobs',f.job_id::text,'queued',f.job_uuid,%s,
               jsonb_build_object('account_id',f.account_id,'retry_action',f.action),f.log_file,f.created_at,
               jsonb_build_object('legacy_job_id',f.job_id,'parent_job_id',f.parent_id,
                                  'route_attempt_no',1,'selected_route_attempt_no',1,
                                  'route_attempts','[]'::jsonb,'failure_stage',null,'config_snapshot',f.projection_config)
        FROM {source} JOIN {tasks} t ON t.task_uuid=f.task_uuid
        LEFT JOIN LATERAL (SELECT MAX(run_no) AS max_no FROM {runs} r WHERE r.task_id=t.id) prior ON true
        RETURNING id,task_id,progress_stage
    ) UPDATE {tasks} t SET last_run_id=added.id,status='queued',current_stage=added.progress_stage,
        updated_at=now(),completed_at=NULL,next_actions='[]'::jsonb,
        error_category=NULL,error_code=NULL,error_message=NULL
      FROM added WHERE t.id=added.task_id""", (stage, payload))
    cur.execute(f"""WITH dirty_batches AS (
        INSERT INTO {queue} AS q (batch_id,reason,source_system,source_id,status,requested_at,available_at)
        SELECT batch_id,'registration_job_updated','registration_jobs',max(job_id)::text,'queued',now(),now()
        FROM {source} GROUP BY batch_id ORDER BY batch_id
        ON CONFLICT (batch_id) DO UPDATE SET
            reason=EXCLUDED.reason,source_system=EXCLUDED.source_system,source_id=EXCLUDED.source_id,
            requested_at=EXCLUDED.requested_at,status=CASE WHEN q.status='running' THEN 'running' ELSE 'queued' END,
            dirty=q.status='running',available_at=CASE WHEN q.status='running' THEN q.available_at ELSE EXCLUDED.available_at END,
            completed_at=CASE WHEN q.status='running' THEN q.completed_at END,
            last_error=CASE WHEN q.status='running' THEN q.last_error END,updated_at=now()
        RETURNING batch_id
    ) UPDATE {batches} b SET projection_status=CASE WHEN b.projection_status='running' THEN 'running' ELSE 'queued' END,
        projection_requested_at=now(),projection_next_retry_at=NULL,
        projection_error=CASE WHEN b.projection_status='running' THEN b.projection_error END
      FROM dirty_batches WHERE b.id=dirty_batches.batch_id""", (payload,))
    cur.execute(f"""UPDATE {jobs} SET data=data ||
                  '{{"registration_dispatch_ready":true,"registration_account_task_id":null}}'::jsonb
                  WHERE id=ANY(%s) RETURNING *""", ([row['id'] for row in inserted.values()],))
    return {row['root_job_id']: records.merge_row(records.JOBS, row) for row in cur.fetchall()}
