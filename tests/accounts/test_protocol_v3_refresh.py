# -*- coding: utf-8 -*-
"""V3 contract tests; HTTP, mailbox and private storage stay offline."""
import json
import base64
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from requests.cookies import RequestsCookieJar


EMAIL = "v3@example.test"
AUTH = "https://auth.openai.com"
CHAT = "https://chatgpt.com"
SESSION = {"accessToken": "fixture-at", "user": {"email": EMAIL, "id": "u-1"},
           "account": {"id": "a-1", "planType": "free"}}


class Response:
    def __init__(self, payload=None, status=200, location=None):
        self.payload = payload
        self.status_code = status
        self.headers = {"location": location} if location else {}
        self.text = json.dumps(payload or {})
        self.url = ""

    def json(self):
        return self.payload


class Session:
    def __init__(self, landing="/log-in/password", routes=None, **kwargs):
        self.proxy = kwargs.get("proxy", "")
        self.device_id = "fixture-device"
        self.browser_profile = {"screen_width": 1920, "screen_height": 1080,
                                "device_pixel_ratio": 1, "hardware_concurrency": 8,
                                "device_memory": 8, "js_heap_size_limit": 4096000000}
        self.session = SimpleNamespace(cookies=RequestsCookieJar(), close=self.close)
        self.session.cookies.set("__Secure-next-auth.session-token", "fixture-cookie", domain="chatgpt.com", path="/")
        self.routes = {("GET", AUTH + "/authorize/start"): Response(status=302, location=AUTH + landing),
                       ("GET", AUTH + landing): Response({}),
                       ("GET", CHAT + "/api/auth/session"): Response(SESSION),
                       ("GET", CHAT + "/api/auth/callback/openai"): Response({})}
        self.routes.update(routes or {})
        self.calls = []
        self.closed = False

    def close(self):
        self.closed = True

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        value = self.routes.get((method, url))
        if value is None:
            raise AssertionError(f"Unexpected fixture request: {method} {url}")
        if isinstance(value, Exception):
            raise value
        value.url = url
        return value

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def get_auth_headers(self, **kwargs):
        return {}

    get_auth_navigate_headers = get_auth_headers
    get_chatgpt_navigate_headers = get_auth_headers
    get_nextauth_headers = get_auth_headers


