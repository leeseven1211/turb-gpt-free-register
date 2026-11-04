"""Roxy 保存密码入口与注册密码阶段使用独立远端事实。"""
import inspect
from unittest.mock import patch

import pytest

from core.auth.browser import password_auth
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.browser.password_entry import PasswordEntryNavigationError
from core.registration import roxy
from tests.registration.test_registration_password_flow import _saved_password_refresh_flow
from tests.registration import test_registration_resume_session as resume_fixtures


def test_saved_password_initial_otp_opens_real_entry_and_keeps_checkpoints():
    assert "prefer_saved_password_entry" in inspect.signature(password_auth._fill_password_page_if_present).parameters
    prepared, submitted = [], []
    with _saved_password_refresh_flow(first_landing="otp", explicit_resume=False) as fixture:
        fixture.driver.state = "otp"
        def enter(*_args, **_kwargs):
            fixture.driver.state = "password"
            return "/log-in/password"
        with patch("core.auth.browser.password_entry.open_offered_password_entry", side_effect=enter) as entry:
            result = password_auth._fill_password_page_if_present(
                fixture.driver, "saved@example.test", existing_password="ValidPass123!", timeout=10,
                prefer_saved_password_entry=True,
                on_password_prepared=prepared.append, on_password_submitted=submitted.append,
            )
    assert result == "ValidPass123!"
    assert entry.call_count == 1
    assert (prepared, submitted, fixture.driver.typed) == ([result], [result], [result])
    assert fixture.driver._browser_submission_receipt.phase == "confirmed"


@pytest.mark.parametrize("phase,result", [("confirmed", "success"), ("unknown", "unknown"), ("ui_dispatched", "")])
def test_saved_password_after_submission_keeps_otp_without_opening_entry(phase, result):
    assert "prefer_saved_password_entry" in inspect.signature(password_auth._fill_password_page_if_present).parameters
    with _saved_password_refresh_flow(explicit_resume=False) as fixture:
        fixture.driver.state = "otp"
        fixture.driver._browser_submission_receipt = BrowserSubmissionReceipt(
            kind="password", stage="login_password", endpoint_kind="password_submit", http_method="POST",
            phase=phase, result=result,
        )
        with patch("core.auth.browser.password_entry.open_offered_password_entry") as entry:
            assert password_auth._fill_password_page_if_present(
                fixture.driver, "saved@example.test", existing_password="ValidPass123!",
                prefer_saved_password_entry=True, saved_password_entry_already_attempted=True,
            ) == "ValidPass123!"
    entry.assert_not_called()
    assert not fixture.driver.queues


@pytest.mark.parametrize("phase", ["confirmed", "unknown"])
def test_previous_auth_session_password_receipt_does_not_suppress_new_initial_otp_entry(phase):
    with _saved_password_refresh_flow(first_landing="otp", explicit_resume=False) as fixture:
        fixture.driver.state = "otp"
        old = BrowserSubmissionReceipt(
            kind="password", stage="login_password", endpoint_kind="password_submit", http_method="POST",
            phase=phase, result="success" if phase == "confirmed" else "unknown",
        )
        fixture.driver._browser_submission_receipt = old
        fixture.driver._browser_submission_receipts = [old]
        fixture.driver._registration_resume_password_attempted = True
        def enter(*_args, **_kwargs):
            fixture.driver.state = "password"
            return "/log-in/password"
        with patch("core.auth.browser.password_entry.open_offered_password_entry", side_effect=enter) as entry:
            result = password_auth._fill_password_page_if_present(
                fixture.driver, "saved@example.test", existing_password="ValidPass123!", timeout=10,
                prefer_saved_password_entry=True,
            )
    assert result == "ValidPass123!"
    entry.assert_called_once()
    assert fixture.driver.typed == [result]
    assert old.phase == phase


def test_local_roxy_retained_otp_without_password_fact_can_try_saved_entry():
    harness = resume_fixtures.RetainedWindowFlowTests()
    with harness.retained_context() as (_driver, mocks):
        mocks["_fill_password_page_if_present"].return_value = "unit-original-password"
        result = harness.run_registration()
    assert result["success"], result.get("error")
    assert mocks["_fill_password_page_if_present"].call_count == 1
    assert mocks["_fill_password_page_if_present"].call_args.kwargs["prefer_saved_password_entry"] is True


@pytest.mark.parametrize("phase", ["confirmed", "unknown", "ui_dispatched"])
def test_retained_otp_rechecks_real_password_entry_despite_old_attempt_submission(phase):
    harness = resume_fixtures.RetainedWindowFlowTests()
    with harness.retained_context() as (_driver, mocks):
        mocks["private"].return_value = {"password": "unit-original-password", "submission_facts": [{
            "submission_id": "same-attempt-confirmed", "stage": "password_create", "kind": "password",
            "endpoint_kind": "password_submit", "http_method": "POST", "phase": phase, "result": "success",
        }]}
        result = harness.run_registration()
    assert result["success"], result.get("error")
    mocks["_fill_password_page_if_present"].assert_called_once()
    assert mocks["persist"].call_args.kwargs["extra"]["account_password_state"] == "candidate"
    assert result["password_validated"] is False
    assert result["account_readiness"] == "incomplete"


