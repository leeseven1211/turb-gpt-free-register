"""补密码的认证、二次验证及候选拒绝须显示明确原因。"""
from copy import deepcopy

import pytest

from core.operations.errors import classify_task_error


SETUP_CASES = [
    ("password_setup_mfa_rejected", "AUTH-PWD-SETUP-MFA-001", "补密码 2FA 验证未通过"),
    ("password_setup_mfa_factor_missing", "AUTH-PWD-SETUP-MFA-002", "补密码重新验证缺少有效的 2FA 挑战"),
    ("password_setup_mfa_secret_invalid", "CFG-PWD-SETUP-MFA-001", "补密码使用的 2FA 密钥格式无效"),
    ("password_setup_mfa_secret_missing", "AUTH-PWD-SETUP-008", "补密码需要额外 MFA 验证"),
    ("password_setup_otp_send_unconfirmed", "MAIL-PWD-SETUP-004", "补密码验证码发送未返回有效的验证页面"),
    ("password_setup_previous_result_unknown", "AUTH-PWD-SETUP-011", "原密码已验证，上次密码提交结果仍待核验"),
    ("password_setup_password_reset_required", "AUTH-PWD-SETUP-RESET", "远端要求重置密码，原密码当前无法用于登录"),
    ("password_setup_password_rejected", "AUTH-PWD-SETUP-012", "补密码登录时原密码被拒绝"),
    ("password_setup_email_otp_failed", "MAIL-PWD-SETUP-005", "补密码登录邮箱验证码验证未完成"),
    ("password_setup_oauth_callback_failed", "AUTH-PWD-SETUP-CALLBACK", "补密码登录回调未完成，尚未取得新会话"),
    ("password_setup_access_token_missing", "AUTH-PWD-SETUP-013", "补密码登录未取得有效 Token"),
    ("password_setup_protocol_network_error", "NET-PWD-SETUP-003", "补密码登录网络请求未完成"),
]


@pytest.mark.parametrize("code,display,summary", SETUP_CASES)
@pytest.mark.parametrize("surface", ["error_code", "summary", "legacy_message"])
def test_password_setup_specific_cause_survives_every_task_projection(code, display, summary, surface):
    private = {"email": "private@example.test", "password": "private-candidate", "token": "private-token"}
    original = {"error_code": code, "remote_receipt_state": "rejected", "private_context": private}
    before = deepcopy(original)
    projected = classify_task_error(
        f"RuntimeError: {code}: 原始细节" if surface == "legacy_message" else "补密码未完成",
        task_type="password_setup", stage="set_password",
        error_code=code if surface == "error_code" else "",
        result_summary=original if surface == "summary" else {},
    )
    assert projected["code"] == code
    assert projected["display_code"] == display
    assert projected["summary"] == summary
    assert projected["source"] != "unknown"
    if code == "password_setup_mfa_secret_invalid":
        assert projected["source"] == "configuration"
    assert all(value not in str(projected) for value in private.values())
    assert original == before


def test_unknown_previous_password_submission_preserves_reconciliation_state():
    original = {"error_code": "password_setup_previous_result_unknown", "outcome": "request_unknown",
                "remote_receipt_state": "unknown", "mutation_submitted": False}
    before = deepcopy(original)
    projected = classify_task_error(
        "原密码验证已通过，但上次密码提交结果仍需核验", task_type="password_setup",
        error_code="password_setup_previous_result_unknown", result_summary=original,
    )
    assert projected["code"] == "password_setup_previous_result_unknown"
    assert projected["display_code"] == "AUTH-PWD-SETUP-011"
    assert projected["reconcile_required"] is True
    assert projected["remote_state_impact"] == "unknown"
    assert original == before


@pytest.mark.parametrize("suffix,display,summary", [
    ("password_login_confirmation_not_prepared", "FLOW-PWD-REC-030", "上次密码候选已提交，不能用原密码登录结果确认候选"),
    ("password_login_confirmation_mismatch", "FLOW-PWD-REC-031", "本轮验证的原密码与检查点保存值不匹配"),
    ("password_login_confirmation_unverified", "FLOW-PWD-REC-032", "密码确认缺少本轮密码验证证据"),
    ("session_context_invalid", "FLOW-PWD-REC-033", "密码恢复会话或 Token 与目标账号身份无法对应"),
])
@pytest.mark.parametrize("surface", ["exception", "structured"])
def test_existing_password_confirmation_rejection_has_a_fixed_workflow_cause(suffix, display, summary, surface):
    raw = "PasswordRecoveryError: 密码恢复失败：" + suffix if surface == "exception" else "补密码未完成"
    evidence = {"cause_code": "password_recovery_" + suffix} if surface == "structured" else {}
    projected = classify_task_error(raw, task_type="password_setup", result_summary=evidence)
    assert projected["code"] == "workflow.password_recovery." + suffix
    assert projected["display_code"] == display
    assert projected["summary"] == summary
    assert projected["source"] == "workflow"
