"""Unique execution owner for one host/instance; never a business lease reaper.

The composing runtime supplies a stable instance directory and a dedicated,
nonpooled autocommit PG connection. Web mode never takes execution ownership.
A lost session cannot be recovered in-process. Its local file fence stays held
until all owner monitoring has stopped and close() succeeds, or the process exits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import threading
import time
from typing import Callable, Protocol
import uuid

_NAMESPACE = 'turb.runtime.execution-owner:v1'
_SCHEMA = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,62}$')
_INSTANCE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
logger = logging.getLogger(__name__)
_LOSS_DIAGNOSTIC_CODES = frozenset({
    'owner_probe_timeout', 'owner_connection_lost', 'owner_lock_lost',
    'owner_probe_callback_failed',
})

class OwnerError(RuntimeError):
    """Stable public reason, deliberately excluding exception/connection text."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

@dataclass(frozen=True)
class OwnerIdentity:
    host: str
    pid: int
    process_start: str
    nonce: str

@dataclass(frozen=True)
class LockIdentity:
    filename: str
    advisory_key: tuple[int, int]

@dataclass(frozen=True)
class OwnerStatus:
    mode: str
    instance_id: str
    schema: str
    state: str
    identity: OwnerIdentity | None
    advisory_key: tuple[int, int]
    file_lock_held: bool
    acquired_at: float | None
    last_verified_at: float | None
    error_code: str
    callback_failed: bool

class FileLease(Protocol):
    held: bool
    def acquire(self) -> None: ...
    def write_metadata(self, value: dict) -> None: ...
    def close(self) -> None: ...


def lock_identity(schema: str, instance_id: str) -> LockIdentity:
    """Same identity across modes, ports, releases and Python hash seeds.

    Distinct instance/schema pairs intentionally have distinct local and PG locks.
    PG session advisory locks are additionally scoped by the connected database.
    Multiple databases sharing this local directory and the same pair serialize
    conservatively; a DB switch cannot evade a still-running local old owner.
    """
    if not isinstance(schema, str) or not _SCHEMA.fullmatch(schema):
        raise ValueError('invalid runtime schema')
    if not isinstance(instance_id, str) or not _INSTANCE.fullmatch(instance_id):
        raise ValueError('invalid runtime instance')
    raw = f'{_NAMESPACE}\0{schema}\0{instance_id}'.encode('utf-8')
    digest = hashlib.sha256(raw).digest()
    key = tuple(int.from_bytes(digest[offset:offset+4], 'big', signed=True) for offset in (0, 4))
    return LockIdentity(f'execution-owner-{digest.hex()}.lock', key)


def current_identity() -> OwnerIdentity:
    """A pid alone is insufficient; collect its observed start and a run nonce."""
    pid = os.getpid()
    try:
        result = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart='],
                                capture_output=True, text=True, timeout=2, check=False)
        start = result.stdout.strip() if result.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        start = ''
    if not start:
        raise OwnerError('owner_identity_unavailable')
    return OwnerIdentity(socket.gethostname(), pid, start, uuid.uuid4().hex)


