"""暗光一条龙配置、密钥存储与工作台公开契约。"""

import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from flask import Flask

import config
from config import env_loader, runtime, schema
from core.storage import postgres, runtime_config as store
from tests.support_pg import PostgresTestCase
from webui import config_editor
from webui.routes import extract_workbench
from webui.runtime import WebUIContext


PREFIX = "EXTRACT_LINK_ANGUANG_"


class AnguangSchemaTests(unittest.TestCase):
    def test_defaults_are_independent_and_auto_payment_starts_disabled(self):
        defaults = {
            "ENABLED": False, "AUTO_PAYMENT_ENABLED": False,
            "API_BASE": "https://ytc.xxsyun.xyz/openapi/v1", "API_KEY": "",
            "CONCURRENCY": 1, "REQUEST_TIMEOUT": 30,
            "POLL_INTERVAL": 10, "PROCESSING_MODE": "STANDARD",
            "PLAN_NAME": "chatgptplusplan", "AUTO_RETRY": False,
        }
        from config import extract_link

        self.assertEqual("anguang", schema.validate_value("EXTRACT_LINK_DEFAULT_PROVIDER", "anguang"))
        for suffix, default in defaults.items():
            key = PREFIX + suffix
            with self.subTest(key=key):
                self.assertEqual(default, schema.schema_default(key))
                self.assertTrue(hasattr(extract_link, key))
                self.assertEqual("提链", schema.CONFIG_SCHEMA[key].group)
                self.assertEqual("safe", schema.CONFIG_SCHEMA[key].hot_edit)
        fields = {field.key for field in schema.CONFIG_SCHEMA.fields}
        self.assertNotIn(PREFIX + "EXTRACT_ENABLED", fields)
        self.assertNotIn(PREFIX + "MANUAL_PAYMENT_ENABLED", fields)
        self.assertNotIn(PREFIX + "AUTO_PAYMENT_SOURCE", fields)

    def test_bounded_numbers_and_documented_modes_are_validated(self):
        for suffix, lower, upper in (
            ("CONCURRENCY", 1, 50), ("REQUEST_TIMEOUT", 5, 300),
            ("POLL_INTERVAL", 10, 300),
        ):
            for value in (lower, upper):
                with self.subTest(suffix=suffix, value=value):
                    self.assertEqual(value, schema.validate_value(PREFIX + suffix, value))
            for value in (lower - 1, upper + 1):
                with self.subTest(suffix=suffix, invalid=value), self.assertRaises(schema.ConfigValidationError):
                    schema.validate_value(PREFIX + suffix, value)
        for suffix, allowed in (("PROCESSING_MODE", ("STANDARD", "STRICT")),
                                ("PLAN_NAME", ("chatgptplusplan",))):
            for value in allowed:
                self.assertEqual(value, schema.validate_value(PREFIX + suffix, value))
            with self.assertRaises(schema.ConfigValidationError):
                schema.validate_value(PREFIX + suffix, "untrusted-value")

    def test_only_plus_plan_can_be_saved_while_other_plans_lack_local_confirmation(self):
        self.assertEqual(["chatgptplusplan"], [option.value for option in schema.CONFIG_SCHEMA[PREFIX + "PLAN_NAME"].options])
        for plan in ("chatgptgoplan", "chatgptprolite"):
            with self.subTest(plan=plan), self.assertRaises(schema.ConfigValidationError):
                schema.validate_config_updates({PREFIX + "PLAN_NAME": plan})

    def test_unused_monitor_budget_is_not_exposed_or_accepted_for_saving(self):
        key = PREFIX + "EVENT_TIMEOUT"
        self.assertNotIn(key, {field["key"] for field in config_editor.get_config()})
        with self.assertRaises(schema.ConfigValidationError):
            schema.validate_config_updates({key: 180})
        from config import extract_link

        self.assertFalse(hasattr(extract_link, key))


