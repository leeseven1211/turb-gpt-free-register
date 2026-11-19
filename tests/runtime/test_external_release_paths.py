"""固定包外运行目录、bootstrap 与历史文件接续的隔离回归。"""
from __future__ import annotations

import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.runtime.bootstrap import RuntimeBootstrap
from core.runtime.paths import compatibility_data_root, legacy_log_roots, runtime_dir, task_log_root
from tools import release as release_tool
from tools.render_release_manager import render_launchd_plist, render_systemd_unit

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_defaults_and_explicit_external_roots(tmp_path):
    assert runtime_dir(environment={}, project_root=tmp_path) == tmp_path / "logs/run"
    assert task_log_root(environment={}, legacy_default=tmp_path / "core/logs") == tmp_path / "core/logs"
    assert compatibility_data_root(tmp_path / "core", environment={}) == tmp_path / "core"
    environment = {"TURB_RUNTIME_DIR": str(tmp_path / "runtime")}
    assert runtime_dir(environment=environment) == tmp_path / "runtime"
    assert task_log_root(environment=environment) == tmp_path / "runtime/logs"
    assert compatibility_data_root(tmp_path / "core", environment=environment) == tmp_path / "runtime/compat"
    environment["TASK_RUN_LOG_ROOT"] = str(tmp_path / "shared/logs")
    assert task_log_root(environment=environment) == tmp_path / "shared/logs"
    for key in ("TURB_RUNTIME_DIR", "TASK_RUN_LOG_ROOT"):
        with pytest.raises(ValueError, match="absolute_required"):
            task_log_root(environment={key: "relative"})


def test_explicit_combined_prepares_external_logs():
    def git_result(command, **_kwargs):
        return SimpleNamespace(stdout="/project" if "--show-toplevel" in command else "a" * 40)
    with patch("core.runtime.bootstrap.subprocess.run", side_effect=git_result):
        bootstrap = RuntimeBootstrap.from_environment(
            project_root=Path("/project"), environment={"TURB_RUNTIME_DIR": "/stable"},
        )
    environment = {}
    bootstrap.prepare_log_environment(environment)
    assert environment["TASK_RUN_LOG_ROOT"] == "/stable/logs"


@pytest.mark.parametrize("key", ["TURB_RUNTIME_DIR", "TASK_RUN_LOG_ROOT"])
def test_split_rejects_paths_in_source_package(tmp_path, key):
    environment = {"TURB_RUNTIME_MODE": "worker", "TURB_RUNTIME_DIR": str(tmp_path.parent / "stable")}
    environment[key] = str(tmp_path / "mutable")
    with pytest.raises(ValueError, match="must_be_external"):
        RuntimeBootstrap.from_environment(project_root=tmp_path, environment=environment)


def test_bootstrap_env_reads_writes_and_locks_one_external_file(tmp_path, monkeypatch):
    from config import env_loader, runtime
    private_env = tmp_path / "shared/bootstrap.env"
    private_env.parent.mkdir()
    private_env.write_text('BASE_VALUE="kept"\n', encoding="utf-8")
    decoy = tmp_path / "release/.env"
    monkeypatch.setattr(env_loader, "_ENV_PATH", decoy)
    monkeypatch.setenv("TURB_BOOTSTRAP_ENV_FILE", str(private_env))
    monkeypatch.setenv("WEBUI_AUTH_CODE", "before-isolated-write")
    monkeypatch.setattr(env_loader, "load_env", lambda **_kwargs: private_env)
    assert runtime.is_bootstrap_key("TURB_BOOTSTRAP_ENV_FILE")
    assert env_loader.env_path() == private_env
    with env_loader.env_file_lock():
        # 同一事务不能因进程环境变化而把后续写入重定向到别处。
        monkeypatch.setenv("TURB_BOOTSTRAP_ENV_FILE", str(tmp_path / "missing.env"))
        env_loader.write_env_values({"WEBUI_AUTH_CODE": "isolated-test-only"})
        assert env_loader.read_env_file()["BASE_VALUE"] == "kept"
    assert (private_env.parent / "bootstrap.env.lock").is_file()
    assert private_env.stat().st_mode & 0o777 == 0o600
    assert not decoy.exists()
    assert not (tmp_path / "release/.env.lock").exists()


@pytest.mark.parametrize("value, code", [
    ("relative.env", "bootstrap_env_file_absolute_required"),
    ("/nonexistent/turb-isolated-bootstrap.env", "bootstrap_env_file_missing"),
])
def test_explicit_bootstrap_never_falls_back_to_package(value, code, monkeypatch):
    from config import env_loader
    monkeypatch.setenv("TURB_BOOTSTRAP_ENV_FILE", value)
    with pytest.raises(ValueError, match=code):
        env_loader.read_env_file()


