#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""显式将源目录 .env 的运行配置迁入 PostgreSQL，支持可恢复的重复执行。"""
from __future__ import annotations

import argparse
import fcntl
import io
import json
import os
import re
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MASTER_KEY = "TURB_CONFIG_ENCRYPTION_KEY"
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CONNECTION_KEYS = ("DATABASE_URL", "TURB_ALLOW_PRODUCTION_DB", "TURB_DB_SCHEMA", "TURB_DB_POOL_MAX")


class MigrationError(RuntimeError):
    """只暴露错误类别和配置键名，不携带原始值或底层异常。"""

    def __init__(self, category: str, *, keys=()):
        self.category = category
        self.keys = tuple(sorted(str(key) for key in keys if _KEY_RE.fullmatch(str(key))))
        super().__init__(category + (": " + ", ".join(self.keys) if self.keys else ""))


def _source_text(source_root: Path) -> str:
    try:
        return (source_root / ".env").read_bytes().decode("utf-8")
    except (OSError, UnicodeError):
        raise MigrationError("source_env_unreadable") from None


def _parse_dotenv(raw: str) -> dict[str, str]:
    try:
        from dotenv.main import resolve_variables
        from dotenv.parser import parse_stream
    except ImportError:
        raise MigrationError("dotenv_parser_unavailable") from None
    assignments = []
    # 标准 parser 同时处理引号、多行、行尾注释和转义；错误绑定不能静默丢掉。
    # load_dotenv 的文本文件读取会统一物理换行；原始字节仅用于备份和并发校验。
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    for binding in parse_stream(io.StringIO(normalized)):
        if binding.error or (binding.key is not None and (
            not _KEY_RE.fullmatch(binding.key) or binding.value is None
        )):
            raise MigrationError("invalid_env_assignment")
        if binding.key is not None:
            assignments.append((binding.key, binding.value))
    return dict(resolve_variables(assignments, override=False))


def read_source_values(source_root: Path | str) -> dict[str, str]:
    """按旧 load_dotenv(override=False) 的同源语法与插值解析源文件。"""
    return _parse_dotenv(_source_text(Path(source_root).resolve()))


@contextmanager
def _migration_environment(values: dict[str, str], *, strict_connection: bool = False):
    updates = {"PYTHON_DOTENV_DISABLED": "1"}
    if strict_connection:
        # 源部署目标是唯一连接来源；缺省 schema/生产放行不能继承外层进程。
        updates.update({key: values.get(key) for key in _CONNECTION_KEYS})
    if values.get(_MASTER_KEY):
        updates[_MASTER_KEY] = values[_MASTER_KEY]
    missing = object()
    previous = {key: os.environ.get(key, missing) for key in updates}
    for key, value in updates.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is missing:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _classify(values: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    with _migration_environment({}):
        from config.runtime import is_bootstrap_key
        bootstrap = {key: value for key, value in values.items() if is_bootstrap_key(key)}
        runtime = {key: value for key, value in values.items() if not is_bootstrap_key(key)}
    return bootstrap, runtime


def _validate_target(values: dict[str, str]) -> None:
    if not values.get("DATABASE_URL", "").strip():
        raise MigrationError("source_database_missing", keys=("DATABASE_URL",))
    conflicts = []
    if os.getenv("DATABASE_URL") and os.environ["DATABASE_URL"] != values["DATABASE_URL"]:
        conflicts.append("DATABASE_URL")
    if os.getenv("TURB_DB_SCHEMA") and os.environ["TURB_DB_SCHEMA"] != (values.get("TURB_DB_SCHEMA") or "public"):
        conflicts.append("TURB_DB_SCHEMA")
    if conflicts:
        raise MigrationError("target_mismatch", keys=conflicts)


def _quote_dotenv(value: str) -> str:
    escaped = (value.replace("\\", "\\\\").replace('"', '\\"')
               .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))
    return f'"{escaped}"'


def _render_bootstrap(bootstrap: dict[str, str]) -> str:
    # dotenv 会对所有引号类型执行插值；无法固化的字面量必须拒绝，不能悄悄二次展开。
    conflicts = [key for key, value in bootstrap.items() if "${" in value]
    if conflicts:
        raise MigrationError("bootstrap_encoding_conflict", keys=conflicts)
    text = "# 启动配置与稳定部署身份；运行配置由 PostgreSQL 管理。\n"
    text += "".join(f"{key}={_quote_dotenv(value)}\n" for key, value in bootstrap.items())
    parsed = _parse_dotenv(text)
    conflicts = [key for key, value in bootstrap.items() if parsed.get(key) != value]
    if conflicts:
        raise MigrationError("bootstrap_encoding_conflict", keys=conflicts)
    return text


