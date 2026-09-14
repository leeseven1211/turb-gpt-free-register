#!/usr/bin/env python3
"""Validate the repository's resolver-produced dependency locks.

This check deliberately validates version pins and include boundaries instead
of inspecting a local environment. A lock generated on one machine is not a
portable wheel/artifact lock; the supported Python/platform range is stated in
the lock headers and in the release documentation.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


_PACKAGE_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)\s*==\s*(?P<version>[A-Za-z0-9][A-Za-z0-9_.!+~-]*)"
    r"(?:\s+.*)?$"
)
_DIRECT_PIN = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^]]+\])?\s*==\s*"
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9.!+~-]*)\s*$"
)
_INCLUDE_PREFIXES = ("-r ", "--requirement ")


@dataclass(frozen=True)
class LockEntry:
    """One normalized package pin from a lock file."""

    name: str
    version: str
    source: Path
    line_number: int


class LockValidationError(ValueError):
    """Raised when a lock file is not deterministic or is malformed."""


def _normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _included_path(line: str, source: Path) -> Path | None:
    for prefix in _INCLUDE_PREFIXES:
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            if not value:
                raise LockValidationError(f"{source}: 空的 requirements include")
            return (source.parent / value).resolve()
    return None


def _parse_lock_file(path: Path, *, seen: set[Path] | None = None) -> list[LockEntry]:
    """Parse exact ``name==version`` entries and recursively resolve ``-r``."""
    current = path.resolve()
    if seen is None:
        seen = set()
    if current in seen:
        raise LockValidationError(f"requirements include 循环: {current}")
    if not current.is_file():
        raise LockValidationError(f"缺少 requirements lock: {current}")

    seen.add(current)
    entries: list[LockEntry] = []
    try:
        lines = current.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise LockValidationError(f"无法读取 lock {current}: {exc}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("--hash=") or line.startswith("--hash "):
            continue
        include = _included_path(line, current)
        if include is not None:
            entries.extend(_parse_lock_file(include, seen=seen))
            continue
        if line.startswith(("-e ", "--editable ", "git+", "file:", "/", "./", "../")):
            raise LockValidationError(
                f"{current}:{line_number}: lock 不得包含 editable/VCS/本地路径: {line}"
            )
        if line.startswith("-"):
            raise LockValidationError(f"{current}:{line_number}: 不允许的 requirements 选项: {line}")
        match = _PACKAGE_LINE.fullmatch(line)
        if not match:
            raise LockValidationError(
                f"{current}:{line_number}: 依赖必须固定为 name==version: {line}"
            )
        entries.append(
            LockEntry(
                name=match.group("name"),
                version=match.group("version"),
                source=current,
                line_number=line_number,
            )
        )
    seen.remove(current)
    return entries


def _parse_input_pins(path: Path) -> dict[str, str]:
    """Read direct exact pins so a lock cannot silently drift from its inputs."""
    pins: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if line.startswith(("git+", "file:", "/", "./", "../")):
            raise LockValidationError(f"{path}:{line_number}: direct input 不得使用本地/VCS依赖")
        match = _DIRECT_PIN.fullmatch(line)
        if match is None:
            raise LockValidationError(f"{path}:{line_number}: direct input 必须固定为 name==version: {line}")
        pins[_normalized_name(match.group("name"))] = match.group("version")
    return pins


def validate_locks(root: Path) -> dict[str, int]:
    """Validate runtime and development locks below ``root``.

    The returned counts are suitable for human-readable check output and do
    not contain package versions from the executing environment.
    """
    runtime_lock = root / "requirements.txt"
    dev_lock = root / "requirements-dev.txt"
    runtime_input = root / "requirements.in"
    dev_input = root / "requirements-dev.in"
    for required in (runtime_lock, dev_lock, runtime_input, dev_input):
        if not required.is_file():
            raise LockValidationError(f"缺少依赖文件: {required}")

    runtime_entries = _parse_lock_file(runtime_lock)
    dev_entries = _parse_lock_file(dev_lock)
    runtime_names = {_normalized_name(entry.name) for entry in runtime_entries}
    dev_names = {_normalized_name(entry.name) for entry in dev_entries}

    direct_runtime = _parse_input_pins(runtime_input)
    missing_runtime = sorted(set(direct_runtime) - runtime_names)
    if missing_runtime:
        raise LockValidationError(f"运行锁缺少直接依赖: {', '.join(missing_runtime)}")

    direct_dev = _parse_input_pins(dev_input)
    missing_dev = sorted(set(direct_dev) - dev_names)
    if missing_dev:
        raise LockValidationError(f"开发锁缺少直接依赖: {', '.join(missing_dev)}")

    def reject_conflicts(entries: list[LockEntry], label: str) -> None:
        versions: dict[str, str] = {}
        for entry in entries:
            key = _normalized_name(entry.name)
            previous = versions.get(key)
            if previous is not None and previous != entry.version:
                raise LockValidationError(
                    f"{label} 对 {entry.name} 出现冲突版本: {previous} 与 {entry.version}"
                )
            versions[key] = entry.version

    reject_conflicts(runtime_entries, "运行锁")
    reject_conflicts(dev_entries, "开发锁")
    runtime_versions = {
        _normalized_name(entry.name): entry.version for entry in runtime_entries
    }
    development_versions = {
        _normalized_name(entry.name): entry.version for entry in dev_entries
    }
    for name, expected in direct_runtime.items():
        actual = runtime_versions.get(name)
        if actual != expected:
            raise LockValidationError(f"运行锁直接依赖 {name} 版本不匹配: {expected} != {actual}")
    for name, expected in direct_dev.items():
        actual = development_versions.get(name)
        if actual != expected:
            raise LockValidationError(f"开发锁直接依赖 {name} 版本不匹配: {expected} != {actual}")
    if not runtime_names.issubset(dev_names):
        missing_in_dev = sorted(runtime_names - dev_names)
        raise LockValidationError(f"开发锁未继承完整运行锁: {', '.join(missing_in_dev)}")

    return {
        "runtime_entries": len(runtime_entries),
        "development_entries": len(dev_entries),
        "runtime_direct": len(direct_runtime),
        "development_direct": len(direct_dev),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 resolver 生成的依赖锁")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="项目根目录，默认为当前脚本所在项目",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出摘要")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    try:
        report = validate_locks(root)
    except (LockValidationError, OSError) as exc:
        print(f"dependency lock check failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        import json

        print(json.dumps({"ok": True, **report}, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "dependency locks ok: "
            f"runtime={report['runtime_entries']} packages, "
            f"development={report['development_entries']} packages"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
