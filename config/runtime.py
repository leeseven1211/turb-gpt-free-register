# -*- coding: utf-8 -*-
"""运行配置持久化门面；启动参数留在文件，激活后数据库拥有运行值。"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar

BOOTSTRAP_KEYS = frozenset({
    "DATABASE_URL", "TURB_ALLOW_PRODUCTION_DB", "WEBUI_AUTH_CODE", "WEBUI_SESSION_SECRET",
    "TURB_MAIL_CONSUMER_ID", "TURB_DB_SCHEMA", "TURB_DB_POOL_MAX", "TURB_CONFIG_ENCRYPTION_KEY",
    "TASK_RUN_LOG_ROOT", "NODE_EXECUTABLE", "OPENAI_SENTINEL_NODE_PATH", "CLOAK_USER_DATA_DIR",
    "ACCOUNT_TASK_DB_SCHEMA", "OPERATION_TASK_DB_SCHEMA", "AUTH_CODE", "WEB_AUTH_CODE",
    "FLASK_SECRET_KEY", "PYTHON_DOTENV_DISABLED", "HOST", "PORT", "OPEN_BROWSER", "VERBOSE",
    "EXTRA_ARGS", "STARTUP_CHECK_TIMEOUT", "PATH", "TMPDIR", "TEMP", "TMP",
})
_LOCK = threading.RLock()
_CACHE_KEY = None
_CACHE_VALUES: dict[str, str] | None = None
_CACHE_AT = 0.0
_PROJECTED_KEYS: set[str] = set()
_IN_TRANSACTION = ContextVar("runtime_config_facade_transaction", default=False)


def is_bootstrap_key(key: str) -> bool:
    return str(key) in BOOTSTRAP_KEYS


def _repository():
    # dotenv 的 bootstrap 已加载后才导入，避免 config/core 相互初始化。
    from core.storage import runtime_config as runtime_config_store
    return runtime_config_store


def _automatic_database_allowed() -> bool:
    from config.env_loader import dotenv_loading_disabled
    return not dotenv_loading_disabled() and bool(os.getenv("DATABASE_URL"))


def reset_cache() -> None:
    """隔离测试或切换数据源时清空缓存，不改进程环境。"""
    global _CACHE_KEY, _CACHE_VALUES, _CACHE_AT
    with _LOCK:
        _CACHE_KEY, _CACHE_VALUES, _CACHE_AT = None, None, 0.0


def _known_runtime_keys() -> set[str]:
    from config.schema import CONFIG_SCHEMA, LEGACY_ENV_OVERRIDE_TYPES
    keys = set(LEGACY_ENV_OVERRIDE_TYPES)
    for field in CONFIG_SCHEMA.fields:
        keys.add(field.key)
        keys.update(field.aliases)
    keys.update(key for key in os.environ if key.startswith("EMAIL_DERIVATION_") and "_SECRET_" in key)
    return {key for key in keys if not is_bootstrap_key(key)}


def _project(values: dict[str, str]) -> None:
    from config.env_loader import dotenv_loading_disabled, read_env_file
    global _PROJECTED_KEYS
    stale = _known_runtime_keys() | _PROJECTED_KEYS
    if not dotenv_loading_disabled():
        stale.update(key for key in read_env_file() if not is_bootstrap_key(key))
    for key in stale - values.keys():
        os.environ.pop(key, None)
    os.environ.update(values)
    _PROJECTED_KEYS = set(values)


def load_values(*, force: bool = False) -> dict[str, str] | None:
    """激活库时投影权威值；未激活返回 None，失败直接抛出。"""
    global _CACHE_KEY, _CACHE_VALUES, _CACHE_AT
    if not _automatic_database_allowed():
        return None
    from config.env_loader import env_path
    key = (os.getenv("DATABASE_URL"), os.getenv("TURB_DB_SCHEMA"),
           os.getenv("TURB_CONFIG_ENCRYPTION_KEY"), str(env_path()))
    with _LOCK:
        if _IN_TRANSACTION.get():
            # 未提交值只属于当前保存操作，不能放入跨线程共享的读取缓存。
            values = _repository().read_values()
            if values is None:
                raise RuntimeError("运行配置存储失败：config_not_migrated，请先显式执行配置数据库迁移")
            values = {str(name): str(value) for name, value in values.items() if not is_bootstrap_key(name)}
            _project(values)
            return values
        if force or key != _CACHE_KEY or time.monotonic() - _CACHE_AT >= 1.0:
            values = _repository().read_values()
            if values is None and str(os.getenv("TURB_CONFIG_ENCRYPTION_KEY") or "").strip():
                raise RuntimeError("运行配置存储失败：config_not_migrated，请先显式执行配置数据库迁移")
            # 读取失败时不能把旧缓存伪装成成功，也不能降级到文件。
            _CACHE_VALUES = None if values is None else {
                str(name): str(value) for name, value in values.items() if not is_bootstrap_key(name)
            }
            _CACHE_KEY, _CACHE_AT = key, time.monotonic()
        if _CACHE_VALUES is not None:
            _project(_CACHE_VALUES)
            return dict(_CACHE_VALUES)
        return None


def database_enabled() -> bool:
    return load_values() is not None


def read_persisted_values() -> dict[str, str]:
    """读取启动文件与权威运行值；激活后不合并历史运行文件。"""
    from config.env_loader import read_env_file
    physical = read_env_file()
    values = load_values()
    if values is None:
        return physical
    return {**{key: value for key, value in physical.items() if is_bootstrap_key(key)}, **values}


@contextmanager
def persistence_transaction():
    """数据库写和 reload 共享事务；隔离旧测试不自动建立数据库连接。"""
    # 兼容模块仍从全局环境 reload；提交前禁止其他 facade 读者投影旧库值。
    with _LOCK:
        if database_enabled():
            try:
                with _repository().transaction() as conn:
                    token = _IN_TRANSACTION.set(True)
                    try:
                        yield conn
                    finally:
                        _IN_TRANSACTION.reset(token)
            finally:
                reset_cache()
        else:
            yield None


def write_persisted_values(updates: dict[str, str]) -> list[str]:
    """分流写入，禁止未迁移时隐式激活部分运行配置。"""
    from config.env_loader import dotenv_loading_disabled, write_env_values
    if not updates:
        return []
    normalized = {str(key): "" if value is None else str(value) for key, value in updates.items()}
    bootstrap = {key: value for key, value in normalized.items() if is_bootstrap_key(key)}
    runtime = {key: value for key, value in normalized.items() if not is_bootstrap_key(key)}
    enabled = database_enabled()
    if runtime and not enabled:
        if dotenv_loading_disabled() and not _automatic_database_allowed():
            return write_env_values(normalized)
        raise RuntimeError("运行配置尚未迁移，请先显式执行配置数据库迁移")
    written = []
    if runtime:
        written.extend(_repository().write_values(runtime, source="webui"))
        reset_cache()
        load_values(force=True)
    if bootstrap:
        written.extend(write_env_values(bootstrap))
    return written


def capture_state():
    with _LOCK:
        return (_CACHE_KEY, None if _CACHE_VALUES is None else dict(_CACHE_VALUES),
                _CACHE_AT, set(_PROJECTED_KEYS))


def restore_state(state) -> None:
    global _CACHE_KEY, _CACHE_VALUES, _CACHE_AT, _PROJECTED_KEYS
    with _LOCK:
        _CACHE_KEY, _CACHE_VALUES, _CACHE_AT, _PROJECTED_KEYS = state
