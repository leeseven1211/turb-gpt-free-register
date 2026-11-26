#!/usr/bin/env python3
"""预览或执行本地、Oracle 的定向部署，默认不修改服务。"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import plistlib
import re
import shlex
import subprocess
import sys
import time
from urllib.request import urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ORACLE_SOURCE = "/srv/apps/turb-gpt-free-register"
LABELS = {"web": "com.leeseven.turb-console-webui", "worker": "com.leeseven.turb-console-worker"}
sys.path.insert(0, str(ROOT))


class DeployError(RuntimeError):
    """只输出稳定错误分类，不附带进程环境或凭据。"""


def git(source: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(source), *arguments], capture_output=True, text=True, timeout=20,
    )
    if result.returncode:
        raise DeployError("deployment_git_failed")
    return result.stdout.strip()


def classify_changes(paths: list[str], *, fixed_release: bool) -> str:
    """仅忽略明确不会被生产进程执行的文件，其余按实际运行布局处理。"""
    runtime = [
        path for path in paths
        if not (
            path.endswith(".md")
            or path.startswith(("docs/", "tests/", ".github/", ".codex/", "frontend/"))
            or path in {
                "tools/deploy.py", "tools/deploy_local.py", "tools/deploy_oracle.py",
                ".gitignore", "requirements.in", "requirements-dev.txt", "requirements-dev.in",
            }
        )
    ]
    if not runtime:
        return "noop"
    if not fixed_release and all(path.startswith("webui/static/") for path in runtime):
        return "static"
    return "restart"


def read_state(source: Path, target: str) -> dict:
    try:
        value = json.loads((source / f"logs/run/deploy/{target}/last-success.json").read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def local_layout() -> dict:
    configs = {
        role: plistlib.loads((Path.home() / f"Library/LaunchAgents/{label}.plist").read_bytes())
        for role, label in LABELS.items()
    }
    roots = {str(Path(value["WorkingDirectory"]).resolve()) for value in configs.values()}
    interpreters = {value["ProgramArguments"][0] for value in configs.values()}
    if len(roots) != 1 or len(interpreters) != 1:
        raise DeployError("deployment_local_roles_mismatch")
    release = Path(roots.pop())
    from tools.release import check_release

    report = check_release(release)
    return {
        "backend_commit": report["source_commit"], "running_release": str(release),
        "interpreter": interpreters.pop(),
    }


def oracle_identity() -> dict:
    from core.runtime.role_launcher import inspect_process

    result = subprocess.run(
        ["systemctl", "show", "turb-gpt-free-register.service", "--property=MainPID", "--value"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode or not result.stdout.strip().isdigit():
        raise DeployError("deployment_manager_unavailable")
    pid = int(result.stdout.strip())
    process = inspect_process(pid)
    return {"pid": pid, "process_start": process.process_start if process else None}


def build_plan(args: argparse.Namespace) -> dict:
    source = Path(args.source).resolve()
    head = git(source, "rev-parse", "HEAD")
    revision = git(source, "rev-parse", "--verify", f"{args.revision or head}^{{commit}}")
    dirty = bool(git(source, "status", "--porcelain", "--untracked-files=no"))
    layout = local_layout() if args.target == "local" else {}
    previous = read_state(source, args.target)
    if args.target == "local":
        if revision != head:
            raise DeployError("deployment_local_requires_source_head")
        backend = layout["backend_commit"]
    else:
        identity = oracle_identity()
        known = (
            previous.get("pid") == identity["pid"]
            and previous.get("process_start") == identity["process_start"]
            and identity["process_start"] is not None
        )
        backend = previous.get("backend_commit") if known else None
        if not known and identity["pid"]:
            from tools.deploy_oracle import _runtime_probe

            try:
                evidence = _runtime_probe(source, head, identity["pid"])
                if evidence.get("runtime", {}).get("ok") is True:
                    backend = head
                    layout["version_evidence"] = "持久运行记录的提交、PID及进程启动身份均匹配"
            except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
                pass
        layout.update(identity)
        result = subprocess.run(
            ["git", "-C", str(source), "merge-base", "--is-ancestor", head, revision],
            capture_output=True, timeout=10,
        )
        if result.returncode:
            raise DeployError("deployment_non_fast_forward")
    # 有已核对的回执时使用已发布文件版本，避免静态热更新后重复部署相同产物。
    comparison = (previous.get("source_commit") if args.target == "oracle" and known else backend) or head
    changed = git(source, "diff", "--name-only", "--no-renames", comparison, revision).splitlines()
    pending = git(source, "diff", "--name-only", "--no-renames", head, revision).splitlines()
    action = classify_changes(changed, fixed_release=args.target == "local")
    http_threads = getattr(args, "http_threads", None)
    if args.restart or http_threads is not None or args.target == "oracle" and backend is None:
        action = "restart"
    dependency_paths = changed if backend else pending
    dependencies_changed = "requirements.txt" in dependency_paths
    plan = {
        "target": args.target, "source_commit": revision, "checkout_commit": head,
        "backend_commit": backend, "action": action, "changed_paths": changed,
        "pending_paths": pending, "dirty": dirty, "dependencies_changed": dependencies_changed,
        "frontend_build": "使用已提交的前端产物，部署阶段不重复构建",
        **layout,
    }
    if http_threads is not None:
        plan["http_threads"] = http_threads
    if args.target == "oracle" and backend is None:
        plan["reason"] = "尚无法核对当前进程的运行版本，执行时需重启建立版本基线"
    return plan


def verify_http(base_url: str, *, timeout: float) -> dict:
    from tools.check_startup import check_startup

    deadline = time.monotonic() + timeout
    while True:
        probes = check_startup(base_url, timeout=min(3, timeout))
        if all(probe.ok for probe in probes):
            try:
                with urlopen(f"{base_url.rstrip('/')}/login", timeout=min(3, timeout)) as response:
                    if response.status == 200:
                        return {"ok": True, "paths": ["/healthz", "/readyz", "/login"]}
            except OSError:
                pass
        if time.monotonic() >= deadline:
            raise DeployError("deployment_http_not_ready")
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def remote_command(host: str, source: str, arguments: list[str]) -> list[str]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]*", host):
        raise DeployError("deployment_ssh_host_invalid")
    bootstrap = (
        "import json,sys,types;"
        "b=json.load(sys.stdin);"
        "r=sys.argv[sys.argv.index('--source')+1];sys.path.insert(0,r);"
        "m=types.ModuleType('tools.deploy_oracle');"
        "m.__file__=r+'/tools/deploy_oracle.py';sys.modules[m.__name__]=m;"
        "exec(compile(b['oracle'],m.__file__,'exec'),m.__dict__);"
        "g={'__name__':'__main__','__file__':r+'/tools/deploy.py'};"
        "exec(compile(b['main'],g['__file__'],'exec'),g)"
    )
    return [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host,
        shlex.join([source + "/.venv/bin/python", "-B", "-c", bootstrap, *arguments]),
    ]


def dispatch_oracle(args: argparse.Namespace) -> int:
    source = args.source or ORACLE_SOURCE
    arguments = [
        "oracle", "--on-host", "--source", source, "--timeout", str(args.timeout),
        "--base-url", args.base_url,
    ]
    for name in ("apply", "check", "restart"):
        if getattr(args, name):
            arguments.append("--" + name)
    if args.revision:
        arguments += ["--revision", args.revision]
    payload = {
        "main": Path(__file__).read_text(encoding="utf-8"),
        "oracle": (ROOT / "tools/deploy_oracle.py").read_text(encoding="utf-8"),
    }
    try:
        result = subprocess.run(
            remote_command(args.host, source, arguments), input=json.dumps(payload),
            # 含等待空闲、停止、启动和失败恢复，不能在服务恢复中途截断 SSH。
            text=True, capture_output=True, timeout=args.timeout * 5 + 180,
        )
    except subprocess.TimeoutExpired:
        raise DeployError("deployment_ssh_timeout_check_remote_receipt") from None
    if result.stdout:
        print(result.stdout, end="")
    # SSH 或远端 Python 的原始 stderr 可能包含环境和日志，只返回稳定分类。
    if result.returncode and not result.stdout:
        raise DeployError("deployment_ssh_failed")
    return result.returncode


def save_receipt(path: Path, value: dict) -> None:
    from core.runtime.role_launcher import atomic_json

    atomic_json(path, value)


def check_dependency_environment(interpreter: str, requirements: str) -> None:
    """验证目标环境的实际版本；部署工具不原地升级现役 venv。"""
    probe = """
