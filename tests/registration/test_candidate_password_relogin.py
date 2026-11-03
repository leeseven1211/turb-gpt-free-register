"""候选密码恢复在交接后续认证之前完成独立确认。"""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.auth.browser import password_auth
from core.auth.browser.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from core.codex.roxy import oauth
from tests.registration.test_registration_password_flow import _saved_password_refresh_flow


EMAIL = "candidate@example.test"
CANDIDATE = "CandidateFixture123!"


def _session():
    checkpoint = SimpleNamespace(
        purpose="registration", state="unknown", password=CANDIDATE, old_password="OldFixture123!",
        email=EMAIL, attempt_id=20, registration_run_id=30,
        registration_execution_id="candidate-execution",
    )
    recovery = SimpleNamespace(checkpoint=checkpoint, prepare=Mock(return_value=CANDIDATE), confirm=Mock())

    def confirm(_driver, **_kwargs):
        checkpoint.state = "confirmed"
        return CANDIDATE

    recovery.confirm_candidate_login = Mock(side_effect=confirm)
    return recovery


@contextmanager
def _candidate_relogin_flow(*, landing="profile", paired=True):
    with _saved_password_refresh_flow(landing=landing) as flow, ExitStack() as stack:
        driver = flow.driver
        driver._registration_fact_context = {
            "attempt_id": 20, "run_id": 30, "execution_id": "candidate-execution", "job_id": None,
        }
        driver._registration_retained_identity_required = True

        def state(_driver):
            inputs = {
                "profile": [{"name": "name", "type": "text"}],
                "otp": [{"name": "code", "type": "text", "autocomplete": "one-time-code"}],
                "mfa": [{"name": "totp", "type": "text"}],
            }.get(driver.state, [{"type": "password"}] if driver.state == "password" else [])
            return {"url": driver.current_url, "inputs": inputs, "buttons": [{"type": "submit"}], "errors": []}

        for name in ("_clear_confirmed_email_submission", "_safe_get", "human_delay", "_maybe_accept", "clear_roxy_browser_auth_state", "_report_login_stage", "_auth_checkpoint", "check_cancelled"):
            stack.enter_context(patch.object(oauth, name))
        stack.enter_context(patch.object(oauth, "time", SimpleNamespace(
            time=lambda: flow.clock.value, monotonic=lambda: flow.clock.value,
            sleep=lambda seconds: setattr(flow.clock, "value", flow.clock.value + seconds),
        )))
        stack.enter_context(patch("core.auth.browser.email_otp._submit_email_and_wait_next", return_value="login_password"))
        stack.enter_context(patch.object(oauth, "_login_challenge_state", side_effect=state))
        stack.enter_context(patch.object(oauth, "_is_login_password_page", side_effect=lambda _d: driver.state == "password"))
        stack.enter_context(patch.object(oauth, "_is_email_verification_page", side_effect=lambda _d: driver.state == "otp"))
        stack.enter_context(patch.object(oauth, "_is_totp_login_page", side_effect=lambda _d, *_args: driver.state == "mfa"))
        stack.enter_context(patch.object(oauth, "_is_login_advanced", side_effect=lambda _d, *_args: driver.state == "session"))
        stack.enter_context(patch.object(oauth, "_has_access_token", return_value=False))
        stack.enter_context(patch.object(oauth, "_fill_password_page_if_present", side_effect=password_auth._fill_password_page_if_present))
        stack.enter_context(patch("core.storage.registration.record_submission_fact", side_effect=lambda _attempt_id, **fact: fact))
        ordinary = stack.enter_context(patch.object(password_auth, "complete_saved_password_relogin", side_effect=ValueError("已保存密码重登录的原密码不匹配")))

        def observe(_driver, phase, *, receipt=None, **changes):
            result = record_browser_submission_fact(_driver, phase, receipt=receipt, **changes)
            if phase == "confirmed" and paired:
                receipt.dispatch_target_id = "candidate-target"
                receipt.request_binding = ("candidate-target", receipt.submission_id)
                receipt.response_binding = receipt.request_binding
                receipt.http_status = 200
            return result

        flow.facts.side_effect = observe
        yield SimpleNamespace(**vars(flow), ordinary=ordinary)


