# 当前项目架构

> 本文只描述当前代码的稳定边界；代码规模、测试耗时和历史改造记录不作为架构事实。
> 发生冲突时以代码、配置 schema、数据库表定义和测试契约为准。

## 1. 运行形态与入口

项目是一个以 PostgreSQL 为运行时事实来源的 Python 单体应用，提供两个共享同一业务层的
入口：

```text
CLI main.py
  -> main.run_registration（兼容门面）
  -> core.registration.dispatcher.run_registration

WebUI web.py
  -> PostgreSQL 启动检查
  -> webui.app.create_app（装配鉴权与各领域 Blueprint）
  -> webui.runtime.start_runtime（在同一进程恢复任务并启动后台工作）
  -> Flask 接收 HTTP 请求
```

Web 进程同时承担 HTTP 和后台执行职责。Flask 路由处理请求，读请求调用查询服务和仓储，写请求由各领域服务受理。`start_runtime()` 负责启动恢复、任务分发、投影和定时工作。打开页面或创建 Flask 应用都不会触发这段启动流程。[Web 入口](../../web.py) · [应用工厂](../../webui/app.py) · [运行时](../../webui/runtime.py)

`/healthz` 表示 HTTP 进程存活。`/readyz` 同时检查 PostgreSQL 和同一进程内的 runtime，两者都就绪时返回 200，否则返回 503。[健康检查](../../webui/routes/health.py)

路由 URL、HTTP 方法和 endpoint 的契约检查位于
[`tests/webui/test_route_contract.py`](../../tests/webui/test_route_contract.py)。调整路由时应同时
核对现行实现与契约，不在架构文档中重复维护路由数量。

## 2. 分层边界

```text
config/
  -> 配置默认值、schema、环境变量加载和热重载快照
core/
  -> 注册、账号、Codex、邮箱、代理、任务、存储与外部客户端
webui/ routes/
  -> 参数校验、服务调用、响应序列化、现代界面
main.py / web.py
  -> CLI 兼容入口与 Web 进程生命周期
```

`core/` 不反向依赖 `webui/` 或 CLI。路由不得直接重写业务状态机；配置的公开字段以
`config/schema.py` 为准，页面编辑器和所有入口必须共用相同的配置语义。

