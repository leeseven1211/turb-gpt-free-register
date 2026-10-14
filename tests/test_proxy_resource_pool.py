"""独立代理池的跨线程容量、领取和恢复边界。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import threading
import uuid
from unittest.mock import patch

from tests.support_pg import PostgresTestCase
from core import proxy_pool, proxy_pool_store as store, proxy_lease_store, record_store
from core.proxy_provider import ProxyLease


class ProxyResourcePoolTests(PostgresTestCase):
    def seed_ready(self, number=1, *, seconds=1800, profile="default", endpoint=None,
                   exit_ip=None):
        slot = store.reserve_slot(profile, "1024proxy", max_size=20, timeout=60)
        now = datetime.now()
        endpoint = endpoint or f"192.0.2.{number}:8080"
        exit_ip = exit_ip or f"198.51.100.{number}"
        lease = ProxyLease(uuid.uuid4().hex, "1024proxy", f"http://{endpoint}", endpoint, now,
                           expires_at=now + timedelta(seconds=seconds), exit_ip=exit_ip,
                           region="US", metadata={"persistent_lease": True})
        proxy_lease_store.reserve_pending(lease_id=lease.lease_id, provider=lease.provider,
                                         endpoint=lease.endpoint, proxy_url=lease.proxy_url,
                                         acquired_at=now.isoformat(), expires_at=lease.expires_at.isoformat(),
                                         purpose="pool-reserve")
        proxy_lease_store.activate(lease_id=lease.lease_id, exit_ip=lease.exit_ip, region=lease.region,
                                   expires_at=lease.expires_at.isoformat())
        self.assertTrue(store.publish(slot, lease))
        return slot, lease

    def alias_ready_resource(self, anchor, *, profile="default"):
        slot = store.reserve_slot(profile, "1024proxy", max_size=20, timeout=60)
        self.assertTrue(store.publish(slot, anchor))
        return slot

    def claim(self, *, shared=False, purpose=None, reuse_limit=3):
        return store.claim("default", min_ttl=300, max_age=60, allow_reuse=shared,
                           reuse_limit=reuse_limit,
                           correlation={"purpose": purpose or ("plan-check" if shared else "registration"),
                                        "job_id": "101", "registration_job_id": 101, "route_attempt_no": 7})

    def test_capacity_is_atomic_across_threads_and_profiles(self):
        barrier = threading.Barrier(8)
        def reserve(index):
            barrier.wait()
            return store.reserve_slot(str(index), "1024proxy", max_size=3, timeout=60)
        with ThreadPoolExecutor(max_workers=8) as executor:
            rows = list(executor.map(reserve, range(8)))
        self.assertEqual(sum(row is not None for row in rows), 3)
        self.assertEqual(store.counts(), {"fetching": 3})

    def test_exclusive_inventory_is_claimed_once_without_network(self):
        self.seed_ready()
        with patch("core.proxy_provider._direct_session", side_effect=AssertionError("领取不能访问网络")):
            with ThreadPoolExecutor(max_workers=5) as executor:
                leases = list(executor.map(lambda _: self.claim(), range(5)))
        claimed = [lease for lease in leases if lease]
        self.assertEqual(len(claimed), 1)
        row = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", claimed[0].lease_id)
        self.assertEqual(row["purpose"], "registration")
        self.assertEqual(row["route_attempt_no"], 7)
        self.assertEqual(store.counts(), {"leased": 1})

    def test_shared_leases_are_independent_and_block_exclusive_claim(self):
        self.seed_ready()
        first, second = self.claim(shared=True), self.claim(shared=True)
        self.assertNotEqual(first.lease_id, second.lease_id)
        self.assertIsNone(self.claim())
        store.release(first, reason="completed")
        self.assertIsNone(self.claim())
        self.assertEqual(record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", second.lease_id)["state"], "shared_leased")
        store.release(second, reason="completed")
        self.assertIsNotNone(self.claim())

    def test_shared_reuse_limit_counts_same_exit_ip_across_resources_and_skips_exhausted_ip(self):
        _, same_ip_anchor = self.seed_ready(1, exit_ip="198.51.100.77")
        self.alias_ready_resource(same_ip_anchor)
        self.seed_ready(3, exit_ip="198.51.100.88")

        first = self.claim(shared=True, reuse_limit=2)
        second = self.claim(shared=True, reuse_limit=2)
        self.assertEqual("198.51.100.77", first.exit_ip)
        self.assertEqual("198.51.100.77", second.exit_ip)
        third = self.claim(shared=True, reuse_limit=2)
        self.assertIsNotNone(third)
        self.assertEqual("198.51.100.88", third.exit_ip)

    def test_released_shared_lease_keeps_count_until_expiry(self):
        self.seed_ready(exit_ip="198.51.100.77")
        first = self.claim(shared=True, reuse_limit=1)
        store.release(first, reason="completed")
        with self.assertRaises(proxy_lease_store.ProxyReuseLimitError):
            self.claim(shared=True, reuse_limit=1)

    def test_exhausted_resource_is_retired_and_does_not_fill_ready_inventory(self):
        slot, anchor = self.seed_ready(exit_ip="198.51.100.77")
        first = self.claim(shared=True, reuse_limit=1)
        store.release(first, reason="completed")
        with self.assertRaises(proxy_lease_store.ProxyReuseLimitError):
            self.claim(shared=True, reuse_limit=1)
        resource = record_store.get_row_by(store.RESOURCES, "resource_id", slot["resource_id"])
        anchor_row = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
        self.assertEqual("retired", resource["state"])
        self.assertEqual("recent", anchor_row["state"])
        self.assertEqual({"retired": 1}, store.counts())

    def test_expired_released_shared_lease_no_longer_counts(self):
        self.seed_ready(exit_ip="198.51.100.77")
        first = self.claim(shared=True, reuse_limit=1)
        store.release(first, reason="completed")
        row = record_store.get_row_by(store.LEASES, "lease_id", first.lease_id)
        record_store.patch_row(store.LEASES, row["id"], {
            "expires_at": store._stamp(-1),
        })
        self.assertIsNotNone(self.claim(shared=True, reuse_limit=1))

    def test_released_strict_pool_child_counts_against_shared_limit(self):
        _, same_ip_anchor = self.seed_ready(1, exit_ip="198.51.100.77")
        self.alias_ready_resource(same_ip_anchor)
        strict = self.claim(purpose="plan-check")
        store.release(strict, reason="completed")
        with self.assertRaises(proxy_lease_store.ProxyReuseLimitError):
            self.claim(shared=True, reuse_limit=1)

    def test_shared_reuse_limit_is_atomic_across_threads(self):
        self.seed_ready(1, exit_ip="198.51.100.77")
        barrier = threading.Barrier(2)

        def claim_once(_):
            barrier.wait()
            try:
                return self.claim(shared=True, reuse_limit=1)
            except proxy_lease_store.ProxyReuseLimitError:
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            leases = list(executor.map(claim_once, range(2)))
        self.assertEqual(1, sum(lease is not None for lease in leases))

    def test_shared_reuse_limit_must_be_bounded(self):
        self.seed_ready()
        with self.assertRaises(ValueError):
            self.claim(shared=True, reuse_limit=0)
        with self.assertRaises(ValueError):
            self.claim(shared=True, reuse_limit=101)

    def test_faulted_shared_resource_cannot_return_to_ready(self):
        self.seed_ready()
        first, second = self.claim(shared=True), self.claim(shared=True)
        store.release(first, reason="transport_failure", fault=True)
        store.release(second, reason="completed")
        self.assertIsNone(self.claim(shared=True))
        self.assertEqual(store.counts(), {"quarantine": 1})

    def test_registration_release_preserves_cooldown_and_recovers_without_rewriting_history(self):
        slot, anchor = self.seed_ready()
        lease = self.claim()
        store.release(lease, reason="completed", cooldown=1800)
        store.release(lease, reason="late_duplicate_release", cooldown=1800)
        row = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", lease.lease_id)
        self.assertEqual(row["state"], "released")
        self.assertEqual(row["release_reason"], "completed")
        self.assertIsNone(self.claim())
        self.assertEqual(store.counts(), {"cooldown": 1})
        record_store.patch_row(store.RESOURCES, slot["id"], {"cooldown_until": store._stamp(-1)})
        store.maintenance(max_age=60, max_idle=300, min_ready=1, max_size=20)
        second = self.claim()
        self.assertIsNotNone(second)
        self.assertNotEqual(second.lease_id, lease.lease_id)
        self.assertNotEqual(second.lease_id, anchor.lease_id)
        self.assertEqual(record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", lease.lease_id), row)
        store.release(lease, reason="very_late_release")
        self.assertIsNone(self.claim())

    def test_fault_and_cooldown_are_retired_after_expiry(self):
        first, _ = self.seed_ready()
        lease = self.claim()
        store.release(lease, reason="transport_failure", fault=True)
        second, _ = self.seed_ready(2)
        store.release(self.claim(), reason="completed", cooldown=20)
        for slot in (first, second):
            record_store.patch_row(store.RESOURCES, slot["id"], {"expires_at": store._stamp(-1)})
        retired = store.maintenance(max_age=60, max_idle=300, min_ready=0)
        self.assertEqual(len(retired), 2)
        self.assertEqual(store.counts(), {"expired": 2})

    def test_idle_shrink_respects_minimum_and_never_revokes_busy_lease(self):
        for number in range(1, 5):
            slot, _ = self.seed_ready(number)
            record_store.patch_row(store.RESOURCES, slot["id"], {"last_used_at": store._stamp(-600)})
        self.claim()
        store.maintenance(max_age=60, max_idle=300, min_ready=1, max_size=2)
        self.assertEqual(store.counts(), {"ready": 1, "leased": 1, "retired": 2})

    def test_background_retirement_preserves_original_anchor_release_time(self):
        slot, anchor = self.seed_ready()
        store.release(self.claim(), reason="transport_failure", fault=True)
        before = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", anchor.lease_id)
        record_store.patch_row(store.RESOURCES, slot["id"], {"expires_at": store._stamp(-1)})
        with patch.object(proxy_pool, "_prewarm", False), patch.object(proxy_pool, "_profiles", {}):
            proxy_pool.maintain_once()
        after = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", anchor.lease_id)
        self.assertEqual(after["released_at"], before["released_at"])
        self.assertEqual(store.counts(), {"expired": 1})

    def test_waiting_profile_can_reclaim_only_other_idle_inventory(self):
        self.seed_ready()
        self.assertIsNone(store.reserve_slot("other", "1024proxy", max_size=1, timeout=60))
        self.assertIsNotNone(store.reserve_slot("other", "1024proxy", max_size=1, timeout=60, reclaim_idle=True))
        self.assertEqual(store.counts(), {"retired": 1, "fetching": 1})

    def test_capacity_reduction_does_not_resurrect_cooldown(self):
        slot, _ = self.seed_ready()
        store.release(self.claim(), reason="completed", cooldown=1)
        self.seed_ready(2)
        record_store.patch_row(store.RESOURCES, slot["id"], {"cooldown_until": store._stamp(-1)})
        store.maintenance(max_age=60, max_idle=300, min_ready=1, max_size=1)
        self.assertEqual(store.counts(), {"ready": 1, "retired": 1})

    def test_near_expiry_and_stale_health_are_not_claimed(self):
        self.seed_ready(seconds=100)
        self.assertIsNone(self.claim())
        slot, _ = self.seed_ready(2)
        record_store.patch_row(store.RESOURCES, slot["id"], {"checked_at": store._stamp(-120)})
        self.assertIsNone(self.claim())
        check = store.take_check("default", max_age=60, timeout=10)
        self.assertEqual(check["resource_id"], slot["resource_id"])
        self.assertTrue(store.finish_check(check, success=True))
        self.assertIsNotNone(self.claim())

    def test_failed_health_check_closes_anchor_in_same_transaction(self):
        slot, anchor = self.seed_ready()
        record_store.patch_row(store.RESOURCES, slot["id"], {"checked_at": store._stamp(-120)})
        checking = store.take_check("default", max_age=60, timeout=10)
        self.assertIsNotNone(checking)
        self.assertTrue(store.finish_check(checking, success=False))
        resource = record_store.get_row_by(store.RESOURCES, "resource_id", slot["resource_id"])
        anchor_row = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
        self.assertEqual("quarantine", resource["state"])
        self.assertEqual("recent", anchor_row["state"])
        self.assertEqual(resource["expires_at"], anchor_row["recent_until"])

    def test_stale_anchor_claim_closes_anchor_and_old_terminal_repair_keeps_child(self):
        slot, anchor = self.seed_ready(seconds=1800)
        anchor_row = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
        record_store.patch_row(store.LEASES, anchor_row["id"], {"expires_at": store._stamp(120)})
        self.assertIsNone(self.claim())
        resource = record_store.get_row_by(store.RESOURCES, "resource_id", slot["resource_id"])
        anchor_row = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
        self.assertEqual("expired", resource["state"])
        self.assertEqual("recent", anchor_row["state"])
        self.assertEqual(resource["expires_at"], anchor_row["recent_until"])

        second_slot, second_anchor = self.seed_ready(2)
        child = self.claim(shared=True)
        record_store.patch_row(store.RESOURCES, second_slot["id"], {
            "state": "retired", "updated_at": store._stamp(-8 * 24 * 60 * 60),
        })
        store.maintenance(max_age=60, max_idle=300, min_ready=0, max_size=20)
        repaired_anchor = record_store.get_row_by(store.LEASES, "lease_id", second_anchor.lease_id)
        preserved_child = record_store.get_row_by(store.LEASES, "lease_id", child.lease_id)
        preserved_resource = record_store.get_row_by(store.RESOURCES, "resource_id", second_slot["resource_id"])
        self.assertEqual("recent", repaired_anchor["state"])
        self.assertEqual("shared_leased", preserved_child["state"])
        self.assertEqual("retired", preserved_resource["state"])
        released_at = repaired_anchor["released_at"]
        store.maintenance(max_age=60, max_idle=300, min_ready=0, max_size=20)
        repaired_again = record_store.get_row_by(store.LEASES, "lease_id", second_anchor.lease_id)
        self.assertEqual(released_at, repaired_again["released_at"])

    def test_old_terminal_without_live_anchor_is_boundedly_purged(self):
        slot, anchor = self.seed_ready()
        old = store._stamp(-8 * 24 * 60 * 60)
        record_store.patch_row(store.RESOURCES, slot["id"], {
            "state": "retired", "updated_at": old, "expires_at": old,
        })
        store.maintenance(max_age=60, max_idle=300, min_ready=0, max_size=20)
        self.assertIsNone(record_store.get_row_by(store.RESOURCES, "resource_id", slot["resource_id"]))
        self.assertIsNone(record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id))

    def test_interrupted_fetch_is_recovered_and_late_publish_rejected(self):
        slot = store.reserve_slot("default", "1024proxy", max_size=1, timeout=-1)
        store.maintenance(max_age=60, max_idle=300, min_ready=0)
        late = ProxyLease("late", "1024proxy", "http://192.0.2.1:80", "192.0.2.1:80", datetime.now(),
                          expires_at=datetime.now() + timedelta(minutes=30))
        self.assertFalse(store.publish(slot, late))
        self.assertIsNotNone(store.reserve_slot("default", "1024proxy", max_size=1, timeout=60))

    def test_public_inventory_does_not_expose_credentials_or_owner(self):
        _, lease = self.seed_ready()
        items = store.public_items()
        self.assertNotIn("proxy_url", items[0])
        self.assertNotIn("owner_token", items[0])
        self.assertNotIn(lease.endpoint, str(items))

    def test_task_timeout_does_not_execute_provider_in_task_thread(self):
        with patch.object(proxy_pool, "start"), patch.object(proxy_pool.store, "claim", return_value=None), \
             patch("core.proxy_provider.fetch_1024_proxy", side_effect=AssertionError("不应提取")):
            with self.assertRaises(proxy_pool.ProxyPoolTimeout):
                proxy_pool.acquire(api_url="https://example.test/api", purpose="registration", timeout=0.01)

    def test_waiter_receives_database_inventory_published_after_old_deadline(self):
        clock = [0.0]
        progress = []
        profile_key = None

        def publish_after_wait(_seconds):
            self.assertEqual(store.counts(), {})
            clock[0] = 65.0
            self.seed_ready(profile=profile_key)

        with patch("config.proxy.PROXY_POOL_WAIT_TIMEOUT", 0), \
             patch.object(proxy_pool, "start"), patch.object(proxy_pool, "_profiles", {}), \
             patch.object(proxy_pool.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(proxy_pool._stop, "wait", side_effect=publish_after_wait), \
             patch("core.proxy_provider._direct_session", side_effect=AssertionError("领取不能访问网络")):
            profile_key = proxy_pool._profile("1024proxy", proxy_pool._provider_options(
                api_url="https://example.test/api",
            )).key
            lease = proxy_pool.acquire(
                api_url="https://example.test/api", purpose="plan-check",
                allow_reuse=True, account_id=101, progress_callback=progress.append,
            )
            self.assertEqual(proxy_pool._profiles[profile_key].waiting, 0)

        self.assertEqual(clock[0], 65.0)
        self.assertEqual(lease.exit_ip, "198.51.100.1")
        row = record_store.get_row_by(store.LEASES, "lease_id", lease.lease_id)
        self.assertEqual(row["state"], "shared_leased")
        self.assertEqual(row["account_id"], 101)
        store.release(lease, reason="completed")
        self.assertEqual(store.counts(), {"ready": 1})

    def test_non_query_cannot_request_shared_lease(self):
        with self.assertRaises(ValueError):
            self.claim(shared=True, purpose="registration")

    def test_recovery_never_reallocates_unrecognized_exclusive_owner(self):
        slot, _ = self.seed_ready()
        record_store.patch_row(store.RESOURCES, slot["id"], {"state": "leased"})
        store.maintenance(max_age=60, max_idle=300, min_ready=0)
        self.assertEqual(store.counts(), {"leased": 1})
        self.assertIsNone(self.claim())

    def test_refill_delivers_first_candidate_immediately_and_stops_at_minimum(self):
        policy = {"min_ready": 2, "max_size": 3, "wait_timeout": 1, "min_ttl": 300,
                  "max_age": 60, "max_idle": 300, "workers": 2}
        def candidates(options, *, count, candidate_count=None, cancelled):
            self.assertEqual(count, 2)
            for number in (1, 2):
                if number == 2:
                    self.assertEqual(store.counts().get("ready"), 1)
                now = datetime.now()
                lease = ProxyLease(uuid.uuid4().hex, "1024proxy", f"http://192.0.2.{number}:80",
                                   f"192.0.2.{number}:80", now, expires_at=now + timedelta(minutes=30),
                                   exit_ip=f"198.51.100.{number}", region="US")
                proxy_lease_store.reserve_pending(lease_id=lease.lease_id, provider=lease.provider,
                    endpoint=lease.endpoint, proxy_url=lease.proxy_url, acquired_at=now.isoformat(),
                    expires_at=lease.expires_at.isoformat(), purpose="pool-reserve")
                proxy_lease_store.activate(lease_id=lease.lease_id, exit_ip=lease.exit_ip, region="US",
                    expires_at=lease.expires_at.isoformat())
                yield lease
        with patch.object(proxy_pool, "_profiles", {}), patch.object(proxy_pool, "_prewarm", False), \
             patch.object(proxy_pool, "settings", return_value=policy), \
             patch.object(proxy_pool._stop, "is_set", return_value=False), \
             patch("core.proxy_supply.fetch_candidates", side_effect=candidates) as fetch:
            proxy_pool._profile("1024proxy", {"api_url": "https://example.test/api", "session_minutes": 30})
            self.assertTrue(proxy_pool.maintain_once())
            self.assertFalse(proxy_pool.maintain_once())
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(store.counts(), {"ready": 2})

    def test_supplier_failure_releases_slots_and_backs_off_without_task_retry(self):
        policy = {"min_ready": 2, "max_size": 2, "wait_timeout": 1, "min_ttl": 300,
                  "max_age": 60, "max_idle": 300, "workers": 2}
        with patch.object(proxy_pool, "_profiles", {}), patch.object(proxy_pool, "_prewarm", False), \
             patch.object(proxy_pool, "settings", return_value=policy), \
             patch("core.proxy_supply.fetch_candidates", side_effect=TimeoutError("模拟失败")) as fetch:
            proxy_pool._profile("1024proxy", {"api_url": "https://example.test/api", "session_minutes": 30})
            self.assertFalse(proxy_pool.maintain_once())
            self.assertFalse(proxy_pool.maintain_once())
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(store.counts(), {"failed": 2})

    def test_supply_uses_fixed_session_duration_and_private_background_reservation(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        from unittest.mock import Mock
        from urllib.parse import parse_qs, urlparse
        from core import proxy_supply
        response = SimpleNamespace(text="192.0.2.1:80\n192.0.2.2:80", raise_for_status=lambda: None)
        session = Mock()
        session.get.return_value = response
        with patch("core.proxy_provider._direct_session", return_value=nullcontext(session)), \
             patch("core.proxy_provider._validate_proxy_with_retries", side_effect=[("198.51.100.1", "US"), ("198.51.100.2", "US")]), \
             patch("core.proxy_provider._LAST_ACQUIRE_AT", 0):
            leases = list(proxy_supply.fetch_candidates({"api_url": "https://example.test/api?time=7",
                "protocol": "http", "region": "US", "session_minutes": 30}, count=2))
        self.assertEqual(len(leases), 2)
        args = session.get.call_args
        query = parse_qs(urlparse(args.args[0]).query)
        self.assertEqual(query["time"], ["30"])
        self.assertEqual(query["num"], ["2"])
        self.assertFalse(args.kwargs["allow_redirects"])
        for lease in leases:
            row = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", lease.lease_id)
            self.assertEqual(row["purpose"], "pool-reserve")
            self.assertIsNone(row["registration_job_id"])

    def test_supply_requests_larger_window_and_validates_only_new_candidates(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        from unittest.mock import Mock
        from urllib.parse import parse_qs, urlparse
        from core import proxy_supply

        now = datetime.now()
        for number in (1, 2):
            proxy_lease_store.reserve_pending(
                lease_id=f"occupied-{number}", provider="1024proxy",
                endpoint=f"192.0.2.{number}:80", proxy_url=f"http://192.0.2.{number}:80",
                acquired_at=now.isoformat(),
                expires_at=(now + timedelta(minutes=30)).isoformat(),
                purpose="pool-reserve",
            )
        response = SimpleNamespace(
            text="192.0.2.1:80\n192.0.2.2:80\n192.0.2.3:80\n192.0.2.4:80",
            raise_for_status=lambda: None,
        )
        session = Mock()
        session.get.return_value = response
        validate = Mock(side_effect=[("198.51.100.3", "US"), ("198.51.100.4", "US")])
        with patch("core.proxy_provider._direct_session", return_value=nullcontext(session)), \
             patch("core.proxy_provider._validate_proxy_with_retries", validate), \
             patch("core.proxy_provider._LAST_ACQUIRE_AT", 0):
            leases = list(proxy_supply.fetch_candidates(
                {"api_url": "https://example.test/api?time=7", "protocol": "http",
                 "region": "US", "session_minutes": 30},
                count=2, candidate_count=4,
            ))

        self.assertEqual([lease.endpoint for lease in leases], ["192.0.2.3:80", "192.0.2.4:80"])
        self.assertEqual(validate.call_count, 2)
        self.assertEqual(
            [call.args[0] for call in validate.call_args_list],
            ["http://192.0.2.3:80", "http://192.0.2.4:80"],
        )
        query = parse_qs(urlparse(session.get.call_args.args[0]).query)
        self.assertEqual(query["time"], ["30"])
        self.assertEqual(query["num"], ["4"])

    def test_supply_reports_duplicate_candidate_window(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        from unittest.mock import Mock
        from core import proxy_supply

        now = datetime.now()
        for number in (1, 2):
            proxy_lease_store.reserve_pending(
                lease_id=f"occupied-only-{number}", provider="1024proxy",
                endpoint=f"192.0.2.{number}:80", proxy_url=f"http://192.0.2.{number}:80",
                acquired_at=now.isoformat(),
                expires_at=(now + timedelta(minutes=30)).isoformat(),
                purpose="pool-reserve",
            )
        response = SimpleNamespace(
            text="192.0.2.1:80\n192.0.2.2:80", raise_for_status=lambda: None,
        )
        session = Mock()
        session.get.return_value = response
        with patch("core.proxy_provider._direct_session", return_value=nullcontext(session)), \
             patch("core.proxy_provider._validate_proxy_with_retries", side_effect=AssertionError("重复候选不应验证")), \
             patch("core.proxy_provider._LAST_ACQUIRE_AT", 0):
            with self.assertRaises(proxy_supply.ProxySupplyDuplicateCandidatesError) as raised:
                list(proxy_supply.fetch_candidates(
                    {"api_url": "https://example.test/api", "protocol": "http",
                     "region": "US", "session_minutes": 30}, count=2,
                ))
        self.assertEqual(raised.exception.code, "supply_candidates_duplicate")
