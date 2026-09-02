# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace


class AuthFingerprintSummaryTests(unittest.TestCase):
    def test_clean_summary_allowlists_public_fields(self):
        from core.auth_fingerprint import clean_safe_fingerprint_summary

        cleaned = clean_safe_fingerprint_summary({
            "schema_version": 1,
            "source": "protocol",
            "profile_ref": "abc123",
            "screen_width": "1440",
            "navigator_languages": ["ja-JP", "en-US", "ignored"],
            "device_id": "private-device-id",
            "oai_session_id": "private-session-id",
            "proxy_url": "http://user:password@example.test:8080",
            "access_token": "private-token",
            "email": "account@example.test",
            "unknown": "not-allowed",
        })

        self.assertEqual(1, cleaned["schema_version"])
        self.assertEqual(1440, cleaned["screen_width"])
        self.assertEqual(["ja-JP", "en-US", "ignored"], cleaned["navigator_languages"])
        for forbidden in {
            "device_id", "oai_session_id", "proxy_url", "access_token", "email", "unknown",
        }:
            self.assertNotIn(forbidden, cleaned)

    def test_build_summary_reads_existing_session_without_private_ids(self):
        from core.auth_fingerprint import build_safe_fingerprint_summary

        session = SimpleNamespace(
            browser_profile={
                "browser_family": "chrome",
                "browser_os": "macOS",
                "chrome_major": "149",
                "user_agent": "Mozilla/5.0 Chrome/149",
                "accept_language": "ja-JP,ja;q=0.9",
                "navigator_language": "ja-JP",
                "navigator_languages": ["ja-JP"],
                "timezone_iana": "Asia/Tokyo",
                "timezone_offset_minutes": 540,
                "screen_width": 1440,
                "screen_height": 900,
                "device_pixel_ratio": 2,
                "hardware_concurrency": 10,
                "device_memory": 16,
                "js_heap_size_limit": 4294,
            },
            exit_geo={"country": "JP", "timezone": "Asia/Tokyo", "ip": "203.0.113.7"},
            device_id="private-device-id",
            oai_session_id="private-session-id",
            proxy="http://user:password@example.test:8080",
        )

        summary = build_safe_fingerprint_summary(
            session,
            source="protocol",
            profile_version=1,
            profile_ref="abc123",
            route={"proxy_mode": "proxy", "proxy_url": session.proxy},
            transport_profile="curl_cffi:chrome146",
        )

        self.assertEqual("protocol", summary["source"])
        self.assertEqual(1, summary["profile_version"])
        self.assertEqual("proxy", summary["proxy_mode"])
        self.assertEqual("JP", summary["geo_country"])
        self.assertNotIn("ip", summary)
        self.assertNotIn("device_id", summary)
        self.assertNotIn("oai_session_id", summary)
        self.assertNotIn("proxy_url", summary)

    def test_text_rendering_contains_observation_not_credentials(self):
        from core.auth_fingerprint import safe_fingerprint_summary_text

        text = safe_fingerprint_summary_text({
            "source": "protocol",
            "profile_ref": "abc123",
            "browser_family": "chrome",
            "browser_version": "149",
            "browser_os": "macOS",
            "screen_width": 1440,
            "screen_height": 900,
            "device_pixel_ratio": 2,
            "navigator_language": "ja-JP",
            "device_id": "private-device-id",
            "password": "private-password",
        })

        self.assertIn("browser=chrome/149/macOS", text)
        self.assertIn("screen=1440x900@2", text)
        self.assertNotIn("private-device-id", text)
        self.assertNotIn("private-password", text)

