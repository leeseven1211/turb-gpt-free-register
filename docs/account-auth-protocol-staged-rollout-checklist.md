# 账号认证协议能力分阶段实施清单

> 本文是本次改造唯一的实施顺序和放行依据。两份完整设计文档只作为技术背景；如果表述冲突，以本清单为准。

- 基线：`main@d038f2a`
- 当前状态：开发阶段已全部完成并通过隔离回归；阶段 3 经上游核对确认没有独立的普通 AT probe，按“不冒充实现”关闭为不适用。普通查活的 `protocol_current` 与 `browser_roxy` 均可配置，浏览器 probe 仍默认关闭；Protocol v2 只用于显式“刷新 AT”认证，密码、TOTP、邮箱 challenge、错误密码和浏览器兜底边界均已实现，旧链路仍是默认。稳定 Protocol identity、受限 raw context、安全指纹摘要、清理调度、日志脱敏、私有读取审计和注册账号邮箱来源恢复均已完成；raw context 的 HTTP 原始值读取及加密存储不开放，因此原始上下文默认仍关闭。剩余的是本地环境的放量门禁，不是未完成的业务代码
- 总原则：现有能力先冻结，新能力只做平行增量；每一阶段独立验证、独立放行、独立回退

### 本轮执行记录（2026-09-02）

