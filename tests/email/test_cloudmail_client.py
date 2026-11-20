# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch

from core.email.cloudmail import client as cloudmail_client


class CloudMailClientTests(unittest.TestCase):
    @patch("core.email.cloudmail.client.time.sleep")
    @patch("core.email.cloudmail.client.requests.post")
    def test_fetch_latest_otp_reads_openai_mail(self, post, sleep):
        response = Mock(status_code=200)
        response.json.return_value = {
            "code": 200,
            "data": [{
                "emailId": "1",
                "sendEmail": "noreply@openai.com",
                "subject": "Your code is 654321",
                "content": "Your verification code is 654321",
                "createTime": "2026-07-15 04:00:10",
            }],
        }
        post.return_value = response

        with patch.object(cloudmail_client._email_cfg, "CLOUDMAIL_API_BASE", "https://mail.example.com", create=True), patch.object(
            cloudmail_client._email_cfg, "CLOUDMAIL_AUTH_TOKEN", "token-123", create=True
        ):
            code = cloudmail_client.fetch_latest_otp(
                "abcdef@example.com",
                after_ts=0,
                max_wait=1,
                poll_interval=1,
                settle_seconds=0,
            )

        self.assertEqual(code, "654321")
        self.assertEqual(post.call_args.kwargs["json"]["toEmail"], "abcdef@example.com")

if __name__ == "__main__":
    unittest.main()
