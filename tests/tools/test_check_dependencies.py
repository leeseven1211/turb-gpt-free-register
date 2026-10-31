"""依赖锁的环境 marker、精确版本和非法尾部回归。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.check_dependencies import (
    LockValidationError,
    _parse_input_pins,
    _parse_lock_file,
    validate_locks,
)


@pytest.mark.parametrize("kind", ["lock", "input"])
@pytest.mark.parametrize(
    "requirement",
    [
        'wreq==0.13.0; python_version >= "3.11"',
        'wreq==0.13.0 ; python_version < "0"',
        'wreq==0.13.0; (python_version >= "3.11" and sys_platform == "linux") or os_name == "nt"',
        'wreq[extra]==0.13.0; python_version >= "3.11" # 受支持的版本条件',
    ],
)
def test_exact_pins_accept_environment_markers(tmp_path: Path, kind: str, requirement: str):
    """检查完整锁内容，不按执行检查器的本机环境过滤依赖。"""
    source = tmp_path / ("requirements.txt" if kind == "lock" else "requirements.in")
    source.write_text(requirement + "\n", encoding="utf-8")
    if kind == "lock":
        entries = _parse_lock_file(source)
        assert [(entry.name, entry.version, entry.line_number) for entry in entries] == [
            ("wreq", "0.13.0", 1)
        ]
    else:
        assert _parse_input_pins(source) == {"wreq": "0.13.0"}


@pytest.mark.parametrize("kind", ["lock", "input"])
@pytest.mark.parametrize(
    "requirement",
    [
        "wreq==0.13.0 arbitrary-tail",
        'wreq==0.13.0 ; python_version >= "3.11"; echo bad',
        'wreq==0.13.0 ; unknown_variable == "linux"',
        'wreq==0.13.0 ; python_version >=',
        'wreq==0.13.0 ; python_version >= "3.11" --index-url https://example.invalid',
        "wreq==0.13.0 --extra-index-url https://example.invalid",
        'wreq>=0.13.0; python_version >= "3.11"',
        'wreq==0.13.*; python_version >= "3.11"',
        'wreq===0.13.0; python_version >= "3.11"',
        'wreq==0.13.0,!=0.13.1; python_version >= "3.11"',
        'wreq @ https://example.invalid/wreq.whl ; python_version >= "3.11"',
    ],
)
def test_invalid_or_unpinned_requirements_are_rejected(
    tmp_path: Path, kind: str, requirement: str
):
    source = tmp_path / ("requirements.txt" if kind == "lock" else "requirements.in")
    source.write_text(requirement + "\n", encoding="utf-8")
    parser = _parse_lock_file if kind == "lock" else _parse_input_pins
    with pytest.raises(LockValidationError, match=r":1:"):
        parser(source)


@pytest.mark.parametrize("locked_version", ["0.13.0", "0.12.0"])
def test_marked_pins_keep_direct_version_and_include_validation(
    tmp_path: Path, locked_version: str
):
    (tmp_path / "requirements.in").write_text(
        'wreq==0.13.0; python_version >= "3.11"\n', encoding="utf-8"
    )
    (tmp_path / "requirements.txt").write_text(
        f'wreq=={locked_version}; python_version >= "3.11"\n', encoding="utf-8"
    )
    (tmp_path / "requirements-dev.in").write_text("-r requirements.txt\n", encoding="utf-8")
    (tmp_path / "requirements-dev.txt").write_text("-r requirements.txt\n", encoding="utf-8")
    if locked_version == "0.13.0":
        assert validate_locks(tmp_path) == {
            "runtime_entries": 1,
            "development_entries": 1,
            "runtime_direct": 1,
            "development_direct": 0,
        }
    else:
        with pytest.raises(LockValidationError, match="版本不匹配"):
            validate_locks(tmp_path)


def test_check_works_with_pip_parser_when_packaging_is_not_installed(tmp_path: Path):
    """仅安装运行锁的环境仍能用 pip 的解析器完成实际命令行检查。"""
    for name in ("requirements.in", "requirements.txt"):
        (tmp_path / name).write_text(
            'wreq==0.13.0; python_version >= "3.11"\n', encoding="utf-8"
        )
    for name in ("requirements-dev.in", "requirements-dev.txt"):
        (tmp_path / name).write_text("-r requirements.txt\n", encoding="utf-8")
    script = Path(__file__).resolve().parents[2] / "tools" / "check_dependencies.py"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy, sys; sys.modules['packaging'] = None; "
            "sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')",
            str(script),
            "--root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "runtime=1 packages, development=1 packages" in result.stdout
