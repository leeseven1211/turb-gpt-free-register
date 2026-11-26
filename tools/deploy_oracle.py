"""Oracle 现有 combined 服务的受控代码切换引擎。"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

SERVICE_NAME = "turb-gpt-free-register.service"
SERVICE_PORT = 8000
_NON_RUNTIME_PREFIXES = ("docs/", "tests/", ".github/", ".codex/", "frontend/")
_DEPLOY_TOOLS = {
    "tools/deploy.py",
    "tools/deploy_local.py",
    "tools/deploy_oracle.py",
    ".gitignore",
    "requirements.in",
    "requirements-dev.txt",
    "requirements-dev.in",
}


class DeployOracleError(RuntimeError):
    """Oracle 部署失败，``code`` 是稳定的机器可读分类。"""

    def __init__(self, message: str, code: str = "deploy_failed") -> None:
        super().__init__(code)
        self.message = message
        self.code = code


DeployError = DeployOracleError


def _git(source: Path, *args: str, timeout: float = 30) -> str:
    result = subprocess.run(
        ["git", "-C", str(source), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[:240]
        raise DeployError(f"Git 操作失败: {' '.join(args)}: {detail}", "git_failed")
    return result.stdout.strip()


def _systemctl(*args: str, timeout: float = 30) -> str:
    prefix = ["sudo", "-n"] if args and args[0] in {"start", "stop", "restart"} else []
    result = subprocess.run(
        [*prefix, "systemctl", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[:240]
        raise DeployError(f"systemd 操作失败: {' '.join(args)}: {detail}", "manager_failed")
    return result.stdout


def _service_state() -> dict[str, str]:
    output = _systemctl(
        "show",
        SERVICE_NAME,
        "--property=MainPID,Result,ExecMainCode,ExecMainStatus,ActiveState,SubState",
    )
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


def _pid_exists(pid: int) -> bool:
    return bool(pid) and Path(f"/proc/{pid}").exists()


def _port_is_open() -> bool:
    with socket.socket() as connection:
        connection.settimeout(0.5)
        return connection.connect_ex(("127.0.0.1", SERVICE_PORT)) == 0


def _active_counts(source: Path) -> dict[str, object]:
    """读取当前部署 schema 的排空状态；查询保持只读和短超时。"""
    from dotenv import dotenv_values
    import psycopg
    from psycopg import sql

    values = dotenv_values(source / ".env")
    database_url = values.get("DATABASE_URL")
    if not database_url:
        raise DeployOracleError("缺少数据库连接配置", "database_configuration_missing")
    schema = values.get("TURB_DB_SCHEMA") or "public"
    states = ("running", "waiting", "stopping", "cancelling", "settling")
    result: dict[str, object] = {}
    with psycopg.connect(
        database_url,
        connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=15000",
    ) as connection:
        for table in ("registration_jobs", "registration_runs", "operation_tasks", "operation_runs"):
            rows = connection.execute(
                sql.SQL("SELECT status,count(*) FROM {} WHERE status=ANY(%s) GROUP BY status").format(
                    sql.Identifier(schema, table)
                ),
                (list(states),),
            ).fetchall()
            result[table] = dict(rows)
        for key, table, condition in (
            ("permits", "operation_execution_permits", "released_at IS NULL"),
            ("leases", "account_operation_leases", "expires_at>now()"),
            ("resources", "operation_resources", "released_at IS NULL"),
        ):
            result[key] = connection.execute(
                sql.SQL("SELECT count(*) FROM {} WHERE " + condition).format(
                    sql.Identifier(schema, table)
                )
            ).fetchone()[0]
    return result


def _require_idle(source: Path) -> dict[str, object]:
    counts = _active_counts(source)
    states = ("running", "waiting", "stopping", "cancelling", "settling")
    active = any(
        isinstance(counts.get(table), dict)
        and any(counts[table].get(state, 0) for state in states)
        for table in ("registration_jobs", "registration_runs", "operation_tasks", "operation_runs")
    )
    active = active or any(counts.get(key, 0) for key in ("permits", "leases", "resources"))
    if active:
        raise DeployOracleError("存在活动任务或资源，拒绝切换", "active_work_present")
    return counts


def _wait_for_idle(source: Path, timeout: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while True:
        try:
            return _require_idle(source)
        except DeployOracleError as error:
            if error.code != "active_work_present" or time.monotonic() >= deadline:
                raise
            time.sleep(min(1, max(0, deadline - time.monotonic())))


def _service_health(*, timeout: float = 10) -> dict[str, object]:
    session = requests.Session()
    session.trust_env = False
    statuses = {}
    paths = []
    ok = True
    for endpoint in ("healthz", "readyz", "login"):
        response = session.get(f"http://127.0.0.1:{SERVICE_PORT}/{endpoint}", timeout=timeout)
        statuses[endpoint] = response.status_code
        if response.status_code != 200:
            ok = False
            continue
        if endpoint != "login":
            try:
                ok = ok and response.json().get("ok") is True
            except (AttributeError, TypeError, ValueError):
                ok = False
        if ok:
            paths.append(f"/{endpoint}")
    return {"ok": ok, "paths": paths, "statuses": statuses}


def _http_evidence(statuses: dict[str, object]) -> dict[str, object]:
    if "ok" in statuses and "paths" in statuses:
        return statuses
    return {
        "ok": all(status == 200 for status in statuses.values()),
        "paths": [f"/{endpoint}" for endpoint in statuses],
    }


def _no_restart_path(path: str) -> bool:
    return (
        path.startswith("webui/static/")
        or path.endswith(".md")
        or path.startswith(_NON_RUNTIME_PREFIXES)
        or path in _DEPLOY_TOOLS
    )


def _runtime_probe(source: Path, expected: str, pid: int) -> dict:
    try:
        environment = {
            item.decode().split("=", 1)[0]: item.decode().split("=", 1)[1]
            for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
            if b"=" in item
        }
        cwd = os.readlink(f"/proc/{pid}/cwd")
    except (OSError, UnicodeDecodeError) as error:
        raise DeployError(f"无法读取服务进程运行时信息: {type(error).__name__}") from error
    if cwd != str(source):
        raise DeployError("服务进程工作目录与 Oracle 源码目录不一致")
    if _git(source, "rev-parse", "HEAD") != expected:
        raise DeployError("服务进程验收时源码版本不一致")
    process_start = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    ).stdout.strip()
    checker = source / "tools" / "check_runtime.py"
    if not checker.is_file():
        return {"pid": pid, "cwd": cwd, "process_start": process_start}
    command = [
        sys.executable,
        "-B",
        str(checker),
        "--instance-id",
        environment.get("TURB_INSTANCE_ID") or "default",
        "--release",
        expected,
        "--pid",
        str(pid),
        "--process-start",
        process_start,
        "--runtime-dir",
        environment.get("TURB_RUNTIME_DIR") or str(source / "logs" / "run"),
    ]
    probe = subprocess.run(
        command,
        cwd=source,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if probe.returncode:
        raise DeployError("运行时版本核验失败")
    try:
        details = json.loads(probe.stdout)
    except json.JSONDecodeError as error:
        raise DeployError("运行时核验返回无效结果") from error
    return {"pid": pid, "cwd": cwd, "process_start": process_start, "runtime": details}


def _stop_and_verify(*, timeout: float) -> dict[str, str]:
    previous = _service_state()
    previous_pid = int(previous.get("MainPID", "0") or 0)
    _systemctl("stop", SERVICE_NAME, timeout=timeout)
    deadline = time.monotonic() + timeout
    state = _service_state()
    while state.get("MainPID", "0") != "0" and time.monotonic() < deadline:
        time.sleep(0.2)
        state = _service_state()
    if state.get("MainPID", "0") != "0" or _pid_exists(previous_pid) or _port_is_open():
        raise DeployError("旧服务未完全停止", "service_stop_incomplete")
    if previous_pid and (
        state.get("Result") != "success"
        or state.get("ExecMainStatus") != "0"
    ):
        raise DeployError("systemd 停止结果异常", "service_stop_incomplete")
    return {"previous_pid": str(previous_pid), **state}


def _start_and_verify(*, source: Path, expected: str, timeout: float) -> dict:
    _systemctl("start", SERVICE_NAME, timeout=min(timeout, 60))
    deadline = time.monotonic() + timeout
    last_state: dict[str, str] = {}
    while time.monotonic() < deadline:
        last_state = _service_state()
        pid = int(last_state.get("MainPID", "0") or 0)
        if pid:
            try:
                health = _service_health(timeout=min(10, timeout))
                runtime = _runtime_probe(source, expected, pid)
                http = _http_evidence(health)
                if http["ok"]:
                    return {"pid": pid, "http": http, "runtime": runtime}
            except (DeployError, OSError, requests.RequestException, ValueError):
                pass
        time.sleep(0.5)
    raise DeployError(f"新服务未就绪: pid={last_state.get('MainPID', '0')}")


def _file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _backup_receipt(*, source: Path, receipt_dir: Path, old_commit: str) -> None:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.chmod(0o700)
    archive = receipt_dir / "source-before.tar"
    result = subprocess.run(
        ["git", "-C", str(source), "archive", "--format=tar", "-o", str(archive), old_commit],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise DeployError("无法保存部署前源码备份")
    archive.chmod(0o600)
    manager = receipt_dir / "manager-config.txt"
    manager.write_text(_systemctl("cat", SERVICE_NAME), encoding="utf-8")
    manager.chmod(0o600)


def _restore_old_tree(*, source: Path, old_commit: str, target: str) -> str | None:
    """仅对未被并发修改的 checkout 应用反向补丁并留下恢复提交。"""
    if _git(source, "rev-parse", "HEAD") != target:
        return None
    if _git(source, "status", "--porcelain", "--untracked-files=all"):
        return None
    if target == old_commit:
        return old_commit
    old_tree = _git(source, "rev-parse", f"{old_commit}^{{tree}}")
    patch = subprocess.run(
        ["git", "-C", str(source), "diff", "--binary", target, old_commit],
        capture_output=True,
        timeout=60,
    )
    if patch.returncode:
        return None
    applied = subprocess.run(
        ["git", "-C", str(source), "apply", "--index"],
        input=patch.stdout,
        capture_output=True,
        timeout=60,
    )
    if applied.returncode or _git(source, "write-tree") != old_tree:
        return None
    commit = subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=turb-deploy",
            "-c",
            "user.email=turb-deploy@localhost",
            "commit",
            "--no-verify",
            "-m",
            "fix(deploy): 恢复 Oracle 发布前代码",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if commit.returncode:
        return None
    restored = _git(source, "rev-parse", "HEAD")
    return restored if _git(source, "rev-parse", "HEAD^{tree}") == old_tree else None


def _write_receipt(receipt_dir: Path, receipt: dict) -> None:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.chmod(0o700)
    path = receipt_dir / "deployment-receipt.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    path.chmod(0o600)


def _event(receipt: dict, name: str, **details: object) -> None:
    receipt["events"].append(
        {
            "at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "event": name,
            **details,
        }
    )


def deploy_oracle(
    *,
    source: Path,
    revision: str,
    receipt_dir: Path,
    timeout: float = 180,
    action: str = "restart",
) -> dict:
    """在 Oracle 当前 checkout 上执行受控快进部署并返回脱敏回执。"""
    if action not in {"restart", "static", "noop"}:
        raise DeployOracleError("action 必须是 restart、static 或 noop", "invalid_action")
    source = Path(source).resolve()
    receipt_dir = Path(receipt_dir)
    receipt: dict = {
        "action": action,
        "source": str(source),
        "service": SERVICE_NAME,
        "revision": revision,
        "engine_receipt": str(receipt_dir / "deployment-receipt.json"),
        "restarted": False,
        "events": [],
    }
    service_may_be_stopped = False
    merged = False
    recovery_done = False
    try:
        _write_receipt(receipt_dir, receipt)
        env_hash = _file_hash(source / ".env")
        if _git(source, "status", "--porcelain", "--untracked-files=all"):
            raise DeployOracleError("Oracle 工作区不干净，拒绝部署", "dirty_worktree")
        old_commit = _git(source, "rev-parse", "HEAD")
        receipt["old_commit"] = old_commit
        try:
            target = _git(source, "rev-parse", "--verify", f"{revision}^{{commit}}")
        except DeployOracleError as error:
            raise DeployOracleError("目标 revision 不存在或不是提交", "revision_invalid") from error
        try:
            _git(source, "merge-base", "--is-ancestor", "HEAD", target)
        except DeployOracleError as error:
            raise DeployOracleError("目标提交不可快进", "not_fast_forward") from error
        changed = [path for path in _git(source, "diff", "--name-only", "HEAD", target).splitlines() if path]
        if action in {"static", "noop"} and any(
            not _no_restart_path(path) for path in changed
        ):
            raise DeployOracleError(
                "静态或 noop 部署只能包含静态资源、文档、测试和部署工具",
                "runtime_change",
            )
        if ".env" in changed:
            raise DeployOracleError("目标提交包含 .env 变更，拒绝部署", "env_change")
        receipt["target_commit"] = target
        receipt["changed_paths"] = changed
        _backup_receipt(source=source, receipt_dir=receipt_dir, old_commit=old_commit)
        _event(receipt, "部署前检查通过", old_commit=old_commit, target_commit=target)
        _write_receipt(receipt_dir, receipt)

        if action == "restart":
            service_may_be_stopped = True
            _wait_for_idle(source, timeout)
            _stop_and_verify(timeout=timeout)
            _require_idle(source)
        if _git(source, "rev-parse", "HEAD") != old_commit or _git(
            source, "status", "--porcelain", "--untracked-files=all"
        ):
            raise DeployOracleError("排空期间源码树发生变化，拒绝合并", "checkout_changed")
        _git(source, "merge", "--ff-only", target)
        merged = True
        if _file_hash(source / ".env") != env_hash:
            raise DeployError("部署意外修改了 .env")
        if action in {"static", "noop"}:
            statuses = _service_health(timeout=min(10, timeout))
            receipt["http"] = _http_evidence(statuses)
            if not receipt["http"]["ok"]:
                raise DeployOracleError("不重启部署后的现有服务健康检查失败", "health_check")
        else:
            started = _start_and_verify(source=source, expected=target, timeout=timeout)
            receipt.update(
                restarted=True,
                backend_commit=target,
                http=started["http"],
                service_pid=started["pid"],
                runtime=started["runtime"],
            )
        receipt["status"] = "succeeded"
        _event(receipt, "Oracle 部署完成", commit=target)
        _write_receipt(receipt_dir, receipt)
        return receipt
    except Exception as error:
        receipt["status"] = "failed"
        receipt["error"] = type(error).__name__
        receipt["reason"] = str(error)[:240]
        if merged and action == "restart":
            receipt["code_restored"] = False
            receipt["manual_restore_required"] = True
            restored = None
            try:
                _stop_and_verify(timeout=timeout)
                restored = _restore_old_tree(
                    source=source, old_commit=receipt["old_commit"], target=receipt["target_commit"]
                )
                if restored:
                    receipt["code_restored"] = True
                    receipt["restored_commit"] = restored
                    _start_and_verify(source=source, expected=restored, timeout=timeout)
                    receipt["manual_restore_required"] = False
                    receipt["recovery_start"] = "restored_and_started"
                    recovery_done = True
            except Exception:
                pass
        if action == "restart" and service_may_be_stopped:
            receipt["recovery_attempted"] = True
            if not recovery_done:
                try:
                    _systemctl("start", SERVICE_NAME, timeout=min(timeout, 60))
                    receipt["recovery_start"] = "attempted"
                except Exception:
                    receipt["recovery_start"] = "failed"
        _event(receipt, "部署未完成", error=receipt["error"])
        _write_receipt(receipt_dir, receipt)
        if isinstance(error, DeployError):
            raise
        raise DeployError(f"部署失败: {type(error).__name__}") from error
