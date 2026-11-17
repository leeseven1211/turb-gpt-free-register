"""本地 Roxy 当前业务失败的同环境换线交接。"""
from contextlib import ExitStack
from types import SimpleNamespace
import hashlib
import time
from unittest.mock import Mock, patch

import pytest

from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.browser import email_otp
from core.auth.browser.email_otp import _EmailSubmissionUnknown
from core.registration import roxy, service
from core.registration.roxy.route_recovery import RoxyRouteRecoveryState
from tests.registration import test_registration_resume_session as resume
from tests.registration.test_roxy_native_signin_diagnostics import event


FACTS = {"job_id": 31, "attempt_id": 41, "run_id": 71, "execution_id": "current-route-run"}
FORM = "https://chatgpt.com/auth/login"


def _network_event(request_id, **kwargs):
    return event(request_id, **kwargs) | {"started_wall_time": time.time()}


def _run_failure(*, status=403, transport=None, callback=True, closed=True, created=False,
                 newer_success=False, other_target=False, helpers=None):
    flow = resume.ResumeSessionFlowTests()
    with flow.run_context(action="registration") as (driver, mocks), ExitStack() as stack:
        mocks["context"].return_value = dict(FACTS)
        mocks["run"].return_value = FACTS | {"action_type": "registration", "status": "running"}
        opened = mocks["opened"].return_value
        opened.created_by_run = created
        opened.account_bound = not created
        opened.proxy_route_retained = False
        opened.traffic_capture = Mock()
        driver.current_url = FORM
        driver.current_window_handle = "CDwindow-current-target"
        driver.execute_async_script.return_value = {"ok": True, "status": 200, "json_valid": True, "data": {}}
        client = mocks["client"].return_value
        client.close_profile.return_value = closed
        client.get_open_profile_connection.return_value = None if closed else {"pid": 123}
        stack.enter_context(patch.object(roxy, "_route_recovery_callback",
                                         return_value=Mock() if callback else None, create=True))
        stack.enter_context(patch("core.registration.debug.current_session", return_value=None))
        stack.enter_context(patch("core.browser.traffic.finish_roxy_capture"))

        def observe(record, phase):
            opened.traffic_capture.set_auth_diagnostic_observer.call_args.args[0](record, phase=phase)

        def navigate(_driver, url, **_kwargs):
            driver.current_url = url
            observe(_network_event("document", url=url, method="GET", started=10.0,
                                   resource_type="Document"), "request")
            observe(_network_event("document", url=url, method="GET", started=10.0,
                                   resource_type="Document", status=200), "response")

        def submit(*_args, **_kwargs):
            kwargs = {"target": "other-target"} if other_target else {}
            record = _network_event("email", **kwargs)
            observe(record, "request")
            observe(record | {"status": status, "failure": transport or ""}, "complete")
            if newer_success:
                observe(_network_event("success", started=12.0), "request")
                observe(_network_event("success", started=12.0, status=200), "response")
            raise _EmailSubmissionUnknown("email_submit_unconfirmed: 本次邮箱入口未确认")

        mocks["navigate"].side_effect = navigate
        mocks["_submit_email_and_wait_next"].side_effect = submit
        result = flow.run_registration(existing_password=None, registration_options={
            "password_enabled": True, "twofa_enabled": False,
            "codex_enabled": False, "plan_check_enabled": False,
        }, _browser_helpers=helpers)
    return result, mocks, client


def test_plain_current_403_hands_off_same_profile_without_cloudflare_permission():
    result, mocks, client = _run_failure(created=True)
    failure = result.get("route_failure")
    assert failure is not None, "普通业务 403 必须产生共同线路事实"
    assert failure.operation == "preauth"
    assert failure.http_status == 403
    assert failure.response_received is True
    assert result["route_recovery_ready"] is True
    assert result["route_recovery_profile_id"] == "unit-profile"
    assert result["route_recovery_state"].profile_id == "unit-profile"
    assert result["route_recovery_state"].facts == FACTS
    assert result["cf_proxy_rotation_ready"] is False
    client.close_profile.assert_called_once_with("unit-profile")
    client.delete_profile.assert_not_called()
    client.discard_profile.assert_not_called()
    mocks["pause"].assert_not_called()
    mocks["retain_default"].assert_not_called()


