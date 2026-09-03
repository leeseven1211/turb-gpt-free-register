# -*- coding: utf-8 -*-
"""
配置读写层（供 WebUI /api/config 使用）。

设计原则：
    1. 白名单：只暴露"运行时安全"的开关/数值/默认值，协议级常量
       （client_id / scope / sentinel 版本等）一律不开放，避免一改就废号。
    2. 所有 WebUI 可编辑项统一写入项目根 `.env`，不再修改 `config/*.py`。
    3. `config/*.py` 只保留默认值；运行时通过 config.env_loader 用 `.env` 覆盖。
    4. 读取时优先 `.env`，缺失时回退解析 `config/*.py` 默认值。
"""
import ast
import os
import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"
EXPLICIT_EMPTY_LIST_KEYS = {"PROXY_POOL"}


# ============================================================
# 白名单：每个可编辑项声明它在哪个文件、键名、类型、分组、说明
# type 决定前端控件 + 写回时的字面量格式：
#   bool   -> True/False
#   int    -> 整数
#   str    -> 带引号字符串
#   list_str_multiline -> 多行字符串列表（PROXY_POOL 专用，整块替换）
# ============================================================

EDITABLE_FIELDS = [
    # ---- 通用配置 ----
    {
        "key": "ACCOUNT_BATCH_WORKERS", "file": "codex.py", "type": "int", "group": "通用配置",
        "label": "账号批量操作并发数", "help": "账号页查活、查套餐和 Codex 批量补跑等操作使用的默认并发数，范围 1-16；建议先保持 3",
    },
    # ---- 定时任务 ----
    {
        "key": "EMAIL_BUTLER_RISK_SCAN_ENABLED", "file": "email.py", "type": "bool", "group": "定时任务",
        "label": "自动查封号邮件", "help": "周期扫描支持的邮箱来源，识别 OpenAI 封号通知；关闭后仍可在账号页手动触发",
    },
    {
        "key": "EMAIL_BUTLER_RISK_SCAN_INTERVAL_SECONDS", "file": "email.py", "type": "int", "group": "定时任务",
        "label": "查封号邮件间隔（秒）", "help": "两轮扫描之间的最短间隔，范围 900-604800；默认 21600（6 小时）",
    },
    {
        "key": "AT_AUTO_REFRESH_ENABLED", "file": "codex.py", "type": "bool", "group": "定时任务",
        "label": "自动刷新账号 AT", "help": "临近过期时自动刷新 ChatGPT accessToken；关闭后仍可在账号页手动刷新",
    },
    {
        "key": "AT_REFRESH_SCAN_INTERVAL_SECONDS", "file": "codex.py", "type": "int", "group": "定时任务",
        "label": "刷新账号 AT 间隔（秒）", "help": "两轮扫描之间的最短间隔，范围 300-86400；默认 3600（1 小时）",
    },
    {
        "key": "CODEX_TOKEN_AUTO_REFRESH_ENABLED", "file": "codex.py", "type": "bool", "group": "定时任务",
        "label": "自动刷新 Codex Token", "help": "用 refresh token 续期 Codex 凭证，无需重跑 OAuth 与接码；关闭后仍可手动刷新",
    },
    {
        "key": "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS", "file": "codex.py", "type": "int", "group": "定时任务",
        "label": "刷新 Codex Token 间隔（秒）", "help": "两轮扫描之间的最短间隔，范围 300-86400；默认 86400（1 天）",
    },

    # ---- WebUI 授权 ----
    {
        "key": "WEBUI_AUTH_CODE", "file": "codex.py", "type": "str", "group": "WebUI 授权",
        "label": "WebUI 授权码", "help": "仅保存在 .env（WEBUI_AUTH_CODE），避免出现在进程命令行中；保存后重启 WebUI 生效",
        "storage": "env", "secret": True,
    },
    {
        "key": "WEBUI_SESSION_SECRET", "file": "codex.py", "type": "str", "group": "WebUI 授权",
        "label": "Session 签名密钥", "help": "可选，保存在 .env（WEBUI_SESSION_SECRET）；不填则从固定授权码派生，修改授权码会使已有登录失效",
        "storage": "env", "secret": True,
    },
    # ---- 注册主链路 ----
    {
        "key": "ENABLE_CODEX_AUTO", "file": "codex.py", "type": "bool", "group": "注册主链路",
        "label": "启用 Codex OAuth", "help": "注册成功后自动跑 Codex 授权（全新session+接码），落盘 codex-邮箱.json",
    },
    {
        "key": "REGISTRATION_DRIVER", "file": "roxybrowser.py", "type": "str", "group": "注册主链路",
        "label": "注册主流程驱动", "help": "选择注册所用的自动化方式：roxy=浏览器主流程，protocol=协议辅助/回退；默认推荐 roxy",
    },
    {
        "key": "REGISTRATION_AUTH_MODE", "file": "register.py", "type": "str", "group": "注册主链路",
        "label": "注册认证方式", "help": "otp=只用邮箱一次性验证码；password=设置并保存账号密码。选择 password 才会执行密码注册，但仍可能需要邮箱验证码",
    },
    {
        "key": "REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS", "file": "register.py", "type": "int", "group": "注册主链路",
        "label": "密码提交跳转等待(秒)", "help": "从点击创建密码页的继续按钮后独立计时；默认 60 秒，避免慢代理下页面迟到进入邮箱验证码页却被提前判失败",
    },
    {
        "key": "REGISTRATION_PLAN_CHECK_ENABLED", "file": "register.py", "type": "bool", "group": "注册主链路",
        "label": "注册后自动查套餐", "help": "注册核心保存后独立查询套餐；关闭后不影响账号落库，之后可在账号管理中手动查询或补全",
    },
    # ---- 账号补全策略 ----
    {
        "key": "ACCOUNT_COMPLETION_PASSWORD_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "补全账号密码", "help": "“补全账号”发现账号缺少登录密码时补充；关闭后不会处理密码",
    },
    {
        "key": "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "补全套餐状态", "help": "“补全账号”发现套餐未成功确认时补查；关闭后不会处理套餐",
    },
    {
        "key": "ACCOUNT_COMPLETION_2FA_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "补全 Authenticator 2FA", "help": "“补全账号”发现账号缺少 Authenticator 2FA 时启用；关闭后不会处理 2FA",
    },
    {
        "key": "ACCOUNT_COMPLETION_CODEX_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "补全 Codex", "help": "“补全账号”发现 Codex 未完成时提交 Codex OAuth；关闭后不会处理 Codex",
    },
    {
        "key": "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "补全时允许刷新 AT", "help": "默认关闭。开启后仅对已完成注册但缺少/无法使用 AT 的账号允许刷新；注册尚未完成的账号会优先继续原注册任务，不会刷新 AT",
    },
    {
        "key": "ACCOUNT_PASSWORD_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "密码补全驱动", "help": "当前唯一实现为 RoxyBrowser，暂不可切换",
    },
    {
        "key": "ACCOUNT_PLAN_CHECK_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "套餐补全驱动", "help": "当前唯一实现为纯协议，暂不可切换",
    },
    {
        "key": "ACCOUNT_LIVE_CHECK_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "普通查活驱动", "help": "可选 protocol_current 或 browser_roxy；browser_roxy 只验证已有 AT，不登录、不发 OTP、不刷新 AT；全局协议版本设置不影响普通查活",
    },
    {
        "key": "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "开放 Roxy 普通查活", "help": "灰度开关，默认关闭；开启后才允许将普通查活驱动设为 browser_roxy，且仍只验证已有 AT",
    },
    {
        "key": "ACCOUNT_TOKEN_REFRESH_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "刷新 AT 驱动", "help": "legacy 保持现有协议邮箱 OTP→Roxy 兜底；protocol_v2 才尝试保存的账号密码/TOTP，需同时开启 Protocol v2 总开关",
    },
    {
        "key": "ACCOUNT_AUTH_V2_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "开启 Protocol v2", "help": "紧急总开关；关闭时即使刷新 AT 选择 protocol_v2，也会临时回到旧实现，不修改已保存的选择",
    },
    {
        "key": "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "密码错误后邮箱兜底", "help": "默认关闭；开启后仅在新认证会话由远端明确进入邮箱验证码 challenge 时继续，不从密码页盲发 OTP；结果仍保留 password_rejected，不重试密码",
    },
    {
        "key": "ACCOUNT_AUTH_PROFILE_MODE", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "Protocol 设备画像", "help": "current 保持现状、每次会话随机设备画像；account_stable 仅在实际使用 v2 协议刷新时按账号懒创建稳定画像，不影响注册 device_id、普通查活和 v1 刷新链路",
    },
    {
        "key": "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "保存认证原始上下文", "help": "默认关闭；开启后仅为 v2 协议实际认证 run 按白名单保存设备 ID、session 标识和代理上下文到受限私有表，不进入普通 API/导出；不会复用过期代理",
    },
    {
        "key": "ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS", "file": "account.py", "type": "int", "group": "账号补全",
        "label": "认证上下文保留天数", "help": "原始认证上下文的自动清理周期，默认 30 天；设置为 0 表示不自动清理，仍可手工逐行清理",
    },
    {
        "key": "LIVE_CHECK_ROXY_FALLBACK_ENABLED", "file": "proxy.py", "type": "bool", "group": "账号补全",
        "label": "刷新 Roxy 兜底", "help": "仅控制 v1 协议刷新 AT 失败后的既有 Roxy 登录兜底；不影响普通查活，也不允许普通查活登录或发送 OTP",
    },
    {
        "key": "ACCOUNT_2FA_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "2FA 补全驱动", "help": "protocol=浏览器前置后协议开通；protocol_direct=已有 AT 先直接协议开通，失败再按兜底开关切浏览器；browser=直接浏览器",
    },
    {
        "key": "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "2FA 协议失败后浏览器兜底", "help": "仅用于账号补全；protocol_direct/protocol 失败后是否允许打开 Roxy 安全设置页面，默认开启",
    },
    {
        "key": "ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED", "file": "account.py", "type": "bool", "group": "账号补全",
        "label": "2FA 401 后协议重认证", "help": "仅用于 protocol_direct；旧 AT 被 MFA 接口要求近期认证时，先走协议邮箱 OTP 换新 AT，再继续开通；默认开启",
    },
    {
        "key": "ACCOUNT_CODEX_DRIVER", "file": "account.py", "type": "str", "group": "账号补全",
        "label": "Codex 补全驱动", "help": "可选纯协议、RoxyBrowser 或跟随注册主流程；三种路由都由 Codex OAuth 执行器处理",
    },
    # ---- 注册调试 ----
    {
        "key": "REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "失败现场保留（秒）", "help": "调试任务最终失败后保留浏览器和代理的最长时间；默认 1800（30 分钟）",
    },
    {
        "key": "REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED", "file": "registration_debug.py", "type": "bool", "group": "注册调试",
        "label": "普通模式失败诊断", "help": "普通注册失败时保存脱敏页面现场、失败请求元数据和浏览器错误；不会抓取成功请求或暂停浏览器",
    },
    {
        "key": "REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "失败资源记录上限", "help": "普通模式失败现场最多保存的资源时序条数；默认 80",
    },
    {
        "key": "REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "失败页面文本上限（KB）", "help": "普通模式失败现场最多保存的页面可见文本大小；默认 32",
    },
    {
        "key": "REGISTRATION_DEBUG_MAX_HELD_SESSIONS", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "最大保留现场数", "help": "允许同时暂停保留的失败浏览器数量；超出后仍保存抓包但自动关闭现场",
    },
    {
        "key": "REGISTRATION_DEBUG_BODY_MAX_KB", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "单正文上限（KB）", "help": "单个文本、HTML 或 JSON 请求/响应正文的最大保存大小",
    },
    {
        "key": "REGISTRATION_DEBUG_BODY_BUDGET_MB", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "单任务正文预算（MB）", "help": "达到预算后继续记录全部请求元数据，但不再保存正文",
    },
    {
        "key": "REGISTRATION_DEBUG_GLOBAL_BUDGET_MB", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "抓包总预算（MB）", "help": "调试目录超过软上限后，新任务自动降级为只记录请求元数据",
    },
    {
        "key": "REGISTRATION_DEBUG_RETENTION_DAYS", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "抓包保留天数", "help": "WebUI 启动时逐文件清理超过此天数的调试产物",
    },
    {
        "key": "REGISTRATION_DEBUG_QUEUE_SIZE", "file": "registration_debug.py", "type": "int", "group": "注册调试",
        "label": "单任务事件队列", "help": "默认 20000；队列满时丢弃后续抓包事件并计数，不阻塞注册线程",
    },

    {
        "key": "ROXY_API_BASE", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "Roxy API 地址", "help": "默认 http://127.0.0.1:50000；需在 Roxy 应用 API 配置中开启",
    },
    {
        "key": "ROXY_API_TOKEN", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "Roxy API Key", "help": "保存在 .env（ROXY_API_TOKEN），不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "ROXY_PROFILE_ID", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "Roxy 环境ID", "help": "指定要打开的 Roxy 浏览器环境/Profile ID；留空则尝试创建临时环境",
    },
    {
        "key": "ROXY_WORKSPACE_ID", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "Roxy 工作区ID", "help": "创建一号一环境时必填，会作为 workspaceId 提交给 Roxy 创建 Profile 接口",
    },
    {
        "key": "ROXY_PROJECT_ID", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "Roxy 项目ID", "help": "从 /browser/workspace 的 project_details.projectId 获取；创建 Profile 时会作为 projectId 提交",
    },
    {
        "key": "ROXY_WORKSPACE_LIST_PATH", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "获取团队接口", "help": "默认 /browser/workspace；点击获取团队/项目时会先试此路径，再自动尝试常见兼容路径",
    },
    {
        "key": "ROXY_OPEN_PATH", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "打开接口路径", "help": "默认 /browser/open；如 Roxy 版本不同可在此调整",
    },
    {
        "key": "ROXY_OPEN_HEADLESS", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "无头启动窗口", "help": "打开 Roxy 环境时向 /browser/open 传 headless；False=显示窗口，True=无头启动",
    },
    {
        "key": "ROXY_CLOSE_PATH", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "关闭接口路径", "help": "默认 /browser/close",
    },
    {
        "key": "ROXY_KEEP_BROWSER_OPEN", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "保留浏览器", "help": "调试时可开启，任务结束后不自动关闭 Roxy 环境",
    },
    {
        "key": "ROXY_WINDOW_WAIT_TIMEOUT", "file": "roxybrowser.py", "type": "int", "group": "RoxyBrowser",
        "label": "窗口满等待上限(秒)", "help": "Roxy 返回窗口额度不足时保持当前任务等待的最长时间；默认 900 秒，避免快速失败并启动全部排队任务",
    },
    {
        "key": "ROXY_WINDOW_WAIT_INTERVAL", "file": "roxybrowser.py", "type": "int", "group": "RoxyBrowser",
        "label": "窗口满重试间隔(秒)", "help": "等待 Roxy 空闲窗口时重新尝试创建环境的间隔；默认 10 秒",
    },
    {
        "key": "ROXY_ONE_PROFILE_PER_ACCOUNT", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "一号一环境", "help": "每个账号强制创建新 Roxy Profile，用完关闭并删除，禁止复用固定环境",
    },
    {
        "key": "ROXY_DELETE_PROFILE_AFTER_RUN", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "结束后删除环境", "help": "一号一环境模式下，任务结束后删除本轮创建的 Roxy Profile",
    },
    {
        "key": "ROXY_RANDOM_OS_ON_CREATE", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "创建环境随机OS", "help": "创建 Roxy 环境时每次在 Windows / macOS 中随机，不固定 macOS",
    },
    {
        "key": "ROXY_RANDOM_OS_CHOICES", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "随机OS范围", "help": "逗号分隔，默认 Windows,macOS；Roxy 支持 Windows / macOS / Linux / IOS / Android",
    },
    {
        "key": "ROXY_RANDOM_PROFILE_NAME_ON_CREATE", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "创建环境随机名称", "help": "创建 Roxy 环境时自动生成不同名称，避免固定 gpt-free-register",
    },
    {
        "key": "ROXY_PROFILE_NAME_PREFIX", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "随机名称前缀", "help": "默认 rb；实际名称格式类似 rb-时间戳-随机码",
    },
    {
        "key": "ROXY_CREATE_USE_PROXY_POOL", "file": "roxybrowser.py", "type": "bool", "group": "RoxyBrowser",
        "label": "创建环境使用代理池", "help": "仅用于静态「代理池」模式；选择 1024Proxy 时会自动把每个任务的独立家宽租约写入 Roxy proxyInfo，且优先于此开关",
    },
    {
        "key": "ROXY_PROXY_CHECK_CHANNEL", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "代理检测通道", "help": "写入 Roxy proxyInfo.checkChannel；留空则不传，默认 IPRust.io",
    },
    {
        "key": "ROXY_DELETE_PATH", "file": "roxybrowser.py", "type": "str", "group": "RoxyBrowser",
        "label": "删除接口路径", "help": "默认 /browser/delete；如 Roxy 版本不同可调整",
    },
    {
        "key": "CODEX_OAUTH_DRIVER", "file": "codex.py", "type": "str", "group": "注册主链路",
        "label": "Codex 授权驱动", "help": "选择 Codex OAuth 所用的自动化方式：protocol=纯协议，roxy=浏览器，same_as_registration=跟随注册主流程驱动",
    },
    {
        "key": "CODEX_TOKEN_AUTO_REFRESH_ENABLED", "file": "codex.py", "type": "bool", "group": "Codex",
        "label": "自动刷新 OAuth Token", "help": "进入到期窗口后使用 refresh_token 换新 access token；不重新登录，不收邮箱或短信验证码",
    },
    {
        "key": "CODEX_TOKEN_REFRESH_BEFORE_HOURS", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "提前刷新(小时)", "help": "Codex access token 距离过期多少小时开始自动刷新，默认 24",
    },
    {
        "key": "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "刷新巡检间隔(秒)", "help": "后台检查 Codex OAuth 到期状态的间隔，默认 86400 秒（每天一次），最小按 300 秒执行",
    },
    {
        "key": "CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "启动后首次巡检(秒)", "help": "WebUI 启动后等待多久执行第一次 Codex OAuth 到期巡检",
    },
    {
        "key": "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "单轮最多刷新", "help": "每轮自动巡检最多加入队列的 Codex 凭证数量",
    },
    {
        "key": "CODEX_TOKEN_AUTO_SYNC_SUB2API", "file": "codex.py", "type": "bool", "group": "Codex",
        "label": "刷新后同步 sub2api", "help": "仅对曾由当前页面成功上传过 sub2api 的凭证自动更新，避免 refresh_token 轮换后 sub2api 仍使用旧值",
    },
    {
        "key": "ROXY_CODEX_CALLBACK_TIMEOUT", "file": "roxybrowser.py", "type": "int", "group": "RoxyBrowser",
        "label": "Codex回调超时", "help": "Roxy Codex OAuth 等待 localhost:1455 callback 的最长秒数",
    },
    {
        "key": "ENABLE_2FA", "file": "twofa.py", "type": "bool", "group": "注册主链路",
        "label": "启用 2FA(TOTP)", "help": "注册完成后自动设置动态口令（会多收一封 OTP 邮件）",
    },
    {
        "key": "TWOFA_DRIVER", "file": "twofa.py", "type": "str", "group": "注册主链路",
        "label": "2FA 开通方式", "help": "protocol=优先用新鲜 AT，Roxy 中失败会自动回退浏览器 UI；browser=直接用 RoxyBrowser 安全设置页面",
    },
    {
        "key": "ENABLE_FLOW_TRIGGER", "file": "flow_trigger.py", "type": "bool", "group": "注册主链路",
        "label": "启用 Flow 触发", "help": "注册成功后自动调用内部 Flow 接口（不影响注册结果）",
    },
    {
        "key": "ENABLE_HUMANIZE_DELAY", "file": "humanize.py", "type": "bool", "group": "人工节奏",
        "label": "启用随机停顿", "help": "在注册、OTP、授权等步骤之间加入随机等待，更接近人工操作节奏",
    },
    {
        "key": "HUMANIZE_DELAY_FACTOR", "file": "humanize.py", "type": "float", "group": "人工节奏",
        "label": "停顿倍率", "help": "随机停顿整体倍率；1.0=默认，0.5=减半，2.0=加倍",
    },
    {
        "key": "ENABLE_HUMANIZE_BROWSER_ACTIONS", "file": "humanize.py", "type": "bool", "group": "人工节奏",
        "label": "浏览器动作随机化", "help": "Roxy 点击、输入、页面观察使用随机鼠标落点和逐字输入，降低机械操作痕迹",
    },
    # ---- 邮箱 / OTP ----
    {
        "key": "USE_EMAIL_SERVICE", "file": "email.py", "type": "bool", "group": "邮箱 / OTP",
        "label": "自动取邮箱+收码", "help": "True=从邮箱池自动领邮箱并自动收 OTP；False=手动模式：用 REGISTER_EMAIL，OTP 在任务页手填",
    },
    {
        "key": "REGISTER_EMAIL", "file": "register.py", "type": "str", "group": "邮箱 / OTP",
        "label": "手动注册邮箱", "help": "USE_EMAIL_SERVICE=False 时必填。例如你的 outlook.com 地址；OTP 去网页邮箱看，再回任务页提交",
    },
    {
        "key": "REGISTER_NAME", "file": "register.py", "type": "str", "group": "邮箱 / OTP",
        "label": "显示名称", "help": "留空则自动生成英文名",
    },
    {
        "key": "OTP_MAX_WAIT", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "OTP 最长等待(秒)", "help": "单轮等待验证码邮件的最长秒数；Email Butler/iCloud 转发建议 240，避免过早重发制造多枚验证码",
    },
    {
        "key": "OTP_POLL_INTERVAL", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "OTP 轮询间隔(秒)", "help": "每隔多少秒查一次新邮件",
    },
    {
        "key": "EMAIL_SOURCE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "邮箱来源", "help": "WebUI 可选来源列表，可填单个或多个并用逗号分隔；开始注册时必须明确选择一个，任务不会跨平台兜底：outlook,generic_api,cloudflare_domain,cloudflare,email_butler,gptmail,mailnest,cloudmail,icloud_hide",
    },
    {
        "key": "EMAIL_BUTLER_API_BASE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Email Butler API 地址", "help": "通用 /v1 根地址，例如 http://127.0.0.1:8788/v1",
        "storage": "env",
    },
    {
        "key": "EMAIL_BUTLER_API_KEY", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Email Butler API Key", "help": "专用客户端 Key；策略在 Butler 端绑定，保存在 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "EMAIL_BUTLER_REQUEST_TIMEOUT", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "Email Butler 请求超时(秒)", "help": "单次 HTTP 请求超时，默认 20 秒",
    },
    {
        "key": "GPTMAIL_API_KEY", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "GPTMail API Key", "help": "选择 gptmail 邮箱来源时必填；保存在 .env，不会写入 config 源码",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDFLARE_API_BASE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare API 地址", "help": "Worker 临时邮箱 API 根地址，如 https://mail.example.com；选择 cloudflare 时必填",
        "storage": "env",
    },
    {
        "key": "CLOUDFLARE_API_KEY", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare API Key", "help": "匿名可空；admin 模式填 ADMIN_PASSWORD；保存在 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDFLARE_SIGNAL_API_KEY", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 封号信号 Key", "help": "仅用于查询封号邮件信号，不返回邮件正文；建议使用独立 Key",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDFLARE_SIGNAL_PATH", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 封号信号路径", "help": "默认 /signals/scan",
    },
    {
        "key": "CLOUDFLARE_AUTH_MODE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 鉴权模式", "help": "none / bearer / x-api-key / x-admin-auth / query-key",
    },
    {
        "key": "CLOUDFLARE_CUSTOM_AUTH", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 全局密码", "help": "Worker PASSWORDS，注入 x-custom-auth；保存在 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDFLARE_PATH_ACCOUNTS", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 创建路径", "help": "默认 /api/new_address；admin 常用 /admin/new_address",
    },
    {
        "key": "CLOUDFLARE_PATH_MESSAGES", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 邮件路径", "help": "默认 /api/mails",
    },
    {
        "key": "CLOUDFLARE_PATH_DOMAINS", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare 域名路径", "help": "默认 /api/domains（预留）",
    },
    {
        "key": "CLOUDFLARE_PATH_TOKEN", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Cloudflare Token路径", "help": "默认 /api/token（fallback 预留）",
    },
    {
        "key": "CLOUDFLARE_DEFAULT_DOMAINS", "file": "email.py", "type": "list_str_multiline", "group": "邮箱 / OTP",
        "label": "Cloudflare 默认域名", "help": "收信域名，每行一个或逗号分隔；创建时轮询使用，可留空",
    },
    {
        "key": "CLOUDFLARE_REQUEST_TIMEOUT", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "Cloudflare 请求超时(秒)", "help": "HTTP 请求超时，默认 20",
    },
    {
        "key": "CLOUDFLARE_NAME_LENGTH", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "Cloudflare 随机名前缀长度", "help": "admin 创建时 local-part 长度，默认 10",
    },
    {
        "key": "OUTLOOK_FETCH_MODE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Outlook取件模式", "help": "auto=远端优先，远端 402/DEPLOYMENT_DISABLED 自动切 Graph 直连；direct=只用 Microsoft Graph 直连；remote=只用远端服务",
    },
    {
        "key": "EMAIL_DOMAIN", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "转发域名(cloudflare_domain)", "help": "仅 cloudflare_domain 使用：Email Routing 的域名，如 mydomain.com；与 EMAIL_SOURCE=cloudflare 无关",
    },
    {
        "key": "QQ_EMAIL", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "QQ 邮箱地址", "help": "仅 cloudflare_domain：接收 Email Routing 转发的 QQ 邮箱，如 123456@qq.com",
    },
    {
        "key": "QQ_IMAP_PASSWORD", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "QQ 邮箱 IMAP 授权码", "help": "仅 cloudflare_domain：QQ IMAP 授权码，保存在 .env，不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "MAIL_NEST_API_KEY", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "MailNest API Key", "help": "选择 mailnest 邮箱来源时必填；保存在 .env，不会写入 config 源码",
        "storage": "env", "secret": True,
    },
    {
        "key": "MAIL_NEST_PROJECT_CODE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "MailNest 项目代码", "help": "项目代码 默认 chatgpt001 获取页面 mailnest.top/buy-email",
    },
    {
        "key": "CLOUDMAIL_API_BASE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "CloudMail API 地址", "help": "Cloud Mail Worker/API 地址，例如 https://mail.example.com",
    },
    {
        "key": "CLOUDMAIL_ADMIN_EMAIL", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "CloudMail管理员邮箱", "help": "用于生成 Token；域名被平台隐藏时也会用它登录读取域名",
        "storage": "env",
    },
    {
        "key": "CLOUDMAIL_PASSWORD", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "CloudMail 密码", "help": "用于自动获取 Token；保存在 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDMAIL_TOKEN_PATH", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "CloudMail Token路径", "help": "固定使用 /api/public/genToken；如部署版本不同可修改",
    },
    {
        "key": "CLOUDMAIL_AUTH_TOKEN", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "CloudMail Token", "help": "CloudMail/Cloud Mail API Authorization Token；保存在 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "CLOUDMAIL_DOMAINS", "file": "email.py", "type": "list_str_multiline", "group": "邮箱 / OTP",
        "label": "CloudMail 域名列表", "help": "可留空；运行时会自动从平台获取。也可点“获取 CloudMail 域名”缓存到这里",
    },
    {
        "key": "CLOUDMAIL_AUTO_ADD_USER", "file": "email.py", "type": "bool", "group": "邮箱 / OTP",
        "label": "CloudMail自动创建用户", "help": "生成随机邮箱后调用 /api/public/addUser 创建用户",
    },
    {
        "key": "CLOUDMAIL_RANDOM_LOCAL_LENGTH", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "CloudMail随机名前缀长度", "help": "生成邮箱 local-part 的长度，建议 10-16",
    },
    {
        "key": "ICLOUD_HME_API_BASE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "iCloud HME 服务地址", "help": "本机 icloud-hme sidecar 地址，默认 http://127.0.0.1:8081",
        "storage": "env",
    },
    {
        "key": "ICLOUD_HME_ACCOUNT_ID", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "iCloud 账号 ID", "help": "sidecar 中的账号 ID；留空自动选 active 账号",
        "storage": "env",
    },
    {
        "key": "ICLOUD_HME_API_TOKEN", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "iCloud HME API Token", "help": "本地服务启用鉴权时填写；仅监听 127.0.0.1 时可留空",
        "storage": "env", "secret": True,
    },
    {
        "key": "ICLOUD_HME_REQUEST_TIMEOUT", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "iCloud 请求超时(秒)", "help": "同步别名和 IMAP 拉信的单次请求超时，默认 35",
    },
    {
        "key": "ICLOUD_HME_SYNC_TTL", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "iCloud 同步缓存(秒)", "help": "别名池自动同步的缓存时长，默认 300；连接测试会强制同步",
    },
    {
        "key": "ICLOUD_HME_INBOX_MODE", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "隐藏邮箱收件模式", "help": "sidecar=iCloud IMAP；forward_imap=本机直接读取 Gmail；forward_butler=Oracle 接收 Gmail 并从 Email Butler PG 缓存取码",
    },
    {
        "key": "ICLOUD_HME_FORWARD_IMAP_SERVER", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "转发 IMAP 服务器", "help": "Gmail 填 imap.gmail.com",
    },
    {
        "key": "ICLOUD_HME_FORWARD_IMAP_PORT", "file": "email.py", "type": "int", "group": "邮箱 / OTP",
        "label": "转发 IMAP 端口", "help": "SSL IMAP 默认 993",
    },
    {
        "key": "ICLOUD_HME_FORWARD_IMAP_EMAIL", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "隐藏邮箱转发到", "help": "Apple HME 的 forwardToEmail；必须与实际 Gmail 地址完全一致",
        "storage": "env",
    },
    {
        "key": "ICLOUD_HME_FORWARD_IMAP_PASSWORD", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "Gmail IMAP 应用密码", "help": "forward_imap 模式用于本机直接读取 Gmail；请填写 Gmail 应用专用密码",
        "storage": "env", "secret": True,
    },
    {
        "key": "ICLOUD_HME_AUTO_CREATE", "file": "email.py", "type": "bool", "group": "邮箱 / OTP",
        "label": "库存为空自动创建", "help": "关闭时仅使用已同步别名；开启后池为空会向 Apple 申请一个新隐藏邮箱",
    },
    {
        "key": "ICLOUD_HME_CREATE_LABEL_PREFIX", "file": "email.py", "type": "str", "group": "邮箱 / OTP",
        "label": "新别名标签前缀", "help": "自动创建新隐藏邮箱时使用的标签前缀，默认 turb",
    },
    # ---- 浏览器地区画像 ----
    {
        "key": "BROWSER_LOCALE_PROFILE", "file": "browser.py", "type": "str", "group": "浏览器画像",
        "label": "地区画像", "help": "应与代理出口地区一致；可选 jp/cn/us/sg。当前本地代理实测为日本东京，推荐 jp",
    },

    {
        "key": "AUTO_BROWSER_LOCALE_FROM_IP", "file": "browser.py", "type": "bool", "group": "浏览器画像",
        "label": "按出口IP自动画像", "help": "开启后每个 BrowserSession 会用当前代理出口 IP 自动选择语言/时区；失败时回退到地区画像",
    },
    {
        "key": "IP_GEO_TIMEOUT", "file": "browser.py", "type": "float", "group": "浏览器画像",
        "label": "IP定位超时(秒)", "help": "出口 IP 地理信息接口的单次请求超时；接口失败会自动回退，不影响注册",
    },

    # ---- 代理池 ----
    {
        "key": "REGISTRATION_PROXY_MODE", "file": "proxy.py", "type": "str", "group": "代理平台",
        "label": "注册代理来源", "help": "pool=现有静态代理池；1024=每个注册任务从 1024Proxy 提取独立 IP；none=直连",
    },
    {
        "key": "PROXY_1024_API_URL", "file": "proxy.py", "type": "str", "group": "代理平台",
        "label": "1024Proxy 提取 API", "help": "粘贴白名单 API 完整 URL；单任务使用 num=1，注册批次会按待执行任务数批量提取，并用下方粘性时长覆盖 URL 的 time 参数；仅保存到 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "PROXY_1024_REGION", "file": "proxy.py", "type": "str", "group": "代理平台",
        "label": "家宽国家 / 地区", "help": "选择或输入 ISO 两位地区代码；例如 US=美国、JP=日本、GB=英国；Rand=随机。留空沿用提取 API 链接中的 region",
    },
    {
        "key": "PROXY_1024_PROTOCOL", "file": "proxy.py", "type": "str", "group": "代理平台",
        "label": "返回代理协议", "help": "通常填 http；也支持 https、socks5、socks5h，必须与 1024Proxy 生成接口时选择的协议一致",
    },
    {
        "key": "PROXY_1024_SESSION_MINUTES", "file": "proxy.py", "type": "int", "group": "代理平台",
        "label": "粘性时长(分钟)", "help": "默认 30，允许 1~120；延长时间本身不增加按 GB 套餐流量，只增加同一 IP 可使用的窗口",
    },
    {
        "key": "PROXY_1024_ROTATE_SESSION_TIME", "file": "proxy.py", "type": "bool", "group": "代理平台",
        "label": "每任务轮换远端会话", "help": "推荐开启；按任务在基础时长至 120 分钟间轮换 time 参数，避免白名单 API 在粘性窗口内重复返回同一 IP",
    },
    {
        "key": "PROXY_1024_API_TIMEOUT", "file": "proxy.py", "type": "float", "group": "代理平台",
        "label": "API/检测超时(秒)", "help": "提取 API 和出口 IP 检测的单次超时，建议 10~20 秒",
    },
    {
        "key": "PROXY_1024_MAX_ATTEMPTS", "file": "proxy.py", "type": "int", "group": "代理平台",
        "label": "最大有效失败次数", "help": "空响应、不可用代理或地区不符的最大次数；重复粘性 IP 另有快速重取额度，不消耗该次数",
    },
    {
        "key": "PROXY_1024_ACQUIRE_TIMEOUT", "file": "proxy.py", "type": "float", "group": "代理平台",
        "label": "代理获取总预算(秒)", "help": "包含重复 IP 重取和出口检测的整段硬上限；建议 60 秒",
    },
    {
        "key": "REGISTRATION_PROXY_RETRIES", "file": "proxy.py", "type": "int", "group": "代理平台",
        "label": "注册代理换线重试次数", "help": "只对隧道、连接重置和认证跳转超时等明确代理瞬时错误换线重试；不改变并发数，也不重试密码入口缺失",
    },
    {
        "key": "REGISTRATION_PROXY_RETRY_DELAY", "file": "proxy.py", "type": "float", "group": "代理平台",
        "label": "注册换线重试间隔(秒)", "help": "换线前的短暂间隔，避免连续请求同一代理平台窗口",
    },
    {
        "key": "PROXY_1024_VALIDATE", "file": "proxy.py", "type": "bool", "group": "代理平台",
        "label": "使用前检测出口", "help": "领取邮箱前先通过该代理访问 IPInfo，确认代理可用并记录出口地区",
    },
    {
        "key": "PROXY_1024_VALIDATE_ATTEMPTS", "file": "proxy.py", "type": "int", "group": "代理平台",
        "label": "同端点检测次数", "help": "出口检测遇到超时、连接或 SSL 瞬时错误时，先重试同一代理；建议 2",
    },
    {
        "key": "PROXY_1024_RECENT_TTL", "file": "proxy.py", "type": "int", "group": "代理平台",
        "label": "最近 IP 隔离(秒)", "help": "任务释放后多久内拒绝重复分配同一 IP；默认 1800，与 30 分钟粘性时间一致",
    },
    {
        "key": "PROXY_1024_ACQUIRE_INTERVAL", "file": "proxy.py", "type": "float", "group": "代理平台",
        "label": "提取最小间隔(秒)", "help": "并发任务调用提取 API 的最小间隔，默认 0.6 秒，避免瞬间突发",
    },
    {
        "key": "PROXY_POOL", "file": "proxy.py", "type": "list_str_multiline", "group": "代理池",
        "label": "代理池(每行一个)", "help": "每行一个代理 URL，留空行会被忽略；为空则不使用代理",
    },
    {
        "key": "PLAN_CHECK_PROXY_MODE", "file": "proxy.py", "type": "str", "group": "代理池",
        "label": "旧版套餐网络模式", "help": "仅兼容 CLI/旧接口；WebUI 查套餐、查活、Agent、Codex OAuth 使用“账号功能代理来源”",
    },
    {
        "key": "PLAN_CHECK_PROXY", "file": "proxy.py", "type": "str", "group": "代理池",
        "label": "旧版套餐专用代理", "help": "仅兼容 CLI/旧接口；留空时从代理池选择。可能包含认证信息，仅保存到 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "ACCOUNT_ACTION_PROXY_MODE", "file": "proxy.py", "type": "str", "group": "代理平台",
        "label": "账号功能代理来源", "help": "registration=跟随注册代理来源（推荐）；1024=每个账号功能申请新租约；pool=使用静态代理池；direct=直连。适用于查套餐、查活和 Codex OAuth",
    },
    {
        "key": "ACCOUNT_ACTION_PROXY", "file": "proxy.py", "type": "str", "group": "代理池",
        "label": "账号功能固定代理", "help": "仅账号功能代理来源为 pool 时优先使用；留空则从代理池抽取。可能包含认证信息，仅保存到 .env",
        "storage": "env", "secret": True,
    },
    {
        "key": "PLAN_CHECK_TIMEOUT", "file": "proxy.py", "type": "float", "group": "代理池",
        "label": "套餐查询超时(秒)", "help": "查套餐的单次请求超时，建议 10-20 秒；独立于注册请求超时",
    },
    {
        "key": "PLAN_CHECK_MAX_ATTEMPTS", "file": "proxy.py", "type": "int", "group": "代理池",
        "label": "套餐查询最大尝试次数", "help": "查套餐遇到网络错误、429、5xx 等临时错误时的重试次数，建议 2 次",
    },
    {
        "key": "PLAN_CHECK_RETRY_DELAY", "file": "proxy.py", "type": "float", "group": "代理池",
        "label": "套餐查询重试间隔(秒)", "help": "查套餐的重试间隔，按尝试次数递增；服务端 Retry-After 优先",
    },
    {
        "key": "PLAN_CHECK_REGISTRATION_RECHECK_DELAY", "file": "proxy.py", "type": "float", "group": "代理池",
        "label": "新账号资格复查延迟(秒)", "help": "新注册 free 账号未发现试用资格或首次查询失败时复查一次；0 表示关闭",
    },
    {
        "key": "PLAN_CHECK_WORKERS", "file": "proxy.py", "type": "int", "group": "代理池",
        "label": "套餐查询并发数", "help": "自动、手动和批量查套餐共用，建议 2-4 个线程",
    },
    {
        "key": "PLAN_CHECK_QUEUE_LIMIT", "file": "proxy.py", "type": "int", "group": "代理池",
        "label": "套餐查询队列上限", "help": "防止异常批量操作无限堆积，建议 100-1000",
    },
    {
        "key": "PLAN_CHECK_MIN_INTERVAL", "file": "proxy.py", "type": "float", "group": "代理池",
        "label": "套餐请求最小间隔(秒)", "help": "限制查套餐请求的启动频率，降低 429 风险",
    },
    {
        "key": "PLAN_CHECK_JITTER", "file": "proxy.py", "type": "float", "group": "代理池",
        "label": "套餐请求随机抖动(秒)", "help": "在查套餐请求的最小间隔上增加随机延迟，避免请求过于规律",
    },
    # ---- 提链 ----
    {
        "key": "EXTRACT_LINK_API_BASE", "file": "extract_link.py", "type": "str", "group": "提链",
        "label": "提链服务地址", "help": "填写提链服务 API 地址",
    },
    {
        "key": "EXTRACT_LINK_CDK", "file": "extract_link.py", "type": "str", "group": "提链",
        "label": "提链 CDK", "help": "创建提链任务和监听任务事件使用；成功提链扣 1 次",
        "storage": "env", "secret": True,
    },
    {
        "key": "EXTRACT_LINK_TYPE", "file": "extract_link.py", "type": "str", "group": "提链",
        "label": "提链类型", "help": "支持 pix / upi / kakao_pay / ideal",
    },
    {
        "key": "EXTRACT_LINK_WORKERS", "file": "extract_link.py", "type": "int", "group": "提链",
        "label": "提链并发数", "help": "批量提链后台线程数，建议 1-4",
    },
    # ---- Codex 配置 ----
    {
        "key": "SUB2API_API_BASE", "file": "sub2api.py", "type": "str", "group": "Codex",
        "label": "sub2 API基址", "help": "sub2api 服务地址；用于 Codex OAuth 授权和凭证上传，例如 http://127.0.0.1:8080",
    },
    {
        "key": "SUB2API_API_KEY", "file": "sub2api.py", "type": "str", "group": "Codex",
        "label": "sub2 API Key", "help": "sub2api 管理接口 API Key；请求头使用 x-api-key；为空则不带鉴权头", "storage": "env", "secret": True,
    },
    {
        "key": "SUB2API_API_TIMEOUT", "file": "sub2api.py", "type": "int", "group": "Codex",
        "label": "sub2 超时", "help": "sub2api 请求超时秒数",
    },
    # ---- 接码平台 ----
    # ---- Codex：基础 / CPA / sub2api 配置 ----
    {
        "key": "CODEX_AUTH_URL_SOURCE", "file": "codex.py", "type": "str", "group": "Codex",
        "label": "授权地址来源", "help": "cpa=CPA生成并上传CPA；sub2=sub2生成并上传sub2；local=本地PKCE",
    },
    {
        "key": "CPA_MANAGEMENT_URL", "file": "codex.py", "type": "str", "group": "Codex",
        "label": "CPA 管理地址", "help": "例如 http://localhost:8317/admin/oauth；程序会取 origin 调用 /v0/management/*",
    },
    {
        "key": "CPA_MANAGEMENT_KEY", "file": "codex.py", "type": "str", "group": "Codex",
        "label": "管理密钥", "help": "保存在 .env（CPA_MANAGEMENT_KEY），不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "CPA_REQUEST_TIMEOUT", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "CPA 超时(秒)", "help": "请求 CPA 管理接口的超时时间",
    },
    {
        "key": "CPA_CREDENTIAL_CONFIRM_TIMEOUT", "file": "codex.py", "type": "int", "group": "Codex",
        "label": "CPA 凭证确认等待(秒)", "help": "Callback 接收后等待 CPA 生成真实 auth JSON 的最长时间；超时则标记待确认。",
    },
    {
        "key": "CPA_SAVE_CALLBACK_RECEIPT", "file": "codex.py", "type": "bool", "group": "Codex",
        "label": "保存CPA回执", "help": "CPA 未返回完整授权文件时，本地仍保存一份回调提交记录",
    },

    {
        "key": "SMS_PROVIDER", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "接码通道", "help": "grizzly / l / h；l 使用 L_API.md，h 使用 H_API.md 定义的本地取号服务",
    },
    {
        "key": "SMS_COUNTRY", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "国家代码", "help": "传给接码平台的 country；GrizzlySMS 可用逗号填写有序备用列表（如 117,2,148），无号/超价时自动切换；H/L 通道填写单个国家",
    },
    {
        "key": "SMS_SERVICE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "服务/项目代码", "help": "GrizzlySMS/L 作为 service；H 通道作为 H_API.md 的 projectId",
    },
    {
        "key": "SMS_MAX_PRICE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "最高价格上限", "help": "这是允许购买的单号价格上限，不是固定成交价；留空表示不限，实际价格以平台返回为准",
    },
    {
        "key": "SMS_AUTO_SELECT_COUNTRY", "file": "codex.py", "type": "bool", "group": "接码平台",
        "label": "按成功率选国家", "help": "GrizzlySMS 每批次首次接码前，在价格上限内按短信成功率自动选国；同批次后续任务优先沿用",
    },
    {
        "key": "SMS_AUTO_COUNTRY_MIN_RATIO", "file": "codex.py", "type": "int", "group": "接码平台",
        "label": "成功率最低统计量", "help": "过滤成功率看似很高但统计量太少的国家；建议保持 25 或更高",
    },
    {
        "key": "SMS_MAX_RETRIES", "file": "codex.py", "type": "int", "group": "接码平台",
        "label": "换号重试次数", "help": "一个号收不到短信/被OpenAI拒时换下一个号，最多重试几次",
    },
    {
        "key": "SMS_CODE_WAIT", "file": "codex.py", "type": "int", "group": "接码平台",
        "label": "单号等短信上限(秒)", "help": "单个号码等待短信的硬上限；超时后后台取消，不再阻塞注册线程",
    },
    {
        "key": "CODEX_PHONE_TOTAL_TIMEOUT", "file": "codex.py", "type": "int", "group": "接码平台",
        "label": "手机验证总预算(秒)", "help": "整段手机验证的硬上限，包含取号、页面操作、等待短信和换号；建议 300",
    },
    {
        "key": "SMS_API_KEY", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "GrizzlySMS API密钥", "help": "GrizzlySMS 平台 API Key，保存在 .env（SMS_API_KEY），不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "H_API_BASE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "H API 地址", "help": "H 取号服务基础地址，例如 http://localhost:8788",
    },
    {
        "key": "H_ADMIN_AUTH_CODE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "H 授权码", "help": "保存在 .env（H_ADMIN_AUTH_CODE），不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "H_PHONE_PREFIX", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "H 号码前缀", "help": "H 返回号码不含国家码时填写，例如美国 10 位本地号填 1；留空则不补",
    },
    {
        "key": "H_PHONE_ACQUIRE_MODE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "H 取号方式", "help": "reusable=优先复用历史可用号码；new=每次都取一个新号码",
    },
    {
        "key": "L_API_BASE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "L API 地址", "help": "L 取号服务基础地址，例如 http://localhost:8788",
    },
    {
        "key": "L_ADMIN_AUTH_CODE", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "L 授权码", "help": "保存在 .env（L_ADMIN_AUTH_CODE），不写回 config/*.py",
        "storage": "env", "secret": True,
    },
    {
        "key": "L_PHONE_PREFIX", "file": "codex.py", "type": "str", "group": "接码平台",
        "label": "L 号码前缀", "help": "L 返回号码不含国家码时填写，例如美国 10 位本地号填 1；留空则不补",
    },
]

