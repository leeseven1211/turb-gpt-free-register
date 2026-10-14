# -*- coding: utf-8 -*-
import unittest

from core.task_errors import classify_task_error


class TaskErrorClassificationTests(unittest.TestCase):
    def test_structured_cause_is_primary_error_even_when_remote_receipt_is_missing(self):
        info = classify_task_error(
            "远端结果待确认：查活失败",
            task_type="token_refresh",
            error_code="request_unknown",
            result_summary={
                "outcome": "request_unknown",
                "cause_code": "email_otp_failed",
                "auth_diagnostics": {"operation": "email_otp", "failure_kind": "no_mail"},
            },
        )
        self.assertEqual("email_otp_failed", info["code"])
        self.assertEqual("email_otp_failed", info["error_code"])
        self.assertEqual("MAIL-OTP-002", info["display_code"])
        self.assertEqual("未收到新的验证码邮件", info["summary"])
        self.assertEqual(info["display_code"], info["cause_display_code"])
        self.assertEqual(info["summary"], info["cause_summary"])
        self.assertTrue(info["reconcile_required"])
        self.assertEqual("manual_reconcile", info["next_action"])

    def test_remote_outcome_does_not_replace_known_raw_registration_rejection(self):
        info = classify_task_error(
            "request_unknown: registration_failed: HTTP Error 400: 远端结果待确认",
            task_type="registration",
            error_code="request_unknown",
            result_summary={"outcome": "request_unknown"},
        )
        self.assertEqual("external.openai.registration_rejected", info["code"])
        self.assertEqual(info["code"], info["error_code"])
        self.assertEqual("OA-REG-400", info["display_code"])
        self.assertEqual("注册请求被拒绝（HTTP 400）", info["summary"])
        self.assertEqual("manual_reconcile", info["next_action"])

    def test_sentinel_transport_diagnostics_identify_specific_primary_failure(self):
        cases = (
            (28, "Timeout", "password_sentinel_transport_timeout", "NET-SENTINEL-001", "密码认证前置检查请求超时"),
            (35, "RequestsError", "password_sentinel_transport_tls", "NET-SENTINEL-002", "密码认证前置检查 TLS 握手失败"),
            (56, "RequestsError", "password_sentinel_transport_connection", "NET-SENTINEL-003", "密码认证前置检查连接中断"),
            (60, "RequestsError", "password_sentinel_transport_certificate", "NET-SENTINEL-004", "密码认证前置检查 TLS 证书校验失败"),
        )
        for curl_code, exception_type, code, display_code, message in cases:
            with self.subTest(curl_code=curl_code):
                info = classify_task_error(
                    "密码认证前置检查失败", stage="login_password", error_code="request_unknown",
                    result_summary={
                        "outcome": "request_unknown", "cause_code": "password_sentinel_failed",
                        "auth_diagnostics": {
                            "operation": "password_sentinel", "failure_kind": "transport_error",
                            "curl_error_code": curl_code, "exception_type": exception_type,
                        },
                    },
                )
                self.assertEqual(code, info["code"])
                self.assertEqual(code, info["error_code"])
                self.assertEqual(display_code, info["display_code"])
                self.assertEqual(message, info["summary"])

    def test_sentinel_http_status_and_timeout_exception_are_safe_diagnostics(self):
        http = classify_task_error(
            "request_unknown", result_summary={
                "cause_code": "password_sentinel_failed",
                "cause_diagnostics": {"operation": "password_sentinel", "http_status": 403},
            },
        )
        self.assertEqual("password_sentinel_http_rejected", http["code"])
        self.assertEqual("OA-SENTINEL-403", http["display_code"])
        self.assertEqual("密码认证前置检查被拒绝（HTTP 403）", http["summary"])
        timeout = classify_task_error(
            "", result_summary={
                "cause_code": "password_sentinel_failed",
                "auth_diagnostics": {"operation": "password_sentinel", "exception_type": "ReadTimeout"},
            },
        )
        self.assertIsNotNone(timeout)
        self.assertEqual("password_sentinel_transport_timeout", timeout["code"])

    def test_submitted_auth_transport_errors_display_the_underlying_network_failure(self):
        cases = (
            ("password_verify", "password_result_unknown", 35, "password_verify_transport_tls", "NET-PWD-002", "密码验证 TLS 握手失败"),
            ("password_verify", "password_result_unknown", 28, "password_verify_transport_timeout", "NET-PWD-001", "密码验证请求超时"),
            ("mfa_verify", "protocol_network_error", 56, "mfa_verify_transport_connection", "NET-MFA-003", "MFA 验证连接中断"),
        )
        for operation, cause_code, curl_code, code, display_code, message in cases:
            with self.subTest(operation=operation, curl_code=curl_code):
                info = classify_task_error(
                    "远端结果待确认", task_type="token_refresh", error_code="request_unknown",
                    result_summary={
                        "outcome": "request_unknown", "cause_code": cause_code,
                        "action_dispatched": True, "mutation_submitted": True,
                        "auth_diagnostics": {
                            "operation": operation, "failure_kind": "transport_error",
                            "curl_error_code": curl_code, "exception_type": "RequestsError",
                        },
                    },
                )
                self.assertEqual(code, info["code"])
                self.assertEqual(code, info["error_code"])
                self.assertEqual(display_code, info["display_code"])
                self.assertEqual(message, info["summary"])
                self.assertTrue(info["reconcile_required"])
                self.assertEqual("manual_reconcile", info["next_action"])

    def test_mfa_http_failure_displays_response_status_above_coarse_protocol_error(self):
        info = classify_task_error(
            "远端结果待确认", error_code="request_unknown", result_summary={
                "outcome": "request_unknown", "cause_code": "protocol_network_error",
                "auth_diagnostics": {"operation": "mfa_verify", "failure_kind": "http_error", "http_status": 503},
            },
        )
        self.assertEqual("mfa_verify_http_error", info["code"])
        self.assertEqual("OA-MFA-503", info["display_code"])
        self.assertEqual("MFA 验证请求返回 HTTP 503", info["summary"])
        self.assertEqual("manual_reconcile", info["next_action"])

    def test_different_diagnostic_sources_do_not_mix_operations_and_transport_details(self):
        info = classify_task_error(
            "远端结果待确认", result_summary={
                "outcome": "request_unknown", "cause_code": "protocol_network_error",
                "auth_diagnostics": {"operation": "mfa_verify", "failure_kind": "transport_error"},
                "cause_diagnostics": {"operation": "password_sentinel", "curl_error_code": 35},
            },
        )
        self.assertEqual("mfa_verify_transport_error", info["code"])
        self.assertEqual("MFA 验证网络请求失败", info["summary"])

    def test_coarse_driver_causes_do_not_hide_specific_raw_failure(self):
        for cause_code, raw, code, display_code in (
            ("refresh_driver_exception", "DuplicateProxyError: 代理分配重复", "external.proxy", "PROXY-001"),
            ("protocol_v2_unknown_error", "ConnectionResetError: connection reset", "external.network", "NET-001"),
            ("post_register_failure", "UndefinedColumn: 数据库列不存在", "internal.storage", "SYS-DB-001"),
        ):
            with self.subTest(cause_code=cause_code):
                info = classify_task_error(raw, result_summary={"outcome": "request_unknown", "cause_code": cause_code})
                self.assertEqual(code, info["code"])
                self.assertEqual(display_code, info["display_code"])
                self.assertEqual("manual_reconcile", info["next_action"])

    def test_unknown_historical_receipt_uses_known_task_or_stage_without_inventing_cause(self):
        stage = classify_task_error(
            "远端结果待确认", stage="login_password", task_type="token_refresh", error_code="request_unknown",
        )
        self.assertEqual("login_password_receipt_missing", stage["code"])
        self.assertEqual("AUTH-PWD-RECEIPT", stage["display_code"])
        self.assertEqual("密码验证阶段未保留回执或失败细项", stage["summary"])
        task = classify_task_error(
            "远端结果待确认", task_type="email_change", error_code="request_unknown",
        )
        self.assertEqual("email_change_receipt_missing", task["code"])
        self.assertEqual("邮箱换绑任务未保留回执或失败细项", task["summary"])

    def test_unknown_untrusted_cause_never_becomes_display_text(self):
        info = classify_task_error(
            "远端结果待确认", task_type="registration", result_summary={
                "outcome": "request_unknown", "cause_code": "secret@example.test",
                "auth_diagnostics": {"operation": "password_sentinel", "exception_type": "secret@example.test"},
            },
        )
        self.assertEqual("registration_receipt_missing", info["code"])
        self.assertNotIn("secret@example.test", str(info))

    def test_generic_receipt_message_does_not_invent_a_failure_from_stage_name(self):
        for stage, code, message in (
            ("codex", "codex_receipt_missing", "Codex 授权阶段未保留回执或失败细项"),
            ("twofa", "twofa_receipt_missing", "Authenticator 2FA阶段未保留回执或失败细项"),
        ):
            with self.subTest(stage=stage):
                info = classify_task_error("远端结果待确认", stage=stage, error_code="request_unknown")
                self.assertEqual(code, info["code"])
                self.assertEqual(message, info["summary"])

    def test_historical_safe_cause_code_is_primary_without_structured_summary(self):
        info = classify_task_error("request_unknown: password_sentinel_failed", stage="login_password")
        self.assertEqual("password_sentinel_failed", info["code"])
        self.assertEqual("AUTH-PWD-005", info["display_code"])
        self.assertEqual("密码认证前置检查失败", info["summary"])
        self.assertEqual("manual_reconcile", info["next_action"])

    def test_refresh_failure_causes_keep_concrete_primary_errors(self):
        cases = (
            ("refresh_result_invalid", "SYS-REFRESH-RESULT", "AT 刷新驱动返回结果无效"),
            ("refresh_cancelled", "USR-REFRESH-001", "AT 刷新已取消"),
            ("refresh_local_commit_failed", "SYS-REFRESH-WRITEBACK", "AT 刷新本地写回或读回未完成"),
            ("account_setup_local_commit_failed", "SYS-SETUP-WRITEBACK", "账号配置本地写回或读回未完成"),
            ("remote_response_missing", "REQ-RESPONSE-001", "远端响应缺失"),
        )
        for code, display_code, message in cases:
            with self.subTest(code=code):
                info = classify_task_error(
                    "远端结果待确认", task_type="token_refresh", error_code="request_unknown",
                    result_summary={"outcome": "request_unknown", "cause_code": code},
                )
                self.assertEqual(code, info["code"])
                self.assertEqual(code, info["error_code"])
                self.assertEqual(display_code, info["display_code"])
                self.assertEqual(message, info["summary"])
                self.assertEqual("manual_reconcile", info["next_action"])

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
        self.assertEqual(info["code"], "external.network")
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

    def test_email_change_local_email_conflicts_are_known_and_not_submitted(self):
        cases = {
            "目标邮箱已被本地账号占用，已停止换绑": (
                "account.email_already_used",
                "ACCT-003",
                "目标邮箱已被使用",
                "目标邮箱已被本地账号使用，换绑尚未提交；请更换邮箱后重试",
            ),
            "领取到的邮箱与当前邮箱相同，已停止换绑": (
                "account.email_matches_current",
                "ACCT-004",
                "目标邮箱与当前邮箱相同",
                "领取到的邮箱与当前邮箱相同，换绑尚未提交；请重新领取邮箱后重试",
            ),
        }
        for message, (code, display_code, label, summary) in cases.items():
            with self.subTest(message=message):
                info = classify_task_error(
                    message,
                    task_type="email_change",
                    stage="email",
                    error_code="unknown.unclassified",
                )
                self.assertEqual(code, info["code"])
                self.assertEqual(code, info["error_code"])
                self.assertEqual(display_code, info["display_code"])
                self.assertEqual(label, info["kind_label"])
                self.assertEqual(summary, info["summary"])
                self.assertEqual("retryable", info["retryability"])
                self.assertEqual("not_started", info["remote_state_impact"])

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
                "token_refresh_receipt_missing", "AUTH-REFRESH-RECEIPT", "AT 刷新任务未保留回执或失败细项", {"task_type": "token_refresh"},
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

    def test_old_account_task_known_errors_no_longer_show_unknown(self):
        cases = (
            ("WebUI 重启导致任务中断，请重新执行", "token_refresh", "SYS-002"),
            ("账号已删除或提链状态已被重置", "extract_link", "ACCT-002"),
            ("HTTP 403", "plan_check", "OA-PLAN-403"),
            ("Cloudflare 邮箱凭据缺失：请配置只读接口", "deactivation_mail", "CFG-001"),
            ("账号配置重试未返回结果", "account_setup_retry", "SYS-CODE-001"),
            ("StaleElementReferenceException: stale element reference", "password_setup", "SYS-BROWSER-001"),
            ("InvalidSessionIdException: browser session closed", "account_setup_retry", "SYS-BROWSER-001"),
            ("JavascriptException: script execution failed", "account_completion", "SYS-BROWSER-001"),
            ("账号设置中未找到“Add password/设置密码”入口", "password_setup", "FLOW-PWD-004"),
        )
        for message, task_type, display_code in cases:
            with self.subTest(message=message):
                info = classify_task_error(message, task_type=task_type)
                self.assertEqual(display_code, info["display_code"])
                self.assertNotEqual("unknown.unclassified", info["code"])
        self.assertEqual(
            "unknown.unclassified",
            classify_task_error("HTTP 403", task_type="password_setup")["code"],
        )

    def test_extract_create_explicit_rejection_uses_exact_safe_message(self):
        for message in (
            "提链创建请求被远端拒绝（HTTP 403）",
            "ExtractCreateRejected: 提链创建请求被远端拒绝（HTTP 403）",
        ):
            with self.subTest(message=message):
                info = classify_task_error(message, task_type="extract_link")
                self.assertEqual("external.extract_link.rejected", info["code"])
                self.assertEqual("LINK-HTTP-403", info["display_code"])
                self.assertEqual("提链创建请求被远端拒绝（HTTP 403）", info["summary"])
        self.assertEqual(
            "unknown.unclassified",
            classify_task_error("提链创建请求 HTTP 403", task_type="extract_link")["code"],
        )

    def test_email_change_begin_local_prepare_has_specific_code(self):
        info = classify_task_error(
            "邮箱换绑失败: begin 请求本地准备失败", task_type="email_change",
        )
        self.assertEqual("internal.request_prepare", info["code"])
        self.assertEqual("SYS-REQ-001", info["display_code"])
        self.assertEqual("邮箱换绑 begin 请求在本地准备阶段失败", info["summary"])
        self.assertNotEqual(
            "internal.request_prepare",
            classify_task_error("邮箱换绑失败: verify 请求本地准备失败", task_type="email_change")["code"],
        )

    def test_missing_remote_receipt_keeps_recovery_action_and_primary_cause(self):
        info = classify_task_error(
            "远端结果待确认：查活失败",
            task_type="token_refresh",
            error_code="request_unknown",
            task_status="attention_required",
            result_summary={
                "outcome": "request_unknown",
                "cause_code": "email_otp_failed",
                "auth_diagnostics": {"operation": "email_otp", "failure_kind": "no_mail"},
            },
        )
        self.assertEqual("email_otp_failed", info["code"])
        self.assertEqual("MAIL-OTP-002", info["display_code"])
        self.assertEqual("MAIL-OTP-002", info["cause_display_code"])
        self.assertEqual("未收到新的验证码邮件", info["cause_summary"])

    def test_request_unknown_uses_safe_historical_evidence_without_guessing(self):
        timeout = classify_task_error(
            "远端结果待确认：查活失败",
            error_code="request_unknown",
            result_summary={
                "outcome": "request_unknown",
                "auth_diagnostics": {
                    "operation": "mfa_verify", "failure_kind": "transport_error",
                    "exception_type": "Timeout",
                },
            },
        )
        self.assertEqual("NET-MFA-001", timeout["cause_display_code"])
        self.assertEqual("MFA 验证请求超时", timeout["cause_summary"])
        email_stage = classify_task_error(
            "远端结果待确认：查活失败",
            task_type="token_refresh",
            error_code="request_unknown",
            result_summary={
                "outcome": "request_unknown", "error_category": "email",
                "auth_method": "email_otp",
            },
        )
        self.assertEqual("MAIL-RECEIPT", email_stage["cause_display_code"])
        self.assertIn("未保留回执或失败细项", email_stage["cause_summary"])
        other_email_stage = classify_task_error(
            "邮箱换绑结果待核验",
            task_type="email_change",
            error_code="request_unknown",
            result_summary={"outcome": "request_unknown", "error_category": "email"},
        )
        self.assertEqual("MAIL-RECEIPT", other_email_stage["cause_display_code"])
        self.assertEqual("邮箱验证阶段未保留回执或失败细项", other_email_stage["cause_summary"])
        missing = classify_task_error(
            "邮箱换绑结果待核验",
            error_code="request_unknown",
            result_summary={"outcome": "request_unknown"},
        )
        self.assertEqual("TASK-RECEIPT-000", missing["cause_display_code"])
        self.assertEqual("任务未保留回执或失败细项", missing["cause_summary"])

    def test_codex_consent_cause_keeps_remote_reconciliation_fence(self):
        info = classify_task_error(
            "Codex 授权确认页无法继续，需浏览器驱动",
            task_type="codex_retry", task_status="attention_required",
            result_summary={
                "outcome": "request_unknown", "reconcile_required": True,
                "cause_code": "codex_consent_unverifiable", "error_category": "auth",
            },
        )

        self.assertEqual("codex_consent_unverifiable", info["error_code"])
        self.assertEqual("OA-CODEX-CONSENT-001", info["display_code"])
        self.assertEqual("manual_only", info["retryability"])
        self.assertEqual("manual_reconcile", info["next_action"])
        self.assertEqual("codex_consent_unverifiable", info["cause_code"])
        self.assertEqual("OA-CODEX-CONSENT-001", info["cause_display_code"])
        self.assertEqual("Codex 授权确认页无法继续，需浏览器驱动", info["cause_summary"])

    def test_remote_receipt_status_does_not_hide_registration_http_status(self):
        info = classify_task_error(
            "registration_failed: HTTP Error 400: 远端结果待确认",
            task_type="registration",
            error_code="request_unknown",
            task_status="request_unknown",
        )
        self.assertEqual("external.openai.registration_rejected", info["code"])
        self.assertEqual("OA-REG-400", info["display_code"])
        self.assertEqual("manual_reconcile", info["next_action"])
        from_summary = classify_task_error(
            "registration_failed: HTTP Error 400",
            task_type="registration",
            error_code="external.openai.registration_rejected",
            result_summary={"outcome": "request_unknown"},
        )
        self.assertEqual("OA-REG-400", from_summary["display_code"])
        self.assertEqual("external.openai.registration_rejected", from_summary["error_code"])
        self.assertEqual("external.openai.registration_rejected", from_summary["original_error_code"])

    def test_extract_link_unknown_keeps_outcome_and_shows_safe_response_failure(self):
        cases = (
            ("extract_create_invalid_json", "OA-EXTRACT-001", "提链创建响应无法解析"),
            ("extract_create_missing_job_id", "OA-EXTRACT-002", "提链创建响应缺少任务 ID"),
            ("extract_create_transport_error", "NET-EXTRACT-001", "提链创建网络请求中断"),
        )
        for cause_code, display_code, cause_summary in cases:
            with self.subTest(cause_code=cause_code):
                info = classify_task_error(
                    "提链结果待核验", task_type="extract_link", error_code="request_unknown",
                    result_summary={"outcome": "request_unknown", "cause_code": cause_code},
                )
                self.assertEqual(cause_code, info["error_code"])
                self.assertEqual(display_code, info["display_code"])
                self.assertEqual(display_code, info["cause_display_code"])
                self.assertEqual(cause_summary, info["cause_summary"])
        http = classify_task_error(
            "提链结果待核验", task_type="extract_link", error_code="request_unknown",
            result_summary={
                "outcome": "request_unknown", "cause_code": "extract_create_http_unknown",
                "cause_diagnostics": {"http_status": 400},
            },
        )
        self.assertEqual("OA-EXTRACT-HTTP", http["cause_display_code"])
        self.assertEqual("提链创建请求返回 HTTP 400", http["cause_summary"])

    def test_email_change_verify_prepare_failure_keeps_begin_reconciliation(self):
        info = classify_task_error(
            "邮箱换绑结果待核验", task_type="email_change", error_code="request_unknown",
            result_summary={
                "outcome": "request_unknown",
                "cause_code": "email_change_verify_prepare_failed",
                "remote_begin_accepted": True,
            },
        )
        self.assertEqual("email_change_verify_prepare_failed", info["error_code"])
        self.assertEqual("OA-EMAIL-VERIFY-001", info["display_code"])
        self.assertEqual("OA-EMAIL-VERIFY-001", info["cause_display_code"])
        self.assertEqual(
            "新邮箱验证请求在本地准备阶段失败；begin 已接受，待核验",
            info["cause_summary"],
        )

    def test_registration_unknown_shows_only_confirmed_stage_cause(self):
        causes = {
            "user_register_result_unknown": "账号创建请求结果未确认",
            "registration_checkpoint_failed": "注册检查点本地写入失败",
            "user_register_continue_url_missing": "账号创建响应缺少后续验证地址",
            "email_otp_send_rejected": "验证码发送请求被拒绝",
            "email_otp_send_failed": "验证码发送请求失败",
            "email_otp_send_unconfirmed": "验证码发送结果未获确认",
            "email_otp_send_no_response": "验证码发送请求未收到响应",
            "email_otp_send_unknown": "验证码发送结果未确认",
            "email_otp_no_mail": "等待窗口内未收到验证码邮件",
            "post_register_failure": "注册请求之后流程失败（细项未记录）",
        }
        for cause_code, cause_summary in causes.items():
            with self.subTest(cause_code=cause_code):
                info = classify_task_error(
                    "远端结果待确认", task_type="registration",
                    result_summary={"outcome": "request_unknown", "cause_code": cause_code},
                )
                self.assertEqual(cause_code, info["code"])
                self.assertEqual(cause_code, info["error_code"])
                self.assertNotEqual("REMOTE-001", info["display_code"])
                self.assertEqual(cause_summary, info["summary"])
                self.assertEqual(cause_summary, info["cause_summary"])
        generic = classify_task_error(
            "远端结果待确认", task_type="registration",
            result_summary={"outcome": "request_unknown", "cause_code": "registration_failed"},
        )
        self.assertEqual("registration_receipt_missing", generic["code"])
        self.assertEqual("注册任务未保留回执或失败细项", generic["summary"])


if __name__ == "__main__":
    unittest.main()
