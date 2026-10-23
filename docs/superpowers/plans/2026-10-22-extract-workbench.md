# 提链工作台实施计划

> 历史说明：本文记录当时的设计或实施计划，不代表当前运行状态；现行行为与约束以 README、AGENTS.md 和当前代码为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development for the independent configuration, provider adapter, and workbench UI tasks. Keep the durable service, storage, API integration, and final verification under the coordinating agent. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 durable 提链流程上新增独立提链工作台、Lumen Flow 与幻光适配器，并在配置页管理所有平台、支付、复核和并发开关。

**Architecture:** `core/extract_link_service.py` 继续拥有账号预检和 durable Run；新的 provider registry 负责请求与状态归一化；PostgreSQL 私有 Run 存储保留远端轮询凭据；工作台只消费安全的任务投影，并把后续支付/状态同步提交为同一逻辑任务的新 Run。平台并发在 durable dispatcher 提交前非阻塞准入，仍受 `ACCOUNT_BATCH_WORKERS` 总预算约束。

**Tech Stack:** Python、Flask、PostgreSQL JSONB/durable operations、项目 `config.schema`、原生 JavaScript、pytest/unittest、Node `node:test`。

**Spec:** [2026-10-22-extract-workbench-design.md](../specs/2026-10-22-extract-workbench-design.md)

## Global Constraints

- PostgreSQL 是唯一事实来源；存储测试继承 `tests.support_pg.PostgresTestCase`，使用独立 `test_` schema，不连接生产 `turb_console` 或 `public`。
- 密钥只存 `.env` secret；AT、CDK、代理凭据、`job_secret` 和远端完整响应不得进入普通任务数据、事件、日志或 WebUI 列表投影。
- 所有开关在配置页体现；自动支付默认关闭，API 参数不能越过全局/平台配置启用能力。
- 复用现有账号操作租约、账号资格校验、`_ensure_extract_token` 和 `ACCOUNT_BATCH_WORKERS`，不得创建并行的账号锁或重登实现。
- 对无响应的提链操作保留原 Run 并允许重跑；付款状态成功或未知时先恢复/查询原远端状态，不重复发送扣款请求。
- 用户授权的首个外部冒烟仅选一条 2026-10-14 前后符合资格的账号，调用 Lumen `extract_only`，不调用支付 API。
- 与用户沟通、新增文档、注释和界面文字使用中文；API 字段和 provider ID 保留原始拼写。

---

### Task 1: 平台配置与功能开关

**Files:**
- Modify: `config/schema.py`
- Modify: `config/extract_link.py`
- Modify: `.env.example`
- Modify: `webui/static/js/modern/config.js`
- Modify: `README.md`
- Test: `tests/test_config_runtime_contract.py`
- Test: `tests/test_config_defaults.py`
- Test: `tests/test_config_ui.py`

**Interfaces:**
- 配置项统一使用 `EXTRACT_LINK_*` 前缀，平台 ID 固定为 `legacy`、`lumen_flow`、`huanguang`。
- 全局字段：`EXTRACT_LINK_ENABLED`、`EXTRACT_LINK_DEFAULT_PROVIDER`、`EXTRACT_LINK_DEFAULT_MODE`、`EXTRACT_LINK_EXTRACT_ENABLED`、`EXTRACT_LINK_MANUAL_PAYMENT_ENABLED`、`EXTRACT_LINK_AUTO_PAYMENT_ENABLED`、`EXTRACT_LINK_POST_PAYMENT_CHECK_ENABLED`、`EXTRACT_LINK_POST_PAYMENT_REFRESH_AT_ENABLED`、`EXTRACT_LINK_POST_PAYMENT_PLAN_CHECK_ENABLED`。
- 每个平台字段：`EXTRACT_LINK_{LEGACY|LUMEN_FLOW|HUANGUANG}_{ENABLED|EXTRACT_ENABLED|MANUAL_PAYMENT_ENABLED|AUTO_PAYMENT_ENABLED|CONCURRENCY|DEFAULT_TYPE|API_BASE|CDK|REQUEST_TIMEOUT|POLL_INTERVAL|EVENT_TIMEOUT}`。为维持环境变量兼容，legacy 的 `API_BASE`、`CDK`、`DEFAULT_TYPE`、`REQUEST_TIMEOUT`、`EVENT_TIMEOUT` 映射至现有 `EXTRACT_LINK_API_BASE`、`EXTRACT_LINK_CDK`、`EXTRACT_LINK_TYPE`、`EXTRACT_LINK_REQUEST_TIMEOUT`、`EXTRACT_LINK_EVENT_TIMEOUT`，不创建同义配置。CDK 字段的 `secret=True`。
- `config.schema` 为每个布尔/枚举/数字字段提供显式类型、范围、默认值及中文帮助；默认平台为 legacy，默认模式为 `extract_only`，全局及逐平台 auto-payment 开关默认 `false`，新增平台默认关闭，legacy 保持现有启用行为，逐平台并发默认 `1`。服务端能力取全局与平台开关交集。

