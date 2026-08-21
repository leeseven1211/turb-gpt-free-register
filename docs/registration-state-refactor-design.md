# 注册流程状态与恢复能力重构设计

状态：Proposal

日期：2026-08-21

适用范围：Protocol、Roxy、Cloak、Browser Use、Skyvern 注册流程，以及 WebUI、CLI、账号补跑和邮箱/代理资源管理。

## 1. 目标

本次重构要解决的不是某一个驱动的接口问题，而是把以下事实统一到一个可恢复的模型中：

1. 远端身份或账号是否已经跨过不可逆创建边界。
2. 本地是否已经保存账号核心资料和 Token。
3. 邮箱是否仍被某次注册尝试占用。
4. Codex、2FA、套餐检查和 Flow 分别完成到什么程度。
5. 当前执行是首次注册、同账号恢复、后处理补跑，还是人工对账。

重构完成后必须满足以下不变量：

- 任何可能已经发出远端创建请求的任务，都不能被自动当作一次全新注册。
- 远端请求前必须先持久化“请求已开始”的检查点。
- 获取 Token 后必须立即保存账号核心资料，不能等待 Codex、2FA、套餐或 Flow 完成。
- 邮箱和代理的生命周期必须绑定到数据库租约和注册尝试，不能依赖邮箱地址、进程内集合或线程存活状态推断。
- 重启恢复必须可重复执行，重复恢复不能重复领取邮箱、重复创建补跑任务或覆盖更晚的状态。
- WebUI、CLI、注册任务内部补跑和账号页面补跑必须使用同一套后端状态判断。

本设计不改变注册接口、反检测策略、验证码供应商和代理供应商的具体实现，只重构它们周围的状态、持久化和调度边界。

## 2. 当前问题

当前实现中存在三种不同层次的状态，但没有统一的事实来源：

```text
registration_jobs       一次任务执行
registered_accounts     一个已保存账号，Roxy 还有少量临时账号例外
进程内变量              create_acknowledged、_RETRYING、邮箱客户端上下文
```

主要问题如下：

- `main.py` 和多个浏览器驱动使用进程内 `create_acknowledged` 判断是否可以释放邮箱或换代理。进程崩溃后该信息丢失。
- Protocol、Cloak、Browser Use、Skyvern 在后处理结束后才调用账号保存逻辑。Token 已经获得但账号还没有落库时，崩溃会制造重复注册风险。
- `registration_jobs` 是一次执行记录，重试会创建子任务，但目前没有独立的业务尝试记录来承载共享状态。
- `get_retry_info()` 根据账号、密码、Codex、套餐、2FA 等字段启发式推断动作，无法表示“远端请求结果未知”。
- 邮箱 claim、临时邮箱上下文和部分补跑互斥仍依赖进程内锁或内存集合。
- 启动恢复主要修改任务和代理状态，没有以注册尝试为中心对账邮箱和账号。
- Codex/2FA 既可以从注册任务补跑，也可以从账号操作任务补跑，两套恢复和互斥逻辑不一致。

相关现有代码：

- `main.py`：统一注册入口、Protocol 后处理和当前的创建边界变量。
- `core/registration_service.py`：任务执行、代理重试、重试决策和注册任务恢复。
- `core/db.py`：注册任务、账号和邮箱池业务存储。
- `core/record_store.py`：行级 PostgreSQL 存储、条件更新和跨表事务。
- `core/email_provider.py`：邮箱来源路由和临时邮箱上下文恢复。
- `core/account_task_store.py`：账号操作任务和启动恢复。

## 3. 总体架构

重构后采用三层模型：

```text
RegistrationAttempt      注册业务事实，一个邮箱注册意图只有一个
        |
        +-- RegistrationJob        一次执行或一次恢复执行
        |
        +-- EmailLease             邮箱资源租约
        |
        +-- ProxyLease             代理资源租约
        |
        +-- AccountActionTask      Codex、2FA、套餐等后处理任务
```

### 3.1 RegistrationAttempt

`RegistrationAttempt` 是本次重构的核心聚合。它代表“使用某个邮箱尝试创建一个远端账号”，从第一次领取邮箱开始一直保留到账号完成、失败或人工对账结束。

它不是线程，也不是单次 HTTP 请求；同一尝试可以有多个执行任务，包含换代理、重启恢复和后处理补跑。

### 3.2 RegistrationJob

`RegistrationJob` 保留现有任务表的作用，负责记录一次执行：

- 谁在执行：进程、执行实例和心跳。
- 什么时候执行：排队、开始、结束和耗时。
- 执行了哪个动作：首次注册、同账号恢复、Codex 补跑、2FA 补跑。
- 本次执行的日志、进度和错误。

它必须通过 `attempt_id` 指向注册尝试，不再独立推断远端创建事实。

### 3.3 AccountActionTask

账号页面创建的 Codex、2FA、套餐和其他账号操作继续使用数据库任务表，但要增加统一的 `attempt_id`、`account_id`、`action_type` 和资源占用字段。

注册任务内部的 Codex/2FA 补跑最终也转换为同一种账号操作任务。迁移完成后，不再保留一套只由注册任务驱动的进程内补跑互斥逻辑。

## 4. 状态模型

### 4.1 检查点和远端状态分离

不能用一个 `create_acknowledged` 布尔值表示整个注册过程。至少要区分远端身份创建和远端账号创建两个边界。

#### RegistrationAttempt.checkpoint

检查点表示流程已经执行到哪里，取值按以下顺序推进：

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

说明：

- `password_request_started` 表示已经准备发出密码提交请求。请求结果未知时也必须停在该检查点或进入后续的未知状态，不能退回 `auth_started`。
- `account_request_started` 表示已经准备发出 `create_account` 或等价的资料提交请求。
- `token_obtained` 是内存中拿到 Token 的瞬时事实，必须尽快推进到 `core_persisted`。
- `manual_reconcile` 是安全终点，表示系统知道不能自动新注册，但目前无法可靠继续同一账号。

#### remote_identity_state

