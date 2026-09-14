#!/usr/bin/env python3
"""Prepare and validate immutable application releases.

The commands in this module only copy committed, non-private source files and
atomically update a local symlink. They do not start, stop, restart, or deploy
the running service. A release directory is valid only when its manifest and
every recorded file hash pass before a switch is attempted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_NAME = "release-manifest.json"
MANIFEST_SCHEMA_VERSION = 1
RELEASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PRIVATE_DIRS = frozenset(
    {
        ".venv",
        "logs",
        "run",
        "codex_accounts",
        "accounts",
        "output",
        "data",
        "__pycache__",
    }
)
PRIVATE_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".jsonl")
LOCK_NAMES = ("requirements.txt", "requirements-dev.txt")


class ReleaseError(ValueError):
    """Raised when a release cannot be safely prepared, checked, or switched."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_release_id(value: str) -> str:
    release_id = str(value or "").strip()
    if not RELEASE_ID_RE.fullmatch(release_id) or release_id in {".", ".."}:
        raise ReleaseError("release id 只能包含字母、数字、点、下划线和短横线")
    return release_id


def _is_private_path(relative: Path | PurePosixPath) -> bool:
    parts = tuple(str(part) for part in relative.parts)
    if not parts:
        return True
    name = parts[-1]
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    if any(part in PRIVATE_DIRS for part in parts):
        return True
    return name.endswith(PRIVATE_SUFFIXES)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_output(source: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(source), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or "git command failed"
        raise ReleaseError(f"无法从已提交 Git 源码生成 release: {str(detail).strip()[:240]}") from exc
    return completed.stdout


def _source_commit(source: Path) -> str:
    commit = _git_output(source, "rev-parse", "HEAD").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", commit):
        raise ReleaseError("源码没有可记录的 Git commit")
    dirty = _git_output(source, "status", "--porcelain", "--untracked-files=no").strip()
    if dirty:
        raise ReleaseError("prepare 要求源码工作树没有未提交的 tracked 改动")
    return commit


def _tracked_paths(source: Path) -> list[Path]:
    output = _git_output(source, "ls-files", "-z")
    paths: list[Path] = []
    for raw in output.split("\x00"):
        if not raw:
            continue
        relative = Path(raw)
        if relative.is_absolute() or ".." in relative.parts:
            raise ReleaseError(f"Git 路径越界: {raw!r}")
        if _is_private_path(relative):
            continue
        source_path = source / relative
        if source_path.is_symlink():
            raise ReleaseError(f"release 不接受符号链接: {relative}")
        if not source_path.is_file():
            continue
        paths.append(relative)
    return sorted(paths, key=lambda value: value.as_posix())


def _relative_manifest_path(value: object) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ReleaseError("manifest 文件路径必须是非空 POSIX 相对路径")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise ReleaseError(f"manifest 文件路径越界: {value!r}")
    relative = Path(*pure.parts)
    if _is_private_path(relative):
        raise ReleaseError(f"manifest 不得记录私有文件: {value!r}")
    return relative


def _load_manifest(release_dir: Path) -> dict[str, Any]:
    manifest_path = release_dir / MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ReleaseError(f"缺少 release manifest: {manifest_path}")
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"无法读取 release manifest: {manifest_path}") from exc
    if not isinstance(value, dict):
        raise ReleaseError("release manifest 必须是 JSON object")
    return value


def _lock_checker():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from tools.check_dependencies import validate_locks

    return validate_locks


def _validate_project_files(root: Path) -> dict[str, int]:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        raise ReleaseError("缺少 pyproject.toml")
    text = pyproject.read_text(encoding="utf-8")
    if not re.search(r"(?m)^\s*requires-python\s*=\s*[\"']>=3\.10[\"']\s*$", text):
        raise ReleaseError("pyproject.toml 必须声明 Python >=3.10")
    try:
        return _lock_checker()(root)
    except Exception as exc:
        raise ReleaseError(f"依赖锁校验失败: {exc}") from exc


def _manifest_for(release_id: str, source_commit: str, files: list[dict[str, Any]], locks: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "release_id": release_id,
        "source_commit": source_commit,
        "python_requires": ">=3.10",
        "generated_at": _utc_now(),
        "files": files,
        "locks": locks,
    }


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.tmp-{uuid.uuid4().hex}"
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError:
        if temporary.is_file():
            temporary.unlink()
        raise


