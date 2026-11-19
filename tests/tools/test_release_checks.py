"""Release, health, and database-safety checks for the isolated release tooling."""
from __future__ import annotations

import copy
import ast
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.release import (
    MANIFEST_NAME,
    ReleaseError,
    check_release,
    main as release_main,
    prepare_release,
    rollback_release,
    switch_release,
)
from core.runtime.bootstrap import RuntimeBootstrap
from tools.benchmarks.test_performance import run_benchmark
from tools.test_isolated import TestEnvironmentError as IsolatedEnvironmentError
from tools.test_isolated import parse_conninfo, validate_test_database_url
from webui.routes import health


_RETIRED_ACCOUNT_FILES = (
    "注册任务.json",
    "注册成功的邮箱.json",
    "注册成功的邮箱.txt",
    "注册成功的token.txt",
    "注册成功整行.txt",
    "注册成功账号.json",
    "用于注册的邮箱.json",
    "用于注册的邮箱.txt",
    "用于注册的iCloud隐藏邮箱.json",
)


def _retired_source_references(path: Path, text: str, project_root: Path) -> list[str]:
    """只对显式历史 Profile 补录函数放行其单个只读历史来源。"""
    references = []
    for filename in _RETIRED_ACCOUNT_FILES:
        checked = text
        if path == project_root / 'core/browser/roxy/profile_binding.py' and filename == "注册成功的邮箱.json":
            lines = text.splitlines(keepends=True)
            for node in ast.parse(text).body:
                if isinstance(node, ast.FunctionDef) and node.name == "load_historical_profile_bindings":
                    # 该显式导入经存储 API 写回展示信息，不作为日常账号事实来源。
                    lines[node.lineno - 1:node.end_lineno] = ["\n"] * (node.end_lineno - node.lineno + 1)
            checked = "".join(lines)
        if filename in checked:
            references.append(f"{path}:{filename}")
    return references


def test_runtime_has_no_retired_root_file_io():
    """账号根快照和批次归档都只能作为历史数据，不得重新进入运行时。"""
    project_root = Path(__file__).resolve().parents[2]
    runtime_files = [
        *sorted((project_root / "core").rglob("*.py")),
        *sorted((project_root / "webui").rglob("*.py")),
        project_root / "main.py",
        project_root / "web.py",
        *sorted((project_root / "tools").rglob("*.py")),
    ]
    violations = []
    for path in runtime_files:
        if path.name == "migrate_collections_to_tables.py":
            continue
        text = path.read_text(encoding="utf-8")
        violations.extend(_retired_source_references(path, text, project_root))
    assert violations == [], "retired root-file references: " + ", ".join(violations)


def test_historical_import_exception_does_not_allow_normal_runtime_file_reads():
    root = Path("/fixture")
    path = root / 'core/browser/roxy/profile_binding.py'
    importer = 'def load_historical_profile_bindings():\n    return "注册成功的邮箱.json"\n'
    assert _retired_source_references(path, importer, root) == []
    runtime = '\ndef normal_runtime():\n    return "注册成功的邮箱.json"\n'
    assert _retired_source_references(path, importer + runtime, root) == [f"{path}:注册成功的邮箱.json"]


def _runtime_status() -> dict:
    return {
        "ready": True,
        "started": True,
        "pid": 1234,
        "started_at": 1726310000.5,
        "executor": {"configured_workers": 4},
        "codex_dispatcher": {"started": True, "alive": True, "name": "codex"},
        "dependency_dispatcher": {"started": True, "alive": True, "name": "dependency"},
        "projection_worker": {"started": True, "alive": True, "name": "projection"},
        "bulk_operations": {"started": True, "alive": True, "name": "bulk"},
    }


