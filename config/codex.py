# -*- coding: utf-8 -*-
"""
注册成功后自动跑 Codex OAuth 授权的配置项。
设置 ENABLE_CODEX = False 可完全跳过此步骤。

参数来源：CLIProxyAPI 源码 internal/auth/codex/openai_auth.go + pkce.go，
对照 https://github.com/router-for-me/CLIProxyAPI 逐行确认。
"""
from config.env_loader import env_str, apply_env_overrides


# 是否启用 Codex OAuth 授权（False = 跳过，不影响注册结果）
ENABLE_CODEX: bool = False

# Codex OAuth 客户端 ID（固定值，来自 CLIProxyAPI openai_auth.go:27 ClientID）
CODEX_CLIENT_ID: str = "app_EMoamEEZ73f0CkXaXp7hrann"

# 授权端点（openai_auth.go:25 AuthURL）
CODEX_AUTH_URL: str = "https://auth.openai.com/oauth/authorize"

# 换 token 端点（openai_auth.go:26 TokenURL）
CODEX_TOKEN_URL: str = "https://auth.openai.com/oauth/token"

# 回调地址（openai_auth.go:28 RedirectURI）
# 注意：本地并不真的起这个 server，只用来拦截重定向并从 Location 提取 code。
CODEX_REDIRECT_URI: str = "http://localhost:1455/auth/callback"

# OAuth scopes（openai_auth.go:75 GenerateAuthURL 里的 scope）
CODEX_SCOPE: str = "openid email profile offline_access"

# 输出目录名（仅名字，运行时拼到项目根；与 OUTLOOK_ACCOUNTS_FILE 同级风格）
CODEX_OUTPUT_DIRNAME: str = "codex_accounts"

# 请求超时（秒）
CODEX_REQUEST_TIMEOUT: int = 30

# ChatGPT access token（AT）自动刷新。原先只能通过环境变量控制，现在纳入配置
# 体系，WebUI 可改、可热加载。
AT_AUTO_REFRESH_ENABLED: bool = True
AT_REFRESH_SCAN_INTERVAL_SECONDS: int = 3600

# Codex OAuth access token 自动刷新。refresh token 仍有效时无需重新跑完整
# OAuth 登录、邮箱 OTP 和短信验证。
CODEX_TOKEN_AUTO_REFRESH_ENABLED: bool = True

# 在 access token 到期前多少小时进入自动刷新窗口。
CODEX_TOKEN_REFRESH_BEFORE_HOURS: int = 24

# 后台扫描间隔、WebUI 启动后的首次扫描延迟，以及单轮最多入队数量。
CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS: int = 86400
CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS: int = 120
CODEX_TOKEN_REFRESH_MAX_PER_CYCLE: int = 20

# 只有曾由当前版本上传到 sub2api 的凭证才会在刷新后自动同步。
CODEX_TOKEN_AUTO_SYNC_SUB2API: bool = True


# ============================================================
# Codex 授权方式（2026-06-15 改造）
#
# 旧方案"复用注册的已登录 session"会撞 /choose-an-account 卡死；
# 新方案用全新干净 session 从头登录，走 OpenAI 标准风控路径
# （邮箱 OTP → 手机短信验证 → 选 workspace → 拿 code），
# 手机验证靠接码平台 GrizzlySMS 自动收码。
# ============================================================

# 注册成功后是否自动跑 Codex 授权（True=自动，False=跳过）
ENABLE_CODEX_AUTO: bool = False

# WebUI 账号页批量操作的默认并发数（查活、查套餐、Codex 补跑等）。
# 页面不再临时填写，统一在「配置 → 通用配置」维护。
ACCOUNT_BATCH_WORKERS: int = 3

# Codex OAuth 授权驱动：
#   "protocol" = 原有 curl_cffi 协议授权
#   "roxy"     = 调用 RoxyBrowser 指纹浏览器完成授权页面/手机验证/回调捕获
#   "cloak"       = 调用 CloakBrowser 完成授权页面/手机验证/回调捕获
#   "browser_use" = 调用 Browser Use Cloud 完成授权页面/手机验证/回调捕获
#   "same_as_registration" = 跟随 REGISTRATION_DRIVER
CODEX_OAUTH_DRIVER: str = "roxy"




