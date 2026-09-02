# 注册与账号认证协作设计

**日期：** 2026-09-02  
**状态：** 已获准实施

## 目标

把注册、账号登录、查活/刷新 AT、补密码、补 2FA 的认证分支统一成可恢复、可判定、可测试的协作流程：Roxy 负责稳定的浏览器主流程和最终兜底，Protocol 负责明确且可替换的阶段能力。

## 非目标

- 不扫描或修改 PostgreSQL 中的历史账号。
- 不新增账号批量业务入口。
- 不把 Protocol 替换成唯一注册驱动。
- 不在密码、OTP、TOTP、Token、Cookie 或原始响应中记录敏感值。
- 不在远端结果未知时自动重新注册或重复提交同一不可幂等请求。

## 架构边界

```text
业务任务/恢复策略
        ↓
统一认证结果与 checkpoint
        ↓
Roxy 浏览器主流程 ── Protocol 阶段适配器
        │                    │
        └────失败/不支持/未知──┘
```

Roxy 是页面、浏览器 session、密码页、资料页、未知页面和最终 fallback 的权威来源。Protocol 只负责适合接口化的明确阶段，必须通过适配器返回统一结果，不能把供应商响应格式泄漏到业务层。

## 统一认证结果

新增存储无关的结果模型，至少包含：

- `status`：当前认证阶段结果。
- `code`：稳定错误/结果码。
- `auth_method`：`password`、`email_otp`、`totp`、`session` 或 `protocol`。
- `challenge_chain`：已完成的非敏感挑战名称。
- `remote_identity`：`new_candidate`、`existing`、`unknown`。
- `retryable`：是否可以安全重试。
- `roxy_fallback_allowed`：Protocol 失败后是否允许交回 Roxy。
- `next_action`：`continue`、`resume`、`manual_reconcile`、`stop`。

对外序列化只保留上述兼容字段，不复制响应体、Token、回调地址或凭证。

## 认证状态链

所有浏览器登录挑战都按以下顺序重新取页面状态，不以旧 URL 单独判断：

```text
email_submitted
  → password_required → password_verified
  → email_otp_required → email_otp_verified
  → totp_required → totp_verified
  → profile_required
  → authenticated
```

密码、邮箱 OTP、TOTP 可以按远端实际顺序出现。每次提交后都必须重新分类，因此必须支持：

- 密码 → TOTP
- 密码 → 邮箱 OTP → TOTP
- 无密码 → 邮箱 OTP
- 无密码 → 邮箱 OTP → TOTP
- 邮箱 OTP 后直接登录或进入资料页
- 页面未知、请求结果未知

缺少本地密码或 TOTP 时安全停止，不进入手机号步骤，不猜测凭证。

## 远端已有账号协调

普通注册不能把“本地无账号记录”当作“远端无账号”。在邮箱提交和 OTP 后的页面观察中记录：

- `new_candidate`：仍处于可新建账号的资料页。
- `existing`：直接进入已登录、OAuth callback 或已有账号授权态。
- `unknown`：无法确认远端请求结果。

远端已有账号只能进入“协调/补全”语义，不能伪装为新注册成功。结果未知时保留邮箱、账号和 checkpoint，并禁止重新注册。

## Protocol 协作策略

- Protocol 成功：只确认当前阶段成功，之后由业务层继续验证 session/Token。
- Protocol 明确不支持：交回 Roxy；不改变账号核心状态。
- Protocol 明确凭证错误：返回 `password_rejected` / `mfa_rejected`，默认不自动重复提交。
- Protocol 网络或响应不完整：返回 `request_unknown` 或阶段性网络错误，保留 checkpoint。
- 只有配置明确允许时才执行一次安全的邮箱 OTP fallback。

## 账号补全语义

账号补全仍以同一个认证结果模型建立真实登录态，然后按 checkpoint 串行执行：

```text
查活/刷新 AT
  → 登录挑战收口
  → 补密码
  → 补 2FA
  → Codex / 套餐等独立后处理
```

密码设置、2FA Secret 生成和激活必须可恢复。2FA Secret 在远端激活前持久化；密码提交后立即持久化。后处理失败不能回滚已经确认的账号核心状态。

## 错误策略

| 结果 | 处理 |
|---|---|
| `password_rejected` | 标记凭证错误，不自动重试密码，不自动注册 |
| `password_result_unknown` | 保留结果未知，不转成密码错误，不自动重复提交 |
| `email_otp_invalid` | 在同一认证尝试内有限次重新取码 |
| `totp_required` 但无 Secret | 安全停止并标记补全阻塞 |
| Protocol `unsupported` | 交回 Roxy |
| Protocol `request_unknown` | 保留 checkpoint，进入人工协调/恢复 |
| 远端已有账号 | 进入协调或账号补全，不走新建账号 |

## 验收范围

必须有契约测试覆盖：

1. 新账号 Roxy OTP → 资料 → Token。
2. Roxy 密码模式创建密码并恢复。
3. 邮箱 OTP 后直接登录/资料页。
4. 邮箱 OTP 后 TOTP。
5. 有密码无 2FA、有密码有 2FA、无密码无 2FA、无密码有 2FA。
6. 本地缺记录但远端已有账号、远端结果未知。
7. Protocol v2 刷新 AT 的密码、邮箱 OTP、TOTP 和错误分支。
8. 账号补密码、补 2FA 的串行 checkpoint 和失败恢复。
9. 2FA 失败、Codex/套餐失败不回滚账号核心状态。

