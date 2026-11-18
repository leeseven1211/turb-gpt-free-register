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


_MAINTENANCE_NATIVE_OWNER = None
_RETAINED_MAINTENANCE_NATIVE_OWNERS = {}


class _MaintenanceNativeOwner:
    """Keep every pytest patch and schema until the original native actors close."""

    def __init__(self, monkeypatch, *, schema, previous_schema, tmp_path, tmp_path_factory):
        from tests.support_settlement import NativeSettlementFixture

        self.native = NativeSettlementFixture(timeout=10)
        self.monkeypatch = monkeypatch
        self.original_undo = monkeypatch.undo
        self.schema = schema
        self.previous_schema = previous_schema
        self.tmp_path = tmp_path
        self.tmp_path_factory = tmp_path_factory
        self.previous_retention_policy = tmp_path_factory._retention_policy
        # pytest owns tmp_path's finalizer outside monkeypatch. Preserve the
        # original cache/log directory if native teardown aborts after the call.
        tmp_path_factory._retention_policy = "all"
        self.closed = False
        # Direct assignment deliberately stays outside the undo journal. The
        # pytest monkeypatch finalizer must use this same gate for body patches.
        monkeypatch.undo = self.close
        _RETAINED_MAINTENANCE_NATIVE_OWNERS[id(self)] = self

    def close(self):
        global _MAINTENANCE_NATIVE_OWNER
        from tests.support_settlement import NativeSettlementAbort

        if self.closed:
            return
        failures = []
        try:
            deadline = time.monotonic() + self.native.timeout
            while True:
                workers = tuple(_WORKERS)
                for consumer, thread in workers:
                    thread.join(timeout=max(0.0, deadline - time.monotonic()))
                    assert not thread.is_alive(), "maintenance Worker still owns original dependencies"
                if tuple(_WORKERS) == workers:
                    break
                assert time.monotonic() < deadline, "maintenance Worker cohort did not stop"
            failures = [failure for consumer, _thread in workers for failure in consumer.failures]
            # This also runs if start() raised: dependencies cannot unwind while
            # a partially started carrier or an original execution remains.
            self.native.close()
            _WORKERS.clear()
            drop_schema(self.schema)
            if self.previous_schema is None:
                os.environ.pop("TURB_DB_SCHEMA", None)
            else:
                os.environ["TURB_DB_SCHEMA"] = self.previous_schema
            postgres.reset_cache()
            self.original_undo()
            self.tmp_path_factory._retention_policy = self.previous_retention_policy
        except BaseException as error:
            _RETAINED_MAINTENANCE_NATIVE_OWNERS[id(self)] = self
            raise NativeSettlementAbort("maintenance native dependencies retained; teardown refused") from error
        self.closed = True
        _RETAINED_MAINTENANCE_NATIVE_OWNERS.pop(id(self))
        _MAINTENANCE_NATIVE_OWNER = None
        assert not failures, failures


@pytest.fixture(autouse=True)
def isolated_maintenance_database(monkeypatch, tmp_path, tmp_path_factory):
    """维护队列与真实结算载体共用原 schema；下载与子进程保持离线替身。"""
    global _MAINTENANCE_NATIVE_OWNER
    from tests.support_settlement import NativeSettlementAbort

    if _MAINTENANCE_NATIVE_OWNER is not None or _RETAINED_MAINTENANCE_NATIVE_OWNERS:
        raise NativeSettlementAbort("previous maintenance native owner remains; new schema refused")
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
    from core.maintenance import sentinel
    from core.operations import task_gateway, run_log

    # This test process has an explicit worker consumer, never a background
    # dispatcher or a Web-owned callback. Preserve global handlers across tests.
    for name in ("_DISPATCH_HANDLERS", "_DISPATCH_CAPACITY_HANDLERS", "_OPERATION_HANDLERS",
                 "_OPERATION_HANDLER_ALLOWLISTS", "_OPERATION_ACTIONS", "_OPERATION_ACTION_SOURCES"):
        monkeypatch.setattr(task_gateway, name, {})
    monkeypatch.setattr(sentinel, "_SERVICE_INSTANCES", {})
    monkeypatch.setattr(sentinel, "_CACHE_DIRECTORY", None)
    monkeypatch.setattr(run_log, "_LOG_ROOT", tmp_path / "logs")
    monkeypatch.setattr(run_log, "_TASK_LOG_ROOT", tmp_path / "logs" / "tasks")
    _WORKERS.clear()
    owner = _MaintenanceNativeOwner(monkeypatch, schema=schema, previous_schema=previous,
                                    tmp_path=tmp_path, tmp_path_factory=tmp_path_factory)
    _MAINTENANCE_NATIVE_OWNER = owner
    try:
        owner.native.start()
        yield
    finally:
        owner.close()


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


