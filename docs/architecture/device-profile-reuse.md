# 设备画像复用与协议改密（设计定稿）

> 状态：**设计定稿，未开发**。代码停留在既有提交。
> 范围：设备画像的保存与重放、协议/rust 改密流程、邮箱查活门禁。

## 0. 总体结构

```
第一部分  画像存储    注册/刷新/改密时，把真实用过的画像原样存库
第二部分  画像重放    用注册内核 + 注册画像，重建一个"同一台设备"的会话
第三部分  执行操作    在重放出的会话上走改密流程（含邮箱门禁）
```

三者关系：先存 → 再重放 → 最后执行。前一步不成立，后一步不做。

## 1. 实测现状（2026-11-26）

| 注册驱动 | 账号数 | 画像来源 | 真实 UA 系统 |
|---|---|---|---|
| `sentinel_rs` | 5,261 | Python 占位会话（假） | macOS（实际注册走 Windows） |
| `protocol_oss_2` | 5,241 | 上游引擎（真） | Windows Chrome |
| 无/历史 | 14 | 无 | — |

- 抽样 800 条：`browser_type` 全部 `chrome`；全库 0 条 Safari 画像
- 邮箱来源：`generic_api` 9,548、`email_butler` 959
- 未封账号 10,507，全部有密码，`email_invalid` 当前 0
- 冷却证据：4 个"刷新 AT 后立刻改密"的账号 4/4 命中 24h 冷却；
  7 个"会话有效、同设备改密"的账号 7/7 成功 → 触发点是设备变化

## 2. 三种驱动的画像来源

### 2.1 浏览器（Roxy）
- 本地只有绑定：`extra_json.roxybrowser = {profile_id, retained, window_name, ...}`
- `/browser/list_v2` 返回：`dirId`、`windowName`、`os`、`osVersion`
- UA / 屏幕 / WebGL 在 Roxy 客户端内部，接口不返回
- 复用语义：重新打开同一 `profile_id`

### 2.2 协议（`protocol_oss_2` 上游引擎）
- 生成：`generate_fingerprint(country_code, browser_family)`，40 个字段
  - `chrome` → Windows Chrome（UA 152，`impersonate=chrome145/146`，上游再覆写为 `chrome152`）
  - `safari` → `mac_safari` / `ios_safari`
- 传输：Python `wreq 0.13`，支持到 Chrome154
- 落库：注册生命周期把 `session.browser_profile`（74 字段）写入
  `registered_accounts.data.extra_json.browser_profile`
- 已知缺陷：见 §6

### 2.3 rust（`sentinel-rs`）
- 生成：`DeviceFingerprint::generate_for_country(seed, country)`，仅 Windows Chrome
- 传输：`wreq 0.16.1 + wreq-util 0.2.0`，最高 Chrome149
- 注册：不回传画像与 device_id（结果只有 email/password/AT/2FA/cookies）
- 刷新：已回传 `browser_profile`（`python_profile()`）
- 注册种子：`SENTINEL_FP_SEED` 环境变量或系统随机 → **不可复现**
- 刷新种子：`device_id` → **可复现**

## 3. 第一部分：画像存储（定稿）

### 3.1 存什么

驱动返回什么就存什么，**原始 JSON 原样保存**：

| 驱动 | 存储内容 |
|---|---|
| protocol_oss_2 | `session.browser_profile` 全量 74 字段 |
| sentinel_rs | 内核回传的画像结构（待内核支持回传） |
| roxy | `profile_id` + `list_v2` 返回字段 |

### 3.2 只加元数据（不改原数据）

- `driver`、`source`、`trust`
- `device_id`、`family`、`os`（从原数据读取，仅用于查询）
- `kernel_version`、`generator_version`、`emulation`（版本与演进，见 4.8）

### 3.3 表结构：`account_device_profiles`

| 列 | 说明 |
|---|---|
| `account_id` PK | 外键，级联删除 |
| `normalized_email` | 与当前邮箱强绑定，换绑即失效 |
| `encrypted_payload` | 加密的原始画像 JSON |
| `driver` | `protocol_oss_2` / `sentinel_rs` / `roxy` |
| `source` | `registration` / `refresh_at` / `password_reset` / `backfill` 等 |
| `trust` | `trusted` / `placeholder` / `unusable` |
| `device_id`、`family`、`os` | 可检索 |
| `kernel_version`、`generator_version`、`emulation` | 版本与档位 |
| `last_used_at`、`updated_at` | 观测 |

### 3.4 写入点与侵入性

