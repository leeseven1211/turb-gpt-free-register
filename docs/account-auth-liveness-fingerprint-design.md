# 账号认证、查活、2FA 与指纹优化设计

> 本文是技术背景设计，不直接作为实施顺序。实际开发、放行和回退以 [分阶段实施清单](account-auth-protocol-staged-rollout-checklist.md) 为唯一依据。

状态：Proposal（业务实现尚未落地；协议/浏览器受控验证已完成）

日期：2026-09-01

配套详细实施规范：[`account-auth-liveness-fingerprint-implementation-design.md`](account-auth-liveness-fingerprint-implementation-design.md)

适用范围：账号查活、ChatGPT AT 刷新、账号密码登录、TOTP/MFA 登录、2FA 设置、Protocol `BrowserSession`、Roxy 浏览器画像、账号列表和任务详情。

## 1. 设计结论

本次不合并上游整套实现，而是在当前 PostgreSQL、账号任务中心和代理租约架构上移植三项能力：

1. 为“刷新 AT”增加密码登录和 TOTP MFA challenge 流程；普通“查活”仍只验证已有 AT。
2. 为 Protocol 账号认证建立“账号级 Protocol 认证画像 + 每次运行独立会话标识”的双层模型。
3. 建立 Protocol/Roxy 共用的安全指纹摘要，并把原始设备 ID、会话标识和代理上下文保存到独立受限存储；普通任务事件和账号列表只读取安全摘要。

同时新增以下长期兼容约束：

4. 当前密码、查活、邮箱 OTP、TOTP/2FA 和 Roxy 链路作为稳定实现长期保留；新能力在平行的 `protocol_v2` 接口中实现，不在原函数内原地替换。
5. 每个主要步骤都能独立选择 `browser_current`、`protocol_current`（该步骤现有协议能力存在时）或 `protocol_v2`；另有全局 v2 紧急开关，只负责禁用新协议接口。
6. Roxy 浏览器是默认主路径，也是 Protocol 路径可选的兜底；Protocol 因速度优势作为用户可选项，不自动升级为默认主路径。浏览器能力、配置入口、能力检测和测试不得删除。
7. 普通“查活”无论选择哪个实现都只验证旧 AT，禁止借“浏览器兜底”执行登录、发 OTP 或提交密码/TOTP。

上游 `2161365` 的密码/MFA 登录流程和 `b306209` 的指纹摘要可作为协议参考，但不能 cherry-pick：上游实现绑定旧 `core/db.py`、旧驱动、旧队列和 SQLite 数据模型，也把本应每次变化的 session/trace 标识一并固定。

目标结构：

```text
普通查活
  -> 有 AT 且启用 account_stable 时读取/确保账号级 Protocol 画像
  -> 创建本次独立 BrowserSession，执行 AT 在线探测
  -> 写 live_check 状态
  -> 不读账号密码、不生成 TOTP、不发送邮箱 OTP、不执行登录

刷新 AT / 账号认证
  -> 账号任务 + 代理租约
  -> 读取账号认证能力（有无账号密码、TOTP、旧 AT、邮箱取码能力）
  -> 读取该步骤 DRIVER 配置
       +-- browser_current（默认）-> Roxy 完整认证链
       +-- protocol_current ------> 现有协议认证链
       +-- protocol_v2 -----------> 新密码/MFA/邮箱 OTP 状态机
  -> 密码 / 密码+MFA / reauth 邮箱 OTP / 邮箱 OTP
  -> OAuth callback + Session/AT
  -> 原子写回 Token、查活状态、安全指纹摘要
  -> 只有 Protocol 被选为主路径时，才按配置考虑 Roxy fallback
```

## 2. 当前实现与上游差异

| 能力 | 当前分支 | 上游新增 | 设计取舍 |
| --- | --- | --- | --- |
| 普通查活 | 只验证已有 AT，明确不登录 | 查活模块本身会重新认证 | 保留不登录语义；新增浏览器/协议驱动选择 |
| 刷新 AT | Protocol 邮箱 OTP，失败可 Roxy 邮箱 OTP fallback | 可密码登录，遇到 MFA 自动提交 TOTP | 浏览器作为默认主路径，现有/新协议由用户配置 |
| 注册密码 | Roxy 创建、提交后立即存检查点、可继续原账号 | 有密码注册和导出 | 保留当前实现 |
| 注册后补密码 | 已接入账号配置补跑和任务事件 | 旧独立实现 | 不合并上游队列 |
| 设置 2FA | Protocol enroll/activate + Roxy UI fallback + secret 检查点 | 独立 `twofa_service.py` | 保留全部能力；默认浏览器，现有/新协议可配置 |
| Protocol 画像 | 每个 `BrowserSession` 随机设备 ID 和硬件候选，单次会话内稳定 | 账号 email seed 固定全部 ID | 只固定设备层，会话层继续轮换 |
| Roxy 指纹 | Roxy 外部环境生成真实浏览器画像，任务结束默认删除临时 Profile | 没有本质更完整的新生成器 | 增加安全观测，不改变 Profile 生命周期 |
| 指纹摘要 | 没有完整生成、存储和 UI 链 | 输出并保存 `BrowserSession` 字段 | 安全摘要与受限原始上下文分层保存 |
| 存储 | PostgreSQL 行级表 + JSONB | SQLite | 禁止合并 SQLite |

### 2.1 普通“查活”现状

当前普通查活入口是 `POST /api/accounts/check-live-bulk`，传入 `force_refresh=False`，任务类型为 `live_check`。

实际流程：

```text
读取账号已有 access_token
  |
  +-- 有 AT -> 领取账号功能代理 -> check_account_plan 在线探测
  |             |
  |             +-- 成功 -> live，记录 HTTP/套餐/线路
  |             +-- 明确废号 -> deactivated
  |             +-- Token 失效 -> failed，提示用户点击“刷新 AT”
  |             +-- 网络类失败 -> 最多换线路探测 4 次
  |
  +-- 无 AT -> failed，提示先“刷新 AT”
```

普通查活当前不会调用 `check_account_liveness()`，不会读取账号密码/TOTP，不会发送邮箱 OTP，也不会取得新 AT。但 `check_account_plan()` 内部会以 `detect_exit_geo=False` 创建临时 `BrowserSession`，用其请求头和设备参数发起套餐/AT 探测。

这个临时 `BrowserSession` 当前没有账号级稳定 identity：每个 probe 都会新生成 `device_id`、会话 ID 和随机硬件候选；换线路重试最多 4 次时，也会分别创建新 session。因此当前普通查活实际存在 Protocol 请求指纹，只是它随机、未生成安全摘要、未落库、未展示。

普通查活当前使用 `check_account_plan()` 作为 AT 在线探测。它同时取得套餐信息，所以“AT 有效”和“套餐接口可达”仍有一定耦合；本次设计先保持行为不变，后续如果要拆成独立低副作用存活接口，需要另做真实接口证据验证。

