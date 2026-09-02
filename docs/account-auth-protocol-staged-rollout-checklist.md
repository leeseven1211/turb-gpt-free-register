# 账号认证协议能力分阶段实施清单

> 本文是本次改造唯一的实施顺序和放行依据。两份完整设计文档只作为技术背景；如果表述冲突，以本清单为准。

- 基线：`main@d038f2a`
- 当前状态：阶段 1 已落地；阶段 2 已完成代码接入并完成部分真实样本验证，默认仍关闭；本轮另完成阶段 5/6 的“刷新 AT 专用 Protocol v2”适配器和真实密码+TOTP 验证，默认仍关闭；错误密码与邮箱兜底的真实失败边界已补齐，邮箱兜底尚未放行；阶段 8 已完成稳定 Protocol identity、Protocol v2 run context、安全指纹摘要和过期上下文清理调度的第一小步，原始上下文仍默认关闭，Roxy/普通查活接入和访问审计待后续
- 总原则：现有能力先冻结，新能力只做平行增量；每一阶段独立验证、独立放行、独立回退

### 本轮执行记录（2026-09-02）

- 实施分支：`codex/staged-live-check-driver`；主工作区 `main` 未修改。
- 已创建独立本地 PostgreSQL 数据库 `turb_live_check_test`，项目表结构已初始化；未连接生产库 `turb_console`。
- 阶段 1：`protocol_current` 默认路径、驱动冻结、任务事件/结果摘要记录和 WebUI 配置已完成。
- 阶段 2：`browser_roxy` 已接入，但 `ACCOUNT_LIVE_CHECK_BROWSER_ENABLED` 默认仍为 `False`。
- 真实样本：有效 AT 8 次均 HTTP 200；不可用 AT 3 次均 HTTP 401；不可用本地代理 2 次均归类为 `browser_navigation` 且可重试；每次临时 Profile 登记数均回到 0。
- 另有 4 次 Roxy 创建/浏览器层瞬时失败，分别落在 Profile/浏览器执行/页面导航错误分类，说明本机 Roxy 服务稳定性门禁尚未通过；不据此放开浏览器默认路径。
- 独立库端到端任务已验证：有效 AT 查活任务成功完成并写回 `live`；失效 AT 任务完成为 `failed`，结果摘要记录 HTTP 401 和 `error_category=auth`；两类任务均记录 `browser_roxy`。
- 上游核对未发现独立的 `protocol_v2` 普通 AT probe；因此没有把密码/MFA 认证链冒充成普通查活，阶段 3（新协议查活）仍未放行。
- 本轮新增刷新 AT 专用 `protocol_v2`：密码直达 callback、密码+TOTP MFA、邮箱 challenge、密码错误分类、未知响应分类和可选一次邮箱兜底均有独立状态机/单测；默认配置仍为 `legacy`，普通查活不触达。
- 真实测试：在一个已有密码、TOTP 和 AT 的本地测试账号上执行一次真实 Protocol v2，结果为 `password_mfa_totp`、`authenticated_session`、`live`；未启用邮箱兜底，未写回数据库。
- 真实错误密码测试：同一测试账号返回 `HTTP 401`，响应结构化错误码为 `invalid_username_or_password`；已分类为 `password_rejected` / `auth`，不会进入 Roxy、不会自动重试密码、默认不会发邮箱 OTP。
- 真实邮箱兜底测试：仅进程内打开邮箱兜底，使用新 session 发起一次验证码请求并等待 45 秒；转发邮箱 IMAP 登录和 `INBOX` 打开正常，但未收到该别名的新 OpenAI OTP，最终为 `password_rejected_email_fallback_failed` / `email`。因此邮箱兜底仍未判定成功，也没有继续重发。
- 本轮顺手为 `forward_imap` 增加 `ICLOUD_HME_REQUEST_TIMEOUT` socket 超时，避免收件链路卡死；对应单测已补齐。
- 上一轮隔离 schema 全量回归为 `673 passed, 24 subtests passed`；加入稳定 identity 后为 `682 passed, 24 subtests passed`；加入受限 raw context 存储边界后为 `686 passed, 24 subtests passed`；本阶段安全指纹摘要定向验证为 `48 passed`，协议专项为 `19 passed`，当前全量回归为 `690 passed, 24 subtests passed`。另修复一个独立的 `registration_debug` 终端上下文覆盖问题，该修复只在数据库缺少新 evidence 时保留会话内已有 evidence，不改变注册行为。
- 阶段 8 第一小步：新增私有 `account_protocol_identities` 表、账号行锁保护的幂等创建、版本化 HMAC 派生和 `ACCOUNT_AUTH_PROFILE_MODE` 配置；只有 `account_stable + protocol_v2` 刷新才会懒创建并把同一身份传给每个 Protocol 会话。`current` 默认完全不建表行、不改变现有随机画像；稳定画像不保存 geo/locale/timezone、session/trace、Sentinel 或 Roxy 标识。Protocol v2 成功认证另写入白名单安全指纹摘要，账号行和任务结果不接收原始设备/session/代理凭据。
- 稳定画像单测验证同一 key 的 device/profile 稳定、不同会话的 session/sentinel ID 仍变化、并发 ensure 只生成一行；受限 run context 已完成白名单、保留期、编号锁和收口测试，但尚未接入 Roxy 或普通查活。

