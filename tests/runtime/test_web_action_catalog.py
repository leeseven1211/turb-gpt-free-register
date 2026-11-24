"""Fresh-process Web action registration; no database, network or worker starts."""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_TYPES = {
    "account_setup_retry", "password_setup", "password_change", "twofa_setup",
    "twofa_change", "account_completion", "registration_resume",
}
NATIVE_TYPES = {
    "live_check", "token_refresh", "plan_check", "deactivation_mail", "extract_link",
    "email_change", "account_inspection", "account_inspection_batch", "codex_retry",
    "codex_token_refresh", "sentinel_maintenance_check", "sub2api_scan",
    "sub2api_sync", "sub2api_manual_upload", "c2a_session_reimport", "c2a_scan",
}


def probe():
    """Run in a new interpreter so earlier tests cannot prefill the registries."""
    from types import SimpleNamespace
    import socket
    import threading

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Web registration attempted execution or external I/O")

    with ExitStack() as stack:
        directory = Path(tempfile.mkdtemp(prefix="turb-web-actions-"))
        stack.callback(directory.rmdir)
        stack.enter_context(patch.object(threading.Thread, "start", forbidden))
        stack.enter_context(patch.object(socket.socket, "connect", forbidden))
        stack.enter_context(patch.object(socket, "create_connection", forbidden))
        from core.storage import postgres
        stack.enter_context(patch.object(postgres, "connect", forbidden))
        stack.enter_context(patch.object(postgres, "connect_dedicated", forbidden))
        from core.operations import task_gateway
        # A Web import must not incidentally install any execution handler.
        with patch.object(task_gateway, "register_operation_handler", forbidden), \
                patch.object(task_gateway, "register_dispatch_handler", forbidden):
            from core.runtime.assembly import install
            from core.runtime.bootstrap import RuntimeBootstrap
            # Match web.py: application imports precede runtime installation.
            from webui.app import create_app
            runtime = install(RuntimeBootstrap("web", "action-fixture", Path(directory), "a" * 40))
            runtime.controller.start()
            assert callable(task_gateway.operation_action(
                "sub2api_scan", "cancel", source_system="native_operations",
            )), "fresh Web cannot cancel an existing Sub2API scan"
            app = create_app(auth_code="test-web-actions")

        assert not runtime.controller.context.executes
        assert runtime.owner is None
        assert not task_gateway.registered_dispatch_types()
        assert not task_gateway.registered_operation_types()
        from core.operations.bulk_mutation_worker import registered_bulk_mutation_operations
        assert not registered_bulk_mutation_operations(), "Web installed executable bulk callbacks"
        for task_type in sorted(RUNTIME_TYPES | NATIVE_TYPES):
            source = "webui_runtime" if task_type in RUNTIME_TYPES else "native_operations"
            for action in ("retry", "cancel", "terminate"):
                assert callable(task_gateway.operation_action(task_type, action, source_system=source)), \
                    f"missing Web action: {task_type}/{action}"
                assert task_gateway.operation_action(task_type, action, source_system="legacy_fixture") is None

        from core.accounts import operation_handlers
        from core.accounts.liveness import service as live
        from core.accounts.plans import service as plans
        from core.accounts.inspection import service as inspection
        from core.operations import action_service
        from core.maintenance import sentinel
        expected = {
            ("password_setup", "retry"): action_service.retry_runtime_task,
            ("account_completion", "cancel"): action_service.cancel_runtime_task,
            ("live_check", "retry"): live._retry_live_check_operation,
            ("token_refresh", "retry"): live._retry_token_refresh_operation,
            ("plan_check", "retry"): plans._retry_plan_operation,
            ("account_inspection", "cancel"): inspection._cancel_item,
            ("account_inspection_batch", "retry"): inspection._retry_parent,
            ("sentinel_maintenance_check", "retry"): sentinel._retry_check,
            ("sentinel_maintenance_check", "cancel"): sentinel._cancel_check,
        }
        for (kind, action), handler in expected.items():
            assert task_gateway.operation_action(kind, action) is handler, (kind, action)

        # Existing task receipts are read at the storage boundary. No submit
        # entrypoint runs first; this is the reported restart regression.
        from core import operation_task_store
        from core.bulk_operations import execution as bulk_execution
        from core.bulk_operations import service as bulk_service
        writes = []
        durable = SimpleNamespace(
            retry_runtime_task=lambda task_id, **kwargs: writes.append(("retry", task_id)) or {"id": 102},
            request_run_cancel=lambda run_id, **kwargs: writes.append(("cancel", run_id)) or {"id": run_id, "status": "cancelled"},
            terminate_run=lambda run_id, **kwargs: writes.append(("terminate", run_id)) or {"id": run_id, "status": "stopped"},
        )
        stack.enter_context(patch.object(task_gateway, "_operation", return_value=durable))
        stack.enter_context(patch.object(task_gateway, "operation_is_deactivated", return_value=False))
        stack.enter_context(patch.object(bulk_service, "retry_managed_task", return_value=None))
        stack.enter_context(patch.object(bulk_execution, "retry_managed", return_value=None))
        client = app.test_client()
        for kind in ("sub2api_scan", "sub2api_sync", "sub2api_manual_upload",
                     "c2a_session_reimport", "c2a_scan", "codex_token_refresh"):
            for action, status in (("retry", "failed"), ("cancel", "queued"), ("terminate", "running")):
                task = {"id": 101, "task_type": kind, "source_system": "native_operations",
                        "status": status, "runs": [{"id": 101, "status": status}]}
                with patch.object(operation_task_store, "get_task", return_value=task):
                    response = client.post(f"/api/operations/101/{action}", headers={"X-Auth-Code": "test-web-actions"})
                assert response.status_code == (202 if action == "retry" else 200), \
                    (kind, action, response.status_code, response.get_json())
                assert response.get_json()["ok"] is True
        assert len(writes) == 18, writes
        assert not task_gateway.registered_dispatch_types()
        assert not task_gateway.registered_operation_types()

        # Codex retains its account-state and local-cancellation bookkeeping.
        from core.codex import operation_service as codex
        task = {"id": 201, "runs": [{"id": 202, "status": "queued"}], "_expected_run_status": "queued"}
        with patch.object(codex, "retry_task", return_value={"accepted": True}) as retry, \
                patch.object(codex, "request_cancel", return_value={"ok": True}) as cancel, \
                patch.object(codex, "terminate", return_value={"ok": True}) as terminate:
            for action in ("retry", "cancel", "terminate"):
                task_gateway.operation_action("codex_retry", action)(task)
            retry.assert_called_once_with(201, trigger="manual_retry")
            cancel.assert_called_once_with(run_id=202, expected_status="queued")
            terminate.assert_called_once_with(run_id=202)

        # Worker handler installation must reuse the same specialized actions.
        from core.runtime.bindings import build_components
        from core.runtime.context import RuntimeContext
        from core.runtime.manifest import COMPONENTS, REQUIRED_DISPATCH_TYPES
        before = {key: task_gateway.operation_action(*key) for key in expected}
        hooks = build_components()
        for spec in COMPONENTS:
            if spec.kind == "handlers":
                hooks[spec.name].start(RuntimeContext("worker"))
        assert REQUIRED_DISPATCH_TYPES <= set(task_gateway.registered_dispatch_types())
        for key, handler in before.items():
            assert task_gateway.operation_action(*key) is handler, key
        assert operation_handlers.RUNTIME_HANDLER_TYPES <= set(task_gateway.registered_operation_types())
        print(json.dumps({"ok": True, "task_types": len(RUNTIME_TYPES | NATIVE_TYPES),
                          "route_actions": len(writes), "worker_catalog": True}))


class WebActionCatalogTests(unittest.TestCase):
    def test_fresh_web_controls_existing_tasks_without_execution_registration(self):
        env = {key: value for key, value in os.environ.items()
               if key in {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT"}}
        env.update(PYTHON_DOTENV_DISABLED="1", DATABASE_URL="", TURB_DB_SCHEMA="test_web_actions",
                   TURB_RUNTIME_MODE="web", TURB_ALLOW_PRODUCTION_DB="0", PYTHONPATH=str(ROOT))
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--probe"],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(result, {"ok": True, "task_types": 23, "route_actions": 18, "worker_catalog": True})


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        unittest.main()
