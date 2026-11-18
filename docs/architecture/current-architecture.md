# 当前项目架构

> 本文只描述当前代码的稳定边界；代码规模、测试耗时和历史改造记录不作为架构事实。
> 发生冲突时以代码、配置 schema、数据库表定义和测试契约为准。

## 1. 运行形态与入口

项目以 PostgreSQL 为运行时事实来源，业务模块共享同一核心层。当前源码提供
`combined`、`web`、`worker` 三种显式模式，生产服务尚未切换到双进程：

```text
CLI main.py
  -> standalone 执行 owner 与原有任务许可
  -> main.run_registration（兼容门面）
  -> core.registration.dispatcher.run_registration

WebUI web.py（默认 combined，兼容原命令）
  -> PostgreSQL 启动检查
  -> core.runtime.assembly.install
  -> webui.app.create_app
  -> 按领域注册的 Flask Blueprint
  -> core.runtime.process.start_runtime
  -> app.run 接收请求

WebUI web.py --mode web
  -> 配置观察、持久受理、查询和任务控制
  -> 不持有执行 owner，不启动业务执行线程
  -> --server flask（默认）或 waitress（固定 3.0.2）

worker.py
  -> 同一 runtime 组合根
  -> 执行 owner、恢复、handler、dispatcher、周期任务与资源收尾
  -> 不组装 Flask 或 HTTP listener
```

`webui.app.create_app()` 只组装 Flask 应用、鉴权、请求级依赖和 Blueprint；启动恢复、
长任务 dispatcher 与周期 worker 由 `core.runtime` 的显式生命周期装配，
`webui.runtime.start_runtime()` 保留兼容委托。`/healthz` 提供 liveness，`/readyz`
同时检查数据库、配置应用、执行组件和 Worker 心跳；Web 没有可用 Worker 时不就绪，
已成功持久化的提交仍可排队。

同一主机实例的 Web/Worker 使用相同代码版本、数据库/schema、实例 ID、加密主密钥和
稳定绝对运行目录。`combined` 与 `worker`、需要执行的独立 CLI 共用文件锁和 PostgreSQL
专用 session advisory 锁；心跳过期本身不释放 owner。失去 owner 或配置观察异常时停止
新执行准入，已受理 Task/Run 与执行证据保留。关闭过程先停生产者和抢占，再排空任务、
关闭执行器、收口投影/资源/兼容导出，最后关闭连接与 owner；超时明确返回失败。

`core.runtime.http_server` 拥有单进程 Waitress listener、实际工作线程、响应资源和有界排空；
Web 先停止 HTTP 准入并完成排空，再关闭 runtime。未完成排空返回失败，不能以 dispatcher
的布尔返回值代替真实线程/资源退出。`tools/manage_runtime.py` 与 `webui.sh` 的显式角色
命令通过 PID、启动时间、目录、release/instance 和 listener 归属绑定本机进程；
`tools/check_runtime.py` 只读已有状态，不初始化表或执行恢复。服务示例和切换规则见
[分进程运行说明](../deployment/split-runtime.md)，模板尚未安装，生产服务未切换。

普通PG连接池按实际连接参数分别计数，默认每池12不是进程/实例总上限；专用owner连接与
只读probe另计。本批F18只验证当时实际装配的4池键饱和、默认10秒PoolTimeout、owner/probe
独立与释放后恢复，不承诺未来池键、SQL锁等待或全数据库中断；分项证据见[本批验收](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/parallel-a-20261116/batch-current-acceptance.md)。

