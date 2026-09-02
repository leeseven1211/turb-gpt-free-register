# 注册与账号认证支持矩阵

**审计日期：** 2026-09-02
**范围：** Roxy 注册/登录主链、Protocol 协作适配、账号查活、刷新 AT、补密码、补 Authenticator 2FA。
**结论：** Roxy 是稳定的浏览器主流程；Protocol 只处理能够明确判定的协议阶段。两者共享认证结果、挑战链和恢复边界，但不会在远端结果未知时自动重新注册。

## 1. 统一结果

所有已接入的认证操作都可以在结果中读取 `auth`，只包含以下非敏感字段：

| 字段 | 含义 |
|---|---|
| `status` | `authenticated`、`password_rejected`、`request_unknown` 等稳定状态 |
| `code` | 稳定错误码，例如 `mfa_secret_missing`、`remote_existing` |
| `auth_method` | `roxy`、`protocol`、`protocol_v2`、`email_otp`、`access_token` 等 |
| `challenge_chain` | 已完成的挑战，例如 `password → email_otp → totp` |
| `remote_identity` | `new_candidate`、`existing`、`unknown` |
| `retryable` | 是否允许安全重试 |
| `roxy_fallback_allowed` | Protocol 失败后是否允许交给 Roxy |
| `next_action` | `continue`、`resume`、`roxy_fallback`、`manual_reconcile`、`stop` |

Token、密码、OTP、TOTP Secret、Cookie、callback URL、原始响应和完整代理信息不会进入 `auth`。

## 2. 注册方式与职责

| 入口 | 当前定位 | 已支持 | 明确不做 |
|---|---|---|---|
| Roxy | 稳定主流程、页面状态权威来源、最终浏览器兜底 | 邮箱提交、创建密码、邮箱 OTP、TOTP、资料页、登录态、Token、注册后账号配置 | 不把已有账号当新账号重复创建 |
| Protocol | 可替换的协议阶段适配器 | 明确的邮箱 OTP、OAuth callback/session、Protocol v2 刷新 AT、协议 2FA | 不在未知页面继续 `create_account`，不因密码错误自动换线重试 |
| Service/Dispatcher | 选择驱动、保存 checkpoint、决定是否重试 | 保留已有账号/邮箱/任务状态，区分 `manual_reconcile` 与普通失败 | 不以本地数据库“没有账号记录”推断远端一定没有账号 |

推荐配置是 `REGISTRATION_DRIVER=roxy`。Protocol 仍可作为注册驱动或账号操作的阶段能力，但其结果必须先经过统一判定；Protocol 不稳定或不支持时才允许按结果交回 Roxy。

## 3. 注册状态矩阵

### 3.1 邮箱提交后

| 远端页面/结果 | `remote_identity` | 是否允许创建资料 | 当前处理 |
|---|---:|---:|---|
| `/create-account/password` 或密码创建页 | `new_candidate` | 是 | 生成并提交账号密码，提交后立即保存 checkpoint |
| 邮箱验证码页 | `new_candidate` | 等 OTP 后判断 | 同一认证尝试内限次数取码/重发 |
| `about-you` / profile | `new_candidate` | 是 | 填姓名、生日/年龄后继续 |
| `/log-in/password`、`login_password` | `existing` | 否 | 有本地密码则走已有账号恢复；没有则 `manual_reconcile` |
| 已登录、session、callback、external OAuth | `existing` | 否 | 跳过资料创建，验证并保存 Token |
| 页面类型/继续 URL 无法识别 | `unknown` | 否 | `request_unknown`，保留现场和 checkpoint，不重注册 |

### 3.2 邮箱 OTP 提交后

| 后续状态 | 当前处理 | 缺少本地凭证时 |
|---|---|---|
| 直接进入资料页 | 继续新账号资料流程 | 不适用 |
| 直接进入登录态/callback | 认定远端已有账号，跳过 `create_account` | 只需完成 session/Token 收口 |
| 进入 Authenticator TOTP | 进入公共 TOTP 状态机，不再次发送邮箱 OTP | 停止，返回 `totp_required`/`mfa_secret_missing` |
| 明确邮箱验证码错误 | 同一认证尝试内有限次重新取最新验证码 | 达到上限后失败 |
| 页面卡住或结果未知 | `request_unknown` | 保留 checkpoint，不自动重复不可确认的提交 |

