"""幻光扫码配置与运行模式的隔离契约。"""

import unittest
from unittest.mock import patch

from core import extract_link_service as service


class HuanguangPaymentConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.switches = (
            "EXTRACT_LINK_ENABLED", "EXTRACT_LINK_EXTRACT_ENABLED", "EXTRACT_LINK_AUTO_PAYMENT_ENABLED",
            "EXTRACT_LINK_HUANGUANG_ENABLED", "EXTRACT_LINK_HUANGUANG_EXTRACT_ENABLED",
            "EXTRACT_LINK_HUANGUANG_AUTO_PAYMENT_ENABLED",
        )
        self.values = {key: True for key in self.switches}
        self.values.update({
            "EXTRACT_LINK_LEGACY_ENABLED": False,
            "EXTRACT_LINK_HUANGUANG_API_BASE": "https://huanguang.example.test",
            "EXTRACT_LINK_HUANGUANG_CDK": "fixture-extract-cdk",
            "EXTRACT_LINK_HUANGUANG_PAYMENT_CDK": "fixture-payment-cdk",
        })
        setting = patch.object(service, "_runtime_setting", side_effect=lambda name, default=None: self.values.get(name, default))
        setting.start()
        self.addCleanup(setting.stop)

    def test_auto_payment_uses_separate_runtime_secret_and_requires_all_switches(self):
        self.assertTrue(service._provider_mode_enabled("huanguang", "auto_payment"))
        runtime = service._provider_configuration("huanguang")
        self.assertEqual("fixture-extract-cdk", runtime.config.cdk)
        self.assertEqual("fixture-payment-cdk", runtime.config.payment_cdk)
        self.assertTrue(runtime.capabilities["auto_payment"])
        self.assertNotIn("fixture-payment-cdk", repr(runtime.config))
        for key in self.switches:
            with self.subTest(disabled=key):
                self.values[key] = False
                self.assertFalse(service._provider_mode_enabled("huanguang", "auto_payment"))
                self.values[key] = True

    def test_missing_payment_key_keeps_extract_only_available_and_hides_auto_mode(self):
        self.values["EXTRACT_LINK_HUANGUANG_PAYMENT_CDK"] = ""
        self.assertTrue(service._provider_mode_enabled("huanguang", "extract_only"))
        self.assertFalse(service._provider_mode_enabled("huanguang", "auto_payment"))
        without_key = service.workbench_config()
        provider = next(item for item in without_key["providers"] if item["id"] == "huanguang")
        self.assertNotIn("auto_payment", provider["modes"])
        self.values["EXTRACT_LINK_HUANGUANG_PAYMENT_CDK"] = "fixture-payment-cdk"
        with_key = service.workbench_config()
        provider = next(item for item in with_key["providers"] if item["id"] == "huanguang")
        self.assertIn("auto_payment", provider["modes"])
        self.assertNotIn("fixture-payment-cdk", repr(with_key))

    def test_request_options_cannot_override_auto_payment_or_supply_payment_secret(self):
        options = service._provider_request_options("huanguang", {
            "chongyun_auto_submit": True, "chongyun_cdk": "untrusted-payment-key",
        }, mode="extract_only", link_type="upi")
        self.assertEqual({}, options)

    def test_request_options_allow_only_bounded_per_task_retry_count(self):
        for count in (1, 3, 10):
            with self.subTest(count=count):
                self.assertEqual({"retry_count": count}, service._provider_request_options("huanguang", {
                    "retry_count": count, "chongyun_auto_submit": True, "chongyun_cdk": "untrusted-secret",
                }, mode="extract_only", link_type="upi"))
        for count in (True, 0, -1, 11, 3.0, "3", None):
            with self.subTest(count=count), self.assertRaises(ValueError):
                service._provider_request_options("huanguang", {"retry_count": count}, mode="extract_only", link_type="upi")