相关背景：

- [账号认证、查活与指纹总体设计](account-auth-liveness-fingerprint-design.md)
- [账号认证、查活与指纹详细实施设计](account-auth-liveness-fingerprint-implementation-design.md)

## 1. 先统一三个事实

### 1.1 当前真实路径

| 功能 | 当前真实路径 | 本次处理 |
| --- | --- | --- |
| 注册、注册密码、注册恢复 | Roxy/Selenium 浏览器 | 保持不动，继续作为稳定主路径 |
| 普通查活 | `check_account_plan()` + `BrowserSession` 的协议型旧 AT probe | 保持默认行为，不登录、不发 OTP |
| 刷新 AT | 当前协议邮箱 OTP 登录；失败后可进入 Roxy fallback | 与普通查活继续严格分开 |
| Codex 密码/TOTP 登录 | 当前 Roxy 浏览器状态机 | 保持不动 |
| 2FA 设置 | 当前协议和 Roxy 已有能力 | 保持不动，新接口单独灰度 |
| GitHub 新协议功能 | 尚未接入生产业务路由 | 逐功能移植，不整体合并提交 |

这里所说的 `BrowserSession` 是协议请求使用的浏览器指纹会话，不等于 Roxy 真浏览器。当前没有一条可直接复用的“Roxy 普通查活”完整路径；如果要让普通查活可选 Roxy，必须新增一个**只使用旧 AT 的浏览器 probe**，不能拿现有 Roxy 登录刷新流程冒充。

### 1.2 用户目标

- 注册、密码、TOTP、2FA 等认证主路径仍以现有浏览器能力为基础。
- 普通查活允许用户明确选择现有协议、Roxy 浏览器 probe 或新协议 v2。
- GitHub 新协议能力用于提速和补充，不自动取代当前稳定能力。
- 浏览器能力永久保留；Protocol 被选择时，只有符合安全条件才允许启动一次完整浏览器 fallback。

### 1.3 不可突破的红线

- [ ] 不整体 cherry-pick/merge 上游认证提交。
- [ ] 不在现有稳定函数内部悄悄替换成新协议。
- [ ] 不删除现有浏览器、现有协议、邮箱 OTP、TOTP 或 2FA 入口。
- [ ] 普通查活只验证已有 AT，绝不登录、发 OTP、提交密码/TOTP 或获取新 AT。
- [ ] 普通查活不做自动跨驱动 fallback，避免掩盖用户所选驱动的真实结果。
- [ ] 同一次认证 session 不混用 Protocol Cookie/challenge 与 Roxy 中间状态。
- [ ] 不改写现有注册 `device_id`、密码、TOTP secret、AT 或最近成功检查点。
- [ ] 不在日志、任务事件、普通 API 或账号列表暴露 Token、密码、OTP、Cookie、完整代理凭据。
- [ ] 不在当前生产工作区直接试验存储层；使用独立 worktree 和独立测试数据库。
- [ ] 未通过本阶段退出条件，不开始下一阶段。

## 2. 分阶段总览

