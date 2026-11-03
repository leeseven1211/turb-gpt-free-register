"""Roxy 密码事实与邮箱、会话结果分别展示和持久化。"""
from unittest.mock import Mock

from core.accounts.liveness import service


def test_verified_password_is_success_even_when_email_challenge_failed():
    reporter = Mock()
    result = {"ok": False, "auth_facts": {
        "credential_check": "verified", "email_challenge": "failed", "session_acquired": False,
    }}
    service._report_roxy_password_evidence(reporter, result)
    stages = {call.args[0]: call for call in reporter.stage.call_args_list}
    assert stages["login_password"].args[1:3] == ("success", "账号密码验证通过")
    assert stages["email_otp"].args[1] == "failed"
    assert stages["token"].args[1] == "failed"


def test_accepted_creation_does_not_claim_login_password_verified():
    reporter = Mock()
    service._report_roxy_password_evidence(reporter, {"ok": False, "auth_facts": {
        "credential_check": "accepted", "email_challenge": "failed", "session_acquired": False,
    }})
    stage = reporter.stage.call_args_list[0]
    assert stage.args[1:3] == ("success", "账号密码设置已被接受")


def test_auth_facts_survive_secret_filter_without_storing_credentials():
    from core.storage.operations.store import _scrub

    result = _scrub({"auth_facts": {
        "credential_check": "verified", "email_challenge": "failed", "session_acquired": False,
    }, "password": "private", "access_token": "private"})
    assert result == {"auth_facts": {
        "credential_check": "verified", "email_challenge": "failed", "session_acquired": False,
    }}
