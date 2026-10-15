"""Token 兜底读取沿用剩余预算，不继承导航留下的脚本上限。"""
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.registration import session_auth
from core.registration.state_machine import StageBudget


SESSION = {"accessToken": "unit-token", "user": {"email": "unit@example.test"}}


class TokenSessionBudgetTests(unittest.TestCase):
    @contextmanager
    def session_context(self, *, probe_cost=0):
        now = [0.0]
        clock = SimpleNamespace(
            monotonic=lambda: now[0],
            sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
        )
        driver = SimpleNamespace(
            current_url="https://chatgpt.com/", timeouts=SimpleNamespace(script=8),
            set_script_timeout=Mock(), execute_async_script=Mock(return_value={
                "ok": True, "status": 200, "json_valid": True, "data": SESSION,
            }),
        )

        def probe(_driver):
            now[0] += probe_cost
            return None

        with patch.object(session_auth, "time", clock), patch.object(
            session_auth, "_auth_terminal_page_state", side_effect=probe,
        ):
            yield driver, now

    def test_complete_read_uses_remaining_parent_budget_and_restores_script_limit(self):
        with self.session_context(probe_cost=3) as (driver, now):
            budget = StageBudget(12, clock=lambda: now[0])
            self.assertIs(session_auth._fetch_chatgpt_session(
                driver, timeout=120, budget=budget, prefer_homepage=True,
            ), SESSION)
        driver.execute_async_script.assert_called_once()
        self.assertEqual(driver.execute_async_script.call_args.args[1:], (9000,))
        self.assertEqual([c.args[0] for c in driver.set_script_timeout.call_args_list], [10, 8])

    def test_shorter_call_timeout_wins_over_larger_parent_budget(self):
        with self.session_context(probe_cost=1) as (driver, now):
            self.assertIs(session_auth._fetch_chatgpt_session(
                driver, timeout=5, budget=StageBudget(120, clock=lambda: now[0]), prefer_homepage=True,
            ), SESSION)
        self.assertEqual(driver.execute_async_script.call_args.args[1:], (4000,))

    def test_each_poll_uses_time_left_after_previous_poll_and_wait(self):
        with self.session_context(probe_cost=1) as (driver, _now):
            driver.execute_async_script.side_effect = [
                {"ok": True, "status": 200, "json_valid": True, "data": {}},
                {"ok": True, "status": 200, "json_valid": True, "data": SESSION},
            ]
            self.assertIs(session_auth._fetch_chatgpt_session(driver, timeout=10, prefer_homepage=True), SESSION)
        self.assertEqual([c.args[1:] for c in driver.execute_async_script.call_args_list], [(9000,), (6000,)])
        self.assertEqual([c.args[0] for c in driver.set_script_timeout.call_args_list], [10, 8, 7, 8])

    def test_budget_spent_inspecting_page_does_not_start_another_request(self):
        with self.session_context(probe_cost=5) as (driver, _now):
            with self.assertRaisesRegex(RuntimeError, "超时"):
                session_auth._fetch_chatgpt_session(driver, timeout=5, prefer_homepage=True)
        driver.execute_async_script.assert_not_called()
        driver.set_script_timeout.assert_not_called()

    def test_failed_browser_read_restores_timeout_and_does_not_retry_after_deadline(self):
        with self.session_context() as (driver, now):
            def failed_read(*_args):
                now[0] = 5
                raise TimeoutError("模拟浏览器读取超时")

            driver.execute_async_script.side_effect = failed_read
            with self.assertRaisesRegex(RuntimeError, "超时"):
                session_auth._fetch_chatgpt_session(driver, timeout=5, prefer_homepage=True)
        driver.execute_async_script.assert_called_once()
        self.assertEqual([c.args[0] for c in driver.set_script_timeout.call_args_list], [6, 8])

    def test_session_document_fallback_read_also_receives_remaining_budget(self):
        with self.session_context(probe_cost=2) as (driver, _now):
            driver.current_url = "https://chatgpt.com/api/auth/session"
            driver.execute_script = Mock(return_value="{}")
            self.assertIs(session_auth._fetch_chatgpt_session(driver, timeout=10), SESSION)
        self.assertEqual(driver.execute_async_script.call_args.args[1:], (8000,))