def test_external_bootstrap_keeps_active_database_runtime_projection(tmp_path):
    from cryptography.fernet import Fernet
    from core.storage import runtime_config as repository
    from tests.support_pg import database_available, drop_schema, temporary_schema_name
    if not database_available():
        pytest.skip("需要隔离 PostgreSQL")
    schema = temporary_schema_name("external_bootstrap")
    key = Fernet.generate_key().decode("ascii")
    private_env = tmp_path / "shared.env"
    private_env.write_text(
        f'TURB_DB_SCHEMA="{schema}"\nTURB_CONFIG_ENCRYPTION_KEY="{key}"\n'
        'WEBUI_AUTH_CODE="isolated-only"\nACCOUNT_PLAN_CHECK_WORKERS="2"\n',
        encoding="utf-8",
    )
    with patch.dict(os.environ, {"TURB_DB_SCHEMA": schema, "TURB_CONFIG_ENCRYPTION_KEY": key}):
        try:
            repository.write_values({"ACCOUNT_PLAN_CHECK_WORKERS": "6"}, activate=True, source="test")
            child_environment = {
                **os.environ, "TURB_BOOTSTRAP_ENV_FILE": str(private_env),
                "PYTHON_DOTENV_DISABLED": "0",
            }
            for name in ("TURB_DB_SCHEMA", "TURB_CONFIG_ENCRYPTION_KEY", "ACCOUNT_PLAN_CHECK_WORKERS"):
                child_environment.pop(name, None)
            script = r'''
import config, sys
from pathlib import Path
from config import env_loader, runtime
assert env_loader.env_path() == Path(sys.argv[1])
assert config.ACCOUNT_PLAN_CHECK_WORKERS == 6
runtime.write_persisted_values({"WEBUI_SESSION_SECRET": "isolated-session"})
assert env_loader.read_env_file()["WEBUI_SESSION_SECRET"] == "isolated-session"
assert config.ACCOUNT_PLAN_CHECK_WORKERS == 6
'''
            result = subprocess.run(
                [sys.executable, "-B", "-c", script, str(private_env)],
                cwd=ROOT, env=child_environment, capture_output=True, text=True, timeout=30,
            )
            # 不回显潜在配置输出；退出码断言仅证明受控测试是否完成。
            assert result.returncode == 0, "外置 bootstrap 数据库投影测试失败"
            assert private_env.stat().st_mode & 0o777 == 0o600
        finally:
            drop_schema(schema)


def test_renderer_maps_private_bootstrap_and_keeps_secret_off_argv(tmp_path):
    bootstrap = tmp_path / "shared/.env"
    output = tmp_path / "private-config/worker.plist"
    render_launchd_plist(
        ROOT / "deploy/launchd/local.turb.worker.plist.example", output,
        release_dir=tmp_path / "release", interpreter=tmp_path / "venv/bin/python", instance="local-main",
        runtime_dir=tmp_path / "runtime", task_log_dir=tmp_path / "shared/logs",
        logs_dir=tmp_path / "manager-logs", bootstrap_env_file=bootstrap,
        environment_overrides={"WEBUI_AUTH_CODE": "isolated-test-only"},
    )
    value = plistlib.loads(output.read_bytes())
    assert value["EnvironmentVariables"]["TURB_BOOTSTRAP_ENV_FILE"] == str(bootstrap)
    assert "PYTHON_DOTENV_DISABLED" not in value["EnvironmentVariables"]
    assert all("isolated-test-only" not in argument for argument in value["ProgramArguments"])
    assert output.stat().st_mode & 0o777 == 0o600
    assert output.parent.stat().st_mode & 0o777 == 0o700
    unit = tmp_path / "private-config/web.service"
    render_systemd_unit(
        ROOT / "deploy/systemd/turb-web@.service", unit,
        release_dir=tmp_path / "release", interpreter=tmp_path / "venv/bin/python",
        instance="local-main", bootstrap_env_file=bootstrap,
    )
    assert f"EnvironmentFile={bootstrap}" in unit.read_text()
    assert f"Environment=TURB_BOOTSTRAP_ENV_FILE={bootstrap}" in unit.read_text()
    assert unit.stat().st_mode & 0o777 == 0o600


def test_legacy_log_allowlist_maps_writes_and_blocks_escape(tmp_path, monkeypatch):
    from core.operations import run_log
    shared = tmp_path / "shared"
    old = tmp_path / "old-release/logs"
    old.mkdir(parents=True)
    historical = old / "example.log"
    historical.write_text("history", encoding="utf-8")
    monkeypatch.setattr(run_log, "_LOG_ROOT", shared)
    monkeypatch.setattr(run_log, "_ADDITIONAL_LEGACY_LOG_ROOTS", (old,))
    assert run_log.resolve_path(historical) == historical
    assert run_log.resolve_path(historical, for_write=True) == shared / "example.log"
    shared.mkdir()
    (shared / "example.log").write_text("continued", encoding="utf-8")
    assert run_log.resolve_path(historical) == shared / "example.log"
    escaped = tmp_path / "escaped.log"
    escaped.write_text("private", encoding="utf-8")
    (old / "symlink.log").symlink_to(escaped)
    (shared / "unsafe.log").symlink_to(escaped)
    for path in (old / "../escaped.log", old / "symlink.log", old / "unsafe.log"):
        with pytest.raises(ValueError, match="受控目录"):
            run_log.resolve_path(path, for_write=True)
    assert legacy_log_roots(environment={"TURB_LEGACY_LOG_ROOTS": json.dumps([str(old)])}) == (old,)
    for value in ("relative", '["relative"]', '{"wrong":"shape"}'):
        with pytest.raises(ValueError):
            legacy_log_roots(environment={"TURB_LEGACY_LOG_ROOTS": value})


