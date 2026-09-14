#!/usr/bin/env python3
"""Measure the real isolated account-list and durable-dispatch paths.

This is an opt-in check, never a deployment action.  It creates one generated
``test_`` schema in the explicitly supplied optimization database, seeds at
least one thousand synthetic accounts and two thousand terminal operation
task/run history rows, then measures the real Flask HTTP routes, repository
SQL, shared account executor, and durable task dispatcher. The dispatcher
handler performs no network I/O; its queue
wait, throughput, and concurrency values are measured from monotonic clocks at
actual enqueue, helper-dispatched handler entry (after the durable claim), and
terminal completion points.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
import uuid
from math import ceil
from typing import Any, Callable


def percentile(values: list[float], percentage: float) -> float:
    """Return a nearest-rank percentile without requiring numpy."""
    if not values:
        raise ValueError("percentile 需要至少一个样本")
    if not 0 < percentage <= 100:
        raise ValueError("percentage 必须在 (0, 100] 范围")
    ordered = sorted(float(value) for value in values)
    rank = max(1, ceil((percentage / 100.0) * len(ordered)))
    return ordered[rank - 1]


def _query_counter():
    """Count the SQL statements issued by a measured request window."""
    import psycopg

    original = psycopg.Cursor.execute
    state = {"count": 0}

    def counting_execute(cursor, query, params=None, **kwargs):
        state["count"] += 1
        return original(cursor, query, params, **kwargs)

    psycopg.Cursor.execute = counting_execute
    return original, state


def _restore_query_counter(original) -> None:
    import psycopg

    psycopg.Cursor.execute = original


def _wait_until(
    predicate: Callable[[], bool], *, timeout: float, interval: float = 0.01,
) -> bool:
    """Poll a local/DB observation with a bounded monotonic deadline."""
    deadline = time.perf_counter() + max(0.0, float(timeout))
    while True:
        if predicate():
            return True
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return False
        time.sleep(min(max(0.001, float(interval)), remaining))


def _restore_environment_value(name: str, previous: str | None) -> None:
    if previous is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = previous


def _seed_accounts(*, rows: int, record_store: Any, postgres_store: Any) -> list[int]:
    """Insert real row-level account records and return their database IDs."""
    record_store.init()
    from core.record_store import ACCOUNTS
    from psycopg.rows import dict_row

    account_ids: list[int] = []
    with postgres_store.connect(row_factory=dict_row) as connection:
        for index in range(rows):
            account_ids.append(
                int(
                    record_store.insert_row(
                        ACCOUNTS,
                        {
                            "email": f"performance-{index}@example.test",
                            "email_source": "synthetic",
                            "archived": False,
                            "account_status": "active",
                            "plan_type": "free",
                            "current_plan_type": "free",
                        },
                        conn=connection,
                    )
                )
            )
    return account_ids


def _seed_terminal_operation_history(
    *, rows: int, operation: Any, postgres_store: Any, account_ids: list[int],
) -> dict[str, int]:
    """Bulk-seed terminal task/run history for the real task-center list path.

    The rows are inserted in one PostgreSQL transaction rather than through a
    synthetic Python loop.  They are deliberately terminal and use their own
    source system, so the durable dispatcher will never claim them.  The
    generated history is still the same schema and row model consumed by
    ``operation.list_tasks`` and the ``/api/operations`` route.
    """
    if rows < 2000:
        raise ValueError("任务中心历史压力要求至少 2000 条终态 task/run")
    if not account_ids:
        raise ValueError("任务中心历史压力需要至少一个合成账号")

    batch = operation.create_runtime_batch(
        batch_type="performance_history",
        title="Synthetic terminal task history for list benchmark",
        requested_count=rows,
        trigger="performance_history",
        data={"synthetic": True, "network": "none", "terminal_history": True},
    )
    batch_id = int(batch["id"])
    token = uuid.uuid4().hex
    task_table = postgres_store.qualified("operation_tasks")
    run_table = postgres_store.qualified("operation_runs")
    batch_table = postgres_store.qualified("operation_batches")
    source_system = "performance_history"
    task_prefix = f"{token}:task:%"

    with postgres_store.connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {task_table} (
                task_uuid, source_system, source_id, batch_id, task_type,
                target_type, target_id, account_id, email_snapshot,
                requested_action, status, target_status, current_stage,
                next_actions, trigger, created_at, updated_at, completed_at,
                data
            )
            SELECT
                concat(%s::text, '-task-', series.ordinal::text),
                %s::text,
                concat(%s::text, ':task:', series.ordinal::text),
                %s::bigint,
                'performance.history',
                'account',
                series.account_id,
                series.account_id,
                concat('performance-history-', series.ordinal::text, '@example.test'),
                'performance.history',
                'success',
                'completed',
                'complete',
                '[]'::jsonb,
                'performance_history',
                series.created_at,
                series.created_at,
                series.created_at,
                jsonb_build_object(
                    'synthetic', true,
                    'network', 'none',
                    'terminal_history', true,
                    'ordinal', series.ordinal
                )
            FROM (
                SELECT
                    ordinal,
                    (%s::bigint[])[
                        mod(ordinal, %s::bigint)::integer + 1
                    ] AS account_id,
                    now() - (ordinal * interval '1 second') AS created_at
                FROM generate_series(0, %s::bigint - 1) AS generated(ordinal)
            ) AS series
            """,
            (
                token,
                source_system,
                token,
                batch_id,
                account_ids,
                len(account_ids),
                rows,
            ),
        )
        cursor.execute(
            f"""
            INSERT INTO {run_table} (
                run_uuid, task_id, run_no, source_system, source_id, status,
                batch_id, account_id, resource_family, cancellation_token,
                progress_stage, progress_steps, started_at, completed_at,
                duration_ms, result_summary, created_at, data
            )
            SELECT
                concat(%s::text, '-run-', task.id::text),
                task.id,
                1,
                %s::text,
                concat(%s::text, ':run:', task.id::text),
                'success',
                task.batch_id,
                task.account_id,
                'openai_interactive',
                concat(%s::text, '-cancel-', task.id::text),
                'complete',
                '{{}}'::jsonb,
                task.created_at,
                task.completed_at,
                1,
                jsonb_build_object(
                    'synthetic', true,
                    'network', 'none',
                    'terminal_history', true
                ),
                task.created_at,
                task.data
            FROM {task_table} AS task
            WHERE task.batch_id = %s::bigint
              AND task.source_system = %s::text
              AND task.source_id LIKE %s::text
            """,
            (token, source_system, token, token, batch_id, source_system, task_prefix),
        )
        cursor.execute(
            f"""
            UPDATE {task_table} AS task
            SET last_run_id = run.id
            FROM {run_table} AS run
            WHERE run.task_id = task.id
              AND run.source_system = %s::text
              AND run.source_id LIKE %s::text
              AND task.batch_id = %s::bigint
            """,
            (source_system, f"{token}:run:%", batch_id),
        )
        cursor.execute(
            f"""
            UPDATE {batch_table}
            SET status = 'success',
                queued_count = 0,
                running_count = 0,
                success_count = %s::integer,
                completed_at = now(),
                data = data || %s::jsonb
            WHERE id = %s::bigint
            """,
            (
                rows,
                json.dumps(
                    {
                        "synthetic": True,
                        "network": "none",
                        "terminal_history": True,
                    },
                    separators=(",", ":"),
                ),
                batch_id,
            ),
        )
        cursor.execute(
            f"""
            SELECT
                (SELECT COUNT(*) FROM {task_table}
                 WHERE batch_id = %s::bigint AND source_system = %s::text
                   AND source_id LIKE %s::text) AS task_count,
                (SELECT COUNT(*) FROM {run_table}
                 WHERE batch_id = %s::bigint AND source_system = %s::text
                   AND source_id LIKE %s::text) AS run_count,
                (SELECT COUNT(*) FROM {task_table}
                 WHERE batch_id = %s::bigint AND source_system = %s::text
                   AND source_id LIKE %s::text AND last_run_id IS NOT NULL) AS linked_count
            """,
            (
                batch_id, source_system, task_prefix,
                batch_id, source_system, f"{token}:run:%",
                batch_id, source_system, task_prefix,
            ),
        )
        counts = cursor.fetchone()

    task_count, run_count, linked_count = (int(value) for value in counts)
    expected = {"tasks": rows, "runs": rows, "linked_runs": rows}
    actual = {"tasks": task_count, "runs": run_count, "linked_runs": linked_count}
    if actual != expected:
        raise RuntimeError(f"合成任务历史 bulk seed 数量异常: expected={expected} actual={actual}")
    return {"batch_id": batch_id, **actual}


