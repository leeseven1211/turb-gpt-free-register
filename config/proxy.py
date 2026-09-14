# -*- coding: utf-8 -*-
"""
代理池配置

每次注册随机抽取一个代理，保证不同 sid 之间彼此独立，避免风控关联。

协议说明：
    - http:// / https://   HTTP(S) 代理
    - socks5://            SOCKS5（DNS 本地解析，可能泄漏）
    - socks5h://           SOCKS5（DNS 在代理端解析，推荐，避免 DNS-IP 错配）
"""
from config.env_loader import apply_env_overrides
from config.schema import schema_default
import random


# 本地代理入口；实际出口地区以代理/分流规则为准。
# 推荐使用 socks5h://（DNS 在代理端解析），避免本地 DNS 与出口 IP 地区错配。
PROXY_POOL = schema_default("PROXY_POOL")

# 注册任务代理来源：
#   pool = 使用上面的静态代理池（兼容原行为）
#   1024 = 每个注册任务从 1024Proxy API 提取一个独立的粘性住宅代理
#   none = 注册任务显式直连
REGISTRATION_PROXY_MODE = schema_default("REGISTRATION_PROXY_MODE")

# 1024Proxy 白名单 API。完整 URL 仅保存到 .env，源码默认留空。
# 客户端会保留 URL 中的筛选参数；单任务强制 num=1，注册批次按并发量批量设置 num，均使用下面配置的粘性时长。
PROXY_1024_API_URL = schema_default("PROXY_1024_API_URL")
# 国家/地区代码；留空时沿用 API URL 中原有的 region 参数。
# 1024Proxy 使用 ISO 3166-1 两位代码，例如 US / JP / GB；Rand 表示随机地区。
PROXY_1024_REGION = schema_default("PROXY_1024_REGION")
PROXY_1024_PROTOCOL = schema_default("PROXY_1024_PROTOCOL")
PROXY_1024_SESSION_MINUTES = schema_default("PROXY_1024_SESSION_MINUTES")
# 1024 白名单接口会在相同 region/time 参数的粘性窗口内复用同一远端会话。
# 开启后按任务 ID 在基础时长到 120 分钟之间轮换 time，确保新任务建立新会话/IP。
PROXY_1024_ROTATE_SESSION_TIME = schema_default("PROXY_1024_ROTATE_SESSION_TIME")
PROXY_1024_API_TIMEOUT = schema_default("PROXY_1024_API_TIMEOUT")
PROXY_1024_MAX_ATTEMPTS = schema_default("PROXY_1024_MAX_ATTEMPTS")
# 整段代理获取硬上限；重复粘性端点会额外快速重取，但不能无限占用任务线程。
PROXY_1024_ACQUIRE_TIMEOUT = schema_default("PROXY_1024_ACQUIRE_TIMEOUT")
PROXY_1024_VALIDATE = schema_default("PROXY_1024_VALIDATE")
# 同一代理出口检测遇到超时/连接/SSL 瞬时错误时，先原地重试次数。
PROXY_1024_VALIDATE_ATTEMPTS = schema_default("PROXY_1024_VALIDATE_ATTEMPTS")
PROXY_1024_RECENT_TTL = schema_default("PROXY_1024_RECENT_TTL")
PROXY_1024_ACQUIRE_INTERVAL = schema_default("PROXY_1024_ACQUIRE_INTERVAL")
# 跨进程代理端点租约。关闭后仅保留当前进程内的去重，默认保持开启。
PROXY_1024_PERSIST_LEASES = True

# 注册浏览器遇到明确的代理瞬时错误时，释放当前租约并换一条线路重试。
# 这里只控制额外重试次数，不改变注册线程池并发数。
REGISTRATION_PROXY_RETRIES = schema_default("REGISTRATION_PROXY_RETRIES")
REGISTRATION_PROXY_RETRY_DELAY = schema_default("REGISTRATION_PROXY_RETRY_DELAY")
# 查活/刷新 AT 在申请线路阶段遇到代理平台租约碰撞时，最多额外换线重试。
ACCOUNT_ACTION_PROXY_RETRIES = schema_default("ACCOUNT_ACTION_PROXY_RETRIES")
ACCOUNT_ACTION_PROXY_RETRY_DELAY = schema_default("ACCOUNT_ACTION_PROXY_RETRY_DELAY")