Roxy 已覆盖“邮箱 OTP → TOTP”；这个判断优先读取最新 DOM 控件，不能只看仍停留在 `/log-in/password` 的旧 URL。

### 3.3 远端已有账号的处理

“本地 `registered_accounts` 没有记录”不等于“远端没有账号”。以下情况会进入协调语义：

- 邮箱 OTP 后跳登录密码页，但本地没有该账号密码；
- Roxy 发现已登录/session/callback 状态；
- Protocol 发现明确 external callback/session；
- 认证请求提交后只得到无法判定的页面或响应。

已知已有账号不会释放邮箱为可复用；未知结果也不会触发新的注册任务。已保存的账号和注册 checkpoint 由后续账号补全或人工协调继续处理。

## 4. 账号操作矩阵

下面的“密码/2FA”指 OpenAI 账号凭证，不是邮箱池密码。

| 本地状态 | 普通查活 | 刷新 AT | 补密码 | 补 2FA |
|---|---|---|---|---|
| 无密码、无 2FA | 只验证现有 AT，不登录 | 默认 legacy 邮箱 OTP；Protocol v2 无密码时回落既有邮箱认证 | 有有效登录态/AT 时可补，提交立即保存 | 生成 Secret 后先保存，再激活；失败保留 pending |
| 有密码、无 2FA | 只验证现有 AT，不登录 | Protocol v2 可密码登录；远端再要邮箱 OTP 就取 OTP | 跳过 | 登录收口后补 2FA |
| 无密码、有 2FA | 只验证现有 AT，不登录 | 不伪造密码，走邮箱认证；若后续要求 TOTP，由 Roxy/公共状态机使用已有 Secret | 有有效登录态/AT 时可补 | 已有有效 Secret 跳过重复设置；pending 状态继续完成 |
| 有密码、有 2FA | 只验证现有 AT，不登录 | Protocol v2 可走密码 → TOTP，或密码 → 邮箱 OTP → TOTP | 跳过 | 跳过；仅 pending/失败状态重试 |

### 4.1 普通查活

普通查活和刷新 AT 是两个动作：

- 有 AT 时只做在线验证；不会因为查活失败偷偷发送邮箱 OTP。
- AT 过期/失效时报告“请刷新 AT”，不把查活当成登录任务。
- 账号已标记停用/封禁时停止，不再登录或刷新。

### 4.2 刷新 AT

| 分支 | 结果 |
|---|---|
| legacy（默认） | 沿用现有邮箱 OTP 刷新；失败且满足条件时可进入 Roxy 浏览器兜底 |
| Protocol v2 + 有密码 | 密码验证成功后可能直接 callback、邮箱 OTP 或 TOTP；按实际响应继续 |
| Protocol v2 + 无密码 | 不发送伪造密码，回落现有邮箱认证路径 |
| 密码明确错误 | `password_rejected`，默认停止，不自动重复提交，也不自动 Roxy 兜底 |
| 密码提交结果未知 | `password_result_unknown`，不改写成密码错误，不重复提交 |
| 明确要求 TOTP但没有 Secret | `mfa_secret_missing`，停止并提示先补 2FA |
| Protocol 不支持/可安全回退 | 允许交给 Roxy；不改变账号核心状态 |

可选配置 `ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=True` 只允许密码明确错误后另起一次邮箱认证会话一次；最终结果仍保留“密码被拒绝”，不会把错误伪装成密码成功。

### 4.3 补密码与补 2FA

账号配置补全按同一个已认证浏览器会话串行执行：

```text
刷新/取得有效登录态
  → 判断是否缺密码
  → 补密码并立即写 checkpoint
  → 判断是否缺 2FA
  → 保存 Secret checkpoint
  → 激活 2FA 并确认成功
```