心跳本地health/admission使用timeout epoch保护：在timeout前已开始的旧pulse不能以迟到成功
清除heartbeat原因，后续及时成功pulse才恢复；pending状态独立于展示错误，避免反复超时检查
饿死恢复。它不取消在途SQL或修改持久readiness协议，PG已保存ready字段不能单独替代本地
执行准入。最小修复、新runtime v4回归及真实Worker/PG F19加速时钟验证已通过：旧pulse迟到
返回和新CAS提交但尚未返回期间均保持本地gate，后续及时成功返回才恢复，原Run单次成功。
该验证中durable PG ready在本地被阻挡期间实际仍为true；它不证明默认20秒墙钟时序或数据库
中断。完整故障/容量验收与实际部署切换仍未完成。分项实现和运行验收的最新边界见
[架构收敛第 12 节](convergence.md#12-邮箱代理与-runtime-a1-并行批次2026-11-16验收收口中)。

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
main.py / web.py / worker.py
  -> CLI 兼容入口与显式进程生命周期
```

`core/` 不反向依赖 `webui/` 或 CLI。路由不得直接重写业务状态机；配置的公开字段以
`config/schema.py` 为准，页面编辑器和所有入口必须共用相同的配置语义。

WebUI 只维护现代界面：主模板为 `webui/templates/index.html`。总览、注册、任务中心、Codex 凭证、
账号资产、批量任务、配置、邮箱、代理、提链工作台与独立提链统计使用 `frontend/` 中的 Vue 3 / TypeScript 模块，按需加载
`webui/static/task-center/` 构建产物；现有导航外壳通过薄桥接调用模块，页面不共享任务
筛选 DOM 或分页状态。配置页只有一个草稿/保存 owner，旧全局配置仅接收已保存字段投影。
邮箱 owner 拥有来源、库存/历史查询与选择、原请求导入和回执；本地粘贴不触发远端领取，
已受理写入不会因页面隐藏或共享刷新失败而重放。代理 owner 拥有三表独立分页、共享筛选、
轮询和冻结只读详情；公开关联 ID 通过共享解码器保留精确十进制值。两页旧脚本只保留
显式导航桥接，弹窗关闭、滚动锁和可见性由所属生命周期管理。
总览 owner 拥有能力可见性、卡片数据、布局和轮询；注册 owner 拥有批次、查询、动作回执与日志读取，
执行驱动仍归核心注册模块。提链工作台 owner 拥有主列表、缓存和批次选择，候选创建与详情/支付
分别有明确的页面内生命周期；统计拥有独立读取范围。页面隐藏会失效读取，已受理写入保存原回执，
新的明确提交使用新身份，未知提交的显式重试沿用原身份。公开 job、Task、Run 和 batch 标识精确解码，
注册任务兼容地址 `#register/tasks` 可从配置动作、直接链接和历史恢复进入。
新迁移页面的懒加载由 `shared/page-bridge.js` 处理；共享原生弹层管理位于
`frontend/src/shared/useNativeDialog.ts`，账号旧查活日志和二维码入口由 `shared/modal-compat.js` 兼容。
外壳导航、兼容脚本和样式仍位于
`webui/static/js/pages/`、`webui/static/js/shared/` 与 `webui/static/css/`。迁移边界、接口类型源与后续顺序见[架构收敛](convergence.md)。旧 `?ui=legacy` 链接和
`ui_mode=legacy` Cookie 均返回现代页面；相关路由兼容检查属于现代界面的入口验收。

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
  -> 按配置选择 Roxy 或 protocol_oss_2 注册驱动
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

新原生 operation 与 `account_action_*` 兼容来源并存；后者会按来源投影到 operation 表，
不能把“统一列表”误解成旧表已经删除。详见[账号操作](../workflows/account-operations.md)。

任务中心读取路径为 `Vue 页面 → API client → /api/operations → core.operations.query_service → 仓储`。查询服务拥有公开状态、分类错误、能力附加及 revision 编排；HTTP 层保留参数转换与响应。任务重跑、取消、终止和隐藏的业务选择及批量结果聚合由 `core.operations.action_service` 拥有；HTTP 路由只解析输入、传递幂等键并序列化响应。既有受管批次优先、注册 / Codex / 历史账号任务回退和 Task/Run 状态机保留。

任务列表兼容GET仍可请求facets与batches；当前Vue客户端的批次参数始终为0。带
include_facets=1/include_batches=1的元数据基准保留兼容读取成本，不代表每次Vue请求。
不同账号基数的同机顺序测量若未控制cache、未做paired A/B，只描述各自观察值，不将差异
全部归因基数或Web/Worker隔离。本批30万/50万各8场景30次Web-only读测的实际结果与
多秒尾延迟、资源采样限制见[两档读测汇总](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/parallel-a-20261116/runtime/scale-read-results.md)；
该结果不是Worker吞吐、公平性或生产容量证明。

账号操作的配置快照捕获、执行字段映射和补全能力组合由 `core.accounts.operation_settings` 维护，配置 schema 和默认值仍由 `config` 拥有。WebUI 和 `operation_coordinator` 的旧配置入口只委托该模块；批量 catalog / adapters 使用其公开入口。账号缺项规划由 `completion.py`、提交及既有持久来源常量由 `operation_coordinator.py` 负责。

账号 setup / completion 的执行由 `setup_execution.py`、`completion_execution.py` 拥有；回执、本地读回和终态适配由 `operation_results.py` 拥有；父子任务续接及共享 executor 提交由 `completion_dependencies.py` 拥有。核心模块不依赖 WebUI。`core.accounts.operation_handlers` 拥有唯一 handler 注册锁 / 状态和历史注册续跑兼容 handler；`webui.runtime` 保留旧函数的同签名委托。持久来源 `webui_runtime` 沿用原值，文件迁移不迁移历史任务。Web 装配任务控制动作目录；实际执行 handler、恢复和 dispatcher 由执行进程装配。

旧 `/api/account-tasks` 列表与详情也由 `query_service` 组装公开响应，但继续通过 `core.account_task_store` 读取旧任务模型。旧 ID、过滤参数、状态、刷新配置和错误响应保留；统一查询拥有者不等于合并新旧模型或删除兼容入口。

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

执行进程启动时，`core.runtime.manifest` 显式列出存储、配置观察、handler、恢复及各 worker
的装配顺序；必须先获得 owner 才执行这些回调。`core.operations.reconciliation` 拥有启动 /
周期恢复编排及旧模型行级排除规则；`task_gateway` 保留 dispatcher / dependency 线程与
恢复节流状态。注册和兼容账号任务恢复会避开已能确认继续语义的账号 / 来源，恢复只收口
运行状态或重新派发安全的 queued 工作。

统一任务仓储的真实实现按职责划分：`common.py` 维护连接 / 序列化 / 状态归一工具，`schema.py` 独占初始化锁与就绪状态，`runtime.py` 拥有 Run 生命周期、资源 / 回执 / 依赖事务，`recovery.py` 拥有失联恢复与行级排除查询，`projection.py` 拥有旧模型同步、批次统计、持久投影队列与唯一投影线程。`store.py` 保留列表 / 详情 / 进度 / 历史维护和同签名兼容委托，不再保存另一份运行写入或投影实现。跨模块的事务 cursor 继续由原调用链持有，锁序和原子终态不拆散。

存储 schema、隔离测试和兼容导出规则见[存储架构](storage-architecture.md)。

## 5. 兼容入口

新代码使用真实实现路径；下列旧入口仍为外部脚本、历史调用和测试保留。

| 入口 | 真实实现 | 保留原因与删除条件 |
| --- | --- | --- |
| `core.roxy_registration` | `core.registration.roxy` | 旧导入路径；确认至少一个稳定版本无源码、工具或部署脚本依赖，并完成导入兼容检查后删除 |
| `core.db` | `core.storage.db_legacy` | 业务、工具和测试仍使用的存储门面；全部切换领域仓储并完成字段对账后删除 |
| `core.operation_task_store` | `core.storage.operations.store` | 任务中心旧导入与测试 patch 点；调用全部切换并完成观察期对账后删除 |
| `core.account_task_store` | `core.storage.operations.legacy_task_store` | 仍在写入的旧账号任务模型；原生 operation 覆盖全部任务类型至少一个稳定版本后评估删除 |
| `main.run_registration` | `core.registration.dispatcher.run_registration` | CLI 与外部调用门面；调用全部切换 dispatcher 后删除 |

五个 `core` 旧入口通过 `sys.modules` 绑定真实实现模块，保持锁、缓存和 patch 点的对象唯一性，
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
- 测试进程/锁/连接释放与测试数据删除分别记账；有意保留的合成schema/CSV仍是复现材料，不能称已清理数据。
- 账号、密码、Token、Cookie、OTP 和含凭据代理不得进入普通日志、任务事件、文档或提交。
- 当前文档维护现行使用、架构与开发规则；过期方案、迁移记录和一次性验收结果通过 Git 历史追溯。