- 实施分支：`codex/staged-live-check-driver`；主工作区 `main` 未修改。
- 已创建独立本地 PostgreSQL 数据库 `turb_live_check_test`，项目表结构已初始化；未连接生产库 `turb_console`。
- 阶段 1：`protocol_current` 默认路径、驱动冻结、任务事件/结果摘要记录、单任务 override 和 WebUI 配置已完成。
- 阶段 2：`browser_roxy` 已接入并完成真实契约样本；`ACCOUNT_LIVE_CHECK_BROWSER_ENABLED` 默认仍为 `False`，需要本地明确开启。
- 真实样本：有效 AT 8 次均 HTTP 200；不可用 AT 3 次均 HTTP 401；不可用本地代理 2 次均归类为 `browser_navigation` 且可重试；每次临时 Profile 登记数均回到 0。
- 本轮在隔离库同一测试账号上追加 4 次真实 Roxy 普通查活（首次验证 1 次、串行重复 3 次），4 次均 `ok=True / HTTP 200 / validation_method=access_token`，且每次执行后的临时 Profile 登记数均为 0；同一 AT 的 `protocol_current` 对比也为 `ok=True / HTTP 200`。此前累计有效 Roxy 样本已超过 10 次。
- 本次最终复核继续使用隔离库 `v2_refresh_e2e_20260902` 的测试账号：`browser_roxy` 连续 3 次均 `ok=True / HTTP 200 / validation_method=access_token`，每次 Roxy 临时 Profile 登记数均回到 0；未登录、未读取邮箱/密码/TOTP、未刷新 AT。
- 在独立 `raw_context_real_20260902` schema 中完成一次真实 raw context 端到端验证：Roxy 查活成功后记录为 `live_check / browser_roxy / access_token`，`status=success`、`cleanup_status=done`，只落白名单 Profile/端点键和线路摘要；随后以 `local-validation / real-roxy-contract / identifiers` 完成审计读取。该 schema 仅用于本地验证，不改变项目 `.env` 的 `turb_console/public` 默认配置。
- 另有 4 次 Roxy 创建/浏览器层瞬时失败，分别落在 Profile/浏览器执行/页面导航错误分类；这属于本机 Roxy 服务的运行稳定性门禁，不能通过代码测试消除，因此不放开浏览器默认路径，但不影响显式配置和失败收口。
- 独立库端到端任务已验证：有效 AT 查活任务成功完成并写回 `live`；失效 AT 任务完成为 `failed`，结果摘要记录 HTTP 401 和 `error_category=auth`；两类任务均记录 `browser_roxy`。
- 上游核对未发现独立的 `protocol_v2` 普通 AT probe；因此没有把密码/MFA 认证链冒充成普通查活，阶段 3 已按“不冒充实现”关闭为不适用。
- 本轮新增刷新 AT 专用 `protocol_v2`：密码直达 callback、密码+TOTP MFA、邮箱 challenge、密码错误分类、未知响应分类和可选一次邮箱兜底均有独立状态机/单测；默认配置仍为 `legacy`，普通查活不触达。
- 真实测试：在一个已有密码、TOTP 和 AT 的本地测试账号上执行一次真实 Protocol v2，结果为 `password_mfa_totp`、`authenticated_session`、`live`；未启用邮箱兜底，未写回数据库。
- 真实错误密码测试：同一测试账号返回 `HTTP 401`，响应结构化错误码为 `invalid_username_or_password`；已分类为 `password_rejected` / `auth`，不会进入 Roxy、不会自动重试密码、默认不会发邮箱 OTP。
- 本次最终复核的 Protocol v2 正确密码路径按账号功能正式申请 1024Proxy JP 租约，返回 `password_mfa_totp`、`authenticated_session`、`live`，`fallback_used=False`，租约已释放；错误密码复核返回 `password_rejected` / `auth`，`fallback_used=False`、`roxy_fallback_allowed=False`，没有重复提交或发送邮箱。
- 真实邮箱兜底测试：仅进程内打开邮箱兜底，使用新 session 发起一次验证码请求并等待 45 秒；转发邮箱 IMAP 登录和 `INBOX` 打开正常，但未收到该别名的新 OpenAI OTP，最终为 `password_rejected_email_fallback_failed` / `email`。因此邮箱兜底仍未判定成功，也没有继续重发。
- 后续生产账号 238 的受控探针确认了失败位置：账号来源为 `icloud_hide`，本地 `forward_imap` 健康；`/api/accounts/email-otp/send` 在 Referer 仍为 `/log-in/password` 时返回 `302 -> /error`，自动跟随后表现为 `200 text/html`，且发送后收件箱没有新 OTP。新实现不再把该响应当作发送成功，也不再从密码页直接调用发送接口；明确返回 `passwordless_fallback_unavailable`，交给后续显式浏览器/人工策略。
- 本轮顺手为 `forward_imap` 增加 `ICLOUD_HME_REQUEST_TIMEOUT` socket 超时，避免收件链路卡死；对应单测已补齐。
- 针对上游 `fd7766f` / `369d8eb` 的取码修复已按当前 PostgreSQL 架构最小移植：已注册账号优先使用落库的 `email_source`，Outlook 邮箱池记录被清理后可从已注册账号快照恢复；来源不一致时不会误读 Outlook 池。
- 上一轮隔离 schema 全量回归为 `673 passed, 24 subtests passed`；加入稳定 identity 后为 `682 passed, 24 subtests passed`；加入受限 raw context 存储边界后为 `686 passed, 24 subtests passed`；本阶段安全指纹摘要定向验证为 `48 passed`，协议专项为 `19 passed`，日志脱敏后为 `694 passed, 24 subtests passed`，审计读取原语后为 `697 passed, 24 subtests passed`，本轮接入普通查活/Roxy/套餐查询的可选上下文记录后为 `700 passed, 24 subtests passed`；最后在隔离数据库 `turb_live_check_test` 的临时 `test_*` schema 上复核仍为 `700 passed, 24 subtests passed`。另修复一个独立的 `registration_debug` 终端上下文覆盖问题，该修复只在数据库缺少新 evidence 时保留会话内已有 evidence，不改变注册行为。
- 阶段 8 第一小步：新增私有 `account_protocol_identities` 表、账号行锁保护的幂等创建、版本化 HMAC 派生和 `ACCOUNT_AUTH_PROFILE_MODE` 配置；只有 `account_stable + protocol_v2` 刷新才会懒创建并把同一身份传给每个 Protocol 会话。`current` 默认完全不建表行、不改变现有随机画像；稳定画像不保存 geo/locale/timezone、session/trace、Sentinel 或 Roxy 标识。Protocol v2 成功认证另写入白名单安全指纹摘要，账号行和任务结果不接收原始设备/session/代理凭据。
- 稳定画像单测验证同一 key 的 device/profile 稳定、不同会话的 session/sentinel ID 仍变化、并发 ensure 只生成一行；受限 run context 已完成白名单、保留期、编号锁、收口、过期清理、审计读取，以及 Protocol v2、`protocol_current`、Roxy 普通查活和套餐查询的可选记录接入测试；真实 Roxy 稳定性门禁仍单独保留。

相关背景：

- [账号认证、查活与指纹总体设计](account-auth-liveness-fingerprint-design.md)
- [账号认证、查活与指纹详细实施设计](account-auth-liveness-fingerprint-implementation-design.md)

## 1. 先统一三个事实

### 1.1 当前真实路径

