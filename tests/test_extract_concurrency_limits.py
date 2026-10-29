"""提链并发的配置与调度边界。"""
from __future__ import annotations

import unittest
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import patch

from core import extract_link_service


class ExtractConcurrencyLimitTests(unittest.TestCase):
    def test_extract_pool_capacity_tracks_platform_limits_not_account_workers(self):
        from core.account_operation_executor import configured_extract_workers

        with (
            patch("config.codex.ACCOUNT_BATCH_WORKERS", 1),
            patch.object(extract_link_service, "_provider_dispatch_capacity_limit",
                         side_effect=lambda provider: {"legacy": 4, "lumen_flow": 7, "huanguang": 11}[provider]),
        ):
            self.assertEqual(22, configured_extract_workers())

    def test_dispatch_pools_do_not_block_each_other(self):
        from core.operations import task_gateway

        class Pool:
            def __init__(self, slots):
                self.slots = slots
                self.submitted = []

            def available_slots(self):
                return self.slots

            def try_submit(self, handler, run_id):
                if not self.slots:
                    return None
                self.slots -= 1
                self.submitted.append(run_id)
                return Future()

        runs = [
            {"id": 1, "task_type": "extract_link", "source_system": "native_operations"},
            {"id": 2, "task_type": "plan_check", "source_system": "native_operations"},
        ]
        def list_runs(*, task_types, limit, **kwargs):
            return [run for run in runs if run["task_type"] in task_types][:limit]

        for account_slots, extract_slots, expected in ((0, 1, [1]), (1, 0, [2]), (1, 1, [1, 2])):
            with self.subTest(account_slots=account_slots, extract_slots=extract_slots):
                account_pool, extract_pool = Pool(account_slots), Pool(extract_slots)
                handlers = {name: (lambda run_id: None, ("native_operations",))
                            for name in ("extract_link", "plan_check")}
                with (
                    patch.object(task_gateway, "_executor", return_value=account_pool),
                    patch.object(task_gateway, "_extract_executor", return_value=extract_pool, create=True),
                    patch.object(task_gateway, "_operation", return_value=SimpleNamespace(list_dispatchable_runs=list_runs)),
                    patch.dict(task_gateway._DISPATCH_HANDLERS, handlers, clear=True),
                    patch.dict(task_gateway._DISPATCH_CAPACITY_HANDLERS, {}, clear=True),
                    patch.object(task_gateway, "_RUN_DISPATCHED", set()),
                ):
                    self.assertEqual(len(expected), task_gateway.dispatch_registered_once(limit=1))
                    self.assertEqual(set(expected), set(account_pool.submitted + extract_pool.submitted))

    def test_batch_default_accepts_fifty_and_clamps_larger_values(self):
        for configured in (20, 50, 51):
            with (
                self.subTest(configured=configured),
                patch.object(extract_link_service, "_bool_setting", return_value=False),
                patch.object(extract_link_service, "_runtime_setting", side_effect=lambda key, default=None: (
                    configured if key == "EXTRACT_LINK_BATCH_WORKERS" else default
                )),
            ):
                result = extract_link_service.workbench_config()
                self.assertEqual(min(configured, 50), result["batch_workers_default"])
                self.assertEqual(50, result["batch_workers_max"])

    def test_all_providers_keep_fifty_batch_slots_and_platform_limit(self):
        for provider in ("legacy", "lumen_flow", "huanguang"):
            for platform_limit in (20, 50, 51):
                with (
                    self.subTest(provider=provider, platform_limit=platform_limit),
                    patch.object(extract_link_service, "_runtime_setting", return_value=platform_limit),
                ):
                    capacity = extract_link_service._provider_dispatch_capacity_key({
                        "batch_id": 7, "batch_workers": 50, "data": {"provider_id": provider},
                    })
                    self.assertEqual({provider: min(platform_limit, 50), "batch:7": 50}, capacity)
