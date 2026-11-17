"""注册内 2FA 换线只续接失败动作，保留核心账号和密钥检查点。"""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch
import time

import pytest

from core.registration import roxy
from core.registration.route_recovery import RegistrationRouteFailure, registration_route_recovery
from core.registration.roxy.route_recovery import RoxyRouteFailureSignal
from tests.registration import test_registration_resume_session as resume
from tests.registration.test_roxy_route_recovery import FACTS, _network_event


def _run_twofa_failure(*, status=403, closed=True, no_new_lease=False, operation="twofa_activate",
                       protocol=False, unknown=False, plan_check=False):
    flow = resume.ResumeSessionFlowTests()
    callback = Mock(return_value=None if no_new_lease else SimpleNamespace(proxy_url="http://next.example.test:8080"))
    events = []
    with flow.run_context() as (driver, mocks), ExitStack() as stack:
        mocks["context"].return_value = dict(FACTS)
        mocks["run"].return_value = FACTS | {"action_type": "registration_resume", "status": "running"}
        if plan_check:
            mocks["plan_read"].return_value = {"ok": True}
        driver.current_window_handle = "CDwindow-current-target"
        opened = mocks["opened"].return_value
        opened.proxy_route_retained = False
        capture = Mock()
        opened.traffic_capture = capture
        client = mocks["client"].return_value
        client.close_profile.side_effect = lambda _profile: events.append("close") or closed
        client.get_open_profile_connection.return_value = None if closed else {"pid": 123}
        callback.side_effect = lambda *_args: events.append("acquire") or (
            None if no_new_lease else SimpleNamespace(proxy_url="http://next.example.test:8080")
        )
        next_driver = resume.session_driver()
        next_driver.current_window_handle = "CDwindow-new-target"
        next_driver.current_url = "https://chatgpt.com/#settings/Security"
        opened_new = SimpleNamespace(
            profile_id="unit-profile", debugger_address="127.0.0.1:9223", created_by_run=False,
            account_bound=True, proxy_route_retained=False, raw={}, traffic_capture=Mock(),
        )
        mocks["opened"].side_effect = [opened, opened_new]
        mocks["driver"].side_effect = [driver, next_driver]
        stack.enter_context(patch("core.browser.traffic.finish_roxy_capture",
                                  side_effect=lambda *_args: events.append("finish")))
        stack.enter_context(patch("core.registration.debug.current_session", return_value=None))
        stack.enter_context(patch.object(roxy, "_wait_registration_homepage", return_value={"ready": True}))
        stack.enter_context(patch("core.auth.browser.mfa_auth._probe_existing_roxy_totp", return_value={
            "confirmed": True, "reason": "enabled",
        }))
        calls = []

        def browser_twofa(current_driver, _email, **kwargs):
            calls.append((current_driver, kwargs))
            events.append("twofa")
            if len(calls) > 1 or protocol:
                return "ORIGINALSECRET"
            if operation == "twofa_activate":
                kwargs["on_secret"]("ORIGINALSECRET")
            url = "https://chatgpt.com/backend-api/accounts/mfa/" + (
                "activate" if operation == "twofa_activate" else "enroll"
            )
            record = _network_event("mfa", url=url)
            observer = capture.set_auth_diagnostic_observer.call_args.args[0]
            observer(record, phase="request")
            observer(record | {"status": None if unknown else status,
                               "failure": "net::ERR_CONNECTION_RESET" if unknown else ""}, phase="complete")
            raise RoxyRouteFailureSignal(RegistrationRouteFailure(
                operation, http_status=None if unknown else status,
                transport_kind="connection" if unknown else "", response_received=not unknown,
            ))

        mocks["twofa"].side_effect = browser_twofa
        mocks["twofa_driver"].return_value = "protocol" if protocol else "browser"
        if protocol:
            base_session = SimpleNamespace(
                post=Mock(return_value=SimpleNamespace(status_code=403)), close=Mock(),
            )
            mocks["base_session"] = base_session
            stack.enter_context(patch.object(roxy, "BrowserSession", return_value=base_session))
            stack.enter_context(patch.object(roxy, "setup_2fa_protocol", side_effect=lambda session, _token, **_kwargs:
                                             session.post("https://chatgpt.com/backend-api/accounts/mfa/enroll")))
        with registration_route_recovery(callback):
            result = flow.run_registration(registration_options={
                "password_enabled": True, "twofa_enabled": True,
                "codex_enabled": False, "plan_check_enabled": plan_check,
            })
    return result, mocks, callback, calls, client, events


