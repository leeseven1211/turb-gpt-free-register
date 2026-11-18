import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class WebUiScriptTests(unittest.TestCase):
    def _log_fixture(self, existing):
        project_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            script = root / "webui.sh"
            shutil.copy2(project_root / "webui.sh", script)
            for relative in (
                "tools/manage_runtime.py", "tools/check_startup.py",
                "core/runtime/bootstrap.py", "core/runtime/role_launcher.py",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(project_root / relative, target)
            for relative in ("core/__init__.py", "core/runtime/__init__.py", "tools/__init__.py"):
                (root / relative).write_text("", encoding="utf-8")

            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_tail = fake_bin / "tail"
            fake_tail.write_text(
                "#!/bin/sh\n"
                "test \"$1\" = '-n' && test \"$2\" = '120' && test \"$3\" = '-f'\n"
                "test -f \"$4\" || exit 91\n"
                "printf '%s' \"$4\"\n",
                encoding="utf-8",
            )
            fake_tail.chmod(fake_tail.stat().st_mode | stat.S_IXUSR)
            fake_git = fake_bin / "git"
            fake_git.write_text(
                "#!/bin/sh\n"
                "test \"$1\" = '-C' && test \"$3\" = 'rev-parse' || exit 92\n"
                "case \"$4\" in\n"
                "  --show-toplevel) printf '%s\\n' \"$2\" ;;\n"
                "  HEAD) printf '%s\\n' 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' ;;\n"
                "  *) exit 93 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            fake_git.chmod(fake_git.stat().st_mode | stat.S_IXUSR)
            runtime_dir = root / "isolated-runtime"
            log = runtime_dir / "logs/combined.log"
            if existing:
                log.parent.mkdir(parents=True)
                log.write_text("synthetic saved log\n", encoding="utf-8")

            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment.get('PATH', '')}"
            environment["TURB_RUNTIME_DIR"] = str(runtime_dir)
            environment["TURB_INSTANCE_ID"] = "webui-script-test"
            environment["PYTHON_DOTENV_DISABLED"] = "1"
            environment.pop("TURB_RUNTIME_MANAGER", None)
            completed = subprocess.run(
                [str(script), "logs"],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return completed, str(log)

    def test_logs_reports_missing_role_log_without_starting_a_process(self):
        completed, _log = self._log_fixture(existing=False)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        self.assertIn('"error_code": "log_absent"', completed.stderr)
        self.assertEqual(completed.stdout, "")

    def test_logs_tails_existing_role_log_through_the_actual_control_entrypoint(self):
        completed, log = self._log_fixture(existing=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, log)


if __name__ == "__main__":
    unittest.main()
