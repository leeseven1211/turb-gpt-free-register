"""统一部署入口的定向回归，不连接数据库或操作真实进程。"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/deploy.py"


def test_cli_help_is_read_only_and_available():
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "--apply" in result.stdout
    assert "--check" in result.stdout
    assert "--http-threads" in result.stdout


@pytest.mark.parametrize(
    ("arguments", "error"),
    [
        (["local", "--http-threads", "0"], "deployment_http_threads_invalid"),
        (["local", "--http-threads", "129"], "deployment_http_threads_invalid"),
        (["oracle", "--http-threads", "16"], "deployment_http_threads_local_only"),
    ],
)
def test_http_threads_rejects_invalid_scope_without_service_access(arguments, error, capsys):
    from tools import deploy

    assert deploy.main(arguments) == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == error


def test_explicit_local_http_threads_plans_restart_even_without_code_changes(tmp_path, monkeypatch):
    from tools import deploy

    monkeypatch.setattr(deploy, "git", lambda *args: "" if args[1] in {"status", "diff"} else "a" * 40)
    monkeypatch.setattr(deploy, "local_layout", lambda: {"backend_commit": "a" * 40})
    args = deploy.parser().parse_args(["local", "--source", str(tmp_path), "--http-threads", "16"])
    plan = deploy.build_plan(args)
    assert plan["action"] == "restart"
    assert plan["http_threads"] == 16


@pytest.mark.parametrize(
    ("paths", "fixed_release", "expected"),
    [
        ([], True, "noop"),
        (["README.md", "tests/tools/test_deploy.py", "tools/deploy.py"], True, "noop"),
        (["webui/static/task-center/accounts.js"], False, "static"),
        (["webui/static/task-center/accounts.js"], True, "restart"),
        (["webui/static/task-center/accounts.js", "core/accounts/plan.py"], False, "restart"),
        (["webui/templates/index.html"], False, "restart"),
        (["config/account.py"], False, "restart"),
    ],
)
def test_change_classification_preserves_hot_reload_boundaries(paths, fixed_release, expected):
    from tools.deploy import classify_changes

    assert classify_changes(paths, fixed_release=fixed_release) == expected


def test_remote_transport_keeps_shell_metacharacters_as_path_data():
    from tools.deploy import remote_command

    source = "/srv/apps/turb's $(touch /tmp/unwanted)"
    command = remote_command("oracle", source, ["oracle", "--on-host", "--source", source])
    import shlex

    argv = shlex.split(command[-1])
    assert argv[0] == source + "/.venv/bin/python"
    assert argv[-1] == source
    assert command[:2] == ["ssh", "-o"]


def test_noop_apply_does_not_import_or_run_cutover(tmp_path, monkeypatch):
    from tools import deploy

    result = {
        "target": "local", "source_commit": "a" * 40,
        "backend_commit": "b" * 40, "action": "noop", "changed_paths": ["README.md"],
    }
    monkeypatch.setattr(deploy, "build_plan", lambda args: result)
    monkeypatch.setattr(deploy, "verify_http", lambda *args, **kwargs: {"ok": True})
    assert deploy.main(["local", "--source", str(tmp_path), "--apply"]) == 0
    state = json.loads((tmp_path / "logs/run/deploy/local/last-success.json").read_text())
    assert state["backend_commit"] == "b" * 40
    assert state["action"] == "noop"


def test_dependency_probe_honors_target_platform_markers_and_missing_packages():
    from tools.deploy import DeployError, check_dependency_environment

    package = "turb-deploy-package-does-not-exist==1.0"
    check_dependency_environment(sys.executable, package + "; python_version < '1'")
    with pytest.raises(DeployError, match="deployment_dependency_environment_mismatch"):
        check_dependency_environment(sys.executable, package)


def test_previously_published_static_files_are_not_republished_as_new_changes(tmp_path, monkeypatch):
    from argparse import Namespace
    from tools import deploy

    def run_git(*arguments):
        return subprocess.check_output(["git", "-C", str(tmp_path), *arguments], text=True).strip()

    run_git("init", "-q")
    run_git("config", "user.name", "部署测试")
    run_git("config", "user.email", "deploy-test@example.invalid")
    run_git("config", "commit.gpgsign", "false")
    run_git("config", "core.hooksPath", "/dev/null")
    (tmp_path / "README.md").write_text("初版")
    run_git("add", ".")
    run_git("commit", "-qm", "docs: 初版")
    backend = run_git("rev-parse", "HEAD")
    (tmp_path / "webui/static").mkdir(parents=True)
    (tmp_path / "webui/static/app.js").write_text("console.log('更新')")
    run_git("add", ".")
    run_git("commit", "-qm", "feat: 静态更新")
    published = run_git("rev-parse", "HEAD")
    monkeypatch.setattr(deploy, "oracle_identity", lambda: {"pid": 123, "process_start": "同一进程"})
    monkeypatch.setattr(deploy, "read_state", lambda *args: {
        "pid": 123, "process_start": "同一进程", "backend_commit": backend, "source_commit": published,
    })
    plan = deploy.build_plan(Namespace(
        source=str(tmp_path), revision=None, target="oracle", restart=False,
    ))
    assert plan["action"] == "noop"
    assert plan["changed_paths"] == []
    assert plan["backend_commit"] == backend
