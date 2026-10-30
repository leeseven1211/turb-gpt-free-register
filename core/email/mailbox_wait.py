"""仅显式启用的邮箱取码预算，兼容各 provider 的既有调用契约。"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import time

from core.auth.challenge import AuthCancelledError
from core.auth.state_machine import StageTimeout


_ACTIVE_BUDGET = ContextVar("mailbox_wait_budget", default=None)
_ACTIVE_CHECKPOINTS = ContextVar("mailbox_wait_checkpoints", default=())


class _MailboxWaitControl(BaseException):
    """越过供应商的通用重试捕获，在最外层调用域还原原异常。"""

    def __init__(self, error):
        self.error = error


WAIT_INTERRUPTED = (AuthCancelledError, StageTimeout, _MailboxWaitControl)


def cooperative_checkpoint():
    """只在显式调用域内，由取码原线程检查页面、取消及共享预算。"""
    active = _ACTIVE_CHECKPOINTS.get()
    if not active:
        return
    try:
        budget = current_budget()
        if budget is not None:
            budget.require("邮箱协作检查")
        for callback, _poll, _timeout in active:
            callback()
    except Exception as error:
        raise _MailboxWaitControl(error) from error


def cooperative_poll_limit(default):
    """未启用时保留供应商原来的长轮询段。"""
    return min([default, *(item[1] for item in _ACTIVE_CHECKPOINTS.get())])


@contextmanager
def cooperative_lock(lock):
    """仅显式调用域内按短段等已有锁，仍由原worker观察页面。"""
    if not _ACTIVE_CHECKPOINTS.get():
        with lock:
            yield
        return
    acquired = False
    try:
        while not acquired:
            cooperative_checkpoint()
            delay = cooperative_poll_limit(0.1)
            budget = current_budget()
            if budget is not None:
                delay = min(delay, budget.require("邮箱共享锁"))
            acquired = lock.acquire(timeout=delay)
        cooperative_checkpoint()
        yield
    finally:
        if acquired:
            lock.release()


@contextmanager
def use_cooperative_wait(page_checkpoint, *, poll_seconds=1.0, request_timeout=2.0):
    """嵌套调用共用原线程检查；退出时完整恢复，控制信号不冒充取消。"""
    parent = _ACTIVE_CHECKPOINTS.get()
    policy = (page_checkpoint, max(0.01, float(poll_seconds)), max(0.01, float(request_timeout)))
    token = _ACTIVE_CHECKPOINTS.set((*parent, policy))
    try:
        cooperative_checkpoint()
        yield
        cooperative_checkpoint()
    except _MailboxWaitControl as signal:
        if parent:
            raise
        raise signal.error
    finally:
        _ACTIVE_CHECKPOINTS.reset(token)


def current_budget():
    return _ACTIVE_BUDGET.get()


def bounded_timeout(timeout):
    """在实际建连前检查取消，并裁剪单次请求/套接字超时。"""
    cooperative_checkpoint()
    policies = _ACTIVE_CHECKPOINTS.get()
    if policies:
        cap = min(item[2] for item in policies)
        if isinstance(timeout, tuple):
            timeout = tuple(min(float(value), cap / len(timeout)) if value is not None and float(value) > 0
                            else cap / len(timeout) for value in timeout)
        else:
            timeout = min(float(timeout), cap) if timeout is not None and float(timeout) > 0 else cap
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
    if _ACTIVE_CHECKPOINTS.get():
        clock = budget.clock if budget is not None else time.monotonic
        end = clock() + max(0.0, float(seconds))
        while clock() < end:
            cooperative_checkpoint()
            delay = cooperative_poll_limit(max(0.0, end - clock()))
            try:
                if budget is None:
                    time.sleep(delay)
                else:
                    budget.sleep(delay)
            except Exception as error:
                raise _MailboxWaitControl(error) from error
        cooperative_checkpoint()
        return
    if budget is None:
        time.sleep(seconds)
    else:
        budget.sleep(seconds)


def request_kwargs(timeout=30):
    """没有阶段预算时沿用调用方原有 session 默认参数。"""
    return {} if current_budget() is None and not _ACTIVE_CHECKPOINTS.get() else {"timeout": bounded_timeout(timeout)}


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
    if budget is not None or _ACTIVE_CHECKPOINTS.get():
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
