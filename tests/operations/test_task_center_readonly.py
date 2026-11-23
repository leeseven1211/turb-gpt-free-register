"""GETs read deployed schemas, including when the database login can write."""
import logging
import os
from contextlib import contextmanager
from unittest.mock import patch

import psycopg
from flask import Flask
from psycopg.conninfo import make_conninfo

from core import account_task_store, operation_task_store
from core.operations import query_service
from core.storage import postgres, records, registration
from core.storage.operations import schema as operation_schema
from tests.support_pg import PostgresTestCase, drop_schema, temporary_schema_name
from webui.routes.accounts import create_accounts_blueprint
from webui.routes.jobs import create_jobs_blueprint
from webui.routes.operations import create_operations_blueprint
from webui.runtime import WebUIContext


class TaskCenterReadonlyTests(PostgresTestCase):
    def setUp(self):
        legacy_schema = patch.object(account_task_store, "_SCHEMA", self.schema)
        legacy_schema.start()
        self.addCleanup(legacy_schema.stop)
        app = Flask(__name__)
        context = WebUIContext(app, logging.getLogger(__name__))
        for blueprint in (create_operations_blueprint, create_accounts_blueprint, create_jobs_blueprint):
            app.register_blueprint(blueprint(context))
        self.client = app.test_client()
        self.reader = make_conninfo(postgres.database_url(), options="-c default_transaction_read_only=on")

    @contextmanager
    def _read_sql_only(self):
        statements = []
        execute = psycopg.Cursor.execute

        def trace(cursor, statement, *args, **kwargs):
            statements.append(" ".join(str(statement).lower().split()))
            return execute(cursor, statement, *args, **kwargs)

        with patch.object(psycopg.Cursor, "execute", trace):
            yield
        self.assertTrue(statements)
        self.assertEqual([], [s[:110] for s in statements
                              if (s.split()[0] not in {"select", "with", "show"} and s != "set local jit = off")
                              or "advisory" in s or " for update" in s])

    def test_cold_reads_match_writable_queries_without_attempting_maintenance(self):
        task = operation_task_store.create_runtime_task(
            task_type="test_read_only", account_id=None, email="", trigger="test",
        )
        task_id, run_id = task["id"], task["run"]["id"]
        legacy = account_task_store.create_task(task_type="test_legacy", account_id=None, email="", trigger="test")
        last_run = "2026-01-02T03:04:05"
        postgres.save_collection("scheduler_state", {"at_refresh": {"last_run_at": last_run}})
        routes = [
            (f"/api/operations?task_id={task_id}", lambda p: (p["total"], p["items"][0]["id"], p["facets"])),
            (f"/api/operations/{task_id}", lambda p: (p["task"]["id"], p["task"]["runs"][0]["id"])),
            (f"/api/operations/{task_id}/runs/{run_id}/progress", lambda p: p["progress"]["outcome"]),
            (f"/api/operations/{task_id}/runs/{run_id}/events", lambda p: p["items"]),
            ("/api/account-tasks", lambda p: (p["items"][0]["id"], p["token_refresh"]["schedule"]["last_run_at"])),
            (f"/api/account-tasks/{legacy}", lambda p: (p["task"]["id"], p["task"]["events"])),
            (f"/api/operations/{task_id}/runs/{run_id}/logs", lambda p: p["items"]),
        ]
        expected = [project(self.client.get(path).get_json()) for path, project in routes]
        self.assertEqual((1, task_id), expected[0][:2])
        self.assertEqual((task_id, run_id), expected[1])
        self.assertEqual((legacy, last_run), expected[4])
        postgres.reset_cache()
        ready = operation_schema._READY_KEY, account_task_store._READY_KEY, records._READY_KEY
        with patch.dict(os.environ, DATABASE_URL=self.reader), self._read_sql_only():
            for (path, project), data in zip(routes, expected):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(200, response.status_code)
                    self.assertEqual(data, project(response.get_json()))
        self.assertEqual(ready, (operation_schema._READY_KEY, account_task_store._READY_KEY, records._READY_KEY))

    def _linked_job(self):
        operation_task_store.init()
        email = "linked-reader@example.test"
        account = records.insert_row(records.ACCOUNTS, {"email": email})
        job = records.insert_row(records.JOBS, {"status": "failed", "job_type": "registration",
                                                "email": email, "account_id": account})
        attempt = registration.create_attempt(email, root_job_id=job)
        records.patch_row(records.JOBS, job, {"attempt_id": attempt["id"]})
        operation_task_store.sync_registration_job(job)
        task = operation_task_store.find_task_by_source("registration_chains", f"{job}:registration")
        return account, job, task["id"]

    def test_cold_gets_with_linked_attempt_work_under_jobs_read_lock(self):
        account, job, task = self._linked_job()
        routes = (
            ("/api/accounts?paged=1", lambda p: (p["items"][0]["id"], p["items"][0]["registration_retry"]["source_job_id"]), (account, job)),
            ("/api/jobs?paged=1", lambda p: (p["items"][0]["id"], p["items"][0]["operation_task_id"]), (job, task)),
            (f"/api/jobs/{job}/progress", lambda p: (p["job"]["id"], p["job"]["operation_task_id"]), (job, task)),
            ("/api/operations?type=registration", lambda p: p["items"][0]["id"], task),
            (f"/api/operations/{task}", lambda p: p["task"]["id"], task),
        )
        # Each DSN is a fresh in-process cache key. Bound the old bug's wait.
        with postgres.connect() as blocker:
            blocker.execute(f"SELECT id FROM {postgres.qualified(records.JOBS.name)} LIMIT 1")
            for readonly in ("off", "on"):
                dsn = make_conninfo(postgres.database_url(), options=f"-c lock_timeout=180ms -c default_transaction_read_only={readonly}")
                with patch.dict(os.environ, DATABASE_URL=dsn):
                    for path, project, expected in routes:
                        with self.subTest(readonly=readonly, path=path), self._read_sql_only():
                            response = self.client.get(path)
                            self.assertEqual(200, response.status_code)
                            self.assertEqual(expected, project(response.get_json()))

    def test_optional_registration_facts_and_progress_can_be_unavailable(self):
        _, job, _ = self._linked_job()
        email = "legacy@example.test"
        account = records.insert_row(records.ACCOUNTS, {"email": email, "codex_status": "failed"})
        other = records.insert_row(records.JOBS, {"status": "failed", "job_type": "registration",
                                                  "email": email, "account_id": account})
        with postgres.connect() as conn:
            conn.execute(f"ALTER TABLE {postgres.qualified('registration_attempts')} RENAME COLUMN root_job_id TO old_root_job_id")
            conn.execute(f"ALTER TABLE {postgres.qualified('operation_events')} RENAME TO hidden_operation_events")
        try:
            for path in ("/api/jobs?paged=1", f"/api/jobs/{job}/progress", "/api/accounts?paged=1"):
                with self.subTest(path=path), self._read_sql_only():
                    response = self.client.get(path)
                    self.assertEqual(200, response.status_code)
                    payload = response.get_json()
                    if path.startswith("/api/accounts"):
                        self.assertFalse(any(row["registration_retry"]["available"] for row in payload["items"]))
                    else:
                        if "job" in payload:
                            item = payload["job"]
                        else:
                            by_id = {row["id"]: row for row in payload["items"]}
                            self.assertTrue(by_id[other]["retryable"])
                            item = by_id[job]
                        self.assertIs(item.get("retryable", False), False)
                        self.assertNotIn("operation_task_id", item)
        finally:
            with postgres.connect() as conn:
                conn.execute(f"ALTER TABLE {postgres.qualified('registration_attempts')} RENAME COLUMN old_root_job_id TO root_job_id")
                conn.execute(f"ALTER TABLE {postgres.qualified('hidden_operation_events')} RENAME TO operation_events")

    def test_table_view_omits_log_binding_when_projection_tasks_are_missing(self):
        _, job, _ = self._linked_job()
        with postgres.connect() as conn:
            conn.execute(f"ALTER TABLE {postgres.qualified('operation_tasks')} RENAME TO hidden_operation_tasks")
        try:
            with self._read_sql_only():
                response = self.client.get("/api/jobs?view=table")
            self.assertEqual(200, response.status_code)
            self.assertEqual(job, response.get_json()["items"][0]["id"])
            self.assertNotIn("operation_task_id", response.get_json()["items"][0])
        finally:
            with postgres.connect() as conn:
                conn.execute(f"ALTER TABLE {postgres.qualified('hidden_operation_tasks')} RENAME TO operation_tasks")

    def test_failed_registration_keeps_verified_retry_reason_on_cold_reader(self):
        operation_task_store.init()
        stamp = "2026-01-02T03:04:05"
        email = "task-reader@example.test"
        job = {"job_type": "registration", "created_at": stamp, "updated_at": stamp, "email": email}
        job_id = records.insert_row(records.JOBS, dict(job, status="failed"))
        attempt = registration.create_attempt(email, root_job_id=job_id)
        records.patch_row(records.JOBS, job_id, {"attempt_id": attempt["id"]})
        retry_id = records.insert_row(records.JOBS, dict(job, status="success", root_job_id=job_id))
        operation_task_store.sync_registration_job(job_id)
        path = "/api/operations?type=registration"
        for dsn in (postgres.database_url(), self.reader):
            with patch.dict(os.environ, DATABASE_URL=dsn):
                item = self.client.get(path).get_json()["items"][0]
                for task in (item, self.client.get(f"/api/operations/{item['id']}").get_json()["task"]):
                    self.assertFalse(task["retryable"])
                    self.assertEqual(f"后续重试任务 #{retry_id} 已成功", task["retry_reason"])
                    self.assertEqual([], task["next_actions"])

    def test_warm_list_reuses_its_query_connection(self):
        operation_task_store.init()
        path = "/api/operations"
        wrapped = query_service.list_operations
        counts = []
        for read in (wrapped.__wrapped__, wrapped):
            with patch.object(query_service, "list_operations", read), patch.object(
                postgres, "connect", wraps=postgres.connect,
            ) as borrow:
                self.assertEqual(200, self.client.get(path).status_code)
                counts.append(borrow.call_count)
        # 一条连接读列表与 facets，另一条读 batches。
        self.assertEqual([2, 2], counts)

    def test_missing_read_schema_returns_unavailable_even_on_writable_database(self):
        empty = temporary_schema_name("task_query_missing")
        self.addCleanup(drop_schema, empty)
        with patch.dict(os.environ, TURB_DB_SCHEMA=empty), patch.object(account_task_store, "_SCHEMA", empty):
            for dsn in (self.reader, postgres.database_url()):
                with patch.dict(os.environ, DATABASE_URL=dsn):
                    for path in ("/api/operations", "/api/accounts", "/api/jobs", "/api/jobs/1/progress"):
                        with self.subTest(path=path), self._read_sql_only():
                            response = self.client.get(path)
                            self.assertEqual(503, response.status_code)
                            self.assertEqual("task_schema_not_ready", response.get_json()["error_code"])
            with postgres.connect() as conn:
                self.assertIsNone(conn.execute("SELECT to_regnamespace(%s)", (empty,)).fetchone()[0])
