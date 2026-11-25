"""同一列筛选在账号列表和固定名单中的集合对照。"""
from core.accounts import query
from core.storage import admin_repository as admin, records, postgres
from tests.support_pg import PostgresTestCase


class AccountQueryTests(PostgresTestCase):
    def setUp(self):
        records.init()
        for n, (created, archived, promo, status) in enumerate([
            ("2026-09-30T23:59:59", False, "none", "success"),
            ("2026-10-01T00:00:00", False, "none", "success"),
            ("2026-10-31T23:59:59", False, "none", "failed"),
            ("2026-11-01T00:00:00", False, "none", "success"),
            ("2026-10-20T00:00:00", True, "none", "success"),
            ("2026-10-20T00:00:00", False, "free_trial", "success"),
        ]):
            records.insert_row(records.ACCOUNTS, {"email": f"bulk-query-{n}@example.test", "created_at": created,
                "updated_at": created, "archived": archived, "plus_promo_kind": promo,
                "plan_check_status": status, "plan_check_ok": status == "success", "current_plan_type": "free",
                "plan_last_success_at": created, "email_source": "outlook" if n % 2 else "generic_api"})

    def _compare(self, **legacy):
        spec = query.from_legacy(**legacy)
        where, params = query.compile_query(spec)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT a.id FROM {postgres.qualified('registered_accounts')} a WHERE {where} ORDER BY a.id DESC", params)
            ids = [row[0] for row in cur.fetchall()]
        listed = admin.list_accounts(admin.PageRequest(page_size=100, filters=legacy.get("filters", {})),
            **{key: value for key, value in legacy.items() if key != "filters"})
        self.assertEqual(ids, [row["id"] for row in listed["items"]])
        return ids

    def test_october_no_offer_includes_stored_success_after_latest_failure(self):
        ids = self._compare(date_from="2026-10-01", date_to="2026-10-31", filters={"promotion": "none"})
        self.assertEqual(len(ids), 2)

    def test_multi_column_or_and_archive_search_are_shared(self):
        self._compare(archived="all", q="邮箱:bulk-query", filters={"source": "outlook,generic_api", "promotion": "none,free_trial"})
        self._compare(archived="only", filters={"email": "query-4"})

    def test_equivalent_selection_has_stable_hash(self):
        a = {"filters": {"promotion": ["none", "free_trial", "none"]}}
        b = {"filters": {"promotion": ["free_trial", "none"]}}
        self.assertEqual(query.query_hash(a), query.query_hash(b))

    def test_team_filter_shares_list_count_and_facets_without_numeric_discount(self):
        fixtures = [
            ("trial", "outlook", {"plan": "team", "kind": "free_trial", "eligible": True}),
            ("discount", "icloud_hide", {"plan": "team", "kind": "discount", "eligible": True}),
            ("other", "generic_api", {"plan": "team", "kind": "other_promo", "eligible": True}),
            ("half", "outlook", {"plan": "team", "kind": "discount", "eligible": True, "discount_percentage": 50}),
            ("unknown", "outlook", {"plan": "team", "kind": "unknown", "eligible": True}),
            ("none", "outlook", {"plan": "team", "kind": "none", "eligible": True}),
            ("ineligible", "outlook", {"plan": "team", "kind": "free_trial", "eligible": False}),
            ("string-flag", "outlook", {"plan": "team", "kind": "free_trial", "eligible": "true"}),
            ("plus", "outlook", {"plan": "plus", "kind": "discount", "eligible": True, "discount_percentage": 50}),
            ("go", "outlook", {"plan": "go", "kind": "free_trial", "eligible": True, "discount_percentage": 100}),
        ]
        ids = {}
        for name, source, promotion in fixtures:
            ids[name] = records.insert_row(records.ACCOUNTS, {
                "email": f"team-filter-{name}@example.test", "email_source": source,
                "current_plan_type": "plus", "plus_promo_kind": "none",
                "plan_check_status": "success", "account_promotions": [promotion],
            })
        scope = "邮箱:team-filter-"
        for values, expected, sources in (
            (["team_eligible"], {"trial", "discount", "other", "half"},
             {"outlook": 2, "icloud_hide": 1, "generic_api": 1}),
            (["team_eligible", "plus_50"], {"trial", "discount", "other", "half", "plus"},
             {"outlook": 3, "icloud_hide": 1, "generic_api": 1}),
            (["plus_50"], {"plus"}, {"outlook": 1}),
        ):
            with self.subTest(values=values):
                spec = query.normalize_query({"q": scope, "filters": {"promotion": values}})
                selected = self._compare(q=scope, filters={"promotion": ",".join(values)})
                self.assertEqual(set(selected), {ids[name] for name in expected})
                self.assertEqual(admin.account_query_count(spec), len(expected))
                facets = admin.account_query_facets(spec)
                self.assertEqual({item["value"]: item["count"] for item in facets["source"]}, sources)

    def test_bad_query_is_rejected_before_sql(self):
        for raw in ({"order": [{"field": "email;drop table", "direction": "asc"}]},
                    {"date_from": "2026-10-32"}, {"date_from": "2026-11-01", "date_to": "2026-10-01"},
                    {"limit": True}, {"filters": {"password": ["confirmed"]}},
                    {"filters": {"not_a_column": ["x"]}}):
            with self.subTest(raw=raw), self.assertRaises(query.AccountQueryError):
                query.normalize_query(raw)
