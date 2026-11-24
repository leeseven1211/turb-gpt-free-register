"""C2A 巡检集合受理：数据库预算、旧请求身份与持久意图恢复。"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from psycopg import Cursor
from psycopg.rows import dict_row

from core.integrations.c2a import client, manual_sync, monitor
from core.operations import task_gateway
from core.storage import c2a as repairs, postgres, records
from core.storage.operations import common, runtime, schema
from tests.support_pg import PostgresTestCase


class C2AMonitorSubmissionTests(PostgresTestCase):
    def setUp(self):
        records.init()
        schema.init_operation_schema()
        repairs.init()
        self.backend = "a" * 64
        self.enterContext(patch.object(client, "configured_backend_identity", return_value=self.backend))
        self.dispatch = self.enterContext(patch.object(task_gateway, "notify_dispatch"))
        self.addCleanup(task_gateway.unregister_operation_handler, manual_sync.TASK_TYPE)

    def submissions(self, size):
        values = []
        for number in range(size):
            account = {"email": f"monitor-{number}@example.test", "access_token": f"synthetic-secret-{number}"}
            account["id"] = records.insert_row(records.ACCOUNTS, account)
            target = {"state": "pending", "key": None, "next_attempt_at": 0}
            remote_id = f"remote-{number}"
            row = {"account_id": account["id"], "email": account["email"], "stage": "sync_wait",
                   "source_generation": f"generation-{number}", "targets": {remote_id: target}}
            values.append((row, account, remote_id, target))
        return values

    @staticmethod
    def summary():
        return {"reasons": Counter(), "diagnostics": [], "child_tasks": [], "sync_queued": 0}

    def tasks(self):
        with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {common._table('operation_tasks')} ORDER BY id")
            return [dict(row) for row in cur.fetchall()]

    def test_monitor_persists_many_uploads_in_one_admission_transaction(self):
        submissions = self.submissions(24)
        statements, task_connections = [], set()
        execute = Cursor.execute

        def capture(cursor, query, *args, **kwargs):
            text = str(query)
            statements.append(text)
            if 'INSERT INTO' in text and '"operation_tasks"' in text:
                task_connections.add(id(cursor.connection))
            return execute(cursor, query, *args, **kwargs)

        result = self.summary()
        with patch.object(Cursor, "execute", capture):
            monitor._submit_uploads(self.backend, submissions, result, 1000, lambda: None)
        self.assertEqual(24, result["sync_queued"])
        self.assertEqual(1, len(task_connections), "巡检不可为每个账号分别提交事务")
        for table in ("operation_tasks", "operation_runs", "operation_events"):
            self.assertEqual(1, sum('INSERT INTO' in text and f'"{table}"' in text for text in statements))
        self.assertEqual(1, sum(
            text.lstrip().startswith("SELECT") and f'"{records.ACCOUNTS.name}"' in text for text in statements
        ))
        self.assertEqual(1, self.dispatch.call_count)
        tasks = self.tasks()
        self.assertEqual(24, len(tasks))
        for task, (row, account, remote_id, target) in zip(tasks, submissions):
            digest = hashlib.sha256(
                f"{self.backend}\n{remote_id}\n{account['id']}\n{target['key']}".encode()
            ).hexdigest()
            self.assertEqual(f"c2a-repair:{digest}", task["source_id"])
            self.assertEqual("native_operations", task["source_system"])
            self.assertEqual("c2a_monitor", task["trigger"])
            run = runtime.get_run(target["run_id"])
            self.assertEqual({
                "backend_identity": self.backend, "remote_account_id": remote_id, "monitor_managed": True,
            }, run["data"])
            self.assertNotIn(account["access_token"], repr(task))
            self.assertEqual(row["source_generation"], target["token_generation"])

    def test_replays_task_after_receipt_save_fails_without_replacing_saved_key(self):
        submissions = self.submissions(1)
        save = repairs.save_repairs
        writes = 0

        def fail_receipt(backend, rows):
            nonlocal writes
            writes += 1
            if writes == 2:
                raise RuntimeError("synthetic receipt write failure")
            return save(backend, rows)

        with patch.object(repairs, "save_repairs", side_effect=fail_receipt):
            with self.assertRaisesRegex(RuntimeError, "receipt write failure"):
                monitor._submit_uploads(self.backend, submissions, self.summary(), 1000, lambda: None)
        first = self.tasks()[0]
        row = repairs.list_repairs(self.backend)[0]
        target = row["targets"]["remote-0"]
        self.assertTrue(target["key"])
        self.assertNotIn("task_id", target)
        expected_key = target["key"]
        result = self.summary()
        monitor._submit_uploads(
            self.backend, [(row, submissions[0][1], "remote-0", target)], result, 1001, lambda: None,
        )
        self.assertEqual(1, len(self.tasks()))
        self.assertEqual(expected_key, target["key"])
        self.assertEqual(first["id"], target["task_id"])
        self.assertEqual(first["last_run_id"], target["run_id"])
        self.assertEqual(1, result["sync_queued"])

    def test_legacy_queue_target_replay_keeps_same_task_and_latest_run(self):
        submissions = self.submissions(1)
        row, account, remote_id, target = submissions[0]
        target["key"] = "persisted-before-collection-migration"
        queued = manual_sync.queue_target(
            account, remote_id, expected_backend=self.backend, idempotency_key=target["key"],
        )
        runtime.finish_run(queued["run_id"], status="success", result_summary={"ok": True})
        result = self.summary()
        monitor._submit_uploads(self.backend, submissions, result, 1000, lambda: None)
        self.assertEqual(1, len(self.tasks()))
        self.assertEqual(queued["task_id"], target["task_id"])
        self.assertEqual(queued["run_id"], target["run_id"])
        self.assertEqual("success", result["child_tasks"][0]["status"])

    def test_busy_and_deactivated_accounts_preserve_per_target_result(self):
        submissions = self.submissions(3)
        busy = runtime.create_runtime_task(
            task_type="live_check", account_id=submissions[1][1]["id"], email=submissions[1][1]["email"],
        )
        records.patch_row(records.ACCOUNTS, submissions[2][1]["id"], changes={"account_status": "deactivated"})
        result = self.summary()
        monitor._submit_uploads(self.backend, submissions, result, 1000, lambda: None)
        self.assertEqual(1, result["sync_queued"])
        self.assertIsNone(submissions[0][3]["last_code"])
        self.assertEqual("account_busy", submissions[1][3]["last_code"])
        self.assertEqual("account_deactivated", submissions[2][3]["last_code"])
        self.assertNotIn("task_id", submissions[1][3])
        self.assertEqual(2, len(self.tasks()))
        self.assertNotEqual(busy["id"], submissions[0][3]["task_id"])

    def test_deleted_account_snapshot_keeps_legacy_admission_and_worker_rejects_execution(self):
        submissions = self.submissions(1)
        records.delete_rows(records.ACCOUNTS, [submissions[0][1]["id"]])
        result = self.summary()
        monitor._submit_uploads(self.backend, submissions, result, 1000, lambda: None)
        self.assertEqual(1, result["sync_queued"])
        task = self.tasks()[0]
        with self.assertRaises(manual_sync.C2AReimportError) as failure:
            manual_sync._read_current_account(SimpleNamespace(
                account_id=task["account_id"], email=task["email_snapshot"],
            ))
        self.assertEqual("c2a_local_account_missing", failure.exception.code)

    def test_partial_task_write_failure_rolls_back_whole_admission_wave(self):
        submissions = self.submissions(2)
        execute = Cursor.execute
        event_inserts = 0

        def fail_second_event(cursor, query, params=None, *args, **kwargs):
            nonlocal event_inserts
            text = str(query)
            if "INSERT INTO" in text and '"operation_events"' in text:
                event_inserts += 1
                # 集合插入在同一条语句注入失败；旧逐项实现到第二条时失败。
                bulk_values = json.loads(params[0]) if params and isinstance(params[0], str) and params[0].startswith("[") else []
                if len(bulk_values) > 1 or event_inserts == 2:
                    raise RuntimeError("synthetic event persistence failure")
            return execute(cursor, query, params, *args, **kwargs)

        result = self.summary()
        with patch.object(Cursor, "execute", fail_second_event):
            monitor._submit_uploads(self.backend, submissions, result, 1000, lambda: None)
        self.assertEqual([], self.tasks(), "本地持久受理失败不可留下半批任务")
        self.assertEqual(0, result["sync_queued"])
        self.assertTrue(all(target.get("key") and not target.get("task_id") for _, _, _, target in submissions))
        self.assertEqual(2, result["reasons"]["c2a_upload_queue_failed"])
        # worker 可以绑定外层结算连接；监控捕获受理错误后也不能提交半波 Task。
        with postgres.connect(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {records._qualified(records.ACCOUNTS)} "
                    """SET data=data || '{"caller_sentinel":true}'::jsonb WHERE id=%s""",
                    (submissions[0][1]["id"],),
                )
            with common.settlement_scope(None, conn=conn), patch.object(Cursor, "execute", fail_second_event):
                monitor._submit_uploads(self.backend, submissions, self.summary(), 1001, lambda: None)
            with conn.cursor() as cur:
                for table in ("operation_tasks", "operation_runs", "operation_events"):
                    cur.execute(f"SELECT count(*) AS n FROM {common._table(table)}")
                    self.assertEqual(0, cur.fetchone()["n"], "借用外层连接也必须回滚整波受理")
                cur.execute(
                    f"SELECT data->'caller_sentinel' AS value FROM {records._qualified(records.ACCOUNTS)} WHERE id=%s",
                    (submissions[0][1]["id"],),
                )
                self.assertIs(cur.fetchone()["value"], True, "受理回滚不能清除外层调用方已写入的内容")
