# -*- coding: utf-8 -*-
import unittest
from pathlib import Path

from config import email
from config.env_loader import SECRET_ENV_KEYS
from webui.config_editor import EDITABLE_FIELDS


class EmailButlerConfigTests(unittest.TestCase):
    def test_email_config_declares_butler_defaults(self):
        source = Path(email.__file__).read_text(encoding="utf-8")
        self.assertIn('EMAIL_BUTLER_API_BASE = env_str("EMAIL_BUTLER_API_BASE", "")', source)
        self.assertIn('EMAIL_BUTLER_API_KEY = env_str("EMAIL_BUTLER_API_KEY", "")', source)

    def test_secret_registry_includes_butler_key(self):
        self.assertEqual(SECRET_ENV_KEYS["EMAIL_BUTLER_API_KEY"], "Email Butler API Key")

    def test_webui_exposes_butler_fields(self):
        fields = {item["key"]: item for item in EDITABLE_FIELDS}
        self.assertTrue(fields["EMAIL_BUTLER_API_KEY"]["secret"])
        self.assertEqual(fields["EMAIL_BUTLER_API_BASE"]["group"], "邮箱 / OTP")


if __name__ == "__main__":
    unittest.main()
