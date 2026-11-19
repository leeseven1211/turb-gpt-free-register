# -*- coding: utf-8 -*-
"""Remail 在现代配置、资源卡片和来源表单中的行为。"""

import json
from pathlib import Path
import subprocess
import unittest

from config.schema import CONFIG_SCHEMA


ROOT = Path(__file__).resolve().parents[2]


class RemailUiTests(unittest.TestCase):
    def test_remail_fields_use_existing_form_controls(self):
        fields = [
            field.metadata() for field in CONFIG_SCHEMA.fields
            if field.key.startswith("REMAIL_") or field.key == "EMAIL_SOURCE"
        ]
        result = subprocess.run(
            ["node", "tests/config/vue_migration_contracts.cjs", "remail_fields", json.dumps(fields)],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_local_inventory_card_has_capacity_and_pool_action(self):
        result = subprocess.run(
            ["node", "tests/email/vue_migration_contracts.cjs", "overview_capacity"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_registration_and_email_change_accept_local_inventory_from_source_api(self):
        result = subprocess.run(
            ["node", "tests/email/remail_source_vue_contracts.cjs"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
