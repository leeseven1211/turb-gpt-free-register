from __future__ import annotations

from core.operations.bulk_mutations import (
    BulkItemResult,
    BulkMutationResult,
    execute_chunked_bulk,
    normalize_bulk_targets,
)


def test_normalize_deduplicates_stably_and_classifies_invalid_targets():
    normalized = normalize_bulk_targets(["b", "a", "b", "", None, True, "a"])

    assert normalized.targets == ("b", "a")
    assert normalized.duplicate_count == 2
    assert [item.key for item in normalized.invalid] == ["", None, True]
    assert [item.reason_code for item in normalized.invalid] == [
        "invalid_target",
        "invalid_target",
        "invalid_target",
    ]


def test_execute_chunks_at_five_hundred_and_preserves_first_input_order():
    targets = list(range(1001))
    chunks: list[tuple[int, ...]] = []

    def apply_chunk(chunk):
        chunks.append(tuple(chunk))
        return [BulkItemResult(key=target, status="updated") for target in chunk]

    result = execute_chunked_bulk("archive", targets, apply_chunk)

    assert [len(chunk) for chunk in chunks] == [500, 500, 1]
    assert [item.key for item in result.items] == targets
    assert result.requested_count == 1001
    assert result.unique_count == 1001
    assert result.updated_count == 1001
    assert result.chunks[0]["chunk_index"] == 0


def test_chunk_exception_only_marks_current_chunk_failed_and_continues():
    targets = list(range(1001))
    calls = 0

    def apply_chunk(chunk):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic failure")
        return [BulkItemResult(key=target, status="updated") for target in chunk]

    result = execute_chunked_bulk("delete", targets, apply_chunk)

    assert calls == 3
    assert all(item.status == "updated" for item in result.items[:500])
    assert all(item.reason_code == "bulk_chunk_failed" for item in result.items[500:1000])
    assert all(item.status == "updated" for item in result.items[1000:])
    assert result.failed_count == 500
    assert result.chunks[1]["status"] == "failed"


def test_result_merges_invalid_items_and_duplicate_count():
    result = execute_chunked_bulk(
        "archive",
        ["ok", "", "ok", None],
        lambda chunk: [BulkItemResult(key="ok", status="updated")],
    )

    assert [item.key for item in result.items] == ["ok", "", None]
    assert [item.reason_code for item in result.items[1:]] == ["invalid_target", "invalid_target"]
    assert result.duplicate_count == 1
    assert result.requested_count == 4
    assert result.unique_count == 1
    assert result.updated_count == 1
    assert result.skipped_count == 2
    assert isinstance(result, BulkMutationResult)


def test_chunk_mapping_keeps_target_keys_when_values_are_statuses():
    result = execute_chunked_bulk(
        "archive",
        ["a", "b"],
        lambda chunk: {target: "skipped" if target == "b" else "updated" for target in chunk},
    )

    assert [(item.key, item.status) for item in result.items] == [
        ("a", "updated"),
        ("b", "skipped"),
    ]


def test_unhashable_invalid_targets_are_classified_without_type_error():
    result = execute_chunked_bulk(
        "archive",
        [["a"], {"id": 1}, "ok"],
        lambda chunk: [BulkItemResult(key="ok", status="updated")],
    )

    assert [item.reason_code for item in result.items[:2]] == ["invalid_target", "invalid_target"]
    assert result.items[2].status == "updated"
