"""711 来源复用统一库存、领取和释放的边界验证。"""
from datetime import datetime, timedelta
from unittest.mock import patch
import uuid

import pytest

from config import proxy as cfg
from core.proxy import account_routes as account_proxy, pool as proxy_pool
from core.storage.proxy import pool as store, leases as proxy_lease_store
from core.storage import records as record_store
from core.proxy.provider import ProxyLease, acquire_registration_proxy
from tests.support_pg import PostgresTestCase


def test_711_profiles_follow_country_and_connection_changes():
    with patch.multiple(cfg, PROXY_POOL_SOURCE="711proxy", PROXY_711_API_URL="http://example.test:8089/gen",
                        PROXY_POOL_DEFAULT_COUNTRY="JP", PROXY_POOL_COUNTRIES=["US"], PLAN_CHECK_COUNTRIES=[]):
        profiles = proxy_pool._configured_profile_options()
        assert {provider for provider, _ in profiles} == {"711proxy"}
        assert {options["region"] for _, options in profiles} == {"JP", "US"}
        provider, options, scope = proxy_pool._public_source_profile("US")
        assert (provider, options["region"], scope) == ("711proxy", "US", {})
        profile = proxy_pool.Profile("test", provider, options)
        assert proxy_pool._profile_is_current(profile)
        with patch.object(cfg, "PROXY_711_API_URL", "http://other.test/gen"):
            assert not proxy_pool._profile_is_current(profile)
        with patch.object(cfg, "PROXY_POOL_SOURCE", "1024proxy"):
            assert not proxy_pool._profile_is_current(profile)


def test_711_lifetime_uses_supplier_limit():
    proxy_pool._validate_lifetime("711proxy", {"session_minutes": 180}, {"min_ttl": 9000})
    with pytest.raises(proxy_pool.ProxyPoolConfigurationError, match="711Proxy"):
        proxy_pool._validate_lifetime("711proxy", {"session_minutes": 5}, {"min_ttl": 300})


def test_711_unconfigured_account_route_is_reported_without_network():
    with patch.multiple(cfg, PROXY_POOL_SOURCE="711proxy", PROXY_711_API_URL=""):
        result = account_proxy.proxy_configuration_status("plan-check")
    assert not result["ok"]
    assert "711Proxy" in result["reason"]


def test_711_maintenance_requests_its_adapter_and_budget():
    now = datetime.now()
    lease = ProxyLease("test", "711proxy", "http://192.0.2.1:80", "192.0.2.1:80", now,
                       expires_at=now + timedelta(minutes=30), region="JP")
    with patch.multiple(cfg, PROXY_POOL_SOURCE="711proxy", PROXY_711_API_URL="http://example.test/gen",
                        PROXY_711_ACQUIRE_TIMEOUT=99, PROXY_POOL_DEFAULT_COUNTRY="JP"), \
         patch.object(proxy_pool, "_profiles", {}), patch.object(proxy_pool, "_prewarm", False), \
         patch.object(proxy_pool._stop, "is_set", return_value=False), \
         patch.object(store, "maintenance", return_value=[]), \
         patch.object(store, "reserve_refill_slots", return_value=[{"resource_id": "test"}]) as reserve, \
         patch.object(store, "publish", return_value=True) as publish, \
         patch("core.proxy.supply.fetch_candidates", return_value=iter([lease])) as fetch:
        profile = proxy_pool._profile("711proxy", proxy_pool._provider_options("711proxy", region="JP"))
        profile.waiting = 1
        assert proxy_pool.maintain_once(role="supply")
    assert fetch.call_args.kwargs["source"] == "711proxy"
    assert reserve.call_args.args[1] == "711proxy"
    assert reserve.call_args.kwargs["timeout"] == 159
    publish.assert_called_once()


class Proxy711InventoryTests(PostgresTestCase):
    def test_registration_and_account_actions_claim_persisted_711_inventory_without_network(self):
        with patch.multiple(cfg, PROXY_POOL_SOURCE="711proxy", PROXY_711_API_URL="http://example.test/gen",
                            PROXY_POOL_DEFAULT_COUNTRY="JP", PROXY_711_RECENT_TTL=42), \
             patch.object(proxy_pool, "start"), patch.object(proxy_pool, "_profiles", {}), \
             patch.object(proxy_pool._stop, "is_set", return_value=False), \
             patch("core.proxy.provider._direct_session", side_effect=AssertionError("领取不能访问供应商")):
            options = proxy_pool._provider_options("711proxy", region="JP")
            key = proxy_pool._profile_key("711proxy", options)
            for number in (1, 2):
                slot = store.reserve_slot(key, "711proxy", max_size=20, timeout=60)
                now = datetime.now()
                lease = ProxyLease(uuid.uuid4().hex, "711proxy", f"http://192.0.2.{number}:8080",
                                   f"192.0.2.{number}:8080", now, expires_at=now + timedelta(minutes=30),
                                   exit_ip=f"198.51.100.{number}", region="JP",
                                   metadata={"persistent_lease": True})
                proxy_lease_store.reserve_pending(lease_id=lease.lease_id, provider=lease.provider,
                                                 endpoint=lease.endpoint, proxy_url=lease.proxy_url,
                                                 acquired_at=now.isoformat(), expires_at=lease.expires_at.isoformat(),
                                                 purpose="pool-reserve")
                proxy_lease_store.activate(lease_id=lease.lease_id, exit_ip=lease.exit_ip, region="JP",
                                          expires_at=lease.expires_at.isoformat())
                self.assertTrue(store.publish(slot, lease))
            registration = acquire_registration_proxy(job_id=7, country="JP", timeout=5)
            with patch.object(account_proxy, "resolve_account_region", return_value="JP"):
                route = account_proxy.acquire_account_proxy(account_id=8, purpose="password-setup")
            self.assertEqual(registration.provider, "711proxy")
            self.assertEqual(route.lease.provider, "711proxy")
            self.assertNotEqual(registration.endpoint, route.lease.endpoint)
            self.assertEqual(store.counts(key), {"leased": 2})
            proxy_pool.release(registration, reason="completed")
            proxy_pool.release(route.lease, reason="completed")
            self.assertEqual(store.counts(key), {"cooldown": 2})
            row = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", route.lease.lease_id)
            self.assertEqual(row["state"], "released")