def test_runtime_status_requires_each_critical_worker():
    baseline = _runtime_status()
    assert health._runtime_check()["ok"] is False

    with patch.object(health.runtime, "runtime_status", return_value=baseline, create=True):
        assert health._runtime_check()["ok"] is True
        for component in ("codex_dispatcher", "dependency_dispatcher", "projection_worker", "bulk_operations"):
            dead = copy.deepcopy(baseline)
            dead[component]["alive"] = False
            with patch.object(health.runtime, "runtime_status", return_value=dead, create=True):
                result = health._runtime_check()
            assert result["ok"] is False
            assert result["workers"][component]["status"] == "not_ready"

            missing = copy.deepcopy(baseline)
            missing.pop(component)
            with patch.object(health.runtime, "runtime_status", return_value=missing, create=True):
                result = health._runtime_check()
            assert result["ok"] is False
            assert result["workers"][component]["status"] == "missing"

            errored = copy.deepcopy(baseline)
            errored[component]["error"] = "worker stopped"
            with patch.object(health.runtime, "runtime_status", return_value=errored, create=True):
                result = health._runtime_check()
            assert result["ok"] is False
            assert result["workers"][component]["status"] == "failed"


def test_runtime_ready_flag_does_not_override_dead_worker_or_executor_error():
    status = _runtime_status()
    status["projection_worker"]["alive"] = False
    with patch.object(health.runtime, "runtime_status", return_value=status, create=True):
        assert health._runtime_check()["ok"] is False

    status = _runtime_status()
    status["executor"] = {"error": "executor unavailable"}
    with patch.object(health.runtime, "runtime_status", return_value=status, create=True):
        result = health._runtime_check()
    assert result["ok"] is False
    assert result["executor"]["status"] == "failed"

    status = _runtime_status()
    status["ready"] = False
    with patch.object(health.runtime, "runtime_status", return_value=status, create=True):
        assert health._runtime_check()["ok"] is False


def test_health_endpoints_are_public_and_readiness_is_strict():
    from webui.app import create_app

    with patch.object(health, "_database_check", return_value={"ok": True, "status": "ok"}), patch.object(
        health.runtime, "runtime_status", return_value=_runtime_status(), create=True
    ):
        app = create_app(auth_code="health-test")
        client = app.test_client()
        assert client.get("/healthz").status_code == 200
        response = client.get("/readyz")
        assert response.status_code == 200
        assert response.get_json()["checks"]["runtime"]["workers"]["projection_worker"]["alive"] is True

    dead = _runtime_status()
    dead["projection_worker"]["alive"] = False
    with patch.object(health, "_database_check", return_value={"ok": True, "status": "ok"}), patch.object(
        health.runtime, "runtime_status", return_value=dead, create=True
    ):
        app = create_app(auth_code="health-test")
        response = app.test_client().get("/readyz")
    assert response.status_code == 503
    assert response.get_json()["ok"] is False


def test_database_guard_uses_decoded_uri_and_query_database_override():
    assert parse_conninfo(
        "postgresql://user:p@127.0.0.1:55432/path?dbname=turb_opt_20260914"
    )["dbname"] == "turb_opt_20260914"
    assert validate_test_database_url(
        "postgresql://user:p@127.0.0.1:55432/path?dbname=turb_opt_20260914"
    ).endswith("/turb_opt_20260914")

    for url in (
        "postgresql://user:p@127.0.0.1:55432/%74urb_console",
        "postgresql://user:p@127.0.0.1:55432/safe?dbname=turb_console",
        "host=127.0.0.1 port=55432 dbname=turb_console user=user password=p",
    ):
        with pytest.raises(IsolatedEnvironmentError):
            validate_test_database_url(url)


def test_performance_check_rejects_production_database(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:p@127.0.0.1:55432/safe?dbname=turb_console",
    )
    with pytest.raises(RuntimeError, match="不安全的测试数据库"):
        run_benchmark()


