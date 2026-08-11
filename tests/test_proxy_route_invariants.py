import unittest
import ast
import inspect
import textwrap
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse


class ProxyRouteInvariantTests(unittest.TestCase):
    @staticmethod
    def _codex_call_keywords(func) -> dict[str, ast.AST]:
        tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if name == "run_roxy_codex_oauth":
                return {item.arg: item.value for item in node.keywords if item.arg}
        raise AssertionError("run_roxy_codex_oauth call not found")

    def test_browser_session_fails_closed_in_platform_mode_without_lease(self):
        from core.session import BrowserSession

        with patch("core.proxy_provider.registration_proxy_mode", return_value="1024"):
            with self.assertRaisesRegex(RuntimeError, "禁止.*PROXY_POOL"):
                BrowserSession(proxy=None)

    def test_codex_standalone_call_acquires_platform_account_route(self):
        from core import codex_oauth

        route = SimpleNamespace(
            proxy_url="http://platform.example:8080",
            provider="1024proxy",
            region="JP",
            public_dict=lambda: {"network_route": "proxy"},
            release=MagicMock(),
        )
        expected = {"ok": True, "status": "success"}
        with (
            patch("config.codex.CODEX_OAUTH_DRIVER", "same_as_registration"),
            patch("config.roxybrowser.REGISTRATION_DRIVER", "roxy"),
            patch("core.db.get_account_by_email", return_value={"id": 7}),
            patch("core.account_proxy.acquire_account_proxy", return_value=route) as acquire,
            patch("core.roxy_codex_oauth.run_roxy_codex_oauth", return_value=expected) as run_roxy,
        ):
            result = codex_oauth.run_codex_oauth("account@example.com", force=True)

        self.assertEqual(expected, result)
        acquire.assert_called_once_with(
            account_id=7,
            email="account@example.com",
            purpose="codex-oauth",
        )
        run_roxy.assert_called_once()
        self.assertEqual("http://platform.example:8080", run_roxy.call_args.kwargs["proxy"])
        route.release.assert_called_once()

    def test_authorize_url_can_preserve_existing_login_session(self):
        from core.codex_oauth import _build_authorize_url

        params = parse_qs(urlparse(_build_authorize_url("state", "challenge", prompt=None)).query)
        self.assertNotIn("prompt", params)

        login_params = parse_qs(urlparse(_build_authorize_url("state", "challenge")).query)
        self.assertEqual(["login"], login_params.get("prompt"))

    def test_live_check_explicit_direct_does_not_fall_back_to_pool(self):
        from core import account_liveness

        session = MagicMock()
        with (
            patch("core.account_liveness.BrowserSession", return_value=session) as browser_session,
            patch("core.account_liveness.get_providers"),
            patch("core.account_liveness.get_csrf_token", return_value="csrf"),
            patch("core.account_liveness.signin_openai", return_value="https://auth.example/authorize"),
        ):
            returned, url = account_liveness._network_preflight_with_retry(
                "account@example.com",
                "",
                max_attempts=1,
            )

        self.assertIs(session, returned)
        self.assertEqual("https://auth.example/authorize", url)
        browser_session.assert_called_once_with(proxy="")

    def test_immediate_browser_oauth_reuses_proxy_and_login_state(self):
        from core.cloakbrowser_registration import run_cloak_registration
        from core.roxy_registration import run_roxy_registration

        for func in (run_roxy_registration, run_cloak_registration):
            keywords = self._codex_call_keywords(func)
            self.assertEqual("proxy", ast.unparse(keywords["proxy"]))
            self.assertIsInstance(keywords["clear_existing_state"], ast.Constant)
            self.assertIs(False, keywords["clear_existing_state"].value)

    def test_existing_login_account_chooser_matches_only_target_email(self):
        from core.roxy_codex_oauth import _select_existing_account_if_present

        driver = MagicMock()
        driver.execute_script.return_value = {"clicked": True, "actionCount": 3}
        self.assertTrue(_select_existing_account_if_present(driver, "account@example.com"))
        self.assertEqual("account@example.com", driver.execute_script.call_args.args[-1])

        driver.reset_mock()
        self.assertFalse(_select_existing_account_if_present(driver, ""))
        driver.execute_script.assert_not_called()


if __name__ == "__main__":
    unittest.main()
