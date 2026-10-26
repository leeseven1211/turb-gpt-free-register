from unittest import TestCase

from core import extract_link_service as service


class ExtractWorkbenchStatusSemanticsTests(TestCase):
    def item(self, **changes):
        return {
            "provider_id": "huanguang",
            "mode": "auto_payment",
            "task_status": "request_unknown",
            "extraction_status": "pending",
            "payment_status": "request_unknown",
            "plus_status": "not_applicable",
            **changes,
        }

    def test_unconfirmed_request_without_halt_marker_is_attention_only(self):
        for status in ("request_unknown", "attention_required", "failed", "partial_success"):
            with self.subTest(status=status):
                item = self.item(task_status=status)
                self.assertFalse(service._workbench_status_matches(item, "processing"))
                self.assertFalse(service._workbench_status_matches(item, "running"))
                self.assertTrue(service._workbench_status_matches(item, "needs_attention"))

    def test_provider_request_failure_projection_does_not_claim_execution(self):
        item = service._workbench_task_item({
            "task_id": 256642, "run_id": 123,
            "task_data": {"provider_id": "huanguang", "mode": "auto_payment"},
            "run_status": "attention_required", "error_message": "Provider 请求失败",
            "public_state": {
                "preflight_status": "passed", "extraction_state": "pending",
                "payment_state": "unknown", "plus_status": "not_applicable",
            },
        })
        self.assertEqual("request_unknown", item["task_status"])
        self.assertFalse(item["local_reconcile_halted"])
        self.assertFalse(service._workbench_status_matches(item, "processing"))
        self.assertTrue(service._workbench_status_matches(item, "needs_attention"))

    def test_scheduled_and_running_unknown_payments_remain_processing(self):
        for status in ("queued", "running", "waiting", "cancelling", "settling", "stopping"):
            with self.subTest(status=status):
                item = self.item(task_status=status)
                self.assertTrue(service._workbench_status_matches(item, "processing"))
                self.assertEqual(status in {"running", "cancelling", "settling", "stopping"},
                                 service._workbench_status_matches(item, "running"))

    def test_real_pending_payment_remains_processing(self):
        item = self.item(task_status="partial_success", extraction_status="success", payment_status="pending_payment")
        self.assertTrue(service._workbench_status_matches(item, "processing"))
        self.assertFalse(service._workbench_status_matches(item, "running"))

    def test_paid_payment_still_waits_for_plus_verification(self):
        for plus in ("unknown", "pending", "queued"):
            with self.subTest(plus=plus):
                item = self.item(task_status="success", extraction_status="success", payment_status="paid", plus_status=plus)
                self.assertTrue(service._workbench_status_matches(item, "processing"))
                self.assertTrue(service._workbench_status_matches(item, "payment_succeeded"))

    def test_halted_original_stays_attention_even_if_queued(self):
        item = self.item(task_status="queued", local_reconcile_halted=True)
        self.assertFalse(service._workbench_status_matches(item, "processing"))
        self.assertTrue(service._workbench_status_matches(item, "needs_attention"))
