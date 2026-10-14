"""无账号记录的失败任务自动续跑，原密码与未知提交始终留在同一 Attempt。"""
from unittest.mock import Mock, patch

from core import account_task_store, admin_repository, db, operation_task_store, record_store
from core import registration_service as service
from core.registration.browser_submission import unresolved_submission_ids
from core.storage import registration
from tests.support_pg import PostgresTestCase


class PrivatePasswordResumeFlowTests(PostgresTestCase):
    def setUp(self):
        self.enterContext(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(account_task_store, "_READY_KEY", ""))
        account_task_store.init()
        operation_task_store.reset_ready()
        operation_task_store.init()
        registration.reset_ready()
        registration.init()

    def test_two_unknown_resumes_reuse_private_password_and_can_persist_core(self):
        address = "automatic-resume@example.test"
        password = "OriginalSavedPassword123!"
        root_id = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "automatic-resume-root", "email": address,
            "email_source": "icloud_hide", "status": "running", "job_type": "registration",
            "batch_id": "automatic-resume-batch", "batch_index": 1, "batch_size": 1,
            "data": {"config_snapshot": {"registration_driver": "roxy"}},
        })
        attempt = registration.ensure_attempt_for_job(root_id)
        attempt_id = attempt["id"]
        original = registration.start_run(
            attempt_id, job_id=root_id, execution_id="original-execution", initial_status="running",
        )
        registration.save_password_checkpoint(
            attempt_id, email=address, password=password, state="started",
            run_id=original["id"], execution_id="original-execution", job_id=root_id,
        )
        registration.record_submission_fact(
            attempt_id, submission_id="original-unknown", kind="password",
            stage="password_create", phase="unknown", endpoint_kind="password_submit",
            http_method="POST", run_id=original["id"], execution_id="original-execution",
        )
        registration.advance_checkpoint(attempt_id, "failed", target_status="request_unknown")
        registration.finish_run(original["id"], status="failed")
        db.update_job(root_id, status="failed", error="request_unknown")
        source_id = root_id
        expected_unknown = {"original-unknown"}
        for index in range(2):
            info = service.get_retry_info(db.get_job(source_id))
            self.assertTrue(info["retryable"], info)
            self.assertEqual(info["retry_action"], "registration_resume")
            listing = admin_repository.list_jobs(
                admin_repository.PageRequest(filters={"id": str(source_id)}),
                progress_batch_id="automatic-resume-batch",
            )
            self.assertTrue(listing["items"][0].get("retryable"), listing["items"][0].get("retry_reason"))
            progress_row = next(row for row in listing["progress_rows"] if row["id"] == source_id)
            self.assertTrue(progress_row.get("retryable"))
            with patch.object(service, "get_executor", return_value=Mock()), \
                 patch.object(service, "is_job_worker_active", return_value=False):
                result = service.retry_job(source_id)
            self.assertTrue(result["ok"], result)
            child = db.get_job(result["job"]["id"])
            self.assertEqual(child["attempt_id"], attempt_id)
            self.assertEqual(child["email"], address)
            self.assertEqual(child["root_job_id"], root_id)
            self.assertEqual(child["job_type"], "registration_resume")
            self.assertIsNone(child["account_id"])
            self.assertEqual(service._private_registration_resume_password(child), password)
            execution = f"resume-execution-{index}"
            run = registration.start_run(
                attempt_id, job_id=child["id"], action_type="registration_resume",
                execution_id=execution, initial_status="running",
            )
            submission_id = f"resume-unknown-{index}"
            registration.record_submission_fact(
                attempt_id, submission_id=submission_id, kind="resume_login",
                stage="login_password", phase="unknown", endpoint_kind="password_submit",
                http_method="POST", run_id=run["id"], execution_id=execution,
            )
            expected_unknown.add(submission_id)
            private = registration.get_private_resume_context(attempt_id, email=address)
            self.assertEqual(private["password"], password)
            self.assertEqual(unresolved_submission_ids(private["submission_facts"]), expected_unknown)
            if index == 0:
                registration.finish_run(run["id"], status="failed")
                db.update_job(child["id"], status="failed", error="request_unknown")
                source_id = child["id"]
        core = registration.persist_core_account(
            attempt_id, access_token="offline-resume-token", account={"email": address},
            run_id=run["id"], job_id=child["id"], execution_id=execution,
        )
        self.assertIsNotNone(core["account_id"])
        self.assertEqual(core["attempt"]["checkpoint"], "core_persisted")
        self.assertEqual(core["attempt"]["remote_account_state"], "confirmed")
        self.assertEqual(
            unresolved_submission_ids(registration.get_private_resume_context(
                attempt_id, email=address,
            )["submission_facts"]), expected_unknown,
        )
