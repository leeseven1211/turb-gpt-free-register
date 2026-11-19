import unittest
from types import SimpleNamespace
from unittest.mock import patch,Mock
from core.runtime import standalone
from core.runtime.context import RuntimeContext

class StandaloneOwnerTests(unittest.TestCase):
    def setUp(self):
        self.previous=standalone._OWNER
        self.previous_binding=standalone._BINDING
        self.previous_lost=standalone._LOST
        standalone._OWNER=None
        standalone._BINDING=None
        import threading
        standalone._LOST=threading.Event()
        self.addCleanup(setattr,standalone,'_OWNER',self.previous)
        self.addCleanup(setattr,standalone,'_BINDING',self.previous_binding)
        self.addCleanup(setattr,standalone,'_LOST',self.previous_lost)
    def test_managed_web_never_obtains_a_standalone_execution_owner(self):
        with patch('core.runtime.process.get_runtime_context',return_value=RuntimeContext('web')):
            with self.assertRaisesRegex(RuntimeError,'web_execution_forbidden'):standalone.require_standalone_owner()
        self.assertIsNone(standalone._OWNER)
    def test_standalone_acquires_once_and_retains_until_process_exit(self):
        owner=Mock();bootstrap=SimpleNamespace(mode='combined',instance_id='fixture',runtime_dir='/stable')
        with patch('core.runtime.process.get_runtime_context',return_value=None),patch('core.runtime.bootstrap.RuntimeBootstrap.from_environment',return_value=bootstrap),patch('core.runtime.instance_owner.ExecutionOwner',return_value=owner),patch('core.storage.postgres.schema_name',return_value='test_fixture'),patch('core.runtime.standalone.atexit.register'):
            standalone.require_standalone_owner();standalone.require_standalone_owner()
        owner.start.assert_called_once();self.assertEqual(owner.require_owner.call_count,2)
    def test_owner_conflict_fails_before_any_caller_execution(self):
        owner=Mock();owner.start.side_effect=RuntimeError('owner_file_busy')
        bootstrap=SimpleNamespace(mode='combined',instance_id='fixture',runtime_dir='/stable')
        with patch('core.runtime.process.get_runtime_context',return_value=None),patch('core.runtime.bootstrap.RuntimeBootstrap.from_environment',return_value=bootstrap),patch('core.runtime.instance_owner.ExecutionOwner',return_value=owner),patch('core.storage.postgres.schema_name',return_value='test_fixture'):
            with self.assertRaisesRegex(RuntimeError,'owner_file_busy'):standalone.require_standalone_owner()
        self.assertIsNone(standalone._OWNER)
