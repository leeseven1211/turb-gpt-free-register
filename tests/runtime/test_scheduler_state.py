# -*- coding: utf-8 -*-
"""周期任务调度的重启行为。

改造前三个定时任务只靠进程内计时：启动等一个初始延迟就跑一轮。于是每重启一次
就重新执行一次，按天调度的 Codex Token 刷新在频繁重启时形同虚设。
"""
import threading
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from unittest.mock import patch

from core.runtime import scheduler_state
from tests.support_pg import PostgresTestCase


class DueCalculationTests(PostgresTestCase):
    def test_never_run_task_is_due_immediately(self):
        self.assertEqual(scheduler_state.seconds_until_due("fresh_task", 3600), 0.0)

    def test_just_ran_task_is_not_due(self):
        scheduler_state.mark_ran("t1")
        remaining = scheduler_state.seconds_until_due("t1", 3600)
        self.assertGreater(remaining, 3500)
        self.assertLessEqual(remaining, 3600)

    def test_task_becomes_due_after_the_interval_elapses(self):
        scheduler_state.mark_ran("t2")
        self.assertGreater(scheduler_state.seconds_until_due("t2", 3600), 0)
        # 用一个更短的间隔来表达"已经过了足够久"
        self.assertEqual(scheduler_state.seconds_until_due("t2", 0), 0.0)

    def test_clock_moved_backwards_does_not_wedge_the_task(self):
        """系统时间被往前调过时必须当成到期，否则任务会永远等下去。"""
        future = (datetime.now() + timedelta(hours=5)).isoformat(timespec="seconds")
        with patch.object(scheduler_state, "last_run_at",
                          return_value=datetime.fromisoformat(future)):
            self.assertEqual(scheduler_state.seconds_until_due("t3", 3600), 0.0)

    def test_state_survives_a_reload(self):
        """这正是重启场景：新进程读到的必须是上次跑完的时间。"""
        scheduler_state.mark_ran("persisted")
        from core.storage import postgres as postgres_store
        postgres_store.reset_cache()
        self.assertIsNotNone(scheduler_state.last_run_at("persisted"))
        self.assertGreater(scheduler_state.seconds_until_due("persisted", 86400), 86000)

    def test_reset_makes_the_task_due_again(self):
        scheduler_state.mark_ran("t4")
        self.assertGreater(scheduler_state.seconds_until_due("t4", 3600), 0)
        scheduler_state.reset("t4")
        self.assertEqual(scheduler_state.seconds_until_due("t4", 3600), 0.0)


class RunPeriodicTests(PostgresTestCase):
    def _run_once(self, task, **kw):
        """跑一轮就让循环退出，便于断言。"""
        stop = threading.Event()
        calls = []

        def work():
            calls.append(1)
            stop.set()          # 跑完立刻结束循环
            return {"ok": True}

        scheduler_state.run_periodic(
            task=task, label="Test", work=work,
            enabled=kw.get("enabled", lambda: True),
            interval_seconds=kw.get("interval", lambda: 3600),
            initial_delay_seconds=0, stop=stop,
        )
        return calls

    def test_runs_when_due_and_records_the_run(self):
        calls = self._run_once("periodic_a")
        self.assertEqual(len(calls), 1)
        self.assertIsNotNone(scheduler_state.last_run_at("periodic_a"))

    def test_does_not_rerun_a_task_that_already_ran_within_the_interval(self):
        """重启后的核心诉求：当天跑过就不该再跑一次。"""
        scheduler_state.mark_ran("periodic_b")
        stop = threading.Event()
        calls = []

        def work():
            calls.append(1)
            return {}

        # 让循环有机会判断一次就退出
        threading.Timer(0.3, stop.set).start()
        scheduler_state.run_periodic(
            task="periodic_b", label="Test", work=work,
            enabled=lambda: True, interval_seconds=lambda: 86400,
            initial_delay_seconds=0, stop=stop,
        )
        self.assertEqual(calls, [], "间隔内不应重复执行")

    def test_disabled_task_does_not_run(self):
        stop = threading.Event()
        calls = []
        threading.Timer(0.3, stop.set).start()
        scheduler_state.run_periodic(
            task="periodic_c", label="Test", work=lambda: calls.append(1),
            enabled=lambda: False, interval_seconds=lambda: 1,
            initial_delay_seconds=0, stop=stop,
        )
        self.assertEqual(calls, [])

    def test_failing_work_still_records_the_attempt(self):
        """失败也要记时间，否则会变成每 60 秒重试一轮，把外部服务打爆。"""
        stop = threading.Event()

        def boom():
            stop.set()
            raise RuntimeError("外部服务不可用")

        scheduler_state.run_periodic(
            task="periodic_d", label="Test", work=boom,
            enabled=lambda: True, interval_seconds=lambda: 3600,
            initial_delay_seconds=0, stop=stop,
        )
        self.assertIsNotNone(scheduler_state.last_run_at("periodic_d"))


