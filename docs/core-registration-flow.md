# 核心注册流程逻辑

本文以当前代码为准，梳理一次 ChatGPT 注册任务从提交到结束的完整链路，以及每个步骤的实现、状态变化和容错边界。

## 0. 先看结论

一次注册任务不是单个函数，而是四层协作：

```text
WebUI / CLI
    |
    v
registration_service.py       任务编排、并发、停止、资源释放、终态判断
    |
    v
main.run_registration()       统一注册入口，按 REGISTRATION_DRIVER 分发
    |
    +--> protocol               纯 HTTP/curl_cffi + Sentinel/PoW
    +--> roxy                   RoxyBrowser + Selenium
    +--> cloak                  CloakBrowser + Playwright/Selenium 适配
    +--> browser_use            Browser Use Cloud + Playwright
    +--> skyvern                Skyvern Browser Session + Playwright
    |
    v
OpenAI 注册主体完成：邮箱 OTP -> 资料 -> OAuth 回调 -> accessToken
    |
    +--> 2FA（可选）
    +--> Codex OAuth（可选，但可能影响任务完整成功）
    +--> 账号落库、邮箱状态收口、套餐查询
    +--> protocol 驱动额外触发 Flow
    |
    v
任务终态：success / partial_success / failed / stopped / cancelled
```

最重要的判断边界：

1. `create_account` 成功只表示 OpenAI 接受了创建请求，不表示本地已经拿到可用账号。
2. 真正的注册主体成功条件是拿到 ChatGPT `/api/auth/session` 的 `accessToken`，并将账号绑定到任务。
3. 邮箱领取后先变为 `used`。只有能确认“没有创建账号”的失败才允许回到 `available`；已经消耗邮箱或已经创建账号的失败会标记为 `failed` 或 `disabled`，避免重复注册。
4. 2FA、Codex、套餐查询是注册后的后置能力。后置步骤失败时，账号可能已经保存在 `registered_accounts`，但任务仍可能是 `partial_success` 或 `failed`。
5. PostgreSQL 是运行时事实来源；根目录 JSON/TXT 和 `accounts_viewer.html` 只是兼容导出，不参与核心状态判断。

## 1. 一眼看懂的主流程

### 1.1 WebUI 批量任务

```text
POST /api/jobs
  |
  | 校验 count、workers、email_source 和必要配置
  v
submit_registration()
  |
  | 创建 N 条 registration_jobs：status=pending
  | 每条记录 batch_id / batch_index / email_source / log_file
  v
ThreadPoolExecutor.submit(_run_one_job)
  |
  +-- 任务已取消？ -> 直接跳过
  |
  +-- 原子 claim：pending -> running 失败？ -> 不执行
  |
  +-- 获取代理租约
  |      pool：从静态池取
  |      1024：接口取代理、连通性/地区校验、去重、持久化租约
  |      none：直连
  |
  +-- 准备邮箱
  |      自动模式：按任务选定的单一来源领取
  |      手动模式：使用 REGISTER_EMAIL，OTP 由人工提交
  |
  +-- run_registration()
  |      按驱动执行注册主体
  |
  +-- 驱动返回 / 抛异常
  |      判断是否已经有账号、是否需要停用邮箱、是否可以回收
  |
  +-- registration_service 更新任务和阶段进度
  |
  +-- finally 释放代理租约、收口批次预取代理、清理线程上下文
```

### 1.2 统一的注册主体

```text
启动浏览器会话 / HTTP 会话
  -> 打开 ChatGPT 注册入口
  -> 提交邮箱，进入 OpenAI 认证跳转
  -> 等待邮箱验证码
  -> 提交并验证 OTP
  -> 判断后续页面
       |-- external_url / 已有登录态：直接 OAuth 回调
       `-- about-you：填写姓名和生日，提交 create_account
  -> 跟随 continue_url / 等待页面登录态
  -> GET chatgpt.com/api/auth/session
  -> 必须拿到 accessToken
