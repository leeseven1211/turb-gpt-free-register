# 文档信息架构整理与现行流程校准设计

> 状态：待评审。本文只定义文档整理和代码流程核对方式，不修改业务实现、数据库结构、运行时数据或私有文件。
>
> 代码核对基线：`93c1a3a`（2026-09-21）。文档中的“当前”描述必须可追溯到此基线或后续已核验的代码。

## 1. 背景与目标

当前 `docs/` 同时放置了现行运行规则、已完成改造的设计/验收记录、未实施提案和
`superpowers` 工作流产生的规格与实施计划。文件名和位置没有表达其有效范围，导致
“Proposal”“已实施设计”和“当前架构”被并列当作日常操作参考。

本次目标是：

1. 为使用者提供一个唯一、简短、可从代码核验的现行入口；
2. 按注册、账号操作、Codex、存储、开发验证等领域组织当前资料；
3. 保留历史设计、实施决策和性能/迁移证据，但不再让它们伪装成当前规则；
4. 不删除任何既有文档、数据库记录、日志或私有运行文件；
5. 更新仓库内 Markdown 链接，保证移动后没有断链。

## 2. 已核对的现行代码流程

### 2.1 注册

```text
WebUI POST /api/jobs
  -> webui/routes/jobs.py:api_jobs_create
  -> core.registration_service.submit_registration
  -> 创建 PostgreSQL registration_jobs（pending）并提交线程池
  -> core.registration_service._run_one_job（条件抢占为 running）
  -> 领取网络租约、领取或恢复指定邮箱、绑定邮箱来源
  -> core.registration.dispatcher.run_registration
       -> REGISTRATION_DRIVER=roxy：core.registration.roxy.run_roxy_registration
       -> REGISTRATION_DRIVER=protocol：core.registration.protocol.run_protocol_registration
  -> 保存账号、收口邮箱/代理、执行可选的 2FA/Codex/套餐后置步骤
  -> 更新 registration_jobs 和对应的 operation 投影/事件
```

`protocol` 仍是可配置的独立注册驱动，`roxy` 是唯一浏览器驱动；旧文档把 Protocol
写成只在同一 Roxy 会话内的阶段级辅助通道，不能再作为现行说明。注册重试、
`registration_resume` 和代理换线重试必须沿用原任务的邮箱来源、账号检查点和资源
收口规则，不能描述为“重新创建一条无关联注册”。

### 2.2 账号操作与统一运行模型

```text
WebUI 账号/操作接口或定时任务
  -> 各领域 service（查活、套餐、刷新 AT、补密码/2FA、封号扫描、提链等）
  -> core.operations.task_gateway 的 durable operation
  -> operation_tasks（逻辑任务）/ operation_runs（一次执行）
  -> operation_events、operation_resources、账号资源租约
  -> handler 在安全检查点响应取消，并收口资源与终态
```

启动时 `webui.runtime.start_runtime()` 初始化 operation 存储和 handler、收口中断的
原生 run，随后启动投影 worker、统一 dispatcher 以及注册/旧账号任务的安全恢复。
兼容 `account_action_*` 仍存在，且历史来源会投影到 operation 表；因此“所有任务均已
完全切换、旧表不再参与”的描述不准确。

### 2.3 Codex OAuth 补跑

```text
WebUI / 注册后置步骤 / CLI
  -> core.codex_operation_service
  -> create_runtime_task 或 create_runtime_batch
  -> operation_tasks / operation_runs / events / resources
  -> core.codex_oauth.run_codex_oauth
  -> 校验并写入 codex_credentials，或以 attention_required 保留待对账结果
```

`core.codex_retry_service` 仍保留历史兼容入口，不能在当前文档中被表述为唯一业务入口。
当前的权威语义是：有效凭证资产、一次执行状态和最近一次结果彼此独立；重跑新增 run，
不覆盖历史。

## 3. 文档分层与权威顺序

对某个行为发生冲突时，按以下顺序判断：

1. 已运行代码、配置 schema、数据库表定义和测试契约；
2. `README.md` 的用户可操作说明；
3. `docs/architecture/`、`docs/workflows/`、`docs/development/` 中标为“当前”的文档；
4. `docs/reference/` 中的技术参考；
5. `docs/history/` 以及 `docs/superpowers/` 中的历史设计、规格、计划和验收记录。

历史文档不删除，也不得反向修改以伪造当时的决策；仅在首页和必要的文件头说明其
历史状态、适用基线与替代的当前文档。

## 4. 目标目录与迁移清单

### 4.1 新增入口

新增 `docs/README.md`，包含：

- 文档优先级与“当前/参考/历史”标记含义；
- 按业务领域的当前阅读入口；
- 历史包与 `superpowers` 资料的用途；
- 修改当前文档时必须同时核验的代码、配置、测试和 README 范围。

### 4.2 当前文档

以下文件通过 `git mv` 移动并校准内容；必要时拆出已过期的历史叙述到 `history/`，
但不丢弃可追溯证据。

