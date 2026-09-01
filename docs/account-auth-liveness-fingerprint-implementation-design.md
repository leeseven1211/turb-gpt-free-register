# 账号认证、刷新 AT、2FA 与指纹详细实施设计

> 本文是详细技术参考，不直接作为实施顺序。实际开发、放行和回退以 [分阶段实施清单](account-auth-protocol-staged-rollout-checklist.md) 为唯一依据。

状态：Proposal（详细实施规范；业务实现尚未落地，受控接口验证已完成）

日期：2026-09-01

关联总设计：[`account-auth-liveness-fingerprint-design.md`](account-auth-liveness-fingerprint-design.md)

## 1. 最终决策

本设计固定以下边界：

1. 普通“查活”继续只验证已有 AT，不执行登录，不读取密码/TOTP，不触发邮箱 OTP。
2. “刷新 AT”才允许重新认证；优先按远端实际页面/响应选择密码、TOTP 或邮箱 OTP。
3. 密码被明确拒绝后，允许在新会话中受控执行一次邮箱 OTP fallback。
4. 密码提交结果未知不等于密码错误；可以执行邮箱 fallback，但密码状态保留 `unknown`，不能标为 `rejected`。
5. 同账号的 Protocol 设备层画像稳定；每次 run 的会话层和每次请求的动态层继续变化。
6. 原始设备 ID、原始会话标识和完整代理凭据允许保存，但只能进入专用受限存储；普通任务事件、日志、账号列表和普通 API 仍只使用脱敏摘要。
7. Roxy 注册 Profile 首版仍是临时 Profile，任务结束关闭并软删除；不把本次改造扩大成长期 Cookie/Profile 管理。
8. 账号密码、TOTP secret、邮箱 OTP、AT、Cookie 不新增到认证上下文表；它们继续由现有各自事实来源管理。
9. 不整体 cherry-pick 上游提交；只移植已验证的协议步骤和响应字段。
10. 每个阶段独立开关、独立提交、可回滚；实施前和灰度期间不得批量真实刷新。
11. 当前密码、普通查活、Token 刷新、邮箱 OTP、TOTP/2FA 和 Roxy 能力作为长期稳定实现保留；新接口平行落在 `protocol_v2`，不得原地改写 current 分支后复用旧名称。
12. 每个主要步骤独立选择 `browser_current`、`protocol_current`（存在时）或 `protocol_v2`；全局 v2 开关只禁用新协议接口，不覆盖用户明确选择的现有协议。
13. Roxy 浏览器是默认主路径，也是 Protocol 被选为主路径时可配置的 fallback。Protocol 因速度优势作为可选驱动，不自动成为默认；Roxy 代码、配置、能力检测、诊断入口和测试必须继续维护。
14. 同一认证 session 不能混合 Protocol Cookie/challenge 与 Roxy 中间状态；任何跨驱动 fallback 都必须是新的完整 run，并遵守凭据已提交和 `request_unknown` 边界。
15. `browser_current`、`protocol_current` 和 `protocol_v2` 都必须保持普通查活只验证旧 AT；任何开关组合都不能让普通查活登录、发送 OTP 或提交密码/TOTP。

## 2. 当前代码事实与可复用能力

| 范围 | 当前能力 | 当前缺口 | 设计动作 |
| --- | --- | --- | --- |
| 普通查活 | `live_check` 读取旧 AT，经 `check_account_plan()` 在线探测 | probe 内部每次随机 `BrowserSession`，无摘要 | 复用账号 Protocol identity，保存独立查活摘要 |
| 刷新 AT | `token_refresh` 走 Protocol 邮箱 OTP，失败可进 Roxy 邮箱 OTP | 不用保存的账号密码/TOTP | 接入统一认证编排器 |
| Protocol 密码/MFA | 上游有 password verify、MFA issue/verify 原型 | 响应分类、错误语义和重试不完整 | 只移植协议请求，重写状态机 |
| Roxy 登录密码 | `roxy_codex_oauth.py` 已能识别并提交保存密码 | 能力被 Codex 私有模块占有 | 保留现有入口；给 v2 新增公开 browser adapter |
| Roxy TOTP | 能识别 stale `/log-in/password` URL 上的 TOTP 控件 | 查活 Roxy fallback 未复用 | 保留 current；v2 fallback 复用公开适配能力 |
| Roxy 邮箱 OTP | 已有严格 passwordless 按钮、OTP 输入、重发和页面确认 | `roxy_liveness.py` 使用的是简化流程 | 两套 current 均保留；v2 新状态机不反向替换 |
| `login?email` 空壳 | 已有浏览器 NextAuth fallback 和一次补交表单 | 多处复制 | current 保留；新代码只新增一份 v2 实现，不再继续复制 |
| 页面状态 | 已有 `PageState`、URL+DOM 识别、共享 stage budget | 缺 MFA、account chooser、risk challenge 等账号登录状态 | 新增 `AuthPageState`，不污染注册状态机 |
| 存储 | PostgreSQL 账号、任务、事件、代理租约都是事实来源 | 原始认证上下文无专用私有边界 | 新增长期 identity 表和 run context 表 |

现有可复用代码位置：

- `core/live_check_service.py`：普通查活/刷新 AT 动作边界、账号 claim、代理轮换和任务投影。
- `core/account_liveness.py`：当前 Protocol 邮箱 OTP 链。
- `core/session.py`：TLS impersonation、请求头、设备/会话参数和 Cookie jar。
- `core/registration/state_machine.py`：共享 deadline 和基础页面分类思想。
- `core/registration/roxy.py`：强 OTP 页面识别、passwordless 按钮和密码页 DOM 快照。
- `core/roxy_codex_oauth.py`：密码/TOTP/邮箱 OTP 浏览器登录状态机、账号选择和 `login?email` 恢复。
- `core/proxy_lease_store.py`：已经保存完整 `proxy_url` 的 PostgreSQL 代理租约事实来源。

## 3. 名词和数据层级

### 3.1 用户动作

```text
registration
  保持现有注册状态机；只记录本次 Roxy 环境、代理和安全摘要

live_check
  只验证已有 AT

token_refresh
  允许重新登录并获取新 AT

twofa_setup
  使用新鲜 AT enroll/activate TOTP
```

### 3.2 画像层级

| 层级 | 生命周期 | 典型字段 | 保存位置 |
| --- | --- | --- | --- |
| 设备层 | 同账号长期稳定 | Protocol `device_id`、OS/UA、screen、CPU、memory | `account_protocol_identities` |
| 会话层 | 每个 run/session 独立 | Sentinel SID、OAuth session ID、auth logging ID、Datadog IDs、React keys | `account_auth_run_contexts` |
| 请求层 | 每次请求变化 | 时间、nonce、PoW、临时 challenge | 默认不持久化，只记录领域结果 |
| Roxy 环境层 | 当前每个 Roxy run | Roxy profile ID、平台/UA/屏幕摘要 | run context + 安全摘要 |

### 3.3 两种展示

`SafeFingerprintSummary` 用于列表、任务详情和普通 API，不含原始关联标识和代理凭据。

`PrivateAuthContext` 用于内部诊断，允许包含原始设备 ID、会话标识、Roxy profile ID 和完整代理上下文，但不包含密码、OTP、Token 或 Cookie。

## 4. 目标架构

```text
WebUI route
   |
   v
live_check_service（队列、claim、代理租约、TaskReporter）
   |
   v
account_auth.policy.resolve_and_snapshot()
   |
   +-- effective=browser_current
   |      -> browser adapter -> 当前稳定 Roxy 主路径
   |
   +-- effective=protocol_current
   |      -> protocol current adapter -> 当前稳定协议入口
   |
   +-- effective=protocol_v2
          -> protocol v2 adapter
                 password / TOTP / email OTP / callback
                    |
                    +-- allowlisted fallback + 无 request_unknown
                           -> 新建完整 browser fallback run
                              Roxy 页面识别 / password / TOTP / email OTP

registration flow ----> auth private context recorder
                         只观察/保存本次 Roxy 环境，不改变注册决策

公共依赖：
  credentials resolver
  protocol identity store
  auth run private context store
  response/page classifier
  safe summary builder
```

业务编排器只接收结构化结果，不根据异常字符串决定密码、MFA 或邮箱分支。browser/protocol current adapter 只调用现有公开入口，不把旧实现搬进新包；`protocol_v2` 和 browser fallback 不能反向修改 current 的内部状态机。

## 5. 领域契约

### 5.1 枚举

```python
class AuthAction(str, Enum):
    REGISTRATION = "registration"
    LIVE_CHECK = "live_check"
    TOKEN_REFRESH = "token_refresh"
    TWOFA_SETUP = "twofa_setup"

class AuthDriver(str, Enum):
    PROTOCOL = "protocol"
    ROXY = "roxy"

class AuthState(str, Enum):
    START = "start"
    PREWARM = "prewarm"
    EMAIL_FORM = "email_form"
    AUTH_TRANSIENT = "auth_transient"
    PASSWORD_LOGIN = "password_login"
    PASSWORD_SUBMITTED = "password_submitted"
    PASSWORD_REJECTED = "password_rejected"
    PASSWORD_RESULT_UNKNOWN = "password_result_unknown"
    EMAIL_OTP_SEND = "email_otp_send"
    EMAIL_OTP_INPUT = "email_otp_input"
    EMAIL_OTP_SUBMITTED = "email_otp_submitted"
    MFA_TOTP = "mfa_totp"
    MFA_SUBMITTED = "mfa_submitted"
    ACCOUNT_CHOOSER = "account_chooser"
    CALLBACK = "callback"
    AUTHENTICATED = "authenticated"
    ACCOUNT_UNUSABLE = "account_unusable"
    PROFILE_CREATE = "profile_create"
    PHONE_REQUIRED = "phone_required"
    EXTERNAL_IDP = "external_idp"
    RISK_CHALLENGE = "risk_challenge"
    UNKNOWN = "unknown"
```

### 5.2 单步结果

```python
@dataclass(frozen=True)
class AuthStepResult:
    state: AuthState
    ok: bool
    error_code: str | None = None
    retry_class: str | None = None
    continue_url: str | None = None
    factor_id: str | None = None
    remote_response_received: bool = False
    action_dispatched: bool = False
    evidence: dict[str, object] = field(default_factory=dict)
```

关键语义：

- `action_dispatched=True` 表示凭据或验证码已经提交，后续不能因为超时就盲目重交。
- `remote_response_received=False` 表示结果未知，不得推断密码错误或验证码错误。
- `evidence` 只允许放白名单字段，例如 HTTP status、`page.type`、URL path、控件数量和错误码；不放响应全文。

### 5.3 最终结果

```python
@dataclass(frozen=True)
class AuthResult:
    ok: bool
    status: str
    action: AuthAction
    driver: AuthDriver
    auth_method: str | None
    validation_method: str
    access_token: str | None
    session_info: dict | None
    password_auth_status: str
    credential_warnings: tuple[str, ...]
    fallback_chain: tuple[str, ...]
    error_code: str | None
    error_message: str | None
    safe_fingerprint: dict | None
    private_context_ids: tuple[int, ...]
```

