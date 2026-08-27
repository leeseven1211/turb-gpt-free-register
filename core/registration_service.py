# -*- coding: utf-8 -*-
"""
注册任务服务层：
    - 线程池并发执行 run_registration
    - 每个任务在 data/registration_jobs.json 里有一条记录
    - 每个任务的日志写到 data/logs/<job_uuid>.log，便于 Web UI 实时尾巴

使用：
    submit_registration(email_source="outlook", count=5)
    → 创建 5 个任务，丢入线程池，立即返回 [job_dict, ...]
"""
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from core import codex_retry_service, db
from core.operations import task_gateway as account_task_store

logger = logging.getLogger(__name__)

# 全局线程池，最大并发数（WebUI 每次提交时可按最新 workers 重建）
_DEFAULT_MAX_WORKERS = 4
_MIN_MAX_WORKERS = 1
_MAX_MAX_WORKERS = 16
_executor: ThreadPoolExecutor | None = None
_executor_workers = _DEFAULT_MAX_WORKERS
_executor_generation = 0
_retired_executors: list[ThreadPoolExecutor] = []
_executor_lock = threading.RLock()

_STOP_EVENTS: dict[int, threading.Event] = {}
_ACTIVE_JOBS: set[int] = set()
_STOP_LOCK = threading.Lock()
_THREAD_CTX = threading.local()


class StopRequested(RuntimeError):
    """用户手动停止注册任务。"""


def _activate_job(job_id: int) -> None:
    _THREAD_CTX.job_id = int(job_id)
    _THREAD_CTX.debug_token = None
    try:
        from core import registration_debug

        debug_job = db.get_job(int(job_id)) or {}
        _THREAD_CTX.debug_token = registration_debug.activate_for_job(debug_job)
    except Exception:
        logger.exception("[Job %s] 启动注册调试记录器失败；注册流程继续执行", job_id)
    try:
        from core import sms_provider

        job = db.get_job(int(job_id)) or {}
        sms_provider.set_sms_batch_context(str(job.get("batch_id") or f"job-{job_id}"))
    except Exception:
        logger.exception("[Job %s] 设置接码批次上下文失败", job_id)
    with _STOP_LOCK:
        _STOP_EVENTS.setdefault(int(job_id), threading.Event())
        _ACTIVE_JOBS.add(int(job_id))


def _deactivate_job(job_id: int) -> None:
    try:
        from core import registration_debug

        final_job = db.get_job(int(job_id)) or {}
        registration_debug.deactivate_for_job(
            getattr(_THREAD_CTX, "debug_token", None),
            status=str(final_job.get("status") or ""),
        )
    except Exception:
        logger.exception("[Job %s] 收口注册调试记录器失败", job_id)
    with _STOP_LOCK:
        _STOP_EVENTS.pop(int(job_id), None)
        _ACTIVE_JOBS.discard(int(job_id))
    try:
        delattr(_THREAD_CTX, "job_id")
    except Exception:
        pass
    try:
        delattr(_THREAD_CTX, "debug_token")
    except Exception:
        pass
    try:
        from core import sms_provider

        sms_provider.clear_sms_batch_context()
    except Exception:
        pass


def is_stop_requested(job_id: int | None = None) -> bool:
    if job_id is None:
        job_id = getattr(_THREAD_CTX, "job_id", None)
    if not job_id:
        return False
    with _STOP_LOCK:
        ev = _STOP_EVENTS.get(int(job_id))
        if ev and ev.is_set():
            return True
    job = db.get_job(int(job_id))
    return bool(job and job.get("status") in ("stopping", "stopped", "cancelled"))


def check_stop_requested() -> None:
    job_id = getattr(_THREAD_CTX, "job_id", None)
    if is_stop_requested(job_id):
        raise StopRequested(f"任务 #{job_id} 已被用户手动停止")


def report_job_progress(stage: str, state: str = "running", detail: str | None = None) -> None:
    """注册驱动调用的轻量进度上报；CLI 场景没有 job_id 时自动忽略。"""
    job_id = getattr(_THREAD_CTX, "job_id", None)
    if not job_id:
        return
    try:
        from core import registration_debug

        registration_debug.update_current_stage(stage, state=state, detail=detail)
    except Exception:
        logger.exception("[Job %s] 写入调试阶段标记失败: stage=%s state=%s", job_id, stage, state)
    try:
        db.update_job_progress(int(job_id), stage, state=state, detail=detail)
    except Exception:
        logger.exception("[Job %s] 写入进度失败: stage=%s state=%s", job_id, stage, state)


def report_registered_account(account_id: int) -> None:
    """注册主体一旦落库，立即把账号绑定到当前任务。

    2FA、Codex 或 WebUI 进程随后中断时，启动恢复逻辑仍能定位并保留这个账号。
    CLI 场景没有 job_id 时自动忽略。
    """
    job_id = getattr(_THREAD_CTX, "job_id", None)
    if not job_id:
        return
    try:
        db.update_job(int(job_id), account_id=int(account_id))
    except Exception:
        logger.exception("[Job %s] 绑定注册账号失败: account_id=%s", job_id, account_id)


def _append_job_log(job_id: int, message: str) -> None:
    try:
        job = db.get_job(job_id)
        log_file = job.get("log_file") if job else None
        if not log_file:
            return
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%H:%M:%S")
        with Path(log_file).open("a", encoding="utf-8") as f:
            f.write(f"{ts} [WARNING] [manual-stop] {message}\n")
    except Exception:
        pass


def _random_display_name() -> str:
    """生成符合 OpenAI 限制的英文字母显示名。"""
    from core.name_samples import random_display_name

    return random_display_name()


def _prepare_registration_args(email_source: str | None = None) -> tuple[str, str, str]:
    """复用 CLI 的默认规则，为旧 Web 任务入口补齐注册参数。"""
    # 用模块属性读，支持 WebUI 热加载
    from config import register as _r, email as _e
    from core.email_provider import acquire_email
    from core.profile_utils import generate_random_birthday

    email = str(getattr(_r, "REGISTER_EMAIL", "") or "").strip()
    name = str(getattr(_r, "REGISTER_NAME", "") or "").strip()
    # WebUI/配置里有时会把空值存成 "-"，这不是合法 OpenAI 显示名，按空处理并自动生成
    if name in {"-", "—", "无", "空", "none", "None", "null", "NULL"}:
        name = ""

    if not name:
        # 手动模式也自动生成显示名，减少配置负担
        name = _random_display_name()

    birthday = generate_random_birthday()

    # 邮箱领取会把池状态置为 used，因此放在所有其他准备逻辑之后。
    if not email:
        if _e.USE_EMAIL_SERVICE:
            email = acquire_email(email_source)
        else:
            raise RuntimeError(
                "手动模式未配置邮箱。请在 WebUI 配置页设置 REGISTER_EMAIL，"
                "或开启 USE_EMAIL_SERVICE 并从邮箱池领取。"
            )

    return email, name, birthday


