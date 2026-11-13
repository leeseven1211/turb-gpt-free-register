"""一次只读 Codex 会话诊断的本地传输契约。"""
import base64
import json
import unittest
from http.cookiejar import Cookie, CookieJar
from types import SimpleNamespace
from urllib.parse import quote

from core.codex.session_diagnostics import CodexDiagnosticSession, safe_session_diagnostics


ORIGIN = "https://auth.openai.com"
DUMP = ORIGIN + "/api/accounts/client_auth_session_dump"


def cookie(name, value, domain="auth.openai.com", path="/"):
    return Cookie(0, name, value, None, False, domain, True, domain.startswith("."), path, True, True, None, True, None, None, {})


def response(payload, status=200, url=ORIGIN + "/api/accounts/mfa/verify"):
    def parsed():
        if isinstance(payload, Exception):
            raise payload
        return payload
    return SimpleNamespace(status_code=status, url=url, headers={}, history=[], json=parsed)


class FakeSession:
    def __init__(self):
        self.session = SimpleNamespace(cookies=SimpleNamespace(jar=CookieJar()))
        self.document_navigation_id = "synthetic-document-id"
        self.calls = []
        self.next_response = response({"page": {"type": "add_phone"}, "continue_url": "/add-phone"})
        self.error = None
        self.headers = {"accept": "application/json", "content-type": "application/json", "Authorization": "secret-auth",
                        "OpenAI-Sentinel-Token": "secret-sentinel", "x-openai-document-navigation-id": self.document_navigation_id}

    def get_auth_headers(self, **kwargs):
        return self.headers

    def get(self, url, headers=None, **kwargs):
        self.calls.append(("GET", url, headers, kwargs))
        if self.error:
            raise self.error
        return self.next_response

    def post(self, url, headers=None, **kwargs):
        self.calls.append(("POST", url, headers, kwargs))
        if self.error:
            raise self.error
        return self.next_response


class CodexSessionDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.base = FakeSession()
        self.session = CodexDiagnosticSession(self.base)

    def verify_mfa(self):
        self.session.post(ORIGIN + "/api/accounts/mfa/verify", headers={}, data="{}", allow_redirects=False)

    def test_observing_existing_stages_keeps_requests_and_cookie_owner(self):
        self.session.get(ORIGIN + "/oauth/authorize?state=private-state", allow_redirects=True)
        self.session.post(ORIGIN + "/api/accounts/password/verify", data="private-password")
        self.session.post(ORIGIN + "/api/accounts/mfa/issue_challenge", data="factor-secret")
        self.verify_mfa()
        state = self.session.snapshot()
        self.assertEqual(set(state["stages"]), {"bootstrap", "primary_verify", "mfa_issue", "mfa_verify"})
        self.assertTrue(all(item["http_status"] == 200 for item in state["stages"].values()))
        self.assertTrue(state["mfa_verified"])
        self.assertEqual(len(self.base.calls), 4)
        self.assertIs(self.session.session, self.base.session)
        self.session._codex_auth_session_payload = {"workspaces": []}
        self.assertEqual(self.base._codex_auth_session_payload, {"workspaces": []})

    def test_mfa_requires_successful_known_next_step(self):
        for payload, status, expected in (
            ({"page": {"type": "add_phone"}}, 200, True),
            ({"continue_url": "/add-phone"}, 200, True),
            ({"continue_url": "http://localhost:1455/auth/callback?code=private-code&state=private-state"}, 200, True),
            ({"page": {"type": "mfa_challenge"}, "continue_url": "/mfa-challenge"}, 200, False),
            ({"page": {"type": "unknown-private-value"}}, 200, False),
            ({"page": {"type": "add_phone"}}, 409, False),
            ({"error": "private-error"}, 200, False),
            (ValueError("private-body"), 200, False),
        ):
            with self.subTest(status=status, expected=expected):
                session = CodexDiagnosticSession(self.base)
                self.base.next_response = response(payload, status)
                session.post(ORIGIN + "/api/accounts/mfa/verify")
                self.assertEqual(session.mfa_verified, expected)

    def test_dump_is_one_get_on_original_transport_and_uses_selected_auth_page(self):
        self.session.observe_url("/add-phone?auth_page=private-page")
        self.verify_mfa()
        self.base.next_response = response({"client_auth_session": {}, "checksum": "private-checksum", "session_id": "private-session"}, url=DUMP)
        result = self.session.collect_after_mfa()
        repeated = self.session.collect_after_mfa()
        self.assertEqual(result, repeated)
        self.assertEqual(len(self.base.calls), 2)
        method, url, headers, kwargs = self.base.calls[-1]
        self.assertEqual((method, url, kwargs), ("GET", DUMP, {"allow_redirects": False}))
        self.assertEqual(headers["OpenAI-Auth-Page"], "private-page")
        self.assertEqual(headers["x-openai-document-navigation-id"], "synthetic-document-id")
        self.assertTrue(headers["x-access-flow-invocation-id"])
        self.assertFalse({key.lower() for key in headers} & {"authorization", "content-type", "openai-sentinel-token"})
        self.assertTrue(result["dump_attempted"])
        self.assertTrue(result["dump_response_received"])
        self.assertEqual(result["dump_http_status"], 200)
        self.assertNotIn("private-checksum", json.dumps(result))

    def test_cookie_and_session_changes_are_only_reported_as_flags(self):
        jar = self.base.session.cookies.jar
        jar.set_cookie(cookie("oai-client-auth-session", "cookie-secret-one"))
        jar.set_cookie(cookie("unknown-cookie-secret-name", "cookie-secret-two", "dynamic.secret.test", "/private-path"))
        self.base.next_response = response({"session_id": "session-one", "checksum": "checksum-one"})
        self.session.post(ORIGIN + "/api/accounts/password/verify")
        jar.set_cookie(cookie("oai-client-auth-session", "cookie-secret-rotated"))
        self.base.next_response = response({"page": {"type": "add_phone"}, "session_id": "session-two", "checksum": "checksum-two"})
        self.verify_mfa()
        state = self.session.snapshot()
        stage = state["stages"]["mfa_verify"]
        self.assertTrue(stage["session_id_changed"])
        self.assertTrue(stage["checksum_changed"])
        self.assertTrue(stage["jar_changed"])
        self.assertEqual(stage["jar_count"], 2)
        self.assertEqual(stage["auth_path_jar_count"], 1)
        self.assertTrue(stage["known_jar_presence"]["client_state"])
        serialized = json.dumps(state)
        for secret in ("cookie-secret", "unknown-cookie-secret-name", "dynamic.secret.test", "/private-path", "session-one", "session-two", "checksum-one", "checksum-two"):
            self.assertNotIn(secret, serialized)

    def test_dump_failure_has_no_retry_or_exception_text(self):
        self.verify_mfa()
        self.base.error = RuntimeError("secret-token-cookie-password-otp")
        result = self.session.collect_after_mfa()
        self.session.collect_after_mfa()
        self.assertEqual(len(self.base.calls), 2)
        self.assertEqual(result["dump_failure_kind"], "transport_error")
        self.assertFalse(result["dump_response_received"])
        self.assertNotIn("secret-token-cookie-password-otp", json.dumps(result))

    def test_dump_requires_known_top_level_schema_and_never_retries_invalid_results(self):
        for payload, status, expected in (
            ({"client_auth_session": {}}, 200, "unknown_schema"),
            ({"client_auth_session": {}, "checksum": 42, "session_id": None}, 200, "unknown_schema"),
            (ValueError("private-body"), 200, "invalid_json"),
            ({"error": "private-error"}, 409, "http_error"),
        ):
            with self.subTest(status=status, expected=expected):
                base = FakeSession()
                session = CodexDiagnosticSession(base)
                session.post(ORIGIN + "/api/accounts/mfa/verify")
                base.next_response = response(payload, status, DUMP)
                result = session.collect_after_mfa()
                session.collect_after_mfa()
                self.assertEqual(result["dump_failure_kind"], expected)
                self.assertEqual(len(base.calls), 2)
                self.assertNotIn("private-", json.dumps(result))

    def test_collect_without_verified_mfa_never_requests_or_later_retries(self):
        result = self.session.collect_after_mfa()
        self.assertEqual(result["dump_failure_kind"], "mfa_unconfirmed")
        self.assertFalse(result["dump_attempted"])
        self.assertEqual(self.base.calls, [])
        self.verify_mfa()
        self.session.collect_after_mfa()
        self.assertEqual(len(self.base.calls), 1)

    def test_unknown_dump_schema_and_untrusted_requests_cannot_leak_values_or_set_mfa(self):
        self.session.post("https://evil.example.test/api/accounts/mfa/verify")
        self.assertFalse(self.session.mfa_verified)
        self.verify_mfa()
        self.base.next_response = response({"raw-private-key": {"access_token": "secret-token"}}, url=DUMP)
        result = self.session.collect_after_mfa()
        self.assertEqual(result["dump_failure_kind"], "unknown_schema")
        self.assertFalse(any(result["dump"]["known_key_flags"].values()))
        self.assertNotIn("raw-private-key", json.dumps(result))
        self.assertNotIn("secret-token", json.dumps(result))

    def test_dump_exposes_known_cas_flags_and_checksum_comparison_without_free_strings(self):
        self.verify_mfa()
        encoded = base64.b64encode(json.dumps({"cs": "private-checksum"}).encode()).decode()
        self.base.session.cookies.jar.set_cookie(cookie(
            "auth-session-minimized-client-checksum", quote(json.dumps({"affinity": encoded})),
        ))
        self.base.next_response = response({
            "client_auth_session": {
                "session_id": "private-session", "auth_session_logging_id": "private-logging-id",
                "email_verified": True, "username_verified": False, "phone_number_verified": False,
                "set_phone_number_verified": False, "multi_channel_allowed": True,
                "email_verification_mode": "private-mode-one", "phone_verification_mode": "private-mode-two",
                "phone_verification_channel": "sms", "set_phone_verification_channel": "private-channel",
                "unknown-private-key": "private-cas-body",
            }, "checksum": "private-checksum", "session_id": "private-session",
        }, url=DUMP)
        result = self.session.collect_after_mfa()
        cas = result["dump"]["client_auth_session"]
        self.assertTrue(cas["email_verified"])
        self.assertFalse(cas["username_verified"])
        self.assertTrue(cas["username_verified_present"])
        self.assertTrue(cas["email_verification_mode_present"])
        self.assertTrue(cas["phone_verification_mode_present"])
        self.assertEqual(cas["phone_verification_channel"], "sms")
        self.assertEqual(cas["set_phone_verification_channel"], "other")
        self.assertTrue(result["dump"]["dump_checksum_matches_jar"])
        self.assertTrue(result["dump"]["session_id_matches_nested"])
        self.assertNotIn("private-", json.dumps(result))

    def test_snapshot_is_detached_from_internal_state(self):
        snapshot = self.session.snapshot()
        snapshot["stages"].clear()
        self.assertEqual(set(self.session.snapshot()["stages"]), {"bootstrap", "primary_verify", "mfa_issue", "mfa_verify"})

    def test_persistence_projection_rejects_unknown_keys_strings_and_wrong_types(self):
        result = safe_session_diagnostics({
            "raw_secret": "private-token", "mfa_verified": "private-token", "dump_http_status": True,
            "dump_failure_kind": "private-exception", "stages": {"mfa_verify": {
                "http_status": 200, "jar_changed": True, "session_id_changed": "private-session",
                "known_jar_presence": {"client_state": True, "private-cookie-name": True},
                "raw_payload": "private-body",
            }, "private-stage": {}},
        })
        self.assertFalse(result["mfa_verified"])
        self.assertEqual(result["dump_http_status"], 0)
        self.assertEqual(result["dump_failure_kind"], "")
        self.assertEqual(result["stages"]["mfa_verify"]["http_status"], 200)
        self.assertTrue(result["stages"]["mfa_verify"]["jar_changed"])
        self.assertFalse(result["stages"]["mfa_verify"]["session_id_changed"])
        self.assertNotIn("private-", json.dumps(result))

    def test_actual_persistence_and_run_log_scrub_preserve_fixed_safe_evidence(self):
        from core.operations.run_log import scrub
        from core.storage.operations.store import _scrub

        self.base.session.cookies.jar.set_cookie(cookie("oai-client-auth-session", "private-state"))
        self.session.post(ORIGIN + "/api/accounts/password/verify")
        self.verify_mfa()
        self.base.next_response = response({"client_auth_session": {"email_verified": True, "username_verified": False},
                                            "checksum": "private-checksum", "session_id": None}, url=DUMP)
        state = self.session.collect_after_mfa()
        for project in (scrub, _scrub):
            with self.subTest(project=project.__name__):
                persisted = project({"session_diagnostics": state})["session_diagnostics"]
                self.assertEqual(persisted["stages"]["primary_verify"]["http_status"], 200)
                self.assertIs(persisted["stages"]["primary_verify"]["jar_changed"], True)
                self.assertIs(persisted["stages"]["mfa_verify"]["known_jar_presence"]["client_state"], True)
                self.assertIs(persisted["dump"]["client_auth_session"]["email_verified"], True)
                self.assertIs(persisted["dump"]["client_auth_session"]["username_verified_present"], True)


if __name__ == "__main__":
    unittest.main()
