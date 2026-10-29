"""代理全局维护不阻塞容量预留，并保留租约与容量边界。"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import threading
from unittest.mock import patch

from core import proxy_pool_store as store, record_store
from tests.support_pg import PostgresTestCase


class ProxyMaintenanceTests(PostgresTestCase):
    def setUp(self):
        record_store.init()

    def maintain(self):
        return store.maintenance(max_age=60, max_idle=300, min_ready=0,
                                 min_ttl=300, max_size=5)

    def seed_ready(self, name, *, profile="default", anchor=None):
        anchor = anchor or name
        if record_store.get_row_by(store.LEASES, "lease_id", anchor) is None:
            record_store.insert_row(store.LEASES, {
                "lease_id": anchor, "provider": "1024proxy", "endpoint": f"{anchor}:80",
                "proxy_url": f"http://{anchor}:80", "state": "leased", "expires_at": store._stamp(1800),
                "acquired_at": store._stamp(),
            })
        return record_store.insert_row(store.RESOURCES, {
            "resource_id": name, "profile_key": profile, "provider": "1024proxy", "state": "ready",
            "anchor_lease_id": anchor, "expires_at": store._stamp(1800), "checked_at": store._stamp(),
            "last_used_at": store._stamp(-600),
        })

    def test_busy_capacity_lock_skips_maintenance_instead_of_queueing_connection(self):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with record_store.transaction() as conn:
                record_store.advisory_xact_lock(conn, "proxy-pool-capacity")
                future = executor.submit(self.maintain)
                try:
                    result = future.result(timeout=0.5)
                    completed_before_unlock = True
                except TimeoutError:
                    completed_before_unlock = False
            future.result(timeout=5)
        self.assertTrue(completed_before_unlock, "重复维护不应占着连接排队等待容量锁")
        self.assertEqual(result, [])

    def test_terminal_cleanup_does_not_hold_capacity_lock(self):
        old = store._stamp(-8 * 24 * 60 * 60)
        record_store.insert_row(store.RESOURCES, {
            "resource_id": "old-terminal", "profile_key": "old", "provider": "1024proxy",
            "state": "retired", "expires_at": old, "last_used_at": old, "updated_at": old,
        })
        entered = threading.Event()
        release = threading.Event()
        original = store._purge_old_terminal

        def slow_cleanup(conn, resource):
            entered.set()
            self.assertTrue(release.wait(5))
            return original(conn, resource)

        with patch.object(store, "_purge_old_terminal", side_effect=slow_cleanup), \
             ThreadPoolExecutor(max_workers=2) as executor:
            maintenance = executor.submit(self.maintain)
            try:
                self.assertTrue(entered.wait(3))
                reservation = executor.submit(store.reserve_slot, "new", "1024proxy", max_size=1, timeout=60)
                try:
                    slot = reservation.result(timeout=0.5)
                    completed_during_cleanup = True
                except TimeoutError:
                    completed_during_cleanup = False
            finally:
                release.set()
            maintenance.result(timeout=5)
            reservation.result(timeout=5)
        self.assertTrue(completed_during_cleanup, "终态历史清理不能占用容量锁")
        self.assertIsNotNone(slot)
        self.assertEqual(store.counts(), {"fetching": 1})

    def test_cooldown_recovery_and_parallel_refill_share_atomic_capacity(self):
        for index in range(8):
            record_store.insert_row(store.RESOURCES, {
                "resource_id": f"cooldown-{index}", "profile_key": "cooldown", "provider": "1024proxy",
                "state": "cooldown", "expires_at": store._stamp(1800), "last_used_at": store._stamp(),
                "cooldown_until": store._stamp(-1),
            })
        start = threading.Barrier(9)

        def refill(index):
            start.wait(timeout=5)
            return store.reserve_refill_slots(str(index), "1024proxy", target=5, max_size=5,
                                             min_ttl=300, max_age=60, limit=5, timeout=60)

        def maintain():
            start.wait(timeout=5)
            self.maintain()

        with ThreadPoolExecutor(max_workers=9) as executor:
            maintenance = executor.submit(maintain)
            reservations = [executor.submit(refill, index) for index in range(8)]
            maintenance.result(timeout=10)
            for future in reservations:
                future.result(timeout=10)
        # 忙时允许跳过；下轮维护仍按同一容量上限恢复冷却库存。
        self.maintain()
        counts = store.counts()
        self.assertEqual(sum(counts.get(state, 0) for state in store.LIVE), 5)
        self.assertNotIn("cooldown", counts)

    def test_locked_live_resource_is_counted_when_maintenance_recovers_cooldown(self):
        ready = self.seed_ready("busy")
        record_store.insert_row(store.RESOURCES, {
            "resource_id": "cooldown", "profile_key": "cooldown", "provider": "1024proxy",
            "state": "cooldown", "expires_at": store._stamp(1800), "last_used_at": store._stamp(),
            "cooldown_until": store._stamp(-1),
        })
        with ThreadPoolExecutor(max_workers=1) as executor:
            with record_store.transaction() as conn:
                record_store.get_row(store.RESOURCES, ready, conn=conn, for_update=True)
                future = executor.submit(store.maintenance, max_age=60, max_idle=300, min_ready=1,
                                         min_ttl=300, max_size=1)
                try:
                    future.result(timeout=0.5)
                    completed_while_busy = True
                except TimeoutError:
                    completed_while_busy = False
            future.result(timeout=5)
        self.assertTrue(completed_while_busy, "维护不应等待业务行锁")
        self.assertEqual(store.counts(), {"ready": 1, "retired": 1})

    def test_busy_anchor_does_not_block_maintenance_or_count_as_stable_ready(self):
        self.seed_ready("busy")
        self.seed_ready("spare")
        with ThreadPoolExecutor(max_workers=1) as executor:
            with record_store.transaction() as conn:
                record_store.get_row_by(store.LEASES, "lease_id", "busy", conn=conn, for_update=True)
                future = executor.submit(store.maintenance, max_age=60, max_idle=300, min_ready=1,
                                         min_ttl=300, max_size=5)
                try:
                    future.result(timeout=0.5)
                    completed_while_busy = True
                except TimeoutError:
                    completed_while_busy = False
            future.result(timeout=5)
        self.assertTrue(completed_while_busy, "维护不应等待业务锚点锁")
        self.assertEqual(store.availability("default", min_ttl=300, max_age=60)["ready"], 2)

    def test_retiring_alias_invalidates_ready_in_other_profile(self):
        self.seed_ready("kept", profile="warm")
        self.seed_ready("other-profile-alias", profile="cold", anchor="alias")
        self.seed_ready("warm-alias", profile="warm", anchor="alias")
        store.maintenance(max_age=60, max_idle=300, min_ready=1, min_ttl=300, max_size=5,
                          warm_profiles={"warm"})
        kept = record_store.get_row_by(store.RESOURCES, "resource_id", "kept")
        self.assertEqual(kept["state"], "ready")
        self.assertEqual(store.availability("warm", min_ttl=300, max_age=60)["ready"], 1)

    def test_terminal_history_with_live_child_is_repaired_but_preserved(self):
        old = store._stamp(-8 * 24 * 60 * 60)
        anchor_id = record_store.insert_row(store.LEASES, {
            "lease_id": "anchor", "provider": "1024proxy", "endpoint": "192.0.2.1:80",
            "proxy_url": "http://192.0.2.1:80", "state": "leased", "expires_at": old, "acquired_at": old,
        })
        child_id = record_store.insert_row(store.LEASES, {
            "lease_id": "child", "provider": "1024proxy", "endpoint": "192.0.2.1:80",
            "proxy_url": "http://192.0.2.1:80", "state": "pool_leased", "pool_anchor_id": "anchor",
            "expires_at": store._stamp(600), "acquired_at": store._stamp(),
        })
        resource_id = record_store.insert_row(store.RESOURCES, {
            "resource_id": "terminal-with-child", "profile_key": "old", "provider": "1024proxy",
            "state": "retired", "anchor_lease_id": "anchor", "expires_at": old,
            "last_used_at": old, "updated_at": old,
        })
        self.maintain()
        self.assertIsNotNone(record_store.get_row(store.RESOURCES, resource_id))
        self.assertEqual(record_store.get_row(store.LEASES, anchor_id)["state"], "recent")
        self.assertEqual(record_store.get_row(store.LEASES, child_id)["state"], "pool_leased")
