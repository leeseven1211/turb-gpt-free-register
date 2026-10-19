"""普通注册观察首页；省流量注册在会话保存后停止应用壳下载。"""
import ast
import inspect
import json
import shutil
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.registration import roxy, session_auth
from core.registration.state_machine import CancellationRequested, StageBudget


class HomepageReadyTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0

    def sleep(self, seconds):
        self.now += seconds

    def driver(self, *, url="https://chatgpt.com/", state=None):
        return SimpleNamespace(
            current_url=url, timeouts=SimpleNamespace(page_load=90),
            execute_script=Mock(return_value=state if state is not None else {"ready": True}),
            set_page_load_timeout=Mock(), get=Mock(),
        )

    def wait(self, driver, *, seconds=2):
        budget = StageBudget(seconds, clock=lambda: self.now)
        with patch.object(session_auth, "_check_manual_stop"), patch(
            "core.registration.state_machine.time.sleep", side_effect=self.sleep,
        ):
            return session_auth._wait_registration_homepage(driver, budget=budget)

    def test_ready_homepage_does_not_navigate_or_send_auth_requests(self):
        driver = self.driver()
        self.assertEqual(self.wait(driver), {"ready": True, "reason": "ready"})
        driver.get.assert_not_called()
        driver.set_page_load_timeout.assert_not_called()
        driver.execute_script.assert_called_once()

    def test_session_document_opens_normal_homepage_once_with_remaining_budget(self):
        driver = self.driver(url="https://chatgpt.com/api/auth/session")
        self.assertTrue(self.wait(driver)["ready"])
        driver.get.assert_called_once_with("https://chatgpt.com/")
        self.assertEqual([c.args[0] for c in driver.set_page_load_timeout.call_args_list], [2, 90])

    def test_slow_homepage_waits_for_dom_readiness_instead_of_fixed_delay(self):
        driver = self.driver()
        driver.execute_script.side_effect = [{"ready": False, "reason": "app_loading"}, {"ready": True}]
        self.assertTrue(self.wait(driver)["ready"])
        self.assertAlmostEqual(self.now, 0.5)
        self.assertEqual(driver.execute_script.call_count, 2)

    def test_timeout_keeps_loading_and_never_refreshes_or_stops_page(self):
        driver = self.driver(state={"ready": False, "reason": "app_loading"})
        self.assertEqual(self.wait(driver), {"ready": False, "reason": "timeout"})
        self.assertAlmostEqual(self.now, 2)
        driver.get.assert_not_called()
        self.assertTrue(all("window.stop" not in c.args[0] for c in driver.execute_script.call_args_list))

    def test_slow_probe_cannot_report_ready_after_budget_is_exhausted(self):
        driver = self.driver()

        def slow_probe(_script):
            self.now = 3
            return {"ready": True}

        driver.execute_script.side_effect = slow_probe
        self.assertEqual(self.wait(driver), {"ready": False, "reason": "timeout"})

    def test_navigation_failure_preserves_original_timeout_and_omits_private_error(self):
        driver = self.driver(url="https://chatgpt.com/api/auth/session")
        driver.get.side_effect = RuntimeError("private@example.test private-token")
        self.assertEqual(self.wait(driver), {"ready": False, "reason": "navigation_failed"})
        self.assertEqual(driver.set_page_load_timeout.call_args.args, (90,))
        driver.execute_script.assert_not_called()

    def test_origin_change_and_unavailable_probe_never_claim_readiness(self):
        for url, state, reason in (
            ("https://chatgpt.com.other.test/", {"ready": True}, "foreign_origin"),
            ("https://chatgpt.com/", {"ready": False, "reason": "foreign_origin"}, "foreign_origin"),
            ("https://chatgpt.com/", None, "probe_unavailable"),
        ):
            with self.subTest(url=url, reason=reason):
                driver = self.driver(url=url)
                driver.execute_script.return_value = state
                self.assertEqual(self.wait(driver), {"ready": False, "reason": reason})
                driver.get.assert_not_called()

    def test_cancellation_is_not_converted_to_optional_homepage_failure(self):
        driver = self.driver()
        budget = StageBudget.start(10, clock=lambda: 0, cancel=lambda: True)
        with patch.object(session_auth, "_check_manual_stop"), self.assertRaises(CancellationRequested):
            session_auth._wait_registration_homepage(driver, budget=budget)
        driver.execute_script.assert_not_called()

    def test_roxy_entrypoint_observes_stop_requested_during_homepage_wait(self):
        from core.registration_service import StopRequested

        for ready in (False, True):
            with self.subTest(ready=ready):
                driver = self.driver()
                stopped = [False]

                def probe(_script):
                    stopped[0] = True
                    return {"ready": ready, "reason": "ready" if ready else "app_loading"}

                driver.execute_script.side_effect = probe
                with patch("core.registration_service.is_stop_requested", side_effect=lambda: stopped[0]), patch(
                    "core.registration.state_machine.time.sleep", side_effect=self.sleep,
                ), self.assertRaises(StopRequested):
                    roxy._wait_registration_homepage(driver, budget=StageBudget(2, clock=lambda: self.now))
                driver.get.assert_not_called()
                driver.execute_script.assert_called_once()

    def test_registration_session_read_keeps_homepage_loaded(self):
        driver = self.driver()
        expected = {"accessToken": "unit-token", "user": {"email": "unit@example.test"}}
        with patch.object(session_auth, "_auth_terminal_page_state", return_value=None), patch.object(
            session_auth, "_read_chatgpt_session_once", return_value=expected,
        ), patch.object(session_auth, "_safe_get") as navigate:
            self.assertIs(session_auth._fetch_chatgpt_session(driver, prefer_homepage=True), expected)
        navigate.assert_not_called()

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证首页 DOM 就绪条件")
    def test_dom_probe_requires_visible_hydrated_controls_and_rejects_auth_pages(self):
        tree = ast.parse(inspect.getsource(session_auth._wait_registration_homepage))
        script = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                      and isinstance(n.value, str) and "const trusted" in n.value)
        source = r"""
        const probe = new Function(SCRIPT);
        const control = hydrated => ({tagName:'TEXTAREA',offsetWidth:10, disabled:false, readOnly:false,
          getAttribute:()=>null, ...(hydrated ? {'__reactProps$unit':{}} : {})});
        const run = ({path='/', hydrated=true, hidden=false, dialog=false, foreign=false, contenteditable=null}={}) => {
          global.location={origin:foreign?'https://other.test':'https://chatgpt.com', pathname:path};
          global.getComputedStyle=()=>({visibility:hidden?'hidden':'visible',display:'block'});
          const input=control(hydrated),button=control(hydrated);
          if(contenteditable!==null) {input.tagName='DIV';input.isContentEditable=contenteditable;}
          const modal={...control(hydrated),querySelectorAll:()=>[button]};
          global.document={querySelector:()=>dialog?null:input,querySelectorAll:()=>dialog?[modal]:[]};
          return probe().ready;
        };
        console.log(JSON.stringify([run(),run({hydrated:false}),run({hidden:true}),
          run({dialog:true}),run({path:'/auth/login'}),run({path:'/api/auth/session'}),run({foreign:true}),
          run({contenteditable:false}),run({contenteditable:true})]));
        """.replace("SCRIPT", json.dumps(script))
        result = subprocess.run([shutil.which("node"), "-e", source], capture_output=True,
                                text=True, check=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), [True, False, False, False, False, False, False, False, True])