目标实现增加 `ACCOUNT_LIVE_CHECK_DRIVER`：默认 `browser_current`，也允许用户选择 `protocol_current/protocol_v2`。浏览器查活同样只用旧 AT 发起一次受控 probe，不进入登录页、不发 OTP、不刷新 AT；查活不做自动跨驱动 fallback，结果必须准确标明本次实际驱动。

### 2.2 “刷新 AT”现状

当前刷新入口是 `POST /api/accounts/refresh-token-bulk`，传入 `force_refresh=True`，任务类型为 `token_refresh`。

实际 Protocol 流程：

```text
跳过旧 AT probe
  -> 每次随机创建 BrowserSession
  -> 网络预热/匿名态 -> CSRF -> Signin -> Authorize
  -> 邮箱 OTP
  -> OAuth callback -> Session -> 新 AT
  -> update_account_liveness 写回
```

当前 `account_liveness.py` 不读取已保存的 OpenAI 账号密码，也不识别密码响应后的 MFA challenge。即使账号已经有账号密码和 TOTP，通用刷新链仍优先走邮箱 OTP。

Protocol 失败、账号保存过旧 AT、且 `LIVE_CHECK_ROXY_FALLBACK_ENABLED` 开启时，会进入 `roxy_liveness.py`。该浏览器兜底也是邮箱 OTP 登录；遇到登录密码页时会尝试点击一次性验证码入口，不会提交保存的账号密码/TOTP。

当前刷新任务还有一个展示误差：只要最终刷新成功，就统一把 `login_password` 和 `email_otp` 两个阶段都标为成功，不能反映真实认证方法。

### 2.3 账号密码现状

当前已有三类密码能力：

1. Roxy 密码注册：密码模式下生成随机 OpenAI 账号密码，提交后立即保存可恢复检查点；结果未知时保留原账号继续恢复，不重新注册。
2. 注册后补密码：账号已有 AT 但没有 OpenAI 密码时，可通过 Roxy ChatGPT 设置页补充密码，并写入规范字段 `extra_json.account_password`。
3. Roxy Codex OAuth 登录：已经可以读取保存的账号密码，并在浏览器登录密码页提交。

兼容读取顺序是 `account_password -> login_password -> registration_password`。邮箱池里的邮箱密码是另一种凭据，不能用于 OpenAI 登录。

缺口是：保存的 OpenAI 账号密码尚未用于通用“刷新 AT”的 Protocol 登录。

### 2.4 2FA/TOTP 现状

当前已有：

- Protocol `enroll -> activate_enrollment` 设置 TOTP；
- Protocol 设置失败后的 Roxy UI fallback；
- 在远端激活前先保存 TOTP secret，并用 `totp_setup_pending` 标记待确认；
- 账号配置补跑可只补密码/2FA，不重新注册；
- Roxy Codex OAuth 已能在浏览器 MFA 登录页用保存的 TOTP secret 生成验证码。

当前默认配置为 `ENABLE_2FA=False`；开启后注册后置步骤才自动设置 2FA。Protocol 2FA 与浏览器密码设置资源独立时可并发，同一个 Selenium 页面上的浏览器密码/2FA 必须串行。

缺口是：通用“刷新 AT”的 Protocol 登录没有 password verify、MFA issue challenge 和 MFA verify，因此没有使用现有 TOTP 完成刷新登录。

### 2.5 指纹现状

当前存在两套不同层级的画像：

**Roxy 浏览器画像**

- 注册任务通过 Roxy API 创建真实浏览器环境，系统在 Windows/macOS 中随机选择；Canvas、WebGL、字体等底层浏览器能力由 Roxy 管理。
- Selenium 连接到该环境完成注册。
- 默认 `ROXY_ONE_PROFILE_PER_ACCOUNT=True`，含义是一次账号注册不共用固定 Profile；不是“账号终身保留一个 Profile”。
- 默认 `ROXY_DELETE_PROFILE_AFTER_RUN=True`，任务结束会关闭并删除本轮创建的临时 Profile。
- 账号虽然保存过 `profile_id/open_result` 兼容信息，但 Profile 被删除后不能把该 ID 当作可复用的长期浏览器身份。

**Protocol BrowserSession 画像**

- curl_cffi 使用 Chrome TLS impersonation；HTTP/JS 画像包含 UA、Client Hints、语言、时区、屏幕、DPR、CPU、内存、JS heap。
- 语言和时区会根据代理出口 Geo 选择。
- `device_id`、Sentinel SID、OAuth session ID、Datadog ID、React key 和硬件候选当前都在每次新建 `BrowserSession` 时重新随机。
- 同一个 `BrowserSession` 内 Cookie、header、OAuth 参数和 Sentinel 使用一致 device ID；跨 session 不保证一致。
- Sentinel `p` 数组还包含时间、PoW nonce、随机 DOM/window sample 等请求级动态字段。

当前没有把 Protocol/Roxy 画像统一成安全摘要，也没有在账号 UI 明确展示“最近一次认证用了什么画像”。

### 2.6 当前不会被本设计改动的部分

- 注册页面状态机、密码提交检查点、账号核心成功条件保持不变。
- Roxy Profile 的创建/删除生命周期首版保持不变。
- 2FA enroll/activate 和现有补跑任务保持不变。
- 现有 PostgreSQL 账号/任务/代理事实表和 claim 语义保持不变；只新增 identity/context 两张受限表，兼容导出继续排除私有数据。
- 普通查活仍是 AT probe；只优化其 Protocol 请求画像的一致性和安全摘要，密码/MFA/邮箱 fallback 仍只进入 `token_refresh`。

## 3. 范围与非目标

### 3.1 本次范围

- 普通查活与刷新 AT 的动作边界。
- 账号密码、邮箱 OTP、TOTP MFA 的登录策略。
- Protocol 设备画像稳定性。
- Protocol 和 Roxy 的安全指纹摘要。
- 认证结果、错误分类、任务事件和账号列表展示。
- PostgreSQL 行级写入、并发互斥和重启恢复。
- 单元测试、PostgreSQL 集成测试和小范围真实账号灰度方案。

### 3.2 非目标

- 不改变注册核心成功条件和注册检查点。
- 不重新引入 Browser Use、Skyvern、Cloak 或本地旧指纹驱动。
- 不使用 SQLite、JSON/TXT 或 `accounts_viewer.html` 作为事实来源。
- 不因为刷新失败重新注册账号、换邮箱或删除已保存密码/TOTP。
- 不在本次把 Roxy Profile 改成长期持久 Profile；其容量、清理和 Cookie 生命周期需要独立设计。
- 不采集 Canvas、WebGL、Audio、字体明细等高风险浏览器指纹原始值。
- 不把指纹摘要当作“账号是否存活”的判断依据。
- 不在设计阶段修改业务代码或生产数据库；本设计允许单账号、用户明确授权的只读认证验证，验证不写回账号资产。

## 4. 必须保持的不变量

