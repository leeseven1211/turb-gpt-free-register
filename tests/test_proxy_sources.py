"""离线验证代理供给注册表的参数契约和私有配置错误边界。"""
from contextlib import ExitStack
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from config import proxy as cfg
from core.proxy_sources import get_source, is_supply_source


@pytest.fixture
def options_711():
    return {
        "api_url": "https://gateway.example.test:8443/extract?" + urlencode({
            "zone": "pool-x", "ptype": "residential", "key": "private-api-key",
            "username": "private-user", "custom": "unknown-option", "empty": "",
            "region": "JP", "count": "7", "proto": "socks5", "stype": "json",
            "split": ",", "sessType": "rotating", "sessTime": "1", "sessAuto": "1",
        }),
        "protocol": "http", "region": "US", "session_minutes": 30,
    }


def query_for(options, *, count=3, name="711proxy"):
    url = get_source(name).build_url(options, count)
    return parse_qs(urlsplit(url).query, keep_blank_values=True)


def test_source_registry_has_stable_names_limits_and_default():
    assert get_source().name == "1024proxy"
    source = get_source(" 711PROXY ")
    assert source.name == "711proxy"
    assert source.config_prefix == "PROXY_711"
    assert source.max_candidates == 900
    assert source.max_session_minutes == 180
    assert is_supply_source("1024proxy")
    assert is_supply_source("711proxy")
    assert not is_supply_source("manual")


def test_unknown_source_error_does_not_echo_private_input():
    with pytest.raises(ValueError) as raised:
        get_source("https://private-user:private-password@example.test/?key=private-api-key")
    assert "private-" not in str(raised.value)
    assert "example.test" not in str(raised.value)


def test_711_preserves_gateway_path_authorization_and_unknown_parameters(options_711):
    original = urlsplit(options_711["api_url"])

    built = urlsplit(get_source("711proxy").build_url(options_711, 3))

    assert built.scheme == original.scheme
    assert built.hostname == "gateway.example.test"
    assert built.port == 8443
    assert built.path == original.path
    query = parse_qs(built.query, keep_blank_values=True)
    for key in ("zone", "ptype", "key", "username", "custom", "empty"):
        assert query[key] == parse_qs(original.query, keep_blank_values=True)[key]


def test_711_overrides_managed_fields_and_removes_early_rotation(options_711):
    query = query_for(options_711)

    assert query["region"] == ["US"]
    assert query["count"] == ["3"]
    assert query["proto"] == ["http"]
    assert query["stype"] == ["text"]
    assert query["split"] == [r"\r\n"]
    assert query["sessType"] == ["sticky"]
    assert query["sessTime"] == ["30"]
    assert "sessAuto" not in query
    assert "sessAuto=1" in options_711["api_url"]


@pytest.mark.parametrize("protocol, expected", [
    ("http", "http"), ("https", "http"), ("socks5", "socks5"), ("socks5h", "socks5"),
])
def test_711_maps_local_protocol_to_supplier_protocol(options_711, protocol, expected):
    options_711["protocol"] = protocol

    assert query_for(options_711)["proto"] == [expected]


@pytest.mark.parametrize("region", ["Rand", "random", "rand"])
def test_711_random_country_removes_panel_country(options_711, region):
    options_711["region"] = region

    assert "region" not in query_for(options_711)


@pytest.mark.parametrize("region", ["", None])
def test_711_empty_country_keeps_panel_country(options_711, region):
    options_711["region"] = region

    assert query_for(options_711)["region"] == ["JP"]


def test_711_normalizes_explicit_country(options_711):
    options_711["region"] = " us "

    assert query_for(options_711)["region"] == ["US"]


@pytest.mark.parametrize("count, minutes, expected_count, expected_minutes", [
    (2000, 240, "900", "180"), (0, 0, "1", "1"), (32, 75, "32", "75"),
])
def test_711_bounds_count_and_sticky_session(options_711, count, minutes, expected_count, expected_minutes):
    options_711["session_minutes"] = minutes

    query = query_for(options_711, count=count)

    assert query["count"] == [expected_count]
    assert query["sessTime"] == [expected_minutes]


