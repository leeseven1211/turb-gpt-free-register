"""多个历史批次的即时统计必须集合计算，保持原状态优先级。"""
from unittest.mock import patch

from core.storage.operations import projection, store
from core.storage.operations.bulk_retry_projection import refresh_batches_many
from tests.support_pg import PostgresTestCase


class RetryBatchProjectionTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()

    def batches(self, count):
        output = []
        for index in range(count):
            batch = store.create_runtime_batch(batch_type="twofa_setup", title=f"isolated-{index}",
                                               requested_count=1)
            task = store.create_runtime_task(task_type="twofa_setup", account_id=None,
                email=f"batch-{index}@example.test", batch_id=batch["id"])
            output.append((batch["id"], task["id"]))
        return output

    def test_twenty_batches_have_bounded_sql(self):
        from psycopg import Cursor
        fixtures = self.batches(20)
        statements = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed'")
            with patch.object(Cursor, "execute", measured):
                refresh_batches_many(cur, [batch_id for batch_id, _ in fixtures])
            cur.execute(f"SELECT status,failed_count FROM {store._table('operation_batches')} ORDER BY id")
            self.assertEqual([dict(row) for row in cur.fetchall()],
                             [{"status": "failed", "failed_count": 1}] * 20)
        self.assertLessEqual(len(statements), 5, f"{len(statements)} SQL")

    def test_status_counts_root_child_and_completion_match_original(self):
        fixtures = self.batches(13)
        statuses = ["queued", "running", "success", "partial_success", "failed",
                    "deactivated", "unsupported", "attention_required", "interrupted",
                    "request_unknown", "manual_reconcile", "stopped", "cancelled"]
        with store._connect() as conn, conn.cursor() as cur:
            for (_, task_id), status in zip(fixtures, statuses, strict=True):
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status=%s WHERE id=%s", (status, task_id))
            projection._refresh_batches(cur, [batch_id for batch_id, _ in fixtures])
            cur.execute(f"""SELECT id,status,queued_count,running_count,success_count,partial_count,
                failed_count,attention_count,stopped_count,cancelled_count,
                completed_at IS NOT NULL AS completed FROM {store._table('operation_batches')} ORDER BY id""")
            expected = [dict(row) for row in cur.fetchall()]
            cur.execute(f"UPDATE {store._table('operation_batches')} SET status='queued',completed_at=NULL")
            refresh_batches_many(cur, [batch_id for batch_id, _ in fixtures])
            cur.execute(f"""SELECT id,status,queued_count,running_count,success_count,partial_count,
                failed_count,attention_count,stopped_count,cancelled_count,
                completed_at IS NOT NULL AS completed FROM {store._table('operation_batches')} ORDER BY id""")
            self.assertEqual([dict(row) for row in cur.fetchall()], expected)

    def test_latest_child_status_and_skipped_count_keep_original_precedence(self):
        fixtures = self.batches(4)
        with store._connect() as conn, conn.cursor() as cur:
            for index, (batch_id, task_id) in enumerate(fixtures):
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='success' WHERE id=%s", (task_id,))
                if index < 3:
                    child = store.create_runtime_task(task_type="twofa_setup", account_id=None,
                        email=f"child-{index}@example.test", batch_id=batch_id, parent_task_id=task_id, conn=conn)
                    cur.execute(f"""UPDATE {store._table('operation_tasks')}
                        SET status=%s,root_task_id=%s WHERE id=%s""",
                        (("failed", "queued", "waiting")[index], task_id, child["id"]))
                    cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='success' WHERE id=%s", (task_id,))
                else:
                    cur.execute(f"UPDATE {store._table('operation_batches')} SET skipped_count=1 WHERE id=%s", (batch_id,))
            refresh_batches_many(cur, [batch_id for batch_id, _ in fixtures])
            cur.execute(f"SELECT status FROM {store._table('operation_batches')} ORDER BY id")
            self.assertEqual([row["status"] for row in cur.fetchall()],
                             ["partial_success", "queued", "running", "partial_success"])

    def test_empty_and_missing_batches_keep_queued_without_completion(self):
        batch = store.create_runtime_batch(batch_type="twofa_setup", title="empty", requested_count=0)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_batches')} SET status='failed',completed_at=now()")
            refresh_batches_many(cur, [batch["id"], batch["id"], 999999])
            cur.execute(f"""SELECT status,completed_at,queued_count,failed_count
                FROM {store._table('operation_batches')} WHERE id=%s""", (batch["id"],))
            self.assertEqual(dict(cur.fetchone()), {"status": "queued", "completed_at": None,
                                                   "queued_count": 0, "failed_count": 0})

    def test_managed_batch_counts_are_left_to_managed_outbox_projection(self):
        from core.storage.operations import bulk
        bulk.reset_ready()
        bulk.init()
        batch_id, task_id = self.batches(1)[0]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s", (task_id,))
            # 控制表字段由真实批次契约要求；这里仅制造已存在控制记录的过滤条件。
            cur.execute(f"""INSERT INTO {store._table('operation_selections')}
                (selection_kind,request_key,request_hash,query_version,query_spec,action_key,
                 action_version,parameters_hash,config_revision,status,total_count,selected_at,expires_at)
                VALUES ('explicit_ids','test-managed-selection','hash',1,'{{}}'::jsonb,'plan_check',
                    1,'hash','12','ready',0,now(),now()+interval '1 hour')
                RETURNING id""")
            selection_id = cur.fetchone()["id"]
            cur.execute(f"""INSERT INTO {store._table('operation_batch_controls')}
                (batch_id,manager_version,selection_id,action_key,action_version,result_version,
                 parameters,config_snapshot,config_revision,request_key,request_hash,state,desired_workers,counts)
                VALUES (%s,1,%s,'plan_check',1,1,'{{}}'::jsonb,'{{}}'::jsonb,'12',
                    'test-managed-control','hash','active',1,'{{}}'::jsonb)""", (batch_id, selection_id))
            refresh_batches_many(cur, [batch_id])
            cur.execute(f"SELECT status,failed_count FROM {store._table('operation_batches')} WHERE id=%s", (batch_id,))
            self.assertEqual(dict(cur.fetchone()), {"status": "queued", "failed_count": 0})

    def test_five_hundred_and_one_batch_ids_are_split_before_queries(self):
        from psycopg import Cursor
        fixtures = self.batches(1)
        observed = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            for parameter in params or ():
                if isinstance(parameter, list):
                    observed.append(len(parameter))
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn, conn.cursor() as cur, patch.object(Cursor, "execute", measured):
            refresh_batches_many(cur, [fixtures[0][0], *range(10000, 10500)])
        self.assertEqual(max(observed), 500)
        self.assertIn(1, observed)

    def test_historical_negative_skipped_count_still_counts_as_nonzero(self):
        batch = store.create_runtime_batch(batch_type="twofa_setup", title="historical", requested_count=0)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_batches')} SET skipped_count=-1 WHERE id=%s", (batch["id"],))
            refresh_batches_many(cur, [batch["id"]])
            cur.execute(f"SELECT status,completed_at IS NOT NULL AS completed FROM {store._table('operation_batches')} WHERE id=%s",
                        (batch["id"],))
            self.assertEqual(dict(cur.fetchone()), {"status": "failed", "completed": True})
