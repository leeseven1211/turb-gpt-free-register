# -*- coding: utf-8 -*-
"""Plus 试用提链服务配置。"""
from config.env_loader import apply_env_overrides
from config.schema import schema_default

# 提链服务地址
EXTRACT_LINK_API_BASE: str = schema_default("EXTRACT_LINK_API_BASE")

# 提链 CDK；创建任务和监听事件都需要。
EXTRACT_LINK_CDK: str = schema_default("EXTRACT_LINK_CDK")

# 提链类型：以提链网站 /api/link-types 当前启用项为准
EXTRACT_LINK_TYPE: str = schema_default("EXTRACT_LINK_TYPE")

# 提链队列容量与超时；提链并发统一使用 config.codex.ACCOUNT_BATCH_WORKERS
EXTRACT_LINK_QUEUE_LIMIT: int = 500
EXTRACT_LINK_REQUEST_TIMEOUT: int = 30
EXTRACT_LINK_EVENT_TIMEOUT: int = 180

apply_env_overrides(globals())
