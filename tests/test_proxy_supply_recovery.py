"""离线验证坏候选恢复，以及补货预算、取消和供应商错误边界。"""
from contextlib import ExitStack, nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from config import proxy as cfg
from core import proxy_lease_store, proxy_provider, proxy_supply


@pytest.fixture
def supply_harness():
    """所有 HTTP、检测和租约写入均替换为内存桩，不访问外部或数据库。"""
    clock = {"now": 1000.0}
    response = SimpleNamespace(
        text="192.0.2.11:8080\n192.0.2.12:8080", raise_for_status=Mock(),
    )
    session = Mock()
    session.get.return_value = response
    validate = Mock(return_value=("198.51.100.12", "US"))
    reserve, activate, abort = Mock(), Mock(), Mock()
    real_validate = proxy_provider._validate_proxy_with_retries
    with ExitStack() as stack:
        for target, name, value in (
            (cfg, "PROXY_1024_ACQUIRE_TIMEOUT", 60),
            (cfg, "PROXY_1024_API_TIMEOUT", 12),
            (cfg, "PROXY_1024_ACQUIRE_INTERVAL", 0),
            (cfg, "PROXY_1024_VALIDATE_ATTEMPTS", 2),
            (proxy_provider, "_LAST_ACQUIRE_AT", 0),
            (proxy_provider, "_direct_session", Mock(return_value=nullcontext(session))),
            (proxy_provider, "_validate_proxy_with_retries", validate),
            (proxy_lease_store, "reserve_pending", reserve),
            (proxy_lease_store, "activate", activate),
            (proxy_lease_store, "abort", abort),
            (proxy_supply.time, "monotonic", lambda: clock["now"]),
        ):
            stack.enter_context(patch.object(target, name, value))
        yield SimpleNamespace(
            clock=clock, response=response, session=session, validate=validate,
            reserve=reserve, activate=activate, abort=abort, real_validate=real_validate,
            options={"api_url": "https://example.test/api?key=private-api-key",
                     "protocol": "http", "region": "US", "session_minutes": 30},
        )


def fetch(harness, **kwargs):
    return list(proxy_supply.fetch_candidates(
        harness.options, count=1, candidate_count=2, **kwargs,
    ))


@pytest.mark.parametrize("error_type", [
    requests.Timeout, requests.ConnectionError, requests.HTTPError,
    requests.exceptions.ProxyError,
])
def test_bad_first_candidate_does_not_block_good_candidate(supply_harness, error_type, caplog):
    harness = supply_harness
    error = error_type("私密异常正文 http://private-user:private-password@192.0.2.11:8080")
    if isinstance(error, requests.HTTPError):
        error.response = SimpleNamespace(status_code=503)
    harness.validate.side_effect = [error, ("198.51.100.12", "US")]

    leases = fetch(harness)

    assert [lease.endpoint for lease in leases] == ["192.0.2.12:8080"]
    assert harness.reserve.call_count == 2
    harness.abort.assert_called_once_with(harness.reserve.call_args_list[0].kwargs["lease_id"])
    harness.activate.assert_called_once_with(
        lease_id=leases[0].lease_id, exit_ip="198.51.100.12", region="US",
        expires_at=leases[0].expires_at.isoformat(),
    )
    assert "stage=exit_check" in caplog.text
    assert f"class={error_type.__name__}" in caplog.text
    expected_status = "503" if isinstance(error, requests.HTTPError) else "-"
    assert f"status={expected_status}" in caplog.text
    assert "endpoint=192.0.*.*:8080" in caplog.text
    for private_value in ("私密异常正文", "private-user", "private-password", "private-api-key", "192.0.2.11"):
        assert private_value not in caplog.text


@pytest.mark.parametrize("failure_stage", ["request", "status"])
def test_supplier_http_error_propagates_without_candidate_recovery(supply_harness, failure_stage, caplog):
    harness = supply_harness
    error = requests.HTTPError("离线模拟供应商提取失败 https://example.test/api?key=private-api-key")
    error.response = SimpleNamespace(status_code=429)
    if failure_stage == "request":
        harness.session.get.side_effect = error
    else:
        harness.response.raise_for_status.side_effect = error

    with pytest.raises(requests.HTTPError) as raised:
        fetch(harness)

    assert raised.value is error
    harness.validate.assert_not_called()
    harness.reserve.assert_not_called()
    harness.abort.assert_not_called()
    assert "stage=supply_request class=HTTPError status=429" in caplog.text
    assert "private-api-key" not in caplog.text
    assert "https://example.test" not in caplog.text


