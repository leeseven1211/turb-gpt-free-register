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
| A Storage | Coordinator; Aquinas reassigned to maintenance | First round integrated; nested metadata corrections in progress | No stale snapshot deletion/overwrite; atomic create/retry; concurrency tests |
| B Tasks | Goodall, Luna max; Aquinas/Hooke service adapters | Phase 2 implementing actual maintenance migrations | Durable dispatch/recovery; automatic completion dependencies; bounded concurrency |
| C Configuration | Tesla, Luna max | First round integrated; dedicated writer/schema corrections in progress | Canonical field schema, validation, explicit effective values/version |
| D Authentication | Hooke, Luna max | First round integrated; combined regressions passed | Shared implementation independent of Roxy orchestration; contract tests |
| E Verification/release | Ohm, Luna max | First round integrated; real performance measurements and environment tests in progress | Reproducible dependency lock, isolated mandatory DB tests, readiness/release checks |

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

### Monitor checkpoint 2026-09-14 10:54 UTC

All five agents are still implementing, with no final commits returned. Changes
now include row-scoped storage transactions, task dispatcher/dependency support,
configuration schema, authentication capability modules, and lock/test tooling.
No changes have been integrated or accepted yet.

Coordinator sent concrete pre-merge review requirements: B must remove double
claiming of resumed dependencies and keep continuations inside the concurrency
budget; C must remove config-to-WebUI dependencies, publish values and revision
as one immutable snapshot, and explicitly disable dotenv loading in test mode;
E must resolve around the verified runtime rather than arbitrarily downgrade
dependencies and test the actual locked environment. Runtime health and config
snapshot interfaces have been relayed between B, C, and E. No normal-progress
user notification was issued.

### Monitor checkpoint 2026-09-14 11:06 UTC

All five agents remain running; targeted regression tests and implementation
documents are now being added. No final implementation commit or integrated
test result has been returned. A has removed normal snapshot-write call sites
and added explicit conflict handling; C has moved field definitions into config
and documented the immutable-snapshot versus legacy-constant boundary; D has
split the extracted capabilities into domain modules. These remain unaccepted
until committed and verified.

Coordinator requested stronger A concurrency tests through changed business
entrypoints (not only already-atomic low-level record helpers) and E readiness
tests where startup succeeded but a required worker is now dead/missing. The
latter must yield HTTP 503 instead of trusting the historical ready flag.

### Monitor checkpoint 2026-09-14 11:18 UTC

All five agents are running, adding regressions and release tooling. No final
implementation commit has been returned, so none has been integrated. B's draft
explicitly identifies all legacy maintenance types still requiring native
handler migration; the infrastructure stage will not count as full acceptance
of stream B.

Coordinator compared real B/C code and found their in-progress snapshot
contracts differed: C publishes `revision` with uppercase schema keys while B
expected `version` with lowercase execution keys. B is assigned the explicit,
allowlisted projection and actual-object contract test. C is assigned separate
configured-versus-published effective values and sensitive proxy-pool coverage.
The verified runtime package versions have been incorporated into E's lock
inputs; installation and testing of that lock remain pending.

Coordinator reviews every returned change, integrates nonconflicting commits,
runs combined checks, delegates corrections, and updates actual acceptance and
remaining work here. A completed agent is not equivalent to accepted delivery.

### Integrated first round and phase 2 checkpoint 2026-09-14 12:14 UTC

All five first-round commits were reviewed and cherry-picked without conflicts:

| Stream | Agent commit | Integration commit |
| --- | --- | --- |
| A | 24b9d3535e8961ca28ca28ba5c7295ec9ab5af90 | a071a17 |
| C | fd339076e78affcea6effe20ef63c472f94821e0 | a615162 |
| B | d289b192ebccc9aa9808a18a716ebdd3c18ba134 | 0d964ee |
| D | 40d8b78a2523252c75998c7905429e9bd6297ca7 | 2d143eb |
| E | 09abfcfaf9596f304454466d27e3ca4255b3d08a | b8c790f |

Integrated full suite: **1012 passed, 617 subtests passed, 3 failed in 141.24s**.
The three inherited baseline failures were fixed; these are integration issues:

- Config isolation fixture used an invalid enum value; C/E are coordinating a
  legal v2 override plus explicit invalid-value regression.
- Snapshot adapter test replaced only sys.modules, leaving config.schema's
  cached package attribute intact. Coordinator replaced it with the real
  ConfigSnapshot/provider boundary; all 3 gateway dispatcher tests now pass.
- C added /api/config/snapshot after E's route hash. E will verify that exact
  route delta and update the fixed count/hash, without weakening the contract.

First-round E lock was installed/tested with Python 3.12.13 on macOS x86_64;
Linux CI has not run remotely. Its queue p95=40ms used generated numbers, not
measured execution timings, so coordinator rejected that as performance
acceptance evidence. E is replacing it with an actual synthetic queue workload
and real UI repository/list measurements.

Storage review found remaining serialized extra_json read/modify/write races
in password, MFA and session updates, plus derived/default upsert and generated
field filtering gaps. Coordinator owns fixes in record_store/db_legacy and a
deterministic database-blocking concurrency test; results pending.

Phase 2 worktrees all start at b8c790f; same five Luna max agents, disjoint scope:

- A: `../turb-gpt-free-register-opt-maintenance-phase2-20260914`: live_check,
  token refresh producer, plan_check, deactivation_mail, extract_link services
  and dedicated tests/docs. No shared gateway/runtime/storage changes.
- B: `../turb-gpt-free-register-opt-tasks-phase2-20260914`: shared durable
  maintenance handler contract, gateway/storage/runtime, account setup and
  completion/registration handoffs. Supplies an early helper commit to A/D.
- C: `../turb-gpt-free-register-opt-config-phase2-20260914`: schema/config and
  dedicated configuration writer consistency, including CloudMail routes.
- D: `../turb-gpt-free-register-opt-token-phase2-20260914`: Codex token refresh
  durable adapter, preserving unknown refresh-token rotation outcomes.
- E: `../turb-gpt-free-register-opt-release-phase2-20260914`: real benchmark,
  complete schema-aware environment isolation, exact route contract correction.

Primary HEAD remains f33e523. Its dirty file count has increased from the
12-file snapshot to 13, including core/registration/roxy.py; these are external
changes, not this integration's edits, and are intentionally not overwritten.
No production service restart, deployment, source-worktree merge, or push.

### Coordinator storage correction checkpoint 2026-09-14 12:24 UTC

The coordinator's nested metadata/derived state/identity corrections passed
**90 targeted tests in 30.59s**, including registration storage, Sub2API import,
record-store and snapshot safety. Added 16 new regression cases. A separate
in-memory reload of the first-round functions against the new isolated DB
tests produced 11 failures out of the initial 12, reproducing lost metadata,
derived-state reset and generated-field leakage without touching checkout
files or any production data. The corrected snapshot adapter test also passes.

Ruff is absent from the primary runtime venv; no packages were installed into
that runtime. E is asked to provide its fresh locked validation environment
for the final merged checks. Phase 2 agents remain active; full acceptance of
all task migrations and real performance measurements is still pending.

## Verification

Baseline full suite completed: **954 passed, 34 subtests passed, 3 failed in
148.96 seconds**. No implementation agent changes were included. Failures:

- `tests/test_email_butler_client.py::EmailButlerClientTests::test_scan_retries_one_transient_connection_error`: mocked network call lacks explicit fake API base when private dotenv is disabled.
- `tests/test_sub2api_sync.py::Sub2ApiSyncMappingTests::test_export_configured_accounts_reads_complete_account_list`: mocked network call lacks explicit fake API base.
- `tests/test_route_contract.py::FlaskRouteContractTests::test_public_route_map_matches_refactor_baseline`: expected 109 routes, actual baseline has 110; verify the explicit route delta before updating the contract.

These three baseline test fixes are delegated to E, including ownership of the
three named test files. Do not restore private dotenv or change business
defaults to satisfy them. See combined results above. Test launcher (private local
coordination tool, no embedded credentials):
`/tmp/turb-optimization-20260914.mJ7Y6R/run.py <worktree> -m pytest -q ...`.
Run it with the primary workspace `.venv/bin/python`. It suppresses private
dotenv loading and selects only the isolated database.