| 阶段 | 内容 | 对现有默认行为的影响 | 当前状态 |
| --- | --- | --- | --- |
| 0 | 冻结基线与隔离环境 | 无 | 部分完成；独立库已建，完整 characterization/专用账号仍可补充 |
| 1 | 查活路由壳，先只接现有协议 | 无 | 已完成 |
| 2 | 新增 Roxy 旧 AT 浏览器 probe | 默认不启用 | 代码完成；真实放行门禁未完成 |
| 3 | 接入 GitHub `protocol_v2` 查活 | 默认不启用 | 未发现独立上游接口，保持待执行 |
| 4 | 查活小流量放行与用户配置 | 只影响显式选择的任务 | 待执行 |
| 5 | 新协议密码登录 | 浏览器仍默认 | 已完成“刷新 AT 专用”子集；真实错误密码边界已验证；通用密码登录仍待执行 |
| 6 | TOTP 与邮箱 OTP challenge | 浏览器仍默认 | 密码+TOTP 真实成功；邮箱兜底真实收件未达，暂不放行 |
| 7 | 新协议 2FA 设置 | 浏览器仍默认 | 待执行 |
| 8 | 稳定设备画像与受限原始上下文 | 默认保持 current；raw context 默认关闭 | 部分完成：稳定 identity、Protocol v2 session context、安全指纹摘要和每日过期清理已接入；Roxy/普通查活 context 和访问审计待后续 |
| 9 | 长期双实现维护 | 不删除旧实现 | 待执行 |

## 3. 阶段 0：冻结基线与隔离环境

目标：先证明“什么都不改时系统能正常工作”，并准备不会碰生产数据的实现环境。

### 实施项

- [ ] 记录 `main` 基线 commit、分支、工作区状态和当前生效配置摘要。
- [ ] 创建 `codex/` 前缀的独立 worktree/分支。
- [ ] 创建独立 PostgreSQL 测试库；不得连接生产 `turb_console`。
- [ ] 准备一个可牺牲测试账号和独立邮箱，不批量使用现有账号。
- [ ] 冻结现有普通查活、刷新 AT、Roxy 登录、密码、TOTP、2FA 的 characterization tests。
- [ ] 对以下现状各保存一份脱敏任务事件和网络请求序列：
  - [ ] 有效 AT 普通查活成功。
  - [ ] 失效 AT 普通查活返回失败且不登录。
  - [ ] 刷新 AT 的当前协议邮箱 OTP 成功。
  - [ ] 当前协议失败后 Roxy fallback 成功或明确失败。
  - [ ] 代理不可用、超时和 401 的分类结果。
- [ ] 运行相关测试、Ruff 和 whitespace 检查，保存基线结果。

### 退出条件

- [ ] 独立环境不会读写生产账号和任务表。
- [ ] 现有网络动作、持久化字段和任务状态已有可比较基线。
- [ ] 现有测试全部通过；失败项必须先解释，不带病进入阶段 1。

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
| `protocol_v2` | 阶段 3 | 移植的 GitHub 新协议查活 |

配置缺失时必须解析为 `protocol_current`，因为这才与当前线上普通查活一致。等 `browser_roxy` 验证通过后，用户可以显式切到浏览器；不能在升级时悄悄改变默认网络路径。

### 实施项

- [ ] 新增窄职责 live-check router，只做配置解析和 adapter 选择。
- [ ] `protocol_current` adapter 原样调用当前入口，不复制逻辑。
- [ ] 配置、WebUI 编辑白名单、`.env.example`、README 和配置测试同步增加。
- [ ] 任务入队时冻结 `requested_driver` 和 `effective_driver`。
- [ ] 任务事件和结果摘要记录驱动名称，不记录敏感配置。
- [ ] 提供单任务 driver override，仅供管理员灰度；全局默认不随单次选择改变。
- [ ] 未开放的值在远端请求前明确拒绝，不能静默退回其他驱动。

### 退出条件

- [ ] 不配置新键时，请求序列、结果和当前版本完全一致。
- [ ] 显式选择 `protocol_current` 时，与未加 router 的冻结基线一致。
- [ ] 非法/未开放 driver 不领代理、不创建 Roxy Profile、不改账号状态。
- [ ] 关闭新路由后可直接回到原入口。

### 回退

- 配置恢复 `protocol_current`。
- router 保留但只允许 current adapter；无需回滚数据库。

## 5. 阶段 2：新增 Roxy 普通查活 probe

目标：让普通查活真正具备浏览器选项，同时保持“只验证旧 AT”。

### 实施项

- [ ] 新增独立的 `browser_roxy` adapter，不调用现有登录刷新函数。
- [ ] 每次任务创建临时 Roxy Profile，使用账号代理和浏览器环境。
- [ ] 只在受控浏览器 context 中携带旧 AT 请求查活接口。
- [ ] AT 只能存在于本次内存请求头；不得写入持久 Cookie、localStorage 或 Profile 数据。
- [ ] 禁止打开登录/authorize 页面，禁止读取邮箱、密码和 TOTP。
- [ ] 任务结束幂等关闭并软删除临时 Profile。
- [ ] Profile 创建失败、页面/CDP 未识别、超时和 HTTP 结果分别分类。
- [ ] 加入网络契约测试，断言没有 signin、authorize、email-verification、OTP 请求。

