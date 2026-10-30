"""验证可保存数值与真实消费者一致，并保留退出编辑页的环境变量兼容。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from config import codex as codex_config
from config import env_loader
from config import proxy as proxy_config
from config import schema
from core.accounts.plans import client as chatgpt_plan
from core.codex import token_refresh_service as codex_token_refresh_service
from core.accounts.liveness import service as live_check_service
from core.accounts.plans import service as plan_check_service
from core.registration import service as registration_service


# 对应 registration_service/live_check_service 的换线边界、chatgpt_plan 和
# plan_check_service 的请求边界，以及 codex_token_refresh_service 的调度边界。
RUNTIME_RANGES = (
    ("EXTRACT_LINK_BATCH_WORKERS", 1, 50),
    ("EXTRACT_LINK_LEGACY_CONCURRENCY", 1, 50),
    ("EXTRACT_LINK_LUMEN_FLOW_CONCURRENCY", 1, 50),
    ("EXTRACT_LINK_HUANGUANG_CONCURRENCY", 1, 50),
    ("REGISTRATION_PROXY_RETRIES", 0, 3),
    ("REGISTRATION_PROXY_RETRY_DELAY", 0, 10.0),
    ("ACCOUNT_ACTION_PROXY_RETRIES", 0, 3),
    ("ACCOUNT_ACTION_PROXY_RETRY_DELAY", 0, 10.0),
    ("PLAN_CHECK_TIMEOUT", 1.0, 60.0),
    ("PLAN_CHECK_MAX_ATTEMPTS", 1, 4),
    ("PLAN_CHECK_RETRY_DELAY", 0, 30.0),
    ("PLAN_CHECK_REGISTRATION_RECHECK_DELAY", 0, 30.0),
    ("PLAN_CHECK_MIN_INTERVAL", 0, 30.0),
    ("PLAN_CHECK_JITTER", 0, 30.0),
    ("CODEX_TOKEN_REFRESH_BEFORE_HOURS", 1, 720),
    ("CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS", 300, 86400),
    ("CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS", 10, 3600),
    ("CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", 1, 200),
)


@pytest.mark.parametrize("workers", (1, 20, 32, 50, 51, 100, 1000))
def test_saved_shared_account_budget_reaches_executor_without_lower_clamp(workers):
    from core.operations.executor import AccountOperationExecutor

    saved = schema.validate_config_updates({"ACCOUNT_BATCH_WORKERS": workers})
    with patch.object(codex_config, "ACCOUNT_BATCH_WORKERS", saved["ACCOUNT_BATCH_WORKERS"]):
        executor = AccountOperationExecutor()
        assert executor.workers() == workers
        assert executor.available_slots() == workers


@pytest.mark.parametrize("workers", (100, 1000))
def test_shared_account_budget_environment_is_published_without_upper_clamp(workers):
    with (
        patch.dict("os.environ", {"ACCOUNT_BATCH_WORKERS": str(workers)}, clear=True),
        patch.object(env_loader, "read_env_file", return_value={}),
        patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
    ):
        item = next(item for item in schema.effective_config_metadata() if item["key"] == "ACCOUNT_BATCH_WORKERS")
        assert item["invalid_env"] is False
        assert item["value"] == workers
        assert schema.resolve_config({"ACCOUNT_BATCH_WORKERS": str(workers)}, strict=True)["ACCOUNT_BATCH_WORKERS"].value == workers


def test_missing_runtime_settings_are_schema_fields_with_explicit_restart_semantics():
    expected = {
        "AT_REFRESH_BEFORE_HOURS": (1, 168),
        "AT_REFRESH_INITIAL_DELAY_SECONDS": (10, 3600),
        "AT_REFRESH_MAX_PER_CYCLE": (1, 200),
        "EMAIL_BUTLER_RISK_SCAN_INITIAL_DELAY_SECONDS": (5, 3600),
        "EMAIL_BUTLER_RISK_SCAN_LOOKBACK_DAYS": (1, 365),
        "OUTLOOK_API_BASE": (None, None),
        "EXTRACT_LINK_QUEUE_LIMIT": (1, 5000),
        "EXTRACT_LINK_REQUEST_TIMEOUT": (5, 300),
        "EXTRACT_LINK_EVENT_TIMEOUT": (30, 900),
    }
    fields = schema.CONFIG_SCHEMA
    for key, (lower, upper) in expected.items():
        field = fields[key]
        assert field.hot_edit == "restart" if key in {
            "AT_REFRESH_BEFORE_HOURS", "AT_REFRESH_INITIAL_DELAY_SECONDS",
            "AT_REFRESH_MAX_PER_CYCLE", "EMAIL_BUTLER_RISK_SCAN_INITIAL_DELAY_SECONDS",
            "EMAIL_BUTLER_RISK_SCAN_LOOKBACK_DAYS", "EXTRACT_LINK_QUEUE_LIMIT",
        } else field.hot_edit == "safe"
        if lower is not None:
            assert (field.min_value, field.max_value) == (lower, upper)


def test_extract_provider_payment_switches_are_editable_and_auto_payment_defaults_off():
    fields = schema.CONFIG_SCHEMA
    assert fields["EXTRACT_LINK_LUMEN_FLOW_ENABLED"].type == "bool"
    assert fields["EXTRACT_LINK_LUMEN_FLOW_CDK"].secret is True
    assert schema.schema_default("EXTRACT_LINK_DEFAULT_MODE") == "extract_only"
    assert schema.schema_default("EXTRACT_LINK_AUTO_PAYMENT_ENABLED") is False
    assert schema.schema_default("EXTRACT_LINK_LUMEN_FLOW_AUTO_PAYMENT_ENABLED") is False
    assert schema.schema_default("EXTRACT_LINK_DEFAULT_PROVIDER") == "legacy"
    assert schema.schema_default("EXTRACT_LINK_ENABLED") is True
    assert schema.schema_default("EXTRACT_LINK_LEGACY_ENABLED") is True
    assert schema.schema_default("EXTRACT_LINK_LEGACY_CONCURRENCY") == 1
    assert schema.schema_default("EXTRACT_LINK_HUANGUANG_ENABLED") is False
    for provider in ("LEGACY", "LUMEN_FLOW", "HUANGUANG"):
        assert fields[f"EXTRACT_LINK_{provider}_CONCURRENCY"].type == "int"
        assert fields[f"EXTRACT_LINK_{provider}_CONCURRENCY"].range == {"min": 1, "max": 50}


def test_extract_link_legacy_environment_names_are_reused_with_separate_payment_cdk():
    legacy_keys = {
        "EXTRACT_LINK_API_BASE", "EXTRACT_LINK_CDK", "EXTRACT_LINK_TYPE",
        "EXTRACT_LINK_REQUEST_TIMEOUT", "EXTRACT_LINK_EVENT_TIMEOUT",
    }
    assert legacy_keys.issubset(set(schema.CONFIG_SCHEMA.keys()))
    legacy_connection_keys = {
        key for key in schema.CONFIG_SCHEMA.keys()
        if key.startswith("EXTRACT_LINK_LEGACY_") and key.endswith(("API_BASE", "CDK", "TYPE", "REQUEST_TIMEOUT", "EVENT_TIMEOUT"))
    }
    assert legacy_connection_keys == {"EXTRACT_LINK_LEGACY_PAYMENT_CDK"}


def test_extract_link_cdk_values_are_never_returned_in_metadata_or_snapshot():
    secret = "extract-link-config-test-secret"
    with (
        patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
        patch.object(env_loader, "read_env_file", return_value={}),
        patch.dict("os.environ", {"EXTRACT_LINK_LUMEN_FLOW_CDK": secret}, clear=True),
    ):
        metadata = schema.effective_config_metadata()
        assert next(item for item in metadata if item["key"] == "EXTRACT_LINK_LUMEN_FLOW_CDK")["value"] == ""
        snapshot = schema.non_sensitive_snapshot().as_dict()
        assert secret not in str(metadata)
        assert secret not in str(snapshot)


@pytest.mark.parametrize("key,lower,upper", RUNTIME_RANGES)
def test_saved_runtime_ranges_accept_boundaries_and_reject_clipped_values(key, lower, upper):
    assert schema.validate_value(key, lower) == lower
    assert schema.validate_value(key, upper) == upper
    default = schema.schema_default(key)
    assert schema.validate_value(key, default) == default
    for outside in (lower - 1, upper + 1):
        with pytest.raises(schema.ConfigValidationError):
            schema.validate_config_updates({key: outside})


@pytest.mark.parametrize("key,lower,upper", RUNTIME_RANGES)
def test_previous_out_of_range_environment_is_visible_without_publishing_it(key, lower, upper):
    del lower
    with (
        patch.dict("os.environ", {key: str(upper + 1)}, clear=True),
        patch.object(env_loader, "read_env_file", return_value={}),
        patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
    ):
        item = next(item for item in schema.effective_config_metadata() if item["key"] == key)
        assert item["invalid_env"] is True
        assert item["pending_reload"] is True
        assert item["value"] == schema.schema_default(key)
        with pytest.raises(schema.ConfigValidationError):
            schema.resolve_config({key: str(upper + 1)}, strict=True)


@pytest.mark.parametrize(
    "key,consumer",
    (
        ("REGISTRATION_PROXY_RETRIES", registration_service._registration_proxy_retry_limit),
        ("REGISTRATION_PROXY_RETRY_DELAY", registration_service._registration_proxy_retry_delay),
        ("ACCOUNT_ACTION_PROXY_RETRIES", live_check_service._account_action_proxy_retry_limit),
        ("ACCOUNT_ACTION_PROXY_RETRY_DELAY", live_check_service._account_action_proxy_retry_delay),
    ),
)
def test_saved_proxy_retry_boundaries_are_not_changed_by_consumers(key, consumer):
    field = schema.CONFIG_SCHEMA[key]
    for value in (field.min_value, field.max_value):
        saved = schema.validate_value(key, value)
        with patch.object(proxy_config, key, saved):
            assert consumer() == saved


@pytest.mark.parametrize("boundary", ("min_value", "max_value"))
def test_saved_plan_request_boundaries_reach_the_request_settings_unchanged(boundary):
    keys = ("PLAN_CHECK_TIMEOUT", "PLAN_CHECK_MAX_ATTEMPTS", "PLAN_CHECK_RETRY_DELAY")
    values = {key: schema.validate_value(key, getattr(schema.CONFIG_SCHEMA[key], boundary)) for key in keys}
    with patch.multiple(proxy_config, **values):
        assert chatgpt_plan._plan_check_settings(None, None, None) == tuple(values.values())


@pytest.mark.parametrize("boundary", ("min_value", "max_value"))
def test_saved_plan_rate_and_recheck_boundaries_are_used_without_real_waits(boundary):
    keys = ("PLAN_CHECK_MIN_INTERVAL", "PLAN_CHECK_JITTER", "PLAN_CHECK_REGISTRATION_RECHECK_DELAY")
    values = {key: schema.validate_value(key, getattr(schema.CONFIG_SCHEMA[key], boundary)) for key in keys}
    with (
        patch.multiple(proxy_config, **values),
        patch.object(plan_check_service, "_NEXT_REQUEST_AT", 100.0),
        patch.object(plan_check_service.time, "monotonic", return_value=100.0),
        patch.object(plan_check_service.time, "sleep") as sleep,
        patch.object(plan_check_service.random, "uniform", side_effect=lambda _low, high: high),
    ):
        plan_check_service._wait_for_rate_slot()
        assert plan_check_service._NEXT_REQUEST_AT == 100.0 + values[keys[0]] + values[keys[1]]
        if values[keys[1]]:
            sleep.assert_called_once_with(values[keys[1]])
        else:
            sleep.assert_not_called()
        assert plan_check_service._registration_recheck_delay() == values[keys[2]]


@pytest.mark.parametrize("hours", (1, 720))
def test_saved_codex_refresh_window_controls_the_expiring_boundary(hours):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with patch.object(codex_config, "CODEX_TOKEN_REFRESH_BEFORE_HOURS", schema.validate_value(
        "CODEX_TOKEN_REFRESH_BEFORE_HOURS", hours,
    )):
        for extra_seconds, expected in ((0, "expiring"), (1, "valid")):
            content = {
                "access_token": "synthetic-access",
                "refresh_token": "synthetic-refresh",
                "expired": (now + timedelta(hours=hours, seconds=extra_seconds)).isoformat(),
            }
            assert codex_token_refresh_service.oauth_metadata(content, now=now)["oauth_status"] == expected


@pytest.mark.parametrize("boundary", ("min_value", "max_value"))
def test_saved_codex_scheduler_boundaries_reach_the_scheduler_unchanged(boundary):
    keys = ("CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS", "CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS")
    values = {key: schema.validate_value(key, getattr(schema.CONFIG_SCHEMA[key], boundary)) for key in keys}
    with (
        patch.multiple(codex_config, **values),
        patch.object(codex_token_refresh_service.scheduler_state, "run_periodic") as periodic,
    ):
        assert codex_token_refresh_service.scheduler_interval_seconds() == values[keys[0]]
        codex_token_refresh_service._scheduler_loop()
        assert periodic.call_args.kwargs["initial_delay_seconds"] == values[keys[1]]


@pytest.mark.parametrize("maximum", (1, 200))
def test_saved_codex_cycle_limit_bounds_the_actual_submissions(maximum):
    service = codex_token_refresh_service
    rows = [{"filename": f"synthetic-{index}.json"} for index in range(maximum + 1)]
    with (
        patch.object(codex_config, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True),
        patch.object(codex_config, "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", schema.validate_value(
            "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", maximum,
        )),
        patch.object(service.db, "list_codex_accounts", return_value=rows),
        patch.object(service, "_reconcile_abandoned_refresh_markers", return_value=0),
        patch.object(service, "_reconciliation_account_ids", return_value=set()),
        patch.object(service, "decorate_row", return_value={"oauth_status": "expiring", "oauth_refreshable": True}),
        patch.object(service, "_registered_account_id", return_value=1),
        patch.object(service, "enqueue_refresh", return_value={"accepted": True}) as enqueue,
    ):
        result = service.enqueue_due_credentials()
        assert result == {"started": maximum, "skipped": 1, "reconciled": 0}
        assert enqueue.call_count == maximum


@pytest.mark.parametrize(
    "workers,queue_limit,expected",
    (("7", "800", (7, 800)), ("0", "-1", (0, -1)), ("invalid", "invalid", (3, 500))),
)
def test_retired_plan_queue_keys_load_as_compatibility_values_only(workers, queue_limit, expected):
    keys = ("PLAN_CHECK_WORKERS", "PLAN_CHECK_QUEUE_LIMIT")
    namespace = {"__name__": "config.proxy", **{key: schema.schema_default(key) for key in keys}}
    with (
        patch.dict("os.environ", dict(zip(keys, (workers, queue_limit))), clear=True),
        patch.object(env_loader, "ensure_loaded"),
    ):
        schema.apply_env_namespace(namespace)
        assert tuple(namespace[key] for key in keys) == expected
        schema.resolve_config(dict(zip(keys, (workers, queue_limit))), strict=True)
    assert all(hasattr(proxy_config, key) for key in keys)
    assert not set(keys).intersection(item["key"] for item in schema.CONFIG_SCHEMA.editor_metadata())
    assert not set(keys).intersection(schema.CONFIG_SCHEMA.restart_keys())
    for key in keys:
        with pytest.raises(schema.ConfigValidationError):
            schema.validate_config_updates({key: 4})
