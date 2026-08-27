from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from core.storage.projection_contract import ProjectionQueue


UTC = timezone.utc


class _BatchOnlyProjector:
    def __init__(self, *, failing: set[str] | None = None) -> None:
        self.failing = set(failing or ())
        self.calls: list[str] = []

    def refresh_batch(self, batch_id: str) -> None:
        self.calls.append(batch_id)
        if batch_id in self.failing:
            self.failing.remove(batch_id)
            raise RuntimeError(f"projection failed for {batch_id}")

    def refresh_all(self) -> None:  # pragma: no cover - contract guard
        raise AssertionError("批次投影不得调用全量刷新")


class ProjectionContractTests(TestCase):
    def test_queue_coalesces_duplicate_requests_and_refreshes_only_named_batches(self):
        queue = ProjectionQueue(retry_delay_seconds=10)
        projector = _BatchOnlyProjector()

        for _ in range(20):
            queue.enqueue("batch-b", reason="duplicate-event")
        queue.enqueue("batch-a")

        self.assertEqual(("batch-a", "batch-b"), queue.pending())
        results = queue.drain(projector)

        self.assertEqual(["batch-a", "batch-b"], projector.calls)
        self.assertEqual(["succeeded", "succeeded"], [item.status for item in results])
        self.assertEqual((), queue.pending())

    def test_successful_batch_can_be_requeued_without_creating_duplicate_entry(self):
        queue = ProjectionQueue()
        projector = _BatchOnlyProjector()

        queue.enqueue("batch-1")
        queue.run_once(projector)
        queue.enqueue("batch-1", reason="later-event")

        self.assertEqual(("batch-1",), queue.pending())
        queue.run_once(projector)
        self.assertEqual(["batch-1", "batch-1"], projector.calls)
        self.assertEqual(2, queue.snapshot("batch-1").attempts)

    def test_request_arriving_while_running_is_not_lost(self):
        queue = ProjectionQueue()
        entered = threading.Event()
        release = threading.Event()
        calls: list[str] = []

        class BlockingProjector:
            def refresh_batch(self, batch_id: str) -> None:
                calls.append(batch_id)
                entered.set()
                self.assert_release()

            @staticmethod
            def assert_release() -> None:
                release.wait(timeout=2)

        worker = threading.Thread(target=queue.run_once, args=(BlockingProjector(),))
        queue.enqueue("batch-race")
        worker.start()
        self.assertTrue(entered.wait(timeout=2))
        queue.enqueue("batch-race", reason="concurrent-event")
        release.set()
        worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(("batch-race",), queue.pending())
        queue.run_once(BlockingProjector())
        self.assertEqual(["batch-race", "batch-race"], calls)

    def test_same_batch_has_single_writer_under_concurrent_consumers(self):
        queue = ProjectionQueue()
        entered = threading.Event()
        release = threading.Event()
        state_lock = threading.Lock()
        active = 0
        max_active = 0
        calls = 0

        class SerializedProjector:
            def refresh_batch(self, _batch_id: str) -> None:
                nonlocal active, max_active, calls
                with state_lock:
                    active += 1
                    calls += 1
                    max_active = max(max_active, active)
                entered.set()
                release.wait(timeout=2)
                with state_lock:
                    active -= 1

        projector = SerializedProjector()
        queue.enqueue("single-writer")
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(queue.run_once, projector)
            self.assertTrue(entered.wait(timeout=2))
            second = executor.submit(queue.run_once, projector)
            self.assertIsNone(second.result(timeout=2))
            release.set()
            self.assertEqual("succeeded", first.result(timeout=2).status)

        self.assertEqual(1, calls)
        self.assertEqual(1, max_active)

    def test_failed_batch_isolated_and_retried_after_backoff(self):
        queue = ProjectionQueue(retry_delay_seconds=5)
        projector = _BatchOnlyProjector(failing={"batch-failed"})
        base = datetime(2026, 8, 27, 1, 0, tzinfo=UTC)
        queue.enqueue("batch-failed", requested_at=base)
        queue.enqueue("batch-ok", requested_at=base)

        failed = queue.run_once(projector, now=base)
        self.assertEqual("failed", failed.status)
        self.assertIn("RuntimeError", failed.last_error or "")
        self.assertEqual(("batch-ok",), queue.pending(now=base))

        succeeded = queue.run_once(projector, now=base)
        self.assertEqual("succeeded", succeeded.status)
        self.assertEqual(("batch-failed",), queue.pending(now=base + timedelta(seconds=5)))
        retried = queue.run_once(projector, now=base + timedelta(seconds=5))
        self.assertEqual("succeeded", retried.status)
        self.assertEqual(["batch-failed", "batch-ok", "batch-failed"], projector.calls)

    def test_multiple_batch_locks_are_acquired_in_stable_order(self):
        queue = ProjectionQueue()
        observed: list[tuple[str, ...]] = []

        with queue.acquire_batches(["batch-z", "batch-a", "batch-z"]):
            observed.append(("batch-a", "batch-z"))
        self.assertEqual([("batch-a", "batch-z")], observed)

        def acquire_reversed() -> str:
            with queue.acquire_batches(["batch-z", "batch-a"]):
                time.sleep(0.01)
            return "done"

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(acquire_reversed) for _ in range(2)]
            self.assertEqual(["done", "done"], [future.result(timeout=2) for future in futures])

    def test_projection_lag_is_explicit_and_serializable(self):
        queue = ProjectionQueue()
        requested = datetime(2026, 8, 27, 2, 0, tzinfo=UTC)
        queue.enqueue("batch-lag", requested_at=requested)

        lag = queue.snapshot("batch-lag", now=requested)
        payload = lag.as_dict(now=requested + timedelta(seconds=2))

        self.assertEqual("queued", payload["status"])
        self.assertEqual(2000, payload["lag_ms"])
        self.assertTrue(payload["delayed"])
        self.assertEqual("batch-lag", payload["batch_id"])


if __name__ == "__main__":
    import unittest

    unittest.main()
