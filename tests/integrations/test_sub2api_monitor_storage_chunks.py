"""Sub2API 巡检集合写入的 501 条边界与调用方整波回滚。"""
from __future__ import annotations

import json
from unittest.mock import patch

from psycopg import Cursor

from core.storage import postgres, records, sub2api, sub2api_monitor
from tests.support_pg import PostgresTestCase


class Sub2ApiMonitorStorageChunkTests(PostgresTestCase):
    def setUp(self):
        records.init()
        sub2api.init()
        self.backend = "monitor-chunk-backend"
        with records.transaction() as conn, conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {records._qualified(records.ACCOUNTS)} (email,created_at,updated_at)
                    SELECT 'chunk-'||number||'@example.test',%s,%s
                    FROM generate_series(1,501) number RETURNING id""",
                (records._now(), records._now()),
            )
            self.accounts = sorted(row["id"] for row in cur.fetchall())
        self.owner = self.accounts[0]
        self.email = records.get_row(records.ACCOUNTS, self.owner)["email"]
        self.filename = "monitor-chunk.json"
        self.credential_id = records.insert_row(records.CODEX_CREDENTIALS, {
            "filename": self.filename, "email": self.email,
            "content": {"email": self.email, "access_token": "isolated-access",
                        "refresh_token": "isolated-refresh"},
        })

    def repair_states(self):
        with records.transaction() as conn:
            conn.execute(
                f"""INSERT INTO {postgres.qualified('sub2api_monitor_repairs')} (backend,account_id,data)
                    SELECT %s,id,jsonb_build_object('stage','sync_wait','manual_requested',true,
                        'remote_account_ids',jsonb_build_array(100000+id),
                        'superseded_targets',jsonb_build_object((100000+id)::text,200000+id))
                    FROM {records._qualified(records.ACCOUNTS)} WHERE id=ANY(%s)""",
                (self.backend, self.accounts),
            )
        return {
            account_id: {"stage": "waiting_manual", "attempt_count": 2,
                         "remote_account_ids": [100000 + account_id, 300000 + account_id],
                         "superseded_targets": {str(200000 + account_id): 400000 + account_id}}
            for account_id in self.accounts
        }

    def intent(self):
        return {
            "filename": self.filename, "credential_id": self.credential_id,
            "account_id": self.owner, "email": self.email,
            "generation": "new-generation", "remote_account_ids": list(range(5000, 5501)),
        }

    def seed_jobs(self):
        with records.transaction() as conn:
            conn.execute(
                f"""INSERT INTO {sub2api._table()}
                    (filename,backend,target_key,remote_account_id,account_id,credential_id,email,
                     generation,status,stage,trigger,dispatch_requested,error_code)
                    SELECT %s,%s,target,target,%s,%s,%s,
                        'old-generation','success','complete','sub2api_monitor',FALSE,'old-code'
                    FROM generate_series(5000,5500) target""",
                (self.filename, self.backend, self.owner, self.credential_id, self.email),
            )

    def rows(self, kind):
        table = (postgres.qualified("sub2api_monitor_repairs") if kind == "repairs" else sub2api._table())
        order = "account_id" if kind == "repairs" else "id"
        with records.transaction() as conn:
            return list(conn.execute(f"SELECT * FROM {table} WHERE backend=%s ORDER BY {order}",
                                     (self.backend,)).fetchall())

    @staticmethod
    def json_rows(query, params):
        if "jsonb_to_recordset" not in str(query):
            return None
        for value in params or ():
            if isinstance(value, str) and value.startswith("["):
                return json.loads(value)
        return None

    def execute_bounded(self, callback):
        sizes = []
        execute = Cursor.execute
        with records.transaction() as conn:
            def bounded(cursor, query, params=None, **kwargs):
                rows = self.json_rows(query, params)
                if rows is not None:
                    self.assertIs(cursor.connection, conn, "分块必须共享调用方连接")
                    sizes.append(len(rows))
                    self.assertLessEqual(len(rows), 500, "批量语句JSON载荷超过500条")
                return execute(cursor, query, params, **kwargs)

            with patch.object(Cursor, "execute", bounded):
                callback(conn)
        self.assertEqual(sum(sizes), 501)
        self.assertGreaterEqual(len(sizes), 2)

    def update_jobs(self, conn):
        # 复现调用者在任何更新块之前一次锁齐整个 Job 集合的边界。
        patches = list(conn.execute(
            f"SELECT * FROM {sub2api._table()} WHERE backend=%s ORDER BY id FOR UPDATE",
            (self.backend,)).fetchall())
        for row in patches:
            row.update(generation="new-generation", status="pending", stage="collection-updated",
                       error_code=None, error=None, dispatch_requested=True)
        sub2api_monitor._update_jobs(conn, patches)

    def assert_second_chunk_rollback(self, kind, callback):
        before = self.rows(kind)
        execute = Cursor.execute
        writes = 0

        def fail_second(cursor, query, params=None, **kwargs):
            nonlocal writes
            if self.json_rows(query, params) is not None:
                writes += 1
                if writes == 2:
                    raise RuntimeError("second chunk failed")
            return execute(cursor, query, params, **kwargs)

        with self.assertRaisesRegex(RuntimeError, "second chunk failed"):
            with records.transaction() as conn:
                conn.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)}
                    SET data=data||'{{"wave_note":"must roll back"}}'::jsonb WHERE id=%s""", (self.owner,))
                with patch.object(Cursor, "execute", fail_second):
                    callback(conn)
        self.assertEqual(writes, 2)
        self.assertEqual(self.rows(kind), before, "后块失败不得留下前块写入")
        self.assertNotIn("wave_note", records.get_row(records.ACCOUNTS, self.owner))

    def test_501_repair_updates_have_bounded_payloads_and_keep_replacement_mapping(self):
        states = self.repair_states()
        self.execute_bounded(lambda conn: sub2api_monitor.save_repairs(conn, self.backend, states))
        rows = self.rows("repairs")
        self.assertEqual(len(rows), 501)
        for row in rows:
            account_id = row["account_id"]
            self.assertEqual(row["data"]["stage"], "waiting_manual")
            self.assertTrue(row["data"]["manual_requested"])
            self.assertEqual(row["data"]["remote_account_ids"], [400000 + account_id, 300000 + account_id])
            self.assertEqual(row["data"]["superseded_targets"], {
                str(100000 + account_id): 400000 + account_id,
                str(200000 + account_id): 400000 + account_id,
            })

    def test_501_new_sync_targets_have_bounded_payloads_and_keep_frozen_identity(self):
        self.execute_bounded(lambda conn: sub2api_monitor.queue_sync_many(conn, self.backend, [self.intent()]))
        rows = self.rows("jobs")
        self.assertEqual([row["remote_account_id"] for row in rows], list(range(5000, 5501)))
        self.assertEqual({(row["credential_id"], row["account_id"], row["generation"], row["status"])
                          for row in rows}, {(self.credential_id, self.owner, "new-generation", "pending")})

    def test_501_job_patches_have_bounded_payloads_and_keep_all_updates(self):
        self.seed_jobs()
        self.execute_bounded(self.update_jobs)
        rows = self.rows("jobs")
        self.assertEqual(len(rows), 501)
        self.assertEqual({(row["generation"], row["status"], row["stage"], row["error_code"])
                          for row in rows}, {("new-generation", "pending", "collection-updated", None)})
        self.assertTrue(all(row["dispatch_requested"] for row in rows))

    def test_second_repair_chunk_failure_rolls_back_every_repair_and_caller_write(self):
        states = self.repair_states()
        self.assert_second_chunk_rollback(
            "repairs", lambda conn: sub2api_monitor.save_repairs(conn, self.backend, states))

    def test_second_new_target_chunk_failure_rolls_back_every_new_job_and_caller_write(self):
        self.assert_second_chunk_rollback(
            "jobs", lambda conn: sub2api_monitor.queue_sync_many(conn, self.backend, [self.intent()]))

    def test_second_job_patch_chunk_failure_rolls_back_every_job_and_caller_write(self):
        self.seed_jobs()
        self.assert_second_chunk_rollback("jobs", self.update_jobs)
