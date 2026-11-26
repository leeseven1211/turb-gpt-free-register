# AT 刷新 Rust 驱动设计（v1 设计稿）

> 状态：已实现（2026-11-25），待灰度。目标行为与 `protocol v3` 等价；新增第三个驱动 `rust`。
> 相关文档：[rust-kernel-bridge.md](rust-kernel-bridge.md)、[sentinel-rs-protocol.md](sentinel-rs-protocol.md)。

## 0. 已确认的决定

1. 刷新语义**跟 protocol v3 一样**：先复用私有会话 Cookie 直接取 AT，失败再走密码 / 邮箱 OTP / MFA 重登。
2. 新增第三个驱动 `rust`（标签 `Rust sentinel-rs`），与 `protocol`、`browser_roxy` 并列。
3. 复用内核 `rust / sentinel_rs`。该实现已在 `IMPLEMENTATIONS` 中登记，当前只开放
   `registration` 操作——这正是预留的扩展位（见 `rust-kernel-bridge.md`：
   “实现名 `sentinel_rs` 已进入 `IMPLEMENTATIONS`，但只有 `registration` 操作可用”）。
4. 任务、租约、代理、邮箱取码、凭据落库、后处理仍在 Python；Rust 只执行认证。
5. 不引入 refresh_token grant。项目内 ChatGPT 账号侧没有 refresh_token（仅 Codex / Outlook 有）。

## 1. 绑定与配置改动清单

| 文件 | 改动 | 目的 |
| --- | --- | --- |
| `contracts/operation_drivers.py` | `_DRIVERS["refresh_at"]` 增加 `DriverDefinition("rust", "Rust sentinel-rs")`；别名增加 `rust / sentinel_rs / sentinel-rs -> rust` | UI 与 `ACCOUNT_AT_REFRESH_DRIVER` 选项自动出现第三项 |
| `contracts/kernel_catalog.py` | `_FIXED_BINDINGS` 增加 `("refresh_at", "rust"): OperationBinding("refresh_at", "rust", "sentinel_rs")` | 规范执行身份 |
| `core/kernels/registry.py` | 目标映射 `-> core.kernels.rust.sentinel_rs:run_refresh_at` | 懒绑定 |
| `core/accounts/liveness/service.py` | `_resolve_refresh_driver` 对 `rust` 早返回（与 `browser_roxy` 同级）；`_refresh_protocol_version` / `_refresh_driver_request` 返回 `rust`；执行分支把 `rust` 与 `protocol_v2/v3` 并列 | 外层冻结选择、代理与租约 |
| `core/kernels/rust/sentinel_rs/` | 新增 `refresh.py`（或 bridge 内新增入口）+ 公开门面 `run_refresh_at` | Python 侧进程边界 |
| `frontend/src/features/accounts/queuedActions.ts` | 第 107 行目前只识别 `browser_roxy`，其余一律 `protocol`；改为三值映射；第 112 行文案同步 | 否则 UI 永远发不出 `rust` |
| `frontend/src/features/accounts/filterDefinitions.ts` / `presentation.ts` | 若驱动会出现在列表列，补充 `rust` 标签映射 | 避免 `sentinel_rs` 漏映射的历史问题 |
| `docs/architecture/rust-kernel-bridge.md` | 更新“只有 registration 可用”的表述 | 文档一致性 |
| `tests/contracts/test_kernel_catalog.py`、`test_kernel_domain_routing.py`、`tests/bulk/test_catalog_settings.py` | 补 `rust` 绑定断言 | 契约回归 |

配置层不需要新键：沿用 `SENTINEL_RS_BIN`、`SENTINEL_RS_TIMEOUT_SECONDS`、`SENTINEL_RS_LOG_LEVEL`。
如刷新需要独立时限，再加 `SENTINEL_RS_REFRESH_TIMEOUT_SECONDS`（默认 1200）。

## 2. 进程接口（沿用 JSONL v1，新增 `action=refresh`）

协议骨架沿用 `sentinel-rs-protocol.md`，只增字段，不改消息类型。

### Python → Rust `start`

| 字段 | 说明 |
| --- | --- |
| `action` | `refresh` |
| `email` | 账号邮箱（身份绑定） |
| `password` | 登录密码，可为空（无密码账号） |
| `totp_secret` | MFA 密钥，可为空 |
| `cookies[]` | `{name,value,domain,path,secure,expires}`，来自 Python 解密后的私有会话缓存 |
| `device_id` / `browser_profile` | 复用注册/上次登录的指纹，禁止重新生成 |
| `proxy` | 已选线路；Rust 不得自行选路 |
| `country` | `ACCOUNT_AT_REFRESH_COUNTRY` 解析结果，用于指纹档位 |
| `otp_window_seconds` | 可选；实际取码窗口由 Python 决定 |

### Rust → Python

