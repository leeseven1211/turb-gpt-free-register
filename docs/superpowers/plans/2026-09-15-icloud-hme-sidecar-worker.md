# iCloud HME Sidecar Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sidecar's fixed-account auto-create loop with a single-request, multi-account scheduler that automatically skips quota, rate-limit, and authentication failures per account.

**Architecture:** Keep `scripts/auto-create-worker.sh` as the launch/compatibility entrypoint, but move scheduling into a testable standard-library Python module `scripts/auto_create_worker.py`. The worker refreshes `/api/accounts`, keeps an in-memory cursor and account cooldown state, calls `POST /api/create` directly with one explicit account ID, and preserves the existing 120–180 second success delay, 300 second ordinary failure delay, and network pause behavior.

**Tech Stack:** Python 3 standard library (`urllib`, `json`, `unittest`), Bash wrapper, sidecar HTTP API.

**Spec:** `docs/superpowers/specs/2026-09-15-icloud-hme-account-pool-design.md`

## Global Constraints

- Never log cookies, App passwords, API tokens, or full credential payloads.
- Never issue parallel alias-creation requests.
- Keep `ICLOUD_HME_AUTO_ACCOUNT_ID` as an explicit fixed-account override.
- A quota or rate-limit failure on one account must not stop eligible accounts.
- Network unavailability pauses the global worker; account-level provider errors do not.
- Do not modify sidecar account data or aliases in worker tests.

### Task 1: Create a testable account scheduler and error classifier

**Files:**
- Create: `/Users/lihongwei/code/personal/icloud/scripts/auto_create_worker.py`
- Create: `/Users/lihongwei/code/personal/icloud/scripts/auto_create_worker_test.py`

**Interfaces:**
- `class ApiError(RuntimeError)`: fields `status_code: int | None`, `retry_after: int | None`, and `body: str`.
- `def classify_error(error: Exception) -> str`: returns one of `quota`, `rate_limit`, `auth`, `network`, `other`.
- `class AutoCreateWorker`: constructor accepts `url`, `label`, delay values, fixed account ID, and injectable `request_json`, `clock`, and `sleep` callables; methods `refresh_accounts()`, `choose_account()`, `create_once(account_id)`, `run_iteration()`, and `run(max_iterations: int | None = None)`.

- [ ] **Step 1: Write failing unit tests for selection and error isolation**

Use a fake request function and a deterministic clock. Add tests with these assertions:

```python
def test_round_robin_skips_quota_account(self):
    worker = self.worker(accounts=[
        {"id": "acc-old", "status": "active", "created_at": "2026-01-01"},
        {"id": "acc-new", "status": "active", "created_at": "2026-01-02"},
    ])
    self.requests.create.side_effect = [
        ApiError("limit of addresses you can create", status_code=400),
        {"email": "new@icloud.com"},
    ]
    self.assertEqual(worker.run_iteration(), "quota")
    self.assertEqual(worker.run_iteration(), "success")
    self.assertTrue(worker.states["acc-old"].quota_exhausted)
    self.assertEqual(self.requests.created_account_ids, ["acc-old", "acc-new"])

def test_new_active_account_is_added_on_refresh(self):
    worker = self.worker(accounts=[{"id": "acc-a", "status": "active"}])
    self.assertEqual(worker.refresh_accounts(), ["acc-a"])
    self.accounts_response[:] = [
        {"id": "acc-a", "status": "active"},
        {"id": "acc-b", "status": "active"},
    ]
    self.assertEqual(worker.refresh_accounts(), ["acc-a", "acc-b"])

def test_fixed_override_only_uses_requested_account(self):
    worker = self.worker(
        accounts=[{"id": "acc-a", "status": "active"}, {"id": "acc-b", "status": "active"}],
        fixed_account_id="acc-b",
    )
    self.assertEqual(worker.refresh_accounts(), ["acc-b"])
```

Also test `classify_error` for HTTP 429, address quota text, 401/403, `urllib.error.URLError`, and an ordinary exception.

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `python3 -m unittest /Users/lihongwei/code/personal/icloud/scripts/auto_create_worker_test.py -v`

Expected: FAIL because the module and scheduler do not exist.

- [ ] **Step 3: Implement structured HTTP helpers and error classification**