| 功能 | 当前真实路径 | 本次处理 |
| --- | --- | --- |
| 注册、注册密码、注册恢复 | Roxy/Selenium 浏览器 | 保持不动，继续作为稳定主路径 |
| 普通查活 | live-check router；默认 `check_account_plan()` + `BrowserSession` 的协议型旧 AT probe，可显式选择 `browser_roxy` | 保持默认行为，不登录、不发 OTP；选择 Roxy 时也只验证已有 AT |
| 刷新 AT | 当前协议邮箱 OTP 登录；失败后可进入 Roxy fallback | 与普通查活继续严格分开 |
| Codex 密码/TOTP 登录 | 当前 Roxy 浏览器状态机 | 保持不动 |
| 2FA 设置 | 当前协议和 Roxy 已有能力 | 保持不动，新接口单独灰度 |
| GitHub 新协议功能 | 尚未接入生产业务路由 | 逐功能移植，不整体合并提交 |

这里所说的 `BrowserSession` 是协议请求使用的浏览器指纹会话，不等于 Roxy 真浏览器。当前没有一条可直接复用的“Roxy 普通查活”完整路径；如果要让普通查活可选 Roxy，必须新增一个**只使用旧 AT 的浏览器 probe**，不能拿现有 Roxy 登录刷新流程冒充。

### 1.2 用户目标

- 注册、密码、TOTP、2FA 等认证主路径仍以现有浏览器能力为基础。
- 普通查活允许用户明确选择现有协议或 Roxy 浏览器 probe；GitHub `protocol_v2` 只用于显式刷新 AT 认证，不作为普通查活驱动。
- GitHub 新协议能力用于提速和补充，不自动取代当前稳定能力。
- 浏览器能力永久保留；Protocol 被选择时，只有符合安全条件才允许启动一次完整浏览器 fallback。

### 1.3 不可突破的红线

- [x] 不整体 cherry-pick/merge 上游认证提交。
- [x] 不在现有稳定函数内部悄悄替换成新协议。
- [x] 不删除现有浏览器、现有协议、邮箱 OTP、TOTP 或 2FA 入口。
- [x] 普通查活只验证已有 AT，绝不登录、发 OTP、提交密码/TOTP 或获取新 AT。
- [x] 普通查活不做自动跨驱动 fallback，避免掩盖用户所选驱动的真实结果。
- [x] 同一次认证 session 不混用 Protocol Cookie/challenge 与 Roxy 中间状态。
- [x] 不改写现有注册 `device_id`、密码、TOTP secret、AT 或最近成功检查点。
- [x] 不在日志、任务事件、普通 API 或账号列表暴露 Token、密码、OTP、Cookie、完整代理凭据。
- [x] 不在当前生产工作区直接试验存储层；使用独立 worktree 和独立测试数据库。
- [x] 未通过本阶段退出条件，不开始下一阶段。

## 2. 分阶段总览

| 阶段 | 内容 | 对现有默认行为的影响 | 当前状态 |
| --- | --- | --- | --- |
| 0 | 冻结基线与隔离环境 | 无 | 已完成；独立库、隔离 worktree、真实样本和 characterization 已记录 |
| 1 | 查活路由壳，先只接现有协议 | 无 | 已完成 |
| 2 | 新增 Roxy 旧 AT 浏览器 probe | 默认不启用 | 已完成；真实样本通过，默认 gate 继续关闭 |
| 3 | 接入 GitHub `protocol_v2` 查活 | 默认不启用 | 不适用；上游没有独立普通 AT probe，已保留明确拒绝 |
| 4 | 查活小流量放行与用户配置 | 只影响显式选择的任务 | 已完成代码；可单任务 override/全局配置，浏览器 gate 需本地明确开启 |
| 5 | 新协议密码登录 | 浏览器仍默认 | 已完成“刷新 AT 专用”认证；独立无副作用密码登录 API 不新增 |
| 6 | TOTP 与邮箱 OTP challenge | 浏览器仍默认 | 已完成状态机和错误边界；真实邮箱样本因未收到新 OTP，兜底默认关闭 |
| 7 | 新协议 2FA 设置 | 浏览器仍默认 | 已完成；复用现有协议开通 + 浏览器安全设置回退和检查点 |
| 8 | 稳定设备画像与受限原始上下文 | 默认保持 current；raw context 默认关闭 | 已完成可安全落地部分；原始值不开放 HTTP 读取，且未配置加密密钥时不建议开启 |
| 9 | 长期双实现维护 | 不删除旧实现 | 已完成本轮双实现契约测试、配置回退和差异审查规范 |

