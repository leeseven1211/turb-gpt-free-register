# Turb GPT Free Register

ChatGPT / OpenAI 账号自动注册与 Codex OAuth 授权工具。当前项目的注册流程围绕 RoxyBrowser，Protocol 仅作为协议辅助/回退：

- **protocol**：原纯协议注册，基于 `curl_cffi` + Sentinel/PoW。
- **roxy**：RoxyBrowser 指纹浏览器 + Selenium 自动化注册，兼容新版页面流，例如 `create-account/password`、`about-you` 年龄/生日表单、地区本地化页面等。

项目提供 **CLI** 和 **本地 WebUI** 两种使用方式。日常推荐使用 WebUI。

> 项目说明：本项目基于 [xiaoguzuiniu/gpt-free-register](https://github.com/xiaoguzuiniu/gpt-free-register) 进行改造与扩展。

- TG 交流群：[https://t.me/+gu_cvEKq_vcyZWRl](https://t.me/+gu_cvEKq_vcyZWRl)

> 开源版说明：仓库只保留源码、配置模板和文档；运行时账号、Token、邮箱池、Codex 凭证、日志等真实数据均已通过 `.gitignore` 排除。

---

## 功能概览

### 注册

- 批量注册 ChatGPT 账号。
- 支持注册驱动切换：
  - `REGISTRATION_DRIVER = "protocol"`
  - `REGISTRATION_DRIVER = "roxy"`
- 支持 RoxyBrowser 一号一环境：自动创建、打开、关闭、删除 Roxy Profile。
- 支持 Roxy 无头启动：`ROXY_OPEN_HEADLESS=True`。
- Roxy 浏览器注册已兼容：
  - 填邮箱后直接进入邮箱验证码页；
  - 填邮箱后先进入 `create-account/password`，自动设置密码再继续；
  - `about-you/profile` 页面直接输入年龄数字；
  - `about-you/profile` 页面输入年月日生日；
  - React Aria birthday select / spinbutton 年月日控件；
  - 不同出口 IP / 不同页面语言下按钮顺序变化导致的三方登录误点问题。

### 邮箱来源

支持多种邮箱来源：

- Outlook 邮箱池：`email----password----clientId----refreshToken`
- Cloudflare 域名邮箱 + QQ 邮箱 IMAP 收信（`cloudflare_domain`）
- Cloudflare Worker 临时邮箱：自动创建 + JWT 取码（`cloudflare`，兼容 cloudflare_temp_email）
- 通用 API 邮箱：`email----取码地址`
- GPTMail 临时邮箱 API：运行时随机生成邮箱并自动收取验证码
- iCloud Hide My Email：同步本机 sidecar 的隐藏邮箱别名，并通过隐藏邮箱实际转发目标的收件箱自动收码（`icloud_hide`）
- `EMAIL_SOURCE` 支持配置多个已启用来源，例如：

```python
EMAIL_SOURCE = "email_butler,icloud_hide"
```

WebUI 启动注册前会显示“本次注册邮箱来源”下拉框，操作者必须为这一批任务明确选择其中一个来源。选中的来源会写入每个任务和重试任务；领取失败时任务直接失败，不会静默切换到另一个邮箱平台。这样可以清楚判断每个账号实际用了哪类邮箱，也避免 Butler 与 iCloud 隐藏邮箱在运行时被程序自动混用。

- MailNest-迈巢：Outlook 临时邮箱

### Codex OAuth

- 注册成功后可自动跑 Codex OAuth。
- Codex 授权驱动可选：
  - `CODEX_OAUTH_DRIVER = "protocol"`
  - `CODEX_OAUTH_DRIVER = "roxy"`
  - `CODEX_OAUTH_DRIVER = "same_as_registration"`
- 支持 CPA 管理接口生成授权 URL，并提交 OAuth callback。
- 支持接码平台：
  - GrizzlySMS
  - 本地 L 取号服务，见 `L_API.md`
- 手机验证支持自动取号、填号、收码、提交、失败换号重试。
- Codex 凭证保存到 PostgreSQL，并同步生成 `codex_accounts/` CPA 兼容文件。
- 账号页与 Codex 管理页都可把已经完成的 Codex OAuth 凭证单个或批量上传到 sub2api；旧的 Codex Agent Token 生成链路已经移除，OAuth 凭证是唯一的 Codex 授权产物。

### WebUI

- 默认进入平台总览，一屏查看账号、套餐、邮箱资源、注册任务、Codex 凭证、代理模式和当前脱敏租约。
- 批量启动注册任务。
- 左侧主导航会在当前大菜单下展开二级菜单；注册中心拆分为「发起注册 / 任务记录」，任务记录可在 ID、邮箱、邮箱来源、代理、状态、开始/完成日期和错误列内直接组合筛选，并可查看日志或按原断点语义重试。
- 任务记录、账号、Codex 凭证和邮箱池列表采用统一结构：文字列点击列名后直接在表头输入搜索；状态、来源、套餐等枚举列使用基于后端真实数据的紧凑选项菜单；日期列使用单日或起止日期控件。支持多列组合筛选、条件标签回显、单列清空和一键清筛，不再额外占用第二行表头。
- 页面刷新会恢复当前大菜单、二级菜单和配置分组，不会自动跳回总览；列表表头保持固定，长列表滚动时筛选条件和列名不会丢失。
- 四类列表保留原有全部功能，并统一面板外框、操作栏、按钮和表头样式；批量动作只在选中记录后出现，低频动作收进「更多操作」。列宽可拖动、自动记忆，也可一键恢复默认宽度。账号批量操作并发数移至「配置 → 通用配置」。
- 主侧栏与配置分组导航保持固定，滚轮不会串动主内容；仅在菜单或页面内容确实超过可用高度时出现纵向滚动。
- 动态调整注册线程数，提交后新任务立即使用最新值。
- 批量补跑 Codex，补跑线程数每次提交即时生效。
- 管理账号、邮箱池、Codex 凭证；模块子菜单与列表操作区保持吸顶，选中下方记录后无需回到页首。
- 邮箱资源池拆分为「资源总览 / 邮箱列表」，区分本地库存与按需平台，并可查看、手动租用和释放当前 WebUI 进程的 Email Butler 租约。
- Codex 授权只保留一个凭证管理页面；同步 sub2api 是列表批量动作，不再重复占用二级菜单。
- 配置页顶部只保留一处页面身份信息，每次只展示一个配置分组，避免重复标题和长页面误滑；保存后继续支持热加载。
- 桌面端配置页固定左侧分组导航，超长配置只在右侧内容区滚动。
- 总览套餐分布会单独统计「Free」和「Free · 可领 Plus 试用」；网络出口只显示当前代理平台与活跃出口，注册流水线显示当天成功、部分成功和失败任务数。
- Roxy 团队/项目可在配置页获取并保存。
- 发起注册时可按批次开启调试模式；支持多并发任务独立抓取 Roxy 页面网络、WebSocket、控制台错误和 protocol HTTP 请求，失败后限时保留浏览器现场，并可在任务日志中对比同批成功任务或下载脱敏 HAR。
- 未开启调试模式的任务，最终失败时也会自动保存轻量脱敏失败诊断（页面 URL/标题/DOM 摘要、资源时序、浏览器错误、失败请求元数据和截图）；成功任务不抓包、不暂停浏览器。诊断结果可在任务日志的「失败诊断」区域查看。
- 根据当前邮箱、代理、浏览器、Codex、提链和 sub2api 配置动态判断功能是否可用；缺少必要配置时，前端按钮会禁用，后端接口也会拒绝执行并返回具体原因。
- 批次进度按邮箱逐行展示，包含准备邮箱、打开浏览器、打开注册页、提交邮箱、认证跳转、邮箱验证码、填写资料、获取 Token、Codex 等阶段；顶部显示成功/失败/运行/等待和总耗时。

### 2026-08-13 更新记录

- 运营页面统一为总览、注册、账号、Codex、邮箱池和配置六个模块；注册任务、账号、Codex 凭证和邮箱列表共用筛选、列宽记忆、分页、批量操作及二级菜单结构，页面刷新后恢复上次模块和子页面。
- 注册批次支持停止运行中任务、取消排队任务、重跑失败任务；单个失败任务也可按断点语义重跑。当前批次逐账号展示每个阶段及阶段耗时，Codex 后继续展示“查套餐”和“完成”，完成后显示任务总时间；失败原因在对应失败阶段查看。
- 邮箱提交和 OTP 等待减少固定等待：Email Butler 按目标邮箱和任务时间窗口精确读取验证码，已入库时只做轻量轮询；各驱动输出提交邮箱、OTP、手机验证和 callback 等阶段耗时。
- Roxy 创建环境遇到明确的窗口额度不足时会留在当前任务等待名额，不再让超出并发上限的后续注册任务全部启动；等待上限和间隔由 `ROXY_WINDOW_WAIT_TIMEOUT`、`ROXY_WINDOW_WAIT_INTERVAL` 控制。
- 注册完成后的套餐查询纳入任务完整进度；查活和查套餐按账号注册地区领取独立短期线路，网络预检失败时释放旧线路并换新代理重试。
- 查活优先在线验证现有 accessToken；只有 AT 缺失、失效或用户明确要求刷新时，才进入邮箱 OTP 登录刷新，避免正常账号重复登录。
- 账号页新增「任务实例」二级菜单。查活、AT 刷新、查套餐和查封号邮件都会创建可检索任务，保存脱敏阶段事件、线路、验证方式、结果和耗时；失败实例可以从任务列表手动重跑。
- accessToken 会解析并保存签发/过期时间；账号列表展示 AT 剩余时间，后台可在到期前按配置自动创建刷新任务。
- 单个、批量以及注册任务断点触发的 Codex 补跑统一创建 `codex_retry` 任务实例。账号菜单不再单独提供“补跑日志”，补跑阶段、错误、线路和结果统一从任务实例查看，失败实例可直接重跑。
- Roxy 注册和查活的 NextAuth 兜底会确认浏览器是否真正落到 `auth.openai.com` 或明确下一步；登录空壳、邮箱框短暂清空只作为过渡态等待。若页面已经进入密码、OTP 或登录完成状态，会停止刷新、重填邮箱和重复导航，避免竞态导致空白页或覆盖已成功的跳转。

---

## 环境要求

- Python 3.10+
- Node.js 18+
- 可用代理、系统代理/VPN，或 RoxyBrowser 代理环境
- 如使用 Roxy 注册：需要本机 RoxyBrowser API 可访问
- 如启用 Codex 自动授权：需要接码平台配置
- PostgreSQL 16（本机统一由 `shared-services/postgres` 管理）

推荐在项目内创建虚拟环境安装依赖：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
node --version
```

macOS 如果本机环境变量仍指向旧版 `openssl@1.1`，安装新版 `cryptography` 可能触发编译失败。可先安装带 wheel 的兼容版本再继续：

```bash
.venv/bin/python -m pip install --only-binary=:all: 'cryptography>=41,<50'
.venv/bin/python -m pip install -r requirements.txt
```

### 密钥配置（.env）

重要 API Key 请放在项目根目录 `.env`，不要写进 `config/*.py`。

```bash
cp .env.example .env
# 编辑 .env，例如：
# ROXY_API_TOKEN=...
```

当前支持从 `.env` 读取的密钥：

- `WEBUI_AUTH_CODE`（WebUI 登录授权码）
- `WEBUI_SESSION_SECRET`（可选，Session Cookie 签名密钥）
- `ROXY_API_TOKEN`
- `QQ_IMAP_PASSWORD`
- `ICLOUD_HME_API_TOKEN`（sidecar 如启用接口鉴权）
- `ICLOUD_HME_FORWARD_IMAP_PASSWORD`（仅旧版直接 IMAP/历史封号扫描使用）
- `PROXY_1024_API_URL`
- `CLOUDFLARE_API_KEY` / `CLOUDFLARE_CUSTOM_AUTH`（`EMAIL_SOURCE=cloudflare` 时）
- `CPA_MANAGEMENT_KEY`
- `SMS_API_KEY`
- `L_ADMIN_AUTH_CODE`
- `H_ADMIN_AUTH_CODE`

WebUI 配置页保存这些字段时会写入 `.env`（不是 config 源码）。

### PostgreSQL 主存储

PostgreSQL 是**唯一事实来源**，没有纯文件模式回退：`DATABASE_URL` 缺失或库连不上时进程会在启动时直接终止，而不是静默改用文件（那会让两份副本悄悄分叉）。

账号、注册任务、四类邮箱池、代理租约和 Codex 凭证均由 PostgreSQL 行级表支撑（`registered_accounts` / `registration_jobs` / `email_pool_*` / `proxy_leases` / `codex_credentials`），可行级更新、可跨进程原子抢占。`app_collections` 仅保留调度状态、兼容集合和迁移期旧数据，不是正常列表的事实来源。

根目录的 JSON/TXT 与 `accounts_viewer.html` 是**兼容产物**，供 CLI、CPA 和人工导出使用；它们由后台去抖任务生成，不在写入主路径上。日志、浏览器缓存与批次文件仍保留在文件系统。

结构、迁移步骤与开发约定见 [`docs/storage-architecture.md`](docs/storage-architecture.md)。

本机 PostgreSQL 已从项目目录拆分为公共服务。启动：

```bash
/Users/lihongwei/code/personal/shared-services/postgres/postgres.sh start
```

然后在 `.env` 配置：

```dotenv
DATABASE_URL=postgresql://turb:turb_local_dev@127.0.0.1:55432/turb_console
```

历史兼容 JSON 只会在对应 PostgreSQL 记录不存在且经过兼容入口时作为一次性种子读取；正常运行不从兼容文件回退。迁移过程不会删除兼容文件。查看状态：

```bash
/Users/lihongwei/code/personal/shared-services/postgres/postgres.sh status
```

其他本机项目需要使用 PostgreSQL 时，应在同一个实例中创建独立数据库和用户，不要共用 `turb_console`。具体用法见 `/Users/lihongwei/code/personal/shared-services/postgres/README.md`。

---

## 快速开始

### WebUI 授权码

WebUI 启动后，除 `/login` 外所有页面和 `/api/*` 接口都会校验授权码。推荐在 `.env` 中配置：

```dotenv
WEBUI_AUTH_CODE=你的授权码
```

也可以启动时直接传入：

```bash
python web.py --auth-code 你的授权码
```

优先级：`--auth-code` > `.env`/环境变量。若都未设置，启动时会在日志中生成并打印本次临时授权码。接口调用可使用登录后的 Cookie，或传 `X-Auth-Code: <授权码>` / `Authorization: Bearer <授权码>`。

`WEBUI_SESSION_SECRET` 可选；未设置时会从固定授权码派生稳定的 Session 签名密钥，修改授权码后已有登录会自动失效。

### 1. 配置邮箱源

#### Outlook 邮箱池

复制示例文件：

```bash
cp 用于注册的邮箱.txt.example 用于注册的邮箱.txt
```

每行格式：

```text
email----password----clientId----refreshToken
```

也可以在 WebUI 的「邮箱池」页面导入。

#### 通用 API 邮箱

每行格式：

```text
email----code_url
```

在 `config/email.py` 设置：

```python
EMAIL_SOURCE = "generic_api"
```

或使用组合来源：

```python
EMAIL_SOURCE = "outlook,generic_api,mailnest"
```

#### GPTMail 临时邮箱

在 WebUI 的「配置 → 邮箱 / OTP」填写 `GPTMail API Key`，然后将邮箱来源设置为：

```python
EMAIL_SOURCE = "gptmail"
```

也可以在项目根目录 `.env` 中填写：

```dotenv
GPTMAIL_API_KEY=你的_GPTMail_API_Key
```

服务地址固定为 `https://mail.chatgpt.org.uk`。未填写 Key 时，任务会提示填写 `GPTMail API Key`，不会使用公共测试 Key。

#### Cloudflare Worker 临时邮箱（`cloudflare`）

兼容 `cloudflare_temp_email` 类 Worker：注册时自动创建域名邮箱，并用 JWT 轮询收件箱提取 OpenAI 六位验证码。  
（与下方 `cloudflare_domain` / QQ IMAP 方案不同，请勿混用标识。）

```dotenv
EMAIL_SOURCE=cloudflare
CLOUDFLARE_API_BASE=https://你的-worker-api-域名
CLOUDFLARE_API_KEY=你的_ADMIN_PASSWORD
CLOUDFLARE_AUTH_MODE=x-admin-auth
# admin 创建时常用：
# CLOUDFLARE_PATH_ACCOUNTS=/admin/new_address
CLOUDFLARE_DEFAULT_DOMAINS=你的收信域名.com
```

匿名模式可将 `CLOUDFLARE_AUTH_MODE=none` 且 Key 留空，创建路径默认 `/api/new_address`；若被 Turnstile 拦截请改用 admin 模式。更多字段见 WebUI「配置 → 邮箱 / OTP」或 `.env.example`。

#### iCloud Hide My Email（`icloud_hide`）

先在本机启动 `icloud-hme` sidecar，再到 WebUI「配置 → 邮箱 / OTP → iCloud 隐藏邮箱」填写服务地址和账号 ID，保存后点击“连接并同步”。推荐配置：

```dotenv
USE_EMAIL_SERVICE=True
EMAIL_SOURCE=icloud_hide
ICLOUD_HME_API_BASE=http://127.0.0.1:8081
ICLOUD_HME_ACCOUNT_ID=你的_sidecar_账号ID
ICLOUD_HME_AUTO_CREATE=False
```

turb 只保存别名库存与领取状态；Apple Cookie 和 iCloud App 专用密码保留在 sidecar 中。Gmail 转发收码支持本机 `forward_imap` 直连和生产 `forward_butler` 两种模式；本机调试/注册可直接连接 Gmail，生产链路仍由 Oracle Email Butler 接收。每个注册任务领取一个别名，注册成功后永久占用；明确未消耗的失败任务才会把别名退回可用池。默认只复用已同步别名，库存为空时不会自动创建；确需自动补充时再开启 `ICLOUD_HME_AUTO_CREATE`。

收码前必须确认以下链路一致：

```text
隐藏邮箱别名 → Apple“转发到”Gmail → 本机 Gmail IMAP
                                  或 → Oracle IMAP IDLE → Email Butler PG
```

- sidecar 使用 Apple App 专用密码连接 `imap.mail.me.com` 时，设置 `ICLOUD_HME_INBOX_MODE=sidecar`，且 Apple“隐藏邮件地址 → 转发到”必须选择同一个 `@icloud.com` 邮箱。
- 如果隐藏邮箱实际转发到 Gmail，本机直接收码使用 `ICLOUD_HME_INBOX_MODE=forward_imap`：

```dotenv
ICLOUD_HME_INBOX_MODE=forward_imap
ICLOUD_HME_FORWARD_IMAP_EMAIL=你的_Gmail_地址
ICLOUD_HME_FORWARD_IMAP_PASSWORD=你的_Gmail_应用专用密码
```

- `forward_butler` 仍表示 Oracle 接收 Gmail 后写入 Email Butler PG；生产切换时再单独配置该模式。
- `forward_imap` 的 Gmail 应用专用密码只保存在本机 `.env`，不会写入仓库或日志。
- Apple 账号页面“隐藏邮件地址 → 转发到”的已选地址和 sidecar 返回的 `forwardToEmail` 才是转发目标的依据，不要根据当前浏览器登录的是哪个 Gmail 账号推断。
- 新版 sidecar 会在别名列表返回 `forwardToEmail`。turb 同步时只启用与当前收件模式匹配的别名，避免把验证码发到 Gmail 却轮询 iCloud IMAP 的假成功。
- 连接测试在 `forward_imap` 下应返回 `inbox_method=local_forward_imap`；在 `forward_butler` 下才返回 `email_butler_pg`。两种模式都要确认同步结果的 `forward_incompatible=0`。
- iCloud 创建别名有频率/数量限制。批量运行建议预先同步库存并保持 `ICLOUD_HME_AUTO_CREATE=False`，不要在遇到限流后高频重试。

sidecar 本地启动示例（具体账号导入方式以 sidecar 自带 README 为准）：

```bash
cd /path/to/icloud
go build -o build/icloud-hme .
./build/icloud-hme -addr 127.0.0.1:8081 -data ./data
```

#### Cloudflare 域名邮箱（`cloudflare_domain`）

在 `config/email.py` 设置：

```python
EMAIL_SOURCE = "cloudflare_domain"
EMAIL_DOMAIN = "你的域名"
QQ_EMAIL = "你的QQ邮箱"
QQ_IMAP_PASSWORD = "QQ邮箱IMAP授权码"
```

Cloudflare Email Routing 需要把域名邮件转发到 QQ 邮箱。此模式不调用 Worker 创建接口，仅本地生成地址并通过 QQ IMAP 取件。

#### MailNest-迈巢 Outlook 临时邮箱

可直接在 Web-UI 中配置 API Key 与项目代码`MAIL_NEST_PROJECT_CODE`，也可以在配置文件中配置。

- `api-key`获取页面：https://mailnest.top/account
- 项目代码获取页面：https://mailnest.top/buy-email。默认为`chatgpt001`，可以直接使用

---

### 2. 配置注册驱动

编辑 `config/roxybrowser.py`，或直接在 WebUI「配置」页修改。

#### 使用 RoxyBrowser 注册

```python
REGISTRATION_DRIVER = "roxy"  # 可选 protocol / roxy
ROXY_API_BASE = "http://127.0.0.1:50100"
ROXY_API_TOKEN = "你的Roxy API Key"
ROXY_WORKSPACE_ID = "你的workspaceId"
ROXY_PROJECT_ID = "你的projectId"
ROXY_ONE_PROFILE_PER_ACCOUNT = True
ROXY_DELETE_PROFILE_AFTER_RUN = True
ROXY_CREATE_USE_PROXY_POOL = True
```

如要无头：

```python
ROXY_OPEN_HEADLESS = True
```


#### 使用协议注册

```python
REGISTRATION_DRIVER = "protocol"
```

协议注册会使用 `curl_cffi`、Sentinel/PoW、代理池等配置。

---

### 3. 配置代理

编辑 `config/proxy.py`：

```python
PROXY_POOL = [
    "http://user:pass@host:port",
]
```

Roxy 一号一环境开启 `ROXY_CREATE_USE_PROXY_POOL=True` 时，会从这里随机取代理写入 Roxy Profile。
当 `REGISTRATION_PROXY_MODE=1024` 时不需要开启该选项：任务服务领取的独立 1024Proxy
家宽租约会自动转换成 Roxy `/browser/create` 使用的 `proxyInfo`，并优先于静态代理池。
Roxy 的字段不是普通浏览器代理 URL，而是 `proxyMethod/proxyCategory/protocol/host/port`
（有鉴权时再加 `proxyUserName/proxyPassword`）；任务日志只记录脱敏端点。

也可以在 WebUI「配置 → 代理平台」中选择 `1024`，填写 1024Proxy 白名单提取 API。
平台模式会为每个注册任务提取一个独立粘性代理，并在领取邮箱前检测出口；注册与紧接着执行的
自动 Codex OAuth 共用该代理。建议把粘性时长设为至少 30 分钟。动态住宅流量套餐按实际流量计费，
延长粘性时间本身不会持续产生流量。当前平台模式支持 protocol 和 RoxyBrowser。

1024Proxy 推荐基线：

```dotenv
REGISTRATION_PROXY_MODE=1024
PROXY_1024_API_URL=https://white.1024proxy.com/white/api?region=US&num=1&time=30&format=1&type=txt
PROXY_1024_REGION=US
PROXY_1024_PROTOCOL=http
PROXY_1024_SESSION_MINUTES=30
PROXY_1024_ROTATE_SESSION_TIME=True
PROXY_1024_API_TIMEOUT=12
PROXY_1024_MAX_ATTEMPTS=5
PROXY_1024_ACQUIRE_TIMEOUT=60
PROXY_1024_VALIDATE=True
PROXY_1024_VALIDATE_ATTEMPTS=2
PROXY_1024_RECENT_TTL=1800
PROXY_1024_ACQUIRE_INTERVAL=0.6
PROXY_1024_PERSIST_LEASES=True
# 注册页遇到线路级瞬时失败时，最多释放旧租约并换线重试 2 次
REGISTRATION_PROXY_RETRIES=2
REGISTRATION_PROXY_RETRY_DELAY=1
ACCOUNT_ACTION_PROXY_MODE=registration
```

- 单任务会使用 `num=1`；注册批次会按待执行任务数批量设置 `num`，再并行检测并分配给任务。
- 平台返回代理后会检测实际出口国家；实际国家与请求国家不一致时会拒绝并重新提取。
- 已占用/隔离期内的重复粘性 IP 不再消耗“有效失败次数”，会在 60 秒总预算内快速重取；出口检测的超时、连接和 SSL 瞬时错误会先对同一端点重试一次。
- `PROXY_1024_ROTATE_SESSION_TIME=True` 会按任务 ID 在基础时长到 120 分钟间派生不同的 `time` 参数，避免平台在相同 `region/time` 窗口内返回同一粘性会话。`PROXY_1024_PERSIST_LEASES=True` 时，租约会在 PostgreSQL 中记录 pending/leased/recent 状态，多个 WebUI/CLI 进程共享端点和出口 IP 去重；白名单 API 没有单独的远程释放调用。
- OpenAI 注册实测优先固定 `region=US`。`Rand` 可能落到画像不完整或高风控地区，增加挑战概率。
- 粘性时间延长本身不产生流量，只有浏览器实际发出请求才消耗代理流量。30 分钟是注册 + 邮件等待的最低建议值，必要时可设更长。
- 日志和 UI 只应显示脱敏后的代理端点/出口 IP；完整 API URL 属于私密配置，只放 `.env`。

`ACCOUNT_ACTION_PROXY_MODE=registration` 会让查套餐、查活和手动 Codex OAuth
跟随注册代理来源：注册使用 1024Proxy 时，每个账号功能会按该账号注册国家重新申请一条独立租约，
完成后立即释放；注册使用静态代理池时则继续从池中抽取。邮箱、短信、CPA/Sub2、提链服务、
Roxy 控制 API 等第三方或本地接口保持直连，不消耗住宅代理流量。批量账号功能不会让整批
账号共用同一个平台 IP。

---

### 4. 配置 Codex OAuth

如不需要 Codex，关闭：

```python
ENABLE_CODEX_AUTO = False
```

如需要自动授权：

```python
ENABLE_CODEX_AUTO = True
# config/codex.py
CODEX_OAUTH_DRIVER = "roxy"  # 可选 protocol / roxy / same_as_registration
```

接码配置在 `config/codex.py`：

```python
SMS_PROVIDER = "l"        # 可选 grizzly / l / h
SMS_API_KEY = "你的 GrizzlySMS key"  # 仅 GrizzlySMS 需要
SMS_SERVICE = "openai"
SMS_COUNTRY = "117,2,148" # Grizzly 可按顺序配置备用国家；无号/超价时自动切换
SMS_MAX_PRICE = ""       # 单号价格上限（不是固定成交价），留空=不限；实际价以平台返回为准
SMS_AUTO_SELECT_COUNTRY = True      # Grizzly 每批次按价格上限内的短信成功率自动选国
SMS_AUTO_COUNTRY_MIN_RATIO = 25     # 排除成功率高但统计量太少的国家
SMS_MAX_RETRIES = 10
SMS_CODE_WAIT = 120                 # 单个号码等待短信的硬上限
CODEX_PHONE_TOTAL_TIMEOUT = 300     # 手机验证整段硬预算
SMS_POLL_INTERVAL = 5

# 若 SMS_PROVIDER="h"，H 固定复用：
#   SMS_SERVICE -> H projectId
#   SMS_COUNTRY -> H country
H_API_BASE = "http://localhost:8788"
H_ADMIN_AUTH_CODE = "你的H后台授权码"
```

`SMS_CODE_WAIT` 是单个号码等待短信的硬上限，`CODEX_PHONE_TOTAL_TIMEOUT` 是取号、页面操作、
等待短信和换号合计的整段硬预算。号码超时后，取消任务会交给后台持久化队列，不再阻塞注册线程。

GrizzlySMS 的订单取消不是“取号后立即取消”：程序会把待取消订单持久化到
`run/sms_cancel_queue.json`，由单一后台 worker 根据平台允许的时间执行取消。
`EARLY_CANCEL_DENIED` 会按平台返回时间或退避策略延后处理，不会高频轮询；WebUI 重启后会自动恢复队列。
`run/` 是运行时私有目录，不得提交 Git。手机号国家选择会按号码国际区号同步页面国家选项；如果页面明确只允许
WhatsApp 而不是 SMS，当前号码会判为不可用并进入换号流程。

CPA 授权地址来源：

```python
CODEX_AUTH_URL_SOURCE = "cpa"
CPA_MANAGEMENT_URL = "你的CPA管理地址"
CPA_MANAGEMENT_KEY = "你的CPA管理密钥"
```

### 当前设计与适配规则

下面这些规则同时适用于 WebUI 自动注册、单账号操作、批量操作和 CLI。修改相关功能时必须一起检查所有入口，不能只修其中一条链路。

#### 邮件验证码

- iCloud 隐藏邮箱转发到 Gmail 时，本机可使用 `Gmail IMAP → turb` 直接取码；生产 `forward_butler` 链路仍是 `Gmail IMAP IDLE → Email Butler PostgreSQL → turb HTTP API`。
- 当前本机配置使用 `ICLOUD_HME_INBOX_MODE=forward_imap`，OTP 直接读取本机 Gmail；`forward_butler` 保留为生产 Email Butler 链路。
- turb 的账号、邮箱池、注册任务和账号操作任务均以本机 PostgreSQL 为主存储；JSON/TXT 只作为兼容导出或输入文件。项目运行时不再使用 SQLite。
- OTP 查询必须携带任务开始时间并按目标别名精确匹配，避免并发任务互相拿错验证码。轮询间隔由 `OTP_POLL_INTERVAL` 控制，Butler 已经接收到邮件时只做轻量查询。

#### 代理与地区

- `REGISTRATION_PROXY_MODE=1024` 时不得静默回退到 `PROXY_POOL`、`127.0.0.1` 或直连；提取、出口检测或地区校验失败会在有限预算内自动补取/换线，耗尽重试后才停止并保留明确错误。
- 1024Proxy 每个注册任务领取独立租约；实际出口国家会写入任务和账号。注册结束后的查套餐、查活和独立 Codex OAuth 由 `ACCOUNT_ACTION_PROXY_MODE` 统一管理，默认按账号注册国家领取新的短期租约。
- 注册完成后立即查套餐时，优先复用仍有效的注册代理并在释放前同步落库，从而保证套餐/Plus 资格查询与注册出口一致；历史账号或手动操作再按账号已保存地区领取线路。
- 住宅代理只用于访问 OpenAI/ChatGPT 的账号功能。邮箱、短信、CPA、sub2api、提链服务、Roxy 控制 API 和其他本地接口保持直连，不得套用住宅代理，也不得把系统 `HTTP_PROXY/HTTPS_PROXY` 意外注入这些客户端。
- UI 中选择的地区、1024Proxy API URL 的 `region` 参数、Roxy Profile 的代理字段、任务日志与账号记录必须保持一致。完整代理 URL、用户名和密码只允许保存在 `.env`，日志和 UI 只能显示脱敏信息。

#### Roxy 环境与登录态

- `ROXY_ONE_PROFILE_PER_ACCOUNT=True` 时，每个注册任务创建一个唯一临时 Profile；创建请求超时或断连属于“结果未知”，客户端会先按唯一环境名查询是否已经创建成功，不能盲目重试并制造孤儿环境。
- Roxy 明确返回“窗口额度不足”时，当前 worker 会停留在“启动浏览器”阶段等待并重试，不会失败后继续消费后续排队任务。默认最多等待 `ROXY_WINDOW_WAIT_TIMEOUT=900` 秒，每 `ROXY_WINDOW_WAIT_INTERVAL=10` 秒重试；其他创建错误不进入容量等待。
- 邮箱 UI 提交后如果进入登录空壳或邮箱框短暂清空，NextAuth 兜底会等待真实落点；只有确认页面仍未前进时才刷新或重填。页面已经到达密码、OTP 或登录完成状态时必须立即接受该状态，不能依据旧快照重复提交邮箱。
- 默认在任务结束时关闭浏览器，并在 `ROXY_DELETE_PROFILE_AFTER_RUN=True` 时删除临时 Profile。需要排查时应在发起注册页勾选「调试模式」：失败任务会在配置的超时时间内暂停并保留自己的 Roxy 窗口，用户可在任务日志中点击「释放现场」继续清理。`ROXY_KEEP_BROWSER_OPEN=True` 只保留为低层紧急诊断开关，不适合日常批量调试，因为它不受任务级超时和并发上限管理。
- 注册后紧接着执行 Codex OAuth 时，复用同一个 driver、Profile、代理和 ChatGPT 登录态，授权 URL 不强制 `prompt=login`；若出现账号选择器，只允许选择与当前任务邮箱完全匹配的账号。
- 从账号页独立补跑 Codex 时没有可信的注册浏览器上下文，因此使用新环境和账号功能代理重新登录。这与“注册后立即 OAuth 复用登录态”是两个不同场景。
- Roxy 免费版界面显示的 5 个 Profile/窗口额度不等于整条注册链路必然能稳定并发 5。实际并发还受住宅代理提取频率、邮箱库存、OTP、接码平台和 OpenAI 风控限制；首次部署先跑通单任务，再逐步提高并发。

#### Codex、接码与 sub2api

- Codex 的事实记录在 PostgreSQL 的 `codex_credentials`，`codex_accounts/` 下的 OAuth JSON 是为 CPA/sub2api 保留的兼容产物。旧 Codex Agent Token 生成、下载和上传接口已经移除；sub2api 导入直接上传 OAuth JSON，并支持按账号更新已有凭证。
- 注册成功不因 Codex 失败而回滚；账号正常保存，Codex 标记失败并允许单独补跑。补跑停止信号必须贯穿邮箱 OTP、取号、短信等待和浏览器流程，不能被普通换号异常吞掉。
- GrizzlySMS 支持在 `SMS_COUNTRY` 中配置备用国家，并透传 `SMS_MAX_PRICE`（它只是购买上限，不是固定成交价）。开启 `SMS_AUTO_SELECT_COUNTRY` 后，每个批次首次接码会结合正式价格/库存接口与价格页短信成功率统计，在价格上限内选出统计量足够且成功率最高的国家；同一国家连续失败两次会自动切到排名中的下一候选。统计接口异常时自动回退 `SMS_COUNTRY`。实际成交价、国家和价格上限会写入本地运行日志与取消队列，便于复盘。
- sub2api、CPA 和短信平台是第三方控制面请求，默认直连；它们的鉴权字段必须放在 `.env`，不得写入源码、README、日志或数据库导出。

#### WebUI 与配置变更

- `/api/capabilities` 是前端功能开关的依据，但后端接口仍必须调用同一套可用性检查，不能只靠隐藏/禁用按钮保证安全。
- 配置保存并热加载后，要同时刷新功能可用性和注册邮箱来源。后台任务启动前读取最新配置，已经运行的任务保持其提交时的邮箱来源和已领取资源，不在途中静默换源。
- 新增、删除或重命名配置时，必须同步检查 `config/*.py`、`config/__init__.py`、`webui/config_editor.py`、`.env.example`、README、CLI/WebUI/自动任务/批量任务入口及测试。涉及代理、邮箱、Codex 或数据结构的改动，还要检查账号页、任务恢复、导入导出和部署配置。
- 提交前至少运行完整单元测试；涉及真实浏览器链路时，按“单任务 → 小并发”顺序验收。`.env`、`run/`、`logs/`、账号、邮箱池、Codex 凭证和生产数据库内容永远不得提交。

---

## 使用方式

## WebUI 推荐方式

推荐使用项目根目录单脚本后台管理：

```bash
./webui.sh start      # 启动
./webui.sh stop       # 关闭
./webui.sh restart    # 重启
./webui.sh status     # 状态
./webui.sh logs       # 查看实时日志
```

脚本默认启动 `http://127.0.0.1:5000`，日志写入 `logs/webui.log`，PID 写入 `run/webui.pid`。

可通过环境变量调整：

```bash
PORT=8000 OPEN_BROWSER=1 ./webui.sh start
HOST=0.0.0.0 PORT=5000 ./webui.sh restart
AUTH_CODE=你的授权码 ./webui.sh start
```

也可以直接前台启动：

启动：

```bash
python web.py --open-browser
```

默认地址：

```text
http://127.0.0.1:5000
```

可指定端口：

```bash
python web.py --port 8000 --open-browser
```

允许局域网访问：

```bash
python web.py --host 0.0.0.0 --port 5000
```

WebUI 页面说明：

| 页面 | 功能 |
|---|---|
| 总览 | 查看账号、邮箱资源、任务、Codex 和代理平台整体状态 |
| 注册 | 「发起注册 / 任务记录」子菜单；设置批次参数，组合查询任务，查看进度、日志和断点重试 |
| 账号 | 「活跃账号 / 归档账号 / 任务实例」子菜单；账号页集中批量操作并组合筛选，任务实例统一查询 Codex 补跑、查活、AT 刷新、查套餐和查封号邮件的脱敏日志与耗时 |
| Codex 授权 | 单一凭证管理页；列表上方集中下载、上传 sub2api、归档和删除，表头按邮箱、Plan、导出/归档状态、Account ID、更新及过期日期筛选 |
| 邮箱池 | 「资源总览 / 邮箱列表」子菜单；管理 Email Butler 当前进程租约；邮箱列表上方集中导入和批量操作，表头按邮箱、类型、状态、Token 和日期筛选 |
| 配置 | 左侧分组切换独立配置页，顶部不再重复显示“运行配置”，修改当前分组并热加载 |

### 线程数说明

- 注册线程数在每次点击「开始注册」时读取。
- 如果线程数和上次不同，新提交任务会使用新线程池。
- 旧线程池里已经排队/运行的任务会继续跑完，不会被强制取消。
- Codex 批量补跑每次都会按本次提交的补跑线程数创建独立线程池。

### 本地验证基线：Roxy + 1024Proxy + iCloud HME

下面是一套适合先在 macOS 本地单账号验证的组合配置。所有密钥和真实接口都写入 `.env`，不要改进源码或提交 Git：

WebUI 中 1024Proxy 位于「配置 → 代理平台」，不是「代理池」；后者只保留静态代理及套餐查询网络配置。任务列表的“代理”列会显示实际 provider、脱敏端点和出口地区，可据此确认任务是否真的使用了 1024Proxy。

```dotenv
# WebUI
WEBUI_AUTH_CODE=请替换

# 主流程
REGISTRATION_DRIVER=roxy
ENABLE_CODEX_AUTO=False
CODEX_OAUTH_DRIVER=same_as_registration

# 一个任务一个 1024Proxy 美国住宅 IP
REGISTRATION_PROXY_MODE=1024
PROXY_1024_API_URL=请替换为你的白名单提取_API
PROXY_1024_REGION=US
PROXY_1024_PROTOCOL=http
PROXY_1024_SESSION_MINUTES=30
PROXY_1024_ROTATE_SESSION_TIME=True
PROXY_1024_API_TIMEOUT=12
PROXY_1024_MAX_ATTEMPTS=5
PROXY_1024_ACQUIRE_TIMEOUT=60
PROXY_1024_VALIDATE=True
PROXY_1024_VALIDATE_ATTEMPTS=2
PROXY_1024_RECENT_TTL=1800
PROXY_1024_ACQUIRE_INTERVAL=0.6
PROXY_1024_PERSIST_LEASES=True
ACCOUNT_ACTION_PROXY_MODE=registration

# WebUI 启用 Email Butler 与 iCloud 两个可选邮箱来源；本地通过 HTTPS 直连生产 Butler，不需要 SSH 隧道
USE_EMAIL_SERVICE=True
EMAIL_SOURCE=email_butler,icloud_hide
OTP_POLL_INTERVAL=3
OTP_MAX_WAIT=240
EMAIL_BUTLER_API_BASE=https://codex-auth.leeseven.com/email-butler/v1
EMAIL_BUTLER_API_KEY=请从生产客户端配置安全同步，禁止提交
EMAIL_BUTLER_REQUEST_TIMEOUT=20

# iCloud 隐藏邮箱（在注册页手动选择时使用，不作为 Butler 失败后的自动回退）
ICLOUD_HME_API_BASE=http://127.0.0.1:8081
ICLOUD_HME_ACCOUNT_ID=请替换
ICLOUD_HME_API_TOKEN=
ICLOUD_HME_REQUEST_TIMEOUT=45
ICLOUD_HME_SYNC_TTL=300
ICLOUD_HME_INBOX_MODE=forward_imap
ICLOUD_HME_FORWARD_IMAP_SERVER=imap.gmail.com
ICLOUD_HME_FORWARD_IMAP_PORT=993
ICLOUD_HME_FORWARD_IMAP_EMAIL=请替换为实际转发_Gmail
ICLOUD_HME_FORWARD_IMAP_PASSWORD=请填写Gmail应用专用密码
ICLOUD_HME_AUTO_CREATE=False
ICLOUD_HME_CREATE_LABEL_PREFIX=turb
```

本机 `5000` 端口可能被 macOS Control Center 占用，开发测试优先使用 `8000`：

```bash
PORT=8000 ./webui.sh status
PORT=8000 ./webui.sh start

# 如果后台进程被终端会话回收，改用前台运行：
env -u NO_PROXY -u no_proxy .venv/bin/python web.py --host 127.0.0.1 --port 8000
```

运行前检查：

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
curl -sS http://127.0.0.1:8081/api/accounts
```

WebUI 提交真实任务时先设为“数量 1、线程 1”。确认批次进度完整走过“拉邮箱 → 打开浏览器 → 打开注册页 → 提交邮箱 → 邮箱验证码 → 填资料 → 获取 Token”后，再考虑连续任务。Codex OAuth 会额外需要 CPA 和短信接码，主注册验收期间建议保持 `ENABLE_CODEX_AUTO=False`。

`.env.example` 是 WebUI 可编辑字段的完整模板；新增配置时必须同步更新 `config/*.py`、`webui/config_editor.py`、`.env.example` 和本 README。配置页的密钥字段只写 `.env`，页面会按密码框处理。

### 后续投产清单

- 使用 systemd、launchd 或其他进程管理器托管 WebUI 和 iCloud sidecar；反向代理只暴露 WebUI，不要把 sidecar 的 `8081` 直接暴露公网。
- WebUI 绑定 `127.0.0.1`，由 Nginx/Caddy 提供 HTTPS；设置固定 `WEBUI_AUTH_CODE` 和 `WEBUI_SESSION_SECRET`。
- 部署新代码前备份 `.env`、邮箱池、`accounts/`、`codex_accounts/`、`注册任务.json`、注册成功文件和日志；这些都是运行时私有数据，不能被仓库覆盖。
- 代理和邮箱都必须按任务生命周期领取：任务开始领取，成功永久占用邮箱并释放本地代理租约；确认账号未创建的失败任务才退回邮箱，避免同一邮箱注册两次。
- 先执行完整测试，再滚动重启服务。不要提交 `.env`、许可证、Apple Cookie、App 专用密码、邮箱、代理完整地址或 Token。

### 账号任务实例与 AT 生命周期

WebUI「账号 → 任务实例」统一保存以下账号操作：

- `codex_retry`：Codex OAuth 补跑。
- `live_check`：优先验证现有 AT 的账号查活。
- `token_refresh`：AT 缺失、失效、临近过期或手动要求时的刷新。
- `plan_check`：查询账号套餐及 Plus 试用资格。
- `deactivation_mail`：扫描支持邮箱来源中的高置信度封号邮件。

每个任务实例保存任务 ID、账号快照、触发方式、状态、验证方式、脱敏线路、开始/完成时间、耗时、结果摘要和阶段事件。账号密码、AT、验证码、邮箱正文、callback 和完整代理凭据不会写入任务库。WebUI 重启时，仍处于排队或运行状态的历史实例会标记为中断，可从实例列表重新执行。

账号列表显示 AT 签发时间、过期时间和剩余时间。定时刷新只处理进入提前刷新窗口的账号；默认提前 24 小时检查，配置如下：

```dotenv
AT_AUTO_REFRESH_ENABLED=True
AT_REFRESH_BEFORE_HOURS=24
AT_REFRESH_SCAN_INTERVAL_SECONDS=3600
AT_REFRESH_INITIAL_DELAY_SECONDS=120
AT_REFRESH_MAX_PER_CYCLE=20
```

### Codex OAuth Token 生命周期

「Codex 授权」列表会把凭证导出状态和 OAuth 状态分开显示。OAuth 状态依据凭证的
`expired`（必要时回退 access token 的 `exp`）计算为有效、即将过期、已过期或未知；
同时显示是否存在 `refresh_token`。手动“刷新 OAuth Token”和后台定时刷新都只执行
refresh-token grant，不重新登录，也不会请求邮箱 OTP 或接码短信。只有 refresh token
本身失效、被撤销或缺失时，才需要“重跑 Codex 授权”。这类刷新失败会额外标记为“需重授权”；
本地 access token 的过期时间尚未到，并不代表服务端仍接受已被撤销的 refresh token。

```dotenv
CODEX_TOKEN_AUTO_REFRESH_ENABLED=True
CODEX_TOKEN_REFRESH_BEFORE_HOURS=24
CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS=86400
CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS=120
CODEX_TOKEN_REFRESH_MAX_PER_CYCLE=20
CODEX_TOKEN_AUTO_SYNC_SUB2API=True
```

为避免 refresh token 轮换后 sub2api 仍持有旧凭证，曾由当前页面成功上传过 sub2api
的凭证会在本地刷新成功后自动同步；仅本地保存、从未由当前页面上传的凭证不会被自动上传。

### 查封号邮件

WebUI「账号」页提供单账号“复查”和批量“查封号邮件”。该功能只读取邮箱服务返回的高置信度 OpenAI 封号通知信号，不登录 OpenAI、不读取或刷新 AT/accessToken，也不保存邮件正文。

当前支持以下账号邮箱来源：

- `email_butler`：调用 `/v1/signals/scan`。
- `cloudflare`：优先调用只读 `CLOUDFLARE_SIGNAL_PATH`；当前进程仍保有邮箱 JWT 时可回退扫描收件箱。
- `icloud_hide`：通过已配置的转发 Gmail/IMAP 按隐藏邮箱地址检索；服务器端先过滤收件人，不会为每个账号下载整个收件箱。

`outlook`、`cloudflare_domain` 等其他来源会显示“不支持”，不会误报。已确认收到封号通知后，证据会持久保留；后续缩短回溯窗口或一次未命中不会把它自动清除。

```dotenv
# Email Butler（本地开发可使用受 API Key 保护的 HTTPS 入口；服务器本机可用 127.0.0.1）
EMAIL_BUTLER_API_BASE=https://codex-auth.leeseven.com/email-butler/v1
EMAIL_BUTLER_API_KEY=请替换
EMAIL_BUTLER_REQUEST_TIMEOUT=20

# Cloudflare 只读封号信号接口（按需）
CLOUDFLARE_SIGNAL_API_KEY=请替换为独立只读Key
CLOUDFLARE_SIGNAL_PATH=/signals/scan

# 后台周期扫描
EMAIL_BUTLER_RISK_SCAN_ENABLED=True
EMAIL_BUTLER_RISK_SCAN_WORKERS=2
EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS=21600
EMAIL_BUTLER_RISK_SCAN_INITIAL_DELAY_SECONDS=90
EMAIL_BUTLER_RISK_SCAN_LOOKBACK_DAYS=120

LIVE_CHECK_ROXY_FALLBACK_ENABLED=True
```

手动接口：

- `POST /api/accounts/<id>/check-deactivation-mail`
- `POST /api/accounts/check-deactivation-mail-bulk`，JSON 为 `{"account_ids":[1,2]}`

---

## CLI 使用方式

注册 1 个：

```bash
python main.py
```

批量注册 10 个，3 线程：

```bash
python main.py -n 10 --workers 3 --continue-on-fail
```

详细日志：

```bash
python main.py -n 1 --verbose
```

参数：

| 参数 | 说明 | 默认 |
|---|---|---|
| `-n, --count` | 注册数量 | 1 |
| `--workers` | 并发线程数 | 1 |
| `--delay` | 每次注册结束后的间隔秒数 | 0 |
| `--continue-on-fail` | 单个失败后继续 | False |
| `--verbose` | DEBUG 日志 | False |

---

## Codex 补跑

WebUI 账号页可单个或批量补跑 Codex；注册任务在账号已创建但 Codex 失败时，也会按断点语义只补跑 Codex，不重复注册账号。

每次补跑都会创建 `codex_retry` 任务实例。账号菜单只负责发起补跑；运行阶段、脱敏线路、耗时、失败原因和最终结果统一在「账号 → 任务实例」查看。单个、批量和注册任务触发的补跑都使用同一套任务记录，失败或中断的实例可以在任务列表中手动重跑。

CLI 单独补跑：

```bash
python tools/test_codex_oauth.py --email <已注册邮箱> --verbose
```

补跑会消耗：

- 1 次邮箱 OTP
- 1 个接码号码

兼容文件日志仍保留用于旧版页面或本地故障排查：

```text
注册日志/codex-retry-邮箱.log
```

标准 WebUI 不再从账号菜单打开该文件；日常查看以任务实例中的脱敏阶段事件为准。

---

## 账号密码说明

OpenAI 新版注册通常先展示邮箱验证码页；新账号页面同时提供：

```text
/create-account/password
```

是否设置密码由「配置 → 注册主链路 → 注册认证方式」决定：

- `otp`：直接使用邮箱一次性验证码完成无密码注册（默认）。
- `password`：在验证码页主动进入 `/create-account/password`，设置随机密码后再完成邮箱验证。

`REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS` 控制密码提交后等待验证码页、资料页或登录态的独立预算，默认 `60` 秒。该预算从点击密码页“继续”后重新计时，不占用前面的密码页识别/填写时间；密码提交请求一发出就会先保存可恢复检查点，超时且没有明确远端结果时，不会丢失已生成的密码或把邮箱重新放回注册池。邮箱表单提交后的认证跳转也会重新获得独立预算；纯代理隧道、空登录壳、页面未水合或注册前阶段预算耗尽且未产生账号状态时，会先自动刷新/强制新导航，仍为空壳才软删除本轮临时 Roxy Profile、释放代理租约并换新 IP 重试。普通页面识别失败仍保留现场，已保存账号检查点的失败不会触发这项回收。

邮箱验证码是 OpenAI 的邮箱所有权验证步骤；即使选择 `password`，设置密码后仍然需要邮箱 OTP。若 password 模式下页面没有提供创建密码入口，任务会明确失败，避免把无密码账号误报为密码注册成功。

密码设置成功后，OpenAI 登录页仍可能默认先展示邮箱验证码；此时可通过 `/log-in/password` 的“使用密码继续”入口改用密码登录。无密码注册的账号可以在账号配置补跑时设置一次密码；已有密码的账号不会修改密码。

密码始终按账号独立随机生成：14 位，包含大写、小写、数字和符号。配置页不提供固定密码输入，避免一批账号共用同一个密码。

保存位置：

- 账号 `extra_json.account_password`：账号唯一密码。注册时或账号配置补跑时设置后都写入这里，后续补跑只会读取，不会改密码。
- 旧数据中的 `extra_json.registration_password` / `extra_json.login_password` 仅作为兼容读取来源，新写入不会再生成这两个字段。
- 批次归档 `accounts/YYYYMMDD-.../注册成功账号.json` 的 `extra.account_password`

账号页提供“账号密码”状态列和真实数据筛选。已设置密码的账号可以单独复制；批量选择后可用“复制密码”导出 `邮箱----密码`，未设置密码的账号会自动跳过。

注意：账号表里的 `password` 字段仍用于 Outlook 邮箱素材密码，不会被 OpenAI 账号密码覆盖。

---

## 重要配置文件

| 文件 | 说明 |
|---|---|
| `config/roxybrowser.py` | 注册驱动、Roxy API、Roxy 环境生命周期 |
| `config/codex.py` | Codex OAuth、授权驱动、CPA 管理接口、接码平台 |
| `config/email.py` | 邮箱来源、OTP 轮询、Email Butler、QQ IMAP、iCloud HME、Cloudflare 临时邮箱及封号信号 |
| `config/proxy.py` | 代理池 |
| `config/register.py` | 默认邮箱、认证模式、显示名 |
| 外部共享 PostgreSQL | 本机由 `/Users/lihongwei/code/personal/shared-services/postgres` 统一管理 |
| `config/twofa.py` | 2FA 开关与开通方式（`protocol` / `browser`） |
| `config/humanize.py` | 随机停顿/人工节奏 |
| `config/flow_trigger.py` | 注册成功后触发 Flow |
| `config/browser.py` | 协议模式浏览器指纹 |
| `config/openai_protocol.py` | OpenAI OAuth/Sentinel 参数 |

WebUI 配置页保存后会调用热加载；Roxy、Codex、邮箱、代理、人工节奏等常用项可立即生效。

---

## 数据与产物

核心业务数据以 PostgreSQL 为主存储；下表文件均为兼容导出或运行产物。

| 路径 | 内容 |
|---|---|
| `用于注册的邮箱.txt/json` | Outlook 邮箱池及状态 |
| `用于注册的API邮箱.txt/json` | 通用 API 邮箱池及状态 |
| `注册成功的邮箱.txt/json` | 注册成功账号 |
| `注册成功的token.txt` | ChatGPT access token |
| `accounts/` | 每次运行的批次归档 |
| `codex_accounts/` | Codex OAuth 凭证 JSON |
| `注册任务.json` | WebUI 注册任务表 |
| PostgreSQL `account_action_batches/account_action_tasks/account_action_events` | 账号操作任务实例及脱敏阶段事件 |
| `注册日志/` | 注册任务日志、兼容用 Codex 补跑文件日志 |
| `accounts_viewer.html` | 本地账号查看页 |

批次目录示例：

```text
accounts/20260709-10个-3线程/
├── 注册成功的邮箱.txt
├── 注册成功的token.txt
├── 注册成功整行.txt
└── 注册成功账号.json
```

---

## 当前主流程

### Roxy 注册流程

```text
创建/打开 Roxy Profile
  ↓
打开 chatgpt.com/auth/login
  ↓
按 DOM 技术属性定位邮箱输入框，避免误点 Google/Apple/Microsoft
  ↓
提交邮箱表单
  ↓
等待 OpenAI 认证跳转；首次确认空白壳时切换 NextAuth 兜底并等待真实落点
  ↓
若页面已进入密码、OTP 或登录完成状态，停止刷新、重填和重复导航
  ↓
如进入 create-account/password：设置密码并提交
  ↓
等待邮箱验证码页
  ↓
读取邮箱 OTP 并提交
  ↓
如进入 about-you/profile：填写姓名 + 年龄或生日
  ↓
进入 ChatGPT，读取 /api/auth/session accessToken
  ↓
使用当前注册代理查询套餐和 Plus 试用资格并保存注册地区
  ↓
可选 2FA
  ↓
可选 Codex OAuth（复用当前 Profile、代理和登录态）
  ↓
保存账号与批次归档
  ↓
关闭/删除 Roxy Profile
```

### Codex Roxy 授权流程

```text
获取 Codex 授权地址（CPA 或 local PKCE）
  ↓
注册后立即授权：复用现有 Roxy 登录态；独立补跑：创建新环境并重新登录
  ↓
邮箱登录 + 邮箱 OTP
  ↓
手机号验证：取号 → 填号 → 发送 → 等短信 → 填 OTP
  ↓
等待 consent/workspace/callback
  ↓
提交 callback 给 CPA 或本地换 token
  ↓
保存 PostgreSQL `codex_credentials`，并生成 `codex_accounts/codex-邮箱*.json` CPA 兼容文件
```

---

## 常见问题

### 配置保存后没生效？

WebUI 配置页保存后会热加载。Codex 补跑线程启动前也会重新热加载一次配置。

`config/*.py` 保存配置默认值；直接修改后 CLI 进程需要重启。运行时配置建议通过 WebUI 配置页写入 `.env`，以便热加载。

### Roxy 无头保存后仍弹窗口？

检查：

```python
ROXY_OPEN_HEADLESS = True
```

并确认 Roxy 版本支持 `/browser/open` 的 `headless` 参数。日志会打印实际传入的 `headless`。

### 出口 IP 不是日本时点到 Google 登录？

当前 Roxy 注册邮箱入口已改为只按 DOM 技术属性定位，并排除三方登录按钮。不会再靠按钮文字匹配“Continue”。

### Codex 显示 `Check your phone` 被误判失败？

已兼容：`Check your phone / Enter the verification code...` 会识别为手机验证码页，进入等待短信验证码流程。

### 手机 OTP 提交后日志曾显示失败，但后面成功？

已修复：提交手机 OTP 后会等待页面离开手机号流程或 callback，不再 3 秒后用旧页面文案误判失败。

### Codex 失败但注册成功怎么办？

账号会保存，Codex 状态会标记失败。可以在 WebUI 账号页点击补跑，或使用：

```bash
python tools/test_codex_oauth.py --email <邮箱> --verbose
```

### Cloudflare Worker 邮箱怎么配？

将 `EMAIL_SOURCE` 设为 `cloudflare`，并配置 `CLOUDFLARE_API_BASE` 等（见上文「Cloudflare Worker 临时邮箱」）。  
注意与 `cloudflare_domain`（QQ IMAP 转发）不是同一来源。

### 没有接码平台能注册吗？

可以。关闭：

```python
ENABLE_CODEX_AUTO = False
```

注册主流程不依赖接码，Codex 自动授权才需要。

---

## 项目结构

```text
.
├── main.py                         # CLI 入口与注册兼容门面
├── web.py                          # WebUI 启动入口
├── config/                         # 配置默认值、环境覆盖和模块配置
│   └── registration_debug.py       # 调试抓包、普通失败诊断、现场保留和清理策略
├── core/
│   ├── registration/                # 注册公共入口、驱动分发和协议流程
│   ├── registration_service.py     # 注册任务线程池与生命周期
│   ├── registration_debug.py        # 按任务隔离的 CDP/协议抓包、失败诊断、脱敏和 HAR
│   ├── admin_repository.py         # 管理台查询读模型
│   ├── db.py                       # 业务数据门面与兼容导出编排
│   ├── record_store.py             # PostgreSQL 行级记录存储
│   ├── postgres_store.py           # 连接、schema 和兼容集合存储
│   ├── operation_task_store.py     # 统一账号操作任务存储
│   ├── account_task_store.py       # 历史账号操作任务兼容层
│   ├── codex_operation_service.py  # Codex 操作编排
│   ├── email_provider.py           # 邮箱来源调度
│   ├── sms_provider.py             # 接码平台调度
│   ├── proxy_provider.py           # 代理租约与释放
│   └── *_registration.py / *_oauth.py / *_client.py # 各驱动和客户端
├── webui/
│   ├── app.py                      # Flask 应用装配
│   ├── blueprint.py                # 保留旧 endpoint 名称的 Blueprint 基础类
│   ├── route_helpers.py             # 路由共享的查询/脱敏/分页辅助函数
│   ├── runtime.py                   # WebUI 启动恢复、worker 和请求上下文
│   ├── routes/                      # 按领域拆分的 Flask Blueprint
│   │   ├── dashboard.py / config.py / email_pool.py
│   │   ├── accounts.py / jobs.py / operations.py
│   │   └── codex.py / integrations.py
│   ├── auth.py                     # 登录鉴权
│   ├── config_editor.py            # 配置白名单、.env 写入与热加载
│   ├── templates/                  # modern / legacy / login 模板
│   └── static/                     # CSS、按页面/领域拆分的普通 JavaScript、favicon
│       ├── css/                   # foundation、modern、legacy、login 样式
│       └── js/                    # modern/legacy 八段业务脚本 + login.js
├── tests/                          # unittest、存储隔离和契约测试
├── tools/                          # 迁移、诊断和单独补跑工具
├── docs/                           # 架构、流程、规范和路线图
└── sentinel/                       # Sentinel Node.js 子进程
```

`accounts/`、`codex_accounts/`、`注册日志/`、`run/`、`logs/`、`.env` 和 `.venv/` 等是本地运行时数据或凭证目录，故意不列入代码结构，也不得提交。

---

## 使用建议

- 日常批量使用 WebUI，不建议直接同时开多个 CLI 进程。
- 注册线程数建议不超过可用代理数。
- Roxy 一号一环境建议保持开启，降低环境污染。
- 调试页面或接口问题时，在「发起注册」勾选「调试模式」。该开关只作用于本批任务：Roxy 强制显示窗口，抓包按任务隔离；失败后脚本暂停等待人工查看，点击「释放现场」、停止任务或达到超时后继续自动清理。
- 在任务日志的「网络调试」区域查看请求状态、阶段、耗时和错误，可选择同批成功任务自动对比，也可下载已经脱敏和限流的 HAR。Cookie、Token、密码、OTP、邮箱和 URL 查询值不会明文写入抓包。
- 普通失败任务在同一日志面板显示「失败诊断」：分类、页面状态、失败请求和截图；普通模式不会保存成功请求或请求/响应正文。
- 保留时间、并发暂停数、单正文/单任务/全局容量、产物保留天数和异步队列长度在「配置 → 注册调试」管理。调试抓包位于 `注册日志/debug/<job_uuid>/`，属于运行时私有数据，不得提交。

---

## 🙏 致谢

- [LINUX DO](https://linux.do) — 社区交流与用户反馈
- [RoxyBrowser](https://roxybrowser.cn/invite/NvH4Jx) — 免费提供 5 个窗口
- [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) — Codex OAuth 凭证格式参考
- [curl_cffi](https://github.com/yifeikong/curl_cffi) — 底层 HTTP 库，提供 TLS 指纹 impersonate 能力

---

## License

MIT
