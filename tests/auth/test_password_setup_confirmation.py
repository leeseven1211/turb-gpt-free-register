"""浏览器添加密码必须取得本次明确成功，空壳只保留候选。"""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.auth.browser import password_auth


@contextmanager
def setup_flow(observations, *, before_body="输入新密码", click_error=None):
    clock = [100.0]
    field = Mock()
    field.get_attribute.side_effect = lambda key: "new-password" if key == "autocomplete" else "password"
    driver = SimpleNamespace(current_url="https://chatgpt.com/#settings/Security")
    prepared = {"inputs": [field], "url": driver.current_url, "body": before_body}
    states = iter(observations)
    last = [None]
    first = [True]

    def observe(_script):
        if first[0]:
            first[0] = False
            return prepared
        last[0] = next(states, last[0])
        if isinstance(last[0], Exception):
            raise last[0]
        return last[0]

    driver.execute_script = Mock(side_effect=observe)
    with ExitStack() as stack:
        for name in ("_safe_get", "_page_warmup", "_check_manual_stop", "_human_type_text", "_human_click"):
            stack.enter_context(patch.object(password_auth, name, **(
                {"side_effect": click_error} if name == "_human_click" and click_error is not None else {}
            )))
        for name, value in {
            "_probe_chatgpt_password_eligibility": None,
            "_refresh_chatgpt_settings_shell_if_needed": 0,
            "_dismiss_chatgpt_pricing_modal": False,
            "_dismiss_single_action_dialog": False,
            "_button_after_input": object(),
        }.items():
            stack.enter_context(patch.object(password_auth, name, return_value=value))
        stack.enter_context(patch.object(password_auth, "time", SimpleNamespace(
            time=lambda: clock[0], sleep=lambda duration: clock.__setitem__(0, clock[0] + duration),
        )))
        yield driver


@pytest.mark.parametrize("observation", [
    None, {},
    {"url": "https://chatgpt.com/#settings/Security", "inputs": [], "errors": [], "body": "加载中"},
    {"url": "https://other.example/", "inputs": [], "errors": [], "body": "Password added"},
    {"url": "https://chatgpt.com/#settings/Security", "inputs": [], "errors": [], "body": "Password has not been added"},
    {"url": "https://chatgpt.com/#settings/Security", "inputs": [], "errors": [], "body": "Password set failed"},
    RuntimeError("页面读取失败"),
])
def test_empty_missing_or_untrusted_page_never_confirms_password(observation):
    candidates = []
    with setup_flow([observation]) as driver:
        with pytest.raises(password_auth.PasswordSetupResultUnknownError) as error:
            password_auth.set_roxy_login_password(
                driver, "setup@example.test", "SyntheticCandidate!123", timeout=8,
                on_password_submitted=candidates.append,
            )
    assert candidates == ["SyntheticCandidate!123"]
    assert error.value.code == "password_setup_result_unconfirmed"
    assert error.value.request_unknown is True


@pytest.mark.parametrize("message", ["Password added", "Your password has been successfully set", "密码已设置", "密码添加成功"])
def test_current_trusted_success_ui_confirms_after_transient_shell(message):
    with setup_flow([{}, {"url": "https://chatgpt.com/#settings/Security", "inputs": [], "errors": [], "body": message}]) as driver:
        assert password_auth.set_roxy_login_password(
            driver, "setup@example.test", "SyntheticCandidate!123", timeout=8,
        ) == "SyntheticCandidate!123"


def test_previous_success_text_does_not_confirm_the_current_submission():
    state = {"url": "https://chatgpt.com/#settings/Security", "inputs": [], "errors": [], "body": "Password added"}
    with setup_flow([state], before_body="Password added") as driver:
        with pytest.raises(password_auth.PasswordSetupResultUnknownError):
            password_auth.set_roxy_login_password(driver, "setup@example.test", "SyntheticCandidate!123", timeout=8)


def test_success_toast_is_not_reported_as_an_error():
    state = {"url": "https://chatgpt.com/#settings/Security", "inputs": [],
             "errors": ["Password added"], "body": "Password added"}
    with setup_flow([state]) as driver:
        assert password_auth.set_roxy_login_password(
            driver, "setup@example.test", "SyntheticCandidate!123", timeout=8,
        ) == "SyntheticCandidate!123"


def test_candidate_is_saved_before_click_even_when_dispatch_raises():
    prepared, submitted = [], []
    with setup_flow([], click_error=RuntimeError("浏览器连接中断")) as driver:
        with pytest.raises(RuntimeError, match="浏览器连接中断"):
            password_auth.set_roxy_login_password(
                driver, "setup@example.test", "SyntheticCandidate!123", timeout=8,
                on_password_prepared=prepared.append, on_password_submitted=submitted.append,
            )
    assert prepared == ["SyntheticCandidate!123"]
    assert submitted == []


def test_candidate_save_failure_prevents_dispatch():
    with setup_flow([]) as driver, patch.object(password_auth, "_human_click") as clicked:
        with pytest.raises(RuntimeError, match="候选保存失败"):
            password_auth.set_roxy_login_password(
                driver, "setup@example.test", "SyntheticCandidate!123", timeout=8,
                on_password_prepared=Mock(side_effect=RuntimeError("候选保存失败")),
            )
    clicked.assert_not_called()
