"""本地 Roxy 显式启用的 OTP 网络错误优先级及原提交保护。"""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.auth.browser import email_otp
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.state_machine import CancellationRequested, StageBudget


OTP_URL = "https://auth.openai.com/email-verification"


def _form(**changes):
    state = {"url": OTP_URL, "title": "OpenAI", "text": "Enter the verification code",
        "inputs": [{"type": "text", "name": "code", "autocomplete": "one-time-code", "ariaInvalid": "false"}],
        "buttons": [{"type": "submit", "text": "Continue"}], "errors": []}
    state.update(changes)
    return state


def _chrome(code="ERR_TUNNEL_CONNECTION_FAILED"):
    return {"url": "chrome-error://chromewebdata/", "title": "auth.openai.com",
        "text": f"This site can't be reached {code}", "inputs": [], "buttons": [], "errors": [code]}


def _application_error():
    return {"url": OTP_URL, "title": "OpenAI", "text": "अज्ञात त्रुटि हुई Failed to fetch",
        "inputs": [], "buttons": [], "errors": ["Failed to fetch"],
        "authErrorPage": True, "authErrorTexts": ["Failed to fetch"]}


def _receipt(phase="ui_dispatched", **changes):
    return BrowserSubmissionReceipt(kind="otp", stage="email_otp", endpoint_kind="otp_submit", phase=phase, **changes)


class _Clock:
    now = 100.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def run_wait():
    clock = _Clock()
    with ExitStack() as stack:
        stack.enter_context(patch.object(email_otp, "time", clock))
        stack.enter_context(patch.object(email_otp, "_check_manual_stop"))
        stack.enter_context(patch.object(email_otp, "_has_access_token", return_value=False))
        stack.enter_context(patch.object(email_otp, "auth_session_unavailable", return_value=False))
        stack.enter_context(patch.object(email_otp, "log_submission_diagnostics"))
        recovery = stack.enter_context(patch.object(email_otp, "recover_submission_page", return_value=None))
        fill = stack.enter_context(patch.object(email_otp, "_type_otp"))
        resend = stack.enter_context(patch.object(email_otp, "_click_resend_email_otp"))

        def run(state, *, receipt=None, timeout=1, enabled=True, baseline_state=None, driver=None):
            driver = driver or SimpleNamespace(current_url=OTP_URL, execute_script=lambda *_args: deepcopy(state),
                get=Mock(), refresh=Mock(), submit=Mock())
            if receipt is not None:
                driver._browser_submission_receipt = receipt
            budget = StageBudget.start(10, clock=clock.monotonic)
            kwargs = {"monitor_otp_network": True} if enabled else {}
            run.driver, run.budget = driver, budget
            return email_otp._wait_after_email_otp_submit(driver, timeout=timeout, budget=budget,
                baseline_state=baseline_state, **kwargs)

        run.clock, run.recovery, run.fill, run.resend = clock, recovery, fill, resend
        yield run


@pytest.mark.parametrize("code,cause", [
    ("ERR_TUNNEL_CONNECTION_FAILED", "otp_network_tunnel_connection_failed"),
    ("ERR_PROXY_CONNECTION_FAILED", "otp_network_proxy_connection_failed"),
    ("ERR_CONNECTION_RESET", "otp_network_connection_reset"),
    ("ERR_CONNECTION_CLOSED", "otp_network_connection_closed"),
    ("ERR_HTTP2_PING_FAILED", "otp_network_http2_ping_failed"),
    ("ERR_NAME_NOT_RESOLVED", "otp_network_name_not_resolved"),
])
def test_actual_chrome_document_wins_over_stale_webdriver_otp_route(run_wait, code, cause):
    receipt = _receipt("request_observed", http_method="POST")
    with pytest.raises(RuntimeError) as raised:
        run_wait(_chrome(code), receipt=receipt)
    error = raised.value
    assert error.code == error.error_code == "otp_page_network_error"
    assert error.cause_code == cause
    assert error.network_error == code
    assert error.request_unknown is True
    assert receipt.phase == "unknown"
    assert receipt.http_status is None
    assert run_wait.driver.current_url == OTP_URL
    run_wait.driver.get.assert_not_called()
    run_wait.driver.submit.assert_not_called()
    run_wait.fill.assert_not_called()
    run_wait.resend.assert_not_called()
    run_wait.recovery.assert_not_called()


@pytest.mark.parametrize("timeout", [0, 1])
def test_application_failed_fetch_is_transport_failure_before_any_invalid_branch(run_wait, timeout):
    state = _application_error()
    state["inputs"] = [{"name": "code", "autocomplete": "one-time-code", "ariaInvalid": "true"}]
    with pytest.raises(RuntimeError) as raised:
        run_wait(state, receipt=_receipt(), timeout=timeout)
    assert raised.value.cause_code == "otp_network_failed_to_fetch"
    assert raised.value.request_unknown is True
    run_wait.resend.assert_not_called()
    assert run_wait.clock.now <= 101