- [ ] **Step 1: 先写配置 schema 合同测试**

```python
def test_extract_provider_payment_switches_are_editable_and_auto_payment_defaults_off():
    assert CONFIG_SCHEMA["EXTRACT_LINK_LUMEN_FLOW_ENABLED"].type == "bool"
    assert CONFIG_SCHEMA["EXTRACT_LINK_LUMEN_FLOW_CDK"].secret is True
    assert schema.schema_default("EXTRACT_LINK_DEFAULT_MODE") == "extract_only"
    assert schema.schema_default("EXTRACT_LINK_AUTO_PAYMENT_ENABLED") is False
    assert schema.schema_default("EXTRACT_LINK_LUMEN_FLOW_AUTO_PAYMENT_ENABLED") is False
```

- [ ] **Step 2: 运行配置测试确认新字段尚未通过**

Run: `python tools/test_isolated.py --profile all -- tests/test_config_runtime_contract.py tests/test_config_defaults.py -q`
Expected: 新增字段缺失导致断言失败；测试使用隔离配置，不读取真实 `.env` 值。

- [ ] **Step 3: 实现 schema、配置默认值和 `.env.example`**

配置模块逐一导出 schema 中的全局开关和三个平台配置；legacy 导出仍沿用现有变量名，避免现有调用方改名。

在 `config/schema.py` 同步维护 `_DEFAULTS`、`_RANGES`/`_OPTIONS`、类型映射、secret 标记和可编辑字段；现有配置保持原值与兼容语义。

- [ ] **Step 4: 验证配置页面分组与密钥行为**

Run: `python tools/test_isolated.py --profile all -- tests/test_config_runtime_contract.py tests/test_config_defaults.py tests/test_config_ui.py -q`
Expected: 新增字段可在“配置 → 服务集成 → 提链”检索、保存、重载；GET 和快照不返回任何 CDK 值，auto-payment 默认关闭。

- [ ] **Step 5: 更新 README 的提链配置说明并提交本任务**

README 说明平台启用、默认模式、逐平台并发和支付/复核开关；示例只给空 secret，不抄入用户提供的 CDK。

```bash
# README.md 已有用户改动；只暂存本任务新增的提链说明 hunk，不暂存已有改动。
git add config/schema.py config/extract_link.py .env.example webui/static/js/modern/config.js tests/test_config_runtime_contract.py tests/test_config_defaults.py tests/test_config_ui.py
git commit -m "feat: add extraction provider configuration"
```

### Task 2: Provider 适配器与状态契约

**Files:**
- Create: `core/extract_link_providers/__init__.py`
- Create: `core/extract_link_providers/contracts.py`
- Create: `core/extract_link_providers/legacy.py`
- Create: `core/extract_link_providers/lumen_flow.py`
- Create: `core/extract_link_providers/huanguang.py`
- Test: `tests/test_extract_link_providers.py`