_FIELD_BY_KEY = {f["key"]: f for f in EDITABLE_FIELDS}

# These values are read when a fixed worker pool or Flask auth context is
# created.  config.reload_all() still updates the .env-backed module values,
# but it cannot resize an existing pool or replace the active auth context.
RESTART_REQUIRED_KEYS = frozenset({
    "WEBUI_AUTH_CODE",
    "WEBUI_SESSION_SECRET",
    "ACCOUNT_BATCH_WORKERS",
    "PLAN_CHECK_WORKERS",
    "PLAN_CHECK_QUEUE_LIMIT",
    "EXTRACT_LINK_WORKERS",
    "EXTRACT_LINK_QUEUE_LIMIT",
})


# ============================================================
# 读：解析源码取当前值（不 import，避免缓存/副作用）
# ============================================================

def _config_path(filename: str) -> Path:
    path = (_CONFIG_DIR / filename).resolve()
    # 防目录穿越：必须落在 config/ 下
    if _CONFIG_DIR not in path.parents:
        raise ValueError(f"非法配置路径: {filename}")
    return path


def _literal_default_from_expr(node):
    """尽量从赋值表达式中取“源码默认值”，不执行模块代码。

    兼容：
      KEY = "literal"
      KEY: str = env_str("KEY", "default")
      KEY = env_bool("KEY", True)
      KEY = env_value("KEY", 123, "int")
    """
    try:
        return ast.literal_eval(node)
    except Exception:
        pass

    if isinstance(node, ast.Call):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        # env_str/env_bool/env_int/env_float/env_list 的第二个位置参数是默认值。
        if func_name in {"env_str", "env_bool", "env_int", "env_float", "env_list"}:
            if len(node.args) >= 2:
                try:
                    return ast.literal_eval(node.args[1])
                except Exception:
                    return None
            return None

        # env_value(key, default, vtype)
        if func_name == "env_value" and len(node.args) >= 2:
            try:
                return ast.literal_eval(node.args[1])
            except Exception:
                return None

    return None


