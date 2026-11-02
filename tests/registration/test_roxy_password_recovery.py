"""Roxy 密码恢复只接纳本轮明确配对的拒绝。"""
from types import SimpleNamespace

import pytest
from unittest.mock import Mock, patch

from core.auth.browser.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from core.registration import roxy


def _password_action():
    receipt = BrowserSubmissionReceipt(
        kind="resume_login", stage="login_password", endpoint_kind="password_submit", http_method="POST",
    )
    driver = SimpleNamespace(current_window_handle="CDwindow-current", _browser_submission_receipt=receipt)
    with patch("core.auth.browser.browser_submission.time.time", return_value=100.0):
        record_browser_submission_fact(driver, "dispatch_intent", receipt=receipt)
    record_browser_submission_fact(driver, "ui_dispatched", receipt=receipt)
    return driver, receipt, roxy._make_submission_observer(driver)


def _request(**changes):
    return {"target_id": "current", "request_id": "password-1", "endpoint_kind": "password_submit",
            "http_method": "POST", "started_wall_time": 100.1, **changes}


def _response(**changes):
    return _request(**{"response": True, "http_status": 401,
                       "auth_error": {"code": "password_reset_required"}, **changes})


def test_current_password_reset_rejection_preserves_bound_safe_evidence():
    driver, receipt, observe = _password_action()
    observe(_request())
    observe(_response())
    assert receipt.dispatch_target_id == "current"
    assert receipt.request_binding == receipt.response_binding == ("current", "password-1")
    assert receipt.auth_error == {"code": "password_reset_required", "type": "unknown", "category": "password_reset_required"}
    assert receipt.phase == "rejected"
    assert roxy._password_reset_required_for_current_submission(driver)


@pytest.mark.parametrize("changes", [
    {"target_id": "other"}, {"request_id": "previous"}, {"endpoint_kind": "otp_submit"},
    {"http_status": 403}, {"http_status": 400}, {"auth_error": {"code": "invalid_password"}},
])
def test_other_response_cannot_trigger_reset(changes):
    driver, _receipt, observe = _password_action()
    observe(_request())
    observe(_response(**changes))
    assert not roxy._password_reset_required_for_current_submission(driver)


@pytest.mark.parametrize("dispatched", [False, True])
def test_response_without_this_action_request_cannot_trigger_reset(dispatched):
    driver, receipt, observe = _password_action()
    if not dispatched:
        receipt.phase = "prepared"
    observe(_response())
    assert not roxy._password_reset_required_for_current_submission(driver)


def test_bound_password_request_cannot_be_replaced_by_later_request():
    driver, receipt, observe = _password_action()
    observe(_request())
    observe(_request(request_id="later"))
    observe(_response(request_id="later"))
    assert not roxy._password_reset_required_for_current_submission(driver)
    assert receipt.request_binding == ("current", "password-1")
    observe(_response())
    assert roxy._password_reset_required_for_current_submission(driver)


def test_password_get_request_cannot_authorize_later_post_response():
    driver, receipt, observe = _password_action()
    observe(_request(http_method="GET"))
    observe(_response())
    assert receipt.request_binding is None
    assert not roxy._password_reset_required_for_current_submission(driver)


@pytest.mark.parametrize("started", [None, 99.9, 0, True, "100.1", float("nan"), float("inf"), 1e100])
def test_password_request_without_this_dispatch_generation_cannot_trigger_recovery(started):
    driver, receipt, observe = _password_action()
    observe(_request(started_wall_time=started))
    observe(_response(started_wall_time=started))
    assert receipt.request_binding is None
    assert not roxy._password_reset_required_for_current_submission(driver)


@pytest.mark.parametrize("debug_enabled", [False, True])
def test_collector_passes_real_cdp_request_wall_time_with_debug_enabled_or_disabled(debug_enabled):
    from core.browser import traffic
    from core.registration import debug

    debug_session = SimpleNamespace(attach_roxy=Mock()) if debug_enabled else None
    opened = SimpleNamespace(profile_id="test-profile", debugger_address="127.0.0.1:9222", proxy_relay=None)
    with (
        patch.object(debug, "current_session", return_value=debug_session),
        patch.object(traffic, "_new_roxy_collector", return_value=SimpleNamespace(start=Mock())),
    ):
        capture = traffic.start_roxy_capture(opened)
        debug.attach_current_roxy(opened.debugger_address)
    observed = []
    capture.set_submission_observer(observed.append)
    collector = debug._RoxyTargetCollector(SimpleNamespace(session=capture.session), "current", "ws://test-only", "page")
    collector._handle({"method": "Network.requestWillBeSent", "params": {
        "requestId": "this-request", "timestamp": 1.0, "wallTime": 100.25, "type": "Fetch",
        "request": {"url": "https://auth.openai.com/api/accounts/password", "method": "POST"},
    }})
    assert observed[0]["started_wall_time"] == 100.25


