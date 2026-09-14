#!/usr/bin/env python3
"""Run the test suite with explicit configuration and database isolation.

The entrypoint never loads the project ``.env``. It removes application
configuration inherited from the shell, preserves only a caller-supplied test
database, probes that database before pytest starts, and then launches pytest
in a subprocess. Tests that intentionally exercise an environment override can
still use ``patch.dict(os.environ, ...)`` inside the pytest process.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


_ENV_HELPERS = {"env_str", "env_bool", "env_int", "env_float", "env_list", "env_value"}
_ENV_METHODS = {"get", "pop", "setdefault"}
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PRODUCTION_DATABASES = {"turb_console"}

# These names are outside config/*.py but still affect test process behavior.
_PROCESS_ENV_KEYS = {
    "AUTH_CODE",
    "ACCOUNT_TASK_DB_SCHEMA",
    "AT_AUTO_REFRESH_ENABLED",
    "AT_REFRESH_BEFORE_HOURS",
    "AT_REFRESH_INITIAL_DELAY_SECONDS",
    "AT_REFRESH_MAX_PER_CYCLE",
    "AT_REFRESH_SCAN_INTERVAL_SECONDS",
    "COMPAT_EXPORT_DEBOUNCE_SECONDS",
    "COMPAT_EXPORT_MODE",
    "DATABASE_URL",
    "EXTRA_ARGS",
    "EMAIL_BUTLER_RISK_SCAN_INITIAL_DELAY_SECONDS",
    "EMAIL_BUTLER_RISK_SCAN_LOOKBACK_DAYS",
    "EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS",
    "FLASK_SECRET_KEY",
    "HOST",
    "ICLOUD_HME_IMAP_RETRY_ATTEMPTS",
    "OPEN_BROWSER",
    "PORT",
    "PYTHONPATH",
    "TASK_RUN_LOG_ROOT",
    "TURB_ALLOW_PRODUCTION_DB",
    "TURB_DB_POOL_MAX",
    "TURB_DB_SCHEMA",
    "TURB_TEST_DATABASE_LABEL",
    "OPERATION_TASK_DB_SCHEMA",
    "VERBOSE",
    "WEB_AUTH_CODE",
    "WEBUI_AUTH_CODE",
    "WEBUI_SESSION_SECRET",
}


class TestEnvironmentError(RuntimeError):
    """Raised when the unified test environment is unsafe or incomplete."""


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _attribute_path(node: ast.AST) -> tuple[str, ...]:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return tuple(reversed(parts))


def _assigned_env_key_names(node: ast.Assign | ast.AnnAssign) -> set[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names: set[str] = set()
    for target in targets:
        if not isinstance(target, ast.Name):
            continue
        value = node.value
        if target.id == "SECRET_ENV_KEYS" and isinstance(value, ast.Dict):
            names.update(
                key_text
                for item in value.keys
                if (key_text := _constant_string(item)) is not None
            )
        if target.id.endswith("ENV_KEYS") and isinstance(value, (ast.Tuple, ast.List, ast.Set)):
            names.update(
                value_text
                for item in value.elts
                if (value_text := _constant_string(item)) is not None
            )
    return names


def _collect_from_python(path: Path) -> set[str]:
    """Extract configuration key names without importing application modules."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise TestEnvironmentError(f"无法扫描配置环境变量 {path}: {exc}") from exc

    keys: set[str] = set()
    for statement in ast.walk(tree):
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            keys.update(_assigned_env_key_names(statement))
        if not isinstance(statement, ast.Call):
            continue

        function_path = _attribute_path(statement.func)
        function_name = function_path[-1] if function_path else ""
        if function_name in _ENV_HELPERS and statement.args:
            key = _constant_string(statement.args[0])
            if key:
                keys.add(key)

        if function_name == "apply_env_overrides" and len(statement.args) >= 2:
            schema = statement.args[1]
            if isinstance(schema, ast.Dict):
                keys.update(
                    key_text
                    for item in schema.keys
                    if (key_text := _constant_string(item)) is not None
                )

        if function_path == ("os", "getenv") or function_path[-2:] == ("os", "getenv"):
            if statement.args:
                key = _constant_string(statement.args[0])
                if key:
                    keys.add(key)
        if len(function_path) >= 3 and function_path[-3:-1] == ("os", "environ") and function_name in _ENV_METHODS:
            if statement.args:
                key = _constant_string(statement.args[0])
                if key:
                    keys.add(key)

    for statement in ast.walk(tree):
        if not isinstance(statement, ast.Subscript):
            continue
        if _attribute_path(statement.value)[-2:] != ("os", "environ"):
            continue
        slice_node = statement.slice
        key = _constant_string(slice_node)
        if key:
            keys.add(key)
    return {key for key in keys if _SAFE_IDENTIFIER.fullmatch(key)}


