"""任务查询的应用层输入；HTTP 响应契约见 contracts/task-center.openapi.json。"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OperationQuery:
    """沿用任务列表的筛选语义，不在应用层重复仓储的分页归一化。"""

    page: int = 1
    page_size: int = 50
    task_type: str = ""
    status: str = ""
    source: str = ""
    q: str = ""
    batch_id: int | None = None
    task_id: str = ""
    target: str = ""
    target_status: str = ""
    batch: str = ""
    run_count: str = ""
    stage: str = ""
    created_from: str = ""
    created_to: str = ""
    result: str = ""
    include_facets: bool = True
    include_batches: bool = True

    def store_arguments(self) -> dict:
        """批次导航属于查询编排，其余字段直接交给已有仓储。"""
        values = asdict(self)
        values.pop("include_batches")
        return values


@dataclass(frozen=True)
class BulkItemResult:
    """批量命令中的单项目回执。"""

    key: object
    status: str
    reason_code: str | None = None
    reason: str = ""
    data: object | None = None

    def __post_init__(self) -> None:
        if self.status not in {"updated", "skipped", "failed"}:
            raise ValueError("invalid bulk item status")


@dataclass(frozen=True)
class BulkMutationResult:
    """批量命令的不可变统一回执。"""

    requested_count: int = 0
    unique_count: int = 0
    duplicate_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    items: tuple[BulkItemResult, ...] = ()
    chunks: tuple[dict, ...] = ()
    operation: str = ""
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "chunks", tuple(self.chunks))
