"""批量命令的目标规范化、分块执行和统一回执。

本模块只处理内存中的契约，不访问数据库、Flask 或 Worker。
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from .contracts import BulkItemResult, BulkMutationResult


@dataclass(frozen=True)
class NormalizedBulkTargets:
    """规范化后的首次目标、无效目标和重复计数。"""

    targets: tuple[object, ...]
    invalid: tuple[BulkItemResult, ...]
    duplicate_count: int = 0

    def __iter__(self):
        # 方便调用方按 (targets, invalid, duplicate_count) 解包。
        yield self.targets
        yield self.invalid
        yield self.duplicate_count


def _is_valid_target(target: object) -> bool:
    if target is None or isinstance(target, (bool, float)):
        return False
    if isinstance(target, str):
        return bool(target.strip())
    try:
        hash(target)
    except TypeError:
        return False
    return True


def normalize_bulk_targets(targets: Iterable[object], *, max_targets: int = 5000) -> NormalizedBulkTargets:
    """稳定去重目标，并将空值、不可哈希值分类为 ``invalid_target``。"""
    if max_targets <= 0:
        raise ValueError("max_targets must be positive")

    unique: list[object] = []
    invalid: list[BulkItemResult] = []
    seen: set[object] = set()
    duplicate_count = 0
    for target in targets:
        if not _is_valid_target(target):
            invalid.append(BulkItemResult(key=target, status="skipped", reason_code="invalid_target", reason="目标无效"))
            continue
        if target in seen:
            duplicate_count += 1
            continue
        seen.add(target)
        unique.append(target)
        if len(unique) > max_targets:
            raise ValueError("bulk_target_limit_exceeded")
    return NormalizedBulkTargets(tuple(unique), tuple(invalid), duplicate_count)


def _coerce_chunk_results(chunk: Sequence[object], raw: object) -> dict[object, BulkItemResult]:
    if raw is None:
        return {target: BulkItemResult(key=target, status="updated") for target in chunk}
    result: dict[object, BulkItemResult] = {}
    if isinstance(raw, Mapping):
        values = raw.items()
    elif isinstance(raw, BulkItemResult):
        values = ((raw.key, raw),)
    else:
        sequence = raw if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)) else (raw,)
        values = ((None, value) for value in sequence)
    for key, value in values:
        if isinstance(value, BulkItemResult):
            item = value
        elif isinstance(value, Mapping):
            item = BulkItemResult(
                key=value.get("key", key),
                status=str(value.get("status", "updated")),
                reason_code=value.get("reason_code"),
                reason=str(value.get("reason", "")),
                data=value.get("data"),
            )
        elif key is not None:
            item = BulkItemResult(key=key, status=str(value or "updated"))
        else:
            item = BulkItemResult(key=value, status="updated")
        if item.key in chunk:
            result[item.key] = item
    for target in chunk:
        result.setdefault(target, BulkItemResult(key=target, status="updated"))
    return result


def execute_chunked_bulk(
    operation: str,
    targets: Iterable[object],
    apply_chunk: Callable[[tuple[object, ...]], object],
    *,
    max_targets: int = 5000,
    chunk_size: int = 500,
    idempotency_key: str | None = None,
) -> BulkMutationResult:
    """按块调用 ``apply_chunk``，合并逐项结果并隔离块级异常。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    raw_targets = tuple(targets)
    normalized = normalize_bulk_targets(raw_targets, max_targets=max_targets)
    # 无效目标可能不可哈希，不能放入按目标索引的映射；最终按原始顺序生成回执。
    by_target: dict[object, BulkItemResult] = {}
    chunk_metadata: list[dict] = []
    for start in range(0, len(normalized.targets), chunk_size):
        chunk = normalized.targets[start : start + chunk_size]
        try:
            chunk_results = _coerce_chunk_results(chunk, apply_chunk(chunk))
            chunk_metadata.append({"chunk_index": start // chunk_size, "requested_count": len(chunk), "status": "updated"})
        except Exception:
            chunk_metadata.append({"chunk_index": start // chunk_size, "requested_count": len(chunk), "status": "failed", "reason_code": "bulk_chunk_failed"})
            chunk_results = {
                target: BulkItemResult(key=target, status="failed", reason_code="bulk_chunk_failed", reason="当前分块执行失败")
                for target in chunk
            }
        by_target.update(chunk_results)

    # 逐项回执按首次输入顺序输出；重复目标不再生成第二项。
    seen: set[object] = set()
    ordered: list[BulkItemResult] = []
    for target in raw_targets:
        if _is_valid_target(target):
            if target in seen:
                continue
            seen.add(target)
        item = by_target.get(target) if _is_valid_target(target) else None
        if item is None:
            item = BulkItemResult(key=target, status="skipped", reason_code="invalid_target", reason="目标无效")
        ordered.append(item)
    items = tuple(ordered)
    chunks = tuple(chunk_metadata)
    return BulkMutationResult(
        operation=operation,
        requested_count=len(raw_targets),
        unique_count=len(normalized.targets),
        duplicate_count=normalized.duplicate_count,
        updated_count=sum(item.status == "updated" for item in items),
        skipped_count=sum(item.status == "skipped" for item in items),
        failed_count=sum(item.status == "failed" for item in items),
        items=items,
        chunks=chunks,
        idempotency_key=idempotency_key,
    )


__all__ = [
    "BulkItemResult",
    "BulkMutationResult",
    "NormalizedBulkTargets",
    "normalize_bulk_targets",
    "execute_chunked_bulk",
]