@pytest.mark.parametrize("failure", [
    "net::ERR_TIMED_OUT", "net::ERR_NAME_NOT_RESOLVED",
    "net::ERR_SSL_PROTOCOL_ERROR", "net::ERR_TUNNEL_CONNECTION_FAILED",
])
def test_current_auth_transport_uses_structured_failure(failure):
    result, _mocks, client = _run_failure(status=None, transport=failure)
    actual = result.get("route_failure")
    assert actual is not None, "当前认证传输失败必须交给共同协调器"
    assert actual.http_status is None
    assert actual.response_received is False
    assert actual.transport_kind
    assert result["route_recovery_ready"] is True
    client.close_profile.assert_called_once_with("unit-profile")


@pytest.mark.parametrize("kwargs", [{"newer_success": True}, {"other_target": True}, {"status": 429}])
def test_stale_other_target_and_rate_limit_do_not_switch_route(kwargs):
    result, _mocks, client = _run_failure(**kwargs)
    assert result.get("route_failure") is None
    assert result.get("route_recovery_ready", False) is False
    client.close_profile.assert_not_called()


def test_unconfirmed_close_retains_original_profile_and_does_not_offer_new_route():
    result, mocks, client = _run_failure(closed=False)
    assert result.get("route_failure") is not None
    assert result.get("route_recovery_ready", False) is False
    client.delete_profile.assert_not_called()
    mocks["pause"].assert_called_once()


def test_no_business_callback_preserves_existing_cleanup_and_reports_failure():
    result, _mocks, client = _run_failure(callback=False)
    assert result.get("route_failure") is not None
    assert result.get("route_recovery_ready", False) is False
    client.close_profile.assert_not_called()


def test_other_roxy_driver_keeps_its_existing_flow():
    helpers = SimpleNamespace(
        driver_name="roxy_oss", complete_profile_page=Mock(),
        submit_email_and_wait_next=Mock(side_effect=RuntimeError("原适配器失败")),
    )
    result, _mocks, client = _run_failure(helpers=helpers)
    assert result.get("route_failure") is None
    assert result.get("route_recovery_ready", False) is False
    client.close_profile.assert_not_called()


def test_initial_get_transport_can_handoff_without_a_cdp_traffic_capture():
    flow = resume.ResumeSessionFlowTests()
    with flow.run_context(action="registration") as (driver, mocks), ExitStack() as stack:
        mocks["context"].return_value = dict(FACTS)
        mocks["run"].return_value = FACTS | {"action_type": "registration", "status": "running"}
        driver.current_window_handle = "CDwindow-current-target"
        driver.current_url = FORM
        opened = mocks["opened"].return_value
        opened.traffic_capture = None
        opened.proxy_route_retained = False
        client = mocks["client"].return_value
        client.close_profile.return_value = True
        client.get_open_profile_connection.return_value = None
        mocks["navigate"].side_effect = TimeoutError("当前登录页导航连接超时")
        stack.enter_context(patch.object(roxy, "_route_recovery_callback", return_value=Mock()))
        stack.enter_context(patch("core.registration.debug.current_session", return_value=None))
        stack.enter_context(patch("core.browser.traffic.finish_roxy_capture"))
        result = flow.run_registration(existing_password=None)
    assert result.get("route_failure") is not None
    assert result["route_failure"].operation == "preauth"
    assert result["route_failure"].transport_kind == "timeout"
    assert result["route_recovery_ready"] is True
    client.close_profile.assert_called_once_with("unit-profile")