def _python_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for relative in ("config", "core", "webui"):
        directory = root / relative
        if directory.is_dir():
            paths.extend(sorted(directory.rglob("*.py")))
    for relative in ("main.py", "web.py"):
        path = root / relative
        if path.is_file():
            paths.append(path)
    return paths


def collect_application_env_keys(root: Path | str) -> set[str]:
    """Return all statically discoverable application environment keys."""
    project_root = Path(root).resolve()
    keys = set(_PROCESS_ENV_KEYS)
    for path in _python_files(project_root):
        keys.update(_collect_from_python(path))
    return keys


def _fallback_conninfo(raw: str) -> dict[str, str]:
    """Parse the small conninfo subset needed if psycopg is unavailable."""
    if "://" in raw:
        parsed = urlsplit(raw)
        values: dict[str, str] = {}
        if parsed.hostname:
            values["host"] = unquote(parsed.hostname)
        if parsed.port is not None:
            values["port"] = str(parsed.port)
        path_name = unquote((parsed.path or "").lstrip("/").split("/", 1)[0])
        if path_name:
            values["dbname"] = path_name
        for key, query_values in parse_qs(parsed.query, keep_blank_values=True).items():
            lowered = key.lower()
            if lowered in {"dbname", "database"} and query_values:
                values["dbname"] = unquote(query_values[-1])
        return values

    values = {}
    for token in shlex.split(raw):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        lowered = key.strip().lower()
        if lowered in {"host", "port", "dbname", "database"}:
            values["dbname" if lowered == "database" else lowered] = unquote(value)
    return values


def parse_conninfo(database_url: str) -> dict[str, str]:
    """Parse a PostgreSQL DSN so query overrides and escaped names are honored.

    ``psycopg`` delegates to libpq-compatible parsing and is preferred. The
    fallback only exists for unit tests that import this helper without the
    optional driver installed; it never reads a dotenv file.
    """
    raw = str(database_url or "").strip()
    if not raw:
        return {}
    try:
        from psycopg.conninfo import conninfo_to_dict

        parsed = conninfo_to_dict(raw)
        return {
            str(key).lower(): str(value)
            for key, value in parsed.items()
            if value is not None
        }
    except Exception:
        return _fallback_conninfo(raw)


def _database_name(database_url: str) -> str:
    parsed = parse_conninfo(database_url)
    return unquote(str(parsed.get("dbname") or parsed.get("database") or "")).strip().lower()


def validate_test_database_url(database_url: str) -> str:
    """Validate a test DSN and return a redacted ``host:port/database`` label."""
    raw = str(database_url or "").strip()
    try:
        uri = urlsplit(raw)
        conninfo = parse_conninfo(raw)
    except (ValueError, TypeError) as exc:
        raise TestEnvironmentError("DATABASE_URL 不是有效的 PostgreSQL 连接") from exc
    name = _database_name(raw)
    scheme = uri.scheme.lower()
    host = str(conninfo.get("host") or uri.hostname or "").strip().lower()
    if scheme not in {"postgres", "postgresql"} and "://" in raw:
        raise TestEnvironmentError("DATABASE_URL 必须是 PostgreSQL 测试连接")
    if not host or not name:
        raise TestEnvironmentError("DATABASE_URL 必须是带主机和数据库名的 PostgreSQL 测试连接")
    if name in _PRODUCTION_DATABASES:
        raise TestEnvironmentError(f"拒绝测试连接生产数据库 {name!r}")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise TestEnvironmentError("测试数据库必须连接本机 PostgreSQL 服务")
    try:
        port = int(str(conninfo.get("port") or uri.port or 5432))
    except (TypeError, ValueError) as exc:
        raise TestEnvironmentError("DATABASE_URL 的 PostgreSQL 端口无效") from exc
    if not 1 <= port <= 65535:
        raise TestEnvironmentError("DATABASE_URL 的 PostgreSQL 端口无效")
    return f"{host}:{port}/{name}"


