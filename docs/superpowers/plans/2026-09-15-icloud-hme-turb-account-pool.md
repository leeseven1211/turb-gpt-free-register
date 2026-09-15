# iCloud HME turb Account Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make turb discover all active iCloud HME accounts, synchronize their aliases into the existing PostgreSQL pool, and claim aliases globally while preserving fixed-account compatibility.

**Architecture:** Keep `email_pool_icloud_hide` as the source of alias state and `account_id` as immutable alias ownership. Add a multi-account selector in `core/icloud_hme_client.py`; successful account snapshots are synchronized independently, while one account's transport/provider failure is reported without disabling another account's aliases. A blank `ICLOUD_HME_ACCOUNT_ID` means dynamic mode; a non-empty value remains fixed mode for compatibility and rollback.

**Tech Stack:** Python 3, requests, Flask, PostgreSQL/psycopg, existing `record_store`, unittest.

**Spec:** `docs/superpowers/specs/2026-09-15-icloud-hme-account-pool-design.md`

## Global Constraints

- Do not modify Apple Cookie, App password, or Gmail/Email Butler credentials.
- Do not rebind existing aliases to another `account_id`.
- Do not use the compatibility JSON export as the source of truth.
- A failed account snapshot must not mark that account's existing aliases `remote_missing`.
- Ordinary WebUI responses must not expose secrets.
- Keep `ICLOUD_HME_ACCOUNT_ID` as explicit fixed-account mode; blank is the dynamic mode after migration.

### Task 1: Add account-scoped pool queries

**Files:**
- Modify: `core/storage/db_legacy.py:4255-4325`
- Modify: `core/storage/email_pool.py:1-20`
- Test: `tests/test_icloud_hme.py`

**Interfaces:**
- Extend `claim_next_icloud_hide_email(account_id: str | None = None, *, account_ids: list[str] | None = None) -> dict | None`.
- Add `icloud_hide_email_pool_summary_by_account(account_ids: list[str] | None = None) -> list[dict]`, returning one row per account with `account_id`, `available`, `used`, `failed`, `disabled`, and `total`.

- [ ] **Step 1: Write failing PostgreSQL tests for scoped claim and per-account summary**

Add these methods to `ICloudHidePoolTests`:

```python
def test_claim_can_restrict_to_multiple_accounts(self):
    db.sync_icloud_hide_aliases([{"email": "a@example.com", "active": True}], "acc-a")
    db.sync_icloud_hide_aliases([{"email": "b@example.com", "active": True}], "acc-b")
    claimed = db.claim_next_icloud_hide_email(account_ids=["acc-b"])
    self.assertEqual(claimed["email"], "b@example.com")
    self.assertEqual(db.get_icloud_hide_email_by_email("a@example.com")["status"], "available")

def test_summary_is_grouped_by_account(self):
    db.sync_icloud_hide_aliases([
        {"email": "a1@example.com", "active": True},
        {"email": "a2@example.com", "active": True},
    ], "acc-a")
    db.sync_icloud_hide_aliases([{"email": "b1@example.com", "active": False}], "acc-b")
    db.claim_next_icloud_hide_email("acc-a")
    grouped = {row["account_id"]: row for row in db.icloud_hide_email_pool_summary_by_account()}
    self.assertEqual(grouped["acc-a"]["available"], 1)
    self.assertEqual(grouped["acc-a"]["used"], 1)
    self.assertEqual(grouped["acc-b"]["disabled"], 1)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `./.venv/bin/python -m unittest tests.test_icloud_hme.ICloudHidePoolTests.test_claim_can_restrict_to_multiple_accounts tests.test_icloud_hme.ICloudHidePoolTests.test_summary_is_grouped_by_account`

Expected: FAIL because the new keyword/function is not implemented.

- [ ] **Step 3: Implement the scoped claim and SQL aggregation**

In `claim_next_icloud_hide_email`, keep the existing single-account predicate and add `account_id = ANY(%s)` when `account_ids` is non-empty. Reject an empty explicit list by returning `None`, not by removing the account filter. In `icloud_hide_email_pool_summary_by_account`, group by `account_id` and `status`, normalize missing statuses to `available`, and return deterministic account ID order.

Expose the new function through `core/storage/email_pool.py`.

- [ ] **Step 4: Run the focused tests and the existing iCloud pool tests**

Run: `./.venv/bin/python -m unittest tests.test_icloud_hme.ICloudHidePoolTests -v`

Expected: PASS, including the pre-existing claim, release, full-snapshot, and registered-alias tests.

- [ ] **Step 5: Commit the storage boundary**

```bash
git add core/storage/db_legacy.py core/storage/email_pool.py tests/test_icloud_hme.py
git commit -m "feat: scope iCloud HME pool claims by account"
```

### Task 2: Implement dynamic multi-account synchronization

**Files:**
- Modify: `core/icloud_hme_client.py:150-305`
- Test: `tests/test_icloud_hme.py`

**Interfaces:**
- Add `select_accounts(account_id: str | None = None, *, api_base: str | None = None, timeout: int | None = None) -> list[dict]`.
- Change `sync_aliases(*, force: bool = False, account_id: str | None = None) -> dict` to return `account_ids`, `accounts`, `account_errors`, aggregate remote counts, and `pool`.
- Preserve `resolve_account_id()` and `list_aliases()` as fixed/single-account compatibility helpers.

- [ ] **Step 1: Add failing tests for dynamic selection and partial sync**

Add tests that stub `_request` with two active accounts and one inactive account, then verify both active accounts are requested and the inactive account is ignored. Add a second test where the first alias request raises `ICloudHMEError` and the second succeeds; assert `account_errors` contains only the failed account and `sync_icloud_hide_aliases` is called for the successful account.

Use this concrete fixture shape:

```python
accounts = [
    {"id": "acc-a", "name": "old", "status": "active"},
    {"id": "acc-b", "name": "new", "status": "active"},
    {"id": "acc-off", "name": "off", "status": "disabled"},
]
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `./.venv/bin/python -m unittest tests.test_icloud_hme.ICloudHMEClientTests.test_dynamic_syncs_all_active_accounts tests.test_icloud_hme.ICloudHMEClientTests.test_dynamic_sync_keeps_successful_account_when_another_fails`

