# Task Progress Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every task detail progress bar show the selected Run's real ordered business flow, with conditional branches and paginated event timelines kept separate.

**Architecture:** Add a pure backend progress projector that consumes one Run's planned flow, structured events, result summary, and run status. The operation detail endpoint will expose this per-Run snapshot; the frontend will render the snapshot and stop deriving progress from the latest page of events. Existing raw stages and event history remain compatible.

**Tech Stack:** Python 3, PostgreSQL JSONB, Flask, vanilla JavaScript, pytest.

**Spec:** `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/superpowers/specs/2026-09-07-task-progress-flow-design.md`

## Global Constraints

- Preserve the user's existing uncommitted changes and private runtime data.
- Never use `rm -r` or `rm -rf`; no deletion is needed for this change.
- Do not expose passwords, OTPs, Tokens, Cookies, Authorization values, or complete proxy credentials in progress responses.
- Progress is calculated per `task_id` and `run_id`; a parent task accepted/busy result is not a child task success.
- Unknown, cleanup, diagnostic, and ordinary note events stay out of the main step list.
- Tests use the repository's isolated PostgreSQL test support and must not connect to production `turb_console`.

---

### Task 1: Add the pure Run progress projector

**Files:**
- Create: `core/task_progress.py`
- Modify: `core/task_stages.py` only if a canonical label or flow contract is missing
- Test: `tests/test_task_progress.py`

**Interfaces:**
- Consumes: `task_type`, `run`, `events`, and the existing `flow_for()` output.
- Produces: `build_progress_snapshot(task_id, run_id, task_type, run, events) -> dict` with `main_steps`, `current`, `outcome`, `source`, `flow_version`, and `revision`.

- [ ] **Step 1: Write failing projector tests**

Add tests using in-memory event dictionaries for these behaviors:

```python
def test_password_setup_keeps_auth_events_before_result():
    snapshot = build_progress_snapshot(44430, 44422, "password_setup", run, events)
    assert [item["id"] for item in snapshot["main_steps"]] == [
        "network", "browser", "authenticate", "set_password", "result",
    ]
    assert snapshot["current"]["step_id"] == "authenticate"


def test_unknown_event_does_not_append_after_result():
    snapshot = build_progress_snapshot(..., events=[success("complete"), note("login")])
    assert snapshot["main_steps"][-1]["id"] == "result"
    assert all(item["id"] != "login" for item in snapshot["main_steps"])


def test_protocol_twofa_omits_browser_and_browser_fallback_includes_it():
    direct = build_progress_snapshot(..., task_type="twofa_setup", events=protocol_events)
    fallback = build_progress_snapshot(..., task_type="twofa_setup", events=fallback_events)
    assert [item["id"] for item in direct["main_steps"]] == ["network", "set_twofa", "result"]
    assert [item["id"] for item in fallback["main_steps"]] == ["network", "set_twofa", "result"]
    assert fallback["main_steps"][1]["children"][0]["step_id"] == "browser_fallback"
```

- [ ] **Step 2: Run only the new tests and verify the expected RED failure**

Run:

```bash
../turb-gpt-free-register/.venv/bin/python -m pytest tests/test_task_progress.py -q
```

Expected: collection fails because `core.task_progress` and `build_progress_snapshot` do not exist.

- [ ] **Step 3: Implement the smallest projector that satisfies the tests**

Define explicit task presentation templates and branch helpers. Normalize only known stage aliases. Use structured `detail.step_id`, `parent_step_id`, `branch_id`, and `browser_opened` when present; use a task-type adapter for legacy events. Ignore `queued`, `complete` as a raw stage, ordinary notes, cleanup, and unknown stages as main nodes. Put the terminal `result` node last. Derive `current` from explicit running evidence and set `source` to `explicit`, `legacy_derived`, or `insufficient_evidence`.

Calculate `revision` from the JSON-serializable normalized plan, relevant event fields, run status, and result summary, using a stable SHA-256 digest. Redact event details from the output and return only safe evidence summaries.

- [ ] **Step 4: Run the projector tests and then its focused edge cases**

Run:

```bash
../turb-gpt-free-register/.venv/bin/python -m pytest tests/test_task_progress.py -q
```

Expected: all projector tests pass without database access.

### Task 2: Expose a complete per-Run progress snapshot

**Files:**
- Modify: `core/storage/operation.py` in `get_task()` and add a Run progress read helper
- Modify: `webui/routes/operations.py`
- Test: `tests/test_operation_task_store.py`, `tests/test_dashboard_api.py`

**Interfaces:**
- Consumes: `build_progress_snapshot()` and operation tables `operation_tasks`, `operation_runs`, `operation_events`.
- Produces: `GET /api/operations/<task_id>/runs/<run_id>/progress` returning `{ok, progress}`; the existing detail response retains `flow` and gains a safe `progress` for the selected/latest Run when available.

- [ ] **Step 1: Write failing API and storage tests**