def _validate_schema(schema: str) -> str:
    value = str(schema or "").strip()
    if not _SAFE_IDENTIFIER.fullmatch(value) or not value.startswith("test_"):
        raise TestEnvironmentError("TURB_DB_SCHEMA 必须是以 test_ 开头的独立测试 schema")
    return value


def build_isolated_environment(
    source_environment: dict[str, str] | None = None,
    *,
    database_url: str | None = None,
    schema: str | None = None,
    project_root: Path | str,
) -> dict[str, str]:
    """Build a sanitized subprocess environment without reading ``.env``."""
    source = dict(os.environ if source_environment is None else source_environment)
    configured_database = str(database_url if database_url is not None else source.get("DATABASE_URL") or "").strip()
    database_label = validate_test_database_url(configured_database)
    configured_schema = _validate_schema(schema or source.get("TURB_DB_SCHEMA") or f"test_runner_{os.getpid()}")
    root = Path(project_root).resolve()

    env = {
        key: value
        for key, value in source.items()
        if key not in collect_application_env_keys(root)
    }
    env.update(
        {
            "DATABASE_URL": configured_database,
            "TURB_DB_SCHEMA": configured_schema,
            "ACCOUNT_TASK_DB_SCHEMA": configured_schema,
            "TURB_ALLOW_PRODUCTION_DB": "0",
            "PYTHON_DOTENV_DISABLED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "COMPAT_EXPORT_MODE": "off",
            "PYTHONPATH": str(root),
        }
    )
    # Keep this local value in the function for easier inspection in callers
    # without ever returning the original DSN or printing it.
    env["TURB_TEST_DATABASE_LABEL"] = database_label
    return env


def _probe_database(environment: dict[str, str]) -> None:
    """Run one SELECT 1 against the explicitly selected non-production DB."""
    try:
        import psycopg
    except ImportError as exc:
        raise TestEnvironmentError("数据库集成测试缺少 psycopg，不能以 skip 代替失败") from exc

    try:
        with psycopg.connect(environment["DATABASE_URL"], connect_timeout=5, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    raise RuntimeError("SELECT 1 返回异常")
    except Exception as exc:
        label = environment.get("TURB_TEST_DATABASE_LABEL", "<redacted>")
        raise TestEnvironmentError(f"PostgreSQL 集成测试连接失败: {label} ({type(exc).__name__})") from exc


def _pytest_command(arguments: list[str]) -> list[str]:
    values = list(arguments)
    if values and values[0] == "--":
        values.pop(0)
    if not values:
        values = ["-q"]
    if len(values) >= 2 and values[:2] == ["-m", "pytest"]:
        return [sys.executable, *values]
    return [sys.executable, "-m", "pytest", *values]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="在独立 PostgreSQL 与无 dotenv 环境中运行 pytest")
    parser.add_argument("--database-url", help="独立测试数据库 DSN；默认读取已存在的进程环境")
    parser.add_argument("--schema", help="测试 schema，必须以 test_ 开头")
    parser.add_argument("--dry-run", action="store_true", help="只校验环境，不启动 pytest")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="传给 pytest 的参数")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        environment = build_isolated_environment(
            database_url=args.database_url,
            schema=args.schema,
            project_root=root,
        )
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "dotenv_disabled": environment["PYTHON_DOTENV_DISABLED"] == "1",
                        "schema": environment["TURB_DB_SCHEMA"],
                        "database": environment["TURB_TEST_DATABASE_LABEL"],
                        "application_env_keys_removed": len(
                            collect_application_env_keys(root)
                        ),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        _probe_database(environment)
    except TestEnvironmentError as exc:
        print(f"isolated test environment failed: {exc}", file=sys.stderr)
        return 2

    command = _pytest_command(args.pytest_args)
    completed = subprocess.run(command, cwd=root, env=environment, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
