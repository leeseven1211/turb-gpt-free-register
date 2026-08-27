# 注册流程重构总设计

状态：Proposal（只读设计，未开始实施）  
日期：2026-08-27  
适用范围：Roxy 主注册流程、Protocol 辅助调用、邮箱/代理资源、Token/账号落库、2FA/Codex/套餐后处理、诊断和统一任务中心。

## 1. 设计结论

本项目的注册体系不是 Roxy 与 Protocol 二选一，而是：

```text
Roxy 主流程
  + Protocol 阶段级辅助
  + Roxy 页面 fallback
  + 独立后处理
  + 统一检查点
  + 异步任务中心投影
```

Roxy 负责浏览器、Profile、页面状态和需要浏览器上下文的动作；Protocol 负责已经验证可靠的快速接口调用、状态检查和部分后处理。两者属于同一次 `RegistrationAttempt`，不能被实现成两套互相独立的注册任务。

正式支持范围只保留 Roxy + Protocol 配合。新任务不再支持本地指纹浏览器、Browser Use、Skyvern 和 CloakBrowser；历史任务仍可查询和展示。

## 2. 现状证据与问题边界

最近批次 `20260827-101530-1de42a14` 共 10 条：6 成功、3 部分成功、1 失败。9 个邮箱收到 OTP，10 个 iCloud 别名均有远端创建记录；未收到 OTP 的邮箱只能标记为“链路未验证”，不能判定为无效。

已确认的程序问题：

1. 邮箱提交后存在约 90 秒级浏览器命令/导航阻塞，并被多层 fallback 重复放大。
2. OAuth callback 错误后仍轮询 `/api/auth/session` 至 120 秒，没有识别已知退出态。
3. 密码页依赖动作和 URL 推断，出现“页面已经到了但流程认为没到”。
4. 邮箱已验证页面仍进入 resend 分支。
5. 2FA 后处理失败没有稳定触发普通诊断。
6. 每个任务更新都刷新所有批次，造成 `operation_batches` 并发死锁和已成功任务显示 `running`。
7. 全量调试的保持现场和 CDP 采集改变了耗时，不能作为普通流程性能基线。

代理 CONNECT、邮箱服务、Roxy API、OpenAI 上游挑战等属于外部因素，应记录和分类，但不能用程序重构“解决”。

## 3. 目标架构

```text
registration_service
        |
        v
RoxyRegistrationOrchestrator
        |
        +-- RoxyBrowserAdapter
        +-- ProtocolClient
        +-- EmailProvider
        +-- ProxyLease
        +-- RegistrationAttempt / RegistrationRun
        +-- DiagnosticSession
        +-- PostprocessTask
        |
        v
registration_events
        |
        v
异步 projection worker
        |
        v
operation_tasks / operation_batches
```

### 3.1 领域对象

`RegistrationAttempt` 表示一个邮箱注册意图，从领取邮箱开始持续到完成、失败或人工对账。  
`RegistrationRun` 表示一次具体执行、恢复或补跑。  
`EmailLease` 和 `ProxyLease` 表示资源租约，不能依赖进程内变量。  
`PostprocessTask` 表示 2FA、Codex、套餐和账号配置等后处理。

### 3.2 驱动职责

Roxy 编排器是唯一的注册主入口。每个阶段声明：

```text
primary_action
protocol_assist
roxy_fallback
total_timeout
retry_policy
checkpoint
```

Protocol 调用失败不等于注册驱动失败；如果页面状态明确，则由 Roxy 继续。只有在远端状态未知时才停止自动动作并进入恢复/人工对账。

## 4. 状态和检查点

### 4.1 检查点

```text
created
email_claimed
auth_started
password_request_started
password_confirmed
otp_started
otp_confirmed
account_request_started
account_confirmed
token_obtained
core_persisted
postprocessing
completed
manual_reconcile
failed
```

不可逆请求前必须先写 `*_request_started`。请求结果未知时不能退回“未开始”，也不能自动开新 Attempt。

### 4.2 状态轴

执行状态：`queued/running/success/partial_success/failed/stopped/cancelled/interrupted`。  
远端身份：`not_started/request_unknown/confirmed/rejected`。  
远端账号：`not_started/request_unknown/confirmed/rejected`。  
本地账号：`none/token_obtained/persisted`。  
能力状态：2FA、Codex、套餐分别维护 `pending/running/success/failed/skipped`。

