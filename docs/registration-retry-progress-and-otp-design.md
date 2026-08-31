# 注册重试、阶段耗时与 OTP 证据链优化设计

状态：Implemented（2026-08-28，代码、测试与本地 WebUI 回归完成；新 OTP 证据将在后续真实任务中产生）

日期：2026-08-28

适用范围：注册批次进度、自动换线重试、人工单任务/批量重试、RegistrationAttempt/Run 事件、iCloud HME 转发收件与 OTP 失败分类。

关联设计：`docs/registration-state-refactor-design.md`、`docs/registration-refactor-master-design.md`。

## 1. 背景与现场证据

本设计来自批次 `20260828-111136-c069c34d` 的三类真实问题。

### 1.1 自动换线后阶段耗时互相重叠

批次第 5 项、任务 `#749` 的完整执行时间为 `11:11:39 -> 11:18:47`，总耗时 7 分 08 秒。第一次线路在 `11:16:18` 失败后自动换线，第二次执行成功。

当前 `progress_steps` 每个阶段只有一组 `started_at/completed_at`。同一阶段第二次进入时保留第一次的开始时间，第二次成功时覆盖结束时间，因此出现：

| 阶段 | 当前错误区间 | 页面显示 |
|---|---|---:|
| 准备邮箱 | 11:11:40 -> 11:16:27 | 4 分 47 秒 |
| 启动浏览器 | 11:12:17 -> 11:16:38 | 4 分 21 秒 |
| 打开注册页 | 11:12:40 -> 11:16:48 | 4 分 08 秒 |
| 提交邮箱 | 11:13:33 -> 11:17:04 | 3 分 31 秒 |

这些区间横跨两次线路尝试且彼此重叠，不能相加，也不是单阶段真实耗时。

### 1.2 两条 OTP 失败任务的邮件证据

原批次第 7、9 项分别是任务 `#751`、`#753`，均已完成密码提交并明确停留在 OpenAI 邮箱验证码页。两条任务都执行了初次等待和两次页面“重新发送”点击，但在各自约 4 分钟预算内没有从 Gmail 收到目标别名的新 OpenAI OTP 邮件。

随后人工点击“继续邮箱验证”生成 `#755`、`#756`：

- `#755` 在再次提交邮箱后的补跑等待窗口内发现新的 OTP 邮件，最终成功；
- `#756` 在再次提交邮箱后的补跑等待窗口内发现两封新的 OTP 邮件，最终成功；
- 当前 Gmail 中没有发现属于两条原始等待窗口的匹配 OTP 邮件，只有补跑时间附近的新邮件及成功后的 MFA 通知。

因此当前证据支持：

1. 浏览器确实进入了正确的验证码页，目标邮箱也正确，主流程导航没有走错；
2. Gmail IMAP 和目标别名匹配链路可用，因为补跑可以很快取到新码；
3. 原始三轮请求没有产生可在 Gmail 中找到的匹配邮件，问题更接近 OpenAI 发送/限流、iCloud 转发投递，或页面 resend 点击未被后端接受；
4. 当前代码只证明“点击了 resend 控件”，没有记录网络响应、按钮冷却或成功提示，因此不能进一步断言 OpenAI 后端确实接受了每次 resend；
5. IMAP 读取目前把邮件 `Date` 头当作 `receivedDateTime`，没有使用 IMAP `INTERNALDATE`。这不构成本次两条失败的直接证据，但可能让延迟投递邮件被错误排除，必须一并修正。

### 1.3 人工重试被显示成新的单任务批次

单任务接口调用 `retry_job()` 时没有传 `batch_id`。`create_retry_job()` 随后用新任务 UUID 作为默认批次 ID，所以 `#755`、`#756` 各自成为一个新的单任务批次。

底层创建新的不可变执行记录是正确的：原失败日志、错误和耗时不能被覆盖。但 UI 把“执行记录”和“原批次中的逻辑任务项”当成同一个概念，导致补跑从原批次消失。

此外，`#755/#756` 与原任务共享 RegistrationAttempt。原 Attempt 已到 `postprocessing`，补跑重新经过 `auth_started/otp_started` 时被当前单调检查点逻辑拒绝，日志持续出现“检查点只能向前推进”。补跑虽然靠兼容任务生命周期完成，但 RegistrationRun 的 `started_at` 和阶段事实没有正确落下。

## 2. 设计目标

