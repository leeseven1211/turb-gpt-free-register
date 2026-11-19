"""Offline producer contracts for proxy actors that may outlive their worker."""
from contextlib import nullcontext
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.accounts import operation_results
from core.accounts.email_change import service as email_change
from core.accounts.liveness import service as liveness
from core.accounts.plans import service as plans


class _OwnershipObserved(BaseException):
    """Stop at the registration boundary before any business request."""


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    from core.storage import postgres
    from curl_cffi import requests as curl_requests
    import requests

    def forbidden(*args, **kwargs):
        raise AssertionError("actor scope test attempted external I/O")

    monkeypatch.setattr(postgres, "connect", forbidden)
    monkeypatch.setattr(postgres, "connect_dedicated", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(curl_requests.Session, "request", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def _route():
    return SimpleNamespace(
        proxy_url="http://proxy.example.test:8080", provider="synthetic", lease=None,
        region="JP", release=Mock(),
        public_dict=lambda: {"network_route": "proxy", "proxy_region": "JP"},
    )


def _ownership_boundary(observed, *, stop_after=1):
    def register(context, route, *, purpose, actor_scope="external"):
        observed.append((purpose, actor_scope))
        if len(observed) == stop_after:
            raise _OwnershipObserved()
        return route

    return register


@pytest.mark.parametrize("explicit_proxy", [None, "http://same-chain.example.test:8080"])
@pytest.mark.parametrize(
    ("force_refresh", "driver", "fallback", "expected_scope"),
    [
        (False, "protocol_current", True, "owner_process"),
        (False, "browser_roxy", False, "external"),
        (False, "unknown_probe", False, "external"),
        (True, "v2", False, "owner_process"),
        (True, "v3", False, "owner_process"),
        (True, "v2", True, "external"),
        (True, "v3", True, "external"),
        (True, "browser_roxy", False, "external"),
        (True, "v1", False, "external"),
        (True, "unknown_refresh", False, "external"),
    ],
)
def test_liveness_registers_actual_actor_scope_before_using_route(
    explicit_proxy, force_refresh, driver, fallback, expected_scope,
):
    # A protocol task with browser fallback must not free a surviving browser.
    observed = []
    route = _route()
    snapshot = {
        "refresh_at_country": "JP",
        "auth_raw_context_enabled": False,
        "refresh_roxy_debug_enabled": False,
        "roxy_fallback_enabled": fallback,
        "proxy_retry_limit": 0,
    }

    def refresh(_email, **kwargs):
        kwargs["proxy_supplier"](1)
        raise AssertionError("ownership observation must stop the refresh")

    with (
        patch.object(liveness.db, "mark_account_live_check_running", return_value=True),
        patch.object(liveness.db, "get_account", return_value={
            "id": 7, "email": "scope@example.test", "access_token": "old-at",
        }),
        patch.object(liveness, "_reporter", return_value=Mock()),
        patch.object(liveness, "_append_log"),
        patch.object(liveness, "_checkpoint"),
        patch.object(liveness, "token_claims", return_value={}),
        patch.object(liveness, "_resolve_protocol_identity", return_value=None),
        patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
        patch.object(operation_results, "own_account_route", side_effect=_ownership_boundary(observed)),
        patch("core.accounts.liveness.protocol.v2.refresh_access_token", side_effect=refresh),
        patch("core.accounts.liveness.protocol.v3.refresh_access_token", side_effect=refresh),
        patch("core.accounts.liveness.roxy.flow.refresh_access_token", side_effect=refresh),
        patch.object(liveness, "check_account_liveness", side_effect=refresh),
    ):
        with pytest.raises(_OwnershipObserved):
            liveness._run_live_check(
                account_id=7, email="scope@example.test", proxy=explicit_proxy,
                trigger="offline", force_refresh=force_refresh,
                driver=None if force_refresh else driver,
                refresh_driver=driver if force_refresh else None,
                config_snapshot=snapshot,
            )

    assert observed == [("token-refresh" if force_refresh else "live-check", expected_scope)]


@pytest.mark.parametrize("snapshot", [
    None,
    {"refresh_at_country": "JP", "auth_raw_context_enabled": False},
])
def test_unfrozen_or_missing_fallback_snapshot_keeps_protocol_refresh_external(snapshot):
    observed = []
    route = _route()

    def refresh(_email, **kwargs):
        kwargs["proxy_supplier"](1)

    with (
        patch.object(liveness.db, "mark_account_live_check_running", return_value=True),
        patch.object(liveness.db, "get_account", return_value={
            "id": 7, "email": "scope@example.test", "access_token": "old-at",
        }),
        patch.object(liveness, "_reporter", return_value=Mock()),
        patch.object(liveness, "_append_log"),
        patch.object(liveness, "_checkpoint"),
        patch.object(liveness, "token_claims", return_value={}),
        patch.object(liveness, "_resolve_protocol_identity", return_value=None),
        patch.object(liveness, "_resolve_at_refresh_country", return_value="JP"),
        patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", False),
        patch("config.proxy.LIVE_CHECK_ROXY_FALLBACK_ENABLED", False),
        patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
        patch.object(operation_results, "own_account_route", side_effect=_ownership_boundary(observed)),
        patch("core.accounts.liveness.protocol.v3.refresh_access_token", side_effect=refresh),
    ):
        with pytest.raises(_OwnershipObserved):
            liveness._run_live_check(
                account_id=7, email="scope@example.test", proxy=None, trigger="offline",
                force_refresh=True, refresh_driver="v3",
                config_snapshot=snapshot,
            )

    assert observed == [("token-refresh", "external")]


@pytest.mark.parametrize("refresh_after_401", [False, True])
def test_single_plan_query_registers_each_local_route_as_owner_process(refresh_after_401):
    observed = []
    routes = [_route(), _route()]

    def refresh(token, *, reason):
        # Returning the query route must precede a potentially external refresh.
        assert routes[0].release.call_count == 1
        assert reason == "token_http_401"
        return "new-at"

    recovery = SimpleNamespace(
        summary={}, needs_refresh=lambda token: False,
        refresh=Mock(side_effect=refresh),
    )
    with (
        patch.object(plans.db, "mark_account_plan_check_running", return_value=True),
        patch.object(plans, "_checkpoint"),
        patch.object(plans, "_ReporterAdapter", return_value=Mock()),
        patch.object(plans, "_query_account_plan", return_value={"ok": False, "http_status": 401}),
        patch.object(plans, "_record_promotion_queries"),
        patch("core.proxy.account_routes.acquire_account_proxy", side_effect=routes),
        patch.object(operation_results, "own_account_route", side_effect=_ownership_boundary(
            observed, stop_after=2 if refresh_after_401 else 1,
        )),
    ):
        with pytest.raises(_OwnershipObserved):
            plans._run_plan_check(
                account_id=7, email="scope@example.test", access_token="old-at",
                trigger="manual", proxy=None, timezone_offset_min="-",
                config_snapshot={"payment_methods_enabled": False},
                at_recovery=recovery if refresh_after_401 else None,
            )

    assert observed == [("plan-check", "owner_process")] * (2 if refresh_after_401 else 1)
    if refresh_after_401:
        # The local query route is returned before recovery can launch a browser.
        assert routes[0].release.call_count == 1
        assert recovery.refresh.call_args.kwargs == {"reason": "token_http_401"}


def test_country_plan_query_registers_local_route_as_owner_process():
    from core.storage.accounts import plan_countries

    observed = []
    deadline = time.time() + 120
    progress = {
        "deadline_at": deadline, "wait_limit": 60, "max_attempts": 1,
        "countries": {"JP": {
            "pending": True, "http_attempts": 0, "wait_used": 0,
            "retry_not_before": 0, "wait_slice_deadline_at": deadline,
            "history": [],
        }},
    }
    with (
        patch.object(plans, "_checkpoint"),
        patch.object(plans, "configured_workers", return_value=1),
        patch.object(plan_countries, "initialize_country_checks", return_value=([], progress)),
        patch.object(plan_countries, "update_country_progress", return_value=([], progress)),
        patch("core.proxy.account_routes.acquire_account_proxy", return_value=_route()),
        patch.object(operation_results, "own_account_route", side_effect=_ownership_boundary(observed)),
    ):
        with pytest.raises(_OwnershipObserved):
            plans._run_country_plan_checks(
                account_id=7, email="scope@example.test", access_token="old-at",
                trigger="manual", proxy=None, timezone_offset_min="-", countries=["JP"],
                reporter=Mock(), operation_context=None, config_snapshot={
                    "payment_methods_enabled": False, "plan_check_max_attempts": 1,
                }, proxy_source=None,
            )

    assert observed == [("plan-check", "owner_process")]


def test_protocol_email_change_registers_route_as_owner_process():
    observed = []
    context = SimpleNamespace(
        account_id=7, run_id=29, task_id=30, email="old@example.test",
        run={"data": {"email_source": "outlook"}, "trigger": "offline"},
        config_snapshot={"email_change_enabled": True},
        report=Mock(), checkpoint=Mock(), lease=Mock(return_value=nullcontext()),
        register_cleanup=Mock(), add_settlement_obligation=Mock(),
    )
    with (
        patch.object(email_change, "db") as database,
        patch.object(email_change.email_provider, "validate_email_source", return_value="outlook"),
        patch.object(email_change, "_acquire_email_change_target", return_value=("new@example.test", None)),
        patch("core.auth.email_guard.email_auth_session", return_value=nullcontext()),
        patch("core.browser.traffic.record_unavailable"),
        patch.object(email_change, "acquire_account_proxy", return_value=_route()),
        patch.object(operation_results, "own_account_route", side_effect=_ownership_boundary(observed)),
    ):
        database.get_account.return_value = {
            "email": context.email, "access_token": "old-at", "email_source": "outlook",
        }
        database.claim_account_email_change.return_value = True
        with pytest.raises(_OwnershipObserved):
            email_change._handle_email_change(context)

    assert observed == [("email-change", "owner_process")]