```

### 1.3 任务阶段顺序

任务进度表由 `core/db.py:JOB_PROGRESS_STAGES` 定义，顺序如下：

| 阶段 | 含义 | 主要负责模块 | 终态判定 |
| --- | --- | --- | --- |
| `email` | 获取邮箱、准备代理 | `registration_service.py` | 邮箱和代理已准备 |
| `browser` | 启动 HTTP/浏览器环境 | 各注册驱动 | 会话可用 |
| `page` | 打开注册页、预热页面 | 各注册驱动 | 注册入口可用 |
| `submit_email` | 填写并提交邮箱 | 各注册驱动 | 邮箱表单已提交 |
| `auth_redirect` | 等待 OpenAI 认证跳转 | `openai_auth.py` 或浏览器辅助函数 | 进入下一认证步骤 |
| `email_otp` | 收码、提交、验证 OTP | `email_provider.py` + 驱动 | OTP 通过或已有登录态 |
| `profile` | 填写姓名和生日 | 协议接口或浏览器驱动 | 资料提交，或确认无需资料 |
| `token` | 完成 OAuth 回调并取得 Token | `account_export.py` 或浏览器驱动 | `accessToken` 非空 |
| `codex` | Codex OAuth | `core/codex_oauth.py` 或对应驱动 | 成功、跳过或失败 |
| `twofa` | Authenticator 2FA | `account_export.py` / Roxy 页面流程 | 成功、跳过或失败 |
| `plan_check` | 查套餐和 Plus 试用资格 | `plan_check_service.py` | 同步完成、后台入队、跳过或失败 |
| `complete` | 汇总任务结果 | `registration_service.py` | 记录总耗时和总状态 |

`finish_job_progress()` 会把失败节点之后未执行的阶段标记为 `skipped`，不会把真实失败节点覆盖成成功。

## 2. 入口和调用链

### 2.1 WebUI 入口

`webui/app.py` 的 `POST /api/jobs` 做三件事：

1. 校验 `count`（1~200）和 `workers`（1~16）。
2. 自动邮箱模式下强制校验一个明确的 `email_source`，且该来源必须已在 `EMAIL_SOURCE` 中启用。一个批次不会在任务执行时静默切换到其他邮箱平台。
3. 调用 `core.registration_service.submit_registration()` 创建任务并投递线程池。

手动 OTP 模式要求配置 `REGISTER_EMAIL`，且 WebUI 限制一次只提交一个任务，避免多个任务共用同一个手动邮箱。

### 2.2 任务服务入口

`submit_registration()`：

- 创建批次 ID。
- 为每个账号创建一条 `registration_jobs` 记录，初始状态为 `pending`。
- 为每个任务设置独立日志文件。
- 按当前 workers 投递 `_run_one_job()`。
- workers 改变时创建新的线程池；旧线程池不再接收新任务，但已提交任务继续执行。

`_run_one_job()` 是 WebUI 单任务的真正入口。它先做数据库条件抢占：

```text
UPDATE registration_jobs
SET status = 'running', started_at = ...
WHERE id = ? AND status = 'pending'
```

抢占失败说明取消请求或其他执行者已经改变了状态，当前线程必须退出，不能把任务重新启动。

### 2.3 CLI 入口

CLI 直接调用 `main.run_registration()`。没有 WebUI `job_id` 时，`report_job_progress()` 自动忽略，因此 CLI 复用注册主体但没有 WebUI 任务进度和停止控制。

## 3. 每个步骤的实现与容错

### 步骤 0：进程启动和中断恢复

WebUI 启动时先调用 `postgres_store.require_ready()`。缺少 `DATABASE_URL` 或 PostgreSQL 不可用时进程直接终止，不再回退到文件模式。

随后执行：

- `db.recover_interrupted_registration_jobs()`：把上个进程遗留的 `pending / running / stopping` 任务收口为 `failed`，当前阶段标记失败，代理状态标记为 `interrupted`。
- `account_task_store.recover_interrupted()`：恢复账号操作类任务实例。
- `cleanup_orphaned_profiles()`：清理 Roxy 遗留浏览器环境。

当前恢复逻辑的业务含义是“任务需要重新执行”，不是自动从网络流程中间点继续。重试入口会根据账号和检查点决定重新注册、继续邮箱验证、补跑 Codex 或补齐账号配置。

### 步骤 1：创建任务和批次

实现位置：`core/registration_service.py:submit_registration()`、`core/db.py:create_job()`。

任务记录至少包含：

- `job_type`：首次注册、继续邮箱验证、Codex 补跑、2FA/账号配置补跑。
- `batch_id`、`batch_index`、`batch_size`、`batch_workers`。
- `email_source`：当前批次选定的单一来源。
- `status`、`progress_stage`、`progress_steps`。
- `proxy_*`：代理提供商、脱敏端点、出口 IP、地区、租约时间。
- `account_id`、`parent_job_id`、`root_job_id`：账号绑定和重试链。

容错：

- 线程池投递失败时，任务直接记为 `failed`，并写入队列提交错误。
- 同一重试链已有 `pending / running / stopping` 任务时，`create_retry_job()` 复用已有任务，避免重复注册。
- 任务状态更新使用行级原子条件更新，避免停止请求被旧快照覆盖。

### 步骤 2：获取代理租约

实现位置：`core/proxy_provider.py:acquire_registration_proxy()`。

根据 `REGISTRATION_PROXY_MODE` 分三种：

| 模式 | 行为 | 容错 |
| --- | --- | --- |
| `none` | 返回 direct 租约，不设置代理 URL | 仍统一走租约释放接口 |
| `pool` | 从静态代理池选一个地址 | 由配置池决定是否有可用代理 |
| `1024` | 请求代理接口、解析端点、校验出口 IP/地区、检查重复 | 多次尝试、重复代理隔离、失败清理 pending 租约 |

批量任务的 `1024` 模式会预取代理。所有任务结束后，`finalize_registration_proxy_batch()` 释放没有分配出去的预取租约。

1024 代理的主要保护：

- 代理端点和出口 IP 去重，避免并发任务共享同一出口。
- 请求失败和验证失败会清理 pending 租约。
- 释放后按 `recent_ttl` 进入短暂隔离期，避免立即复用。
- 代理 URL、账号密码、完整端点在日志和任务记录中脱敏。
- `browser_use / skyvern` 当前不支持 `1024` 注册代理模式，启动任务时直接拒绝。

代理获取失败属于任务级失败；邮箱此时通常还没有领取，不需要回收邮箱。

### 步骤 3：领取邮箱

实现位置：`core/email_provider.py` 和各邮箱 client。

自动模式下，`_prepare_registration_args()` 在其他参数准备完成后才领取邮箱，因为领取动作会把资源从 `available` 改为 `used`。

支持的来源包括：

```text
outlook / generic_api / cloudflare_domain / cloudflare
email_butler / gptmail / mailnest / cloudmail / icloud_hide
```

领取策略：

- WebUI 任务传入明确 `source`：只尝试这个来源，失败直接结束，不跨平台兜底。
- CLI 或旧兼容调用不传 `source`：按 `EMAIL_SOURCE` 顺序尝试来源。
- `USE_EMAIL_SERVICE=False`：不自动领取，使用已配置的 `REGISTER_EMAIL`，OTP 走人工提交。

领取成功后，服务层把邮箱写入任务记录；后续通过邮箱反查实际来源，统一路由等待 OTP 和释放逻辑。

容错：

- 领取失败：任务失败，未领取成功的邮箱不需要释放。
- 临时邮箱（GPTMail、Cloudflare 等）没有本地可复用库存，释放时只清理运行时上下文。
- 本地邮箱池的 `release_email_if_unconsumed()` 会先确认本地没有已保存账号，并且当前状态仍是 `used`，防止把其他并发任务正在使用的邮箱错误改回 `available`。

### 步骤 4：启动注册驱动

实现位置：`main.py:run_registration()`。

分发关系：

| `REGISTRATION_DRIVER` | 实现 | 注册会话 |
| --- | --- | --- |
| `protocol` / `api` / `http` | `main.py` 内置流程 | `BrowserSession` + HTTP |
| `roxy` 等别名 | `core/roxy_registration.py` | RoxyBrowser + Selenium |
| `cloak` | `core/cloakbrowser_registration.py` | CloakBrowser + 适配后的 Selenium 操作 |
| `browser_use` | `core/browser_use_registration.py` | Browser Use Cloud + Playwright/CDP |
| `skyvern` | `core/skyvern_registration.py` | Skyvern Browser Session + Playwright/CDP |

所有驱动接收相同的核心参数：

```text
(email, name, birthday, proxy, otp_code, batch_dir)
```

浏览器驱动还会在需要时接收或读取密码检查点。

### 步骤 5A：协议驱动初始化和网络预检

实现位置：`main.py:run_registration()`、`core/openai_auth.py`。

执行顺序：

1. 创建 `BrowserSession`，固定本次任务的代理、设备 ID、UA 和认证 Cookie。
2. `network_preflight()` 依次检查 ChatGPT、Auth、Sentinel 三段链路。
3. 可选执行匿名 ChatGPT bootstrap，预热匿名态首页和模型链路。
4. 获取 providers 和 CSRF token。
5. 调用 `signin_openai()`，在 signin 请求中携带 `login_hint` 和 `screen_hint=login_or_signup`。
6. 记录 OTP 时间边界 `otp_after_ts`。
7. `follow_authorize()` 跟随 OpenAI 重定向，建立认证 Cookie 并进入邮箱验证码页。

容错：

- 网络预检只对临时网络错误做有限次指数退避；业务 4xx 不盲目重试。
- `follow_authorize()` 对代理抖动、TLS 临时失败等重试；如果落入旧的密码注册路径，直接拒绝继续，避免继续消耗邮箱。
- Sentinel 不在等待 OTP 前生成，避免 challenge 在收码期间过期；只有需要提交验证码或资料时才生成对应 flow 的 token。

### 步骤 5B：浏览器驱动初始化

共同动作：

1. 启动或连接浏览器环境。
2. 安装套餐响应捕获器，尽量复用注册页面已有的权益响应。
3. 打开 `https://chatgpt.com/auth/login` 或驱动配置的起始 URL。
4. 接受 Cookie、等待 DOM、检查停止信号。