def test_refreshed_candidate_login_uses_atomic_confirmation_before_profile_handoff():
    recovery = _session()
    assert recovery.checkpoint.password != recovery.checkpoint.old_password
    with _candidate_relogin_flow() as flow:
        result = oauth._relogin_after_password_reset(
            flow.driver, EMAIL, CANDIDATE, "", Mock(), recovery=recovery, allow_profile_handoff=True,
        )
        old, new = flow.driver._browser_submission_receipts
        assert result == "profile_handoff"
        assert flow.driver.typed == [CANDIDATE, CANDIDATE]
        assert len(flow.driver.queues) == 2
        recovery.confirm_candidate_login.assert_called_once_with(
            flow.driver, email=EMAIL, password=CANDIDATE, receipt=new, original=old,
        )
        assert recovery.checkpoint.state == "confirmed"
        assert flow.driver._registration_retained_identity_required is False
        recovery.confirm.assert_not_called()
        flow.ordinary.assert_not_called()


@pytest.mark.parametrize("landing,expected", [("otp", "email_otp"), ("mfa", "advanced")])
def test_refreshed_candidate_is_confirmed_before_otp_or_totp(landing, expected):
    recovery = _session()
    with _candidate_relogin_flow(landing=landing) as flow:
        def submit_totp(_driver, _email, _secret):
            assert recovery.checkpoint.state == "confirmed"
            recovery.confirm_candidate_login.assert_called_once()
            flow.driver.state = "session"

        with patch.object(oauth, "_submit_saved_login_totp", side_effect=submit_totp) as totp:
            assert oauth._relogin_after_password_reset(
                flow.driver, EMAIL, CANDIDATE, "fixture-secret", Mock(), recovery=recovery,
                allow_profile_handoff=True,
            ) == expected
        assert totp.call_count == (1 if landing == "mfa" else 0)
        recovery.confirm_candidate_login.assert_called_once()


def test_late_response_waits_for_same_receipt_without_extra_submission():
    recovery = _session()
    with _candidate_relogin_flow(paired=False) as flow:
        observed = []

        def tick(seconds):
            flow.clock.value += seconds
            receipt = getattr(flow.driver, "_browser_submission_receipt", None)
            if receipt is not None and receipt.phase == "confirmed":
                observed.append(receipt.submission_id)
                if len(observed) == 2:
                    receipt.dispatch_target_id = "candidate-target"
                    receipt.request_binding = ("candidate-target", receipt.submission_id)
                    receipt.response_binding = receipt.request_binding
                    receipt.http_status = 200

        with patch.object(oauth.time, "sleep", side_effect=tick):
            assert oauth._relogin_after_password_reset(
                flow.driver, EMAIL, CANDIDATE, "", Mock(), recovery=recovery, allow_profile_handoff=True,
            ) == "profile_handoff"
        assert len(observed) == 2
        assert len(set(observed)) == 1
        assert len(flow.driver.queues) == 2
        recovery.confirm_candidate_login.assert_called_once()


@pytest.mark.parametrize("changes", [
    {"response_binding": ("other-target", "other-request")},
    {"http_status": 401}, {"http_method": "GET"},
    {"auth_error": {"code": "password_reset_required"}},
    {"phase": "response_observed"},
])
def test_incomplete_candidate_evidence_stops_before_handoff(changes):
    recovery = _session()
    with _candidate_relogin_flow() as flow:
        observe = flow.facts.side_effect

        def altered(_driver, phase, *, receipt=None, **metadata):
            result = observe(_driver, phase, receipt=receipt, **metadata)
            if phase == "confirmed":
                for name, value in changes.items():
                    setattr(receipt, name, value)
            return result

        flow.facts.side_effect = altered
        with pytest.raises(oauth.PasswordResetTransitionUnknown, match="候选密码认证"):
            oauth._relogin_after_password_reset(
                flow.driver, EMAIL, CANDIDATE, "", Mock(), recovery=recovery, allow_profile_handoff=True,
            )
        recovery.confirm_candidate_login.assert_not_called()
        recovery.confirm.assert_not_called()
        assert recovery.checkpoint.state == "unknown"
        assert flow.driver._registration_retained_identity_required is True
        assert len(flow.driver.queues) == 2