class AnguangConfigurationStorageTests(PostgresTestCase):
    def setUp(self):
        self.original_state = config.capture_reload_state()
        self.addCleanup(config.restore_reload_state, self.original_state)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env_path = Path(self.directory.name) / ".env"
        self.env_path.write_text("# isolated bootstrap fixture\n", encoding="utf-8")
        for context in (
            patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                                    "PYTHON_DOTENV_DISABLED": "1"}),
            patch.object(env_loader, "_ENV_PATH", self.env_path),
            patch.object(runtime, "_automatic_database_allowed", return_value=True),
            patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
        ):
            context.start()
            self.addCleanup(context.stop)
        runtime.reset_cache()
        self.addCleanup(runtime.reset_cache)
        store.write_values({"EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY": "fixture-normal-scan-key"}, activate=True)
        runtime.load_values(force=True)
        config.reload_all()

    def test_ordinary_scan_key_is_never_copied_to_anguang(self):
        fields = {field["key"]: field for field in config_editor.get_config()}
        item = fields[PREFIX + "API_KEY"]
        self.assertFalse(item["configured"])
        self.assertEqual("", item["value"])
        self.assertFalse(fields[PREFIX + "ENABLED"]["value"])
        self.assertFalse(fields[PREFIX + "AUTO_PAYMENT_ENABLED"]["value"])
        self.assertNotIn(PREFIX + "API_KEY", store.read_values())

    def test_save_encrypts_key_masks_metadata_and_leaves_bootstrap_and_other_keys_unchanged(self):
        before_file = self.env_path.read_bytes()
        updates = {PREFIX + "API_KEY": "fixture-yitiaochong-secret", PREFIX + "PROCESSING_MODE": "STRICT",
                   PREFIX + "PLAN_NAME": "chatgptplusplan", PREFIX + "POLL_INTERVAL": 15,
                   "EXTRACT_LINK_DEFAULT_PROVIDER": "anguang"}
        result = config_editor.update_config(updates)
        self.assertEqual(sorted(updates), sorted(result["database_updated"]))
        self.assertEqual([], result["env_updated"])
        self.assertEqual(before_file, self.env_path.read_bytes())
        saved = store.read_values()
        self.assertEqual("fixture-yitiaochong-secret", saved[PREFIX + "API_KEY"])
        self.assertEqual("fixture-normal-scan-key", saved["EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY"])
        fields = {field["key"]: field for field in config_editor.get_config()}
        item = fields[PREFIX + "API_KEY"]
        self.assertTrue(item["configured"])
        self.assertTrue(item["secret"])
        self.assertEqual("database", item["storage"])
        self.assertEqual("database", item["source"])
        self.assertEqual("", item["value"])
        self.assertNotIn("fixture-yitiaochong-secret", repr(fields))
        self.assertNotIn(PREFIX + "API_KEY", schema.non_sensitive_snapshot())
        self.assertEqual("STRICT", schema.non_sensitive_snapshot()[PREFIX + "PROCESSING_MODE"])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT row_to_json(t)::text FROM {postgres.qualified('runtime_config_values')} t")
            self.assertNotIn("fixture-yitiaochong-secret", " ".join(row[0] for row in cur.fetchall()))


class AnguangWorkbenchRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask("anguang-workbench")
        app.register_blueprint(extract_workbench.create_extract_workbench_blueprint(
            WebUIContext(app, logging.getLogger("anguang-workbench"))))
        self.client = app.test_client()

    def test_public_config_keeps_only_native_payment_source_and_removes_secrets(self):
        value = {"default_provider": "anguang", "providers": [{
            "id": "anguang", "label": "暗光（XXSYUN 一条龙）", "default_type": "upi",
            "link_types": ["upi"], "modes": ["auto_payment"], "payment_source": "native",
            "payment_sources": ["native"], "api_key": "fixture-private-key",
        }]}
        with patch.object(extract_workbench.extract_link_service, "workbench_config", return_value=value):
            response = self.client.get("/api/extract-workbench/config")
        self.assertEqual(200, response.status_code)
        provider = response.json["providers"][0]
        self.assertEqual(["native"], provider["payment_sources"])
        self.assertEqual("native", provider["payment_source"])
        self.assertEqual(["auto_payment"], provider["modes"])
        self.assertNotIn("fixture-private-key", response.get_data(as_text=True))

    def test_candidate_filter_accepts_anguang_and_rejects_unknown_provider(self):
        valid = extract_workbench._candidate_filters({"never_provider": "anguang"})
        self.assertIsNotNone(valid)
        self.assertEqual("anguang", valid["never_provider"])
        self.assertIsNone(extract_workbench._candidate_filters({"never_provider": "untrusted-provider"}))