驱动差异：

- Roxy 创建环境遇到窗口额度不足时，当前 worker 在 `ROXY_WINDOW_WAIT_TIMEOUT` 内等待，不会快速失败并消耗后续任务槽位；页面跳转超时会先 `window.stop()` 检查 DOM，目标页面可用时继续。
- Cloak 复用 Roxy 的页面操作函数，但使用 Cloak 的输入和浏览器生命周期。
- Browser Use/Skyvern 通过 CDP 连接远端浏览器，远程页面关闭时有心跳和存活页选择逻辑；任务结束默认关闭连接和 Skyvern browser session。

### 步骤 6：提交邮箱并处理认证跳转

浏览器驱动会：

1. 找到邮箱输入框，排除 Google、Apple、Microsoft 等第三方登录入口。
2. 填写并提交邮箱。
3. 等待进入密码页、邮箱验证码页、资料页或已登录态。
4. 如果进入 `/log-in/password`，按“邮箱已注册或不可用于注册”处理，后续会停用邮箱。

页面容错：

- Roxy/Cloak 对页面加载超时先检查当前 URL、`document.readyState` 和 DOM；页面已经可用就继续。
- ChatGPT 登录壳短暂空白、邮箱输入框短暂清空属于过渡状态，会去抖等待，不立即重填造成竞态。
- Browser Use 的 OTP 重新触发会重新打开注册入口并重新提交邮箱，避免直接点击 resend 导致 `chrome-error/500`。
- 所有驱动在关键页面动作前检查手动停止信号。