### 灰度样本

- [ ] 有效 AT：至少 10 次重复 probe，确认结果稳定且没有登录动作。
- [ ] 明确 401/失效 AT：至少 3 次，必须直接返回失效。
- [ ] 代理失败、Roxy 容量不足、CDP 超时：每类至少 2 次。
- [ ] 与 `protocol_current` 对同一测试账号的结果做成对比较。

### 退出条件

- [ ] 浏览器 probe 零登录、零 OTP、零 Token 刷新。
- [ ] 成功/401/网络错误不会互相误判。
- [ ] 所有临时 Profile 均完成关闭和软删除。
- [ ] `protocol_current` 默认路径无回归。

### 回退

将 `ACCOUNT_LIVE_CHECK_DRIVER` 改回 `protocol_current`；`browser_roxy` adapter 保留但不可达。

## 6. 阶段 3：接入 GitHub `protocol_v2` 查活

目标：只移植新协议查活所需的最小能力，不引入密码、OTP 和 2FA 状态机。

### 实施项

- [ ] 根据已验证真实请求逐段移植，不复制上游整个任务/存储/UI 框架。
- [ ] 新建 `protocol_v2` adapter，与 `protocol_current` 物理分离。
- [ ] 复用现有 AT、账号代理租约、任务队列和 PostgreSQL 写回边界。
- [x] 第一版只保存安全指纹摘要；稳定设备画像使用新增 nullable 数据，不覆盖注册 device ID。
- [ ] 每个 run 使用新的 session/trace 标识，不能把稳定画像误做成长久 session。
- [ ] 对响应采用类型化结果：成功、401、账号不可用、风控、代理错误、超时、未知响应。
- [ ] 保存脱敏 fixture，禁止保存 Token、Cookie、邮箱 OTP 和完整代理。
- [ ] `protocol_v2` 失败直接返回本驱动结果；普通查活不自动改走浏览器。

### 灰度样本

- [ ] 使用阶段 2 的同一组有效、失效和网络异常样本。
- [ ] 对 `protocol_current`、`browser_roxy`、`protocol_v2` 做三路结果比较。
- [ ] 重复运行验证设备层稳定、session/trace 层每次变化。
- [ ] 验证 401 不被本地 JWT 到期时间或浏览器成功结果覆盖。

### 退出条件

- [ ] 三路对有效/失效账号的核心结论一致；差异都有明确证据和分类。
- [ ] 新协议没有登录、OTP、密码或 2FA 请求。
- [ ] 新画像数据可以停写，不影响账号查活。
- [ ] 切回 `protocol_current` 后不需要数据回滚。

### 回退

将 driver 改回 `protocol_current` 或已验证的 `browser_roxy`；禁用 `protocol_v2` 能力声明。

## 7. 阶段 4：普通查活小流量放行

目标：让用户可以自己配置，但不自动替用户改变生产默认。

### 放量顺序

- [ ] 单个测试账号通过单任务 override 运行。
- [ ] 5 个明确选定账号运行，不做批量刷新 AT。
- [ ] 连续观察任务成功率、401、代理错误、Roxy Profile 清理和任务投影。
- [ ] 用户在 WebUI 显式选择全局 driver 后才改变后续任务默认值。
- [ ] 页面同时显示 configured driver 与本次 effective driver。

### 用户最终可选

```text
ACCOUNT_LIVE_CHECK_DRIVER=protocol_current  # 保持现状
ACCOUNT_LIVE_CHECK_DRIVER=browser_roxy      # 浏览器旧 AT probe
ACCOUNT_LIVE_CHECK_DRIVER=protocol_v2       # GitHub 新协议 probe
```

如果希望普通查活以浏览器为主，阶段 2 通过后显式配置 `browser_roxy`。协议仍可随时手动切回。系统不得根据成功率自动修改该配置。

### 停止条件

出现以下任一情况立即停止放量并切回 `protocol_current`：

- [ ] 普通查活触发登录或 OTP。
- [ ] 旧 AT、密码、TOTP、注册 device ID 被覆盖。
- [ ] 同一账号不同 driver 的核心结论无法解释。
- [ ] 临时 Roxy Profile 泄漏或任务无法收口。
- [ ] Token/代理凭据出现在日志或普通 API。

