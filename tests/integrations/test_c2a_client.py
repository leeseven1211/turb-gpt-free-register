# -*- coding: utf-8 -*-
"""C2A AT 同步客户端按接口契约新建或覆盖账号，且不泄露凭据。"""
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

    @staticmethod
    def remote_sync_row(*, account_id="acct-target", **updates):
        return {
            "id": account_id,
            "email": "User@Example.test",
            "enabled": True,
            "backend_status": "正常",
            "status_category": "normal",
            "status_reason_code": "access_token_refresh_required",
            "access_token_status": "invalid",
            "access_token_issued_at": 1000,
            "access_token_expires_at": 2000,
            "credential_availability": "recoverable",
            "can_refresh_access_token": True,
            "group_id": "account-group",
            **updates,
        }

    @patch("core.integrations.c2a.client.requests.get")
    def test_scan_reads_every_page_and_projects_only_known_metadata(self, get):
        first_page = [
            self.remote_sync_row(account_id=f"acct-{index}")
            for index in range(500)
        ]
        last_row = self.remote_sync_row(
            access_token=PRIVATE_TOKEN, status_raw_error="private-remote-response",
            refresh_token=PRIVATE_KEY,
        )
        get.side_effect = [
            self.response({"items": first_page, "total": 501, "page": 1, "page_size": 500}),
            self.response({"items": [last_row], "total": 501, "page": 2, "page_size": 500}),
        ]

        rows = client.list_configured_accounts(expected_backend=client.configured_backend_identity())

        self.assertEqual(501, len(rows))
        self.assertEqual({
            "id": "acct-target",
            "email": "user@example.test",
            "enabled": True,
            "backend_status": "正常",
            "status_category": "normal",
            "status_reason_code": "access_token_refresh_required",
            "access_token_status": "invalid",
            "access_token_issued_at": 1000,
            "access_token_expires_at": 2000,
            "credential_availability": "recoverable",
            "can_refresh_access_token": True,
            "group_id": "account-group",
        }, rows[-1])
        self.assertEqual([1, 2], [call.kwargs["params"]["page"] for call in get.call_args_list])
        self.assertTrue(all(call.kwargs["params"]["status"] == "all" for call in get.call_args_list))
        self.assertTrue(all(call.kwargs.get("allow_redirects") is False for call in get.call_args_list))
        self.assert_safe(rows)

    @patch("core.integrations.c2a.client.requests.get")
    def test_scan_never_returns_a_partial_snapshot_on_a_short_page(self, get):
        get.return_value = self.response({
            "items": [self.remote_sync_row()], "total": 501, "page": 1, "page_size": 500,
        })

        with self.assertRaises(client.C2AError) as raised:
            client.list_configured_accounts()

        self.assertEqual("c2a_response_invalid", raised.exception.code)
        self.assert_safe(raised.exception)

    @patch("core.integrations.c2a.client.requests.get")
    def test_target_state_compares_at_in_memory_using_the_management_id(self, get):
        checkpoint = Mock()
        for remote_at, token_matches in ((PRIVATE_TOKEN, True), ("other-fixture-at", False)):
            with self.subTest(token_matches=token_matches):
                get.reset_mock()
                checkpoint.reset_mock()
                get.side_effect = [
                    self.response({"item": self.remote_sync_row()}),
                    self.response({"access_token": remote_at}),
                ]

                result = client.get_account_sync_state(
                    "acct-target", "user@example.test", PRIVATE_TOKEN, checkpoint=checkpoint,
                )

                self.assertIs(token_matches, result["token_matches"])
                self.assertTrue(result["enabled"])
                self.assertEqual("invalid", result["access_token_status"])
                self.assertEqual([
                    "https://c2a.example.test/prefix/api/accounts/acct-target",
                    "https://c2a.example.test/prefix/api/accounts/acct-target/access-token",
                ], [call.args[0] for call in get.call_args_list])
                self.assertEqual(2, checkpoint.call_count)
                self.assert_safe(result)
                self.assertNotIn(remote_at, str(result))

    @patch("core.integrations.c2a.client.requests.get")
    def test_target_conflict_stops_before_credential_read(self, get):
        for response, code in (
            (self.response({}, status=404), "c2a_remote_account_missing"),
            (self.response({"item": self.remote_sync_row(enabled=False)}), "c2a_remote_account_disabled"),
            (
                self.response({"item": self.remote_sync_row(email="changed@example.test")}),
                "c2a_remote_account_identity_changed",
            ),
            (self.response({"item": self.remote_sync_row(account_id="acct-different")}), "c2a_response_invalid"),
        ):
            with self.subTest(code=code):
                get.reset_mock()
                get.return_value = response

                with self.assertRaises(client.C2AError) as raised:
                    client.get_account_sync_state("acct-target", "user@example.test", PRIVATE_TOKEN)

                self.assertEqual(code, raised.exception.code)
                self.assertEqual(1, get.call_count)
                self.assert_safe(raised.exception)

    @patch("core.integrations.c2a.client.requests.get")
    def test_missing_access_token_field_is_not_a_confirmed_different_token(self, get):
        get.side_effect = [
            self.response({"item": self.remote_sync_row()}),
            self.response({"detail": PRIVATE_TOKEN}),
        ]

        with self.assertRaises(client.C2AError) as raised:
            client.get_account_sync_state("acct-target", "user@example.test", PRIVATE_TOKEN)

        self.assertEqual("c2a_response_invalid", raised.exception.code)
        self.assert_safe(raised.exception)

    @patch("core.integrations.c2a.client.requests.get")
    def test_confirmed_missing_at_keeps_the_original_target_for_update(self, get):
        get.return_value = self.response({"item": self.remote_sync_row(
            access_token_status="missing", access_token_issued_at=None, access_token_expires_at=None,
        )})

        result = client.get_account_sync_state("acct-target", "user@example.test", PRIVATE_TOKEN)

        self.assertEqual("acct-target", result["id"])
        self.assertIs(False, result["token_matches"])
        self.assertEqual("missing", result["access_token_status"])
        self.assertEqual(1, get.call_count)

    @patch("core.integrations.c2a.client.requests.get")
    def test_missing_credential_subresource_does_not_report_account_missing(self, get):
        for response in (self.response({}, status=404), self.response({"access_token": ""})):
            with self.subTest(status=response.status_code):
                get.side_effect = [self.response({"item": self.remote_sync_row()}), response]

                with self.assertRaises(client.C2AError) as raised:
                    client.get_account_sync_state("acct-target", "user@example.test", PRIVATE_TOKEN)

                self.assertEqual("c2a_remote_access_token_missing", raised.exception.code)
                self.assert_safe(raised.exception)

    @patch("core.integrations.c2a.client.requests.get")
    def test_target_read_rejects_non_id_path_segments_and_backend_changes(self, get):
        for remote_id, backend, code in (
            ("acct-target/access-token", None, "c2a_remote_account_id_invalid"),
            ("acct-target", "other-backend", "c2a_backend_changed"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(client.C2AError) as raised:
                    client.get_account_sync_state(
                        remote_id, "user@example.test", PRIVATE_TOKEN, expected_backend=backend,
                    )
                self.assertEqual(code, raised.exception.code)
        get.assert_not_called()

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
            allow_redirects=False,
            json={"id": "acct-target", "access_token": PRIVATE_TOKEN},
        )
        self.assertNotIn(PRIVATE_TOKEN, str(result))
        self.assertNotIn(PRIVATE_KEY, str(result))

    @staticmethod
    def import_receipt(**overrides):
        return {
            "added": 1,
            "skipped": 0,
            "synced": 0,
            "updated_ids": ["acct-new"],
            "removed_ids": [],
            "errors": [],
            "events": [],
            "items": [{"id": "acct-new", "email": "user@example.test"}],
            **overrides,
        }

    @patch("core.integrations.c2a.client.requests.post")
    def test_create_sends_email_and_current_at_without_remote_sync(self, post):
        post.return_value = self.response(self.import_receipt())

        result = client.create_account_access_token(
            " User@Example.test ", PRIVATE_TOKEN, safe_mutation_policy=self.safe_mutation_policy(),
        )

        self.assertEqual({
            "id": "acct-new", "created": True, "updated": False,
            "backend_identity": client.configured_backend_identity(),
        }, result)
        post.assert_called_once_with(
            "https://c2a.example.test/prefix/api/accounts",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {PRIVATE_KEY}",
                "User-Agent": "turb-gpt-free-register/c2a",
                "Content-Type": "application/json",
            },
            timeout=17,
            json={
                "accounts": [{"email": "user@example.test", "access_token": PRIVATE_TOKEN}],
                "sync_after_import": False,
            },
        )
        self.assert_safe(result)

    @patch("core.integrations.c2a.client.requests.post")
    def test_create_dedup_receipt_does_not_claim_token_was_overwritten(self, post):
        post.return_value = self.response(self.import_receipt(added=0, skipped=1))

        result = client.create_account_access_token(
            "user@example.test", PRIVATE_TOKEN, safe_mutation_policy=self.safe_mutation_policy(),
        )

        self.assertFalse(result["created"])
        self.assertFalse(result["updated"])
        self.assertEqual("acct-new", result["id"])
        post.assert_called_once()

    @patch("core.integrations.c2a.client.requests.post")
    def test_create_rejects_unconfirmed_or_wrong_identity_receipt(self, post):
        cases = (
            self.import_receipt(added=True),
            self.import_receipt(skipped=False),
            self.import_receipt(synced=1),
            self.import_receipt(added=0, skipped=0),
            self.import_receipt(updated_ids=[]),
            self.import_receipt(items=[{"id": "acct-other", "email": "user@example.test"}]),
            self.import_receipt(items=[{"id": "acct-new", "email": "other@example.test"}]),
            self.import_receipt(removed_ids=["acct-new"]),
            self.import_receipt(errors=[{"error": PRIVATE_TOKEN}]),
        )
        for payload in cases:
            with self.subTest(payload=payload):
                post.reset_mock()
                post.return_value = self.response(payload)
                with self.assertRaises(client.C2AError) as raised:
                    client.create_account_access_token(
                        "user@example.test", PRIVATE_TOKEN, safe_mutation_policy=self.safe_mutation_policy(),
                    )
                self.assertEqual("c2a_create_unconfirmed", raised.exception.code)
                self.assertEqual("create_account", raised.exception.stage)
                self.assert_safe(raised.exception)
                post.assert_called_once()

    @patch("core.integrations.c2a.client.requests.post")
    def test_create_classifies_rejection_and_timeout_without_replaying_post(self, post):
        for outcome, code in (
            (self.response({}, status=400), "c2a_create_rejected"),
            (requests.Timeout(PRIVATE_TOKEN), "c2a_timeout"),
        ):
            with self.subTest(code=code):
                post.reset_mock()
                post.side_effect = outcome if isinstance(outcome, Exception) else None
                post.return_value = outcome
                with self.assertRaises(client.C2AError) as raised:
                    client.create_account_access_token(
                        "user@example.test", PRIVATE_TOKEN, safe_mutation_policy=self.safe_mutation_policy(),
                    )
                self.assertEqual(code, raised.exception.code)
                self.assert_safe(raised.exception)
                post.assert_called_once()

    @patch("core.integrations.c2a.client.requests.post")
    def test_create_requires_same_backend_and_verified_policy_before_post(self, post):
        for kwargs, code in (
            ({}, "c2a_remote_policy_unverified"),
            ({"safe_mutation_policy": client.SafeMutationPolicy("other-backend")}, "c2a_remote_policy_unverified"),
            ({"expected_backend": "other-backend"}, "c2a_backend_changed"),
        ):
            with self.subTest(code=code), self.assertRaises(client.C2AError) as raised:
                client.create_account_access_token("user@example.test", PRIVATE_TOKEN, **kwargs)
            self.assertEqual(code, raised.exception.code)
        post.assert_not_called()

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

    @patch("core.integrations.c2a.client.requests.post")
    def test_update_classifies_only_the_official_token_conflict_detail(self, post):
        conflict_detail = "access token already belongs to another account"
        for error, code in (
            (conflict_detail, "c2a_remote_token_conflict"),
            (f"{conflict_detail}: {PRIVATE_TOKEN}", "c2a_update_rejected"),
        ):
            with self.subTest(code=code):
                post.return_value = self.response({"detail": {"error": error}}, status=400)

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
            allow_redirects=False,
        )

    @patch("core.integrations.c2a.client.requests.get")
    def test_redirected_settings_cannot_confirm_the_configured_backends_policy(self, get):
        def request_settings(*args, **kwargs):
            if kwargs.get("allow_redirects") is False:
                return self.response({}, status=307)
            return self.response({"settings": {
                "auto_remove_invalid_accounts": False, "auto_remove_rate_limited_accounts": False,
            }})

        get.side_effect = request_settings

        with self.assertRaises(client.C2AError) as raised:
            client.verify_safe_mutation_policy()

        self.assertEqual("c2a_safety", raised.exception.stage)
        self.assert_safe(raised.exception)

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