@pytest.mark.parametrize("landing", ["profile", "otp", "mfa"])
def test_store_confirmation_failure_does_not_submit_next_challenge(landing):
    recovery = _session()
    recovery.confirm_candidate_login.side_effect = RuntimeError("password_recovery_password_conflict")
    with _candidate_relogin_flow(landing=landing) as flow, patch.object(oauth, "_submit_saved_login_totp") as totp:
        with pytest.raises(RuntimeError, match="password_recovery_password_conflict"):
            oauth._relogin_after_password_reset(
                flow.driver, EMAIL, CANDIDATE, "fixture-secret", Mock(), recovery=recovery,
                allow_profile_handoff=True,
            )
        totp.assert_not_called()
        assert len(flow.driver.queues) == 2
        assert recovery.checkpoint.state == "unknown"
        assert flow.driver._registration_retained_identity_required is True


def test_candidate_confirmation_runtime_error_is_not_a_password_prepare_retry():
    receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password", phase="not_dispatched")
    driver = SimpleNamespace(
        current_url="https://auth.openai.com/log-in/password", _browser_submission_receipt=receipt,
        refresh=Mock(), timeouts=SimpleNamespace(page_load=90), set_page_load_timeout=Mock(),
    )
    callback = Mock(side_effect=RuntimeError("password_form_not_ready: 确认事务失败"))

    def fill(_driver, _email, **kwargs):
        kwargs["on_candidate_password_confirmed"](receipt)

    with patch.object(oauth, "_fill_password_page_if_present", side_effect=fill) as filled:
        with pytest.raises(RuntimeError, match="确认事务失败"):
            oauth._submit_saved_login_password(driver, EMAIL, CANDIDATE, on_candidate_password_confirmed=callback)
    assert filled.call_count == 1
    driver.refresh.assert_not_called()


@pytest.mark.parametrize("page,expected", [
    ("profile", "profile_handoff"), ("otp", "email_otp"), ("mfa", "advanced"), ("session", "advanced"),
])
def test_direct_challenge_handoff_cannot_bypass_candidate_barrier(page, expected):
    with _candidate_relogin_flow() as flow:
        flow.driver.state = page
        flow.driver.current_url = "https://auth.openai.com/about-you" if page == "profile" else "https://auth.openai.com/mfa"
        confirmed = []
        callback = Mock(side_effect=lambda *_args, **_kwargs: confirmed.append("confirmed"))

        def totp(_driver, _email, _secret):
            assert confirmed
            flow.driver.state = "session"

        with patch.object(oauth, "_submit_saved_login_password") as password_submit, patch.object(
            oauth, "_submit_saved_login_totp", side_effect=totp,
        ):
            assert oauth._complete_login_challenge_after_email(
                flow.driver, EMAIL, CANDIDATE, "fixture-secret", allow_profile_handoff=True,
                password_already_submitted=True, on_candidate_password_confirmed=callback,
            ) == expected
        assert confirmed
        password_submit.assert_not_called()


def test_helper_bypass_without_fresh_password_evidence_keeps_recovery_pending():
    recovery = _session()
    with _candidate_relogin_flow() as flow, patch.object(
        oauth, "_complete_login_challenge_after_email", return_value="profile_handoff",
    ):
        with pytest.raises(oauth.PasswordResetTransitionUnknown, match="候选密码认证"):
            oauth._relogin_after_password_reset(
                flow.driver, EMAIL, CANDIDATE, "", Mock(), recovery=recovery, allow_profile_handoff=True,
            )
        recovery.confirm_candidate_login.assert_not_called()
        assert flow.driver._registration_retained_identity_required is True


