"""提链统计的服务入口，仅执行只读聚合。"""
from __future__ import annotations

from core.storage.extract_link import analytics


def workbench_analytics(*, days: int = 7, provider_id: str | None = None) -> dict:
    return analytics.workbench_analytics(days=days, provider_id=provider_id)
