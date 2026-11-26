from __future__ import annotations

import plistlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tools import deploy_local


def _plist(label: str, role: str, current: Path, interpreter: Path) -> dict:
    arguments = [str(interpreter), str(current / f"{role}.py")]
    if role == "web":
        arguments += ["--port", "8000"]
    arguments += ["--shutdown-timeout", "55"]
    return {
        "Label": label,
        "ProgramArguments": arguments,
        "WorkingDirectory": str(current),
        "EnvironmentVariables": {
            "TURB_RUNTIME_MODE": role,
            "TURB_RUNTIME_DIR": "/private/runtime",
            "TASK_RUN_LOG_ROOT": "/private/task-logs",
            "TURB_BOOTSTRAP_ENV_FILE": "/private/bootstrap.env",
            "WEBUI_AUTH_CODE": "keep-me",
        },
        "StandardOutPath": f"/private/logs/{role}.stdout.log",
        "StandardErrorPath": f"/private/logs/{role}.stderr.log",
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 5,
    }


def test_retarget_plist_only_changes_release_entrypoint_and_optional_interpreter(
    tmp_path: Path,
) -> None:
    current = tmp_path / "current"
    release = tmp_path / "release"
    current.mkdir()
    release.mkdir()
    interpreter = Path("/opt/python/bin/python")
    original = _plist("com.example.web", "web", current, Path("/opt/old/python"))

    updated = deploy_local._retarget_plist(
        original,
        role="web",
        release=release,
        interpreter=interpreter,
    )

    assert updated["WorkingDirectory"] == str(release)
    assert updated["ProgramArguments"][0] == str(interpreter)
    assert updated["ProgramArguments"][1] == str(release / "web.py")
    assert updated["ProgramArguments"][2:] == original["ProgramArguments"][2:]
    assert updated["EnvironmentVariables"] == original["EnvironmentVariables"]
    assert updated["StandardOutPath"] == original["StandardOutPath"]
    assert updated["StandardErrorPath"] == original["StandardErrorPath"]
    assert original["WorkingDirectory"] == str(current)
    assert original["ProgramArguments"][1] == str(current / "web.py")


