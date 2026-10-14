# -*- coding: utf-8 -*-
"""
代理池配置

独立库存负责后台检查和补货；业务任务领取独立租约，按用途决定是否允许共享。

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
# 独立代理池生命周期策略：任务只领取已检测库存，不在任务线程内提取或校验。
# MIN_READY 是每个活跃配置的空闲底数，领取后后台补足；占用与检查中不计入。
PROXY_POOL_MIN_READY = schema_default("PROXY_POOL_MIN_READY")
PROXY_POOL_MAX_SIZE = schema_default("PROXY_POOL_MAX_SIZE")
# 0 表示代理不足时持续等待；正数限制领取总等待时间，后台补货预算独立。
PROXY_POOL_WAIT_TIMEOUT = schema_default("PROXY_POOL_WAIT_TIMEOUT")
PROXY_POOL_MIN_TTL = schema_default("PROXY_POOL_MIN_TTL")
PROXY_POOL_CHECK_INTERVAL = schema_default("PROXY_POOL_CHECK_INTERVAL")
PROXY_POOL_MAX_IDLE = schema_default("PROXY_POOL_MAX_IDLE")
PROXY_POOL_WORKERS = schema_default("PROXY_POOL_WORKERS")

# 注册任务代理来源：
#   pool = 使用独立代理池中的已检测库存
#   1024 = 兼容旧配置；由代理池按固定供给参数维护库存，再向任务发放租约
#   none = 注册任务显式直连
REGISTRATION_PROXY_MODE = schema_default("REGISTRATION_PROXY_MODE")

# 1024Proxy 白名单 API。完整 URL 仅保存到 .env，源码默认留空。
# 代理池预热/补货使用 URL 与下方固定的 region、time、num 参数；任务只领取库存，不在业务线程内提取。
# time 是供应商的粘性窗口参数，不承诺每次领取都是新会话或新 IP。
PROXY_1024_API_URL = schema_default("PROXY_1024_API_URL")
# 国家/地区代码；留空时沿用 API URL 中原有的 region 参数。
# 1024Proxy 使用 ISO 3166-1 两位代码，例如 US / JP / GB；Rand 表示随机地区。
PROXY_1024_REGION = schema_default("PROXY_1024_REGION")
PROXY_1024_PROTOCOL = schema_default("PROXY_1024_PROTOCOL")
PROXY_1024_SESSION_MINUTES = schema_default("PROXY_1024_SESSION_MINUTES")
# 兼容旧配置项；独立代理池使用固定供给参数，不能通过改变 time 推断新会话或新 IP。
# 是否复用线路由代理池租约生命周期与供应商实际行为决定。
PROXY_1024_ROTATE_SESSION_TIME = schema_default("PROXY_1024_ROTATE_SESSION_TIME")
PROXY_1024_API_TIMEOUT = schema_default("PROXY_1024_API_TIMEOUT")
PROXY_1024_MAX_ATTEMPTS = schema_default("PROXY_1024_MAX_ATTEMPTS")
# 后台补货轮次预算；锁等待、节流、请求和出口检测共用。
PROXY_1024_ACQUIRE_TIMEOUT = schema_default("PROXY_1024_ACQUIRE_TIMEOUT")
PROXY_1024_VALIDATE = schema_default("PROXY_1024_VALIDATE")
# 同一代理出口检测遇到超时/连接/SSL 瞬时错误时，先原地重试次数。
PROXY_1024_VALIDATE_ATTEMPTS = schema_default("PROXY_1024_VALIDATE_ATTEMPTS")
PROXY_1024_RECENT_TTL = schema_default("PROXY_1024_RECENT_TTL")
PROXY_1024_ACQUIRE_INTERVAL = schema_default("PROXY_1024_ACQUIRE_INTERVAL")
# 旧提取器兼容项；独立代理池始终通过 PostgreSQL 协调库存和租约。
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

# 代理池来源的查套餐允许共享已检测库存；注册与认证任务保持独占租约。
PLAN_CHECK_PROXY_ALLOW_REUSE = schema_default("PLAN_CHECK_PROXY_ALLOW_REUSE")
# 开启复用时，同一实际出口 IP 在租约有效期内允许建立的套餐查询租约数；包含首次租用。
PLAN_CHECK_PROXY_REUSE_LIMIT = schema_default("PLAN_CHECK_PROXY_REUSE_LIMIT")

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

# 旧套餐队列配置仅为历史 .env 和模块调用方保留，不参与当前任务调度。
# 独立套餐任务使用 ACCOUNT_BATCH_WORKERS；复用注册会话的查询随注册任务同步执行。
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
