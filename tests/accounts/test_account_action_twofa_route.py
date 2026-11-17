"""独立 2FA 的协议失败与浏览器兜底失败均须可追溯。"""
from contextlib import ExitStack
import logging
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.accounts.password_setup.route_recovery import AccountActionRouteError, AccountActionRouteFailure
from core.codex import retry_service as worker


@pytest.mark.parametrize("active_secret,extra", [
    ("JBSWY3DPEHPK3PXP", {"totp_setup_pending": True}),
    ("", {"totp_pending_secret": "JBSWY3DPEHPK3PXP", "totp_setup_pending": True}),
    ("", {"totp_pending_secret": "JBSWY3DPEHPK3PXP"}),
    ("   ", {"totp_pending_secret": "JBSWY3DPEHPK3PXP"}),
])
def test_direct_twofa_pending_secret_never_starts_a_second_enrollment(active_secret, extra):
    account = {
        "id": 42, "email": "twofa-fixture@example.test", "access_token": "fixture-at",
        "totp_secret": active_secret, "extra_json": dict(extra),
    }
    with patch("core.auth.protocol.session.BrowserSession") as session, \
            patch("core.accounts.export.setup_2fa_protocol") as enroll:
        with pytest.raises(AccountActionRouteError) as caught:
            worker._run_protocol_direct_twofa(account["email"], account, SimpleNamespace(proxy_url="fixture"), 81)
    assert caught.value.request_unknown is True
    session.assert_not_called()
    enroll.assert_not_called()
    assert account["totp_secret"] == active_secret
    assert account["extra_json"] == extra


def test_protocol_cancellation_never_enters_browser_fallback():
    from core.operations.runtime import OperationCancelled
    from tests.accounts.test_account_twofa_direct import ProtocolDirectTwofaTests

    account = {"id": 9, "email": "a@example.com", "access_token": "saved-chatgpt-token"}
    fixture = ProtocolDirectTwofaTests()
    result, route, _db, _events, _protocol, _reauth, _session, browser, _action = fixture._run_worker(
        account=account, fallback_enabled=True, protocol_side_effect=OperationCancelled("已取消"),
    )
    assert result["status"] == "stopped"
    browser.assert_not_called()
    route.release.assert_called_once()


def test_pending_secret_with_disabled_browser_never_creates_protocol_or_roxy_session():
    from tests.accounts.test_account_twofa_direct import ProtocolDirectTwofaTests

    account = {
        "id": 9, "email": "a@example.com", "access_token": "saved-chatgpt-token",
        "totp_secret": "JBSWY3DPEHPK3PXP", "extra_json": {"totp_setup_pending": True},
    }
    result, route, _db, _events, protocol, _reauth, session, browser, _action = (
        ProtocolDirectTwofaTests()._run_worker(account=account, fallback_enabled=False)
    )
    assert result["ok"] is False
    assert result["remote_receipt_state"] == "unknown"
    assert account["totp_secret"] == "JBSWY3DPEHPK3PXP"
    protocol.assert_not_called()
    session.assert_not_called()
    browser.assert_not_called()
    route.release.assert_called_once()


def test_real_mfa_enroll_connect_failure_recovers_only_current_call_without_roxy():
    from core.accounts import export
    from core.accounts.password_setup import route_recovery
    from tests.accounts.test_account_action_route_session import session

    current = session(RuntimeError("Proxy CONNECT aborted"), SimpleNamespace(
        status_code=200, json=lambda: {"secret": "JBSWY3DPEHPK3PXP", "session_id": "fixture"}),
        SimpleNamespace(status_code=200, json=lambda: {"success": True}))
    current.get_chatgpt_headers = Mock(return_value={})
    current.navigator_language = Mock(return_value="en-US")
    current.close = lambda: current.session.close()
    recover = Mock(return_value="http://replacement.example:8080")
    account = {"id": 42, "email": "twofa-fixture@example.test", "access_token": "fixture-at"}
    with patch("core.auth.protocol.session.BrowserSession", return_value=current), \
            patch.object(route_recovery, "Session", return_value=SimpleNamespace(close=Mock())), \
            patch.object(worker.db, "update_account_totp_secret", return_value=True), \
            patch.object(worker.db, "update_account_twofa_status", return_value=True), \
            patch.object(worker.account_task_store, "append_event"), \
            patch.object(worker, "check_stop_requested"), \
            patch.object(export, "human_delay"), \
            patch("core.codex.roxy.oauth.run_roxy_chatgpt_account_action") as browser:
        result = worker._run_protocol_direct_twofa(
            account["email"], account, SimpleNamespace(proxy_url=current.proxy), 81, route_recover=recover,
        )
    assert result["ok"] is True
    assert current.post.call_count == 3
    assert ["enroll", "enroll", "activate_enrollment"] == [
        call.args[0].rsplit("/", 1)[-1] for call in current.post.call_args_list
    ]
    assert recover.call_args.args[0].proxy_fault is True
    browser.assert_not_called()


