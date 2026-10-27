"""Retired CloudMail management routes do not access the service or save drafts."""
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
from webui.routes.config import create_config_blueprint


class ConfigCloudMailRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(create_config_blueprint(SimpleNamespace(logger=logging.getLogger(__name__))))
        self.client = app.test_client()

    def test_management_routes_are_gone_without_saving_drafts(self):
        for path in ("gen-token", "domains"):
            with self.subTest(path=path), patch("webui.config_editor.update_config") as update, patch(
                "core.cloudmail_client.gen_token") as generate, patch("core.cloudmail_client.fetch_domains") as domains:
                response = self.client.post("/api/cloudmail/" + path, json={"password": "private-draft"})
                self.assertEqual(response.status_code, 410)
                self.assertEqual(response.get_json()["reason_code"], "email_management_managed_by_service")
                self.assertNotIn("private-draft", response.get_data(as_text=True))
                update.assert_not_called()
                generate.assert_not_called()
                domains.assert_not_called()
