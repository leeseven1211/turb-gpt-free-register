"""失败现场只使用本次未恢复的认证证据，不让单条网络事件改写任务主因。"""
from unittest.mock import patch

import pytest

from core.registration import debug as debug


@pytest.fixture(params=[
    ("full", "registration"), ("failure_only", "registration"),
    ("full", "twofa_retry"), ("failure_only", "twofa_retry"),
])
def session(request):
    capture_mode, job_type = request.param
    with patch.object(debug.RegistrationDebugSession, "_start_capture"):
        value = debug.RegistrationDebugSession({
            "id": 991, "job_uuid": "unit-failure-evidence", "progress_stage": "submit_email",
            "job_type": job_type,
        }, capture_mode=capture_mode)
    return value


def challenge_record(**changes):
    return {
        "method": "POST", "url": "https://chatgpt.com/api/auth/signin/openai?state=private-token",
        "stage": "submit_email", "status": 403,
        "response_headers": {"CF-Mitigated": "challenge", "server": "cloudflare", "set-cookie": "private-token"},
        **changes,
    }


def category(session, reason):
    return session._failure_category(reason, {
        "failure_stage": session.failure_stage, "error_info": session.error_info or {},
    }, list(session._failure_network_seen))


def test_failure_network_evidence_retains_only_fixed_auth_error_metadata():
    evidence = debug._failure_network_evidence({
        "method": "POST", "url": "https://auth.openai.com/api/accounts/email-otp/validate?secret=private-token",
        "stage": "email_otp", "status": 401,
        "auth_error": {"code": "invalid_otp", "type": "invalid_request_error",
                       "message": "private@example.test 123456", "category": "private-token"},
        "request_body": "private-password", "response_body": "private-token",
    })
    assert evidence == {
        "status": 401, "failure": False, "auth_endpoint": "otp_submit", "stage": "email_otp",
        "auth_challenge": False,
        "auth_error": {"code": "invalid_otp", "type": "invalid_request_error", "category": "otp_rejected"},
    }


@pytest.mark.parametrize("changes", [
    {"url": "https://auth.openai.com.evil.test/api/accounts/email-otp/validate"},
    {"method": "GET"}, {"status": 200},
])
def test_failure_network_evidence_ignores_unbound_or_success_auth_error(changes):
    evidence = debug._failure_network_evidence({
        "method": "POST", "url": "https://auth.openai.com/api/accounts/email-otp/validate",
        "stage": "email_otp", "status": 401, "auth_error": {"code": "invalid_otp"}, **changes,
    })
    assert "auth_error" not in evidence


@pytest.mark.parametrize("record", [
    {"url": "https://chatgpt.com/cdn/assets/app.js", "resource_type": "Script",
     "failure": "net::ERR_HTTP2_PING_FAILED"},
    {"url": "https://assets.example.test/image.png", "resource_type": "Image",
     "failure": "net::ERR_SSL_PROTOCOL_ERROR"},
    {"url": "https://assets.example.test/blocked.js", "resource_type": "Script",
     "failure": "net::ERR_TUNNEL_CONNECTION_FAILED"},
    {"url": "https://chatgpt.com/cdn/assets/app.js", "resource_type": "Script",
     "failure": "network_failed", "status": 403, "_data_saver_blocked": True},
])
def test_real_transport_and_http_errors_are_not_hidden_by_data_saver_compatibility(record):
    with patch("core.browser.data_saver.configured_resource_types", return_value=["image"]), \
            patch("core.browser.data_saver.configured_url_patterns", return_value=["https://assets.example.test/*"]):
        assert debug._is_expected_data_saver_failure(record) is False


@pytest.mark.parametrize("failure", [
    "net::ERR_HTTP2_PROTOCOL_ERROR", "net::ERR_PROXY_CONNECTION_FAILED", "net::ERR_TLS13_DOWNGRADE_DETECTED",
    "net::ERR_CERT_DATE_INVALID", "net::ERR_CONNECTION_RESET", "net::ERR_CONN_RESET", "net::ERR_TIMED_OUT",
    "net::ERR_NAME_NOT_RESOLVED", "net::ERR_INTERNET_DISCONNECTED",
])
def test_known_chromium_transport_families_override_even_explicit_data_saver_marker(failure):
    assert debug._is_expected_data_saver_failure({"failure": failure, "_data_saver_blocked": True}) is False