def test_real_mfa_unknown_enroll_bypasses_shared_two_attempt_loop():
    from core.accounts import export
    from tests.accounts.test_account_action_route_session import session

    current = session(TimeoutError("response timed out"))
    current.get_chatgpt_headers = Mock(return_value={})
    current.navigator_language = Mock(return_value="en-US")
    current.close = lambda: current.session.close()
    recover = Mock()
    account = {"id": 42, "email": "twofa-fixture@example.test", "access_token": "fixture-at"}
    with patch("core.auth.protocol.session.BrowserSession", return_value=current), \
            patch.object(worker.account_task_store, "append_event"), \
            patch.object(worker, "check_stop_requested"), patch.object(export, "human_delay"), \
            patch.object(worker.db, "update_account_totp_secret") as write:
        with pytest.raises(AccountActionRouteError) as caught:
            worker._run_protocol_direct_twofa(
                account["email"], account, SimpleNamespace(proxy_url=current.proxy), 81, route_recover=recover,
            )
    assert caught.value.request_unknown is True
    assert current.post.call_count == 1
    write.assert_not_called()
    recover.assert_not_called()


@pytest.mark.parametrize("terminal_kind", ["unusable", "mfa_http"])
def test_explicit_account_deactivation_after_secret_checkpoint_keeps_original_account_cause(terminal_kind):
    from core.auth.protocol.openai_auth import AccountUnusableError
    from core.accounts.export import TwofaProtocolHTTPError

    account = {"id": 42, "email": "twofa-fixture@example.test", "access_token": "fixture-at"}
    terminal = (
        AccountUnusableError("远端明确停用", error_code="account_deactivated") if terminal_kind == "unusable"
        else TwofaProtocolHTTPError("activate", 403, error_code="account_deactivated")
    )

    def setup(_session, _token, *, on_secret):
        on_secret("JBSWY3DPEHPK3PXP")
        raise terminal

    with patch("core.auth.protocol.session.BrowserSession"), \
            patch("core.accounts.export.setup_2fa_protocol", side_effect=setup), \
            patch.object(worker.db, "update_account_totp_secret", return_value=True), \
            patch.object(worker.account_task_store, "append_event"):
        with pytest.raises(type(terminal)) as caught:
            worker._run_protocol_direct_twofa(account["email"], account, SimpleNamespace(proxy_url="fixture"), 81)
    assert caught.value is terminal


@pytest.mark.parametrize("account_code", ["account_deactivated", "account_deleted"])
def test_real_activation_account_rejection_preserves_confirmed_cause_after_secret_checkpoint(account_code):
    from core.accounts import export
    from tests.accounts.test_account_action_route_session import session

    secret = "JBSWY3DPEHPK3PXP"
    current = session(
        SimpleNamespace(status_code=200, json=lambda: {"secret": secret, "session_id": "fixture"}),
        SimpleNamespace(
            status_code=403, json=lambda: {"error": {"code": account_code}},
            text="", headers={},
        ),
    )
    current.get_chatgpt_headers = Mock(return_value={})
    current.navigator_language = Mock(return_value="en-US")
    current.close = lambda: current.session.close()
    recover = Mock()
    account = {"id": 42, "email": "twofa-fixture@example.test", "access_token": "fixture-at"}
    with patch("core.auth.protocol.session.BrowserSession", return_value=current), \
            patch.object(worker.account_task_store, "append_event"), \
            patch.object(worker, "check_stop_requested"), patch.object(export, "human_delay"), \
            patch.object(export.time, "time", return_value=0), \
            patch.object(worker.db, "update_account_totp_secret", return_value=True) as write:
        with pytest.raises(export.TwofaProtocolHTTPError) as caught:
            worker._run_protocol_direct_twofa(
                account["email"], account, SimpleNamespace(proxy_url=current.proxy), 81, route_recover=recover,
            )
    assert caught.value.error_code == account_code
    assert worker._account_deactivation_code(caught.value) == account_code
    assert current.post.call_count == 2
    write.assert_called_once_with(account["email"], secret, setup_pending=True)
    recover.assert_not_called()


