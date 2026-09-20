# 邮箱换绑与代理流量 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在当前 PostgreSQL + durable operation 架构中实现协议换绑邮箱、独立代理与浏览器流量运维页面，并完成测试、迁移和受控真实验证。

**Architecture:** 邮箱换绑作为 `email_change` 原生 operation，由账号 lease 和 remote intent/receipt 保护，协议层复用公开仓库的 `change_email` 与 Recent Login 流程但使用本地 `BrowserSession`、邮箱池和用途化代理。代理与流量作为独立认证页面读取持久化租约和流量摘要，账号页面保持现有 compact contract。

**Tech Stack:** Python, Flask, PostgreSQL/psycopg, curl_cffi `BrowserSession`, 现有 operation gateway, 现有 HTML/CSS/vanilla JS WebUI, pytest。

**Spec:** `docs/superpowers/specs/2026-09-16-email-change-proxy-traffic.md`

## Global Constraints

- 邮箱换绑不打开 Roxy/Selenium，不增加浏览器兜底。
- 账号、Token、OTP、邮箱池秘密、代理认证信息和日志私有数据不得提交或进入普通 API。
- PostgreSQL 是事实来源；不新增 SQLite 或文件任务模式。
- 任务中心使用现有 `operation_tasks` / `operation_runs`；不复制一套邮箱换绑队列表。
- 代理页面可展示完整 `exit_ip`，但代理 URL、用户名和密码必须隐藏。
- 账号列表和账号详情保持现有字段契约；代理/流量独立页面承载新增展示。
- 必须保留现有未相关改动；提交和合并时只包含本功能及必要测试/文档。
- 任何远程写请求都要在提交前记录 intent，响应不等于最终成功；不确定结果禁止盲重试。

---

### Task 1: 邮箱换绑协议与 Durable Operation

**Files:**
- Create: `core/email_change_service.py`
- Modify: `core/storage/accounts.py`, `core/storage/db_legacy.py`
- Modify: `core/account_proxy.py`, `core/account_liveness.py`, `core/chatgpt_bootstrap.py`, `config/account.py`, `config/schema.py` only where the shared protocol reauth/config contract requires it
- Modify: `webui/runtime.py`, `webui/routes/accounts.py`, `core/task_progress.py`, `core/task_errors.py`
- Test: focused email-change protocol, storage, task-gateway, retry and request-unknown tests under `tests/`

**Interfaces:**
- Produces durable task type `email_change`, source system `native_operations`, resource family `openai_interactive`.
- Handler accepts `OperationHandlerContext` and reports safe stages/events; it must not write credentials into event detail.
- Uses existing `email_provider` acquisition/OTP adapters and existing `account_proxy.acquire_account_proxy(purpose="email-change")`.
- Uses local `BrowserSession`; adapt the public implementation rather than copying its SQLite/thread-pool storage or `fingerprint_seed` constructor.

- [ ] Add failing tests for task submission, account conflict, stage projection, protocol `begin/verify`, conditional `reauth_required`, local writeback, and uncertain remote response.
- [ ] Run the focused tests and record expected failures before implementation.
- [ ] Implement account email-change storage operations with row locks and preserved original mailbox material; keep AT invalidation and email update atomic.
- [ ] Implement the protocol flow: existing AT begin first; on explicit `reauth_required`, warm the authenticated session when available, run local protocol Recent Login with old-email OTP, retry begin once with the fresh AT, wait for new-email OTP, then verify.
- [ ] Add remote intent/receipt boundaries around begin and verify and classify network interruption after remote submission as `request_unknown`.
- [ ] Register the durable handler, account route(s), bulk submission, retry/cancel policy, config snapshot allowlist, and task progress template. Post-change AT recovery must use an existing protocol live-check child/dependency rather than a raw thread.
- [ ] Ensure no browser fallback path is reachable from `email_change`; preserve existing 2FA fallback behavior outside this task type.
- [ ] Run focused tests and commit the task with a scoped message.

### Task 2: 持久化代理与浏览器流量后端

**Files:**
- Create: `core/browser_traffic.py` or the smallest focused traffic-summary module matching existing naming
- Create: `webui/routes/proxy_traffic.py` if a separate blueprint is appropriate
- Modify: `core/record_store.py`, `core/proxy_lease_store.py`, `core/proxy_provider.py`
- Modify: `core/registration_service.py` and blueprint registration module as needed
- Test: proxy correlation, raw exit IP page scope, masking, traffic aggregation, and migration tests under `tests/`

