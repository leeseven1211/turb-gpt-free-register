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

from core.registration import password_auth, roxy, session_auth
from core.registration.state_machine import StageBudget


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
    def test_explicit_resume_can_leave_native_page_reached_during_session_probe(self):
        for native_url in ("chrome-error://chromewebdata/", "about:blank"):
            with self.subTest(native_url=native_url):
                driver = session_driver()
                driver._registration_resume_login = True
                def fail_after_origin_change(_driver, **_kwargs):
                    driver.current_url = native_url
                    raise RuntimeError("request_unknown: origin_changed")
                with patch.object(session_auth, "_read_chatgpt_session_once", side_effect=fail_after_origin_change) as read:
                    self.assertIsNone(roxy._read_registration_resume_session(driver, EMAIL))
                read.assert_called_once()

    def test_native_page_after_probe_failure_is_not_a_general_retry_escape(self):
        cases = [(False, "chrome-error://chromewebdata/"), (False, "about:blank"),
                 (True, "https://other.example.test/"), (True, "chrome-error://other/"),
                 (True, "about:blank?redirect=other"), (True, "https://chatgpt.com/complete")]
        for explicit_resume, changed_url in cases:
            with self.subTest(explicit_resume=explicit_resume, changed_url=changed_url):
                driver = session_driver()
                driver._registration_resume_login = explicit_resume
                def fail_after_origin_change(_driver, **_kwargs):
                    driver.current_url = changed_url
                    raise RuntimeError("request_unknown: origin_changed")
                with (patch.object(session_auth, "_read_chatgpt_session_once", side_effect=fail_after_origin_change),
                      self.assertRaisesRegex(RuntimeError, "resume_session_probe_incomplete")):
                    roxy._read_registration_resume_session(driver, EMAIL)

    def test_explicit_resume_callback_error_reaches_login_recovery_without_session_probe(self):
        for explicit_resume in (True, False):
            with self.subTest(explicit_resume=explicit_resume):
                driver = session_driver()
                driver.current_url = "https://chatgpt.com/auth/error?error=OAuthCallback"
                driver._registration_resume_login = explicit_resume
                with patch.object(session_auth, "_read_chatgpt_session_once", return_value=None) as read:
                    self.assertIsNone(roxy._read_registration_resume_session(driver, EMAIL))
                self.assertEqual(read.call_count, 0 if explicit_resume else 1)

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

    def test_confirmation_session_read_uses_only_remaining_otp_budget(self):
        driver = session_driver()
        budget = roxy.StageBudget(2.0, clock=lambda: 0.0)
        self.assertIs(roxy._read_registration_resume_session(driver, EMAIL, budget=budget), SESSION)
        self.assertEqual(driver.execute_async_script.call_args.args[1], 2000)
        self.assertEqual(driver.set_script_timeout.call_args_list[0].args[0], 3.0)
        expired_driver = session_driver()
        with patch.object(roxy, "_check_manual_stop"), self.assertRaisesRegex(RuntimeError, "request_unknown"):
            roxy._read_registration_resume_session(expired_driver, EMAIL, budget=roxy.StageBudget(0, clock=lambda: 0.0))
        expired_driver.execute_async_script.assert_not_called()

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
            mock("private", "core.storage.registration.get_private_resume_context", return_value={
                "password": "unit-original-password", "submission_facts": [],
            })
            mock("take_default", "core.registration.roxy.take_failed_browser", return_value=None)
            mock("attempt_default", "core.registration.roxy.recover_attempt_failed_browser", return_value=None, create=True)
            mock("bound_default", "core.registration.roxy.recover_bound_failed_browser", return_value=None, create=True)
            mock("browser_resume_persist", "core.registration.roxy.persist_browser_resume_context", return_value=True, create=True)
            mock("retain_default", "core.registration.roxy.retain_failed_browser", return_value=False)
            mock("binding", "core.roxy_profile_binding.persist_account_profile_id", return_value=True)
            mock("attach", "core.registration_debug.attach_current_roxy")
            mock("pause", "core.registration_debug.pause_current_failure")
            mock("capture", "core.browser_traffic.bind_roxy_capture")
            mock("cache_start", "core.browser_asset_policy.start_registration_asset_cache")
            mock("cache_stop", "core.browser_asset_policy.stop_registration_asset_cache")
            mock("observer", "core.registration.password_auth._install_auth_initialization_observer")
            mock("saver", "core.browser_data_saver.BrowserDataSaver")
            mocks["saver"].return_value.enabled = False
            mock("plan_install", "core.registration_plan_capture.install_selenium")
            mock("plan_read", "core.registration_plan_capture.read_or_fetch_selenium",
                 return_value={"ok": True, "quota_status": "success"})
            mock("plan_cached", "core.registration_plan_capture.read_selenium", return_value=None)
            mock("plan_save", "core.db.update_account_plan_check")
            mock("plan_enqueue", "core.plan_check_service.enqueue_account_plan_check", return_value={"accepted": True})
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
        args = {"proxy": "http://pool.example:8080", "existing_password": "unit-original-password", "profile_id": "unit-profile",
                "email_source": "icloud_hide", "registration_options": {
                    "password_enabled": True, "twofa_enabled": False,
                    "codex_enabled": False, "plan_check_enabled": False}}
        args.update(kwargs)
        return roxy.run_roxy_registration(args.pop("email", EMAIL), "Example User", "2000-01-02", **args)

    def test_fresh_resume_login_get_transport_failure_has_explicit_route_proof(self):
        with self.run_context() as (driver, mocks):
            driver.current_url = "https://auth.openai.com/log-in"
            mocks["navigate"].side_effect = RuntimeError("net::ERR_TUNNEL_CONNECTION_FAILED")
            result = self.run_registration()
        self.assertIs(result.get("proxy_transport_failure"), True)
        self.assertIs(result.get("current_lease_route_verified"), True)
        self.assertIs(result.get("resume_login_get_transport_failure"), True)
        mocks["_submit_email_and_wait_next"].assert_not_called()
        mocks["_fill_password_page_if_present"].assert_not_called()

    def test_login_get_http_and_budget_failures_do_not_fault_the_proxy(self):
        for error in ("HTTP 400", "HTTP 403", "StageTimeout: budget exhausted",
                      "net::ERR_TIMED_OUT", "chrome-error://chromewebdata/", "找不到邮箱输入框"):
            with self.subTest(error=error), self.run_context() as (driver, mocks):
                driver.current_url = "https://auth.openai.com/log-in"
                mocks["navigate"].side_effect = RuntimeError(error)
                result = self.run_registration()
                self.assertIs(result.get("proxy_transport_failure"), False)
                self.assertIs(result.get("resume_login_get_transport_failure"), False)

    def test_ordinary_registration_get_cannot_claim_resume_retry_permission(self):
        with self.run_context(action="registration") as (driver, mocks):
            driver.current_url = "https://auth.openai.com/log-in"
            mocks["navigate"].side_effect = RuntimeError("net::ERR_PROXY_CONNECTION_FAILED")
            result = self.run_registration(existing_password=None)
        self.assertIs(result.get("proxy_transport_failure"), True)
        self.assertIs(result.get("resume_login_get_transport_failure"), False)

    def test_transport_failure_after_email_submission_cannot_claim_get_only_phase(self):
        with self.run_context() as (driver, mocks):
            driver.current_url = "https://auth.openai.com/log-in"
            mocks["navigate"].side_effect = None
            def dispatched_then_failed(*_args, **_kwargs):
                from core.registration.browser_submission import BrowserSubmissionReceipt
                driver._browser_submission_receipt = BrowserSubmissionReceipt(
                    kind="resume_login", stage="submit_email", endpoint_kind="email_submit",
                    phase="ui_dispatched", http_method="POST",
                )
                raise RuntimeError("net::ERR_CONNECTION_RESET")
            mocks["_submit_email_and_wait_next"].side_effect = dispatched_then_failed
            result = self.run_registration()
        mocks["_submit_email_and_wait_next"].assert_called_once()
        self.assertEqual(driver._browser_submission_receipt.phase, "ui_dispatched")
        self.assertIs(result.get("proxy_transport_failure"), True)
        self.assertIs(result.get("resume_login_get_transport_failure"), False)

    def test_retained_route_never_faults_unrelated_new_lease(self):
        with self.run_context() as (driver, mocks):
            driver.current_url = "https://auth.openai.com/log-in"
            mocks["take_default"].return_value = SimpleNamespace(
                driver=driver, opened=mocks["opened"].return_value, otp_after_ts=123.0,
            )
            mocks["navigate"].side_effect = RuntimeError("net::ERR_TUNNEL_CONNECTION_FAILED")
            with patch.object(roxy, "prepare_retained_resume", return_value=SimpleNamespace(
                password="unit-original-password", restart_login=True,
            )):
                result = self.run_registration()
        self.assertIs(result.get("proxy_transport_failure"), True)
        self.assertIs(result.get("current_lease_route_verified"), False)
        self.assertIs(result.get("resume_login_get_transport_failure"), False)

    @staticmethod
    def rotation_context(*, retry_available=True, reopen_profile_id=""):
        return {"job_id": 31, "attempt_id": 41, "run_id": 71, "execution_id": "rotation-execution",
                "retry_available": retry_available, "reopen_profile_id": reopen_profile_id}

    def enable_rotation_context(self, mocks):
        context = {key: value for key, value in self.rotation_context().items()
                   if key in {"job_id", "attempt_id", "run_id", "execution_id"}}
        mocks["context"].return_value = context
        mocks["run"].return_value = {**context, "id": 71, "action_type": "registration_resume", "status": "running"}

    def test_bound_profile_rotation_closes_failed_connection_then_opens_new_lease(self):
        from core.registration.browser_submission import BrowserSubmissionReceipt
        with self.run_context() as (driver, mocks):
            self.enable_rotation_context(mocks)
            driver.current_url = "https://auth.openai.com/log-in"
            old = BrowserSubmissionReceipt(kind="profile", stage="profile", phase="unknown")
            driver._browser_submission_receipts = [old]
            mocks["client"].return_value.close_profile.return_value = True
            mocks["navigate"].side_effect = RuntimeError("net::ERR_TUNNEL_CONNECTION_FAILED")
            options = {"password_enabled": True, "twofa_enabled": False,
                       "codex_enabled": False, "plan_check_enabled": False,
                       "_resume_proxy_rotation": self.rotation_context()}
            debug = SimpleNamespace(capture_mode="full", capture_page_snapshot=Mock())
            with patch("core.registration_debug.current_session", return_value=debug):
                first = self.run_registration(registration_options=options)
            self.assertIs(first.get("resume_proxy_rotation_ready"), True)
            self.assertEqual(first.get("resume_proxy_rotation_profile_id"), "unit-profile")
            mocks["client"].return_value.close_profile.assert_called_once_with("unit-profile")
            mocks["client"].return_value.cleanup_profile.assert_not_called()
            mocks["client"].return_value.discard_profile.assert_not_called()
            mocks["retain_default"].assert_not_called()
            mocks["pause"].assert_not_called()
            debug.capture_page_snapshot.assert_called_once()
            # 当前 Run 的持久窗口关联仍可能指向刚关闭的连接；下一圈只凭已核验
            # 的临时重开事实跳过连接恢复，不能再拿回旧线路。
            for name in ("take_default", "attempt_default", "bound_default"):
                mocks[name].side_effect = AssertionError("换线重开不能接管刚关闭的旧连接")
            options["_resume_proxy_rotation"] = self.rotation_context(
                retry_available=False, reopen_profile_id=first["resume_proxy_rotation_profile_id"],
            )
            mocks["navigate"].side_effect = RuntimeError("HTTP 400")
            second = self.run_registration(proxy="http://new-pool.example:8080", registration_options=options)
            self.assertIs(second.get("current_lease_route_verified"), True)
            self.assertIs(second.get("resume_proxy_rotation_ready"), False)
            self.assertEqual(mocks["opened"].call_count, 2)
            self.assertEqual(mocks["opened"].call_args.args[1], "http://new-pool.example:8080")
            self.assertEqual(mocks["opened"].call_args.kwargs["profile_id"], "unit-profile")
            self.assertEqual(old.phase, "unknown")

    def test_unconfirmed_close_keeps_failure_window_and_does_not_offer_rotation(self):
        with self.run_context() as (driver, mocks):
            self.enable_rotation_context(mocks)
            driver.current_url = "https://auth.openai.com/log-in"
            mocks["client"].return_value.close_profile.return_value = False
            mocks["navigate"].side_effect = RuntimeError("net::ERR_PROXY_CONNECTION_FAILED")
            result = self.run_registration(registration_options={"_resume_proxy_rotation": self.rotation_context()})
        self.assertIs(result.get("resume_proxy_rotation_ready"), False)
        mocks["pause"].assert_called_once()
        mocks["retain_default"].assert_called_once()

    def test_exhausted_rotation_budget_preserves_debug_hold_and_window(self):
        with self.run_context() as (driver, mocks):
            self.enable_rotation_context(mocks)
            driver.current_url = "https://auth.openai.com/log-in"
            mocks["navigate"].side_effect = RuntimeError("net::ERR_CONNECTION_RESET")
            result = self.run_registration(registration_options={
                "_resume_proxy_rotation": self.rotation_context(retry_available=False),
            })
        self.assertIs(result.get("resume_proxy_rotation_ready"), False)
        mocks["client"].return_value.close_profile.assert_not_called()
        mocks["pause"].assert_called_once()
        mocks["retain_default"].assert_called_once()

    def test_reopen_permission_requires_same_run_attempt_execution_and_profile(self):
        for field, value in (("attempt_id", 42), ("run_id", 72), ("job_id", 32),
                             ("execution_id", "other-execution"), ("reopen_profile_id", "other-profile")):
            with self.subTest(field=field), self.run_context() as (_driver, mocks):
                self.enable_rotation_context(mocks)
                context = {**self.rotation_context(reopen_profile_id="unit-profile"), field: value}
                with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                    self.run_registration(registration_options={"_resume_proxy_rotation": context})
                mocks["opened"].assert_not_called()
                mocks["take_default"].assert_not_called()

    def test_native_error_during_bound_profile_probe_reaches_new_login_get(self):
        with self.run_context() as (driver, mocks):
            def fail_after_origin_change(_driver, **_kwargs):
                driver.current_url = "chrome-error://chromewebdata/"
                raise RuntimeError("request_unknown: origin_changed")
            with patch.object(session_auth, "_read_chatgpt_session_once", side_effect=fail_after_origin_change):
                result = self.run_registration()
        self.assertFalse(result["success"])
        mocks["navigate"].assert_called_once()
        self.assertEqual(mocks["navigate"].call_args.args[1], "https://chatgpt.com/auth/login")
        mocks["_submit_email_and_wait_next"].assert_not_called()

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

    def test_core_and_profile_are_saved_before_plan_capture_even_when_it_fails(self):
        for plan_fails in (False, True):
            with self.subTest(plan_fails=plan_fails), self.run_context() as (_, mocks):
                events = []
                mocks["persist"].side_effect = lambda **_kwargs: events.append("persist") or 19
                mocks["client"].return_value.mark_profile_bound.side_effect = lambda *_args: events.append("bind")

                def capture_plan(*_args):
                    events.append("plan")
                    if plan_fails:
                        raise TimeoutError("模拟套餐捕获失败")
                    return {"ok": True, "quota_status": "success"}

                mocks["plan_read"].side_effect = capture_plan
                result = self.run_registration(registration_options={
                    "password_enabled": True, "twofa_enabled": False,
                    "codex_enabled": False, "plan_check_enabled": True,
                })
                self.assertTrue(result["success"], result.get("error"))
                self.assertTrue(result["core_persisted"])
                self.assertEqual(result["account_id"], 19)
                self.assertEqual(events[:3], ["persist", "bind", "plan"])
                self.assertIs(mocks["persist"].call_args.kwargs["chatgpt_session"], SESSION)
                self.assertEqual(mocks["plan_enqueue"].call_count, int(plan_fails))
                mocks["release"].assert_not_called()

    def test_plan_query_timer_excludes_homepage_wait_and_twofa(self):
        with self.run_context() as (_, mocks):
            events = []
            mocks["progress"].side_effect = lambda stage, state, *_args, **_kwargs: (
                events.append("plan_start") if (stage, state) == ("plan_check", "running") else None)
            mocks["twofa"].side_effect = lambda *_args, **_kwargs: events.append("twofa") or "unit-totp"
            with patch.object(roxy, "_wait_registration_homepage", side_effect=lambda *_a, **_k: (
                events.append("homepage") or {"ready": True})):
                result = self.run_registration(registration_options={
                    "password_enabled": True, "twofa_enabled": True,
                    "codex_enabled": False, "plan_check_enabled": True,
                })
        self.assertTrue(result["success"], result.get("error"))
        self.assertGreater(events.index("plan_start"), events.index("homepage"))
        self.assertGreater(events.index("plan_start"), events.index("twofa"))

    def test_natural_plan_capture_survives_twofa_navigation_without_refetch(self):
        captured = {"ok": True, "quota_status": "success", "source": "browser_response"}
        with self.run_context() as (_, mocks):
            mocks["plan_cached"].return_value = captured
            mocks["twofa"].side_effect = lambda *_a, **_k: (
                setattr(mocks["plan_cached"], "return_value", None) or "unit-totp")
            with patch.object(roxy, "_wait_registration_homepage", return_value={"ready": True}):
                result = self.run_registration(registration_options={
                    "password_enabled": True, "twofa_enabled": True,
                    "codex_enabled": False, "plan_check_enabled": True,
                })
        self.assertTrue(result["postprocess_success"], result)
        mocks["plan_cached"].assert_called_once()
        mocks["plan_read"].assert_not_called()
        self.assertEqual(mocks["plan_save"].call_args.kwargs["result"]["source"], "browser_response")

    def test_stop_after_confirmed_token_preserves_core_before_honoring_stop(self):
        from core.registration_service import StopRequested

        with self.run_context(action="registration") as (_, mocks):
            mocks["navigate"].side_effect = None
            mocks["_submit_email_and_wait_next"].return_value = "otp"
            mocks["_fill_password_page_if_present"].return_value = "unit-new-password"
            mocks["_has_access_token"].return_value = True
            confirmed = [False]

            def fetch_session(*_args, **_kwargs):
                confirmed[0] = True
                return SESSION

            def stop_if_confirmed():
                if confirmed[0]:
                    raise StopRequested("模拟会话确认后收到停止请求")

            mocks["_fetch_chatgpt_session"].side_effect = fetch_session
            mocks["_check_manual_stop"].side_effect = stop_if_confirmed
            result = self.run_registration(existing_password=None)
        self.assertFalse(result["success"])
        self.assertTrue(result["core_persisted"])
        self.assertEqual(result["account_id"], 19)
        mocks["persist"].assert_called_once()
        mocks["client"].return_value.mark_profile_bound.assert_called_once_with("unit-profile")
        mocks["plan_read"].assert_not_called()
        mocks["release"].assert_not_called()

    def test_homepage_is_checked_after_persist_and_only_ready_page_enables_deep_saving(self):
        for ready in (True, False):
            with self.subTest(ready=ready), self.run_context() as (_, mocks):
                def homepage(*args, **kwargs):
                    mocks["persist"].assert_called_once()
                    mocks["saver"].return_value.activate_post_auth.assert_not_called()
                    return {"ready": ready, "reason": "ready" if ready else "timeout"}

                with patch.object(roxy, "_wait_registration_homepage", side_effect=homepage):
                    result = self.run_registration()
                self.assertTrue(result["success"], result.get("error"))
                self.assertTrue(result["core_persisted"])
                self.assertEqual(mocks["saver"].return_value.activate_post_auth.call_count, int(ready))

    def test_data_saver_preserves_natural_plan_before_parking_saved_session(self):
        captured = {"ok": True, "quota_status": "success", "source": "browser_response"}
        with self.run_context() as (_, mocks):
            mocks["saver"].return_value.enabled = True
            mocks["plan_cached"].return_value = captured

            def park(*_args, **_kwargs):
                mocks["persist"].assert_called_once()
                mocks["plan_cached"].assert_called_once()
                mocks["saver"].return_value.activate_post_auth.assert_called_once()
                return True

            with patch.object(session_auth, "_park_verified_registration_page", side_effect=park) as parked, patch.object(
                roxy, "_wait_registration_homepage",
            ) as homepage:
                result = self.run_registration(registration_options={
                    "password_enabled": True, "twofa_enabled": False,
                    "codex_enabled": False, "plan_check_enabled": True,
                })
        self.assertTrue(result["postprocess_success"], result)
        parked.assert_called_once()
        homepage.assert_not_called()
        mocks["plan_read"].assert_not_called()
        mocks["_install_registration_postprocess_data_saver"].assert_not_called()

    def test_data_saver_protocol_twofa_success_does_not_restore_homepage_resources(self):
        with self.run_context() as (_, mocks):
            mocks["saver"].return_value.enabled = True
            mocks["twofa_driver"].return_value = "protocol"
            with patch.object(session_auth, "_park_verified_registration_page", return_value=True), patch.object(
                roxy, "setup_protocol_2fa_with_browser_fallback", return_value=("unit-totp", False),
            ) as protocol, patch.object(roxy, "BrowserSession"), patch.object(roxy, "_wait_registration_homepage") as homepage:
                result = self.run_registration(registration_options={
                    "password_enabled": True, "twofa_enabled": True,
                    "codex_enabled": False, "plan_check_enabled": False,
                })
        self.assertTrue(result["postprocess_success"], result)
        protocol.assert_called_once()
        self.assertTrue(callable(protocol.call_args.kwargs["before_browser"]))
        homepage.assert_not_called()
        mocks["_install_registration_postprocess_data_saver"].assert_not_called()
        mocks["twofa"].assert_not_called()

    def test_data_saver_restores_resources_immediately_before_browser_twofa(self):
        with self.run_context() as (_, mocks):
            mocks["saver"].return_value.enabled = True
            events = []
            mocks["_install_registration_postprocess_data_saver"].side_effect = lambda *_a: events.append("restore")
            mocks["twofa"].side_effect = lambda *_a, **_k: events.append("browser_twofa") or "unit-totp"
            with patch.object(session_auth, "_park_verified_registration_page", side_effect=lambda *_a, **_k: events.append("park") or True):
                result = self.run_registration(registration_options={
                    "password_enabled": True, "twofa_enabled": True,
                    "codex_enabled": False, "plan_check_enabled": False,
                })
        self.assertTrue(result["postprocess_success"], result)
        self.assertEqual(events, ["park", "restore", "browser_twofa", "park"])

    def test_new_registration_keeps_profile_and_callback_resources_until_homepage_ready(self):
        with self.run_context(action="registration") as (_, mocks):
            mocks["navigate"].side_effect = None
            mocks["_submit_email_and_wait_next"].return_value = "otp"
            mocks["_fill_password_page_if_present"].return_value = "unit-new-password"
            mocks["_has_access_token"].return_value = True
            mocks["_fetch_chatgpt_session"].return_value = SESSION

            def profile(*args, **kwargs):
                self.assertNotIn("on_submit", kwargs)
                mocks["saver"].return_value.activate_post_auth.assert_not_called()
                return True

            def homepage(*args, **kwargs):
                mocks["persist"].assert_called_once()
                mocks["saver"].return_value.activate_post_auth.assert_not_called()
                return {"ready": True, "reason": "ready"}

            mocks["_complete_profile_page"].side_effect = profile
            with patch.object(roxy, "_wait_registration_homepage", side_effect=homepage):
                result = self.run_registration(existing_password=None, profile_id=None)
            self.assertTrue(result["success"], result.get("error"))
            self.assertTrue(mocks["_fetch_chatgpt_session"].call_args.kwargs["prefer_homepage"])
            mocks["saver"].return_value.activate_post_auth.assert_called_once()

    def test_direct_login_without_a_new_password_keeps_the_original_credential_in_all_checkpoints(self):
        for returned_password in (None, "", "unit-new-password"):
            with self.subTest(returned_new_password=bool(returned_password)), self.run_context() as (driver, mocks):
                driver.execute_async_script.return_value = {
                    "ok": True, "status": 401, "json_valid": True, "data": {},
                }
                mocks["navigate"].side_effect = None
                mocks["_submit_email_and_wait_next"].return_value = "logged_in"
                mocks["_fill_password_page_if_present"].return_value = returned_password
                mocks["_has_access_token"].return_value = True
                mocks["login"].return_value = "advanced"
                mocks["_fetch_chatgpt_session"].return_value = SESSION
                result = self.run_registration()
                self.assertTrue(result["success"], result.get("error"))
                expected = returned_password or "unit-original-password"
                self.assertEqual(mocks["persist"].call_args.kwargs["extra"]["account_password"], expected)
                for checkpoint in mocks["checkpoint"].call_args_list:
                    self.assertEqual(checkpoint.kwargs["openai_password"], expected)

    def test_core_checkpoint_without_any_password_omits_the_password_field(self):
        with self.run_context(action="registration") as (_, mocks):
            mocks["navigate"].side_effect = None
            mocks["_submit_email_and_wait_next"].return_value = "logged_in"
            mocks["_fill_password_page_if_present"].return_value = None
            mocks["_has_access_token"].return_value = True
            mocks["_fetch_chatgpt_session"].return_value = SESSION
            result = self.run_registration(existing_password=None, profile_id=None)
            self.assertTrue(result["success"], result.get("error"))
            self.assertNotIn("account_password", mocks["persist"].call_args.kwargs["extra"])

    def test_exhausted_homepage_budget_does_not_turn_saved_account_into_registration_failure(self):
        with self.run_context() as (driver, mocks):
            entrypoint = roxy._wait_registration_homepage

            def homepage(*args, **kwargs):
                mocks["persist"].assert_called_once()
                return entrypoint(driver, budget=StageBudget(0, clock=lambda: 1))

            with patch.object(roxy, "_wait_registration_homepage", side_effect=homepage):
                result = self.run_registration()
            self.assertTrue(result["success"], result.get("error"))
            self.assertTrue(result["core_persisted"])
            mocks["saver"].return_value.activate_post_auth.assert_not_called()

    def test_explicit_no_token_resumes_existing_login_path(self):
        for status in (200, 401, 403):
            with self.subTest(status=status), self.run_context() as (driver, mocks):
                driver.execute_async_script.return_value = {"ok": True, "status": status, "data": {}, "json_valid": True}
                self.run_registration()
                mocks["navigate"].assert_called_once()
                mocks["persist"].assert_not_called()

    def test_submitted_resume_password_is_forwarded_to_shared_challenge_without_replay(self):
        with self.run_context() as (driver, mocks), patch(
            "core.registration.checkpoints.save_protocol_password_checkpoint",
        ):
            driver.execute_async_script.return_value = {"ok": True, "status": 200, "data": {}, "json_valid": True}
            mocks["navigate"].side_effect = None
            mocks["_submit_email_and_wait_next"].return_value = "otp"

            def password_submitted(*_args, **kwargs):
                kwargs["on_password_submitted"]("unit-original-password")
                return "unit-original-password"

            mocks["_fill_password_page_if_present"].side_effect = password_submitted
            mocks["login"].side_effect = RuntimeError("单测在公共登录边界结束")
            self.run_registration()
        mocks["login"].assert_called_once()
        self.assertIs(mocks["login"].call_args.kwargs.get("password_already_submitted"), True)

    def profile_after_saved_password(self, driver, mocks, *, url="https://auth.openai.com/about-you", inputs=None):
        from core.registration.browser_submission import BrowserSubmissionReceipt
        mocks["navigate"].side_effect = None
        mocks["_submit_email_and_wait_next"].return_value = "login_password"
        mocks["_has_access_token"].return_value = False
        mocks["_complete_profile_page"].return_value = True
        mocks["_fetch_chatgpt_session"].return_value = SESSION
        driver.execute_async_script.return_value = {"ok": True, "status": 200, "data": {}, "json_valid": True}
        snapshot = {"url": url, "inputs": inputs if inputs is not None else [
            {"name": "name", "type": "text", "visible": True},
            {"name": "age", "type": "number", "visible": True},
        ]}

        def submitted(*_args, **kwargs):
            kwargs["on_password_submitted"]("unit-original-password")
            driver.current_url = url
            driver._browser_submission_receipt = BrowserSubmissionReceipt(
                kind="resume_login", stage="login_password", endpoint_kind="password_submit", phase="confirmed",
            )
            return "unit-original-password"

        mocks["_fill_password_page_if_present"].side_effect = submitted
        return snapshot

    def test_saved_password_about_you_form_reaches_profile_without_public_challenge(self):
        with self.run_context() as (driver, mocks), patch(
            "core.registration.checkpoints.save_protocol_password_checkpoint",
        ):
            snapshot = self.profile_after_saved_password(driver, mocks)
            mocks["login"].side_effect = AssertionError("已到资料表单不能再等待公共验证码分支")
            with patch.object(roxy, "_page_snapshot", return_value=snapshot):
                result = self.run_registration()
        self.assertTrue(result["success"], result.get("error"))
        mocks["login"].assert_not_called()
        mocks["wait_for_otp"].assert_not_called()
        mocks["_complete_profile_page"].assert_called_once()
        self.assertEqual(mocks["_complete_profile_page"].call_args.kwargs["expected_email"], EMAIL)
        self.assertEqual(mocks["persist"].call_args.kwargs["extra"]["account_password"], "unit-original-password")
        self.assertEqual(driver._registration_fact_context["attempt_id"], 41)
        self.assertEqual(driver._browser_submission_receipt.phase, "confirmed")
        mocks["_fill_password_page_if_present"].assert_called_once()

    @contextmanager
    def existing_profile_context(self, *, session=None, historical=False, email=EMAIL):
        from core.registration.browser_submission import BrowserSubmissionReceipt
        with self.run_context() as (driver, mocks), patch(
            "core.registration.checkpoints.save_protocol_password_checkpoint",
        ):
            snapshot = self.profile_after_saved_password(driver, mocks)
            driver.current_url = "https://auth.openai.com/log-in"
            receipt = BrowserSubmissionReceipt(
                kind="profile", stage="profile", endpoint_kind="profile_submit", http_method="POST",
                phase="rejected", http_status=400, error_type="account_create_user_already_exists",
            )
            if historical:
                mocks["private"].return_value["submission_facts"] = [receipt.safe_fact()]
            else:
                def rejected(*_args, **_kwargs):
                    driver._browser_submission_receipt = receipt
                    raise password_auth.ProfileAccountAlreadyExistsError()
                mocks["_complete_profile_page"].side_effect = rejected

            def navigate(_driver, url, **_kwargs):
                driver.current_url = url
            mocks["navigate"].side_effect = navigate
            driver.execute_async_script.return_value = {
                "ok": True, "status": 200, "json_valid": True,
                "data": session if session is not None else {"accessToken": "unit-token", "user": {"email": email}},
            }
            with patch.object(roxy, "_page_snapshot", return_value=snapshot):
                yield driver, mocks, receipt

    def test_current_existing_profile_rejection_reconciles_without_second_create(self):
        with self.existing_profile_context() as (driver, mocks, receipt):
            result = self.run_registration()
        self.assertTrue(result["success"], result.get("error"))
        mocks["_complete_profile_page"].assert_called_once()
        mocks["_fetch_chatgpt_session"].assert_not_called()
        driver.execute_async_script.assert_called_once()
        self.assertEqual([c.args[1] for c in mocks["navigate"].call_args_list], [
            "https://chatgpt.com/auth/login", "https://chatgpt.com/api/auth/session",
        ])
        self.assertEqual(mocks["navigate"].call_args.kwargs["attempts"], 1)
        self.assertEqual(receipt.phase, "rejected")
        self.assertEqual(receipt.error_type, "account_create_user_already_exists")
        self.assertEqual(mocks["persist"].call_args.kwargs["extra"]["account_password"], "unit-original-password")
        self.assertEqual(driver._registration_fact_context["attempt_id"], 41)
        mocks["wait_for_otp"].assert_not_called()
        mocks["login"].assert_not_called()

    def test_existing_profile_without_full_exact_tag_session_never_persists_or_confirms(self):
        email = "resume+original@example.test"
        for session in ({"user": {"email": email}},
                        {"accessToken": "unit-token", "user": {"email": "resume@example.test"}},
                        {"accessToken": "unit-token", "user": {"email": "resume+other@example.test"}}):
            with self.subTest(session=session), self.existing_profile_context(session=session, email=email) as (driver, mocks, receipt):
                result = self.run_registration(email=email)
            self.assertFalse(result["success"])
            self.assertEqual(result["email"], email)
            self.assertTrue(result["request_unknown"])
            self.assertEqual(result["remote_account_state"], "request_unknown")
            self.assertEqual(result["remote_identity_state"], "unknown")
            self.assertFalse(result["manual_reconcile"])
            self.assertEqual(result.get("cause_code"), "account_create_user_already_exists")
            self.assertIs(result.get("register_response_confirmed"), True)
            self.assertIn("account_create_user_already_exists", result["error"])
            self.assertEqual(receipt.phase, "rejected")
            mocks["persist"].assert_not_called()
            mocks["_complete_profile_page"].assert_called_once()
            mocks["_fetch_chatgpt_session"].assert_not_called()
            driver.execute_async_script.assert_called_once()
            mocks["wait_for_otp"].assert_not_called()

    def test_historical_existing_profile_marker_skips_create_after_original_login(self):
        with self.existing_profile_context(historical=True) as (driver, mocks, receipt):
            result = self.run_registration()
        self.assertTrue(result["success"], result.get("error"))
        mocks["private"].assert_called_once_with(41, email=EMAIL)
        mocks["_complete_profile_page"].assert_not_called()
        mocks["_fill_password_page_if_present"].assert_called_once()
        mocks["_fetch_chatgpt_session"].assert_not_called()
        driver.execute_async_script.assert_called_once()
        self.assertEqual(receipt.phase, "rejected")
        self.assertEqual(driver._registration_fact_context["attempt_id"], 41)

    def test_historical_generic_400_is_not_reinterpreted_as_existing_account(self):
        with self.existing_profile_context(historical=True) as (driver, mocks, receipt):
            mocks["private"].return_value["submission_facts"][0]["error_type"] = "account_create_http_400"
            mocks["_complete_profile_page"].side_effect = RuntimeError("request_unknown: account_create_http_400")
            result = self.run_registration()
        self.assertFalse(result["success"])
        mocks["_complete_profile_page"].assert_called_once()
        self.assertEqual([c.args[1] for c in mocks["navigate"].call_args_list], ["https://chatgpt.com/auth/login"])
        driver.execute_async_script.assert_not_called()

    def test_existing_profile_session_reconciliation_rejects_changed_or_untrusted_target(self):
        for target in ("https://chatgpt.com.evil.test/api/auth/session", "http://chatgpt.com/api/auth/session",
                       "https://chatgpt.com:8443/api/auth/session", "https://private@chatgpt.com/api/auth/session",
                       "https://chatgpt.com/auth/error", "https://auth.openai.com/api/auth/session"):
            with self.subTest(target=target), self.existing_profile_context() as (driver, mocks, receipt):
                def navigate(_driver, url, **_kwargs):
                    driver.current_url = target if url.endswith("/api/auth/session") else url
                mocks["navigate"].side_effect = navigate
                result = self.run_registration()
            self.assertFalse(result["success"])
            self.assertEqual(result["remote_account_state"], "request_unknown")
            mocks["persist"].assert_not_called()
            driver.execute_async_script.assert_not_called()
            self.assertEqual(receipt.phase, "rejected")

    def test_existing_profile_reconciliation_get_and_read_share_one_deadline(self):
        for navigation_seconds, expected_read_ms in ((19, 11000), (31, None)):
            tick = [0.0]
            budget = StageBudget(30, clock=lambda: tick[0])
            with self.subTest(navigation_seconds=navigation_seconds), self.existing_profile_context() as (driver, mocks, receipt):
                def navigate(_driver, url, **_kwargs):
                    driver.current_url = url
                    if url.endswith("/api/auth/session"):
                        tick[0] = navigation_seconds
                mocks["navigate"].side_effect = navigate
                with patch.object(roxy.StageBudget, "start", return_value=budget):
                    result = self.run_registration()
            self.assertEqual(result["success"], expected_read_ms is not None, result.get("error"))
            if expected_read_ms is None:
                driver.execute_async_script.assert_not_called()
                mocks["persist"].assert_not_called()
                self.assertEqual(result["remote_account_state"], "request_unknown")
            else:
                self.assertEqual(driver.execute_async_script.call_args.args[1], expected_read_ms)
            self.assertEqual(receipt.phase, "rejected")

    def test_existing_profile_verified_session_then_persist_failure_preserves_confirmed_identity(self):
        with self.existing_profile_context() as (driver, mocks, receipt):
            mocks["persist"].side_effect = RuntimeError("unit-persist-failure")
            result = self.run_registration()
        self.assertFalse(result["success"])
        self.assertEqual(result["remote_account_state"], "confirmed")
        self.assertEqual(result["remote_identity_state"], "confirmed")
        self.assertNotEqual(result["error_code"], "account_create_user_already_exists")
        self.assertEqual(receipt.phase, "rejected")

    def test_historical_existing_profile_password_failure_keeps_identity_unconfirmed_and_real_cause(self):
        from core.auth_challenge import PasswordRejectedError
        with self.existing_profile_context(historical=True) as (driver, mocks, receipt):
            mocks["_fill_password_page_if_present"].side_effect = PasswordRejectedError("unit-password-rejected")
            result = self.run_registration()
        self.assertFalse(result["success"])
        self.assertEqual(result["remote_account_state"], "request_unknown")
        self.assertEqual(result["remote_identity_state"], "unknown")
        self.assertFalse(result["manual_reconcile"])
        self.assertEqual(result["error_code"], "password_rejected")
        self.assertNotIn("cause_code", result)
        mocks["persist"].assert_not_called()
        driver.execute_async_script.assert_not_called()
        self.assertEqual(receipt.phase, "rejected")

    def test_historical_existing_profile_transport_failure_never_discards_original_identity(self):
        with self.existing_profile_context(historical=True) as (driver, mocks, receipt):
            mocks["opened"].return_value.created_by_run = True
            mocks["navigate"].side_effect = RuntimeError("net::ERR_TUNNEL_CONNECTION_FAILED")
            result = self.run_registration()
        self.assertFalse(result["success"])
        self.assertTrue(result["request_unknown"])
        self.assertEqual(result["remote_account_state"], "request_unknown")
        mocks["persist"].assert_not_called()
        mocks["release"].assert_not_called()
        mocks["client"].return_value.discard_profile.assert_not_called()
        self.assertEqual(receipt.phase, "rejected")

    def test_profile_handoff_rejects_foreign_shell_hidden_or_unrecognized_forms(self):
        cases = [
            ("https://auth.openai.com.evil.test/about-you", None),
            ("http://auth.openai.com/about-you", None),
            ("https://auth.openai.com:8443/about-you", None),
            ("https://private@auth.openai.com/about-you", None),
            ("https://auth.openai.com/log-in/password", None),
            ("https://auth.openai.com/about-you", []),
            ("https://auth.openai.com/about-you", [{"name": "name", "type": "hidden", "visible": True}]),
            ("https://auth.openai.com/about-you", [{"name": "name", "type": "text", "visible": False},
                                                   {"name": "age", "type": "number", "visible": False}]),
            ("https://auth.openai.com/about-you", [{"name": "search", "type": "text", "visible": True}]),
        ]
        for url, inputs in cases:
            with self.subTest(url=url, inputs=inputs), self.run_context() as (driver, mocks), patch(
                "core.registration.checkpoints.save_protocol_password_checkpoint",
            ):
                snapshot = self.profile_after_saved_password(driver, mocks, url=url, inputs=inputs)
                mocks["login"].side_effect = RuntimeError("单测在公共登录边界结束")
                with patch.object(roxy, "_page_snapshot", return_value=snapshot):
                    result = self.run_registration()
                self.assertFalse(result["success"])
                mocks["login"].assert_called_once()
                mocks["_complete_profile_page"].assert_not_called()
                mocks["persist"].assert_not_called()

    def test_profile_handoff_still_requires_full_exact_email_session(self):
        with self.run_context() as (driver, mocks), patch(
            "core.registration.checkpoints.save_protocol_password_checkpoint",
        ):
            snapshot = self.profile_after_saved_password(driver, mocks)
            mocks["_fetch_chatgpt_session"].return_value = {
                "accessToken": "unit-other-token", "user": {"email": "other@example.test"},
            }
            with patch.object(roxy, "_page_snapshot", return_value=snapshot):
                result = self.run_registration()
        self.assertFalse(result["success"])
        self.assertIn("session_identity_mismatch", result["error"])
        mocks["login"].assert_not_called()
        mocks["_complete_profile_page"].assert_called_once()
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

