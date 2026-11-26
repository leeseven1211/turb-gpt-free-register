"""本地 launchd release 切换工具。

模块导入只加载标准库和 release 校验函数；实际部署阶段才读取现役
plist，并按 plist 中的运行配置执行只读排空检查。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from tools.release import check_release as _check_release

LABELS = {
    "web": "com.leeseven.turb-console-webui",
    "worker": "com.leeseven.turb-console-worker",
}
ROLES = ("web", "worker")
MANAGER_DIR = Path.home() / "Library" / "LaunchAgents"
DOMAIN = f"gui/{os.getuid()}"
STOP_FLAGS = ("http_stop_incomplete", "后台排空未完成", "后台收尾失败")
REQUIRED_COUNTS = {
    "accepted", "active", "active_batches", "pending_owner_releases",
    "legacy_release_pending", "legacy_release_inflight", "legacy_renewal_pending",
    "registration_pending", "settlement_pending", "resource_pending",
    "permit_pending", "compensation_inflight", "unpersisted", "callback_active",
    "registered", "unverified_scan_pending",
}


class DeployLocalError(RuntimeError):
    """部署失败，字符串内容是稳定错误码。"""

    def __init__(self, code: str, *, receipt: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.receipt = receipt


DeployError = DeployLocalError


def _fail(code: str) -> None:
    raise DeployError(code)


def _run_command(
    arguments: list[str],
    *,
    timeout: float = 20.0,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            arguments, capture_output=True, text=True, timeout=max(0.1, timeout),
            env=env, cwd=cwd,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DeployLocalError(f"command_{type(exc).__name__}") from exc


def _inspect_process(pid: int):
    from core.runtime.role_launcher import inspect_process

    return inspect_process(pid)


def _manager_path(role: str) -> Path:
    return MANAGER_DIR / f"{LABELS[role]}.plist"


def _atomic_write(path: Path, payload: bytes) -> None:
    if path.is_symlink():
        _fail("manager_symlink_rejected")
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _retarget_plist(
    original: dict[str, Any],
    *,
    role: str,
    release: Path,
    interpreter: Path | None = None,
    http_threads: int | None = None,
) -> dict[str, Any]:
    """改变包目录、入口脚本及明确传入的本地启动参数。"""
    if role not in ROLES:
        _fail("role_invalid")
    if http_threads is not None and (type(http_threads) is not int or not 1 <= http_threads <= 128):
        _fail("http_threads_invalid")
    value = deepcopy(original)
    arguments = value.get("ProgramArguments")
    working = value.get("WorkingDirectory")
    environment = value.get("EnvironmentVariables")
    if not isinstance(arguments, list) or len(arguments) < 2:
        _fail("manager_arguments_invalid")
    if not isinstance(working, str) or not Path(working).is_absolute():
        _fail("manager_working_directory_invalid")
    if not isinstance(environment, dict):
        _fail("manager_environment_invalid")
    entrypoint = f"{role}.py"
    old_entrypoint = str(Path(working).resolve() / entrypoint)
    if str(arguments[1]) != old_entrypoint:
        _fail("manager_entrypoint_invalid")
    if interpreter is not None:
        interpreter = Path(interpreter)
        if not interpreter.is_absolute():
            _fail("interpreter_invalid")
        arguments[0] = str(interpreter)
    arguments[1] = str(release / entrypoint)
    if role == "web" and http_threads is not None:
        if "--http-threads" in arguments:
            index = arguments.index("--http-threads") + 1
            if index >= len(arguments):
                _fail("manager_arguments_invalid")
            arguments[index] = str(http_threads)
        else:
            arguments += ["--http-threads", str(http_threads)]
    value["ProgramArguments"] = arguments
    value["WorkingDirectory"] = str(release)
    value["EnvironmentVariables"] = environment
    return value


def _current_identity(role: str, config: dict[str, Any]) -> dict[str, Any]:
    environment = config.get("EnvironmentVariables")
    if not isinstance(environment, dict) or not environment.get("TURB_RUNTIME_DIR"):
        _fail("runtime_directory_missing")
    path = Path(str(environment["TURB_RUNTIME_DIR"])) / f"{role}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DeployLocalError("identity_unavailable") from exc
    if not isinstance(value, dict):
        _fail("identity_invalid")
    return value


def _loaded_pid(role: str) -> int | None:
    result = _run_command(["launchctl", "print", f"{DOMAIN}/{LABELS[role]}"])
    if result.returncode:
        return None
    match = re.search(r"(?m)^\s*pid = ([1-9][0-9]*)\s*$", result.stdout)
    return int(match.group(1)) if match else 0


def _identity_matches(
    role: str,
    identity: dict[str, Any],
    *,
    release: str,
    cwd: Path,
) -> bool:
    pid = identity.get("pid")
    if (
        identity.get("role") not in (None, role)
        or identity.get("release") != release
        or identity.get("cwd") != str(cwd)
        or type(pid) is not int
        or _loaded_pid(role) != pid
    ):
        return False
    observed = _inspect_process(pid)
    if observed is None:
        return False
    return all(
        identity.get(key) == getattr(observed, key)
        for key in ("pid", "process_start", "cwd", "command")
        if identity.get(key) is not None
    )


def _port(config: dict[str, Any]) -> int:
    arguments = config.get("ProgramArguments", [])
    try:
        return int(arguments[arguments.index("--port") + 1])
    except (ValueError, IndexError, TypeError):
        _fail("web_port_missing")
    raise AssertionError


def _listener_pids(port: int) -> set[int]:
    result = _run_command(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"])
    if result.returncode not in (0, 1):
        _fail("listener_probe_failed")
    return {int(item) for item in result.stdout.split() if item.isdigit()}


def _idle_snapshot(configs: dict[str, dict[str, Any]], identities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """在执行阶段读取当前配置指向的数据库，返回旧流程的排空证据。"""
    try:
        from dotenv.main import DotEnv
        import psycopg
        from psycopg import sql
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise DeployLocalError("idle_probe_dependencies_missing") from exc
    environment = dict(configs["web"]["EnvironmentVariables"])
    bootstrap = Path(str(environment.get("TURB_BOOTSTRAP_ENV_FILE", "")))
    if not bootstrap.is_file():
        _fail("bootstrap_file_missing")
    values = DotEnv(bootstrap, interpolate=True, override=False).dict()
    db_env = {key: value for key, value in values.items() if value is not None}
    db_env.update(environment)
    database_url = db_env.get("DATABASE_URL")
    if not database_url:
        _fail("database_configuration_missing")
    schema = db_env.get("TURB_DB_SCHEMA") or "public"
    operation_schema = db_env.get("OPERATION_TASK_DB_SCHEMA") or schema
    instance = environment.get("TURB_INSTANCE_ID")
    with psycopg.connect(
        database_url, row_factory=dict_row, autocommit=True,
        connect_timeout=5, options="-c default_transaction_read_only=on -c statement_timeout=4000",
    ) as conn:
        worker = conn.execute(sql.SQL(
            "SELECT pid,release,extract(epoch FROM clock_timestamp()-heartbeat_at) AS age,status "
            "FROM {} WHERE instance_id=%s"
        ).format(sql.Identifier(schema, "runtime_workers")), (instance,)).fetchone()
        if worker is None:
            _fail("worker_record_missing")
        permits = conn.execute(sql.SQL(
            "SELECT count(*) AS n FROM {} WHERE released_at IS NULL"
        ).format(sql.Identifier(schema, "operation_execution_permits"))).fetchone()["n"]
        leases = conn.execute(sql.SQL(
            "SELECT count(*) AS n FROM {} WHERE expires_at>now()"
        ).format(sql.Identifier(operation_schema, "account_operation_leases"))).fetchone()["n"]
    counts = worker["status"].get("counts") if isinstance(worker.get("status"), dict) else {}
    if not isinstance(counts, dict) or not REQUIRED_COUNTS <= counts.keys():
        _fail("idle_counts_invalid")
    if any(type(value) is not int or value < 0 for value in counts.values()):
        _fail("idle_counts_invalid")
    worker_ok = (
        worker["pid"] == identities["worker"].get("pid")
        and worker["release"] == identities["worker"].get("release")
        and 0 <= float(worker["age"]) < 20
    )
    return {
        "idle": bool(worker_ok and all(value == 0 for value in counts.values())
                    and permits == 0 and leases == 0),
        "counts": counts,
        "permits": permits,
        "leases": leases,
    }


def _readiness(role: str, config: dict[str, Any], release: Path, sha: str) -> bool:
    identity = _current_identity(role, config)
    if not _identity_matches(role, identity, release=sha, cwd=release):
        return False
    if role == "worker":
        environment = {
            "PATH": os.defpath, "HOME": str(Path.home()), "PYTHONDONTWRITEBYTECODE": "1",
            **config["EnvironmentVariables"],
        }
        result = _run_command([
            config["ProgramArguments"][0], str(release / "tools/check_runtime.py"),
            "--instance-id", str(environment["TURB_INSTANCE_ID"]),
            "--release", sha, "--pid", str(identity["pid"]),
            "--process-start", str(identity.get("owner_process_start", "")),
            "--runtime-dir", str(environment["TURB_RUNTIME_DIR"]),
        ], timeout=12, env=environment, cwd=release)
        return result.returncode == 0 and '"ok": true' in result.stdout.lower()
    port = _port(config)
    if _listener_pids(port) != {identity["pid"]}:
        return {"ok": False, "paths": []}
    from tools.check_startup import check_startup

    probes = check_startup(f"http://127.0.0.1:{port}", timeout=4)
    paths = [probe.path for probe in probes if probe.ok]
    if not all(probe.ok for probe in probes):
        return {"ok": False, "paths": paths}
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/login", timeout=4) as response:
            if response.status != 200:
                return {"ok": False, "paths": paths}
    except (OSError, urllib.error.URLError):
        return {"ok": False, "paths": paths}
    paths.append("/login")
    return {"ok": True, "paths": paths}


class _Deployment:
    def __init__(
        self,
        *,
        source: Path,
        release: Path,
        receipt_dir: Path,
        timeout: float,
        interpreter: Path | None,
        allow_same_release: bool,
        http_threads: int | None = None,
    ) -> None:
        self.source = source.resolve()
        self.release = release.resolve()
        self.receipt_dir = receipt_dir
        self.deadline = time.monotonic() + timeout
        self.interpreter = interpreter
        self.allow_same_release = allow_same_release
        self.http_threads = http_threads
        self.configs: dict[str, dict[str, Any]] = {}
        self.original: dict[str, bytes] = {}
        self.next: dict[str, dict[str, Any]] = {}
        self.identities: dict[str, dict[str, Any]] = {}
        self.touched: list[str] = []
        self.bootstrapped: list[str] = []
        self.log_offsets: dict[str, dict[str, int]] = {}
        self.target = ""
        self.previous = ""
        self.old_release = Path()
        self.receipt: Path | None = None

    def _budget(self, maximum: float) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            _fail("timeout")
        return min(maximum, remaining)

    def _load(self) -> None:
        if not self.source.is_dir() or not (self.source / "web.py").is_file() or not (self.source / "worker.py").is_file():
            _fail("source_invalid")
        if self.release.is_symlink() or not self.release.is_dir():
            _fail("release_invalid")
        report = _check_release(self.release, validate_project=True)
        self.target = str(report["source_commit"])
        for role in ROLES:
            path = _manager_path(role)
            if path.is_symlink() or not path.is_file():
                _fail("manager_file_invalid")
            payload = path.read_bytes()
            try:
                config = plistlib.loads(payload)
            except (OSError, plistlib.InvalidFileException, ValueError) as exc:
                raise DeployLocalError("manager_plist_invalid") from exc
            if config.get("Label") != LABELS[role]:
                _fail("manager_label_invalid")
            self.original[role] = payload
            self.configs[role] = config
            self.next[role] = _retarget_plist(
                config, role=role, release=self.release, interpreter=self.interpreter,
                http_threads=self.http_threads,
            )
            environment = config.get("EnvironmentVariables", {})
            for key in ("StandardOutPath", "StandardErrorPath"):
                value = config.get(key)
                self.log_offsets.setdefault(role, {})[key] = (
                    Path(value).stat().st_size if isinstance(value, str) and Path(value).is_file() else 0
                )
        old_paths = {Path(self.configs[role]["WorkingDirectory"]).resolve() for role in ROLES}
        if len(old_paths) != 1:
            _fail("old_release_mismatch")
        old_release = next(iter(old_paths))
        self.old_release = old_release
        old_report = _check_release(old_release, validate_project=True)
        self.previous = str(old_report["source_commit"])
        if self.previous == self.target and not self.allow_same_release:
            _fail("target_already_deployed")
        for role in ROLES:
            identity = _current_identity(role, self.configs[role])
            if not _identity_matches(role, identity, release=self.previous, cwd=old_release):
                _fail("identity_mismatch")
            self.identities[role] = identity

    def _write_receipt(self, payload: dict[str, Any]) -> Path:
        self.receipt_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.receipt_dir / f"deploy-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.json"
        _atomic_write(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode())
        self.receipt = path
        return path

    def _backup_configs(self) -> None:
        self.receipt_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        for role in ROLES:
            _atomic_write(self.receipt_dir / f"{role}.original.plist", self.original[role])

    def _wait_stopped(self, role: str) -> None:
        while time.monotonic() < self.deadline:
            identity = self.identities.get(role)
            process_gone = identity is None or _inspect_process(identity.get("pid")) is None
            if _loaded_pid(role) is None and process_gone:
                return
            time.sleep(min(0.2, self._budget(0.2)))
        _fail("stop_timeout")

    def _wait_identity_stopped(self, role: str, identity: dict[str, Any] | None) -> bool:
        pid = identity.get("pid") if identity else None
        while time.monotonic() < self.deadline:
            loaded = _loaded_pid(role)
            process_gone = pid is None or _inspect_process(pid) is None
            if loaded is None and process_gone:
                return True
            time.sleep(min(0.2, self._budget(0.2)))
        return False

    def _wait_idle(self) -> None:
        while time.monotonic() < self.deadline:
            if _idle_snapshot(self.configs, self.identities).get("idle") is True:
                return
            time.sleep(min(1.0, self._budget(1.0)))
        _fail("idle_timeout")

    def _bootout(self, role: str) -> None:
        if role not in self.touched:
            self.touched.append(role)
        result = _run_command(
            ["launchctl", "bootout", f"{DOMAIN}/{LABELS[role]}"],
            timeout=self._budget(65),
        )
        if result.returncode:
            _fail("bootout_failed")
        self._wait_stopped(role)

    def _bootstrap(self, role: str) -> None:
        if role not in self.bootstrapped:
            self.bootstrapped.append(role)
        result = _run_command(
            ["launchctl", "bootstrap", DOMAIN, str(_manager_path(role))],
            timeout=self._budget(20),
        )
        if result.returncode:
            _fail("bootstrap_failed")

    def _check_logs(self, role: str) -> None:
        for key, offset in self.log_offsets[role].items():
            value = self.configs[role].get(key)
            if not isinstance(value, str):
                continue
            path = Path(value)
            if not path.is_file():
                continue
            with path.open("rb") as stream:
                stream.seek(offset if path.stat().st_size >= offset else 0)
                tail = stream.read().decode(errors="replace")
            if any(flag in tail for flag in STOP_FLAGS):
                _fail("service_drain_incomplete")

    def _wait_ready(self, role: str):
        while time.monotonic() < self.deadline:
            result = _readiness(role, self.next[role], self.release, self.target)
            if result is True or isinstance(result, dict) and result.get("ok") is True:
                return {"ok": True, "paths": []} if role == "web" and result is True else result
            time.sleep(min(0.5, self._budget(0.5)))
        _fail(f"{role}_ready_timeout")

    @staticmethod
    def _ready_result(result: Any) -> bool:
        return result is True or isinstance(result, dict) and result.get("ok") is True

    def _wait_recovery_ready(self, role: str) -> bool:
        deadline = min(self.deadline, time.monotonic() + 30)
        while time.monotonic() < deadline:
            try:
                if self._ready_result(
                    _readiness(role, self.configs[role], self.old_release, self.previous)
                ):
                    return True
            except BaseException:
                pass
            time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
        return False

    def _rollback(self) -> dict[str, Any]:
        errors = []
        for role in reversed(self.bootstrapped):
            loaded_pid = _loaded_pid(role)
            try:
                identity = _current_identity(role, self.next[role])
            except BaseException:
                identity = {"pid": loaded_pid} if loaded_pid is not None else None
            try:
                result = _run_command(
                    ["launchctl", "bootout", f"{DOMAIN}/{LABELS[role]}"], timeout=10,
                )
                if result.returncode:
                    errors.append(f"{role}_bootout")
                if not self._wait_identity_stopped(role, identity):
                    errors.append(f"{role}_stop")
            except BaseException:
                errors.append(f"{role}_bootout")
        for role in ROLES:
            if role in self.touched or role in self.bootstrapped:
                try:
                    _atomic_write(_manager_path(role), self.original[role])
                except BaseException:
                    errors.append(f"{role}_plist")
        for role in ("worker", "web"):
            if _loaded_pid(role) is not None:
                continue
            try:
                result = _run_command(
                    ["launchctl", "bootstrap", DOMAIN, str(_manager_path(role))], timeout=20,
                )
                if result.returncode:
                    errors.append(f"{role}_bootstrap")
            except BaseException:
                errors.append(f"{role}_bootstrap")
        for role in ("worker", "web"):
            if not self._wait_recovery_ready(role):
                errors.append(f"{role}_readiness")
        return {"ok": not errors, "errors": errors}

    def _verify_originals(self) -> None:
        for role in ROLES:
            if _manager_path(role).read_bytes() != self.original[role]:
                _fail("manager_changed_concurrently")

    def run(self) -> dict[str, Any]:
        self._load()
        self._backup_configs()
        self._wait_idle()
        self._verify_originals()
        for role in ROLES:
            self._bootout(role)
            self._check_logs(role)
            if role == "web":
                self._wait_idle()
        self._verify_originals()
        if _listener_pids(_port(self.configs["web"])):
            _fail("port_not_closed")
        for role in ROLES:
            _atomic_write(_manager_path(role), plistlib.dumps(self.next[role], sort_keys=False))
        self._bootstrap("worker")
        self._wait_ready("worker")
        self._bootstrap("web")
        http = self._wait_ready("web")
        pids = {
            role: _current_identity(role, self.next[role]).get("pid")
            for role in ROLES
        }
        receipt = self._write_receipt({
            "ok": True, "status": "deployed", "release": self.target,
            "previous_release": self.previous, "pids": pids, "http": http,
        })
        return {
            "ok": True, "release": self.target, "status": "deployed",
            "pids": pids, "http": http, "engine_receipt": str(receipt),
        }


def deploy_local(
    *,
    source: Path,
    release: Path,
    receipt_dir: Path,
    timeout: float = 180,
    interpreter: Path | None = None,
    allow_same_release: bool = False,
    http_threads: int | None = None,
) -> dict[str, Any]:
    """切换本机 launchd 固定 release，并在失败时恢复原 plist。"""
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        _fail("timeout_invalid")
    task = _Deployment(
        source=Path(source), release=Path(release), receipt_dir=Path(receipt_dir),
        timeout=float(timeout), interpreter=Path(interpreter) if interpreter is not None else None,
        allow_same_release=allow_same_release,
        http_threads=http_threads,
    )
    try:
        return task.run()
    except BaseException as exc:
        rollback = {"ok": True, "errors": []}
        if task.touched or task.bootstrapped:
            task.deadline = max(task.deadline, time.monotonic() + 60)
            try:
                rollback = task._rollback()
            except BaseException:
                rollback = {"ok": False, "errors": ["rollback_exception"]}
        if isinstance(exc, DeployLocalError):
            error = exc
        else:
            error = DeployLocalError(type(exc).__name__)
        try:
            receipt = task._write_receipt({
                "ok": False,
                "status": "failed",
                "release": task.target or None,
                "previous_release": task.previous or None,
                "error_code": error.code,
                "rollback": rollback,
            })
            error.receipt = str(receipt)
        except BaseException:
            pass
        raise error from exc
