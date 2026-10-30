"""待确认 TOTP 检查点可恢复登录，但必须另行确认远端启用状态。"""
import json
import shutil
import subprocess
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from core.accounts import credentials as account_credentials
from core.codex import retry_service as codex_retry_service
from core.auth.browser import mfa_auth
from core.auth.browser.auth_context import AuthExecutionContext, execution_context
from core.auth.state_machine import CancellationRequested, StageBudget, StageTimeout


_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


class ExistingTotpProbeTests(unittest.TestCase):
    def _driver(self):
        driver = Mock(current_url="https://chatgpt.com/")
        driver.timeouts.script = 8
        driver.execute_async_script.return_value = {"confirmed": True, "reason": "totp_enabled"}
        return driver

    def _script_results(self, cases):
        driver = self._driver()
        mfa_auth._probe_existing_roxy_totp(driver, "fixture@example.test")
        script = driver.execute_async_script.call_args.args[0]
        source = r"""
        (async () => {
          const outputs = [];
          for (const fixture of CASES) {
            const calls = [];
            let aborted = false, callbacks = 0, firstSignal;
            global.location = {href:fixture.url || 'https://chatgpt.com/settings/security'};
            global.fetch = async (url, options) => {
              firstSignal ||= options.signal;
              calls.push({url, method:options.method, credentials:options.credentials,
                sharedSignal:firstSignal === options.signal,
                auth:options.headers.Authorization === 'Bearer fixture-token'});
              if (fixture.hang === calls.length) return new Promise((resolve, reject) => {
                options.signal.addEventListener('abort', () => { aborted = true; reject(new Error('aborted')); });
              });
              const session = url === '/api/auth/session';
              if (session && fixture.changedUrl) location.href = fixture.changedUrl;
              return {status:(session ? fixture.sessionStatus : fixture.infoStatus) ?? 200,
                json:async () => {
                  if (session ? fixture.badSessionJson : fixture.badInfoJson) throw new Error('private body');
                  return session ? (Object.hasOwn(fixture, 'session') ? fixture.session : {
                    accessToken:'fixture-token',user:{email:'Fixture@Example.test'}
                  }) : fixture.info;
                }};
            };
            const result = await new Promise(resolve => new Function(SCRIPT)(
              'fixture@example.test', 30, value => { callbacks++; resolve(value); }
            ));
            await new Promise(resolve => setTimeout(resolve, 0));
            outputs.push({result,calls,aborted,callbacks});
          }
          process.stdout.write(JSON.stringify(outputs));
        })().catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
        """.replace("CASES", json.dumps(cases)).replace("SCRIPT", json.dumps(script))
        result = subprocess.run([shutil.which("node"), "-e", source], capture_output=True, text=True, check=True, timeout=10)
        return json.loads(result.stdout)

    def _info(self, **values):
        return {"mfa_enabled": True, "mfa_enabled_v2": True, "factors": {
            "totp": [{"id": "private-factor-id", "factor_type": "totp", "is_recovery": False, "metadata": None}],
            "sms": [], "passkeys": [], "push_auth": None,
        }, **values}

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证实际只读脚本")
    def test_actual_script_requires_strict_flags_and_non_recovery_totp_factor(self):
        infos = [self._info(), self._info(mfa_enabled="true"), self._info(mfa_enabled_v2=1),
                 self._info(mfa_enabled=False)]
        for totp in ([], None, {}, [None], ["totp"], [{"factor_type": "sms", "is_recovery": False}],
                     [{"factor_type": "totp", "is_recovery": True}], [{"factor_type": "totp"}]):
            infos.append(self._info(factors={"totp": totp, "sms": [{"id": "private-sms"}], "passkeys": [{}]}))
        results = self._script_results([{"info": info} for info in infos])
        self.assertEqual([row["result"]["confirmed"] for row in results], [True] + [False] * (len(infos) - 1))
        for row in results:
            self.assertEqual(set(row["result"]), {"confirmed", "reason"})
            self.assertEqual([call["method"] for call in row["calls"]], ["GET", "GET"])
            self.assertTrue(all(call["sharedSignal"] for call in row["calls"]))
            self.assertEqual([call["auth"] for call in row["calls"]], [False, True])
        self.assertNotIn("private-factor-id", json.dumps(results))
        self.assertNotIn("fixture-token", json.dumps(results))

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证实际只读脚本")
    def test_actual_script_checks_identity_and_http_before_mfa_read(self):
        cases = [
            {"session": {"accessToken": "fixture-token", "user": {"email": "other@example.test"}}},
            {"session": {"accessToken": "fixture-token", "user": {}}},
            {"session": {"accessToken": "", "user": {"email": "fixture@example.test"}}},
            {"sessionStatus": 401}, {"badSessionJson": True},
            {"infoStatus": 403}, {"badInfoJson": True},
        ]
        results = self._script_results([{**case, "info": self._info()} for case in cases])
        self.assertEqual([row["result"]["reason"] for row in results], [
            "session_identity_mismatch", "session_identity_unverified", "session_token_missing",
            "session_http", "session_json", "mfa_http", "mfa_json",
        ])
        self.assertEqual([len(row["calls"]) for row in results], [1, 1, 1, 1, 1, 2, 2])
        self.assertTrue(all(row["result"]["confirmed"] is False for row in results))

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证实际只读脚本")
    def test_actual_script_rejects_untrusted_origin_and_navigation_race(self):
        urls = ["https://chatgpt.com.evil.test/", "http://chatgpt.com/", "https://chatgpt.com:8443/",
                "https://user:password@chatgpt.com/"]
        results = self._script_results([{"url": url} for url in urls] + [{"changedUrl": urls[0]}])
        self.assertEqual([len(row["calls"]) for row in results], [0, 0, 0, 0, 1])
        self.assertTrue(all(row["result"] == {"confirmed": False, "reason": "untrusted_origin"} for row in results))

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证实际只读脚本")
    def test_actual_script_aborts_either_get_with_one_shared_timer_and_callback(self):
        results = self._script_results([{"hang": 1}, {"hang": 2}])
        for row in results:
            self.assertEqual(row["result"], {"confirmed": False, "reason": "timeout"})
            self.assertTrue(row["aborted"])
            self.assertEqual(row["callbacks"], 1)

    def test_python_origin_guard_never_runs_browser_script_for_untrusted_urls(self):
        for url in ("https://auth.openai.com/", "https://chatgpt.com.evil.test/", "http://chatgpt.com/",
                    "https://chatgpt.com:8443/", "https://user@chatgpt.com/"):
            with self.subTest(url=url):
                driver = self._driver()
                driver.current_url = url
                self.assertEqual(mfa_auth._probe_existing_roxy_totp(driver, "fixture@example.test"), {
                    "confirmed": False, "reason": "untrusted_origin",
                })
                driver.execute_async_script.assert_not_called()

    def test_probe_respects_smaller_context_deadline_and_restores_script_timeout(self):
        driver = self._driver()
        with patch("core.auth.browser.auth_context.time.monotonic", return_value=0.0):
            with execution_context(AuthExecutionContext(budget=StageBudget(0.5, clock=lambda: 0), deadline=0.125)):
                self.assertTrue(mfa_auth._probe_existing_roxy_totp(driver, "fixture@example.test")["confirmed"])
        self.assertLessEqual(driver.set_script_timeout.call_args_list[0].args[0], 0.125)
        self.assertLessEqual(driver.execute_async_script.call_args.args[2], 125)
        self.assertEqual(driver.set_script_timeout.call_args_list[-1].args, (8,))

    def test_probe_keeps_cancellation_and_budget_expiry_out_of_dom_fallback(self):
        for error in (CancellationRequested("用户取消"), StageTimeout("预算耗尽")):
            with self.subTest(error=type(error).__name__):
                driver = self._driver()
                driver.execute_async_script.side_effect = error
                with self.assertRaises(type(error)):
                    mfa_auth._probe_existing_roxy_totp(driver, "fixture@example.test")
                self.assertEqual(driver.set_script_timeout.call_args_list[-1].args, (8,))

    def test_probe_browser_error_and_invalid_return_are_unconfirmed_and_filtered(self):
        driver = self._driver()
        driver.execute_async_script.side_effect = RuntimeError("private-token")
        self.assertEqual(mfa_auth._probe_existing_roxy_totp(driver, "fixture@example.test"), {
            "confirmed": False, "reason": "read_failed",
        })
        self.assertEqual(driver.set_script_timeout.call_args_list[-1].args, (8,))
        driver.execute_async_script.side_effect = None
        driver.execute_async_script.return_value = {"confirmed": True, "reason": "private-token", "token": "private"}
        self.assertEqual(mfa_auth._probe_existing_roxy_totp(driver, "fixture@example.test"), {
            "confirmed": False, "reason": "invalid_response",
        })


