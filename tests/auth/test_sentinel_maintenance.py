"""Offline WebUI maintenance checks use a separate candidate cache only."""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import threading
import time
import os
from pathlib import Path

import pytest

from core.auth.protocol.sentinel_assets import SentinelAssetManager
from core.storage import postgres
from tests.support_pg import database_available, drop_schema, temporary_schema_name


@pytest.fixture(autouse=True)
def isolated_maintenance_database(monkeypatch):
    """维护队列使用独立 schema，候选下载与子进程均为离线替身。"""
    if not database_available():
        pytest.skip("需要本机 PostgreSQL 测试库")
    previous = os.environ.get("TURB_DB_SCHEMA")
    schema = temporary_schema_name("sentinel_maintenance")
    monkeypatch.setenv("TURB_DB_SCHEMA", schema)
    postgres.reset_cache()
    postgres.ensure_schema()
    from core.storage import records
    from core import account_task_store
    from core.storage.operations import permits, store

    records.reset_ready()
    records.init()
    account_task_store.init()
    store.init()
    permits.ensure_tables()
    # 后续测试会替换 subprocess.Popen；先固定真实 owner 身份，避免把 ps 核验
    # 也误送进下载用的子进程替身。
    permits.current_owner()
    try:
        yield
    finally:
        from core.maintenance import sentinel

        for instance in sentinel._SERVICE_INSTANCES.values():
            for thread in instance._worker_threads:
                thread.join(timeout=10)
                assert not thread.is_alive(), "维护测试必须等待真实 worker 收口后才能删除隔离 schema"
            if instance._pending_lease is not None:
                instance._pending_lease.close()
                instance._pending_lease = None
        sentinel._SERVICE_INSTANCES.clear()
        drop_schema(schema)
        if previous is None:
            os.environ.pop("TURB_DB_SCHEMA", None)
        else:
            os.environ["TURB_DB_SCHEMA"] = previous
        postgres.reset_cache()


VERSION = "20260810913b"
SDK = b"var SentinelSDK=function(t){var E=new O;t.init=init,t.token=je,t}({});"
URL = f"https://sentinel.openai.com/sentinel/{VERSION}/sdk.js"
LOADER = f'var src="{URL}";'.encode()


class Response(io.BytesIO):
    status = 200
    headers = {"Content-Type": "application/javascript"}

    def geturl(self):
        return None


class Opener:
    def __init__(self, replies=()):
        self.replies = list(replies)

    def open(self, request, timeout):
        if not self.replies:
            raise AssertionError("Unexpected network access")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return Response(reply)


class DeferredExecutor:
    def __init__(self):
        self.callbacks = []

    def __call__(self, callback):
        self.callbacks.append(callback)

    def finish(self):
        self.callbacks.pop(0)()


def service(cache, *, replies=(), builtin=SDK, version=VERSION, executor=None, clock=None):
    from core.maintenance.sentinel import SentinelMaintenanceService

    path = cache.parent / "builtin.js"
    path.write_bytes(builtin)
    assets = SentinelAssetManager(cache, opener=Opener(replies))
    return SentinelMaintenanceService(
        manager=assets, builtin_path=path, builtin_version=version,
        executor=executor or DeferredExecutor(), clock=clock or (lambda: 1700000000.0),
    )


def test_missing_cache_status_reads_only_local_builtin_without_creating_cache(tmp_path):
    cache = tmp_path / "candidates"
    summary = service(cache).status()
    assert summary == {
        "ok": True, "running": False, "last_checked_at": None, "last_status": "never",
        "error_code": None, "builtin": {"version": VERSION, "sha256": hashlib.sha256(SDK).hexdigest()},
        "candidate": None, "comparison": "not_checked",
    }
    assert not cache.exists()


def test_double_click_starts_only_one_deferred_refresh_and_publishes_safe_metadata(tmp_path):
    executor = DeferredExecutor()
    maintenance = service(tmp_path / "cache", replies=[LOADER, SDK], executor=executor)
    accepted = maintenance.start_check()
    duplicate = maintenance.start_check()
    assert accepted["started"] is True and accepted["running"] is True
    assert duplicate["started"] is False and duplicate["running"] is True
    executor.finish()
    result = maintenance.status()
    assert result["running"] is False
    assert result["last_status"] == "refreshed"
    assert result["last_checked_at"] == 1700000000.0
    assert result["comparison"] == "same"
    assert result["candidate"] == {
        "version": VERSION, "sha256": hashlib.sha256(SDK).hexdigest(),
        "fetched_at": result["candidate"]["fetched_at"],
        "generic_status": "static_markers_present", "proto2_status": "static_markers_present",
        "runtime_verified": False,
    }
    assert not executor.callbacks
    serialized = json.dumps(result)
    assert str(tmp_path) not in serialized and "sdk_url" not in serialized and "loader_sha256" not in serialized


