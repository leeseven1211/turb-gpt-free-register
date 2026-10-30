"""Authenticator 现场结构的离线步骤识别与等待协作回归。"""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import threading

import pytest

from core.auth.browser import mfa_auth
from core.auth.state_machine import CancellationRequested


SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


def _driver(*, text="", title="", name="verification-code", url="https://chatgpt.com/settings/security", dialogs=1):
    field = Mock()
    field.get_attribute.side_effect = lambda key: {"name": name, "aria-invalid": "false"}.get(key, "")
    snapshot = {
        "url": url, "text": text, "title": "ChatGPT", "ready_state": "complete", "alerts": [],
        "dialogs": [{"title": title, "text": text, "fields": [{"element": field, "name": name,
            "autocomplete": "one-time-code", "invalid": False}]} for _ in range(dialogs)],
    }
    driver = SimpleNamespace(current_url=url, execute_script=lambda *_args: snapshot,
        find_elements=lambda _by, selector: [field] if name in selector or "one-time-code" in selector else [])
    return driver, field, snapshot


def test_modern_hindi_authenticator_is_totp_before_generic_email_selector():
    driver, field, _ = _driver(title="ऑथेंटिकेटर ऐप कनेक्ट करें",
        text="QR कोड स्कैन करें स्कैन नहीं कर पा रहे? कोड मैन्युअल रूप से डालें ऑथेंटिकेटर ऐप से 6-अंकों का कोड डालें")
    assert mfa_auth._detect_mfa_enrollment_step(driver) == ("totp", field)


@pytest.mark.parametrize("name", ["totp_otp", "verification-code"])
def test_legacy_and_modern_authenticator_dialogs_share_identification(name):
    driver, field, _ = _driver(title="Connect authenticator app", text="Scan the QR code and enter a 6-digit code", name=name)
    assert mfa_auth._detect_mfa_enrollment_step(driver) == ("totp", field)


@pytest.mark.parametrize("url", ["https://auth.openai.com/email-verification", "http://chatgpt.com/settings/security",
    "https://chatgpt.com.evil.test/settings/security", "https://private@chatgpt.com/settings/security",
    "https://chatgpt.com:444/settings/security", "https://chatgpt.com/#settings/General"])
def test_same_named_code_on_untrusted_or_wrong_page_is_not_enrollment(url):
    driver, _, _ = _driver(title="Connect authenticator app", text="Scan the QR code", url=url)
    assert mfa_auth._detect_mfa_enrollment_step(driver) == (None, None)


def test_ambiguous_visible_dialogs_and_generic_one_time_code_are_not_email():
    for dialogs in (1, 2):
        driver, _, _ = _driver(text="Enter code", dialogs=dialogs)
        assert mfa_auth._detect_mfa_enrollment_step(driver) == (None, None)


def test_real_email_challenge_requires_explicit_delivery_semantics():
    driver, field, _ = _driver(title="Check your email", text="Enter the code we sent to your email address", name="code")
    assert mfa_auth._detect_mfa_enrollment_step(driver) == ("email", field)


@pytest.mark.parametrize("text", ["SMS code sent to your phone", "Approve the push notification on your phone"])
def test_sms_and_push_are_explicitly_unsupported_instead_of_email(text):
    driver, _, _ = _driver(title="Verify your identity", text=text)
    with pytest.raises(RuntimeError, match="mfa_enrollment_unsupported"):
        mfa_auth._detect_mfa_enrollment_step(driver)


def test_visible_error_has_priority_over_totp_field():
    driver, _, snapshot = _driver(title="Connect authenticator app", text="Scan the QR code")
    snapshot["alerts"] = ["Something went wrong"]
    with pytest.raises(RuntimeError, match="mfa_enrollment_page_error"):
        mfa_auth._detect_mfa_enrollment_step(driver)


def test_success_toast_is_not_an_error_and_ready_security_page_is_explicit():
    driver, _, snapshot = _driver(text="Security settings Authenticator app", dialogs=0)
    snapshot["alerts"] = ["Authenticator enabled successfully"]
    assert mfa_auth._detect_mfa_enrollment_step(driver) == ("complete", None)


def test_unknown_dialog_missing_document_or_conflicting_dialogs_cannot_be_completion():
    for dialogs, text in ((1, "Please wait"), (2, "Security settings"), (0, "")):
        driver, _, _ = _driver(dialogs=dialogs, text=text)
        assert mfa_auth._detect_mfa_enrollment_step(driver)[0] != "complete"