1. PostgreSQL 是账号和任务的唯一事实来源。
2. 普通“查活”永远不发送邮箱 OTP、不提交密码、不生成 TOTP、不刷新 AT。
3. “刷新 AT”是明确的认证动作，才允许使用账号密码、TOTP 或邮箱 OTP。
4. 密码、TOTP secret/code、Token、Cookie、完整代理凭据不得进入日志、任务事件、普通 API 或 DOM；原始设备 ID、会话标识和完整代理只允许进入专用受限存储。
5. 邮箱池密码和 OpenAI 账号密码是两种不同凭据，不能混用。
6. 已取得账号 Token 或已保存 TOTP secret 的部分成功不得因后续失败回滚。
7. 远端结果未知时不重复提交不可逆动作，不推断账号不存在。
8. 网络失败允许换线路；密码错误、缺失 TOTP、明确废号不允许通过换线路反复提交凭据。
9. 查活/刷新不得覆盖注册时保存的 `device_id`；认证会话设备信息使用独立字段和摘要。
10. 启动恢复只修正任务状态，不增加、删除或重建账号行。

## 5. 领域模型

### 5.1 动作类型

继续保留两个用户动作和任务类型：

| 用户动作 | 任务类型 | 是否认证 | 成功条件 |
| --- | --- | --- | --- |
| 查活 | `live_check` | 否 | 已有 AT 通过在线验证 |
| 刷新 AT | `token_refresh` | 是 | 完成认证并取得、保存新 AT |

`force_refresh` 可作为兼容调用参数保留，但业务分支和任务展示必须以动作类型为准。不能仅根据 `trigger` 字符串猜测任务类型；新入口应显式传入动作类型，旧入口继续兼容映射。

### 5.2 认证方法

统一枚举 `auth_method`：

```text
access_token_probe       仅验证旧 AT，不是重新认证
password                 账号密码直接登录
password_mfa_totp        账号密码 + Authenticator TOTP
password_email_otp       密码提交后远端仍要求邮箱验证
password_fallback_email_otp  密码明确错误后受控改走邮箱 OTP
password_fallback_email_otp_mfa  上述邮箱登录后远端仍要求 TOTP
reauth_email_otp         复用旧 AT 预热后走 reauth 邮箱 OTP
email_otp                无密码/无可复用登录态时走邮箱 OTP
roxy_email_otp           Protocol 不兼容后的 Roxy 浏览器兜底
```

`validation_method` 只表达最终如何确认账号正常：`access_token` 或 `authenticated_session`。`auth_method` 表达刷新 AT 时实际使用的认证链，二者不能混成一个字段。

### 5.3 认证结果契约

新增不含敏感值的结果契约，建议使用 dataclass/enum：

```python
AuthResult(
    ok: bool,
    status: live | failed | deactivated,
    checked_at: str,
    validation_method: str,
    auth_method: str | None,
    access_token: str | None,       # 只在进程内传递给存储命令
    session: dict | None,           # 只提取允许落库的用户/套餐字段
    http_status: int | None,
    error_code: str | None,
    error: str | None,
    retry_class: str | None,
    fallback_eligible: bool,
    credential_warnings: list[str], # 例如密码被拒绝、但邮箱 fallback 成功
    fingerprint: SafeFingerprintSummary | None,
)
```

`AuthResult` 不得被整体写进任务事件或 API。存储和任务层分别从中挑选白名单字段。

### 5.4 凭据视图

建立只在业务层内存中存在的 `AccountAuthCredentials`：

```text
account_id
email
account_password
totp_secret
totp_setup_pending
existing_access_token
email_source
```

读取兼容顺序由一个公共 resolver 负责：

- OpenAI 账号密码：规范字段 `extra_json.account_password`，兼容读取旧 `login_password`、`registration_password`。
- TOTP：`registered_accounts.data->>'totp_secret'`；`totp_setup_pending=true` 表示 secret 已保存但远端激活结果待确认。
- 邮箱密码只由邮箱 Provider 使用，绝不作为 OpenAI 账号密码候选。

新写入只使用规范字段，旧字段继续只读兼容，待数据对账完成后另行迁移。

## 6. 刷新 AT 认证状态机

### 6.1 策略选择

刷新任务领取账号和线路后，按远端实际响应驱动状态，不根据本地字段直接断言远端页面：

```text
START
  |
  +-- 有账号密码 --------------------> PASSWORD_VERIFY
  |                                      |
  |                                      +-- callback ------> SESSION
  |                                      +-- MFA challenge -> MFA_TOTP
  |                                      +-- email verify --> EMAIL_OTP
  |                                      +-- rejected ------> EMAIL_OTP_FALLBACK
  |
  +-- 无账号密码 + 有旧 AT ----------> REAUTH_EMAIL_OTP
  |
  +-- 无账号密码 + 无旧 AT ----------> EMAIL_OTP

MFA_TOTP -> issue challenge -> 生成 TOTP -> verify -> callback -> SESSION
EMAIL_OTP_FALLBACK -> 新认证会话 -> 邮箱 OTP -> MFA(如远端要求) -> SESSION
SESSION  -> 取得新 AT -> 原子落库 -> SUCCESS
```

本地存在 `totp_secret` 只说明“具备生成验证码的能力”，不能跳过远端 `mfa_challenge`。只有密码响应明确进入 MFA 后才提交 TOTP。

### 6.2 密码路径

从上游移植协议动作，但重新封装为公共账号认证能力：

1. 获取密码验证所需 Sentinel token。
2. `POST /api/accounts/password/verify`，单次 run 最多提交一次账号密码。
3. 解析结构化响应中的 `page.type`、`continue_url` 和 challenge 信息。
4. 直接返回 callback 时进入 Session；要求邮箱验证时进入邮箱 OTP；要求 MFA 时进入 TOTP。
5. 密码被明确拒绝后，不换代理重复提交同一个密码，标记本次 `password_auth_status=rejected`。
6. 同一“刷新 AT”任务内允许受控改走一次邮箱 OTP；当前实现创建新的会话层 ID 和 Cookie jar，账号级稳定设备画像待阶段 8 接入。
7. 邮箱 OTP 后如果远端仍返回 MFA challenge，继续使用保存的 TOTP 完成验证。

密码错误后的邮箱兜底由 `ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK` 明确控制；当前落地默认关闭，避免把过期/录错密码静默掩盖。开启后它仍不是静默掩盖：任务事件和账号最近认证结果必须记录“密码被拒绝、邮箱兜底是否成功”。

兜底成功时整体刷新任务可以成功，但账号保留 `password_auth_status=rejected` 和下一步动作“核对/重设账号密码”；不得删除、覆盖或自动猜测新密码。兜底失败时同时保留密码错误和邮箱失败两个原因，不能只显示最后一个错误。

### 6.3 TOTP MFA 路径

1. 从密码响应提取 `factor_id`。
2. 如果本地没有 TOTP secret，返回 `mfa_secret_missing`，不尝试邮箱 OTP 冒充 MFA。
3. 调用 `mfa/issue_challenge`；此接口不携带密码验证阶段的 Sentinel header。
4. 使用本地 secret 生成一次 TOTP，日志和事件只记录“已生成”，不记录验证码。
5. 距离 30 秒窗口结束不足 6 秒时，等待下个窗口再提交。
6. 如果明确返回验证码过期/无效，只允许跨窗口再生成一次；网络失败按是否已收到远端响应分类，不盲目重复提交。
7. 验证成功后跟随 callback 并获取 Session/AT。