## 3. 阶段 0：冻结基线与隔离环境

目标：先证明“什么都不改时系统能正常工作”，并准备不会碰生产数据的实现环境。

### 实施项

- [x] 记录 `main` 基线 commit、分支、工作区状态和当前生效配置摘要。
- [x] 创建 `codex/` 前缀的独立 worktree/分支。
- [x] 创建独立 PostgreSQL 测试库；不得连接生产 `turb_console`。
- [x] 准备一个可牺牲测试账号和独立邮箱，不批量使用现有账号。
- [x] 冻结现有普通查活、刷新 AT、Roxy 登录、密码、TOTP、2FA 的 characterization tests。
- [x] 对以下现状各保存一份脱敏任务事件和网络请求序列：
  - [x] 有效 AT 普通查活成功。
  - [x] 失效 AT 普通查活返回失败且不登录。
  - [x] 刷新 AT 的当前协议邮箱 OTP 成功。
  - [x] 当前协议失败后 Roxy fallback 成功或明确失败。
  - [x] 代理不可用、超时和 401 的分类结果。
- [x] 运行相关测试、Ruff 和 whitespace 检查，保存基线结果。

### 退出条件

- [x] 独立环境不会读写生产账号和任务表。
- [x] 现有网络动作、持久化字段和任务状态已有可比较基线。
- [x] 现有测试全部通过；失败项必须先解释，不带病进入阶段 1。

### 回退

本阶段不改业务代码，无需业务回退。

## 4. 阶段 1：只增加查活路由壳，不改变行为

目标：先建立可配置、可观测的路由边界，但第一版只允许调用当前稳定普通查活。

### 配置

仅新增一个配置，不预先加入密码、TOTP、2FA 的开关：

```text
ACCOUNT_LIVE_CHECK_DRIVER=protocol_current
```

允许值按阶段逐步开放：

| 值 | 开放阶段 | 含义 |
| --- | --- | --- |
| `protocol_current` | 阶段 1 | 当前 `check_account_plan()` 旧 AT probe；升级兼容默认 |
| `browser_roxy` | 阶段 2 | 新增 Roxy 浏览器旧 AT probe，不是登录 |
| `protocol_v2` | 阶段 5/6 | 显式刷新 AT 的密码/MFA 认证，不是普通查活 |

配置缺失时必须解析为 `protocol_current`，因为这才与当前线上普通查活一致。等 `browser_roxy` 验证通过后，用户可以显式切到浏览器；不能在升级时悄悄改变默认网络路径。

### 实施项

- [x] 新增窄职责 live-check router，只做配置解析和 adapter 选择。
- [x] `protocol_current` adapter 原样调用当前入口，不复制逻辑。
- [x] 配置、WebUI 编辑白名单、`.env.example`、README 和配置测试同步增加。
- [x] 任务入队时冻结 `requested_driver` 和 `effective_driver`。
- [x] 任务事件和结果摘要记录驱动名称，不记录敏感配置。
- [x] 提供单任务 driver override，仅供管理员灰度；全局默认不随单次选择改变。
- [x] 未开放的值在远端请求前明确拒绝，不能静默退回其他驱动。

### 退出条件

- [x] 不配置新键时，请求序列、结果和当前版本完全一致。
- [x] 显式选择 `protocol_current` 时，与未加 router 的冻结基线一致。
- [x] 非法/未开放 driver 不领代理、不创建 Roxy Profile、不改账号状态。
- [x] 关闭新路由后可直接回到原入口。

### 回退

- 配置恢复 `protocol_current`。
- router 保留但只允许 current adapter；无需回滚数据库。

## 5. 阶段 2：新增 Roxy 普通查活 probe

目标：让普通查活真正具备浏览器选项，同时保持“只验证旧 AT”。

### 实施项

- [x] 新增独立的 `browser_roxy` adapter，不调用现有登录刷新函数。
- [x] 每次任务创建临时 Roxy Profile，使用账号代理和浏览器环境。
- [x] 只在受控浏览器 context 中携带旧 AT 请求查活接口。
- [x] AT 只能存在于本次内存请求头；不得写入持久 Cookie、localStorage 或 Profile 数据。
- [x] 禁止打开登录/authorize 页面，禁止读取邮箱、密码和 TOTP。
- [x] 任务结束幂等关闭并软删除临时 Profile。
- [x] Profile 创建失败、页面/CDP 未识别、超时和 HTTP 结果分别分类。
- [x] 加入网络契约测试，断言没有 signin、authorize、email-verification、OTP 请求。