def _release_unconsumed_job_email(email: str | None, reason: str) -> None:
    """任务失败兜底：只回收尚未生成账号、仍处于 used 的邮箱领取。"""
    if not email:
        return
    try:
        from core.email_provider import release_email_if_unconsumed

        release_email_if_unconsumed(email, note=f"任务未消耗，已自动回收: {reason[:180]}")
    except Exception:
        logger.exception("[Service] 回收未消耗邮箱失败: %s", email)


def _is_final_session_access_token_timeout(error: object) -> bool:
    """
    识别注册最后一步已经返回 /api/auth/session 200 但没有 accessToken 的失败。
    这种邮箱后续继续注册通常会卡在同一状态，按要求直接停用邮箱池条目。
    """
    text = str(error or "")
    if not text:
        return False
    return (
        "等待 /api/auth/session accessToken 超时" in text
        and "WARNING_BANNER" in text
        and "'_http_status': 200" in text
    )


def _should_disable_failed_registration_email(error: object) -> bool:
    """需要直接停用邮箱的注册失败类型。"""
    text = str(error or "")
    if not text:
        return False
    return (
        _is_final_session_access_token_timeout(text)
        or "邮箱提交后进入登录密码页" in text
        or "auth.openai.com/log-in/password" in text
        or "/log-in/password" in text
    )


def _disable_job_email(email: str | None, reason: str) -> bool:
    """把本次任务邮箱停用，避免后续再次领取。"""
    if not email:
        return False
    try:
        from core.email_provider import release_email

        source = release_email(email, status="disabled", note=f"自动停用: {reason[:180]}")
        logger.warning("[Service] 已自动停用邮箱: source=%s email=%s reason=%s", source, email, reason[:220])
        return True
    except Exception:
        logger.exception("[Service] 自动停用邮箱失败: %s", email)
        return False


def _mark_completed_resume_email(email: str | None, account_id: int | None) -> bool:
    """恢复任务成功后把曾被失败分支标记的邮箱重新收口为已使用。"""
    if not email:
        return False
    try:
        from core.email_provider import release_email

        source = release_email(
            email,
            status="used",
            note=f"继续注册已完成，已绑定账号 #{account_id or '-'}",
        )
        logger.info("[Service] 已收口恢复账号邮箱: source=%s account_id=%s", source, account_id)
        return True
    except Exception:
        logger.exception("[Service] 收口恢复账号邮箱失败: account_id=%s", account_id)
        return False


def _registration_proxy_retry_limit() -> int:
    """读取注册换线重试次数；只允许有限次数，避免任务无限占用线程。"""
    try:
        from config import proxy as proxy_config

        value = int(getattr(proxy_config, "REGISTRATION_PROXY_RETRIES", 2) or 0)
    except (TypeError, ValueError, ImportError):
        value = 2
    return max(0, min(3, value))


def _registration_proxy_retry_delay() -> float:
    try:
        from config import proxy as proxy_config

        value = float(getattr(proxy_config, "REGISTRATION_PROXY_RETRY_DELAY", 1.0) or 0)
    except (TypeError, ValueError, ImportError):
        value = 1.0
    return max(0.0, min(10.0, value))


def _is_transient_registration_proxy_error(error: object) -> bool:
    """只识别线路级瞬时错误，不把页面状态错误伪装成可重试。"""
    text = str(error or "").lower()
    if not text:
        return False
    markers = (
        "err_tunnel_connection_failed",
        "err_proxy_connection_failed",
        "err_connection_reset",
        "err_connection_closed",
        "err_timed_out",
        "proxy connection",
        "ssl_error_syscall",
        "unexpected eof while reading",
        "remote end closed connection",
        "connection aborted",
        "chrome-error://chromewebdata/",
    )
    return any(marker in text for marker in markers) or "邮箱提交/认证跳转超过总预算" in str(error or "")


def _should_retry_registration_with_new_proxy(
    result: object,
    proxy_lease: object,
    retry_attempt: int,
) -> bool:
    """决定是否释放当前线路并用新线路重新执行整段浏览器注册。"""
    if retry_attempt >= _registration_proxy_retry_limit():
        return False
    if not isinstance(result, dict):
        return False
    # 已落库的账号、待邮箱验证检查点或 access token 都不能再从头注册。
    if result.get("account_id") is not None or result.get("registration_pending"):
        return False
    if str(result.get("access_token") or "").strip():
        return False
    if str(getattr(proxy_lease, "provider", "") or "").strip().lower() != "1024proxy":
        return False
    return _is_transient_registration_proxy_error(result.get("error"))


def _normalize_workers(max_workers: int | None) -> int:
    if max_workers is None:
        return _DEFAULT_MAX_WORKERS
    try:
        value = int(max_workers)
    except (TypeError, ValueError):
        value = _DEFAULT_MAX_WORKERS
    return max(_MIN_MAX_WORKERS, min(_MAX_MAX_WORKERS, value))


def get_executor(max_workers: int | None = None) -> ThreadPoolExecutor:
    """返回注册线程池。

    旧逻辑只在首次创建线程池时使用 max_workers，后续 WebUI 改线程数再提交仍会复用
    上一次的池。这里改成：每次传入的 max_workers 和当前池不一致时，立即创建新池供
    新提交任务使用；旧池不接收新任务，但会继续把已经排队/运行的任务跑完。
    """
    global _executor, _executor_workers, _executor_generation
    requested_workers = _normalize_workers(max_workers) if max_workers is not None else _executor_workers
    with _executor_lock:
        if _executor is None or requested_workers != _executor_workers:
            old_executor = _executor
            if old_executor is not None:
                # 不取消旧池里已提交的任务，只是不再往旧池追加新任务。
                old_executor.shutdown(wait=False, cancel_futures=False)
                _retired_executors.append(old_executor)
                logger.info(
                    "[Service] 注册线程池 workers 从 %s 切换为 %s；旧池继续处理已排队任务",
                    _executor_workers,
                    requested_workers,
                )
            _executor_workers = requested_workers
            _executor_generation += 1
            _executor = ThreadPoolExecutor(
                max_workers=requested_workers,
                thread_name_prefix=f"reg-worker-{_executor_generation}",
            )
    return _executor


def get_executor_workers() -> int:
    """当前新提交注册任务会使用的线程数。"""
    with _executor_lock:
        return _executor_workers


def shutdown_executor(wait: bool = True) -> None:
    global _executor
    with _executor_lock:
        executors = []
        if _executor is not None:
            executors.append(_executor)
            _executor = None
        executors.extend(_retired_executors)
        _retired_executors.clear()
    for ex in executors:
        ex.shutdown(wait=wait, cancel_futures=False)


# ============================================================
# 单任务执行：日志重定向到任务专属文件
# ============================================================

class _JobLogContext:
    """让本线程的根 logger 多一个 FileHandler，结束后移除。"""

    def __init__(self, log_path: str):
        self.log_path = log_path
        self.handler: logging.FileHandler | None = None

    def __enter__(self):
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
        self.handler = logging.FileHandler(self.log_path, encoding="utf-8")
        self.handler.setLevel(logging.INFO)
        self.handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        # 仅给本线程过滤 —— 用 thread name 做区分，避免污染其他任务的日志
        thread_name = threading.current_thread().name
        self.handler.addFilter(lambda r: r.threadName == thread_name)
        logging.getLogger().addHandler(self.handler)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handler is not None:
            self.handler.close()
            logging.getLogger().removeHandler(self.handler)