def _git_source(root: Path) -> Path:
    source = root / "source"
    source.mkdir()
    project_root = Path(__file__).resolve().parents[2]
    for name in ("requirements.in", "requirements-dev.in", "requirements.txt", "requirements-dev.txt", "pyproject.toml"):
        shutil.copy2(project_root / name, source / name)
    (source / "app.py").write_text("print('release')\n", encoding="utf-8")
    (source / ".env").write_text("PRIVATE_TOKEN=not-in-release\n", encoding="utf-8")
    (source / ".env.example").write_text("PUBLIC_EXAMPLE=1\n", encoding="utf-8")
    (source / "logs").mkdir()
    (source / "logs" / "private.log").write_text("private\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=release-test",
            "-c",
            "user.email=release-test@example.invalid",
            "commit",
            "-qm",
            "initial",
        ],
        cwd=source,
        check=True,
    )
    return source


def test_prepare_manifest_and_atomic_switch_are_recoverable(tmp_path):
    source = _git_source(tmp_path)
    releases = tmp_path / "releases"
    first = prepare_release(source, releases, "r1")
    second = prepare_release(source, releases, "r2")

    report = check_release(first, expected_release_id="r1")
    assert report["ok"] is True
    assert (first / ".env.example").is_file()
    assert not (first / ".env").exists()
    assert not (first / "logs").exists()
    assert (first / "release-manifest.json").is_file()

    current = tmp_path / "current"
    state = tmp_path / "state.json"
    switched = switch_release(releases, "r1", current_link=current, state_file=state)
    assert switched["previous_release"] is None
    assert current.resolve() == first.resolve()
    switch_release(releases, "r2", current_link=current, state_file=state)
    assert current.resolve() == second.resolve()
    rolled_back = rollback_release(releases, current_link=current, state_file=state)
    assert rolled_back["release_id"] == "r1"
    assert current.resolve() == first.resolve()

    (first / "app.py").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ReleaseError):
        check_release(first, expected_release_id="r1")