### 步骤 7：等待和验证邮箱 OTP

实现位置：`core/email_provider.py:wait_for_otp()` 和各驱动 OTP 循环。

统一原则：

- OTP 只读取 `after_ts` 之后的邮件，避免拿到同一邮箱上一轮注册遗留的旧码。
- 默认最多 3 轮尝试。
- 每次重新发送前刷新 `after_ts`，下一轮只接受新邮件。
- 邮件服务模式按邮箱实际来源路由到对应 client；手动模式阻塞等待 WebUI/CLI 提交 6 位验证码。

协议驱动：

1. `wait_for_otp()` 收到验证码。
2. 可选生成 `authorize_continue` Sentinel header。
3. `validate_email_otp()` 提交验证码。
4. 如果是无效/过期验证码，调用 `send_email_otp()`，刷新时间戳并取新码。

浏览器驱动：

1. 在页面填写验证码并点击 Continue。
2. 观察页面状态是否进入资料页、登录态或成功跳转。
3. 无验证码、验证码错误、页面未跳转时重新发送或重新提交邮箱。

错误分类：

| 错误 | 处理 |
| --- | --- |
| 暂时未收到邮件 | 在总等待预算内重新触发 OTP，超过 3 轮失败 |
| OTP 无效/过期 | 刷新 `after_ts`，重发后重新取码 |
| 账号已废弃等明确不可用码 | 抛出 `AccountUnusableError`，邮箱标记 `failed` |
| 手动停止 | 抛出 `StopRequested`，由服务层收口任务和资源 |

