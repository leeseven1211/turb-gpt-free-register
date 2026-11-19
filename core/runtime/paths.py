"""无配置或数据库副作用的运行目录解析。"""
from __future__ import annotations

import os
import json
from collections.abc import Mapping
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _external_root(environment: Mapping, key: str, code: str) -> Path | None:
    raw = str(environment.get(key) or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError(code)
    return path.resolve()


def runtime_dir(*, environment: Mapping | None = None, project_root: Path | None = None) -> Path:
    """显式运行根稳定跨版本；旧 combined 继续使用源码下的 logs/run。"""
    env = os.environ if environment is None else environment
    configured = _external_root(env, "TURB_RUNTIME_DIR", "runtime_directory_absolute_required")
    if configured is not None:
        return configured
    root = _PROJECT_ROOT if project_root is None else Path(project_root)
    return root / "logs" / "run"


def task_log_root(
    *, environment: Mapping | None = None, legacy_default: Path | None = None,
) -> Path:
    """共享日志根优先；显式运行实例的默认日志也在包外运行根。"""
    env = os.environ if environment is None else environment
    configured = _external_root(env, "TASK_RUN_LOG_ROOT", "runtime_log_directory_absolute_required")
    if configured is not None:
        return configured
    configured = _external_root(env, "TURB_RUNTIME_DIR", "runtime_directory_absolute_required")
    if configured is not None:
        return configured / "logs"
    return _PROJECT_ROOT / "logs" if legacy_default is None else Path(legacy_default)


def compatibility_data_root(legacy_default: Path, *, environment: Mapping | None = None) -> Path:
    """只有显式运行实例才迁移仍启用的兼容导出，保留旧只读查找位置。"""
    env = os.environ if environment is None else environment
    configured = _external_root(env, "TURB_RUNTIME_DIR", "runtime_directory_absolute_required")
    return Path(legacy_default) if configured is None else configured / "compat"


def legacy_log_roots(*, environment: Mapping | None = None) -> tuple[Path, ...]:
    """历史日志只接受部署显式列出的绝对目录，不扫描父目录或其它版本。"""
    env = os.environ if environment is None else environment
    raw = str(env.get("TURB_LEGACY_LOG_ROOTS") or "").strip()
    if not raw:
        return ()
    try:
        values = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("runtime_legacy_log_roots_invalid") from None
    if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
        raise ValueError("runtime_legacy_log_roots_invalid")
    roots = []
    for value in values:
        path = Path(value)
        if not path.is_absolute():
            raise ValueError("runtime_legacy_log_root_absolute_required")
        roots.append(path.resolve())
    return tuple(dict.fromkeys(roots))
