# -*- coding: utf-8 -*-
"""注册任务成功结算时的父任务收口与事务回滚回归测试。"""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from core import db
from core.operations import run_log as task_run_log
from core.storage import postgres as postgres_store
from core.storage import records
from core.storage.operations import runtime as operation_runtime
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class RegistrationCompletionSettlementTests(PostgresTestCase):
    def setUp(self):
        self.log_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.log_dir.cleanup)
        self.enterContext(patch.object(task_run_log, "_LOG_ROOT", Path(self.log_dir.name)))
        self.enterContext(patch.object(task_run_log, "_TASK_LOG_ROOT", Path(self.log_dir.name) / "tasks"))
        operation.reset_ready()
        operation.init()

    def _seed_registration_job(self) -> tuple[int, int]:
        email = f"registration-settlement-{uuid.uuid4().hex}@example.test"
        account_id = records.insert_row(records.ACCOUNTS, {
            "email": email,
            "access_token": "synthetic-access-token",
            "extra_json": {
                "account_password": "synthetic-password",
                "account_password_state": "confirmed",
            },
            "plan_check_status": "success",
            "totp_secret": "synthetic-totp-secret",
            "codex_status": "success",
        })
        job = db.create_job("outlook")
        job_id = int(job["id"])

        # 只改旧注册事实，保留刚创建的 registration_jobs 排队 Run。
        records.patch_row(records.JOBS, job_id, {
            "status": "partial_success",
            "email": email,
            "account_id": account_id,
            "error_message": "等待账号配置完成",
        })
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT id FROM {postgres_store.qualified('operation_runs')} "
                "WHERE source_system='registration_jobs' AND source_id=%s",
                (str(job_id),),
            )
            run = cur.fetchone()
        self.assertIsNotNone(run)
        return job_id, int(run[0])

    def test_successful_registration_job_settlement_commits_parent_and_child(self):
        job_id, run_id = self._seed_registration_job()

        result = operation.finish_run(run_id, status="success", result_summary={"ok": True})

        self.assertEqual("success", result["status"])
        self.assertEqual("success", records.get_row(records.JOBS, job_id)["status"])
        self.assertEqual("success", operation.get_run(run_id)["status"])

    def test_failed_transaction_rolls_back_parent_and_child_settlement(self):
        job_id, run_id = self._seed_registration_job()

        with self.assertRaisesRegex(RuntimeError, "故意回滚"):
            with operation._connect() as conn:
                operation_runtime.finish_run(
                    run_id,
                    status="success",
                    result_summary={"ok": True},
                    _settlement_conn=conn,
                )
                raise RuntimeError("故意回滚")

        self.assertEqual("partial_success", records.get_row(records.JOBS, job_id)["status"])
        self.assertNotEqual("success", operation.get_run(run_id)["status"])
