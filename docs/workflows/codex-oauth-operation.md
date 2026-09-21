# Codex OAuth 操作流程

> 核对基线：2026-09-21。本文说明当前原生 Codex operation 与兼容入口的关系，不把
> 历史 service 误写成唯一入口。

## 1. 入口与持久化模型

```text
WebUI 单个/批量补跑、注册后置步骤或任务中心重跑
  -> core.codex_operation_service
  -> create_runtime_task / create_runtime_batch / retry_runtime_task
  -> operation_tasks + operation_runs + events + resources
  -> core.codex_oauth.run_codex_oauth
  -> codex_credentials 与执行状态收口
```

`core.codex_operation_service` 是新原生 operation 的提交与执行协调层。它会校验账号、功能
可用性和并发资源族，再创建持久化 task/run；相同逻辑任务的重跑增加 `run_no`，不覆盖旧
执行。`core.codex_retry_service` 仍是兼容入口/历史调用链的一部分，不能据此假设其已被
物理删除，也不能再把它描述为唯一业务入口。

## 2. 成功与待确认

凭证资产、当前执行和最近执行结果相互独立。一次新授权失败不应抹掉旧的有效凭证。

- 本地授权模式只有在实际 auth 内容完成校验并写入 `codex_credentials` 后才是成功。
- CPA/Sub2 callback 的“已接受”不是凭证；系统会按确认窗口读取并验证真实 auth 内容。
- 若 callback 已提交但不能确认新凭证，run 应保留为 `attention_required` 或对应待对账状态，
  记录脱敏回执/证据而不是虚报成功。
- 凭证数据、Token、Cookie、OTP、密码和完整代理地址不进入普通任务事件或文档。

## 3. 生命周期、资源与取消

```text
queued -> running -> success / failed / deactivated / attention_required
                   -> cancelling -> cancelled
callback 已提交     -> settling -> success / attention_required
进程中断            -> interrupted，再按恢复规则收口或重派
```

run 通过数据库条件认领和账号资源族租约防止跨进程重复授权。代理、接码等外部资源写入
`operation_resources`，终态必须释放、完成、取消或标记 `reconciliation_required`。取消
依赖安全检查点，而不是强杀线程；`settling` 期间优先完成有界凭证确认，避免把未知远端
结果误记为完全取消。

## 4. 界面和排障

账号页只负责发起单个或批量任务；运行阶段、线路摘要、事件、资源、错误和重跑历史都应在
操作任务详情中核对。排障顺序是：确认 account/task/run 关联 -> 查看 callback/凭证确认
证据 -> 查看资源和取消状态 -> 再决定是否服务端允许重跑。

通用任务模型见[账号操作](account-operations.md)；认证与 driver 支持范围见
[账号认证支持矩阵](account-auth-support-matrix.md)。
