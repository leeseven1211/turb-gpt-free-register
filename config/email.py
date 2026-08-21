# -*- coding: utf-8 -*-
"""
Outlook 邮箱账号池配置。

注册邮箱与 OTP 均只走 Outlook 账号池：
    1. 把邮箱素材写入项目根目录 `用于注册的邮箱.txt`
    2. 每行格式：email====password====clientId====refreshToken
    3. 运行注册时会自动导入新增邮箱
"""
from config.env_loader import env_str, apply_env_overrides


# True: REGISTER_EMAIL 留空时从 Outlook 账号池自动获取邮箱，OTP 自动收取
# False: 走人工输入邮箱 + 人工填 OTP 的流程
USE_EMAIL_SERVICE = False

# 可选值（也可以用英文逗号配置多个，作为 WebUI 注册页的可选来源列表）：
# WebUI 每批必须明确选择一个来源；任务领取失败时不会跨平台兜底。
#   "outlook"           — 外购 Outlook 账号池 + mail.chatai.codes 远端取信
#   "cloudflare_domain" — Cloudflare 域名邮箱（转发到 QQ 邮箱），通过 IMAP 取信
#   "cloudflare" — Cloudflare Worker 临时邮箱（cloudflare_temp_email），API 创建并取码
#   "email_butler" — Email Butler 通用 /v1 Mail API（租用 + 收信 + 释放）
#   "generic_api"       — 通用 API 取码邮箱池（邮箱----取码地址）
#   "gptmail"           — GPTMail 临时邮箱 API（运行时随机生成邮箱并自动收码）
#   "mailnest"          — MailNest/迈巢临时邮箱 API（运行时购买邮箱并自动收码）
#   "cloudmail"         — CloudMail/Cloud Mail API（自动从平台获取域名并随机生成邮箱）
#   "icloud_hide"       — iCloud Hide My Email 别名池（可用本机 Gmail IMAP 或 Email Butler 收码）
EMAIL_SOURCE = "outlook,generic_api,mailnest"


# ============================================================
# Outlook 模式（外购账号池 + 取信服务）
# ============================================================

OUTLOOK_ACCOUNTS_FILE = "用于注册的邮箱.txt"

# Outlook 取件模式：
#   "auto"   = 先用远端 mail.chatai.codes；远端 402/DEPLOYMENT_DISABLED 时自动切 Microsoft Graph 直连
#   "remote" = 只用远端 mail.chatai.codes
#   "direct" = 只用 Microsoft Graph 直连（使用 clientId + refreshToken 换 access_token）
OUTLOOK_FETCH_MODE = "auto"

# 取邮件 API 的根 URL（远端模式使用）
OUTLOOK_API_BASE = "https://mail.chatai.codes"


# ============================================================
# OTP 轮询参数
# ============================================================

OTP_POLL_INTERVAL = 3
# Email Butler 的 PG 接口是长轮询：邮件入库后会立即返回，但 iCloud 转发到
# Gmail/PG 的上游链路在高并发时 P90 可超过 3 分钟。默认等待 240 秒，避免
# 90 秒过早超时后立即重发，制造多封验证码和错误码竞争。
OTP_MAX_WAIT = 240

# Outlook 双协议取件：抓到一封 OTP 后再多等多少秒看是否有更晚到达的邮件。
OTP_SETTLE_SECONDS = 5


# ============================================================
# Email Butler 通用 Mail API（/v1）
# ============================================================

EMAIL_BUTLER_API_BASE = env_str("EMAIL_BUTLER_API_BASE", "")
EMAIL_BUTLER_API_KEY = env_str("EMAIL_BUTLER_API_KEY", "")
EMAIL_BUTLER_REQUEST_TIMEOUT = 20

# 封号邮件周期扫描。原先只能通过环境变量控制，现在纳入配置体系。
EMAIL_BUTLER_RISK_SCAN_ENABLED: bool = True
EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS: int = 21600


# ============================================================
# Cloudflare 域名邮箱模式（转发到 QQ 邮箱，通过 IMAP 取信）
# ============================================================

# 你的 Cloudflare 域名，如 "mydomain.com"
# 注册时会自动生成 random@mydomain.com 作为注册邮箱
EMAIL_DOMAIN = ""

# QQ 邮箱 IMAP 服务器地址（固定为 imap.qq.com）
QQ_IMAP_SERVER = "imap.qq.com"

# QQ 邮箱 IMAP 端口（SSL）
QQ_IMAP_PORT = 993

# QQ 邮箱地址（接收 Cloudflare 转发的邮件），如 "123456@qq.com"
QQ_EMAIL = ""