def test_default_shared_wait_retains_old_behavior_without_explicit_roxy_option(run_wait):
    assert run_wait(_application_error(), enabled=False) == "invalid"
    assert run_wait(_chrome(), enabled=False, timeout=0) == "invalid"


@pytest.mark.parametrize("state", [
    _form(errors=["Failed to fetch"], text="Enter the verification code. Documentation: Failed to fetch"),
    _form(errors=["Invalid verification code"]),
    {**_application_error(), "url": "https://auth.openai.com.evil.test/email-verification"},
    {**_application_error(), "url": "http://auth.openai.com/email-verification"},
    {**_application_error(), "url": "https://private@auth.openai.com/email-verification"},
    {**_application_error(), "url": "https://auth.openai.com:444/email-verification"},
    {**_chrome(), "url": "https://example.test/email-verification"},
])
def test_unrelated_error_text_and_untrusted_documents_are_never_otp_rejection(run_wait, state):
    assert run_wait(state, receipt=_receipt(), timeout=0) == "stuck"


@pytest.mark.parametrize("change,expected", [
    ({"name": "code", "autocomplete": "one-time-code", "ariaInvalid": "true"}, "invalid"),
    ({"name": "password", "type": "password", "ariaInvalid": "true"}, "stuck"),
    ({"name": "phone", "type": "tel", "ariaInvalid": "true"}, "stuck"),
    ({"name": "code", "ariaInvalid": "true", "visible": False}, "stuck"),
    ({"name": "code", "ariaInvalid": "true", "disabled": True}, "stuck"),
])
def test_only_current_visible_otp_field_invalidity_can_reject(run_wait, change, expected):
    assert run_wait(_form(inputs=[change]), timeout=0) == expected


def test_stale_baseline_invalidity_does_not_reject_new_submission(run_wait):
    state = _form(inputs=[{"name": "code", "autocomplete": "one-time-code", "ariaInvalid": "true"}])
    assert run_wait(state, timeout=0, baseline_state=deepcopy(state)) == "stuck"


@pytest.mark.parametrize("binding,response,status,phase,expected", [
    (("page", "current"), ("page", "current"), 400, "rejected", "invalid"),
    (("page", "current"), ("page", "old"), 400, "rejected", "stuck"),
    (None, None, 400, "rejected", "stuck"),
    (("page", ""), ("page", ""), 400, "rejected", "stuck"),
    (("page", "current"), ("page", "current"), 200, "response_observed", "stuck"),
    (("page", "current"), ("page", "current"), 400, "confirmed", "stuck"),
])
def test_remote_wrong_code_requires_current_matching_request_and_rejection(run_wait, binding, response, status, phase, expected):
    receipt = _receipt(phase, http_method="POST", http_status=status,
        request_binding=binding, response_binding=response, auth_error={"code": "wrong_email_otp_code"})
    assert run_wait(_form(inputs=[]), receipt=receipt, timeout=0) == expected


def test_later_success_page_cannot_be_overridden_by_old_wrong_code_receipt(run_wait):
    receipt = _receipt("rejected", http_method="POST", http_status=400,
        request_binding=("page", "current"), response_binding=("page", "current"),
        auth_error={"code": "wrong_email_otp_code"})
    assert run_wait({"url": "https://auth.openai.com/about-you", "text": "Tell us about you", "inputs": []},
        receipt=receipt) == "accepted"


@pytest.mark.parametrize("new_phase,new_wrong,expected", [
    ("request_observed", False, "stuck"), ("rejected", True, "invalid"),
])
def test_wait_uses_current_otp_action_when_old_action_is_replaced(run_wait, new_phase, new_wrong, expected):
    old = _receipt("rejected", http_method="POST", http_status=400,
        request_binding=("page", "A"), response_binding=("page", "A"), auth_error={"code": "wrong_email_otp_code"})
    current = _receipt(new_phase, http_method="POST", http_status=400 if new_wrong else None,
        request_binding=("page", "B"), response_binding=("page", "B") if new_wrong else None,
        auth_error={"code": "wrong_email_otp_code"} if new_wrong else {})
    driver = SimpleNamespace(current_url=OTP_URL, get=Mock(), refresh=Mock(), submit=Mock())

    def snapshot(*_args):
        driver._browser_submission_receipt = current
        return _form()

    driver.execute_script = snapshot
    assert run_wait(_form(), driver=driver, receipt=old) == expected
    assert old.phase == "rejected"
    run_wait.resend.assert_not_called()


