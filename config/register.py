# -*- coding: utf-8 -*-
"""
注册基础信息（默认值）

CLI 走 main.py 时会优先读这里；Web 控制台批量注册时也会用同样的默认值。
留空字段会触发交互式输入或自动生成（仅 USE_EMAIL_SERVICE=True 时邮箱会从 Outlook 池领取）。
"""
from config.env_loader import apply_env_overrides

# 注册邮箱（留空 + USE_EMAIL_SERVICE=True 时从 Outlook 池领取）
REGISTER_EMAIL = ""

# 注册认证流程：otp=优先一次性验证码；password=遇到注册密码页时设置密码。
# 即使选择 password，OpenAI 仍可能在后续要求邮箱验证码。
REGISTRATION_AUTH_MODE = "otp"

# 密码提交后的页面跳转使用独立预算。慢代理下 OpenAI 可能在表单提交后数十秒才
# 进入邮箱验证码页，不能继续消耗“检测/填写密码页”的剩余时间。
REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS = 60

# 注册后套餐查询是独立后处理能力。默认保持原有行为，关闭后账号仍会保存，
# 之后可在账号管理中手动查套餐或由“补全账号”按其自身配置处理。
REGISTRATION_PLAN_CHECK_ENABLED = True

# 用户名（注册完成后设置的显示名称，留空会自动生成 "Foo Bar" 形式）
# OpenAI 限制：name_invalid_chars —— 只允许字母和空格
REGISTER_NAME = ""

# ---- .env overrides for WebUI editable fields ----
apply_env_overrides(globals(), {
    'REGISTER_EMAIL': 'str',
    'REGISTRATION_AUTH_MODE': 'str',
    'REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS': 'int',
    'REGISTRATION_PLAN_CHECK_ENABLED': 'bool',
    'REGISTER_NAME': 'str',
})
