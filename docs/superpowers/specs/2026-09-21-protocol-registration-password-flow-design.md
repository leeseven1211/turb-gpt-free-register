# 协议注册密码主链路设计

> 历史说明：本文记录当时的设计或实施计划，不代表当前运行状态；现行行为与约束以 README、AGENTS.md 和当前代码为准。

## 目标

让 `protocol` 注册驱动覆盖当前 Roxy 成功样本中的密码注册主链路：创建密码、发送邮箱验证、提交 OTP、创建用户、完成 OAuth callback/session、保存账号，并继续复用已有 2FA 和后处理阶段。Roxy 仍作为独立驱动保留，不改变其现有行为。

## 当前证据

- Roxy 脱敏抓包已经确认成功链路包含 `POST /api/accounts/user/register`、`GET /api/accounts/email-otp/send`、`POST /api/accounts/email-otp/validate`、`POST /api/accounts/create_account`、OAuth callback/session 和 MFA 接口。
- `core/openai_auth.py` 已有 Sentinel bundle、密码生成、用户注册、邮箱 OTP 导航、OTP 校验和账号创建 helper。
- `core/registration/protocol.py` 当前只调用邮箱 OTP 分支；`password_enabled` 只写入挑战阶段字段，没有真正提交密码。
- Roxy 现有的邮箱验证中间态保存逻辑绑定了 profile，不适合直接由协议驱动复用。

## 设计

### 1. 协议密码阶段

在 `follow_authorize` 成功后、且仅当 `password_enabled` 为真时：

1. 生成或读取配置密码。
2. 请求一次包含 `username_password_create` flow 的 Sentinel bundle。
3. 以同一 bundle 的 Sentinel/`SO` 上下文调用 `register_user`。
4. 从注册响应中解析 `continue_url`；解析失败、超时或结果不确定时保留 `request_unknown`，不换邮箱、不重新注册。
5. 不调用无密码注册页专用的 `/passwordless/send-otp`；调用 `navigate_email_otp_send`，由 `user/register` 成功后的继续地址触发密码注册的邮箱验证码，进入现有 OTP 等待与校验逻辑。

未启用密码时保留现有邮箱 OTP 入口，避免改变已有兼容路径。

### 2. 邮箱验证中间态

抽取一个与浏览器驱动无关的 checkpoint helper。它必须：

- 首次创建只保存脱敏无关的业务字段、空 access token、密码和 `email_verification_pending` checkpoint。
- 已存在且没有 access token 的同邮箱记录只更新密码/checkpoint，不覆盖已有字段。
- 已存在且已有 access token 时拒绝覆盖，避免把已完成账号降级成待验证状态。
- Roxy 继续记录 profile 信息；Protocol 不虚构 profile 信息。
- 失败时由上层按现有 lease/unknown 规则处理，不把邮箱直接恢复为可用。

### 3. 结果与恢复

- 成功创建账号后沿用现有 `_finalize_registration_session`、持久化、2FA、Codex 和套餐检查逻辑。
- 协议请求超时、响应缺少继续 URL、OAuth callback/session 不完整时，沿用现有 `request_unknown` 分类。
- 本次改动不增加 SQLite、兼容文件状态写入或新的重试策略。
- 待邮箱验证账号的续跑入口必须保持驱动一致；若 Protocol 续跑所需信息不足，必须返回明确的 attention/unknown 结果，不得静默切换到 Roxy 或重新申请邮箱。

## 验证策略

先添加能证明当前缺少密码提交阶段的失败测试，再实现最小代码。验证分三层：

1. helper 单元测试：Sentinel bundle、密码注册、邮箱 OTP 导航和中间态 checkpoint 的调用顺序与覆盖保护。
2. Protocol 编排测试：密码开启/关闭、OTP、callback/session、2FA 后处理和 unknown 分类。
3. 一次真实的单任务 Protocol 脱敏抓包：确认端点顺序、状态码、数据库终态、邮箱租约和账号敏感字段均符合预期；真实运行不使用批量账号，不启用 Codex。

## 非目标

- 不删除或替换 Roxy 浏览器驱动。
- 不把原始 Cookie、Token、OTP、密码、完整代理地址或原始 HAR 写入提交或最终输出。
- 不在没有真实单任务证据时声称“全部协议化”已经完成。