`totp_setup_pending=true` 时仍允许在远端明确要求 MFA 后尝试该 secret；成功后可清除 pending。若远端没有 MFA challenge，不根据本地 pending 主动调用 MFA verify。

### 6.4 邮箱 OTP 路径

保留当前能力：

- `reauth_email_otp`：有旧 AT 时先执行 authenticated bootstrap，再触发 reauth。
- `email_otp`：无可用密码和旧登录态时走 CSRF/Signin/Authorize。
- OTP 无效或过期最多受控重发一次，使用新的 `after_ts`，避免重复取到旧码。
- 邮箱 Provider 必须接收账号保存的 `email_source`，不能重新按全局默认猜来源。

密码响应主动要求 email verification 时，记录 `auth_method=password_email_otp`，以便区分“没有密码”与“远端额外验证”。

密码明确错误后主动重新开启的邮箱链记录 `auth_method=password_fallback_email_otp`；若邮箱验证后又完成 TOTP，则记录 `password_fallback_email_otp_mfa`。这两种情况都只允许一次邮箱 fallback。

### 6.5 Roxy fallback

Roxy 只在以下情况兜底：

- Protocol 响应结构变化，无法识别下一步；
- Protocol 页面/挑战被确认不支持；
- 经过受控网络重试后仍是可由真实浏览器验证的工作流错误。

以下情况禁止 Roxy fallback：

- 账号明确停用/封禁；
- 密码明确错误本身不触发 Roxy fallback；先按受控邮箱 OTP fallback，邮箱链失败后也不能用 Roxy 重试同一错误密码；
- 远端要求 MFA 但本地缺 TOTP secret；
- 邮箱 Provider 明确不可用；
- 用户取消或任务状态已失效。

Roxy fallback 仍然只允许“已有账号登录”，一旦识别为新账号创建密码或资料页立即停止，不能在刷新 AT 时意外创建账号。

## 7. 错误分类与重试

替换当前以错误字符串包含关系为主的判断，建立稳定错误码：

| 错误类 | 示例错误码 | 换线路 | 重试凭据 | Roxy fallback |
| --- | --- | ---: | ---: | ---: |
| 网络/代理 | `network_timeout`、`proxy_connect_failed`、`upstream_5xx` | 是 | 否 | 条件允许 |
| 风控/限流 | `auth_403`、`rate_limited` | 受控 | 否 | 条件允许 |
| 密码 | `password_missing`、`password_rejected` | 否 | 密码不重试；邮箱 fallback 一次 | 否 |
| MFA | `mfa_secret_missing`、`mfa_code_rejected` | 否 | 最多跨窗口一次 | 否 |
| 邮箱 | `email_otp_unavailable`、`email_otp_invalid` | 否 | 受控重发一次 | 条件允许 |
| 账号 | `account_deactivated`、`account_deleted` | 否 | 否 | 否 |
| 工作流 | `auth_page_unknown`、`continue_url_missing` | 否 | 否 | 是 |
| 本地状态 | `task_cancelled`、`account_missing`、`claim_lost` | 否 | 否 | 否 |

同一次刷新 run 中，线路轮换必须复用同一个账号级 Protocol 认证画像，但创建新的 HTTP session。`proxy=None` 与显式 `proxy=""` 的语义继续严格区分。

## 8. 指纹与身份模型

### 8.1 “账号稳定设备画像”的准确含义

本设计中的准确名称是“账号级 Protocol 认证画像”，不是“把注册时 Roxy 的整套浏览器 Profile 固定下来永久复用”。

首版行为是：账号第一次进入需要 Protocol 请求的账号操作时生成一套稳定的 Protocol 设备层参数，以后该账号的普通 AT 查活、刷新 AT、Protocol 2FA 等操作都复用这套设备层参数；每次操作仍创建新的会话层标识和 Cookie jar。它解决的是当前每次 `BrowserSession` 都随机换 device ID、屏幕和 CPU 的漂移。

它不等于注册 Roxy 画像，原因是当前注册使用外部 Roxy 浏览器，Profile 任务结束默认删除；Protocol 使用 curl_cffi，是另一个执行驱动。上游的 account seed 也只是让后续 Protocol 查活稳定，并没有保存或复用注册 Roxy 的真实 Profile。

如果未来要求“注册、查活、Codex、2FA 始终像同一台真实浏览器”，需要单独设计 Roxy Profile 长期保留，或做受限的 Roxy -> Protocol 认证上下文交接。首版不改变 Roxy 生命周期，避免同时引入 Profile 容量、Cookie 持久化、孤儿环境和删除恢复风险。

### 8.2 三层身份

当前和上游都把多类字段称为“指纹”，本设计拆为三层：

| 层级 | 生命周期 | 字段示例 | 设计规则 |
| --- | --- | --- | --- |
| 账号设备层 | 同账号长期稳定，版本升级时可迁移 | `device_id`、硬件候选、屏幕、DPR、基础 OS/UA | 按账号稳定 |
| 会话层 | 每次 `BrowserSession` 新建 | `sentinel_sid`、`oai_session_id`、`auth_session_logging_id`、Datadog ID、React key | 每次随机 |
| 请求层 | 每个请求或 PoW 变化 | performance 时间、nonce、随机 DOM/window sample | 保留现有动态生成 |

上游用 `fingerprint_seed` 固定三层所有字段，虽然减少漂移，但会让 session/trace 标识长期不变。本项目只稳定账号设备层。

### 8.3 账号设备画像键

为每个账号建立服务端专用 `protocol_profile_key`：

- 首次需要重新认证时随机生成 256 bit 值；不直接使用邮箱作为 seed。
- 使用 PostgreSQL 原子 upsert“缺失才创建”，并发任务只能得到同一个值。
- 放在专用受限表 `account_protocol_identities`，不写入 `registered_accounts.data`。
- 不进入日志、API、任务事件、兼容导出或 UI。
- 使用带字段域分离的 `HMAC-SHA256(profile_key, label)` 分别派生设备 ID、硬件候选索引和对外可展示的短 `profile_ref`；不从邮箱、账号 ID 或一个共用 hash 直接切片。

账号 profile key 不是登录凭据，但具有关联性，按敏感内部元数据处理。普通查活可以读取/确保它，但这只是本地画像元数据，不会触发远端登录、OTP 或凭据提交。

### 8.4 BrowserSession API

不直接给 `BrowserSession` 一个会固定所有 ID 的字符串 seed，改为显式身份对象：

```python
BrowserIdentity(
    profile_version: int,
    profile_ref: str,
    device_id: str,
    base_profile: dict,
)

BrowserSession(
    proxy=...,
    identity=browser_identity,  # 可选；注册等匿名任务仍可随机
)
```

`BrowserSession` 使用 identity 中的 `device_id` 和硬件画像，但每次重新生成：

- `sentinel_sid`
- `oai_session_id`
- `auth_session_logging_id`
- Datadog trace/parent ID
- React listening/container/resources key

