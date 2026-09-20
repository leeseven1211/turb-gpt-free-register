# Local Test Suite Streamlining Implementation Plan

> For agentic workers: use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make the normal isolated local regression profile pass in at most 60 seconds while retaining rare database, recovery, migration, concurrency, performance, and release checks for explicit execution.

**Architecture:** Add a small pure profile/classification module, apply an extended marker during pytest collection, and let the guarded PostgreSQL runner select default, extended, or all. Keep all tests available; move expensive PostgreSQL classes and a small set of diagnostic contracts to extended, and keep an explicit database smoke allowlist in default. Remove artificial test waits before measuring the budget.

**Tech Stack:** Python 3.10+, pytest 9, unittest-compatible tests, local PostgreSQL through tools/test_isolated.py.

**Spec:** docs/superpowers/specs/2026-09-20-local-test-suite-streamlining-design.md

## Global Constraints

- Default isolated profile: three consecutive runs at no more than 60.00 seconds on the current Mac; target 45 seconds or less.
- tools/test_isolated.py remains canonical and must reject production-like or non-local databases.
- Extended tests remain runnable and isolated; no test contacts real providers or production data.
- No application runtime behavior, production timeout, account workflow, or deployment behavior changes.
- No test deletion without documenting its protected production break and retained replacement coverage.
- No pytest-xdist or other parallel dependency in the first implementation.
- Manual live tools under tools/ remain opt-in and outside pytest profiles.

## Review Focus

- Profile selection must not silently run zero tests or ignore an explicit node.
- PostgreSQL smoke tests must cover schema/row storage, registration/run durability, one operation path, and WebUI authorization.
- New database tests must not silently expand the default budget.
- Browser tests must stop real wall-clock waits only in tests; production timeout behavior stays unchanged.
- The guarded runner must retain environment sanitization and production-database refusal.

### Task 1: Add Profile Parsing and Runner Selection

**Files:**
- Create: tools/test_profiles.py
- Modify: tools/test_isolated.py:376-429
- Modify: pyproject.toml:7-10
- Create: tests/test_test_profiles.py
- Modify: tests/test_config_test_isolation.py

**Interfaces:**
- tools.test_profiles.PROFILES = ("default", "extended", "all")
- marker_expression(profile) returns "not extended", "extended", or None.
- apply_profile(arguments, profile) appends the profile marker and rejects a conflicting caller -m filter.
- test_isolated.py accepts --profile with default "default" and prints a redacted elapsed-time result after pytest exits.

- [ ] Step 1: Write failing tests. Assert:
  - apply_profile(["-q"], "default") == ["-q", "-m", "not extended"]
  - apply_profile(["-q"], "extended") == ["-q", "-m", "extended"]
  - apply_profile(["-q"], "all") == ["-q"]
  - unknown profiles and caller-supplied -m filters raise ValueError.
  Add a parser test proving omission selects default and --profile extended is consumed before pytest arguments.
- [ ] Step 2: Run
  PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest -q tests/test_test_profiles.py tests/test_config_test_isolation.py
  Expected: RED because the profile module and parser option do not exist.
- [ ] Step 3: Implement the pure helpers, parser option, marker registration in pyproject.toml, and monotonic runner timing. Preserve pytest's exit code and existing isolated environment behavior.
- [ ] Step 4: Re-run the focused tests and confirm GREEN with no marker warnings.
- [ ] Step 5: Commit:
  git add tools/test_profiles.py tools/test_isolated.py pyproject.toml tests/test_test_profiles.py tests/test_config_test_isolation.py
  git commit -m "test: add isolated regression profiles"

### Task 2: Classify Collection Items and Keep a Database Smoke Set

**Files:**
- Modify: tests/conftest.py:1-42
- Modify: tools/test_profiles.py
- Modify: tests/test_test_profiles.py
- Create: tests/test_profile_collection.py

**Interfaces:**
- DEFAULT_DATABASE_NODE_IDS is an immutable set of the 11 default database smoke nodes below.
- classify_node(relative_path, nodeid, is_postgres) returns "extended" or None.
- pytest_collection_modifyitems adds the registered marker without changing test bodies.

The default database smoke nodes are:

- tests/test_postgres_store.py::PostgresPrimaryStoreTests::test_read_prefers_postgres_payload_over_compatibility_file
- tests/test_postgres_store.py::PostgresPrimaryStoreTests::test_write_commits_postgres_and_refreshes_compatibility_file
- tests/test_record_store.py::RecordStoreSchemaTests::test_promoted_and_jsonb_fields_round_trip_as_one_flat_dict
- tests/test_record_store.py::AtomicClaimTests::test_only_one_of_many_concurrent_claims_wins
- tests/test_record_store.py::CrossTableTransactionTests::test_failure_rolls_back_both_tables
- tests/test_registration_storage.py::RegistrationFactsTests::test_job_links_one_attempt_and_retries_add_runs
- tests/test_registration_storage.py::RegistrationFactsTests::test_unknown_request_does_not_rewind_and_manual_reconcile_is_terminal
- tests/test_operation_task_store.py::OperationTaskStoreTests::test_native_submission_key_is_idempotent
- tests/test_operation_task_store.py::OperationTaskStoreTests::test_incremental_event_and_run_log_api_use_explicit_contract
- tests/test_webui_auth.py::WebUiAuthTests::test_api_requires_auth_code
- tests/test_webui_auth.py::WebUiAuthTests::test_api_accepts_auth_header

All other current PostgresTestCase items are extended. The following non-PostgreSQL modules are also extended: tests/test_route_contract.py, tests/test_release_checks.py, tests/test_performance_checks.py, and tests/test_live_check_browser.py.

