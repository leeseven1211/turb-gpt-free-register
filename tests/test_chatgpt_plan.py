# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch

from core import chatgpt_plan


class ChatGPTPlanTests(unittest.TestCase):
    def test_common_headers_match_frontend_context(self):
        session = Mock()
        session.get_chatgpt_headers.return_value = {
            "User-Agent": "Mozilla/5.0",
            "oai-client-build-number": "8370486",
            "oai-client-version": "build",
            "oai-device-id": "device-1",
            "oai-language": "zh-CN",
            "oai-session-id": "session-1",
            "x-datadog-trace-id": "trace-1",
        }

        headers = chatgpt_plan._common_headers(
            session,
            "access-token",
            {"account_id": "account-1"},
        )

        session.get_chatgpt_headers.assert_called_once_with(referer="https://chatgpt.com/")
        self.assertEqual(headers["authorization"], "Bearer access-token")
        self.assertEqual(headers["chatgpt-account-id"], "account-1")
        self.assertEqual(
            headers["x-openai-target-route"],
            "/backend-api/accounts/check/{version}",
        )
        self.assertEqual(
            headers["x-openai-target-path"],
            "/backend-api/accounts/check/v4-2023-04-27",
        )
        self.assertEqual(headers["oai-session-id"], "session-1")

    def test_plan_check_reuses_existing_protocol_session(self):
        response = Mock()
        response.status_code = 200
        response.text = "{}"
        response.json.return_value = {
            "accounts": {
                "default": {
                    "account": {"account_id": "account-1", "plan_type": "free"},
                    "entitlement": {"subscription_plan": "chatgptfreeplan"},
                }
            }
        }
        session = Mock()
        session.get.return_value = response
        session.js_timezone_offset_min.return_value = -480
        session.get_chatgpt_headers.return_value = {
            "User-Agent": "Mozilla/5.0",
            "oai-client-build-number": "8370486",
            "oai-client-version": "build",
            "oai-device-id": "device-1",
            "oai-language": "zh-CN",
            "oai-session-id": "session-1",
        }

        with patch.object(chatgpt_plan, "BrowserSession") as browser_session:
            result = chatgpt_plan.check_account_plan(
                "access-token",
                proxy="",
                session=session,
                max_attempts=1,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["http_status"], 200)
        browser_session.assert_not_called()
        session.get.assert_called_once()
        session.session.close.assert_not_called()
        request_url = session.get.call_args.args[0]
        request_headers = session.get.call_args.kwargs["headers"]
        self.assertIn("timezone_offset_min=-480", request_url)
        self.assertEqual(
            request_headers["x-openai-target-route"],
            "/backend-api/accounts/check/{version}",
        )


if __name__ == "__main__":
    unittest.main()
