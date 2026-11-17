"""换线控制只消费当前动作事实，进程内恢复身份不得漂移。"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.registration import roxy
from core.registration.roxy import route_recovery as roxy_routes
from core.registration.roxy.route_recovery import (
    RoxyRouteFailureObserver, RoxyRouteFailureSignal, RoxyRouteRecoveryState,
    make_recovery_state, validated_recovery_state,
)
from core.registration.route_recovery import RegistrationRouteFailure, registration_route_recovery
from tests.registration.test_roxy_route_recovery import FACTS
from tests.registration.test_registration_resume_session import EMAIL, session_driver


def _record(request="current", *, url="https://chatgpt.com/api/auth/csrf", method="GET",
            target="target", wall=100.0, status=None, resource="Fetch", redirect=0):
    return {"request_id": request, "target_id": target, "url": url, "method": method,
            "started_wall_time": wall, "resource_type": resource, "status": status,
            "redirect_index": redirect}


def _observer(stage="preauth"):
    driver = SimpleNamespace(current_window_handle="CDwindow-target", current_url="https://chatgpt.com/auth/login")
    clock = [100.0]
    observer = RoxyRouteFailureObserver(driver, wall_clock=lambda: clock[0])
    observer.begin_stage(driver, stage)
    return driver, observer, clock


@pytest.mark.parametrize("stage,url,method,operation", [
    ("preauth", "https://chatgpt.com/api/auth/csrf", "GET", "preauth"),
    ("preauth", "https://auth.openai.com/api/accounts/authorize", "POST", "email_submit"),
    ("password", "https://auth.openai.com/api/accounts/user/register", "POST", "password_create"),
    ("password", "https://auth.openai.com/api/accounts/password/verify", "POST", "password_verify"),
    ("otp", "https://auth.openai.com/api/accounts/email-otp/send", "POST", "otp_send"),
    ("otp", "https://auth.openai.com/api/accounts/email-otp/validate", "POST", "otp_validate"),
    ("profile", "https://auth.openai.com/api/accounts/create_account", "POST", "profile_submit"),
    ("session", "https://chatgpt.com/api/auth/session", "GET", "session"),
    ("session", "https://chatgpt.com/api/auth/callback/openai?code=private", "GET", "callback"),
])
def test_each_active_registration_stage_reports_its_current_403(stage, url, method, operation):
    driver, observer, _clock = _observer(stage)
    record = _record(url=url, method=method)
    observer.observe_network(record, phase="request")
    observer.observe_network(record | {"status": 403}, phase="response")
    failure = observer.failure(driver)
    assert failure.operation == operation
    assert failure.http_status == 403
    assert "private" not in repr(failure)
    if operation == "callback":
        assert failure.replay_safe is False


@pytest.mark.parametrize("change", [
    {"wall": 99.0}, {"target": "old-target"}, {"resource": "Image"},
    {"url": "https://mail.example.test/api/messages"},
    {"url": "https://auth.openai.com/awe/api/v2/rum", "method": "POST"},
    {"url": "https://chatgpt.com/assets/denied.js"},
])
def test_historical_or_auxiliary_request_cannot_supply_current_failure(change):
    driver, observer, _clock = _observer()
    record = _record(**change)
    observer.observe_network(record, phase="request")
    observer.observe_network(record | {"status": 403}, phase="complete")
    assert observer.failure(driver) is None


def test_a_response_without_its_current_request_or_wrong_redirect_is_ignored():
    driver, observer, _clock = _observer()
    observer.observe_network(_record(status=403), phase="response")
    assert observer.failure(driver) is None
    observer.observe_network(_record(), phase="request")
    observer.observe_network(_record(status=403, redirect=1), phase="response")
    assert observer.failure(driver) is None


def test_later_pending_request_new_document_and_new_stage_revoke_failure():
    for revoke in ("pending", "document", "stage"):
        driver, observer, clock = _observer()
        observer.observe_network(_record(), phase="request")
        observer.observe_network(_record(status=403), phase="response")
        assert observer.failure(driver) is not None
        if revoke == "stage":
            clock[0] = 101.0
            observer.begin_stage(driver, "password")
        else:
            observer.observe_network(_record("next", resource="Document" if revoke == "document" else "Fetch"),
                                     phase="request")
        observer.observe_network(_record(status=403), phase="complete")
        assert observer.failure(driver) is None


def test_incomplete_extra_info_cannot_erase_an_already_observed_403():
    driver, observer, _clock = _observer()
    observer.observe_network(_record(), phase="request")
    observer.observe_network(_record(status=403), phase="response")
    observer.observe_network(_record() | {"response_headers": {}}, phase="complete")
    assert observer.failure(driver).http_status == 403


def test_diagnostic_observer_failure_does_not_disable_route_control():
    driver, _unused, _clock = _observer()
    observer = RoxyRouteFailureObserver(
        driver, diagnostic_observer=Mock(side_effect=RuntimeError("只读诊断存储失败")),
        wall_clock=lambda: 100.0,
    )
    observer.begin_stage(driver, "preauth")
    observer.observe_network(_record(), phase="request")
    observer.observe_network(_record(status=403), phase="response")
    assert observer.failure(driver).http_status == 403


def test_registration_checkpoint_stops_old_route_before_the_next_browser_action():
    driver, observer, _clock = _observer()
    driver._registration_route_observer = observer
    observer.observe_network(_record(), phase="request")
    observer.observe_network(_record(status=403), phase="response")
    with registration_route_recovery(Mock()), patch("core.registration.service.is_stop_requested", return_value=False):
        with pytest.raises(RoxyRouteFailureSignal):
            roxy._has_access_token(driver)


def test_synchronous_session_403_is_current_evidence_even_without_cdp_delivery():
    driver = session_driver({"ok": True, "status": 403, "json_valid": True, "data": {}})
    driver.current_window_handle = "CDwindow-target"
    driver._registration_route_observer = RoxyRouteFailureObserver(driver)
    with registration_route_recovery(Mock()), pytest.raises(RoxyRouteFailureSignal) as raised:
        roxy._read_registration_resume_session(driver, EMAIL)
    assert raised.value.failure.operation == "session"
    assert raised.value.failure.http_status == 403


def test_synchronous_session_transport_records_the_actual_read_before_unknown_wrap():
    driver = session_driver()
    driver.current_window_handle = "CDwindow-target"
    driver.execute_async_script.side_effect = TimeoutError("本次 Session 读取超时")
    observer = RoxyRouteFailureObserver(driver)
    driver._registration_route_observer = observer
    with registration_route_recovery(Mock()), patch.object(roxy, "_check_manual_stop"):
        with pytest.raises(RuntimeError, match="resume_session_probe_incomplete"):
            roxy._read_registration_resume_session(driver, EMAIL)
    assert observer.failure(driver) is not None
    assert observer.failure(driver).operation == "session"
    assert observer.failure(driver).transport_kind == "timeout"


def test_current_bound_403_closes_only_that_refused_receipt_and_preserves_prior_unknown():
    receipt = BrowserSubmissionReceipt(
        kind="email", stage="submit_email", endpoint_kind="email_submit",
        phase="response_observed", http_method="POST", http_status=403,
        request_binding=("target", "current"), response_binding=("target", "current"),
    )
    previous = BrowserSubmissionReceipt(
        kind="password", stage="password_create", endpoint_kind="password_submit", phase="unknown",
    )
    driver = SimpleNamespace(_browser_submission_receipt=receipt, _browser_submission_receipts=[previous, receipt])
    refuse = getattr(roxy_routes, "record_current_refusal", lambda *_args: False)
    changed = refuse(driver, (RegistrationRouteFailure("email_submit", http_status=403, response_received=True),
                              ("target", "current", 0)))
    assert changed is True
    assert receipt.phase == "rejected"
    assert receipt.http_status == 403
    assert previous.phase == "unknown"


def test_confirmed_historical_write_does_not_force_unknown_identity_recovery():
    driver = SimpleNamespace()
    facts = [
        {"submission_id": "old", "endpoint_kind": "password_submit", "phase": "request_observed"},
        {"submission_id": "old", "endpoint_kind": "password_submit", "phase": "confirmed"},
    ]
    with patch("core.storage.registration.get_private_resume_context", return_value={
        "password": "original-candidate", "submission_facts": facts,
    }):
        state = make_recovery_state(driver, SimpleNamespace(profile_id="original"), email="unit@example.test",
                                    facts=FACTS, failure=RegistrationRouteFailure("preauth", http_status=403))
    assert state.restart_identity_login is False
    assert state.preauth_restart is True


def test_unknown_profile_keeps_receipts_candidate_and_otp_time_without_confirming_the_write():
    receipt = BrowserSubmissionReceipt(kind="profile", stage="profile", endpoint_kind="profile_submit",
                                       phase="request_observed", http_method="POST")
    driver = SimpleNamespace(_browser_submission_receipt=receipt, _browser_submission_receipts=[receipt],
                             _registration_otp_after_ts=1234.5)
    with patch("core.storage.registration.get_private_resume_context", return_value={
        "password": "original-candidate", "submission_facts": [receipt.safe_fact()],
    }):
        state = make_recovery_state(driver, SimpleNamespace(profile_id="original"), email="unit@example.test",
                                    facts=FACTS, failure=RegistrationRouteFailure("profile_submit",
                                                                                transport_kind="timeout"))
    restored = SimpleNamespace()
    state.restore(restored)
    assert state.restart_identity_login is True
    assert restored._browser_submission_receipt is receipt
    assert restored._registration_otp_after_ts == 1234.5
    assert state.password == "original-candidate"
    assert receipt.phase == "request_observed"


def test_route_state_checks_live_candidate_before_new_login():
    state = RoxyRouteRecoveryState("original", dict(FACTS), "unit@example.test", password="original-candidate")
    with patch("core.storage.registration.get_run", return_value=FACTS | {
        "action_type": "registration", "status": "running",
    }), patch("core.storage.registration.get_private_resume_context", return_value={"password": "different-candidate"}):
        with pytest.raises(RuntimeError, match="候选"):
            validated_recovery_state(state, facts=FACTS, profile_id="original", email="unit@example.test")


def test_managed_cli_recovery_keeps_the_same_run_without_requiring_a_web_job():
    facts = FACTS | {"job_id": None}
    state = RoxyRouteRecoveryState("original", dict(facts), "unit@example.test", password="candidate")
    with patch("core.storage.registration.get_run", return_value=facts | {
        "action_type": "registration", "status": "running",
    }), patch("core.storage.registration.get_private_resume_context", return_value={"password": "candidate"}):
        assert validated_recovery_state(
            state, facts=facts, profile_id="original", email="unit@example.test",
        ) is state
    assert state.consumed is True


@pytest.mark.parametrize("change", [
    {"facts": FACTS | {"execution_id": "different"}}, {"email": "other@example.test"},
    {"profile_id": "other"}, {"consumed": True},
])
def test_route_state_cannot_cross_execution_email_profile_or_repeat_consumption(change):
    state = RoxyRouteRecoveryState("original", dict(FACTS), "unit@example.test")
    for name, value in change.items():
        setattr(state, name, value)
    with pytest.raises(RuntimeError, match="原 Run"):
        validated_recovery_state(state, facts=FACTS, profile_id="original", email="unit@example.test")
