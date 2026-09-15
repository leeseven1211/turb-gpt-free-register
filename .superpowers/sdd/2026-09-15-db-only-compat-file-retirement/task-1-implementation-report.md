# Task 1 Implementation Report

- Commit: `5d2b90d45734a9446198b42d7a02286b82d9b96c`
- Scope: removed account, registration-job, Outlook, and iCloud compatibility export registration and scheduling. PostgreSQL row mutations and operation-task synchronization remain.
- Tests: `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m pytest tests/test_db_only_compat_files.py tests/test_icloud_hme.py tests/test_job_progress.py tests/test_account_tasks.py tests/test_postgres_store.py -q` -> 82 passed.
- Added `tests/test_db_only_compat_files.py` to assert account/job/pool mutations remain queryable without retired projection paths.
- Updated test fixtures that previously redirected retired export paths.
- Risk/follow-up: the old `_render_static_viewer` implementation remains unreachable dead code and still references retired path names; remove it in the documentation/reference cleanup stage. The migration helper is still handled by the explicit-import/migration stages.
- No root material files were deleted.
