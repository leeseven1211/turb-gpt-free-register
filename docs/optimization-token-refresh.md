# Codex token refresh durable operation

本阶段把 Codex `refresh_token` 旋转从进程内 `_IN_FLIGHT`/直接 executor
提交迁移为 PostgreSQL `operation_tasks`/`operation_runs`。实现位于
`core/codex_token_refresh_service.py`；不创建第二个 dispatcher，也不把
native `task_id` 交给旧 `TaskReporter`。

## 调度与入口

`enqueue_refresh()` 是唯一提交入口。它校验凭证、registered account 和
`openai_interactive` lease 资源族，生成稳定幂等键，并优先调用 B 的：

```text
register_operation_handler(
    "codex_token_refresh", handler, source_systems=("native_operations",),
    config_allowlist={"request_timeout": "CODEX_REQUEST_TIMEOUT"},
)
submit_durable_operation(..., dispatch=True)
```

`enqueue_refresh()` 提交时取得 C 发布的 `config.non_sensitive_snapshot()`
`ConfigSnapshot`，不会手造逐字段配置 dict；gateway 再按上述 allowlist 投影，
因此任务只保存 `request_timeout` 和该对象的 `config_snapshot_revision`。执行
handler 使用已落库的这份版本化快照，不回读提交后的可变配置。

`start_periodic_refresher()` 和 `resume_queued()` 只注册 handler、唤醒共享
gateway 或读取 queued 数量。定时线程只负责发现到期凭证并生产 durable
任务；claim、账号 lease、executor 预算、handler 调用和 terminal result
由共享 gateway 负责。每个周期 producer 还必须先调用
`operation_runtime_store.list_reconciliation_accounts(task_type=..., account_ids=...)`；
本次候选的本地 account id 按有限批次完整查询，返回的账号一律跳过。任一批次
查询失败也 fail-closed，不能用“凭证 marker 已清空”推断上一次 remote-write
没有待核验。

B 的 runtime 启动顺序应在完成通用 runtime recovery、启动共享 dispatcher
后调用 `start_periodic_refresher()`。手动 route 继续调用
`enqueue_refresh(filename, trigger=...)`；停止 route 调用
`request_cancel(run_id=...)`，不要把 legacy `account_action_tasks` 的 task
ID 或 `TaskReporter` 传入 token refresh worker。

任务 data 只保存凭证文件名、资源族和必要的旧 batch 兼容标识；`reconcile=True`
不会被保存为授权标志。当前可持久化的配置只有非敏感 request timeout；client
identity、token endpoint 和任何 credential 不进入任务 payload 或 terminal
summary。

## 一次 refresh attempt

handler 取得 gateway context/lease 后按以下顺序执行：

1. 在远端调用前写凭证行 `oauth_refresh_error=request_pending`，并写入
   `refresh_request_dispatched` checkpoint/event。
2. 调用 `ctx.remote_request_started(action="codex_token_refresh",
   intent_kind="remote_write", request_id=..., detail=...)`。这是 restart
   reconcile/fencing 的持久 remote-write intent；handler 只依赖这一套
   gateway context，不另建 resource、dispatcher 或 claim 实现。
3. refresh grant 本层只发送一次。HTTP 返回先记录非终结
   `received`（`accepted` 是兼容别名）观测；明确拒绝才可记录终结
   `rejected`，传输未知记录 `unknown`。响应 body、access token、refresh
   token 不进入 receipt/resource detail。
4. 远端响应后不再以取消检查打断 credential write。此处只做 lease/fence
   心跳确认；用户取消会保留在运行记录中，但不打断 settling。随后写入新
   credential 并 readback 校验 access/refresh pair，再调用
   `remote_request_receipt(outcome="confirmed")`，最后完成 gateway `finish`。
   只有这一步之后才发布 success `result_summary`；写/readback/receipt 任一
   未知都保留 `started`/`unknown`，绝不写 `confirmed`。若 lease/fence 已丢失，
   不越权写本地凭证，保留 request_unknown/reconciliation 所需的已授权持久
   记录。durable handler 会把行级
   `oauth_refresh_error` 清除延后到 gateway terminal finish 之后；这是因为
   既有 credential upsert 会在写入时重建并清空该字段。旋转 proof 使用不含
   secret-like key 的 `credential_persisted` 与 `credential_rotated` 元数据。
5. sub2api 同步是独立的后置副作用；同步失败只记录 `sub2_sync=failed`，
   绝不会再次发送 refresh grant。

## Unknown / recovery 边界

网络 timeout、连接异常、408/409/425/429、5xx、无效成功响应和远端响应后
的本地 credential/metadata/terminal writeback 异常，都不能归为普通 failed
再自动 refresh。它们落为：