### 灰度样本

- [x] 有效 AT：累计超过 10 次重复 probe，确认结果稳定且没有登录动作。
- [x] 明确 401/失效 AT：至少 3 次，必须直接返回失效。
- [x] 代理失败、Roxy 容量不足、CDP 超时：每类至少 2 次并分别归类。
- [x] 与 `protocol_current` 对同一测试账号的结果做成对比较。

### 退出条件

- [x] 浏览器 probe 零登录、零 OTP、零 Token 刷新。
- [x] 成功/401/网络错误不会互相误判。
- [x] 所有临时 Profile 均完成关闭和软删除。
- [x] `protocol_current` 默认路径无回归。

> 说明：代码和契约退出条件已满足；由于本机 Roxy 仍出现过浏览器服务瞬时失败，`ACCOUNT_LIVE_CHECK_BROWSER_ENABLED` 保持默认 `False`。这不是隐藏 fallback：用户开启后仍会明确使用 `browser_roxy`，失败会作为该驱动结果收口。

### 回退

将 `ACCOUNT_LIVE_CHECK_DRIVER` 改回 `protocol_current`；`browser_roxy` adapter 保留但不可达。

## 6. 阶段 3：核对 GitHub `protocol_v2` 普通查活能力

目标：只移植新协议查活所需的最小能力，不引入密码、OTP 和 2FA 状态机。

### 实施项

- [x] 根据已验证真实请求逐段移植，不复制上游整个任务/存储/UI 框架；已完成上游提交和当前仓库接口核对。
- [x] 新建 `protocol_v2` adapter，与 `protocol_current` 物理分离；核对结果是上游没有可移植的普通 AT probe，因此 adapter 不对普通查活宣称支持。
- [x] 复用现有 AT、账号代理租约、任务队列和 PostgreSQL 写回边界；仅用于已实现的显式刷新 AT 认证链。
- [x] 第一版只保存安全指纹摘要；稳定设备画像使用新增 nullable 数据，不覆盖注册 device ID。
- [x] 每个 run 使用新的 session/trace 标识，不能把稳定画像误做成长久 session。
- [x] 对响应采用类型化结果：成功、401、账号不可用、风控、代理错误、超时、未知响应。
- [x] 保存脱敏 fixture，禁止保存 Token、Cookie、邮箱 OTP 和完整代理。
- [x] 上游没有独立普通 AT probe，普通查活配置为 `protocol_v2` 时在远端请求前明确返回“不支持”；不会把认证失败伪装成查活结果，也不会自动改走浏览器。

### 灰度样本

- [x] 使用阶段 2 的同一组有效、失效和网络异常样本核对“普通查活不支持 v2”。
- [x] 三路结果比较项已审查并关闭为不适用：`protocol_v2` 没有普通查活接口。
- [x] 重复运行验证设备层稳定、session/trace 层每次变化。
- [x] 验证 401 不被本地 JWT 到期时间或浏览器成功结果覆盖。

### 退出条件

- [x] `protocol_v2` 作为普通查活驱动会在远端请求前明确拒绝；不存在“三路结果”可比较的假实现。
- [x] 新协议普通查活不存在登录、OTP、密码或 2FA 请求；认证链只在独立刷新 AT 动作中运行。
- [x] 新画像数据可以停写，不影响账号查活。
- [x] 切回 `protocol_current` 后不需要数据回滚。

> 结论：阶段 3 不是“代码未完成”，而是上游没有独立普通 AT probe。保留 `protocol_v2` 的明确拒绝比伪造一个普通查活实现更安全；`protocol_v2` 不能写入 `ACCOUNT_LIVE_CHECK_DRIVER`。

### 回退

将 driver 改回 `protocol_current` 或已验证的 `browser_roxy`；禁用 `protocol_v2` 能力声明。

## 7. 阶段 4：普通查活小流量放行

目标：让用户可以自己配置，但不自动替用户改变生产默认。

### 放量顺序

- [x] 单个测试账号通过单任务 override 运行；接口现在接受 `driver`，入队前校验且只作用于普通查活。
- [x] 小批量灰度入口已完成，普通查活请求不会转成批量刷新 AT；具体 5 个账号放量仍由本地操作员选择账号后执行。
- [x] 任务事件、结果摘要、HTTP 结果、代理错误、Roxy Profile 清理和任务投影均可观察。
- [x] 用户在 WebUI 显式选择全局 driver 后才改变后续任务默认值；单次 override 不写回全局配置。
- [x] 页面同时显示 configured driver 与本次 effective driver。

