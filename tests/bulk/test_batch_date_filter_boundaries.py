"""批次创建日期的日历校验、HTTP 错误和真实 PostgreSQL 微秒边界。"""
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch
import uuid

from flask import Flask

from core.storage import records
from core.storage.operations import bulk, bulk_batches, bulk_common, bulk_schema, legacy_task_store, store
from tests.support_pg import PostgresTestCase
from webui.routes.bulk import create_bulk_blueprint


class BatchDateValidationTests(TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(create_bulk_blueprint(None))
        self.client = app.test_client()

    def test_invalid_calendar_values_return_400_before_any_storage_probe(self):
        cases = (
            ("created_from", "2026-02-31"),
            ("created_to", "2026-13-01"),
            ("created_before", "2026-11-31T00:00:00Z"),
            ("created_before", "not-a-date"),
            ("created_to", "9999-12-31"),
            ("created_from", "2026-11-19' OR TRUE--"),
            ("created_to", "2026-11-19T25:00:00Z"),
        )
        with patch.object(bulk_schema, "require_readable") as probe, patch.object(
            bulk_batches, "connect",
        ) as connect:
            for field, value in cases:
                with self.subTest(field=field, value=value):
                    response = self.client.get("/api/bulk/batches", query_string={field: value})
                    self.assertEqual(400, response.status_code, response.json)
                    self.assertEqual("parameter_invalid", response.json["error"]["code"])
                    self.assertEqual(field, response.json["error"]["field"])
                    self.assertFalse(response.json["error"]["retryable"])
            probe.assert_not_called()
            connect.assert_not_called()

    def test_route_passes_optional_exclusive_bound_to_storage(self):
        result = {"items": [], "summary": {}, "page": {"has_more": False, "next_cursor": None}}
        with patch.object(bulk, "list_batches", return_value=result) as listing:
            response = self.client.get("/api/bulk/batches", query_string={
                "created_from": "2026-11-18T16:00:00Z", "created_before": "2026-11-19T16:00:00Z",
            })
        self.assertEqual(200, response.status_code, response.json)
        self.assertEqual("2026-11-19T16:00:00Z", listing.call_args.kwargs["created_before"])

    def test_date_only_includes_the_whole_day_and_timestamp_remains_inclusive(self):
        utc = timezone.utc
        self.assertEqual([("<", datetime(2026, 11, 20, tzinfo=utc))],
                         bulk_common.batch_created_bounds({"created_to": "2026-11-19"}))
        self.assertEqual([("<=", datetime(2026, 11, 19, 23, 59, 59, tzinfo=utc))],
                         bulk_common.batch_created_bounds({"created_to": "2026-11-19T23:59:59Z"}))
        self.assertEqual([("<", datetime(2026, 11, 20, tzinfo=utc))],
                         bulk_common.batch_created_bounds({"created_before": "2026-11-20T00:00:00Z"}))

    def test_inverted_range_returns_a_stable_validation_error(self):
        response = self.client.get("/api/bulk/batches", query_string={
            "created_from": "2026-11-20", "created_before": "2026-11-19",
        })
        self.assertEqual(400, response.status_code, response.json)
        self.assertEqual("created_from", response.json["error"]["field"])


class BatchDatePostgresBoundaryTests(PostgresTestCase):
    def setUp(self):
        self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
        bulk.reset_ready()
        bulk.init()
        self.enterContext(patch("core.bulk_operations.catalog.capture_settings", return_value={
            "config_revision": "test-v1", "effective_settings": {},
        }))

    def batch_at(self, timestamp):
        account_id = self.seed(records.ACCOUNTS, [{"email": f"date-{uuid.uuid4().hex}@example.test"}])[0]
        selection = bulk.create_selection(request_key=uuid.uuid4().hex,
            source={"kind": "ids", "ids": [account_id]}, operation_key="plan_check",
            parameters={}, config_revision="test-v1")
        bulk.freeze_selection(selection["id"])
        batch = bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=selection["id"],
            selection_revision=1, operation_key="plan_check", parameters={}, config_revision="test-v1")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_batch_controls')} SET created_at=%s WHERE batch_id=%s",
                        (timestamp, batch["id"]))
        return batch["id"]

    def test_local_day_exclusive_upper_bound_includes_last_microsecond(self):
        before = self.batch_at("2026-11-18T15:59:59.999999Z")
        first = self.batch_at("2026-11-18T16:00:00Z")
        last = self.batch_at("2026-11-19T15:59:59.999999Z")
        next_day = self.batch_at("2026-11-19T16:00:00Z")
        result = bulk.list_batches(created_from="2026-11-19T00:00:00+08:00",
                                   created_before="2026-11-20T00:00:00+08:00")
        self.assertEqual({first, last}, {row["id"] for row in result["items"]})
        self.assertEqual(2, result["summary"]["total_batches"])
        self.assertNotIn(before, {row["id"] for row in result["items"]})
        self.assertNotIn(next_day, {row["id"] for row in result["items"]})

    def test_legacy_timestamp_upper_bound_stays_inclusive_and_date_only_covers_full_day(self):
        first = self.batch_at("2026-11-19T00:00:00Z")
        exact = self.batch_at("2026-11-19T23:59:59Z")
        micro = self.batch_at("2026-11-19T23:59:59.999999Z")
        self.batch_at("2026-11-20T00:00:00Z")
        old = bulk.list_batches(created_from="2026-11-19", created_to="2026-11-19T23:59:59Z")
        self.assertEqual({first, exact}, {row["id"] for row in old["items"]})
        whole_day = bulk.list_batches(created_from="2026-11-19", created_to="2026-11-19")
        self.assertEqual({first, exact, micro}, {row["id"] for row in whole_day["items"]})
        self.assertEqual(3, whole_day["summary"]["total_batches"])