def _measure_account_list(*, rows: int, samples: int) -> dict[str, Any]:
    """Measure the actual authenticated HTTP route backed by admin_repository."""
    from webui.app import create_app

    path = "/api/accounts?paged=1&page_size=50"
    headers = {"X-Auth-Code": "performance-check"}
    app = create_app(auth_code="performance-check")
    client = app.test_client()

    # Warm schema/pool/configuration work is deliberately outside the measured
    # window. Every measured sample still traverses the same HTTP route.
    warmup = client.get(path, headers=headers)
    if warmup.status_code != 200:
        raise RuntimeError(f"账号列表 HTTP warmup 失败: status={warmup.status_code}")
    warmup_payload = warmup.get_json()
    if not isinstance(warmup_payload, dict) or int(warmup_payload.get("total") or 0) != rows:
        raise RuntimeError("账号列表 HTTP warmup 未返回完整合成账号总数")

    latencies: list[float] = []
    query_counts: list[int] = []
    original_execute, counter = _query_counter()
    try:
        for _ in range(samples):
            counter["count"] = 0
            started = time.perf_counter()
            response = client.get(path, headers=headers)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if response.status_code != 200:
                raise RuntimeError(f"账号列表 HTTP 请求失败: status={response.status_code}")
            payload = response.get_json()
            if not isinstance(payload, dict):
                raise RuntimeError("账号列表 HTTP 响应不是分页 object")
            if payload.get("ok") is not True or int(payload.get("total") or 0) != rows:
                raise RuntimeError("账号列表 HTTP 响应总数异常")
            items = payload.get("items")
            if not isinstance(items, list) or len(items) != 50:
                raise RuntimeError("账号列表 HTTP 分页大小异常")
            latencies.append(elapsed_ms)
            query_counts.append(int(counter["count"]))
    finally:
        _restore_query_counter(original_execute)

    return {
        "path": path,
        "transport": "Flask test_client HTTP route",
        "repository": "core.admin_repository.list_accounts",
        "rows": rows,
        "samples": samples,
        "query_count": {
            "per_request": query_counts,
            "p95": percentile([float(value) for value in query_counts], 95),
            "max": max(query_counts),
        },
        "latency_ms": {
            "p95": round(percentile(latencies, 95), 3),
            "max": round(max(latencies), 3),
        },
    }


