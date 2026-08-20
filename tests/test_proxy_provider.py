# -*- coding: utf-8 -*-
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from unittest.mock import patch

import requests

from core import proxy_provider
from core.codex_retry_service import CodexRetryStopped


class _FakeResponse:
    def __init__(self, *, text="", payload=None, status_code=200):
        self.text = text
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "ipinfo.io" in url:
            return _FakeResponse(payload={"ip": "8.8.8.8", "country": "US"})
        return _FakeResponse(text="1.2.3.4:8080\n")


class _SequenceSession:
    def __init__(self, endpoints):
        self.endpoints = iter(endpoints)
        self.calls = []
        self.lock = threading.Lock()

    def get(self, url, **kwargs):
        with self.lock:
            self.calls.append((url, kwargs))
            endpoint = next(self.endpoints)
        return _FakeResponse(text=f"{endpoint}\n")


class _BatchSession:
    def __init__(self):
        self.endpoints = [
            "1.2.3.4:8080",
            "5.6.7.8:9000",
            "9.10.11.12:10000",
        ]
        self.exit_ips = {
            "1.2.3.4:8080": "8.8.8.8",
            "5.6.7.8:9000": "9.9.9.9",
            "9.10.11.12:10000": "1.1.1.1",
        }
        self.calls = []
        self.lock = threading.Lock()
        self.api_call_count = 0

    def get(self, url, **kwargs):
        with self.lock:
            self.calls.append((url, kwargs))
        if "ipinfo.io" in url:
            proxy_url = str((kwargs.get("proxies") or {}).get("http") or "")
            endpoint = proxy_url.rsplit("://", 1)[-1]
            return _FakeResponse(payload={"ip": self.exit_ips[endpoint], "country": "US"})
        self.api_call_count += 1
        endpoints = self.endpoints if self.api_call_count == 1 else ["13.14.15.16:11000"]
        self.exit_ips.setdefault("13.14.15.16:11000", "4.4.4.4")
        return _FakeResponse(text="\n".join(endpoints) + "\n")


