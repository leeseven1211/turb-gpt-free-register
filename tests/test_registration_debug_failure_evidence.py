"""失败现场只使用本次未恢复的认证证据，不让单条网络事件改写任务主因。"""
from unittest.mock import patch

import pytest

from core import registration_debug as debug


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
