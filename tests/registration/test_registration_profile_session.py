"""资料提交后的完整会话读取使用单一剩余预算。"""
import ast
from contextlib import ExitStack
import inspect
import json
import shutil
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.auth.browser import password_auth, session_auth
from core.auth.state_machine import StageTimeout


class ProfileSessionReadTests(unittest.TestCase):
    def driver(self):
        return SimpleNamespace(
            current_url="https://chatgpt.com/", timeouts=SimpleNamespace(script=8),
            set_script_timeout=Mock(), execute_async_script=Mock(return_value={
                "ok": True, "status": 200,
                "data": {"accessToken": "test-token", "user": {"email": "unit@example.test"}, "WARNING_BANNER": True},
            }),
        )

    def test_complete_body_uses_remaining_budget_and_restores_script_timeout(self):
        driver = self.driver()
        session = session_auth._read_profile_session_once(driver, timeout=15, expected_email="Unit@Example.test")
        self.assertTrue(session.get("accessToken"))
        self.assertEqual(driver.execute_async_script.call_args.args[1], 15000)
        self.assertEqual([c.args[0] for c in driver.set_script_timeout.call_args_list], [16.0, 8])
        self.assertEqual(driver._registration_verified_session["email"], "unit@example.test")

    def test_validated_session_is_consumed_by_token_step_without_another_request(self):
        driver = self.driver()
        expected = session_auth._read_profile_session_once(driver, timeout=15, expected_email="unit@example.test")
        with patch.object(session_auth, "_safe_get") as navigate:
            self.assertIs(session_auth._fetch_chatgpt_session(driver, timeout=10), expected)
        driver.execute_async_script.assert_called_once()
        navigate.assert_not_called()
        self.assertIsNone(driver._registration_verified_session)

    def test_otp_verified_session_is_reused_by_profile_then_consumed_by_token(self):
        driver = self.driver()
        expected = session_auth._read_profile_session_once(driver, timeout=15, expected_email="unit@example.test")
        self.assertIs(session_auth._read_profile_session_once(driver, timeout=15, expected_email="unit@example.test"), expected)
        self.assertIs(session_auth._fetch_chatgpt_session(driver, timeout=15), expected)
        driver.execute_async_script.assert_called_once()
        self.assertIsNone(driver._registration_verified_session)

    def test_expired_verified_session_is_read_again_without_extending_old_cache(self):
        driver = self.driver()
        session_auth._read_profile_session_once(driver, timeout=15, expected_email="unit@example.test")
        driver._registration_verified_session["expires_at"] = -1
        session_auth._read_profile_session_once(driver, timeout=15, expected_email="unit@example.test")
        self.assertEqual(driver.execute_async_script.call_count, 2)

    def test_missing_or_mismatched_identity_is_not_cached(self):
        for user in ({}, {"email": "other@example.test"}):
            driver = self.driver()
            driver.execute_async_script.return_value["data"]["user"] = user
            with self.subTest(user=user), self.assertRaisesRegex(RuntimeError, "request_unknown.*session_identity_mismatch"):
                session_auth._read_profile_session_once(driver, timeout=15, expected_email="unit@example.test")
            self.assertFalse(hasattr(driver, "_registration_verified_session"))
            driver.execute_async_script.assert_called_once()

    def test_read_failure_restores_script_timeout_without_retry(self):
        driver = self.driver()
        driver.execute_async_script.side_effect = RuntimeError("bridge unavailable")
        with self.assertRaisesRegex(RuntimeError, "request_unknown"):
            session_auth._read_profile_session_once(driver, timeout=15, expected_email="unit@example.test")
        driver.execute_async_script.assert_called_once()
        self.assertEqual([c.args[0] for c in driver.set_script_timeout.call_args_list], [16.0, 8])

    def test_unavailable_session_keeps_status_and_marker_without_response_secrets(self):
        driver = self.driver()
        driver.execute_async_script.return_value = {
            "ok": True, "status": 401, "json_valid": True,
            "data": {"WARNING_BANNER": "unit@example.test private-cookie", "user": {"email": "unit@example.test"}},
        }
        with self.assertRaisesRegex(RuntimeError, "profile_session_read_failed"):
            session_auth._read_profile_session_once(driver, timeout=15, expected_email="unit@example.test")
        diagnostic = driver._registration_session_diagnostic
        self.assertEqual(diagnostic["status"], 401)
        self.assertEqual(diagnostic["marker"], "WARNING_BANNER")
        self.assertFalse(diagnostic["token_present"])
        self.assertNotIn("unit@example.test", json.dumps(diagnostic))
        self.assertNotIn("private-cookie", json.dumps(diagnostic))

    def test_incomplete_session_body_does_not_claim_token_is_absent(self):
        driver = self.driver()
        driver.execute_async_script.return_value = {"ok": False, "error_type": "timeout"}
        with self.assertRaisesRegex(RuntimeError, "profile_session_unconfirmed"):
            session_auth._read_profile_session_once(driver, timeout=15)
        diagnostic = driver._registration_session_diagnostic
        self.assertIsNone(diagnostic["status"])
        self.assertIsNone(diagnostic["token_present"])
        self.assertEqual(diagnostic["marker"], "")
        self.assertEqual(diagnostic["error_type"], "timeout")

    def test_read_failure_keeps_exception_type_without_copying_private_message(self):
        driver = self.driver()
        original = TimeoutError("unit@example.test password=private-value token=private-token")
        driver.execute_async_script.side_effect = original
        with self.assertLogs(session_auth.logger, level="WARNING") as logged:
            with self.assertRaisesRegex(RuntimeError, "profile_session_read_failed.*异常类型=TimeoutError") as raised:
                session_auth._read_profile_session_once(driver, timeout=15, expected_email="unit@example.test")
        self.assertIs(raised.exception.__cause__, original)
        summary = str(raised.exception) + str(logged.output)
        for private_value in ("unit@example.test", "private-value", "private-token"):
            self.assertNotIn(private_value, summary)
        driver.execute_async_script.assert_called_once()
        self.assertFalse(hasattr(driver, "_registration_verified_session"))

    def test_zero_budget_or_foreign_origin_does_not_start_read(self):
        driver = self.driver()
        with self.assertRaises(StageTimeout):
            session_auth._read_chatgpt_session_once(driver, timeout=0)
        driver.current_url = "https://chatgpt.com.evil.test/"
        self.assertIsNone(session_auth._read_chatgpt_session_once(driver, timeout=15))
        driver.execute_async_script.assert_not_called()
        driver.set_script_timeout.assert_not_called()

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证慢响应体和单一超时")
    def test_browser_read_waits_for_body_after_two_seconds_with_one_fetch(self):
        tree = ast.parse(inspect.getsource(session_auth._read_chatgpt_session_once))
        script = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                      and isinstance(n.value, str) and "const timeoutMs" in n.value)
        source = r"""
        (async()=>{
          const script=SCRIPT;
          let now=0,seq=0,fetches=0,aborts=0;const timers=new Map();
          global.location={origin:'https://chatgpt.com'};
          global.setTimeout=(fn,delay)=>{const id=++seq;timers.set(id,{fn,at:now+delay});return id;};
          global.clearTimeout=id=>timers.delete(id);
          global.AbortController=class{constructor(){this.signal={};}abort(){aborts++;}};
          global.fetch=()=>{fetches++;return Promise.resolve({status:200,text:()=>new Promise(resolve=>
            setTimeout(()=>resolve('{"accessToken":"test-token","user":{"email":"unit@example.test"}}'),3500))});};
          let result;new Function(script)(15000,value=>{result=value;});
          for(let rounds=0;rounds<20&&!result;rounds++){
            for(let i=0;i<8;i++)await Promise.resolve();
            if(result)break;
            const next=[...timers.entries()].sort((a,b)=>a[1].at-b[1].at)[0];
            if(next){timers.delete(next[0]);now=next[1].at;next[1].fn();}
          }
          console.log(JSON.stringify({fetches,aborts,elapsed:now,ok:result?.ok,hasToken:!!result?.data?.accessToken}));
        })();
        """.replace("SCRIPT", json.dumps(script))
        result = subprocess.run([shutil.which("node"), "-e", source], capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), {"fetches": 1, "aborts": 0, "elapsed": 3500, "ok": True, "hasToken": True})


