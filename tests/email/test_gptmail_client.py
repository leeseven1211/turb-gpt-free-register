# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch

from core.email.gptmail import client as gptmail_client


class GPTMailClientTests(unittest.TestCase):
    @patch("core.email.gptmail.client.time.sleep")
    @patch("core.email.gptmail.client.requests.get")
    def test_fetch_latest_otp_reads_only_new_openai_email(self, get, sleep):
        inbox = Mock(status_code=200)
        inbox.json.return_value = {
            "success": True,
            "data": {
                "emails": [
                    {
                        "id": "old",
                        "timestamp": 100,
                        "from_address": "noreply@openai.com",
                        "subject": "Code 111111",
                    },
                    {
                        "id": "new",
                        "timestamp": 205,
                        "from_address": "noreply@openai.com",
                        "subject": "Code 654321",
                    },
                ]
            },
        }
        detail = Mock(status_code=200)
        detail.json.return_value = {
            "success": True,
            "data": {
                "id": "new",
                "timestamp": 205,
                "from_address": "noreply@openai.com",
                "subject": "Code 654321",
                "content": "Your code is 654321",
            },
        }
        get.side_effect = [inbox, detail]

        with patch.object(gptmail_client._email_cfg, "GPTMAIL_API_KEY", "key-123", create=True):
            code = gptmail_client.fetch_latest_otp(
                "fresh@gptmail.test",
                after_ts=200,
                max_wait=1,
                poll_interval=1,
                settle_seconds=0,
            )

        self.assertEqual(code, "654321")

    @patch("core.email.gptmail.client.time.monotonic")
    @patch("core.email.gptmail.client.time.sleep")
    @patch("core.email.gptmail.client.requests.get")
    def test_fetch_latest_otp_does_not_reset_settle_for_same_message(self, get, sleep, monotonic):
        inbox = Mock(status_code=200)
        inbox.json.return_value = {
            "success": True,
            "data": {"emails": [{
                "id": "same",
                "timestamp": 205,
                "from_address": "noreply@openai.com",
                "subject": "Code 654321",
            }]},
        }
        detail = Mock(status_code=200)
        detail.json.return_value = {
            "success": True,
            "data": {
                "id": "same",
                "timestamp": 205,
                "from_address": "noreply@openai.com",
                "subject": "Code 654321",
                "content": "Your code is 654321",
            },
        }
        get.side_effect = lambda url, **kwargs: inbox if url.endswith("/emails") else detail
        clock = iter([0, 0, 0, 0, 0, 3, 6])
        monotonic.side_effect = lambda: next(clock, 6)
        sleep_calls = []

        def sleep_once(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) > 1:
                self.fail("同一封邮件不应重置 OTP settle 计时")

        sleep.side_effect = sleep_once
        with patch.object(gptmail_client._email_cfg, "GPTMAIL_API_KEY", "key-123", create=True):
            code = gptmail_client.fetch_latest_otp(
                "fresh@gptmail.test",
                after_ts=200,
                max_wait=10,
                poll_interval=3,
                settle_seconds=5,
            )

        self.assertEqual(code, "654321")
        self.assertEqual(sleep_calls, [3])
