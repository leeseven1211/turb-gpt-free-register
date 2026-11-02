"""显式换国重跑必须给原 Profile 写入本轮线路，不能接管旧代理窗口。"""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.browser.roxy.client import RoxyBrowserClient
from core.registration import retained_resume, roxy
from tests.registration import test_registration_resume_session as resume_fixture


class _OpenedForTest(Exception):
    pass


class RoxyRetryCountryTests(unittest.TestCase):
    @contextmanager
    def context(self, *, close_confirmed=True, reuse_enabled=True, profile_exists=True):
        client = RoxyBrowserClient(api_base="http://roxy.example.test")
        events = []
        candidate = SimpleNamespace(
            driver=SimpleNamespace(current_url="https://auth.openai.com/email-verification"),
            opened=SimpleNamespace(profile_id="original-profile", proxy_route_retained=True),
            otp_after_ts=1234.5,
        )
        with ExitStack() as stack:
            stack.enter_context(patch("core.registration.service.report_job_progress"))
            stack.enter_context(patch("core.registration.service.registration_fact_context", return_value={
                "job_id": 31, "run_id": 71, "attempt_id": 41, "execution_id": "new-run",
            }))
            stack.enter_context(patch.object(roxy, "_registration_auth_mode", return_value="password"))
            stack.enter_context(patch.object(roxy, "_check_manual_stop"))
            stack.enter_context(patch.object(roxy, "RoxyBrowserClient", return_value=client))
            take = stack.enter_context(patch.object(roxy, "take_failed_browser", return_value=candidate))
            stack.enter_context(patch.object(client, "_find_active_profile_by_id", return_value=(
                {"dirId": "original-profile"} if profile_exists else None
            )))
            close = stack.enter_context(patch.object(client, "close_profile", side_effect=lambda profile: (
                events.append(("close", profile)), close_confirmed,
            )[1]))
            modify = stack.enter_context(patch.object(client, "request", side_effect=lambda *_args, **kwargs: (
                events.append(("modify", kwargs["json_body"])), {"code": 0},
            )[1]))
            opened = stack.enter_context(patch.object(client, "open_profile_with_capacity_wait", side_effect=lambda **kwargs: (
                events.append(("open", kwargs)), (_ for _ in ()).throw(_OpenedForTest()),
            )[1]))
            retained = stack.enter_context(patch.object(client, "attach_retained_profile_relay", side_effect=_OpenedForTest))
            stack.enter_context(patch("core.proxy.chain.open_browser_proxy", return_value=("http://127.0.0.1:13001", None)))
            stack.enter_context(patch("core.browser.roxy.client._close_profile_relay"))
            stack.enter_context(patch("core.browser.roxy.client._remember_profile_relay"))
            stack.enter_context(patch.object(roxy._cfg, "ROXY_REUSE_ACCOUNT_PROFILE", reuse_enabled))
            yield SimpleNamespace(client=client, candidate=candidate, take=take, close=close,
                                  modify=modify, opened=opened, retained=retained, events=events)

    @staticmethod
    def run_registration(*, country_override=True, profile_id="original-profile"):
        options = {"password_enabled": True, "twofa_enabled": False, "codex_enabled": False,
                   "plan_check_enabled": False, "proxy_country": "JP"}
        if country_override:
            options["retry_proxy_country_override"] = "JP"
        return roxy.run_roxy_registration(
            "held@example.test", "Original Name", "2000-01-02", proxy="http://jp.example.test:8080",
            existing_password="OriginalSavedPassword!123", profile_id=profile_id,
            registration_options=options,
        )

    def test_explicit_country_reopens_original_profile_after_updating_only_proxy(self):
        with self.context() as state, self.assertRaises(_OpenedForTest):
            self.run_registration()
        state.retained.assert_not_called()
        self.assertEqual([event[0] for event in state.events], ["close", "modify", "open"])
        self.assertEqual(state.events[0][1], "original-profile")
        body = state.events[1][1]
        self.assertEqual(body["dirId"], "original-profile")
        self.assertEqual(set(body), {"workspaceId", "dirId", "proxyInfo"})
        self.assertEqual(body["proxyInfo"]["host"], "127.0.0.1")
        self.assertEqual(state.events[2][1]["profile_id"], "original-profile")
        self.assertIsNone(state.events[2][1]["proxy_url"])

    def test_explicit_country_recovers_profile_from_original_attempt_window(self):
        with self.context() as state, self.assertRaises(_OpenedForTest):
            self.run_registration(profile_id=None)
        state.retained.assert_not_called()
        self.assertEqual(state.events[0], ("close", "original-profile"))
        self.assertEqual(state.events[2][1]["profile_id"], "original-profile")

    def test_explicit_country_keeps_original_profile_when_global_reuse_is_disabled(self):
        with self.context(reuse_enabled=False) as state, self.assertRaises(_OpenedForTest):
            self.run_registration()
        state.retained.assert_not_called()
        self.assertEqual([event[0] for event in state.events], ["close", "modify", "open"])
        self.assertEqual(state.events[2][1]["profile_id"], "original-profile")
        self.assertIsNone(state.events[2][1]["proxy_url"])

    def test_confirmed_missing_original_profile_creates_replacement_on_current_jp_route(self):
        with self.context(profile_exists=False) as state, self.assertRaises(_OpenedForTest):
            self.run_registration()
        state.retained.assert_not_called()
        state.close.assert_not_called()
        state.modify.assert_not_called()
        state.opened.assert_called_once_with(profile_id="", proxy_url="http://jp.example.test:8080",
                                             data_saver_flow="registration")

    def test_original_profile_explicitly_not_found_during_open_creates_replacement(self):
        with self.context() as state:
            state.opened.side_effect = [RuntimeError("profile not found"), _OpenedForTest()]
            with self.assertRaises(_OpenedForTest):
                self.run_registration()
        self.assertEqual(state.opened.call_count, 2)
        self.assertEqual(state.opened.call_args_list[0].kwargs["profile_id"], "original-profile")
        self.assertEqual(state.opened.call_args_list[1].kwargs["profile_id"], "")
        self.assertEqual(state.opened.call_args_list[1].kwargs["proxy_url"], "http://jp.example.test:8080")

    def test_generic_open_failure_never_creates_replacement(self):
        with self.context() as state:
            state.opened.side_effect = RuntimeError("connection failed")
            with self.assertRaisesRegex(RuntimeError, "connection failed"):
                self.run_registration()
        self.assertEqual(state.opened.call_count, 1)
        self.assertEqual(state.opened.call_args.kwargs["profile_id"], "original-profile")

    def test_unconfirmed_window_close_never_modifies_proxy_or_opens(self):
        with self.context(close_confirmed=False) as state:
            with self.assertRaisesRegex(RuntimeError, "关闭未确认"):
                self.run_registration()
        state.retained.assert_not_called()
        state.modify.assert_not_called()
        state.opened.assert_not_called()

    def test_ordinary_retry_keeps_existing_window_and_route(self):
        with self.context() as state, self.assertRaises(_OpenedForTest):
            self.run_registration(country_override=False)
        state.retained.assert_called_once()
        state.close.assert_not_called()
        state.modify.assert_not_called()
        state.opened.assert_not_called()


