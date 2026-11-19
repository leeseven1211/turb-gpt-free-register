"""Phase 6 T5 read consistency regressions against product fake connections."""
import unittest
from unittest.mock import patch

from core.storage import runtime_config as repository


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def execute(self, sql, args=None):
        self.connection.queries.append((sql,args))
        db = self.connection
        if 'to_regclass' in sql:
            self.rows = [{'relation': 'table' if db.exists else None}]
        elif 'JOIN' in sql:
            revision, values = db.current
            selected = values if args is None else {key: value for key,value in values.items() if key in args[0]}
            self.rows = [dict(active=db.active,revision=revision,key=key,value_encrypted=value)
                         for key,value in selected.items() if db.active]
            if not self.rows:
                self.rows = [dict(active=db.active,revision=revision,key=None,value_encrypted=None)]
            # A concurrent write after this SQL statement cannot change its rows.
            db.current = (2, {'A':'new'})
        elif 'active, revision' in sql:
            revision, _ = db.current
            self.rows = [dict(active=db.active,revision=revision)]
            db.current = (2, {'A':'new'})
        else:
            self.rows = [dict(key=key,value_encrypted=value) for key,value in db.current[1].items() if args is None or key in args[0]]
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, *, active=True, exists=True):
        self.active, self.exists = active, exists
        self.current = (1, {'A':'old'})
        self.queries = []
    def cursor(self, **kwargs):
        return Cursor(self)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        no_db = patch.object(repository.postgres_store, 'connect', side_effect=AssertionError('real DB forbidden'))
        no_db.start()
        self.addCleanup(no_db.stop)
        self.cipher = patch.object(repository, '_cipher', return_value=object())
        self.decrypt = patch.object(repository, '_decrypt', side_effect=lambda cipher,value:value)
        self.cipher.start()
        self.decrypt.start()
        self.addCleanup(self.cipher.stop)
        self.addCleanup(self.decrypt.stop)

    def test_concurrent_commit_cannot_pair_old_revision_with_new_values(self):
        self.assertEqual(repository.read_snapshot(conn=Connection()), ({'A':'old'},1))

    def test_inactive_does_not_decrypt_or_return_values(self):
        self.assertEqual(repository.read_snapshot(conn=Connection(active=False)), (None,1))
        repository._cipher.assert_not_called()

    def test_missing_metadata_does_not_build_tables(self):
        connection = Connection(exists=False)
        self.assertEqual(repository.read_snapshot(conn=connection), (None,0))
        self.assertEqual(len(connection.queries),1)

    def test_empty_filter_is_revisioned_empty_values_not_all_rows(self):
        self.assertEqual(repository.read_snapshot(conn=Connection(), keys=[]), ({},1))

    def test_selected_keys_are_bound_as_parameters(self):
        connection = Connection()
        selected = "bad'); DROP TABLE x; --"
        self.assertEqual(repository.read_snapshot(conn=connection, keys=[selected]), ({},1))
        self.assertNotIn(selected, connection.queries[-1][0])
        self.assertEqual(connection.queries[-1][1],([selected],))

if __name__ == '__main__':
    unittest.main()
