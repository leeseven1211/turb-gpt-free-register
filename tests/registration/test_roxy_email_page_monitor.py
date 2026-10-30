"""注册邮箱等待的明确页面错误优先级与原提交事实保护。"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.auth.browser import email_otp
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.page_errors import AuthPageError
from core.auth.state_machine import CancellationRequested, StageBudget
from core.registration import roxy
from tests.email.test_email_frontend_loading import _Clock, _email_flow
from tests.registration import test_registration_resume_session as resume


PAGE_ERRORS = (
    ("Operation timed out", "auth_operation_timeout"),
    ("इस पेज पर आगे बढ़ने के लिए ज़रूरी जानकारी नहीं है.", "auth_context_missing"),
)


@pytest.mark.parametrize("path", ["ui", "nextauth", "csrf_then_ui"])
@pytest.mark.parametrize("error", [False, True])
def test_wrapper_forwards_observer_to_each_existing_wait_without_extra_submission(path, error):
    clock = _Clock()
    driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login")
    observed = []
    failure = AuthPageError("auth_context_missing") if error else None

    def observe(snapshot):
        observed.append(snapshot)
        if failure is not None:
            raise failure

    first_wait = path == "nextauth"

    def wait(_driver, _email, **kwargs):
        nonlocal first_wait
        if first_wait:
            first_wait = False
            return "email_page"
        kwargs["on_page_observed"]({"url": driver.current_url, "text": "页面快照"})
        return "otp"

    with _email_flow(clock, driver) as stack:
        stack.enter_context(patch.object(email_otp, "_check_manual_stop"))
        submit = stack.enter_context(patch.object(email_otp, "_submit_email_step", side_effect=(
            [email_otp._EmailFrontendNotReady("尚未接管"), None] if path == "csrf_then_ui" else None
        )))
        stack.enter_context(patch.object(email_otp, "_email_ui_submission_state", return_value=None))
        fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth", return_value=(
            {"ok": False, "not_dispatched": True, "stage": "csrf"}
            if path == "csrf_then_ui" else {"ok": True}
        )))
        waiting = stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", side_effect=wait))
        recovery = stack.enter_context(patch.object(email_otp, "recover_submission_page"))
        reload_page = stack.enter_context(patch.object(email_otp, "_reload_blank_chatgpt_auth_shell"))
        if error:
            with pytest.raises(AuthPageError) as caught:
                email_otp._submit_email_and_wait_next(driver, "unit@example.test", on_page_observed=observe)
            assert caught.value is failure
        else:
            assert email_otp._submit_email_and_wait_next(
                driver, "unit@example.test", on_page_observed=observe,
            ) == "otp"
    assert len(observed) == 1
    assert submit.call_count == (2 if path == "csrf_then_ui" else 1)
    assert fallback.call_count == (0 if path == "ui" else 1)
    assert waiting.call_count == (2 if path == "nextauth" else 1)
    assert all(call.kwargs["on_page_observed"] is observe for call in waiting.call_args_list)
    assert waiting.call_args.kwargs["timeout"] == (20 if path == "ui" else 35)
    recovery.assert_not_called()
    reload_page.assert_not_called()
    assert clock.now == 0


def test_default_wrapper_keeps_observer_absent_for_existing_callers():
    clock = _Clock()
    driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login")
    with _email_flow(clock, driver) as stack:
        stack.enter_context(patch.object(email_otp, "_submit_email_step"))
        waiting = stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"))
        assert email_otp._submit_email_and_wait_next(driver, "unit@example.test") == "otp"
    assert "on_page_observed" not in waiting.call_args.kwargs


@pytest.mark.parametrize("other_helpers", [False, True])
def test_email_page_monitor_only_enabled_for_local_roxy_registration(other_helpers):
    flow = resume.ResumeSessionFlowTests()
    helpers = SimpleNamespace(driver_name="roxy_oss", submit_email_and_wait_next=Mock(), complete_profile_page=Mock()) if other_helpers else None
    with flow.run_context() as (driver, mocks):
        driver.current_url = "https://auth.openai.com/log-in"
        mocks["navigate"].side_effect = None
        submit = helpers.submit_email_and_wait_next if helpers is not None else mocks["_submit_email_and_wait_next"]
        submit.side_effect = RuntimeError("单测在邮箱提交处结束")
        result = flow.run_registration(_browser_helpers=helpers)
    assert not result["success"]
    assert callable(submit.call_args.kwargs.get("on_page_observed")) is (not other_helpers)


@pytest.mark.parametrize("text,code", PAGE_ERRORS)
@pytest.mark.parametrize("phase,history_unknown,expected_phase,unknown,not_submitted", [
    (None, False, None, False, True),
    ("prepared", False, "not_dispatched", False, True),
    ("not_dispatched", False, "not_dispatched", False, True),
    ("ui_dispatched", False, "unknown", True, False),
    ("request_observed", False, "unknown", True, False),
    ("response_observed", False, "unknown", True, False),
    ("unknown", False, "unknown", True, False),
    ("prepared", True, "prepared", True, False),
    (None, True, None, True, False),
    ("confirmed", False, "confirmed", False, False),
])
def test_page_error_keeps_reason_and_current_or_historical_submission_boundary(
    text, code, phase, history_unknown, expected_phase, unknown, not_submitted,
):
    receipt = BrowserSubmissionReceipt(
        kind="email", stage="submit_email", endpoint_kind="email_submit", phase=phase,
        http_status=200 if phase in {"response_observed", "confirmed"} else None,
    ) if phase else None
    history = [BrowserSubmissionReceipt(kind="email", stage="submit_email", phase="unknown")] if history_unknown else []
    driver = SimpleNamespace(_browser_submission_receipt=receipt, _browser_submission_receipts=history)
    with pytest.raises(AuthPageError) as caught:
        roxy._observe_registration_email_page(driver, {"url": "https://auth.openai.com/log-in", "text": text})
    assert caught.value.code == code
    assert caught.value.submission_unknown is unknown
    assert caught.value.not_submitted is not_submitted
    assert roxy._is_registration_request_unknown(caught.value) is unknown
    assert driver._browser_submission_receipt is receipt
    if receipt is not None:
        assert receipt.phase == expected_phase
        assert receipt.http_status == (200 if phase in {"response_observed", "confirmed"} else None)
        assert receipt.error_type == (code if expected_phase in {"unknown", "not_dispatched"} and phase != "not_dispatched" else "")
    if history_unknown:
        assert history[0].phase == "unknown"


@pytest.mark.parametrize("snapshot", [
    {"url": "https://untrusted.example.test/log-in", "text": "Operation timed out"},
    {"url": "https://auth.openai.com:8443/log-in", "text": "Operation timed out"},
    {"url": "https://auth.openai.com/log-in", "error": "页面脚本暂时不可读"},
    {"url": "https://auth.openai.com/log-in", "text": "正在加载"},
])
def test_untrusted_or_unreadable_page_keeps_existing_wait(snapshot):
    receipt = BrowserSubmissionReceipt(kind="email", stage="submit_email", phase="ui_dispatched")
    driver = SimpleNamespace(_browser_submission_receipt=receipt)
    assert roxy._observe_registration_email_page(driver, snapshot) is None
    assert receipt.phase == "ui_dispatched"


@pytest.mark.parametrize("phase", [None, "prepared"])
def test_active_ui_receipt_cannot_be_reclassified_as_not_submitted(phase):
    receipt = BrowserSubmissionReceipt(kind="email", stage="submit_email", phase=phase) if phase else None
    ui_receipt = {"id": "original-ui-submission"}
    driver = SimpleNamespace(_browser_submission_receipt=receipt, _email_submission_receipt=ui_receipt)
    with pytest.raises(AuthPageError) as caught:
        roxy._observe_registration_email_page(driver, {
            "url": "https://auth.openai.com/log-in", "text": "Operation timed out",
        })
    assert caught.value.submission_unknown is True
    assert caught.value.not_submitted is False
    assert driver._email_submission_receipt is ui_receipt
    assert receipt is None or receipt.phase == "prepared"


@pytest.mark.parametrize("phase", [None, "prepared", "confirmed"])
@pytest.mark.parametrize("durable", [False, True, "unavailable"])
def test_new_driver_checks_original_attempt_durable_history_only_after_explicit_page_error(phase, durable):
    receipt = BrowserSubmissionReceipt(kind="email", stage="submit_email", phase=phase) if phase else None
    driver = SimpleNamespace(_browser_submission_receipt=receipt,
                             _registration_fact_context={"attempt_id": 41, "run_id": 71})
    with patch("core.storage.registration.has_unresolved_submission_facts", return_value=durable is True,
               side_effect=RuntimeError("历史事实暂不可读") if durable == "unavailable" else None) as pending, patch(
        "core.storage.registration.record_submission_fact", return_value={},
    ) as record_fact:
        with pytest.raises(AuthPageError) as caught:
            roxy._observe_registration_email_page(driver, {
                "url": "https://auth.openai.com/log-in", "text": "Operation timed out",
            })
    pending.assert_called_once_with(41)
    assert caught.value.code == "auth_operation_timeout"
    assert caught.value.submission_unknown is (durable is not False)
    assert caught.value.not_submitted is (durable is False and phase in {None, "prepared"})
    if receipt is not None:
        assert receipt.phase == ("not_dispatched" if durable is False and phase == "prepared" else phase)
    if durable is not False or phase != "prepared":
        record_fact.assert_not_called()


@pytest.mark.parametrize("explicit_error,in_memory_pending", [(False, False), (True, True)])
def test_normal_page_and_existing_pending_do_not_poll_durable_history(explicit_error, in_memory_pending):
    driver = SimpleNamespace(_registration_fact_context={"attempt_id": 41})
    if in_memory_pending:
        driver._browser_submission_receipts = [BrowserSubmissionReceipt(kind="email", stage="submit_email", phase="unknown")]
    with patch("core.storage.registration.has_unresolved_submission_facts") as pending:
        if explicit_error:
            with pytest.raises(AuthPageError):
                roxy._observe_registration_email_page(driver, {
                    "url": "https://auth.openai.com/log-in", "text": "Operation timed out",
                })
        else:
            roxy._observe_registration_email_page(driver, {
                "url": "https://auth.openai.com/log-in", "text": "继续输入邮箱",
            })
    pending.assert_not_called()


@pytest.mark.parametrize("text,code", PAGE_ERRORS)
def test_actual_email_wait_checks_error_before_advanced_state_and_receipt_cleanup(text, code):
    clock = _Clock()
    receipt = BrowserSubmissionReceipt(kind="email", stage="submit_email", phase="ui_dispatched")
    ui_receipt = {"id": "original"}
    driver = SimpleNamespace(current_url="https://auth.openai.com/log-in/password",
                             _email_submission_receipt=ui_receipt, _browser_submission_receipt=receipt)
    with patch.object(email_otp, "time", clock), patch.object(
        email_otp, "_page_snapshot", return_value={"url": driver.current_url, "text": text},
    ), patch.object(email_otp, "_check_manual_stop"), patch.object(
        email_otp, "_email_submit_advanced_state", return_value="password",
    ) as advanced, patch.object(email_otp, "_email_ui_submission_state") as ui_state, patch.object(
        email_otp, "recover_submission_page",
    ) as recover:
        with pytest.raises(AuthPageError) as caught:
            email_otp._wait_email_submit_next_state(
                driver, "unit@example.test", timeout=30, budget=StageBudget(30, clock=clock.time),
                on_page_observed=lambda page: roxy._observe_registration_email_page(driver, page),
            )
    assert caught.value.code == code
    assert caught.value.submission_unknown is True
    assert clock.now == 0
    assert driver._email_submission_receipt is ui_receipt
    assert driver._browser_submission_receipt is receipt
    assert receipt.phase == "unknown"
    advanced.assert_not_called()
    ui_state.assert_not_called()
    recover.assert_not_called()


def test_observer_cancellation_reaches_caller_without_recovery_or_unknown_rewrite():
    clock = _Clock()
    driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login")
    cancelled = CancellationRequested("用户停止")
    observer = Mock(side_effect=cancelled)
    with _email_flow(clock, driver) as stack:
        stack.enter_context(patch.object(email_otp, "_submit_email_step"))
        stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", side_effect=lambda *_args, **kwargs: kwargs["on_page_observed"]({})))
        recovery = stack.enter_context(patch.object(email_otp, "recover_submission_page"))
        with pytest.raises(CancellationRequested) as caught:
            email_otp._submit_email_and_wait_next(driver, "unit@example.test", on_page_observed=observer)
    assert caught.value is cancelled
    recovery.assert_not_called()


@pytest.mark.parametrize("text,code", PAGE_ERRORS)
@pytest.mark.parametrize("phase,history_unknown,unknown", [
    ("prepared", False, False), ("ui_dispatched", False, True),
    ("prepared", True, True), ("confirmed", False, False),
])
def test_roxy_projects_original_page_error_and_retains_original_identity(text, code, phase, history_unknown, unknown):
    flow = resume.ResumeSessionFlowTests()
    receipt = BrowserSubmissionReceipt(kind="email", stage="submit_email", phase=phase)
    old = BrowserSubmissionReceipt(kind="email", stage="submit_email", phase="unknown")
    with flow.run_context(opened_profile="original-profile") as (driver, mocks), patch(
        "core.storage.registration.record_submission_fact", return_value={},
    ) as record_fact, patch("core.storage.registration.has_unresolved_submission_facts", return_value=False):
        mocks["navigate"].side_effect = None
        driver._browser_submission_receipt = receipt
        driver._browser_submission_receipts = [old] if history_unknown else []

        def submit(*_args, **kwargs):
            kwargs["on_page_observed"]({"url": "https://auth.openai.com/log-in", "text": text})

        mocks["_submit_email_and_wait_next"].side_effect = submit
        result = flow.run_registration(existing_password=None)
    assert not result["success"]
    assert result["error_code"] == result["cause_code"] == code
    assert result["request_unknown"] is unknown
    assert result["email_submission_unconfirmed"] is unknown
    assert result["email"] == "resume@example.test"
    assert result["auth"]["code"] == code
    assert result["auth"].get("reconcile_required", False) is unknown
    assert result["cf_proxy_rotation_ready"] is False
    mocks["release"].assert_not_called()
    mocks["retain"].assert_called_once()
    mocks["_fill_password_page_if_present"].assert_not_called()
    mocks["client"].return_value.discard_profile.assert_not_called()
    mocks["navigate"].assert_called_once()
    mocks["browser_resume_persist"].assert_called()
    assert driver._registration_fact_context["attempt_id"] == 41
    assert receipt.phase == ("unknown" if phase == "ui_dispatched" else "not_dispatched" if phase == "prepared" and not history_unknown else phase)
    if record_fact.call_count:
        assert record_fact.call_args.args[0] == 41
        assert record_fact.call_args.kwargs["run_id"] == 71
        assert record_fact.call_args.kwargs["job_id"] == 31
