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

## 5. 第二部分：回放（范围已定，细节待讨论）

### 5.1 已定范围

- 目标等级：**L2**（UA/client hints/OS/屏幕/语言/TLS 档位都要与上次一致）
- **只用于改密**，不用于刷新、不用于注册
- **每个内核只回放自己的画像**，不做跨内核回放（后续再议）
- 每个账号的 `replay_kernel` 固定，不动态切换

### 5.2 硬约束（实测）

- 协议注册画像：UA/TLS 均为 Chrome152，只有 Python wreq 能跑（支持到 154）
- rust 注册画像：TLS ≤149，但**注册未回传**，目前没有真实画像可回放
- 改密现跑在 Python v3 + curl_cffi，**TLS 上限 146**

结论：即使"只用自己内核"，协议号改密要 L2 一致，也必须让改密走 wreq 传输；
否则只能 L1 近似（UA 152 + TLS 146）。

### 5.3 待定

- 改密是否改用 wreq 传输（达成 L2），或先接受 146 近似（L1）
- rust 号暂无真实画像，是否等注册回传后再纳入
- family 差异（chrome-windows / safari-macos / safari-ios）在回放时的必填必空规则

## 6. 第三步：回填 + 观测 + 对照实验（待讨论）

- 历史回填：协议号 trusted；rust 号 placeholder（不复用）
- 日志：`driver/device/os/tls/trust/source`
- A/B：过期号各 20 个，复用 vs 新生成，比较成功率与冷却率
- 开关：`ACCOUNT_DEVICE_PROFILE_REPLAY_ENABLED`

## 7. 待定问题

1. rust 回传需要动注册链路输出字段，何时批准
2. rust 传输栈是否升级（149 → 152）
3. 是否支持 Safari 家族回放
4. 上游生成器修 webgl/OS 的排期与验证方式
