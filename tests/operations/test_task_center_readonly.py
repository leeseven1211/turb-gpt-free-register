"""Cold migrated GETs must work on an already deployed, read-only PostgreSQL database."""
import logging
import os
from unittest.mock import patch

import psycopg
from flask import Flask
from psycopg.conninfo import make_conninfo

from core import account_task_store, operation_task_store
from core.operations import query_service
from core.storage import postgres, records, registration
from core.storage.task_query_context import _readonly_connection
from tests.support_pg import PostgresTestCase, temporary_schema_name
from webui.routes.operations import create_operations_blueprint
from webui.runtime import WebUIContext


class TaskCenterReadonlyTests(PostgresTestCase):
    def setUp(self):
        legacy_schema = patch.object(account_task_store, "_SCHEMA", self.schema)
        legacy_schema.start()
        self.addCleanup(legacy_schema.stop)
        app = Flask(__name__)
        app.register_blueprint(create_operations_blueprint(WebUIContext(app, logging.getLogger(__name__))))
        self.client = app.test_client()
        self.reader = make_conninfo(postgres.database_url(), options="-c default_transaction_read_only=on")

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
        ]
        expected = [project(self.client.get(path).get_json()) for path, project in routes]
        self.assertEqual((1, task_id), expected[0][:2])
        self.assertEqual((task_id, run_id), expected[1])
        self.assertEqual((legacy, last_run), expected[4])
        postgres.reset_cache()
        statements = []
        execute = psycopg.Cursor.execute

        def trace(cursor, statement, *args, **kwargs):
            statements.append(str(statement).strip().lower())
            return execute(cursor, statement, *args, **kwargs)

        ready = operation_task_store._READY_KEY, account_task_store._READY_KEY, records._READY_KEY
        with patch.dict(os.environ, DATABASE_URL=self.reader), patch.object(psycopg.Cursor, "execute", trace):
            for (path, project), data in zip(routes, expected):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(200, response.status_code)
                    self.assertEqual(data, project(response.get_json()))
        self.assertTrue(statements)
        self.assertEqual([], [s.split()[0] for s in statements if s.split()[0] not in {"select", "with", "show"}])
        self.assertEqual(ready, (operation_task_store._READY_KEY, account_task_store._READY_KEY, records._READY_KEY))

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

    def test_unreported_connection_mode_falls_back_to_the_server(self):
        for dsn, expected in ((postgres.database_url(), False), (self.reader, True)):
            with postgres.connect(dsn) as conn, patch.object(type(conn.info), "parameter_status", return_value=None):
                self.assertIs(_readonly_connection(conn), expected)

    def test_missing_read_schema_returns_unavailable_then_writable_request_initializes_it(self):
        empty = temporary_schema_name("task_query_missing")
        from tests.support_pg import drop_schema
        self.addCleanup(drop_schema, empty)
        with patch.dict(os.environ, TURB_DB_SCHEMA=empty), patch.object(account_task_store, "_SCHEMA", empty):
            with patch.dict(os.environ, DATABASE_URL=self.reader):
                response = self.client.get("/api/operations")
                self.assertEqual(503, response.status_code)
                self.assertEqual("task_schema_not_ready", response.get_json()["error_code"])
            self.assertEqual(200, self.client.get("/api/operations").status_code)
