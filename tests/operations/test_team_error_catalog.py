"""Team 原因使用统一分类目录，细因和正常等待不能被概括成失败。"""
from __future__ import annotations

from copy import deepcopy
import unittest

from core.operations.error_labels import short_error_label
from core.operations.errors import classify_task_error


TEAM_REASONS = (
    ("probe_not_ready", "等待探测完成"),
    ("probe_expired", "探测已过期"),
    ("probe_revision_conflict", "探测版本变化"),
    ("probe_identity_mismatch", "探测身份不符"),
    ("manager_permission_unconfirmed", "管理权限待核验"),
    ("team_already_bound", "工作区已绑定"),
    ("already_in_another_team", "已属其他Team"),
    ("already_member", "已是成员"),
    ("missing_auth_materials", "缺认证材料"),
    ("account_identity_changed", "账号身份变化"),
    ("team_limit_required", "缺人数上限"),
    ("selection_team_mismatch", "名单团队不符"),
    ("no_eligible_targets", "无可处理目标"),
    ("team_workspace_unavailable", "工作区不可见"),
    ("team_permission_denied", "无管理权限"),
    ("team_invite_rate_limited", "邀请限流"),
    ("team_invite_rejected", "邀请被拒"),
    ("team_invite_receipt_missing", "邀请回执缺失"),
    ("team_invitation_expired", "邀请已过期"),
    ("team_invitation_revoked", "邀请已撤回"),
    ("team_workspace_mismatch", "工作区不符"),
    ("team_member_unconfirmed", "成员待核验"),
    ("team_save_failed", "结果保存失败"),
    ("team_execution_lost", "执行租约失效"),
    ("waiting_account", "等待账号空闲"),
    ("waiting_sync", "等待同步"),
    ("waiting_capacity", "等待名额"),
    ("team_join_endpoint_required", "请从团队加入"),
    ("selection_transaction_required", "名单事务缺失"),
    ("team_outbox_store_failed", "出站入队保存失败"),
    ("team_child_failed", "加入子任务失败"),
    ("team_execution_failed", "阶段程序异常"),
    ("team_accept_receipt_missing", "接受回执缺失"),
    ("team_account_busy", "等待账号空闲"),
    ("team_store_unavailable", "团队存储不可用"),
    ("team_auth_network_failed", "团队认证网络失败"),
    ("team_auth_required", "需要团队认证"),
    ("team_auth_response_invalid", "认证响应无效"),
    ("team_auth_context_invalid", "认证上下文无效"),
    ("team_remote_network_failed", "团队请求网络失败"),
    ("team_remote_http_failed", "团队接口异常"),
    ("team_remote_response_invalid", "团队响应无效"),
    ("team_invite_unsupported", "邀请暂不支持"),
    ("team_accept_unsupported", "接受暂不支持"),
    ("workspace_paid_seat_capacity_exhausted", "工作区席位不足"),
    ("workspace_join_request_pending", "加入待审批"),
    ("workspace_invite_seat_type_mismatch", "邀请席位不符"),
    ("autojoin_retry_pending", "等待加入重试"),
)