一次认证可能创建多条 route、Protocol 新会话和 Roxy fallback，所以结果携带的是有序 `private_context_ids`，不能用一个 ID 覆盖整条链；raw context 关闭时它是空 tuple。`access_token` 和 `session_info` 只在 service 到 storage command 的进程内调用链中存在；不得把整个 dataclass 直接写入事件或 API。

## 6. 原始设备、会话和代理的存储设计

### 6.1 数据分级

| 级别 | 内容 | 是否持久化 | 是否进任务事件/UI |
| --- | --- | --- | --- |
| P0 公共摘要 | driver、OS、UA major、地区、screen、profile ref | 是 | 是 |
| P1 关联标识 | 原始 device ID、Sentinel/OAuth/Datadog/React IDs、Roxy profile ID | 是 | 否 |
| P2 网络凭据 | 完整代理 URL、用户名、密码、出口 IP | 是，受限 | 普通页面只显示脱敏值 |
| P3 登录凭据 | 账号密码、TOTP secret、AT | 继续存现有事实来源 | 不复制进新表 |
| P4 一次性数据 | 邮箱 OTP、TOTP code、Cookie、Sentinel token、PoW token | 不新增持久化 | 否 |

### 6.2 长期 Protocol identity 表

新增 `account_protocol_identities`：

```sql
CREATE TABLE account_protocol_identities (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    account_id BIGINT,
    profile_version INTEGER NOT NULL,
    profile_key TEXT NOT NULL,
    device_id TEXT NOT NULL,
    browser_profile JSONB NOT NULL,
    profile_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at TIMESTAMPTZ,
    UNIQUE(account_id, profile_version)
);

CREATE UNIQUE INDEX uq_account_protocol_identities_active
    ON account_protocol_identities(account_id)
    WHERE retired_at IS NULL;
```

规则：

- `profile_key` 和 `device_id` 原值允许保存，但不进入 `registered_accounts.data`、普通账号 API 和兼容导出。
- `browser_profile` 只保存设备层字段，不保存 session/trace/request 字段。
- 首次创建使用 upsert/事务内锁配合 active 唯一索引；并发 worker 必须取得同一个 active identity。
- 账号归档不删除 identity；账号明确删除时是否级联由后续删除功能显式处理。
- 画像算法升级在一个事务中退休旧行并新增版本，不静默重算或覆盖老画像。

`ensure_account_protocol_identity(account_id)` 的固定事务顺序：

1. `SELECT id FROM registered_accounts WHERE id=%s FOR UPDATE`，账号不存在立即返回领域错误。
2. 查询该账号 `retired_at IS NULL` 的 active identity；存在即返回，不更新任何画像字段。
3. 在进程内用安全随机数生成 256 bit `profile_key`，按当前 `profile_version` 派生 device/profile。
4. 插入 identity；`(account_id, profile_version)` 冲突时重新读取 active 行，不生成第二套画像。
5. 提交后只向调用方返回 `BrowserIdentity` 和内部 identity ID；日志只允许 `profile_ref`。

画像版本升级不走普通 ensure：必须使用单独的 `rotate_account_protocol_identity(account_id, expected_old_version)`，在同一账号行锁事务里退休旧行、插入新行，并保留旧行供历史 context 关联。

设备字段使用域分离的确定性派生，禁止用 email/account ID 作为 seed，也禁止用一次 hash 连续切片承载所有字段：

```text
material(label) = HMAC-SHA256(
    key=profile_key_bytes,
    message="turb-account-auth:v<profile_version>:<label>"
)

device_id              <- material("device-id") 的 128 bit，按 UUID 格式化
os_candidate_index     <- material("os")
ua_candidate_index     <- material("ua")
screen_candidate_index <- material("screen")
hardware_candidates    <- 分别使用 cpu/memory/heap 标签
profile_ref            <- material("profile-ref") 的前 12 个 hex，仅用于展示
```

候选列表属于 `profile_version` 的代码常量；版本内只能追加兼容项，不能重排，否则同一 key 会漂移。代理 Geo 派生的语言、时区和出口字段不写入长期 `browser_profile`，由每次 route context 记录真实观测值。

### 6.3 每次 run 私有上下文表

新增 `account_auth_run_contexts`：

```sql
CREATE TABLE account_auth_run_contexts (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    operation_run_id BIGINT NOT NULL REFERENCES operation_runs(id) ON DELETE CASCADE,
    context_no INTEGER NOT NULL,
    parent_context_id BIGINT REFERENCES account_auth_run_contexts(id) ON DELETE SET NULL,
    context_schema_version INTEGER NOT NULL DEFAULT 1,
    account_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    driver TEXT NOT NULL,
    auth_method TEXT,
    route_attempt_no INTEGER,
    session_no INTEGER NOT NULL,
    protocol_identity_id BIGINT REFERENCES account_protocol_identities(id) ON DELETE SET NULL,
    protocol_profile_ref TEXT,
    device_id TEXT,
    session_identifiers JSONB NOT NULL DEFAULT '{}'::jsonb,
    proxy_lease_id TEXT,
    proxy_url TEXT,
    proxy_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    roxy_profile_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    result_code TEXT,
    cleanup_status TEXT NOT NULL DEFAULT 'pending',
    cleanup_error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    UNIQUE(operation_run_id, context_no)
);
```

一行表示一个实际 driver session，而不是一个完整 operation run。首次 Protocol session 的 `parent_context_id` 为空；换线路、新建邮箱 fallback session 和 Roxy fallback 各新增一行，并用 `parent_context_id` 指向触发它的上一条 context。`context_no` 在同一 run 内单调递增，`session_no` 表示认证会话序号，`route_attempt_no` 表示线路尝试序号；这些值由单个 run 编排器的有界状态对象显式分配。统一任务中心已经保证同一 active run 只有一个 worker，恢复会创建新 run；不得通过无锁 `MAX(context_no)+1` 生成编号。

`operation_run_id` 明确关联统一任务中心并随 run 删除。`account_id` 允许为空，因为注册 Profile/代理在账号行创建前已经存在；注册成功后通过 operation run 的确认结果回填 account ID，注册失败则保持为空。`account_id` 首版不设级联外键，因为账号删除/归档语义尚未统一。identity 和 context 的账号删除策略要等账号删除功能做显式事务设计，不能靠数据库隐式级联猜测。

`session_identifiers` 允许：

```text
sentinel_sid
oai_session_id
auth_session_logging_id
datadog_trace_id
datadog_parent_id
react_listening_key
react_container_key
react_resources_key
roxy_debugger_address
roxy_webdriver_url
roxy_ws_endpoint
roxy_browser_instance_id
```

`RoxyOpenResult.raw` 不允许整包入库：先用显式 allowlist 提取上述原始连接/会话标识及 `profile_id`，未知字段默认丢弃。这里的“允许保存原始标识”不等于允许保存不透明响应，因为 Roxy 后续版本可能在 raw 中加入 API 凭据或其他未分类数据。

代理规则：

- 1024Proxy 已经把完整 `proxy_url` 保存到 `proxy_leases`；run context 优先保存 `proxy_lease_id`，不重复复制。
- 静态池、调用方显式代理没有 lease 行时，允许把完整 `proxy_url` 保存到私有表。
- `proxy_context` 保存 provider、mode、region、endpoint、exit IP、租约时间和轮换序号。
- 保存的代理凭据只用于回溯当次请求；租约过期或静态凭据失效后，后续任务不得从 run context 自动复用，仍必须通过当前代理 Provider/租约流程重新获取。
- 任务事件仍只使用 `mask_proxy_url()` 的结果。

### 6.4 保存周期和访问边界

私有上下文新增配置：

```text
ACCOUNT_AUTH_RAW_CONTEXT_ENABLED=True
ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS=30
ACCOUNT_AUTH_PROFILE_MODE=current         # current / account_stable
ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=True
```

首版建议 run context 保留 30 天，稳定 identity 随账号长期保留。设置 `RETENTION_DAYS=0` 才表示不自动清理。

`ACCOUNT_AUTH_RAW_CONTEXT_ENABLED=False` 时，identity、登录、查活和 fallback 行为完全不变，只跳过 P1/P2 原始 run context 写入并继续保存 P0 安全摘要。该开关不能被实现成“关闭后不用稳定 identity”。

`ACCOUNT_AUTH_PROFILE_MODE=current` 时严格保持现状：不创建、不读取稳定 identity，向 `BrowserSession` 传 `identity=None`，每个 session 随机设备层；`account_stable` 时才懒调用 ensure。两个模式都可以独立保存安全摘要和 raw run context。

私有表不接入现有 `get_task()`、账号列表、兼容导出和任务详情 API。若以后增加“查看原始上下文”，必须是独立 secret endpoint、显式点击、单账号/单 run 查询，并记录访问审计；本次不实现普通 UI 展示。

首版“受限”主要是应用边界：只有 `core/storage/account_auth.py` 可以读写，普通 repository、task serializer 和 export 没有查询入口。当前服务共用一个 PostgreSQL runtime role，因此它不能抵御拿到数据库凭据的管理员或进程内任意 SQL；不能把它宣传成数据库级加密隔离。若要硬隔离，需要后续引入独立 private schema/reader role、密钥和审计服务，并同步改备份恢复。

### 6.5 静态数据、导出、备份和清理

现有本地 PostgreSQL 已经保存账号密码、TOTP、AT 和部分完整代理 URL。首版 private context 延续同一数据库信任边界，不单独做一套不完整的字段级加密；如果以后做静态加密，必须把现有 P2/P3 一并纳入密钥轮换、备份恢复和审计方案，不能只加密新表造成“看似安全”。

- 应用层账号导出、兼容 JSON/TXT、任务导出和诊断包默认永远排除两个私有表。
- `pg_dump`、物理快照等数据库级备份会包含私有表，必须按账号凭据级别限制访问、加密保存并遵循同等保留策略。
- `cleanup_expired_auth_contexts(limit=500)` 由存储维护任务分批删除 `expires_at < now()` 的 context；启动时补跑一次，运行中每日执行，单批失败可重试且不影响认证任务。
- `RETENTION_DAYS=0` 只关闭自动清理，不代表禁止手工按明确 run/account 查询和逐行清理；不得使用 shell 递归删除代替数据库清理。
- identity 长期保留；画像版本迁移通过新增/退休记录或显式版本升级完成，不随 run context 保留期一起清除。

### 6.6 旧数据迁移边界

- 不批量为全部账号生成 identity；只有 `PROFILE_MODE=account_stable` 且账号实际进入有 AT 的查活或重新认证时才懒创建。
- 现有注册 `device_id` 保留原语义，不复制成 Protocol device ID，也不被查活/刷新覆盖。
- 历史 `profile_id/open_result` 不自动搬进 run context，因为缺少可靠 `operation_run_id`、生命周期和代理归属；继续保留原数据，但普通 repository/API 立即按敏感字段白名单排除。
- 新版本启用后停止把新的 Roxy `open_result` 和原始 Profile 信息写入 `registered_accounts.data`；未来只写 private context。
- 新注册任务在 Roxy Profile 创建后立即建立 `action=registration` 的 context；当时账号尚未落库允许 `account_id=NULL`，注册成功原子收口时回填，失败时仍可通过 `operation_run_id` 诊断。
- 不从历史邮箱、代理或注册 device ID 推导 profile key，避免把不完整旧状态伪装成稳定身份。

