# -*- coding: utf-8 -*-
import unittest

from core.task_errors import classify_task_error


class TaskErrorClassificationTests(unittest.TestCase):
    def test_proxy_failure_is_external(self):
        info = classify_task_error("RuntimeError: 1024Proxy 获取失败：上游超时")
        self.assertEqual(info["code"], "external.proxy")
        self.assertEqual(info["error_code"], "external.proxy")
        self.assertEqual(info["stage"], "unknown")
        self.assertEqual(info["retryability"], "retryable")
        self.assertEqual(info["remote_state_impact"], "not_started_or_unknown")
        self.assertEqual(info["next_action"], "retry_with_new_proxy")
        self.assertEqual(info["source_label"], "外部错误")
        self.assertNotIn("RuntimeError:", info["summary"])

    def test_unexpected_page_is_workflow_error(self):
        info = classify_task_error("RuntimeError: 邮箱提交后未识别到密码或验证码分支")
        self.assertEqual(info["code"], "workflow.page_state")
        self.assertEqual(info["kind_label"], "页面状态不符合预期")

    def test_password_entry_failures_keep_distinct_recovery_categories(self):
        cases = {
            "password_entry_page_not_hydrated": (
                "workflow.password_entry_not_hydrated",
                "密码入口页面未加载",
            ),
            "password_entry_not_offered": (
                "workflow.password_entry_not_offered",
                "当前流程未提供密码入口",
            ),
            "password_entry_recovery_exhausted": (
                "workflow.password_entry_recovery_exhausted",
                "密码入口页面恢复已用尽",
            ),
        }
        for message, (code, label) in cases.items():
            with self.subTest(message=message):
                info = classify_task_error(
                    f"RuntimeError: 密码注册模式失败：{message}; https://auth.openai.com/email-verification",
                    stage="email_otp",
                )
                self.assertEqual(code, info["code"])
                self.assertEqual(label, info["kind_label"])
                self.assertEqual("retry_registration", info["next_action"])

    def test_imap_otp_timeout_is_email_service_error(self):
        info = classify_task_error("Gmail IMAP 等待验证码超时；尚未收到新的 OpenAI 验证码邮件")
        self.assertEqual(info["code"], "external.email")

    def test_chatgpt_session_timeout_is_openai_error(self):
        info = classify_task_error("等待 /api/auth/session accessToken 超时")
        self.assertEqual(info["code"], "external.openai")

    def test_password_submit_unknown_is_manual_reconcile(self):
        info = classify_task_error(
            "request_unknown: _PasswordTransitionTimeout: 密码提交后页面报告账号创建失败，远端结果待确认",
            stage="login_password",
        )
        self.assertEqual(info["code"], "request_unknown")
        self.assertEqual(info["retryability"], "manual_only")
        self.assertEqual(info["next_action"], "manual_reconcile")

    def test_known_registration_failures_do_not_fall_into_unknown(self):
        cases = {
            "Roxy API 返回失败 POST /browser/open: 窗口额度不足": "external.roxy_capacity",
            "Roxy API 返回失败 POST /browser/open: socket hang up": "external.roxy",
            "otp_request_unconfirmed: 验证码重发控件未能完成或缺少确认": "external.email",
            "WebUI 进程重启导致任务中断；浏览器和接码资源将在启动恢复阶段回收": "service.interrupted",
        }
        for message, code in cases.items():
            with self.subTest(message=message):
                info = classify_task_error(message, stage="email_otp")
                self.assertEqual(code, info["code"])
                self.assertNotEqual("unknown.unclassified", info["error_code"])

    def test_email_change_forbidden_is_actionable(self):
        info = classify_task_error(
            "/backend-api/accounts/change_email/begin 返回 403",
            task_type="email_change",
        )
        self.assertEqual(info["code"], "external.openai.email_change_forbidden")
        self.assertEqual(info["kind_label"], "邮箱换绑请求被拒绝")
        self.assertEqual(info["next_action"], "reauthenticate_before_retry")

    def test_email_change_failures_are_projected_with_safe_actionable_causes(self):
        cases = {
            "/backend-api/accounts/change_email/begin 返回 422 (email_domain_rejected)": (
                "external.openai.email_domain_rejected",
                "目标邮箱域名被拒绝",
                "change_email_domain",
                "OpenAI 拒绝该目标邮箱域名，请更换域名后再试",
            ),
            "/backend-api/accounts/change_email/begin 返回 400 (email_change_account_too_new)": (
                "external.openai.email_change_account_too_new",
                "账号注册时间不足",
                "wait_for_account_age",
                "账号注册时间不足，暂不允许换绑邮箱",
            ),
            "/backend-api/accounts/change_email/begin 返回 422": (
                "external.openai.email_change_rejected",
                "邮箱换绑请求被拒绝",
                "inspect_remote_rejection",
                "OpenAI 拒绝邮箱换绑请求（HTTP 422，未返回可识别细码）",
            ),
            "Recent Login 失败: AuthorizeRouteRejectedError": (
                "external.openai.email_change_recent_login",
                "Recent Login 认证失败",
                "reauthenticate_before_retry",
                "Recent Login 认证失败，尚未提交目标邮箱",
            ),
            "邮箱准备失败: Email Butler 领取失败（HTTP 409）": (
                "external.email.email_butler_prepare",
                "EmailButler 邮箱准备失败",
                "retry_email_prepare",
                "EmailButler 未能准备目标邮箱（HTTP 409）",
            ),
        }
        for message, (code, label, next_action, summary) in cases.items():
            with self.subTest(message=message):
                info = classify_task_error(message, task_type="email_change")
                self.assertEqual(info["code"], code)
                self.assertEqual(info["kind_label"], label)
                self.assertEqual(info["next_action"], next_action)
                self.assertEqual(info["summary"], summary)

    def test_email_change_projection_upgrades_coarse_persisted_error_code(self):
        info = classify_task_error(
            "/backend-api/accounts/change_email/begin 返回 422 (email_domain_rejected)",
            task_type="email_change",
            error_code="external.openai",
        )

        self.assertEqual(info["error_code"], "external.openai.email_domain_rejected")
        self.assertEqual(info["original_error_code"], "external.openai")

    def test_unsupported_payment_method_is_explicit_unsupported_error(self):
        info = classify_task_error("当前账号不支持 MoMo 支付方式")
        self.assertEqual(info["code"], "workflow.unsupported")
        self.assertEqual(info["kind_label"], "当前功能不支持")
        self.assertEqual(info["retryability"], "not_retryable")

    def test_missing_api_key_is_configuration_error(self):
        info = classify_task_error("CloudMail API Key 为空，请填写配置")
        self.assertEqual(info["code"], "configuration.missing")

    def test_empty_error_has_no_projection(self):
        self.assertIsNone(classify_task_error(""))

    def test_explicit_error_code_is_preserved_with_structured_metadata(self):
        info = classify_task_error(
            "OpenAI account was deactivated",
            stage="codex_result",
            error_code="account_deactivated",
        )
        self.assertEqual(info["error_code"], "account_deactivated")
        self.assertEqual(info["stage"], "codex")
        self.assertIn("retryability", info)

    def test_current_task_center_errors_have_short_codes_and_summaries(self):
        cases = (
            ("用户手动取消", "user.interrupted", "USR-001", "任务已取消", {}),
            ("AT已过期/失效，请手动查活刷新", "external.openai.credential_expired", "AUTH-001", "授权已失效，请刷新 AT", {}),
            (
                "远端写请求尚未完成整条任务核验，结果未知，已保留原记录，可重新执行：查活失败",
                "request_unknown", "REMOTE-001", "远端结果待核验", {"task_type": "token_refresh"},
            ),
            (
                "TokenRefreshReauthRequiredError: reauth_required: refresh_token_reused",
                "external.openai.auth_reauth_required", "AUTH-002", "授权已失效，请重新登录", {"task_type": "codex_token_refresh"},
            ),
            (
                "Email Butler 请求失败 (/signals/scan): HTTP 502; None",
                "external.email.service_unavailable", "MAIL-002", "邮箱服务暂时不可用", {"task_type": "deactivation_mail"},
            ),
            (
                "Email Butler 请求失败 (/signals/scan): HTTP 404; email account not found",
                "external.email.account_missing", "MAIL-003", "邮箱服务账号不存在", {"task_type": "deactivation_mail"},
            ),
            (
                "原注册邮箱不再处于保留状态（source=icloud_hide, status=available），不能改用其他邮箱重跑",
                "workflow.retry_blocked", "FLOW-RETRY-001", "原邮箱不可用，不能安全重试", {"task_type": "registration"},
            ),
            ("account_deactivated", "account.deactivated", "ACCT-001", "账号已停用", {"task_type": "token_refresh"}),
            (
                "registration_failed: HTTP Error 403:",
                "external.openai.registration_rejected", "OA-REG-403", "注册请求被拒绝（HTTP 403）", {"task_type": "registration"},
            ),
            (
                "auth_route_rejected: Auth authorize 路由被拒绝: HTTP 403",
                "external.openai.auth_route_rejected", "OA-AUTH-403", "授权路由被拒绝（HTTP 403）", {"task_type": "registration"},
            ),
            ("SyntaxError: invalid syntax (roxy.py, line 1)", "internal.code", "SYS-CODE-001", "本地代码错误", {}),
            (
                "registration_failed: RuntimeError: 资料页点击提交后 45 秒仍未离开",
                "workflow.page_state", "FLOW-PAGE-001", "页面未进入下一步", {"task_type": "registration"},
            ),
            ("邮箱换绑未完成", "external.openai.email_change_incomplete", "OA-EMAIL-001", "邮箱换绑未完成", {"task_type": "email_change"}),
            ("远端拒绝邮箱换绑请求", "external.openai.email_change_rejected", "OA-EMAIL-005", "邮箱换绑请求被拒绝", {"task_type": "email_change"}),
            ("邮箱换绑失败: UndefinedColumn", "internal.storage", "SYS-DB-001", "数据存储异常", {"task_type": "email_change"}),
            ("套餐查询待处理: 套餐查询已入队", "task.pending", "STATE-001", "套餐查询等待执行", {"task_type": "plan_check"}),
            ("任务在取得账号 lease 前收到取消请求", "user.interrupted", "USR-001", "任务已取消", {"task_type": "account_completion"}),
        )
        for message, code, display_code, summary, options in cases:
            with self.subTest(message=message):
                info = classify_task_error(message, **options)
                self.assertEqual(code, info["code"])
                self.assertEqual(display_code, info["display_code"])
                self.assertEqual(summary, info["summary"])

    def test_unknown_error_has_safe_short_fallback(self):
        info = classify_task_error("某个尚未建立映射的内部异常：opaque_failure_123")
        self.assertEqual("unknown.unclassified", info["code"])
        self.assertEqual("UNK-000", info["display_code"])
        self.assertEqual("未知错误", info["summary"])
        self.assertNotIn("opaque_failure_123", info["summary"])


if __name__ == "__main__":
    unittest.main()
