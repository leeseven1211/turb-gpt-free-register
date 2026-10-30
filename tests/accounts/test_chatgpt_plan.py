# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch

from curl_cffi import requests as curl_requests

from core.accounts.plans import client as chatgpt_plan
from core.registration import plan_capture as registration_plan_capture
from core.browser import traffic as browser_traffic
from core.network import protocol_traffic
from core.auth.protocol.session import BrowserSession


class ChatGPTPlanTests(unittest.TestCase):
    def test_query_flushes_final_http_counts_only_for_its_own_session(self):
        for external in (False, True):
            with self.subTest(external=external):
                env = BrowserSession(proxy="", detect_exit_geo=False)
                env.protocol_traffic = protocol_traffic.ProtocolTrafficCapture(
                    {"operation_task_id": 1}, clock=lambda: 100.0,
                )
                response = Mock(status_code=200, text="{}", content=b"{}",
                                upload_size=0, download_size=2, redirect_count=0)
                response.json.return_value = self._accounts_check_payload()

                def quota(session, *_args):
                    session.get("https://chatgpt.com/backend-api/wham/usage", timeout=1)
                    return {}

                with patch.object(chatgpt_plan, "BrowserSession", return_value=env), \
                     patch.object(chatgpt_plan, "resolve_plan_check_route", return_value={"proxy": ""}), \
                     patch.object(chatgpt_plan, "_query_account_quota", side_effect=quota), \
                     patch.object(env.session, "get", return_value=response), \
                     patch.object(env.session, "close", wraps=env.session.close) as close, \
                     patch.object(browser_traffic, "persist_summary") as persist, \
                     patch("core.registration.debug.record_protocol_exchange"):
                    result = chatgpt_plan.check_account_plan(
                        "synthetic-token", max_attempts=1, timezone_offset_min="0",
                        **({"session": env} if external else {}),
                    )
                    self.assertTrue(result["ok"])
                    # 同一个节流窗口内第二个请求也须在自有会话结束时落盘。
                    self.assertEqual(1 if external else 2,
                                     persist.call_args.kwargs["summary"]["request_count"])
                    self.assertEqual(0 if external else 1, close.call_count)
                    if external:
                        env.close()

    @staticmethod
    def _accounts_check_payload(plus_campaign=None):
        item = {
            "account": {"account_id": "account-1", "plan_type": "free"},
            "entitlement": {"subscription_plan": "chatgptfreeplan"},
        }
        if plus_campaign is not None:
            item["eligible_promo_campaigns"] = {"plus": plus_campaign}
        return {"accounts": {"default": item}}

    def test_parse_accounts_check_distinguishes_free_trial_discount_and_no_promo(self):
        free_trial = chatgpt_plan.parse_accounts_check(self._accounts_check_payload({
            "id": "plus-1-month-free",
            "metadata": {
                "title": "One month free",
                "discount": {"percentage": 100},
                "duration": {"num_periods": 1, "period": "month"},
            },
        }))
        discount = chatgpt_plan.parse_accounts_check(self._accounts_check_payload({
            # 即使活动名沿用 trial，只要折扣百分比明确就不能当成免费试用。
            "id": "plus-trial-half-price",
            "metadata": {
                "title": "50% off for two months",
                "discount": {"percentage": 50},
                "duration": {"num_periods": 2, "period": "month"},
            },
        }))
        no_promo = chatgpt_plan.parse_accounts_check(self._accounts_check_payload())

        self.assertEqual(free_trial["plus_promo_kind"], "free_trial")
        self.assertTrue(free_trial["plus_trial_eligible"])
        self.assertFalse(free_trial["plus_discount_eligible"])
        self.assertEqual(discount["plus_promo_kind"], "discount")
        self.assertTrue(discount["plus_promo_eligible"])
        self.assertFalse(discount["plus_trial_eligible"])
        self.assertTrue(discount["plus_discount_eligible"])
        self.assertEqual(discount["plus_promo_discount_percentage"], 50)
        self.assertEqual(discount["plus_promo_duration_num_periods"], 2)
        self.assertEqual(no_promo["plus_promo_kind"], "none")
        self.assertFalse(no_promo["plus_promo_eligible"])

    def test_parse_accounts_check_keeps_go_trial_and_plus_discount_separate(self):
        payload = self._accounts_check_payload({
            "id": "plus-half-price",
            "metadata": {"discount": {"percentage": 50}, "duration": {"num_periods": 2, "period": "month"}},
        })
        payload["accounts"]["default"]["eligible_promo_campaigns"]["go"] = {
            "id": "go-one-month-free",
            "metadata": {"discount": {"percentage": 100}, "duration": {"num_periods": 1, "period": "month"}},
        }

        result = chatgpt_plan.parse_accounts_check(payload)

        self.assertEqual([item["plan"] for item in result["account_promotions"]], ["go", "plus"])
        self.assertEqual([item["kind"] for item in result["account_promotions"]], ["free_trial", "discount"])
        self.assertEqual(result["plus_promo_kind"], "discount")
        self.assertEqual(result["plus_promo_campaign_id"], "plus-half-price")
        self.assertFalse(result["plus_trial_eligible"])
        self.assertEqual(result["promotion_query_snapshot"]["version"], 1)
        self.assertEqual(result["promotion_query_snapshot"]["source"], "accounts_check")
        self.assertEqual(result["promotion_query_snapshot"]["campaign_keys"], ["plus", "go"])

    def test_go_only_promotion_does_not_enable_plus_link_extraction(self):
        payload = self._accounts_check_payload()
        payload["accounts"]["default"]["eligible_promo_campaigns"] = {
            "go": {"id": "go-free", "metadata": {"discount": {"percentage": 100}}},
        }

        result = chatgpt_plan.parse_accounts_check(payload)

        self.assertEqual(result["account_promotions"][0]["kind"], "free_trial")
        self.assertEqual(result["account_promotions"][1]["kind"], "none")
        self.assertFalse(result["plus_trial_eligible"])
        self.assertFalse(result["plus_promo_eligible"])
        self.assertIsNone(result["plus_trial_campaign_id"])

    def test_go_offer_is_not_a_free_promotion(self):
        payload = self._accounts_check_payload()
        payload["accounts"]["default"]["eligible_offers"] = {
            "offers": [{"id": "chatgptgoplan"}],
        }

        result = chatgpt_plan.parse_accounts_check(payload)

        self.assertEqual(result["eligible_offer_ids"], ["chatgptgoplan"])
        self.assertEqual([item["kind"] for item in result["account_promotions"]], ["none", "none"])
        self.assertFalse(any(item["eligible"] for item in result["account_promotions"]))

    def test_nonfree_account_keeps_previous_plus_eligibility_boundary(self):
        payload = self._accounts_check_payload({"id": "plus-free", "metadata": {"discount": {"percentage": 100}}})
        item = payload["accounts"]["default"]
        item["account"]["plan_type"] = "go"
        item["entitlement"]["subscription_plan"] = "chatgptgoplan"
        item["eligible_promo_campaigns"]["go"] = {"id": "go-free", "metadata": {"discount": {"percentage": 100}}}

        result = chatgpt_plan.parse_accounts_check(payload)

        self.assertEqual([entry["kind"] for entry in result["account_promotions"]], ["none", "none"])
        self.assertFalse(result["plus_trial_eligible"])
        self.assertEqual(len(result["promotion_query_snapshot"]["campaigns"]), 2)

    def test_malformed_promotion_metadata_keeps_plan_query_successful(self):
        payload = self._accounts_check_payload({"id": "plus-free", "metadata": ["unsupported"]})
        payload["accounts"]["default"]["eligible_promo_campaigns"]["go"] = "unsupported"

        result = chatgpt_plan.parse_accounts_check(payload)

        self.assertTrue(result["ok"])
        self.assertEqual([entry["kind"] for entry in result["account_promotions"]], ["unknown", "unknown"])
        self.assertFalse(result["plus_trial_eligible"])

    def test_registration_capture_returns_the_same_go_plus_evidence(self):
        payload = self._accounts_check_payload()
        payload["accounts"]["default"]["eligible_promo_campaigns"] = {
            "go": {"id": "go-free", "metadata": {"discount": {"percentage": 100}}},
        }
        result = chatgpt_plan.parse_accounts_check(payload)

        captured = registration_plan_capture._normalize_capture({"status": 200, "data": payload}, token="")

        self.assertEqual(captured["account_promotions"], result["account_promotions"])
        self.assertEqual(captured["promotion_query_snapshot"], result["promotion_query_snapshot"])
        self.assertFalse(captured["plus_trial_eligible"])

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

        with patch.object(chatgpt_plan, "BrowserSession") as browser_session, \
             patch.object(chatgpt_plan, "resolve_plan_check_route", return_value={"proxy": "http://192.0.2.10:8080"}):
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
        self.assertEqual([item["plan"] for item in result["account_promotions"]], ["go", "plus"])
        self.assertEqual(result["promotion_query_snapshot"]["source"], "accounts_check")
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

        with patch.object(chatgpt_plan, "resolve_plan_check_route", return_value={"proxy": "http://192.0.2.10:8080"}):
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

    @staticmethod
    def _plan_check_session():
        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.js_timezone_offset_min.return_value = -480
        return session

    def test_plan_check_marks_final_proxy_transport_failure(self):
        for exception_type in (
            curl_requests.exceptions.ProxyError,
            curl_requests.exceptions.ConnectionError,
            curl_requests.exceptions.SSLError,
            curl_requests.exceptions.Timeout,
        ):
            with self.subTest(exception=exception_type.__name__):
                session = self._plan_check_session()
                session.get.side_effect = exception_type("proxy transport failed")

                result = chatgpt_plan.check_account_plan(
                    "access-token",
                    proxy="http://proxy.example.test:8080",
                    session=session,
                    max_attempts=1,
                )

                self.assertFalse(result["ok"])
                self.assertTrue(result["proxy_transport_failure"])
                self.assertIsNone(result["http_status"])

    def test_plan_check_does_not_mark_local_or_direct_transport_errors(self):
        for proxy, exception in (
            ("http://proxy.example.test:8080", RuntimeError("local setup failed")),
            ("", curl_requests.exceptions.ProxyError("direct request failed")),
        ):
            with self.subTest(proxy=proxy, exception=type(exception).__name__):
                session = self._plan_check_session()
                session.get.side_effect = exception

                result = chatgpt_plan.check_account_plan(
                    "access-token",
                    proxy=proxy,
                    session=session,
                    max_attempts=1,
                )

                self.assertFalse(result["ok"])
                self.assertNotIn("proxy_transport_failure", result)

    def test_plan_check_does_not_mark_http_failures_as_proxy_transport_failure(self):
        for status_code in (401, 403, 429, 502):
            with self.subTest(status_code=status_code):
                response = Mock()
                response.status_code = status_code
                response.text = "upstream error"
                session = self._plan_check_session()
                session.get.return_value = response

                result = chatgpt_plan.check_account_plan(
                    "access-token",
                    proxy="http://proxy.example.test:8080",
                    session=session,
                    max_attempts=1,
                )

                self.assertFalse(result["ok"])
                self.assertNotIn("proxy_transport_failure", result)

    def test_plan_check_successful_retry_does_not_keep_old_proxy_failure_marker(self):
        response = Mock()
        response.status_code = 200
        response.text = "{}"
        response.json.return_value = self._accounts_check_payload()
        quota_response = Mock()
        quota_response.status_code = 200
        quota_response.text = "{}"
        quota_response.json.return_value = {"rate_limit": {"allowed": True}}
        session = self._plan_check_session()
        session.get.side_effect = [
            curl_requests.exceptions.ProxyError("temporary proxy failure"),
            response,
            quota_response,
        ]

        result = chatgpt_plan.check_account_plan(
            "access-token",
            proxy="http://proxy.example.test:8080",
            session=session,
            max_attempts=2,
            retry_delay=0,
        )

        self.assertTrue(result["ok"])
        self.assertNotIn("proxy_transport_failure", result)


if __name__ == "__main__":
    unittest.main()
