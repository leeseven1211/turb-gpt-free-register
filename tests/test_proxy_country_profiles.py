import json
from datetime import datetime
from unittest.mock import patch

import pytest

from config import account as account_cfg
from config import proxy as cfg
from core import account_proxy, proxy_pool
from core.proxy_provider import ProxyLease
from tests.support_pg import PostgresTestCase


def test_country_profiles_are_isolated_by_region():
    with patch.object(proxy_pool, "_profiles", {}):
        jp = proxy_pool._profile("1024proxy", proxy_pool._provider_options(region="JP"))
        vn = proxy_pool._profile("1024proxy", proxy_pool._provider_options(region="VN"))
    assert jp.key != vn.key
    assert jp.options["region"] == "JP"
    assert vn.options["region"] == "VN"


def test_prewarm_only_creates_configured_plan_country_profiles_for_valid_1024_route():
    policy = {
        "min_ready": 2, "max_size": 20, "wait_timeout": 0, "min_ttl": 300,
        "max_age": 60, "max_idle": 300, "workers": 2,
    }
    with patch.object(proxy_pool, "_profiles", {}), \
         patch.object(proxy_pool, "_prewarm", True), \
         patch.object(proxy_pool, "settings", return_value=policy), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]), \
         patch.object(proxy_pool.store, "take_check", return_value=None), \
         patch.object(proxy_pool.store, "reserve_refill_slots", return_value=[]), \
         patch.object(cfg, "PLAN_CHECK_COUNTRIES", ["JP", "VN"]), \
         patch.object(cfg, "REGISTRATION_PROXY_MODE", "none"), \
         patch.object(account_cfg, "ACCOUNT_PLAN_CHECK_PROXY_MODE", "provider:1024proxy"), \
         patch.object(cfg, "ACCOUNT_ACTION_PROXY_MODE", "provider:1024proxy"), \
         patch.object(cfg, "PROXY_1024_API_URL", "https://proxy.example.test/api"):
        proxy_pool.maintain_once()
        regions = {profile.options.get("region") for profile in proxy_pool._profiles.values()}
    assert regions == {"JP", "VN"}


def test_prewarm_does_not_start_for_direct_plan_route():
    policy = {
        "min_ready": 2, "max_size": 20, "wait_timeout": 0, "min_ttl": 300,
        "max_age": 60, "max_idle": 300, "workers": 2,
    }
    with patch.object(proxy_pool, "_profiles", {}), \
         patch.object(proxy_pool, "_prewarm", True), \
         patch.object(proxy_pool, "settings", return_value=policy), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]), \
         patch.object(proxy_pool.store, "take_check", return_value=None), \
         patch.object(proxy_pool.store, "reserve_refill_slots", return_value=[]), \
         patch.object(cfg, "PLAN_CHECK_COUNTRIES", ["JP"]), \
         patch.object(cfg, "REGISTRATION_PROXY_MODE", "none"), \
         patch.object(account_cfg, "ACCOUNT_PLAN_CHECK_PROXY_MODE", "direct"), \
         patch.object(cfg, "ACCOUNT_ACTION_PROXY_MODE", "direct"), \
         patch.object(cfg, "PROXY_1024_API_URL", "https://proxy.example.test/api"):
        proxy_pool.maintain_once()
        assert proxy_pool._profiles == {}


def test_snapshot_country_pools_contains_only_safe_aggregates():
    jp = proxy_pool.Profile("jp-key", "1024proxy", {"region": "JP"}, waiting=2)
    vn = proxy_pool.Profile("vn-key", "1024proxy", {"region": "VN"}, waiting=0)
    policy = {
        "min_ready": 2, "max_size": 20, "wait_timeout": 0, "min_ttl": 300,
        "max_age": 60, "max_idle": 300, "workers": 2,
    }
    with patch.object(proxy_pool, "_profiles", {jp.key: jp, vn.key: vn}), \
         patch.object(proxy_pool, "settings", return_value=policy), \
         patch.object(cfg, "PLAN_CHECK_COUNTRIES", []), \
         patch.object(proxy_pool.store, "counts", side_effect=lambda key=None: {"ready": 1} if key == "jp-key" else {"leased": 2}), \
         patch.object(proxy_pool.store, "public_items", return_value=[]):
        snapshot = proxy_pool.snapshot()
    assert snapshot["country_pools"] == [
            {"provider": "1024proxy", "region": "JP", "counts": {"ready": 1}, "waiting_local": 2, "target_ready": 2, "configured": False,
             "last_supply_error": None, "last_supply_error_class": None, "retry_after_seconds": 0},
            {"provider": "1024proxy", "region": "VN", "counts": {"leased": 2}, "waiting_local": 0, "target_ready": 0, "configured": False,
             "last_supply_error": None, "last_supply_error_class": None, "retry_after_seconds": 0},
    ]
    assert "endpoint" not in json.dumps(snapshot["country_pools"])
    assert "url" not in json.dumps(snapshot["country_pools"])