class ServiceWiringTests(PostgresTestCase):
    def test_all_three_services_expose_a_scheduler_task_name(self):
        from core.codex import token_refresh_service as codex_token_refresh_service
        from core.accounts.deactivation import mail_scan as deactivation_mail_service
        from core.accounts import token_refresh as token_refresh_service
        names = {
            deactivation_mail_service.SCHEDULER_TASK,
            token_refresh_service.SCHEDULER_TASK,
            codex_token_refresh_service.SCHEDULER_TASK,
        }
        self.assertEqual(len(names), 3, "任务名必须互不相同，否则会共用同一条调度记录")


class SchedulerHotReloadTests(unittest.TestCase):
    def _service_cases(self):
        from config import account, codex, email
        from core.accounts import auth_context_cleanup as account_auth_context_service
        from core.codex import token_refresh_service as codex_token_refresh_service
        from core.accounts.deactivation import mail_scan as deactivation_mail_service
        from core.accounts import token_refresh as token_refresh_service

        return (
            (token_refresh_service, "start_periodic_refresher", "enqueue_due_accounts",
             codex, "AT_AUTO_REFRESH_ENABLED"),
            (codex_token_refresh_service, "start_periodic_refresher", "enqueue_due_credentials",
             codex, "CODEX_TOKEN_AUTO_REFRESH_ENABLED"),
            (deactivation_mail_service, "start_periodic_scanner", "enqueue_due_accounts",
             email, "EMAIL_BUTLER_RISK_SCAN_ENABLED"),
            (account_auth_context_service, "start_periodic_cleanup", "cleanup_once",
             account, "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED"),
        )

    def _isolate_startup(self, stack, service, config_module, enabled_key):
        stack.enter_context(patch.object(service, "_SCHEDULER_STARTED", False))
        stack.enter_context(patch.object(config_module, enabled_key, False))
        stack.enter_context(patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS", 30))
        if hasattr(service, "_register_worker"):
            stack.enter_context(patch.object(service, "_register_worker"))
        return stack.enter_context(patch.object(service.threading, "Thread"))

    def test_disabled_start_can_enable_and_disable_without_another_thread(self):
        """用可控等待驱动真实循环，不启动线程，也不访问调度数据库。"""
        for service, start_name, work_name, config_module, enabled_key in self._service_cases():
            with self.subTest(service=service.__name__), ExitStack() as stack:
                thread = self._isolate_startup(stack, service, config_module, enabled_key)
                work = stack.enter_context(patch.object(service, work_name))
                due = stack.enter_context(patch.object(scheduler_state, "seconds_until_due", return_value=0))
                mark_ran = stack.enter_context(patch.object(scheduler_state, "mark_ran"))
                start = getattr(service, start_name)
                self.assertTrue(start())
                self.assertFalse(start())
                thread.assert_called_once()
                thread.return_value.start.assert_called_once_with()
                work.assert_not_called()
                due.assert_not_called()

                waits = []
                before_enable = []

                def wait(seconds):
                    waits.append(seconds)
                    if len(waits) == 2:
                        before_enable.append((work.call_count, due.call_count))
                        setattr(config_module, enabled_key, True)
                    return len(waits) >= 3

                def finish_work():
                    setattr(config_module, enabled_key, False)
                    return {"ok": True}

                work.side_effect = finish_work
                event = stack.enter_context(patch.object(scheduler_state.threading, "Event"))
                event.return_value.wait.side_effect = wait
                thread.call_args.kwargs["target"]()

                self.assertEqual(before_enable, [(0, 0)], "关闭时不读取调度数据或执行业务")
                self.assertEqual(waits[1:], [60.0, 60.0], "开关仍按最多60秒轮询")
                work.assert_called_once_with()
                due.assert_called_once_with(service.SCHEDULER_TASK, service.scheduler_interval_seconds())
                mark_ran.assert_called_once_with(service.SCHEDULER_TASK)
                thread.assert_called_once()

    def test_thread_start_failure_can_be_retried(self):
        for service, start_name, _work_name, config_module, enabled_key in self._service_cases():
            with self.subTest(service=service.__name__), ExitStack() as stack:
                thread = self._isolate_startup(stack, service, config_module, enabled_key)
                stack.enter_context(patch.object(service.logger, "exception"))
                thread.return_value.start.side_effect = [RuntimeError("线程资源暂不可用"), None]
                start = getattr(service, start_name)

                self.assertFalse(start())
                self.assertFalse(service._SCHEDULER_STARTED)
                self.assertTrue(start())
                self.assertTrue(service._SCHEDULER_STARTED)
                self.assertFalse(start())
                self.assertEqual(thread.call_count, 2)

    def test_disabled_producers_do_not_read_accounts(self):
        for service, _start_name, work_name, config_module, enabled_key in self._service_cases():
            if work_name == "cleanup_once":
                continue
            reader_name = "list_codex_accounts" if work_name == "enqueue_due_credentials" else "list_accounts"
            with self.subTest(service=service.__name__), \
                 patch.object(config_module, enabled_key, False), \
                 patch.object(service.db, reader_name) as read_accounts:
                result = getattr(service, work_name)()
                self.assertEqual(result["started"], 0)
                read_accounts.assert_not_called()

    def test_codex_handler_registration_failure_can_be_retried(self):
        from core.codex import token_refresh_service as service

        with patch.object(service, "_SCHEDULER_STARTED", False), \
             patch.object(service, "_register_worker", side_effect=[RuntimeError("handler暂不可用"), None]), \
             patch.object(service.threading, "Thread") as thread, \
             patch.object(service.logger, "exception"):
            self.assertFalse(service.start_periodic_refresher())
            self.assertFalse(service._SCHEDULER_STARTED)
            thread.assert_not_called()
            self.assertTrue(service.start_periodic_refresher())
            thread.return_value.start.assert_called_once_with()

    def test_deactivation_scan_and_status_use_current_interval(self):
        from config import email
        from core.accounts.deactivation import mail_scan as service

        checked_at = (datetime.now().astimezone() - timedelta(hours=1)).isoformat()
        with patch.object(email, "EMAIL_BUTLER_RISK_SCAN_ENABLED", True), \
             patch.object(email, "EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS", 900), \
             patch.object(service.db, "list_accounts", return_value=[{
                 "id": 101, "email_source": "email_butler", "deactivation_mail_checked_at": checked_at,
             }]), \
             patch.object(service, "enqueue_bulk", return_value={
                 "started": [101], "busy": [], "skipped": [],
             }) as enqueue:
            self.assertEqual(service.enqueue_due_accounts()["started"], 1)
            enqueue.assert_called_once_with([101], trigger="scheduled")
            self.assertEqual(service.queue_settings()["interval_seconds"], 900)
            email.EMAIL_BUTLER_RISK_SCAN_ENABLED = False
            self.assertFalse(service.queue_settings()["enabled"])


if __name__ == "__main__":
    unittest.main()
