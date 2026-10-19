"""Release, health, and database-safety checks for the isolated release tooling."""
from __future__ import annotations

import copy
import ast
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.release import (
    ReleaseError,
    check_release,
    prepare_release,
    rollback_release,
    switch_release,
)
from tools.test_performance import run_benchmark
from tools.test_isolated import TestEnvironmentError as IsolatedEnvironmentError
from tools.test_isolated import parse_conninfo, validate_test_database_url
from webui.routes import health


_RETIRED_ACCOUNT_FILES = (
    "注册任务.json",
    "注册成功的邮箱.json",
    "注册成功的邮箱.txt",
    "注册成功的token.txt",
    "注册成功整行.txt",
    "注册成功账号.json",
    "用于注册的邮箱.json",
    "用于注册的邮箱.txt",
    "用于注册的iCloud隐藏邮箱.json",
)


def _retired_source_references(path: Path, text: str, project_root: Path) -> list[str]:
    """只对显式历史 Profile 补录函数放行其单个只读历史来源。"""
    references = []
    for filename in _RETIRED_ACCOUNT_FILES:
        checked = text
        if path == project_root / "core" / "roxy_profile_binding.py" and filename == "注册成功的邮箱.json":
            lines = text.splitlines(keepends=True)
            for node in ast.parse(text).body:
                if isinstance(node, ast.FunctionDef) and node.name == "load_historical_profile_bindings":
                    # 该显式导入经存储 API 写回展示信息，不作为日常账号事实来源。
                    lines[node.lineno - 1:node.end_lineno] = ["\n"] * (node.end_lineno - node.lineno + 1)
            checked = "".join(lines)
        if filename in checked:
            references.append(f"{path}:{filename}")
    return references


def test_runtime_has_no_retired_root_file_io():
    """账号根快照和批次归档都只能作为历史数据，不得重新进入运行时。"""
    project_root = Path(__file__).resolve().parents[1]
    runtime_files = [
        *sorted((project_root / "core").rglob("*.py")),
        *sorted((project_root / "webui").rglob("*.py")),
        project_root / "main.py",
        project_root / "web.py",
        *sorted((project_root / "tools").glob("*.py")),
    ]
    violations = []
    for path in runtime_files:
        if path.name == "migrate_collections_to_tables.py":
            continue
        text = path.read_text(encoding="utf-8")
        violations.extend(_retired_source_references(path, text, project_root))
    assert violations == [], "retired root-file references: " + ", ".join(violations)


def test_historical_import_exception_does_not_allow_normal_runtime_file_reads():
    root = Path("/fixture")
    path = root / "core" / "roxy_profile_binding.py"
    importer = 'def load_historical_profile_bindings():\n    return "注册成功的邮箱.json"\n'
    assert _retired_source_references(path, importer, root) == []
    runtime = '\ndef normal_runtime():\n    return "注册成功的邮箱.json"\n'
    assert _retired_source_references(path, importer + runtime, root) == [f"{path}:注册成功的邮箱.json"]


def _runtime_status() -> dict:
    return {
        "ready": True,
        "started": True,
        "pid": 1234,
        "started_at": 1726310000.5,
        "executor": {"configured_workers": 4},
        "codex_dispatcher": {"started": True, "alive": True, "name": "codex"},
        "dependency_dispatcher": {"started": True, "alive": True, "name": "dependency"},
        "projection_worker": {"started": True, "alive": True, "name": "projection"},
    }


def test_runtime_status_requires_each_critical_worker():
    baseline = _runtime_status()
    assert health._runtime_check()["ok"] is False

    with patch.object(health.runtime, "runtime_status", return_value=baseline, create=True):
        assert health._runtime_check()["ok"] is True
        for component in ("codex_dispatcher", "dependency_dispatcher", "projection_worker"):
            dead = copy.deepcopy(baseline)
            dead[component]["alive"] = False
            with patch.object(health.runtime, "runtime_status", return_value=dead, create=True):
                result = health._runtime_check()
            assert result["ok"] is False
            assert result["workers"][component]["status"] == "not_ready"

            missing = copy.deepcopy(baseline)
            missing.pop(component)
            with patch.object(health.runtime, "runtime_status", return_value=missing, create=True):
                result = health._runtime_check()
            assert result["ok"] is False
            assert result["workers"][component]["status"] == "missing"

            errored = copy.deepcopy(baseline)
            errored[component]["error"] = "worker stopped"
            with patch.object(health.runtime, "runtime_status", return_value=errored, create=True):
                result = health._runtime_check()
            assert result["ok"] is False
            assert result["workers"][component]["status"] == "failed"


