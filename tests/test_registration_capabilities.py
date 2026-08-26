"""注册/Codex 浏览器能力边界契约。"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core import browser_use_registration, roxy_registration
from core.registration import browser_use_auth, selenium_auth


class RegistrationCapabilityContractTests(TestCase):
    def test_selenium_facade_keeps_legacy_patch_point(self):
        expected = {"accessToken": "test-token"}
        with patch.object(roxy_registration, "_fetch_chatgpt_session", return_value=expected) as fetch:
            result = selenium_auth.fetch_chatgpt_session("driver", timeout=3)

        self.assertIs(expected, result)
        fetch.assert_called_once_with("driver", timeout=3)

    def test_browser_use_facade_keeps_legacy_patch_point(self):
        with patch.object(browser_use_registration, "_timeout_ms", return_value=1234) as timeout:
            result = browser_use_auth.timeout_ms(12)

        self.assertEqual(1234, result)
        timeout.assert_called_once_with(12)

    def test_public_capability_names_are_explicit(self):
        self.assertTrue(set(selenium_auth.__all__) <= set(vars(selenium_auth)))
        self.assertTrue(set(browser_use_auth.__all__) <= set(vars(browser_use_auth)))
        self.assertIn("fetch_chatgpt_session", selenium_auth.__all__)
        self.assertIn("wait_after_otp", browser_use_auth.__all__)

    def test_core_does_not_import_private_browser_helpers_across_modules(self):
        root = Path(__file__).resolve().parents[1] / "core"
        offenders = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.module not in {
                    "core.roxy_registration",
                    "core.browser_use_registration",
                }:
                    continue
                private_names = [alias.name for alias in node.names if alias.name.startswith("_")]
                if private_names:
                    offenders.append(f"{path.relative_to(root.parent)}: {private_names}")

        self.assertEqual([], offenders)


if __name__ == "__main__":
    import unittest

    unittest.main()
