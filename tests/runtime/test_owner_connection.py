"""Execute only the new connection factory AST; forbid pooled/real DB calls."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

class DedicatedConnectionTests(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).resolve().parents[2] / 'core/storage/postgres.py'
        self.assertTrue(path.exists(),'Dedicated connection candidate missing')
        parsed=ast.parse(path.read_text())
        nodes=[node for node in parsed.body if isinstance(node,ast.FunctionDef) and node.name=='connect_dedicated']
        self.assertEqual(len(nodes),1,'Dedicated connection factory missing')
        self.events=[];self.connection=object()
        def guard_database(target): self.events.append(('database_guard',target))
        def guard_schema(): self.events.append(('schema_guard',))
        self.namespace={'database_url':lambda:'postgres://fixture-db/test_fixture','_guard_production_database':guard_database,'_guard_production_schema':guard_schema}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path),'exec'),self.namespace)
        def connect(target,**kwargs):self.events.append(('connect',target,kwargs));return self.connection
        self.patch=patch.dict(sys.modules,{'psycopg':SimpleNamespace(connect=connect)});self.patch.start();self.addCleanup(self.patch.stop)
    def test_factory_bypasses_pool_and_returns_dedicated_autocommit_session(self):
        result=self.namespace['connect_dedicated']()
        self.assertIs(result,self.connection)
        self.assertEqual([event[0] for event in self.events],['database_guard','schema_guard','connect'])
        kwargs=self.events[2][2];self.assertIs(kwargs['autocommit'],True)
        self.assertEqual(kwargs['connect_timeout'],5)
        self.assertIn('statement_timeout=2000',kwargs['options'])
        self.assertEqual(kwargs['application_name'],'turb-execution-owner')
        self.assertEqual(kwargs['keepalives'],1)
    def test_production_database_guard_rejection_precedes_connection(self):
        def reject(target):raise SystemExit('production database rejected')
        self.namespace['_guard_production_database']=reject
        with self.assertRaises(SystemExit):self.namespace['connect_dedicated']()
        self.assertEqual(self.events,[])
    def test_test_schema_guard_rejection_precedes_connection(self):
        def reject():raise RuntimeError('public schema rejected')
        self.namespace['_guard_production_schema']=reject
        with self.assertRaisesRegex(RuntimeError,'public schema'):self.namespace['connect_dedicated']()
        self.assertEqual([event[0] for event in self.events],['database_guard'])
    def test_absent_database_fails_without_silent_fallback(self):
        self.namespace['database_url']=lambda:''
        with self.assertRaisesRegex(RuntimeError,'DATABASE_URL'):self.namespace['connect_dedicated']()
        self.assertEqual(self.events,[])

if __name__=='__main__':unittest.main(verbosity=2)