@pytest.mark.parametrize("phase", ["confirmed", "rejected"])
@pytest.mark.parametrize("in_history", [False, True])
def test_terminal_receipt_new_pending_network_request_still_preserves_unknown(run_wait, phase, in_history):
    old = _receipt(phase, http_method="POST", http_status=401,
        request_binding=("page", "B"), auth_error={})
    old._otp_network_request_unknown = True
    old._otp_network_http_status = None
    current = _receipt("confirmed") if in_history else old
    driver = SimpleNamespace(current_url=OTP_URL, execute_script=lambda *_args: _chrome(),
        _browser_submission_receipts=[old], get=Mock(), refresh=Mock(), submit=Mock())
    before = deepcopy(vars(old))
    with pytest.raises(RuntimeError) as raised:
        run_wait(_chrome(), receipt=current, timeout=0, driver=driver)
    assert raised.value.request_unknown is True
    assert vars(old) == before
    assert current.phase == "confirmed" if in_history else current.phase == phase


@pytest.mark.parametrize("phase", ["confirmed", "rejected"])
@pytest.mark.parametrize("status,unknown,wrong,expected", [
    (None, True, False, "stuck"), (200, True, True, "stuck"), (400, False, True, "invalid"),
])
def test_current_network_response_overrides_old_terminal_http_status(run_wait, phase, status, unknown, wrong, expected):
    receipt = _receipt(phase, http_method="POST", http_status=401,
        request_binding=("page", "B"), response_binding=("page", "B") if status is not None else None,
        auth_error={"code": "wrong_email_otp_code"} if wrong else {})
    receipt._otp_network_request_unknown = unknown
    receipt._otp_network_http_status = status
    assert run_wait(_form(), receipt=receipt, timeout=0) == expected
    assert receipt.phase == phase


@pytest.mark.parametrize("state,expected", [
    ({"url": "https://auth.openai.com/about-you", "text": "Tell us about you", "inputs": []}, "accepted"),
    ({"url": OTP_URL, "emailVerified": True, "inputs": [], "text": "Email verified"}, "email_verified"),
    ({"url": "https://auth.openai.com/log-in/password", "text": "Authenticator code", "inputs": [{"name": "totp"}]}, "totp_required"),
])
def test_confirmed_page_result_clears_only_current_network_unknown_marker(run_wait, state, expected):
    current, historical = _receipt("response_observed", http_status=200), _receipt("unknown")
    current._otp_network_request_unknown = historical._otp_network_request_unknown = True
    current._otp_network_http_status = 200
    driver = SimpleNamespace(current_url=OTP_URL, execute_script=lambda *_args: deepcopy(state),
        _browser_submission_receipts=[historical, current], get=Mock(), refresh=Mock(), submit=Mock())
    assert run_wait(state, driver=driver, receipt=current) == expected
    assert current._otp_network_request_unknown is False
    assert historical._otp_network_request_unknown is True
    assert current.phase == "response_observed"
    assert current._otp_network_http_status == 200


def test_success_then_confirmed_receipt_does_not_claim_unresolved_network_request(run_wait):
    receipt = _receipt("response_observed", http_status=200)
    receipt._otp_network_request_unknown = True
    receipt._otp_network_http_status = 200
    assert run_wait({"url": "https://auth.openai.com/about-you", "text": "Tell us about you", "inputs": []}, receipt=receipt) == "accepted"
    receipt.transition("confirmed", result="success")
    with pytest.raises(RuntimeError) as raised:
        run_wait(_chrome(), receipt=receipt, timeout=0)
    assert raised.value.request_unknown is False
    assert receipt.phase == "confirmed"


@pytest.mark.parametrize("current_phase,history_phase,unknown", [
    ("prepared", "confirmed", False), ("confirmed", "confirmed", False),
    ("confirmed", "unknown", True), ("unknown", "confirmed", True),
])
def test_network_error_preserves_confirmed_and_historical_submission_facts(run_wait, current_phase, history_phase, unknown):
    current, historical = _receipt(current_phase), _receipt(history_phase)
    before = (deepcopy(vars(current)), deepcopy(vars(historical)))
    driver = SimpleNamespace(current_url=OTP_URL, execute_script=lambda *_args: _chrome(),
        _browser_submission_receipts=[historical], get=Mock(), refresh=Mock(), submit=Mock())
    with pytest.raises(RuntimeError) as raised:
        run_wait(_chrome(), receipt=current, timeout=0, driver=driver)
    assert raised.value.request_unknown is unknown
    assert vars(current) == before[0]
    assert vars(historical) == before[1]


