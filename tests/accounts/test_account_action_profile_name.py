"""账号配置落到资料页时复用正常姓名规则，禁止 UUID 数字姓名。"""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.codex.roxy import oauth


class AccountActionProfileNameTests(unittest.TestCase):
    def _run_action(self, url, *, generated_name="Alice Smith", expected_error=False,
                    allow_passwordless_fallback=False):
        opened = SimpleNamespace(profile_id="unit-profile", debugger_address="127.0.0.1:9222",
                                 raw={}, account_bound=True)
        driver = Mock(current_url=url)
        client = Mock()
        client.open_profile_for_account.return_value = opened
        session_info = {"user": {"name": "fixture-session"}}
        action = Mock(return_value={"ok": True})
        with ExitStack() as stack:
            stack.enter_context(patch.object(oauth, "RoxyBrowserClient", return_value=client))
            stack.enter_context(patch("core.browser.roxy.profile_binding.account_profile_id_by_email", return_value="unit-profile"))
            stack.enter_context(patch.object(oauth, "_build_driver", return_value=driver))
            for name in ("_center_browser_window", "clear_roxy_browser_auth_state", "_quit_driver"):
                stack.enter_context(patch.object(oauth, name))
            fill_email = stack.enter_context(patch.object(oauth, "_fill_email_and_otp"))
            stack.enter_context(patch.object(oauth, "_detect_browser_kind", return_value="Roxy"))
            stack.enter_context(patch.object(oauth._roxy_cfg, "ROXY_KEEP_BROWSER_OPEN", False))
            for target in (
                "core.browser.traffic.bind_roxy_capture", "core.browser.traffic.finish_roxy_capture",
                "core.browser.flow_policy.install_for_flow", "core.browser.asset_policy.start_auth_asset_cache",
                "core.browser.asset_policy.stop_asset_cache", "core.registration.debug.attach_current_roxy",
                "core.registration.debug.pause_current_failure",
            ):
                stack.enter_context(patch(target))
            stack.enter_context(patch("core.registration.debug.current_session", return_value=None))
            generate_name = stack.enter_context(patch(
                "core.registration.name_samples.random_display_name", return_value=generated_name,
            ))
            generate_birthday = stack.enter_context(patch(
                "core.registration.profile_utils.generate_random_birthday", return_value="1997-05-09",
            ))
            complete_profile = stack.enter_context(patch(
                "core.auth.browser.selenium_auth.complete_profile_page", return_value=True,
            ))
            fetch_session = stack.enter_context(patch(
                "core.auth.browser.selenium_auth.fetch_chatgpt_session", return_value=session_info,
            ))
            if expected_error:
                with self.assertRaisesRegex(ValueError, "姓名"):
                    oauth.run_roxy_chatgpt_account_action("unit@example.test", action=action)
                complete_profile.assert_not_called()
                fetch_session.assert_not_called()
                action.assert_not_called()
            else:
                result = oauth.run_roxy_chatgpt_account_action(
                    "unit@example.test", action=action, allow_passwordless_fallback=allow_passwordless_fallback,
                )
                self.assertEqual(result, {"ok": True})
                action.assert_called_once_with(driver, session_info)
                self.assertEqual(bool(fill_email.call_args.kwargs.get("allow_passwordless_fallback")),
                                 allow_passwordless_fallback)
        return driver, generate_name, generate_birthday, complete_profile

    def test_profile_page_uses_the_normal_display_name_generator(self):
        driver, name, birthday, profile = self._run_action("https://auth.openai.com/about-you")
        name.assert_called_once_with()
        birthday.assert_called_once_with()
        profile.assert_called_once_with(driver, "Alice Smith", "1997-05-09", timeout=60)
        self.assertRegex(profile.call_args.args[1], r"^[A-Za-z ]+$")

    def test_existing_session_does_not_generate_or_submit_profile(self):
        _, name, birthday, profile = self._run_action("https://chatgpt.com/")
        name.assert_not_called()
        birthday.assert_not_called()
        profile.assert_not_called()

    def test_explicit_password_setup_passes_email_fallback_to_login(self):
        self._run_action("https://chatgpt.com/", allow_passwordless_fallback=True)

    def test_invalid_generated_name_is_rejected_before_profile_submission(self):
        for invalid in ("User8490f0fe", "Alice1 Smith", "", " ", None):
            with self.subTest(name=invalid):
                self._run_action("https://auth.openai.com/about-you", generated_name=invalid, expected_error=True)