def prepare_release(source: Path | str, releases_dir: Path | str, release_id: str) -> Path:
    """Copy committed source into a fixed release directory and write its manifest."""
    source_root = Path(source).resolve()
    releases_root = Path(releases_dir).resolve()
    safe_id = _safe_release_id(release_id)
    if not source_root.is_dir():
        raise ReleaseError(f"源码目录不存在: {source_root}")
    _validate_project_files(source_root)
    source_commit = _source_commit(source_root)
    final_dir = releases_root / safe_id
    if final_dir.exists() or final_dir.is_symlink():
        raise ReleaseError(f"release 已存在，不覆盖: {final_dir}")
    releases_root.mkdir(parents=True, exist_ok=True)
    staging = releases_root / f".{safe_id}.staging-{uuid.uuid4().hex}"
    files: list[dict[str, Any]] = []
    try:
        for relative in _tracked_paths(source_root):
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_root / relative, destination)
            files.append(
                {
                    "path": relative.as_posix(),
                    "size": destination.stat().st_size,
                    "sha256": _sha256(destination),
                }
            )
        locks = {
            name: _sha256(staging / name)
            for name in LOCK_NAMES
            if (staging / name).is_file()
        }
        manifest = _manifest_for(safe_id, source_commit, files, locks)
        _write_json_atomic(staging / MANIFEST_NAME, manifest)
        check_release(staging, expected_release_id=safe_id, validate_project=True)
        os.replace(staging, final_dir)
    except Exception:
        # Leave a failed staging directory for inspection/recovery. It is
        # outside the fixed release namespace and is never switched to.
        raise
    return final_dir


def check_release(
    release_dir: Path | str,
    *,
    expected_release_id: str | None = None,
    validate_project: bool = True,
) -> dict[str, Any]:
    """Validate manifest, hashes, private-file boundaries, and dependency locks."""
    raw_root = Path(os.path.abspath(os.fspath(release_dir)))
    if raw_root.is_symlink():
        raise ReleaseError(f"release 目录不得是符号链接: {raw_root}")
    root = raw_root.resolve()
    if not root.is_dir():
        raise ReleaseError(f"release 目录不存在或不是普通目录: {root}")
    manifest = _load_manifest(root)
    release_id = _safe_release_id(str(manifest.get("release_id") or ""))
    if expected_release_id is not None and release_id != _safe_release_id(expected_release_id):
        raise ReleaseError("release id 与 manifest 不一致")
    if expected_release_id is None and _safe_release_id(root.name) != release_id:
        raise ReleaseError("release 目录名与 manifest release_id 不一致")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ReleaseError("不支持的 release manifest schema_version")
    if not isinstance(manifest.get("source_commit"), str) or not re.fullmatch(
        r"[0-9a-fA-F]{7,64}", str(manifest["source_commit"])
    ):
        raise ReleaseError("manifest source_commit 无效")
    if manifest.get("python_requires") != ">=3.10":
        raise ReleaseError("manifest python_requires 必须为 >=3.10")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ReleaseError("manifest files 不能为空")

    recorded: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ReleaseError("manifest files 项必须是 object")
        relative = _relative_manifest_path(item.get("path"))
        key = relative.as_posix()
        if key in recorded or key == MANIFEST_NAME:
            raise ReleaseError(f"manifest 存在重复文件: {key}")
        recorded.add(key)
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ReleaseError(f"release 文件缺失或不是普通文件: {key}")
        if item.get("size") != path.stat().st_size or item.get("sha256") != _sha256(path):
            raise ReleaseError(f"release 文件校验失败: {key}")

    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ReleaseError(f"release 不得包含符号链接: {path.relative_to(root)}")
        if path.is_file() and path.name != MANIFEST_NAME:
            relative = path.relative_to(root)
            if _is_private_path(relative):
                raise ReleaseError(f"release 包含私有文件: {relative}")
            actual.add(relative.as_posix())
    if actual != recorded:
        extras = sorted(actual - recorded)
        missing = sorted(recorded - actual)
        raise ReleaseError(f"release 文件清单不一致: extras={extras[:5]} missing={missing[:5]}")

    locks = manifest.get("locks")
    if not isinstance(locks, dict) or any(name not in locks for name in LOCK_NAMES):
        raise ReleaseError("manifest 必须记录运行与开发依赖锁")
    for name in LOCK_NAMES:
        lock_path = root / name
        if not lock_path.is_file() or locks.get(name) != _sha256(lock_path):
            raise ReleaseError(f"manifest lock 校验失败: {name}")
    lock_report = _validate_project_files(root) if validate_project else {}
    return {
        "ok": True,
        "release_id": release_id,
        "source_commit": manifest["source_commit"],
        "files": len(recorded),
        "locks": lock_report,
    }


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _current_target(current_link: Path, releases_root: Path) -> Path | None:
    if not current_link.exists() and not current_link.is_symlink():
        return None
    if not current_link.is_symlink():
        raise ReleaseError(f"current link 已存在但不是符号链接: {current_link}")
    try:
        target = current_link.resolve(strict=True)
    except OSError as exc:
        raise ReleaseError(f"current link 是悬空链接: {current_link}") from exc
    if not target.is_dir() or not _within(target, releases_root):
        raise ReleaseError("current link 指向 release 目录之外，拒绝切换")
    return target


def _atomic_link(current_link: Path, target: Path) -> None:
    current_link.parent.mkdir(parents=True, exist_ok=True)
    candidate = current_link.parent / f".{current_link.name}.next-{uuid.uuid4().hex}"
    try:
        candidate.symlink_to(target, target_is_directory=True)
        os.replace(candidate, current_link)
    except OSError:
        if candidate.is_symlink():
            candidate.unlink()
        raise


