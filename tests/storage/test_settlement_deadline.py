"""Offline tests: no dotenv, sockets, PostgreSQL or pool creation."""
import time
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from core.storage import postgres


class SettlementDeadlineTests(unittest.TestCase):
    def test_checkout_timeout_logs_wait_without_connection_target(self):
        from psycopg_pool import PoolTimeout

        @contextmanager
        def timed_out(**_kwargs):
            raise PoolTimeout('postgresql://private-user:private-password@unit.invalid/test_deadline')
            yield

        pool = MagicMock()
        pool.connection = timed_out
        with patch.object(postgres, '_pool_for', return_value=pool), \
                self.assertLogs('core.postgres_store', level='WARNING') as captured:
            with self.assertRaises(PoolTimeout):
                with postgres.connect('postgresql://unit.invalid/test_deadline'):
                    self.fail('超时后仍进入数据库上下文')
        message = captured.records[0].getMessage()
        self.assertRegex(message, r'\bdb_pool_checkout_timeout\b.*\bcheckout_ms=\d')
        self.assertNotIn('private', message)

    def test_expired_deadline_never_checks_out_or_creates_pool(self):
        with patch.object(postgres, '_pool_for') as factory, patch.object(postgres, '_guard_production_database'):
            with self.assertRaises(TimeoutError):
                with postgres.connect('postgresql://unit.invalid/test_deadline', deadline=time.monotonic() - 1):
                    self.fail('expired work entered connection')
            factory.assert_not_called()

    def test_deadlines_do_not_fragment_pool_keys_and_scoped_timeouts(self):
        conn = MagicMock()
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value = conn
        with patch.object(postgres, '_pool_for', return_value=pool) as factory, patch.object(postgres, '_guard_production_database'):
            for seconds in (2, 3):
                with postgres.connect('postgresql://unit.invalid/test_deadline', deadline=time.monotonic() + seconds):
                    pass
            for call in factory.call_args_list:
                self.assertNotIn('deadline', call.args[1])
            for call in pool.connection.call_args_list:
                self.assertGreater(call.kwargs['timeout'], 0)
                self.assertLessEqual(call.kwargs['timeout'], 3)
            sql = str(conn.cursor.return_value.__enter__.return_value.execute.call_args_list)
            self.assertIn('statement_timeout', sql)
            self.assertIn('lock_timeout', sql)
            self.assertIn('true', sql)

    def test_nested_connect_inherits_origin_deadline_without_new_pool_key(self):
        from core.storage.operations import common
        from core.operations.settlement_contracts import SettlementDomain
        domain=SettlementDomain('postgresql://unit.invalid/inherited','test_operations','test_records','unit')
        with common.settlement_scope(domain,deadline=time.monotonic()-1), \
             patch.object(postgres,'_pool_for') as factory:
            with self.assertRaises(TimeoutError):
                with postgres.connect():
                    self.fail('nested expired SQL entered checkout')
            factory.assert_not_called()