Expected: FAIL because `select_accounts` and multi-account `sync_aliases` do not exist.

- [ ] **Step 3: Implement `select_accounts` and account-aware cache keys**

When the explicit argument is non-empty, validate it against `/api/accounts` and return one matching account. When it is empty, use the configured `ICLOUD_HME_ACCOUNT_ID` if non-empty; otherwise return all accounts whose status is `active`, sorted by `(created_at, id)`. In `sync_aliases`, fetch the account list once per non-cached sync, compute the cache key from the sorted selected IDs plus inbox mode and final forward mailbox, and keep `_LAST_ACCOUNT_ID` as the first selected ID only for legacy response compatibility.

- [ ] **Step 4: Implement per-account sync without destructive partial failure**

For every selected account, call `/api/aliases` with that account ID, run `_prepare_imap_aliases`, and call `db.sync_icloud_hide_aliases(prepared, selected, full_snapshot=True)`. Catch `ICloudHMEError` per account and append a redacted `{account_id, error_type, error}` entry to `account_errors`; do not call the DB sync function for that failed account. Aggregate `remote_count`, `remote_active`, `remote_usable`, inserted/updated/disabled counts, grouped pool summaries, and selected account metadata.

- [ ] **Step 5: Run focused client tests and preserve fixed-mode tests**

Run: `./.venv/bin/python -m unittest tests.test_icloud_hme.ICloudHMEClientTests -v`

Expected: PASS, including fixed `account_id`, cached sync, forward target compatibility, connection, and OTP tests.

- [ ] **Step 6: Commit dynamic synchronization**

```bash
git add core/icloud_hme_client.py tests/test_icloud_hme.py
git commit -m "feat: sync iCloud HME aliases across active accounts"
```

### Task 3: Make allocation global and update connection summaries

**Files:**
- Modify: `core/icloud_hme_client.py:260-305,430-500`
- Modify: `webui/routes/integrations.py:100-130`
- Modify: `config/schema.py:860-868`
- Modify: `webui/static/js/modern/config.js:995-1010`
- Modify: `webui/static/js/legacy/config.js:328-345`
- Test: `tests/test_icloud_hme.py`

**Interfaces:**
- `pick_account()` returns an `ICloudHMEAccount` from any selected active account; its `account_id` comes from the claimed pool row.
- `/api/icloud-hme/test` returns `accounts`, `account_errors`, `remote_count`, `remote_active`, grouped pool summaries, and the existing `message` field.

- [ ] **Step 1: Add failing tests for global allocation and connection aggregation**