### 步骤 8：判断 OTP 后续页面

#### 协议驱动

`validate_email_otp()` 返回后读取 `page.type` 和 URL：

- `external_url`，或 URL 指向 ChatGPT OAuth callback / `authorize/continue`：认为服务端已经有可继续的登录态，跳过资料页，直接进入 OAuth 回调。
- `about_you` 或 URL 指向 `about-you`：导航到资料页，继续获取 Sentinel 并提交姓名/生日。
- 页面类型未知但 `continue_url` 明确指向 `about-you`：记录警告后继续。
- 页面类型未知且 URL 不是 `about-you`：拒绝盲目调用 `create_account`，避免状态错位。

#### 浏览器驱动

浏览器通过当前 URL、页面元素和 `/api/auth/session` 轮询判断：

- 需要资料时填写姓名和生日。
- 已经有登录态时跳过资料填写。
- 资料提交成功或确认已有登录态后才进入 Token 阶段。

### 步骤 9：完成资料和创建账号

协议驱动的资料分支：

1. `navigate_about_you()` 真实导航到 `about-you`，让服务端认证状态和下一次请求一致。
2. 请求 `oauth_create_account` Sentinel challenge。
3. 用 Node Sentinel runner 生成最终 header。
4. `create_account()` POST 姓名和生日。
5. 响应必须包含 `continue_url`。
6. 设置 `create_acknowledged=True`，表示远端已经接受账号创建，邮箱后续不能再按普通未消耗失败回收。

浏览器驱动通过页面表单完成同样的资料提交。Roxy 在新版页面可能先走 `/create-account/password`：

- 密码提交成功后立即写入 `email_verification_pending` 检查点。
- 此时账号行存在但 `access_token` 为空，不能被当作完整账号、不能查套餐或跑 Codex。
- 后续重试会复用保存的邮箱和密码，进入“继续邮箱验证”分支。

### 步骤 10：完成 OAuth 回调并取得 accessToken

协议驱动：


```text
create_account.continue_url
  -> follow_oauth_callback()
  -> chatgpt.com/api/auth/callback/openai
  -> ChatGPT session cookie
  -> fetch_session()
  -> accessToken
```

`main._finalize_registration_session()` 最多尝试 5 次，采用 `2s / 4s / 8s / 16s` 退避。每次都会重新跟随 callback 并拉取 `/api/auth/session`。

只拿到 `create_account` 200、没有拿到 `accessToken`，不能算注册成功。若响应表现为 ChatGPT 已返回 200 但持续没有 Token，服务层会把该邮箱列为需要停用的异常类型，避免下次重复卡在同一状态。

Roxy/Cloak/Browser Use/Skyvern：

- 通过页面跳转和 Cookie 等待 `/api/auth/session`。
- 页面关闭、认证空壳、超时都会进入有限等待或抛出失败。
- 只有 `accessToken` 非空才进入账号后置处理。

### 步骤 11：可选设置 2FA

进入条件：`ENABLE_2FA=True`。

协议模式：

1. 使用刚取得的 `accessToken` 调用 TOTP enroll。
2. 获取 secret。
3. 等待 TOTP 窗口剩余时间足够，再生成验证码。
4. 调用 activate 完成启用。

Roxy 的 browser 2FA：

- 可在当前 Roxy 页面完成设置。
- secret 在激活前先写入账号检查点，并记录 `totp_setup_pending`，防止进程在“已拿到 key、尚未确认启用”时丢失恢复材料。
- 首次 TOTP 提交跨过 30 秒窗口时会用新验证码补交一次。