@pytest.mark.parametrize("failure", [
    "network_failed", "net::ERR_ABORTED", "net::ERR_BLOCKED_BY_CLIENT",
    "message net::ERR_CONNECTION_RESET", "net::ERR_CONNECTION_RESET trailing", "connection failed",
])
def test_existing_marker_compatibility_and_nontransport_errors_keep_behavior(failure):
    assert debug._is_expected_data_saver_failure({"failure": failure, "_data_saver_blocked": True}) is True


def test_http2_asset_failure_remains_in_diagnostic_counts_and_category(session):
    session.record_network({
        "method": "GET", "url": "https://chatgpt.com/cdn/assets/app.js", "resource_type": "Script",
        "failure": "net::ERR_HTTP2_PING_FAILED", "status": 0,
    })
    summary = session.summary()
    assert summary["failed_count"] == 1
    assert summary["data_saver_blocked_count"] == 0
    assert summary["network_error_observed"] is True
    assert category(session, "找不到邮箱输入框") == "network_or_proxy"


def test_unresolved_auth_challenge_explains_entry_timeout_without_debug_disk_reads(session):
    session.record_network(challenge_record())
    reason = "StageTimeout: 找不到邮箱输入框"
    with patch.object(debug, "read_events", side_effect=AssertionError("分类不得读取磁盘抓包")):
        info = session._classify_failure(reason)
        assert info["code"] == "auth_cloudflare_challenge"
        assert category(session, reason) == "challenge_or_captcha"
    assert "Cloudflare" in info["summary"]
    assert "private-token" not in str(list(session._failure_network_seen))
    assert "response_headers" not in str(list(session._failure_network_seen))


def roxy_email_session(**changes):
    job = {
        "id": 992, "job_uuid": "unit-roxy-email-challenge", "progress_stage": "auth_redirect",
        "job_type": "registration_resume", "debug_enabled": True,
        "config_snapshot": {"registration_driver": "roxy"},
        **changes,
    }
    with patch.object(debug.RegistrationDebugSession, "_start_capture"):
        return debug.RegistrationDebugSession(job, capture_mode=job.pop("capture_mode", "full"))


@pytest.mark.parametrize("job_type", ["registration", "registration_resume"])
def test_roxy_debug_current_signin_challenge_refines_unknown_email_and_keeps_reconcile(job_type):
    value = roxy_email_session(job_type=job_type)
    value.record_network(challenge_record(stage="auth_redirect"))
    reason = "_EmailSubmissionUnknown: request_unknown: 邮箱提交后阶段预算耗尽，远端结果未确认"
    info = value._classify_failure(reason)
    assert info["code"] == "auth_cloudflare_challenge"
    assert info["reconcile_required"] is True
    assert info["retryability"] == "manual_only"
    assert info["remote_state_impact"] == "unknown"
    assert info["next_action"] == "manual_reconcile"
    assert category(value, reason) == "challenge_or_captcha"
    assert value.summary()["error_info"]["cause_code"] == "auth_cloudflare_challenge"


@pytest.mark.parametrize("changes", [
    {"capture_mode": "failure_only"}, {"debug_enabled": False},
    {"config_snapshot": {"registration_driver": "roxy_oss"}},
    {"config_snapshot": {"registration_driver": "protocol_oss_2"}}, {"config_snapshot": {}},
    {"job_type": "twofa_retry"}, {"progress_stage": "password"}, {"progress_stage": "profile"},
])
def test_unknown_email_challenge_refinement_is_limited_to_local_roxy_debug(changes):
    value = roxy_email_session(**changes)
    value.record_network(challenge_record(stage=value.current_stage))
    info = value._classify_failure("_EmailSubmissionUnknown: request_unknown: 未确认下一步")
    assert info["code"] == "email_submit_unconfirmed"


@pytest.mark.parametrize("record", [
    challenge_record(response_headers={}),
    challenge_record(response_headers={"server": "cloudflare"}),
    challenge_record(url="https://auth.openai.com/awe/api/v2/rum"),
    challenge_record(url="https://chatgpt.com.evil.test/api/auth/signin/openai"),
    challenge_record(method="GET"),
])
def test_unknown_roxy_email_requires_real_auth_post_challenge(record):
    value = roxy_email_session(progress_stage="submit_email")
    value.record_network(record)
    info = value._classify_failure("_EmailSubmissionUnknown: request_unknown: 未确认下一步")
    assert info["code"] == "email_submit_unconfirmed"


