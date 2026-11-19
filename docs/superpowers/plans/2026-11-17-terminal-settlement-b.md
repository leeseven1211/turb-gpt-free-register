# Terminal settlement B implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Implement and review each task against the approved spec; use checkbox steps to record execution.

**Goal:** Complete the approved execution-local terminal/defer settlement, exact resource compensation, durable PostgreSQL receipts and honest bounded shutdown without replaying business.
**Architecture:** Keep the existing operation gateway, admission transactions and ManagedRuntime. Capture responsibility at admission, freeze one transition, atomically persist the transition/receipt/cleanup, and release the exact permit only after callback and required cleanup are complete. PostgreSQL remains authoritative; pre-persistence process death uses conservative recovery.
**Tech Stack:** Existing Python, psycopg/psycopg_pool, PostgreSQL, unittest/pytest. No dependency or UI framework additions.
**Spec:** `docs/superpowers/specs/2026-11-17-terminal-settlement-discussion.md`, approved as option B by the user in this turn.

## Global Constraints

- Reuse this linked worktree on `codex/architecture-task-center`; base HEAD `2fe57ac56415c746bf7fa566ee7cf147bebfd0c2`. Preserve all earlier dirty/private files.
- Never execute `rm -r`; delete individual files only. No commit, staging, push, merge, production restart or deployment.
- No real remote business or credentials in output. Test external actions with loopback-only synthetic implementations and exact counters.
- Root exclusively schedules PostgreSQL, database restart, scale measurements and actual subprocess acceptance. Children run only explicitly offline tests with database/config loading blocked unless root grants an exclusive test slot.
- Evidence root: `/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117`.
- Do not overwrite the preserved F16 v6/v7 databases or failure evidence. New true-restart acceptance uses a new fixed-endpoint synthetic container.
- Existing business statuses, remote checkpoint classification, child waiting, partial results, same-Run defer and 55-second local total shutdown budget remain binding.
- Scope is B: no local journal, remote replay, arbitrary callback queue, general SQL tuning, five-hundred-thousand capacity remediation or production/systemd cutover.
- Write meaningful failing regression tests first. Preserve RED output, GREEN output and exact commands. A test import error alone is not the behavioral RED.
- One writer per listed file; interface changes go through root and are recorded in the ledger before other writers adapt.

## Shared interfaces and file ownership

Task 1 owns the following stable protocol in `core/operations/settlement_contracts.py`:

```python
@dataclass(frozen=True)
class SettlementDomain:
    database_url: str = field(repr=False)
    operation_schema: str
    permit_schema: str
    domain_id: str

@dataclass(frozen=True)
class SettlementIntent:
    transition_id: str
    kind: str                 # terminal | defer
    origin: Mapping           # immutable ticket + original execution identity
    payload: Mapping          # recursively frozen, storage-safe request
    obligations: tuple
    request_digest: str
    version: int = 1

def seal_intent(*, kind, origin, payload, obligations=(), transition_id=None): ...
def thaw(value): ...          # a fresh JSON-compatible value
def same_intent(left, right): ...
class OperationSettlementPending(RuntimeError): ...
class OperationSettlementConflict(RuntimeError): ...
class OperationSettlementFenced(PermissionError): ...
```

Task 1 owns the execution responsibility registry and coordinator in `core/operations/settlement.py`. Public module API:

```python
def register_execution(execution, ticket): ...
def responsibility(execution): ...          # None for a nonparticipant
def callback_started(execution): ...
def callback_exited(execution): ...
def register_lease(execution, lease, *, scope_kind="final"): ...
def settle(execution, intent, submit): ...  # submit(intent, deadline) -> receipt
def release_eligible(execution): ...
def request_release(execution, *, reason="worker_exit"): ...
def active_counts(): ...                    # disjoint integer pending facts
def runtime_status(): ...                   # sanitized, nonblocking
def start_runtime(*, admission=None): ...
def drain_runtime(deadline): ...
def stop_runtime(deadline): ...             # real join and bool
```

The in-memory `submit` adapter may perform only the typed local repository operation; it is not serialized and cannot be a business handler. The coordinator owns one tracked carrier, exact registry membership and synchronized callback/cleanup handoff. `settle` attempts synchronously, returns an authoritative receipt, or registers the original immutable intent and raises `OperationSettlementPending`. An attempt never rewrites the frozen intent.

Task 2 owns `core/storage/operations/settlements.py`, operation schema/runtime/facade, domain binding in common and the scoped connection helper:

```python
def submit_intent(intent, *, domain, deadline=None): ...
def read_receipt(intent, *, domain, deadline=None): ...
def pending_cleanup(*, domain, limit=32, deadline=None): ...
def run_cleanup_once(*, domain, deadline=None): ...
def cleanup_blocks_permit(permit_id, execution_id, *, domain, conn=None): ...
def initialize_schema(cur): ...             # same original operation schema
```

Task 2 adds optional `settlement_intent`, `settlement_domain`, `deadline` to the existing `finish_run` and `requeue_claimed_run` repository/facade methods. Existing callers remain compatible. First-write and pure-readback branches are separate; same transaction persists receipt and typed cleanup obligations. A domain context uses ContextVar, never temporarily mutates process environment.

Task 3 owns only `core/operations/concurrency.py` and `core/storage/operations/permits.py`: ticket creation in claim+permit transaction, registry registration before callback, release eligibility and recovery liveness.

Task 4 owns only `core/operations/task_gateway.py` and new gateway tests: lease state/scope, original domain, frozen finish/defer, callback/rollback/future boundaries. `context.lease(..., scope_kind="final"|"step")` is explicit; step remains the default for compatibility until Task 5 marks native final scopes. Expose pending/conflict/fenced classes from the gateway for domain adapters.

Task 5a owns account setup/completion/results, liveness/plans/mail scan/inspection/email-change and integration adapters plus their targeted tests. Task 5b owns Codex refresh/old guard and tests. Task 5c owns extract/independent-payment and tests. No domain writer edits gateway, coordinator, concurrency or storage.

Task 6 owns runtime assembly/managed/readiness/bindings and relevant runtime tests. Task 7 owns new ART fault harnesses and integration acceptance fixtures; root performs actual DB runs.

## Task 1: Immutable protocol and one managed settlement carrier

**Files:** create `core/operations/settlement_contracts.py`, `core/operations/settlement.py`, `tests/operations/test_settlement_contracts.py`, `tests/operations/test_settlement_coordinator.py`.

**Consumes:** existing ExecutionContext identity and lease handles; storage submit adapter supplied by gateway. **Produces:** shared API above.

- [ ] RED: exercise real immutable payload behavior, conflicting second intent, duplicate confirmation, callback still active versus cleanup handoff, transient submit failure and same-intent retry.

```python
summary = {"steps": [{"state": "done"}]}
intent = seal_intent(kind="terminal", origin=origin, payload={"status": "success", "summary": summary})
summary["steps"][0]["state"] = "changed"
assert thaw(intent.payload)["summary"]["steps"][0]["state"] == "done"
```

- [ ] Implement canonical JSON/versioned digest, recursively frozen values and safe technical exceptions; never include connection material in repr/status.
- [ ] Implement per-execution responsibility, synchronized register/start/exit/lease/release transitions and one bounded tracked retry carrier. A callback exit does not free responsibility.
- [ ] GREEN: offline unit tests with real threads/barriers and injected local storage failure; preserve original submit count/intent and prove no business callback execution.
- [ ] Send API/hash package for independent spec+quality review; address findings before integrated acceptance.

## Task 2: Transactional receipt, typed cleanup and original-domain deadline

**Files:** create `core/storage/operations/settlements.py`; modify `schema.py`, `runtime.py`, `store.py`, `common.py` and scoped helper in `core/storage/postgres.py`; create `tests/operations/test_settlement_store.py`, `tests/storage/test_settlement_deadline.py`.

**Consumes:** Task 1 intent/domain. **Produces:** exact receipt and durable cleanup APIs above, additive runtime/facade parameters.

- [ ] RED: add original-native transaction regressions for commit-before-ACK loss, exact readback after lease deletion, same execution terminal/defer conflict, multiple defer generations, old Run/current Task protection and no repeated event/fact/parent side effect.

```python
first = submit_intent(intent, domain=domain)
again = read_receipt(intent, domain=domain)
assert again["transition_event_uuid"] == first["transition_event_uuid"]
assert terminal_event_count(original_run) == 1
assert current_task_run_id() == newer_run_id
```

