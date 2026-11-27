# -*- coding: utf-8 -*-
"""Team 领域表的真实 PostgreSQL 约束测试。"""
from __future__ import annotations

import importlib

from core.storage import postgres, records
from tests.support_pg import PostgresTestCase


class TeamSchemaTests(PostgresTestCase):
    def setUp(self):
        try:
            self.storage_schema = importlib.import_module("core.storage.teams.schema")
        except ModuleNotFoundError:
            self.fail("尚未实现 Team PostgreSQL schema 初始化")
        self.storage_schema.reset_ready()
        self.storage_schema.init()
        self.manager_id = self.seed(records.ACCOUNTS, [{
            "email": "manager@example.test",
            "created_at": "2026-11-27T00:00:00+00:00",
            "updated_at": "2026-11-27T00:00:00+00:00",
        }])[0]

    def _team(self, workspace_id="workspace-test"):
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {postgres.qualified('team_workspaces')} "
                "(workspace_id,manager_account_id) VALUES (%s,%s) RETURNING id",
                (workspace_id, self.manager_id),
            )
            return cur.fetchone()[0]

    def test_initializer_is_idempotent_and_creates_all_domain_tables(self):
        self.storage_schema.init()
        self.storage_schema.ensure_schema()
        expected = {
            "team_workspaces", "team_members", "team_invitations",
            "team_account_ownership", "team_binding_probes",
            "team_request_receipts", "team_join_requests",
            "team_join_request_items", "team_auth_contexts",
            "team_execution_receipts", "team_outbox",
        }
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname=%s",
                (self.schema,),
            )
            actual = {row[0] for row in cur.fetchall()}
        self.assertTrue(expected.issubset(actual), expected - actual)

    def test_unknown_counts_and_remote_facts_remain_null(self):
        team_id = self._team()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT purchased_seats,planned_member_limit,confirmed_member_count,"
                f"pending_invite_count,last_synced_at,members_complete,invitations_complete "
                f"FROM {postgres.qualified('team_workspaces')} WHERE id=%s",
                (team_id,),
            )
            row = cur.fetchone()
        self.assertEqual(row, (None, None, None, None, None, False, False))

    def test_zero_purchased_seats_is_valid_but_zero_local_limit_is_rejected(self):
        from psycopg.errors import CheckViolation
        team_id = self._team()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres.qualified('team_workspaces')} SET purchased_seats=0 WHERE id=%s",
                (team_id,),
            )
        with self.assertRaises(CheckViolation):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {postgres.qualified('team_workspaces')} SET planned_member_limit=0 WHERE id=%s",
                    (team_id,),
                )

    def test_account_business_ownership_is_unique_across_teams(self):
        from psycopg.errors import UniqueViolation
        first, second = self._team("first"), self._team("second")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {postgres.qualified('team_account_ownership')} "
                "(account_id,team_id,kind) VALUES (%s,%s,'manager')",
                (self.manager_id, first),
            )
        with self.assertRaises(UniqueViolation):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {postgres.qualified('team_account_ownership')} "
                    "(account_id,team_id,kind) VALUES (%s,%s,'member')",
                    (self.manager_id, second),
                )

    def test_remote_membership_history_can_preserve_cross_team_facts(self):
        first, second = self._team("first"), self._team("second")
        with postgres.connect() as conn, conn.cursor() as cur:
            for team_id in (first, second):
                cur.execute(
                    f"INSERT INTO {postgres.qualified('team_members')} "
                    "(team_id,identity_key,remote_user_id,account_id,membership_state) "
                    "VALUES (%s,'remote:user','user',%s,'joined')",
                    (team_id, self.manager_id),
                )
            cur.execute(
                f"SELECT count(*) FROM {postgres.qualified('team_members')} "
                "WHERE account_id=%s AND membership_state='joined'",
                (self.manager_id,),
            )
            self.assertEqual(cur.fetchone()[0], 2)

    def test_invitation_target_is_unique_within_team(self):
        from psycopg.errors import UniqueViolation
        team_id = self._team()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {postgres.qualified('team_invitations')} "
                "(team_id,target_key,email_snapshot) VALUES (%s,'email:one','one@example.test')",
                (team_id,),
            )
        with self.assertRaises(UniqueViolation):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {postgres.qualified('team_invitations')} "
                    "(team_id,target_key,email_snapshot) VALUES (%s,'email:one','one@example.test')",
                    (team_id,),
                )

    def test_outbox_lease_state_requires_token_and_expiry(self):
        from psycopg.errors import CheckViolation
        with self.assertRaises(CheckViolation):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {postgres.qualified('team_outbox')} "
                    "(kind,aggregate_type,aggregate_id,dedupe_key,status) "
                    "VALUES ('sync','team',1,'missing-lease','processing')"
                )

    def test_auth_context_cannot_be_saved_for_another_workspace(self):
        from psycopg.errors import ForeignKeyViolation
        team_id = self._team("workspace-correct")
        with self.assertRaises(ForeignKeyViolation):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {postgres.qualified('team_auth_contexts')} "
                    "(account_id,team_id,workspace_id,identity_ref,encrypted_context) "
                    "VALUES (%s,%s,'workspace-other','user-id','encrypted-value')",
                    (self.manager_id, team_id),
                )

    def test_old_manager_receipt_survives_but_workspace_mismatch_is_rejected(self):
        from psycopg.errors import ForeignKeyViolation
        team_id = self._team("workspace-correct")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres.qualified('team_workspaces')} SET manager_revision=2 WHERE id=%s",
                (team_id,),
            )
            cur.execute(
                f"INSERT INTO {postgres.qualified('team_execution_receipts')} "
                "(team_id,request_key,workspace_id,manager_account_id,manager_revision,execution_fence,kind) "
                "VALUES (%s,'old-manager','workspace-correct',%s,1,1,'invite') RETURNING manager_revision",
                (team_id, self.manager_id),
            )
            self.assertEqual(cur.fetchone()[0], 1)
        with self.assertRaises(ForeignKeyViolation):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {postgres.qualified('team_execution_receipts')} "
                    "(team_id,request_key,workspace_id,manager_account_id,manager_revision,execution_fence,kind) "
                    "VALUES (%s,'wrong-workspace','workspace-other',%s,1,1,'invite')",
                    (team_id, self.manager_id),
                )

    def test_member_and_invitation_sync_times_can_be_recorded_separately(self):
        team_id = self._team()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres.qualified('team_workspaces')} "
                "SET members_synced_at='2026-11-27T01:00:00Z',"
                "invitations_synced_at='2026-11-27T02:00:00Z' WHERE id=%s",
                (team_id,),
            )
            cur.execute(
                f"SELECT members_synced_at < invitations_synced_at "
                f"FROM {postgres.qualified('team_workspaces')} WHERE id=%s",
                (team_id,),
            )
            self.assertTrue(cur.fetchone()[0])

    def test_same_account_cannot_have_two_intents_even_with_different_keys(self):
        from psycopg.errors import UniqueViolation
        team_id = self._team()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {postgres.qualified('team_invitations')} "
                "(team_id,target_key,account_id) VALUES (%s,'account:first',%s)",
                (team_id, self.manager_id),
            )
        with self.assertRaises(UniqueViolation):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {postgres.qualified('team_invitations')} "
                    "(team_id,target_key,account_id) VALUES (%s,'account:second',%s)",
                    (team_id, self.manager_id),
                )

    def test_remote_identity_cannot_be_duplicated_via_different_keys(self):
        from psycopg.errors import UniqueViolation
        team_id = self._team()
        cases = (
            ("team_members", "identity_key", "remote_user_id"),
            ("team_invitations", "target_key", "remote_invitation_id"),
        )
        for table, key, remote in cases:
            with self.subTest(table=table):
                with postgres.connect() as conn, conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {postgres.qualified(table)} "
                        f"(team_id,{key},{remote}) VALUES (%s,'first','remote-id')",
                        (team_id,),
                    )
                with self.assertRaises(UniqueViolation):
                    with postgres.connect() as conn, conn.cursor() as cur:
                        cur.execute(
                            f"INSERT INTO {postgres.qualified(table)} "
                            f"(team_id,{key},{remote}) VALUES (%s,'second','remote-id')",
                            (team_id,),
                        )

    def test_member_keeps_narrow_latest_execution_status(self):
        team_id = self._team()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {postgres.qualified('team_members')} "
                "(team_id,identity_key,last_task_id,last_run_id,execution_status) "
                "VALUES (%s,'remote:member',20,30,'partial_success') RETURNING execution_status",
                (team_id,),
            )
            self.assertEqual(cur.fetchone()[0], "partial_success")

    def test_complete_snapshot_absence_counters_start_at_zero_and_reject_negative(self):
        from psycopg.errors import CheckViolation
        team_id = self._team()
        for table, key in (
            ("team_members", "identity_key"),
            ("team_invitations", "target_key"),
        ):
            with self.subTest(table=table):
                with postgres.connect() as conn, conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {postgres.qualified(table)} (team_id,{key}) "
                        "VALUES (%s,'remote:absence') RETURNING id,absent_complete_count",
                        (team_id,),
                    )
                    row_id, absent_count = cur.fetchone()
                    self.assertEqual(absent_count, 0)
                with self.assertRaises(CheckViolation):
                    with postgres.connect() as conn, conn.cursor() as cur:
                        cur.execute(
                            f"UPDATE {postgres.qualified(table)} "
                            "SET absent_complete_count=-1 WHERE id=%s",
                            (row_id,),
                        )

    def test_ownership_absence_counter_starts_at_zero_and_rejects_negative(self):
        from psycopg.errors import CheckViolation
        team_id = self._team()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {postgres.qualified('team_account_ownership')} "
                "(account_id,team_id,kind) VALUES (%s,%s,'manager') "
                "RETURNING absent_complete_count",
                (self.manager_id, team_id),
            )
            self.assertEqual(cur.fetchone()[0], 0)
        with self.assertRaises(CheckViolation):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {postgres.qualified('team_account_ownership')} "
                    "SET absent_complete_count=-1 WHERE account_id=%s",
                    (self.manager_id,),
                )

    def test_processing_index_covers_only_active_execution_states(self):
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT indexdef FROM pg_indexes WHERE schemaname=%s AND indexname=%s",
                (self.schema, "team_invitations_processing_idx"),
            )
            row = cur.fetchone()
        self.assertIsNotNone(row, "Team 列表的处理中聚合缺少部分覆盖索引")
        definition = row[0]
        self.assertIn("(team_id, account_id, target_key, updated_at)", definition)
        self.assertIn("active", definition)
        for status in ("queued", "running", "waiting", "cancelling", "settling", "stopping"):
            self.assertIn(f"'{status}'", definition)
        self.assertNotIn("'success'", definition)
        self.assertNotIn("'failed'", definition)

    def test_unlinked_email_indexes_match_account_normalization(self):
        definitions = {}
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=%s "
                "AND indexname=ANY(%s::text[])",
                (self.schema, ["team_members_unlinked_email_idx", "team_invitations_unlinked_email_idx"]),
            )
            definitions = dict(cur.fetchall())
        self.assertEqual(len(definitions), 2, "未关联远端事实缺少规范邮箱部分索引")
        for name, column in (
            ("team_members_unlinked_email_idx", "email"),
            ("team_invitations_unlinked_email_idx", "email_snapshot"),
        ):
            definition = definitions[name]
            self.assertIn(f"lower(btrim(COALESCE({column}, ''::text)))", definition)
            self.assertIn("account_id IS NULL", definition)
        self.assertIn("'joined'", definitions["team_members_unlinked_email_idx"])
