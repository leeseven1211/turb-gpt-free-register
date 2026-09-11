# 代理来源与提供商路由 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让代理池、代理平台和各类账号动作通过统一的、可扩展的代理来源配置路由，并默认让查套餐/查活不消耗 1024Proxy 流量。

**Architecture:** 在现有 `core/account_proxy.py` 上增加动作级来源解析和 provider registry，保留 1024 租约实现及旧配置兼容。账号补全的查套餐线路与浏览器认证线路按步骤分开申请和释放；WebUI 将所有代理字段归入“代理与网络”，由现代/旧版前端渲染二级页签。

**Tech Stack:** Python 3, Flask WebUI, existing PostgreSQL-backed task services, vanilla JavaScript, pytest/unittest.

**Spec:** `docs/superpowers/specs/2026-09-11-proxy-routing-design.md`

## Global Constraints

- 现有工作区中的无关用户改动必须保留。
- 不允许使用 `rm -r` 或 `rm -rf`；本任务不删除文件。
- `REGISTRATION_PROXY_MODE=1024` 时注册主流程不得回退到静态池或直连。
- 未实现的 `provider:<id>` 必须报明确配置错误，不静默切换到其他来源。
- 日志和 WebUI 继续只显示脱敏代理信息。

---

### Task 1: Define action-level configuration

**Files:**
- Modify: `config/account.py`
- Modify: `config/__init__.py`
- Modify: `webui/config_editor.py`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `tests/test_config_defaults.py`

**Interfaces:**
- Produces six environment-editable `ACCOUNT_*_PROXY_MODE` fields with defaults from the spec.
- Preserves `ACCOUNT_ACTION_PROXY_MODE` as the compatibility fallback.

- [x] Write tests for defaults, environment overrides, and WebUI field metadata.
- [x] Run the focused config tests and confirm they fail because the fields are absent.
- [x] Add config constants, env overrides, exports, editor metadata, example values, and documentation.
- [x] Run the focused config tests and confirm they pass.

### Task 2: Add provider/source resolution

**Files:**
- Modify: `core/account_proxy.py`
- Test: `tests/test_account_proxy.py`

**Interfaces:**
- `normalize_proxy_source(value: str | None, *, fallback: str = "registration") -> str`
- `account_action_proxy_mode(purpose: str | None = None) -> str`
- `acquire_account_proxy(..., purpose: str, explicit_proxy: str | None = None, source: str | None = None) -> AccountProxyRoute`

- [x] Write tests for `direct`, `pool`, `registration`, `provider:1024proxy`, and legacy aliases.
- [x] Run the focused account proxy tests and confirm the new source cases fail.
- [x] Implement source normalization and the provider registry without changing 1024 lease acquisition.
- [x] Ensure unknown providers raise a clear error and direct mode returns a released-free route without network calls.
- [x] Run the focused account proxy tests and the existing proxy route invariant tests.

### Task 3: Route plan checks and live checks independently

**Files:**
- Modify: `core/plan_check_service.py`
- Modify: `core/live_check_service.py`
- Modify: `core/codex_operation_service.py`
- Test: `tests/test_account_proxy.py`
- Test: existing plan/live operation tests as identified by pytest collection

**Interfaces:**
- Plan checks use `purpose="plan-check"` and therefore `ACCOUNT_PLAN_CHECK_PROXY_MODE`.
- Live checks use `purpose="live-check"` and therefore `ACCOUNT_LIVE_CHECK_PROXY_MODE`.
- Codex OAuth uses `purpose="codex-oauth"` and therefore `ACCOUNT_CODEX_PROXY_MODE`.

- [x] Add tests proving direct plan/live modes do not call `acquire_1024_proxy`.
- [x] Run the focused tests and confirm they fail with the current shared account action mode.
- [x] Pass action purpose/source through the existing acquisition calls and preserve explicit proxy overrides.
- [x] Run focused plan/live/Codex tests and verify lease release behavior remains intact.

### Task 4: Split combined account completion routes

**Files:**
- Modify: `core/codex_retry_service.py`
- Test: `tests/test_account_proxy.py` or a focused new `tests/test_account_completion_proxy_routing.py`

**Interfaces:**
- Plan check route is acquired with `purpose="plan-check"` and released before browser/2FA work.
- Browser account setup route uses `purpose="password-setup"` when password is requested, otherwise `purpose="twofa-setup"`.

- [x] Write a test for a combined account recovery run that expects separate plan-check and account-action route decisions.
- [x] Run the route regression and verify the separate route calls and releases.
- [x] Refactor the worker to acquire/release the plan route separately and choose password before 2FA for the browser route.
- [x] Preserve checkpoints, event summaries, retry route replacement, and final route reporting.
- [x] Run account completion and 2FA regression tests.

### Task 5: Reorganize proxy configuration UI

**Files:**
- Modify: `webui/static/js/modern/config.js`
- Modify: `webui/static/js/legacy/config.js`
- Modify: `webui/static/css/modern.css` only if the existing tab styles need the new section
- Test: `tests/test_config_defaults.py` and browser/DOM smoke checks if available

**Interfaces:**
- All proxy fields expose backend group `代理与网络`.
- `proxyConfigSectionForKey(key)` maps fields into `注册线路`, `账号动作线路`, `代理提供商`, and `静态代理池`.

- [x] Add frontend grouping assertions through WebUI field metadata tests.
- [x] Run the focused metadata and static checks for the new section mapping.
- [x] Reuse the existing sectioned config renderer to add proxy sub-tabs and update category/intro text.
- [x] Keep config save, dirty-state, search, and legacy rendering behavior unchanged.
- [x] Run WebUI JavaScript syntax checks and a local browser smoke check when the server is available.

### Task 6: Verify documentation and full regression surface

**Files:**
- Modify: `.env.example`, `README.md` as needed after implementation review
- Test: targeted suite plus full available test suite

- [x] Run `pytest` for the changed config/proxy/account-operation tests.
- [x] Inspect the diff for accidental changes to existing user modifications and secret leakage.
- [x] Run the project verification commands appropriate to the touched modules.
- [x] Report any pre-existing failures separately from failures introduced by this change.
