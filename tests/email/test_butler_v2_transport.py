"""验证 v2 HTTP 合同、原幂等意图和精确租约身份，所有请求均使用桩。"""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

import requests

from core.email.email_butler import v2

CONNECTION = {"api_base": "https://butler.example/v2", "api_key": "fixture-key"}


def lease(**changes):
    return {"id": "lse_original", "email": "parent+tag@example.test", "service": "openai",
            "provider": "icloud_hme", "status": "active", "created_at": "2026-11-08T00:00:00Z",
            "expires_at": None, "external_ref": "original-intent", **changes}


def response(data=None, *, status=200, error=None, page=None):
    result = Mock(status_code=status)
    payload = {"request_id": "req_fixture"}
    if error is not None:
        payload["error"] = error
    else:
        payload["data"] = data
    if page is not None:
        payload["page"] = page
    result.json.return_value = payload
    return result


class ButlerV2TransportTests(unittest.TestCase):
    def test_normalizes_old_known_and_custom_bases_without_a_redirect(self):
        examples = {
            "https://codex-auth.leeseven.com/email-butler/v1/": "https://email-butler.leeseven.com/v2",
            "https://codex-auth.leeseven.com/email-butler/v2": "https://email-butler.leeseven.com/v2",
            "http://127.0.0.1:8788/v1/": "http://127.0.0.1:8788/v2",
            "https://butler.example": "https://butler.example/v2",
            "https://butler.example/prefix/v1": "https://butler.example/prefix/v2",
            "https://butler.example/prefix/v2": "https://butler.example/prefix/v2",
        }
        for original, expected in examples.items():
            with self.subTest(original=original):
                self.assertEqual(v2.normalize_base(original), expected)

    def test_rejects_credential_urls_queries_fragments_and_path_traversal(self):
        for url in ("", "file:///v2", "https://key@butler.example/v2", "https://butler.example/v2?key=secret",
                    "https://butler.example/v2#fragment", "https://butler.example/../v2",
                    "https://butler.example:invalid/v2", "https://butler.example/\nv2"):
            with self.subTest(url=url), self.assertRaises(v2.ButlerV2Error) as caught:
                v2.normalize_base(url)
            self.assertEqual(caught.exception.error_code, "butler_configuration_invalid")

    def test_success_envelope_and_connection_are_kept_separate(self):
        with patch.object(v2.requests, "request", return_value=response({"value": 1})) as request:
            result = v2.request("GET", "/me", **CONNECTION)
        self.assertEqual(result, {"data": {"value": 1}, "request_id": "req_fixture"})
        self.assertFalse(request.call_args.kwargs["allow_redirects"])
        self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer fixture-key")

    def test_nested_error_preserves_code_retryability_request_id_without_upstream_text(self):
        raw = response(status=403, error={"code": "permission_denied", "message": "private upstream text",
                                          "retryable": False})
        with patch.object(v2.requests, "request", return_value=raw), self.assertRaises(v2.ButlerV2Error) as caught:
            v2.list_leases(**CONNECTION)
        error = caught.exception
        self.assertEqual((error.status_code, error.error_code, error.request_id),
                         (403, "permission_denied", "req_fixture"))
        self.assertFalse(error.retryable)
        self.assertFalse(error.request_unknown)
        self.assertTrue(error.definite_rejection)
        self.assertNotIn("private upstream text", str(error))

    def test_missing_retryable_uses_http_classification(self):
        raw = response(status=503, error={"code": "service_unavailable", "message": "upstream"})
        with patch.object(v2.requests, "request", return_value=raw), self.assertRaises(v2.ButlerV2Error) as caught:
            v2.request("GET", "/availability", **CONNECTION)
        self.assertTrue(caught.exception.retryable)
        self.assertFalse(caught.exception.request_unknown)

    def test_success_without_request_id_or_data_is_not_accepted(self):
        for payload in ({"data": lease()}, {"request_id": "req_fixture"}, [lease()], {"code": 200}):
            raw = Mock(status_code=200)
            raw.json.return_value = payload
            with self.subTest(payload=payload), patch.object(v2.requests, "request", return_value=raw):
                with self.assertRaises(v2.ButlerV2Error):
                    v2.request("GET", "/me", **CONNECTION)

    def test_redirect_is_rejected_without_forwarding_credentials(self):
        with patch.object(v2.requests, "request", return_value=Mock(status_code=302)) as request:
            with self.assertRaises(v2.ButlerV2Error) as caught:
                v2.request("GET", "/me", **CONNECTION)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(caught.exception.error_code, "butler_endpoint_redirect")

    def test_create_long_term_uses_exact_persisted_idempotency_key(self):
        with patch.object(v2.requests, "request", return_value=response(lease(), status=201)) as request:
            result = v2.create_lease(external_ref="original-intent", idempotency_key="persisted-create", **CONNECTION)
        self.assertEqual(result["id"], "lse_original")
        self.assertEqual(request.call_args.kwargs["json"], {"service": "openai", "provider": "icloud_hme",
                                                          "external_ref": "original-intent", "ttl_seconds": None})
        self.assertEqual(request.call_args.kwargs["headers"]["Idempotency-Key"], "persisted-create")

    def test_write_transport_failure_is_unknown_and_never_automatically_reallocated(self):
        for failure in (requests.ReadTimeout("private connection text"), requests.ConnectionError("private address")):
            with self.subTest(kind=type(failure).__name__), patch.object(v2.requests, "request", side_effect=failure) as request:
                with self.assertRaises(v2.ButlerV2Error) as caught:
                    v2.create_lease(external_ref="original-intent", idempotency_key="persisted-create", **CONNECTION)
            self.assertEqual(request.call_count, 1)
            self.assertTrue(caught.exception.request_unknown)
            self.assertTrue(caught.exception.retryable)
            self.assertNotIn("private", str(caught.exception))

    def test_readlike_code_post_failure_does_not_claim_a_new_lease_is_unknown(self):
        with patch.object(v2.requests, "request", side_effect=requests.ReadTimeout("private")):
            with self.assertRaises(v2.ButlerV2Error) as caught:
                v2.code("lse_original", **CONNECTION)
        self.assertFalse(caught.exception.request_unknown)
        self.assertEqual(caught.exception.error_code, "butler_transport_timeout")

    def test_unknown_write_result_includes_non_json_and_wrong_lease_identity(self):
        raw = Mock(status_code=201)
        raw.json.side_effect = ValueError("private response")
        malformed_error = Mock(status_code=502)
        malformed_error.json.return_value = ["invalid gateway envelope"]
        for value in (raw, malformed_error, response(lease(external_ref="replacement"), status=201),
                      response(lease(expires_at="no time"), status=201)):
            with self.subTest(), patch.object(v2.requests, "request", return_value=value):
                with self.assertRaises(v2.ButlerV2Error) as caught:
                    v2.create_lease(external_ref="original-intent", idempotency_key="persisted-create", **CONNECTION)
            self.assertTrue(caught.exception.request_unknown)

    def test_writes_require_a_nonempty_printable_idempotency_key(self):
        with patch.object(v2.requests, "request") as request:
            for key in ("", " ", "key\nheader", "不可用于HTTP头"):
                with self.subTest(key=key), self.assertRaises(v2.ButlerV2Error):
                    v2.create_lease(external_ref="original-intent", idempotency_key=key, **CONNECTION)
        request.assert_not_called()

    def test_me_validates_client_policy_instead_of_v1_capabilities(self):
        data = {"client_id": "client_original", "allowed_services": ["openai"],
                "permissions": ["codes.read", "leases.read"], "limits": {"wait_seconds": 20}}
        with patch.object(v2.requests, "request", return_value=response(data)):
            self.assertEqual(v2.me(**CONNECTION), data)
        with patch.object(v2.requests, "request", return_value=response({**data, "permissions": "codes.read"})):
            with self.assertRaises(v2.ButlerV2Error) as caught:
                v2.me(**CONNECTION)
        self.assertEqual(caught.exception.error_code, "butler_client_response_invalid")

    def test_list_reads_all_bound_pages_and_keeps_original_filters(self):
        replies = [response([lease()], page={"limit": 100, "has_more": True, "next_cursor": "next"}),
                   response([lease(id="lse_second")], page={"limit": 100, "has_more": False, "next_cursor": None})]
        with patch.object(v2.requests, "request", side_effect=replies) as request:
            values = v2.list_leases(email="PARENT+TAG@example.test", external_ref="original-intent", **CONNECTION)
        self.assertEqual([value["id"] for value in values], ["lse_original", "lse_second"])
        first, second = [call.kwargs["params"] for call in request.call_args_list]
        self.assertEqual(first["email"], "parent+tag@example.test")
        self.assertNotIn("cursor", first)
        self.assertEqual(second, {**first, "cursor": "next"})

    def test_list_rejects_repeated_cursor_missing_cursor_and_cross_address_reply(self):
        page = {"limit": 100, "has_more": True, "next_cursor": "same"}
        cases = [
            [response([lease()], page={**page, "next_cursor": None})],
            [response([lease()], page=page), response([lease(id="lse_second")], page=page)],
            [response([lease(email="other@example.test")], page={**page, "has_more": False})],
        ]
        for replies in cases:
            with self.subTest(), patch.object(v2.requests, "request", side_effect=replies):
                with self.assertRaises(v2.ButlerV2Error):
                    v2.list_leases(email="parent+tag@example.test", **CONNECTION)

    def test_exact_get_does_not_accept_a_replacement_lease(self):
        with patch.object(v2.requests, "request", return_value=response(lease(id="lse_replacement"))):
            with self.assertRaises(v2.ButlerV2Error) as caught:
                v2.get_lease("lse_original", **CONNECTION)
        self.assertEqual(caught.exception.error_code, "butler_lease_identity_mismatch")

    def test_code_preserves_since_cursor_and_all_response_states(self):
        base = {"lease_id": "lse_original", "service": "openai", "verification_code": None,
                "code_id": None, "received_at": None}
        for state in ("matched", "pending", "ambiguous"):
            data = {**base, "status": state}
            if state == "matched":
                data.update(verification_code="ABC123", code_id="code_new_event", received_at="2026-11-08T00:01:00Z")
            with self.subTest(state=state), patch.object(v2.requests, "request", return_value=response(data)) as request:
                result = v2.code("lse_original", since="2026-11-08T00:00:00Z", after_code_id="code_previous",
                                 wait_seconds=20, **CONNECTION)
            self.assertEqual(result, data)
            self.assertEqual(request.call_args.kwargs["json"], {"wait_seconds": 20, "since": "2026-11-08T00:00:00Z",
                                                              "after_code_id": "code_previous"})
            self.assertEqual(request.call_args.kwargs["timeout"], 30)

    def test_code_rejects_incomplete_match_mismatched_lease_and_stale_pending_payload(self):
        valid = {"lease_id": "lse_original", "service": "openai", "status": "matched",
                 "verification_code": "123456", "code_id": "code_new_event", "received_at": "2026-11-08T00:01:00Z"}
        for data in ({**valid, "received_at": None}, {**valid, "lease_id": "lse_replacement"},
                     {**valid, "status": "pending"}):
            with self.subTest(data=data), patch.object(v2.requests, "request", return_value=response(data)):
                with self.assertRaises(v2.ButlerV2Error):
                    v2.code("lse_original", **CONNECTION)

    def test_code_validates_wait_range_and_explicit_time_zone_before_http(self):
        with patch.object(v2.requests, "request") as request:
            for options in ({"wait_seconds": 21}, {"wait_seconds": True}, {"since": "2026-11-08T00:00:00"}):
                with self.subTest(options=options), self.assertRaises(v2.ButlerV2Error):
                    v2.code("lse_original", **options, **CONNECTION)
        request.assert_not_called()

    def test_release_and_renew_keep_exact_lease(self):
        result = {**lease(status="released"), "service_tag_removed": True, "already_inactive": False}
        with patch.object(v2.requests, "request", return_value=response(result)) as request:
            self.assertEqual(v2.release("lse_original", reason="unused", **CONNECTION), result)
        self.assertEqual(request.call_args.kwargs["json"], {"reason": "unused"})
        with patch.object(v2.requests, "request", return_value=response(lease())) as request:
            self.assertEqual(v2.renew("lse_original", None, "original-renew", **CONNECTION)["id"], "lse_original")
        self.assertEqual(request.call_args.kwargs["headers"]["Idempotency-Key"], "original-renew")

    def test_availability_reports_real_counts_for_requested_service_provider(self):
        data = {"service": "openai", "provider": "icloud_hme", "resource_total": 9,
                "available": 3, "client_active_leases": 4, "availability_buckets": {"available": 3},
                "as_of": "2026-11-08T00:00:00Z"}
        with patch.object(v2.requests, "request", return_value=response(data)):
            self.assertEqual(v2.availability(**CONNECTION), data)
        wrong = deepcopy(data)
        wrong["available"] = 99
        with patch.object(v2.requests, "request", return_value=response(wrong)):
            with self.assertRaises(v2.ButlerV2Error):
                v2.availability(**CONNECTION)