Cloak/Browser Use/Skyvern 当前主要支持协议 2FA；配置为 browser 2FA 时记录为跳过或失败，不会抹掉已取得的 Token。2FA 失败通常保留账号，后续可走账号配置/2FA 补跑。

### 步骤 12：可选执行 Codex OAuth

进入条件：`ENABLE_CODEX_AUTO=True`。未启用时记录 `skipped`，视为不影响任务完整性。

驱动策略：

- 协议驱动：使用注册阶段同一出口，避免注册和 Codex 之间 IP 漂移。
- Roxy：复用同一个 Profile，在新标签页执行，保持注册后的登录态，不覆盖原注册页。
- Cloak：复用当前浏览器窗口和 Profile。
- Browser Use：关闭注册 CDP 会话后执行独立 Codex OAuth。
- Skyvern：关闭注册 browser session 后执行 Codex OAuth。

Codex 失败不会删除已经注册的账号。失败结果会保存到账号的 `codex_status / codex_error` 或 `extra.codex`，并提供后续 Codex 补跑能力。

### 步骤 13：账号落库和套餐查询

实现位置：`core/account_export.py:save_account_data()`、`core/db.py:insert_account()`。

账号落库内容包括：

- 邮箱、`access_token`、用户信息、账号信息、过期时间。
- TOTP secret（如果已启用）。
- 邮箱来源、注册代理上下文、设备信息。
- Codex、浏览器 Profile 和其他非凭据运行摘要。

Outlook 来源的账号和邮箱池状态在同一个 PostgreSQL 事务内提交：

```text
registered_accounts：插入或按邮箱更新
email_pool_outlook：绑定 registered_account_id，状态保持 used，记录 token/完成时间
```

其他来源在领取时已经由各自 client 将资源标记为 `used`，成功后保持已消耗状态；它们的来源上下文和释放逻辑由 `email_provider.py` 路由到对应 client。当前不能把所有邮箱来源都描述成由 `insert_account()` 通过同一跨表事务更新。

Outlook 的事务写入可以避免“账号已经创建，但邮箱池仍是 available，之后又被领取重复注册”的半完成状态；其他来源依靠领取时的状态收口和失败时的来源专属释放逻辑达到同样的业务约束。

落库成功后：

1. 通过 `report_registered_account(account_id)` 立即绑定当前任务。Roxy 会在多个检查点提前绑定，WebUI 重启后仍能定位已创建账号。
2. 写入批次归档文件，供兼容复制使用。
3. 触发套餐查询：
   - 有注册代理时优先同步查询，完成后再释放代理。
   - 没有可复用代理时进入后台任务队列。
   - 查询失败只记录 `plan_check` 失败，不否定注册主体。
4. 兼容 JSON/TXT 导出由去抖导出任务生成，导出失败不回滚数据库业务写入。

### 步骤 14：protocol 驱动的 Flow 和结果返回

当前 `main.py` 协议流程在账号保存成功后调用 `flow_trigger.trigger_flow(access_token)`：

- Flow 成功、跳过、失败都会记录日志。
- Flow 失败不影响已经保存的账号，也不改变注册主体 Token。
- 当前任务的核心失败判断主要看 Codex；Flow 结果包含在返回值中，但不是独立的注册进度阶段。

浏览器驱动当前不复用 protocol 的这段 Flow 调用，主要返回注册、Codex、2FA 和账号落库结果。

## 4. 失败、停止和资源回收

### 4.1 邮箱状态决策

```text
邮箱领取成功 -> used
       |
       +-- 未创建账号前的普通网络/页面/OTP失败 -> available
       |
       +-- 明确账号不可用、落入登录密码页、Token 最终状态异常 -> failed / disabled
       |
       +-- 账号已创建或已经落库 -> 保持 used，不能再次注册
```

驱动内部通常会在异常时释放一次；`registration_service` 对“函数直接抛异常”的路径再调用 `release_email_if_unconsumed()` 做兜底。这个兜底只会回收“没有本地账号且仍为 used”的邮箱，避免二次释放误伤并发任务。

