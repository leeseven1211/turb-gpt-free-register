"""协调worker必须完整存活，重入启动能补起缺失线程。"""
from unittest import TestCase
from unittest.mock import Mock, patch

from core.bulk_operations import service


class WorkerLifecycleTests(TestCase):
    def test_partial_workers_are_not_ready_and_start_repairs_missing_thread(self):
        alive = Mock()
        alive.is_alive.return_value = True
        dead = Mock()
        dead.is_alive.return_value = False
        started = []

        def thread(**kwargs):
            item = Mock()
            item.is_alive.side_effect = lambda: item in started
            item.start.side_effect = lambda: started.append(item)
            return item

        with patch.dict(service._THREADS, {"selection": alive, "expand": dead}, clear=True), patch.object(
            service, "_store", return_value=Mock()
        ), patch.object(service.threading, "Thread", side_effect=thread):
            self.assertFalse(service.worker_status()["alive"])
            self.assertTrue(service.start_workers())
            self.assertEqual(len(started), 2)
            self.assertTrue(service.worker_status()["alive"])
            self.assertFalse(service.start_workers())