@pytest.mark.parametrize(("version", "builtin", "expected"), [
    ("different", SDK, "version_changed"),
    (VERSION, SDK + b"// different", "content_changed"),
])
def test_candidate_comparison_distinguishes_version_and_content_changes(tmp_path, version, builtin, expected):
    executor = DeferredExecutor()
    maintenance = service(tmp_path / "cache", replies=[LOADER, SDK], executor=executor, builtin=builtin, version=version)
    maintenance.start_check()
    executor.finish()
    assert maintenance.status()["comparison"] == expected


def test_failed_refresh_keeps_candidate_and_persists_failure_across_service_restart(tmp_path):
    executor = DeferredExecutor()
    cache = tmp_path / "cache"
    maintenance = service(cache, replies=[LOADER, SDK, OSError("private-token https://secret.test")], executor=executor)
    maintenance.start_check()
    executor.finish()
    good = maintenance.status()["candidate"]
    maintenance.start_check()
    executor.finish()
    restored = service(cache).status()
    assert restored["last_status"] == "failed"
    assert restored["last_checked_at"] == 1700000000.0
    assert restored["error_code"] == "fetch_or_cache_failed"
    assert restored["candidate"] == good
    assert "private-token" not in json.dumps(restored)


def test_success_metadata_and_time_are_restored_without_network(tmp_path):
    executor = DeferredExecutor()
    cache = tmp_path / "cache"
    maintenance = service(cache, replies=[LOADER, SDK], executor=executor)
    maintenance.start_check()
    executor.finish()
    assert service(cache).status()["last_status"] == "refreshed"
    assert service(cache).status()["comparison"] == "same"


def test_get_status_never_waits_for_a_refresh_holding_the_asset_cache_lock(tmp_path):
    started, release, done = threading.Event(), threading.Event(), threading.Event()
    cache = tmp_path / "cache"
    maintenance = service(cache)

    class BlockingOpener(Opener):
        def open(self, request, timeout):
            started.set()
            assert release.wait(3)
            return super().open(request, timeout)

    maintenance.manager.opener = BlockingOpener([LOADER, SDK])

    def executor(callback):
        def run():
            try:
                callback()
            finally:
                done.set()
        threading.Thread(target=run, daemon=True).start()

    maintenance.executor = executor
    maintenance.start_check()
    assert started.wait(1)
    try:
        before = time.monotonic()
        result = maintenance.status()
        assert time.monotonic() - before < 0.25
        assert result["running"] is True
        assert not release.is_set()
    finally:
        release.set()
        assert done.wait(3)
    assert maintenance.status()["last_status"] == "refreshed"


def test_idle_reader_also_does_not_wait_for_an_external_manager_lock(tmp_path):
    import fcntl

    cache = tmp_path / "cache"
    cache.mkdir()
    maintenance = service(cache)
    with (cache / ".lock").open("wb") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        before = time.monotonic()
        assert maintenance.status()["last_status"] == "never"
        assert time.monotonic() - before < 0.25


def test_corrupt_metadata_and_raw_failure_are_not_returned(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / ".lock").touch()
    (cache / "index.json").write_text('{"schema": 1, "latest": "../../secret"}')
    (cache / "last_check.json").write_text(json.dumps({
        "status": "secret-status", "reason": "private-token/secret", "checked_at": 1700000000,
    }))
    result = service(cache).status()
    assert result["candidate"] is None
    assert result["error_code"] == "corrupt_cache"
    assert result["last_status"] == "corrupt"
    assert "private-token" not in json.dumps(result)