注册核心成功条件固定为：远端账号确认、Token 获取、本地核心账号资料保存。后处理不回滚核心成功。

## 5. Roxy 页面状态机

统一页面状态：

```text
EMAIL_FORM -> AUTH_TRANSIENT -> PASSWORD_CREATE/PASSWORD_LOGIN
    -> OTP_EMAIL -> PROFILE -> AUTHENTICATED -> CORE_PERSISTED

任何阶段 -> AUTH_ERROR / LOGGED_OUT / UNKNOWN
```

OTP 阶段还要区分 `OTP_ACCEPTED`、`EMAIL_VERIFIED`、`OTP_INVALID`、`OTP_STUCK`。只有确认仍在邮箱 OTP 页面且验证码未生效时才允许重发，单次执行最多一次受控重发。

Session 等待采用正向信号优先：已知 `AUTH_ERROR`、`LOGGED_OUT` 或 callback 错误连续确认后立即结束，不再无条件轮询 120 秒。

## 6. 失败、重试和恢复

每个错误必须同时具备：`error_code`、`source`、`stage`、`retryability`、`remote_state_impact`、`next_action`。

规则：

- 程序确定性错误：当前阶段最多一次纠正动作，不重新注册。
- 外部瞬态错误：只重试幂等或结果安全的动作。
- 已越过不可逆边界：只能继续同一 Attempt、补跑后处理或人工对账。
- 结果未知：进入 `request_unknown/manual_reconcile`，禁止根据邮箱地址重新猜测。
- Token 获取后立即保存核心账号，2FA/Codex/套餐独立补跑。

## 7. 诊断策略

本地部署下不增加任何脱敏处理。邮箱、URL、页面文本、请求参数、响应正文、截图和浏览器事件均按原始内容保存。诊断仍限制单任务采集范围、队列和容量，防止抓包阻塞注册主流程。

诊断触发条件：核心失败、部分成功、后处理失败、未知状态、远端请求已开始但结果不确定、任务中心投影异常。

诊断必须带有：`job_id`、`attempt_id`、`run_id`、`trigger_stage`、`last_confirmed_state`、`failure_stage`、`capture_scope`、`network_error_observed` 和 `email_evidence`。

`email_evidence` 至少记录邮箱、来源、池记录、远端别名状态、是否收到 OTP、是否验证、是否创建账号、是否落库和释放结果。

## 8. 性能设计

不增加 fast 模式。只有一套正常流程，但删除重复等待和无效等待。每阶段只能有一个总超时，内部的 Roxy、Protocol 和 fallback 共享该预算。

重点优化：邮箱提交导航去重、密码页状态直判、OTP 终态识别、Session 退出态提前结束、Protocol 与 Roxy fallback 不叠加长超时、后处理移出核心耗时。

每个阶段记录单调时钟和 `wait_reason`：`resource_wait`、`driver_command`、`page_transition`、`email_wait`、`human_delay`、`db_write`、`projection`、`cleanup`。性能指标使用 p50/p95，资源等待和外部等待单独统计。

## 9. 任务中心

注册事实由 `registration_attempts/registration_runs/registration_events` 维护，任务中心只是异步投影。注册执行不等待投影，投影失败不能改变注册结果。

投影只重算受影响的 `batch_id`，采用固定更新顺序和单批次锁/单写者；失败进入重试队列；启动时执行事实与投影对账。前端显示“注册已完成，任务中心投影延迟”，不能显示为永久 `running`。

## 10. 与现有文档的关系

本设计补充并收敛：

- [registration-state-refactor-design.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/registration-state-refactor-design.md)：状态和恢复模型基础。
- [core-registration-flow.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/core-registration-flow.md)：当前实现流程。
- [unified-task-center-architecture.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/unified-task-center-architecture.md)：任务中心模型。
- [registration-implementation-plan.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/registration-implementation-plan.md)：本设计的实施拆分。

后续以本文的“Roxy 主流程 + Protocol 辅助”定义覆盖旧文档中把驱动并列描述的部分。
