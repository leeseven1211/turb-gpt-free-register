"""Root-opt-in real-process acceptance for terminal proxy-child reconciliation.

Only the root's exclusive PG slot may enable SETTLEMENT_DB_TESTS. Ordinary
collection does not import PG support. The parent owns every spawned process;
owner/ticket identities come from native admission, never mocked liveness.

All three crash windows already have a committed terminal receipt. They do not
exercise no-receipt orphan recovery or the default 900-second stale boundary.
The final window is resource-confirmed/job-not-confirmed, not SQL ACK loss.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import uuid
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
WINDOWS = ("child_released", "child_expires", "resource_confirmed")
_RETAINED_PROCESS_FIXTURES = {}
if __name__ == "__main__" and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write(path, value):
    path = Path(path)
    temporary = path.with_suffix(".writing")
    temporary.write_text(json.dumps(value, sort_keys=True, default=str), encoding="utf-8")
    temporary.replace(path)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _wait_file(path, *, timeout=25.0, process=None):
    deadline = time.monotonic() + timeout
    while not Path(path).exists():
        if process is not None and process.poll() is not None:
            raise AssertionError(f"owned child exited {process.returncode} before {Path(path).name}")
        if time.monotonic() >= deadline:
            raise AssertionError(f"owned child did not reach {Path(path).name}")
        time.sleep(.025)
    return _read(path)


def _sources():
    paths = (
        Path(__file__), ROOT / "core/operations/proxy_resources.py",
        ROOT / "core/storage/operations/settlements.py",
        ROOT / "core/storage/operations/permits.py",
        ROOT / "core/storage/proxy/pool.py",
    )
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


if os.getenv("SETTLEMENT_DB_TESTS") == "1":
    from psycopg.rows import dict_row

    from core.operations import run_log, settlement
    from core.operations.settlement_contracts import seal_intent, thaw
    from core.proxy.provider import ProxyLease
    from core.storage import postgres, records
    from core.storage.operations import common, legacy_task_store, permits, settlements, store
    from core.storage.proxy import leases as proxy_leases
    from core.storage.proxy import pool
    from tests.support_pg import PostgresTestCase
    from tests.support_settlement import NativeSettlementAbort

    def _initialize():
        schema = postgres.schema_name()
        if not schema.startswith("test_") or common._schema_name() != schema:
            raise AssertionError("real-process acceptance requires one owned test schema")
        legacy_task_store._SCHEMA = schema
        legacy_task_store._READY_KEY = ""
        legacy_task_store.init()
        store.reset_ready()
        store.init()
        permits.ensure_tables()
        records.init()

    def _rows(table, where="TRUE", args=(), *, operation=True):
        qualified = common._table(table) if operation else postgres.qualified(table)
        with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {qualified} WHERE {where} ORDER BY id", args)
            return [dict(row) for row in cur.fetchall()]

    def _permit(origin):
        with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {permits._permit_table()} WHERE permit_id=%s AND execution_id=%s",
                (origin["permit_id"], origin["execution_id"]),
            )
            row = cur.fetchone()
            if row is None:
                raise AssertionError("original permit missing")
            return dict(row)

    def _resource(identity):
        rows = _rows("operation_resources", "id=%s AND run_id=%s AND resource_uuid=%s", (
            identity["resource"]["id"], identity["origin"]["run_id"],
            identity["resource"]["resource_uuid"],
        ))
        if len(rows) != 1:
            raise AssertionError("original operation resource missing")
        return rows[0]

    def _business(identity):
        origin = identity["origin"]
        return {
            "tasks": _rows("operation_tasks", "id=%s", (origin["task_id"],)),
            "runs": _rows("operation_runs", "id=%s", (origin["run_id"],)),
            "events": _rows("operation_events", "run_id=%s", (origin["run_id"],)),
            "receipts": _rows("operation_settlement_receipts", "run_id=%s", (origin["run_id"],)),
            "dispositions": _rows("operation_settlement_dispositions", "run_id=%s", (origin["run_id"],)),
        }

    def _proxy_rows():
        return {
            name: _rows(name, operation=False)
            for name in ("proxy_leases", "proxy_pool_resources")
        }

    def _jobs(identity):
        origin = identity["origin"]
        return _rows("operation_settlement_cleanup", "permit_id=%s AND execution_id=%s", (
            origin["permit_id"], origin["execution_id"],
        ))

    def _claim(profile, role):
        task = store.create_runtime_task(
            task_type="plan_check", account_id=None,
            email=f"{role}@proxy-process.example.test",
            resource_family="proxy-process-acceptance", trigger="synthetic_proxy_process",
        )
        run_id = int(task["run"]["id"])
        execution_id = uuid.uuid4().hex
        owner = permits.current_owner()
        if owner["pid"] != os.getpid() or not owner.get("process_start"):
            raise AssertionError("native process start identity is required")
        admitted = permits.try_admit(
            execution_key=f"operation_run:{run_id}", task_type="plan_check",
            execution_id=execution_id, run_id=run_id, batch_key="", owner=owner, metadata={},
            policy=lambda conn: ([{"kind": "global", "key": "proxy-process", "limit": 8}], 1, []),
            claim=lambda conn, execution: store.claim_run(
                run_id, execution_id=execution, worker_pid=os.getpid(), conn=conn,
            ),
        )
        if "permit_id" not in admitted or not admitted.get("settlement_ticket"):
            raise AssertionError(f"native admission refused: {admitted.get('blocked_by')}")
        domain = admitted["settlement_domain"]
        origin = thaw(admitted["settlement_ticket"])
        if origin["owner"] != owner or origin["run_uuid"] != admitted["claimed_run"]["run_uuid"]:
            raise AssertionError("repository ticket differs from the claimed original Run")
        child = pool.claim(
            profile, min_ttl=0, max_age=60, allow_reuse=True, reuse_limit=100,
            correlation={"purpose": "plan-check", "operation_task_id": task["id"],
                         "operation_run_id": run_id},
        )
        if child is None or not pool.mark_delivered(child):
            raise AssertionError("real shared proxy child was not delivered")
        execution = SimpleNamespace(
            execution_id=execution_id, permit_id=admitted["permit_id"],
            claimed_run=admitted["claimed_run"], settlement_ticket=admitted["settlement_ticket"],
            settlement_domain=domain,
        )
        context = SimpleNamespace(
            task_id=task["id"], run_id=run_id, run=admitted["claimed_run"],
            execution_id=execution_id, settlement_domain=domain, _execution=execution,
        )
        from core.operations.proxy_resources import capture_proxy_pool_child

        binding = capture_proxy_pool_child(
            SimpleNamespace(lease=child, provider=child.provider, mode="pool"),
            context, actor_scope="owner_process",
        )
        if not binding or binding["execution_id"] != origin["execution_id"]:
            raise AssertionError("new producer did not capture the original execution")
        child_row = records.get_row_by(records.PROXY_LEASES, "lease_id", child.lease_id)
        if (binding["lease_id"] != child_row["lease_id"]
                or binding["acquired_at"] != child_row["acquired_at"]
                or binding["expires_at"] != child_row["expires_at"]):
            raise AssertionError("descriptor must freeze original child timestamps exactly")
        resource = store.register_resource(
            run_id, resource_type="proxy_lease", provider=child.provider,
            external_id=f"proxy-process:{execution_id}",
            detail={"execution_id": execution_id, "proxy_pool_child": binding},
        )
        identity = {
            "origin": origin, "resource": resource, "binding": binding,
            "owner": owner, "role": role, "profile": profile,
        }
        return identity, child, domain

    def _terminal(identity, domain):
        origin = {**identity["origin"], "lease_requirement": "accountless", "leases": []}
        resource = identity["resource"]
        intent = seal_intent(
            kind="terminal", origin=origin,
            payload={"status": "success", "message": "confirmed synthetic process result",
                     "result_summary": {
                         "fixture_business_count": identity["business"]["callback_count"],
                         "fixture_remote_count": identity["business"]["remote_count"],
                     }},
            obligations=({
                "action_kind": "resource_release", "resource_identity": resource["resource_uuid"],
                "blocks_permit": True,
                "payload": {
                    "resource_id": resource["id"], "resource_uuid": resource["resource_uuid"],
                    "run_id": origin["run_id"], "execution_id": origin["execution_id"],
                    "external_id": resource["external_id"], "proxy_pool_child": identity["binding"],
                },
            },),
        )
        receipt = settlements.submit_intent(intent, domain=domain)
        if receipt["actual_result"]["status"] != "success":
            raise AssertionError("original terminal receipt was not committed")
        return receipt

    def _seed(profile, seconds):
        slot = pool.reserve_slot(profile, "1024proxy", max_size=8, timeout=30)
        if slot is None:
            raise AssertionError("synthetic pool reserve refused")
        now = datetime.now()
        anchor = ProxyLease(
            uuid.uuid4().hex, "1024proxy", "http://192.0.2.211:8080", "192.0.2.211:8080", now,
            expires_at=now + timedelta(seconds=seconds), exit_ip="198.51.100.211", region="US",
            metadata={"persistent_lease": True},
        )
        proxy_leases.reserve_pending(
            lease_id=anchor.lease_id, provider=anchor.provider, endpoint=anchor.endpoint,
            proxy_url=anchor.proxy_url, acquired_at=now.isoformat(),
            expires_at=anchor.expires_at.isoformat(), purpose="pool-reserve",
        )
        proxy_leases.activate(
            lease_id=anchor.lease_id, exit_ip=anchor.exit_ip, region="US",
            expires_at=anchor.expires_at.isoformat(),
        )
        if not pool.publish(slot, anchor):
            raise AssertionError("synthetic anchor publish refused")

    def _producer(request, directory):
        role = request["role"]
        profile = request["profile"]
        if role == "original":
            _seed(profile, 12 if request["window"] == "child_expires" else 120)
        identity, child, domain = _claim(profile, role)
        counter_path = directory / "business.json"
        counters = _read(counter_path) if counter_path.exists() else {"callback_count": 0, "remote_count": 0}
        counters["callback_count"] += 1  # One actual synthetic business invocation.
        _write(counter_path, counters)
        identity["business"] = counters
        if role == "original":
            identity["receipt"] = _terminal(identity, domain)
            if request["window"] in {"child_released", "resource_confirmed"}:
                pool.release(child, reason="original_business_finished")
            if request["window"] == "resource_confirmed":
                if not store.release_resource(identity["resource"]["id"]):
                    raise AssertionError("original resource confirmation did not commit")
            identity["window"] = request["window"]
        identity["source"] = _sources()
        _write(directory / "gate.json", identity)
        _wait_file(directory / "finish.json", timeout=60)
        if role != "successor":
            raise AssertionError("original crash producer must be killed at its gate")
        pool.release(child, reason="successor_normal_finish")
        if not store.release_resource(identity["resource"]["id"]):
            raise AssertionError("successor resource confirmation failed")
        receipt = _terminal(identity, domain)
        _write(directory / "normal-finish.json", {
            "receipt": receipt, "owner": identity["owner"], "source": _sources(),
        })

    def _drain(identity, *, directory):
        domain = permits._settlement_domain()
        origin = identity["origin"]
        if (domain.domain_id != origin["domain_id"]
                or permits.owner_liveness(origin["owner"]) != "exited"):
            raise AssertionError("cleanup requires the exact actually exited original process")
        attempts = []
        observations = []
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            result = settlements.run_cleanup_once(
                domain=domain, permit_id=origin["permit_id"], execution_id=origin["execution_id"],
            )
            if result is not None:
                attempts.append(result)
                if result["state"] not in {"pending", "done", "superseded"}:
                    raise AssertionError(f"unexpected cleanup outcome: {result}")
            blocked = settlements.cleanup_blocks_permit(
                origin["permit_id"], origin["execution_id"], domain=domain,
            )
            observed_at = datetime.now()
            resource = _resource(identity)
            observations.append({
                "observed_at": observed_at.isoformat(), "cleanup": result,
                "resource_state": resource["state"], "permit_blocked": blocked,
            })
            if (identity.get("window") == "child_expires"
                    and resource["state"] == "released"
                    and observed_at < datetime.fromisoformat(identity["binding"]["expires_at"])):
                raise AssertionError("passive reconciliation confirmed an unreturned unexpired child")
            if not blocked:
                if not permits.release(
                    origin["permit_id"], origin["execution_id"],
                    schema=domain.permit_schema, database_url=domain.database_url,
                ):
                    raise AssertionError("native permit gate refused the completed original")
                _write(directory / "cleanup-attempts.json", attempts)
                _write(directory / "cleanup-observations.json", observations)
                return
            if _permit(origin)["released_at"] is not None:
                raise AssertionError("native permit released while cleanup still blocks")
            if permits.release(
                origin["permit_id"], origin["execution_id"],
                schema=domain.permit_schema, database_url=domain.database_url,
            ):
                raise AssertionError("permit gate bypassed outstanding cleanup")
            time.sleep(.05)
        _write(directory / "cleanup-attempts.json", attempts)
        _write(directory / "cleanup-observations.json", observations)
        raise AssertionError("original cleanup did not converge within the synthetic fixture window")

    def _replacement(request, directory):
        identity = request["original"]
        forbidden_calls = []

        def forbidden(*args, **kwargs):
            forbidden_calls.append("provider_or_pool_release")
            raise AssertionError("passive reconciliation must not release or call a provider")

        _write(directory / "started.json", {"owner": permits.current_owner()})
        _wait_file(directory / "go.json")
        with ExitStack() as stack:
            for target in (
                "requests.sessions.Session.request", "core.proxy.provider.release_proxy",
                "core.proxy.pool.release", "core.storage.proxy.pool.release",
                "core.storage.proxy.leases.release",
            ):
                stack.enter_context(patch(target, side_effect=forbidden))
            _drain(identity, directory=directory)
        if forbidden_calls:
            raise AssertionError("replacement attempted a forbidden active release")
        _write(directory / "result.json", {
            "owner": permits.current_owner(), "resource": _resource(identity),
            "permit": _permit(identity["origin"]), "business": _business(identity),
            "jobs": _jobs(identity), "forbidden_calls": forbidden_calls, "source": _sources(),
        })

    def _child_main(request_path, directory):
        request = _read(request_path)
        directory = Path(directory)
        _initialize()
        with patch("requests.sessions.Session.request",
                   side_effect=AssertionError("process fixture cannot access a remote service")):
            if request["role"] == "replacement":
                _replacement(request, directory)
            else:
                _producer(request, directory)

    class ProxyProcessReconciliationPostgresTests(PostgresTestCase):
        def setUp(self):
            super().setUp()
            self.assertTrue(all(value == 0 for value in settlement.active_counts().values()))
            self.assertFalse(settlement._THREAD is not None and settlement._THREAD.is_alive())
            self.enterContext(patch.dict(os.environ, {
                "OPERATION_TASK_DB_SCHEMA": self.schema, "ACCOUNT_TASK_DB_SCHEMA": self.schema,
            }))
            self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
            self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
            _initialize()
            artifact_root = os.getenv("PROXY_PROCESS_RECONCILIATION_ARTIFACTS")
            if artifact_root:
                Path(artifact_root).mkdir(parents=True, exist_ok=True)
            self.artifacts = Path(tempfile.mkdtemp(
                prefix="proxy-process-", dir=artifact_root,
            ))
            self.enterContext(patch.object(run_log, "_LOG_ROOT", self.artifacts / "logs"))
            self.enterContext(patch.object(run_log, "_TASK_LOG_ROOT", self.artifacts / "logs/tasks"))
            _write(self.artifacts / "source-before.json", _sources())
            self._install_owned_cleanup()

        def _install_owned_cleanup(self):
            self._owned_processes = []
            self._owned_closed = False
            self._owned_cleanup_error = None
            self._owned_blocked_dependencies = []
            test_class = type(self)
            if "_owned_proxy_fixtures" not in test_class.__dict__:
                test_class._owned_proxy_fixtures = []
            test_class._owned_proxy_fixtures.append(self)

            def schema_guard():
                for owner in test_class._owned_proxy_fixtures:
                    if (not owner._owned_closed or owner._owned_blocked_dependencies
                            or id(owner) in _RETAINED_PROCESS_FIXTURES):
                        raise NativeSettlementAbort(
                            "owned proxy process/permit cleanup incomplete; schema cleanup refused",
                        )

            test_class._native_settlement_before_schema_use = staticmethod(schema_guard)

            def after_run(stack, directory):
                if self._owned_closed and not self._owned_blocked_dependencies:
                    return
                directory._finalizer.detach()
                self._owned_retained_export_scope = (stack, directory)
                _RETAINED_PROCESS_FIXTURES[id(self)] = self
                raise NativeSettlementAbort(
                    "owned proxy process/permit cleanup incomplete; schema and artifacts retained",
                )

            self._native_settlement_after_run = after_run
            original_add_cleanup = self.addCleanup

            def guarded_cleanup(function, *args, **kwargs):
                def after_owned_cleanup():
                    try:
                        self._close_owned()
                    except BaseException:
                        self._owned_blocked_dependencies.append((function, args, kwargs))
                        raise
                    return function(*args, **kwargs)
                return after_owned_cleanup

            self._cleanups[:] = [
                (guarded_cleanup(function, *args, **kwargs), (), {})
                for function, args, kwargs in self._cleanups
            ]

            def add_cleanup(function, *args, **kwargs):
                original_add_cleanup(guarded_cleanup(function, *args, **kwargs))

            self.addCleanup = add_cleanup
            original_add_cleanup(self._close_owned)

        def _owned_database_snapshot(self):
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {permits._permit_table()} ORDER BY permit_id")
                permit_rows = [dict(row) for row in cur.fetchall()]
            return {
                "schema": self.schema, "permits": permit_rows,
                "resources": _rows("operation_resources"),
                "cleanup": _rows("operation_settlement_cleanup"),
                "runs": _rows("operation_runs"),
            }

        def _close_owned_peer(self, entry):
            process, directory, role = entry["process"], entry["directory"], entry["role"]
            gate_path = directory / ("started.json" if role == "replacement" else "gate.json")
            gate = _read(gate_path) if gate_path.exists() else None
            owner = (gate or {}).get("owner")
            if owner is not None:
                if (owner["pid"] != process.pid
                        or owner["process_start"] != entry["process_start"]):
                    raise AssertionError("owned cleanup child identity differs from the captured spawn")
            was_running = process.poll() is None
            fallback = False
            if was_running and role == "successor" and gate is not None:
                self._alive(process, owner)
                if not (directory / "finish.json").exists():
                    _write(directory / "finish.json", {"reason": "owned_failure_cleanup"})
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            if process.poll() is None:
                if (not entry["process_start"]
                        or permits._process_start(process.pid) != entry["process_start"]):
                    raise AssertionError("owned cleanup refused an unverified process signal")
                process.kill()
                process.wait(timeout=10)
                fallback = True
            process.wait(timeout=0)
            if owner is not None and permits.owner_liveness(owner) != "exited":
                raise AssertionError("owned cleanup has not proven original process exit")
            receipt = {
                "role": role, "pid": process.pid, "process_start": entry["process_start"],
                "actual_returncode": process.returncode, "reaped": True,
                "was_running_at_cleanup": was_running, "fallback_sigkill": fallback,
                "acceptance_gate_kill": False,
            }
            _write(directory / "owned-cleanup-exit.json", receipt)
            return receipt

        def _close_owned(self):
            if self._owned_closed:
                return
            if self._owned_cleanup_error is not None:
                raise AssertionError("owned cleanup remains unconfirmed; exact schema retained")
            peers = []
            before = None
            try:
                # Preserve source/schema/log overrides until every actual actor
                # has exited and every original native permit has closed.
                for entry in reversed(self._owned_processes):
                    peers.append(self._close_owned_peer(entry))
                before = self._owned_database_snapshot()
                known = {
                    (entry["process"].pid, entry["process_start"]): entry
                    for entry in self._owned_processes
                    if entry["role"] in {"original", "successor"}
                }
                for permit in before["permits"]:
                    owner = permit["owner"]
                    entry = known.get((owner.get("pid"), owner.get("process_start")))
                    if entry is None:
                        raise AssertionError("owned schema contains an unaccounted native permit")
                    gate_path = entry["directory"] / "gate.json"
                    if not gate_path.exists():
                        raise AssertionError("claimed native owner has no saved exact resource gate")
                    identity = _read(gate_path)
                    origin = identity["origin"]
                    ticket = common._decode(permit["metadata"])["settlement_ticket"]
                    if (ticket != origin or permit["permit_id"] != origin["permit_id"]
                            or permit["execution_id"] != origin["execution_id"]
                            or owner != identity["owner"]):
                        raise AssertionError("failure cleanup cannot bind the exact original ticket")
                    business_before = _business(identity)
                    if len(business_before["receipts"]) != 1:
                        raise AssertionError("failure cleanup has no original committed terminal receipt")
                    proxy_before = _proxy_rows()
                    _drain(identity, directory=entry["directory"])
                    if (business_before != _business(identity) or proxy_before != _proxy_rows()
                            or _resource(identity)["state"] != "released"
                            or _permit(origin)["released_at"] is None):
                        raise AssertionError("failure cleanup altered original business or proxy facts")
                after = self._owned_database_snapshot()
                if (any(row["released_at"] is None for row in after["permits"])
                        or any(row["state"] != "released" for row in after["resources"])
                        or any(row["state"] not in {"done", "superseded"} for row in after["cleanup"])
                        or any(row["status"] in {"queued", "running", "cancelling", "settling",
                                                 "stopping", "waiting"} for row in after["runs"])):
                    raise AssertionError("owned schema still holds active original responsibility")
                _write(self.artifacts / "owned-cleanup.json", {
                    "closed": True, "retained_for_diagnosis": False,
                    "peers": peers, "before": before, "after": after,
                })
                self._owned_closed = True
            except BaseException as exc:
                self._owned_cleanup_error = type(exc).__name__
                _write(self.artifacts / "owned-cleanup.json", {
                    "closed": False, "retained_for_diagnosis": True, "schema": self.schema,
                    "peers": peers, "before": before, "error_type": type(exc).__name__,
                    "schema_cleanup_refused": True,
                })
                raise

        def _start(self, role, request):
            directory = self.artifacts / role
            directory.mkdir()
            request_path = directory / "request.json"
            _write(request_path, {**request, "role": role})
            env = {
                **os.environ, "PYTHON_DOTENV_DISABLED": "1", "SETTLEMENT_DB_TESTS": "1",
                "TURB_DB_SCHEMA": self.schema, "OPERATION_TASK_DB_SCHEMA": self.schema,
                "ACCOUNT_TASK_DB_SCHEMA": self.schema,
                "TASK_RUN_LOG_ROOT": str(self.artifacts / "logs"),
                "PYTHONPATH": str(ROOT),
            }
            output = (directory / "output.log").open("wb")
            self.addCleanup(output.close)
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--child",
                 str(request_path), str(directory)],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.STDOUT,
            )
            entry = {
                "process": process, "directory": directory, "role": role,
                "process_start": permits._process_start(process.pid),
            }
            self._owned_processes.append(entry)
            _write(directory / "spawn.json", {
                "pid": process.pid, "process_start": entry["process_start"], "role": role,
            })
            return process, directory

        def _alive(self, process, owner):
            self.assertIsNone(process.poll())
            self.assertEqual(process.pid, owner["pid"])
            self.assertNotEqual(os.getpid(), owner["pid"])
            self.assertTrue(owner["process_start"])
            self.assertEqual(owner["process_start"], permits._process_start(process.pid))
            self.assertEqual("alive", permits.owner_liveness(owner))

        def _run(self, window):
            self.assertIn(window, WINDOWS)
            profile = f"proxy-process-{uuid.uuid4().hex}"
            original_process, original_dir = self._start("original", {
                "window": window, "profile": profile,
            })
            original = _wait_file(original_dir / "gate.json", process=original_process)
            self._alive(original_process, original["owner"])
            successor_process, successor_dir = self._start("successor", {"profile": profile})
            successor = _wait_file(successor_dir / "gate.json", process=successor_process)
            self._alive(successor_process, successor["owner"])
            self.assertNotEqual(original["origin"]["run_id"], successor["origin"]["run_id"])
            self.assertNotEqual(original["binding"]["lease_id"], successor["binding"]["lease_id"])
            self.assertEqual(original["binding"]["pool_anchor_id"], successor["binding"]["pool_anchor_id"])
            self.assertEqual(original["binding"]["pool_resource_id"], successor["binding"]["pool_resource_id"])
            before_business = _business(original)
            successor_before = {"business": _business(successor), "permit": _permit(successor["origin"]),
                                "resource": _resource(successor)}
            before_proxy = _proxy_rows()
            _write(self.artifacts / "before-kill.json", {
                "original": original, "business": before_business,
                "resource": _resource(original), "permit": _permit(original["origin"]),
                "proxy": before_proxy, "successor": successor_before,
            })
            self.assertEqual(1, len(before_business["receipts"]))
            self.assertEqual("success", before_business["runs"][0]["status"])
            self.assertEqual(1, before_business["runs"][0]["result_summary"]["fixture_business_count"])
            self.assertTrue(all(job["state"] == "pending" for job in _jobs(original)))
            if window == "resource_confirmed":
                self.assertEqual("released", _resource(original)["state"])
            else:
                self.assertIn(_resource(original)["state"], {"acquired", "reconciliation_required"})
            if window == "child_expires":
                self.assertGreater(datetime.fromisoformat(original["binding"]["expires_at"]), datetime.now())
            self.assertFalse(permits.release(
                original["origin"]["permit_id"], original["origin"]["execution_id"],
                schema=self.schema, database_url=postgres.database_url(),
            ))
            self._alive(original_process, original["owner"])
            killed_at = time.monotonic()
            original_process.send_signal(signal.SIGKILL)
            self.assertEqual(-signal.SIGKILL, original_process.wait(timeout=10))
            self.assertEqual("exited", permits.owner_liveness(original["owner"]))
            _write(original_dir / "exit.json", {
                "owner": original["owner"], "actual_returncode": original_process.returncode,
                "reaped": True, "formal_sigkill": True, "killed_monotonic": killed_at,
            })
            _write(self.artifacts / "after-death.json", {
                "business": _business(original), "resource": _resource(original),
                "permit": _permit(original["origin"]), "proxy": _proxy_rows(),
                "successor": {"business": _business(successor), "permit": _permit(successor["origin"]),
                              "resource": _resource(successor)},
            })
            replacement_process, replacement_dir = self._start("replacement", {"original": original})
            started = _wait_file(replacement_dir / "started.json", process=replacement_process)
            self._alive(replacement_process, started["owner"])
            _write(replacement_dir / "go.json", {"parent_confirmed_physical_identity": True})
            self.assertEqual(0, replacement_process.wait(timeout=45))
            result = _read(replacement_dir / "result.json")
            self.assertEqual(replacement_process.pid, result["owner"]["pid"])
            self.assertEqual(started["owner"], result["owner"])
            self.assertEqual("exited", permits.owner_liveness(result["owner"]))
            _write(replacement_dir / "exit.json", {
                "owner": result["owner"], "actual_returncode": replacement_process.returncode,
                "reaped": True, "formal_sigkill": False,
            })
            self.assertEqual("released", _resource(original)["state"])
            self.assertIsNotNone(_permit(original["origin"])["released_at"])
            self.assertTrue(all(job["state"] in {"done", "superseded"} for job in _jobs(original)))
            self.assertEqual(before_business, _business(original))
            self.assertEqual(before_proxy, _proxy_rows())
            self.assertEqual(successor_before, {
                "business": _business(successor), "permit": _permit(successor["origin"]),
                "resource": _resource(successor),
            })
            self._alive(successor_process, successor["owner"])
            _write(self.artifacts / "after-reconcile.json", {
                "business": _business(original), "resource": _resource(original),
                "permit": _permit(original["origin"]), "proxy": _proxy_rows(),
                "successor": {"business": _business(successor), "permit": _permit(successor["origin"]),
                              "resource": _resource(successor)},
            })
            self.assertEqual({"callback_count": 1, "remote_count": 0},
                             _read(original_dir / "business.json"))
            self.assertEqual([], result["forbidden_calls"])
            if window == "child_expires":
                observations = _read(replacement_dir / "cleanup-observations.json")
                expires_at = datetime.fromisoformat(original["binding"]["expires_at"])
                self.assertTrue(any(
                    datetime.fromisoformat(sample["observed_at"]) < expires_at
                    and sample["resource_state"] != "released" and sample["permit_blocked"]
                    for sample in observations
                ), "must observe the exact unexpired child blocking passive reconciliation")
                self.assertGreaterEqual(datetime.fromisoformat(observations[-1]["observed_at"]), expires_at)
            for _ in range(2):
                self.assertIsNone(settlements.run_cleanup_once(
                    domain=permits._settlement_domain(), permit_id=original["origin"]["permit_id"],
                    execution_id=original["origin"]["execution_id"],
                ))
                self.assertTrue(permits.release(
                    original["origin"]["permit_id"], original["origin"]["execution_id"],
                    schema=self.schema, database_url=postgres.database_url(),
                ))
            self.assertEqual(before_business, _business(original))
            self.assertEqual(before_proxy, _proxy_rows())
            _write(successor_dir / "finish.json", {"reason": "normal_successor_finish_after_acceptance"})
            self.assertEqual(0, successor_process.wait(timeout=15))
            self.assertTrue((successor_dir / "normal-finish.json").exists())
            self.assertEqual("exited", permits.owner_liveness(successor["owner"]))
            _drain(successor, directory=successor_dir)
            self.assertIsNotNone(_permit(successor["origin"])["released_at"])
            source_after = _sources()
            self.assertEqual(_read(self.artifacts / "source-before.json"), source_after)
            self.assertEqual(original["source"], source_after)
            self.assertEqual(result["source"], source_after)
            _write(self.artifacts / "source-after.json", source_after)
            _write(self.artifacts / "result.json", {
                "window": window, "accepted": True, "already_committed_terminal_receipt": True,
                "original_exit": -9, "replacement_exit": 0, "successor_exit": 0,
                "no_receipt_orphan_900_tested": False, "sql_ack_loss_tested": False,
                "source_before_after_equal": True,
            })

        def test_original_child_return_committed_before_operation_resource_confirmation(self):
            self._run("child_released")

        def test_unreturned_original_child_expires_naturally_and_preserves_shared_successor(self):
            self._run("child_expires")

        def test_operation_resource_confirmation_committed_before_cleanup_job_confirmation(self):
            self._run("resource_confirmed")


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--child" or os.getenv("SETTLEMENT_DB_TESTS") != "1":
        raise SystemExit("child entry is reserved for root-opt-in isolated PostgreSQL acceptance")
    if str(ROOT) not in sys.path:
        raise SystemExit("root must launch this fixture with the repository in PYTHONPATH")
    _child_main(sys.argv[2], sys.argv[3])
