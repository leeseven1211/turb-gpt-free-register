# 设备画像复用方案（讨论稿，2026-11-26）

> 状态：方案讨论已完成，**未开发**。本文档是第一步（记录注册画像）的设计依据。

## 0. 结论摘要

- 复用画像的目的：让同一账号后续的刷新 / 改密 / 登录沿用**上一次真实用过的设备**，
  避免"换设备 + 敏感操作"触发 OpenAI 的 24 小时 `sensitive_action_cooldown`。
- 复用的前提是**存的是真画像**：必须记录驱动**实际发出**的那一套，而不是本地占位会话的画像。
- 三种驱动的画像格式**不一致**（字段名、字段集、来源都不同），需要一层 canonical 归一。
- 版本号原样保留，不做降级；TLS 档位由画像决定，UA 不改。

## 1. 实测现状（2026-11-26）

### 1.1 账号分布

| 注册驱动 | 账号数 | 画像来源 | 真实 UA 系统 |
|---|---|---|---|
| `sentinel_rs` | 5,261 | Python 占位会话（假） | macOS（实际注册走 Windows） |
| `protocol_oss_2` | 5,241 | 上游引擎（真） | Windows Chrome |
| 无/历史 | 14 | 无 | — |

抽样 800 条：`browser_type` 全部为 `chrome`；`protocol_oss_2` 全部 Windows，
`sentinel_rs` 全部 macOS（占位）。全库 **0 条 Safari 画像**。

### 1.2 已有的冷却证据

- 4 个"刷新 AT（新设备登录）→ 立刻改密"的账号：**4/4** 返回
  `403 sensitive_action_cooldown`（`cooldownAction=password_reset`，24 小时）
- 7 个"会话仍有效（同设备，无新登录）→ 改密"的账号：**7/7** 成功

结论：触发点是**设备变化**，不是设备未变。

### 1.3 传输层能力（决定能否原样回放）

| 栈 | 组件 | 最高 Chrome 档位 |
|---|---|---|
| 协议注册（上游引擎） | Python `wreq` | Chrome154（含 152/153） |
| rust sentinel-rs | `wreq 0.16.1` + `wreq-util 0.2.0` | **Chrome149** |
| Python BrowserSession | `curl_cffi 0.16.0` | **Chrome146** |

- 协议注册画像：UA 写 `152.0.0.0`，`impersonate=chrome152`，**传输层真的能发 152**（wreq）
- 若用 rust 或 curl_cffi 回放同一画像，TLS 只能到 149/146 → 会出现"UA 152 + TLS 149"的错位

## 2. 三种驱动的画像来源

### 2.1 浏览器（Roxy）

- 本地**没有指纹字段**，只有绑定关系：`extra_json.roxybrowser = {profile_id, retained, window_name, ...}`
- 指纹（UA / 屏幕 / WebGL / 时区）保存在 Roxy 客户端内部的 Profile 里
- 创建时可控的字段只有：`os`（Windows/macOS/Linux/IOS/Android）、`osVersion`、`windowName`、代理
- 复用语义：**重新打开同一个 `profile_id`**，而不是回灌字段
- 本机浏览器能力关闭，库内 0 个 roxy 注册账号

### 2.2 协议（`protocol_oss_2` 上游引擎）

- 生成：`generate_fingerprint(country_code, browser_family)`，`browser_family ∈ {chrome, safari}`
  - `chrome` → 仅 `chrome`（Windows Chrome）
  - `safari` → `mac_safari` / `ios_safari`
- 版本池：`ua_ver=152.0.0.0`，`impersonate=chrome146/145`（上游配置里再被覆写为 `chrome152`）
- 落库：注册生命周期把 `session.browser_profile` 写进 `registered_accounts.data.extra_json.browser_profile`
- 字段数：74（含别名、TLS/Akamai 摘要、react key）
- **脏字段**：`browser_os=macOS`（残留）、`webgl_renderer=Apple Metal`（与 Windows UA 矛盾）

### 2.3 rust（`sentinel-rs`）