def test_new_password_action_cannot_reuse_historical_reset_rejection():
    driver, _receipt, observe = _password_action()
    observe(_request())
    observe(_response())
    driver._browser_submission_receipt = BrowserSubmissionReceipt(
        kind="resume_login", stage="login_password", endpoint_kind="password_submit", phase="ui_dispatched",
    )
    assert not roxy._password_reset_required_for_current_submission(driver)


def test_new_password_action_binds_its_own_request_after_rejected_old_password():
    driver, _receipt, observe = _password_action()
    observe(_request())
    observe(_response())
    fresh = BrowserSubmissionReceipt(kind="resume_login", stage="login_password", endpoint_kind="password_submit")
    driver._browser_submission_receipt = fresh
    with patch("core.auth.browser.browser_submission.time.time", return_value=100.0):
        record_browser_submission_fact(driver, "dispatch_intent", receipt=fresh)
    observe(_request(request_id="new-password"))
    observe(_response(request_id="new-password", http_status=200, auth_error={}))
    assert fresh.request_binding == fresh.response_binding == ("current", "new-password")
    assert fresh.http_status == 200


def test_late_paired_password_response_adds_safe_metadata_without_reopening_confirmed_action():
    from core.codex.roxy.oauth import _candidate_login_confirmed

    driver, receipt, observe = _password_action()
    record_browser_submission_fact(driver, "confirmed", receipt=receipt, result="success")
    observe(_request())
    observe(_response(http_status=200, auth_error={}))
    assert receipt.phase == "confirmed"
    assert receipt.result == "success"
    assert receipt.http_status == 200
    assert _candidate_login_confirmed(driver, set())


@pytest.mark.parametrize("status,code,expected", [
    (401, "password_reset_required", True), (401, "invalid_password", False),
    (403, "password_reset_required", False),
])
def test_delayed_password_error_body_is_observed_without_submitting_again(status, code, expected):
    driver, receipt, observe = _password_action()
    clock = [100.0]
    receipt.dispatch_started_at = 100.0
    observe(_request())
    def tick(_seconds):
        clock[0] += 0.1
        observe(_response(http_status=status, auth_error={"code": code}))
    with patch.object(roxy.time, "monotonic", side_effect=lambda: clock[0]), patch.object(roxy.time, "sleep", side_effect=tick):
        assert roxy._wait_for_current_password_reset_required(driver) is expected
    assert clock[0] < 102.2


def test_password_error_body_wait_cannot_exceed_original_transition_budget():
    driver, receipt, _observe = _password_action()
    receipt.dispatch_started_at = 1.0
    with patch.object(roxy.time, "monotonic", return_value=1000.0), patch.object(roxy.time, "sleep") as sleep:
        assert not roxy._wait_for_current_password_reset_required(driver)
    sleep.assert_not_called()


def test_registration_owner_uses_operation_execution_in_its_own_namespace():
    from core import db
    from core.storage.operations import store as operations

    facts = {"attempt_id": 41, "run_id": 71, "execution_id": "registration-execution", "job_id": 31}
    with (
        patch.object(db, "get_account_by_email", return_value={"id": 19}),
        patch.object(operations, "get_registration_progress", return_value={31: {"operation_run_id": 81}}),
        patch.object(operations, "get_run", return_value={"id": 81, "execution_id": "job-uuid"}),
    ):
        owner = roxy._registration_password_recovery_owner("account@example.com", facts)
    assert owner == {
        "email": "account@example.com", "account_id": 19, "purpose": "registration",
        "operation_run_id": 81, "operation_execution_id": "job-uuid", "operation_lease_token": None,
        "attempt_id": 41, "registration_run_id": 71, "registration_execution_id": "registration-execution",
    }


@pytest.mark.parametrize("error", [
    roxy.PasswordPageError("password_page_error", "密码页明确要求恢复"),
    roxy._PasswordTransitionTimeout("密码提交后页面没有及时推进"),
])
def test_roxy_current_rejection_resets_once_then_continues_original_profile_flow(error):
    from tests.registration.test_registration_resume_session import RetainedWindowFlowTests

    flow = RetainedWindowFlowTests()
    session = SimpleNamespace(resume=Mock(return_value=False), checkpoint=None)
    with (
        flow.retained_context(page=roxy.PageState.PASSWORD_LOGIN) as (driver, mocks),
        patch.object(roxy, "_registration_password_recovery_session", return_value=session, create=True),
        patch("core.codex.roxy.oauth._reset_password_via_email") as reset,
        patch.object(roxy, "_registration_profile_form_ready", return_value=True),
    ):
        def rejected(*_args, **_kwargs):
            driver._browser_submission_receipt = BrowserSubmissionReceipt(
                kind="resume_login", stage="login_password", endpoint_kind="password_submit",
                http_method="POST", http_status=401, phase="rejected", dispatch_target_id="current",
                request_binding=("current", "this-run"), response_binding=("current", "this-run"),
                auth_error={"code": "password_reset_required"},
            )
            raise error

        def recovered(*_args, **_kwargs):
            session.checkpoint = SimpleNamespace(state="confirmed", password="updated-password")
            return "updated-password"

        mocks["_fill_password_page_if_present"].side_effect = rejected
        reset.side_effect = recovered
        result = flow.run_registration()
    assert result["success"], result.get("error")
    reset.assert_called_once()
    assert reset.call_args.kwargs["recovery"] is session
    assert reset.call_args.kwargs["allow_profile_handoff"] is True
    assert mocks["persist"].call_args.kwargs["extra"]["account_password"] == "updated-password"


