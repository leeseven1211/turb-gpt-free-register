"""CLI owner rejection precedes proxy, profile and remote-maintenance effects."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def function(relative, name, namespace):
    path = ROOT / relative
    tree = ast.parse(path.read_text())
    selected = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    values = {"__file__": str(path), "Path": Path, "argparse": argparse, **namespace}
    exec(compile(ast.Module(body=[selected], type_ignores=[]), str(path), "exec"), values)
    return values[name]


class CliOwnerGuardTests(unittest.TestCase):
    def test_owner_conflict_never_constructs_a_proxy_or_roxy_diagnostic_run(self):
        for relative, run_class in (
            ("tools/diagnostics/diagnose_protocol_password_interface.py", "ProtocolPasswordRun"),
            ("tools/diagnostics/diagnose_roxy_auth_interface.py", "AuthInterfaceRun"),
        ):
            state = SimpleNamespace(constructed=False)
            failure = RuntimeError("owner_file_busy")

            def reject_owner():
                raise failure

            def construct(_args):
                state.constructed = True
                raise AssertionError("diagnostic run entered without an execution owner")

            owner_module = ModuleType("core.runtime.standalone")
            owner_module.require_standalone_owner = reject_owner
            main = function(relative, "main", {
                "_parse_args": lambda: SimpleNamespace(),
                run_class: construct, "roxy_cfg": SimpleNamespace(),
            })
            with self.subTest(relative=relative), \
                    patch.dict(sys.modules, {"core.runtime.standalone": owner_module}):
                with self.assertRaises(RuntimeError) as caught:
                    main()
                self.assertIs(caught.exception, failure)
                self.assertFalse(state.constructed)

    def test_apply_owner_conflict_precedes_butler_source_reads_and_remote_writes(self):
        for relative in (
            "tools/maintenance/reconcile_butler_service_facts.py",
            "tools/maintenance/reconcile_butler_read_bindings.py",
        ):
            failure = RuntimeError("owner_database_busy")
            cfg = {"DATABASE_URL": "fixture-target", "TURB_DB_SCHEMA": "target_schema"}
            args = SimpleNamespace(source_root=Path("/target"), apply=True)
            state = SimpleNamespace(connected=False, owner_checked=False)

            def require_owner(actual_args, actual_cfg):
                self.assertIs(actual_args, args)
                self.assertIs(actual_cfg, cfg)
                state.owner_checked = True
                raise failure

            def connect(*_args, **_kwargs):
                state.connected = True
                raise AssertionError("maintenance read source before owner rejection")

            run = function(relative, "run", {
                "dotenv_values": lambda *_args, **_kwargs: cfg,
                "require_source_owner": require_owner,
                "psycopg": SimpleNamespace(connect=connect), "dict_row": None,
            })
            with self.subTest(relative=relative):
                with self.assertRaises(RuntimeError) as caught:
                    run(args)
                self.assertIs(caught.exception, failure)
                self.assertTrue(state.owner_checked)
                self.assertFalse(state.connected)

    def test_butler_dry_runs_read_source_without_acquiring_an_execution_owner(self):
        for relative in (
            "tools/maintenance/reconcile_butler_service_facts.py",
            "tools/maintenance/reconcile_butler_read_bindings.py",
        ):
            args = SimpleNamespace(source_root=Path("/target"), apply=False,
                source_instance="target", source_timezone="UTC", receipt=Path("/receipt"))
            cfg = {"DATABASE_URL": "fixture-target", "TURB_DB_SCHEMA": "target_schema"}
            receipts = []

            def forbidden_owner(*_args):
                raise AssertionError("dry run must remain independent of execution ownership")

            run = function(relative, "run", {
                "dotenv_values": lambda *_args, **_kwargs: cfg,
                "require_source_owner": forbidden_owner,
                "psycopg": SimpleNamespace(connect=lambda *_args, **_kwargs: nullcontext(object())),
                "dict_row": None, "datetime": datetime, "timezone": timezone,
                "Counter": Counter, "json": json, "digest": lambda _value: "manifest",
                "collect": lambda *_args: [], "build_items": lambda *_args, **_kwargs: ([], []),
                "collect_bindings": lambda *_args: ([], [], {}),
                "write_receipt": lambda _path, summary: receipts.append(summary),
            })
            with self.subTest(relative=relative):
                result = run(args)
                self.assertEqual(result["mode"], "dry_run")
                self.assertEqual(len(receipts), 1)

    def test_butler_apply_owner_uses_the_source_instance_and_its_stable_directory(self):
        for directory in (None, "/stable/target"):
            cfg = {"DATABASE_URL": "fixture-target", "TURB_DB_SCHEMA": "target_schema",
                   "TURB_INSTANCE_ID": "target"}
            if directory:
                cfg.update(TURB_RUNTIME_MODE="worker", TURB_RUNTIME_DIR=directory)
            observed = []

            def require_owner(**values):
                if values:
                    observed.append(values)
                    values["connect_dedicated"]()

            owner_module = ModuleType("core.runtime.standalone")
            owner_module.require_standalone_owner = require_owner
            connections = []
            require_source_owner = function("tools/maintenance/reconcile_butler_service_facts.py",
                "require_source_owner", {
                    "sys": sys, "ReconcileError": RuntimeError,
                    "psycopg": SimpleNamespace(connect=lambda target, **kwargs:
                        connections.append((target, kwargs))),
                })
            with self.subTest(directory=directory), \
                    patch.dict(sys.modules, {"core.runtime.standalone": owner_module}):
                guard = require_source_owner(SimpleNamespace(source_root=Path("/target")), cfg)
            self.assertIs(guard, require_owner)
            self.assertEqual(observed[0]["schema"], "target_schema")
            self.assertEqual(observed[0]["bootstrap"].instance_id, "target")
            self.assertEqual(observed[0]["bootstrap"].runtime_dir,
                             Path(directory or "/target/logs/run"))
            self.assertEqual(connections[0][0], "fixture-target")
            self.assertTrue(connections[0][1]["autocommit"])
            self.assertEqual(connections[0][1]["connect_timeout"], 5)


if __name__ == "__main__":
    unittest.main()