class ProtocolV3RefreshTests(unittest.TestCase):
    def setUp(self):
        from core.accounts.liveness.protocol import v3
        from core.accounts.liveness.protocol import v2

        self.v3 = v3
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.target = {"id": 7, "email": EMAIL, "user_id": "u-1", "chatgpt_account_id": "a-1"}
        for name in ("get_account", "get_account_by_email"):
            self.stack.enter_context(patch.object(v3.db, name, return_value=self.target))
        self.stack.enter_context(patch.object(v3, "get_account_login_credentials", return_value=("fixture-password", "JBSWY3DPEHPK3PXP")))
        self.stack.enter_context(patch.object(v3, "account_email_is_invalid", return_value=False))
        self.stack.enter_context(patch.object(v2, "request_sentinel_token", return_value={}))
        self.stack.enter_context(patch.object(v2, "build_sentinel_header", return_value=("fixture", None)))
        self.stack.enter_context(patch.object(v3, "_totp_code", return_value="123456"))
        self.stack.enter_context(patch.object(v3, "wait_for_otp", return_value="654321"))
        self.stack.enter_context(patch.object(v3, "send_email_otp"))
        self.load = self.stack.enter_context(patch.object(v3.protocol_sessions, "load_session", return_value=None))
        self.save = self.stack.enter_context(patch.object(v3.protocol_sessions, "save_session"))
        self.stack.enter_context(patch.object(v3.protocol_sessions, "invalidate_session"))

    def run_flow(self, session, **kwargs):
        with patch.object(self.v3, "_network_preflight_with_retry", return_value=(session, AUTH + "/authorize/start")):
            return self.v3.refresh_access_token(EMAIL, account_id=7, proxy="", **kwargs)

    def test_password_email_and_nested_mfa_challenges_complete_in_order(self):
        session = Session(routes={
            ("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": AUTH + "/email-verification"}),
            ("POST", AUTH + "/api/accounts/email-otp/validate"): Response({"page": {"type": "mfa_challenge"}, "oai-client-auth-session": {"mfa_challenge_factors": [{"id": "factor-1", "factor_type": "totp"}]}}),
            ("POST", AUTH + "/api/accounts/mfa/issue_challenge"): Response({}),
            ("POST", AUTH + "/api/accounts/mfa/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
        })
        result = self.run_flow(session)
        self.assertTrue(result["ok"], result)
        self.assertEqual("protocol_v3", result["live_check_driver"])
        self.assertEqual("password_email_otp_mfa", result["auth_method"])
        self.assertEqual(["/api/accounts/password/verify", "/api/accounts/email-otp/validate", "/api/accounts/mfa/issue_challenge", "/api/accounts/mfa/verify"],
                         [url.removeprefix(AUTH) for method, url, _ in session.calls if method == "POST"])
        self.assertTrue(session.closed)

    def test_direct_mfa_uses_factor_from_url(self):
        session = Session(landing="/mfa-challenge/factor-2", routes={
            ("POST", AUTH + "/api/accounts/mfa/issue_challenge"): Response({}),
            ("POST", AUTH + "/api/accounts/mfa/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
        })
        self.assertTrue(self.run_flow(session)["ok"])

    def test_workspace_selection_uses_target_account_not_first_workspace(self):
        session = Session(routes={
            ("POST", AUTH + "/api/accounts/password/verify"): Response({"page": {"type": "workspace"}, "oai-client-auth-session": {"workspaces": [{"id": "a-other"}, {"id": "a-1"}]}}),
            ("POST", AUTH + "/api/accounts/workspace/select"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
        })
        result = self.run_flow(session)
        self.assertTrue(result["ok"], result)
        submitted = [json.loads(kw["data"]) for method, url, kw in session.calls if url.endswith("workspace/select")]
        self.assertEqual([{"workspace_id": "a-1"}], submitted)

    def test_ambiguous_workspaces_do_not_guess(self):
        session = Session(routes={
            ("POST", AUTH + "/api/accounts/password/verify"): Response({"page": {"type": "workspace"}, "oai-client-auth-session": {"workspaces": [{"id": "other-1"}, {"id": "other-2"}]}}),
        })
        self.assertEqual("workspace_ambiguous", self.run_flow(session)["error"])

    def test_profile_page_is_rejected_without_creating_account(self):
        session = Session(landing="/about-you")
        self.assertEqual("account_profile_required", self.run_flow(session)["error"])
        self.assertFalse(any(method == "POST" for method, _, _ in session.calls))

    def test_mismatched_returned_identity_is_not_saved(self):
        session = Session(landing="/email-verification", routes={
            ("POST", AUTH + "/api/accounts/email-otp/validate"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
            ("GET", CHAT + "/api/auth/session"): Response({**SESSION, "user": {"email": "other@example.test", "id": "other"}}),
        })
        self.assertEqual("identity_mismatch", self.run_flow(session)["error"])
        self.assertFalse(self.save.called)

    def test_untrusted_continue_url_is_not_requested(self):
        session = Session(routes={
            ("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": "https://evil.example.test/steal"}),
        })
        self.assertEqual("untrusted_auth_url", self.run_flow(session)["error"])
        self.assertFalse(any("evil." in url for _, url, _ in session.calls))

    def test_unknown_password_submission_does_not_send_otp_or_retry(self):
        session = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): TimeoutError("fixture secret must stay private")})
        result = self.run_flow(session)
        self.assertEqual("password_result_unknown", result["error"])
        self.assertTrue(result["reconcile_required"])
        self.assertFalse(result["roxy_fallback_allowed"])
        self.assertEqual(1, len([item for item in session.calls if item[0] == "POST"]))
        self.assertNotIn("fixture secret", json.dumps(result))

    def cache(self):
        return {"cookies": [{"name": "__Secure-next-auth.session-token", "value": "fixture-cached", "domain": "chatgpt.com", "path": "/", "secure": True}],
                "device_id": "fixture-device", "browser_profile": Session().browser_profile,
                "user_id": "u-1", "chatgpt_account_id": "a-1"}

    def test_valid_cached_session_returns_at_without_authentication(self):
        self.load.return_value = self.cache()
        cached = Session()
        with patch.object(self.v3, "BrowserSession", return_value=cached), patch.object(self.v3, "_network_preflight_with_retry", side_effect=AssertionError("must not login")):
            result = self.v3.refresh_access_token(EMAIL, account_id=7, proxy="")
        self.assertTrue(result["ok"], result)
        self.assertEqual("session_cookie", result["auth_method"])
        self.assertTrue(result["session_reused"])
        self.assertEqual([("GET", CHAT + "/api/auth/session")], [(m, u) for m, u, _ in cached.calls])

    def test_cache_network_failure_does_not_start_fresh_login(self):
        self.load.return_value = self.cache()
        cached = Session(routes={("GET", CHAT + "/api/auth/session"): TimeoutError("secret-url")})
        with patch.object(self.v3, "BrowserSession", return_value=cached), patch.object(self.v3, "_network_preflight_with_retry", side_effect=AssertionError("must not login")):
            result = self.v3.refresh_access_token(EMAIL, account_id=7, proxy="")
        self.assertEqual("cached_session_network_failed", result["error"])
        self.assertFalse(result["remote_request_started"])
        self.assertNotIn("secret-url", json.dumps(result))

    def test_explicitly_expired_cache_uses_clean_new_session(self):
        self.load.return_value = self.cache()
        cached = Session(routes={("GET", CHAT + "/api/auth/session"): Response({}, status=401)})
        fresh = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"})})
        with patch.object(self.v3, "BrowserSession", return_value=cached):
            result = self.run_flow(fresh)
        self.assertTrue(result["ok"], result)
        self.assertTrue(cached.closed)
        self.assertEqual("fixture-cookie", fresh.session.cookies.get("__Secure-next-auth.session-token"))

    def test_cache_storage_failure_preserves_success_and_live_callback(self):
        self.save.side_effect = RuntimeError("private-storage-secret")
        session = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"})})
        def callback(result, active_session):
            self.assertFalse(active_session.closed)
            return {**result, "callback_completed": True}
        result = self.run_flow(session, on_authenticated=callback)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["callback_completed"])
        self.assertEqual("unavailable", result["session_cache_status"])
        self.assertNotIn("private-storage-secret", json.dumps(result))

    def test_cached_proxy_acquisition_error_never_starts_new_login(self):
        self.load.return_value = self.cache()
        with patch.object(self.v3, "_network_preflight_with_retry", side_effect=AssertionError("must not login")) as fresh:
            result = self.v3.refresh_access_token(EMAIL, account_id=7, proxy_supplier=lambda _: (_ for _ in ()).throw(TimeoutError("private-route")))
        self.assertEqual("cached_session_network_failed", result["error"])
        self.assertFalse(fresh.called)

    def test_cached_http_error_is_not_treated_as_expired_cookie(self):
        for status in (403, 429, 500):
            with self.subTest(status=status):
                self.load.return_value = self.cache()
                cached = Session(routes={("GET", CHAT + "/api/auth/session"): Response({}, status=status)})
                with patch.object(self.v3, "BrowserSession", return_value=cached), patch.object(self.v3, "_network_preflight_with_retry", side_effect=AssertionError("must not login")):
                    result = self.v3.refresh_access_token(EMAIL, account_id=7, proxy="")
                self.assertEqual("cached_session_http_failed", result["error"])

    def test_access_token_claim_identity_cannot_disagree_with_session(self):
        claims = {"https://api.openai.com/auth": {"chatgpt_user_id": "different-user", "chatgpt_account_id": "a-1"}}
        segment = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        session = Session(routes={
            ("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
            ("GET", CHAT + "/api/auth/session"): Response({**SESSION, "accessToken": "fixture." + segment + ".signature"}),
        })
        self.assertEqual("identity_mismatch", self.run_flow(session)["error"])

    def test_cached_identity_ids_are_checked_even_when_account_has_no_saved_ids(self):
        self.target.pop("user_id")
        self.target.pop("chatgpt_account_id")
        self.load.return_value = self.cache()
        cached = Session(routes={("GET", CHAT + "/api/auth/session"): Response({**SESSION, "user": {"email": EMAIL, "id": "other"}})})
        fresh = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"})})
        with patch.object(self.v3, "BrowserSession", return_value=cached):
            result = self.run_flow(fresh)
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["session_reused"])

    def test_callback_redirect_to_third_party_is_never_followed(self):
        session = Session(routes={
            ("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
            ("GET", CHAT + "/api/auth/callback/openai"): Response(status=302, location="https://evil.example.test/"),
        })
        self.assertEqual("untrusted_auth_url", self.run_flow(session)["error"])

    def test_repeated_challenge_stops_after_one_password_submit(self):
        session = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": AUTH + "/log-in/password"})})
        self.assertEqual("auth_challenge_loop", self.run_flow(session)["error"])
        self.assertEqual(1, len([item for item in session.calls if item[0] == "POST"]))

    def test_cache_payload_contains_only_trusted_cookies_and_no_route_secrets(self):
        session = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"})})
        session.session.cookies.set("third-party", "not-allowed", domain="evil.example.test", path="/")
        session.browser_profile["script_src_samples"] = ["https://evil.example.test/script?secret=yes"]
        self.assertTrue(self.run_flow(session)["ok"])
        payload = self.save.call_args.args[2]
        self.assertNotIn("evil.example.test", json.dumps(payload))
        self.assertNotIn("proxy", payload)

    def test_cancelled_callback_propagates_without_becoming_auth_failure(self):
        from core.operations.runtime import OperationCancelled
        session = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"})})
        with self.assertRaises(OperationCancelled):
            self.run_flow(session, on_authenticated=lambda *_: (_ for _ in ()).throw(OperationCancelled("stopped")))
        self.assertTrue(session.closed)

    def test_context_cleanup_failure_does_not_discard_valid_at(self):
        from unittest.mock import Mock
        session = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"})})
        recorder = Mock()
        recorder.finish_session.side_effect = RuntimeError("private-diagnostic-data")
        result = self.run_flow(session, context_recorder=recorder)
        self.assertTrue(result["ok"], result)
        self.assertTrue(session.closed)

    def test_cached_transport_setup_failure_does_not_start_new_login(self):
        self.load.return_value = self.cache()
        with patch.object(self.v3, "BrowserSession", side_effect=ConnectionError("private-route")), patch.object(self.v3, "_network_preflight_with_retry", side_effect=AssertionError("must not login")) as fresh:
            result = self.v3.refresh_access_token(EMAIL, account_id=7, proxy="")
        self.assertEqual("cached_session_network_failed", result["error"])
        self.assertFalse(fresh.called)

    def test_invalid_email_can_use_server_offered_password_route(self):
        self.stack.enter_context(patch.object(self.v3, "account_email_is_invalid", return_value=True))
        session = Session(landing="/email-verification", routes={
            ("GET", AUTH + "/email-verification"): Response({}),
            ("GET", AUTH + "/log-in/password"): Response({}),
            ("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
        })
        self.assertTrue(self.run_flow(session)["ok"])

    def test_real_curl_cookie_container_can_restore_expiring_cache(self):
        from curl_cffi.requests import Cookies
        self.load.return_value = self.cache()
        self.load.return_value["cookies"][0]["expires"] = 4102444800
        cached = Session()
        cached.session.cookies = Cookies()
        with patch.object(self.v3, "BrowserSession", return_value=cached), patch.object(self.v3, "_network_preflight_with_retry", side_effect=AssertionError("must not login")):
            result = self.v3.refresh_access_token(EMAIL, account_id=7, proxy="")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["session_reused"])
        self.assertEqual(4102444800, next(iter(cached.session.cookies.jar)).expires)

    def test_empty_session_is_expired_but_malformed_response_is_not(self):
        fresh = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"})})
        self.load.return_value = self.cache()
        cached = Session(routes={("GET", CHAT + "/api/auth/session"): Response({})})
        with patch.object(self.v3, "BrowserSession", return_value=cached):
            self.assertTrue(self.run_flow(fresh)["ok"])
        cached = Session(routes={("GET", CHAT + "/api/auth/session"): Response(["unexpected"])})
        with patch.object(self.v3, "BrowserSession", return_value=cached), patch.object(self.v3, "_network_preflight_with_retry", side_effect=AssertionError("must not login")):
            self.assertEqual("cached_session_invalid_response", self.v3.refresh_access_token(EMAIL, account_id=7, proxy="")["error"])

    def test_corrupt_cookie_payload_is_discarded_before_clean_authentication(self):
        self.load.return_value = {**self.cache(), "cookies": [{"name": "secret", "value": "wrong", "domain": "evil.example.test"}]}
        fresh = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"})})
        cached = Session()
        with patch.object(self.v3, "BrowserSession", return_value=cached):
            result = self.run_flow(fresh)
        self.assertTrue(result["ok"])
        self.assertFalse(cached.calls)
        self.assertNotIn("wrong", str(fresh.session.cookies))

    def test_missing_target_account_stops_before_any_login(self):
        self.stack.enter_context(patch.object(self.v3.db, "get_account", return_value=None))
        with patch.object(self.v3, "_network_preflight_with_retry", side_effect=AssertionError("must not login")):
            result = self.v3.refresh_access_token(EMAIL, account_id=999, proxy="")
        self.assertEqual("account_reference_mismatch", result["error"])

    def test_missing_totp_secret_is_a_configuration_error(self):
        self.stack.enter_context(patch.object(self.v3, "get_account_login_credentials", return_value=("fixture-password", "")))
        session = Session(landing="/mfa-challenge/factor-2")
        result = self.run_flow(session)
        self.assertEqual("mfa_secret_missing", result["error"])
        self.assertFalse(any(method == "POST" for method, _, _ in session.calls))

    def test_expired_jwt_from_cached_or_fresh_session_never_returns_live(self):
        claims = {"exp": 1, "https://api.openai.com/auth": {"chatgpt_user_id": "u-1", "chatgpt_account_id": "a-1"}, "https://api.openai.com/profile": {"email": EMAIL}}
        encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        expired = {**SESSION, "accessToken": "header." + encoded + ".signature"}
        fresh = Session(routes={
            ("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
            ("GET", CHAT + "/api/auth/session"): Response(expired),
        })
        result = self.run_flow(fresh)
        self.assertFalse(result["ok"])
        self.assertEqual("access_token_expired", result["error"])
        self.assertFalse(self.save.called)
        self.load.return_value = self.cache()
        cached = Session(routes={("GET", CHAT + "/api/auth/session"): Response(expired)})
        with patch.object(self.v3, "BrowserSession", return_value=cached), patch.object(self.v3, "_network_preflight_with_retry", side_effect=AssertionError("must not login")):
            result = self.v3.refresh_access_token(EMAIL, account_id=7, proxy="")
        self.assertFalse(result["ok"])
        self.assertEqual("access_token_expired", result["error"])
        self.assertFalse(self.save.called)

    def test_direct_mfa_reads_factor_from_signed_client_auth_cookie(self):
        session = Session(landing="/mfa-challenge", routes={
            ("POST", AUTH + "/api/accounts/mfa/issue_challenge"): Response({}),
            ("POST", AUTH + "/api/accounts/mfa/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
        })
        context = {"mfa_challenge_factors": [{"id": "cookie-factor", "factor_type": "totp"}]}
        encoded = base64.urlsafe_b64encode(json.dumps(context).encode()).decode().rstrip("=")
        session.session.cookies.set("oai-client-auth-session", encoded + ".signature", domain="auth.openai.com", path="/")
        result = self.run_flow(session)
        self.assertTrue(result["ok"], result)
        issue = [json.loads(kw["data"]) for _, url, kw in session.calls if url.endswith("issue_challenge")]
        self.assertEqual("cookie-factor", issue[0]["id"])

    def test_workspace_reads_candidates_from_urlencoded_jwt_client_auth_cookie(self):
        from urllib.parse import quote
        session = Session(landing="/workspace", routes={
            ("POST", AUTH + "/api/accounts/workspace/select"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
        })
        context = {"workspaces": [{"id": "other"}, {"id": "a-1"}]}
        encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
        session.session.cookies.set("oai-client-auth-session", quote(encode({"alg": "HS256"}) + "." + encode(context) + ".signature"), domain="auth.openai.com", path="/")
        result = self.run_flow(session)
        self.assertTrue(result["ok"], result)
        submitted = [json.loads(kw["data"]) for _, url, kw in session.calls if url.endswith("workspace/select")]
        self.assertEqual([{"workspace_id": "a-1"}], submitted)

    def test_v2_helpers_do_not_swallow_cancel_or_lease_control_exceptions(self):
        from core.accounts.liveness.protocol import v2
        from core.operations.runtime import OperationCancelled
        from core.operations.task_gateway import OperationLeaseLost
        for exception in (OperationCancelled, OperationLeaseLost):
            for boundary in ("sentinel", "password_post", "email_post", "mfa_post", "workspace_post"):
                with self.subTest(exception=exception.__name__, boundary=boundary), ExitStack() as stack:
                    control = exception("control-signal")
                    if boundary == "email_post":
                        session = Session(landing="/email-verification", routes={("POST", AUTH + "/api/accounts/email-otp/validate"): control})
                    elif boundary == "mfa_post":
                        session = Session(landing="/mfa-challenge/factor", routes={("POST", AUTH + "/api/accounts/mfa/issue_challenge"): control})
                    elif boundary == "workspace_post":
                        session = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): Response({"page": {"type": "workspace"}, "oai-client-auth-session": {"workspaces": [{"id": "a-1"}]}}), ("POST", AUTH + "/api/accounts/workspace/select"): control})
                    else:
                        session = Session(routes={("POST", AUTH + "/api/accounts/password/verify"): control})
                    if boundary == "sentinel":
                        stack.enter_context(patch.object(v2, "request_sentinel_token", side_effect=control))
                    with self.assertRaises(exception) as raised:
                        self.run_flow(session)
                    self.assertIs(control, raised.exception)
                    self.assertTrue(session.closed)

    def test_mfa_rejection_preserves_verified_password_and_email_stages(self):
        session = Session(routes={
            ("POST", AUTH + "/api/accounts/password/verify"): Response({"continue_url": AUTH + "/email-verification"}),
            ("POST", AUTH + "/api/accounts/email-otp/validate"): Response({"page": {"type": "mfa_challenge"}, "oai-client-auth-session": {"mfa_challenge_factors": [{"id": "factor-1", "factor_type": "totp"}]}}),
            ("POST", AUTH + "/api/accounts/mfa/issue_challenge"): Response({}),
            ("POST", AUTH + "/api/accounts/mfa/verify"): Response({"error": "invalid code"}, status=400),
        })
        result = self.run_flow(session)
        self.assertFalse(result["ok"])
        self.assertEqual("mfa_rejected", result["error"])
        self.assertEqual("verified", result["password_auth_status"])
        self.assertEqual("success", result["email_otp_status"])
        self.assertEqual("failed", result["mfa_status"])
        self.assertEqual("password_email_otp_mfa", result["auth_method"])
        self.assertEqual(["password", "email_otp", "totp"], result["auth"]["challenge_chain"])

    def test_session_fetch_failure_does_not_erase_completed_mfa(self):
        session = Session(landing="/mfa-challenge/factor", routes={
            ("POST", AUTH + "/api/accounts/mfa/issue_challenge"): Response({}),
            ("POST", AUTH + "/api/accounts/mfa/verify"): Response({"continue_url": CHAT + "/api/auth/callback/openai"}),
            ("GET", CHAT + "/api/auth/session"): Response({}, status=503),
        })
        result = self.run_flow(session)
        self.assertFalse(result["ok"])
        self.assertEqual("session_fetch_failed", result["error"])
        self.assertEqual("success", result["mfa_status"])
        self.assertEqual("skipped", result["password_auth_status"])
