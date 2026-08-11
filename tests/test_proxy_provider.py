# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from core import proxy_provider


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


class ProxyProviderTests(unittest.TestCase):
    def setUp(self):
        proxy_provider._ACTIVE_ENDPOINTS.clear()
        proxy_provider._RECENT_ENDPOINTS.clear()
        proxy_provider._LAST_ACQUIRE_AT = 0.0

    def tearDown(self):
        proxy_provider._ACTIVE_ENDPOINTS.clear()
        proxy_provider._RECENT_ENDPOINTS.clear()

    def test_parse_proxy_response_supports_txt_and_json(self):
        self.assertEqual(proxy_provider.parse_proxy_response("1.2.3.4:8080\n"), "1.2.3.4:8080")
        self.assertEqual(
            proxy_provider.parse_proxy_response('{"data":[{"ip":"5.6.7.8","port":9000}]}'),
            "5.6.7.8:9000",
        )

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

    def test_public_values_are_masked(self):
        self.assertEqual(proxy_provider.mask_endpoint("1.2.3.4:8080"), "1.2.*.*:8080")
        self.assertEqual(proxy_provider.mask_proxy_url("http://user:pass@1.2.3.4:8080"), "http://***:***@1.2.*.*:8080")


if __name__ == "__main__":
    unittest.main()