1. UI 明确区分自动换线、人工重试以及当前是第几次执行。
2. 每次阶段执行拥有独立起止时间，不再跨自动重试或人工重试拼接。
3. 人工重试默认回到原批次、原序号、原任务卡片，不增加批次总数。
4. 原执行记录、日志和错误保持不可变；“在原任务上重试”是 UI 聚合，不是覆盖历史行。
5. OTP 失败能够区分请求未确认、邮件未投递、收件链路故障、匹配过滤错误和验证码无效。
6. RegistrationAttempt 表示业务安全边界，RegistrationRun 表示一次执行；补跑的早期阶段事件不能被 Attempt 的最高检查点拒绝。

## 3. 非目标

- 本轮不改变 OpenAI 页面操作策略、邮箱供应商选择或代理供应商。
- 不把账号密码、OTP、Token、Cookie、完整邮件正文或代理凭据写入事件表。
- 不删除或覆盖现有 `registration_jobs`、日志、RegistrationAttempt/Run/Event 历史。
- 不把人工重试直接复用原 `registration_jobs.id`。

## 4. 统一层级模型

```text
RegistrationBatch                 用户发起的一批逻辑任务
  +-- TaskSlot                    批次中的固定位置，例如 #7
        +-- RegistrationJob/Run   一次真实执行；人工重试新增一条
              +-- RouteAttempt   同一次执行内的自动换线/重建浏览器
                    +-- StageOccurrence  某阶段的一次进入与退出
```

### 4.1 TaskSlot

TaskSlot 是 UI 概念，不必立即新增表。可用以下稳定键投影：

```text
slot_root_job_id = COALESCE(root_job_id, id)
slot_batch_id    = 根任务 batch_id
slot_index       = 根任务 batch_index
```

一个 TaskSlot 可以包含多条 `registration_jobs`，但批次总数只计算 Slot 数量。

### 4.2 RegistrationJob / RegistrationRun

- 人工点击重试继续创建新的 job/run，保留独立日志和错误；
- 新 run 继承原 Slot 的批次、序号和批次大小；
- `retry_attempt` 表示人工执行次数，首次为 0；
- `RegistrationRun.status` 创建后立即进入 `running`，写入真实 `started_at`；
- 同一 Slot/Attempt 同时只允许一个活跃 Run。

### 4.3 RouteAttempt

RouteAttempt 表示同一 Run 内部的自动重试，例如：

- 首条代理失败后换线；
- 丢弃临时 Roxy Profile 后重建；
- 明确允许的同一安全检查点恢复。

字段至少包括：

```text
run_id
route_attempt_no
retry_kind            initial / proxy_rotation / browser_recreate / navigation_recover
retry_reason_code
started_at
completed_at
status
```

若暂不新增表，可先作为 `registration_events` 的结构化事件落库；不能只存在日志文本中。

RouteAttempt 同时保存当次脱敏邮箱快照。自动换线安全释放旧邮箱并重新领取新邮箱时，任务卡片显示当前邮箱，尝试历史说明“换线并重新领取邮箱”，避免用户误以为整个 Slot 始终绑定同一个地址。

### 4.4 StageOccurrence

每次进入阶段都生成独立 occurrence：

```text
run_id
route_attempt_no
stage
occurrence_no
state_before/state_after
started_at/completed_at/duration_ms
wait_reason
detail（脱敏）
```

`progress_steps` 降级为列表页投影，只保存“当前/最新 occurrence 摘要”，不再作为多次执行的完整事实来源。

## 5. 阶段耗时语义

### 5.1 计时规则

1. `running` 从非 running 状态进入时创建新的 occurrence；重复上报同一个 running 状态只更新详情，不重置计时。
2. 进入后续阶段时关闭当前 occurrence。
3. 自动换线开始时关闭当前 RouteAttempt 的所有未结束 occurrence，并以失败/重试状态收口。
4. 新 RouteAttempt 的阶段必须重新计时，不复用旧 `started_at` 或 `completed_at`。
5. `完成` 节点显示 Run 总耗时，文案改为“本次总耗时”，避免被理解为普通阶段并参与求和。

### 5.2 UI 显示口径

任务卡片默认显示最新一次 RouteAttempt 的阶段耗时；顶部同时显示：

```text
本次执行 2分07秒 · 累计执行 7分39秒
自动换线 1 次 · 人工重试 1 次
```

展开“尝试记录”后显示：