- 生成：`DeviceFingerprint::generate_for_country(seed=device_id, country)`，**仅 Windows Chrome**
  - UA：`Windows NT 10.0; Win64; x64 ... Chrome/146.0.0.0`
  - platform：`Win32`；`sec-ch-ua-platform: "Windows"`；arch `x86`
  - TLS：wreq 档位 `Chrome140/145/146/149`
- 注册：**不回传**画像与 device_id（结果只有 email/password/AT/2FA/cookies）
- 刷新：已支持回传 `browser_profile`（`python_profile()`，39 字段）
- 落库的注册画像是 Python 占位会话（macOS），不是它真正用的 Windows

## 3. 字段格式比对

### 3.1 三份字段集合

| 分组 | Roxy | 协议（74） | rust（39） |
|---|---|---|---|
| 设备标识 | `profile_id` | `device_id`(账号级) | `device_id` |
| 系统 | `os`、`osVersion` | `browser_os`(脏)、`browser_type` | `browser_os`、`device_os` |
| UA / 版本 | 由 Profile 决定，不落本地 | `user_agent`、`chrome_major`、`chrome_full_version` | 同左 |
| client hints | 无 | `sec_ch_ua*` 全套 | `sec_ch_ua*` 全套 |
| navigator | 无 | `navigator_platform/vendor/languages` | 同左 |
| 屏幕/硬件 | 无 | `screen_*`、`outer_*`、`viewport_*`、`dpr`、`cores`、`memory`、`heap` | 同左 |
| WebGL | 无 | `webgl_*`（值错） | **缺失**（要按 OS 补默认） |
| 语言/时区 | 无 | `timezone_*`、`navigator_language*` | 同左 |
| 别名 | 无 | `lang`、`lang_full`、`languages`、`locale`、`timezone`、`screen`(str)、`viewport`(dict)、`ua_arch`、`ua_bitness`、`ua_model`、`ua_platform_version`、`ua_full_version_list`、`browser_version` | 无 |
| TLS 传输 | 无 | `impersonate`、`fallback_impersonates`、`tls_fp`、`akamai_fp`、`client_hints_high_entropy` | `impersonate` |
| 元信息 | 无 | `fingerprint_id`、`country_code` | 无 |
| 请求级（禁止复用） | 无 | `react_listening_key`、`react_container_key`、`react_resources_key` | 无 |

### 3.2 结论：不一致，但可归一

差异分四类：

1. **命名差异**：协议用 `lang/lang_full/screen/viewport/ua_*`，rust 用 `navigator_*` / `sec_ch_ua_*`
2. **缺失**：rust 没有 WebGL、没有 `tls_fp/akamai_fp`；Roxy 没有任何字段
3. **脏值**：协议的 `browser_os`、`webgl_renderer` 与 UA 矛盾
4. **请求级**：`react_*` 每次会话都变，必须排除

处理方式：**canonical 字段 + 每个驱动一个 adapter**。

### 3.3 canonical 字段（存储与复用都以它为准）

- 标识：`device_id`
- 引擎：`browser_family`、`browser_type`、`browser_os`、`chrome_major`、`chrome_full_version`
- HTTP：`user_agent`、`accept_language`、`sec_ch_ua`、`sec_ch_ua_platform`、
  `sec_ch_ua_platform_version`、`sec_ch_ua_arch`、`sec_ch_ua_bitness`、`sec_ch_ua_model`、
  `sec_ch_ua_full_version_list`、`sec_ch_ua_mobile`、`send_client_hints`
- navigator：`navigator_platform`、`navigator_vendor`、`user_agent_data_platform`、
  `navigator_language`、`navigator_languages`、`max_touch_points`、`is_mobile`
- 屏幕/硬件：`screen_width/height`、`screen_avail_*`、`outer_*`、`viewport_*`、`color_depth`、
  `device_pixel_ratio`、`hardware_concurrency`、`device_memory`、`js_heap_size_limit`、
  `webgl_vendor`、`webgl_renderer`
- 语言/时区：`timezone_iana`、`timezone_name`、`timezone_offset_minutes`、`locale_profile`
- 传输：`impersonate`、`fallback_impersonates`、`tls_fp`、`akamai_fp`
- 元信息：`fingerprint_id`、`country_code`

