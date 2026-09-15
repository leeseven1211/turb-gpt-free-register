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
| A Storage | Coordinator; Aquinas reassigned to maintenance | Row/metadata corrections integrated; targeted and full suites passed | No stale snapshot deletion/overwrite; atomic create/retry; concurrency tests |
| B Tasks | Goodall, Luna max; Aquinas/Hooke service adapters | Phase 2 implementing actual maintenance migrations | Durable dispatch/recovery; automatic completion dependencies; bounded concurrency |
| C Configuration | Tesla, Luna max, closed after completion | Phase 2 integrated and targeted checks accepted; legacy constant atomicity boundary remains explicit | Canonical field schema, validation, explicit effective values/version |
| D Authentication | Hooke, Luna max | First round integrated; combined regressions passed | Shared implementation independent of Roxy orchestration; contract tests |
| E Verification/release | Ohm, Luna max | History-load benchmark integrated; task-center latency gate failed and optimization continues | Reproducible dependency lock, isolated mandatory DB tests, readiness/release checks |

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

Latest combined suite at integration commit `957c5f8`: **1029 passed,
617 subtests passed, 2 failed in 145.42s**. Only the two known configuration
fixture/route-contract failures remain, assigned to E. No running test session
is left from this checkpoint. E is asked to return those fixes in an early
commit independently of the remaining real-performance benchmark.

B's draft common handler contract is now visible in its phase-2 worktree:
`register_operation_handler`, `submit_durable_operation`, and
`OperationHandlerContext`. A/D have received those provisional names but must
wait for B's actual helper commit before pulling code into their worktrees.
Coordinator requested tests for accepted-new versus busy-reused return values,
lease renewal and execution-owner fencing. Do not accept or copy the uncommitted
draft as a completed interface. All five phase-2 agents continue with the scope
above; the heartbeat remains active.

### Phase 2 integration checkpoint 2026-09-14 12:44 UTC

E's early contract/isolation commit `a9c3fb7` was reviewed and integrated as
`a03ac46`. Full suite at that point: **1031 passed, 617 subtests passed in
139.53s**, with no failures.

C completed `ed84ee4`, integrated as `68427f4`: all 195 schema field/module
bindings verified, legal `none` enum preserved, CloudMail writers routed through
the canonical configuration editor. C's own relevant regression was 124 passed
with 783 subtests. Main reviewed and tested the combined changes. Tesla is now
closed after completed delivery. Legacy direct module-constant reads still lack
global atomicity; each new task must consume its captured snapshot. CloudMail
domain discovery retains two sequential, individually validated writes.

B's early helper commit `73b6510` was integrated as `9808845`. Coordinator found
that `last_result` was a method but read as a property, allowing an execution to
return failed after its database success commit. Correction `5db5ada` adds the
property, safe normalization defaults and direct return-value/DB-terminal
regressions. Combined target results: **65 passed, 782 subtests in 24.07s**.
A/D/E have been instructed to cherry-pick B's helper and `5db5ada` into their
existing phase-2 worktrees, preserving their service-only edits. B must take the
small correction into its own continuing branch as well.

B's scope now explicitly includes `webui/routes/operations.py`: native retry
and cancellation must dispatch by task type, never route maintenance tasks to
Codex OAuth. Startup legacy recoverers must not reset business status belonging
to active durable operations. B/D must agree a durable remote-write intent and
receipt contract: an unconfirmed token rotation/password submission found after
restart must remain request_unknown/reconcile, not become a blind retry.

Full suite after C + B helper + coordinator correction completed: **1045 passed,
816 subtests passed in 148.08s**. Session `57838` is finished, with no background
test sessions remaining. A/D have both taken the helper and coordinator fix
into their worktrees and are editing all assigned maintenance/token services.
Four phase-2 agents remain active (A/B/D/E), and the heartbeat monitor is still
ACTIVE. Full test success at this checkpoint is not acceptance of the still
unfinished service migrations, remote-write recovery contract or benchmark.
No production changes or push.

### Monitor checkpoint 2026-09-14 12:56 UTC

A/B/D remain active on service migration and shared remote-write checkpoints.
A's four maintenance services and D's token service have implementation/test
edits but no final migration commits. B is adding runtime wiring and durable
remote intent/receipt recovery. No production/primary-worktree changes.