- [ ] Step 1: Write failing tests for allowlisted nodes, arbitrary PostgreSQL nodes, listed diagnostic paths, ordinary unit paths, and the collection hook's marker assignment.
- [ ] Step 2: Run
  PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest -q tests/test_profile_collection.py tests/test_test_profiles.py
  Expected: RED because classification and the collection hook do not exist.
- [ ] Step 3: Implement immutable path/node sets in tools/test_profiles.py. In tests/conftest.py, derive each item's tests/... path, detect PostgresTestCase through its class MRO without database initialization, call classify_node, and add pytest.mark.extended when required.
- [ ] Step 4: Collect the five smoke files and verify default selects 11 nodes while extended selects the other 72. Run one default and one extended invocation against those files.
- [ ] Step 5: Commit:
  git add tools/test_profiles.py tests/conftest.py tests/test_test_profiles.py tests/test_profile_collection.py
  git commit -m "test: classify expensive regression cases"

### Task 3: Remove Artificial Browser and Humanized Test Waits

**Files:**
- Modify: tests/test_roxy_phone_country.py:235-246
- Modify: tests/test_password_reset_flow.py
- Modify: tests/test_account_change_actions.py
- Create: tests/test_test_runtime_budget.py

**Interfaces:** No production interface changes. The timing regression test runs the existing slow login node and asserts it finishes under 3 seconds with the isolated local database available.

- [ ] Step 1: Write a subprocess timing test for
  tests/test_roxy_phone_country.py::RoxyPhoneCountryTests::test_login_password_page_without_saved_password_fails_before_phone
  using the guarded local test environment. The current real wait must exceed the threshold.
- [ ] Step 2: Run
  .venv/bin/python -m pytest -q tests/test_test_runtime_budget.py::test_passwordless_login_regression_is_fast
  Expected: RED because the node currently takes about 25 seconds.
- [ ] Step 3: Patch only test-side clocks and delays. Patch _safe_get and the NextAuth fallback to controlled unsuccessful results; patch imported time.time, time.monotonic, and time.sleep to advance a fake clock. Patch core.roxy_codex_oauth.human_delay in both password-reset tests. Do not change production timeout constants or retry branches.
- [ ] Step 4: Run
  .venv/bin/python -m pytest -q tests/test_test_runtime_budget.py tests/test_roxy_phone_country.py tests/test_password_reset_flow.py tests/test_account_change_actions.py
  Confirm the timing node is under 3 seconds and all behavior assertions pass.
- [ ] Step 5: Commit:
  git add tests/test_test_runtime_budget.py tests/test_roxy_phone_country.py tests/test_password_reset_flow.py tests/test_account_change_actions.py
  git commit -m "test: remove real waits from browser regressions"

### Task 4: Audit Low-Value Contracts Without Broad Deletion

**Files:**
- Review: tests/test_route_contract.py
- Review: tests/test_ui_performance_contract.py
- Review: tests/test_proxy_traffic_ui.py
- Review: tests/test_registration_capabilities.py
- Review: tests/test_storage_boundaries.py
- Review: tests/test_legacy_schema_alignment.py
- Modify only candidates that fail the reduction rules.

- [ ] Step 1: For each candidate, name the production break it catches. Keep behavioral route, authorization, secret-redaction, compatibility, and storage-boundary tests. Replace source-text assertions only when a real boundary assertion can replace them.
- [ ] Step 2: Before replacing any source check, add the real boundary assertion, run it RED against the old behavior, then remove only the redundant source assertion. Do not delete an entire file solely to lower the count.
- [ ] Step 3: Run
  .venv/bin/python -m pytest -q tests/test_route_contract.py tests/test_ui_performance_contract.py tests/test_proxy_traffic_ui.py tests/test_registration_capabilities.py tests/test_storage_boundaries.py tests/test_legacy_schema_alignment.py
- [ ] Step 4: Commit only verified reductions:
  git add tests
  git commit -m "test: consolidate redundant contract checks"
  If no safe reduction is found, make no commit for this task and report that result.

### Task 5: Verify the Budget, Retained Extended Set, Main, and Service

**Files:** Inspect the profile runner, collection hook, pyproject marker registration, and committed tests. Modify only if verification finds a classification defect.

- [ ] Step 1: Run:
  PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest -q tests/test_test_profiles.py tests/test_profile_collection.py tests/test_config_test_isolation.py
  .venv/bin/python -m compileall -q tools/test_isolated.py tools/test_profiles.py tests/conftest.py
  git diff --check HEAD~4..HEAD
- [ ] Step 2: Resolve the private local DSN to non-production turb_dev without printing credentials and run the default isolated profile three times:
  tools/test_isolated.py --profile default -- -q
  Each run must be non-zero and <=60.00 seconds.
- [ ] Step 3: Run the retained extended profile and verify the all-profile collection is exactly the union:
  tools/test_isolated.py --profile extended -- -q
  tools/test_isolated.py --profile all -- --collect-only -q
- [ ] Step 4: Review status, stage only profile/test changes, commit on local main:
  git commit -m "test: streamline local regression profiles"
  Verify git branch --show-current is main. Do not push unless separately requested.
- [ ] Step 5: Restart and verify the local WebUI:
  PORT=8000 ./webui.sh stop
  PORT=8000 ./webui.sh start
  PORT=8000 ./webui.sh status
  curl -fsS http://127.0.0.1:8000/healthz
  curl -fsS http://127.0.0.1:8000/readyz
  Confirm the serving process comes from the current main checkout and both endpoints report success.
