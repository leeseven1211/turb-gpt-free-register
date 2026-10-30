"""用真实 role/aria 关系覆盖新版 Authenticator 开关识别边界。"""
from html.parser import HTMLParser
from unittest.mock import Mock, patch

import pytest
from selenium.webdriver.common.by import By

from core.auth.browser import mfa_auth


class _Element:
    def __init__(self, tag, attrs, parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.content = []

    def get_attribute(self, name):
        if name in {"textContent", "innerText"}:
            return "".join(item.get_attribute("textContent") if isinstance(item, _Element) else item
                           for item in self.content)
        return self.attrs.get(name)

    def is_displayed(self):
        return "hidden" not in self.attrs and "display:none" not in self.attrs.get("style", "").replace(" ", "") \
            and (self.parent is None or self.parent.is_displayed())

    def is_enabled(self):
        return "disabled" not in self.attrs and self.attrs.get("aria-disabled") != "true"


class _Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.nodes = []
        self.stack = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = _Element(tag, attrs, self.stack[-1] if self.stack else None)
        if self.stack:
            self.stack[-1].content.append(node)
        self.nodes.append(node)
        self.stack.append(node)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].content.append(data)


class _Driver:
    def __init__(self, html, url="https://chatgpt.com/#settings/Security"):
        self.nodes = _Document(html).nodes
        self.current_url = url
        self.calls = []

    def find_elements(self, by, value):
        self.calls.append((by, value))
        if by == By.ID:
            return [node for node in self.nodes if node.attrs.get("id") == value]
        assert by == By.CSS_SELECTOR
        if value == '[data-testid="mfa-authenticator-toggle"]':
            return [node for node in self.nodes if node.attrs.get("data-testid") == "mfa-authenticator-toggle"]
        if value == 'input[name="totp_otp"]':
            return [node for node in self.nodes if node.tag == "input" and node.attrs.get("name") == "totp_otp"]
        assert value == '[role="switch"][aria-labelledby]'
        return [node for node in self.nodes if node.attrs.get("role") == "switch" and "aria-labelledby" in node.attrs]


def _switch(label="ऑथेंटिकेटर ऐप", *, name="authenticator", extra=""):
    return (
        f'<span id="{name}-label">{label}</span>'
        f'<span id="{name}-description">ऑथेंटिकेटर ऐप से वन-टाइम कोड इस्तेमाल करें</span>'
        f'<button id="{name}" role="switch" aria-checked="false" data-state="unchecked" '
        f'aria-labelledby="{name}-label" aria-describedby="{name}-description" {extra}></button>'
    )


def test_legacy_testid_keeps_priority_over_multiple_new_switches():
    driver = _Driver(
        '<button id="legacy" data-testid="mfa-authenticator-toggle"></button>'
        + _switch(name="new-one") + _switch(name="new-two")
    )
    found = mfa_auth._find_authenticator_toggle(driver)
    assert found.get_attribute("id") == "legacy"
    assert driver.calls == [(By.CSS_SELECTOR, '[data-testid="mfa-authenticator-toggle"]')]


@pytest.mark.parametrize("label", [
    "ऑथेंटिकेटर ऐप", "Authenticator app", "Authenticator", "身份验证器应用", "驗證器應用程式", "認証アプリ",
])
def test_exact_label_selects_authenticator_among_sms_and_lockdown_switches(label):
    driver = _Driver(
        _switch("SMS", name="sms") + _switch(label) + _switch("Lockdown mode", name="lockdown")
    )
    found = mfa_auth._find_authenticator_toggle(driver)
    assert found is not None
    assert found.get_attribute("id") == "authenticator"
    assert found.get_attribute("aria-checked") == "false"


@pytest.mark.parametrize("url", [
    "https://chatgpt.com/#settings/Security", "https://chatgpt.com/#settings/security/",
    "https://chatgpt.com/settings/security", "https://chatgpt.com:443/settings/security/",
])
def test_fallback_accepts_only_known_security_routes(url):
    assert mfa_auth._find_authenticator_toggle(_Driver(_switch(), url)) is not None


