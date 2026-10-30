# -*- coding: utf-8 -*-
import json
import unittest

from core.storage import admin_repository as repo
from core import db
from core.storage import records as rs
from tests.support_pg import PostgresTestCase


class _QueryCounter:
    def __init__(self):
        self.count = 0
        self.queries = []

    def __enter__(self):
        import psycopg
        self._original = psycopg.Cursor.execute
        counter = self

        def execute(cursor, query, params=None, **kwargs):
            counter.count += 1
            counter.queries.append(str(query))
            return counter._original(cursor, query, params, **kwargs)

        psycopg.Cursor.execute = execute
        return self

    def __exit__(self, *_exc):
        import psycopg
        psycopg.Cursor.execute = self._original
        return False


class AdminRepositoryTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.account_ids = []
        for index in range(30):
            self.account_ids.append(rs.insert_row(rs.ACCOUNTS, {
                "email": f"user{index}@example.test",
                "email_source": "icloud_hide" if index % 2 else "outlook",
                "current_plan_type": "plus" if index % 3 == 0 else "free",
                "plan_check_status": "success",
                "plus_promo_kind": "free_trial" if index % 4 == 0 else "none",
                "plus_trial_eligible": index % 4 == 0,
                "codex_status": "success" if index % 2 else "failed",
                "access_token": f"token-{index}" if index % 2 else "",
                "totp_secret": "totp" if index % 2 else "",
                "password": "password" if index % 2 else "",
            }))
        for index in range(45):
            rs.insert_row(rs.JOBS, {
                "job_uuid": f"job-{index}",
                "email": f"user{index % 30}@example.test",
                "account_id": self.account_ids[index % 30] if index % 2 else None,
                "root_job_id": index + 1,
                "status": "failed" if index % 2 else "success",
                "email_source": "icloud_hide",
                "batch_id": "latest-batch" if index >= 40 else "older-batch",
                "batch_index": index,
            })
        rs.insert_row(rs.OUTLOOK_POOL, {"email": "pool1@example.test", "status": "available", "password": "secret"})
        rs.insert_row(rs.DOMAIN_POOL, {"email": "pool2@example.test", "status": "used", "code_url": "https://secret.test"})
        rs.insert_row(rs.ICLOUD_HIDE_POOL, {"email": "pool3@example.test", "status": "available", "account_id": "hme-1"})
        db.save_codex_credential_record(
            "codex-user1.json",
            {"email": "user1@example.test", "type": "codex", "access_token": "secret-token"},
        )

    def test_accounts_are_filtered_and_paginated_in_repository(self):
        result = repo.list_accounts(
            repo.PageRequest(page=2, page_size=7, filters={"source": "icloud_hide"}),
            archived="0",
        )
        self.assertEqual(result["total"], 15)
        self.assertEqual(len(result["items"]), 7)
        self.assertTrue(result["revision"])
        self.assertIn("source", result["facets"])
        self.assertTrue(all(item["email_source"] == "icloud_hide" for item in result["items"]))

    def test_account_query_matches_registration_driver_and_safe_display_fields(self):
        protocol_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "protocol-search@example.test",
            "email_source": "protocol-source",
            "user_name": "协议用户",
            "note": "协议注册样本",
        })
        roxy_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "roxy-search@example.test",
            "email_source": "outlook",
            "user_name": "浏览器用户",
            "note": "Roxy 样本",
        })
        open_source_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "open-source-search@example.test",
            "email_source": "outlook",
            "user_name": "开源用户",
            "note": "开源协议样本",
        })
        rs.insert_row(rs.ACCOUNTS, {
            "email": "contains-protocol@example.test",
            "email_source": "outlook",
        })
        rs.insert_row(rs.JOBS, {
            "job_uuid": "driver-protocol-search",
            "email": "protocol-search@example.test",
            "account_id": protocol_id,
            "job_type": "registration",
            "data": {"config_snapshot": {"registration_driver": "protocol"}},
        })
        rs.insert_row(rs.JOBS, {
            "job_uuid": "driver-roxy-search",
            "email": "roxy-search@example.test",
            "account_id": roxy_id,
            "job_type": "registration",
            "data": {"config_snapshot": {"registration_driver": "roxy"}},
        })
        rs.insert_row(rs.JOBS, {
            "job_uuid": "driver-protocol-oss-search",
            "email": "open-source-search@example.test",
            "account_id": open_source_id,
            "job_type": "registration",
            "data": {"config_snapshot": {"registration_driver": "protocol_oss"}},
        })

        for query in ("protocol", "协议注册"):
            with self.subTest(query=query):
                result = repo.list_accounts(repo.PageRequest(page=1, page_size=20), q=query)
                self.assertEqual(result["total"], 1)
                self.assertEqual(result["items"][0]["id"], protocol_id)

        for query in ("roxy", "浏览器"):
            with self.subTest(query=query):
                result = repo.list_accounts(repo.PageRequest(page=1, page_size=20), q=query)
                self.assertEqual(result["total"], 1)
                self.assertEqual(result["items"][0]["id"], roxy_id)

        for query in ("开源协议", "开源协议注册", "方式:protocol_oss"):
            with self.subTest(query=query):
                result = repo.list_accounts(repo.PageRequest(page=1, page_size=20), q=query)
                self.assertEqual(result["total"], 1)
                self.assertEqual(result["items"][0]["id"], open_source_id)

        for query, expected in (
            (str(protocol_id), protocol_id),
            ("协议用户", protocol_id),
            ("protocol-source", protocol_id),
            ("协议注册样本", protocol_id),
        ):
            with self.subTest(query=query):
                result = repo.list_accounts(repo.PageRequest(page=1, page_size=20), q=query)
                self.assertEqual(result["total"], 1)
                self.assertEqual(result["items"][0]["id"], expected)

        # 轻量状态接口必须沿用相同的账号搜索条件。
        status = repo.list_account_statuses(repo.PageRequest(page=1, page_size=20), q="protocol")
        self.assertEqual(status["total"], 1)
        self.assertEqual(status["items"][0]["id"], protocol_id)

    def test_account_registration_driver_projects_metadata_then_latest_registration_job(self):
        expected = {}
        for name, metadata, drivers, driver in (
            ("top-level", {"registration_driver": " ROXY ", "extra_json": {"registration_driver": "protocol"}}, ["protocol_oss"], "roxy"),
            ("extra-object", {"extra_json": {"registration_driver": "roxy_oss", "account_password": "private-value"}}, ["protocol"], "roxy_oss"),
            ("extra-string", {"extra_json": json.dumps({"registration_driver": "protocol_oss", "account_password": "private-value"})}, [], "protocol_oss"),
            ("latest-job", {}, ["protocol", "protocol_oss_2"], "protocol_oss_2"),
            ("invalid-extra", {"extra_json": "{invalid-json"}, ["protocol"], "protocol"),
            ("unknown", {}, [], None),
            ("latest-unknown", {}, ["protocol", None], None),
        ):
            account_id = rs.insert_row(rs.ACCOUNTS, {"email": f"driver-{name}@example.test", **metadata})
            expected[account_id] = driver
            for index, job_driver in enumerate(drivers):
                rs.insert_row(rs.JOBS, {
                    "job_uuid": f"driver-projection-{name}-{index}", "account_id": account_id,
                    "job_type": "registration_resume" if index else "registration",
                    "data": {"config_snapshot": {"registration_driver": job_driver}},
                })
            rs.insert_row(rs.JOBS, {
                "job_uuid": f"driver-projection-{name}-non-registration", "account_id": account_id,
                "job_type": "account_setup", "data": {"config_snapshot": {"registration_driver": "roxy"}},
            })

        result = repo.list_accounts(repo.PageRequest(page_size=500))
        projected = {row["id"]: row for row in result["items"] if row["id"] in expected}
        self.assertEqual(set(projected), set(expected))
        for account_id, driver in expected.items():
            with self.subTest(account_id=account_id):
                row = projected[account_id]
                self.assertEqual(row.get("registration_driver"), driver)
                self.assertNotIn("extra_json", row)
                self.assertNotIn("private-value", json.dumps(row))

    def test_account_query_does_not_scan_arbitrary_json_or_credentials(self):
        rs.insert_row(rs.ACCOUNTS, {
            "email": "safe-fields-only@example.test",
            "access_token": "credential-only-marker",
            "secret_marker": "private-json-marker",
        })

        for query in ("credential-only-marker", "private-json-marker"):
            with self.subTest(query=query):
                result = repo.list_accounts(repo.PageRequest(page=1, page_size=20), q=query)
                self.assertEqual(result["total"], 0)

    def test_combined_account_search_uses_historical_method_and_country(self):
        account_ids = {}
        for name, driver, region in (
            ("protocol-jp", "protocol", "JP"),
            ("protocol-us", "protocol", "US"),
            ("browser-jp", "roxy", "JP"),
            ("missing-country", "protocol", None),
            ("missing-method", None, "JP"),
        ):
            account_id = rs.insert_row(rs.ACCOUNTS, {
                "email": f"{name}@search.test", "email_source": "outlook",
                "registration_proxy_region": region, "note": "协议 jp 待整理",
            })
            account_ids[name] = account_id
            if driver:
                rs.insert_row(rs.JOBS, {
                    "job_uuid": f"search-{name}", "account_id": account_id,
                    "job_type": "registration", "data": {"config_snapshot": {"registration_driver": driver}},
                })
        for query, expected in (
            ("协议 jp", "protocol-jp"), ("协议/jp注册", "protocol-jp"),
            ("方式:协议 地区:日本", "protocol-jp"), ("浏览器 JP", "browser-jp"),
            ("协议 jp 备注:待整理 邮箱:search.test 来源:outlook", "protocol-jp"),
        ):
            for query_fn in (repo.list_accounts, repo.list_account_statuses):
                with self.subTest(query=query, endpoint=query_fn.__name__):
                    result = query_fn(repo.PageRequest(page_size=1), q=query)
                    self.assertEqual(result["total"], 1)
                    self.assertEqual(result["items"][0]["id"], account_ids[expected])

    def test_combined_account_search_keeps_pagination_archive_and_column_filters(self):
        expected = []
        for index in range(4):
            account_id = rs.insert_row(rs.ACCOUNTS, {
                "email": f"page-{index}@search.test", "email_source": "outlook" if index < 3 else "icloud_hide",
                "registration_proxy_region": "JP", "archived": index == 2,
            })
            rs.insert_row(rs.JOBS, {
                "job_uuid": f"search-page-{index}", "account_id": account_id,
                "data": {"config_snapshot": {"registration_driver": "protocol"}},
            })
            if index < 2:
                expected.append(account_id)
        for query_fn in (repo.list_accounts, repo.list_account_statuses):
            pages = [query_fn(repo.PageRequest(page=page, page_size=1, filters={"source": "outlook"}), q="协议/jp") for page in (1, 2)]
            self.assertEqual([result["total"] for result in pages], [2, 2])
            self.assertEqual({result["items"][0]["id"] for result in pages}, set(expected))

    def test_scoped_account_search_preserves_literal_text_and_field_boundaries(self):
        target = rs.insert_row(rs.ACCOUNTS, {
            "email": "literal@search.test", "user_name": "Alice Smith", "note": "jp a/b 100% ready_one",
        })
        rs.insert_row(rs.ACCOUNTS, {
            "email": "jp@search.test", "user_name": "Alice Jones", "note": "a b 1000 readyXone",
            "access_token": "credential-only-marker",
        })
        for query in ('备注:jp', '姓名:"Alice Smith"', '备注:"a/b"', '备注:100%', '备注:ready_one', f'ID:{target}', '"jp" 姓名:Smith'):
            with self.subTest(query=query):
                result = repo.list_accounts(repo.PageRequest(), q=query)
                self.assertEqual([row["id"] for row in result["items"]], [target])
        for query in ('备注:credential-only-marker', '邮箱:jp 姓名:Smith'):
            self.assertEqual(repo.list_accounts(repo.PageRequest(), q=query)["total"], 0)

    def test_registration_query_uses_latest_registration_attempt_driver(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "driver-history@example.test",
        })
        rs.insert_row(rs.JOBS, {
            "job_uuid": "driver-history-protocol",
            "email": "driver-history@example.test",
            "account_id": account_id,
            "job_type": "registration",
            "data": {"config_snapshot": {"registration_driver": "protocol"}},
        })
        rs.insert_row(rs.JOBS, {
            "job_uuid": "driver-history-roxy",
            "email": "driver-history@example.test",
            "account_id": account_id,
            "job_type": "registration_resume",
            "data": {"config_snapshot": {"registration_driver": "roxy"}},
        })

        protocol = repo.list_accounts(repo.PageRequest(page=1, page_size=20), q="protocol")
        roxy = repo.list_accounts(repo.PageRequest(page=1, page_size=20), q="roxy")
        self.assertNotIn(account_id, {item["id"] for item in protocol["items"]})
        self.assertIn(account_id, {item["id"] for item in roxy["items"]})

    def test_account_list_does_not_return_full_chatgpt_session(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "session-hidden@example.test",
            "chatgpt_session": json.dumps({"accessToken": "session-token"}),
        })

        result = repo.list_accounts(repo.PageRequest(page=1, page_size=100, filters={}))
        item = next(row for row in result["items"] if row["id"] == account_id)
        self.assertNotIn("chatgpt_session", item)

    def test_compact_status_bounds_payload_and_clears_removed_state(self):
        promotion = {"plan": "plus", "kind": "discount", "discount_percentage": 50,
                     "campaign_id": "campaign", "stale": True, "summary": "详情" * 1500,
                     "checkout_status": "success", "payment_method_types": ["card"]}
        countries = [{"country": country, "status": "success", "result": {
            "account_promotions": [promotion], "promotion_query_snapshot": {"raw": "x" * 20000}}}
            for country in ("US", "IN", "JP", "GB", "CA", "AU", "DE", "FR", "BR", "MX")]
        for index in range(10):
            rs.insert_row(rs.ACCOUNTS, {"email": f"compact{index}@example.test",
                "plan_check_status": "success", "account_promotions": [promotion],
                "plan_check_countries": ["US", "IN", "JP"], "plan_check_country_results": countries})
        result = repo.list_account_statuses(repo.PageRequest(1, 10, {}), compact=True)
        self.assertLess(len(json.dumps(result).encode()), 20000)
        item = result["items"][0]
        self.assertNotIn("account_promotions", item)
        self.assertNotIn("plan_check_country_results", item)
        self.assertEqual(item["plan_summary"]["countries"][1]["country"], "IN")
        self.assertEqual(item["plan_summary"]["countries"][1]["promotions"][0]["discount_percentage"], 50)
        self.assertTrue(item["plan_details_revision"])
        self.assertIs(item["plan_summary"]["promotions"][0]["stale"], True)
        rs.patch_row(rs.ACCOUNTS, item["id"], {"account_promotions": [], "plan_check_countries": [],
            "plan_check_country_results": [], "plan_check_error": None, "extract_link_error": None})
        refreshed = repo.list_account_statuses(repo.PageRequest(1, 10, {}), compact=True)["items"][0]
        self.assertEqual(refreshed["plan_summary"], {"promotions": [], "countries": []})
        self.assertIsNone(refreshed["plan_check_error"])
        self.assertIsNone(refreshed["extract_link_error"])
        self.assertNotEqual(item["plan_details_revision"], refreshed["plan_details_revision"])

    def test_account_promotions_are_returned_by_list_and_status_projection(self):
        promotions = [{
            "plan": "go", "kind": "free_trial", "eligible": True,
            "campaign_id": "go-free-1-month", "summary": "免费1个月",
        }, {
            "plan": "plus", "kind": "discount", "eligible": True,
            "campaign_id": "plus-50-off-1-month", "summary": "50%折扣1个月",
        }]
        snapshot = {
            "version": 1,
            "source": "accounts_check",
            "eligible_promo_campaigns": {
                "go": {"campaign_id": "go-free-1-month"},
                "plus": {"campaign_id": "plus-50-off-1-month"},
            },
        }
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "promotion-query@example.test",
            "account_promotions": promotions,
            "promotion_query_snapshot": snapshot,
        })

        for query in (repo.list_accounts, repo.list_account_statuses):
            with self.subTest(query=query.__name__):
                result = query(repo.PageRequest(page=1, page_size=100))
                item = next(row for row in result["items"] if row["id"] == account_id)
                self.assertEqual(item["account_promotions"], promotions)
                self.assertEqual(item["promotion_query_snapshot"], snapshot)

    def test_status_projection_keeps_explicitly_empty_promotions(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "promotion-empty@example.test",
            "account_promotions": [],
            "promotion_query_snapshot": {
                "version": 1, "source": "accounts_check", "eligible_promo_campaigns": {},
            },
        })

        result = repo.list_account_statuses(repo.PageRequest(page=1, page_size=100))
        item = next(row for row in result["items"] if row["id"] == account_id)

        self.assertEqual(item["account_promotions"], [])
        self.assertEqual(item["promotion_query_snapshot"]["eligible_promo_campaigns"], {})

    def test_accounts_can_filter_and_report_account_status(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "deactivated@example.test",
            "account_status": "deactivated",
            "account_status_reason": "account_deactivated",
        })

        result = repo.list_accounts(
            repo.PageRequest(page=1, page_size=20, filters={"account_status": "deactivated"}),
            archived="0",
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["id"], account_id)
        self.assertEqual(result["items"][0]["account_status"], "deactivated")
        self.assertEqual(
            {item["value"] for item in result["facets"]["account_status"]},
            {"active", "deactivated"},
        )
        status_snapshot = repo.list_account_statuses(repo.PageRequest(page=1, page_size=50))
        status_item = next(item for item in status_snapshot["items"] if item["id"] == account_id)
        self.assertEqual(status_item["account_status"], "deactivated")

    def test_job_page_has_constant_query_count(self):
        with _QueryCounter() as counter:
            result = repo.list_jobs(repo.PageRequest(page=1, page_size=20, filters={}))
        self.assertEqual(result["total"], 45)
        self.assertEqual(len(result["items"]), 20)
        self.assertLessEqual(counter.count, 8, counter.count)
        self.assertEqual(result["progress_rows"][-1]["batch_id"], "latest-batch")
        self.assertEqual([batch["batch_id"] for batch in result["progress_batches"][:2]], ["latest-batch", "older-batch"])

    def test_job_progress_can_select_an_older_batch(self):
        result = repo.list_jobs(
            repo.PageRequest(page=1, page_size=20, filters={}),
            progress_batch_id="older-batch",
        )

        self.assertEqual(len(result["progress_rows"]), 40)
        self.assertTrue(all(row["batch_id"] == "older-batch" for row in result["progress_rows"]))
        older = next(batch for batch in result["progress_batches"] if batch["batch_id"] == "older-batch")
        self.assertEqual(older["total"], 40)
        self.assertEqual(older["kind"], "registration")

    def test_job_batch_view_skips_table_and_facets_but_counts_global_active_jobs(self):
        rs.insert_row(rs.JOBS, {
            "job_uuid": "active-other-batch", "status": "running", "batch_id": "other-batch",
        })
        with _QueryCounter() as counter:
            result = repo.list_jobs(
                repo.PageRequest(filters={"status": "success"}),
                progress_batch_id="older-batch", view="batch",
            )

        self.assertEqual([], result["items"])
        self.assertEqual({}, result["facets"])
        self.assertEqual(1, result["status_counts"]["active"])
        self.assertEqual(40, len(result["progress_rows"]))
        self.assertTrue(all(row["batch_id"] == "older-batch" for row in result["progress_rows"]))
        self.assertFalse(any("AS facet" in query or "OFFSET" in query for query in counter.queries))
        self.assertTrue(all("items" not in batch and "progress" not in batch for batch in result["progress_batches"]))

    def test_job_table_view_skips_batch_queries(self):
        with _QueryCounter() as counter:
            result = repo.list_jobs(repo.PageRequest(page_size=7), view="table")

        self.assertEqual(45, result["total"])
        self.assertEqual(7, len(result["items"]))
        self.assertEqual([], result["progress_rows"])
        self.assertEqual([], result["progress_batches"])
        self.assertFalse(any("effective_batch_id" in query for query in counter.queries))

    def test_job_batch_summary_uses_active_slot_and_keeps_latest_retry_metadata(self):
        root_id = rs.insert_row(rs.JOBS, {
            "job_uuid": "active-slot-root", "batch_id": "active-slot", "status": "running",
        })
        retry_id = rs.insert_row(rs.JOBS, {
            "job_uuid": "active-slot-retry", "batch_id": "legacy-retry", "status": "failed",
            "parent_job_id": root_id, "root_job_id": root_id, "retry_attempt": 1,
        })
        result = repo.list_jobs(repo.PageRequest(), progress_batch_id="active-slot", view="batch")
        batch = next(batch for batch in result["progress_batches"] if batch["batch_id"] == "active-slot")

        self.assertEqual(1, batch["total"])
        self.assertEqual(1, batch["status_counts"]["active"])
        self.assertEqual(0, batch["status_counts"]["failed"])
        self.assertEqual(retry_id, batch["latest_job_id"])
        self.assertTrue(batch["has_retries"])

    def test_job_batch_view_returns_empty_for_missing_or_empty_batch(self):
        missing = repo.list_jobs(repo.PageRequest(), progress_batch_id="missing", view="batch")
        self.assertEqual([], missing["progress_rows"])
        rs.delete_rows(rs.JOBS, [row["id"] for row in rs.list_rows(rs.JOBS)])
        empty = repo.list_jobs(repo.PageRequest(), view="batch")
        self.assertEqual([], empty["progress_rows"])
        self.assertEqual([], empty["progress_batches"])

    def test_email_pool_is_unified_and_does_not_return_secrets(self):
        result = repo.list_email_pool(repo.PageRequest(page=1, page_size=20, filters={"source": "all"}))
        self.assertEqual(result["total"], 3)
        self.assertEqual({row["source"] for row in result["items"]}, {"outlook", "cloudflare_domain", "icloud_hide"})
        for row in result["items"]:
            self.assertNotIn("password", row)
            self.assertNotIn("code_url", row)

    def test_email_pool_exposes_usage_and_resource_metadata_without_account_token(self):
        rs.insert_row(rs.OUTLOOK_POOL, {
            "email": "user0@example.test",
            "status": "used",
            "password": "mail-password",
            "client_id": "client-id",
            "refresh_token": "refresh-secret",
        })

        result = repo.list_email_pool(repo.PageRequest(page=1, page_size=20, filters={"source": "outlook"}))
        item = next(row for row in result["items"] if row["email"] == "user0@example.test")

        self.assertEqual(item["usage_state"], "bound")
        self.assertEqual(item["registered_account_id"], self.account_ids[0])
        self.assertEqual(item["resource_meta"], {
            "password": True,
            "client_id": True,
            "refresh_token": True,
            "code_url": False,
        })
        self.assertEqual(item["linked_account_status"], "active")
        self.assertNotIn("has_access_token", item)
        self.assertNotIn("refresh_token", item)
        self.assertNotIn("account_copy_line", item)

    def test_email_pool_can_filter_replaced_mailboxes(self):
        rs.insert_row(rs.OUTLOOK_POOL, {
            "email": "changed@example.test",
            "status": "replaced",
            "note": "邮箱已换绑，原邮箱不再使用",
        })

        result = repo.list_email_pool(
            repo.PageRequest(
                page=1,
                page_size=20,
                filters={"source": "outlook", "status": "replaced"},
            )
        )

        self.assertEqual(1, result["total"])
        self.assertEqual("changed@example.test", result["items"][0]["email"])
        self.assertEqual("replaced", result["items"][0]["status"])
        self.assertIn("replaced", {item["value"] for item in result["facets"]["status"]})

    def test_codex_list_uses_relational_table_and_hides_content(self):
        result = repo.list_codex(repo.PageRequest(page=1, page_size=20, filters={"archived": "0"}))
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["summary"], {"total": 1, "exported": 0, "pending": 1})
        self.assertNotIn("content", result["accounts"][0])
        self.assertEqual(result["accounts"][0]["access_token_preview"], "已保存")

    def test_codex_list_shows_deactivated_account_over_token_expiry(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "dead-list@example.test",
            "account_status": "deactivated",
            "account_status_reason": "account_deactivated",
        })
        db.save_codex_credential_record(
            "codex-dead-list@example.test-free.json",
            {
                "email": "dead-list@example.test",
                "type": "codex",
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expired": "2099-01-01T00:00:00Z",
            },
        )

        result = repo.list_codex(
            repo.PageRequest(page=1, page_size=20, filters={"archived": "0"})
        )

        item = next(row for row in result["accounts"] if row["email"] == "dead-list@example.test")
        self.assertEqual("deactivated", item["oauth_status"])
        self.assertTrue(item["oauth_reauth_required"])

    def test_codex_list_exposes_and_filters_sub2api_id_from_account_metadata(self):
        db.save_codex_credential_record(
            "codex-user2.json",
            {"email": "user2@example.test", "type": "codex", "access_token": "secret-token-2"},
        )
        rs.patch_row(
            rs.ACCOUNTS,
            self.account_ids[1],
            {"extra_json": json.dumps({"sub2api_account_id": 77})},
        )
        rs.patch_row(
            rs.ACCOUNTS,
            self.account_ids[2],
            {"extra_json": json.dumps({"sub2api_account_id": 145})},
        )

        listing = repo.list_codex(
            repo.PageRequest(page=1, page_size=20, filters={"archived": "0", "sub2api_id": "77"})
        )

        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["accounts"][0]["sub2api_account_id"], 77)

    def test_codex_list_treats_sub2api_link_as_exported_without_local_download(self):
        filename = "codex-user3.json"
        db.save_codex_credential_record(
            filename,
            {"email": "user3@example.test", "type": "codex", "access_token": "secret-token-3"},
        )
        rs.patch_row(
            rs.ACCOUNTS,
            self.account_ids[3],
            {"extra_json": json.dumps({"sub2api_account_id": 207})},
        )

        exported = repo.list_codex(
            repo.PageRequest(page=1, page_size=20, filters={"archived": "0", "status": "exported"})
        )
        linked = next(row for row in exported["accounts"] if row["filename"] == filename)
        self.assertTrue(linked["exported"])
        self.assertEqual(linked["exported_count"], 0)
        self.assertEqual(linked["sub2api_account_id"], 207)
        self.assertEqual(exported["summary"], {"total": 2, "exported": 1, "pending": 1})
        self.assertEqual(
            {item["value"] for item in exported["facets"]["status"]},
            {"exported", "unexported"},
        )

        unexported = repo.list_codex(
            repo.PageRequest(page=1, page_size=20, filters={"archived": "0", "status": "unexported"})
        )
        self.assertNotIn(filename, {row["filename"] for row in unexported["accounts"]})

    def test_dashboard_codex_summary_counts_sub2api_link_as_exported(self):
        db.save_codex_credential_record(
            "codex-user4.json",
            {"email": "user4@example.test", "type": "codex", "access_token": "secret-token-4"},
        )
        rs.patch_row(
            rs.ACCOUNTS,
            self.account_ids[4],
            {"extra_json": json.dumps({"sub2api_account_id": 308})},
        )

        result = repo.dashboard_aggregates()

        self.assertEqual(result["codex"], {"total": 2, "exported": 1, "pending": 1})

    def test_jobs_poll_skips_facets_without_changing_rows(self):
        request = repo.PageRequest(1, 10, {})
        before = repo.list_jobs(request, view="table")
        with _QueryCounter() as counter:
            after = repo.list_jobs(request, view="table", include_facets=False)
        self.assertEqual([row["id"] for row in before["items"]], [row["id"] for row in after["items"]])
        self.assertEqual(before["revision"], after["revision"])
        self.assertNotIn("facets", after)
        self.assertNotIn("status_counts", after)
        self.assertFalse(any("SELECT 'status' AS facet" in query for query in counter.queries))

    def test_revision_changes_when_state_changes_inside_same_second(self):
        before_accounts = repo.list_account_statuses(repo.PageRequest(page=1, page_size=20))
        account_id = before_accounts["items"][0]["id"]
        rs.patch_row(rs.ACCOUNTS, account_id, {"plan_check_status": "running"})
        after_accounts = repo.list_account_statuses(repo.PageRequest(page=1, page_size=20))
        self.assertNotEqual(before_accounts["revision"], after_accounts["revision"])

        before_jobs = repo.list_jobs(repo.PageRequest(page=1, page_size=20))
        job_id = before_jobs["items"][0]["id"]
        rs.patch_row(rs.JOBS, job_id, {"status": "running"})
        after_jobs = repo.list_jobs(repo.PageRequest(page=1, page_size=20))
        self.assertNotEqual(before_jobs["revision"], after_jobs["revision"])

    def test_dashboard_uses_aggregates(self):
        result = repo.dashboard_aggregates()
        self.assertEqual(result["accounts"]["total"], 30)
        self.assertEqual(result["accounts"]["plans"]["free_trial_eligible"], 5)
        self.assertEqual(result["accounts"]["plans"]["free"], 15)
        self.assertEqual(result["jobs"]["total"], 45)
        self.assertEqual(result["codex"]["total"], 1)

    def test_all_admin_reads_have_bounded_query_counts(self):
        cases = {
            "accounts": lambda: repo.list_accounts(repo.PageRequest(1, 20, {})),
            "account_status": lambda: repo.list_account_statuses(repo.PageRequest(1, 20, {})),
            "email_pool": lambda: repo.list_email_pool(repo.PageRequest(1, 20, {"source": "all"})),
            "codex": lambda: repo.list_codex(repo.PageRequest(1, 20, {"archived": "0"})),
            "dashboard": repo.dashboard_aggregates,
        }
        for name, call in cases.items():
            with self.subTest(name=name), _QueryCounter() as counter:
                call()
            self.assertLessEqual(counter.count, 12, (name, counter.count))


if __name__ == "__main__":
    unittest.main()