### 6.7 新旧实现与浏览器兜底配置

#### 6.7.1 配置键

```text
ACCOUNT_AUTH_V2_ENABLED=False

ACCOUNT_LIVE_CHECK_DRIVER=browser_current
ACCOUNT_TOKEN_REFRESH_DRIVER=browser_current
ACCOUNT_PASSWORD_LOGIN_DRIVER=browser_current
ACCOUNT_PASSWORD_SETUP_DRIVER=browser_current
ACCOUNT_EMAIL_OTP_DRIVER=browser_current
ACCOUNT_TOTP_LOGIN_DRIVER=browser_current
ACCOUNT_2FA_SETUP_DRIVER=browser_current

ACCOUNT_BROWSER_FALLBACK_ENABLED=True
ACCOUNT_TOKEN_REFRESH_BROWSER_FALLBACK_ENABLED=True
ACCOUNT_PASSWORD_LOGIN_BROWSER_FALLBACK_ENABLED=True
ACCOUNT_PASSWORD_SETUP_BROWSER_FALLBACK_ENABLED=True
ACCOUNT_EMAIL_OTP_BROWSER_FALLBACK_ENABLED=True
ACCOUNT_TOTP_BROWSER_FALLBACK_ENABLED=True
ACCOUNT_2FA_SETUP_BROWSER_FALLBACK_ENABLED=True
```

所有 `*_DRIVER` 只允许该步骤能力矩阵声明过的值：

- `browser_current`：默认主路径，原样调用当前稳定 Roxy/Selenium 能力。
- `protocol_current`：原样调用该步骤当前已经稳定存在的协议能力；没有现有协议能力的步骤不允许配置此值。
- `protocol_v2`：调用新建类型化协议接口；不允许通过修改 current 函数内部实现达到“表面双路由”。

`ACCOUNT_AUTH_V2_ENABLED=False` 只覆盖请求值为 `protocol_v2` 的步骤：有效驱动临时变为 `browser_current`，保存值保留；`browser_current/protocol_current` 不受影响。该开关只影响新任务；已经开始的任务继续使用入队时冻结的策略，防止执行中途切实现。

所有步骤默认 `browser_current`。完成协议真实灰度后只把相应协议值开放给用户选择，系统不自动修改默认主路径。用户选择 Protocol 时，正常成功不会启动 Roxy；只有明确命中 fallback 条件才创建浏览器环境。

#### 6.7.2 分步骤行为矩阵

| 步骤/动作 | `browser_current` | `protocol_current` | `protocol_v2` |
| --- | --- | --- | --- |
| 普通查活 | 浏览器上下文验证已有 AT，不登录、不发 OTP | 现有旧 AT + `check_account_plan()` 探测 | 稳定 identity 的旧 AT probe |
| Token 刷新编排 | 现有 Roxy 完整登录链 | 现有 `check_account_liveness()` 邮箱 OTP | 新密码/MFA/reauth/email OTP 状态机 |
| 密码登录 | 当前 Roxy/Codex 密码能力 | 暂无，不提供该值 | `password/verify` + 类型化响应分类 |
| 密码设置 | 当前 Roxy 账号配置/注册后补密码能力 | 暂无，不提供该值 | set/create-password 真实接口验证后才开放 |
| 邮箱 OTP | 当前 Roxy OTP 能力 | 当前 Protocol 邮箱 OTP | v2 send/validate parser、旧码和 send 确认边界 |
| TOTP 登录 | 当前 Roxy/Codex TOTP 能力 | 暂无独立 current adapter | `mfa/issue_challenge` + `mfa/verify` |
| 2FA 设置 | 当前 Roxy UI 流程 | 当前 enroll/activate | v2 类型化 enroll/activate 和检查点 |

步骤选 `browser_current` 时浏览器就是主路径，不受 fallback 总开关影响。步骤选 `protocol_current/protocol_v2` 时，browser fallback 才由总开关和分步骤开关控制。

密码登录和密码设置必须使用两个独立 selector、独立 checkpoint 和独立结果枚举。当前已经验证的是登录 `password/verify`；未验证 set/create-password 前，`ACCOUNT_PASSWORD_SETUP_DRIVER=protocol_v2` 必须被能力校验拒绝，不能因为登录接口可用就假设设置接口也可用。

`CODEX_OAUTH_DRIVER`、注册驱动和当前 `LIVE_CHECK_ROXY_FALLBACK_ENABLED` 继续保留原语义。本配置首版只给新账号认证路由使用；注册密码仍由现有注册驱动控制。若后续让 Codex/注册接入 v2，必须增加显式适配配置，不能悄悄改变已有 driver 键含义。

#### 6.7.3 任务策略快照

任务入队时解析成不含敏感值的 `AuthExecutionPolicy`：

```python
@dataclass(frozen=True)
class AuthExecutionPolicy:
    config_revision: str
    v2_enabled: bool
    requested_drivers: dict[str, str]
    effective_drivers: dict[str, str]
    browser_fallback_enabled: bool
    browser_fallback_steps: frozenset[str]
    forced_browser_reason: str | None
```

快照只允许进入 operation run 的受控配置摘要，不得包含密码、OTP、Token、邮箱或代理。任务事件可显示 `driver=browser_current/protocol_current/protocol_v2` 和 fallback 原因，但不展开整份环境配置。

#### 6.7.4 会话亲和与组合校验

逐步骤可配是任务规划输入，不允许执行时半路拼接两个会话：

1. Token 刷新选择 `browser_current` 时，整条认证链由浏览器完成，不再逐步切到 Protocol。
2. Token 刷新选择 `protocol_current/protocol_v2` 时，先根据本地凭据能力预测密码/TOTP/email OTP 链；若某个预计必需步骤选择浏览器，必须在任何远端凭据请求前把整条任务交给 `browser_current`，并记录 `forced_browser_reason=step_selected_browser`。
3. Protocol 已提交密码、邮箱 OTP 或 TOTP 后，不允许把 Cookie、factor ID、challenge 或半成品状态注入 Roxy。
4. 远端临时出现未预计步骤时，只有对应 browser fallback 开启、错误属于 allowlist、没有 `request_unknown`、且 fallback budget 未使用，才允许创建一个全新的浏览器 run，从登录起点完整执行一次。
5. 明确密码错误只允许在 `ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=True` 且相应浏览器开关开启时，启动一次不提交密码的 passwordless 邮箱 OTP 浏览器 fallback；找不到严格入口就停止。OTP/TOTP 错误、账号停用、限流和凭据请求结果未知都不触发自动跨驱动重试。
6. 非法枚举、互相冲突的旧/新配置或无法覆盖预期链路的组合，在任务开始前返回 `configuration_invalid`；不能运行一半再决定。

浏览器环境缺失、Roxy Core 未安装或容量不足时返回 `browser_fallback_unavailable`，保留原 Protocol 结果。浏览器不可用不得阻断 Protocol 成功路径，也不得让服务进程因可选依赖缺失而启动失败。

#### 6.7.5 WebUI 配置编辑器

WebUI 新增“账号认证实现与兜底”分组，按以下顺序展示：

1. 全局启用账号认证 v2。
2. 普通查活、刷新 AT、密码登录、密码设置、邮箱 OTP、TOTP 登录、2FA 设置的实现选择。
3. 浏览器兜底总开关和各步骤兜底开关。
4. Protocol 账号画像、raw context 和保留天数。

每个步骤按能力显示“浏览器（默认）”“现有协议”“Protocol v2”。浏览器是可直接选择的主驱动，不只出现在 fallback 开关中。全局 v2 关闭时，页面保留分步骤的 v2 保存值，但以只读提示展示“本次有效值：浏览器”；不得在前端偷偷重写用户配置。

配置 API 返回 `requested`、`effective`、`overridden_by_global_switch`、browser capability 和冲突告警，不返回 `.env` 原文。保存时后端先完成枚举、旧键冲突和依赖校验，再原子更新；非法组合整包拒绝，不能只保存一半字段。

## 7. 普通查活逐步流程

普通查活不得复用下面的重新认证状态机。它按配置选择浏览器或协议做“已有 AT probe”，但任一驱动都不读取密码/TOTP、不发送邮箱 OTP、不获取新 AT。

| 步骤 | 动作 | 成功证据 | 失败处理 |
| --- | --- | --- | --- |
| L0 | claim 同账号账号操作资源 | claim 成功 | busy，任务不启动 |
| L1 | 读取账号和旧 AT | 有账号、有 AT | 无 AT 直接失败，不领线路、不建 identity |
| L2 | 读取本次冻结的 `ACCOUNT_LIVE_CHECK_DRIVER` | browser_current / protocol_current / protocol_v2 | 非法或能力不可用在远端动作前停止 |
| L3 | 领取账号地区线路 | route/lease 成功 | 网络类失败按当前规则 |
| L4-P | 协议驱动按 profile mode 创建 `BrowserSession`；raw context 开启时新增 context 行 | current 为随机 identity，v2 可用稳定 identity；会话层全新 | 初始化失败释放线路；context 写入失败记 warning |
| L4-B | 浏览器驱动创建一次临时 Roxy Profile，只在页面上下文发起携带旧 AT 的探测请求 | Profile 创建成功，未进入 auth/login 页面 | Profile 不可用即返回该驱动失败，不自动切协议 |
| L5-P | 协议调用 `check_account_plan(AT, session=session)` | HTTP 成功且账号可用 | 网络类最多 4 个 route attempt；401 不登录 |
| L5-B | 浏览器通过受控 fetch/CDP 调同一 AT probe 接口 | HTTP 成功且账号可用；未创建登录 Session | 401/403 按 AT probe 分类；禁止打开登录页、发 OTP 或调用 NextAuth |
| L6 | 保存查活结果和独立安全摘要 | 单账号行级更新成功 | 写回失败不伪报任务成功 |
| L7 | 收口当前 private run context | 保存完成时间、status、result code | 诊断存储失败记 warning，不改变远端查活事实 |
| L8 | 释放线路和 claim | 资源终态可核对 | finally 执行 |

协议普通查活的 `BrowserSession` 必须由调用方创建并传入 `check_account_plan()`，避免该函数内部偷偷再建一个随机 session。浏览器普通查活只能把 AT 临时交给单次探测请求，不能写入持久 Cookie/localStorage，不能复用账号密码做登录；任务结束关闭/软删除 Profile。

普通查活不做自动跨驱动 fallback：用户选浏览器就只返回浏览器 probe 结果，选协议就只返回协议 probe 结果。这样页面展示和故障判断能明确反映用户配置，不会协议失败后悄悄改用浏览器。

## 8. Protocol 刷新 AT 总状态机

