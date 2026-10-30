# 注册与账号认证支持矩阵

**范围：** Roxy/Protocol 注册驱动、账号查活、刷新 AT、补密码、补 Authenticator 2FA。
**结论：** Roxy 是推荐的浏览器注册驱动；Protocol 也是可直接选择的协议注册驱动。
两者共享认证结果、挑战链和恢复边界，但 `REGISTRATION_DRIVER` 不会因为某一步失败而
自动切换，也不会在远端结果未知时自动重新注册。

## 0. 协议版本选择

全局配置只有一个：`OPENAI_PROTOCOL_VERSION=v1|v2`，默认 `v1`。它不是新的执行驱动，也不影响 Roxy。只有某个协议步骤同时具备 v1/v2 实现时才读取该配置；单版本步骤忽略全局配置并直接使用唯一实现。

| 步骤 | 当前支持版本 | 是否读取 `OPENAI_PROTOCOL_VERSION` | 有效实现 |
|---|---|---:|---|
| 注册协议 | v1 | 否 | v1 |
| 协议 2FA | v1 | 否 | v1 |
| 套餐查询 | v1 | 否 | v1 |
| 普通查活 | v1 | 否 | v1 |
| 刷新 AT | v1、v2 | 是 | 按全局配置选择 |
| Codex 协议授权 | v1 | 否 | v1 |

历史 `.env` 的 `ACCOUNT_TOKEN_REFRESH_DRIVER`、`ACCOUNT_AUTH_V2_ENABLED` 只在兼容边界读取，不再作为新配置项或 WebUI 选项。内部仍可能保留 `legacy`、`protocol_v2` 等实现标签，但对外结果同时提供稳定的 `protocol_version` 字段。

## 1. 统一结果

所有已接入的认证操作都可以在结果中读取 `auth`，只包含以下非敏感字段：

| 字段 | 含义 |
|---|---|
| `status` | `authenticated`、`password_rejected`、`request_unknown` 等稳定状态 |
| `code` | 稳定错误码，例如 `mfa_secret_missing`、`remote_existing` |
| `auth_method` | `roxy`、`protocol`、`email_otp`、`access_token` 等实际认证方式 |
| `protocol_version` | 使用协议时的公开版本；单版本步骤为 `v1`，刷新 AT 为实际选择的 `v1`/`v2` |
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
| Protocol | 可直接选择的纯协议注册驱动，以及账号认证协议能力 | 协议注册、明确的邮箱 OTP、OAuth callback/session、v1/v2 刷新 AT、协议 2FA | 不在未知远端结果下自动改用 Roxy 或重新创建账号；不因密码错误自动换线重试 |
| Service/Dispatcher | 选择驱动、保存 checkpoint、决定是否重试 | 保留已有账号/邮箱/任务状态，区分 `manual_reconcile` 与普通失败 | 不以本地数据库“没有账号记录”推断远端一定没有账号 |

推荐配置是 `REGISTRATION_DRIVER=roxy`；显式设置 `REGISTRATION_DRIVER=protocol` 时会直接
运行协议驱动。2FA 的公开选择统一为 `auto`、`protocol`、`browser`：`auto` 是协议优先的
自动上下文选择，`protocol` 强制协议执行器，`browser` 强制 Roxy 安全设置页。历史值
`protocol_direct` 仍兼容，但只作为 `auto` 的别名，不再作为独立决策。认证操作返回的
`roxy_fallback_allowed` 只表示对应账号动作可按结果进入浏览器处理，不改变注册任务的
驱动选择。

### 2.1 2FA 执行器与认证上下文不是一回事