**Interfaces:**
- `ProviderConfig` 是 worker 内存对象，含 `provider_id`、API Base、CDK、能力开关、并发和超时；禁止序列化到 task data/config snapshot。
- `ExtractRequest` 含 `account_id: int`、内存 `access_token: str`、`link_type: str`、`mode: Literal["extract_only", "manual_payment", "auto_payment"]`、`idempotency_key: str`、经校验的 options 和可选入口/出口代理。
- `ProviderJob` 返回 `job_id: str | None`、归一化 extraction/payment state、受控链接结果和仅供私有存储使用的 `private_data: dict`。
- `ExtractLinkProvider` 提供 `create_job(request)`、`get_status(job_ref)`、`start_payment(job_ref, options)`；不支持的能力返回明确 `unsupported`，不能伪造支持。
- `get_provider(provider_id)` 只从显式 registry 返回 provider；未知 ID 或未启用能力拒绝提交。

- [ ] **Step 1: 写 adapter contract 测试**

使用注入的 mock HTTP transport 记录 create/status/payment 请求；服务流程测试断言 `extract_only` 只创建并查询提链任务，未调用 payment adapter。

- [ ] **Step 2: 运行 adapter 测试确认 contract 缺失**

Run: `python tools/test_isolated.py --profile all -- tests/test_extract_link_providers.py -q`
Expected: FAIL，直到 contracts 与 registry 建立。

- [ ] **Step 3: 实现三个 adapter 并归一化远端响应**

Lumen 使用文档中的 flow submit/status/payment/sync 边界；幻光创建与进度查询使用 `job_id`/`job_secret`，并要求调用方传入已有代理池分配的入口/出口线路；legacy adapter 包装当前 `/api/extract` 与 SSE，不改旧协议。

- [ ] **Step 4: 用 mock transport 验证响应、能力和脱敏**

Run: `python tools/test_isolated.py --profile all -- tests/test_extract_link_providers.py -q`
Expected: 覆盖 Lumen extract-only 请求体不含支付选项、Huanguang 状态映射、legacy 兼容、无效状态、未知响应、secret 不出现在摘要和异常文本。

- [ ] **Step 5: 提交 adapter 边界**

```bash
git add core/extract_link_providers tests/test_extract_link_providers.py
git commit -m "feat: add extraction provider adapters"
```

### Task 3: 远端任务私有存储与 dispatcher 并发准入

**Files:**
- Create: `core/storage/extract_link_jobs.py`
- Modify: `core/operations/task_gateway.py`
- Modify: `core/storage/operation.py`
- Test: `tests/test_extract_link_provider_storage.py`
- Test: `tests/test_operation_gateway_dispatcher.py`

**Interfaces:**
- `save_provider_job(run_id, provider_id, job_id, public_state, private_data)`、`get_provider_job_private(run_id)`、`update_provider_job_state(run_id, public_state)`。
- 私有 `private_data` 与公共摘要分列保存；普通 `get_task`、`list_tasks` 和 operation events 不返回私有列。
- dispatcher handler 注册可选的 `dispatch_capacity_key(run)` 和 `dispatch_capacity_limit(key)`；准入非阻塞，未获容量的 Run 留在 queued，不占公共 executor。
- `extract_link` 的容量 key 为 provider ID，容量来自对应配置中的 `*_CONCURRENCY`；Run future 完成后释放该 key。配置降低至现有运行数以下时暂停新领取，不中断执行中的 Run。

- [ ] **Step 1: 写隔离存储和 dispatcher 准入测试**

使用 `tests.support_pg.PostgresTestCase` 和 `submit_durable_operation(...)` 创建隔离 schema 内的 task/run；比较普通 task/run projection 与 provider 私有 getter，确认 `job_secret` 仅在私有 getter 中可读。

- [ ] **Step 2: 运行存储和 dispatcher 定向测试确认失败**

Run: `python tools/test_isolated.py --profile all -- tests/test_extract_link_provider_storage.py tests/test_operation_gateway_dispatcher.py -q`
Expected: 存储接口和 capacity hook 的新断言失败；PostgreSQL 只使用隔离 `test_` schema。

- [ ] **Step 3: 实现 PostgreSQL 私有表与非阻塞 dispatcher gate**