```text
not_started
request_unknown
confirmed
rejected
```

它描述密码注册、邮箱身份创建等较早的不可逆远端状态。

#### remote_account_state

```text
not_started
request_unknown
confirmed
rejected
```

它描述资料提交、`create_account` 或通过登录态确认远端账号存在的状态。

#### local_account_state

```text
none
token_obtained
persisted
```

新流程不再把没有 Token 的临时记录当作完整的 `registered_accounts`。密码、邮箱和恢复检查点放在 `registration_attempts` 中；只有账号核心资料和 Token 已经保存后，才创建或更新 `registered_accounts`。

现有 Roxy 产生的空 Token 临时账号需要在迁移期兼容读取，并逐步转成注册尝试记录。任何账号列表、Codex 和套餐逻辑都必须显式排除 `access_token` 为空的历史临时记录。

### 4.2 任务执行状态与业务状态分离

任务执行状态保留以下取值：

```text
queued
running
stopping
success
partial_success
failed
stopped
cancelled
interrupted
```

任务状态只表示这次执行的结果，不能代表远端账号是否存在。

业务状态由注册尝试和账号投影共同计算：

```text
registration_core_status:
  pending
  in_progress
  success
  failed
  unknown
  manual_reconcile

account_readiness:
  incomplete
  ready
  deactivated

codex_status:
  pending
  running
  success
  failed
  skipped
  stopped
  deactivated
```

“注册核心成功”定义为：远端账号已确认、Token 已获得、账号核心资料已经保存。

“账号可用”定义为：账号核心成功，并且密码、套餐和启用的 2FA 要求均已满足。

“Codex 可用”单独由 `codex_status` 表示。Codex 跳过是否影响任务最终状态由配置决定，但不能反向改变注册核心状态。

Flow 属于增强能力，不影响注册核心成功；它的结果单独记录在账号或操作事件中。

## 5. 不可逆边界和检查点协议

### 5.1 统一协议

所有驱动必须通过统一的 `RegistrationAttemptStore` 或等价服务更新检查点，禁止直接修改内存布尔值作为重试依据。

每次远端不可逆请求都遵守以下顺序：

```text
1. 开启数据库事务
2. 校验 attempt 当前状态允许进入目标检查点
3. 写入 request_started 检查点和事件
4. 提交事务
5. 发出远端请求
6. 根据响应写入 confirmed / rejected
7. 网络异常写入 request_unknown
```

第 4 步和第 5 步之间崩溃时，系统仍按“请求可能尚未发出但不可安全重试”处理。这是有意的保守策略，用少量人工对账换取不重复创建账号。

### 5.2 Protocol

需要在 `create_account()` 调用前写入 `account_request_started`，响应被明确判定为成功后写入 `account_confirmed`。

如果 `/api/auth/session` 拿到 Token：

1. 保存 `token_obtained` 检查点和必要的非敏感 session 元数据。
2. 立即执行核心账号落库事务。
3. 成功后写入 `core_persisted`。
4. 再执行 2FA、Codex、套餐和 Flow。

### 5.3 浏览器驱动

Cloak、Browser Use、Skyvern 和 Roxy 需要把以下动作从“页面操作”转换为“持久化检查点 + 页面操作”：

- 提交密码前写入 `password_request_started`。
- 密码提交成功或页面确认后写入 `password_confirmed`。
- 点击提交资料或确认 `create_account` 前写入 `account_request_started`。
- 进入明确的已登录页面或获取 session Token 后写入 `account_confirmed`。
- Token 获取后立即进行核心账号落库。

页面超时、浏览器断开和代理断开不能自动清除已有检查点。

### 5.4 Token 核心落库

当前 `save_account_data()` 同时包含账号写入、兼容归档和套餐查询。重构后拆为：

```text
persist_account_core()
  - upsert registered_accounts
  - 保存 access_token、密码、邮箱来源、设备和基础用户信息
  - 绑定 registration_attempt.account_id
  - 将 email lease 标记为 linked
  - 将 attempt 标记为 core_persisted

run_post_registration_actions()
  - 2FA
  - Codex
  - 套餐查询
  - Flow
  - 兼容导出和归档
```

核心落库必须是幂等的。以 `email` 和 `account_id` 为唯一关联依据，重复执行只能更新同一账号，不能创建第二条账号记录。

## 6. 数据模型

项目当前使用“提升列 + JSONB data”的 PostgreSQL 行级模型。新增字段只有在需要查询、排序或原子抢占时才提升为列，其余放入 `data`。

### 6.1 registration_attempts

建议新增 `registration_attempts` 表：

