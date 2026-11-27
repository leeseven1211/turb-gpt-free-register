# -*- coding: utf-8 -*-
"""Team 仓储事务、归属和容量的隔离回归。"""
from __future__ import annotations

import importlib
import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from core.storage import postgres, records
from tests.support_pg import PostgresTestCase


class TeamRepositoryTests(PostgresTestCase):
    def setUp(self):
        try:
            spec = importlib.util.find_spec("core.storage.teams.repository")
        except ModuleNotFoundError:
            spec = None
        self.assertIsNotNone(
            spec,
            "Team 仓储尚未实现",
        )
        self.store = importlib.import_module("core.storage.teams.repository")
        self.store.init()
        self.accounts = self.seed(records.ACCOUNTS, [
            {"email": f"person-{index}@example.test", "password": "test-only",
             "created_at": "2026-11-27", "updated_at": "2026-11-27"}
            for index in range(8)
        ])

    def bind(self, index=0, workspace="workspace-a", limit=5):
        probe = self.store.create_probe(manager_account_id=self.accounts[index])
        probe = self.store.update_probe(
            probe["id"], status="success", stage="complete",
            workspaces=[{
                "workspace_id": workspace, "workspace_type": "team", "name": workspace,
                "role": "owner", "can_manage": True,
                "capabilities": {"read_members": True, "read_invitations": True, "invite_members": True},
                "purchased_seats": None,
            }],
        )
        return self.store.bind_team(
            manager_account_id=self.accounts[index], workspace_id=workspace,
            probe_id=probe["id"], probe_revision=probe["revision"],
            planned_member_limit=limit,
        )["team"]

    def joined_snapshot(self, team, *, seats=3, extra_members=None, invitations=None):
        return self.store.apply_sync_snapshot(
            team["id"], workspace_id=team["workspace_id"],
            manager_account_id=team["manager_account_id"], manager_revision=team["manager_revision"],
            members=[{
                "remote_user_id": "owner", "email": "person-0@example.test",
                "account_id": self.accounts[0], "role": "owner", "membership_state": "joined",
            }] + list(extra_members or []),
            invitations=list(invitations or []), purchased_seats=seats,
            members_complete=True, invitations_complete=True,
        )

    def request(self, team, index=2):
        return self.store.create_join_request(
            team["id"], targets=[{"account_id": self.accounts[index],
                                 "email_snapshot": f"person-{index}@example.test"}],
        )

    def accept(self, team, index=2):
        request = self.request(team, index)
        return self.store.accept_join_item(team["id"], request["id"], 0)

    def test_binding_and_first_sync_outbox_commit_together(self):
        team = self.bind()
        self.assertEqual(team["last_sync_status"], "queued")
        self.assertIsNone(team["confirmed_member_count"])
        self.assertIsNone(team["pending_invite_count"])
        jobs = self.store.claim_outbox(kinds=["team_sync"])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["payload"]["team_id"], team["id"])

    def test_binding_rolls_back_when_task_creation_fails(self):
        probe = self.store.create_probe(manager_account_id=self.accounts[0])
        probe = self.store.update_probe(
            probe["id"], status="success",
            workspaces=[{"workspace_id": "atomic", "workspace_type": "team",
                         "can_manage": True, "role": "owner"}],
        )
        def failing_task(conn, kind, payload):
            raise RuntimeError("测试受理失败")
        with self.assertRaisesRegex(RuntimeError, "测试受理失败"):
            self.store.bind_team(
                manager_account_id=self.accounts[0], workspace_id="atomic",
                probe_id=probe["id"], probe_revision=probe["revision"], task_factory=failing_task,
            )
        self.assertEqual(self.store.list_teams()["total"], 0)
        self.assertEqual(self.store.claim_outbox(), [])

    def test_concurrent_cross_team_acceptance_claims_account_once(self):
        first, second = self.bind(), self.bind(1, "workspace-b")
        requests = [self.request(first), self.request(second)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda pair: self.store.accept_join_item(pair[0]["id"], pair[1]["id"], 0),
                [(first, requests[0]), (second, requests[1])],
            ))
        self.assertEqual(sorted(row["acceptance_status"] for row in results), ["accepted", "skipped"])
        skipped = next(row for row in results if row["acceptance_status"] == "skipped")
        self.assertEqual(skipped["reason_code"], "already_in_another_team")
        accepted = next(row for row in results if row["acceptance_status"] == "accepted")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {postgres.qualified('team_account_ownership')} WHERE account_id=%s",
                        (self.accounts[2],))
            self.assertEqual(cur.fetchone()[0], 1)
        self.assertIsNotNone(accepted["invitation_id"])

    def test_unknown_snapshot_accepts_ownership_without_reserving_seat(self):
        team = self.bind()
        item = self.accept(team)
        invitation = self.store.get_invitation(team["id"], item["invitation_id"])
        self.assertEqual(item["acceptance_status"], "accepted")
        self.assertFalse(invitation["seat_reserved"])
        result = self.store.reserve_capacity(team["id"], invitation["id"])
        self.assertFalse(result["reserved"])
        self.assertEqual(result["reason_code"], "waiting_sync")
        self.assertIsNone(result["capacity"]["occupied_count"])

    def test_seat_union_deduplicates_member_invitation_and_local_reservation(self):
        team = self.bind()
        self.joined_snapshot(team, seats=2)
        item = self.accept(team)
        result = self.store.reserve_capacity(team["id"], item["invitation_id"])
        self.assertTrue(result["reserved"])
        self.store.update_invitation(team["id"], item["invitation_id"], changes={"invitation_state": "pending"})
        self.store.apply_sync_snapshot(
            team["id"], workspace_id=team["workspace_id"],
            manager_account_id=team["manager_account_id"], manager_revision=team["manager_revision"],
            members=[{"remote_user_id": "owner", "email": "person-0@example.test", "account_id": self.accounts[0]},
                     {"remote_user_id": "member", "email": "PERSON-2@example.test", "account_id": self.accounts[2]}],
            invitations=[{"remote_invitation_id": "inv-2", "email": "person-2@example.test",
                          "account_id": self.accounts[2], "invitation_state": "pending"}],
            members_complete=True, invitations_complete=True,
        )
        self.assertEqual(self.store.get_capacity(team["id"])["occupied_count"], 2)
        self.assertTrue(self.store.reserve_capacity(team["id"], item["invitation_id"])["reserved"])
        self.assertFalse(self.store.reserve_capacity(team["id"], self.accept(team, 3)["invitation_id"])["reserved"])

    def test_zero_purchased_seats_does_not_fall_back_to_local_limit(self):
        team = self.bind(limit=10)
        self.joined_snapshot(team, seats=0)
        capacity = self.store.get_capacity(team["id"])
        self.assertEqual(capacity["effective_limit"], 0)
        self.assertEqual(capacity["basis"], "purchased_seats")

    def test_incomplete_or_missing_member_snapshot_preserves_joined_history(self):
        team = self.bind()
        self.joined_snapshot(team, extra_members=[{
            "remote_user_id": "member", "email": "person-2@example.test",
            "account_id": self.accounts[2], "membership_state": "joined",
        }])
        self.store.apply_sync_snapshot(
            team["id"], workspace_id=team["workspace_id"],
            manager_account_id=team["manager_account_id"], manager_revision=team["manager_revision"],
            members=[], invitations=[], members_complete=False, invitations_complete=False,
        )
        states = self.store.get_account_states(team["id"], [self.accounts[2]])
        self.assertTrue(states[self.accounts[2]]["already_member"])
        self.assertIsNone(self.store.get_capacity(team["id"])["occupied_count"])
        self.joined_snapshot(team)
        self.assertTrue(self.store.get_account_states(team["id"], [self.accounts[2]])[self.accounts[2]]["already_member"])

    def test_old_manager_receipt_is_saved_without_replacing_current_configuration(self):
        team = self.bind()
        item = self.accept(team)
        execution = self.store.start_invitation_execution(team["id"], item["invitation_id"], task_id=10, run_id=11)
        newer = self.store.patch_team(team["id"], expected_revision=team["revision"], changes={"display_name": "新备注"})
        receipt = self.store.save_execution_receipt(
            team["id"], invitation_id=item["invitation_id"], request_key="remote-request-1",
            workspace_id=team["workspace_id"], manager_account_id=team["manager_account_id"],
            manager_revision=team["manager_revision"], execution_fence=execution["execution_fence"],
            kind="invite", facts={"invitation_state": "pending", "remote_invitation_id": "remote-one"},
        )
        self.assertEqual(receipt["manager_revision"], team["manager_revision"])
        self.assertEqual(self.store.get_team(team["id"])["display_name"], newer["display_name"])
        self.assertEqual(self.store.get_invitation(team["id"], item["invitation_id"])["invitation_state"], "pending")

    def test_global_request_receipt_conflicts_across_paths_and_replays_old_response(self):
        with self.store.transaction() as conn:
            self.assertIsNone(self.store.request_receipt("same-key", path="/one", fingerprint="first", conn=conn))
            self.store.save_request_receipt("same-key", path="/one", fingerprint="first",
                                            response={"saved": True}, status_code=201, conn=conn)
        self.assertEqual(self.store.request_receipt("same-key", path="/one", fingerprint="first")["response_json"],
                         {"saved": True})
        with self.assertRaisesRegex(Exception, "幂等"):
            self.store.request_receipt("same-key", path="/two", fingerprint="first")

    def test_workspace_auth_contexts_do_not_overwrite_another_member(self):
        team = self.bind()
        for index in (2, 3):
            self.store.put_auth_context(team["id"], self.accounts[index], workspace_id=team["workspace_id"],
                                        identity_ref=f"user-{index}", encrypted_context=f"encrypted-{index}")
        self.assertEqual(self.store.get_auth_context(team["id"], self.accounts[2])["encrypted_context"], "encrypted-2")
        self.assertEqual(self.store.get_auth_context(team["id"], self.accounts[3])["encrypted_context"], "encrypted-3")

    def test_outbox_stale_token_cannot_ack_reclaimed_work(self):
        team = self.bind()
        job = self.store.claim_outbox(lease_seconds=60)[0]
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('team_outbox')} SET lease_until=now()-interval '1 second' WHERE id=%s",
                        (job["id"],))
        newer = self.store.claim_outbox()[0]
        self.assertNotEqual(job["lease_token"], newer["lease_token"])
        self.assertFalse(self.store.complete_outbox(job["id"], job["lease_token"]))
        self.assertTrue(self.store.complete_outbox(newer["id"], newer["lease_token"]))

    def test_two_complete_absences_release_terminal_target_without_inventing_revocation(self):
        team = self.bind()
        self.joined_snapshot(team)
        item = self.accept(team)
        self.assertTrue(self.store.reserve_capacity(team["id"], item["invitation_id"])["reserved"])
        self.store.update_invitation(team["id"], item["invitation_id"], changes={
            "invitation_state": "pending", "execution_status": "failed", "active": False,
        })
        self.joined_snapshot(team)
        first = self.store.get_invitation(team["id"], item["invitation_id"])
        self.assertEqual(first["invitation_state"], "pending")
        self.assertTrue(first["seat_reserved"])
        self.joined_snapshot(team)
        second = self.store.get_invitation(team["id"], item["invitation_id"])
        self.assertEqual(second["invitation_state"], "unconfirmed")
        self.assertFalse(second["seat_reserved"])
        self.assertFalse(self.store.get_account_states(team["id"], [self.accounts[2]])[self.accounts[2]]["has_owner"])

    def test_two_complete_absences_do_not_release_active_or_manager_ownership(self):
        team = self.bind()
        self.joined_snapshot(team)
        item = self.accept(team)
        self.assertTrue(self.store.reserve_capacity(team["id"], item["invitation_id"])["reserved"])
        for _ in range(2):
            self.joined_snapshot(team)
        states = self.store.get_account_states(team["id"], [self.accounts[0], self.accounts[2]])
        self.assertTrue(states[self.accounts[0]]["has_owner"])
        self.assertTrue(states[self.accounts[2]]["has_owner"])
        self.assertTrue(self.store.get_invitation(team["id"], item["invitation_id"])["seat_reserved"])

    def test_membership_survives_first_absence_and_leaves_after_second_complete_absence(self):
        team = self.bind()
        self.joined_snapshot(team, extra_members=[{
            "remote_user_id": "member", "email": "person-2@example.test",
            "account_id": self.accounts[2], "membership_state": "joined",
        }])
        self.joined_snapshot(team)
        self.assertTrue(self.store.get_account_states(team["id"], [self.accounts[2]])[self.accounts[2]]["already_member"])
        self.joined_snapshot(team)
        self.assertFalse(self.store.get_account_states(team["id"], [self.accounts[2]])[self.accounts[2]]["already_member"])
        history = self.store.list_members(team["id"], {"membership_state": "left"})
        self.assertEqual(len(history["items"]), 1)

    def test_late_receipt_is_preserved_without_overwriting_newer_verified_invitation(self):
        team = self.bind()
        item = self.accept(team)
        execution = self.store.start_invitation_execution(team["id"], item["invitation_id"], task_id=10, run_id=11)
        requested_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.store.update_invitation(team["id"], item["invitation_id"], changes={
            "invitation_state": "revoked", "last_verified_at": datetime.now(timezone.utc),
        })
        receipt = self.store.save_execution_receipt(
            team["id"], invitation_id=item["invitation_id"], request_key="late-request",
            workspace_id=team["workspace_id"], manager_account_id=team["manager_account_id"],
            manager_revision=team["manager_revision"], execution_fence=execution["execution_fence"],
            kind="invite", facts={"invitation_state": "pending", "observed_at": requested_at.isoformat()},
        )
        self.assertEqual(receipt["facts"]["invitation_state"], "pending")
        self.assertEqual(self.store.get_invitation(team["id"], item["invitation_id"])["invitation_state"], "revoked")

    def test_remote_member_receipt_keeps_joined_when_auth_context_save_fails(self):
        team = self.bind()
        item = self.accept(team)
        execution = self.store.start_invitation_execution(team["id"], item["invitation_id"], task_id=10, run_id=11)
        self.store.save_execution_receipt(
            team["id"], invitation_id=item["invitation_id"], request_key="joined-request",
            workspace_id=team["workspace_id"], manager_account_id=team["manager_account_id"],
            manager_revision=team["manager_revision"], execution_fence=execution["execution_fence"],
            kind="member_verify", facts={"membership_state": "joined", "remote_user_id": "member-two"},
        )
        self.store.update_invitation(team["id"], item["invitation_id"], changes={
            "execution_status": "partial_success", "reason_code": "team_save_failed", "active": False,
        })
        invitation = self.store.get_invitation(team["id"], item["invitation_id"])
        self.assertEqual(invitation["membership_state"], "joined")
        self.assertFalse(invitation["local_saved"])
        member = self.store.list_members(team["id"])["items"][0]
        self.assertEqual(member["execution_status"], "partial_success")

    def test_join_item_tracks_exact_run_without_rewriting_old_request_on_retry(self):
        team = self.bind()
        request = self.request(team)
        item = self.store.accept_join_item(team["id"], request["id"], 0)
        self.store.update_invitation(team["id"], item["invitation_id"], changes={
            "last_task_id": 50, "last_run_id": 51,
        })
        self.store.mark_join_item(team["id"], request["id"], 0, changes={"task_id": 50, "run_id": 51})
        self.store.update_invitation(team["id"], item["invitation_id"], changes={"execution_status": "failed"})
        old = self.store.list_join_items(team["id"], request["id"])["items"][0]
        self.assertEqual(old["execution_status"], "failed")
        self.store.start_invitation_execution(team["id"], item["invitation_id"], task_id=50, run_id=52)
        self.store.update_invitation(team["id"], item["invitation_id"], changes={"execution_status": "success"})
        old = self.store.list_join_items(team["id"], request["id"])["items"][0]
        self.assertEqual(old["run_id"], 51)
        self.assertEqual(old["execution_status"], "failed")

    def test_old_manager_ownership_requires_two_complete_absences_after_switch(self):
        team = self.bind()
        probe = self.store.create_probe(manager_account_id=self.accounts[1])
        probe = self.store.update_probe(probe["id"], status="success", workspaces=[{
            "workspace_id": team["workspace_id"], "workspace_type": "team",
            "can_manage": True, "role": "admin",
        }])
        team = self.store.patch_team(team["id"], expected_revision=team["revision"],
                                     changes={"manager_account_id": self.accounts[1]},
                                     probe_id=probe["id"], probe_revision=probe["revision"])
        for attempt in range(2):
            self.store.apply_sync_snapshot(
                team["id"], workspace_id=team["workspace_id"], manager_account_id=self.accounts[1],
                manager_revision=team["manager_revision"], members=[{
                    "remote_user_id": "new-manager", "account_id": self.accounts[1],
                    "email": "person-1@example.test", "role": "admin",
                }], invitations=[], members_complete=True, invitations_complete=True,
            )
            old_state = self.store.get_account_states(team["id"], [self.accounts[0]])[self.accounts[0]]
            self.assertEqual(old_state["has_owner"], attempt == 0)

    def test_concurrent_capacity_reservation_grants_only_one_net_new_seat(self):
        team = self.bind()
        self.joined_snapshot(team, seats=2)
        items = [self.accept(team, index) for index in (2, 3)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            reservations = list(pool.map(
                lambda item: self.store.reserve_capacity(team["id"], item["invitation_id"]), items))
        self.assertEqual(sum(result["reserved"] for result in reservations), 1)
        self.assertEqual(self.store.get_capacity(team["id"])["occupied_count"], 2)

    def test_changed_supplied_invitation_identity_is_skipped_without_rebinding_target(self):
        team = self.bind()
        accepted = self.accept(team, 2)
        self.store.update_invitation(team["id"], accepted["invitation_id"], changes={
            "execution_status": "failed", "active": False,
        })
        request = self.store.create_join_request(team["id"], operation="retry", targets=[{
            "account_id": self.accounts[3], "email_snapshot": "person-3@example.test",
            "input_invitation_id": accepted["invitation_id"],
        }])
        result = self.store.accept_join_item(team["id"], request["id"], 0)
        self.assertEqual(result["acceptance_status"], "skipped")
        self.assertEqual(result["reason_code"], "account_identity_changed")
        self.assertEqual(result["account_id"], self.accounts[3])

    def test_remote_invitation_matches_unique_local_email_and_blocks_other_team(self):
        first, second = self.bind(), self.bind(1, "workspace-b")
        self.joined_snapshot(first, invitations=[{
            "remote_invitation_id": "external-invite", "email": "PERSON-2@example.test",
            "invitation_state": "pending",
        }])
        item = self.accept(second, 2)
        self.assertEqual(item["acceptance_status"], "skipped")
        self.assertEqual(item["reason_code"], "already_in_another_team")

    def test_member_receipt_updates_known_narrow_counts_without_faking_a_full_sync(self):
        team = self.bind()
        snapshot = self.joined_snapshot(team)
        item = self.accept(team)
        execution = self.store.start_invitation_execution(team["id"], item["invitation_id"], task_id=10, run_id=11)
        self.store.save_execution_receipt(
            team["id"], invitation_id=item["invitation_id"], request_key="known-count",
            workspace_id=team["workspace_id"], manager_account_id=team["manager_account_id"],
            manager_revision=team["manager_revision"], execution_fence=execution["execution_fence"],
            kind="member_verify", facts={"membership_state": "joined", "remote_user_id": "member-two"},
        )
        current = self.store.get_team(team["id"])
        self.assertEqual(current["confirmed_member_count"], 2)
        self.assertEqual(current["last_synced_at"], snapshot["last_synced_at"])

    def test_same_team_external_invitation_is_linked_to_exact_local_account_on_acceptance(self):
        team = self.bind()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {postgres.qualified('team_invitations')}
                (team_id,target_key,email_snapshot,remote_invitation_id,invitation_state)
                VALUES (%s,'external:2','person-2@example.test','external-2','pending')""", (team["id"],))
        item = self.accept(team, 2)
        invitation = self.store.get_invitation(team["id"], item["invitation_id"])
        self.assertEqual(invitation["account_id"], self.accounts[2])

    def test_old_manager_receipt_after_switch_is_applied_when_snapshot_precedes_action(self):
        original = self.bind()
        self.joined_snapshot(original)
        item = self.accept(original)
        execution = self.store.start_invitation_execution(original["id"], item["invitation_id"], task_id=10, run_id=11)
        requested_at = datetime.now(timezone.utc)
        probe = self.store.create_probe(manager_account_id=self.accounts[1])
        probe = self.store.update_probe(probe["id"], status="success", workspaces=[{
            "workspace_id": original["workspace_id"], "workspace_type": "team",
            "can_manage": True, "role": "admin",
        }])
        self.store.patch_team(original["id"], expected_revision=original["revision"],
                              changes={"manager_account_id": self.accounts[1]},
                              probe_id=probe["id"], probe_revision=probe["revision"])
        self.store.save_execution_receipt(
            original["id"], invitation_id=item["invitation_id"], request_key="old-manager-action",
            workspace_id=original["workspace_id"], manager_account_id=original["manager_account_id"],
            manager_revision=original["manager_revision"], execution_fence=execution["execution_fence"],
            kind="invite", facts={"invitation_state": "pending", "observed_at": requested_at.isoformat()},
        )
        self.assertEqual(self.store.get_invitation(original["id"], item["invitation_id"])["invitation_state"], "pending")
        self.assertEqual(self.store.get_team(original["id"])["manager_account_id"], self.accounts[1])

    def test_partial_positive_invitation_evidence_resets_complete_absence_chain(self):
        team = self.bind()
        self.joined_snapshot(team, invitations=[{
            "remote_invitation_id": "repeat-presence", "email": "person-2@example.test",
        }])
        self.joined_snapshot(team)
        self.store.apply_sync_snapshot(
            team["id"], workspace_id=team["workspace_id"], manager_account_id=team["manager_account_id"],
            manager_revision=team["manager_revision"], members=[], invitations=[{
                "remote_invitation_id": "repeat-presence", "email": "person-2@example.test",
                "invitation_state": "pending",
            }], members_complete=False, invitations_complete=False,
        )
        self.joined_snapshot(team)
        invitation = self.store.list_invitations(team["id"])["items"][0]
        self.assertEqual(invitation["invitation_state"], "pending")

    def test_delayed_snapshot_cannot_downgrade_newer_joined_receipt(self):
        team = self.bind()
        self.joined_snapshot(team)
        item = self.accept(team)
        execution = self.store.start_invitation_execution(team["id"], item["invitation_id"], task_id=10, run_id=11)
        snapshot_at = datetime.now(timezone.utc)
        verified_at = snapshot_at + timedelta(seconds=1)
        self.store.save_execution_receipt(
            team["id"], invitation_id=item["invitation_id"], request_key="newer-member",
            workspace_id=team["workspace_id"], manager_account_id=team["manager_account_id"],
            manager_revision=team["manager_revision"], execution_fence=execution["execution_fence"],
            kind="member_verify", facts={
                "membership_state": "joined", "invitation_state": "accepted",
                "remote_user_id": "person-2", "last_verified_at": verified_at.isoformat(),
            },
        )
        self.store.apply_sync_snapshot(
            team["id"], workspace_id=team["workspace_id"], manager_account_id=team["manager_account_id"],
            manager_revision=team["manager_revision"], members=[], invitations=[{
                "remote_invitation_id": "old-invite", "email": "person-2@example.test", "invitation_state": "pending",
            }], members_complete=True, invitations_complete=True, observed_at=snapshot_at,
        )
        invitation = self.store.get_invitation(team["id"], item["invitation_id"])
        self.assertEqual(invitation["invitation_state"], "accepted")
        self.assertEqual(invitation["last_verified_at"], verified_at)

    def test_member_receipt_without_remote_user_id_reuses_existing_identity(self):
        team = self.bind()
        self.joined_snapshot(team, extra_members=[{
            "remote_user_id": "known-user", "account_id": self.accounts[2], "email": "person-2@example.test",
        }])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {postgres.qualified('team_invitations')}
              (team_id,target_key,account_id,email_snapshot,execution_fence)
              VALUES (%s,'account:2',%s,'person-2@example.test',1) RETURNING id""",
                        (team["id"], self.accounts[2]))
            invitation_id = cur.fetchone()[0]
        self.store.save_execution_receipt(
            team["id"], invitation_id=invitation_id, request_key="no-user-id",
            workspace_id=team["workspace_id"], manager_account_id=team["manager_account_id"],
            manager_revision=team["manager_revision"], execution_fence=1,
            kind="member_verify", facts={"membership_state": "joined"},
        )
        members = self.store.list_members(team["id"])["items"]
        self.assertEqual(len(members), 2)

    def test_retry_request_copies_fixed_targets_in_sql_without_rewriting_old_receipt(self):
        team = self.bind()
        original = self.store.create_join_request(team["id"], targets=[
            {"account_id": self.accounts[2], "email_snapshot": "person-2@example.test"},
            {"account_id": self.accounts[3], "email_snapshot": "person-3@example.test"},
            {"account_id": self.accounts[2], "email_snapshot": "person-2@example.test"},
        ])
        self.store.accept_join_item(team["id"], original["id"], 0)
        copied = self.store.create_retry_join_request(team["id"], original["id"])
        self.assertEqual(copied["operation"], "retry")
        self.assertEqual(copied["counts"]["requested_count"], 3)
        self.assertEqual(copied["counts"]["unique_count"], 2)
        self.assertEqual(copied["counts"]["pending_count"], 2)
        self.assertNotEqual(copied["id"], original["id"])
        before = self.store.list_join_items(team["id"], original["id"])["items"]
        after = self.store.list_join_items(team["id"], copied["id"])["items"]
        self.assertEqual([row["email_snapshot"] for row in before], [row["email_snapshot"] for row in after])
        self.assertEqual(before[0]["acceptance_status"], "accepted")
        self.assertEqual(after[0]["acceptance_status"], "pending")

    def test_continue_external_invitation_uses_frozen_unique_local_identity(self):
        team = self.bind()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {postgres.qualified('team_invitations')}
                (team_id,target_key,email_snapshot,invitation_state)
                VALUES (%s,'external-continue','person-2@example.test','pending') RETURNING id""",
                        (team["id"],))
            invitation_id = cur.fetchone()[0]
        row = self.store.get_invitation(team["id"], invitation_id)
        request = self.store.create_join_request(team["id"], operation="continue", targets=[{
            "account_id": row["account_id"], "email_snapshot": row["email_snapshot"],
            "input_invitation_id": row["id"],
        }])
        item = self.store.accept_join_item(team["id"], request["id"], 0)
        self.assertEqual(item["acceptance_status"], "accepted")
        self.assertEqual(self.store.get_invitation(team["id"], invitation_id)["account_id"], self.accounts[2])

    def test_execution_receipt_key_cannot_change_original_manager_or_fence(self):
        team = self.bind()
        item = self.accept(team)
        facts = dict(invitation_state="pending")
        arguments = dict(
            invitation_id=item["invitation_id"], request_key="immutable-remote-request",
            workspace_id=team["workspace_id"], manager_account_id=team["manager_account_id"],
            manager_revision=team["manager_revision"], execution_fence=0, kind="invite", facts=facts,
        )
        self.store.save_execution_receipt(team["id"], **arguments)
        with self.assertRaisesRegex(Exception, "回执键冲突"):
            self.store.save_execution_receipt(team["id"], **{**arguments, "execution_fence": 1})

    def test_first_outbox_execution_reference_attaches_unassigned_acceptance_receipts(self):
        team = self.bind()
        request = self.request(team)
        item = self.store.accept_join_item(team["id"], request["id"], 0)
        self.assertIsNone(item["run_id"])
        self.store.update_invitation(team["id"], item["invitation_id"], changes={
            "last_task_id": 10, "last_run_id": 11, "execution_status": "queued",
        })
        attached = self.store.list_join_items(team["id"], request["id"])["items"][0]
        self.assertEqual(attached["task_id"], 10)
        self.assertEqual(attached["run_id"], 11)
        self.store.update_invitation(team["id"], item["invitation_id"], changes={"execution_status": "success"})
        self.assertEqual(self.store.summarize_join_execution(team["id"], request["id"])["success_count"], 1)

    def test_capacity_reads_only_team_identity_emails_instead_of_grouping_all_accounts(self):
        from core.storage.teams.joins import _occupancy_sql
        team = self.bind()
        self.joined_snapshot(team, invitations=[{
            "remote_invitation_id": "outside-only", "email": "outside@example.test", "invitation_state": "pending",
        }])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"INSERT INTO {postgres.qualified('registered_accounts')}(email,created_at,updated_at) "
                        "SELECT 'capacity-'||n||'@example.test','2026-11-27','2026-11-27' "
                        "FROM generate_series(1,10000) n")
            cur.execute(f"ANALYZE {postgres.qualified('registered_accounts')}")
            cur.execute("EXPLAIN (ANALYZE,FORMAT JSON) " + _occupancy_sql(), (team["id"], team["id"]))
            plan = cur.fetchone()[0][0]["Plan"]
        def account_rows(node):
            return (node.get("Actual Rows", 0) * node.get("Actual Loops", 1)
                    if node.get("Relation Name") == "registered_accounts" else 0) + sum(
                        account_rows(child) for child in node.get("Plans", []))
        self.assertLess(account_rows(plan), 10, "容量计算扫描了不属于当前Team的账号")

    def test_selection_consumption_respects_independent_operation_schema(self):
        from tests.support_pg import drop_schema
        team = self.bind()
        operation_schema = self.schema + "_ops"
        self.addCleanup(drop_schema, operation_schema)
        qualified = postgres.quote_identifier(operation_schema) + '."operation_selections"'
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {postgres.quote_identifier(operation_schema)}")
            cur.execute(f"CREATE TABLE {qualified}(id BIGINT PRIMARY KEY,status TEXT,updated_at TIMESTAMPTZ)")
            cur.execute(f"INSERT INTO {qualified}(id,status) VALUES (1,'ready')")
        with patch.dict(os.environ, {"OPERATION_TASK_DB_SCHEMA": operation_schema}):
            request = self.store.create_join_request(team["id"], targets=[{
                "account_id": self.accounts[2], "email_snapshot": "person-2@example.test",
            }], selection_id=1, selection_revision=1)
        self.assertEqual(request["selection_id"], 1)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT status FROM {qualified} WHERE id=1")
            self.assertEqual(cur.fetchone()[0], "consumed")

    def test_capacity_reuses_current_transaction_team_snapshot_without_reloading(self):
        team = self.bind()
        self.joined_snapshot(team, seats=3)
        original_one = self.store._one
        queries = []
        def observed_one(conn, sql, values=()):
            queries.append(sql)
            return original_one(conn, sql, values)
        with self.store.transaction() as conn:
            current = self.store.get_team(team["id"], conn=conn)
            with patch.object(self.store, "_one", side_effect=observed_one):
                result = self.store.get_capacity(team["id"], team=current, conn=conn)
        self.assertEqual(result["occupied_count"], 1)
        self.assertEqual(result["available_count"], 2)
        self.assertEqual(len(queries), 1, "已读取Team后只需一次容量事实查询")

    def test_capacity_rejects_another_team_snapshot(self):
        team, other = self.bind(), self.bind(1, "workspace-b")
        with self.assertRaisesRegex(ValueError, "Team.*不符"):
            self.store.get_capacity(team["id"], team=other)

    def test_acceptance_uses_captured_operation_schema_for_parent_cancellation(self):
        from core.operations.runtime import OperationCancelled
        from core.storage.operations import common
        from tests.support_pg import drop_schema

        team = self.bind()
        request = self.request(team)
        operation_schema = self.schema + "_ops"
        self.addCleanup(drop_schema, operation_schema)
        prefix = postgres.quote_identifier(operation_schema)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {prefix}")
            cur.execute(f"CREATE TABLE {prefix}.operation_tasks "
                        "(id BIGINT PRIMARY KEY,parent_task_id BIGINT,last_run_id BIGINT)")
            cur.execute(f"CREATE TABLE {prefix}.operation_runs "
                        "(id BIGINT PRIMARY KEY,status TEXT,cancel_requested_at TIMESTAMPTZ)")
            cur.execute(f"INSERT INTO {prefix}.operation_tasks VALUES(101,NULL,201)")
            cur.execute(f"INSERT INTO {prefix}.operation_runs VALUES(201,'cancelled',now())")
        self.store.update_join_request(team["id"], request["id"], changes={"task_id": 101, "run_id": 201})
        captured = SimpleNamespace(operation_schema=operation_schema)
        token = common._SETTLEMENT_DOMAIN.set(captured)
        try:
            with patch.dict(os.environ, {"OPERATION_TASK_DB_SCHEMA": self.schema + "_wrong"}):
                with self.assertRaises(OperationCancelled):
                    self.store.accept_join_item(team["id"], request["id"], 0)
        finally:
            common._SETTLEMENT_DOMAIN.reset(token)
        item = self.store.list_join_items(team["id"], request["id"])["items"][0]
        self.assertEqual(item["acceptance_status"], "pending")
        self.assertFalse(self.store.get_account_states(team["id"], [self.accounts[2]])[self.accounts[2]]["has_owner"])

    def test_joined_intent_occupies_seat_when_member_row_is_temporarily_missing(self):
        team = self.bind()
        self.joined_snapshot(team, seats=2)
        joined = self.accept(team, 2)
        self.store.update_invitation(team["id"], joined["invitation_id"], changes={
            "invitation_state": "accepted", "membership_state": "joined",
            "seat_reserved": False, "active": False, "execution_status": "success",
        })
        capacity = self.store.get_capacity(team["id"])
        self.assertEqual(capacity["occupied_count"], 2)
        self.assertEqual(capacity["available_count"], 0)
        next_item = self.accept(team, 3)
        reservation = self.store.reserve_capacity(team["id"], next_item["invitation_id"])
        self.assertFalse(reservation["reserved"])
        self.assertEqual(reservation["reason_code"], "waiting_capacity")