def _find_assignment_value_node(source: str, key: str):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for t in targets:
            if isinstance(t, ast.Name) and t.id == key:
                return node.value
    return None


def _parse_value_from_source(source: str, key: str, vtype: str):
    """从源码里解析 KEY 的当前值。失败返回 None。"""
    if vtype == "list_str_multiline":
        # 用 AST 解析整个模块，取这个赋值的 list 字面量
        value_node = _find_assignment_value_node(source, key)
        if value_node is None:
            return None
        try:
            val = ast.literal_eval(value_node)
            if isinstance(val, (list, tuple)):
                return [str(x) for x in val]
        except (ValueError, SyntaxError):
            return None
        return None

    # 标量：优先 AST 取默认值，避免 env_str("KEY", "") 被当成普通字符串。
    value_node = _find_assignment_value_node(source, key)
    if value_node is not None:
        value = _literal_default_from_expr(value_node)
        if value is not None:
            return value

    # AST 失败时再回退到旧的正则解析。
    m = re.search(
        rf"^{re.escape(key)}\s*(?::[^=\n]+)?=\s*(.+?)\s*(?:#.*)?$",
        source, re.MULTILINE,
    )
    if not m:
        return None
    raw = m.group(1).strip()
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return raw


def _parse_env_typed_value(raw: str, fallback, vtype: str):
    """把 .env 字符串按字段类型转换；失败时回退 fallback。"""
    from config.env_loader import env_value
    return env_value("__NO_SUCH_ENV_KEY__", fallback, vtype) if raw is None else _coerce_raw_value(raw, fallback, vtype)


