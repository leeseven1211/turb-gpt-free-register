"""注册并发接受无固定上限的正整数，并在任何业务副作用前拒绝非法输入。"""
from __future__ import annotations

import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from core import db
from core.operations import run_log
from core.registration import service
from tests.support_pg import PostgresTestCase
from webui.app import create_app


VALID_WORKERS = [(1, 1), (30, 30), (50, 50), (100, 100), ("30", 30), (" 30 ", 30)]
INVALID_WORKERS = [True, False, 1.5, 30.0, None, 0, -1, "", " ", "1.5", "-1", "1e2", "３０", [], {}]


@pytest.mark.parametrize("value,expected", VALID_WORKERS)
def test_registration_worker_validation_preserves_positive_integer_values(value, expected):
    assert service.validate_registration_workers(value) == expected
    assert service._normalize_workers(value) == expected


@pytest.mark.parametrize("value", INVALID_WORKERS)
def test_registration_worker_validation_rejects_values_that_are_not_positive_integers(value):
    with pytest.raises(ValueError, match="workers"):
        service.validate_registration_workers(value)


def test_internal_default_remains_compatible_without_restoring_a_fixed_maximum():
    assert service._normalize_workers(None) == 4
    assert service.validate_registration_workers(100_000) == 100_000


@pytest.mark.parametrize("value", [value for value in INVALID_WORKERS if value is not None])
def test_invalid_executor_workers_do_not_change_the_previous_default(value):
    with patch.object(service, "_executor_workers", 30), patch.object(service, "_executor", None):
        with pytest.raises(ValueError, match="workers"):
            service.get_executor(max_workers=value)
        assert service.get_executor_workers() == 30
        assert service._executor is None


@pytest.mark.parametrize("value", [True, 1.5, 0, "1.5", []])
def test_service_entry_points_validate_workers_before_reading_or_creating_jobs(value):
    with patch.object(db, "create_job") as create_job, patch.object(db, "get_job") as get_job:
        with pytest.raises(ValueError, match="workers"):
            service.submit_registration(count=2, email_source="outlook", workers=value)
        result = service.retry_job(21, workers=value, batch_id="新批次")
    assert result["ok"] is False
    assert result["status"] == 400
    assert "workers" in result["error"]
    create_job.assert_not_called()
    get_job.assert_not_called()


@pytest.fixture
def client():
    result = create_app(auth_code="test-auth").test_client()
    result.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
    return result


def _api_request(endpoint, workers):
    if endpoint == "create":
        return "/api/jobs", {"count": 1, "workers": workers, "registration_driver": "protocol_oss_2"}
    if endpoint == "retry":
        return "/api/jobs/21/retry", {"workers": workers}
    return "/api/jobs/retry-bulk", {"job_ids": [21, 22], "workers": workers}


def _api_services():
    stack = ExitStack()
    stack.enter_context(patch("config.email.USE_EMAIL_SERVICE", False))
    stack.enter_context(patch("config.register.REGISTER_EMAIL", "fixture@example.test"))
    stack.enter_context(patch.object(service, "registration_config_snapshot", return_value={"registration_driver": "protocol_oss_2"}))
    stack.enter_context(patch.object(service, "registration_deployment_unavailable", return_value=None))
    submit = stack.enter_context(patch.object(service, "submit_registration", return_value=[{"id": 9}]))
    retry = stack.enter_context(patch.object(service, "retry_job", return_value={"ok": True, "job": {"id": 23, "batch_id": "测试批次"}}))
    return stack, submit, retry


@pytest.mark.parametrize("endpoint", ["create", "retry", "retry-bulk"])
@pytest.mark.parametrize("value", [30, "30"])
def test_all_registration_apis_pass_workers_above_sixteen_to_the_service(client, endpoint, value):
    path, body = _api_request(endpoint, value)
    stack, submit, retry = _api_services()
    with stack:
        response = client.post(path, json=body)
    assert response.status_code == 200
    if endpoint == "create":
        assert submit.call_args.kwargs["workers"] == 30
        assert response.get_json()["workers"] == 30
        retry.assert_not_called()
    else:
        assert retry.call_count == (1 if endpoint == "retry" else 2)
        assert all(call.kwargs["workers"] == 30 for call in retry.call_args_list)
        if endpoint == "retry-bulk":
            assert response.get_json()["workers"] == 30
        submit.assert_not_called()


@pytest.mark.parametrize("endpoint", ["create", "retry", "retry-bulk"])
@pytest.mark.parametrize("value", INVALID_WORKERS)
def test_all_registration_apis_return_400_without_dispatching_invalid_workers(client, endpoint, value):
    path, body = _api_request(endpoint, value)
    stack, submit, retry = _api_services()
    with stack:
        response = client.post(path, json=body)
    assert response.status_code == 400
    assert response.get_json()["ok"] is False
    assert "workers" in response.get_json()["error"]
    submit.assert_not_called()
    retry.assert_not_called()


