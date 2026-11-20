"""Codex execution kernels retain requests and the legacy patch boundary."""
from dataclasses import FrozenInstanceError, replace
import importlib
import json
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.codex import oauth
from core.codex.roxy import oauth as roxy


class CodexKernelExecutionTests(unittest.TestCase):
    def kernel(self, family):
        path = {
            "protocol": "core.kernels.protocol.local.codex_oauth",
            "browser": "core.kernels.browser.roxy.codex_oauth",
        }[family]
        try:
            return importlib.import_module(path)
        except ModuleNotFoundError as exc:
            self.fail(f"Codex execution kernel is missing: {exc.name}")

    def test_kernels_import_without_domain_storage_config_or_optional_drivers(self):
        self.kernel("protocol")
        self.kernel("browser")
        probe = """
import importlib
import sys
from importlib.abc import MetaPathFinder

class DomainImportGuard(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith((
            "config", "core.codex", "core.accounts", "core.registration",
            "core.storage", "core.db", "selenium", "curl_cffi",
        )):
            raise AssertionError("kernel imported domain or optional dependency: " + fullname)

sys.meta_path.insert(0, DomainImportGuard())
for name in (
    "core.kernels.protocol.local.codex_oauth",
    "core.kernels.browser.roxy.codex_oauth",
):
    importlib.import_module(name)
"""
        result = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_protocol_wrapper_executes_kernel_with_current_patched_post_helper(self):
        kernel = self.kernel("protocol")
        requests = []
        response = SimpleNamespace(
            status_code=200,
            json=lambda: {
                "page": {"type": "email_verification"},
                "continue_url": "/email-verification",
                "auth_session": {"workspaces": [{"id": "workspace-1"}]},
            },
        )
        session = SimpleNamespace(
            get_auth_headers=lambda **_: {"Origin": "https://auth.openai.com"},
            post=lambda url, **kwargs: requests.append((url, kwargs)) or response,
            session=SimpleNamespace(cookies=SimpleNamespace(jar=[], get=lambda _: None)),
        )
        original_post = oauth._post_json
        helper_calls = []

        def current_post(*args, **kwargs):
            helper_calls.append(args[1])
            return original_post(*args, **kwargs)

        with (
            patch.object(oauth, "request_sentinel_token", return_value={}),
            patch.object(oauth, "build_sentinel_header", return_value=("sentinel", "so")),
            patch.object(oauth, "_post_json", side_effect=current_post),
            patch.object(oauth.time, "time", return_value=123.0),
            patch.object(kernel, "_submit_email", wraps=kernel._submit_email) as execute,
        ):
            result = oauth._submit_email(session, "fixture@example.test")

        self.assertEqual(result, ("verify", "/email-verification", 123.0))
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(helper_calls, ["https://auth.openai.com/api/accounts/authorize/continue"])
        self.assertEqual(requests, [(
            "https://auth.openai.com/api/accounts/authorize/continue",
            {
                "headers": {
                    "Origin": "https://auth.openai.com",
                    "openai-sentinel-token": "sentinel",
                    "openai-sentinel-so-token": "so",
                },
                "data": json.dumps({"username": {"kind": "email", "value": "fixture@example.test"}}),
                "allow_redirects": False,
            },
        )])
        self.assertEqual(session._codex_auth_session_payload, {"workspaces": [{"id": "workspace-1"}]})

    def test_protocol_bootstrap_keeps_navigation_parameters_and_current_retry(self):
        kernel = self.kernel("protocol")
        events = []
        session = SimpleNamespace(
            device_id="device-1", auth_session_logging_id="session-1",
            get_auth_navigate_headers=lambda **kwargs: events.append(("headers", kwargs)) or {"navigate": "yes"},
            get=lambda url, **kwargs: events.append(("get", url, kwargs)) or SimpleNamespace(
                url="https://auth.openai.com/log-in", status_code=200,
            ),
        )

        def retry(label, action):
            events.append(("retry", label))
            return action()

        with (
            patch.object(oauth, "_ensure_oai_context_url", return_value="https://auth.openai.com/authorize?fixture=1"),
            patch.object(oauth, "_with_net_retry", side_effect=retry),
        ):
            kernel._bootstrap_authorize(
                oauth._protocol_execution_context(), session, "state",
                auth_url="https://auth.openai.com/authorize",
            )

        self.assertEqual(events, [
            ("headers", {"referer": "https://chatgpt.com/"}),
            ("retry", "bootstrap authorize"),
            ("get", "https://auth.openai.com/authorize?fixture=1", {
                "headers": {"navigate": "yes"}, "allow_redirects": True,
            }),
        ])

    def test_protocol_password_inputs_do_not_read_storage_and_unknown_is_preserved(self):
        kernel = self.kernel("protocol")
        events = []

        class ProtocolError(RuntimeError):
            code = "request_unknown"

        def no_credentials(_email):
            self.fail("explicit login credentials must not read account storage")

        def verify(session, password):
            events.append(("password", password))
            raise ProtocolError()

        dependencies = kernel.PasswordAuthCallbacks(
            credentials=no_credentials, auth_error=ProtocolError, password_verify=verify,
        )
        session = SimpleNamespace(
            get_auth_navigate_headers=lambda **_: {},
            get=lambda url, **kwargs: events.append(("get", url, kwargs)) or SimpleNamespace(
                url="https://auth.openai.com/log-in/password?challenge=1", status_code=200,
            ),
        )
        context = replace(
            oauth._protocol_execution_context(),
            password_auth=lambda: dependencies,
            rotate_document_navigation_id=lambda _session: events.append(("rotate",)),
        )

        with self.assertRaises(oauth.CodexAuthResultUnknown):
            kernel._verify_saved_login_password(
                context, session, "fixture@example.test", "/log-in/password?challenge=1",
                login_password="fixture-password",
            )

        self.assertEqual(events, [
            ("get", "https://auth.openai.com/log-in/password?challenge=1", {
                "headers": {}, "allow_redirects": True,
            }),
            ("rotate",),
            ("password", "fixture-password"),
        ])

    def test_protocol_workspace_kernel_retains_state_validation(self):
        kernel = self.kernel("protocol")
        session = SimpleNamespace(
            get_auth_headers=lambda **_: {},
            post=lambda *_args, **_kwargs: SimpleNamespace(
                status_code=302, headers={
                    "Location": "http://localhost:1455/auth/callback?code=fixture-code&state=other",
                },
                json=lambda: {},
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "state 不匹配"):
            kernel._select_workspace_and_get_callback(
                oauth._protocol_execution_context(), session, "expected",
                workspace_id="workspace-1",
            )

    def test_browser_challenge_kernel_uses_current_password_and_totp_patch_points(self):
        kernel = self.kernel("browser")
        driver = SimpleNamespace(step="password")
        events = []

        def submit_password(_driver, email, password):
            events.append(("password", email, password))
            driver.step = "totp"

        def submit_totp(_driver, email, secret):
            events.append(("totp", email, secret))
            driver.step = "advanced"

        with (
            patch.object(roxy, "_login_challenge_state", side_effect=lambda _driver: {
                "url": "https://auth.openai.com/" + driver.step, "inputs": [], "errors": [],
            }),
            patch.object(roxy, "_is_login_password_page", side_effect=lambda _driver: driver.step == "password"),
            patch.object(roxy, "_is_totp_login_page", side_effect=lambda *_: driver.step == "totp"),
            patch.object(roxy, "_is_email_verification_page", return_value=False),
            patch.object(roxy, "_is_login_advanced", side_effect=lambda *_: driver.step == "advanced"),
            patch.object(roxy, "_submit_saved_login_password", side_effect=submit_password),
            patch.object(roxy, "_submit_saved_login_totp", side_effect=submit_totp),
            patch.object(roxy, "human_delay"),
            patch.object(kernel, "_complete_login_challenge_after_email", wraps=kernel._complete_login_challenge_after_email) as execute,
        ):
            result = roxy._complete_login_challenge_after_email(
                driver, "fixture@example.test", "fixture-password", "fixture-totp", timeout=5,
            )

        self.assertEqual(result, "advanced")
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(events, [
            ("password", "fixture@example.test", "fixture-password"),
            ("totp", "fixture@example.test", "fixture-totp"),
        ])

    def test_browser_callback_kernel_recovers_navigation_history(self):
        kernel = self.kernel("browser")
        callback = "http://localhost:1455/auth/callback?code=fixture-code&state=fixture-state"
        driver = SimpleNamespace(
            current_url="chrome-error://chromewebdata/",
            execute_script=lambda _script: ["https://untrusted.example.test/", callback],
        )
        result = kernel._extract_callback_url_from_page(roxy._browser_execution_context(), driver)
        self.assertEqual(result, callback)

    def test_execution_contexts_are_frozen(self):
        self.kernel("protocol")
        self.kernel("browser")
        for context in (oauth._protocol_execution_context(), roxy._browser_execution_context()):
            with self.subTest(context=type(context).__name__):
                with self.assertRaises(FrozenInstanceError):
                    context.logger = None

    def test_browser_alias_uses_operation_binding_and_preserves_oauth_arguments(self):
        from contracts.kernel_catalog import OperationBinding
        from core.kernels import registry

        result = {"status": "fixture-browser-result"}
        calls = []

        def run(email, **kwargs):
            calls.append((email, kwargs))
            return result

        def resolve(binding):
            self.assertEqual(binding, OperationBinding("codex_oauth", "browser", "roxy"))
            return run

        with (
            patch.object(registry, "resolve_operation_runner", side_effect=resolve),
            patch.object(roxy, "run_roxy_codex_oauth", side_effect=AssertionError("legacy import bypassed registry")),
        ):
            actual = oauth.run_codex_oauth(
                "fixture@example.test", proxy="", force=True, driver_override="browser",
                phone_enabled=False,
            )

        self.assertIs(actual, result)
        self.assertEqual(calls, [("fixture@example.test", {
            "otp_provider": None, "proxy": "", "force": True,
            "allow_password_reset": False, "on_password_reset_submitted": None,
            "phone_enabled": False,
        })])

    def test_protocol_parsing_does_not_read_token_configuration(self):
        class NoTokenConfiguration:
            def __getattr__(self, name):
                raise AssertionError("parsing must not read token configuration: " + name)

        with patch.object(oauth, "_cfg", NoTokenConfiguration()):
            self.assertTrue(oauth._is_redirect_uri("http://localhost:1455/auth/callback"))

    def test_token_exchange_reads_endpoint_after_common_headers(self):
        configuration = SimpleNamespace(
            CODEX_CLIENT_ID="client-before", CODEX_REDIRECT_URI="https://before.invalid/callback",
            CODEX_TOKEN_URL="https://before.invalid/token",
        )
        requests = []

        def common_headers():
            configuration.CODEX_CLIENT_ID = "client-after"
            configuration.CODEX_REDIRECT_URI = "https://after.invalid/callback"
            configuration.CODEX_TOKEN_URL = "https://after.invalid/token"
            return {"common": "header"}

        session = SimpleNamespace(
            _get_common_headers=common_headers,
            post=lambda url, **kwargs: requests.append((url, kwargs)) or SimpleNamespace(
                status_code=200, json=lambda: {"access_token": "fixture-token"},
            ),
        )
        with patch.object(oauth, "_cfg", configuration):
            result = oauth.exchange_codex_token(session, "fixture-code", "fixture-verifier")

        self.assertEqual(result, {"access_token": "fixture-token"})
        self.assertEqual(requests, [("https://after.invalid/token", {
            "headers": {
                "common": "header", "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            "data": (
                "grant_type=authorization_code&client_id=client-before&code=fixture-code"
                "&redirect_uri=https%3A%2F%2Fbefore.invalid%2Fcallback&code_verifier=fixture-verifier"
            ),
        })])

    def test_explicit_browser_callback_timeout_does_not_read_configuration(self):
        class NoCallbackConfiguration:
            def __getattr__(self, name):
                raise AssertionError("explicit timeout must not read callback configuration: " + name)

        callback = "http://localhost:1455/auth/callback?code=fixture-code&state=fixture-state"
        with (
            patch.object(roxy, "_roxy_cfg", NoCallbackConfiguration()),
            patch.object(roxy, "_extract_callback_url_from_any_window", return_value=callback),
        ):
            self.assertEqual(roxy._wait_for_callback(SimpleNamespace(current_url=callback), timeout=5), callback)

    def test_browser_kernel_treats_password_recovery_as_opaque_at_original_stage(self):
        kernel = self.kernel("browser")
        recovery = object()
        events = []
        driver = object()

        def pending(value):
            self.assertIs(value, recovery)
            events.append("recovery_pending")
            return True

        def reset(_driver, _email, _otp_provider, **kwargs):
            self.assertIs(kwargs["recovery"], recovery)
            events.append("reset")
            return True

        with (
            patch.object(roxy, "time", SimpleNamespace(
                time=lambda: events.append("start_budget") or 100.0,
            )),
            patch.object(roxy, "_uses_roxy_saved_password_entry", side_effect=lambda _: events.append("browser_kind") or False),
            patch.object(roxy, "_password_recovery_pending", side_effect=pending, create=True),
            patch.object(roxy, "_reset_password_via_email", side_effect=reset),
            patch.object(roxy, "_is_password_recovery_profile_page", return_value=True),
        ):
            result = kernel._complete_login_challenge_after_email(
                roxy._browser_execution_context(), driver, "fixture@example.test", "", "",
                otp_provider=object(), password_recovery=recovery, allow_profile_handoff=True,
            )

        self.assertEqual(result, "profile_handoff")
        self.assertEqual(events, ["start_budget", "browser_kind", "recovery_pending", "reset"])
