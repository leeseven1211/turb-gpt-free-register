# Local Test Suite Streamlining

## Goal

Make the repository's normal local regression command useful enough to run
often and fast enough to finish within 60 seconds on the current Mac. Preserve
rare but valuable database, recovery, migration, concurrency, and performance
checks as an explicitly selected extended suite instead of pretending every
local change needs every historical scenario.

This is a test-infrastructure change only. It must not change application
runtime behavior, production database rules, account workflows, or deployment
behavior.

## Current Evidence

- Pytest currently collects 1,352 tests from 130 files in about 2.36 seconds.
  Collection is not the bottleneck.
- The guarded isolated run passes 1,352 tests and 872 subtests in 233.73
  seconds on the current Mac.
- Forty-one files contain `PostgresTestCase`; those files account for 526
  collected tests. The base class creates a schema per class and truncates all
  tables with identity reset before every test, so repeated database setup is
  the dominant cumulative cost.
- The 89 files without `PostgresTestCase` contain 826 tests and currently take
  54.62 seconds. Roughly 39 seconds come from four tests that execute real
  browser-state waits, humanized delays, or a full source-tree configuration
  scan.
- The suite defines no `fast`, `extended`, `postgres`, or similar markers.
  Every guarded run therefore executes every category together.
- Manual live tools under `tools/`, including Codex OAuth and ChatGPT request
  probes, are outside `testpaths = ["tests"]` and are not part of pytest.

## Local-Only Operating Model

The project is operated locally. This design does not add CI, a release
pipeline, scheduled jobs, test dashboards, or deployment gates. It introduces
only two practical pytest profiles plus an escape hatch:

- `default`: the normal complete local check. This is what “full test” means
  in day-to-day project work and must finish within 60 seconds.
- `extended`: low-frequency tests selected when the changed code touches their
  risk area.
- `all`: an occasional diagnostic command that runs both profiles. It has no
  one-minute requirement and is not a normal merge prerequisite.

The profiles describe execution frequency, not importance. An extended test
may protect an important invariant whose setup cost is disproportionate for
unrelated local changes.

## Default Suite

The default suite contains deterministic tests that give broad feedback about
normal local behavior:

- pure business rules and state transitions;
- configuration parsing, defaults, and environment isolation;
- email/SMS provider parsing with network calls mocked at the transport edge;
- WebUI route, authorization, projection, and JavaScript behavior contracts;
- authentication and browser state transitions driven by a fake clock;
- storage guards and a representative PostgreSQL smoke path for schema
  creation, row CRUD/claiming, one registration/job lifecycle, one durable
  operation lifecycle, and one authenticated WebUI read/write path;
- secret redaction and production-database refusal behavior.

Default tests must not contact an external service, consume a real mailbox or
SMS number, start a browser, depend on random humanized delays, or wait on a
production timeout. Short synchronization sleeps used to exercise real thread
coordination are allowed only when a fake clock or condition-based primitive
cannot prove the behavior, and their combined contribution must remain within
the suite budget.

## Extended Suite

The extended suite retains scenarios that are useful when their owning module
changes but waste time on unrelated work:

- exhaustive durable-task lease, fencing, retry, `request_unknown`, and crash
  recovery permutations;
- legacy compatibility and one-time migration paths;
- historical schema/bootstrap/snapshot repair cases;
- high-contention concurrency and table-size/query-efficiency checks;
- task-center retention and archive edge matrices beyond the default smoke
  path;
- uncommon browser hydration, fallback, and timeout recovery branches that
  need multiple clock advances;
- release-manifest creation, dependency-lock validation, and immutable-release
  switching;
- opt-in performance benchmarks.

Extended tests remain isolated and automated. They must not mutate production
data or call real providers. Live account/browser tools remain manual tools and
do not become an extended pytest category.

## Test Audit and Reduction Rules

Every existing test is audited by the production break it is intended to
catch. Passing today is not enough reason to keep it, and a large file or old
name is not enough reason to delete it.

Keep or rewrite a test when it catches a distinct wrong branch, missing side
effect, boundary violation, malformed payload, or durability failure. Move it
to `extended` when the behavior remains valuable but is rare and expensive.
Delete or consolidate it when one of these conditions is true:

1. It only checks source text, an exact private symbol, a route count, or a
   transitional implementation shape rather than observable behavior.
2. Another test exercises the same fault boundary and asserts the same
   externally visible result with equal or stronger fidelity.
3. It tests a superseded migration phase or compatibility seam that production
   code no longer contains.
4. It asserts calls on mocks without proving a real component result.
5. A broad end-to-end setup repeats a contract already covered below it; keep
   the lower-level test and one representative cross-layer path.

Before deleting a test, the implementation record must name the production
break it used to catch and identify the retained test that catches that break,
or state why the production behavior no longer exists. Transitional names such
as `phase2` are renamed or merged only after this mapping; they are not bulk
deleted.