`release_email()` 的状态含义：

- `available`：可再次领取。
- `failed`：素材或账号状态不可再用，不再领取。
- `disabled`：服务层识别到特定注册异常，直接停用。
- `used`：已消费或已关联注册账号。

### 4.2 任务停止

`request_stop_job()`：

- `pending`：原子改为 `cancelled`，线程即使已经从 Future 中取出，也会在真正执行前自检并跳过。
- `running`：改为 `stopping`，设置线程停止事件。
- 驱动在页面跳转、等待 OTP、输入表单等检查点调用 `check_stop_requested()`。
- 驱动抛出 `StopRequested` 后，服务层把任务改为 `stopped`，仅回收可确认未消耗的邮箱。
- `finally` 始终尝试释放代理和清理线程上下文。

如果数据库状态显示运行中但进程内找不到真实线程实例，服务层会直接把任务收口为 `stopped`，避免任务永久停留在 `stopping`。

### 4.3 未捕获异常

`_run_one_job()` 的服务层兜底顺序：

1. 识别是否为需要停用邮箱的特定错误。
2. 不是停用型错误时，调用 `release_email_if_unconsumed()`。
3. 记录当前阶段失败，之后阶段标记 skipped。
4. 写入任务错误、完成时间和日志。
5. finally 释放代理租约，并在批量任务末尾释放未分配代理。

### 4.4 WebUI 重启

重启不会自动从浏览器中间页面续跑。遗留注册任务会被标为 `failed`，用户需要点击重试。

重试时服务端根据账号事实和检查点选择：

| 条件 | 重试动作 |
| --- | --- |
| 没有账号，或没有可用账号检查点 | `registration`，重新准备邮箱并重新注册 |
| 有 `email_verification_pending` + 已保存密码 + 无 Token | `registration_resume`，继续同一账号邮箱验证；当前只支持 Roxy |
| 已有完整账号但 Codex 未成功 | `codex`，只补跑 Codex |
| 账号已完成 Codex，但密码、套餐或 2FA 缺失 | `twofa`，补齐账号配置 |
| 账号已废号 | 不允许补跑 Codex |

## 5. 任务、账号和邮箱的状态关系

### 5.1 任务状态

```text
pending -> running -> success
                  -> partial_success
                  -> failed
                  -> stopping -> stopped
pending -> cancelled
```

说明：

- `success` 表示任务认为注册主体和必要后置步骤均已完成，或者后置步骤明确跳过。
- `partial_success` 表示账号和 Token 已存在，但 Codex/2FA 等后置能力未完整完成。
- `failed` 可能表示注册主体失败，也可能表示已有账号但当前驱动没有把结果映射成部分成功；查看 `account_id`、`progress_steps` 和账号记录才能确定事实。
- `complete` 是进度节点，不是独立的业务状态。

### 5.2 账号事实

账号是否真实注册成功优先看：

1. `registered_accounts` 是否存在对应邮箱。
2. `access_token` 是否非空。
3. `account_id` 是否已绑定到注册任务。
4. `extra_json.registration_checkpoint` 是否为 `registered` 或 `email_verification_pending`。

不要只看任务 `status` 判断账号是否存在，因为 Codex、2FA、套餐等后置步骤可能失败或中断。

### 5.3 存储来源

```text
事实来源：PostgreSQL
  registered_accounts
  registration_jobs
  email_pool_outlook
  email_pool_generic_api
  email_pool_domain
  email_pool_icloud_hide
  codex_credentials
  proxy_leases
  app_collections（调度状态、兼容集合和迁移期旧数据，不是正常列表事实来源）

兼容输出：根目录 JSON/TXT、accounts_viewer.html、批次 accounts/ 目录
```

核心写入路径应优先保证数据库事务成功；兼容导出不应被当成任务成功条件。

## 6. 重试语义

`get_retry_info()` 不让前端根据错误文本猜重试类型，而是读取任务、账号、进度节点和账号后置状态：

- `registration`：尚未产生账号，重新跑完整注册。
- `registration_resume`：复用 Roxy 保存的邮箱/密码检查点，继续完成 OTP 和 Token。
- `codex`：账号已存在，只执行 Codex OAuth；同一邮箱通过 `codex_retry_service.reserve()` 防止并发补跑。
- `twofa`：账号已存在，补齐密码、套餐和 Authenticator 2FA。