**Interfaces:**
- Produces a read-only authenticated API for current leases, history, and traffic summaries.
- `proxy_leases` rows correlate provider, endpoint, exit IP, state, account ID, purpose, operation task/run, registration job, and route attempt where available.
- Traffic summaries contain source/method, timing, upload/download/total bytes, request counts, failed/unfinished/unknown counts, and no URL/header/body payload.

- [ ] Add failing tests proving persistent lease rows survive process-memory absence, raw `exit_ip` is returned only by the new page API, and all generic account/job compact APIs remain masked/unchanged.
- [ ] Implement an idempotent additive schema migration and backfill-safe nullable correlation fields; keep static proxy pool configuration distinct from dynamic leases.
- [ ] Route account operations and registration lease acquisition through the correlation fields without changing unrelated routing policy or silently forcing direct traffic.
- [ ] Add a lightweight Roxy/CDP summary collector boundary; do not reuse raw diagnostic capture or persist sensitive request contents. Protocol email-change tasks must report traffic as unavailable rather than inventing browser bytes.
- [ ] Add the authenticated blueprint/API and query PostgreSQL joins rather than `_ACTIVE_ENDPOINTS` only.
- [ ] Run focused tests and commit the task with a scoped message.

### Task 3: 独立代理与流量 UI

**Files:**
- Modify: `webui/templates/index.html`, `webui/templates/index_legacy.html`
- Modify: the existing modern/legacy navigation, page shell, CSS and JS modules selected after inspection
- Modify: `webui/static/js/modern/jobs.js` only if a task-center link/status badge is needed; do not add proxy columns to account pages
- Test: template/API contract tests and Playwright/browser smoke coverage where the project already supports it

**Interfaces:**
- Consumes Task 1 task-center API and Task 2 proxy/traffic API.
- Produces one independent “代理与流量” navigation destination with current leases, history, traffic views, filters, responsive tables/details, loading/empty/error states, and raw exit IP rendering only in that destination.

- [ ] Inspect existing UI tokens and navigation before editing; preserve current information density and avoid a marketing/card-heavy layout.
- [ ] Design the desktop information hierarchy: toolbar filters, summary counts, current lease table, historical table, traffic table/detail drawer, and clear state badges.
- [ ] Design mobile behavior with readable wrapping/detail view, stable table dimensions, keyboard/focus states, and no horizontal page overflow.
- [ ] Implement the new menu/page using existing icons and styles; keep account page structure unchanged.
- [ ] Connect polling/refresh to the new APIs without exposing raw proxy URLs or secrets.
- [ ] Run template/JS tests and browser smoke checks, then commit the task with a scoped message.

### Task 4: 子任务审查与集成修复

**Files:**
- Review all changes from Tasks 1-3; modify only files needed to resolve concrete findings.
- Test: focused suites for all three tasks plus operation/proxy/account regression suites.

- [ ] Review each task diff for spec compliance, secret leakage, lease conflicts, duplicate remote writes, migration safety, and UI contract regressions.
- [ ] Resolve cross-task interface mismatches, especially task type registration, API response shape, operation dependency state, and proxy correlation IDs.
- [ ] Run focused suites in an isolated test schema and record baseline failures separately.
- [ ] Run the full test suite; no new failures may be introduced beyond the recorded baseline.
- [ ] Run a WebUI smoke test on a non-production local port and verify `/login`, task center, new menu, API responses, and no raw secrets.

### Task 5: 本机迁移、真实验证与发布

**Files:**
- Only migration/runtime/config files already reviewed in Tasks 1-4.

- [ ] Back up the relevant PostgreSQL schema/data metadata and verify the backup is readable before applying changes.
- [ ] Apply the additive migration to the local shared PostgreSQL database with production DB guardrails intact; verify table/index/column state and startup logs.
- [ ] Restart the local WebUI on `PORT=8000`, verify PID/cwd/listener/logs and `/login` HTTP 200.
- [ ] Choose one controlled account/mailbox and execute exactly one email-change task through the UI; observe task stages, remote result, account writeback, child live-check/AT writeback, and proxy page data. Do not retry on an uncertain remote result without reconciliation evidence.
- [ ] Verify the new menu in browser at desktop and mobile viewport sizes and confirm account page remains unchanged.
- [ ] Review `git diff`, run final focused/full verification, create a scoped commit, merge to local `main`, verify the merge, and push the named configured remote/ref only after all checks pass.