def test_pending_recovery_confirms_original_candidate_before_retained_password_guard():
    from tests.registration.test_registration_resume_session import RetainedWindowFlowTests

    flow = RetainedWindowFlowTests()
    session = SimpleNamespace(resume=Mock(return_value=True), checkpoint=SimpleNamespace(state="unknown"))
    calls = []
    with (
        flow.retained_context(page=roxy.PageState.PROFILE) as (_driver, mocks),
        patch.object(roxy, "_registration_password_recovery_session", return_value=session),
        patch("core.codex.roxy.oauth._reset_password_via_email") as reset,
    ):
        def recovered(*_args, **_kwargs):
            calls.append("confirmed")
            session.checkpoint = SimpleNamespace(state="confirmed", password="same-pending-candidate")
            return "same-pending-candidate"
        def retained(*_args, **kwargs):
            calls.append("retained_guard")
            assert kwargs["existing_password"] == "same-pending-candidate"
            return SimpleNamespace(page_state=roxy.PageState.PROFILE, password="same-pending-candidate", pending_otp=None)
        reset.side_effect = recovered
        mocks["prepare_retained_resume"].side_effect = retained
        result = flow.run_registration()
    assert result["success"], result.get("error")
    assert calls == ["confirmed", "retained_guard"]
    mocks["_fill_password_page_if_present"].assert_not_called()
    assert mocks["persist"].call_args.kwargs["extra"]["account_password"] == "same-pending-candidate"


def test_pending_recovery_without_password_confirmation_preserves_original_identity():
    from tests.registration.test_registration_resume_session import RetainedWindowFlowTests

    flow = RetainedWindowFlowTests()
    session = SimpleNamespace(resume=Mock(return_value=True), checkpoint=SimpleNamespace(state="unknown"))
    with (
        flow.retained_context(page=roxy.PageState.PROFILE) as (_driver, mocks),
        patch.object(roxy, "_registration_password_recovery_session", return_value=session),
        patch("core.codex.roxy.oauth._reset_password_via_email", return_value="unconfirmed-candidate"),
    ):
        result = flow.run_registration()
    assert not result["success"]
    assert "password_recovery_unconfirmed" in result["error"]
    assert result["error_code"] == "password_recovery_unconfirmed"
    assert result["request_unknown"] is False
    mocks["prepare_retained_resume"].assert_not_called()
    mocks["persist"].assert_not_called()
    mocks["release"].assert_not_called()


def test_recovery_store_conflict_keeps_stable_cause_without_inventing_remote_unknown():
    from core.storage.accounts.password_recovery import PasswordRecoveryError
    from tests.registration.test_registration_resume_session import RetainedWindowFlowTests

    flow = RetainedWindowFlowTests()
    with (
        flow.retained_context(page=roxy.PageState.PROFILE) as (_driver, mocks),
        patch.object(roxy, "_registration_password_recovery_session", side_effect=PasswordRecoveryError("password_conflict")),
    ):
        result = flow.run_registration()
    assert not result["success"]
    assert result["cause_code"] == "password_recovery_password_conflict"
    assert result["error_code"] == "password_recovery_password_conflict"
    assert result["request_unknown"] is False
    mocks["release"].assert_not_called()


@pytest.mark.parametrize("page", [roxy.PageState.PROFILE, roxy.PageState.OTP_EMAIL])
def test_pending_recovery_without_retained_connection_keeps_recovered_page_and_new_mail_boundary(page):
    from tests.registration.test_registration_resume_session import RetainedWindowFlowTests

    flow = RetainedWindowFlowTests()
    session = SimpleNamespace(resume=Mock(return_value=True), checkpoint=SimpleNamespace(state="unknown"))
    with (
        flow.retained_context(page=page) as (driver, mocks),
        patch.object(roxy, "_registration_password_recovery_session", return_value=session),
        patch("core.codex.roxy.oauth._reset_password_via_email") as reset,
    ):
        mocks["take_failed_browser"].return_value = None
        def recovered(*_args, **_kwargs):
            driver._registration_otp_after_ts = 9999.5
            session.checkpoint = SimpleNamespace(state="confirmed", password="same-pending-candidate")
            return "same-pending-candidate"
        reset.side_effect = recovered
        mocks["prepare_retained_resume"].return_value = SimpleNamespace(
            page_state=page, password="same-pending-candidate", pending_otp=None,
        )
        result = flow.run_registration()
    assert result["success"], result.get("error")
    mocks["navigate"].assert_not_called()
    mocks["_submit_email_and_wait_next"].assert_not_called()
    mocks["_fill_password_page_if_present"].assert_not_called()
    assert mocks["prepare_retained_resume"].call_args.kwargs["otp_after_ts"] == 9999.5
    assert driver._registration_otp_after_ts == 9999.5
