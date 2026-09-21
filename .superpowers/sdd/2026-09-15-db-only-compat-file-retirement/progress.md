# SDD ledger — plan: docs/superpowers/plans/2026-09-15-db-only-compat-file-retirement.md

## Setup

- Worktree: `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.worktrees/db-only-storage`
- Base commit: `c6f7ad9`
- Spec: `docs/superpowers/specs/2026-09-15-db-only-compat-file-retirement-design.md`
- Plan: `docs/superpowers/plans/2026-09-15-db-only-compat-file-retirement.md`

## Plan scan

| Task | Own consistency | Shared interface / file | Finding | Ruling |
|---|---|---|---|---|
| Task 1 | Consistent: removes exporters and adds no-export tests | `tests/test_db_only_compat_files.py` consumed by Tasks 2 and 5 | Task 2 adds Outlook assertions to the same test file | Keep shared test file; Task 2 extends it after Task 1, and Task 5 runs it only after both commits. |
| Task 2 | Consistent: explicit path import and CLI produce DB rows | `core/outlook_client.py` only in Task 2 | No cross-task conflict | Proceed. |
| Task 3 | Consistent: tools stop reading root snapshots | `tests/test_postgres_store.py` also touched by Task 1 | Task 1 replaces path fallback tests; Task 3 updates migration expectations | Task 1 lands first; Task 3 consumes the updated DB-only test contract. |
| Task 4 | Consistent: docs follow final interfaces | Runtime path names from Tasks 1-3 | Must run after implementation tasks | Run after Tasks 1-3. |
| Task 5 | Consistent: verification and deletion gate only | All previous outputs | Deletion is explicitly gated and not performed by the verification task | Stop before deletion and report exact targets. |

## Rulings

- Ruling: explicit external Outlook file import remains supported — because the user requested it — but it must require a supplied path and never use the project root as a default.
- Ruling: the existing `email_pool_outlook` table is authoritative — because it already exists and current runtime uses it — so no second mailbox table or schema fork will be introduced.
- Ruling: `app_collections` remains a temporary database rollback mirror — because it is database-resident and the migration has already populated normalized tables — while normal runtime reads normalized tables.

## Verification baseline

- Focused baseline: `25 passed in 18.45s` for `tests/test_postgres_store.py`, `tests/test_icloud_hme.py`, `tests/test_outlook_client.py`, `tests/test_collection_migration.py`, and `tests/test_release_checks.py`.
- Full baseline: `1130 passed, 45 failed, 790 subtests passed in 971.35s`.
- Existing failures are outside this change: five `tests/test_codex_token_refresh_durable.py` failures around public-schema/fixture behavior, plus configuration-schema failures caused by the loaded local `.env` values differing from schema defaults. No production source changes had been made when this baseline was collected.

## Task 1: complete

- Commit: `c044ae3` (`refactor: stop exporting account and pool compatibility files`).
- Verification: focused suite reported `82 passed`.
- Review ruling: exporter registrations/scheduling and retired storage-path entries are removed while PostgreSQL row writes remain. `_render_static_viewer` is unreachable dead code and still references retired symbols; defer its removal to Task 4 reference cleanup, where it is explicitly in scope.
- Review tool note: the configured review-agent models returned HTTP 404 on this host; controller performed the required diff/report/risk checks directly.

## Task 2: complete

- Commit: `56e99d9` (`refactor: make Outlook file import an explicit DB import`).
- Verification: implementer reported `41 passed, 3 subtests passed`; CLI help and `git diff --check` passed.
- Review ruling: explicit path import parses transient input and writes through `import_outlook_accounts`; `pick_account` no longer imports a root file; the config field is removed. The module's historical root-file wording and dead viewer references remain documentation/reference-cleanup work for Task 4.
- Review tool note: review-agent model dispatch remained unavailable (HTTP 404); controller performed a read-only diff and targeted reference review.

## Task 3: complete

- Commits: `08ee9e3` (`refactor: remove legacy file fallbacks from operational tools`) and `b465b77` (`fix: repair database token test parser`).
- Verification: implementer reported `10 passed`; CLI help exposes `--token`, `--account-id`, `--email`, and optional `--chatgpt-account-id`, while `--token-file` is rejected. A controller help check also completed successfully.
- Review ruling: migration source loading now fails explicitly when PostgreSQL collections are absent; token tests resolve access tokens only through DB account selectors. The parser regression found during review was fixed before proceeding.

## Task 4: complete

- Commit: `0d50036` (`docs: document database-only runtime storage`).
- Verification: release checks `7 passed`; related DB-only regression checks `16 passed`; `git diff --check` passed.
- Review ruling: removed the static viewer implementation, corrected operator/architecture docs, kept `accounts/` batch archives as the spec-defined out-of-scope artifact, and added a runtime reference audit permitting only the migration mapping and batch archive contract.

## Task 5: verification complete; deletion gate pending

- Focused regression: `96 passed in 61.01s`.
- Post-doc targeted regression: `23 passed in 5.76s`.
- Full suite: `1145 passed, 44 failed, 791 subtests passed in 305.57s`. The failures remain the baseline categories: five `tests/test_codex_token_refresh_durable.py` cases and configuration-schema subfailures caused by local `.env` overrides; no failure pointed at this change's focused surface.
- Runtime reference audit: no retired root-file references in normal runtime modules except the intentional `accounts/` batch archive filenames in `core/account_export.py`; migration collection names are historical DB mappings and were excluded by the audit contract.
- Live health: existing local WebUI PID `82555` on port 8000 returned `/login` HTTP 200. Read-only PostgreSQL counts were `registered_accounts=965`, `registration_jobs=1310`, `email_pool_outlook=0`, `email_pool_icloud_hide=873`.
- Implementation worktree check: all seven retired root files are absent and were not recreated. No production/runtime data files were deleted or modified.
- Stop reason: deleting the seven files is irreversible maintenance. Await explicit confirmation after reporting the exact targets; do not remove them as part of code verification.
