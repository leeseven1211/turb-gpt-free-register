"""暗光原单续查的调度公平性与服务中断恢复。"""
from __future__ import annotations

import tempfile
import os
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet

from core import account_task_store
from core.operations import run_log, task_gateway
from core.storage.extract_link import jobs
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class AnguangDispatchCapacityTests(PostgresTestCase):
    def test_pending_polls_reserve_slots_for_initial_submissions(self):
        from config.concurrency import policy_values
        from core.operations import concurrency
        from core.storage import runtime_config

        values = policy_values({})
        values.update(GLOBAL_TASK_WORKERS=10, EXTRACT_LINK_WORKERS=10, EXTRACT_LINK_ANGUANG_CONCURRENCY=10)
        contexts = []
        with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()}):
            runtime_config.write_values({key: str(value) for key, value in values.items()}, activate=True, source="test")
            tasks = [operation.create_runtime_task(task_type="extract_link", account_id=None, email="", data={
                "provider_id": "anguang", "extract_poll_continuation": index < 3,
            }) for index in range(4)]
            try:
                for task in tasks[:2]:
                    admitted = task_gateway.admit_operation_run(operation.get_run(task["run"]["id"]))
                    self.assertTrue(admitted)
                    contexts.append(admitted.context)
                denied = task_gateway.admit_operation_run(operation.get_run(tasks[2]["run"]["id"]))
                self.assertIn("provider_capacity", denied.blocked_by)
                initial = task_gateway.admit_operation_run(operation.get_run(tasks[3]["run"]["id"]))
                self.assertTrue(initial)
                contexts.append(initial.context)
            finally:
                for context in contexts:
                    concurrency.release_execution(context)


class AnguangDispatchStorageTests(PostgresTestCase):
    def setUp(self):
        self.logs = tempfile.TemporaryDirectory()
        self.addCleanup(self.logs.cleanup)
        for name, value in (("_LOG_ROOT", Path(self.logs.name)),
                            ("_TASK_LOG_ROOT", Path(self.logs.name) / "tasks")):
            patcher = patch.object(run_log, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, value in (("_SCHEMA", self.schema), ("_READY_KEY", "")):
            patcher = patch.object(account_task_store, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        account_task_store.init()
        operation.reset_ready()
        operation.init()

    def test_initial_submission_visible_beyond_full_page_of_polls(self):
        for number in range(70):
            operation.create_runtime_task(task_type="extract_link", account_id=None,
                email=f"anguang-poll-{number}@example.test", data={
                    "provider_id": "anguang", "extract_poll_continuation": True,
                })
        initial = operation.create_runtime_task(task_type="extract_link", account_id=None,
            email="anguang-initial@example.test", data={"provider_id": "anguang"})
        initial_id = int(initial["run"]["id"])
        initial_first = operation.list_dispatchable_runs(limit=64, prioritize_continuations=False)
        self.assertEqual(initial_id, initial_first[0]["id"])
        polls_first = operation.list_dispatchable_runs(limit=64, prioritize_continuations=True)
        self.assertTrue(polls_first[0]["data"].get("extract_poll_continuation"))
        self.assertIn(initial_id, [row["id"] for row in polls_first])

    def test_crashed_polls_resume_same_run_only_with_original_receipt(self):
        cases = (
            ("original-task", {}, False, "queued"),
            (None, {"anguang_submission_pending": True, "anguang_request_encrypted": "synthetic-encrypted"}, False, "queued"),
            (None, {"anguang_submission_pending": True}, False, "interrupted"),
            (None, {"anguang_submission_pending": False, "anguang_request_encrypted": "synthetic-encrypted"}, False, "interrupted"),
            ("cancelled-original", {}, True, "interrupted"),
        )
        for number, (job_id, private, cancelled, expected) in enumerate(cases):
            with self.subTest(case=number):
                task = operation.create_runtime_task(task_type="extract_link", account_id=None,
                    email=f"anguang-recover-{number}@example.test", data={
                        "provider_id": "anguang", "extract_poll_continuation": True,
                        "workbench_action": "sync_status",
                    })
                run_id = int(task["run"]["id"])
                jobs.save_provider_job(run_id, "anguang", job_id,
                    {"extraction_state": "unknown"}, private)
                operation.claim_run(run_id, execution_id=f"anguang-crash-{run_id}", worker_pid=92)
                with operation._connect() as conn, conn.cursor() as cur:
                    cur.execute(f"UPDATE {operation._table('operation_runs')} "
                                "SET heartbeat_at=now()-interval '1 hour', "
                                "cancel_requested_at=CASE WHEN %s THEN now() ELSE NULL END WHERE id=%s",
                                (cancelled, run_id))
                self.assertEqual(1, operation.recover_interrupted_runtime_runs())
                self.assertEqual(expected, operation.get_run(run_id)["status"])
                self.assertEqual(run_id, operation.get_task(int(task["id"]))["last_run_id"])
