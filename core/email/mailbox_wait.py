"""仅显式启用的邮箱取码预算，兼容各 provider 的既有调用契约。"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import time

from core.auth.challenge import AuthCancelledError
from core.auth.state_machine import StageTimeout


WAIT_INTERRUPTED = (AuthCancelledError, StageTimeout)


_ACTIVE_BUDGET = ContextVar("mailbox_wait_budget", default=None)


def current_budget():
    return _ACTIVE_BUDGET.get()


def bounded_timeout(timeout):
    """在实际建连前检查取消，并裁剪单次请求/套接字超时。"""
    budget = current_budget()
    if budget is None:
        return timeout
    remaining = budget.require("邮箱网络请求")
    if isinstance(timeout, tuple):
        # requests 的 connect/read 是空闲超时；分配剩余额度到各参数，
        # 不把持续返回数据的同步响应误称为可硬中断的总耗时上限。
        part = remaining / len(timeout)
        return tuple(min(float(value), part) if value is not None and float(value) > 0 else part for value in timeout)
    return min(float(timeout), remaining) if timeout is not None and float(timeout) > 0 else remaining


def bounded_sleep(seconds):
    budget = current_budget()
    if budget is None:
        time.sleep(seconds)
    else:
        budget.sleep(seconds)


def request_kwargs(timeout=30):
    """没有阶段预算时沿用调用方原有 session 默认参数。"""
    return {} if current_budget() is None else {"timeout": bounded_timeout(timeout)}


def close_imap(mail):
    """异常收口只释放本机套接字和流，不发出新的 LOGOUT 请求。"""
    for resource in (getattr(mail, "sock", None), getattr(mail, "file", None)):
        if resource is not None:
            try:
                resource.close()
            except Exception:
                pass


def imap_call(mail, method, *args, **kwargs):
    """每条 IMAP 命令重新裁剪套接字超时，避免多条读取叠加预算。"""
    budget = current_budget()
    if budget is not None:
        sock = getattr(mail, "sock", None)
        if method == "logout":
            # 只读会话退出无需等待远端响应，避免收码结束后超预算。
            close_imap(mail)
            return None
        timeout = bounded_timeout(30)
        if sock is not None:
            sock.settimeout(timeout)
    return getattr(mail, method)(*args, **kwargs)


@contextmanager
def use_budget(budget):
    """预算只属于当前调用；退出或异常时恢复原来的上下文。"""
    token = _ACTIVE_BUDGET.set(budget)
    try:
        budget.require("邮箱验证码")
        yield budget
    finally:
        _ACTIVE_BUDGET.reset(token)
