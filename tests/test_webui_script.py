import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class WebUiScriptTests(unittest.TestCase):
    def test_logs_creates_log_directory_in_a_fresh_checkout(self):
        source_script = Path(__file__).resolve().parents[1] / "webui.sh"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "webui.sh"
            shutil.copy2(source_script, script)

            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_tail = fake_bin / "tail"
            fake_tail.write_text(
                "#!/bin/sh\n"
                "test -f \"$4\"\n",
                encoding="utf-8",
            )
            fake_tail.chmod(fake_tail.stat().st_mode | stat.S_IXUSR)

            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment.get('PATH', '')}"
            completed = subprocess.run(
                [str(script), "logs"],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((root / "logs" / "webui.log").is_file())


if __name__ == "__main__":
    unittest.main()