`operation_runs`/`operation_tasks` 公开 projection 不 join 私有凭据；容量 gate 在 `try_submit` 之前占位，在 future callback 和提交异常时都释放。

- [ ] **Step 4: 验证私有数据隔离、容量公平和异常释放**

Run: `python tools/test_isolated.py --profile all -- tests/test_extract_link_provider_storage.py tests/test_operation_gateway_dispatcher.py tests/test_account_operation_executor.py -q`
Expected: 私有数据只经内部 getter 读取；满额 provider 的任务保持 queued，其他 provider 与账号操作仍可分配公共 slot；executor 拒绝或异常不会泄漏容量。

- [ ] **Step 5: 提交 storage 与 dispatcher 修改**

```bash
git add core/storage/extract_link_jobs.py core/operations/task_gateway.py core/storage/operation.py tests/test_extract_link_provider_storage.py tests/test_operation_gateway_dispatcher.py
git commit -m "feat: persist provider jobs and enforce provider limits"
```

### Task 4: Durable 提链、支付和 Plus 复核流程

**Files:**
- Modify: `core/extract_link_service.py`
- Modify: `core/task_stages.py`
- Modify: `core/feature_availability.py`
- Modify: `core/operations/task_gateway.py`
- Test: `tests/test_extract_link_integration.py`
- Test: `tests/test_extract_link_reporting.py`
- Test: `tests/test_maintenance_durable_gateway_phase2.py`
- Test: `tests/test_extract_link_provider_flow.py`

**Interfaces:**
- durable task data 保留 `provider_id`、`mode`、`link_type`、安全 options；旧 task 缺 `provider_id` 时解释为 legacy。AT/CDK 不持久化。
- 新增 `_handle_extract_operation` 的 action 分派：`extract`、`manual_payment`、`auto_payment`、`sync_status`。`extract_link_service.submit_extract_action(task_id, action)` 校验动作和配置后，调用 `retry_runtime_task(task_id, trigger=action, data={"extract_action": action})` 创建同一逻辑 task 下的新 Run，并通知既有 dispatcher；不会重做已完成的提链阶段。
- 创建 checkout 前执行执行时资格/占用检查和现有 `_ensure_extract_token`。支付成功后根据配置运行一次 inline live check，必要时使用现有强制刷新，再按配置调用 `plan_check_service`；本地 Plus 状态来自账号套餐检查而非 provider 付款状态。
- worker 重启恢复：有可读远端 job 时只查询/收口既有 job；无正文的提链失败保留重跑能力和原 Run；付款成功/未知不重复发支付请求。
- 每个平台自动支付能力需同时满足全局开关、provider 开关、模式、adapter capability 和支付渠道支持；API 直接请求不能绕过配置。

- [ ] **Step 1: 写服务行为测试**

新增 service 测试通过注入 fake provider 执行一条 `lumen_flow`/`extract_only` Run，断言仅发生创建/查状态调用，并检查公开 Run summary 不含 provider 私有凭据。

- [ ] **Step 2: 扩展现有提链测试并确认回归断言失败**

Run: `python tools/test_isolated.py --profile all -- tests/test_extract_link_integration.py tests/test_extract_link_reporting.py tests/test_extract_link_provider_flow.py -q`
Expected: provider 选择、动作 Run 与支付/Plus 状态断言在实现前失败；现有 legacy SSE 与 AT 刷新测试继续保留。

- [ ] **Step 3: 接入 provider snapshot、状态阶段和私有 job 保存**

在 handler claim 时解析 secret config；调用 provider adapter 前保存 remote intent，得到 `job_id` 后先保存安全摘要和私有查询凭据，再继续轮询。跨进程恢复读取私有 job 并继续查询。

- [ ] **Step 4: 接入 conditional post-payment verification 与 retry action**

付款成功后的查活使用 `live_check_service.run_account_live_check_inline(..., operation_context=current_context, force_refresh=False)`；仅当结果明确判定 AT 失效且 refresh 开关开启时，再用 `force_refresh=True` 走既有刷新流程。Plus 复核使用 `plan_check_service.enqueue_account_plan_check(account_id=..., email=..., access_token=latest_db_token, trigger="extract_post_payment", idempotency_key=...)`；先从账号存储重读最新 AT。复核错误不得覆盖已确认的支付成功状态。