## Removing Artificial Time

The first optimization step removes test-only wall-clock waits without
shortening production timeouts:

- browser state-machine tests patch both wall and monotonic clocks and advance
  them deterministically;
- humanized delays are patched at the imported call site;
- transport retries mock only the external transport or sleeper while keeping
  response parsing and state transitions real;
- source-tree scans are performed once per test process or tested against a
  small controlled fixture when the full tree is not the behavior under test.

The current approximately 25-second passwordless-login test and password-reset
tests stay in the default suite after their clocks/delays are controlled. They
protect common behavior; moving them to `extended` would hide a test defect
rather than fix it.

## Selection Interface

`tools/test_isolated.py` remains the only canonical full-suite entrypoint. It
continues to sanitize application environment variables, disable dotenv,
reject `turb_console` and non-local database hosts, probe the selected local
test database, and use a `test_` schema.

The runner gains a profile option:

```bash
# Normal local complete check; profile omission is equivalent to default.
tools/test_isolated.py --profile default -- -q

# Low-frequency tests only.
tools/test_isolated.py --profile extended -- -q

# Both groups for occasional diagnosis.
tools/test_isolated.py --profile all -- -q
```

Pytest registers an `extended` marker. Tests are default unless explicitly
marked extended. `default` applies `not extended`, `extended` applies
`extended`, and `all` applies no marker filter. Explicitly running an extended
node uses `--profile all -- tests/path.py::test_name` so the profile never
silently overrides an explicit path.

The runner prints the selected profile and elapsed wall time. It does not add a
new parallel-test dependency in the first implementation. Parallelism is a
fallback only if classification, consolidation, and fake-time fixes cannot
meet the budget; this avoids introducing multi-process schema and global-state
isolation work for a local-only project.

## Classification Migration

Classification proceeds in this order:

1. Fix artificial waits and measure the non-PostgreSQL suite again.
2. Audit source-text, mock-only, exact-count, and transitional tests; rewrite,
   consolidate, or delete them under the reduction rules.
3. Mark exhaustive migration, recovery, concurrency, performance, and release
   modules or individual cases as extended.
4. Keep a small representative database smoke set in default and measure it
   with the optimized non-database suite.
5. Adjust only the classification or redundant coverage until the default
   suite has reasonable headroom; do not weaken production database guards.

New tests enter the default suite unless the author can state the rare risk and
cost that justify `extended`. This prevents the default suite from becoming an
unreviewed dumping ground while keeping unusual cases available.

## Focused Testing After Changes

The profile does not replace change-focused testing. For non-architectural
work, run the directly affected files and necessary adjacent regression files.
Run the default suite when a broader local merge check is useful. Run relevant
extended files only when changing storage architecture, durable task recovery,
migrations, concurrency behavior, browser timeout recovery, performance code,
or the release helper itself.

Reports must name the exact profile/files run. A focused or default pass must
not be described as an `all` pass.

## Performance Budget

The default budget is measured from invocation of `tools/test_isolated.py` to
its exit, with the shared local PostgreSQL service already running. It includes
environment sanitization, the database probe, collection, setup, execution,
and teardown. Dependency installation and starting PostgreSQL are outside the
budget.

Acceptance requires three consecutive isolated default runs on the current Mac
to finish in at most 60.00 seconds each. The implementation should target 45
seconds or less so normal machine variance does not immediately break the
requirement. No test-result cache or changed-file selector may be used to meet
the budget; each run selects the entire default profile.

The extended and all profiles have no fixed duration target, but both must
remain runnable through the same isolation guard.

## Safety and Failure Handling

- No test may connect to `turb_console` or a non-local PostgreSQL host.
- Profile parsing failures and unknown profile names fail before pytest starts.
- An empty profile is an error, not a successful zero-test run.
- Removed tests are not replaced with production-only test hooks.
- Private `.env`, credentials, account rows, logs, browser data, and runtime
  files remain outside commits and test output.
- Test cleanup continues to operate only on generated `test_` schemas.

## Acceptance Criteria

- The canonical default isolated command passes three consecutive times in at
  most 60.00 seconds per run on the current Mac.
- The default profile contains deterministic unit/UI/config coverage plus the
  documented representative PostgreSQL smoke capabilities.
- The extended profile independently collects and passes all retained
  low-frequency tests.
- The all profile collects exactly the union of default and extended with no
  unclassified or double-counted items.
- Artificial browser and humanized waits are removed from tests without
  changing production timeout behavior.
- Every deleted or consolidated test has a recorded retained-coverage or
  removed-production-behavior justification.
- Manual live tools remain opt-in and outside pytest.
- Focused, default, extended, and all results are reported by their exact
  scope; none is mislabeled as another.