| 驱动 | 是否改注册链路 | 说明 |
|---|---|---|
| protocol_oss_2 | 否 | 画像已在会话里，落库后多写一行 |
| roxy | 否 | 读绑定与 `list_v2`，多写一行 |
| sentinel_rs | **是（最小）** | 需内核在结果 JSON 增加画像字段；只加输出 |

> 约束：注册链路暂不改，rust 回传等批准后再做。

### 3.5 验收

1. 注册成功后设备行存在
2. 原始画像可解密、可完整还原
3. `device_id` 与账号一致
4. 写失败只记日志，不影响注册结果

### 3.6 明确不做

- 不定义 canonical 字段、不推导、不补值、不修正脏值
- 不统一命名
- 不存 `react_*` 请求级 key

## 4. 第二部分：指纹重放（定稿）

### 4.1 定义与范围

- 重放 = 用**注册内核 + 注册画像**重建会话；不执行任何业务操作
- 目标等级 **L2**：UA、client hints、OS、屏幕/硬件、语言/时区、TLS 档位全部一致
- 只服务**改密**（刷新 AT、注册不在此范围）
- `replay_kernel` 由注册驱动决定并固定，不动态切换

### 4.2 内核选择规则（定稿）

```
内核 ∈ 能运行该画像的内核集合        # 能力筛选（保护）
且 内核 == 该账号的注册驱动          # 最终决定（唯一）
否则失败，不降级、不换内核
```

- `protocol_oss_2` → 协议内核（Python `wreq`）
- `sentinel_rs` → rust 内核
- 理由：只有产出画像的内核才能发出同一套 TLS 指纹；UA/CH 可照抄，TLS 栈实现不能
- 例外：将来某内核能逐字节等价复现另一内核的 TLS 栈，才允许交叉

### 4.3 重放的五层

| 层 | 注入内容 | 来源 |
|---|---|---|
| TLS | `impersonate`（如 `chrome152`）→ wreq emulation | 画像 |
| HTTP 默认头 | `User-Agent`、`accept-language`、全套 `sec-ch-ua*` | 画像 |
| Cookie | `oai-did=device_id` + 未过期历史 Cookie | 画像 + 会话缓存 |
| sentinel 环境 | 屏幕/dpr/cores/memory/WebGL/时区/语言/platform | 画像 |
| 语言/时区 | `navigator_language(s)`、`accept_language`、`timezone_iana` | 画像（与头同源） |

### 4.4 重放前的画像整理（内存内，不回写）

1. 以 UA 判定 OS，重写 `browser_os`、`navigator_platform`、`sec_ch_ua_platform`、`user_agent_data_platform`
2. `sec_ch_ua_arch/bitness/model/platform_version/full_version_list` 为空时用 `ua_*` 回填
3. `screen_width/height` 缺失时从 `screen`（`"1366x768"`）解析
4. `viewport_width/height` 缺失时从 `viewport` 对象取
5. `navigator_language` ← `lang`，`accept_language` ← `lang_full`
6. `webgl` 与 OS 不符时按 OS 修正（Windows → D3D11 ANGLE）
7. **版本号一律不动**

### 4.5 会话接口（第三部分使用）

```
session = open_replayed_session(account, proxy, cookies=None)
session.get / post / cookies / headers
session.browser_profile   # 供 sentinel 使用
session.device_id
```

### 4.6 probe 验收（不联网）

1. 用画像建会话
2. 读取实际配置：TLS 档位、UA、全部 `sec-ch-ua*`、语言、时区
3. 与存储画像逐项对比
4. 输出差异清单；**差异必须为 0**

### 4.7 失败策略

- 缺关键字段（`user_agent` / `impersonate` / `device_id`）→ 失败
- 档位在内核中不存在 → 失败
- 内核版本与画像记录不一致 → `kernel_version_mismatch`，默认不重放
- 一律不静默降级

### 4.8 版本与指纹演进

1. 每条画像记录 `kernel_version`、`generator_version`、`emulation`
2. 重放要求三个一致：内核一致、内核版本一致、参数一致
3. 内核升级：先 probe 对比新旧版本；TLS 行为变化则旧账号默认不重放，需要时一次性迁移
4. 生成规则优化：新注册用新规则（`generator_version` +1）；老账号保留原画像
5. 可选：离线计算档位 JA3/JA4 摘要入库，升级后直接比对

### 4.9 组件位置与测试

```
core/accounts/device_replay/
  normalize.py   画像整理（4.4 的 7 条）
  session.py     内核分派 + 五层注入
  probe.py       差异对比
  errors.py      错误分类
```

- 单测：整理规则、档位映射、不支持时报错
- probe：3 个真实画像差异为 0
- 负例：非法 `impersonate` 必须报错