Implement `request_json(method, url, body=None, timeout=60)` with `urllib.request`. Decode JSON only after reading the response; on HTTP errors preserve status, `Retry-After`, and a bounded body excerpt in `ApiError`. Use markers that distinguish address quota (`limit of addresses`, `reached the limit of addresses`, `maximum number of aliases`, `quota`) from rate limiting (`429`, `too many requests`, `rate limit`, `请求过于频繁`). Treat 401/403 and authentication/session/cookie markers as `auth`; `URLError` is `network`.

- [ ] **Step 4: Implement account refresh and round-robin selection**

`refresh_accounts()` calls `GET /api/accounts`, filters `status == "active"`, sorts `(created_at, id)`, and preserves the current cursor when accounts are added or removed. If `ICLOUD_HME_AUTO_ACCOUNT_ID` is set, return only that ID and do not choose another account. Maintain `AccountState` records with `cooldown_until`, `quota_exhausted`, and `auth_error`; stale state for removed accounts is retained only in memory and cannot be selected.

- [ ] **Step 5: Implement one-request creation and per-account state transitions**

`create_once(account_id)` posts `{"account_id": account_id, "label": label}` to `/api/create`. On success return `success`. On `quota`, mark only that account `quota_exhausted`; on `rate_limit`, set that account's cooldown to `now + retry_after` or the configured rate-limit cooldown; on `auth`, set the account cooldown and `auth_error`; on ordinary errors set a shorter account cooldown. Return the classification string so the loop can choose the next account on its next iteration.

- [ ] **Step 6: Run the scheduler unit tests**

Run: `python3 -m unittest /Users/lihongwei/code/personal/icloud/scripts/auto_create_worker_test.py -v`

Expected: PASS for account refresh, fixed override, round-robin, quota isolation, rate-limit cooldown, auth classification, and new-account discovery.

- [ ] **Step 7: Commit the testable scheduler in the sidecar repository**

```bash
cd /Users/lihongwei/code/personal/icloud
git add scripts/auto_create_worker.py scripts/auto_create_worker_test.py
git commit -m "feat: add multi-account HME auto-create scheduler"
```

Only the two listed files may be staged; preserve the sidecar repository's existing unrelated modifications.

### Task 2: Preserve the launch entrypoint and worker timing contract

**Files:**
- Modify: `/Users/lihongwei/code/personal/icloud/scripts/auto-create-worker.sh`
- Modify: `/Users/lihongwei/code/personal/icloud/scripts/auto-create-worker_test.sh`
- Test: `/Users/lihongwei/code/personal/icloud/scripts/auto_create_worker_test.py`

**Interfaces:**
- The existing `.sh` path remains executable by LaunchAgent and invokes the Python scheduler.
- Existing environment variables remain supported: `ICLOUD_HME_URL`, `ICLOUD_HME_AUTO_LABEL`, `ICLOUD_HME_AUTO_ACCOUNT_ID`, `ICLOUD_HME_SUCCESS_DELAY_MIN`, `ICLOUD_HME_SUCCESS_DELAY_MAX`, `ICLOUD_HME_FAILURE_DELAY`, `ICLOUD_HME_NETWORK_RETRY_DELAY`, and `ICLOUD_HME_NETWORK_CHECK_URL`.
- Add optional `ICLOUD_HME_RATE_LIMIT_COOLDOWN`, `ICLOUD_HME_AUTH_RETRY_DELAY`, and `ICLOUD_HME_AUTO_MAX_ITERATIONS` (the last is for tests/controlled probes and defaults to unlimited).

- [ ] **Step 1: Add failing wrapper-contract assertions**

Update `auto-create-worker_test.sh` to assert that the wrapper references `auto_create_worker.py`, preserves `ICLOUD_HME_AUTO_ACCOUNT_ID`, and does not execute the old fixed-account CLI loop. Add a Python test that a success sleeps within the configured 120–180 second range and an ordinary failure uses 300 seconds when injected with a fake sleep function.

- [ ] **Step 2: Run wrapper tests and verify the new assertions fail**

Run: `bash /Users/lihongwei/code/personal/icloud/scripts/auto-create-worker_test.sh` and `python3 -m unittest /Users/lihongwei/code/personal/icloud/scripts/auto_create_worker_test.py -v`

Expected: FAIL because the existing Bash script still owns the loop.

- [ ] **Step 3: Replace the Bash loop with an exec wrapper**

