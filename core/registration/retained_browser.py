"""恢复失败窗口的连接，业务身份始终重新读取 PostgreSQL。"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import threading
from types import SimpleNamespace
from typing import Any, Mapping


@dataclass
class RetainedRoxyBrowser:
    """原浏览器的临时连接资源，不代替任务、Attempt 或账号的持久记录。"""

    driver: Any
    opened: Any
    email: str
    job_id: int
    attempt_id: int
    root_job_id: int
    otp_after_ts: float | None = None


_LOCK = threading.RLock()
_RETAINED: OrderedDict[int, RetainedRoxyBrowser] = OrderedDict()
_MAX_RETAINED = 128
_REGISTRATION_TYPES = frozenset({"registration", "registration_resume"})
_TERMINAL_SOURCE_STATES = frozenset({
    "failed", "partial_success", "request_unknown", "cancelled", "stopped",
})


def _positive_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _attempt_id(row: Mapping[str, Any]) -> int | None:
    values = [row[key] for key in ("attempt_id", "registration_attempt_id")
              if row.get(key) is not None]
    parsed = [_positive_id(value) for value in values]
    if not parsed or any(value is None for value in parsed) or len(set(parsed)) != 1:
        return None
    return parsed[0]


def _email(value: Any) -> str:
    return str(value or "").strip().casefold()


def _root_id(row: Mapping[str, Any]) -> int | None:
    return _positive_id(row.get("root_job_id") or row.get("id"))


def _job_matches(row: Any, *, job_id: int, email: str, attempt_id: int) -> bool:
    return bool(
        isinstance(row, Mapping)
        and _positive_id(row.get("id")) == job_id
        and _email(row.get("email")) == email
        and _attempt_id(row) == attempt_id
        and str(row.get("job_type") or "") in _REGISTRATION_TYPES
    )


def _original_otp_time(driver: Any, source: Mapping[str, Any]) -> float | None:
    missing = object()
    original_time = getattr(driver, "_registration_otp_after_ts", missing)
    if original_time is not missing:
        try:
            value = float(original_time)
            return value if math.isfinite(value) and value >= 0 else None
        except (TypeError, ValueError, OverflowError):
            return None
    # 重跑任务开始时间不能证明原邮件边界；明确未知的 driver 时间也不推断。
    if source.get("parent_job_id") is not None:
        return None
    started_at = source.get("started_at")
    try:
        if isinstance(started_at, datetime):
            parsed = started_at
        elif isinstance(started_at, str):
            parsed = datetime.fromisoformat(started_at.strip().replace("Z", "+00:00"))
        else:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        value = parsed.timestamp()
        return value if math.isfinite(value) and value >= 0 else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def retain_failed_browser(driver: Any, opened: Any, *, email: str,
                          facts: Mapping[str, Any]) -> bool:
    """登记原失败连接；旧 worker 此时仍可处于失败收口阶段。"""
    if driver is None or opened is None or not isinstance(facts, Mapping):
        return False
    address = _email(email)
    job_id = _positive_id(facts.get("job_id"))
    attempt_id = _attempt_id(facts)
    if not address or job_id is None or attempt_id is None:
        return False
    if not str(getattr(opened, "profile_id", "") or "").strip():
        return False
    from core import db

    with _LOCK:
        try:
            source = db.get_job(job_id)
        except Exception:
            return False
        if not _job_matches(source, job_id=job_id, email=address, attempt_id=attempt_id):
            return False
        root_job_id = _root_id(source)
        if root_job_id is None:
            return False
        if facts.get("root_job_id") is not None and _positive_id(facts["root_job_id"]) != root_job_id:
            return False
        _RETAINED[attempt_id] = RetainedRoxyBrowser(
            driver=driver, opened=opened, email=address, job_id=job_id,
            attempt_id=attempt_id, root_job_id=root_job_id,
            otp_after_ts=_original_otp_time(driver, source),
        )
        _RETAINED.move_to_end(attempt_id)
        while len(_RETAINED) > _MAX_RETAINED:
            # 只释放本进程缓存的引用；不改变 Roxy 窗口或 Profile 的生命周期。
            _RETAINED.popitem(last=False)
        return True


def _blocked(reason: str) -> RuntimeError:
    return RuntimeError(f"request_unknown: {reason}，已保留原浏览器提交")


def persist_browser_resume_context(driver: Any, opened: Any, *, email: str,
                                  facts: Mapping[str, Any]) -> bool:
    """打开窗口时即保存最小连接资料，失败收口时再更新原邮件时间。"""
    if opened is None or not isinstance(facts, Mapping):
        return False
    attempt_id = _attempt_id(facts)
    job_id = _positive_id(facts.get("job_id"))
    run_id = _positive_id(facts.get("run_id"))
    execution_id = str(facts.get("execution_id") or "").strip()
    profile_id = str(getattr(opened, "profile_id", "") or "").strip()
    debugger_address = str(getattr(opened, "debugger_address", "") or "").strip()
    if not all((attempt_id, job_id, run_id, execution_id, profile_id, debugger_address)):
        return False
    raw = getattr(opened, "raw", None)
    data = raw.get("data") if isinstance(raw, Mapping) else None
    driver_path = str(data.get("driver") or data.get("driverPath") or data.get("driver_path") or "").strip() if isinstance(data, Mapping) else ""
    otp_after_ts = _original_otp_time(driver, {"parent_job_id": job_id})
    try:
        from core.storage import registration

        registration.save_browser_resume_context(
            attempt_id, email=_email(email), job_id=job_id, run_id=run_id,
            execution_id=execution_id, profile_id=profile_id,
            debugger_address=debugger_address, driver_path=driver_path,
            otp_after_ts=otp_after_ts,
        )
    except Exception:
        raise _blocked("原窗口恢复关联保存失败") from None
    return True


def recover_attempt_failed_browser(*, email: str, profile_id: str | None,
                                  facts: Mapping[str, Any]) -> RetainedRoxyBrowser | None:
    """缓存丢失后按原 Attempt 恢复窗口，尚无账号记录也可接管。"""
    if not isinstance(facts, Mapping):
        return None
    current_job_id = _positive_id(facts.get("job_id"))
    attempt_id = _attempt_id(facts)
    address = _email(email)
    if current_job_id is None or attempt_id is None or not address:
        return None
    with _LOCK:
        try:
            from core import db
            from core.registration.service import is_job_worker_active
            from core.browser.roxy.client import RoxyOpenResult
            from core.storage import registration

            current = db.get_job(current_job_id)
            if not isinstance(current, Mapping) or current.get("parent_job_id") is None:
                return None
            private = registration.get_private_resume_context(attempt_id, email=address)
        except Exception:
            raise _blocked("原浏览器恢复事实读取失败") from None
        if not isinstance(private, Mapping):
            raise _blocked("原浏览器恢复资料无法读取")
        binding = private.get("retained_browser")
        if not isinstance(binding, Mapping):
            return None
        source_job_id = _positive_id(binding.get("job_id"))
        root_job_id = _positive_id(binding.get("root_job_id"))
        if (source_job_id is None or root_job_id is None
                or not _job_matches(current, job_id=current_job_id, email=address, attempt_id=attempt_id)
                or _root_id(current) != root_job_id
                or (facts.get("root_job_id") is not None and _positive_id(facts["root_job_id"]) != root_job_id)):
            raise _blocked("当前重跑任务身份未能核验")
        try:
            source = db.get_job(source_job_id)
            source_active = is_job_worker_active(source_job_id)
        except Exception:
            raise _blocked("原浏览器恢复事实读取失败") from None
        if (not _job_matches(source, job_id=source_job_id, email=address, attempt_id=attempt_id)
                or _root_id(source) != root_job_id):
            raise _blocked("原任务身份未能核验")
        if (str(source.get("status") or "") not in _TERMINAL_SOURCE_STATES
                or str(source.get("debug_state") or "") == "paused" or source_active):
            raise _blocked("原任务尚未结束或旧 worker 仍在使用浏览器")
        if (source.get("account_id") is not None and current.get("account_id") is not None
                and _positive_id(source["account_id"]) != _positive_id(current["account_id"])):
            raise _blocked("原任务与当前重跑账号绑定不一致")
        saved_profile = str(binding.get("profile_id") or "").strip()
        debugger_address = str(binding.get("debugger_address") or "").strip()
        if not saved_profile or not debugger_address:
            raise _blocked("原浏览器连接资料不完整")
        if profile_id and str(profile_id).strip() != saved_profile:
            raise _blocked("当前账号环境绑定与原浏览器不一致")
        raw = {"data": {"http": debugger_address, "driver": str(binding.get("driver_path") or "")}}
        opened = RoxyOpenResult(
            profile_id=saved_profile, raw=raw, debugger_address=debugger_address,
            created_by_run=False, account_bound=current.get("account_id") is not None,
        )
        # 只还原已保存的邮件边界；没有边界时不能按重跑开始时间推断旧验证码。
        otp_after_ts = _original_otp_time(SimpleNamespace(_registration_otp_after_ts=binding.get("otp_after_ts")), source)
        return RetainedRoxyBrowser(
            driver=None, opened=opened, email=address, job_id=source_job_id,
            attempt_id=attempt_id, root_job_id=root_job_id, otp_after_ts=otp_after_ts,
        )


def take_failed_browser(*, email: str, profile_id: str | None,
                        facts: Mapping[str, Any]) -> RetainedRoxyBrowser | None:
    """锁内核对旧任务与当前任务的持久身份后，一次性认领原连接。"""
    if not isinstance(facts, Mapping):
        return None
    lookup_ids = [_positive_id(facts.get(key)) for key in ("attempt_id", "registration_attempt_id")]
    with _LOCK:
        candidate = next((_RETAINED[value] for value in lookup_ids if value in _RETAINED), None)
        if candidate is None:
            return None
        current_job_id = _positive_id(facts.get("job_id"))
        if (current_job_id is None or _attempt_id(facts) != candidate.attempt_id
                or _email(email) != candidate.email):
            raise _blocked("当前重跑身份与原浏览器不一致")
        if facts.get("root_job_id") is not None and _positive_id(facts["root_job_id"]) != candidate.root_job_id:
            raise _blocked("当前重跑任务链与原浏览器不一致")
        if profile_id and str(profile_id).strip() != str(candidate.opened.profile_id).strip():
            raise _blocked("当前账号环境绑定与原浏览器不一致")
        try:
            from core import db
            from core.registration.service import is_job_worker_active

            source = db.get_job(candidate.job_id)
            current = db.get_job(current_job_id)
            source_active = is_job_worker_active(candidate.job_id)
        except Exception:
            # 不复制底层异常，避免连接信息、邮箱或浏览器端口进入用户错误文案。
            raise _blocked("原浏览器恢复事实读取失败") from None
        if not _job_matches(source, job_id=candidate.job_id, email=candidate.email,
                            attempt_id=candidate.attempt_id):
            raise _blocked("原任务身份未能核验")
        if not _job_matches(current, job_id=current_job_id, email=candidate.email,
                            attempt_id=candidate.attempt_id):
            raise _blocked("当前重跑任务身份未能核验")
        if _root_id(source) != candidate.root_job_id or _root_id(current) != candidate.root_job_id:
            raise _blocked("原任务与当前重跑任务链不一致")
        if (source.get("account_id") is not None and current.get("account_id") is not None
                and _positive_id(source["account_id"]) != _positive_id(current["account_id"])):
            raise _blocked("原任务与当前重跑账号绑定不一致")
        if (str(source.get("status") or "") not in _TERMINAL_SOURCE_STATES
                or str(source.get("debug_state") or "") == "paused" or source_active):
            raise _blocked("原任务尚未结束或旧 worker 仍在使用浏览器")
        return _RETAINED.pop(candidate.attempt_id)


def recover_bound_failed_browser(*, email: str, profile_id: str | None,
                                facts: Mapping[str, Any]) -> RetainedRoxyBrowser | None:
    """进程缓存丢失时，从同一失败任务的账号绑定恢复原调试连接。"""
    requested_profile = str(profile_id or "").strip()
    if not requested_profile or not isinstance(facts, Mapping):
        return None
    current_job_id = _positive_id(facts.get("job_id"))
    if current_job_id is None:
        return None
    address = _email(email)
    attempt_id = _attempt_id(facts)
    with _LOCK:
        try:
            from core import db
            from core.registration.service import is_job_worker_active
            from core.browser.roxy.profile_binding import _roxy_binding, account_profile_id
            from core.browser.roxy.client import RoxyBrowserClient, RoxyOpenResult

            current = db.get_job(current_job_id)
        except Exception:
            raise _blocked("原浏览器恢复事实读取失败") from None
        if not isinstance(current, Mapping):
            raise _blocked("当前重跑任务身份未能核验")
        if current.get("parent_job_id") is None:
            return None
        source_job_id = _positive_id(current.get("parent_job_id"))
        if (not address or attempt_id is None or source_job_id is None
                or not _job_matches(current, job_id=current_job_id, email=address, attempt_id=attempt_id)):
            raise _blocked("当前重跑任务身份未能核验")
        try:
            source = db.get_job(source_job_id)
            source_active = is_job_worker_active(source_job_id)
        except Exception:
            raise _blocked("原浏览器恢复事实读取失败") from None
        if not _job_matches(source, job_id=source_job_id, email=address, attempt_id=attempt_id):
            raise _blocked("原任务身份未能核验")
        root_job_id = _root_id(source)
        if (root_job_id is None or _root_id(current) != root_job_id
                or (facts.get("root_job_id") is not None
                    and _positive_id(facts["root_job_id"]) != root_job_id)):
            raise _blocked("原任务与当前重跑任务链不一致")
        if (str(source.get("status") or "") not in _TERMINAL_SOURCE_STATES
                or str(source.get("debug_state") or "") == "paused" or source_active):
            raise _blocked("原任务尚未结束或旧 worker 仍在使用浏览器")
        account_id = _positive_id(current.get("account_id"))
        if account_id is None or _positive_id(source.get("account_id")) != account_id:
            raise _blocked("原任务与当前重跑账号绑定不一致")
        try:
            account = db.get_account(account_id)
        except Exception:
            raise _blocked("原浏览器恢复事实读取失败") from None
        if (not isinstance(account, Mapping) or _positive_id(account.get("id")) != account_id
                or _email(account.get("email")) != address):
            raise _blocked("原账号身份未能核验")
        binding = _roxy_binding(account)
        bound_profile = account_profile_id(account)
        if binding is None or not bound_profile:
            return None
        if bound_profile != requested_profile:
            raise _blocked("当前账号环境绑定与原浏览器不一致")
        raw = binding.get("open_result")
        if not isinstance(raw, Mapping):
            return None
        try:
            debugger_address = RoxyBrowserClient._extract_debugger_address(dict(raw))
        except Exception:
            raise _blocked("原浏览器连接元数据读取失败") from None
        if not debugger_address:
            return None
        # 这里只还原连接元数据；窗口是否仍存活由调用方独立确认。
        opened = RoxyOpenResult(
            profile_id=requested_profile, raw=dict(raw), debugger_address=debugger_address,
            created_by_run=False, account_bound=True,
        )
        return RetainedRoxyBrowser(
            driver=None, opened=opened, email=address, job_id=source_job_id,
            attempt_id=attempt_id, root_job_id=root_job_id,
            otp_after_ts=_original_otp_time(None, source),
        )


__all__ = [
    "RetainedRoxyBrowser", "retain_failed_browser", "take_failed_browser",
    "recover_bound_failed_browser", "recover_attempt_failed_browser", "persist_browser_resume_context",
]