同一任务链用 `root_job_id / parent_job_id / retry_attempt` 关联；已有活跃的同类型任务时直接返回已有任务。账号操作任务还会写入 `account_action_batches`、`account_action_tasks`、`account_action_events`，并对密码、OTP、Token、邮件正文和代理凭据做脱敏。

## 7. 各驱动当前实现对比

| 项目 | protocol | Roxy | Cloak | Browser Use / Skyvern |
| --- | --- | --- | --- | --- |
| 注册方式 | HTTP 接口 | Selenium 页面 | 页面自动化 | Playwright/CDP 页面 |
| OTP 重试 | validate 失败后 API resend | 页面 resend，新时间边界 | 页面 resend | 重新打开入口提交邮箱，避免 resend 500 |
| 密码页 | 当前明确拒绝旧密码路径 | 支持，先保存待验证检查点 | 页面辅助处理 | 页面辅助处理 |
| 资料页 | about-you + Sentinel + create_account | 页面填写 | 页面填写 | 页面填写或跳过 |
| Token 获取 | OAuth callback + `/api/auth/session` | 页面登录态 + session | 页面登录态 + session | 页面登录态 + session |
| 2FA | protocol | protocol 或 browser | 主要 protocol | 主要 protocol |
| Codex | 同一 proxy 的独立 OAuth | 同 Profile 新标签页 | 复用当前窗口 | 关闭注册 CDP 后独立执行 |
| 账号检查点 | 最终落库 | 密码提交、Token 后、Codex/2FA 中间多次落库 | 最终落库 | 最终落库 |
| 后置失败语义 | 账号保存，但 `success` 可能因 Codex 失败为 false | 返回 `registration_success=True` + `partial_success` | `success` 取决于 Codex | 当前返回主体成功，需结合 Codex 阶段查看 |

最后一行是当前代码的真实差异，排查任务时不要假设所有驱动返回值完全一致。判断事实时以 `account_id`、账号表、阶段进度和 `codex_status` 为准。

## 8. 代码定位速查

| 关注点 | 文件和入口 |
| --- | --- |
| CLI/统一驱动分发 | `main.py:run_registration()` |
| 协议注册主体 | `main.py:run_registration()`、`core/openai_auth.py` |
| WebUI 任务提交 | `webui/app.py:api_jobs_create()` |
| 单任务编排和清理 | `core/registration_service.py:_run_one_job()` |
| 任务状态和阶段进度 | `core/db.py` 的 `claim_job_for_execution()`、`update_job_progress()`、`finish_job_progress()` |
| 邮箱领取/OTP/释放 | `core/email_provider.py` |
| 代理获取/释放 | `core/proxy_provider.py` |
| OAuth 回调、Session、账号保存 | `core/account_export.py` |
| Roxy 页面注册和检查点 | `core/roxy_registration.py` |
| Cloak 注册 | `core/cloakbrowser_registration.py` |
| Browser Use/Skyvern 注册 | `core/browser_use_registration.py`、`core/skyvern_registration.py` |
| PostgreSQL 行级存储 | `core/record_store.py`、`core/postgres_store.py` |

## 9. 排查一条失败任务的推荐顺序

```text
1. 看 registration_jobs.status / job_type / account_id
2. 看 progress_stage 和 progress_steps，定位第一个 failed/stopped 节点
3. 看任务日志 注册日志/<job_uuid>.log
4. 如果 account_id 非空，优先检查 registered_accounts.access_token
5. 检查账号 extra_json.registration_checkpoint
6. 检查 codex_status、twofa、plan_check_status
7. 检查邮箱池 status，确认是否 available / used / failed / disabled
8. 检查 proxy_status 和代理租约记录
9. 根据 get_retry_info() 选择 registration / registration_resume / codex / twofa
```

一句话总结：先以 `registration_jobs` 看任务运行到哪一步，再以 `registered_accounts.access_token` 判断账号事实，最后结合邮箱状态和后置状态决定是否重试；不要只凭任务最终文字状态判断注册是否成功。