- [ ] Add append-only receipt and cleanup schema/indexes. One execution gets one terminal/defer handoff; terminal is unique per Run; historical rows without receipts remain explicit unproved legacy results.
- [ ] Refactor existing terminal/requeue internals only enough to share the same connection/fact lock, exact original token deletion, receipt and cleanup insert. Pure readback never enters emitting fact-update/log/notification.
- [ ] Add ContextVar-bound original connection/schema and scoped checkout/statement/lock deadlines. Keep pool keys stable, report uninterruptible I/O truthfully, never broaden automatic transaction retry.
- [ ] Persist minimum actual-result snapshot and separate request/actual digests. Preserve existing remote classification and current Run fence.
- [ ] Implement typed cleanup claim/CAS/readback, no arbitrary stored callable. Durable followup whitelist must not execute a remote action inline.
- [ ] Root runs targeted PG regressions in exclusive disposable schema; writer may run only offline serialization/deadline tests before its slot.
- [ ] Independent storage/lock-order review and fix before F16.

## Task 3: Admission ticket and permit responsibility

**Files:** `core/operations/concurrency.py`, `core/storage/operations/permits.py`; create `tests/operations/test_settlement_permits.py`.

**Consumes:** Task 1 registry and Task 2 cleanup query; existing claim callback. **Produces:** immutable ticket in the claim+permit transaction and captured original domain on ExecutionContext.

- [ ] RED: demonstrate `release_execution` and recovery do not release a participating permit while callback or settlement responsibility remains; legacy nonparticipants retain existing behavior.

```python
register_execution(execution, ticket)
assert release_execution(execution) is False
assert not execution.released
assert exact_permit_not_released()
```

- [ ] Build ticket only for participating operation executions, after claim and before INSERT, with original Run UUID/domain/process/permit/execution; do not tag registration/Butler permits accidentally.
- [ ] Register responsibility before returned admission can enter callback; handle post-commit registration failure conservatively with exact ownership evidence.
- [ ] Gate all release paths and `_LOCAL_EXITS`; participating cross-process liveness ignores callback thread death and uses host/PID/start. Check durable cleanup before dead-process release.
- [ ] Keep separate admission-lock permit release outside business transactions; legacy release retries remain partitioned and observable.
- [ ] GREEN offline liveness/registry race tests; root executes PG capacity/claim/recovery compatibility.
- [ ] Independent recovery review and integration with Tasks 4/6.

## Task 4: Gateway, explicit lease scope and all handoff paths

**Files:** `core/operations/task_gateway.py`; create `tests/operations/test_settlement_gateway.py`, `tests/operations/test_settlement_leases.py`.

**Consumes:** Tasks 1–3 APIs; optional storage intent/domain/deadline. **Produces:** native context terminal/defer protocol, scope_kind API and shared control exceptions.

- [ ] RED using real OperationLease/Context methods: failed DELETE preserves handle/retry, failed finish preserves immutable result, duplicate finish exact confirmation, outer finally/future cannot release pending permit.
- [ ] Implement scope state/registry and serialized heartbeat/release. Final scope transfers ownership; step scope confirms release before another acquire; never silently omit a required original fence.
- [ ] Seal terminal/defer once before storage. Technical pending/fenced/conflict takes priority over all later exception branches; confirmed context result reflects stored actual result.
- [ ] Represent executor submit failure, pre-execution drain and cancelled future as defer/unstarted_rollback with callback-start barrier and exact receipt; no premature release on rollback failure.
- [ ] Add typed original-version postcommit obligation registration for Tasks 5a–c; no implicit anonymous callback queue.
- [ ] GREEN focused offline tests and root PG tests; independently review all exit/catch/rollback/future paths.

## Task 5a: Account/integration adapters and parent-child obligation

**Files:** `core/accounts/{operation_results,setup_execution,completion_execution,completion_dependencies}.py`, `core/accounts/{liveness,plans,deactivation,inspection,email_change}/service.py` (mail scan actual file `deactivation/mail_scan.py`), `core/integrations/{c2a/manual_sync,sub2api/manual_upload,sub2api/jobs}.py`; scoped new tests under `tests/accounts/`.

**Consumes:** gateway scope/control/typed obligation API. **Produces:** native final scopes, exception transparency, once-only existing child registration.

- [ ] RED tests for frozen success/partial result surviving finish failure; no business writeback/callback repeats; completion fast child and ordinary non-bulk handoff.
- [ ] Mark audited final scopes; propagate settlement control before business catches, preserve inline finish_operation=False behavior and accountless cases.
- [ ] Freeze completion existing child source/id/payload before partial finish; persist dependency obligation for both normal and bulk. Do not enqueue a second child.
- [ ] Keep email session/actor quiescence as required cleanup; no post-change different-family child while original actor is unverified.
- [ ] GREEN targeted account/integration regressions, then independent adapter review.

## Task 5b: Codex refresh and old guard seam

**Files:** `core/codex/token_refresh_service.py`, `core/codex/operation_service.py` and scoped new Codex tests.

