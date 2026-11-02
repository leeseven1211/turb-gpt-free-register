"""暗光工作台只读投影沿用公共状态，并分开展示出链、扫码和到账。"""

from unittest import TestCase

from core.extract_link.workbench_queries import (
    provider_status_label,
    workbench_batch_summary,
    workbench_task_item,
    workbench_status_matches,
)


class AnguangWorkbenchProjectionTests(TestCase):
    def row(self, payment_state="pending"):
        return {
            "task_id": 71, "run_id": 72, "run_status": "running",
            "task_created_at": "2026-11-02T08:00:00Z",
            "task_data": {"provider_id": "anguang", "mode": "auto_payment", "link_type": "upi",
                          "payment_source": "native"},
            "public_state": {"extraction_state": "succeeded", "payment_state": payment_state,
                             "plus_status": "unknown", "links": ["https://example.test/payment"],
                             "summary": {"remote_status": "SUCCEEDED"}},
        }

    def test_succeeded_normalizes_to_extracted_without_claiming_payment_or_plus(self):
        self.assertEqual("success", provider_status_label("SUCCEEDED"))
        item = workbench_task_item(self.row())
        self.assertEqual("anguang", item["provider_id"])
        self.assertEqual("success", item["extraction_status"])
        self.assertEqual("pending_payment", item["payment_status"])
        self.assertEqual("unknown", item["plus_status"])
        self.assertTrue(workbench_status_matches(item, "extraction_succeeded"))
        self.assertFalse(workbench_status_matches(item, "payment_succeeded"))
        self.assertFalse(workbench_status_matches(item, "plus_confirmed"))

    def test_completed_scan_shows_paid_while_plus_still_awaits_independent_confirmation(self):
        item = workbench_task_item(self.row(payment_state="succeeded"))
        self.assertEqual("paid", item["payment_status"])
        self.assertEqual("unknown", item["plus_status"])
        self.assertTrue(workbench_status_matches(item, "payment_succeeded"))
        self.assertFalse(workbench_status_matches(item, "plus_confirmed"))

    def test_fresh_independent_plus_confirmation_does_not_rewrite_scan_result(self):
        item = workbench_task_item(self.row(), account={
            "plan_check_status": "success", "current_plan_type": "plus",
            "plan_checked_at": "2026-11-02T08:01:00Z",
        })
        self.assertEqual("confirmed", item["plus_status"])
        self.assertEqual("pending_payment", item["payment_status"])
        self.assertTrue(workbench_status_matches(item, "plus_confirmed"))
        self.assertFalse(workbench_status_matches(item, "payment_succeeded"))

    def test_task_and_batch_show_frozen_native_source_and_omit_payment_material(self):
        item = workbench_task_item(self.row())
        batch = workbench_batch_summary({"id": 73, "requested_count": 1, "data": {
            "provider_id": "anguang", "mode": "auto_payment", "payment_source": "native",
            "submission_complete": True,
        }}, {"all": 1, "processing": 1, "extraction_succeeded": 1})
        for projection in (item, batch):
            self.assertEqual("anguang", projection["provider_id"])
            self.assertEqual("native", projection["payment_source"])
            self.assertEqual("平台自带", projection["payment_source_label"])
            self.assertNotIn("example.test/payment", repr(projection))
        self.assertTrue(item["has_payment_entry"])
        self.assertEqual(1, batch["counts"]["extraction_succeeded"])
        self.assertEqual(0, batch["counts"]["payment_succeeded"])
        self.assertEqual(0, batch["counts"]["plus_confirmed"])