## 8. 阶段 5：新协议密码登录

目标：在普通查活稳定后，再单独接入密码验证；现有浏览器登录继续默认。

### 配置

到本阶段才新增：

```text
ACCOUNT_PASSWORD_LOGIN_DRIVER=browser_current|protocol_v2
```

默认必须是 `browser_current`。密码登录和密码创建/补设是两件事，本阶段不新增协议密码设置。

### 实施项

- [ ] 新增独立密码登录 service/API，不替换现有 Roxy 入口。
- [ ] 密码从现有受控事实来源读取，不复制到画像或任务表。
- [ ] 识别正确密码、明确错误、MFA challenge、邮箱验证、未知页面和请求结果未知。
- [ ] 浏览器页面没识别到时只保存脱敏证据并停止，不盲点按钮。
- [ ] 密码提交 `request_unknown` 时禁止自动切浏览器重复提交。
- [ ] 明确密码错误可在单独配置允许时进入一次邮箱 passwordless fallback，但必须记录密码状态为 rejected。
- [ ] fallback 成功不得显示成“密码登录成功”。

### 必测场景

- [ ] 正确密码，无 MFA。
- [ ] 正确密码，进入 TOTP。
- [ ] 正确密码，进入邮箱 OTP。
- [ ] 明确错误密码。
- [ ] 本地没有密码。
- [ ] 密码页未识别、控件缺失、提交超时和返回未知。
- [ ] 页面要求其他验证方法、重新发送或返回上一步。

### 退出条件

- [ ] 默认浏览器路径网络序列和结果无变化。
- [ ] 新协议只对显式测试账号可达。
- [ ] 错误密码、未知结果和远端页面变化不会触发循环或重复提交。

## 9. 阶段 6：TOTP 与邮箱 OTP challenge

目标：补全密码登录后的 challenge，不把所有 fallback 塞进一个状态机分支。

### 配置

能力完成后再逐项新增；没有能力时不显示对应选项：

```text
ACCOUNT_TOTP_LOGIN_DRIVER=browser_current|protocol_v2
ACCOUNT_EMAIL_OTP_DRIVER=browser_current|protocol_current|protocol_v2
ACCOUNT_PASSWORD_EMAIL_FALLBACK_ENABLED=False|True
```

### 实施项

- [ ] 页面/协议返回先分类，再决定 TOTP、邮箱 OTP 或停止。
- [ ] TOTP 只在远端明确要求且本地存在 secret 时生成。
- [ ] TOTP 每个时间窗限制提交次数，防止快速重复。
- [ ] 邮箱 OTP 流程明确处理“其他方式”“发送验证码”“重新发送”“验证码输入”“继续”按钮。
- [ ] OTP 读取设置严格的接收时间边界，拒绝历史验证码。
- [ ] 缺少按钮或页面未知时保存脱敏快照，返回 `attention_required`。
- [ ] 密码明确错误后的邮箱 fallback 与正常邮箱 challenge 分开记录。
- [ ] 任何 challenge 完成后都重新读取远端状态，不能凭点击动作推断成功。

### 退出条件

- [ ] 密码、TOTP、邮箱 OTP 的状态和结果来源可区分。
- [ ] 不会因为识别不到页面而无限等待、盲点或重复发验证码。
- [ ] 任一步切回浏览器都启动新的完整 run，不注入 Protocol 中间状态。

## 10. 阶段 7：新协议 2FA 设置

目标：最后接入会改变账号安全状态的能力。

### 配置

```text
ACCOUNT_2FA_SETUP_DRIVER=browser_current|protocol_current|protocol_v2
```

默认 `browser_current`；新协议未通过 enroll/activate 真实验证前不得出现在 WebUI 可选项中。

### 实施项

- [ ] enroll、secret 检查点、activate、远端确认分成独立步骤。
- [ ] secret 拿到后立即写入受控事实来源，不写任务日志。
- [ ] 只有远端确认 activate 成功后才标记 2FA enabled。
- [ ] 中断重试从检查点恢复，不能重复创建并覆盖已有 secret。
- [ ] 测试重复设置、已有 2FA、错误 TOTP、activate 超时和远端结果未知。
- [ ] 协议失败不破坏当前浏览器重试能力。

### 退出条件