@pytest.mark.parametrize("following", ["success", "progress", "password_error"])
def test_old_challenge_cannot_replace_later_roxy_outcome(following):
    value = roxy_email_session(progress_stage="submit_email")
    value.record_network(challenge_record())
    reason = "_EmailSubmissionUnknown: request_unknown: 未确认下一步"
    if following == "success":
        value.record_network(challenge_record(status=200, response_headers={}))
    elif following == "progress":
        value.update_stage("auth_redirect", state="success")
    else:
        reason = "_PasswordTransitionTimeout: request_unknown: 密码结果未确认"
    assert value._classify_failure(reason)["code"] != "auth_cloudflare_challenge"


@pytest.mark.parametrize("following", [
    {"status": 200, "response_headers": {}},
    {"status": 400, "response_headers": {}},
    {"status": 0, "response_headers": {}, "failure": "net::ERR_TUNNEL_CONNECTION_FAILED"},
])
def test_later_auth_outcome_prevents_old_challenge_from_becoming_final_cause(session, following):
    session.record_network(challenge_record())
    session.record_network(challenge_record(**following))
    info = session._classify_failure("StageTimeout: 后续阶段等待预算耗尽")
    assert info["code"] != "auth_cloudflare_challenge"
    assert category(session, "StageTimeout: 后续阶段等待预算耗尽") != "challenge_or_captcha"


def test_confirmed_auth_progress_prevents_old_challenge_from_masking_later_failure(session):
    session.record_network(challenge_record())
    session.update_stage("auth_redirect", state="success")
    session.update_stage("submit_email", state="running")
    info = session._classify_failure("StageTimeout: 找不到邮箱输入框")
    assert info["code"] != "auth_cloudflare_challenge"
    assert category(session, "StageTimeout: 找不到邮箱输入框") != "challenge_or_captcha"


def test_page_entry_challenge_still_explains_email_entry_wait_after_page_success(session):
    session.record_network(challenge_record(stage="page"))
    session.update_stage("page", state="success")
    session.update_stage("submit_email", state="running")
    reason = "StageTimeout: 找不到邮箱输入框"
    assert session._classify_failure(reason)["code"] == "auth_cloudflare_challenge"
    assert category(session, reason) == "challenge_or_captcha"


@pytest.mark.parametrize("stage,reason", [
    ("password", "_PasswordTransitionTimeout: 创建密码页没有完成跳转"),
    ("profile", "StageTimeout: 资料页面等待预算耗尽"),
])
def test_entry_challenge_does_not_explain_later_password_or_profile_failure(session, stage, reason):
    session.record_network(challenge_record(stage="page"))
    session.update_stage(stage, state="running")
    assert session._classify_failure(reason)["code"] != "auth_cloudflare_challenge"
    assert category(session, reason) != "challenge_or_captcha"


@pytest.mark.parametrize("changes", [
    {"url": "https://chatgpt.com.evil.test/api/auth/signin/openai"},
    {"url": "https://private@chatgpt.com/api/auth/signin/openai"},
    {"url": "https://chatgpt.com/other"},
    {"method": "GET"},
    {"response_headers": {"server": "cloudflare", "content-type": "text/html"}},
])
def test_untrusted_endpoint_or_unconfirmed_cloudflare_headers_are_not_challenge(session, changes):
    session.record_network(challenge_record(**changes))
    info = session._classify_failure("StageTimeout: 找不到邮箱输入框")
    assert info["code"] != "auth_cloudflare_challenge"
    assert category(session, "StageTimeout: 找不到邮箱输入框") != "challenge_or_captcha"


def test_specific_final_password_error_is_not_replaced_by_old_challenge(session):
    session.record_network(challenge_record())
    info = session._classify_failure("_PasswordTransitionTimeout: 创建密码页没有完成跳转")
    assert info["code"] == "password_result_unknown"
    assert category(session, "_PasswordTransitionTimeout: 创建密码页没有完成跳转") != "challenge_or_captcha"


@pytest.mark.parametrize("reason", ["StageTimeout", "TimeoutError: timed out"])
def test_budget_timeout_alone_does_not_prove_network_or_proxy_failure(reason):
    assert debug.RegistrationDebugSession._failure_category(reason, {}) != "network_or_proxy"
    assert debug.RegistrationDebugSession._failure_category_label("unknown") == "诊断证据不足"


def test_explicit_transport_failure_keeps_network_category(session):
    session.record_network({
        "method": "GET", "url": "https://chatgpt.com/auth/login", "status": 0,
        "failure": "net::ERR_TUNNEL_CONNECTION_FAILED",
    })
    assert category(session, "WebDriverException") == "network_or_proxy"