@pytest.mark.parametrize("close_mode", ["false", "exception", "still_open"])
def test_initial_get_close_failure_cannot_fall_back_to_unclosed_outer_route_retry(close_mode):
    flow = resume.ResumeSessionFlowTests()
    with flow.run_context(action="registration") as (driver, mocks), ExitStack() as stack:
        mocks["context"].return_value = dict(FACTS)
        mocks["run"].return_value = FACTS | {"action_type": "registration", "status": "running"}
        driver.current_window_handle = "CDwindow-current-target"
        driver.current_url = FORM
        opened = mocks["opened"].return_value
        opened.traffic_capture = None
        opened.proxy_route_retained = False
        client = mocks["client"].return_value
        client.close_profile.return_value = close_mode == "still_open"
        if close_mode == "exception":
            client.close_profile.side_effect = RuntimeError("Roxy 关闭接口失败")
        client.get_open_profile_connection.return_value = {"pid": 123}
        mocks["navigate"].side_effect = TimeoutError("net::ERR_CONNECTION_RESET")
        stack.enter_context(patch.object(roxy, "_route_recovery_callback", return_value=Mock()))
        stack.enter_context(patch("core.registration.debug.current_session", return_value=None))
        stack.enter_context(patch("core.browser.traffic.finish_roxy_capture"))
        result = flow.run_registration(existing_password=None)
    assert result["route_recovery_ready"] is False
    assert result["route_failure"].operation == "preauth"
    assert result.get("cause_code") == "registration_route_close_failed"
    with patch.object(service, "_registration_proxy_retry_limit", return_value=3):
        assert service._should_retry_registration_with_new_proxy(result, Mock(), 0) is False


def test_bound_password_receipt_without_response_is_preserved_for_same_identity_login():
    flow = resume.ResumeSessionFlowTests()
    receipt = BrowserSubmissionReceipt(
        kind="password", stage="password_create", phase="request_observed",
        endpoint_kind="password_submit", http_method="POST",
        dispatch_target_id="current-target", request_binding=("current-target", "password"),
    )
    with flow.run_context(action="registration") as (driver, mocks), ExitStack() as stack:
        mocks["context"].return_value = dict(FACTS)
        mocks["run"].return_value = FACTS | {"action_type": "registration", "status": "running"}
        driver.current_window_handle = "CDwindow-current-target"
        driver.current_url = "https://auth.openai.com/create-account/password"
        opened = mocks["opened"].return_value
        opened.traffic_capture = Mock()
        opened.proxy_route_retained = False
        client = mocks["client"].return_value
        client.close_profile.return_value = True
        client.get_open_profile_connection.return_value = None
        mocks["navigate"].side_effect = None
        mocks["_submit_email_and_wait_next"].return_value = "password"

        def password(*_args, **_kwargs):
            driver._browser_submission_receipt = receipt
            driver._browser_submission_receipts = [receipt]
            record = _network_event("password", url="https://auth.openai.com/api/accounts/user/register")
            observer = opened.traffic_capture.set_auth_diagnostic_observer.call_args.args[0]
            observer(record, phase="request")
            observer(record | {"failure": "net::ERR_CONNECTION_RESET"}, phase="complete")
            raise RuntimeError("password_submit_unknown: 密码请求未取得响应")

        mocks["_fill_password_page_if_present"].side_effect = password
        stack.enter_context(patch.object(roxy, "_route_recovery_callback", return_value=Mock(), create=True))
        stack.enter_context(patch("core.registration.debug.current_session", return_value=None))
        stack.enter_context(patch("core.browser.traffic.finish_roxy_capture"))
        result = flow.run_registration(existing_password=None)
    assert result.get("route_failure") is not None
    assert result["route_failure"].operation == "password_create"
    assert result["route_failure"].replay_safe is False
    assert result["route_recovery_ready"] is True
    assert result["route_recovery_state"].restart_identity_login is True
    assert receipt.phase == "request_observed"
    assert receipt.request_binding == ("current-target", "password")
    mocks["_fill_password_page_if_present"].assert_called_once()


def _reentry_state(*, operation="profile_submit", unknown=True):
    receipt = BrowserSubmissionReceipt(
        kind="profile" if operation == "profile_submit" else "password", stage="profile",
        endpoint_kind="profile_submit" if operation == "profile_submit" else "password_submit",
        phase="request_observed", http_method="POST",
    )
    state = RoxyRouteRecoveryState(
        "unit-profile", dict(FACTS), resume.EMAIL, password="unit-original-password",
        driver_state={"_browser_submission_receipt": receipt, "_browser_submission_receipts": [receipt]},
        otp_after_ts=1234.5, restart_identity_login=True,
    )
    state.failed_operation = operation
    state.has_unknown_identity_write = unknown
    return state, receipt


