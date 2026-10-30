# -*- coding: utf-8 -*-
"""验证封号邮件扫描阶段收口与真实调用边界一致，不访问账号或邮箱。"""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.accounts.deactivation import mail_scan as service
from core.operations import run_log as task_run_log
from core.operations.runtime import OperationCancelled
from core.operations.progress import build_progress_snapshot


class DeactivationMailReportingTests(unittest.TestCase):
    def tearDown(self):
        task_run_log.clear_current_context()

    @contextmanager
    def _scenario(self, *, native=True, source="email_butler"):
        events, execution = [], []

        def report(*_args, **event):
            events.append(dict(event))
            execution.append((event.get("stage"), event.get("state")))
            return {"event_id": len(events)}

        def finish(*_args, **result):
            execution.append(("finished", result["status"]))

        context = SimpleNamespace(
            report=Mock(side_effect=report), finish=Mock(side_effect=finish),
            checkpoint=Mock(), is_cancel_requested=Mock(return_value=False),
        )
        database = Mock()
        database.get_account.return_value = {
            "id": 7, "email": "fixture@example.test", "email_source": source,
        }
        result = {"ok": True, "detected": False, "checked_at": "2026-10-09T08:00:00Z"}

        def scan(*_args, **_kwargs):
            execution.append(("mailbox_call", None))
            return result

        def scan_bulk(emails, **_kwargs):
            execution.append(("mailbox_call", None))
            return {email: dict(result) for email in emails}

        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "db", database))
            stack.enter_context(patch.object(service, "logger"))
            stack.enter_context(patch.object(service.account_task_store, "start_task"))
            stack.enter_context(patch.object(service.account_task_store, "append_event", side_effect=report))
            legacy_finish = stack.enter_context(patch.object(service.account_task_store, "finish_task", side_effect=finish))
            scans = {
                "email_butler": stack.enter_context(patch.object(service, "scan_openai_deactivation", side_effect=scan)),
                "cloudflare": stack.enter_context(patch.object(service, "scan_cloudflare_deactivation", side_effect=scan)),
                "icloud_hide": stack.enter_context(patch.object(service, "scan_hme_deactivation_bulk", side_effect=scan_bulk)),
            }
            yield SimpleNamespace(
                context=context, operation_context=context if native else None,
                events=events, execution=execution, database=database, scans=scans,
                finish=context.finish if native else legacy_finish,
            )

    @staticmethod
    def _states(scenario):
        return [(event["stage"], event["state"]) for event in scenario.events if event.get("state")]

    @staticmethod
    def _run(scenario):
        service._scan(7, "manual", task_id=901, operation_context=scenario.operation_context)

    def _assert_no_scan(self, scenario):
        for client in scenario.scans.values():
            client.assert_not_called()
        self.assertNotIn(("preflight", "success"), self._states(scenario))
        self.assertFalse(any(stage == "mailbox_scan" for stage, _state in self._states(scenario)))

    def test_single_scan_closes_preflight_before_provider_for_native_and_legacy(self):
        for native in (True, False):
            for source in ("email_butler", "cloudflare", "icloud_hide"):
                with self.subTest(native=native, source=source), self._scenario(native=native, source=source) as scenario:
                    self._run(scenario)
                    self.assertEqual([
                        ("preflight", "running"), ("preflight", "success"),
                        ("mailbox_scan", "running"), ("mailbox_scan", "success"),
                    ], self._states(scenario))
                    self.assertLess(
                        scenario.execution.index(("preflight", "success")),
                        scenario.execution.index(("mailbox_call", None)),
                    )
                    self.assertEqual("success", scenario.finish.call_args.kwargs["status"])

    def test_invalid_single_mailbox_only_fails_preflight(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(native=native) as scenario:
                scenario.database.get_account.return_value["email"] = ""
                self._run(scenario)
                self._assert_no_scan(scenario)
                self.assertEqual([("preflight", "running"), ("preflight", "failed")], self._states(scenario))
                self.assertEqual("failed", scenario.finish.call_args.kwargs["status"])

    def test_database_preflight_exception_does_not_fabricate_scan_failure(self):
        with self._scenario() as scenario:
            scenario.database.get_account.side_effect = RuntimeError("模拟读取失败")
            self._run(scenario)
            self._assert_no_scan(scenario)
            self.assertEqual([("preflight", "running"), ("preflight", "failed")], self._states(scenario))

    def test_unsupported_source_skips_preflight_without_provider_call(self):
        with self._scenario(source="outlook") as scenario:
            self._run(scenario)
            self._assert_no_scan(scenario)
            self.assertEqual([("preflight", "running"), ("preflight", "skipped")], self._states(scenario))
            self.assertEqual("unsupported", scenario.finish.call_args.kwargs["status"])

    def test_deleted_account_cancels_without_failed_stage(self):
        with self._scenario() as scenario:
            scenario.database.get_account.return_value = None
            self._run(scenario)
            self._assert_no_scan(scenario)
            self.assertEqual([("preflight", "running")], self._states(scenario))
            self.assertEqual("cancelled", scenario.finish.call_args.kwargs["status"])

    def test_single_provider_failure_keeps_completed_preflight(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(native=native) as scenario:
                scenario.scans["email_butler"].side_effect = service.EmailButlerClientError("模拟邮箱服务失败")
                self._run(scenario)
                self.assertEqual([
                    ("preflight", "running"), ("preflight", "success"),
                    ("mailbox_scan", "running"), ("mailbox_scan", "failed"),
                ], self._states(scenario))
                self.assertEqual("failed", scenario.finish.call_args.kwargs["status"])

    def test_cancellation_during_single_preflight_does_not_turn_green_or_fail(self):
        with self._scenario() as scenario:
            scenario.context.checkpoint.side_effect = [None, OperationCancelled("模拟预检取消")]
            self._run(scenario)
            self._assert_no_scan(scenario)
            self.assertEqual([("preflight", "running")], self._states(scenario))
            self.assertEqual("cancelled", scenario.finish.call_args.kwargs["status"])

    def test_cancellation_after_single_provider_does_not_report_scan_success(self):
        with self._scenario() as scenario:
            scenario.context.checkpoint.side_effect = [None, None, None, OperationCancelled("模拟扫描取消")]
            self._run(scenario)
            self.assertEqual([
                ("preflight", "running"), ("preflight", "success"), ("mailbox_scan", "running"),
            ], self._states(scenario))
            scenario.scans["email_butler"].assert_called_once()
            self.assertEqual("cancelled", scenario.finish.call_args.kwargs["status"])

    def test_lost_lease_after_single_provider_preserves_unknown_boundary(self):
        with self._scenario() as scenario:
            scenario.context.checkpoint.side_effect = [None, None, None, service.account_task_store.OperationLeaseLost("模拟租约丢失")]
            with self.assertRaises(service.account_task_store.OperationLeaseLost):
                self._run(scenario)
            self.assertEqual([
                ("preflight", "running"), ("preflight", "success"), ("mailbox_scan", "running"),
            ], self._states(scenario))
            scenario.finish.assert_not_called()

    @staticmethod
    def _group(scenario, entries=None):
        service._scan_hme_group(scenario.context, entries if entries is not None else [
            {"account_id": 7, "email": "first@example.test"},
            {"account_id": 8, "email": "second@example.test"},
        ], "manual_bulk")

    def test_hme_group_closes_preflight_before_shared_mailbox_and_aggregate_end(self):
        with self._scenario(source="icloud_hide") as scenario:
            self._group(scenario)
            states = self._states(scenario)
            self.assertEqual([("preflight", "running"), ("preflight", "success"), ("mailbox_scan", "running")], states[:3])
            self.assertEqual(("mailbox_scan", "success"), states[-1])
            self.assertLess(scenario.execution.index(("preflight", "success")), scenario.execution.index(("mailbox_call", None)))
            scenario.scans["icloud_hide"].assert_called_once()
            self.assertEqual(2, scenario.finish.call_args.kwargs["result_summary"]["success_count"])

    def test_hme_invalid_targets_only_fail_preflight(self):
        with self._scenario(source="icloud_hide") as scenario:
            self._group(scenario, [{"account_id": 7, "email": "invalid"}])
            self._assert_no_scan(scenario)
            self.assertEqual([("preflight", "running"), ("preflight", "failed")], self._states(scenario))

    def test_hme_running_projection_failure_is_a_preflight_failure(self):
        with self._scenario(source="icloud_hide") as scenario:
            scenario.database.update_account_deactivation_mail.side_effect = [RuntimeError("模拟投影写入失败"), None, None]
            self._group(scenario)
            self._assert_no_scan(scenario)
            self.assertEqual([("preflight", "running"), ("preflight", "failed")], self._states(scenario))

    def test_hme_partial_failure_has_failed_aggregate_after_last_success(self):
        with self._scenario(source="icloud_hide") as scenario:
            scenario.scans["icloud_hide"].side_effect = None
            scenario.scans["icloud_hide"].return_value = {
                "first@example.test": {"ok": False, "error": "模拟单别名失败"},
                "second@example.test": {"ok": True, "detected": False},
            }
            self._group(scenario)
            self.assertEqual(("mailbox_scan", "failed"), self._states(scenario)[-1])
            self.assertEqual("failed", scenario.finish.call_args.kwargs["status"])
            events = [
                {**event, "id": index, "event_type": f"stage.{event['state']}"}
                for index, event in enumerate(scenario.events, 1) if event.get("state")
            ]
            progress = build_progress_snapshot(901, 902, "deactivation_mail", {"status": "failed"}, events)
            self.assertEqual("failed", next(step for step in progress["main_steps"] if step["id"] == "mailbox_scan")["state"])

    def test_hme_provider_exception_closes_actual_scan_stage(self):
        with self._scenario(source="icloud_hide") as scenario:
            scenario.scans["icloud_hide"].side_effect = service.ForwardIMAPError("模拟共享邮箱失败")
            self._group(scenario)
            self.assertEqual(("mailbox_scan", "failed"), self._states(scenario)[-1])
            self.assertIn(("preflight", "success"), self._states(scenario))
            self.assertEqual("failed", scenario.finish.call_args.kwargs["status"])

    def test_hme_cancellation_before_scan_does_not_fabricate_account_stage_failure(self):
        with self._scenario(source="icloud_hide") as scenario:
            scenario.context.checkpoint.side_effect = [None, OperationCancelled("模拟批量预检取消")]
            self._group(scenario)
            self._assert_no_scan(scenario)
            self.assertEqual([("preflight", "running")], self._states(scenario))
            self.assertEqual(2, scenario.finish.call_args.kwargs["result_summary"]["cancelled_count"])
            self.assertFalse(any(event.get("state") == "failed" for event in scenario.events))

    def test_hme_already_cancelled_targets_are_closed_without_provider_call(self):
        with self._scenario(source="icloud_hide") as scenario:
            scenario.context.checkpoint.side_effect = OperationCancelled("模拟批量取消")
            self._group(scenario)
            self._assert_no_scan(scenario)
            cancelled_updates = [
                call.args[0] for call in scenario.database.update_account_deactivation_mail.call_args_list
                if call.args[1].get("status") == "cancelled"
            ]
            self.assertEqual([7, 8], cancelled_updates)
            self.assertEqual("cancelled", scenario.finish.call_args.kwargs["status"])

    def test_hme_cancellation_after_provider_preserves_uncancelled_preflight(self):
        with self._scenario(source="icloud_hide") as scenario:
            scenario.context.checkpoint.side_effect = [None, None, None, OperationCancelled("模拟批量扫描取消")]
            self._group(scenario)
            self.assertEqual([
                ("preflight", "running"), ("preflight", "success"), ("mailbox_scan", "running"),
            ], self._states(scenario))
            self.assertEqual("cancelled", scenario.finish.call_args.kwargs["status"])

    def test_hme_cancellation_after_first_alias_keeps_main_scan_unfinished(self):
        with self._scenario(source="icloud_hide") as scenario:
            scenario.context.checkpoint.side_effect = [None] * 5 + [OperationCancelled("模拟第二个别名写回前取消")]
            self._group(scenario)
            self.assertEqual([
                ("preflight", "running"), ("preflight", "success"), ("mailbox_scan", "running"),
            ], self._states(scenario))
            self.assertEqual("cancelled", scenario.finish.call_args.kwargs["status"])
            self.assertEqual(1, scenario.finish.call_args.kwargs["result_summary"]["completed_count"])
            account_events = [event for event in scenario.events if event.get("detail", {}).get("account_id")]
            self.assertEqual([(7, "success"), (8, "cancelled")], [
                (event["detail"]["account_id"], event["detail"]["result_status"]) for event in account_events
            ])
            self.assertTrue(all(event["event_type"].startswith("note.") for event in account_events))
            events = [{
                **event, "id": index,
                "event_type": event.get("event_type") or f"stage.{event['state']}",
            } for index, event in enumerate(scenario.events, 1)]
            progress = build_progress_snapshot(901, 902, "deactivation_mail", {"status": "cancelled"}, events)
            scan = next(step for step in progress["main_steps"] if step["id"] == "mailbox_scan")
            self.assertNotEqual("success", scan["state"])
            self.assertNotEqual("failed", scan["state"])
            self.assertIsNone(scan["completed_at"])

    def test_hme_lost_lease_does_not_finish_or_fabricate_account_failure(self):
        with self._scenario(source="icloud_hide") as scenario:
            scenario.context.checkpoint.side_effect = [None, None, None, service.account_task_store.OperationLeaseLost("模拟租约丢失")]
            with self.assertRaises(service.account_task_store.OperationLeaseLost):
                self._group(scenario)
            self.assertEqual([
                ("preflight", "running"), ("preflight", "success"), ("mailbox_scan", "running"),
            ], self._states(scenario))
            scenario.finish.assert_not_called()