class RetainedProfileConnectionTests(unittest.TestCase):
    def client(self, connection):
        return SimpleNamespace(
            get_open_profile_connection=Mock(return_value=connection),
            _find_active_profile_by_id=Mock(return_value={"openStatus": 0}),
        )

    def test_live_connection_is_attachable_despite_stale_closed_list_status(self):
        for current, saved in (("127.0.0.1:9222", "127.0.0.1:9222"),
                               ("http://127.0.0.1:9222", "127.0.0.1:9222")):
            with self.subTest(current=current, saved=saved):
                client = self.client({"dirId": "unit-profile", "pid": 123, "http": current})
                opened = SimpleNamespace(profile_id="unit-profile", debugger_address=saved)
                self.assertTrue(roxy._retained_profile_can_attach(client, opened))
                client.get_open_profile_connection.assert_called_once_with("unit-profile")
                client._find_active_profile_by_id.assert_not_called()

    def test_absent_connection_is_closed_even_if_list_status_says_open(self):
        client = self.client(None)
        client._find_active_profile_by_id.return_value = {"openStatus": 1}
        opened = SimpleNamespace(profile_id="unit-profile", debugger_address="127.0.0.1:9222")
        self.assertFalse(roxy._retained_profile_can_attach(client, opened))

    def test_connection_lookup_failure_preserves_unknown_without_private_error(self):
        client = self.client(None)
        client.get_open_profile_connection.side_effect = TimeoutError("unit-private-error")
        opened = SimpleNamespace(profile_id="unit-profile", debugger_address="127.0.0.1:9222")
        with self.assertRaisesRegex(RuntimeError, "request_unknown") as raised:
            roxy._retained_profile_can_attach(client, opened)
        self.assertNotIn("unit-private-error", str(raised.exception))

    def test_changed_or_unusable_debugger_port_cannot_reuse_saved_connection(self):
        cases = (
            ("127.0.0.1:9223", "127.0.0.1:9222"),
            ("127.0.0.1", "127.0.0.1:9222"),
            ("127.0.0.1:9222", ""),
            ("127.0.0.1:99999", "127.0.0.1:9222"),
        )
        for current, saved in cases:
            with self.subTest(current=current, saved=saved):
                client = self.client({"dirId": "unit-profile", "pid": 123, "http": current})
                opened = SimpleNamespace(profile_id="unit-profile", debugger_address=saved)
                with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                    roxy._retained_profile_can_attach(client, opened)


