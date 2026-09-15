# Database-Only Compatibility File Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the seven root JSON/TXT compatibility files from normal runtime while preserving explicit external Outlook-file import directly into PostgreSQL.

**Architecture:** PostgreSQL row tables remain the only runtime source and sink. Account/job/Outlook/iCloud compatibility exporters are removed, while the generic/domain/Codex exporters outside this scope remain. Outlook file import becomes an explicit transient parser that requires a caller-supplied path and writes only `email_pool_outlook`.

**Tech Stack:** Python 3.12, Flask, PostgreSQL/psycopg, pytest, existing `record_store`/`admin_repository` layers.

**Spec:** `docs/superpowers/specs/2026-09-15-db-only-compat-file-retirement-design.md`

## Global Constraints

- PostgreSQL is mandatory; no runtime fallback to root JSON/TXT files.
- `email_pool_outlook` is the existing table; do not create a second Outlook pool table.
- Explicit file import reads the caller-supplied source in memory and writes rows to PostgreSQL only; it never rewrites or copies the source.
- Registration must never auto-import from a root file.
- Keep generic/domain/Codex compatibility outputs outside this scope.
- Do not expose passwords, refresh tokens, access tokens, OTPs, or full emails in ordinary list responses, test output, or reports.
- Preserve unrelated worktree changes and never use recursive deletion commands.
- Before deleting the seven material files, stop the local WebUI and verify exact targets; deletion is a separate irreversible gate after code verification.

---

### Task 1: Remove Account, Job, Outlook, and iCloud File Exports

**Files:**
- Modify: `core/storage/db_legacy.py:39-47,266-289,630-702,3909-4008,4108-4122`
- Inspect: `core/compat_export.py` to preserve the remaining generic/domain/Codex exporter contract
- Test: `tests/test_db_storage_backend.py`, `tests/test_icloud_hme.py`, `tests/test_job_progress.py`, `tests/test_account_tasks.py`, `tests/test_postgres_store.py`
- Create: `tests/test_db_only_compat_files.py`

**Interfaces:**
- Consumes: `record_store.ACCOUNTS`, `record_store.JOBS`, `record_store.OUTLOOK_POOL`, `record_store.ICLOUD_HIDE_POOL`.
- Produces: row mutations that never schedule or write the seven retired files; remaining generic/domain/Codex exporters continue to work.

- [ ] **Step 1: Add failing tests for the no-export contract**

Create `tests/test_db_only_compat_files.py` using the existing
`tests.support_pg.PostgresTestCase` schema fixture and a temporary project
root. Add three concrete tests: insert/patch an account and assert the account
JSON/TXT/token/viewer paths are absent; create/update a registration job and
assert the job JSON path is absent; insert/update Outlook and iCloud pool rows
and assert both pool JSON paths are absent.

Run: `.venv/bin/python -m pytest tests/test_db_only_compat_files.py -q`

Expected: FAIL because current mutation paths still schedule compatibility exporters.

- [ ] **Step 2: Remove the seven export constants and exporter registrations**

Delete the account/job/Outlook/iCloud root-path constants and their `_export_*` functions from `core/storage/db_legacy.py`. Keep `_write_json` and registrations required by generic API, domain email, and Codex outputs. Remove `storage_paths()` entries for retired files and retire `refresh_static_viewer()` rather than rebuilding `accounts_viewer.html`.

- [ ] **Step 3: Remove retired scheduling calls without changing row writes**

Keep every `record_store` insert/update/delete and transaction intact. Remove only `compat_export.schedule("accounts")`, `schedule("jobs")`, `schedule("outlook")`, and `schedule("icloud_hide_emails")` calls. Ensure account/job/iCloud state remains queryable through row tables.

- [ ] **Step 4: Update affected tests and compatibility fixtures**

Remove path monkeypatches that only test retired projections. Replace them with assertions against the test schema rows. Preserve tests for generic/domain/Codex exports and the generic `compat_export` debounce mechanism.