### 4.10 已知限制

- rust 注册画像未回传，当前无法重放 rust 号（需注册链路上报）
- rust 注册种子不可还原；只能从首次刷新（seed=device_id）起固定
- Safari 家族：协议支持，rust 不支持；当前库内 0 条 Safari 画像
- rust 传输最高 149，无法重放 152 画像（必须用协议内核）

## 5. 第三部分：执行操作（改密，定稿）

### 5.1 前置条件与邮箱门禁

- 会话已重放完成
- 新密码候选已生成并写入 `prepared` checkpoint
- **邮箱查活通过**（见 5.11），否则直接失败
- 账号未在冷却中

### 5.2 流程总览：会话优先

```
① 检查会话（同内核 + 同画像）
   GET /api/auth/session
   ├─ 有效（200 且有 accessToken）→ 进 ②
   └─ 过期/无效 → 登录（同一会话、同一画像）→ 顺带刷新 AT → 进 ②
② 改密（与"会话未过期"完全相同的步骤）
③ 用新密码在同会话重新登录验证 → confirmed
```

要点：
- 同一内核 + 同一画像下的重新登录，对服务端是"同一台设备再次登录"
- 登录即刷新 AT，刷新成果被复用
- 登录失败才回退"未登录忘记密码"（仅协议号；rust 号直接失败）

### 5.3 请求序列（6 个接口）

| 步骤 | 请求 | 关键内容 | 期望 |
|---|---|---|---|
| 1 | `GET https://auth.openai.com/reset-password` | 导航头，落 Cookie | 200 |
| 2 | `POST /api/accounts/password/send-otp` | body `{}`（邮箱取自会话） | 200 |
| 3 | 取验证码 | 邮箱取码 | 6 位码 |
| 4 | `POST /api/accounts/email-otp/validate` | `{"code": "..."}` | 200 + `continue_url` |
| 5 | `GET <continue_url>` | 导航头，再落 Cookie | 200 |
| 6 | `POST https://sentinel.openai.com/backend-api/sentinel/req` | flow=`password_reset` | token |
| 7 | `POST /api/accounts/password/reset` | `{"password": "..."}` + sentinel 头 | 200 |
| 8 | 用新密码登录验证 | 同会话 | 成功 → confirmed |

全程同一会话、同一代理，不换设备。

### 5.4 OTP 策略

- 只接受发码之后到达的邮件（`after_ts`）
- 等待窗口 = `OTP_MAX_WAIT`，超时按 `OTP_RESEND_COUNT` 重发
- 验码错误最多重试 2 次
- 冷却（`sensitive_action_cooldown`）→ 不重试，记录 `cooldownAction` 与解除时间

### 5.5 密码与 checkpoint

```
prepared → submitted → confirmed
```

- 新密码由 `generate_registration_password()` 生成（默认 14 位；配置 `REGISTER_PASSWORD` 时优先使用配置值）
- `prepared`：候选已落库（改密前）
- `submitted`：`/password/reset` 返回 200
- `confirmed`：用新密码重新登录验证成功
- 任何失败停在 `prepared`，不留脏密码

### 5.6 错误分类

| 错误码 | 含义 | 可重试 |
|---|---|---|
| `email_unusable` | 邮箱不可用（门禁） | 否 |
| `password_reset_cooldown` | 24h 敏感操作冷却 | 否 |
| `password_reset_rate_limited` | 429 限流 | 是（退避） |
| `password_reset_otp_invalid` | 验证码错误 | 有限次 |
| `password_reset_otp_timeout` | 未收到码 | 是（重发） |
| `password_reset_session_required` | 需要登录态 | 切登录流程 |
| `password_reset_network` | 网络/CF | 是 |
| `password_reset_unknown` | 结果未知 | 不自动重试，标记对账 |

### 5.7 并发与节流

- 同一账号串行（复用账号租约）
- 改密全局并发默认 1，可配置
- 发码/验码按账号维度限速

### 5.8 观测

日志字段：`driver`、`device`(尾号)、`os`、`tls`、`trust`、`source`、`step`、`http_status`、`error_code`、`cooldown_action`

指标：成功率、冷却率、OTP 时延、各步骤失败分布

### 5.9 验收

1. 单账号完整跑通（真发码、真改密、真登录验证）
2. 连跑 5 个号，成功率达标且无冷却
3. 失败用例分类正确、不留脏密码
4. 日志能还原每步的设备特征

### 5.10 端点探测结论（2026-11-27 实测）

有效会话下，先导航 `/reset-password`，再 GET 候选端点：

