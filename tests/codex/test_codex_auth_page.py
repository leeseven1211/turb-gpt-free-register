"""Codex selected Auth Page continuity, using a transport that never opens sockets."""
import unittest
from types import SimpleNamespace

from core.codex.auth_page import CodexAuthPageSession


HEADER = "OpenAI-Auth-Page"


class FakeSession:
    def __init__(self):
        self.session = SimpleNamespace(cookies=object())
        self.auth_headers = {"accept": "application/json", "oai-device-id": "device"}
        self.calls = []
        self.response = SimpleNamespace(
            status_code=200, url="https://auth.openai.com/email-verification",
            headers={}, history=[], json=lambda: {"continue_url": "/add-phone"},
        )

    def get_auth_headers(self, **kwargs):
        return self.auth_headers

    def get(self, url, headers=None, **kwargs):
        self.calls.append(("GET", url, headers, kwargs))
        return self.response

    def post(self, url, headers=None, **kwargs):
        self.calls.append(("POST", url, headers, kwargs))
        return self.response

    def reset_transport(self):
        self.session = SimpleNamespace(cookies=object())


class CodexAuthPageTests(unittest.TestCase):
    def setUp(self):
        self.base = FakeSession()
        self.session = CodexAuthPageSession(self.base)

    def test_cookie_only_flow_preserves_existing_request_headers(self):
        self.session.observe_url("https://auth.openai.com/log-in?state=old")
        headers = self.session.get_auth_headers(referer="https://auth.openai.com/log-in")
        self.assertEqual(headers, {"accept": "application/json", "oai-device-id": "device"})
        self.session.post("https://auth.openai.com/api/accounts/authorize/continue", headers=headers)
        self.assertEqual(self.base.calls[-1][2], headers)

    def test_selected_page_is_added_to_real_post_without_mutating_caller_headers(self):
        self.session.observe_url("/add-phone?auth_page=selected-page", source="continue")
        supplied = {"content-type": "application/json"}
        self.session.post("https://auth.openai.com/api/accounts/add-phone", headers=supplied, data="{}")
        self.assertEqual(self.base.calls[-1][2], {"content-type": "application/json", HEADER: "selected-page"})
        self.assertEqual(supplied, {"content-type": "application/json"})
        self.assertEqual(self.base.calls[-1][3], {"data": "{}"})
        self.assertNotIn(HEADER, self.base.auth_headers)

    def test_shared_mfa_helper_uses_selected_page_on_the_same_transport(self):
        from core.accounts.liveness.protocol.v2 import _mfa_verify

        self.session.observe_url("/mfa-challenge?auth_page=mfa-page")
        result = _mfa_verify(self.session, "factor", "123456")
        self.assertEqual(result, {"continue_url": "/add-phone"})
        self.assertEqual(self.base.calls[-1][1], "https://auth.openai.com/api/accounts/mfa/verify")
        self.assertEqual(self.base.calls[-1][2][HEADER], "mfa-page")

    def test_relative_continue_rotates_and_explicit_empty_clears(self):
        self.session.observe_url("/log-in?auth_page=initial")
        self.session.observe_payload({"continue_url": "/add-phone?auth_page=rotated"})
        self.assertEqual(self.session.get_auth_headers()[HEADER], "rotated")
        self.session.observe_payload({"page": {"continue_url": "/add-phone?auth_page="}})
        self.assertNotIn(HEADER, self.session.get_auth_headers())

    def test_api_and_parameterless_pages_do_not_clear_or_replace_selection(self):
        self.session.observe_url("/log-in?auth_page=selected")
        for url in ("/email-verification", "/api/accounts/continue?auth_page=api-value",
                    "/authorize?auth_page=entry", "/oauth/authorize?auth_page=entry",
                    "https://evil.test/add-phone?auth_page=external",
                    "/add-phone?auth_page=one&auth_page=two"):
            with self.subTest(url=url):
                self.session.observe_url(url)
                self.assertEqual(self.session.get_auth_headers()[HEADER], "selected")

    def test_untrusted_or_ambiguous_urls_never_select_a_header(self):
        for url in (
            "https://evil.test/add-phone?auth_page=secret",
            "//evil.test/add-phone?auth_page=secret",
            "http://auth.openai.com/add-phone?auth_page=secret",
            "https://auth.openai.com:444/add-phone?auth_page=secret",
            "https://user@auth.openai.com/add-phone?auth_page=secret",
            "http://localhost:1455/auth/callback?auth_page=secret",
            "https://auth.openai.com.evil.test/add-phone?auth_page=secret",
            "/add-phone?auth_page=one&auth_page=two",
            "/add-phone?auth_page=bad%0D%0AX-Injected%3Ayes",
            "/add-phone?auth_page=bad\r\nInjected",
            "/api%2faccounts/continue?auth_page=api-value",
            "https://auth.openai.com//api/accounts/continue?auth_page=api-value",
            "https://auth.openai.com/%2fapi/accounts/continue?auth_page=api-value",
            "https://auth.openai.com\\@evil.test/add-phone?auth_page=secret",
        ):
            with self.subTest(url=url):
                session = CodexAuthPageSession(FakeSession())
                session.observe_url(url)
                self.assertNotIn(HEADER, session.get_auth_headers())

    def test_non_account_targets_do_not_receive_even_a_caller_supplied_header(self):
        self.session.observe_url("/add-phone?auth_page=selected")
        for url in ("https://evil.test/api/accounts/add-phone",
                    "http://auth.openai.com/api/accounts/add-phone",
                    "https://auth.openai.com:444/api/accounts/add-phone",
                    "https://auth.openai.com/oauth/token",
                    "https://auth.openai.com/api/accounts/../oauth/token",
                    "https://auth.openai.com/api/accounts.evil/add-phone"):
            with self.subTest(url=url):
                self.session.post(url, headers={"openai-auth-page": "caller-secret", "accept": "*/*"})
                self.assertEqual(self.base.calls[-1][2], {"accept": "*/*"})

    def test_navigation_observes_requested_and_redirected_document_without_extra_gets(self):
        self.session.get("https://auth.openai.com/log-in?auth_page=requested", allow_redirects=True)
        self.assertEqual(self.session.get_auth_headers()[HEADER], "requested")
        self.base.response = SimpleNamespace(
            url="https://auth.openai.com/add-phone", headers={}, history=[SimpleNamespace(
                url="https://auth.openai.com/api/accounts/continue",
                headers={"Location": "/add-phone?auth_page=redirected"},
            )],
        )
        self.session.get("https://auth.openai.com/api/accounts/continue")
        self.assertEqual(self.session.get_auth_headers()[HEADER], "redirected")
        self.assertEqual(len(self.base.calls), 2)
        self.assertEqual(self.base.calls[0][3], {"allow_redirects": True})

    def test_get_does_not_leak_action_header_or_trust_external_response_location(self):
        self.session.observe_url("/add-phone?auth_page=selected")
        self.base.response = SimpleNamespace(
            url="https://evil.test/", headers={"location": "/add-phone?auth_page=external"}, history=[],
        )
        self.session.get("https://evil.test/", headers=self.session.get_auth_headers())
        self.assertNotIn(HEADER, self.base.calls[-1][2])
        self.assertEqual(self.session.get_auth_headers()[HEADER], "selected")

    def test_query_only_location_stays_on_its_api_route_and_cannot_select_page(self):
        self.session.observe_url("/add-phone?auth_page=selected")
        self.base.response = SimpleNamespace(
            url="https://auth.openai.com/api/accounts/continue", headers={"location": "?auth_page=api-value"}, history=[],
        )
        self.session.get("https://auth.openai.com/api/accounts/continue")
        self.assertEqual(self.session.get_auth_headers()[HEADER], "selected")

    def test_parameterless_document_has_safe_presence_diagnostic(self):
        with self.assertLogs("core.codex_oauth", level="INFO") as captured:
            self.session.observe_url("/log-in?state=private-state", source="bootstrap")
        diagnostic = "\n".join(captured.output)
        self.assertIn("source=bootstrap", diagnostic)
        self.assertIn("auth_page_present=False", diagnostic)
        self.assertIn("has_auth_page=False", diagnostic)
        self.assertNotIn("private-state", diagnostic)

    def test_session_state_does_not_cross_accounts_or_shadow_base_attributes(self):
        other = CodexAuthPageSession(FakeSession())
        self.session.observe_url("/add-phone?auth_page=one-account")
        self.assertNotIn(HEADER, other.get_auth_headers())
        self.assertIs(self.session.session, self.base.session)
        self.session._codex_auth_session_payload = {"workspaces": []}
        self.assertEqual(self.base._codex_auth_session_payload, {"workspaces": []})
        self.session.reset_transport()
        self.assertIs(self.session.session, self.base.session)
        self.assertEqual(self.session.get_auth_headers()[HEADER], "one-account")

    def test_diagnostics_only_contain_fixed_source_and_presence_flags(self):
        with self.assertLogs("core.codex_oauth", level="INFO") as captured:
            self.session.observe_url(
                "/add-phone?auth_page=synthetic-secret-auth-page&password=pw-secret&otp=987654",
                source="source-cookie-token-secret",
            )
            self.session.post("https://auth.openai.com/api/accounts/add-phone", headers={"cookie": "cookie-secret"})
        diagnostic = "\n".join(captured.output)
        for secret in ("synthetic-secret-auth-page", "source-cookie-token-secret", "pw-secret", "987654", "cookie-secret"):
            self.assertNotIn(secret, diagnostic)
        self.assertIn("source=unknown", diagnostic)
        self.assertIn("auth_page_present=True", diagnostic)
        self.assertIn("has_auth_page=True", diagnostic)
        self.assertIn("changed=True", diagnostic)
        self.assertIn("header_present=True", diagnostic)


if __name__ == "__main__":
    unittest.main()
