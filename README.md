# Turb GPT 注册与账号管理工具

ChatGPT / OpenAI 账号自动注册与 Codex OAuth 授权工具。注册驱动支持本地优化 Protocol、开源 Protocol、开源protocol-2、本地 Roxy 和开源 Roxy：

- **protocol**：本项目持续优化的纯协议注册链路，包含本地恢复、检查点、错误分类与阶段预算。
- **protocol_oss**：隔离接入上游开源注册协议，保留独立协议流程；邮箱、代理、任务状态、PostgreSQL 和注册后处理继续使用本项目能力。
- **protocol_oss_2**：接入 wangshen233 开源仓库的 AuthFlow 与 wreq，展示为「开源protocol-2」；复用本地邮箱、代理、原 Attempt 恢复、PostgreSQL 和注册后处理。
- **roxy**：RoxyBrowser 指纹浏览器 + Selenium 自动化注册，兼容新版页面流，例如 `create-account/password`、`about-you` 年龄/生日表单、地区本地化页面等。
- **roxy_oss**：使用固定上游 Roxy 页面识别和表单辅助，复用本地浏览器生命周期、认证提交、任务恢复和账号后处理。

项目提供 **CLI** 和 **本地 WebUI** 两种使用方式，日常推荐使用 WebUI。本项目由我们自行维护，主仓库为
[leeseven1211/turb-gpt-free-register](https://github.com/leeseven1211/turb-gpt-free-register)。

## 项目概况

- WebUI 入口：`web.py` / `webui.sh`。
- CLI 入口：`main.py`。
- 默认仅监听 `127.0.0.1:5000`；macOS 的 `5000` 端口可能被 Control Center 占用，本机运行优先使用 `8000`。
- PostgreSQL 是账号、注册任务、邮箱池、代理租约和 Codex 凭证的唯一事实来源；根目录中的兼容导出文件不能替代数据库。
- 项目代码、注释、日志、界面和文档统一使用中文；配置键、协议字段和第三方产品名保留原名。
- `.env`、账号、Token、邮箱池、Codex 凭证、日志、`run/` 和 `.venv/` 都属于运行时私有数据，不得提交仓库。

---

## 功能概览

### 注册

- 批量注册 ChatGPT 账号。
- 支持注册驱动切换：
  - `REGISTRATION_DRIVER = "protocol"`
  - `REGISTRATION_DRIVER = "protocol_oss"`
  - `REGISTRATION_DRIVER = "protocol_oss_2"`
  - `REGISTRATION_DRIVER = "roxy"`
  - `REGISTRATION_DRIVER = "roxy_oss"`
- 注册批次使用全局默认注册方式；每个任务都会冻结所用 driver，任务列表和账号高级搜索可区分本地与开源方式。
- 支持 RoxyBrowser 一号一环境：账号首次需要时创建 Profile，后续注册续跑、Codex、账号配置、查活和 AT 刷新优先复用同一 Profile。
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
- Remail 开放 API：按项目下单领取邮箱并自动收取验证码（`remail`）
- MailCode 域名邮箱：按指定商品购买邮箱，持久化幂等订单和取码游标（`mailcode`）
- 西瓜邮箱接码：按指定 Offer 购买邮箱并获取邮件验证码（`xigua`）
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
  - 本地 L 取号服务，见「本地 L 接码服务」
- 手机验证支持自动取号、填号、收码、提交、失败换号重试。
- Codex 凭证保存到 PostgreSQL，并同步生成 `codex_accounts/` CPA 兼容文件。
- 账号页与 Codex 管理页都可把已经完成的 Codex OAuth 凭证单个或批量上传到 sub2api；旧的 Codex Agent Token 生成链路已经移除，OAuth 凭证是唯一的 Codex 授权产物。

### WebUI

- 默认进入平台总览，一屏查看账号、套餐、邮箱资源、注册任务、Codex 凭证、代理模式和当前脱敏租约。
- 批量启动注册任务。
- 账号页支持一键巡检、巡检历史和失败详情：固定当前归档范围，按需刷新失效 AT 并复用登录会话查询套餐；已废账号单独跳过，也可明确确认范围后一次清理。
- 左侧主导航会在当前大菜单下展开二级菜单；注册中心拆分为「发起注册 / 任务记录」，任务记录可在 ID、邮箱、邮箱来源、代理、状态、开始/完成日期和错误列内直接组合筛选，并可查看日志或按原断点语义重试。
- 任务记录、账号、Codex 凭证和邮箱池列表采用统一结构：文字列点击列名后直接在表头输入搜索；状态、来源、套餐等枚举列使用基于后端真实数据的紧凑选项菜单；日期列使用单日或起止日期控件。支持多列组合筛选、条件标签回显、单列清空和一键清筛，不再额外占用第二行表头。
- 账号列表的枚举列支持多选：同列满足任一所选项，不同列同时满足；选项及数量覆盖当前活跃或归档视图的全部分页，只显示有记录的值。套餐为空时统一显示并提供「未查询」筛选；有套餐值时沿用该套餐。点击「全部」清空该列，点击「完成」关闭菜单，已选条件会在列表上方回显，分页和状态轮询沿用同一组条件。
- 账号列表的套餐列仅附带显示提链排队、提链中和提链成功；未提取到链接时不显示失败标签或原因，具体结果仍可在任务记录中查看，符合资格的账号仍可重跑提链。
- 账号列表右上角提供「高级搜索」：多个条件用空格或 `/` 分隔，全部条件同时满足。例如 `优化协议 jp`、`开源协议/jp` 表示对应协议注册且历史注册出口国家为日本；`协议注册` / `protocol`、`开源协议` / `protocol_oss`、`浏览器注册` / `browser`、`jp` / `JP` / `日本` 可互换，地区也支持 `jp注册` 写法。历史搜索「协议」和 `方式:protocol` 仍只匹配本地优化 Protocol。注册方式按账号关联的最新注册任务快照判断，地区按账号记录的注册出口国家判断，缺失记录不会按当前配置猜测。普通文字搜索 ID、邮箱、姓名、邮箱来源和备注；也支持 `方式:开源协议 地区:JP`、`邮箱:example.com`、`姓名:张三`、`来源:outlook`、`备注:待整理` 和精确 `ID:123`。完整文字用双引号包裹，例如 `备注:"a/b"`、`姓名:"Alice Smith"`；`备注:jp` 或 `"jp"` 可搜索文字而不识别为国家。搜索覆盖全部分页并与列筛选组合，已生效的条件以可单独移除的标签回显；语法错误会在输入框旁提示。输入后自动搜索，回车立即搜索，清空恢复原列筛选结果，「清筛」同时移除全部条件。
- 页面刷新会恢复当前大菜单、二级菜单和配置分组，不会自动跳回总览；列表表头保持固定，长列表滚动时筛选条件和列名不会丢失。
- 四类列表保留原有全部功能，并统一面板外框、操作栏、按钮和表头样式；批量动作只在选中记录后出现，低频动作收进「更多操作」。列宽可拖动、自动记忆，也可一键恢复默认宽度。账号批量操作并发数位于「配置 → 系统设置 → 通用配置」。
- 账号列表默认每页 10 条，桌面行高随可用空间收紧，每格最多两行；时间列上方为创建、下方为更新，操作列上方为删除、下方为更多。2FA 已配置时直接复制验证码，未配置时提供「补充」。封号邮件平时仅显示「复查」，确认收到封号通知后显示红色「封号」；扫描中及不支持的来源禁用复查，原因保留在提示中。账号列宽可独立缩放，包括最后的操作列；拖动时优先与后一列交换空间，邻列达到最小宽度后再扩展整表，末列可独立调整；列宽自动记忆，仅在超出可用宽度时出现横向滚动条。
- 主侧栏与配置分组导航保持固定，滚轮不会串动主内容；仅在菜单或页面内容确实超过可用高度时出现纵向滚动。
- 历史列宽中操作列异常宽、出现大片空白时，升级后首次加载会只收紧操作列并保留其余列宽；收窄创建/更新时间列时同步缩短整表，避免把多余宽度转入操作列。后续手动拖宽操作列仍正常记忆。
- 动态调整注册线程数，提交后新任务立即使用最新值。
- 账号页的补全、查活、刷新 AT、查套餐、查封号邮件、Codex 操作和提链共用「配置 → 系统设置 → 通用配置 → ACCOUNT_BATCH_WORKERS」；修改后新入队任务立即按新值调度。
- 管理账号、邮箱池、Codex 凭证；模块子菜单与列表操作区保持吸顶，选中下方记录后无需回到页首。
- 邮箱资源池拆分为「资源总览 / 邮箱列表 / 邮箱子地址」，区分本地库存与按需平台，并可查看、手动租用和释放当前 WebUI 进程的 Email Butler 租约；子地址在独立菜单中查看归属和关联任务。
- Codex 授权只保留一个凭证管理页面；同步 sub2api 是列表批量动作，不再重复占用二级菜单。
- 配置页按用途合并为「注册设置、账号补全、浏览器设置、邮箱 / OTP、接码平台、代理与网络、Codex、提链、系统设置」9 个主菜单，菜单内按小节组织字段；Codex Token 自动刷新统一放在「系统设置 → 定时任务」，每项配置只展示一次。保存后继续支持热加载，旧分组入口和上次停留位置会迁移到对应新菜单。
- 桌面端配置页固定左侧分组导航，超长配置只在右侧内容区滚动。
- 总览套餐分布会区分「Free」「Free · Plus 免费试用」「Free · Plus 半价」「Free · Plus 其他折扣」和历史优惠待复查；账号页的「套餐优惠」列只展示 Plus 优惠，同一国家有多个 Plus 活动时按免费、减免比例、优惠期限选择最高优惠。鼠标悬停、键盘聚焦或点击可查看 Go 与 Plus 的全部活动，Plus 优惠筛选仍按 Plus 判断。旧记录未查询过 Go 时在详情中显示待查询，查询失败保留上次成功快照。网络出口只显示当前代理平台与活跃出口，注册流水线显示当天成功、部分成功和失败任务数。
- Roxy 团队/项目可在配置页获取并保存。
- 发起注册时可按批次开启调试模式；支持多并发任务独立抓取 Roxy 页面网络、WebSocket、控制台错误和 protocol HTTP 请求，失败后限时保留浏览器现场，并可在任务日志中对比同批成功任务或下载脱敏 HAR。
- 调试保留期间，任务中心列表、所选 Run 和当前步骤显示“调试暂停”；步骤耗时固定在实际暂停时刻。底层 Run 仍保持执行中，结束调试后才收口；历史记录缺少暂停时间时显示“—”，不倒推时间。
- 单条重跑接口 `POST /api/jobs/<job_id>/retry` 和批量重跑接口 `POST /api/jobs/retry-bulk` 均可传 `debug_enabled: true`，为新注册、继续验证及账号配置补跑开启完整抓包和失败现场保留；未传时继承原任务设置，不修改全局配置，也不切换已经运行的任务。页面上的单条重跑、选中重跑和批次失败重跑均使用当前调试勾选。独立 Codex、套餐补跑暂不支持完整抓包时仍正常入队，页面明确提示仅保留步骤日志。
- 邮箱领取失败且同一 Attempt 仍为 `created`、远端身份与账号均未开始、尚无邮箱和密码时，可从原邮箱来源重跑领取；子任务已经领到邮箱后，即使根任务尚未回填地址，也按同源、同 Attempt 的邮箱快照继续，后续失败不会改领其他邮箱。进入认证或已有提交事实的任务仍复用原身份与断点。
- 未开启调试模式的任务，最终失败时也会自动保存轻量脱敏失败诊断（页面 URL/标题/DOM 摘要、资源时序、浏览器错误、失败请求元数据和截图）；成功任务不抓包、不暂停浏览器。诊断结果可在任务日志的「失败诊断」区域查看。
- 根据当前邮箱、代理、浏览器、Codex、提链和 sub2api 配置动态判断功能是否可用；缺少必要配置时，前端按钮会禁用，后端接口也会拒绝执行并返回具体原因。
- 批次进度按邮箱逐行展示，包含准备邮箱、打开浏览器、打开注册页、提交邮箱、认证跳转、邮箱验证码、填写资料、获取 Token、Codex 等阶段；顶部显示成功/失败/运行/等待和总耗时。
- 发起注册页只读取当前选择批次的完整步骤，其他批次仅在切换后加载；下拉框只读取批次摘要。分页任务查询不附带批次步骤。当前批次结束后停止自动轮询，切换批次、手动刷新或提交新任务时重新读取；旧请求返回不会覆盖新选择的批次。

### 2026-08-13 更新记录

- 运营页面统一为总览、注册、账号、Codex、邮箱池和配置六个模块；注册任务、账号、Codex 凭证和邮箱列表共用筛选、列宽记忆、分页、批量操作及二级菜单结构，页面刷新后恢复上次模块和子页面。
- 注册批次支持停止运行中任务、取消排队任务、重跑失败任务；单个失败任务也可按断点语义重跑。当前批次逐账号展示每个阶段及阶段耗时，Codex 后继续展示“查套餐”和“完成”，完成后显示任务总时间；失败原因在对应失败阶段查看。
- 注册流程结束时尚未确认成功的任务统一按失败处理，保留原邮箱、密码和 Attempt 事实。已保存原密码的任务，即使账号尚未落库或旧提交结果未知，也可直接重跑；系统自动创建同一 Attempt 的 `registration_resume`，沿用原邮箱、原密码继续认证，无需人工核对。没有保存密码且尚未进入账号创建的任务复用原邮箱重跑；仍有未决提交时保留原结果。活跃运行、废号、恢复资料缺失或不匹配仍会拦截；Remail 付费订单结果未知时仍须先恢复原订单，不能重复下单。原注册任务和续跑子任务的单个、批量及任务中心入口共用校验，同链已有同类重试时复用已有运行。新任务统一记录失败，历史执行记录和任务中心筛选保留原状态并开放相应重跑入口；已确认注册成功的账号仅补跑未完成的后处理。
- 邮箱提交和 OTP 等待减少固定等待：Email Butler 按目标邮箱和任务时间窗口精确读取验证码，已入库时只做轻量轮询；各驱动输出提交邮箱、OTP、手机验证和 callback 等阶段耗时。NextAuth 先单独完成只读 CSRF GET，再在 signin POST 即将发送前写入 Attempt 提交事实；旧未知结果持续保留，使用原密码的显式续跑可以继续新的登录流程。
- Roxy 资料提交使用独立回执关联 `create_account` 请求；本次请求明确返回 HTTP 4xx 时及时报告 `account_create_http_<状态码>`，保留原身份和密码供原任务续跑。原身份密码登录直接进入可信地址上的可见资料表单时，交给资料阶段继续处理。普通流量观测仅解析有限大小的认证失败 JSON，诊断只记录固定错误枚举，原始正文不进入普通日志或流量摘要；HTTP 2xx 仍须取得匹配原邮箱的完整登录会话才算注册成功。
- 当前资料请求明确返回 HTTP 400 且错误码为 `user_already_exists` 时，保留拒绝回执，只进行一次有界的登录会话对账。取得 Token 且完整邮箱精确匹配才继续保存账号；否则保留原身份和续跑入口。后续原任务续跑使用保存的原密码登录，再次进入资料页时不重复创建账号。历史通用 HTTP 400 不会被推断为此错误。
- 密码表单持续未加载且本次密码尚未排队时，可在原预算内 GET 当前可信密码页一次，随后重新核验原邮箱再提交原密码。显式续跑确认新的邮箱登录后，保留先前邮箱 403/429 失败回执，继续当前未提交密码页的恢复。当前会话诊断明确返回 `missing_session` 时，使用原身份有界重建登录，最多两次，并共享固定恢复截止时间；新登录明确提供可用 OTP 页时继续该验证路径。只有 HTTP 404 不会触发密码页会话重建，旧会话迟到响应也不能冒充当前会话。已派发或结果未知的密码、OTP 和资料动作沿用原回执。
- 原任务 `registration_resume` 在本轮首次登录 GET 遇到明确代理连接故障，且已确认关闭本次失败连接时，可在现有重试上限内重新领取公共池线路，继续使用原邮箱、密码和 Attempt。只有确认浏览器实际使用该租约才标记线路故障；HTTP 拒绝和页面超时保留各自原因。
- Roxy `/browser/create` 明确返回 Profile 总额度不足时立即失败；仅 `/browser/open` 遇到可恢复的窗口忙状态会在当前任务内等待。等待上限和间隔由 `ROXY_WINDOW_WAIT_TIMEOUT`、`ROXY_WINDOW_WAIT_INTERVAL` 控制。
- 注册完成后的套餐查询纳入任务完整进度；查活和查套餐按账号注册地区领取独立短期线路，网络预检失败时释放旧线路并换新代理重试。
- 查活优先在线验证现有 accessToken；只有 AT 缺失、失效或用户明确要求刷新时，才重新登录刷新，避免正常账号重复登录。邮箱失效账号优先使用已保存的 OpenAI 密码登录，并按服务端要求完成 TOTP 2FA；缺少密码或所需 TOTP 密钥时明确报告原因，仍保留手动重跑入口。密码登录不能绕过服务端强制要求的邮箱验证。
- 账号页新增「任务实例」二级菜单。查活、AT 刷新、查套餐和查封号邮件都会创建可检索任务，保存脱敏阶段事件、线路、验证方式、结果和耗时；失败实例可以从任务列表手动重跑。
- accessToken 会解析并保存签发/过期时间；账号列表展示 AT 剩余时间，后台可在到期前按配置自动创建刷新任务。
- 单个、批量以及注册任务断点触发的 Codex 补跑统一创建 `codex_retry` 任务实例。账号菜单不再单独提供“补跑日志”，补跑阶段、错误、线路和结果统一从任务实例查看，失败实例可直接重跑。
- Roxy 注册和查活的 NextAuth 兜底会确认浏览器是否真正落到 `auth.openai.com` 或明确下一步；登录空壳、邮箱框短暂清空只作为过渡态等待。若页面已经进入密码、OTP 或登录完成状态，会停止刷新、重填邮箱和重复导航，避免竞态导致空白页或覆盖已成功的跳转。

---

## 环境要求

- Python 3.10+（项目声明下限；当前锁已在 CPython 3.12.13、macOS x86_64 验证）
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

`requirements.txt` 和 `requirements-dev.txt` 是基于已验证 Python 3.12.13 环境
重新解析的版本锁，不是主环境 `pip freeze`，也不是无需重解析即可覆盖所有平台的
wheel 锁。使用其他 Python 版本或操作系统时，请在独立 resolver 环境重新解析并
运行 `python -m pip check`。依赖与锁覆盖检查：

```bash
.venv/bin/python tools/check_dependencies.py
.venv/bin/python -m pip check
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

账号、注册任务、四类邮箱池、代理租约、代理池库存、Remail 订单意图和 Codex 凭证均由 PostgreSQL 行级表支撑（`registered_accounts` / `registration_jobs` / `email_pool_*` / `proxy_leases` / `proxy_pool_resources` / `remail_order_intents` / `codex_credentials`），可行级更新、可跨进程原子抢占。`app_collections` 仅保留调度状态、兼容集合和迁移期旧数据，不是正常列表的事实来源。

账号、注册任务、Outlook 和 iCloud 邮箱池不再生成根目录 JSON/TXT、`accounts/` 批次归档或 `accounts_viewer.html`，运行时只读写 PostgreSQL。仍有外部消费者的通用 API、域名邮箱和 Codex 兼容产物由后台按需生成；日志和浏览器缓存仍保留在文件系统。

结构、迁移步骤与开发约定见 [`docs/architecture/storage-architecture.md`](docs/architecture/storage-architecture.md)。

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

准备外部导入文本（示例文件只描述格式，不是运行时库存）：

```bash
cp 用于注册的邮箱.txt.example /tmp/outlook-import.txt
```

每行格式：

```text
email----password----clientId----refreshToken
```

也可以在 WebUI 的「邮箱池」页面导入；导入弹窗会先预览新增、已存在、重复和无效行，确认后只写入 PostgreSQL 的 `email_pool_outlook`，不会保存或改写源文件，也不会创建注册账号或写入 ChatGPT / Codex Token。命令行可使用 `tools/import_outlook_pool.py --file PATH`。

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

#### 通用邮箱子地址

在「邮箱池 → 邮箱子地址」点击「生成子邮箱」，选择来源和数量，预先生成
`母地址+6位随机字母数字@域名` 库存。列表提供表头筛选、分页、勾选复制及未领取
库存的停用/恢复操作；已有任务归属的地址不能重新投入库存。
在「配置 → 邮箱 / OTP → 邮箱子地址」启用对应来源后，新任务只领取已生成的
子地址，库存不足时提示补充后重跑，不再临时生成。首期接入 `icloud_hide` 的本机
`forward_imap` 和具备完整收件人信息的 Outlook 取信链路；固定取码 URL、
Email Butler 裸验证码接口及付费订单来源不会自动开放派生。

```dotenv
EMAIL_DERIVATION_ENABLED=False
EMAIL_DERIVATION_SOURCES=icloud_hide
EMAIL_DERIVATION_MAX_CHILDREN=3
EMAIL_DERIVATION_TAG_LENGTH=6
```

每个母邮箱默认累计生成 **3 个**子地址；后续提高上限时保留已有地址，只增加
剩余额度。这里母邮箱指一个原始 HME 别名或 Outlook 邮箱，不是整个 Apple 账号。
母地址已注册或已换出仍可在资源有效时派生，不把原地址重新放回可用池。
子地址仅保存在 PostgreSQL，不创建新的 Apple 隐藏邮箱。人工生成不依赖注册领取
开关，生成时固定母资源与收件配置；开关只控制新任务是否从子地址库存领取。
母邮箱被标记“邮箱失效”后停止新领取和新派生，容量预览不再计入剩余额度；
已有子地址、账本状态和同一领取身份的恢复保持保留。

新任务冻结入队时的领取选项，子地址绑定原 root/Attempt。普通失败、重启和结果
不明继续原地址；成功时与账号在同一事务写回。子地址不跨任务回收，关闭派生仅
停止新任务领取，已有账号仍按持久绑定取码。CLI 的 `--mail-acquisition-id` 可复用
原领取意图。预生成库存为 `available`，停用库存为 `disabled`，领取后为 `reserved`，
注册绑定账号后为 `used`；历史 `replaced/retired` 继续保留。所有状态都占用累计
生成额度。重复提交同一次生成请求会复用原结果，未生成的缺口会明确提示。
零结果和部分生成也保留原请求结果；补充额度或修复配置后，发起新的生成操作即可继续补库。

取码按原始完整收件地址隔离，不能直接读取母收件箱最新验证码。HME 转发可能
改写 `To`，因此会核对 `Received for`、保留的完整子地址及 HME 母资源证据；
当前目标平台的 SendGrid 邮件还可从 iCloud 原始 SPF 通过记录中完整还原收件地址，
仅接受已验证的发信域、明确 VERP 模板和同母证据，不按随机后缀子串猜测。
母地址存在子地址历史时，无法确认归属的邮件不会返回给母账号。同一完整地址的
认证在发码前取得独占租约，不同子地址可以并发。

收件配置有持久版本引用。更换最终 Gmail 不会让历史绑定静默改读新邮箱；应用
密码的版本化引用保留在 `.env`，普通 API 不返回凭据或原始邮件。关联已有子地址
的母资源删除会停止新分配并保留恢复资料。实际转发目标迁移需要明确验证并切换
绑定的收件配置，不应仅覆盖全局邮箱字段。

完整约束、能力矩阵和发布顺序见[通用子地址设计](docs/superpowers/specs/2026-10-20-email-address-derivation-design.md)。

#### iCloud Hide My Email（`icloud_hide`）

先在本机启动 `icloud-hme` sidecar，再到 WebUI「配置 → 邮箱 / OTP → iCloud 隐藏邮箱」填写服务地址，账号 ID 留空即可自动发现全部 active 账号；保存后点击“连接并同步”。推荐配置：

```dotenv
USE_EMAIL_SERVICE=True
EMAIL_SOURCE=icloud_hide
ICLOUD_HME_API_BASE=http://127.0.0.1:8081
ICLOUD_HME_ACCOUNT_ID=
ICLOUD_HME_AUTO_CREATE=False
```

turb 只保存别名库存、领取状态和所属 sidecar 账号 ID；Apple Cookie 和 iCloud App 专用密码保留在 sidecar 中。`ICLOUD_HME_ACCOUNT_ID` 留空时会自动发现并同步所有 active iCloud 账号，填写后固定使用指定账号（适合排障或回滚）。Gmail 转发收码支持本机 `forward_imap` 直连和生产 `forward_butler` 两种模式；本机调试/注册可直接连接 Gmail，生产链路仍由 Oracle Email Butler 接收。所有账号共用同一个最终 Gmail/Email Butler 收件箱，OTP 仍按原始隐藏邮箱地址匹配。每个注册任务领取一个别名，注册成功后永久占用；明确未消耗的失败任务才会把别名退回可用池。默认只复用已同步别名，库存为空时不会自动创建；持续自动创建建议由 sidecar worker 负责，turb 侧仅在排障或按需补充时开启 `ICLOUD_HME_AUTO_CREATE`。

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
- 本机收码使用共同的单调时钟截止时间，覆盖建连、登录、只读选箱、搜索、逐封读取和轮询；每步还受 `ICLOUD_HME_REQUEST_TIMEOUT` 限制。按最新候选使用 `BODY.PEEK` 取信，取得有效码即停止扫描并直接关闭连接，不等待 LOGOUT。日志仅记录阶段、数量和耗时。异常网络执行最多占用 8 个后台槽位，等待槽位也计入收码预算；晚到连接会被关闭，不接受超过总期限才返回的验证码。
- 真实 IMAP 连接使用 UID 搜索和读取，避免邮件删除引起序号漂移；批量封号邮件扫描每次最多读取 20 封并按响应 UID 归属，收码仍逐封读取并在取得有效码后立即结束。日期月份固定为英文，不受本机语言影响。
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

#### MailCode 与西瓜邮箱接码

在 WebUI「配置 → 邮箱 / OTP」填写所选供应商的密钥及商品信息，并在邮箱来源中启用 `mailcode` 或 `xigua`。注册批次和换绑邮箱仍须明确选择本次来源，不会在失败时切换到其他供应商。

```dotenv
# MailCode 固定使用官方服务地址；商品可用配置页的“查询商品与余额”确认
MAILCODE_API_KEY=你的MailCode_API_Key
MAILCODE_PRODUCT_ID=你的商品ID
MAILCODE_REQUEST_TIMEOUT=20
MAILCODE_CHANNEL_WAIT_SECONDS=60

# 西瓜提供邮箱与邮件验证码
XIGUA_API_BASE=https://xigua.dasiqo.com
XIGUA_API_KEY=你的西瓜_API_Key
XIGUA_OFFER_ID=你的Offer_ID
XIGUA_REQUEST_TIMEOUT=20
XIGUA_POLL_ATTEMPTS=10
XIGUA_POLL_INTERVAL=5
```

两种供应商的订单身份、原请求及已购邮箱保存在 PostgreSQL `mail_provider_orders`，密钥只保存在 `.env`。同一个注册或换绑任务重跑时继续原订单和原邮箱；请求异常后保留原幂等键，不另建随机购买意图。MailCode 已购但通道尚未就绪时，下次继续准备原通道；验证码按每个邮箱持久化服务端游标，支持分页和重启恢复，保留前导零，不按验证码数字去重。西瓜按精确订单关联恢复，并要求连续两次确认相同验证码。普通释放不取消已购邮箱或退款。CLI 可用 `--mail-acquisition-id` 继续同一领取意图；历史 `--remail-acquisition-id` 参数继续兼容。

#### Remail 开放 API（`remail`）

在 WebUI「配置 → 邮箱 / OTP → Remail」填写 API Key，并在通用邮箱设置的「邮箱来源」中启用 Remail。发起注册或换绑邮箱时，再选择本次使用 Remail。也可以在 `.env` 中配置；默认值由 `config/schema.py` 统一维护：

```dotenv
EMAIL_SOURCE=remail
REMAIL_API_BASE=https://remail.aishop6.com
REMAIL_API_KEY=你的Remail_API_Key
REMAIL_PROJECT_ID=2
REMAIL_EMAIL_SUFFIX=outlook.com
REMAIL_SERVICE_MODE=purchase
REMAIL_SUPPLY_POLICY=public_only
REMAIL_ORDER_WAIT_SECONDS=30
REMAIL_REQUEST_TIMEOUT=20
```

项目 ID 和邮箱后缀应与平台项目列表一致。`purchase` 为可重复收件的长效购买，`code` 为短效接码，后续登录或账号操作能否收码取决于服务是否仍有效。`public_only` 只使用公开库存，`private_first` 优先使用自己的库存。订单未立即返回收件凭证时，客户端最多等待 `REMAIL_ORDER_WAIT_SECONDS` 秒；单次请求超时由 `REMAIL_REQUEST_TIMEOUT` 控制。接口说明见 [Remail 开放 API 文档](https://remail.aishop6.com/docs)。

注册和换绑统一通过 Remail coordinator。`remail_order_intents` 是下单事实表：先持久化 `prepared`，只有一个进程能 CAS 到 `submitting` 后发出付费 POST；POST 返回订单号后立即写入 `order_created`，再进行有界 GET 取回完整凭证。进程在 `submitting` 或 `request_unknown` 中断时只恢复原订单，不按幂等请求头自动重放 POST。订单交付前的私有凭证会先写入数据库，只有 durable 状态为 `delivered` 且凭证完整时才交给注册或换绑流程。

CLI 支持 `--email-source remail` 和 `--remail-acquisition-id PREFIX`。首次运行可以省略前缀，程序会按批次和序号生成持久标识；对未知订单重跑时必须复用同一个前缀，例如：

```bash
python main.py --count 1 --email-source remail --remail-acquisition-id cli:recovery-20261013
```

该参数是稳定标识前缀，不是供应商订单号；批量任务会在末尾追加 `:1`、`:2` 等序号。WebUI/任务恢复使用原注册 root 的 acquisition ID，续跑子任务不会另起一份领取意图。核验接口只返回脱敏订单摘要，不返回邮箱、取件凭证或供应商私有字段。

Remail 属于运行时按需领取来源，无需导入本地 Outlook 邮箱池。API Key 只保存在 `.env`。订单关联、状态和恢复所需私有取件凭据写入 PostgreSQL 的 `remail_order_intents`；注册成功后账号私有上下文也可引用该恢复事实。进程重启后优先恢复原意图和原订单号。缺少原领取意图或订单号时保持待核验，不按完整邮箱搜索最新订单，也不会改领其他邮箱。普通列表和日志不展示取件凭据。

下单网络超时、服务端结果不明或订单交付凭据等待超时时，注册和换绑任务进入 `request_unknown`，禁止直接重试下单；需先在 Remail 控制台核对原订单，避免重复扣费。短效订单失效后不会自动购买新邮箱代替原地址。

---

### 2. 配置注册驱动

WebUI 批量注册使用全局默认驱动；未显式指定 driver 的 CLI/API 调用也使用该默认值。全局默认可在 WebUI「配置 → 注册与账号 → 注册主链路」设置，Roxy API 和环境参数在「配置 → 浏览器 → RoxyBrowser」调整；`.env` 中也可设置 `REGISTRATION_DRIVER`。配置默认值和可选项由 `config/schema.py` 统一维护。

#### 使用 RoxyBrowser 注册

```python
REGISTRATION_DRIVER = "roxy"  # 可选 protocol / protocol_oss / protocol_oss_2 / roxy / roxy_oss
ROXY_API_BASE = "http://127.0.0.1:50100"
ROXY_API_TOKEN = "你的Roxy API Key"
ROXY_WORKSPACE_ID = "你的workspaceId"
ROXY_PROJECT_ID = "你的projectId"
ROXY_ONE_PROFILE_PER_ACCOUNT = True
ROXY_REUSE_ACCOUNT_PROFILE = True
ROXY_DELETE_PROFILE_AFTER_RUN = False
ROXY_CREATE_USE_PROXY_POOL = True
```

如要无头：

```python
ROXY_OPEN_HEADLESS = True
```

Codex OAuth 使用独立的 `ROXY_CODEX_OPEN_HEADLESS` 开关，默认显示窗口；注册流程可以继续使用
`ROXY_OPEN_HEADLESS = True`。如果确认当前 Roxy 版本和 OAuth consent 页面支持无头模式，再单独将
`ROXY_CODEX_OPEN_HEADLESS` 设为 `True`。

#### 使用开源 Roxy 注册

在 WebUI「配置 → 注册与账号 → 注册主链路」中选择「开源 Roxy」，或设置：

```python
REGISTRATION_DRIVER = "roxy_oss"
```

来源为 [myfanhua/turb-gpt-free-register](https://github.com/myfanhua/turb-gpt-free-register)，固定提交 `9a0c55baa9b7d2f9c09ba6eea8cdec200a44eb5e`，许可证为 MIT。源码基线、实际使用的页面辅助及适配说明位于 [`core/registration/roxy_oss/upstream/`](core/registration/roxy_oss/upstream/UPSTREAM.md)。开源方式使用上游邮箱入口定位、资料字段识别与填写能力；密码、验证码和资料的提交确认、会话邮箱核验、原 Attempt 续跑、代理租约、Profile 生命周期、核心账号落库和后处理继续使用本地实现。上游单体注册入口不直接运行。

两种 Roxy 共用 Roxy API 和环境配置，均需配置可用的 RoxyBrowser 与统一代理池。注册批次冻结 `roxy_oss`，重跑保留原选择；`CODEX_OAUTH_DRIVER=same_as_registration` 对应本地 Roxy OAuth。账号高级搜索可用 `roxy_oss` 或「开源Roxy」区分来源。


#### 使用本地优化 Protocol 注册

```python
REGISTRATION_DRIVER = "protocol"
```

本地优化 Protocol 基于 `curl_cffi`、Sentinel/PoW 和代理池，带有本项目维护的阶段预算、密码/注册检查点、错误分类、未知结果保护和同 Attempt 续跑。已有优化与恢复逻辑留在 `core/registration/protocol.py`。

协议驱动在原注册 Attempt 内提前保存密码和提交阶段；超时或取消后沿用原邮箱、密码与 Attempt，按照服务端返回的密码、OTP、MFA、回调或资料页继续。CLI 也使用持久化 Attempt/Run；已保存核心账号后应补跑后处理，不重复注册。2FA 密钥在激活前保存为待确认，只有激活确认后才显示启用。完整 session 与 AT 在登录态预热、Codex 等后处理之前持久化，后处理失败不会抹掉核心成功。

OTP 轮询、验证码重试、退避与网络请求共用阶段预算；同步 HTTP 在途请求仍受底层 connect/read 超时约束，不保证持续响应的硬总耗时上限或即时取消。回调成功后只重试 session 获取，回调结果未知时停止自动重放。实现与验证边界见[协议注册可靠性实施记录](docs/development/2026-10-12-protocol-reliability-plan.md)。`wreq` 仅完成本地兼容性评估，默认后端仍为 `curl_cffi`。

#### 使用开源protocol-2 注册

```dotenv
REGISTRATION_DRIVER=protocol_oss_2
```

来源为 [wangshen233/turb-gpt-free-register-oss-20260928](https://github.com/wangshen233/turb-gpt-free-register-oss-20260928)，固定提交 `7df094e05e48a74eeacc4ff6e3c27165def21cae`。这是独立的 AuthFlow / wreq 实现，保留现有 `protocol_oss`。需要 Python 3.11+、`wreq==0.13.0` 和可运行的 Node.js；随项目依赖安装，不需要上游 WebUI、SQLite 或浏览器引擎。

在「配置 → 注册与账号 → 注册主链路」选择「开源protocol-2」后，新的注册批次使用该默认驱动；API 也支持通过 `registration_driver` 为单个批次指定。驱动使用邮箱验证码和密码，入队时冻结这一要求。邮箱领取/取码、代理租约、原密码检查点、任务进度、账号保存和后处理均使用本项目服务；失败后可通过原任务重跑，恢复原邮箱与已保存密码。`CODEX_OAUTH_DRIVER=same_as_registration` 对应本地 Protocol OAuth。账号高级搜索支持 `开源protocol-2`、`protocol-2` 或 `方式:protocol_oss_2`。

上游组件与本地适配说明见 [UPSTREAM.md](core/registration/protocol_oss_2/upstream/UPSTREAM.md)。原组件许可证为 AGPL-3.0，保留在该目录的 `LICENSE`；不将其标为主项目的 MIT 代码。上游独立邮箱、代理轮换、SQLite、凭据明文日志、付费套餐检测及内置 Codex OAuth 不接入。

#### 使用开源 Protocol 注册

```python
REGISTRATION_DRIVER = "protocol_oss"
```

该 driver 固定同步自 [myfanhua/turb-gpt-free-register](https://github.com/myfanhua/turb-gpt-free-register)，基线提交为 `83721dc33a83b3e09dfdf7d91cc511b0124d9b4c`，许可证为 MIT。注册协议代码和许可证位于 `core/registration/protocol_oss/upstream/`，本地适配位于 `core/registration/protocol_oss/__init__.py`；上游入口 `main.py` 不直接运行。

| 对比项 | `protocol` 本地优化版 | `protocol_oss` 开源版 |
| --- | --- | --- |
| 注册请求流程 | 本项目维护，含阶段预算、密码检查点和同 Attempt 恢复 | 固定上游协议顺序，单独适配，不回退到本地实现 |
| 认证方式 | 按 `REGISTRATION_AUTH_MODE` 选择 OTP 或密码 | 上游固定邮箱 + 密码；入队快照会记录实际 password 模式 |
| 本地能力 | 本地邮箱、代理、Attempt/Run、PostgreSQL 和后处理 | 同样使用本地邮箱、代理、Attempt/Run、PostgreSQL 和后处理 |
| 后续更新 | 直接维护本项目实现 | 按 `upstream/UPSTREAM.md` 更新隔离源码，再验证适配器 |

OSS 版本的 Codex OAuth 仍调用本项目的 Codex 实现；`CODEX_OAUTH_DRIVER=same_as_registration` 在 OSS 批次中解析为本地 Protocol OAuth，因为 Codex 不运行上游注册 driver。任务列表按每个任务的冻结快照显示来源；账号搜索使用「优化协议」和「开源协议」分别匹配，历史搜索「协议」仍指本地优化 Protocol。

---

### 3. 配置代理

在 WebUI「配置 → 代理与网络」设置唯一的默认代理池。注册、查套餐、查活、刷新 AT、补密码、补 2FA、邮箱换绑和 Codex OAuth 都向池领取租约；业务页面不再选择代理平台或直连。池内的 `PROXY_POOL_SOURCE` 可选 `1024proxy`（1024Proxy）、`711proxy`（711Proxy）或 `manual`（手动地址），`PROXY_POOL_DEFAULT_COUNTRY` 只为没有指定国家的池请求及缺少历史国家的账号动作提供默认值。保存来源或供给字段时，当前 API 来源必须已有对应提取配置，手动来源必须至少有一条完整代理地址；尚未配置代理不会阻止保存其他分组。

新注册的国家在「配置 → 注册与账号 → 注册主链路 → 注册国家」设置，对应 `REGISTRATION_COUNTRY`（默认 `JP`）。WebUI/API 批量注册在提交入队时将它冻结为任务的 `config_snapshot.proxy_country`，运行和重跑沿用原快照；CLI 未提供任务国家时也读取注册国家。业务只向代理池申请对应国家，不读取池默认国家或供应商国家字段。缺少国家库存时由池按需求补货，不回退其他国家。新字段尚未配置时兼容读取原有效池默认国家、旧 1024Proxy 国家或 API 的 `region`；保存注册国家后与这些旧字段独立。已有任务优先保留原快照或实际出口国家，均缺失时才使用当前注册国家。

手动地址示例（只写入 `.env`，不要把真实凭据写入源码）：

```dotenv
PROXY_POOL_SOURCE=manual
PROXY_POOL_DEFAULT_COUNTRY=JP
PROXY_POOL="socks5h://user:password@proxy.example.test:1080"
```

手动地址也必须经过健康和实际出口国家检测；只填写 IP 时需要补全协议、端口及必要的认证信息。供应商提取、出口复检和补货在后台 worker 中执行，任务线程只领取 PostgreSQL 库存中的已检测线路。WebUI 启动时预热代理池，CLI 首次领取时懒启动；缺少配置、数据库不可用或没有匹配国家的线路时不会回退直连。Roxy 与协议流程使用同一租约契约，Roxy 自动把已领取租约写入 Profile 的 `proxyInfo`。

已有账号优先沿用实际注册国家，未记录时使用池默认国家；多国查套餐按其业务国家列表领取。修改池来源或平台参数只影响后续领取（包括已入队但尚未领取的任务），已发放租约继续到当前动作结束，不在认证中途换 IP。旧任务保存的 `direct`、`pool`、`registration`、`provider:*` 来源不再覆盖当前池，也不阻止历史任务重跑。新配置缺席时，旧 `REGISTRATION_PROXY_MODE=pool/1024` 分别映射为手动来源和 1024Proxy；旧有效国家或供给 URL 的 `region` 可迁移为默认国家，缺失或随机国家采用明确的默认值 `JP`。保存新字段后以新字段为准。

代理池 worker 数量支持热加载；WebUI worker 统计仅代表当前进程，库存容量和租约由 PostgreSQL 在多个进程间统一协调。将来新增平台只需扩展池的供应商适配与配置，不需要在每种业务里再接一次。

代理池预热 profile 取池默认国家、`PROXY_POOL_COUNTRIES` 额外国家，以及 `PLAN_CHECK_COUNTRIES` 的并集；同一来源、配置和国家只建立一份 profile。`PROXY_POOL_COUNTRIES` 只增加预热库存，不替代注册国家，也不改变 `PLAN_CHECK_COUNTRIES` 的业务国家和顺序。国家代码支持换行、逗号或空格分隔，保存时自动大写、去重并校验 ISO 两位代码。WebUI 的“代理池预热国家”和“独立查套餐国家列表”统一使用单行多选入口，可按中文名称或代码搜索、选择和移除国家；国家目录只表示可填写的 ISO 国家和地区范围，不代表供应商在所有地区都有可用库存。静态池同一完整 URL 来源的普通与国家 profile 可领取同一份已检测库存，指定国家时仍校验实际出口；预热不会复制 endpoint 或放宽独占、冷却与 IP 次数限制。

代理池的默认策略是全局最大容量 20、每个活动 profile 最少保持 2 条可用库存，代理不足时持续等待补货或线路释放，领取时要求剩余寿命至少 300 秒，后台每 60 秒复检，空闲回收阈值 300 秒，worker 数 2。`PROXY_POOL_WAIT_TIMEOUT=0` 表示持续等待，可手动停止任务；设为正数时才限制领取总等待时间并在到期后失败，调用方显式指定的 `timeout` 仍按指定期限执行。等待进度每 30 秒记录一次，供应商提取和出口检测仍使用各自的有界预算并退避重试；缺少配置或不可能满足的寿命策略仍立即报错。`PROXY_POOL_MAX_SIZE` 是所有配置共同使用的全局上限；容量缩减只退役 `ready` 库存，不踢出正在使用的线路。有其他配置的任务等待时，池可以回收其他配置的空闲 `ready` 库存来满足等待者。

`PROXY_POOL_MIN_READY` 表示每个活跃来源/地区预留的空闲底数，只计算检测新鲜、剩余寿命足够、没有任务占用且锚点有效的可立即领取线路。配置为 5 时，后台持续以 5 条空闲线路为目标；领取后不足 5 就唤醒补货。有任务等待时，目标是等待数加空闲底数，例如 3 个任务等待时准备 8 条。提取中、复检中的槽位只用于防止多个 worker 重复补货，不算可用线路。全局容量必须为正在使用的线路和空闲底数预留空间；供应商不可用、检测失败或容量不足时仍可能等待。库存快照提供所有已配置来源/地区的 `min_ready_total`；该合计超过 `PROXY_POOL_MAX_SIZE` 时显示容量不足提示，不宣称能够同时满足所有 profile 的底数。

注册和认证使用独占子租约 `pool_leased`；只有套餐查询明确启用复用时才使用 `shared`/共享子租约。正常释放进入按 `PROXY_1024_RECENT_TTL` 配置的 cooldown，冷却结束后可再次领取。明确的线路传输故障会保留故障原因；没有活跃子租约且原始寿命仍足够时进入有界的 `rotation_wait`，后台复检同一 endpoint，等待出口变化。检测到国家匹配的新 IP 后换代发布，沿用原 `expires_at`，不因复检或换代延长寿命；检测到原 IP 时继续等待，连续失败达到上限或剩余寿命不足则退役。旧出口锚点保留隔离和历史关联，不会因为 endpoint 换代而重新可用。无活跃关联的库存终态保留 7 天后分批清理；任务子租约历史保留。`PROXY_POOL_MIN_TTL` 必须小于 1024Proxy 会话时长，并为检测预留时间，不可能满足的组合会在提取前被拒绝。`PROXY_1024_MAX_ATTEMPTS`、`PROXY_1024_ROTATE_SESSION_TIME` 和旧 batch/rotate 开关仅为旧诊断或兼容调用保留，正常代理池不依赖它们，也不按任务 ID 派生供应商参数。

当前供应商请求固定 `region` 和 `time`，`num` 使用与池最大容量一致的有界候选窗口，上限 1000；跳过已占用或冷却线路，只检测并交付本轮预留槽位所需的数量，避免较大库存反复困在旧批量客户端的 64 条前缀。总 worker 大于 1 时固定保留至少一半（向上取整）给供给，复检最多占一半（向下取整）；例如 5 个 worker 为供给 3、复检 2。一个 worker 时交替处理供给和复检。各地区仍按等待和最近服务时间公平轮转，复检卡慢不能占满供给机会。候选全重复会记录明确原因并退避，不声称增加数量就保证获得新 IP。`time` 是供应商的粘性窗口，不保证每次领取都是新会话或新 IP；系统只记录实际检测到的出口 IP 和地区，不把“新租约”写成“已换新 IP”。可参考 [1024Proxy 动态住宅 API 文档](https://help.1024proxy.com/1024/1024proxy/dynamic-residential-traffic/api)，该文档只说明 `region`、`time`、`num` 等请求参数；连接池的并发和回收语义参考 [Psycopg 连接池文档](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)。

单条候选的出口检测发生 HTTP、连接或超时错误时，清理该候选并在共同预算内继续检测后面的候选；供应商提取失败、整轮预算耗尽或取消仍终止本轮。候选故障日志只记录检测阶段、异常类型、HTTP 状态码和脱敏端点。

WebUI「代理与流量」中的“代理池库存”只显示脱敏库存快照、状态和统计，不提供领取或释放操作。当前配置页的代理池字段只保存策略；完整供应商 URL、账号和密码仍只允许保存在 `.env`。

1024Proxy 推荐基线：

```dotenv
PROXY_POOL_SOURCE=1024proxy
PROXY_1024_API_URL=https://white.1024proxy.com/white/api?region=US&num=1&time=30&format=1&type=txt
PROXY_POOL_DEFAULT_COUNTRY=US
REGISTRATION_COUNTRY=US
PROXY_1024_PROTOCOL=http
PROXY_1024_SESSION_MINUTES=30
PROXY_1024_API_TIMEOUT=12
PROXY_1024_ACQUIRE_TIMEOUT=60
PROXY_1024_VALIDATE=True
PROXY_1024_VALIDATE_ATTEMPTS=2
PROXY_1024_RECENT_TTL=1800
PROXY_1024_ACQUIRE_INTERVAL=0.6
# 独立库存默认值：全局容量 20，最少可用 2，代理不足时持续等待
# 额外预热国家；不替代注册国家或 PLAN_CHECK_COUNTRIES，留空不额外预热
PROXY_POOL_COUNTRIES=
PROXY_POOL_MIN_READY=2
PROXY_POOL_MAX_SIZE=20
PROXY_POOL_WAIT_TIMEOUT=0
PROXY_POOL_MIN_TTL=300
PROXY_POOL_CHECK_INTERVAL=60
PROXY_POOL_MAX_IDLE=300
PROXY_POOL_WORKERS=2
# 注册页遇到线路级瞬时失败时，最多释放旧租约并换线重试 3 次（初始线路共最多 4 条）
REGISTRATION_PROXY_RETRIES=3
REGISTRATION_PROXY_RETRY_DELAY=1
# 查活/刷新 AT 申请线路遇到重复租约时，额外换线重试；不重跑已提交的认证步骤
ACCOUNT_ACTION_PROXY_RETRIES=2
ACCOUNT_ACTION_PROXY_RETRY_DELAY=1
```

- 后台按固定供给参数补充库存并检测实际出口国家；实际国家与请求国家不一致时，该库存不会发布给任务。
- 领取与释放通过 PostgreSQL 原子租约完成，多个 WebUI/CLI 进程共享同一库存；供应商白名单 API 没有单独的远程释放调用。
- 默认国家必须选择明确的 ISO 两位代码；池不使用随机国家替代业务目标国家。
- 粘性时间延长本身不产生流量，只有浏览器实际发出请求才消耗代理流量。30 分钟是注册 + 邮件等待的最低建议值，必要时可设更长。
- 日志和 UI 只应显示脱敏后的代理端点/出口 IP；完整 API URL 属于私密配置，只放 `.env`。

账号动作参数在「配置 → 注册与账号」按功能集中：查询套餐、查活与刷新 AT、补密码、补 2FA、邮箱换绑及 Codex OAuth。这里只维护动作开关、预算和重试等行为；代理来源统一由池管理。查套餐、查活使用已有 Token，但也领取池租约。独立查套餐仅在开启“查询支付方式”后为有效 Plus 优惠创建一次结账预检会话。邮箱、短信、CPA/Sub2、提链服务和 Roxy 控制 API 仍使用各自连接配置。

在「注册与账号 → 查询套餐」中可设置 `PLAN_CHECK_PROXY_ALLOW_REUSE`（查询套餐允许复用 IP），默认 `True`，保存后热加载。它仅影响使用代理池的查套餐（1024Proxy/静态代理池）：允许复用 IP；1024Proxy 仍验证出口国家，静态代理池仍使用健康校验。设为 `False` 后查套餐恢复严格独占和冷却。开启复用时，`PLAN_CHECK_PROXY_REUSE_LIMIT` 默认 `3`，取值范围 `1-100`，按实际出口 IP 在租约有效期内累计，包含首次租用；释放或进程重启不会清零，达到次数上限后会换线。注册及认证任务继续使用独占租约，其他账号动作不受此开关影响。

账号页独立「查套餐」支持 `PLAN_CHECK_COUNTRIES`，默认按 `JP / VN / IN` 查询。可在「配置 → 注册与账号 → 查询套餐」按中文名称或代码搜索并多选国家，收起时为单行摘要，保存时自动大写、去重并保留选择顺序；留空回到按账号注册国家的单次查询。国家列表和业务预算在任务入队时冻结，手动重跑沿用该任务的国家列表；实际代理来源在领取时读取当前池配置。注册同步查询、注册自动补查及注册任务内套餐重跑仍沿用原有单次查询。

多国家查询只使用检测到对应国家出口的线路，不会把账单国家、注册国家或未知出口当作本次查询国家。使用 1024Proxy 时，同一个供应商连接按国家维护独立库存 profile；已配置国家会预热，各国共用 `PROXY_POOL_MAX_SIZE` 全局容量、复检和实际 IP 复用限制，代理池库存页显示各国统计。静态代理池也按目标国家区分 profile，在有界检测预算内挑选实际出口匹配的候选；确实没有对应国家线路时按该国等待预算记录失败。`PLAN_CHECK_COUNTRY_WAIT_TIMEOUT` 默认 `60` 秒，可设 `5–300` 秒；每个国家首轮领取只占用最多 5 秒切片，缺货即轮转其他国家，后续公平补试继续消耗同一国家在原 Run 内累计的 60 秒等待预算，不因切片或进程恢复重置。每个 Run 的截止时间、等待切片和 HTTP 尝试次数写入 `operation_runs.data.plan_country_progress`，恢复时沿用原预算。

每个国家完成后立即保存其 Go / Plus 活动、时间和状态；一国失败不影响其他国家，失败国家保留上次成功快照并标明历史。账号列表每条数据最多两行：一国或两国时按现有摘要展示；三国及以上第一行展示当前优先的最佳结果，第二行显示“另 N 国”，并独立保留失败数、历史数等不可裁切提示。完整国家结果、失败原因、历史时间和活动证据继续在现有浮窗与详情中查看，悬浮、聚焦、点击、键盘和滚动定位保持可用。免费试用使用 `JP：支付方式`，折扣使用 `JP-50%-3：支付方式`（减免 50%，持续 3 个月；其他周期保留单位）。所有国家的 Plus 均无优惠时显示「无优惠」，尚未查明时显示「待查询」；Go 活动及无优惠国家的完整结果保留在浮窗和详情中。部分国家失败时，任务标为「部分成功」，可继续重跑。全部失败、取消和重启中断分别显示。`PLAN_CHECK_PAYMENT_METHODS_ENABLED`（查询支付方式）默认 `False`，位于「配置 → 注册与账号 → 查询套餐」。关闭时只查询套餐、优惠和额度，不创建结账会话，减少额外耗时与网络失败；开启后，独立查套餐会为每国当前最优的有效 Plus 活动创建一次结账预检会话，按实际响应显示 `cs_live` / `oaics`、可用支付方式以及应付金额和币种；金额未知时不显示为零。Go 活动及注册流程内查询只保留优惠资格，不创建预检会话。支付方式是服务端本次返回的选项，不代表已绑定或已支付；本流程不会提交支付或确认订阅。支付预检失败仍保存套餐优惠，并将任务标为「部分成功」供重跑；旧记录或未执行预检的活动显示「支付方式待查询」。每国预检最多使用 60 秒预算，同一次预检不重发创建请求。该开关在新任务入队时冻结，手动重跑沿用原任务设置，正在执行的任务不因配置切换改变查询范围。切换开关不会主动清理账号或历史任务；关闭后的新查询按原规则更新优惠快照，未执行预检的支付字段显示待查询，旧证据仍可从历史任务查看。

历史单国优惠沿用相同格式，国家只读取对应成功查询快照中的实际出口国家；没有记录时显示「国家未记录」，不借用注册国家或当前线路配置。单国、多国及无优惠、待查询等状态统一使用纯文字行，位置、字号和颜色规则一致，不再混用胶囊底色。完整优惠期限仍保留在浮窗中。

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

#### 本地 L 接码服务

`SMS_PROVIDER="l"` 时，本项目把 L 服务作为内部接码客户端依赖。这里仅记录客户端必须遵守的接口约定；L 服务自身的后台管理、完整错误码和调试示例不属于本仓库文档范围。

配置统一放在 `.env` 或 WebUI「配置 → 接码平台」，不要把授权码写入源码：

```dotenv
SMS_PROVIDER=l
SMS_SERVICE=openai
SMS_COUNTRY=10
SMS_MAX_PRICE=0.05
L_API_BASE=http://localhost:8788
L_ADMIN_AUTH_CODE=你的后台授权码
```

所有请求均为 JSON，并携带 `Authorization: Bearer <L_ADMIN_AUTH_CODE>`：

| 用途 | 接口 | 本项目发送 | 本项目读取 |
|---|---|---|---|
| 获取号码 | `POST /api/admin/l/take-phone` | `service`、`country`，可选 `maxPrice` | `item.id`、`item.phone` |
| 获取验证码 | `POST /api/admin/l/fetch-code` | `id` | `code`；空字符串表示继续等待 |
| 释放号码 | `POST /api/admin/l/release` | 单个 `id` 或批量 `ids` | `released` / `updated`、`failed` |

`item.id` 是 L 服务的号码记录 ID，必须原样保存并用于后续取码和释放；`item.phone` 会在客户端按 `L_PHONE_PREFIX` 做号码规范化。服务返回非 `200`、`error`、`NO_NUMBERS` 或 `NO_BALANCE` 时，客户端会转换为对应的接码异常。号码使用完毕或任务失败后由现有释放/取消流程处理，不要在业务流程外重复释放。

`SMS_CODE_WAIT` 是单个号码等待短信的硬上限，`CODEX_PHONE_TOTAL_TIMEOUT` 是取号、页面操作、
等待短信和换号合计的整段硬预算。号码超时后，取消任务会交给后台持久化队列，不再阻塞注册线程。

GrizzlySMS 的订单取消不是“取号后立即取消”：程序会把待取消订单持久化到
`logs/run/sms_cancel_queue.json`，由单一后台 worker 根据平台允许的时间执行取消。
`EARLY_CANCEL_DENIED` 会按平台返回时间或退避策略延后处理，不会高频轮询；WebUI 重启后会自动恢复队列。
`logs/run/` 是运行时私有目录，不得提交 Git。手机号国家选择会按号码国际区号同步页面国家选项；如果页面明确只允许
WhatsApp 而不是 SMS，当前号码会判为不可用并进入换号流程。

CPA 授权地址来源：

```python
CODEX_AUTH_URL_SOURCE = "cpa"
CPA_MANAGEMENT_URL = "你的CPA管理地址"
CPA_MANAGEMENT_KEY = "你的CPA管理密钥"
```

### 当前设计与适配规则

下面这些规则同时适用于 WebUI 自动注册、单账号操作、批量操作和 CLI。修改相关功能时必须一起检查所有入口，不能只修其中一条链路。

#### 代码分层与运行时

- 项目按 `config/`（声明式默认值）→ `core/`（驱动与业务服务）→ `webui/routes/` 和 `main.py`（WebUI / CLI 入口）分层；`core/` 不反向依赖 `webui/`。
- 注册由 `core.registration.dispatcher.run_registration()` 按 `REGISTRATION_DRIVER` 分发，Codex OAuth 由 `core.codex_oauth.run_codex_oauth()` 按 `CODEX_OAUTH_DRIVER` 分发。驱动必须使用统一参数和任务进度上报接口。
- `webui/app.py` 只负责组装应用；领域路由位于 `webui/routes/`，`webui/runtime.py` 负责启动恢复和后台 worker。新增长期任务时必须补充启动恢复，避免重启后记录永久停在 `running`。
- WebUI 只维护现代界面，统一使用 `webui/templates/index.html` 和 `webui/static/js/modern/`。旧书签中的 `?ui=legacy` 和浏览器保留的 `ui_mode=legacy` Cookie 仍返回现代页面。涉及页面结构、脚本或接口契约的改动，应检查现代界面、相关回归测试及真实浏览器行为。
- 配置页保存到 `.env` 并热加载，不修改 `config/*.py`。需要读取热加载值的运行时代码应通过配置模块访问，避免 `from config import X` 形成过期绑定。

#### 邮件验证码

- iCloud 隐藏邮箱转发到 Gmail 时，本机可使用 `Gmail IMAP → turb` 直接取码；生产 `forward_butler` 链路仍是 `Gmail IMAP IDLE → Email Butler PostgreSQL → turb HTTP API`。
- 当前本机配置使用 `ICLOUD_HME_INBOX_MODE=forward_imap`，OTP 直接读取本机 Gmail；`forward_butler` 保留为生产 Email Butler 链路。
- turb 的账号、邮箱池、注册任务和账号操作任务均以本机 PostgreSQL 为主存储；JSON/TXT 只作为兼容导出或输入文件。项目运行时不再使用 SQLite。
- OTP 查询必须携带任务开始时间并按目标别名精确匹配，避免并发任务互相拿错验证码。轮询间隔由 `OTP_POLL_INTERVAL` 控制，Butler 已经接收到邮件时只做轻量查询。

#### 代理与地区

- 所有注册及账号动作都通过代理池领取，不回退到其他来源、其他国家或直连；后台补货和检测有独立预算，任务遵循原有等待和重跑规则。
- 每个注册任务领取独立租约，实际出口国家写入任务和账号。注册结束后的账号动作仍从统一代理池领取，优先沿用账号注册国家。
- 注册完成后立即查套餐时，优先复用仍有效的注册代理并在释放前同步落库，从而保证套餐/Plus 资格查询与注册出口一致；历史账号或手动操作再按账号已保存地区领取线路。
- 住宅代理只用于访问 OpenAI/ChatGPT 的账号功能。邮箱、短信、CPA、sub2api、提链服务、Roxy 控制 API 和其他本地接口保持直连，不得套用住宅代理，也不得把系统 `HTTP_PROXY/HTTPS_PROXY` 意外注入这些客户端。
- UI 中选择的地区、供应商 API URL 的 `region` 参数、Roxy Profile 的代理字段、任务日志与账号记录必须保持一致。完整代理 URL、用户名和密码只允许保存在 `.env`，日志和 UI 只能显示脱敏信息。

#### 711Proxy 与统一代理供给

「配置 → 代理与网络 → 代理来源」支持 `1024proxy`、`711proxy` 和 `manual`。供应商的 URL 参数、数量上限和会话寿命由 `core/proxy_sources.py` 管理；`core/proxy_supply.py` 共用提取、候选去重、出口检测和失败回收，业务任务仍只从统一库存领取。切换来源只影响后续领取；旧来源停止补货，已发放租约保持到释放。

711 当前接入[动态住宅代理 GB 的白名单 API](https://docs.711proxy.com/proxies/residential-proxies-gb/markdown)：先在 711 面板将调用 API 的公网 IPv4 加入白名单，选择对应套餐、代理主机并生成完整 URL，然后填入 `.env` 或配置页。API 提取绕过系统代理，请核对白名单对应的是服务进程直连出口。

```dotenv
PROXY_POOL_SOURCE=711proxy
PROXY_POOL_DEFAULT_COUNTRY=JP
PROXY_711_API_URL=请替换为面板生成的完整提取_URL
PROXY_711_PROTOCOL=http
PROXY_711_SESSION_MINUTES=30
```

711 适配器保留 URL 的主机、端口、`zone`、`ptype` 及其他授权参数，按目标国家覆盖 `region`，使用 `count`（最多 900）、`proto`、换行 TXT 输出和 `sessType=sticky` / `sessTime`（1–180 分钟），并关闭 `sessAuto` 提前换 IP。`socks5h` 以 `proto=socks5` 提取，在客户端保持代理端 DNS 解析。供应商返回的是网关地址，实际出口 IP 和国家仍须检测后才能入池；粘性时长须大于代理池最短剩余寿命。

`PROXY_711_API_TIMEOUT`、`PROXY_711_ACQUIRE_TIMEOUT`、`PROXY_711_VALIDATE_ATTEMPTS`、`PROXY_711_RECENT_TTL` 和 `PROXY_711_ACQUIRE_INTERVAL` 分别控制请求/检测超时、补货总预算、检测次数、释放隔离期和提取间隔。「提取并测试 1 个 IP」使用当前供应商及页面草稿参数，测试完成后释放本地测试租约，会消耗少量流量。该入口不修改白名单；711 用户名密码生成方式尚未作为自动供给来源接入，手动地址仍使用 `manual`。

#### Roxy 环境与登录态

- `ROXY_ONE_PROFILE_PER_ACCOUNT=True` 时，每个账号最多绑定一个 Roxy Profile；账号记录的 `extra_json.roxybrowser.profile_id` 是复用入口，没有绑定时才创建环境。创建请求超时或断连属于“结果未知”，客户端会先按唯一环境名查询是否已经创建成功，不能盲目重试并制造孤儿环境。
- Roxy `/browser/create` 明确返回 Profile 总额度不足时立即失败，不进入等待；仅 `/browser/open` 的可恢复窗口忙状态会在当前 worker 等待并重试。默认最多等待 `ROXY_WINDOW_WAIT_TIMEOUT=900` 秒，每 `ROXY_WINDOW_WAIT_INTERVAL=10` 秒重试。多 worker 创建 Profile 时，`ROXY_CREATE_INTERVAL=1.5` 秒限制相邻 `/browser/create` 请求的起始间隔，设为 `0` 可关闭。
- 邮箱 UI 提交前等待页面前端接管表单，避免 SSR 输入框可见但提交变成原生 GET 重载。注册页面准备最多等待 180 秒，每 10 秒上报加载进度；就绪后自动继续首次点击，不刷新正在加载的页面。提交及认证跳转最多 60 秒，整个邮箱阶段最多 240 秒，调用方传入的较小预算仍有效。异常时保留一次有界 NextAuth 兜底；只读 CSRF 预检失败且确认未派发提交时，在剩余预算内等页面就绪后执行首次 UI 点击。页面已经到达密码、OTP 或登录完成状态时立即接受该状态，不能依据旧快照重复提交邮箱。认证域不跨域探测 ChatGPT session；同源探测主动取消超时请求。验证码入口的初始化/发码仍在进行时继续有界等待，不按固定 5 秒刷新，等待仍受阶段预算限制。已交给前端的邮箱提交在结果未确认时不重复点击或启动兜底；到期按结果未知收口。
- 邮箱点击前再次检查输入、表单有效性和按钮状态；排队超过 3 秒的点击仅在原回执仍未执行时原子取消，再进入已有恢复路径。点击已执行或回执丢失时继续保留未知结果屏障；超时日志记录脱敏回执事实。仍停留邮箱表单时，session 探测间隔至少 3 秒，密码/验证码页面识别不受节流影响。
- 密码表单等待前端接管后才填写，填写后重新确认输入值和同一表单内已启用的主提交按钮，避免误点返回或验证码入口。输入框重建时沿用同一密码重新填写，准备过程有界；进入单次异步提交阶段后保存可恢复检查点，远端结果仍需后续页面确认。提交结果未知时保留原密码，不自动补点。
- 默认在任务结束时关闭浏览器但保留 Profile；账号级重试/补配置/查活/AT 刷新再次打开账号绑定的 Profile。复用前会先检查当前 workspace 的活动 Profile 列表：如果绑定记录已被 Roxy 手动删除、移入回收站或不再可用，就创建替代环境并回写账号绑定；活动列表探测本身失败时不会误清绑定或盲目创建。动作领取了新的代理租约时，若 Profile 仍在运行，会先调用 Roxy 官方 `POST /browser/close` 并确认退出，再用 `POST /browser/mdf` 仅更新 `proxyInfo`，最后重新 `POST /browser/open`；关闭未确认或更新失败时停止，不继续使用旧出口。该流程保留 Profile 的 Cookie、指纹和账号身份字段，不发送清理或随机指纹参数。接口字段参考 [Roxy Local API 文档](https://roxybrowser.cn/docs/api-documentation/api-endpoint.html)，代理配置语义参考 [Roxy 代理资源说明](https://roxybrowser.cn/docs/features/proxies.html)。
- 显式注册续跑复用原 Profile 时，先完整读取现有会话并核对邮箱身份；匹配后跳过本轮无需执行的认证步骤，沿用原密码继续保存和后处理。会话读取结果未知或身份不符时停止，不重复发起注册；资料提交后的完整会话读取与 Token 步骤共用已核验结果，避免短探测反复取消慢响应。
- Token 阶段的 session 兜底请求使用当前剩余时间覆盖完整响应体读取，并临时调整、随后恢复浏览器脚本超时，避免被导航留下的短超时提前截断。取得 Token 并核对邮箱身份后，先保存账号、密码和完整会话、绑定任务及 Profile，再响应停止请求、捕获套餐或执行其他后处理。
- `ROXY_DELETE_PROFILE_AFTER_RUN=True` 是高风险兼容开关，会删除本轮新建的 Profile，即使任务已经将其绑定到账号；默认关闭。开启后可释放 Roxy 的 Profile/窗口额度，但下一次使用该账号时需要重新创建环境。启动恢复对没有 `disposable` 标记的历史登记项永不自动删除。需要排查时仍可在发起注册页勾选「调试模式」：失败任务会在配置的超时时间内暂停并保留自己的 Roxy 窗口，用户可在任务日志中点击「释放现场」继续清理。`ROXY_KEEP_BROWSER_OPEN=True` 只保留为低层紧急诊断开关，不适合日常批量调试，因为它不受任务级超时和并发上限管理。
- 注册后紧接着执行 Codex OAuth 时，复用同一个 driver、Profile、代理和 ChatGPT 登录态，授权 URL 不强制 `prompt=login`；若出现账号选择器，只允许选择与当前任务邮箱完全匹配的账号。
- 从账号页独立补跑 Codex 时优先打开账号绑定的 Profile；只有账号没有绑定或 Roxy 明确报告 Profile 已不存在时才创建环境。这与“注册后立即 OAuth 复用登录态”仍是两个不同场景，但两者共享账号级 Profile 绑定。
- Roxy 免费版界面显示的 5 个 Profile/窗口额度不等于整条注册链路必然能稳定并发 5。实际并发还受住宅代理提取频率、邮箱库存、OTP、接码平台和 OpenAI 风控限制；首次部署先跑通单任务，再逐步提高并发。

#### Roxy 浏览器省流量

- `BROWSER_DATA_SAVER_MODE` 是省流量总开关。注册使用 `BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES` 和 `BROWSER_DATA_SAVER_BLOCKED_URL_PATTERNS`；认证及资料提交期间自动忽略 script/stylesheet 类型和 ChatGPT/auth CDN 脚本、样式的旧拦截规则。Roxy 核验完整会话并保存账号后，停止首页应用壳加载，保留轻量的 ChatGPT 同源 session 页面，跳过完整首页初始化；协议 2FA 与套餐查询继续执行，需要浏览器 2FA 或协议失败回退时才恢复核心资源并进入安全设置。已自然捕获的套餐结果在页面切换前保留，缺少结果时仍可在同源页面补查。关闭省流量时继续保留并观察正常首页，最多等待 30 秒，超时保留已保存的账号。刷新 AT、旧 AT 浏览器查活、独立 Codex OAuth 和账号操作使用认证安全规则；注册窗口继续执行 Codex OAuth 时按独立标签页切换认证规则。
- `BROWSER_DATA_SAVER_AUTH_FLOWS` 是可选流程列表，可填写 `token_refresh`、`live_check`、`codex_oauth`、`account_action`；默认全选，填 `[]` 可只保留注册省流量。它和总开关都可以在 WebUI「配置 → 浏览器设置 → 浏览器画像」调整。流程开关同时控制 Roxy 启动参数和 Selenium CDP 拦截。
- `BROWSER_PUBLIC_ASSET_CACHE_MODE` 独立控制 Roxy 注册及账号认证流程（刷新 AT、普通查活、Codex OAuth、账号操作）：默认 `off`；`observe` 仅统计候选，不下载或回放；`enabled` 在浏览器原生缓存之外跨 Profile 复用公共 JS/CSS。可在同一配置分组调整；`BROWSER_PUBLIC_ASSET_CACHE_MAX_MB` 默认 256 MiB。缓存位于忽略提交的 `run/public-asset-cache/`，最多 1000 项、单项 10 MiB、有效期不超过响应声明及 24 小时，旧资源自动淘汰。
- 公共缓存只接受审核过的 ChatGPT/auth CDN 目录下带版本的 JS/CSS，要求 HTTP 200、明确公共缓存、正确 MIME、无 Set-Cookie 和敏感响应变体。仅收录已证实不携带 Cookie/Authorization 的浏览器响应；已完成资源最多等待 250 毫秒收齐 CDP 元数据，优先复用已经下载的正文，不暂停业务请求。明确带凭据的资源不再额外匿名下载；其余注册资源需要匿名验证时，只沿本次新建 Profile 的已知代理下载，不跟重定向、不回退直连。账号认证流程只读取浏览器已经完成的公共响应，不额外发起匿名下载；缓存只连接当前业务页面，复用注册窗口时由注册外层持有并收口，保留窗口也会停止本轮缓存及流量统计。认证 API、HTML、session、OTP 和安全挑战不缓存。原 URL、内容完整性与安全响应头保留，过期、损坏、磁盘或连接异常均回到浏览器正常网络。注册首次填充可能额外下载，不能以冷缓存单次任务承诺省流量比例。
- 省流量拦截或缓存失败会继续原浏览器业务。「代理与流量」页分别标明浏览器和协议采集来源：浏览器统计已采集的 HTTP/WebSocket 字节及缓存匿名填充下载，排除公共缓存本地回放；协议统计已接入 `BrowserSession` 的业务请求，字节使用后端报告的传输正文大小，不含请求头、TLS 或代理隧道，解码后的正文大小另存。协议请求数按每次 `get/post` 调用累计，自动重定向另计；其他客户端、外部脚本和未接入的请求不在此范围。
- 今日请求记录按采集记录的开始时间计数，不是 HTTP 请求数；今日新建线路按任务租约获取时间计数，后台库存锚点不计任务线路，日期边界为北京时间零点。旧协议未采集标记保留在 PostgreSQL 排障但不进入可用记录合计。常规协议采集只存聚合统计和任务归属，不存 URL、正文或凭据；计量异常不改变业务结果。浏览器未确认的本地回放不扣减可观测字节，后台填充未收口时记录下界并标记未知。所有可观测字节都不等于代理商账单。

#### 浏览器代理计量与诊断

Roxy 新建或安全重开绑定 Profile 时，已领取的代理线路可经过本机 HTTP CONNECT 中继。中继只包装原线路，不领取新代理、不替换原出口；端口随窗口生命周期释放，保留窗口时继续保留中继。有原租约恢复资料的窗口可在服务重启后恢复原端口与原线路，续跑仍按实际使用的旧线路归因；端口冲突会明确报告失败。窗口是否仍在运行通过 `/browser/connection_info` 的目标进程与连接资料核验，不能仅凭列表中的 `openStatus` 撤销中继或新建环境；查询失败或结构不明时保留恢复资料。经过中继的 `proxy_transport` 统计覆盖 TLS、启动及后台连接，并按目标 `host:port` 给出上传、下载、占比、连接及失败/恢复次数；它与原 `roxy_cdp` 页面字节分开展示，不能相加，也不等同于供应商计费。复用未经过中继的现有连接时不补造历史数据。

- 开启 `BROWSER_DATA_SAVER_MODE` 后，`BROWSER_DATA_SAVER_BLOCKED_PROXY_HOSTS` 默认在连接上游前拒绝 `dl.google.com`、`gvt1.com` 及其子域名；配置填 `[]` 可关闭域名拦截。规则只对经过中继的本地浏览器生效，保存后用于新建中继，不改变已有连接；计数只表示拦截次数，不估算节省字节。
- SOCKS5 CONNECT 返回临时错误码 `1/3/4/6` 时，握手阶段最多尝试 3 次，间隔 0.25/0.5 秒。认证失败、规则拒绝及端口拒绝直接返回；建立隧道后不重放 HTTP 或 TLS 数据。日志单独记录重试、恢复和最终失败。
- `BROWSER_TRAFFIC_DETAIL_LOG` 默认关闭；开启后在任务日志输出脱敏的资源 URL、请求类型、状态与实际可观察字节，`BROWSER_TRAFFIC_DETAIL_MAX_ENTRIES` 限制明细条数。
- `BROWSER_JS_COVERAGE_LOG` 默认关闭；开启后通过 Chromium Profiler 记录脚本执行范围摘要，`BROWSER_JS_COVERAGE_MAX_ENTRIES` 限制条数。诊断不保存源码、请求正文、Cookie 或验证码；“未观察到执行”不能单独证明某个脚本可以屏蔽。浏览器不支持 Profiler 时记录不支持，不影响业务。

#### Codex、接码与 sub2api

- Codex 的事实记录在 PostgreSQL 的 `codex_credentials`，`codex_accounts/` 下的 OAuth JSON 是为 CPA/sub2api 保留的兼容产物。旧 Codex Agent Token 生成、下载和上传接口已经移除；sub2api 导入直接上传 OAuth JSON，并支持按账号更新已有凭证。
- 注册成功不因 Codex 失败而回滚；账号正常保存，Codex 标记失败并允许单独补跑。补跑停止信号必须贯穿邮箱 OTP、取号、短信等待和浏览器流程，不能被普通换号异常吞掉。
- GrizzlySMS 支持在 `SMS_COUNTRY` 中配置备用国家，并透传 `SMS_MAX_PRICE`（它只是购买上限，不是固定成交价）。开启 `SMS_AUTO_SELECT_COUNTRY` 后，每个批次首次接码会结合正式价格/库存接口与价格页短信成功率统计，在价格上限内选出统计量足够且成功率最高的国家；同一国家连续失败两次会自动切到排名中的下一候选。统计接口异常时自动回退 `SMS_COUNTRY`。实际成交价、国家和价格上限会写入本地运行日志与取消队列，便于复盘。
- sub2api、CPA 和短信平台是第三方控制面请求，默认直连；它们的鉴权字段必须放在 `.env`，不得写入源码、README、日志或数据库导出。

#### WebUI 与配置变更

- `/api/capabilities` 是前端功能开关的依据，但后端接口仍必须调用同一套可用性检查，不能只靠隐藏/禁用按钮保证安全。
- 配置保存并热加载后，要同时刷新功能可用性和注册邮箱来源。后台任务启动前读取最新配置，已经运行的任务保持其提交时的邮箱来源和已领取资源，不在途中静默换源。
- 新增、删除或重命名配置时，必须同步检查 `config/schema.py`、`config/*.py`、`config/__init__.py`、`webui/config_editor.py`、`.env.example`、README、CLI/WebUI/自动任务/批量任务入口及测试。字段的领域分组由 schema 维护，配置菜单由前端按用途映射；每个字段只保留一个编辑入口。本轮清理范围与保留依据见[配置核查记录](docs/development/configuration-audit.md)。涉及代理、邮箱、Codex 或数据结构的改动，还要检查账号页、任务恢复、导入导出和部署配置。
- 主要注册、续跑、查活、AT/Codex 刷新、封号扫描和邮箱来源链路的入口、共享组件、配置键与定向测试见[功能链路与测试影响地图](docs/architecture/functional-map.md)；修改公共组件时先按地图反查受影响链路。
- 提交前完成受影响功能的定向测试和相邻回归，再按风险决定是否扩大范围；涉及真实浏览器链路时，按“单任务 → 小并发”顺序验收。`.env`、`run/`、`logs/`、账号、邮箱池、Codex 凭证和生产数据库内容永远不得提交。

---

## 使用方式

## WebUI 推荐方式

推荐使用项目根目录单脚本后台管理：

```bash
./webui.sh start      # 启动
./webui.sh stop       # 关闭
./webui.sh restart    # 重启
./webui.sh status     # 状态
./webui.sh check      # HTTP、数据库和 worker readiness（只读）
./webui.sh logs       # 查看实时日志
```

脚本默认启动 `http://127.0.0.1:5000`，日志写入 `logs/webui.log`，PID 写入 `logs/run/webui.pid`。
`start` 会等待 `/healthz`、PostgreSQL 和必需后台 worker readiness 全部通过后才报告成功；
`check` 不启动或重启服务。固定版本发布、回退和隔离测试见
[`docs/development/release-verification.md`](docs/development/release-verification.md)。

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
| 邮箱池 | 「资源总览 / 邮箱列表 / 邮箱子地址」子菜单；管理 Email Butler 当前进程租约；邮箱列表集中导入和批量操作；子地址页预生成库存，支持表头筛选、复制、停用恢复和分页，注册只领取库存 |
| 代理与流量 | 「代理池库存 / 租约与流量」子菜单；库存与记录分别展示，记录页保留当前租约、线路历史、请求流量及其筛选、分页、详情和列宽调整 |
| 配置 | 左侧切换 9 个用途菜单，菜单内按小节集中修改；系统设置统一管理通用配置、网站授权、定时任务和任务历史保留 |

### 线程数说明

- 注册线程数在每次点击「开始注册」时读取。
- 如果线程数和上次不同，新提交任务会使用新线程池。
- 旧线程池里已经排队/运行的任务会继续跑完，不会被强制取消。
- 账号操作共用一个线程池，批量补跑不会按请求参数另起线程池；注册流程仍使用独立的注册线程数和注册套餐查询线程数。

### 本地验证基线：Roxy + 1024Proxy + iCloud HME

下面是一套适合先在 macOS 本地单账号验证的组合配置。所有密钥和真实接口都写入 `.env`，不要改进源码或提交 Git：

WebUI 中代理相关配置统一位于「配置 → 代理与网络」，集中设置来源、默认国家、库存和补货策略。任务列表的“代理”列会显示实际 provider、脱敏端点和出口地区，可据此确认任务是否真的使用了 1024Proxy。

```dotenv
# WebUI
WEBUI_AUTH_CODE=请替换

# 主流程
REGISTRATION_DRIVER=roxy
ENABLE_CODEX_AUTO=False
CODEX_OAUTH_DRIVER=same_as_registration

# 由独立代理池提供已检测的 1024Proxy 美国线路
PROXY_POOL_SOURCE=1024proxy
PROXY_1024_API_URL=请替换为你的白名单提取_API
PROXY_POOL_DEFAULT_COUNTRY=US
PROXY_1024_PROTOCOL=http
PROXY_1024_SESSION_MINUTES=30
PROXY_1024_API_TIMEOUT=12
PROXY_1024_ACQUIRE_TIMEOUT=60
PROXY_1024_VALIDATE=True
PROXY_1024_VALIDATE_ATTEMPTS=2
PROXY_1024_RECENT_TTL=1800
PROXY_1024_ACQUIRE_INTERVAL=0.6
PROXY_POOL_MIN_READY=2
PROXY_POOL_MAX_SIZE=20
PROXY_POOL_WAIT_TIMEOUT=0
PROXY_POOL_MIN_TTL=300
PROXY_POOL_CHECK_INTERVAL=60
PROXY_POOL_MAX_IDLE=300
PROXY_POOL_WORKERS=2

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
ICLOUD_HME_ACCOUNT_ID=请留空以自动发现全部 active 账号
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

`.env.example` 是 WebUI 可编辑字段的完整模板；新增配置时必须同步更新 `config/schema.py`、`config/*.py`、`webui/config_editor.py`、`.env.example` 和本 README。配置页的密钥字段只写 `.env`，页面会按密码框处理。

### 当前部署边界

- 当前默认运行和部署目标是本机工作区 `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register`，本机 WebUI 优先使用 `PORT=8000`。
- Oracle 主机上旧的项目 WebUI、systemd 服务和 Nginx 站点已经停用，不再把 `ssh oracle` 作为本项目默认部署方式。
- Oracle 上可能仍运行 Email Butler；它只是本项目可选的外部收信依赖，不是 WebUI 的部署目标。
- 更新或重启前必须保留 `.env`、PostgreSQL 数据、`accounts/`、`codex_accounts/`、日志、`run/` 和 `.venv/`。提交代码、推送仓库、重启服务和验证实际运行版本是四个独立步骤，不能相互代替。

### 后续投产清单

- 使用 systemd、launchd 或其他进程管理器托管 WebUI 和 iCloud sidecar；反向代理只暴露 WebUI，不要把 sidecar 的 `8081` 直接暴露公网。
- WebUI 绑定 `127.0.0.1`，由 Nginx/Caddy 提供 HTTPS；设置固定 `WEBUI_AUTH_CODE` 和 `WEBUI_SESSION_SECRET`。
- 部署新代码前备份 `.env`、PostgreSQL 数据库、`accounts/`、`codex_accounts/` 和日志；账号、任务与邮箱池以 PostgreSQL 备份为准，不能用根目录快照替代。
- 代理和邮箱都必须按任务生命周期领取：任务开始领取，成功永久占用邮箱并释放本地代理租约；确认账号未创建的失败任务才退回邮箱，避免同一邮箱注册两次。
- 先按本次发布范围和风险完成验证，再依据明确的部署授权重启服务；涉及共享存储、运行时或迁移时补充对应扩展验证。不要提交 `.env`、许可证、Apple Cookie、App 专用密码、邮箱、代理完整地址或 Token。

### 一键巡检与已废账号清理

账号页的「一键巡检」按当前活跃/归档视图创建固定账号清单，不受勾选、搜索、当前页及其他列筛选影响。每轮可设 1–16 并发，同时遵守 `ACCOUNT_BATCH_WORKERS` 的共享预算；同一时间只运行一轮巡检。有效 AT 仅本地解析 JWT `exp`，不验证签名、不发网络请求；过期、缺失或格式异常才刷新 AT，先保存新 Token，再借用同一次登录会话查套餐。套餐失败单独计数，不覆盖已经成功保存的新 AT。

「巡检历史」展示范围、进度、AT 失效、查活及套餐结果；「失败详情」保留本轮原始 Run 的错误和已废跳过记录，后续重跑或账号删除不改写原记录，历史保留期沿用任务中心配置。巡检使用现有 PostgreSQL 父子任务、账号租约、取消和启动恢复，不另起无界线程池；可在历史中停止当前轮次，异常结束后仍可重新发起。

「删除已废」只删除明确标记为已废的账号记录，操作前显示归档范围与数量；不会因为当前搜索或勾选而缩小范围，也不会把普通超时、查活失败或未知状态当作已废。邮箱池、原始任务及巡检历史不随账号清理删除。

### 账号任务实例与 AT 生命周期

任务中心默认每天自动执行一次历史保留清理。它只处理已明确结束且超过保留期的统一任务中心记录；排队/运行中的任务、`request_unknown`、有效租约、未完成父子依赖以及仍在执行的注册/账号源任务都会保留。清理前会先在 `logs/task-center-archives/` 生成并回读校验脱敏 gzip 归档，归档失败时数据库事务回滚。配置可在 WebUI「配置 → 系统设置 → 任务中心」修改：

```dotenv
TASK_CENTER_RETENTION_DAYS=7
TASK_CENTER_ARCHIVE_RETENTION_DAYS=30
```

`TASK_CENTER_RETENTION_DAYS=0` 会关闭自动清理；`TASK_CENTER_ARCHIVE_RETENTION_DAYS=0` 会永久保留已生成的本地归档。清理只删除统一任务中心历史及其级联投影，不删除 `registered_accounts`、`registration_*`、`account_action_*` 等业务/兼容事实表。原生任务的独占 `run.jsonl` 会逐文件删除，兼容任务复用的源日志保留。

WebUI「账号 → 任务实例」统一保存以下账号操作：

- `codex_retry`：Codex OAuth 补跑。
- `live_check`：优先验证现有 AT 的账号查活。
- `token_refresh`：AT 缺失、失效、临近过期或手动要求时的刷新。
- `plan_check`：查询账号套餐、Go / Plus 免费试用或折扣优惠及额度。成功结果通过 `account_promotions` 保存各套餐活动，`promotion_query_snapshot` 保存白名单活动证据和响应结构摘要；账号保存最新成功结果，每次独立查询的任务 Run 保留对应历史，后续复查不会覆盖旧任务。首次响应与注册自动复查分别写入 `promotion.query.recorded` 任务事件，Run 摘要中的 `promotion_query_history` 标注各次查询。证据不含完整账号响应、邮箱、Token、Cookie 或代理凭据；出现 Go 套餐 offer 不等于具有 Go 免费资格。
- `deactivation_mail`：扫描支持邮箱来源中的高置信度封号邮件。

每个任务实例保存任务 ID、账号快照、触发方式、状态、验证方式、脱敏线路、开始/完成时间、耗时、结果摘要和阶段事件。账号密码、AT、验证码、邮箱正文、callback 和完整代理凭据不会写入任务库。WebUI 重启时，仍处于排队或运行状态的历史实例会标记为中断，可从实例列表重新执行。

失败分类优先使用实际阶段、固定原因码和脱敏诊断，例如密码认证前置 TLS 失败、验证码未收到、MFA 请求超时或本地写回失败；不再统一包装成 `request_unknown` / `REMOTE-001`。历史任务也按已有证据展示具体原因，没有记录细项时明确标注对应步骤缺少回执。远端提交与回执核验状态独立保留，避免丢失原请求记录或自动重复提交。

浏览器注册已有的邮箱提交未确认、密码提交未确认、创建密码页跳转超时、资料会话读取失败和认证错误页会分别显示；不会仅凭异常类名中的 `Timeout` 判定网络故障。资料会话读取失败时记录异常类型，摘要不复制可能含凭据的原始异常正文；原提交仍保留待核验状态。这些分类也适用于历史任务的读取，不会改写历史结果或自动重跑。

任务中心列表、事件时间线和运行日志的时间由 WebUI 按当前浏览器时区显示，页面会标注当前时区；原始 `run.jsonl` 中的 `ts` 保持 UTC ISO 8601 值，便于跨环境排障。缺失或非法时间会保留诊断提示，不静默伪装成本地时间。
旧注册/账号任务的开始时间、注册阶段时间和派生事件按保留的源时间快照进行兼容读取；已有时区偏移的时间不会重复偏移，也不回写历史记录。事件分页仍使用 ID 游标，页面按校正后的时间排列。

任务中心、注册页和批次卡片共用统一步骤模板，按实际执行顺序展示阶段、子步骤与阶段事件。点击步骤可同时筛选事件和运行日志；任务详情的步骤区固定高度，按宽度和步骤数量紧凑排列，能在一行放下时全部展示，超出容量时再翻页；步骤用箭头连接并直接显示耗时，悬停或键盘聚焦查看阶段时间、阶段事件和子步骤；悬浮信息较长时可滚动，键盘向下键可进入浮层，Esc 关闭。点击步骤仍筛选对应日志，日志上方同时展示所选步骤的起止时间。已跳过的主步骤与流程卡片中的子步骤不显示，详情保留已记录的跳过原因；注册任务保存的配置明确关闭的可选分支从排队时就隐藏；实际执行证据优先保留。结果节点在收到收尾事件或任务结束前保持“未开始”，整体任务状态单独展示。原始阶段事件、重试实例和日志保留。失败摘要展示原始阶段、错误分类及关联事件。任务结束时，漏收口的历史阶段显示中性的“记录不完整”，明确失败后未进入的步骤显示“未执行”；没有足够证据的执行结果仍保留“未确认”，不会自动变绿。新增任务与驱动的报告契约见[统一任务步骤与日志](docs/architecture/task-observation.md)。

注册的“登录与身份验证”保留页面、邮箱提交、认证跳转、密码与验证码子阶段；页面加载完成不代表身份验证完成。各子阶段独立记录耗时，事件时间使用实际发生时刻；详情中的“阶段事件”条数不表示重试次数。本次核对范围与验收进展见[2026-10-13 注册主流程核对](docs/development/2026-10-13-registration-flow-audit.md)。

普通查活驱动在第一阶段通过 `ACCOUNT_LIVE_CHECK_DRIVER` 独立配置，缺失时保持当前协议型旧 AT 探测：

```dotenv
ACCOUNT_LIVE_CHECK_DRIVER=protocol_current
```

当前默认仍只启用 `protocol_current`。Roxy 浏览器旧 AT probe 已完成独立 adapter、契约测试和真实样本验证，但仍由 `ACCOUNT_LIVE_CHECK_BROWSER_ENABLED=False` 灰度开关保护；需要本地明确开启后才能把 `ACCOUNT_LIVE_CHECK_DRIVER` 切为 `browser_roxy`。当前没有独立的 v2 协议普通 AT probe，因此它不会出现在普通查活选项中。普通查活无论使用哪种已开放驱动，都不会登录、发送 OTP 或刷新 AT。该配置不影响 `ACCOUNT_PLAN_CHECK_DRIVER`（账号补全套餐步骤），也不影响刷新 AT 的协议版本选择。

账号列表的“查活”请求会把当前配置驱动显式传给后端，后端在领代理/创建 Roxy Profile 前校验；任务结果同时保留 configured/effective driver。也可以在测试账号上通过批量接口的 `driver` 字段做单次 override，该 override 不会写回全局配置。

在「配置 → 注册与账号 → 账号补全 → 刷新 AT 策略」选择 `ACCOUNT_AT_REFRESH_DRIVER`：默认 `protocol` 使用协议刷新，`browser_roxy` 直接使用 Roxy 指纹浏览器重新登录，不先尝试协议。单号、批量和后台刷新使用同一驱动配置，任务入队后固定本次驱动。任务中心重跑 AT 刷新时，新 Run 重新读取并固定当前刷新配置，包括驱动、协议版本和 Roxy 调试开关；历史 Run 继续保留原配置和执行证据。

`OPENAI_PROTOCOL_VERSION` 仅为协议刷新选择 v1/v2，默认 v1；直接 Roxy 刷新不读取它。注册协议、协议 2FA、套餐查询、普通查活和 Codex 协议授权继续使用各自的唯一实现：

```dotenv
ACCOUNT_AT_REFRESH_DRIVER=protocol
ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED=False
OPENAI_PROTOCOL_VERSION=v1
ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK=False
ACCOUNT_PASSWORD_RESET_ENABLED=False
ACCOUNT_AUTH_PROFILE_MODE=current
ACCOUNT_AUTH_RAW_CONTEXT_ENABLED=False
ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS=30
LIVE_CHECK_ROXY_FALLBACK_ENABLED=True
```

协议刷新设置为 `OPENAI_PROTOCOL_VERSION=v1` 时使用现有邮箱 OTP 登录，并按 `LIVE_CHECK_ROXY_FALLBACK_ENABLED` 决定是否使用 Roxy 兜底；设置为 `v2` 时优先尝试保存的 OpenAI 账号密码，并按远端响应进入直接回调、TOTP MFA 或邮箱验证码。邮箱已失效的账号优先使用支持密码和 TOTP 的登录路径。账号没有保存密码时不会伪造密码提交；邮箱仍有效时沿用邮箱认证，邮箱已失效时明确报告缺少密码。密码页/返回结果无法识别时记录明确失败。密码明确错误默认不发送邮箱验证码；仅邮箱有效且打开 `ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK` 时，最多另起一次会话走邮箱 OTP，结果仍保留“密码被拒绝”。普通查活不会触达这条认证链。

Roxy 刷新 AT 进入邮箱验证码页后，如果本地保存了密码，会先通过页面提供的密码入口完成登录，并按服务端要求继续 TOTP；没有密码入口或密码后仍要求邮箱验证码时，邮箱有效的账号继续收码，已标记邮箱失效的账号保留明确失败原因。
验证码确认会区分提交前已有的页面错误与本次新错误；只有明确的验证码无效结果才重发。提交未确认或认证会话失效时保存具体原因，本轮不再追加收码等待；任务仍可手动重跑。

开启 `ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED`（Roxy 刷新调试）后，实际使用 Roxy 刷新 AT 时会显示浏览器窗口并全程抓包；失败后保留窗口，可在任务日志的“诊断资源”中查看失败截图、下载完整页面现场与 HAR。该开关默认关闭，位于「配置 → 注册与账号 → 账号补全 → 刷新 AT 策略」，独立于注册任务的调试开关；它不自动打开 Chrome DevTools，也不暂停任务线程。实际启用时任务日志会明确记录。该开关只作用于实际 Roxy 刷新，不改变协议请求或普通查活。
账号补全遇到“本地没有 OpenAI 密码、远端显示登录密码页”时，只有明确打开 `ACCOUNT_PASSWORD_RESET_ENABLED=True` 才会执行：点击多语言“忘记密码”链接 → 在重置页点击继续 → 等待该次请求之后的新邮箱验证码 → 提交验证码 → 填写并提交新密码。新密码提交后立即写入账号的 `extra_json.account_password` 检查点；若远端结果无法确认，任务会失败但保留检查点，后续重试使用该密码，不会再次盲发重置邮件。该流程只属于账号补全，不影响注册恢复、普通查活或刷新 AT。
补密码的首次邮箱登录和重置后重新登录分别使用有界的邮箱确认流程，调用结束后恢复临时预算与提交回调；同一次邮箱阶段内仍共享截止时间。已保存密码登录复用共享密码表单的就绪检查、一次提交回执和密码跳转确认预算；明确拒绝时按账号补全配置决定是否重置，结果未确认时保留密码与回执。任务进度按实际边界记录分配网络、启动浏览器、登录验证和设置密码；外层“执行账号配置”保留在执行记录中，缺少历史记录的步骤按计划位置展示“记录不完整”。
`ACCOUNT_AUTH_PROFILE_MODE=current` 保持现有每个会话随机设备画像；只有实际使用 v2 协议刷新且明确改为 `account_stable` 时，才按账号懒创建私有稳定 Protocol identity。它不修改注册时的 `device_id`，不影响普通查活、v1 协议刷新或浏览器兜底；画像的原始 profile key 不进入账号 JSON、导出和普通 API。
`ACCOUNT_AUTH_RAW_CONTEXT_ENABLED` 默认关闭；开启后才会为 v2 协议的实际认证 session 按白名单保存受限 run context，包含原始 device/session 标识和当次代理上下文，不会作为后续任务的代理或会话来源。默认保留 30 天，`ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS=0` 关闭自动清理；这些原始值不进入普通账号 API、任务事件和导出。
`LIVE_CHECK_ROXY_FALLBACK_ENABLED` 控制协议刷新 AT 失败后的 Roxy 登录兜底，不影响普通查活。v2 密码认证的 Sentinel 前置步骤失败且已确认密码请求未提交时，可以切换浏览器；密码或验证码已经提交但没有完整回执时，保留具体失败原因和核验记录，不自动重新提交。普通查活是否使用浏览器由 `ACCOUNT_LIVE_CHECK_BROWSER_ENABLED` 与 `ACCOUNT_LIVE_CHECK_DRIVER` 独立控制。历史 `.env` 中的 `ACCOUNT_TOKEN_REFRESH_DRIVER` 和 `ACCOUNT_AUTH_V2_ENABLED` 仍可被兼容读取，但不再是新配置项，也不在 WebUI 展示。

已有账号单独执行“补 2FA”时，`ACCOUNT_2FA_DRIVER` 独立于注册 `TWOFA_DRIVER`：

```dotenv
ACCOUNT_2FA_DRIVER=auto
ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED=True
ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED=True
```

协议 2FA 的重认证总尝试次数由 `TWOFA_REAUTH_MAX_ATTEMPTS`（默认 3，范围 1–8）控制，退避基数由 `TWOFA_REAUTH_RETRY_DELAY`（默认 3 秒，范围 0–60）控制，均可在「账号补全」配置。邮箱 OTP 只对无业务拒绝、无交互挑战的 403/429 复用原会话与验证码重试，不重新发码，并尊重 120 秒以内的数字 `Retry-After`。明确拒绝、挑战及网络结果未知会保留失败原因，当前调用不自动重放验证请求；后续仍可使用已有任务重跑入口。

`auto` 是推荐配置：单独补 2FA 时先复用已有 AT；没有 AT 或旧 AT 被 MFA 要求近期认证时，通过协议邮箱 OTP 重认证并写回新 AT；协议仍无法完成且 `ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED=True` 时，才进入 Roxy 安全设置页。组合“补全账号”同时缺密码时，必须先打开 Roxy 登录页补密码，再从当前浏览器会话取得新 AT，随后仍优先使用协议完成 2FA。`protocol` 强制使用协议执行 2FA，但仍按上述认证上下文和兜底开关处理；`browser` 直接走现有浏览器安全设置页。历史配置中的 `protocol_direct` 仍兼容，但会自动归一为 `auto`，不再作为单独选项显示，也不会传给只接受 `protocol`/`browser` 的注册校验器。「配置 → 注册设置 → 注册主链路」管理注册 2FA；「配置 → 账号补全」管理账号补全 2FA、协议重认证和浏览器兜底开关。

补 2FA 的协议重认证必须确认进入 HTTPS 认证域的邮箱验证码页，再显式请求发码；发码成功后才按本次发送时间收取新邮件。落到密码页、错误页或其他页面时保留脱敏页面类型，按现有配置进入浏览器兜底；发码被拒绝或结果未确认时不空等邮箱，也不在本次调用中自动重放发码请求，后续任务仍可重跑。调用方已提供验证码时不重新发码。普通 AT 续期不保证满足 MFA 的近期认证要求，仍以开通接口的实际结果为准。

已注册账号的 `email_source` 是后续 OTP 取码的权威来源；即使进程重启或 Outlook 池记录被清理，也会优先按账号来源取码，Outlook 账号凭据可从已注册账号快照恢复，不会因为当前 `EMAIL_SOURCE` 顺序变化而误走其他邮箱平台。

账号列表支持独立的“邮箱失效”标记、原因和时间，可在单号或批量操作中标记、解除，并按邮箱状态筛选。“未标记失效”只表示没有失效记录，不代表已验证可收件。标记同时记录关联母资源与地址账本的邮箱事实，不改变 OpenAI 账号状态、Token、归档或手动任务重跑资格；按原 Apple 副号整组标记时包括当前关联的母地址与派生地址。普通 Token 写回保留标记，确认换绑后按目标邮箱事实重新计算。解除单号标记不会自动清除所属副号整组的母资源失效依据。

协议邮箱换绑默认要求账号已创建至少 24 小时，提交阶段会先检查 `created_at`，不满足时不会租用新邮箱或发送远端换绑请求。这个门槛可通过 `ACCOUNT_EMAIL_CHANGE_MIN_ACCOUNT_AGE_HOURS` 调整；设为 `0` 才会关闭前置保护。远端明确拒绝、远端结果未知和本地写回未确认仍分别保留为独立任务结果，不会自动切换浏览器或盲目重试。

领取的目标邮箱若已属于本地账号（包括已归档或已废号的账号），换绑会在申请代理和发送远端请求前停止，并将任务与当前账号的换绑状态收口为失败；已用邮箱不会被释放为可用邮箱。应先核对邮箱来源的已使用记录，再重试。

换绑远端成功且本地写回确认后，会将目标邮箱收口为已使用。Email Butler 按 API Key 的服务策略登记 `openai` 标签，避免后续再次分配；若供应商收口失败，任务保留换绑成功并记录告警。此流程不会自动回填旧版本成功记录中遗漏的服务标签，历史补登记须先核对账号、换绑结果和远端邮箱身份。

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
- `icloud_hide`：通过独立协调队列处理；每个合并批次只建立一条转发 Gmail/IMAP 连接，服务器端按多个隐藏邮箱合并过滤收件人，再按账号拆分结果，不会为每个账号单独建连接或下载整个收件箱。

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
# Email Butler/Cloudflare 扫描并发使用 ACCOUNT_BATCH_WORKERS；icloud_hide 使用独立协调队列
EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS=21600
EMAIL_BUTLER_RISK_SCAN_INITIAL_DELAY_SECONDS=90
EMAIL_BUTLER_RISK_SCAN_LOOKBACK_DAYS=120

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

兼容文件日志仍保留用于本地故障排查：

```text
logs/codex-retry-邮箱.log
```

标准 WebUI 不再从账号菜单打开该文件；日常查看以任务实例中的脱敏阶段事件为准。

---

## 账号密码说明

OpenAI 新版注册通常先展示邮箱验证码页；新账号页面同时提供：

```text
/create-account/password
```

是否设置密码由「配置 → 注册设置 → 注册主链路 → 注册认证方式」决定：

- `otp`：直接使用邮箱一次性验证码完成无密码注册（默认）。
- `password`：在验证码页主动进入 `/create-account/password`，设置随机密码后再完成邮箱验证。

`REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS` 控制密码提交后等待验证码页、资料页或登录态的独立预算，默认 `60` 秒。该预算从点击密码页“继续”后重新计时，不占用前面的密码页识别/填写时间；密码提交请求一发出就会先保存可恢复检查点，超时且没有明确远端结果时，不会丢失已生成的密码或把邮箱重新放回注册池。邮箱表单提交后的认证跳转也会重新获得独立预算；纯代理隧道、空登录壳、页面未水合或注册前阶段预算耗尽且未产生账号状态时，会先自动刷新/强制新导航，仍为空壳才软删除本轮临时 Roxy Profile、释放代理租约并换代理线路重试。普通页面识别失败仍保留现场，已保存账号检查点的失败不会触发这项回收。

邮箱、密码、邮箱验证码和资料提交后没有推进时，会在原确认预算内预留最多 `20` 秒执行一次受控刷新；资料阶段遇到认证错误页、会话读取异常或未返回登录态时立即尝试刷新，仍未确认登录态时再回到浏览器历史里的上一认证地址。资料会话的首次读取也会给恢复预留时间，身份不匹配则直接停止。刷新和回退使用原地址的 GET 导航，沿用原邮箱、原密码和同一 Attempt，只观察原提交结果，不再次点击未知结果的表单；恢复后须有真实可见的下一步表单或经过身份校验的完整登录会话才接续，空壳 URL 不能作为确认。恢复没有推进时仍保留原提交和恢复资料，不增加一轮注册。以密码确认预算 `120` 秒为例，等待约 `100` 秒仍未推进时开始刷新，恢复不延长原预算。

邮箱提交或 NextAuth 导航已到达 `/email-verification`、但页面空白且没有验证码表单时，不必等到进入收码阶段才恢复：空白持续 `3` 秒后，在原提交剩余预算内对当前验证码地址执行一次 GET，并继续等待真实表单；刷新后仍为空白时不追加刷新或表单提交。

邮箱验证码收码前最多等待 `45` 秒挂载表单，空壳持续至少 `3` 秒或出现可识别的路由错误时最多刷新一次；页面等待与刷新仍受原 OTP 总预算裁剪。收码前的刷新和提交后的恢复分别计数，提交后按原回执最多恢复一次，不重新填码或重发。重发后的失败说明会区分本轮没有追加重发与此前已经尝试重发，并在有观测时保留 HTTP 状态。

认证会话结束页即使仍停在 `/email-verification`，也按登录已结束处理，支持中文、英文和日文提示。若既有网络观测发现认证站点最近一次 `/api/accounts/client_auth_session_dump` 返回 `404`，即使验证码表单仍可见，也停止收码或继续等待，记录 `auth_session_unavailable` 并保留原 Attempt 和未知提交；通过服务端的继续验证入口沿用原身份建立新的登录会话。该检查不额外请求认证接口，较新的成功或尚未完成请求不会沿用旧 `404` 的结论。

原身份续跑且已有保存密码时，验证码表单就绪后若页面明确提供同源 `/log-in/password` 链接，会优先通过该正常入口使用原密码登录；不猜测入口、不生成新密码，每个浏览器最多切换一次。密码提交后若服务端仍要求邮箱验证码或 TOTP，继续完成相应验证。新注册与页面没有提供密码入口的流程保持原有收码行为。

任务日志会记录「认证提交诊断」：提交回执、页面路由、加载状态、控件是否禁用、固定错误标记，以及认证接口的方法、HTTP 状态、耗时和网络错误。提交确认等待期间每 `15` 秒记录一次，刷新/回退前后分别记录，失败关闭浏览器前补记最终现场。页面、控件、资源和接口记录按同一 `capture_id` 分段写入，避免单条日志上限截断 JSON；资料会话还记录状态码、固定标记和是否有 Token。Roxy 复用既有 CDP 连接，响应头到达但响应体未结束时也会记录状态；普通失败诊断关闭时仍有这段脱敏日志。认证响应只额外保留经过值校验的 `server`、`cf-ray`、`cf-mitigated`、`content-type`、`retry-after`，不保存完整响应头或 Cookie。403 遇到 `cf-mitigated: challenge` 时标记为「检测到 Cloudflare 挑战」；只有 Cloudflare 服务标志时标记为「请求经过 Cloudflare，拒绝原因未确认」，其余情况保留来源与原因未确认，不据此判断代理 IP 被封。补充响应头允许乱序到达；重定向链只使用能可靠对应到各跳的响应头。诊断采集本身不发送额外认证请求，不保存表单值、正文、请求头或 URL 查询值；未知路径只保留指纹。资源时序里的状态 `0` 记为未知，不能当作请求失败。

Roxy 的密码与当前邮箱验证码表单会先核验控件、输入值和按钮遮挡情况，再预留一次提交并通过 CDP 派发真实鼠标事件。鼠标事件派发未确认时不会再切换 JS 点击；原密码、邮箱和 Attempt 仍保留给后续续跑。没有 CDP 的兼容驱动沿用原有表单提交方式。

邮箱验证码是 OpenAI 的邮箱所有权验证步骤；即使选择 `password`，设置密码后仍然需要邮箱 OTP。若 password 模式下页面没有提供创建密码入口，任务会明确失败，避免把无密码账号误报为密码注册成功。

密码设置成功后，OpenAI 登录页仍可能默认先展示邮箱验证码；此时可通过 `/log-in/password` 的“使用密码继续”入口改用密码登录。无密码注册的账号可以在账号配置补跑时设置一次密码；已有密码的账号不会修改密码。

密码始终按账号独立随机生成：14 位，包含大写、小写、数字和符号。配置页不提供固定密码输入，避免一批账号共用同一个密码。

注册、查活、刷新 AT、补密码和补 2FA 的完整支持矩阵见 [`docs/workflows/account-auth-support-matrix.md`](docs/workflows/account-auth-support-matrix.md)。

保存位置：

- 账号 `extra_json.account_password`：账号唯一密码。注册时或账号配置补跑时设置后都写入这里，后续补跑只会读取，不会改密码。
- 旧数据中的 `extra_json.registration_password` / `extra_json.login_password` 仅作为兼容读取来源，新写入不会再生成这两个字段。

账号页提供“账号密码”状态列和真实数据筛选。已设置密码的账号可以单独复制；批量选择后可用“复制密码”导出 `邮箱----密码`，未设置密码的账号会自动跳过。

注意：账号表里的 `password` 字段仍用于 Outlook 邮箱素材密码，不会被 OpenAI 账号密码覆盖。

---

## 重要配置文件

| 文件 | 说明 |
|---|---|
| `config/schema.py` | 可编辑字段的唯一契约：默认值、类型、领域分组、范围、选项与生效策略 |
| `config/roxybrowser.py` | 注册驱动、Roxy API、Roxy 环境生命周期 |
| `config/codex.py` | Codex OAuth、授权驱动、CPA 管理接口、接码平台 |
| `config/email.py` | 邮箱来源、OTP 轮询、Email Butler、QQ IMAP、iCloud HME、Cloudflare 临时邮箱及封号信号 |
| `config/proxy.py` | 代理池 |
| `config/register.py` | 默认邮箱、认证模式、显示名 |
| 外部共享 PostgreSQL | 本机由 `/Users/lihongwei/code/personal/shared-services/postgres` 统一管理 |
| `config/twofa.py` | 注册 2FA 开关与开通方式（`auto` / `protocol` / `browser`） |
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
| PostgreSQL `email_pool_outlook` | Outlook 邮箱池及状态；通过 WebUI/API 或显式文件导入写入 |
| `用于注册的API邮箱.txt/json` | 通用 API 邮箱池及状态 |
| PostgreSQL `registered_accounts` | 注册成功账号、access token，以及单独保存的完整 `chatgpt_session`（恢复用，不进入普通列表/导出） |
| `codex_accounts/` | Codex OAuth 凭证 JSON |
| PostgreSQL `account_action_batches/account_action_tasks/account_action_events` | 账号操作任务实例及脱敏阶段事件 |
| `logs/` | WebUI、注册任务、查活和 Codex 补跑日志 |

旧版本生成的 `accounts/` 批次目录仅是历史归档，当前注册流程不会继续创建或读取它；是否清理历史目录应在核对 PostgreSQL 数据后单独执行。

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
等待 OpenAI 认证跳转；前端尚未接手且确认异常时使用一次 NextAuth 兜底，已提交但结果未知时继续等待同一预算
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
核验邮箱身份，立即将账号、密码和完整会话保存到 PostgreSQL 并绑定任务及 Profile
  ↓
使用当前注册代理查询套餐、Go / Plus 优惠和额度并保存注册地区
  ↓
确认正常首页就绪后收紧注册静态资源；未就绪继续放行
  ↓
可选 Codex OAuth（复用当前 Profile、代理和登录态）
  ↓
可选 2FA，并保存后处理结果
  ↓
关闭/删除 Roxy Profile
```

Codex Protocol 登录后若进入 `/sign-in-with-chatgpt/codex/consent`，仅在受信任页面返回 HTTP 200、
未返回 JSON 后续状态且当前 Cookie / Auth 元数据确认唯一一致的工作区时，继续提交工作区选择并校验
callback 的 `state`。工作区缺失或冲突时仍需浏览器驱动；任务详情会显示
`OA-CODEX-CONSENT-001` 和具体原因，同时保留远端结果核验状态。

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

### 提链平台配置

提链工作台由 `EXTRACT_LINK_ENABLED` 总开关控制，默认平台为 `legacy`，默认模式为 `extract_only`。全局提取、手动支付、自动支付和支付后检查/刷新 AT/查询套餐开关，与对应平台开关取交集；自动支付及支付后操作默认关闭。支付后刷新 AT 还依赖支付后检查，并且只在检查确认 AT 失效时触发。每个平台可单独设置启用状态、能力开关和并发，默认并发为 1；`lumen_flow`、`huanguang` 新平台默认关闭。

提链前行为可在“配置 → 提链 → 通用配置”调整：`EXTRACT_LINK_PREFLIGHT_ENABLED` 控制“提链前预检”，`EXTRACT_LINK_PREFLIGHT_REFRESH_AT_ENABLED` 控制“预检失败时刷新 AT”，两项默认开启，保持原有流程。保存后热加载，对下一次执行或重跑生效；已开始的执行沿用本次设置。只有启用预检并确认 AT 失效时才会按刷新开关尝试刷新；关闭刷新后，预检确认 AT 失效会结束本次提链。关闭预检后直接使用库中保存的 AT，不执行提链前检查或刷新；账号是否归档、停用、缺少 AT 等基础资格仍会校验。

`legacy` 的连接参数继续使用既有环境变量 `EXTRACT_LINK_API_BASE`、`EXTRACT_LINK_CDK`、`EXTRACT_LINK_TYPE`、`EXTRACT_LINK_REQUEST_TIMEOUT` 和 `EXTRACT_LINK_EVENT_TIMEOUT`，不另建重复配置键。新平台各自配置 API 地址、CDK、默认提链类型、请求超时、轮询间隔和事件超时。CDK 属于密钥，只在 `.env` 中保存，配置 API 和快照不返回密钥内容。

提链成功后，卡片的“支付入口”按需显示平台返回的支付页面、支付链接、原生二维码图片及可复制的二维码内容；平台没有返回的字段会明确标注，不把普通网页链接生成付款码。平台支付状态、平台 Plus 状态与本地到账核验分别展示。旧任务未保存二维码时，可用“同步状态”读取原远端任务补齐，无需重新提链；打开支付入口本身仅读取本地已保存内容，不触发支付。任务中心按独立提链、支付状态展示结果，后续支付失败或待确认不会把已成功的提链写成失败。

接口契约以[流光文档](https://int31.space/public/checkout-api)和[幻光文档](https://chongyun-link.xiaoliai.shop/static/api-docs.html)为准。流光记录平台步骤、百分比、任务/步骤尝试次数及 `failureCode/failureType`；平台 Plus 验证不能代替本地套餐核验。幻光当前仅开放 UPI，默认类型为 `upi`；出链成功依据有效支付材料判断，顶层任务 `done` 本身不足以证明成功。

幻光提链失败时，卡片优先显示平台返回的具体错误、失败阶段和原因；例如“提链 CDK 次数已用完，任务未执行”，不会被通用的“任务处理失败”覆盖。旧任务也会从已经保存的失败信息中补全显示，无需同步或重跑；没有具体记录时保留原错误，不推测原因。

幻光新提链执行前会只读检查提链 CDK 额度；自动支付还检查支付扫码 CDK。任一 CDK 次数耗尽、停用或额度暂无法确认时，原任务保留排队并显示等待原因，每 60 秒重新检查，不查 AT、不领取代理、不提交提链。补充额度或更新 CDK 后按原批次并发继续；已有原单的状态同步、支付和到账核验不受影响。正额度不缓存，本机并发提交也会先占用本地预算，避免同时使用最后一次；本地预算不代替平台实际扣次。提链平台明确关闭计次时放行，XXSYUN 备用扫码额度不能代替幻光主扫码额度。可通过只读 `GET /api/extract-link/huanguang/cdk-quota` 查询两种已配置 CDK 的可用次数，接口不返回密钥。

幻光创建任务或批次时可在 `options.retry_count` 指定单个远端任务内部的提链尝试次数，接受 1 至 10 的整数。例如 `{"retry_count":3}` 表示每个账号在该远端任务中最多尝试 3 次；省略时沿用平台默认值。该参数随任务保存，重新创建提链时继续使用，不影响扫码订单提交次数或仅查询原任务的行为。

「配置 → 提链 → 幻光」中的“幻光提链 CDK”（`EXTRACT_LINK_HUANGUANG_CDK`）用于创建提链任务，“幻光支付扫码 CDK”（`EXTRACT_LINK_HUANGUANG_PAYMENT_CDK`）用于自动支付扫码，两者分开保存。只有明确选择 `auto_payment` 模式、开启全局 `EXTRACT_LINK_AUTO_PAYMENT_ENABLED` 与平台 `EXTRACT_LINK_HUANGUANG_AUTO_PAYMENT_ENABLED`，并已配置支付扫码 CDK 时，请求才携带 `chongyun_auto_submit: true` 和 `chongyun_cdk`。仅提链与手动支付均不携带这两个扫码参数，也不使用支付扫码 CDK。自动支付开关默认关闭，支付扫码 CDK 默认空字符串；密钥仅保存在 `.env`，配置 API 和非敏感快照不返回内容。

同页可配置“XXSYUN API Key”（`EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY`）和“幻光超时后转 XXSYUN”（`EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED`，默认关闭）。幻光平台本身已实现后台逻辑：先走幻光扫码，90 秒未接单后取消并确认退次，才转 XXSYUN。本客户端仅在新建自动支付任务时透传 `scan_fallback_enabled` 和 `fallback_xxsyun_api_key`，由平台执行后台转单；缺少 Key 时不启用转单，仍先走幻光扫码。

XXSYUN Key 下方的“查询剩余次数”可读取已保存 Key 的次数，也可用尚未保存的非空输入查询；明确清空后查询会提示未配置，不会默用旧 Key。查询不会保存、清除或覆盖配置。剩余次数为零时显示 0，总次数和占用次数未返回时显示未知；剩余次数直接使用接口值，不再扣减占用次数。Key 属于密钥，仅保存在 `.env`，不会进入非敏感快照或任务数据，查询接口不回显 Key；查询失败仅显示固定中文提示。

幻光入口和出口代理池可在「配置 → 提链 → 幻光」分别填写，对应 `EXTRACT_LINK_HUANGUANG_ENTRY_PROXIES`、`EXTRACT_LINK_HUANGUANG_EXIT_PROXIES`。每行一条完整代理 URL，支持 `http`、`https`、`socks5`、`socks5h` 和认证信息，每侧去重后最多 500 条。填写某侧后，提链请求向平台发送该侧完整候选列表；某侧留空时，才为该侧从统一代理池领取 IN 线路。请提供适用于 UPI 的 IN 代理。两项默认空列表，保存后热加载，对下一次执行或重跑生效；代理地址只保存在 `.env`，配置 API 和非敏感快照不返回内容。已配置时输入框留空不会覆盖旧值，使用“清除”可恢复该侧的统一代理池来源。

新平台的 `EVENT_TIMEOUT` 表示本次持续监控的等待预算，不包含前置查活和远端创建，也不是平台任务的最长执行时间。轮询间隔和单次请求均受剩余预算限制；状态/步骤变化会写入任务事件，无变化时每 30 秒记录等待摘要，查询失败按 10/20/30 秒退避。预算到期保留远端任务，可继续同步状态或重跑；同步读取不会重新创建远端任务。幻光轮询默认 10 秒，流光默认 3 秒，均可单独配置。

幻光在首轮预算到期后自动转为同一次执行的定时续查，每次有限查询后释放线程与账号租约，等待期间显示“等待平台同步”。续查与新任务交替调度，最多同时占两个执行槽，仍受平台、批次和共享并发限制；并发为一时两类任务轮换。短暂网络失败保留上次有效结果继续查询，重启后恢复仍在自动查询范围内的原单。平台自动重提的子任务沿原凭据追踪，父子付款材料各自保存；当前付款入口属于当前子任务。

「配置 → 提链 → 幻光」可设置自动续查总时限（`EXTRACT_LINK_HUANGUANG_RECONCILE_TIMEOUT`，默认 3600 秒）、无进展等待（`EXTRACT_LINK_HUANGUANG_NO_PROGRESS_TIMEOUT`，默认 900 秒）和连续查询失败上限（`EXTRACT_LINK_HUANGUANG_MAX_QUERY_FAILURES`，默认 12 次）。总预算从原单首次监控起计算，包含首轮监控，不包含尚未创建原单时等待 CDK 的时间；重复旧状态、查询失败或服务重启不重新开始预算。达到任一限额，或连续 3 次原单查询返回 HTTP 404，就停止本地自动续查，明确显示“待核验”，保留原单引用和已有付款材料，不推断远端失败或再次支付。手动“同步状态”仍可读取原单一次，但不会因读到旧状态而无限重启自动续查；“重跑”仍按现有入口执行，创建新提链时继续检查双 CDK 额度。

平台声明支持提交回执时，幻光单账号也使用单行批次提交，随机回执凭据在发送前保存到私有存储。提交超时或响应丢失后仅查询原回执，不重复提交。旧任务没有任务 ID 且未保存回执凭据、或登录结果尚未确认时，仍需依据原始记录处理。工作台“运行中”只统计本地实际执行，不把已经结束查询的旧远端快照算入并发。

### 提链批次

提链工作台通过“新建批次”按注册日期、邮箱来源、邮箱搜索、历史提链状态和套餐优惠筛选账号。套餐优惠可选全部明确优惠、Plus 免费试用、半价、其他折扣或其他优惠；未知、无优惠、套餐待查及非 free 套餐不进入提链批次。预览显示总匹配数、本批计划数与前 20 个账号，无需逐个勾选。提交和执行前都会重新校验资格，排除归档、停用、没有 AT 或正在执行交互任务的账号；AT 过期的账号仍可进入批次，并按通用配置决定是否预检和刷新。新建批次可按所选平台选择提链类型，幻光当前仅支持 UPI。每批可设置并发账号数（1–16），默认值由配置项 `EXTRACT_LINK_BATCH_WORKERS` 控制。该值保存在批次中，任务重跑继续沿用；实际运行同时受本批并发、平台并发和共享账号操作预算限制。旧批次没有单独并发值时沿用既有平台与共享限制。

“启用平台”只控制平台开关；新建批次还要求该平台配置有效 API 地址和 CDK。启用但缺少连接配置的平台会在平台选项中显示为不可用并说明缺项。

工作台左侧新建批次，右侧查询批次和刷新；桌面任务每页 10 个，按五列两排展示；历史批次与任务分页固定在工作台底部，卡片区独立滚动，小屏幕按宽度减少列数。批次摘要可查看本批并发、计划、入队、跳过和提交失败数量，以及提链、支付和 Plus 核验的独立进度；运行中的批次自动刷新。筛选和任务卡片均限定在当前批次，重跑保留原批次归属。“全部任务”同时保留历史单独任务。创建请求使用持久提交标识，网络异常后重试会返回同一批次，避免重复选取下一批账号。

工作台重跑没有原单或提链已明确失败的任务时，沿用原运行模式和已保存的提链尝试次数，并重新检查该模式开关；自动支付任务继续使用自动支付，已有未失败原单则只同步原单状态。

已结束的失败或待确认任务，若支付尚未开始，可重新进入自动支付批次；历史提链提交记录不再单独阻止入队。已有支付处理中（`pending`）、支付结果未知（`unknown`）或支付成功（`succeeded`）记录时，继续拦截重复自动支付。

支付回执和 Plus 到账分别显示。自动或手动支付任务已经出链，且任务创建后的独立套餐查询成功确认 Plus/Pro 时，即使平台支付回执仍待确认，卡片也会显示“Plus 已到账”，并计入“Plus 已确认”筛选。任务开始前的历史查询、失败查询和仅提链任务不会因此被补记为本次到账。

幻光自动支付原单扫码已经完成、平台权益检测结束但仅给出推断结果时，可结合任务创建后成功的独立 Plus/Pro 套餐查询，确认支付成功；XXSYUN 已明确完成的原单也遵循这一核验规则。开启支付后套餐查询时，扫码完成即可触发独立查询，按支付后查活与刷新配置处理失效 AT，不必先等支付确认为成功。任务记录本地联合核验的来源与查询时间，保留平台原始推断标记；后续同步沿同一原单查询。扫码未完成、平台仍在查询或明确失败时，独立套餐结果不能单独把支付改成成功。

该独立套餐查询在提链原任务内完成，沿用套餐查询的国家、代理和重试配置，不创建另一条账号任务。查询确认 Plus/Pro 后立即收口原单；查询成功但仍是免费套餐显示“未确认到账”，查询失败单独记录失败，均可点击“同步”重查原单。进程中断后会恢复尚未完成的套餐核验，不重新提链或再次付款。

点击“同步状态”后，新 Run 入队时即继承同一原单的公开状态与私有恢复凭据，排队期间仍保留已出链记录。旧单首次查询未再返回支付材料时保留该单已保存的材料；平台自动重提产生子单时，“已提链”保留历史成功事实，当前支付入口仍只使用当前单的材料。

### 配置保存后没生效？

WebUI 配置页保存后会热加载。Codex 补跑线程启动前也会重新热加载一次配置。

配置页分为「注册与账号、代理与网络、邮箱与验证码、浏览器、服务集成、系统与维护」六组，常用参数优先展示，高级参数折叠。字段使用统一高度和对齐规则；枚举单选、国家和有序列表多选、数字范围校验复用统一交互。详细说明、配置键和来源收进可点击帮助，搜索仍可定位隐藏或高级配置。切换分类和保存失败时保留未保存值。

密钥只显示是否配置，留空未修改不会覆盖旧值，明确清除后才删除配置值。`EMAIL_SOURCE` 是邮箱启用的唯一开关：自动模式至少启用一个来源，手动模式可为空。邮箱资源页默认只显示已启用来源和收码依赖；iCloud 使用 `forward_butler` 时始终保留 Email Butler 入口。停用服务的配置、库存和历史不删除，可通过“显示未启用”查看；已注册账号的取码仍按账号保存的来源恢复。

AT 刷新窗口、单轮上限、封号扫描首次延迟/回看天数、Outlook 远端地址和提链超时现在都由 schema、`.env.example` 和配置页统一维护。标记“需重启”的字段会写入 `.env`，但当前进程中的既有 worker 不会伪装成已切换，重启后才开始使用新值。

自动刷新 AT、刷新 Codex 凭证、封号邮件扫描和原始认证上下文清理在启动时关闭，也可以保存配置后启用；调度线程最长约 60 秒识别开关变化，实际执行仍遵循首次延迟、已保存的下次执行时间和扫描间隔。关闭开关会阻止下一轮执行，已经开始的任务继续完成。

配置页按实际执行范围校验重试次数、等待时间和每轮处理量。若历史 `.env` 超出范围，保存会指出具体键及允许范围，需要一起修正。`PLAN_CHECK_WORKERS`、`PLAN_CHECK_QUEUE_LIMIT` 仅保留历史环境变量兼容，已退出配置页；当前套餐查询等持久账号任务的并发由 `ACCOUNT_BATCH_WORKERS` 控制。

`config/schema.py` 统一维护可编辑配置默认值，`config/*.py` 导出对应模块常量。运行时配置通过 WebUI 配置页或 `.env` 覆盖；修改默认值源码后，已有 CLI 进程需要重启。

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
│   │   └── codex.py / integrations.py / health.py
│   ├── auth.py                     # 登录鉴权
│   ├── config_editor.py            # 配置白名单、.env 写入与热加载
│   ├── templates/                  # 现代界面 index.html / 登录页 login.html
│   └── static/                     # CSS、按页面/领域拆分的普通 JavaScript、favicon
│       ├── css/                   # foundation、modern、login 样式
│       └── js/                    # modern 八段业务脚本、proxy_traffic.js 和 login.js
├── tests/                          # pytest 统一收集，包含 unittest、存储隔离和契约测试
├── tools/                          # 迁移、诊断和单独补跑工具
├── docs/                           # 架构、流程、规范和路线图
└── sentinel/                       # Sentinel Node.js 子进程
```

历史 `accounts/`、`codex_accounts/`、`logs/`、`.env` 和 `.venv/` 等是本地运行时数据或凭证目录，故意不列入代码结构，也不得提交。

---

## 开发与验证

项目统一通过 `tools/test_isolated.py` 调用 `pytest`，现有 `unittest.TestCase` 也由 pytest 收集。先在已激活的开发环境中提供独立测试库的 `DATABASE_URL`；入口会禁用项目 dotenv、清除业务环境配置并检查非生产数据库，测试 schema 必须以 `test_` 开头，未指定时由入口生成。禁止连接生产数据库 `turb_console` 或使用 `public` schema。

小改动运行受影响功能的定向测试和相邻回归即可；只有共享存储、运行时、迁移、跨模块契约等风险，或明确的发布验收需要，才扩大范围，并说明原因。不要因为改了一个文件就默认全量，也不要按测试数量删除用例；调整测试应依据它保护的业务行为、重复覆盖和实际耗时。

```bash
# 定向验证：包含指定文件中的普通与扩展测试，不扫描其他测试文件
python tools/test_isolated.py --profile all -- tests/test_config_defaults.py -q

# 定向测试通过后，按影响范围补充相邻回归
python tools/test_isolated.py --profile all -- tests/test_config_ui.py tests/test_dashboard_api.py -q

# 静态检查
ruff check .
ruff check --select E4,E7,E9,F --exit-zero .
```

`--profile default` 只选未标记 `extended` 的测试；`--profile extended` 只选扩展测试，不包含 default；`--profile all` 不加 marker 筛选，但仍受后面指定的文件、目录或用例节点限制。因此 `all -- tests/test_config_ui.py` 只是该文件的全部用例；不指定路径时，pytest 才按 `tests/` 收集整个测试目录。不要将 profile 与 pytest 的 `-m`/`--markexpr` 同时使用。完整的范围选择与交付规则见[发布与验证](docs/development/release-verification.md)。

存储测试继承 `tests.support_pg.PostgresTestCase`；该基类创建临时 schema、重定向兼容导出并在用例间清理数据，与统一隔离入口配合使用。详细存储约束见[存储架构](docs/architecture/storage-architecture.md)。

涉及真实浏览器或外部服务时，先验证单任务，再逐步增加并发；测试结论要区分静态测试、数据库状态、浏览器链路和实际服务运行状态。

---

## 使用建议

- 日常批量使用 WebUI，不建议直接同时开多个 CLI 进程。
- 注册线程数建议不超过可用代理数。
- 如果要复用账号环境，Roxy 一号一环境和账号环境复用建议保持开启，并关闭 `ROXY_DELETE_PROFILE_AFTER_RUN`；如果优先释放 Roxy Profile/窗口额度，则开启删除开关，但后续任务会重新创建环境，不能同时获得 Profile 复用和删除后的额度释放。
- 调试页面或接口问题时，在「发起注册」勾选「调试模式」，随后发起注册或重跑。该开关作用于本次提交的任务：Roxy 强制显示窗口，抓包按任务隔离；账号配置补跑也在登录前启动抓包，失败后在清理浏览器前保存现场。点击「释放现场」、停止任务或达到保留超时后继续自动清理。
- 原身份续跑进入页面提供的密码登录入口时，整体导航超时后会重新检查页面；同源密码页已有可用密码框且阶段预算尚有剩余时继续登录，仍为空白或没有可用密码框时保留失败。
- 账号配置补跑和其他账号登录在验证码页发现页面实际提供的同源密码入口、且本地保存了 OpenAI 密码时，也会在原预算内最多进入一次该密码页；入口未提供或页面仍要求邮箱验证码时继续原收码分支。
- 账号配置从 ChatGPT 登录页重新登录时，与注册共用邮箱准备、提交及认证跳转预算和一次导航恢复。表单未就绪或提交未确认时保留原始错误，不再跳过登录直接读取 session；页面进度会显示加载、派发及确认阶段。
- Roxy 注册先保留自然捕获的权益快照（省流量模式在切换轻量页前读取，普通模式在首页观察后读取），Codex 和 2FA 结束后集中补查套餐与额度，「查询套餐」计时只覆盖这段处理。主动请求只允许在 ChatGPT 页面内发送，受浏览器内中止超时约束，结束后恢复原脚本超时；日志单独记录本轮查询耗时与来源。后台补查仍使用独立任务。
- 在任务日志的「网络调试」区域查看请求状态、阶段、耗时和错误，可选择同批成功任务自动对比，也可下载已经脱敏和限流的 HAR。Cookie、Token、密码、OTP、邮箱和 URL 查询值不会明文写入抓包。
- Roxy 注册进入邮箱验证码路由后，先确认输入框已挂载。持续空白 3 秒、出现 `400 Invalid content type: text/html` 或明确的 `5xx` Route Error 时，本次浏览器执行最多刷新一次，沿用原阶段预算；验证码提交后的刷新只观察原结果，不重复填写、提交或自动重发。
- 验证码页的认证初始化请求尚未结束、页面仍在加载或水合时，先在原预算内等待，不按空白时长提前刷新。原身份显式续跑在进入密码步骤前若确认认证会话失效，可在该步骤剩余预算内先切离失效文档、再重新登录一次，沿用原邮箱和密码，并按新登录的邮件时间收码；旧请求记录继续保留。
- 原身份续跑若页面仍明确提供创建密码入口，会进入该实际链接并使用保存的原密码。资料页准备和提交后确认分别计时；注册入口点击资料提交后最多等待 `90` 秒确认完整会话，保留有界刷新恢复时间，不重复提交资料。
- 登录页 GET 遇到隧道或连接重置错误时，最后一次导航可额外只读观察最多 `10` 秒；仅确认受信来源出现可用控件后继续，不追加 GET 或表单提交。同一任务换线后的每次调试失败均单独暂停，上一轮的结束调试不会自动释放下一轮现场。
- 注册验证码提交后若已回到 ChatGPT，使用剩余确认预算读取完整会话并匹配原邮箱，不再循环启动两秒 Token 探测。已核验会话供资料确认和 Token 保存复用；读取失败时仍只做有界页面恢复，不能凭首页 URL 或接口响应头判定账号成功。
- 邮箱验证码输入触发但被页面取消的表单事件，不再阻止首次点击「继续」。脚本会确认当前表单仍可用并点击一次；已观察到验证码请求、同表单 POST 或未取消的原生 POST 时继续等待原结果。日志只记录事件取消状态、请求次数与点击标记，不记录验证码。
- Roxy 失败任务已结束且浏览器仍保留时，重跑优先接管同一 Attempt 的原窗口。已经进入邮箱验证码或资料页且可继续时，从当前步骤继续；密码或验证码提交仍未知、重发结果未知，或认证页为空白/邮箱入口时，使用保存的原密码自动进入新的登录流程，服务器仍要求创建密码时也沿用原密码。新登录按新邮件时间收码，旧未知提交记录持续保留，不要求人工核对。缺少原邮件时间时不能使用旧页面开始收码。旧 worker 尚未退出或调试现场仍暂停时不能接管。保留窗口打开时即在 PostgreSQL 的 Attempt 私有上下文保存最小连接资料，失败收口时更新原邮件时间；进程重启后，账号尚未落库的任务也能恢复原窗口。有账号绑定的历史 Profile 仍支持恢复调试连接。原窗口已关闭或没有保存连接关联时，使用原邮箱、原密码继续认证。
- 原身份续跑遇到邮箱认证停滞时，可在共享总预算内通过新页面最多恢复一次登录；原提交事实继续保留。已保存密码的登录在刷新后确认同一邮箱的新密码表单，可补填原密码一次，两次提交共用最初截止时间。已进入验证码、资料或完整登录态时直接向后推进，不重复提交。OAuth 回调错误页、验证码页缺少可信原邮件时间时，沿用原身份重新登录；完整调试模式会保存刷新前的页面现场。
- 普通失败任务在同一日志面板显示「失败诊断」：分类、页面状态、失败请求和截图；普通模式不会保存成功请求或请求/响应正文。
- 保留时间、并发暂停数、单正文/单任务/全局容量、产物保留天数和异步队列长度在「配置 → 注册设置 → 注册调试」管理。调试抓包位于 `logs/debug/<job_uuid>/`，属于运行时私有数据，不得提交。
