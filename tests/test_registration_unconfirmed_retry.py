"""注册未确认成功时按失败处理，并保留原身份重跑。"""
import copy
import unittest
from unittest.mock import Mock, patch

from core import registration_service as svc
from tests import test_registration_resume_retry_chain as resume_tests
from webui.routes import operations

facts = resume_tests.facts

def pre_account_facts():
    job = {"id": 21, "attempt_id": 70, "status": "request_unknown",
           "email": "held@example.test", "email_source": "icloud_hide"}
    attempt = {"id": 70, "source_root_job_id": 21, "email_snapshot": job["email"],
               "checkpoint": "auth_started", "remote_identity_state": "not_started",
               "remote_account_state": "not_started", "local_account_state": "none",
               "target_status": "not_created"}
    return job, attempt


class UnconfirmedRegistrationRetryTests(unittest.TestCase):
    def test_unconfirmed_driver_results_are_failed(self):
        for result in ({"request_unknown": True}, {"manual_reconcile": True},
                       {"account_id": 44},
                       {"registration_pending": True, "account_id": 44, "registration_success": True}):
            with self.subTest(result=result):
                self.assertEqual(svc.registration_result_status(result), "failed")

    def test_persisted_token_confirms_registration_despite_postprocess_error(self):
        self.assertEqual(svc.registration_result_status({
            "success": False, "account_id": 44, "access_token": "test-token",
            "request_unknown": True, "error": "注册后的配置请求超时",
        }), "success")

    def test_unpersisted_core_cannot_be_confirmed_by_pending_id_and_memory_token(self):
        for core_persisted in (False, None, "true", 1):
            with self.subTest(core_persisted=core_persisted):
                self.assertEqual(svc.registration_result_status({
                    "success": True, "registration_success": True,
                    "account_id": 44, "access_token": "test-token",
                    "core_persisted": core_persisted,
                }), "failed")

    def test_explicitly_persisted_core_survives_later_postprocess_failure(self):
        self.assertEqual(svc.registration_result_status({
            "success": False, "account_id": 44, "core_persisted": True,
            "request_unknown": True, "error": "注册后的配置请求超时",
        }), "success")

    def test_core_marker_requires_account_and_completed_email_verification(self):
        for fields in ({}, {"account_id": 44, "registration_pending": True}):
            with self.subTest(fields=fields):
                self.assertEqual(svc.registration_result_status({
                    "success": True, "core_persisted": True, **fields,
                }), "failed")

    def test_old_email_submission_unknown_can_retry_original_email(self):
        job, attempt = pre_account_facts()
        for status in ("failed", "request_unknown", "manual_reconcile"):
            with self.subTest(status=status):
                info = svc._build_retry_info(dict(job, status=status), account=None,
                                            attempt=attempt, successful_retry=None)
                self.assertTrue(info["retryable"])
                self.assertEqual(info["retry_action"], "registration")
                self.assertEqual(info["display_status"], "failed")

    def test_failed_pre_account_task_with_unresolved_submission_is_not_retryable(self):
        job, attempt = pre_account_facts()
        job["status"] = "failed"
        with patch("core.storage.registration.has_unresolved_submission_facts", return_value=True):
            info = svc._build_retry_info(
                job, account=None, attempt=attempt, successful_retry=None,
            )
        self.assertFalse(info["retryable"])
        self.assertIn("未决", info["retry_reason"])

    def test_old_unconfirmed_child_loads_root_for_single_and_bulk_retry(self):
        root, attempt = pre_account_facts()
        child = dict(root, id=22, root_job_id=21, parent_job_id=21)
        with patch.object(svc.db, "get_successful_retry_for_job", return_value=None), \
             patch.object(svc, "_account_for_job", return_value=None), \
             patch.object(svc, "_read_linked_attempt_for_job", return_value=(attempt, False)), \
             patch.object(svc, "_retry_jobs_by_ids", side_effect=lambda ids: {21: root} if 21 in ids else {}):
            self.assertTrue(svc.get_retry_info(child)["retryable"])
        with patch.object(svc.db, "get_successful_retries_for_jobs", return_value={}), \
             patch.object(svc.db, "get_accounts_for_jobs", return_value={}), \
             patch("core.storage.registration.get_attempts_for_root_jobs", return_value={21: attempt}), \
             patch.object(svc, "_retry_jobs_by_ids", side_effect=lambda ids: {21: root} if 21 in ids else {}):
            self.assertTrue(svc.get_retry_info_bulk([child])[22]["retryable"])

    def test_unknown_identity_without_recovery_context_is_not_resubmitted(self):
        job, attempt = pre_account_facts()
        for changes in ({"remote_account_state": "confirmed"}, {"remote_identity_state": "request_unknown"},
                        {"checkpoint": "password_request_started"}, {"email_snapshot": "other@example.test"},
                        {"id": 999}, {"source_root_job_id": 999}):
            with self.subTest(changes=changes):
                info = svc._build_retry_info(job, account=None, attempt=dict(attempt, **changes),
                                            successful_retry=None)
                self.assertFalse(info["retryable"])

    def test_saved_password_can_resume_unknown_or_manual_attempt(self):
        root, child, account, attempt = facts()
        for status in ("request_unknown", "manual_reconcile"):
            with self.subTest(status=status):
                saved = dict(attempt, checkpoint="manual_reconcile", target_status=status,
                             remote_identity_state="request_unknown")
                info = svc._build_retry_info(dict(child, status=status), account=account,
                    attempt=saved, successful_retry=None, root_job=root)
                self.assertTrue(info["retryable"])
                self.assertEqual(info["retry_action"], "registration_resume")
                self.assertEqual(info["display_status"], "failed")

    def test_confirmed_account_ignores_old_unknown_label_and_only_retries_postprocess(self):
        root, child, account, attempt = facts()
        account.update(access_token="test-token", codex_status="failed")
        account["extra_json"]["registration_checkpoint"] = "core_persisted"
        attempt.update(checkpoint="core_persisted", target_status="account_available",
                       remote_identity_state="confirmed", remote_account_state="confirmed", local_account_state="persisted")
        for status in ("request_unknown", "manual_reconcile"):
            with self.subTest(status=status):
                info = svc._build_retry_info(dict(child, status=status), account=account,
                    attempt=attempt, successful_retry=None, root_job=root)
                self.assertTrue(info["retryable"])
                self.assertEqual(info["retry_action"], "codex")

    def test_uncertain_paid_order_is_still_blocked(self):
        job, attempt = pre_account_facts()
        job.update(email_source="remail", error_message="request_unknown: Remail 邮箱订单结果待核验")
        info = svc._build_retry_info(job, account=None, attempt=attempt, successful_retry=None)
        self.assertFalse(info["retryable"])
        self.assertIn("订单", info["retry_reason"])

    def test_task_center_exposes_retry_for_latest_original_registration_job(self):
        job, attempt = pre_account_facts()
        task = {"id": 9, "task_type": "registration", "source_system": "registration_chains",
                "source_id": "21:registration", "status": "request_unknown", "target_status": "not_created",
                "latest_legacy_job_id": 21, "next_actions": []}
        info = svc._build_retry_info(job, account=None, attempt=attempt, successful_retry=None)
        with patch.object(svc, "_retry_jobs_by_ids", return_value={21: job}), \
             patch.object(svc, "get_retry_info_bulk", return_value={21: info}):
            svc.attach_registration_resume_retry_info([task])
        self.assertEqual(task["status"], "request_unknown")
        self.assertTrue(task["retryable"])
        self.assertEqual(task["next_actions"][0]["action"], "registration_retry")
        self.assertEqual(task["next_actions"][0]["source_job_id"], 21)

    def test_task_center_preserves_postprocess_actions_for_confirmed_old_unknown(self):
        job, _ = pre_account_facts()
        for retry_action, task_action in (("codex", "codex_retry"), ("twofa", "twofa_retry"),
                                          ("plan_check", "plan_check")):
            with self.subTest(action=retry_action):
                task = {"id": 9, "task_type": "registration", "source_system": "registration_chains",
                        "source_id": "21:registration", "status": "request_unknown",
                        "target_status": "request_unknown", "latest_legacy_job_id": 21, "next_actions": []}
                info = {"retryable": True, "retry_action": retry_action, "retry_label": "补跑后处理"}
                with patch.object(svc, "_retry_jobs_by_ids", return_value={21: job}), \
                     patch.object(svc, "get_retry_info_bulk", return_value={21: info}):
                    svc.attach_registration_resume_retry_info([task])
                self.assertTrue(task["retryable"])
                self.assertEqual(task["next_actions"], [{"action": task_action, "label": "补跑后处理",
                                                         "source_job_id": 21}])

    def test_single_and_bulk_routes_reuse_original_email(self):
        job, attempt = pre_account_facts()
        task = {"id": 9, "task_type": "registration", "source_system": "registration_chains",
                "source_id": "21:registration", "status": "request_unknown", "next_actions": [],
                "runs": [{"source_system": "registration_jobs", "source_id": "21"}]}
        client = resume_tests.ResumeRetryChainTests._client()
        with patch.object(operations.operation_task_store, "get_task", side_effect=lambda *a, **kw: copy.deepcopy(task)), \
             patch.object(svc.db, "get_job", return_value=job), \
             patch.object(svc.db, "get_successful_retry_for_job", return_value=None), \
             patch.object(svc, "_account_for_job", return_value=None), \
             patch.object(svc, "_read_linked_attempt_for_job", return_value=(attempt, False)), \
             patch.object(svc.db, "create_retry_job", return_value=({"id": 22, "log_file": "/tmp/test-registration-retry.log"}, True)) as create, \
             patch.object(svc, "get_executor", return_value=Mock()):
            single = client.post("/api/operations/9/retry")
            bulk = client.post("/api/operations/bulk", json={"action": "retry", "task_ids": [9]})
        self.assertEqual(single.status_code, 200)
        self.assertEqual(bulk.get_json()["accepted_count"], 1)
        for call in create.call_args_list:
            self.assertEqual(call.kwargs["email"], job["email"])
            self.assertEqual(call.kwargs["email_source"], "icloud_hide")