出口 Geo、语言和时区仍由账号代理线路决定。账号代理应尽量保持注册国家/地区一致；同一次 run 换线路时硬件画像不变，Geo 变化作为任务事件记录。

### 8.5 画像版本

`profile_version=1` 固定当前画像派生算法。将来调整 UA、Chrome 大版本、硬件池或地区策略时：

- 老账号默认继续使用 v1，不因部署自动全部换画像。
- 新账号/新 profile 使用最新版本。
- 需要迁移时提供显式批次和事件，不在查活过程中静默升级。
- UI 显示版本和观测时间，便于解释前后差异。

### 8.6 Sentinel 一致性

保留当前 Sentinel `p` 数组和 PoW 动态字段，确保：

- Cookie `oai-did`、OAuth 参数/请求头 device ID 和 Sentinel 请求 `id` 使用同一账号设备 ID。
- UA、语言、时区、屏幕、CPU 和 JS heap 都来自同一 `browser_profile`。
- `performance.now`、`timeOrigin`、nonce 和抽样键仍按请求变化。
- 画像摘要只观察输入字段，不参与 PoW 结果或服务器响应判断。

### 8.7 “跨驱动认证上下文交接”的准确含义

这里的“跨驱动”是指同一个账号可能先由 Roxy 真实浏览器注册/登录，后续又由 Protocol `BrowserSession` 做刷新 AT、2FA 或套餐接口。

所谓交接，是尝试让两个驱动共享可安全复用的部分：

- `oai-did`/设备 ID；
- UA、Client Hints、语言、时区、屏幕和硬件摘要；
- 同一次运行里的代理地区和认证上下文；
- 必要时仅在内存中传递允许复用的 Cookie。

它不能做到“完整指纹复制”：Roxy 的 Canvas、WebGL、字体、真实 Chrome TLS/HTTP2 行为无法完整搬进 curl_cffi；Cookie 直接跨驱动复制也有安全和状态一致性风险。因此设计中不再使用“跨驱动完整指纹”这个容易误导的说法，统一称为“跨驱动认证上下文交接”。

首版只做两件事：分别观察 Roxy/Protocol 的安全摘要，并让 Protocol 自身按账号稳定。是否做跨驱动交接，要等摘要对比确认确实存在影响成功率的差异后再单独设计。

## 9. 安全指纹摘要

### 9.1 统一摘要结构

Protocol 和 Roxy 都输出同一种 `SafeFingerprintSummary`：

```text
schema_version
source                    protocol / roxy
profile_version
profile_ref               不可逆短摘要
browser_family / browser_os / browser_version
user_agent
accept_language
navigator_language / navigator_languages
timezone_iana / timezone_offset_minutes
screen_width / screen_height / device_pixel_ratio
hardware_concurrency / device_memory / js_heap_size_limit
geo_country / geo_timezone
proxy_mode
transport_profile         仅 Protocol，例如 curl impersonate 版本
observed_at
```

以下字段明确排除在 `SafeFingerprintSummary`、任务事件和普通 API 之外，但设备/会话/代理上下文可按第 10 节写入受限原始存储：

- 原始 `protocol_profile_key`、`device_id`；
- Sentinel/OAuth/Datadog/React 会话标识；
- Token、Cookie、密码、TOTP secret/code；
- 邮箱、账号 ID；
- 完整代理 URL、用户名、密码、出口 IP；
- Canvas/WebGL/Audio/字体等原始指纹值。

### 9.2 Protocol 摘要

从 `BrowserSession.browser_profile` 和已脱敏 route 信息生成。摘要函数必须是纯观察函数，不改变 session、Cookie 或随机数状态。

### 9.3 Roxy 摘要

通过 Selenium 执行只读 JavaScript，采集 UA、language、timezone、screen、DPR、CPU、memory 和 platform，并映射到同一结构。

不读取 Canvas/WebGL，不调用外部指纹检测站，不把 Roxy `open_result` 原样展示。Roxy Profile 当前为临时环境，摘要的 `profile_ref` 只代表本次观测，不承诺跨任务稳定。

### 9.4 展示语义

普通 AT 查活与刷新认证分别保存安全摘要，UI 不能把两者混成一条：

```text
查活：正常 · AT 在线验证 · JP · Chrome 149 · profile a1b2c3d4
最近认证：密码+TOTP · JP · Chrome 149 · profile a1b2c3d4
```

账号列表只显示单行安全文本；任务详情显示结构化字段。历史摘要必须带 `observed_at` 和 `source`，避免被误解为本次结果。

## 10. PostgreSQL 数据设计

### 10.1 字段

账号业务结果继续使用 `registered_accounts` 的提升列 + JSONB 模型；原始 identity 和每次会话上下文使用专用受限表，不能混入账号普通 payload。

已有稳定筛选字段继续提升：

- `live_check_status`
- `token_expires_at`
- `account_has_password`
- `account_totp_enabled`

新增稀疏字段放入账号 `data` JSONB：

```text
last_auth_method
last_auth_result
last_auth_error_code
last_auth_attempt_at
last_auth_success_at
password_auth_status              unknown / verified / rejected
password_auth_checked_at
last_auth_fingerprint             SafeFingerprintSummary JSON
last_auth_fingerprint_text        列表安全摘要
last_live_check_fingerprint       SafeFingerprintSummary JSON
last_live_check_fingerprint_text  列表安全摘要
live_check_validation_method      access_token / authenticated_session
```

`protocol_profile_key`、`protocol_profile_version`、原始 `device_id` 和设备层 `browser_profile` 放入 `account_protocol_identities`。注册 Roxy 环境、每条线路、Protocol 新会话和 Roxy fallback 的原始会话标识、代理凭据及 Roxy Profile ID，按 session 分行写入 `account_auth_run_contexts`；一次 operation run 可以有多行上下文，注册账号行尚未创建时允许 context 暂无 `account_id`。账号 API 如需展示 `profile_ref`，由 repository 只读 join 后投影，不把原始 identity 合并回账号 JSONB。

这些字段不参与筛选和抢占，首版不新增普通列或索引。后续只有在出现明确 SQL 筛选需求时才提升。

### 10.2 写入边界

提供三个边界清楚的存储命令组：

1. `ensure_account_protocol_identity(account_id)`：在受限表中原子确保 profile key/version 存在，不修改账号普通 payload。
2. `create_auth_run_context(...)` / `finish_auth_run_context(...)`：为每个实际 session 单独保存或收口私有上下文；fallback 新建行，不覆盖父 session。
3. `finish_account_auth_check(account_id, result)`：在一个事务中写入查活/认证结果、成功的新 AT、Token 元数据和安全摘要。

写入规则：

