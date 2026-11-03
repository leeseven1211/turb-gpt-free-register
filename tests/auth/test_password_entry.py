"""密码入口只点击当前可信页面实际提供的可用链接。"""
import importlib
import importlib.util
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from selenium.common.exceptions import StaleElementReferenceException


def _module():
    name = "core.auth.browser.password_entry"
    assert importlib.util.find_spec(name) is not None, "缺少共用的真实密码入口选择器"
    return importlib.import_module(name)


class Link:
    def __init__(self, driver, href, *, shown=True, enabled=True, attrs=None, landing=None, error=None):
        self.driver, self.href = driver, href
        self.shown, self.enabled, self.attrs = shown, enabled, attrs or {}
        self.landing, self.error, self.clicks = landing, error, 0

    def is_displayed(self):
        return self.shown

    def is_enabled(self):
        return self.enabled

    def get_attribute(self, key):
        return self.href if key == "href" else self.attrs.get(key)

    def click(self):
        self.clicks += 1
        if self.error:
            raise self.error
        self.driver.current_url = self.landing or self.href


def _driver(url="https://auth.openai.com/email-verification"):
    driver = SimpleNamespace(current_url=url, links=[])
    driver.find_elements = Mock(side_effect=lambda *_args: driver.links)
    return driver


def test_entry_prefers_login_link_and_preserves_real_query_once():
    driver = _driver()
    create = Link(driver, "https://auth.openai.com/create-account/password?state=create")
    login = Link(driver, "https://auth.openai.com/log-in/password?state=offered&mode=saved")
    driver.links = [create, login]
    assert _module().open_offered_password_entry(driver, timeout=1) == "/log-in/password"
    assert driver.current_url == login.href
    assert (login.clicks, create.clicks) == (1, 0)


def test_entry_can_choose_server_offered_create_link():
    driver = _driver()
    create = Link(driver, "https://auth.openai.com/create-account/password?state=offered")
    driver.links = [create]
    assert _module().open_offered_password_entry(driver, timeout=1) == "/create-account/password"
    assert create.clicks == 1


@pytest.mark.parametrize("href,options", [
    ("https://other.example/log-in/password", {}),
    ("https://auth.openai.com:444/log-in/password", {}),
    ("https://user@auth.openai.com/log-in/password", {}),
    ("https://auth.openai.com/log-in/password", {"shown": False}),
    ("https://auth.openai.com/log-in/password", {"enabled": False}),
    ("https://auth.openai.com/log-in/password", {"attrs": {"aria-disabled": "true"}}),
])
def test_entry_rejects_untrusted_hidden_or_disabled_links(href, options):
    driver = _driver()
    link = Link(driver, href, **options)
    driver.links = [link]
    assert _module().open_offered_password_entry(driver, timeout=0.01) is None
    assert link.clicks == 0


def test_entry_no_link_does_not_invent_standard_route():
    driver = _driver()
    assert _module().open_offered_password_entry(driver, timeout=0.01) is None
    assert driver.current_url.endswith("/email-verification")


def test_entry_allow_create_false_keeps_create_link_untouched():
    driver = _driver()
    link = Link(driver, "https://auth.openai.com/create-account/password")
    driver.links = [link]
    assert _module().open_offered_password_entry(driver, timeout=0.01, allow_create=False) is None
    assert link.clicks == 0


@pytest.mark.parametrize("landing,error", [
    ("https://other.example/log-in/password", None),
    (None, RuntimeError("模拟点击未确认")),
])
def test_entry_navigation_failure_is_classified_without_second_click(landing, error):
    driver = _driver()
    link = Link(driver, "https://auth.openai.com/log-in/password", landing=landing, error=error)
    driver.links = [link]
    with pytest.raises(RuntimeError) as caught:
        _module().open_offered_password_entry(driver, timeout=0.01)
    assert getattr(caught.value, "code", "") == "password_entry_navigation_failed"
    assert link.clicks == 1


def test_entry_replaced_before_click_is_classified_without_clicking_stale_link():
    driver = _driver()
    link = Link(driver, "https://auth.openai.com/log-in/password")
    href_reads = [0]
    def read_attribute(key):
        if key == "href":
            href_reads[0] += 1
            if href_reads[0] == 2:
                raise StaleElementReferenceException("模拟水合替换入口链接")
            return link.href
        return link.attrs.get(key)
    link.get_attribute = Mock(side_effect=read_attribute)
    driver.links = [link]
    with pytest.raises(RuntimeError) as caught:
        _module().open_offered_password_entry(driver, timeout=1)
    assert getattr(caught.value, "code", "") == "password_entry_navigation_failed"
    assert link.clicks == 0