@contextmanager
def _source_lock(root: Path):
    descriptor = os.open(root / ".env.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_env_write(path: Path, text: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".env.migration-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _backup_env(root: Path, original: str, backup_dir: Path | str | None) -> None:
    directory = Path(backup_dir) if backup_dir is not None else Path("run/runtime-config-backups")
    if not directory.is_absolute():
        directory = root / directory
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"runtime-config-{stamp}-{uuid.uuid4().hex}.env"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(directory)


def _persist_master_key(root: Path, original: str, values: dict[str, str], store) -> tuple[str, str]:
    from cryptography.fernet import Fernet

    master_key = values.get(_MASTER_KEY) or os.getenv(_MASTER_KEY) or ""
    if not master_key:
        if store.is_active():
            raise MigrationError("missing_encryption_key", keys=(_MASTER_KEY,))
        master_key = Fernet.generate_key().decode("ascii")
    try:
        Fernet(master_key.encode("ascii"))
    except (ValueError, UnicodeError):
        raise MigrationError("invalid_encryption_key", keys=(_MASTER_KEY,)) from None
    if values.get(_MASTER_KEY) == master_key:
        # 即使已有密钥也确保当前文件只有本用户可读。
        _atomic_env_write(root / ".env", original)
        return master_key, original
    escaped = _quote_dotenv(master_key)
    keyed_text = original + ("" if original.endswith("\n") or not original else "\n")
    keyed_text += f"{_MASTER_KEY}={escaped}\n"
    _atomic_env_write(root / ".env", keyed_text)
    return master_key, keyed_text


def _prune_env(root: Path, bootstrap: dict[str, str], expected_text: str) -> None:
    if _source_text(root) != expected_text:
        raise MigrationError("source_changed_during_migration")
    _atomic_env_write(root / ".env", _render_bootstrap(bootstrap))


def _report(bootstrap: dict[str, str], runtime: dict[str, str], *, mode: str, migrated: int = 0) -> dict:
    return {
        "mode": mode,
        "bootstrap_count": len(bootstrap),
        "bootstrap_keys": sorted(bootstrap),
        "runtime_count": len(runtime),
        "runtime_keys": sorted(runtime),
        "migrated_count": migrated,
    }


def run_migration(
    source_root: Path | str, *, apply: bool = False, backup_dir: Path | str | None = None
) -> dict:
    """默认只读统计；显式 apply 才备份、保存密钥、迁库和精简源文件。"""
    root = Path(source_root).resolve()
    values = read_source_values(root)
    bootstrap, runtime = _classify(values)
    if not apply:
        return _report(bootstrap, runtime, mode="dry-run")
    _validate_target(values)
    try:
        with _source_lock(root):
            original = _source_text(root)
            values = read_source_values(root)
            bootstrap, runtime = _classify(values)
            _validate_target(values)
            # 旧启动默认不覆盖显式进程值；迁移保存当次实际生效值，防止切换行为改变。
            runtime = {key: os.environ.get(key, value) for key, value in runtime.items()}
            _render_bootstrap(bootstrap)
            try:
                _backup_env(root, original, backup_dir)
            except Exception:
                raise MigrationError("env_backup_failed") from None
            with _migration_environment(values, strict_connection=True):
                from core.storage import runtime_config as store
                try:
                    master_key, keyed_text = _persist_master_key(root, original, values, store)
                except OSError:
                    raise MigrationError("encryption_key_persist_failed") from None
                bootstrap[_MASTER_KEY] = master_key
                with _migration_environment({_MASTER_KEY: master_key}):
                    with store.transaction() as conn:
                        store.ensure_tables(conn)
                        # 在未提交的同一事务里解密已有值；冲突时连激活标志一起回滚。
                        store.write_values({}, conn=conn, activate=True, source="migration")
                        existing = store.read_values(conn=conn) or {}
                        conflicts = [key for key, value in runtime.items() if key in existing and existing[key] != value]
                        if conflicts:
                            raise MigrationError("database_conflict", keys=conflicts)
                        changed = store.write_values(runtime, conn=conn, activate=True, source="migration")
                        persisted = store.read_values(conn=conn)
                        mismatches = [key for key, value in runtime.items() if (persisted or {}).get(key) != value]
                        if mismatches:
                            raise MigrationError("database_verification_failed", keys=mismatches)
                    # 数据库 commit 已完成；这里失败时源值与主密钥仍齐全，允许重放。
                    try:
                        _prune_env(root, bootstrap, keyed_text)
                    except MigrationError:
                        raise
                    except Exception:
                        raise MigrationError("env_prune_failed") from None
            return _report(bootstrap, runtime, mode="apply", migrated=len(changed))
    except MigrationError:
        raise
    except (Exception, SystemExit) as exc:
        code = getattr(exc, "code", None)
        if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,80}", code):
            raise MigrationError("database_" + code) from None
        raise MigrationError("migration_failed") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="显式将 .env 运行配置迁入 PostgreSQL")
    parser.add_argument("--source-root", required=True, type=Path, help="待迁移部署目录")
    parser.add_argument("--backup-dir", type=Path, help="原 .env 的私有备份目录，默认位于源目录 run/runtime-config-backups")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只输出配置键及统计，不连接数据库或修改文件")
    mode.add_argument("--apply", action="store_true", help="备份并迁库，成功后精简 .env")
    args = parser.parse_args(argv)
    try:
        report = run_migration(args.source_root, apply=args.apply, backup_dir=args.backup_dir)
    except MigrationError as exc:
        print(json.dumps({"error_category": exc.category, "keys": list(exc.keys)}, ensure_ascii=False), file=sys.stderr)
        return 1
    except (Exception, SystemExit):
        print(json.dumps({"error_category": "migration_failed", "keys": []}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(_PROJECT_ROOT))
    raise SystemExit(main())
