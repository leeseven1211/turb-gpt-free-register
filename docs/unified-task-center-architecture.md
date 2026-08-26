# 统一任务中心架构与迁移方案

## 1. 结论

注册、注册恢复、Codex 补跑、账号配置补跑、查活、Token 刷新、套餐查询和封号邮件扫描，
统一使用下面的任务模型：

```text
operation_batches
  └─ operation_tasks            用户看到的逻辑任务
       ├─ operation_runs         一次真实执行；重跑只增加 run
       └─ operation_events       结构化阶段、错误和资源事件

account_operation_leases        账号资源族的跨进程互斥
operation_resources             代理、接码等运行资源台账

registration_attempts           一个邮箱注册一个远端身份的业务状态
registered_accounts             已落库的账号资产
```

核心约束是：**执行状态和目标状态永远分开**。

Codex 补跑的运行态、协作式取消、三轴账号状态和 callback 凭证确认规则详见
[`codex-operation-architecture.md`](codex-operation-architecture.md)。

- “本次执行失败”不等于“OpenAI 账号不存在”。
- `operation_tasks.status` 描述执行结果。
- `registration_attempts.target_status` 描述远端身份/本地账号目前处于哪个业务检查点。
- 重试同一动作时增加 `operation_runs`，不覆盖历史。
- 从完整注册切换为“继续邮箱验证”、Codex 补跑或 2FA 补跑时，创建子任务并关联原任务。
- 前端只展示服务端计算的 `next_actions`，不再通过错误文本猜应该显示哪个按钮。

## 2. 当前问题的根因

### 2.1 “任务”被三个概念混用

现状同时存在：

- `registration_jobs`：既像逻辑任务，又像一次执行；
- `account_action_tasks`：名称是任务，实际是一条执行实例；
- WebUI 的进度批次：只取“最近一个批次”，不是稳定的用户选择。

所以批量重跑会被拆成多个互不关联的任务，新的单任务又会覆盖页面当前显示的批次。

### 2.2 账号状态被执行结果遮蔽

账号可能已经跨过远端创建边界，但执行在 OTP、资料页、Token 保存或 2FA 步骤失败。
旧模型只有一条 `success/failed`，无法表达“任务失败、远端身份已创建、本地有密码、仍待验证”。

### 2.3 日志是文本，不是领域事件

相同的 2FA、登录、邮箱 OTP、套餐查询在不同流程里使用不同阶段名和日志前缀。列表页只能
截断最后一段错误，无法稳定聚合错误来源、错误类型和可执行动作。

## 3. 数据模型

### 3.1 `operation_batches`

代表一次用户或系统提交的任务集合。批次计数由子任务聚合，不由线程手工累加。

关键字段：

- `batch_uuid`：稳定公开标识；
- `source_system/source_id`：迁移期与旧批次的幂等映射；
- `batch_type`：`registration`、`retry`、`account_action`、`mixed`；
- `requested_count` 和各状态计数；
- `created_by`、`created_at`、`completed_at`；
- `data`：低频扩展信息，不保存凭据。

### 3.2 `operation_tasks`

代表用户可理解、可查看、可重跑的逻辑操作。

关键字段：

- `parent_task_id/root_task_id`：完整任务链；
- `task_type`：注册、恢复、Codex、2FA、查活等；
- `target_type/target_id`：注册尝试或账号；
- `attempt_id/account_id`：显式关联；
- `status`：执行状态；
- `target_status`：目标业务状态；
- `last_run_id/current_stage`：列表快速读取；
- `next_actions`：服务端判定的后续操作；
- `error_category/error_code/error_message`：结构化错误与原始摘要；
- `data`：迁移来源和非敏感扩展字段。

### 3.3 `operation_runs`

代表一次真实执行。首次运行、失败重跑和崩溃恢复各自保留一行。

关键字段：

- `(task_id, run_no)` 唯一；
- `source_system/source_id` 保证历史回填幂等；
- `status`、`progress_stage/progress_steps`；
- `started_at/completed_at/duration_ms`；
- 结构化错误；
- `result_summary` 和 `log_file`；
- `data` 只保存脱敏的线路、验证方式和兼容来源。

