from __future__ import annotations

from unittest import TestCase

from core.extract_link_service import _workbench_task_item


class ExtractWorkbenchErrorDetailsTests(TestCase):
    def item(self, *, step="提链 CDK 次数已用完，任务未执行", error="平台提链失败：任务处理失败",
             message="平台提链失败：任务处理失败", provider="huanguang", extraction="failed",
             failure_message="任务处理失败"):
        return _workbench_task_item({
            "task_id": 257151, "run_id": 257146, "run_count": 2, "run_status": "failed",
            "task_data": {"provider_id": provider, "mode": "auto_payment"},
            "error_message": error,
            "public_state": {
                "extraction_state": extraction, "payment_state": "not_started", "message": message,
                "summary": {"current_step": step, "failure_message": failure_message, "percent": 100},
            },
        })

    def test_existing_failed_card_exposes_saved_cdk_reason_without_changing_facts(self):
        item = self.item()
        self.assertEqual("平台提链失败：提链 CDK 次数已用完，任务未执行", item["message"])
        self.assertEqual(item["message"], item["error"])
        self.assertEqual((257146, 2, "failed", "failed", "unpaid"), (
            item["run_id"], item["run_count"], item["task_status"], item["extraction_status"], item["payment_status"],
        ))
        self.assertFalse(item["has_payment_entry"])

    def test_saved_failure_stage_and_network_reason_are_visible(self):
        reason = "失败阶段：Sentinel 校验｜原因：网络或上游校验异常"
        item = self.item(step=reason)
        self.assertIn(reason, item["error"])

    def test_explicit_error_is_not_replaced_by_another_progress_reason(self):
        message = "平台提链失败：支付权限被拒绝"
        item = self.item(error=message, message=message)
        self.assertEqual(message, item["error"])
        self.assertEqual(message, item["message"])

    def test_generic_error_does_not_hide_specific_saved_message(self):
        message = "平台提链失败：入口代理认证失败"
        item = self.item(message=message)
        self.assertEqual(message, item["error"])
        self.assertEqual(message, item["message"])

    def test_specific_summary_failure_precedes_progress(self):
        item = self.item(failure_message="入口代理认证失败")
        self.assertIn("入口代理认证失败", item["error"])
        self.assertNotIn("CDK", item["error"])

    def test_running_progress_does_not_become_failure_cause(self):
        for step in ("正在生成支付链接", "等待网络超时后重试", "排队中", "准备失败重试", ""):
            with self.subTest(step=step):
                item = self.item(step=step)
                self.assertEqual("平台提链失败：任务处理失败", item["error"])

    def test_other_provider_or_non_failed_extraction_keeps_original_message(self):
        for values in ({"provider": "lumen_flow"}, {"extraction": "succeeded"}, {"extraction": "unknown"}):
            with self.subTest(values=values):
                self.assertEqual("平台提链失败：任务处理失败", self.item(**values)["error"])

    def test_generic_error_only_record_can_use_saved_terminal_reason(self):
        item = self.item(message="")
        self.assertIn("提链 CDK 次数已用完，任务未执行", item["error"])

    def test_fallback_detail_remains_redacted(self):
        item = self.item(step="代理失败 https://user:private-pass@example.test/path?token=secret-value 联系 person@example.test")
        self.assertIn("代理失败", item["error"])
        for value in ("private-pass", "example.test", "secret-value", "person@"):
            self.assertNotIn(value, item["error"])
