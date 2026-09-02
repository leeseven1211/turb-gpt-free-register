# Registration Auth Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Roxy the stable registration/login orchestrator, use Protocol only through explicit stage adapters, and make registration, live-check/AT refresh, password setup, and 2FA setup share recoverable authentication outcomes.

**Architecture:** Add a storage-neutral authentication outcome contract. Roxy remains authoritative for browser pages, challenge ordering, unknown page handling, and fallback. Protocol v2 remains an assist adapter for deterministic token/auth stages and returns classified outcomes; it never causes a new registration after an unknown result. Registration and account-completion workers consume the same outcome vocabulary and preserve existing checkpoints.

**Tech Stack:** Python 3, `unittest`, Selenium/Roxy browser adapters, existing Protocol v2 HTTP adapter, PostgreSQL-backed storage contracts, existing task/event projections.

**Spec:** `docs/superpowers/specs/2026-09-02-registration-auth-compatibility-design.md`

## Global Constraints

- Roxy remains the primary registration and browser-authentication driver; Protocol is a replaceable stage adapter.
- No PostgreSQL historical-account inventory or runtime-data mutation during tests.
- No passwords, OTPs, TOTP secrets, Tokens, cookies, callback URLs, or raw response bodies in the new result model, logs, or tests.
- A remote result classified as `request_unknown` must preserve the checkpoint and must not start a new registration.
- Existing account password fields are distinct from email-provider credentials.
- Password and 2FA setup remain idempotent/checkpointed and are executed serially on one authenticated browser session.
- Every production behavior change starts with a failing test and is followed by the focused test and the relevant regression suite.

---

### Task 1: Record the design and establish the implementation baseline

**Files:**
- Create: `docs/superpowers/specs/2026-09-02-registration-auth-compatibility-design.md`
- Create: `docs/superpowers/plans/2026-09-02-registration-auth-compatibility.md`
- Test: Existing focused suites listed in the execution notes below.

**Interfaces:**
- Consumes: Current Roxy registration, Protocol v2 liveness, account-completion, and postprocess behavior.
- Produces: The approved design and this executable plan.

- [x] **Step 1: Capture the approved architecture and non-goals.**

  Keep Roxy primary, Protocol replaceable, and prohibit blind re-registration after an unknown remote result.

- [x] **Step 2: Run the focused baseline.**

  Run:

  ```bash
  /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_registration_password_flow tests.test_roxy_twofa tests.test_roxy_phone_country tests.test_account_tasks tests.test_account_completion_service tests.test_registration_postprocess_contract tests.test_registration_state_machine_contract tests.test_account_twofa_direct tests.test_protocol_v2_liveness
  ```

  Expected: 148 tests, 0 failures.

- [ ] **Step 3: Commit the design and plan.**

  ```bash
  git add docs/superpowers/specs/2026-09-02-registration-auth-compatibility-design.md docs/superpowers/plans/2026-09-02-registration-auth-compatibility.md
  git commit -m "docs: define registration auth compatibility design"
  ```

### Task 2: Add the unified authentication outcome contract

**Files:**
- Create: `core/auth_challenge.py`
- Create: `tests/test_auth_challenge_contract.py`
- Modify: `core/registration/state_machine.py:1-250`
- Test: `tests/test_registration_state_machine_contract.py`

**Interfaces:**
- Consumes: Existing `PageState`, `classify_page`, and Protocol v2 error codes.
- Produces: `AuthStatus`, `AuthAttemptResult`, `normalize_auth_result()`, and a `MFA_TOTP` page state that both browser and protocol adapters can name consistently.

- [ ] **Step 1: Write failing contract tests.**

  Add tests that require:

  ```python
  result = AuthAttemptResult(
      status=AuthStatus.AUTHENTICATED,
      auth_method="email_otp",
      challenge_chain=("email_otp", "totp"),
      remote_identity="existing",
  )
  self.assertEqual(
      {
          "status": "authenticated",
          "auth_method": "email_otp",
          "challenge_chain": ["email_otp", "totp"],
          "remote_identity": "existing",
          "retryable": False,
          "roxy_fallback_allowed": True,
          "next_action": "continue",
      },
      result.as_dict(),
  )
  ```

  Also assert that `detail`, `access_token`, `callback_url`, `password`, and `totp_secret` supplied in a mapping never appear in `as_dict()`, and that Protocol v2 codes normalize to `password_rejected`, `password_result_unknown`, `unsupported`, or `request_unknown` without changing their safety flags.