@pytest.mark.parametrize("operation,unknown", [("twofa_enroll", False)])
def test_browser_twofa_switches_same_profile_without_repeating_saved_registration(operation, unknown):
    result, mocks, callback, calls, client, events = _run_twofa_failure(operation=operation, unknown=unknown)
    assert result["success"] is True
    assert result["twofa"]["ok"] is True, result["twofa"]
    assert len(calls) == (1 if operation == "twofa_activate" else 2)
    if operation == "twofa_activate":
        assert result["totp_secret"] == "ORIGINALSECRET"
    else:
        assert calls[0][0] is not calls[1][0]
    assert callback.call_count == 1
    assert callback.call_args.args[0].operation == operation
    assert callback.call_args.args[1] == "http://pool.example:8080"
    assert mocks["opened"].call_args.kwargs["preclosed_profile"] is True
    assert mocks["opened"].call_args.args[1] == "http://next.example.test:8080"
    assert events.index("close") < events.index("acquire")
    client.close_profile.assert_called_once_with("unit-profile")
    mocks["persist"].assert_called_once()
    mocks["_submit_email_and_wait_next"].assert_not_called()
    mocks["_complete_profile_page"].assert_not_called()
    mocks["codex"].assert_not_called()


@pytest.mark.parametrize("unknown", [False, True])
def test_new_route_enabled_does_not_confirm_the_pending_secret(unknown):
    result, mocks, callback, calls, client, _events = _run_twofa_failure(unknown=unknown)
    assert result["success"] is True
    assert result["twofa"]["ok"] is False
    assert "enabled_candidate_unverified" in result["twofa"]["message"]
    assert result["totp_secret"] == "ORIGINALSECRET"
    assert len(calls) == 1
    callback.assert_called_once()
    client.close_profile.assert_called_once_with("unit-profile")
    mocks["persist"].assert_called_once()


def test_recovered_activation_requires_readonly_remote_proof_before_any_new_enrollment():
    from core.registration.roxy import route_recovery as routes

    run = getattr(routes, "continue_browser_twofa", None)
    assert callable(run), "需要原密钥专用恢复边界"
    driver = SimpleNamespace()
    action = Mock(side_effect=AssertionError("激活未知不能重新开通"))
    with patch("core.auth.browser.mfa_auth._probe_existing_roxy_totp", return_value={
        "confirmed": False, "reason": "session_http",
    }), pytest.raises(RuntimeError, match="mfa_route_state_unconfirmed"):
        run(driver, resume.EMAIL, failure=RegistrationRouteFailure(
            "twofa_activate", transport_kind="connection",
        ), existing_secret="ORIGINALSECRET", action=action, on_secret=Mock(), check_stop=Mock())
    action.assert_not_called()


def test_unknown_activation_can_only_use_the_visible_original_enrollment_secret():
    from core.registration.roxy import route_recovery as routes

    run = getattr(routes, "continue_browser_twofa", None)
    assert callable(run), "需要原密钥专用恢复边界"
    action = Mock(side_effect=AssertionError("激活未知不能重新开通"))
    with patch("core.auth.browser.mfa_auth._probe_existing_roxy_totp", return_value={
        "confirmed": False, "reason": "mfa_not_enabled",
    }), patch("core.auth.browser.mfa_auth._detect_mfa_enrollment_step",
              return_value=("totp", object())), patch(
        "core.auth.browser.mfa_auth._read_totp_secret_from_dialog", return_value="DIFFERENTSECRET",
    ), pytest.raises(RuntimeError, match="mfa_route_enrollment_changed"):
        run(SimpleNamespace(), resume.EMAIL, failure=RegistrationRouteFailure(
            "twofa_activate", transport_kind="connection",
        ), existing_secret="ORIGINALSECRET", action=action, on_secret=Mock(), check_stop=Mock())
    action.assert_not_called()