- 普通 AT probe 有有效 AT 且 `PROFILE_MODE=account_stable` 时读取/确保 Protocol identity；`current` 模式保持随机 session。两种模式都写入独立的最近查活摘要，但不覆盖最近认证摘要。
- 无 AT 的普通查活直接失败，不创建 profile、不领取线路。
- 认证成功才替换 access token 和 session 基础字段。
- 认证失败保留旧 AT、旧密码、TOTP secret 和最近一次成功摘要；只更新最近尝试状态和错误码。
- 密码被拒绝后保留原密码，但把 `password_auth_status` 标为 `rejected`；邮箱 fallback 成功不能把该状态覆盖成 verified。
- 成功或失败都不能把认证会话的临时 `device_id` 写到注册 `device_id` 字段。
- 明确废号才更新独立 `account_status=deactivated`。
- 任务终态和账号结果按现有 task gateway 收口，不能用“加载全表再保存”实现。

### 10.3 并发

- 继续使用账号查活 claim，保证同账号不能同时执行查活/刷新。
- `ensure_account_protocol_identity` 使用单条 `INSERT ... ON CONFLICT ... RETURNING` 或等价事务语义，禁止 Python 先读后写竞争。
- 密码补充、2FA 设置和 Token 刷新若共享账号认证资源，应使用同一账号资源租约；不同任务表的进程内 set 不能作为跨进程互斥依据。
- 同账号刷新重试创建新 run/事件，不覆盖前一次任务历史。

## 11. 模块边界

新增公共账号认证包和路由层，避免继续扩大 `account_liveness.py` 或从 Codex/注册驱动导入私有函数。现有浏览器和现有协议实现分别通过兼容适配器原样调用，新实现走独立 `protocol_v2`：

```text
core/account_auth/
  contracts.py       AuthResult、AuthError、AuthMethod、SafeFingerprintSummary
  policy.py          读取并冻结本次任务的逐步骤实现与 fallback 配置
  router.py          browser_current / protocol_current / protocol_v2 路由，不承载协议细节
  browser_current_adapter.py 调用现有稳定浏览器入口
  protocol_current_adapter.py 调用现有稳定协议入口
  credentials.py     OpenAI 密码/TOTP/旧字段兼容解析
  profile.py         auth profile key、BrowserIdentity、安全摘要
  protocol_v2.py     新 password verify、MFA、email OTP、reauth、callback
  browser_fallback.py 公共 Roxy 兜底入口和能力检测
  service.py         单次认证策略和错误/fallback 决策
```

现有模块调整：

| 文件 | 设计职责 |
| --- | --- |
| `core/live_check_service.py` | 队列、动作边界、代理租约、TaskReporter、持久化收口 |
| `core/account_liveness.py` | 当前实现继续保留；`browser_current/protocol_current` 分别调用原稳定入口，`protocol_v2` 才进入新协议 service |
| `core/session.py` | 接收可选 `BrowserIdentity`，会话 ID 始终新建 |
| `core/account_export.py` | 2FA enroll/activate 调用公共认证协议；移除 Token/TOTP code 日志 |
| `core/roxy_liveness.py` | 当前浏览器能力继续保留，可作为用户选择的主路径，也可作为 Protocol fallback |
| `core/storage/accounts.py` | 暴露 profile ensure 和认证结果写入命令 |
| `core/storage/db_legacy.py` | PostgreSQL 行级实现，禁止覆盖注册 device ID |
| `core/admin_repository.py` | 账号当前页读取安全摘要，不返回内部 key |
| `webui/routes/accounts.py` | 只处理入参、service 调用和紧凑响应 |
| `webui/static/js/modern/accounts.js` | 区分本次查活与最近认证摘要 |
| `webui/static/js/legacy/accounts.js` | 保持兼容展示，不暴露敏感字段 |

浏览器认证能力是注册、Codex、2FA、查活之间的公共边界；新代码不得从 `core.codex_oauth`、`core.registration.roxy` 等驱动导入下划线私有 helper。这里的公共化是“增加稳定适配边界”，不是删除当前 Roxy 实现；旧入口必须保留 characterization tests，确保 `browser_current/protocol_current` 路由行为不漂移。

## 12. 任务事件与 UI

### 12.1 阶段

刷新 AT 使用以下阶段：

```text
network
auth_context
login_password
mfa_challenge
email_otp
oauth_callback
token
roxy_fallback
```

阶段允许 `skipped`，例如密码+TOTP 成功时 `email_otp=skipped`。普通查活只使用 `network` 和 `access_token`，不会出现伪造的 `login_password/email_otp=success`。

当前实现刷新成功后无论实际路径都把 `login_password` 和 `email_otp` 标成功，实施时必须改为由 `AuthResult.auth_method` 精确投影。

### 12.2 任务结果摘要

允许写入：

```text
ok / status / http_status / checked_at / plan
validation_method / auth_method
fallback_used
fingerprint source / profile_version / profile_ref
```

任务 `result_summary` 和事件禁止写入凭据、设备 ID、完整 UA 数组、完整代理、会话标识和原始服务响应。需要保留的原始设备/会话/代理上下文写入专用私有表，错误正文只保存截断和脱敏后的领域摘要。

### 12.3 账号页

账号行展示：

- AT 状态与最近在线验证时间；
- 最近刷新 AT 的认证方式；
- 最近认证画像安全摘要；
- 密码/TOTP 只显示“已保存/未保存”，读取原值仍走专用 secret 接口；
- 失败时展示稳定错误码对应的中文说明和下一步动作。

建议下一步动作：

| 状态 | UI 动作 |
| --- | --- |
| `password_rejected` 且邮箱 fallback 成功 | “AT 已刷新；账号密码需核对/重设” |
| `password_rejected` 且邮箱 fallback 失败 | “核对账号密码和邮箱取码能力” |
| `mfa_secret_missing` | “补录/修复 2FA”，不得显示“重新注册” |
| `email_otp_unavailable` | “检查邮箱取码能力” |
| `auth_page_unknown` | “查看任务详情/尝试 Roxy” |
| `account_deactivated` | 禁用查活、刷新和账号配置动作 |

## 13. 安全修正

实施第一阶段必须同时修正当前日志问题：

- `_exchange_new_token` 不再打印 Token 前缀。
- `_activate_totp` 不再打印 TOTP code。
- Roxy open 不再把 `open_result.raw` 响应或原始 Profile ID 写日志；只记录 profile 是否创建、连接方式和不可逆短 `profile_ref`。
- `fingerprint_summary_text` 不包含 raw device ID、邮箱或完整代理 URL。
- Roxy `open_result` 不进入账号普通列表和任务事件。
- 所有新 detail/result_summary 继续经过 task gateway 的敏感字段过滤，并增加契约测试。

不得依赖“只显示前几位”作为 Token、TOTP 或设备标识的安全处理；这些值完全不进入日志。

## 14. 配置与灰度

配置采用“每个主要步骤独立选择主驱动 + Protocol v2 紧急开关 + 浏览器兜底独立治理”。浏览器是默认主驱动，Protocol 只有用户明确选择时才成为该步骤主驱动：