def _coerce_raw_value(raw: str, fallback, vtype: str):
    try:
        if raw is None or str(raw).strip() == "":
            return fallback
        if vtype == "bool":
            return str(raw).strip().lower() in ("true", "1", "yes", "on", "y")
        if vtype == "int":
            return int(str(raw).strip())
        if vtype == "float":
            return float(str(raw).strip())
        if vtype == "list_str_multiline":
            text = str(raw)
            try:
                val = ast.literal_eval(text)
                if isinstance(val, (list, tuple)):
                    return [str(x).strip() for x in val if str(x).strip()]
            except Exception:
                pass
            return [line.strip() for line in text.splitlines() if line.strip()]
        return str(raw)
    except Exception:
        return fallback


def get_config() -> list[dict]:
    """返回所有可编辑项的当前值 + 元信息，供前端渲染表单。

    优先读取 `.env` / 环境变量；没有配置时回退到 `config/*.py` 默认值。
    """
    from config.env_loader import load_env, read_env_file
    load_env(override=True)
    env_file_values = read_env_file()

    out = []
    for field in EDITABLE_FIELDS:
        key = field["key"]
        path = _config_path(field["file"])
        source = path.read_text(encoding="utf-8") if path.exists() else ""
        fallback = _parse_value_from_source(source, key, field["type"])

        if key in env_file_values:
            raw_env_value = env_file_values[key]
            if field["type"] == "list_str_multiline" and key in EXPLICIT_EMPTY_LIST_KEYS and str(raw_env_value).strip() == "":
                value = []
            else:
                value = _coerce_raw_value(raw_env_value, fallback, field["type"])
        elif os.getenv(key) is not None:
            value = _coerce_raw_value(os.getenv(key, ""), fallback, field["type"])
        else:
            value = fallback

        if field["type"] in ("str", "list_str_multiline"):
            value = _normalize_config_value(value, field["type"])
        item = dict(field)
        item["storage"] = "env"
        item["requires_restart"] = key in RESTART_REQUIRED_KEYS
        item["value"] = value
        out.append(item)
    return out


