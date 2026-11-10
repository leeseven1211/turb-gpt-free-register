# -*- coding: utf-8 -*-
"""每部署业务并发策略的配置投影与只读迁移预览。"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from config.env_loader import apply_env_overrides
from config.schema import CONCURRENCY_WORKER_DEFAULTS, non_sensitive_snapshot, schema_default, validate_value

GLOBAL_TASK_WORKERS: int = schema_default("GLOBAL_TASK_WORKERS")
REGISTRATION_ROXY_WORKERS: int = schema_default("REGISTRATION_ROXY_WORKERS")
REGISTRATION_PROTO2_WORKERS: int = schema_default("REGISTRATION_PROTO2_WORKERS")
ACCOUNT_LIVE_CHECK_WORKERS: int = schema_default("ACCOUNT_LIVE_CHECK_WORKERS")
ACCOUNT_TOKEN_REFRESH_WORKERS: int = schema_default("ACCOUNT_TOKEN_REFRESH_WORKERS")
ACCOUNT_PLAN_CHECK_WORKERS: int = schema_default("ACCOUNT_PLAN_CHECK_WORKERS")
ACCOUNT_DEACTIVATION_MAIL_WORKERS: int = schema_default("ACCOUNT_DEACTIVATION_MAIL_WORKERS")
ACCOUNT_PASSWORD_SETUP_WORKERS: int = schema_default("ACCOUNT_PASSWORD_SETUP_WORKERS")
ACCOUNT_PASSWORD_CHANGE_WORKERS: int = schema_default("ACCOUNT_PASSWORD_CHANGE_WORKERS")
ACCOUNT_TWOFA_SETUP_WORKERS: int = schema_default("ACCOUNT_TWOFA_SETUP_WORKERS")
ACCOUNT_TWOFA_CHANGE_WORKERS: int = schema_default("ACCOUNT_TWOFA_CHANGE_WORKERS")
ACCOUNT_SETUP_WORKERS: int = schema_default("ACCOUNT_SETUP_WORKERS")
ACCOUNT_EMAIL_CHANGE_WORKERS: int = schema_default("ACCOUNT_EMAIL_CHANGE_WORKERS")
ACCOUNT_INSPECTION_WORKERS: int = schema_default("ACCOUNT_INSPECTION_WORKERS")
CODEX_OAUTH_WORKERS: int = schema_default("CODEX_OAUTH_WORKERS")
CODEX_TOKEN_REFRESH_WORKERS: int = schema_default("CODEX_TOKEN_REFRESH_WORKERS")
SUB2API_SYNC_WORKERS: int = schema_default("SUB2API_SYNC_WORKERS")
C2A_SYNC_WORKERS: int = schema_default("C2A_SYNC_WORKERS")
EXTRACT_LINK_WORKERS: int = schema_default("EXTRACT_LINK_WORKERS")
EMAIL_IMPORT_WORKERS: int = schema_default("EMAIL_IMPORT_WORKERS")
SUB2API_SCAN_WORKERS: int = schema_default("SUB2API_SCAN_WORKERS")
MAINTENANCE_CHECK_WORKERS: int = schema_default("MAINTENANCE_CHECK_WORKERS")
CONCURRENCY_POLICY_REVISION: int = schema_default("CONCURRENCY_POLICY_REVISION")

WORKER_KEYS = tuple(CONCURRENCY_WORKER_DEFAULTS)
POLICY_KEYS = (*WORKER_KEYS, "CONCURRENCY_POLICY_REVISION")
_LEGACY_ACCOUNT_KEYS = frozenset({
    key for key in WORKER_KEYS
    if key.startswith("ACCOUNT_") or key.startswith("CODEX_") or key in {"SUB2API_SYNC_WORKERS", "C2A_SYNC_WORKERS"}
})


def policy_values(values: Mapping[str, Any] | None = None) -> dict[str, int]:
    """校验完整策略；准入器可传同一事务读出的数据库值，避免进程缓存漂移。"""
    source = non_sensitive_snapshot().values if values is None else values
    return {key: validate_value(key, source.get(key, schema_default(key))) for key in POLICY_KEYS}


def migration_preview(values: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """仅生成建议，不把历史账号池上限解释成历史全局上限，也不写配置。"""
    source = values or {}
    required = values is not None and "CONCURRENCY_POLICY_REVISION" not in source
    legacy = source.get("ACCOUNT_BATCH_WORKERS")
    try:
        legacy = validate_value("ACCOUNT_BATCH_WORKERS", legacy) if legacy is not None else None
    except ValueError:
        legacy = None
    proposed = {key: schema_default(key) for key in POLICY_KEYS}
    if required and legacy is not None:
        proposed.update({key: legacy for key in _LEGACY_ACCOUNT_KEYS})
    for key in POLICY_KEYS:
        if key in source:
            try:
                proposed[key] = validate_value(key, source[key])
            except ValueError:
                # 损坏的历史字段不扩散到建议；实际读取与保存仍严格校验。
                pass
    return {
        "migration_required": required,
        "policy_revision": 1,
        "legacy_account_workers": legacy,
        "proposed_values": proposed,
        "required_keys": list(POLICY_KEYS),
        "notes": [
            "旧账号池上限无法推导历史全局上限；全局 3 是新策略建议，请按当前部署资源明确设置。",
            "注册与提链现在也计入全局上限；混跑峰值可能下降，类型上限之和可以超过全局。",
            "先停止旧版本新派发并排空旧 worker，再完整保存新策略；未确认迁移时新任务保留排队。",
            "本地与 Oracle 分别保存自己的策略；本预览不会修改配置或执行任务。",
        ],
    }


apply_env_overrides(globals())