### 3.4 `operation_events`

统一时间线。注册进度和账号任务事件进入同一张表：

- `stage` 使用 `core/task_stages.py` 的稳定名称；
- `event_type` 只使用步骤五态：`stage.pending`、`stage.running`、`stage.success`、
  `stage.skipped`、`stage.failed`；业务流程通过 `append_event(..., state=...)` 明确写入，
  不能把“出现过一条日志”解释成执行成功；
- `error_category/error_code` 使用 `core/task_errors.py`；
- `detail` 经过统一脱敏，密码、OTP、Token、Cookie 和代理凭据不入库；
- `source_system/source_id` 让重复迁移只更新原事件，不产生副本。

### 3.5 `registration_attempts`

注册尝试跨越多次任务和执行实例持续存在，保存远端边界状态：

- `checkpoint`：如 `email_verification_pending`、`registered`；
- `remote_identity_state`：远端邮箱身份是否已创建/验证；
- `remote_account_state`：远端账号是否仍待资料页、已创建或未知；
- `local_account_state`：本地是否已保存检查点/完整账号；
- `target_status`：给 UI 的稳定业务状态；
- `source_root_job_id`：旧注册链的幂等映射。

## 4. 状态机

### 4.1 执行状态

```text
queued → running → success
                 → partial_success
                 → failed
                 → stopped
                 → interrupted
                 → attention_required
running → cancelling → cancelled
running/cancelling → settling → success / attention_required
queued → cancelled
```

终态不会被下一次运行覆盖；下一次运行是新的 `operation_runs` 行，任务状态投影到最新运行。

### 4.2 注册目标状态

```text
not_created
  → email_verification_pending
  → account_available

任意不确定边界 → attention_required
```

`email_verification_pending` 的唯一默认动作是 `registration_resume`。它不能默认进入普通账号
2FA 补跑，因为后者假设账号已经完成资料页并拥有可持久化 session。

## 5. 公共步骤与执行器

`core/task_stages.py` 是展示与事件协议，实际浏览器/协议函数仍按能力复用：

- Authenticator 2FA：统一调用 `setup_roxy_2fa` 或 `setup_2fa_protocol`；
- OpenAI 登录挑战：注册恢复与 Codex OAuth 统一调用
  `complete_openai_login_challenge`，同一状态机识别密码、Authenticator TOTP、邮箱 OTP 和已登录态；
- ChatGPT 会话：统一通过 `_fetch_chatgpt_session` 获取；
- about-you/profile：统一通过 `_complete_profile_page` 完成；
- 套餐、Token、邮箱 OTP 各自由单一服务函数实现。

流程只负责编排这些能力并写标准事件，不复制页面操作实现。

## 6. 错误模型

每个错误同时保留：

- `error_category`：`configuration/user/external/internal/workflow/unknown`；
- `error_code`：如 `external.proxy`、`external.email`、`workflow.page_state`；
- `error_message`：脱敏后的原始技术摘要；
- `stage`、`task_type` 和事件时间。

列表显示“分类徽标 + 一行摘要”，详情显示完整事件和原始日志。分类错误不会覆盖原始错误。

## 7. WebUI

- 左侧新增独立“任务中心”；注册和账号菜单不再各自维护一套历史入口。
- 注册页继续保留当前批次的实时执行卡片，适合观察刚发起的批次。
- 任务中心统一列出任务类型、执行状态、目标状态、批次、运行次数、当前阶段和错误分类。
- 任务详情按标准流程渲染图形化阶段，并显示所有运行和事件。
- 阶段图只聚合 `last_run_id` 对应的本次事件，历史运行保留在时间线中但不能污染本次状态；
  “已跳过”使用中性灰色，“执行中”使用蓝色，只有明确的 `stage.success` 才显示绿色。
- 重跑按钮只在 `next_actions` 非空时出现，调用统一任务接口。
- 批次选择持久化，不因单任务重跑或轮询切回“最新批次”。