def _run_one_job(job_id: int, log_file: str) -> None:
    """单任务入口（线程池里跑这个）。"""
    log_logger = logging.getLogger(__name__)
    _activate_job(job_id)

    # 取消检查：用户可能在任务排队期间点了"取消排队"，把 status 改成了 cancelled。
    # 因为 Future 已经 submit 进线程池无法撤回，只能在真正执行前自检一下，跳过 cancelled 的。
    try:
        current = db.get_job(job_id)
    except Exception:
        _deactivate_job(job_id)
        raise
    if not current:
        log_logger.info(f"[Job {job_id}] 任务记录已删除，跳过执行")
        _deactivate_job(job_id)
        return
    batch_id = str(current.get("batch_id") or "").strip()
    try:
        batch_size = max(1, int(current.get("batch_size") or 1))
    except (TypeError, ValueError):
        batch_size = 1
    try:
        batch_workers = max(1, int(current.get("batch_workers") or 1))
    except (TypeError, ValueError):
        batch_workers = 1
    if current.get("status") == "cancelled":
        log_logger.info(f"[Job {job_id}] 已被用户取消，跳过执行")
        if batch_id and batch_size > 1:
            try:
                from core.proxy_provider import finalize_registration_proxy_batch

                finalize_registration_proxy_batch(batch_id)
            except Exception:
                logger.exception("[Job %s] 收口已取消注册批次失败", job_id)
        _deactivate_job(job_id)
        return

    try:
        claimed = db.claim_job_for_execution(
            job_id,
            started_at=datetime.now().isoformat(timespec="seconds"),
        )
    except Exception:
        _deactivate_job(job_id)
        raise
    if not claimed:
        # 停止/取消可能发生在工作线程刚从线程池取出任务、尚未开始执行的窗口。
        # 条件抢占失败表示数据库状态已经被控制接口改变，不能再把它启动回来。
        latest = db.get_job(job_id) or {}
        if latest.get("status") == "stopping":
            db.transition_job_status(
                job_id,
                ("stopping",),
                "stopped",
                completed_at=datetime.now().isoformat(timespec="seconds"),
                error="用户手动停止",
            )
        _deactivate_job(job_id)
        return
    db.update_job_progress(job_id, "email", state="running", detail="正在准备代理并领取邮箱")

    email: str | None = None
    proxy_lease = None
    try:
        with _JobLogContext(log_file):
            from core.registration.dispatcher import run_registration
            from core.proxy_provider import acquire_registration_proxy, mask_endpoint, mask_ip, release_proxy

            def _bind_proxy_lease(lease) -> None:
                db.update_job(
                    job_id,
                    proxy_provider=lease.provider,
                    proxy_status="leased",
                    proxy_endpoint=mask_endpoint(lease.endpoint),
                    proxy_exit_ip=mask_ip(lease.exit_ip) or "-",
                    proxy_region=lease.region or "-",
                    proxy_acquired_at=lease.acquired_at.isoformat(timespec="seconds"),
                    proxy_expires_at=lease.expires_at.isoformat(timespec="seconds") if lease.expires_at else "-",
                )

            log_logger.info(f"[Job {job_id}] 开始注册任务")
            db.update_job(job_id, proxy_status="acquiring")
            proxy_lease = acquire_registration_proxy(
                job_id=job_id,
                batch_id=batch_id if batch_size > 1 else None,
                batch_size=batch_size,
                batch_workers=batch_workers,
                progress_callback=lambda detail: db.update_job_progress(
                    job_id,
                    "email",
                    state="running",
                    detail=detail,
                ),
            )
            _bind_proxy_lease(proxy_lease)
            selected_source = str(current.get("email_source") or "").strip()
            try:
                from core.email_provider import validate_email_source
                selected_source = validate_email_source(selected_source)
            except ValueError:
                # 兼容改造前已经存在的多来源历史任务；新任务 API 不再允许这种值。
                from core.email_provider import parse_email_sources
                selected_source = parse_email_sources(selected_source)[0]
            existing_password = ""
            existing_totp_secret = ""
            if str(current.get("job_type") or "") == "registration_resume":
                resume_account = _account_for_job(current)
                email = str((resume_account or {}).get("email") or current.get("email") or "").strip()
                existing_password = _pending_registration_password(resume_account)
                existing_totp_secret = str((resume_account or {}).get("totp_secret") or "").strip()
                if not email or not existing_password:
                    raise RuntimeError("待邮箱验证账号缺少邮箱或已保存账号密码，无法继续验证")
                from core.profile_utils import generate_random_birthday

                name = _random_display_name()
                birthday = generate_random_birthday()
                db.update_job_progress(
                    job_id,
                    "email",
                    state="success",
                    detail="已复用待邮箱验证账号和保存的账号密码",
                )
                log_logger.info("[Job %s] 继续验证已保存账号：account_id=%s", job_id, (resume_account or {}).get("id"))
            else:
                email, name, birthday = _prepare_registration_args(selected_source)
            db.update_job(job_id, email=email)
            if not existing_password:
                db.update_job_progress(job_id, "email", state="success", detail=f"已从 {selected_source} 领取邮箱")
            check_stop_requested()
            retry_attempt = 0
            while True:
                check_stop_requested()
                result = run_registration(
                    email=email,
                    name=name,
                    birthday=birthday,
                    proxy=proxy_lease.proxy_url,
                    existing_password=existing_password or None,
                    existing_totp_secret=existing_totp_secret or None,
                )
                if not _should_retry_registration_with_new_proxy(result, proxy_lease, retry_attempt):
                    break

                retry_attempt += 1
                retry_error = str((result or {}).get("error") or "代理线路瞬时失败")[:220]
                log_logger.warning(
                    "[Job %s] 注册遇到代理瞬时错误，释放旧线路并换线重试 (%s/%s): %s",
                    job_id,
                    retry_attempt,
                    _registration_proxy_retry_limit(),
                    retry_error,
                )
                release_proxy(proxy_lease, reason=f"registration_proxy_retry_{retry_attempt}")
                proxy_lease = None
                db.update_job(
                    job_id,
                    proxy_status="acquiring",
                    error=f"代理线路瞬时失败，准备换线重试: {retry_error}",
                )
                db.update_job_progress(
                    job_id,
                    "auth_redirect",
                    state="running",
                    detail=f"认证线路瞬时失败，正在更换代理重试 ({retry_attempt}/{_registration_proxy_retry_limit()})",
                )
                retry_delay = _registration_proxy_retry_delay()
                if retry_delay:
                    time.sleep(retry_delay)
                check_stop_requested()
                proxy_lease = acquire_registration_proxy(
                    job_id=job_id,
                    # 批次首轮租约已经释放；重试必须单独申请新线路，不能消耗批次剩余槽位。
                    batch_id=None,
                    batch_size=1,
                    batch_workers=1,
                    progress_callback=lambda detail: db.update_job_progress(
                        job_id,
                        "auth_redirect",
                        state="running",
                        detail=detail,
                    ),
                )
                _bind_proxy_lease(proxy_lease)
                if not existing_password:
                    # Roxy 失败后会把未建号邮箱释放回池；重试不能继续持有已释放的
                    # 字符串，否则可能被另一个并发任务抢走。仍使用同一个已选来源，
                    # 不引入第二邮箱供应商或兜底来源。
                    email, name, birthday = _prepare_registration_args(selected_source)
                    db.update_job(job_id, email=email)
                    db.update_job_progress(
                        job_id,
                        "email",
                        state="success",
                        detail=f"换线重试已从 {selected_source} 重新领取邮箱",
                    )
            # Codex 失败时注册账号可能已经创建并保存。代理地区属于账号注册事实，
            # 不能只在整项任务 success 时落库，否则后续补跑/查套餐无法稳定沿用地区。
            if isinstance(result, dict) and result.get("account_id"):
                db.update_account_registration_proxy(
                    int(result.get("account_id")),
                    provider=proxy_lease.provider,
                    region=proxy_lease.region,
                )
            if is_stop_requested(job_id):
                # run_registration 正常返回前，各注册驱动已经完成邮箱状态收口。
                # 这里不能再次释放：失败邮箱可能已经被下一任务重新领取，二次释放
                # 会把别的线程正在使用的租约错误改回 available。
                db.finish_job_progress(job_id, success=False, detail="用户手动停止", failure_state="stopped")
                db.update_job(
                    job_id,
                    status="stopped",
                    error="用户手动停止",
                    completed_at=datetime.now().isoformat(timespec="seconds"),
                )
                log_logger.warning(f"[Job {job_id}] 已按用户请求停止")
                return
            result_is_dict = isinstance(result, dict)
            registration_succeeded = bool(
                result_is_dict
                and (
                    result.get("registration_success")
                    or result.get("success")
                    or result.get("account_id")
                )
            )
            partial_success = bool(
                registration_succeeded
                and (
                    result.get("partial_success")
                    or result.get("postprocess_success") is False
                    or not result.get("success")
                )
            )
            if registration_succeeded:
                warning = str(result.get("error") or "").strip()
                registration_pending = bool(
                    not result.get("success")
                    and result.get("account_id")
                    and (
                        result.get("registration_pending")
                        or not str(result.get("access_token") or "").strip()
                    )
                )
                if (
                    str(current.get("job_type") or "") == "registration_resume"
                    and not registration_pending
                ):
                    _mark_completed_resume_email(
                        str(result.get("email") or email or "").strip(),
                        int(result.get("account_id")) if result.get("account_id") else None,
                    )
                if registration_pending:
                    # 密码已经保存只能说明账号进入了“待邮箱验证”，不能把当前
                    # 验证码节点及后续未执行节点涂成绿色。先保留真实失败节点，
                    # finish_job_progress 再把从未上报的后续节点收口为 skipped。
                    progress = db.get_job(job_id) or {}
                    failed_stage = str(progress.get("progress_stage") or "email_otp")
                    if failed_stage not in {key for key, _label in db.JOB_PROGRESS_STAGES} or failed_stage == "complete":
                        failed_stage = "email_otp"
                    db.update_job_progress(
                        job_id,
                        failed_stage,
                        state="failed",
                        detail=(warning or "账号已保存，邮箱验证尚未完成")[:300],
                    )
                db.finish_job_progress(job_id, success=True)
                final_status = "partial_success" if partial_success else "success"
                db.update_job(
                    job_id,
                    status=final_status,
                    email=result.get("email"),
                    account_id=result.get("account_id"),
                    error=warning[:500] if warning else None,
                    completed_at=datetime.now().isoformat(timespec="seconds"),
                )
                if partial_success:
                    log_logger.warning(
                        "[Job %s] 注册主体成功，后置步骤部分未完成: %s",
                        job_id,
                        warning or "请查看 Codex/2FA 子步骤",
                    )
                else:
                    log_logger.info(f"[Job {job_id}] 成功: {result.get('email')}")
            else:
                # 注意：失败也可能伴随 account_id（如 Codex 失败但账号已注册成功）
                err = (result or {}).get("error") if isinstance(result, dict) else "unknown"
                result_email = (result or {}).get("email") if isinstance(result, dict) else None
                try:
                    from core.registration_debug import capture_current_failure
                    capture_current_failure(str(err)[:1000])
                except Exception:
                    logger.exception("[Job %s] 保存失败诊断现场失败", job_id)
                db.finish_job_progress(job_id, success=False, detail=str(err)[:300])
                db.update_job(
                    job_id,
                    status="failed",
                    email=result_email,
                    account_id=(result or {}).get("account_id") if isinstance(result, dict) else None,
                    error=str(err)[:500],
                    completed_at=datetime.now().isoformat(timespec="seconds"),
                )
                email_to_handle = str(result_email or email or "").strip()
                if _should_disable_failed_registration_email(err):
                    _disable_job_email(email_to_handle, str(err))
                # 普通失败的邮箱已经由 run_registration/具体驱动释放。
                # 只有 run_registration 直接抛出、没有正常返回时，才由下面的
                # except 分支调用 _release_unconsumed_job_email 做服务层兜底。
                log_logger.error(f"[Job {job_id}] 失败: {err}")
    except StopRequested as exc:
        _release_unconsumed_job_email(email, str(exc))
        db.finish_job_progress(job_id, success=False, detail="用户手动停止", failure_state="stopped")
        log_logger.warning(f"[Job {job_id}] 已停止: {exc}")
        db.update_job(
            job_id,
            status="stopped",
            error="用户手动停止",
            completed_at=datetime.now().isoformat(timespec="seconds"),
        )
    except Exception as exc:
        err_text = f"{type(exc).__name__}: {exc}"
        try:
            from core.registration_debug import capture_current_failure
            capture_current_failure(err_text[:1000])
        except Exception:
            logger.exception("[Job %s] 保存失败诊断现场失败", job_id)
        if _should_disable_failed_registration_email(err_text):
            _disable_job_email(email, err_text)
        else:
            _release_unconsumed_job_email(email, err_text)
        if is_stop_requested(job_id):
            log_logger.warning(f"[Job {job_id}] 停止中捕获异常，按停止处理: {type(exc).__name__}: {exc}")
            db.finish_job_progress(job_id, success=False, detail="用户手动停止", failure_state="stopped")
            db.update_job(
                job_id,
                status="stopped",
                error="用户手动停止",
                completed_at=datetime.now().isoformat(timespec="seconds"),
            )
            return
        log_logger.exception(f"[Job {job_id}] 异常")
        db.finish_job_progress(job_id, success=False, detail=err_text[:300])
        db.update_job(
            job_id,
            status="failed",
            proxy_status="failed" if proxy_lease is None else "leased",
            error=f"{type(exc).__name__}: {exc}"[:500],
            completed_at=datetime.now().isoformat(timespec="seconds"),
        )
    finally:
        if proxy_lease is not None:
            try:
                from core.proxy_provider import release_proxy

                final_job = db.get_job(job_id) or {}
                release_proxy(proxy_lease, reason=str(final_job.get("status") or "completed"))
                db.update_job(job_id, proxy_status="released")
            except Exception:
                logger.exception("[Job %s] 释放代理租约失败", job_id)
        if batch_id and batch_size > 1:
            try:
                from core.proxy_provider import finalize_registration_proxy_batch

                finalize_registration_proxy_batch(batch_id)
            except Exception:
                logger.exception("[Job %s] 收口注册代理批次失败", job_id)
        _deactivate_job(job_id)


