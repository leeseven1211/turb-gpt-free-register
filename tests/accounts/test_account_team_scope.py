"""账号 Team 范围在列表、轮询、分面和名单查询中保持一致。"""
from __future__ import annotations

import unittest
import uuid

from core.accounts import query
from core.storage import admin_repository as admin, postgres, records
from tests.support_pg import PostgresTestCase


class AccountTeamScopeContractTests(unittest.TestCase):
    def test_default_and_archive_aliases_remain_independent(self):
        self.assertEqual("all", query.normalize_query({})["team_scope"])
        for value in ("1", "true", "yes", "only"):
            normalized = query.normalize_query({"team_scope": "team", "archived": value})
            self.assertEqual("team", normalized["team_scope"])
            self.assertEqual("only", normalized["archived"])
        self.assertEqual("all", query.from_legacy(archived="include", team_scope="non_team")["archived"])

    def test_invalid_team_scope_is_rejected_in_both_entrypoints(self):
        for value in ("joined", "team,non_team", "", True, None):
            with self.subTest(value=value):
                with self.assertRaises(query.AccountQueryError) as error:
                    query.normalize_query({"team_scope": value})
                self.assertEqual("team_scope", error.exception.field)
        with self.assertRaises(query.AccountQueryError):
            query.from_legacy(team_scope="joined")

    def test_team_scope_changes_query_identity(self):
        self.assertNotEqual(query.query_hash({"team_scope": "team"}),
                            query.query_hash({"team_scope": "non_team"}))


