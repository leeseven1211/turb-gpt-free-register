"""A standalone dispatcher must stop admitting work when its owner is lost."""
from __future__ import annotations

import threading
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.runtime import execution_access, standalone


class StandaloneExecutionAccessTests(unittest.TestCase):
    def setUp(self):
        previous_owner, previous_lost = standalone._OWNER, standalone._LOST
        previous_binding = getattr(standalone, "_BINDING", None)
        standalone._OWNER = None
        standalone._LOST = threading.Event()
        self.addCleanup(setattr, standalone, "_OWNER", previous_owner)
        self.addCleanup(setattr, standalone, "_LOST", previous_lost)
        self.addCleanup(setattr, standalone, "_BINDING", previous_binding)
        self.context = patch.object(execution_access, "_context", return_value=None)
        self.context.start()
        self.addCleanup(self.context.stop)

    def assert_access(self, expected):
        self.assertEqual({
            "component": execution_access.component_start_allowed(),
            "admission": execution_access.execution_allowed(),
            "settlement": execution_access.execution_owner_valid(),
            "support": execution_access.execution_support_allowed(),
        }, dict.fromkeys(("component", "admission", "settlement", "support"), expected))

    def test_unconfigured_offline_callers_keep_their_compatibility_boundary(self):
        self.assert_access(True)

    def test_standalone_owner_loss_closes_every_execution_boundary(self):
        standalone._OWNER = type("Owner", (), {"require_owner": lambda _self: None})()
        self.assert_access(True)
        standalone._LOST.set()
        self.assert_access(False)

    def test_invalid_owner_is_fenced_even_before_its_loss_callback_runs(self):
        class Owner:
            valid = True

            def require_owner(self):
                if not self.valid:
                    raise RuntimeError("owner_probe_timeout")

        owner = Owner()
        standalone._OWNER = owner
        self.assert_access(True)
        owner.valid = False
        self.assert_access(False)
        owner.valid = True
        self.assert_access(False)

    def test_explicit_target_owner_refuses_a_different_binding(self):
        class Owner:
            starts = 0

            def start(self):
                self.starts += 1

            def require_owner(self):
                pass

        bootstrap = SimpleNamespace(mode="combined", instance_id="target",
                                    runtime_dir=Path("/stable/target"))
        connect = lambda: None
        owner = Owner()
        with patch("core.runtime.process.get_runtime_context", return_value=None), \
                patch("core.runtime.instance_owner.ExecutionOwner", return_value=owner), \
                patch.object(standalone.atexit, "register"):
            standalone.require_standalone_owner(bootstrap=bootstrap, schema="target_schema",
                                               connect_dedicated=connect)
            standalone.require_standalone_owner(bootstrap=bootstrap, schema="target_schema",
                                               connect_dedicated=connect)
            variants = (
                {"schema": "different_schema"},
                {"bootstrap": SimpleNamespace(mode="combined", instance_id="other",
                                              runtime_dir=Path("/stable/target"))},
                {"bootstrap": SimpleNamespace(mode="combined", instance_id="target",
                                              runtime_dir=Path("/stable/other"))},
                {"connect_dedicated": lambda: None},
            )
            for changed in variants:
                values = dict(bootstrap=bootstrap, schema="target_schema", connect_dedicated=connect)
                values.update(changed)
                with self.subTest(changed=tuple(changed)):
                    with self.assertRaisesRegex(RuntimeError, "standalone_owner_binding_mismatch"):
                        standalone.require_standalone_owner(**values)
        self.assertEqual(owner.starts, 1)

    def test_failed_start_closes_the_unused_owner_resources(self):
        class Owner:
            closed = False

            def start(self):
                raise RuntimeError("owner_database_busy")

            def close(self, *, timeout):
                self.closed = True
                return True

        owner = Owner()
        bootstrap = SimpleNamespace(mode="combined", instance_id="target",
                                    runtime_dir=Path("/stable/target"))
        with patch("core.runtime.process.get_runtime_context", return_value=None), \
                patch("core.runtime.instance_owner.ExecutionOwner", return_value=owner):
            with self.assertRaisesRegex(RuntimeError, "owner_database_busy"):
                standalone.require_standalone_owner(
                    bootstrap=bootstrap, schema="target", connect_dedicated=lambda: None)
        self.assertTrue(owner.closed)
        self.assertIsNone(standalone._OWNER)

    @unittest.skipUnless(os.name == "posix", "execution owner uses POSIX file locks")
    def test_process_exit_retains_the_file_fence_through_later_export_finalizers(self):
        directory = Path(tempfile.mkdtemp(prefix="standalone-owner-exit-"))
        self.addCleanup(directory.rmdir)
        for name in ("owner.lock", "receipt"):
            self.addCleanup((directory / name).unlink, missing_ok=True)
        script = textwrap.dedent("""
            import atexit
            from pathlib import Path
            import sys
            from types import SimpleNamespace
            from unittest.mock import patch
            from core.runtime import standalone
            from core.runtime.instance_owner import PosixFileLease, OwnerError
            root = Path(sys.argv[1])
            lease = PosixFileLease(root / "owner.lock")
            class Owner:
                def start(self): lease.acquire()
                def require_owner(self): pass
                def close(self, timeout=2):
                    lease.close()
                    return True
            def compatibility_finalizer():
                contender = PosixFileLease(root / "owner.lock")
                try:
                    contender.acquire()
                except OwnerError as exc:
                    result = "held" if exc.code == "owner_file_busy" else exc.code
                else:
                    result = "released_early"
                    contender.close()
                (root / "receipt").write_text(result)
            # Application exports are imported before the explicit CLI owner.
            atexit.register(compatibility_finalizer)
            bootstrap = SimpleNamespace(mode="combined", instance_id="fixture", runtime_dir=root)
            with patch("core.runtime.instance_owner.ExecutionOwner", return_value=Owner()):
                standalone.require_standalone_owner(
                    bootstrap=bootstrap, schema="fixture", connect_dedicated=lambda: None)
        """)
        result = subprocess.run([sys.executable, "-c", script, str(directory)],
            cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((directory / "receipt").read_text(), "held")


if __name__ == "__main__":
    unittest.main()
