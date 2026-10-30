# -*- coding: utf-8 -*-
"""账号列表安全投影回归。"""
from __future__ import annotations

import json
import unittest


class AccountListProjectionTests(unittest.TestCase):
    def test_compact_account_reads_last_success_country_without_exposing_result_json(self):
        from webui.route_helpers import _compact_account_for_list

        projected = _compact_account_for_list({
            "id": 8,
            "email": "account@example.test",
            "updated_at": "2026-10-16T10:00:00+00:00",
            "current_plan_type": "free",
            "plan_check_status": "failed",
            "plan_check_ok": False,
            "account_promotions": [{"plan": "plus", "kind": "free_trial"}],
            "plan_last_success_result_json": json.dumps({"ok": True, "proxy_region": "jp"}),
            "plan_check_result_json": json.dumps({"ok": False, "proxy_region": "us"}),
            "access_token": "private-token",
        })

        self.assertEqual("JP", projected["plan_promotion_country"])
        self.assertEqual("2026-10-16T10:00:00+00:00", projected["updated_at"])
        self.assertNotIn("plan_last_success_result_json", projected)
        self.assertNotIn("plan_check_result_json", projected)

    def test_compact_account_uses_current_country_only_on_explicit_success(self):
        from webui.route_helpers import _compact_account_for_list

        projected = _compact_account_for_list({
            "id": 9,
            "email": "account@example.test",
            "plan_check_status": "success",
            "plan_check_ok": True,
            "account_promotions": [{"plan": "plus", "kind": "none"}],
            "plan_check_result_json": json.dumps({"ok": True, "proxy_region": "vn"}),
        })

        self.assertEqual("VN", projected["plan_promotion_country"])

    def test_compact_account_does_not_override_existing_multi_country_evidence(self):
        from webui.route_helpers import _compact_account_for_list

        projected = _compact_account_for_list({
            "id": 10,
            "email": "account@example.test",
            "plan_check_country_results": [{
                "country": "jp", "status": "success", "result": {"proxy_region": "JP"},
            }],
            "account_promotions": [{"plan": "plus", "kind": "free_trial", "country": "JP"}],
            "plan_last_success_result_json": json.dumps({"ok": True, "proxy_region": "us"}),
        })

        self.assertNotIn("plan_promotion_country", projected)

    def test_compact_account_uses_latest_single_result_after_multi_country_is_disabled(self):
        from webui.route_helpers import _compact_account_for_list

        row = {
            "id": 11,
            "email": "account@example.test",
            "plan_check_countries": [],
            "plan_check_country_results": [{
                "country": "JP", "status": "success", "result": {"proxy_region": "JP"},
            }],
            "account_promotions": [{"plan": "plus", "kind": "free_trial", "country": "JP"}],
            "plan_last_success_result_json": json.dumps({"ok": True, "proxy_region": "vn"}),
        }
        before = json.loads(json.dumps(row))

        projected = _compact_account_for_list(row)

        self.assertEqual("VN", projected["plan_promotion_country"])
        self.assertEqual(before, row)

    def test_compact_account_does_not_use_first_country_of_multi_country_success_snapshot(self):
        from webui.route_helpers import _compact_account_for_list

        aggregate = {
            "ok": True,
            "proxy_region": "JP",
            "plan_check_countries": ["JP", "US"],
            "plan_check_country_results": [
                {"country": "JP", "status": "success", "result": {"proxy_region": "JP"}},
                {"country": "US", "status": "success", "result": {"proxy_region": "US"}},
            ],
            "account_promotions": [
                {"plan": "plus", "kind": "none", "country": "JP"},
                {"plan": "plus", "kind": "free_trial", "country": "US"},
            ],
        }
        projected = _compact_account_for_list({
            "id": 12,
            "email": "account@example.test",
            "plan_check_countries": [],
            "plan_check_country_results": aggregate["plan_check_country_results"],
            "account_promotions": aggregate["account_promotions"],
            "plan_last_success_result_json": json.dumps(aggregate),
        })

        self.assertNotIn("plan_promotion_country", projected)

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
