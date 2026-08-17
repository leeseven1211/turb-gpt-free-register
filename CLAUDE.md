# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ChatGPT / OpenAI account auto-registration and Codex OAuth authorization tool. Two parallel entry points over the same `core/` layer: CLI (`main.py`) and a local Flask WebUI (`web.py`, recommended for daily use). Code, comments, log messages and UI are Chinese; keep new code consistent with that.

`AGENTS.md` holds project memory written for a previous agent (local startup history, deployment state, in-flight local changes). Read it when the task touches deployment, PostgreSQL, or unfinished local work — it is more current than this file on those points.

## Commands

```bash
# Setup (macOS: if cryptography fails to compile against openssl@1.1, install the wheel first)
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: 'cryptography>=41,<50'
.venv/bin/python -m pip install -r requirements.txt

# Tests (stdlib unittest, no pytest; ~270 tests, ~10s)
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'   # NOTE: `-t .` breaks discovery (tests/ has no __init__.py)
.venv/bin/python -m unittest tests.test_config_defaults          # single module
.venv/bin/python -m unittest tests.test_dashboard_api.DashboardApiTests.test_jobs_date_range_filter  # single test

# WebUI — prefer PORT=8000 locally; macOS Control Center may hold 5000
PORT=8000 ./webui.sh start | stop | restart | status | logs
.venv/bin/python web.py --host 127.0.0.1 --port 8000 --auth-code '<code>'   # foreground, for debugging

# CLI
.venv/bin/python main.py -n 5 --workers 3 --continue-on-fail --verbose

# Shared PostgreSQL (not managed by this repo)
/Users/lihongwei/code/personal/shared-services/postgres/postgres.sh status | start | stop
```

Node 18+ is required at runtime: `core/sentinel_runner.py` shells out to `node sentinel/sentinel-runner.js` for the protocol driver's PoW challenges.

## Architecture

### Layers

`config/` (declarative defaults) → `core/` (drivers + services) → `webui/app.py` (Flask API) and `main.py` (CLI). `core/` never imports from `webui/`.

### Driver dispatch

Both major flows are strategy-dispatched on a config string; adding a driver means adding a branch plus a `core/<name>_registration.py` / `core/<name>_codex_oauth.py` module:

- `main.run_registration()` (`main.py:157`) switches on `config.roxybrowser.REGISTRATION_DRIVER`: `protocol` (curl_cffi + Sentinel PoW), `roxy` (RoxyBrowser + Selenium), `cloak` (CloakBrowser + Playwright via `core/cloakbrowser_driver.py`, a Playwright→Selenium-style shim), `browser_use`, `skyvern`.
- `core.codex_oauth.run_codex_oauth()` (`core/codex_oauth.py:1297`) switches on `config.codex.CODEX_OAUTH_DRIVER`, which also accepts `same_as_registration`.

All drivers take the same `(email, name, birthday, proxy, otp_code, batch_dir)` signature and report progress through `core.registration_service.report_job_progress()`, which writes into the job's stage table (`db.JOB_PROGRESS_STAGES`).

### Email sources

`core/email_provider.py` is the only place that knows about the nine sources (`outlook`, `generic_api`, `cloudflare_domain`, `cloudflare`, `email_butler`, `gptmail`, `mailnest`, `cloudmail`, `icloud_hide`). It exposes `acquire_email` / `wait_for_otp` / `release_email` / `release_email_if_unconsumed` and dispatches to a per-source client module. WebUI jobs always pass an explicit `source`; source-less CLI calls fall back to trying `EMAIL_SOURCE` in order.

Lease semantics matter: a successful registration permanently consumes the mailbox, and only failures that provably created no account release it back — otherwise the same address gets registered twice.

### Configuration

Three-part system; a new user-editable knob touches all of them:

1. `config/<module>.py` holds the default as a module-level constant, then calls `apply_env_overrides(globals(), {...})` (`config/env_loader.py:242`) so `.env` / environment wins. Blank env values fall back to the source default, except for keys in `EXPLICIT_EMPTY_LIST_ENV_KEYS` (`PROXY_POOL`).
2. `webui/config_editor.py` `EDITABLE_FIELDS` is an explicit whitelist (key, file, type, group, label, help). Protocol-level constants — client_id, scope, Sentinel version — are deliberately excluded. Saving writes to `.env`, never to `config/*.py`.
3. `.env.example` and the README table document it; `tests/test_config_defaults.py` asserts the field is WebUI-editable and env-overridable.

