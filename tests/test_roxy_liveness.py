import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core import browser_flow_policy, roxy_liveness


class RoxyLivenessFlowPolicyTests(unittest.TestCase):
    def _patch_refresh_dependencies(self, *, client, opened, driver, install):
        return (
            patch.object(roxy_liveness, "available", return_value=True),
            patch.object(roxy_liveness, "RoxyBrowserClient", return_value=client),
            patch.object(roxy_liveness, "_build_driver", return_value=driver),
            patch.object(roxy_liveness, "_center_browser_window"),
            patch.object(roxy_liveness, "_safe_get"),
            patch.object(roxy_liveness, "_page_warmup"),
            patch.object(roxy_liveness, "_maybe_accept"),
            patch.object(roxy_liveness, "_page_account_unusable_code", return_value=""),
            patch.object(roxy_liveness, "_enter_existing_account_otp", return_value="logged_in"),
            patch.object(roxy_liveness, "_fetch_chatgpt_session", return_value={"accessToken": "new-at"}),
            patch("core.roxy_profile_binding.account_profile_id_by_email", return_value="profile-1"),
            patch("core.roxy_codex_oauth._account_login_credentials", return_value=("saved-password", "saved-totp")),
            patch.object(browser_flow_policy, "install_for_flow", install),
        )

    def test_refresh_binds_existing_auth_context_and_installs_token_refresh_policy(self):
        opened = SimpleNamespace(profile_id="profile-1", account_bound=True)
        driver = MagicMock()
        client = MagicMock()
        client.open_profile_for_account.return_value = opened
        recorder = MagicMock()
        saver = MagicMock()
        install = MagicMock(return_value=saver)

        patches = self._patch_refresh_dependencies(
            client=client, opened=opened, driver=driver, install=install,
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12]:
            result = roxy_liveness.refresh_access_token(
                "account@example.com",
                proxy="proxy",
                context_recorder=recorder,
            )

        self.assertTrue(result["ok"])
        client.open_profile_for_account.assert_called_once_with(
            profile_id="profile-1",
            proxy_url="proxy",
            data_saver_flow="token_refresh",
        )
        recorder.open_roxy_profile.assert_called_once_with(
            opened,
            route_attempt_no=1,
            proxy_url=None,
            proxy_context=None,
        )
        recorder.finish_roxy_profile.assert_called_once_with(
            opened,
            status="success",
            result_code="authenticated",
        )
        install.assert_called_once_with("token_refresh", opened, driver)
        saver.stop.assert_called_once_with()

    def test_refresh_closes_auth_context_with_safe_failure_code(self):
        opened = SimpleNamespace(profile_id="profile-1", account_bound=True)
        driver = MagicMock()
        client = MagicMock()
        client.open_profile_for_account.return_value = opened
        recorder = MagicMock()
        saver = MagicMock()
        install = MagicMock(return_value=saver)

        patches = self._patch_refresh_dependencies(
            client=client, opened=opened, driver=driver, install=install,
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12], patch.object(
            roxy_liveness,
            "_fetch_chatgpt_session",
            side_effect=RuntimeError("browser session unavailable"),
        ):
            result = roxy_liveness.refresh_access_token(
                "account@example.com",
                context_recorder=recorder,
            )

        self.assertFalse(result["ok"])
        recorder.finish_roxy_profile.assert_called_once_with(
            opened,
            status="failed",
            result_code="failed",
        )
        saver.stop.assert_called_once_with()

    def test_refresh_without_auth_context_binds_token_refresh_capture(self):
        opened = SimpleNamespace(profile_id="profile-1", account_bound=True)
        driver = MagicMock()
        client = MagicMock()
        client.open_profile_for_account.return_value = opened
        saver = MagicMock()
        install = MagicMock(return_value=saver)

        patches = self._patch_refresh_dependencies(
            client=client, opened=opened, driver=driver, install=install,
        )
        with (
            patches[0], patches[1], patches[2], patches[3], patches[4], patches[5],
            patches[6], patches[7], patches[8], patches[9], patches[10], patches[11],
            patches[12], patch("core.browser_traffic.bind_roxy_capture") as bind_capture,
        ):
            result = roxy_liveness.refresh_access_token("account@example.com", proxy="proxy")

        self.assertTrue(result["ok"])
        bind_capture.assert_called_once_with(opened, purpose="token_refresh")
        saver.stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
