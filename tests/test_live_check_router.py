import unittest
from unittest.mock import MagicMock, patch

from core.live_check_router import (
    CURRENT_PROTOCOL_DRIVER,
    LiveCheckDriverError,
    resolve_driver,
    run_probe,
)
from webui import config_editor


class LiveCheckRouterTests(unittest.TestCase):
    def test_missing_config_uses_current_protocol_driver(self):
        with patch("config.account.ACCOUNT_LIVE_CHECK_DRIVER", ""):
            self.assertEqual(CURRENT_PROTOCOL_DRIVER, resolve_driver())

    def test_legacy_aliases_only_resolve_to_current_protocol(self):
        self.assertEqual(CURRENT_PROTOCOL_DRIVER, resolve_driver("current"))
        self.assertEqual(CURRENT_PROTOCOL_DRIVER, resolve_driver("protocol"))

    def test_unopened_driver_fails_before_network(self):
        with self.assertRaisesRegex(LiveCheckDriverError, "尚未开放"):
            resolve_driver("protocol_v2")

    def test_browser_driver_requires_explicit_stage_two_gate(self):
        with patch("config.account.ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", False):
            with self.assertRaisesRegex(LiveCheckDriverError, "阶段 2"):
                resolve_driver("browser_roxy")

        with patch("config.account.ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", True):
            self.assertEqual("browser_roxy", resolve_driver("browser_roxy"))

    def test_current_probe_preserves_probe_contract_and_marks_driver(self):
        probe = MagicMock(return_value={"ok": True, "http_status": 200})

        result = run_probe(
            driver=CURRENT_PROTOCOL_DRIVER,
            probe=probe,
            token="existing-at",
            proxy="http://proxy.example:8080",
            max_attempts=1,
        )

        probe.assert_called_once_with(
            "existing-at",
            proxy="http://proxy.example:8080",
            max_attempts=1,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(CURRENT_PROTOCOL_DRIVER, result["live_check_driver"])

    def test_browser_probe_is_called_only_after_stage_two_gate(self):
        protocol_probe = MagicMock()
        browser_probe = MagicMock(return_value={"ok": True})

        with patch("config.account.ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", True):
            result = run_probe(
                driver="browser_roxy",
                probe=protocol_probe,
                browser_probe=browser_probe,
                token="existing-at",
                proxy="http://proxy.example:8080",
                max_attempts=1,
            )

        browser_probe.assert_called_once_with(token="existing-at", proxy="http://proxy.example:8080")
        protocol_probe.assert_not_called()
        self.assertEqual("browser_roxy", result["live_check_driver"])

    def test_live_check_config_is_editable_but_only_current_is_opened(self):
        fields = {item["key"]: item for item in config_editor.EDITABLE_FIELDS}
        self.assertIn("ACCOUNT_LIVE_CHECK_DRIVER", fields)
        self.assertEqual("account.py", fields["ACCOUNT_LIVE_CHECK_DRIVER"]["file"])
        self.assertEqual("str", fields["ACCOUNT_LIVE_CHECK_DRIVER"]["type"])
        self.assertEqual("账号补全", fields["ACCOUNT_LIVE_CHECK_DRIVER"]["group"])

    def test_enqueue_rejects_unopened_driver_before_claiming_account(self):
        from core import live_check_service

        with patch.object(live_check_service.db, "get_account") as get_account:
            result = live_check_service.enqueue_account_live_check(
                account_id=123,
                email="account@example.com",
                driver="protocol_v2",
            )

        self.assertFalse(result["accepted"])
        self.assertIn("尚未开放", result["error"])
        get_account.assert_not_called()


if __name__ == "__main__":
    unittest.main()
