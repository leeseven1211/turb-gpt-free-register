# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import unittest

from core import proxy_lease_store, record_store
from tests.support_pg import PostgresTestCase


class ProxyLeaseStoreTests(PostgresTestCase):
    def _reserve(self, lease_id, endpoint, *, job_id=None):
        now = datetime.now()
        proxy_lease_store.reserve_pending(
            lease_id=lease_id,
            provider="1024proxy",
            endpoint=endpoint,
            proxy_url=f"http://{endpoint}",
            acquired_at=now.isoformat(timespec="seconds"),
            expires_at=(now + timedelta(minutes=30)).isoformat(timespec="seconds"),
            batch_id="batch-1",
            job_id=job_id,
        )

    def test_endpoint_is_mutually_exclusive_while_pending_or_recent(self):
        self._reserve("lease-1", "1.2.3.4:8080", job_id=1)
        with self.assertRaises(proxy_lease_store.DuplicateProxyLeaseError):
            self._reserve("lease-2", "1.2.3.4:8080", job_id=2)

        proxy_lease_store.activate(
            lease_id="lease-1",
            exit_ip="8.8.8.8",
            region="US",
            expires_at=(datetime.now() + timedelta(minutes=30)).isoformat(timespec="seconds"),
        )
        proxy_lease_store.release(
            lease_id="lease-1",
            recent_until=(datetime.now() + timedelta(minutes=5)).isoformat(timespec="seconds"),
            reason="test",
        )
        with self.assertRaises(proxy_lease_store.DuplicateProxyLeaseError):
            self._reserve("lease-3", "1.2.3.4:8080", job_id=3)

        proxy_lease_store.release(
            lease_id="lease-1",
            recent_until=(datetime.now() - timedelta(seconds=1)).isoformat(timespec="seconds"),
            reason="expire",
        )
        self._reserve("lease-4", "1.2.3.4:8080", job_id=4)
        proxy_lease_store.abort("lease-4")

    def test_exit_ip_is_mutually_exclusive_across_endpoints(self):
        self._reserve("lease-1", "1.2.3.4:8080")
        self._reserve("lease-2", "5.6.7.8:9000")
        expires_at = (datetime.now() + timedelta(minutes=30)).isoformat(timespec="seconds")
        proxy_lease_store.activate(
            lease_id="lease-1",
            exit_ip="8.8.8.8",
            region="US",
            expires_at=expires_at,
        )
        with self.assertRaises(proxy_lease_store.DuplicateProxyLeaseError):
            proxy_lease_store.activate(
                lease_id="lease-2",
                exit_ip="8.8.8.8",
                region="US",
                expires_at=expires_at,
            )
        proxy_lease_store.abort("lease-2")

        rows = record_store.list_rows(
            record_store.PROXY_LEASES,
            where='"state" IN (\'pending\', \'leased\', \'recent\')',
        )
        self.assertEqual([row["lease_id"] for row in rows], ["lease-1"])


if __name__ == "__main__":
    unittest.main()
