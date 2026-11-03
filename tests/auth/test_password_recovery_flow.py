"""恢复分支以真实页面决策和持久化边界验证，外部浏览器与数据库使用替身。"""
from contextlib import ExitStack
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.codex.roxy import oauth
from core.storage.accounts import password_recovery as store


OWNER = dict(
    email="fixture@example.test", account_id=8, purpose="registration",
    operation_run_id=10, operation_execution_id="op-execution", operation_lease_token=None,
    attempt_id=20, registration_run_id=30, registration_execution_id="reg-execution",
)


def checkpoint(state="prepared", version=1):
    return store.PrivateCheckpoint(
        recovery_id=1, state=state, version=version, account_id=8, email=OWNER["email"],
        purpose="registration", operation_run_id=10, operation_execution_id="op-execution",
        attempt_id=20, registration_run_id=30, registration_execution_id="reg-execution",
        account_password_version="original-version", old_password="old-fixture-password", password="candidate-fixture-password",
    )


@pytest.fixture
def session():
    from core.auth.browser.password_recovery import PasswordRecoverySession

    current = [None]

    def prepare(*, candidate_factory, **owner):
        assert owner == OWNER
        if current[0] is None:
            current[0] = replace(checkpoint(), password=candidate_factory())
        return current[0]

    def get(recovery_id, **owner):
        assert owner == OWNER and recovery_id == 1
        return current[0]

    def transition(recovery_id, *, state, expected_version, confirmation,
                   candidate_login_submission_id=None, candidate_login_original_submission_id=None,
                   candidate_login_job_id=None, **owner):
        assert owner == OWNER and recovery_id == 1
        assert expected_version == current[0].version
        if state == "confirmed":
            assert confirmation == "candidate_login"
        if candidate_login_submission_id is not None:
            assert candidate_login_original_submission_id is None
            assert candidate_login_job_id == 31
        current[0] = replace(current[0], state=state, version=expected_version + 1)
        return current[0]

    with (
        patch.object(store, "prepare_password_recovery", side_effect=prepare),
        patch.object(store, "get_password_recovery", side_effect=get),
        patch.object(store, "transition_password_recovery", side_effect=transition),
        patch.object(store, "resume_password_recovery", side_effect=lambda **owner: current[0]),
    ):
        yield PasswordRecoverySession(**OWNER), current


def test_session_reuses_persisted_candidate_and_versions_every_transition(session):
    recovery, current = session
    factory = Mock(return_value="candidate-fixture-password")
    assert recovery.prepare(factory) == "candidate-fixture-password"
    assert recovery.prepare(factory) == "candidate-fixture-password"
    recovery.mark_started()
    recovery.mark_unknown()
    assert recovery.confirm("candidate_login") == "candidate-fixture-password"
    assert current[0].state == "confirmed" and current[0].version == 4
    assert factory.call_count == 1


def test_session_resume_does_not_create_candidate(session):
    recovery, current = session
    assert recovery.resume() is False
    current[0] = checkpoint("unknown", 3)
    assert recovery.resume() is True
    assert recovery.checkpoint.state == "unknown"


def test_failed_candidate_persistence_does_not_type_or_click():
    driver = SimpleNamespace(current_url="https://auth.openai.com/reset-password")
    recovery = SimpleNamespace(prepare=Mock(side_effect=RuntimeError("private_store_failed")))
    with patch.object(oauth, "_reset_password_targets", return_value={"ok": True, "inputs": [object()], "submit": object()}), patch.object(oauth, "_human_type_text") as typed, patch.object(oauth, "_human_click") as clicked:
        with pytest.raises(RuntimeError, match="private_store_failed"):
            oauth._submit_reset_password_and_wait(driver, OWNER["email"], "candidate-fixture-password", recovery=recovery)
    typed.assert_not_called()
    clicked.assert_not_called()


def test_click_exception_keeps_persisted_candidate_as_unknown(session):
    recovery, current = session
    driver = SimpleNamespace(current_url="https://auth.openai.com/reset-password")

    def interrupted(*_args, **_kwargs):
        assert current[0].state == "started"
        assert current[0].password == "candidate-fixture-password"
        raise RuntimeError("browser_interrupted")

    with patch.object(oauth, "_reset_password_targets", return_value={"ok": True, "inputs": [object()], "submit": object()}), patch.object(oauth, "_human_type_text"), patch.object(oauth, "human_delay"), patch.object(oauth, "_human_click", side_effect=interrupted):
        with pytest.raises(RuntimeError, match="browser_interrupted"):
            oauth._submit_reset_password_and_wait(driver, OWNER["email"], "candidate-fixture-password", recovery=recovery)
    assert current[0].state == "unknown"
    assert current[0].password == "candidate-fixture-password"