class RegistrationWorkerStorageTests(PostgresTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {
            "TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "ACCOUNT_TASK_DB_SCHEMA": self.schema,
            "OPERATION_TASK_DB_SCHEMA": self.schema,
        }))
        self.stack.enter_context(patch.object(run_log, "_LOG_ROOT", root))
        self.stack.enter_context(patch.object(run_log, "_TASK_LOG_ROOT", root / "tasks"))
        self.stack.enter_context(patch.object(service, "_executor", None))
        self.stack.enter_context(patch.object(service, "_executor_workers", 4))

    def test_new_registration_batch_persists_thirty_workers_without_starting_real_jobs(self):
        snapshot = {"registration_driver": "protocol_oss_2", "proxy_country": "JP"}
        with patch.object(service, "start_dispatcher") as start, \
                patch.object(service, "notify_dispatch") as notify, \
                patch.object(db, "create_job", side_effect=AssertionError("unexpected per-job creation")), \
                patch.object(service, "require_registration_deployment"), \
                patch.object(service, "registration_config_snapshot", return_value=snapshot):
            jobs = service.submit_registration(count=2, email_source="outlook", workers="30", debug_enabled=True)
        self.assertEqual(2, len(jobs))
        start.assert_called_once()
        notify.assert_called_once()
        self.assertEqual(30, service.get_executor_workers())
        stored = [db.get_job(job["id"]) for job in jobs]
        self.assertEqual([30, 30], [job["batch_workers"] for job in stored])
        self.assertEqual(["pending", "pending"], [job["status"] for job in stored])
        self.assertEqual(1, len({job["batch_id"] for job in stored}))
        self.assertEqual([1, 2], [job["batch_index"] for job in stored])
        from core.storage import registration
        from core.storage.operations import store as operation
        for job in stored:
            self.assertTrue(job["registration_dispatch_ready"])
            self.assertTrue(job["debug_enabled"])
            self.assertEqual("pending", job["debug_state"])
            self.assertEqual(snapshot, job["config_snapshot"])
            attempt = registration.get_attempt_by_job(job["id"])
            self.assertEqual(job["attempt_id"], attempt["id"])
            self.assertEqual("not_created", attempt["target_status"])
            runs = registration.list_runs(attempt["id"])
            self.assertEqual([(job["id"], "queued")], [(run["job_id"], run["status"]) for run in runs])
            task = operation.find_task_by_source("registration_jobs", str(job["id"]), include_runs=True)
            self.assertEqual((attempt["id"], "queued"), (task["attempt_id"], task["status"]))

    def test_batch_submission_preserves_business_attempt_with_separate_projection_schema(self):
        from core.storage import postgres, registration
        from core.storage.operations import schema
        from core.storage.operations import store as operation
        from tests.support_pg import drop_schema, temporary_schema_name

        operation_schema = temporary_schema_name("registration_projection")
        self.addCleanup(drop_schema, operation_schema)
        with patch.dict(os.environ, {"OPERATION_TASK_DB_SCHEMA": operation_schema}), \
                patch.object(service, "start_dispatcher"), \
                patch.object(service, "notify_dispatch"), \
                patch.object(service, "require_registration_deployment"), \
                patch.object(service, "registration_config_snapshot", return_value={"registration_driver": "protocol_oss_2"}):
            schema.init_operation_schema()
            projected_attempts = f'{postgres.quote_identifier(operation_schema)}."registration_attempts"'
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"""INSERT INTO {projected_attempts} (attempt_uuid,source_root_job_id)
                               SELECT 'unrelated-' || n, 10000 + n FROM generate_series(1,5) n""")
            jobs = service.submit_registration(count=2, email_source="outlook", workers=2)
            for job in jobs:
                attempt = registration.get_attempt_by_job(job["id"])
                self.assertEqual(job["attempt_id"], attempt["id"])
                self.assertEqual("pending", attempt["target_status"])
                self.assertEqual(job["id"], registration.list_runs(attempt["id"])[0]["job_id"])
                task = operation.find_task_by_source("registration_jobs", str(job["id"]), include_runs=True)
                self.assertEqual("not_created", task["target_status"])
                self.assertNotEqual(attempt["id"], task["attempt_id"])
                db.update_job(job["id"], status="running")
                # Force the synchronous projector to surface an FK error rather than logging it.
                operation.sync_registration_job(job["id"])
                self.assertEqual(attempt["id"], db.get_job(job["id"])["attempt_id"])
                projected = operation.find_task_by_source("registration_jobs", str(job["id"]), include_runs=True)
                self.assertEqual((task["attempt_id"], "running"), (projected["attempt_id"], projected["status"]))

    def test_large_registration_batch_writes_bounded_statements_in_original_order(self):
        from core.storage import postgres, registration
        from core.storage.operations import schema

        registration.init()
        schema.init_operation_schema()
        jobs = postgres.qualified("registration_jobs")
        captured = postgres.qualified("registration_statement_sizes")
        fn = postgres.qualified("capture_registration_statement")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE TABLE {captured} (id bigserial,n int)")
            cur.execute(f"""CREATE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$
                             BEGIN INSERT INTO {captured}(n) SELECT count(*) FROM inserted;
                             RETURN NULL; END $$""")
            cur.execute(f"""CREATE TRIGGER capture_registration_statement AFTER INSERT ON {jobs}
                            REFERENCING NEW TABLE AS inserted FOR EACH STATEMENT EXECUTE FUNCTION {fn}()""")
        try:
            with (patch.object(service, "start_dispatcher") as start,
                  patch.object(service, "notify_dispatch") as wake,
                  patch.object(service, "require_registration_deployment"),
                  patch.object(service, "registration_config_snapshot", return_value={"registration_driver": "protocol_oss_2"})):
                rows = service.submit_registration(count=501, email_source="outlook", workers=3)
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT n FROM {captured} ORDER BY id")
                self.assertEqual([500, 1], [row[0] for row in cur.fetchall()])
            self.assertEqual(list(range(1, 502)), [row["batch_index"] for row in rows])
            self.assertEqual({501}, {row["batch_size"] for row in rows})
            self.assertEqual(1, len({row["batch_id"] for row in rows}))
            self.assertTrue(all(row["registration_dispatch_ready"] for row in rows))
            start.assert_called_once()
            wake.assert_called_once()
        finally:
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"DROP TRIGGER capture_registration_statement ON {jobs}")
                cur.execute(f"DROP FUNCTION {fn}()")
                cur.execute(f"DROP TABLE {captured}")
