"""同一 Attempt 重跑按显式账号归属恢复，不能被同批次重复邮箱误挡。"""
from unittest.mock import patch

from core import db
from core.registration import service
from core.storage import records, registration
from tests.support_pg import PostgresTestCase


class AttemptLinkedRetryAccountTests(PostgresTestCase):
    def job(self, *, email="linked@example.test", batch="linked-batch", **fields):
        return records.insert_row(records.JOBS, {
            "email": email, "email_source": "email_butler", "batch_id": batch,
            "status": "failed", "job_type": "registration", "created_at": "2026-11-06T00:00:00+00:00",
            "updated_at": "2026-11-06T00:00:00+00:00", **fields,
        })

    def linked_placeholder(self):
        root_id = self.job()
        attempt = registration.create_attempt(
            "linked@example.test", root_job_id=root_id, email_source="email_butler", driver="protocol_oss_2",
        )
        attempt_id = int(attempt["id"])
        records.patch_row(records.JOBS, root_id, {"attempt_id": attempt_id})
        run = registration.start_run(attempt_id, job_id=root_id, initial_status="running", execution_id="fixture-execution")
        saved = registration.save_password_checkpoint(
            attempt_id, email="linked@example.test", password="fixture-original", state="confirmed",
            run_id=int(run["id"]), execution_id="fixture-execution", job_id=root_id,
            account={"email_source": "email_butler"},
        )
        registration.advance_checkpoint(attempt_id, "account_request_started")
        registration.mark_request_unknown(attempt_id, target="account")
        registration.finish_run(int(run["id"]), status="failed", error_code="email_otp_no_mail")
        child_id = self.job(root_job_id=root_id, parent_job_id=root_id, attempt_id=attempt_id)
        return root_id, child_id, attempt_id, int(saved["account_id"])

    def test_same_batch_retry_uses_attempt_placeholder_and_can_resume(self):
        root_id, child_id, attempt_id, account_id = self.linked_placeholder()
        child = db.get_job(child_id)
        self.assertIsNone(child["account_id"])
        self.assertEqual(2, db.count_registration_jobs_by_batch_email("linked-batch", child["email"]))
        account = service._account_for_job(child)
        self.assertEqual(account_id, account["id"])
        self.assertFalse(account["access_token"])
        self.assertEqual("none", registration.get_attempt(attempt_id)["local_account_state"])
        with patch.object(db, "get_successful_retry_for_job", return_value=None):
            info = service.get_retry_info(child, account_override=account)
        self.assertTrue(info["retryable"], info)
        self.assertEqual("registration_resume", info["retry_action"])
        projected = db.get_accounts_for_jobs([db.get_job(root_id), child])
        self.assertEqual({root_id, child_id}, set(projected))
        self.assertTrue(all(item["id"] == account_id for item in projected.values()))
        infos = service.get_retry_info_bulk([db.get_job(root_id), child])
        self.assertTrue(all(item["retryable"] for item in infos.values()), infos)
        self.assertTrue(all(item["retry_action"] == "registration_resume" for item in infos.values()), infos)

    def test_wrong_email_or_explicit_account_conflict_cannot_fall_back(self):
        root_id, child_id, _attempt_id, _account_id = self.linked_placeholder()
        other_account = records.insert_row(records.ACCOUNTS, {"email": "other@example.test", "access_token": "fixture-at"})
        original = db.get_job(child_id)
        for changed in (
            {"email": "other@example.test"},
            {"account_id": other_account},
            {"root_job_id": root_id + 999},
        ):
            with self.subTest(changed=changed):
                child = {**original, **changed}
                self.assertIsNone(service._account_for_job(child))
                self.assertNotIn(child_id, db.get_accounts_for_jobs([child]))

    def test_wrong_account_email_is_rejected_even_for_matching_ids(self):
        root_id, child_id, _attempt_id, account_id = self.linked_placeholder()
        records.patch_row(records.ACCOUNTS, account_id, {"email": "changed@example.test"})
        child = db.get_job(child_id)
        self.assertIsNone(service._account_for_job(child))
        self.assertNotIn(child_id, db.get_accounts_for_jobs([db.get_job(root_id), child]))

    def test_independent_jobs_with_same_batch_email_still_cannot_claim_account(self):
        records.insert_row(records.ACCOUNTS, {"email": "linked@example.test", "access_token": "fixture-at"})
        first, second = self.job(), self.job()
        jobs = [db.get_job(first), db.get_job(second)]
        self.assertTrue(all(service._account_for_job(job) is None for job in jobs))
        self.assertEqual({}, db.get_accounts_for_jobs(jobs))

    def test_missing_explicit_account_does_not_take_another_email_match(self):
        _root_id, child_id, _attempt_id, account_id = self.linked_placeholder()
        records.delete_rows_where_returning(records.ACCOUNTS, where="id=%s", params=(account_id,))
        records.insert_row(records.ACCOUNTS, {"email": "linked@example.test", "access_token": "fixture-other-at"})
        child = db.get_job(child_id)
        self.assertIsNone(service._account_for_job(child))
        self.assertEqual({}, db.get_accounts_for_jobs([child]))

    def test_attempt_without_account_link_does_not_claim_independent_email_match(self):
        root_id = self.job(batch="independent-batch")
        attempt = registration.create_attempt(
            "linked@example.test", root_job_id=root_id, email_source="email_butler", driver="protocol_oss_2",
        )
        records.patch_row(records.JOBS, root_id, {"attempt_id": int(attempt["id"])})
        records.insert_row(records.ACCOUNTS, {"email": "linked@example.test", "access_token": "fixture-other-at"})
        root = db.get_job(root_id)
        self.assertIsNone(service._account_for_job(root))
        self.assertEqual({}, db.get_accounts_for_jobs([root]))
