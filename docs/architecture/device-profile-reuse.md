# 设备画像复用方案（讨论稿，2026-11-26）

> 状态：本文的**注册成功后原样存储方案尚未开发**，第一部分已定稿，后续方案待讨论。
> 已有实现另外保存刷新 AT、补密码和改密使用的设备画像，并供账号动作复用；
> 这不代表本文提出的注册画像存储、三驱动完整回放或回填方案已经完成。
> 原则：先存后用；本文第一部分只记录，不改注册链路行为。

## 0. 三步走

1. **第一部分：原样存储**（本文档重点）——注册成功后把驱动实际用的画像原样存库，不做归一、不推导
2. **第二部分：回放**——刷新/改密等操作复用画像（待讨论）
3. **第三步：回填 + 观测 + 对照实验**（待讨论）

目标：让同一账号后续操作沿用上一次真实设备，避免"换设备 + 敏感操作"触发
OpenAI 的 24 小时 `sensitive_action_cooldown`。

## 1. 实测现状（2026-11-26）

| 注册驱动 | 账号数 | 画像来源 | 真实 UA 系统 |
|---|---|---|---|
| `sentinel_rs` | 5,261 | Python 占位会话（假） | macOS（实际注册走 Windows） |
| `protocol_oss_2` | 5,241 | 上游引擎（真） | Windows Chrome |
| 无/历史 | 14 | 无 | — |

- 抽样 800 条：`browser_type` 全部为 `chrome`；全库 0 条 Safari 画像
- 冷却证据：4 个"刷新 AT 后立刻改密"的账号 4/4 命中 24h 冷却；
  7 个"会话有效、同设备改密"的账号 7/7 成功 → 触发点是设备变化

## 2. 三种驱动的画像来源

### 2.1 浏览器（Roxy）
- 本地只有绑定：`extra_json.roxybrowser = {profile_id, retained, window_name, ...}`
- `/browser/list_v2` 可返回：`dirId`、`windowName`、`os`、`osVersion`
- UA / 屏幕 / WebGL 在 Roxy 客户端内部，接口不返回
- 复用语义：重新打开同一 `profile_id`

### 2.2 协议（`protocol_oss_2` 上游引擎）
- 生成：`generate_fingerprint(country_code, browser_family)`，40 个字段
  - `chrome` → Windows Chrome（UA 152，`impersonate=chrome146/145`，上游再覆写为 `chrome152`）
  - `safari` → `mac_safari` / `ios_safari`
- 传输：Python `wreq`，支持到 Chrome154 → 152 是真实能力
- 落库：注册生命周期把 `session.browser_profile`（74 字段）写进
  `registered_accounts.data.extra_json.browser_profile`
- 已知缺陷：见 §4（Windows/macOS 串值）

### 2.3 rust（`sentinel-rs`）
- 生成：`DeviceFingerprint::generate_for_country(seed=device_id, country)`，仅 Windows Chrome
- 传输：`wreq 0.16.1 + wreq-util 0.2.0`，最高 Chrome149
- 注册：**不回传**画像与 device_id（结果只有 email/password/AT/2FA/cookies）
- 刷新：已回传 `browser_profile`（`python_profile()`）
- 当前落库的注册画像是 Python 占位会话（macOS），不是真实设备

## 3. 第一部分：原样存储（定稿）

### 3.1 存什么

驱动返回什么就存什么，**原始 JSON 原样保存**：

| 驱动 | 存储内容 |
|---|---|
| protocol_oss_2 | `session.browser_profile` 全量 74 字段 |
| sentinel_rs | 内核回传的画像结构（原样；待内核支持回传） |
| roxy | `profile_id` + `list_v2` 返回字段 |

### 3.2 只加元数据（不改原数据）

- `driver`：`sentinel_rs` / `protocol_oss_2` / `roxy`
- `source`：`registration`（后续有 `refresh_at` / `password_reset` 等）
- `trust`：`trusted` / `placeholder`
- `device_id`：从原数据读取
- `family`、`os`：从 UA 读取，仅用于查询（不写回画像）

### 3.3 表结构

`account_device_profiles`（已建，需补列）：

