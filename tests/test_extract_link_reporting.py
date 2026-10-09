# -*- coding: utf-8 -*-
"""验证提链预检真实分支的收口事件，不调用真实账号、数据库或远端服务。"""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import extract_link_service, task_run_log
from core.task_progress import build_progress_snapshot


class ExtractLinkReportingTests(unittest.TestCase):
    def tearDown(self):
        task_run_log.clear_current_context()

    @contextmanager
    def _scenario(self, *, native, inline_results):
        events = []

        def report(*_args, **event):
            event = dict(event)
            event["id"] = len(events) + 1
            event["created_at"] = f"2026-10-09T10:00:{len(events):02d}+08:00"
            if event.get("state"):
                event["event_type"] = f"stage.{event['state']}"
            events.append(event)
            return event

        context = SimpleNamespace(
            run_id=902, task_id=901, report=Mock(side_effect=report),
            checkpoint=Mock(), finish=Mock(),
        )
        database = Mock()
        database.mark_account_extract_running.return_value = True
        database.update_account_extract.return_value = True
        database.get_account.return_value = {
            "access_token": "fixture-access-value",
            "extract_link_status": "success", "extract_link_ok": True,
            "extract_link_job_id": "fixture-job",
        }
        with ExitStack() as stack:
            stack.enter_context(patch.object(extract_link_service, "db", database))
            stack.enter_context(patch.object(extract_link_service, "logger"))
            stack.enter_context(patch.object(extract_link_service.account_task_store, "start_task"))
            stack.enter_context(patch.object(
                extract_link_service.account_task_store, "append_event", side_effect=report,
            ))
            legacy_finish = stack.enter_context(patch.object(
                extract_link_service.account_task_store, "finish_task",
            ))
            inline = stack.enter_context(patch(
                "core.live_check_service.run_account_live_check_inline", side_effect=inline_results,
            ))
            create = stack.enter_context(patch.object(
                extract_link_service, "_create_extract_job", return_value={"job_id": "fixture-job"},
            ))
            stream = stack.enter_context(patch.object(
                extract_link_service, "_iter_sse_events", return_value=iter([
                    ("result", {"result": {"payment_method": "pix"}}),
                ]),
            ))
            yield SimpleNamespace(
                context=context, operation_context=context if native else None,
                database=database, events=events, inline=inline, create=create, stream=stream,
                finish=context.finish if native else legacy_finish,
            )

    @staticmethod
    def _run(scenario):
        return extract_link_service._run_extract(
            account_id=7, email="fixture@example.test", access_token="ignored-snapshot",
            link_type="pix", cdk="fixture-cdk", trigger="manual", task_id=901,
            operation_context=scenario.operation_context, release_queue_slot=False,
        )

    @staticmethod
    def _inline(result):
        return {"accepted": True, "result": result}

    @staticmethod
    def _states(events, stage):
        return [event.get("state") for event in events if event.get("stage") == stage and event.get("state")]

    @staticmethod
    def _snapshot(scenario, result):
        return build_progress_snapshot(
            task_id=901, run_id=902, task_type="extract_link",
            run={"id": 902, "status": result["status"]}, events=scenario.events,
        )

    def test_valid_existing_token_closes_preflight_before_remote_create(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(
                native=native, inline_results=[self._inline({"ok": True, "status": "live"})],
            ) as scenario:
                result = self._run(scenario)
                self.assertTrue(result["ok"])
                self.assertEqual("success", self._states(scenario.events, "preflight")[-1])
                self.assertEqual(["skipped"], self._states(scenario.events, "refresh_token"))
                stages = [(event.get("stage"), event.get("state")) for event in scenario.events]
                self.assertLess(stages.index(("preflight", "success")), stages.index(("extract_link", "running")))
                snapshot = self._snapshot(scenario, result)
                preflight = next(step for step in snapshot["main_steps"] if step["id"] == "preflight")
                self.assertEqual("success", preflight["display_status"])
                self.assertIsNotNone(preflight["completed_at"])

    def test_expired_token_refresh_success_closes_both_started_stages(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(
                native=native, inline_results=[
                    self._inline({"ok": False, "status": "failed", "token_expired": True}),
                    self._inline({"ok": True, "status": "live"}),
                ],
            ) as scenario:
                result = self._run(scenario)
                self.assertTrue(result["ok"])
                self.assertEqual(["running", "success"], self._states(scenario.events, "refresh_token"))
                self.assertEqual("success", self._states(scenario.events, "preflight")[-1])
                self.assertEqual(2, scenario.inline.call_count)

    def test_refresh_failure_closes_preflight_and_keeps_specific_failed_phase(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(
                native=native, inline_results=[
                    self._inline({"ok": False, "status": "failed", "token_expired": True}),
                    self._inline({"ok": False, "status": "failed", "error": "邮箱验证失败"}),
                ],
            ) as scenario:
                result = self._run(scenario)
                self.assertEqual("failed", result["status"])
                self.assertEqual("failed", self._states(scenario.events, "preflight")[-1])
                self.assertEqual(["running", "failed"], self._states(scenario.events, "refresh_token"))
                scenario.create.assert_not_called()
                snapshot = self._snapshot(scenario, result)
                preflight = next(step for step in snapshot["main_steps"] if step["id"] == "preflight")
                self.assertEqual("failed", preflight["display_status"])
                self.assertIsNotNone(preflight["completed_at"])
                self.assertEqual("refresh_token", snapshot["failure"]["step_id"])

    def test_live_check_network_failure_closes_preflight_without_refresh(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(
                native=native, inline_results=[self._inline({
                    "ok": False, "status": "failed", "http_status": 503, "error": "HTTP 503",
                })],
            ) as scenario:
                result = self._run(scenario)
                self.assertEqual("failed", result["status"])
                self.assertEqual("failed", self._states(scenario.events, "preflight")[-1])
                self.assertEqual([], self._states(scenario.events, "refresh_token"))
                scenario.create.assert_not_called()
                self.assertEqual(1, scenario.inline.call_count)

    def test_cancelled_preflight_or_refresh_does_not_become_failed_or_success(self):
        for native in (True, False):
            for during_refresh in (True, False):
                results = [self._inline({"ok": False, "status": "cancelled", "error": "请求发出前取消"})]
                if during_refresh:
                    results.insert(0, self._inline({"ok": False, "status": "failed", "token_expired": True}))
                with self.subTest(native=native, during_refresh=during_refresh), self._scenario(
                    native=native, inline_results=results,
                ) as scenario:
                    result = self._run(scenario)
                    self.assertEqual("cancelled", result["status"])
                    self.assertFalse(any(event.get("state") in {"failed", "success"} for event in scenario.events))
                    cancelled = [event for event in scenario.events if (event.get("detail") or {}).get("cancelled")]
                    self.assertIn("preflight", [event["stage"] for event in cancelled])
                    if during_refresh:
                        self.assertIn("refresh_token", [event["stage"] for event in cancelled])
                    self.assertEqual("cancelled", scenario.finish.call_args.kwargs["status"])
                    scenario.create.assert_not_called()

    def test_unknown_preflight_or_refresh_keeps_reconciliation_fence(self):
        for native in (True, False):
            for during_refresh in (True, False):
                results = [self._inline({"ok": False, "status": "request_unknown", "manual_reconcile": True})]
                if during_refresh:
                    results.insert(0, self._inline({"ok": False, "status": "failed", "token_expired": True}))
                with self.subTest(native=native, during_refresh=during_refresh), self._scenario(
                    native=native, inline_results=results,
                ) as scenario:
                    result = self._run(scenario)
                    self.assertEqual("request_unknown", result["status"])
                    self.assertTrue(result["manual_reconcile"])
                    self.assertFalse(any(event.get("state") in {"failed", "success"} for event in scenario.events))
                    unresolved = [event for event in scenario.events if (event.get("detail") or {}).get("reconcile_required")]
                    self.assertIn("preflight", [event["stage"] for event in unresolved])
                    if during_refresh:
                        self.assertIn("refresh_token", [event["stage"] for event in unresolved])
                    self.assertEqual("request_unknown", scenario.finish.call_args.kwargs["status"])
                    scenario.create.assert_not_called()

    def test_failure_after_successful_preflight_does_not_close_it_again(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(
                native=native, inline_results=[self._inline({"ok": True, "status": "live"})],
            ) as scenario:
                scenario.create.side_effect = RuntimeError("本地请求配置无效")
                result = self._run(scenario)
                self.assertEqual("failed", result["status"])
                preflight_states = self._states(scenario.events, "preflight")
                self.assertEqual("success", preflight_states[-1])
                self.assertEqual(1, preflight_states.count("success"))
                self.assertNotIn("failed", preflight_states)
                self.assertEqual(["running", "failed"], self._states(scenario.events, "extract_link"))

    def test_local_progress_failure_after_refresh_does_not_overwrite_confirmed_refresh(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(
                native=native, inline_results=[
                    self._inline({"ok": False, "status": "failed", "token_expired": True}),
                    self._inline({"ok": True, "status": "live"}),
                ],
            ) as scenario:
                def write_progress(_account_id, payload):
                    if str(payload.get("message") or "").startswith("AT 刷新成功，已读取数据库新 Token"):
                        raise RuntimeError("模拟刷新成功后的本地进度写入异常")
                    return True

                scenario.database.update_account_extract.side_effect = write_progress
                result = self._run(scenario)
                self.assertEqual("failed", result["status"])
                self.assertEqual(["running", "success"], self._states(scenario.events, "refresh_token"))
                self.assertEqual("failed", self._states(scenario.events, "preflight")[-1])
                scenario.create.assert_not_called()
                snapshot = self._snapshot(scenario, result)
                refreshed = next(step for step in snapshot["main_steps"] if step["id"] == "refresh_token")
                self.assertEqual("success", refreshed["display_status"])
                self.assertEqual("preflight", snapshot["failure"]["step_id"])

    def test_creation_progress_failure_does_not_overwrite_successful_preflight(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(
                native=native, inline_results=[self._inline({"ok": True, "status": "live"})],
            ) as scenario:
                def write_progress(_account_id, payload):
                    if payload.get("message") == "AT 已确认有效，正在创建提链任务":
                        raise RuntimeError("模拟创建前的本地进度写入异常")
                    return True

                scenario.database.update_account_extract.side_effect = write_progress
                result = self._run(scenario)
                self.assertEqual("failed", result["status"])
                self.assertEqual("success", self._states(scenario.events, "preflight")[-1])
                self.assertNotIn("failed", self._states(scenario.events, "preflight"))
                self.assertEqual(["running", "failed"], self._states(scenario.events, "extract_link"))
                scenario.create.assert_not_called()
                snapshot = self._snapshot(scenario, result)
                self.assertEqual("extract_link", snapshot["failure"]["step_id"])


if __name__ == "__main__":
    unittest.main()