class AccountTeamScopeStorageTests(PostgresTestCase):
    def setUp(self):
        from core.storage.teams import schema
        records.init()
        schema.reset_ready()
        schema.init()
        self.ids = self.seed(records.ACCOUNTS, [
            {"email": "scope-unassigned@example.test", "email_source": "outlook"},
            {"email": "scope-joined@example.test", "email_source": "icloud_hide"},
            {"email": "scope-archived@example.test", "email_source": "outlook", "archived": True},
            {"email": "scope-unconfirmed@example.test", "email_source": "outlook"},
            {"email": "scope-left@example.test", "email_source": "outlook"},
            {"email": "scope-manager@example.test", "email_source": "outlook"},
        ])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {postgres.qualified('team_workspaces')}
                (workspace_id,name,display_name,manager_account_id) VALUES
                ('scope-workspace-a','远端名称','本地备注',%s),
                ('scope-workspace-b','另一团队',NULL,%s) RETURNING id""", (self.ids[5], self.ids[5]))
            self.teams = [row[0] for row in cur.fetchall()]
            for team_id, account_id, state in (
                (self.teams[0], self.ids[1], "joined"), (self.teams[1], self.ids[1], "joined"),
                (self.teams[0], self.ids[2], "joined"), (self.teams[0], self.ids[3], "unconfirmed"),
                (self.teams[0], self.ids[4], "left"),
            ):
                cur.execute(f"""INSERT INTO {postgres.qualified('team_members')}
                    (team_id,account_id,identity_key,role,membership_state,last_verified_at)
                    VALUES (%s,%s,%s,'member',%s,now())""", (team_id, account_id, str(account_id), state))

    def test_joined_scope_is_unique_and_shared_by_list_status_count_and_facets(self):
        for scope, archived, expected in (
            ("team", "all", self.ids[1:3]), ("non_team", "0", [self.ids[n] for n in (0, 3, 4, 5)]),
            ("all", "only", [self.ids[2]]), ("team", "1", [self.ids[2]]),
        ):
            with self.subTest(scope=scope, archived=archived):
                spec = {"team_scope": scope, "archived": archived}
                listed = admin.list_accounts(admin.PageRequest(page_size=100), **spec)
                statuses = admin.list_account_statuses(admin.PageRequest(page_size=100), compact=True, **spec)
                self.assertEqual(expected[::-1], [row["id"] for row in listed["items"]])
                self.assertEqual(expected[::-1], [row["id"] for row in statuses["items"]])
                self.assertEqual(len(expected), listed["total"])
                self.assertEqual(len(expected), statuses["total"])
                self.assertEqual(len(expected), admin.account_query_count(spec))
                self.assertEqual(len(expected), sum(row["count"] for row in listed["facets"]["source"]))
                self.assertEqual(len(expected), sum(row["count"] for row in admin.account_query_facets(spec)["source"]))
        joined = admin.list_accounts(admin.PageRequest(page_size=100), team_scope="team", archived="all")["items"][-1]
        self.assertEqual(2, len(joined["team_memberships"]))
        fields = {"team_id", "workspace_id", "name", "display_name", "role", "membership_state", "last_verified_at"}
        self.assertTrue(all(set(item) == fields for item in joined["team_memberships"]))
        self.assertEqual(str(self.teams[0]), joined["team_memberships"][0]["team_id"])

    def test_final_confirmed_membership_leaving_updates_scope_and_clears_status(self):
        before = admin.list_account_statuses(admin.PageRequest(page_size=100), archived="all")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('team_members')} SET membership_state='left' WHERE account_id=%s",
                        (self.ids[1],))
        after = admin.list_account_statuses(admin.PageRequest(page_size=100), archived="all")
        self.assertNotEqual(before["revision"], after["revision"])
        changed = next(item for item in after["items"] if item["id"] == self.ids[1])
        self.assertEqual([], changed["team_memberships"])
        remaining = admin.list_accounts(admin.PageRequest(), team_scope="team", archived="all")
        self.assertEqual([self.ids[2]], [item["id"] for item in remaining["items"]])

    def test_later_imported_joined_member_is_in_every_team_query_without_writing_link(self):
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {postgres.qualified('team_members')}
                (team_id,identity_key,email,role,membership_state,last_verified_at)
                VALUES (%s,'remote:scope-later',' SCOPE-LATER@example.test ','owner','joined',now())
                RETURNING id""", (self.teams[0],))
            remote_member = cur.fetchone()[0]
        imported = self.seed(records.ACCOUNTS, [
            {"email": "scope-later@example.test", "email_source": "outlook"},
        ])[0]
        all_rows = admin.list_accounts(admin.PageRequest(page_size=100), archived="all")["items"]
        enriched = next(row for row in all_rows if row["id"] == imported)
        self.assertEqual([str(self.teams[0])], [row["team_id"] for row in enriched["team_memberships"]])
        expected = [imported, self.ids[2], self.ids[1]]
        spec = {"team_scope": "team", "archived": "all"}
        listed = admin.list_accounts(admin.PageRequest(page_size=100), **spec)
        statuses = admin.list_account_statuses(admin.PageRequest(page_size=100), compact=True, **spec)
        self.assertEqual(expected, [row["id"] for row in listed["items"]])
        self.assertEqual(expected, [row["id"] for row in statuses["items"]])
        self.assertEqual(3, listed["total"])
        self.assertEqual(3, statuses["total"])
        self.assertEqual(3, admin.account_query_count(spec))
        self.assertEqual(3, sum(row["count"] for row in listed["facets"]["source"]))
        self.assertEqual(3, sum(row["count"] for row in admin.account_query_facets(spec)["source"]))
        where, values = query.compile_query(spec)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT a.id FROM {postgres.qualified('registered_accounts')} a
                WHERE {where} ORDER BY a.id DESC""", values)
            self.assertEqual(expected, [row[0] for row in cur.fetchall()])
            cur.execute(f"SELECT account_id FROM {postgres.qualified('team_members')} WHERE id=%s",
                        (remote_member,))
            self.assertIsNone(cur.fetchone()[0])
        non_team = admin.list_accounts(
            admin.PageRequest(page_size=100), team_scope="non_team", archived="all")
        self.assertNotIn(imported, [row["id"] for row in non_team["items"]])

    def test_later_imported_pending_identity_stays_non_team(self):
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {postgres.qualified('team_members')}
                (team_id,identity_key,email,role,membership_state)
                VALUES (%s,'remote:scope-pending',' SCOPE-PENDING@example.test ','member','unconfirmed')""",
                        (self.teams[0],))
            cur.execute(f"""INSERT INTO {postgres.qualified('team_invitations')}
                (team_id,target_key,email_snapshot,invitation_state)
                VALUES (%s,'remote:scope-pending','scope-pending@example.test','pending')""",
                        (self.teams[0],))
        imported = self.seed(records.ACCOUNTS, [
            {"email": "scope-pending@example.test", "email_source": "outlook"},
        ])[0]
        for scope, expected in (("team", []), ("non_team", [imported])):
            with self.subTest(scope=scope):
                rows = admin.list_accounts(
                    admin.PageRequest(filters={"id": str(imported)}), team_scope=scope, archived="all")["items"]
                self.assertEqual(expected, [row["id"] for row in rows])
                if rows:
                    self.assertEqual([], rows[0]["team_memberships"])

    def test_ambiguous_email_is_not_inferred_when_duplicate_is_archived_and_outside_query(self):
        duplicates = self.seed(records.ACCOUNTS, [
            {"email": "scope-duplicate@example.test", "email_source": "outlook"},
            {"email": " SCOPE-DUPLICATE@example.test ", "email_source": "outlook", "archived": True},
        ])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {postgres.qualified('team_members')}
                (team_id,identity_key,email,role,membership_state)
                VALUES (%s,'remote:scope-duplicate','scope-duplicate@example.test','member','joined')""",
                        (self.teams[0],))
        for account_id, archived in ((duplicates[0], "0"), (duplicates[1], "only")):
            with self.subTest(account_id=account_id):
                request = admin.PageRequest(filters={"id": str(account_id)})
                team = admin.list_accounts(request, team_scope="team", archived=archived)
                non_team = admin.list_accounts(request, team_scope="non_team", archived=archived)
                self.assertEqual([], team["items"])
                self.assertEqual([account_id], [row["id"] for row in non_team["items"]])
                self.assertEqual([], non_team["items"][0]["team_memberships"])

    def test_saved_account_link_wins_over_changed_remote_email(self):
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {postgres.qualified('team_members')}
                (team_id,account_id,identity_key,email,role,membership_state)
                VALUES (%s,%s,'remote:scope-linked','scope-unassigned@example.test','member','joined')""",
                        (self.teams[0], self.ids[4]))
        team = admin.list_accounts(admin.PageRequest(page_size=100), team_scope="team", archived="all")
        self.assertEqual([self.ids[4], self.ids[2], self.ids[1]], [row["id"] for row in team["items"]])
        non_team = admin.list_accounts(admin.PageRequest(page_size=100), team_scope="non_team", archived="all")
        unassigned = next(row for row in non_team["items"] if row["id"] == self.ids[0])
        self.assertEqual([], unassigned["team_memberships"])

    def test_http_list_and_poll_preserve_scope_and_validate_enum(self):
        from webui.app import create_app
        client = create_app(auth_code="scope-test").test_client()
        for endpoint in ("/api/accounts?page=1&include_facets=1", "/api/accounts/plan-check-status?compact=1"):
            response = client.get(endpoint + "&team_scope=team&archived=all", headers={"X-Auth-Code": "scope-test"})
            self.assertEqual(200, response.status_code, response.get_json())
            self.assertEqual(self.ids[1:3][::-1], [row["id"] for row in response.get_json()["items"]])
            self.assertTrue(all("team_memberships" in row for row in response.get_json()["items"]))
            invalid = client.get(endpoint + "&team_scope=joined", headers={"X-Auth-Code": "scope-test"})
            self.assertEqual(422, invalid.status_code)

    def test_query_selection_keeps_joined_accounts_when_later_membership_changes(self):
        from core.storage.operations import bulk
        from core.teams.selection import read_team_selection
        bulk.reset_ready()
        bulk.init()
        spec = query.normalize_query({"team_scope": "team", "archived": "all"})
        selected = bulk.create_selection(
            request_key=uuid.uuid4().hex, source={"kind": "query", "query": spec},
            operation_key="team_join", parameters={"team_id": str(self.teams[0])},
            config_revision="team_join.v1", query_spec=spec)
        where, values = query.compile_query(spec)
        frozen = bulk.freeze_selection(selected["id"], where_sql=where, params=values)
        self.assertEqual(2, frozen["target_count"])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('team_members')} SET membership_state='left'")
        targets = read_team_selection(str(selected["id"]), 1, str(self.teams[0]))
        self.assertEqual([str(value) for value in self.ids[1:3][::-1]], targets["account_ids"])
        self.assertEqual(0, admin.account_query_count(spec))
