# -*- coding: utf-8 -*-
"""统一代理池业务边界测试。"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from core import account_proxy, proxy_pool
from core.proxy_provider import ProxyLease, acquire_registration_proxy


def _lease(provider="1024proxy", region="JP"):
    return ProxyLease(
        "lease-1", provider, "http://192.0.2.10:8080", "192.0.2.10:8080",
        datetime.now(), exit_ip="198.51.100.10", region=region,
    )


def test_account_actions_ignore_historical_provider_and_use_public_pool_api():
    lease = _lease()
    with patch("core.proxy_pool.acquire_proxy", return_value=lease) as acquire, \
         patch("core.account_proxy.resolve_account_region", return_value="JP"), \
         patch.multiple("config.account", ACCOUNT_PLAN_CHECK_PROXY_MODE="direct"), \
         patch.multiple("config.proxy", PROXY_POOL_SOURCE="1024proxy", create=True):
        route = account_proxy.acquire_account_proxy(
            account_id=7, purpose="plan-check", source="provider:old-platform",
            allow_reuse=True, reuse_limit=4,
        )

    assert route.lease is lease
    assert route.mode == "pool"
    assert acquire.call_args.kwargs["purpose"] == "plan-check"
    assert acquire.call_args.kwargs["country"] == "JP"
    assert acquire.call_args.kwargs["reuse_limit"] == 4
    assert "provider" not in acquire.call_args.kwargs
    assert "source" not in acquire.call_args.kwargs


def test_registration_wrapper_forwards_to_current_pool_source_without_mode_branch():
    lease = _lease("proxy_pool", "US")
    with patch("core.proxy_pool.acquire_proxy", return_value=lease) as acquire, \
         patch.multiple("config.proxy", REGISTRATION_PROXY_MODE="none", PROXY_POOL_SOURCE="manual", create=True):
        received = acquire_registration_proxy(
            job_id=91, account_id=7, purpose="registration", timeout=12,
        )

    assert received is lease
    assert acquire.call_args.kwargs["job_id"] == 91
    assert acquire.call_args.kwargs["timeout"] == 12
    assert "provider" not in acquire.call_args.kwargs


def test_registration_wrapper_forwards_frozen_country_to_public_pool():
    lease = _lease("1024proxy", "VN")
    with patch("core.proxy_pool.acquire_proxy", return_value=lease) as acquire:
        received = acquire_registration_proxy(
            job_id=92, account_id=7, purpose="registration", country="VN", timeout=12,
        )

    assert received is lease
    assert acquire.call_args.kwargs["country"] == "VN"
    assert "provider" not in acquire.call_args.kwargs


def test_pool_source_uses_new_source_and_default_country_before_legacy_values():
    with patch.multiple(
        "config.proxy", PROXY_POOL_SOURCE="1024proxy", PROXY_POOL_DEFAULT_COUNTRY="VN",
        PROXY_1024_REGION="US", REGISTRATION_PROXY_MODE="pool", create=True,
    ):
        assert proxy_pool.pool_source() == "1024proxy"
        assert proxy_pool.default_country() == "VN"


def test_public_pool_claim_rejects_random_and_unknown_countries():
    with patch.multiple(
        "config.proxy", PROXY_POOL_SOURCE="1024proxy",
        PROXY_1024_API_URL="https://proxy.example.test/api", create=True,
    ):
        for country in ("Rand", "XX", "JPN", "U"):
            try:
                proxy_pool.acquire_proxy(country=country, timeout=0)
            except ValueError as exc:
                assert "ISO" in str(exc)
            else:
                raise AssertionError(f"无效国家 {country} 未被统一代理池拒绝")


def test_historical_direct_snapshot_is_mapped_to_pool_for_plan_country():
    from core.plan_check_service import _country_proxy_source

    snapshot = {
        "ACCOUNT_PLAN_CHECK_PROXY_MODE": "direct",
        "ACCOUNT_ACTION_PROXY_MODE": "provider:old-platform",
        "REGISTRATION_PROXY_MODE": "none",
    }
    assert _country_proxy_source(snapshot) == "pool"


def test_browser_session_without_lease_cannot_randomly_bypass_pool():
    from core.session import BrowserSession

    try:
        BrowserSession(proxy=None)
    except RuntimeError as exc:
        assert "统一代理池" in str(exc)
    else:
        raise AssertionError("未领取租约的 BrowserSession 不应随机选择静态代理")


def test_legacy_standalone_plan_route_uses_pool_when_explicit_proxy_is_empty():
    from core import chatgpt_plan

    route = account_proxy.AccountProxyRoute(
        "http://192.0.2.20:8080", "1024proxy", "pool", region="JP",
        lease=_lease(), purpose="plan-check",
    )
    with patch("core.account_proxy.acquire_account_proxy", return_value=route) as acquire:
        resolved = chatgpt_plan.resolve_plan_check_route("")

    acquire.assert_called_once_with(purpose="plan-check")
    assert resolved["proxy"] == route.proxy_url
    assert resolved["proxy_mode"] == "pool"
    chatgpt_plan._release_plan_route(resolved)


def test_waiting_claim_reloads_pool_source_and_keeps_original_budget():
    lease = _lease()
    state = {"source": "1024proxy"}
    claimed_keys = []

    def claim(profile_key, **kwargs):
        claimed_keys.append(profile_key)
        if len(claimed_keys) == 1:
            state["source"] = "manual"
            return None
        return lease

    with patch.object(proxy_pool, "_profiles", {}), \
         patch.object(proxy_pool, "pool_source", side_effect=lambda: state["source"]), \
         patch.object(proxy_pool, "start"), \
         patch.object(proxy_pool._stop, "is_set", return_value=False), \
         patch.object(proxy_pool._stop, "wait"), \
         patch.object(proxy_pool.store, "claim", side_effect=claim), \
         patch.multiple(
             "config.proxy", PROXY_1024_API_URL="https://proxy.example.test/api",
             PROXY_POOL=["http://192.0.2.40:8080"], PROXY_POOL_DEFAULT_COUNTRY="JP",
             create=True,
         ):
        received = proxy_pool.acquire_proxy(purpose="registration", country="JP", timeout=5)

    assert received is lease
    assert len(claimed_keys) == 2
    assert claimed_keys[0] != claimed_keys[1]
    assert all(profile.waiting == 0 for profile in proxy_pool._profiles.values())


def test_old_source_profile_is_excluded_from_warm_and_refill_after_switch():
    current_options = proxy_pool._provider_options(region="JP")
    current_options["api_url"] = "https://proxy.example.test/api"
    current = proxy_pool.Profile(
        proxy_pool._profile_key("1024proxy", current_options), "1024proxy", current_options, waiting=1,
    )
    old = proxy_pool.Profile("old-source", "1024proxy", {**current_options, "api_url": "https://old.test/api"})
    calls = []
    policy = {"min_ready": 1, "max_size": 20, "wait_timeout": 0, "min_ttl": 300,
              "max_age": 60, "max_idle": 300, "workers": 1}
    with patch.object(proxy_pool, "_profiles", {current.key: current, old.key: old}), \
         patch.object(proxy_pool, "_prewarm", False), \
         patch.object(proxy_pool, "settings", return_value=policy), \
         patch.object(proxy_pool, "_configured_profile_options", return_value=[("1024proxy", current_options)]), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]), \
         patch.object(proxy_pool.store, "take_check", return_value=None), \
         patch.object(proxy_pool.store, "reserve_refill_slots", side_effect=lambda *args, **kwargs: calls.append(args) or []):
        proxy_pool.maintain_once(role="supply")

    assert calls and all(call[0] == current.key for call in calls)


def test_current_source_replenishes_historical_country_outside_prewarm_list():
    options = proxy_pool._provider_options(region="US")
    options["api_url"] = "https://proxy.example.test/api"
    profile = proxy_pool.Profile(proxy_pool._profile_key("1024proxy", options), "1024proxy", options, waiting=1)
    calls = []
    policy = {"min_ready": 1, "max_size": 20, "wait_timeout": 0, "min_ttl": 300,
              "max_age": 60, "max_idle": 300, "workers": 1}
    with patch.object(proxy_pool, "_profiles", {profile.key: profile}), \
         patch.object(proxy_pool, "_prewarm", False), \
         patch.object(proxy_pool, "settings", return_value=policy), \
         patch.multiple("config.proxy", PROXY_POOL_SOURCE="1024proxy",
                        PROXY_1024_API_URL="https://proxy.example.test/api",
                        PROXY_POOL_DEFAULT_COUNTRY="JP", PLAN_CHECK_COUNTRIES=["JP"],
                        PROXY_POOL_COUNTRIES=[], create=True), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]), \
         patch.object(proxy_pool.store, "take_check", return_value=None), \
         patch.object(proxy_pool.store, "reserve_refill_slots", side_effect=lambda *args, **kwargs: calls.append(args) or []):
        proxy_pool.maintain_once(role="supply")

    assert calls and calls[0][0] == profile.key


def test_claim_source_recheck_failure_returns_uncommitted_lease():
    options = proxy_pool._provider_options(region="JP")
    options["api_url"] = "https://proxy.example.test/api"
    lease = SimpleNamespace(metadata={})
    with patch.object(proxy_pool, "_profiles", {}), \
         patch.object(proxy_pool, "_public_source_profile",
                      side_effect=[("1024proxy", options, {}), ("1024proxy", options, {}),
                                   ("1024proxy", options, {}), RuntimeError("来源已失效")]), \
         patch.object(proxy_pool, "start"), \
         patch.object(proxy_pool._stop, "is_set", return_value=False), \
         patch.object(proxy_pool.store, "claim", return_value=lease), \
         patch.object(proxy_pool.store, "release") as release, \
         patch.multiple("config.proxy", PROXY_POOL_SOURCE="1024proxy",
                        PROXY_1024_API_URL="https://proxy.example.test/api", create=True):
        try:
            proxy_pool.acquire_proxy(country="JP", timeout=1)
        except RuntimeError as exc:
            assert "来源已失效" in str(exc)
        else:
            raise AssertionError("领取后来源解析失败应中止并归还线路")

    release.assert_called_once_with(lease, reason="allocation_cancelled", cooldown=0)
    assert all(profile.waiting == 0 for profile in proxy_pool._profiles.values())


def test_failed_profile_switch_keeps_old_waiting_counter_consistent():
    valid = proxy_pool._provider_options(region="JP")
    valid["api_url"] = "https://proxy.example.test/api"
    invalid = dict(valid, session_minutes=1)
    with patch.object(proxy_pool, "_profiles", {}), \
         patch.object(proxy_pool, "_public_source_profile",
                      side_effect=[("1024proxy", valid, {}), ("1024proxy", invalid, {})]), \
         patch.object(proxy_pool, "start"), \
         patch.object(proxy_pool.store, "claim") as claim, \
         patch.multiple("config.proxy", PROXY_POOL_SOURCE="1024proxy",
                        PROXY_1024_API_URL="https://proxy.example.test/api", PROXY_POOL_MIN_TTL=300,
                        create=True):
        try:
            proxy_pool.acquire_proxy(country="JP", timeout=1)
        except proxy_pool.ProxyPoolConfigurationError:
            pass
        else:
            raise AssertionError("不兼容的新 profile 应在领取前失败")

    claim.assert_not_called()
    assert all(profile.waiting >= 0 for profile in proxy_pool._profiles.values())
    assert all(profile.waiting == 0 for profile in proxy_pool._profiles.values())
