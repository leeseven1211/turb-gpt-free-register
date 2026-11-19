import threading
import unittest
from core.operations.executor import AccountOperationExecutor

class ExecutorCloseTests(unittest.TestCase):
    def test_active_work_keeps_carrier_then_idle_close_joins_real_threads(self):
        executor=AccountOperationExecutor(lambda:1)
        entered,release=threading.Event(),threading.Event()
        self.addCleanup(release.set)
        future=executor.try_submit(lambda:(entered.set(),release.wait(2)))
        self.assertTrue(entered.wait(1));self.assertFalse(executor.close_runtime(.01))
        release.set();future.result(timeout=1)
        threads=tuple(executor._executor._threads)
        self.assertTrue(executor.close_runtime(1));self.assertTrue(all(not t.is_alive() for t in threads))
        with self.assertRaisesRegex(RuntimeError,'runtime_executor_closed'):executor.try_submit(lambda:None)
        self.assertTrue(executor.close_runtime(.1))
