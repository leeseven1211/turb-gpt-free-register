"""使用流光公开文档的任务快照核对进度、失败与支付边界。"""
from __future__ import annotations

from copy import deepcopy
import unittest

from core.extract_link_providers.contracts import ProviderConfig
from core.extract_link_providers.lumen_flow import LumenFlowProvider


_TASK_ID = "9c7f1f0e-2a8b-4c69-9d17-1f49f30a3e72"
_RUNNING_SNAPSHOT = {
    "taskId": _TASK_ID,
    "email": "fixture@example.test",
    "paymentMethodType": "IDEAL",
    "planName": "chatgptplusplan",
    "processingMode": "STANDARD",
    "automaticMomoPayment": False,
    "automaticMomoPaymentStatusUrl": None,
    "status": "RUNNING",
    "statusUrl": f"/public/api/checkout/flow/{_TASK_ID}",
    "deduplicated": False,
    "currentStep": "CREATE_PAYMENT_METHOD",
    "completedSteps": 7,
    "skippedSteps": [],
    "totalSteps": 12,
    "progressPercent": 58,
    "runAttempt": 1,
    "stepAttempt": 1,
    "lastEvent": "StepStarted",
    "failureCode": None,
    "failureType": None,
    "createdAt": "2026-09-10T10:00:00Z",
    "startedAt": "2026-09-10T10:00:00Z",
    "updatedAt": "2026-09-10T10:00:12Z",
    "completedAt": None,
    "paymentStateSyncAttempts": 0,
    "nextPaymentStateSyncAt": None,
    "plusVerificationStatus": "WAITING_FOR_PAYMENT",
    "plusVerificationAttempts": 0,
    "nextPlusVerificationAt": None,
    "plusVerifiedAt": None,
    "egress": None,
    "result": None,
}


class _SnapshotTransport:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def request(self, method, path, **_kwargs):
        if method != "GET" or path not in {
            f"/public/api/checkout/flow/{_TASK_ID}",
            f"/public/api/checkout/flow/{_TASK_ID}/momo-payment",
        }:
            raise AssertionError("文档契约测试只允许查询占位任务")
        return deepcopy(self.snapshot)


def _provider(snapshot):
    return LumenFlowProvider(
        ProviderConfig(
            provider_id="lumen_flow", api_base="https://example.invalid", cdk="private-cdk",
            capabilities={"extract": True, "payment": True},
        ),
        _SnapshotTransport(snapshot),
    )


