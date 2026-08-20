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
import random


# 本地代理入口；实际出口地区以代理/分流规则为准。
# 推荐使用 socks5h://（DNS 在代理端解析），避免本地 DNS 与出口 IP 地区错配。
PROXY_POOL = [
    "socks5://127.0.0.1:7897",
]

# 注册任务代理来源：
#   pool = 使用上面的静态代理池（兼容原行为）
#   1024 = 每个注册任务从 1024Proxy API 提取一个独立的粘性住宅代理
#   none = 注册任务显式直连
REGISTRATION_PROXY_MODE = "pool"

# 1024Proxy 白名单 API。完整 URL 仅保存到 .env，源码默认留空。
# 客户端会保留 URL 中的筛选参数；单任务强制 num=1，注册批次按并发量批量设置 num，均使用下面配置的粘性时长。
PROXY_1024_API_URL = ""
# 国家/地区代码；留空时沿用 API URL 中原有的 region 参数。
# 1024Proxy 使用 ISO 3166-1 两位代码，例如 US / JP / GB；Rand 表示随机地区。
PROXY_1024_REGION = ""
PROXY_1024_PROTOCOL = "http"
PROXY_1024_SESSION_MINUTES = 30
# 1024 白名单接口会在相同 region/time 参数的粘性窗口内复用同一远端会话。
# 开启后按任务 ID 在基础时长到 120 分钟之间轮换 time，确保新任务建立新会话/IP。
PROXY_1024_ROTATE_SESSION_TIME = True
PROXY_1024_API_TIMEOUT = 12.0
PROXY_1024_MAX_ATTEMPTS = 5
# 整段代理获取硬上限；重复粘性端点会额外快速重取，但不能无限占用任务线程。
PROXY_1024_ACQUIRE_TIMEOUT = 60.0
PROXY_1024_VALIDATE = True
# 同一代理出口检测遇到超时/连接/SSL 瞬时错误时，先原地重试次数。
PROXY_1024_VALIDATE_ATTEMPTS = 2
PROXY_1024_RECENT_TTL = 1800
PROXY_1024_ACQUIRE_INTERVAL = 0.6
# 跨进程代理端点租约。关闭后仅保留当前进程内的去重，默认保持开启。
PROXY_1024_PERSIST_LEASES = True

# 旧版/CLI 直接调用 check_account_plan() 时使用的兼容网络策略。
# WebUI 账号功能统一由下方 ACCOUNT_ACTION_PROXY_MODE 管理。
#   auto   = 优先使用 PLAN_CHECK_PROXY 或代理池；本地代理端口未监听时回退直连
#   proxy  = 强制使用 PLAN_CHECK_PROXY 或代理池，失败直接报错
#   direct = 始终直连
PLAN_CHECK_PROXY_MODE = "auto"

# 旧版套餐查询专用代理。留空时 auto/proxy 模式从 PROXY_POOL 选择。
# 代理可能包含账号密码，因此 WebUI 会把它保存到 .env。
PLAN_CHECK_PROXY = ""

# 注册完成后的 OpenAI 账号功能（查套餐、查活、Codex OAuth）代理来源：
#   registration = 跟随 REGISTRATION_PROXY_MODE（推荐；1024 平台会按账号申请新租约）
#   1024         = 始终从 1024Proxy 为每个账号/功能申请独立短期租约
#   pool         = 使用 ACCOUNT_ACTION_PROXY，留空时从 PROXY_POOL 抽取
#   direct       = 直连
# 第三方邮箱、短信、CPA/Sub2、提链服务和本地控制接口不使用这里的代理，避免浪费流量。
ACCOUNT_ACTION_PROXY_MODE = "registration"
ACCOUNT_ACTION_PROXY = ""

# 查套餐使用独立的短超时和有限重试，避免后台任务长时间卡住。
PLAN_CHECK_TIMEOUT = 15.0
PLAN_CHECK_MAX_ATTEMPTS = 2
PLAN_CHECK_RETRY_DELAY = 1.5

# 新注册账号的权益可能存在短暂同步延迟。首次查询失败，或返回 free 且暂未发现
# Plus 试用资格时，等待该秒数后再复查一次；设为 0 可关闭复查。
PLAN_CHECK_REGISTRATION_RECHECK_DELAY = 2.0

# 自动、手动和批量套餐查询共用同一个后台队列，并复用这里的网络模式、
# 请求启动间隔与随机抖动，避免批量后台请求过于集中。
PLAN_CHECK_WORKERS = 3
PLAN_CHECK_QUEUE_LIMIT = 500
PLAN_CHECK_MIN_INTERVAL = 0.4
PLAN_CHECK_JITTER = 0.3


def pick_proxy() -> str:
    """从代理池中随机抽取一个代理 URL；池为空时返回空串（即不使用代理）。"""
    return random.choice(PROXY_POOL) if PROXY_POOL else ""


# 兼容入口：默认每次进程启动随机选一个，作为本次注册全程的固定代理
PROXY = pick_proxy()

# ---- .env overrides for WebUI editable fields ----
apply_env_overrides(globals(), {
    'PROXY_POOL': 'list_str_multiline',
    'REGISTRATION_PROXY_MODE': 'str',
    'PROXY_1024_API_URL': 'str',
    'PROXY_1024_REGION': 'str',
    'PROXY_1024_PROTOCOL': 'str',
    'PROXY_1024_SESSION_MINUTES': 'int',
    'PROXY_1024_ROTATE_SESSION_TIME': 'bool',
    'PROXY_1024_API_TIMEOUT': 'float',
    'PROXY_1024_MAX_ATTEMPTS': 'int',
    'PROXY_1024_ACQUIRE_TIMEOUT': 'float',
    'PROXY_1024_VALIDATE': 'bool',
    'PROXY_1024_VALIDATE_ATTEMPTS': 'int',
    'PROXY_1024_RECENT_TTL': 'int',
    'PROXY_1024_ACQUIRE_INTERVAL': 'float',
    'PROXY_1024_PERSIST_LEASES': 'bool',
    'PLAN_CHECK_PROXY_MODE': 'str',
    'PLAN_CHECK_PROXY': 'str',
    'ACCOUNT_ACTION_PROXY_MODE': 'str',
    'ACCOUNT_ACTION_PROXY': 'str',
    'PLAN_CHECK_TIMEOUT': 'float',
    'PLAN_CHECK_MAX_ATTEMPTS': 'int',
    'PLAN_CHECK_RETRY_DELAY': 'float',
    'PLAN_CHECK_REGISTRATION_RECHECK_DELAY': 'float',
    'PLAN_CHECK_WORKERS': 'int',
    'PLAN_CHECK_QUEUE_LIMIT': 'int',
    'PLAN_CHECK_MIN_INTERVAL': 'float',
    'PLAN_CHECK_JITTER': 'float',
})
PROXY = pick_proxy()
