"""同一 Attempt 的原浏览器会话恢复：只读核验、未知围栏和共享收尾。"""
from contextlib import ExitStack, contextmanager
import ast
import inspect
import json
import shutil
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.registration import roxy, session_auth


EMAIL = "resume@example.test"
SESSION = {"accessToken": "unit-token", "user": {"email": EMAIL}}


def session_driver(response=None):
    return SimpleNamespace(
        current_url="https://chatgpt.com/complete",
        timeouts=SimpleNamespace(script=12),
        set_script_timeout=Mock(), set_page_load_timeout=Mock(),
        execute_async_script=Mock(return_value=response if response is not None else {
            "ok": True, "status": 200, "json_valid": True, "data": SESSION,
        }),
    )


class ResumeSessionReadTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证空响应体边界")
    def test_browser_empty_body_is_not_a_verified_json_session(self):
        tree = ast.parse(inspect.getsource(session_auth._read_chatgpt_session_once))
        script = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                      and isinstance(n.value, str) and "const timeoutMs" in n.value)
        source = r"""
        (async()=>{
          global.location={origin:'https://chatgpt.com'};
          const results=[];
          for(const body of ['', '   ', '{}']){
            global.fetch=async()=>({status:200,text:async()=>body});
            const result=await new Promise(resolve=>new Function(SCRIPT)(1000,resolve));
            results.push({ok:result.ok,json_valid:result.json_valid});
          }
          console.log(JSON.stringify(results));
        })();
        """.replace("SCRIPT", json.dumps(script))
        result = subprocess.run([shutil.which("node"), "-e", source], capture_output=True,
                                text=True, check=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), [
            {"ok": True, "json_valid": False}, {"ok": True, "json_valid": False},
            {"ok": True, "json_valid": True},
        ])

    def test_explicit_unknown_prefix_is_preserved_for_session_and_profile(self):
        for message in (
            "request_unknown: resume_session_probe_incomplete: 原环境会话读取未完成",
            "request_unknown: 资料提交后的会话读取未完成，已保留原提交",
        ):
            with self.subTest(message=message):
                self.assertTrue(roxy._is_registration_request_unknown(RuntimeError(message)))
        self.assertFalse(roxy._is_registration_request_unknown("普通读取错误"))

    def test_complete_identity_matched_response_is_read_once(self):
        driver = session_driver()
        self.assertIs(roxy._read_registration_resume_session(driver, "Resume@Example.test"), SESSION)
        driver.execute_async_script.assert_called_once()
        self.assertEqual(driver.execute_async_script.call_args.args[1], 30000)
        self.assertEqual([c.args[0] for c in driver.set_script_timeout.call_args_list], [31.0, 12])

    def test_explicit_unauthenticated_responses_allow_normal_login(self):
        for status in (200, 401, 403):
            with self.subTest(status=status):
                driver = session_driver({"ok": True, "status": status, "json_valid": True, "data": {}})
                self.assertIsNone(roxy._read_registration_resume_session(driver, EMAIL))
                driver.execute_async_script.assert_called_once()

    def test_incomplete_or_unverifiable_response_is_unknown(self):
        for response in (
            {"ok": False, "error_type": "timeout"},
            {"ok": False, "error_type": "session_read_failed"},
            {"ok": False, "error_type": "origin_changed"},
            {"ok": True, "status": 500, "data": {}},
            {"ok": True, "status": 200, "json_valid": False, "data": {}},
            {"ok": True, "status": 200, "json_valid": True, "data": []},
        ):
            with self.subTest(response=response), patch.object(roxy, "_check_manual_stop"):
                with self.assertRaisesRegex(RuntimeError, "request_unknown.*resume_session_probe_incomplete"):
                    roxy._read_registration_resume_session(session_driver(response), EMAIL)

    def test_driver_failure_preserves_unknown_and_restores_timeout(self):
        driver = session_driver()
        driver.execute_async_script.side_effect = TimeoutError("unit transport failure")
        with patch.object(roxy, "_check_manual_stop"), self.assertRaisesRegex(RuntimeError, "request_unknown"):
            roxy._read_registration_resume_session(driver, EMAIL)
        self.assertEqual([c.args[0] for c in driver.set_script_timeout.call_args_list], [31.0, 12])
        driver.execute_async_script.assert_called_once()

    def test_missing_and_mismatched_identity_never_fall_back(self):
        for user, marker in (({}, "session_identity_unverified"),
                             ({"email": "other@example.test"}, "session_identity_mismatch")):
            driver = session_driver({"ok": True, "status": 200, "json_valid": True,
                                     "data": {"accessToken": "unit-token", "user": user}})
            with self.subTest(marker=marker), self.assertRaisesRegex(RuntimeError, marker) as raised:
                roxy._read_registration_resume_session(driver, EMAIL)
            self.assertTrue(roxy._is_registration_request_unknown(raised.exception))

    def test_foreign_origin_is_not_probed_and_default_reader_stays_compatible(self):
        driver = session_driver()
        driver.current_url = "https://chatgpt.com.other.test/complete"
        self.assertIsNone(roxy._read_registration_resume_session(driver, EMAIL))
        driver.execute_async_script.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, "request_unknown.*origin_changed"):
            session_auth._read_chatgpt_session_once(driver, timeout=30, strict_read=True)
        driver.current_url = "https://chatgpt.com/"
        driver.execute_async_script.return_value = {"ok": False}
        self.assertIsNone(session_auth._read_chatgpt_session_once(driver, timeout=30))