E returned benchmark commit `3d95cc2`, reviewed and integrated as `ec32fbf`.
Coordinator ran the real benchmark in the isolated database: 1000 accounts,
20 authenticated HTTP samples, 3 SQL statements/request, list p95 **19.795ms**.
With 32 synthetic no-network tasks, the gate produced a real backlog of 29;
max active was **3/3**, all 32 tasks committed success, measured queue-wait p95
**1022.102ms** and throughput **29.38 runs/s** under this artificial congestion.
Scanner restart recovered the same 6 queued rows, all success. Thresholds pass;
test session `80408` is finished. These are observations, not production SLA
or before/after optimization claims.

E still needs final locked-environment verification and history-load coverage:
the current HTTP list timing precedes operation seed and thus does not exercise
thousands of historical task rows. Coordinator requested >=2000 terminal
synthetic jobs/operations before list tests plus actual task-center listing,
and unconditional environment restoration if benchmark cleanup raises. Current
benchmark is accepted only for its explicitly measured small-queue scope.

Cross-agent review found D's draft records a confirmed remote receipt before
persisting the rotated credential. Coordinator sent B/D a mandatory correction:
an HTTP response alone must not clear pending-write recovery; confirmation must
follow required local write/readback. Add a crash-between-receipt-and-persistence
test, or recovery could expose an unsafe blind retry. D must also converge its
temporary fallback claim/executor path onto the now available shared handler.
No additional user notification was issued for this normal interim checkpoint;
the heartbeat remains ACTIVE and full five-stream acceptance is not complete.

### Monitor checkpoint 2026-09-14 13:10 UTC

All four remaining agents are still implementing/testing; no new completed
commit was available to integrate. A has native service adapters and a dedicated
maintenance regression file; D has added HTTP-response-before-readback crash
coverage and moved confirmed receipt after credential persistence/readback in
its draft. These are not yet accepted results. B is implementing remote-intent
storage and runtime integration; E is expanding the benchmark to historical
task load. Integration remains clean at `1ea2cc7` before this log update.

Coordinator found an A draft performance regression: it removed the prior HME
bulk shared-mailbox scan and replaced it with one IMAP scan per alias. A must
preserve batched mailbox search and per-account result fanout under durable
dispatch, without restoring a second independent consumer. Added acceptance
requirements cover a single bulk scan for multiple aliases, per-account result
writeback, cancellation and partial failure. Queue unification is not permission
to remove an existing batching optimization.

B is asked to return a separately verified remote-intent/receipt helper commit
before the larger runtime/routes migration, so A/D can replace draft/fallback
hooks with the actual shared contract and test crash recovery end-to-end.
No user notification was issued for unchanged normal execution. The monitor
remains ACTIVE; primary workspace and production service are unchanged.

### Monitor checkpoint 2026-09-14 13:36 UTC

B's remote-intent helper `8004538` was reviewed and integrated as `ca786db`.
Coordinator identified a terminal-state safety gap: exceptions/cancellation
after a remote write could become retryable failures and thereby bypass stale
recovery. Coordinator correction `4d91dcd` enforces reconciliation in
`finish_run` and rejects blind retry in storage, aligns handler return values
with the actual committed status, clears rejected checkpoints after retry-data
merge, and latches lease-heartbeat exceptions. Outstanding write checkpoints
cannot be replaced, receipt correlation IDs must match, and read-only receipts
do not need an account lease. Targeted result: **78 passed, 11 subtests in
24.34s**. Loading the original `8004538` functions in a separate isolated test
process reproduced **10 failures** against the initial new safety regressions.
A/B/D have received the correction commit for their continuing branches.

B's account reconciliation query `6742fbf` was integrated as `beed557`; the
test-only cherry-pick conflict was resolved by retaining both agents' added
tests. Two review corrections remain assigned to B: apply SQL account dedupe
before a result cap (avoid silently omitted fenced accounts), and use exact
non-sensitive config policy fields rather than broad password-name exceptions.
B also must dispatch registered maintenance route actions by type rather than
reject all non-Codex tasks in `native_operations`; A/D actually use that source.
The service migrations have not returned final commits yet.