def _measure_operation_list(*, rows: int, samples: int) -> dict[str, Any]:
    """Measure the real task-center route over terminal task/run history."""
    from webui.app import create_app

    path = "/api/operations?page=1&page_size=50"
    headers = {"X-Auth-Code": "performance-check"}
    app = create_app(auth_code="performance-check")
    client = app.test_client()

    warmup = client.get(path, headers=headers)
    if warmup.status_code != 200:
        raise RuntimeError(f"任务中心 HTTP warmup 失败: status={warmup.status_code}")
    warmup_payload = warmup.get_json()
    if not isinstance(warmup_payload, dict) or int(warmup_payload.get("total") or 0) != rows:
        raise RuntimeError("任务中心 HTTP warmup 未返回完整终态历史总数")

    latencies: list[float] = []
    query_counts: list[int] = []
    original_execute, counter = _query_counter()
    try:
        for _ in range(samples):
            counter["count"] = 0
            started = time.perf_counter()
            response = client.get(path, headers=headers)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if response.status_code != 200:
                raise RuntimeError(f"任务中心 HTTP 请求失败: status={response.status_code}")
            payload = response.get_json()
            if not isinstance(payload, dict):
                raise RuntimeError("任务中心 HTTP 响应不是分页 object")
            if payload.get("ok") is not True or int(payload.get("total") or 0) != rows:
                raise RuntimeError("任务中心 HTTP 响应总数异常")
            items = payload.get("items")
            batches = payload.get("batches")
            if not isinstance(items, list) or len(items) != 50:
                raise RuntimeError("任务中心 HTTP 分页大小异常")
            if not isinstance(batches, list) or not batches:
                raise RuntimeError("任务中心 HTTP 未返回合成历史批次")
            latencies.append(elapsed_ms)
            query_counts.append(int(counter["count"]))
    finally:
        _restore_query_counter(original_execute)

    return {
        "path": path,
        "transport": "Flask test_client HTTP route",
        "repository": "core.storage.operation.list_tasks + list_batches",
        "rows": rows,
        "samples": samples,
        "query_count": {
            "per_request": query_counts,
            "p95": percentile([float(value) for value in query_counts], 95),
            "max": max(query_counts),
        },
        "latency_ms": {
            "p95": round(percentile(latencies, 95), 3),
            "max": round(max(latencies), 3),
        },
    }