@pytest.mark.parametrize("unresolved", [True, False, RuntimeError("事实暂不可核验")])
def test_durable_history_is_checked_only_when_network_error_needs_it(run_wait, unresolved):
    driver = SimpleNamespace(current_url=OTP_URL, execute_script=lambda *_args: _chrome(),
        _registration_fact_context={"attempt_id": 41}, get=Mock(), refresh=Mock(), submit=Mock())
    with patch("core.storage.registration.has_unresolved_submission_facts",
        side_effect=unresolved if isinstance(unresolved, Exception) else None, return_value=unresolved) as query:
        with pytest.raises(RuntimeError) as raised:
            run_wait(_chrome(), receipt=_receipt("confirmed"), timeout=0, driver=driver)
    assert raised.value.request_unknown is (unresolved is not False)
    query.assert_called_once_with(41)


def test_recovery_observation_checks_network_before_invalid_and_keeps_original_budget(run_wait):
    state = _form(inputs=[], errors=["Route Error (500)"], text="Route Error (500)")
    driver = SimpleNamespace(current_url=OTP_URL, execute_script=lambda *_args: deepcopy(state),
        get=Mock(), refresh=Mock(), submit=Mock())
    receipt = _receipt()

    def recover(_driver, _stage, observe, *, budget, **_kwargs):
        driver.execute_script = lambda *_args: _chrome()
        return observe(budget)

    run_wait.recovery.side_effect = recover
    with pytest.raises(RuntimeError) as raised:
        run_wait(state, receipt=receipt, driver=driver)
    assert raised.value.cause_code == "otp_network_tunnel_connection_failed"
    assert receipt.phase == "unknown"
    assert run_wait.budget.deadline == 110
    assert run_wait.clock.now <= 101
    run_wait.resend.assert_not_called()


def test_blank_redirect_shell_keeps_unknown_without_extending_confirmation_budget(run_wait):
    receipt = _receipt("unknown")
    assert run_wait({"url": "https://auth.openai.com/about-you", "text": "Loading", "inputs": []},
        receipt=receipt, timeout=0) == "stuck"
    assert receipt.phase == "unknown"
    assert run_wait.clock.now == 100


def test_manual_stop_remains_original_exception_before_network_observation(run_wait):
    error = CancellationRequested("停止")
    with patch.object(email_otp, "_check_manual_stop", side_effect=error):
        with pytest.raises(CancellationRequested) as raised:
            run_wait(_chrome(), receipt=_receipt())
    assert raised.value is error
    run_wait.resend.assert_not_called()


@pytest.fixture(scope="module")
def dom_page():
    api = pytest.importorskip("playwright.sync_api")
    with api.sync_playwright() as runtime:
        if not Path(runtime.chromium.executable_path).exists():
            pytest.skip("本机未安装隔离 Chromium 测试运行时")
        browser = runtime.chromium.launch(headless=True)
        context = browser.new_context()
        context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body="<main></main>"))
        page = context.new_page()
        page.goto(OTP_URL)
        try:
            yield page
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("html,expected_network,expected_invalid", [
    ("<main><h1>अज्ञात त्रुटि हुई</h1><p class='error-message'>Failed to fetch</p></main>", True, False),
    ("<main><h1>ओह, एक अनजान गड़बड़ी हो गई!</h1><p>Failed to fetch</p><button>दोबारा कोशिश करें</button></main>", True, False),
    ("<main><h1>Unknown error</h1><p class='error-message' hidden>Failed to fetch</p></main>", False, False),
    ("<form><input name='code' autocomplete='one-time-code' aria-invalid='true' style='visibility:hidden'></form>", False, False),
    ("<form><label>Verification code<input name='code' autocomplete='one-time-code'></label></form>"
     "<footer><p>Documentation: Failed to fetch</p></footer>", False, False),
    ("<form><input name='code' autocomplete='one-time-code' aria-describedby='code-error'>"
     "<p id='code-error'>Invalid verification code</p></form>", False, True),
])
def test_actual_dom_distinguishes_error_page_from_otp_field_errors(dom_page, run_wait, html, expected_network, expected_invalid):
    dom_page.set_content(html)
    driver = SimpleNamespace(current_url=OTP_URL,
        execute_script=lambda script, *_args: dom_page.evaluate("() => {" + script + "}"),
        get=Mock(), refresh=Mock(), submit=Mock())
    state = email_otp._email_otp_page_state(driver)
    if expected_network:
        with pytest.raises(RuntimeError) as raised:
            run_wait(state, driver=driver, receipt=_receipt(), timeout=0)
        assert raised.value.cause_code == "otp_network_failed_to_fetch"
    else:
        assert run_wait(state, driver=driver, timeout=0) == ("invalid" if expected_invalid else "stuck")