E returned `94ea8aa`, integrated as `7ef5b71`, adding 2000 terminal task/run
history rows before real account and task-center HTTP measurements. E measured
account p95 **18.535ms / 3 SQL** but task-center p95 **1453.913ms / 8 SQL**,
above the unchanged **250ms** gate: `passes_thresholds=false`. This is a real
acceptance failure, not a passed benchmark. Ohm continues on the read-query
bottleneck, with bounded ownership of task/batch list SQL and independent tests;
B retains runtime, routes, recovery, reconciliation and write paths. Do not
weaken thresholds, remove history load, or substitute a fake request path.

E supplied its fresh locked environment `/tmp/turb-opt-release-lock-20260914`.
Coordinator verified Python 3.12.13, `pip check`, and whole-repo Ruff. Full
merged pytest in that locked environment passed: **1056 passed, 825 subtests
passed in 164.31s** at `7ef5b71`. Session `52568` is finished, with no test
sessions left running. The safe launcher selected only `turb_opt_20260914`.
This passing suite does not waive the failed performance gate or accept the
unfinished service migrations.

Review of D's uncommitted migration found `reconcile=True` could only bypass a
marker and enqueue the same refresh POST without an actual reconciliation
handler. D must close this public-entrypoint bypass, query the durable fence on
manual submission as well as scheduled scans, and prove zero remote requests
for unresolved credentials. This draft is not an accepted migration.

Heartbeat remains ACTIVE; A/B/D/E remain assigned to remaining work. Primary
HEAD is still `f33e523` with the same 13 external dirty files. No production DB
tests, primary edits, service restart, deployment or push.

### Monitor checkpoint 2026-09-14 13:52 UTC

B returned shared-action/fence correction `bab0c60`, integrated as `55d5121`.
Reconciliation query now deduplicates accounts in SQL before LIMIT and returns
the whole explicit candidate set; password policy projection uses exact names.
Every registered context handler receives safe shared retry/cancel actions.
The cherry-pick's test-order conflict was resolved retaining each distinct test
once. B's actual route/runtime migration remains uncommitted and unaccepted.

D returned token migration `766a5fe`, integrated as `060bec4`. It uses the
shared gateway, persists remote intent/receipt, gates manual as well as
scheduled submission on durable unknown state, and no longer lets
`reconcile=True` authorize another refresh grant. Combined locked-environment
target tests passed: **73 passed, 11 subtests in 17.68s**; session `34063` is
finished. No running test sessions remain.

D is not closed or fully accepted yet: review found that the post-HTTP
checkpoint still checks cancellation before saving the rotated credential.
Hooke is assigned a narrow follow-up separating lease/fence checks from user
cancellation during response settlement, with a real gateway test cancelling
inside the synthetic POST and proving the returned token pair is persisted.
D must also capture C's canonical config snapshot/revision instead of constructing
a revisionless timeout dictionary. A has the same explicit snapshot requirement
for its maintenance submissions and handler execution values.

E's read-path draft identifies repeated correlated run-count/current-run work
as the task-center bottleneck and reports unchanged-load p95 around 43ms
(about 52ms in its locked environment). No final read-query commit has returned
yet, so these remain agent-reported draft results, not integrated performance
acceptance. Ohm is finishing filter/facet semantics tests before delivery.

B's startup draft currently skips legacy recovery for an entire category if any
durable run exists. Coordinator requested row-scoped exclusions instead: an
active native account must be preserved while unrelated orphan legacy work is
still recovered. B's write scope is expanded only to the needed legacy recovery
functions/parameters and dedicated tests, not unrelated metadata writers.

A/B/D/E continue in their assigned worktrees. The heartbeat remains ACTIVE.
No normal-progress user notification, production changes, restart, deployment
or push occurred in this checkpoint.

### Monitor checkpoint 2026-09-15 00:08 UTC

The prior three Luna max worktree sessions were no longer addressable by the
agent tool, so their uncommitted work was not treated as delivered. The
integration branch contains the reviewed commits through `13ba506` plus the
task-center read optimization; no newer service/runtime migration has been
integrated. The last verified full locked-environment result remains **1056
passed, 825 subtests**, while the real 2000-history task-center benchmark passed
after the read optimization at p95 about **45 ms** with 8 SQL queries.

