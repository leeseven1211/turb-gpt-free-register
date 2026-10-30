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