class ProxyProviderTests(unittest.TestCase):
    def setUp(self):
        from core import session as browser_session

        self._persist_patcher = patch("config.proxy.PROXY_1024_PERSIST_LEASES", False)
        self._persist_patcher.start()
        proxy_provider._ACTIVE_ENDPOINTS.clear()
        proxy_provider._RECENT_ENDPOINTS.clear()
        proxy_provider._PENDING_ENDPOINTS.clear()
        proxy_provider._LAST_ACQUIRE_AT = 0.0
        proxy_provider._BATCH_STATES.clear()
        browser_session._GEO_CACHE.clear()

    def tearDown(self):
        from core import session as browser_session

        self._persist_patcher.stop()
        proxy_provider._ACTIVE_ENDPOINTS.clear()
        proxy_provider._RECENT_ENDPOINTS.clear()
        proxy_provider._PENDING_ENDPOINTS.clear()
        proxy_provider._BATCH_STATES.clear()
        browser_session._GEO_CACHE.clear()

    @patch("core.proxy_provider._direct_session")
    @patch("core.proxy_lease_store.release")
    @patch("core.proxy_lease_store.activate")
    @patch("core.proxy_lease_store.reserve_pending")
    def test_persistent_lease_lifecycle_is_written_around_validation(
        self, reserve_pending, activate, release, direct_session
    ):
        direct_session.return_value = _FakeSession()
        with patch.multiple(
            "config.proxy",
            PROXY_1024_PERSIST_LEASES=True,
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_MAX_ATTEMPTS=1,
            PROXY_1024_RECENT_TTL=1800,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ):
            lease = proxy_provider.acquire_1024_proxy(
                api_url="https://white.1024proxy.com/white/api?region=US&type=txt",
                protocol="http",
                region="US",
                validate=True,
                job_id="persistent-test",
            )
            proxy_provider.release_proxy(lease, reason="test")

        reserve_pending.assert_called_once()
        activate.assert_called_once()
        release.assert_called_once()
        self.assertTrue(lease.metadata["persistent_lease"])

    def test_parse_proxy_response_supports_txt_and_json(self):
        self.assertEqual(proxy_provider.parse_proxy_response("1.2.3.4:8080\n"), "1.2.3.4:8080")
        self.assertEqual(
            proxy_provider.parse_proxy_response('{"data":[{"ip":"5.6.7.8","port":9000}]}'),
            "5.6.7.8:9000",
        )
        self.assertEqual(
            proxy_provider.parse_proxy_responses("1.2.3.4:8080\n5.6.7.8:9000\n1.2.3.4:8080\n"),
            ["1.2.3.4:8080", "5.6.7.8:9000"],
        )
        self.assertEqual(
            proxy_provider.parse_proxy_responses(
                '{"data":[{"ip":"5.6.7.8","port":9000},{"ip":"9.10.11.12","port":10000}]}'
            ),
            ["5.6.7.8:9000", "9.10.11.12:10000"],
        )

    @patch("core.proxy_provider.time.sleep", return_value=None)
    @patch("core.proxy_provider._direct_session")
    def test_codex_stop_signal_is_not_swallowed_by_proxy_retry(self, direct_session, _sleep):
        class StoppedSession:
            def get(self, *_args, **_kwargs):
                raise CodexRetryStopped("stop")

        direct_session.return_value = StoppedSession()
        with patch.multiple(
            "config.proxy",
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_MAX_ATTEMPTS=5,
            PROXY_1024_RECENT_TTL=1800,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ):
            with self.assertRaises(CodexRetryStopped):
                proxy_provider.acquire_1024_proxy(
                    api_url="https://white.1024proxy.com/white/api?region=US&type=txt",
                    protocol="http",
                    region="US",
                    validate=False,
                    job_id="stop-test",
                )

        self.assertFalse(proxy_provider._PENDING_ENDPOINTS)

    def test_build_api_url_forces_one_ip_and_configured_session(self):
        url = proxy_provider._build_api_url(
            "https://white.1024proxy.com/white/api?region=Rand&num=9&time=10&type=txt",
            30,
        )
        self.assertIn("region=Rand", url)
        self.assertIn("num=1", url)
        self.assertIn("time=30", url)

    def test_build_api_url_region_setting_overrides_url(self):
        url = proxy_provider._build_api_url(
            "https://white.1024proxy.com/white/api?region=US&num=1&time=10&type=txt",
            30,
            "jp",
        )
        self.assertIn("region=JP", url)
        self.assertNotIn("region=US", url)

    def test_region_accepts_rand_and_rejects_invalid_value(self):
        self.assertEqual(proxy_provider._normalize_region("random"), "Rand")
        with self.assertRaisesRegex(ValueError, "ISO 两位代码"):
            proxy_provider._normalize_region("United States")

    @patch("core.proxy_provider.time.sleep", return_value=None)
    @patch("core.proxy_provider._direct_session")
    def test_acquire_validates_and_releases_local_lease(self, direct_session, _sleep):
        fake = _FakeSession()
        direct_session.return_value = fake
        with patch.multiple(
            "config.proxy",
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_MAX_ATTEMPTS=1,
            PROXY_1024_RECENT_TTL=1800,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ):
            lease = proxy_provider.acquire_1024_proxy(
                api_url="https://white.1024proxy.com/white/api?region=Rand&num=1&time=10&type=txt",
                protocol="http",
                region="US",
                session_minutes=30,
                validate=True,
                job_id=12,
            )

        self.assertEqual(lease.proxy_url, "http://1.2.3.4:8080")
        self.assertEqual(lease.exit_ip, "8.8.8.8")
        self.assertEqual(lease.region, "US")
        self.assertIn("1.2.3.4:8080", proxy_provider._ACTIVE_ENDPOINTS)
        api_call = fake.calls[0]
        self.assertIn("num=1", api_call[0])
        self.assertIn("time=30", api_call[0])

        proxy_provider.release_proxy(lease, reason="test")
        self.assertEqual(lease.state, "released")
        self.assertNotIn("1.2.3.4:8080", proxy_provider._ACTIVE_ENDPOINTS)

    @patch("core.proxy_provider.time.sleep", return_value=None)
    @patch("core.proxy_provider._direct_session")
    def test_validation_seeds_browser_session_geo_cache(self, direct_session, _sleep):
        from core import session as browser_session

        direct_session.return_value = _FakeSession()
        with patch.multiple(
            "config.proxy",
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_MAX_ATTEMPTS=1,
            PROXY_1024_RECENT_TTL=0,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ):
            lease = proxy_provider.acquire_1024_proxy(
                api_url="https://white.1024proxy.com/white/api?region=US&type=txt",
                protocol="http",
                region="US",
                validate=True,
                job_id="geo-cache-test",
            )

        self.assertEqual(
            browser_session._GEO_CACHE[lease.proxy_url],
            {
                "ip": "8.8.8.8",
                "country": "US",
                "region": None,
                "city": None,
                "timezone": "",
                "org": None,
            },
        )
        proxy_provider.release_proxy(lease, reason="test")

    def test_browser_session_uses_seeded_geo_without_second_request(self):
        from core import session as browser_session

        proxy_url = "http://1.2.3.4:8080"
        browser_session.seed_exit_geo(
            proxy_url,
            {
                "ip": "8.8.8.8",
                "country": "US",
                "city": "Mountain View",
                "timezone": "America/Los_Angeles",
                "org": "Example ISP",
            },
        )
        instance = object.__new__(browser_session.BrowserSession)
        instance.proxy = proxy_url

        self.assertEqual(instance._detect_exit_geo()["country"], "US")
        self.assertEqual(instance._detect_exit_geo()["timezone"], "America/Los_Angeles")

    @patch("core.proxy_provider.time.sleep", return_value=None)
    @patch("core.proxy_provider._direct_session")
    def test_task_id_rotates_remote_sticky_session(self, direct_session, _sleep):
        fake = _FakeSession()
        direct_session.return_value = fake
        with patch.multiple(
            "config.proxy",
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_MAX_ATTEMPTS=1,
            PROXY_1024_RECENT_TTL=1800,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=True,
        ):
            lease = proxy_provider.acquire_1024_proxy(
                api_url="https://white.1024proxy.com/white/api?region=US&num=1&time=10&type=txt",
                protocol="http",
                session_minutes=30,
                validate=False,
                job_id=12,
            )
        self.assertIn("time=42", fake.calls[0][0])
        self.assertEqual(lease.metadata["session_minutes"], 42)

    @patch("core.proxy_provider.time.sleep", return_value=None)
    @patch("core.proxy_provider._validate_proxy", return_value=("8.8.8.8", "US"))
    @patch("core.proxy_provider._direct_session")
    def test_known_duplicate_endpoint_retries_before_validation(self, direct_session, validate_proxy, _sleep):
        duplicate = "1.2.3.4:8080"
        fresh = "5.6.7.8:9000"
        proxy_provider._RECENT_ENDPOINTS[duplicate] = float("inf")
        direct_session.return_value = _SequenceSession([duplicate, fresh])
        with patch.multiple(
            "config.proxy",
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_MAX_ATTEMPTS=2,
            PROXY_1024_RECENT_TTL=1800,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ):
            lease = proxy_provider.acquire_1024_proxy(
                api_url="https://white.1024proxy.com/white/api?region=US&type=txt",
                protocol="http",
                region="US",
                validate=True,
                job_id=21,
            )

        self.assertEqual(lease.endpoint, fresh)
        validate_proxy.assert_called_once_with("http://5.6.7.8:9000", 5.0)
        self.assertFalse(proxy_provider._PENDING_ENDPOINTS)

    @patch("core.proxy_provider.time.sleep", return_value=None)
    @patch(
        "core.proxy_provider._validate_proxy",
        side_effect=[requests.Timeout("temporary timeout"), ("8.8.8.8", "US")],
    )
    @patch("core.proxy_provider._direct_session")
    def test_transient_validation_error_retries_same_endpoint(
        self, direct_session, validate_proxy, _sleep
    ):
        direct_session.return_value = _SequenceSession(["1.2.3.4:8080"])
        with patch.multiple(
            "config.proxy",
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_MAX_ATTEMPTS=1,
            PROXY_1024_VALIDATE_ATTEMPTS=2,
            PROXY_1024_RECENT_TTL=0,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ):
            lease = proxy_provider.acquire_1024_proxy(
                api_url="https://white.1024proxy.com/white/api?region=US&type=txt",
                protocol="http",
                region="US",
                validate=True,
                job_id=22,
            )

        self.assertEqual(lease.endpoint, "1.2.3.4:8080")
        self.assertEqual(validate_proxy.call_count, 2)
        self.assertEqual(len(direct_session.return_value.calls), 1)

    @patch("core.proxy_provider._direct_session")
    def test_concurrent_acquires_validate_different_endpoints_in_parallel(self, direct_session):
        direct_session.return_value = _SequenceSession(["1.2.3.4:8080", "5.6.7.8:9000"])
        barrier = threading.Barrier(2)
        state_lock = threading.Lock()
        active_validations = 0
        max_active_validations = 0

        def validate(proxy_url, _timeout):
            nonlocal active_validations, max_active_validations
            with state_lock:
                active_validations += 1
                max_active_validations = max(max_active_validations, active_validations)
            try:
                barrier.wait(timeout=2)
                exit_ip = "8.8.8.8" if "1.2.3.4" in proxy_url else "9.9.9.9"
                return exit_ip, "US"
            finally:
                with state_lock:
                    active_validations -= 1

        with patch.multiple(
            "config.proxy",
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_MAX_ATTEMPTS=1,
            PROXY_1024_RECENT_TTL=1800,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ), patch("core.proxy_provider._validate_proxy", side_effect=validate):
            with ThreadPoolExecutor(max_workers=2) as executor:
                leases = list(executor.map(
                    lambda job_id: proxy_provider.acquire_1024_proxy(
                        api_url="https://white.1024proxy.com/white/api?region=US&type=txt",
                        protocol="http",
                        region="US",
                        validate=True,
                        job_id=job_id,
                    ),
                    (31, 32),
                ))

        self.assertEqual(max_active_validations, 2)
        self.assertEqual({lease.endpoint for lease in leases}, {"1.2.3.4:8080", "5.6.7.8:9000"})
        self.assertFalse(proxy_provider._PENDING_ENDPOINTS)

    @patch("core.proxy_provider.time.sleep", return_value=None)
    @patch("core.proxy_provider._direct_session")
    def test_batch_acquire_requests_num_and_validates_candidates_in_parallel(self, direct_session, _sleep):
        fake = _BatchSession()
        direct_session.return_value = fake
        with patch.multiple(
            "config.proxy",
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_VALIDATE_ATTEMPTS=1,
            PROXY_1024_RECENT_TTL=0,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ):
            leases = proxy_provider.acquire_1024_proxy_batch(
                count=3,
                api_url="https://white.1024proxy.com/white/api?region=US&type=txt",
                protocol="http",
                region="US",
                session_minutes=30,
                validate=True,
                job_id="batch-test",
            )

        self.assertEqual(len(leases), 3)
        self.assertEqual({lease.exit_ip for lease in leases}, {"8.8.8.8", "9.9.9.9", "1.1.1.1"})
        api_calls = [url for url, _kwargs in fake.calls if "white.1024proxy.com" in url]
        self.assertEqual(len(api_calls), 1)
        self.assertIn("num=3", api_calls[0])
        self.assertTrue(all(lease.region == "US" for lease in leases))
        self.assertFalse(proxy_provider._PENDING_ENDPOINTS)
        for lease in leases:
            proxy_provider.release_proxy(lease, reason="test")

    @patch("core.proxy_provider.time.sleep", return_value=None)
    @patch("core.proxy_provider._validate_proxy_with_retries")
    @patch("core.proxy_provider._direct_session")
    def test_batch_acquire_refills_validation_gap(self, direct_session, validate_proxy, _sleep):
        fake = _BatchSession()
        direct_session.return_value = fake

        def validate(proxy_url, _timeout, *, attempts):
            if "9.10.11.12" in proxy_url:
                raise RuntimeError("temporary SSL failure")
            endpoint = proxy_url.rsplit("://", 1)[-1]
            return fake.exit_ips[endpoint], "US"

        validate_proxy.side_effect = validate
        with patch.multiple(
            "config.proxy",
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_VALIDATE_ATTEMPTS=1,
            PROXY_1024_RECENT_TTL=0,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ):
            leases = proxy_provider.acquire_1024_proxy_batch(
                count=3,
                api_url="https://white.1024proxy.com/white/api?region=US&type=txt",
                protocol="http",
                region="US",
                session_minutes=30,
                validate=True,
                job_id="batch-refill-test",
            )

        self.assertEqual(len(leases), 3)
        api_calls = [url for url, _kwargs in fake.calls if "white.1024proxy.com" in url]
        self.assertEqual(len(api_calls), 2)
        self.assertIn("num=3", api_calls[0])
        self.assertIn("num=1", api_calls[1])
        for lease in leases:
            proxy_provider.release_proxy(lease, reason="test")

    @patch("core.proxy_provider.acquire_1024_proxy_batch")
    def test_registration_batch_shares_prefetched_leases_and_releases_leftovers(self, acquire_batch):
        leases = [
            proxy_provider.ProxyLease(
                lease_id=f"lease-{index}",
                provider="1024proxy",
                proxy_url=f"http://1.2.3.{index}:8080",
                endpoint=f"1.2.3.{index}:8080",
                acquired_at=datetime.now(),
                exit_ip=f"8.8.8.{index}",
                metadata={"uniqueness_key": f"8.8.8.{index}"},
            )
            for index in (1, 2, 3, 4)
        ]
        acquire_batch.return_value = leases

        with patch.multiple(
            "config.proxy",
            REGISTRATION_PROXY_MODE="1024",
        ), patch.multiple(
            "config.roxybrowser",
            REGISTRATION_DRIVER="protocol",
        ), ThreadPoolExecutor(max_workers=3) as executor:
            acquired = list(executor.map(
                lambda job_id: proxy_provider.acquire_registration_proxy(
                    job_id=job_id,
                    batch_id="batch-1",
                    batch_size=3,
                    batch_workers=3,
                ),
                (101, 102, 103),
            ))

        self.assertEqual(acquire_batch.call_count, 1)
        self.assertEqual(acquire_batch.call_args.kwargs["count"], 3)
        self.assertEqual({lease.metadata["job_id"] for lease in acquired}, {101, 102, 103})
        for _ in acquired:
            proxy_provider.finalize_registration_proxy_batch("batch-1")
        self.assertNotIn("batch-1", proxy_provider._BATCH_STATES)
        self.assertEqual([lease.state for lease in leases], ["leased", "leased", "leased", "released"])
        for lease in acquired:
            proxy_provider.release_proxy(lease, reason="test")

    @patch("core.proxy_provider.time.sleep", return_value=None)
    @patch("core.proxy_provider._validate_proxy", side_effect=[("1.1.1.1", "CA"), ("8.8.8.8", "US")])
    @patch("core.proxy_provider._direct_session")
    def test_acquire_rejects_actual_country_mismatch(self, direct_session, validate_proxy, _sleep):
        fake = _FakeSession()
        direct_session.return_value = fake
        with patch.multiple(
            "config.proxy",
            PROXY_1024_API_TIMEOUT=5.0,
            PROXY_1024_MAX_ATTEMPTS=2,
            PROXY_1024_RECENT_TTL=0,
            PROXY_1024_ACQUIRE_INTERVAL=0.0,
            PROXY_1024_ROTATE_SESSION_TIME=False,
        ):
            lease = proxy_provider.acquire_1024_proxy(
                api_url="https://white.1024proxy.com/white/api?region=US&type=txt",
                protocol="http",
                region="US",
                session_minutes=30,
                validate=True,
                job_id=99,
            )
        self.assertEqual(validate_proxy.call_count, 2)
        self.assertEqual(lease.region, "US")
        self.assertEqual(lease.exit_ip, "8.8.8.8")
        self.assertFalse(proxy_provider._PENDING_ENDPOINTS)

    def test_public_values_are_masked(self):
        self.assertEqual(proxy_provider.mask_endpoint("1.2.3.4:8080"), "1.2.*.*:8080")
        self.assertEqual(proxy_provider.mask_proxy_url("http://user:pass@1.2.3.4:8080"), "http://***:***@1.2.*.*:8080")


if __name__ == "__main__":
    unittest.main()
