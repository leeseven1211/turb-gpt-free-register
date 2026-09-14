# Project optimization implementation status

Updated: 2026-09-14. Coordinator owns this file.

Heartbeat monitor: automation ID `automation`, active every 10 minutes in this
task. Notify only meaningful milestones, failures, required decisions, or final
completion; pause when all five streams are accepted.

## Scope and baseline

Implement the five accepted optimization proposals: safe row-level storage,
durable unified task execution and completion, canonical configuration,
shared authentication implementation, reproducible tests and releases.

Primary workspace is intentionally preserved. Integration branch:
`codex/project-optimization-20260914`; snapshot baseline: `56cd2e6`.
The baseline contains the user's 12 pre-existing modified files; these are not
optimization deliverables. No production restart, deployment, or remote push.

Implementation and integration use isolated worktrees and database
`turb_opt_20260914` on the existing shared PostgreSQL service. All data are
synthetic. Never connect tests to `turb_console` or read private account exports.

## Workstreams

| Stream | Owner | State | Acceptance |
| --- | --- | --- | --- |
| A Storage | Aquinas, Luna max | Running | No stale snapshot deletion/overwrite; atomic create/retry; concurrency tests |
| B Tasks | Goodall, Luna max | Running | Durable dispatch/recovery; automatic completion dependencies; bounded concurrency |
| C Configuration | Tesla, Luna max | Running | Canonical field schema, validation, explicit effective values/version |
| D Authentication | Hooke, Luna max | Running | Shared implementation independent of Roxy orchestration; contract tests |
| E Verification/release | Ohm, Luna max | Running | Reproducible dependency lock, isolated mandatory DB tests, readiness/release checks |

Agent IDs and worktrees:

- A `01a09f76-3ee4-7562-a94d-1c2f5a78ea11`: `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register-opt-storage-20260914`
- B `01a09f76-3fac-7072-9e0d-653f7ffcad00`: `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register-opt-tasks-20260914`
- C `01a09f76-4062-7b70-a591-e5456bf25ede`: `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register-opt-config-20260914`
- D `01a09f76-411b-76a2-87ff-f221bbcbdddb`: `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register-opt-auth-20260914`
- E `01a09f76-4325-7452-8904-f77dcbd83208`: `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register-opt-release-20260914`

Use local commits in each assigned worktree as integration artifacts. Agents
must preserve scope boundaries; coordinator resolves shared-interface concerns.

### Monitor checkpoint 2026-09-14 10:42 UTC

All five agents remain running and have implementation edits in their assigned
worktrees. None has returned a completed implementation commit or accepted test
result yet. Integration branch remains at the documented baseline plus this
coordination log. No milestone notification was issued for normal progress.

Coordinator reviewed in-progress storage, executor, and authentication changes.
Sent A review constraints about explicit optimistic-conflict handling, nested
JSON metadata filtering/compatibility, and cold-schema initialization. Sent D
constraints to decompose the extracted shared module by capability and remove
its application-service cancellation dependency. These are pre-merge checks,
not accepted changes or confirmed regressions in a finished deliverable.

Coordinator reviews every returned change, integrates nonconflicting commits,
runs combined checks, delegates corrections, and updates actual acceptance and
remaining work here. A completed agent is not equivalent to accepted delivery.

## Verification

Baseline full suite completed: **954 passed, 34 subtests passed, 3 failed in
148.96 seconds**. No implementation agent changes were included. Failures:

- `tests/test_email_butler_client.py::EmailButlerClientTests::test_scan_retries_one_transient_connection_error`: mocked network call lacks explicit fake API base when private dotenv is disabled.
- `tests/test_sub2api_sync.py::Sub2ApiSyncMappingTests::test_export_configured_accounts_reads_complete_account_list`: mocked network call lacks explicit fake API base.
- `tests/test_route_contract.py::FlaskRouteContractTests::test_public_route_map_matches_refactor_baseline`: expected 109 routes, actual baseline has 110; verify the explicit route delta before updating the contract.

These three baseline test fixes are delegated to E, including ownership of the
three named test files. Do not restore private dotenv or change business
defaults to satisfy them. Post-integration results pending. Test launcher (private local
coordination tool, no embedded credentials):
`/tmp/turb-optimization-20260914.mJ7Y6R/run.py <worktree> -m pytest -q ...`.
Run it with the primary workspace `.venv/bin/python`. It suppresses private
dotenv loading and selects only the isolated database.