def test_recovery_reset_totp_hands_off_to_original_secret_login_instead_of_claiming_missing_secret(session):
    recovery, current = session
    driver = SimpleNamespace(current_url='https://auth.openai.com/mfa-challenge/totp')
    with (
        patch.object(oauth, '_reset_password_targets', return_value={'ok': True, 'inputs': [object()], 'submit': object()}),
        patch.object(oauth, '_human_type_text'), patch.object(oauth, 'human_delay'), patch.object(oauth, '_human_click'),
        patch.object(oauth, '_is_login_advanced', return_value=False), patch.object(oauth, '_is_totp_login_page', return_value=True),
    ):
        oauth._submit_reset_password_and_wait(driver, OWNER['email'], 'candidate-fixture-password', recovery=recovery)
    assert current[0].state == 'started'


def test_unknown_recovery_authenticates_same_candidate_without_repeating_reset(session):
    recovery, current = session
    current[0] = checkpoint("unknown", 3)
    recovery.resume()
    driver = SimpleNamespace()

    def authenticated(*_args, **_kwargs):
        recovery.confirm("candidate_login")
        return "profile_handoff"

    with patch.object(oauth, "_forgot_password_target") as forgot, patch.object(oauth, "_submit_reset_password_and_wait") as submit, patch.object(oauth, "_relogin_after_password_reset", side_effect=authenticated) as relogin:
        result = oauth._reset_password_via_email(driver, OWNER["email"], Mock(), recovery=recovery, allow_profile_handoff=True)
    assert result == "candidate-fixture-password"
    assert relogin.call_args.args[2] == "candidate-fixture-password"
    forgot.assert_not_called()
    submit.assert_not_called()


def test_prepared_recovery_reestablishes_original_email_before_using_reset_form(session):
    recovery, current = session
    current[0] = checkpoint()
    recovery.resume()
    driver = SimpleNamespace(current_url='https://auth.openai.com/reset-password')
    events = []
    with (
        patch.object(oauth, '_reset_password_targets', return_value={'ok': True}),
        patch.object(oauth, '_submit_reset_password_and_wait', side_effect=lambda *_a, **_k: events.append('submit')),
        patch.object(oauth, '_relogin_after_password_reset'),
        patch.object(oauth, 'clear_roxy_browser_auth_state', side_effect=lambda _d: events.append('clear')),
        patch.object(oauth, '_clear_confirmed_email_submission'),
        patch.object(oauth, '_safe_get'), patch.object(oauth, '_maybe_accept'), patch.object(oauth, 'human_delay'),
        patch('core.auth.browser.email_otp._submit_email_and_wait_next', side_effect=lambda _d, email, **_k: events.append(('email', email))),
        patch.object(oauth, '_is_login_password_page', return_value=True),
        patch.object(oauth, '_forgot_password_target', side_effect=lambda _d: events.append('forgot')),
    ):
        result = oauth._reset_password_via_email(driver, OWNER['email'], Mock(), recovery=recovery, allow_profile_handoff=True)
    assert result is False
    assert events == ['clear', ('email', 'fixture@example.test'), 'forgot']
    assert current[0].state == 'prepared'


def profile_state(url="https://auth.openai.com/about-you", visible=True):
    return {"url": url, "inputs": [{"name": "name", "type": "text", "visible": visible}], "buttons": [{"type": "submit", "visible": visible}], "errors": []}


@pytest.mark.parametrize("state,want", [
    (profile_state(), True),
    (profile_state("https://auth.openai.com/profile"), True),
    (profile_state("https://evil.test/about-you"), False),
    (profile_state("https://auth.openai.com.evil.test/about-you"), False),
    (profile_state("https://auth.openai.com:444/about-you"), False),
    (profile_state(visible=False), False),
    ({"url": "https://auth.openai.com/about-you", "inputs": [], "buttons": []}, False),
])
def test_profile_handoff_requires_trusted_visible_profile_form(state, want):
    assert oauth._is_password_recovery_profile_page(SimpleNamespace(), state) is want