@pytest.mark.parametrize("url", [
    "https://chatgpt.com/", "https://chatgpt.com/#settings/General",
    "https://chatgpt.com/auth/login#settings/Security", "https://chatgpt.com/settings/security/other",
    "http://chatgpt.com/#settings/Security", "https://chatgpt.com.evil.test/#settings/Security",
    "https://private@chatgpt.com/#settings/Security", "https://chatgpt.com:444/#settings/Security",
    "https://auth.openai.com/#settings/Security", "not-a-url",
])
def test_fallback_rejects_untrusted_origin_or_nonsecurity_page(url):
    assert mfa_auth._find_authenticator_toggle(_Driver(_switch(), url)) is None


def test_visible_duplicate_authenticator_switches_are_ambiguous():
    assert mfa_auth._find_authenticator_toggle(_Driver(_switch(name="one") + _switch(name="two"))) is None


def test_hidden_or_disabled_matches_do_not_hide_the_unique_available_switch():
    driver = _Driver(_switch(name="hidden", extra="hidden") + _switch(name="disabled", extra="disabled") + _switch())
    found = mfa_auth._find_authenticator_toggle(driver)
    assert found.get_attribute("id") == "authenticator"


@pytest.mark.parametrize("label", ["MFA", "OTP", "SMS", "Authenticator app SMS", "Lockdown mode"])
def test_generic_mfa_otp_and_partial_names_do_not_identify_authenticator(label):
    assert mfa_auth._find_authenticator_toggle(_Driver(_switch(label))) is None


def test_control_text_and_description_cannot_replace_the_labelledby_name():
    driver = _Driver(
        '<span id="sms-label">SMS</span><span id="description">Authenticator app</span>'
        '<button role="switch" aria-labelledby="sms-label" aria-describedby="description">Authenticator app</button>'
        '<button role="switch" aria-label="Authenticator app">Authenticator app</button>'
    )
    assert mfa_auth._find_authenticator_toggle(driver) is None


def test_missing_or_duplicate_label_targets_are_rejected():
    html = '<span id="label">Authenticator app</span><span id="label">Authenticator app</span>'
    html += '<button role="switch" aria-labelledby="label"></button>'
    html += '<button role="switch" aria-labelledby="absent"></button>'
    assert mfa_auth._find_authenticator_toggle(_Driver(html)) is None


def test_disable_confirmation_uses_the_modern_authenticator_switch():
    driver = _Driver(_switch())
    toggle = mfa_auth._find_authenticator_toggle(driver)
    toggle.attrs.update({"aria-checked": "true", "data-state": "checked"})
    driver.execute_script = Mock(return_value=None)

    def disable(_driver, _element, **_kwargs):
        toggle.attrs.update({"aria-checked": "false", "data-state": "unchecked"})

    with patch.object(mfa_auth, "_human_click", side_effect=disable) as click:
        mfa_auth._disable_roxy_2fa(driver, toggle)
    click.assert_called_once_with(driver, toggle, label="mfa_authenticator_disable")


def test_reconfiguration_and_activation_confirmation_reuse_the_modern_switch():
    driver = _Driver(_switch())
    toggle = mfa_auth._find_authenticator_toggle(driver)
    toggle.attrs.update({"aria-checked": "true", "data-state": "checked"})
    secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
    field, verify_button = object(), object()
    on_disabled = Mock()

    def disable(*_args):
        toggle.attrs.update({"aria-checked": "false", "data-state": "unchecked"})

    def click(_driver, _element, *, label):
        if label == "totp_verify":
            toggle.attrs.update({"aria-checked": "true", "data-state": "checked"})

    with (
        patch.object(mfa_auth, "_open_chatgpt_security_settings", return_value=toggle),
        patch.object(mfa_auth, "_disable_roxy_2fa", side_effect=disable) as disable_existing,
        patch.object(mfa_auth, "_wait_mfa_enrollment_step", return_value=("totp", field)),
        patch.object(mfa_auth, "_manual_totp_secret", return_value=secret),
        patch.object(mfa_auth, "_human_type_text"),
        patch.object(mfa_auth, "_button_after_input", return_value=verify_button),
        patch.object(mfa_auth, "_human_click", side_effect=click) as human_click,
        patch.object(mfa_auth.time, "time", return_value=100.0),
    ):
        result = mfa_auth.setup_roxy_2fa(
            driver, "unit@example.test", force_reconfigure=True, on_disabled=on_disabled,
        )
    assert result == secret
    disable_existing.assert_called_once_with(driver, toggle)
    on_disabled.assert_called_once_with()
    assert [call.kwargs["label"] for call in human_click.call_args_list] == ["mfa_authenticator_toggle", "totp_verify"]
