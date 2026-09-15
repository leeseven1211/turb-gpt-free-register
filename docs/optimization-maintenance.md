# 维护动作 durable operation 迁移（2026-09-14）

本阶段把账号维护动作的排队和执行边界接到共享
`core.operations.task_gateway`。PostgreSQL 的 `operation_tasks`/
`operation_runs` 是队列与执行状态事实来源；账号表仍保存查活、套餐、提链和
封号邮件扫描的业务结果。服务不再为 native operation 创建自己的消费者线程。

## 已迁移的 native 类型

| 类型 | 服务注册入口 | 资源族 | 业务写回 |
| --- | --- | --- | --- |
| `live_check` | `live_check_service.register_operation_handlers()` | `openai_interactive` | `update_account_liveness` |
| `token_refresh` | `live_check_service.register_operation_handlers()` | `openai_interactive` | `update_account_liveness` |
| `plan_check` | `plan_check_service.register_operation_handlers()` | `openai_interactive` | `update_account_plan_check` |
| `extract_link` | `extract_link_service.register_operation_handlers()` | `openai_interactive` | `update_account_extract` |
| `deactivation_mail` | `deactivation_mail_service.register_operation_handlers()` | `mailbox_scan` | `update_account_deactivation_mail` |

B 侧 runtime 导入这些 service 时，各模块会把上述 handler 注册到 shared
`task_gateway`；`core.live_check_service.register_maintenance_operation_handlers()`
同时作为显式的一次性注册入口。随后由 runtime 已有的共享启动路径启动唯一的
`task_gateway` dispatcher。注册函数不创建第二个 dispatcher；各服务的
`start_dispatcher()` 仅作为兼容的单服务启动入口，不能与 runtime 的共享启动同时调用。

提交入口仍保留既有 HTTP 返回字段（`accepted`、`busy`、`task_id`、`status`，
提链还保留 `future=None` 的兼容形状），并增加 `run_id`/`reused` 供任务中心
对账。重复请求使用 `idempotency_key` 时返回同一个 logical task/run；新建的
accepted 项不是 busy，只有账号资源冲突才返回 busy。没有幂等键的普通入口先用
账号表条件 claim，再写 durable Run；持久化失败会收口业务 queued 状态。

## handler 边界

共享 dispatcher 原子 claim Run 后才构造 `OperationHandlerContext`。handler 从
`context.run["data"]` 取排队 payload，从 `context.task_reporter`（服务中的
adapter 最终路由到该 structured reporter）写结构化事件；native task ID 不传给
legacy `TaskReporter`。账号操作在 `context.lease()` 内执行，安全检查点调用
`context.checkpoint()`，由 gateway 同时刷新 Run/账号 lease 心跳。业务表写回
成功后由 adapter 调用 `context.finish(...)`，handler 随后返回 `None`；未使用
adapter 的简单分支直接调用 `context.finish(...)`。

worker 重新从数据库读取 access token，排队请求中的 token 只用于兼容旧调用和
入口校验，不作为 native payload。普通配置值在提交时冻结为 payload；不会把全量
配置、凭据或配置来源写入 operation。显式代理 URL 不写入 durable payload，native
worker 按账号维护动作代理策略重新申请线路；这样重启恢复不会暴露或复用过期的
代理凭据。

AT 刷新和提链远端 job 创建都在真正跨出进程前调用
`ctx.remote_request_started(action, request_id=...)`。收到远端响应只记录
`response_received`；只有远端结果确认、业务表写回成功、再从数据库读回相同结果
这三个证据都为 true 时才记录 `confirmed`。任一异常、取消或进程恢复发现非
`rejected` intent 都保持 `request_unknown`，不会自动重放认证或远端提链创建；
Roxy 兜底只有在前一个认证请求得到明确拒绝后才允许开始新的 intent。提链 job
创建确认后，SSE 后续步骤仍由原 Run 继续；若后续步骤失败，Run 进入对账态而不
把已创建的远端 job 当作可安全重试的普通失败。

## 取消、未知结果与恢复

- queued Run 的取消由 operation 存储立即收口；handler 在申请线路、网络请求前和
  外部事件处理间检查取消，不会在取消后继续申请新资源或写成功结果。
- 共享 gateway 负责跨进程 claim、lease heartbeat 和 execution/lease fence。
  lease 丢失时不重做可能已经提交的远端动作，而是保留待核验结果。
- AT 刷新只在远端确认成功后写回 Token。协议/回调返回
  `request_unknown`、密码结果未知或 OAuth callback 未确认时，账号状态保留
  `request_unknown`，Run 收口为 `attention_required`，只提供人工 reconcile；不
  自动重复注册、写密码或再次提交认证。
- 提链在远端 job 已创建后若取消或事件流失去确认，同样保留
  `request_unknown`/人工对账，不把链接类型静默记为普通失败。
- queued native Run 可跨进程、跨 WebUI 重启继续；B 侧启动恢复需要排除仍有有效
  native lease/心跳的 Run，并按 task type 路由 native retry/cancel。旧的
  `recover_interrupted_*` 和旧消费者不能处理 native active Run，以免重复执行。

定时扫描（封号邮件）和其他 scheduler 仍只负责发现到期账号并调用 enqueue；
真正执行始终由共享 durable dispatcher 完成。iCloud HME 不再为每个 alias 各起
一次完整共享邮箱检索：一次 `enqueue_bulk` 会写入一个 `deactivation_mail` durable
协调 Run，handler 持真实账号的 `mailbox_scan` lease，调用
`scan_hme_deactivation_bulk` 一次，再按 alias fanout 业务写回和结构化事件。没有
独立的 HME 队列或消费者；协调 Run 的 queued/running/terminal 状态负责重启恢复，
取消和部分失败结果逐账号落库。

## 有意保留的兼容边界

注册流程中的 `check_registration_account_plan()` 需要复用注册 worker 已持有的
同一条代理租约，因此仍是同步 inline 查询和 legacy 任务投影；它不是 standalone
maintenance enqueue，注册代理负责继续收口这条路径。`codex_token_refresh`、
账号配置补跑和注册续跑也不在本阶段迁移范围。

## 回归覆盖

专属 `tests/test_maintenance_durable_gateway_phase2.py` 使用
`PostgresTestCase` 的全新 schema，覆盖：真实 native handler terminal 与账号表
写回、并发账号 claim、重复 idempotency key、queued 重启恢复、取消不执行、AT
刷新 response/confirmed 与异常结果的 `attention_required`、提链远端 job intent
的 response/confirmed/异常、重新读取数据库 token、封号邮件 native 扫描、HME 多
alias 一次 bulk 检索后的逐账号写回/取消/部分失败，以及
legacy task/executor/reporter/HME consumer 的调用边界。
