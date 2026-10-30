import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from config import env_loader, schema
from config.countries import normalize_plan_check_countries


class PlanCountryConfigTests(unittest.TestCase):
    def test_config_package_reexports_plan_country_settings(self):
        self.assertEqual(["JP", "VN", "IN"], config.PLAN_CHECK_COUNTRIES)
        self.assertEqual(60, config.PLAN_CHECK_COUNTRY_WAIT_TIMEOUT)
        self.assertFalse(config.PLAN_CHECK_PAYMENT_METHODS_ENABLED)
        self.assertIn("PLAN_CHECK_COUNTRIES", config.__all__)
        self.assertIn("PLAN_CHECK_COUNTRY_WAIT_TIMEOUT", config.__all__)
        self.assertIn("PLAN_CHECK_PAYMENT_METHODS_ENABLED", config.__all__)

    def test_normalize_countries_accepts_common_separators_and_preserves_order(self):
        self.assertEqual(
            ["JP", "VN", "IN", "DE"],
            normalize_plan_check_countries("jp, VN\n in  de jp"),
        )

    def test_normalize_empty_countries_keeps_single_country_compatibility(self):
        self.assertEqual([], normalize_plan_check_countries(""))
        self.assertEqual([], normalize_plan_check_countries([]))

    def test_normalize_countries_rejects_unknown_codes_and_rand(self):
        for value in ("ZZ", "J", "JPN", "Rand", "jp Rand"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_plan_check_countries(value)

    def test_schema_exposes_country_list_and_wait_timeout(self):
        countries = schema.CONFIG_SCHEMA["PLAN_CHECK_COUNTRIES"]
        timeout = schema.CONFIG_SCHEMA["PLAN_CHECK_COUNTRY_WAIT_TIMEOUT"]
        payment_methods = schema.CONFIG_SCHEMA["PLAN_CHECK_PAYMENT_METHODS_ENABLED"]
        self.assertEqual(["JP", "VN", "IN"], countries.default)
        self.assertEqual("list_str_multiline", countries.type)
        self.assertEqual("代理与网络", countries.group)
        self.assertEqual(60, timeout.default)
        self.assertEqual({"min": 5, "max": 300}, timeout.range)
        self.assertIs(False, payment_methods.default)
        self.assertEqual("bool", payment_methods.type)
        self.assertEqual("代理与网络", payment_methods.group)
        self.assertIs(True, schema.validate_value("PLAN_CHECK_PAYMENT_METHODS_ENABLED", "true"))
        self.assertIs(False, schema.validate_value("PLAN_CHECK_PAYMENT_METHODS_ENABLED", "false"))
        self.assertEqual(["US", "JP"], schema.validate_value("PLAN_CHECK_COUNTRIES", "us jp"))
        self.assertEqual([], schema.validate_value("PLAN_CHECK_COUNTRIES", ""))
        with self.assertRaises(schema.ConfigValidationError):
            schema.validate_value("PLAN_CHECK_COUNTRY_WAIT_TIMEOUT", 4)

    def test_country_config_reload_updates_module_and_published_snapshot(self):
        fd, raw_path = tempfile.mkstemp(prefix="turb-plan-country-config-")
        os.close(fd)
        path = Path(raw_path)
        self.addCleanup(path.unlink)
        with (
            patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True),
            patch.object(env_loader, "_ENV_PATH", path),
            patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
        ):
            try:
                config.reload_all()
                path.write_text(
                    "PLAN_CHECK_COUNTRIES=us, jp\nPLAN_CHECK_COUNTRY_WAIT_TIMEOUT=120\n"
                    "PLAN_CHECK_PAYMENT_METHODS_ENABLED=true\n",
                    encoding="utf-8",
                )
                with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "0"}):
                    reloaded = config.reload_all()
                self.assertIn("config.proxy", reloaded)
                proxy = importlib.import_module("config.proxy")
                self.assertEqual(["US", "JP"], proxy.PLAN_CHECK_COUNTRIES)
                self.assertEqual(120, proxy.PLAN_CHECK_COUNTRY_WAIT_TIMEOUT)
                self.assertTrue(proxy.PLAN_CHECK_PAYMENT_METHODS_ENABLED)
                self.assertEqual(["US", "JP"], list(schema.non_sensitive_snapshot()["PLAN_CHECK_COUNTRIES"]))
                self.assertIs(True, schema.non_sensitive_snapshot()["PLAN_CHECK_PAYMENT_METHODS_ENABLED"])
                path.write_text("PLAN_CHECK_PAYMENT_METHODS_ENABLED=false\n", encoding="utf-8")
                with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "0"}):
                    config.reload_all()
                self.assertFalse(proxy.PLAN_CHECK_PAYMENT_METHODS_ENABLED)
                self.assertIs(False, schema.non_sensitive_snapshot()["PLAN_CHECK_PAYMENT_METHODS_ENABLED"])
            finally:
                os.environ.pop("PLAN_CHECK_COUNTRIES", None)
                os.environ.pop("PLAN_CHECK_COUNTRY_WAIT_TIMEOUT", None)
                os.environ.pop("PLAN_CHECK_PAYMENT_METHODS_ENABLED", None)
                config.reload_all()


if __name__ == "__main__":
    unittest.main()