- [ ] **Step 5: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_db_only_compat_files.py tests/test_icloud_hme.py tests/test_job_progress.py tests/test_account_tasks.py tests/test_postgres_store.py -q`

Expected: PASS with no retired file creation.

- [ ] **Step 6: Commit**

```bash
git add core/storage/db_legacy.py core/compat_export.py tests/test_db_only_compat_files.py tests/test_db_storage_backend.py tests/test_icloud_hme.py tests/test_job_progress.py tests/test_account_tasks.py tests/test_postgres_store.py
git commit -m "refactor: stop exporting account and pool compatibility files"
```

### Task 2: Make Outlook File Import Explicit and Database-Only

**Files:**
- Modify: `core/outlook_client.py:256-272,341-352`
- Modify: `config/email.py:36`, `config/__init__.py`, `config/schema.py:1389`
- Create: `tools/import_outlook_pool.py`
- Test: `tests/test_outlook_client.py`, `tests/test_config_defaults.py`, `tests/test_db_only_compat_files.py`

**Interfaces:**
- Consumes: a caller-supplied text path containing `----` or `====` Outlook rows.
- Produces: `import_outlook_from_file(path: str | Path) -> tuple[int, int]` and CLI `tools/import_outlook_pool.py --file PATH`, both writing only through `db.import_outlook_accounts()`.

- [ ] **Step 1: Add failing tests for explicit import and no automatic import**

Add tests that patch `core.outlook_client.import_outlook_from_file` and assert `pick_account()` does not call it. Add a temporary external input file test that asserts `import_outlook_from_file(path)` inserts rows into the test PostgreSQL schema and leaves the source bytes unchanged.

Run: `.venv/bin/python -m pytest tests/test_outlook_client.py -q`

Expected: FAIL because `pick_account()` currently imports the configured root file and the helper has a default path.

- [ ] **Step 2: Change the helper contract**

Make `path` required, resolve only that path, parse it in memory, and pass records to `import_outlook_accounts()`. Do not call any exporter or write to the source. Keep `import_outlook_from_text()` for WebUI/API input.

- [ ] **Step 3: Remove automatic file import from registration**

Change `pick_account()` to call `claim_next_outlook()` directly. When no row is available, report that Outlook material must be imported through WebUI/API or the explicit import command. Do not mention a project-root filename.

- [ ] **Step 4: Add the explicit CLI wrapper**

Create `tools/import_outlook_pool.py` with:

```text
usage: import_outlook_pool.py --file PATH [--verbose]
```

The command must call `postgres_store.require_ready()`, invoke `import_outlook_from_file(PATH)`, print only inserted/skipped counts, and never copy or rewrite `PATH`.

- [ ] **Step 5: Remove the file-path configuration**

Remove `OUTLOOK_ACCOUNTS_FILE` from `config/email.py`, `config/__init__.py`, and the editable schema. Update comments and tests so WebUI/API import is the primary resource entry point.

- [ ] **Step 6: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_outlook_client.py tests/test_config_defaults.py tests/test_db_only_compat_files.py -q`

Expected: PASS; direct file import works only when explicitly requested.

- [ ] **Step 7: Commit**

```bash
git add core/outlook_client.py config/email.py config/__init__.py config/schema.py tools/import_outlook_pool.py tests/test_outlook_client.py tests/test_config_defaults.py tests/test_db_only_compat_files.py
git commit -m "refactor: make Outlook file import an explicit DB import"
```

### Task 3: Remove File Fallbacks from Migration and Manual Token Tools

**Files:**
- Modify: `tools/migrate_collections_to_tables.py:40-83,86-113`
- Modify: `tools/test_chatgpt_curl_cffi.py:10-18,73-90` and argument parsing
- Modify: `tools/test_codex_oauth.py:10-18`
- Modify: `tests/test_collection_migration.py`, `tests/test_postgres_store.py`
- Create: `tests/test_db_only_tools.py`

**Interfaces:**
- Consumes: normalized PostgreSQL rows and explicit account selector (`--account-id` or `--email`) for manual token testing.
- Produces: clear database-only migration verification and a manual token test that never reads `注册成功的token.txt`.

- [ ] **Step 1: Add failing migration and token-selector tests**

Test that migration source loading returns a clear missing-collection error instead of reading a root JSON file. Test that the token tool can resolve an account by ID/email from the database and rejects `--token-file` as removed.

Run: `.venv/bin/python -m pytest tests/test_collection_migration.py tests/test_postgres_store.py -q`

Expected: FAIL against the current file fallback and token-file interface.

- [ ] **Step 2: Make migration verification database-only**

Remove `load_source()` file fallback for the seven collections. Keep collection-to-row verification against `app_collections` and normalized tables. When a required collection is missing, raise/report the collection name and stop with nonzero status; never treat a stale root snapshot as empty or current.

- [ ] **Step 3: Resolve manual ChatGPT tokens from PostgreSQL**

