# -*- coding: utf-8 -*-
"""统一任务中心的历史保留策略。"""
from config.env_loader import apply_env_overrides
from config.schema import schema_default


# 0 关闭自动清理；正数表示只保留最近 N 天的明确终态任务。
TASK_CENTER_RETENTION_DAYS: int = schema_default("TASK_CENTER_RETENTION_DAYS")

# 清理前生成的脱敏本地归档保留期；0 表示永久保留归档。
TASK_CENTER_ARCHIVE_RETENTION_DAYS: int = schema_default("TASK_CENTER_ARCHIVE_RETENTION_DAYS")


apply_env_overrides(globals())