Coordinator dispatched three replacement Luna max agents into the existing
isolated worktrees, with disjoint scopes and explicit commit/test requirements:

- Zeno `01a0a264-8016-7181-a7cc-f16e5c516ee3`: maintenance service handlers,
  HME bulk preservation and canonical snapshots;
- Dewey `01a0a264-80ca-7ad0-a37e-691876dc7afd`: shared runtime/routes,
  row-scoped legacy recovery and parent/child continuation;
- Aquinas `01a0a264-81b9-7310-8402-6807a821395c`: token refresh final audit,
  cancellation settlement and canonical snapshot verification.

They must work only in their assigned worktree and use synthetic isolated
PostgreSQL through the safe launcher. No agent completion will be accepted
without coordinator diff review, targeted tests, and a fresh locked full-suite
run. Primary workspace, private data, production database, deployment and push
remain out of scope. The heartbeat remains ACTIVE.

The coordinator ran a fresh full suite on the current integration branch after
the token settlement and task-center read-query integrations: **1087 passed,
830 subtests passed in 536.68s** using the locked Python environment and safe
isolated database launcher. This result predates the replacement agents' new
commits and therefore does not accept their pending service/runtime work.

### Monitor checkpoint 2026-09-15 00:37 UTC

Aquinas returned Luna max token audit commit `35e15a1`, which adds a fail-closed
guard so `reconcile=True` cannot create a refresh run or send a refresh grant
even when the credential marker is clean. The commit was reviewed and
integrated as `7a8ce99`. Isolated token targets passed: **38 passed in 14.99s**;
the earlier gateway/executor audit also passed **24 passed, 11 subtests**.

Zeno and Dewey remain in progress with uncommitted maintenance and runtime
changes; their work is not accepted. A first incorrect local test invocation
referenced a nonexistent test file and ran no tests; it was corrected before
the passing result above. Integration remains isolated, primary HEAD remains
`f33e523` with 13 user-owned dirty files, and no production DB test, restart,
deployment or push occurred.

### Monitor checkpoint 2026-09-15 01:08 UTC

Zeno returned maintenance commit `036e623`; after diff review it was
integrated as `6e007da`. It migrates live check, plan check, extract-link and
deactivation-mail handlers to the durable gateway, retaining the single HME
bulk scan plus per-account fanout. Dewey returned runtime/recovery commit
`737ac25`; it was integrated as `c12f863` after resolving only the combined
`Callable`/`Iterable` import conflict in `core/storage/db_legacy.py`.

The combined focused integration set passed: **94 passed, 11 subtests in
52.98s**, with `git diff --check` clean. This is targeted acceptance only;
the locked full suite is still required before accepting the two streams.
Both source worktrees are clean and local-only. Aquinas's token acceptance
remains integrated. Primary workspace still has 13 user-owned dirty files;
there were no production DB tests, restarts, deployments or pushes.

### Monitor checkpoint 2026-09-15 01:13 UTC

The first locked full-suite run after integrating Zeno and Dewey completed
with **1121 passed, 830 subtests, 4 failed in 280.50s**. The failures are a
real compatibility regression from the maintenance migration: four existing
tests patch the historical `_EXECUTOR` aliases on live-check/plan-check
services, but those aliases were removed while the durable gateway became the
submission path. No production behavior was reverted. Zeno was assigned a
narrow Luna max follow-up to restore the test/legacy patch seam without
reintroducing direct process-pool submission; its result remains pending.

The two implementation commits remain only on the isolated integration branch
(`6e007da`, `c12f863` plus this follow-up log). Primary workspace and private
data remain unchanged; no production DB test, restart, deployment or push
occurred.

### Monitor checkpoint 2026-09-15 01:53 UTC

Zeno returned follow-up commit `4532f32`; after review it was integrated as
`1c97df2`. It restores the live-check common-executor compatibility alias and
the plan-check registration seam as non-consuming compatibility surfaces;
native submissions still go through the durable gateway. The four previously
failed regression tests plus maintenance coverage now pass: **81 passed, 8
subtests in 37.74s**.

The next required gate is a fresh locked full-suite run on this exact
integration state. Primary workspace remains unchanged with 13 user-owned
dirty files; no production DB test, restart, deployment or push occurred.

