"""Test-owned Codex crash cohort; no database or process action at import.

Three fresh schemas share one real default-stale wait.  READY never means
PASS: the original test methods still perform native readback and recovery.
No result from a previous invocation or an artifact directory is accepted.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
CASES = ("response-crash", "confirmed-crash", "post-write-crash")
METHOD_CASES = {
    "test_http_response_before_readback_crash_is_not_confirmed_or_retried": CASES[0],
    "test_confirmed_receipt_before_terminal_finish_still_blocks_producer": CASES[1],
    "test_post_write_marker_restore_crash_uses_durable_producer_fence": CASES[2],
}
STALE_SECONDS = 900
LEASE_SECONDS = 600


def source_hashes():
    paths = [
        *ROOT.joinpath("core").rglob("*.py"),
        *ROOT.joinpath("config").rglob("*.py"),
        ROOT / "tests/support_pg.py",
        ROOT / "tests/support_settlement.py",
        ROOT / "tests/codex/test_codex_token_refresh_durable.py",
        Path(__file__).resolve(),
    ]
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(set(paths))}


def _write(path, value):
    from core.runtime.role_launcher import atomic_json
    atomic_json(path, value)


@dataclass
class CrashCase:
    name: str
    schema: str
    directory: Path
    account_id: int = 0
    email: str = ""
    filename: str = ""
    task_id: int = 0
    run_id: int = 0
    run_uuid: str = ""
    gate: dict | None = None
    claimed: bool = False
    asserted: bool = False
    prepared: bool = False


class CodexCrashCohort:
    """One class invocation owns its children, schemas, and all observations."""

    def __init__(self):
        self.nonce = uuid.uuid4().hex
        self.owner_pid = os.getpid()
        self.hashes = source_hashes()
        # Retained evidence, never a source of cached PASS on a later run.
        self.directory = Path(tempfile.mkdtemp(prefix=f"codex-crash-{self.nonce[:8]}-")).resolve()
        self.phase = "new"
        self.cases = {}
        self.peers = []
        self.closed = False

    def _check_source(self):
        assert os.getpid() == self.owner_pid, "cohort cannot cross process invocations"
        assert source_hashes() == self.hashes, "cohort source changed during real stale wait"

    @contextmanager
    def case_scope(self, case):
        """No env redirect of another thread; only the idle test caller moves."""
        from core import account_task_store
        from core.operations import run_log, settlement
        from core.operations.settlement_contracts import SettlementDomain
        from core.storage import postgres
        from core.storage.operations import common, permits
        import requests

        assert settlement._THREAD is None or not settlement._THREAD.is_alive()
        assert all(value == 0 for value in settlement.active_counts().values())
        assert self.cases.get(case.name) is case
        domain = SettlementDomain(
            self.database_url, case.schema, case.schema,
            permits._domain_id(self.database_url, case.schema, case.schema),
        )
        with ExitStack() as stack:
            stack.enter_context(patch.object(account_task_store, "_SCHEMA", case.schema))
            stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
            stack.enter_context(patch.object(run_log, "_LOG_ROOT", case.directory / "logs"))
            stack.enter_context(patch.object(run_log, "_TASK_LOG_ROOT", case.directory / "logs/tasks"))
            stack.enter_context(patch.object(requests.sessions.Session, "request",
                                            side_effect=AssertionError("case consumer forbids remote network")))
            stack.enter_context(common.settlement_scope(domain))
            postgres.reset_cache()
            try:
                yield
            finally:
                postgres.reset_cache()

    def _prepare(self, name):
        from core import account_task_store, db
        from core.codex import token_refresh_service as service
        from core.operations import run_log, settlement, task_gateway
        from core.storage import postgres, records
        from core.storage.operations import permits, store
        from tests.support_pg import temporary_schema_name

        assert settlement._THREAD is None or not settlement._THREAD.is_alive()
        assert all(value == 0 for value in settlement.active_counts().values())
        assert not task_gateway.dispatcher_status()["alive"]
        assert not task_gateway.dependency_dispatcher_status()["alive"]
        case = CrashCase(name, temporary_schema_name(f"codex_{self.nonce[:8]}_{name}"),
                         self.directory / name)
        self.cases[name] = case  # Register ownership before the first DDL.
        case.directory.mkdir(mode=0o700)
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {
                "TURB_DB_SCHEMA": case.schema,
                "OPERATION_TASK_DB_SCHEMA": case.schema,
                "ACCOUNT_TASK_DB_SCHEMA": case.schema,
            }))
            stack.enter_context(patch.object(account_task_store, "_SCHEMA", case.schema))
            stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
            stack.enter_context(patch.object(run_log, "_LOG_ROOT", case.directory / "logs"))
            stack.enter_context(patch.object(run_log, "_TASK_LOG_ROOT", case.directory / "logs/tasks"))
            postgres.reset_cache()
            postgres.ensure_schema()
            records.reset_ready()
            records.init()
            account_task_store.init()
            store.reset_ready()
            store.init()
            permits.ensure_tables()
            case.email = f"{name}@example.test"
            case.filename = f"codex-{name}@example.test-free.json"
            case.account_id = records.insert_row(records.ACCOUNTS, {
                "email": case.email, "access_token": "synthetic-account-access",
                "codex_status": "failed", "account_status": "active",
                "created_at": "2026-09-14T10:00:00", "updated_at": "2026-09-14T10:00:00",
            })
            db.save_codex_credential_record(case.filename, {
                "type": "codex", "email": case.email, "access_token": "old-access",
                "refresh_token": "old-refresh", "expired": "2020-01-01T00:00:00Z",
                "account_id": str(case.account_id),
            })
            created = store.create_runtime_task(
                task_type=service.TASK_TYPE, account_id=case.account_id, email=case.email,
                source_system="native_operations", source_id=f"{self.nonce}:{name}",
                data={"credential_filename": case.filename, "resource_family": service.RESOURCE_FAMILY,
                      "config_snapshot": {"CODEX_REQUEST_TIMEOUT": 5}},
            )
            # create_runtime_task returns the Task itself with an embedded Run.
            case.task_id = int(created["id"])
            case.run_id = int(created["run"]["id"])
            case.run_uuid = created["run"]["run_uuid"]
            case.prepared = True
            postgres.reset_cache()
        return case

    def _snapshot(self, case):
        from core.storage.operations import common, permits, store
        with self.case_scope(case), common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT now() AS observed_at,
                extract(epoch FROM now()-heartbeat_at) AS heartbeat_age
                FROM {common._table('operation_runs')} WHERE id=%s AND run_uuid=%s""",
                        (case.run_id, case.run_uuid))
            age = cur.fetchone()
            assert age is not None
            cur.execute(f"SELECT * FROM {permits._permit_table(case.schema)} WHERE run_id=%s",
                        (case.run_id,))
            permit_rows = list(cur.fetchall())
            cur.execute(f"""SELECT lease_token,expires_at > now() AS valid,
                extract(epoch FROM expires_at-heartbeat_at) AS ttl
                FROM {common._table('account_operation_leases')} WHERE run_id=%s""",
                        (case.run_id,))
            leases = list(cur.fetchall())
            counts = {}
            for table, condition in (
                ("operation_settlement_receipts", ""),
                ("operation_settlement_cleanup", " AND state NOT IN ('done','superseded')"),
                ("operation_resources", " AND state <> 'released'"),
                ("operation_events", " AND event_type IN ('run.attention_required','run.interrupted','run.success')"),
            ):
                cur.execute(f"SELECT count(*) AS n FROM {common._table(table)} WHERE run_id=%s{condition}",
                            (case.run_id,))
                counts[table] = int(cur.fetchone()["n"])
            cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_runs')} WHERE task_id=%s",
                        (case.task_id,))
            counts["runs"] = int(cur.fetchone()["n"])
            return {"run": store.get_run(case.run_id), "task": store.get_task(case.task_id),
                    "heartbeat_age": float(age["heartbeat_age"]), "observed_at": str(age["observed_at"]),
                    "permits": permit_rows, "leases": leases, "counts": counts}

    def _assert_origin(self, case, value):
        run = value["run"]
        assert run["id"] == case.run_id and run["run_uuid"] == case.run_uuid
        assert int(run["task_id"]) == case.task_id
        assert int(run["account_id"]) == case.account_id
        assert run["data"]["credential_filename"] == case.filename
        assert value["counts"]["runs"] == 1
        assert int(value["task"]["last_run_id"]) == case.run_id
        assert len(value["permits"]) == 1
        if case.gate is not None:
            permit = value["permits"][0]
            ticket = permit["metadata"]["settlement_ticket"]
            assert str(run["execution_id"]) == str(case.gate["execution_id"])
            assert ticket["operation_schema"] == ticket["permit_schema"] == case.schema
            for key in ("permit_id", "execution_id"):
                assert str(permit[key]) == str(case.gate[key])
            for key in ("run_uuid", "run_id", "ticket_id", "domain_id", "owner"):
                assert ticket[key] == case.gate["ticket"][key]

    def _assert_prestate(self, case):
        from core.codex import token_refresh_service as service
        from core.storage import records
        value = self._snapshot(case)
        self._assert_origin(case, value)
        assert value["run"]["status"] == "settling"
        assert value["permits"][0]["released_at"] is None
        assert value["counts"]["operation_settlement_receipts"] == 0
        assert value["counts"]["operation_events"] == 0
        assert case.gate["refresh_calls"] == case.gate["callback_calls"] == 1
        data = value["run"]["data"]
        expected = "confirmed" if case.name == "confirmed-crash" else "response_received"
        assert data["remote_intent"]["receipt_state"] == expected
        assert data["remote_receipt"]["outcome"] == expected
        if expected == "confirmed":
            for key in ("remote_result_confirmed", "local_business_writeback_confirmed",
                        "local_readback_confirmed"):
                assert data["remote_receipt"]["detail"][key] is True
        else:
            assert not data["remote_receipt"]["detail"].get("terminal", False)
        with self.case_scope(case):
            row = records.get_row_by(records.CODEX_CREDENTIALS, "filename", case.filename)
        if case.name == "post-write-crash":
            assert row["oauth_refresh_error"] is None
        elif case.name == "confirmed-crash":
            assert row["oauth_refresh_error"] == service.REQUEST_PENDING
        return value

    def _record_snapshot(self, case, stage, value):
        """Fixed metadata only; never serialize credentials, DSNs or lease tokens."""
        data = value["run"]["data"]
        _write(case.directory / f"{stage}.json", {
            "nonce": self.nonce, "case": case.name, "schema": case.schema,
            "run_id": case.run_id, "run_uuid": case.run_uuid, "task_id": case.task_id,
            "execution_id": value["run"]["execution_id"],
            "run_status": value["run"]["status"], "task_status": value["task"]["status"],
            "last_run_id": value["task"]["last_run_id"], "counts": value["counts"],
            "heartbeat_age": value["heartbeat_age"], "observed_at": value["observed_at"],
            "leases": [{"valid": row["valid"], "ttl": float(row["ttl"])}
                       for row in value["leases"]],
            "permit_released": [row["released_at"] is not None for row in value["permits"]],
            "remote_intent_state": data["remote_intent"]["receipt_state"],
            "remote_receipt_outcome": data["remote_receipt"]["outcome"],
        })

    def _kill(self, peer):
        from core.runtime.role_launcher import inspect_process
        process, identity = peer["process"], peer["identity"]
        current = inspect_process(process.pid)
        assert current is not None and asdict(current) == identity
        process.send_signal(signal.SIGKILL)
        assert process.wait(timeout=10) == -signal.SIGKILL
        after = inspect_process(process.pid)
        assert after is None or after.process_start != identity["process_start"]
        peer["reaped"] = True
        _write(peer["case"].directory / "death.json", {
            "nonce": self.nonce, "identity": identity, "exit_code": process.returncode,
            "reaped": True, "signal": "SIGKILL",
        })
        peer["log"].close()

    def _launch_and_kill(self, case):
        from core.runtime.role_launcher import inspect_process
        from core.storage.operations import permits, recovery
        from tools.test_isolated import build_isolated_environment

        request = {"nonce": self.nonce, "hashes": self.hashes, "case": case.name,
                   "schema": case.schema, "run_id": case.run_id, "run_uuid": case.run_uuid,
                   "directory": str(case.directory)}
        request_file = case.directory / "request.json"
        _write(request_file, request)
        env = build_isolated_environment(database_url=self.database_url, schema=case.schema, project_root=ROOT)
        env.update(OPERATION_TASK_DB_SCHEMA=case.schema,
                   TASK_RUN_LOG_ROOT=str(case.directory / "logs"), COMPAT_EXPORT_MODE="off")
        log = (case.directory / "child.log").open("x", encoding="utf-8")
        try:
            process = subprocess.Popen(
                [sys.executable, "-B", "-m", "tests.codex.support_token_refresh_crash",
                 "--child-request", str(request_file)], cwd=ROOT, env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            )
        except BaseException:
            log.close()
            raise
        peer = {"process": process, "case": case, "identity": None, "log": log, "reaped": False}
        self.peers.append(peer)  # Cleanup ownership before waiting for a gate.
        deadline = time.monotonic() + 60
        gate_path = case.directory / "gate.json"
        while not gate_path.is_file():
            assert process.poll() is None, f"child exited before original {case.name} gate"
            assert time.monotonic() < deadline, f"child did not reach {case.name}"
            time.sleep(.05)
        case.gate = json.loads(gate_path.read_text())
        assert case.gate["nonce"] == self.nonce and case.gate["hashes"] == self.hashes
        assert case.gate["case"] == case.name and case.gate["pid"] == process.pid
        info = inspect_process(process.pid)
        assert info is not None and info.cwd == str(ROOT)
        assert "tests.codex.support_token_refresh_crash" in info.command
        assert str(request_file) in info.command
        assert info.owner_process_start == case.gate["ticket"]["owner"]["process_start"]
        assert process.pid == case.gate["ticket"]["owner"]["pid"]
        assert permits.owner_liveness(case.gate["ticket"]["owner"]) == "alive"
        peer["identity"] = asdict(info)
        assert not recovery._original_process_exited(case.gate["ticket"]["owner"])
        self._assert_prestate(case)
        before = self._snapshot(case)
        self._record_snapshot(case, "before-kill", before)
        assert before["leases"] and all(row["valid"] for row in before["leases"])
        assert all(abs(float(row["ttl"]) - LEASE_SECONDS) < .1 for row in before["leases"])
        with self.case_scope(case):
            from core.storage.operations import runtime
            assert runtime.recover_interrupted_runtime_runs() == 0
        self._kill(peer)
        assert recovery._original_process_exited(case.gate["ticket"]["owner"])
        self._record_snapshot(case, "after-death", self._assert_prestate(case))

    def ensure_ready(self):
        self._check_source()
        if self.phase == "ready":
            return self
        assert self.phase == "new", f"failed/consumed cohort cannot restart: {self.phase}"
        from core.storage import postgres
        from tools.test_isolated import validate_test_database_url
        self.database_url = postgres.database_url()
        validate_test_database_url(self.database_url)
        self.phase = "preparing"
        try:
            for name in CASES:
                self._launch_and_kill(self._prepare(name))
            self.phase = "waiting"
            deadline = time.monotonic() + STALE_SECONDS + 120
            samples = []
            while True:
                self._check_source()
                values = {name: self._snapshot(case) for name, case in self.cases.items()}
                for name, value in values.items():
                    self._assert_origin(self.cases[name], value)
                    assert value["run"]["status"] == "settling", "recovery was consumed before original method"
                samples.append({name: {"age": value["heartbeat_age"],
                                       "valid_leases": sum(row["valid"] for row in value["leases"]),
                                       "observed_at": value["observed_at"]}
                                for name, value in values.items()})
                _write(self.directory / "natural-age-observations.json", samples)
                if all(value["heartbeat_age"] > STALE_SECONDS
                       and not any(row["valid"] for row in value["leases"]) for value in values.values()):
                    break
                assert time.monotonic() < deadline, "real default900 readiness not reached"
                time.sleep(2)
            self.phase = "ready"
            return self
        except BaseException:
            self.phase = "failed"
            raise

    def claim(self, name):
        self.ensure_ready()
        case = self.cases[name]
        assert not case.claimed, "case may be asserted only once per class invocation"
        self._assert_prestate(case)
        case.claimed = True
        return case

    def assert_closed(self, case):
        from core.storage.operations import common, settlements
        self._check_source()
        value = self._snapshot(case)
        self._assert_origin(case, value)
        assert value["run"]["status"] == value["task"]["status"] == "attention_required"
        assert value["run"]["result_summary"]["outcome"] == "request_unknown"
        assert value["counts"]["operation_settlement_receipts"] == 0
        assert value["counts"]["operation_events"] == 1
        assert not value["leases"] and value["counts"]["operation_settlement_cleanup"] == 0
        assert value["counts"]["operation_resources"] == 0
        assert all(row["released_at"] is not None for row in value["permits"])
        with self.case_scope(case), common._connect() as conn:
            disposition = settlements.read_disposition(
                case.gate["ticket"], domain=common.current_settlement_domain(), conn=conn)
        assert disposition and disposition["original_intent_committed"] is False
        self._record_snapshot(case, "native-closed", value)
        return value

    def finish(self, case):
        from core.storage.operations import runtime
        assert case.claimed and not case.asserted
        self.assert_closed(case)
        with self.case_scope(case):
            assert runtime.recover_interrupted_runtime_runs() == 0
        self.assert_closed(case)  # Idempotent confirmation cannot add an event.
        case.asserted = True

    def close(self):
        """Never DROP a failed or still-owned case to make teardown green."""
        if self.closed:
            return
        errors = []
        for peer in self.peers:
            if peer["process"].poll() is None:
                try:
                    if peer["identity"] is None:
                        from core.runtime.role_launcher import inspect_process
                        info = inspect_process(peer["process"].pid)
                        assert info is not None and info.cwd == str(ROOT)
                        assert "tests.codex.support_token_refresh_crash" in info.command
                        assert str(peer["case"].directory / "request.json") in info.command
                        peer["identity"] = asdict(info)
                    self._kill(peer)
                except BaseException as exc:
                    errors.append(type(exc).__name__)
            else:
                peer["process"].wait(timeout=1)
                peer["log"].close()
        if self.phase == "ready":
            from core.storage.operations import runtime
            for case in self.cases.values():
                try:
                    if not case.asserted:
                        # Unselected methods are cleanup, never fabricated PASS.
                        with self.case_scope(case):
                            recovered = runtime.recover_interrupted_runtime_runs()
                        assert recovered in (0, 1)
                    self.assert_closed(case)
                except BaseException as exc:
                    errors.append(f"{case.name}:{type(exc).__name__}")
        elif self.cases:
            errors.append("cohort_failed_before_natural_recovery_ready")
        if not errors:
            from tests.support_pg import drop_schema
            for case in self.cases.values():
                with self.case_scope(case):
                    drop_schema(case.schema)
            self.closed = True
        _write(self.directory / "closure.json", {
            "nonce": self.nonce, "phase": self.phase,
            "cases": {name: {"schema": case.schema, "claimed": case.claimed,
                             "asserted_by_original_method": case.asserted}
                      for name, case in self.cases.items()},
            "errors": errors, "closed": self.closed,
        })
        assert not errors, f"cohort schemas retained; closure errors: {errors}"


