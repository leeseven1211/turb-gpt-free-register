"""失败续跑拿到 Token 后必须收口原 Attempt，并保留脱敏失败原因。"""
from unittest.mock import patch

from core import account_task_store, db, operation_task_store, record_store
from core.storage import registration
from tests.support_pg import PostgresTestCase


class FailedRegistrationResumeStorageTests(PostgresTestCase):
    def setUp(self):
        self.enterContext(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(account_task_store, "_READY_KEY", ""))
        account_task_store.init()
        operation_task_store.reset_ready()
        operation_task_store.init()

    def _pending_resume(self, checkpoint="manual_reconcile"):
        job = db.create_job("outlook")
        address = "resume@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": address, "access_token": "",
            "extra_json": {"registration_checkpoint": "email_verification_pending"},
        })
        db.update_job(job["id"], email=address, account_id=account_id, status="failed")
        attempt_id = job["attempt_id"]
        original = registration.list_runs(attempt_id)[0]
        registration.finish_run(original["id"], status="failed")
        registration.advance_checkpoint(attempt_id, checkpoint, target_status=checkpoint)
        run = registration.start_run(attempt_id, action_type="registration_resume",
            initial_status="running", execution_id="current-resume")
        return attempt_id, account_id, run

    def test_confirmed_resume_closes_old_manual_checkpoint(self):
        self._assert_confirmed_resume("manual_reconcile")

    def test_confirmed_resume_closes_old_failed_checkpoint(self):
        self._assert_confirmed_resume("failed")

    def _assert_confirmed_resume(self, checkpoint):
        attempt_id, account_id, run = self._pending_resume(checkpoint)
        result = registration.persist_core_account(attempt_id, access_token="test-token",
            account={"id": account_id, "email": "resume@example.test"},
            run_id=run["id"], execution_id="current-resume")
        self.assertEqual(result["account_id"], account_id)
        self.assertEqual(result["attempt"]["checkpoint"], "core_persisted")
        self.assertEqual(result["attempt"]["remote_identity_state"], "confirmed")
        self.assertEqual(result["attempt"]["remote_account_state"], "confirmed")
        self.assertIsNone(result["attempt"]["terminal_at"])
        finished = registration.advance_checkpoint(attempt_id, "completed", target_status="completed")
        self.assertEqual(finished["target_status"], "completed")
        events = registration.events(attempt_id)
        recovery = next(item for item in events if item["event_type"] == "core_persisted")
        self.assertEqual(recovery["detail"]["recovered_checkpoint"], checkpoint)
        self.assertNotIn("test-token", str(events))
        registration.finish_run(run["id"], status="success")

    def test_terminal_resume_rejects_identity_execution_and_deactivation_conflicts(self):
        attempt_id, account_id, run = self._pending_resume()
        cases = [
            {"account": {"id": account_id, "email": "other@example.test"}},
            {"account": {"id": account_id + 1000, "email": "resume@example.test"}},
            {"execution_id": "stale-resume"},
            {"execution_id": None},
            {"run_id": None},
        ]
        for changes in cases:
            kwargs = {"account": {"id": account_id, "email": "resume@example.test"},
                      "run_id": run["id"], "execution_id": "current-resume"}
            kwargs.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                registration.persist_core_account(attempt_id, access_token="test-token", **kwargs)
        registration.advance_checkpoint(attempt_id, "failed", target_status="deactivated")
        with self.assertRaises(ValueError):
            registration.persist_core_account(attempt_id, access_token="test-token",
                account={"id": account_id, "email": "resume@example.test"},
                run_id=run["id"], execution_id="current-resume")
        self.assertEqual(registration.get_attempt(attempt_id)["target_status"], "deactivated")
        self.assertEqual(record_store.get_row(record_store.ACCOUNTS, account_id)["access_token"], "")

    def test_postprocessing_checkpoint_still_cannot_be_rewound(self):
        attempt_id, account_id, run = self._pending_resume("postprocessing")
        with self.assertRaises(ValueError):
            registration.persist_core_account(attempt_id, access_token="test-token",
                account={"id": account_id, "email": "resume@example.test"},
                run_id=run["id"], execution_id="current-resume")

    def test_failed_run_projects_unknown_cause_without_reclassifying_task(self):
        job = db.create_job("outlook")
        db.update_job(job["id"], status="failed", error="request_unknown", email="cause@example.test")
        run = registration.list_runs(job["attempt_id"])[0]
        registration.finish_run(run["id"], status="failed", result_summary={
            "outcome": "request_unknown", "cause_code": "email_otp_no_mail",
            "register_response_confirmed": True, "raw_response": "不可投影",
        })
        operation_task_store.sync_registration_job(job["id"])
        task = next(row for row in operation_task_store.list_tasks(page_size=20)["items"]
                    if row["source_id"] == f"{job['id']}:registration")
        detail = operation_task_store.get_task(task["id"], include_events=False)
        for item in (task, detail, detail["runs"][-1]):
            self.assertEqual(item["status"], "failed")
            self.assertEqual(item["result_summary"]["cause_code"], "email_otp_no_mail")
            self.assertTrue(item["result_summary"]["register_response_confirmed"])
            self.assertNotIn("raw_response", item["result_summary"])