def _create_native_runs(
    *,
    task_gateway: Any,
    batch_id: int,
    account_ids: list[int],
    task_type: str,
    phase: str,
    count: int,
    token: str,
    enqueue_times: dict[int, float],
    phase_by_run: dict[int, str],
) -> list[int]:
    """Persist native task/run rows through the durable submission helper."""
    run_ids: list[int] = []
    for index in range(count):
        source_id = f"performance:{token}:{phase}:{index}"
        submission = task_gateway.submit_durable_operation(
            task_type=task_type,
            account_id=account_ids[index % len(account_ids)],
            email=f"performance-{index % len(account_ids)}@example.test",
            trigger=f"performance_{phase}",
            batch_id=batch_id,
            batch_ordinal=index + 1,
            data={
                "synthetic": True,
                "network": "none",
                "phase": phase,
                "ordinal": index,
            },
            source_id=source_id,
            idempotency_key=source_id,
            dispatch=False,
        )
        if not isinstance(submission, dict) or not submission.get("accepted"):
            raise RuntimeError(f"合成 {phase} 任务没有创建 durable run")
        run_id = int(submission.get("run_id") or 0)
        if run_id <= 0:
            raise RuntimeError(f"合成 {phase} 任务没有返回 durable run id")
        # The timestamp is taken immediately after the committed command
        # returns, before any next enqueue operation. It is not generated from
        # an arithmetic sequence or copied from a database timestamp.
        enqueue_times[run_id] = time.perf_counter()
        phase_by_run[run_id] = phase
        run_ids.append(run_id)
    return run_ids


def _durable_statuses(operation: Any, run_ids: list[int]) -> dict[int, str]:
    statuses: dict[int, str] = {}
    for run_id in run_ids:
        run = operation.get_run(run_id)
        statuses[run_id] = str((run or {}).get("status") or "missing")
    return statuses


def _wait_for_success(operation: Any, run_ids: list[int], *, timeout: float) -> dict[int, str]:
    latest: dict[int, str] = {}

    def all_success() -> bool:
        nonlocal latest
        latest = _durable_statuses(operation, run_ids)
        return all(status == "success" for status in latest.values())

    if not _wait_until(all_success, timeout=timeout, interval=0.02):
        latest = _durable_statuses(operation, run_ids)
        raise RuntimeError(f"durable synthetic runs 未全部成功: {latest}")
    return latest


