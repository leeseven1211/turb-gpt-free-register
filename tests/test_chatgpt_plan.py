# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch

from core import chatgpt_plan


class ChatGPTPlanTests(unittest.TestCase):
    def test_parse_quota_usage_classifies_windows_and_calculates_remaining(self):
        result = chatgpt_plan.parse_quota_usage({
            "rate_limit": {
                "allowed": True,
                "limit_reached": False,
                "primary_window": {
                    "used_percent": 12.5,
                    "limit_window_seconds": 5 * 60 * 60,
                    "reset_after_seconds": 1200,
                    "reset_at": 1790000000,
                },
                "secondary_window": {
                    "used_percent": 80,
                    "limit_window_seconds": 7 * 24 * 60 * 60,
                    "reset_after_seconds": 86400,
                    "reset_at": 1791000000,
                },
            }
        })

        self.assertEqual(result["quota_status"], "success")
        self.assertEqual(result["quota_type"], "5小时限额 / 周限额")
        self.assertEqual([item["kind"] for item in result["quota_windows"]], ["five_hour", "weekly"])
        self.assertEqual(result["quota_windows"][0]["remaining_percent"], 87.5)
        self.assertEqual(result["quota_windows"][1]["remaining_percent"], 20.0)
        self.assertEqual(chatgpt_plan.classify_quota_window(30 * 24 * 60 * 60), ("monthly", "月限额"))

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
        quota_response = Mock()
        quota_response.status_code = 200
        quota_response.text = "{}"
        quota_response.json.return_value = {
            "rate_limit": {
                "allowed": True,
                "primary_window": {
                    "used_percent": 12,
                    "limit_window_seconds": 5 * 60 * 60,
                    "reset_after_seconds": 1200,
                    "reset_at": 1790000000,
                },
            }
        }
        session = Mock()
        session.get.side_effect = [response, quota_response]
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
        self.assertEqual(result["quota_type"], "5小时限额")
        self.assertEqual(result["quota_windows"][0]["remaining_percent"], 88.0)
        browser_session.assert_not_called()
        self.assertEqual(session.get.call_count, 2)
        session.session.close.assert_not_called()
        request_url = session.get.call_args.args[0]
        request_headers = session.get.call_args.kwargs["headers"]
        self.assertEqual(request_url, "https://chatgpt.com/backend-api/wham/usage")
        self.assertEqual(
            request_headers["x-openai-target-route"],
            "/backend-api/wham/usage",
        )
        self.assertEqual(request_headers["openai-beta"], "codex-1")
        plan_request_url = session.get.call_args_list[0].args[0]
        self.assertIn("timezone_offset_min=-480", plan_request_url)

    def test_plan_check_can_record_protocol_probe_session_without_changing_request(self):
        response = Mock()
        response.status_code = 200
        response.text = "{}"
        response.json.return_value = {
            "accounts": {
                "default": {
                    "account": {"account_id": "account-1", "plan_type": "free"},
                    "entitlement": {},
                }
            }
        }
        session = Mock()
        session.get.return_value = response
        session.js_timezone_offset_min.return_value = -480
        session.get_chatgpt_headers.return_value = {"oai-session-id": "session-1"}
        recorder = Mock()

        result = chatgpt_plan.check_account_plan(
            "access-token",
            proxy="",
            session=session,
            max_attempts=1,
            context_recorder=recorder,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(session.get.call_count, 2)
        recorder.open_protocol_session.assert_called_once_with(
            session, route_attempt_no=1, auth_method="access_token",
        )
        recorder.finish_session.assert_called_once_with(
            session, status="success", result_code="authenticated",
        )


if __name__ == "__main__":
    unittest.main()