def _state_path(state_file: Path | str | None, releases_root: Path) -> Path:
    if state_file is None:
        return releases_root / ".switch-state.json"
    path = Path(os.path.abspath(os.fspath(state_file)))
    if path.is_symlink():
        raise ReleaseError(f"state 文件不得是符号链接: {path}")
    return path


def switch_release(
    releases_dir: Path | str,
    release_id: str,
    *,
    current_link: Path | str,
    state_file: Path | str | None = None,
) -> dict[str, Any]:
    """Preflight and atomically point ``current_link`` at one immutable release."""
    releases_root = Path(releases_dir).resolve()
    safe_id = _safe_release_id(release_id)
    raw_target = releases_root / safe_id
    if raw_target.is_symlink() or not raw_target.is_dir():
        raise ReleaseError(f"release target 不存在或不是普通目录: {raw_target}")
    target = raw_target.resolve()
    if target.parent != releases_root:
        raise ReleaseError("release target 必须是 releases_dir 的直接子目录")
    report = check_release(target, expected_release_id=safe_id)
    # ``Path.resolve()`` follows an existing current symlink and would make
    # the target look like a regular directory. Keep the link pathname itself.
    link = Path(os.path.abspath(os.fspath(current_link)))
    previous = _current_target(link, releases_root)
    _atomic_link(link, target)
    state = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "updated_at": _utc_now(),
        "current_link": str(link),
        "current_release": safe_id,
        "previous_release": previous.name if previous else None,
    }
    _write_json_atomic(_state_path(state_file, releases_root), state)
    return {**report, "current_link": str(link), "previous_release": state["previous_release"]}


def rollback_release(
    releases_dir: Path | str,
    *,
    current_link: Path | str,
    state_file: Path | str | None = None,
    release_id: str | None = None,
) -> dict[str, Any]:
    """Switch back to the recorded previous release, or an explicit safe target."""
    releases_root = Path(releases_dir).resolve()
    state_path = _state_path(state_file, releases_root)
    target_id = release_id
    state: dict[str, Any] = {}
    if target_id is None:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReleaseError("rollback 缺少有效 switch state，请显式指定 release id") from exc
        target_id = state.get("previous_release")
    safe_id = _safe_release_id(str(target_id or ""))
    raw_target = releases_root / safe_id
    if raw_target.is_symlink() or not raw_target.is_dir():
        raise ReleaseError(f"rollback target 不存在或不是普通目录: {raw_target}")
    target = raw_target.resolve()
    if target.parent != releases_root:
        raise ReleaseError("rollback target 必须是 releases_dir 的直接子目录")
    report = check_release(target, expected_release_id=safe_id)
    link = Path(os.path.abspath(os.fspath(current_link)))
    previous = _current_target(link, releases_root)
    _atomic_link(link, target)
    new_state = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "updated_at": _utc_now(),
        "current_link": str(link),
        "current_release": safe_id,
        "previous_release": previous.name if previous else None,
    }
    _write_json_atomic(state_path, new_state)
    return {**report, "current_link": str(link), "previous_release": new_state["previous_release"]}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查、准备和原子切换固定 release（默认只检查）")
    parser.add_argument("command", nargs="?", choices=("check", "prepare", "switch", "rollback"), default="check")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="源码/项目根目录")
    parser.add_argument("--source", type=Path, help="prepare 使用的已提交源码目录")
    parser.add_argument("--releases-dir", type=Path, default=Path("releases"), help="固定 release 父目录")
    parser.add_argument("--release-dir", type=Path, help="check 指定的 release 目录")
    parser.add_argument("--release-id", help="固定 release id")
    parser.add_argument("--current-link", type=Path, default=Path("current"), help="switch/rollback 使用的 current 符号链接")
    parser.add_argument("--state-file", type=Path, help="switch state 文件，默认在 releases-dir 内")
    parser.add_argument("--json", action="store_true", help="输出 JSON 摘要")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "check":
            target = args.release_dir or args.root
            if (target / MANIFEST_NAME).is_file():
                result = check_release(target, expected_release_id=args.release_id)
            else:
                result = {"ok": True, "source": str(target.resolve()), "locks": _validate_project_files(target)}
        elif args.command == "prepare":
            if not args.release_id:
                raise ReleaseError("prepare 必须显式指定 --release-id")
            result = {
                "ok": True,
                "release_dir": str(
                    prepare_release(args.source or args.root, args.releases_dir, args.release_id)
                ),
            }
        elif args.command == "switch":
            if not args.release_id:
                raise ReleaseError("switch 必须显式指定 --release-id")
            result = switch_release(
                args.releases_dir,
                args.release_id,
                current_link=args.current_link,
                state_file=args.state_file,
            )
        else:
            result = rollback_release(
                args.releases_dir,
                current_link=args.current_link,
                state_file=args.state_file,
                release_id=args.release_id,
            )
    except (OSError, ReleaseError) as exc:
        print(f"release check failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