```text
START
  -> CLAIM_ACCOUNT
  -> LOAD_CREDENTIALS
  -> ACQUIRE_ROUTE
  -> RESOLVE_PROTOCOL_IDENTITY_BY_MODE
  -> CREATE_SESSION
  -> PREWARM_NEXTAUTH
  -> FOLLOW_AUTHORIZE
  -> CLASSIFY_REMOTE_STATE

CLASSIFY_REMOTE_STATE
  +-- PASSWORD_LOGIN + 有密码 -> PASSWORD_VERIFY
  +-- PASSWORD_LOGIN + 无密码 -> EMAIL_OTP_SWITCH
  +-- EMAIL_OTP_SEND/INPUT ----> EMAIL_OTP
  +-- MFA_TOTP ----------------> MFA_TOTP
  +-- CALLBACK/AUTHENTICATED --> FETCH_SESSION
  +-- PROFILE_CREATE ----------> STOP_NOT_EXISTING_ACCOUNT
  +-- ACCOUNT_UNUSABLE --------> DEACTIVATED
  +-- UNKNOWN -----------------> CONTROLLED_ROXY_FALLBACK

PASSWORD_VERIFY
  +-- CALLBACK ----------------> FETCH_SESSION
  +-- MFA_TOTP ----------------> MFA_TOTP
  +-- EMAIL_OTP ---------------> EMAIL_OTP
  +-- REJECTED ----------------> NEW_SESSION_EMAIL_FALLBACK
  +-- RESULT_UNKNOWN ----------> CONFIRM_ONCE -> NEW_SESSION_EMAIL_FALLBACK

EMAIL_OTP
  +-- CALLBACK/AUTHENTICATED --> FETCH_SESSION
  +-- MFA_TOTP ----------------> MFA_TOTP

MFA_TOTP
  +-- CALLBACK/AUTHENTICATED --> FETCH_SESSION

FETCH_SESSION -> VALIDATE_NEW_AT -> ATOMIC_PERSIST -> SUCCESS
```

下一节对每个状态逐项定义动作、证据和恢复方式。

## 9. Protocol 每一步实现细节

### 9.1 P0：账号、任务和凭据预检

输入必须是 `account_id`，email 只作为快照和远端 login hint，不能作为数据库主定位键。

预检顺序：

1. 确认任务类型是 `token_refresh`。
2. 取得账号资源 claim；与 Codex 登录、密码补充和 2FA 设置使用同一 `openai_interactive` 资源族。
3. 单行读取账号，不加载全账号表。
4. 明确废号直接终止。
5. 通过公共 `AccountAuthCredentialsResolver` 读取：
   - OpenAI 密码：`account_password -> login_password -> registration_password`；
   - TOTP secret 和 `totp_setup_pending`；
   - 旧 AT；
   - `email_source` 和邮箱 Provider 能力。
6. 邮箱池密码绝不参与 OpenAI 密码候选。
7. 只记录 `password_present/totp_present/email_otp_available` 布尔值，不记录原值。

### 9.2 P1：线路和 identity

1. 使用 `acquire_account_proxy(account_id=..., purpose="token-refresh")`。
2. 默认地区沿用注册地区；拿不到地区时停止，不随机换国家。
3. 调用 `resolve_account_protocol_identity(account_id, mode)`；`current` 返回 None，`account_stable` 才委托 `ensure_account_protocol_identity()`。
4. 创建 `BrowserSession(proxy=route.proxy_url, identity=identity_or_none)`。
5. raw context 开启时立即写入 private run context：identity 引用、原始 session IDs、lease ID/代理上下文；关闭时只生成安全摘要，不改变认证链。
6. 线路轮换时：
   - 复用同一 Protocol identity；
   - 创建新 BrowserSession 和新会话标识；
   - 每条线路建立独立 route attempt；
   - 不在同一 session 中间替换代理。

### 9.3 P2：NextAuth 预热和 authorize

顺序保持当前已验证链：

```text
chatgpt.com 页面/匿名态预热
  -> /api/auth/providers
  -> /api/auth/csrf
  -> /api/auth/signin/openai
  -> auth.openai.com authorize
```

要求：

- `ext-oai-did`、Cookie `oai-did`、请求头 `oai-device-id` 和 Sentinel body 使用 identity 的同一个 device ID。
- `auth_session_logging_id` 使用本次 session 的新值。
- `signin_openai()` 返回 URL 后先做 host allowlist；只允许 `auth.openai.com`。
- authorize 最终状态不能只看 HTTP 200，要解析最终 URL、结构化响应和 Cookie 状态。
- 网络失败发生在提交任何凭据之前时，可以换线路；最多 4 个 route attempt。
- 一旦提交密码/OTP/TOTP，线路切换规则按第 14 节执行。

### 9.4 P3：远端状态分类器

新增纯函数 `classify_protocol_auth_response()`，输入是白名单化的 HTTP 元数据：

```text
status_code
final_url path
JSON page.type
JSON page.payload.factor_id/factors
continue_url path
结构化 error.code/type
是否已经取得 Session/AT
```

优先级：

1. 明确账号停用/删除；
2. 已取得 Session/AT；
3. callback；
4. MFA TOTP；
5. 登录密码；
6. 邮箱 OTP send/input；
7. 新账号资料/创建密码；
8. 风控/限流；
9. unknown。

不能把整个 URL 查询串、响应正文或 challenge payload放入事件。测试 fixture 可以保存脱敏后的结构化片段。

### 9.5 P4：什么时候才提交密码

必须同时满足：

1. 当前响应明确分类为 `PASSWORD_LOGIN`；
2. 本地存在保存的 OpenAI 账号密码；
3. 本次 run 尚未提交过密码；
4. Sentinel password flow 已成功取得要求的 token；
5. 当前 session/route 未被取消或失效。

不能因为“本地有密码”就不看远端状态直接调用 password verify。如果远端默认直接进入邮箱 OTP，就尊重远端路径，不强行切回密码。

Protocol 请求：

```text
POST https://auth.openai.com/api/accounts/password/verify
flow=password_verify
body={password: <saved account password>}
```

请求前记录 `password_submit_started`；请求 body 交给传输层后记录 `action_dispatched=True`。日志只写长度和凭据来源字段名，不写密码或 hash。

### 9.6 P5：密码提交后的完整分支

| 证据 | 分类 | 后续动作 | 密码状态 |
| --- | --- | --- | --- |
| callback URL 或已取得 Session | `password_success` | callback/session | `verified` |
| `page.type=mfa_challenge` 或 TOTP factor | `password_mfa` | issue + verify TOTP | TOTP 成功后 `verified` |
| `email_otp_send` / `email_verification` | `password_email_otp` | 触发/等待邮箱 OTP | 最终成功后 `verified` |
| 结构化 incorrect password | `password_rejected` | 新 session 邮箱 fallback | `rejected` |
| 429/明确限流 | `password_rate_limited` | 不换线、不重交密码、不自动 fallback | `unknown` |
| body 已发送后连接断开/超时 | `password_result_unknown` | 先被动确认一次，再邮箱 fallback | `unknown` |
| 5xx 且可证明远端未接收 body | `network_before_submit` | 可新 session/线路重走，但密码总提交次数仍受限 | `unknown` |
| 未知 page type/无 continue URL | `password_response_unknown` | 不猜成功；受控 Roxy 观察或邮箱 fallback | `unknown` |

“被动确认一次”只允许：

- 在原 session 调一次 `fetch_session()`；
- 检查响应已有的 callback/continue URL；
- 不重新提交密码，不重新发送邮箱 OTP。

确认后仍未知，可以创建新 session 走邮箱 fallback，但任务必须保留 `password_result_unknown` warning。

### 9.7 P6：密码不存在或密码页没识别到

分为四种情况：

| 情况 | 动作 |
| --- | --- |
| 本地无密码，远端直接进入邮箱 OTP | 正常走邮箱 OTP，不记密码错误 |
| 本地无密码，远端明确是 password login | 调用协议 passwordless/email OTP 切换；不生成密码 |
| 本地有密码，但远端页面/响应没识别为 password | 不盲调 password verify；继续分类、等待受控 hydration 或进 Roxy 观察 |
| 远端是 password login，但找不到 passwordless 能力 | 返回 `password_missing_no_email_fallback`，Roxy 只做一次页面确认，不点击通用按钮 |

Protocol 没有“点击按钮”，它需要根据服务端返回的 `continue_url/page.type` 调用对应 email OTP send 路径。不能把浏览器按钮选择器直接映射成猜测 URL。

### 9.8 P7：邮箱 OTP fallback 的启动

密码被拒绝或结果未知后：

1. 关闭原 Protocol session；保存其 private context 终态。
2. 保留账号级 Protocol identity。
3. 新建 session IDs 和 Cookie jar。
4. 重新执行 NextAuth/authorize，不复用密码验证后的 Cookie。
5. 如果新会话直接进入 OTP input，记录 `otp_request_origin=authorize_auto`。
6. 如果响应是 `email_otp_send`：
   - 在真正发起 send 前记录 `otp_after_ts`；
   - 跟随 allowlist 内的 send URL一次；
   - 以 HTTP/页面状态确认 send 是否已受理；
   - 不能只因为函数返回就宣称邮件已发出。
7. 如果仍停在 password login，调用显式 passwordless OTP 协议路径一次。
8. 仍无法进入 OTP 时，才考虑 Roxy fallback。

同一刷新 run 最多启动一次邮箱 fallback；OTP 内部的“重发”属于同一 fallback，不重新开始整个认证链。

### 9.9 P8：邮箱 OTP 获取和提交

每次 OTP attempt 必须记录：

```text
request_started_at
request_confirmed_at
mail_after_ts
mail_received_at
submit_started_at
remote_response_received
outcome
```

不记录 OTP 原值。

流程：

1. 使用账号保存的 `email_source` 选择 Provider。
2. `wait_for_otp(email, after_ts=mail_after_ts)`；拒绝本 run 已经提交过的 code。
3. 只有拿到新 code 才提交。
4. 成功响应可能进入 callback，也可能再进入 MFA TOTP。
5. 明确 invalid/expired 才重发；最多 2 次重发、总计最多 3 个不同 code。
6. 提交后网络结果未知时，不立即重交同一个 code；先检查 Session/continue 状态。
7. 邮箱服务不可用和“服务端没有发信”是两个错误码，不能合并。
8. 账号停用文案优先于 OTP invalid。

### 9.10 P9：TOTP MFA

只在远端明确要求 TOTP factor 后执行：

1. 从 `page.payload.factor_id`、factor 列表或 allowlist URL path 提取 factor ID。
2. factor 列表存在时只选 `type=totp/authenticator`；不默认取第一个。
3. 本地无 secret：`mfa_secret_missing`，停止；邮箱 OTP 不能绕过已要求的 MFA。
4. `totp_setup_pending=true` 可以尝试；成功后清除 pending。
5. 调用 `mfa/issue_challenge`；不携带 password verify 的 Sentinel headers。
6. 生成 code 前检查 30 秒窗口；剩余不足 6 秒时等下一窗口。
7. 调用 `mfa/verify`，不记录 code。
8. 明确 invalid/expired 时最多跨窗口再试一次。
9. body 已发送但响应未知时，不在同一窗口重复；先确认 Session，下一窗口是否重试取决于远端明确状态。
10. 成功后只跟随返回的 allowlist callback/continue URL。

### 9.11 P10：callback、Session 和新 AT

成功必须同时满足：

1. callback/authorize 链完成；
2. `fetch_session()` 返回结构化 Session；
3. `accessToken` 非空；
4. Token claims 可解析，或在线校验确认可用；
5. Session 用户与目标账号没有明显冲突；
6. 没有落入 `about-you/create-account/password` 新账号流程。

