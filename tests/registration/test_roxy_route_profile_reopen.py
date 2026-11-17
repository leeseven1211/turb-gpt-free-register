"""换线已确认关闭后，仅更新原 Profile 的代理并重开。"""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.browser.roxy import client as roxy_client


def _state(*, opened_connection=None, present=True, reuse=True):
    stack = ExitStack()
    client = roxy_client.RoxyBrowserClient(api_base="http://roxy.example.test")
    stack.enter_context(patch.object(roxy_client._cfg, "ROXY_REUSE_ACCOUNT_PROFILE", reuse))
    stack.enter_context(patch.object(client, "_find_active_profile_by_id",
                                     return_value={"dirId": "original"} if present else None))
    stack.enter_context(patch.object(client, "get_open_profile_connection", return_value=opened_connection))
    close = stack.enter_context(patch.object(client, "close_profile", return_value=True))
    update = stack.enter_context(patch.object(client, "request", return_value={"code": 0}))
    opened = SimpleNamespace(profile_id="original", account_bound=False)
    reopen = stack.enter_context(patch.object(client, "open_profile_with_capacity_wait", return_value=opened))
    stack.enter_context(patch("core.proxy.chain.open_browser_proxy",
                              return_value=("http://127.0.0.1:13001", None)))
    stack.enter_context(patch.object(roxy_client, "_close_profile_relay"))
    stack.enter_context(patch.object(roxy_client, "_remember_profile_relay"))
    stack.enter_context(patch.object(roxy_client, "_mark_profile_bound"))
    return stack, client, close, update, reopen


def test_preclosed_reopen_updates_only_proxy_without_second_close_even_when_global_reuse_disabled():
    stack, client, close, update, reopen = _state(reuse=False)
    with stack:
        opened = client.open_profile_for_account(
            profile_id="original", proxy_url="http://next.example.test:8080",
            data_saver_flow="registration", preclosed_profile=True,
        )
    assert opened.profile_id == "original"
    close.assert_not_called()
    assert set(update.call_args.kwargs["json_body"]) == {"workspaceId", "dirId", "proxyInfo"}
    assert update.call_args.kwargs["json_body"]["dirId"] == "original"
    reopen.assert_called_once_with(profile_id="original", proxy_url=None, data_saver_flow="registration")


@pytest.mark.parametrize("connection,present", [({"pid": 123}, True), (None, False)])
def test_preclosed_reopen_never_mutates_live_or_missing_original_profile(connection, present):
    stack, client, _close, update, reopen = _state(opened_connection=connection, present=present)
    with stack, pytest.raises(RuntimeError, match="原 Profile"):
        client.open_profile_for_account(
            profile_id="original", proxy_url="http://next.example.test:8080", preclosed_profile=True,
        )
    update.assert_not_called()
    reopen.assert_not_called()


def test_preclosed_reopen_refuses_replacement_when_original_open_disappears():
    stack, client, _close, _update, reopen = _state()
    with stack:
        reopen.side_effect = RuntimeError("profile not found")
        with pytest.raises(RuntimeError, match="原 Profile"):
            client.open_profile_for_account(
                profile_id="original", proxy_url="http://next.example.test:8080", preclosed_profile=True,
            )
    assert reopen.call_count == 1


@pytest.mark.parametrize("profile,proxy", [(None, "http://next.example.test:8080"), ("original", None)])
def test_preclosed_reopen_requires_both_original_profile_and_current_route(profile, proxy):
    stack, client, _close, update, reopen = _state()
    with stack, pytest.raises(RuntimeError, match="原 Profile"):
        client.open_profile_for_account(profile_id=profile, proxy_url=proxy, preclosed_profile=True)
    update.assert_not_called()
    reopen.assert_not_called()
