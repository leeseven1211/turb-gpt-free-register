"""提链取消以集合事务执行，保留 Run 竞争及账号占用归属。"""
from __future__ import annotations

import importlib
import os
from unittest.mock import patch

from psycopg import Cursor

from core.storage import postgres, records
from core.storage.operations import store as operation
from core.storage.extract_link import jobs
from tests.support_pg import PostgresTestCase


class ExtractBulkCancelTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._old_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        operation.reset_ready()
        if cls._old_schema is None:
            os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
        else:
            os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._old_schema
        super().tearDownClass()

    def setUp(self):
        operation.init()

    def bulk(self):
        return importlib.import_module("core.storage.extract_link.bulk_cancel")

    def batch(self):
        return operation.create_runtime_batch(batch_type="extract_link", title="集合取消", requested_count=501,
            data={"workbench_batch": True, "submission_complete": True})["id"]

    def tasks(self, batch_id, count=1, *, task_type="extract_link", account_id=None):
        # 合成无外部行为的真实 Task/Run，避免测试数据准备本身按目标开事务。
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {operation._table('operation_tasks')}
                (task_uuid,source_system,source_id,batch_id,task_type,target_type,account_id,status,data,requested_action)
                SELECT md5(random()::text), 'native_operations',md5(random()::text),%s,%s,'account',%s,'queued',
                       '{{"provider_id":"huanguang","mode":"extract_only"}}'::jsonb,%s
                FROM generate_series(1,%s) RETURNING id,task_uuid""", (batch_id,task_type,account_id,task_type,count))
            tasks=list(cur.fetchall())
            cur.execute(f"""INSERT INTO {operation._table('operation_runs')}
                (run_uuid,task_id,run_no,source_system,source_id,batch_id,account_id,resource_family,status,data)
                SELECT md5(random()::text),id,1,'native_operations',md5(random()::text),batch_id,account_id,
                       CASE WHEN account_id IS NULL THEN 'openai_interactive' ELSE 'fixture_'||id::text END,'queued',data
                FROM {operation._table('operation_tasks')} WHERE id=ANY(%s) RETURNING id,task_id""",
                ([row['id'] for row in tasks],))
            runs=list(cur.fetchall())
            cur.execute(f"""UPDATE {operation._table('operation_tasks')} task SET last_run_id=run.id,root_task_id=task.id
                FROM {operation._table('operation_runs')} run WHERE run.task_id=task.id AND task.id=ANY(%s)""",
                ([row['id'] for row in tasks],))
            return {row['task_id']:row['id'] for row in runs}

    def account(self, suffix, **changes):
        return self.seed(records.ACCOUNTS,[{"email":f"{suffix}@example.test","created_at":"2026-01-01T00:00:00",
            "updated_at":"2026-01-01T00:00:00","extract_link_status":"queued",
            "extract_link_queued_at":"2026-01-01T00:00:00",**changes}])[0]

    def test_cancels_501_in_chunks_and_preserves_running_other_type_and_batch(self):
        bulk=self.bulk()
        batch=self.batch(); selected=self.tasks(batch,501)
        running=self.tasks(batch); running_id=next(iter(running.values()))
        other_type=self.tasks(batch,task_type="live_check")
        other_batch=self.tasks(self.batch())
        with operation._connect() as conn,conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET status='running' WHERE id=%s",(running_id,))
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status='running' WHERE id=%s",(next(iter(running)),))
        statements=[]; original=Cursor.execute
        def execute(cur,query,*args,**kwargs):
            statements.append(str(query));return original(cur,query,*args,**kwargs)
        with patch.object(Cursor,'execute',execute),patch.object(postgres,'connect',wraps=postgres.connect) as connections:
            result=bulk.cancel_batch(batch)
        self.assertEqual({"batch_id":batch,"cancelled":501,"skipped":0,"failed":0},result)
        self.assertLess(len(statements),65)
        self.assertLessEqual(connections.call_count,6)
        with operation._connect() as conn,conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_events')} WHERE event_type='run.cancel_requested'")
            self.assertEqual(501,cur.fetchone()['n'])
            cur.execute(f"SELECT id,status,cancel_requested_at FROM {operation._table('operation_runs')}")
            runs={row['id']:row for row in cur.fetchall()}
        self.assertTrue(all(runs[run]['status']=='cancelled' and runs[run]['cancel_requested_at'] for run in selected.values()))
        self.assertEqual('running',runs[running_id]['status'])
        self.assertTrue(all(runs[run]['status']=='queued' for run in [*other_type.values(),*other_batch.values()]))
        self.assertEqual(0,bulk.cancel_batch(batch)['cancelled'])

    def test_account_writeback_preserves_success_material_and_new_claim(self):
        bulk=self.bulk();batch=self.batch()
        old=self.account('old',extract_link_error='旧错误')
        succeeded=self.account('success',extract_link_long_url='https://example.test/saved')
        newer=self.account('newer',extract_link_trigger='新占用')
        selected={}
        for acc in (old,succeeded,newer):selected.update(self.tasks(batch,account_id=acc))
        run_by_account={}
        with operation._connect() as conn,conn.cursor() as cur:
            cur.execute(f"SELECT id,account_id FROM {operation._table('operation_runs')} WHERE id=ANY(%s)",(list(selected.values()),))
            run_by_account={row['account_id']:row['id'] for row in cur.fetchall()}
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET created_at=now()-interval '5 minutes' WHERE id=%s",(run_by_account[newer],))
        records.patch_row(records.ACCOUNTS,newer,{"extract_link_queued_at":"2099-01-01T00:00:00"})
        jobs.save_provider_job(run_by_account[succeeded],'huanguang','saved-job',{"extraction_state":"unknown",
            "summary":{"extraction_ever_succeeded":True},"links":["https://example.test/saved"]},{})
        result=bulk.cancel_batch(batch)
        self.assertEqual({"batch_id":batch,"cancelled":2,"skipped":0,"failed":1},result)
        old_row=records.get_row(records.ACCOUNTS,old);success_row=records.get_row(records.ACCOUNTS,succeeded)
        self.assertEqual('cancelled',old_row['extract_link_status']);self.assertIsNone(old_row['extract_link_error'])
        self.assertEqual('success',success_row['extract_link_status']);self.assertTrue(success_row['extract_link_ok'])
        self.assertEqual('https://example.test/saved',success_row['extract_link_long_url'])
        self.assertEqual('新占用',records.get_row(records.ACCOUNTS,newer)['extract_link_trigger'])
        self.assertEqual('queued',records.get_row(records.ACCOUNTS,newer)['extract_link_status'])

    def test_race_claim_after_snapshot_is_skipped_without_cancel_request(self):
        bulk=self.bulk();batch=self.batch();selected=self.tasks(batch);run_id=next(iter(selected.values()))
        original=bulk._cancel_chunk
        def claim_then_cancel(rows):
            with operation._connect() as conn,conn.cursor() as cur:
                cur.execute(f"UPDATE {operation._table('operation_runs')} SET status='running' WHERE id=%s",(run_id,))
                cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status='running' WHERE id=%s",(next(iter(selected)),))
            return original(rows)
        with patch.object(bulk,'_cancel_chunk',side_effect=claim_then_cancel):result=bulk.cancel_batch(batch)
        self.assertEqual(1,result['skipped']);self.assertEqual(0,result['cancelled'])
        run=operation.get_run(run_id);self.assertEqual('running',run['status']);self.assertIsNone(run['cancel_requested_at'])

    def test_chunk_failure_rolls_back_run_task_lease_and_event_then_continues(self):
        bulk=self.bulk();batch=self.batch();selected=self.tasks(batch,501)
        with operation._connect() as conn,conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {operation._table('account_operation_leases')}
                (account_id,resource_family,run_id,lease_token,expires_at)
                VALUES (987,'fixture',%s,'lease-fixture',now()+interval '1 minute')""",(min(selected.values()),))
        original=bulk._write_cancel_events;calls=0
        def fail_once(cur,rows):
            nonlocal calls
            calls+=1
            if calls==1:raise RuntimeError('合成故障')
            return original(cur,rows)
        with patch.object(bulk,'_write_cancel_events',side_effect=fail_once):result=bulk.cancel_batch(batch)
        self.assertEqual({"batch_id":batch,"cancelled":1,"skipped":0,"failed":500},result)
        with operation._connect() as conn,conn.cursor() as cur:
            cur.execute(f"SELECT status,count(*) AS n FROM {operation._table('operation_runs')} GROUP BY status")
            self.assertEqual({'queued':500,'cancelled':1},{row['status']:row['n'] for row in cur.fetchall()})
            cur.execute(f"SELECT cancel_requested_at FROM {operation._table('account_operation_leases')} WHERE lease_token='lease-fixture'")
            self.assertIsNone(cur.fetchone()['cancel_requested_at'])

    def test_repeated_cancel_repairs_old_projection_and_keeps_ambiguous_claim(self):
        bulk=self.bulk();batch=self.batch();old=self.account('repair');unknown=self.account('ambiguous',extract_link_queued_at=None)
        selected={**self.tasks(batch,account_id=old),**self.tasks(batch,account_id=unknown)}
        for run_id in selected.values():operation.request_run_cancel(run_id)
        result=bulk.cancel_batch(batch)
        self.assertEqual({"batch_id":batch,"cancelled":0,"skipped":0,"failed":1},result)
        self.assertEqual('cancelled',records.get_row(records.ACCOUNTS,old)['extract_link_status'])
        self.assertEqual('queued',records.get_row(records.ACCOUNTS,unknown)['extract_link_status'])

    def test_account_version_change_after_cancel_preserves_reclaimed_account(self):
        bulk=self.bulk();batch=self.batch();account=self.account('version')
        self.tasks(batch,account_id=account)
        original=bulk._sync_accounts
        def newer_version(rows,**kwargs):
            records.patch_row(records.ACCOUNTS,account,{"extract_link_trigger":"重新占用"})
            return original(rows,**kwargs)
        with patch.object(bulk,'_sync_accounts',side_effect=newer_version):result=bulk.cancel_batch(batch)
        self.assertEqual(1,result['failed']);self.assertEqual(0,result['cancelled'])
        value=records.get_row(records.ACCOUNTS,account)
        self.assertEqual('queued',value['extract_link_status']);self.assertEqual('重新占用',value['extract_link_trigger'])

    def test_other_active_operation_and_terminal_or_missing_account_need_no_writeback(self):
        bulk=self.bulk();batch=self.batch();other=self.batch()
        active=self.account('active',extract_link_status='running')
        terminal=self.account('terminal',extract_link_status='success',extract_link_ok=True,extract_link_message='保留成功')
        missing=self.account('missing')
        self.tasks(other,account_id=active)
        for account in (active,terminal,missing):self.tasks(batch,account_id=account)
        records.delete_rows(records.ACCOUNTS,[missing])
        result=bulk.cancel_batch(batch)
        self.assertEqual({"batch_id":batch,"cancelled":3,"skipped":0,"failed":0},result)
        self.assertEqual('running',records.get_row(records.ACCOUNTS,active)['extract_link_status'])
        value=records.get_row(records.ACCOUNTS,terminal)
        self.assertEqual('success',value['extract_link_status']);self.assertEqual('保留成功',value['extract_link_message'])

    def test_missing_snapshot_version_uses_historical_time_guard_for_new_account_row(self):
        bulk=self.bulk();batch=self.batch();self.tasks(batch,account_id=123)
        original=bulk._sync_accounts
        def restore_account(rows,**kwargs):
            with operation._connect() as conn,conn.cursor() as cur:
                cur.execute(f"""INSERT INTO {postgres.qualified(records.ACCOUNTS.name)}
                    (id,email,created_at,updated_at,extract_link_status,data)
                    VALUES (123,'restored@example.test','2026-01-01T00:00:00','2026-01-01T00:00:00','queued','{{}}'::jsonb)""")
            return original(rows,**kwargs)
        with patch.object(bulk,'_sync_accounts',side_effect=restore_account):result=bulk.cancel_batch(batch)
        self.assertEqual(1,result['failed'])
        self.assertEqual('queued',records.get_row(records.ACCOUNTS,123)['extract_link_status'])
