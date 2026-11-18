"""任务中心只读查询的应用层参数。"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OperationQuery:
    """沿用任务列表的筛选语义，仓储负责分页归一化。"""

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
        """批次导航由查询服务另外读取。"""
        values = asdict(self)
        values.pop("include_batches")
        return values
