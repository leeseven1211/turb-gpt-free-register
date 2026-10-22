from __future__ import annotations

import os
from unittest.mock import patch

from core import account_task_store
from core.storage import operation
from tests.support_pg import PostgresTestCase


class ExtractLinkProviderStorageTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._previous_operation_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        cls._account_schema_patch = patch.object(account_task_store, "_SCHEMA", cls.schema)
        cls._account_ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        cls._account_schema_patch.start()
        cls._account_ready_patch.start()
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        try:
            operation.reset_ready()
            if cls._previous_operation_schema is None:
                os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
            else:
                os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._previous_operation_schema
        finally:
            cls._account_ready_patch.stop()
            cls._account_schema_patch.stop()
            super().tearDownClass()

    def setUp(self):
        operation.init()

    def test_provider_private_data_is_not_in_normal_task_or_run_projections(self):
        from core.storage import extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=None,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "huanguang", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "huanguang",
            "remote-job-1",
            {
                "extraction_state": "running",
                "payment_state": "not_started",
                "job_secret": "test-private-job-secret",
            },
            {"job_secret": "test-private-job-secret"},
        )

        projected_task = operation.get_task(int(task["id"]))
        listed_tasks = operation.list_tasks(task_type="extract_link")["items"]
        self.assertNotIn("test-private-job-secret", repr(projected_task))
        self.assertNotIn("test-private-job-secret", repr(listed_tasks))
        self.assertNotIn("test-private-job-secret", repr(operation.get_run(run_id)))

        private_job = extract_link_jobs.get_provider_job_private(run_id)
        self.assertEqual("remote-job-1", private_job["job_id"])
        self.assertEqual("test-private-job-secret", private_job["private_data"]["job_secret"])
        self.assertNotIn("job_secret", private_job["public_state"])

    def test_provider_state_updates_do_not_replace_private_resume_data(self):
        from core.storage import extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=None,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "lumen_flow", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "lumen_flow",
            "remote-job-2",
            {"extraction_state": "running", "payment_state": "not_started"},
            {"resume_cursor": "private-cursor"},
        )

        extract_link_jobs.update_provider_job_state(
            run_id,
            {"extraction_state": "success", "payment_state": "not_started", "links": ["https://example.test/result"]},
        )

        saved = extract_link_jobs.get_provider_job_private(run_id)
        self.assertEqual("success", saved["extraction_state"])
        self.assertEqual(["https://example.test/result"], saved["public_state"]["links"])
        self.assertEqual("private-cursor", saved["private_data"]["resume_cursor"])

    def test_workbench_rows_join_current_run_and_return_only_public_state(self):
        from core.storage import extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=None,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "huanguang", "mode": "extract_only"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "huanguang",
            "remote-job-3",
            {
                "extraction_state": "succeeded",
                "payment_state": "not_started",
                "preflight_status": "passed",
                "links": ["https://example.test/result"],
            },
            {"job_secret": "private-resume-secret"},
        )

        rows = extract_link_jobs.list_workbench_rows(provider_id="huanguang", mode="extract_only")

        self.assertEqual(1, len(rows))
        self.assertEqual(int(task["id"]), rows[0]["task_id"])
        self.assertEqual(run_id, rows[0]["run_id"])
        self.assertEqual("remote-job-3", rows[0]["remote_job_id"])
        self.assertEqual("succeeded", rows[0]["extraction_state"])
        self.assertEqual(["https://example.test/result"], rows[0]["public_state"]["links"])
        self.assertNotIn("private-resume-secret", repr(rows))

    def test_unresolved_auto_payment_includes_unknown_payment_without_remote_job_id(self):
        from core.storage import extract_link_jobs

        payment_task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=77,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "lumen_flow", "mode": "auto_payment"},
        )
        extract_link_jobs.save_provider_job(
            int(payment_task["run"]["id"]),
            "lumen_flow",
            None,
            {"extraction_state": "unknown", "payment_state": "unknown"},
            {},
        )

        extraction_task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=78,
            email="redacted@example.test",
            trigger="test",
            data={"provider_id": "lumen_flow", "mode": "extract_only"},
        )
        extract_link_jobs.save_provider_job(
            int(extraction_task["run"]["id"]),
            "lumen_flow",
            None,
            {"extraction_state": "unknown", "payment_state": "unknown"},
            {},
        )

        self.assertTrue(extract_link_jobs.has_unresolved_auto_payment(77))
        self.assertFalse(extract_link_jobs.has_unresolved_auto_payment(78))

    def test_recoverable_remote_jobs_only_include_interrupted_current_runs(self):
        from core.storage import extract_link_jobs

        task = operation.create_runtime_task(
            task_type="extract_link",
            account_id=77,
            email="redacted@example.test",
            trigger="test",
            source_system="native_operations",
            data={"provider_id": "lumen_flow", "mode": "auto_payment"},
        )
        run_id = int(task["run"]["id"])
        extract_link_jobs.save_provider_job(
            run_id,
            "lumen_flow",
            "remote-job-4",
            {"extraction_state": "running", "payment_state": "pending"},
            {},
        )
        operation.finish_run(
            run_id,
            status="attention_required",
            message="worker restarted",
        )

        rows = extract_link_jobs.list_recoverable_workbench_jobs()

        self.assertEqual(1, len(rows))
        self.assertEqual(int(task["id"]), rows[0]["task_id"])
        self.assertEqual(run_id, rows[0]["run_id"])
        self.assertEqual("lumen_flow", rows[0]["provider_id"])
        self.assertEqual("auto_payment", rows[0]["mode"])
