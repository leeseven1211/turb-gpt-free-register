"""静态来源跨国家库存的兼容领取与安全边界。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import patch

from config import account as account_cfg, proxy as cfg
from core.proxy import pool as proxy_pool
from core.storage.proxy import pool as store, leases as proxy_lease_store
from core.storage import records as record_store
from tests.support_pg import PostgresTestCase


class ProxyStaticInventoryTests(PostgresTestCase):
    urls = ["http://192.0.2.70:8080"]
    policy = {"min_ready": 1, "max_size": 2, "wait_timeout": .5, "min_ttl": 300,
              "max_age": 60, "max_idle": 300, "workers": 1}

    @contextmanager
    def environment(self, *, countries=None):
        with (
            patch.object(proxy_pool, "_profiles", {}),
            patch.object(proxy_pool, "_prewarm", True),
            patch.object(proxy_pool, "settings", return_value=self.policy),
            patch.object(proxy_pool, "start"),
            patch.object(proxy_pool._stop, "is_set", return_value=False),
            patch.object(cfg, "REGISTRATION_PROXY_MODE", "none"),
            patch.object(cfg, "PROXY_POOL_SOURCE", "manual", create=True),
            patch.object(cfg, "ACCOUNT_ACTION_PROXY", ""),
            patch.object(cfg, "PROXY_POOL", self.urls),
            patch.object(cfg, "PROXY_POOL_COUNTRIES", countries or []),
            patch.object(cfg, "PLAN_CHECK_COUNTRIES", []),
            patch.object(account_cfg, "ACCOUNT_PLAN_CHECK_PROXY_MODE", "pool"),
            patch("core.proxy.provider._validate_proxy_with_retries", return_value=("198.51.100.70", "JP")),
        ):
            yield

    def seed(self, *, urls=None, region=None, observed="JP", exit_ip=None):
        options = {"urls": urls or self.urls}
        if region:
            options["region"] = region
        profile = proxy_pool._profile("proxy_pool", options)
        slot = store.reserve_slot(profile.key, "proxy_pool", max_size=20, timeout=60)
        exit_ip = exit_ip or "198.51.100." + options["urls"][0].split(".")[-1].split(":")[0]
        with patch("core.proxy.provider._validate_proxy_with_retries", return_value=(exit_ip, observed)):
            lease = proxy_pool._fetch_static(profile, slot, self.policy)
        self.assertTrue(store.publish(slot, lease))
        return slot, lease

    def acquire(self, *, region=None, urls=None, shared=False, limit=3):
        return proxy_pool.acquire(provider="proxy_pool", static_urls=urls or self.urls,
                                  region=region, purpose="plan-check" if shared else "live-check",
                                  allow_reuse=shared, reuse_limit=limit, timeout=.5)

    def test_country_prewarm_inventory_serves_real_generic_controller(self):
        # 只有一个端点时，JP预热不能饿死不传国家的查活/2FA/密码入口。
        with self.environment(countries=["JP"]):
            self.assertTrue(proxy_pool.maintain_once(role="supply"))
            lease = self.acquire()
            self.assertEqual("JP", lease.region)
            self.assertEqual({"leased": 1}, store.counts())
            with record_store.transaction() as conn:
                self.assertEqual(1, record_store.count_rows(store.LEASES,
                    where="state = 'leased' AND endpoint_owner", conn=conn))

    def test_generic_inventory_serves_matching_country_after_profile_restart(self):
        # 控制器内存profile清空后仍能推导同源generic键，不要求复制端点。
        with self.environment():
            self.seed()
            with patch.object(proxy_pool, "_profiles", {}):
                lease = self.acquire(region="JP")
            self.assertEqual("JP", lease.region)
            self.assertEqual({"leased": 1}, store.counts())

    def test_country_inventory_serves_generic_after_profile_restart(self):
        with self.environment():
            self.seed(region="JP")
            with patch.object(proxy_pool, "_profiles", {}):
                self.assertEqual("JP", self.acquire().region)

    def test_wrong_country_unknown_country_and_other_source_are_rejected(self):
        with self.environment():
            slot, anchor = self.seed()
            with self.assertRaises(proxy_pool.ProxyPoolTimeout):
                self.acquire(region="VN")
            with self.assertRaises(proxy_pool.ProxyPoolTimeout):
                self.acquire(urls=["http://192.0.2.71:8080"])
            record_store.patch_row(store.RESOURCES, slot["id"], {"region": None})
            row = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
            record_store.patch_row(store.LEASES, row["id"], {"region": None})
            with self.assertRaises(proxy_pool.ProxyPoolTimeout):
                self.acquire(region="JP")

    def test_generic_and_country_concurrent_claims_keep_one_exclusive_child(self):
        with self.environment():
            self.seed(region="JP")
            def claim(region):
                try:
                    return self.acquire(region=region)
                except proxy_pool.ProxyPoolTimeout:
                    return None
            with ThreadPoolExecutor(max_workers=2) as executor:
                leases = list(executor.map(claim, [None, "JP"]))
            self.assertEqual(1, sum(lease is not None for lease in leases))
            self.assertEqual({"leased": 1}, store.counts())

    def test_cross_profile_shared_claims_preserve_ip_limit_and_block_exclusive(self):
        with self.environment():
            self.seed()
            first = self.acquire(region="JP", shared=True, limit=2)
            with self.assertRaises(proxy_pool.ProxyPoolTimeout):
                self.acquire()
            second = self.acquire(shared=True, limit=2)
            store.release(first, reason="completed")
            store.release(second, reason="completed")
            with self.assertRaises(proxy_pool.ProxyPoolTimeout):
                self.acquire(region="JP", shared=True, limit=2)
            with record_store.transaction() as conn:
                self.assertEqual(2, proxy_lease_store.plan_check_exit_ip_count(conn, "198.51.100.70"))
            self.assertEqual({"rotation_wait": 1}, store.counts())

    def test_borrowed_inventory_still_rejects_ttl_staleness_fault_and_cooldown(self):
        for reason in ("ttl", "stale", "fault", "cooldown"):
            with self.subTest(reason=reason), self.environment():
                # 每个分支使用不同来源与端点，避免先前分支的库存互相干扰。
                number = {"ttl": 80, "stale": 81, "fault": 82, "cooldown": 83}[reason]
                urls = [f"http://192.0.2.{number}:8080"]
                slot, _ = self.seed(urls=urls, region="JP")
                if reason == "ttl":
                    record_store.patch_row(store.RESOURCES, slot["id"], {"expires_at": store._stamp(100)})
                elif reason == "stale":
                    record_store.patch_row(store.RESOURCES, slot["id"], {"checked_at": store._stamp(-120)})
                else:
                    lease = self.acquire(urls=urls)
                    store.release(lease, reason="测试释放", fault=reason == "fault", cooldown=60)
                with self.assertRaises(proxy_pool.ProxyPoolTimeout):
                    self.acquire(urls=urls)

    def test_matching_profile_key_cannot_bypass_provider_url_or_observed_region(self):
        # 即使旧库存碰巧位于允许键下，也必须重新校验锚点的同源与实际国家。
        for reason in ("provider", "url", "region"):
            with self.subTest(reason=reason), self.environment():
                number = {"provider": 90, "url": 91, "region": 92}[reason]
                urls = [f"http://192.0.2.{number}:8080"]
                slot, anchor = self.seed(urls=urls)
                row = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
                changes = {"provider": "1024proxy"} if reason == "provider" else (
                    {"proxy_url": "http://192.0.2.99:8080"} if reason == "url" else {"region": "VN"})
                record_store.patch_row(store.LEASES, row["id"], changes)
                with self.assertRaises(proxy_pool.ProxyPoolTimeout):
                    self.acquire(urls=urls, region="JP")
                self.assertEqual("ready", record_store.get_row(store.RESOURCES, slot["id"])["state"])

    def test_full_pool_refill_keeps_borrowable_ready_country_for_generic_waiter(self):
        # worker先运行时，不能把调用方即将借用的唯一JP库存当作旧profile回收。
        with self.environment(), patch.object(proxy_pool, "settings", return_value={**self.policy, "max_size": 1}):
            slot, _ = self.seed(region="JP")
            generic = proxy_pool._profile("proxy_pool", {"urls": self.urls})
            generic.waiting = 1
            proxy_pool.maintain_once(role="supply")
            generic.waiting = 0
            self.assertEqual("ready", record_store.get_row(store.RESOURCES, slot["id"])["state"])
            self.assertEqual("JP", self.acquire().region)

    def test_full_pool_deficit_does_not_reclaim_compatible_ready_contribution(self):
        # target2大于兼容ready1时，另一条已占用也不能导致唯一ready被回收补货。
        urls = ["http://192.0.2.70:8080", "http://192.0.2.71:8080"]
        with self.environment():
            jp, _ = self.seed(urls=urls, region="JP")
            self.seed(urls=urls, region="VN", observed="VN", exit_ip="198.51.100.71")
            occupied = self.acquire(urls=urls, region="VN")
            generic = proxy_pool._profile("proxy_pool", {"urls": urls})
            generic.waiting = 1
            proxy_pool.maintain_once(role="supply")
            generic.waiting = 0
            self.assertEqual("ready", record_store.get_row(store.RESOURCES, jp["id"])["state"])
            self.assertEqual("JP", self.acquire(urls=urls).region)
            self.assertEqual("pool_leased", record_store.get_row_by(store.LEASES, "lease_id", occupied.lease_id)["state"])
