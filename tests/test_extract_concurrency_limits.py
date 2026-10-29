"""提链并发的配置与调度边界。"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core import extract_link_service


class ExtractConcurrencyLimitTests(unittest.TestCase):
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
