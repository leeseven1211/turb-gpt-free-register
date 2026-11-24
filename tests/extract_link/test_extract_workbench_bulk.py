"""提链集合本地事实不执行远端请求。"""
from __future__ import annotations

import os
from unittest.mock import patch

from psycopg import Cursor

from core.storage.operations import store as operation
from core.storage.extract_link import jobs
from core.extract_link import service
from tests.support_pg import PostgresTestCase
from tests.extract_link import test_extract_workbench_batches as fixtures


class ExtractWorkbenchBulkTests(PostgresTestCase):
    accounts = fixtures.ExtractWorkbenchBatchStorageTests.accounts
    provider_patches = fixtures.ExtractWorkbenchBatchStorageTests.provider_patches

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.previous = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        operation.reset_ready()
        if cls.previous is None:
            os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
        else:
            os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.previous
        super().tearDownClass()

    def setUp(self):
        operation.init()

    def finished_task(self, account_id=None, provider="legacy", source="native_operations"):
        task = operation.create_runtime_task(task_type="extract_link", account_id=account_id,
            email="synthetic@example.test", source_system=source,
            data={"provider_id": provider, "mode": "auto_payment"})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET status='success' WHERE id=%s",
                        (task["run"]["id"],))
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status='success' WHERE id=%s",
                        (task["id"],))
        return task

    def test_payment_entries_reads_collection_and_keeps_legacy_identity_guard(self):
        from core.extract_link import workbench_bulk

        account = self.accounts([{"extract_link_job_id": "remote-old",
                                  "extract_link_long_url": "https://pay.example.test/legacy"}])[0]
        first = self.finished_task()
        legacy = self.finished_task(account)
        jobs.save_provider_job(first["run"]["id"], "legacy", "saved",
            {"payment_artifact": {"payment_url": "https://pay.example.test/current", "amount": 0}},
            {"job_secret": "synthetic-private"})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET result_summary=%s::jsonb WHERE id=%s",
                        ('{"has_link":true,"remote_job_id":"different-order"}', legacy["run"]["id"]))
        queries = []
        original = Cursor.execute
        def execute(cur, query, *args, **kwargs):
            queries.append(str(query))
            return original(cur, query, *args, **kwargs)
        with patch.object(Cursor, "execute", execute):
            result = workbench_bulk.payment_entries([first["id"], legacy["id"], 9999, first["id"]])
        self.assertEqual(1, result["duplicate_count"])
        self.assertEqual(["updated", "skipped", "skipped"], [item["status"] for item in result["items"]])
        self.assertEqual(0, result["items"][0]["entry"]["amount"])
        self.assertNotIn("synthetic-private", repr(result))
        self.assertLessEqual(len([query for query in queries if query.lstrip().upper().startswith("SELECT")]), 3)

    def test_sync_creates_runs_and_private_provider_clones_as_collection(self):
        from core.extract_link import workbench_bulk

        tasks = [self.finished_task() for _ in range(12)]
        for task in tasks:
            jobs.save_provider_job(task["run"]["id"], "legacy", f"order-{task['id']}",
                {"extraction_state": "succeeded", "payment_state": "succeeded"},
                {"job_secret": f"synthetic-private-{task['id']}"})
        queries = []
        original = Cursor.execute
        def execute(cur, query, *args, **kwargs):
            queries.append(str(query))
            return original(cur, query, *args, **kwargs)
        with self.provider_patches(), patch.object(service, "_bool_setting", return_value=False), \
                patch.object(service, "_provider_enabled", return_value=False), \
                patch.object(Cursor, "execute", execute), operation._connect() as conn:
            receipts = workbench_bulk.sync_status_many([str(task["id"]) for task in tasks] + ["9999"], {}, conn=conn)
        self.assertEqual(12, sum(item.status == "updated" for item in receipts))
        self.assertEqual("task_not_found", receipts[-1].reason_code)
        self.assertNotIn("synthetic-private", repr(receipts))
        self.assertLessEqual(len(queries), 15)
        for task, item in zip(tasks, receipts):
            new_run = item.data["run_id"]
            self.assertNotEqual(task["run"]["id"], new_run)
            saved = jobs.get_provider_job_private(new_run)
            self.assertEqual(f"synthetic-private-{task['id']}", saved["private_data"]["job_secret"])
            self.assertEqual(task["run"]["id"], operation.get_run(new_run)["data"]["provider_job_run_id"])

    def test_managed_sync_retains_target_ownership_and_projection_change(self):
        from core.extract_link import workbench_bulk
        from core.storage.operations import bulk
        import uuid

        bulk.reset_ready()
        bulk.init()
        account_id = self.accounts([{}])[0]
        task = self.finished_task(account_id)
        jobs.save_provider_job(task['run']['id'],'legacy','managed-saved',{}, {'job_secret':'private-managed'})
        with patch('core.bulk_operations.catalog.capture_settings',return_value={
                'config_revision':'test-v1','effective_settings':{}}):
            selection = bulk.create_selection(request_key=uuid.uuid4().hex,source={'kind':'ids','ids':[account_id]},
                operation_key='plan_check',parameters={},config_revision='test-v1')
            selection = bulk.freeze_selection(selection['id'])
            batch = bulk.create_batch(request_key=uuid.uuid4().hex,selection_id=selection['id'],
                selection_revision=1,operation_key='plan_check',parameters={},config_revision='test-v1',max_concurrency=1)
        bulk.materialize_targets(batch['id'])
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {operation._table('operation_batch_target_rounds')} WHERE batch_id=%s",(batch['id'],))
            target_id = cur.fetchone()['id']
            cur.execute(f"UPDATE {operation._table('operation_batch_target_rounds')} SET admission_state='submitted',"
                "chain_state='started',chain_started_at=now(),next_execution_generation=2 WHERE id=%s",(target_id,))
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET batch_id=%s,"
                "data=data||jsonb_build_object('bulk_target_round_id',%s::bigint) WHERE id=%s",
                (batch['id'],target_id,task['run']['id']))
            cur.execute(f"INSERT INTO {operation._table('operation_batch_run_links')}"
                "(target_round_id,task_id,run_id,task_id_snapshot,run_id_snapshot,step_key,execution_generation,relation)"
                " VALUES (%s,%s,%s,%s,%s,'extract_link',1,'owned_root')",
                (target_id,task['id'],task['run']['id'],task['id'],task['run']['id']))
        locks = []
        original = Cursor.execute
        def execute(cur,query,*args,**kwargs):
            text = str(query)
            if 'FOR UPDATE' in text:
                locks.append(text)
            return original(cur,query,*args,**kwargs)
        with self.provider_patches(), patch.object(Cursor,'execute',execute), operation._connect() as conn:
            result = workbench_bulk.sync_status_many([str(task['id'])],{},conn=conn)
        self.assertEqual('updated',result[0].status)
        run = operation.get_run(result[0].data['run_id'])
        self.assertEqual(target_id,run['data']['bulk_target_round_id'])
        self.assertEqual(batch['id'],run['batch_id'])
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT target_round_id,relation,step_key FROM {operation._table('operation_batch_run_links')} "
                "WHERE run_id=%s",(run['id'],))
            link = cur.fetchone()
            self.assertIsNotNone(link)
            self.assertEqual((target_id,'owned_continuation','extract_link'),
                (link['target_round_id'],link['relation'],link['step_key']))
            cur.execute(f"SELECT source_revision,chain_state FROM {operation._table('operation_batch_target_rounds')} WHERE id=%s",(target_id,))
            target = cur.fetchone()
            self.assertGreater(target['source_revision'],0)
            self.assertEqual('started',target['chain_state'])
        target_lock = next(index for index,sql in enumerate(locks) if 'operation_batch_target_rounds' in sql)
        account_lock = next(index for index,sql in enumerate(locks) if '"registered_accounts"' in sql)
        task_lock = next(index for index,sql in enumerate(locks) if '"operation_tasks"' in sql)
        self.assertLess(target_lock,account_lock)
        self.assertLess(account_lock,task_lock)

    def test_sync_skips_source_changed_while_waiting_for_locks(self):
        from core.extract_link import workbench_bulk
        from core.storage.extract_link import workbench_bulk as storage
        task = self.finished_task()
        jobs.save_provider_job(task['run']['id'],'legacy','saved',{}, {})
        original = storage._lock_sync_sources
        def advance(cur,conn,ids):
            sources = original(cur,conn,ids)
            operation.retry_runtime_task(task['id'],conn=conn)
            return sources
        with self.provider_patches(),patch.object(storage,'_lock_sync_sources',advance),operation._connect() as conn:
            result = workbench_bulk.sync_status_many([str(task['id'])],{},conn=conn)
        self.assertEqual('skipped',result[0].status)
        self.assertEqual('task_active',result[0].reason_code)
        with operation._connect() as conn,conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_runs')} WHERE task_id=%s",(task['id'],))
            self.assertEqual(2,cur.fetchone()['n'])

    def test_sync_skips_active_and_wrong_kind_without_changing_runs(self):
        from core.extract_link import workbench_bulk

        queued = operation.create_runtime_task(task_type="extract_link", account_id=None, email="a")
        wrong = operation.create_runtime_task(task_type="live_check", account_id=None, email="b")
        with self.provider_patches(), operation._connect() as conn:
            result = workbench_bulk.sync_status_many([str(queued["id"]), str(wrong["id"])], {}, conn=conn)
        self.assertTrue(all(item.status == "skipped" for item in result))
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_runs')} WHERE task_id=%s",
                        (queued["id"],))
            self.assertEqual(1, cur.fetchone()["n"])

    def test_hidden_task_cannot_be_synced_or_return_payment_artifact(self):
        from core.extract_link import workbench_bulk

        task = self.finished_task()
        jobs.save_provider_job(task["run"]["id"], "legacy", "saved",
            {"payment_artifact": {"payment_url": "https://pay.example.test/current"}}, {})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} "
                        "SET data=data||'{\"deleted_by_user\":true}'::jsonb WHERE id=%s", (task["id"],))
        entries = workbench_bulk.payment_entries([task["id"]])
        self.assertEqual("task_not_found", entries["items"][0]["reason_code"])
        with operation._connect() as conn:
            result = workbench_bulk.sync_status_many([str(task["id"])], {}, conn=conn)
        self.assertEqual("task_not_found", result[0].reason_code)

    def test_sync_rollback_keeps_source_run_and_no_copied_private_snapshot(self):
        from core.extract_link import workbench_bulk

        task = self.finished_task()
        jobs.save_provider_job(task["run"]["id"], "legacy", "saved", {}, {"job_secret": "private-local"})
        with self.provider_patches(), self.assertRaisesRegex(RuntimeError, "simulate"):
            with operation._connect() as conn:
                workbench_bulk.sync_status_many([str(task["id"])], {}, conn=conn)
                raise RuntimeError("simulate")
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT last_run_id FROM {operation._table('operation_tasks')} WHERE id=%s",
                        (task["id"],))
            self.assertEqual(task["run"]["id"], cur.fetchone()["last_run_id"])
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('extract_link_provider_jobs')}")
            self.assertEqual(1, cur.fetchone()["n"])

    def test_sync_same_account_only_queues_one_selected_task(self):
        from core.extract_link import workbench_bulk

        account_id = self.accounts([{}])[0]
        tasks = [self.finished_task(account_id) for _ in range(2)]
        for task in tasks:
            jobs.save_provider_job(task["run"]["id"], "legacy", str(task["id"]), {}, {})
        with self.provider_patches(), operation._connect() as conn:
            result = workbench_bulk.sync_status_many([str(task["id"]) for task in tasks], {}, conn=conn)
        self.assertEqual(["updated", "skipped"], [item.status for item in result])
        self.assertEqual("account_busy", result[1].reason_code)

    def test_independent_payment_sync_reuses_saved_order_without_new_payment_intent(self):
        from core.extract_link import workbench_bulk

        task = self.finished_task(provider="huanguang")
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} "
                        "SET data=data||'{\"payment_source\":\"xxsyun\",\"link_type\":\"upi\"}'::jsonb WHERE id=%s",
                        (task["id"],))
            cur.execute(f"""INSERT INTO {operation._table('extract_link_payment_orders')}
                (task_id,origin_run_id,extract_provider_id,extract_job_id,material_job_id,payment_provider,
                 attempt_no,api_base,idempotency_key,material_fingerprint,private_encrypted)
                VALUES (%s,%s,'huanguang','saved-extract','saved-material','xxsyun',1,
                    'https://pay.example.test','saved-intent','fingerprint','private-local-ciphertext')""",
                (task["id"], task["run"]["id"]))
        with patch.object(service, "_bool_setting", return_value=False), \
                patch.object(service, "_provider_enabled", return_value=False), operation._connect() as conn:
            result = workbench_bulk.sync_status_many([str(task["id"])], {}, conn=conn)
        self.assertEqual("updated", result[0].status)
        run = operation.get_run(result[0].data["run_id"])
        self.assertEqual("sync_status", run["data"]["workbench_action"])
        self.assertFalse(run["data"]["independent_payment_new_attempt"])
        self.assertFalse(run["data"]["independent_payment_refresh_material"])
        self.assertNotIn("private-local-ciphertext", repr(result))
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('extract_link_payment_orders')}")
            self.assertEqual(1, cur.fetchone()["n"])