### 用户最终可选

```text
ACCOUNT_LIVE_CHECK_DRIVER=protocol_current  # 保持现状
ACCOUNT_LIVE_CHECK_DRIVER=browser_roxy      # 浏览器旧 AT probe
```

`protocol_v2` 不在普通查活选项中：上游没有独立的旧 AT probe，不能把密码/MFA 认证接口冒充为查活。

如果希望普通查活以浏览器为主，阶段 2 通过后显式配置 `browser_roxy`。协议仍可随时手动切回。系统不得根据成功率自动修改该配置。

### 停止条件

出现以下任一情况立即停止放量并切回 `protocol_current`：

- [x] 普通查活触发登录或 OTP：当前契约测试和真实样本均未发生；若发生立即停止并切回 `protocol_current`。
- [x] 旧 AT、密码、TOTP、注册 device ID 被覆盖：写回边界已锁定；若发生立即停止。
- [x] 同一账号不同 driver 的核心结论无法解释：结果摘要保留 effective driver；若出现立即停止。
- [x] 临时 Roxy Profile 泄漏或任务无法收口：adapter 已有幂等清理和分类；若出现立即停止。
- [x] Token/代理凭据出现在日志或普通 API：已有 redaction/allowlist；若出现立即停止。

## 8. 阶段 5：新协议密码登录

目标：在显式“刷新 AT”任务中接入密码验证；注册、Codex 登录和账号密码补设仍继续使用现有浏览器主路径。本阶段不新增一个没有调用方的“通用密码登录 API”，避免配置看似生效但实际没人使用。

### 配置

实际使用的配置是现有刷新 AT 驱动：

```dotenv
ACCOUNT_TOKEN_REFRESH_DRIVER=legacy|protocol_v2
ACCOUNT_AUTH_V2_ENABLED=False|True
ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=False|True
```

默认 `legacy` + `ACCOUNT_AUTH_V2_ENABLED=False`。密码登录和密码创建/补设是两件事；前者只在显式刷新 AT 的 Protocol v2 状态机中使用，后者仍由 `ACCOUNT_PASSWORD_DRIVER=roxy` 负责。

### 实施项

- [x] 新增独立 Protocol v2 刷新认证 service，不替换现有 Roxy 入口。
- [x] 密码从账号受控事实来源读取，不复制到画像或任务表。
- [x] 识别正确密码、明确错误、MFA challenge、邮箱验证、未知页面和请求结果未知。
- [x] Protocol 响应没有可识别落点时返回 `auth_page_unknown` 并停止，不盲点按钮；若进入现有浏览器兜底，则由 Roxy 自己的页面状态机处理识别失败。
- [x] 密码提交 `request_unknown` 时禁止自动切浏览器重复提交。
- [x] 明确密码错误仅在 `ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=True` 时另起一次邮箱会话，但必须保留密码状态为 `rejected`。
- [x] fallback 成功显示为邮箱认证成功，不显示成“密码登录成功”。

### 必测场景

- [x] 正确密码，无 MFA。
- [x] 正确密码，进入 TOTP。
- [x] 正确密码，进入邮箱 OTP。
- [x] 明确错误密码。
- [x] 本地没有密码。
- [x] 密码页未识别、控件缺失、提交超时和返回未知。
- [x] 页面要求其他验证方法、重新发送或返回上一步；协议路径根据结构化 challenge 选择接口，浏览器路径由现有页面状态机处理。

### 退出条件

- [x] 默认浏览器路径网络序列和结果无变化。
- [x] 新协议只对显式选择 `protocol_v2` 且开启总开关的刷新任务可达。
- [x] 错误密码、未知结果和远端页面变化不会触发循环或重复提交。

## 9. 阶段 6：TOTP 与邮箱 OTP challenge

目标：补全密码登录后的 challenge，不把所有 fallback 塞进一个状态机分支。

### 配置

TOTP 和邮箱 OTP 是 Protocol v2 密码认证的子状态，不另外增加未接入执行器的配置键：

```dotenv
ACCOUNT_TOKEN_REFRESH_DRIVER=protocol_v2
ACCOUNT_AUTH_V2_ENABLED=True
ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=False
```

### 实施项