def _run_codex_retry_job(
    job_id: int,
    log_file: str,
    email: str,
    account_id: int,
    account_task_id: int | None = None,
) -> None:
    """把 Codex 补跑作为标准任务执行，并复用任务状态、日志和停止入口。"""
    _activate_job(job_id)
    try:
        current = db.get_job(job_id)
    except Exception:
        _deactivate_job(job_id)
        raise
    if not current or current.get("status") == "cancelled":
        account_task_store.finish_task(
            account_task_id,
            status="cancelled",
            message="注册重试任务已取消，Codex 补跑未执行",
        )
        codex_retry_service.release(email)
        _deactivate_job(job_id)
        return

    try:
        claimed = db.claim_job_for_execution(
            job_id,
            started_at=datetime.now().isoformat(timespec="seconds"),
        )
    except Exception:
        _deactivate_job(job_id)
        raise
    if not claimed:
        latest = db.get_job(job_id) or {}
        if latest.get("status") == "stopping":
            db.transition_job_status(
                job_id,
                ("stopping",),
                "stopped",
                completed_at=datetime.now().isoformat(timespec="seconds"),
                error="用户手动停止",
            )
        account_task_store.finish_task(
            account_task_id,
            status="cancelled",
            message="注册重试任务未启动，已取消",
        )
        codex_retry_service.release(email)
        _deactivate_job(job_id)
        return
    for stage, _label in db.JOB_PROGRESS_STAGES:
        if stage not in {"codex", "complete"}:
            db.update_job_progress(job_id, stage, state="skipped", detail="Codex 补跑任务")
    db.update_job_progress(job_id, "codex", state="running", detail="正在补跑 Codex 授权")
    try:
        result = codex_retry_service.run_worker(
            email,
            clear_log=False,
            target_log_path=log_file,
            task_id=account_task_id,
            task_trigger="registration_job_retry",
        )
        now_iso = datetime.now().isoformat(timespec="seconds")
        proxy_fields = {}
        if result.get("proxy_provider"):
            proxy_fields = {
                "proxy_provider": result.get("proxy_provider"),
                "proxy_region": result.get("proxy_region") or "-",
                "proxy_status": "released",
            }
        if is_stop_requested(job_id) or result.get("status") == "stopped":
            db.finish_job_progress(job_id, success=False, detail=str(result.get("message") or "用户手动停止")[:300], failure_state="stopped")
            db.update_job(job_id, status="stopped", email=email, account_id=account_id, error=str(result.get("message") or "用户手动停止")[:500], completed_at=now_iso, **proxy_fields)
        elif result.get("ok"):
            db.finish_job_progress(job_id, success=True)
            db.update_job(
                job_id,
                status="success",
                email=email,
                account_id=account_id,
                completed_at=now_iso,
                **proxy_fields,
            )
        else:
            db.finish_job_progress(job_id, success=False, detail=str(result.get("message") or "Codex 补跑失败")[:300])
            db.update_job(
                job_id,
                status="failed",
                email=email,
                account_id=account_id,
                error=str(result.get("message") or "Codex 补跑失败")[:500],
                completed_at=now_iso,
                **proxy_fields,
            )
    except Exception as exc:
        db.finish_job_progress(job_id, success=False, detail=f"{type(exc).__name__}: {exc}"[:300])
        db.update_job(
            job_id,
            status="failed",
            error=f"{type(exc).__name__}: {exc}"[:500],
            completed_at=datetime.now().isoformat(timespec="seconds"),
        )
        codex_retry_service.release(email)
        logger.exception("[Job %s] Codex 补跑异常", job_id)
    finally:
        _deactivate_job(job_id)


