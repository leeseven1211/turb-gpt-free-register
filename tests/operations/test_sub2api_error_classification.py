"""Sub2API 固定原因码保留传输、鉴权、契约与本地阶段，不猜远端账号状态。"""
import unittest

from core.operations.errors import _SUB2API_ERROR_DETAILS, classify_task_error


class Sub2ApiErrorClassificationTests(unittest.TestCase):
    def test_every_registered_code_has_specific_category_and_stage(self):
        for code, (category, display, _message) in _SUB2API_ERROR_DETAILS.items():
            with self.subTest(code=code):
                value = classify_task_error("诊断原文", task_type="sub2api_manual_upload", stage="complete",
                                            result_summary={"error_code": code, "stage": "upload"}, task_status="failed")
                self.assertEqual(f"external.sub2api.{category}", value["code"])
                self.assertEqual(code, value["error_code"])
                self.assertEqual(display, value["display_code"])
                self.assertEqual("upload", value["stage"])
                self.assertNotIn("UNK", value["display_code"])

    def test_timeout_with_unknown_receipt_stays_transport_and_keeps_unknown_fact(self):
        result = classify_task_error("请求超时", task_type="sub2api_manual_upload", result_summary={
            "error_code": "sub2api_timeout", "stage": "upload", "outcome": "request_unknown",
        }, task_status="attention_required")
        self.assertEqual("external.sub2api.transport", result["code"])
        self.assertTrue(result["reconcile_required"])
        self.assertEqual("unknown", result["remote_state_impact"])
        self.assertNotIn("封号", result["summary"])
        self.assertNotIn("鉴权", result["summary"])

    def test_arbitrary_remote_text_does_not_create_a_specific_sub2api_cause(self):
        result = classify_task_error("remote claimed auth failure", task_type="sub2api_manual_upload",
                                     error_code="future_unverified", task_status="failed")
        self.assertNotEqual("external.sub2api.auth", result["code"])
