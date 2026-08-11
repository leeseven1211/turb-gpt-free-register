# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor
import json
import tempfile
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

import requests

from core import roxybrowser_client


class RoxyProxyInjectionTests(unittest.TestCase):
    def test_concurrent_profile_creates_are_serialized(self):
        active = 0
        max_active = 0
        state_lock = threading.Lock()

        def fake_request(_client, _method, _path, *, params=None, json_body=None):
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.02)
                return {"data": {"dirId": str((json_body or {}).get("windowName") or "created")}}
            finally:
                with state_lock:
                    active -= 1

        with patch.multiple(
            roxybrowser_client._cfg,
            ROXY_PROFILE_CREATE_PAYLOAD={},
            ROXY_RANDOM_PROFILE_NAME_ON_CREATE=True,
            ROXY_PROFILE_NAME_PREFIX="test",
            ROXY_RANDOM_OS_ON_CREATE=False,
            ROXY_DEFAULT_OS="macOS",
            ROXY_DEFAULT_OS_VERSION="",
            ROXY_WORKSPACE_ID="123",
            ROXY_PROJECT_ID="456",
            ROXY_CREATE_USE_PROXY_POOL=False,
            ROXY_CREATE_METHOD="POST",
            ROXY_CREATE_PATH="/browser/create",
        ), patch.object(
            roxybrowser_client.RoxyBrowserClient,
            "request",
            autospec=True,
            side_effect=fake_request,
        ):
            with ThreadPoolExecutor(max_workers=5) as executor:
                profile_ids = list(executor.map(lambda _: roxybrowser_client.RoxyBrowserClient().create_profile(), range(5)))

        self.assertEqual(len(profile_ids), 5)
        self.assertEqual(max_active, 1)

    def test_create_retries_after_confirmed_timeout_when_unique_name_is_absent(self):
        client = roxybrowser_client.RoxyBrowserClient()
        calls = []

        def fake_request(_method, path, *, params=None, json_body=None):
            calls.append((path, params, json_body))
            if path == "/browser/list_v2":
                return {"code": 0, "data": {"rows": [], "total": 0}}
            create_count = sum(1 for one in calls if one[0] == "/browser/create")
            if create_count == 1:
                raise RuntimeError("Roxy API 返回失败 POST /browser/create: timeout of 15000ms exceeded")
            return {"code": 0, "data": {"dirId": "created-after-retry"}}

        with patch.multiple(
            roxybrowser_client._cfg,
            ROXY_PROFILE_CREATE_PAYLOAD={"windowName": "retry-name"},
            ROXY_RANDOM_PROFILE_NAME_ON_CREATE=False,
            ROXY_RANDOM_OS_ON_CREATE=False,
            ROXY_DEFAULT_OS="macOS",
            ROXY_DEFAULT_OS_VERSION="",
            ROXY_WORKSPACE_ID="123",
            ROXY_PROJECT_ID="456",
            ROXY_CREATE_USE_PROXY_POOL=False,
            ROXY_CREATE_METHOD="POST",
            ROXY_CREATE_PATH="/browser/create",
            ROXY_API_RETRIES=3,
            ROXY_API_RETRY_DELAY=1,
        ), patch.object(client, "request", side_effect=fake_request), patch.object(
            roxybrowser_client.time, "sleep"
        ):
            profile_id = client.create_profile()

        self.assertEqual(profile_id, "created-after-retry")
        self.assertEqual([one[0] for one in calls], ["/browser/create", "/browser/list_v2", "/browser/create"])
        self.assertEqual(calls[0][2]["windowName"], calls[2][2]["windowName"])

    def test_create_reconciles_existing_profile_instead_of_duplicating(self):
        client = roxybrowser_client.RoxyBrowserClient()
        calls = []

        def fake_request(_method, path, *, params=None, json_body=None):
            calls.append(path)
            if path == "/browser/create":
                raise RuntimeError("Roxy API 返回失败 POST /browser/create: timeout of 15000ms exceeded")
            return {
                "code": 0,
                "data": {"rows": [{"dirId": "already-created", "windowName": "same-name"}]},
            }

        with patch.multiple(
            roxybrowser_client._cfg,
            ROXY_PROFILE_CREATE_PAYLOAD={"windowName": "same-name"},
            ROXY_RANDOM_PROFILE_NAME_ON_CREATE=False,
            ROXY_RANDOM_OS_ON_CREATE=False,
            ROXY_DEFAULT_OS="macOS",
            ROXY_DEFAULT_OS_VERSION="",
            ROXY_WORKSPACE_ID="123",
            ROXY_PROJECT_ID="456",
            ROXY_CREATE_USE_PROXY_POOL=False,
            ROXY_CREATE_METHOD="POST",
            ROXY_CREATE_PATH="/browser/create",
            ROXY_API_RETRIES=3,
            ROXY_API_RETRY_DELAY=1,
        ), patch.object(client, "request", side_effect=fake_request):
            profile_id = client.create_profile()

        self.assertEqual(profile_id, "already-created")
        self.assertEqual(calls, ["/browser/create", "/browser/list_v2"])

    def test_create_does_not_retry_ambiguous_client_timeout(self):
        client = roxybrowser_client.RoxyBrowserClient()
        with patch.multiple(
            roxybrowser_client._cfg,
            ROXY_PROFILE_CREATE_PAYLOAD={"windowName": "ambiguous"},
            ROXY_RANDOM_PROFILE_NAME_ON_CREATE=False,
            ROXY_RANDOM_OS_ON_CREATE=False,
            ROXY_DEFAULT_OS="macOS",
            ROXY_DEFAULT_OS_VERSION="",
            ROXY_WORKSPACE_ID="123",
            ROXY_PROJECT_ID="456",
            ROXY_CREATE_USE_PROXY_POOL=False,
            ROXY_CREATE_METHOD="POST",
            ROXY_CREATE_PATH="/browser/create",
            ROXY_API_RETRIES=3,
            ROXY_API_RETRY_DELAY=1,
        ), patch.object(client, "request", side_effect=requests.Timeout("client timeout")) as request:
            with self.assertRaises(requests.Timeout):
                client.create_profile()

        request.assert_called_once()

    def test_concurrent_profile_opens_are_serialized(self):
        active = 0
        max_active = 0
        state_lock = threading.Lock()

        def fake_request(_client, _method, _path, *, params=None, json_body=None):
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.02)
                return {"debuggerAddress": "127.0.0.1:9222"}
            finally:
                with state_lock:
                    active -= 1

        with patch.multiple(
            roxybrowser_client._cfg,
            ROXY_ONE_PROFILE_PER_ACCOUNT=False,
            ROXY_PROFILE_ID="",
            ROXY_OPEN_PATH="/browser/open",
            ROXY_OPEN_EXTRA_PARAMS={},
            ROXY_OPEN_HEADLESS=True,
            ROXY_KEEP_BROWSER_OPEN=False,
            ROXY_OPEN_METHOD="POST",
        ), patch.object(
            roxybrowser_client.RoxyBrowserClient,
            "request",
            autospec=True,
            side_effect=fake_request,
        ):
            with ThreadPoolExecutor(max_workers=5) as executor:
                opened = list(
                    executor.map(
                        lambda i: roxybrowser_client.RoxyBrowserClient().open_profile(profile_id=str(i)),
                        range(1, 6),
                    )
                )

        self.assertEqual(len(opened), 5)
        self.assertEqual(max_active, 1)

    def test_roxy_proxy_info_maps_authenticated_socks5h(self):
        with patch.object(roxybrowser_client._cfg, "ROXY_PROXY_CHECK_CHANNEL", "IPRust.io"):
            proxy_info = roxybrowser_client._proxy_url_to_roxy_info(
                "socks5h://demo%40user:p%40ss@1.2.3.4:1080"
            )

        self.assertEqual(proxy_info["proxyMethod"], "custom")
        self.assertEqual(proxy_info["proxyCategory"], "SOCKS5")
        self.assertEqual(proxy_info["protocol"], "SOCKS5")
        self.assertEqual(proxy_info["host"], "1.2.3.4")
        self.assertEqual(proxy_info["port"], "1080")
        self.assertEqual(proxy_info["proxyUserName"], "demo@user")
        self.assertEqual(proxy_info["proxyPassword"], "p@ss")
        self.assertEqual(proxy_info["checkChannel"], "IPRust.io")

    def test_explicit_task_proxy_is_written_to_new_profile(self):
        client = roxybrowser_client.RoxyBrowserClient()
        with tempfile.TemporaryDirectory() as td:
            with patch.multiple(
                roxybrowser_client._cfg,
                ROXY_ONE_PROFILE_PER_ACCOUNT=True,
                ROXY_PROFILE_ID="",
                ROXY_OPEN_PATH="/browser/open",
                ROXY_OPEN_EXTRA_PARAMS={},
                ROXY_OPEN_HEADLESS=True,
                ROXY_KEEP_BROWSER_OPEN=False,
                ROXY_OPEN_METHOD="POST",
            ), patch.object(
                roxybrowser_client, "_PROFILE_REGISTRY_PATH", Path(td) / "profiles.json"
            ), patch.object(client, "create_profile", return_value="123") as create_profile, patch.object(
                client, "request", return_value={"debuggerAddress": "127.0.0.1:9222"}
            ):
                opened = client.open_profile(proxy_url="http://1.2.3.4:8080")

        self.assertEqual(opened.profile_id, "123")
        proxy_info = create_profile.call_args.kwargs["payload"]["proxyInfo"]
        self.assertEqual(proxy_info["protocol"], "HTTP")
        self.assertEqual(proxy_info["host"], "1.2.3.4")
        self.assertEqual(proxy_info["port"], "8080")

    def test_startup_cleans_registered_orphan_profile(self):
        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / "profiles.json"
            registry.write_text(json.dumps({"items": [{"profile_id": "orphan-1"}]}), encoding="utf-8")
            with patch.object(
                roxybrowser_client, "_PROFILE_REGISTRY_PATH", registry
            ), patch.object(
                roxybrowser_client.RoxyBrowserClient, "close_profile", return_value=True
            ) as close_profile, patch.object(
                roxybrowser_client.RoxyBrowserClient, "delete_profile", return_value=True
            ) as delete_profile:
                result = roxybrowser_client.cleanup_orphaned_profiles()

            self.assertEqual(result, {"found": 1, "cleaned": 1, "failed": 0})
            close_profile.assert_called_once_with("orphan-1")
            delete_profile.assert_called_once_with("orphan-1")
            payload = json.loads(registry.read_text(encoding="utf-8"))
            self.assertEqual(payload["items"], [])

    def test_explicit_task_proxy_rejects_fixed_profile(self):
        client = roxybrowser_client.RoxyBrowserClient()
        with patch.multiple(
            roxybrowser_client._cfg,
            ROXY_ONE_PROFILE_PER_ACCOUNT=False,
            ROXY_PROFILE_ID="fixed-profile",
        ):
            with self.assertRaisesRegex(RuntimeError, "不能复用固定"):
                client.open_profile(proxy_url="http://1.2.3.4:8080")

    def test_task_proxy_wins_over_static_proxy_pool(self):
        client = roxybrowser_client.RoxyBrowserClient()
        task_proxy = roxybrowser_client._proxy_url_to_roxy_info("http://1.2.3.4:8080")
        with patch.multiple(
            roxybrowser_client._cfg,
            ROXY_PROFILE_CREATE_PAYLOAD={"name": "test"},
            ROXY_RANDOM_PROFILE_NAME_ON_CREATE=False,
            ROXY_RANDOM_OS_ON_CREATE=False,
            ROXY_DEFAULT_OS="macOS",
            ROXY_DEFAULT_OS_VERSION="",
            ROXY_WORKSPACE_ID="123",
            ROXY_PROJECT_ID="456",
            ROXY_CREATE_USE_PROXY_POOL=True,
            ROXY_CREATE_METHOD="POST",
            ROXY_CREATE_PATH="/browser/create",
        ), patch("config.proxy.pick_proxy") as pick_proxy, patch.object(
            client,
            "request",
            return_value={"data": {"dirId": "created-profile"}},
        ) as request:
            profile_id = client.create_profile(payload={"proxyInfo": task_proxy})

        self.assertEqual(profile_id, "created-profile")
        pick_proxy.assert_not_called()
        request_body = request.call_args.kwargs["json_body"]
        self.assertEqual(request_body["proxyInfo"], task_proxy)
        self.assertEqual(request_body["windowName"], "test")
        self.assertNotIn("name", request_body)

    def test_delete_profile_uses_recoverable_soft_delete(self):
        client = roxybrowser_client.RoxyBrowserClient()
        with patch.multiple(
            roxybrowser_client._cfg,
            ROXY_DELETE_PATH="/browser/delete",
            ROXY_DELETE_METHOD="POST",
            ROXY_WORKSPACE_ID="123",
        ), patch.object(client, "request", return_value={"code": 0}) as request:
            client.delete_profile("456")

        self.assertEqual(
            request.call_args.kwargs["json_body"],
            {"workspaceId": 123, "dirIds": [456], "isSoftDelete": True},
        )


if __name__ == "__main__":
    unittest.main()
