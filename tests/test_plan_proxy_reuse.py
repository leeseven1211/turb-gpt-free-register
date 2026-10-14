"""验证套餐查询共享线路的独立租约和严格线路隔离。"""
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from types import SimpleNamespace
import uuid
import unittest
from unittest.mock import patch

from core import account_proxy, proxy_lease_store, proxy_provider, record_store
from tests.support_pg import PostgresTestCase


class PlanProxyReuseTests(PostgresTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.multiple(
            "config.proxy", PROXY_1024_PERSIST_LEASES=True,
            PROXY_1024_ACQUIRE_INTERVAL=0.0, PROXY_1024_MAX_ATTEMPTS=1,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ))
        self.stack.enter_context(patch("core.proxy_provider.time.sleep"))
        self.stack.enter_context(patch("core.proxy_provider._direct_session", return_value=SimpleNamespace(
            get=lambda *_args, **_kwargs: SimpleNamespace(
                text="192.0.2.10:8080", raise_for_status=lambda: None,
            ),
        )))
        self.validate = self.stack.enter_context(patch(
            "core.proxy_provider._validate_proxy_with_retries", return_value=("203.0.113.20", "US"),
        ))
        for name in ("_ACTIVE_ENDPOINTS", "_RECENT_ENDPOINTS", "_PENDING_ENDPOINTS", "_SHARED_LEASES"):
            value = getattr(proxy_provider, name, None)
            if value is not None:
                self.stack.enter_context(patch.object(proxy_provider, name, type(value)()))

    def _acquire(self, *, shared=False, purpose="plan-check"):
        return proxy_provider.fetch_1024_proxy(
            api_url="https://proxy.example.test/api", region="US", validate=True,
            purpose=purpose, allow_reuse=shared,
        )

    def _reserve_shared(self, *, exit_ip="203.0.113.30", expires_in=1800):
        now = datetime.now()
        lease_id = uuid.uuid4().hex
        proxy_lease_store.reserve_pending(
            lease_id=lease_id, provider="1024proxy", endpoint=f"198.18.0.{lease_id[:4]}:8080",
            proxy_url="http://198.18.0.1:8080", acquired_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=expires_in)).isoformat(),
            purpose="plan-check", allow_reuse=True,
        )
        return lease_id, now + timedelta(seconds=expires_in)

    def test_shared_queries_release_only_their_own_leases(self):
        strict = self._acquire(purpose="registration")
        first = self._acquire(shared=True)
        second = self._acquire(shared=True)
        self.assertEqual(3, len({strict.lease_id, first.lease_id, second.lease_id}))
        self.assertEqual(3, self.validate.call_count)
        self.assertEqual(3, len(proxy_lease_store.list_page(view="current")))

        proxy_provider.release_proxy(first)
        rows = {row["lease_id"]: row["state"] for row in record_store.list_rows(record_store.PROXY_LEASES)}
        self.assertEqual("released", rows[first.lease_id])
        self.assertEqual("shared_leased", rows[second.lease_id])
        self.assertEqual("leased", rows[strict.lease_id])
        self.assertIs(strict, proxy_provider._ACTIVE_ENDPOINTS[strict.endpoint])
        self.assertNotIn(first.lease_id, proxy_provider._SHARED_LEASES)
        self.assertIn(second.lease_id, proxy_provider._SHARED_LEASES)

        with self.assertRaisesRegex(RuntimeError, "重复代理"):
            self._acquire(purpose="registration")
        proxy_provider.release_proxy(second)
        self.assertIs(strict, proxy_provider._ACTIVE_ENDPOINTS[strict.endpoint])

    def test_shared_query_can_reuse_recent_endpoint_without_removing_isolation(self):
        strict = self._acquire(purpose="registration")
        proxy_provider.release_proxy(strict)
        until = proxy_provider._RECENT_ENDPOINTS[strict.endpoint]
        shared = self._acquire(shared=True)
        proxy_provider.release_proxy(shared)
        self.assertEqual(until, proxy_provider._RECENT_ENDPOINTS[strict.endpoint])
        with self.assertRaisesRegex(RuntimeError, "重复代理"):
            self._acquire(purpose="registration")

    def test_shared_exit_still_requires_expected_country_and_aborts_reservation(self):
        self.validate.return_value = ("203.0.113.20", "JP")
        with self.assertRaisesRegex(RuntimeError, "实际出口地区不匹配"):
            self._acquire(shared=True)
        self.assertEqual([], record_store.list_rows(record_store.PROXY_LEASES))
        self.assertEqual({}, proxy_provider._SHARED_LEASES)

    def test_shared_lease_expiry_releases_abandoned_queries(self):
        lease = self._acquire(shared=True)
        row = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", lease.lease_id)
        record_store.patch_row(record_store.PROXY_LEASES, row["id"], {
            "expires_at": (datetime.now() - timedelta(seconds=1)).isoformat(timespec="seconds"),
        })
        proxy_lease_store._cleanup_expired()
        self.assertEqual([], proxy_lease_store.list_page(view="current"))
        self.assertEqual("released", proxy_lease_store.list_page(view="history")[0]["state"])

    def test_persistent_strict_uniqueness_survives_without_process_memory(self):
        strict = self._acquire(purpose="registration")
        proxy_provider._ACTIVE_ENDPOINTS.clear()
        shared = self._acquire(shared=True)
        proxy_provider._SHARED_LEASES.clear()
        with self.assertRaisesRegex(RuntimeError, "占用"):
            self._acquire(purpose="registration")
        proxy_provider.release_proxy(shared)
        row = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", strict.lease_id)
        self.assertEqual("leased", row["state"])

    def test_shared_activation_and_release_are_idempotent_and_do_not_resurrect(self):
        strict = self._acquire(purpose="registration")
        shared = self._acquire(shared=True)
        proxy_lease_store.activate(
            lease_id=shared.lease_id, exit_ip=shared.exit_ip, region=shared.region,
            expires_at=shared.expires_at.isoformat(timespec="seconds"),
        )
        for _ in range(2):
            proxy_lease_store.release(
                lease_id=shared.lease_id, reason="test",
                recent_until=(datetime.now() + timedelta(minutes=30)).isoformat(timespec="seconds"),
            )
        row = record_store.get_row_by(record_store.PROXY_LEASES, "lease_id", shared.lease_id)
        self.assertEqual("released", row["state"])
        self.assertIsNone(row["recent_until"])
        with self.assertRaisesRegex(RuntimeError, "已结束"):
            proxy_lease_store.activate(
                lease_id=shared.lease_id, exit_ip=shared.exit_ip, region=shared.region,
                expires_at=shared.expires_at.isoformat(timespec="seconds"),
            )
        self.assertIs(strict, proxy_provider._ACTIVE_ENDPOINTS[strict.endpoint])

    def test_shared_activation_limit_counts_released_leases_and_is_idempotent(self):
        first_id, first_expires = self._reserve_shared()
        proxy_lease_store.activate(
            lease_id=first_id, exit_ip="203.0.113.30", region="US",
            expires_at=first_expires.isoformat(timespec="seconds"), reuse_limit=1,
        )
        proxy_lease_store.activate(
            lease_id=first_id, exit_ip="203.0.113.30", region="US",
            expires_at=first_expires.isoformat(timespec="seconds"), reuse_limit=1,
        )
        proxy_lease_store.release(lease_id=first_id, reason="completed", recent_until=None)

        second_id, second_expires = self._reserve_shared()
        with self.assertRaises(proxy_lease_store.DuplicateProxyLeaseError):
            proxy_lease_store.activate(
                lease_id=second_id, exit_ip="203.0.113.30", region="US",
                expires_at=second_expires.isoformat(timespec="seconds"), reuse_limit=1,
            )

    def test_shared_activation_does_not_count_failed_pending_or_expired_leases(self):
        first_id, first_expires = self._reserve_shared(exit_ip="203.0.113.31")
        proxy_lease_store.abort(first_id)
        second_id, second_expires = self._reserve_shared(exit_ip="203.0.113.31")
        proxy_lease_store.activate(
            lease_id=second_id, exit_ip="203.0.113.31", region="US",
            expires_at=second_expires.isoformat(timespec="seconds"), reuse_limit=1,
        )

        expired_id, expired_at = self._reserve_shared(exit_ip="203.0.113.32", expires_in=-1)
        with self.assertRaises(RuntimeError):
            proxy_lease_store.activate(
                lease_id=expired_id, exit_ip="203.0.113.32", region="US",
                expires_at=expired_at.isoformat(timespec="seconds"), reuse_limit=1,
            )

    def test_shared_activation_rejects_unknown_exit_ip_and_invalid_limit(self):
        lease_id, expires_at = self._reserve_shared(exit_ip="203.0.113.33")
        with self.assertRaises(ValueError):
            proxy_lease_store.activate(
                lease_id=lease_id, exit_ip=None, region="US",
                expires_at=expires_at.isoformat(timespec="seconds"), reuse_limit=1,
            )
        with self.assertRaises(ValueError):
            proxy_lease_store.activate(
                lease_id=lease_id, exit_ip="203.0.113.33", region="US",
                expires_at=expires_at.isoformat(timespec="seconds"), reuse_limit=0,
            )

    def test_strict_acquisition_blocks_existing_shared_queries_across_processes(self):
        shared = self._acquire(shared=True)
        proxy_provider._SHARED_LEASES.clear()
        with self.assertRaisesRegex(RuntimeError, "重复代理|占用"):
            self._acquire(purpose="registration")
        proxy_provider.release_proxy(shared)
        strict = self._acquire(purpose="registration")
        self.assertEqual(shared.endpoint, strict.endpoint)

    def test_strict_exit_ip_blocks_shared_query_on_different_endpoint(self):
        shared = self._acquire(shared=True)
        proxy_provider._SHARED_LEASES.clear()
        with patch("core.proxy_provider.parse_proxy_response", return_value="192.0.2.11:8081"):
            with self.assertRaisesRegex(RuntimeError, "重复代理|占用"):
                self._acquire(purpose="registration")
        self.assertEqual([shared.lease_id], [row["lease_id"] for row in proxy_lease_store.active_rows()])

    def test_concurrent_queries_share_endpoint_with_independent_release(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            leases = list(executor.map(lambda _: self._acquire(shared=True), range(2)))
        self.assertEqual(2, len(proxy_lease_store.list_page(view="current")))
        self.assertEqual(2, len({lease.lease_id for lease in leases}))
        proxy_provider.release_proxy(leases[0])
        self.assertEqual([leases[1].lease_id], [row["lease_id"] for row in proxy_lease_store.list_page(view="current")])

    def test_memory_only_strict_acquisition_also_blocks_shared_endpoint(self):
        with patch("config.proxy.PROXY_1024_PERSIST_LEASES", False):
            shared = self._acquire(shared=True)
            with self.assertRaisesRegex(RuntimeError, "重复代理"):
                self._acquire(purpose="registration")
            proxy_provider.release_proxy(shared)
            strict = self._acquire(purpose="registration")
            self.assertEqual(shared.endpoint, strict.endpoint)


class PlanProxyReusePolicyTests(unittest.TestCase):
    def test_reuse_is_rejected_for_authentication_purposes(self):
        with patch("core.proxy_provider._direct_session") as request:
            with self.assertRaisesRegex(ValueError, "套餐查询"):
                proxy_provider.fetch_1024_proxy(
                    api_url="https://proxy.example.test/api", purpose="token-refresh", allow_reuse=True,
                )
        request.assert_not_called()

    def test_action_policy_and_explicit_override_apply_only_to_plan_check(self):
        for purpose, override, expected in (
            ("plan-check", None, True), ("plan-check", False, False),
            ("token-refresh", True, False),
        ):
            with (
                self.subTest(purpose=purpose, override=override),
                patch("config.proxy.PLAN_CHECK_PROXY_ALLOW_REUSE", True, create=True),
                patch("core.proxy_pool.acquire", return_value=SimpleNamespace(
                    proxy_url="http://192.0.2.10:8080", provider="1024proxy", region="US",
                )) as acquire,
            ):
                account_proxy.acquire_account_proxy(
                    account_id=7, purpose=purpose, region="US", source="provider:1024proxy",
                    allow_reuse=override,
                )
                self.assertEqual("1024proxy", acquire.call_args.kwargs["provider"])
                self.assertEqual(expected, acquire.call_args.kwargs.get("allow_reuse", False))