| 原路径 | 目标路径 | 处理 |
| --- | --- | --- |
| `current-architecture.md` | `architecture/current-architecture.md` | 以当前代码更新入口、路由/规模等易漂移事实；去除过期基线数字，保留稳定边界。 |
| `storage-architecture.md` | `architecture/storage-architecture.md` | 保持 PostgreSQL 唯一事实来源、隔离测试和兼容导出边界。 |
| `code-conventions.md` | `architecture/code-conventions.md` | 保留分层、私有数据和兼容入口约束，校准目录说明。 |
| `compatibility-inventory.md` | `architecture/compatibility-inventory.md` | 保持观察期与逐文件删除条件，更新链接。 |
| `core-registration-flow.md` | `workflows/registration.md` | 以 2.1 的实代码入口校准注册、续跑、资源和后置步骤。 |
| `registration-auth-support-matrix.md` | `workflows/account-auth-support-matrix.md` | 保持公开配置与支持范围的唯一矩阵角色，并标记仅刷新 AT 可选 v2。 |
| `codex-operation-architecture.md` | `workflows/codex-oauth-operation.md` | 校准为 Codex 原生 operation 说明，并写明兼容入口仍存在。 |
| `optimization-release.md` | `development/release-verification.md` | 保留可复用的隔离测试与发布检查；把一次性性能数字改为指向历史证据。 |
| `protocol_fingerprint_har_analysis.md` | `reference/protocol-fingerprint-har-analysis.md` | 保持代码引用一致，同时移动 `protocol_har_summary.json` 到同目录。 |

新增 `workflows/account-operations.md`，以 2.2 为依据说明任务类型、durable run、
取消、恢复、兼容投影和“账号状态/执行状态”边界。它替代散落在任务中心、优化和
账号认证设计中的当前操作说明，不复制页面实现细节。

### 4.3 历史文档包

以下材料保留内容、移动归档，并在顶部补一行“历史记录，不是当前实现依据”。

| 历史目录 | 迁入文件 |
| --- | --- |
| `history/2026-08-project-refactor/` | `admin-data-architecture.md`、`refactor-roadmap.md` |
| `history/2026-08-registration-design/` | `registration-implementation-plan.md`、`registration-parallel-workstreams.md`、`registration-refactor-master-design.md`、`registration-refactor-plan-index.md`、`registration-retry-progress-and-otp-design.md`、`registration-state-refactor-design.md`、`registration-test-migration-rollout.md`、`task-log-unification-design.md`、`unified-task-center-architecture.md` |
| `history/2026-09-account-auth-design/` | `account-auth-liveness-fingerprint-design.md`、`account-auth-liveness-fingerprint-implementation-design.md`、`account-auth-protocol-staged-rollout-checklist.md`、`registration-account-config-redesign.md` |
| `history/2026-09-optimization/` | `optimization-auth.md`、`optimization-config.md`、`optimization-maintenance.md`、`optimization-status.md`、`optimization-storage.md`、`optimization-tasks.md`、`optimization-token-refresh.md` |

`docs/superpowers/specs/` 和 `docs/superpowers/plans/` 保持原路径：它们是当时的设计与
执行输入，不重命名、不合并进当前指南。首页只提供索引和“历史规格/计划”的定位说明。

`ui-audit-2026-08-14.html` 迁入 `history/2026-08-project-refactor/`，作为视觉验收快照；
它不参与现行架构或流程判断。

## 5. 已判定的过期或误导性表述

1. `current-architecture.md` 的基线日期、代码规模、测试数量和 96 条路由均是历史快照；
   现行测试契约固定为 121 条路由，不能把旧统计继续标为“当前”。
2. `registration-refactor-plan-index.md` 的“未修改业务代码”和“Roxy + Protocol 仅同会话
   协作”的前提已不符合 dispatcher 的实际双驱动分发。
3. `unified-task-center-architecture.md` 和 `task-log-unification-design.md` 是迁移设计，
   不能当作已完成全量统一的事实；当前仍有 `registration_jobs` 与 `account_action_*` 的
   兼容/投影边界。
4. 账号认证三份设计中出现的 `ACCOUNT_TOKEN_REFRESH_DRIVER`、
   `ACCOUNT_AUTH_V2_ENABLED` 与 `protocol_v2` 是历史名称；当前公开配置以
   `OPENAI_PROTOCOL_VERSION` 和支持矩阵为准。
5. `optimization-status.md` 及同组文档含当时的性能、验收和并行工作记录；有审计价值，
   但不能当成当前测试结果或发布完成证明。

## 6. 实施与验证

1. 创建目录与首页；按上表用 `git mv` 移动已跟踪文档和参考 JSON/HTML。
2. 更新 README、AGENTS.md、代码注释和所有 Markdown 内部链接；不修改私有运行数据。
3. 重写四份当前汇总文档：当前架构、注册流程、账号操作、Codex operation；每个流程
   的入口必须可通过 `rg` 定位到现行函数。
4. 为历史资料补充统一的状态说明，不修改其中的原始设计结论、日期、验收数值或运行记录。
5. 运行 Markdown 链接/重复标题/绝对工作区路径检查，并执行文档引用相关的最小测试；
   对注册、账号操作、Codex 和路由契约分别做只读源码核对。
6. 检查 `git diff --check`、`git status --short` 和文档导航；不删除文件，不触及已有
   未跟踪的私有文件。

## 7. 非目标

- 不删除历史文档，也不删除 `docs/superpowers/` 内容；
- 不改动注册、账号、Codex、数据库、WebUI 或部署逻辑；
- 不重新执行真实注册、账号操作、PostgreSQL 迁移或服务重启；
- 不把历史测试/性能数据重新表述为本次验证结果。
