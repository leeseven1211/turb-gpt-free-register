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
        self.assertIn('CLOUDMAIL_ADMIN_EMAIL = env_str("CLOUDMAIL_ADMIN_EMAIL", "")', source)
        self.assertIn('CLOUDMAIL_PASSWORD = env_str("CLOUDMAIL_PASSWORD", "")', source)
        self.assertIn('CLOUDMAIL_DOMAINS = []', source)
        self.assertIn('"cloudmail"', source)

    def test_secret_registry_includes_cloudmail_token(self):
        self.assertEqual(SECRET_ENV_KEYS["CLOUDMAIL_AUTH_TOKEN"], "CloudMail Authorization Token")
        self.assertEqual(SECRET_ENV_KEYS["CLOUDMAIL_PASSWORD"], "CloudMail 登录密码")

    def test_webui_exposes_only_cloudmail_receive_settings(self):
        keys = {item["key"]: item for item in EDITABLE_FIELDS}
        self.assertEqual(keys["CLOUDMAIL_AUTH_TOKEN"]["storage"], "env")
        self.assertTrue(keys["CLOUDMAIL_AUTH_TOKEN"]["secret"])
        for key in ("CLOUDMAIL_ADMIN_EMAIL", "CLOUDMAIL_PASSWORD", "CLOUDMAIL_DOMAINS", "CLOUDMAIL_AUTO_ADD_USER", "CLOUDMAIL_RANDOM_LOCAL_LENGTH", "CLOUDMAIL_TOKEN_PATH"):
            self.assertNotIn(key, keys)


if __name__ == "__main__":
    unittest.main()