class ProfileDeadlineTests(unittest.TestCase):
    def test_registration_transition_budget_starts_after_preparing_and_submitting_profile(self):
        driver = SimpleNamespace(execute_script=Mock(return_value={"valid": True, "fields": []}))
        now = [0.0]
        clock = SimpleNamespace(time=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))
        profile = {"url": "https://auth.openai.com/about-you", "inputs": [{"name": "name"}, {"name": "age"}]}
        submitted = [False]

        def submit(_driver, *, before_dispatch=None):
            if before_dispatch is not None:
                before_dispatch()
            submitted[0] = True
            return True

        def read(_driver, *, timeout, expected_email):
            self.assertGreaterEqual(timeout, 35)
            now[0] += 35
            return {"accessToken": "test-token"}

        with ExitStack() as stack:
            stack.enter_context(patch.object(password_auth, "time", clock))
            for name in ("_check_manual_stop", "_accept_profile_consents", "human_delay", "log_submission_diagnostics"):
                stack.enter_context(patch.object(password_auth, name))
            stack.enter_context(patch.object(password_auth, "_page_snapshot", side_effect=lambda _d:
                                            {"url": "https://chatgpt.com/"} if submitted[0] else profile))
            stack.enter_context(patch.object(password_auth, "_fill_birthday_or_age", side_effect=lambda *_a:
                                            now.__setitem__(0, now[0] + 40) or "age"))
            stack.enter_context(patch.object(password_auth, "_select_or_type", return_value=True))
            click = stack.enter_context(patch.object(password_auth, "_click_if_enabled_submit", side_effect=submit))
            session = stack.enter_context(patch.object(password_auth, "_read_profile_session_once", side_effect=read))
            self.assertTrue(password_auth._complete_profile_page(
                driver, "Example User", "2000-01-02", timeout=60, transition_timeout=90,
                expected_email="unit@example.test",
            ))
        click.assert_called_once()
        session.assert_called_once()
        self.assertLessEqual(now[0], 131)

    def test_failed_profile_click_does_not_call_submission_callback(self):
        driver = SimpleNamespace(execute_script=Mock(return_value={"valid": True}))
        now = [0.0]
        clock = SimpleNamespace(time=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))
        callback = Mock()
        with ExitStack() as stack:
            stack.enter_context(patch.object(password_auth, "time", clock))
            for name in ("_check_manual_stop", "_accept_profile_consents", "human_delay", "log_submission_diagnostics"):
                stack.enter_context(patch.object(password_auth, name))
            stack.enter_context(patch.object(password_auth, "_page_snapshot", return_value={
                "url": "https://auth.openai.com/about-you", "inputs": [{"name": "name"}, {"name": "age"}],
            }))
            stack.enter_context(patch.object(password_auth, "_fill_birthday_or_age", return_value="age"))
            stack.enter_context(patch.object(password_auth, "_select_or_type", return_value=True))
            submit = stack.enter_context(patch.object(password_auth, "_click_if_enabled_submit", return_value=False))
            with self.assertRaisesRegex(RuntimeError, "资料页超时"):
                password_auth._complete_profile_page(driver, "Example User", "2000-01-02", timeout=3, on_submit=callback)
        self.assertEqual(submit.call_count, 3)
        callback.assert_not_called()

    def test_profile_uses_remaining_total_deadline_for_one_complete_read(self):
        driver = SimpleNamespace(execute_script=Mock(return_value={"valid": True, "fields": []}))
        now = [0.0]
        clock = SimpleNamespace(time=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))
        with ExitStack() as stack:
            stack.enter_context(patch.object(password_auth, "time", clock))
            for name in ("_check_manual_stop", "_accept_profile_consents", "human_delay"):
                stack.enter_context(patch.object(password_auth, name))
            stack.enter_context(patch.object(password_auth, "_page_snapshot", side_effect=[
                {"url": "https://auth.openai.com/about-you", "inputs": [{"name": "name"}, {"name": "age"}]},
                {"url": "https://chatgpt.com/", "inputs": []},
            ]))
            stack.enter_context(patch.object(password_auth, "_fill_birthday_or_age", return_value="age"))
            stack.enter_context(patch.object(password_auth, "_select_or_type", return_value=True))
            submit = stack.enter_context(patch.object(password_auth, "_click_if_enabled_submit", return_value=True))
            callback = Mock(side_effect=lambda: self.assertEqual(submit.call_count, 1))
            short = stack.enter_context(patch.object(password_auth, "_has_access_token"))
            read = stack.enter_context(patch.object(password_auth, "_read_profile_session_once", return_value={"accessToken": "test-token"}))
            self.assertTrue(password_auth._complete_profile_page(driver, "Example User", "2000-01-02", timeout=5,
                                                               expected_email="unit@example.test", on_submit=callback))
        read.assert_called_once_with(driver, timeout=3.5, expected_email="unit@example.test")
        submit.assert_called_once()
        callback.assert_called_once()
        short.assert_not_called()
