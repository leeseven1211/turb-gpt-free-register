"""任务错误展示只细化同一 Roxy 调试任务已保存的认证挑战。"""
from copy import deepcopy
from unittest.mock import patch

import pytest

from webui.app import create_app
from webui.route_helpers import _compact_job_for_list


RAW_ERROR = "_EmailSubmissionUnknown: request_unknown: 邮箱提交后阶段预算耗尽，远端结果未确认"


def challenged_job():
    return {
        "id": 992, "status": "failed", "job_type": "registration_resume", "debug_enabled": True,
        "config_snapshot": {"registration_driver": "roxy"}, "progress_stage": "auth_redirect",
        "error_message": RAW_ERROR, "error_code": "request_unknown", "request_unknown": True,
        "retryable": True, "retry_action": "registration_resume",
        "debug_capture_summary": {
            "job_id": 992, "capture_mode": "full", "failure_stage": "auth_redirect",
            "error_info": {"code": "auth_cloudflare_challenge", "cause_code": "auth_cloudflare_challenge",
                           "summary": "不直接信任此文案", "private_extra": "不应进入投影"},
        },
    }


@pytest.fixture
def client():
    return create_app(auth_code="test-auth").test_client()


def projection(row, surface, client):
    if surface == "list":
        return _compact_job_for_list(row, include_progress=False)
    with patch("webui.routes.jobs.db.get_job", return_value=deepcopy(row)), patch(
        "webui.routes.jobs.svc.read_job_log", return_value="测试日志",
    ):
        response = client.get("/api/jobs/992/log", headers={"X-Auth-Code": "test-auth"})
    assert response.status_code == 200
    return response.get_json()["job"]


@pytest.mark.parametrize("surface", ["list", "log"])
@pytest.mark.parametrize("job_type", ["registration", "registration_resume"])
def test_password_prepare_failure_is_classified_without_changing_retry(surface, job_type, client):
    row = challenged_job()
    row.update(
        job_type=job_type, progress_stage="complete", request_unknown=False,
        error_code="registration_failed",
        error_message=("registration_failed: RuntimeError: password_form_not_ready: "
                       "密码表单在提交前未就绪，尚未提交密码：password_value_changed；"
                       "path=/log-in/password inputs=3 buttons=3 text_length=155"),
    )
    row.pop("debug_capture_summary")
    original = deepcopy(row)
    result = projection(row, surface, client)
    assert result["error_info"]["code"] == "roxy_password_prepare_timeout"
    assert result["error_info"]["display_code"] == "AUTH-PWD-PREPARE"
    assert result["error_info"]["summary"] == "密码表单准备超时"
    assert not result["error_info"].get("reconcile_required", False)
    assert result["retryable"] is True
    assert result["retry_action"] == "registration_resume"
    assert result["error_message"] == original["error_message"]
    assert row == original


@pytest.mark.parametrize("surface", ["list", "log"])
@pytest.mark.parametrize("job_type", ["registration", "registration_resume"])
@pytest.mark.parametrize("terminal_stage", ["auth_redirect", "complete"])
def test_saved_current_roxy_challenge_reaches_list_and_log_without_changing_unknown(surface, job_type, terminal_stage, client):
    row = challenged_job()
    row["job_type"] = job_type
    row["progress_stage"] = terminal_stage
    original = deepcopy(row)
    result = projection(row, surface, client)
    info = result["error_info"]
    assert info["code"] == "auth_cloudflare_challenge"
    assert info["display_code"] == "OA-AUTH-CF-CHALLENGE"
    assert info["stage"] == "auth_redirect"
    assert info["summary"] == "认证请求被 Cloudflare 挑战阻断"
    assert info["reconcile_required"] is True
    assert info["retryability"] == "manual_only"
    assert info["remote_state_impact"] == "unknown"
    assert info["next_action"] == "manual_reconcile"
    assert "private_extra" not in info
    assert result["error_message"] == RAW_ERROR
    assert result["status"] == "failed"
    assert result["retryable"] is True
    assert result["retry_action"] == "registration_resume"
    assert row == original


