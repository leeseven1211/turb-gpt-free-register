import unittest
import ast
import inspect
import textwrap
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse


class ProxyRouteInvariantTests(unittest.TestCase):
    def test_blank_auth_shell_error_is_eligible_for_fresh_registration_proxy(self):
        from core.registration_service import _is_transient_registration_proxy_error

        self.assertTrue(
            _is_transient_registration_proxy_error(
                "找不到邮箱输入框/邮箱入口，state={'actions': [], 'inputs': [], "
                "'url': 'https://chatgpt.com/auth/login'}"
            )
        )
        self.assertTrue(
            _is_transient_registration_proxy_error(
                '找不到邮箱输入框/邮箱入口，state={"actions": [], "inputs": [], '
                '"url": "https://chatgpt.com/auth/login"}'
            )
        )

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

    def test_browser_session_uses_stable_identity_only_when_explicitly_passed(self):
        from core.session import BrowserSession
        from core.storage.account_auth import _derive_identity

        identity = _derive_identity("55" * 32)
        with patch("core.session.Session"):
            session = BrowserSession(proxy="", detect_exit_geo=False, identity=identity)

        self.assertEqual(identity["device_id"], session.device_id)
        self.assertEqual(identity["profile_ref"], session.protocol_profile_ref)
        self.assertEqual(identity["profile_version"], session.protocol_profile_version)
        self.assertEqual(identity["browser_profile"]["screen_width"], session.browser_profile["screen_width"])
        self.assertEqual(identity["browser_profile"]["hardware_concurrency"], session.browser_profile["hardware_concurrency"])

        with patch("core.session.Session"):
            second = BrowserSession(proxy="", detect_exit_geo=False, identity=identity)
        self.assertEqual(session.device_id, second.device_id)
        self.assertNotEqual(session.oai_session_id, second.oai_session_id)
        self.assertNotEqual(session.sentinel_sid, second.sentinel_sid)

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
            patch("core.account_liveness._warm_protocol_login_context") as warm_context,
            patch("core.account_liveness.get_csrf_token", return_value="csrf"),
            patch("core.account_liveness.signin_openai", return_value="https://auth.example/authorize"),
            patch("core.account_liveness.human_delay"),
        ):
            returned, url = account_liveness._network_preflight_with_retry(
                "account@example.com",
                "",
                max_attempts=1,
            )

        self.assertIs(session, returned)
        self.assertEqual("https://auth.example/authorize", url)
        browser_session.assert_called_once_with(proxy="")
        warm_context.assert_called_once_with(session)

    def test_live_check_warms_browser_like_context_before_csrf(self):
        from core import account_liveness

        session = MagicMock()
        with (
            patch("core.account_liveness.network_preflight") as network_preflight,
            patch("core.chatgpt_bootstrap.anonymous_bootstrap") as anonymous_bootstrap,
            patch("core.account_liveness.human_delay") as human_delay,
            patch.object(account_liveness._protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", True),
            patch.object(account_liveness._protocol_cfg, "CHATGPT_BOOTSTRAP_STRICT", False),
        ):
            account_liveness._warm_protocol_login_context(session)

        network_preflight.assert_called_once_with(session)
        anonymous_bootstrap.assert_called_once_with(session, strict=False)
        self.assertEqual(
            [unittest.mock.call("navigate"), unittest.mock.call("navigate")],
            human_delay.call_args_list,
        )

    def test_live_check_preflight_uses_fresh_proxy_from_supplier(self):
        from core import account_liveness

        first_session = MagicMock(proxy="http://first.example:8080", device_id="first-device")
        second_session = MagicMock(proxy="http://second.example:8080", device_id="second-device")
        supplier = MagicMock(side_effect=["http://first.example:8080", "http://second.example:8080"])
        with (
            patch("core.account_liveness.BrowserSession", side_effect=[first_session, second_session]) as browser_session,
            patch("core.account_liveness._warm_protocol_login_context"),
            patch("core.account_liveness.get_csrf_token", side_effect=[RuntimeError("HTTP 403"), "csrf"]),
            patch("core.account_liveness.signin_openai", return_value="https://auth.example/authorize"),
            patch("core.account_liveness.human_delay"),
            patch("core.account_liveness.time.sleep"),
        ):
            returned, url = account_liveness._network_preflight_with_retry(
                "account@example.com",
                None,
                max_attempts=2,
                proxy_supplier=supplier,
            )

        self.assertIs(second_session, returned)
        self.assertEqual("https://auth.example/authorize", url)
        self.assertEqual([unittest.mock.call(1), unittest.mock.call(2)], supplier.call_args_list)
        self.assertEqual(
            [
                unittest.mock.call(proxy="http://first.example:8080"),
                unittest.mock.call(proxy="http://second.example:8080"),
            ],
            browser_session.call_args_list,
        )
        first_session.session.close.assert_called_once()

    def test_protocol_preflight_records_rotation_without_reusing_session_ids(self):
        from core import account_liveness

        first_session = MagicMock(proxy="http://first.example:8080", device_id="first-device")
        second_session = MagicMock(proxy="http://second.example:8080", device_id="second-device")
        recorder = MagicMock()
        supplier = MagicMock(side_effect=["http://first.example:8080", "http://second.example:8080"])
        with (
            patch("core.account_liveness.BrowserSession", side_effect=[first_session, second_session]),
            patch("core.account_liveness._warm_protocol_login_context"),
            patch("core.account_liveness.get_csrf_token", side_effect=[RuntimeError("HTTP 403"), "csrf"]),
            patch("core.account_liveness.signin_openai", return_value="https://auth.example/authorize"),
            patch("core.account_liveness.human_delay"),
            patch("core.account_liveness.time.sleep"),
        ):
            returned, _ = account_liveness._network_preflight_with_retry(
                "account@example.com",
                None,
                max_attempts=2,
                proxy_supplier=supplier,
                context_recorder=recorder,
            )

        self.assertIs(second_session, returned)
        self.assertEqual(2, recorder.open_protocol_session.call_count)
        recorder.finish_session.assert_called_once_with(
            first_session,
            status="rotated",
            result_code="network_preflight_retry",
        )

    def test_live_check_without_saved_token_does_not_login_or_acquire_route(self):
        from core import live_check_service

        def make_route(proxy_url: str):
            return SimpleNamespace(
                proxy_url=proxy_url,
                public_dict=lambda: {
                    "proxy_mode": "1024",
                    "network_route": "proxy",
                    "proxy_provider": "1024proxy",
                    "proxy_used": proxy_url,
                    "proxy_region": "US",
                },
                release=MagicMock(),
            )

        first_route = make_route("http://first.example:8080")
        second_route = make_route("http://second.example:8080")

        with (
            patch.object(live_check_service.db, "mark_account_live_check_running", return_value=True),
            patch.object(live_check_service.db, "get_account", return_value={}),
            patch.object(live_check_service.db, "update_account_liveness") as updated,
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "check_account_liveness") as email_login,
            patch("core.account_proxy.acquire_account_proxy", side_effect=[first_route, second_route]) as acquire,
            patch.object(live_check_service._QUEUE_SLOTS, "release"),
        ):
            result = live_check_service._run_live_check(
                account_id=8,
                email="account@example.com",
                proxy=None,
                trigger="manual",
            )

        self.assertFalse(result["ok"])
        self.assertIn("没有 accessToken", result["error"])
        acquire.assert_not_called()
        email_login.assert_not_called()
        self.assertNotIn("access_token", updated.call_args.args[1])

    def test_protocol_v2_refresh_loads_stable_identity_only_in_account_stable_mode(self):
        from core import live_check_service

        route = SimpleNamespace(
            proxy_url="http://stable.example:8080",
            public_dict=lambda: {
                "proxy_mode": "explicit",
                "network_route": "proxy",
                "proxy_provider": "manual",
                "proxy_used": "http://stable.example:8080",
                "proxy_region": "US",
            },
            release=MagicMock(),
        )
        identity = SimpleNamespace(profile_ref="abc123def456", profile_version=1)
        refreshed = {
            "ok": True,
            "status": "live",
            "access_token": "fresh-token",
            "session": {"account": {"planType": "free"}},
            "validation_method": "authenticated_session",
            "live_check_driver": "protocol_v2",
        }
        with (
            patch("config.account.ACCOUNT_AUTH_V2_ENABLED", True),
            patch("config.account.ACCOUNT_AUTH_PROFILE_MODE", "account_stable"),
            patch.object(live_check_service.db, "mark_account_live_check_running", return_value=True),
            patch.object(live_check_service.db, "get_account", return_value={"access_token": "expired-token"}),
            patch.object(live_check_service.db, "update_account_liveness"),
            patch.object(live_check_service, "token_claims", return_value={"token_expired": True}),
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service._QUEUE_SLOTS, "release"),
            patch("core.account_proxy.acquire_account_proxy", return_value=route),
            patch("core.storage.account_auth.ensure_account_protocol_identity", return_value=identity) as ensure,
            patch("core.protocol_v2_liveness.refresh_access_token", return_value=refreshed) as refresh,
        ):
            result = live_check_service._run_live_check(
                account_id=85,
                email="first@example.com",
                proxy="",
                trigger="token_refresh_manual",
                force_refresh=True,
                refresh_driver="protocol_v2",
            )

        self.assertTrue(result["ok"])
        ensure.assert_called_once_with(85)
        self.assertIs(identity, refresh.call_args.kwargs["identity"])
        route.release.assert_called_once_with(reason="live-check-85")

    def test_live_check_uses_valid_saved_token_before_email_login(self):
        from core import live_check_service

        route = SimpleNamespace(
            proxy_url="http://fresh.example:8080",
            public_dict=lambda: {
                "proxy_mode": "1024",
                "network_route": "proxy",
                "proxy_provider": "1024proxy",
                "proxy_used": "http://fresh.example:8080",
                "proxy_region": "US",
            },
            release=MagicMock(),
        )
        updated = MagicMock()
        with (
            patch.object(live_check_service.db, "mark_account_live_check_running", return_value=True),
            patch.object(live_check_service.db, "get_account", return_value={"access_token": "valid-token"}),
            patch.object(live_check_service.db, "update_account_liveness", updated),
            patch.object(live_check_service, "token_claims", return_value={"token_expired": False}),
            patch.object(
                live_check_service,
                "check_account_plan",
                return_value={"ok": True, "http_status": 200, "current_plan_type": "free"},
            ) as probe,
            patch.object(live_check_service, "check_account_liveness") as email_login,
            patch.object(live_check_service, "_append_log"),
            patch("core.account_proxy.acquire_account_proxy", return_value=route),
            patch.object(live_check_service._QUEUE_SLOTS, "release"),
        ):
            result = live_check_service._run_live_check(
                account_id=85,
                email="first@example.com",
                proxy=None,
                trigger="manual",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("live", result["status"])
        self.assertEqual("access_token", result["validation_method"])
        probe.assert_called_once_with(
            "valid-token",
            proxy="http://fresh.example:8080",
            max_attempts=1,
        )
        email_login.assert_not_called()
        persisted = updated.call_args.args[1]
        self.assertTrue(persisted["ok"])
        self.assertEqual("access_token", persisted["validation_method"])
        route.release.assert_called_once_with(reason="live-check-85")

    def test_expired_token_live_check_does_not_login_or_refresh(self):
        from core import live_check_service

        route = SimpleNamespace(
            proxy_url="http://fresh.example:8080",
            public_dict=lambda: {
                "proxy_mode": "1024",
                "network_route": "proxy",
                "proxy_provider": "1024proxy",
                "proxy_used": "http://fresh.example:8080",
                "proxy_region": "US",
            },
            release=MagicMock(),
        )
        with (
            patch.object(live_check_service.db, "mark_account_live_check_running", return_value=True),
            patch.object(live_check_service.db, "get_account", return_value={"access_token": "expired-token"}),
            patch.object(live_check_service.db, "update_account_liveness") as updated,
            patch.object(live_check_service, "token_claims", return_value={"token_expired": True}),
            patch.object(
                live_check_service,
                "check_account_plan",
                return_value={"ok": False, "token_expired": True, "http_status": 401, "error": "AT expired"},
            ) as probe,
            patch.object(live_check_service, "check_account_liveness") as email_login,
            patch.object(live_check_service, "_append_log"),
            patch("core.account_proxy.acquire_account_proxy", return_value=route),
            patch.object(live_check_service._QUEUE_SLOTS, "release"),
        ):
            result = live_check_service._run_live_check(
                account_id=85,
                email="first@example.com",
                proxy="http://fresh.example:8080",
                trigger="manual",
            )

        self.assertFalse(result["ok"])
        self.assertEqual("failed", result["status"])
        self.assertEqual(401, result["http_status"])
        self.assertIn("刷新AT", result["error"])
        probe.assert_called_once_with(
            "expired-token",
            proxy="http://fresh.example:8080",
            max_attempts=1,
        )
        email_login.assert_not_called()
        self.assertNotIn("access_token", updated.call_args.args[1])
        self.assertEqual(401, updated.call_args.args[1]["http_status"])

    def test_ordinary_live_check_records_optional_context_without_auth_refresh(self):
        from core import live_check_service

        route = SimpleNamespace(
            proxy_url="http://fresh.example:8080",
            public_dict=lambda: {
                "proxy_mode": "1024",
                "network_route": "proxy",
                "proxy_provider": "1024proxy",
                "proxy_used": "http://fresh.example:8080",
                "proxy_region": "US",
            },
            release=MagicMock(),
        )
        with (
            patch.object(live_check_service.db, "mark_account_live_check_running", return_value=True),
            patch.object(live_check_service.db, "get_account", return_value={"access_token": "valid-token"}),
            patch.object(live_check_service.db, "update_account_liveness"),
            patch.object(live_check_service, "token_claims", return_value={"token_expired": False}),
            patch.object(
                live_check_service,
                "check_account_plan",
                return_value={"ok": True, "http_status": 200, "current_plan_type": "free"},
            ) as plan_check,
            patch.object(live_check_service, "check_account_liveness") as email_login,
            patch("core.storage.account_auth.ensure_account_protocol_identity") as ensure_identity,
            patch("core.storage.account_auth.AuthContextRecorder.from_account_action_task") as recorder,
            patch.object(live_check_service, "_append_log"),
            patch("core.account_proxy.acquire_account_proxy", return_value=route),
            patch.object(live_check_service._QUEUE_SLOTS, "release"),
            patch("config.account.ACCOUNT_AUTH_PROFILE_MODE", "account_stable"),
            patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", True),
        ):
            result = live_check_service._run_live_check(
                account_id=85,
                email="first@example.com",
                proxy=None,
                trigger="manual",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("access_token", result["validation_method"])
        ensure_identity.assert_not_called()
        recorder.assert_called_once_with(
            None,
            account_id=85,
            protocol_identity=None,
            action="live_check",
            driver="protocol_current",
        )
        self.assertIs(
            plan_check.call_args.kwargs["context_recorder"],
            recorder.return_value,
        )
        email_login.assert_not_called()

    def test_force_refresh_uses_roxy_after_protocol_login_failure(self):
        from core import live_check_service

        refreshed = {
            "ok": True,
            "status": "live",
            "access_token": "fresh-token",
            "session": {"account": {"planType": "free"}},
            "validation_method": "roxy_email_otp",
        }
        with (
            patch.object(live_check_service.db, "mark_account_live_check_running", return_value=True),
            patch.object(live_check_service.db, "get_account", return_value={"access_token": "expired-token"}),
            patch.object(live_check_service.db, "update_account_liveness") as updated,
            patch.object(live_check_service, "token_claims", return_value={"token_expired": True}),
            patch.object(
                live_check_service,
                "check_account_liveness",
                return_value={"ok": False, "status": "failed", "error": "HTTP 403"},
            ),
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service._QUEUE_SLOTS, "release"),
            patch("core.roxy_liveness.available", return_value=True),
            patch("core.roxy_liveness.refresh_access_token", return_value=refreshed) as roxy_refresh,
        ):
            result = live_check_service._run_live_check(
                account_id=85,
                email="first@example.com",
                proxy=None,
                trigger="token_refresh_manual",
                force_refresh=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual("roxy_email_otp", result["validation_method"])
        roxy_refresh.assert_called_once_with("first@example.com", proxy=None)
        self.assertEqual("fresh-token", updated.call_args.args[1]["access_token"])

    def test_roxy_liveness_reuses_saved_password_on_login_password_page(self):
        from core import roxy_liveness

        driver = MagicMock(current_url="https://auth.openai.com/log-in/password")
        with (
            patch.object(roxy_liveness, "_page_account_unusable_code", return_value=""),
            patch.object(roxy_liveness, "_type_email_address"),
            patch.object(roxy_liveness, "_submit_email_step"),
            patch.object(roxy_liveness, "_wait_email_submit_next_state", return_value="login_password"),
            patch.object(roxy_liveness, "_is_login_password_page", return_value=True),
            patch.object(roxy_liveness, "_is_email_verification_page", return_value=False),
            patch.object(roxy_liveness, "_has_access_token", return_value=False),
            patch("core.roxy_codex_oauth.complete_openai_login_challenge", return_value="advanced") as challenge,
        ):
            result = roxy_liveness._enter_existing_account_otp(
                driver,
                "account@example.com",
                password="saved-password",
                totp_secret="saved-totp",
            )

        self.assertEqual("logged_in", result)
        challenge.assert_called_once_with(
            driver,
            "account@example.com",
            "saved-password",
            "saved-totp",
            timeout=45,
        )

    def test_force_refresh_rejects_account_without_existing_access_token(self):
        from core import live_check_service

        with (
            patch.object(
                live_check_service.db,
                "get_account",
                return_value={"id": 8, "email": "pending@example.com", "access_token": ""},
            ),
            patch.object(live_check_service.db, "account_is_deactivated", return_value=False),
            patch.object(live_check_service._QUEUE_SLOTS, "acquire") as acquire_slot,
            patch.object(live_check_service.db, "claim_account_live_check", return_value=True) as claim,
            patch.object(live_check_service.account_task_store, "create_task", return_value=999),
            patch.object(live_check_service._EXECUTOR, "submit"),
        ):
            result = live_check_service.enqueue_account_live_check(
                account_id=8,
                email="pending@example.com",
                trigger="token_refresh_manual",
                force_refresh=True,
            )

        self.assertFalse(result["accepted"])
        self.assertIn("没有现有 access_token", result["error"])
        acquire_slot.assert_not_called()
        claim.assert_not_called()

    def test_protocol_v2_password_rejection_never_enters_roxy_fallback(self):
        from core import live_check_service

        route = SimpleNamespace(
            proxy_url="http://fresh.example:8080",
            public_dict=lambda: {
                "proxy_mode": "1024",
                "network_route": "proxy",
                "proxy_provider": "1024proxy",
                "proxy_used": "http://fresh.example:8080",
                "proxy_region": "US",
            },
            release=MagicMock(),
        )
        rejected = {
            "ok": False,
            "status": "failed",
            "error": "password_rejected",
            "error_category": "auth",
            "password_auth_status": "rejected",
            "roxy_fallback_allowed": False,
            "live_check_driver": "protocol_v2",
        }
        with (
            patch("config.account.ACCOUNT_AUTH_V2_ENABLED", True),
            patch.object(live_check_service.db, "mark_account_live_check_running", return_value=True),
            patch.object(live_check_service.db, "get_account", return_value={"access_token": "expired-token"}),
            patch.object(live_check_service.db, "update_account_liveness") as updated,
            patch.object(live_check_service, "token_claims", return_value={"token_expired": True}),
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service._QUEUE_SLOTS, "release"),
            patch("core.account_proxy.acquire_account_proxy", return_value=route),
            patch("core.protocol_v2_liveness.refresh_access_token", return_value=rejected),
            patch("core.roxy_liveness.available", return_value=True),
            patch("core.roxy_liveness.refresh_access_token") as roxy_refresh,
        ):
            result = live_check_service._run_live_check(
                account_id=85,
                email="first@example.com",
                proxy="",
                trigger="token_refresh_manual",
                force_refresh=True,
                refresh_driver="protocol_v2",
            )

        self.assertFalse(result["ok"])
        self.assertEqual("password_rejected", result["error"])
        self.assertEqual("protocol_v2", result["token_refresh_driver"])
        roxy_refresh.assert_not_called()
        self.assertNotIn("access_token", updated.call_args.args[1])
        route.release.assert_called_once_with(reason="live-check-85")

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