_WORKERS = []


class WorkerConsumer:
    """Explicitly consume the persisted Run through the production gateway.

    start_check() cannot call this helper. Tests choose when a Worker becomes
    available, and the real gateway owns claim, permit, handler and settlement.
    """
    def __init__(self, maintenance=None):
        self.maintenance = maintenance
        self.results = []
        self.failures = []
        self.execution = None

    def finish(self, *, wait_for_release=True):
        from core.maintenance import sentinel
        from core.operations import task_gateway
        from core.storage.operations import sentinel_checks, store

        assert self.maintenance is not None
        active = sentinel_checks.active_check(sentinel._cache_key(self.maintenance))
        assert active is not None, "Worker must consume an accepted durable Run"
        sentinel.register_handler()
        owner = _MAINTENANCE_NATIVE_OWNER
        assert owner is not None and not owner.closed
        fixture = owner.native
        with fixture._condition:
            prior_contexts = set(fixture.contexts)
        # The owner retains this patch even if execution or its exact wait
        # raises; only proven native closure may restore get_service.
        owner.monkeypatch.setattr(sentinel, "get_service", lambda: self.maintenance)
        result = task_gateway._execute_operation_handler(sentinel._TASK_TYPE, active["run_id"])
        with fixture._condition:
            admitted = [execution for key, execution in fixture.contexts.items()
                        if key not in prior_contexts
                        and int(execution.claimed_run["id"]) == int(active["run_id"])]
        assert len(admitted) == 1, "Worker must own exactly one new original admission"
        self.execution = admitted[0]
        if wait_for_release:
            fixture.wait_for_execution_released(self.execution)
        self.results.append(result)
        terminal = store.get_run(active["run_id"])
        assert terminal["status"] in {"success", "failed", "cancelled"}, (result, terminal)
        assert not (terminal.get("result_summary") or {}).get("running"), terminal
        return result

    def wait_for_release(self):
        assert self.execution is not None, "Worker has not consumed a durable Run"
        owner = _MAINTENANCE_NATIVE_OWNER
        assert owner is not None and not owner.closed
        owner.native.wait_for_execution_released(self.execution)

    def start(self):
        def run():
            try:
                self.finish()
            except BaseException as error:
                self.failures.append(error)
        thread = threading.Thread(target=run, name="test-sentinel-worker", daemon=True)
        _WORKERS.append((self, thread))
        thread.start()
        return thread


def service(cache, *, replies=(), builtin=SDK, version=VERSION, worker=None, clock=None):
    from core.maintenance.sentinel import SentinelMaintenanceService

    path = cache.parent / "builtin.js"
    path.write_bytes(builtin)
    assets = SentinelAssetManager(cache, opener=Opener(replies))
    maintenance = SentinelMaintenanceService(
        manager=assets, builtin_path=path, builtin_version=version,
        clock=clock or (lambda: 1700000000.0),
    )
    if worker is not None:
        worker.maintenance = maintenance
    return maintenance


def test_missing_cache_status_reads_only_local_builtin_without_creating_cache(tmp_path):
    cache = tmp_path / "candidates"
    summary = service(cache).status()
    assert summary == {
        "ok": True, "running": False, "last_checked_at": None, "last_status": "never",
        "error_code": None, "builtin": {"version": VERSION, "sha256": hashlib.sha256(SDK).hexdigest()},
        "candidate": None, "comparison": "not_checked",
    }
    assert not cache.exists()