class PosixFileLease:
    """Keep a stable inode. Never unlink a lock file, including during close."""
    def __init__(self, path: Path):
        self.path = path
        self._fd: int | None = None
        self._close_failed = False
        self.held = False
    def acquire(self) -> None:
        import fcntl
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        fd = os.open(self.path, flags, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
                raise OwnerError('owner_file_invalid')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise OwnerError('owner_file_busy') from None
            self._fd = fd
            self.held = True
        except BaseException:
            os.close(fd)
            raise
    def write_metadata(self, value: dict) -> None:
        if self._fd is None or not self.held:
            raise OwnerError('owner_file_not_held')
        data = (json.dumps(value, ensure_ascii=True, separators=(',', ':')) + '\n').encode('utf-8')
        os.lseek(self._fd, 0, os.SEEK_SET)
        offset = 0
        while offset < len(data):
            written = os.write(self._fd, data[offset:])
            if written <= 0:
                raise OSError('owner metadata write failed')
            offset += written
        os.ftruncate(self._fd, len(data))
    def close(self) -> None:
        if self._close_failed:
            raise OwnerError('owner_file_close_unknown')
        if self._fd is not None:
            # A failed close may already have freed the descriptor. Never retry
            # that integer: another thread could now own the same descriptor.
            # No LOCK_UN on an inherited/shared open-file description is issued.
            fd = self._fd
            self._fd = None
            try:
                os.close(fd)
            except OSError:
                self._close_failed = True
                raise
            self.held = False


class ExecutionOwner:
    """Lifecycle ownership only; the runtime separately controls admission.

    on_pause and on_resume may only update local state or wake a reporter. can_resume
    checks whether work is idle without holding the owner state lock. on_lost
    closes admission permanently. A paused session never reacquires its locks.
    close() belongs after execution components have stopped. False means the
    runtime must retain its fence and exit rather than report a clean stop.
    """
    def __init__(self, *, mode: str, instance_id: str, schema: str, stable_dir: Path,
                 connect_dedicated: Callable[[], object], on_lost: Callable[[], None],
                 file_lock_factory: Callable[[Path], FileLease] = PosixFileLease,
                 identity_provider: Callable[[], OwnerIdentity] = current_identity,
                 monitor_interval: float = 1.0, probe_timeout: float = 5.0,
                 on_pause: Callable[[], None] | None = None,
                 can_resume: Callable[[], bool] | None = None,
                 on_resume: Callable[[], None] | None = None):
        if mode not in {'web', 'worker', 'combined'}:
            raise ValueError('invalid runtime mode')
        if not Path(stable_dir).is_absolute():
            raise ValueError('runtime instance directory must be absolute and stable')
        if not (0 < monitor_interval < probe_timeout):
            raise ValueError('owner probe timeout must exceed its positive interval')
        pause_callbacks = (on_pause, can_resume, on_resume)
        if any(callback is not None for callback in pause_callbacks) and not all(
                callable(callback) for callback in pause_callbacks):
            raise ValueError('owner pause requires all callbacks')
        self.mode = mode
        self.instance_id = instance_id
        self.schema = schema
        self.lock = lock_identity(schema, instance_id)
        self._path = Path(stable_dir).resolve() / 'execution-owner' / self.lock.filename
        self._connect = connect_dedicated
        self._on_lost = on_lost
        self._on_pause = on_pause
        self._can_resume = can_resume
        self._on_resume = on_resume
        self._file_factory = file_lock_factory
        self._identity_provider = identity_provider
        self._interval = float(monitor_interval)
        self._timeout = float(probe_timeout)
        self._mutex = threading.RLock()
        self._lifecycle = threading.RLock()
        self._stop = threading.Event()
        self._state = 'new'
        self._identity: OwnerIdentity | None = None
        self._file: FileLease | None = None
        self._connection = None
        self._backend_pid: int | None = None
        self._threads: list[threading.Thread] = []
        self._acquired_at: float | None = None
        self._last_verified_at: float | None = None
        self._last_verified_mono = 0.0
        self._error_code = ''
        self._callback_failed = False

    def _same_process(self) -> bool:
        return self._identity is None or self._identity.pid == os.getpid()

    def status(self) -> OwnerStatus:
        self._expire()
        with self._mutex:
            return OwnerStatus(self.mode, self.instance_id, self.schema, self._state,
                self._identity, self.lock.advisory_key, bool(self._file and self._file.held),
                self._acquired_at, self._last_verified_at, self._error_code, self._callback_failed)

    def is_owner(self) -> bool:
        self._expire()
        with self._mutex:
            return self._same_process() and self._state == 'held'

    def require_owner(self) -> None:
        if not self._same_process():
            raise OwnerError('owner_process_changed')
        self._expire()
        with self._mutex:
            if self._state != 'held':
                raise OwnerError(self._error_code or 'execution_owner_required')

    def start(self) -> OwnerStatus:
        with self._lifecycle:
            if not self._same_process():
                raise OwnerError('owner_process_changed')
            already_held = False
            with self._mutex:
                if self._state == 'held':
                    already_held = True
                elif self._state == 'disabled':
                    return self.status()
                elif self._state != 'new':
                    raise OwnerError(self._error_code or 'owner_not_restartable')
                elif self.mode == 'web':
                    self._state = 'disabled'
                    return self.status()
                else:
                    self._state = 'starting'
            if already_held:
                # 验证过期可能触发失去归属的诊断，不能在状态锁内记录日志。
                self.require_owner()
                return self.status()
            try:
                self._identity = self._identity_provider()
                if self._identity.pid != os.getpid() or not self._identity.process_start or not self._identity.nonce:
                    raise OwnerError('owner_identity_unavailable')
                self._file = self._file_factory(self._path)
                self._file.acquire()
                try:
                    self._connection = self._connect()
                except Exception:
                    raise OwnerError('owner_connect_failed') from None
                if self._connection.autocommit is not True or self._connection.closed:
                    raise OwnerError('owner_connection_invalid')
                row = self._connection.execute(
                    'SELECT pg_try_advisory_lock(%s::integer, %s::integer), pg_backend_pid()',
                    self.lock.advisory_key).fetchone()
                if not row or row[0] is not True:
                    raise OwnerError('owner_database_busy')
                if len(row) != 2 or type(row[1]) is not int or row[1] <= 0:
                    raise OwnerError('owner_connection_invalid')
                self._backend_pid = row[1]
                self._acquired_at = self._last_verified_at = time.time()
                self._last_verified_mono = time.monotonic()
                self._file.write_metadata({'namespace': _NAMESPACE, 'instance_id': self.instance_id,
                    'schema': self.schema, 'mode': self.mode, 'identity': asdict(self._identity),
                    'acquired_at': self._acquired_at, 'advisory_key': self.lock.advisory_key})
                with self._mutex:
                    self._state = 'held'
                # The watchdog must not share the probe's blocking database call.
                for name, target in [('execution-owner-watchdog', self._watchdog), ('execution-owner-probe', self._monitor)]:
                    thread = threading.Thread(name=name, target=target, daemon=True)
                    thread.start()
                    self._threads.append(thread)
                return self.status()
            except BaseException as cause:
                self._stop.set()
                with self._mutex:
                    self._state = 'failed'
                    self._error_code = cause.code if isinstance(cause, OwnerError) else 'owner_start_failed'
                # No execution was admitted. Release only this startup's resources;
                # a thread still in I/O keeps the local fence until exit/clean close.
                self.close(timeout=1.0)
                if not isinstance(cause, Exception):
                    raise
                raise OwnerError(self._error_code or 'owner_start_failed') from None

    def _lose(self, code: str) -> None:
        with self._mutex:
            if not self._mark_lost_locked(code):
                return
        self._notify_lost(code)

    def _mark_lost_locked(self, code: str) -> bool:
        if self._state in ('held', 'paused'):
            self._state = 'lost'
            self._error_code = code
            self._stop.set()
            return True
        return False

    def _notify_lost(self, code: str) -> None:
        # Publish the closed state before notifying the shared admission gate.
        try:
            self._on_lost()
        except Exception:
            with self._mutex:
                self._callback_failed = True
        # 先关闭接单，再在状态锁外记录固定原因；日志故障不影响已有收口。
        safe_code = code if code in _LOSS_DIAGNOSTIC_CODES else 'owner_lost'
        try:
            logger.warning("执行归属已丢失：code=%s", safe_code)
        except Exception:
            pass

    def _expire(self) -> None:
        lost = False
        paused = False
        reason = 'owner_probe_timeout'
        with self._mutex:
            if not self._same_process() or self._state not in ('held', 'paused'):
                return
            age = time.monotonic() - self._last_verified_mono
            if self._state == 'held' and age >= self._timeout:
                if self._on_pause is None or age >= 2 * self._timeout:
                    lost = self._mark_lost_locked('owner_probe_timeout')
                else:
                    self._state = 'paused'
                    self._error_code = 'owner_probe_paused'
                    try:
                        self._on_pause()
                    except Exception:
                        self._callback_failed = True
                        reason = 'owner_probe_callback_failed'
                        lost = self._mark_lost_locked(reason)
                    else:
                        paused = True
            elif self._state == 'paused' and age >= 2 * self._timeout:
                lost = self._mark_lost_locked('owner_probe_timeout')
        if lost:
            self._notify_lost(reason)
        elif paused:
            try:
                logger.warning("执行归属验证超时，已暂停接单：code=owner_probe_paused")
            except Exception:
                pass

    def _watchdog(self) -> None:
        while not self._stop.wait(min(self._interval, self._timeout / 4)):
            self._expire()

    def _idle_for_retry(self) -> bool:
        try:
            idle = self._can_resume() is True
        except Exception:
            with self._mutex:
                self._callback_failed = True
            self._lose('owner_probe_callback_failed')
            return False
        if not idle:
            self._lose('owner_probe_timeout')
        return idle

    def _monitor(self) -> None:
        unsigned_key = tuple(value & 0xffffffff for value in self.lock.advisory_key)
        while not self._stop.wait(self._interval):
            try:
                self._expire()
                with self._mutex:
                    state = self._state
                if state not in ('held', 'paused'):
                    return
                if self._connection is None or self._connection.closed:
                    self._lose('owner_connection_lost')
                    return
                if state == 'paused':
                    if not self._idle_for_retry():
                        return
                    self._expire()
                    if self._stop.is_set():
                        return
                # A successful SELECT 1 alone does not prove this session still owns
                # the lock. Two-int advisory locks have objsubid=2 in pg_locks.
                row = self._connection.execute('''SELECT EXISTS (
                    SELECT 1 FROM pg_catalog.pg_locks
                    WHERE locktype = 'advisory' AND pid = pg_backend_pid()
                      AND classid = %s::oid AND objid = %s::oid AND objsubid = 2
                      AND mode = 'ExclusiveLock' AND granted
                ), pg_backend_pid()''', unsigned_key).fetchone()
                if not row or row[0] is not True:
                    self._lose('owner_lock_lost')
                    return
                if len(row) != 2 or type(row[1]) is not int or row[1] != self._backend_pid:
                    self._lose('owner_connection_lost')
                    return
                verified_mono, verified_at = time.monotonic(), time.time()
                # A late success must not erase an expired verification budget,
                # even if OS scheduling delayed the independent watchdog.
                self._expire()
                if self._stop.is_set():
                    return
                if state == 'paused' and not self._idle_for_retry():
                    return
                loss_reason = ''
                with self._mutex:
                    # A probe sent before the pause cannot clear it.
                    if self._state != state:
                        continue
                    deadline = self._last_verified_mono + (
                        2 * self._timeout if state == 'paused' else self._timeout)
                    if time.monotonic() >= deadline:
                        continue
                    if state == 'paused':
                        try:
                            self._on_resume()
                        except Exception:
                            self._callback_failed = True
                            loss_reason = 'owner_probe_callback_failed'
                        else:
                            if time.monotonic() >= min(deadline, verified_mono + self._timeout):
                                loss_reason = 'owner_probe_timeout'
                            else:
                                self._state = 'held'
                                self._error_code = ''
                    if loss_reason:
                        self._mark_lost_locked(loss_reason)
                    else:
                        self._last_verified_at = verified_at
                        self._last_verified_mono = verified_mono
                if loss_reason:
                    self._notify_lost(loss_reason)
                    return
                if state == 'paused':
                    try:
                        logger.info("执行归属复查成功，已恢复接单：code=owner_probe_resumed")
                    except Exception:
                        pass
            except Exception:
                self._lose('owner_connection_lost')
                return

    def close(self, timeout: float = 2.0) -> bool:
        """Only call after execution shutdown; False retains the local fence."""
        if not self._same_process():
            raise OwnerError('owner_process_changed')
        with self._lifecycle:
            with self._mutex:
                if self._state == 'closed':
                    return True
                self._stop.set()
                self._state = 'stopping'
            deadline = time.monotonic() + max(0.0, timeout)
            for thread in self._threads:
                if thread is not threading.current_thread():
                    thread.join(max(0.0, deadline - time.monotonic()))
            if any(thread.is_alive() for thread in self._threads):
                return False
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    with self._mutex:
                        self._error_code = self._error_code or 'owner_close_failed'
                    return False
                self._connection = None
            if self._file is not None:
                try:
                    self._file.close()
                except Exception:
                    with self._mutex:
                        self._error_code = self._error_code or 'owner_close_failed'
                    return False
            with self._mutex:
                self._state = 'closed'
            return True
