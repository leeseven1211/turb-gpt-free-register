"""Offline regressions for account results crossing the settlement boundary."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core import db, operation_task_store
from core.accounts import completion_execution, operation_results, operation_settings, setup_execution
from core.accounts.deactivation import mail_scan
from core.accounts.email_change import service as email_change
from core.accounts.liveness import service as liveness
from core.accounts.plans import service as plans
from core.codex import retry_service
from core.operations import task_gateway
from core.runtime import capabilities


Pending = task_gateway.OperationSettlementPending


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    from core.storage import postgres

    def forbidden(*args, **kwargs):
        raise AssertionError("offline adapter test attempted database access")

    monkeypatch.setattr(postgres, "connect", forbidden)
    monkeypatch.setattr(postgres, "connect_dedicated", forbidden)
    monkeypatch.setattr(operation_task_store, "register_resource", lambda *args, **kwargs: {
        "id": 901, "resource_uuid": "fixture-resource",
    })
    monkeypatch.setattr(operation_task_store, "release_resource", lambda *args, **kwargs: True)


def context(*, data=None):
    ctx = SimpleNamespace(
        account_id=41, task_id=42, run_id=43, email="settlement@example.test",
        task_type="account_setup_retry", source_system="webui_runtime",
        run={"data": dict(data or {}), "trigger": "manual", "log_file": ""},
        config_snapshot={}, execution_fence={"run_id": 43},
        finished=False, last_result=None, report=Mock(), release_lease=Mock(),
        checkpoint=Mock(), is_cancel_requested=Mock(return_value=False),
        lease=Mock(return_value=nullcontext()),
        remote_request_started=Mock(), remote_request_receipt=Mock(),
        add_settlement_obligation=Mock(), register_cleanup=Mock(),
    )
    ctx.finish = Mock(side_effect=Pending("terminal ACK unavailable"))
    return ctx


def test_completion_pending_partial_does_not_rewrite_or_reenqueue_child():
    ctx = context()
    child = {
        "accepted": True, "task_id": 61, "run_id": 62, "source_system": "webui_runtime",
        "source_id": "account-completion-setup:42:43",
        "_setup_child_source_id": "account-completion-setup:42:43",
    }
    with (
        patch.object(setup_execution, "submit_native_account_setup_child", return_value=child) as submit,
        patch.object(db, "get_account", side_effect=AssertionError("sealed parent must not reread business")),
        patch.object(operation_task_store, "register_task_dependency") as dependency,
    ):
        with pytest.raises(Pending):
            completion_execution.run_account_completion_worker(
                ctx.email, account_id=41, task_id=42, task_trigger="manual",
                planned_steps=["password"], settings={}, context=ctx, reservation_held=False,
            )
    assert submit.call_count == 1
    assert ctx.finish.call_count == 1
    assert dependency.call_count == 0
    assert ctx.finish.call_args.args[0].status == "partial_success"


def test_setup_control_exception_never_becomes_remote_unknown():
    ctx = context(data={"steps": ["password"]})
    with (
        patch.object(operation_settings, "completion_settings_from_snapshot", return_value={}),
        patch.object(capabilities, "account_setup_unavailable", return_value=None),
        patch.object(retry_service, "run_twofa_worker", side_effect=Pending("cleanup pending")) as business,
    ):
        with pytest.raises(Pending):
            setup_execution.handle_native_account_setup(ctx)
    assert business.call_count == 1
    assert ctx.finish.call_count == 0
    assert ctx.remote_request_receipt.call_count == 0


def test_scan_pending_success_does_not_write_a_business_failure():
    ctx = context()
    with (
        patch.object(mail_scan.db, "get_account", return_value={
            "id": 41, "email": ctx.email, "email_source": "email_butler",
        }),
        patch.object(mail_scan, "scan_openai_deactivation", return_value={"ok": True, "detected": False}) as scan,
        patch.object(mail_scan.db, "update_account_deactivation_mail") as writeback,
    ):
        with pytest.raises(Pending):
            mail_scan._scan(41, "manual", task_id=42, operation_context=ctx)
    assert scan.call_count == 1
    assert [call.args[1]["status"] for call in writeback.call_args_list] == ["running", "success"]
    assert ctx.finish.call_count == 1
    assert ctx.finish.call_args.kwargs["status"] == "success"


def test_protocol_close_failure_is_observable():
    session = SimpleNamespace(session=SimpleNamespace(close=Mock(side_effect=OSError("close unconfirmed"))))
    with pytest.raises(OSError, match="close unconfirmed"):
        email_change._close_protocol_session(session)


def test_native_setup_declares_a_final_scope():
    ctx = context(data={"steps": ["password"]})
    with (
        patch.object(operation_settings, "completion_settings_from_snapshot", return_value={}),
        patch.object(capabilities, "account_setup_unavailable", return_value=None),
        patch.object(retry_service, "run_twofa_worker", return_value={"ok": False, "status": "unsupported"}),
    ):
        with pytest.raises(Pending):
            setup_execution.handle_native_account_setup(ctx)
    assert ctx.lease.call_args.kwargs["scope_kind"] == "final"


@pytest.mark.parametrize("bulk", [False, True])
def test_existing_child_is_declared_before_partial_parent_can_be_pending(bulk):
    ctx = context(data={"bulk_target_round_id": 71} if bulk else {})
    events = []
    obligations = []
    ctx.add_settlement_obligation.side_effect = lambda *args, **kwargs: (
        events.append("declared"), obligations.append((args, kwargs)),
    )

    def finish(result):
        events.append("finish")
        assert result.summary["completion_handoff"]["child_source_id"] == "61"
        raise Pending("ACK lost")

    ctx.finish.side_effect = finish
    with (
        patch.object(setup_execution, "submit_native_account_setup_child", return_value={
            "accepted": True, "task_id": 61, "run_id": 62,
            "source_system": "webui_runtime", "source_id": "setup-existing",
            "_setup_child_source_id": "setup-existing",
        }),
        patch.object(db, "get_account", side_effect=AssertionError("unexpected business replay")),
        patch.object(operation_task_store, "register_task_dependency") as register,
    ):
        with pytest.raises(Pending):
            completion_execution.run_account_completion_worker(
                ctx.email, account_id=41, task_id=42, task_trigger="manual",
                planned_steps=["password"], settings={}, context=ctx, reservation_held=False,
            )
    assert events == ["declared", "finish"]
    assert len(obligations) == 1
    args, kwargs = obligations[0]
    assert args == ("completion_dependency",)
    assert kwargs["payload"]["child_source_id"] == "61"
    assert kwargs["payload"]["parent_run_id"] == 43
    assert kwargs["payload"]["payload"]["remaining_steps"] == []
    assert kwargs["blocks_permit"] is False
    assert register.call_count == 0


def test_dependency_delivery_waits_for_parent_and_handles_fast_child_without_enqueue():
    payload = {
        "parent_source_system": "webui_runtime", "parent_source_id": "42",
        "parent_run_id": 43, "child_source_system": "webui_runtime",
        "child_source_id": "61", "dependency_type": "account_completion",
        "payload": {"parent_run_id": 43, "remaining_steps": []},
    }
    events = []
    with (
        patch.object(operation_task_store, "get_task", side_effect=[
            {"id": 42, "last_run_id": 43, "status": "running"},
            {"id": 42, "last_run_id": 43, "status": "partial_success"},
            {"id": 61, "status": "success", "result_summary": {"ok": True}},
        ]),
        patch.object(operation_task_store, "register_task_dependency", side_effect=lambda **kw: (
            events.append("edge") or {"id": 81, "status": "waiting"}
        )),
        patch.object(operation_task_store, "mark_task_dependency_ready", side_effect=lambda **kw: (
            events.append("ready") or [{"id": 81}]
        )),
        patch.object(task_gateway, "notify_dependency_ready", side_effect=lambda row: events.append("notify")),
        patch.object(setup_execution, "submit_native_account_setup_child", side_effect=AssertionError("child replay")),
    ):
        assert completion_execution.apply_settlement_dependency(payload) is False
        assert events == []
        assert completion_execution.apply_settlement_dependency(payload) is True
    assert events == ["edge", "ready", "notify"]


def test_completion_dependency_passes_original_parent_run_cas():
    payload = {
        "parent_source_system": "webui_runtime", "parent_source_id": "42",
        "parent_run_id": 43, "child_source_system": "webui_runtime",
        "child_source_id": "61", "dependency_type": "account_completion",
        "payload": {"parent_run_id": 43, "remaining_steps": []},
    }
    with (
        patch.object(operation_task_store, "get_task", return_value={
            "id": 42, "last_run_id": 43, "status": "partial_success",
        }),
        patch.object(operation_task_store, "register_task_dependency", return_value={
            "id": 81, "status": "superseded", "dependency_stale": True,
        }) as register,
    ):
        assert completion_execution.apply_settlement_dependency(payload) is True
    assert register.call_args.kwargs["expected_parent_run_id"] == 43


def test_email_close_pending_preserves_change_and_blocks_cross_family_child():
    from tests.accounts.test_email_change_reporting import EmailChangeReportingTests

    with EmailChangeReportingTests().scenario() as scenario:
        scenario.context.register_cleanup = Mock()
        scenario.begin.return_value.session.session.close.side_effect = OSError("actor still open")
        with patch.object(email_change, "_enqueue_live_check_child") as child:
            result = email_change._handle_email_change(scenario.context)
        assert result.status == "success"
        assert result.summary["email_change_confirmed"] is True
        assert result.summary["cleanup_pending"] is True
        assert child.call_count == 0
        cleanup = scenario.context.register_cleanup.call_args_list[0].args[0]
        scenario.begin.return_value.session.session.close.side_effect = None
        assert cleanup.release() is True
        assert child.call_count == 0


def test_auth_stack_consumed_close_failure_is_still_pending_and_exactly_retried():
    from contextlib import ExitStack
    from core.auth.email_guard import EmailAuthSession
    from core.storage.email import address_allocations

    actor = EmailAuthSession("target+derived@example.test", None, "fixture", "original", None)
    actor.row = {"id": 91, "fence": 3, "state": "active", "submission_state": "prepared"}
    actor.set_result({"ok": True})
    cleanup = email_change._EmailChangeCleanup()
    cleanup.target_auth = actor
    cleanup.writeback_confirmed = True
    cleanup.auth_stack = ExitStack()
    cleanup.auth_stack.callback(actor.close)
    with patch.object(address_allocations, "finish_otp_request", side_effect=[
        OSError("target close unknown"),
        {"id": 91, "fence": 3, "state": "confirmed"},
    ]) as finish_auth:
        assert cleanup.release() is False
        assert cleanup.release() is True
    assert finish_auth.call_count == 2
    assert [call.args for call in finish_auth.call_args_list] == [(91,), (91,)]


def test_plan_success_pending_does_not_overwrite_saved_plan():
    ctx = context()
    route = SimpleNamespace(proxy_url="", provider="synthetic", public_dict=lambda: {}, release=Mock())
    with (
        patch.object(plans.db, "mark_account_plan_check_running", return_value=True),
        patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
        patch.object(plans, "_query_account_plan", return_value={"ok": True, "current_plan_type": "plus"}) as query,
        patch.object(plans.db, "update_account_plan_check", return_value=True) as writeback,
        patch.object(plans, "_reconcile_extract_payment_after_plan"),
        patch.object(plans, "_log_plan_result"),
    ):
        with pytest.raises(Pending):
            plans._run_plan_check(
                account_id=41, email=ctx.email, access_token="fixture",
                trigger="manual", proxy=None, timezone_offset_min="-",
                task_id=42, operation_context=ctx, config_snapshot={},
            )
    assert query.call_count == 1
    assert writeback.call_count == 1
    assert writeback.call_args.kwargs["result"]["ok"] is True
    assert ctx.finish.call_count == 1
    assert ctx.finish.call_args.kwargs["status"] == "success"


@pytest.mark.parametrize("service", [plans, liveness])
def test_inline_reporter_never_seals_parent_operation(service):
    ctx = context()
    reporter = service._ReporterAdapter(42, ctx, finish_operation=False)
    reporter.finish(status="success", message="inline step done", result_summary={"ok": True})
    assert ctx.finish.call_count == 0
    assert ctx.report.call_count == 1


def test_accountless_manual_upload_uses_no_account_scope_and_runs_business_once():
    from core.integrations.sub2api import manual_upload

    ctx = context(data={"backend_identity": "synthetic"})
    ctx.account_id = None
    with (
        patch.object(manual_upload, "_bound_reference", return_value={"content": {}, "filename": "fixture.json"}),
        patch.object(manual_upload.client, "configured_backend_identity", return_value="synthetic"),
        patch.object(manual_upload.client, "upload_configured_codex_oauth_credential", return_value={}) as upload,
        patch.object(manual_upload, "_commit_upload", return_value="fixture.json") as writeback,
    ):
        result = manual_upload._handle(ctx)
    assert result.status == "success"
    assert upload.call_count == writeback.call_count == 1
    assert ctx.lease.call_count == 0
    assert ctx.finish.call_count == 0


def test_email_reauth_closes_both_original_and_replacement_protocol_sessions():
    from tests.accounts.test_email_change_reporting import EmailChangeReportingTests

    original = SimpleNamespace(session=SimpleNamespace(close=Mock()))
    replacement = SimpleNamespace(session=SimpleNamespace(close=Mock()))
    with EmailChangeReportingTests().scenario() as scenario:
        scenario.session_factory.return_value = original
        scenario.begin.return_value = email_change.BeginChangeResult(replacement, "fixture-at", 123.0, True)
        result = email_change._handle_email_change(scenario.context)
    assert result.status == "success"
    assert original.session.close.call_count == 1
    assert replacement.session.close.call_count == 1


def test_actor_cleanup_uses_captured_database_domain_after_environment_changes(monkeypatch):
    from core.operations.settlement_contracts import SettlementDomain
    from core.storage import postgres

    original = SettlementDomain("postgresql://synthetic/original", "original_operations", "original_records", "fixture")
    observed = []
    cleanup = email_change._EmailChangeCleanup()
    cleanup.domain = original
    cleanup.route = SimpleNamespace(release=lambda **kwargs: observed.append(
        (postgres.database_url(), postgres.schema_name()),
    ))
    monkeypatch.setenv("DATABASE_URL", "postgresql://synthetic/later")
    monkeypatch.setenv("TURB_DB_SCHEMA", "later_records")
    assert cleanup.release() is True
    assert observed == [("postgresql://synthetic/original", "original_records")]


def test_exact_route_cleanup_does_not_accept_swallowed_persistent_release_failure():
    from core.proxy.provider import ProxyLease
    from datetime import datetime

    lease = ProxyLease("original-proxy-lease", "synthetic", "", "synthetic:1", datetime.now(),
                       metadata={"persistent_lease": True})
    calls = []
    route = SimpleNamespace(
        lease=lease, provider="synthetic",
        release=lambda **kw: calls.append("provider-returned"),
    )
    helper = getattr(operation_results, "AccountRouteCleanup", None)
    assert helper is not None, "native account routes need an owned exact cleanup handle"
    cleanup = helper(route, run_id=43)
    class Cursor:
        def __init__(self):
            self.reads = iter([
                {"lease_id": "original-proxy-lease", "state": "leased"},
                {"lease_id": "original-proxy-lease", "state": "released"},
            ])
            self.rowcount = 1
            self.sql = []
        def execute(self, sql, params=()):
            self.sql.append((sql, params))
        def fetchone(self):
            return next(self.reads, None)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    cursor = Cursor()
    released_cursor = Cursor()
    released_cursor.reads = iter([{"lease_id": "original-proxy-lease", "state": "released"}])
    class Conn:
        def __init__(self, bound):
            self.bound = bound
        def cursor(self):
            return self.bound
        def commit(self):
            return None
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    with patch("core.storage.postgres.connect", side_effect=[
        Conn(cursor), OSError("original release still unconfirmed"), Conn(released_cursor),
    ]):
        with pytest.raises(task_gateway.OperationSettlementPending):
            cleanup.release()
        assert cleanup.release_confirmed is False
        assert cleanup.release() is True
    assert calls == ["provider-returned"]


def test_route_is_owned_before_resource_registration_can_fail():
    ctx = context()
    route = SimpleNamespace(provider="synthetic", lease=None, release=Mock())
    attach = getattr(operation_results, "own_account_route", None)
    assert attach is not None, "native route acquisition needs immediate cleanup ownership"
    with patch.object(operation_task_store, "register_resource", side_effect=OSError("resource DB outage")):
        with pytest.raises(task_gateway.OperationResourceCleanupPending):
            attach(ctx, route, purpose="plan-check")
    assert ctx.register_cleanup.call_count == 1
    handle = ctx.register_cleanup.call_args.args[0]
    assert handle.route is route
    assert handle.release() is True


def test_plan_late_route_failure_retains_frozen_success_and_exact_handle():
    ctx = context()
    successes = []
    ctx.finish.side_effect = lambda **result: successes.append(result)
    route = SimpleNamespace(
        proxy_url="", provider="synthetic", lease=None, public_dict=lambda: {},
        release=Mock(side_effect=[OSError("pool commit unavailable"), None]),
    )
    with (
        patch.object(plans.db, "mark_account_plan_check_running", return_value=True),
        patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
        patch.object(plans, "_query_account_plan", return_value={"ok": True, "current_plan_type": "plus"}) as query,
        patch.object(plans.db, "update_account_plan_check", return_value=True) as writeback,
        patch.object(plans, "_reconcile_extract_payment_after_plan"),
        patch.object(plans, "_log_plan_result"),
    ):
        with pytest.raises(task_gateway.OperationSettlementPending):
            plans._run_plan_check(
                account_id=41, email=ctx.email, access_token="fixture",
                trigger="manual", proxy=None, timezone_offset_min="-",
                task_id=42, operation_context=ctx, config_snapshot={},
            )
        assert [result["status"] for result in successes] == ["success"]
        assert query.call_count == writeback.call_count == 1
        assert ctx.register_cleanup.call_count == 1
        cleanup = ctx.register_cleanup.call_args.args[0]
        assert cleanup.route is route
        assert cleanup.release_confirmed is False
        assert cleanup.release() is True
        assert query.call_count == writeback.call_count == 1
    assert ctx.add_settlement_obligation.call_args.args == ("resource_release",)
    assert ctx.add_settlement_obligation.call_args.kwargs["blocks_permit"] is True


def test_email_actor_is_quiescent_while_original_proxy_cleanup_remains_owned():
    from tests.accounts.test_email_change_reporting import EmailChangeReportingTests
    from core.proxy.account_routes import AccountProxyRoute
    from core.proxy.provider import ProxyLease
    from datetime import datetime

    lease = ProxyLease("email-original", "1024proxy", "", "", datetime.now(),
                       metadata={"persistent_lease": True})
    route = AccountProxyRoute("", "1024proxy", "pool", lease=lease)
    with EmailChangeReportingTests().scenario() as scenario:
        scenario.proxy.return_value = route
        with (
            patch("core.storage.proxy.leases.release", side_effect=OSError("synthetic release unconfirmed")),
            patch.object(email_change, "_enqueue_live_check_child", return_value={"accepted": False}),
        ):
            result = email_change._handle_email_change(scenario.context)
        assert result.status == "success"
        assert result.summary["actor_quiescent"] is True
        assert result.summary["cleanup_pending"] is True
        actor, proxy = [
            call.args[0] for call in scenario.context.register_cleanup.call_args_list
        ]
        assert actor.release_confirmed is True
        assert proxy.release_confirmed is False
        assert proxy.route is route


def test_midcountry_cleanup_stops_next_country_and_carries_observed_unpersisted_fact():
    import time
    from core.storage.accounts import plan_countries

    ctx = context()
    ctx.execution_fence = {"run_id": 43}
    progress = {
        "deadline_at": time.time() + 120, "wait_limit": 60, "max_attempts": 2,
        "countries": {
            country: {"pending": True, "http_attempts": 0, "wait_used": 0,
                      "retry_not_before": 0, "wait_slice_deadline_at": time.time() + 60,
                      "history": []}
            for country in ("US", "CA")
        },
    }
    actions = []

    def update(_account, country, _progress, *, action, **kwargs):
        actions.append((country, action))
        if action == "http_start":
            progress["countries"][country]["http_attempts"] += 1
        return [], progress

    route = SimpleNamespace(
        proxy_url="", provider="synthetic", lease=None,
        public_dict=lambda: {"proxy_region": "US"},
        release=Mock(side_effect=OSError("exact first route unavailable")),
    )
    with (
        patch.object(plans, "configured_workers", return_value=3),
        patch.object(plan_countries, "initialize_country_checks", return_value=([], progress)),
        patch.object(plan_countries, "update_country_progress", side_effect=update),
        patch("core.proxy.account_routes.acquire_account_proxy", return_value=route) as acquire,
        patch.object(plans, "check_account_plan", return_value={"ok": True, "http_status": 200}) as query,
        patch.object(plans, "_wait_for_rate_slot"),
    ):
        with pytest.raises(task_gateway.OperationSettlementPending) as raised:
            plans._run_country_plan_checks(
                account_id=41, email=ctx.email, access_token="fixture",
                trigger="manual", proxy=None, timezone_offset_min="-", countries=["US", "CA"],
                reporter=Mock(), operation_context=ctx, config_snapshot={}, proxy_source=None,
                fence=ctx.execution_fence,
            )
    assert acquire.call_count == query.call_count == 1
    assert ("CA", "http_start") not in actions
    assert ("US", "result") not in actions
    assert raised.value.facts["observed_steps"][0]["country"] == "US"
    assert raised.value.facts["observed_steps"][0]["ok"] is True
    assert raised.value.facts["observed_steps"][0]["local_business_writeback_confirmed"] is False
    assert list(raised.value.facts["unexecuted_steps"]) == ["CA"]
    assert ctx.register_cleanup.call_args.args[0].release_confirmed is False


@pytest.mark.parametrize("original", [
    {"state": "shared_leased", "data": {"allow_reuse": True}, "expires_at": "2099-01-01T00:00:00"},
    {"state": "leased", "data": {}, "expires_at": "2000-01-01T00:00:00"},
    {"state": "recent", "data": {}, "expires_at": "2099-01-01T00:00:00", "recent_until": "2000-01-01T00:00:00"},
])
def test_original_shared_or_expired_persistent_release_does_not_extend_cooldown(original):
    from core.proxy.provider import ProxyLease
    from datetime import datetime
    from core.storage import postgres

    lease = ProxyLease("exact-original", "1024proxy", "", "", datetime.now(),
                       metadata={"persistent_lease": True, "recent_ttl": 300})
    route = SimpleNamespace(lease=lease, release=Mock(return_value=None))
    cleanup = operation_results.AccountRouteCleanup(route, run_id=43)
    writes = []

    def record_retry(**kwargs):
        writes.append(cleanup._recent_until)

    with (
        patch.object(cleanup, "_read_original", side_effect=[original, {"state": "released"}]),
        patch.object(cleanup, "_retry_original", side_effect=record_retry),
    ):
        assert cleanup.release() is True
    assert writes == ([] if original["state"] == "recent" else [None])