def test_double_click_accepts_one_durable_run_and_worker_publishes_safe_metadata(tmp_path):
    worker = WorkerConsumer()
    maintenance = service(tmp_path / "cache", replies=[LOADER, SDK], worker=worker)
    accepted = maintenance.start_check()
    duplicate = maintenance.start_check()
    assert accepted["started"] is True and accepted["running"] is True
    assert duplicate["started"] is False and duplicate["running"] is True
    assert accepted["run_id"] == duplicate["run_id"]
    assert accepted["task_id"] == duplicate["task_id"]
    assert not (tmp_path / "cache").exists()
    assert maintenance.manager.opener.replies == [LOADER, SDK]
    worker.finish()
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
    assert not worker.failures
    serialized = json.dumps(result)
    assert str(tmp_path) not in serialized and "sdk_url" not in serialized and "loader_sha256" not in serialized


@pytest.mark.parametrize(("version", "builtin", "expected"), [
    ("different", SDK, "version_changed"),
    (VERSION, SDK + b"// different", "content_changed"),
])
def test_candidate_comparison_distinguishes_version_and_content_changes(tmp_path, version, builtin, expected):
    worker = WorkerConsumer()
    maintenance = service(tmp_path / "cache", replies=[LOADER, SDK], worker=worker, builtin=builtin, version=version)
    maintenance.start_check()
    worker.finish()
    assert maintenance.status()["comparison"] == expected


def test_failed_refresh_keeps_candidate_and_persists_failure_across_service_restart(tmp_path):
    worker = WorkerConsumer()
    cache = tmp_path / "cache"
    maintenance = service(cache, replies=[LOADER, SDK, OSError("private-token https://secret.test")], worker=worker)
    maintenance.start_check()
    worker.finish()
    good = maintenance.status()["candidate"]
    maintenance.start_check()
    worker.finish()
    restored = service(cache).status()
    assert restored["last_status"] == "failed"
    assert restored["last_checked_at"] == 1700000000.0
    assert restored["error_code"] == "fetch_or_cache_failed"
    assert restored["candidate"] == good
    assert "private-token" not in json.dumps(restored)


def test_success_metadata_and_time_are_restored_without_network(tmp_path):
    worker = WorkerConsumer()
    cache = tmp_path / "cache"
    maintenance = service(cache, replies=[LOADER, SDK], worker=worker)
    maintenance.start_check()
    worker.finish()
    assert service(cache).status()["last_status"] == "refreshed"
    assert service(cache).status()["comparison"] == "same"


def test_get_status_never_waits_for_a_refresh_holding_the_asset_cache_lock(tmp_path):
    started, release = threading.Event(), threading.Event()
    cache = tmp_path / "cache"
    maintenance = service(cache)

    class BlockingOpener(Opener):
        def open(self, request, timeout):
            started.set()
            assert release.wait(3)
            return super().open(request, timeout)

    maintenance.manager.opener = BlockingOpener([LOADER, SDK])

    worker = WorkerConsumer(maintenance)
    maintenance.start_check()
    thread = worker.start()
    assert started.wait(1)
    try:
        before = time.monotonic()
        result = maintenance.status()
        assert time.monotonic() - before < 0.25
        assert result["running"] is True
        assert maintenance._lease(create=False) is None
        assert not release.is_set()
    finally:
        release.set()
        thread.join(timeout=3)
        assert not thread.is_alive() and not worker.failures
    assert maintenance.status()["last_status"] == "refreshed"
    lease = maintenance._lease(create=False)
    assert lease is not None
    lease.close()


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


def test_worker_handler_recovers_after_unexpected_failure(tmp_path):
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
    assert not entered.is_set(), "Web acceptance cannot execute the manager"
    worker = WorkerConsumer(maintenance)
    thread = worker.start()
    assert entered.wait(1)
    assert maintenance.start_check()["started"] is False
    release.set()
    assert completed.wait(1)
    thread.join(timeout=3)
    assert not thread.is_alive() and not worker.failures
    # The terminal status comes from actual gateway settlement.
    for _ in range(100):
        result = maintenance.status()
        if not result["running"]:
            break
        threading.Event().wait(0.005)
    assert result["last_status"] == "failed"
    assert result["error_code"] == "check_failed"
    assert worker_daemon == [True]
    assert "private-token" not in json.dumps(result)


