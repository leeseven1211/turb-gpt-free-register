# -*- coding: utf-8 -*-
import unittest

from core.task_errors import classify_task_error


class TaskErrorClassificationTests(unittest.TestCase):
    def test_local_butler_inventory_empty_is_not_unclassified(self):
        info = classify_task_error(
            "RuntimeError: 所选邮箱来源 email_butler 领取失败: local_email_inventory_empty: 本地 Butler 邮箱库存为空，请先手动导入",
            task_type="registration", stage="email", error_code="unknown.unclassified",
        )
        self.assertEqual("local_email_inventory_empty", info["code"])
        self.assertEqual("本地 Butler 邮箱库存为空", info["summary"])
        self.assertEqual("internal", info["source"])

    def test_extract_original_order_reconciliation_uses_specific_evidence(self):
        for reason, message, expected_code, expected_summary in (
            ("remote_not_found", "原单连续查询返回 HTTP 404，已停止自动续查，待核验", "extract_order_not_found", "提链原单查询连续返回 HTTP 404"),
            ("timeout", "原单自动续查已超过总时限，已停止自动续查，待核验", "extract_order_polling_timeout", "提链原单自动续查达到总时限"),
            ("query_failures", "原单连续查询失败达到上限，已停止自动续查，待核验", "extract_order_query_failures", "提链原单连续查询失败达到上限"),
            ("no_progress", "原单长时间没有有效进展，已停止自动续查，待核验", "extract_order_no_progress", "提链原单长时间没有有效进展"),
        ):
            with self.subTest(reason=reason):
                info = classify_task_error(
                    message, task_type="extract_link", stage="access_token",
                    error_code="access_token_receipt_missing", task_status="attention_required",
                    result_summary={"cause_code": "extract_reconcile_halted", "local_reconcile_reason": reason,
                                    "outcome": "request_unknown", "reconcile_required": True},
                )
                self.assertEqual(expected_code, info["code"])
                self.assertEqual(expected_summary, info["summary"])
                self.assertEqual("remote_sync", info["stage"])
                self.assertTrue(info["reconcile_required"])

        from core.task_stages import stage_label
        self.assertEqual("原单状态查询", stage_label("remote_sync"))

    def test_extract_provider_failure_surfaces_specific_recorded_cause(self):
        for raw, expected_code, expected_summary in (
            ("平台提链失败：失败阶段：Checkout approval｜上游 result=blocked", "extract_checkout_blocked", "Checkout approval 被阻断，原因未记录"),
            ("平台提链失败：失败阶段：零元优惠校验｜原因：今日应付金额不是 0", "extract_nonzero_amount", "零元优惠校验失败：今日应付金额不是 0"),
            ("平台提链失败：失败阶段：OpenAI Checkout 创建｜上游详情：OpenAI Checkout HTTP 400: Billing country must match request country.", "extract_country_mismatch", "OpenAI Checkout 账单国家与请求国家不一致（HTTP 400）"),
            ("平台提链失败：失败阶段：UPI 支付确认｜原因：支付提供商拒绝", "extract_upi_rejected", "UPI 支付确认被支付提供商拒绝"),
            ("平台提链失败：OpenAI Checkout HTTP 401: token_revoked", "extract_checkout_token_revoked", "OpenAI Checkout OAuth Token 已撤销（HTTP 401）"),
            ("平台提链失败：blocked：支付确认被拦截", "extract_payment_blocked", "支付确认被拦截，原因未记录"),
            ("平台提链失败：优惠未生效", "extract_promotion_not_applied", "优惠未生效，具体原因未记录"),
            ("平台提链失败：任务处理失败", "extract_provider_task_failed", "提链平台任务处理失败，具体原因未记录"),
            ("平台提链失败：支付提交失败，请稍后重试。", "extract_payment_submit_failed", "提链平台报告支付提交失败，具体原因未记录"),
            ("平台提链失败：失败阶段：Sentinel 校验｜原因：网络或上游校验异常", "extract_sentinel_failed", "Sentinel 校验发生网络或上游异常，具体原因未记录"),
            ("平台提链失败：网络连接失败，请稍后重试。", "extract_connection_failed", "提链平台报告网络连接失败"),
            ("平台提链失败：支付授权或审批被阻止", "extract_payment_approval_blocked", "支付授权或审批被阻止，具体原因未记录"),
            ("平台提链失败：checkout create failed: HTTP 400: Our systems have detected unusual activity", "extract_checkout_unusual_activity", "Checkout HTTP 400：上游提示异常活动"),
            ("平台提链失败：支付方式设置流程失败", "extract_payment_method_failed", "支付方式设置流程失败，具体原因未记录"),
            ("平台提链失败：上游结账风控拦截", "extract_checkout_risk_blocked", "平台报告上游结账被风控拦截"),
            ("平台已明确拒绝提链请求：CDK is invalid or unavailable", "extract_cdk_invalid", "提链平台报告 CDK 无效或不可用"),
            ("平台提链失败：token_revoked：access_token 已失效，请更换 token。", "extract_token_revoked", "提链平台报告 access_token 已失效（token_revoked）"),
            ("平台提链失败：请求超时，请稍后重试。", "extract_request_timeout", "提链阶段请求超时，具体位置未记录"),
            ("平台提链失败：Failed to perform, curl: (28) Operation timed out", "extract_request_timeout", "提链阶段请求超时，具体位置未记录"),
            ("平台提链失败：Failed to perform, curl: (35) TLS connect error", "extract_tls_error", "提链阶段 TLS 连接失败"),
            ("平台提链失败：Failed to perform, curl: (60) SSL certificate problem", "extract_certificate_error", "提链阶段 TLS 证书校验失败"),
            ("平台提链失败：任务处理失败：curl: (60) SSL certificate problem", "extract_certificate_error", "提链阶段 TLS 证书校验失败"),
            ("平台提链失败：Stripe confirm 后审批/结果查询阶段失败", "extract_approval_query_failed", "Stripe 确认后的审批或结果查询失败"),
        ):
            with self.subTest(raw=raw):
                info = classify_task_error(
                    raw, task_type="extract_link", stage="extraction", error_code="extract_provider_failed",
                    result_summary={"cause_code": "extract_provider_failed"},
                )
                self.assertEqual(expected_code, info["code"])
                self.assertEqual(expected_summary, info["summary"])
                self.assertEqual("extraction", info["stage"])

    def test_plan_country_failure_reports_stage_without_inventing_cause(self):
        info = classify_task_error(
            "全部国家查询失败：JP、VN、IN", task_type="plan_check", stage="plan_check",
            error_code="unknown.unclassified",
        )
        self.assertEqual("plan_country_queries_failed", info["code"])
        self.assertEqual("套餐国家查询均失败，具体原因未记录", info["summary"])
        self.assertEqual("plan_check", info["stage"])

    def test_extract_categories_do_not_infer_cause_from_generic_http(self):
        for raw in ("平台提链失败：HTTP 401", "平台提链失败：HTTP 400", "平台提链失败：原因未知"):
            with self.subTest(raw=raw):
                info = classify_task_error(raw, task_type="extract_link", stage="extraction",
                                           error_code="extract_provider_failed")
                self.assertEqual("extract_provider_failed", info["code"])

    def test_butler_cutover_and_report_failures_are_classified(self):
        for code in ("email_cutover_target_invalid", "email_cutover_route_changed", "icloud_result_conflict", "icloud_identity_not_found"):
            with self.subTest(code=code):
                info = classify_task_error(f"Butler 操作失败: {code}")
                self.assertEqual(info["code"], code)
                self.assertNotEqual(info["display_code"], "UNK-000")

    def test_butler_recipient_failures_have_specific_causes_for_raw_and_structured_errors(self):
        codes = ("recipient_contract_unsupported", "recipient_evidence_missing", "recipient_ambiguous",
                 "recipient_mismatch", "mailbox_mismatch", "inbound_code_timeout")
        for code in codes:
            for raw, structured in [(f"Email Butler 严格收件取码失败: {code}: 取码失败", ""), ("收件失败", code)]:
                with self.subTest(code=code, structured=bool(structured)):
                    info = classify_task_error(raw, task_type="registration", error_code=structured)
                    self.assertEqual(info["code"], code)
                    self.assertTrue(info["display_code"].startswith("MAIL-RECIPIENT-"))
                    self.assertNotEqual(info["retryability"], "not_retryable")

    def test_butler_source_failures_are_classified_and_allow_conditional_retry(self):
        for code in ("source_untrusted", "source_authentication_failed"):
            for raw, structured in [(f"Email Butler 入站取码失败: {code}", ""), ("来源核验失败", code)]:
                with self.subTest(code=code, structured=bool(structured)):
                    info = classify_task_error(raw, task_type="registration", error_code=structured)
                    self.assertEqual(info["code"], code)
                    self.assertTrue(info["display_code"].startswith("MAIL-"))
                    self.assertEqual(info["retryability"], "conditional")

    def test_unsupported_mailbox_scan_connector_has_specific_retryable_cause(self):
        info = classify_task_error("原收件配置不支持扫描", task_type="deactivation_mail",
            error_code="email_scan_connector_unsupported")
        self.assertEqual(info["code"], "email_scan_connector_unsupported")
        self.assertEqual(info["display_code"], "MAIL-SCAN-001")
        self.assertEqual(info["retryability"], "conditional")

    def test_subaddress_inventory_shortage_is_specific_and_retryable(self):
        for task_type in ('registration', 'email_change'):
            info = classify_task_error(
                '所选邮箱领取失败: email_derivation_inventory_empty: 子地址库存不足，请先生成子邮箱',
                task_type=task_type, error_code='unknown.unclassified')
            self.assertEqual(info['code'], 'email_derivation_inventory_empty')
            self.assertEqual(info['display_code'], 'MAIL-STOCK-001')
            self.assertEqual(info['retryability'], 'retryable')
            self.assertEqual(info['next_action'], 'generate_email_inventory')

    def test_subaddress_structured_causes_are_all_classified(self):
        for code in ('email_derivation_inventory_empty', 'email_derivation_identity_conflict',
                     'email_derivation_source_unsupported', 'email_derivation_profile_unavailable',
                     'email_derivation_capacity_exhausted', 'email_derivation_request_conflict',
                     'email_derivation_source_disabled', 'email_derivation_parent_unavailable',
                     'email_derivation_address_invalid', 'email_derivation_address_collision'):
            with self.subTest(code=code):
                info = classify_task_error('子地址操作失败', error_code=code)
                self.assertEqual(info['code'], code)
                self.assertNotEqual(info['display_code'], 'UNK-000')

    def test_short_lived_mailbox_errors_do_not_offer_verification_resume(self):
        for code in ('email_resource_expired', 'email_resource_expiry_invalid', 'email_resource_read_failed'):
            with self.subTest(code=code):
                info = classify_task_error('邮箱读取失败', stage='email_verification',
                                           task_type='registration', error_code=code)
                self.assertEqual(info['code'], code)
                self.assertTrue(info['display_code'].startswith('MAIL-RESOURCE-'))
                self.assertNotEqual(info['next_action'], 'resume_email_verification')

    def test_existing_account_without_session_keeps_specific_cause_and_unknown_outcome(self):
        info = classify_task_error(
            "request_unknown: 既存账号完整登录态尚未确认",
            task_type="registration_resume", error_code="request_unknown",
            result_summary={"outcome": "request_unknown", "cause_code": "account_create_user_already_exists"},
        )
        self.assertEqual("account_create_user_already_exists", info["error_code"])
        self.assertEqual("OA-REG-EXISTS-001", info["display_code"])
        self.assertEqual("远端提示账号已存在，完整登录态尚未确认", info["summary"])
        self.assertTrue(info["reconcile_required"])

    def test_existing_account_cause_survives_registration_fact_allowlist(self):
        from core.registration_service import _registration_request_unknown_facts

        facts = _registration_request_unknown_facts({
            "cause_code": "account_create_user_already_exists", "register_response_confirmed": True,
            "response_body": "必须丢弃的私有正文",
        })
        self.assertEqual({"outcome": "request_unknown", "cause_code": "account_create_user_already_exists",
                          "register_response_confirmed": True}, facts)

    def test_remail_inventory_shortage_is_displayed_before_coarse_http_failure(self):
        for task_type, message in (
            ("registration", "RuntimeError: 所选邮箱来源 remail 领取失败: Remail 库存不足 (HTTP 422)"),
            ("registration", "registration_failed: RuntimeError: Remail 库存不足 (HTTP 422)"),
            ("email_change", "邮箱换绑失败: Remail 库存不足 (HTTP 422)"),
        ):
            with self.subTest(task_type=task_type, message=message):
                info = classify_task_error(message, task_type=task_type, error_code="unknown.unclassified")
                self.assertEqual(info["code"], "external.email")
                self.assertEqual(info["summary"], "库存不足")

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

    def test_password_401_displays_observed_status_without_inferring_password_rejection(self):
        info = classify_task_error(
            "密码提交结果未知", task_type="token_refresh", stage="login_password",
            error_code="password_verify_http_error", task_status="attention_required",
            result_summary={"outcome": "request_unknown", "cause_code": "password_result_unknown",
                            "auth_diagnostics": {"operation": "password_verify", "failure_kind": "http_error",
                                                 "http_status": 401, "response_observed": True}},
        )
        self.assertEqual("password_verify_http_error", info["code"])
        self.assertEqual("密码验证请求返回 HTTP 401", info["cause_summary"])
        self.assertEqual("login_password", info["stage"])

    def test_auth_error_summary_includes_only_recognized_server_code(self):
        summary = {"cause_code": "password_result_unknown", "auth_diagnostics": {
            "operation": "password_verify", "failure_kind": "http_error", "http_status": 401,
            "auth_error": {"code": "session_expired", "type": "authentication_error"},
        }}
        info = classify_task_error("密码验证失败", task_type="token_refresh", result_summary=summary)
        self.assertEqual("密码验证请求返回 HTTP 401（服务端错误码：session_expired）", info["summary"])
        summary["auth_diagnostics"]["auth_error"]["code"] = "private-secret"
        info = classify_task_error("密码验证失败", task_type="token_refresh", result_summary=summary)
        self.assertNotIn("private-secret", str(info))

    def test_mfa_403_diagnostics_override_incorrect_saved_password_stage(self):
        info = classify_task_error(
            "账号已停用", task_type="token_refresh", stage="login_password",
            error_code="mfa_verify_http_error", task_status="deactivated",
            result_summary={"cause_code": "account_deactivated",
                            "auth_diagnostics": {"operation": "mfa_verify", "failure_kind": "http_error",
                                                 "http_status": 403, "response_observed": True}},
        )
        self.assertEqual("mfa_verify_http_error", info["code"])
        self.assertEqual("MFA 验证请求返回 HTTP 403", info["cause_summary"])
        self.assertEqual("mfa_challenge", info["stage"])

    def test_mfa_stage_projection_is_limited_to_terminal_account_auth_tasks(self):
        summary = {"cause_code": "protocol_network_error", "auth_diagnostics": {
            "operation": "mfa_verify", "failure_kind": "http_error", "http_status": 403}}
        for task_type, status, expected_stage in (
            ("live_check", "failed", "mfa_challenge"),
            ("token_refresh", "running", "login_password"),
            ("registration", "failed", "login_password"),
        ):
            with self.subTest(task_type=task_type, status=status):
                info = classify_task_error("认证失败", task_type=task_type, stage="login_password",
                                           task_status=status, result_summary=summary)
                self.assertEqual(expected_stage, info["stage"])

    def test_password_email_fallback_mfa_failure_uses_nested_operation_stage(self):
        for operation, cause_operation, expected_stage in (
            ("password_email_fallback", "mfa_verify", "mfa_challenge"),
            ("password_email_fallback", "email_otp", "login_password"),
            ("password_verify", "mfa_verify", "login_password"),
        ):
            with self.subTest(operation=operation, cause_operation=cause_operation):
                info = classify_task_error(
                    "密码认证后验证失败", task_type="token_refresh", stage="login_password", task_status="failed",
                    result_summary={"cause_code": "password_rejected_email_fallback_failed",
                                    "auth_diagnostics": {"operation": operation, "cause_operation": cause_operation,
                                                         "cause_failure_kind": "http_error", "http_status": 403}},
                )
                self.assertEqual(expected_stage, info["stage"])

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

    def test_proxy_pool_wait_and_reuse_exhaustion_show_specific_reasons(self):
        for message, expected in (
            ("ProxyPoolTimeout: 代理池暂时没有符合要求的可用线路，领取等待超时", "等待可用线路超时"),
            ("ProxyPoolTimeout: 当前线路已达到查询次数上限，等待其他可用线路", "IP 查询次数已用尽，等待换线超时"),
            ("RuntimeError: 1024Proxy 获取失败：上游超时", "代理获取失败"),
        ):
            with self.subTest(message=message):
                info = classify_task_error(message, task_type="plan_check", stage="network")
                self.assertEqual("external.proxy", info["code"])
                self.assertEqual(expected, info["summary"])

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
        self.assertEqual(info["code"], "password_result_unknown")
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
        self.assertEqual("诊断证据不足，无法确认具体原因", info["summary"])
        self.assertEqual("诊断证据不足", info["source_label"])
        self.assertEqual("具体原因未确认", info["kind_label"])
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

    def test_confirmed_provider_failure_has_specific_error_without_reconciliation(self):
        info = classify_task_error(
            "平台提链失败：必须隐藏的远端细项", stage="extraction", task_type="extract_link",
            error_code="extract_provider_failed", task_status="failed",
            result_summary={
                "cause_code": "extract_provider_failed", "remote_result_state": "failed",
                "remote_terminal_failure": True,
            },
        )
        self.assertEqual("extract_provider_failed", info["code"])
        self.assertEqual("extract_provider_failed", info["error_code"])
        self.assertEqual("LINK-FAILED", info["display_code"])
        self.assertEqual("平台提链失败", info["summary"])
        self.assertEqual("extraction", info["stage"])
        self.assertEqual("external", info["source"])
        self.assertNotIn("reconcile_required", info)
        self.assertNotEqual("manual_reconcile", info["next_action"])

    def test_provider_failure_error_code_is_readable_without_summary(self):
        info = classify_task_error(
            "远端细项未保存", task_type="extract_link", error_code="extract_provider_failed",
        )
        self.assertEqual("extract_provider_failed", info["code"])
        self.assertEqual("LINK-FAILED", info["display_code"])
        self.assertEqual("平台提链失败", info["summary"])

    def test_historical_provider_failure_keeps_existing_reconciliation(self):
        info = classify_task_error(
            "平台提链失败", task_type="extract_link", stage="payment",
            error_code="extract_link_receipt_missing", task_status="attention_required",
            result_summary={"outcome": "request_unknown", "reconcile_required": True},
        )
        self.assertEqual("extract_provider_failed", info["code"])
        self.assertEqual("extract_provider_failed", info["error_code"])
        self.assertEqual("extract_link_receipt_missing", info["original_error_code"])
        self.assertEqual("LINK-FAILED", info["display_code"])
        self.assertEqual("平台提链失败", info["summary"])
        self.assertTrue(info["reconcile_required"])
        self.assertEqual("manual_reconcile", info["next_action"])

    def test_historical_provider_failure_only_matches_exact_extract_task_message(self):
        for message, task_type in (
            ("平台提链失败", "registration"),
            ("平台提链失败原因未确认", "extract_link"),
        ):
            with self.subTest(message=message, task_type=task_type):
                info = classify_task_error(message, task_type=task_type)
                self.assertEqual("unknown.unclassified", info["code"])

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
            "user_register_result_unknown": "账号创建请求结果未确认，未保留失败细项",
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