- [ ] **Step 2: Run only the new contract test to verify the expected failure.**

  Run: `.venv/bin/python -m unittest tests.test_auth_challenge_contract`

  Expected: FAIL because the new result model and/or enum do not exist.

- [ ] **Step 3: Implement the minimal storage-neutral model.**

  Define string enums/constants for `authenticated`, `password_required`, `password_rejected`, `email_otp_required`, `email_otp_invalid`, `totp_required`, `totp_rejected`, `unsupported`, `request_unknown`, and `remote_existing`. Implement a frozen dataclass with safe defaults and `as_dict()` that emits lists instead of tuples and only the contract fields.

- [ ] **Step 4: Extend page classification with TOTP precedence.**

  Add `PageState.MFA_TOTP`. In `classify_page()`, detect authenticator/TOTP/MFA controls before the generic OTP markers and never classify an explicit `/email-verification` page as TOTP. Add transition coverage for `OTP_ACCEPTED → MFA_TOTP → AUTHENTICATED` and `EMAIL_VERIFIED → MFA_TOTP`.

- [ ] **Step 5: Run the focused contract tests.**

  Run: `.venv/bin/python -m unittest tests.test_auth_challenge_contract tests.test_registration_state_machine_contract`

  Expected: PASS.

- [ ] **Step 6: Commit the contract.**

  ```bash
  git add core/auth_challenge.py core/registration/state_machine.py tests/test_auth_challenge_contract.py tests/test_registration_state_machine_contract.py
  git commit -m "feat: add unified authentication outcome contract"
  ```

### Task 3: Complete the Roxy browser challenge chain

**Files:**
- Modify: `core/roxy_codex_oauth.py:366-620,731-887,1114-1179`
- Modify: `core/registration/roxy.py:1781-1826,4354-4390`
- Create: `tests/test_roxy_auth_challenge_flow.py`
- Modify: `tests/test_roxy_phone_country.py`

**Interfaces:**
- Consumes: `AuthAttemptResult`, `PageState.MFA_TOTP`, `_login_challenge_state()`, `_is_totp_login_page()`, and existing saved-password/TOTP submitters.
- Produces: A Roxy flow that handles `email OTP → TOTP` and returns a classified outcome instead of treating every non-email URL as accepted.

- [ ] **Step 1: Write the failing Roxy regression tests.**

  Add a stateful fake driver test where `_wait_after_email_otp_submit()` first sees an authenticator form while the URL is still `/log-in/password`; assert it returns `totp_required` (or the equivalent normalized status). Add a second test where `_fill_email_and_otp()` receives that result, invokes the common challenge resolver, submits TOTP exactly once, and reaches `advanced`. Add a registration test for a resumed account whose sequence is `email_otp → totp → authenticated`.

- [ ] **Step 2: Run the new tests to verify the expected failure.**

  Run: `.venv/bin/python -m unittest tests.test_roxy_auth_challenge_flow`

  Expected: FAIL because the post-email-OTP wait currently returns `accepted` without resolving TOTP.

- [ ] **Step 3: Classify the post-email-OTP page before URL acceptance.**

  In both Roxy wait helpers, inspect the fresh DOM snapshot and return a distinct TOTP-required result before the generic “left email verification” branch. Preserve phone/callback acceptance behavior.

- [ ] **Step 4: Re-enter the common challenge resolver after email OTP.**

  In `core/roxy_codex_oauth.py`, when the outcome is TOTP-required, call `_complete_login_challenge_after_email()` with the already loaded saved credentials. In `core/registration/roxy.py`, do the same only when the current attempt has an existing saved password/TOTP; otherwise return `remote_existing` or a safe `totp_required` failure and do not proceed to phone verification.

- [ ] **Step 5: Preserve bounded retry semantics.**

  Do not restart or resend email OTP after a successful email OTP has advanced to TOTP. Keep the existing maximum email OTP attempts and independent TOTP submit timeout.

- [ ] **Step 6: Run the focused Roxy suites.**

  Run: `.venv/bin/python -m unittest tests.test_roxy_auth_challenge_flow tests.test_roxy_phone_country tests.test_registration_password_flow`

  Expected: PASS.

- [ ] **Step 7: Commit the Roxy chain fix.**

  ```bash
  git add core/roxy_codex_oauth.py core/registration/roxy.py tests/test_roxy_auth_challenge_flow.py tests/test_roxy_phone_country.py
  git commit -m "fix: resolve Roxy email OTP followed by TOTP"
  ```

