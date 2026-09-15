# Task 4 implementation report

## Scope

- Updated operator and architecture documentation to identify PostgreSQL as the runtime source of truth.
- Documented WebUI/API and `tools/import_outlook_pool.py --file PATH` as explicit Outlook import paths; the input file is parsed transiently and is not persisted.
- Removed the retired static account viewer implementation and stale root-snapshot comments.
- Added a release audit that rejects retired root JSON/TXT references in runtime code while allowing the historical migration mapping and the existing `accounts/` batch archive contract.

## Verification

- `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m pytest tests/test_release_checks.py -q`: 7 passed.
- `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m pytest tests/test_db_only_compat_files.py tests/test_outlook_client.py tests/test_collection_migration.py tests/test_db_only_tools.py -q`: 16 passed.
- `git diff --check`: passed.
- Runtime reference audit: only `tools/migrate_collections_to_tables.py` retains historical collection filenames; batch archive filenames remain under `accounts/` by design.
- No material root files were deleted or modified.
