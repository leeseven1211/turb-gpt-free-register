"""Oracle 部署引擎的定向回归测试。"""
from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from tools import deploy_oracle


def test_restore_old_tree_preserves_history_and_creates_a_verified_recovery_commit(tmp_path):
    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(tmp_path), *arguments], text=True).strip()

    git("init", "-q")
    git("config", "user.name", "部署测试")
    git("config", "user.email", "deploy-test@example.invalid")
    git("config", "commit.gpgsign", "false")
    git("config", "core.hooksPath", "/dev/null")
    code = tmp_path / "web.py"
    code.write_text("旧版")
    git("add", ".")
    git("commit", "-qm", "feat: 旧版")
    old = git("rev-parse", "HEAD")
    code.write_text("新版")
    git("add", ".")
    git("commit", "-qm", "feat: 新版")
    target = git("rev-parse", "HEAD")

    restored = deploy_oracle._restore_old_tree(source=tmp_path, old_commit=old, target=target)

    assert restored not in (None, old, target)
    assert git("rev-parse", "HEAD^") == target
    assert git("rev-parse", "HEAD^{tree}") == git("rev-parse", f"{old}^{{tree}}")
    assert code.read_text() == "旧版"
    assert git("status", "--porcelain") == ""


def test_deploy_oracle_rejects_dirty_tree_before_service_control(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    calls: list[tuple[str, ...]] = []

    def fake_git(_source: Path, *args: str) -> str:
        calls.append(args)
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return " M web.py"
        raise AssertionError(f"不应读取脏树之后的 Git 状态: {args}")

    monkeypatch.setattr(deploy_oracle, "_git", fake_git)
    monkeypatch.setattr(deploy_oracle, "_backup_receipt", lambda **kwargs: None)
    monkeypatch.setattr(
        deploy_oracle,
        "_systemctl",
        lambda *args, **kwargs: pytest.fail("脏树不应操作 systemd"),
    )

    with pytest.raises(deploy_oracle.DeployError, match="dirty_worktree"):
        deploy_oracle.deploy_oracle(
            source=source,
            revision="target",
            receipt_dir=tmp_path / "receipt",
        )

    assert calls == [("status", "--porcelain", "--untracked-files=all")]


def test_deploy_oracle_rejects_non_fast_forward_before_service_control(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    calls: list[tuple[str, ...]] = []

    def fake_git(_source: Path, *args: str) -> str:
        calls.append(args)
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return ""
        if args == ("rev-parse", "HEAD"):
            return "old-full"
        if args == ("rev-parse", "--verify", "target^{commit}"):
            return "target-full"
        if args == ("merge-base", "--is-ancestor", "HEAD", "target-full"):
            raise deploy_oracle.DeployOracleError("不是祖先", "not_fast_forward")
        raise AssertionError(f"非快进检查不应继续: {args}")

    monkeypatch.setattr(deploy_oracle, "_git", fake_git)
    monkeypatch.setattr(
        deploy_oracle,
        "_systemctl",
        lambda *args, **kwargs: pytest.fail("非快进目标不应操作 systemd"),
    )

    with pytest.raises(deploy_oracle.DeployOracleError) as caught:
        deploy_oracle.deploy_oracle(
            source=source,
            revision="target",
            receipt_dir=tmp_path / "receipt",
        )

    assert caught.value.code == "not_fast_forward"
    assert not any(call[:1] == ("merge",) for call in calls)


def test_deploy_oracle_static_change_merges_without_restart(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    events: list[tuple[str, ...]] = []

    def fake_git(_source: Path, *args: str) -> str:
        if args == ("rev-parse", "--verify", "target^{commit}"):
            return "target-full"
        if args == ("rev-parse", "HEAD"):
            return "old-full"
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return ""
        if args == ("merge-base", "--is-ancestor", "HEAD", "target-full"):
            return ""
        if args == ("diff", "--name-only", "HEAD", "target-full"):
            return "webui/static/app.js\ndocs/deploy.md\n"
        if args == ("merge", "--ff-only", "target-full"):
            events.append(args)
            return ""
        raise AssertionError(f"未覆盖的 Git 调用: {args}")

    monkeypatch.setattr(deploy_oracle, "_git", fake_git)
    monkeypatch.setattr(deploy_oracle, "_backup_receipt", lambda **kwargs: None)
    monkeypatch.setattr(
        deploy_oracle,
        "_systemctl",
        lambda *args, **kwargs: pytest.fail("静态部署不应重启服务"),
    )
    monkeypatch.setattr(
        deploy_oracle,
        "_service_health",
        lambda **kwargs: {"healthz": 200, "readyz": 200, "login": 200},
    )

    result = deploy_oracle.deploy_oracle(
        source=source,
        revision="target",
        receipt_dir=tmp_path / "receipt",
        action="static",
    )

    assert events == [("merge", "--ff-only", "target-full")]
    assert result["action"] == "static"
    assert result["restarted"] is False
    assert "backend_commit" not in result
    assert result["http"] == {
        "ok": True,
        "paths": ["/healthz", "/readyz", "/login"],
    }


def test_deploy_oracle_start_failure_attempts_service_recovery_without_revert(
    tmp_path, monkeypatch
):
    source = tmp_path / "source"
    source.mkdir()
    systemd_calls: list[tuple[str, ...]] = []
    git_calls: list[tuple[str, ...]] = []
    starts = iter([True, False, False])
    merged = False

    def fake_git(_source: Path, *args: str) -> str:
        nonlocal merged
        git_calls.append(args)
        if args == ("rev-parse", "--verify", "target^{commit}"):
            return "target-full"
        if args == ("rev-parse", "HEAD"):
            return "target-full" if merged else "old-full"
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return ""
        if args == ("merge-base", "--is-ancestor", "HEAD", "target-full"):
            return ""
        if args == ("diff", "--name-only", "HEAD", "target-full"):
            return "web.py\n"
        if args == ("merge", "--ff-only", "target-full"):
            merged = True
            return ""
        raise AssertionError(f"未覆盖的 Git 调用: {args}")

    def fake_systemctl(*args: str, **kwargs) -> str:
        systemd_calls.append(args)
        if args[:1] == ("start",):
            if next(starts):
                return ""
            raise deploy_oracle.DeployError("启动失败")
        return ""

    monkeypatch.setattr(deploy_oracle, "_git", fake_git)
    monkeypatch.setattr(deploy_oracle, "_backup_receipt", lambda **kwargs: None)
    monkeypatch.setattr(deploy_oracle, "_systemctl", fake_systemctl)
    monkeypatch.setattr(
        deploy_oracle,
        "_service_state",
        lambda: {"MainPID": "123", "Result": "success", "ExecMainStatus": "0"},
    )
    monkeypatch.setattr(deploy_oracle, "_require_idle", lambda source: {})
    monkeypatch.setattr(deploy_oracle, "_stop_and_verify", lambda **kwargs: None)
    monkeypatch.setattr(
        deploy_oracle,
        "_start_and_verify",
        lambda **kwargs: (_ for _ in ()).throw(
            deploy_oracle.DeployError("健康检查失败", "service_not_ready")
        ),
    )

    with pytest.raises(deploy_oracle.DeployError, match="service_not_ready"):
        deploy_oracle.deploy_oracle(
            source=source,
            revision="target",
            receipt_dir=tmp_path / "receipt",
        )

    assert ("merge", "--ff-only", "target-full") in git_calls
    assert all(call[:1] != ("revert",) for call in git_calls)
    assert systemd_calls == [("start", deploy_oracle.SERVICE_NAME)]