def test_candidate_response_observation_cannot_extend_execution_budget():
    from core.auth.browser.auth_context import AuthExecutionContext, execution_context
    from core.auth.state_machine import StageBudget

    recovery = _session()
    with _candidate_relogin_flow(paired=False) as flow:
        observe = flow.facts.side_effect
        observation_started = []

        def confirmed(_driver, phase, *, receipt=None, **metadata):
            result = observe(_driver, phase, receipt=receipt, **metadata)
            if phase == "confirmed":
                observation_started.append(flow.clock.value)
            return result

        flow.facts.side_effect = confirmed
        context = AuthExecutionContext(budget=StageBudget(10.25, clock=lambda: flow.clock.value))
        with execution_context(context), pytest.raises(oauth.PasswordResetTransitionUnknown):
            oauth._relogin_after_password_reset(
                flow.driver, EMAIL, CANDIDATE, "", Mock(), recovery=recovery, allow_profile_handoff=True,
            )
        assert observation_started
        assert flow.clock.value <= 10.25
        recovery.confirm_candidate_login.assert_not_called()


@pytest.mark.parametrize("helper_budget,expected", [(2.0, 2.0), (20.0, 5.0)])
def test_confirmation_uses_smaller_password_and_challenge_budget(helper_budget, expected):
    from core.auth.state_machine import StageBudget

    with _candidate_relogin_flow() as flow:
        receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password")

        def confirm(_receipt, *, budget, **_kwargs):
            assert budget.remaining() == expected
            raise RuntimeError("已验证原预算")

        def submit(_driver, _email, _password, **kwargs):
            kwargs["on_candidate_password_confirmed"](
                receipt, budget=StageBudget(helper_budget, clock=lambda: flow.clock.value),
            )

        with patch.object(oauth, "_submit_saved_login_password", side_effect=submit):
            with pytest.raises(RuntimeError, match="已验证原预算"):
                oauth._complete_login_challenge_after_email(
                    flow.driver, EMAIL, CANDIDATE, "", timeout=5,
                    on_candidate_password_confirmed=confirm,
                )


@pytest.mark.parametrize("shell", ["blank", "email"])
@pytest.mark.parametrize("fallback_state", ["otp", "advanced"])
@pytest.mark.parametrize("remaining", [0.0, 0.2])
def test_nextauth_candidate_handoff_keeps_original_challenge_deadline(shell, fallback_state, remaining):
    recovery = _session()
    with _candidate_relogin_flow(paired=False) as flow:
        flow.driver.state = shell
        state = {
            "url": "https://chatgpt.com/auth/login?email=candidate%40example.test",
            "inputs": [{"type": "email", "name": "email"}] if shell == "email" else [],
            "buttons": [], "errors": [],
        }
        receipt = BrowserSubmissionReceipt(
            kind="resume_login", stage="login_password", endpoint_kind="password_submit",
            http_method="POST", phase="confirmed", result="success",
        )

        def fallback(_driver, _email):
            # 模拟既有 NextAuth 导航消耗原 challenge 预算；CDP 响应仍未到达。
            flow.clock.value = 45.0 - remaining
            flow.driver._browser_submission_receipt = receipt
            flow.driver._browser_submission_receipts = [receipt]
            return {"ok": True, "state": fallback_state}

        with (
            patch.object(oauth, "_login_challenge_state", return_value=state),
            patch.object(oauth, "_email_ui_submission_state", return_value=""),
            patch.object(oauth, "_submit_email_via_browser_nextauth", side_effect=fallback) as nextauth,
            patch.object(oauth, "_submit_saved_login_password") as password_submit,
            pytest.raises(oauth.PasswordResetTransitionUnknown, match="候选密码认证"),
        ):
            oauth._relogin_after_password_reset(
                flow.driver, EMAIL, CANDIDATE, "", Mock(), recovery=recovery, allow_profile_handoff=True,
            )
        assert flow.clock.value <= 45.0
        nextauth.assert_called_once()
        password_submit.assert_not_called()
        recovery.confirm_candidate_login.assert_not_called()
        assert recovery.checkpoint.state == "unknown"
        assert flow.driver._registration_retained_identity_required is True
