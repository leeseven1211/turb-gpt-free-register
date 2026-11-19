"""约束新任务中心接缝，防止业务重新进入页面全局状态或 HTTP 查询入口。"""
from __future__ import annotations

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_query_service_has_no_http_or_execution_dependency():
    tree = ast.parse((ROOT / "core/operations/query_service.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("webui", "flask", "main"))
        if isinstance(node, ast.Import):
            assert all(not alias.name.startswith(("webui", "flask", "main")) for alias in node.names)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"retry_job", "request_cancel", "terminate", "submit", "enqueue"}


def test_other_pages_do_not_mutate_task_page_state():
    for path in (ROOT / "webui/static/js/pages").rglob("*.js"):
        if path.parent.name == "operations":
            continue
        source = path.read_text()
        assert not re.search(r"PAGERS\.accountTasks|(?:\$\(|getElementById\()['\"]#?accountTask(?:Type|Target|Status|Batch|RunCount|Stage|Date|Result|Id)", source), path


def test_frontend_features_access_http_only_through_client():
    for folder in ("features", "components"):
        for path in (ROOT / "frontend/src" / folder).rglob("*"):
            if path.suffix not in {".ts", ".vue"} or ".test." in path.name:
                continue
            source = path.read_text()
            assert not re.search(r"\bfetch\s*\(|XMLHttpRequest|window\.(?:ACCOUNTS|PAGERS)|\bACCOUNT_TASKS\b", source), path


def test_only_one_task_center_mount_and_no_retired_task_dom():
    source = (ROOT / "webui/templates/index.html").read_text()
    assert source.count('id="task-center-root"') == 1
    assert 'id="accountTaskLogPanel"' not in source
    assert 'id="accountTasksBody"' not in source
