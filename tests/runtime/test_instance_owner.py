"""Contract tests: fake external locks/PG only; no application imports or DB."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'core/runtime/instance_owner.py'
owner_module = None
if SOURCE.exists():
    spec = importlib.util.spec_from_file_location('candidate_instance_owner', SOURCE)
    owner_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = owner_module
    spec.loader.exec_module(owner_module)

class Result:
    def __init__(self, value): self.value = value
    def fetchone(self): return (self.value,)

class FakeConnection:
    def __init__(self, acquire=True, autocommit=True):
        self.autocommit = autocommit
        self.closed = False
        self.acquire = acquire
        self.probe = True
        self.calls = []
        self.close_count = 0
        self.probe_entered = threading.Event()
        self.probe_release = None
        self.close_failure = False
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if 'pg_try_advisory_lock' in sql: return Result(self.acquire)
        if 'pg_locks' in sql:
            self.probe_entered.set()
            if self.probe_release is not None: self.probe_release.wait(2)
            if isinstance(self.probe, Exception): raise self.probe
            return Result(self.probe)
        raise AssertionError('Unexpected SQL: '+sql)
    def close(self):
        self.close_count += 1
        if self.close_failure: raise OSError('private-dsn')
        self.closed = True

class FakeFileLease:
    live = {}
    all = []
    def __init__(self, path):
        self.path = path
        self.held = False
        self.releases = 0
        self.metadata = []
        self.all.append(self)
    def acquire(self):
        if self.path in self.live: raise owner_module.OwnerError('owner_file_busy')
        self.live[self.path] = self
        self.held = True
    def write_metadata(self, value): self.metadata.append(value)
    def close(self):
        if self.held:
            self.releases += 1
            assert self.live.get(self.path) is self
            del self.live[self.path]
            self.held = False

class InstanceOwnerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(owner_module, 'Execution owner candidate is not implemented')
        FakeFileLease.live.clear(); FakeFileLease.all.clear()
        self.owners = []
        self.connections = []
    def tearDown(self):
        for connection in self.connections:
            if connection.probe_release: connection.probe_release.set()
            connection.close_failure = False
        for owner in self.owners: owner.close(timeout=1)
    def make(self, *, connection=None, connector=None, on_lost=None, **kwargs):
        conn = connection or FakeConnection(); self.connections.append(conn)
        calls = []
        def connect():
            calls.append(True)
            return connector() if connector else conn
        owner = owner_module.ExecutionOwner(mode=kwargs.pop('mode','worker'), instance_id='fixture', schema='test_fixture',
            stable_dir=Path('/stable/fixture'), connect_dedicated=connect,
            file_lock_factory=FakeFileLease,
            identity_provider=lambda: owner_module.OwnerIdentity('host-fixture', os.getpid(), 'start-fixture', 'nonce-fixture'),
            on_lost=on_lost or (lambda: None), monitor_interval=kwargs.pop('monitor_interval', 100),
            probe_timeout=kwargs.pop('probe_timeout', 300), **kwargs)
        self.owners.append(owner)
        return owner, conn, calls
    def test_web_never_creates_either_execution_lock(self):
        owner, conn, calls = self.make(mode='web')
        self.assertEqual(owner.start().state, 'disabled')
        self.assertFalse(owner.is_owner()); self.assertEqual(calls, [])
        self.assertEqual(FakeFileLease.all, []); self.assertTrue(owner.close())
    def test_lock_identity_is_stable_distinct_and_path_safe(self):
        key = owner_module.lock_identity('test_fixture', 'fixture')
        self.assertEqual(key, owner_module.lock_identity('test_fixture', 'fixture'))
        self.assertNotEqual(key, owner_module.lock_identity('test_other', 'fixture'))
        self.assertNotEqual(key, owner_module.lock_identity('test_fixture', 'second'))
        self.assertRegex(key.filename, r'^execution-owner-[a-f0-9]{64}\.lock$')
        self.assertTrue(all(-(2**31) <= value < 2**31 for value in key.advisory_key))
        for bad in ['../escape', '', '/root', '.', 'a/b']:
            with self.subTest(bad=bad), self.assertRaises(ValueError): owner_module.lock_identity('test_fixture', bad)
        with self.assertRaises(ValueError): owner_module.lock_identity('x; DROP SCHEMA', 'fixture')
    def test_relative_instance_path_rejected_before_connections(self):
        with self.assertRaises(ValueError):
            owner_module.ExecutionOwner(mode='worker',instance_id='fixture',schema='test_fixture',stable_dir=Path('release/logs'),connect_dedicated=lambda: self.fail('must not connect'),on_lost=lambda: None)
    def test_duplicate_start_does_not_stack_session_lock(self):
        owner, conn, calls = self.make(); first = owner.start(); second = owner.start()
        self.assertEqual(first.identity, second.identity); self.assertTrue(owner.is_owner())
        owner.require_owner(); self.assertEqual(len(calls), 1)
        self.assertEqual(sum('pg_try_advisory_lock' in sql for sql,_ in conn.calls), 1)
        self.assertTrue(conn.autocommit)
    def test_combined_and_worker_share_lock_before_any_second_connection(self):
        first, _, _ = self.make(); first.start()
        second, _, calls = self.make(mode='combined')
        with self.assertRaisesRegex(owner_module.OwnerError, 'owner_file_busy'): second.start()
        self.assertEqual(calls, []); self.assertTrue(first.is_owner())
    def test_database_busy_releases_only_the_unadmitted_local_handle(self):
        owner, conn, _ = self.make(connection=FakeConnection(acquire=False))
        with self.assertRaisesRegex(owner_module.OwnerError, 'owner_database_busy'): owner.start()
        self.assertTrue(conn.closed); self.assertFalse(FakeFileLease.all[0].held)
        self.assertFalse(owner.is_owner())
    def test_database_connect_failure_redacts_and_releases_startup_file(self):
        def fail(): raise OSError('postgres://secret@private')
        owner, _, _ = self.make(connector=fail)
        with self.assertRaisesRegex(owner_module.OwnerError, '^owner_connect_failed$'): owner.start()
        self.assertFalse(FakeFileLease.all[0].held)
        self.assertNotIn('secret', repr(owner.status()))
    def test_transactional_or_closed_connection_is_never_admitted(self):
        for conn in [FakeConnection(autocommit=False), FakeConnection()]:
            if conn.autocommit: conn.closed = True
            owner, _, _ = self.make(connection=conn)
            with self.assertRaisesRegex(owner_module.OwnerError, 'owner_connection_invalid'): owner.start()
            self.assertFalse(owner.is_owner()); self.assertFalse(FakeFileLease.all[-1].held)
    def test_probe_failure_closes_admission_once_but_holds_local_fence(self):
        lost = threading.Event(); seen = []
        def on_lost(): seen.append(owner.status().state); lost.set()
        conn = FakeConnection(); conn.probe = OSError('private-dsn')
        owner, _, _ = self.make(connection=conn,on_lost=on_lost,monitor_interval=.01,probe_timeout=.2)
        owner.start(); self.assertTrue(lost.wait(1)); self.assertEqual(seen, ['lost'])
        self.assertFalse(owner.is_owner()); self.assertTrue(FakeFileLease.all[0].held)
        self.assertEqual(owner.status().error_code, 'owner_connection_lost')
        with self.assertRaises(owner_module.OwnerError): owner.require_owner()
        with self.assertRaises(owner_module.OwnerError): owner.start()
        second, _, calls = self.make()
        with self.assertRaisesRegex(owner_module.OwnerError, 'owner_file_busy'): second.start()
        self.assertEqual(calls, [])
    def test_missing_session_lock_is_loss_even_when_connection_answers(self):
        lost = threading.Event(); conn = FakeConnection(); conn.probe = False
        owner, _, _ = self.make(connection=conn,on_lost=lost.set,monitor_interval=.01,probe_timeout=.2)
        owner.start(); self.assertTrue(lost.wait(1)); self.assertFalse(owner.is_owner())
        self.assertEqual(owner.status().error_code, 'owner_lock_lost')
        self.assertTrue(FakeFileLease.all[0].held)
    def test_probe_blackhole_has_independent_watchdog_and_close_cannot_release_early(self):
        lost = threading.Event(); conn = FakeConnection(); conn.probe_release = threading.Event()
        owner, _, _ = self.make(connection=conn,on_lost=lost.set,monitor_interval=.01,probe_timeout=.05)
        owner.start(); self.assertTrue(conn.probe_entered.wait(1)); self.assertTrue(lost.wait(1))
        self.assertEqual(owner.status().error_code, 'owner_probe_timeout'); self.assertFalse(owner.is_owner())
        self.assertFalse(owner.close(timeout=.01)); self.assertTrue(FakeFileLease.all[0].held)
        self.assertFalse(conn.closed); conn.probe_release.set()
        self.assertTrue(owner.close(timeout=1)); self.assertFalse(FakeFileLease.all[0].held)
    def test_lost_callback_exception_never_reopens_or_reacquires_owner(self):
        lost = threading.Event()
        def fail(): lost.set(); raise RuntimeError('callback failed')
        conn = FakeConnection(); conn.probe = False
        owner, _, calls = self.make(connection=conn,on_lost=fail,monitor_interval=.01,probe_timeout=.1)
        owner.start(); self.assertTrue(lost.wait(1)); self.assertFalse(owner.is_owner())
        self.assertEqual(len(calls),1); self.assertTrue(FakeFileLease.all[0].held)
    def test_close_is_idempotent_and_does_not_release_a_later_owner(self):
        old, conn, _ = self.make(); old.start(); self.assertTrue(old.close()); self.assertTrue(old.close())
        new, _, _ = self.make(); new.start(); self.assertTrue(old.close())
        self.assertEqual(conn.close_count,1); self.assertTrue(new.is_owner())
        self.assertTrue(FakeFileLease.all[-1].held)
        with self.assertRaises(owner_module.OwnerError): old.start()
    def test_connection_close_failure_retains_file_fence(self):
        owner, conn, _ = self.make(); owner.start(); conn.close_failure = True
        self.assertFalse(owner.close()); self.assertTrue(FakeFileLease.all[0].held)
        self.assertFalse(owner.is_owner()); conn.close_failure = False; self.assertTrue(owner.close())
    def test_forked_identity_cannot_admit_or_close_parent_owner(self):
        owner, conn, _ = self.make(); owner.start()
        with patch.object(owner_module.os, 'getpid', return_value=os.getpid()+1000):
            self.assertFalse(owner.is_owner())
            with self.assertRaisesRegex(owner_module.OwnerError, 'owner_process_changed'): owner.require_owner()
            with self.assertRaisesRegex(owner_module.OwnerError, 'owner_process_changed'): owner.close()
        self.assertFalse(conn.closed); self.assertTrue(FakeFileLease.all[0].held)
    def test_startup_interrupt_cleans_unadmitted_resources_and_preserves_signal(self):
        def interrupt(): raise KeyboardInterrupt()
        owner, _, _ = self.make(connector=interrupt)
        with self.assertRaises(KeyboardInterrupt): owner.start()
        self.assertFalse(FakeFileLease.all[0].held)
        self.assertFalse(owner.is_owner())
    def test_late_probe_cannot_mask_timeout_if_watchdog_scheduling_is_delayed(self):
        lost=threading.Event();conn=FakeConnection();conn.probe_release=threading.Event()
        owner, _, _=self.make(connection=conn,on_lost=lost.set,monitor_interval=.01,probe_timeout=.05)
        # Model a paused watchdog; only the returned probe can notice its deadline.
        with patch.object(owner,'_watchdog',side_effect=lambda: owner._stop.wait(1)):
            owner.start();self.assertTrue(conn.probe_entered.wait(1))
            with owner._mutex:owner._last_verified_mono-=1
            conn.probe_release.set();self.assertTrue(lost.wait(.5))
        self.assertEqual(owner.status().error_code,'owner_probe_timeout')
    def test_probe_deadline_is_not_refreshed_by_a_late_success(self):
        lost = threading.Event(); conn = FakeConnection(); conn.probe_release = threading.Event()
        owner, _, calls = self.make(connection=conn,on_lost=lost.set,monitor_interval=.01,probe_timeout=.05)
        owner.start(); self.assertTrue(conn.probe_entered.wait(1)); self.assertTrue(lost.wait(1))
        previous=owner.status().last_verified_at; conn.probe_release.set()
        self.assertFalse(owner.is_owner()); self.assertEqual(len(calls),1)
        self.assertTrue(owner.close(timeout=1)); self.assertEqual(owner.status().last_verified_at,previous)
    def test_metadata_failure_before_admission_releases_both_resources(self):
        owner, conn, _ = self.make()
        with patch.object(FakeFileLease,'write_metadata',side_effect=OSError('private-path')):
            with self.assertRaisesRegex(owner_module.OwnerError,'owner_start_failed'): owner.start()
        self.assertTrue(conn.closed); self.assertFalse(FakeFileLease.all[0].held)
    def test_monitor_checks_the_held_two_integer_lock_without_relocking(self):
        lost=threading.Event();conn=FakeConnection();conn.probe=False
        owner, _, _=self.make(connection=conn,on_lost=lost.set,monitor_interval=.01,probe_timeout=.2)
        owner.start();self.assertTrue(lost.wait(1))
        probe_sql,params=next((sql,params) for sql,params in conn.calls if 'pg_locks' in sql)
        self.assertIn('pg_backend_pid()',probe_sql);self.assertIn('objsubid = 2',probe_sql)
        self.assertTrue(all(0<=value<2**32 for value in params))
        self.assertEqual(sum('pg_try_advisory_lock' in sql for sql,_ in conn.calls),1)
    def test_public_status_has_process_identity_and_no_connection_material(self):
        owner, _, _ = self.make(); owner.start(); status=owner.status()
        self.assertEqual(status.identity.host,'host-fixture'); self.assertEqual(status.identity.pid,os.getpid())
        self.assertEqual(status.identity.process_start,'start-fixture'); self.assertEqual(status.identity.nonce,'nonce-fixture')
        self.assertEqual(status.schema,'test_fixture'); self.assertEqual(status.instance_id,'fixture')
        self.assertTrue(status.file_lock_held); self.assertGreater(status.last_verified_at,0)
        self.assertNotIn('postgres:',repr(status)); self.assertNotIn('connect_dedicated',repr(status))

if __name__=='__main__': unittest.main(verbosity=2)