def test_legacy_debug_artifacts_are_readable_without_deleting_source(tmp_path, monkeypatch):
    from core.registration import debug
    shared = tmp_path / "shared/debug"
    old = tmp_path / "old-release/logs/debug"
    artifact = old / "job-1"
    artifact.mkdir(parents=True)
    (artifact / "last-page.json").write_text('{"status":"historical"}', encoding="utf-8")
    monkeypatch.setattr(debug, "_ARTIFACT_ROOT", shared)
    monkeypatch.setattr(debug, "_ADDITIONAL_LEGACY_ARTIFACT_ROOTS", (old,))
    job = {"debug_artifact_dir": str(artifact)}
    assert debug.read_page_state(job) == {"status": "historical"}
    debug.delete_job_artifacts(job)
    assert artifact.is_dir()
    escaped = tmp_path / "escaped"
    escaped.mkdir()
    (old / "symlink").symlink_to(escaped, target_is_directory=True)
    with pytest.raises(ValueError, match="允许目录"):
        debug._artifact_dir_for_job({"debug_artifact_dir": str(old / "symlink")})


def _make_minimal_release(root: Path) -> None:
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.10"\n', encoding="utf-8")
    for name in ("requirements.txt", "requirements-dev.txt", "requirements.in", "requirements-dev.in"):
        shutil.copyfile(ROOT / name, root / name)
    files = [
        {"path": path.name, "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(root.iterdir())
    ]
    locks = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in release_tool.LOCK_NAMES}
    manifest = release_tool._manifest_for(root.name, "b" * 40, files, locks)
    (root / release_tool.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")


def test_repeated_bootstrap_preserves_archive_registry_and_package_manifest(tmp_path):
    """两次独立解释器模拟启动；不是正式服务或数据库验收。"""
    package = tmp_path / "isolated-release"
    _make_minimal_release(package)
    bootstrap_file = tmp_path / "bootstrap.env"
    bootstrap_file.write_text('BASE_VALUE="kept"\n', encoding="utf-8")
    environment = {
        **os.environ, "PYTHONDONTWRITEBYTECODE": "1",
        "TURB_RUNTIME_MODE": "worker", "TURB_RUNTIME_DIR": str(tmp_path / "runtime"),
        "TASK_RUN_LOG_ROOT": str(tmp_path / "shared-logs"),
        "TURB_BOOTSTRAP_ENV_FILE": str(bootstrap_file),
    }
    script = r'''
import json, sys
from pathlib import Path
from core.runtime.bootstrap import RuntimeBootstrap
root = Path(sys.argv[1])
runtime = RuntimeBootstrap.from_environment(project_root=root)
runtime.prepare_log_environment()
from core.operations import retention
from core.browser.roxy import client
from core.registration import debug
from core.storage import db_legacy
from config import env_loader
assert env_loader.read_env_file()["BASE_VALUE"] == "kept"
env_loader.load_env = lambda **kwargs: env_loader.env_path()
env_loader.write_env_values({"WEBUI_SESSION_SECRET": "isolated-value"})
items = client._load_profile_registry_locked()
if not items:
    items = [{"profile_id": "isolated-profile", "disposable": True}]
    client._save_profile_registry_locked(items)
assert len(items) == 1
retention.archive_snapshot({"tasks": [{"id": 1, "state": "success"}]})
debug._ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
(debug._ARTIFACT_ROOT / "isolated.log").write_text("test")
db_legacy._ensure_storage()
from tools.release import check_release
assert check_release(root)["ok"]
assert RuntimeBootstrap.from_environment(project_root=root).release == "b" * 40
print(json.dumps({"registry": len(items), "archives": len(list(retention._ARCHIVE_ROOT.glob("*.json.gz")))}))
'''
    reports = []
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, str(package)], cwd=ROOT, env=environment,
            capture_output=True, text=True, check=True, timeout=30,
        )
        reports.append(json.loads(result.stdout))
    assert reports == [{"registry": 1, "archives": 1}, {"registry": 1, "archives": 2}]
    assert release_tool.check_release(package)["ok"]
    assert not (package / "logs").exists()
    assert not (package / ".env").exists()
