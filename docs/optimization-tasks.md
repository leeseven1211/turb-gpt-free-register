# 任务可靠性优化（2026-09-14）

本轮只做可审查的增量：保留 `account_action_*` 兼容写模型和原生
`operation_*` 模型，不在一个版本内切换全部任务。PostgreSQL 是队列、Run、
依赖和恢复状态的事实来源；进程内集合只做去重和唤醒优化。

## 已实现阶段

### 1. Durable dispatch 与全局并发预算

- `AccountOperationExecutor` 在 pool generation 之外维护 accepted/active
  计数。配置热更新保留旧池排空，但新旧池共享同一
  `ACCOUNT_BATCH_WORKERS` budget，不会叠加总并发。
- `try_submit()` 是非阻塞的有界提交接口。持久 dispatcher 没有空位时不等待、
  不占账号租约，把队列行放回数据库等待下一轮。
- `operation_runs` 继续由数据库 CAS 认领，启动恢复只收口心跳过期且没有其它
  worker 有效账号 lease 的 Run；WebUI 启动不会打断仍由其它 worker 持有有效
  lease 的 Run。
- gateway 的 `register_dispatch_handler(task_type, handler, source_systems=...)`
  注册按任务类型的执行器。`start_dispatcher()` 持续扫描所有已注册类型的
  durable operation queue，而不是把循环写死成 Codex；默认只消费
  `native_operations`，迁移完一个兼容来源后再显式放开该来源，避免双跑。

### 2. 补全父子依赖

- `operation_task_dependencies` 用 source system/id 表达 legacy 父任务和 native
  子 Run，注册、ready、claim、ack 都是幂等的数据库状态转换。
- `drain_ready_dependencies()` 只读并唤醒，不 claim。唯一 claim owner 是
  `operation-dependency-dispatcher`；收到通知也只唤醒同一个持久扫描器，避免
  “drain 先 claim、handler 再 claim”丢失续接。
- 扫描器每轮有限读取 ready 行并调用 runtime 的非阻塞提交回调；回调通过共享
  `AccountOperationExecutor.try_submit()` 执行，不在 child worker 栈同步执行
  `_run_account_completion_worker`。
- 并发满或执行异常时，依赖回到 `ready` 并写入 `next_attempt_at`（短退避）；
  不使用每行 `threading.Timer`。启动时会把超时的 running claim 恢复为 ready，
  供下一轮重新 claim。
- 子任务终态和业务任务落库都完成后才收口父任务；等待中的父 coordinator 不
  占用账号操作 lease。已确认的远端未知结果仍保持待对账，不会自动重复注册、
  重复写密码或重复授权。

## 对外协作接口

### Phase 2 durable handler helper

维护动作迁移统一复用 `core.operations.task_gateway`，不为每个服务创建线程池或
自己的队列消费者。提交方只负责持久化一次逻辑任务/Run：

```python
task_gateway.submit_durable_operation(
    task_type="live_check",
    account_id=account_id,
    email=email,
    source_system="live_check_service",
    source_id=stable_source_id,
    idempotency_key=stable_request_key,
    config_snapshot=snapshot,
    config_allowlist={"driver": "ACCOUNT_LIVE_CHECK_DRIVER"},
)
```

`source_system + source_id` 是旧来源到统一任务的幂等映射；同一请求重复提交返回
`reused=True`，而新创建且已接受的排队项始终是 `accepted=True, busy=False`。只有
复用中的活跃 Run 或数据库账号资源冲突才返回 `busy=True`。配置代理仍由调用方注入，
helper 只读取 C 的 `revision/values`、递归解冻 immutable mapping，并保存显式
allowlist；不会把 `sources` 或全局配置写入任务。

handler 注册为：

```python
task_gateway.register_operation_handler(
    "live_check", handle_live_check,
    source_systems=("live_check_service",),
)
```

`handle_live_check(context)` 只在共享 `AccountOperationExecutor` worker 中收到已由
数据库 CAS 认领的 `context.run`。`context.task_reporter.report/stage/note` 写结构化
事件；`context.lease()` 申请账号 lease，`lease.heartbeat()` 或
`context.checkpoint()` 刷新 lease 与 Run 心跳；finally 自动释放 lease。handler 必须
先确认业务表写回，再 `return OperationResult.success(...)` 或调用
`context.finish(...)`。结果未知用 `OperationResult.request_unknown(...)`，数据库记录
为 `attention_required` 并只提供 `reconcile`，不会自动重复密码、注册或 OAuth 写入。
每个 terminal 写入带 `execution_id` fence；lease owner 不匹配的旧 worker 不能覆盖
当前结果。暂时拿不到 lease 时 Run 有界回到持久队列，远端边界已可能发生或 lease
心跳丢失时则保留 `request_unknown`，不重做远端动作。

### Remote intent / receipt 崩溃契约

所有可能改变远端或本地凭证/账号状态的 handler，必须使用同一个持久检查点，不能
只写 logger，也不能由每个 service 自己造 SQL：

