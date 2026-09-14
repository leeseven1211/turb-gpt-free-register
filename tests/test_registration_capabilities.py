"""注册/Codex 浏览器能力边界契约。"""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core import browser_use_registration, roxy_registration
from core.registration import auth_capabilities, browser_use_auth, selenium_auth
from core.registration.auth_context import AuthExecutionContext, CancellationRequested


class RegistrationCapabilityContractTests(TestCase):
    def test_selenium_facade_keeps_legacy_patch_point(self):
        expected = {"accessToken": "test-token"}
        with patch.object(auth_capabilities, "_fetch_chatgpt_session", return_value=expected) as fetch:
            result = selenium_auth.fetch_chatgpt_session("driver", timeout=3)

        self.assertIs(expected, result)
        fetch.assert_called_once_with("driver", timeout=3)

    def test_roxy_compatibility_override_is_context_local(self):
        barrier = __import__("threading").Barrier(2)

        def invoke(label):
            def override(_driver):
                barrier.wait(timeout=2)
                return label

            return auth_capabilities.call_with_compatibility(
                "_log_prefix",
                {"_log_prefix": override},
                object(),
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = sorted(pool.map(invoke, ("one", "two")))

        self.assertEqual(["one", "two"], results)

    def test_injected_auth_context_cancels_before_browser_io(self):
        context = AuthExecutionContext(cancellation=lambda: True)
        with self.assertRaises(CancellationRequested):
            selenium_auth.fetch_chatgpt_session(object(), timeout=1, context=context)

    def test_shared_capabilities_are_split_and_do_not_import_app_orchestrators(self):
        root = Path(__file__).resolve().parents[1] / "core" / "registration"
        shared = [
            root / name
            for name in (
                "auth_capabilities.py",
                "auth_context.py",
                "selenium_resource.py",
                "selenium_dom.py",
                "email_otp.py",
                "password_auth.py",
                "session_auth.py",
                "mfa_auth.py",
            )
        ]
        self.assertLess(len((root / "auth_capabilities.py").read_text().splitlines()), 400)
        forbidden = {"core.registration_service", "core.roxy_codex_oauth", "core.registration.roxy"}
        offenders = []
        for path in shared:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                else:
                    continue
                for module in modules:
                    if module in forbidden:
                        offenders.append(f"{path.name}: {module}")
        self.assertEqual([], offenders)

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