class PendingTotpCredentialsTests(unittest.TestCase):
    def test_login_reads_pending_checkpoint_without_promoting_it(self):
        for encode in (dict, json.dumps):
            with self.subTest(encoding=encode.__name__):
                account = {
                    "totp_secret": "",
                    "extra_json": encode({
                        "account_password": "saved-password",
                        "totp_pending_secret": f" {_SECRET} ",
                        "totp_setup_pending": True,
                    }),
                }
                before = json.dumps(account, sort_keys=True)
                with patch("core.db.get_account_by_email", return_value=account):
                    credentials = account_credentials.get_account_login_credentials("fixture@example.test")
                self.assertEqual(credentials, ("saved-password", _SECRET))
                self.assertEqual(json.dumps(account, sort_keys=True), before)

    def test_active_secret_takes_precedence_over_pending_checkpoint(self):
        account = {
            "totp_secret": " active-secret ",
            "extra_json": {"totp_pending_secret": _SECRET, "totp_setup_pending": True},
        }
        with patch("core.db.get_account_by_email", return_value=account):
            self.assertEqual(
                account_credentials.get_account_login_credentials("fixture@example.test"),
                ("", "active-secret"),
            )

    def test_blank_active_secret_uses_pending_checkpoint(self):
        with patch("core.db.get_account_by_email", return_value={
            "totp_secret": "   ", "extra_json": {"totp_pending_secret": _SECRET},
        }):
            self.assertEqual(
                account_credentials.get_account_login_credentials("fixture@example.test"), ("", _SECRET),
            )

    def test_invalid_extra_does_not_break_active_credentials(self):
        for extra in ("{invalid-json", "[]", [], None):
            with self.subTest(extra=extra), patch(
                "core.db.get_account_by_email",
                return_value={"account_password": "saved-password", "totp_secret": _SECRET, "extra_json": extra},
            ):
                self.assertEqual(
                    account_credentials.get_account_login_credentials("fixture@example.test"),
                    ("saved-password", _SECRET),
                )