class RoxyReopenedIdentityTests(unittest.TestCase):
    run_context = resume_fixture.ResumeSessionFlowTests.run_context
    run_registration = resume_fixture.ResumeSessionFlowTests.run_registration

    @contextmanager
    def reopened_context(self, *, private_password="unit-original-password", page_email=None, pending=True):
        with self.run_context() as (old_driver, mocks), ExitStack() as stack:
            new_driver = resume_fixture.session_driver()
            new_driver.current_url = "https://auth.openai.com/email-verification"
            old_driver._registration_otp_after_ts = 1234.5
            receipt = roxy.BrowserSubmissionReceipt(
                submission_id="original-unknown-otp", kind="otp", stage="email_otp",
                phase="unknown", endpoint_kind="otp_submit", http_method="POST",
            )
            old_driver._browser_submission_receipt = receipt
            old_driver._browser_submission_receipts = [receipt]
            old_driver._registration_otp_tracker = {"original-code-hash"}
            candidate = SimpleNamespace(driver=old_driver, opened=mocks["opened"].return_value, otp_after_ts=1234.5)
            mocks["take_default"].return_value = candidate
            mocks["driver"].return_value = new_driver
            facts = [{"submission_id": receipt.submission_id, "kind": "otp", "stage": "email_otp",
                      "phase": "unknown", "endpoint_kind": "otp_submit", "http_method": "POST"}] if pending else []
            mocks["private"].return_value = {"password": private_password, "submission_facts": facts}
            saved_boundaries = []
            mocks["browser_resume_persist"].side_effect = lambda driver, *_args, **_kwargs: saved_boundaries.append(
                getattr(driver, "_registration_otp_after_ts", None))
            stack.enter_context(patch.object(roxy, "_read_registration_resume_session", return_value=None))
            snapshot = {"url": new_driver.current_url, "text": page_email or resume_fixture.EMAIL,
                        "inputs": [{"name": "code", "autocomplete": "one-time-code", "visible": True}]}
            stack.enter_context(patch.object(retained_resume, "_email_otp_page_state", return_value=snapshot))
            stack.enter_context(patch.object(retained_resume, "_check_manual_stop"))
            confirmations = stack.enter_context(patch.object(retained_resume, "record_browser_submission_fact"))
            prepare = stack.enter_context(patch.object(roxy, "prepare_retained_resume", wraps=retained_resume.prepare_retained_resume))
            # 停在 OTP 后续观察点，避免测试继续读取邮件或提交认证表单。
            stack.enter_context(patch.object(roxy, "_wait_email_otp_page_ready", side_effect=RuntimeError("unit OTP observation stop")))
            yield SimpleNamespace(old_driver=old_driver, driver=new_driver, mocks=mocks, prepare=prepare,
                                  confirmations=confirmations, receipt=receipt, private_facts=facts,
                                  saved_boundaries=saved_boundaries, snapshot=snapshot, candidate=candidate)

    def run_reopened(self):
        return self.run_registration(registration_options={
            "password_enabled": True, "twofa_enabled": False, "codex_enabled": False,
            "plan_check_enabled": False, "proxy_country": "JP", "retry_proxy_country_override": "JP",
        })

    def assert_no_submission(self, state):
        for name in ("_submit_email_and_wait_next", "_fill_password_page_if_present", "wait_for_otp", "_complete_profile_page"):
            state.mocks[name].assert_not_called()
        state.confirmations.assert_not_called()
        self.assertEqual(state.receipt.phase, "unknown")

    def test_reopened_profile_rejects_private_password_conflict_before_submission(self):
        with self.reopened_context(private_password="different-private-password") as state:
            result = self.run_reopened()
        self.assertFalse(result["success"])
        self.assertIn("原任务密码与恢复凭据不一致", result["error"])
        self.assertTrue(result["current_lease_route_verified"])
        state.mocks["navigate"].assert_not_called()
        self.assert_no_submission(state)

    def test_reopened_profile_rejects_visible_foreign_email_before_submission(self):
        with self.reopened_context(page_email="other@example.test") as state:
            result = self.run_reopened()
        self.assertFalse(result["success"])
        self.assertIn("邮箱身份与原任务不一致", result["error"])
        state.mocks["navigate"].assert_not_called()
        self.assert_no_submission(state)

    def test_reopened_profile_rejects_untrusted_page_before_submission(self):
        with self.reopened_context() as state:
            state.snapshot["url"] = "https://untrusted.example.test/email-verification"
            result = self.run_reopened()
        self.assertFalse(result["success"])
        self.assertIn("原窗口来源无法核验", result["error"])
        state.mocks["navigate"].assert_not_called()
        self.assert_no_submission(state)

    def test_reopened_profile_preserves_original_otp_boundary_before_persist_and_prepare(self):
        with self.reopened_context(pending=False) as state:
            self.run_reopened()
        state.prepare.assert_called_once()
        self.assertEqual(state.prepare.call_args.kwargs["otp_after_ts"], 1234.5)
        self.assertTrue(state.driver._registration_retained_identity_required)
        self.assertTrue(state.saved_boundaries)
        self.assertTrue(all(value == 1234.5 for value in state.saved_boundaries))
        self.assertEqual(state.driver._registration_otp_after_ts, 1234.5)

    def test_reopened_unknown_otp_uses_new_login_without_confirming_old_post(self):
        with self.reopened_context() as state:
            self.run_reopened()
        state.prepare.assert_called_once()
        self.assertIs(state.driver._browser_submission_receipt, state.receipt)
        state.mocks["navigate"].assert_called_once()
        self.assert_no_submission(state)
        self.assertEqual(state.private_facts[0]["phase"], "unknown")

    def test_reopened_profile_without_visible_email_restarts_login_without_old_confirmation(self):
        with self.reopened_context() as state:
            state.snapshot["text"] = ""
            self.run_reopened()
        self.assertTrue(state.driver._registration_retained_identity_required)
        state.mocks["navigate"].assert_called_once()
        self.assert_no_submission(state)

    def test_reopened_profile_without_old_driver_restores_unknown_receipt_from_private_facts(self):
        with self.reopened_context() as state:
            state.candidate.driver = None
            self.run_reopened()
        state.prepare.assert_called_once()
        self.assertEqual(state.prepare.call_args.kwargs["otp_after_ts"], 1234.5)
        restored = state.driver._browser_submission_receipts
        self.assertEqual([(item.submission_id, item.phase) for item in restored], [("original-unknown-otp", "unknown")])
        self.assertTrue(all(value == 1234.5 for value in state.saved_boundaries[:1]))
        self.assert_no_submission(state)


if __name__ == "__main__":
    unittest.main()