Keep the shebang and executable path, resolve `SCRIPT_DIR`, choose `${PYTHON:-python3}`, and `exec "$PYTHON" "$SCRIPT_DIR/auto_create_worker.py"`. Do not delete the file or change LaunchAgent paths.

- [ ] **Step 4: Implement the worker loop and timing behavior**

Before each iteration, check network availability using `ICLOUD_HME_NETWORK_CHECK_URL`; if unavailable, log a pause and poll every `NETWORK_RETRY_DELAY`. Refresh accounts, select one eligible account, and issue exactly one create request. Sleep a random value in `[SUCCESS_DELAY_MIN, SUCCESS_DELAY_MAX]` after success, `FAILURE_DELAY` after ordinary/account-level failure, and the configured network retry delay only while the network is down. When all accounts are exhausted or cooling down, sleep `FAILURE_DELAY` and refresh on the next iteration.

- [ ] **Step 5: Run the wrapper and timing tests**

Run: `bash /Users/lihongwei/code/personal/icloud/scripts/auto-create-worker_test.sh && python3 -m unittest /Users/lihongwei/code/personal/icloud/scripts/auto_create_worker_test.py -v`

Expected: PASS. No real sidecar request should occur because tests inject the request function or stop after a bounded iteration count.

- [ ] **Step 6: Commit the wrapper and timing changes**

```bash
cd /Users/lihongwei/code/personal/icloud
git add scripts/auto-create-worker.sh scripts/auto-create-worker_test.sh scripts/auto_create_worker_test.py
git commit -m "feat: rotate HME worker accounts without global retries"
```

### Task 3: Document operational migration and verify sidecar scope

**Files:**
- Modify: `/Users/lihongwei/code/personal/icloud/README.md:118-126`
- Modify: `/Users/lihongwei/code/personal/icloud/API.md` only if structured error wording needs documenting

- [ ] **Step 1: Update the worker documentation**

Document that an empty `ICLOUD_HME_AUTO_ACCOUNT_ID` dynamically discovers all active accounts, a non-empty value pins the worker for troubleshooting, and one create request is sent every 120–180 seconds by default. Explain that quota and 429 errors skip only the affected account, while network outages pause the entire worker. State that the worker never logs credentials.

- [ ] **Step 2: Run static checks and sidecar tests**

Run: `python3 -m py_compile /Users/lihongwei/code/personal/icloud/scripts/auto_create_worker.py && bash /Users/lihongwei/code/personal/icloud/scripts/auto-create-worker_test.sh && python3 -m unittest /Users/lihongwei/code/personal/icloud/scripts/auto_create_worker_test.py -v`

If the Go project has a passing baseline, also run `go test ./...` from `/Users/lihongwei/code/personal/icloud`; report unrelated failures from the pre-existing dirty worktree separately.

- [ ] **Step 3: Commit only the sidecar worker documentation**

```bash
cd /Users/lihongwei/code/personal/icloud
git add README.md API.md
git commit -m "docs: document multi-account HME worker rotation"
```

Do not stage `main.go`, `internal/`, or any other pre-existing sidecar changes in this commit.

### Task 4: Controlled cross-repository verification

**Files:**
- No new production files.
- Verify: turb tests from `2026-09-15-icloud-hme-turb-account-pool.md` and sidecar worker tests.

- [ ] **Step 1: Confirm sidecar worker is not running during test probes**

Inspect the current LaunchAgent/process state before any live test. Do not kill or restart it as part of unit testing; only report its state.

- [ ] **Step 2: Run both focused suites**

Run the turb iCloud suite and sidecar Python/shell worker suite. Expected: all focused tests pass without creating a real alias.

- [ ] **Step 3: Verify final diffs and dirty-worktree provenance**

Run `git status --short` in both repositories and confirm turb contains only its planned commits, while sidecar retains unrelated pre-existing changes. Report commit SHAs separately; do not claim deployment or worker activation.

- [ ] **Step 4: Prepare the operator migration, but do not apply it automatically**

The operator action is to clear the existing turb `ICLOUD_HME_ACCOUNT_ID` once, restart/reload turb, and leave sidecar `ICLOUD_HME_AUTO_ACCOUNT_ID` empty. This plan does not edit `.env`, update cookies, launch the worker, or create a live alias without an explicit operational request.
