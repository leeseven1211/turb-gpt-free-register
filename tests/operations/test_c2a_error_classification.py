"""C2A 导入的固定错误码必须保留可操作的任务中心分类。"""
from __future__ import annotations

import unittest

from core.operations.errors import _C2A_ERROR_DETAILS, classify_task_error


class C2AErrorClassificationTests(unittest.TestCase):
    def test_every_registered_code_has_specific_category_and_stage(self):
        for code, (category, display, _message) in _C2A_ERROR_DETAILS.items():
            with self.subTest(code=code):
                value = classify_task_error(
                    "诊断原文",
                    task_type="c2a_session_reimport",
                    stage="complete",
                    result_summary={"error_code": code, "stage": "c2a_update"},
                    task_status="failed",
                )
                self.assertEqual(f"external.c2a.{category}", value["code"])
                self.assertEqual(code, value["error_code"])
                self.assertEqual(display, value["display_code"])
                self.assertEqual("c2a_update", value["stage"])
                self.assertNotIn("UNK", value["display_code"])

    def test_timeout_with_unknown_receipt_stays_transport_and_keeps_unknown_fact(self):
        result = classify_task_error(
            "请求超时",
            task_type="c2a_session_reimport",
            result_summary={
                "error_code": "c2a_timeout",
                "stage": "c2a_update",
                "outcome": "request_unknown",
            },
            task_status="attention_required",
        )
        self.assertEqual("external.c2a.transport", result["code"])
        self.assertTrue(result["reconcile_required"])
        self.assertEqual("unknown", result["remote_state_impact"])
        self.assertNotIn("封号", result["summary"])
        self.assertNotIn("鉴权", result["summary"])

    def test_prewrite_timeout_does_not_claim_remote_update_is_pending(self):
        result = classify_task_error(
            "请求超时",
            task_type="c2a_session_reimport",
            result_summary={
                "error_code": "c2a_timeout",
                "stage": "c2a_safety",
                "remote_update_started": False,
            },
            task_status="failed",
        )
        self.assertEqual("external.c2a.transport", result["code"])
        self.assertEqual("c2a_safety", result["stage"])
        self.assertIn("未更新远端账号", result["summary"])
        self.assertNotIn("待确认", result["summary"])

    def test_client_update_stage_keeps_unknown_remote_result(self):
        result = classify_task_error(
            "请求超时", task_type="c2a_session_reimport",
            result_summary={
                "error_code": "c2a_timeout", "stage": "update_account",
                "remote_update_started": True, "outcome": "request_unknown",
            },
            task_status="attention_required",
        )
        self.assertEqual("C2A 更新请求超时，未收到更新回执", result["summary"])
        self.assertTrue(result["reconcile_required"])
        self.assertNotIn("未更新远端账号", result["summary"])

    def test_create_rejected_has_specific_remote_rejection_category(self):
        result = classify_task_error(
            "远端拒绝新建", task_type="c2a_session_reimport",
            result_summary={
                "error_code": "c2a_create_rejected", "stage": "create_account",
                "action": "create", "remote_update_started": True,
            },
            task_status="failed",
        )
        self.assertEqual("external.c2a.remote_rejected", result["code"])
        self.assertEqual("C2A-REMOTE-003", result["display_code"])
        self.assertEqual("create_account", result["stage"])
        self.assertIn("拒绝新建", result["summary"])

    def test_create_unconfirmed_keeps_confirmation_category_and_unknown_result(self):
        result = classify_task_error(
            "未返回有效创建回执", task_type="c2a_session_reimport",
            result_summary={
                "error_code": "c2a_create_unconfirmed", "stage": "c2a_update",
                "action": "create", "remote_update_started": True,
                "outcome": "request_unknown",
            },
            task_status="attention_required",
        )
        self.assertEqual("external.c2a.confirmation", result["code"])
        self.assertEqual("C2A-CONFIRM-002", result["display_code"])
        self.assertIn("创建回执", result["summary"])
        self.assertTrue(result["reconcile_required"])
        self.assertEqual("unknown", result["remote_state_impact"])

    def test_create_timeout_describes_missing_receipt_without_claiming_no_write(self):
        for stage, action in (("c2a_update", "create"), ("create_account", "")):
            with self.subTest(stage=stage, action=action):
                result = classify_task_error(
                    "请求超时", task_type="c2a_session_reimport",
                    result_summary={
                        "error_code": "c2a_timeout", "stage": stage,
                        "action": action, "remote_update_started": True,
                        "outcome": "request_unknown",
                    },
                    task_status="attention_required",
                )
                self.assertEqual("external.c2a.transport", result["code"])
                self.assertEqual("C2A 新建请求超时，未收到导入回执", result["summary"])
                self.assertTrue(result["reconcile_required"])
                self.assertNotIn("未更新远端账号", result["summary"])

    def test_receipt_writeback_failure_covers_both_import_actions(self):
        for action in ("create", "update"):
            with self.subTest(action=action):
                result = classify_task_error(
                    "本地写回失败", task_type="c2a_session_reimport",
                    result_summary={
                        "error_code": "c2a_local_receipt_writeback_failed",
                        "stage": "local_writeback", "action": action,
                    },
                    task_status="failed",
                )
                self.assertEqual("external.c2a.local_writeback", result["code"])
                self.assertEqual("C2A 导入已确认，但本地回执写回失败", result["summary"])

    def test_arbitrary_remote_text_does_not_create_a_specific_c2a_cause(self):
        result = classify_task_error(
            "remote claimed auth failure",
            task_type="c2a_session_reimport",
            error_code="future_unverified",
            task_status="failed",
        )
        self.assertNotEqual("external.c2a.auth", result["code"])


if __name__ == "__main__":
    unittest.main()
