# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core import roxybrowser_client
from core.registration import dispatcher
from core.roxybrowser_client import RoxyBrowserClient, RoxyOpenResult


class RoxyProfileLifecycleTests(unittest.TestCase):
    def test_account_profile_reuse_ignores_task_proxy_for_open(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        opened = RoxyOpenResult(profile_id="profile-1", raw={})

        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / "profiles.json"
            with patch.object(roxybrowser_client, "_PROFILE_REGISTRY_PATH", registry), patch.object(
                client, "open_profile_with_capacity_wait", return_value=opened
            ) as open_profile, patch.object(
                client,
                "request",
                return_value={"code": 0, "data": {"rows": [{"dirId": "profile-1", "openStatus": 0}]}},
            ):
                result = client.open_profile_for_account(
                    profile_id="profile-1",
                    proxy_url="http://new-route.example:8080",
                )

        self.assertIs(result, opened)
        open_profile.assert_called_once_with(profile_id="profile-1", proxy_url=None)

    def test_missing_account_profile_creates_replacement_and_does_not_retry_other_open_errors(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        replacement = RoxyOpenResult(profile_id="profile-2", raw={}, created_by_run=True)
        client.open_profile_with_capacity_wait = Mock(side_effect=[
            RuntimeError("Roxy API 返回失败：环境不存在或已删除"),
            replacement,
        ])

        with patch.object(
            client,
            "request",
            return_value={"code": 0, "data": {"rows": [{"dirId": "profile-1", "openStatus": 0}]}},
        ):
            result = client.open_profile_for_account(
                profile_id="profile-1",
                proxy_url="http://new-route.example:8080",
            )

        self.assertIs(result, replacement)
        self.assertEqual(
            client.open_profile_with_capacity_wait.call_args_list,
            [
                (( ), {"profile_id": "profile-1", "proxy_url": None}),
                (( ), {"profile_id": "", "proxy_url": "http://new-route.example:8080"}),
            ],
        )

        client.open_profile_with_capacity_wait = Mock(side_effect=RuntimeError("Roxy API 连接失败"))
        with patch.object(
            client,
            "request",
            return_value={"code": 0, "data": {"rows": [{"dirId": "profile-1", "openStatus": 0}]}},
        ), self.assertRaisesRegex(RuntimeError, "连接失败"):
            client.open_profile_for_account(
                profile_id="profile-1",
                proxy_url="http://new-route.example:8080",
            )
        client.open_profile_with_capacity_wait.assert_called_once_with(profile_id="profile-1", proxy_url=None)

    def test_deleted_bound_profile_is_replaced_before_open(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        replacement = RoxyOpenResult(profile_id="profile-2", raw={}, created_by_run=True)
        client.open_profile_with_capacity_wait = Mock(return_value=replacement)

        with patch.object(client, "request", return_value={"code": 0, "data": {"rows": []}}):
            result = client.open_profile_for_account(
                profile_id="profile-1",
                proxy_url="http://new-route.example:8080",
            )

        self.assertIs(result, replacement)
        client.open_profile_with_capacity_wait.assert_called_once_with(
            profile_id="",
            proxy_url="http://new-route.example:8080",
        )

    def test_profile_probe_error_does_not_create_replacement(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        client.open_profile_with_capacity_wait = Mock()

        with patch.object(client, "request", side_effect=RuntimeError("Roxy API 连接失败")), self.assertRaisesRegex(
            RuntimeError, "连接失败"
        ):
            client.open_profile_for_account(
                profile_id="profile-1",
                proxy_url="http://new-route.example:8080",
            )

        client.open_profile_with_capacity_wait.assert_not_called()

    def test_retained_profile_cleanup_closes_and_untracks_without_delete(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        opened = RoxyOpenResult(profile_id="profile-1", raw={}, created_by_run=True)

        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / "profiles.json"
            registry.write_text(json.dumps({"items": [{"profile_id": "profile-1"}]}), encoding="utf-8")
            with patch.object(roxybrowser_client, "_PROFILE_REGISTRY_PATH", registry), patch.multiple(
                roxybrowser_client._cfg,
                ROXY_KEEP_BROWSER_OPEN=False,
                ROXY_DELETE_PROFILE_AFTER_RUN=False,
            ), patch.object(client, "close_profile", return_value=True) as close_profile, patch.object(
                client, "delete_profile", return_value=True
            ) as delete_profile:
                client.cleanup_profile(opened)

            close_profile.assert_called_once_with("profile-1")
            delete_profile.assert_not_called()
            self.assertEqual(json.loads(registry.read_text(encoding="utf-8"))["items"], [])

    def test_account_bound_profile_is_deleted_when_delete_switch_is_enabled(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        opened = RoxyOpenResult(profile_id="profile-1", raw={}, created_by_run=True, account_bound=True)

        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / "profiles.json"
            registry.write_text(json.dumps({"items": [{"profile_id": "profile-1"}]}), encoding="utf-8")
            with patch.object(roxybrowser_client, "_PROFILE_REGISTRY_PATH", registry), patch.multiple(
                roxybrowser_client._cfg,
                ROXY_KEEP_BROWSER_OPEN=False,
                ROXY_DELETE_PROFILE_AFTER_RUN=True,
            ), patch.object(client, "close_profile", return_value=True) as close_profile, patch.object(
                client, "delete_profile", return_value=True
            ) as delete_profile:
                client.cleanup_profile(opened)

            self.assertEqual(json.loads(registry.read_text(encoding="utf-8"))["items"], [])

        close_profile.assert_called_once_with("profile-1")
        delete_profile.assert_called_once_with("profile-1")

    def test_close_profile_waits_until_roxy_reports_closed(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        responses = [
            {"code": 0},
            {"code": 0, "data": {"rows": [{"dirId": "456", "openStatus": 1}]}},
            {"code": 0, "data": {"rows": [{"dirId": "456", "openStatus": 0}]}},
        ]

        with patch.object(client, "request", side_effect=responses) as request, patch(
            "core.roxybrowser_client.time.sleep"
        ) as sleep:
            self.assertTrue(client.close_profile("456"))

        self.assertEqual(request.call_count, 3)
        self.assertEqual(request.call_args_list[1].args[:2], ("GET", "/browser/list_v2"))
        self.assertEqual(request.call_args_list[1].kwargs["params"]["dirId"], 456)
        self.assertEqual(request.call_args_list[1].kwargs["params"]["isDelete"], 0)
        sleep.assert_called_once()

    def test_close_profile_falls_back_to_deleted_profile_list(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        responses = [
            {"code": 0},
            {"code": 0, "data": {"rows": []}},
            {"code": 0, "data": {"rows": [{"dirId": "456", "openStatus": 0}]}},
        ]

        with patch.object(client, "request", side_effect=responses) as request, patch(
            "core.roxybrowser_client._ROXY_CLOSE_VERIFY_ATTEMPTS", 1
        ), patch("core.roxybrowser_client.time.sleep"):
            self.assertTrue(client.close_profile("456"))

        self.assertEqual(request.call_count, 3)
        self.assertEqual(request.call_args_list[1].kwargs["params"]["isDelete"], 0)
        self.assertEqual(request.call_args_list[2].kwargs["params"]["isDelete"], 1)

    def test_close_profile_fails_when_roxy_never_confirms_closed(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        responses = [
            {"code": 0},
            {"code": 0, "data": {"rows": [{"dirId": "456", "openStatus": 1}]}},
            {"code": 0, "data": {"rows": [{"dirId": "456", "openStatus": 1}]}},
        ]

        with patch.object(client, "request", side_effect=responses), patch(
            "core.roxybrowser_client._ROXY_CLOSE_VERIFY_ATTEMPTS", 2
        ), patch("core.roxybrowser_client.time.sleep"):
            self.assertFalse(client.close_profile("456"))

    def test_lifecycle_defaults_reuse_and_keep_profiles(self):
        from config.schema import DEFAULTS

        self.assertTrue(DEFAULTS["ROXY_REUSE_ACCOUNT_PROFILE"])
        self.assertFalse(DEFAULTS["ROXY_DELETE_PROFILE_AFTER_RUN"])

    def test_delete_failure_keeps_created_profile_in_recovery_registry(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        opened = RoxyOpenResult(profile_id="profile-1", raw={}, created_by_run=True)

        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / "profiles.json"
            registry.write_text(json.dumps({"items": [{"profile_id": "profile-1", "disposable": True}]}), encoding="utf-8")
            with patch.object(roxybrowser_client, "_PROFILE_REGISTRY_PATH", registry), patch.multiple(
                roxybrowser_client._cfg,
                ROXY_KEEP_BROWSER_OPEN=False,
                ROXY_DELETE_PROFILE_AFTER_RUN=True,
            ), patch.object(client, "close_profile", return_value=True), patch.object(
                client, "delete_profile", return_value=False
            ):
                client.cleanup_profile(opened)

            self.assertEqual(
                json.loads(registry.read_text(encoding="utf-8"))["items"],
                [{"profile_id": "profile-1", "disposable": True}],
            )

    def test_startup_never_deletes_legacy_unclassified_registry_item(self):
        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / "profiles.json"
            registry.write_text(json.dumps({"items": [{"profile_id": "legacy-1"}]}), encoding="utf-8")
            with patch.object(roxybrowser_client, "_PROFILE_REGISTRY_PATH", registry), patch.multiple(
                roxybrowser_client._cfg,
                ROXY_KEEP_BROWSER_OPEN=False,
                ROXY_DELETE_PROFILE_AFTER_RUN=True,
            ), patch.object(
                roxybrowser_client.RoxyBrowserClient, "close_profile", return_value=True
            ) as close_profile, patch.object(
                roxybrowser_client.RoxyBrowserClient, "delete_profile", return_value=True
            ) as delete_profile:
                result = roxybrowser_client.cleanup_orphaned_profiles()

            self.assertEqual(result, {"found": 1, "cleaned": 0, "failed": 1})
            close_profile.assert_called_once_with("legacy-1")
            delete_profile.assert_not_called()
            self.assertEqual(json.loads(registry.read_text(encoding="utf-8"))["items"], [{"profile_id": "legacy-1"}])

    def test_startup_deletes_bound_disposable_profile_when_delete_switch_is_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / "profiles.json"
            registry.write_text(
                json.dumps({"items": [{"profile_id": "bound-1", "disposable": True, "account_bound": True}]}),
                encoding="utf-8",
            )
            with patch.object(roxybrowser_client, "_PROFILE_REGISTRY_PATH", registry), patch.multiple(
                roxybrowser_client._cfg,
                ROXY_KEEP_BROWSER_OPEN=False,
                ROXY_DELETE_PROFILE_AFTER_RUN=True,
            ), patch.object(
                roxybrowser_client.RoxyBrowserClient, "close_profile", return_value=True
            ) as close_profile, patch.object(
                roxybrowser_client.RoxyBrowserClient, "delete_profile", return_value=True
            ) as delete_profile:
                result = roxybrowser_client.cleanup_orphaned_profiles()

            self.assertEqual(result, {"found": 1, "cleaned": 1, "failed": 0})
            close_profile.assert_called_once_with("bound-1")
            delete_profile.assert_called_once_with("bound-1")
            self.assertEqual(json.loads(registry.read_text(encoding="utf-8"))["items"], [])

    def test_profile_id_is_read_from_account_metadata_and_non_retained_binding_is_ignored(self):
        from core.roxy_profile_binding import account_profile_id

        retained = {"extra_json": json.dumps({"roxybrowser": {"profile_id": "profile-1"}})}
        deleted = {"extra_json": json.dumps({"roxybrowser": {"profile_id": "profile-1", "retained": False}})}

        self.assertEqual(account_profile_id(retained), "profile-1")
        self.assertEqual(account_profile_id(deleted), "")

    def test_account_profile_update_uses_existing_account_metadata_mutation(self):
        from core.storage import db_legacy

        mutate = Mock(return_value=True)
        with patch.object(db_legacy, "_mutate_account_extra", mutate):
            self.assertTrue(db_legacy.update_account_roxy_profile("user@example.com", "profile-2"))

        mutate.assert_called_once()
        row, extra = {}, {}
        changes = mutate.call_args.args[1](row, extra)
        self.assertEqual(changes, {})
        self.assertEqual(extra["roxybrowser"], {"profile_id": "profile-2", "retained": True})

    def test_dispatcher_forwards_bound_profile_only_to_roxy_driver(self):
        args = {
            "email": "user@example.com",
            "name": "Test User",
            "birthday": "1990-01-01",
            "proxy": "http://proxy.example:8080",
            "otp_code": None,
            "batch_dir": None,
            "profile_id": "profile-1",
        }
        expected = {"success": True}
        with patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "roxybrowser"), patch(
            "core.registration.roxy.run_roxy_registration", return_value=expected
        ) as run_roxy:
            result = dispatcher.run_registration(**args)

        self.assertIs(result, expected)
        self.assertEqual(run_roxy.call_args.kwargs["profile_id"], "profile-1")


if __name__ == "__main__":
    unittest.main()
