# 开源协议注册驱动接入 Implementation Plan

> 历史说明：本文记录当时的设计或实施计划，不代表当前运行状态；现行行为与约束以 README、AGENTS.md 和当前代码为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在注册页增加独立的 `protocol_oss` 选项，将固定上游版本的注册协议流程适配到本地任务、邮箱、代理、Attempt/Run、PostgreSQL 与后处理体系。

**Architecture:** 保留上游协议源码快照于独立 vendor 子树，由 `core.registration.protocol_oss` 作为适配入口；dispatcher 继续按每个任务冻结的 `registration_driver` 分流。WebUI 传递批次选项，搜索、任务列表和后处理继续使用本地服务。

**Tech Stack:** Python、Flask、PostgreSQL、现有现代 WebUI JavaScript、`tools/test_isolated.py`、Playwright。

**Spec:** `docs/superpowers/specs/2026-10-16-open-source-registration-driver-design.md`

## Global Constraints

- 上游基线固定为 `myfanhua/turb-gpt-free-register` 的 `83721dc33a83b3e09dfdf7d91cc511b0124d9b4c`，许可证为 MIT。
- 本地优化 Protocol 的请求流程、检查点、错误分类、续跑和后处理行为保持不变。
- 注册任务快照字段为 `config_snapshot.registration_driver`，开源驱动名固定为 `protocol_oss`。
- 邮箱、代理、Attempt/Run、账号持久化和套餐、2FA、Codex、Flow 后处理走本地实现。
- 存储测试使用项目隔离 PostgreSQL 测试入口，不连接生产库或 `public` schema。

---

### Task 1: 固定上游源码快照

**Files:**
- Create: `core/registration/protocol_oss/upstream/main.py`
- Create: `core/registration/protocol_oss/upstream/core/chatgpt_auth.py`
- Create: `core/registration/protocol_oss/upstream/core/openai_auth.py`
- Create: `core/registration/protocol_oss/upstream/config/openai_protocol.py`
- Create: `core/registration/protocol_oss/upstream/LICENSE`
- Create: `core/registration/protocol_oss/upstream/UPSTREAM.md`
- Create test: `tests/test_protocol_oss_vendor.py`

**Interfaces:**
- Produces: 可与固定上游提交逐文件核验的协议快照、许可证和同步说明。
- Runtime boundary: 上游 `main.py` 仅作流程基线；本地运行代码只调用上游认证/协议模块，不调用上游邮箱池、账号导出、SQLite、Codex、2FA 或 Flow。

- [ ] **Step 1: 写来源契约测试**，检查 `UPSTREAM.md` 中的仓库、提交、同步范围和本地补丁说明，并确认 MIT 许可证存在。
- [ ] **Step 2: 用精确提交导入最小协议源码集**；不导入抓包、账号、邮箱、日志、数据库或导出文件。
- [ ] **Step 3: 将协议模块的导入适配限制在 vendor 边界**，使用本地 `BrowserSession` 与 Sentinel 公共组件，不改本地优化 Protocol。
- [ ] **Step 4: 运行 `python tools/test_isolated.py --profile all -- tests/test_protocol_oss_vendor.py -q`**。

### Task 2: 实现独立协议驱动

**Files:**
- Create: `core/registration/protocol_oss/__init__.py`
- Modify: `core/registration/dispatcher.py`
- Modify: `core/registration/standalone.py`
- Test: `tests/test_registration_dispatcher.py`
- Create test: `tests/test_protocol_oss_adapter.py`

**Interfaces:**
- Produces: `run_protocol_oss_registration(email, name, birthday=None, proxy=None, otp_code=None, existing_password=None, existing_totp_secret=None, profile_id=None, registration_options=None, email_source=None) -> dict`。
- Consumes: dispatcher 的统一注册参数、上游认证/协议 helper、本地邮箱 OTP、任务进度/停止、密码与 TOTP checkpoint、账号核心持久化及本地后处理服务。
- 返回值遵循现有 `registration_success`、`core_persisted`、`postprocess_success`、`partial_success`、`next_actions`、`account_readiness` 契约。

- [ ] **Step 1: 添加失败的分发测试**，验证 `protocol_oss` 使用独立函数及 standalone `driver_name="protocol_oss"`，不调用 `run_protocol_registration`。
- [ ] **Step 2: 添加适配器契约测试**，验证邮箱来源、代理、进度、停止回调和本地核心持久化由本地适配层提供。
- [ ] **Step 3: 实现上游注册主链路适配**，将 OTP 交给指定的本地邮箱来源，将 Attempt/Run 与密码检查点绑定当前任务；未知提交结果保留原身份供本地恢复。
- [ ] **Step 4: 接入本地核心持久化和后处理**，只使用本地套餐、2FA、Codex、Flow 和状态收口服务。
- [ ] **Step 5: 扩展 dispatcher 对 `protocol_oss` 的白名单和分支**，保持现有 Protocol/Roxy 分支原样。
- [ ] **Step 6: 运行 `python tools/test_isolated.py --profile all -- tests/test_protocol_oss_adapter.py tests/test_registration_dispatcher.py -q`**。

