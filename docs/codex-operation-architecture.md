# Codex 补跑运行架构

## 结论

Codex 补跑只有一个业务入口：`core/codex_operation_service.py`。Web 单账号、Web 批量、
注册任务的 Codex 重试、任务中心重跑和 CLI 测试工具都只负责创建或重跑 operation；
OAuth 驱动不再自行维护“补跑中”集合、线程终止和成功状态。

```text
调用入口
  └─ codex_operation_service
       ├─ operation_tasks       一个可持续重跑的逻辑任务
       ├─ operation_runs        每次执行一行，run_no 递增
       ├─ account_operation_leases
       ├─ operation_resources   代理、接码等有生命周期资源
       └─ operation_events      结构化阶段、取消和终态事件
            └─ run_codex_oauth → protocol / roxy
```

## 不变量

1. 同一账号在 `openai_interactive` 资源族最多存在一个活跃 run。数据库部分唯一索引是
   跨进程事实，进程内集合不参与正确性。
2. 重跑不会覆盖历史。逻辑任务不变，新增 `operation_runs.run_no`。
3. 账号的凭证资产、当前执行和最近一次结果是三条独立状态轴：
   `codex_credential_state`、`codex_execution_status`、`codex_last_run_status`。
4. 旧凭证有效时，本次重新授权失败不能把资产降级为无效。
5. callback 回执不是凭证。只有实际 auth JSON 完成校验并写入 `codex_credentials`，本次
   run 才能进入 `success`。
6. 取消是 run 级协作式取消，不向 Python 线程注入异步异常。
7. 代理和接码资源必须登记并收口；终态仍为 `acquired` 的资源自动标记为
   `reconciliation_required`，不能静默消失。

## 运行状态机

```text
queued ──claim──> running ───────────────> success
  │                 │                     attention_required
  │ cancel          │ cancel              failed / deactivated
  v                 v
cancelled         cancelling ─checkpoint─> cancelled
                    │
                    └─callback 已提交──> settling ──> success / attention_required

进程重启：running / cancelling / settling ──> interrupted
```

- `claim_run` 原子认领数据库队列；多进程同时看到同一任务也只有一个能进入 `running`。
- 账号租约是第二层防护，用于资源族互斥与心跳。
- `settling` 表示 callback 已交给外部系统、正在有界确认真实凭证。此时即使用户请求停止，
  也必须先完成短时对账，避免把未知远端状态错误报告为完全取消。
- Web 进程启动时，失去 worker 的活跃 run 收口为 `interrupted`，排队 run 重新派发。

## 成功语义

本地 PKCE 模式在换取 token、解析并保存凭证后成功。CPA 模式在授权前记录现有远端凭证
内容指纹；callback 后按 `CPA_CREDENTIAL_CONFIRM_TIMEOUT` 有界轮询。只有下载到可用且
指纹不同的新 auth JSON，才保存并返回 `credential_confirmed=true`。

如果 CPA/sub2 仅返回“accepted”或本地只保存了 callback 回执，结果是：

```text
run.status = attention_required
codex_credential_state = pending_confirmation   # 没有旧有效凭证时
callback_submitted = true
credential_confirmed = false
```

回执路径只写入 `receipt_path`，不能冒充 `file_path`。

## 取消与阻塞调用

停止 API 把 `cancel_requested_at` 写入数据库，同时通知本进程 token。OAuth、页面等待、
接码等待和重试退避在安全检查点调用 `check_cancelled()` 或 `cancellable_sleep()`。

邮箱供应商等无法中断的第三方阻塞调用由 daemon 线程执行，operation worker 只轮询取消
token；用户停止后 worker 可以及时收口，但不会用 `PyThreadState_SetAsyncExc` 破坏库的
内部状态。接码激活在取消路径必须调用 provider cancel，并更新资源台账。

## 资源与崩溃恢复

`operation_resources` 至少登记：

- `proxy_lease`：执行结束在 `finally` 释放；
- `sms_activation`：短信成功标记 `completed`，换号或取消标记 `cancelled`；
- 未能确认释放的资源：`reconciliation_required`。

资源台账不保存代理凭据、OTP、Token 或 Cookie。服务崩溃后，运行实例会标记为
`interrupted`，资源台账保留外部 ID，供后续对账，不以删除记录伪装清理成功。

## API 与界面

- `POST /api/codex/retry`：创建单账号逻辑任务和首次 run；
- `POST /api/codex/retry-bulk`：创建稳定批次，限制并发 worker；
- `POST /api/operations/<task_id>/retry`：同一任务新增 attempt；
- `POST /api/operations/<task_id>/cancel`：取消当前活跃 attempt；
- `GET /api/operations/<task_id>`：返回 runs、events、resources 和标准流程。

账号列表分别展示凭证状态和执行状态。任务中心以 run 为边界展示阶段，取消按钮只针对
原生活跃 operation，避免“重置 retrying”篡改真实运行状态。
批次的 `requested_count` 保留用户请求数，无法入队的账号写入 `skipped_count` 和脱敏原因；
因此批次计数不会因为账号不存在或跨进程防重而凭空缺项。

## 隔离验证与生产切换

存储改造必须在独立 worktree 和独立数据库演练。推荐顺序：

1. 在隔离库执行 `tools/migrate_unified_task_center.py --apply`；
2. 重复执行一次确认幂等；
3. 执行 `--verify`，所有旧记录映射计数相等且无孤儿；
4. 运行全量测试；
5. 人工验证单账号、批量、防重、排队取消、运行取消、callback 待确认和重跑；
6. 正式切换前停服务并备份，显式放行生产库后再迁移；
7. `--verify` 失败时禁止启动新代码。

本次迁移只新增表、字段和索引，不删除旧任务表。回滚时切回旧代码，新表保留；不要为
回滚删除表或清空数据。
