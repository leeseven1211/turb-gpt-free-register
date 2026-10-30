"""补全只等待同账号的活跃注册，不使用历史注册结果阻断。"""
from core import record_store
from core import account_completion_service as completion
from tests.support_pg import PostgresTestCase


class CompletionRegistrationGuardTests(PostgresTestCase):
    def test_active_registration_matches_account_id_or_normalized_email(self):
        for status in ("pending", "queued", "running", "stopping", "cancelling", "settling", "waiting", "debug_paused"):
            with self.subTest(status=status):
                job_id = record_store.insert_row(record_store.JOBS, {
                    "job_type": "registration_resume", "status": status,
                    "account_id": 4103, "email": "original@example.test",
                })
                active = completion.active_registration_job(4103, "other@example.test")
                self.assertEqual(job_id, active["id"])
                record_store.patch_row(record_store.JOBS, job_id, {"status": "failed"})

        job_id = record_store.insert_row(record_store.JOBS, {
            "job_type": "registration", "status": "running",
            "account_id": None, "email": "  Original@Example.Test  ",
        })
        self.assertEqual(job_id, completion.active_registration_job(4103, "original@example.test")["id"])

    def test_terminal_history_and_other_accounts_do_not_block(self):
        for status in ("failed", "cancelled", "interrupted", "stopped", "success", "partial_success", "attention_required"):
            record_store.insert_row(record_store.JOBS, {
                "job_type": "registration", "status": status,
                "account_id": 4103, "email": "original@example.test",
            })
        record_store.insert_row(record_store.JOBS, {
            "job_type": "registration", "status": "running",
            "account_id": 4104, "email": "another@example.test",
        })
        record_store.insert_row(record_store.JOBS, {
            "job_type": "twofa_retry", "status": "running",
            "account_id": 4103, "email": "original@example.test",
        })
        self.assertIsNone(completion.active_registration_job(4103, "original@example.test"))

    def test_newer_terminal_job_does_not_hide_an_older_active_registration(self):
        active_id = record_store.insert_row(record_store.JOBS, {
            "job_type": "registration_resume", "status": "running",
            "account_id": 4103, "email": "original@example.test",
        })
        record_store.insert_row(record_store.JOBS, {
            "job_type": "registration_resume", "status": "failed",
            "account_id": 4103, "email": "original@example.test",
        })
        self.assertEqual(active_id, completion.active_registration_job(4103, "original@example.test")["id"])