### Task 3: 冻结批次选项并开放 API 选择

**Files:**
- Modify: `core/registration_service.py`
- Modify: `webui/routes/jobs.py`
- Modify: `config/schema.py`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `tests/test_registration_country_snapshot.py`
- Test: `tests/test_email_source_selection.py`
- Test: `tests/test_feature_availability.py`
- Test: `tests/test_registration_retry_driver.py`
- Test: `tests/test_config_defaults.py`
- Test: `tests/test_config_ui.py`

**Interfaces:**
- Produces: `submit_registration(..., registration_driver: str | None = None)`；只接受 `protocol`、`protocol_oss`、`roxy`。
- POST `/api/jobs` 接收 `registration_driver`，入队时将归一化 driver 写入本批每个 job 的 `config_snapshot`；未提供时沿用全局默认。
- GET `/api/email-sources` 同时返回驱动选项与当前全局默认，手动邮箱模式也返回驱动选项。

- [ ] **Step 1: 测试服务快照**，确认显式 driver 覆盖全局默认且整批一致，未传 driver 时保留旧配置行为。
- [ ] **Step 2: 测试 API 白名单**，确认三个有效值分别入队，无效值在创建任务前返回 400。
- [ ] **Step 3: 实现 service/API/config schema/.env.example/README 更新**，沿用任务快照恢复原 driver 的既有机制。
- [ ] **Step 4: 扩展可用性判断**，全局默认 `protocol_oss` 时报告支持，不要求 Roxy 配置。
- [ ] **Step 5: 运行上述三个定向测试文件**。

### Task 4: 任务可观察性、搜索和注册页

**Files:**
- Modify: `core/account_search.py`
- Modify: `core/admin_repository.py`
- Modify: `webui/route_helpers.py`
- Modify: `webui/templates/index.html`
- Modify: `webui/static/js/modern/jobs.js`
- Test: `tests/test_account_search.py`
- Test: `tests/test_account_search_api.py`
- Create test: `tests/test_registration_jobs_frontend.cjs`

**Interfaces:**
- Produces: 任务列表只返回安全的 `registration_driver`；注册页可选“本地优化 Protocol”“开源 Protocol”“RoxyBrowser”；搜索短语“优化协议”“开源协议”分别命中两种协议。
- Existing query “协议”与 `method:protocol` 继续只匹配本地优化 Protocol，避免既有搜索语义变化。

- [ ] **Step 1: 添加搜索与 API 测试**，验证三种 driver 对应各自快照，开源和优化别名不互相命中。
- [ ] **Step 2: 添加前端测试**，验证已选 driver 随注册请求提交，并在提交结果中展示对应名称。
- [ ] **Step 3: 实现安全任务投影、搜索别名和注册页选择器**，任务表增加 driver 信息列并维持当前现代页面布局。
- [ ] **Step 4: 运行三个定向测试文件**。

### Task 5: 集成回归和真实批次验收

**Files:**
- Test: `tests/test_registration_dispatcher.py`
- Test: `tests/test_registration_country_snapshot.py`
- Test: `tests/test_email_source_selection.py`
- Test: `tests/test_account_search.py`
- Test: `tests/test_account_search_api.py`
- Test: `tests/test_protocol_oss_adapter.py`
- Test: `tests/test_registration_retry_driver.py`
- Test: `tests/test_protocol_registration_password.py`
- Test: `tests/test_protocol_standalone.py`
- Test: `tests/test_registration_postprocess_contract.py`

**Interfaces:**
- Consumes: 两个 driver 的统一 dispatcher、每任务快照、注册页选项和本地适配结果。
- Produces: 聚合批次结果；报告只包含 driver、batch id、提交数、成功/部分成功/失败/待核验数，不输出邮箱、Token、密码、OTP 或代理凭据。

- [ ] **Step 1: 运行 `python tools/test_isolated.py --profile all -- tests/test_registration_dispatcher.py tests/test_registration_country_snapshot.py tests/test_email_source_selection.py tests/test_feature_availability.py tests/test_account_search.py tests/test_account_search_api.py tests/test_protocol_oss_vendor.py tests/test_protocol_oss_adapter.py tests/test_registration_retry_driver.py tests/test_protocol_registration_password.py tests/test_protocol_standalone.py tests/test_registration_postprocess_contract.py -q`**。
- [ ] **Step 2: 运行 `ruff check` 覆盖本次新增和修改的 Python 文件，并执行 `git diff --check`**。
- [ ] **Step 3: 用真实浏览器验证注册页可选两种协议，确认请求携带所选 driver 且任务行展示其来源**。
- [ ] **Step 4: 本地回归通过后，分别以 `protocol` 和 `protocol_oss` 提交 50 个任务；保持邮箱来源、并发及其它选项一致，并核对两批任务、Attempt/Run、账号持久化与最终状态的脱敏汇总**。