```python
ctx.remote_request_started(
    action="codex_token_refresh",
    intent_kind="remote_write",
    request_id=correlation_id,
    detail={"checkpoint": "refresh_request_dispatched"},
)
# HTTP response 到达时只记录非终结回执：
ctx.remote_request_receipt(
    outcome="response_received",
    action="codex_token_refresh",
    request_id=correlation_id,
)
# 只有远端结果、本地业务写回和本地 readback 都成功后才能这样记录：
ctx.remote_request_receipt(
    outcome="confirmed",
    action="codex_token_refresh",
    request_id=correlation_id,
    detail={
        "remote_result_confirmed": True,
        "local_business_writeback_confirmed": True,
        "local_readback_confirmed": True,
    },
)
```

`received`、`response_observed`、`accepted` 会规范化为
`response_received`；当远端可能已接受而本地提交尚未完成时可使用
`local_commit_required`。`confirmed` 的三个证明字段是公共 helper 的强制校验，
绝不能因为 HTTP 200 就直接填写。`rejected` 只适用于明确确认远端没有应用写入的
拒绝；其它异常用 `unknown`。receipt 不会自行把 Run 变成终态，handler 仍须在
业务持久化和 readback 后调用 `context.finish()`。

恢复时，只要 stale `remote_write` 的 receipt 不是明确 `rejected`（包括
`started`、`response_received`、`local_commit_required`、`confirmed`），Run 会进入
`attention_required`，结果为 `outcome=request_unknown` 并只提供 `reconcile`，禁止
自动重做密码、MFA、Token、注册或 OAuth。`execution_id` 与 lease token 同时参与
检查点和终态 fence；旧 worker 的 receipt/finish 不能覆盖新执行。纯读取
`intent_kind="read"` 不占账号写 lease，但仍建议在需要解释异常时记录 receipt。

### 配置代理 C

Codex operation 优先调用：

```python
config.schema.non_sensitive_snapshot()
# -> ConfigSnapshot(values, sources, revision)
```

`ConfigSnapshot.__slots__` 是 `revision`、`values`、`sources`；服务读取
`revision`，通过 `as_dict()`/递归 thaw 复制冻结值，再将 C 的大写 schema key
显式投影为既有执行字段。任务只保存 `oauth_driver`、`auth_source`、
`sms_provider`、`sms_country`、账号动作代理模式及 `config_snapshot_revision`，
不保存全量 schema 或 `sources`，也不定义配置字段。`same_as_registration` 会在
快照内解析 `REGISTRATION_DRIVER`，旧的 `ACCOUNT_ACTION_PROXY_MODE` fallback
仍保留。`set_config_snapshot_provider()` 继续作为测试/滚动集成边界；当前
checkout 没有该模块时才使用旧配置读取兼容路径。

### 发布/health 代理 E

`webui.runtime.runtime_status()` 是只读、无账号/Token/代理内容的状态结构：

```text
{
  ready, started, pid, started_at,
  executor,
  codex_dispatcher,
  dependency_dispatcher,
  projection_worker,
}
```

其中 `executor` 提供 budget/accepted/active/available/generation，三个 worker
状态提供 `started/alive/name`。health 路由可以按自身策略把 `ready` 与组件
`alive`、数据库探活组合，不应把这些状态写回数据库。

### 认证代理 D

本轮没有修改 `core/codex_retry_service.py`。补全续接只依赖其现有外层契约：
`run_twofa_worker(..., manage_task=False, steps=...)`；账号密码/MFA 的 HTTP 回应
也只能记录 `response_received`，必须在业务表写回和 readback 后记录上述
`confirmed`。Codex 子操作仍通过 `codex_operation_service.submit()` 入 durable
队列。若认证代理改动这些签名，需要在 runtime 外层适配，不要让 gateway 直接
调用认证内部实现。

## 已覆盖回归

- 两代线程池热更新的总 active 数不超过全局 budget。
- 原生任务同一 idempotency key 不重复创建逻辑任务/Run。
- ready drain 不重复 claim；单一 scanner claim 后第二轮不重复；超时 running
  claim 可在模拟重启后恢复并再次 claim。
- 父任务从 waiting 在 child terminal 后自动推进；waiting coordinator 不阻塞
  同账号 child。
- 有效其它 worker lease 保留，孤儿 Run 才会被启动恢复收口。
- gateway handler 按 task type/source 过滤，兼容未迁移来源不会被原生 handler 双跑。

## 尚未迁移的任务类型

本轮只把 Codex 原生 Run 接入通用 dispatcher，并完成补全依赖基础设施；以下
兼容维护任务仍由各自 legacy queue/scanner 写入 gateway，再由 projection 对账，
尚未注册为 native gateway handler：

- `live_check` / `token_refresh` / `plan_check`；
- `deactivation_mail` / `extract_link`；
- `codex_token_refresh`；
- `account_setup_retry`、`password_setup`、`password_change`、`twofa_setup`、
  `twofa_change`；
- 注册后置动作及注册续跑的完整 native Run 执行器。

后续迁移每种类型时，应先提供其 native handler 和 source 迁移/去重证明，再
停止对应旧 scanner，保留 projection 对账和失败/重启回归；不能仅把旧线程名
改成 dispatcher。