### Task 4: Make registration classify remote-existing and unknown results

**Files:**
- Modify: `core/registration/roxy.py:774-785,1460-1585,4074-4698`
- Modify: `core/registration/protocol.py:139-560`
- Modify: `core/registration_service.py:258-320,665-675,1313-1342`
- Modify: `core/registration/dispatcher.py:1-70`
- Create: `tests/test_registration_identity_reconciliation.py`
- Modify: `tests/test_registration_postprocess_contract.py`

**Interfaces:**
- Consumes: `AuthAttemptResult`, existing `registration.mark_request_unknown()`, `registration.mark_manual_reconcile()`, job status `manual_reconcile`, and Roxy/Protocol page outcomes.
- Produces: Explicit result fields `remote_identity`, `remote_identity_state`, `manual_reconcile`, `request_unknown`, and a service path that preserves the email/account instead of treating an existing remote account as an ordinary new-registration failure.

- [ ] **Step 1: Write failing identity/recovery tests.**

  Require these behaviors:

  ```python
  self.assertEqual("existing", classify_registration_identity("login_password"))
  self.assertTrue(result["manual_reconcile"])
  self.assertEqual("manual_reconcile", job_status_for_result(result))
  self.assertFalse(safe_to_start_new_registration(result))
  ```

  Also test that a logged-in/external-callback OTP result is marked `remote_identity="existing"`, while an about-you/profile result is `new_candidate`; an unknown page remains `request_unknown` and never becomes a new registration.

- [ ] **Step 2: Run the identity tests to verify the expected failure.**

  Run: `.venv/bin/python -m unittest tests.test_registration_identity_reconciliation`

  Expected: FAIL because the current driver results do not expose the normalized identity classification.

- [ ] **Step 3: Add safe Roxy identity classification.**

  Treat a login-password page reached from a normal registration as `remote_existing`, not as an untyped exception. Keep the existing saved-password resume path unchanged. Treat authenticated/session/callback after OTP as existing remote identity; treat a visible create-account profile page as a new candidate.

- [ ] **Step 4: Add Protocol result classification.**

  Mark external callback/OTP direct OAuth as `remote_existing` only when the response proves an existing session; mark about-you as `new_candidate`; mark missing/unknown continuation as `request_unknown` or `unsupported` with no blind `create_account`.

- [ ] **Step 5: Wire service status and storage facts.**

  Add a small `_mark_registration_manual_reconcile()` adapter beside `_mark_registration_request_unknown()`. When a driver returns `manual_reconcile`, finish progress without releasing the email as reusable, mark the job `manual_reconcile`, and persist the Attempt as manual reconciliation. Do not create a fresh registration retry.

- [ ] **Step 6: Run registration recovery tests.**

  Run: `.venv/bin/python -m unittest tests.test_registration_identity_reconciliation tests.test_registration_postprocess_contract tests.test_registration_service_postprocess_contract tests.test_registration_dispatcher`

  Expected: PASS.

- [ ] **Step 7: Commit identity reconciliation.**

  ```bash
  git add core/registration/roxy.py core/registration/protocol.py core/registration_service.py core/registration/dispatcher.py tests/test_registration_identity_reconciliation.py tests/test_registration_postprocess_contract.py
  git commit -m "feat: classify existing registration identities safely"
  ```

### Task 5: Use the same outcome contract for AT refresh and account completion

**Files:**
- Modify: `core/protocol_v2_liveness.py:50-90,443-570,680-720`
- Modify: `core/live_check_service.py` at the refresh-driver result boundary.
- Modify: `core/codex_retry_service.py:493-721`
- Modify: `core/account_completion_service.py:95-230`
- Create: `tests/test_auth_completion_matrix.py`
- Modify: `tests/test_protocol_v2_liveness.py`
- Modify: `tests/test_account_tasks.py`
- Modify: `tests/test_account_completion_service.py`

**Interfaces:**
- Consumes: `AuthAttemptResult`, Protocol v2 error codes, existing account planner, password checkpoint callback, and 2FA Secret checkpoint callback.
- Produces: Consistent result projections for refresh AT, password setup, and 2FA setup; serialized password/2FA execution; explicit retry/manual action without rolling back core account state.

- [ ] **Step 1: Write the cross-operation matrix tests.**

  Cover all four saved-credential combinations for both Roxy login and Protocol v2 refresh:

  ```text
  no password + no TOTP
  password + no TOTP
  no password + TOTP
  password + TOTP
  ```

  Assert correct handling for password success, password rejection, result unknown, email OTP, email OTP followed by TOTP, missing TOTP, password checkpoint, and 2FA Secret checkpoint. Assert that `run_twofa_worker()` still executes password before 2FA on the same session.