def _run_dispatch_benchmark(
    *,
    operation: Any,
    task_gateway: Any,
    executor: Any,
    account_ids: list[int],
    workers: int,
    queue_tasks: int,
) -> dict[str, Any]:
    """Exercise congestion and dispatcher restart with real durable rows."""
    from core.operations.task_gateway import OperationResult

    task_type = f"performance.synthetic.{uuid.uuid4().hex}"
    token = uuid.uuid4().hex
    main_batch = operation.create_runtime_batch(
        batch_type="performance_synthetic",
        title="Synthetic no-network dispatcher benchmark",
        requested_count=queue_tasks,
        trigger="performance_check",
        data={"synthetic": True, "network": "none"},
    )
    recovery_count = max(4, min(queue_tasks, workers * 2))
    recovery_batch = operation.create_runtime_batch(
        batch_type="performance_synthetic_recovery",
        title="Synthetic dispatcher restart recovery",
        requested_count=recovery_count,
        trigger="performance_check_restart",
        data={"synthetic": True, "network": "none", "restart": True},
    )

    enqueue_times: dict[int, float] = {}
    handler_entered: dict[int, float] = {}
    completion_times: dict[int, float] = {}
    phase_by_run: dict[int, str] = {}
    errors: list[str] = []
    main_ids = _create_native_runs(
        task_gateway=task_gateway,
        batch_id=int(main_batch["id"]),
        account_ids=account_ids,
        task_type=task_type,
        phase="main",
        count=queue_tasks,
        token=token,
        enqueue_times=enqueue_times,
        phase_by_run=phase_by_run,
    )
    main_set = set(main_ids)
    recovery_ids: list[int] = []
    release_gate = threading.Event()
    state_lock = threading.RLock()
    main_done = threading.Event()
    recovery_done = threading.Event()
    active = 0
    max_active = 0
    phase_completed = {"main": 0, "recovery": 0}
    phase_targets = {"main": len(main_ids), "recovery": 0}

    def synthetic_operation_handler(context: Any) -> OperationResult:
        """Run a no-network body after the durable helper claims the run."""
        nonlocal active, max_active
        run_id = int(context.run_id)
        # register_operation_handler invokes this callback only after its
        # shared executor wrapper and atomic PostgreSQL claim have succeeded.
        entered_at = time.perf_counter()
        phase = phase_by_run.get(run_id, "unknown")
        with state_lock:
            handler_entered[run_id] = entered_at
            active += 1
            max_active = max(max_active, active)
        try:
            context.report(
                stage="preflight",
                message="synthetic no-network handler started",
                detail={"synthetic": True, "network": "none", "phase": phase},
            )
            if not release_gate.wait(timeout=30.0):
                raise TimeoutError("synthetic congestion gate timed out")
            # Keep several real executor handlers overlapped long enough for
            # the observed maximum concurrency to be meaningful.
            time.sleep(0.05)
            result = OperationResult.success(
                {"synthetic": True, "network": "none", "phase": phase},
                message="synthetic no-network handler complete",
            )
        except Exception as exc:
            with state_lock:
                errors.append(f"run {run_id}: {type(exc).__name__}: {exc}")
            result = OperationResult.failed(
                "synthetic no-network handler failed",
                {"synthetic": True, "network": "none", "phase": phase},
            )

        # Finish inside the handler so completion_times is recorded only after
        # the durable terminal write has committed, not merely when the body
        # returns to the dispatcher wrapper.
        try:
            context.finish(result)
            with state_lock:
                completion_times[run_id] = time.perf_counter()
                phase_completed[phase] = phase_completed.get(phase, 0) + 1
                if phase == "main" and phase_completed[phase] >= phase_targets[phase]:
                    main_done.set()
                if phase == "recovery" and phase_completed[phase] >= phase_targets[phase]:
                    recovery_done.set()
            return result
        finally:
            with state_lock:
                active -= 1

    if task_gateway.dispatcher_status().get("alive"):
        raise RuntimeError("性能检查发现已有 durable dispatcher；拒绝接管运行中 worker")
    if int(executor.status().get("accepted") or 0) != 0:
        raise RuntimeError("性能检查发现 shared executor 已有未完成任务")

    dispatcher_started = False
    handler_registered = False
    try:
        task_gateway.register_operation_handler(
            task_type,
            synthetic_operation_handler,
            source_systems=("native_operations",),
        )
        handler_registered = True
        dispatcher_started = bool(
            task_gateway.start_dispatcher(
                interval_seconds=0.01,
                batch_size=max(queue_tasks, workers),
            )
        )
        if not dispatcher_started:
            raise RuntimeError("性能检查未能启动独占 durable dispatcher")
        task_gateway.notify_dispatch()

        expected_active = min(workers, len(main_ids))
        congestion_snapshot: dict[str, Any] = {}

        def observe_congestion() -> bool:
            queued = operation.list_queued_runs(limit=max(100, queue_tasks * 2))
            queued_ids = {int(row["id"]) for row in queued if row.get("id") is not None}
            with state_lock:
                active_now = active
                entered_now = len(set(handler_entered) & main_set)
            if active_now >= expected_active and bool(queued_ids & main_set):
                congestion_snapshot.update(
                    {
                        "observed": True,
                        "active_handlers": active_now,
                        "handler_entries_after_durable_claim": entered_now,
                        "queued_backlog": len(queued_ids & main_set),
                        "executor": executor.status(),
                    }
                )
                return True
            return False

        if not _wait_until(observe_congestion, timeout=15.0, interval=0.02):
            queued = operation.list_queued_runs(limit=max(100, queue_tasks * 2))
            with state_lock:
                congestion_snapshot = {
                    "observed": False,
                    "active_handlers": active,
                    "handler_entries_after_durable_claim": len(set(handler_entered) & main_set),
                    "queued_backlog": len(
                        {int(row["id"]) for row in queued if row.get("id") is not None} & main_set
                    ),
                    "executor": executor.status(),
                }
            raise RuntimeError(f"没有观察到真实 durable 队列拥堵: {congestion_snapshot}")

        # Release only after all available executor slots and a durable queued
        # backlog were observed. The wait values below therefore include the
        # actual congestion interval rather than a deterministic sample list.
        release_gate.set()
        if not main_done.wait(timeout=30.0):
            raise RuntimeError("synthetic main dispatcher runs 未在期限内完成")
        main_statuses = _wait_for_success(operation, main_ids, timeout=10.0)
        if errors:
            raise RuntimeError(f"synthetic main handler errors: {errors}")

        if not _wait_until(
            lambda: int(executor.status().get("accepted") or 0) == 0,
            timeout=10.0,
            interval=0.02,
        ):
            raise RuntimeError(f"shared executor 未在主负载后归零: {executor.status()}")
        task_gateway.unregister_operation_handler(task_type)
        handler_registered = False
        if not task_gateway.stop_dispatcher(timeout=5.0):
            raise RuntimeError("主负载后的 durable dispatcher 未停止")
        dispatcher_started = False

        # Queue the recovery rows while the scanner is stopped. They are
        # durable PostgreSQL rows, so restart recovery is verified by observing
        # those same IDs transition to success after a new scanner thread.
        recovery_ids = _create_native_runs(
            task_gateway=task_gateway,
            batch_id=int(recovery_batch["id"]),
            account_ids=account_ids,
            task_type=task_type,
            phase="recovery",
            count=recovery_count,
            token=token,
            enqueue_times=enqueue_times,
            phase_by_run=phase_by_run,
        )
        phase_targets["recovery"] = len(recovery_ids)
        recovery_set = set(recovery_ids)
        queued_while_stopped = {
            int(row["id"])
            for row in operation.list_queued_runs(limit=max(100, recovery_count * 2))
            if row.get("id") is not None
        } & recovery_set
        if queued_while_stopped != recovery_set:
            raise RuntimeError(
                "dispatcher 停止期间 durable recovery rows 不完整: "
                f"{len(queued_while_stopped)}/{len(recovery_set)}"
            )

        task_gateway.register_operation_handler(
            task_type,
            synthetic_operation_handler,
            source_systems=("native_operations",),
        )
        handler_registered = True
        restarted = bool(
            task_gateway.start_dispatcher(
                interval_seconds=0.01,
                batch_size=max(recovery_count, workers),
            )
        )
        if not restarted:
            raise RuntimeError("durable dispatcher recovery restart 未启动新 scanner")
        dispatcher_started = True
        task_gateway.notify_dispatch()
        if not recovery_done.wait(timeout=30.0):
            raise RuntimeError("synthetic recovery runs 未在期限内完成")
        recovery_statuses = _wait_for_success(operation, recovery_ids, timeout=10.0)
        if errors:
            raise RuntimeError(f"synthetic recovery handler errors: {errors}")

        if not task_gateway.stop_dispatcher(timeout=5.0):
            raise RuntimeError("recovery 后的 durable dispatcher 未停止")
        dispatcher_started = False
        task_gateway.unregister_operation_handler(task_type)
        handler_registered = False

        def phase_metrics(run_ids: list[int]) -> dict[str, Any]:
            missing = [run_id for run_id in run_ids if run_id not in completion_times]
            if missing:
                raise RuntimeError(f"合成 runs 缺少实际完成计时: {missing[:5]}")
            waits = [
                (handler_entered[run_id] - enqueue_times[run_id]) * 1000.0
                for run_id in run_ids
            ]
            starts = [handler_entered[run_id] for run_id in run_ids]
            completions = [completion_times[run_id] for run_id in run_ids]
            enqueue_span = max(completions) - min(enqueue_times[run_id] for run_id in run_ids)
            service_span = max(completions) - min(starts)
            return {
                "runs": len(run_ids),
                "queue_wait_ms": {
                    "p95": round(percentile(waits, 95), 3),
                    "max": round(max(waits), 3),
                    "source": "measured_monotonic_enqueue_to_executor_handler_entry",
                },
                "elapsed_ms": {
                    "enqueue_to_last_completion": round(enqueue_span * 1000.0, 3),
                    "first_handler_to_last_completion": round(service_span * 1000.0, 3),
                },
                "throughput_runs_per_second": round(
                    len(run_ids) / service_span if service_span > 0 else 0.0,
                    3,
                ),
            }

        main_metrics = phase_metrics(main_ids)
        recovery_metrics = phase_metrics(recovery_ids)
        with state_lock:
            observed_max_active = max_active
            observed_errors = list(errors)
        return {
            "load_type": "synthetic_no_network",
            "handler": "shared_executor + durable task_gateway",
            "network_calls": 0,
            "workers": workers,
            "concurrency": {
                "configured_limit": workers,
                "max_active_observed": observed_max_active,
                "within_limit": observed_max_active <= workers,
            },
            "congestion": congestion_snapshot,
            "main": {"statuses": main_statuses, **main_metrics},
            "restart_recovery": {
                "queued_while_dispatcher_stopped": len(queued_while_stopped),
                "queued_expected": len(recovery_set),
                "dispatcher_restarted": True,
                "all_completed": all(status == "success" for status in recovery_statuses.values()),
                "statuses": recovery_statuses,
                **recovery_metrics,
            },
            "errors": observed_errors,
        }
    finally:
        release_gate.set()
        if handler_registered:
            task_gateway.unregister_operation_handler(task_type)
        if dispatcher_started:
            task_gateway.stop_dispatcher(timeout=5.0)