@pytest.mark.parametrize("surface", ["list", "log"])
@pytest.mark.parametrize("change", [
    "no_summary", "other_job", "missing_job_id", "invalid_job_id", "other_driver", "missing_driver", "other_type",
    "not_debug", "failure_only", "other_stage", "other_summary_stage", "ordinary_403", "rum",
    "missing_cause", "completed_success", "specific_password_error",
])
def test_untrusted_or_obsolete_summary_cannot_replace_original_job_error(surface, change, client):
    row = challenged_job()
    expected = "email_submit_unconfirmed"
    summary = row["debug_capture_summary"]
    if change == "no_summary":
        row.pop("debug_capture_summary")
    elif change == "other_job":
        summary["job_id"] = 993
    elif change == "missing_job_id":
        summary.pop("job_id")
    elif change == "invalid_job_id":
        row["id"] = 1
        summary["job_id"] = True
    elif change == "other_driver":
        row["config_snapshot"]["registration_driver"] = "roxy_oss"
    elif change == "missing_driver":
        row["config_snapshot"] = {}
    elif change == "other_type":
        row["job_type"] = "twofa_retry"
    elif change == "not_debug":
        row["debug_enabled"] = False
    elif change == "failure_only":
        summary["capture_mode"] = "failure_only"
    elif change == "other_stage":
        row["progress_stage"] = "profile"
    elif change == "other_summary_stage":
        summary["failure_stage"] = "submit_email"
    elif change in {"ordinary_403", "rum"}:
        summary["error_info"] = {"code": "email_submit_unconfirmed", "cause_code": "email_submit_unconfirmed"}
    elif change == "missing_cause":
        summary["error_info"].pop("cause_code")
    elif change == "completed_success":
        row["status"] = "success"
    else:
        row["error_message"] = "_PasswordTransitionTimeout: request_unknown: 密码结果未确认"
        expected = "password_result_unknown"
    assert projection(row, surface, client)["error_info"]["code"] == expected


@pytest.mark.parametrize("surface", ["list", "log"])
@pytest.mark.parametrize("capture_mode,summary_key", [
    ("full", "debug_capture_summary"), ("failure_only", "failure_diagnostics_summary"),
])
def test_current_password_reset_diagnosis_reaches_job_display_without_changing_job(surface, capture_mode, summary_key, client):
    row = challenged_job()
    row.pop("debug_capture_summary")
    row.update({
        "debug_enabled": capture_mode == "full", "progress_stage": "complete",
        "error_message": "password_page_error: PasswordPageError: 密码登录页显示错误，具体原因未识别",
        summary_key: {"job_id": 992, "capture_mode": capture_mode, "failure_stage": "login_password",
                      "error_info": {"code": "password_change_required", "cause_code": "password_change_required",
                                     "summary": "不直接信任此文案"}},
    })
    original = deepcopy(row)
    result = projection(row, surface, client)
    assert result["error_info"]["code"] == "password_change_required"
    assert result["error_info"]["display_code"] == "AUTH-PWD-RESET"
    assert result["error_info"]["summary"] == "OpenAI 要求修改密码后重新登录"
    assert result["error_info"]["stage"] == "login_password"
    assert result["error_message"] == original["error_message"]
    assert result["status"] == "failed"
    assert result["retryable"] is True
    assert row == original


@pytest.mark.parametrize("change", ["other_job", "other_stage", "other_driver", "success", "specific_failure", "missing_cause"])
def test_obsolete_password_reset_diagnosis_cannot_replace_job_error(change):
    row = challenged_job()
    row.update({"progress_stage": "complete", "error_message": "password_page_error: PasswordPageError: 密码登录页显示错误，具体原因未识别"})
    summary = row["debug_capture_summary"]
    summary.update({"failure_stage": "login_password", "error_info": {
        "code": "password_change_required", "cause_code": "password_change_required",
    }})
    expected = "password_page_error"
    if change == "other_job":
        summary["job_id"] = 993
    elif change == "other_stage":
        summary["failure_stage"] = "email_otp"
    elif change == "other_driver":
        row["config_snapshot"]["registration_driver"] = "protocol_oss_2"
    elif change == "success":
        row["status"] = "success"
    elif change == "missing_cause":
        summary["error_info"].pop("cause_code")
    else:
        row["error_message"] = "password_rejected"
        expected = "password_rejected"
    assert _compact_job_for_list(row, include_progress=False)["error_info"]["code"] == expected