@pytest.mark.parametrize("reason,expected", [
    ("_PasswordTransitionTimeout: 创建密码页没有完成跳转", "password_result_unknown"),
    ("StageTimeout: 找不到邮箱输入框", "auth_cloudflare_challenge"),
])
def test_network_event_does_not_replace_the_task_terminal_error(session, reason, expected):
    session.record_network(challenge_record())
    original = session._classify_failure(reason)
    assert original["code"] == expected
    session.record_network(challenge_record())
    session.record_network({
        "method": "GET", "url": "https://chatgpt.com/auth/login", "status": 0,
        "failure": "net::ERR_ABORTED",
    })
    assert session.error_info == original
    assert session.summary()["error_info"]["code"] == expected


def otp_record(**changes):
    return {
        "method": "POST", "url": "https://auth.openai.com/api/accounts/email-otp/validate",
        "stage": "email_otp", "status": None, "failure": "net::ERR_TUNNEL_CONNECTION_FAILED",
        **changes,
    }


def rejected_otp_record(**changes):
    return otp_record(status=401, failure="", auth_error={
        "code": "wrong_email_otp_code", "type": "invalid_request_error", "category": "otp_rejected",
    }, **changes)


@pytest.mark.parametrize("job_type", ["registration", "registration_resume"])
@pytest.mark.parametrize("reason", [
    "RuntimeError: request_unknown: otp_request_unconfirmed",
    "StageTimeout: 验证码提交确认预算耗尽", "RuntimeError: 尚未确认下一步",
])
def test_current_exact_otp_401_refines_generic_wait_without_changing_job(job_type, reason):
    value = roxy_email_session(job_type=job_type)
    value.update_stage("email_otp", state="running")
    value.record_network(rejected_otp_record())
    original_job = dict(value.job)
    info = value._classify_failure(reason)
    assert info["code"] == "email_otp_code_rejected"
    assert info["display_code"] == "OA-OTP-CODE-001"
    assert info["stage"] == "email_otp"
    assert value.job == original_job
    if "request_unknown" in reason:
        assert info["reconcile_required"] is True
        assert info["retryability"] == "manual_only"


@pytest.mark.parametrize("following", [
    {"status": 200, "failure": "", "auth_error": {}},
    {"status": 403, "failure": "", "auth_error": {}},
    {"status": None, "failure": "net::ERR_ABORTED", "auth_error": {}},
])
def test_new_auth_outcome_prevents_old_otp_rejection_from_becoming_final(following):
    value = roxy_email_session()
    value.update_stage("email_otp", state="running")
    value.record_network(rejected_otp_record())
    value.record_network(otp_record(**following))
    assert value._classify_failure("request_unknown: otp_request_unconfirmed")["code"] != "email_otp_code_rejected"


def test_confirmed_progress_prevents_recovered_otp_401_from_becoming_final():
    value = roxy_email_session()
    value.update_stage("email_otp", state="running")
    value.record_network(rejected_otp_record())
    value.update_stage("email_otp", state="success")
    value.update_stage("email_otp", state="running")
    assert value._classify_failure("request_unknown: otp_request_unconfirmed")["code"] != "email_otp_code_rejected"


@pytest.mark.parametrize("changes", [
    {"url": "https://auth.openai.com.evil.test/api/accounts/email-otp/validate"},
    {"url": "https://auth.openai.com/api/accounts/password/verify"}, {"method": "GET"},
    {"status": 400}, {"stage": "password"}, {"stage": "browser"},
    {"failure": "net::ERR_ABORTED"},
    {"auth_error": {"code": "invalid_otp"}}, {"auth_error": {"code": "wrong_email_otp_code_typo"}},
    {"auth_error": {"category": "otp_rejected"}},
])
def test_otp_rejection_requires_trusted_post_401_exact_code_and_same_stage(changes):
    value = roxy_email_session()
    value.update_stage("email_otp", state="running")
    record = rejected_otp_record()
    record.update(changes)
    value.record_network(record)
    assert value._classify_failure("request_unknown: otp_request_unconfirmed")["code"] != "email_otp_code_rejected"


@pytest.mark.parametrize("stage", ["", "browser", "submit_email", "profile", "complete"])
def test_otp_rejection_does_not_explain_another_final_stage(stage):
    record = rejected_otp_record()
    assert debug._pending_auth_failure_cause([record], stage) != "email_otp_code_rejected"