- [x] 页面/协议返回先分类，再决定 TOTP、邮箱 OTP 或停止。
- [x] TOTP 只在远端明确要求且本地存在 secret 时生成。
- [x] TOTP 每个时间窗限制提交次数，防止快速重复。
- [x] 协议邮箱 OTP 通过明确的 send/validate 接口完成并在无 continue URL 时停止；现有浏览器 fallback 继续由页面状态机处理“其他方式/发送/重新发送/输入/继续”按钮。
- [x] OTP 读取设置严格的接收时间边界，拒绝历史验证码；已登记账号优先使用落库 `email_source`。
- [x] 缺少协议落点或浏览器控件时保存脱敏结果并返回明确失败/attention 语义，不盲点。
- [x] 密码明确错误后的邮箱 fallback 与正常邮箱 challenge 分开记录。
- [x] 任何 challenge 完成后都重新读取远端 session，不能凭点击或接口返回片段推断成功。

### 退出条件

- [x] 密码、TOTP、邮箱 OTP 的状态和结果来源可区分。
- [x] 不会因为识别不到页面而无限等待、盲点或重复发验证码。
- [x] 任一步切回浏览器都启动新的完整 run，不注入 Protocol 中间状态。

> 真实邮箱兜底样本曾因测试别名未收到新 OTP 而失败；因此兜底仍保持默认关闭。这是外部收件结果门禁，不是把失败误报为成功。

## 10. 阶段 7：新协议 2FA 设置

目标：最后接入会改变账号安全状态的能力。

### 配置

```dotenv
TWOFA_DRIVER=auto|protocol|browser
ACCOUNT_2FA_DRIVER=auto|protocol|browser
ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED=True|False
ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED=True|False
```

注册主链路和账号补全分别使用已有真实配置键；公开值统一为 `auto`、`protocol`、
`browser`。`auto`/`protocol` 在单独补 2FA 时优先复用已有 AT，没有 AT 或 MFA 要求近期
认证时先通过协议邮箱 OTP 重认证取得新 AT；协议仍失败时由
`ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED` 控制是否进入现有浏览器安全设置页。组合补密码
和 2FA 时则复用 Roxy 登录会话取得新 AT，再由协议完成 2FA。旧配置值
`protocol_direct` 继续兼容，但归一为 `auto`，不再作为单独选项。

### 实施项

- [x] enroll、secret 检查点、activate、远端确认分成独立步骤。
- [x] secret 拿到后立即写入受控事实来源，不写任务日志。
- [x] 只有远端确认 activate 成功后才标记 2FA enabled。
- [x] 中断重试从检查点恢复，不能重复创建并覆盖已有 secret。
- [x] 测试重复设置、已有 2FA、错误 TOTP、activate 超时和远端结果未知。
- [x] 协议失败不破坏当前浏览器重试能力；回退会把已有 secret 作为检查点传入。

### 退出条件

- [x] 中断、超时、重复执行都不会让本地与远端 2FA 状态被错误标记为一致。
- [x] 当前浏览器和现有协议入口仍可单独使用。

## 11. 阶段 8：稳定设备画像与受限原始上下文

目标：在协议功能稳定后再增加诊断数据，避免数据模型先于业务能力扩张。

### 分层保存

| 数据 | 是否稳定复用 | 存储位置 | 普通 UI/API |
| --- | --- | --- | --- |
| 账号设备画像 seed/摘要 | 是 | 账号认证 profile | 只显示安全摘要 |
| 原始设备 ID | 按账号/驱动保存 | 受限私有表 | 不返回 |
| session/trace 标识 | 每次 run 新建 | 受限 run context | 不返回原值 |
| 完整代理凭据 | 不作为账号画像复用 | 受限 run context/既有代理事实来源 | 只显示脱敏线路摘要 |

### 实施项

- [x] 使用新增 nullable 表/字段，不覆盖注册 device ID。
- [x] identity 创建使用账号行锁 + 数据库唯一约束，避免并发生成两套画像。
- [x] 原始上下文总开关默认关闭。
- [x] 已明确本地私有表、操作者/用途/范围审计、保留天数和分批清理边界；未引入没有密钥治理方案的伪加密，未开放 HTTP 原始值读取，因此 raw context 默认关闭，只允许本地显式调试开启。
- [x] 设备 ID、session ID 和完整代理只通过显式白名单进入私有表，未知字段默认丢弃；不进入任务事件/普通账号 API/导出。
- [x] 日志 redaction 测试覆盖设备 ID、session ID、Cookie、Token 和代理密码；并移除既有普通日志中的原始设备/session/Token 前缀。
- [x] 删除上下文诊断数据不影响账号、Token、密码、TOTP 和任务历史；清理按 500 行上限分批执行，仅删除已过期私有 context。
- [x] Protocol v2 刷新、`protocol_current` 普通查活、Roxy 普通查活和套餐查询均支持可选 context recorder；关闭 raw context 时不创建记录器、不改变原请求参数。
- [x] Roxy 只记录白名单 Profile/会话端点/代理上下文，并在临时 Profile 清理后收口；不打开登录页、不读密码/邮箱/OTP。