## 8. 五个待恢复账号的处理

账号 338、347、353、354、355 均被迁移为：

```text
target_status = email_verification_pending
next_actions = [registration_resume]
```

此外账号级重新登录流程做两项兜底：

1. OTP 后进入 about-you/profile 时，复用注册流程的资料页函数完成资料；
2. 取得新 session 后，必须通过 `db.update_account_session` 写回 Token，并把检查点推进为
   `registered`；写回失败则任务失败，禁止显示虚假成功。

因此 #347 的“2FA 成功但 Token 未落库”和另外 4 个“OTP 成功后卡资料页”均有明确修复路径。
生产续跑又验证出 #347 会进入“密码 → Authenticator TOTP”分支；该分支现已接入上面的公共
登录状态机，避免把 Authenticator 输入框误判为邮箱 OTP。恢复成功后邮箱池状态统一收口为
`used`，不会保留失败流程产生的 `disabled/failed` 状态。

## 9. 迁移策略

### 阶段 A：隔离演练

1. 从生产库做一致性 `pg_dump -Fc`；
2. 恢复到独立开发库；
3. 执行 `tools/migrate_unified_task_center.py --apply`；
4. 执行 `--verify`，校验旧注册执行、账号执行和账号事件一一映射且无孤儿；
5. 重复执行 `--apply`，确认幂等；
6. 执行全量测试和浏览器验收。

### 阶段 B：生产切换

1. 停止 WebUI，禁止新任务进入；
2. 再做一份停服时间点备份并验证归档目录；
3. 记录五张旧表行数；
4. 显式设置 `TURB_ALLOW_PRODUCTION_DB=1` 执行迁移；
5. `--verify` 必须返回 `ok=true`；
6. 核对旧表行数完全不变；
7. 启动新代码，执行 API 和浏览器验收。

迁移只新增/更新新表，不删除或改写旧任务表。

## 10. 兼容与回滚

迁移期旧服务仍写 `registration_jobs` 和 `account_action_*`，写后通过兼容桥刷新统一投影。
异常会记录日志，幂等迁移工具可重新对账修复。旧表是只用于回滚的完整落点，不再作为新
任务中心的读模型。

回滚步骤：

1. 停止 WebUI；
2. 切回迁移前代码；
3. 启动旧 WebUI；
4. 核对旧表行数和核心账号字段；
5. 新表暂时保留，不做破坏性删除。

因为生产迁移不改旧表，正常回滚不需要恢复数据库。只有旧表本身发生意外变化时，才使用
停服前的 custom-format dump 恢复。

## 11. 切换门槛

以下条件必须全部满足：

- 全量测试通过；
- 迁移重复执行后计数不增加；
- `legacy_registration_jobs == mapped_registration_runs`；
- `legacy_account_tasks == mapped_account_runs`；
- `legacy_account_events == mapped_account_events`；
- `orphan_runs == 0`、`orphan_events == 0`；
- 五个半成品账号都显示“待邮箱验证 / 资料”和“继续邮箱验证”；
- 新 session 写回失败时任务不能成功；
- 浏览器控制台无错误，任务详情阶段图和错误详情可读；
- 生产旧表迁移前后行数完全一致。

## 12. 生产切换结果（2026-08-26）

- 本地 `turb_console` 已完成停机备份并验证归档可读；备份目录为
  `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register-backups/20260826-161335`；
- 迁移前记录为 448 个账号、656 条注册任务、34 个账号操作批次、2514 条账号任务和 9821 条账号事件；
- `--apply` 已执行并重复执行验证幂等；最终校验为 656/656 条注册运行、2514/2514 条账号运行、9821/9821 条账号事件完成映射；
- 孤儿运行、孤儿事件、重复活跃账号族、终态租约和待邮箱验证尝试均为 0；
- 主工作区全量测试为 525 项全部通过；正式 WebUI 在 8000 端口持续运行；登录、总览、仪表盘、能力、配置、账号、注册任务、Codex、账号任务接口和 modern CSS/JS 静态资源冒烟均通过，未授权 API 正确返回 401。
