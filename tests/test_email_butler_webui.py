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

    @patch("core.email_butler_client.fetch_pool_snapshot")
    def test_pool_endpoint_filters_and_paginates_safe_rows(self, fetch_pool_snapshot):
        fetch_pool_snapshot.return_value = {
            "ok": True,
            "name": "turb-gpt-register",
            "policy": {"consumer": "turb-gpt-register", "service": "openai"},
            "summary": {"total": 2, "available": 1, "registered": 1},
            "accounts": [
                {"email": "fresh@example.com", "effective_status": "available", "service_tags": []},
                {"email": "used@example.com", "effective_status": "registered", "service_tags": ["openai"]},
            ],
        }
        response = self.client.get("/api/email-butler/pool?status=registered&page=1&page_size=20")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "used@example.com")


if __name__ == "__main__":
    unittest.main()