def test_registration_protocol_twofa_reports_current_403_before_browser_fallback():
    from core.registration.roxy import route_recovery as routes

    wrap = getattr(routes, "RegistrationTwofaSession", None)
    assert callable(wrap), "协议2FA需要局部观察适配"
    driver = SimpleNamespace(current_window_handle="CDwindow-target")
    observer = routes.RoxyRouteFailureObserver(driver, wall_clock=lambda: time.time())
    observer.begin_stage(driver, "twofa")
    driver._registration_route_observer = observer
    original = SimpleNamespace(
        post=Mock(return_value=SimpleNamespace(status_code=403)),
        device_id="original-device", browser_profile={"timezone": "Asia/Tokyo"},
    )
    session = wrap(original, driver_getter=lambda: driver)
    with pytest.raises(RoxyRouteFailureSignal):
        session.post("https://chatgpt.com/backend-api/accounts/mfa/enroll", data="same-body")
    assert session.device_id == "original-device"
    assert session.browser_profile is original.browser_profile
    assert observer.failure(driver).operation == "twofa_enroll"
    original.post.assert_called_once_with("https://chatgpt.com/backend-api/accounts/mfa/enroll", data="same-body")


def test_registration_protocol_activate_transport_does_not_become_safe_replay():
    from core.registration.roxy import route_recovery as routes

    wrap = getattr(routes, "RegistrationTwofaSession", None)
    assert callable(wrap), "协议2FA需要局部观察适配"
    driver = SimpleNamespace(current_window_handle="CDwindow-target")
    observer = routes.RoxyRouteFailureObserver(driver)
    observer.begin_stage(driver, "twofa")
    driver._registration_route_observer = observer
    original = SimpleNamespace(post=Mock(side_effect=TimeoutError("当前激活请求传输超时")))
    with pytest.raises(RoxyRouteFailureSignal) as raised:
        wrap(original, driver_getter=lambda: driver).post(
            "https://chatgpt.com/backend-api/accounts/mfa/activate",
        )
    assert raised.value.failure.operation == "twofa_activate"
    assert raised.value.failure.replay_safe is False
    assert raised.value.failure.response_received is False


@pytest.mark.parametrize("operation", ["enroll", "activate"])
def test_real_protocol_twofa_retry_cannot_resend_unknown_post_on_old_route(operation):
    from core.accounts import export
    from core.registration.roxy import route_recovery as routes

    driver = SimpleNamespace(current_window_handle="CDwindow-target")
    observer = routes.RoxyRouteFailureObserver(driver)
    observer.begin_stage(driver, "twofa")
    driver._registration_route_observer = observer
    original = SimpleNamespace(
        post=Mock(side_effect=TimeoutError("当前 MFA 写入传输超时")),
        get_chatgpt_headers=lambda **_kwargs: {}, device_id="original-device",
        navigator_language=lambda: "en-US", reset_circuit_breaker=Mock(),
    )
    session = routes.RegistrationTwofaSession(original, driver_getter=lambda: driver)
    with patch.object(export.time, "sleep"):
        with pytest.raises((RoxyRouteFailureSignal, export.TwofaProtocolTransportError)):
            if operation == "enroll":
                export._enroll_totp(session, "unit-token")
            else:
                export._activate_totp(session, "unit-token", "JBSWY3DPEHPK3PXP", "original-session")
    assert original.post.call_count == 1
    assert observer.failure(driver).operation == "twofa_" + operation
    assert observer.failure(driver).replay_safe is False


def test_protocol_2fa_current_403_changes_route_before_original_browser_fallback():
    result, mocks, callback, calls, _client, events = _run_twofa_failure(protocol=True, operation="twofa_enroll")
    assert result["success"] is True
    assert result["twofa"]["ok"] is True, result["twofa"]
    assert result["twofa"]["driver"] == "browser_fallback"
    assert len(calls) == 1
    assert events.index("acquire") < events.index("twofa")
    callback.assert_called_once()
    mocks["persist"].assert_called_once()


