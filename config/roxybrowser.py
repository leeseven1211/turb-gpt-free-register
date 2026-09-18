# -*- coding: utf-8 -*-
"""
RoxyBrowser 指纹浏览器自动化注册配置。

官方文档：
- API 默认 host: http://127.0.0.1:50000
- 所有接口请求头必须带 token
- 可配合 Selenium / Puppeteer / Playwright 自动化
"""
from config.env_loader import apply_env_overrides
from config.schema import schema_default


# 注册驱动：
#   "roxy"         = RoxyBrowser 主流程（推荐）
#   "protocol"     = 协议辅助/回退流程
REGISTRATION_DRIVER: str = schema_default("REGISTRATION_DRIVER")

# RoxyBrowser 本地 API
ROXY_API_BASE: str = schema_default("ROXY_API_BASE")
ROXY_API_TOKEN: str = schema_default("ROXY_API_TOKEN")

# Roxy 全局环境/Profile ID；一号一环境模式下不应配置它，账号绑定会优先使用账号元数据中的 Profile ID。
ROXY_PROFILE_ID: str = schema_default("ROXY_PROFILE_ID")

# Roxy 工作区 ID。Roxy 创建 Profile 时接口要求 workspaceId，必须填写。
# 可在 Roxy 工作区/团队页面或 API 返回中查看。
ROXY_WORKSPACE_ID: str = schema_default("ROXY_WORKSPACE_ID")

# Roxy 项目 ID。/browser/workspace 返回 project_details.projectId；创建 Profile 时一并提交。
ROXY_PROJECT_ID: str = schema_default("ROXY_PROJECT_ID")

# 获取团队/工作区列表接口路径。不同版本若不同，可在 WebUI 修改；客户端也会自动尝试多个常见路径。
ROXY_WORKSPACE_LIST_PATH: str = schema_default("ROXY_WORKSPACE_LIST_PATH")
ROXY_WORKSPACE_LIST_METHOD: str = "GET"

# 接口路径模板。不同版本如有差异，只改这里即可。
# {profile_id} 会替换为 ROXY_PROFILE_ID。
ROXY_OPEN_PATH: str = schema_default("ROXY_OPEN_PATH")
ROXY_CLOSE_PATH: str = schema_default("ROXY_CLOSE_PATH")
ROXY_CREATE_PATH: str = "/browser/create"

# 接口方法：常见 open/close 为 GET；若你的版本要求 POST，可在 WebUI/配置里改。
ROXY_OPEN_METHOD: str = "POST"
ROXY_CLOSE_METHOD: str = "POST"
ROXY_CREATE_METHOD: str = "POST"

# 打开浏览器时是否无头启动：
#   False = 显示 Roxy 浏览器窗口（便于观察/调试）
#   True  = 无头启动，不显示窗口（如果当前 Roxy 版本支持 headless）
ROXY_OPEN_HEADLESS: bool = schema_default("ROXY_OPEN_HEADLESS")

# Codex OAuth 专用的无头开关。默认显示窗口，避免 OAuth consent 页在无头渲染下
# 无法完成确认并最终卡在 localhost:1455 callback 等待；不影响注册流程的无头设置。
ROXY_CODEX_OPEN_HEADLESS: bool = schema_default("ROXY_CODEX_OPEN_HEADLESS")

# 打开浏览器时附加参数；会合并到 /browser/open 请求体，优先级高于默认值。
ROXY_OPEN_EXTRA_PARAMS: dict = {}

# Selenium 行为
ROXY_SELENIUM_TIMEOUT: int = 90
ROXY_KEEP_BROWSER_OPEN: bool = schema_default("ROXY_KEEP_BROWSER_OPEN")

# Roxy API transient 错误重试。create 仅在 Roxy 明确返回失败、并通过唯一环境名
# 查证没有创建成功后才重试；客户端超时/断连等结果未知场景不会盲目重复创建。
ROXY_API_RETRIES: int = 3
ROXY_API_RETRY_DELAY: int = 2

