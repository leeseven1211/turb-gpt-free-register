# -*- coding: utf-8 -*-
"""Characterize Codex's existing normalized-email LEFT JOIN on real PostgreSQL.

These assertions also apply without the account expression index. In particular,
multiple raw account emails may normalize to one email; they remain separate
joined rows. Ordering within one credential's matching account group is undefined.
"""
import json
import unittest
from collections import Counter
from unittest.mock import patch

import psycopg

from core.storage import admin_repository as repo
from core.storage import records as rs
from tests.support_pg import PostgresTestCase


class CodexJoinSemanticsTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()

    def account(self, email, extra_json=None, **fields):
        return rs.insert_row(rs.ACCOUNTS, {
            "email": email,
            "extra_json": {} if extra_json is None else extra_json,
            **fields,
        })

    def credential(self, filename, email, **fields):
        return rs.insert_row(rs.CODEX_CREDENTIALS, {
            "filename": filename,
            "email": email,
            "plan": "free",
            "oauth_status": "missing",
            "created_at": "2026-10-01T00:00:00Z",
            "updated_at": "2026-10-01T00:00:00Z",
            "mtime": "2026-10-01T00:00:00Z",
            **fields,
        })

    def listing(self, *, page=1, size=100, **filters):
        result = repo.list_codex(repo.PageRequest(page, size, filters))
        self.assertIs(type(result["ok"]), bool)
        self.assertIs(type(result["accounts"]), list)
        self.assertIs(type(result["revision"]), str)
        for key in ("total", "page", "page_size", "offset", "limit"):
            self.assertIs(type(result[key]), int, key)
        self.assertEqual(set(result["summary"]), {"total", "exported", "pending"})
        for value in result["summary"].values():
            self.assertIs(type(value), int)
        for values in result["facets"].values():
            self.assertIs(type(values), list)
            for item in values:
                self.assertEqual(set(item), {"value", "count"})
                self.assertIs(type(item["value"]), str)
                self.assertIs(type(item["count"]), int)
        return result

    @staticmethod
    def identities(rows):
        return Counter((row["filename"], row["sub2api_account_id"]) for row in rows)

    @staticmethod
    def facet_counts(result):
        return {
            name: {item["value"]: item["count"] for item in values}
            for name, values in result["facets"].items()
        }

    def test_empty_database_keeps_empty_facets_and_exact_zero_summary(self):
        for filters in ({}, {"archived": "all"}, {"archived": "only", "q": "absent"}):
            with self.subTest(filters=filters):
                result = self.listing(page=2, size=3, **filters)
                self.assertEqual(result["accounts"], [])
                self.assertEqual(result["total"], 0)
                self.assertEqual(result["facets"], {})
                self.assertEqual(result["summary"], {"total": 0, "exported": 0, "pending": 0})
                self.assertEqual((result["page"], result["page_size"], result["offset"], result["limit"]),
                                 (2, 3, 3, 3))

    def test_credential_receipt_id_is_visible_and_searchable_without_imported_account(self):
        self.credential("receipt.json", "receipt@example.test", sub2api_account_id=321)
        for filters in ({}, {"sub2api_id": "321"}, {"q": "321"}, {"status": "exported"}):
            with self.subTest(filters=filters):
                result = self.listing(**filters)
                self.assertEqual(1, result["total"])
                self.assertEqual(321, result["accounts"][0]["sub2api_account_id"])
                self.assertTrue(result["accounts"][0]["exported"])
                self.assertEqual({"total": 1, "exported": 1, "pending": 0}, result["summary"])
        self.assertEqual(0, self.listing(status="unexported")["total"])

    def test_receipt_id_keeps_distinct_imported_account_targets(self):
        self.account("receipt@example.test", {"sub2api_account_id": 123})
        self.account(" RECEIPT@example.test ", {"sub2api_account_id": 456})
        self.credential("receipt.json", "receipt@example.test", sub2api_account_id=321)
        self.assertEqual({123, 456}, {row["sub2api_account_id"] for row in self.listing()["accounts"]})
        self.assertEqual(1, self.listing(sub2api_id="123")["total"])
        self.assertEqual(1, self.listing(sub2api_id="456")["total"])

    def test_receipt_id_fills_empty_import_metadata(self):
        for index, value in enumerate((None, "", "   ")):
            with self.subTest(value=value):
                self.account(f"empty-{index}@example.test", {"sub2api_account_id": value})
                self.credential(f"empty-{index}.json", f"empty-{index}@example.test", sub2api_account_id=321)
        result = self.listing(sub2api_id="321")
        self.assertEqual(3, result["total"])

    def test_null_blank_and_padded_facets_keep_distinct_raw_groups_after_trim(self):
        for ordinal, (plan, oauth) in enumerate((
            (None, None), ("", ""), (" ", " "), (" PLUS ", " VALID "),
            ("plus", "valid"), ("PLUS", "VALID"),
        )):
            self.credential(f"facet-{ordinal}.json", f"facet-{ordinal}@example.test",
                            plan=plan, oauth_status=oauth)
        expected = {
            "plan": [{"value": "plus", "count": 2}, {"value": "plus", "count": 1}],
            "oauth_status": [{"value": "valid", "count": 2},
                             {"value": "unknown", "count": 1}, {"value": "valid", "count": 1}],
            "status": [{"value": "unexported", "count": 6}],
        }
        for filters, total in (({}, 6), ({"q": "no-matching-row"}, 0)):
            with self.subTest(filters=filters):
                result = self.listing(**filters)
                self.assertEqual(result["total"], total)
                self.assertEqual(result["facets"], expected)
                self.assertEqual(result["summary"], {"total": 6, "exported": 0, "pending": 6})

    def test_count_page_and_complete_global_statistics_use_three_real_sql_queries(self):
        self.account("Exported@example.test", {"sub2api_account_id": 0})
        self.account(" exported@example.test ", json.dumps({"sub2api_account_id": 82}))
        self.credential("exported.json", "exported@example.test", plan="plus", oauth_status="valid")
        self.credential("pending.json", "pending@example.test", plan=None, oauth_status=None)
        self.credential("archived.json", "archived@example.test", plan="team", oauth_status="expired", archived=True)
        expected_facets = {
            "plan": [{"value": "plus", "count": 2}, {"value": "team", "count": 1}],
            "status": [{"value": "exported", "count": 2}, {"value": "archived", "count": 1},
                       {"value": "unexported", "count": 1}],
            "oauth_status": [{"value": "valid", "count": 2}, {"value": "expired", "count": 1},
                             {"value": "unknown", "count": 1}],
        }
        original_execute = psycopg.Cursor.execute
        cases = (({}, 3), ({"archived": "only"}, 1),
                 ({"plan": "plus", "status": "exported", "sub2api_id": "82"}, 1),
                 ({"q": "no-matching-row"}, 0))
        for filters, total in cases:
            with self.subTest(filters=filters):
                executed = []

                def execute(cursor, query, params=None, **kwargs):
                    executed.append((str(query), params))
                    return original_execute(cursor, query, params, **kwargs)

                # Observe actual PostgreSQL execution; do not supply fake result rows.
                with patch.object(psycopg.Cursor, "execute", execute):
                    result = self.listing(size=2, **filters)
                self.assertEqual(result["total"], total)
                self.assertEqual(len(result["accounts"]), min(total, 2))
                self.assertEqual(result["facets"], expected_facets)
                self.assertEqual(result["summary"], {"total": 3, "exported": 2, "pending": 1})
                self.assertEqual(len(executed), 3, "count, page and one complete global statistics query")
                self.assertEqual(tuple(executed[1][1])[-2:], (2, 0))
                self.assertIn(executed[2][1], (None, (), []))

    def test_case_and_space_duplicates_keep_all_object_and_string_metadata_matches(self):
        self.account("Member@example.test", {"sub2api_account_id": 101})
        self.account("member@example.test", json.dumps({"sub2api_account_id": "202"}), archived=True)
        self.account("  MEMBER@example.test  ", {"sub2api_account_id": "remote-member"})
        self.account("unrelated@example.test", {"sub2api_account_id": 999})
        self.credential("member.json", "  mEmBeR@example.test  ", account_id="oauth-member")

        result = self.listing()

        self.assertEqual(result["total"], 3)
        self.assertEqual(self.identities(result["accounts"]), Counter({
            ("member.json", 101): 1,
            ("member.json", 202): 1,
            ("member.json", "remote-member"): 1,
        }))
        self.assertTrue(all(row["account_id"] == "oauth-member" for row in result["accounts"]))
        self.assertTrue(all(row["exported"] for row in result["accounts"]))
        self.assertEqual(result["summary"], {"total": 3, "exported": 3, "pending": 0})

        for selected_id, expected in (("101", 101), ("202", 202), ("remote-member", "remote-member")):
            with self.subTest(sub2api_id=selected_id):
                filtered = self.listing(sub2api_id=selected_id)
                self.assertEqual(filtered["total"], 1)
                self.assertEqual(self.identities(filtered["accounts"]), Counter({("member.json", expected): 1}))

    def test_null_empty_and_space_credential_emails_match_empty_accounts_and_keep_orphans(self):
        # Account email is NOT NULL; NULL belongs to the nullable credential side.
        self.account("", {"sub2api_account_id": 501})
        self.account("   ", json.dumps({"sub2api_account_id": 502}))
        for filename, email in (("null.json", None), ("empty.json", ""), ("space.json", "  ")):
            self.credential(filename, email)
        self.credential("orphan.json", "orphan@example.test")

        result = self.listing()

        expected = Counter({("orphan.json", None): 1})
        for filename in ("null.json", "empty.json", "space.json"):
            expected.update({(filename, 501): 1, (filename, 502): 1})
        self.assertEqual(result["total"], 7)
        self.assertEqual(self.identities(result["accounts"]), expected)
        self.assertEqual(result["summary"], {"total": 7, "exported": 6, "pending": 1})
        orphan = next(row for row in result["accounts"] if row["filename"] == "orphan.json")
        self.assertFalse(orphan["exported"])

    def test_account_archive_does_not_change_credential_archive_scope_or_association(self):
        self.account("archived-account@example.test", {"sub2api_account_id": 601}, archived=True)
        self.account("active-account@example.test", {"sub2api_account_id": 602}, archived=False)
        self.credential("active-credential.json", "archived-account@example.test", archived=False)
        self.credential("archived-credential.json", "active-account@example.test", archived=True)

        for scope, expected in (
            ("0", Counter({("active-credential.json", 601): 1})),
            ("only", Counter({("archived-credential.json", 602): 1})),
            ("all", Counter({("active-credential.json", 601): 1, ("archived-credential.json", 602): 1})),
        ):
            with self.subTest(archived=scope):
                result = self.listing(archived=scope)
                self.assertEqual(result["total"], sum(expected.values()))
                self.assertEqual(self.identities(result["accounts"]), expected)
                self.assertEqual(result["summary"], {"total": 1, "exported": 1, "pending": 0})
                for row in result["accounts"]:
                    self.assertEqual(row["archived"], row["filename"] == "archived-credential.json")

    def test_exported_filters_use_local_count_or_nonblank_sub2_id_including_zero(self):
        cases = (
            ("zero", {"sub2api_account_id": 0}, True),
            ("string", json.dumps({"sub2api_account_id": "702"}), True),
            ("space", {"sub2api_account_id": "   "}, False),
            ("empty", json.dumps({"sub2api_account_id": ""}), False),
            ("null", {"sub2api_account_id": None}, False),
            ("absent", {}, False),
        )
        for name, extra_json, _exported in cases:
            self.account(f"{name}@example.test", extra_json)
            self.credential(f"{name}.json", f"{name}@example.test")
        self.credential("downloaded-orphan.json", "no-account@example.test", exported_count=2)
        expected_exported = {"zero.json", "string.json", "downloaded-orphan.json"}
        expected_pending = {f"{name}.json" for name, _extra, exported in cases if not exported}

        all_rows = self.listing()
        self.assertEqual(all_rows["total"], 7)
        self.assertEqual({row["filename"] for row in all_rows["accounts"] if row["exported"]}, expected_exported)
        self.assertEqual(next(row for row in all_rows["accounts"] if row["filename"] == "zero.json")["sub2api_account_id"], 0)
        for status, expected in (("exported", expected_exported), ("unexported", expected_pending)):
            with self.subTest(status=status):
                result = self.listing(status=status)
                self.assertEqual(result["total"], len(expected))
                self.assertEqual({row["filename"] for row in result["accounts"]}, expected)
                self.assertEqual(result["summary"], {"total": 7, "exported": 3, "pending": 4})

    def test_facets_are_global_and_summary_is_active_even_with_combined_or_empty_filters(self):
        self.account("Duplicate@example.test", {"sub2api_account_id": 101})
        self.account(" duplicate@example.test ", json.dumps({"sub2api_account_id": 202}))
        self.credential(
            "duplicate.json", "duplicate@example.test", plan="plus", account_id="oauth-shared",
            oauth_status="valid", oauth_expires_at="2099-01-01T00:00:00Z",
            expired="2099-01-01T00:00:00Z", access_token_preview="fixture-present",
            mtime="2026-10-20T12:00:00Z",
        )
        self.credential("pending.json", "pending@example.test", plan="free")
        self.credential("archived.json", "archived@example.test", plan="team", oauth_status="expired", archived=True)
        expected_facets = {
            "plan": {"plus": 2, "free": 1, "team": 1},
            "status": {"exported": 2, "unexported": 1, "archived": 1},
            "oauth_status": {"valid": 2, "missing": 1, "expired": 1},
        }
        expected_summary = {"total": 3, "exported": 2, "pending": 1}
        cases = (
            ({"archived": "all"}, 4),
            ({"archived": "only"}, 1),
            ({"archived": "0", "q": "duplicate", "plan": "plus", "status": "exported",
              "oauth_status": "valid", "account_id": "oauth-shared", "sub2api_id": "202",
              "date_from": "2026-10-20", "date_to": "2026-10-20", "expired_date": "2099-01-01"}, 1),
            ({"archived": "0", "q": "no-matching-record"}, 0),
        )
        for filters, total in cases:
            with self.subTest(filters=filters):
                result = self.listing(**filters)
                self.assertEqual(result["total"], total)
                self.assertEqual(len(result["accounts"]), total)
                self.assertEqual(self.facet_counts(result), expected_facets)
                self.assertEqual(result["summary"], expected_summary)
        self.assertEqual(repo.dashboard_aggregates()["codex"], expected_summary)

    def test_sorting_and_page_boundaries_count_joined_rows_without_ordering_account_ties(self):
        for email, sub2_id in (("Newest@example.test", 801), ("newest@example.test", 802), (" newest@example.test ", 803)):
            self.account(email, {"sub2api_account_id": sub2_id})
        self.credential("middle-first.json", "first@example.test", mtime="2026-10-10T00:00:00Z")
        self.credential("middle-second.json", "second@example.test", mtime="2026-10-10T00:00:00Z")
        self.credential("newest.json", "NEWEST@example.test", mtime="2026-10-20T00:00:00Z")
        # Inserted last, but its fallback updated_at is older than both middle rows.
        self.credential("oldest.json", "oldest@example.test", mtime=None)

        all_rows = self.listing()
        expected_names = ["newest.json"] * 3 + ["middle-second.json", "middle-first.json", "oldest.json"]
        self.assertEqual(all_rows["total"], 6)
        self.assertEqual([row["filename"] for row in all_rows["accounts"]], expected_names)
        expected_newest = Counter({("newest.json", value): 1 for value in (801, 802, 803)})
        self.assertEqual(self.identities(all_rows["accounts"][:3]), expected_newest)

        # Group-aligned page verifies all linked values without specifying tie order.
        first_group = self.listing(size=3)
        self.assertEqual(self.identities(first_group["accounts"]), expected_newest)
        # Split the group across pages: only credential order/cardinality is stable.
        for page in (1, 2, 3, 4):
            with self.subTest(page=page):
                result = self.listing(page=page, size=2)
                self.assertEqual(result["total"], 6)
                self.assertEqual(result["offset"], (page - 1) * 2)
                self.assertEqual(result["page_size"], 2)
                self.assertEqual([row["filename"] for row in result["accounts"]], expected_names[(page - 1) * 2:page * 2])
                newest = [row for row in result["accounts"] if row["filename"] == "newest.json"]
                self.assertEqual(len({row["sub2api_account_id"] for row in newest}), len(newest))
                self.assertTrue(all(row["sub2api_account_id"] in {801, 802, 803} for row in newest))

    def test_public_list_http_response_does_not_expose_credential_or_account_secrets(self):
        from webui.app import create_app

        secrets = {key: f"synthetic-private-{key}" for key in ("access_token", "refresh_token", "id_token", "password")}
        self.account("safe@example.test", {"sub2api_account_id": 901, **secrets}, **secrets)
        self.credential(
            "safe.json", "SAFE@example.test", content={"email": "safe@example.test", **secrets},
            access_token_preview=secrets["access_token"], oauth_refreshable=True, **secrets,
        )
        client = create_app(auth_code="codex-join-test").test_client()
        response = client.get("/api/codex?paged=1&archived=0&page_size=20", headers={"X-Auth-Code": "codex-join-test"})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["accounts"][0]["sub2api_account_id"], 901)
        self.assertEqual(result["accounts"][0]["access_token_preview"], "已保存")
        self.assertTrue(result["accounts"][0]["oauth_refreshable"])
        for key in ("content", "data", "extra_json", *secrets):
            self.assertNotIn(key, result["accounts"][0])
        payload = response.get_data(as_text=True)
        for secret in secrets.values():
            self.assertNotIn(secret, payload)


class CodexStatisticsDecodeTests(unittest.TestCase):
    @staticmethod
    def total_row():
        return {"grouping_mask": 7, "plan_value": None, "status_value": None, "oauth_value": None,
                "count": 9, "active_total": 6, "active_exported": 2}

    def test_incomplete_or_unrecognized_grouping_result_cannot_be_reported_as_zero(self):
        decoder = getattr(repo, "_decode_codex_statistics", None)
        self.assertTrue(callable(decoder), "Codex global statistics need a validated decoder")
        for rows in ([], [self.total_row(), self.total_row()],
                     [{**self.total_row(), "grouping_mask": 0}],
                     [self.total_row(), {"grouping_mask": 1}]):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                decoder(rows)


if __name__ == "__main__":
    unittest.main()