```sql
CREATE TABLE registration_attempts (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    attempt_uuid TEXT NOT NULL UNIQUE,
    root_job_id BIGINT,
    email TEXT NOT NULL,
    email_source TEXT,
    email_lease_id BIGINT,
    driver TEXT,
    checkpoint TEXT NOT NULL,
    remote_identity_state TEXT NOT NULL,
    remote_account_state TEXT NOT NULL,
    local_account_state TEXT NOT NULL,
    account_id BIGINT,
    resume_policy TEXT,
    active_execution_id TEXT,
    heartbeat_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    terminal_at TEXT,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

建议索引：

```text
(root_job_id)
(account_id)
(email)
(checkpoint, updated_at)
(remote_account_state, updated_at)
```

`data` 可保存：

- 注册密码或密码引用。由于同账号恢复需要密码，必须在密码提交前持久化；不得写入日志和事件详情。
- name、birthday、设备标识和驱动私有恢复信息。
- 最后一次安全错误摘要。
- provider-specific 的非敏感上下文。

Access Token、refresh token、验证码和完整远端响应不写入事件表。Token 仍由 `registered_accounts` 的现有私有存储承载。

### 6.2 registration_attempt_events

建议新增追加式事件表：

```sql
CREATE TABLE registration_attempt_events (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    attempt_id BIGINT NOT NULL,
    created_at TEXT NOT NULL,
    execution_id TEXT,
    checkpoint TEXT NOT NULL,
    event_type TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

事件用于恢复、审计和排查，当前状态仍以 `registration_attempts` 投影为准。事件写入和状态投影必须在同一个数据库事务中完成。

事件详情禁止包含：

- 密码、Token、refresh token、OTP、TOTP secret。
- 完整代理 URL、代理认证信息和邮箱池凭据。
- 未脱敏的第三方 API 响应。

### 6.3 registration_jobs 扩展

在现有任务表增加或提升：

```text
attempt_id
execution_id
action_type
worker_pid
heartbeat_at
interrupted_at
```

现有 `root_job_id`、`parent_job_id`、`batch_id` 继续兼容，但新的业务判断必须优先使用 `attempt_id`。

### 6.4 email_leases

现有 Outlook 和 Generic API 邮箱池只描述库存，不足以描述跨来源租约。建议增加统一 `email_leases` 表：

```sql
CREATE TABLE email_leases (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    lease_uuid TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    email TEXT NOT NULL,
    provider_account_ref TEXT,
    attempt_id BIGINT,
    state TEXT NOT NULL,
    resume_capability TEXT NOT NULL,
    owner_execution_id TEXT,
    claimed_at TEXT,
    expires_at TEXT,
    consumed_at TEXT,
    released_at TEXT,
    registered_account_id BIGINT,
    release_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

租约状态：

```text
available
claimed
consumed
linked
quarantined
released
failed
```

其中：

- `claimed`：已领取但尚未跨越远端不可逆边界。
- `consumed`：已经提交密码或创建请求，不能回收到 `available`。
- `linked`：已经绑定到本地账号。
- `quarantined`：远端是否使用未知，必须人工或同账号恢复处理。
- `released`：确认没有跨越不可逆边界，可以再次领取。

`resolve_email_source(email)` 只能作为兼容逻辑，新的流程必须使用 `email_lease_id`，不能按邮箱地址猜测上下文。

### 6.5 现有账号表

`registered_accounts` 继续作为已获得 Token 的账号事实表。新增：

```text
registration_attempt_id
registration_core_status
account_readiness
```

这些字段可以先放在 `data`，等需要筛选和排序时再提升为列。

空 Token 的历史临时账号在迁移期间保留，但必须加上 `legacy_provisional=true`，并从完整账号查询、Codex 补跑和套餐检查中排除。

## 7. 邮箱恢复策略

每个邮箱来源必须实现统一能力声明：

```text
resume_capability:
  durable_reconnect
  api_reconnect
  process_bound
  manual_only
```

含义：

- `durable_reconnect`：凭数据库中的邮箱凭据或池记录可以跨进程重新连接。
- `api_reconnect`：通过 provider_account_ref 和持久化上下文可以重新获取邮件。
- `process_bound`：上下文只存在当前进程内，重启后不能保证找回原邮箱。
- `manual_only`：只能由用户或外部系统继续处理。

### 7.1 任务未跨越不可逆边界

如果 attempt 的 remote identity 和 remote account 都是 `not_started`，恢复时可以：

- 释放当前租约为 `released`。
- 重新使用同一邮箱，或按业务配置领取新邮箱。
- 允许代理换线后重跑完整注册。

### 7.2 已跨越边界且邮箱可恢复

如果密码或账号创建请求已经开始，且 `resume_capability` 为 `durable_reconnect` 或 `api_reconnect`：

- 邮箱租约保持 `consumed`。
- 只能创建 `registration_resume` 执行任务。
- 恢复流程使用同一邮箱和已保存密码。
- 不允许创建新的注册邮箱。

### 7.3 已跨越边界但邮箱不可恢复

如果来源为 `process_bound` 或 `manual_only`，重启后：

- 不允许根据邮箱地址重新构造客户端。
- 租约标记为 `quarantined`。
- attempt 标记为 `manual_reconcile`。
- UI 显示“不能自动恢复同账号”，而不是显示为可重新注册。

### 7.4 邮箱回收原则

只有以下情况允许回到 `available` 或 `released`：

- 邮箱领取后，明确没有发出密码或账号创建请求。
- Provider 明确拒绝领取且没有产生远端注册副作用。
- 用户主动取消，并且 attempt 的不可逆状态仍为 `not_started`。

以下情况绝不自动回收：

- 请求超时、连接断开或响应无法解析。
- 已写入 `password_request_started`。
- 已写入 `account_request_started`。
- 已拿到 Token 但本地核心落库失败。

## 8. 启动恢复

启动恢复改为以注册尝试为中心执行，不再只把任务批量改成失败。

### 8.1 恢复顺序

```text
1. 创建新的 execution_id
2. 原子收口上个进程遗留的 registration_jobs
3. 找出没有活跃执行者的 registration_attempts
4. 按 attempt checkpoint 对账账号和邮箱租约
5. 回收或隔离邮箱租约
6. 回收代理租约
7. 修正 Codex/2FA/account action 的 retrying 状态
8. 生成恢复事件和可执行的下一步动作
```

### 8.2 恢复决策

| attempt 状态 | 恢复结果 |
| --- | --- |
| 未领取邮箱 | 标记执行中断，可重新排队 |
| 已领取但未跨边界 | 释放邮箱，可重新注册 |
| 密码请求未知，密码已保存，邮箱可恢复 | 标记为可 `registration_resume` |
| 账号请求未知 | 标记为同账号恢复或人工对账，禁止新注册 |
| Token 已保存但账号未关联 | 幂等补齐 `registered_accounts` 和租约绑定 |
| 核心账号已保存 | 不重跑注册，只生成后处理动作 |
| 缺少密码或临时邮箱上下文 | `manual_reconcile`，邮箱隔离 |

恢复函数必须具备幂等性。重复执行时使用条件更新和状态版本校验，不能重复插入账号、租约或补跑任务。

### 8.3 旧数据恢复

历史任务没有完整的远端边界记录，不能假装能够准确推断。迁移规则：

- 有有效 `account_id` 且 Token 非空：建立 `core_persisted` attempt。
- 有 Roxy 的 `email_verification_pending`：建立 `password_confirmed` attempt，并迁移密码和邮箱来源。
- 进度明确停在创建请求之前：建立 `not_started` attempt。
- 进度已进入资料提交、Token 或后处理但没有账号：建立 `legacy_unknown`，默认 `manual_reconcile`，禁止自动新注册。
- 无法分类的历史失败任务：保留原任务状态，新增迁移事件，要求用户显式选择继续同账号或新注册。

## 9. 代理换线和重试

`_should_retry_registration_with_new_proxy()` 不能再依赖结果字典中是否包含 `account_id`、Token 或某个错误字符串。

允许完整换线重试的条件必须由数据库确认：

```text
attempt.remote_identity_state == not_started
attempt.remote_account_state == not_started
attempt.local_account_state == none
attempt 未进入 manual_reconcile
```

如果代理在邮箱提交前失败，可以保留同一个邮箱租约并换线；是否重新领取邮箱由邮箱来源策略决定。

如果代理在不可逆边界之后失败：

- 只能释放代理租约。
- 新执行必须是同账号恢复，不能重新走注册入口。
- 不允许用“换代理”掩盖远端账号创建结果未知。

代理重试次数、冷却时间和 provider 限制仍由配置控制，但重试资格由 attempt 状态控制。

## 10. 重跑动作模型

后端不再返回一个模糊的“重试”按钮状态，而是返回显式动作：

```text
registration_new
registration_resume
registration_reconcile
codex_retry
twofa_retry
account_setup_retry
plan_check_retry
```

每个动作都有服务端前置条件：

| 动作 | 前置条件 |
| --- | --- |
| `registration_new` | 没有现存 attempt，或明确确认远端未创建 |
| `registration_resume` | attempt 已跨边界、邮箱可恢复、密码或恢复上下文存在 |
| `registration_reconcile` | 远端状态未知，用户或人工流程负责确认 |
| `codex_retry` | 本地账号 Token 有效，且没有同账号活动任务 |
| `twofa_retry` | 本地账号存在，2FA 未完成或状态失败 |
| `account_setup_retry` | 账号核心成功但密码、套餐或 2FA 不完整 |
| `plan_check_retry` | 账号存在且 Token 可用 |

`get_retry_info()` 可以保留为兼容 API，但内部改为读取动作服务的结果，不能自行拼接启发式判断。

### 10.1 Codex 和 2FA 互斥

同一个账号的动作任务必须使用数据库条件抢占：

```text
queued -> running
WHERE account_id = ?
  AND action_type = ?
  AND 没有其它 queued/running 任务
```

进程内 `_RETRYING` 只能作为性能优化，不能作为正确性依据。进程重启后，数据库任务状态和账号状态必须可以独立恢复。

## 11. 跨进程互斥

所有资源和任务抢占都必须由 PostgreSQL 完成。

### 11.1 邮箱抢占

使用 `UPDATE ... WHERE ... RETURNING` 或 `SELECT ... FOR UPDATE SKIP LOCKED`：

- 只有 `available` 或租约已过期的记录可以被抢占。
- 抢占同时写入 `lease_uuid`、`attempt_id`、`owner_execution_id` 和过期时间。
- 相同邮箱和相同 attempt 的重复请求返回原租约，不创建第二个租约。

### 11.2 attempt 执行抢占

一个 attempt 同时只能有一个活动注册执行。恢复任务需要先通过条件更新抢占 attempt，再创建或启动 job。

### 11.3 重试任务去重

对同一 attempt 或 account 的活动动作建立数据库唯一约束，或者使用带状态条件的唯一索引：

```text
同一 attempt + action_type 只能有一个 queued/running 任务
同一 account + action_type 只能有一个 queued/running 任务
```

重复请求返回已有任务 ID，而不是新建第二个任务。

### 11.4 代理租约

继续使用现有 `proxy_leases` 表，但恢复依据改为 `owner_execution_id`、过期时间和数据库状态，不依赖线程是否仍然存在。

## 12. 批次、WebUI 和 CLI

### 12.1 注册批次

批量补跑必须有真正的批次实体，而不是循环创建多个无关联子任务。批次至少包含：

```text
batch_id
batch_type
requested_count
queued_count
running_count
success_count
partial_count
failed_count
stopped_count
created_at
completed_at
stop_requested
```

每个子任务关联 `batch_id` 和 `attempt_id`。批次统计由数据库聚合刷新，不能由某个 WebUI 进程内存维护。

后续可将 `account_action_batches`、注册批次和其它批次统一为 `operation_batches`；在完成前先提供兼容适配层，避免一次性迁移所有 UI API。

### 12.2 WebUI

任务详情需要同时展示：

- 执行状态。
- 注册核心状态。
- 远端身份和账号状态。
- 本地账号状态。
- 邮箱租约状态及是否支持重启恢复。
- 当前允许的显式动作。
- 不允许继续的原因。

### 12.3 CLI

CLI 必须通过同一个 registration service 创建 attempt 和 job。直接调用 `main.run_registration()` 的兼容入口可以保留，但必须自动创建一个 CLI execution context，否则：

- 没有数据库任务状态。
- 没有停止信号。
- 没有启动恢复信息。
- 不能使用统一的重试和资源释放规则。

## 13. 驱动迁移策略

采用共同接口、逐驱动接入，不在一个提交中重写所有浏览器流程。

### 13.1 共同接口

建议提供以下服务接口：

```python
attempt = registration_attempts.start(...)
attempt.checkpoint("password_request_started", ...)
attempt.checkpoint("password_confirmed", ...)
attempt.mark_remote_account_request_started(...)
attempt.mark_remote_account_confirmed(...)
account_id = attempt.persist_account_core(...)
attempt.start_postprocessing(...)
attempt.complete(...)
```

接口内部负责：

- 状态转换校验。
- 事件和投影同事务写入。
- attempt/job/email lease 关联。
- 脱敏日志。
- 重复调用幂等处理。

### 13.2 接入顺序

1. Protocol：HTTP 边界最清晰，先完成端到端垂直切片。
2. Roxy：把现有空 Token 临时账号检查点迁移到 attempt。
3. Cloak：接入密码和资料页面边界。
4. Browser Use：接入云浏览器断开和恢复能力声明。
5. Skyvern：沿用 Browser Use 的检查点契约，单独声明 provider 恢复限制。

每个驱动接入后都必须通过同一组 driver contract tests，不能只依赖各自的集成测试。

## 14. 迁移与兼容

### 14.1 增量迁移

建议分为以下阶段：

#### Phase 0：契约和存储准备

- 增加 `registration_attempts`、事件和邮箱租约表。
- 增加 `attempt_id`、执行实例和心跳字段。
- 不改变现有任务执行逻辑。
- 为现有账号和任务生成兼容投影。

#### Phase 1：核心持久化

- 实现状态转换服务和事件记录。
- Protocol 接入请求前检查点。
- Token 后立即核心账号落库。
- 增加崩溃点测试。

#### Phase 2：驱动接入

- 逐个接入 Roxy、Cloak、Browser Use、Skyvern。
- 新流程不再创建空 Token 的临时账号。
- 旧临时账号只读兼容，逐步迁移。

#### Phase 3：恢复和邮箱租约

- 启动恢复改为 attempt 对账。
- 所有本地邮箱池使用数据库租约。
- 临时邮箱来源声明恢复能力。
- 代理回收和邮箱回收统一按 attempt 决策。

#### Phase 4：重试和互斥

- 代理重试使用 attempt 状态。
- 显式重跑动作替代 `get_retry_info()` 启发式判断。
- Codex/2FA 统一到账号操作任务。
- 移除 `_RETRYING` 作为正确性依赖。

#### Phase 5：批次和 CLI

- 引入真正的补跑批次。
- WebUI 和 CLI 共用同一个任务服务。
- 保留 API 兼容字段，完成稳定期后再删除旧路径。

### 14.2 兼容字段

迁移期间继续维护以下旧字段，但它们只能作为兼容投影：

- `registration_jobs.account_id`
- `registration_jobs.progress_steps`
- `registration_jobs.status`
- `registered_accounts.extra_json.registration_checkpoint`
- `result.account_id`
- `result.registration_pending`

新代码以 `attempt_id` 和状态服务为准。兼容投影写失败不能回滚核心事务，只记录错误并由后台导出重试。

## 15. 测试方案

### 15.1 状态机单元测试

- 合法状态只能向前推进。
- `request_unknown` 不能转为 `not_started`。
- 重复 checkpoint 调用是幂等的。
- 非法状态转换被拒绝。
- 账号核心落库重复执行不会创建第二条账号。

### 15.2 崩溃点测试

至少模拟以下退出点：

```text
邮箱领取后、远端请求前
检查点提交后、远端请求前
远端请求已发出、响应前
远端成功响应后、Token 前
Token 获取后、核心落库前
核心落库后、Codex 前
Codex/2FA/套餐执行中
```

验证每个点重启后：

- 不会新建错误的邮箱或账号。
- 不会重复领取同一邮箱。
- 不会丢失可恢复的密码和 attempt。
- 不会把已保存账号重新判定为注册失败。

### 15.3 跨进程测试

使用独立 PostgreSQL 测试 schema，启动两个 worker：

- 同一邮箱只能被一个 attempt 抢到。
- 同一 attempt 只能有一个活动执行。
- 同一账号只能有一个 Codex/2FA 活动任务。
- 两个进程同时创建 retry 时只产生一个任务。
- 一个进程退出后，另一个进程可以完成租约恢复。

### 15.4 驱动契约测试

每个驱动至少验证：

- 请求前写入检查点。
- 请求成功和请求未知分别写入正确状态。
- Token 后立即调用核心落库。
- 后处理失败不影响核心账号记录。
- 返回结果包含 `attempt_id`、`account_id`、核心状态和可恢复动作。

### 15.5 迁移测试

- 旧的 Roxy 待邮箱验证账号能转换为 attempt。
- 有 Token 的旧任务能转换为 `core_persisted`。
- 无法判断远端状态的历史任务不会自动新注册。
- 兼容导出和现有 WebUI 字段仍然可读。

## 16. 可观测性和安全

每个日志和事件都应带上：

```text
attempt_id
job_id
execution_id
account_id（如有）
checkpoint
driver
```

日志中不出现密码、Token、OTP、TOTP secret、邮箱池凭据和带认证信息的代理 URL。

状态转换失败、恢复跳过、租约隔离和重复任务去重都必须有结构化事件，便于之后判断是业务失败还是调度失败。

注册密码必须在跨过密码请求边界前持久化。第一阶段可以沿用当前本地 PostgreSQL 私有数据的存储方式，但不能把密码复制到事件、日志、兼容导出或 API 错误信息。后续可独立增加字段加密，不与状态重构耦合。

## 17. 验收标准

满足以下条件才算完成第一阶段：

1. Protocol 在远端创建请求前后都有数据库检查点。
2. Protocol 获取 Token 后，任何后处理开始前都能在 `registered_accounts` 找到核心账号。
3. 进程在任一关键崩溃点退出并重启后，不会自动新注册一个可能已经存在的账号。
4. 代理重试只对未跨不可逆边界的 attempt 生效。
5. 邮箱释放由 attempt 状态决定，而不是由任务最终状态决定。
6. 同一 attempt、账号和邮箱在两个进程并发时不会产生重复活动任务或重复租约。
7. Roxy 旧的待邮箱验证数据可以继续使用，且不再被误判为完整账号。
8. 所有新状态都能在 WebUI 和 CLI 中给出明确的下一步动作。

## 18. 明确不做的事情

- 不尝试对远端未知请求做不可靠的“肯定没有创建”判断。
- 不因为恢复困难就自动换新邮箱重新注册。
- 不把临时邮箱服务的进程内上下文伪装成可重启恢复。
- 不在本次重构中修改 OpenAI 注册接口、反检测参数或验证码供应商协议。
- 不立即删除旧字段和旧 API；先保留兼容投影，完成稳定期后再清理。

## 19. 统一任务中心设计

前面的 `RegistrationJob` 和 `AccountActionTask` 仍然是两个领域名称，容易把“注册任务”和“账号任务”误解为两套任务系统。本节对任务模型做进一步收敛：

```text
批次 Batch
  -> 任务 Task
       -> 执行实例 Run
            -> 事件 Event
```

注册尝试和账号不是任务类型，而是任务的目标对象：

```text
OperationTask.target_type = registration_attempt
OperationTask.target_type = account
```

因此，注册页看到的“任务记录”和账号页看到的“任务实例”是同一个任务中心的不同筛选入口，不再维护两套任务状态、列表和重跑判断。

### 19.1 用户概念

| 概念 | 用户理解 | 系统含义 |
| --- | --- | --- |
| 批次 | 一次批量操作 | 一组相关任务的统计、停止和进度容器 |
| 任务 | 用户发起的一次明确动作 | 一个可重跑、可查看结果的逻辑操作 |
| 执行实例 | 任务实际跑过的一次 | 首次执行、重试、恢复各自一条实例 |
| 事件 | 任务过程中的时间线 | 状态、阶段、错误和资源变化 |
| 注册尝试 | 一个邮箱注册一个远端账号的业务档案 | 跨越多次任务和执行实例持续存在 |
| 账号 | 已保存 Token 的本地账号 | 后处理任务的目标 |

任务和执行实例必须区分：

- 同一个动作由于网络失败重试时，仍然是同一个任务，增加执行实例 `run_no=2`。
- 从“重新注册”转为“继续原账号”时，动作发生变化，创建一个新的子任务，仍然关联同一个注册尝试。
- 注册核心完成后补跑 Codex 或 2FA 时，创建账号目标任务，并通过 `parent_task_id` 关联原注册任务。
- 历史执行实例不能因为后续重跑成功而删除或覆盖；任务详情始终展示完整链路。

### 19.2 统一数据模型

#### operation_batches

批次是用户或系统一次提交的集合：

```text
id
batch_uuid
batch_type                 registration / retry / account_action / mixed
title
requested_count
queued_count
running_count
success_count
partial_count
failed_count
attention_count
stopped_count
cancelled_count
stop_requested
created_by                  webui / cli / scheduler / recovery
created_at
completed_at
data
```

批次不直接保存业务状态。批次状态由子任务聚合得出，避免一个 WebUI 进程退出后留下错误统计。

#### operation_tasks

任务是用户可见的逻辑操作：

```text
id
task_uuid
batch_id
parent_task_id
root_task_id
task_type                   registration / registration_resume / codex_retry / twofa_retry / ...
target_type                 registration_attempt / account
target_id
attempt_id
account_id
requested_action
status                      queued / running / waiting / success / partial_success /
                            failed / stopped / cancelled / attention_required
last_run_id
next_actions                jsonb
trigger                     manual / manual_bulk / recovery / registration_auto / scheduler
created_at
updated_at
completed_at
data
```

约束：

- `target_type=registration_attempt` 时必须有 `attempt_id`。
- `target_type=account` 时必须有 `account_id`。
- `registration_resume`、`registration_reconcile` 和后处理动作必须保留 `parent_task_id`。
- `next_actions` 是服务端计算的动作列表，前端不能根据错误文本自行猜测按钮。

#### operation_runs

执行实例替代当前 `registration_jobs` 和账号操作任务中“每次真正执行”的部分：

```text
id
run_uuid
task_id
run_no
status                      queued / running / success / partial_success /
                            failed / stopped / cancelled / interrupted
execution_id
worker_pid
heartbeat_at
progress_stage
progress_steps
started_at
completed_at
duration_ms
error_message
result_summary
log_file
email_lease_id
proxy_lease_id
created_at
data
```

`registration_jobs` 和 `account_action_tasks` 在迁移期可以继续保留，但应变成 `operation_runs` 的兼容投影或读取适配层。新逻辑不能再分别维护两套执行状态。

#### operation_events

统一事件表承载注册阶段、账号操作阶段和资源事件：

```text
id
task_id
run_id
created_at
level
stage
event_type
message
detail
```

注册尝试的远端状态事件仍然可以保留 `registration_attempt_events` 作为领域审计表，但任务中心的展示通过 `operation_events` 统一读取。两者写入必须由同一个应用服务完成，并保持脱敏规则一致。

### 19.3 任务与注册尝试的关系

一次首次注册的关系：

```text
Batch B100
  Task T100: registration -> Attempt A100
    Run R100-1: 首次注册
```

第一次注册跨过远端边界后进程中断：

```text
Task T100: registration -> Attempt A100
  Run R100-1: interrupted, remote_account=request_unknown
  next_actions: [registration_resume, registration_reconcile]
```

用户选择继续原账号：

```text
Task T101: registration_resume -> Attempt A100
  parent_task_id = T100
  Run R101-1: 使用原邮箱和已保存密码恢复
```

注册核心成功后补跑 Codex：

```text
Task T102: codex_retry -> Account U100
  parent_task_id = T100
  Run R102-1: Codex OAuth
```

账号页打开“任务实例”时，应能看到 T102；注册页打开“任务记录”时，也应能沿 T100 的任务链看到 T102。两处显示的是同一条数据，不复制任务。

### 19.4 任务状态和目标状态分开显示

列表中的“失败”只能说明本次执行失败，不能说明远端账号不存在。因此任务列表每行显示两组信息：

```text
执行状态：执行中 / 已完成 / 已失败 / 已停止 / 已中断
目标状态：未开始 / 远端状态待确认 / 注册核心已完成 / 账号可用 / 需要人工处理
```

示例：

| 执行状态 | 目标状态 | 用户动作 |
| --- | --- | --- |
| 已失败 | 尚未跨创建边界 | 重新注册 |
| 已中断 | 远端账号状态待确认 | 继续原账号 / 人工对账 |
| 已失败 | 注册核心已完成 | 补跑 Codex、2FA 或套餐 |
| 已完成 | 账号仍缺 2FA | 重试 2FA |
| 已完成 | 账号可用、Codex 失败 | 补跑 Codex |
| 已停止 | 远端状态待确认 | 不允许新注册，只能恢复或对账 |

内部的 `request_unknown`、`remote_account_state` 和 `local_account_state` 不直接作为主要中文标签展示，统一映射为“远端状态待确认”“本地账号未落库”“需要人工处理”等用户可理解的状态。

## 20. 信息架构和页面展示

### 20.1 入口原则

保留注册页和账号页的上下文入口，但所有入口进入同一个任务中心组件：

```text
注册
  - 新建注册
  - 当前批次
  - 任务记录       -> /tasks?scope=registration

账号
  - 账号列表
  - 任务实例       -> /tasks?scope=account&account_id=...

任务中心
  - 全部任务
  - 注册
  - 账号操作
  - 批次
  - 待处理
```

“任务记录”和“任务实例”是页面上下文名称，不是两个后端对象。用户从账号列表点击“任务记录”时，只是打开统一任务中心并自动带上账号筛选。

不建议把注册任务、Codex 任务、查活任务、AT 刷新任务分别放在三个互不关联的页面。它们在数据库里是不同 `task_type`，在用户界面上属于同一个“任务中心”。

### 20.2 任务中心列表

任务中心采用面向操作人员的密集表格，不展示内部表名和过多 JSON 字段。

顶部显示四个摘要：

```text
执行中
待处理
最近失败
今日完成
```

工具栏提供：

- 范围：全部、注册、账号操作。
- 状态：执行中、待处理、已完成、部分完成、失败、已停止、已中断。
- 动作：首次注册、继续原账号、Codex、2FA、套餐、查活、AT 刷新等。
- 目标：邮箱、账号 ID、批次 ID。
- 来源：手动、注册后自动、任务恢复、批量操作、定时任务。
- 时间范围和“只看需要处理”。

列表列建议如下：

```text
状态 | 动作 | 目标 | 当前阶段 | 目标状态 | 最近执行 | 创建时间 | 操作
```

每行展示：

- 状态徽标：任务执行状态。
- 动作名称：例如“继续原账号”“补跑 Codex”。
- 目标：邮箱或账号，第二行显示账号 ID、attempt ID 或批次。
- 当前阶段：来自最近执行实例，例如“等待邮箱验证码”“OAuth 授权”。
- 目标状态：例如“远端状态待确认”“注册核心已完成”。
- 最近执行：`第 2 次执行 · 失败 · 12s`，点击可展开历史。
- 操作：查看详情、停止、执行明确动作。

注册页的“任务记录”默认隐藏与账号日常维护无关的查活、AT 刷新等动作；任务中心“全部”可以查看全部。

### 20.3 任务详情页

注册任务和账号任务使用同一个详情布局，内容按目标类型动态显示。

#### 顶部摘要

```text
继续原账号                         需要处理
test@example.com · Account #123    远端账号状态待确认
批次 B100 · 父任务 T100 · Attempt A100
```

右侧只显示当前允许的操作：

- 继续原账号。
- 人工标记已确认或未创建。
- 补跑 Codex。
- 重试 2FA。
- 查看账号。
- 停止当前执行。

按钮必须来自 `next_actions`。对于远端状态未知的任务，不能显示普通“重新注册”按钮。

#### 注册生命周期面板

注册目标显示一条简化生命周期：

```text
邮箱领取 -> 身份创建 -> 账号创建 -> Token 落库 -> 账号配置 -> Codex
```

每个节点显示：

- 未开始。
- 执行中。
- 已完成。
- 失败。
- 结果待确认。
- 不适用。

2FA、套餐、Flow 放在“账号配置”和“增强能力”分组中，不与注册核心阶段混成一条成功/失败状态。

#### 执行历史

执行历史显示所有 `operation_runs`：

```text
第 1 次执行 失败      代理连接断开      2026-08-21 15:01
第 2 次执行 中断      进程重启          2026-08-21 15:05
第 3 次执行 执行中    继续邮箱验证      2026-08-21 15:12
```

每个执行实例可以展开自己的进度和日志，但不能覆盖任务的当前目标状态。

#### 资源状态

资源区域只显示对恢复有帮助的信息：

```text
邮箱：已消耗 · Outlook · 支持重启恢复
代理：已释放 · 1024Proxy · 最近出口区域
```

不在普通页面展示邮箱池凭据、完整代理认证 URL 或内部客户端上下文。

#### 事件时间线

统一展示任务事件、注册检查点、账号操作阶段和恢复动作。事件按时间倒序或正序切换，但不再要求用户在“注册日志”和“账号任务日志”两个弹窗之间来回寻找。

### 20.4 账号页的任务实例

账号页不再单独渲染一套任务表，而是复用任务中心组件：

- 默认筛选 `target_type=account` 和当前账号 ID。
- 显示注册任务产生的后处理子任务。
- 显示 Codex、2FA、套餐、查活、AT 刷新和封号邮件任务。
- 支持从账号状态直接创建明确动作。
- 创建后跳转到统一任务详情，而不是只显示一个“补跑中”字段。

账号列表中保留轻量摘要：

```text
Codex：已失败 · 可补跑
2FA：未完成 · 可补齐
最近任务：Codex 补跑失败 · 5 分钟前
```

点击“任务”进入统一任务中心，不在账号行内嵌套完整任务表。

## 21. 注册、重跑和补跑的统一流程

### 21.1 首次批量注册

用户提交 20 个账号时：

```text
创建 Batch B1
  -> 创建 20 个 registration Task
  -> 每个 Task 创建一个 RegistrationAttempt
  -> 每个 Task 创建 Run #1
  -> worker 执行并持续写入 checkpoint/event
```

用户看到的是一个批次进度页，批次内可以展开任务；任务详情中可以看到执行实例和注册生命周期。

### 21.2 注册失败后的重试

重试不是一个模糊按钮，而是先根据 attempt 状态计算动作：

```text
未跨不可逆边界
  -> registration_new
  -> 同一个 Task 新增 Run，或创建新的重试 Task

已跨边界且邮箱可恢复
  -> registration_resume
  -> 创建子 Task，绑定同一个 Attempt

远端状态未知且缺少恢复条件
  -> registration_reconcile
  -> 创建人工对账 Task，不启动完整注册
```

建议规则：

- 相同动作的网络重试复用原任务，增加新的执行实例。
- 动作语义变化时创建子任务，避免把“重新注册”和“继续原账号”混成同一条历史。
- 原任务永远保留，子任务成功后只更新 attempt 的当前状态，不删除失败历史。

### 21.3 注册核心成功后的后处理

核心账号落库成功后，不再把 Codex 或 2FA 失败显示成“注册不存在”。

```text
Registration Task
  -> core_status=success
  -> 创建 Codex Task（如果配置要求或用户手动补跑）
  -> 创建 2FA / account_setup Task（如果需要）
  -> 创建 plan_check Task（如果异步执行）
```

这些子任务共享 `attempt_id` 和 `account_id`，在注册详情、账号详情和任务中心中都能被定位。

### 21.4 账号页面发起补跑

账号页面的“补跑 Codex”执行以下流程：

```text
用户点击补跑 Codex
  -> 服务端校验账号状态和互斥
  -> 创建 OperationTask(target=account, type=codex_retry)
  -> 关联最近的 registration_task（如果存在）
  -> 创建 Run #1
  -> 更新账号 Codex 投影为 running
  -> 任务结束后更新账号投影和 next_actions
```

账号页面不再直接修改 `codex_status=retrying` 后依赖进程内线程；账号状态和任务状态必须在同一个任务服务中推进。

### 21.5 批量补跑

批量补跑创建一个新的 `operation_batch`：

```text
Batch B2: Codex 补跑
  -> Task T201: account #1, parent=T100
  -> Task T202: account #2, parent=T101
  -> Task T203: account #3, parent=T102
```

批次页显示：

- 总数、执行中、成功、失败、跳过、待处理。
- 当前并发数和已经消耗的邮箱/短信/代理资源。
- 批次停止状态。
- 失败项的统一重跑入口。

批次重跑不会修改原批次的历史结果，而是创建新的批次并链接 `parent_batch_id`。这样用户可以比较两次批量操作的结果。

### 21.6 进程恢复

进程恢复创建 `created_by=recovery` 的任务或执行实例，但不伪造用户主动重试：

```text
发现旧 Run 中断
  -> 收口旧 Run=interrupted
  -> 根据 Attempt/Account 状态计算 next_actions
  -> 可安全继续时创建 recovery Run
  -> 需要用户选择时创建 attention_required Task
```

恢复后的任务必须在详情中显示“由进程恢复产生”，让用户知道它不是一次新的注册提交。

## 22. API 设计

### 22.1 统一查询

新增统一查询接口：

```text
GET /api/tasks
GET /api/tasks/{task_id}
GET /api/batches
GET /api/batches/{batch_id}
```

查询参数：

```text
scope=all|registration|account|attention
task_type=
status=
target_type=
target_id=
account_id=
attempt_id=
batch_id=
q=
date_from=
date_to=
```

详情响应统一返回：

```json
{
  "task": {},
  "target": {},
  "batch": {},
  "registration_attempt": {},
  "latest_run": {},
  "runs": [],
  "events": [],
  "resources": {},
  "lifecycle": {},
  "next_actions": []
}
```

### 22.2 统一动作

```text
POST /api/tasks/{task_id}/actions
Body: {"action": "registration_resume"}

POST /api/batches/{batch_id}/actions
Body: {"action": "stop" | "retry_failed"}
```

服务端必须校验动作是否在当前 `next_actions` 中。前端提交非法动作时返回 `409`，同时返回当前状态和允许动作。

现有接口兼容映射：

```text
/api/jobs                       -> /api/tasks?scope=registration
/api/jobs/{id}/retry            -> /api/tasks/{id}/actions
/api/jobs/retry-bulk            -> /api/batches + actions
/api/account-tasks              -> /api/tasks?scope=account
/api/account-tasks/{id}/retry   -> /api/tasks/{id}/actions
```

兼容接口只负责参数转换，不能继续保留独立业务判断。

## 23. 统一设计后的关键原则

1. 用户看到的是“任务”，系统内部才有“执行实例”。
2. 注册和账号操作使用同一个任务中心，区别只在目标对象和动作类型。
3. 注册尝试是业务生命周期，任务是对它执行的一次动作，账号是后处理目标。
4. 重试同一动作增加执行实例，改变动作创建子任务。
5. 批次是任务集合，不是多个独立请求的前端包装。
6. 任务的成功与否不覆盖注册尝试和账号的真实状态。
7. 页面显示“下一步动作”，不让用户根据“失败”自行猜测该重新注册还是继续原账号。
8. 注册页和账号页可以有不同筛选，但不能有不同事实来源。

## 24. 统一任务模型的实施顺序

1. 固定术语：批次、任务、执行实例、事件、注册尝试、账号。
2. 在现有数据库上增加 `operation_batches`、`operation_tasks`、`operation_runs`、`operation_events` 的兼容表或投影。
3. 先做统一只读 API，把现有注册任务和账号任务映射到同一返回结构。
4. 任务中心先复用现有 UI，通过 `scope` 实现注册页和账号页的上下文入口。
5. 将注册任务迁移为 `operation_task + operation_run`。
6. 将 Codex、2FA、套餐和其它账号操作迁移为同一模型。
7. 接入显式动作和批次操作，删除前端对 `retry_action`、`codex_status` 的自行推断。
8. 稳定运行后，再移除 `/api/jobs`、`/api/account-tasks` 的独立实现和进程内互斥。

在统一任务模型完成前，不应先继续增加新的任务类型或新的任务列表页面，否则会继续扩大两套体系的差异。
