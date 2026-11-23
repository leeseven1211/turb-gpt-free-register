"""Entrypoint ordering is tested with module injection, never actual runtime I/O."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
def mod(name,**values):
    value=ModuleType(name);value.__dict__.update(values);return value


def unexpected_owner_check():
    raise AssertionError("Worker polled execution ownership before the expected shutdown")


class EntrypointTests(unittest.TestCase):
    def load(self,filename='web.py'):
        spec=importlib.util.spec_from_file_location('test_runtime_entry',ROOT/filename);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    def test_invalid_role_and_budgets_fail_before_environment_or_application_import(self):
        entry=self.load()
        for extra in (['--mode','combined','--server','waitress'],['--port','0'],['--http-drain-timeout','nan'],['--http-threads','0']):
            with self.subTest(extra=extra),patch.object(sys,'argv',['web.py',*extra]),patch.dict(sys.modules,{'config.env_loader':None}):
                with self.assertRaises(SystemExit) as caught:entry.main()
                self.assertEqual(caught.exception.code,2)
    def test_worker_sigterm_during_database_or_install_startup_uses_truthful_cleanup(self):
        for stage in ('database','start'):
            entry=self.load('worker.py');events=[];handlers={}
            def interrupt(name):
                events.append(name)
                if name==stage:handlers[entry.signal.SIGTERM](entry.signal.SIGTERM,None)
            bootstrap=SimpleNamespace(prepare_log_environment=lambda:None)
            modules={'config':mod('config'),'config.env_loader':mod('config.env_loader',ensure_loaded=lambda:None),
              'core.runtime.bootstrap':mod('core.runtime.bootstrap',RuntimeBootstrap=SimpleNamespace(from_environment=lambda **_:bootstrap)),
              'core.storage':mod('core.storage',postgres=SimpleNamespace(require_ready=lambda:interrupt('database'))),
              'core.runtime.assembly':mod('core.runtime.assembly',install=lambda *_:events.append('install')),
              'core.runtime.process':mod('core.runtime.process',
                execution_owner_lost=unexpected_owner_check,
                start_runtime=lambda:interrupt('start'),stop_runtime=lambda **_:events.append('stop') or True)}
            with patch.dict(sys.modules,modules),patch.dict(entry.os.environ,{'PYTHON_DOTENV_DISABLED':'1'},clear=True),patch.object(sys,'argv',['worker.py']),patch.object(entry.signal,'signal',side_effect=lambda key,handler:handlers.__setitem__(key,handler)):
                with self.assertRaises(SystemExit) as caught:entry.main()
                self.assertEqual(caught.exception.code,0)
            self.assertEqual('stop' in events,stage=='start')
    def test_http_drains_before_runtime_and_incomplete_http_retains_runtime_resources(self):
        for clean in (True,False):
            events=[];entry=self.load()
            class Server:
                def __init__(self,*args,**kwargs):events.append('http-init')
                def start(self):events.append('http-start')
                def serve(self):events.append('http-serve')
                def stop(self,timeout):events.append(('http-stop',timeout));return clean
                def status(self):return {'workers_alive':1 if not clean else 0}
            bootstrap=SimpleNamespace(mode='web',runtime_dir=Path('/tmp/synthetic-runtime'),prepare_log_environment=lambda:events.append('logs'))
            modules={'config':mod('config'),'config.env_loader':mod('config.env_loader',ensure_loaded=lambda:events.append('env')),'config.deployment':mod('config.deployment',browser_enabled=lambda:True),
              'core.runtime.bootstrap':mod('core.runtime.bootstrap',RuntimeBootstrap=SimpleNamespace(from_environment=lambda **_:bootstrap)),
              'core.runtime.assembly':mod('core.runtime.assembly',install=lambda *a,**k:events.append('install')),
              'core.runtime.process':mod('core.runtime.process',start_runtime=lambda *_:events.append('runtime-start'),stop_runtime=lambda **_:events.append('runtime-stop') or True),
              'core.runtime.http_server':mod('core.runtime.http_server',HttpServer=Server),
              'core.storage':mod('core.storage',postgres=SimpleNamespace(require_ready=lambda:events.append('db')),
                                 registration=SimpleNamespace(init=lambda:events.append('registration-storage'))),
              'core.operation_task_store':mod('core.operation_task_store',init=lambda:events.append('operation-storage')),
              'webui.app':mod('webui.app',create_app=lambda **_:object()),'webui.auth':mod('webui.auth',is_generated_code=lambda:False)}
            with patch.dict(sys.modules,modules),patch.object(sys,'argv',['web.py','--mode','web','--server','waitress']),patch.object(entry,'_acquire_single_instance',return_value=object()),patch.object(entry,'_release_single_instance',side_effect=lambda _:events.append('unlock')),patch.object(entry.signal,'signal'):
                if clean:entry.main()
                else:
                    with self.assertRaises(SystemExit) as caught:entry.main()
                    self.assertEqual(caught.exception.code,3)
            self.assertIn(('http-stop',20.0),events)
            self.assertLess(events.index('db'),events.index('operation-storage'))
            self.assertLess(events.index('db'),events.index('registration-storage'))
            self.assertLess(events.index('registration-storage'),events.index('http-start'))
            self.assertLess(events.index('operation-storage'),events.index('http-start'))
            if clean:self.assertLess(events.index(('http-stop',20.0)),events.index('runtime-stop'))
            else:self.assertNotIn('runtime-stop',events);self.assertNotIn('unlock',events)
class ShutdownDeadlineTests(unittest.TestCase):
    """Catch budget renewal at HTTP/runtime and repeated-signal boundaries."""

    def exercise(self, role, *, total=55, http_spent=20, repeat=False,
                 http_clean=True, runtime_clean=True, startup_delay=None,
                 startup_error=None, waiter_delay=0, cleanup_first_signal=False):
        entry = EntrypointTests().load('worker.py' if role == 'worker' else 'web.py')
        now = [100.]
        events, handlers, receipts = [], {}, []
        bootstrap = SimpleNamespace(mode=role, runtime_dir=Path('/synthetic/not-created'),
                                    prepare_log_environment=lambda: None)

        def interrupt():
            handlers[entry.signal.SIGTERM](entry.signal.SIGTERM, None)

        def install(*_args, **_kwargs):
            if startup_delay is not None:
                try:
                    interrupt()
                finally:
                    now[0] += startup_delay
            if startup_error is not None:
                raise startup_error

        def stop_runtime(*, timeout):
            events.append(('runtime', timeout))
            if cleanup_first_signal:
                interrupt()
            return runtime_clean

        class Server:
            def __init__(self, *_args, **_kwargs):
                pass
            def start(self):
                pass
            def serve(self):
                interrupt()
            def stop(self, *, timeout):
                events.append(('http', timeout))
                now[0] += http_spent
                if repeat:
                    interrupt()
                    interrupt()
                return http_clean

        class Event:
            def set(self):
                pass
            def wait(self, _timeout):
                interrupt()
                now[0] += waiter_delay
                if repeat:
                    interrupt()
                    interrupt()
                return True

        modules = {
            'config': mod('config'),
            'config.env_loader': mod('config.env_loader', ensure_loaded=lambda: None),
            'config.deployment': mod('config.deployment', browser_enabled=lambda: True),
            'core': mod('core'), 'core.runtime': mod('core.runtime'),
            'core.runtime.bootstrap': mod('core.runtime.bootstrap',
                RuntimeBootstrap=SimpleNamespace(from_environment=lambda **_: bootstrap)),
            'core.runtime.assembly': mod('core.runtime.assembly', install=install),
            'core.runtime.process': mod('core.runtime.process',
                execution_owner_lost=unexpected_owner_check,
                start_runtime=lambda *_: None, stop_runtime=stop_runtime),
            'core.runtime.http_server': mod('core.runtime.http_server', HttpServer=Server),
            'core.runtime.role_launcher': mod('core.runtime.role_launcher',
                publish_managed_identity=lambda _: None,
                write_exit_receipt=lambda **value: receipts.append(value)),
            'core.storage': mod('core.storage', postgres=SimpleNamespace(require_ready=lambda: None),
                                registration=SimpleNamespace(init=lambda: None)),
            'core.operation_task_store': mod('core.operation_task_store', init=lambda: None),
            'webui': mod('webui'), 'webui.app': mod('webui.app', create_app=lambda **_: object()),
            'webui.auth': mod('webui.auth', is_generated_code=lambda: False),
        }
        argv = ['worker.py'] if role == 'worker' else ['web.py', '--mode', 'web', '--server', 'waitress']
        if total is not None:
            argv += ['--shutdown-timeout', str(total)]
        error = None
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, modules))
            stack.enter_context(patch.dict(entry.os.environ, {
                'TURB_RUNTIME_MANAGER': 'launchd', 'PYTHON_DOTENV_DISABLED': '1',
                'TURB_ROLE_EXIT_PATH': '/synthetic/unused-receipt'}, clear=True))
            stack.enter_context(patch.object(sys, 'argv', argv))
            stack.enter_context(patch('time.monotonic', side_effect=lambda: now[0]))
            stack.enter_context(patch.object(entry.signal, 'signal',
                side_effect=lambda number, handler: handlers.__setitem__(number, handler)))
            if role == 'web':
                stack.enter_context(patch.object(entry, '_setup_logging'))
                stack.enter_context(patch.object(entry, '_acquire_single_instance', return_value=object()))
                stack.enter_context(patch.object(entry, '_release_single_instance',
                    side_effect=lambda _: events.append(('unlock', None))))
            else:
                stack.enter_context(patch.object(entry.threading, 'Event', Event))
                stack.enter_context(patch.object(entry.logging, 'basicConfig'))
            try:
                entry.main()
            except BaseException as caught:
                error = caught
        return events, receipts, error

    def test_total_budget_rejects_invalid_values_before_env_loading(self):
        for role in ('web', 'worker'):
            for value in ('nan', 'inf', '0', '-1'):
                entry = EntrypointTests().load('worker.py' if role == 'worker' else 'web.py')
                with self.subTest(role=role, value=value), \
                        patch.object(sys, 'argv', [role + '.py', '--shutdown-timeout', value]), \
                        patch.dict(sys.modules, {'config.env_loader': None}):
                    with self.assertRaises(SystemExit) as caught:
                        entry.main()
                    self.assertEqual(caught.exception.code, 2)

    def test_web_http_time_is_deducted_from_one_total_deadline(self):
        events, receipts, error = self.exercise('web')
        self.assertIsNone(error)
        self.assertEqual(events, [('http', 20.), ('runtime', 35.), ('unlock', None)])
        self.assertEqual(receipts, [{'role': 'web', 'clean': True, 'code': 0}])

    def test_short_total_budget_caps_http_and_preserves_incomplete_evidence(self):
        events, receipts, error = self.exercise('web', total=10, http_spent=10, http_clean=False)
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 3)
        self.assertEqual(events, [('http', 10.)])
        self.assertEqual(receipts, [{'role': 'web', 'clean': False, 'code': 3}])

    def test_repeat_web_signals_do_not_renew_deadline_or_skip_cleanup(self):
        events, receipts, error = self.exercise('web', repeat=True)
        self.assertIsNone(error)
        self.assertEqual(events, [('http', 20.), ('runtime', 35.), ('unlock', None)])
        self.assertTrue(receipts[0]['clean'])

    def test_worker_wait_and_repeat_signals_consume_original_deadline(self):
        events, receipts, error = self.exercise('worker', waiter_delay=9, repeat=True)
        self.assertIsNone(error)
        self.assertEqual(events, [('runtime', 46.)])
        self.assertEqual(receipts, [{'role': 'worker', 'clean': True, 'code': 0}])

    def test_startup_signal_elapsed_time_is_not_granted_again(self):
        for role in ('web', 'worker'):
            with self.subTest(role=role):
                events, receipts, error = self.exercise(role, startup_delay=9)
                self.assertIsInstance(error, SystemExit)
                self.assertEqual(error.code, 0)
                self.assertEqual(events[0], ('runtime', 46.))
                self.assertTrue(receipts[0]['clean'])

    def test_exhausted_startup_budget_passes_zero_and_reports_incomplete(self):
        for role in ('web', 'worker'):
            with self.subTest(role=role):
                events, receipts, error = self.exercise(role, startup_delay=60, runtime_clean=False)
                self.assertIsInstance(error, SystemExit)
                self.assertEqual(error.code, 3)
                self.assertEqual(events[0], ('runtime', 0.))
                self.assertFalse(receipts[0]['clean'])

    def test_startup_failure_remains_original_when_cleanup_is_incomplete(self):
        for role in ('web', 'worker'):
            with self.subTest(role=role):
                failure = RuntimeError('synthetic-startup-failure')
                events, receipts, error = self.exercise(role, startup_error=failure, runtime_clean=False)
                self.assertIs(error, failure)
                self.assertEqual(events[0], ('runtime', 55.))
                self.assertEqual(receipts[0], {'role': role, 'clean': False, 'code': 1})

    def test_first_signal_during_exception_cleanup_keeps_original_failure(self):
        for role in ('web', 'worker'):
            with self.subTest(role=role):
                failure = RuntimeError('synthetic-startup-failure')
                events, receipts, error = self.exercise(
                    role, startup_error=failure, runtime_clean=False, cleanup_first_signal=True)
                self.assertIs(error, failure)
                self.assertEqual(events[0], ('runtime', 55.))
                self.assertEqual(receipts[0], {'role': role, 'clean': False, 'code': 1})

    def test_runtime_incomplete_has_nonzero_receipt(self):
        for role in ('web', 'worker'):
            with self.subTest(role=role):
                _events, receipts, error = self.exercise(role, runtime_clean=False)
                self.assertIsInstance(error, SystemExit)
                self.assertEqual(error.code, 3)
                self.assertEqual(receipts[0], {'role': role, 'clean': False, 'code': 3})

    def test_default_web_and_worker_runtime_caps_preserve_compatibility(self):
        for role in ('web', 'worker'):
            with self.subTest(role=role):
                events, _receipts, error = self.exercise(role, total=None)
                self.assertIsNone(error)
                self.assertIn(('runtime', 60.), events)


if __name__=='__main__':unittest.main()