def test_all_bad_candidates_are_aborted_without_delivery(supply_harness):
    harness = supply_harness
    harness.validate.side_effect = requests.ConnectionError("离线模拟候选不可连接")

    assert fetch(harness) == []

    assert harness.validate.call_count == 2
    assert [call.args[0] for call in harness.abort.call_args_list] == [
        call.kwargs["lease_id"] for call in harness.reserve.call_args_list
    ]
    harness.activate.assert_not_called()


def test_candidate_recovery_uses_remaining_shared_budget(supply_harness):
    harness = supply_harness
    def validate(url, timeout, *, attempts, deadline):
        assert attempts == 2
        assert deadline == 1060.0
        if url.endswith("192.0.2.11:8080"):
            assert timeout == 12
            harness.clock["now"] = 1058.0
            raise requests.Timeout("离线模拟第一条耗时检测失败")
        assert timeout == 2
        return "198.51.100.12", "US"
    harness.validate.side_effect = validate

    assert len(fetch(harness)) == 1
    assert harness.validate.call_count == 2
    harness.abort.assert_called_once()


def test_exhausted_budget_stops_before_next_candidate(supply_harness):
    harness = supply_harness
    def timeout(*args, **kwargs):
        harness.clock["now"] = 1060.0
        raise requests.Timeout("离线模拟耗尽补货预算")
    harness.validate.side_effect = timeout

    with pytest.raises(TimeoutError, match="代理池本轮补充预算已耗尽"):
        fetch(harness)

    harness.validate.assert_called_once()
    harness.reserve.assert_called_once()
    harness.abort.assert_called_once()
    harness.activate.assert_not_called()


def test_cancelled_failed_candidate_is_aborted_without_checking_next(supply_harness):
    harness = supply_harness
    cancelled = {"value": False}
    def fail_and_cancel(*args, **kwargs):
        cancelled["value"] = True
        raise requests.ConnectionError("离线模拟检测中取消")
    harness.validate.side_effect = fail_and_cancel

    assert fetch(harness, cancelled=lambda: cancelled["value"]) == []

    harness.validate.assert_called_once()
    harness.abort.assert_called_once()
    harness.activate.assert_not_called()


def test_cancelled_supply_does_not_request_supplier(supply_harness):
    harness = supply_harness

    assert fetch(harness, cancelled=lambda: True) == []

    harness.session.get.assert_not_called()
    harness.validate.assert_not_called()
    harness.reserve.assert_not_called()


def test_cancelled_successful_candidate_is_aborted_without_delivery(supply_harness):
    harness = supply_harness
    cancelled = {"value": False}
    def succeed_and_cancel(*args, **kwargs):
        cancelled["value"] = True
        return "198.51.100.11", "US"
    harness.validate.side_effect = succeed_and_cancel

    assert fetch(harness, cancelled=lambda: cancelled["value"]) == []

    harness.validate.assert_called_once()
    harness.abort.assert_called_once()
    harness.activate.assert_not_called()


def test_unexpected_validation_error_is_not_swallowed(supply_harness):
    harness = supply_harness
    error = RuntimeError("离线模拟非网络实现错误")
    harness.validate.side_effect = error

    with pytest.raises(RuntimeError) as raised:
        fetch(harness)

    assert raised.value is error
    harness.validate.assert_called_once()
    harness.abort.assert_called_once()


def test_real_validation_retries_do_not_log_private_error_text(supply_harness, caplog):
    harness = supply_harness
    error = requests.ConnectionError("http://private-user:private-password@192.0.2.11:8080?key=private-api-key")
    with patch.object(proxy_provider, "_validate_proxy_with_retries", harness.real_validate), \
         patch.object(proxy_provider, "_validate_proxy", side_effect=[error, error, ("198.51.100.12", "US")]), \
         patch.object(proxy_provider.time, "sleep"):
        leases = fetch(harness)
    assert [lease.endpoint for lease in leases] == ["192.0.2.12:8080"]
    assert "class=ConnectionError" in caplog.text
    assert "endpoint=192.0.*.*:8080" in caplog.text
    for private_value in ("private-user", "private-password", "private-api-key", "192.0.2.11"):
        assert private_value not in caplog.text
