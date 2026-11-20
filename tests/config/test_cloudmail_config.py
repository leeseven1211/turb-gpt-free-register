# -*- coding: utf-8 -*-
import unittest
from pathlib import Path

from config import email
from config.env_loader import SECRET_ENV_KEYS
from webui.config_editor import EDITABLE_FIELDS


class CloudMailConfigTests(unittest.TestCase):
    def test_email_config_declares_cloudmail_defaults(self):
        source = Path(email.__file__).read_text(encoding="utf-8")
        self.assertIn('CLOUDMAIL_AUTH_TOKEN = env_str("CLOUDMAIL_AUTH_TOKEN", "")', source)
        self.assertIn('"cloudmail"', source)

    def test_secret_registry_includes_cloudmail_token(self):
        self.assertEqual(SECRET_ENV_KEYS["CLOUDMAIL_AUTH_TOKEN"], "CloudMail Authorization Token")

    def test_cloudmail_receive_settings_remain_writable(self):
        keys = {item["key"]: item for item in EDITABLE_FIELDS}
        self.assertEqual(keys["CLOUDMAIL_AUTH_TOKEN"]["storage"], "database")
        self.assertTrue(keys["CLOUDMAIL_AUTH_TOKEN"]["secret"])


if __name__ == "__main__":
    unittest.main()