# 旧版/CLI 直接调用 check_account_plan() 时使用的兼容网络策略。
# WebUI 账号功能统一由下方 ACCOUNT_ACTION_PROXY_MODE 管理。
#   auto   = 优先使用 PLAN_CHECK_PROXY 或代理池；本地代理端口未监听时回退直连
#   proxy  = 强制使用 PLAN_CHECK_PROXY 或代理池，失败直接报错
#   direct = 始终直连
PLAN_CHECK_PROXY_MODE = schema_default("PLAN_CHECK_PROXY_MODE")

# 旧版套餐查询专用代理。留空时 auto/proxy 模式从 PROXY_POOL 选择。
# 代理可能包含账号密码，因此 WebUI 会把它保存到 .env。
PLAN_CHECK_PROXY = schema_default("PLAN_CHECK_PROXY")

# 注册完成后的 OpenAI 账号功能（查套餐、查活、Codex OAuth）代理来源：
#   registration = 跟随 REGISTRATION_PROXY_MODE（推荐；1024 平台会按账号申请新租约）
#   1024         = 始终从 1024Proxy 为每个账号/功能申请独立短期租约
#   pool         = 使用 ACCOUNT_ACTION_PROXY，留空时从 PROXY_POOL 抽取
#   direct       = 直连
# 第三方邮箱、短信、CPA/Sub2、提链服务和本地控制接口不使用这里的代理，避免浪费流量。
ACCOUNT_ACTION_PROXY_MODE = schema_default("ACCOUNT_ACTION_PROXY_MODE")
ACCOUNT_ACTION_PROXY = schema_default("ACCOUNT_ACTION_PROXY")

# 兼容旧版 token_refresh 的 Roxy 登录兜底开关。它不影响普通 live_check；
# 普通查活是否允许使用 Roxy 由 config.account 的独立开关控制。
LIVE_CHECK_ROXY_FALLBACK_ENABLED = schema_default("LIVE_CHECK_ROXY_FALLBACK_ENABLED")

# 查套餐使用独立的短超时和有限重试，避免后台任务长时间卡住。
PLAN_CHECK_TIMEOUT = schema_default("PLAN_CHECK_TIMEOUT")
PLAN_CHECK_MAX_ATTEMPTS = schema_default("PLAN_CHECK_MAX_ATTEMPTS")
PLAN_CHECK_RETRY_DELAY = schema_default("PLAN_CHECK_RETRY_DELAY")

# 新注册账号的权益可能存在短暂同步延迟。首次查询失败，或返回 free 且暂未发现
# Plus 试用资格时，等待该秒数后再复查一次；设为 0 可关闭复查。
PLAN_CHECK_REGISTRATION_RECHECK_DELAY = schema_default("PLAN_CHECK_REGISTRATION_RECHECK_DELAY")

# 注册链路中没有复用注册代理时，异步套餐查询使用独立后台队列；账号页
# 的套餐操作使用 config.codex.ACCOUNT_BATCH_WORKERS，不读取这里的线程数。
PLAN_CHECK_WORKERS = schema_default("PLAN_CHECK_WORKERS")
PLAN_CHECK_QUEUE_LIMIT = schema_default("PLAN_CHECK_QUEUE_LIMIT")
PLAN_CHECK_MIN_INTERVAL = schema_default("PLAN_CHECK_MIN_INTERVAL")
PLAN_CHECK_JITTER = schema_default("PLAN_CHECK_JITTER")


def pick_proxy() -> str:
    """从代理池中随机抽取一个代理 URL；池为空时返回空串（即不使用代理）。"""
    return random.choice(PROXY_POOL) if PROXY_POOL else ""


# 兼容入口：默认每次进程启动随机选一个，作为本次注册全程的固定代理
PROXY = pick_proxy()

# ---- .env overrides for WebUI editable fields ----
apply_env_overrides(globals())
PROXY = pick_proxy()
