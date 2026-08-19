# -*- coding: utf-8 -*-
"""周期任务调度的重启行为。

改造前三个定时任务只靠进程内计时：启动等一个初始延迟就跑一轮。于是每重启一次
就重新执行一次，按天调度的 Codex Token 刷新在频繁重启时形同虚设。
"""
import threading
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from core import scheduler_state
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
        from core import postgres_store
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
        from core import (codex_token_refresh_service, deactivation_mail_service,
                          token_refresh_service)
        names = {
            deactivation_mail_service.SCHEDULER_TASK,
            token_refresh_service.SCHEDULER_TASK,
            codex_token_refresh_service.SCHEDULER_TASK,
        }
        self.assertEqual(len(names), 3, "任务名必须互不相同，否则会共用同一条调度记录")


if __name__ == "__main__":
    unittest.main()
