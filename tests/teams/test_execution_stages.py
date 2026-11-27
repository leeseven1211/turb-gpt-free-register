"""Team 执行事件与任务中心业务阶段的映射测试。"""
from __future__ import annotations

import unittest

from core.operations import stages


class TeamExecutionStageTests(unittest.TestCase):
    def test_team_events_resolve_to_their_own_business_steps(self):
        flows = {
            "team_probe": ("manager_auth", "workspace_discovery", "permission_check"),
            "team_sync": ("manager_verify", "state_check", "persist"),
            "team_reverify": ("manager_verify", "persist"),
            "team_join_request": ("state_check", "dispatch"),
            "team_join": (
                "manager_verify", "state_check", "invite", "member_auth",
                "accept", "member_verify", "persist",
            ),
            "team_invite": ("manager_verify", "state_check", "invite", "persist"),
            "team_accept": ("member_auth", "accept", "member_verify", "persist"),
            "team_outbox_drain": ("dispatch",),
        }
        for task_type, raw_stages in flows.items():
            for raw_stage in raw_stages:
                with self.subTest(task_type=task_type, stage=raw_stage):
                    step = stages.step_for_raw_stage(task_type, raw_stage)
                    self.assertIsNotNone(step)
                    self.assertEqual(raw_stage, step["id"])
                    self.assertEqual(raw_stage, stages.resolve_step(task_type, raw_stage))
            self.assertEqual("result", stages.resolve_step(task_type, "complete"))

    def test_team_specific_steps_have_chinese_labels_and_team_group(self):
        for stage in (
            "manager_auth", "workspace_discovery", "permission_check",
            "manager_verify", "state_check", "invite", "member_auth",
            "accept", "member_verify", "persist",
        ):
            with self.subTest(stage=stage):
                self.assertNotEqual(stage, stages.stage_label(stage))
                step = stages.step_for_raw_stage("team_probe" if stage in {
                    "manager_auth", "workspace_discovery", "permission_check",
                } else "team_join", stage)
                self.assertIsNotNone(step)
                self.assertEqual("team", step["group"])


if __name__ == "__main__":
    unittest.main()