**Consumes:** gateway final scope, native context/ticket and typed marker obligation. **Produces:** both Codex paths obey same intent/resource/permit gate.

- [ ] RED: finish-only failure does not `_mark_unknown`/rewrite credential result, marker cleanup cannot clear a newer Run/version, old guard release failure remains pending.
- [ ] Mark final scope and route legacy direct guard/finish/requeue through exact responsibility without rewriting OAuth business.
- [ ] Declare marker cleanup before freeze; add original credential Run/version CAS and keep credential secrets out of receipts.
- [ ] Only mark route resource released after physical release confirmation; preserve unknown as cleanup fact.
- [ ] GREEN targeted refresh/old dispatch compatibility and independent review.

## Task 5c: Extract, continuation and independent payment

**Files:** `core/extract_link/service.py`, `core/extract_link/independent_payment.py` and scoped new extract tests.

**Consumes:** gateway explicit scope/control/obligation API. **Produces:** provider/legacy final scopes, proxy step scope and existing followup whitelist.

- [ ] RED: step release failure cannot enter payment or ordinary requeue; proxy finish never seals main Run; defer ACK loss cannot create a second order/terminal.
- [ ] Keep extraction step release → payment final scope; propagate pending through all audited catch branches.
- [ ] Necessary legacy account writebacks precede final freeze. Declare existing post-payment plan-check obligation using `extract-workbench:{task_id}:payment-success`, original trigger and exact Run/version provider update; actual local enqueue only from healthy owner/normal dispatcher.
- [ ] Do not mark proxy released after physical release error; retain cleanup ownership.
- [ ] GREEN deterministic step/followup/defer tests and root PG integration; independent review.

## Task 6: Managed lifecycle, readiness and two drain barriers

**Files:** `core/runtime/{assembly,managed,readiness,bindings}.py`, any required additive component binding; create `tests/runtime/test_settlement_lifecycle.py`.

**Consumes:** Task 1 coordinator APIs and disjoint numeric counts. **Produces:** start before claims, pending progress before executor close, final drain/join before pools/owner.

- [ ] RED: pending progresses while idle waits; stop hooks may enqueue cleanup; unknown/failed pending prevents clean stop; repeated stop shares original deadline.
- [ ] Integrate coordinator as lifecycle-owned service, not a business executor or a late-only settle callback. Keep it alive through all cleanup-producing stop hooks.
- [ ] Propagate required status/counts through local and remote worker status/readiness; heartbeat success cannot clear another admission reason.
- [ ] Enforce callback-exited/real-thread-joined difference; preserve explicit unclean stop with live I/O, owner and pools retained.
- [ ] GREEN native thread/barrier tests plus existing runtime/tools suite under root-controlled isolated runner.
- [ ] Independent lifecycle/spec review.

## Task 7: Integration, true-restart F16 and crash acceptance

**Files:** lane-owned new ART scripts/fixtures, root final reports and existing architecture status docs only after verified evidence.

**Consumes:** integrated Tasks 1–6 and approved acceptance matrix. **Produces:** measured acceptance, honest gaps and release scope.

- [ ] Freeze changed source/test/harness hashes; execute RED probes against preserved pre-change source where practical and keep earlier failure evidence.
- [ ] Root runs native methods, isolated PG commit/ACK-loss, multi-generation defer, administrative supersession and new fixed-endpoint real restart.
- [ ] Root runs process-kill boundaries before/after persistence with exact callback/remote counters and conservative fallback; never shorten default TTL/stale to claim live settlement.
- [ ] Verify 55-second stop/repeated signals, physical joins and no premature pool/owner close. Persistent DB failure is honest pending, not F16 PASS.
- [ ] Verify scoped work at 300k/500k history with indexed bounded queues; this is cost/regression coverage, not repair or reacceptance of the failed mixed-capacity cases.
- [ ] Run affected full regressions once integrated, fix confirmed regressions, perform final independent whole-change review and report exact implementation/test/deployment boundaries.

## Execution rulings

- User approval “B可以” authorizes the full B source/test/schema work and isolated validation, so do not ask for another routine implementation confirmation.
- The current linked worktree and installed dependencies are reused; do not reinstall or create another worktree.
- Commit steps in the general skill are omitted because delivery was not authorized. No destructive evidence cleanup.
- Fresh implementation agents use fixed file ownership; existing analysis agents may supply read-only knowledge, never silently become a second writer.
- Review and test verdicts are separate. Passing isolated tests does not imply F16, capacity, production or deployment acceptance.
