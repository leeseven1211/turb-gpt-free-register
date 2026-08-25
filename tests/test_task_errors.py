# -*- coding: utf-8 -*-
import unittest

from core.task_errors import classify_task_error


class TaskErrorClassificationTests(unittest.TestCase):
    def test_proxy_failure_is_external(self):
        info = classify_task_error("RuntimeError: 1024Proxy 获取失败：上游超时")
        self.assertEqual(info["code"], "external.proxy")
        self.assertEqual(info["source_label"], "外部错误")
        self.assertNotIn("RuntimeError:", info["summary"])

    def test_unexpected_page_is_workflow_error(self):
        info = classify_task_error("RuntimeError: 邮箱提交后未识别到密码或验证码分支")
        self.assertEqual(info["code"], "workflow.page_state")
        self.assertEqual(info["kind_label"], "页面状态不符合预期")

    def test_imap_otp_timeout_is_email_service_error(self):
        info = classify_task_error("Gmail IMAP 等待验证码超时；尚未收到新的 OpenAI 验证码邮件")
        self.assertEqual(info["code"], "external.email")

    def test_chatgpt_session_timeout_is_openai_error(self):
        info = classify_task_error("等待 /api/auth/session accessToken 超时")
        self.assertEqual(info["code"], "external.openai")

    def test_missing_api_key_is_configuration_error(self):
        info = classify_task_error("CloudMail API Key 为空，请填写配置")
        self.assertEqual(info["code"], "configuration.missing")

    def test_empty_error_has_no_projection(self):
        self.assertIsNone(classify_task_error(""))


if __name__ == "__main__":
    unittest.main()
