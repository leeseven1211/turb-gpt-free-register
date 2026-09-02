import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core import live_check_browser


class _FakeDriver:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def execute_async_script(self, *args):
        self.calls.append(args)
        return self.response


class LiveCheckBrowserProbeTests(unittest.TestCase):
    @staticmethod
    def _success_body():
        return json.dumps({
            "accounts": {
                "default": {
                    "account": {"account_id": "acct-1", "plan_type": "free"},
                    "entitlement": {},
                },
            },
        })

    def test_probe_uses_one_authenticated_fetch_without_browser_credentials(self):
        driver = _FakeDriver({"status": 200, "body": self._success_body()})

        result = live_check_browser._execute_probe(driver, "test-at", "http://proxy.example:8080")

        self.assertTrue(result["ok"])
        self.assertEqual("browser_roxy", result["live_check_driver"])
        self.assertEqual("access_token", result["validation_method"])
        script, endpoint, headers = driver.calls[0]
        self.assertIn("credentials: 'omit'", script)
        self.assertIn("redirect: 'manual'", script)
        self.assertNotIn("auth/login", endpoint)
        self.assertNotIn("email", script.lower())
        self.assertEqual("Bearer test-at", headers["authorization"])

    def test_401_is_reported_as_at_failure_without_refresh(self):
        driver = _FakeDriver({"status": 401, "body": "unauthorized"})

        result = live_check_browser._execute_probe(driver, "test-at", None)

        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_live_check"])
        self.assertTrue(result["token_expired"])
        self.assertEqual(401, result["http_status"])
        self.assertEqual("auth", result["error_category"])
        self.assertEqual("access_token", result["validation_method"])

    def test_profile_failure_is_classified_before_driver_creation(self):
        client = MagicMock()
        client.open_profile.side_effect = RuntimeError("proxy rejected")

        with (
            patch.object(live_check_browser, "available", return_value=True),
            patch.object(live_check_browser, "RoxyBrowserClient", return_value=client),
            patch.object(live_check_browser, "build_driver") as build_driver,
        ):
            result = live_check_browser.run_probe(token="test-at", proxy="http://127.0.0.1:1")

        self.assertFalse(result["ok"])
        self.assertEqual("profile", result["error_category"])
        build_driver.assert_not_called()

    def test_navigation_failure_is_classified_and_profile_is_cleaned(self):
        opened = SimpleNamespace(profile_id="profile-1")
        driver = MagicMock()
        client = MagicMock()
        client.open_profile.return_value = opened

        with (
            patch.object(live_check_browser, "available", return_value=True),
            patch.object(live_check_browser, "RoxyBrowserClient", return_value=client),
            patch.object(live_check_browser, "build_driver", return_value=driver),
            patch.object(live_check_browser, "safe_get", side_effect=TimeoutError("proxy timeout")),
        ):
            result = live_check_browser.run_probe(token="test-at", proxy="http://127.0.0.1:1")

        self.assertFalse(result["ok"])
        self.assertEqual("browser_navigation", result["error_category"])
        driver.quit.assert_called_once_with()
        client.cleanup_profile.assert_called_once_with(opened)

    def test_run_probe_cleans_profile_after_success(self):
        opened = SimpleNamespace(profile_id="profile-1")
        driver = MagicMock()
        client = MagicMock()
        client.open_profile.return_value = opened
        expected = {"ok": True, "status": "live", "live_check_driver": "browser_roxy"}

        with (
            patch.object(live_check_browser, "available", return_value=True),
            patch.object(live_check_browser, "RoxyBrowserClient", return_value=client),
            patch.object(live_check_browser, "build_driver", return_value=driver),
            patch.object(live_check_browser, "safe_get") as safe_get,
            patch.object(live_check_browser, "_execute_probe", return_value=expected),
        ):
            result = live_check_browser.run_probe(token="test-at", proxy="http://proxy.example:8080")

        self.assertEqual(expected, result)
        client.open_profile.assert_called_once_with(proxy_url="http://proxy.example:8080")
        safe_get.assert_called_once()
        self.assertEqual("https://chatgpt.com/robots.txt", safe_get.call_args.args[1])
        driver.quit.assert_called_once_with()
        client.cleanup_profile.assert_called_once_with(opened)


if __name__ == "__main__":
    unittest.main()