def test_saved_entry_keeps_expired_resume_session_recovery_before_link_selection():
    with _saved_password_refresh_flow(first_landing="otp") as fixture:
        fixture.driver.state = "otp"
        def restart(*_args, **_kwargs):
            fixture.driver.state = "password"
            return True
        with (
            patch.object(password_auth, "_wait_email_otp_page_ready", return_value="session_expired") as ready,
            patch.object(password_auth, "_restart_expired_resume_auth", side_effect=restart) as restarted,
            patch("core.auth.browser.password_entry.open_offered_password_entry", return_value=None) as entry,
        ):
            result = password_auth._fill_password_page_if_present(
                fixture.driver, "saved@example.test", existing_password="ValidPass123!", timeout=10,
                prefer_saved_password_entry=True,
            )
    assert result == "ValidPass123!"
    ready.assert_called_once()
    restarted.assert_called_once()
    entry.assert_not_called()
    assert fixture.driver.typed == [result]


@pytest.mark.parametrize("stage", ["login_password", "password_create"])
@pytest.mark.parametrize("otp_failed", [False, True])
def test_registration_keeps_confirmed_password_evidence_when_downstream_otp_fails(stage, otp_failed):
    harness = resume_fixtures.RetainedWindowFlowTests()
    with harness.retained_context(page=roxy.PageState.PASSWORD_LOGIN) as (driver, mocks):
        def fill(*_args, **_kwargs):
            driver._browser_submission_receipt = BrowserSubmissionReceipt(
                kind="password", stage=stage, endpoint_kind="password_submit", http_method="POST",
                phase="confirmed", result="success",
            )
            return "unit-original-password"
        mocks["_fill_password_page_if_present"].side_effect = fill
        if otp_failed:
            mocks["_wait_email_otp_page_ready"].return_value = "ready"
            mocks["wait_for_otp"].side_effect = RuntimeError("email_otp_delivery_timeout: 模拟邮件未到达")
        result = harness.run_registration()
    assert result["success"] is not otp_failed
    events = [call.args for call in mocks["progress"].call_args_list if call.args[0] == "login_password"]
    assert events[-1][1] == "running"
    assert ("本次密码登录验证已通过" if stage == "login_password" else "本次创建请求已被接受") in events[-1][2]


def test_retained_driver_uses_current_registration_password_entry_policy():
    from core.codex.roxy.oauth import _uses_roxy_saved_password_entry

    harness = resume_fixtures.RetainedWindowFlowTests()
    with harness.retained_context() as (driver, _mocks):
        # 复用窗口不能继承上一种注册驱动的密码入口策略。
        driver._registration_local_roxy_password_entry = False
        result = harness.run_registration()
    assert result["success"], result.get("error")
    assert _uses_roxy_saved_password_entry(driver) is True


@pytest.mark.parametrize("error,code", [
    (PasswordEntryNavigationError("页面提供的密码入口未能确认导航"), "password_entry_navigation_failed"),
    (RuntimeError("profile_completion_required: 保存密码已提交，账号仍需补全资料"), "profile_completion_required"),
])
def test_registration_preserves_specific_password_entry_and_profile_failure_codes(error, code):
    harness = resume_fixtures.RetainedWindowFlowTests()
    with harness.retained_context(page=roxy.PageState.PASSWORD_LOGIN) as (_driver, mocks):
        mocks["_fill_password_page_if_present"].side_effect = error
        result = harness.run_registration()
    assert result["success"] is False
    assert result["error_code"] == code
    mocks["release"].assert_not_called()


def test_local_password_and_ui_dispatch_callback_do_not_imply_remote_password_success():
    harness = resume_fixtures.ResumeSessionFlowTests()
    with harness.run_context() as (driver, mocks):
        driver.execute_async_script.return_value = {"ok": True, "status": 401, "json_valid": True, "data": {}}
        mocks["navigate"].side_effect = None
        mocks["_submit_email_and_wait_next"].return_value = "otp"
        mocks["_has_access_token"].return_value = True
        mocks["_fetch_chatgpt_session"].return_value = {"accessToken": "unit-token", "user": {"email": "resume@example.test"}}
        def fill(*_args, **kwargs):
            kwargs["on_password_submitted"]("unit-original-password")
            return "unit-original-password"
        mocks["_fill_password_page_if_present"].side_effect = fill
        with patch("core.registration.checkpoints.save_protocol_password_checkpoint"):
            result = harness.run_registration()
    assert result["success"], result.get("error")
    password_events = [call.args for call in mocks["progress"].call_args_list if call.args[0] == "login_password"]
    assert not any(event[1] == "success" for event in password_events)
    assert mocks["persist"].call_args.kwargs["extra"]["account_password_state"] == "candidate"
    assert result["password_validated"] is False
    assert result["account_readiness"] == "incomplete"