| 列 | 说明 |
|---|---|
| `account_id` PK | 外键，级联删除 |
| `normalized_email` | 与当前邮箱强绑定，换绑即失效 |
| `encrypted_payload` | 加密的原始画像 JSON |
| `driver` | 新增 |
| `source` | 已有 |
| `trust` | 新增 |
| `device_id`、`family`、`os` | 新增，可检索 |
| `last_used_at`、`updated_at` | 观测 |
| `kernel_version` | 新增：产出该画像的内核版本（如 `wreq-0.13.0` / `wreq-0.16.1+util-0.2.0`） |
| `generator_version` | 新增：生成规则版本，规则变更时递增，用于区分“老画像”和“新画像” |
| `emulation` | 新增：TLS 档位名（如 `chrome152`），便于直接检索 |

### 3.4 写入点与侵入性

| 驱动 | 是否需要改注册链路 | 说明 |
|---|---|---|
| protocol_oss_2 | 否 | 画像已在 `session.browser_profile`，落库后多写一行 |
| roxy | 否 | 读绑定与 `list_v2`，多写一行 |
| sentinel_rs | **是（最小）** | 需内核在结果 JSON 里增加画像字段；只加输出，不改注册流程 |

> 约束：老板暂不希望改注册链路。因此第一部分可先落 **协议 + 浏览器**；
> rust 回传作为独立小改动，等批准后再做。

### 3.5 验收

1. 注册成功后设备行存在
2. 原始画像可解密、可完整还原（与源字段逐项相等）
3. `device_id` 与账号记录一致
4. 写失败只记日志，不影响注册结果

### 3.6 明确不做

- 不定义 canonical 字段
- 不推导、不补值、不修正脏值
- 不统一命名
- 不存 `react_*` 请求级 key（会话级随机，存了也不能用；如需排查可临时记录，不落长期表）

## 4. 已知缺陷：协议注册画像 Windows/macOS 串值（必修，独立立项）

### 4.1 证据（账号 10570）

```
user_agent          = Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/152
navigator_platform  = Win32
sec-ch-ua-platform  = "Windows"
browser_os          = macOS                    ← 矛盾
webgl_renderer      = ANGLE (Apple, ... Apple M2)  ← 矛盾
```

另：`sec_ch_ua_arch/bitness/model/platform_version/full_version_list` 全部为空字符串，
真值在 `ua_arch/ua_bitness/ua_model/ua_platform_version/ua_full_version_list` 里
（抽样 120 个协议账号，120 个都是这样）。

### 4.2 成因

1. 协议注册开始时 Python 先建本地会话，默认 macOS Chrome（`browser_os=macOS`、`webgl=Apple`）
2. 上游生成 Windows Chrome 指纹后执行 `session.browser_profile.update(fingerprint)`
3. 合并只覆盖上游存在的键：
   - 上游没有 `browser_os` → 保留 macOS
   - 上游没有 `webgl_*` → 保留 Apple
   - 上游的 `sec_ch_ua_arch` 等为空字符串 → 覆盖成空

### 4.3 影响

- `browser_os`：不发给 OpenAI，只是内部标签 → 不影响风控，但会误导排查与后续复用判断
- `webgl_renderer`：**会进入 sentinel token 的 JS 环境** → Windows UA 报 Apple GPU，
  属于真实的不一致
- `sec-ch-ua-*` 为空：若将来原样回放，会发出空 client hints，比不发更假

### 4.4 修复方案

- **A（先做，零链路风险）**：入库归一。写设备表时以 UA 判定 OS，重写
  `browser_os`、`webgl_*`，并用 `ua_*` 回填空的 `sec_ch_ua_*`。只影响存储副本，
  不改注册请求、不改 `session.browser_profile`
- **B（后做，需验证）**：修上游生成器，给 chrome 画像补 WebGL，并让合并覆盖
  `browser_os` 与空 client hints。会改变未来注册实际发送的 sentinel 内容，
  必须单独验证注册成功率

> 说明：A 修的是"记录准确"，B 修的是"请求本身"。当前 5,241 个历史号带着该组合
> 注册成功，说明服务端暂未因此拦截；B 不应与第一部分混做。

## 5. 第二步：指纹重放（定稿）

### 5.1 定义与范围

