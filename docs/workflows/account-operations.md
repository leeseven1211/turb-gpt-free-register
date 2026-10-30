# 账号操作流程

> 本文说明当前的任务运行边界；具体某项动作支持哪些认证方式，
> 以[账号认证支持矩阵](account-auth-support-matrix.md)和对应 service 为准。

## 1. 两层任务模型

账号操作区分“用户可理解的逻辑任务”和“一次真实执行”：

```text
operation_batches（可选批次）
  -> operation_tasks（逻辑任务）
       -> operation_runs（一次执行；重跑递增 run_no）
            -> operation_events（脱敏阶段与结果）
            -> operation_resources（代理、接码等资源台账）
```

同一账号/资源族的活跃 run 由数据库约束和账号资源租约共同防重。任务的业务目标状态、
凭证资产状态与本次执行状态不是同一个概念：一次失败或 `request_unknown` 不等于远端账号
不存在，也不授权重新注册或回收已使用邮箱。

## 2. 入口与执行路径

```text
WebUI accounts / operations / codex 路由
  -> 对应领域 service
  -> core.operations.task_gateway 或原生 operation service
  -> 持久化 task/run，dispatcher 条件认领 queued run
  -> handler 运行并通过 TaskReporter/operation context 写阶段
  -> 写入终态、释放或标记待对账资源
```

覆盖范围包括查活、套餐查询、刷新 AT、账号补全、2FA、封号邮件扫描、提链和 Codex
相关任务。每个 service 决定自己的可执行条件、配置快照和远端确认方式；WebUI 只提交
请求、显示服务端投影的状态和允许的后续动作。

## 3. 兼容投影仍在运行

`account_action_batches`、`account_action_tasks` 和 `account_action_events` 仍保留为兼容来源。
`core.storage.operations.store` 通过 `source_system/source_id` 将这类历史/兼容行幂等投影到
`operation_*` 表；注册 `registration_jobs` 也拥有对应投影。因而：

- operation 列表是统一读模型，不代表所有写入都已经原生化；
- 重试必须新增 run，不能覆盖历史 task/run/event；
- 观察期内不得删除 `account_action_*`、重排任务 ID 或用兼容导出改写数据库；
- `operation.verify()` 用映射数、孤儿 run/event、活跃资源族和终态资源检查投影一致性。

## 4. 取消、未知结果和恢复

取消是 run 级协作式操作：取消请求持久化后，handler 在邮箱、页面、接码、网络和退避的
安全检查点退出；不能向 Python 线程注入异步异常。无法确认已释放的代理或接码资源应标为
`reconciliation_required`，不得通过删除台账伪造成功清理。

`attention_required` 与 `request_unknown` 表示远端写入、回执或读回尚不能确定。保留原
task/run、账号检查点、邮箱来源和事件证据，按服务端给出的 `next_actions` 继续、对账或
人工处理；不得把它们降级为普通失败后直接创建新账号。

`webui.runtime.start_runtime()` 在进程启动时初始化 handler 与 dispatcher、收口无法安全
继续的活跃 run，并重新派发可恢复的 queued 工作。恢复过程不覆盖历史执行记录。

## 5. 账号解封后恢复

OpenAI 恢复访问后，本地仍保留先前确认的停用状态。普通查活、自动刷新和批量刷新不会
自动清除它。收到恢复通知后，在账号行「更多」菜单选择「已解封，恢复账号」，再执行
「刷新 AT」。恢复只解除当前停用标记，历史原因、时间和邮件证据继续保留；远端登录是否
成功仍由新任务确认，Codex 凭证需要重新授权。

账号仍有操作在执行时，恢复请求会被拒绝，应等待任务结束。旧失败任务和日志保持原状，
没有新任务入队时页面显示跳过原因。

接口为 `POST /api/accounts/<id>/restore`，需要正常鉴权，并提供确认原因：

```json
{"reason": "已收到 OpenAI 恢复访问通知"}
```

专用存储命令在同一事务中更新账号与关联 Codex 凭证的生命周期状态，不修改密码、AT、
TOTP 或凭证 JSON。同一封旧封号邮件不会再次覆盖显式恢复；新收到的封号通知仍会标记
停用。历史任务不改写，恢复后的刷新通过现有入口创建新任务。

## 6. 排障顺序

1. 先确认账号、源任务、`operation_tasks`、`operation_runs` 和事件的关联，而不是只看 UI 文案。
2. 查看当前 run 的阶段、错误分类、资源状态和远端确认/回执证据；日志只用于补充。
3. 区分本次执行失败、可继续检查点、等待对账和真正不可重试的配置/资源错误。
4. 只有服务端明确允许的 `next_actions` 才可发起重试、续跑或取消。

数据库事实来源和脱敏约束见[存储架构](../architecture/storage-architecture.md)；Codex 的
独立确认语义见[Codex OAuth 操作](codex-oauth-operation.md)。