- [ ] **Step 2: Run the new matrix tests to verify the expected failures.**

  Run: `.venv/bin/python -m unittest tests.test_auth_completion_matrix`

  Expected: FAIL at the newly required normalized projections and the Roxy email-OTP-to-TOTP completion case.

- [ ] **Step 3: Normalize Protocol v2 results.**

  Add an `auth` compatibility projection to success/failure dictionaries using `AuthAttemptResult`. Preserve existing `error`, `password_auth_status`, `roxy_fallback_allowed`, and `auth_method` fields for callers. Keep `password_rejected` and `password_result_unknown` fallback restrictions unchanged.

- [ ] **Step 4: Normalize Roxy account-completion results.**

  Convert browser challenge completion and setup failures to the same safe codes. Preserve the existing password checkpoint immediately after submit and the 2FA Secret checkpoint before activation. Do not mask a successful account core with a postprocess failure.

- [ ] **Step 5: Keep parent/child completion semantics explicit.**

  Have the planner/worker identify `refresh_at`, `password`, `twofa`, `plan_check`, and `codex` as independent capability results. A parent task is `partial_success`/pending when a child is still pending, not fully complete.

- [ ] **Step 6: Run the account-completion suites.**

  Run: `.venv/bin/python -m unittest tests.test_auth_completion_matrix tests.test_protocol_v2_liveness tests.test_account_tasks tests.test_account_completion_service tests.test_account_twofa_direct tests.test_registration_postprocess_contract`

  Expected: PASS.

- [ ] **Step 7: Commit the completion integration.**

  ```bash
  git add core/auth_challenge.py core/protocol_v2_liveness.py core/live_check_service.py core/codex_retry_service.py core/account_completion_service.py tests/test_auth_completion_matrix.py tests/test_protocol_v2_liveness.py tests/test_account_tasks.py tests/test_account_completion_service.py
  git commit -m "feat: unify authentication outcomes for account completion"
  ```

### Task 6: Publish the current support matrix and finish verification

**Files:**
- Create: `docs/registration-auth-support-matrix.md`
- Modify: `docs/core-registration-flow.md`
- Modify: `docs/registration-account-config-redesign.md`
- Modify: `docs/account-auth-protocol-staged-rollout-checklist.md`
- Test: All registration/auth/account-completion suites below.

**Interfaces:**
- Consumes: Implemented result codes, task outcomes, configuration defaults, and focused tests.
- Produces: A current matrix that distinguishes fully supported, conditional, manual-reconcile, and unsupported cases.

- [ ] **Step 1: Write the matrix from code behavior.**

  Include registration, existing remote identity, password/OTP/TOTP combinations, wrong password, unknown results, refresh AT, password setup, 2FA setup, Codex/plan child work, retry action, and preserved checkpoints. Every row must name its driver boundary.

- [ ] **Step 2: Run the complete relevant regression set.**

  ```bash
  /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_auth_challenge_contract tests.test_registration_identity_reconciliation tests.test_roxy_auth_challenge_flow tests.test_registration_password_flow tests.test_roxy_phone_country tests.test_roxy_twofa tests.test_registration_state_machine_contract tests.test_registration_postprocess_contract tests.test_registration_service_postprocess_contract tests.test_registration_dispatcher tests.test_protocol_v2_liveness tests.test_live_check_router tests.test_live_check_browser tests.test_account_completion_service tests.test_account_tasks tests.test_account_twofa_direct
  ```

  Expected: 0 failures. Report the exact test count from the command output.

- [ ] **Step 3: Run static and repository checks.**

  ```bash
  git diff --check
  python -m compileall -q core tests
  git status --short --branch
  ```

  Expected: no whitespace errors, compile success, and only intended files changed.

- [ ] **Step 4: Review the implementation against the spec.**

  Verify each acceptance item in `docs/superpowers/specs/2026-09-02-registration-auth-compatibility-design.md`, especially no blind registration after unknown results, no credential leakage, and Roxy fallback boundaries.

- [ ] **Step 5: Commit the matrix and final changes.**

  ```bash
  git add docs/registration-auth-support-matrix.md docs/core-registration-flow.md docs/registration-account-config-redesign.md docs/account-auth-protocol-staged-rollout-checklist.md
  git commit -m "docs: publish registration auth support matrix"
  ```