def test_plan_after_protocol_twofa_rotation_discards_old_session_and_uses_current_proxy():
    queries = []
    with patch("core.accounts.plans.client.query_account_quota", side_effect=lambda *_args, **kwargs: (
        queries.append(kwargs), {"ok": True, "quota_status": "success"},
    )):
        result, mocks, callback, _calls, _client, _events = _run_twofa_failure(
            protocol=True, operation="twofa_enroll", plan_check=True,
        )
    assert result["success"] is True
    assert len(queries) == 1
    assert queries[0]["session"] is None
    assert queries[0]["proxy"] == "http://next.example.test:8080"
    mocks["base_session"].close.assert_called_once()
    callback.assert_called_once()
    mocks["persist"].assert_called_once()
    mocks["_submit_email_and_wait_next"].assert_not_called()


@pytest.mark.parametrize("response_observed,success", [(True, True), (False, False)])
def test_original_activation_requires_its_current_response_and_remote_transition(response_observed, success):
    from core.registration.roxy import route_recovery as routes

    driver = SimpleNamespace(current_window_handle="CDwindow-target")
    observer = routes.RoxyRouteFailureObserver(driver, wall_clock=lambda: time.time())
    driver._registration_route_observer = observer
    action = Mock(side_effect=AssertionError("不能新开 enrollment"))
    field = object()
    secret = "JBSWY3DPEHPK3PXP"
    before = {"confirmed": False, "reason": "mfa_not_enabled"}
    after = {"confirmed": True, "reason": "totp_enabled"}

    def clicked(*_args, **_kwargs):
        record = {
            "request_id": "original-activate", "target_id": "target", "redirect_index": 0,
            "url": "https://chatgpt.com/backend-api/accounts/mfa/activate", "method": "POST",
            "resource_type": "Fetch", "started_wall_time": time.time(),
        }
        observer.observe_network(record, phase="request")
        if response_observed:
            observer.observe_network(record | {"status": 200}, phase="response")

    with patch("core.auth.browser.mfa_auth._probe_existing_roxy_totp", side_effect=[before, after]), \
            patch("core.auth.browser.mfa_auth._detect_mfa_enrollment_step", return_value=("totp", field)), \
            patch("core.auth.browser.mfa_auth._read_totp_secret_from_dialog", return_value=secret), \
            patch("core.auth.browser.mfa_auth._human_type_text"), \
            patch("core.auth.browser.mfa_auth._button_after_input", return_value=object()), \
            patch("core.auth.browser.mfa_auth._human_click", side_effect=clicked), \
            patch.object(routes.time, "time", return_value=100.0):
        if success:
            assert routes.continue_browser_twofa(
                driver, resume.EMAIL, failure=RegistrationRouteFailure(
                    "twofa_activate", http_status=403, response_received=True,
                ), existing_secret=secret, action=action, on_secret=Mock(), check_stop=Mock(),
            ) == secret
        else:
            with pytest.raises(RuntimeError, match="enabled_candidate_unverified"):
                routes.continue_browser_twofa(
                    driver, resume.EMAIL, failure=RegistrationRouteFailure(
                        "twofa_activate", transport_kind="connection",
                    ), existing_secret=secret, action=action, on_secret=Mock(), check_stop=Mock(),
                )
    action.assert_not_called()


def test_failed_close_prevents_new_lease_and_preserves_core_as_partial_success():
    result, mocks, callback, calls, _client, _events = _run_twofa_failure(closed=False)
    assert result["success"] is True
    assert result["twofa"]["ok"] is False
    assert result["core_persisted"] is True
    assert len(calls) == 1
    callback.assert_not_called()
    mocks["persist"].assert_called_once()


def test_exhausted_twofa_budget_keeps_original_secret_and_does_not_restart_core():
    result, mocks, callback, calls, _client, _events = _run_twofa_failure(no_new_lease=True)
    assert result["success"] is True
    assert result["twofa"]["ok"] is False
    assert result["totp_secret"] == "ORIGINALSECRET"
    assert len(calls) == 1
    callback.assert_called_once()
    mocks["persist"].assert_called_once()