def run_benchmark(
    *,
    rows: int = 1000,
    samples: int = 20,
    workers: int = 3,
    queue_tasks: int = 32,
    history_rows: int = 2000,
) -> dict[str, Any]:
    """Seed and measure isolated list and durable dispatcher workloads."""
    if rows < 1000:
        raise ValueError("性能门槛要求至少 1000 条合成账号数据")
    if history_rows < 2000:
        raise ValueError("性能门槛要求至少 2000 条终态任务/运行历史")
    if samples < 5:
        raise ValueError("性能样本至少需要 5 次")
    if not 1 <= workers <= 16:
        raise ValueError("workers 必须在 1 到 16 之间")
    if queue_tasks < max(16, workers * 4):
        raise ValueError("queue_tasks 至少为 16 且需达到 workers 的 4 倍以形成拥堵")

    database_url = str(os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL 未配置；性能验证不得回退到文件或生产库")
    from tools.test_isolated import TestEnvironmentError, validate_test_database_url

    try:
        validate_test_database_url(database_url)
    except TestEnvironmentError as exc:
        raise RuntimeError(f"性能验证拒绝不安全的测试数据库: {exc}") from exc

    previous_schema = os.environ.get("TURB_DB_SCHEMA")
    previous_workers = os.environ.get("ACCOUNT_BATCH_WORKERS")
    previous_operation_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
    previous_account_task_schema = os.environ.get("ACCOUNT_TASK_DB_SCHEMA")
    schema = f"test_perf_{uuid.uuid4().hex[:12]}"
    os.environ["TURB_DB_SCHEMA"] = schema
    os.environ["ACCOUNT_BATCH_WORKERS"] = str(workers)
    # operation.py has a dedicated override; force it to the same generated
    # schema so both list and dispatcher rows are cleaned up together even if
    # the caller inherited a different operation schema.
    os.environ["OPERATION_TASK_DB_SCHEMA"] = schema
    # The compatibility task store reads this value at module import time;
    # keep its tables beside the operation tables rather than public or an
    # inherited caller schema.
    os.environ["ACCOUNT_TASK_DB_SCHEMA"] = schema

    postgres_store = None
    task_gateway = None
    executor = None
    try:
        # These imports intentionally happen after the generated schema and
        # worker setting are installed; config/database modules cache both.
        from core import postgres_store as imported_postgres_store
        from core import record_store
        from core.account_operation_executor import executor as imported_executor
        from core.operations import task_gateway as imported_task_gateway
        from core.storage import operation

        postgres_store = imported_postgres_store
        task_gateway = imported_task_gateway
        executor = imported_executor
        account_ids = _seed_accounts(
            rows=rows,
            record_store=record_store,
            postgres_store=postgres_store,
        )
        operation.init()
        effective_workers = int(executor.status().get("budget") or workers)
        if effective_workers != workers:
            raise RuntimeError(
                f"shared executor worker 配置未生效: requested={workers} effective={effective_workers}"
            )
        history_report = _seed_terminal_operation_history(
            rows=history_rows,
            operation=operation,
            postgres_store=postgres_store,
            account_ids=account_ids,
        )
        account_list_report = _measure_account_list(rows=rows, samples=samples)
        operation_list_report = _measure_operation_list(rows=history_rows, samples=samples)
        dispatcher_report = _run_dispatch_benchmark(
            operation=operation,
            task_gateway=task_gateway,
            executor=executor,
            account_ids=account_ids,
            workers=effective_workers,
            queue_tasks=queue_tasks,
        )

        thresholds = {
            "account_list_max_query_count": 3,
            "account_list_latency_p95_ms": 250.0,
            "operation_list_max_query_count": 10,
            "operation_list_latency_p95_ms": 250.0,
            "dispatcher_concurrency_must_not_exceed_workers": True,
            "dispatcher_congestion_must_be_observed": True,
            "restart_recovery_must_complete": True,
        }
        passes_thresholds = bool(
            account_list_report["query_count"]["max"]
            <= thresholds["account_list_max_query_count"]
            and account_list_report["latency_ms"]["p95"]
            <= thresholds["account_list_latency_p95_ms"]
            and operation_list_report["query_count"]["max"]
            <= thresholds["operation_list_max_query_count"]
            and operation_list_report["latency_ms"]["p95"]
            <= thresholds["operation_list_latency_p95_ms"]
            and dispatcher_report["concurrency"]["within_limit"]
            and dispatcher_report["congestion"].get("observed") is True
            and dispatcher_report["restart_recovery"].get("all_completed") is True
            and not dispatcher_report["errors"]
        )
        return {
            "ok": True,
            "rows": rows,
            "samples": samples,
            "task_rows": queue_tasks,
            "history_rows": history_report,
            "database_scope": "generated test_ schema in explicit optimization database",
            "list_benchmark": {
                "history_seeded_before_measurement": True,
                "accounts": account_list_report,
                "operations": operation_list_report,
            },
            "dispatcher_benchmark": dispatcher_report,
            "thresholds": thresholds,
            "passes_thresholds": passes_thresholds,
            "comparison_note": (
                "queue wait and throughput are measured observations from this synthetic "
                "no-network load; no generated baseline is used"
            ),
        }
    finally:
        # Cleanup can fail independently (for example a worker shutdown or a
        # lost DB connection). Environment restoration must still happen on
        # every path, including those cleanup failures.
        try:
            try:
                if executor is not None:
                    executor.shutdown(wait=True)
            finally:
                if postgres_store is not None:
                    try:
                        with postgres_store.connect() as connection, connection.cursor() as cursor:
                            cursor.execute(
                                f"DROP SCHEMA IF EXISTS {postgres_store.quote_identifier(schema)} CASCADE"
                            )
                    finally:
                        postgres_store.close_pools()
        finally:
            try:
                _restore_environment_value("TURB_DB_SCHEMA", previous_schema)
            finally:
                try:
                    _restore_environment_value("ACCOUNT_BATCH_WORKERS", previous_workers)
                finally:
                    try:
                        _restore_environment_value(
                            "OPERATION_TASK_DB_SCHEMA", previous_operation_schema
                        )
                    finally:
                        _restore_environment_value(
                            "ACCOUNT_TASK_DB_SCHEMA", previous_account_task_schema
                        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="千级合成账号、真实 HTTP 列表与 durable dispatcher 性能检查"
    )
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--queue-tasks", type=int, default=32)
    parser.add_argument("--history-rows", type=int, default=2000)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = run_benchmark(
            rows=args.rows,
            samples=args.samples,
            workers=args.workers,
            queue_tasks=args.queue_tasks,
            history_rows=args.history_rows,
        )
    except Exception as exc:
        print(f"performance check failed: {type(exc).__name__}: {exc}")
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passes_thresholds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
