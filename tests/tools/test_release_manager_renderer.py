from pathlib import Path
import json
import plistlib
import subprocess
import venv

import pytest

from tools.render_release_manager import render_launchd_plist, render_systemd_unit


ROOT = Path(__file__).resolve().parents[2]


def test_render_systemd_unit_binds_external_interpreter_and_release(tmp_path):
    release = tmp_path / "releases" / "r1"
    interpreter = tmp_path / "environments" / "lock-py311" / "bin" / "python"
    output = tmp_path / "turb-web@r1.service"

    render_systemd_unit(
        ROOT / "deploy/systemd/turb-web@.service",
        output,
        release_dir=release,
        interpreter=interpreter,
        instance="r1",
    )

    text = output.read_text(encoding="utf-8")
    assert f"WorkingDirectory={release}" in text
    assert f"ExecStart={interpreter} {release}/web.py" in text
    assert "Environment=PYTHONDONTWRITEBYTECODE=1" in text
    assert "current/.venv" not in text
    assert "TimeoutStopSec=90" in text


def test_render_launchd_plist_uses_external_interpreter_and_keeps_role_boundaries(tmp_path):
    release = tmp_path / "releases" / "r1"
    interpreter = tmp_path / "environments" / "lock-py311" / "bin" / "python"
    runtime = tmp_path / "runtime"
    task_logs = tmp_path / "task-logs"
    output = tmp_path / "turb-worker.plist"

    render_launchd_plist(
        ROOT / "deploy/launchd/local.turb.worker.plist.example",
        output,
        release_dir=release,
        interpreter=interpreter,
        instance="r1",
        runtime_dir=runtime,
        task_log_dir=task_logs,
        logs_dir=tmp_path / "logs",
    )

    value = plistlib.loads(output.read_bytes())
    assert value["ProgramArguments"][0] == str(interpreter)
    assert value["ProgramArguments"][1] == str(release / "worker.py")
    assert value["WorkingDirectory"] == str(release)
    assert value["EnvironmentVariables"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert value["EnvironmentVariables"]["TURB_INSTANCE_ID"] == "r1"
    assert value["ExitTimeOut"] == 60
    assert value["ProgramArguments"][-2:] == ["--shutdown-timeout", "55"]
    assert value["StandardOutPath"] == str(tmp_path / "logs" / "worker.stdout.log")


def test_render_manager_rejects_interpreter_inside_release(tmp_path):
    release = tmp_path / "release"
    with pytest.raises(ValueError, match="interpreter_must_be_external"):
        render_systemd_unit(
            ROOT / "deploy/systemd/turb-worker@.service",
            tmp_path / "worker.service",
            release_dir=release,
            interpreter=release / "bin/python",
            instance="r1",
        )


def test_render_launchd_rejects_runtime_paths_inside_release(tmp_path):
    release = tmp_path / "release"
    with pytest.raises(ValueError, match="runtime_path_must_be_external"):
        render_launchd_plist(
            ROOT / "deploy/launchd/local.turb.worker.plist.example",
            tmp_path / "worker.plist",
            release_dir=release,
            interpreter=tmp_path / "python",
            instance="r1",
            runtime_dir=release / "runtime",
            task_log_dir=tmp_path / "task-logs",
            logs_dir=tmp_path / "logs",
        )


def test_render_manager_keeps_symlink_venv_identity(tmp_path):
    environment = tmp_path / "environment"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    interpreter = environment / "bin/python"
    output = tmp_path / "worker.plist"
    render_launchd_plist(
        ROOT / "deploy/launchd/local.turb.worker.plist.example",
        output,
        release_dir=tmp_path / "release",
        interpreter=interpreter,
        instance="r1",
        runtime_dir=tmp_path / "runtime",
        task_log_dir=tmp_path / "task-logs",
        logs_dir=tmp_path / "logs",
    )
    command = plistlib.loads(output.read_bytes())["ProgramArguments"][0]
    probe = subprocess.run(
        [command, "-B", "-c", "import sys,json; print(json.dumps(sys.prefix))"],
        capture_output=True, text=True, check=True,
    )
    assert Path(json.loads(probe.stdout)) == environment.resolve()
    assert command == str(interpreter)


@pytest.mark.parametrize("field", ["release_dir", "interpreter"])
def test_render_manager_rejects_relative_paths(tmp_path, field):
    arguments = {
        "release_dir": tmp_path / "release",
        "interpreter": tmp_path / "python",
        "instance": "r1",
    }
    arguments[field] = Path("relative")
    with pytest.raises(ValueError, match="must_be_absolute"):
        render_systemd_unit(
            ROOT / "deploy/systemd/turb-worker@.service",
            tmp_path / "worker.service",
            **arguments,
        )


def test_render_manager_rejects_output_inside_release(tmp_path):
    release = tmp_path / "release"
    with pytest.raises(ValueError, match="output_path_must_be_external"):
        render_systemd_unit(
            ROOT / "deploy/systemd/turb-worker@.service",
            release / "worker.service",
            release_dir=release,
            interpreter=tmp_path / "python",
            instance="r1",
        )
    assert not release.exists()


def test_render_systemd_rejects_ambiguous_unquoted_path(tmp_path):
    with pytest.raises(ValueError, match="systemd_path_requires_simple_absolute_path"):
        render_systemd_unit(
            ROOT / "deploy/systemd/turb-worker@.service",
            tmp_path / "worker.service",
            release_dir=tmp_path / "release with spaces",
            interpreter=tmp_path / "python",
            instance="r1",
        )
