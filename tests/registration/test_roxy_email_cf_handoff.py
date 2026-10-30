"""当前 CF 挑战在邮箱恢复刷新前交回本地 Roxy，避免导航抹掉强证据。"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.auth.browser import email_otp
from core.registration import roxy
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from tests.email.test_email_frontend_loading import _Clock, _email_flow
from tests.registration.test_roxy_native_signin_diagnostics import event


FORM = "https://chatgpt.com/auth/login"


def current_evidence(driver, *, challenge=True):
    evidence = roxy._NativeSigninFailureDiagnostics(Mock(), include_form_entry=True)
    evidence.begin_navigation(driver)
    evidence.observe_network(event("document", url=FORM, method="GET", started=10.0,
                                   resource_type="Document"), phase="request")
    evidence.observe_network(event("signin"), phase="request")
    evidence.observe_network(event("signin", status=403, headers=(
        {"cf-mitigated": "challenge"} if challenge else {"server": "cloudflare"}
    )), phase="response")
    return evidence


def handoff_current_challenge(driver, evidence):
    def check():
        if evidence.failure_diagnostic(driver):
            raise email_otp._EmailSubmissionUnknown("request_unknown: 当前邮箱认证入口已确认 CF 挑战")
    return Mock(side_effect=check)


def submission(driver, *, http_rejected):
    driver._email_submission_receipt = {"phase": "dispatched"}
    driver._browser_submission_receipt = BrowserSubmissionReceipt(
        kind="resume_login", stage="submit_email", endpoint_kind="email_submit",
        phase="response_observed" if http_rejected else "ui_dispatched",
        http_status=403 if http_rejected else None, result="failure" if http_rejected else "",
    )


@pytest.mark.parametrize("http_rejected", [True, False])
def test_current_challenge_stops_before_both_saved_login_and_waiting_recovery(http_rejected):
    clock = _Clock()
    driver = SimpleNamespace(current_url=FORM, current_window_handle="CDwindow-current-target")
    evidence = current_evidence(driver)
    before_recovery = handoff_current_challenge(driver, evidence)
    with _email_flow(clock, driver) as stack:
        submit = stack.enter_context(patch.object(email_otp, "_submit_email_step", side_effect=lambda *_:
                                                  submission(driver, http_rejected=http_rejected)))
        stack.enter_context(patch.object(email_otp, "_email_ui_submission_state", return_value="dispatched"))
        stack.enter_context(patch.object(email_otp, "log_submission_diagnostics"))
        waiting_recovery = stack.enter_context(patch.object(email_otp, "recover_submission_page"))
        saved_recovery = stack.enter_context(patch.object(email_otp, "_recover_saved_login_email_page"))
        with pytest.raises(email_otp._EmailSubmissionUnknown, match="CF 挑战"):
            email_otp._submit_email_and_wait_next(
                driver, "unit@example.test", total_timeout=80, allow_login_password=True,
                on_before_recovery=before_recovery,
            )
    submit.assert_called_once()
    before_recovery.assert_called()
    waiting_recovery.assert_not_called()
    saved_recovery.assert_not_called()
    assert driver._browser_submission_receipt.phase in {"response_observed", "ui_dispatched"}


@pytest.mark.parametrize("evidence_kind", ["ordinary_403", "later_success", "pending_auth", "none"])
def test_other_or_obsolete_evidence_keeps_existing_saved_login_recovery(evidence_kind):
    clock = _Clock()
    driver = SimpleNamespace(current_url=FORM, current_window_handle="CDwindow-current-target")
    evidence = current_evidence(driver, challenge=evidence_kind != "ordinary_403")
    if evidence_kind in {"later_success", "pending_auth"}:
        evidence.observe_network(event("next", started=12.0), phase="request")
        if evidence_kind == "later_success":
            evidence.observe_network(event("next", started=12.0, status=200), phase="response")
    options = {} if evidence_kind == "none" else {
        "on_before_recovery": handoff_current_challenge(driver, evidence),
    }
    with _email_flow(clock, driver) as stack:
        stack.enter_context(patch.object(email_otp, "_submit_email_step", side_effect=lambda *_:
                                         submission(driver, http_rejected=True)))
        stack.enter_context(patch.object(email_otp, "_email_ui_submission_state", return_value="dispatched"))
        stack.enter_context(patch.object(email_otp, "log_submission_diagnostics"))
        saved_recovery = stack.enter_context(patch.object(email_otp, "_recover_saved_login_email_page", return_value="otp"))
        result = email_otp._submit_email_and_wait_next(
            driver, "unit@example.test", total_timeout=80, allow_login_password=True, **options,
        )
    assert result == "otp"
    saved_recovery.assert_called_once()


def test_advanced_authentication_returns_before_recovery_callback():
    clock = _Clock()
    driver = SimpleNamespace(current_url=FORM)
    before_recovery = Mock(side_effect=AssertionError("已进入下一步不应检查旧邮箱挑战"))
    with _email_flow(clock, driver) as stack:
        stack.enter_context(patch.object(email_otp, "_type_email_address", return_value="otp"))
        submit = stack.enter_context(patch.object(email_otp, "_submit_email_step"))
        result = email_otp._submit_email_and_wait_next(
            driver, "unit@example.test", on_before_recovery=before_recovery,
        )
    assert result == "otp"
    submit.assert_not_called()
    before_recovery.assert_not_called()


@pytest.mark.parametrize("recovery_path", ["initial_fallback", "csrf_ui_retry", "csrf_blank_reload", "settled_blank_reload"])
def test_challenge_stops_nextauth_recovery_before_its_next_browser_action(recovery_path):
    clock = _Clock()
    driver = SimpleNamespace(current_url=FORM, current_window_handle="CDwindow-current-target")
    evidence = current_evidence(driver, challenge=recovery_path == "initial_fallback")
    before_recovery = handoff_current_challenge(driver, evidence)

    def csrf_challenge(*_args):
        record = event("csrf", url="https://chatgpt.com/api/auth/csrf", method="GET", started=12.0)
        evidence.observe_network(record, phase="request")
        evidence.observe_network(record | {"status": 403, "response_headers": {"cf-mitigated": "challenge"}},
                                 phase="response")
        return {"ok": recovery_path == "settled_blank_reload", "not_dispatched": True, "stage": "csrf"}

    with _email_flow(clock, driver) as stack:
        frontend_unready = recovery_path in {"initial_fallback", "csrf_ui_retry"}
        submit = stack.enter_context(patch.object(
            email_otp, "_submit_email_step",
            side_effect=email_otp._EmailFrontendNotReady("表单尚未接管") if frontend_unready else None,
        ))
        stack.enter_context(patch.object(email_otp, "_email_ui_submission_state", return_value=None))
        stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", side_effect=["blank_shell", "unknown"]))
        stack.enter_context(patch.object(email_otp, "_is_blank_chatgpt_auth_shell", return_value=True))
        stack.enter_context(patch.object(email_otp, "_log_blank_auth_shell_diagnostics"))
        fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth", side_effect=csrf_challenge))
        refresh = stack.enter_context(patch.object(email_otp, "_reload_blank_chatgpt_auth_shell"))
        with pytest.raises(email_otp._EmailSubmissionUnknown, match="CF 挑战"):
            email_otp._submit_email_and_wait_next(
                driver, "unit@example.test", on_before_recovery=before_recovery,
            )
    submit.assert_called_once()
    refresh.assert_not_called()
    if recovery_path == "initial_fallback":
        fallback.assert_not_called()
    else:
        fallback.assert_called_once()