def _run_twofa_retry_job(
    job_id: int,
    log_file: str,
    email: str,
    account_id: int,
    account_task_id: int | None = None,
) -> None:
    """把账号配置检查/补齐作为标准注册重试任务执行。"""
    _activate_job(job_id)
    try:
        current = db.get_job(job_id)
    except Exception:
        _deactivate_job(job_id)
        raise
    if not current or current.get("status") == "cancelled":
        account_task_store.finish_task(
            account_task_id,
            status="cancelled",
            message="注册重试任务已取消，账号配置重试未执行",
        )
        codex_retry_service.release(email)
        _deactivate_job(job_id)
        return

    try:
        claimed = db.claim_job_for_execution(
            job_id,
            started_at=datetime.now().isoformat(timespec="seconds"),
        )
    except Exception:
        _deactivate_job(job_id)
        raise
    if not claimed:
        latest = db.get_job(job_id) or {}
        if latest.get("status") == "stopping":
            db.transition_job_status(
                job_id,
                ("stopping",),
                "stopped",
                completed_at=datetime.now().isoformat(timespec="seconds"),
                error="用户手动停止",
            )
        account_task_store.finish_task(
            account_task_id,
            status="cancelled",
            message="注册重试任务未启动，已取消",
        )
        codex_retry_service.release(email)
        _deactivate_job(job_id)
        return
    for stage, _label in db.JOB_PROGRESS_STAGES:
        if stage not in {"twofa", "complete"}:
            db.update_job_progress(job_id, stage, state="skipped", detail="账号配置重试任务")
    db.update_job_progress(job_id, "twofa", state="running", detail="正在补齐账号密码、套餐和 Authenticator 2FA")
    try:
        result = codex_retry_service.run_twofa_worker(
            email,
            clear_log=False,
            target_log_path=log_file,
            task_id=account_task_id,
            task_trigger="registration_job_retry",
        )
        now_iso = datetime.now().isoformat(timespec="seconds")
        proxy_fields = {}
        if result.get("proxy_provider"):
            proxy_fields = {
                "proxy_provider": result.get("proxy_provider"),
                "proxy_region": result.get("proxy_region") or "-",
                "proxy_status": "released",
            }
        if is_stop_requested(job_id) or result.get("status") == "stopped":
            db.finish_job_progress(job_id, success=False, detail=str(result.get("message") or "用户手动停止")[:300], failure_state="stopped")
            db.update_job(job_id, status="stopped", email=email, account_id=account_id, error=str(result.get("message") or "用户手动停止")[:500], completed_at=now_iso, **proxy_fields)
        elif result.get("ok"):
            db.update_job_progress(job_id, "twofa", state="success", detail="账号密码、套餐和 Authenticator 2FA 已确认")
            db.finish_job_progress(job_id, success=True)
            db.update_job(job_id, status="success", email=email, account_id=account_id, completed_at=now_iso, **proxy_fields)
        else:
            db.update_job_progress(job_id, "twofa", state="failed", detail=str(result.get("message") or "账号配置重试失败")[:300])
            db.finish_job_progress(job_id, success=False, detail=str(result.get("message") or "账号配置重试失败")[:300])
            db.update_job(job_id, status="failed", email=email, account_id=account_id, error=str(result.get("message") or "账号配置重试失败")[:500], completed_at=now_iso, **proxy_fields)
    except Exception as exc:
        db.update_job_progress(job_id, "twofa", state="failed", detail=f"{type(exc).__name__}: {exc}"[:300])
        db.finish_job_progress(job_id, success=False, detail=f"{type(exc).__name__}: {exc}"[:300])
        db.update_job(
            job_id,
            status="failed",
            error=f"{type(exc).__name__}: {exc}"[:500],
            completed_at=datetime.now().isoformat(timespec="seconds"),
        )
        codex_retry_service.release(email)
        logger.exception("[Job %s] 账号配置重试异常", job_id)
    finally:
        _deactivate_job(job_id)