- 重放 = **用注册内核 + 注册画像，重建一个会话**；不执行任何业务操作、不发业务请求
- 目标等级 **L2**：UA、client hints、OS、屏幕/硬件、语言/时区、TLS 档位全部与上次一致
- 只服务**改密**（刷新 AT、注册不在此范围）
- 每个账号的 `replay_kernel` 由注册驱动决定并固定，不动态切换

### 5.2 内核选择规则（定稿）

```
内核 ∈ 能运行该画像的内核集合        # 能力筛选（保护）
且 内核 == 该账号的注册驱动          # 最终决定（唯一）
否则失败，不降级、不换内核
```

- `protocol_oss_2` → 协议内核（Python `wreq`）
- `sentinel_rs` → rust 内核
- 理由：只有产出画像的内核才能发出同一套 TLS 指纹；UA/CH 可照抄，TLS 栈实现不能
- 例外：将来某内核能逐字节等价复现另一内核的 TLS 栈，才允许交叉

### 5.3 重放的五层

| 层 | 注入内容 | 来源 |
|---|---|---|
| TLS | `impersonate`（如 `chrome152`）→ wreq emulation | 画像 |
| HTTP 默认头 | `User-Agent`、`accept-language`、全套 `sec-ch-ua*` | 画像 |
| Cookie | `oai-did=device_id` + 未过期历史 Cookie | 画像 + 会话缓存 |
| sentinel 环境 | 屏幕/dpr/cores/memory/WebGL/时区/语言/platform | 画像 |
| 语言/时区 | `navigator_language(s)`、`accept_language`、`timezone_iana` | 画像（与头同源） |

### 5.4 重放前的画像整理（内存内，不回写）

存储保持原样，重放时整理成自洽副本：

1. 以 UA 判定 OS，重写 `browser_os`、`navigator_platform`、`sec_ch_ua_platform`、`user_agent_data_platform`
2. `sec_ch_ua_arch/bitness/model/platform_version/full_version_list` 为空时用 `ua_*` 回填
3. `screen_width/height` 缺失时从 `screen`（`"1366x768"`）解析
4. `viewport_width/height` 缺失时从 `viewport` 对象取
5. `navigator_language` ← `lang`，`accept_language` ← `lang_full`
6. `webgl` 与 OS 不符时按 OS 修正（Windows → D3D11 ANGLE）
7. **版本号一律不动**

### 5.5 会话接口（第三步使用）

```
session = open_replayed_session(account, proxy, cookies=None)
session.get / post / cookies / headers
session.browser_profile   # 供 sentinel 使用
session.device_id
```

### 5.6 probe 验收（不联网）

1. 用画像建会话
2. 读取实际配置：TLS 档位、UA、全部 `sec-ch-ua*`、语言、时区
3. 与存储画像逐项对比
4. 输出差异清单；**差异必须为 0**

### 5.7 失败策略

- 缺关键字段（`user_agent` / `impersonate` / `device_id`）→ 失败
- 档位在内核中不存在 → 失败
- 内核版本与画像记录不一致 → `kernel_version_mismatch`，默认不重放
- 一律不静默降级（降级比失败更危险：看着像复用，其实换了设备）

### 5.8 版本与指纹演进

1. 每条画像记录 `kernel_version`、`generator_version`、`emulation`
2. 重放要求三个一致：内核一致、内核版本一致、参数一致
3. 内核升级：先 probe 对比新旧版本；TLS 行为变化则旧账号默认不重放，需要时走一次性迁移
4. 生成规则优化：新注册用新规则（`generator_version` +1）；老账号保留原画像，不用新规则重算
5. 可选：离线计算档位 JA3/JA4 摘要入库，升级后直接比对

### 5.9 组件位置与测试

```
core/accounts/device_replay/
  normalize.py   画像整理（5.4 的 7 条）
  session.py     内核分派 + 五层注入
  probe.py       差异对比
  errors.py      错误分类
```

- 单测：整理规则、档位映射、不支持时报错
- probe：3 个真实画像差异为 0
- 负例：非法 `impersonate` 必须报错

### 5.10 已知限制

- rust 注册画像未回传，当前无法重放 rust 号（需注册链路上报，暂不允许）
- rust 注册种子为环境/随机，不可还原；只能从首次刷新（seed=device_id）起固定
- Safari 家族：协议支持，rust 不支持；当前库内 0 条 Safari 画像
- curl_cffi（146）不参与本方案，仅作历史参考