class RegistrationBrowserFailureCauseTests(unittest.TestCase):
    """真实阶段异常不能被通用网络或回执分类覆盖。"""

    def test_cloudflare_challenge_requires_structured_failure_evidence(self):
        info = classify_task_error(
            "StageTimeout: 邮箱输入准备恢复预算耗尽", task_type="registration",
            result_summary={"cause_code": "auth_cloudflare_challenge"},
        )
        self.assertEqual("auth_cloudflare_challenge", info["code"])
        self.assertEqual("OA-AUTH-CF-CHALLENGE", info["display_code"])
        self.assertEqual("认证请求被 Cloudflare 挑战阻断", info["summary"])
        without_evidence = classify_task_error(
            "auth_cloudflare_challenge", task_type="registration",
        )
        self.assertNotEqual("auth_cloudflare_challenge", without_evidence["code"])

    def test_missing_email_entry_has_a_fixed_cause_without_guessing_the_root_cause(self):
        info = classify_task_error(
            "账号配置补跑失败：RuntimeError: 找不到邮箱输入框/邮箱入口（未使用文字识别），"
            "state={'inputs': [], 'actions': [], 'url': 'https://chatgpt.com/auth/login'}",
            task_type="registration",
        )
        self.assertEqual("email_entry_not_ready", info["code"])
        self.assertEqual("FLOW-EMAIL-003", info["display_code"])
        self.assertEqual("邮箱输入框或邮箱入口尚未就绪", info["summary"])
        self.assertEqual("workflow", info["source"])
        self.assertEqual("unknown", info["remote_state_impact"])

    def test_stage_timeout_alone_is_a_stage_symptom_without_network_evidence(self):
        info = classify_task_error(
            "账号配置补跑失败：StageTimeout: email-entry: 邮箱输入准备恢复预算耗尽",
            task_type="registration",
        )
        self.assertEqual("browser_stage_timeout", info["code"])
        self.assertEqual("FLOW-STAGE-001", info["display_code"])
        self.assertEqual("workflow", info["source"])
        self.assertEqual("浏览器阶段等待预算耗尽，具体原因证据不足", info["summary"])

    def test_more_specific_browser_failure_precedes_generic_stage_timeout(self):
        info = classify_task_error(
            "StageTimeout: 找不到邮箱输入框/邮箱入口（未使用文字识别）",
            task_type="registration",
        )
        self.assertEqual("email_entry_not_ready", info["code"])

    def test_shared_account_login_causes_apply_to_real_setup_types_only(self):
        cases = (
            ("RuntimeError: 找不到邮箱输入框/邮箱入口（未使用文字识别）", "email_entry_not_ready"),
            ("_PasswordTransitionTimeout: request_unknown: 密码提交结果未确认", "password_result_unknown"),
            ("StageTimeout: 邮箱输入准备恢复预算耗尽", "browser_stage_timeout"),
            ("StageTimeout: net::ERR_TUNNEL_CONNECTION_FAILED", "roxy_proxy_tunnel_failed"),
        )
        for task_type in ("twofa_retry", "account_setup_retry", "password_setup", "account_completion"):
            for raw, code in cases:
                with self.subTest(task_type=task_type, code=code):
                    info = classify_task_error(raw, task_type=task_type)
                    self.assertEqual(code, info["code"])
            profile = classify_task_error(
                "RuntimeError: 资料提交后的会话读取未完成", task_type=task_type,
            )
            self.assertNotEqual("profile_session_read_failed", profile["code"])
        for task_type in ("extract_link", "plan_check", "live_check"):
            for raw, code in cases:
                with self.subTest(task_type=task_type, code=code):
                    info = classify_task_error(raw, task_type=task_type)
                    self.assertNotEqual(code, info["code"])

    def test_existing_browser_messages_keep_the_known_failure_stage(self):
        cases = (
            (
                "_EmailSubmissionUnknown: request_unknown: 邮箱提交结果在共享预算内未确认，未重复点击或发送认证请求",
                "registration_receipt_missing", "email_submit_unconfirmed", "FLOW-EMAIL-001",
                "邮箱提交后未确认下一步", True,
            ),
            (
                "_EmailSubmissionUnknown: request_unknown: 邮箱提交后阶段预算耗尽，远端结果未确认",
                "registration_receipt_missing", "email_submit_unconfirmed", "FLOW-EMAIL-001",
                "邮箱提交后未确认下一步", True,
            ),
            (
                "_PasswordTransitionTimeout: request_unknown: 已触发密码提交操作，等待 120 秒仍未确认远端结果",
                "external.network", "password_result_unknown", "AUTH-PWD-004",
                "密码提交结果未确认", True,
            ),
            (
                "RuntimeError: request_unknown: 资料提交后的会话读取未完成，已保留原提交",
                "registration_receipt_missing", "profile_session_read_failed", "FLOW-PROFILE-001",
                "资料提交后的会话读取未完成", True,
            ),
            (
                "RuntimeError: request_unknown: 资料提交后的会话尚未确认登录态，已保留原提交",
                "registration_receipt_missing", "profile_session_unconfirmed", "FLOW-PROFILE-002",
                "资料提交后的登录态未确认", True,
            ),
            (
                "RuntimeError: request_unknown: 资料提交后进入认证错误页，账号创建结果未确认",
                "registration_receipt_missing", "profile_auth_error", "FLOW-PROFILE-003",
                "资料阶段进入认证错误页", True,
            ),
            (
                "registration_failed: RuntimeError: 邮箱提交/认证跳转超过总预算 240 秒",
                "external.openai", "email_transition_timeout", "FLOW-EMAIL-002",
                "邮箱提交或认证跳转预算耗尽", False,
            ),
            (
                "registration_failed: RuntimeError: 无法切换到创建密码页：create_account_password_navigation_timeout",
                "external.openai", "password_entry_navigation_timeout", "FLOW-PWD-005",
                "创建密码页跳转超时", False,
            ),
        )
        for task_type in ("registration", "registration_resume"):
            for raw, original_code, code, display, summary, unknown in cases:
                with self.subTest(task_type=task_type, code=code, original_code=original_code):
                    info = classify_task_error(raw, task_type=task_type, error_code=original_code)
                    self.assertEqual(code, info["code"])
                    self.assertEqual(display, info["display_code"])
                    self.assertEqual(summary, info["summary"])
                    self.assertEqual(original_code, info["original_error_code"])
                    self.assertEqual(unknown, info.get("reconcile_required", False))
                    if unknown:
                        self.assertEqual("manual_only", info["retryability"])
                        self.assertEqual("manual_reconcile", info["next_action"])

    def test_specific_structured_diagnostics_keep_precedence(self):
        info = classify_task_error(
            "_PasswordTransitionTimeout: request_unknown: 密码提交结果未确认",
            task_type="registration", result_summary={
                "cause_code": "password_verify_failed",
                "auth_diagnostics": {"operation": "password_verify", "curl_error_code": 35},
            },
        )
        self.assertEqual("password_verify_transport_tls", info["code"])
        self.assertEqual("manual_reconcile", info["next_action"])

    def test_browser_cause_does_not_reclassify_other_task_types(self):
        info = classify_task_error(
            "RuntimeError: 资料提交后的会话读取未完成",
            task_type="extract_link",
        )
        self.assertNotEqual("profile_session_read_failed", info["code"])

    def test_fixed_summary_does_not_copy_identity_or_credentials(self):
        info = classify_task_error(
            "_PasswordTransitionTimeout: request_unknown: unit@example.test password=unit-secret",
            task_type="registration",
        )
        self.assertEqual("password_result_unknown", info["code"])
        self.assertNotIn("unit@example.test", str(info))
        self.assertNotIn("unit-secret", str(info))


if __name__ == "__main__":
    unittest.main()