class LightweightRegistrationPageTests(unittest.TestCase):
    def driver(self, url="https://chatgpt.com/"):
        driver = SimpleNamespace(
            current_url=url, timeouts=SimpleNamespace(page_load=90),
            execute_script=Mock(), set_page_load_timeout=Mock(),
        )
        driver.get = Mock(side_effect=lambda value: setattr(driver, "current_url", value))
        return driver

    def park(self, driver, *, budget=None):
        with patch.object(session_auth, "_check_manual_stop"):
            return session_auth._park_verified_registration_page(
                driver, budget=budget or StageBudget.start(3),
            )

    def test_verified_homepage_stops_loading_and_keeps_same_origin_for_plan_fetch(self):
        driver = self.driver()
        calls = Mock()
        calls.attach_mock(driver.execute_script, "stop")
        calls.attach_mock(driver.get, "navigate")
        budget = StageBudget(3, clock=lambda: 0)
        self.assertTrue(self.park(driver, budget=budget))
        self.assertEqual([c[0] for c in calls.mock_calls], ["stop", "navigate"])
        driver.execute_script.assert_called_once_with("window.stop();")
        driver.get.assert_called_once_with("https://chatgpt.com/api/auth/session")
        self.assertEqual([c.args[0] for c in driver.set_page_load_timeout.call_args_list], [3, 90])

    def test_session_document_does_not_reload_or_repeat_session_request(self):
        driver = self.driver("https://chatgpt.com/api/auth/session")
        self.assertTrue(self.park(driver))
        driver.get.assert_not_called()
        driver.execute_script.assert_not_called()

    def test_foreign_or_credentialed_origin_is_not_stopped_or_navigated(self):
        for url in ("https://auth.openai.com/about-you", "https://chatgpt.com.evil.test/",
                    "http://chatgpt.com/", "https://chatgpt.com:8443/", "https://user@chatgpt.com/"):
            with self.subTest(url=url):
                driver = self.driver(url)
                self.assertFalse(self.park(driver))
                driver.get.assert_not_called()
                driver.execute_script.assert_not_called()

    def test_failed_stop_script_still_attempts_lightweight_navigation(self):
        driver = self.driver()
        driver.execute_script.side_effect = RuntimeError("脚本连接暂时不可用")
        self.assertTrue(self.park(driver))
        driver.get.assert_called_once()

    def test_navigation_failure_restores_timeout_without_exposing_private_error(self):
        driver = self.driver()
        driver.get.side_effect = RuntimeError("private@example.test private-token")
        with self.assertLogs(session_auth.logger, "WARNING") as logged:
            self.assertFalse(self.park(driver))
        self.assertEqual(driver.set_page_load_timeout.call_args.args, (90,))
        self.assertNotIn("private", str(logged.output))

    def test_redirect_does_not_claim_lightweight_page_ready(self):
        driver = self.driver()
        driver.get.side_effect = lambda _value: setattr(driver, "current_url", "https://chatgpt.com/auth/login")
        self.assertFalse(self.park(driver))

    def test_spent_budget_stops_heavy_page_without_starting_new_request(self):
        driver = self.driver()
        self.assertFalse(self.park(driver, budget=StageBudget(0, clock=lambda: 0)))
        driver.execute_script.assert_called_once_with("window.stop();")
        driver.get.assert_not_called()

    def test_cancellation_propagates_before_any_page_mutation(self):
        driver = self.driver()
        with self.assertRaises(CancellationRequested):
            self.park(driver, budget=StageBudget.start(10, clock=lambda: 0, cancel=lambda: True))
        driver.get.assert_not_called()
        driver.execute_script.assert_not_called()

    def test_stop_during_navigation_propagates_after_restoring_timeout(self):
        from core.registration_service import StopRequested

        driver = self.driver()
        stopped = [False]

        def navigate(value):
            driver.current_url = value
            stopped[0] = True

        driver.get.side_effect = navigate
        with patch("core.registration_service.is_stop_requested", side_effect=lambda: stopped[0]), self.assertRaises(StopRequested):
            session_auth._park_verified_registration_page(driver, budget=StageBudget.start(3), check_stop=roxy._check_manual_stop)
        self.assertEqual(driver.set_page_load_timeout.call_args.args, (90,))
