"""Offline integrity tests and explicitly gated original-native PG regressions.

Only the root exclusive DB slot may set SETTLEMENT_DB_TESTS=1. Merely importing
this file never probes a database or imports tests.support_pg.
"""
from __future__ import annotations
import os
import time
import unittest
import hashlib
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from core.operations.settlement_contracts import SettlementDomain, seal_intent, OperationSettlementConflict
from core.storage.operations import common, settlements

_UNIT_DOMAIN_ID=hashlib.sha256(json.dumps(
    ['postgresql://unit.invalid/not-contacted','test_origin','test_origin'],
    ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def make_intent(kind='terminal', *, execution='exec-1', transition='transition-1', **payload):
    origin = {'domain_id':_UNIT_DOMAIN_ID, 'operation_schema':'test_origin', 'permit_schema':'test_origin',
              'run_id':1, 'run_uuid':'run-one', 'task_id':1, 'execution_id':execution,
              'permit_id':f'permit-{execution}', 'ticket_id':f'ticket-{execution}',
              'lease_requirement':'accountless'}
    return seal_intent(kind=kind, origin=origin, payload=payload or {'status':'success'}, transition_id=transition)


class SettlementStoreOfflineTests(unittest.TestCase):
    domain = SettlementDomain('postgresql://unit.invalid/not-contacted', 'test_origin', 'test_origin', _UNIT_DOMAIN_ID)

    def test_context_domain_is_local_and_restored_without_environment_mutation(self):
        from core.storage import postgres
        before = dict(os.environ)
        with patch.object(postgres, 'connect') as connect:
            with common.settlement_scope(self.domain, deadline=123):
                self.assertEqual(common._schema_name(), 'test_origin')
                common._connect()
                self.assertEqual(connect.call_args.args[0], self.domain.database_url)
                self.assertEqual(connect.call_args.kwargs['deadline'], 123)
                self.assertEqual(postgres.schema_name(), 'test_origin')
            self.assertIsNone(common.current_settlement_domain())
        self.assertEqual(before, dict(os.environ))

    def test_exact_receipt_returns_original_snapshot_before_any_fence_or_fact(self):
        intent = make_intent()
        expected = {'status':'success', 'receipt_id':7, 'transition_event_uuid':'original'}
        conn = MagicMock()
        with patch.object(common, '_connect', return_value=conn), \
             patch.object(settlements, '_read_cur', return_value=expected), \
             patch.object(settlements, '_permit_fence') as fence, \
             patch('core.bulk_operations.execution.fact_update') as fact:
            self.assertEqual(expected, settlements.submit_intent(intent, domain=self.domain))
            fence.assert_not_called()
            fact.assert_not_called()

    def test_actual_digest_is_independent_of_request_and_readback_rejects_corruption(self):
        intent = make_intent(status='failed')
        actual = {'id':1,'status':'attention_required','result_summary':{'requested_status':'failed'}}
        row = {'id':1,'domain_id':_UNIT_DOMAIN_ID,'run_id':1,'run_uuid':'run-one','execution_id':'exec-1',
               'permit_id':'permit-exec-1','ticket_id':'ticket-exec-1','transition_id':'transition-1',
               'transition_kind':'terminal','request_digest':intent.request_digest,'request_version':1,'actual_version':1,'receipt_version':1,
               'actual_result':actual,'actual_digest':settlements._digest(actual)}
        cursor = MagicMock()
        cursor.fetchall.return_value = [row]
        result = settlements._read_cur(cursor, intent, dict(intent.origin))
        self.assertEqual(result['status'],'attention_required')
        self.assertNotEqual(intent.request_digest, result['actual_digest'])
        row['actual_result']['status']='success'
        with self.assertRaises(OperationSettlementConflict):
            settlements._read_cur(cursor, intent, dict(intent.origin))

    def test_typed_cleanup_rejects_unknown_callable_and_private_data(self):
        base = make_intent()
        for obligation in (
            {'action_kind':'invoke_handler','resource_identity':'one','payload':{}},
            {'action_kind':'run_log','resource_identity':'one','payload':{'password':'private'}},
        ):
            with self.assertRaises(ValueError):
                settlements._obligations(seal_intent(kind='terminal',origin=base.origin,payload=base.payload,obligations=(obligation,)))

    def test_cleanup_claim_cannot_adopt_live_callback_or_unknown_process(self):
        from core.storage.operations import permits
        owner = {'host_id':'foreign','pid':12345,'process_start':'old'}
        with patch.object(permits, 'current_owner', return_value={'host_id':'local','pid':1}), \
             patch.object(permits, 'owner_liveness', return_value='unverified'):
            self.assertFalse(settlements._cleanup_handoff_ready({'owner':owner}))
        with patch.object(permits, 'current_owner', return_value={'host_id':'local','pid':1}), \
             patch.object(permits, 'owner_liveness', return_value='exited'):
            self.assertTrue(settlements._cleanup_handoff_ready({'owner':owner}))

    def test_receipt_missing_does_not_infer_no_resource_disposition(self):
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [None]
        self.assertTrue(settlements.cleanup_blocks_permit('p','e',domain=self.domain,conn=conn))

    def test_cleanup_log_append_before_ack_retry_uses_original_event_once(self):
        import tempfile
        from pathlib import Path
        from core.operations import run_log
        with tempfile.TemporaryDirectory() as directory, patch.object(run_log, '_LOG_ROOT', Path(directory)):
            path = Path(directory) / 'run.jsonl'
            job = {'action_kind':'run_log','payload':{'log_file':str(path),'level':'INFO',
                   'message':'original','event_uuid':'one-event','task_id':1,'run_id':1}}
            settlements._execute_cleanup(job, domain=self.domain)
            settlements._execute_cleanup(job, domain=self.domain)
            self.assertEqual(1, len(path.read_text().splitlines()))

    def test_changed_bulk_ready_key_does_not_drop_original_managed_lock_or_fact(self):
        from core.storage.operations import bulk, bulk_schema, runtime
        intent = make_intent()
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        connect = MagicMock()
        connect.__enter__.return_value = conn
        sql = []
        def execute(query, params=None):
            sql.append(str(query))
        cursor.execute.side_effect = execute
        def row():
            query = sql[-1]
            if 'operation_batch_run_links' in query:
                return {'id':7,'target_round_id':7}
            if 'SELECT' in query and 'operation_runs' in query:
                return {'id':1,'run_uuid':'run-one','data':{'bulk_target_round_id':7}}
            return {'id':1,'domain_id':_UNIT_DOMAIN_ID,'run_id':1,'run_uuid':'run-one',
                    'execution_id':'exec-1','permit_id':'permit-exec-1'}
        cursor.fetchone.side_effect = row
        with patch.object(common,'_connect',return_value=connect), \
             patch.object(settlements,'_read_cur',side_effect=[None,None,{'receipt_id':1}]), \
             patch.object(settlements,'_permit_fence',return_value={'metadata':{'settlement_ticket':{'owner':{}}}}), \
             patch.object(settlements,'_first_write_fence',return_value={'task_id':1,'last_run_id':1}), \
             patch.object(settlements,'_verify_domain_cur',return_value={}), \
             patch.object(settlements,'_lock_origin'), \
             patch.object(runtime,'finish_run',return_value={'id':1,'task_id':1,'status':'success',
                          'terminal_event_id':1,'terminal_event_uuid':'original-event'}), \
             patch.object(bulk_schema,'_READY_KEY','another-domain'), \
             patch.object(bulk,'record_managed_change') as changed:
            settlements.submit_intent(intent,domain=self.domain)
        self.assertTrue(any('operation_batch_run_links' in query and 'FOR UPDATE' in query for query in sql),
                        'original target must remain locked after default domain changes')
        changed.assert_called_once_with(conn,7,event_kind='fact_changed')

    def test_live_superseded_requires_irreversible_local_handoff_before_database(self):
        from core.operations import settlement
        helper = getattr(settlements,'reconcile_superseded',lambda *args,**kwargs: {'unsafe':True})
        with patch.object(settlement,'superseded_handoff_ready',return_value=False,create=True), \
             patch.object(settlements,'read_receipt',return_value=None), \
             patch.object(settlements,'read_disposition',return_value=None), \
             patch.object(common,'_connect') as connect:
            self.assertIsNone(helper(make_intent(),domain=self.domain))
            connect.assert_not_called()

    def test_initialized_account_lock_never_calls_records_migration(self):
        from core.storage import records
        cur=MagicMock()
        cur.fetchone.return_value={'id':4,'email':'unit@example.test','data':{}}
        with common.settlement_scope(self.domain), \
             patch.object(records,'init',side_effect=AssertionError('unexpected records DDL')):
            account=common._settlement_account(cur,4,for_update=True)
        self.assertEqual(4,account['id'])
        self.assertIn('FOR UPDATE',cur.execute.call_args.args[0])

    def test_unsupported_actual_receipt_version_is_not_confirmed(self):
        intent=make_intent()
        row={'id':1,'domain_id':_UNIT_DOMAIN_ID,'run_id':1,'run_uuid':'run-one','execution_id':'exec-1',
             'permit_id':'permit-exec-1','ticket_id':'ticket-exec-1','transition_id':'transition-1',
             'transition_kind':'terminal','request_digest':intent.request_digest,'request_version':1,
             'actual_version':2,'receipt_version':1,'actual_result':{},'actual_digest':settlements._digest({})}
        cur=MagicMock()
        cur.fetchall.return_value=[row]
        with self.assertRaises(OperationSettlementConflict):
            settlements._read_cur(cur,intent,dict(intent.origin))

    def test_independent_disposition_cannot_ignore_cancel_pending_resource(self):
        from core.operations.settlement_contracts import OperationSettlementFenced
        cur=MagicMock()
        cur.fetchone.return_value=None
        cur.fetchall.return_value=[{'id':5,'resource_uuid':'sms-old','state':'cancel_pending'}]
        ticket=dict(make_intent().origin)
        result={'status':'interrupted','event_uuid':'authority-event','original_intent_committed':False,
                'resource_disposition':'no_blocking_resources','recovery_reason':'worker_exit_confirmed'}
        with self.assertRaises(OperationSettlementFenced):
            settlements.write_disposition(cur,ticket=ticket,result=result)
        sql=' '.join(str(item.args[0]) for item in cur.execute.call_args_list)
        self.assertIn("state <> 'released'",sql)

    def test_live_first_page_does_not_starve_later_handoff_cleanup(self):
        conn=MagicMock()
        conn.__enter__.return_value=conn
        cur=conn.cursor.return_value.__enter__.return_value
        initial=[{'id':index,'origin':{},'handoff_receipt_id':None} for index in range(1,33)]
        eligible={'id':33,'origin':{},'handoff_receipt_id':1,'settlement_actual_result':{}}
        cur.fetchall.side_effect=[initial,[eligible]]
        cur.fetchone.return_value={'id':33}
        settlements._CLEANUP_SCAN_CURSORS.pop(self.domain.domain_id,None)
        with patch.object(common,'_connect',return_value=conn), \
             patch.object(settlements,'_cleanup_handoff_ready',return_value=False):
            self.assertIsNone(settlements._claim_cleanup(domain=self.domain))
            claimed=settlements._claim_cleanup(domain=self.domain)
        self.assertEqual(33,claimed['id'])
        selects=[call for call in cur.execute.call_args_list if 'JOIN' in str(call.args[0])]
        self.assertEqual(32,selects[1].args[1][1])

    def test_independent_no_resources_proof_does_not_ignore_new_original_resource(self):
        conn=MagicMock()
        cur=conn.cursor.return_value.__enter__.return_value
        intent=make_intent()
        ticket={**dict(intent.origin),'version':1}
        result={'original_intent_committed':False,'resource_disposition':'no_blocking_resources'}
        disposition={'id':8,'run_id':1,'run_uuid':'run-one','domain_id':self.domain.domain_id,
                     'execution_id':'exec-1','permit_id':'permit-exec-1','ticket_id':'ticket-exec-1',
                     'disposition_kind':'orphan_recovery','original_intent_committed':False,
                     'result':result,'result_digest':settlements._digest(result)}
        cur.fetchone.side_effect=[
            {'metadata':{'settlement_ticket':ticket}},None,disposition,
            {'id':4,'resource_uuid':'late-original-resource','state':'cancel_pending'},
        ]
        self.assertTrue(settlements.cleanup_blocks_permit(
            'permit-exec-1','exec-1',domain=self.domain,conn=conn))

    def test_native_create_under_captured_scope_never_initializes_records(self):
        from core.storage.operations import runtime
        from core.storage import records
        conn=MagicMock()
        cur=conn.cursor.return_value.__enter__.return_value
        latest_sql=[]
        def execute(sql,params=None):
            latest_sql.append(str(sql))
        def fetchone():
            if 'registered_accounts' in latest_sql[-1]:
                return {'id':4,'email':'original@example.test','deactivated':False,
                        'data':{'access_token':'private-account-reference'}}
            return {'id':9,'task_uuid':'created','parent_task_id':None}
        cur.execute.side_effect=execute
        cur.fetchone.side_effect=fetchone
        with common.settlement_scope(self.domain), \
             patch.object(records,'init',side_effect=AssertionError('scoped create triggered records migration')), \
             patch.object(runtime,'_insert_runtime_run',return_value={'id':11,'task_id':9}), \
             patch('core.bulk_operations.execution.source_run_for_creation',return_value=None):
            created=runtime.create_runtime_task(task_type='plan_check',account_id=4,
                email='original@example.test',conn=conn)
        self.assertEqual(11,created['run']['id'])
        account_queries=[sql for sql in latest_sql if 'registered_accounts' in sql]
        self.assertEqual(1,len(account_queries))
        self.assertIn('"test_origin"."registered_accounts"',account_queries[0])
        self.assertIn('FOR UPDATE',account_queries[0])


if os.getenv('SETTLEMENT_DB_TESTS') == '1':
    # Deliberate opt-in is required in addition to the repository test DB guard.
    from tests.support_pg import PostgresTestCase
    from core.storage.operations import store, schema, permits, legacy_task_store
    from core.storage import postgres
    from psycopg.rows import dict_row
    import uuid

    class SettlementStorePostgresTests(PostgresTestCase):
        def setUp(self):
            # Legacy schemas are captured at import, before joint collection
            # selects this class's temporary PostgreSQL schema.
            self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
            self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
            legacy_task_store.init()
            store.reset_ready()
            store.init()
            self.domain = self._domain(self.schema, self.schema)

        def _domain(self, operation_schema, permit_schema):
            target = postgres.database_url()
            return SettlementDomain(target, operation_schema, permit_schema,
                settlements._digest([target,operation_schema,permit_schema]))

        def _claim(self, task=None, execution=None):
            task = task or store.create_runtime_task(task_type='plan_check', account_id=None,
                    email='settlement@example.test', trigger='test', resource_family='unit')
            run = task.get('run') or store.get_run(int(task['last_run_id']))
            execution = execution or uuid.uuid4().hex
            store.claim_run(int(run['id']),execution_id=execution,worker_pid=os.getpid())
            permit_id = uuid.uuid4().hex
            ticket = {'version':1,'domain_id':self.domain.domain_id,'operation_schema':self.domain.operation_schema,
                'permit_schema':self.domain.permit_schema,'run_id':int(run['id']),'run_uuid':run['run_uuid'],
                'task_id':int(run['task_id']),'execution_id':execution,'permit_id':permit_id,
                'ticket_id':uuid.uuid4().hex,'owner':permits.current_owner()}
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f'''INSERT INTO {permits._permit_table(self.domain.permit_schema)}
                    (permit_id,execution_key,execution_id,run_id,task_type,owner,metadata)
                    VALUES (%s,%s,%s,%s,'plan_check',%s::jsonb,%s::jsonb)''',
                    (permit_id,permit_id,execution,int(run['id']),settlements._json(ticket['owner']),
                     settlements._json({'settlement_ticket':ticket})))
            return task,run,{**ticket,'lease_requirement':'accountless' if run.get('account_id') is None else 'not_acquired'}

        def _intent(self, origin, *, kind='terminal', **payload):
            return seal_intent(kind=kind,origin=origin,payload=payload or {'status':'success'})

        def _leased_claim(self, *, task_type='plan_check', data=None):
            from core.storage import records
            account_id=records.insert_row(records.ACCOUNTS,{'email':f'fault-{uuid.uuid4().hex}@example.test'})
            task=store.create_runtime_task(task_type=task_type,account_id=account_id,
                email=f'fault-{account_id}@example.test',trigger='test',resource_family='unit',data=data)
            task,run,origin=self._claim(task)
            token=store.acquire_account_lease(account_id=account_id,run_id=run['id'],resource_family='unit')
            self.assertTrue(token)
            return task,run,{**origin,'lease_token':token,'lease_requirement':'final'}

        def _execution_snapshot(self, task_id, run_id):
            """Exact current generation facts; excludes mutable DB statistics."""
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                result={}
                for key,sql,args in (
                    ('task',f"SELECT * FROM {common._table('operation_tasks')} WHERE id=%s",(task_id,)),
                    ('run',f"SELECT * FROM {common._table('operation_runs')} WHERE id=%s",(run_id,)),
                    ('events',f"SELECT * FROM {common._table('operation_events')} WHERE run_id=%s ORDER BY id",(run_id,)),
                    ('leases',f"SELECT * FROM {common._table('account_operation_leases')} WHERE run_id=%s ORDER BY lease_token",(run_id,)),
                    ('resources',f"SELECT * FROM {common._table('operation_resources')} WHERE run_id=%s ORDER BY id",(run_id,)),
                    ('permits',f"SELECT * FROM {permits._permit_table(self.domain.permit_schema)} WHERE run_id=%s ORDER BY permit_id",(run_id,)),
                ):
                    cur.execute(sql,args)
                    result[key]=list(cur.fetchall())
                return result

        def _transition_counts(self, run_id):
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f'''SELECT
                    (SELECT count(*) FROM {common._table('operation_settlement_receipts')} WHERE run_id=%s) receipts,
                    (SELECT count(*) FROM {common._table('operation_events')} WHERE run_id=%s
                       AND (event_type='run.requeued' OR event_type IN
                         ('run.success','run.failed','run.cancelled','run.stopped','run.attention_required'))) transitions,
                    (SELECT count(*) FROM {common._table('operation_settlement_cleanup')} WHERE run_id=%s) cleanups''',
                    (run_id,run_id,run_id))
                return dict(cur.fetchone())

        @contextmanager
        def _connection_fault(self, *, boundary):
            """Inject one driver boundary around the real native transaction.

            BEGIN/SQL/precommit failures roll back through the actual pooled
            connection context. ACK loss is raised only after real commit.
            """
            from psycopg import OperationalError
            from psycopg.errors import SerializationFailure
            original=common._connect
            fired=[]
            class CursorProxy:
                def __init__(self,cur):
                    self._cur=cur
                def __getattr__(self,name):
                    return getattr(self._cur,name)
                def __enter__(self):
                    self._cur.__enter__()
                    return self
                def __exit__(self,*args):
                    return self._cur.__exit__(*args)
                def execute(self,query,params=None,**kwargs):
                    normalized=' '.join(str(query).split())
                    should_fail=(
                        boundary=='first_write' and normalized.startswith('UPDATE')
                            and '"operation_runs"' in normalized
                        or boundary=='projection' and normalized.startswith('UPDATE')
                            and '"operation_tasks"' in normalized
                        or boundary=='final_delete' and normalized.startswith('DELETE')
                            and '"account_operation_leases"' in normalized
                    )
                    if should_fail and not fired:
                        fired.append(boundary)
                        raise SerializationFailure('injected_known_rollback')
                    self._cur.execute(query,params,**kwargs)
                    return self
            class ConnectionProxy:
                def __init__(self,conn):
                    self._conn=conn
                def __getattr__(self,name):
                    return getattr(self._conn,name)
                def cursor(self,*args,**kwargs):
                    return CursorProxy(self._conn.cursor(*args,**kwargs))
            @contextmanager
            def connect():
                with original() as conn:
                    if boundary=='begin' and not fired:
                        with conn.cursor() as cur:
                            cur.execute('BEGIN')
                        fired.append(boundary)
                        raise SerializationFailure('injected_known_begin_rollback')
                    yield ConnectionProxy(conn)
                    if boundary=='precommit' and not fired:
                        fired.append(boundary)
                        raise SerializationFailure('injected_known_precommit_rollback')
                if boundary=='commit_ack_lost' and not fired:
                    fired.append(boundary)
                    raise OperationalError('injected_commit_ack_lost')
            with patch.object(common,'_connect',side_effect=connect):
                yield fired

        def test_s02_known_transaction_failures_keep_exact_success_request_and_rollback(self):
            from psycopg.errors import SerializationFailure
            for boundary in ('begin','first_write','projection','precommit'):
                with self.subTest(boundary=boundary):
                    task,run,origin=self._leased_claim()
                    intent=self._intent(origin,status='success',message='sealed success',
                                        result_summary={'observed_result':'confirmed'})
                    digest=intent.request_digest
                    before=self._execution_snapshot(task['id'],run['id'])
                    with self._connection_fault(boundary=boundary) as fired:
                        with self.assertRaises(SerializationFailure):
                            settlements.submit_intent(intent,domain=self.domain)
                    self.assertEqual([boundary],fired)
                    self.assertEqual(before,self._execution_snapshot(task['id'],run['id']))
                    self.assertEqual(0,self._transition_counts(run['id'])['receipts'])
                    self.assertIsNone(settlements.read_receipt(intent,domain=self.domain))
                    receipt=settlements.submit_intent(intent,domain=self.domain)
                    self.assertEqual(digest,receipt['request_digest'])
                    self.assertEqual('success',receipt['status'])
                    self.assertEqual('sealed success',dict(intent.payload)['message'])
                    self.assertEqual(1,self._transition_counts(run['id'])['transitions'])

        def test_s04_final_exact_delete_failure_rolls_back_terminal_and_defer_atomically(self):
            from psycopg.errors import SerializationFailure
            for kind in ('terminal','defer'):
                with self.subTest(kind=kind):
                    task,run,origin=self._leased_claim()
                    intent=(self._intent(origin,status='success') if kind=='terminal' else
                            self._intent(origin,kind='defer',reason='saved order continuation',
                                delay_seconds=0,stage='remote_sync',data={'original_order_id':'order-one'}))
                    before=self._execution_snapshot(task['id'],run['id'])
                    with self._connection_fault(boundary='final_delete') as fired:
                        with self.assertRaises(SerializationFailure):
                            settlements.submit_intent(intent,domain=self.domain)
                    self.assertEqual(['final_delete'],fired)
                    self.assertEqual(before,self._execution_snapshot(task['id'],run['id']))
                    self.assertEqual(0,self._transition_counts(run['id'])['receipts'])
                    receipt=settlements.submit_intent(intent,domain=self.domain)
                    self.assertEqual('success' if kind=='terminal' else 'queued',receipt['status'])
                    self.assertEqual('deleted_exact_token',receipt['lease_disposition'])
                    self.assertEqual([],self._execution_snapshot(task['id'],run['id'])['leases'])
                    self.assertEqual(1,self._transition_counts(run['id'])['transitions'])

        def test_s05_terminal_and_defer_commit_ack_loss_only_reads_original_receipt(self):
            from psycopg import OperationalError
            for kind in ('terminal','defer'):
                with self.subTest(kind=kind):
                    task,run,origin=self._leased_claim(task_type='extract_link' if kind=='defer' else 'plan_check',
                        data={'provider_id':'legacy','extract_poll_continuation':True,
                              'original_order_id':'existing-order'} if kind=='defer' else None)
                    intent=(self._intent(origin,status='success') if kind=='terminal' else
                            self._intent(origin,kind='defer',reason='continue existing order',
                                delay_seconds=0,stage='remote_sync',data={'original_order_id':'existing-order'}))
                    with self._connection_fault(boundary='commit_ack_lost') as fired:
                        with self.assertRaises(OperationalError):
                            settlements.submit_intent(intent,domain=self.domain)
                    self.assertEqual(['commit_ack_lost'],fired)
                    before=self._execution_snapshot(task['id'],run['id'])
                    counts=self._transition_counts(run['id'])
                    self.assertEqual([],before['leases'])
                    with patch.object(settlements,'_permit_fence',side_effect=AssertionError('ACK readback reentered fence')), \
                         patch.object(settlements,'_lock_original_managed_target',side_effect=AssertionError('ACK readback locked target')), \
                         patch('core.operations.run_log.append',side_effect=AssertionError('ACK readback appended log')), \
                         patch('core.operations.task_gateway.notify_dependency_ready',side_effect=AssertionError('ACK readback notified')):
                        confirmed=settlements.read_receipt(intent,domain=self.domain)
                        duplicate=settlements.submit_intent(intent,domain=self.domain)
                    self.assertEqual(confirmed['receipt_id'],duplicate['receipt_id'])
                    self.assertEqual(confirmed['transition_event_uuid'],duplicate['transition_event_uuid'])
                    self.assertEqual(counts,self._transition_counts(run['id']))
                    self.assertEqual(before,self._execution_snapshot(task['id'],run['id']))

        def test_s06_two_native_consumers_and_twenty_duplicates_commit_one_transition(self):
            from concurrent.futures import ThreadPoolExecutor
            import threading
            task,run,origin=self._leased_claim()
            intent=self._intent(origin,status='success',result_summary={'observed':'one'})
            original_read=settlements._read_cur
            barrier=threading.Barrier(2)
            thread_seen=set()
            lock=threading.Lock()
            def synchronized_read(cur,*args,**kwargs):
                with lock:
                    first=threading.get_ident() not in thread_seen
                    thread_seen.add(threading.get_ident())
                if first:
                    # Both genuine native transactions start before either
                    # permit/business lock can serialize first persistence.
                    barrier.wait(timeout=5)
                return original_read(cur,*args,**kwargs)
            with patch.object(settlements,'_read_cur',side_effect=synchronized_read):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures=[pool.submit(settlements.submit_intent,intent,domain=self.domain) for _ in range(2)]
                    receipts=[future.result(timeout=10) for future in futures]
            self.assertEqual(receipts[0]['receipt_id'],receipts[1]['receipt_id'])
            self.assertEqual(receipts[0]['transition_event_uuid'],receipts[1]['transition_event_uuid'])
            before=self._execution_snapshot(task['id'],run['id'])
            counts=self._transition_counts(run['id'])
            for _ in range(20):
                receipt=settlements.submit_intent(intent,domain=self.domain)
                self.assertEqual(receipts[0]['receipt_id'],receipt['receipt_id'])
            self.assertEqual(1,counts['receipts'])
            self.assertEqual(1,counts['transitions'])
            self.assertEqual(counts,self._transition_counts(run['id']))
            self.assertEqual(before,self._execution_snapshot(task['id'],run['id']))

        def test_s07_old_terminal_confirmation_preserves_new_run_generation_and_resources(self):
            task,run,origin=self._leased_claim()
            first_intent=self._intent(origin,status='failed',error='original observed failure')
            first=settlements.submit_intent(first_intent,domain=self.domain)
            newer=store.retry_runtime_task(task['id'])
            current_task=store.get_task(task['id'],include_events=False)
            _,new_run,new_origin=self._claim(current_task)
            token=store.acquire_account_lease(account_id=new_run['account_id'],run_id=new_run['id'],resource_family='unit')
            resource=store.register_resource(new_run['id'],resource_type='browser',external_id='generation-two',
                detail={'execution_id':new_origin['execution_id']})
            before=self._execution_snapshot(task['id'],newer['id'])
            for _ in range(3):
                self.assertEqual(first['receipt_id'],settlements.submit_intent(first_intent,domain=self.domain)['receipt_id'])
            self.assertEqual(before,self._execution_snapshot(task['id'],newer['id']))
            with self.assertRaises(OperationSettlementConflict):
                settlements.submit_intent(self._intent(origin,status='success'),domain=self.domain)
            self.assertEqual(before,self._execution_snapshot(task['id'],newer['id']))
            self.assertEqual(token,before['leases'][0]['lease_token'])
            self.assertEqual(resource['id'],before['resources'][0]['id'])

        def test_s12_old_defer_readback_preserves_same_run_g2_queued_running_and_terminal(self):
            for state in ('queued','running','terminal'):
                with self.subTest(state=state):
                    task,run,origin=self._leased_claim(task_type='extract_link',data={
                        'provider_id':'legacy','extract_poll_continuation':True,
                        'original_order_id':'existing-order','original_request_id':'existing-request'})
                    first_intent=self._intent(origin,kind='defer',reason='poll original order',
                        delay_seconds=0,stage='remote_sync',data={'original_order_id':'existing-order'})
                    first=settlements.submit_intent(first_intent,domain=self.domain)
                    _,_,next_origin=self._claim(task)
                    token=store.acquire_account_lease(account_id=run['account_id'],run_id=run['id'],resource_family='unit')
                    next_origin.update(lease_token=token,lease_requirement='final')
                    if state=='queued':
                        second_intent=self._intent(next_origin,kind='defer',reason='next generation poll',
                            delay_seconds=0,stage='remote_sync',data={'original_order_id':'existing-order'})
                        settlements.submit_intent(second_intent,domain=self.domain)
                    else:
                        if state=='terminal':
                            settlements.submit_intent(self._intent(next_origin,status='success'),domain=self.domain)
                    store.register_resource(run['id'],resource_type='provider_reference',external_id='existing-order',
                        detail={'execution_id':next_origin['execution_id']})
                    before=self._execution_snapshot(task['id'],run['id'])
                    counts=self._transition_counts(run['id'])
                    self.assertEqual('queued' if state=='queued' else 'running' if state=='running' else 'success',
                                     before['run'][0]['status'])
                    with patch.object(settlements,'_first_write_fence',side_effect=AssertionError('late defer rewrote G2')):
                        late=settlements.submit_intent(first_intent,domain=self.domain)
                        exact=settlements.read_receipt(first_intent,domain=self.domain)
                    self.assertEqual(first['receipt_id'],late['receipt_id'])
                    self.assertEqual(first['transition_event_uuid'],exact['transition_event_uuid'])
                    self.assertEqual(before,self._execution_snapshot(task['id'],run['id']))
                    self.assertEqual(counts,self._transition_counts(run['id']))
                    self.assertEqual('existing-order',before['run'][0]['data']['original_order_id'])
                    self.assertEqual('existing-request',before['run'][0]['data']['original_request_id'])

        def test_s07_uncommitted_old_execution_is_fenced_without_touching_successor_facts(self):
            from core.operations.settlement_contracts import OperationSettlementFenced
            task,run,origin=self._leased_claim()
            old_intent=self._intent(origin,status='success',result_summary={'observed':'old result'})
            new_execution=uuid.uuid4().hex
            new_token=uuid.uuid4().hex
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                # Explicit authoritative generation replacement for a fence
                # probe, not an inferred old-commit or business replay.
                cur.execute(f"UPDATE {common._table('operation_runs')} SET execution_id=%s WHERE id=%s",
                            (new_execution,run['id']))
                cur.execute(f"UPDATE {common._table('account_operation_leases')} SET lease_token=%s WHERE run_id=%s",
                            (new_token,run['id']))
            store.register_resource(run['id'],resource_type='browser',external_id='successor-browser',
                detail={'execution_id':new_execution})
            before=self._execution_snapshot(task['id'],run['id'])
            with self.assertRaises(OperationSettlementFenced):
                settlements.submit_intent(old_intent,domain=self.domain)
            self.assertIsNone(settlements.read_receipt(old_intent,domain=self.domain))
            self.assertEqual(before,self._execution_snapshot(task['id'],run['id']))
            self.assertEqual(0,self._transition_counts(run['id'])['receipts'])

        def test_commit_before_ack_pure_readback_without_current_execution_or_lease(self):
            task,run,origin=self._claim()
            intent=self._intent(origin)
            first=settlements.submit_intent(intent,domain=self.domain)
            with patch('core.bulk_operations.execution.fact_update',side_effect=AssertionError('readback emitted')), \
                 patch('core.operations.run_log.append',side_effect=AssertionError('readback logged')):
                second=settlements.submit_intent(intent,domain=self.domain)
                third=settlements.read_receipt(intent,domain=self.domain)
            self.assertEqual(first['receipt_id'],second['receipt_id'])
            self.assertEqual(first['transition_event_uuid'],third['transition_event_uuid'])
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f"SELECT count(*) n FROM {common._table('operation_events')} WHERE run_id=%s AND event_type='run.success'",(run['id'],))
                self.assertEqual(1,cur.fetchone()['n'])

        def test_same_execution_terminal_defer_conflict_and_multiple_defer_generations(self):
            task,run,origin=self._claim()
            first_intent=self._intent(origin,kind='defer',reason='temporary',delay_seconds=0,stage='queued')
            first=settlements.submit_intent(first_intent,domain=self.domain)
            with self.assertRaises(OperationSettlementConflict):
                settlements.submit_intent(self._intent(origin),domain=self.domain)
            _,_,next_origin=self._claim(task)
            next_intent=self._intent(next_origin,kind='defer',reason='again',delay_seconds=0,stage='queued')
            second=settlements.submit_intent(next_intent,domain=self.domain)
            self.assertNotEqual(first['receipt_id'],second['receipt_id'])
            self.assertEqual(first['receipt_id'],settlements.read_receipt(first_intent,domain=self.domain)['receipt_id'])

        def test_old_run_readback_never_overwrites_new_current_task(self):
            task,run,origin=self._claim()
            intent=self._intent(origin,status='failed',error='original failure')
            first=settlements.submit_intent(intent,domain=self.domain)
            retry=store.retry_runtime_task(int(task['id']))
            newer=int(retry['id'])
            settlements.submit_intent(intent,domain=self.domain)
            self.assertEqual(newer,store.get_task(int(task['id']))['last_run_id'])
            self.assertEqual(first['receipt_id'],settlements.read_receipt(intent,domain=self.domain)['receipt_id'])

        def test_split_operation_and_business_schema_keep_original_domain_after_env_change(self):
            from tests.support_pg import drop_schema
            from core.storage import records
            operation_schema = self.schema + '_op'
            self.addCleanup(drop_schema, operation_schema)
            with patch.dict(os.environ, {'OPERATION_TASK_DB_SCHEMA':operation_schema}):
                store.reset_ready()
                store.init()
                self.domain = self._domain(operation_schema, self.schema)
                account_id = records.insert_row(records.ACCOUNTS, {'email':'split@example.test'})
                task = store.create_runtime_task(task_type='plan_check', account_id=account_id,
                    email='split@example.test', trigger='test', resource_family='unit')
                task,run,origin = self._claim(task)
                intent = self._intent(origin)
                with patch.dict(os.environ, {'OPERATION_TASK_DB_SCHEMA':'test_unrelated', 'TURB_DB_SCHEMA':'test_unrelated'}):
                    receipt = settlements.submit_intent(intent,domain=self.domain)
                    self.assertEqual('success',receipt['status'])
                    with common.settlement_scope(self.domain):
                        self.assertEqual(operation_schema, common._schema_name())
                        self.assertEqual(self.schema, postgres.schema_name())
                        self.assertIsNotNone(records.get_row(records.ACCOUNTS,account_id))
                    with postgres.connect() as conn:
                        # Supplied tuple-row connection must be supported.
                        self.assertTrue(settlements.cleanup_blocks_permit(
                            origin['permit_id'],origin['execution_id'],domain=self.domain,conn=conn))
                    self.assertEqual(receipt['receipt_id'],settlements.read_receipt(intent,domain=self.domain)['receipt_id'])

        def test_original_token_deleted_atomically_readback_preserves_successor_token(self):
            from core.storage import records
            account_id = records.insert_row(records.ACCOUNTS,{'email':'exact-token@example.test'})
            task = store.create_runtime_task(task_type='plan_check',account_id=account_id,
                email='exact-token@example.test',trigger='test',resource_family='unit')
            task,run,origin = self._claim(task)
            token = store.acquire_account_lease(account_id=account_id,run_id=run['id'],resource_family='unit')
            origin.update(lease_token=token,lease_requirement='final')
            intent = self._intent(origin)
            receipt = settlements.submit_intent(intent,domain=self.domain)
            self.assertEqual('deleted_exact_token',receipt['lease_disposition'])
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f"SELECT count(*) n FROM {common._table('account_operation_leases')} WHERE lease_token=%s",(token,))
                self.assertEqual(0,cur.fetchone()['n'])
                cur.execute(f'''INSERT INTO {common._table('account_operation_leases')}
                    (account_id,resource_family,run_id,lease_token,expires_at)
                    VALUES (%s,'unit',%s,'successor-token',now()+interval '10 minutes')''',(account_id,run['id']))
            settlements.submit_intent(intent,domain=self.domain)
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f"SELECT lease_token FROM {common._table('account_operation_leases')} WHERE run_id=%s",(run['id'],))
                self.assertEqual('successor-token',cur.fetchone()['lease_token'])

        def test_original_managed_target_lock_and_single_fact_after_bulk_domain_change(self):
            from core.storage import records
            from core.storage.operations import bulk, bulk_schema
            from tests.bulk.test_bulk_storage import BulkStorageTests
            from psycopg.errors import LockNotAvailable, QueryCanceled
            bulk.reset_ready()
            bulk.init()
            account_id = records.insert_row(records.ACCOUNTS, {'email':'managed-origin@example.test'})
            with patch('core.bulk_operations.catalog.capture_settings',
                       return_value={'config_revision':'test-v1','effective_settings':{}}):
                selection = bulk.create_selection(request_key=uuid.uuid4().hex,
                    source={'kind':'ids','ids':[account_id]},operation_key='plan_check',
                    parameters={},config_revision='test-v1')
                selection = bulk.freeze_selection(selection['id'])
                batch = bulk.create_batch(request_key=uuid.uuid4().hex,selection_id=selection['id'],
                    selection_revision=1,operation_key='plan_check',parameters={},config_revision='test-v1',
                    max_concurrency=1)
                bulk.process_batch(batch['id'],lambda conn,targets,context:
                    BulkStorageTests.submitter(self,conn,targets,context))
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f'''UPDATE {common._table('operation_runs')} run
                    SET data=run.data || jsonb_build_object('bulk_target_round_id',link.target_round_id)
                    FROM {common._table('operation_batch_run_links')} link
                    WHERE link.run_id=run.id AND run.batch_id=%s''',(batch['id'],))
                cur.execute(f'''SELECT task.*,link.target_round_id FROM {common._table('operation_tasks')} task
                    JOIN {common._table('operation_batch_run_links')} link ON link.task_id=task.id
                    WHERE task.batch_id=%s''',(batch['id'],))
                task = dict(cur.fetchone())
            task,run,origin = self._claim(task)
            target_id = int(task['target_round_id'])
            intent = self._intent(origin)
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f"SELECT source_revision FROM {common._table('operation_batch_target_rounds')} WHERE id=%s",(target_id,))
                before = int(cur.fetchone()['source_revision'])
            with patch.object(bulk_schema,'_READY_KEY','another-domain-is-now-initialized'):
                with postgres.connect(row_factory=dict_row) as locker,locker.cursor() as cur:
                    cur.execute(f"SELECT id FROM {common._table('operation_batch_target_rounds')} WHERE id=%s FOR UPDATE",(target_id,))
                    with self.assertRaises((LockNotAvailable,QueryCanceled,TimeoutError)):
                        settlements.submit_intent(intent,domain=self.domain,deadline=time.monotonic()+0.15)
                first = settlements.submit_intent(intent,domain=self.domain)
                again = settlements.submit_intent(intent,domain=self.domain)
            self.assertEqual(first['receipt_id'],again['receipt_id'])
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f"SELECT source_revision,chain_state FROM {common._table('operation_batch_target_rounds')} WHERE id=%s",(target_id,))
                target = cur.fetchone()
                self.assertEqual(before+1,int(target['source_revision']))
                self.assertEqual('closed',target['chain_state'])
                cur.execute(f'''SELECT count(*) n FROM {common._table('operation_projection_outbox')}
                    WHERE target_round_id=%s AND source_revision=%s AND event_kind='fact_changed' ''',(target_id,before+1))
                self.assertEqual(1,cur.fetchone()['n'])

        def test_live_administrative_terminal_has_distinct_authority_backed_disposition(self):
            from core.operations import settlement
            from core.operations.settlement_contracts import OperationSettlementFenced
            task,run,origin = self._claim()
            intent = self._intent(origin,status='success')
            # Administrative legacy terminal is an independent authority. It
            # must never be represented as delivery of the frozen success.
            store.finish_run(run['id'],status='stopped',message='administrator stopped')
            with self.assertRaises(OperationSettlementFenced):
                settlements.submit_intent(intent,domain=self.domain)
            with patch.object(settlement,'superseded_handoff_ready',return_value=False):
                self.assertIsNone(settlements.reconcile_superseded(intent,domain=self.domain))
            with patch.object(settlement,'superseded_handoff_ready',return_value=True):
                proof = settlements.reconcile_superseded(intent,domain=self.domain)
            self.assertEqual('live_superseded',proof['disposition_kind'])
            self.assertFalse(proof['original_intent_committed'])
            self.assertEqual('stopped',proof['result']['status'])
            self.assertEqual(intent.request_digest,proof['request_digest'])
            self.assertIsNone(settlements.read_receipt(intent,domain=self.domain))
            self.assertFalse(settlements.cleanup_blocks_permit(
                origin['permit_id'],origin['execution_id'],domain=self.domain))
            # Repeated proof is pure readback after original scope cleanup.
            with patch.object(settlement,'superseded_handoff_ready',side_effect=AssertionError('proof rechecked live state')):
                again = settlements.reconcile_superseded(intent,domain=self.domain)
            self.assertEqual(proof['id'],again['id'])

        def test_settlement_stale_record_ready_never_initializes_under_business_locks(self):
            from core.storage import records
            account_id=records.insert_row(records.ACCOUNTS,{'email':'no-init-under-lock@example.test'})
            task=store.create_runtime_task(task_type='plan_check',account_id=account_id,
                email='no-init-under-lock@example.test',trigger='test',resource_family='unit')
            task,run,origin=self._claim(task)
            intent=self._intent(origin)
            with patch.object(records,'_READY_KEY','another-domain'), \
                 patch.object(records,'init',side_effect=AssertionError('settlement replayed records migration')):
                result=settlements.submit_intent(intent,domain=self.domain,deadline=time.monotonic()+3)
            self.assertEqual('success',result['status'])

        def test_unmanaged_cancel_run_lock_does_not_invert_settlement_task_lock(self):
            import threading
            task,run,origin=self._claim()
            intent=self._intent(origin)
            worker_pid=[]
            ready=threading.Event()
            output=[]
            errors=[]
            real_fence=settlements._permit_fence
            def fence(cur,*args,**kwargs):
                result=real_fence(cur,*args,**kwargs)
                worker_pid.append(cur.connection.info.backend_pid)
                ready.set()
                return result
            def worker():
                try:
                    output.append(settlements.submit_intent(intent,domain=self.domain,deadline=time.monotonic()+5))
                except BaseException as error:
                    errors.append(error)
            with postgres.connect(row_factory=dict_row) as cancellation,cancellation.cursor() as cur:
                cur.execute(f"SELECT id FROM {common._table('operation_runs')} WHERE id=%s FOR UPDATE",(run['id'],))
                with patch.object(settlements,'_permit_fence',side_effect=fence):
                    thread=threading.Thread(target=worker)
                    thread.start()
                    self.assertTrue(ready.wait(2),'settlement did not enter original permit fence')
                    waiting=False
                    until=time.monotonic()+2
                    with postgres.connect(row_factory=dict_row) as observer,observer.cursor() as inspect:
                        while time.monotonic()<until:
                            inspect.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s",(worker_pid[0],))
                            activity=inspect.fetchone()
                            if activity and activity['wait_event_type']=='Lock':
                                waiting=True
                                break
                            time.sleep(.01)
                    self.assertTrue(waiting,'settlement did not wait on held native Run lock')
                    # Native cancellation already owns Run and now needs Task.
                    # Task-first settlement would hold this and form a cycle.
                    cur.execute(f"SELECT id FROM {common._table('operation_tasks')} WHERE id=%s FOR UPDATE NOWAIT",(task['id'],))
                # Commit cancellation's lock scope before joining settlement.
            thread.join(6)
            self.assertFalse(thread.is_alive(),'settlement retained a native lock wait')
            if errors:
                raise errors[0]
            self.assertEqual('success',output[0]['status'])

        def test_nonblocking_cleanup_survives_permit_release_and_registry_pruning(self):
            from core.operations import settlement
            task,run,origin=self._claim()
            obligation={'action_kind':'completion_dependency','resource_identity':'existing-child-one',
                        'payload':{'parent_task_id':task['id'],'parent_run_id':run['id'],'child_task_id':123},
                        'blocks_permit':False}
            intent=seal_intent(kind='terminal',origin=origin,payload={'status':'success'},obligations=(obligation,))
            settlements.submit_intent(intent,domain=self.domain)
            with patch.object(settlement,'cleanup_handoff_ready',return_value=True):
                settlements.mark_cleanup_handoff(origin,domain=self.domain)
            # Simulate first typed local tail outage before ACK.
            with patch.object(settlements,'_execute_cleanup',side_effect=OSError('local store unavailable')):
                result=settlements.run_cleanup_once(domain=self.domain,permit_id=origin['permit_id'],execution_id=origin['execution_id'])
                self.assertEqual('pending',result['state'])
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f"UPDATE {permits._permit_table(self.schema)} SET released_at=now(),state='released' WHERE permit_id=%s",(origin['permit_id'],))
                cur.execute(f"UPDATE {common._table('operation_settlement_cleanup')} SET next_attempt_at=now() WHERE permit_id=%s",(origin['permit_id'],))
            with patch.object(settlement,'cleanup_handoff_ready',return_value=False), \
                 patch.object(settlements,'_execute_cleanup',return_value=None) as apply:
                result=settlements.run_cleanup_once(domain=self.domain)
            self.assertEqual('done',result['state'])
            apply.assert_called_once()

        def test_old_child_receipt_cannot_publish_dependency_for_new_current_run(self):
            parent=store.create_runtime_task(task_type='account_setup_retry',account_id=None,
                email='parent@example.test',trigger='test',resource_family='parent-unit')
            child,run,origin=self._claim()
            store.register_task_dependency(parent_source_system=parent['source_system'],
                parent_source_id=str(parent['id']),child_source_system=child['source_system'],
                child_source_id=str(child['id']),dependency_type='completion_child',
                payload={'parent_run_id':parent['run']['id']})
            intent=self._intent(origin)
            receipt=settlements.submit_intent(intent,domain=self.domain)
            store.retry_runtime_task(child['id'])
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f'''SELECT * FROM {common._table('operation_settlement_cleanup')}
                    WHERE receipt_id=%s AND action_kind='dependency_ready' ''',(receipt['receipt_id'],))
                job=dict(cur.fetchone())
            outcome=settlements._execute_cleanup(job,domain=self.domain)
            self.assertEqual('superseded',outcome['state'])
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f'''SELECT status FROM {common._table('operation_task_dependencies')}
                    WHERE child_source_id=%s''',(str(child['id']),))
                self.assertEqual('waiting',cur.fetchone()['status'])

        def test_startup_capability_and_actual_versions_fail_closed(self):
            from core.operations.settlement_contracts import OperationSettlementFenced
            self.assertEqual(1,settlements.verify_domain(self.domain)['schema_version'])
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f"UPDATE {common._table('operation_settlement_domains')} SET schema_version=999 WHERE domain_id=%s",(self.domain.domain_id,))
            with self.assertRaises(OperationSettlementFenced):
                settlements.verify_domain(self.domain)

        def test_disposition_blocks_later_original_resource_but_not_new_run_resource(self):
            from core.operations import settlement
            task,run,origin=self._claim()
            intent=self._intent(origin)
            store.finish_run(run['id'],status='stopped',message='administrative stop')
            with patch.object(settlement,'superseded_handoff_ready',return_value=True):
                proof=settlements.reconcile_superseded(intent,domain=self.domain)
            self.assertEqual('no_blocking_resources',proof['result']['resource_disposition'])
            self.assertFalse(settlements.cleanup_blocks_permit(
                origin['permit_id'],origin['execution_id'],domain=self.domain))
            original_resource=store.register_resource(run['id'],resource_type='sms_lease',
                external_id='original-late-resource',detail={'execution_id':origin['execution_id']})
            self.assertTrue(settlements.cleanup_blocks_permit(
                origin['permit_id'],origin['execution_id'],domain=self.domain))
            store.release_resource(original_resource['id'],state='released')
            newer=store.retry_runtime_task(task['id'])
            store.register_resource(newer['id'],resource_type='sms_lease',external_id='newer-run-resource')
            self.assertFalse(settlements.cleanup_blocks_permit(
                origin['permit_id'],origin['execution_id'],domain=self.domain))

        def test_scoped_native_create_split_business_schema_uses_initialized_account(self):
            from core.storage import records
            from tests.support_pg import drop_schema
            operation_schema=self.schema+'_create'
            self.addCleanup(drop_schema,operation_schema)
            account_id=records.insert_row(records.ACCOUNTS,{'email':'scoped-create@example.test',
                'access_token':'private-reference'})
            with patch.dict(os.environ,{'OPERATION_TASK_DB_SCHEMA':operation_schema}):
                store.reset_ready()
                store.init()
                domain=self._domain(operation_schema,self.schema)
            with common.settlement_scope(domain,deadline=time.monotonic()+3), \
                 patch.object(records,'init',side_effect=AssertionError('scoped native create triggered DDL')), \
                 patch.dict(os.environ,{'TURB_DB_SCHEMA':'test_wrong_current','OPERATION_TASK_DB_SCHEMA':'test_wrong_current'}):
                created=store.create_runtime_task(task_type='plan_check',account_id=account_id,
                    email='scoped-create@example.test',idempotency_key='scoped-native-create')
            self.assertEqual(account_id,created['run']['account_id'])
            with postgres.connect(row_factory=dict_row) as conn,conn.cursor() as cur:
                cur.execute(f'SELECT account_id FROM "{operation_schema}"."operation_tasks" WHERE id=%s',
                            (created['id'],))
                self.assertEqual(account_id,cur.fetchone()['account_id'])