def test_snapshot_hides_idle_removed_profiles_and_marks_historical_active_profiles():
    current_options = proxy_pool._provider_options(region="JP")
    current_options["api_url"] = "https://proxy.example.test/api"
    current = proxy_pool.Profile(proxy_pool._profile_key("1024proxy", current_options), "1024proxy", current_options, waiting=0)
    old_same_country = proxy_pool.Profile("old-jp", "1024proxy", {"region": "JP", "api_url": "old"}, waiting=0)
    old_waiter = proxy_pool.Profile("old-vn", "1024proxy", {"region": "VN", "api_url": "old"}, waiting=1)
    idle_removed = proxy_pool.Profile("idle-us", "1024proxy", {"region": "US", "api_url": "old"}, waiting=0)
    policy = {
        "min_ready": 2, "max_size": 20, "wait_timeout": 0, "min_ttl": 300,
        "max_age": 60, "max_idle": 300, "workers": 2,
    }
    counts = {
        current.key: {},
        old_same_country.key: {"ready": 1},
        old_waiter.key: {},
        idle_removed.key: {},
    }
    with patch.object(proxy_pool, "_profiles", {
        current.key: current, old_same_country.key: old_same_country,
        old_waiter.key: old_waiter, idle_removed.key: idle_removed,
    }), patch.object(proxy_pool, "settings", return_value=policy), \
         patch.object(cfg, "PLAN_CHECK_COUNTRIES", ["JP"]), \
         patch.object(cfg, "REGISTRATION_PROXY_MODE", "none"), \
         patch.object(cfg, "PROXY_1024_API_URL", "https://proxy.example.test/api"), \
         patch.object(account_cfg, "ACCOUNT_PLAN_CHECK_PROXY_MODE", "provider:1024proxy"), \
         patch.object(proxy_pool.store, "counts", side_effect=lambda key=None: counts.get(key, {"ready": 1})), \
         patch.object(proxy_pool.store, "public_items", return_value=[]):
        snapshot = proxy_pool.snapshot()

    rows = snapshot["country_pools"]
    assert [(row["region"], row["configured"], row["target_ready"]) for row in rows] == [
        ("JP", True, 2), ("JP", False, 0), ("VN", False, 1),
    ]


def test_snapshot_includes_region_scoped_static_profiles():
    urls = ["http://192.0.2.30:8080", "http://192.0.2.31:8080"]
    options = {"urls": urls, "region": "JP"}
    static = proxy_pool.Profile(
        proxy_pool._profile_key("proxy_pool", options), "proxy_pool", options, waiting=1,
    )
    with patch.object(proxy_pool, "_profiles", {static.key: static}), \
         patch.object(proxy_pool, "settings", return_value={
             "min_ready": 2, "max_size": 20, "wait_timeout": 0, "min_ttl": 300,
             "max_age": 60, "max_idle": 300, "workers": 1,
         }), \
         patch.object(cfg, "PLAN_CHECK_COUNTRIES", ["JP"]), \
         patch.object(cfg, "ACCOUNT_ACTION_PROXY", ""), \
         patch.object(cfg, "PROXY_POOL", urls), \
         patch.object(account_cfg, "ACCOUNT_PLAN_CHECK_PROXY_MODE", "pool"), \
         patch.object(proxy_pool.store, "counts", return_value={"ready": 1}), \
         patch.object(proxy_pool.store, "public_items", return_value=[]):
        rows = proxy_pool.snapshot()["country_pools"]

    assert rows == [{
        "provider": "proxy_pool", "region": "JP", "counts": {"ready": 1},
        "waiting_local": 1, "target_ready": 3, "configured": True,
        "last_supply_error": None, "last_supply_error_class": None, "retry_after_seconds": 0,
    }]
    assert urls[0] not in json.dumps(rows)