# QQ 邮箱 IMAP 授权码（在 QQ 邮箱网页版 → 设置 → 账户 → POP3/IMAP/SMTP 服务 中生成）
# 注意：这是 16 位授权码，不是 QQ 密码
QQ_IMAP_PASSWORD = env_str("QQ_IMAP_PASSWORD", "")


# ============================================================
# GPTMail 临时邮箱 API（固定地址：https://mail.chatgpt.org.uk）
# ============================================================

# 选择 EMAIL_SOURCE="gptmail" 时必填；请在 WebUI「配置 → 邮箱 / OTP」填写。
GPTMAIL_API_KEY = env_str("GPTMAIL_API_KEY", "")


# ============================================================
# Cloudflare Worker 临时邮箱（cloudflare_temp_email 兼容）
# EMAIL_SOURCE 含 "cloudflare" 时启用；与 cloudflare_domain（QQ IMAP）不同。
# ============================================================

# Worker API 根地址，例如 https://mail.example.com
CLOUDFLARE_API_BASE = env_str("CLOUDFLARE_API_BASE", "")

# 匿名模式可留空；admin 模式填 ADMIN_PASSWORD
CLOUDFLARE_API_KEY = env_str("CLOUDFLARE_API_KEY", "")

# 只读封号邮件信号接口，建议使用与创建邮箱分离的 Key。
CLOUDFLARE_SIGNAL_API_KEY = env_str("CLOUDFLARE_SIGNAL_API_KEY", "")
CLOUDFLARE_SIGNAL_PATH = "/signals/scan"

# none / bearer / x-api-key / x-admin-auth / query-key
CLOUDFLARE_AUTH_MODE = "none"

# Worker 全局密码（PASSWORDS），注入请求头 x-custom-auth
CLOUDFLARE_CUSTOM_AUTH = env_str("CLOUDFLARE_CUSTOM_AUTH", "")

CLOUDFLARE_PATH_DOMAINS = "/api/domains"
CLOUDFLARE_PATH_ACCOUNTS = "/api/new_address"
CLOUDFLARE_PATH_TOKEN = "/api/token"
CLOUDFLARE_PATH_MESSAGES = "/api/mails"

# 默认收信域名，多个可用换行或逗号分隔；留空则由 Worker 决定
CLOUDFLARE_DEFAULT_DOMAINS = []

CLOUDFLARE_REQUEST_TIMEOUT = 20
CLOUDFLARE_NAME_LENGTH = 10


# ============================================================
# MailNest-迈巢 Outlook 临时邮箱：https://mailnest.top/
# ============================================================

# 选择 EMAIL_SOURCE="mailnest" 时必填；请在 WebUI「配置 → 邮箱 / OTP」填写。
MAIL_NEST_API_KEY = env_str("MAIL_NEST_API_KEY", "")

# MailNest 项目代码；OpenAI/ChatGPT 默认 chatgpt001。
MAIL_NEST_PROJECT_CODE = "chatgpt001"

# ============================================================
# CloudMail API 文档：https://doc.skymail.ink/api/api-doc
# ============================================================

# Cloud Mail Worker/API 地址，例如：https://mail.example.com
CLOUDMAIL_API_BASE = ""

# CloudMail 管理员邮箱/密码；用于手动生成 Token，也用于域名被隐藏时自动登录获取域名。
CLOUDMAIL_ADMIN_EMAIL = env_str("CLOUDMAIL_ADMIN_EMAIL", "")
CLOUDMAIL_PASSWORD = env_str("CLOUDMAIL_PASSWORD", "")

# CloudMail 生成 Token 接口路径；默认按 Cloud Mail 公共 API 风格。
CLOUDMAIL_TOKEN_PATH = "/api/public/genToken"

# CloudMail/Cloud Mail API Authorization Token；可手动填写，也可由账号密码自动获取。
CLOUDMAIL_AUTH_TOKEN = env_str("CLOUDMAIL_AUTH_TOKEN", "")

# 邮箱域名列表，每行一个或用英文逗号分隔；可留空，运行时会从 CloudMail 平台自动获取。
CLOUDMAIL_DOMAINS = []

# 生成邮箱后是否调用 /api/public/addUser 创建邮箱用户。
CLOUDMAIL_AUTO_ADD_USER = True

# 随机邮箱 local-part 长度。
CLOUDMAIL_RANDOM_LOCAL_LENGTH = 12


# ============================================================
# iCloud Hide My Email 本地服务
# ============================================================

# 本机 sidecar 地址；Apple Cookie 和 App 专用密码只保存在 sidecar 项目中。
ICLOUD_HME_API_BASE = "http://127.0.0.1:8081"

# sidecar 账号 ID；留空时自动选择第一个 active 账号。
ICLOUD_HME_ACCOUNT_ID = ""

