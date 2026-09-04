# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import roxy_registration, roxybrowser_client
from core import registration_debug
from core.roxybrowser_client import RoxyBrowserClient, RoxyOpenResult


class RoxyCapacityWaitTests(unittest.TestCase):
    def test_account_client_waits_for_window_capacity_before_opening(self):
        opened = RoxyOpenResult(profile_id="profile-1", raw={})
        client = RoxyBrowserClient(api_base="http://roxy.example")
        client.open_profile = Mock(side_effect=[
            RuntimeError("Roxy API 返回失败 POST /browser/create: 窗口额度不足"),
            opened,
        ])
        progress = Mock()

        with patch.object(roxybrowser_client._cfg, "ROXY_WINDOW_WAIT_TIMEOUT", 60), patch.object(
            roxybrowser_client._cfg, "ROXY_WINDOW_WAIT_INTERVAL", 10
        ), patch.object(roxybrowser_client.time, "sleep") as wait_sleep:
            result = client.open_profile_with_capacity_wait(
                proxy_url="http://proxy.example:8080",
                progress_callback=progress,
            )

        self.assertIs(result, opened)
        self.assertEqual(client.open_profile.call_count, 2)
        client.open_profile.assert_called_with(proxy_url="http://proxy.example:8080")
        wait_sleep.assert_called_once_with(10.0)
        progress.assert_called_once()

    def test_capacity_error_waits_in_same_worker_then_opens(self):
        opened = RoxyOpenResult(profile_id="profile-1", raw={})
        client = Mock()
        client.open_profile.side_effect = [
            RuntimeError("Roxy API 返回失败 POST /browser/create: 窗口额度不足"),
            opened,
        ]
        progress = Mock()

        with patch.object(roxy_registration._cfg, "ROXY_WINDOW_WAIT_TIMEOUT", 60), patch.object(
            roxy_registration._cfg, "ROXY_WINDOW_WAIT_INTERVAL", 10
        ), patch.object(roxy_registration, "_wait_for_roxy_window_retry") as wait_retry:
            result = roxy_registration._open_roxy_profile_with_capacity_wait(
                client,
                "http://proxy.example:8080",
                progress_callback=progress,
            )

        self.assertIs(result, opened)
        self.assertEqual(client.open_profile.call_count, 2)
        client.open_profile.assert_called_with(proxy_url="http://proxy.example:8080")
        wait_retry.assert_called_once_with(10.0)
        progress.assert_called_once()
        self.assertIn("窗口已满", progress.call_args.args[2])

    def test_non_capacity_error_does_not_wait(self):
        client = Mock()
        client.open_profile.side_effect = RuntimeError("Roxy API 连接失败")

        with patch.object(roxy_registration, "_wait_for_roxy_window_retry") as wait_retry:
            with self.assertRaisesRegex(RuntimeError, "连接失败"):
                roxy_registration._open_roxy_profile_with_capacity_wait(client, None)

        client.open_profile.assert_called_once_with(proxy_url=None)
        wait_retry.assert_not_called()

    def test_failure_only_debug_context_keeps_headless_configuration(self):
        opened = RoxyOpenResult(profile_id="profile-1", raw={})
        client = Mock()
        client.open_profile.return_value = opened

        with patch.object(
            registration_debug,
            "current_session",
            return_value=SimpleNamespace(capture_mode="failure_only"),
        ):
            result = roxy_registration._open_roxy_profile_with_capacity_wait(client, None)

        self.assertIs(result, opened)
        client.open_profile.assert_called_once_with(proxy_url=None)

    def test_full_debug_context_forces_visible_window(self):
        opened = RoxyOpenResult(profile_id="profile-1", raw={})
        client = Mock()
        client.open_profile.return_value = opened

        with patch.object(
            registration_debug,
            "current_session",
            return_value=SimpleNamespace(capture_mode="full"),
        ):
            result = roxy_registration._open_roxy_profile_with_capacity_wait(client, None)

        self.assertIs(result, opened)
        client.open_profile.assert_called_once_with(proxy_url=None, headless=False)

    def test_capacity_wait_has_bounded_timeout(self):
        client = Mock()
        client.open_profile.side_effect = RuntimeError("窗口额度不足")

        with patch.object(roxy_registration._cfg, "ROXY_WINDOW_WAIT_TIMEOUT", 30), patch.object(
            roxy_registration.time, "monotonic", side_effect=[100.0, 131.0]
        ), patch.object(roxy_registration, "_wait_for_roxy_window_retry") as wait_retry:
            with self.assertRaisesRegex(RuntimeError, "等待 Roxy 空闲窗口超时"):
                roxy_registration._open_roxy_profile_with_capacity_wait(client, None)

        wait_retry.assert_not_called()

    def test_manual_stop_interrupts_capacity_wait(self):
        client = Mock()
        client.open_profile.side_effect = RuntimeError("窗口额度不足")

        with patch.object(roxy_registration._cfg, "ROXY_WINDOW_WAIT_TIMEOUT", 60), patch.object(
            roxy_registration, "_wait_for_roxy_window_retry", side_effect=RuntimeError("manual stop")
        ):
            with self.assertRaisesRegex(RuntimeError, "manual stop"):
                roxy_registration._open_roxy_profile_with_capacity_wait(client, None)


if __name__ == "__main__":
    unittest.main()
