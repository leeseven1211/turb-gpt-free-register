# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch

from core import email_butler_client


class EmailButlerClientTests(unittest.TestCase):
    def setUp(self):
        email_butler_client._CONTEXT_CACHE.clear()

    @patch("core.email_butler_client.requests.request")
    def test_connection_checks_policy_and_capabilities(self, request):
        response = Mock(status_code=200)
        response.json.return_value = {
            "code": 200,
            "name": "turb-gpt-register",
            "policy": {"consumer": "turb-gpt-register", "service": "openai"},
            "capabilities": [
                "mailboxes.create", "mailboxes.messages", "mailboxes.release",
            ],
        }
        request.return_value = response

        result = email_butler_client.test_connection(
            api_base="http://127.0.0.1:8788/v1",
            api_key="key-123",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["consumer"], "turb-gpt-register")
        self.assertEqual(result["service"], "openai")

    @patch("core.email_butler_client.requests.request")
    def test_pick_fetch_and_release_mailbox(self, request):
        lease = Mock(status_code=200)
        lease.json.return_value = {
            "code": 200,
            "mailbox": {
                "id": "lease-1:fresh@example.com",
                "email": "fresh@example.com",
                "lease_id": "lease-1",
                "provider": "outlook_graph",
            },
        }
        messages = Mock(status_code=200)
        messages.json.return_value = {
            "code": 200,
            "verification_code": "654321",
            "messages": [],
        }
        release = Mock(status_code=200)
        release.json.return_value = {"code": 200}
        request.side_effect = [lease, messages, release]

        with patch.object(email_butler_client._email_cfg, "EMAIL_BUTLER_API_BASE", "http://127.0.0.1:8788/v1", create=True), patch.object(
            email_butler_client._email_cfg, "EMAIL_BUTLER_API_KEY", "key-123", create=True
        ):
            account = email_butler_client.pick_account()
            code = email_butler_client.fetch_latest_otp(
                account.email,
                after_ts=200,
                max_wait=1,
                poll_interval=1,
                settle_seconds=0,
            )
            email_butler_client.release_account(account.email, status="succeeded", note="ok")

        self.assertEqual(code, "654321")
        self.assertIsNone(email_butler_client.get_account_context(account.email))
        release_body = request.call_args_list[2].kwargs["json"]
        self.assertEqual(release_body["outcome"], "succeeded")


if __name__ == "__main__":
    unittest.main()