# ============================================================
# CPA 管理接口（Codex 授权地址由 CPA 生成，本地只负责跑登录并提交回调）
# ============================================================

# 授权地址来源：
#   "cpa"   = 通过 CPA 管理接口 /v0/management/codex-auth-url 生成（推荐）
#   "sub2"  = 通过 sub2 管理接口生成，并把 callback 上传到 sub2
#   "local" = 使用本模块保留的本地 PKCE 生成逻辑（兼容旧方案）
CODEX_AUTH_URL_SOURCE: str = "cpa"

# CPA 管理页面或服务地址，例如 http://localhost:8317/admin/oauth
# 实际请求会取 origin，调用：
#   GET  /v0/management/codex-auth-url
#   POST /v0/management/oauth-callback
CPA_MANAGEMENT_URL: str = "http://127.0.0.1:8317/management.html"#/oauth"

# CPA 管理密钥，同时作为 Authorization: Bearer 和 X-Management-Key
CPA_MANAGEMENT_KEY: str = env_str("CPA_MANAGEMENT_KEY", "")

# CPA 管理接口请求超时（秒）
CPA_REQUEST_TIMEOUT: int = 30

# 提交 OAuth callback 给 CPA 的重试次数/基础间隔。
# 遇到 409 Timeout waiting for OAuth callback、网络超时或 5xx 时，会按同一个 callback URL 重试。
CPA_CALLBACK_SUBMIT_RETRIES: int = 5
CPA_CALLBACK_SUBMIT_RETRY_DELAY: int = 6

# CPA 未返回完整 auth json 时，是否仍在本地 codex_accounts/ 记录一份回调提交凭据
CPA_SAVE_CALLBACK_RECEIPT: bool = True

# ============================================================
# 接码平台（手机短信验证用）
# SMS_PROVIDER:
#   "grizzly" = GrizzlySMS，接口说明见 https://api.grizzlysms.com
#   "l"       = 本地 L 取号服务，接口说明见 L_API.md
#   "h"       = 本地 H 取号服务，接口说明见 H_API.md
# ============================================================

SMS_PROVIDER: str = "l"

# 接码 API 基址（GET handler）
SMS_API_BASE: str = "https://api.grizzlysms.com/stubs/handler_api.php"

# 接码 API 密钥（在 GrizzlySMS 后台 → 设置 获取）
# 留空时 Codex 授权的手机验证步会失败；如不需要 Codex 自动授权，把 ENABLE_CODEX_AUTO=False。
SMS_API_KEY: str = env_str("SMS_API_KEY", "")

# 服务代码：OpenAI = "dr"
SMS_SERVICE: str = "openai"

# 国家代码：葡萄牙 = "117" / 美国 = "187"
SMS_COUNTRY: str = "10"

# 单个号愿意支付的最高价格（留空=不限）。透传给 getNumber 的 maxPrice。
SMS_MAX_PRICE: str = ""

# GrizzlySMS 每个注册批次第一次接码前，按价格页的短信成功率自动选择国家；
# 同一批次后续任务优先沿用该国家。统计/价格接口不可用时回退 SMS_COUNTRY。
SMS_AUTO_SELECT_COUNTRY: bool = True

# GrizzlySMS 价格页统计量的最低门槛。用于排除“成功率 100% 但样本极少”的国家。
SMS_AUTO_COUNTRY_MIN_RATIO: int = 25

# 一个号收不到短信/被拒时，换号重试的最大次数
SMS_MAX_RETRIES: int = 10

# 单个号等待短信的硬上限。超时后取消任务交给后台队列，不阻塞注册线程。
SMS_CODE_WAIT: int = 120

# Codex 手机验证整段硬预算（含取号、页面操作、等短信和换号），避免多次换号无限拉长。
CODEX_PHONE_TOTAL_TIMEOUT: int = 300

