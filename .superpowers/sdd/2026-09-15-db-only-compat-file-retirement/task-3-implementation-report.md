# Task 3 implementation report

## Changes

- `tools/migrate_collections_to_tables.py` now reads migration collections only from PostgreSQL `app_collections`. A missing collection or non-array payload raises a named error; the CLI exits nonzero before treating any root snapshot as input.
- `tools/test_chatgpt_curl_cffi.py` removed `--token-file` and token-file parsing. The mutually exclusive selectors are `--token`, `--account-id`, and `--email`; database selectors resolve an account through `core.db` and read its access token only in the process.
- `tools/test_codex_oauth.py` now documents the PostgreSQL email pool as the mailbox credential source.
- Added focused coverage in `tests/test_db_only_tools.py` and a missing-collection regression in `tests/test_collection_migration.py`.

## Verification

- `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m pytest tests/test_collection_migration.py tests/test_postgres_store.py tests/test_db_only_tools.py -q`: `9 passed`.
- `tools/test_chatgpt_curl_cffi.py --help`: shows the three mutually exclusive selectors and no `--token-file`.
- Passing `--token-file` exits with status `2` during argument parsing.
- `compileall` passed for the changed tools and test module.
- `git diff --check` passed.

No material data files were deleted or written.