```text
outcome=request_unknown
reconcile_required=true
needs_reconciliation=true
next_action=manual_reconcile
retryable=false
```

credential row 同时保留 `request_unknown: needs_reconciliation` marker；后续
periodic producer 对 `request_pending`、`request_unknown` 或
`needs_reconciliation` 一律跳过。当前没有可证明的远端与本地核验凭据时，
即使传入 `reconcile=True` 也返回 `NEEDS_RECONCILIATION` 且不创建 refresh
operation；明确的 invalid grant/401 会进入
`reauth_required`，不自动重发。

进程在 `request_pending` 后崩溃时，正常异常 handler 没有机会运行。因此
不能只依赖 worker 的 `except`：B 的 generic recovery 必须读取同一 operation
run 的 remote intent/receipt。`started`、`received`/`accepted`、`unknown`
以及“已 `confirmed` 但 terminal finish 尚未完成”的 `remote_write` attempt
都不能产生普通 `interrupted -> retry`：前者必须保留为
`attention_required`/`request_unknown`/`reconcile_required`，后者只能补终态
或进入人工 reconcile，绝不能再次 refresh。只有明确 `rejected` 才可按 B 的
通用规则重试。恢复后本 service 的 producer 仍会检查 credential marker，
避免全局 recovery 把 token 旋转未知状态绕回下一轮 refresh。

terminal `finish` 也必须带 execution/lease fence 并幂等。如果 credential 已
写成功而 summary/finish 写回失败，必须留下 unknown/reconcile fencing；不能
因为“token 可能已成功”而重新提交 refresh。B handler 支持两种合法形式：
返回 `OperationResult`，或 `ctx.finish(result)` 后返回 `None`。

## B gateway 集成要求

正式 gateway 需要提供以下 context 能力（方法内部负责持久化到同一
`operation_runs.data`，并验证 execution/lease owner）：

```text
ctx.remote_request_started(
    action, intent_kind="remote_write", request_id=None, detail={...}
)
ctx.remote_request_receipt(
    outcome="received" | "accepted" | "confirmed" | "rejected" | "unknown",
    action, request_id=None, detail={...}
)
```

`request_id` 可以是 provider request id；OAuth endpoint 没有 request id 时，
adapter 使用不含凭证的公开 correlation UUID。recovery 查询最新 intent /
receipt 时必须使用 run 的 execution/lease fence；旧 worker 不能覆写新 attempt。
`received`/`accepted` 只代表 HTTP/远端响应已观察，`confirmed` 必须同时带
`remote_result_confirmed=true`、`local_business_writeback_confirmed=true` 和
`local_readback_confirmed=true`（业务层同时记录
`credential_persisted=true` 与 `readback_confirmed=true`）；`unknown` 表示禁止
自动 refresh。`request_id` 由 intent 与每个 receipt 严格匹配；未知 intent
不能被下一次请求覆盖。

定时 producer 的共享 fence 查询为：

```text
operation_runtime_store.list_reconciliation_accounts(
    task_type="codex_token_refresh",
    account_ids=[...],
    source_systems=("native_operations",),
)
```

producer 会把本轮候选 `account_ids` 分批调用上面的接口并合并结果，不能依赖
不完整的全库 `LIMIT` 结果；任一批查询异常即本轮 fail-closed。接口必须覆盖未终结
remote-write 的 `started`、`response_received`、
`local_commit_required` 和 `confirmed`，而明确 `rejected` 不应阻止下一次
安全重试。该查询只读，不 claim、不提交任务。

B runtime/routes 的注册需求：共享 dispatcher 只启动一次；runtime 在 recovery
后调用 `start_periodic_refresher()`，manual/bulk route 调用
`enqueue_refresh()`，cancel route 调用 `request_cancel()`；不要启动旧 token
consumer，不要把 `task_id` 映射回 legacy `TaskReporter`。`reconcile=True` 目前
仅保留 API 兼容性，不能绕过 unknown marker、durable fence 或创建新的 refresh
grant；人工动作必须先由独立核验流程证明远端与本地凭证状态，再提供明确的
follow-up handler。

## 验证

测试通过隔离 launcher 运行，使用独立 `turb_opt_20260914` 数据库；所有远端
HTTP 都是 synthetic mock，不读取真实账号/token，不运行生产 dotenv：

```bash
/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python \
  /tmp/turb-optimization-20260914.mJ7Y6R/run.py \
  /Users/lihongwei/code/personal/gpt/turb-gpt-free-register-opt-token-phase2-20260914 \
  -m pytest -q tests/test_codex_token_refresh.py tests/test_codex_token_refresh_durable.py
```