def test_new_registration_chooses_real_create_entry_and_keeps_candidate_until_token():
    prepared = []
    with _saved_password_refresh_flow(signup=True, first_landing="otp", explicit_resume=False) as fixture:
        fixture.driver.state = "otp"
        def enter(*_args, **kwargs):
            assert kwargs["allow_login"] is False
            fixture.driver.state = "password"
            return "/create-account/password"
        with (
            patch("core.auth.browser.password_entry.open_offered_password_entry", side_effect=enter) as entry,
            patch.object(password_auth, "_registration_password", return_value="SyntheticCandidate!"),
        ):
            candidate = password_auth._fill_password_page_if_present(
                fixture.driver, "saved@example.test", existing_password=None,
                prefer_saved_password_entry=True, on_password_prepared=prepared.append, timeout=10,
            )
    assert candidate == "SyntheticCandidate!"
    assert prepared == [candidate]
    assert len(fixture.driver.queues) == 1
    entry.assert_called_once()
    assert fixture.driver._registration_password_creation_chain["password"] == candidate


def test_new_registration_without_real_password_entry_continues_otp():
    with _saved_password_refresh_flow(explicit_resume=False) as fixture:
        fixture.driver.state = "otp"
        with patch("core.auth.browser.password_entry.open_offered_password_entry", return_value=None) as entry:
            assert password_auth._fill_password_page_if_present(
                fixture.driver, "saved@example.test", prefer_saved_password_entry=True, timeout=10,
            ) is None
    entry.assert_called_once()
    assert not fixture.driver.queues


@pytest.mark.parametrize("same_chain", [False, True])
def test_only_live_creation_chain_can_confirm_candidate_after_matching_token(same_chain):
    harness = resume_fixtures.RetainedWindowFlowTests()
    with harness.retained_context() as (driver, mocks):
        receipt = BrowserSubmissionReceipt(
            kind="password", stage="password_create", endpoint_kind="password_submit", http_method="POST",
            phase="confirmed", result="success",
        )
        driver._browser_submission_receipts = [receipt]
        if same_chain:
            driver._registration_password_creation_chain = {
                "email": resume_fixtures.EMAIL, "password": "unit-original-password", "receipt": receipt,
            }
        result = harness.run_registration()
    assert result["success"] is True
    assert result["password_validated"] is same_chain
    assert result["postprocess_success"] is same_chain
    assert mocks["persist"].call_args.kwargs["extra"]["account_password_state"] == (
        "confirmed" if same_chain else "candidate"
    )
    assert all(call.kwargs["password_confirmed"] is same_chain for call in mocks["checkpoint"].call_args_list)


@pytest.mark.parametrize("network_confirmed", [False, True])
def test_current_password_verify_needs_paired_success_before_formal_persistence(network_confirmed):
    harness = resume_fixtures.RetainedWindowFlowTests()
    with harness.retained_context(page=roxy.PageState.PASSWORD_LOGIN) as (driver, mocks):
        def fill(*_args, **_kwargs):
            receipt = BrowserSubmissionReceipt(
                kind="resume_login", stage="login_password", endpoint_kind="password_submit", http_method="POST",
                phase="confirmed", result="success", http_status=200,
                dispatch_target_id="current-target", request_binding=("current-target", "current-request"),
                response_binding=("current-target", "current-request") if network_confirmed else None,
            )
            driver._browser_submission_receipts = [receipt]
            return "unit-original-password"
        mocks["_fill_password_page_if_present"].side_effect = fill
        result = harness.run_registration()
    assert result["password_validated"] is network_confirmed
    assert mocks["persist"].call_args.kwargs["extra"]["account_password_state"] == (
        "confirmed" if network_confirmed else "candidate"
    )


def test_fresh_login_drops_previous_creation_chain_before_otp_only_completion():
    harness = resume_fixtures.ResumeSessionFlowTests()
    with harness.run_context() as (driver, mocks):
        driver.current_url = "https://auth.openai.com/log-in"
        driver._registration_password_creation_chain = {
            "email": resume_fixtures.EMAIL, "password": "unit-original-password",
            "receipt": BrowserSubmissionReceipt(
                kind="password", stage="password_create", endpoint_kind="password_submit", http_method="POST",
                phase="confirmed", result="success",
            ),
        }
        mocks["navigate"].side_effect = None
        mocks["_submit_email_and_wait_next"].return_value = "otp"
        mocks["_fill_password_page_if_present"].return_value = "unit-original-password"
        mocks["_has_access_token"].return_value = True
        mocks["_fetch_chatgpt_session"].return_value = resume_fixtures.SESSION
        result = harness.run_registration()
    assert result["success"] is True
    assert driver._registration_password_creation_chain is None
    assert result["password_validated"] is False
    assert mocks["persist"].call_args.kwargs["extra"]["account_password_state"] == "candidate"
