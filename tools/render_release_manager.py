"""Render manager configuration for an immutable release and external runtime.

The repository templates remain usable for a checkout.  This module creates a
concrete, package-outside configuration for a validated release without
installing or starting a service.
"""
from __future__ import annotations

import os
import plistlib
import re
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any


_INSTANCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _paths(release_dir: Path | str, interpreter: Path | str) -> tuple[Path, Path]:
    release = Path(release_dir)
    python = Path(interpreter)
    if not release.is_absolute() or not python.is_absolute():
        raise ValueError("release_and_interpreter_must_be_absolute")
    release = release.resolve()
    # Resolving bin/python itself loses the venv (it commonly links to the
    # base interpreter). Preserve argv0 while checking both path boundaries.
    python = python.parent.resolve() / python.name
    _external_path(python, release, "interpreter_must_be_external")
    if python.is_relative_to(release):
        raise ValueError("interpreter_must_be_external")
    return release, python


def _instance(value: str) -> str:
    instance = str(value or "").strip()
    if not _INSTANCE.fullmatch(instance):
        raise ValueError("instance_invalid")
    return instance


def _external_path(value: Path | str, release: Path, code: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("path_must_be_absolute")
    path = path.resolve()
    try:
        path.relative_to(release)
    except ValueError:
        return path
    raise ValueError(code)


def _write(path: Path, payload: bytes) -> None:
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.tmp-{uuid.uuid4().hex}"
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def render_systemd_unit(
    template: Path | str,
    output: Path | str,
    *,
    release_dir: Path | str,
    interpreter: Path | str,
    instance: str,
    bootstrap_env_file: Path | str | None = None,
) -> Path:
    """Render one split systemd unit without mutating the source template."""
    release, python = _paths(release_dir, interpreter)
    target = _external_path(output, release, "output_path_must_be_external")
    for path in (release, python):
        if re.search(r"""[\s\\'"%$]""", str(path)):
            raise ValueError("systemd_path_requires_simple_absolute_path")
    instance_name = _instance(instance)
    text = Path(template).read_text(encoding="utf-8")
    old_working = "/srv/turb/%i/current"
    old_python = f"{old_working}/.venv/bin/python"
    text = text.replace(old_python, str(python)).replace(old_working, str(release))
    text = text.replace("%i", instance_name)
    bootstrap = _external_path(
        bootstrap_env_file or f"/etc/turb/{instance_name}/bootstrap.env",
        release, "bootstrap_env_path_must_be_external",
    )
    if re.search(r"""[\s\\'"%$]""", str(bootstrap)):
        raise ValueError("systemd_path_requires_simple_absolute_path")
    text = re.sub(r"(?m)^EnvironmentFile=.*$", f"EnvironmentFile={bootstrap}", text)
    text = text.replace(
        "Environment=PYTHONUNBUFFERED=1",
        f"Environment=TURB_BOOTSTRAP_ENV_FILE={bootstrap}\nEnvironment=PYTHONUNBUFFERED=1", 1,
    )
    if "Environment=PYTHONDONTWRITEBYTECODE=1" not in text:
        marker = "Environment=PYTHONUNBUFFERED=1"
        if marker in text:
            text = text.replace(
                marker,
                marker + "\nEnvironment=PYTHONDONTWRITEBYTECODE=1",
                1,
            )
        else:
            raise ValueError("systemd_template_missing_python_environment")
    if old_python in text:
        raise ValueError("systemd_template_kept_checkout_interpreter")
    _write(target, text.encode("utf-8"))
    return target


def _replace_text(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        for source, target in replacements.items():
            value = value.replace(source, target)
    return value


def render_launchd_plist(
    template: Path | str,
    output: Path | str,
    *,
    release_dir: Path | str,
    interpreter: Path | str,
    instance: str,
    runtime_dir: Path | str,
    task_log_dir: Path | str,
    logs_dir: Path | str,
    bootstrap_env_file: Path | str | None = None,
    environment_overrides: Mapping[str, str] | None = None,
) -> Path:
    """Render one split launchd plist with package-outside runtime paths."""
    release, python = _paths(release_dir, interpreter)
    target = _external_path(output, release, "output_path_must_be_external")
    instance_name = _instance(instance)
    runtime = _external_path(runtime_dir, release, "runtime_path_must_be_external")
    task_logs = _external_path(task_log_dir, release, "task_log_path_must_be_external")
    logs = _external_path(logs_dir, release, "manager_log_path_must_be_external")
    bootstrap = None if bootstrap_env_file is None else _external_path(
        bootstrap_env_file, release, "bootstrap_env_path_must_be_external",
    )
    value = plistlib.loads(Path(template).read_bytes())
    if not isinstance(value, dict):
        raise ValueError("launchd_template_invalid")
    arguments = value.get("ProgramArguments")
    if not isinstance(arguments, list) or len(arguments) < 2:
        raise ValueError("launchd_program_arguments_invalid")
    arguments = [str(item) for item in arguments]
    arguments[0] = str(python)
    arguments[1] = arguments[1].replace("/ABSOLUTE/PROJECT", str(release))
    value["ProgramArguments"] = arguments
    value["WorkingDirectory"] = str(release)
    replacements = {
        "INSTANCE": instance_name,
        "/ABSOLUTE/RUNTIME": str(runtime),
        "/ABSOLUTE/TASK_LOGS": str(task_logs),
        "/ABSOLUTE/LOGS": str(logs),
        "/ABSOLUTE/PROJECT": str(release),
    }
    environment = value.get("EnvironmentVariables")
    if not isinstance(environment, dict):
        raise ValueError("launchd_environment_invalid")
    value["EnvironmentVariables"] = {
        str(key): _replace_text(str(item), replacements)
        for key, item in environment.items()
    }
    value["EnvironmentVariables"]["PYTHONDONTWRITEBYTECODE"] = "1"
    if bootstrap is not None:
        value["EnvironmentVariables"]["TURB_BOOTSTRAP_ENV_FILE"] = str(bootstrap)
    for key, item in (environment_overrides or {}).items():
        # 凭据可以私下继承；角色身份和路径必须由已校验的参数确定。
        if key in value["EnvironmentVariables"] or key in {"PYTHON_DOTENV_DISABLED", "TURB_BOOTSTRAP_ENV_FILE"}:
            raise ValueError("manager_environment_override_reserved")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError("manager_environment_override_invalid")
        if not isinstance(item, str) or "\x00" in item:
            raise ValueError("manager_environment_override_invalid")
        value["EnvironmentVariables"][key] = item
    value["Label"] = _replace_text(str(value.get("Label") or ""), replacements)
    value["StandardOutPath"] = _replace_text(str(value["StandardOutPath"]), replacements)
    value["StandardErrorPath"] = _replace_text(str(value["StandardErrorPath"]), replacements)
    _write(target, plistlib.dumps(value, fmt=plistlib.FMT_XML, sort_keys=False))
    return target
