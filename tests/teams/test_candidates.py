"""候选集合搜索、归档及明确粘贴解析。"""
from tests.support_pg import PostgresTestCase


class CandidateTests(PostgresTestCase):
    def setUp(self):
        from core.storage import records
        from core.storage.teams import repository
        repository.init()
        self.ids = self.seed(records.ACCOUNTS, [
            {"email": "active@example.test", "password": "test-password"},
            {"email": "archived@example.test", "archived": True},
            {"email": "duplicate@example.test"},
            {"email": "DUPLICATE@example.test"},
        ])

    def test_default_candidates_exclude_archived_but_resolve_keeps_it(self):
        from core.teams.queries import candidates, resolve
        from core.storage.teams import repository
        with repository.transaction() as conn:
            result = candidates(999, {"page": 1, "page_size": 20}, conn=conn)
            self.assertEqual(3, result["total"])
            resolved = resolve(999, [str(self.ids[1]), str(self.ids[1])], conn=conn)
        self.assertEqual(2, resolved["requested_count"])
        self.assertEqual(1, resolved["unique_count"])
        self.assertTrue(resolved["items"][0]["candidates"][0]["account"]["archived"])

    def test_email_multiple_matches_are_ambiguous_and_unknown_auth_is_selectable(self):
        from core.teams.queries import resolve
        from core.storage.teams import repository
        with repository.transaction() as conn:
            result = resolve(999, ["DUPLICATE@example.test", "missing@example.test"], conn=conn)
        self.assertEqual("ambiguous", result["items"][0]["match_status"])
        self.assertEqual(2, len(result["items"][0]["candidates"]))
        self.assertTrue(all(not item["disabled"] for item in result["items"][0]["candidates"]))
        self.assertEqual("not_found", result["items"][1]["match_status"])

    def test_later_imported_account_is_not_unassigned_when_remote_invite_has_its_email(self):
        from core.teams.queries import candidates
        from core.storage import postgres
        from core.storage.teams import repository
        with repository.transaction() as conn:
            conn.execute(
                f"INSERT INTO {postgres.qualified('team_workspaces')}"
                "(workspace_id,manager_account_id) VALUES ('test-existing-team',%s) RETURNING id",
                (self.ids[0],),
            )
            team_id = conn.execute(
                f"SELECT id FROM {postgres.qualified('team_workspaces')} WHERE workspace_id='test-existing-team'"
            ).fetchone()["id"]
            conn.execute(
                f"INSERT INTO {postgres.qualified('team_invitations')}"
                "(team_id,target_key,email_snapshot,invitation_state,active)"
                " VALUES (%s,'remote:one','archived@example.test','pending',false)",
                (team_id,),
            )
            result = candidates(999, {"scope": "unassigned", "archived": "all"}, conn=conn)
        self.assertNotIn(str(self.ids[1]), [item["account"]["id"] for item in result["items"]])
