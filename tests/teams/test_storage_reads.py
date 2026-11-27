# -*- coding: utf-8 -*-
"""Team 窄读模型、集合归属与旧部署兼容的隔离回归。"""
from __future__ import annotations

import importlib
import importlib.util
from contextlib import contextmanager

from psycopg import sql
from psycopg.rows import dict_row

from core.storage import postgres, records
from core.storage.teams import schema
from tests.support_pg import PostgresTestCase


class _ReadModuleMixin:
    def load_reads(self):
        self.assertIsNotNone(
            importlib.util.find_spec("core.storage.teams.reads"),
            "Team 只读仓储尚未实现",
        )
        return importlib.import_module("core.storage.teams.reads")


class TeamReadsLegacyTests(_ReadModuleMixin, PostgresTestCase):
    def test_membership_enrichment_does_not_create_missing_tables(self):
        reads = self.load_reads()
        with postgres.connect(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename", (self.schema,))
                before = cur.fetchall()
            self.assertEqual(reads.get_account_memberships([1, 2], conn=conn), {})
            with conn.cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename", (self.schema,))
                self.assertEqual(cur.fetchall(), before)

    def test_missing_team_tables_return_classified_unavailability(self):
        reads = self.load_reads()
        from core.teams.errors import TeamError

        for method, args in (
            (reads.get_team, (1,)),
            (reads.list_teams, ()),
            (reads.list_members, (1,)),
            (reads.list_invitations, (1,)),
            (reads.get_invitation, (1, 2)),
            (reads.get_account_states, (1, [2])),
        ):
            with self.subTest(method=method.__name__):
                with self.assertRaises(TeamError) as raised:
                    method(*args)
                self.assertEqual(raised.exception.code, "team_store_unavailable")
                self.assertEqual(raised.exception.status, 503)
                self.assertTrue(raised.exception.retryable)


class TeamStorageReadsTests(_ReadModuleMixin, PostgresTestCase):
    def setUp(self):
        self.reads = self.load_reads()
        schema.reset_ready()
        schema.init()
        self.accounts = self.seed(records.ACCOUNTS, [
            {"email": f"reader-{index}@example.test", "created_at": "2026-11-27",
             "updated_at": "2026-11-27", "archived": index == 0,
             **({"access_token": "测试私有AT", "chatgpt_session": '{"private":"测试Session"}'}
                if index == 2 else {})}
            for index in range(10)
        ])
        self.team = self.insert("team_workspaces", {
            "workspace_id": "workspace-first", "manager_account_id": self.accounts[0],
            "name": "第一团队", "role": "owner", "confirmed_member_count": 7,
            "pending_invite_count": 3, "last_sync_status": "success",
        })
        self.other = self.insert("team_workspaces", {
            "workspace_id": "workspace-second", "manager_account_id": self.accounts[1],
            "name": "第二团队", "display_name": "第二备注", "role": "admin",
        })

    def insert(self, table, values):
        with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
                    sql.Identifier(self.schema, table),
                    sql.SQL(",").join(map(sql.Identifier, values)),
                    sql.SQL(",").join(sql.Placeholder() for _ in values),
                ),
                list(values.values()),
            )
            return cur.fetchone()["id"]

    def test_invitation_detail_and_list_resolve_later_imported_unique_account_without_writing(self):
        invitation_id = self.insert("team_invitations", {
            "team_id": self.team, "target_key": "external-reader-2", "account_id": None,
            "email_snapshot": " READER-2@example.test ", "invitation_state": "pending",
        })
        with self.read_only() as conn:
            detail = self.reads.get_invitation(self.team, invitation_id, conn=conn)
            listing = self.reads.list_invitations(self.team, conn=conn)
            self.assertEqual(detail["account_id"], self.accounts[2])
            self.assertEqual(detail["account_email"], "reader-2@example.test")
            self.assertEqual(listing["items"][0]["account_id"], self.accounts[2])
            with conn.cursor() as cur:
                cur.execute(f"SELECT account_id FROM {postgres.qualified('team_invitations')} WHERE id=%s",
                            (invitation_id,))
                self.assertIsNone(cur.fetchone()["account_id"])

    def invitation(self, index, *, team=None, **values):
        return self.insert("team_invitations", {
            "team_id": team or self.team, "target_key": f"account:{self.accounts[index]}",
            "account_id": self.accounts[index], "email_snapshot": f"reader-{index}@example.test",
            **values,
        })

    def member(self, index, *, team=None, state="joined", **values):
        return self.insert("team_members", {
            "team_id": team or self.team, "identity_key": f"user:{index}",
            "account_id": self.accounts[index], "email": f"reader-{index}@example.test",
            "membership_state": state, **values,
        })

    @contextmanager
    def read_only(self):
        with postgres.connect(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
            yield conn

    def test_team_reads_use_saved_counts_and_distinct_active_targets(self):
        self.invitation(2, execution_status="running")
        self.invitation(3, execution_status="failed", invitation_state="unconfirmed")
        self.invitation(4, execution_status="waiting")
        self.invitation(5, execution_status="queued", active=False)
        with self.read_only() as conn:
            row = self.reads.get_team(self.team, conn=conn)
            listing = self.reads.list_teams({"page_size": 1}, conn=conn)
        self.assertEqual((row["confirmed_member_count"], row["pending_invite_count"]), (7, 3))
        self.assertEqual(row["processing_count"], 2)
        self.assertEqual(row["manager_email"], "reader-0@example.test")
        self.assertTrue(row["manager_archived"])
        self.assertEqual(listing["total"], 2)
        self.assertEqual(listing["items"][0]["id"], self.other)
        self.assertIsNone(listing["items"][0]["confirmed_member_count"])
        self.assertNotIn("data", row)

    def test_team_filters_facets_and_empty_page_share_full_scope(self):
        result = self.reads.list_teams({
            "role": "owner", "q": "第一", "page": 8, "page_size": 1, "include_facets": True,
        })
        self.assertEqual(result["items"], [])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["facets"]["role"], [{"value": "owner", "count": 1}])
        exact = self.reads.list_teams({"manager_account_id": str(self.accounts[1])})
        self.assertEqual([row["id"] for row in exact["items"]], [self.other])

    def test_processing_changes_advance_team_list_revision(self):
        query = {"manager_account_id": str(self.accounts[0])}
        before = self.reads.list_teams(query)
        self.invitation(2, execution_status="running")
        after = self.reads.list_teams(query)
        self.assertEqual(before["items"][0]["processing_count"], 0)
        self.assertEqual(after["items"][0]["processing_count"], 1)
        self.assertNotEqual(before["revision"], after["revision"])

    def test_finishing_older_active_target_advances_revision(self):
        first = self.invitation(2, execution_status="running")
        self.invitation(3, execution_status="running")
        query = {"manager_account_id": str(self.accounts[0])}
        before = self.reads.list_teams(query)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres.qualified('team_invitations')} "
                "SET execution_status='success',active=FALSE,updated_at=now() WHERE id=%s",
                (first,),
            )
        after = self.reads.list_teams(query)
        self.assertEqual(before["items"][0]["processing_count"], 2)
        self.assertEqual(after["items"][0]["processing_count"], 1)
        self.assertNotEqual(before["revision"], after["revision"])

    def test_member_defaults_and_link_filters_preserve_unlinked_remote_facts(self):
        joined = self.member(2, role="member")
        self.member(3, state="left")
        external = self.insert("team_members", {
            "team_id": self.team, "identity_key": "user:external",
            "email": "external@example.test", "membership_state": "joined",
        })
        with self.read_only() as conn:
            result = self.reads.list_members(self.team, {"include_facets": True}, conn=conn)
        self.assertEqual([row["id"] for row in result["items"]], [joined, external])
        self.assertEqual(result["facets"]["linked"], [
            {"value": "linked", "count": 1}, {"value": "unlinked", "count": 1},
        ])
        self.assertIsNone(result["items"][1]["account_email"])
        filtered = self.reads.list_members(self.team, {"linked": "linked", "q": "reader-2"})
        self.assertEqual(filtered["items"][0]["account_email"], "reader-2@example.test")
        self.assertNotIn("access_token", filtered["items"][0])

    def test_list_and_facets_use_one_snapshot_during_concurrent_member_insert(self):
        self.member(2, role="member")
        test_case = self

        class ObservedCursor:
            def __init__(self, inner, after_read):
                self.inner, self.after_read = inner, after_read

            def __enter__(self):
                self.inner.__enter__()
                return self

            def __exit__(self, *args):
                return self.inner.__exit__(*args)

            def execute(self, *args, **kwargs):
                return self.inner.execute(*args, **kwargs)

            def fetchall(self):
                rows = self.inner.fetchall()
                self.after_read()
                return rows

        class ObservedConnection:
            inserted = False

            def __init__(self, inner):
                self.inner = inner

            def after_read(self):
                if not self.inserted:
                    self.inserted = True
                    test_case.member(3, role="admin")

            def cursor(self, *args, **kwargs):
                return ObservedCursor(self.inner.cursor(*args, **kwargs), self.after_read)

        with self.read_only() as conn:
            result = self.reads.list_members(
                self.team, {"include_facets": True}, conn=ObservedConnection(conn),
            )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["facets"]["role"], [{"value": "member", "count": 1}])
        self.assertEqual(self.reads.list_members(self.team)["total"], 2)

    def test_invitation_request_filter_does_not_duplicate_or_escape_team(self):
        first = self.invitation(2, invitation_state="pending", execution_status="waiting")
        self.invitation(3, invitation_state="expired", execution_status="failed")
        foreign = self.invitation(4, team=self.other, invitation_state="pending")
        request = self.insert("team_join_requests", {
            "team_id": self.team, "requested_count": 2, "unique_count": 2,
        })
        with postgres.connect() as conn, conn.cursor() as cur:
            for ordinal in (0, 1):
                cur.execute(
                    f"INSERT INTO {postgres.qualified('team_join_request_items')} "
                    "(request_id,ordinal,invitation_id) VALUES (%s,%s,%s)",
                    (request, ordinal, first),
                )
        with self.read_only() as conn:
            result = self.reads.list_invitations(
                self.team, {"join_request_id": str(request), "include_facets": True}, conn=conn,
            )
            self.assertIsNone(self.reads.get_invitation(self.team, foreign, conn=conn))
            self.assertEqual(self.reads.get_invitation(self.team, first, conn=conn)["id"], first)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["facets"]["invitation_state"], [{"value": "pending", "count": 1}])

    def test_batch_states_include_all_local_ownership_sources_without_secrets(self):
        self.member(2)
        self.member(2, team=self.other)
        pending = self.invitation(3, invitation_state="pending", execution_status="failed")
        active = self.invitation(4, execution_status="running", seat_reserved=True)
        self.invitation(5, team=self.other, invitation_state="pending", execution_status="none")
        unknown = self.invitation(6, invitation_state="unconfirmed", execution_status="failed")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {postgres.qualified('team_account_ownership')} "
                "(account_id,team_id,kind,invitation_id) VALUES (%s,%s,%s,%s)",
                (self.accounts[6], self.team, "join_intent", unknown),
            )
        with self.read_only() as conn:
            states = self.reads.get_account_states(
                self.team, self.accounts + [999_999, self.accounts[2]], conn=conn,
            )
        self.assertEqual(len(states), 10)
        self.assertEqual(states[self.accounts[1]]["other_teams"][0]["id"], str(self.other))
        self.assertTrue(states[self.accounts[2]]["already_member"])
        self.assertEqual(len(states[self.accounts[2]]["other_teams"]), 1)
        self.assertEqual(states[self.accounts[3]]["invitation"]["id"], pending)
        self.assertIsNone(states[self.accounts[3]]["active_invitation"])
        self.assertEqual(states[self.accounts[4]]["active_invitation"]["id"], active)
        self.assertTrue(states[self.accounts[4]]["reservation_active"])
        self.assertEqual(states[self.accounts[5]]["other_teams"][0]["id"], str(self.other))
        self.assertTrue(states[self.accounts[6]]["has_owner"])
        self.assertEqual(states[self.accounts[2]]["auth_capability"], "available")
        self.assertEqual(states[self.accounts[7]]["auth_capability"], "unknown")
        self.assertNotIn("access_token", states[self.accounts[2]])
        self.assertNotIn("chatgpt_session", states[self.accounts[2]])
        self.assertNotIn("extra_json", states[self.accounts[2]])

    def test_email_failure_is_separate_from_account_unavailability(self):
        records.patch_row(records.ACCOUNTS, self.accounts[2], {"email_invalid": True})
        records.patch_row(records.ACCOUNTS, self.accounts[3], {"email_invalid": True})
        records.patch_row(records.ACCOUNTS, self.accounts[4], {"account_status": "deactivated"})
        states = self.reads.get_account_states(self.team, self.accounts)
        self.assertFalse(states[self.accounts[2]]["account_unavailable"])
        self.assertEqual(states[self.accounts[2]]["email_status"], "invalid")
        self.assertEqual(states[self.accounts[2]]["auth_capability"], "available")
        self.assertEqual(states[self.accounts[3]]["auth_capability"], "missing")
        self.assertTrue(states[self.accounts[4]]["account_unavailable"])

    def test_membership_enrichment_only_returns_confirmed_deduplicated_relations(self):
        self.member(2, role="member")
        self.member(2, team=self.other, role="admin")
        self.member(3, state="left")
        with self.read_only() as conn:
            memberships = self.reads.get_account_memberships(self.accounts + [999_999], conn=conn)
        self.assertNotIn(self.accounts[3], memberships)
        self.assertNotIn(self.accounts[0], memberships)
        self.assertEqual([row["team_id"] for row in memberships[self.accounts[2]]],
                         [str(self.team), str(self.other)])
        self.assertEqual(set(memberships[self.accounts[2]][0]), {
            "team_id", "workspace_id", "name", "display_name", "role",
            "membership_state", "last_verified_at",
        })

    def test_later_imported_account_recognizes_other_team_remote_pending_invitation(self):
        self.insert("team_invitations", {
            "team_id": self.other, "target_key": "remote:later-imported",
            "remote_invitation_id": "remote-later-imported",
            "email_snapshot": " LATER-IMPORTED@example.test ", "invitation_state": "pending",
            "execution_status": "none", "active": False,
        })
        imported = self.seed(records.ACCOUNTS, [{
            "email": "later-imported@example.test", "created_at": "2026-11-27",
            "updated_at": "2026-11-27",
        }])[0]
        with self.read_only() as conn:
            state = self.reads.get_account_states(self.team, [imported], conn=conn)[imported]
        self.assertTrue(state["has_owner"])
        self.assertEqual([item["id"] for item in state["other_teams"]], [str(self.other)])

    def test_later_imported_account_can_resume_same_team_unlinked_invitation(self):
        invitation = self.insert("team_invitations", {
            "team_id": self.team, "target_key": "remote:resume-later",
            "remote_invitation_id": "remote-resume-later", "email_snapshot": "resume-later@example.test",
            "invitation_state": "pending", "execution_status": "failed", "active": False,
        })
        imported = self.seed(records.ACCOUNTS, [{
            "email": "RESUME-LATER@example.test", "created_at": "2026-11-27",
            "updated_at": "2026-11-27",
        }])[0]
        with self.read_only() as conn:
            state = self.reads.get_account_states(self.team, [imported], conn=conn)[imported]
        self.assertTrue(state["has_owner"])
        self.assertEqual(state["invitation"]["id"], invitation)
        self.assertEqual(state["invitation"]["account_id"], imported)
        self.assertEqual(state["invitation"]["invitation_state"], "pending")
        self.assertIsNone(state["active_invitation"])
        self.assertEqual(state["other_teams"], [])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT account_id FROM {postgres.qualified('team_invitations')} WHERE id=%s",
                (invitation,),
            )
            self.assertIsNone(cur.fetchone()[0])

    def test_email_fallback_does_not_pick_ambiguous_or_replace_linked_identity(self):
        duplicates = self.seed(records.ACCOUNTS, [
            {"email": email, "created_at": "2026-11-27", "updated_at": "2026-11-27"}
            for email in ("duplicate@example.test", " DUPLICATE@example.test ")
        ])
        self.insert("team_invitations", {
            "team_id": self.other, "target_key": "remote:duplicate",
            "email_snapshot": "duplicate@example.test", "invitation_state": "pending",
            "execution_status": "none", "active": False,
        })
        self.invitation(2, team=self.other, email_snapshot="reader-3@example.test",
                        invitation_state="pending", execution_status="none", active=False)
        self.member(4, team=self.other, email="reader-5@example.test")
        with self.read_only() as conn:
            states = self.reads.get_account_states(
                self.team, [duplicates[0], self.accounts[2], self.accounts[3],
                            self.accounts[4], self.accounts[5]], conn=conn,
            )
        self.assertFalse(states[duplicates[0]]["has_owner"])
        self.assertFalse(states[self.accounts[3]]["has_owner"])
        self.assertFalse(states[self.accounts[5]]["has_owner"])
        self.assertTrue(states[self.accounts[2]]["has_owner"])
        self.assertTrue(states[self.accounts[4]]["has_owner"])

    def test_later_imported_account_recognizes_joined_remote_member_in_state_and_enrichment(self):
        self.insert("team_members", {
            "team_id": self.team, "identity_key": "remote:joined-later",
            "remote_user_id": "remote-joined-later", "email": " JOINED-LATER@example.test ",
            "membership_state": "joined", "role": "member",
        })
        imported = self.seed(records.ACCOUNTS, [{
            "email": "joined-later@example.test", "created_at": "2026-11-27",
            "updated_at": "2026-11-27",
        }])[0]
        with self.read_only() as conn:
            state = self.reads.get_account_states(self.team, [imported], conn=conn)[imported]
            memberships = self.reads.get_account_memberships([imported], conn=conn)
        self.assertTrue(state["already_member"])
        self.assertTrue(state["has_owner"])
        self.assertEqual([item["team_id"] for item in memberships[imported]], [str(self.team)])

    def test_large_target_window_uses_set_queries_with_bounded_statement_time(self):
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {postgres.qualified('registered_accounts')} "
                "(email,created_at,updated_at) SELECT 'window-'||n||'@example.test',"
                "'2026-11-27','2026-11-27' FROM generate_series(1,10000) n RETURNING id"
            )
            imported = [row[0] for row in cur.fetchall()]
            cur.execute(f"ANALYZE {postgres.qualified('registered_accounts')}")
        self.insert("team_members", {
            "team_id": self.team, "identity_key": "remote:large-window",
            "email": "WINDOW-1@example.test", "membership_state": "joined",
        })
        self.insert("team_invitations", {
            "team_id": self.team, "target_key": "remote:large-window",
            "email_snapshot": "window-2@example.test", "invitation_state": "pending",
            "execution_status": "none", "active": False,
        })
        with self.read_only() as conn:
            # 预算高于产品目标，专门拒绝目标数×全账号扫描的数量级退化。
            conn.execute("SET LOCAL statement_timeout='1500ms'")
            states = self.reads.get_account_states(self.team, imported[:1000], conn=conn)
            memberships = self.reads.get_account_memberships(imported[:1000], conn=conn)
        self.assertEqual(len(states), 1000)
        self.assertTrue(states[imported[0]]["already_member"])
        self.assertEqual(states[imported[1]]["invitation"]["invitation_state"], "pending")
        self.assertEqual(memberships[imported[0]][0]["team_id"], str(self.team))

    def test_member_link_filter_and_facet_use_resolved_unique_account(self):
        linked = self.insert("team_members", {
            "team_id": self.team, "identity_key": "remote:resolved-link",
            "email": "READER-2@example.test", "membership_state": "joined",
        })
        self.insert("team_members", {
            "team_id": self.team, "identity_key": "remote:without-link",
            "email": "outside@example.test", "membership_state": "joined",
        })
        with self.read_only() as conn:
            listing = self.reads.list_members(self.team, {"include_facets": True}, conn=conn)
            filtered = self.reads.list_members(self.team, {"linked": "linked"}, conn=conn)
        self.assertEqual([item["id"] for item in filtered["items"]], [linked])
        self.assertEqual(listing["facets"]["linked"], [
            {"value": "linked", "count": 1}, {"value": "unlinked", "count": 1},
        ])

    def test_read_revision_changes_when_fallback_resolves_a_different_account_id(self):
        self.insert("team_members", {
            "team_id": self.team, "identity_key": "remote:replacement",
            "email": "reader-2@example.test", "membership_state": "joined",
        })
        before = self.reads.list_members(self.team)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {postgres.qualified('registered_accounts')} WHERE id=%s",
                (self.accounts[2],),
            )
            cur.execute(
                f"INSERT INTO {postgres.qualified('registered_accounts')} (email,created_at,updated_at) "
                "VALUES ('reader-2@example.test','2026-11-27','2026-11-27') RETURNING id"
            )
            replacement = cur.fetchone()[0]
        after = self.reads.list_members(self.team)
        self.assertEqual(before["items"][0]["account_id"], self.accounts[2])
        self.assertEqual(after["items"][0]["account_id"], replacement)
        self.assertNotEqual(before["revision"], after["revision"])

    def test_already_occupied_aggregates_pending_and_joined_without_a_local_reservation(self):
        older = self.invitation(2, invitation_state="pending", execution_status="failed", active=False)
        self.insert("team_invitations", {
            "team_id": self.team, "target_key": "remote:expired-newer",
            "email_snapshot": "reader-2@example.test", "invitation_state": "expired",
            "execution_status": "failed", "active": False,
        })
        self.invitation(3, membership_state="joined", execution_status="success", active=False)
        with self.read_only() as conn:
            states = self.reads.get_account_states(
                self.team, [self.accounts[2], self.accounts[3], self.accounts[4]], conn=conn,
            )
        self.assertNotEqual(states[self.accounts[2]]["invitation"]["id"], older)
        for account_id in (self.accounts[2], self.accounts[3]):
            self.assertTrue(states[account_id].get("already_occupied"))
            self.assertFalse(states[account_id]["reservation_active"])
        self.assertFalse(states[self.accounts[4]].get("already_occupied"))
