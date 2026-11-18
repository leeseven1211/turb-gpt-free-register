"""Real PostgreSQL concurrency checks; run only in an isolated test schema."""
from concurrent.futures import ThreadPoolExecutor
import threading

from core.runtime import scheduler_state
from core.storage import postgres
from tests.support_pg import PostgresTestCase


class SchedulerAtomicStateTests(PostgresTestCase):
    def _payload(self):
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT payload FROM {postgres.qualified('app_collections')} WHERE name = %s",
                ("scheduler_state",),
            )
            row = cur.fetchone()
            return row[0] if row else {}

    def test_concurrent_marks_for_same_task_preserve_every_increment(self):
        scheduler_state.mark_ran("shared")
        barrier = threading.Barrier(4)
        def marks():
            barrier.wait(timeout=5)
            for _ in range(10):
                scheduler_state.mark_ran("shared")
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = [executor.submit(marks) for _ in range(4)]
            for result in results:
                result.result(timeout=30)
        self.assertEqual(self._payload()["shared"]["run_count"], 41)

    def test_cross_task_writes_preserve_all_existing_entries(self):
        postgres.save_collection("scheduler_state", {
            "legacy": {"last_run_at": "2026-01-01T00:00:00", "run_count": 8, "extra": "keep"},
        })
        barrier = threading.Barrier(4)
        def marks(task):
            barrier.wait(timeout=5)
            for _ in range(8):
                scheduler_state.mark_ran(task)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = [executor.submit(marks, f"task-{index}") for index in range(4)]
            for result in results:
                result.result(timeout=30)
        state = self._payload()
        self.assertEqual(state["legacy"], {
            "last_run_at": "2026-01-01T00:00:00", "run_count": 8, "extra": "keep",
        })
        for index in range(4):
            self.assertEqual(state[f"task-{index}"]["run_count"], 8)

    def test_concurrent_reset_and_other_task_marks_do_not_lose_updates(self):
        scheduler_state.mark_ran("reset")
        barrier = threading.Barrier(2)
        def resets():
            barrier.wait(timeout=5)
            for _ in range(12):
                scheduler_state.reset("reset")
        def marks():
            barrier.wait(timeout=5)
            for _ in range(12):
                scheduler_state.mark_ran("keep")
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [executor.submit(resets), executor.submit(marks)]
            for result in results:
                result.result(timeout=30)
        state = self._payload()
        self.assertNotIn("reset", state)
        self.assertEqual(state["keep"]["run_count"], 12)
