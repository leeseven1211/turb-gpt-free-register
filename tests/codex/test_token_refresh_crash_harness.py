"""Offline harness contracts; no child, socket, PostgreSQL or stale acceptance."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.codex import support_token_refresh_crash as harness


@pytest.fixture(autouse=True)
def no_live_actions(monkeypatch):
    from core.storage import postgres
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setattr(postgres, "connect", Mock(side_effect=AssertionError("offline DB forbidden")))
    monkeypatch.setattr(harness.subprocess, "Popen", Mock(side_effect=AssertionError("offline child forbidden")))


def cohort(tmp_path, monkeypatch):
    monkeypatch.setattr(harness.tempfile, "mkdtemp", lambda **kwargs: str(tmp_path))
    monkeypatch.setattr(harness, "source_hashes", lambda: {"test-source": "fixed"})
    monkeypatch.setattr(harness, "_write", Mock())
    return harness.CodexCrashCohort()


def test_new_session_never_reuses_artifact_pass_or_class_state(tmp_path, monkeypatch):
    first = cohort(tmp_path, monkeypatch)
    second = harness.CodexCrashCohort()
    assert first is not second and first.nonce != second.nonce
    assert first.cases is not second.cases
    assert first.phase == second.phase == "new"
    assert harness.STALE_SECONDS == 900
    assert harness.LEASE_SECONDS == 600
    assert len(harness.METHOD_CASES) == len(harness.CASES) == 3


def test_source_drift_refuses_before_preparing_or_spawning(tmp_path, monkeypatch):
    session = cohort(tmp_path, monkeypatch)
    monkeypatch.setattr(harness, "source_hashes", lambda: {"test-source": "changed"})
    monkeypatch.setattr(session, "_prepare", Mock())
    with pytest.raises(AssertionError, match="source changed"):
        session.ensure_ready()
    session._prepare.assert_not_called()
    assert session.phase == "new"


def test_ready_phase_cannot_hide_recovery_or_unknown_source(tmp_path, monkeypatch):
    session = cohort(tmp_path, monkeypatch)
    session.phase = "ready"
    prepare = Mock(side_effect=AssertionError("READY must not prepare again"))
    monkeypatch.setattr(session, "_prepare", prepare)
    assert session.ensure_ready() is session
    prepare.assert_not_called()
    monkeypatch.setattr(harness, "source_hashes", lambda: {"different": "source"})
    with pytest.raises(AssertionError, match="source changed"):
        session.ensure_ready()


def test_case_may_be_claimed_once_without_consuming_recovery(tmp_path, monkeypatch):
    from core.storage.operations import runtime
    session = cohort(tmp_path, monkeypatch)
    case = harness.CrashCase("response-crash", "test_current", tmp_path)
    session.cases[case.name] = case
    session.phase = "ready"
    monkeypatch.setattr(session, "_assert_prestate", Mock())
    recover = Mock(side_effect=AssertionError("claim must not recover"))
    monkeypatch.setattr(runtime, "recover_interrupted_runtime_runs", recover)
    assert session.claim(case.name) is case
    assert case.claimed and not case.asserted
    with pytest.raises(AssertionError, match="only once"):
        session.claim(case.name)
    recover.assert_not_called()


def test_failed_phase_cannot_retry_to_pass(tmp_path, monkeypatch):
    session = cohort(tmp_path, monkeypatch)
    session.phase = "failed"
    with pytest.raises(AssertionError, match="cannot restart"):
        session.ensure_ready()


def test_shared_wait_reaches_ready_without_consuming_native_recovery(tmp_path, monkeypatch):
    from core.storage import postgres
    from core.storage.operations import runtime
    session = cohort(tmp_path, monkeypatch)
    monkeypatch.setattr(postgres, "database_url", lambda: "postgresql://u:p@127.0.0.1:55432/turb_test")
    monkeypatch.setattr(runtime, "recover_interrupted_runtime_runs",
                        Mock(side_effect=AssertionError("wait must not recover")))

    def prepare(name):
        case = harness.CrashCase(name, f"test_{name.replace('-', '_')}", tmp_path)
        session.cases[name] = case
        return case

    monkeypatch.setattr(session, "_prepare", prepare)
    killed = Mock()
    monkeypatch.setattr(session, "_launch_and_kill", killed)
    monkeypatch.setattr(session, "_assert_origin", Mock())
    observations = iter([899.0] * 3 + [901.0] * 3)
    monkeypatch.setattr(session, "_snapshot", lambda case: {
        "run": {"status": "settling"}, "heartbeat_age": next(observations),
        "observed_at": "synthetic-observation", "leases": [],
    })
    monkeypatch.setattr(harness.time, "sleep", Mock())
    assert session.ensure_ready() is session
    assert session.phase == "ready" and killed.call_count == 3
    harness.time.sleep.assert_called_once_with(2)
    runtime.recover_interrupted_runtime_runs.assert_not_called()
    assert not any(case.claimed or case.asserted for case in session.cases.values())


def test_prepare_uses_native_task_with_embedded_run_return_shape(tmp_path, monkeypatch):
    from core import account_task_store, db
    from core.storage import postgres, records
    from core.storage.operations import permits, store
    session = cohort(tmp_path, monkeypatch)
    for module, name in (
        (postgres, "reset_cache"), (postgres, "ensure_schema"),
        (records, "reset_ready"), (records, "init"),
        (account_task_store, "init"), (store, "reset_ready"),
        (store, "init"), (permits, "ensure_tables"),
        (db, "save_codex_credential_record"),
    ):
        monkeypatch.setattr(module, name, Mock())
    monkeypatch.setattr(records, "insert_row", Mock(return_value=41))
    # This is the real create_runtime_task return contract, not {"task": ...}.
    create = Mock(return_value={"id": 71, "run": {
        "id": 81, "run_uuid": "native-run-uuid", "task_id": 71,
    }})
    monkeypatch.setattr(store, "create_runtime_task", create)
    case = session._prepare("response-crash")
    assert (case.account_id, case.task_id, case.run_id, case.run_uuid) == (
        41, 71, 81, "native-run-uuid")
    assert session.cases[case.name] is case and case.prepared
    assert create.call_args.kwargs["source_id"].startswith(session.nonce + ":")


def test_incomplete_close_retains_schema_and_never_fakes_pass(tmp_path, monkeypatch):
    from tests import support_pg
    session = cohort(tmp_path, monkeypatch)
    case = harness.CrashCase("response-crash", "test_incomplete", tmp_path)
    session.cases[case.name] = case
    session.phase = "failed"
    drop = Mock(side_effect=AssertionError("pending schema must survive"))
    monkeypatch.setattr(support_pg, "drop_schema", drop)
    with pytest.raises(AssertionError, match="retained"):
        session.close()
    assert not session.closed and not case.asserted
    drop.assert_not_called()


def test_kill_refuses_changed_physical_identity(tmp_path, monkeypatch):
    from core.runtime import role_launcher
    session = cohort(tmp_path, monkeypatch)
    process = SimpleNamespace(pid=123, send_signal=Mock(), wait=Mock())
    peer = {"process": process, "identity": {"pid": 123, "process_start": "original"}}
    changed = SimpleNamespace(pid=123, process_start="different")
    monkeypatch.setattr(role_launcher, "inspect_process", lambda pid: changed)
    monkeypatch.setattr(harness, "asdict", lambda info: vars(info))
    with pytest.raises(AssertionError):
        session._kill(peer)
    process.send_signal.assert_not_called()
    process.wait.assert_not_called()


def test_class_scratch_truncate_contract_is_not_overridden():
    import ast
    module = harness.ROOT / "tests/codex/test_codex_token_refresh_durable.py"
    tree = ast.parse(module.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "CodexTokenRefreshDurablePostgresTests")
    methods = {node.name for node in cls.body if isinstance(node, ast.FunctionDef)}
    assert len([name for name in methods if name.startswith("test_")]) == 13
    assert not {"run", "_callTestMethod"}.intersection(methods)
    source = ast.get_source_segment(module.read_text(), cls)
    assert "self.schema =" not in source
    assert "cls.schema =" not in source
    assert "interval '1 hour'" in source  # Legacy test remains; crash trio no backdate.
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name in harness.METHOD_CASES:
            body = ast.get_source_segment(module.read_text(), node)
            assert "heartbeat_at=" not in body and "SystemExit" not in body
            assert "self.assertEqual(1, operation_runtime_store.recover_interrupted_runtime_runs())" in body