Add a client test where `sync_aliases` returns `account_ids=["acc-a", "acc-b"]` and the DB mock returns an alias from `acc-b`; assert `pick_account()` returns that alias without passing a single account ID. Add a route-level or client-level test that a two-account connection result exposes both account IDs and grouped pool counts.

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `./.venv/bin/python -m unittest tests.test_icloud_hme.ICloudHMEClientTests.test_pick_account_uses_global_pool tests.test_icloud_hme.ICloudHMEClientTests.test_connection_reports_all_accounts`

Expected: FAIL because `pick_account` still restricts claims to one selected account and `test_connection` still assumes one remote response.

- [ ] **Step 3: Implement global claim and bounded on-demand creation fallback**

Use `db.claim_next_icloud_hide_email(account_ids=selected_ids)` in `pick_account`. After a forced multi-account sync, retry the same scoped claim. If `ICLOUD_HME_AUTO_CREATE` is enabled and no alias is available, try selected accounts once in stable order; a failure on one account is collected and the next account is attempted. Never loop indefinitely inside one registration request.

- [ ] **Step 4: Update `test_connection` and the WebUI response**

Make `test_connection` accept an optional fixed `account_id`; otherwise test the final inbox once and synchronize all selected accounts. For `sidecar` inbox mode, use the first selected account for the existing one-message probe while reporting every account's alias counts. Return the aggregate error list and do not include credentials. Change the configuration help to “固定账号 ID；留空自动发现全部 active 账号”, and update both modern/legacy tool status text to mention multi-account sync.

- [ ] **Step 5: Run the complete focused suite**

Run: `./.venv/bin/python -m unittest tests.test_icloud_hme tests.test_email_provider_gptmail tests.test_email_source_selection -v`

Expected: PASS. Existing fixed-account and provider selection behavior must remain intact.

- [ ] **Step 6: Commit global allocation and WebUI contract**

```bash
git add core/icloud_hme_client.py webui/routes/integrations.py config/schema.py webui/static/js/modern/config.js webui/static/js/legacy/config.js tests/test_icloud_hme.py
git commit -m "feat: allocate iCloud HME aliases globally"
```

### Task 4: Update turb documentation and verify storage/config contracts

**Files:**
- Modify: `.env.example:252-271`
- Modify: `README.md:294-330,680-691`
- Test: `tests/test_config_defaults.py`, `tests/test_config_ui.py`

- [ ] **Step 1: Add/adjust failing config contract assertions**

Assert that the existing `ICLOUD_HME_ACCOUNT_ID` field help contains “留空自动发现全部 active 账号” and that the iCloud tool text refers to synchronizing multiple accounts. Do not add secrets or account IDs to fixtures.

- [ ] **Step 2: Update examples and operational documentation**

Document blank `ICLOUD_HME_ACCOUNT_ID` as dynamic mode, non-empty as fixed mode, one-time migration by clearing the old ID, the shared Gmail/Email Butler inbox assumption, and the fact that the sidecar worker is the recommended continuous creator.

- [ ] **Step 3: Run config and iCloud regression tests**

Run: `./.venv/bin/python -m unittest tests.test_config_defaults tests.test_config_ui tests.test_icloud_hme -v`

Expected: PASS. Report any unrelated `.env`-derived baseline failures separately; do not edit production `.env` to make tests pass.

- [ ] **Step 4: Commit documentation and contract updates**

```bash
git add .env.example README.md tests/test_config_defaults.py tests/test_config_ui.py
git commit -m "docs: document iCloud HME dynamic account mode"
```

### Task 5: End-to-end turb verification

**Files:**
- No new production files.
- Test: `tests/test_icloud_hme.py`, `tests/test_dashboard_api.py`

- [ ] **Step 1: Run the focused integration set**

Run: `./.venv/bin/python -m unittest tests.test_icloud_hme tests.test_dashboard_api tests.test_email_source_selection -v`

Expected: PASS with no secret values in output.

- [ ] **Step 2: Verify the diff and repository scope**

Run: `git diff --check HEAD~4..HEAD` and `git status --short`. Confirm only the planned turb files changed and the pre-existing sidecar worktree remains untouched.

- [ ] **Step 3: Record the turb implementation boundary**

Report the commit SHAs, focused test counts, and explicitly state that no live alias was created during turb-only tests. Keep production migration (clearing `ICLOUD_HME_ACCOUNT_ID`) as a separate operator action after sidecar worker verification.