def test_reopened_unknown_profile_reads_matching_session_and_never_confirms_or_resubmits_old_write():
    state, receipt = _reentry_state()
    flow = resume.ResumeSessionFlowTests()
    with flow.run_context(action="registration") as (driver, mocks):
        mocks["context"].return_value = dict(FACTS)
        mocks["run"].return_value = FACTS | {"action_type": "registration", "status": "running"}
        with patch("core.registration.roxy.prepare_retained_resume") as prepare:
            result = flow.run_registration(registration_options={
                "password_enabled": True, "twofa_enabled": False,
                "codex_enabled": False, "plan_check_enabled": False, "_roxy_route_recovery": state,
            })
    assert result["success"] is True, result.get("error")
    assert receipt.phase == "request_observed"
    assert mocks["opened"].call_args.kwargs["preclosed_profile"] is True
    assert state.consumed is True
    prepare.assert_not_called()
    mocks["_complete_profile_page"].assert_not_called()
    mocks["_fill_password_page_if_present"].assert_not_called()
    mocks["take_default"].assert_not_called()
    mocks["attempt_default"].assert_not_called()


def test_prepared_candidate_preauth_reentry_creates_a_regular_email_receipt():
    candidate = "unit-original-password"
    prior = BrowserSubmissionReceipt(
        kind="email", stage="nextauth", endpoint_kind="nextauth_signin",
        phase="unknown", http_method="POST",
    )
    state = RoxyRouteRecoveryState(
        "unit-profile", dict(FACTS), resume.EMAIL, password=candidate,
        driver_state={"_browser_submission_receipt": prior, "_browser_submission_receipts": [prior]},
        preauth_restart=True, failed_operation="preauth",
    )
    authorization = FACTS | {
        "mode": "preauth", "candidate_digest": hashlib.sha256(candidate.encode()).hexdigest(),
        "prior_submission_ids": [prior.submission_id], "previous_route_no": 1, "route_attempt_no": 2,
    }
    flow = resume.ResumeSessionFlowTests()
    observed = []
    with flow.run_context(action="registration") as (driver, mocks), ExitStack() as stack:
        mocks["context"].return_value = dict(FACTS)
        mocks["run"].return_value = FACTS | {"action_type": "registration", "status": "running"}
        mocks["private"].return_value = {
            "password": candidate, "password_state": "prepared",
            "submission_facts": [prior.safe_fact()], "route_resume_authorization": authorization,
        }
        driver.current_url = FORM
        driver.current_window_handle = "CDwindow-current-target"
        driver.execute_async_script.return_value = {"ok": True, "status": 200, "json_valid": True, "data": {}}
        mocks["navigate"].side_effect = None

        def submission(_driver, email, **_kwargs):
            return email_otp._submit_email_form_stable(_driver, email)

        def dispatched(_driver, phase, *, receipt=None, **_changes):
            observed.append(receipt.safe_fact(phase=phase))
            raise _EmailSubmissionUnknown("本次邮箱派发已到存储边界")

        mocks["_submit_email_and_wait_next"].side_effect = submission
        stack.enter_context(patch.object(email_otp, "_email_ui_submission_state", return_value=None))
        stack.enter_context(patch.object(email_otp, "log_submission_diagnostics"))
        stack.enter_context(patch.object(email_otp, "record_browser_submission_fact", side_effect=dispatched))
        result = flow.run_registration(registration_options={
            "password_enabled": True, "twofa_enabled": False, "codex_enabled": False,
            "plan_check_enabled": False, "_roxy_route_recovery": state,
        })
    assert result["success"] is False
    assert len(observed) == 1
    assert observed[0]["kind"] == "email"
    assert driver._registration_resume_login is False
    assert state.password == candidate
    assert prior.phase == "unknown"