def test_static_pool_forwards_explicit_plan_country_but_keeps_legacy_path_unchanged():
    lease = ProxyLease("pool-lease", "proxy_pool", "http://192.0.2.1:8080", "192.0.2.1:8080",
                       datetime.now(), exit_ip="198.51.100.1", region="JP")
    with patch("core.proxy_pool.acquire", return_value=lease) as acquire, \
         patch.multiple(cfg, ACCOUNT_ACTION_PROXY="http://192.0.2.1:8080", PROXY_POOL=[]):
        account_proxy.acquire_account_proxy(account_id=1, purpose="plan-check", source="pool", region="JP")
        plan_call = acquire.call_args
        account_proxy.acquire_account_proxy(account_id=1, purpose="live-check", source="pool")
        legacy_call = acquire.call_args

    assert plan_call.kwargs["region"] == "JP"
    assert "region" not in legacy_call.kwargs


def test_static_fetch_skips_wrong_country_candidates_until_matching_region():
    urls = ["http://user:pass@192.0.2.10:8080", "http://user:pass@192.0.2.11:8080"]
    profile = proxy_pool.Profile("jp-static", "proxy_pool", {"urls": urls, "region": "JP"})
    slot = {"id": 1}
    validated = []
    aborted = []

    def validate(url, _timeout, *, attempts):
        validated.append(url)
        return ("198.51.100.10", "VN") if url == urls[0] else ("198.51.100.11", "JP")

    with patch.object(proxy_pool.proxy_lease_store, "reserve_pending"), \
         patch.object(proxy_pool.proxy_lease_store, "activate") as activate, \
         patch.object(proxy_pool.proxy_lease_store, "abort", side_effect=aborted.append), \
         patch("core.proxy_provider._validate_proxy_with_retries", side_effect=validate):
        lease = proxy_pool._fetch_static(profile, slot, {"min_ttl": 300, "max_idle": 300})

    assert validated == urls
    assert aborted and len(aborted) == 1
    assert activate.call_count == 1
    assert lease.region == "JP"
    assert lease.proxy_url == urls[1]


def test_static_fetch_continues_after_ordinary_candidate_error():
    urls = ["http://192.0.2.44:8080", "http://192.0.2.45:8080"]
    profile = proxy_pool.Profile("error-jp", "proxy_pool", {"urls": urls, "region": "JP"})
    with patch.object(proxy_pool.proxy_lease_store, "reserve_pending"), \
         patch.object(proxy_pool.proxy_lease_store, "activate") as activate, \
         patch.object(proxy_pool.proxy_lease_store, "abort") as abort, \
         patch("core.proxy_provider._validate_proxy_with_retries",
               side_effect=[RuntimeError("检测失败"), ("198.51.100.45", "JP")]):
        lease = proxy_pool._fetch_static(profile, {"id": 1}, {"min_ttl": 300, "max_idle": 300})

    assert lease.proxy_url == urls[1]
    abort.assert_called_once()
    activate.assert_called_once()


def test_static_fetch_without_region_keeps_single_candidate_timeout_behavior():
    profile = proxy_pool.Profile("legacy-static", "proxy_pool", {
        "urls": ["http://192.0.2.46:8080", "http://192.0.2.47:8080"],
    })
    with patch.object(cfg, "PROXY_1024_API_TIMEOUT", 12), \
         patch.object(proxy_pool.proxy_lease_store, "reserve_pending"), \
         patch.object(proxy_pool.proxy_lease_store, "abort") as abort, \
         patch("core.proxy_provider._validate_proxy_with_retries",
               side_effect=ValueError("旧路径检测失败")) as validate:
        with pytest.raises(ValueError, match="旧路径检测失败"):
            proxy_pool._fetch_static(profile, {"id": 1}, {"min_ttl": 300, "max_idle": 300})

    assert validate.call_args.args[1] == 12
    validate.assert_called_once()
    abort.assert_called_once()


def test_static_fetch_country_candidates_share_bounded_acquire_budget():
    urls = ["http://192.0.2.40:8080", "http://192.0.2.41:8080"]
    profile = proxy_pool.Profile("budget-jp", "proxy_pool", {"urls": urls, "region": "JP"})
    validated = []
    with patch.object(cfg, "PROXY_1024_API_TIMEOUT", 10), \
         patch.object(cfg, "PROXY_1024_ACQUIRE_TIMEOUT", 1), \
         patch.object(proxy_pool, "_stop") as stop, \
         patch.object(proxy_pool.time, "monotonic", side_effect=[0.0, 0.0, 1.1]), \
         patch.object(proxy_pool.proxy_lease_store, "reserve_pending"), \
         patch.object(proxy_pool.proxy_lease_store, "abort") as abort, \
         patch("core.proxy_provider._validate_proxy_with_retries",
               side_effect=lambda url, timeout, *, attempts: validated.append((url, timeout)) or ("198.51.100.40", "VN")):
        stop.is_set.return_value = False
        with pytest.raises(proxy_pool.ProxyPoolTimeout):
            proxy_pool._fetch_static(profile, {"id": 1}, {"min_ttl": 300, "max_idle": 300})

    assert len(validated) == 1
    assert validated[0][1] == pytest.approx(1.0)
    abort.assert_called_once()


