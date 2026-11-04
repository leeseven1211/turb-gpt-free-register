# -*- coding: utf-8 -*-
"""
注册基础信息（默认值）

CLI 走 main.py 时会优先读这里；Web 控制台批量注册时也会用同样的默认值。
留空字段会触发交互式输入或自动生成（仅 USE_EMAIL_SERVICE=True 时邮箱会从 Outlook 池领取）。
"""
from config.env_loader import apply_env_overrides
from config.schema import schema_default

# 注册邮箱（留空 + USE_EMAIL_SERVICE=True 时从 Outlook 池领取）
REGISTER_EMAIL = schema_default("REGISTER_EMAIL")

# 注册任务按此国家向统一代理池申请，独立于代理池默认国家。
REGISTRATION_COUNTRY = schema_default("REGISTRATION_COUNTRY")

# 注册固定优先使用页面提供的登录/创建密码入口；没有入口时继续邮箱验证码。
# OpenAI 仍可能在密码步骤后要求邮箱验证码；旧 otp 配置按现行策略读取。
REGISTRATION_AUTH_MODE = schema_default("REGISTRATION_AUTH_MODE")

# 密码提交后的页面跳转使用独立预算。慢代理下 OpenAI 可能在表单提交后数十秒才
# 进入邮箱验证码页，不能继续消耗“检测/填写密码页”的剩余时间。
REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS = schema_default("REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS")

# 注册后套餐查询是独立后处理能力。默认保持原有行为，关闭后账号仍会保存，
# 之后可在账号管理中手动查套餐或由“补全账号”按其自身配置处理。
REGISTRATION_PLAN_CHECK_ENABLED = schema_default("REGISTRATION_PLAN_CHECK_ENABLED")

# 用户名（注册完成后设置的显示名称，留空会自动生成 "Foo Bar" 形式）
# OpenAI 限制：name_invalid_chars —— 只允许字母和空格
REGISTER_NAME = schema_default("REGISTER_NAME")

# ---- 统一运行配置覆盖 ----
apply_env_overrides(globals())
if str(REGISTRATION_AUTH_MODE).strip().lower() == "otp":
    REGISTRATION_AUTH_MODE = "password"
