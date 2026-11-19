"""Registration event projection scope, historical ownership and replay consistency."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import uuid

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from core.storage import postgres as pg, records, registration
from core.storage.operations import projection, store
from tests.support_pg import PostgresTestCase

FIXED_TIME = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


class RegistrationProjectionBatchingTests(PostgresTestCase):
    def setUp(self):
        records.init()
        registration.reset_ready()
        registration.init()
        store.reset_ready()
        store.init()

    def insert(self, table, fields):
        names = list(fields)
        placeholders = ','.join(['%s'] * len(names))
        with pg.connect(row_factory=dict_row) as conn:
            row = conn.execute(f"INSERT INTO {pg.qualified(table)} ({','.join(names)}) "
                               f"VALUES ({placeholders}) RETURNING id", list(fields.values())).fetchone()
        return row['id']

    def task(self, fixture, *, task_type='registration'):
        token = uuid.uuid4().hex
        return self.insert('operation_tasks', dict(task_uuid=token, source_system='projection_test',
            source_id=token, batch_id=fixture['batch'], attempt_id=fixture['attempt'],
            task_type=task_type, target_type='synthetic', requested_action=task_type, status='failed'))

    def make_run(self, fixture, *, historical=True, task_id=None):
        token = uuid.uuid4().hex
        return self.insert('operation_runs', dict(run_uuid=token, task_id=task_id or fixture['task'],
            run_no=1 if historical else 2,
            source_system='registration_jobs' if historical else 'projection_test_latest',
            source_id=str(fixture['job']) if historical else token, batch_id=fixture['batch'], status='failed'))

    def fixture(self, *, historical=True, task=True):
        token = uuid.uuid4().hex
        batch = self.insert('operation_batches', dict(batch_uuid=token, source_system='registration_batches',
            source_id=token, batch_type='registration', title='synthetic', status='failed'))
        job = self.insert('registration_jobs', dict(job_uuid=token, email=f'{token}@example.test',
            created_at=FIXED_TIME, updated_at=FIXED_TIME, status='failed', batch_id=token, data=Jsonb({})))
        attempt = self.insert('registration_attempts', dict(attempt_uuid=token, root_job_id=job,
            source_root_job_id=job, email_snapshot=f'{token}@example.test', checkpoint='created'))
        with pg.connect() as conn:
            conn.execute(f'UPDATE {pg.qualified("registration_jobs")} SET attempt_id=%s WHERE id=%s', (attempt, job))
        result = dict(batch=batch, job=job, attempt=attempt)
        if task:
            result['task'] = self.task(result)
            if historical:
                result['old_run'] = self.make_run(result)
            result['new_run'] = self.make_run(result, historical=False)
            with pg.connect() as conn:
                conn.execute(f'UPDATE {pg.qualified("operation_tasks")} SET last_run_id=%s WHERE id=%s',
                             (result['new_run'], result['task']))
        return result

    def event(self, fixture, *, job=True, detail=None, message='synthetic event'):
        token = uuid.uuid4().hex
        self.insert('registration_events', dict(event_uuid=token, attempt_id=fixture['attempt'],
            job_id=fixture['job'] if job else None, created_at=FIXED_TIME, checkpoint='created',
            event_type='synthetic.checkpoint', message=message, detail=Jsonb(detail or {'ordinal': 1})))
        return token

    def events(self, *, xmin=False):
        extra = ',xmin::text AS xmin' if xmin else ''
        with pg.connect(row_factory=dict_row) as conn:
            return list(conn.execute(f"SELECT *{extra} FROM {pg.qualified('operation_events')} "
                                     "WHERE source_system='registration_events' ORDER BY source_id").fetchall())

    def source_facts(self):
        with pg.connect(row_factory=dict_row) as conn:
            return {name: list(conn.execute(f'SELECT * FROM {pg.qualified(name)} ORDER BY id').fetchall())
                    for name in ('registration_jobs', 'registration_attempts', 'registration_runs', 'registration_events')}

    def project(self, batch, cursor_wrapper=None):
        with pg.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
            return projection._project_registration_fact_events(cursor_wrapper(cur) if cursor_wrapper else cur, batch)

    def test_batch_scope_task_preference_and_historical_or_unknown_run_ownership(self):
        first, second = self.fixture(), self.fixture()
        preferred = self.task(first)
        self.task(first, task_type='plan_check')  # Newer non-registration task cannot win.
        old, unknown = self.event(first), self.event(first, job=False)
        unrelated = self.event(second)
        source = self.source_facts()
        self.assertEqual(2, self.project(first['batch']))
        result = {row['source_id']: row for row in self.events()}
        self.assertEqual({old, unknown}, set(result))
        self.assertEqual(preferred, result[old]['task_id'])
        self.assertEqual(first['old_run'], result[old]['run_id'])
        self.assertNotEqual(first['new_run'], result[old]['run_id'])
        self.assertIsNone(result[unknown]['run_id'])
        before = deepcopy(result)
        self.assertEqual(1, self.project(second['batch']))
        result = {row['source_id']: row for row in self.events()}
        self.assertEqual({old, unknown, unrelated}, set(result))
        self.assertEqual(before, {key: result[key] for key in before})
        self.assertEqual(source, self.source_facts())

    def test_missing_task_is_skipped_then_late_task_and_run_are_projected_on_replay(self):
        fixture = self.fixture(task=False)
        token = self.event(fixture)
        source = self.source_facts()
        self.assertEqual(0, self.project(fixture['batch']))
        self.assertEqual([], self.events())
        fixture['task'] = self.task(fixture, task_type='plan_check')
        self.assertEqual(1, self.project(fixture['batch']))
        self.assertIsNone(self.events()[0]['run_id'])
        historical = self.make_run(fixture)
        self.assertEqual(1, self.project(fixture['batch']))
        self.assertEqual((token, historical), (self.events()[0]['source_id'], self.events()[0]['run_id']))
        self.assertEqual(source, self.source_facts())

    def test_more_than_one_mapping_chunk_keeps_every_task_and_run(self):
        fixture = self.fixture(task=False)
        prefix = uuid.uuid4().hex
        with pg.connect(row_factory=dict_row) as conn:
            source = conn.execute(f'SELECT source_id FROM {pg.qualified("operation_batches")} WHERE id=%s',
                                  (fixture['batch'],)).fetchone()['source_id']
            conn.execute(f'''INSERT INTO {pg.qualified('registration_jobs')}
                (job_uuid,email,created_at,updated_at,status,batch_id,data)
                SELECT %s||n,n||'@example.test',%s,%s,'failed',%s,'{{}}'::jsonb
                FROM generate_series(1,1001)n''', (prefix, FIXED_TIME, FIXED_TIME, source))
            conn.execute(f'''INSERT INTO {pg.qualified('registration_attempts')}
                (attempt_uuid,root_job_id,source_root_job_id,checkpoint)
                SELECT job_uuid,id,id,'created' FROM {pg.qualified('registration_jobs')}
                WHERE job_uuid LIKE %s''', (prefix + '%',))
            conn.execute(f'''INSERT INTO {pg.qualified('operation_tasks')}
                (task_uuid,source_system,source_id,batch_id,attempt_id,task_type,target_type,requested_action,status)
                SELECT attempt_uuid,'projection_chunk',attempt_uuid,%s,id,'registration','synthetic','registration','failed'
                FROM {pg.qualified('registration_attempts')} WHERE attempt_uuid LIKE %s''',
                         (fixture['batch'], prefix + '%'))
            conn.execute(f'''INSERT INTO {pg.qualified('operation_runs')}
                (run_uuid,task_id,run_no,source_system,source_id,batch_id,status)
                SELECT t.task_uuid,t.id,1,'registration_jobs',a.root_job_id::text,%s,'failed'
                FROM {pg.qualified('operation_tasks')} t JOIN {pg.qualified('registration_attempts')} a ON a.id=t.attempt_id
                WHERE t.source_system='projection_chunk' ''', (fixture['batch'],))
            conn.execute(f'''INSERT INTO {pg.qualified('registration_events')}
                (event_uuid,attempt_id,job_id,created_at,checkpoint,event_type,message,detail)
                SELECT attempt_uuid,id,root_job_id,%s,'created','synthetic.checkpoint','chunk event','{{}}'::jsonb
                FROM {pg.qualified('registration_attempts')} WHERE attempt_uuid LIKE %s''',
                         (FIXED_TIME, prefix + '%'))
            expected = {row['source_id']: (row['task_id'], row['run_id']) for row in conn.execute(f'''
                SELECT t.task_uuid AS source_id,t.id AS task_id,r.id AS run_id
                FROM {pg.qualified('operation_tasks')} t JOIN {pg.qualified('operation_runs')} r ON r.task_id=t.id
                WHERE t.source_system='projection_chunk' ''').fetchall()}
        source_before = self.source_facts()
        self.assertEqual(1001, self.project(fixture['batch']))
        self.assertEqual(expected, {row['source_id']: (row['task_id'], row['run_id']) for row in self.events()})
        self.assertEqual(source_before, self.source_facts())

    def test_unchanged_replay_keeps_xmin_and_count_while_changed_source_updates(self):
        fixture = self.fixture()
        token = self.event(fixture)
        source = self.source_facts()
        self.assertEqual(1, self.project(fixture['batch']))
        original = self.events(xmin=True)
        self.assertEqual(1, self.project(fixture['batch']))
        self.assertEqual(original, self.events(xmin=True))
        self.assertEqual(source, self.source_facts())
        with pg.connect() as conn:
            conn.execute(f'UPDATE {pg.qualified("registration_events")} SET message=%s,detail=%s WHERE event_uuid=%s',
                         ('corrected message', Jsonb({'ordinal': 2}), token))
        self.assertEqual(1, self.project(fixture['batch']))
        changed = self.events(xmin=True)[0]
        self.assertEqual('corrected message', changed['message'])
        self.assertEqual(2, changed['detail']['ordinal'])
        self.assertNotEqual(original[0]['xmin'], changed['xmin'])
        self.assertEqual(original[0]['id'], changed['id'])
        self.assertEqual(original[0]['event_uuid'], changed['event_uuid'])

    def test_legacy_duplicate_source_order_keeps_last_write_and_processed_count(self):
        fixture = self.fixture()
        self.event(fixture)
        source = self.source_facts()

        class DuplicateSourceCursor:
            """Normal DB uniqueness stays enabled; simulate an old duplicate input export only."""
            def __init__(self, cursor):
                self.cursor = cursor
                self.is_source = False

            def execute(self, query, params=None):
                self.is_source = 'SELECT e.*, rr.job_id AS run_job_id' in query
                return self.cursor.execute(query, params)

            def fetchone(self):
                return self.cursor.fetchone()

            def fetchall(self):
                rows = self.cursor.fetchall()
                if self.is_source:
                    return [dict(rows[0], message='first source version'), dict(rows[0], message='last source version')]
                return rows

        self.assertEqual(2, self.project(fixture['batch'], DuplicateSourceCursor))
        self.assertEqual(1, len(self.events()))
        self.assertEqual('last source version', self.events()[0]['message'])
        self.assertEqual(source, self.source_facts())

    def test_late_run_enqueued_during_mapping_is_repaired_by_dirty_queue_replay(self):
        fixture = self.fixture(historical=False)
        related = self.event(fixture)
        unknown = self.event(fixture, job=False)
        projection.enqueue_batch_projection(fixture['batch'])
        claimed = projection.claim_projection(worker_id='projection-test')
        self.assertEqual(fixture['batch'], claimed['batch_id'])
        late = {}

        class LateRunCursor:
            def __init__(self, cursor):
                self.cursor = cursor

            def execute(wrapper, query, params=None):
                value = wrapper.cursor.execute(query, params)
                if not late and query.lstrip().startswith('SELECT') and 'operation_runs' in query and "source_system='registration_jobs'" in query:
                    # The SELECT snapshot already missed the Run. A separate commit
                    # plus durable enqueue must force another projection pass.
                    late['run'] = self.make_run(fixture)
                    projection.enqueue_batch_projection(fixture['batch'], reason='late-run')
                return value

            def fetchone(self):
                return self.cursor.fetchone()

            def fetchall(self):
                return self.cursor.fetchall()

        self.assertEqual(2, self.project(fixture['batch'], LateRunCursor))
        self.assertTrue(late)
        first = {row['source_id']: row for row in self.events()}
        self.assertIsNone(first[related]['run_id'])
        self.assertIsNone(first[unknown]['run_id'])
        completed = projection._complete_projection(fixture['batch'], claimed['id'])
        self.assertEqual('queued', completed['status'])
        projection.run_projection_once(worker_id='projection-test-replay')
        result = {row['source_id']: row for row in self.events()}
        self.assertEqual(late['run'], result[related]['run_id'])
        self.assertIsNone(result[unknown]['run_id'])
        self.assertEqual(first[related]['id'], result[related]['id'])