Seed one task with two Runs and more than 500 events. Assert the selected Run's progress excludes events from the other Run, has the terminal result last, and remains the same when timeline pagination is changed. Assert a nonexistent Run returns 404 and a Run belonging to another task cannot be read.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
../turb-gpt-free-register/.venv/bin/python -m pytest tests/test_operation_task_store.py tests/test_dashboard_api.py -q
```

Expected: the new endpoint/response assertions fail because the progress API is absent.

- [ ] **Step 3: Implement the Run-scoped read path**

Read task, Run, plan metadata, all structured progress events needed by the projector, and result data in one database transaction. Do not use the timeline endpoint's 500-event page. Return a typed `LookupError` for missing task/Run ownership. Keep the existing detail response backward compatible.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the same pytest command. Expected: all new storage/API tests pass and existing operation tests remain green.

### Task 3: Emit enough explicit metadata at the key execution boundaries

**Files:**
- Modify: `core/task_reporter.py`
- Modify: `core/codex_retry_service.py`
- Modify: `core/roxy_codex_oauth.py`
- Modify: `core/account_completion_service.py`
- Modify: `core/registration/roxy.py`, `core/registration/protocol.py`, `core/registration/browser_use.py` only at already existing stage-report calls
- Test: the existing focused service tests plus `tests/test_task_progress.py`

**Interfaces:**
- Consumes: existing `TaskReporter.stage()` and account-task stage reporters.
- Produces: safe `step_id`, `parent_step_id`, `branch_id`, and `instance_id` metadata without changing the business execution order or credentials.

- [ ] **Step 1: Add failing contract tests for key sequences**

Use the existing service seams and reporter capture fixtures to assert: account setup emits `network` before `plan_check`; protocol 2FA can complete without `browser`; browser fallback emits a child branch; password setup distinguishes authentication from password setting; account completion labels independent refresh/Codex submissions as dispatch/partial outcomes.

- [ ] **Step 2: Run the focused service tests and verify RED**

Run:

```bash
../turb-gpt-free-register/.venv/bin/python -m pytest tests/test_account_twofa_direct.py tests/test_account_completion_service.py tests/test_roxy_twofa.py -q
```

Expected: the new metadata assertions fail while existing behavior remains otherwise unchanged.

- [ ] **Step 3: Add metadata through existing reporting calls**

Extend `TaskReporter.stage()` and the account-task reporter adapter to accept optional safe presentation metadata. Mark browser initialization separately from its long-lived action scope; mark login-email submission as an authentication child step; distinguish password reset/checkpoint/remote confirmation; identify protocol vs browser 2FA branches; include only verified child task/run IDs for independent dispatches.

- [ ] **Step 4: Run service tests and the full relevant regression set**

Run the focused command above, then run the repository's task/progress tests. Expected: metadata tests pass and no credential-bearing values appear in serialized detail.

### Task 4: Render only the Run snapshot in the modern account task UI

**Files:**
- Modify: `webui/static/js/modern/accounts.js`
- Modify: `webui/static/css/modern.css` if child steps, result states, or narrow layouts require it
- Test: `tests/test_dashboard_api.py` and browser/DOM replay checks using fixture JSON

**Interfaces:**
- Consumes: `GET /api/operations/<task_id>/runs/<run_id>/progress`.
- Produces: a stable main-step bar whose final item is always the result node, a current child-step description, and a timeline independent of progress loading.

- [ ] **Step 1: Write failing UI contract tests**

Assert the page source requests the Run progress endpoint, does not append `observed` stages to the flow, and preserves the event endpoint for the timeline. Replay the #44430 snapshot and assert the rendered main-step IDs are `network`, `browser`, `authenticate`, `set_password`, `result`; assert `login` cannot appear after `result`.

- [ ] **Step 2: Run the UI contract tests and verify RED**

Run:

```bash
../turb-gpt-free-register/.venv/bin/python -m pytest tests/test_dashboard_api.py -q
```

Expected: the new endpoint/render assertions fail against the current event-derived implementation.

- [ ] **Step 3: Implement the snapshot-driven renderer**

Load progress after the selected Run is known. Track task/Run/request generation to ignore stale responses. Render `main_steps` in server order, render children under their parent, and render outcome/association separately. Never add a stage from timeline events. Keep the last successful snapshot on refresh failure and show an update warning; do not fall back to the current timeline page.

- [ ] **Step 4: Run UI tests and perform visual replay**

Run the focused pytest command, start the WebUI on port 8000 if needed, replay the fixture in the task modal, and check desktop plus narrow layout. Verify no horizontal overflow, the terminal result remains last, and status meaning is available in text as well as color.

### Task 5: Final verification and branch handoff

**Files:**
- Modify: only files required by the preceding tasks
- Test: all relevant Python tests and static checks

- [ ] **Step 1: Run the complete focused regression suite**

```bash
../turb-gpt-free-register/.venv/bin/python -m pytest tests/test_task_progress.py tests/test_operation_task_store.py tests/test_dashboard_api.py tests/test_account_tasks.py tests/test_account_twofa_direct.py tests/test_account_completion_service.py tests/test_roxy_twofa.py -q
```

- [ ] **Step 2: Run repository syntax and whitespace checks**

```bash
../turb-gpt-free-register/.venv/bin/python -m compileall -q core webui
git diff --check
```

- [ ] **Step 3: Inspect the final diff and verify scope**

Confirm the diff contains no `.env`, runtime logs, account exports, tokens, or unrelated user changes. Confirm the source branch is `codex/task-progress-flow` and report its path and validation results.
