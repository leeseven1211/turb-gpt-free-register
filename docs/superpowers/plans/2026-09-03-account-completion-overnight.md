# Account Completion Overnight Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify every account that still has configured completion gaps, process them in bounded batches, verify durable writeback after each batch, and apply evidence-backed fixes before continuing.

**Architecture:** Use `completion_plan()` as the single classifier and the WebUI `setup-bulk` endpoint as the execution boundary. The shared account-operation executor enforces the configured concurrency; each batch is monitored from PostgreSQL task state and account fields, with failed work retained for diagnosis and safe retry only after a proven fix.

**Tech Stack:** Python 3.12, Flask WebUI, PostgreSQL task/account storage, pytest, RoxyBrowser and proxy integrations.

**Spec:** User request in the current task: classify remaining account-completion gaps, run bounded batches, optimize after each batch, and finish the configured account setup overnight.

## Global Constraints

- Do not re-register accounts or overwrite existing tokens, sessions, passwords, or partial 2FA checkpoints.
- Use PostgreSQL task/account state as runtime truth; do not use JSON/TXT exports or SQLite for selection.
- Exclude deactivated accounts and accounts with queued/running/cancelling/settling tasks before every batch.
- Keep registration worker pools separate; account-page operations use `ACCOUNT_BATCH_WORKERS`.
- Do not retry a failed account until its failure category and remote-state impact are recorded.
- Redact emails, passwords, tokens, OTPs, proxy credentials, and full proxy URLs from progress reports.

### Task 1: Build the remaining-account inventory

**Files:**
- Read: `core/account_completion_service.py`
- Read: `core/storage/db_legacy.py`
- Read: `core/storage/operation.py`
- Read: `docs/storage-architecture.md`

**Interfaces:**
- Consume `db.list_accounts()`, `completion_plan()`, `account_task_store.list_tasks()`, and `operation_task_store.list_tasks()`.
- Produce category counts and account ID lists for `missing:password+twofa`, `missing:twofa`, `missing:password`, `missing:plan_check+twofa`, and other configured gaps.

- [ ] Query current accounts and active task states.
- [ ] Classify accounts using the configured completion plan without exposing secrets.
- [ ] Freeze the first batch only after the inventory has been rechecked.

### Task 2: Execute a bounded completion batch

**Files:**
- Use: `webui/routes/accounts.py:api_accounts_setup_bulk`
- Use: `webui/runtime.py:WebUIContext.enqueue_account_setup`
- Use: `core/account_operation_executor.py`
- Verify: `core/operations/legacy_task_store.py`

**Interfaces:**
- POST `/api/accounts/setup-bulk` with at most the selected account IDs.
- Observe task IDs, terminal statuses, latest stages, and durable account fields.

- [ ] Submit only accounts in the selected category that remain inactive and non-deactivated.
- [ ] Confirm running count never exceeds `ACCOUNT_BATCH_WORKERS`.
- [ ] Wait until the batch has zero queued/running tasks before evaluating it.
- [ ] Compare task success with password and 2FA writeback, including partial checkpoints.

### Task 3: Diagnose and optimize one failure class at a time

**Files:**
- Read: `core/task_errors.py`
- Read: `core/roxybrowser_client.py`
- Read: `core/account_proxy.py`
- Read: `core/codex_retry_service.py`
- Modify only the smallest proven root-cause file when evidence identifies a local defect.
- Test: the narrowest existing task/service test plus a new regression test when a code fix is required.

**Interfaces:**
- Consume sanitized task errors, event stages, provider responses, and active-resource state.
- Produce either a tested local fix or an explicit external-resource blocker; never hide a provider quota/network failure as success.

- [ ] Group failures by stable root cause and inspect the full boundary evidence.
- [ ] Reproduce a local defect with a failing test before editing code.
- [ ] Run focused tests and `git diff --check` after each code fix.
- [ ] Only after verification, continue with the next batch or retry a safely retryable failed subset.

### Task 4: Overnight completion and final reconciliation

**Files:**
- Read: `core/account_completion_service.py`
- Read: `core/operations/legacy_task_store.py`
- Read: `core/storage/operation.py`

- [ ] Continue category-by-category until no eligible gap remains or an external blocker is exhausted and documented.
- [ ] Recompute the inventory after every batch so successful writeback removes accounts from later batches.
- [ ] Confirm zero active tasks and zero active account-operation leases at the end.
- [ ] Report final counts, success rate, failure categories, partial writebacks, and any accounts requiring manual follow-up.
