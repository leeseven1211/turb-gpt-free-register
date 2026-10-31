"""Oracle 备份在导出前核对实例连接，测试不接触真实 Docker 或数据库。"""
from __future__ import annotations

import json
import os
import shutil
import shlex
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "maintenance" / "backup_oracle.sh"
CONTAINER_ID = "a" * 64


@pytest.fixture
def backup_case(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".env").write_text(
        'DATABASE_URL="postgresql://app:private-password@127.0.0.1:5432/turb_restored"\n',
        encoding="utf-8",
    )
    interpreter = source / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    # 临时目录没有 pyvenv.cfg，直接链接解释器会丢失当前虚拟环境依赖。
    interpreter.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n', encoding="utf-8")
    interpreter.chmod(0o755)
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(
        ["git", "-C", str(source), "-c", "user.name=测试", "-c", "user.email=test@example.invalid",
         "commit", "--allow-empty", "-qm", "test: 初始化备份测试仓库"],
        check=True,
    )
    commands = tmp_path / "commands.jsonl"
    container = tmp_path / "container.json"
    container.write_text(json.dumps([{
        "Id": CONTAINER_ID,
        "State": {"Running": True},
        "NetworkSettings": {"Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "5432"}]}},
    }]), encoding="utf-8")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    docker = binaries / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['TURB_TEST_COMMAND_LOG'], 'a') as output:\n"
        "    output.write(json.dumps(args) + '\\n')\n"
        "if args[:1] == ['inspect']:\n"
        "    print(pathlib.Path(os.environ['TURB_TEST_CONTAINER']).read_text())\n"
        "elif 'pg_dump' in args:\n"
        "    print('数据库备份测试内容')\n"
        "elif 'pg_restore' in args:\n"
        "    sys.stdin.read()\n"
        "    print('备份目录测试内容')\n"
        "else:\n"
        "    raise SystemExit(93)\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    if shutil.which("flock") is None:
        lock = binaries / "flock"
        lock.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        lock.chmod(0o755)
    destination = tmp_path / "backups"
    environment = {
        **os.environ,
        "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
        "TURB_BACKUP_SOURCE_ROOT": str(source),
        "TURB_BACKUP_ROOT": str(destination),
        "TURB_BACKUP_PG_CONTAINER": "postgres",
        "TURB_TEST_CONTAINER": str(container),
        "TURB_TEST_COMMAND_LOG": str(commands),
    }
    environment.pop("TURB_BACKUP_DATABASE", None)
    return source, destination, environment, commands, container


def _run_backup(case):
    result = subprocess.run(["bash", str(SCRIPT)], env=case[2], capture_output=True, text=True)
    assert "private-password" not in result.stdout + result.stderr
    calls = [json.loads(line) for line in case[3].read_text().splitlines()] if case[3].exists() else []
    return result, calls


def test_backup_uses_database_from_the_copied_bootstrap(backup_case):
    result, calls = _run_backup(backup_case)
    assert result.returncode == 0, result.stderr
    dump = next(call for call in calls if "pg_dump" in call)
    assert dump[dump.index("-d") + 1] == "turb_restored"
    assert CONTAINER_ID in dump
    completed = list(backup_case[1].glob("*/COMPLETE"))
    assert len(completed) == 1
    assert (completed[0].parent / "bootstrap.env").read_bytes() == (backup_case[0] / ".env").read_bytes()
    assert (completed[0].parent / "database.dump").read_text().strip() == "数据库备份测试内容"


@pytest.mark.parametrize("failure", ["database_override", "host", "port", "container_port", "stopped"])
def test_mismatched_targets_fail_before_dump_or_completion(backup_case, failure):
    if failure == "database_override":
        backup_case[2]["TURB_BACKUP_DATABASE"] = "some_other_database"
    elif failure in {"host", "port"}:
        address = "192.0.2.5:5432" if failure == "host" else "127.0.0.1:55432"
        (backup_case[0] / ".env").write_text(
            f'DATABASE_URL="postgresql://app:private-password@{address}/turb_restored"\n',
            encoding="utf-8",
        )
    else:
        state = json.loads(backup_case[4].read_text())
        if failure == "container_port":
            state[0]["NetworkSettings"]["Ports"] = {"5433/tcp": [{"HostIp": "127.0.0.1", "HostPort": "5432"}]}
        else:
            state[0]["State"]["Running"] = False
        backup_case[4].write_text(json.dumps(state), encoding="utf-8")
    result, calls = _run_backup(backup_case)
    assert result.returncode != 0
    assert not any("pg_dump" in call for call in calls)
    assert not list(backup_case[1].glob("*/COMPLETE"))


def test_root_service_can_record_commit_for_another_owner(backup_case):
    """通过 Git 自身的所有权检查复现 systemd root 与 ubuntu 工作树差异。"""
    backup_case[2]["GIT_TEST_ASSUME_DIFFERENT_OWNER"] = "1"
    result, _ = _run_backup(backup_case)
    assert result.returncode == 0, result.stderr
    completed = next(backup_case[1].glob("*/COMPLETE"))
    assert len((completed.parent / "commit.txt").read_text().strip()) == 40