### Monitor checkpoint 2026-09-15 01:59 UTC — all five acceptance gates complete

The fresh locked full-suite run on the repaired integration branch passed:
**1125 passed, 830 subtests in 220.68s**. Ruff, compileall, `pip check` and
the dependency-lock checker also passed (`runtime=51`, `development=61`).

The release performance gate passed on 1000 synthetic accounts and 2000
terminal history rows using 20 HTTP samples: account list p95 **19.422 ms**
(max 41.762, 3 SQL), task center p95 **60.303 ms** (max 60.578, 8 SQL), under
the 250 ms/3-SQL/10-SQL limits. Durable dispatcher measured configured max
concurrency **3/3**, observed a 29-run backlog with 32/32 successful
no-network runs, and restarted recovery completed **6/6**; no network calls
were made.

Coordinator acceptance is now complete for storage row safety, durable task
and runtime migration, canonical configuration snapshots, authentication/
token remote-boundary handling, and release/test/read-performance gates. The
integration branch remains local-only. Primary HEAD is still `f33e523` with
the same 13 user-owned dirty files; no production database test, restart,
deployment or push occurred. This monitoring automation can now be closed.

### Local deployment verification 2026-09-15 02:12 UTC

按用户要求在本优化 worktree 做本地启动验证。第一次启动在
`operation_task_store.repair_stale_compatibility_projections()` 处失败：
`test_opt_bootstrap.account_action_tasks` 不存在。根因是 `legacy_task_store`
在未设置 `ACCOUNT_TASK_DB_SCHEMA` 时固定使用 `public`，而隔离启动入口只设置
了 `TURB_DB_SCHEMA`。先新增回归测试确认该失败，再将默认选择改为
`ACCOUNT_TASK_DB_SCHEMA` -> `TURB_DB_SCHEMA` -> `public`，回归测试通过。

修复后的集成 worktree 已在独立本地端口 `127.0.0.1:8001` 启动，使用
`turb_opt_20260914` 的隔离 schema；进程监听正常，`/healthz` 返回 **200**，
`/readyz` 返回 **200** 且 database、executor、codex dispatcher、dependency
dispatcher、projection worker 均为 healthy，`/login` 返回 **200**。该进程
只用于本地隔离验证，未读取生产数据库、未重启既有服务、未部署远端、未推送。

### Local deployment and real batch verification 2026-09-15 03:10 UTC

按用户要求将优化 worktree 部署到本机 `127.0.0.1:8000`，复用主工作区的本地
`.env`、共享 PostgreSQL 和虚拟环境；只建立了指向这些运行时文件的符号链接，
没有复制或提交私有数据。发现主工作区的 launchd 任务
`turb_gpt_free_register_webui` 会在旧进程停止后自动拉回旧代码，已停止该本机
守护任务，再用持续前台会话运行优化 worktree。优化进程 cwd、HTTP 监听、
`/healthz`、`/readyz` 均已确认，ready 响应中的 database、三个 dispatcher/
projection worker 均为 ready。

启动时新增的 identity sequence 对齐修复发现本地行级表已有显式导入 ID 但
sequence 落后；当时 iCloud 池为 `MAX(id)=842`、sequence=`514`，导致同步别名
时报重复主键。新增 `test_init_repairs_identity_sequences_after_explicit_import_ids`
并补充启动期逐表修复；行级存储和 iCloud 相关测试通过：**32 passed**。重启
8000 后 9 张行级表均确认 `sequence >= MAX(id)`；随后补上空表不消耗首个 ID 的
回归修正，3 个受影响测试和完整隔离套件最终通过：**1127 passed，830 subtests**。

在 8000 通过 WebUI API 发起真实本地批次
`20260915-105251-e9b1bb43`：10 个任务、并发 10，任务 ID `1129-1138`，邮箱来源
为 iCloud 隐藏邮箱。首轮终态为 **6 success / 4 failed**；失败分别为 1024Proxy
无可用线路（2）、Roxy `browser/open` socket hang up（1）、OpenAI 验证码页流程
未出现创建密码页（1）。统一投影最终为 `succeeded`，无 queue error，10 个源任务
和 run 均写回数据库。