class ResumeSessionFlowTests(unittest.TestCase):
    @contextmanager
    def run_context(self, *, action="registration_resume", status="running", opened_profile="unit-profile"):
        driver = session_driver()
        opened = SimpleNamespace(profile_id=opened_profile, debugger_address="127.0.0.1:9222",
                                 created_by_run=False, account_bound=True, raw={})
        mocks = {}
        with ExitStack() as stack:
            def mock(name, target, **kwargs):
                mocks[name] = stack.enter_context(patch(target, **kwargs))
                return mocks[name]

            mock("progress", "core.registration_service.report_job_progress")
            mock("otp_evidence", "core.registration_service.report_job_otp_evidence")
            mock("registered", "core.registration_service.report_registered_account")
            mock("stop", "core.registration_service.is_stop_requested", return_value=False)
            mock("context", "core.registration_service.registration_fact_context",
                 return_value={"run_id": 71, "attempt_id": 41, "job_id": 31})
            mock("run", "core.storage.registration.get_run", return_value={"action_type": action, "status": status})
            mock("binding", "core.roxy_profile_binding.persist_account_profile_id", return_value=True)
            mock("attach", "core.registration_debug.attach_current_roxy")
            mock("pause", "core.registration_debug.pause_current_failure")
            mock("capture", "core.browser_traffic.bind_roxy_capture")
            mock("cache_start", "core.browser_asset_policy.start_registration_asset_cache")
            mock("cache_stop", "core.browser_asset_policy.stop_registration_asset_cache")
            mock("observer", "core.registration.password_auth._install_auth_initialization_observer")
            mock("saver", "core.browser_data_saver.BrowserDataSaver")
            mock("plan_install", "core.registration_plan_capture.install_selenium")
            mock("plan_read", "core.registration_plan_capture.read_or_fetch_selenium",
                 return_value={"ok": True, "quota_status": "success"})
            mock("plan_save", "core.db.update_account_plan_check")
            mock("persist", "core.registration_service.persist_registration_core", return_value=19)
            mock("retain", "core.email_provider.retain_email")
            mock("release", "core.email_provider.release_email")
            mock("login", "core.roxy_codex_oauth.complete_openai_login_challenge")
            mock("codex", "core.roxy_codex_oauth.run_roxy_codex_oauth", return_value={"ok": True, "status": "success"})
            for name in ("_center_browser_window", "_page_warmup", "_maybe_accept", "_check_manual_stop",
                         "human_delay", "_submit_email_and_wait_next", "_fill_password_page_if_present",
                         "_has_access_token", "wait_for_otp", "_complete_profile_page", "_fetch_chatgpt_session",
                         "_save_pending_email_verification_checkpoint", "_quit_driver",
                         "_install_registration_postprocess_data_saver"):
                mock(name, f"core.registration.roxy.{name}")
            mock("navigate", "core.registration.roxy._safe_get", side_effect=RuntimeError("unit login reached"))
            mock("client", "core.registration.roxy.RoxyBrowserClient")
            mock("opened", "core.registration.roxy._open_roxy_profile_with_capacity_wait", return_value=opened)
            mock("driver", "core.registration.roxy._build_driver", return_value=driver)
            mock("checkpoint", "core.registration.roxy._save_roxy_account_checkpoint", return_value=19)
            mock("twofa", "core.registration.roxy.setup_roxy_2fa", return_value="unit-totp")
            mock("twofa_driver", "core.registration.roxy._twofa_cfg.get_twofa_driver_for_options", return_value="browser")
            mock("isolated_tab", "core.registration.roxy._run_in_isolated_browser_tab",
                 side_effect=lambda _driver, callback, *, label: callback())
            mock("auth_mode", "core.registration.roxy._registration_auth_mode", return_value="password")
            stack.enter_context(patch.object(roxy._cfg, "ROXY_KEEP_BROWSER_OPEN", True))
            yield driver, mocks

    def run_registration(self, **kwargs):
        args = {"existing_password": "unit-original-password", "profile_id": "unit-profile",
                "email_source": "icloud_hide", "registration_options": {
                    "password_enabled": True, "twofa_enabled": False,
                    "codex_enabled": False, "plan_check_enabled": False}}
        args.update(kwargs)
        return roxy.run_roxy_registration(EMAIL, "Example User", "2000-01-02", **args)

    def test_verified_resume_skips_all_auth_submissions_and_reuses_shared_persist(self):
        with self.run_context() as (driver, mocks):
            result = self.run_registration()
        self.assertTrue(result["success"], result.get("error"))
        self.assertTrue(result["core_persisted"])
        self.assertEqual(result["account_id"], 19)
        driver.execute_async_script.assert_called_once()
        for name in ("navigate", "_submit_email_and_wait_next", "_fill_password_page_if_present", "login",
                     "_has_access_token", "wait_for_otp", "_complete_profile_page", "_fetch_chatgpt_session",
                     "_save_pending_email_verification_checkpoint", "otp_evidence", "release"):
            mocks[name].assert_not_called()
        mocks["persist"].assert_called_once()
        persisted = mocks["persist"].call_args.kwargs
        self.assertEqual(persisted["extra"]["account_password"], "unit-original-password")
        self.assertIs(persisted["chatgpt_session"], SESSION)
        self.assertEqual(driver._registration_fact_context["attempt_id"], 41)
        for stage in ("page", "submit_email", "auth_redirect", "login_password", "email_otp", "profile"):
            states = [call.args[1] for call in mocks["progress"].call_args_list if call.args[0] == stage]
            self.assertEqual(states, ["running", "skipped"] if stage == "page" else ["skipped"], stage)
        for call in mocks["checkpoint"].call_args_list:
            self.assertEqual(call.kwargs["openai_password"], "unit-original-password")

    def test_shared_required_postprocess_still_runs(self):
        with self.run_context() as (_, mocks):
            result = self.run_registration(registration_options={
                "password_enabled": True, "twofa_enabled": True, "codex_enabled": True, "plan_check_enabled": True})
        self.assertTrue(result["success"], result.get("error"))
        self.assertTrue(result["postprocess_success"])
        for name in ("persist", "codex", "twofa", "plan_read", "plan_save"):
            mocks[name].assert_called_once()
        mocks["navigate"].assert_not_called()

    def test_explicit_no_token_resumes_existing_login_path(self):
        for status in (200, 401, 403):
            with self.subTest(status=status), self.run_context() as (driver, mocks):
                driver.execute_async_script.return_value = {"ok": True, "status": status, "data": {}, "json_valid": True}
                self.run_registration()
                mocks["navigate"].assert_called_once()
                mocks["persist"].assert_not_called()

    def test_unverified_resume_never_navigates_or_submits_or_persists(self):
        for response in (
            {"ok": False, "error_type": "timeout"},
            {"ok": True, "status": 200, "data": {"accessToken": "unit-token", "user": {}}},
            {"ok": True, "status": 200, "data": {"accessToken": "unit-token", "user": {"email": "other@example.test"}}},
        ):
            with self.subTest(response=response), self.run_context() as (driver, mocks):
                driver.execute_async_script.return_value = response
                result = self.run_registration()
                self.assertFalse(result["success"])
                self.assertTrue(result["request_unknown"])
                self.assertEqual(result["error_code"], "request_unknown")
                self.assertEqual(result["remote_account_state"], "request_unknown")
                for name in ("navigate", "_submit_email_and_wait_next", "_fill_password_page_if_present", "login",
                             "wait_for_otp", "_complete_profile_page", "persist", "release", "checkpoint"):
                    mocks[name].assert_not_called()
                mocks["retain"].assert_called_once()
                mocks["client"].return_value.discard_profile.assert_not_called()

    def test_fastpath_requires_explicit_active_resume_original_profile_and_password(self):
        for context, args in (
            ({"action": "registration"}, {}), ({"status": "success"}, {}),
            ({}, {"profile_id": None}), ({}, {"existing_password": None}),
            ({"opened_profile": "unit-replacement-profile"}, {}),
        ):
            with self.subTest(context=context, args=args), self.run_context(**context) as (driver, mocks):
                self.run_registration(**args)
                driver.execute_async_script.assert_not_called()
                mocks["navigate"].assert_called_once()
                mocks["persist"].assert_not_called()
