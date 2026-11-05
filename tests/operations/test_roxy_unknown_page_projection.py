"""Roxy 未识别页面经过维护摘要过滤后仍能显示明确分类。"""
from copy import deepcopy

import pytest

from core.accounts.liveness import service
from core.operations.errors import classify_task_error


@pytest.mark.parametrize("stage", ["login", "email_otp"])
def test_roxy_unknown_page_survives_summary_filter_without_losing_submission_facts(stage):
    result = {
        "error_code": "auth_page_unknown",
        "error": "无法识别认证页面；页面状态=UNKNOWN；路由=/unsupported-auth-page",
        "auth_diagnostics": {
            "operation": f"roxy_{stage}", "failure_kind": "runtime_exception",
            "exception_type": "RuntimeError",
        },
    }
    original = deepcopy(result)
    summary = {
        "cause_code": service._safe_refresh_cause_code(result),
        "auth_diagnostics": service._safe_refresh_auth_diagnostics(result["auth_diagnostics"]),
        "outcome": "request_unknown", "remote_request_started": True,
    }
    before = deepcopy(summary)
    info = classify_task_error(
        result["error"], task_type="token_refresh", stage=stage,
        error_code="request_unknown", result_summary=summary, task_status="failed",
    )
    assert info["code"] == "auth_page_unknown"
    assert info["display_code"] == "AUTH-PAGE-001"
    assert info["summary"] == "认证页面状态未识别"
    assert info["reconcile_required"] is True
    assert info["original_error_code"] == "request_unknown"
    assert summary == before
    assert result == original
