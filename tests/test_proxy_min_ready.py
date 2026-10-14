"""代理池以真正可领取的线路维持空闲底数，并发补货不重复占槽。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import threading
import time
import uuid
from unittest.mock import patch

from core import proxy_lease_store, proxy_pool, proxy_pool_store as store, record_store
from core.proxy_provider import ProxyLease
from tests.support_pg import PostgresTestCase


class ProxyMinReadyTests(PostgresTestCase):
    def setUp(self):
        self._number = 0

    def new_anchor(self, *, seconds=1800):
        self._number += 1
        number = self._number
        now = datetime.now()
        lease = ProxyLease(
            uuid.uuid4().hex, "1024proxy", f"http://192.0.2.{number}:8080",
            f"192.0.2.{number}:8080", now, expires_at=now + timedelta(seconds=seconds),
            exit_ip=f"198.51.100.{number}", region="US",
            metadata={"persistent_lease": True},
        )
        proxy_lease_store.reserve_pending(
            lease_id=lease.lease_id, provider=lease.provider, endpoint=lease.endpoint,
            proxy_url=lease.proxy_url, acquired_at=now.isoformat(),
            expires_at=lease.expires_at.isoformat(), purpose="pool-reserve",
        )
        proxy_lease_store.activate(
            lease_id=lease.lease_id, exit_ip=lease.exit_ip, region=lease.region,
            expires_at=lease.expires_at.isoformat(),
        )
        return lease

    def seed_ready(self, *, profile="default", seconds=1800):
        slot = store.reserve_slot(profile, "1024proxy", max_size=30, timeout=60)
        lease = self.new_anchor(seconds=seconds)
        self.assertTrue(store.publish(slot, lease))
        return slot, lease

    def patch_anchor(self, anchor, fields):
        row = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
        record_store.patch_row(store.LEASES, row["id"], fields)

    def add_child(self, anchor, *, state="pool_leased", seconds=600):
        return record_store.insert_row(store.LEASES, {
            "lease_id": uuid.uuid4().hex, "provider": anchor.provider,
            "endpoint": anchor.endpoint, "proxy_url": anchor.proxy_url,
            "state": state, "acquired_at": store._stamp(), "expires_at": store._stamp(seconds),
            "pool_anchor_id": anchor.lease_id,
        })

    def available(self, profile="default"):
        return store.availability(profile, min_ttl=300, max_age=60)

    def reserve(self, *, profile="default", target=7, max_size=20, limit=10):
        return store.reserve_refill_slots(
            profile, "1024proxy", target=target, max_size=max_size,
            min_ttl=300, max_age=60, limit=limit, timeout=60,
        )

    def seed_checking(self, *, seconds=1800):
        slot, anchor = self.seed_ready(seconds=seconds)
        record_store.patch_row(store.RESOURCES, slot["id"], {"checked_at": store._stamp(-120)})
        checking = store.take_check("default", max_age=60, timeout=60)
        self.assertEqual(checking["resource_id"], slot["resource_id"])
        return slot, anchor

    def test_pending_supply_prevents_duplicate_refill_but_is_not_ready(self):
        self.seed_ready()
        for _ in range(2):
            store.reserve_slot("default", "1024proxy", max_size=20, timeout=60)
            self.seed_checking()

        self.assertEqual(self.available(), {"ready": 1, "fetching": 2, "checking": 2})
        slots = self.reserve(target=7)
        self.assertEqual(len(slots), 2)
        self.assertEqual(self.available(), {"ready": 1, "fetching": 4, "checking": 2})
        self.assertEqual(self.reserve(target=7), [])

    def test_expired_or_unusable_pending_supply_does_not_block_refill(self):
        store.reserve_slot("default", "1024proxy", max_size=20, timeout=-1)
        store.reserve_slot("default", "1024proxy", max_size=20, timeout=60)
        self.seed_checking(seconds=120)
        slot, _ = self.seed_checking()
        record_store.patch_row(store.RESOURCES, slot["id"], {"check_deadline": store._stamp(-1)})
        _, anchor = self.seed_checking()
        self.patch_anchor(anchor, {"expires_at": store._stamp(120)})

        self.assertEqual(self.available(), {"ready": 0, "fetching": 1, "checking": 0})
        self.assertEqual(len(self.reserve(target=5)), 4)

    def test_ready_requires_fresh_health_long_lived_anchor_and_no_live_children(self):
        self.seed_ready()
        slot, _ = self.seed_ready()
        record_store.patch_row(store.RESOURCES, slot["id"], {"anchor_lease_id": "missing-anchor"})
        _, anchor = self.seed_ready()
        self.patch_anchor(anchor, {"state": "recent"})
        _, anchor = self.seed_ready()
        self.patch_anchor(anchor, {"expires_at": store._stamp(120)})
        self.seed_ready(seconds=120)
        slot, _ = self.seed_ready()
        record_store.patch_row(store.RESOURCES, slot["id"], {"checked_at": store._stamp(-120)})
        slot, _ = self.seed_ready()
        record_store.patch_row(store.RESOURCES, slot["id"], {"checked_at": None})
        _, anchor = self.seed_ready()
        self.add_child(anchor)
        slot, anchor = self.seed_ready()
        self.add_child(anchor, state="shared_leased")
        record_store.patch_row(store.RESOURCES, slot["id"], {"state": "shared"})

        self.assertEqual(self.available(), {"ready": 1, "fetching": 0, "checking": 0})
        self.assertEqual(len(self.reserve(target=5)), 4)

    def test_finished_or_expired_children_do_not_hide_ready_inventory(self):
        for state, seconds in (("released", 600), ("pool_leased", -1), ("shared_leased", -1)):
            _, anchor = self.seed_ready()
            self.add_child(anchor, state=state, seconds=seconds)
        self.assertEqual(self.available(), {"ready": 3, "fetching": 0, "checking": 0})

    def test_concurrent_refill_reserves_only_the_shared_deficit(self):
        self.seed_ready()
        barrier = threading.Barrier(8)

        def reserve(_):
            barrier.wait()
            return self.reserve(target=7, max_size=20, limit=2)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(reserve, range(8)))
        self.assertEqual(sum(len(rows) for rows in results), 6)
        self.assertEqual(self.available(), {"ready": 1, "fetching": 6, "checking": 0})

    def test_concurrent_profiles_obey_global_capacity(self):
        record_store.init()
        barrier = threading.Barrier(8)

        def reserve(index):
            barrier.wait()
            return self.reserve(profile=str(index), target=7, max_size=3, limit=2)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(reserve, range(8)))
        self.assertEqual(sum(len(rows) for rows in results), 3)
        self.assertEqual(store.counts(), {"fetching": 3})

    def test_idle_shrink_preserves_real_ready_minimum(self):
        usable, _ = self.seed_ready()
        stale, _ = self.seed_ready()
        record_store.patch_row(store.RESOURCES, stale["id"], {"checked_at": store._stamp(-120)})
        missing, _ = self.seed_ready()
        record_store.patch_row(store.RESOURCES, missing["id"], {"anchor_lease_id": "missing-anchor"})
        unusable, anchor = self.seed_ready()
        self.patch_anchor(anchor, {"state": "recent"})
        for slot in (usable, stale, missing, unusable):
            record_store.patch_row(store.RESOURCES, slot["id"], {"last_used_at": store._stamp(-600)})

        store.maintenance(
            max_age=60, max_idle=300, min_ready=1, min_ttl=300,
            max_size=20, warm_profiles={"default"},
        )
        row = record_store.get_row_by(store.RESOURCES, "resource_id", usable["resource_id"])
        self.assertEqual(row["state"], "ready")
        self.assertEqual(self.available()["ready"], 1)

    def supply_candidates(self, options, *, count, candidate_count=None, cancelled):
        for _ in range(count):
            yield self.new_anchor()

    def pool_patches(self):
        policy = {
            "min_ready": 5, "max_size": 20, "wait_timeout": 1, "min_ttl": 300,
            "max_age": 60, "max_idle": 300, "workers": 2,
        }
        return (
            patch.object(proxy_pool, "_profiles", {}),
            patch.object(proxy_pool, "_prewarm", False),
            patch.object(proxy_pool, "settings", return_value=policy),
            patch.object(proxy_pool._stop, "is_set", return_value=False),
            patch("core.proxy_supply.fetch_candidates", side_effect=self.supply_candidates),
        )

    def test_background_keeps_five_idle_routes_and_refills_after_claim(self):
        patches = self.pool_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4] as supply:
            profile = proxy_pool._profile("1024proxy", {
                "api_url": "https://example.test/api", "session_minutes": 30,
            })
            for _ in range(3):
                self.assertTrue(proxy_pool.maintain_once())
            self.assertEqual(self.available(profile.key)["ready"], 5)
            self.assertFalse(proxy_pool.maintain_once())
            self.assertEqual(supply.call_count, 3)

            lease = store.claim(
                profile.key, min_ttl=300, max_age=60,
                correlation={"purpose": "registration", "job_id": "101"},
            )
            self.assertIsNotNone(lease)
            self.assertEqual(self.available(profile.key)["ready"], 4)
            self.assertTrue(proxy_pool.maintain_once())
            self.assertEqual(self.available(profile.key)["ready"], 5)
            self.assertEqual(store.counts(), {"ready": 5, "leased": 1})

    def test_background_covers_waiters_in_addition_to_five_idle_routes(self):
        patches = self.pool_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            profile = proxy_pool._profile("1024proxy", {
                "api_url": "https://example.test/api", "session_minutes": 30,
            })
            profile.waiting = 3
            for _ in range(4):
                self.assertTrue(proxy_pool.maintain_once())
            self.assertEqual(self.available(profile.key)["ready"], 8)
            self.assertFalse(proxy_pool.maintain_once())
            for job_id in range(3):
                lease = store.claim(
                    profile.key, min_ttl=300, max_age=60,
                    correlation={"purpose": "registration", "job_id": str(job_id)},
                )
                self.assertIsNotNone(lease)
                profile.waiting -= 1
            self.assertEqual(self.available(profile.key)["ready"], 5)
            self.assertFalse(proxy_pool.maintain_once())

    def test_five_concurrent_consumers_complete_one_hundred_allocations(self):
        patches = self.pool_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            profile = proxy_pool._profile("1024proxy", {
                "api_url": "https://example.test/api", "session_minutes": 30,
            })
            for _ in range(3):
                self.assertTrue(proxy_pool.maintain_once())
            self.assertEqual(self.available(profile.key)["ready"], 5)
            lease_ids = set()
            with ThreadPoolExecutor(max_workers=5) as executor:
                for round_no in range(20):
                    barrier = threading.Barrier(5)

                    def claim(job_id):
                        barrier.wait()
                        return store.claim(
                            profile.key, min_ttl=300, max_age=60,
                            correlation={"purpose": "registration", "job_id": str(job_id)},
                        )

                    with patch("core.proxy_provider._direct_session", side_effect=AssertionError("领取不能访问外网")):
                        leases = list(executor.map(claim, range(round_no * 5, round_no * 5 + 5)))
                    self.assertTrue(all(lease is not None for lease in leases))
                    self.assertEqual(self.available(profile.key)["ready"], 0)
                    for lease in leases:
                        self.assertNotIn(lease.lease_id, lease_ids)
                        lease_ids.add(lease.lease_id)
                        store.release(lease, reason="completed", cooldown=1800)
                    self.assertEqual(self.available(profile.key)["ready"], 0)
                    self.assertEqual(store.counts().get("cooldown"), (round_no + 1) * 5)

                    for _ in range(3):
                        self.assertTrue(proxy_pool.maintain_once())
                    self.assertEqual(self.available(profile.key), {"ready": 5, "fetching": 0, "checking": 0})
                    self.assertFalse(proxy_pool.maintain_once())
            self.assertEqual(len(lease_ids), 100)
            self.assertEqual(store.counts(), {"ready": 5, "cooldown": 100})

    def test_supply_backoff_does_not_block_existing_route_health_checks(self):
        patches = self.pool_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            profile = proxy_pool._profile("1024proxy", {
                "api_url": "https://example.test/api", "session_minutes": 30,
            })
            slot, anchor = self.seed_ready(profile=profile.key)
            record_store.patch_row(store.RESOURCES, slot["id"], {"checked_at": store._stamp(-120)})
            profile.retry_after = time.monotonic() + 60
            self.assertEqual(self.available(profile.key)["ready"], 0)

            with patch("core.proxy_supply.fetch_candidates", side_effect=TimeoutError("模拟供应商故障")) as supply, \
                 patch("core.proxy_provider._validate_proxy_with_retries", return_value=(anchor.exit_ip, anchor.region)) as check:
                self.assertTrue(proxy_pool.maintain_once())
            check.assert_called_once()
            supply.assert_not_called()
            self.assertEqual(self.available(profile.key), {"ready": 1, "fetching": 0, "checking": 0})

    def test_warm_idle_stale_routes_survive_until_recheck_restores_minimum(self):
        patches = self.pool_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            profile = proxy_pool._profile("1024proxy", {
                "api_url": "https://example.test/api", "session_minutes": 30,
            })
            checks = {}
            for _ in range(5):
                slot, anchor = self.seed_ready(profile=profile.key)
                checks[anchor.proxy_url] = (anchor.exit_ip, anchor.region)
                record_store.patch_row(store.RESOURCES, slot["id"], {
                    "checked_at": store._stamp(-120), "last_used_at": store._stamp(-600),
                })
            profile.retry_after = time.monotonic() + 60
            self.assertEqual(self.available(profile.key)["ready"], 0)

            def validate(proxy_url, *args, **kwargs):
                return checks[proxy_url]

            with patch("core.proxy_supply.fetch_candidates", side_effect=TimeoutError("模拟供应商故障")) as supply, \
                 patch("core.proxy_provider._validate_proxy_with_retries", side_effect=validate) as check:
                for number in range(1, 6):
                    self.assertTrue(proxy_pool.maintain_once())
                    self.assertEqual(self.available(profile.key)["ready"], number)
            self.assertEqual(check.call_count, 5)
            supply.assert_not_called()
            self.assertEqual(store.counts(), {"ready": 5})