| type | 关键字段 | 说明 |
| --- | --- | --- |
| `ready` | `capabilities[]` | 新增 `refresh`、`session_reuse`、`cookie_restore`；缺失时 Python 不启用 rust 驱动 |
| `progress` | `stage`、`state`、`detail` | 映射 `session_cache` / `authenticate` / `password` / `email_otp` / `mfa_challenge` / `workspace` / `token` |
| `otp_request` | `challenge_id`、`sent_at`、`after_ts` | 与注册一致：取码仍由 Python 的邮箱服务完成 |
| `otp_response` | `challenge_id`、`code?`、`status` | `ok / timeout / malformed` |
| `result` | 见下 | 成功终态 |
| `result_partial` | `status`、`stage`、`error_code`、`error_category`、`retryable`、`roxy_fallback_allowed`、`remote_request_started`、`mutation_submitted`、`action_dispatched`、`diagnostics` | 失败终态；字段必须能让现有分类器工作 |

`result.data` 成功字段：`access_token`、`cookies[]`、`session_info{accessToken,sessionToken,user{id,email},account{id}}`、
`session_reused`、`auth_method`、`methods[]`、`password_auth_status`、`email_otp_status`、`mfa_status`、`checked_at`。

### 约束

- 凭据（password / code / cookies / access_token）不得出现在 `progress`、日志、错误消息里。
- 每条消息同样带 `v / exec / req / seq / type / data`，单条 ≤ 64 KiB。
- `cancel` 只阻止新动作；已发送动作以 `submission` 事实收口。

## 3. Rust 内部流程（与 v3 一一对应）

| 步骤 | 行为 | Rust 现状 |
| --- | --- | --- |
| 0 | 入参校验、邮箱归一、身份绑定 | 新建（简单） |
| 1 | cookies → wreq Jar；`device_id` / `browser_profile` 注入 | 导出已有，**导入需新建** |
| 2 | `GET chatgpt.com/api/auth/session` 取快路径 AT | 请求构造与解析已有 |
| 3 | 身份核验：email、user id、JWT `sub` 与账号一致 | **新建** |
| 4 | 网络预检 + warmup（csrf/oai-did）+ signin + authorize 跟随 | 引导/authorize 已有（`flow/authorize.rs`） |
| 5 | 登录状态机（≤8 轮）：页面/路径判定、阶段去重、循环检测 | **新建**（对标 `_authenticate`） |
| 6 | `POST /api/accounts/password/verify` | 构造已有 |
| 7 | `POST email-otp/send` → `otp_request` → `email-otp/validate` | 构造已有；取码改由 Python |
| 8 | `POST mfa/verify`（TOTP） | 构造 + TOTP 算法已有，登录分支需新建 |
| 9 | `workspace/select` → 跟随 → callback code | 构造已有 |
| 10 | `GET /api/auth/session` 取最终 AT / sessionToken | 已有 |
| 11 | 输出 cookies + 身份事实 | **新建导出字段** |

状态机分支矩阵（与 v3 相同）：

| 判定 | 动作 | 终态/错误 |
| --- | --- | --- |
| `/about-you`、`/create-account*`、`about_you` | 终止 | `account_profile_required`（account） |
| `/mfa-challenge*` | `mfa/verify` | 缺密钥 `mfa_secret_missing`，拒绝 `mfa_rejected` |
| `/workspace` | `workspace/select` | 歧义 `workspace_ambiguous` |
| `/log-in/password` | `password/verify` | 缺密码 `password_missing`，拒绝 `password_rejected` |
| `/email-verification` | OTP 流程 | 超时 `email_otp_failed`；邮箱失效 `email_verification_required` |
| 其它落地 URL | callback → session | 无法识别 `auth_page_unknown` |
| 同名阶段重复 | 终止 | `auth_challenge_loop` |
| 8 轮未结束 | 终止 | `auth_challenge_loop` |

密码页探测（仅一次）与“无密码账号退回邮箱验证码”的判定必须照搬 v3，否则老号失败率会明显上升。

## 4. 错误码映射

Rust 直接使用现有 code，不再发明一套：

| code | category | retryable | roxy_fallback_allowed |
| --- | --- | --- | --- |
| `access_token_missing` / `access_token_expired` | response / auth | false | false |
| `cached_session_network_failed` / `cached_session_http_failed` | network | true | true |
| `cached_session_invalid_response` / `session_invalid_response` | response | true | true |
| `identity_mismatch` / `identity_unconfirmed` | account / response | false | false |
| `auth_navigation_failed` | network | true | true |
| `auth_route_rejected` | network | true | **true**（外层按现有规则） |
| `auth_page_unknown` / `auth_challenge_loop` / `auth_context_ambiguous` / `untrusted_auth_url` / `auth_redirect_*` | response | false | false |
| `password_missing` / `mfa_secret_missing` | configuration | false | false |
| `password_rejected` / `mfa_rejected` | auth | false | false（禁止重复提交） |
| `password_login_unavailable` | auth | false | false |
| `email_otp_failed` | email | true | true（仅 no_mail 分支） |
| `email_verification_required` | email | false | false |
| `account_profile_required` | account | false | false |
| 兜底 | `protocol_rust_unknown_error` | runtime | false | false |