如果登录后进入资料页，返回 `existing_account_incomplete`，绝不在刷新任务里补资料或创建账号。

### 9.12 P11：原子写回

账号事实来源在同一事务内完成：

- 新 AT 和 Token metadata；
- live/auth 状态；
- `last_auth_method`；
- `password_auth_status`；
- fallback warning；
- 最近认证安全摘要；

private run context 在账号事务前后做 best-effort 收口，但不作为新 AT 原子提交的前置条件：私有诊断写入失败必须产生 warning，不能把已经确认的新 AT 回滚成“远端认证失败”。反过来，账号事务失败时不能把任务报成功，即使 context 已经记录了远端成功。

失败时保留旧 AT、密码、TOTP、注册 device ID 和最近一次成功认证摘要。普通刷新产生的 Protocol device ID 不再覆盖注册 `device_id`。

## 10. Roxy 浏览器认证状态机

### 10.1 为什么必须抽公共组件

当前最完整的浏览器登录逻辑在 `core/roxy_codex_oauth.py`，注册又在 `core/registration/roxy.py` 维护相似选择器，`core/roxy_liveness.py` 只用了简化 OTP 路径。这些 current 实现首版全部保留，`browser_current` 继续直接调用它们作为默认主路径；新增公共包服务 `protocol_v2` 的完整浏览器 fallback、浏览器只读 AT probe 和未来新调用方，不在本轮反向替换三个稳定入口。新功能不得继续复制第四套状态机。

新增公共包：

```text
core/browser_auth/
  contracts.py       页面快照、状态、动作结果
  snapshot.py        只读 DOM 快照和敏感值清理
  classify.py        URL + DOM + Session 状态分类
  selectors.py       严格控件查找，不执行流程
  actions.py         提交邮箱/密码/TOTP/OTP、选择账号
  flow.py            有界状态机
  diagnostics.py     红acted fixture 和未知页面证据
```

新写的注册、Codex 或账号认证代码只能调用公开函数，不能跨模块导入 `_private_helper`。既有 current 代码中的私有调用先由 characterization tests 冻结，不以“公共化”为由在本轮大改；后续迁移必须逐入口单独灰度。

### 10.2 浏览器页面识别优先级

每轮读取同一份 `BrowserAuthSnapshot`，按以下顺序分类：

1. 明确账号停用/删除；
2. 已取得目标 Session/AT；
3. callback/consent/workspace 等已越过登录挑战的页面；
4. TOTP 控件；
5. 登录密码控件；
6. 邮箱 OTP 控件；
7. 目标邮箱账号选择器；
8. 邮箱输入页；
9. 新账号创建密码/资料页；
10. 手机验证页；
11. 外部 IdP；
12. Cloudflare/Turnstile/risk challenge；
13. `login?email` 空壳/SPA transient；
14. unknown。

TOTP 必须在 password 之前判断，因为 OpenAI 可能保留 `/log-in/password` URL，但 DOM 已替换成验证码输入框。

### 10.3 密码页识别

`PASSWORD_LOGIN` 需要以下证据之一：

- URL path 明确 `/log-in/password`，并且页面不是 OTP/TOTP 控件；
- 可见 `input[type=password]` 或 `autocomplete=current-password`，加上 login form/action/intent；
- DOM form action 明确 login/signin。

以下情况不能判为登录密码页：

- 只有 stale URL，没有 password input；
- 有 code/OTP input 且没有 password input；
- `autocomplete=new-password` 或 create-account/signup form；
- 页面仍在 hydration，没有稳定控件。

页面刚跳转时允许 2 秒 hydration 观察；快照连续两次一致后才执行动作。

### 10.4 密码控件识别和提交

密码 input 与 submitter 必须来自同一个 form。submitter 优先级：

1. `name=intent,value=validate`；
2. `data-dd-action-name=continue`；
3. 同 form 内唯一可用 `type=submit`。

如果同 form 有多个无法区分的 submitter，返回 `ambiguous_password_submitter`，不得点击离 input 最近的任意按钮。

提交规则：

- 密码只输入一次、提交一次；
- 优先 `form.requestSubmit(submitter)`，失败才对 password input 发送 Enter；
- 提交后使用独立 25 秒 settle budget；
- 看到明确错误区域/`aria-invalid` 才标记 rejected；
- 页面未变化且无错误是 `password_result_unknown`，不是 rejected；
- 诊断快照必须把 input value 替换成 `<redacted:password>`。

### 10.5 本地没有密码怎么办

如果远端是登录密码页：

1. 查找严格 passwordless/OTP 入口；
2. 找到唯一候选后点击；
3. 没有直接 OTP 入口、但存在唯一且明确的“Try another way/其他方式”方法选择器时，只打开一次方法面板，再查找严格 email code 选项；
4. 等待 EMAIL_FORM、EMAIL_OTP_SEND、EMAIL_OTP_INPUT、登录态或明确错误；
5. 找不到按钮时调用一次浏览器 NextAuth fallback；
6. 再等待一次稳定状态；
7. 仍失败返回 `password_missing_no_email_entry`。

绝不生成新密码，也不点击“忘记密码”、创建账号或第三方登录。

### 10.6 邮箱 OTP fallback 按钮

允许的强属性：

```text
button/input[name=intent][value=passwordless_login_send_otp]
button/input[name=intent][value*=passwordless][value*=otp]
button/input[name=intent][value*=passwordless][value*=send_otp]
data-testid / data-dd-action-name 明确包含 passwordless + otp/code
```

允许的文本兜底仅限唯一候选：

```text
Use a one-time code / Continue with a one-time code
使用一次性验证码 / 使用一次性驗證碼
メールでコード / ワンタイムコード / 認証コード
일회용 코드
```

明确排除：

- Google、Apple、Microsoft、GitHub、SSO/SAML；
- Forgot/reset password；
- create account/signup；
- consent/authorize/allow；
- 页面任意全局 `Continue`。

点击后必须满足至少一个确认条件：

- URL/DOM 进入邮箱 OTP；
- 网络 hook 观察到 OTP send 请求被接受；
- 页面按钮进入 disabled/cooldown 且出现 OTP 控件。

点击本身不等于邮件已发送。30 秒内没有确认时，状态是 `otp_entry_click_unconfirmed`。

passwordless 入口之后允许出现三种中间态，不能假设“一点就发信”：

1. `EMAIL_FORM`：输入框为空时填目标邮箱；已有值必须与目标邮箱规范化后完全相同，否则停止。只提交同 form 的唯一 email submitter。
2. `EMAIL_OTP_SEND`：只点击 `intent`/`data-testid` 明确表示 send/resend code 的唯一控件一次；如果只有通用 Continue，返回 `otp_send_submitter_ambiguous`。
3. `EMAIL_OTP_INPUT`：说明 authorize 或前一步已自动发信，不再点 send；以首次确认进入该状态前的时间作为 `mail_after_ts`。

如果打开“其他方式”后同时出现 authenticator、passkey、SMS、email code，只选择明确的 email/one-time-code 项；不存在唯一邮箱项时安全停止。方法面板打开和 OTP 项点击分别计数，页面 refresh 不能重置计数。

### 10.7 `login?email` 空壳和没识别到窗口

处理顺序：

1. 收集 URL、可见 inputs、forms、buttons 技术属性和受控错误文本。
2. 观察 2 秒，排除 SPA hydration。
3. 若 URL 是 `/auth/login?email=...`、仍有邮箱 input 且没有 challenge input，调用一次当前浏览器 Cookie 上下文的 NextAuth fallback。
4. NextAuth 返回稳定 `otp/password/advanced` 状态时直接消费结果。
5. 8 秒后仍是同一空壳，补交一次同邮箱表单。
6. 仍未进入稳定状态，只允许一次页面 refresh；refresh 后重新快照，不重填凭据。
7. 最后仍 unknown：停止自动点击，保存脱敏 fixture，返回 `auth_page_unknown`。

“识别不到窗口”绝不能落到“随便点第一个 Continue”。

### 10.8 邮箱 OTP 输入与提交

支持：

- 单个 `autocomplete=one-time-code/name=code/inputmode=numeric/type=tel` 输入框；
- 六个分格 code 输入框；
- 页面 auto-submit；
- 同 form 唯一 Verify/Continue submitter。

收到 code 后如果输入框尚未出现，最多等 30 秒；期间若仍回到 password 页，可以再探测一次 passwordless 入口，但总点击次数不超过 2。

提交后分类：

- 离开 OTP 页、callback、Session、MFA、consent：accepted；
- 明确 invalid/expired/`aria-invalid`：invalid；
- 仍在 OTP 页且无错误：stuck/unknown；
- 账号停用：deactivated；
- 手机验证：`phone_required`，刷新 AT 首版停止，不自动接码；
- 新账号资料页：`existing_account_incomplete`，停止。

### 10.9 浏览器 TOTP 识别和提交

浏览器 `MFA_TOTP` 必须满足“存在 code input 且有 TOTP 上下文”，TOTP 上下文至少一个：

- URL path 含 allowlist 内的 `/mfa`、`/totp` 或 `/authenticator`；
- 页面技术属性或受控标题明确指向 authenticator app/two-factor authentication；
- 本 session 已提交密码，URL 仍是 stale `/log-in/password`，password input 已消失且出现 code input。

`email-verification` URL、带目标邮箱提示的 code 页或已经分类为 EMAIL_OTP 的页面优先排除，避免把邮件码填成 TOTP。

执行顺序：

1. 解析保存的 TOTP secret；缺失返回 `mfa_secret_missing`，不点击其他验证方式绕过 MFA。
2. 只接受同一 form 内唯一的 `autocomplete=one-time-code`、name/id 含 `totp/otp/code` 或 numeric/tel code input；多个无法归组时返回 ambiguous。
3. 距当前 30 秒窗口结束不足 6 秒时等待下一窗口，之后再生成 code。
4. 填入一次；如果页面 auto-submit，不再点击。
5. 需要提交时，只使用同 form 的唯一 submitter；文本 Verify/Continue 只能作为该 form 内唯一候选，不能全局搜索。
6. callback、Session、consent/workspace 表示 accepted；明确 invalid/expired/`aria-invalid` 才算 invalid。
7. 明确 invalid 时等待下一窗口最多再试一次；提交后页面无变化且无错误为 result unknown，不在同一窗口重交。
8. 全程不记录 secret、code、input value 或其前后缀。

### 10.10 邮箱 OTP 后再遇到 TOTP

邮箱 OTP 不是最终成功证据。离开邮箱 OTP 后必须重新执行完整状态分类：

- TOTP：使用保存 secret；
- callback/session：完成；
- account chooser：只选精确包含目标邮箱的候选；
- consent/workspace：只在当前目标动作允许时处理；
- password：不再次提交本 run 已失败/未知的密码，返回循环保护错误；
- unknown：保存 fixture，停止。

### 10.11 其他页面

