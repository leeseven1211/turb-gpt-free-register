# -*- coding: utf-8 -*-
"""Team 加入预检的单行 SQL 聚合与纯规则对照。"""
from __future__ import annotations

import importlib
import importlib.util
from contextlib import contextmanager
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from core.storage import postgres, records
from core.storage.teams import reads, repository, schema
from core.teams import domain
from core.teams.errors import TeamError
from tests.support_pg import PostgresTestCase


def _module():
    if importlib.util.find_spec("core.storage.teams.preview") is None:
        raise AssertionError("Team 单行预检聚合尚未实现")
    return importlib.import_module("core.storage.teams.preview")


class TeamPreviewLegacyTests(PostgresTestCase):
    def test_missing_tables_are_classified_without_initializing_schema(self):
        preview = _module()
        with postgres.connect(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
            with self.assertRaises(TeamError) as raised:
                preview.summary(1, ["2"], conn=conn)
        self.assertEqual(raised.exception.code, "team_store_unavailable")
        self.assertEqual(raised.exception.status, 503)
        self.assertTrue(raised.exception.retryable)

    def test_snapshot_missing_tables_are_classified_without_initializing_schema(self):
        preview = _module()
        self.assertTrue(callable(getattr(preview, "snapshot", None)), "Team 预检快照尚未实现")
        with postgres.connect(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
            with self.assertRaises(TeamError) as raised:
                preview.snapshot(1, ["2"], conn=conn)
        self.assertEqual(raised.exception.code, "team_store_unavailable")
        self.assertEqual(raised.exception.status, 503)
        self.assertTrue(raised.exception.retryable)


class TeamPreviewQueryTests(PostgresTestCase):
    def setUp(self):
        self.preview = _module()
        schema.reset_ready()
        schema.init()
        with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {postgres.qualified(records.ACCOUNTS.name)}
                    (email,created_at,updated_at,data)
                    SELECT 'preview-'||n||'@example.test','2026-11-27','2026-11-27',
                           '{{"access_token":"合成认证投影"}}'::jsonb
                    FROM generate_series(0,23) n ORDER BY n RETURNING id"""
            )
            self.accounts = [row["id"] for row in cur.fetchall()]
        self.team = self.insert("team_workspaces", {
            "workspace_id": "preview-team", "manager_account_id": self.accounts[0],
            "role": "owner",
        })
        self.other = self.insert("team_workspaces", {
            "workspace_id": "preview-other", "manager_account_id": self.accounts[1],
            "role": "owner",
        })

    def insert(self, table, values):
        returning = "account_id" if table == "team_account_ownership" else "id"
        with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING {}").format(
                    sql.Identifier(self.schema, table),
                    sql.SQL(",").join(map(sql.Identifier, values)),
                    sql.SQL(",").join(sql.Placeholder() for _ in values),
                    sql.Identifier(returning),
                ),
                list(values.values()),
            )
            return cur.fetchone()[returning]

    def invitation(self, index, *, team=None, key=None, linked=True, **values):
        return self.insert("team_invitations", {
            "team_id": team or self.team, "target_key": key or f"account:{self.accounts[index]}",
            "account_id": self.accounts[index] if linked else None,
            "email_snapshot": f" PREVIEW-{index}@example.test ", **values,
        })

    def member(self, index, *, team=None, linked=True, **values):
        return self.insert("team_members", {
            "team_id": team or self.team, "identity_key": f"member:{index}",
            "account_id": self.accounts[index] if linked else None,
            "email": f" PREVIEW-{index}@example.test ", "membership_state": "joined", **values,
        })

    def update_account(self, index, **values):
        records.patch_row(records.ACCOUNTS, self.accounts[index], values)

    @contextmanager
    def read_only(self):
        with postgres.connect(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
            yield conn

    def assert_matches_domain(self, ids, expected=None):
        with self.read_only() as conn:
            result = self.preview.summary(self.team, ids, expected, conn=conn)
            states = reads.get_account_states(self.team, ids, conn=conn)
        known = domain.preview(ids, states, {"occupied_count": 0}, expected)
        self.assertEqual(result["counts"], known["counts"])
        self.assertEqual(result["additional_required"], known["capacity"]["additional_required"])
        return result

    def test_seven_buckets_priorities_duplicates_and_missing_account_match_domain(self):
        self.update_account(2, account_status="deactivated")
        self.member(2, team=self.other)
        self.member(3, team=self.other)
        self.member(3)
        self.member(4)
        self.invitation(4, execution_status="running")
        self.invitation(5, execution_status="waiting")
        self.update_account(5, access_token="", email_invalid=True)
        self.update_account(6, access_token="", email_invalid=True)
        self.invitation(6, invitation_state="pending", execution_status="failed")
        self.invitation(7, invitation_state="pending", execution_status="failed")
        ids = [str(value) for value in self.accounts[2:9]] + ["99999999", str(self.accounts[8])]
        result = self.assert_matches_domain(ids)
        self.assertEqual(result["counts"], {
            "unavailable_count": 2, "another_team_count": 1, "already_member_count": 1,
            "same_team_active_count": 1, "missing_auth_count": 1, "resume_invite_count": 1,
            "new_count": 1, "requested_count": 9, "unique_count": 8,
            "duplicate_count": 1, "eligible_count": 3,
        })
        self.assertEqual(result["additional_required"], 2)

    def test_all_other_team_occupation_sources_and_archived_account_match_domain(self):
        self.insert("team_account_ownership", {
            "account_id": self.accounts[2], "team_id": self.other, "kind": "invitation",
        })
        self.member(3, team=self.other)
        self.invitation(4, team=self.other, active=True, execution_status="failed")
        self.invitation(5, team=self.other, active=False, seat_reserved=True)
        self.invitation(6, team=self.other, active=False, invitation_state="pending")
        self.invitation(7, team=self.other, active=False, membership_state="joined")
        self.invitation(8, team=self.other, active=False, invitation_state="expired")
        self.update_account(8, archived=True)
        result = self.assert_matches_domain([str(value) for value in self.accounts[1:9]])
        self.assertEqual(result["counts"]["another_team_count"], 7)
        self.assertEqual(result["counts"]["new_count"], 1)

    def test_expected_email_distinguishes_absence_and_explicit_empty_snapshot(self):
        ids = [str(value) for value in self.accounts[2:9]]
        expected = {
            ids[0]: " PREVIEW-2@EXAMPLE.TEST ", ids[1]: "",
            ids[2]: "changed@example.test", ids[3]: None,
            ids[5]: "preview-7@example.test", ids[6]: "PREVIEW-8@example.test",
        }
        result = self.assert_matches_domain(ids, expected)
        self.assertEqual(result["counts"]["unavailable_count"], 2)
        self.assertEqual(result["counts"]["new_count"], 5)

    def test_frozen_email_array_escapes_quotes_backslashes_commas_and_literal_null(self):
        unusual = 'preview-{"\\\\,}@example.test'
        self.update_account(2, email=unusual)
        self.update_account(3, email="NULL")
        ids = [str(value) for value in self.accounts[2:4]]
        result = self.assert_matches_domain(ids, {ids[0]: unusual, ids[1]: "NULL"})
        self.assertEqual(result["counts"]["new_count"], 2)

    def test_frozen_email_uses_same_lower_and_space_normalization_as_sql(self):
        self.update_account(2, email="Straße@example.test")
        self.update_account(3, email="\u00a0preview-3@example.test\u00a0")
        self.update_account(4, email="Straße-original@example.test")
        ids = [str(value) for value in self.accounts[2:5]]
        result = self.assert_matches_domain(ids, {
            ids[0]: "STRASSE@example.test", ids[1]: "preview-3@example.test",
            ids[2]: "Straße-original@example.test",
        })
        self.assertEqual(result["counts"]["unavailable_count"], 2)
        self.assertEqual(result["counts"]["new_count"], 1)

    def test_unique_late_import_relations_and_ambiguous_global_email_match_domain(self):
        self.member(2, linked=False)
        self.member(3, team=self.other, linked=False)
        self.invitation(4, linked=False, invitation_state="pending", execution_status="failed")
        self.invitation(5, team=self.other, linked=False, active=False, seat_reserved=True)
        self.member(6, team=self.other, linked=False)
        self.invitation(7, team=self.other, linked=False, active=True)
        self.update_account(20, email=" PREVIEW-6@example.test ")
        self.update_account(21, email=" PREVIEW-7@example.test ")
        # 重复邮箱对应账号在本次窗口外，仍必须判定全库歧义。
        result = self.assert_matches_domain([str(value) for value in self.accounts[2:8]])
        self.assertEqual(result["counts"]["already_member_count"], 1)
        self.assertEqual(result["counts"]["another_team_count"], 2)
        self.assertEqual(result["counts"]["resume_invite_count"], 1)
        self.assertEqual(result["counts"]["new_count"], 2)

    def test_active_requires_persistent_intent_and_live_execution_status(self):
        for index, status in enumerate(sorted(domain.ACTIVE_STATUSES), start=2):
            self.invitation(index, execution_status=status)
        self.invitation(8, active=False, execution_status="running")
        self.invitation(9, active=True, execution_status="failed")
        result = self.assert_matches_domain([str(value) for value in self.accounts[2:10]])
        self.assertEqual(result["counts"]["same_team_active_count"], 6)
        self.assertEqual(result["counts"]["new_count"], 2)

    def test_latest_invitation_controls_pending_and_any_reservation_prevents_new_seat(self):
        self.invitation(2, key="older-pending", active=False, invitation_state="pending",
                        updated_at="2026-11-26T00:00:00Z")
        self.invitation(2, key="newer-expired", linked=False, active=False, invitation_state="expired",
                        updated_at="2026-11-27T00:00:00Z")
        self.invitation(3, key="older-reserved", active=False, seat_reserved=True,
                        updated_at="2026-11-26T00:00:00Z")
        self.invitation(3, key="newer-expired-three", linked=False, active=False, invitation_state="expired",
                        updated_at="2026-11-27T00:00:00Z")
        result = self.assert_matches_domain([str(value) for value in self.accounts[2:4]])
        self.assertEqual(result["counts"]["new_count"], 2)
        self.assertEqual(result["additional_required"], 0)

    def test_joined_intent_without_member_fact_already_occupies_seat(self):
        self.invitation(2, active=False, membership_state="joined")
        result = self.assert_matches_domain([str(self.accounts[2])])
        self.assertEqual(result["counts"]["new_count"], 1)
        self.assertEqual(result["additional_required"], 0)

    def test_derived_status_password_and_email_capability_match_domain(self):
        self.update_account(2, account_status="disabled")
        self.update_account(3, access_token="", password="合成密码", email_invalid=True)
        self.update_account(4, access_token="", email_invalid=False)
        self.update_account(5, access_token="", email_invalid=True)
        result = self.assert_matches_domain([str(value) for value in self.accounts[2:6]])
        self.assertEqual(result["counts"]["unavailable_count"], 1)
        self.assertEqual(result["counts"]["missing_auth_count"], 1)
        self.assertEqual(result["counts"]["new_count"], 2)

    def test_hundred_thousand_targets_and_out_of_bigint_reference_use_one_select(self):
        ids = [str(value) for value in range(1_000_000, 1_100_000)]
        ids += [str(2**63), "9" * 5000, ids[0]]
        statements = []
        execute = psycopg.Cursor.execute

        def observed(cursor, statement, *args, **kwargs):
            statements.append(str(statement))
            return execute(cursor, statement, *args, **kwargs)

        with self.read_only() as conn, patch.object(psycopg.Cursor, "execute", observed):
            result = self.preview.summary(self.team, ids, conn=conn)
        self.assertEqual(len(statements), 1)
        self.assertTrue(statements[0].lstrip().upper().startswith("WITH "))
        self.assertEqual(result["counts"]["requested_count"], 100_003)
        self.assertEqual(result["counts"]["unique_count"], 100_002)
        self.assertEqual(result["counts"]["duplicate_count"], 1)
        self.assertEqual(result["counts"]["unavailable_count"], 100_002)
        self.assertEqual(result["additional_required"], 0)

    def test_empty_targets_return_one_zero_summary(self):
        with self.read_only() as conn:
            result = self.preview.summary(self.team, [], conn=conn)
        self.assertEqual(set(result), {"counts", "additional_required"})
        self.assertTrue(all(value == 0 for value in result["counts"].values()))
        self.assertEqual(result["additional_required"], 0)

    def test_snapshot_returns_team_summary_and_existing_capacity_union_in_one_select(self):
        self.assertTrue(callable(getattr(self.preview, "snapshot", None)), "Team 预检快照尚未实现")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres.qualified('team_workspaces')} "
                "SET members_complete=TRUE,invitations_complete=TRUE,purchased_seats=10,"
                "planned_member_limit=8,snapshot_sequence=7,last_synced_at=now() WHERE id=%s",
                (self.team,),
            )
        self.member(2)
        self.member(3, linked=False)
        self.invitation(2, invitation_state="pending", seat_reserved=True)
        self.invitation(4, invitation_state="pending")
        self.invitation(4, linked=False, key="external-four", invitation_state="pending")
        ids = [str(value) for value in self.accounts[2:7]]
        statements = []
        execute = psycopg.Cursor.execute

        def observed(cursor, statement, *args, **kwargs):
            statements.append(str(statement))
            return execute(cursor, statement, *args, **kwargs)

        with self.read_only() as conn:
            with patch.object(psycopg.Cursor, "execute", observed):
                result = self.preview.snapshot(self.team, ids, conn=conn)
            expected = self.preview.summary(self.team, ids, conn=conn)
            facts = repository.get_capacity(self.team, conn=conn)
        self.assertEqual(len(statements), 1)
        self.assertEqual(result["counts"], expected["counts"])
        self.assertEqual(result["additional_required"], expected["additional_required"])
        self.assertEqual(result["team"]["id"], self.team)
        self.assertEqual(result["team"]["snapshot_sequence"], 7)
        self.assertIsNotNone(result["team"]["last_synced_at"])
        self.assertEqual(result["facts"], {key: facts[key] for key in (
            "purchased_seats", "planned_member_limit", "members_complete",
            "invitations_complete", "occupied_count",
        )})
        self.assertEqual(result["facts"]["occupied_count"], 3)

    def test_snapshot_incomplete_evidence_keeps_occupied_unknown_and_additional_integer(self):
        self.assertTrue(callable(getattr(self.preview, "snapshot", None)), "Team 预检快照尚未实现")
        self.member(2)
        with self.read_only() as conn:
            result = self.preview.snapshot(self.team, [str(self.accounts[3])], conn=conn)
        self.assertIsNone(result["facts"]["occupied_count"])
        self.assertFalse(result["facts"]["members_complete"])
        self.assertFalse(result["facts"]["invitations_complete"])
        self.assertEqual(result["additional_required"], 1)

    def test_snapshot_nonexistent_team_is_classified_as_not_found(self):
        self.assertTrue(callable(getattr(self.preview, "snapshot", None)), "Team 预检快照尚未实现")
        with self.read_only() as conn, self.assertRaises(TeamError) as raised:
            self.preview.snapshot(99999999, [str(self.accounts[2])], conn=conn)
        self.assertEqual(raised.exception.code, "team_not_found")
        self.assertEqual(raised.exception.status, 404)