# ============================================================
# 公共接口
# ============================================================

def submit_registration(
    count: int = 1,
    email_source: str | None = None,
    workers: int | None = None,
    *,
    debug_enabled: bool = False,
) -> list[dict]:
    """
    创建 N 个注册任务并提交到线程池。
    email_source 会写入每个任务，任务执行时严格使用该来源，不跨平台兜底。

    Returns:
        N 个新创建的 job dict
    """
    if email_source is None:
        from config import email as _email_cfg
        from core.email_provider import parse_email_sources
        email_source = parse_email_sources(_email_cfg.EMAIL_SOURCE)[0]
    from core.email_provider import validate_email_source
    email_source = validate_email_source(email_source)

    # 创建/切换线程池和提交本批任务必须整体串行化：否则另一请求在本批提交中途
    # 切换 workers 并 shutdown 旧池，会导致后续 submit 报 cannot schedule new futures after shutdown。
    with _executor_lock:
        executor = get_executor(max_workers=workers)
        effective_workers = get_executor_workers()
        batch_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        jobs = []
        for index in range(count):
            job = db.create_job(
                email_source=email_source,
                batch_id=batch_id,
                batch_index=index + 1,
                batch_size=count,
                batch_workers=effective_workers,
            )
            if debug_enabled:
                from core.registration_debug import patch_job
                patch_job(
                    int(job["id"]),
                    debug_enabled=True,
                    debug_state="pending",
                    debug_policy={
                        "capture_network": True,
                        "hold_on_failure": True,
                        "preserve_success_browser": False,
                    },
                )
                job = db.get_job(int(job["id"])) or job
            try:
                executor.submit(_run_one_job, job["id"], job["log_file"])
            except Exception as exc:
                db.update_job(
                    int(job["id"]),
                    status="failed",
                    error=f"队列提交失败：{type(exc).__name__}: {exc}"[:500],
                    completed_at=datetime.now().isoformat(timespec="seconds"),
                )
                logger.exception("[Service] 注册任务 #%s 提交线程池失败", job["id"])
            jobs.append(db.get_job(int(job["id"])) or job)
    logger.info(
        "[Service] 已提交 %s 个注册任务，源=%s，workers=%s，debug=%s",
        count,
        email_source,
        effective_workers,
        bool(debug_enabled),
    )
    return jobs


def _account_for_job(job: dict) -> dict | None:
    account_id = job.get("account_id")
    if account_id is not None:
        try:
            account = db.get_account(int(account_id))
            if account is not None:
                return account
        except (TypeError, ValueError):
            pass
    email = str(job.get("email") or "").strip()
    return db.get_account_by_email(email) if email else None


def _account_extra(account: dict | None) -> dict:
    if not account:
        return {}
    raw = account.get("extra_json") or {}
    if isinstance(raw, str):
        try:
            import json

            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = {}
    return dict(raw) if isinstance(raw, dict) else {}


def _pending_registration_password(account: dict | None) -> str:
    extra = _account_extra(account)
    if str(extra.get("registration_checkpoint") or "").strip() != "email_verification_pending":
        return ""
    if str((account or {}).get("access_token") or "").strip():
        return ""
    return str(
        extra.get("account_password")
        or extra.get("registration_password")
        or extra.get("login_password")
        or ""
    ).strip()


def _account_login_password(account: dict | None) -> str:
    """读取账号当前密码；旧账号兼容历史字段。"""
    extra = _account_extra(account)
    return str(
        extra.get("account_password")
        or extra.get("login_password")
        or extra.get("registration_password")
        or ""
    ).strip()


def _account_twofa_ready(account: dict | None, twofa_failed: bool = False) -> bool:
    if twofa_failed or not account or not str(account.get("totp_secret") or "").strip():
        return False
    extra = _account_extra(account)
    return not bool(extra.get("totp_setup_pending"))


def _account_plan_ready(account: dict | None) -> bool:
    return bool(account and str(account.get("plan_check_status") or "").strip().lower() == "success")


def _build_retry_info(
    job: dict,
    *,
    account: dict | None,
    successful_retry: dict | None,
) -> dict:
    """纯函数版本的任务重试投影；列表页可批量准备关联数据后复用。"""
    status = str(job.get("status") or "")
    info = {
        "retryable": False,
        "retry_action": None,
        "retry_label": None,
        "retry_reason": None,
        "display_status": status,
    }
    if status not in ("success", "failed", "partial_success", "stopped", "cancelled"):
        return info

    if successful_retry is not None:
        info["retry_reason"] = f"后续重试任务 #{successful_retry.get('id')} 已成功"
        info["successful_retry_job_id"] = successful_retry.get("id")
        return info

    if status == "success" and account is None:
        return info
    pending_password = _pending_registration_password(account)
    if account and pending_password:
        info.update({
            "display_status": "partial_success",
            "retryable": True,
            "retry_action": "registration_resume",
            "retry_label": "继续邮箱验证",
            "retry_reason": "OpenAI 密码已创建并保存在本地，继续登录同一账号完成邮箱验证",
        })
        return info

    steps = job.get("progress_steps") if isinstance(job.get("progress_steps"), dict) else {}
    twofa_step = steps.get("twofa") if isinstance(steps.get("twofa"), dict) else {}
    twofa_failed = str(twofa_step.get("state") or "") == "failed"
    if not twofa_failed and account:
        try:
            import json

            extra = json.loads(str(account.get("extra_json") or "{}"))
            twofa = extra.get("twofa") if isinstance(extra, dict) else None
            twofa_failed = isinstance(twofa, dict) and str(twofa.get("status") or "") == "failed"
        except Exception:
            pass

    setup_missing = bool(account) and (
        not _account_login_password(account)
        or not _account_plan_ready(account)
        or not _account_twofa_ready(account, twofa_failed)
    )

    if account and job.get("account_id") is not None:
        info["display_status"] = (
            "success"
            if (account.get("codex_status") or "") == "success" and not setup_missing
            else "partial_success"
        )

    if account:
        codex_status = str(account.get("codex_status") or "")
        if codex_status == "deactivated":
            info["retry_reason"] = "账号已废号，不能补跑 Codex"
            return info
        if codex_status == "success":
            if setup_missing:
                config_only = not twofa_failed and (
                    not _account_login_password(account)
                    or not _account_plan_ready(account)
                )
                info.update({
                    "retryable": True,
                    "retry_action": "twofa",
                    "retry_label": "补齐账号配置" if config_only else "重试 2FA",
                    "retry_reason": "账号和 Codex 已完成，重新登录补齐账号密码、套餐和 Authenticator 2FA",
                })
                return info
            info["retry_reason"] = "账号和 Codex 授权均已完成"
            return info
        info.update({
            "retryable": True,
            "retry_action": "codex",
            "retry_label": "补跑 Codex",
        })
        return info

    info.update({
        "retryable": True,
        "retry_action": "registration",
        "retry_label": "重试",
    })
    return info