只对这 4 个失败任务做了跟进重试，未重跑已成功任务；跟进终态为 **9 success /
1 partial_success**。Roxy 与代理失败项均恢复成功；剩余任务进入 OAuth `AUTH_ERROR`，
远端身份为 `confirmed`、本地账号行已存在但 access token 未确认，保留为
`request_unknown`/后处理不确定状态，不能作为全绿验收。因真实批次仍有该残留，
五项优化暂不合并到主工作区，也未 push；主工作区 13 个用户改动保持原状。

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

### Local merge and deployment checkpoint 2026-09-15 12:25 Asia/Shanghai

The validated optimization branch was fast-forwarded into local `main` at
`f3cd9a4` after the combined isolated suite passed **1127 tests and 830
subtests**, with ruff, compileall, dependency-lock validation, pip check, and
diff checks passing. The primary workspace's 13 pre-existing uncommitted files
were preserved in a recoverable stash; they were not overwritten or pushed.

The local WebUI is now running from the primary checkout at
`http://127.0.0.1:8000`. Fresh checks returned `/healthz=200`, `/readyz=200`,
`/login=200`; PostgreSQL, executor, codex dispatcher, dependency dispatcher,
and projection worker were all ready. The projection queue is fully succeeded
with no pending rows.

The previous real 10-task, concurrency-10 batch remains mixed rather than green:
9 successful follow-up outcomes, 4 original failed parent jobs retained for
history, and 1 `partial_success` OAuth reconciliation outcome. Its task/run
writeback is present and was not rewritten. This is runtime evidence of the
new durable state handling, but not a claim that all external registration
dependencies succeeded.

Luna max review then identified a real remaining acceptance gap in startup
identity sequence repair: repeated startup can consume an ID on non-empty tables,
and legacy tables without an owned identity sequence need an explicit safe path.
The fix and isolated regressions are delegated before final five-gate closure;
no push or remote deployment is authorized by this checkpoint.

### Final local acceptance checkpoint 2026-09-15 12:52 Asia/Shanghai

The review correction was integrated at `7a28188`. Final isolated verification
passed **1132 tests and 830 subtests**, with ruff, compileall, dependency-lock
validation, pip check, bash syntax, and diff checks passing. The local service
was restarted from this commit on `127.0.0.1:8000`; `/healthz`, `/readyz`, and
`/login` all returned **200**, and the database plus all three runtime workers
reported ready.

Read-only live checks after restart found no identity sequence regression across
the nine row tables (`sequence >= MAX(id)`) and the projection queue remained
fully `succeeded`. The startup repair now avoids consuming a synchronized ID,
preserves empty-table first inserts, repairs explicit imports, and tolerates
legacy tables without an owned sequence. `webui.sh logs` also works in a fresh
checkout without a pre-existing `logs/` directory.

Five optimization gates are locally integrated and operationally verified:
row-safe storage, durable tasks/runtime, canonical configuration snapshots,
remote authentication/token uncertainty handling, and release/test/read
performance. The real 10-task external batch remains intentionally recorded as
mixed evidence (9 success, 4 failed parent jobs, 1 partial-success follow-up),
not as a fabricated all-green result. No production/remote deployment or push
was performed. The remaining documented operational risk is that
`STARTUP_CHECK_TIMEOUT` still defaults to 30 seconds and was not broadened in
this pass; the observed local startup completed within that window.

Monitoring is closed after this final local acceptance checkpoint.

### Primary stash equivalence audit 2026-09-15 14:14 Asia/Shanghai

The five optimization streams are already represented on local `main` by the
reviewed integration commits for storage, durable tasks/runtime, configuration,
shared authentication/token handling, and release verification. The original
agent branch tips are patch-equivalent to `main`; they do not contain an
additional implementation that needs to be merged again.

The primary-workspace snapshot `stash@{0}` (`ffb0e835`) was compared file by
file before any cleanup. Its proxy retry/rotation, iCloud relay/reactivation,
and regression tests are already present in `main`. Its Roxy and legacy storage
sections are older copies of code that the shared authentication and row-level
storage migrations replaced; applying them wholesale would regress the new
architecture. No unique source change from this stash remains to merge. The
stash is retained as a recoverable backup; the single active code version is
the committed `main` tree.