def relogin_stack(driver, *, receipt_factory=None):
    stack = ExitStack()
    for name in ("_clear_confirmed_email_submission", "_safe_get", "human_delay", "_maybe_accept", "clear_roxy_browser_auth_state", "_report_login_stage"):
        stack.enter_context(patch.object(oauth, name))
    clock = [0.0]
    stack.enter_context(patch.object(oauth, 'time', SimpleNamespace(
        time=lambda: clock[0], monotonic=lambda: clock[0],
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )))
    stack.enter_context(patch("core.auth.browser.email_otp._submit_email_and_wait_next", return_value="login_password"))
    stack.enter_context(patch.object(oauth, "_login_challenge_state", return_value=profile_state()))
    stack.enter_context(patch.object(oauth, "_is_login_advanced", return_value=False))

    def resolve(*_args, **_kwargs):
        if receipt_factory:
            receipt = receipt_factory()
            driver._browser_submission_receipt = receipt
            driver._browser_submission_receipts = [receipt]
        return "profile_handoff"

    stack.enter_context(patch.object(oauth, "_complete_login_challenge_after_email", side_effect=resolve))
    return stack


def login_receipt(**changes):
    from core.auth.browser.browser_submission import BrowserSubmissionReceipt
    receipt = BrowserSubmissionReceipt(kind="password", stage="login_password", endpoint_kind="password_submit", http_method="POST")
    receipt.dispatch_target_id = "fixture-target"
    receipt.request_binding = ("fixture-target", "fresh-request")
    receipt.response_binding = receipt.request_binding
    receipt.transition("confirmed", result="success", http_status=200)
    for key, value in changes.items():
        setattr(receipt, key, value)
    return receipt


def test_direct_profile_after_reset_requires_fresh_candidate_login_proof(session):
    recovery, current = session
    current[0] = checkpoint("unknown", 3)
    recovery.resume()
    driver = SimpleNamespace(current_url="https://auth.openai.com/about-you", _browser_submission_receipts=[])
    with relogin_stack(driver, receipt_factory=login_receipt), patch.object(oauth, 'clear_roxy_browser_auth_state') as clear:
        assert oauth._relogin_after_password_reset(driver, OWNER["email"], current[0].password, "", Mock(), recovery=recovery, allow_profile_handoff=True) == "profile_handoff"
    clear.assert_called_once_with(driver)
    assert current[0].state == "confirmed"


@pytest.mark.parametrize("receipt_factory", [
    None,
    lambda: login_receipt(http_status=401),
    lambda: login_receipt(response_binding=("other-target", "fresh-request")),
    lambda: login_receipt(auth_error={"code": "password_reset_required"}),
    lambda: login_receipt(phase="response_observed"),
])
def test_profile_or_unpaired_login_cannot_confirm_new_password(session, receipt_factory):
    recovery, current = session
    current[0] = checkpoint("unknown", 3)
    recovery.resume()
    driver = SimpleNamespace(current_url="https://auth.openai.com/about-you", _browser_submission_receipts=[], _registration_retained_identity_required=True)
    with relogin_stack(driver, receipt_factory=receipt_factory), pytest.raises(oauth.PasswordResetTransitionUnknown):
        oauth._relogin_after_password_reset(driver, OWNER["email"], current[0].password, "", Mock(), recovery=recovery, allow_profile_handoff=True)
    assert current[0].state == "unknown"
    assert driver._registration_retained_identity_required is True


def test_confirmed_candidate_identity_passes_real_retained_profile_guard_without_email_hint(session):
    from core.registration import retained_resume

    recovery, current = session
    current[0] = checkpoint('unknown', 3)
    recovery.resume()
    driver = SimpleNamespace(
        current_url='https://auth.openai.com/about-you', _browser_submission_receipts=[],
        _registration_retained_identity_required=True, _registration_resume_login=True,
        _registration_fact_context={"attempt_id": 20, "run_id": 30, "execution_id": "reg-execution", "job_id": 31},
    )
    with relogin_stack(driver, receipt_factory=lambda: login_receipt(kind="resume_login")):
        oauth._relogin_after_password_reset(driver, OWNER['email'], current[0].password, '', Mock(), recovery=recovery, allow_profile_handoff=True)
    with (
        patch.object(retained_resume, '_email_otp_page_state', return_value=profile_state()),
        patch.object(retained_resume.registration, 'get_private_resume_context', return_value={
            'password': 'candidate-fixture-password', 'submission_facts': [],
        }),
    ):
        result = retained_resume.prepare_retained_resume(
            driver, email=OWNER['email'], existing_password='candidate-fixture-password', facts={'attempt_id': 20},
            otp_after_ts=driver._registration_otp_after_ts,
        )
    assert result.page_state == oauth.PageState.PROFILE
    assert result.restart_login is False


