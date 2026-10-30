"""幻光提链与扫码 CDK 的只读额度查询契约。"""

import unittest
from types import SimpleNamespace

from core.extract_link.contracts import ProviderConfig, ProviderError
from core.extract_link.huanguang.client import HuanguangProvider


class HuanguangCdkQuotaTests(unittest.TestCase):
    def _provider(self, payload, *, status=200, error=None):
        transport = _Transport(payload, status=status, error=error)
        config = ProviderConfig("huanguang", "https://provider.example.test", "saved-extract-secret", timeout=17)
        return HuanguangProvider(config, transport), transport

    def test_extract_query_posts_only_supplied_cdk_and_preserves_available_and_reserved(self):
        provider, transport = self._provider({
            "ok": True, "enabled": True, "remaining_uses": 2, "reserved_uses": 5,
            "total_uses": 10, "spent_uses": 3, "cdk": "untrusted-secret",
        })
        result = provider.query_cdk_quota("  draft-extract-secret  ")
        self.assertEqual({"required": True, "remaining": 2, "reserved": 5, "active": True}, result)
        self.assertEqual([("POST", "/api/cdk-status", {
            "json": {"cdk": "draft-extract-secret"},
            "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"}, "timeout": 10,
        })], transport.calls)
        self.assertEqual("saved-extract-secret", provider.config.cdk)

    def test_extract_query_distinguishes_zero_and_disabled(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                provider, _ = self._provider({"ok": True, "enabled": enabled, "remaining_uses": 0, "reserved_uses": 0})
                self.assertEqual({"required": True, "remaining": 0, "reserved": 0, "active": enabled},
                                 provider.query_cdk_quota("synthetic-cdk"))

    def test_counting_disabled_is_exempt_instead_of_zero_quota(self):
        provider, _ = self._provider({"ok": True, "required": False})
        self.assertEqual({"required": False, "remaining": None, "reserved": None, "active": True},
                         provider.query_cdk_quota("synthetic-cdk"))

    def test_extract_missing_optional_flags_remain_unknown(self):
        provider, _ = self._provider({"ok": True, "remaining_uses": 3})
        self.assertEqual({"required": True, "remaining": 3, "reserved": None, "active": None},
                         provider.query_cdk_quota("synthetic-cdk"))

    def test_payment_query_uses_separate_endpoint_and_active_state(self):
        for status, active in (("ACTIVE", True), ("DISABLED", False), ("UNKNOWN", None)):
            with self.subTest(status=status):
                provider, transport = self._provider({"remainingUses": 0, "totalUses": 50, "status": status})
                result = provider.query_cdk_quota("draft-payment-secret", payment=True)
                self.assertEqual({"required": True, "remaining": 0, "reserved": None, "active": active}, result)
                self.assertEqual("/api/chongyun-cdk-status", transport.calls[0][1])
                self.assertEqual({"cdk": "draft-payment-secret"}, transport.calls[0][2]["json"])

    def test_unrecognized_payment_status_remains_unknown_without_returning_raw_value(self):
        for status in (None, "unexpected-secret", True):
            with self.subTest(status=status):
                provider, _ = self._provider({"remainingUses": 4, "status": status})
                self.assertEqual({"required": True, "remaining": 4, "reserved": None, "active": None},
                                 provider.query_cdk_quota("synthetic-cdk", payment=True))

    def test_payment_does_not_accept_extract_counting_exemption(self):
        provider, _ = self._provider({"ok": True, "required": False})
        with self.assertRaises(ProviderError):
            provider.query_cdk_quota("synthetic-cdk", payment=True)

    def test_invalid_counts_never_become_zero_or_truthy_booleans(self):
        for payment, name in ((False, "remaining_uses"), (True, "remainingUses")):
            for value in (None, True, False, -1, "0", 1.5, 2**53):
                with self.subTest(payment=payment, value=value):
                    provider, _ = self._provider({"ok": True, name: value})
                    with self.assertRaises(ProviderError):
                        provider.query_cdk_quota("synthetic-cdk", payment=payment)

    def test_invalid_extract_reserved_or_flags_are_rejected(self):
        for fields in ({"reserved_uses": True}, {"reserved_uses": -1}, {"reserved_uses": "2"},
                       {"enabled": "true"}, {"required": 0}):
            with self.subTest(fields=fields):
                provider, _ = self._provider({"ok": True, "remaining_uses": 4, **fields})
                with self.assertRaises(ProviderError):
                    provider.query_cdk_quota("synthetic-cdk")

    def test_empty_or_invalid_cdk_never_contacts_platform(self):
        for cdk in (None, "", "   ", True, 123, "x" * 513):
            with self.subTest(cdk=cdk):
                provider, transport = self._provider({})
                with self.assertRaises(ProviderError):
                    provider.query_cdk_quota(cdk)
                self.assertEqual([], transport.calls)

    def test_failed_response_never_exposes_cdk_or_raw_upstream_message(self):
        for payload, status, error in (
            ({"error": "draft-secret private upstream"}, 502, None),
            ({"ok": False, "remaining_uses": 4, "error": "draft-secret"}, 200, None),
            (["draft-secret"], 200, None),
            ({}, 200, RuntimeError("draft-secret private upstream")),
        ):
            for payment in (False, True):
                with self.subTest(status=status, payment=payment, error=bool(error)):
                    provider, _ = self._provider(payload, status=status, error=error)
                    with self.assertRaises(ProviderError) as caught:
                        provider.query_cdk_quota("draft-secret", payment=payment)
                    self.assertIn("CDK", str(caught.exception))
                    self.assertNotIn("draft-secret", str(caught.exception))
                    self.assertNotIn("private upstream", str(caught.exception))


class _Transport:
    def __init__(self, payload, *, status=200, error=None):
        self.payload, self.status, self.error = payload, status, error
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(status_code=self.status, json=lambda: self.payload)