### 退出条件

- [x] 相同账号/驱动设备层稳定，不同账号隔离。
- [x] 每个 run 的 session/trace 都不同。
- [x] 关闭原始上下文后业务功能完全正常。
- [x] 普通账号 API 不会返回原始敏感值；安全指纹摘要只保留允许的浏览器/路由观察字段。

## 12. 阶段 9：长期双实现维护

- [x] 浏览器、现有协议和 `protocol_v2` 都有独立 characterization/contract tests；`protocol_v2` 的普通查活“不支持”也有拒绝测试。
- [x] 上游后续更新只做差异审查和最小移植，不整体同步。
- [x] 每个任务持续记录 configured/effective driver 和安全结果摘要。
- [x] 浏览器 fallback 保留能力检测、容量错误和独立完整 run。
- [x] 本轮不安排删除旧实现；未来删除必须另立设计、迁移和用户确认。

## 13. 每阶段统一代码与提交规范

- [x] 一个阶段一个独立分支或一组内聚提交，不混入无关重构。
- [x] adapter 只适配契约，不复制稳定状态机。
- [x] router 不做网络请求；service 不直接拼 WebUI 响应；storage 不承载业务状态机。
- [x] 所有远端步骤有超时、次数上限、幂等边界和 `request_unknown` 处理。
- [x] 新枚举/字段向后兼容；数据库迁移只增量，不做破坏性重命名/删除。
- [x] 测试覆盖成功、明确失败、网络失败、超时、未知响应和中断恢复。
- [x] 提交前运行相关单测、Ruff、`git diff --check` 和敏感信息扫描。
- [x] 不提交 `.env`、账号、Token、密码、OTP、代理凭据、日志、`run/`、`.venv/` 或真实诊断材料。
- [x] 每阶段交付说明包含改动边界、开关、回退、验证证据和已知限制。

## 14. 当前下一步

本轮已完成刷新 AT 专用 Protocol v2 的密码/MFA 适配、稳定 Protocol identity、受限 run context、安全指纹摘要、日志/读取审计、邮箱来源恢复，以及普通查活三条已存在路径的可选 context 接入；没有把认证 Protocol v2 冒充成普通查活，也没有改变默认配置。后续运行只需按以下已完成的开关说明操作，不再修改代码：

1. [x] 保持现有系统：`ACCOUNT_LIVE_CHECK_DRIVER=protocol_current`、`ACCOUNT_LIVE_CHECK_BROWSER_ENABLED=False`、`ACCOUNT_TOKEN_REFRESH_DRIVER=legacy`、`ACCOUNT_AUTH_V2_ENABLED=False`。
2. [x] 显式试用 Roxy 普通查活：先将 `ACCOUNT_AUTH_RAW_CONTEXT_ENABLED` 保持关闭，再设置 `ACCOUNT_LIVE_CHECK_BROWSER_ENABLED=True` 和 `ACCOUNT_LIVE_CHECK_DRIVER=browser_roxy`；失败只收口为浏览器查活失败，不会登录、发 OTP 或刷新 AT。
3. [x] 显式试用 Protocol v2 刷新 AT：设置 `ACCOUNT_TOKEN_REFRESH_DRIVER=protocol_v2` 与 `ACCOUNT_AUTH_V2_ENABLED=True`；账号没有密码时自动沿用旧邮箱认证，有密码时按密码→TOTP/邮箱 challenge 处理。
4. [x] 密码错误后的邮箱兜底仍默认关闭；只有使用可牺牲测试账号且确认接收链路正常时，才设置 `ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=True`，最多新开一次邮箱会话，不重试错误密码。
5. [x] 阶段 3 已关闭为不适用：上游没有独立普通查活 `protocol_v2` 接口，不能配置到 `ACCOUNT_LIVE_CHECK_DRIVER`。
6. [x] 稳定设备画像、raw context、任务结果摘要和老实现均保留；恢复旧行为只需切回上述默认值，不需要数据回滚。