| 页面 | token refresh 动作 |
| --- | --- |
| account chooser | 只点击精确目标邮箱；多个相同/无目标时停止 |
| create-account/password | 停止，防止查活创建账号 |
| about-you/profile | 停止，标记账号远端状态不完整 |
| phone verification | 首版停止，提示需要独立账号补全流程 |
| consent/workspace | 仅点击 allowlist 目标动作，不能全局 Continue |
| external IdP | 停止，不能跳入第三方登录 |
| Turnstile/CAPTCHA | 标记 `risk_challenge_required`；可保留可见窗口人工确认，不自动绕过 |
| auth error/logout | 结构化失败；必要时重新建立一次干净登录会话 |

### 10.12 Roxy Profile 和清理

- 每次 fallback 新建临时 Roxy Profile，并保存 raw profile ID 到 private run context。
- 使用账号当前 route，不能在 Roxy 内再随机选代理。
- 成功、失败、取消都在 `finally` 中 quit driver、关闭/软删除 Profile、释放 route。
- `ROXY_KEEP_BROWSER_OPEN=True` 只用于人工诊断；任务终态必须显示“等待人工关闭”，不能假装资源已释放。
- 进程崩溃依赖现有 `run/roxy_active_profiles.json` 孤儿清理；新设计不另建第二份 Profile 注册表。

## 11. fallback 决策表

| 当前结果 | 换线路 | 重交密码 | 邮箱 fallback | Roxy fallback | 最终状态 |
| --- | ---: | ---: | ---: | ---: | --- |
| 凭据提交前网络失败 | 最多 4 条 route | 尚未提交可继续 | 否 | 条件允许 | retry/failed |
| 密码明确错误 | 否 | 否 | 一次 | 仅 passwordless 邮箱 OTP；不得再提交密码 | success_with_warning/failed |
| 密码提交结果未知 | 否 | 否 | 一次 Protocol 邮箱链，密码状态 unknown | 自动 Roxy 禁止；只允许人工诊断观察 | success_with_warning/failed |
| 本地无密码 | 否 | 否 | 正常主路径 | Protocol 不兼容时允许 | success/failed |
| MFA 缺 secret | 否 | 否 | 不能绕过 MFA | 可确认页面，不生成 secret | attention_required |
| TOTP 明确错误 | 否 | 否 | 否 | 否 | failed |
| 邮箱 OTP 无效/过期 | 否 | 否 | 同链重发，最多 2 次 | 已提交 code 后禁止跨驱动 | success/failed |
| 邮箱服务不可用 | 否 | 否 | 否 | Roxy 也不能解决收件问题 | failed |
| Protocol page/response unknown | 否 | 否 | 未提交凭据时条件允许 | 凭据前可一次；凭据后仅人工诊断 | success/failed |
| 明确废号 | 否 | 否 | 否 | 否 | deactivated |
| profile/create-account | 否 | 否 | 否 | 否 | attention_required |
| CAPTCHA/risk challenge | 可换线仅限凭据前 | 否 | 否 | 可见窗口人工处理 | attention_required |

全局循环保护：

```text
password_submit_count <= 1
email_fallback_start_count <= 1
email_otp_code_submit_count <= 3
email_otp_resend_count <= 2
totp_submit_count <= 2
roxy_fallback_count <= 1
auth_method_chooser_open_count <= 1
email_otp_entry_click_count <= 2
page_refresh_count_per_state <= 1
email_form_resubmit_count <= 1
```

## 12. 超时和取消规范

每个阶段使用 monotonic deadline；fallback 共享总预算，不能每进入新 helper 就重新获得完整超时。

建议初始值：

| 阶段 | 单步预算 | 说明 |
| --- | ---: | --- |
| 线路获取/验证 | 60 秒/route | 最多 4 条 route |
| NextAuth 预热 | 45 秒 | 凭据前可换线 |
| authorize settle | 45 秒 | 直到稳定状态 |
| 密码提交后 settle | 25 秒 | 独立于页面识别预算 |
| passwordless 入口确认 | 30 秒 | 点击后必须确认 OTP 状态 |
| 等邮箱 OTP | 90 秒/封 | 总计最多 3 封 |
| OTP 页面渲染 | 30 秒 | 收到邮件后仍给 DOM 时间 |
| OTP 提交后 settle | 45 秒 | 区分 invalid/stuck/accepted |
| TOTP 提交后 settle | 25 秒 | 最多跨一个窗口 |
| Roxy 页面总登录 | 180 秒 | 内部动作共享 deadline |
| fetch Session | 120 秒 | 不重复触发凭据 |

每个循环和外部等待都要调用统一 cancellation check。取消后不开始新的密码、OTP、TOTP 或 fallback 动作；已经发出的远端请求只记录结果未知并进入清理。

### 12.1 统一资源收口顺序

所有入口使用同一个 `ExitStack`/资源作用域，不能依赖各 helper 自己“顺手释放”。终态和异常统一执行：

1. 设置 cancellation/closing 标志，禁止再开始密码、OTP、TOTP、send 或新 fallback。
2. 保存最后一份脱敏状态和每个 context 的领域结果；写入失败只追加诊断 warning。
3. 调用新增的 `BrowserSession.close()` 关闭 curl session；重复 close 必须幂等。
4. 若存在 Selenium，先 `driver.quit()`，再调用 Roxy close；默认随后软删除本次临时 Profile。
5. 释放本次取得的代理租约；不得从 private context 反向释放不属于本 run 的 lease。
6. 更新 context 的 `cleanup_status=complete`；某一步失败则写 `warning` 和稳定 `cleanup_error_code`，保留 raw resource ID 供孤儿清理。
7. 最后释放账号 resource claim，并让 TaskReporter 根据已确认业务结果收口；清理错误只加 warning，不覆盖已确认成功/失败。

`ROXY_KEEP_BROWSER_OPEN=True` 时 operation 不能进入普通终态：保持 `attention_required/waiting_manual_close`，Profile 和代理租约继续归该 run 所有；用户关闭或 watchdog 超时后才执行第 4-7 步。进程恢复扫描 `cleanup_status != complete` 的 context，与现有 Roxy active profile 注册表交叉核对，只清理能证明属于该 run 的资源。

## 13. 任务阶段、检查点和 UI

### 13.1 阶段

```text
network
protocol_identity
auth_prewarm
auth_route
login_password
password_result
email_fallback
email_otp_request
email_otp_wait
email_otp_submit
mfa_challenge
mfa_verify
oauth_callback
session
token
roxy_fallback
complete
```

普通查活只显示：

```text
network -> protocol_identity -> access_token -> complete
```

阶段必须由真实 `AuthStepResult` 投影。不能再出现“最终邮箱登录成功，所以 password 和 email_otp 都标成功”的推断。

### 13.2 密码 fallback 的 UI 语义

| 结果 | 任务终态 | 账号提示 |
| --- | --- | --- |
| 密码成功 | success | 密码已验证 |
| 密码错误，邮箱成功 | success | AT 已刷新；保存密码已失效，请核对/重设 |
| 密码结果未知，邮箱成功 | success | AT 已刷新；本次无法确认密码是否有效 |
| 密码错误，邮箱失败 | failed | 密码已失效，邮箱 fallback 也失败 |
| 无密码，邮箱成功 | success | 通过邮箱 OTP 刷新 |
| MFA 缺 secret | attention_required | 远端要求 Authenticator，但本地没有 secret |

`success_with_warning` 可作为领域结果；如果现有任务终态只接受 `success`，则任务仍为 success，同时在 `result_summary.warnings` 和账号字段保存 warning，不能新增一个未被统一任务中心识别的随意状态。

### 13.3 检查点

每次有远端副作用的动作都先写 started，再执行，再写 result：

```text
password_submit_started -> password_submit_dispatched -> password_result_*
email_otp_request_started -> email_otp_request_confirmed
email_otp_submit_started -> email_otp_result_*
mfa_issue_started -> mfa_issue_confirmed
mfa_verify_started -> mfa_result_*
token_persist_started -> token_persisted
```

进程恢复时：

- 不自动重放密码/OTP/TOTP；
- 已拿到并保存新 AT 的任务直接对账收口；
- `*_dispatched` 无 result 的任务标记 `request_unknown`；
- 用户重试创建新 run，继承账号结果，不覆盖旧 run 历史。

## 14. 代码文件实施方案

### 14.1 新增文件

| 文件 | 责任 |
| --- | --- |
| `config/account_auth.py` | 全局 v2、逐步骤实现、browser fallback、画像、raw context、预算和次数配置 |
| `core/account_auth/contracts.py` | enum/dataclass，不做 I/O |
| `core/account_auth/policy.py` | 配置解析、旧键兼容、组合校验、任务策略快照 |
| `core/account_auth/router.py` | 只按有效策略选择 browser_current / protocol_current / protocol_v2；不做网络请求 |
| `core/account_auth/browser_current_adapter.py` | 调用当前公开浏览器入口；不复制或重解释旧状态机 |
| `core/account_auth/protocol_current_adapter.py` | 调用当前公开协议入口；步骤无现有协议能力时不可选 |
| `core/account_auth/credentials.py` | 账号密码/TOTP/email source 兼容解析 |
| `core/account_auth/identity.py` | Protocol identity 生成和 BrowserIdentity |
| `core/account_auth/protocol_parser.py` | HTTP/JSON 状态分类纯函数 |
| `core/account_auth/protocol_v2.py` | password/MFA/email OTP/callback 原子协议动作 |
| `core/account_auth/service.py` | 单次认证编排、fallback 和循环保护 |
| `core/account_auth/browser_fallback.py` | Roxy 能力检测和一次完整 fallback run；不实现半路状态注入 |
| `core/browser_auth/contracts.py` | 浏览器快照和页面状态 |
| `core/browser_auth/snapshot.py` | 只读 DOM 快照和 redaction |
| `core/browser_auth/classify.py` | 浏览器状态分类纯函数 |
| `core/browser_auth/selectors.py` | 控件查找，无流程决策 |
| `core/browser_auth/actions.py` | 单次 UI 动作 |
| `core/browser_auth/flow.py` | 有界 Roxy 登录状态机 |
| `core/storage/account_auth.py` | identity/run context 私有存储命令 |

### 14.2 修改文件

| 文件 | 修改 |
| --- | --- |
| `core/session.py` | 接收可选 `BrowserIdentity`；设备层稳定、会话层始终随机；提供 private/safe 两种快照；新增幂等 `close()`/context manager |
| `core/chatgpt_plan.py` | 新增可选调用方 session；`protocol_current` 未传时保持现状，`protocol_v2` 查活显式传入稳定 identity session；浏览器查活从 Roxy 受控 context 发起同一旧 AT probe |
| `core/live_check_service.py` | 入队时冻结策略；按 browser_current/protocol_current/protocol_v2 路由；精确阶段投影和原子收口 |
| `core/account_liveness.py` | 当前稳定实现原样保留；只新增必要的公开 adapter 入口，不把内部逻辑替换成 v2 |
| `core/roxy_liveness.py` | 当前浏览器兜底原样保留；新 browser fallback 通过公开入口调用，不删除简化链 |
| `core/roxy_codex_oauth.py` | 保留现有 Codex 密码/TOTP/邮箱 OTP 和后续手机/consent/workspace 流程；本轮不强制迁移到公共 flow |
| `core/registration/roxy.py` | current 注册专属 create-password/profile 和登录恢复保留；本轮只旁路记录 registration context，不切换认证实现 |
| `core/account_export.py` | current 2FA 流程保留；只做敏感日志修正，v2 通过新 adapter 实现类型化 challenge |
| `core/operations/legacy_task_store.py` | 保持事件脱敏，不允许 private context 穿透 |
| `core/storage/operation.py` | 保持任务 API 白名单；不得把 private context ID/内容写入会被 `get_task()` 返回的 `data/result_summary` |
| `core/admin_repository.py` | 账号列表只读 safe summary 和布尔状态 |
| `webui/routes/accounts.py` | 不新增隐式登录入口；返回紧凑入队结果 |
| `webui/static/js/modern/accounts.js` | 分开展示查活摘要、认证方法和密码 warning |
| `webui/static/js/legacy/accounts.js` | 同等语义兼容展示 |