@pytest.mark.parametrize("operation,broken", [
    ("enroll", ValueError("invalid json")), ("enroll", {}),
    ("activate", ValueError("invalid json")), ("activate", {"success": False}),
])
def test_mfa_accepted_response_without_valid_receipt_never_falls_back_to_new_enrollment(operation, broken):
    from core.accounts import export
    from tests.accounts.test_account_action_route_session import session

    class Response:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            if isinstance(self.payload, Exception):
                raise self.payload
            return self.payload

    secret = "JBSWY3DPEHPK3PXP"
    outcomes = [Response(broken)] if operation == "enroll" else [
        Response({"secret": secret, "session_id": "fixture"}), Response(broken),
    ]
    current = session(*outcomes)
    current.get_chatgpt_headers = Mock(return_value={})
    current.navigator_language = Mock(return_value="en-US")
    current.close = lambda: current.session.close()
    account = {"id": 42, "email": "twofa-fixture@example.test", "access_token": "fixture-at"}
    with patch("core.auth.protocol.session.BrowserSession", return_value=current), \
            patch.object(worker.account_task_store, "append_event"), \
            patch.object(worker, "check_stop_requested"), patch.object(export, "human_delay"), \
            patch.object(worker.db, "update_account_totp_secret", return_value=True) as write:
        with pytest.raises(AccountActionRouteError) as caught:
            worker._run_protocol_direct_twofa(
                account["email"], account, SimpleNamespace(proxy_url=current.proxy), 81, route_recover=Mock(),
            )
    assert caught.value.request_unknown is True
    assert caught.value.failure.http_status == 200
    assert current.post.call_count == (1 if operation == "enroll" else 2)
    if operation == "enroll":
        write.assert_not_called()
    else:
        write.assert_called_once_with(account["email"], secret, setup_pending=True)


def test_unavailable_roxy_preserves_protocol_failure_and_releases_account_route():
    account = {"id": 42, "email": "twofa-fixture@example.test", "access_token": "fixture-at"}
    protocol_failure = AccountActionRouteFailure(
        "mfa_enroll", "POST", transport_kind="proxy", request_unknown=False, proxy_fault=True,
    )
    protocol_error = AccountActionRouteError(protocol_failure, code="account_action_route_exhausted")
    route = SimpleNamespace(
        proxy_url="http://fixture.proxy:8080", provider="fixture", mode="pool", region="JP",
        release=Mock(), lease=SimpleNamespace(lease_id="fixture-lease"),
        public_dict=lambda: {"network_route": "proxy", "proxy_mode": "pool"},
    )
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        stack.enter_context(patch("config.reload_all"))
        stack.enter_context(patch.object(worker.db, "get_account_by_email", return_value=dict(account)))
        stack.enter_context(patch.object(worker.db, "update_account_twofa_status"))
        stack.enter_context(patch.object(worker.account_task_store, "get_task", return_value={}))
        stack.enter_context(patch.object(worker.account_task_store, "append_event"))
        stack.enter_context(patch.object(worker.task_run_log, "TaskRunLogHandler", return_value=logging.NullHandler()))
        stack.enter_context(patch.object(worker, "check_stop_requested"))
        stack.enter_context(patch.object(worker, "_run_protocol_direct_twofa", side_effect=protocol_error))
        stack.enter_context(patch.object(worker, "_build_roxy_account_setup", return_value=Mock()))
        stack.enter_context(patch("core.proxy.account_routes.acquire_account_proxy", return_value=route))
        browser = stack.enter_context(patch(
            "core.codex.roxy.oauth.run_roxy_chatgpt_account_action",
            side_effect=ConnectionRefusedError("fixture Roxy unavailable"),
        ))
        stack.enter_context(patch.object(worker, "_RUNNING_THREADS", {}))
        stack.enter_context(patch.object(worker, "_RESERVED_AT", {}))
        stack.enter_context(patch.object(worker, "_STOP_REQUESTED", set()))
        result = worker.run_twofa_worker(
            account["email"], task_id=81, manage_task=False, clear_log=False,
            target_log_path=Path(directory) / "setup.log", steps={"twofa"},
            twofa_driver_override="protocol",
            execution_settings={"twofa_browser_fallback_enabled": True, "twofa_protocol_reauth_enabled": True},
        )
    assert result["ok"] is False
    assert browser.call_count == 1
    assert result["protocol_failure"]["cause_code"] == "account_action_route_exhausted"
    assert result["protocol_failure"]["operation"] == "mfa_enroll"
    assert result["protocol_failure"]["transport_kind"] == "proxy"
    assert result["fallback_failure"]["error_type"] == "ConnectionRefusedError"
    assert route.release.call_count == 1
    assert account["access_token"] == "fixture-at"