# ============================================================
# 写：统一写 .env，不修改 config/*.py
# ============================================================


_PLACEHOLDER_EMPTY = {
    "", "-", "—", "无", "空", "none", "null", "n/a", "na", "未设置", "未配置",
}


def _normalize_config_value(value, vtype: str):
    """把前端/历史占位空值规范化，避免 '-' 被当成真实配置。"""
    if vtype == "str":
        s = "" if value is None else str(value).strip()
        if s.lower() in {x.lower() for x in _PLACEHOLDER_EMPTY}:
            return ""
        return s
    if vtype == "list_str_multiline":
        if value is None:
            return []
        if isinstance(value, str):
            lines = value.splitlines()
        elif isinstance(value, (list, tuple)):
            lines = list(value)
        else:
            lines = [str(value)]
        out = []
        for item in lines:
            s = str(item or "").strip()
            if not s or s.lower() in {x.lower() for x in _PLACEHOLDER_EMPTY}:
                continue
            out.append(s)
        return out
    return value


def _format_literal(value, vtype: str) -> str:
    """把前端传来的值格式化成 Python 字面量字符串。"""
    if vtype == "bool":
        if isinstance(value, str):
            value = value.strip().lower() in ("true", "1", "yes", "on")
        return "True" if value else "False"
    if vtype == "int":
        return str(int(value))
    if vtype == "float":
        return repr(float(value))
    if vtype == "str":
        s = str(value)
        # 用 repr 保证转义安全，但统一成双引号风格
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise ValueError(f"_format_literal 不支持的类型: {vtype}")


