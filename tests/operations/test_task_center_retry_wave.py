"""跨原生和注册后处理的账号资源准入保持用户选择顺序。"""
from unittest.mock import patch

from psycopg import Cursor

from core import db
from core.codex import operation_service as codex
from core.operations import action_service, task_gateway
from core.storage import records, registration
from core.storage.operations import legacy_task_store, store
from tests.support_pg import PostgresTestCase


class TaskCenterRetryWaveTests(PostgresTestCase):
    def setUp(self):
        self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
        legacy_task_store.init()
        store.reset_ready()
        store.init()
        codex.register_actions()
        self.enterContext(patch.object(codex, "_config_snapshot", return_value={"oauth_driver": "protocol"}))
        self.enterContext(patch.object(codex, "_deployment_unavailable", return_value=None))
        self.enterContext(patch.object(codex, "_feature_ready", return_value=(True, "")))
        self.enterContext(patch("core.runtime.capabilities.account_setup_unavailable", return_value=None))
        self.enterContext(patch.object(codex, "start_dispatcher", side_effect=AssertionError("API 不能启动 Worker")))
        self.enterContext(patch.object(codex, "register_handler", side_effect=AssertionError("API 不能注册 handler")))
        self.enterContext(patch.object(task_gateway, "start_dispatcher", side_effect=AssertionError("API 不能启动 Worker")))
        self.notify = self.enterContext(patch.object(task_gateway, "notify_dispatch"))
        task_gateway.register_operation_actions("wave_native",
            retry_handler=task_gateway.default_operation_retry, source_systems=("native_operations",))

    def source(self, index=1, *, action="codex"):
        email = f"retry-wave-{index}@example.test"
        account_id = records.insert_row(records.ACCOUNTS, {
            "email": email, "access_token": "isolated-private-at",
            "codex_status": "failed" if action == "codex" else "success",
            "plan_check_status": "failed" if action == "plan_check" else "success",
            "totp_secret": "" if action == "twofa" else "isolated-totp",
            "extra_json": {"account_password": "isolated-password", "account_password_state": "confirmed"},
        })
        snapshot = {"registration_driver": "protocol_oss_2", "password_enabled": True,
            "twofa_enabled": True, "plan_check_enabled": True, "codex_enabled": True}
        job = db.create_job("outlook", batch_id=f"wave-followup-{index}", data={"config_snapshot": snapshot})
        db.update_job(job["id"], email=email, account_id=account_id, status="partial_success")
        registration.finish_run(registration.list_runs(job["attempt_id"])[0]["id"], status="partial_success")
        job = db.get_job(job["id"])
        parent = store.find_task_by_source("registration_jobs", str(job["id"]), include_runs=True)
        return job, parent["id"]

    def native(self, account, *, family="openai_interactive", prior_status="failed"):
        with store._connect() as conn, conn.cursor() as cur:
            task = store.create_runtime_task(task_type="wave_native", account_id=account["id"],
                email=account["email"], source_system="native_operations", resource_family=family, conn=conn)
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status=%s WHERE id=%s",
                (prior_status, task["run"]["id"]))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s", (task["id"],))
        return task["id"]

    def test_native_before_registration_followup_keeps_native_winner(self):
        source, parent = self.source()
        native = self.native(db.get_account(source["account_id"]))
        reply = action_service.accept_bulk_operation_action("retry", [native, parent])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [native])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [parent])
        self.notify.assert_called_once()

    def test_registration_followup_before_native_keeps_registration_winner(self):
        source, parent = self.source()
        native = self.native(db.get_account(source["account_id"]))
        reply = action_service.accept_bulk_operation_action("retry", [parent, native])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [parent])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [native])
        self.notify.assert_called_once()

    def test_each_registration_followup_kind_yields_to_preceding_native(self):
        ids, expected = [], []
        for index, action in enumerate(("codex", "plan_check", "twofa"), 1):
            source, parent = self.source(index, action=action)
            native = self.native(db.get_account(source["account_id"]))
            ids.extend((native, parent))
            expected.append(native)
        reply = action_service.accept_bulk_operation_action("retry", ids)
        # 套餐补跑的旧响应会把已有操作作为复用成功，事实仍必须由 native 拥有。
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT task_id FROM {store._table('operation_runs')} WHERE status='queued' ORDER BY task_id")
            self.assertEqual([row["task_id"] for row in cur.fetchall()], expected)
        self.assertIn(expected[0], [row["task_id"] for row in reply["accepted"]])
        self.notify.assert_called_once()

    def test_rejected_registration_stage_does_not_reserve_family(self):
        source, parent = self.source(action="plan_check")
        account = db.get_account(source["account_id"])
        records.patch_row(records.ACCOUNTS, account["id"], changes={
            "plan_check_status": "running", "plan_check_started_at": "2099-01-01T00:00:00"})
        native = self.native(account)
        reply = action_service.accept_bulk_operation_action("retry", [parent, native])
        self.assertIn(native, [row["task_id"] for row in reply["accepted"]])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT task_id FROM {store._table('operation_runs')} WHERE status='queued'")
            self.assertEqual([row["task_id"] for row in cur.fetchall()], [native])

    def test_native_latest_run_rejection_does_not_reserve_for_later_registration(self):
        source, parent = self.source()
        native = self.native(db.get_account(source["account_id"]), prior_status="waiting")
        reply = action_service.accept_bulk_operation_action("retry", [native, parent])
        self.assertEqual([row["task_id"] for row in reply["accepted"]], [parent])
        self.assertEqual([row["task_id"] for row in reply["skipped"]], [native])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT task_id FROM {store._table('operation_runs')} WHERE status='queued'")
            queued = [row["task_id"] for row in cur.fetchall()]
        self.assertEqual(len(queued), 1)
        self.assertNotEqual(queued[0], native)

    def test_busy_receipt_references_run_state_instead_of_winner_http_code(self):
        from core.operations.task_center_retry_wave import _busy

        reply = _busy({"accepted": True, "task_id": 41, "run_id": 42, "state": "queued", "status": 200})
        self.assertEqual(reply["task_id"], 41)
        self.assertEqual(reply["run_id"], 42)
        self.assertEqual(reply["status"], "queued")

    def test_one_and_twenty_registration_followups_keep_constant_sql(self):
        parents = [self.source(index)[1] for index in range(1, 22)]
        counts = []
        for selected in (parents[:1], parents[1:]):
            statements = []
            execute = Cursor.execute

            def measured(cursor, query, params=None, **kwargs):
                statements.append(str(query))
                return execute(cursor, query, params, **kwargs)

            with patch.object(Cursor, "execute", measured):
                reply = action_service.accept_bulk_operation_action("retry", selected)
            self.assertEqual(reply["accepted_count"], len(selected), reply)
            counts.append(len(statements))
        print(f"统一任务中心注册后处理 1 / 20 个来源 SQL：{counts}")
        self.assertEqual(counts[0], counts[1], counts)
        self.assertLessEqual(counts[1], 65, counts)