WebUI 维护一套现代界面。主模板为 `webui/templates/index.html`，原页面脚本和样式位于
`webui/static/js/pages/`、`webui/static/js/shared/` 与 `webui/static/css/`。已迁移的 Vue 页面和报告组件在 `frontend/src/`，由现有页面入口加载。[各页面接入范围](list-ui.md#当前接入范围)

`core/` 内按业务查找：`registration/`、`accounts/`、`codex/`、`email/`、`extract_link/`、`proxy/` 和 `sms/`；域内共用逻辑在各自根部，具体驱动或提供方在子目录。跨业务认证、浏览器、网络、任务和调度分别在 `auth/`、`browser/`、`network/`、`operations/`、`runtime/`，仓储集中于 `storage/<业务>/`。`integrations/` 放外部流程及 sub2api 客户端。

注册只保留 `registration/roxy/` 与 `registration/protocol_oss_2/`。protocol-2 的生命周期和后处理位于自身 `lifecycle.py`，错误展示与历史驱动映射使用公共外围模块。旧注册代码可在 Git 基线 `a4f20f3` 查阅；账号协议认证与注册驱动分离。新调用应使用真实实现路径。具体文件索引见 [README 项目结构](../../README.md#项目结构) 和[功能地图](functional-map.md)。

配置的模块结构与热加载名称保持不变。工具真实实现归入 `tools/{diagnostics,benchmarks,maintenance,migrations}/`，原命令保留薄入口；测试按业务归组，公共隔离与源码读取帮助文件继续位于 `tests/` 根部。

## 3. 主要业务流

### 注册

```text
POST /api/jobs
  -> core.registration.service.submit_registration
  -> registration_jobs（pending）+ ThreadPoolExecutor
  -> _run_one_job 的数据库条件抢占
  -> 网络租约、邮箱来源/邮箱领取或恢复
  -> core.registration.dispatcher.run_registration
  -> 按冻结配置选择 protocol_oss_2 或 roxy 注册驱动
  -> 账号、资源与可选后置步骤收口
```

完整的阶段、续跑和资源回收规则见[注册流程](../workflows/registration.md)。

### 账号操作与任务中心

```text
领域 service / WebUI / 定时任务
  -> core.operations.task_gateway 或原生 operation service
  -> operation_tasks / operation_runs / operation_events / operation_resources
  -> 账号资源族租约、取消检查点、终态收口
```

`/api/operations` 和旧 `/api/account-tasks` 的列表、详情共用 `core.operations.query_service`。应用层负责公开状态和错误投影，存储层负责筛选、计数和分页。进度与事件按所选 Run 查询。[列表与任务详情](list-ui.md)

新原生 operation 与 `account_action_*` 兼容来源并存；后者会按来源投影到 operation 表，
不能把“统一列表”误解成旧表已经删除。详见[账号操作](../workflows/account-operations.md)。

### Codex OAuth

Codex 补跑由 `core.codex.operation_service` 创建或重跑原生 operation，再调用
`core.codex.oauth.run_codex_oauth`。实际凭证保存、callback 确认、资源台账和失败后的
可重跑边界见[Codex OAuth 操作](../workflows/codex-oauth-operation.md)。

## 4. 数据与恢复边界

PostgreSQL 是账号、注册任务、邮箱池、代理租约、Codex 凭证和任务运行状态的唯一事实
来源。兼容 JSON/TXT/HTML/凭证导出只能是输入、缓存或对外输出，不能在数据库不可用时
充当回退存储。

业务行级表包括 `registered_accounts`、`registration_jobs`、各类 `email_pool_*`、
`proxy_leases` 和 `codex_credentials`；任务中心以 `operation_tasks`、`operation_runs`、
`operation_events`、`operation_resources` 和账号资源租约表达运行历史。迁移期保留
`account_action_*`，重跑必须新增 run，不能覆盖旧 run/event。

进程启动时 runtime 先初始化 operation 存储和 handler，收口无法继续的中断 run，再启动
投影与 dispatcher；注册和兼容账号任务恢复会避开已能确认继续语义的账号/来源。恢复只能
收口运行状态或重新派发安全的 queued 工作，不得删除账号、邮箱或历史证据。

存储 schema、隔离测试和兼容导出规则见[存储架构](storage-architecture.md)。

## 5. 兼容入口

新代码使用真实实现路径。下列旧入口仍供外部脚本、历史页面链接或现有调用方使用。

| 入口 | 真实实现 | 保留原因与删除条件 |
| --- | --- | --- |
| `core.roxy_registration` | `core.registration.roxy` | 旧导入路径；确认至少一个稳定版本无源码、工具或部署脚本依赖，并完成导入兼容检查后删除 |
| `core.db` | `core.storage.db_legacy` | 业务、工具和测试仍使用的存储门面；全部切换领域仓储并完成字段对账后删除 |
| `core.operation_task_store` | `core.storage.operations.store` | 任务中心旧导入与测试 patch 点；调用全部切换并完成观察期对账后删除 |
| `core.account_task_store` | `core.storage.operations.legacy_task_store` | 仍在写入的旧账号任务模型；原生 operation 覆盖全部任务类型至少一个稳定版本后评估删除 |
| `main.run_registration` | `core.registration.dispatcher.run_registration` | CLI 与外部调用门面；调用全部切换 dispatcher 后删除 |
| `GET /api/account-tasks` 及其详情 | 新旧 GET 均调用 `core.operations.query_service`，各自保留原响应与 ID 语义 | 迁移旧调用方时核对字段、筛选和分页，确认历史任务能定位到对应的任务与 Run。重试动作和按 Run 读日志有各自的路由契约，须单独核对。[任务路由](../../webui/routes/operations.py) |
| `?ui=legacy`、`ui_mode=legacy` Cookie | 两种旧入口均返回现代首页 | 确认旧链接与 Cookie 无调用依赖，且现代首页通过入口回归后，再评估退出兼容。[首页契约](../../tests/webui/test_dashboard_api.py) |
| 批次详情深链接、原报告渲染器 | 原页面按批次与选定轮次读取报告，优先交给 Vue 展示，模块加载失败时回退 | 调整兼容入口前核对已保存的详情链接、当前结果与指定轮次。移除原渲染器前，还须验证正常加载和资源加载失败两条路径都能展示报告。[批次页面](../../webui/static/js/pages/bulk/page.js) · [浏览器回归](../../tests/bulk/test_list_navigation_browser.py) |

表中的四个 `core` 旧入口通过 `sys.modules` 绑定真实实现模块，保持锁、缓存和 patch 点的对象唯一性，
不得复制实现或改成通配符再导出。观察期内保留 `account_action_*` 表及其投影关系，不重排
任务 ID、不覆盖历史 run/event；`core.storage.operations.store.verify()` 用于检查映射、
孤儿记录、活跃资源族和终态资源的一致性。

公开的 `python tools/<脚本>.py` 命令同样保留薄入口，保持参数、当前工作目录、退出码和
单次执行语义；模块导入时绑定真实实现模块。

| 原入口（均位于 `tools/`） | 真实实现目录 |
| --- | --- |
| `analyze_har_protocol.py`、`diagnose_protocol_password_interface.py`、`diagnose_roxy_auth_interface.py` | `tools/diagnostics/` |
| `evaluate_http_backends.py`、`test_chatgpt_curl_cffi.py`、`test_performance.py` | `tools/benchmarks/` |
| `import_outlook_pool.py`、`prepare_mail_pipeline_otp_patch.py`、`test_codex_oauth.py` | `tools/maintenance/` |
| `migrate_codex_files.py`、`migrate_collections_to_tables.py`、`migrate_hme_inbox_to_butler.py`、`migrate_registration_attempts.py`、`migrate_runtime_config.py`、`migrate_unified_task_center.py` | `tools/migrations/` |

删除兼容入口前重新搜索仓库、部署脚本及外部命令引用，确认至少一个稳定版本无依赖，
完成相应契约和回归验证后逐文件删除。

## 6. 维护规则

- 代码改动先用最小相关测试验证，再按存储、运行时和发布风险扩大范围。
- 数据库测试必须使用独立测试库或 schema，不能连接生产库或使用 `public` schema。
- 账号、密码、Token、Cookie、OTP 和含凭据代理不得进入普通日志、任务事件、文档或提交。
- 当前文档维护现行使用、架构与开发规则；过期方案、迁移记录和一次性验收结果通过 Git 历史追溯。

## 7. 原六阶段计划在主线的进度

阶段名称沿用历史候选 `59795268` 的 `docs/architecture/convergence.md` 第 7 节。下表按当前主线的实现核对进度。

| 阶段 | 主线现状 | 实现或验证依据 |
| --- | --- | --- |
| 1. 整体架构设计 | 设计已记录。模块职责、依赖方向与兼容入口分别见功能地图、代码规范和本文第 5 节。 | [功能地图](functional-map.md) · [代码规范](code-conventions.md) |
| 2. 任务中心完整样板 | 部分接入。新旧任务查询共用服务，模板页面已支持紧凑列表、表头筛选、Run 切换和步骤证据。候选的任务中心 Vue 页面、OpenAPI 契约及生成类型尚未接入。 | [查询服务](../../core/operations/query_service.py) · [页面脚本](../../webui/static/js/pages/operations/page.js) · [任务详情](list-ui.md#任务详情) |
| 3. 后端职责收敛 | 部分接入。配置读取使用快照，查询展示和历史任务投影已有实现。原账号任务的动作、恢复和终态处理仍有调用使用 `core.account_task_store`。 | [配置路由](../../webui/routes/config.py) · [旧账号任务存储](../../core/storage/operations/legacy_task_store.py) · [运行时](../../webui/runtime.py) |
| 4. 性能测量与优化 | 部分接入。账号列表在无业务筛选时合并精确分类计数。任务列表在仅按运行中状态筛选且不请求分类计数时先缩小候选 ID。现有回归核对查询结果与字段，整站容量及端到端延迟仍待验证。 | [账号分类计数回归](../../tests/accounts/test_account_grouped_facets.py) · [任务读取回归](../../tests/operations/test_operation_task_read_optimization.py) |
| 5. 其他业务页面迁移 | 部分接入。五个 Vue 构建入口覆盖总览、代理与流量、提链统计、历史子邮箱、批次列表和批次详情内的报告。账号与凭证列表、配置编辑、注册和提链工作台、批次目标与轮次控制仍由原页面承接。 | [构建入口](../../frontend/vite.config.ts) · [各页面接入范围](list-ui.md#当前接入范围) |
| 6. Web / Worker 运行隔离 | 独立运行角色尚未接入。主线由 `web.py` 在同一进程组装应用、启动后台工作并提供 HTTP 服务。 | [Web 入口](../../web.py) · [运行时回归](../../tests/webui/test_webui_runtime.py) |
