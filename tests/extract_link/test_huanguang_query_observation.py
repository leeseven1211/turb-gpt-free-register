"""保留历史节点时仍应向续查策略报告当前查询故障。"""

from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from urllib.error import HTTPError

from core.extract_link.huanguang.client import HuanguangProvider
from tests.extract_link.test_huanguang_document_contract import _config, _Transport


class HuanguangQueryObservationTests(TestCase):
    root_id = "0123456789abcdef"
    child_id = "fedcba9876543210"

    def private(self, *, child=False):
        chain = [{"job_id": self.root_id, "parent_job_id": None, "state": {
            "extraction_state": "succeeded", "payment_state": "pending",
            "links": ["https://pay.example.test/retained"],
            "payment_artifact": {"qr_data": "upi://pay?pa=fixture"},
            "summary": {"remote_status": "RUNNING", "remote_polling": True},
        }}]
        if child:
            chain.append({"job_id": self.child_id, "parent_job_id": self.root_id, "state": {
                "extraction_state": "running", "payment_state": "pending",
                "summary": {"remote_status": "RUNNING", "remote_polling": True},
            }})
        return {"job_secret": "synthetic-private-secret", "job_chain": chain}

    def response(self, status):
        return SimpleNamespace(status_code=status, json=lambda: {"error": "synthetic-private-response"})

    def test_saved_snapshot_404_reports_failure_and_preserves_material(self):
        private = self.private()
        before = deepcopy(private)
        job = HuanguangProvider(_config(), _Transport([self.response(404)])).get_status(
            self.root_id, private_data=private,
        )
        self.assertIs(True, job.private_data.get("latest_query_failed"))
        self.assertEqual(404, job.private_data.get("latest_query_http_status"))
        self.assertEqual("succeeded", job.extraction_state)
        self.assertEqual(("https://pay.example.test/retained",), job.links)
        self.assertEqual("upi://pay?pa=fixture", job.payment_artifact.get("qr_data"))
        self.assertEqual(before, private)

    def test_success_clears_previous_failure_observation(self):
        private = self.private()
        private.update(latest_query_failed=True, latest_query_http_status=404)
        job = HuanguangProvider(_config(), _Transport([{"status": "running"}])).get_status(
            self.root_id, private_data=private,
        )
        self.assertIs(False, job.private_data.get("latest_query_failed"))
        self.assertIsNone(job.private_data.get("latest_query_http_status"))

    def test_latest_child_failure_is_not_hidden_by_parent_success(self):
        job = HuanguangProvider(_config(), _Transport([
            self.response(404), {"status": "running"},
        ])).get_status(self.root_id, private_data=self.private(child=True))
        self.assertIs(True, job.private_data.get("latest_query_failed"))
        self.assertEqual(404, job.private_data.get("latest_query_http_status"))

    def test_parent_failure_does_not_override_fresh_latest_child_success(self):
        private = self.private(child=True)
        private.update(latest_query_failed=True, latest_query_http_status=404)
        job = HuanguangProvider(_config(), _Transport([
            {"status": "running"}, self.response(404),
        ])).get_status(self.root_id, private_data=private)
        self.assertIs(False, job.private_data.get("latest_query_failed"))
        self.assertIsNone(job.private_data.get("latest_query_http_status"))

    def test_receipt_failures_report_http_status_and_keep_recovery_fields(self):
        for response, status in (
            (self.response(404), 404),
            (HTTPError("https://example.test/receipt", 503, "private", {}, BytesIO(b"private")), 503),
            (TimeoutError("synthetic-private-failure"), None),
        ):
            with self.subTest(status=status):
                job = HuanguangProvider(_config(), _Transport([response])).get_status("", private_data={
                    "batch_receipt_secret": "synthetic-batch-secret", "batch_receipt_pending": True,
                })
                self.assertIs(True, job.private_data.get("latest_query_failed"))
                self.assertEqual(status, job.private_data.get("latest_query_http_status"))
                self.assertIs(True, job.private_data.get("batch_receipt_pending"))
                self.assertEqual("synthetic-batch-secret", job.private_data.get("batch_receipt_secret"))
                self.assertIs(True, job.summary.get("submission_receipt_pending"))

    def test_successful_pending_receipt_clears_previous_failure_observation(self):
        job = HuanguangProvider(_config(), _Transport([{"state": "processing"}])).get_status("", private_data={
            "batch_receipt_secret": "synthetic-batch-secret", "batch_receipt_pending": True,
            "latest_query_failed": True, "latest_query_http_status": 404,
        })
        self.assertIs(False, job.private_data.get("latest_query_failed"))
        self.assertIsNone(job.private_data.get("latest_query_http_status"))