import importlib.metadata as metadata
import json, sys
try:
    from packaging.requirements import Requirement
except ImportError:
    from pip._vendor.packaging.requirements import Requirement
missing = []
for line in json.load(sys.stdin).splitlines():
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    requirement = Requirement(line.split(' #', 1)[0])
    if requirement.marker and not requirement.marker.evaluate():
        continue
    try:
        version = metadata.version(requirement.name)
    except metadata.PackageNotFoundError:
        missing.append(requirement.name)
        continue
    if version not in requirement.specifier:
        missing.append(requirement.name)
sys.exit(bool(missing))
"""
    result = subprocess.run(
        [interpreter, "-B", "-c", probe], input=json.dumps(requirements),
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise DeployError("deployment_dependency_environment_mismatch")


def execute(args: argparse.Namespace, plan: dict) -> dict:
    source = Path(args.source).resolve()
    if plan.get("dirty"):
        raise DeployError("deployment_source_has_uncommitted_changes")
    if plan.get("checkout_commit") and git(source, "rev-parse", "HEAD") != plan["checkout_commit"]:
        raise DeployError("deployment_source_changed_during_preview")
    if plan.get("dependencies_changed") or args.interpreter:
        if args.target == "local" and not args.interpreter:
            raise DeployError("deployment_dependency_environment_required")
        interpreter = args.interpreter or str(source / ".venv/bin/python")
        check_dependency_environment(
            interpreter, git(source, "show", f"{plan['source_commit']}:requirements.txt"),
        )
    stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d-%H%M%S-%f")
    receipt_dir = source / "logs/run/deploy" / args.target / stamp
    plan["receipt"] = str(receipt_dir / "deployment.json")
    if args.target == "local" and plan["action"] == "restart":
        from tools.deploy_local import deploy_local
        from tools.release import MANIFEST_NAME, prepare_release

        release_id = stamp + "-" + plan["source_commit"][:8]
        releases = Path(plan["running_release"]).parent
        release = prepare_release(source, releases, release_id)
        if json.loads((release / MANIFEST_NAME).read_text())["source_commit"] != plan["source_commit"]:
            raise DeployError("deployment_source_changed_during_prepare")
        result = deploy_local(
            source=source, release=release, receipt_dir=receipt_dir, timeout=args.timeout,
            interpreter=Path(args.interpreter) if args.interpreter else None,
            allow_same_release=args.restart or args.http_threads is not None,
            http_threads=args.http_threads,
        )
        plan.update(result, backend_commit=plan["source_commit"])
    elif args.target == "oracle" and (
        plan["action"] != "noop" or plan["source_commit"] != plan["checkout_commit"]
    ):
        from tools.deploy_oracle import deploy_oracle

        if args.interpreter:
            raise DeployError("deployment_oracle_environment_requires_service_update")
        result = deploy_oracle(
            source=source, revision=plan["source_commit"], receipt_dir=receipt_dir,
            timeout=args.timeout, action=plan["action"],
        )
        plan.update(result)
        if plan["action"] == "restart":
            plan["backend_commit"] = plan["source_commit"]
        plan["checkout_commit"] = git(source, "rev-parse", "HEAD")
        if plan["checkout_commit"] != plan["source_commit"]:
            raise DeployError("deployment_source_changed_during_acceptance")
        identity = oracle_identity()
        if result.get("service_pid") and identity["pid"] != result["service_pid"]:
            raise DeployError("deployment_process_changed_during_acceptance")
        plan.update(identity)
    if not plan.get("http", {}).get("ok"):
        plan["http"] = verify_http(args.base_url, timeout=args.timeout)
    plan.update(ok=True, finished_at=stamp)
    save_receipt(receipt_dir / "deployment.json", plan)
    save_receipt(source / f"logs/run/deploy/{args.target}/last-success.json", plan)
    return plan


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("target", choices=("local", "oracle"), help="两端独立部署")
    value.add_argument("--apply", action="store_true", help="执行预览中的动作，默认只读")
    value.add_argument("--check", action="store_true", help="只检查健康；可热加载配置由现有 observer 应用")
    value.add_argument("--restart", action="store_true", help="启动环境或需重启配置变化时显式重启")
    value.add_argument("--source", help="目标端源码根目录；Oracle 路径在远端解释")
    value.add_argument("--revision", help="目标端已有的提交；Oracle 只允许快进合并，默认该端 HEAD")
    value.add_argument("--interpreter", help="依赖变化时指定已准备好的本地包外 Python 环境")
    value.add_argument("--http-threads", type=int, help="显式设置本地 Web HTTP 线程数并重启")
    value.add_argument("--host", default="oracle", help="Oracle SSH 别名")
    value.add_argument("--base-url", default="http://127.0.0.1:8000")
    value.add_argument("--timeout", type=float, default=180, help="等待空闲和启动的秒数")
    value.add_argument("--on-host", action="store_true", help=argparse.SUPPRESS)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise DeployError("deployment_timeout_invalid")
        if args.http_threads is not None:
            if args.target != "local":
                raise DeployError("deployment_http_threads_local_only")
            if not 1 <= args.http_threads <= 128:
                raise DeployError("deployment_http_threads_invalid")
        if args.target == "oracle" and args.interpreter:
            raise DeployError("deployment_oracle_environment_requires_service_update")
        if args.target == "oracle" and not args.on_host:
            return dispatch_oracle(args)
        args.source = args.source or str(ROOT)
        if args.check:
            result = {"target": args.target, "action": "check", **verify_http(args.base_url, timeout=args.timeout)}
        else:
            result = build_plan(args)
            if args.apply:
                result = execute(args, result)
            else:
                result["preview"] = True
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        detail = str(exc)
        code = detail if isinstance(exc, RuntimeError) and re.fullmatch(r"[a-z][a-z0-9_]+", detail) else (
            "deployment_" + type(exc).__name__
        )
        failure = {"ok": False, "target": args.target, "error_code": code}
        if args.apply and (args.target == "local" or args.on_host) and Path(args.source or ROOT).is_dir():
            plan = locals().get("result", {})
            stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d-%H%M%S-%f")
            receipt = Path(plan.get("receipt") or (
                Path(args.source or ROOT) / f"logs/run/deploy/{args.target}/{stamp}/deployment.json"
            ))
            try:
                save_receipt(receipt, {**plan, **failure})
                failure["receipt"] = str(receipt)
            except OSError:
                failure["receipt_error"] = "deployment_receipt_write_failed"
        print(json.dumps(failure, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