```text
ACCOUNT_AUTH_V2_ENABLED=False|True
ACCOUNT_LIVE_CHECK_DRIVER=browser_current|protocol_current|protocol_v2
ACCOUNT_TOKEN_REFRESH_DRIVER=browser_current|protocol_current|protocol_v2
ACCOUNT_PASSWORD_LOGIN_DRIVER=browser_current|protocol_v2
ACCOUNT_PASSWORD_SETUP_DRIVER=browser_current|protocol_v2
ACCOUNT_EMAIL_OTP_DRIVER=browser_current|protocol_current|protocol_v2
ACCOUNT_TOTP_LOGIN_DRIVER=browser_current|protocol_v2
ACCOUNT_2FA_SETUP_DRIVER=browser_current|protocol_current|protocol_v2
ACCOUNT_AUTH_PROFILE_MODE=current|account_stable

ACCOUNT_BROWSER_FALLBACK_ENABLED=True|False
ACCOUNT_TOKEN_REFRESH_BROWSER_FALLBACK_ENABLED=True|False
ACCOUNT_PASSWORD_LOGIN_BROWSER_FALLBACK_ENABLED=True|False
ACCOUNT_PASSWORD_SETUP_BROWSER_FALLBACK_ENABLED=True|False
ACCOUNT_EMAIL_OTP_BROWSER_FALLBACK_ENABLED=True|False
ACCOUNT_TOTP_BROWSER_FALLBACK_ENABLED=True|False
ACCOUNT_2FA_SETUP_BROWSER_FALLBACK_ENABLED=True|False

ACCOUNT_AUTH_RAW_CONTEXT_ENABLED=True|False
ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS=30
ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=True|False
```

含义：

- `browser_current`：默认值，调用当前稳定的 Roxy/Selenium 能力；这是主路径，不是只有 Protocol 失败后才能进入的隐藏分支。
- `protocol_current`：调用该步骤已经稳定存在的协议入口；某步骤没有 current 协议能力时，配置页不提供该值。
- `protocol_v2`：调用新建的类型化协议接口；不能通过修改旧函数内部逻辑来伪装成 v2。
- `ACCOUNT_AUTH_V2_ENABLED=false`：只覆盖请求值为 `protocol_v2` 的步骤；这些步骤临时回到 `browser_current`，`browser_current/protocol_current` 不受影响，保存值保留。
- 分步骤开关只对新创建的任务生效。任务入队时解析并保存一份不含敏感值的有效策略快照，运行中修改配置不会让同一个任务前半段走旧实现、后半段走新实现。
- `current`（profile mode）：保持当前每次 Protocol session 随机设备画像。
- `account_stable`：启用账号设备画像，Session ID 仍每次随机。
- `ACCOUNT_BROWSER_FALLBACK_ENABLED=false`：只关闭“Protocol 主路径失败后自动转浏览器”；步骤本身选择 `browser_current` 时仍正常运行浏览器主路径。
- 分步骤 browser fallback 开关只有在总开关开启时生效；关闭某一步后，Protocol 遇到该步不兼容应返回明确状态，不得偷偷调用浏览器。
- 密码登录和密码设置是两个独立步骤：前者验证已有密码，后者创建/补设/重设密码；不得共用一个开关或错误状态。密码设置的 `protocol_v2` 只有在对应真实接口单独验证后才能开放。
- 普通 `live_check` 可选浏览器或协议驱动，但两者都只能做旧 AT probe；浏览器模式不得提交邮箱、密码、OTP/TOTP，也不得借查活刷新 AT。
- `ACCOUNT_AUTH_RAW_CONTEXT_ENABLED=false`：只停止保存每次 run 的原始设备/会话/代理上下文，不改变 identity、认证或查活流程。
- `ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=false`：密码被拒绝/结果未知时安全停止，不发送邮箱 OTP，作为副作用紧急开关。

现有 `LIVE_CHECK_ROXY_FALLBACK_ENABLED` 首版继续兼容读取，但只用于当前 `token_refresh` 的 Roxy 登录兜底，不能作用于普通 `live_check`。迁移到新配置时先做别名映射和冲突告警，不立即删除旧键；两个键冲突时，新键只对 `protocol_v2` 生效，`browser_current/protocol_current` 仍按旧键保持现状。

同一认证 session 有驱动亲和性：步骤选择浏览器时整条步骤由浏览器完成；选择 Protocol 时，一旦提交了密码/OTP/TOTP，就不能把 Cookie 或中间 challenge 注入 Roxy 后从下一步继续。只有按 allowlist 新建一次完整浏览器认证 run，才属于合法 fallback。

配置实施时必须同步 `config/` 默认、环境覆盖、WebUI 编辑白名单、`.env.example`、README 和 `tests/test_config_defaults.py`。所有步骤默认 `browser_current`；用户可以逐项切到 `protocol_current/protocol_v2`，但系统不因灰度成功自动修改其配置。浏览器主路径和 fallback 永久保留，删除它们不属于本设计范围。

推荐目标态仍以 `browser_current` 为默认主路径。需要速度时由用户把具体步骤切到 `protocol_current/protocol_v2`；当 Protocol 被选为主路径时，正常成功不创建 Roxy Profile，只有安全 allowlist 命中才启动浏览器 fallback。

WebUI 配置页按步骤展示“浏览器（默认）/现有协议/Protocol v2”，密码登录和密码设置分成两项。页面同时展示 requested 和 effective 值；全局关闭 v2 时，选择 v2 的步骤保留保存值，但明确标注当前实际执行浏览器。

## 15. 测试设计

### 15.1 设备画像

- 同一账号 key 派生相同 `device_id`、基础硬件画像和 `profile_ref`。
- 不同账号派生不同画像。
- 同一账号两次 `BrowserSession` 的 Sentinel/OAuth/Datadog/React session ID 不同。
- 同一次 run 换代理后设备画像不变，route/Geo 可按真实线路变化。
- `proxy=None` 和 `proxy=""` 语义不退化。
- 安全摘要不包含内部 key、raw device ID、邮箱、Token、Cookie 和代理凭据。
- 摘要函数不消耗随机数、不修改 Cookie、不发网络请求。

### 15.2 认证状态机

- 密码直接 callback 成功。
- 密码响应要求邮箱 OTP。
- 密码响应进入 MFA，TOTP 成功。
- 密码请求已发出但没有收到可判定响应时，结果为 `password_result_unknown`；不得记成密码错误或自动重交密码。
- TOTP 临近窗口切换时等待后再提交。
- TOTP 明确无效时最多跨窗口重试一次。
- 密码拒绝不换线路重试、不自动删除密码；只允许创建新会话后邮箱 fallback 一次。
- 密码错误后邮箱 OTP 成功，整体任务成功但保留 `password_auth_status=rejected` 和 warning。
- 密码错误后邮箱 OTP 又进入 MFA challenge，可继续用保存的 TOTP 完成。
- 密码错误和邮箱 fallback 都失败时，结果同时保留两个错误来源。
- 远端要求 MFA 但本地缺 secret，返回 `mfa_secret_missing`。
- 无密码但有旧 AT 走 reauth 邮箱 OTP。
- 无密码且无旧 AT 走普通邮箱 OTP。
- 明确废号不进入任何 fallback。
- 工作流未知才进入一次 Roxy fallback。

### 15.3 查活边界

