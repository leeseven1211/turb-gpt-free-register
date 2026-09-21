# 当前项目架构

> 核对基线：2026-09-21。本文只描述当前代码的稳定边界；代码规模、测试耗时和历史改造
> 记录不作为架构事实。发生冲突时以代码、配置 schema、数据库表定义和测试契约为准。

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

当前路由数量和 URL/方法/endpoint 摘要由
[`tests/test_route_contract.py`](../../tests/test_route_contract.py) 固定为 **121** 条；不要把
历史路由数量或 `len(app.url_map)` 当作发布契约。

## 2. 分层边界

```text
config/
  -> 配置默认值、schema、环境变量加载和热重载快照
core/
  -> 注册、账号、Codex、邮箱、代理、任务、存储与外部客户端
webui/ routes/
  -> 参数校验、服务调用、响应序列化、现代版/兼容版界面
main.py / web.py
  -> CLI 兼容入口与 Web 进程生命周期
```

`core/` 不反向依赖 `webui/` 或 CLI。路由不得直接重写业务状态机；配置的公开字段以
`config/schema.py` 为准，页面编辑器和所有入口必须共用相同的配置语义。

现代与兼容版 UI 同时存在：模板位于 `webui/templates/`，脚本和样式位于
`webui/static/js/{modern,legacy}/` 与 `webui/static/css/`。涉及路由契约、模板或配置页时，
两套 UI 都是同一功能范围的一部分。

## 3. 主要业务流

### 注册

```text
POST /api/jobs
  -> core.registration_service.submit_registration
  -> registration_jobs（pending）+ ThreadPoolExecutor
  -> _run_one_job 的数据库条件抢占
  -> 网络租约、邮箱来源/邮箱领取或恢复
  -> core.registration.dispatcher.run_registration
  -> Roxy 或 Protocol 驱动
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

Codex 补跑由 `core.codex_operation_service` 创建或重跑原生 operation，再调用
`core.codex_oauth.run_codex_oauth`。实际凭证保存、callback 确认、资源台账和失败后的
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

存储 schema、隔离测试和兼容导出规则见[存储架构](storage-architecture.md)；兼容门面及
删除前提见[兼容入口清单](compatibility-inventory.md)。

## 5. 维护规则

- 代码改动先用最小相关测试验证，再按存储、运行时和发布风险扩大范围。
- 数据库测试必须使用独立测试库或 schema，不能连接生产库或使用 `public` schema。
- 账号、密码、Token、Cookie、OTP 和含凭据代理不得进入普通日志、任务事件、文档或提交。
- 当前资料只说明已核验的现行行为；方案、迁移记录和一次性性能结果移入
  [`docs/history/`](../history/)。