def accepted_resend_job():
    row = challenged_job()
    row.update({
        "progress_stage": "complete", "run_id": 17, "execution_id": "unit-execution",
        "error_message": ("otp_request_unconfirmed: 验证码请求缺少页面或网络确认；"
                          "不能断言服务端已经发信"),
        "debug_capture_summary": {
            "job_id": 992, "run_id": 17, "execution_id": "unit-execution", "capture_mode": "full",
            "failure_stage": "email_otp", "error_info": {
                "code": "email_otp_no_mail", "cause_code": "email_otp_no_mail",
                "otp_request_accepted": True, "summary": "不可直接信任的正文", "private_extra": "private-value",
            },
        },
    })
    return row


@pytest.mark.parametrize("surface", ["list", "log"])
def test_current_accepted_resend_refines_no_mail_display_without_changing_retry(surface, client):
    row = accepted_resend_job()
    original = deepcopy(row)
    baseline = deepcopy(row)
    baseline.pop("debug_capture_summary")
    original_projection = projection(baseline, surface, client)
    result = projection(row, surface, client)
    info = result["error_info"]
    assert info["code"] == "email_otp_no_mail"
    assert info["cause_code"] == "email_otp_no_mail"
    assert info["display_code"] == "MAIL-OTP-005"
    assert info["summary"] == "等待窗口内未收到验证码邮件"
    assert info["otp_request_accepted"] is True
    assert "private_extra" not in info
    for key in ("status", "error_message", "request_unknown", "retryable", "retry_action"):
        assert (key in result) == (key in original_projection)
        assert result.get(key) == original_projection.get(key)
    assert row == original


def test_actual_capture_summary_reaches_job_list_after_delayed_resend_acceptance():
    from tests.registration.test_registration_otp_delivery_diagnostics import Capture

    capture = Capture(id=992)
    capture.request()
    capture.response()
    assert capture.classify()["code"] == "email_otp_no_mail"
    row = accepted_resend_job()
    row["debug_capture_summary"] = capture.session.summary()
    assert _compact_job_for_list(row, include_progress=False)["error_info"]["code"] == "email_otp_no_mail"


@pytest.mark.parametrize("change", [
    "other_job", "other_run", "other_execution", "other_stage", "other_driver", "no_debug",
    "failure_only", "missing_acceptance", "missing_cause", "success", "other_failure",
])
def test_obsolete_or_unaccepted_resend_cannot_replace_job_failure(change):
    row = accepted_resend_job()
    summary = row["debug_capture_summary"]
    if change == "other_job":
        summary["job_id"] = 993
    elif change == "other_run":
        summary["run_id"] = 18
    elif change == "other_execution":
        summary["execution_id"] = "other-execution"
    elif change == "other_stage":
        summary["failure_stage"] = "login_password"
    elif change == "other_driver":
        row["config_snapshot"]["registration_driver"] = "protocol_oss_2"
    elif change == "no_debug":
        row["debug_enabled"] = False
    elif change == "failure_only":
        summary["capture_mode"] = "failure_only"
    elif change == "missing_acceptance":
        summary["error_info"].pop("otp_request_accepted")
    elif change == "missing_cause":
        summary["error_info"].pop("cause_code")
    elif change == "success":
        row["status"] = "success"
    else:
        row["error_message"] = "otp_request_unconfirmed: 原验证码提交仍未确认"
    assert _compact_job_for_list(row, include_progress=False)["error_info"]["code"] != "email_otp_no_mail"