class PendingTotpBrowserRecoveryTests(unittest.TestCase):
    def test_confirmed_remote_totp_recovers_candidate_without_old_settings_toggle(self):
        driver = Mock(current_url="https://chatgpt.com/api/auth/session")
        driver.timeouts.script = 8
        driver.execute_async_script.return_value = {"confirmed": True, "reason": "totp_enabled"}
        on_secret = Mock()
        with patch.object(mfa_auth, "_open_chatgpt_security_settings", side_effect=RuntimeError("旧开关定位已失效")) as settings, patch.object(
            mfa_auth, "_human_click",
        ) as click:
            self.assertEqual(mfa_auth.setup_roxy_2fa(
                driver, "fixture@example.test", existing_secret=_SECRET, on_secret=on_secret,
            ), _SECRET)
        settings.assert_not_called()
        click.assert_not_called()
        on_secret.assert_not_called()
        driver.execute_async_script.assert_called_once()
        self.assertEqual(driver.set_script_timeout.call_args_list[-1].args, (8,))

    def test_unverified_or_conflicting_session_identity_never_falls_back_to_settings(self):
        for reason in ("session_identity_mismatch", "session_identity_unverified"):
            with self.subTest(reason=reason):
                driver = Mock(current_url="https://chatgpt.com/")
                driver.timeouts.script = 8
                driver.execute_async_script.return_value = {"confirmed": False, "reason": reason}
                toggle = Mock()
                toggle.get_attribute.return_value = "true"
                with patch.object(mfa_auth, "_open_chatgpt_security_settings", return_value=toggle) as settings:
                    with self.assertRaisesRegex(RuntimeError, reason):
                        mfa_auth.setup_roxy_2fa(driver, "fixture@example.test", existing_secret=_SECRET)
                settings.assert_not_called()

    def _recover(self, *, enabled, executor="browser", pending_flag=True, browser_fallback_enabled=True):
        extra = {"account_password": "saved-password", "totp_pending_secret": _SECRET}
        if pending_flag:
            extra["totp_setup_pending"] = True
        account = {
            "id": 9, "email": "fixture@example.test", "access_token": "fixture-token",
            "totp_secret": "", "extra_json": json.dumps(extra),
        }
        transitions = []
        toggle = Mock()
        toggle.get_attribute.side_effect = lambda name: (
            "true" if enabled else "false"
        ) if name == "aria-checked" else ""

        def open_settings(_driver):
            self.assertEqual(account["totp_secret"], "")
            self.assertEqual(transitions, [])
            return toggle

        def save_secret(_email, secret, *, setup_pending):
            transitions.append(setup_pending)
            account["totp_secret"] = secret
            return True

        with ExitStack() as stack:
            stack.enter_context(patch.object(codex_retry_service.db, "get_account_by_email", return_value=account))
            stack.enter_context(patch.object(codex_retry_service.db, "update_account_totp_secret", side_effect=save_secret))
            stack.enter_context(patch.object(codex_retry_service.db, "update_account_twofa_status", return_value=True))
            stack.enter_context(patch.object(codex_retry_service.db, "update_account_session", return_value=True))
            stack.enter_context(patch.object(codex_retry_service.account_task_store, "append_event"))
            stack.enter_context(patch.object(codex_retry_service, "check_stop_requested"))
            stack.enter_context(patch("config.twofa.get_twofa_driver", return_value=executor))
            stack.enter_context(patch.object(mfa_auth, "_open_chatgpt_security_settings", side_effect=open_settings))
            stack.enter_context(patch.object(mfa_auth, "_human_click"))
            stack.enter_context(patch.object(
                mfa_auth, "_wait_mfa_enrollment_step", side_effect=RuntimeError("远端尚未确认启用"),
            ))
            stack.enter_context(patch(
                "core.auth.browser.selenium_auth.setup_roxy_2fa", side_effect=mfa_auth.setup_roxy_2fa,
            ))
            stack.enter_context(patch(
                "core.auth.browser.selenium_auth.fetch_chatgpt_session",
                **({"return_value": {"accessToken": "fixture-token"}} if not browser_fallback_enabled else {
                    "side_effect": AssertionError("待确认密钥恢复不应先重新执行协议 enroll"),
                }),
            ))
            stack.enter_context(patch(
                "core.accounts.export.setup_2fa_protocol", side_effect=RuntimeError("协议恢复失败"),
            ))
            stack.enter_context(patch("core.auth.protocol.session.BrowserSession"))
            setup = codex_retry_service._build_roxy_account_setup(
                "fixture@example.test", 101, include_password=False,
                browser_fallback_enabled=browser_fallback_enabled,
            )
            if executor == "protocol" and not browser_fallback_enabled:
                with self.assertRaisesRegex(RuntimeError, "协议恢复失败"):
                    setup(Mock())
                self.assertEqual(account["totp_secret"], "")
                self.assertEqual(transitions, [])
            elif enabled:
                self.assertTrue(setup(Mock()))
                self.assertEqual(account["totp_secret"], _SECRET)
                self.assertEqual(transitions, [True, False])
            else:
                with self.assertRaisesRegex(RuntimeError, "远端尚未确认启用"):
                    setup(Mock())
                self.assertEqual(account["totp_secret"], "")
                self.assertEqual(transitions, [])
                self.assertEqual(json.loads(account["extra_json"])["totp_pending_secret"], _SECRET)

    def test_pending_checkpoint_is_promoted_only_after_enabled_toggle(self):
        self._recover(enabled=True)

    def test_disabled_toggle_does_not_promote_or_discard_pending_checkpoint(self):
        self._recover(enabled=False)

    def test_protocol_fallback_checks_existing_pending_before_reenrollment(self):
        self._recover(enabled=True, executor="protocol")

    def test_pending_secret_without_flag_is_not_treated_as_confirmed(self):
        self._recover(enabled=True, pending_flag=False)

    def test_disabled_browser_fallback_does_not_force_pending_recovery_into_browser(self):
        self._recover(enabled=True, executor="protocol", browser_fallback_enabled=False)


if __name__ == "__main__":
    unittest.main()