复核错误只更新 Plus 阶段；不得把已确认付款改成支付失败。对 `request_unknown` 保留原 receipt 和可重跑状态。

- [ ] **Step 5: 运行 legacy 与新 provider 相邻回归**

Run: `python tools/test_isolated.py --profile all -- tests/test_extract_link_integration.py tests/test_extract_link_reporting.py tests/test_extract_link_provider_flow.py tests/test_maintenance_durable_gateway_phase2.py tests/test_account_operation_deactivation_policy.py -q`
Expected: legacy SSE 行为、AT 刷新规则和 durable receipts 不回退；支付关闭时无支付调用；成功付款后复核阶段按配置工作。

- [ ] **Step 6: 提交 durable flow 修改**

```bash
git add core/extract_link_service.py core/task_stages.py core/feature_availability.py core/operations/task_gateway.py tests/test_extract_link_integration.py tests/test_extract_link_reporting.py tests/test_maintenance_durable_gateway_phase2.py tests/test_extract_link_provider_flow.py
git commit -m "feat: orchestrate provider extraction and payment states"
```

### Task 5: 工作台 API 与旧入口兼容

**Files:**
- Create: `webui/routes/extract_workbench.py`
- Modify: `webui/app.py`
- Modify: `webui/routes/accounts.py`
- Modify: `webui/routes/operations.py`
- Test: `tests/test_extract_workbench_routes.py`
- Test: `tests/test_account_operation_deactivation_policy.py`

**Interfaces:**
- `GET /api/extract-workbench/config` 返回 `{default_provider, default_mode, providers:[{id,label,default_type,modes}]}`；仅列全局与平台开关都允许的模式，不返回 API secret。
- `GET /api/extract-workbench/tasks` 接受 `provider_id`、`mode`、`status`、`query`、`page`、`page_size`，返回 `{items,counts,page,page_size,total}`。每个 item 含 `task_id`、`run_id`、`email`、`provider_id`、`mode`、`task_status`、`preflight_status`、`extraction_status`、`payment_status`、`plus_status`、`run_count`、`progress`、`created_at`、`updated_at`、`message`、`error`、`has_extract_link`、`has_payment_link`；不含链接本身或密钥。
- `GET /api/extract-workbench/tasks/<task_id>` 返回该安全 item、阶段历史和安全事件；链接由独立 POST 授权 endpoint 按需返回，不含 AT、CDK、`job_secret`。
- `POST /api/extract-workbench/tasks/<task_id>/links` 按需返回用户明确请求的已保存提链/支付链接；不把链接加入普通 task list/detail 或日志。
- `POST /api/extract-workbench/tasks` 接收账号 ID、provider、mode、type/options；服务端重新检查配置和账号资格后逐账号提交 durable Run，并返回 started/busy/skipped/failed 计数。
- `POST /api/extract-workbench/tasks/<task_id>/actions` 仅接受配置和能力允许的 `manual_payment`、`auto_payment`、`sync_status`、`retry`，返回 `{accepted,task_id,run_id,error}`；所有操作都提交 durable Run，不在 Flask request thread 执行外部网络操作。
- 旧 `/api/accounts/extract-link` 与 bulk route 继续可用；未传 provider 时固定 legacy + extract-only，账号页入口不绕开资格检查。

- [ ] **Step 1: 写路线测试**

用现有 WebUI app fixture 创建真实隔离 operation task，关闭 auto-payment 配置后 POST `{"action":"auto_payment"}` 返回 409，且 provider mock 未收到 payment 调用；GET 任务和事件不含 AT、CDK、`job_secret`。

- [ ] **Step 2: 运行新路线测试并确认 endpoint 缺失**

Run: `python tools/test_isolated.py --profile all -- tests/test_extract_workbench_routes.py tests/test_operations_route_migration_phase2.py -q`
Expected: 新工作台 endpoint 未注册时返回 404，新测试失败。