def test_default_executor_runs_a_daemon_and_recovers_after_unexpected_failure(tmp_path):
    from core.maintenance.sentinel import SentinelMaintenanceService

    cache = tmp_path / "cache"
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    worker_daemon = []

    class BrokenManager(SentinelAssetManager):
        def check(self, *, refresh=False):
            worker_daemon.append(threading.current_thread().daemon)
            entered.set()
            assert release.wait(3)
            completed.set()
            raise RuntimeError("private-token")

    builtin = tmp_path / "builtin.js"
    builtin.write_bytes(SDK)
    maintenance = SentinelMaintenanceService(manager=BrokenManager(cache), builtin_path=builtin, builtin_version=VERSION)
    assert maintenance.start_check()["started"] is True
    assert entered.wait(1)
    assert maintenance.start_check()["started"] is False
    release.set()
    assert completed.wait(1)
    # Joining only the test-owned worker would require exposing implementation;
    # the public status converges through a bounded Event-backed wait instead.
    for _ in range(100):
        result = maintenance.status()
        if not result["running"]:
            break
        threading.Event().wait(0.005)
    assert result["last_status"] == "failed"
    assert result["error_code"] == "check_failed"
    assert worker_daemon == [True]
    assert "private-token" not in json.dumps(result)


def test_executor_start_failure_keeps_the_durable_check_queued(tmp_path):
    def broken_executor(callback):
        raise RuntimeError("private-token")

    maintenance = service(tmp_path / "cache", executor=broken_executor)
    result = maintenance.start_check()
    assert result["running"] is True
    assert result["started"] is True
    assert result["status"] == "queued"
    assert result["blocked_by"] == ["executor_submit_failed"]
    assert "private-token" not in json.dumps(result)


def test_separate_service_instances_share_a_nonblocking_check_lease(tmp_path):
    first_executor, second_executor = DeferredExecutor(), DeferredExecutor()
    cache = tmp_path / "cache"
    first = service(cache, replies=[LOADER, SDK], executor=first_executor)
    second = service(cache, executor=second_executor)
    assert first.start_check()["started"] is True
    try:
        assert second.start_check()["started"] is False
        assert second.status()["running"] is True
        assert not second_executor.callbacks
    finally:
        first_executor.finish()
    assert second.status()["running"] is False
    assert second.status()["last_status"] == "refreshed"


def test_worker_start_failure_does_not_wait_for_the_asset_download_lock(tmp_path):
    import fcntl

    def broken_executor(callback):
        raise RuntimeError("private-token")

    cache = tmp_path / "cache"
    cache.mkdir()
    maintenance = service(cache, executor=broken_executor)
    maintenance.manager.timeout_seconds = 0.4
    with (cache / ".lock").open("wb") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        before = time.monotonic()
        result = maintenance.start_check()
        assert time.monotonic() - before < 0.25
    assert result["status"] == "queued"
    assert result["blocked_by"] == ["executor_submit_failed"]


