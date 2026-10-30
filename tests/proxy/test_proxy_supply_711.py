"""离线验证 711Proxy 复用代理池补货、恢复和安全错误边界。"""
from contextlib import ExitStack, nullcontext
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from core.storage.proxy import leases as proxy_lease_store
from core.proxy import provider as proxy_provider, supply as proxy_supply


@pytest.fixture
def supply_711():
    """所有供应商请求、出口检查和租约写入均使用内存桩。"""
    response = SimpleNamespace(
        text='{"code":200,"data":[{"ip":"192.0.2.11","port":8080}]}',
        raise_for_status=Mock(),
    )
    session = Mock()
    session.get.return_value = response
    adapter = SimpleNamespace(
        name="711proxy", label="711Proxy", max_candidates=900, max_session_minutes=60,
        settings=Mock(return_value={
            "acquire_timeout": 60, "api_timeout": 12, "validate_attempts": 3,
            "recent_ttl": 42, "acquire_interval": 0,
        }),
        build_url=Mock(side_effect=lambda options, count: f"https://example.test/api?num={count}"),
        normalize_protocol=lambda value: "http" if value == "https" else value,
    )
    validate = Mock(return_value=("198.51.100.11", "US"))
    reserve, activate, abort, source = Mock(), Mock(), Mock(), Mock(return_value=adapter)
    with ExitStack() as stack:
        for target, name, value in (
            (proxy_supply, "get_source", source),
            (proxy_provider, "_direct_session", Mock(return_value=nullcontext(session))),
            (proxy_provider, "_validate_proxy_with_retries", validate),
            (proxy_provider, "_LAST_ACQUIRE_AT", 0),
            (proxy_lease_store, "reserve_pending", reserve),
            (proxy_lease_store, "activate", activate),
            (proxy_lease_store, "abort", abort),
        ):
            stack.enter_context(patch.object(target, name, value))
        yield SimpleNamespace(
            adapter=adapter, response=response, session=session, validate=validate,
            reserve=reserve, activate=activate, abort=abort, source=source,
            options={"api_url": "https://example.test/api?key=private-api-key",
                     "protocol": "http", "region": "US", "session_minutes": 30},
        )


def fetch(harness, **kwargs):
    return list(proxy_supply.fetch_candidates(harness.options, count=1, source="711proxy", **kwargs))


def test_711_uses_source_settings_and_persists_supplier_identity(supply_711):
    harness = supply_711

    leases = fetch(harness)

    harness.source.assert_called_once_with("711proxy")
    harness.adapter.settings.assert_called_once_with()
    assert len(leases) == 1
    lease = leases[0]
    assert lease.provider == "711proxy"
    assert lease.proxy_url == "http://192.0.2.11:8080"
    assert lease.expires_at - lease.acquired_at == timedelta(minutes=30)
    assert lease.metadata["recent_ttl"] == 42
    assert harness.reserve.call_args.kwargs["provider"] == "711proxy"
    assert harness.validate.call_args.kwargs["attempts"] == 3
    assert 0 < harness.session.get.call_args.kwargs["timeout"] <= 12
    assert harness.session.get.call_args.kwargs["allow_redirects"] is False
    harness.abort.assert_not_called()
    harness.activate.assert_called_once()


def test_711_bounds_candidate_window_and_session_before_building_url(supply_711):
    harness = supply_711
    harness.options["session_minutes"] = 120

    leases = fetch(harness, candidate_count=1200)

    options, count = harness.adapter.build_url.call_args.args
    assert count == 900
    assert options["session_minutes"] == 60
    assert leases[0].expires_at - leases[0].acquired_at == timedelta(minutes=60)
    assert harness.options["session_minutes"] == 120


@pytest.mark.parametrize("text", [
    "192.0.2.11:8080",
    '{"code":"200","data":["192.0.2.11:8080"]}',
    '{"data":[{"ip":"192.0.2.11","port":8080}]}',
])
def test_711_accepts_txt_json_and_legacy_success_envelopes(supply_711, text):
    harness = supply_711
    harness.response.text = text

    assert [lease.endpoint for lease in fetch(harness)] == ["192.0.2.11:8080"]