def test_static_fetch_does_not_start_candidates_after_pool_stop():
    profile = proxy_pool.Profile("stopped-jp", "proxy_pool", {
        "urls": ["http://192.0.2.42:8080"], "region": "JP",
    })
    with patch.object(cfg, "PROXY_1024_ACQUIRE_TIMEOUT", 1), \
         patch.object(proxy_pool, "_stop") as stop, \
         patch.object(proxy_pool.proxy_lease_store, "reserve_pending"), \
         patch("core.proxy_provider._validate_proxy_with_retries") as validate:
        stop.is_set.return_value = True
        with pytest.raises(proxy_pool.ProxyPoolTimeout):
            proxy_pool._fetch_static(profile, {"id": 1}, {"min_ttl": 300, "max_idle": 300})

    validate.assert_not_called()


def test_static_fetch_aborts_then_propagates_keyboard_interrupt():
    profile = proxy_pool.Profile("interrupt-jp", "proxy_pool", {
        "urls": ["http://192.0.2.43:8080"], "region": "JP",
    })
    with patch.object(cfg, "PROXY_1024_ACQUIRE_TIMEOUT", 1), \
         patch.object(proxy_pool, "_stop") as stop, \
         patch.object(proxy_pool.proxy_lease_store, "reserve_pending"), \
         patch.object(proxy_pool.proxy_lease_store, "abort") as abort, \
         patch("core.proxy_provider._validate_proxy_with_retries", side_effect=KeyboardInterrupt):
        stop.is_set.return_value = False
        with pytest.raises(KeyboardInterrupt):
            proxy_pool._fetch_static(profile, {"id": 1}, {"min_ttl": 300, "max_idle": 300})

    abort.assert_called_once()


class StaticCountryProxyPoolPostgresTests(PostgresTestCase):
    def test_mixed_static_pool_publishes_and_claims_matching_country_profiles(self):
        policy = {"min_ready": 1, "max_size": 4, "wait_timeout": 1, "min_ttl": 300,
                  "max_age": 60, "max_idle": 300, "workers": 1}
        urls = ["http://192.0.2.20:8080", "http://192.0.2.21:8080"]
        expected = {urls[0]: ("198.51.100.20", "JP"), urls[1]: ("198.51.100.21", "VN")}
        with patch.object(proxy_pool, "_profiles", {}), \
             patch.object(proxy_pool, "_prewarm", False), \
             patch.object(proxy_pool, "settings", return_value=policy), \
             patch.object(proxy_pool._stop, "is_set", return_value=False), \
             patch("config.proxy.PROXY_1024_API_TIMEOUT", 1), \
             patch("core.proxy_provider._validate_proxy_with_retries",
                   side_effect=lambda url, _timeout, *, attempts: expected[url]):
            jp_key = proxy_pool._profile("proxy_pool", {"urls": urls, "region": "JP"}).key
            vn_key = proxy_pool._profile("proxy_pool", {"urls": urls, "region": "VN"}).key
            self.assertTrue(proxy_pool.maintain_once())
            self.assertTrue(proxy_pool.maintain_once())

            with patch.object(proxy_pool, "start"):
                jp = proxy_pool.acquire(provider="proxy_pool", static_urls=urls, region="JP",
                                        purpose="plan-check", allow_reuse=True, timeout=1)
                vn = proxy_pool.acquire(provider="proxy_pool", static_urls=urls, region="VN",
                                        purpose="plan-check", allow_reuse=True, timeout=1)

        self.assertEqual(jp_key, proxy_pool._profile_key("proxy_pool", {"urls": urls, "region": "JP"}))
        self.assertEqual(vn_key, proxy_pool._profile_key("proxy_pool", {"urls": urls, "region": "VN"}))
        self.assertEqual("JP", jp.region)
        self.assertEqual("VN", vn.region)
        proxy_pool.release(jp, reason="test-completed")
        proxy_pool.release(vn, reason="test-completed")