**必须同时改的地方**：`core/operations/errors.py`、`error_labels.py`、`docs/architecture/task-error-catalog.md`
登记 `protocol_rust_unknown_error`，并把该 code 加入 `service._refresh_result_is_unknown` 的 markers
集合；否则“请求已发出但结果未知”会被当成普通失败，触发重放。

`auth_diagnostics` 需带 `operation`、`failure_kind`、`mailbox_error_code`，否则
`_refresh_result_is_no_mail` / `_refresh_result_is_temporary_mailbox_failure` 不会回退 browser_roxy。

## 5. 结果落地（Python 侧）

1. bridge 校验进程退出码、`exec/req` 关联、邮箱一致、AT 非空。
2. 组装与 v3 同形的结果字典，调用 `on_authenticated(result, session=None)`。
   - 现有 v3 传真实 `BrowserSession`；rust 无会话对象，`session` 传 `None`。
   - `core/accounts/inspection/service.py` 的套餐复用会退化为 token-only（已有兜底文案
     “当前登录驱动未提供可复用的协议会话”），需要在验收时确认套餐结果仍可接受。
3. Python 用返回的 `cookies + device_id + browser_profile + user/account id` 写
   `account_protocol_sessions`（Postgres 加密列，TTL 24h）。**Rust 不直连数据库。**
4. `remote_request_started` / `mutation_submitted` / `action_dispatched` 必须如实回填：
   - 快路径命中：`remote_request_started=false`；
   - 已调 authorize 或 password/OTP/MFA：`true`；
   - 提交了密码但没收到回执：`mutation_submitted=true` + `reconcile_required`。

## 6. 并发、取消、超时、灰度

- 每账号一个子进程，互不共享 SQLite；并发上限沿用任务执行器，不新增独立池。
- `cancel` → 发送 cancel 消息，等待 `result_partial`；超时后 kill 进程，按“已确认事实”收口。
- 超时沿用 `SENTINEL_RS_TIMEOUT_SECONDS=1200`；OTP 等待计入 Python 侧邮箱预算，不叠加。
- 默认驱动仍是 `protocol`；`rust` 仅显式选择生效，先单账号 / 小批量灰度。
- 回滚：切回 `protocol` 即可，无需回退二进制；`ready.capabilities` 缺 `refresh` 时 Python 拒绝启动该驱动。

## 7. 测试计划

**Rust 单测（离线 fixture）**
1. cookie 注入 → Jar 内容与域/期限过滤（过期 cookie 丢弃、非白名单域拒绝）。
2. `/api/auth/session` 解析：camelCase / snake_case、缺 AT、非 2xx。
3. 身份核验：email 不匹配、JWT sub 不匹配、user id 不匹配。
4. 状态机：password / email_otp / mfa / workspace / callback / unknown / 循环 / 超过 8 轮。
5. 密码页仅探测一次；无密码账号走 OTP 分支。
6. 错误码与 category/retryable/roxy_fallback 三元组逐条断言。

**Python 契约测试**
1. `operation_driver_options("refresh_at")` 含 `rust`；schema 选项自动出现。
2. `operation_binding("refresh_at", "rust")` 与 `resolve_operation_runner` 正确。
3. `_resolve_refresh_driver` 对 `rust` / 别名 / 任务快照的解析。
4. `result` → 归一字段 → `_refresh_result_is_unknown / _is_no_mail / _is_rejected` 分类正确。
5. 会话缓存写回与 `session=None` 时的套餐查询退化。
6. 取消：发 cancel、超时 kill、不重放已提交动作。

**回放与灰度**
- 用同一账号分别跑 `rust` 与 `protocol v3`，对比请求序列（method + path 顺序）与阶段事件。
- 10 个真实号小批量：成功率、`session_reused` 命中率、耗时、风控/验证码触发率。
- 回归现有刷新相关用例（`tests/accounts/*refresh*`、`tests/bulk/test_token_refresh.py` 等）。

## 8. 已确认的决定

1. OTP 取码完全交 Python：Rust 只发 `otp_request`，等待 `otp_response`；不引入邮箱依赖差异。
2. 快路径（cookie 复用 → `/api/auth/session`）失败后**自动重登**，与 v3 行为一致。
3. 无密码账号**照 v3 走邮箱验证码**，不是直接报错：
   - 页面是 `/email-verification` 且本地存有密码时，只探测一次 `/log-in/password`；服务端若不下发密码页，继续邮箱验证码；
   - 只有服务端确实要求密码、而本地没有密码时，才报 `password_missing`；
   - `account_email_is_invalid` 的账号才报 `email_verification_required`。
4. 兜底码使用新名 `protocol_rust_unknown_error`。
