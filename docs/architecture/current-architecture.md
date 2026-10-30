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
  -> webui.runtime.start_runtime
  -> webui.app.create_app
  -> 按领域注册的 Flask Blueprint
```

`webui.app.create_app()` 只组装 Flask 应用、鉴权、请求级依赖和 Blueprint；启动恢复、
长任务 dispatcher 与周期 worker 只能由 `webui.runtime.start_runtime()` 在进程生命周期中
初始化。`/healthz` 提供 liveness，`/readyz` 同时检查数据库与 runtime 就绪。

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

WebUI 只维护现代界面：主模板为 `webui/templates/index.html`，业务脚本和样式位于
`webui/static/js/pages/`、`webui/static/js/shared/` 与 `webui/static/css/`。旧 `?ui=legacy` 链接和
`ui_mode=legacy` Cookie 均返回现代页面；相关路由兼容检查属于现代界面的入口验收。

`core/` 内按业务查找：`registration/`、`accounts/`、`codex/`、`email/`、`extract_link/`、`proxy/` 和 `sms/`；域内共用逻辑在各自根部，具体驱动或提供方在子目录。跨业务认证、浏览器、网络、任务和调度分别在 `auth/`、`browser/`、`network/`、`operations/`、`runtime/`，仓储集中于 `storage/<业务>/`。`integrations/` 放外部流程及 sub2api 客户端。

五种注册方式分别拥有 `registration/{roxy,roxy_oss,protocol,protocol_oss,protocol_oss_2}/` 目录。本地 Roxy 和 Protocol 当前保留完整 `__init__.py`，其他驱动仍保留现有复用关系。`core/` 根部只有包入口和五个模块兼容别名；新调用应使用真实实现路径。具体文件索引见 [README 项目结构](../../README.md#项目结构) 和[功能地图](functional-map.md)。

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
  -> 按配置选择五种注册驱动之一
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

新代码使用真实实现路径；下列旧入口仍为外部脚本、历史调用和测试保留。

| 入口 | 真实实现 | 保留原因与删除条件 |
| --- | --- | --- |
| `core.roxy_registration` | `core.registration.roxy` | 旧导入路径；确认至少一个稳定版本无源码、工具或部署脚本依赖，并完成导入兼容检查后删除 |
| `core.browser_use_registration` | `core.registration.legacy.browser_use.flow` | 已禁用入口的历史导入；稳定版本确认无外部调用后逐文件删除 |
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
- 账号、密码、Token、Cookie、OTP 和含凭据代理不得进入普通日志、任务事件、文档或提交。
- 当前文档维护现行使用、架构与开发规则；过期方案、迁移记录和一次性验收结果通过 Git 历史追溯。
