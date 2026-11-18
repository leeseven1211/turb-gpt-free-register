"""Owner identity checks reuse only this process's confirmed start time."""
from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.storage.operations import permits


class CurrentProcessOwnerChecks(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(permits._OWNER_CACHE, {}, clear=True))
        self.stack.enter_context(patch.dict(permits.__dict__, {'_OWNER_CACHE_PID': 101}))
        self.stack.enter_context(patch.object(permits, '_LOCAL_EXITS', set()))
        self.stack.enter_context(patch.object(permits.os, 'getpid', return_value=101))
        self.kill = self.stack.enter_context(patch.object(permits.os, 'kill'))

    def owner(self, **changes):
        return {'host_id': permits._HOST_ID, 'pid': 101, 'process_start': 'current-start',
                'instance_id': 'current-instance', **changes}

    def cached_owner(self):
        owner = self.owner()
        permits._OWNER_CACHE[101] = dict(owner)
        return owner

    def test_confirmed_current_process_reuses_start_but_checks_existence_each_time(self):
        owner = self.cached_owner()
        with patch.object(permits, '_process_start', return_value='current-start') as process_start:
            self.assertEqual(['alive'] * 64, [permits.owner_liveness(owner) for _ in range(64)])
        process_start.assert_not_called()
        self.assertEqual(64, self.kill.call_count)

    def test_current_process_old_recorded_start_is_exited_without_refreshing_known_identity(self):
        self.cached_owner()
        with patch.object(permits, '_process_start', return_value='current-start') as process_start:
            self.assertEqual('exited', permits.owner_liveness(self.owner(process_start='old-start')))
        process_start.assert_not_called()
        self.assertEqual('current-start', permits._OWNER_CACHE[101]['process_start'])

    def test_unknown_or_absent_cache_uses_fresh_ps_without_cache_writes(self):
        for cache in ({}, {101: self.owner(process_start=None)}, {101: self.owner(process_start='')}):
            with self.subTest(cache=cache), patch.dict(permits._OWNER_CACHE, cache, clear=True):
                with patch.object(permits, '_process_start', side_effect=[None, 'current-start']) as process_start:
                    self.assertEqual('unverified', permits.owner_liveness(self.owner()))
                    self.assertEqual('alive', permits.owner_liveness(self.owner()))
                self.assertEqual(2, process_start.call_count)
                self.assertEqual(cache, permits._OWNER_CACHE)

    def test_other_pid_never_uses_cache_and_detects_reuse_between_checks(self):
        permits._OWNER_CACHE[202] = self.owner(pid=202, process_start='other-start')
        with patch.object(permits, '_process_start', side_effect=['other-start', 'reused-start']) as process_start:
            self.assertEqual('alive', permits.owner_liveness(self.owner(pid=202, process_start='other-start')))
            self.assertEqual('exited', permits.owner_liveness(self.owner(pid=202, process_start='other-start')))
        self.assertEqual([((202,),), ((202,),)], [(call.args,) for call in process_start.call_args_list])

    def test_cache_cannot_override_missing_process_or_permission_error(self):
        owner = self.cached_owner()
        for error, expected in ((ProcessLookupError(), 'exited'), (PermissionError(), 'unverified')):
            with self.subTest(error=type(error).__name__), patch.object(permits.os, 'kill', side_effect=error):
                with patch.object(permits, '_process_start', return_value='current-start') as process_start:
                    self.assertEqual(expected, permits.owner_liveness(owner))
                process_start.assert_not_called()

    def test_host_and_missing_recorded_start_remain_unverified(self):
        self.cached_owner()
        with patch.object(permits, '_process_start', return_value='current-start'):
            self.assertEqual('unverified', permits.owner_liveness(self.owner(host_id='other-host')))
            self.assertEqual('unverified', permits.owner_liveness(self.owner(process_start=None)))
            self.assertEqual('unverified', permits.owner_liveness(self.owner(pid=0)))

    def test_each_current_process_thread_is_checked_even_when_identity_is_cached(self):
        self.cached_owner()
        alive = SimpleNamespace(ident=71, is_alive=lambda: True)
        stopped = SimpleNamespace(ident=72, is_alive=lambda: False)
        with patch.object(permits.threading, 'enumerate', return_value=[alive, stopped]):
            with patch.object(permits, '_process_start', return_value='current-start'):
                self.assertEqual('alive', permits.owner_liveness(self.owner(thread_id=71)))
                self.assertEqual('exited', permits.owner_liveness(self.owner(thread_id=72)))
                self.assertEqual('exited', permits.owner_liveness(self.owner(thread_id=73)))

    def test_fork_first_current_owner_discards_inherited_ancestor_pid_and_instance(self):
        self.cached_owner()
        permits._OWNER_CACHE[202] = self.owner(pid=202, process_start='ancestor-start', instance_id='ancestor')
        with patch.object(permits.os, 'getpid', return_value=202):
            with patch.object(permits, '_process_start', return_value='child-start') as process_start:
                child = permits.current_owner()
                repeated = permits.current_owner()
        self.assertEqual('child-start', child['process_start'])
        self.assertEqual(202, child['pid'])
        self.assertNotEqual('ancestor', child['instance_id'])
        self.assertEqual(child, repeated)
        self.assertEqual({202}, set(permits._OWNER_CACHE))
        process_start.assert_called_once_with(202)

    def test_fork_first_liveness_clears_ancestor_before_creating_any_owner(self):
        self.cached_owner()
        permits._OWNER_CACHE[202] = self.owner(pid=202, process_start='ancestor-start')
        with patch.object(permits.os, 'getpid', return_value=202):
            with patch.object(permits, '_process_start', return_value='child-start') as process_start:
                self.assertEqual('exited', permits.owner_liveness(self.owner(pid=202, process_start='ancestor-start')))
                self.assertEqual('alive', permits.owner_liveness(self.owner(pid=202, process_start='child-start')))
        self.assertEqual({}, permits._OWNER_CACHE)
        self.assertEqual(2, process_start.call_count)

    def test_current_owner_returns_copy_and_retains_first_unknown_identity(self):
        with patch.object(permits, '_process_start', side_effect=[None, 'later-start']) as process_start:
            original = permits.current_owner()
            external = permits.current_owner()
            external['process_start'] = 'mutation'
            self.assertEqual('unverified', permits.owner_liveness(original))
        self.assertIsNone(permits._OWNER_CACHE[101]['process_start'])
        self.assertEqual(2, process_start.call_count)
        self.assertEqual(original['instance_id'], external['instance_id'])

    def test_exact_local_exit_overrides_live_owner_without_releasing_new_execution(self):
        owner = self.cached_owner()
        rows = [{'permit_id': 'p', 'execution_id': 'old', 'owner': owner},
                {'permit_id': 'p', 'execution_id': 'new', 'owner': owner},
                {'permit_id': 'other', 'execution_id': 'old', 'owner': owner}]
        writes = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, query, params=None):
                if str(query).lstrip().startswith('UPDATE'):
                    writes.append(params)

            def fetchall(self):
                return rows

        class Connection(Cursor):
            def cursor(self, **_):
                return Cursor()

        permits.mark_execution_exited('p', 'old')
        with ExitStack() as stack:
            stack.enter_context(patch.object(permits, 'ensure_tables'))
            stack.enter_context(patch.object(permits.postgres, 'connect', return_value=Connection()))
            stack.enter_context(patch.object(permits.postgres, 'qualified', side_effect=lambda name: name))
            stack.enter_context(patch.object(permits, '_process_start', return_value='current-start'))
            release = stack.enter_context(patch.object(permits, 'release', return_value=True))
            result = permits.recover_execution_permits()
        self.assertEqual({'released': 1, 'alive': 2, 'unverified': 0}, result)
        release.assert_called_once_with('p', 'old', reason='owner_exit_confirmed')
        self.assertEqual([('alive', 'p', 'new'), ('alive', 'other', 'old')], writes)

