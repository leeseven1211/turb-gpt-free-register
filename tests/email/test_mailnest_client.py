# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch

from core.email.mailnest import client as mailnest_client


class MailNestClientTests(unittest.TestCase):
    @patch("core.email.mailnest.client.time.sleep")
    @patch("core.email.mailnest.client.requests.request")
    def test_fetch_latest_otp_reads_code_match(self, request, sleep):
        response = Mock(status_code=200)
        response.json.return_value = {
            "code": "00000",
            "data": [{"code_match": "654321", "subject": "OpenAI code", "from": "noreply@openai.com", "timestamp": 205}],
        }
        request.return_value = response

        with patch.object(mailnest_client._email_cfg, "MAIL_NEST_API_KEY", "key-123", create=True):
            code = mailnest_client.fetch_latest_otp(
                "fresh@mailnest.test",
                after_ts=200,
                max_wait=1,
                poll_interval=1,
                settle_seconds=0,
            )

        self.assertEqual(code, "654321")


if __name__ == "__main__":
    unittest.main()