```text
第 1 次执行  #751  部分成功  5分32秒  邮箱验证码未收到
第 2 次执行  #755  成功      2分07秒  继续邮箱验证
  - 线路尝试 1  成功
```

自动换线任务类似 `#749` 显示：

```text
#5  成功  自动换线 1 次
线路尝试 1：提交邮箱失败，已更换代理
线路尝试 2：成功
```

批次统计按每个 Slot 的最新有效状态计算，不能把原失败行和成功补跑行同时计数。

自动重试产生的中间错误进入 RouteAttempt 事件和 `warning_summary`，最终成功后不应继续占用任务级 `error_message`。例如 `#749` 应显示“成功 · 自动换线 1 次”，而不是同时携带一个看似仍然有效的注册错误。

## 6. 原批次内重试语义

### 6.1 默认行为

- 单任务重试：继承根任务的 `batch_id/batch_index/batch_size`；
- 同批次批量重试：每个任务回到自己的原 Slot；
- 跨批次批量重试：按来源批次分别更新，接口返回 `affected_batch_ids`；
- 只有用户明确选择“复制为新批次重跑”时才创建新批次。

### 6.2 API 调整

`POST /api/jobs/<id>/retry` 默认：

```json
{
  "mode": "in_place"
}
```

响应增加：

```json
{
  "source_job_id": 751,
  "retry_job_id": 755,
  "root_job_id": 751,
  "batch_id": "20260828-111136-c069c34d",
  "batch_index": 7,
  "retry_attempt": 1
}
```

`POST /api/jobs/retry-bulk` 不再预先生成统一 `retry_batch_id`；默认逐条继承来源批次。显式新批次使用独立动作和 `mode=new_batch`，不能由普通“重试”按钮隐式触发。

### 6.3 批次投影

批次查询先按 Slot 分组，再为每个 Slot 选择：

1. 活跃 Run；
2. 否则最新成功 Run；
3. 否则最新终态 Run。

返回对象增加：

```text
root_job_id
current_job_id
retry_count
internal_retry_count
attempts[]（摘要，详细日志按需加载）
```

批次下拉框中的 `total/success/failed/active` 均按 Slot 数量聚合。

### 6.4 历史兼容

现有 `#755/#756` 等单任务重试批次不改写数据库。读取时通过 `root_job_id -> 根任务 batch_id` 计算 `effective_batch_id`，将其投影回原批次。原始 `batch_id` 仍保留用于审计。

## 7. RegistrationAttempt 与 Run 的检查点处理

Attempt 检查点继续单调前进，表示已经达到的最高安全边界；Run 阶段允许从较早位置恢复。

调整原则：

1. 所有阶段变化先写 Run/Stage 追加事件；
2. 只有目标检查点高于 Attempt 当前值时才推进 Attempt；
3. 目标检查点低于当前值时不报错、不回退 Attempt，只记录“本 Run 正在恢复较早步骤”；
4. `postprocessing/completed` 的 Attempt 可以产生 `registration_resume` Run；
5. Run 必须记录真实 `started_at/completed_at/duration_ms`，不能只在结束时补终态。

这样既保持不可逆安全边界，又能完整记录补跑经过登录、OTP、资料和 Token 阶段的事实。

## 8. OTP 证据链与失败分类

### 8.1 每次请求/重发记录

新增脱敏事件 `otp_request`：

```text
run_id / route_attempt_no
otp_request_no
request_kind          initial / resend / resume_login
requested_at
page_url_path
ui_control_identity
ui_ack                confirmed / unconfirmed / rejected
http_status           可获得时记录；不保存请求体、Cookie、Token
```

“点击成功”不等于“发送成功”。至少观察一种确认信号：按钮进入冷却/disabled、成功提示、相关网络请求返回 2xx，或页面状态明确更新。没有确认信号时写 `ui_ack=unconfirmed`。

### 8.2 邮件时间与匹配

IMAP 读取同时保存：

- `sent_at`：邮件 `Date` 头，仅作参考；
- `received_at`：IMAP `INTERNALDATE`，用于任务时间窗判断；
- `first_seen_at`：本程序第一次看到该 Message-ID 的时间；
- 脱敏 Message-ID 指纹、目标别名匹配结果、OpenAI 邮件识别结果、是否提取到 OTP。

不能再把 `Date` 头直接当 `receivedDateTime`。重发后按 `received_at/first_seen_at` 选择新邮件，并保留每个 request window，避免延迟投递邮件被静默过滤。