Add mutually exclusive `--token`, `--account-id`, and `--email` selectors. For database selectors, call the existing DB account lookup and obtain the access token only inside the manual test process. Remove `--token-file` and all root token-file reads. Keep output redacted.

- [ ] **Step 4: Update Codex tool documentation**

Change the prerequisite text to say the mailbox credential is in the database email pool. The command already submits a database-backed operation and must not gain a file read.

- [ ] **Step 5: Run focused tests and CLI help checks**

Run:

```bash
.venv/bin/python -m pytest tests/test_collection_migration.py tests/test_postgres_store.py tests/test_db_only_tools.py -q
.venv/bin/python tools/import_outlook_pool.py --help
.venv/bin/python tools/test_chatgpt_curl_cffi.py --help
```

Expected: tests pass; help output contains explicit import/account selectors and no `--token-file`.

- [ ] **Step 6: Commit**

```bash
git add tools/migrate_collections_to_tables.py tools/test_chatgpt_curl_cffi.py tools/test_codex_oauth.py tests/test_collection_migration.py tests/test_postgres_store.py tests/test_db_only_tools.py
git commit -m "refactor: remove legacy file fallbacks from operational tools"
```

### Task 4: Documentation and Reference Cleanup

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/storage-architecture.md`, `docs/current-architecture.md`, `docs/core-registration-flow.md`, `docs/compatibility-inventory.md`
- Modify: `用于注册的邮箱.txt.example` to state that it is an external import-format example, not a runtime pool
- Test: `tests/test_release_checks.py` or a new reference-audit test

**Interfaces:**
- Consumes: final DB-only runtime contracts from Tasks 1-3.
- Produces: documentation that no longer instructs operators to treat retired root exports as current data.

- [ ] **Step 1: Add a reference-audit assertion**

Add a test or deterministic audit command that searches runtime Python modules for the seven root filenames and permits only the explicit import helper, migration history comments, and tests that intentionally cover removal.

- [ ] **Step 2: Update operational documentation**

Document `email_pool_outlook` and the WebUI/API import route as the supported resource path. Describe `tools/import_outlook_pool.py --file PATH` as transient input only. Remove backup instructions that imply the seven files are required runtime backups; point backups at PostgreSQL instead.

- [ ] **Step 3: Update examples and comments**

Keep the `.example` file only as an external import-format example, clearly state that it is not a runtime pool, and remove stale comments claiming registration reads root JSON/TXT state.

- [ ] **Step 4: Run reference and documentation checks**

Run: `.venv/bin/python -m pytest tests/test_release_checks.py -q` and the reference-audit test from Step 1.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md docs/storage-architecture.md docs/current-architecture.md docs/core-registration-flow.md docs/compatibility-inventory.md '用于注册的邮箱.txt.example' tests/test_release_checks.py
git commit -m "docs: document database-only runtime storage"
```

### Task 5: Integrated Verification and Deletion Gate

**Files:**
- No production source changes unless verification exposes a concrete regression.
- Inspect: all seven retired root files, `run/webui.pid`, WebUI logs, PostgreSQL counts.

- [ ] **Step 1: Run the focused regression suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_db_only_compat_files.py tests/test_outlook_client.py tests/test_collection_migration.py tests/test_postgres_store.py tests/test_icloud_hme.py tests/test_job_progress.py tests/test_account_tasks.py tests/test_release_checks.py -q
```

- [ ] **Step 2: Run the complete test suite**

Run: `.venv/bin/python -m pytest -q`

Expected: no new failures. Existing unrelated failures must be recorded with their exact test names and output.

- [ ] **Step 3: Audit runtime references**

Run `rg` over `core`, `webui`, `main.py`, `web.py`, and `tools` to confirm no normal runtime code reads or writes the seven retired paths. Verify the explicit import helper and CLI are the only permitted file-input references.

- [ ] **Step 4: Verify local WebUI behavior**

Restart the local WebUI on port 8000 using the existing project procedure. Verify `/login` returns HTTP 200, the process uses the DB-only worktree code, and a read-only account/job/email-pool API smoke check succeeds.

- [ ] **Step 5: Verify no regeneration**

Run `.venv/bin/python -m pytest tests/test_db_only_compat_files.py -q` and
confirm the seven root files are not recreated in the implementation worktree.

- [ ] **Step 6: Stop before irreversible deletion and request confirmation**

Report the test totals, DB counts, runtime health, exact seven deletion targets, and any remaining external consumer. Do not delete files in this task until the deletion gate is explicitly confirmed after verification.
