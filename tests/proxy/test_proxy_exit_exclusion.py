"""注册换线只排除上一实际出口，并保留统一池等待和取消语义。"""
from contextlib import contextmanager
from datetime import datetime, timedelta
import threading
import uuid
from unittest.mock import patch

from core.operations.runtime import OperationCancelled
from core.proxy import pool as proxy_pool
from core.proxy.provider import ProxyLease, acquire_registration_proxy, release_proxy
from core.storage import records as record_store
from core.storage.proxy import leases as lease_store, pool as store
from tests.support_pg import PostgresTestCase


class ProxyExitExclusionTests(PostgresTestCase):
    urls = [f"http://192.0.2.{number}:8080" for number in range(1, 5)]
    policy = {"min_ready": 1, "max_size": 20, "wait_timeout": 0, "min_ttl": 300,
              "max_age": 60, "max_idle": 300, "workers": 1}

    @contextmanager
    def environment(self):
        with (
            patch.object(proxy_pool, "_profiles", {}),
            patch.object(proxy_pool, "settings", return_value=self.policy),
            patch.object(proxy_pool, "start"),
            patch.object(proxy_pool._stop, "is_set", return_value=False),
            patch.multiple("config.proxy", PROXY_POOL_SOURCE="manual", PROXY_POOL=self.urls,
                           PROXY_POOL_DEFAULT_COUNTRY="JP", PROXY_POOL_COUNTRIES=[],
                           PLAN_CHECK_COUNTRIES=[]),
            patch("core.proxy.provider._validate_proxy_with_retries",
                  side_effect=AssertionError("领取不能重复探测出口")),
            patch("core.proxy.provider._direct_session",
                  side_effect=AssertionError("领取不能执行网络请求")),
        ):
            yield

    def seed_ready(self, number=1, *, region="JP"):
        profile = proxy_pool._profile("proxy_pool", {"urls": self.urls})
        slot = store.reserve_slot(profile.key, "proxy_pool", max_size=20, timeout=60)
        now = datetime.now()
        endpoint = f"192.0.2.{number}:8080"
        anchor = ProxyLease(
            uuid.uuid4().hex, "proxy_pool", f"http://{endpoint}", endpoint, now,
            expires_at=now + timedelta(seconds=1800 + number),
            exit_ip=f"198.51.100.{number}", region=region,
        )
        lease_store.reserve_pending(
            lease_id=anchor.lease_id, provider=anchor.provider, endpoint=endpoint,
            proxy_url=anchor.proxy_url, acquired_at=now.isoformat(),
            expires_at=anchor.expires_at.isoformat(), purpose="pool-reserve",
        )
        lease_store.activate(lease_id=anchor.lease_id, exit_ip=anchor.exit_ip,
                             region=region, expires_at=anchor.expires_at.isoformat())
        self.assertTrue(store.publish(slot, anchor))
        return slot, anchor

    def claim(self, excluded_exit_ip):
        profile = proxy_pool._profile("proxy_pool", {"urls": self.urls})
        return store.claim(profile.key, min_ttl=300, max_age=60,
                           correlation={"purpose": "registration"},
                           excluded_exit_ip=excluded_exit_ip)

    def assert_ready(self, slot):
        self.assertEqual("ready", record_store.get_row(store.RESOURCES, slot["id"])["state"])

    def test_manual_release_keeps_old_exit_ready_but_registration_gets_other_matching_country(self):
        with self.environment():
            old_slot, _ = self.seed_ready(1)
            self.seed_ready(2, region="VN")
            _, next_anchor = self.seed_ready(3)
            previous = acquire_registration_proxy(country="JP", timeout=1)
            release_proxy(previous, reason="registration_route_recovery", fault=False)
            self.assert_ready(old_slot)

            replacement = acquire_registration_proxy(
                country="JP", excluded_exit_ip=previous.exit_ip, timeout=1,
            )

            self.assertEqual(next_anchor.exit_ip, replacement.exit_ip)
            self.assertEqual("JP", replacement.region)
            self.assert_ready(old_slot)

    def test_locked_candidate_loop_skips_all_resources_with_same_actual_exit(self):
        with self.environment():
            old_slot, old_anchor = self.seed_ready(1)
            duplicate_slot = store.reserve_slot(old_slot["profile_key"], "proxy_pool",
                                                max_size=20, timeout=60)
            self.assertTrue(store.publish(duplicate_slot, old_anchor))
            _, next_anchor = self.seed_ready(2)

            replacement = self.claim(" 198.51.100.1 ")

            self.assertEqual(next_anchor.exit_ip, replacement.exit_ip)
            self.assert_ready(old_slot)
            self.assert_ready(duplicate_slot)

    def test_exclusion_uses_locked_anchor_exit_instead_of_resource_snapshot(self):
        with self.environment():
            old_slot, old_anchor = self.seed_ready(1)
            record_store.patch_row(store.RESOURCES, old_slot["id"], {"exit_ip": "203.0.113.99"})
            _, next_anchor = self.seed_ready(2)

            self.assertEqual(next_anchor.exit_ip, self.claim(old_anchor.exit_ip).exit_ip)
            self.assert_ready(old_slot)

    def test_missing_previous_exit_keeps_existing_exclusive_claim_behavior(self):
        with self.environment():
            slot, anchor = self.seed_ready()
            lease = self.claim(None)
            self.assertEqual(anchor.exit_ip, lease.exit_ip)
            store.release(lease, reason="completed")
            self.assertEqual(anchor.exit_ip, self.claim(" ").exit_ip)
            self.assertEqual("leased", record_store.get_row(store.RESOURCES, slot["id"])["state"])

    def test_missing_candidate_exit_is_skipped_only_when_replacement_must_prove_new_exit(self):
        with self.environment():
            slot, anchor = self.seed_ready()
            anchor_row = record_store.get_row_by(store.LEASES, "lease_id", anchor.lease_id)
            record_store.patch_row(store.LEASES, anchor_row["id"], {"exit_ip": None})
            record_store.patch_row(store.RESOURCES, slot["id"], {"exit_ip": None})

            self.assertIsNone(self.claim("198.51.100.99"))
            self.assert_ready(slot)
            lease = self.claim(None)

            self.assertIsNone(lease.exit_ip)
            self.assertEqual(anchor.proxy_url, lease.proxy_url)

    def test_no_new_exit_waits_until_background_publishes_other_inventory(self):
        notices = []
        published = []
        with self.environment():
            old_slot, old_anchor = self.seed_ready()

            def publish_after_wait(_seconds):
                published.append(self.seed_ready(2)[1])

            with patch.object(proxy_pool._stop, "wait", side_effect=publish_after_wait):
                replacement = acquire_registration_proxy(
                    country="JP", excluded_exit_ip=old_anchor.exit_ip,
                    progress_callback=notices.append,
                )

            self.assertEqual(1, len(published))
            self.assertEqual("198.51.100.2", replacement.exit_ip)
            self.assertTrue(any("等待后台补货" in message for message in notices))
            self.assertTrue(all(profile.waiting == 0 for profile in proxy_pool._profiles.values()))
            self.assert_ready(old_slot)

    def test_no_new_exit_preserves_explicit_timeout_without_consuming_old_inventory(self):
        with self.environment():
            old_slot, old_anchor = self.seed_ready()

            with self.assertRaises(proxy_pool.ProxyPoolTimeout):
                acquire_registration_proxy(
                    country="JP", excluded_exit_ip=old_anchor.exit_ip, timeout=.05,
                )

            self.assert_ready(old_slot)
            self.assertTrue(all(profile.waiting == 0 for profile in proxy_pool._profiles.values()))

    def test_no_new_exit_still_observes_cancellation_while_waiting(self):
        cancelled = threading.Event()
        with self.environment():
            old_slot, old_anchor = self.seed_ready()

            def checkpoint():
                if cancelled.is_set():
                    raise OperationCancelled("测试取消等待")

            with patch.object(proxy_pool._stop, "wait", side_effect=lambda _seconds: cancelled.set()):
                with self.assertRaises(OperationCancelled):
                    acquire_registration_proxy(
                        country="JP", excluded_exit_ip=old_anchor.exit_ip, cancel=checkpoint,
                    )

            self.assert_ready(old_slot)
            self.assertTrue(all(profile.waiting == 0 for profile in proxy_pool._profiles.values()))
