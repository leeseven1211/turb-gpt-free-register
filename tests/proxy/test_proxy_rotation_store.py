"""代理出口换代、交付预留和持久化恢复边界。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import uuid

from core.storage import postgres as postgres_store
from core.storage.proxy import leases as proxy_lease_store, pool as store
from core.storage import records as record_store
from core.proxy.provider import ProxyLease
from tests.support_pg import PostgresTestCase


class ProxyRotationStoreTests(PostgresTestCase):
    def seed(self, number=1, *, region="US", seconds=1800, profile="default"):
        slot = store.reserve_slot(profile, "1024proxy", max_size=20, timeout=60)
        now = datetime.now()
        lease = ProxyLease(uuid.uuid4().hex, "1024proxy", f"http://192.0.2.{number}:8080",
                           f"192.0.2.{number}:8080", now,
                           expires_at=now + timedelta(seconds=seconds),
                           exit_ip=f"198.51.100.{number}", region=region)
        proxy_lease_store.reserve_pending(lease_id=lease.lease_id, provider=lease.provider,
            endpoint=lease.endpoint, proxy_url=lease.proxy_url, acquired_at=now.isoformat(),
            expires_at=lease.expires_at.isoformat(), purpose="pool-reserve")
        proxy_lease_store.activate(lease_id=lease.lease_id, exit_ip=lease.exit_ip,
            region=region, expires_at=lease.expires_at.isoformat())
        self.assertTrue(store.publish(slot, lease))
        return slot, lease

    def claim(self, *, limit=3):
        return store.claim("default", min_ttl=300, max_age=60, allow_reuse=True,
                           reuse_limit=limit, correlation={"purpose": "plan-check"})

    def resource(self, slot):
        return record_store.get_row_by(store.RESOURCES, "resource_id", slot["resource_id"])

    def exhaust(self, slot):
        leases = [self.claim() for _ in range(3)]
        for lease in leases:
            store.release(lease, reason="completed")
        return leases

    def stale(self, slot):
        record_store.patch_row(store.RESOURCES, slot["id"], {"checked_at": store._stamp(-120)})

    def test_third_claim_marks_exhausted(self):
        slot, _ = self.seed()
        leases = [self.claim() for _ in range(3)]
        self.assertTrue(all(leases))
        self.assertTrue(self.resource(slot).get("reuse_exhausted"))
        self.assertEqual({"ready": 0, "fetching": 0, "checking": 0},
                         store.availability("default", min_ttl=300, max_age=60))
        for lease in leases:
            store.release(lease, reason="completed")
        self.assertEqual("rotation_wait", self.resource(slot)["state"])

    def test_unhanded_cancel_refunds_only_reserved_lease(self):
        slot, _ = self.seed()
        reserved = self.claim(limit=1)
        store.release(reserved, reason="allocation_cancelled")
        row = record_store.get_row_by(store.LEASES, "lease_id", reserved.lease_id)
        self.assertEqual("not_delivered", row.get("delivery_state"))
        self.assertTrue(callable(getattr(store, "mark_delivered", None)))
        delivered = self.claim(limit=1)
        self.assertTrue(store.mark_delivered(delivered))
        self.assertTrue(store.mark_delivered(delivered))
        store.release(delivered, reason="allocation_cancelled")
        self.assertEqual("rotation_wait", self.resource(slot)["state"])
        self.assertFalse(store.mark_delivered(reserved))
        with record_store.transaction() as conn:
            self.assertEqual(1, proxy_lease_store.plan_check_exit_ip_count(conn, delivered.exit_ip))

    def test_rotation_preserves_old_ip_and_expiry(self):
        slot, anchor = self.seed()
        old_tasks = self.exhaust(slot)
        self.assertEqual("rotation_wait", self.resource(slot)["state"])
        check = store.take_check("default", max_age=60, timeout=10, min_ttl=300)
        self.assertIsNotNone(check)
        self.assertTrue(store.finish_check(check, success=True, exit_ip="203.0.113.9", region="US", min_ttl=300))
        current = self.resource(slot)
        old = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
        new = record_store.get_row_by(store.LEASES, "lease_id", current["anchor_lease_id"])
        self.assertEqual("ready", current["state"])
        self.assertNotEqual(anchor.lease_id, new["lease_id"])
        self.assertEqual(anchor.expires_at.isoformat(timespec="microseconds"), current["expires_at"])
        self.assertEqual(current["expires_at"], new["expires_at"])
        self.assertEqual("198.51.100.1", old["exit_ip"])
        self.assertEqual("recent", old["state"])
        self.assertFalse(old["endpoint_owner"])
        self.assertTrue(new["endpoint_owner"])
        self.assertFalse(current.get("reuse_exhausted"))
        store.release(old_tasks[-1], reason="late", fault=True)
        self.assertEqual(current, self.resource(slot))
        self.assertFalse(store.finish_check(check, success=True, exit_ip="203.0.113.8", region="US"))

    def test_confirmation_committed_but_unhanded_allocation_can_refund(self):
        slot, _ = self.seed()
        lease = self.claim(limit=1)
        self.assertTrue(store.mark_delivered(lease))
        store.release(lease, reason="allocation_cancelled", before_delivery=True)
        row = record_store.get_row_by(store.LEASES, "lease_id", lease.lease_id)
        self.assertEqual("not_delivered", row["delivery_state"])
        self.assertEqual("ready", self.resource(slot)["state"])
        with record_store.transaction() as conn:
            self.assertEqual(0, proxy_lease_store.plan_check_exit_ip_count(conn, lease.exit_ip))
        self.assertIsNotNone(self.claim(limit=1))

    def test_unchanged_ip_waits_and_three_failures_retire(self):
        slot, _ = self.seed()
        self.exhaust(slot)
        check = store.take_check("default", max_age=60, timeout=10)
        self.assertIsNotNone(check)
        store.finish_check(check, success=True, exit_ip="198.51.100.1", region="US", check_interval=0)
        self.assertEqual("rotation_wait", self.resource(slot)["state"])
        for expected in (1, 2, 3):
            check = store.take_check("default", max_age=60, timeout=10)
            self.assertIsNotNone(check)
            store.finish_check(check, success=False, check_interval=0)
            self.assertEqual(expected, self.resource(slot)["probe_attempts"])
        self.assertEqual("retired", self.resource(slot)["state"])

    def test_region_conflict_and_old_ip_cannot_be_published(self):
        slot, anchor = self.seed()
        self.exhaust(slot)
        check = store.take_check("default", max_age=60, timeout=10)
        self.assertIsNotNone(check)
        store.finish_check(check, success=True, exit_ip="203.0.113.9", region="JP", check_interval=0)
        self.assertEqual(anchor.lease_id, self.resource(slot)["anchor_lease_id"])
        self.assertEqual("rotation_wait", self.resource(slot)["state"])
        check = store.take_check("default", max_age=60, timeout=10)
        store.finish_check(check, success=True, exit_ip="203.0.113.9", region="US", check_interval=0)
        self.stale(slot)
        check = store.take_check("default", max_age=60, timeout=10)
        store.finish_check(check, success=True, exit_ip="198.51.100.1", region="US", check_interval=0)
        self.assertEqual("203.0.113.9", self.resource(slot)["exit_ip"])
        self.assertEqual("rotation_wait", self.resource(slot)["state"])

    def test_check_recovery_preserves_schedule_and_rejects_late_result(self):
        slot, _ = self.seed()
        self.stale(slot)
        check = store.take_check("default", max_age=60, timeout=-1)
        store.maintenance(max_age=60, max_idle=300, min_ready=1, min_ttl=300)
        self.assertEqual("rotation_wait", self.resource(slot)["state"])
        self.assertIsNone(self.claim())
        self.assertFalse(store.finish_check(check, success=True))
        replacement = store.take_check("default", max_age=60, timeout=10, min_ttl=300)
        self.assertIsNotNone(replacement)
        self.assertTrue(store.finish_check(replacement, success=True))
        self.assertIsNotNone(self.claim())

    def test_near_expiry_does_not_extend_or_rotate(self):
        slot, _ = self.seed(seconds=100)
        self.stale(slot)
        self.assertIsNone(store.take_check("default", max_age=60, timeout=10, min_ttl=300))
        self.assertEqual("retired", self.resource(slot)["state"])

    def test_waiting_capacity_reclaims_only_idle_generation(self):
        slot, _ = self.seed()
        leases = [self.claim() for _ in range(3)]
        self.assertIsNone(store.reserve_slot("other", "1024proxy", max_size=1, timeout=60, reclaim_idle=True))
        for lease in leases:
            store.release(lease, reason="completed")
        self.assertIsNone(store.reserve_slot("other", "1024proxy", max_size=1, timeout=60))
        self.assertIsNotNone(store.reserve_slot("other", "1024proxy", max_size=1, timeout=60, reclaim_idle=True))
        self.assertEqual("retired", self.resource(slot)["state"])

    def test_concurrent_rotation_claims_one_owner_and_conflicting_ip_is_not_published(self):
        slot, _ = self.seed()
        self.exhaust(slot)
        with ThreadPoolExecutor(max_workers=3) as executor:
            checks = list(executor.map(lambda _: store.take_check("default", max_age=60, timeout=10), range(3)))
        self.assertEqual(1, sum(check is not None for check in checks))
        _, other = self.seed(2, profile="other")
        store.finish_check(next(check for check in checks if check), success=True,
                           exit_ip=other.exit_ip, region="US", check_interval=0)
        self.assertEqual("rotation_wait", self.resource(slot)["state"])
        self.assertEqual("198.51.100.1", self.resource(slot)["exit_ip"])

    def test_endpoint_index_upgrade_is_idempotent_and_preserves_old_ip(self):
        slot, anchor = self.seed()
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f'DROP INDEX {postgres_store.qualified("uq_proxy_leases_endpoint_partial")}')
            cur.execute(f'CREATE UNIQUE INDEX uq_proxy_leases_endpoint_partial ON {postgres_store.qualified("proxy_leases")} (endpoint) WHERE state IN (\'pending\', \'leased\', \'recent\')')
        for _ in range(2):
            record_store.reset_ready()
            record_store.init()
        row = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
        self.assertTrue(row.get("endpoint_owner"))
        self.exhaust(slot)
        check = store.take_check("default", max_age=60, timeout=10)
        store.finish_check(check, success=True, exit_ip="203.0.113.9", region="US")
        record_store.reset_ready()
        record_store.init()
        old = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
        self.assertEqual("198.51.100.1", old["exit_ip"])
        self.assertFalse(old["endpoint_owner"])

    def test_legacy_delivery_and_stale_refund_never_restore_bad_inventory(self):
        slot, _ = self.seed()
        lease = self.claim(limit=1)
        row = record_store.get_row_by(store.LEASES, "lease_id", lease.lease_id)
        record_store.patch_row(store.LEASES, row["id"], {}, remove_data_keys=("delivery_state",))
        store.release(lease, reason="allocation_cancelled")
        self.assertEqual("rotation_wait", self.resource(slot)["state"])
        with record_store.transaction() as conn:
            self.assertEqual(1, proxy_lease_store.plan_check_exit_ip_count(conn, lease.exit_ip))

        second, _ = self.seed(2)
        reserved = self.claim(limit=1)
        self.stale(second)
        store.release(reserved, reason="allocation_cancelled")
        self.assertEqual("rotation_wait", self.resource(second)["state"])
        self.assertIsNone(store.claim("default", min_ttl=300, max_age=60,
                                     correlation={"purpose": "registration"}))

    def test_idle_rotation_and_persistent_backoff(self):
        slot, _ = self.seed()
        self.stale(slot)
        check = store.take_check("default", max_age=60, timeout=10)
        self.assertTrue(store.finish_check(check, success=True, exit_ip="203.0.113.9", region="US"))
        self.assertEqual("203.0.113.9", self.resource(slot)["exit_ip"])
        self.exhaust(slot)
        check = store.take_check("default", max_age=60, timeout=10)
        self.assertTrue(store.finish_check(check, success=False, check_interval=60))
        before = self.resource(slot)
        record_store.reset_ready()
        record_store.init()
        self.assertIsNone(store.take_check("default", max_age=60, timeout=10))
        self.assertEqual(before["next_probe_at"], self.resource(slot)["next_probe_at"])
        self.assertEqual(1, self.resource(slot)["probe_attempts"])

    def test_quarantined_original_ip_is_not_republished_after_restart(self):
        slot, _ = self.seed()
        lease = self.claim()
        store.release(lease, reason="transport_failure", fault=True)
        store.maintenance(max_age=60, max_idle=300, min_ready=1, min_ttl=300)
        self.assertEqual("rotation_wait", self.resource(slot)["state"])
        check = store.take_check("default", max_age=60, timeout=-1)
        store.maintenance(max_age=60, max_idle=300, min_ready=1, min_ttl=300)
        self.assertFalse(store.finish_check(check, success=True))
        check = store.take_check("default", max_age=60, timeout=10)
        self.assertTrue(store.finish_check(check, success=True, exit_ip="198.51.100.1", region="US"))
        self.assertEqual("rotation_wait", self.resource(slot)["state"])

    def test_concurrent_generations_cannot_publish_same_new_ip(self):
        first, _ = self.seed(1)
        self.exhaust(first)
        second, _ = self.seed(2, profile="other")
        self.stale(second)
        checks = [store.take_check(profile, max_age=60, timeout=10) for profile in ("default", "other")]
        with ThreadPoolExecutor(max_workers=2) as executor:
            accepted = list(executor.map(lambda check: store.finish_check(check, success=True,
                exit_ip="203.0.113.9", region="US", check_interval=0), checks))
        self.assertEqual([True, True], accepted)
        states = [self.resource(slot)["state"] for slot in (first, second)]
        self.assertEqual(["ready", "rotation_wait"], sorted(states))
        current = [self.resource(slot) for slot in (first, second)]
        self.assertEqual(1, sum(row["exit_ip"] == "203.0.113.9" for row in current))

    def test_rotated_endpoint_has_one_owner_and_old_ip_keeps_isolation(self):
        slot, anchor = self.seed()
        self.exhaust(slot)
        check = store.take_check("default", max_age=60, timeout=10)
        self.assertTrue(store.finish_check(check, success=True, exit_ip="203.0.113.9", region="US"))
        new_id = self.resource(slot)["anchor_lease_id"]
        proxy_lease_store.release(lease_id=new_id, recent_until=None, reason="test")
        now = datetime.now()
        proxy_lease_store.reserve_pending(lease_id="after-rotation", provider="1024proxy",
            endpoint=anchor.endpoint, proxy_url=anchor.proxy_url, acquired_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=10)).isoformat(), purpose="registration")
        with self.assertRaises(proxy_lease_store.DuplicateProxyLeaseError):
            proxy_lease_store.activate(lease_id="after-rotation", exit_ip=anchor.exit_ip,
                region="US", expires_at=(now + timedelta(minutes=10)).isoformat())

    def test_swap_old_exit_ips_remains_isolated_without_deadlock(self):
        first, _ = self.seed(1)
        second, _ = self.seed(2, profile="other")
        for slot in (first, second):
            self.stale(slot)
        checks = [store.take_check(profile, max_age=60, timeout=10) for profile in ("default", "other")]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [executor.submit(store.finish_check, check, success=True,
                exit_ip=ip, region="US", check_interval=0)
                for check, ip in zip(checks, ("198.51.100.2", "198.51.100.1"))]
            self.assertEqual([True, True], [future.result(timeout=5) for future in results])
        self.assertEqual(["rotation_wait", "rotation_wait"], [self.resource(slot)["state"] for slot in (first, second)])
        self.assertEqual(["198.51.100.1", "198.51.100.2"], [self.resource(slot)["exit_ip"] for slot in (first, second)])

    def test_rotation_rejects_new_ip_whose_released_usage_is_exhausted(self):
        slot, _ = self.seed()
        self.stale(slot)
        now = datetime.now()
        for number in range(3):
            record_store.insert_row(store.LEASES, {
                "lease_id": f"old-shared-{number}", "provider": "1024proxy", "endpoint": "192.0.2.9:80",
                "state": "released", "purpose": "plan-check", "acquired_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=10)).isoformat(), "exit_ip": "203.0.113.9",
            })
        check = store.take_check("default", max_age=60, timeout=10)
        self.assertTrue(store.finish_check(check, success=True, exit_ip="203.0.113.9", region="US"))
        self.assertEqual("rotation_wait", self.resource(slot)["state"])
        self.assertEqual("exit_ip_reuse_exhausted", self.resource(slot)["last_error_code"])

    def test_rotation_transaction_rolls_back_old_owner_when_new_anchor_write_fails(self):
        slot, anchor = self.seed()
        self.exhaust(slot)
        check = store.take_check("default", max_age=60, timeout=10)
        function = postgres_store.qualified("reject_test_anchor")
        leases = postgres_store.qualified("proxy_leases")
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                        "BEGIN IF NEW.exit_ip = '203.0.113.9' THEN RAISE EXCEPTION '模拟新锚点写入失败'; "
                        "END IF; RETURN NEW; END $$")
            cur.execute(f"CREATE TRIGGER reject_test_anchor BEFORE INSERT ON {leases} "
                        f"FOR EACH ROW EXECUTE FUNCTION {function}()")
        with self.assertRaisesRegex(Exception, "模拟新锚点写入失败"):
            store.finish_check(check, success=True, exit_ip="203.0.113.9", region="US")
        old = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
        self.assertTrue(old["endpoint_owner"])
        self.assertEqual("leased", old["state"])
        self.assertEqual(anchor.lease_id, self.resource(slot)["anchor_lease_id"])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f"DROP TRIGGER reject_test_anchor ON {leases}")
        self.assertTrue(store.finish_check(check, success=True, exit_ip="203.0.113.9", region="US"))

    def test_strict_plan_query_cannot_bypass_global_usage_limit(self):
        slot, anchor = self.seed()
        alias = store.reserve_slot("default", "1024proxy", max_size=20, timeout=60)
        self.assertTrue(store.publish(alias, anchor))
        self.exhaust(slot)
        with self.assertRaises(proxy_lease_store.ProxyReuseLimitError):
            store.claim("default", min_ttl=300, max_age=60, allow_reuse=False,
                        correlation={"purpose": "plan-check"})

    def test_refund_does_not_publish_faulted_generation(self):
        slot, _ = self.seed()
        first, cancelled = self.claim(limit=2), self.claim(limit=2)
        store.release(first, reason="transport_failure", fault=True)
        store.release(cancelled, reason="allocation_cancelled")
        self.assertEqual("quarantine", self.resource(slot)["state"])
        self.assertFalse(self.resource(slot).get("reuse_exhausted"))
        store.maintenance(max_age=60, max_idle=300, min_ready=1, min_ttl=300)
        check = store.take_check("default", max_age=60, timeout=10)
        store.finish_check(check, success=True, exit_ip="198.51.100.1", region="US", check_interval=0)
        self.assertEqual("rotation_wait", self.resource(slot)["state"])