- [ ] **Step 3: 建立 blueprint 和安全读/写接口**

使用统一 operation projection 和 provider private store；通过 app factory 注册新 blueprint。所有输入重新调用 service 层验证，不信任浏览器传入的 eligibility 或支付支持标记。

- [ ] **Step 4: 验证旧入口与新 endpoint 的边界**

Run: `python tools/test_isolated.py --profile all -- tests/test_extract_workbench_routes.py tests/test_account_operation_deactivation_policy.py tests/test_operations_route_migration_phase2.py -q`
Expected: 旧单/批量 route 保持原状态码与 legacy fallback；新 API 的 auto-payment、平台 disabled、未确认试用资格都会在 remote call 前拒绝；普通 JSON 不出现 secret。

- [ ] **Step 5: 提交 route 修改**

```bash
git add webui/routes/extract_workbench.py webui/app.py webui/routes/accounts.py webui/routes/operations.py tests/test_extract_workbench_routes.py tests/test_account_operation_deactivation_policy.py
git commit -m "feat: add extraction workbench APIs"
```

### Task 6: 独立工作台页面与任务卡片

**Files:**
- Modify: `webui/templates/index.html`
- Modify: `webui/static/js/modern/common.js`
- Create: `webui/static/js/modern/extract-workbench.js`
- Create: `webui/static/css/extract-workbench.css`
- Test: `tests/test_extract_workbench_frontend.cjs`

**Interfaces:**
- 独立一级 tab ID 为 `extract-workbench`；按当前 nav/tab history 机制加载，不借用账号页任务表。
- 新 JS 调用 `/api/extract-workbench/tasks`、`/api/extract-workbench/tasks/<id>` 和 actions endpoint；每次 render 只使用服务端提供的安全字段。
- `renderExtractWorkbenchTaskCard(task)` 将 preflight/extract/payment/Plus 四阶段分别显示；过滤状态以支付与 Plus 的独立字段为准。
- 平台/模式能力由 `/api/extract-workbench/config` 返回；选择器仅列出配置允许的 provider/mode，自动支付不默认选中；页面不提供修改服务端配置开关的控件。
- 新脚本向现有 `common.js` 暴露 `loadExtractWorkbench()`，只在 `extract-workbench` tab 首次打开或用户刷新时请求 API。

- [ ] **Step 1: 写前端筛选、状态卡和支付 gating 测试**

用 `node:test` 传入 `payment_status: "paid"`、`plus_status: "pending"` 的卡片数据，断言 HTML 同时显示“支付成功”和“Plus 待确认”，并分别保留两个阶段状态。

- [ ] **Step 2: 运行 Node 测试确认工作台模块缺失**

Run: `node --test tests/test_extract_workbench_frontend.cjs`
Expected: 测试因页面函数未提供而失败。

- [ ] **Step 3: 添加一级菜单、视图模板和专属 CSS/JS**

```html
<button type="button" data-tab="extract-workbench" class="sidebar-item">
  <span class="sidebar-item-label">提链工作台</span>
</button>
<section id="tab-extract-workbench" class="hidden"></section>
```

更新 `TAB_META`、`NAV_ALLOWED_TABS`、tab 显隐和加载分派；新 CSS 独立成文件，不改当前用户已修改的 `ui-foundation.css`。

- [ ] **Step 4: 实现卡片、过滤、批量提交、链接和状态操作**

页面支持全部/处理中/成功出链/成功支付/Plus 已确认/失败待确认、provider/mode/search、分页、批量账号选择和创建。Open/copy actions 仅请求显式授权的链接 endpoint；不把 raw AT 添加到工作台 list API。

- [ ] **Step 5: 验证 JS 单测、布局契约与真实浏览器交互**

Run: `node --test tests/test_extract_workbench_frontend.cjs`
Run: `python tools/test_isolated.py --profile all -- tests/test_config_ui.py -q`
Expected: 卡片阶段状态、平台筛选、disabled mode 和刷新响应竞争测试通过；真实桌面与移动视口无横向溢出，批量 extract-only 只创建选定账号任务。

