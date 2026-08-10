# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch

from core import email_butler_client as client


class EmailButlerClientTests(unittest.TestCase):
    def test_scan_maps_only_safe_signal_fields(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": 200,
            "checked_at": "2026-08-10T00:00:00Z",
            "signal": {
                "detected": True,
                "received_at": "2026-08-09T00:00:00Z",
                "subject": "OpenAI Account Deactivated",
                "from": "noreply@openai.com",
                "message_id": "m-1",
                "confidence": "high",
                "body": "must not be returned",
            },
        }
        with patch.object(client.requests, "request", return_value=response), patch.object(
            client._email_cfg, "EMAIL_BUTLER_API_BASE", "http://127.0.0.1:8788/v1"
        ), patch.object(client._email_cfg, "EMAIL_BUTLER_API_KEY", "secret"):
            result = client.scan_openai_deactivation("a@example.com")
        self.assertTrue(result["detected"])
        self.assertNotIn("body", result)
        self.assertEqual(result["confidence"], "high")

    def test_connection_requires_signal_capability(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": 200,
            "capabilities": ["mailboxes.create", "mailboxes.messages", "mailboxes.release"],
        }
        with patch.object(client.requests, "request", return_value=response):
            with self.assertRaises(client.EmailButlerClientError):
                client.test_connection(api_base="http://example.test/v1", api_key="secret")

    def test_restore_context_requests_exact_email(self):
        with patch.object(client, "_request", return_value={
            "mailbox": {
                "id": "mb-1",
                "email": "restore@example.com",
                "lease_id": "lease-1",
            }
        }) as request_mock:
            account = client.restore_account_context("restore@example.com")
        self.assertEqual(account.mailbox_id, "mb-1")
        request_mock.assert_called_once_with(
            "POST",
            "/mailboxes",
            json={"requested_email": "restore@example.com", "purpose": "live-check"},
        )


if __name__ == "__main__":
    unittest.main()