def _replace_scalar(source: str, key: str, literal: str) -> str:
    """替换 `KEY[: 类型] = 旧值` 行的右值，保留行内注释和类型标注。"""
    pattern = re.compile(
        rf"^(?P<head>{re.escape(key)}\s*(?::[^=\n]+)?=\s*)"
        rf"(?P<val>.+?)"
        rf"(?P<tail>\s*(?:#.*)?)$",
        re.MULTILINE,
    )
    if not pattern.search(source):
        raise ValueError(f"未在源码中找到可替换的赋值: {key}")
    return pattern.sub(lambda m: f"{m.group('head')}{literal}{m.group('tail')}", source, count=1)


def _replace_proxy_pool(source: str, lines: list[str]) -> str:
    """整块替换 PROXY_POOL = [ ... ] 列表字面量（保留前面的赋值头）。"""
    items = [ln.strip() for ln in lines if ln.strip()]
    if items:
        body = "\n".join(
            '    "' + it.replace("\\", "\\\\").replace('"', '\\"') + '",'
            for it in items
        )
        literal = "[\n" + body + "\n]"
    else:
        literal = "[]"

    # 匹配 PROXY_POOL = [ ... ]（含跨行），用 AST 定位起止偏移最稳
    tree = ast.parse(source)
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "PROXY_POOL":
                src_lines = source.splitlines(keepends=True)
                start = node.value.lineno          # 值（[）所在行，1-based
                end = node.value.end_lineno        # 值（]）所在行，1-based
                col = node.value.col_offset         # [ 在起始行的列偏移
                # 保留起始行 [ 之前的内容（即 "PROXY_POOL = " 或 "PROXY_POOL: list = "）
                prefix = src_lines[start - 1][:col]
                # 保留结束行 ] 之后的内容（行内注释 / 换行）
                end_line = src_lines[end - 1]
                suffix = end_line[node.value.end_col_offset:]
                new_lines = (
                    src_lines[: start - 1]
                    + [prefix + literal + suffix]
                    + src_lines[end:]
                )
                return "".join(new_lines)
    raise ValueError("未找到 PROXY_POOL 赋值")


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _format_env_value(value, vtype: str) -> str:
    """把前端值格式化成适合写入 .env 的字符串。"""
    if vtype == "bool":
        if isinstance(value, str):
            value = value.strip().lower() in ("true", "1", "yes", "on", "y")
        return "True" if value else "False"
    if vtype == "int":
        return str(int(value))
    if vtype == "float":
        return repr(float(value))
    if vtype == "list_str_multiline":
        lines = _normalize_config_value(value, vtype)
        return "\n".join(lines) if lines else "[]"
    if vtype == "str":
        return _normalize_config_value(value, vtype)
    return "" if value is None else str(value)


def update_config(updates: dict) -> dict:
    """批量更新配置。所有 WebUI 可编辑项只写项目根 `.env`。"""
    from config.env_loader import write_env_values, load_env

    updated, ignored = [], []
    env_updates: dict[str, str] = {}

    for key, value in updates.items():
        field = _FIELD_BY_KEY.get(key)
        if field is None:
            ignored.append(key)
            continue
        env_updates[key] = _format_env_value(value, field["type"])
        updated.append(key)


    env_updated = write_env_values(env_updates) if env_updates else []
    if env_updated:
        load_env(override=True)

    return {
        "updated": updated,
        "ignored": ignored,
        "env_updated": env_updated,
        "restart_required": [key for key in updated if key in RESTART_REQUIRED_KEYS],
    }