class TeamErrorCatalogTests(unittest.TestCase):
    def test_structured_team_reasons_keep_their_registered_short_labels(self):
        """遗漏原因映射会退回诊断缺失，丢失可操作的 Team 业务原因。"""
        for code, label in TEAM_REASONS:
            for field in ("error_code", "cause_code"):
                with self.subTest(code=code, field=field):
                    arguments = {"error_code": code} if field == "error_code" else {
                        "result_summary": {"cause_code": code},
                    }
                    info = classify_task_error(
                        "", task_type="team_join", stage="state_check", **arguments,
                    )
                    self.assertIsNotNone(info)
                    self.assertEqual(code, info["code"])
                    self.assertEqual(label, short_error_label(info))
                    self.assertEqual("state_check", info["stage"])
                    self.assertLessEqual(len(short_error_label(info)), 10)

    def test_normal_waiting_and_completed_outcomes_do_not_become_failures(self):
        for code in ("waiting_account", "waiting_sync", "waiting_capacity", "team_account_busy",
                     "already_member", "no_eligible_targets"):
            with self.subTest(code=code):
                summary = {"cause_code": code, "execution_status": "waiting", "membership_state": "joined"}
                before = deepcopy(summary)
                info = classify_task_error(
                    "", task_type="team_join", stage="member_verify", result_summary=summary,
                    task_status="waiting",
                )
                self.assertFalse(info["is_error"])
                self.assertNotIn("status", info)
                self.assertEqual(before, summary)

    def test_team_summary_never_overrides_saved_authentication_or_storage_details(self):
        cases = (
            ("password_rejected", "member_auth", "password_rejected"),
            ("email_otp_invalid", "member_auth", "email_otp_invalid"),
            ("totp_rejected", "member_auth", "totp_rejected"),
            ("password_recovery_database_deadlock_detected", "persist", "internal.storage"),
        )
        for concrete, stage, expected in cases:
            with self.subTest(concrete=concrete):
                summary = {"cause_code": concrete}
                info = classify_task_error(
                    "", task_type="team_join", stage=stage, error_code="team_invite_rejected",
                    result_summary=summary, task_status="failed",
                )
                self.assertEqual(expected, info["code"])
                self.assertEqual(stage, info["stage"])
        info = classify_task_error(
            "", task_type="team_join", stage="member_auth", error_code="password_rejected",
            result_summary={"cause_code": "team_invite_rejected"}, task_status="failed",
        )
        self.assertEqual("password_rejected", info["code"])

    def test_team_summary_yields_to_concrete_auth_diagnostics_and_database_evidence(self):
        info = classify_task_error(
            "认证调用超时", task_type="team_join", stage="member_auth",
            error_code="team_invite_rejected",
            result_summary={"cause_code": "team_invite_rejected", "auth_diagnostics": {
                "operation": "password_verify", "failure_kind": "transport_error", "curl_error_code": 28,
            }},
        )
        self.assertEqual("password_verify_transport_timeout", info["code"])
        info = classify_task_error(
            "PostgreSQL deadlock detected", task_type="team_join", stage="persist",
            error_code="team_save_failed", result_summary={"cause_code": "team_save_failed"},
        )
        self.assertEqual("internal.storage", info["code"])

    def test_missing_invite_receipt_preserves_reconciliation_without_permanent_retry_block(self):
        for code, stage in (("team_invite_receipt_missing", "invite"), ("team_accept_receipt_missing", "accept")):
            with self.subTest(code=code):
                summary = {"cause_code": code, "outcome": "request_unknown"}
                info = classify_task_error(
                    "", task_type="team_join", stage=stage, error_code=code,
                    result_summary=summary, task_status="request_unknown",
                )
                self.assertEqual(code, info["code"])
                self.assertTrue(info["reconcile_required"])
                self.assertEqual("conditional", info["retryability"])
                self.assertEqual("retry_with_reconcile", info["next_action"])
                self.assertEqual("request_unknown", summary["outcome"])

    def test_team_auth_and_remote_failures_do_not_infer_deactivated_accounts(self):
        for code in ("team_auth_required", "team_remote_http_failed", "team_auth_response_invalid"):
            with self.subTest(code=code):
                info = classify_task_error(
                    "Team 远端请求返回 HTTP 401", task_type="team_sync", stage="manager_verify",
                    error_code=code, result_summary={"cause_code": code}, task_status="failed",
                )
                self.assertEqual(code, info["code"])
                self.assertNotEqual("account.deactivated", info["code"])
                self.assertEqual("manager_verify", info["stage"])

    def test_unsupported_actions_keep_explicit_capability_reason_and_allow_later_retry(self):
        for code, stage in (("team_invite_unsupported", "invite"), ("team_accept_unsupported", "accept")):
            with self.subTest(code=code):
                info = classify_task_error(
                    "", task_type="team_join", stage=stage, error_code=code, task_status="unsupported",
                )
                self.assertEqual(code, info["code"])
                self.assertEqual("not_started", info["remote_state_impact"])
                self.assertEqual("conditional", info["retryability"])

    def test_remote_pending_join_reasons_preserve_waiting_and_allow_retry(self):
        for code in ("workspace_paid_seat_capacity_exhausted", "workspace_join_request_pending",
                     "autojoin_retry_pending"):
            with self.subTest(code=code):
                info = classify_task_error(
                    "", task_type="team_join", stage="accept", error_code=code, task_status="waiting",
                )
                self.assertEqual(code, info["code"])
                self.assertFalse(info["is_error"])
                self.assertEqual("wait", info["next_action"])
                self.assertEqual("conditional", info["retryability"])
                self.assertNotIn("status", info)


if __name__ == "__main__":
    unittest.main()