# 轮询接码平台查短信的间隔（秒）
SMS_POLL_INTERVAL: int = 5

# 接码平台 HTTP 请求超时（秒）
SMS_REQUEST_TIMEOUT: int = 30


# ============================================================
# H 取号服务（SMS_PROVIDER="h" 时使用）
# ============================================================

# H API 基址，例如本地后台：http://localhost:8788
H_API_BASE: str = "http://localhost:8788"

# H 后台授权码，对应 H_API.md 里的 Authorization: Bearer <ADMIN_AUTH_CODE>
H_ADMIN_AUTH_CODE: str = env_str("H_ADMIN_AUTH_CODE", "")

# H 返回的号码如果不含国家码，可在这里补前缀；留空则直接使用 H 返回的 item.phone。
H_PHONE_PREFIX: str = ""

# H 取号方式：
#   "reusable" = 优先复用号码，调用 /api/admin/h/take-reusable-phone（默认）
#   "new"      = 每次取新号，调用 /api/admin/h/take-phone
H_PHONE_ACQUIRE_MODE: str = "reusable"


# ============================================================
# L 取号服务（SMS_PROVIDER="l" 时使用）
# ============================================================

# L API 基址，例如本地后台：http://localhost:8788
L_API_BASE: str = "http://localhost:8788"

# L 后台授权码，对应 L_API.md 里的 Authorization: Bearer <ADMIN_AUTH_CODE>
L_ADMIN_AUTH_CODE: str = env_str("L_ADMIN_AUTH_CODE", "")

# L 返回的号码如果不含国家码，可在这里补前缀；例如美国本地 10 位号填 "1"。
# 留空则直接使用 L 返回的 item.phone。
L_PHONE_PREFIX: str = ""

# ---- .env overrides for WebUI editable fields ----
apply_env_overrides(globals(), {'ENABLE_CODEX_AUTO': 'bool', 'AT_AUTO_REFRESH_ENABLED': 'bool', 'AT_REFRESH_SCAN_INTERVAL_SECONDS': 'int', 'ACCOUNT_BATCH_WORKERS': 'int', 'CODEX_TOKEN_AUTO_REFRESH_ENABLED': 'bool', 'CODEX_TOKEN_REFRESH_BEFORE_HOURS': 'int', 'CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS': 'int', 'CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS': 'int', 'CODEX_TOKEN_REFRESH_MAX_PER_CYCLE': 'int', 'CODEX_TOKEN_AUTO_SYNC_SUB2API': 'bool', 'CODEX_OAUTH_DRIVER': 'str', 'CODEX_AUTH_URL_SOURCE': 'str', 'CPA_MANAGEMENT_URL': 'str', 'CPA_MANAGEMENT_KEY': 'str', 'CPA_REQUEST_TIMEOUT': 'int', 'CPA_CALLBACK_SUBMIT_RETRIES': 'int', 'CPA_CALLBACK_SUBMIT_RETRY_DELAY': 'int', 'CPA_SAVE_CALLBACK_RECEIPT': 'bool', 'SMS_PROVIDER': 'str', 'SMS_COUNTRY': 'str', 'SMS_SERVICE': 'str', 'SMS_MAX_PRICE': 'str', 'SMS_AUTO_SELECT_COUNTRY': 'bool', 'SMS_AUTO_COUNTRY_MIN_RATIO': 'int', 'SMS_MAX_RETRIES': 'int', 'SMS_CODE_WAIT': 'int', 'CODEX_PHONE_TOTAL_TIMEOUT': 'int', 'SMS_API_KEY': 'str', 'H_API_BASE': 'str', 'H_ADMIN_AUTH_CODE': 'str', 'H_PHONE_PREFIX': 'str', 'H_PHONE_ACQUIRE_MODE': 'str', 'L_API_BASE': 'str', 'L_ADMIN_AUTH_CODE': 'str', 'L_PHONE_PREFIX': 'str'})
