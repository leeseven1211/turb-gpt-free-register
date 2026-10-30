# -*- coding: utf-8 -*-
import unittest
import ast
import inspect
import json
import shutil
import subprocess
from unittest.mock import Mock
from types import SimpleNamespace

from core.registration import plan_capture as registration_plan_capture


class RegistrationPlanCaptureTests(unittest.TestCase):
    def _payload(self):
        return {
            "accounts": {
                "default": {
                    "account": {
                        "account_id": "acct-1",
                        "plan_type": "free",
                    },
                    "entitlement": {
                        "subscription_plan": "chatgptfreeplan",
                    },
                    "eligible_promo_campaigns": {
                        "plus": {
                            "id": "plus-trial",
                            "metadata": {
                                "title": "Plus trial",
                                "duration": {"num_periods": 1, "period": "month"},
                            },
                        },
                    },
                    "eligible_offers": {
                        "offers": [{"id": "offer-1"}],
                    },
                }
            }
        }

    def test_normalize_capture_extracts_trial_and_offer(self):
        result = registration_plan_capture._normalize_capture(
            {"status": 200, "captured_at": "2026-08-14T00:00:00Z", "data": self._payload()},
            token="",
        )
        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["current_plan_type"], "free")
        self.assertTrue(result["plus_trial_eligible"])
        self.assertEqual(result["plus_promo_kind"], "free_trial")
        self.assertEqual(result["plus_trial_campaign_id"], "plus-trial")
        self.assertEqual(result["eligible_offer_ids"], ["offer-1"])
        self.assertEqual(result["trigger"], "registration_browser_response")

    def test_invalid_capture_is_ignored(self):
        self.assertIsNone(
            registration_plan_capture._normalize_capture(
                {"status": 200, "data": {"not_accounts": {}}}, token=""
            )
        )

    def test_read_selenium_returns_first_valid_capture(self):
        driver = Mock()
        driver.execute_script.return_value = {
            "status": 200,
            "data": self._payload(),
        }
        result = registration_plan_capture.read_selenium(driver, token="", wait_seconds=0)
        self.assertTrue(result["plus_trial_eligible"])
        driver.execute_script.assert_called_once()

    def test_read_or_fetch_selenium_queries_inside_signed_in_browser(self):
        driver = Mock()
        driver.execute_script.return_value = None
        driver.execute_async_script.return_value = {
            "status": 200,
            "captured_at": "2026-08-19T00:00:00Z",
            "data": self._payload(),
        }

        result = registration_plan_capture.read_or_fetch_selenium(
            driver,
            token="header.payload.signature",
            wait_seconds=0,
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["plus_trial_eligible"])
        self.assertEqual(result["source"], "browser_fallback_request")
        driver.execute_async_script.assert_called_once()

    def test_browser_fetch_restores_script_timeout_after_success_and_failure(self):
        for fails in (False, True):
            with self.subTest(fails=fails):
                driver = SimpleNamespace(timeouts=SimpleNamespace(script=8),
                    set_script_timeout=Mock(), execute_async_script=Mock(return_value={
                        "status": 200, "data": self._payload(),
                    }))
                if fails:
                    driver.execute_async_script.side_effect = TimeoutError("模拟套餐请求超时")
                result = registration_plan_capture.fetch_selenium(driver, "unit-token", timeout_seconds=3)
                self.assertEqual(bool(result), not fails)
                self.assertEqual(driver.set_script_timeout.call_args_list[-1].args, (8,))

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证浏览器请求的实际超时")
    def test_browser_timeout_aborts_pending_fetch_and_settles_once(self):
        tree = ast.parse(inspect.getsource(registration_plan_capture.fetch_selenium))
        script = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
                      and isinstance(node.value, str) and "const token = arguments[0]" in node.value)
        harness = r"""
        global.location={origin:'https://chatgpt.com'};
        global.localStorage={getItem:()=>null};
        let aborted=false, callbackCount=0;
        global.fetch=(_url, options)=>new Promise((_resolve,reject)=>{
          if(options.signal) options.signal.addEventListener('abort',()=>{
            aborted=true;reject(new Error('aborted'));
          });
        });
        (async()=>{
          const result=await Promise.race([
            new Promise(resolve=>new Function(SCRIPT)('unit-token','/unit',15,value=>{
              callbackCount++;resolve(value);
            })),
            new Promise(resolve=>setTimeout(()=>resolve(null),100)),
          ]);
          console.log(JSON.stringify({timed_out:result?.error_type==='timeout',aborted,callbackCount}));
        })();
        """.replace("SCRIPT", json.dumps(script))
        output = subprocess.run([shutil.which("node"), "-e", harness], capture_output=True,
                                text=True, check=True, timeout=10)
        self.assertEqual(json.loads(output.stdout), {"timed_out": True, "aborted": True, "callbackCount": 1})

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证套餐请求的来源边界")
    def test_browser_fetch_does_not_send_token_from_auth_or_untrusted_origin(self):
        tree = ast.parse(inspect.getsource(registration_plan_capture.fetch_selenium))
        script = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
                      and isinstance(node.value, str) and "const token = arguments[0]" in node.value)
        harness = r"""
        global.localStorage={getItem:()=>null};
        let requests=0;
        global.fetch=async()=>{requests++;return {status:200,json:async()=>({})};};
        (async()=>{
          const results=[];
          for(const origin of ['https://auth.openai.com','https://chatgpt.com.other.test']) {
            global.location={origin};
            const result=await new Promise(resolve=>new Function(SCRIPT)('unit-token','/unit',15,resolve));
            results.push(result.error_type==='origin_changed');
          }
          console.log(JSON.stringify({requests,results}));
        })();
        """.replace("SCRIPT", json.dumps(script))
        output = subprocess.run([shutil.which("node"), "-e", harness], capture_output=True,
                                text=True, check=True, timeout=10)
        self.assertEqual(json.loads(output.stdout), {"requests": 0, "results": [True, True]})


if __name__ == "__main__":
    unittest.main()