- [ ] 中断、超时、重复执行都不会让本地与远端 2FA 状态被错误标记为一致。
- [ ] 当前浏览器和现有协议入口仍可单独使用。

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
- [ ] 明确访问控制、加密/密钥来源、保留期限和清理机制后才能开启原始值保存；当前只实现保留天数配置和显式关闭，尚未开放原始值读取。
- [x] 设备 ID、session ID 和完整代理只通过显式白名单进入私有表，未知字段默认丢弃；不进入任务事件/普通账号 API/导出。
- [ ] 日志 redaction 测试覆盖设备 ID、session ID、Cookie、Token 和代理密码。
- [x] 删除上下文诊断数据不影响账号、Token、密码、TOTP 和任务历史；清理按 500 行上限分批执行，仅删除已过期私有 context。

### 退出条件

- [ ] 相同账号/驱动设备层稳定，不同账号隔离。
- [ ] 每个 run 的 session/trace 都不同。
- [ ] 关闭原始上下文后业务功能完全正常。
- [x] 普通账号 API 不会返回原始敏感值；安全指纹摘要只保留允许的浏览器/路由观察字段。

## 12. 阶段 9：长期双实现维护

- [ ] 浏览器、现有协议和 `protocol_v2` 都有独立 characterization/contract tests。
- [ ] 上游后续更新只做差异审查和最小移植，不整体同步。
- [ ] 每个任务持续记录 configured/effective driver 和安全结果摘要。
- [ ] 浏览器 fallback 保留能力检测、容量错误和独立完整 run。
- [ ] 本轮不安排删除旧实现；未来删除必须另立设计、迁移和用户确认。

## 13. 每阶段统一代码与提交规范

- [ ] 一个阶段一个独立分支或一组内聚提交，不混入无关重构。
- [ ] adapter 只适配契约，不复制稳定状态机。
- [ ] router 不做网络请求；service 不直接拼 WebUI 响应；storage 不承载业务状态机。
- [ ] 所有远端步骤有超时、次数上限、幂等边界和 `request_unknown` 处理。
- [ ] 新枚举/字段向后兼容；数据库迁移只增量，不做破坏性重命名/删除。
- [ ] 测试至少覆盖成功、明确失败、网络失败、超时、未知响应和中断恢复。
- [ ] 提交前运行相关单测、Ruff、`git diff --check` 和敏感信息扫描。
- [ ] 不提交 `.env`、账号、Token、密码、OTP、代理凭据、日志、`run/`、`.venv/` 或真实诊断材料。
- [ ] 每阶段交付说明必须包含：改了什么、没改什么、怎么开启、怎么关闭、验证证据、已知限制。

## 14. 当前下一步

本轮已完成刷新 AT 专用 Protocol v2 的密码/MFA 适配、稳定 Protocol identity、受限 Protocol v2 run context、安全指纹摘要和隔离端到端验证，但没有把它接到普通查活，也没有改变默认配置。下一步按以下顺序推进：

1. [ ] 保持 `ACCOUNT_TOKEN_REFRESH_DRIVER=legacy`，先由用户确认是否需要在本地测试环境显式开启 v2。
2. [ ] 在不启用邮箱兜底的前提下，补充 1-2 个密码+TOTP 测试账号，比较成功率、耗时和失败分类。
3. [ ] 如需验证密码错误后的邮箱兜底，单独开启 `ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=True`，使用可牺牲测试账号，逐项确认发送、取码、MFA 和任务收口。
4. [ ] 阶段 3 只有在发现并验证独立的 GitHub 普通查活协议接口后才继续；当前上游没有该独立实现，不将认证链冒充查活。
5. [x] 稳定设备画像第一小步已完成：默认 `current` 不生效，显式 `account_stable + protocol_v2` 才懒创建并复用设备层；注册 `device_id`、普通查活、legacy 刷新和 Roxy fallback 未改。
6. [x] 受限 run context 的 operation run 关联、原始标识/代理凭据白名单、默认关闭、保留字段和收口已完成；当前只接 Protocol v2 刷新，Roxy/普通查活仍不写原始值。
7. [x] Protocol v2 成功认证的安全指纹摘要已按白名单生成，并写入账号最近认证摘要和任务结果；不包含 device/session ID、Cookie、Token、密码、邮箱或完整代理。
8. [x] 已增加 raw context 启用时的启动清理和每日数据库调度；仍需补访问审计、日志 redaction fixture，再考虑开放 raw context 到更多驱动。
9. [ ] 通用密码登录、浏览器 fallback 逐项按门禁推进，不与本轮 v2 刷新适配混合放量。
