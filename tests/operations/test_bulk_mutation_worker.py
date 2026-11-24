from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from core.operations import bulk_mutation_worker as worker
from core.operations.bulk_mutations import BulkItemResult
from core.operations.task_gateway import OperationResult


@pytest.fixture(autouse=True)
def _reset_worker_registry(monkeypatch):
    worker._HANDLERS.clear()
    worker._RUNTIME_REGISTERED = False
    yield
    worker._HANDLERS.clear()
    worker._RUNTIME_REGISTERED = False


def test_register_handler_and_submit_duplicate_idempotency_key(monkeypatch):
    calls = []

    def handler(chunk, parameters):
        calls.append((tuple(chunk), dict(parameters)))
        return [BulkItemResult(key=item, status="updated") for item in chunk]

    worker.register_bulk_mutation_handler("archive", handler)
    assert worker.registered_bulk_mutation_operations() == ("archive",)

    submitted = []

    def submit(**kwargs):
        submitted.append(kwargs)
        return {
            "accepted": True,
            "reused": len(submitted) > 1,
            "task_id": 11,
            "run_id": 21,
            "status": "queued",
        }

    monkeypatch.setattr(worker.task_gateway, "submit_durable_operation", submit)
    first = worker.submit_bulk_mutation(
        "archive", [1, 2], {"mode": "soft", "password": "do-not-store"},
        idempotency_key="request-1", trigger="manual",
    )
    second = worker.submit_bulk_mutation(
        "archive", [1, 2], {"mode": "soft", "password": "do-not-store"},
        idempotency_key="request-1", trigger="manual",
    )

    assert first["run_id"] == second["run_id"]
    assert submitted[0]["data"]["parameters"] == {"mode": "soft"}
    assert "password" not in submitted[0]["data"]["parameters"]
    assert submitted[0]["task_type"] == worker.TASK_TYPE
    assert submitted[0]["source_id"].startswith("bulk:")
    assert submitted[0]["source_id"] == submitted[1]["source_id"]


def test_worker_claims_and_calls_handler_by_chunks(monkeypatch):
    seen = []
    context = _Context(
        run_id=31,
        task_id=41,
        run={
            "id": 31,
            "task_id": 41,
            "data": {
                "operation": "archive",
                "targets": [1, 2, 3],
                "parameters": {"mode": "soft"},
                "chunk_size": 2,
                "idempotency_key": "request-2",
            },
        },
    )

    def handler(chunk, parameters):
        seen.append((tuple(chunk), dict(parameters)))
        return [BulkItemResult(key=item, status="updated") for item in chunk]

    worker.register_bulk_mutation_handler("archive", handler)
    result = worker._handle_claimed_bulk_mutation(context)

    assert [chunk for chunk, _ in seen] == [(1, 2), (3,)]
    assert result.status == "success"
    assert result.summary["updated_count"] == 3
    assert [event["detail"]["chunk_index"] for event in context.events] == [0, 1]


def test_repeated_claim_skips_completed_chunks_and_keeps_reason_code(monkeypatch):
    seen = []
    first_context = _Context(
        run_id=51,
        task_id=61,
        run={
            "id": 51,
            "task_id": 61,
            "data": {
                "operation": "archive",
                "targets": [1, 2, 3, 4],
                "parameters": {},
                "chunk_size": 2,
                "idempotency_key": "request-3",
            },
        },
    )

    def handler(chunk, parameters):
        seen.append(tuple(chunk))
        if tuple(chunk) == (1, 2):
            return [
                BulkItemResult(key=1, status="updated"),
                BulkItemResult(key=2, status="failed", reason_code="target_locked"),
            ]
        return [BulkItemResult(key=item, status="updated") for item in chunk]

    worker.register_bulk_mutation_handler("archive", handler)
    first = worker._handle_claimed_bulk_mutation(first_context)
    assert first.status == "partial_success"

    second_context = _Context(
        run_id=51,
        task_id=61,
        run={**first_context.run, "data": first_context.run["data"]},
        events=list(first_context.events),
    )
    second = worker._handle_claimed_bulk_mutation(second_context)

    assert seen == [(1, 2), (3, 4)]
    failed = next(item for item in second.summary["items"] if item["key"] == 2)
    assert failed["reason_code"] == "target_locked"
    assert second.summary["failed_count"] == 1


def test_run_bulk_mutation_delegates_to_durable_gateway(monkeypatch):
    called = []
    monkeypatch.setattr(
        worker.task_gateway,
        "_execute_operation_handler",
        lambda task_type, run_id: called.append((task_type, run_id)) or {"status": "success"},
    )

    assert worker.run_bulk_mutation(99) == {"status": "success"}
    assert called == [(worker.TASK_TYPE, 99)]


def test_mapping_handler_result_preserves_failure_reason_code():
    context = _Context(
        run_id=71,
        task_id=81,
        run={
            "id": 71,
            "task_id": 81,
            "data": {
                "operation": "archive",
                "targets": [1],
                "parameters": {},
            },
        },
    )
    worker.register_bulk_mutation_handler(
        "archive",
        lambda chunk, parameters: {
            1: {"status": "failed", "reason_code": "already_deleted"},
        },
    )

    result = worker._handle_claimed_bulk_mutation(context)

    assert result.status == "failed"
    assert result.summary["items"][0]["reason_code"] == "already_deleted"


@dataclass
class _Context:
    run_id: int
    task_id: int
    run: dict
    events: list[dict] = field(default_factory=list)

    def report(self, **event):
        self.events.append(event)
        return event

    def checkpoint(self):
        return None
