# -*- coding: utf-8 -*-
"""C2A AT 同步客户端只覆盖既有账号，且不泄露凭据。"""
from __future__ import annotations

import hashlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

import requests

from core.integrations.c2a import client


PRIVATE_KEY = "private-c2a-admin-key"
PRIVATE_TOKEN = "private-local-access-token"


class C2AClientTests(unittest.TestCase):
    def setUp(self):
        self.config = types.ModuleType("config.c2a")
        self.config.C2A_API_BASE = "https://C2A.example.test:443/prefix/"
        self.config.C2A_API_KEY = PRIVATE_KEY
        self.config.C2A_API_TIMEOUT = 17
        self.config_patch = patch.dict(sys.modules, {"config.c2a": self.config})
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    @staticmethod
    def response(payload, *, status=200):
        response = Mock(status_code=status, text="private-remote-response")
        response.json.return_value = payload
        return response

    def assert_safe(self, value):
        text = str(value)
        self.assertNotIn(PRIVATE_KEY, text)
        self.assertNotIn(PRIVATE_TOKEN, text)
        self.assertNotIn("private-remote-response", text)

    def safe_mutation_policy(self):
        return client.SafeMutationPolicy(client.configured_backend_identity())

    def test_normalizes_base_and_hashes_only_normalized_target(self):
        self.assertEqual(
            "https://c2a.example.test/prefix",
            client.normalize_base(" HTTPS://C2A.example.test:443/prefix/ "),
        )
        expected = hashlib.sha256(b"https://c2a.example.test/prefix").hexdigest()
        self.assertEqual(expected, client.configured_backend_identity())

    def test_rejects_invalid_base_without_leaking_configuration(self):
        for base in (
            "",
            "ftp://c2a.example.test",
            "https://key@c2a.example.test",
            "https://c2a.example.test?key=private-c2a-admin-key",
            "https://c2a.example.test#fragment",
            "https://c2a.example.test/../api",
            "https://c2a.example.test/has space",
        ):
            with self.subTest(base=base):
                self.config.C2A_API_BASE = base
                with self.assertRaises(client.C2AError) as raised:
                    client.configured_backend_identity()
                self.assertEqual("c2a_config_invalid", raised.exception.code)
                self.assert_safe(raised.exception)
        self.config.C2A_API_BASE = "https://c2a.example.test"

    @patch("core.integrations.c2a.client.requests.get")
    def test_finds_unique_exact_email_and_uses_bearer_management_key(self, get):
        get.return_value = self.response({
            "items": [
                {"id": "acct-target", "email": "User@Example.test"},
                {"id": "acct-substring", "email": "other-user@example.test"},
            ],
            "total": 2,
            "page": 1,
            "page_size": 500,
        })

        result = client.find_unique_account(" user@example.test ")

        self.assertEqual("acct-target", result["id"])
        self.assertEqual("user@example.test", result["email"])
        self.assertEqual(client.configured_backend_identity(), result["backend_identity"])
        get.assert_called_once_with(
            "https://c2a.example.test/prefix/api/accounts",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {PRIVATE_KEY}",
                "User-Agent": "turb-gpt-free-register/c2a",
            },
            timeout=17,
            params={
                "page": 1,
                "page_size": 500,
                "keyword": "user@example.test",
                "status": "all",
                "group_id": "all",
                "memory_state": "all",
            },
        )
        self.assert_not_in_result_or_call(PRIVATE_TOKEN, result, get)

    def assert_not_in_result_or_call(self, secret, result, request):
        self.assertNotIn(secret, str(result))
        self.assertNotIn(secret, str(request.call_args))

    @patch("core.integrations.c2a.client.requests.get")
    def test_pages_through_fuzzy_keyword_results_before_exact_email_selection(self, get):
        first_page = [
            {"id": f"acct-substring-{index}", "email": f"other-{index}@example.test"}
            for index in range(500)
        ]
        get.side_effect = [
            self.response({"items": first_page, "total": 501}),
            self.response({"items": [{"id": "acct-target", "email": "User@Example.test"}], "total": 501}),
        ]

        result = client.find_unique_account("user@example.test")

        self.assertEqual("acct-target", result["id"])
        self.assertEqual(2, get.call_count)
        self.assertEqual(
            {
                "page": 1,
                "page_size": 500,
                "keyword": "user@example.test",
                "status": "all",
                "group_id": "all",
                "memory_state": "all",
            },
            get.call_args_list[0].kwargs["params"],
        )
        self.assertEqual(
            {
                "page": 2,
                "page_size": 500,
                "keyword": "user@example.test",
                "status": "all",
                "group_id": "all",
                "memory_state": "all",
            },
            get.call_args_list[1].kwargs["params"],
        )

    @patch("core.integrations.c2a.client.requests.get")
    @patch("core.integrations.c2a.client.requests.post")
    def test_missing_or_ambiguous_remote_email_never_posts(self, post, get):
        cases = (
            ({"items": [], "total": 0}, "c2a_account_missing"),
            ({"items": [
                {"id": "acct-one", "email": "user@example.test"},
                {"id": "acct-two", "email": "USER@example.test"},
            ], "total": 2}, "c2a_account_ambiguous"),
        )
        for payload, code in cases:
            with self.subTest(code=code):
                get.return_value = self.response(payload)
                with self.assertRaises(client.C2AError) as raised:
                    client.find_unique_account("user@example.test")
                self.assertEqual(code, raised.exception.code)
                self.assert_safe(raised.exception)
        post.assert_not_called()

    @patch("core.integrations.c2a.client.requests.get")
    def test_bad_list_contract_is_classified_without_response_body(self, get):
        get.return_value = self.response({"items": "not-a-list", "total": 1})
        with self.assertRaises(client.C2AError) as raised:
            client.find_unique_account("user@example.test")
        self.assertEqual("find_account", raised.exception.stage)
        self.assertEqual("c2a_response_invalid", raised.exception.code)
        self.assert_safe(raised.exception)

    @patch("core.integrations.c2a.client.requests.get")
    def test_backend_change_rejects_before_remote_lookup(self, get):
        with self.assertRaises(client.C2AError) as raised:
            client.find_unique_account("user@example.test", expected_backend="different-backend")
        self.assertEqual("c2a_backend_changed", raised.exception.code)
        self.assert_safe(raised.exception)
        get.assert_not_called()

    @patch("core.integrations.c2a.client.requests.post")
    def test_update_sends_only_remote_id_and_access_token_and_requires_full_receipt(self, post):
        post.return_value = self.response({
            "updated": 1,
            "updated_ids": ["acct-target"],
            "removed_ids": [],
            "errors": [],
            "items": [{"id": "acct-target", "email": "user@example.test"}],
        })

        result = client.update_account_access_token(
            "acct-target", PRIVATE_TOKEN, safe_mutation_policy=self.safe_mutation_policy(),
        )

        self.assertEqual({
            "id": "acct-target",
            "updated": True,
            "backend_identity": client.configured_backend_identity(),
        }, result)
        post.assert_called_once_with(
            "https://c2a.example.test/prefix/api/accounts/update",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {PRIVATE_KEY}",
                "User-Agent": "turb-gpt-free-register/c2a",
                "Content-Type": "application/json",
            },
            timeout=17,
            json={"id": "acct-target", "access_token": PRIVATE_TOKEN},
        )
        self.assertNotIn(PRIVATE_TOKEN, str(result))
        self.assertNotIn(PRIVATE_KEY, str(result))

    @patch("core.integrations.c2a.client.requests.post")
    def test_update_rejects_unconfirmed_or_sensitive_remote_response(self, post):
        cases = (
            {
                "updated": 1,
                "updated_ids": ["acct-target"],
                "removed_ids": [],
                "errors": [],
                "items": [{"id": "other-account"}],
                "detail": PRIVATE_TOKEN,
            },
            {
                "updated": 1.0,
                "updated_ids": ["acct-target"],
                "removed_ids": [],
                "errors": [],
                "items": [{"id": "acct-target"}],
            },
            {
                "updated": 1,
                "updated_ids": ["ACCT-TARGET"],
                "removed_ids": [],
                "errors": [],
                "items": [{"id": "acct-target"}],
            },
        )
        for payload in cases:
            with self.subTest(payload=payload):
                post.return_value = self.response(payload)
                with self.assertRaises(client.C2AError) as raised:
                    client.update_account_access_token(
                        "acct-target", PRIVATE_TOKEN, safe_mutation_policy=self.safe_mutation_policy(),
                    )
                self.assertEqual("update_account", raised.exception.stage)
                self.assertEqual("c2a_update_unconfirmed", raised.exception.code)
                self.assert_safe(raised.exception)

    @patch("core.integrations.c2a.client.requests.post")
    def test_update_classifies_http_and_transport_failures_without_secrets(self, post):
        cases = (
            (self.response({}, status=401), "c2a_auth_rejected"),
            (self.response({}, status=429), "c2a_rate_limited"),
            (self.response({}, status=503), "c2a_server_error"),
            (self.response({}, status=404), "c2a_remote_account_missing"),
            (requests.Timeout("private-local-access-token"), "c2a_timeout"),
            (requests.ConnectionError("private-c2a-admin-key"), "c2a_connection_failed"),
        )
        for outcome, code in cases:
            with self.subTest(code=code):
                post.reset_mock()
                post.side_effect = outcome if isinstance(outcome, Exception) else None
                if not isinstance(outcome, Exception):
                    post.return_value = outcome
                with self.assertRaises(client.C2AError) as raised:
                    client.update_account_access_token(
                        "acct-target", PRIVATE_TOKEN, safe_mutation_policy=self.safe_mutation_policy(),
                    )
                self.assertEqual(code, raised.exception.code)
                self.assert_safe(raised.exception)

    def test_success_http_with_invalid_json_is_a_response_error_for_get_and_post(self):
        response = requests.Response()
        response.status_code = 200
        response._content = b"<html>invalid-private-response</html>"
        for method in ("get", "post"):
            with self.subTest(method=method), patch.object(client.requests, method, return_value=response) as request:
                with self.assertRaises(client.C2AError) as raised:
                    if method == "get":
                        client.find_unique_account("local@example.test")
                    else:
                        client.update_account_access_token(
                            "acct-target", PRIVATE_TOKEN, safe_mutation_policy=self.safe_mutation_policy(),
                        )
                self.assertEqual("c2a_response_invalid", raised.exception.code)
                self.assertNotIn("invalid-private-response", str(raised.exception))
                request.assert_called_once()

    @patch("core.integrations.c2a.client.requests.post")
    def test_checkpoint_runs_before_update_request(self, post):
        post.return_value = self.response({
            "updated": 1,
            "updated_ids": ["acct-target"],
            "removed_ids": [],
            "errors": [],
            "items": [{"id": "acct-target"}],
        })
        checkpoint = Mock()

        client.update_account_access_token(
            "acct-target", PRIVATE_TOKEN, checkpoint=checkpoint,
            safe_mutation_policy=self.safe_mutation_policy(),
        )

        checkpoint.assert_called_once_with()
        post.assert_called_once()

    @patch("core.integrations.c2a.client.requests.post")
    def test_update_requires_verified_policy_before_post(self, post):
        with self.assertRaises(client.C2AError) as raised:
            client.update_account_access_token("acct-target", PRIVATE_TOKEN)

        self.assertEqual("c2a_safety", raised.exception.stage)
        self.assertEqual("c2a_remote_policy_unverified", raised.exception.code)
        self.assert_safe(raised.exception)
        post.assert_not_called()

    @patch("core.integrations.c2a.client.requests.get")
    def test_safe_policy_preflight_requires_both_auto_removal_switches_false(self, get):
        get.return_value = self.response({
            "settings": {
                "auto_remove_invalid_accounts": False,
                "auto_remove_rate_limited_accounts": False,
            },
        })

        policy = client.verify_safe_mutation_policy()

        self.assertEqual(client.configured_backend_identity(), policy.backend_identity)
        get.assert_called_once_with(
            "https://c2a.example.test/prefix/api/settings",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {PRIVATE_KEY}",
                "User-Agent": "turb-gpt-free-register/c2a",
            },
            timeout=17,
        )

    def test_unsafe_or_unverified_policy_never_reaches_update_post(self):
        for settings, code in (
            ({"auto_remove_invalid_accounts": True, "auto_remove_rate_limited_accounts": False}, "c2a_remote_auto_removal_enabled"),
            ({"auto_remove_invalid_accounts": False}, "c2a_remote_policy_unverified"),
            ({"auto_remove_invalid_accounts": "false", "auto_remove_rate_limited_accounts": False}, "c2a_remote_policy_unverified"),
            ({}, "c2a_remote_policy_unverified"),
        ):
            with self.subTest(code=code), patch("core.integrations.c2a.client.requests.get") as get, patch(
                "core.integrations.c2a.client.requests.post"
            ) as post:
                get.return_value = self.response({"settings": settings}) if settings else self.response({})
                with self.assertRaises(client.C2AError) as raised:
                    client.verify_safe_mutation_policy()
                self.assertEqual(code, raised.exception.code)
                self.assert_safe(raised.exception)
                post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