def test_runtime_ready_flag_does_not_override_dead_worker_or_executor_error():
    status = _runtime_status()
    status["projection_worker"]["alive"] = False
    with patch.object(health.runtime, "runtime_status", return_value=status, create=True):
        assert health._runtime_check()["ok"] is False

    status = _runtime_status()
    status["executor"] = {"error": "executor unavailable"}
    with patch.object(health.runtime, "runtime_status", return_value=status, create=True):
        result = health._runtime_check()
    assert result["ok"] is False
    assert result["executor"]["status"] == "failed"

    status = _runtime_status()
    status["ready"] = False
    with patch.object(health.runtime, "runtime_status", return_value=status, create=True):
        assert health._runtime_check()["ok"] is False


def test_health_endpoints_are_public_and_readiness_is_strict():
    from webui.app import create_app

    with patch.object(health, "_database_check", return_value={"ok": True, "status": "ok"}), patch.object(
        health.runtime, "runtime_status", return_value=_runtime_status(), create=True
    ):
        app = create_app(auth_code="health-test")
        client = app.test_client()
        assert client.get("/healthz").status_code == 200
        response = client.get("/readyz")
        assert response.status_code == 200
        assert response.get_json()["checks"]["runtime"]["workers"]["projection_worker"]["alive"] is True

    dead = _runtime_status()
    dead["projection_worker"]["alive"] = False
    with patch.object(health, "_database_check", return_value={"ok": True, "status": "ok"}), patch.object(
        health.runtime, "runtime_status", return_value=dead, create=True
    ):
        app = create_app(auth_code="health-test")
        response = app.test_client().get("/readyz")
    assert response.status_code == 503
    assert response.get_json()["ok"] is False


def test_database_guard_uses_decoded_uri_and_query_database_override():
    assert parse_conninfo(
        "postgresql://user:p@127.0.0.1:55432/path?dbname=turb_opt_20260914"
    )["dbname"] == "turb_opt_20260914"
    assert validate_test_database_url(
        "postgresql://user:p@127.0.0.1:55432/path?dbname=turb_opt_20260914"
    ).endswith("/turb_opt_20260914")

    for url in (
        "postgresql://user:p@127.0.0.1:55432/%74urb_console",
        "postgresql://user:p@127.0.0.1:55432/safe?dbname=turb_console",
        "host=127.0.0.1 port=55432 dbname=turb_console user=user password=p",
    ):
        with pytest.raises(IsolatedEnvironmentError):
            validate_test_database_url(url)


def test_performance_check_rejects_production_database(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:p@127.0.0.1:55432/safe?dbname=turb_console",
    )
    with pytest.raises(RuntimeError, match="不安全的测试数据库"):
        run_benchmark()


def _git_source(root: Path) -> Path:
    source = root / "source"
    source.mkdir()
    project_root = Path(__file__).resolve().parents[1]
    for name in ("requirements.in", "requirements-dev.in", "requirements.txt", "requirements-dev.txt", "pyproject.toml"):
        shutil.copy2(project_root / name, source / name)
    (source / "app.py").write_text("print('release')\n", encoding="utf-8")
    (source / ".env").write_text("PRIVATE_TOKEN=not-in-release\n", encoding="utf-8")
    (source / ".env.example").write_text("PUBLIC_EXAMPLE=1\n", encoding="utf-8")
    (source / "logs").mkdir()
    (source / "logs" / "private.log").write_text("private\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=release-test",
            "-c",
            "user.email=release-test@example.invalid",
            "commit",
            "-qm",
            "initial",
        ],
        cwd=source,
        check=True,
    )
    return source


def test_prepare_manifest_and_atomic_switch_are_recoverable(tmp_path):
    source = _git_source(tmp_path)
    releases = tmp_path / "releases"
    first = prepare_release(source, releases, "r1")
    second = prepare_release(source, releases, "r2")

    report = check_release(first, expected_release_id="r1")
    assert report["ok"] is True
    assert (first / ".env.example").is_file()
    assert not (first / ".env").exists()
    assert not (first / "logs").exists()
    assert (first / "release-manifest.json").is_file()

    current = tmp_path / "current"
    state = tmp_path / "state.json"
    switched = switch_release(releases, "r1", current_link=current, state_file=state)
    assert switched["previous_release"] is None
    assert current.resolve() == first.resolve()
    switch_release(releases, "r2", current_link=current, state_file=state)
    assert current.resolve() == second.resolve()
    rolled_back = rollback_release(releases, current_link=current, state_file=state)
    assert rolled_back["release_id"] == "r1"
    assert current.resolve() == first.resolve()

    (first / "app.py").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ReleaseError):
        check_release(first, expected_release_id="r1")