- [ ] **Step 6: 提交工作台 UI**

```bash
git add webui/templates/index.html webui/static/js/modern/common.js webui/static/js/modern/extract-workbench.js webui/static/css/extract-workbench.css tests/test_extract_workbench_frontend.cjs
git commit -m "feat: build extraction workbench UI"
```

### Task 7: 端到端回归、文档和 Lumen extract-only 验收

**Files:**
- Modify: `README.md`
- Test: `tests/test_extract_link_provider_flow.py`
- Test: `tests/test_extract_workbench_routes.py`
- Test: `tests/test_extract_workbench_frontend.cjs`

**Interfaces:**
- 验收记录使用 Run ID、provider、mode、归一化状态和脱敏错误；不输出账号身份、CDK、AT、链接查询参数或代理完整地址。
- 只在自动化/mock 回归通过后，才运行用户授权的单账号 Lumen `extract_only` 测试；任何支付 endpoint 均不调用。

- [ ] **Step 1: 执行风险匹配的定向回归**

Run: `python tools/test_isolated.py --profile all -- tests/test_config_runtime_contract.py tests/test_config_defaults.py tests/test_config_ui.py tests/test_extract_link_integration.py tests/test_extract_link_reporting.py tests/test_extract_link_providers.py tests/test_extract_link_provider_flow.py tests/test_extract_link_provider_storage.py tests/test_extract_workbench_routes.py tests/test_operation_gateway_dispatcher.py -q`
Run: `node --test tests/test_extract_workbench_frontend.cjs`
Expected: 全部通过；若存储 profile 没有 `DATABASE_URL`，准确报告对应 PostgresTestCase 被 skip，不绕过隔离保护。

- [ ] **Step 2: 做静态检查和文档复核**

Run: `ruff check core/extract_link_service.py core/extract_link_providers core/storage/extract_link_jobs.py core/operations/task_gateway.py webui/routes/extract_workbench.py webui/app.py`
Expected: 本次 Python 修改无新增 lint error；README 配置说明、`.env.example` 字段与 schema 一致。

- [ ] **Step 3: 选择一个安全样本并执行无支付外部冒烟**

通过只读 PostgreSQL 查询找出 2026-10-14 前后创建、活跃、已确认免费 Plus 试用资格、无活动账号操作、无既有付款状态的候选；只选择一个。运行工作台的 live preflight；若资格或 Token 刷新结果未知则停止，不向远端提交。以配置 secret 中的用户 Lumen CDK 创建一个 `extract_only` Run；HTTP mock/审计确认没有调用 `/momo-payment`、支付同步或其他扣款 API。

- [ ] **Step 4: 核验数据库任务、浏览器和运行中的 WebUI**

确认一条 durable Run 的 provider/mode、提链状态、未支付状态和 Plus 未确认状态与卡片一致；核验 task events 和账号 projection 未泄露凭据。完成自动化测试后才重启实际托管 WebUI，并核对 PID、cwd、listener、最新日志和 `/healthz`、`/readyz`。

- [ ] **Step 5: 汇报提交、推送和运行状态**

只报告有证据的本地 commit、push、服务重启和真实 API 结果。没有用户明确要求时不 push；支付不在本次验收范围内。

## Plan Self-Review

- Spec coverage：配置开关在 Task 1；provider contract 在 Task 2；私有状态与并发在 Task 3；AT/权益/恢复/重跑在 Task 4；安全 API 与旧入口在 Task 5；一级菜单/卡片/批量提链在 Task 6；无支付流光实测和服务验收在 Task 7。
- Placeholder scan：所有任务列出具体文件、接口、命令、预期结果；无 `TBD`、无“之后再实现”步骤。
- Type consistency：adapter 的 `provider_id`、`mode`、`ProviderJob.private_data` 与 service、private store、route 投影字段一致；动作 API 写入新 Run 的 `action` 字段，provider/mode 保持原快照。
- Scope: 一条工作台端到端闭环，分层任务可并行，最终集成由协调 agent 负责。
