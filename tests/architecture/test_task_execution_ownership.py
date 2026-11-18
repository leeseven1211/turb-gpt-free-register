"""任务动作、恢复和存储职责不得重新进入 HTTP 或产生重复状态拥有者。"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_action_and_recovery_services_are_independent_of_http_and_webui():
    for name in (
        "core/operations/action_service.py", "core/operations/reconciliation.py",
        "core/accounts/operation_handlers.py",
    ):
        tree = ast.parse((ROOT / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("webui", "flask", "main")), name
            elif isinstance(node, ast.Import):
                assert all(not alias.name.startswith(("webui", "flask", "main")) for alias in node.names), name


def test_operation_routes_do_not_dispatch_business_actions_or_write_store():
    tree = ast.parse((ROOT / "webui/routes/operations.py").read_text())
    forbidden = {"retry_job", "retry_task", "retry_runtime_task", "request_cancel", "request_run_cancel",
                 "terminate_run", "delete_tasks", "operation_action", "retry_managed_task"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden, node.func.attr


def test_mutable_execution_state_has_one_owner():
    expected = {
        "_RUNTIME_HANDLERS_REGISTERED": "core/accounts/operation_handlers.py",
        "_PROJECTION_WORKER": "core/storage/operations/projection.py",
        "_PROJECTION_WORKER_LOCK": "core/storage/operations/projection.py",
        "_PROJECTION_STOP": "core/storage/operations/projection.py",
        "_PROJECTION_WAKE": "core/storage/operations/projection.py",
    }
    paths = [ROOT / "webui/runtime.py", ROOT / "core/accounts/operation_handlers.py",
             ROOT / "core/operations/reconciliation.py", *(ROOT / "core/storage/operations").glob("*.py")]
    owners = {name: set() for name in expected}
    for path in paths:
        for node in ast.parse(path.read_text()).body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            for target in targets:
                if isinstance(target, ast.Name) and target.id in owners:
                    owners[target.id].add(str(path.relative_to(ROOT)))
    assert owners == {name: {path} for name, path in expected.items()}


def test_reconciliation_does_not_create_threads_or_claim_dependencies():
    tree = ast.parse((ROOT / "core/operations/reconciliation.py").read_text())
    forbidden = {"Thread", "Timer", "ThreadPoolExecutor", "claim_task_dependency", "register_operation_handler"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
            assert name not in forbidden, name
