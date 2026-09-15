# Database-Only Runtime and Compatibility File Retirement

## Goal

Make the seven legacy root exports non-authoritative and non-runtime: normal
account, registration-job, Outlook pool, and iCloud Hide My Email workflows
read and write PostgreSQL row tables only. Preserve explicit Outlook file
import as a transient operator input: parse a caller-supplied file in memory,
insert/update `email_pool_outlook`, and never copy, rewrite, or use that file
as a pool during registration.

## Current Evidence

- `email_pool_outlook` already exists and is the normalized table for Outlook
  resources. Credentials are stored in its `data` JSONB payload alongside
  promoted identity/status fields; no new table is required.
- Current row counts are 965 `registered_accounts`, 1310
  `registration_jobs`, 0 `email_pool_outlook`, and 873
  `email_pool_icloud_hide`.
- The seven root files are compatibility projections. The current root
  snapshots are behind the row tables, so they cannot be used as a recovery
  or list source.
- The normal WebUI list/operation paths already use `record_store` and
  `admin_repository`. The remaining runtime file read is the automatic
  `pick_account()` call to `import_outlook_from_file()`.
- The migration tool still has a file fallback when an `app_collections`
  collection is absent. This fallback is removed from the normal migration
  path; any legacy import must be explicit and one-time.

## Scope

### Retired root files

1. `注册任务.json`
2. `注册成功的邮箱.json`
3. `注册成功的邮箱.txt`
4. `注册成功的token.txt`
5. `用于注册的邮箱.json`
6. `用于注册的邮箱.txt`
7. `用于注册的iCloud隐藏邮箱.json`

`accounts_viewer.html` is retired with the account export because it would
otherwise remain a misleading snapshot. `codex_accounts/`, batch `accounts/`,
logs, and other provider compatibility outputs are outside this change.

### Retained transient import

`import_outlook_from_file(path)` remains an explicit import helper, but:

- `path` is required; it has no project-root default.
- The helper reads and parses the supplied file in memory.
- It calls `import_outlook_accounts()` and returns insert/skip counts.
- It does not write a projection, rewrite the input, or make the input path a
  runtime configuration value.
- Registration never calls it automatically. A file import is an operator
  action before registration, equivalent to the existing WebUI text import.

Add a small CLI wrapper, `tools/import_outlook_pool.py --file /path/to/input.txt`,
for this explicit operation. The input file remains
outside the project data directory and is not copied into it.

## Data Flow

```text
WebUI paste/API import                 explicit external file import
        |                                        |
        +------------ parse/validate ------------+
                             |
                 db.import_outlook_accounts()
                             |
                    email_pool_outlook
                             |
                  claim_next_outlook()
```

The registration path stops at `claim_next_outlook()` and never inspects a
root file. Accounts and jobs are read through `record_store`/repositories;
iCloud aliases are read and claimed through `email_pool_icloud_hide`.

## Code Changes

### Storage and export layer

- Remove the seven file path constants and their account/job/Outlook/iCloud
  export registrations from `core/storage/db_legacy.py`.
- Keep the generic/domain/Codex compatibility exporters that are outside the
  scope of this change.
- Remove the seven-file `compat_export.schedule()` calls from row mutation
  paths. No account/job/pool mutation may recreate the retired files.
- Remove or narrow `storage_paths()` and `refresh_static_viewer()` so they do
  not advertise or rebuild retired projections.
- Keep PostgreSQL `app_collections` only as a temporary database rollback
  mirror; normal reads use normalized row tables. Do not use root files as a
  fallback.

### Outlook runtime

- Delete the automatic `import_outlook_from_file()` call from
  `core/outlook_client.py::pick_account()`.
- Keep `import_outlook_from_text()` for UI/API input.
- Change `import_outlook_from_file(path)` to require an explicit path and use
  it only as a transient import operation.
- Remove `OUTLOOK_ACCOUNTS_FILE` as a runtime configuration setting and update
  error messages to direct operators to the WebUI/API or explicit import
  command.

### Scripts and migration tools

- Change `tools/test_chatgpt_curl_cffi.py` from `--token-file` to a database
  selector such as `--account-id` or `--email`; retain direct `--token` for
  deliberate one-off testing.
- Update `tools/test_codex_oauth.py` documentation to describe the database
  mailbox pool rather than a root JSON file.
- Make `tools/migrate_collections_to_tables.py` database-only after the
  already-completed migration. If a required collection is absent, fail
  clearly instead of silently reading a root snapshot.
- Preserve explicit, separately-invoked legacy import capability only where
  an operator supplies the source path; it must not be part of startup,
  registration, or recovery.

### Documentation and tests

- Update README, CLAUDE/operational documentation, and config comments to
  describe PostgreSQL as the only source and transient file import as an
  explicit input.
- Replace tests that patch retired export paths with database assertions.
- Add tests proving:
  - account/job/Outlook/iCloud mutations do not create the seven files;
  - `pick_account()` does not read a root file;
  - explicit file import writes rows and does not rewrite the input;
  - the token test script resolves a token from PostgreSQL;
  - migration fails clearly when a required database collection/table is
    absent instead of falling back to a stale file.

## Error Handling and Rollout

- PostgreSQL remains mandatory; database connection failure still terminates
  startup rather than falling back to files.
- An empty Outlook table produces the existing "no available Outlook
  material" error and points to WebUI/API or explicit import.
- Before deleting files, run a read-only row-count/identity verification and
  confirm the database backup. Stop the WebUI, delete the seven files one by
  one, restart, and verify that ordinary account/job/pool mutations do not
  recreate them.
- Keep the old `app_collections` rows until focused tests and a live local
  restart pass; removing those duplicate database mirrors is a separate
  cleanup decision.

## Acceptance Criteria

- All normal runtime reads and writes for the seven domains go through
  PostgreSQL row tables.
- Explicit external file import still works and writes only to PostgreSQL.
- No root compatibility file is created or updated by WebUI, CLI, startup
  recovery, account operations, registration, or iCloud sync.
- The full focused regression suite passes, followed by the project test
  suite and a local WebUI restart/health check.