def test_deploy_local_stops_and_starts_in_role_order_and_writes_sanitized_receipt(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    release = tmp_path / "release"
    plist_dir = tmp_path / "LaunchAgents"
    receipt_dir = tmp_path / "receipts"
    source.mkdir()
    release.mkdir()
    plist_dir.mkdir()
    (source / "web.py").write_text("# web\n")
    (source / "worker.py").write_text("# worker\n")
    (release / "web.py").write_text("# web\n")
    (release / "worker.py").write_text("# worker\n")
    interpreter = Path("/opt/python/bin/python")
    for role in ("web", "worker"):
        label = deploy_local.LABELS[role]
        (plist_dir / f"{label}.plist").write_bytes(
            plistlib.dumps(_plist(label, role, source, interpreter))
        )

    calls: list[tuple[str, str]] = []
    loaded = {"web": True, "worker": True}

    def fake_command(arguments, **_kwargs):
        if arguments[0] == "lsof":
            return SimpleNamespace(returncode=1, stdout="")
        action = arguments[1] if arguments[:1] == ["launchctl"] else ""
        role = "web" if "web" in " ".join(arguments) else "worker"
        calls.append((action, role))
        if action == "bootout":
            loaded[role] = False
        elif action == "bootstrap":
            loaded[role] = True
        if action == "print" and not loaded[role]:
            return SimpleNamespace(returncode=1, stdout="")
        pid = 101 if role == "web" else 202
        return SimpleNamespace(returncode=0, stdout=f"pid = {pid}\n")

    def fake_inspect(pid):
        role = "web" if pid == 101 else "worker"
        if not loaded[role]:
            return None
        working = plistlib.loads(
            (plist_dir / f"{deploy_local.LABELS[role]}.plist").read_bytes()
        )["WorkingDirectory"]
        return SimpleNamespace(pid=pid, cwd=working, command=f"{role}.py")

    def fake_identity(role, _config):
        config = plistlib.loads(
            (plist_dir / f"{deploy_local.LABELS[role]}.plist").read_bytes()
        )
        return {
            "role": role,
            "pid": 101 if role == "web" else 202,
            "cwd": config["WorkingDirectory"],
            "release": "newsha123" if Path(config["WorkingDirectory"]) == release else "oldsha123",
        }

    with (
        patch.object(deploy_local, "MANAGER_DIR", plist_dir),
        patch.object(
            deploy_local,
            "_check_release",
            side_effect=[
                {"source_commit": "newsha123"},
                {"source_commit": "oldsha123"},
            ],
        ),
        patch.object(deploy_local, "_inspect_process", side_effect=fake_inspect),
        patch.object(deploy_local, "_run_command", side_effect=fake_command),
        patch.object(deploy_local, "_readiness", return_value=True),
        patch.object(deploy_local, "_idle_snapshot", return_value={"idle": True}),
        patch.object(deploy_local, "_current_identity", side_effect=fake_identity),
    ):
        result = deploy_local.deploy_local(
            source=source,
            release=release,
            receipt_dir=receipt_dir,
            interpreter=interpreter,
            timeout=10,
        )

    assert result["ok"] is True
    assert result["release"] == "newsha123"
    assert set(result) == {"ok", "release", "status", "pids", "http", "engine_receipt"}
    assert result["http"] == {"ok": True, "paths": []}
    assert [role for action, role in calls if action == "bootout"] == ["web", "worker"]
    assert [role for action, role in calls if action == "bootstrap"] == ["worker", "web"]
    receipt = Path(result["engine_receipt"])
    assert receipt.is_file()
    payload = receipt.read_text()
    assert "WEBUI_AUTH_CODE" not in payload
    assert "keep-me" not in payload


def test_deploy_local_restores_original_plists_when_bootstrap_fails(tmp_path: Path) -> None:
    source = tmp_path / "source"
    release = tmp_path / "release"
    plist_dir = tmp_path / "LaunchAgents"
    receipt_dir = tmp_path / "receipts"
    source.mkdir()
    release.mkdir()
    plist_dir.mkdir()
    (source / "web.py").write_text("# web\n")
    (source / "worker.py").write_text("# worker\n")
    (release / "web.py").write_text("# web\n")
    (release / "worker.py").write_text("# worker\n")
    originals = {}
    for role in ("web", "worker"):
        label = deploy_local.LABELS[role]
        path = plist_dir / f"{label}.plist"
        originals[role] = plistlib.dumps(_plist(label, role, source, Path("/opt/python/bin/python")))
        path.write_bytes(originals[role])

    command_calls: list[tuple[str, str]] = []

    def failing_command(arguments, **_kwargs):
        action = arguments[1]
        role = "web" if "web" in " ".join(arguments) else "worker"
        command_calls.append((action, role))
        if action == "bootstrap" and role == "web":
            return SimpleNamespace(returncode=1, stdout="", stderr="failed")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    loaded = {"web": True, "worker": True}

    def fake_command_with_state(arguments, **_kwargs):
        if arguments[0] == "lsof":
            return SimpleNamespace(returncode=1, stdout="")
        action = arguments[1]
        role = "web" if "web" in " ".join(arguments) else "worker"
        command_calls.append((action, role))
        if action == "bootout":
            loaded[role] = False
        elif action == "bootstrap" and not (role == "web" and loaded.get("worker") is False):
            loaded[role] = True
        if action == "print" and not loaded[role]:
            return SimpleNamespace(returncode=1, stdout="")
        if action == "bootstrap" and role == "web":
            return SimpleNamespace(returncode=1, stdout="", stderr="failed")
        pid = 101 if role == "web" else 202
        return SimpleNamespace(returncode=0, stdout=f"pid = {pid}\n", stderr="")

    with (
        patch.object(deploy_local, "MANAGER_DIR", plist_dir),
        patch.object(
            deploy_local,
            "_check_release",
            side_effect=[
                {"source_commit": "newsha123"},
                {"source_commit": "oldsha123"},
            ],
        ),
        patch.object(deploy_local, "_run_command", side_effect=fake_command_with_state),
        patch.object(deploy_local, "_inspect_process", return_value=None),
        patch.object(deploy_local, "_idle_snapshot", return_value={"idle": True}),
        patch.object(deploy_local, "_readiness", return_value=True),
        patch.object(
            deploy_local,
            "_current_identity",
            side_effect=lambda role, _config: {
                "role": role,
                "pid": 101 if role == "web" else 202,
                "cwd": str(source),
                "release": "oldsha123",
            },
        ),
        patch.object(deploy_local, "_identity_matches", return_value=True),
    ):
        with pytest.raises(deploy_local.DeployError, match="bootstrap_failed"):
            deploy_local.deploy_local(
                source=source,
                release=release,
                receipt_dir=receipt_dir,
                timeout=10,
            )

    for role in ("web", "worker"):
        path = plist_dir / f"{deploy_local.LABELS[role]}.plist"
        assert path.read_bytes() == originals[role]
    assert ("bootstrap", "worker") in command_calls
    assert ("bootstrap", "web") in command_calls
    receipts = list(receipt_dir.glob("deploy-*.json"))
    assert len(receipts) == 1
    assert '"error_code": "bootstrap_failed"' in receipts[0].read_text()


def test_rollback_wait_rejects_false_readiness_payload() -> None:
    task = object.__new__(deploy_local._Deployment)
    task.deadline = 1.0
    task.configs = {"web": {}}
    task.old_release = Path("/old")
    task.previous = "oldsha123"
    with (
        patch.object(deploy_local.time, "monotonic", side_effect=[0.0, 0.0, 0.0, 1.0]),
        patch.object(deploy_local.time, "sleep"),
        patch.object(deploy_local, "_readiness", return_value={"ok": False}),
    ):
        assert task._wait_recovery_ready("web") is False