归一规则（adapter）：
- 协议：别名映射到 canonical；`screen`(str) → `screen_width/height`；`viewport`(dict) → `viewport_*`；
  `ua_*` → `sec_ch_ua_*`；`browser_os`/`webgl_*` 以 UA 为准重写
- rust：直接是 canonical 子集；缺 `webgl_*` 时按 OS 补默认值
- Roxy：只存 `profile_id` + `os` + `osVersion`，其余标记 `unavailable`

## 4. 存储设计

### 4.1 表 `account_device_profiles`（已建）

| 列 | 说明 |
|---|---|
| `account_id` PK | 外键到 `registered_accounts`，级联删除 |
| `normalized_email` | 与当前账号邮箱强绑定，换绑即失效 |
| `encrypted_payload` | 加密 JSON：`{device_id, profile(canonical), raw(原始), impersonate, browser_ref}` |
| `source` | `registration` / `refresh_at` / `refresh_at_rust` / `password_reset` / `password_setup` / `backfill` |
| `trust` | `trusted` / `placeholder` / `unusable`（新增列） |
| `last_used_at` / `updated_at` | 观测用 |

### 4.2 读取优先级

```
设备表 trusted → 账号 data.extra_json.browser_profile（规范化后可用才用）
              → 设备表 placeholder（仅记录，不复用）
              → 无画像（现场生成）
```

### 4.3 写入时机

| 场景 | 写什么 | trust |
|---|---|---|
| 协议注册成功 | 上游真实画像（74→canonical） | trusted |
| rust 注册成功 | rust 回传的真实画像（需新增回传） | trusted |
| rust 刷新成功 | rust 实际画像 | trusted |
| 协议 v2/v3 刷新成功 | 会话画像 | trusted |
| 改密/补密码成功 | 本次会话画像 | trusted |
| 历史回填：协议号 | 规范化后的注册画像 | trusted |
| 历史回填：rust 号 | Python 占位 macOS 画像 | placeholder（不复用） |
| 浏览器注册 | `profile_id` 引用 | trusted（字段不全） |

失败一律只记日志，不阻断主流程。

## 5. 三步实施

### 第一步：注册画像写入 + 格式归一（本文档范围）

1. 新建 `core/storage/accounts/device_profiles.py`（已完成基础版）
2. 加 `trust` 列
3. 定义 canonical schema + 三个 adapter（protocol / rust / roxy）
4. 注册链路写入：
   - 协议：生命周期落库后，从 `session.browser_profile` 归一后写
   - rust：**需要内核回传** `device_id` + 画像，且新增 `--device-profile` 无关（第一步只做回传）
   - 浏览器：写 `profile_id` + `os`
5. 校验：注册后设备行存在、`trust=trusted`、canonical 字段自洽

### 第二步：复用

1. rust 支持"按画像回放"（`--device-profile` 文件）
2. Python 侧读取优先级 + 临时文件传递
3. TLS 档位：按画像 `impersonate`，不支持时按 `fallback_impersonates` 顺序挑
4. 开关 `ACCOUNT_DEVICE_PROFILE_REPLAY_ENABLED`

### 第三步：回填 + 观测 + 对照实验

1. 全量回填（协议 trusted / rust placeholder）
2. 日志：`device/os/tls/trust/source`
3. A/B：过期号各 20 个，复用 vs 新生成，比较成功率与 `sensitive_action_cooldown` 率

## 6. 待定问题

1. **rust 传输栈升级**：`wreq-util 0.2.0` 只到 Chrome149，协议画像常是 152。
   要么升级 rust 到 `wreq 6 + wreq-util 3`（有编译风险），要么接受"UA 152 + TLS 149"。
2. **Safari 家族**：目前 0 个真实 Safari 画像；是否支持回放 Safari（rust 当前不支持）。
3. **Roxy 画像细节**：是否需要调 Roxy API 拉取 Profile 的真实 UA/屏幕，还是只存 `profile_id`。
4. **协议注册的 webgl 脏值**：是否在本步一起修正上游生成器（给 chrome 画像补 Windows GPU 默认值）。