def get_retry_info(job: dict) -> dict:
    """返回给 API/UI 的重试能力描述，不依赖前端猜测错误阶段。"""
    status = str(job.get("status") or "")
    if status not in ("success", "failed", "partial_success", "stopped", "cancelled"):
        return _build_retry_info(job, account=None, successful_retry=None)
    successful_retry = db.get_successful_retry_for_job(int(job.get("id") or 0))
    account = None if successful_retry is not None else _account_for_job(job)
    return _build_retry_info(
        job,
        account=account,
        successful_retry=successful_retry,
    )


def get_retry_info_bulk(jobs: list[dict]) -> dict[int, dict]:
    """批量生成列表重试信息，查询次数固定，不随当前页行数增长。"""
    rows = [dict(job) for job in (jobs or [])]
    terminal = [
        job for job in rows
        if str(job.get("status") or "") in ("success", "failed", "partial_success", "stopped", "cancelled")
    ]
    successful_by_job = db.get_successful_retries_for_jobs(terminal)
    needs_accounts = [job for job in terminal if int(job.get("id") or 0) not in successful_by_job]
    accounts_by_job = db.get_accounts_for_jobs(needs_accounts)
    return {
        int(job.get("id") or 0): _build_retry_info(
            job,
            account=accounts_by_job.get(int(job.get("id") or 0)),
            successful_retry=successful_by_job.get(int(job.get("id") or 0)),
        )
        for job in rows
    }


def retry_job(
    job_id: int,
    workers: int | None = None,
    *,
    batch_id: str | None = None,
    batch_index: int | None = None,
    batch_size: int | None = None,
) -> dict:
    """智能重试终态任务：未生成账号则重新注册，已有账号则仅补跑 Codex。"""
    source = db.get_job(job_id)
    if source is None:
        return {"ok": False, "error": "任务不存在", "status": 404}

    retry_info = get_retry_info(source)
    if not retry_info["retryable"]:
        reason = retry_info.get("retry_reason") or f"当前状态不支持重试：{source.get('status')}"
        return {"ok": False, "error": reason, "status": 409}

    action = str(retry_info["retry_action"])
    account = _account_for_job(source)
    email = str((account or {}).get("email") or source.get("email") or "").strip()
    account_id = int(account["id"]) if account and account.get("id") is not None else None
    if action == "codex":
        # 注册任务只提供父上下文；Codex 补跑本身由原生 operation run 执行，
        # 不再额外创建 registration_job + account_action_task 两份重复记录。
        from core import codex_operation_service, operation_task_store

        parent = operation_task_store.find_task_by_source("registration_jobs", str(job_id))
        queued = codex_operation_service.submit(
            email,
            trigger="registration_job_retry",
            parent_task_id=int(parent["id"]) if parent else None,
        )
        if not queued.get("accepted"):
            return {
                "ok": False,
                "error": queued.get("error") or "Codex 补跑入队失败",
                "status": 503 if queued.get("unavailable") else 409,
                **queued,
            }
        return {
            "ok": True,
            "created": True,
            "reused": False,
            "message": f"已创建 Codex 子任务 #{queued['task_id']}，attempt #{queued['run_id']}",
            "source_job_id": int(job_id),
            "retry_action": action,
            "operation_task_id": queued["task_id"],
            "run_id": queued["run_id"],
            "job": source,
        }
    reserved_account_action = False
    if action == "twofa":
        if not email or account_id is None:
            return {"ok": False, "error": "已保存账号信息不完整，无法执行账号补跑", "status": 409}
        if not codex_retry_service.reserve(email):
            return {"ok": False, "error": "该账号正在执行 Codex/2FA 补跑，请稍候", "status": 409}
        reserved_account_action = True

    try:
        job_type = {
            "codex": "codex_retry",
            "twofa": "twofa_retry",
            "registration_resume": "registration_resume",
        }.get(action, "registration")
        job, created = db.create_retry_job(
            int(job_id),
            job_type=job_type,
            email_source=str(source.get("email_source") or "outlook"),
            email=email if action in {"codex", "twofa", "registration_resume"} else None,
            account_id=account_id if action in {"codex", "twofa", "registration_resume"} else None,
            batch_id=batch_id,
            batch_index=batch_index,
            batch_size=batch_size,
            batch_workers=workers,
        )
    except LookupError as exc:
        if reserved_account_action:
            codex_retry_service.release(email)
        return {"ok": False, "error": str(exc), "status": 404}
    except ValueError as exc:
        if reserved_account_action:
            codex_retry_service.release(email)
        return {"ok": False, "error": str(exc), "status": 409}

    if not created:
        if reserved_account_action:
            codex_retry_service.release(email)
        return {
            "ok": True,
            "created": False,
            "reused": True,
            "message": f"已有重试任务 #{job['id']} 在排队或运行中",
            "source_job_id": int(job_id),
            "retry_action": action,
            "job": job,
        }

    if bool(source.get("debug_enabled", False)) and action in {"registration", "registration_resume"}:
        from core.registration_debug import patch_job
        patch_job(
            int(job["id"]),
            debug_enabled=True,
            debug_state="pending",
            debug_policy=dict(source.get("debug_policy") or {
                "capture_network": True,
                "hold_on_failure": True,
                "preserve_success_browser": False,
            }),
        )
        job = db.get_job(int(job["id"])) or job

    account_task_id = None
    try:
        if action in {"codex", "twofa"}:
            account_task_id = account_task_store.create_task(
                task_type="codex_retry" if action == "codex" else "twofa_retry",
                account_id=int(account_id),
                email=email,
                trigger="registration_job_retry",
            )
        if action == "codex":
            db.update_account_codex_status(email, "retrying", None)
        with _executor_lock:
            executor = get_executor(max_workers=workers)
            if action == "codex":
                executor.submit(
                    _run_codex_retry_job,
                    job["id"],
                    job["log_file"],
                    email,
                    int(account_id),
                    account_task_id,
                )
            elif action == "twofa":
                executor.submit(
                    _run_twofa_retry_job,
                    job["id"],
                    job["log_file"],
                    email,
                    int(account_id),
                    account_task_id,
                )
            else:
                executor.submit(_run_one_job, job["id"], job["log_file"])
    except Exception as exc:
        if reserved_account_action:
            codex_retry_service.release(email)
        if action == "codex":
            db.update_account_codex_status(email, "failed", f"队列提交失败：{type(exc).__name__}: {exc}"[:500])
        if account_task_id:
            account_task_store.finish_task(
                account_task_id,
                status="failed",
                message="账号补跑任务入队失败",
                error=f"{type(exc).__name__}: {exc}",
            )
        db.update_job(
            int(job["id"]),
            status="failed",
            error=f"队列提交失败：{type(exc).__name__}: {exc}"[:500],
            completed_at=datetime.now().isoformat(timespec="seconds"),
        )
        logger.exception("[Service] 重试任务 #%s 提交线程池失败", job["id"])
        return {"ok": False, "error": "重试任务创建成功，但提交执行失败", "status": 500, "job": db.get_job(int(job["id"]))}

    return {
        "ok": True,
        "created": True,
        "reused": False,
        "message": f"已创建重试任务 #{job['id']}（{ {'codex': 'Codex 补跑', 'twofa': '账号配置补跑', 'registration_resume': '继续邮箱验证'}.get(action, '完整注册') }）",
        "source_job_id": int(job_id),
        "retry_action": action,
        "job": job,
    }


