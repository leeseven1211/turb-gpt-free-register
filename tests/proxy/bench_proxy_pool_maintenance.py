"""隔离库合成代理维护基准，显式运行，不接触业务资源或供应商。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import statistics
import threading
import time
from unittest.mock import patch

import psycopg

from core.storage import postgres as postgres_store
from core.proxy import pool as proxy_pool
from core.storage.proxy import pool as store
from core.storage import records as record_store
from tests.support_pg import PostgresTestCase


class ProxyMaintenanceBenchmark(PostgresTestCase):
    def test_synthetic_500_active_and_40000_terminal(self):
        record_store.init()
        now, old, expires = store._stamp(), store._stamp(-600), store._stamp(3600)
        history_old = store._stamp(-8 * 24 * 60 * 60)
        with record_store.transaction() as conn, conn.cursor() as cur:
            cur.execute(f"INSERT INTO {postgres_store.qualified(store.LEASES.name)} "
                        "(lease_id, provider, endpoint, proxy_url, state, acquired_at, expires_at, created_at, updated_at) "
                        "SELECT 'anchor-' || n, '1024proxy', 'bench-' || n || ':80', 'http://bench-' || n || ':80', "
                        "'leased', %s, %s, %s, %s FROM generate_series(1, 500) n", (now, expires, now, now))
            cur.execute(f"INSERT INTO {postgres_store.qualified(store.RESOURCES.name)} "
                        "(resource_id, profile_key, provider, state, anchor_lease_id, checked_at, expires_at, "
                        "last_used_at, created_at, updated_at, data) SELECT 'active-' || n, 'bench', '1024proxy', "
                        "CASE WHEN n <= 409 THEN 'cooldown' ELSE 'ready' END, 'anchor-' || n, %s, %s, %s, %s, %s, "
                        "jsonb_build_object('cooldown_until', %s::text) FROM generate_series(1, 500) n",
                        (now, expires, old, now, now, expires))
            cur.execute(f"INSERT INTO {postgres_store.qualified(store.RESOURCES.name)} "
                        "(resource_id, profile_key, provider, state, expires_at, last_used_at, created_at, updated_at) "
                        "SELECT 'terminal-' || n, 'old', '1024proxy', (ARRAY['failed','retired','expired'])[1 + n %% 3], "
                        "%s, %s, %s, %s FROM generate_series(1, 40000) n", (old, old, old, old))
            cur.execute(f"ANALYZE {postgres_store.qualified(store.RESOURCES.name)}")
            cur.execute(f"ANALYZE {postgres_store.qualified(store.LEASES.name)}")
            cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT * FROM "
                        f"{postgres_store.qualified(store.RESOURCES.name)} "
                        "WHERE state IN ('failed','retired','expired') AND updated_at <= %s "
                        "ORDER BY updated_at, id LIMIT 200", (history_old,))
            plan = cur.fetchone()["QUERY PLAN"][0]

            def scans(node):
                rows = [{key: node[key] for key in ("Node Type", "Index Name", "Actual Rows", "Rows Removed by Filter")
                         if key in node}] if "Scan" in node["Node Type"] else []
                return rows + [item for child in node.get("Plans", []) for item in scans(child)]

            print("历史清理执行计划 " + json.dumps({"execution_ms": plan["Execution Time"],
                                                 "scans": scans(plan["Plan"])}, ensure_ascii=False))
        policy = {"max_age": 3600, "max_idle": 300, "min_ready": 91, "min_ttl": 300,
                  "max_size": 500, "workers": 20}
        original_execute = psycopg.Cursor.execute
        original_transaction = record_store.transaction
        for workers in (2, 10, 20):
            metrics = {"workers": workers, "sql": 0, "maintenance_sql": 0, "maintenance_calls": 0,
                       "connection_wait_ms": [], "capacity_wait_ms": [], "capacity_hold_ms": []}
            metrics_lock = threading.Lock()
            tx_state = threading.local()

            def execute(cursor, query, params=None, **kwargs):
                start = time.perf_counter()
                result = original_execute(cursor, query, params, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                with metrics_lock:
                    metrics["sql"] += 1
                    if getattr(tx_state, "maintenance_worker", False):
                        metrics["maintenance_sql"] += 1
                    if params and params[0] == "proxy-pool-capacity" and "advisory" in str(query):
                        metrics["capacity_wait_ms"].append(elapsed)
                        tx_state.capacity_since = time.perf_counter()
                return result

            @contextmanager
            def transaction():
                start = time.perf_counter()
                with original_transaction() as conn:
                    with metrics_lock:
                        metrics["connection_wait_ms"].append((time.perf_counter() - start) * 1000)
                    tx_state.capacity_since = None
                    yield conn
                if tx_state.capacity_since is not None:
                    with metrics_lock:
                        metrics["capacity_hold_ms"].append((time.perf_counter() - tx_state.capacity_since) * 1000)

            original_maintenance = store.maintenance

            def maintenance(**kwargs):
                with metrics_lock:
                    metrics["maintenance_calls"] += 1
                return original_maintenance(**dict(kwargs, warm_profiles={"bench"}))

            barrier = threading.Barrier(workers)

            def run(_):
                tx_state.maintenance_worker = True
                barrier.wait(timeout=5)
                return proxy_pool.maintain_once(role="check")

            probes = []
            with patch.object(proxy_pool, "settings", return_value=policy), \
                 patch.object(proxy_pool, "_profiles", {}), patch.object(proxy_pool, "_prewarm", False), \
                 patch.object(proxy_pool, "_current_profile_keys", return_value=set()), \
                 patch.object(store, "maintenance", side_effect=maintenance), \
                 patch.object(record_store, "transaction", side_effect=transaction), \
                 patch.object(psycopg.Cursor, "execute", execute), \
                 ThreadPoolExecutor(max_workers=workers) as executor:
                started = time.perf_counter()
                futures = [executor.submit(run, index) for index in range(workers)]
                while not all(future.done() for future in futures):
                    probe = time.perf_counter()
                    with record_store.transaction() as conn:
                        record_store.count_rows(store.RESOURCES, where="state = 'ready'", conn=conn)
                    probes.append((time.perf_counter() - probe) * 1000)
                    if len(probes) < 200:
                        threading.Event().wait(0.005)
                for future in futures:
                    future.result(timeout=30)
                metrics["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
            for key in ("connection_wait_ms", "capacity_wait_ms", "capacity_hold_ms"):
                values = metrics[key]
                metrics[key] = {"count": len(values), "total": round(sum(values), 2),
                                "max": round(max(values, default=0), 2)}
            metrics["ordinary_read_ms"] = {"count": len(probes), "median": round(statistics.median(probes), 2) if probes else 0,
                                             "max": round(max(probes, default=0), 2)}
            print("代理维护基准 " + json.dumps(metrics, ensure_ascii=False))
        self.assertEqual(store.counts(), {"cooldown": 409, "ready": 91,
                                         "failed": 13333, "retired": 13334, "expired": 13333})
        # 再确认到期历史真正返回候选时仍只扫描有界数量，不以空结果计划代替清理负载。
        with record_store.transaction() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres_store.qualified(store.RESOURCES.name)} "
                        "SET updated_at = %s WHERE state IN ('failed','retired','expired')", (history_old,))
            cur.execute(f"ANALYZE {postgres_store.qualified(store.RESOURCES.name)}")
            cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT * FROM "
                        f"{postgres_store.qualified(store.RESOURCES.name)} "
                        "WHERE state IN ('failed','retired','expired') AND updated_at <= %s "
                        "ORDER BY updated_at, id LIMIT 200", (store._stamp(-7 * 24 * 60 * 60),))
            plan = cur.fetchone()["QUERY PLAN"][0]
            print("到期历史执行计划 " + json.dumps({"execution_ms": plan["Execution Time"],
                                                 "scans": scans(plan["Plan"])}, ensure_ascii=False))
        started = time.perf_counter()
        retired = store.maintenance(max_age=3600, max_idle=300, min_ready=91, min_ttl=300,
                                    max_size=500, warm_profiles={"bench"})
        self.assertEqual(retired, [])
        self.assertEqual(record_store.count_rows(store.RESOURCES), 40300)
        print("到期历史清理 " + json.dumps({"elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                                          "removed": 200}, ensure_ascii=False))
