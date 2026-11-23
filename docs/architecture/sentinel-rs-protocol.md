# sentinel-rs 子进程协议（v1 草案）

本文定义 Python 桥接与 `sentinel-rs` 原生进程之间的版本化 JSON Lines 协议，用来替换当前
"一次性子进程 + 临时 SQLite 交换"的接入方式。协议的目标只有一个：**把本地持久化放到远端
写动作之前**，同时把 OTP 取码和恢复入口收回 Python 侧。

> 状态：草案（P1 范围已可实施）。上游源码许可仍未确认；实现前需要按
> [rust-kernel-bridge.md](rust-kernel-bridge.md) 的约定固化源码与补丁清单。

## 背景：当前边界的问题

现状是 `email----code_url` 输入、`accounts.db`（临时 SQLite）输出。由此产生三个已知缺口：

1. 密码只在原生进程内存/临时库中；进程异常退出后临时目录被删，远端账号变成"无凭据半成品"。
2. OTP 等待固定在内核里（`OTP_MAX_WAIT`，当前 300 秒），邮箱投递稍慢就整任务失败。
3. 内核已判定"已有账号"但没有把事实传给 Python，重试入口仍会给出"重新执行注册"，必然被上游拒绝。

## 传输与编码

- stdin/stdout 各一条管道，UTF-8，一行一条 JSON 对象，行内不含换行；stderr 仅脱敏诊断。
- 协议消息与普通日志互斥：协议模式下 `[n/10]` 日志改走 `progress` 消息，不再写 stdout。
- 每条消息含 `v`（协议版本）、`exec`（执行标识）、`req`（请求序号）、`seq`（进程内单调序号）、`type`、`data`。
- 单条消息上限 64 KiB；凭据字段（password/code/cookies/access_token）不得出现在 `progress`、`landing`、日志中。
- Python 侧按 `ready.data.capabilities` 决定启用哪些特性；缺失能力时退回 CLI 模式。

## 消息

| 方向 | type | data 关键字段 | 说明 |
| --- | --- | --- | --- |
| P→R | `start` | `action=register\|resume`、`email`、`proxy`、`code_url`、`otp_started_at`、`existing_password?`、`options` | 交付已分配资源；内核不得自行领取邮箱或选择任务 |
| R→P | `ready` | `v`、`build`、`capabilities[]` | 尚未执行任何远端动作 |
| R→P | `landing` | `verdict=new\|existing\|unknown`、`host` | authorize 落地判定，供重试与库存标记 |
| R→P | `checkpoint_prepare` | `kind=password`、`email`、`password`、`challenge_id` | 在发送 `user/register` 之前发出 |
| P→R | `checkpoint_ack` | `challenge_id`、`persisted=true\|false`、`attempt_id`、`error?` | 未收到且 `persisted=true` 时内核禁止发送 `user/register` |
| R→P | `progress` | `stage`、`state`、`detail?` | 有界阶段事件，映射现有阶段表 |
| R→P | `otp_request` | `challenge_id`、`sent_at`、`after_ts` | 请求 Python 用现有邮箱服务取码 |
| P→R | `otp_response` | `challenge_id`、`code?`、`status=ok\|timeout\|malformed` | 超时由 Python 决定；内核不再自带 300 秒窗口 |
| R→P | `submission` | `endpoint`、`sent_at`、`receipt=confirmed\|unknown\|rejected`、`error_code?`、`http_status?` | 对应现有提交回执语义 |
| P→R | `cancel` | `reason` | 请求停止新动作；已发送动作仍按 `submission` 事实处理 |
| R→P | `result` | `created`、`email`、`access_token`、`cookies`、`session_info`、`totp_secret?`、`pending` | 终态；凭据只在私有通道返回 |
| R→P | `result_partial` | `email`、`password?`、`status`、`stage`、`error_code` | 失败时也返回内核已落库事实（P1 的兜底） |

## 顺序约束（核心）

```
start → ready → landing → checkpoint_prepare → checkpoint_ack(persisted) → user/register
```

- Python 在 `checkpoint_prepare` 落库（`save_password_checkpoint(state="prepared")`）后回 ack；
  收到 `submission(confirmed)` 再升为 `confirmed`。
- 任何一步失败，内核发 `result_partial` 并退出，远端动作不发生。
- 密码从生成到落库之间不再存在"只有内核知道"的窗口。

## 与现有 Python 侧的映射

| 现实现 | 协议后 |
| --- | --- |
| `bridge.run_registration` 解析 stdout 阶段 | 读 `progress` 消息，沿用 `_STAGES` 映射 |
| 进程结束后读临时 SQLite | `result` 直接带事实；仍保留一次身份核验（邮箱一致、AT 非空） |
| 失败后 salvage 读临时库 | 正常路径由 `checkpoint_prepare` 保证；salvage 降级为兜底 |
| 内核 `OTP_MAX_WAIT` | `otp_request/otp_response`，窗口由 `core/email` 决定（可配、可宽限重取） |
| 重试入口只看 Attempt 事实 | 增加 `landing=existing` 与 `result_partial.status=pending_otp` 两个事实 |

## 失败与恢复语义

- `receipt=unknown` 表示请求已发出但未取得回执：Python 记录未决提交，禁止自动重放。
- 进程崩溃或管道断开：Python 以最后一条已确认消息为准；已 `checkpoint_ack` 的密码已持久化。
- `cancel` 只阻止新动作；已发送动作等待 `submission`。
- `resume`：`start.action=resume` 携带 `existing_password`；内核从密码校验进入，继续 OTP 与资料步骤。
  缺少密码或身份不匹配时返回 `result_partial`，不改写远端状态。

## 分期

| 期 | 范围 | 交付判据 |
| --- | --- | --- |
| P1 | `start/ready/progress/checkpoint_prepare/ack/result_partial` | 失败任务 100% 有本地密码；请求序列与 CLI 模式逐条一致 |
| P2 | `otp_request/otp_response` | 取码窗口可配；不再出现"300 秒到点即失败" |
| P3 | `landing` + Python 侧服务事实 | 已建号邮箱不再出现在"重新执行注册"入口 |
| P4 | `resume`（已落地：跨内核） | 有密码的失败任务可继续，不重复建号；Rust 无续跑入口，续跑自动交给 `protocol_oss_2` |

## 跨内核续跑（P4 实现说明）

Rust 内核没有原身份续跑入口，因此 `registration_resume` 在源驱动为 `sentinel_rs` 时自动改用
`protocol_oss_2` 执行：复用 Attempt 已保存密码，按真实上游步骤（authorize → 已有账号登录 →
邮箱验证码 → create_account → 会话）继续，不重新创建账号。实测该场景下上游会直接要求邮箱验证码，
只有验证码通过与资料完成后才发会话；不再出现“重复建号被拒 400”。

续跑成功时，如果本地检查点的密码状态本来就是 `confirmed`（即密码曾由 `user/register` 接受），
不再把同一密码降级成“未确认”。

## 兼容与回滚

- 同一个二进制：`SENTINEL_PROTOCOL=1` 开启协议模式，默认关闭。
- `ready.capabilities` 缺 `checkpoint` 时 Python 退回 CLI 并记录告警。
- 回滚只需关环境变量，无需回退二进制。

## 验收

1. `--dry-run` 输出的请求计划（method + url + label）在协议模式与 CLI 模式逐行一致。
2. 契约测试：版本协商、ack 延迟/拒绝、管道半关闭、取消、超时。
3. 灰度：同一批次 20 并发跑改前/改后，比对 p50/p95、成功率与失败原因分布。