Secrets are declared in `SECRET_ENV_KEYS` (`config/env_loader.py`) and live only in `.env`.

`config.reload_all()` re-imports every submodule for WebUI hot reload. Caveat: values imported as `from config import X` are bound at import time and go stale — read through the submodule (`from config import email as _email_cfg; _email_cfg.EMAIL_SOURCE`) in code that must see reloaded values. Most of `core/` imports config lazily inside functions for this reason.

### Storage

PostgreSQL is the primary store; the root-level JSON/TXT files are compatibility exports, still written on every mutation for CLI, CPA and manual export.

- `core/postgres_store.py` — generic JSONB `app_collections` table keyed by the legacy filename (`"accounts.json"` → one row). `db._read_json` / `db._write_json` prefer PostgreSQL and refresh the file; a missing row bootstraps from the existing file.
- `core/db.py` — the business data layer (accounts, mailbox pools, jobs, Codex credentials, progress stages) on top of that, plus all compatibility-file and `accounts_viewer.html` generation.
- `core/account_task_store.py` — account-operation tasks get real relational tables instead: `account_action_batches` / `account_action_tasks` / `account_action_events` (schema overridable via `ACCOUNT_TASK_DB_SCHEMA`). This module redacts on write: passwords, access tokens, OTPs, mail bodies, JWTs and credentialed proxy URLs must never be persisted here.

There is no SQLite anywhere in the runtime; `data/` is a legacy migration leftover.

`postgres_store.database_url()` returns `""` whenever `unittest` is in `sys.modules` unless `TURB_ALLOW_DATABASE_IN_TESTS=1`, so tests never touch the real database by accident. DB-backed tests (`test_account_tasks.py`) opt in explicitly, patch `database_url`, and create a throwaway schema.

### Job lifecycle and recovery

`core/registration_service.py` runs jobs on a rebuildable `ThreadPoolExecutor` (1–16 workers), with per-job stop events (`StopRequested`), per-job log files under `注册日志/`, and thread-local job context used by `report_job_progress`.

Every process-scoped resource — browser profiles, proxy leases, in-flight jobs — is reconciled at startup in `web.py`, which calls `db.recover_interrupted_registration_jobs()`, `account_task_store.recover_interrupted()` and `cleanup_orphaned_profiles()`; `create_app` adds `recover_interrupted_plan_checks/extract_links/live_checks`. When adding a new long-running task type, add its recovery pass here — otherwise a restart leaves rows stuck in `running`.

Proxies are leased per job by `core/proxy_provider.py` (`acquire_registration_proxy` / `release_proxy`), which tracks active and recently-used endpoints and masks credentials before anything reaches logs or the API.

Background loops started by the WebUI: `deactivation_mail_service.start_periodic_scanner()`, `token_refresh_service.start_periodic_refresher()`, `sms_provider.start_cancel_worker()`.

### WebUI

`webui/app.py` is a single 3.3k-line `create_app()` factory with all routes nested inside it (no blueprints); `webui/auth.py` gates everything except `/login` on an auth code (session cookie, or `X-Auth-Code` / `Authorization: Bearer` headers). `web.py` holds a per-port file lock so two instances cannot share a port, and runs with `debug=False` so the reloader does not duplicate thread pools and timers.

Two single-page templates — `index.html` (modern, default) and `index_legacy.html` — selected by `?ui=modern|legacy` and a `ui_mode` cookie. Both carry large inline JS blocks, and `tests/test_dashboard_api.py` asserts on that rendered JS by substring; editing polling or refresh logic in a template will break those tests until the assertions are updated.

## Constraints

- Never run `rm -r` / `rm -rf`. Delete files individually after confirming the target.
- The repo root holds live runtime data under Chinese filenames (`注册成功的邮箱.json`, `用于注册的邮箱.txt`, `注册任务.json`, `codex_accounts/`, `accounts/`, `注册日志/`, `.env`, `logs/`, `run/`). All are gitignored real credentials — never commit, overwrite, or clean them up.
- PostgreSQL is a shared cross-project service at `/Users/lihongwei/code/personal/shared-services/postgres`, listening on `127.0.0.1:55432`, database `turb_console`. Do not add a project-local Compose PostgreSQL, and do not delete the `turb-gpt-free-register_turb_gpt_postgres_data` volume.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `perf:`).