@pytest.mark.parametrize("operation", ["password_create", "profile_submit", "callback"])
def test_reentry_starts_new_identity_login_without_replaying_old_callback_or_creation(operation):
    state, receipt = _reentry_state(operation=operation)
    flow = resume.ResumeSessionFlowTests()
    with flow.run_context(action="registration") as (driver, mocks):
        mocks["context"].return_value = dict(FACTS)
        mocks["run"].return_value = FACTS | {"action_type": "registration", "status": "running"}
        driver.current_url = (
            "https://chatgpt.com/api/auth/callback/openai?code=old-private-code"
            if operation == "callback" else "https://auth.openai.com/about-you"
        )
        driver.execute_async_script.return_value = {"ok": True, "status": 200, "json_valid": True, "data": {}}
        with patch("core.registration.retained_resume._email_otp_page_state", return_value={
            "url": driver.current_url, "text": resume.EMAIL,
            "inputs": [{"name": "name", "type": "text"}, {"name": "age", "type": "number"}],
        }), patch("core.registration.roxy.prepare_retained_resume") as prepare:
            result = flow.run_registration(registration_options={
                "password_enabled": True, "twofa_enabled": False,
                "codex_enabled": False, "plan_check_enabled": False, "_roxy_route_recovery": state,
            })
    assert result["success"] is False
    mocks["navigate"].assert_called_once()
    assert mocks["navigate"].call_args.args[1] == FORM
    assert driver._registration_resume_login is True
    assert receipt.phase == "request_observed"
    prepare.assert_not_called()


def test_unknown_password_recovery_never_submits_a_new_create_password_form():
    state, receipt = _reentry_state(operation="password_create")
    flow = resume.ResumeSessionFlowTests()
    with flow.run_context(action="registration") as (driver, mocks):
        mocks["context"].return_value = dict(FACTS)
        mocks["run"].return_value = FACTS | {"action_type": "registration", "status": "running"}
        driver.current_url = "https://auth.openai.com/create-account/password"
        mocks["navigate"].side_effect = None
        mocks["_submit_email_and_wait_next"].return_value = "password"

        def prepare_new_creation(_driver, _email, **kwargs):
            driver._browser_submission_receipt = BrowserSubmissionReceipt(
                kind="resume_login", stage="password_create", endpoint_kind="password_submit",
            )
            kwargs["on_password_prepared"]("unit-original-password")
            raise AssertionError("未知创建不可走到新密码派发")

        mocks["_fill_password_page_if_present"].side_effect = prepare_new_creation
        with patch("core.registration.retained_resume._email_otp_page_state", return_value={
            "url": driver.current_url, "text": resume.EMAIL,
            "inputs": [{"type": "password", "autocomplete": "new-password"}],
        }), patch("core.registration.checkpoints.save_protocol_password_checkpoint") as checkpoint:
            result = flow.run_registration(registration_options={
                "password_enabled": True, "twofa_enabled": False, "codex_enabled": False,
                "plan_check_enabled": False, "_roxy_route_recovery": state,
            })
    assert result["success"] is False
    assert "route_password_create_not_replayable" in result["error"]
    assert receipt.phase == "request_observed"
    checkpoint.assert_not_called()


def test_unknown_profile_recovery_requires_session_instead_of_a_second_create():
    state, receipt = _reentry_state(operation="profile_submit")
    flow = resume.ResumeSessionFlowTests()
    with flow.run_context(action="registration") as (driver, mocks):
        mocks["context"].return_value = dict(FACTS)
        mocks["run"].return_value = FACTS | {"action_type": "registration", "status": "running"}
        driver.current_url = "https://auth.openai.com/about-you"
        mocks["navigate"].side_effect = None
        mocks["_submit_email_and_wait_next"].return_value = "login_password"
        mocks["_fill_password_page_if_present"].return_value = "unit-original-password"
        mocks["_has_access_token"].return_value = True
        driver.execute_async_script.return_value = {"ok": True, "status": 200, "json_valid": True, "data": {}}
        with patch("core.registration.retained_resume._email_otp_page_state", return_value={
            "url": driver.current_url, "text": resume.EMAIL,
            "inputs": [{"name": "name", "type": "text"}, {"name": "age", "type": "number"}],
        }), patch.object(roxy, "_registration_profile_form_ready", return_value=False):
            result = flow.run_registration(registration_options={
                "password_enabled": True, "twofa_enabled": False, "codex_enabled": False,
                "plan_check_enabled": False, "_roxy_route_recovery": state,
            })
    assert result["success"] is False
    assert "route_profile_result_unconfirmed" in result["error"]
    assert receipt.phase == "request_observed"
    mocks["_complete_profile_page"].assert_not_called()