def test_1024_keeps_original_num_time_region_contract():
    options = {
        "api_url": "https://gateway.example.test/api?key=private-api-key&num=1&time=7&region=JP&custom=keep",
        "protocol": "http", "region": "US", "session_minutes": 30,
    }

    query = query_for(options, count=200, name="1024proxy")

    assert query["num"] == ["200"]
    assert query["time"] == ["30"]
    assert query["region"] == ["US"]
    assert query["key"] == ["private-api-key"]
    assert query["custom"] == ["keep"]
    assert "count" not in query
    assert "sessType" not in query


def test_1024_preserves_panel_country_without_override():
    options = {"api_url": "https://gateway.example.test/api?region=JP", "protocol": "http",
               "region": "", "session_minutes": 200}

    query = query_for(options, count=2000, name="1024proxy")

    assert query["region"] == ["JP"]
    assert query["num"] == ["1000"]
    assert query["time"] == ["120"]


@pytest.mark.parametrize("name, prefix", [("1024proxy", "PROXY_1024"), ("711proxy", "PROXY_711")])
def test_source_options_read_own_config_and_support_explicit_overrides(name, prefix):
    values = {"API_URL": "https://example.test/configured", "PROTOCOL": "socks5h",
              "REGION": "JP", "SESSION_MINUTES": 45}
    with ExitStack() as stack:
        for suffix, value in values.items():
            stack.enter_context(patch.object(cfg, f"{prefix}_{suffix}", value, create=True))
        source = get_source(name)

        assert source.options() == {
            "api_url": "https://example.test/configured", "protocol": "socks5h",
            "region": "JP", "session_minutes": 45,
        }
        assert source.options(api_url="https://example.test/override", protocol="http",
                              region="", session_minutes=90) == {
            "api_url": "https://example.test/override", "protocol": "http",
            "region": "", "session_minutes": 90,
        }
        assert source.options(region=None)["region"] == "JP"


def test_711_country_defaults_to_pool_country_when_legacy_region_is_absent():
    with patch.object(cfg, "PROXY_POOL_DEFAULT_COUNTRY", "DE"), \
         patch.dict(cfg.__dict__):
        cfg.__dict__.pop("PROXY_711_REGION", None)

        assert get_source("711proxy").options()["region"] == "DE"


@pytest.mark.parametrize("name, prefix", [("1024proxy", "PROXY_1024"), ("711proxy", "PROXY_711")])
def test_source_settings_read_and_convert_own_config(name, prefix):
    values = {"ACQUIRE_TIMEOUT": "70", "API_TIMEOUT": "13", "VALIDATE_ATTEMPTS": "3",
              "RECENT_TTL": "51", "ACQUIRE_INTERVAL": "0.7"}
    with ExitStack() as stack:
        for suffix, value in values.items():
            stack.enter_context(patch.object(cfg, f"{prefix}_{suffix}", value, create=True))

        assert get_source(name).settings() == {
            "acquire_timeout": 70.0, "api_timeout": 13.0, "validate_attempts": 3,
            "recent_ttl": 51, "acquire_interval": 0.7,
        }


@pytest.mark.parametrize("field, value", [
    ("api_url", ""),
    ("api_url", "ftp://private-user:private-password@example.test/?key=private-api-key"),
    ("api_url", "https://[private-api-key"),
    ("region", "private-api-key"),
    ("protocol", "private-password"),
    ("session_minutes", "private-password"),
    ("count", "private-password"),
])
def test_711_invalid_configuration_errors_hide_urls_and_credentials(options_711, field, value):
    count = value if field == "count" else 1
    if field != "count":
        options_711[field] = value

    with pytest.raises((ValueError, RuntimeError)) as raised:
        get_source("711proxy").build_url(options_711, count)

    for secret in ("private-user", "private-password", "private-api-key", "example.test"):
        assert secret not in str(raised.value)