### 8.3 失败分类

| 分类 | 判定 |
|---|---|
| `otp_request_unconfirmed` | 页面点击完成，但没有 UI/网络确认 |
| `otp_delivery_missing` | 请求已确认，收件连接健康，预算内没有匹配邮件 |
| `otp_mailbox_unavailable` | IMAP/Butler 持续连接或读取失败 |
| `otp_recipient_mismatch` | 收到 OpenAI 邮件但目标别名不匹配 |
| `otp_filtered_by_window` | 邮件存在，但因错误时间口径被过滤 |
| `otp_invalid_or_expired` | 已取得并提交，页面明确返回错误或仍停留验证码页 |

当前 `#751/#753` 应暂时展示为：

```text
验证码邮件未到达；页面已进入验证码步骤，收件链路可用，重发是否被 OpenAI 接受缺少确认
```

不能只显示笼统的“验证码超时”。

## 9. 数据与隐私边界

允许持久化：阶段、状态、毫秒耗时、重试类型、脱敏原因、URL host/path、HTTP 状态、邮件时间、Message-ID 哈希。

禁止持久化：OTP 数值、密码、Token、Cookie、Authorization、完整请求/响应体、完整邮件正文、代理凭据。

普通模式只记录上述轻量元数据；完整 Debug 模式继续负责更丰富但经过脱敏的网络/页面现场。

## 10. 测试设计

必须增加以下回归场景：

1. 同一 Job 自动换线两次，同名阶段生成两个 occurrence，第二次耗时不包含第一次。
2. `#749` 时间线 fixture：阶段耗时不重叠，Run 总耗时仍为 7 分 08 秒。
3. 单任务重试继承原 batch/slot，但创建新的 job/run 和独立日志。
4. `#751 -> #755`、`#753 -> #756` fixture：批次仍为 10 个 Slot，#7/#9 显示“重试 1 次后成功”。
5. 批次计数只看 Slot 当前状态；原失败和补跑成功不重复计数。
6. 同一 Slot 已有活动 Run 时重复点击返回 reused，不创建并发补跑。
7. 跨批次批量重试分别回写来源批次；显式 `new_batch` 才创建新批次。
8. Attempt 已到 `postprocessing` 时启动 `registration_resume`，Run 早期阶段事件可写入且 Attempt 不倒退。
9. RegistrationRun 开始时写入 `running/started_at`，结束时正确计算 duration。
10. 邮件 Date 早于请求时间但 INTERNALDATE 晚于请求时间时仍可被发现。
11. resend 只有 DOM click、没有确认信号时分类为 `otp_request_unconfirmed`。
12. IMAP 健康但无匹配邮件时分类为 `otp_delivery_missing`，连接异常单独分类。

## 11. 推荐实施顺序

### 阶段 A：事实与计时

- 修正 RegistrationRun 启动状态和时间；
- 将轻量 stage 事件写入 PostgreSQL；
- 增加 RouteAttempt/StageOccurrence；
- 修正 `progress_steps` 投影和完成节点文案。

### 阶段 B：原批次重试与 UI

- 单条/批量重试继承 Slot；
- 批次按 Slot 聚合状态和数量；
- 增加自动重试、人工重试徽标与尝试历史；
- 历史独立重试批次通过 effective batch 投影兼容。

### 阶段 C：OTP 证据链

- 使用 IMAP INTERNALDATE；
- 记录 initial/resend 请求确认；
- 落地 OTP 失败分类和 UI 文案；
- 补失败诊断接口的轻量证据摘要。

### 阶段 D：回归与部署

- 使用 749、751/755、753/756 脱敏 fixture 回放；
- 跑存储、任务进度、重试、Roxy OTP 和 API/UI 全套测试；
- 部署后只做一条低风险真实任务验证，再恢复批量并发。

## 12. 验收标准

- 任一阶段显示的时间都能指向唯一 Run、RouteAttempt 和 occurrence。
- 自动换线后，阶段时间之和不再因跨尝试重叠而大于本次执行时间。
- 原批次失败任务补跑后仍位于原序号，批次总数不变，并可展开查看每次执行。
- UI 能一眼看到“自动换线 N 次”“人工重试 N 次”和最终成功/失败。
- OTP 失败至少能区分请求未确认、投递未到、收件故障和验证码无效。
- 补跑不会再产生 Attempt 检查点倒退错误，Run 有完整开始、结束和阶段事件。