- 普通查活有有效 AT：`account_stable` 模式读取/确保账号级 Protocol 画像，`current` 模式不建 identity；两者都以新 session 调用在线 probe。
- 普通查活无 AT：直接失败并提示刷新，不领取认证线路、不创建 profile、不读密码。
- 普通查活 AT 失效：不自动登录、不发送 OTP。
- 刷新 AT 才允许调用账号认证 service。
- 普通查活只写独立的最近查活摘要，不覆盖最近认证画像。

### 15.4 PostgreSQL

- 并发 6 个 worker 对同账号 ensure profile，只产生一个 key/version。
- 认证成功在一次事务中更新 AT、Token metadata、状态和安全摘要。
- 认证失败保留旧 AT 和最近一次成功摘要。
- 查活不覆盖注册 `device_id`。
- 启动恢复不改变账号行数。
- 同一 operation run 的换线、新邮箱 session 和 Roxy fallback 分别保存上下文，不互相覆盖。
- raw context 开启时，私有表可查到原始设备/会话/代理；关闭时认证行为不变，只跳过私有原始上下文写入。
- 普通账号/任务 API、事件、日志和兼容导出不包含 `protocol_profile_key`、原始 device/session/proxy、密码、TOTP、Token。
- 账号分页 SQL 次数不随总账号数线性增长。

### 15.5 任务和 UI

- `live_check` 与 `token_refresh` 任务类型和文案分开。
- 密码+TOTP 路径不会把邮箱 OTP 标为成功。
- 所有事件和任务日志均通过敏感值扫描。
- 账号列表和任务详情明确区分“最近查活摘要”与“最近认证摘要”。
- 现代和兼容 UI 都覆盖 HTML 转义和空字段兼容。
- 配置 UI 展示每一步的“当前稳定实现 / Protocol v2”和浏览器兜底状态；保存后只影响新任务。
- 全局 v2 关闭时，UI 明确显示分步骤配置被临时覆盖，不修改其保存值。

## 16. 实施顺序

### 阶段 0：冻结基线

- 记录当前目标测试和完整测试结果。
- 固化普通查活“不登录”的现有契约。
- 为当前 Token/TOTP 日志泄漏增加失败测试。
- 不运行真实注册或批量刷新。

### 阶段 1：纯模型与安全修正

- 新增 contracts、错误码和 SafeFingerprintSummary。
- 修正 Token/TOTP 日志。
- 给 Protocol/Roxy 增加只读安全摘要，暂不落库、不改变认证策略。
- 完成纯单元测试。

### 阶段 2：稳定设备画像与存储

- 实现 `BrowserIdentity`，只稳定设备层。
- 实现 PostgreSQL 原子 ensure 和安全摘要写回。
- 停止查活覆盖注册 `device_id`。
- 接入任务详情和账号“最近认证”展示。
- 使用独立 worktree 和独立数据库完成迁移/并发测试。

### 阶段 3：密码与 MFA 协议链

- 实现公共 password verify、MFA challenge/verify 和响应状态机。
- 新代码只进入 `protocol_v2` adapter；步骤选择 `browser_current/protocol_current` 时不得触达。
- 完成 mock/fixture 测试后，单账号手动开启对应步骤的 `protocol_v2` 验证。

### 阶段 4：灰度和 fallback 收敛

- 先验证一批有密码无 2FA 账号，再验证有密码+TOTP 账号。
- 对比成功率、OTP 消耗、平均耗时、网络错误和 Roxy fallback 率。
- 确认错误分类后再逐步骤允许定时 Token 刷新使用 `protocol_v2`。
- 不在同一发布中同时改变 Roxy Profile 生命周期。

### 阶段 5：默认切换与长期双实现维护

- 默认值保持 `browser_current`；协议灰度结果用于证明“可供用户选择”，不自动把默认主路径切成协议。
- `browser_current`、`protocol_current` 和浏览器 fallback 长期保留，不设置自动清理计划。
- 新代码停止继续复制旧 helper；已有稳定 helper 保留，由 adapter 封装。未来如需删除必须另立设计、迁移和用户确认，不能作为本次兼容清理顺手完成。
- 更新当前架构、兼容清单和操作手册。

每阶段独立提交、可单独回滚。涉及存储的阶段必须在独立 worktree + 独立数据库开发，不允许未完成代码留在生产工作目录后重启 WebUI。

## 17. 验收标准

全部满足才视为完成：

1. 普通查活不会触发任何登录或 OTP。
2. 密码账号可刷新 AT；遇到 MFA 可用保存的 TOTP 完成认证。
3. 密码/TOTP 错误不会通过换线路重复提交；密码错误只允许一次邮箱 OTP fallback。
4. 同账号普通查活、刷新 AT 和 Protocol 2FA 的设备画像稳定，但每次 session/trace 标识不同。
5. Protocol 和 Roxy 都能产生同结构安全摘要，且不包含敏感值。
6. 查活不再覆盖注册 `device_id`。
7. 认证成功原子写回新 AT；失败保留旧 Token、密码、TOTP 和成功检查点。
8. 账号页明确区分“本次 AT 查活”和“最近认证画像”。
9. 任务事件准确显示密码、MFA、邮箱 OTP 和 fallback 的实际状态。
10. PostgreSQL 并发、启动恢复、列表紧凑响应和敏感字段测试全部通过。
11. 单账号灰度没有出现意外注册、重复 OTP、重复密码提交或账号行数变化。
12. 完整测试、`ruff check .`、`git diff --check` 通过，且没有修改/提交 `.env`、日志、`run/`、账号、Token、邮箱池和 `.venv/`。
13. 每个步骤都能独立选择浏览器或可用协议实现；默认浏览器，全局关闭 v2 只覆盖选择 v2 的步骤。
14. 步骤选择浏览器时直接创建主路径 Profile；步骤选择 Protocol 时，fallback 关闭不创建 Profile，开启且命中 allowlist 时最多启动一次独立 fallback run。
15. browser_current/protocol_current 的 characterization tests 与上线前基线一致，且没有删除当前密码、查活、邮箱 OTP、TOTP/2FA 或 Roxy 入口。

## 18. 已确认与待确认决策

已确认：

1. 密码明确拒绝后，同一刷新 AT 任务允许受控改走一次邮箱 OTP。
2. 邮箱 fallback 必须记录密码已失效；不得删除/覆盖密码，也不得把 fallback 成功显示成密码成功。
3. 当前密码、查活、邮箱 OTP、TOTP/2FA、现有协议和 Roxy 实现长期保留；每一步可以单独选浏览器、现有协议或 Protocol v2。
4. 浏览器是默认主路径；现有协议和 Protocol v2 由用户逐步骤选择，Protocol 被选中时浏览器仍可作为兜底。

仍待进入实施前确认：

1. 灰度验证通过后，账号级 Protocol 认证画像是否默认启用，还是继续保留为手动配置。
2. Roxy 与 Protocol 安全摘要对比后，是否有必要另做“跨驱动认证上下文交接”；本次只观测，不承诺跨驱动完全一致。

除以上两项外，普通查活边界、敏感值规则、PostgreSQL 事实来源和不整体合并上游均为本设计固定约束。