def _child(request_file):
    """Only this fresh process enters the original business callback."""
    request = json.loads(Path(request_file).read_text())
    assert request["case"] in CASES and request["hashes"] == source_hashes()
    assert os.environ.get("PYTHON_DOTENV_DISABLED") == "1"
    assert os.environ["TURB_DB_SCHEMA"] == request["schema"]
    assert os.environ["OPERATION_TASK_DB_SCHEMA"] == request["schema"]
    assert os.environ["ACCOUNT_TASK_DB_SCHEMA"] == request["schema"]
    assert Path(request["directory"]).resolve() == Path(request_file).resolve().parent
    assert len(request["nonce"]) == 32 and uuid.UUID(hex=request["nonce"]).hex == request["nonce"]
    from tools.test_isolated import _validate_schema, validate_test_database_url
    _validate_schema(request["schema"])
    validate_test_database_url(str(os.environ.get("DATABASE_URL") or ""))
    from core.codex import token_refresh_service as service
    from core.operations import concurrency, settlement, task_gateway
    from core.operations.settlement_contracts import thaw
    from core.storage import postgres
    from tests.support_settlement import NativeSettlementFixture
    import requests

    fixture = NativeSettlementFixture()
    fixture.start()
    service._HANDLER_REGISTERED = False
    service._register_worker()
    refresh_calls = 0
    callback_calls = 0
    hook_calls = 0

    def refresh(*_args, **_kwargs):
        nonlocal refresh_calls
        refresh_calls += 1
        assert refresh_calls == 1
        return {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600}

    def gate():
        execution = concurrency.current_execution()
        assert execution is not None and execution.claimed_run["id"] == request["run_id"]
        ticket = thaw(execution.settlement_ticket)
        # Ticket values are JSON primitives; no credentials are serialized.
        _write(Path(request["directory"]) / "gate.json", {
            "nonce": request["nonce"], "hashes": source_hashes(), "case": request["case"],
            "pid": os.getpid(), "ticket": ticket, "refresh_calls": refresh_calls,
            "callback_calls": callback_calls, "permit_id": execution.permit_id,
            "execution_id": execution.execution_id,
        })
        # Parent must kill/reap this exact process; do not unwind into finally.
        while True:
            time.sleep(1)

    original_mark = service.db.mark_codex_oauth_refresh
    original_callback_started = settlement.callback_started

    def callback_started(execution):
        nonlocal callback_calls
        started = original_callback_started(execution)
        if started:
            callback_calls += 1
        return started

    def marker(*args, **kwargs):
        nonlocal hook_calls
        hook_calls += 1
        if hook_calls == 2:
            gate()
        return original_mark(*args, **kwargs)

    def update(*_args, **_kwargs):
        nonlocal hook_calls
        hook_calls += 1
        if hook_calls == 2:
            gate()

    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "_request_refresh", side_effect=refresh))
            stack.enter_context(patch.object(settlement, "callback_started", side_effect=callback_started))
            stack.enter_context(patch.object(service, "_sync_sub2_if_needed", return_value={"status": "disabled"}))
            stack.enter_context(patch.object(requests.sessions.Session, "request",
                                            side_effect=AssertionError("crash tests forbid remote network")))
            if request["case"] == "response-crash":
                stack.enter_context(patch.object(service, "_persist_refreshed_credential", side_effect=lambda *a, **k: gate()))
            elif request["case"] == "confirmed-crash":
                stack.enter_context(patch.object(service, "_update_account_state", side_effect=update))
            else:
                stack.enter_context(patch.object(service.db, "mark_codex_oauth_refresh", side_effect=marker))
            task_gateway._execute_operation_handler(service.TASK_TYPE, request["run_id"])
            raise AssertionError("original crash hook was not reached")
    finally:
        fixture.close()
        postgres.close_pools()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child-request", required=True)
    _child(parser.parse_args().child_request)