class LumenFlowDocumentContractTests(unittest.TestCase):
    def test_documented_running_snapshot_retains_published_progress(self):
        job = _provider(_RUNNING_SNAPSHOT).get_status(_TASK_ID)

        self.assertEqual(job.extraction_state, "running")
        self.assertEqual(job.summary.get("percent"), 58)
        self.assertEqual(job.summary.get("completed_steps"), 7)
        self.assertEqual(job.summary.get("total_steps"), 12)
        self.assertEqual(job.summary.get("run_attempt"), 1)
        self.assertEqual(job.summary.get("step_attempt"), 1)
        self.assertEqual(job.summary.get("last_event"), "StepStarted")
        self.assertEqual(job.summary.get("current_step"), "CREATE_PAYMENT_METHOD")
        self.assertEqual(job.summary.get("plus_verification_status"), "WAITING_FOR_PAYMENT")

    def test_remote_retry_can_reset_progress_without_becoming_terminal_failure(self):
        snapshot = {
            **_RUNNING_SNAPSHOT, "completedSteps": 0, "progressPercent": 0,
            "runAttempt": 2, "stepAttempt": 3, "lastEvent": "StepRetryScheduled",
            "failureCode": "RATE_LIMITED", "failureType": "RATE_LIMITED",
        }
        job = _provider(snapshot).get_status(_TASK_ID)

        self.assertEqual(job.extraction_state, "running")
        self.assertEqual(job.summary.get("percent"), 0)
        self.assertEqual(job.summary.get("run_attempt"), 2)
        self.assertEqual(job.summary.get("step_attempt"), 3)
        self.assertEqual(job.summary.get("failure_code"), "RATE_LIMITED")
        self.assertEqual(job.summary.get("failure_type"), "RATE_LIMITED")
        self.assertNotIn("remote_terminal_failure", job.summary)
        self.assertNotIn("failure_message", job.summary)

    def test_documented_failure_code_supplies_chinese_reason_without_error_message(self):
        job = _provider({
            **_RUNNING_SNAPSHOT, "status": "FAILED", "currentStep": "INIT_PAYMENT_PAGE",
            "failureCode": "AMOUNT_POLICY_REJECTED", "failureType": "AMOUNT_REJECTED",
        }).get_status(_TASK_ID)

        self.assertEqual(job.extraction_state, "failed")
        self.assertEqual(job.summary.get("failure_code"), "AMOUNT_POLICY_REJECTED")
        self.assertEqual(job.summary.get("failure_type"), "AMOUNT_REJECTED")
        self.assertIn("金额", job.summary.get("failure_message", ""))
        self.assertIn("上限", job.summary.get("failure_message", ""))

    def test_unknown_failure_code_remains_available_for_diagnosis(self):
        job = _provider({
            **_RUNNING_SNAPSHOT, "status": "FAILED", "failureCode": "FUTURE_FAILURE",
            "failureType": "NewProviderException", "raw": {"accessToken": "private-token"},
        }).get_status(_TASK_ID)

        self.assertEqual(job.summary.get("failure_code"), "FUTURE_FAILURE")
        self.assertEqual(job.summary.get("failure_type"), "NewProviderException")
        self.assertIn("失败", job.summary.get("failure_message", ""))
        self.assertNotIn("raw", job.summary)
        self.assertNotIn("private-token", repr(job))

    def test_invalid_progress_and_secret_bearing_metadata_are_not_retained(self):
        job = _provider({
            **_RUNNING_SNAPSHOT, "progressPercent": True, "completedSteps": -1,
            "totalSteps": "12", "runAttempt": 1.5, "stepAttempt": False,
            "lastEvent": {"accessToken": "private-token"},
            "failureCode": "private-cdk", "failureType": "https://example.test/secret",
        }).get_status(_TASK_ID)

        for key in ("percent", "completed_steps", "total_steps", "run_attempt", "step_attempt", "last_event", "failure_code", "failure_type"):
            self.assertNotIn(key, job.summary)
        self.assertNotIn("private-cdk", repr(job))

    def test_explicit_null_payment_schedule_can_clear_a_previously_saved_schedule(self):
        job = _provider(_RUNNING_SNAPSHOT).get_status(_TASK_ID)

        self.assertIn("next_payment_state_sync_at", job.private_data)
        self.assertIsNone(job.private_data["next_payment_state_sync_at"])

    def test_omitted_payment_schedule_does_not_claim_to_clear_older_services(self):
        snapshot = deepcopy(_RUNNING_SNAPSHOT)
        snapshot.pop("nextPaymentStateSyncAt")
        job = _provider(snapshot).get_status(_TASK_ID)

        self.assertNotIn("next_payment_state_sync_at", job.private_data)

    def test_uncertain_momo_payment_is_terminal_for_automatic_polling(self):
        for status in ("PAYMENT_UNCERTAIN", "SUBMISSION_UNKNOWN"):
            with self.subTest(status=status):
                job = _provider({
                    "checkoutTaskId": _TASK_ID, "status": status,
                    "failureCode": "UPSTREAM_RESULT_UNKNOWN", "upstreamJobId": None,
                    "createdAt": "2026-09-10T10:00:00Z", "updatedAt": "2026-09-10T10:01:00Z",
                    "checkoutCompletedAt": "2026-09-10T10:00:30Z", "submittedAt": None,
                    "nextPollAt": None, "completedAt": "2026-09-10T10:01:00Z",
                }).get_automatic_payment_status(_TASK_ID)

                self.assertEqual(job.payment_state, "unknown")
                self.assertEqual(job.summary.get("automatic_payment_status"), status)
                self.assertIs(job.summary.get("automatic_payment_terminal"), True)
                self.assertIs(job.summary.get("automatic_payment_requires_reconcile"), True)
                self.assertEqual(job.summary.get("failure_code"), "UPSTREAM_RESULT_UNKNOWN")
                self.assertIn("核对", job.summary.get("failure_message", ""))

    def test_pending_momo_payment_does_not_stop_automatic_polling(self):
        job = _provider({
            "checkoutTaskId": _TASK_ID, "status": "PAYMENT_PENDING", "failureCode": None,
        }).get_automatic_payment_status(_TASK_ID)

        self.assertEqual(job.payment_state, "pending")
        self.assertEqual(job.summary.get("automatic_payment_status"), "PAYMENT_PENDING")
        self.assertIs(job.summary.get("automatic_payment_terminal"), False)
        self.assertIs(job.summary.get("automatic_payment_requires_reconcile"), False)