@pytest.mark.parametrize("code", [0, 403, "private-api-key", None, True])
def test_711_rejects_business_error_before_parsing_candidates(supply_711, code, caplog):
    import json
    harness = supply_711
    harness.response.text = json.dumps({
        "code": code, "msg": "private-api-key private-password",
        "data": ["192.0.2.11:8080"],
    })

    with patch.object(proxy_provider, "parse_proxy_responses") as parse:
        with pytest.raises(RuntimeError, match="711Proxy API 返回业务错误") as raised:
            fetch(harness)

    parse.assert_not_called()
    harness.validate.assert_not_called()
    harness.reserve.assert_not_called()
    for private_value in ("private-api-key", "private-password", "192.0.2.11"):
        assert private_value not in str(raised.value)
        assert private_value not in caplog.text


@pytest.mark.parametrize("text", [
    '{"code":200,"msg":"private-api-key private-password"}',
    "private-api-key private-password",
    '{"private-api-key":',
    "",
])
def test_711_parse_failure_never_exposes_response_body(supply_711, text, caplog):
    harness = supply_711
    harness.response.text = text

    with pytest.raises(RuntimeError, match="711Proxy API 未返回可用代理地址") as raised:
        fetch(harness)

    harness.validate.assert_not_called()
    harness.reserve.assert_not_called()
    assert raised.value.__suppress_context__ is True
    for private_value in ("private-api-key", "private-password"):
        assert private_value not in str(raised.value)
        assert private_value not in caplog.text


def test_711_large_request_preserves_bad_gateway_fallback(supply_711):
    harness = supply_711
    error = requests.HTTPError("离线模拟供应商网关错误")
    error.response = SimpleNamespace(status_code=502)
    harness.session.get.side_effect = [error, error, harness.response]

    assert len(fetch(harness, candidate_count=1200)) == 1

    assert [call.args[1] for call in harness.adapter.build_url.call_args_list] == [900, 64, 1]


def test_711_request_error_propagates_original_exception_without_private_logs(supply_711, caplog):
    harness = supply_711
    error = requests.HTTPError("private-api-key private-password")
    error.response = SimpleNamespace(status_code=429)
    harness.session.get.side_effect = error

    with pytest.raises(requests.HTTPError) as raised:
        fetch(harness)

    assert raised.value is error
    assert "stage=supply_request class=HTTPError status=429" in caplog.text
    assert "private-api-key" not in caplog.text
    assert "private-password" not in caplog.text
    harness.reserve.assert_not_called()


def test_711_bad_candidate_is_aborted_before_next_candidate(supply_711):
    harness = supply_711
    harness.response.text = "192.0.2.11:8080\n192.0.2.12:8080"
    harness.validate.side_effect = [requests.ConnectionError("离线模拟出口故障"), ("198.51.100.12", "US")]

    leases = fetch(harness, candidate_count=2)

    assert [lease.endpoint for lease in leases] == ["192.0.2.12:8080"]
    assert harness.reserve.call_count == 2
    harness.abort.assert_called_once_with(harness.reserve.call_args_list[0].kwargs["lease_id"])
    harness.activate.assert_called_once()


def test_711_duplicate_candidates_are_skipped_without_exit_validation(supply_711):
    harness = supply_711
    harness.reserve.side_effect = proxy_lease_store.DuplicateProxyLeaseError("离线模拟重复候选")

    with pytest.raises(proxy_supply.ProxySupplyDuplicateCandidatesError):
        fetch(harness)

    harness.validate.assert_not_called()
    harness.abort.assert_not_called()


def test_default_supply_source_preserves_1024_call_contract(supply_711):
    harness = supply_711
    harness.adapter.name = "1024proxy"
    harness.adapter.label = "1024Proxy"
    harness.response.text = "192.0.2.11:8080"

    leases = list(proxy_supply.fetch_candidates(harness.options, count=1))

    harness.source.assert_called_once_with("1024proxy")
    assert leases[0].provider == "1024proxy"
