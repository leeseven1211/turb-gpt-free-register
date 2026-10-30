# -*- coding: utf-8 -*-
"""Roxy 刷新登录的错误分类；只解释已记录的失败，不决定认证与重试行为。"""
from __future__ import annotations

import re


ROXY_LOGIN_CAUSES = {
    "roxy_login_page_not_ready": ("ROXY-REFRESH-007", "Roxy 登录页未就绪，邮箱入口未出现", "browser"),
    "roxy_login_page_timeout": ("ROXY-REFRESH-008", "Roxy 登录页未就绪，登录预检请求超时", "network"),
    "roxy_login_preflight_timeout": ("ROXY-REFRESH-009", "Roxy 登录预检请求超时", "network"),
    "roxy_login_preflight_failed": ("ROXY-REFRESH-010", "Roxy 登录预检请求失败", "response"),
}


def roxy_login_failure_code(message: object) -> str:
    """从固定异常标记识别症状，不把 NextAuth 超时一律认作预检失败。"""
    text = str(message or "")
    page_not_ready = any(marker in text for marker in (
        "找不到邮箱输入框/邮箱入口", "邮箱入口未挂载且 NextAuth 兜底失败",
    ))
    nextauth_failed = any(marker in text for marker in (
        "邮箱入口未挂载且 NextAuth 兜底失败", "浏览器 NextAuth 登录导航失败",
    ))
    # 该字段只证明兜底 signin 尚未发出，不能推断整条任务从未提交过认证。
    preflight_failed = nextauth_failed and re.search(
        r'''["']not_dispatched["']\s*:\s*true\b''', text, flags=re.IGNORECASE,
    )
    if preflight_failed:
        stage = re.search(r'''["']stage["']\s*:\s*["']([^"']+)["']''', text)
        stage_name = stage.group(1) if stage else ""
        if stage_name == "timeout" and re.search(r'''["']reason["']\s*:\s*["']nextauth_budget_exhausted["']''', text):
            return "roxy_login_page_timeout" if page_not_ready else "roxy_login_preflight_timeout"
        if stage_name == "csrf" or (stage_name == "exception" and "nextauth_exception" in text):
            return "roxy_login_preflight_failed"
        if re.search(r'''["']reason["']\s*:\s*["']csrf_preflight_(?:result_unknown|token_missing)["']''', text):
            return "roxy_login_preflight_failed"
    return "roxy_login_page_not_ready" if page_not_ready else ""