def cancel_pending_jobs(*, batch_id: str | None = None) -> int:
    """
    把 status=pending 的任务批量改成 cancelled，避免它们被执行。
    如果传入 batch_id，只处理指定批次。
    已经在 running 的任务不动（线程池中无法中途打断）。
    返回成功取消的数量。
    """
    cancelled = db.cancel_pending_jobs(batch_id=batch_id)
    scope = f"批次 {batch_id}" if batch_id else "全部"
    logger.info("[Service] 已取消 %s 个排队任务（范围=%s）", cancelled, scope)
    return cancelled


def request_stop_job(job_id: int) -> dict:
    """手动停止单个注册任务。pending 直接取消；running 设置停止标记，运行线程会在检查点退出。"""
    job = db.get_job(job_id)
    if not job:
        return {"ok": False, "error": "任务不存在", "status": 404}
    status = job.get("status")
    now_iso = datetime.now().isoformat(timespec="seconds")
    if status == "pending":
        changed = db.transition_job_status(
            job_id,
            ("pending",),
            "cancelled",
            completed_at=now_iso,
            error_message="用户手动停止/取消排队",
        )
        if not changed:
            latest = db.get_job(job_id) or {}
            return request_stop_job(job_id) if latest.get("status") != status else {
                "ok": False,
                "error": "任务状态刚刚发生变化，请刷新后重试",
                "status": 409,
            }
        _append_job_log(job_id, "用户手动停止：任务尚未运行，已取消排队。")
        return {"ok": True, "message": "排队任务已取消", "job_id": job_id, "state": "cancelled"}
    if status in ("success", "partial_success", "failed", "cancelled", "stopped"):
        return {"ok": True, "message": f"任务已结束：{status}", "job_id": job_id, "state": status}
    if status in ("running", "stopping"):
        with _STOP_LOCK:
            active = int(job_id) in _ACTIVE_JOBS
            ev = _STOP_EVENTS.get(int(job_id)) if active else None
            if ev is not None:
                ev.set()
        if not active or ev is None:
            # Web 服务重启、线程异常退出、历史残留 stopping，或之前手动停止时只创建了 stop event
            # 但没有真实线程实例：直接落为 stopped，避免永远卡在“停止中”。
            with _STOP_LOCK:
                _STOP_EVENTS.pop(int(job_id), None)
                _ACTIVE_JOBS.discard(int(job_id))
            changed = db.transition_job_status(
                job_id,
                ("running", "stopping"),
                to_status="stopped",
                completed_at=now_iso,
                error_message="用户手动停止（任务实例不存在）",
            )
            if not changed:
                latest = db.get_job(job_id) or {}
                return {
                    "ok": True,
                    "message": f"任务已结束：{latest.get('status') or 'unknown'}",
                    "job_id": job_id,
                    "state": latest.get("status") or "unknown",
                }
            _release_unconsumed_job_email(
                str(job.get("email") or "").strip() or None,
                "任务实例不存在，确认未继续执行",
            )
            _append_job_log(job_id, "用户手动停止：未找到运行中的任务实例，已直接标记为已停止。")
            logger.warning("[Service] 用户停止任务 #%s：任务实例不存在，已直接标记 stopped", job_id)
            return {"ok": True, "message": "任务实例不存在，已直接标记为已停止", "job_id": job_id, "state": "stopped"}
        changed = db.transition_job_status(
            job_id,
            ("running",),
            "stopping",
            error_message="用户手动停止中",
        )
        if not changed:
            latest = db.get_job(job_id) or {}
            if latest.get("status") in ("stopping", "stopped"):
                return {
                    "ok": True,
                    "message": f"任务已{('停止中' if latest.get('status') == 'stopping' else '停止')}",
                    "job_id": job_id,
                    "state": latest.get("status"),
                }
            return {
                "ok": False,
                "error": f"任务状态刚刚变为：{latest.get('status') or '未知'}",
                "status": 409,
            }
        _append_job_log(job_id, "用户手动停止：已发送停止信号，任务会在当前步骤检查点退出。")
        logger.warning("[Service] 用户请求停止任务 #%s", job_id)
        return {"ok": True, "message": "已发送停止信号", "job_id": job_id, "state": "stopping"}
    return {"ok": False, "error": f"当前状态不支持停止：{status}", "status": 409}


def request_stop_batch(batch_id: str, *, cancel_pending: bool = False) -> dict:
    """在服务端一次处理整个注册批次，避免前端并发发出 N 个控制请求。"""
    batch_key = str(batch_id or "").strip()
    if not batch_key:
        return {"ok": False, "error": "批次 ID 为空", "status": 400}

    jobs = [
        row for row in db.list_jobs(limit=1000)
        if str(row.get("batch_id") or "").strip() == batch_key
    ]
    if not jobs:
        return {"ok": False, "error": "批次不存在", "status": 404}

    cancelled = cancel_pending_jobs(batch_id=batch_key) if cancel_pending else 0
    stopping = 0
    stopped = 0
    completed = 0
    for row in jobs:
        if row.get("status") not in ("running", "stopping"):
            continue
        result = request_stop_job(int(row["id"]))
        if result.get("state") == "stopping":
            stopping += 1
        elif result.get("state") == "stopped":
            stopped += 1
        elif result.get("state") in ("success", "failed", "cancelled", "partial_success"):
            completed += 1

    return {
        "ok": True,
        "batch_id": batch_key,
        "cancelled": cancelled,
        "stopping": stopping,
        "stopped": stopped,
        "completed": completed,
        "message": (
            f"已请求停止 {stopping} 个运行中任务"
            + (f"，取消 {cancelled} 个排队任务" if cancel_pending else "")
        ),
    }


def read_job_log(job_id: int, max_bytes: int = 50_000) -> str:
    """读取任务日志文件最后 max_bytes 字节，给 Web UI 显示。"""
    job = db.get_job(job_id)
    if not job or not job.get("log_file"):
        return ""
    p = Path(job["log_file"])
    if not p.exists():
        return ""
    size = p.stat().st_size
    with p.open("rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
        data = f.read()
    return data.decode("utf-8", errors="replace")