### 14.3 不允许的实现方式

- 不从 `core.roxy_codex_oauth`、`core.registration.roxy` 导入下划线私有函数。
- 不把新逻辑继续堆进已经很大的 `roxy.py` 或 `account_liveness.py`。
- 不删除、改名或静默改写 current/Roxy 公开入口；需要新行为时新增 v2 文件和显式 router 分支。
- 不因为某个 Protocol 灰度成功就移除浏览器依赖、配置、能力检测或测试。
- 不在已提交凭据后把 Protocol 中间状态交给 Roxy 继续下一步。
- 不按错误字符串包含“password/mfa”决定业务状态。
- 不复制完整远端响应、DOM body 或 Cookie 到任务事件。
- 不通过加载全部账号再整体保存实现单账号更新。
- 不让 `BrowserSession(fingerprint_seed=...)` 固定所有 session/trace ID。
- 不新增 SQLite/JSON/TXT 事实来源。

## 15. 代码规范

### 15.1 状态与错误

- 所有跨模块状态使用 Enum；数据库值在 repository 边界转字符串。
- 每个领域错误必须有稳定 `error_code`、`category`、`retry_class`。
- 异常正文只用于诊断，不能作为唯一分支条件。
- unknown 必须是一等状态，不能强行归到成功或密码错误。

### 15.2 函数边界

- parser/classifier 必须是纯函数，可用 fixture 单测。
- router/policy 是唯一允许读取驱动选择配置的位置；Protocol、browser action 和 current adapters 内部不得再次读取环境变量改变路由。
- browser_current、protocol_current 与 protocol_v2 adapters 实现同一公开 Protocol/ABC，输入输出统一为领域契约；current adapters 不捕获后重写旧错误语义，只做字段映射。
- action 函数一次只做一个远端动作，并返回 `AuthStepResult`。
- orchestrator 决定下一状态，不让 action 自己偷偷 fallback。
- repository 只做行级/事务写入，不做远端 I/O。
- 冻结的 `AuthExecutionPolicy`、route、session、credentials、cancellation token 显式传参，不从全局隐式重新获取。

### 15.3 选择器

- 技术属性优先：URL path、form action、name/value、autocomplete、data-testid。
- 文本只作为唯一候选兜底，覆盖中/英/日/韩已观测文案。
- 每次点击前确认元素可见、可用、唯一且属于正确 form。
- 禁止全局第一个 `button[type=submit]` 或任意 “Continue” fallback。
- 点击后必须等待目标状态，不能把“click 没抛异常”当成功。

### 15.4 日志和敏感数据

- 禁止记录密码、OTP、TOTP code、Token、Cookie、Sentinel token。
- 当前代码中“邮箱 OTP 收到：code”和 secret 前后缀日志必须删除。
- `RoxyBrowserClient.open_profile()` 当前打印的 raw 响应和原始 Profile ID 必须改成白名单摘要/短 `profile_ref`；debugger/WebDriver/WS 原值只进 private context，日志不打印。
- 原始设备/会话/代理只写 private repository，不通过 logger 间接保存。
- 任务日志继续经过统一 redactor；增加 JWT、proxy auth、OTP 六位码和 session ID key 测试。
- 页面快照永远清空 password/OTP input value。

### 15.5 时间、重试和资源

- 使用 `time.monotonic()` 计算预算；业务时间写带时区 UTC。
- 所有 retry 有上限，并写明是否产生过远端副作用。
- 所有 profile/driver/session/route/claim 在 `finally` 收口。
- 资源清理失败写 warning 和资源状态，不覆盖已确认的认证结果。

### 15.6 PostgreSQL

- 使用参数化 SQL。
- 新表通过项目现有 schema/table resolver 创建和访问，不把 `public` 或裸表名写死在业务代码。
- identity 使用数据库原子 upsert，不用 Python 先读后写。
- 新 AT 与账号认证结果在一个事务里提交。
- private context 写入失败不能把远端认证改成失败，但任务必须带诊断告警。
- 新表初始化和测试必须使用独立 schema/独立数据库，不连接生产 `turb_console` 开发。

## 16. 测试矩阵

### 16.1 Protocol classifier

- callback、Session、password、email send、email input、MFA、profile、deactivated、429、5xx、unknown。
- `factor_id` 来自 payload、factor list 和 URL path。
- 非 allowlist host 的 continue URL 被拒绝。
- 响应正文中含敏感值时 fixture sanitizer 清除。

### 16.2 Protocol 状态机

- 有密码直接成功。
- 有密码进入 TOTP。
- 有密码进入邮箱 OTP。
- 密码明确错误，邮箱 fallback 成功/失败。
- 密码响应未知，确认到 Session。
- 密码响应未知，邮箱 fallback 成功且密码状态仍 unknown。
- 本地无密码直接邮箱 OTP。
- 邮箱后再次进入 TOTP。
- TOTP 缺 secret、临近窗口、一次 invalid、连续 invalid。
- OTP send 未确认、邮箱不可用、旧码重复、invalid、stuck、结果未知。
- profile/create-account、phone、risk challenge 不被误报成功。
- 每个计数器都不能超过全局上限。

### 16.3 Browser classifier/actions

- stale password URL + TOTP DOM 优先识别 TOTP。
- login password 与 create password 不混淆。
- 多个 submitter 返回 ambiguous，不点击。
- 无密码且有 passwordless 按钮。
- 无直接 passwordless 入口时，只打开一次方法选择器并只选唯一 email code 项。
- 无密码且无按钮，NextAuth fallback 一次后失败。
- passwordless 后分别进入 EMAIL_FORM、EMAIL_OTP_SEND、EMAIL_OTP_INPUT；send 确认页没有强选择器时不点通用 Continue。
- `login?email` 空壳：NextAuth、补交表单、refresh 的固定顺序。
- 账号 chooser 只选择精确目标邮箱。
- Google/Apple/Microsoft/SSO 永远不被点击。
- OTP 单框、六框、auto-submit、无 submitter。
- 点击 OTP 入口但未确认 send。
- OTP 后进入 MFA、profile、phone、consent、callback。
- stale password URL 的 TOTP、正常 MFA URL 的 TOTP、邮件 OTP 页排除、临近窗口和 result unknown 不重交。
- 所有快照中的 password/OTP value 被清理。

### 16.4 Identity 和存储

- 6 个并发 worker 只创建一个 identity。
- 同账号设备层一致，不同账号不同。
- 同账号两次 session ID 全部不同。
- route rotation 设备层不变、session 层变化。
- 1024Proxy run 只存 lease ID；静态代理存 private raw URL。
- 同一 run 的换线、邮箱 fallback 新 session 和 Roxy fallback 生成按序 context 行，父子链和 session/route 序号正确且不覆盖。
- 注册 context 可在 `account_id=NULL` 时创建，成功后只回填正确账号 ID，失败任务仍可按 operation run 查询且不会产生空账号行。
- `ACCOUNT_AUTH_RAW_CONTEXT_ENABLED=False` 时认证结果与开启时一致，只是不产生 run context 行。
- 到期清理按 500 行分批、可重入；不删除 identity、账号、operation run 或未到期 context。
- BrowserSession/driver/Roxy Profile/代理/claim 在成功、失败、取消和异常下按统一顺序幂等收口；单项清理失败留下可恢复 resource ID。
- private table 不出现在账号 API、任务 API、兼容导出和普通日志。
- 应用层导出明确排除私有表；数据库备份恢复测试确认其按凭据级别受控且不会进入诊断包。
- 普通查活不覆盖最近认证摘要和注册 device ID。
- 刷新失败保留旧 AT/密码/TOTP/成功摘要。
- 新 AT 和结果写回事务回滚测试。

### 16.5 配置、router 和长期兼容

- 默认 `ACCOUNT_AUTH_V2_ENABLED=False` 且所有步骤为 browser_current；浏览器网络调用序列与冻结基线一致。
- 逐个步骤验证 browser_current/protocol_current/protocol_v2；未切换步骤保持浏览器主路径。
- 任务入队后修改配置，本任务策略快照不变，新任务读取新配置。
- Token 刷新为 browser_current 时整条走浏览器；Token 刷新为协议但预计必要步骤选择浏览器时，在远端凭据提交前整条 forced-browser。
- Protocol 已提交密码/OTP/TOTP 后出现 current-only 步骤，不做中间状态注入；按规则 attention 或启动一次完整浏览器 run。
- browser 总开关与每步开关做笛卡尔组合测试：关闭不创建 Profile，开启只对 allowlist fallback，最多一次。
- Roxy 不可用、Core 缺失、容量不足返回 `browser_fallback_unavailable`，Protocol 成功路径不受影响。
- current 密码、查活、邮箱 OTP、TOTP/2FA、Roxy/Codex 公开入口持续通过 characterization tests。
- 非法枚举、旧新键冲突、缺少必要 adapter 在任务启动前得到确定配置错误。

### 16.6 集成和真实灰度

1. 独立 PostgreSQL schema 跑存储/并发/恢复测试。
2. mock HTTP fixture 覆盖所有 Protocol 分支。
3. Selenium fake DOM fixture 覆盖所有 Roxy 选择器。
4. 单账号 Roxy 可见模式验证页面结构。
5. 单账号 Protocol 灰度：先正确密码无 2FA，再正确密码+TOTP。
6. 只有用户明确同意的账号才做一次错误密码验证。
7. 5 个账号小批量，对比 OTP 消耗、成功率、时长、fallback 和未知状态。
8. 每次只切一个步骤，并完成“浏览器 → 现有协议/Protocol v2 → 验证 → 单步回浏览器 → 全局关闭 v2”回滚演练。
9. 完整测试、ruff、compileall、`git diff --check` 后才能切默认。

## 17. 实施阶段和回滚

### 阶段 0：冻结现状

- 给普通查活“不登录”增加契约测试。
- 固化当前成功/失败样本。
- 为当前密码、邮箱 OTP、TOTP/2FA、Token 刷新和 Roxy 入口增加 characterization tests；后续 browser_current/protocol_current 路由必须持续通过。
- 修复现有日志里的 OTP/TOTP secret 泄漏测试，但不改变认证策略。

### 阶段 1：配置、router、contracts 和 private storage

- 先实现全局/逐步骤配置、policy/router/current adapters、新表、新 dataclass、纯 parser、safe/private 快照。
- 所有步骤默认 `browser_current`。
- 证明全部步骤选择 browser_current 时，网络调用和任务结果与冻结的浏览器基线一致。
- 只跑单元/独立数据库测试。