def test_release_keeps_account_modules_without_copying_private_account_data(tmp_path):
    """发布包须能导入账号领域，同时排除同名数据目录及嵌套私有文件。"""
    source = _git_source(tmp_path)
    files = {
        "core/__init__.py": "",
        "core/accounts/__init__.py": "",
        "core/accounts/search.py": "REGISTRATION_DRIVERS = ('roxy',)\n",
        "core/storage/__init__.py": "",
        "core/storage/accounts/__init__.py": "",
        "core/storage/accounts/data.py": "VALUE = 1\n",
        "tests/accounts/test_search.py": "def test_search(): pass\n",
        "tests/accounts/test_search.cjs": "console.log('ok');\n",
        "webui/static/js/pages/accounts/page.js": "const value = 1;\n",
        "frontend/src/features/accounts/AccountsList.vue": "<style src='./accounts.css' />\n",
        "frontend/src/features/accounts/accounts.css": ".accounts { display: block; }\n",
        "frontend/src/features/accounts/actions.ts": "export const action = true;\n",
        "frontend/src/features/accounts/private.json": '{"private": true}\n',
        "frontend/src/features/accounts/logs/private.ts": "export const value = 'private';\n",
        "accounts/private.py": "PRIVATE = True\n",
        "core/accounts/private.json": '{"private": true}\n',
        "core/storage/accounts/private.json": '{"private": true}\n',
        "core/accounts/logs/private.py": "PRIVATE = True\n",
        "core/accounts/.env": "PRIVATE_TOKEN=test-only\n",
        "core/accounts/__pycache__/private.py": "PRIVATE = True\n",
    }
    for relative, content in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    subprocess.run(
        ["git", "-c", "user.name=release-test", "-c", "user.email=release-test@example.invalid",
         "commit", "-qm", "test: 添加账号源码与私有文件样本"],
        cwd=source, check=True,
    )
    release = prepare_release(source, tmp_path / "releases", "account-modules")
    assert check_release(release)["ok"] is True
    assert (release / "tests/accounts/test_search.py").is_file()
    assert (release / "tests/accounts/test_search.cjs").is_file()
    assert (release / "webui/static/js/pages/accounts/page.js").is_file()
    for name in ("AccountsList.vue", "accounts.css", "actions.ts"):
        assert (release / "frontend/src/features/accounts" / name).is_file()
    for relative in files:
        if "private" in relative or relative.endswith(".env"):
            assert not (release / relative).exists()
    result = subprocess.run(
        [sys.executable, "-c",
         "from core.accounts.search import REGISTRATION_DRIVERS; "
         "from core.storage.accounts.data import VALUE; "
         "assert REGISTRATION_DRIVERS == ('roxy',) and VALUE == 1"],
        cwd=release, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def _dashboard_source(source: Path, *, omit: str | None = None) -> dict[str, str]:
    files = {
        "frontend/package.json": '{"name": "dashboard", "private": true}\n',
        "frontend/package-lock.json": '{"name": "dashboard", "lockfileVersion": 3, "packages": {}}\n',
        "frontend/src/dashboard/main.ts": "export const dashboard = 'read-only';\n",
        "frontend/src/dashboard/App.vue": "<template><main>Overview</main></template>\n",
        "frontend/vite.config.ts": "export default {};\n",
        "webui/static/dashboard/dashboard.js": "console.log('dashboard');\n",
        "webui/static/dashboard/dashboard.css": "main { display: block; }\n",
    }
    for relative, content in files.items():
        if relative == omit:
            continue
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return {name: content for name, content in files.items() if name != omit}


def _commit_fixture_paths(source: Path, paths: list[str]) -> None:
    subprocess.run(["git", "add", "--", *paths], cwd=source, check=True)
    subprocess.run(
        ["git", "-c", "user.name=release-test", "-c", "user.email=release-test@example.invalid",
         "commit", "-qm", "test: dashboard release fixture"],
        cwd=source, check=True,
    )


@pytest.mark.parametrize(("selector", "damage"), [
    ("--release-dir", "missing"),
    ("--release-dir", "directory"),
    ("--release-dir", "broken_symlink"),
    ("--root", "directory"),
    ("--root", "broken_symlink"),
])
def test_cli_rejects_invalid_release_manifest(tmp_path, capsys, selector, damage):
    source = _git_source(tmp_path)
    if damage == "directory":
        (source / MANIFEST_NAME).mkdir()
    elif damage == "broken_symlink":
        (source / MANIFEST_NAME).symlink_to(source / "absent.json")
    assert release_main(["check", selector, str(source), "--json"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "缺少 release manifest" in output.err


def test_cli_identifies_source_checkout_and_standalone_release(tmp_path, capsys):
    source = _git_source(tmp_path)
    assert release_main(["check", "--root", str(source), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["source"] == str(source.resolve())
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    release = prepare_release(source, tmp_path / "releases", "standalone")
    assert not (release / ".git").exists()
    assert release_main(["check", "--release-dir", str(release), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["source_commit"] == revision


@pytest.mark.parametrize("recorded", [False, True])
def test_check_nested_manifest_like_any_other_file(tmp_path, recorded):
    source = _git_source(tmp_path)
    relative = Path("docs") / MANIFEST_NAME
    if recorded:
        (source / relative).parent.mkdir()
        (source / relative).write_text("{}\n", encoding="utf-8")
        _commit_fixture_paths(source, [relative.as_posix()])
    release = prepare_release(source, tmp_path / "releases", "nested")
    assert check_release(release)["ok"] is True
    (release / relative).parent.mkdir(exist_ok=True)
    (release / relative).write_text("[]\n", encoding="utf-8")
    with pytest.raises(ReleaseError, match="文件校验失败" if recorded else "文件清单不一致"):
        check_release(release)


def test_release_keeps_dashboard_sources_and_assets_without_frontend_private_files(tmp_path):
    source = _git_source(tmp_path)
    files = _dashboard_source(source)
    private_files = (
        "frontend/node_modules/example/index.js",
        "frontend/.vite/deps/cache.js",
        "frontend/.cache/build.json",
        "frontend/coverage/index.html",
        "frontend/dist/dashboard.js",
        "frontend/test-results/result.json",
        "frontend/playwright-report/index.html",
        "frontend/.npmrc",
        "frontend/.env.local",
        "frontend/vite.config.local.ts",
    )
    for relative in private_files:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("private fixture\n", encoding="utf-8")
    _commit_fixture_paths(source, [*files, *private_files])

    release = prepare_release(source, tmp_path / "releases", "dashboard")

    assert check_release(release)["ok"] is True
    for relative, content in files.items():
        assert (release / relative).read_text(encoding="utf-8") == content
    for relative in private_files:
        assert not (release / relative).exists()
    manifest = json.loads((release / "release-manifest.json").read_text(encoding="utf-8"))
    lock_entry = next(item for item in manifest["files"] if item["path"] == "frontend/package-lock.json")
    assert manifest["locks"]["frontend/package-lock.json"] == lock_entry["sha256"]


@pytest.mark.parametrize("missing", [
    "frontend/package-lock.json",
    "webui/static/dashboard/dashboard.js",
    "webui/static/dashboard/dashboard.css",
])
def test_prepare_dashboard_rejects_missing_lock_or_built_assets(tmp_path, missing):
    source = _git_source(tmp_path)
    files = _dashboard_source(source, omit=missing)
    _commit_fixture_paths(source, list(files))

    with pytest.raises(ReleaseError, match=missing.replace(".", r"\.")):
        prepare_release(source, tmp_path / "releases", "dashboard")


@pytest.mark.parametrize("page", ["proxy", "extractStats", "emailHistory", "bulk"])
@pytest.mark.parametrize("omitted", ["source", "script", "style"])
def test_prepare_rejects_incomplete_optional_page(tmp_path, page, omitted):
    source = _git_source(tmp_path)
    files = _dashboard_source(source)
    paths = {
        "source": f"frontend/src/{page}.ts",
        "script": f"webui/static/{page}/{page}.js",
        "style": f"webui/static/{page}/{page}.css",
    }
    missing = paths.pop(omitted)
    for relative in paths.values():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        files[relative] = "/* page fixture */\n"
        path.write_text(files[relative], encoding="utf-8")
    _commit_fixture_paths(source, list(files))
    with pytest.raises(ReleaseError, match=missing.replace(".", r"\.")):
        prepare_release(source, tmp_path / "releases", page)


@pytest.mark.parametrize(("page", "template_name"), [
    ("proxy", "webui/templates/index.html"),
    ("emailHistory", "webui/templates/index.html"),
    ("extractStats", "webui/templates/partials/extract_stats.html"),
    ("bulk", "webui/templates/index.html"),
])
def test_prepare_rejects_template_pointing_to_absent_bundle(tmp_path, page, template_name):
    source = _git_source(tmp_path)
    files = _dashboard_source(source)
    template = source / template_name
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text(f'<div data-module-url="{page}/{page}.js"></div>\n', encoding="utf-8")
    _commit_fixture_paths(source, [*files, template_name])
    with pytest.raises(ReleaseError, match=f"frontend/src/{page}"):
        prepare_release(source, tmp_path / "releases", "missing-page")


@pytest.mark.parametrize("lock_hash", [None, "0" * 64])
def test_check_dashboard_requires_frontend_lock_manifest_hash(tmp_path, lock_hash):
    source = _git_source(tmp_path)
    _commit_fixture_paths(source, list(_dashboard_source(source)))
    release = prepare_release(source, tmp_path / "releases", "dashboard")
    manifest_path = release / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if lock_hash is None:
        manifest["locks"].pop("frontend/package-lock.json")
    else:
        manifest["locks"]["frontend/package-lock.json"] = lock_hash
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReleaseError, match="lock|依赖锁"):
        check_release(release)


def test_check_pre_dashboard_release_verifies_original_package(tmp_path):
    revision = "59795268e2226015fd97b6f76bbbfc09ed6805b0"
    repo = Path(__file__).resolve().parents[2]
    if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{revision}^{{commit}}"],
                      capture_output=True).returncode:
        pytest.skip("历史发布集成用例需要本地 Git 对象")
    source = tmp_path / "old-source"
    subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout", str(repo), str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "checkout", "--quiet", "--detach", revision], check=True)
    releases = tmp_path / "releases"
    subprocess.run(
        [sys.executable, "-I", "-B", str(source / "tools/release.py"), "prepare",
         "--source", str(source), "--releases-dir", str(releases), "--release-id", "original"],
        check=True, capture_output=True, text=True,
    )
    release = releases / "original"
    assert check_release(release)["source_commit"] == revision
    with pytest.raises(ReleaseError, match="依赖锁"):
        check_release(release, allow_archived_layout=False)

    # A self-consistent replacement file must still be rejected.
    manifest_path = release / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    changed = b"replacement\n"
    (release / "README.md").write_bytes(changed)
    readme = next(item for item in manifest["files"] if item["path"] == "README.md")
    readme.update(size=len(changed), sha256=hashlib.sha256(changed).hexdigest())
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ReleaseError):
        check_release(release)
def test_prepare_release_keeps_frontend_accounts_source_closure(tmp_path):
    """固定 release 需要保留 accounts 页面可重建的 TS/Vue/CSS 源码。"""
    source = _git_source(tmp_path)
    files = {
        "frontend/src/features/accounts/AccountsList.vue": "<style src='./accounts.css' />\n",
        "frontend/src/features/accounts/accounts.css": ".accounts { display: block; }\n",
        "frontend/src/features/accounts/account-actions.ts": "export const action = true;\n",
        "frontend/src/features/accounts/private.json": '{"secret": true}\n',
        "frontend/src/features/accounts/logs/private.ts": "export const privateValue = true;\n",
        "frontend/src/features/accounts/.env": "PRIVATE=1\n",
    }
    for relative, content in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=release-test",
            "-c",
            "user.email=release-test@example.invalid",
            "commit",
            "-qm",
            "test: 保留 accounts 页面源码闭包",
        ],
        cwd=source,
        check=True,
    )

    release = prepare_release(source, tmp_path / "releases", "frontend-accounts")

    assert check_release(release)["ok"] is True
    for relative in (
        "frontend/src/features/accounts/AccountsList.vue",
        "frontend/src/features/accounts/accounts.css",
        "frontend/src/features/accounts/account-actions.ts",
    ):
        assert (release / relative).is_file()
    for relative in (
        "frontend/src/features/accounts/private.json",
        "frontend/src/features/accounts/logs/private.ts",
        "frontend/src/features/accounts/.env",
    ):
        assert not (release / relative).exists()


def test_runtime_bootstrap_uses_validated_release_manifest_without_git(tmp_path, monkeypatch):
    """离开 Git 的真实 release 只能以已校验 manifest 作为运行身份。"""
    source = _git_source(tmp_path)
    release = prepare_release(source, tmp_path / "releases", "manifest-runtime")
    runtime_dir = tmp_path / "runtime"
    expected_release = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    def fail_if_git(*_args, **_kwargs):
        raise AssertionError("固定 release 不应回退调用 Git")

    monkeypatch.setattr("core.runtime.bootstrap.subprocess.run", fail_if_git)
    bootstrap = RuntimeBootstrap.from_environment(
        project_root=release,
        environment={
            "TURB_RUNTIME_MODE": "worker",
            "TURB_INSTANCE_ID": "release-test",
            "TURB_RUNTIME_DIR": str(runtime_dir),
        },
    )

    assert bootstrap.release == expected_release
    assert bootstrap.legacy_paths is False
    assert not runtime_dir.exists()


def test_runtime_bootstrap_fails_closed_on_manifest_without_git_fallback(tmp_path, monkeypatch):
    """损坏的 manifest 不得被祖先 Git 或环境变量伪造身份掩盖。"""
    source = _git_source(tmp_path)
    release = prepare_release(source, tmp_path / "releases", "manifest-broken")
    manifest = release / "release-manifest.json"
    manifest.write_text("{\n  \"source_commit\": \"short\"\n}\n", encoding="utf-8")
    git_called = False

    def fail_if_git(*_args, **_kwargs):
        nonlocal git_called
        git_called = True
        raise AssertionError("损坏的固定 release 不应回退调用 Git")

    monkeypatch.setattr("core.runtime.bootstrap.subprocess.run", fail_if_git)
    with pytest.raises(ValueError, match="runtime_release_manifest_invalid"):
        RuntimeBootstrap.from_environment(
            project_root=release,
            environment={
                "TURB_RUNTIME_MODE": "worker",
                "TURB_RUNTIME_DIR": str(tmp_path / "runtime"),
                "TURB_RELEASE": "a" * 40,
            },
        )
    assert git_called is False


def test_runtime_bootstrap_fails_closed_on_manifest_marker_directory(tmp_path, monkeypatch):
    """manifest 标记路径被占用为目录时也不得退回祖先 Git。"""
    root = tmp_path / "release"
    root.mkdir()
    (root / "release-manifest.json").mkdir()
    git_called = False

    def fail_if_git(*_args, **_kwargs):
        nonlocal git_called
        git_called = True
        raise AssertionError("固定 release 标记异常时不应回退调用 Git")

    monkeypatch.setattr("core.runtime.bootstrap.subprocess.run", fail_if_git)
    with pytest.raises(ValueError, match="runtime_release_manifest_invalid"):
        RuntimeBootstrap.from_environment(
            project_root=root,
            environment={
                "TURB_RUNTIME_MODE": "worker",
                "TURB_RUNTIME_DIR": str(tmp_path / "runtime"),
            },
        )
    assert git_called is False


@pytest.mark.parametrize(
    "damage",
    [
        "bad_json", "wrong_schema", "wrong_release_id", "short_commit",
        "changed_file", "missing_file", "extra_file", "private_file",
        "file_symlink", "broken_manifest_symlink", "wrong_lock",
    ],
)
def test_runtime_bootstrap_rejects_damaged_release_before_git(tmp_path, monkeypatch, damage):
    source = _git_source(tmp_path)
    release = prepare_release(source, tmp_path / "releases", "integrity")
    marker = release / "release-manifest.json"
    if damage in {"wrong_schema", "wrong_release_id", "short_commit", "wrong_lock"}:
        manifest = json.loads(marker.read_text(encoding="utf-8"))
        if damage == "wrong_schema":
            manifest["schema_version"] = 999
        elif damage == "wrong_release_id":
            manifest["release_id"] = "other"
        elif damage == "short_commit":
            manifest["source_commit"] = "a" * 7
        else:
            manifest["locks"]["requirements.txt"] = "a" * 64
        marker.write_text(json.dumps(manifest), encoding="utf-8")
    elif damage == "bad_json":
        marker.write_text("{", encoding="utf-8")
    elif damage == "changed_file":
        (release / "app.py").write_text("changed\n", encoding="utf-8")
    elif damage == "missing_file":
        (release / "app.py").unlink()
    elif damage == "extra_file":
        (release / "extra.py").write_text("EXTRA=True\n", encoding="utf-8")
    elif damage == "private_file":
        (release / ".env").write_text("PRIVATE=synthetic\n", encoding="utf-8")
    elif damage == "file_symlink":
        (release / "app.py").unlink()
        (release / "app.py").symlink_to(source / "app.py")
    elif damage == "broken_manifest_symlink":
        marker.unlink()
        marker.symlink_to(tmp_path / "absent.json")

    def fail_if_git(*_args, **_kwargs):
        raise AssertionError("damaged release must never fall back to Git")

    monkeypatch.setattr("core.runtime.bootstrap.subprocess.run", fail_if_git)
    with pytest.raises(ValueError, match="runtime_release_manifest_invalid"):
        RuntimeBootstrap.from_environment(
            project_root=release,
            environment={"TURB_RUNTIME_MODE": "worker", "TURB_RUNTIME_DIR": str(tmp_path / "runtime")},
        )
    assert not (tmp_path / "runtime").exists()


def test_runtime_bootstrap_accepts_checkout_but_rejects_git_subdirectory(tmp_path):
    source = _git_source(tmp_path)
    bootstrap = RuntimeBootstrap.from_environment(project_root=source, environment={})
    assert len(bootstrap.release) == 40
    nested = source / "nested"
    nested.mkdir()
    with pytest.raises(ValueError, match="runtime_release_unavailable"):
        RuntimeBootstrap.from_environment(project_root=nested, environment={})


def _manifest_only_release_fixture(root: Path, *, nested_manifest=False) -> Path:
    """Pure file fixture: no Git, database or application process."""
    import hashlib

    root.mkdir()
    contents = {
        "app.py": "VALUE = 1\n",
        "requirements.txt": "example-runtime==1.0\n",
        "requirements-dev.txt": "example-development==1.0\n",
    }
    if nested_manifest:
        contents["docs/release-manifest.json"] = '{"document": true}\n'
    entries = []
    for name, content in contents.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        entries.append({"path": name, "size": len(path.read_bytes()),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {
        "schema_version": 1, "release_id": root.name, "source_commit": "a" * 40,
        "python_requires": ">=3.10", "files": entries,
        "locks": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                  for name in ("requirements.txt", "requirements-dev.txt")},
    }
    (root / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


@pytest.mark.parametrize("damage", ["missing", "directory", "broken_symlink"])
def test_release_cli_explicit_release_dir_never_downgrades_to_source_check(
    tmp_path, monkeypatch, capsys, damage,
):
    from tools import release as release_tool

    release = _manifest_only_release_fixture(tmp_path / "explicit")
    marker = release / "release-manifest.json"
    marker.unlink()
    if damage == "directory":
        marker.mkdir()
    elif damage == "broken_symlink":
        marker.symlink_to(tmp_path / "absent-manifest.json")
    monkeypatch.setattr(release_tool, "_validate_project_files", lambda _root: {"source_only": 1})
    assert release_tool.main([
        "check", "--release-dir", str(release), "--release-id", "explicit", "--json",
    ]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "release check failed" in captured.err


@pytest.mark.parametrize("damage", ["directory", "broken_symlink"])
def test_release_cli_root_marker_never_downgrades_to_source_check(
    tmp_path, monkeypatch, capsys, damage,
):
    from tools import release as release_tool

    source = tmp_path / "source"
    source.mkdir()
    marker = source / "release-manifest.json"
    if damage == "directory":
        marker.mkdir()
    else:
        marker.symlink_to(tmp_path / "absent-manifest.json")
    monkeypatch.setattr(release_tool, "_validate_project_files", lambda _root: {"source_only": 1})
    assert release_tool.main(["check", "--root", str(source), "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "release check failed" in captured.err


def test_release_cli_unmarked_source_check_remains_available(tmp_path, monkeypatch, capsys):
    from tools import release as release_tool

    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setattr(release_tool, "_validate_project_files", lambda _root: {"source_only": 1})
    assert release_tool.main(["check", "--root", str(source), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {"ok": True, "source": str(source.resolve()), "locks": {"source_only": 1}}


def test_release_checker_rejects_unrecorded_nested_manifest_name(tmp_path):
    release = _manifest_only_release_fixture(tmp_path / "nested-extra")
    nested = release / "docs" / "release-manifest.json"
    nested.parent.mkdir()
    nested.write_text('{"unrecorded": true}\n', encoding="utf-8")
    with pytest.raises(ReleaseError, match="文件清单不一致"):
        check_release(release, validate_project=False)


def test_release_checker_hashes_recorded_nested_manifest_name(tmp_path):
    release = _manifest_only_release_fixture(tmp_path / "nested-recorded", nested_manifest=True)
    assert check_release(release, validate_project=False)["files"] == 4
    (release / "docs" / "release-manifest.json").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ReleaseError, match="文件校验失败"):
        check_release(release, validate_project=False)
