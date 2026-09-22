# -*- coding: utf-8 -*-
"""账号列表安全投影回归。"""
from __future__ import annotations

import unittest


class AccountListProjectionTests(unittest.TestCase):
    def test_compact_account_exposes_registration_context_and_safe_fingerprint(self):
        from webui.route_helpers import _compact_account_for_list

        projected = _compact_account_for_list({
            "id": 7,
            "email": "account@example.test",
            "email_source": "icloud_hide",
            "registration_proxy_provider": "1024proxy",
            "registration_proxy_region": "US",
            "last_auth_method": "password",
            "last_auth_fallback_used": False,
            "last_auth_fingerprint": {
                "source": "protocol",
                "profile_ref": "abc123def456",
                "browser_family": "chrome",
                "browser_version": "149",
                "browser_os": "macOS",
                "navigator_language": "en-US",
                "timezone_iana": "America/Los_Angeles",
                "screen_width": 1440,
                "screen_height": 900,
                "device_pixel_ratio": 2,
                "hardware_concurrency": 8,
                "device_memory": 8,
                "geo_country": "US",
                "observed_at": "2026-09-22T10:00:00+00:00",
                "user_agent": "must-not-be-returned",
                "proxy_url": "http://user:password@example.test:8080",
            },
            "access_token": "private-token",
            "totp_secret": "private-totp",
        })

        self.assertEqual("1024proxy", projected["registration_proxy_provider"])
        self.assertEqual("US", projected["registration_proxy_region"])
        self.assertEqual("password", projected["last_auth_method"])
        self.assertFalse(projected["last_auth_fallback_used"])
        self.assertEqual("abc123def456", projected["fingerprint_summary"]["profile_ref"])
        self.assertEqual("1440x900", projected["fingerprint_summary"]["screen"])
        self.assertEqual("chrome/149/macOS", projected["fingerprint_summary"]["browser"])
        self.assertEqual("en-US", projected["fingerprint_summary"]["language"])
        self.assertEqual("America/Los_Angeles", projected["fingerprint_summary"]["timezone"])
        self.assertEqual("US", projected["fingerprint_summary"]["geo_country"])
        self.assertNotIn("user_agent", projected["fingerprint_summary"])
        self.assertNotIn("proxy_url", projected["fingerprint_summary"])
        self.assertNotIn("access_token", projected)
        self.assertNotIn("totp_secret", projected)