def test_otp_rejection_does_not_refine_nonregistration_job():
    value = roxy_email_session(job_type="twofa_retry")
    value.update_stage("email_otp", state="running")
    value.record_network(rejected_otp_record())
    assert value._classify_failure("request_unknown: otp_request_unconfirmed")["code"] != "email_otp_code_rejected"


@pytest.mark.parametrize("reason,expected", [
    ("ValueError: 当前 Run 仍有未决浏览器提交，拒绝重复派发请求", "local_browser_submission_conflict"),
    ("password_rejected", "password_rejected"),
    ("ERR_TUNNEL_CONNECTION_FAILED", "roxy_proxy_tunnel_failed"),
    ("KeyError: 'schema 未定义字段: UNIT_FIELD'", "local_config_schema_mismatch"),
])
def test_otp_401_does_not_replace_specific_final_failure(reason, expected):
    value = roxy_email_session()
    value.update_stage("email_otp", state="running")
    value.record_network(rejected_otp_record())
    assert value._classify_failure(reason)["code"] == expected


@pytest.mark.parametrize("failure", ["net::ERR_TUNNEL_CONNECTION_FAILED", "net::ERR_PROXY_CONNECTION_FAILED"])
@pytest.mark.parametrize("stage", ["email_otp", "browser"])
def test_exact_otp_transport_failure_refines_unconfirmed_receipt_after_password_and_code(session, failure, stage):
    session.update_stage("login_password", state="success")
    session.update_stage(stage, state="running", detail="已收到验证码")
    session.record_network(otp_record(failure=failure, stage=stage))
    session.record_network(otp_record(failure=failure, stage=stage))
    for _ in range(3):
        session.record_network({
            "method": "POST", "url": "https://sentinel.openai.com/backend-api/sentinel/req",
            "stage": stage, "status": None, "failure": failure,
        })
    info = session._classify_failure("_EmailSubmissionUnknown: request_unknown otp_request_unconfirmed")
    assert info["code"] == "roxy_proxy_tunnel_failed"
    assert info["display_code"] == "NET-ROXY-001"
    assert info["reconcile_required"] is True
    assert category(session, "_EmailSubmissionUnknown: request_unknown otp_request_unconfirmed") == "network_or_proxy"
    assert failure not in str(list(session._failure_network_seen))


@pytest.mark.parametrize("following", [
    {"status": 200, "failure": ""}, {"status": 403, "failure": ""},
    {"status": None, "failure": "net::ERR_ABORTED"},
])
def test_new_auth_outcome_prevents_old_transport_from_replacing_receipt(session, following):
    session.update_stage("email_otp", state="running")
    session.record_network(otp_record())
    session.record_network(otp_record(**following))
    info = session._classify_failure("_EmailSubmissionUnknown: request_unknown otp_request_unconfirmed")
    assert info["code"] == "email_submit_unconfirmed"


def test_confirmed_auth_progress_prevents_old_transport_from_becoming_final_cause(session):
    session.update_stage("email_otp", state="running")
    session.record_network(otp_record())
    session.update_stage("email_otp", state="success")
    session.update_stage("email_otp", state="running")
    info = session._classify_failure("_EmailSubmissionUnknown: request_unknown otp_request_unconfirmed")
    assert info["code"] == "email_submit_unconfirmed"


@pytest.mark.parametrize("changes", [
    {"failure": "net::ERR_CONNECTION_TIMED_OUT"},
    {"failure": "private net::ERR_TUNNEL_CONNECTION_FAILED"},
    {"failure": "TimeoutError"},
    {"url": "https://auth.openai.com.evil.test/api/accounts/email-otp/validate"},
    {"method": "GET"},
])
def test_only_exact_transport_failure_on_trusted_auth_endpoint_can_refine_receipt(session, changes):
    session.update_stage("email_otp", state="running")
    session.record_network(otp_record(**changes))
    info = session._classify_failure("_EmailSubmissionUnknown: request_unknown otp_request_unconfirmed")
    assert info["code"] == "email_submit_unconfirmed"


@pytest.mark.parametrize("reason,expected", [
    ("_PasswordTransitionTimeout: 创建密码页没有完成跳转", "password_result_unknown"),
    ("account_deactivated", "account.deactivated"),
    ("password_rejected", "password_rejected"),
    ("KeyError: 'schema 未定义字段: UNIT_FIELD'", "local_config_schema_mismatch"),
])
def test_transport_evidence_does_not_replace_specific_password_or_local_failure(session, reason, expected):
    session.update_stage("email_otp", state="running")
    session.record_network(otp_record())
    assert session._classify_failure(reason)["code"] == expected