def test_mail_wait_observes_totp_transition_on_original_thread_before_candidate_use():
    email_field, totp_field = object(), object()
    owner = threading.get_ident()
    checks = []
    states = [("email", email_field), ("totp", totp_field)]

    def detect(_driver):
        checks.append(threading.get_ident())
        return states.pop(0) if states else ("totp", totp_field)

    def provider(_email, *, after_ts, max_wait, page_checkpoint, **_kwargs):
        assert after_ts == 123.0
        assert 0 < max_wait <= 240
        page_checkpoint()
        return "123456"

    with patch.object(mfa_auth, "_detect_mfa_enrollment_step", side_effect=detect):
        assert mfa_auth._wait_mfa_email_code(object(), "unit@example.test", 123.0, provider) == ("totp", totp_field, None)
    assert checks and set(checks) == {owner}


def test_mail_wait_preserves_cancellation_and_rejects_opaque_blocking_provider():
    with patch.object(mfa_auth, "_check_manual_stop", side_effect=CancellationRequested("停止")):
        with pytest.raises(CancellationRequested):
            mfa_auth._wait_mfa_email_code(object(), "unit@example.test", 123.0, Mock())
    with patch.object(mfa_auth, "_check_manual_stop"), patch.object(mfa_auth, "_detect_mfa_enrollment_step", return_value=("email", object())):
        with pytest.raises(RuntimeError, match="mfa_otp_provider_not_cooperative"):
            mfa_auth._wait_mfa_email_code(object(), "unit@example.test", 123.0, lambda email, after_ts: "123456")


def test_manual_key_rerender_reacquires_modern_field_before_secret_read():
    old_field, new_field, manual = object(), object(), object()
    driver = Mock()
    driver.execute_script.return_value = manual
    fields_read = []

    def read(_driver, field):
        fields_read.append(field)
        return SECRET if field is new_field else None

    with patch.object(mfa_auth, "_read_totp_secret_from_dialog", side_effect=read), \
            patch.object(mfa_auth, "_detect_mfa_enrollment_step", return_value=("totp", new_field)), \
            patch.object(mfa_auth, "_human_click"):
        assert mfa_auth._manual_totp_secret(driver, old_field, timeout=2) == SECRET
    assert fields_read == [old_field, new_field]
    assert "स्कैन नहीं कर पा रहे" in driver.execute_script.call_args.args[0]


def test_activation_uses_reacquired_field_persists_first_and_requires_same_email_probe():
    events = []
    toggle = Mock()
    enabled = [False]
    toggle.get_attribute.side_effect = lambda key: "true" if key == "aria-checked" and enabled[0] else "false"
    old_field, fresh_field, button = object(), object(), object()

    def click(_driver, element, **_kwargs):
        if element is button:
            enabled[0] = True
            events.append("激活")

    with patch.object(mfa_auth, "_open_chatgpt_security_settings", return_value=toggle), \
            patch.object(mfa_auth, "_wait_mfa_enrollment_step", return_value=("totp", old_field)), \
            patch.object(mfa_auth, "_manual_totp_secret", return_value=SECRET), \
            patch.object(mfa_auth, "_detect_mfa_enrollment_step", side_effect=lambda _driver: ("complete", None) if enabled[0] else ("totp", fresh_field)), \
            patch.object(mfa_auth, "_find_authenticator_toggle", return_value=toggle), \
            patch.object(mfa_auth, "_human_click", side_effect=click), \
            patch.object(mfa_auth, "_human_type_text", side_effect=lambda _driver, field, *_args, **_kwargs: events.append(("输入", field))), \
            patch.object(mfa_auth, "_button_after_input", return_value=button), \
            patch.object(mfa_auth, "_probe_existing_roxy_totp", side_effect=lambda _driver, email, **_kwargs: (events.append(("核验", email)), {"confirmed": True, "reason": "totp_enabled"})[1]), \
            patch.object(mfa_auth.time, "time", return_value=100):
        assert mfa_auth.setup_roxy_2fa(object(), "unit@example.test", on_secret=lambda _secret: events.append("已存pending")) == SECRET
    assert events == ["已存pending", ("输入", fresh_field), "激活", ("核验", "unit@example.test")]