### 阶段 2：Protocol identity 与查活摘要

- 普通查活复用 identity。
- 账号 UI 分开显示最近查活和最近认证。
- 不接密码/MFA。
- 可通过 `ACCOUNT_AUTH_PROFILE_MODE=current` 立即回滚到随机 session。

### 阶段 3：公共浏览器认证组件

- 先增加 browser fallback adapter 和能力检测，不删除或大改现有 Roxy/Codex 状态机。
- browser_current 直接调用原浏览器入口；Protocol 被选为主路径时，只在 allowlist 命中后通过 adapter 启动一次完整浏览器 fallback run。
- 浏览器总开关关闭、Roxy 不可用、容量不足和正常 fallback 各有独立测试。

### 阶段 4：Protocol 密码/MFA

- `ACCOUNT_AUTH_V2_ENABLED=True` 且相关步骤为 `protocol_v2` 时才可触达新代码，并且只对显式单账号开启。
- 正确密码路径先灰度；邮箱 fallback 后灰度；错误密码路径最后验证。

### 阶段 5：小批量与默认切换

- 5 个账号、20 个账号逐级扩大。
- 同时监控 password rejected、unknown、OTP、MFA、Roxy fallback、账号行数和资源泄漏。
- 每次只切一个步骤；全局 v2 关闭和每步回到 browser_current 都要做演练。
- browser_current、protocol_current 路由和浏览器 fallback 长期保留，不设自动删除日期。

任何阶段都不得同时改变 Roxy Profile 生命周期、注册成功条件或账号删除规则。

## 18. 受控实测结果与仍需确认事项

2026-09-01 使用现有 Roxy + 1024Proxy 环境完成单账号、一次性真实认证验证。诊断工具只输出 URL path、控件属性、HTTP 状态、结构化错误分类和资源清理结果；不输出密码、OTP、TOTP、Token、Cookie、完整代理或完整响应正文，也不写回账号资产。

### 18.1 已确认的真实链路

| 场景 | 真实证据 | 结论 |
| --- | --- | --- |
| Roxy 正确密码 + TOTP，账号 302 | `/log-in/password` 提交后约 15.31 秒进入 `/mfa-challenge/...`；TOTP 提交后约 6.52 秒到 ChatGPT `/`；Session AT 存在 | 密码页确实提交并跳转，后续是 TOTP，不是卡住 |
| Protocol 正确密码 + TOTP，账号 302 | `password/verify=200`，`page.type=mfa_challenge`；`mfa/issue_challenge=200`；`mfa/verify=200`，继续地址为 `/api/auth/callback/openai` | 上游新增的三条协议请求形状在当前环境有效 |
| Roxy 无密码邮箱 OTP，账号 241 | 邮箱提交后进入 `/email-verification`；验证码输入为 `name=code/autocomplete=one-time-code/inputmode=numeric`；同一表单有 `intent=validate` 和 `intent=resend`；定向 validate 后 Session AT 存在 | 兜底/邮箱验证码页必须明确点 `validate`，不能取第一个按钮 |
| 当前 Protocol 无密码邮箱 OTP，账号 241 | 当前 `check_account_liveness()` 真实完成邮箱 OTP、OAuth callback 和 Session，返回 `status=live` 且 AT 存在；测试后租约归零 | 现有邮箱 OTP 协议链可作为无密码分支基线 |
| 有保存密码但无 TOTP，账号 492 | 授权预热实际落到 `/email-verification`，没有进入密码页；本轮未提交密码 | 编排器必须按远端页面/响应选择分支，不能因为本地有密码就强行调用 `password/verify` |
| Roxy 随机错误密码，账号 557 | 提交后约 11.38 秒仍在 `/log-in/password`，密码输入 `aria-invalid=true`，有可见错误；未提交邮箱 OTP | 浏览器层可区分明确拒绝，不应按“停留密码页”判定未知 |
| Protocol 随机错误密码，账号 557 | `POST /api/accounts/password/verify=401`，JSON 顶层仅有 `error`，`error.code=invalid_username_or_password`、`error.type=invalid_request_error`，无 `page.type` | 协议层明确拒绝；密码错误不换线路重试 |

所有上述运行均确认账号密码、TOTP、AT、`updated_at` 未变化；Roxy 临时 Profile 跟踪数为 0，活跃代理租约为 0。

### 18.2 已确认的控件与提交规则

1. 当前日文密码页的密码输入使用 `autocomplete=current-password` 并带 `webauthn`，提交控件为 `name=intent/value=validate`。实现应优先用语义属性和唯一 value，不依赖日文按钮文本。
2. TOTP 页可能保留 `/log-in/password` 的历史 URL，但 DOM 是 MFA 表单；必须先检查 `mfa-challenge`/`one-time-code` 等 DOM，再按 TOTP 分类，不能只看 URL。
3. 邮箱验证码页的 `validate` 和 `resend` 共存。收到验证码后必须显式选择 `name=intent,value=validate`；只有找不到该控件时才进入 `unknown`，绝不能按 DOM 顺序点击第一个提交按钮。
4. “密码错误后邮箱兜底”在本次错误密码账号上没有发现安全可识别的 passwordless 按钮，因此没有强行调用隐藏接口或自行补发 OTP。该分支目前只能实现为 `password_rejected + passwordless_fallback_unavailable`，不能声称已经验证成功。

### 18.3 仍需在业务灰度前补齐的证据

1. 停用账号、风控挑战、限流页面的稳定 DOM/协议错误分类尚未覆盖；这些状态必须继续归为 `unknown/attention_required`，不得自动 fallback。
2. “邮箱 OTP 验证后再进入 MFA”的组合页面尚未在真实账号上出现；协议密码→MFA 已验证，邮箱 OTP→MFA 仍需独立 fixture 和单账号灰度。
3. passwordless 入口在其他语言/版本上的完整按钮集合尚未证明一致；自动化只能依赖 `name/value/data-testid` 白名单，无法识别时安全停止。

本节结论已经足够冻结实现契约，但不等于业务代码可以直接切默认。以上 3 类未知项完成前，只允许手动灰度，不允许批量刷新或把 passwordless fallback 默认打开。

受控 Roxy 验证步骤：

1. 用户指定一个允许测试的账号 ID；账号应有已保存 OpenAI 密码，最好同时有 TOTP。
2. 查询并确认该账号没有正在运行的注册/Codex/查活/2FA 任务。
3. 复用账号注册地区和现有账号代理租约规则。
4. 创建一个可见临时 Roxy Profile，不复用其他账号 Profile。
5. 第一轮只提交邮箱并采集密码页脱敏 DOM，不提交密码。
6. 第二轮提交正确密码，观察 password -> MFA/email/callback。
7. 只有用户明确同意“允许一次错误密码提交”时，才验证 password rejected -> email OTP 入口。
8. 不在诊断中补资料、接手机号、创建账号或修改保存密码。
9. 输出只保留 URL path、控件技术属性和错误码；不保存 input value、OTP、Token、Cookie。
10. finally 关闭/软删除 Profile并释放代理租约，核对无孤儿资源。

在完成上述剩余实测前，代码实现必须把停用/风控/限流、邮箱 OTP→MFA 和无法识别的 passwordless 控件保留为 `unknown/attention_required`，不能用猜测规则自动点击。

## 19. 完成标准

1. 普通查活没有任何登录/OTP 远端动作。
2. 所有密码、邮箱 OTP、TOTP 分支都有明确识别证据、次数上限和 unknown 处理。
3. 密码错误和密码结果未知语义分开。
4. 邮箱 fallback 覆盖按钮、send 确认、OTP、后续 MFA 和异常页面。
5. 识别不到页面时不点击通用按钮，保存脱敏 fixture 后安全停止。
6. 原始设备/会话/代理上下文可在私有存储中查询，但不会泄露到普通 API、UI、事件和日志。
7. 同账号 Protocol 设备层稳定、会话层变化。
8. 新 AT 原子写回；失败保留账号全部已有资产和检查点。
9. Roxy Profile、代理和 claim 在全部终态下均可释放或明确显示待人工处理。
10. 所有阶段可按配置回滚，不需要回滚账号数据。
11. 所有逐步骤配置在任务入队时冻结，同一任务运行中修改配置不会切换实现。
12. browser_current/protocol_current 路由的调用序列、远端副作用和结果契约与各自冻结基线一致。
13. 浏览器 fallback 可关闭但能力仍存在；关闭时不创建 Profile，开启时最多一个独立 fallback run。
14. 普通查活在所有配置组合下都不登录、不发 OTP、不调用 Roxy 登录兜底。

## 20. 2026-09-01 受控 Roxy/Protocol 实测记录

本次使用账号 302（保存密码 + TOTP）、241（无保存密码）和 557（错误密码分支）做单账号验证。错误密码测试均使用每次运行生成的随机字符串；没有重复提交同一密码，也没有修改账号资产。

- Roxy Chrome Core 152 已完成下载并解压。此前两次 `/browser/open` 超时的直接原因是本机缺少 Core 152，Roxy 在 `open` 请求内同步下载内核；后续重测必须把内核可用性作为 open 前置检查，超时后不得无条件再次创建 Profile。
- Roxy Core 152 已可用；使用账号注册地区的 1024 JP 线路后，登录页稳定进入可交互日文认证页面。此前 Core 缺失导致的 `/browser/open` 超时不再是当前阻塞项。
- 账号 302 的正确密码浏览器链路为：邮箱页 → `/log-in/password` → `/mfa-challenge/...` → ChatGPT `/`；密码提交后确实发生跳转，TOTP 页面使用 `name=code`、`autocomplete=one-time-code`、`inputmode=numeric`。
- 账号 241 的无密码浏览器链路为：邮箱页 → `/email-verification` → OTP；该页同时显示 validate 和 resend，诊断明确选择 `intent=validate` 后取得 Session。
- 账号 557 的随机错误密码浏览器链路为：密码提交 → 约 11.38 秒后仍在密码页，但已出现 `aria-invalid=true` 和可见错误；未出现安全可识别的 passwordless 邮箱入口。
- Protocol 同步完成了账号 302 的正确密码→MFA 和账号 557 的错误密码请求：正确密码为 `200/mfa_challenge`，错误密码为 `401/invalid_username_or_password`；账号 241 的现有邮箱 OTP Protocol 查活也返回 `live` 并取得 Session。
- 旧的 ad-hoc 等待辅助函数曾把“仍在密码页”过早归类为终态，导致此前“等待 30 秒/45 秒”的描述不准确；当前诊断改为等待明确 DOM 错误、离开密码页或完整超时，并已用 11.38 秒错误提示和 15.31 秒 MFA 跳转重新校正结论。
- 每轮结束均关闭临时会话/软删除 Profile、释放代理租约；最终本地 Profile 跟踪数为 0，活跃代理租约为 0。账号密码、TOTP、AT 和 `updated_at` 均未变化。

当前的实现前置条件只剩：为停用/风控/限流、邮箱 OTP→MFA 和跨语言 passwordless 控件补齐脱敏 fixture，然后在独立 worktree + 独立数据库中实现并灰度；不能据此直接批量开启 `protocol_v2` 步骤。