def _wait_until_check_finishes(maintenance, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = maintenance.status()
        if not result["running"]:
            return result
        threading.Event().wait(0.005)
    return maintenance.status()


def test_default_download_process_timeout_reaps_hung_child_preserves_candidate_and_allows_retry(tmp_path, monkeypatch):
    import fcntl
    from core.maintenance import sentinel

    cache = tmp_path / "run" / "sentinel-candidates"
    previous = SentinelAssetManager(cache, opener=Opener([LOADER, SDK])).check(refresh=True).artifact
    path = tmp_path / "builtin.js"
    path.write_bytes(SDK)
    parent_entered, parent_release = threading.Event(), threading.Event()

    class HungResolver(Opener):
        def open(self, request, timeout):
            # Reproduce a DNS resolver that does not honor urllib's timeout.
            parent_entered.set()
            parent_release.wait(3)
            raise OSError("private resolver failure")

    real_popen = subprocess.Popen
    children = []
    child_started = cache / "child-started"
    hang_script = (
        "import fcntl,time\n"
        f"handle=open({str(cache / '.lock')!r}, 'a+b')\n"
        "fcntl.flock(handle, fcntl.LOCK_EX)\n"
        f"open({str(child_started)!r}, 'w').write('started')\n"
        "time.sleep(60)\n"
    )
    repo = Path(__file__).resolve().parents[2]
    success_script = (
        "import sys,json\n"
        f"sys.path.insert(0, {str(repo)!r})\n"
        "from tests.auth.test_sentinel_maintenance import SentinelAssetManager,Opener,LOADER,SDK\n"
        f"result=SentinelAssetManager({str(cache)!r}, opener=Opener([LOADER,SDK])).check(refresh=True)\n"
        "print(json.dumps(result.to_dict()))\n"
    )

    def offline_popen(command, **kwargs):
        script = hang_script if not children else success_script
        child = real_popen([sys.executable, "-c", script], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(sentinel, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sentinel, "_PROCESS_TIMEOUT_SECONDS", 0.5)
    monkeypatch.setattr(sentinel, "SentinelAssetManager", lambda cache: SentinelAssetManager(cache, opener=HungResolver(), timeout_seconds=0.1))
    monkeypatch.setattr(subprocess, "Popen", offline_popen)
    maintenance = sentinel.SentinelMaintenanceService(builtin_path=path, builtin_version=VERSION)
    try:
        before = time.monotonic()
        assert maintenance.start_check()["started"] is True
        assert time.monotonic() - before < 0.25
        result = _wait_until_check_finishes(maintenance, timeout=1.5)
        assert result["running"] is False
        assert result["last_status"] == "failed"
        assert result["error_code"] == "download_timeout"
        assert result["candidate"]["sha256"] == previous.sha256
        assert children[0].poll() is not None
        assert child_started.exists()
        assert not parent_entered.is_set()
        with (cache / ".lock").open("rb") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        restored = sentinel.SentinelMaintenanceService(builtin_path=path, builtin_version=VERSION).status()
        assert restored["error_code"] == "download_timeout"
        # 首轮短期限只验证挂死进程会被杀死并回收。正常重试会重新启动 Python
        # 和测试依赖，不要求其在同一 0.5 秒内完成；保持独立的有界等待。
        monkeypatch.setattr(sentinel, "_PROCESS_TIMEOUT_SECONDS", 5)
        assert maintenance.start_check()["started"] is True
        retried = _wait_until_check_finishes(maintenance, timeout=7)
        assert retried["last_status"] == "refreshed"
        assert retried["error_code"] is None
        assert retried["candidate"]["sha256"] == previous.sha256
        assert len(children) == 2 and all(child.poll() is not None for child in children)
    finally:
        parent_release.set()
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)


@pytest.mark.parametrize(("payload", "expected"), [
    ({"status": "refreshed", "artifact": {"version": "private-version", "path": "/private/path"}}, "corrupt_cache"),
    ({"status": "failed", "reason": "private-remote-error"}, "check_failed"),
])
def test_default_process_does_not_trust_child_artifact_metadata_or_raw_error(tmp_path, monkeypatch, payload, expected):
    from core.maintenance import sentinel

    real_popen = subprocess.Popen
    children = []

    def offline_popen(command, **kwargs):
        script = f"print({json.dumps(payload)!r})"
        child = real_popen([sys.executable, "-c", script], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(sentinel, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sentinel, "SentinelAssetManager", lambda cache: SentinelAssetManager(cache, opener=Opener()))
    monkeypatch.setattr(subprocess, "Popen", offline_popen)
    builtin = tmp_path / "builtin.js"
    builtin.write_bytes(SDK)
    maintenance = sentinel.SentinelMaintenanceService(builtin_path=builtin, builtin_version=VERSION)
    maintenance.start_check()
    result = _wait_until_check_finishes(maintenance)
    assert result["last_status"] == "failed"
    assert result["error_code"] == expected
    assert result["candidate"] is None
    assert "private-" not in json.dumps(result) and "/private/path" not in json.dumps(result)
    assert len(children) == 1 and children[0].poll() is not None


def test_default_process_is_killed_and_reaped_when_reading_its_output_fails(tmp_path, monkeypatch):
    from core.maintenance import sentinel

    real_popen = subprocess.Popen
    children = []

    def broken_pipe_popen(command, **kwargs):
        child = real_popen([sys.executable, "-c", "import time;time.sleep(0.5)"], **kwargs)
        communicate = child.communicate
        attempts = []

        def read_output(*args, **kwargs):
            if not attempts:
                attempts.append(True)
                raise OSError("private-pipe-failure")
            return communicate(*args, **kwargs)

        child.communicate = read_output
        children.append(child)
        return child

    monkeypatch.setattr(sentinel, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sentinel, "SentinelAssetManager", lambda cache: SentinelAssetManager(cache, opener=Opener()))
    monkeypatch.setattr(subprocess, "Popen", broken_pipe_popen)
    builtin = tmp_path / "builtin.js"
    builtin.write_bytes(SDK)
    executor = DeferredExecutor()
    maintenance = sentinel.SentinelMaintenanceService(builtin_path=builtin, builtin_version=VERSION, executor=executor)
    maintenance.start_check()
    before = time.monotonic()
    executor.finish()
    assert time.monotonic() - before < 0.25
    assert len(children) == 1 and children[0].poll() < 0
    result = maintenance.status()
    assert result["running"] is False and result["error_code"] == "check_failed"
    assert "private-pipe-failure" not in json.dumps(result)
