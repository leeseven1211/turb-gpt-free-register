# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from webui.app import create_app


class EmailButlerWebUiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"

    @patch("core.email_butler_client.test_connection")
    def test_connection_endpoint_uses_current_form_values(self, test_connection):
        test_connection.return_value = {
            "ok": True,
            "name": "turb-gpt-register",
            "consumer": "turb-gpt-register",
            "service": "openai",
            "capabilities": ["mailboxes.create", "mailboxes.messages", "mailboxes.release"],
        }
        response = self.client.post("/api/email-butler/test-connection", json={
            "api_base": "http://127.0.0.1:8788/v1",
            "api_key": "key-123",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        test_connection.assert_called_once_with(
            api_base="http://127.0.0.1:8788/v1",
            api_key="key-123",
        )


if __name__ == "__main__":
    unittest.main()