def test_shared_worker_submit_failure_keeps_original_durable_run_queued(tmp_path):
    from core.operations import concurrency, task_gateway
    from core.storage.operations import store

    maintenance = service(tmp_path / "cache", replies=[LOADER, SDK])
    receipt = maintenance.start_check()
    original = store.get_run(receipt["run_id"])
    assert receipt["started"] is True and receipt["status"] == "queued"
    assert not maintenance.manager.cache_dir.exists()
    admission = task_gateway.admit_operation_run(original)
    assert admission.admitted
    # The dispatcher uses this exact rollback if its shared executor rejects a
    # submission; it must release the unused permit and keep the same identity.
    task_gateway.rollback_admission(admission.context, reason="executor_submit_failed")
    _MAINTENANCE_NATIVE_OWNER.native.wait_for_execution_released(admission.context)
    queued = store.get_run(receipt["run_id"])
    assert queued["status"] == "queued"
    assert queued["id"] == original["id"] and queued["task_id"] == original["task_id"]
    assert queued["data"]["last_requeue_reason"] == "executor_submit_failed"
    assert admission.context.released
    assert not concurrency.has_active_execution(admission.context.execution_key)
    repeated = maintenance.start_check()
    assert repeated["started"] is False and repeated["run_id"] == receipt["run_id"]
    WorkerConsumer(maintenance).finish()
    assert maintenance.status()["last_status"] == "refreshed"


def test_separate_service_instances_share_a_nonblocking_check_lease(tmp_path):
    worker = WorkerConsumer()
    cache = tmp_path / "cache"
    first = service(cache, replies=[LOADER, SDK], worker=worker)
    second = service(cache)
    receipt = first.start_check()
    repeated = second.start_check()
    assert receipt["started"] is True and repeated["started"] is False
    assert receipt["run_id"] == repeated["run_id"]
    assert second.status()["running"] is True
    assert not cache.exists(), "queued Web requests must not acquire a file lease"
    worker.finish()
    assert second.status()["running"] is False
    assert second.status()["last_status"] == "refreshed"


def test_acceptance_does_not_wait_for_asset_download_lock_or_start_a_worker(tmp_path):
    import fcntl

    cache = tmp_path / "cache"
    cache.mkdir()
    maintenance = service(cache)
    maintenance.manager.timeout_seconds = 0.4
    with (cache / ".lock").open("wb") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        before = time.monotonic()
        result = maintenance.start_check()
        assert time.monotonic() - before < 0.25
    assert result["status"] == "queued"
    assert result["running"] is True
    assert not (cache / ".maintenance.lock").exists()
    assert not _WORKERS


def _wait_until_check_finishes(maintenance, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = maintenance.status()
        if not result["running"]:
            # Business status may publish before the native permit releases.
            # Await the original consumer exit within this same wait budget.
            for consumer, thread in tuple(_WORKERS):
                if consumer.maintenance is maintenance:
                    thread.join(timeout=max(0.0, deadline - time.monotonic()))
                    assert not thread.is_alive(), "maintenance Worker did not finish its original release wait"
                    assert not consumer.failures, consumer.failures
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
        if len(command) < 2 or not str(command[1]).endswith("check_sentinel_assets.py"):
            return real_popen(command, **kwargs)
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
        assert not children
        WorkerConsumer(maintenance).start()
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
        WorkerConsumer(maintenance).start()
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
        if len(command) < 2 or not str(command[1]).endswith("check_sentinel_assets.py"):
            return real_popen(command, **kwargs)
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
    assert not children
    WorkerConsumer(maintenance).start()
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
        if len(command) < 2 or not str(command[1]).endswith("check_sentinel_assets.py"):
            return real_popen(command, **kwargs)
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
    maintenance = sentinel.SentinelMaintenanceService(builtin_path=builtin, builtin_version=VERSION)
    worker = WorkerConsumer(maintenance)
    maintenance.start_check()
    assert not children
    before = time.monotonic()
    worker.finish(wait_for_release=False)
    assert time.monotonic() - before < 0.25
    worker.wait_for_release()
    assert len(children) == 1 and children[0].poll() < 0
    result = maintenance.status()
    assert result["running"] is False and result["error_code"] == "check_failed"
    assert "private-pipe-failure" not in json.dumps(result)
