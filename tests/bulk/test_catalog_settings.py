"""批次操作参数只派生冻结快照，不修改全局配置。"""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from core.bulk_operations import catalog


class BulkCatalogSettingsTests(TestCase):
    def snapshot(self):
        return {"revision": 42, "values": {
            "REGISTRATION_DRIVER": "roxy", "OPENAI_PROTOCOL_VERSION": "v1",
            "ACCOUNT_PLAN_CHECK_DRIVER": "protocol", "PLAN_CHECK_COUNTRIES": ["JP"],
            "PLAN_CHECK_AUTO_REFRESH_AT_ENABLED": True,
            "ACCOUNT_AT_REFRESH_DRIVER": "browser_roxy", "ACCOUNT_PASSWORD_DRIVER": "roxy",
            "ACCOUNT_2FA_DRIVER": "auto", "ACCOUNT_CODEX_DRIVER": "roxy", "CODEX_OAUTH_DRIVER": "roxy",
            "ACCOUNT_COMPLETION_PASSWORD_ENABLED": True, "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED": True,
            "ACCOUNT_COMPLETION_2FA_ENABLED": True, "ACCOUNT_COMPLETION_CODEX_ENABLED": True,
            "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED": False,
        }}

    def test_plan_settings_are_canonical_and_do_not_change_global_snapshot(self):
        original = self.snapshot()
        before = deepcopy(original)
        with patch("config.schema.non_sensitive_snapshot", return_value=original):
            value = catalog.capture_settings("plan_check", {
                "countries": ["us", "JP", "us"], "auto_refresh_at_enabled": False, "driver": "protocol"})
        self.assertEqual(value["config_revision"], "42")
        self.assertEqual(value["parameters"]["countries"], ["US", "JP"])
        self.assertEqual(value["config_snapshot"]["countries"], ["US", "JP"])
        self.assertFalse(value["config_snapshot"]["auto_refresh_at_enabled"])
        self.assertEqual(original, before)

    def test_invalid_and_unrelated_parameters_are_rejected(self):
        for operation, parameters in [
            ("plan_check", {"countries": ["RAND"]}),
            ("plan_check", {"auto_refresh_at_enabled": "false"}),
            ("plan_check", {"driver": "roxy"}),
            ("password_setup", {"password_driver": "unknown"}),
            ("password_setup", {"REGISTRATION_DRIVER": "protocol_oss_2"}),
            ("twofa_setup", {"twofa_driver": []}),
            ("account_completion", {"password_enabled": 1}),
        ]:
            with self.subTest(operation=operation, parameters=parameters), self.assertRaises(catalog.ParameterError):
                catalog.normalize_parameters(operation, parameters)

    def test_refresh_availability_reads_the_overridden_driver_and_protocol(self):
        with patch("config.schema.non_sensitive_snapshot", return_value=self.snapshot()), \
                patch("core.accounts.liveness.service.deployment_unavailable", return_value=None) as availability, \
                patch("core.proxy.account_routes.proxy_configuration_status", return_value={"ok": True}):
            value = catalog.capture_settings("token_refresh", {"refresh_driver": "protocol", "refresh_protocol_version": "v3"})
        snapshot = value["config_snapshot"]
        self.assertEqual(snapshot["refresh_driver"], "protocol")
        self.assertEqual(snapshot["refresh_protocol_version"], "v3")
        self.assertEqual(availability.call_args.kwargs["driver"], "protocol_v3")
        self.assertEqual(availability.call_args.kwargs["config_snapshot"], snapshot)

    def test_setup_availability_reads_only_this_batch_driver(self):
        with patch("config.schema.non_sensitive_snapshot", return_value=self.snapshot()), \
                patch("core.runtime.capabilities.account_setup_unavailable", return_value=None) as availability:
            value = catalog.capture_settings("password_setup", {"password_driver": "protocol"})
        self.assertEqual(value["config_snapshot"]["password_driver"], "protocol")
        self.assertEqual(availability.call_args.args[0], {"password"})
        self.assertEqual(availability.call_args.args[1]["password_driver"], "protocol")

    def test_codex_override_is_used_by_availability_and_frozen_snapshot(self):
        with patch("config.schema.non_sensitive_snapshot", return_value=self.snapshot()), \
                patch("core.codex.operation_service._deployment_unavailable", return_value=None) as availability, \
                patch("core.codex.operation_service._feature_ready", return_value=(True, "")):
            value = catalog.capture_settings("codex_retry", {"driver": "protocol"})
        self.assertEqual(value["config_revision"], "42")
        self.assertEqual(value["config_snapshot"]["oauth_driver"], "protocol")
        self.assertEqual(availability.call_args.args[0]["oauth_driver"], "protocol")

    def test_completion_children_share_overridden_snapshot_and_revision(self):
        original = self.snapshot()
        before = deepcopy(original)
        with patch("config.schema.non_sensitive_snapshot", return_value=original):
            value = catalog.capture_settings("account_completion", {
                "password_enabled": False, "refresh_at_enabled": True,
                "password_driver": "protocol", "twofa_driver": "protocol", "codex_driver": "protocol"})
        snapshot = value["config_snapshot"]
        self.assertFalse(snapshot["password_enabled"])
        self.assertTrue(snapshot["refresh_at_enabled"])
        self.assertEqual(snapshot["password_driver"], "protocol")
        self.assertEqual(snapshot["twofa_driver"], "protocol")
        self.assertEqual(snapshot["child_execution"]["codex"]["oauth_driver"], "protocol")
        for child in snapshot["child_execution"].values():
            self.assertEqual(child["config_snapshot_revision"], 42)
        self.assertEqual(original, before)

    def test_public_parameter_schema_reuses_options_and_effective_defaults(self):
        schema = catalog._parameter_schema("plan_check", {"countries": ["US"], "auto_refresh_at_enabled": False})
        self.assertEqual(schema["countries"]["type"], "array")
        self.assertEqual(schema["countries"]["default"], ["US"])
        self.assertEqual(schema["driver"]["enum"], ["protocol"])
        self.assertEqual(schema["auto_refresh_at_enabled"]["type"], "boolean")
        self.assertFalse(schema["auto_refresh_at_enabled"]["default"])
        self.assertEqual(catalog._parameter_schema("codex_retry", {"oauth_driver": "protocol"})["driver"]["default"], "protocol")