- 已有密码不会覆盖或重新生成。
- 密码设置失败不会丢失已经写入的密码 checkpoint；任务返回失败，可单独重跑。
- 2FA Secret 在远端激活前先保存，激活失败标记 `totp_setup_pending`，下次继续而不是重新猜测状态。
- 密码和 2FA 的成功状态不互相回滚；Codex/套餐等后处理失败也不回滚账号核心状态。
- 当前组合补全会独立收集密码和 2FA 步骤结果，最终任务只要有一步失败就标记为可重跑的部分失败。

## 5. 错误码与重试矩阵

| 错误/状态 | 是否自动重试 | 是否 Roxy 兜底 | 后续动作 |
|---|---:|---:|---|
| `unsupported` | 否 | 是 | 交给 Roxy |
| `network_error` / 可确认的临时网络错误 | 有限 | 视结果而定 | 重新取得线路或进入 Roxy |
| `email_otp_invalid` | 同一认证尝试内有限次 | 不因验证码错误盲目注册 | 重新取最新 OTP |
| `password_rejected` | 否 | 否（默认） | 修正账号密码或人工协调 |
| `password_result_unknown` | 否 | 否 | 保留 checkpoint，人工/恢复任务确认 |
| `mfa_rejected` | 否 | 否 | 检查 Secret/远端状态后重跑 |
| `mfa_secret_missing` | 否 | 否 | 先补 2FA 或人工提供 Secret |
| `remote_existing` | 否 | 否 | 走账号补全/人工协调，不走新注册 |
| `request_unknown` | 否 | 否 | 保留现场、邮箱和 checkpoint |
| `account_deactivated` | 否 | 否 | 停止账号操作 |

## 6. 已完成的代码与测试审计项

- `core/auth_challenge.py`：统一结果、错误策略、远端身份判定和安全序列化。
- `core/registration/state_machine.py`：增加 TOTP 状态及邮箱 OTP 后的 TOTP 优先级。
- `core/registration/roxy.py`：已有账号/未知页面保护、邮箱 OTP 后 TOTP、注册结果投影。
- `core/registration/protocol.py`：Protocol continuation 分类，未知页面禁止继续创建资料。
- `core/protocol_v2_liveness.py`：密码、邮箱 OTP、TOTP、密码错误和结果未知投影。
- `core/live_check_service.py`：普通查活与刷新 AT 的边界及统一结果投影。
- `core/roxy_liveness.py`：Roxy 刷新 AT 的邮箱 OTP 后 TOTP 收口。
- `core/codex_retry_service.py`：补密码/补 2FA 的 checkpoint 与统一结果投影。
- `core/account_completion_service.py`：四种密码/2FA 缺失组合的规划结果。

自动化测试覆盖：

1. Roxy/Protocol 的密码、邮箱 OTP、TOTP 页面识别；
2. 邮箱 OTP → TOTP 不重复发邮箱验证码；
3. 本地无记录但远端已有账号、未知页面禁止新注册；
4. 有密码/无密码 × 有 2FA/无 2FA 的账号补全规划；
5. Protocol v2 的直接 callback、邮箱 OTP、邮箱 OTP → TOTP、密码错误、结果未知、缺 TOTP；
6. 密码 checkpoint、2FA Secret checkpoint、串行补全和后置失败不回滚。

## 7. 当前边界与后续优化方向

本次实现的单元测试使用脱敏 fake session/driver，不会访问真实账号、邮箱池或生产 PostgreSQL。尚未宣称真实外部 E2E 全部通过，原因是 OpenAI 页面、风控、邮箱延迟和 Protocol 响应会变化。

后续优化按优先级：

1. 用专用测试账号分别验证四种凭证组合，每种至少跑注册续跑、刷新 AT、补密码、补 2FA 一次，并保留只含状态码的审计结果；
2. 为每个页面分类保存脱敏 DOM fixture，Provider 变化时先更新适配器和契约测试；
3. 把 `remote_identity`、`challenge_chain`、`next_action` 在任务详情页做成结构化展示，减少只看自然语言错误；
4. 为密码错误、TOTP 错误、结果未知分别增加人工恢复入口，避免所有失败都依赖重新点击；
5. Protocol v2 稳定后再扩大灰度，不改变 Roxy 主流程和可回退开关；
6. 完成一次真实小样本验收后，再决定是否允许批量启用新的 Protocol 阶段。
