"""HTTP snapshots of the durable bulk command and its complete item receipts."""
from core.operations import bulk_mutation_worker as worker
from core.operations import task_gateway
from core.operations.contracts import BulkItemResult
from core.storage.operations import store as operation_store
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class BulkRouteContractsTests(PostgresTestCase):
    def setUp(self):
        self.client = create_app(auth_code="bulk-route-test").test_client()
        self.headers = {"X-Auth-Code": "bulk-route-test"}
        worker.register_bulk_mutation_handler("test_bulk_receipt_page", self._receipt)

    @staticmethod
    def _receipt(chunk, _parameters, *, conn):
        return [BulkItemResult(key, "updated", data={"id": key, "count": 1}) for key in chunk]

    def _submit(self, targets):
        return worker.submit_bulk_mutation("test_bulk_receipt_page", targets, {},
            idempotency_key="bulk-query-test", trigger="manual")

    def test_poll_queued_command_shows_request_counts(self):
        command = self._submit([123, 123, 456, None])
        response = self.client.get(f"/api/bulk-mutations/{command['command_id']}", headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual({
            "ok": True, "command_id": str(command["command_id"]), "operation": "test_bulk_receipt_page",
            "task_id": str(command["task_id"]), "run_id": str(command["run_id"]),
            "status": "queued", "requested_count": 4, "unique_count": 2, "duplicate_count": 1,
            "updated_count": 0, "skipped_count": 0, "failed_count": 0,
            "item_count": 0, "items": [], "offset": 0, "limit": 500, "next_offset": None,
        }, response.get_json())

    def test_complete_receipt_pages_keep_all_items_and_bigint_ids(self):
        first = 2**53 + 1
        command = self._submit(list(range(first, first + 5001)))
        execution_id = "bulk-route-test-worker"
        run = operation_store.claim_run(command["run_id"], execution_id=execution_id, worker_pid=123)
        context = task_gateway.OperationHandlerContext(run, execution_id=execution_id)
        result = worker._handle_claimed_bulk_mutation(context)
        operation_store.finish_run(context.run_id, status=result.status, execution_id=execution_id)
        url = f"/api/bulk-mutations/{command['command_id']}"

        response = self.client.get(f"{url}?limit=5000", headers=self.headers)
        self.assertEqual(200, response.status_code)
        primary = response.get_json()
        self.assertEqual("success", primary["status"])
        self.assertEqual(5001, primary["item_count"])
        self.assertEqual(5001, primary["updated_count"])
        self.assertEqual(5000, primary["next_offset"])
        self.assertEqual({"key": str(first), "status": "updated", "reason_code": None,
            "reason": "", "data": {"id": str(first), "count": 1}}, primary["items"][0])

        response = self.client.get(f"{url}?offset=5000", headers=self.headers)
        self.assertEqual(200, response.status_code)
        tail = response.get_json()
        self.assertEqual([str(key) for key in range(first, first + 5001)],
                         [item["key"] for item in primary["items"] + tail["items"]])
        self.assertIsNone(tail["next_offset"])

    def test_poll_rejects_unknown_command_and_invalid_pagination(self):
        missing = self.client.get("/api/bulk-mutations/999999", headers=self.headers)
        self.assertEqual(404, missing.status_code)
        self.assertEqual("bulk_command_not_found", (missing.get_json() or {}).get("reason_code"))
        for suffix in ("?offset=-1", "?limit=0", "?limit=5001", "?limit=not-a-number"):
            with self.subTest(suffix=suffix):
                invalid = self.client.get(f"/api/bulk-mutations/999999{suffix}", headers=self.headers)
                self.assertEqual(400, invalid.status_code)
                self.assertEqual("invalid_bulk_pagination", invalid.get_json()["reason_code"])

    def test_domains_return_exact_submission_ids_and_reject_conflicting_requests(self):
        # Exercise both domain endpoints with real command persistence and the
        # same request key, then vary the targets within each operation.
        headers = {**self.headers, "Idempotency-Key": "domain-query-test"}
        for path, field, first, second in (
            ("/api/codex/reset-export-bulk", "filenames", "codex-first.json", "codex-second.json"),
            ("/api/outlook/delete-bulk", "emails", "first@example.test", "second@example.test"),
        ):
            with self.subTest(path=path):
                accepted = self.client.post(path, json={field: [first]}, headers=headers)
                self.assertEqual(202, accepted.status_code)
                response = accepted.get_json()
                for key in ("command_id", "task_id", "run_id"):
                    self.assertRegex(response[key], r"^[1-9][0-9]*$")
                poll = self.client.get(f"/api/bulk-mutations/{response['command_id']}", headers=self.headers)
                self.assertEqual("queued", poll.get_json()["status"])
                conflict = self.client.post(path, json={field: [second]}, headers=headers)
                self.assertEqual(409, conflict.status_code)
                self.assertEqual("idempotency_key_conflict", conflict.get_json()["reason_code"])
