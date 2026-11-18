"""账号执行不依赖 WebUI 装配，也不拥有第二套线程池或 handler 注册表。"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXECUTION_MODULES = (
    "operation_results", "setup_execution", "completion_execution", "completion_dependencies",
)


def test_account_execution_has_no_web_entrypoint_dependency():
    for module in EXECUTION_MODULES:
        path = ROOT / "core/accounts" / f"{module}.py"
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("webui", "flask", "main")), path
            elif isinstance(node, ast.Import):
                assert all(not alias.name.startswith(("webui", "flask", "main")) for alias in node.names), path


def test_account_execution_does_not_create_scheduler_or_register_handlers():
    forbidden_calls = {
        "ThreadPoolExecutor", "Thread", "Timer", "register_operation_handler",
        "set_dependency_ready_handler", "claim_task_dependency",
    }
    for module in EXECUTION_MODULES:
        path = ROOT / "core/accounts" / f"{module}.py"
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
            assert name not in forbidden_calls, (path, name)