class RetainedWindowFlowTests(unittest.TestCase):
    run_context = ResumeSessionFlowTests.run_context
    run_registration = ResumeSessionFlowTests.run_registration

    @contextmanager
    def retained_context(self, *, page=roxy.PageState.OTP_EMAIL, pending=None):
        with self.run_context() as (driver, mocks), ExitStack() as stack:
            driver.current_url = "https://auth.openai.com/email-verification"
            driver._registration_otp_after_ts = 1234.5
            opened = mocks["opened"].return_value
            candidate = SimpleNamespace(driver=driver, opened=opened, otp_after_ts=1234.5)
            for name, value in (
                ("take_failed_browser", candidate), ("retain_failed_browser", True),
                ("prepare_retained_resume", SimpleNamespace(
                    page_state=page, password="unit-original-password", pending_otp=pending)),
                ("_wait_email_otp_page_ready", "accepted"),
                ("_wait_after_email_otp_submit", "accepted"),
                ("record_browser_submission_fact", {}),
            ):
                mocks[name] = stack.enter_context(patch.object(roxy, name, return_value=value, create=True))
            if pending is not None:
                mocks["prepare_retained_resume"].side_effect = [
                    mocks["prepare_retained_resume"].return_value,
                    SimpleNamespace(page_state=roxy.PageState.PROFILE, password="unit-original-password", pending_otp=None),
                ]
            mocks["start_capture"] = stack.enter_context(patch("core.browser_traffic.start_roxy_capture"))
            for name in ("_clear_otp_inputs", "_type_otp", "_submit_email_otp_current_form", "_resend_email_otp_after_failure"):
                mocks[name] = stack.enter_context(patch.object(roxy, name))
            mocks["_has_access_token"].return_value = False
            mocks["_fetch_chatgpt_session"].return_value = SESSION
            mocks["_complete_profile_page"].return_value = False
            yield driver, mocks

    def test_retry_claims_original_live_driver_without_opening_or_navigating(self):
        with self.retained_context() as (driver, mocks):
            result = self.run_registration()
            self.assertTrue(result["success"], result.get("error"))
            self.assertEqual(driver._registration_otp_after_ts, 1234.5)
            for name in ("opened", "driver", "navigate", "_submit_email_and_wait_next", "_fill_password_page_if_present", "login"):
                mocks[name].assert_not_called()
            mocks["take_failed_browser"].assert_called_once()
            mocks["start_capture"].assert_called_once()
            mocks["retain_failed_browser"].assert_not_called()

    def test_pre_account_retry_uses_original_window_and_saved_password(self):
        with self.retained_context() as (_, mocks):
            result = self.run_registration(profile_id=None, existing_password=None)
        self.assertTrue(result["success"], result.get("error"))
        self.assertEqual(mocks["persist"].call_args.kwargs["extra"]["account_password"], "unit-original-password")
        mocks["opened"].assert_not_called()
        mocks["navigate"].assert_not_called()

    def test_durable_binding_connects_saved_browser_without_open_or_navigation(self):
        with self.retained_context() as (driver, mocks):
            candidate = mocks["take_failed_browser"].return_value
            candidate.driver = None
            mocks["take_failed_browser"].return_value = None
            mocks["bound_default"].return_value = candidate
            mocks["client"].return_value.get_open_profile_connection.return_value = {
                "dirId": "unit-profile", "pid": 123, "http": "http://127.0.0.1:9222",
            }
            result = self.run_registration()
        self.assertTrue(result["success"], result.get("error"))
        self.assertTrue(driver._registration_retained_identity_required)
        mocks["driver"].assert_called_once_with(candidate.opened)
        mocks["opened"].assert_not_called()
        mocks["navigate"].assert_not_called()

    def test_pre_account_durable_context_reconnects_without_opening_another_profile(self):
        with self.retained_context() as (driver, mocks):
            saved_mail_times = []
            mocks["browser_resume_persist"].side_effect = lambda active_driver, *_args, **_kwargs: saved_mail_times.append(
                getattr(active_driver, "_registration_otp_after_ts", None))
            candidate = mocks["take_failed_browser"].return_value
            candidate.driver = None
            candidate.opened.account_bound = False
            mocks["take_failed_browser"].return_value = None
            mocks["attempt_default"].return_value = candidate
            mocks["client"].return_value.get_open_profile_connection.return_value = {
                "dirId": "unit-profile", "pid": 123, "http": "http://127.0.0.1:9222",
            }
            result = self.run_registration(profile_id=None)
        self.assertTrue(result["success"], result.get("error"))
        self.assertTrue(driver._registration_retained_identity_required)
        self.assertEqual(driver._registration_otp_after_ts, 1234.5)
        mocks["attempt_default"].assert_called_once_with(
            email=EMAIL, profile_id=None,
            facts={"run_id": 71, "attempt_id": 41, "job_id": 31},
        )
        mocks["bound_default"].assert_not_called()
        mocks["driver"].assert_called_once_with(candidate.opened)
        mocks["opened"].assert_not_called()
        mocks["client"].return_value.open_profile.assert_not_called()
        mocks["client"].return_value.open_profile_for_account.assert_not_called()
        mocks["navigate"].assert_not_called()
        mocks["browser_resume_persist"].assert_called_once()
        self.assertEqual(saved_mail_times, [1234.5])

    def test_reconnected_window_keeps_mail_boundary_if_page_probe_fails(self):
        with self.retained_context() as (_, mocks):
            candidate = mocks["take_failed_browser"].return_value
            candidate.driver = None
            mocks["take_failed_browser"].return_value = None
            mocks["attempt_default"].return_value = candidate
            mocks["client"].return_value.get_open_profile_connection.return_value = {
                "dirId": "unit-profile", "pid": 123, "http": "http://127.0.0.1:9222",
            }
            saved_mail_times = []
            mocks["browser_resume_persist"].side_effect = lambda active_driver, *_args, **_kwargs: saved_mail_times.append(
                getattr(active_driver, "_registration_otp_after_ts", None))
            mocks["prepare_retained_resume"].side_effect = RuntimeError("request_unknown: 原页暂不可读取")
            result = self.run_registration(profile_id=None)
        self.assertFalse(result["success"])
        self.assertEqual(saved_mail_times, [1234.5, 1234.5])
        mocks["opened"].assert_not_called()
        mocks["navigate"].assert_not_called()

    def test_explicitly_closed_saved_browser_uses_existing_profile_open_path(self):
        with self.retained_context() as (_, mocks):
            candidate = mocks["take_failed_browser"].return_value
            candidate.driver = None
            mocks["client"].return_value.get_open_profile_connection.return_value = None
            result = self.run_registration()
        self.assertFalse(result["success"])
        mocks["opened"].assert_called_once()
        self.assertEqual(mocks["opened"].call_args.kwargs["profile_id"], "unit-profile")
        mocks["prepare_retained_resume"].assert_not_called()

    def test_uncertain_saved_browser_state_never_opens_another_environment(self):
        with self.retained_context() as (_, mocks):
            mocks["take_failed_browser"].return_value.driver = None
            mocks["client"].return_value.get_open_profile_connection.side_effect = TimeoutError("unit lookup failed")
            with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                self.run_registration()
        mocks["opened"].assert_not_called()
        mocks["navigate"].assert_not_called()

    def test_unknown_original_otp_only_observes_and_confirms_same_receipt(self):
        pending = roxy.BrowserSubmissionReceipt(kind="otp", stage="email_otp", phase="unknown", endpoint_kind="otp_submit")
        with self.retained_context(pending=pending) as (_, mocks):
            result = self.run_registration()
        self.assertTrue(result["success"], result.get("error"))
        mocks["_wait_after_email_otp_submit"].assert_called_once()
        self.assertEqual(mocks["prepare_retained_resume"].call_count, 2)
        for name in ("wait_for_otp", "_clear_otp_inputs", "_type_otp", "_submit_email_otp_current_form", "_resend_email_otp_after_failure", "login"):
            mocks[name].assert_not_called()

    def test_unknown_original_otp_stays_unknown_without_extra_submission(self):
        pending = roxy.BrowserSubmissionReceipt(kind="otp", stage="email_otp", phase="unknown", endpoint_kind="otp_submit")
        with self.retained_context(pending=pending) as (_, mocks):
            mocks["_wait_after_email_otp_submit"].return_value = "stuck"
            result = self.run_registration()
        self.assertFalse(result["success"])
        self.assertTrue(result["request_unknown"])
        for name in ("wait_for_otp", "_type_otp", "_submit_email_otp_current_form", "_resend_email_otp_after_failure", "navigate", "login", "persist"):
            mocks[name].assert_not_called()
        mocks["retain_failed_browser"].assert_called_once()

    def test_pending_otp_checks_identity_again_before_confirming_or_continuing(self):
        pending = roxy.BrowserSubmissionReceipt(kind="otp", stage="email_otp", phase="unknown", endpoint_kind="otp_submit")
        for message in ("原窗口来源无法核验", "原窗口的邮箱身份与原任务不一致"):
            with self.subTest(message=message), self.retained_context(pending=pending) as (_, mocks):
                initial = mocks["prepare_retained_resume"].return_value
                mocks["prepare_retained_resume"].side_effect = [initial, RuntimeError("request_unknown: " + message)]
                result = self.run_registration()
            self.assertFalse(result["success"])
            self.assertTrue(result["request_unknown"])
            mocks["record_browser_submission_fact"].assert_not_called()
            for name in ("persist", "_complete_profile_page", "wait_for_otp", "_type_otp", "_resend_email_otp_after_failure"):
                mocks[name].assert_not_called()

    def test_unknown_mail_boundary_allows_only_original_pending_observation(self):
        pending = roxy.BrowserSubmissionReceipt(kind="otp", stage="email_otp", phase="unknown", endpoint_kind="otp_submit")
        with self.retained_context(pending=pending) as (_, mocks):
            mocks["take_failed_browser"].return_value.otp_after_ts = None
            result = self.run_registration()
        self.assertTrue(result["success"], result.get("error"))
        mocks["_wait_after_email_otp_submit"].assert_called_once()
        mocks["wait_for_otp"].assert_not_called()
        with self.retained_context() as (_, mocks):
            mocks["take_failed_browser"].return_value.otp_after_ts = None
            result = self.run_registration()
        self.assertFalse(result["success"])
        self.assertTrue(result["request_unknown"])
        mocks["wait_for_otp"].assert_not_called()

    def test_password_page_cannot_start_mail_read_with_unknown_original_boundary(self):
        with self.retained_context(page=roxy.PageState.PASSWORD_CREATE) as (_, mocks):
            mocks["take_failed_browser"].return_value.otp_after_ts = None
            mocks["_fill_password_page_if_present"].return_value = "unit-original-password"
            mocks["_wait_email_otp_page_ready"].return_value = "ready"
            result = self.run_registration()
        self.assertFalse(result["success"])
        self.assertTrue(result["request_unknown"])
        mocks["wait_for_otp"].assert_not_called()
        mocks["_resend_email_otp_after_failure"].assert_not_called()

    def test_profile_page_resumes_profile_without_password_or_mail(self):
        with self.retained_context(page=roxy.PageState.PROFILE) as (_, mocks):
            result = self.run_registration()
        self.assertTrue(result["success"], result.get("error"))
        for name in ("navigate", "_fill_password_page_if_present", "login", "wait_for_otp", "_wait_email_otp_page_ready"):
            mocks[name].assert_not_called()
        mocks["_complete_profile_page"].assert_called_once()

    def test_unknown_retained_password_automatically_reenters_login_with_original_password(self):
        with self.retained_context(page=roxy.PageState.PASSWORD_CREATE) as (driver, mocks):
            state = mocks["prepare_retained_resume"].return_value
            state.restart_login = True
            mocks["navigate"].side_effect = None
            mocks["_submit_email_and_wait_next"].return_value = "password"
            mocks["_fill_password_page_if_present"].return_value = "unit-original-password"
            mocks["login"].return_value = "advanced"
            driver._registration_otp_tracker = object()
            result = self.run_registration()
        self.assertTrue(result["success"], result.get("error"))
        mocks["opened"].assert_not_called()
        mocks["navigate"].assert_called_once()
        self.assertEqual(mocks["navigate"].call_args.args[1], "https://chatgpt.com/auth/login")
        mocks["_submit_email_and_wait_next"].assert_called_once()
        self.assertTrue(mocks["_submit_email_and_wait_next"].call_args.kwargs["allow_login_password"])
        mocks["_fill_password_page_if_present"].assert_called_once()
        self.assertEqual(mocks["_fill_password_page_if_present"].call_args.kwargs["existing_password"],
                         "unit-original-password")
        self.assertGreater(driver._registration_otp_after_ts, 1234.5)
        mocks["_wait_after_email_otp_submit"].assert_not_called()

    def test_failed_window_is_remembered_after_previous_resources_finish(self):
        with self.retained_context() as (driver, mocks):
            finished = []
            mocks["client"].return_value.cleanup_profile.side_effect = lambda _: finished.append("cleanup")
            mocks["retain_failed_browser"].side_effect = lambda *_args, **_kwargs: finished.append("remember")
            mocks["prepare_retained_resume"].side_effect = RuntimeError("request_unknown: 原页面读取未完成")
            result = self.run_registration()
        self.assertFalse(result["success"])
        self.assertEqual(finished, ["cleanup", "remember"])
        self.assertIs(mocks["retain_failed_browser"].call_args.args[0], driver)
