"""虾扯蛋链 UPI 自动支付的开关、独立扫码凭据与类型契约。"""
import unittest
from unittest.mock import patch

from core import extract_link_service as service


class LegacyPaymentConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.switches = (
            "EXTRACT_LINK_ENABLED", "EXTRACT_LINK_EXTRACT_ENABLED", "EXTRACT_LINK_AUTO_PAYMENT_ENABLED",
            "EXTRACT_LINK_LEGACY_ENABLED", "EXTRACT_LINK_LEGACY_EXTRACT_ENABLED",
            "EXTRACT_LINK_LEGACY_AUTO_PAYMENT_ENABLED",
        )
        self.values = {key: True for key in self.switches}
        self.values.update({
            "EXTRACT_LINK_LUMEN_FLOW_ENABLED": False, "EXTRACT_LINK_HUANGUANG_ENABLED": False,
            "EXTRACT_LINK_API_BASE": "https://extract.example.test",
            "EXTRACT_LINK_CDK": "synthetic-extract-cdk", "EXTRACT_LINK_TYPE": "upi",
            "EXTRACT_LINK_LEGACY_PAYMENT_CDK": "synthetic-payment-cdk",
        })
        setting = patch.object(service, "_runtime_setting", side_effect=lambda name, default=None: self.values.get(name, default))
        setting.start()
        self.addCleanup(setting.stop)

    def test_auto_payment_requires_each_switch_and_independent_payment_cdk(self):
        self.assertTrue(service._provider_mode_enabled("legacy", "auto_payment"))
        runtime = service._provider_configuration("legacy")
        self.assertEqual("synthetic-extract-cdk", runtime.config.cdk)
        self.assertEqual("synthetic-payment-cdk", runtime.config.payment_cdk)
        self.assertTrue(runtime.capabilities["auto_payment"])
        self.assertNotIn("synthetic-payment-cdk", repr(runtime.config))
        for key in self.switches:
            with self.subTest(disabled=key):
                self.values[key] = False
                self.assertFalse(service._provider_mode_enabled("legacy", "auto_payment"))
                self.values[key] = True

    def test_missing_payment_cdk_keeps_extraction_available_and_hides_auto_mode(self):
        self.values["EXTRACT_LINK_LEGACY_PAYMENT_CDK"] = ""
        self.assertTrue(service._provider_mode_enabled("legacy", "extract_only"))
        self.assertFalse(service._provider_mode_enabled("legacy", "auto_payment"))
        provider = service.workbench_config()["providers"][0]
        self.assertNotIn("auto_payment", provider["modes"])
        self.values["EXTRACT_LINK_LEGACY_PAYMENT_CDK"] = "synthetic-payment-cdk"
        provider = service.workbench_config()["providers"][0]
        self.assertIn("auto_payment", provider["modes"])

    def test_upi_is_the_only_automatic_payment_type_and_request_cannot_inject_keys(self):
        self.assertEqual({}, service._provider_request_options("legacy", {
            "payment_platform": {"enabled": True, "cdk": "untrusted-cdk"},
        }, mode="auto_payment", link_type="upi"))
        for link_type in ("pix", "gopay", "paypal"):
            with self.subTest(link_type=link_type), self.assertRaisesRegex(ValueError, "UPI"):
                service._provider_request_options("legacy", {}, mode="auto_payment", link_type=link_type)
        self.assertEqual({}, service._provider_request_options("legacy", {
            "payment_platform": {"enabled": True},
        }, mode="extract_only", link_type="upi"))

    def test_workbench_only_advertises_upi_automatic_payment_and_keeps_secrets_out(self):
        config = service.workbench_config()
        self.assertIn("auto_payment", config["providers"][0]["modes"])
        self.assertNotIn("synthetic-payment-cdk", repr(config))
        self.values["EXTRACT_LINK_TYPE"] = "pix"
        self.assertNotIn("auto_payment", service.workbench_config()["providers"][0]["modes"])