def test_failed_store_confirmation_keeps_retained_identity_guard(session):
    recovery, current = session
    current[0] = checkpoint('unknown', 3)
    recovery.resume()
    driver = SimpleNamespace(
        current_url='https://auth.openai.com/about-you', _browser_submission_receipts=[],
        _registration_retained_identity_required=True,
    )
    with relogin_stack(driver, receipt_factory=login_receipt), patch.object(
        store, 'transition_password_recovery', side_effect=RuntimeError('store_confirm_conflict'),
    ), pytest.raises(RuntimeError, match='store_confirm_conflict'):
        oauth._relogin_after_password_reset(driver, OWNER['email'], current[0].password, '', Mock(), recovery=recovery, allow_profile_handoff=True)
    assert driver._registration_retained_identity_required is True
    assert current[0].state == 'unknown'


def test_old_successful_password_receipt_cannot_confirm_new_candidate(session):
    recovery, current = session
    current[0] = checkpoint('unknown', 3)
    recovery.resume()
    old_receipt = login_receipt()
    driver = SimpleNamespace(
        current_url='https://auth.openai.com/about-you', _browser_submission_receipts=[old_receipt],
        _browser_submission_receipt=old_receipt,
    )
    with relogin_stack(driver), pytest.raises(oauth.PasswordResetTransitionUnknown):
        oauth._relogin_after_password_reset(driver, OWNER['email'], current[0].password, '', Mock(), recovery=recovery, allow_profile_handoff=True)
    assert current[0].state == 'unknown'


def test_relogin_authenticates_persisted_candidate_instead_of_stale_caller_password(session):
    recovery, current = session
    current[0] = checkpoint('unknown', 3)
    recovery.resume()
    driver = SimpleNamespace(current_url='https://auth.openai.com/about-you', _browser_submission_receipts=[])
    with relogin_stack(driver, receipt_factory=login_receipt), patch.object(
        oauth, '_complete_login_challenge_after_email', wraps=oauth._complete_login_challenge_after_email,
    ) as complete:
        oauth._relogin_after_password_reset(driver, OWNER['email'], 'stale-caller-password', '', Mock(), recovery=recovery, allow_profile_handoff=True)
    assert complete.call_args.args[2] == 'candidate-fixture-password'


def challenge_stack(driver):
    stack = ExitStack()
    clock = [0.0]
    stack.enter_context(patch.object(oauth, 'time', SimpleNamespace(
        time=lambda: clock[0], monotonic=lambda: clock[0],
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )))
    stack.enter_context(patch.object(oauth, '_login_challenge_state', side_effect=lambda _driver: {
        'url': driver.current_url, 'inputs': [{'type': 'password'}], 'buttons': [], 'errors': [],
    }))
    for name in ('_auth_checkpoint', '_clear_confirmed_email_submission'):
        stack.enter_context(patch.object(oauth, name))
    for name in ('_is_totp_login_page', '_is_login_advanced', '_has_access_token'):
        stack.enter_context(patch.object(oauth, name, return_value=False))
    stack.enter_context(patch.object(oauth, '_is_login_password_page', side_effect=lambda _driver: driver.current_url.endswith('/log-in/password')))
    stack.enter_context(patch.object(oauth, '_is_email_verification_page', side_effect=lambda _driver: driver.current_url.endswith('/email-verification')))
    return stack


def test_forced_recovery_keeps_checkpoint_callback_and_hands_accepted_password_to_otp(session):
    recovery, current = session
    driver = SimpleNamespace(current_url='https://auth.openai.com/log-in/password')
    callback = Mock()

    def reset(*_args, **kwargs):
        assert kwargs['on_password_submitted'] is callback
        assert kwargs['recovery'] is recovery
        current[0] = checkpoint('confirmed', 3)
        driver.current_url = 'https://auth.openai.com/email-verification'
        return current[0].password

    with challenge_stack(driver), patch.object(oauth, '_reset_password_via_email', side_effect=reset):
        state = oauth._complete_login_challenge_after_email(
            driver, OWNER['email'], 'old-fixture-password', '', otp_provider=Mock(),
            force_password_reset=True, on_password_reset_submitted=callback, password_recovery=recovery,
        )
    assert state == 'email_otp'


def test_profile_handoff_is_explicitly_enabled_and_does_not_claim_complete_session():
    driver = SimpleNamespace(current_url='https://auth.openai.com/about-you')
    with challenge_stack(driver), patch.object(oauth, '_login_challenge_state', return_value=profile_state()):
        assert oauth._complete_login_challenge_after_email(
            driver, OWNER['email'], 'candidate-fixture-password', '', allow_profile_handoff=True,
        ) == 'profile_handoff'
        with pytest.raises(RuntimeError, match='未识别到密码'):
            oauth._complete_login_challenge_after_email(driver, OWNER['email'], 'candidate-fixture-password', '')
