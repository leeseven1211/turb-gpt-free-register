"""Sub2API 客户端的目标校验、增量更新和巡检契约。"""
import base64
import json
import threading
import unittest

import config
from unittest.mock import Mock, patch

from config import sub2api as cfg
from core.integrations.sub2api import client


class Sub2ApiClientTests(unittest.TestCase):
    def setUp(self):
        self.auth = {"email": "user@example.test", "access_token": "new-access", "refresh_token": "new-refresh"}
        self.remote = {
            "id": 41, "name": "oauth---user@example.test", "platform": "openai", "type": "oauth", "status": "error",
            "credentials": {"email": "user@example.test", "access_token": "old-access", "model_mapping": {"custom": "upstream"}, "chatgpt_account_id": "old-account"},
            "extra": {"device": "existing-device"}, "concurrency": 9, "priority": 70, "group_ids": [8], "proxy_id": 2, "load_factor": 150,
        }
        self.config = patch.multiple(cfg, create=True, SUB2API_API_BASE="https://sub2.example/prefix/", SUB2API_API_URL="", SUB2API_API_KEY="synthetic-key", SUB2API_API_TIMEOUT=12,
            SUB2API_UPLOAD_GROUP_IDS="", SUB2API_UPLOAD_PROXY_ID="", SUB2API_UPLOAD_CONCURRENCY="", SUB2API_UPLOAD_PRIORITY="", SUB2API_UPLOAD_LOAD_FACTOR="", SUB2API_UPLOAD_MODELS="")
        self.config.start()
        self.addCleanup(self.config.stop)

    @staticmethod
    def response(data, status=200):
        return Mock(status_code=status, json=Mock(return_value={"code": 0, "data": data}), text="synthetic-private-response")

    def test_target_update_preserves_settings_and_oauth_identity_fields(self):
        with patch.object(client.requests, "get", return_value=self.response(self.remote)), patch.object(client.requests, "put", return_value=self.response({})) as put, patch.object(client.requests, "post", return_value=self.response({})) as post:
            result = client.update_and_enable_configured_account(self.auth, 41)
        payload = put.call_args.kwargs["json"]
        self.assertEqual(payload, {"credentials": {**self.remote["credentials"], "access_token": "new-access", "refresh_token": "new-refresh"}})
        self.assertTrue(result["uploaded"])
        self.assertTrue(result["enabled"])
        self.assertEqual([c.args[0].rsplit("/", 1)[-1] for c in post.call_args_list], ["clear-error", "schedulable"])
        self.assertNotIn("new-refresh", str(result))

    def test_target_update_maps_codex_fields_and_ignores_unrelated_local_fields(self):
        auth = {**self.auth, "account_id": "new-account", "expired": "2026-12-01T00:00:00Z", "type": "codex", "model_mapping": {"unsafe": "override"}, "extra": {"unsafe": True}}
        with patch.object(client.requests, "get", return_value=self.response(self.remote)), patch.object(client.requests, "put", return_value=self.response({})) as put, patch.object(client.requests, "post", return_value=self.response({})):
            client.update_and_enable_configured_account(auth, 41)
        payload = put.call_args.kwargs["json"]
        self.assertEqual(payload["credentials"]["chatgpt_account_id"], "new-account")
        self.assertEqual(payload["credentials"]["expires_at"], "2026-12-01T00:00:00Z")
        self.assertEqual(payload["credentials"]["model_mapping"], {"custom": "upstream"})
        self.assertNotIn("extra", payload)
        self.assertNotIn("type", payload["credentials"])

    def test_target_update_refreshes_identity_metadata_from_new_jwt(self):
        claims = {
            "sub": "jwt-sub", "email": self.auth["email"],
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "jwt-account", "chatgpt_user_id": "jwt-user",
                "chatgpt_plan_type": "plus", "organizations": [{"id": "first-org"}, {"id": "default-org", "is_default": True}],
            },
        }
        token = synthetic_jwt(claims)
        remote = {**self.remote, "credentials": {**self.remote["credentials"], "client_id": "existing-client", "plan_type": "free", "organization_id": "old-org"}}
        auth = {**self.auth, "id_token": token}
        with patch.object(client.requests, "get", return_value=self.response(remote)), patch.object(client.requests, "put", return_value=self.response({})) as put, patch.object(client.requests, "post", return_value=self.response({})):
            client.update_and_enable_configured_account(auth, 41)
        credentials = put.call_args.kwargs["json"]["credentials"]
        self.assertEqual(credentials["chatgpt_account_id"], "jwt-account")
        self.assertEqual(credentials["chatgpt_user_id"], "jwt-user")
        self.assertEqual(credentials["plan_type"], "plus")
        self.assertEqual(credentials["organization_id"], "default-org")
        self.assertEqual(credentials["client_id"], "existing-client")
        self.assertEqual(credentials["model_mapping"], {"custom": "upstream"})

    def test_target_update_explicit_metadata_overrides_jwt_and_missing_claims_preserve_remote(self):
        auth = {
            **self.auth, "id_token": synthetic_jwt({"sub": "jwt-user", "https://api.openai.com/auth": {"chatgpt_plan_type": "free", "poid": "jwt-org"}}),
            "chatgpt_user_id": "explicit-user", "plan_type": "plus", "organization_id": "explicit-org", "client_id": "explicit-client",
        }
        with patch.object(client.requests, "get", return_value=self.response(self.remote)), patch.object(client.requests, "put", return_value=self.response({})) as put, patch.object(client.requests, "post", return_value=self.response({})):
            client.update_and_enable_configured_account(auth, 41)
        credentials = put.call_args.kwargs["json"]["credentials"]
        self.assertEqual(credentials["chatgpt_user_id"], "explicit-user")
        self.assertEqual(credentials["plan_type"], "plus")
        self.assertEqual(credentials["organization_id"], "explicit-org")
        self.assertEqual(credentials["client_id"], "explicit-client")
        self.assertEqual(credentials["chatgpt_account_id"], "old-account")

    def test_explicit_upload_options_are_normalized_and_applied(self):
        with patch.multiple(cfg, SUB2API_UPLOAD_GROUP_IDS="4, 7,4", SUB2API_UPLOAD_PROXY_ID="3", SUB2API_UPLOAD_CONCURRENCY="6", SUB2API_UPLOAD_PRIORITY="0", SUB2API_UPLOAD_LOAD_FACTOR="125", SUB2API_UPLOAD_MODELS="gpt-a\ngpt-b,gpt-a"):
            options = client.configured_upload_options()
            with patch.object(client.requests, "get", return_value=self.response(self.remote)), patch.object(client.requests, "put", return_value=self.response({})) as put, patch.object(client.requests, "post", return_value=self.response({})):
                client.update_and_enable_configured_account(self.auth, 41)
        self.assertEqual(options, {"group_ids": [4, 7], "proxy_id": 3, "concurrency": 6, "priority": 0, "load_factor": 125, "model_whitelist": ["gpt-a", "gpt-b"]})
        payload = put.call_args.kwargs["json"]
        self.assertEqual(payload["group_ids"], [4, 7])
        self.assertTrue(payload["confirm_mixed_channel_risk"])
        self.assertEqual(payload["priority"], 0)
        self.assertEqual(payload["credentials"]["model_mapping"], {"gpt-a": "gpt-a", "gpt-b": "gpt-b"})

    def test_invalid_options_are_rejected_before_network(self):
        for key, value in (("SUB2API_UPLOAD_GROUP_IDS", "1,wrong"), ("SUB2API_UPLOAD_PROXY_ID", "0"), ("SUB2API_UPLOAD_CONCURRENCY", "-1"), ("SUB2API_UPLOAD_CONCURRENCY", "0"), ("SUB2API_UPLOAD_LOAD_FACTOR", "0"), ("SUB2API_UPLOAD_LOAD_FACTOR", "nan"), ("SUB2API_UPLOAD_LOAD_FACTOR", "1.25")):
            with self.subTest(key=key), patch.object(cfg, key, value), patch.object(client.requests, "get") as get:
                with self.assertRaises(client.Sub2ApiSyncError) as raised:
                    client.update_and_enable_configured_account(self.auth, 41)
                self.assertEqual(raised.exception.code, "sub2api_config_invalid")
                get.assert_not_called()

    def test_backend_identity_is_normalized_and_contains_no_credentials(self):
        first = client.configured_backend_identity()
        with patch.object(cfg, "SUB2API_API_BASE", "HTTPS://SUB2.EXAMPLE:443/prefix"):
            self.assertEqual(first, client.configured_backend_identity())
        with patch.object(cfg, "SUB2API_API_BASE", "https://other.example/prefix"):
            self.assertNotEqual(first, client.configured_backend_identity())
        self.assertNotIn("sub2", first)
        self.assertNotIn("synthetic-key", first)

    def test_backend_mismatch_stops_before_network(self):
        with patch.object(client.requests, "get") as get, patch.object(client.requests, "put") as put:
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.update_and_enable_configured_account(self.auth, 41, expected_backend="old-backend")
        self.assertEqual(raised.exception.code, "sub2api_backend_changed")
        get.assert_not_called()
        put.assert_not_called()

    def test_identity_and_platform_mismatch_never_write(self):
        for change in ({"id": 42}, {"platform": "anthropic"}, {"type": "apikey"}, {"credentials": {"email": "other@example.test"}}):
            with self.subTest(change=change), patch.object(client.requests, "get", return_value=self.response({**self.remote, **change})), patch.object(client.requests, "put") as put, patch.object(client.requests, "post") as post:
                with self.assertRaises(client.Sub2ApiSyncError) as raised:
                    client.update_and_enable_configured_account(self.auth, 41)
                self.assertEqual(raised.exception.stage, "resolve_account")
                put.assert_not_called()
                post.assert_not_called()

    def test_snapshot_freezes_target_key_options_and_timeout_across_checkpoints(self):
        def hot_reload():
            cfg.SUB2API_API_BASE = "https://different.example"
            cfg.SUB2API_API_KEY = "changed-key"
            cfg.SUB2API_UPLOAD_PRIORITY = "100"
            cfg.SUB2API_API_TIMEOUT = 90
        with patch.object(client.requests, "get", return_value=self.response(self.remote)) as get, patch.object(client.requests, "put", return_value=self.response({})) as put, patch.object(client.requests, "post", return_value=self.response({})) as post:
            client.update_and_enable_configured_account(self.auth, 41, checkpoint=hot_reload)
        for request in (get.call_args, put.call_args, *post.call_args_list):
            self.assertTrue(request.args[0].startswith("https://sub2.example/prefix/"))
            self.assertEqual(request.kwargs["headers"]["x-api-key"], "synthetic-key")
            self.assertEqual(request.kwargs["timeout"], 12)
        self.assertNotIn("priority", put.call_args.kwargs["json"])

    def test_clear_error_failure_keeps_uploaded_fact_and_does_not_enable(self):
        with patch.object(client.requests, "get", return_value=self.response(self.remote)), patch.object(client.requests, "put", return_value=self.response({})), patch.object(client.requests, "post", side_effect=requests_timeout()) as post:
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.update_and_enable_configured_account(self.auth, 41)
        self.assertEqual(raised.exception.stage, "reset_error")
        self.assertEqual(raised.exception.code, "sub2api_timeout")
        self.assertTrue(raised.exception.uploaded)
        self.assertEqual(raised.exception.sub2api_account_id, 41)
        self.assertEqual(post.call_count, 1)
        self.assertNotIn("synthetic-private", str(raised.exception))

    def test_error_account_listing_paginates_and_filters_groups(self):
        outside = {**self.remote, "id": 42, "group_ids": [9]}
        active = {**self.remote, "id": 43, "status": "active"}
        second = {**self.remote, "id": 44, "group_ids": [], "account_groups": [{"group_id": 8}]}
        with patch.object(client.requests, "get", side_effect=[self.response({"items": [self.remote, outside, active], "pages": 2}), self.response({"items": [second], "pages": 2})]) as get:
            accounts = client.list_configured_error_accounts(group_ids=[8])
        self.assertEqual([a["id"] for a in accounts], [41, 44])
        self.assertEqual([c.kwargs["params"]["page"] for c in get.call_args_list], [1, 2])
        self.assertEqual(get.call_args.kwargs["params"]["platform"], "openai")
        self.assertEqual(get.call_args.kwargs["params"]["status"], "error")

    def test_configured_upload_updates_existing_id_without_import_defaults(self):
        get_responses = [self.response({"items": [self.remote], "pages": 1}), self.response(self.remote)]
        with patch.object(client.requests, "get", side_effect=get_responses), patch.object(client.requests, "put", return_value=self.response({})) as put, patch.object(client.requests, "post") as post:
            result = client.upload_configured_codex_oauth_credential(self.auth)
        self.assertTrue(result["uploaded"])
        self.assertEqual(result["updated"], 1)
        self.assertNotIn("concurrency", put.call_args.kwargs["json"])
        self.assertNotIn("priority", put.call_args.kwargs["json"])
        post.assert_not_called()

    def test_initial_import_does_not_send_unconfigured_fixed_settings(self):
        with patch.object(client.requests, "post", return_value=self.response({"total": 1, "created": 1, "failed": 0})) as post:
            client.upload_codex_oauth_credential(self.auth, "https://sub2.example/api/v1/admin/accounts/import/codex-session")
        self.assertNotIn("concurrency", post.call_args.kwargs["json"])
        self.assertNotIn("priority", post.call_args.kwargs["json"])

    def test_upload_rejects_changed_backend_before_first_request(self):
        with patch.object(client.requests, "get") as get:
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.upload_and_enable_configured_codex_oauth_credential(self.auth, expected_backend="old-backend")
        self.assertEqual(raised.exception.code, "sub2api_backend_changed")
        get.assert_not_called()

    def test_initial_import_applies_models_after_confirmed_id_without_enabling(self):
        imported = self.response({"total": 1, "created": 1, "updated": 0, "failed": 0, "items": [{"index": 1, "action": "created", "account_id": 41}]})
        with patch.object(cfg, "SUB2API_UPLOAD_MODELS", "gpt-a"), patch.object(client.requests, "get", side_effect=[self.response({"items": [], "pages": 1}), self.response(self.remote)]), patch.object(client.requests, "post", return_value=imported) as post, patch.object(client.requests, "put", return_value=self.response({})) as put:
            result = client.upload_configured_codex_oauth_credential(self.auth)
        self.assertTrue(result["uploaded"])
        self.assertFalse(result["enabled"])
        self.assertEqual(put.call_args.kwargs["json"]["credentials"]["model_mapping"], {"gpt-a": "gpt-a"})
        self.assertEqual(post.call_count, 1)

    def test_ambiguous_email_match_does_not_import_or_update(self):
        duplicate = {**self.remote, "id": 42}
        with patch.object(client.requests, "get", return_value=self.response({"items": [self.remote, duplicate], "pages": 1})), patch.object(client.requests, "post") as post, patch.object(client.requests, "put") as put:
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertEqual(raised.exception.code, "sub2api_account_ambiguous")
        self.assertEqual(raised.exception.backend_identity, client.configured_backend_identity())
        post.assert_not_called()
        put.assert_not_called()

    def test_missing_remote_account_keeps_classified_failure(self):
        with patch.object(client.requests, "get", return_value=self.response({}, status=404)), patch.object(client.requests, "put") as put:
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.update_and_enable_configured_account(self.auth, 41)
        self.assertEqual(raised.exception.code, "sub2api_account_missing")
        self.assertFalse(raised.exception.uploaded)
        self.assertEqual(raised.exception.backend_identity, client.configured_backend_identity())
        put.assert_not_called()

    def test_cancellation_before_scheduling_preserves_uploaded_fact_and_backend(self):
        cancellation = RuntimeError("已取消")
        with patch.object(client.requests, "get", return_value=self.response(self.remote)), patch.object(client.requests, "put", return_value=self.response({})), patch.object(client.requests, "post", return_value=self.response({})) as post:
            with self.assertRaises(RuntimeError) as raised:
                client.update_and_enable_configured_account(self.auth, 41, checkpoint=Mock(side_effect=[None, None, None, cancellation]))
        self.assertIs(raised.exception, cancellation)
        self.assertTrue(raised.exception.sub2api_uploaded)
        self.assertEqual(raised.exception.sub2api_stage, "enable_scheduling")
        self.assertEqual(raised.exception.backend_identity, client.configured_backend_identity())
        self.assertEqual(post.call_count, 1)

    def test_initial_import_uses_remote_identity_dedup_without_fixed_settings(self):
        imported = self.response({"total": 1, "created": 1, "updated": 0, "failed": 0, "items": [{"index": 1, "action": "created", "account_id": 41}]})
        with patch.object(client.requests, "get", return_value=self.response({"items": [], "pages": 1})), patch.object(client.requests, "post", return_value=imported) as post:
            client.upload_configured_codex_oauth_credential(self.auth)
        self.assertTrue(post.call_args.kwargs["json"]["update_existing"])
        self.assertNotIn("concurrency", post.call_args.kwargs["json"])
        self.assertNotIn("priority", post.call_args.kwargs["json"])

    def test_post_import_option_failure_preserves_imported_id_and_upload_fact(self):
        imported = self.response({"total": 1, "created": 1, "updated": 0, "failed": 0, "items": [{"index": 1, "action": "created", "account_id": 41}]})
        with patch.object(cfg, "SUB2API_UPLOAD_PRIORITY", "5"), patch.object(client.requests, "get", side_effect=[self.response({"items": [], "pages": 1}), self.response(self.remote)]), patch.object(client.requests, "post", return_value=imported), patch.object(client.requests, "put", side_effect=requests_timeout()):
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertTrue(raised.exception.uploaded)
        self.assertEqual(raised.exception.sub2api_account_id, 41)

    def test_email_fallback_strips_known_oauth_name_prefix(self):
        remote = {**self.remote, "credentials": {"access_token": "old-access"}}
        with patch.object(client.requests, "get", return_value=self.response(remote)), patch.object(client.requests, "put", return_value=self.response({})) as put, patch.object(client.requests, "post", return_value=self.response({})):
            result = client.update_and_enable_configured_account(self.auth, 41)
        self.assertTrue(result["enabled"])
        self.assertEqual(put.call_args.kwargs["json"]["credentials"]["email"], "user@example.test")

    def test_low_level_import_rejection_never_exposes_remote_body(self):
        rejected = self.response({"failed": 1, "errors": [{"message": "opaque-secret-value"}]})
        with patch.object(client.requests, "post", return_value=rejected):
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.upload_codex_oauth_credential(self.auth, "https://sub2.example/api/v1/admin/accounts/import/codex-session")
        self.assertEqual(raised.exception.code, "sub2api_upload_rejected")
        self.assertNotIn("opaque-secret-value", str(raised.exception))

    def test_low_level_import_invalid_json_is_not_reported_as_success(self):
        response = self.response({})
        response.json.side_effect = ValueError("opaque-secret-value")
        with patch.object(client.requests, "post", return_value=response):
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.upload_codex_oauth_credential(self.auth, "https://sub2.example/api/v1/admin/accounts/import/codex-session")
        self.assertEqual(raised.exception.code, "sub2api_response_invalid")
        self.assertNotIn("opaque-secret-value", str(raised.exception))

    def test_custom_remote_name_still_matches_credentials_email_without_name_search(self):
        remote = {**self.remote, "name": "自定义名称"}
        def remote_list(url, **kwargs):
            if url.endswith("/41"):
                return self.response(remote)
            items = [] if kwargs.get("params", {}).get("search") else [remote]
            return self.response({"items": items, "pages": 1})
        with patch.object(client.requests, "get", side_effect=remote_list), patch.object(client.requests, "put", return_value=self.response({})) as put, patch.object(client.requests, "post") as post:
            result = client.upload_configured_codex_oauth_credential(self.auth)
        self.assertEqual(result["sub2api_account_id"], 41)
        self.assertEqual(put.call_count, 1)
        post.assert_not_called()

    def test_export_failure_never_exposes_remote_body(self):
        response = self.response({})
        response.json.return_value = {"code": 400, "message": "opaque-secret-value"}
        with patch.object(client.requests, "get", return_value=response):
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.export_configured_accounts()
        self.assertNotIn("opaque-secret-value", str(raised.exception))
        self.assertEqual(raised.exception.stage, "export_accounts")

    def test_initial_import_applies_models_using_native_credential_extras(self):
        with patch.object(client.requests, "post", return_value=self.response({"total": 1, "created": 1, "failed": 0})) as post:
            client.upload_codex_oauth_credential(self.auth, "https://sub2.example/api/v1/admin/accounts/import/codex-session", upload_options={"model_whitelist": ["gpt-a", "gpt-b"]})
        self.assertEqual(post.call_args.kwargs["json"]["credential_extras"], {"model_mapping": {"gpt-a": "gpt-a", "gpt-b": "gpt-b"}})

    def test_unconfirmed_import_counters_do_not_claim_uploaded_fact(self):
        imported = self.response({"total": 1, "created": 0, "updated": 0, "failed": 0})
        with patch.object(client.requests, "get", return_value=self.response({"items": [], "pages": 1})), patch.object(client.requests, "post", return_value=imported):
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.upload_and_enable_configured_codex_oauth_credential(self.auth)
        self.assertEqual(raised.exception.stage, "resolve_account")
        self.assertFalse(raised.exception.uploaded)

    def test_config_capture_waits_for_completed_reload_transaction(self):
        halfway = threading.Event()
        finish_reload = threading.Event()
        requested = threading.Event()
        outcomes = []
        def reload_configuration():
            with config._RELOAD_LOCK:
                cfg.SUB2API_API_BASE = "https://reloaded.example"
                halfway.set()
                finish_reload.wait(2)
                cfg.SUB2API_API_KEY = "reloaded-key"
                cfg.SUB2API_API_TIMEOUT = 36
        def synchronize():
            try:
                outcomes.append(client.update_and_enable_configured_account(self.auth, 41))
            except Exception as exc:
                outcomes.append(exc)
        def read_remote(*args, **kwargs):
            requested.set()
            return self.response(self.remote)
        with patch.object(client.requests, "get", side_effect=read_remote) as get, patch.object(client.requests, "put", return_value=self.response({})), patch.object(client.requests, "post", return_value=self.response({})):
            reload_thread = threading.Thread(target=reload_configuration)
            reload_thread.start()
            self.assertTrue(halfway.wait(2))
            sync_thread = threading.Thread(target=synchronize)
            sync_thread.start()
            try:
                self.assertFalse(requested.wait(0.05), "配置事务未完成时不能发送请求")
            finally:
                finish_reload.set()
                reload_thread.join(2)
                sync_thread.join(2)
        self.assertTrue(outcomes[0]["enabled"])
        self.assertEqual(get.call_args.args[0], "https://reloaded.example/api/v1/admin/accounts/41")
        self.assertEqual(get.call_args.kwargs["headers"]["x-api-key"], "reloaded-key")
        self.assertEqual(get.call_args.kwargs["timeout"], 36)

    def test_monitor_list_rejects_backend_changed_after_identity_capture(self):
        backend = client.configured_backend_identity()
        with patch.object(cfg, "SUB2API_API_BASE", "https://other.example"), patch.object(client.requests, "get") as get:
            with self.assertRaises(client.Sub2ApiSyncError) as raised:
                client.list_configured_error_accounts(expected_backend=backend)
        self.assertEqual(raised.exception.code, "sub2api_backend_changed")
        get.assert_not_called()


def synthetic_jwt(claims):
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def requests_timeout():
    from requests import Timeout
    return Timeout("synthetic-private-key")