| 端点 | 结果 |
|---|---|
| `POST /api/accounts/password/reset` | 405 on GET → 存在 |
| `/api/accounts/password/change` | 404 |
| `/api/accounts/password/update` | 404 |
| `/api/accounts/password/set` | 404 |
| `/api/accounts/password` | 404 |
| `/api/accounts/password/change/send-otp` | 404 |
| `/api/accounts/password/current` | 404 |

结论：
1. **改密必须接码**，唯一确认路径是 `send-otp → validate → reset`
2. **邮箱失效即无法改密**
3. "登录后旧密码直改"不成立，取消该候选
4. 前端 `password_change` 仅作为冷却类别出现，无对应端点

### 5.11 邮箱查活门禁（定稿）

**检查三层**

| 层 | 内容 | 失败判定 |
|---|---|---|
| 账号标记 | `email_invalid`、`email_source` | 任一不满足 → 失败 |
| 资源有效期 | `generic_api` 的 `expires_at`；`email_butler` 的租约/凭据 | 过期/无效 → 失败 |
| 实际可读 | 轻量读一次取码接口（不等待新邮件） | 非 200 / 无法解析 / 超时 → 失败 |

**两个适配器一起做**
- `generic_api`（9,548）：`get_account_context` + `require_usable` + 轻量读 `code_url`
- `email_butler`（959）：租约有效性 + 轻量接口

**结果与缓存**
- 写回 `extra_json.email_health = {ok, reason, checked_at, source}`
- 成功缓存 10 分钟，失败缓存 1 小时

**门禁语义**
- 失败 → 任务直接终止，错误码 `email_unusable`，不可重试
- 第一版只接改密；后续扩展注册续跑、换绑邮箱

### 5.12 两个内核的职责划分

| 事项 | 协议（Python） | rust |
|---|---|---|
| 建会话 | Python wreq | rust wreq |
| 会话检查 | `_read_session` | `read_session`（现有） |
| 登录 | Python 流程 | `authenticate`（现有） |
| 改密 7 步 | Python | rust（新增） |
| OTP 取码 | Python | Python 取 → 写 stdin |
| 新密码验证 | Python 登录 | rust `authenticate` |
| 落库 | Python | Python |

**rust 改密的复用方式**
- ① `read_session()`：有效则跳过登录；失效则 `authenticate()`（顺带刷新 AT）
- ② 新增重置密码步骤（同 5.3）
- ③ 用新密码再 `authenticate()` 验证
- 需要小重构：`read_session` / `authenticate` 从 `refresh.rs` 私有提升为 `pub(crate)`

## 6. 已知缺陷：协议注册画像 Windows/macOS 串值

### 6.1 证据（账号 10570）

```
user_agent          = Windows NT 10.0 ... Chrome/152
navigator_platform  = Win32
sec-ch-ua-platform  = "Windows"
browser_os          = macOS                    ← 矛盾
webgl_renderer      = ANGLE (Apple, ... M2)    ← 矛盾
sec_ch_ua_arch 等   = ""（空，真值在 ua_*）     ← 120/120 都这样
```

### 6.2 成因

1. 协议注册开始时 Python 先建本地会话（默认 macOS）
2. 上游生成 Windows 指纹后执行 `session.browser_profile.update(fingerprint)`
3. 合并只覆盖上游存在的键：`browser_os`、`webgl_*` 保留 macOS；`sec_ch_ua_*` 被空串覆盖

### 6.3 影响

- `browser_os`：不发送，仅内部标签，会误导判断
- `webgl_renderer`：进入 sentinel JS 环境，是真不一致
- 空 client hints：回放时会发出空头，比不发更假

### 6.4 修复

- **A（先做，零链路风险）**：入库归一——以 UA 判定 OS，重写 `browser_os`、`webgl_*`，用 `ua_*` 回填空值
- **B（另立项）**：修上游生成器，补 WebGL、覆盖 OS 与空 hints；会改变未来注册实际发送内容，需重新验证成功率

## 7. 待定问题

1. settings 页是否有其他改密入口（需真实浏览器抓包）
2. rust 注册回传画像/种子（需改注册链路，暂不允许）
3. rust 传输栈升级到 Chrome152+（受上游 crate 限制，等发布）
4. 上游生成器补 WebGL/OS 的排期与验证方式

## 8. 实施顺序（建议）

1. **P1 协议改密链路**：存储写入 → 重放组件 → 邮箱门禁 → 改密流程 → probe
2. **P2 rust 改密**：`read_session`/`authenticate` 复用 + 新增重置步骤 + OTP 通道
3. **P3 观测与实验**：日志、开关、A/B（复用 vs 新生成）
4. P4 历史回填：协议号 trusted、rust 号 placeholder
