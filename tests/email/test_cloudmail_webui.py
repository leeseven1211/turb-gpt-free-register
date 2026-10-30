"""Retired CloudMail UI routes retain the normal WebUI authentication boundary."""
import unittest
from unittest.mock import patch

from webui.app import create_app


class CloudMailWebUiTests(unittest.TestCase):
    def test_token_route_requires_auth_and_never_writes_configuration(self):
        client = create_app(auth_code="test-auth").test_client()
        self.assertEqual(client.post("/api/cloudmail/gen-token", json={}).status_code, 401)
        with patch("config.env_loader.write_env_values") as write, patch("core.email.cloudmail.client.gen_token") as generate:
            result = client.post("/api/cloudmail/gen-token", headers={"X-Auth-Code": "test-auth"}, json={"password": "draft"})
        self.assertEqual(result.status_code, 410)
        write.assert_not_called()
        generate.assert_not_called()