| 概念 | 可选值 | 作用 | 当前行为 |
|---|---|---|---|
| 2FA 执行器 | `protocol` | 调用 MFA `enroll/activate` 协议接口 | 可复用 AT；没有 AT 或遇到 MFA 401 时走协议邮箱重认证；失败后按开关回退 Roxy |
| 2FA 执行器 | `browser` | 使用浏览器安全设置页 | 依赖已经登录的 Roxy 会话，直接在页面完成 2FA |
| 2FA 模式 | `auto` | 自动选择上下文，协议优先 | 单独补 2FA 优先已有 AT；组合补密码时复用浏览器会话取得新 AT，再由协议完成 2FA |
| 认证上下文 | `existing_at` | 已保存、可尝试使用的 AT | 只适用于不需要浏览器登录的协议路径；MFA 401 时不把查活成功误认为近期认证 |
| 认证上下文 | `protocol_reauth` | 协议邮箱 OTP 重认证取得新 AT | 适用于无 AT 或旧 AT 被 MFA 要求近期认证；新 AT 成功后先写回账号再继续 2FA |
| 认证上下文 | `browser_session` | 当前 Roxy 登录会话取得新 AT | 适用于显式 browser，或同一任务还必须补密码的组合流程 |

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

| 本地状态 | 普通查活 | 刷新 AT | 补密码 | 补 2FA（`auto`） |
|---|---|---|---|---|
| 无密码、无 2FA | 只验证现有 AT，不登录 | v1 走邮箱 OTP；v2 无密码时回落既有邮箱认证 | 有有效登录态/AT 时可补，提交立即保存 | `existing_at` → 协议；无 AT/近期认证失败 → `protocol_reauth`；仍失败且开关开启 → Roxy |
| 有密码、无 2FA | 只验证现有 AT，不登录 | v2 可密码登录；远端再要邮箱 OTP 就取 OTP | 跳过 | 单独补 2FA 仍优先协议；与密码同批时 Roxy 登录取新 AT，再协议开通 |
| 无密码、有 2FA | 只验证现有 AT，不登录 | 不伪造密码，走邮箱认证；若后续要求 TOTP，由 Roxy/公共状态机使用已有 Secret | 有有效登录态/AT 时可补 | 已有有效 Secret 跳过；pending 状态继续完成，不重复注册 |
| 有密码、有 2FA | 只验证现有 AT，不登录 | v2 可走密码 → TOTP，或密码 → 邮箱 OTP → TOTP | 跳过 | 跳过；仅 pending/失败状态重试 |

### 4.1 普通查活

普通查活和刷新 AT 是两个动作：

- 有 AT 时只做在线验证；不会因为查活失败偷偷发送邮箱 OTP。
- AT 过期/失效时报告“请刷新 AT”，不把查活当成登录任务。
- 账号已标记停用/封禁时停止，不再登录或刷新。

### 4.2 刷新 AT

| 分支 | 结果 |
|---|---|
| v1（默认） | 沿用现有邮箱 OTP 刷新；失败且满足条件时可进入 Roxy 浏览器兜底 |
| v2 + 有密码 | 密码验证成功后可能直接 callback、邮箱 OTP 或 TOTP；按实际响应继续 |
| v2 + 无密码 | 不发送伪造密码，回落现有邮箱认证路径 |
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

### 4.4 补 2FA 的自动选择矩阵

| 配置/任务条件 | 取得认证上下文 | 2FA 执行器 | 是否打开浏览器 | 失败后的处理 |
|---|---|---|---:|---|
| `auto`/`protocol`，已有 AT，单独补 2FA | `existing_at` | `protocol` | 否 | MFA 401 时协议重认证；仍失败且开关开启则 Roxy |
| `auto`/`protocol`，没有 AT，单独补 2FA | `protocol_reauth` | `protocol` | 否 | 协议重认证失败且开关开启则 Roxy，否则失败并保留原因 |
| `auto`/`protocol`，同时补密码和 2FA | `browser_session` | `protocol` | 是 | 密码与 2FA 共享同一会话、串行执行；协议 2FA 失败按兜底开关处理 |
| `browser`，任意 AT 状态 | `browser_session` | `browser` | 是 | 页面流程失败即停止，不再额外发送协议 OTP |
| 历史值 `protocol_direct` | 按 `auto` 处理 | `protocol` | 同 `auto` | 不再进入注册驱动的非法值校验，也不在 WebUI 展示为独立选项 |

安全边界：`existing_at` 不是“查活成功”的同义词。MFA enrollment 仍可能要求近期认证；只有协议重认证或当前浏览器登录态取得的新 AT 成功后，才继续激活。协议邮箱重认证取得的新 AT 会在继续 2FA 前写回账号检查点；TOTP Secret 仍在激活前写入 `totp_setup_pending` 检查点。

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