# 预留的本地 API Token；当前仅绑定 127.0.0.1 时可留空。
ICLOUD_HME_API_TOKEN = env_str("ICLOUD_HME_API_TOKEN", "")

ICLOUD_HME_REQUEST_TIMEOUT = 35
ICLOUD_HME_SYNC_TTL = 300

# 隐藏邮箱验证码实际收件方式：
#   sidecar     = sidecar 读取 iCloud IMAP（forwardToEmail 必须是 iCloud 邮箱）
#   forward_imap = 本机直接连接转发目标 Gmail，注册任务本地取 OTP
#   forward_butler = Oracle 监听 Gmail 并写入 Email Butler PG
ICLOUD_HME_INBOX_MODE = "sidecar"
ICLOUD_HME_FORWARD_IMAP_SERVER = "imap.gmail.com"
ICLOUD_HME_FORWARD_IMAP_PORT = 993
ICLOUD_HME_FORWARD_IMAP_EMAIL = ""
ICLOUD_HME_FORWARD_IMAP_PASSWORD = env_str("ICLOUD_HME_FORWARD_IMAP_PASSWORD", "")

# 库存为空时是否调用 sidecar 自动创建新隐藏邮箱。默认关闭，优先复用已同步别名。
ICLOUD_HME_AUTO_CREATE = False
ICLOUD_HME_CREATE_LABEL_PREFIX = "turb"

# ---- .env overrides for WebUI editable fields ----
apply_env_overrides(globals(), {'USE_EMAIL_SERVICE': 'bool', 'OTP_MAX_WAIT': 'int', 'OTP_POLL_INTERVAL': 'int', 'EMAIL_SOURCE': 'str', 'EMAIL_BUTLER_API_BASE': 'str', 'EMAIL_BUTLER_API_KEY': 'str', 'EMAIL_BUTLER_REQUEST_TIMEOUT': 'int', 'EMAIL_BUTLER_RISK_SCAN_ENABLED': 'bool', 'EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS': 'int', 'EMAIL_DOMAIN': 'str', 'QQ_EMAIL': 'str', 'QQ_IMAP_PASSWORD': 'str', 'GPTMAIL_API_KEY': 'str', 'OUTLOOK_FETCH_MODE': 'str', 'MAIL_NEST_API_KEY': 'str', 'MAIL_NEST_PROJECT_CODE': 'str', 'CLOUDFLARE_API_BASE': 'str', 'CLOUDFLARE_API_KEY': 'str', 'CLOUDFLARE_SIGNAL_API_KEY': 'str', 'CLOUDFLARE_SIGNAL_PATH': 'str', 'CLOUDFLARE_AUTH_MODE': 'str', 'CLOUDFLARE_CUSTOM_AUTH': 'str', 'CLOUDFLARE_PATH_DOMAINS': 'str', 'CLOUDFLARE_PATH_ACCOUNTS': 'str', 'CLOUDFLARE_PATH_TOKEN': 'str', 'CLOUDFLARE_PATH_MESSAGES': 'str', 'CLOUDFLARE_DEFAULT_DOMAINS': 'list_str_multiline', 'CLOUDFLARE_REQUEST_TIMEOUT': 'int', 'CLOUDFLARE_NAME_LENGTH': 'int', 'CLOUDMAIL_API_BASE': 'str', 'CLOUDMAIL_ADMIN_EMAIL': 'str', 'CLOUDMAIL_PASSWORD': 'str', 'CLOUDMAIL_TOKEN_PATH': 'str', 'CLOUDMAIL_AUTH_TOKEN': 'str', 'CLOUDMAIL_DOMAINS': 'list_str_multiline', 'CLOUDMAIL_AUTO_ADD_USER': 'bool', 'CLOUDMAIL_RANDOM_LOCAL_LENGTH': 'int', 'ICLOUD_HME_API_BASE': 'str', 'ICLOUD_HME_ACCOUNT_ID': 'str', 'ICLOUD_HME_API_TOKEN': 'str', 'ICLOUD_HME_REQUEST_TIMEOUT': 'int', 'ICLOUD_HME_SYNC_TTL': 'int', 'ICLOUD_HME_INBOX_MODE': 'str', 'ICLOUD_HME_FORWARD_IMAP_SERVER': 'str', 'ICLOUD_HME_FORWARD_IMAP_PORT': 'int', 'ICLOUD_HME_FORWARD_IMAP_EMAIL': 'str', 'ICLOUD_HME_FORWARD_IMAP_PASSWORD': 'str', 'ICLOUD_HME_AUTO_CREATE': 'bool', 'ICLOUD_HME_CREATE_LABEL_PREFIX': 'str'})
