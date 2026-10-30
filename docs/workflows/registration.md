# 注册流程

本文说明五种注册驱动共用的任务、身份、资源和结果边界。具体请求顺序由各驱动实现；修改前按[功能地图](../architecture/functional-map.md)定位代码与测试。

## 入口与分层

```text
WebUI：POST /api/jobs
  → core/registration/service.py
  → 任务及配置快照、原子抢占、资源领取
  → core/registration/dispatcher.py
  → 选定驱动
  → 核心账号保存、可选后处理、任务及资源收口

CLI：main.py
  → dispatcher
  → core/registration/standalone.py
  → 持久化 Attempt / Run 上下文及同一驱动
```

`dispatcher.run_registration()` 优先读取本次任务 `registration_options` 中的驱动快照，再读取配置。已经排队的任务不会因为配置页后续改动而隐式换驱动。

| `REGISTRATION_DRIVER` | 实现目录 | 执行方式 |
| --- | --- | --- |
| `roxy` | [registration/roxy](../../core/registration/roxy/__init__.py) | 本地 RoxyBrowser + Selenium |
| `roxy_oss` | [registration/roxy_oss](../../core/registration/roxy_oss/__init__.py) | 开源页面辅助与本地 Roxy 生命周期 |
| `protocol` | [registration/protocol](../../core/registration/protocol/__init__.py) | 本地 HTTP 协议流程 |
| `protocol_oss` | [registration/protocol_oss](../../core/registration/protocol_oss/__init__.py) | 开源 Protocol 适配 |
| `protocol_oss_2` | [registration/protocol_oss_2](../../core/registration/protocol_oss_2/__init__.py) | 开源 Protocol-2 适配 |

`api/http` 是本地 Protocol 别名，`roxybrowser/fingerprint/browser` 是本地 Roxy 别名。未知驱动明确报错，不自动换成其他实现。公共编排、恢复和后处理位于 `core/registration/` 根部；跨业务认证能力位于 `core/auth/`。驱动支持差异见[认证支持矩阵](account-auth-support-matrix.md)。

## 提交与资源领取

WebUI 创建 `registration_jobs`，由执行器按数据库条件抢占任务；Attempt 保存原始注册意图，Run 保存本次执行。任务、线程池和取消上下文由服务层管理，路由不直接执行注册主体。

网络配置决定直连或代理路线。启用代理时，业务从统一代理库存领取检测通过的租约；供应商提取、出口检测和补货由后台供给完成。供应商粘性窗口、新租约和新出口 IP 是不同事实，以实际检测记录为准。

新注册的自动邮箱只来自已导入的五个本地池：Outlook、通用 API、域名邮箱、iCloud 隐藏邮箱和 Butler 导入邮箱。空库存需要手动导入，不远端买号、自动生成或换来源补领。显式指定来源时只领取该来源；兼容调用未指定来源时按配置顺序选择。关闭自动邮箱时沿用手动邮箱与人工 OTP 入口。

领取保存稳定 acquisition、owner 和完整邮箱。续跑使用原地址及其固定收件连接；历史结果未知的领取不能通过换领新地址跳过。统计和领取共用库存资格规则，详细导入及收件规则见[邮箱资源与取码](email-resources.md)。

## 驱动执行与检查点

一次注册通常涉及会话与网络预检、邮箱提交、密码或验证码挑战、必要的资料提交、OAuth 回调和 ChatGPT session。服务端可能直接返回已认证回调、MFA、已有账号密码或邮箱验证；这些分支必须结合原意图和已保存凭据判断，不能把所有落地页都当成新账号。

本地 Protocol 在密码请求前保存 prepared/started 检查点，确认后记录 confirmed，并支持沿原邮箱、密码和 Attempt 恢复。浏览器驱动保存密码、Profile 和认证阶段检查点。具体驱动的恢复能力以其实现及矩阵为准，不把一个驱动的检查点保证推广到全部驱动。

邮箱验证码按发码时间、完整收件身份和已保存游标筛选。取到候选码不表示远端接受；提交结果未知要保留候选与执行证据。重发、退避与网络请求受阶段预算约束，底层同步请求仍受 connect/read 超时限制，不能保证任意在途请求立即取消。

协议回调成功后，session 获取可以在既有边界内重试；回调或密码提交结果未知时，不根据异常文本重新提交远端写操作。`protocol_oss_2` 的 `invalid_state`、`user_already_exists` 等结果应保留账号身份与待确认状态，不能仅由 HTTP 错误推断账号未创建。

Roxy 按账号复用绑定 Profile，浏览器、代理和诊断现场均有明确 owner。现场保留和释放沿调试策略执行，不以强制关闭浏览器替代任务收口。

## 核心账号与后处理

`create_account` 被接受只说明创建请求已返回；应继续核对 ChatGPT session 的 `accessToken`、持久化账号及任务关联。核心账号、完整 session 和凭据检查点应与后处理结果分开判断。

| 事实 | 核对位置 |
| --- | --- |
| 注册意图和本次执行 | `registration_attempts`、`registration_runs`、`registration_jobs` |
| 核心账号及 Token | `registered_accounts`、账号关联、核心保存结果 |
| 2FA、Codex、套餐结果 | 各步骤与对应凭据、任务和状态字段 |
| 实际执行顺序与失败位置 | Run 事件、进度快照和关联日志 |

2FA、Codex、套餐及 Flow 都有各自成功、跳过和失败语义。已经保存账号时，后置失败不能抹掉账号或让已用邮箱回到新库存。不同驱动的整体返回字段和后处理顺序有差异，不能只凭 `success` 或页面红绿判断核心账号事实。

本地 Protocol 的 Flow 调用位于 `core/registration/protocol/__init__.py`，通过 `core/integrations/flow_trigger.py` 执行。它在账号保存后运行，失败不撤销核心账号，也不能据此假设其他驱动具有同一后处理。

## 失败、停止与续跑

邮箱领取后的释放必须确认远端未创建账号、没有本地账号或保留身份、没有未知提交，并满足来源自己的状态条件。已使用、已创建或待确认的身份不能回到可重新分配库存。代理、浏览器和线程上下文按各自租约与 `finally` 收口，不能用统一清理覆盖不同资源的恢复语义。

停止使用协作式取消和安全检查点。远端在途请求不因本地停止就自动变成“未提交”；`request_unknown` 等状态保留核验围栏。

重跑入口通过 `get_retry_info()` 综合账号、检查点和后置状态决定完整注册、原意图续跑、Codex 或 2FA 补跑。已有账号优先执行相应账号操作；原任务链保留 `root_job_id/parent_job_id/retry_attempt`，新执行保留独立 Run，不覆盖旧事件。批次内已领取邮箱的去重记录不会因为一次失败释放而删除。

## 排查与验证

1. 从 `registration_jobs` 的类型、状态和 `account_id` 找到对应 Attempt / Run。
2. 看当前线路的阶段事件、失败原因和原始检查点，区分执行失败、后置失败与结果未知。
3. 核对账号、Token、2FA/Codex、邮箱占用和代理租约，避免仅凭最终文案判断。
4. 通过同一 Run 的日志及诊断资源确认请求是否已提交；普通日志位于 `logs/tasks/<task_uuid>/runs/<run_no>-<run_uuid>/run.jsonl`。
5. 依据现有续跑入口处理，不手工重写历史任务或复用已发行邮箱。

步骤实例、线路和日志关联契约见[统一任务步骤与日志](../architecture/task-observation.md)。测试通过[统一隔离入口](../development/release-verification.md)运行，按功能地图选择驱动、恢复、邮箱释放和存储测试；静态测试不替代已授权范围内的真实流程验收。
