# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock

from core import registration_plan_capture


class RegistrationPlanCaptureTests(unittest.TestCase):
    def _payload(self):
        return {
            "accounts": {
                "default": {
                    "account": {
                        "account_id": "acct-1",
                        "plan_type": "free",
                    },
                    "entitlement": {
                        "subscription_plan": "chatgptfreeplan",
                    },
                    "eligible_promo_campaigns": {
                        "plus": {
                            "id": "plus-trial",
                            "metadata": {
                                "title": "Plus trial",
                                "duration": {"num_periods": 1, "period": "month"},
                            },
                        },
                    },
                    "eligible_offers": {
                        "offers": [{"id": "offer-1"}],
                    },
                }
            }
        }

    def test_normalize_capture_extracts_trial_and_offer(self):
        result = registration_plan_capture._normalize_capture(
            {"status": 200, "captured_at": "2026-08-14T00:00:00Z", "data": self._payload()},
            token="",
        )
        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["current_plan_type"], "free")
        self.assertTrue(result["plus_trial_eligible"])
        self.assertEqual(result["plus_trial_campaign_id"], "plus-trial")
        self.assertEqual(result["eligible_offer_ids"], ["offer-1"])
        self.assertEqual(result["trigger"], "registration_browser_response")

    def test_invalid_capture_is_ignored(self):
        self.assertIsNone(
            registration_plan_capture._normalize_capture(
                {"status": 200, "data": {"not_accounts": {}}}, token=""
            )
        )

    def test_read_selenium_returns_first_valid_capture(self):
        driver = Mock()
        driver.execute_script.return_value = {
            "status": 200,
            "data": self._payload(),
        }
        result = registration_plan_capture.read_selenium(driver, token="", wait_seconds=0)
        self.assertTrue(result["plus_trial_eligible"])
        driver.execute_script.assert_called_once()

    def test_read_or_fetch_selenium_queries_inside_signed_in_browser(self):
        driver = Mock()
        driver.execute_script.return_value = None
        driver.execute_async_script.return_value = {
            "status": 200,
            "captured_at": "2026-08-19T00:00:00Z",
            "data": self._payload(),
        }

        result = registration_plan_capture.read_or_fetch_selenium(
            driver,
            token="header.payload.signature",
            wait_seconds=0,
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["plus_trial_eligible"])
        self.assertEqual(result["source"], "browser_fallback_request")
        driver.execute_async_script.assert_called_once()


if __name__ == "__main__":
    unittest.main()