## 6. 第三步：执行操作（改密流程，详设）

> 前提：第二步已产出"已重放"的会话；本节只讲拿到会话之后做什么。

### 6.1 前置条件

- 会话已就绪（内核 = 注册内核，画像已注入）
- 新密码候选已生成并写入 `prepared` checkpoint
- 邮箱可收码（generic_api 取码通道可用）
- 账号未被标记冷却（`password_reset_cooldown` 未命中）

### 6.2 流程总览：会话优先（定稿方向）

改为"先确保有有效会话，再走同一套改密流程"，不再区分"未登录/登录"两套：

```
① 检查会话（同内核 + 同画像）
   GET /api/auth/session
   ├─ 有效（200 且有 accessToken）→ 直接进入 ②
   └─ 过期/无效 → 登录（同一会话、同一画像）→ 顺带刷新 AT → 进入 ②
② 走改密流程（与"会话未过期"完全相同的步骤）
   GET /reset-password → send-otp → 取码 → validate → continue_url → sentinel → reset
③ 用新密码在同会话重新登录验证 → confirmed
```

要点：

- **登录不是换设备**：同一内核 + 同一画像下的重新登录，对服务端是"同一台设备再次登录"
- 之前 4/4 冷却的根因是"rust 刷新（Windows）+ Python 改密（macOS）"跨内核混用，不是登录本身
- **登录即刷新 AT**：登录成功后顺手更新 access_token，刷新 AT 的流程自然被复用
- 登录失败（密码不可用/被拒）时才回退到"未登录忘记密码"（U）作为兜底
- 改密流程只有一套，不再维护 U/L 两条

### 6.3 请求序列（U 流程）

| 步骤 | 请求 | 关键内容 | 期望 | 失败处理 |
|---|---|---|---|---|
| 1 | `GET /reset-password` | 导航头、referer=log-in | 200，落 Cookie | 网络/CF 重试；403 记录 |
| 2 | `POST /api/accounts/password/send-otp` | body 待验证（`{}` 或 `{"username": email}`） | 200 | 429 退避；403 冷却终止 |
| 3 | 等验证码 | 邮箱取码 | 6 位码 | 超时按配置重发 |
| 4 | `POST /api/accounts/email-otp/validate` | `{"code": "..."}` | 200 + `continue_url` | 400/401 码错误；403 冷却终止 |
| 5 | `GET continue_url` | 导航头 | 200 | 失败重试一次 |
| 6 | `POST sentinel/req` | flow=`password_reset` | token | 失败重试 |
| 7 | `POST /api/accounts/password/reset` | `{"password": "..."}` + sentinel 头 | 200 | 403/400 分类；未知 → 对账 |

### 6.4 OTP 策略

- 发码后记录 `after_ts`，只接受之后到达的邮件
- 等待窗口 = `OTP_MAX_WAIT`（统一配置），超时按 `OTP_RESEND_COUNT` 重发
- 验码错误最多重试 2 次（避免把码试废），超过则终止
- 冷却（`sensitive_action_cooldown`）→ 不重试，记录 `cooldownAction` 与解除时间

### 6.5 密码与 checkpoint

```
prepared → submitted → confirmed
```

- `prepared`：候选已生成并落库（改密前）
- `submitted`：`/password/reset` 返回 200
- `confirmed`：用新密码在同会话重新登录验证成功
- 任何失败都停在 `prepared`，不确认；重试沿用或重新生成候选

### 6.6 错误分类

| 错误码 | 含义 | 可重试 |
|---|---|---|
| `password_reset_cooldown` | 24h 敏感操作冷却 | 否（记录解除时间） |
| `password_reset_rate_limited` | 429 限流 | 是（退避） |
| `password_reset_otp_invalid` | 验证码错误 | 有限次 |
| `password_reset_otp_timeout` | 未收到码 | 是（重发） |
| `password_reset_session_required` | 需要登录态 | 切 L 流程 |
| `password_reset_network` | 网络/CF | 是 |
| `password_reset_unknown` | 响应异常/结果未知 | 不自动重试，标记对账 |

### 6.7 并发与节流

- 同一账号串行（复用现有账号租约）
- 改密全局并发默认 1（敏感操作），可配置
- 发码/验码按账号维度限速，避免触发限流

