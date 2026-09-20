"""Profile selection helpers for the guarded pytest runner."""
from __future__ import annotations

PROFILES = ("default", "extended", "all")

DEFAULT_DATABASE_NODE_IDS = frozenset(
    {
        "tests/test_postgres_store.py::PostgresPrimaryStoreTests::test_read_prefers_postgres_payload_over_compatibility_file",
        "tests/test_postgres_store.py::PostgresPrimaryStoreTests::test_write_commits_postgres_and_refreshes_compatibility_file",
        "tests/test_record_store.py::RecordStoreSchemaTests::test_promoted_and_jsonb_fields_round_trip_as_one_flat_dict",
        "tests/test_record_store.py::AtomicClaimTests::test_only_one_of_many_concurrent_claims_wins",
        "tests/test_record_store.py::CrossTableTransactionTests::test_failure_rolls_back_both_tables",
        "tests/test_registration_storage.py::RegistrationFactsTests::test_job_links_one_attempt_and_retries_add_runs",
        "tests/test_registration_storage.py::RegistrationFactsTests::test_unknown_request_does_not_rewind_and_manual_reconcile_is_terminal",
        "tests/test_operation_task_store.py::OperationTaskStoreTests::test_native_submission_key_is_idempotent",
        "tests/test_operation_task_store.py::OperationTaskStoreTests::test_incremental_event_and_run_log_api_use_explicit_contract",
        "tests/test_webui_auth.py::WebUiAuthTests::test_api_requires_auth_code",
        "tests/test_webui_auth.py::WebUiAuthTests::test_api_accepts_auth_header",
    }
)

EXTENDED_PATHS = frozenset(
    {
        "tests/test_route_contract.py",
        "tests/test_release_checks.py",
        "tests/test_performance_checks.py",
        "tests/test_live_check_browser.py",
        "tests/test_test_runtime_budget.py",
    }
)


def marker_expression(profile: str) -> str | None:
    """Return the pytest marker expression for a supported profile."""
    if profile == "default":
        return "not extended"
    if profile == "extended":
        return "extended"
    if profile == "all":
        return None
    raise ValueError(f"未知测试 profile: {profile!r}")


def apply_profile(arguments: list[str], profile: str) -> list[str]:
    """Add the profile selector to pytest arguments without duplicating ``--``."""
    expression = marker_expression(profile)
    values = list(arguments)
    if values and values[0] == "--":
        values.pop(0)
    if any(value in {"-m", "--markexpr"} for value in values):
        raise ValueError("测试 profile 不能与 pytest -m/--markexpr 同时使用")
    if expression is not None:
        values.extend(["-m", expression])
    return values


def classify_node(relative_path: str, nodeid: str, *, is_postgres: bool) -> str | None:
    """Return the marker for a collected node, if it is extended-only."""
    if nodeid in DEFAULT_DATABASE_NODE_IDS:
        return None
    if is_postgres or relative_path in EXTENDED_PATHS:
        return "extended"
    return None