# Roxy 窗口达到套餐/本机上限时，不要让当前 worker 快速失败并继续消费后续
# 排队任务。保持任务在“启动浏览器”阶段等待，直到前面的窗口释放。
ROXY_WINDOW_WAIT_TIMEOUT: int = schema_default("ROXY_WINDOW_WAIT_TIMEOUT")
ROXY_WINDOW_WAIT_INTERVAL: int = schema_default("ROXY_WINDOW_WAIT_INTERVAL")

# 环境生命周期：
#   True  = 每个账号最多绑定一个 Profile；账号没有绑定时才创建新环境
#   False = 允许使用全局 ROXY_PROFILE_ID（兼容旧配置）
ROXY_ONE_PROFILE_PER_ACCOUNT: bool = schema_default("ROXY_ONE_PROFILE_PER_ACCOUNT")

# 是否在任务结束后删除本轮新建 Profile。默认 False：关闭浏览器但保留环境，后续可按账号绑定复用。
# 开启后即使 Profile 已绑定账号也会软删除，下一次使用需要重新创建环境。
ROXY_REUSE_ACCOUNT_PROFILE: bool = schema_default("ROXY_REUSE_ACCOUNT_PROFILE")
ROXY_DELETE_PROFILE_AFTER_RUN: bool = schema_default("ROXY_DELETE_PROFILE_AFTER_RUN")

# 删除环境接口路径/方法；如你的 Roxy 版本不同，只改这里。
ROXY_DELETE_PATH: str = "/browser/delete"
ROXY_DELETE_METHOD: str = "POST"

# 创建 Roxy 环境时随机系统指纹；开启后每次 /browser/create 在 Windows / macOS 里随机选一个，
# 避免固定 macOS 指纹。
ROXY_RANDOM_OS_ON_CREATE: bool = schema_default("ROXY_RANDOM_OS_ON_CREATE")
ROXY_RANDOM_OS_CHOICES: str = schema_default("ROXY_RANDOM_OS_CHOICES")

# 创建 Roxy 环境时随机名称；开启后会覆盖 ROXY_PROFILE_CREATE_PAYLOAD 里的固定 windowName。
ROXY_RANDOM_PROFILE_NAME_ON_CREATE: bool = schema_default("ROXY_RANDOM_PROFILE_NAME_ON_CREATE")
ROXY_PROFILE_NAME_PREFIX: str = schema_default("ROXY_PROFILE_NAME_PREFIX")

# 创建 Roxy 环境时默认系统指纹。仅在 ROXY_RANDOM_OS_ON_CREATE=False 时使用。
# Roxy 官方 os 枚举：Windows / macOS / Linux / IOS / Android。
ROXY_DEFAULT_OS: str = "macOS"
# 留空则使用 Roxy 对应系统的默认/最大版本；如需固定可填 15.3.2、14.7 等。
ROXY_DEFAULT_OS_VERSION: str = ""

# 创建 Roxy 环境时是否使用 config/proxy.py 的 PROXY_POOL：
#   False = 不主动给 Roxy 环境设置代理
#   True  = 每次创建环境时从 PROXY_POOL 随机取一个代理写入 proxyInfo
ROXY_CREATE_USE_PROXY_POOL: bool = schema_default("ROXY_CREATE_USE_PROXY_POOL")

# Roxy 代理检测通道；留空则不传 checkChannel。
ROXY_PROXY_CHECK_CHANNEL: str = schema_default("ROXY_PROXY_CHECK_CHANNEL")

# 没有 ROXY_PROFILE_ID 时创建环境的最小 payload；按你的 Roxy 版本字段调整。
# 默认开启 ROXY_RANDOM_PROFILE_NAME_ON_CREATE，因此这里的 windowName 只是兜底值。
ROXY_PROFILE_CREATE_PAYLOAD: dict = {
    "windowName": "gpt-free-register",
    "os": "macOS",
}


# Roxy Codex 授权等待 callback 的最长秒数
ROXY_CODEX_CALLBACK_TIMEOUT: int = schema_default("ROXY_CODEX_CALLBACK_TIMEOUT")

# ---- .env overrides for WebUI editable fields ----
apply_env_overrides(globals())