### 6.8 观测

日志字段：`driver`、`device`(尾号)、`os`、`tls`、`trust`、`source`、`step`、`http_status`、`error_code`、`cooldown_action`

指标：成功率、冷却率、OTP 时延、各步骤失败分布

### 6.9 验收

1. 单账号 U 流程跑通（真发码、真改密、真重新登录验证）
2. 连跑 5 个号，成功率 ≥ 预期且无冷却
3. 失败用例：码错误、超时、429 都能正确分类且不留脏密码
4. 日志能还原每一步实际请求的设备特征

### 6.10 第 0 步待验证（决定 U 是否可行）

- 未登录访问 `/reset-password` 是否 200
- `send-otp` 未登录是否可用；body 是否需要邮箱
- `reset` 是否强制 sentinel；`continue_url` 是否为必走跳转

### 6.11 后续（原第三步尾巴）

- 历史回填：协议号 trusted；rust 号 placeholder（不复用）
- A/B：过期号各 20 个，复用 vs 新生成，比较成功率与冷却率
- 开关：`ACCOUNT_DEVICE_PROFILE_REPLAY_ENABLED`

## 7. 待定问题

1. rust 回传需要动注册链路输出字段，何时批准
2. rust 传输栈是否升级（149 → 152）
3. 是否支持 Safari 家族回放
4. 上游生成器修 webgl/OS 的排期与验证方式

## 8. 改密设计（协议 + rust，两条都要）

> 本节是"改密"整体设计，实施顺序可以先协议、后 rust，但设计覆盖两者。

### 8.1 共同原则

- 内核由注册驱动决定：`protocol_oss_2` → protocol；`sentinel_rs` → rust
- 先重放画像，再执行操作；重放不联网、不发请求
- 只走"未登录的忘记密码"路线（若验证不可行，再退回登录后改密）
- 密码候选由 Python 生成并先写 checkpoint（prepared），提交成功后确认（confirmed）
- OTP 由 Python 侧统一取码，内核负责"发码/验码/等码"

### 8.2 协议改密（P1）

> 执行细节见 §6；此处只列实现要点。

- 传输：Python `wreq 0.13`，`impersonate` 取画像值（152）
- 会话：新建 `WreqProtocolSession`（requests 兼容），注入五层（TLS/头/Cookie/sentinel 环境/语言时区）
- 流程：GET /reset-password → POST send-otp → 取码 → POST validate → GET continue_url
  → sentinel(flow=password_reset) → POST /password/reset
- 位置：`core/accounts/password_reset/`（新目录，不改旧实现）

### 8.3 rust 改密（P2）

- Rust 新增 `reset-password` 流程（现无此能力）
- 输入：`--device-profile <file>`、email、新密码候选、proxy、OTP 通道
- 步骤与协议一致（同一组 auth.openai.com 端点），sentinel 用 `password_reset` flow
- 画像来源：优先设备表 trusted（rust 刷新时写入）；无画像时用 `seed=device_id` 派生
- OTP 交互：Rust 阻塞等待 Python 写入一行验证码（与注册的 OTP 等待/重发口径一致）
- 输出：JSON（ok/status/error/device_id/profile_source），供 Python 确认 checkpoint

### 8.4 职责划分

| 事项 | Python | 内核（protocol/rust） |
|---|---|---|
| 选账号、取画像 | ✅ | — |
| 画像整理/自洽 | ✅ | — |
| 建会话（TLS/头/Cookie） | 协议：✅ / rust：传文件 | ✅ |
| 发码、验码、提交密码 | 协议：✅ | rust：✅ |
| 取邮箱验证码 | ✅ | — |
| 生成密码候选 + checkpoint | ✅ | — |
| 结果分类与落库 | ✅ | — |

### 8.5 分阶段

- P1：协议改密（wreq）+ probe
- P2：rust 改密（新流程 + 画像注入 + OTP 通道）+ probe
- P3：观测（device/os/tls/trust/source）、开关、对照实验

### 8.6 两条链路的验收

1. probe 差异为 0
2. 单账号真实改密成功
3. 不出现 `sensitive_action_cooldown`
4. 失败可重试且不产生脏密码（checkpoint 未确认）
