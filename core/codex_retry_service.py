# -*- coding: utf-8 -*-
"""Codex 授权补跑服务，供账号页和注册任务队列共同使用。"""
import json
import logging
import threading
import time
from pathlib import Path

from core import account_task_store, db

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).resolve().parent.parent / "注册日志"
_RETRYING: set[str] = set()
_RETRYING_LOCK = threading.Lock()
_STOP_REQUESTED: set[str] = set()
_RUNNING_THREADS: dict[str, int] = {}
_RESERVED_AT: dict[str, float] = {}
_ACCOUNT_SETUP_DB_LOCK = threading.RLock()


class CodexRetryStopped(RuntimeError):
    """用户手动停止 Codex 补跑。"""


def _totp_setup_pending(account: dict) -> bool:
    raw_extra = account.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    return bool(raw_extra.get("totp_setup_pending")) if isinstance(raw_extra, dict) else False


def _account_login_password(account: dict | None) -> str:
    """读取账号当前密码；旧账号兼容历史字段。"""
    raw_extra = (account or {}).get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    if not isinstance(raw_extra, dict):
        return ""
    return str(
        raw_extra.get("account_password")
        or raw_extra.get("login_password")
        or raw_extra.get("registration_password")
        or ""
    ).strip()


def _run_retry_plan_check(
    email: str,
    account: dict,
    account_route,
    task_id: int | None,
    *,
    trigger: str,
) -> dict | None:
    """补跑前同步补查套餐；失败只记事件，不阻断后续账号动作。"""
    if str(account.get("plan_check_status") or "").lower() == "success":
        account_task_store.append_event(
            task_id,
            stage="plan_check",
            message="账号已有成功套餐记录，跳过重复查询",
            state="skipped",
        )
        return None
    token = str(account.get("access_token") or "").strip()
    if not token:
        account_task_store.append_event(
            task_id,
            stage="plan_check",
            message="账号缺少 access_token，暂时无法补查套餐",
            level="WARNING",
            state="skipped",
        )
        return None
    account_task_store.append_event(
        task_id,
        stage="plan_check",
        message="账号缺少成功套餐记录，开始补查套餐",
        state="running",
    )
    try:
        from core.plan_check_service import check_registration_account_plan

        result = check_registration_account_plan(
            account_id=int(account.get("id") or 0),
            email=email,
            access_token=token,
            proxy=(getattr(account_route, "proxy_url", None) if account_route is not None else None),
            trigger=str(trigger or "retry_plan_check"),
        )
        if result.get("ok"):
            account_task_store.append_event(
                task_id,
                stage="plan_check_result",
                message="套餐查询完成",
                detail={
                    "current_plan_type": result.get("current_plan_type"),
                    "plus_trial_eligible": bool(result.get("plus_trial_eligible")),
                },
                state="success",
            )
        else:
            account_task_store.append_event(
                task_id,
                stage="plan_check_result",
                message="套餐查询失败，继续执行其它补跑步骤",
                level="WARNING",
                detail={"error": result.get("error")},
                state="failed",
            )
        return result
    except Exception as exc:
        account_task_store.append_event(
            task_id,
            stage="plan_check_result",
            message="套餐查询异常，继续执行其它补跑步骤",
            level="WARNING",
            detail={"error": f"{type(exc).__name__}: {str(exc)[:180]}"},
            state="failed",
        )
        logger.warning("[补跑][套餐] %s 补查异常：%s: %s", email, type(exc).__name__, str(exc)[:180])
        return None


def _thread_alive(thread_id: int | None) -> bool:
    if not thread_id:
        return False
    try:
        tid = int(thread_id)
    except Exception:
        return False
    return any(getattr(t, "ident", None) == tid and t.is_alive() for t in threading.enumerate())


def _clear_state_locked(key: str) -> None:
    _RETRYING.discard(key)
    _RUNNING_THREADS.pop(key, None)
    _RESERVED_AT.pop(key, None)


def log_path(email: str) -> Path:
    safe = email.replace("/", "_").replace("\\", "_").replace(":", "_")
    return _LOG_DIR / f"codex-retry-{safe}.log"


def reserve(email: str) -> bool:
    """进程内防止同一账号被重复补跑。"""
    key = (email or "").strip().lower()
    if not key:
        return False
    with _RETRYING_LOCK:
        if key in _RETRYING:
            thread_id = _RUNNING_THREADS.get(key)
            alive = _thread_alive(thread_id)
            age = time.time() - float(_RESERVED_AT.get(key) or 0)
            stop_req = key in _STOP_REQUESTED
            try:
                acc = db.get_account_by_email(email)
                status = str((acc or {}).get("codex_status") or "").lower()
            except Exception:
                status = ""
            # 修复“实际已停止/线程已结束，但进程内占位未释放”导致无法再次补跑。
            # 用户点停止后，部分浏览器/短信等待步骤可能不会立刻退出，UI 已是 stopped 但进程占位仍在。
            # 这种场景允许清理占位后重新补跑；旧线程仍保留 stop_requested，会在检查点退出。
            terminal_status = status in {"stopped", "failed", "success", "deactivated", "skipped", "cancelled"}
            if ((not alive) and (status != "retrying" or age > 15 * 60)) or (terminal_status and (stop_req or age > 30)):
                logger.warning(
                    "[Codex 补跑] 清理脏占位：email=%s status=%s thread_id=%s alive=%s stop_requested=%s age=%.1fs",
                    email, status or "-", thread_id or "-", alive, stop_req, age,
                )
                _clear_state_locked(key)
            else:
                return False
        _STOP_REQUESTED.discard(key)
        _RUNNING_THREADS.pop(key, None)
        _RETRYING.add(key)
        _RESERVED_AT[key] = time.time()
        return True


def release(email: str) -> None:
    key = (email or "").strip().lower()
    with _RETRYING_LOCK:
        _clear_state_locked(key)


def is_retrying(email: str) -> bool:
    with _RETRYING_LOCK:
        return (email or "").strip().lower() in _RETRYING


def is_stop_requested(email: str) -> bool:
    with _RETRYING_LOCK:
        return (email or "").strip().lower() in _STOP_REQUESTED


def check_stop_requested(email: str) -> None:
    if is_stop_requested(email):
        raise CodexRetryStopped("用户手动停止 Codex 补跑")


def _build_roxy_twofa_setup(
    email: str,
    task_id: int,
    *,
    proxy: str | None = None,
    access_token: str | None = None,
):
    """为缺少 TOTP 的补跑构造一次性 2FA 前置步骤。"""
    state = {"secret": ""}

    def _setup(driver) -> bool:
        current = db.get_account_by_email(email) or {}
        existing_secret = str(current.get("totp_secret") or state["secret"] or "").strip()
        setup_pending = _totp_setup_pending(current)
        if existing_secret and not setup_pending:
            state["secret"] = existing_secret
            account_task_store.append_event(
                task_id,
                stage="twofa",
                message="账号已有 Authenticator 2FA，跳过重复设置",
                state="skipped",
            )
            logger.info("[Codex 补跑][2FA] 本地已存在 Authenticator key，跳过重复设置：%s", email)
            return False

        check_stop_requested(email)
        account_task_store.append_event(
            task_id,
            stage="twofa",
            message="账号未设置 2FA，开始启用 Authenticator",
            state="running",
        )
        logger.info("[Codex 补跑][2FA] 账号缺少 Authenticator key，开始前置设置：%s", email)

        def _checkpoint(secret: str) -> None:
            normalized = str(secret or "").strip()
            if not normalized:
                raise RuntimeError("Authenticator key 写入账号检查点失败")
            with _ACCOUNT_SETUP_DB_LOCK:
                if not db.update_account_totp_secret(email, normalized, setup_pending=True):
                    raise RuntimeError("Authenticator key 写入账号检查点失败")
            state["secret"] = normalized
            logger.info("[Codex 补跑][2FA] Authenticator key 已在激活前写入账号检查点")

        try:
            from config import twofa as twofa_cfg

            twofa_driver = twofa_cfg.get_twofa_driver()
            if twofa_driver == "protocol":
                # Roxy 负责登录和拿到本次新鲜 session；enroll/activate 直接走协议，
                # 不再依赖不同地区的安全设置页面布局。
                from core.account_export import setup_2fa_protocol
                from core.roxy_registration import _fetch_chatgpt_session
                from core.session import BrowserSession

                fresh_access_token = str(access_token or "").strip()
                if not fresh_access_token:
                    session_info = _fetch_chatgpt_session(driver, timeout=60, auto_jump_wait=5)
                    fresh_access_token = str(session_info.get("accessToken") or "").strip()
                if not fresh_access_token:
                    raise RuntimeError("协议开通 2FA 未拿到新鲜 accessToken")
                protocol_session = BrowserSession(proxy=proxy)
                secret = setup_2fa_protocol(
                    protocol_session,
                    fresh_access_token,
                    on_secret=_checkpoint,
                )
                logger.info("[账号补跑][2FA] 使用 protocol 直接开通 Authenticator：%s", email)
            else:
                from core.roxy_registration import setup_roxy_2fa

                secret = setup_roxy_2fa(
                    driver,
                    email,
                    on_secret=_checkpoint,
                    existing_secret=existing_secret or None,
                )
                logger.info("[账号补跑][2FA] 使用 browser 安全设置页开通 Authenticator：%s", email)
            if not state["secret"]:
                _checkpoint(secret)
            with _ACCOUNT_SETUP_DB_LOCK:
                if not db.update_account_totp_secret(email, state["secret"], setup_pending=False):
                    raise RuntimeError("Authenticator 完成状态写入账号失败")
                if not db.update_account_twofa_status(email, "success", "Authenticator 2FA 已启用"):
                    raise RuntimeError("Authenticator 结果状态写入账号失败")
            check_stop_requested(email)
            account_task_store.append_event(
                task_id,
                stage="twofa_result",
                message="Authenticator 2FA 已启用",
                detail={"enabled": True},
                state="success",
            )
            logger.info("[Codex 补跑][2FA] Authenticator 2FA 已启用：%s", email)
            return True
        except CodexRetryStopped:
            raise
        except Exception as exc:
            with _ACCOUNT_SETUP_DB_LOCK:
                db.update_account_twofa_status(
                    email,
                    "failed",
                    f"{type(exc).__name__}: {str(exc)[:220]}",
                )
            account_task_store.append_event(
                task_id,
                stage="twofa_result",
                message="Authenticator 2FA 设置失败，已停止后续账号流程",
                level="ERROR",
                detail={"enabled": False, "error": f"{type(exc).__name__}: {str(exc)[:220]}"},
                state="failed",
            )
            raise RuntimeError(
                f"2FA 设置失败，已停止进入 Codex OAuth：{type(exc).__name__}: {str(exc)[:180]}"
            ) from exc

    return _setup


def _build_roxy_account_setup(email: str, task_id: int, *, proxy: str | None = None):
    """补账号密码和 Authenticator 2FA；protocol 模式下使用独立会话并发。"""

    def _setup(driver, session_info: dict | None = None) -> bool:
        account = db.get_account_by_email(email) or {}
        fresh_access_token = str((session_info or {}).get("accessToken") or "").strip()
        if fresh_access_token:
            if not db.update_account_session(
                email,
                fresh_access_token,
                expires_at=str((session_info or {}).get("expires") or "") or None,
            ):
                raise RuntimeError("重新登录已取得 ChatGPT Token，但写回账号失败")
            account_task_store.append_event(
                task_id,
                stage="token",
                message="重新登录取得的 ChatGPT Token 已写回账号",
                detail={"saved": True},
                state="success",
            )
            account = db.get_account_by_email(email) or account
        account_token = str(account.get("access_token") or "").strip()
        needs_password = bool(account_token) and not _account_login_password(account)
        needs_twofa = (
            not bool(str(account.get("totp_secret") or "").strip())
            or _totp_setup_pending(account)
        )
        if not needs_password:
            account_task_store.append_event(
                task_id,
                stage="login_password",
                message="账号密码无需补充，跳过此步骤",
                state="skipped",
            )
        if not needs_twofa:
            account_task_store.append_event(
                task_id,
                stage="twofa",
                message="账号已有 Authenticator 2FA，跳过此步骤",
                state="skipped",
            )
        if not needs_password and not needs_twofa:
            return False

        from config import twofa as twofa_cfg

        twofa_driver = twofa_cfg.get_twofa_driver()
        parallel_setup = bool(needs_password and needs_twofa and twofa_driver == "protocol")
        protocol_access_token = fresh_access_token or None
        if parallel_setup:
            # protocol 2FA 不触碰 Selenium 页面，可以和密码设置并发；先在
            # 主线程取得一次新鲜 token，避免两个线程同时操作同一个 driver。
            from core.roxy_registration import _fetch_chatgpt_session

            try:
                session_info = _fetch_chatgpt_session(driver, timeout=60, auto_jump_wait=5)
                protocol_access_token = str(session_info.get("accessToken") or "").strip()
                if not protocol_access_token:
                    parallel_setup = False
                    account_task_store.append_event(
                        task_id,
                        stage="account_setup",
                        message="协议 2FA 未拿到新鲜会话，改为串行补配置",
                        level="WARNING",
                    )
            except Exception as exc:
                account_task_store.append_event(
                    task_id,
                    stage="account_setup",
                    message="协议 2FA 未能预取新鲜会话，改为串行补配置",
                    level="WARNING",
                    detail={"error": f"{type(exc).__name__}: {str(exc)[:180]}"},
                )
                parallel_setup = False

        twofa_setup = _build_roxy_twofa_setup(
            email,
            task_id,
            proxy=proxy,
            access_token=protocol_access_token,
        )

        def _setup_password() -> tuple[bool, str | None]:
            # 没有完整 AT 的历史检查点不能安全判断账号已完成注册，交给
            # 外层登录流程处理；有 AT 但没有密码时才进入“添加密码”流程。
            if not needs_password:
                return False, None
            from core.roxy_registration import _registration_password, set_roxy_login_password

            password = _registration_password()
            account_task_store.append_event(
                task_id,
                stage="login_password",
                message="账号缺少账号密码，先在安全设置中补充随机密码",
                state="running",
            )
            try:
                set_roxy_login_password(driver, email, password)
                with _ACCOUNT_SETUP_DB_LOCK:
                    if not db.update_account_login_password(email, password, source="retry"):
                        raise RuntimeError("账号密码写入账号失败")
            except CodexRetryStopped:
                raise
            except Exception as exc:
                account_task_store.append_event(
                    task_id,
                    stage="login_password_result",
                    message="账号密码补充失败，停止后续账号配置",
                    level="ERROR",
                    detail={"error": f"{type(exc).__name__}: {str(exc)[:220]}"},
                    state="failed",
                )
                return False, f"{type(exc).__name__}: {str(exc)[:180]}"
            account_task_store.append_event(
                task_id,
                stage="login_password_result",
                message="账号密码已补充并保存",
                detail={"saved": True},
                state="success",
            )
            return True, None

        def _setup_twofa() -> tuple[bool, str | None]:
            if not needs_twofa:
                return False, None
            return bool(twofa_setup(driver)), None

        changed = False
        errors: list[str] = []

        def _collect(label: str, future_or_result) -> None:
            nonlocal changed
            try:
                if hasattr(future_or_result, "result"):
                    step_changed, error = future_or_result.result()
                else:
                    step_changed, error = future_or_result
            except CodexRetryStopped:
                raise
            except Exception as exc:
                step_changed, error = False, f"{type(exc).__name__}: {str(exc)[:180]}"
            changed = changed or bool(step_changed)
            if error:
                errors.append(f"{label}：{error}")

        if parallel_setup:
            from concurrent.futures import ThreadPoolExecutor

            account_task_store.append_event(
                task_id,
                stage="account_setup",
                message="密码设置与 protocol 2FA 并发执行",
                detail={"parallel": True, "twofa_driver": "protocol"},
            )
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="account-setup-step") as executor:
                password_future = executor.submit(_setup_password)
                twofa_future = executor.submit(_setup_twofa)
                _collect("账号密码", password_future)
                _collect("Authenticator 2FA", twofa_future)
        else:
            # browser 2FA 和密码都依赖同一个 Selenium 页面，必须串行。
            _collect("账号密码", _setup_password())
            _collect("Authenticator 2FA", _setup_twofa())

        if errors:
            account_task_store.append_event(
                task_id,
                stage="account_setup_result",
                message="账号配置部分完成，存在失败步骤，可重跑补齐",
                level="ERROR",
                detail={"errors": errors, "parallel": parallel_setup},
            )
            raise RuntimeError("账号配置部分失败：" + "；".join(errors))
        return changed

    return _setup


def request_stop(email: str) -> dict:
    """兼容入口：原生 Codex run 使用数据库取消令牌；旧账号配置任务只置停止位。"""
    from core import codex_operation_service

    native = codex_operation_service.request_cancel(email=email)
    if native.get("run_id") or native.get("state") != "empty":
        return native
    key = (email or "").strip().lower()
    if not key:
        return {"ok": False, "error": "email 为空", "status": 400}
    with _RETRYING_LOCK:
        retrying = key in _RETRYING
        thread_id = _RUNNING_THREADS.get(key)
        _STOP_REQUESTED.add(key)
    if not retrying:
        db.update_account_codex_status(email, "stopped", "用户手动停止（未发现运行中的补跑）")
        return {"ok": True, "message": "未发现运行中的补跑，已标记为已停止", "state": "stopped", "running": False}

    db.update_account_codex_status(email, "stopped", "用户手动停止 Codex 补跑")
    with _RETRYING_LOCK:
        if not _thread_alive(thread_id):
            _clear_state_locked(key)
    try:
        p = log_path(email)
        p.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime as _dt
        with p.open("a", encoding="utf-8") as f:
            f.write(f"{_dt.now().strftime('%H:%M:%S')} [WARNING] [账号配置补跑] 用户手动停止，已记录协作式停止信号\n")
    except Exception:
        logger.exception("写入 Codex 停止日志失败")
    return {"ok": True, "message": "已记录停止请求，将在安全检查点退出", "state": "cancelling", "running": True}


def run_twofa_worker(
    email: str,
    *,
    clear_log: bool = True,
    target_log_path: str | Path | None = None,
    task_id: int | None = None,
    task_trigger: str = "manual",
) -> dict:
    """重新登录并补齐账号配置，不重复执行 Codex OAuth。"""
    fh: logging.FileHandler | None = None
    root_logger = logging.getLogger()
    result: dict = {"status": "failed", "ok": False, "message": "账号配置重试未返回结果"}
    account_route = None
    route_summary: dict = {}
    browser_stage_started = False
    browser_stage_finished = False
    key = (email or "").strip().lower()
    try:
        account = db.get_account_by_email(email) or {}
        if task_id is None:
            task_id = account_task_store.create_task(
                task_type="twofa_retry",
                account_id=int(account.get("id") or 0) or None,
                email=email,
                trigger=str(task_trigger or "manual"),
            )
        with _RETRYING_LOCK:
            _RUNNING_THREADS[key] = threading.get_ident()
            _RESERVED_AT[key] = time.time()
        check_stop_requested(email)
        account_task_store.start_task(task_id, message="开始补齐账号密码、套餐和 Authenticator 2FA")

        path = Path(target_log_path) if target_log_path else log_path(email)
        path.parent.mkdir(parents=True, exist_ok=True)
        if clear_log:
            path.write_text("", encoding="utf-8")
        thread_name = threading.current_thread().name
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        fh.addFilter(lambda record: record.threadName == thread_name)
        root_logger.addHandler(fh)

        import config as config_pkg

        config_pkg.reload_all()
        from config import codex as codex_cfg
        from config import roxybrowser as roxy_cfg

        oauth_driver = str(getattr(codex_cfg, "CODEX_OAUTH_DRIVER", "protocol") or "protocol").strip().lower()
        if oauth_driver == "same_as_registration":
            oauth_driver = str(getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
        if oauth_driver not in {"roxy", "roxybrowser", "fingerprint", "browser"}:
            raise RuntimeError(f"账号配置重试当前仅支持 Roxy 驱动，当前驱动={oauth_driver or 'protocol'}")

        from core.account_proxy import acquire_account_proxy

        account_route = acquire_account_proxy(
            account_id=int(account.get("id") or 0) or None,
            email=email,
            purpose="twofa-retry",
        )
        route_summary = account_route.public_dict()
        account_task_store.append_event(
            task_id,
            stage="network",
            message="已分配账号配置重试线路",
            detail={
                "network_route": route_summary.get("network_route"),
                "proxy_mode": account_route.mode,
                "proxy_provider": account_route.provider,
                "proxy_region": account_route.region,
            },
            state="success",
        )
        _run_retry_plan_check(
            email,
            account,
            account_route,
            task_id,
            trigger=str(task_trigger or "manual") + "_plan_check",
        )
        account_task_store.append_event(
            task_id,
            stage="browser",
            message="重新登录 ChatGPT，补齐账号密码并检查 Authenticator 开关",
            state="running",
        )
        browser_stage_started = True
        from core.roxy_codex_oauth import run_roxy_chatgpt_account_action

        run_roxy_chatgpt_account_action(
            email,
            proxy=account_route.proxy_url,
            action=_build_roxy_account_setup(
                email,
                task_id,
                proxy=(account_route.proxy_url if account_route is not None else None),
            ),
        )
        account_task_store.append_event(
            task_id,
            stage="browser",
            message="ChatGPT 重新登录与账号配置检查已完成",
            state="success",
        )
        browser_stage_finished = True
        check_stop_requested(email)
        result = {
            "status": "success",
            "ok": True,
            "message": "账号密码、套餐和 Authenticator 2FA 已补齐或确认",
            "proxy_provider": account_route.provider,
            "proxy_region": account_route.region,
            "proxy_mode": account_route.mode,
        }
        return result
    except CodexRetryStopped as exc:
        if browser_stage_started and not browser_stage_finished:
            account_task_store.append_event(
                task_id,
                stage="browser",
                message="ChatGPT 重新登录流程已被用户停止",
                level="ERROR",
                state="failed",
            )
        result = {"status": "stopped", "ok": False, "message": str(exc) or "用户手动停止账号配置重试"}
        return result
    except Exception as exc:
        if browser_stage_started and not browser_stage_finished:
            account_task_store.append_event(
                task_id,
                stage="browser",
                message="ChatGPT 重新登录与账号配置检查失败",
                level="ERROR",
                detail={"error": f"{type(exc).__name__}: {str(exc)[:220]}"},
                state="failed",
            )
        result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {exc}"}
        logger.exception("[账号配置重试] %s 异常", email)
        return result
    finally:
        if fh is not None:
            try:
                root_logger.removeHandler(fh)
                fh.close()
            except Exception:
                pass
        if account_route is not None:
            account_route.release(reason=f"twofa-retry-{email}")
        release(email)
        with _RETRYING_LOCK:
            if key:
                _STOP_REQUESTED.discard(key)
        task_status = "success" if result.get("ok") else "cancelled" if result.get("status") == "stopped" else "failed"
        try:
            account_task_store.finish_task(
                task_id,
                status=task_status,
                message=(
                    "账号密码、套餐和 Authenticator 2FA 已补齐或确认"
                    if task_status == "success"
                    else "账号配置重试已停止" if task_status == "cancelled" else "账号配置重试失败"
                ),
                error=None if task_status == "success" else str(result.get("message") or "账号配置重试失败"),
                result_summary={"ok": bool(result.get("ok")), "status": result.get("status"), "message": result.get("message")},
                route={
                    "network_route": route_summary.get("network_route"),
                    "proxy_mode": result.get("proxy_mode") or getattr(account_route, "mode", None),
                    "proxy_provider": result.get("proxy_provider") or getattr(account_route, "provider", None),
                    "proxy_region": result.get("proxy_region") or getattr(account_route, "region", None),
                    "proxy_used": route_summary.get("proxy_used"),
                },
                validation_method="chatgpt_account_setup",
            )
        except Exception:
            logger.exception("[账号配置重试] 写入任务实例失败：task_id=%s email=%s", task_id or "-", email)


def _run_worker_legacy(
    email: str,
    *,
    batch_label: str | None = None,
    clear_log: bool = True,
    target_log_path: str | Path | None = None,
    task_id: int | None = None,
    task_trigger: str = "manual",
) -> dict:
    """执行一次 Codex 补跑，并把脱敏后的关键阶段写入统一任务实例。"""
    fh: logging.FileHandler | None = None
    root_logger = logging.getLogger()
    result: dict = {"status": "failed", "ok": False, "message": "Codex 补跑未返回结果"}
    account_route = None
    route_summary: dict = {}
    oauth_driver = ""
    key = (email or "").strip().lower()
    sms_batch_bound = False
    if batch_label:
        from core import sms_provider

        # WebUI 会在同一批次标签后追加“#序号/总数”；去掉序号后共享一次选国结果。
        sms_provider.set_sms_batch_context(f"codex-retry:{batch_label.split(' #', 1)[0]}")
        sms_batch_bound = True
    try:
        if task_id is None:
            account = db.get_account_by_email(email) or {}
            task_id = account_task_store.create_task(
                task_type="codex_retry",
                account_id=int(account.get("id") or 0) or None,
                email=email,
                trigger=str(task_trigger or "manual"),
            )
        with _RETRYING_LOCK:
            _RUNNING_THREADS[key] = threading.get_ident()
            _RESERVED_AT[key] = time.time()
        check_stop_requested(email)

        account_task_store.start_task(task_id, message="开始补跑 Codex OAuth 授权")

        from core.codex_oauth import run_codex_oauth

        path = Path(target_log_path) if target_log_path else log_path(email)
        path.parent.mkdir(parents=True, exist_ok=True)
        if clear_log:
            path.write_text("", encoding="utf-8")

        thread_name = threading.current_thread().name
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        fh.addFilter(lambda record: record.threadName == thread_name)
        root_logger.addHandler(fh)

        try:
            import config as config_pkg
            config_pkg.reload_all()
            from config import codex as codex_cfg
            from config import roxybrowser as roxy_cfg
            logger.info(
                "[Codex 补跑] 已热加载配置：CODEX_OAUTH_DRIVER=%s ROXY_OPEN_HEADLESS=%s ROXY_KEEP_BROWSER_OPEN=%s",
                getattr(codex_cfg, "CODEX_OAUTH_DRIVER", ""),
                getattr(roxy_cfg, "ROXY_OPEN_HEADLESS", ""),
                getattr(roxy_cfg, "ROXY_KEEP_BROWSER_OPEN", ""),
            )
        except Exception as exc:
            logger.warning("[Codex 补跑] 配置热加载失败，将继续使用当前内存配置：%s: %s", type(exc).__name__, exc)

        if batch_label:
            logger.info("[Codex 补跑] 批量任务：%s", batch_label)
        logger.info("[Codex 补跑] 开始：%s", email)
        logger.info(
            "[Codex 补跑] 阶段说明：获取授权地址 → 登录邮箱 → 邮箱 OTP → "
            "缺失时先补账号密码/套餐/2FA → 手机验证 → 捕获 callback → 提交/保存凭证"
        )
        check_stop_requested(email)
        from config import codex as codex_cfg
        from config import roxybrowser as roxy_cfg
        oauth_driver = str(getattr(codex_cfg, "CODEX_OAUTH_DRIVER", "protocol") or "protocol").strip().lower()
        if oauth_driver == "same_as_registration":
            oauth_driver = str(getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
        account_task_store.append_event(
            task_id,
            stage="driver",
            message=f"使用 {oauth_driver or 'protocol'} 驱动执行 Codex OAuth",
            detail={"oauth_driver": oauth_driver or "protocol"},
            state="success",
        )
        # Browser Use / Skyvern 的浏览器运行在云端，只能使用云服务自身的代理设置；
        # protocol / Roxy / Cloak 才能注入本地申请的 1024Proxy 或静态代理池。
        if oauth_driver not in {"browser_use", "browseruse", "browser-use", "bu", "skyvern", "sv"}:
            from core.account_proxy import acquire_account_proxy
            account = db.get_account_by_email(email) or {}
            account_route = acquire_account_proxy(
                account_id=int(account.get("id") or 0) or None,
                email=email,
                purpose="codex-oauth",
            )
            route_summary = account_route.public_dict()
            logger.info(
                "[Codex 补跑] 账号网络：provider=%s region=%s route=%s proxy=%s",
                account_route.provider,
                account_route.region or "-",
                account_route.public_dict().get("network_route"),
                account_route.public_dict().get("proxy_used") or "-",
            )
            account_task_store.append_event(
                task_id,
                stage="network",
                message="已分配账号补跑线路",
                detail={
                    "network_route": route_summary.get("network_route"),
                    "proxy_mode": account_route.mode,
                    "proxy_provider": account_route.provider,
                    "proxy_region": account_route.region,
                    "proxy_used": route_summary.get("proxy_used"),
                },
                state="success",
            )
        else:
            route_summary = {"network_route": "cloud_driver"}
            account_task_store.append_event(
                task_id,
                stage="network",
                message="云端浏览器驱动使用平台线路",
                detail={"network_route": "cloud_driver"},
                state="success",
            )
        account = db.get_account_by_email(email) or {}
        _run_retry_plan_check(
            email,
            account,
            account_route,
            task_id,
            trigger=str(task_trigger or "manual") + "_plan_check",
        )
        needs_twofa = (
            not bool(str(account.get("totp_secret") or "").strip())
            or _totp_setup_pending(account)
        )
        needs_login_password = bool(str(account.get("access_token") or "").strip()) and not _account_login_password(account)
        needs_roxy_setup = needs_twofa or needs_login_password
        account_task_store.append_event(
            task_id,
            stage="oauth",
            message=(
                "账号缺少账号密码/2FA，将先补齐账号配置再完成 OAuth"
                if needs_roxy_setup and oauth_driver in {"roxy", "roxybrowser", "fingerprint", "browser"}
                else "开始获取授权地址并完成邮箱、短信与 callback 流程"
            ),
            state="running",
        )
        if needs_roxy_setup and oauth_driver in {"roxy", "roxybrowser", "fingerprint", "browser"}:
            from core.roxy_codex_oauth import run_roxy_codex_oauth

            result = run_roxy_codex_oauth(
                email,
                proxy=(account_route.proxy_url if account_route is not None else None),
                force=True,
                before_oauth_setup=_build_roxy_account_setup(
                    email,
                    task_id,
                    proxy=(account_route.proxy_url if account_route is not None else None),
                ),
            )
        else:
            result = run_codex_oauth(
                email,
                proxy=(account_route.proxy_url if account_route is not None else None),
                force=True,
            )
        if account_route is not None:
            # 标准任务页需要展示补跑实际使用的平台/地区；只写公开元数据，绝不落代理凭据。
            result["proxy_provider"] = account_route.provider
            result["proxy_region"] = account_route.region
            result["proxy_mode"] = account_route.mode
        check_stop_requested(email)
        logger.info(
            "[Codex 补跑] 结果：status=%s ok=%s file=%s callback=%s",
            result.get("status"), result.get("ok"), result.get("file_path"), result.get("callback_url"),
        )
        account_task_store.append_event(
            task_id,
            stage="oauth_result",
            message="Codex OAuth 已返回成功结果" if result.get("ok") else "Codex OAuth 返回失败结果",
            level="INFO" if result.get("ok") else "ERROR",
            detail={
                "ok": bool(result.get("ok")),
                "status": result.get("status"),
                "message": result.get("message"),
                "credential_saved": bool(result.get("file_path")),
            },
            state="success" if result.get("ok") else "failed",
        )
        result_status = result.get("status", "failed")
        if result.get("ok"):
            db.update_account_codex_status(email, "success", None)
            logger.info("[Codex 补跑] %s 成功", email)
        elif result_status == "deactivated":
            db.update_account_codex_status(email, "deactivated", result.get("message"))
            logger.warning("[Codex 补跑] %s 账号已废: %s", email, result.get("message"))
        else:
            db.update_account_codex_status(email, result_status, result.get("message"))
            logger.warning("[Codex 补跑] %s 失败: %s", email, result.get("message"))
        return result
    except CodexRetryStopped as exc:
        result = {"status": "stopped", "ok": False, "message": str(exc) or "用户手动停止 Codex 补跑"}
        db.update_account_codex_status(email, "stopped", result["message"])
        logger.warning("[Codex 补跑] %s 已停止: %s", email, result["message"])
        return result
    except Exception as exc:
        if is_stop_requested(email):
            result = {"status": "stopped", "ok": False, "message": "用户手动停止 Codex 补跑"}
            db.update_account_codex_status(email, "stopped", result["message"])
            logger.warning("[Codex 补跑] %s 已停止", email)
            return result
        result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {exc}"}
        db.update_account_codex_status(email, "failed", result["message"])
        logger.exception("[Codex 补跑] %s 异常", email)
        logger.error("[Codex 补跑] 已结束：异常失败")
        return result
    finally:
        try:
            logger.info("[Codex 补跑] 结束：%s", email)
            if fh is not None:
                root_logger.removeHandler(fh)
                fh.close()
        finally:
            if account_route is not None:
                account_route.release(reason=f"codex-oauth-{email}")
            release(email)
            with _RETRYING_LOCK:
                if key:
                    _STOP_REQUESTED.discard(key)
            result_status = str(result.get("status") or "failed").lower()
            task_status = (
                "success" if result.get("ok")
                else "deactivated" if result_status == "deactivated"
                else "cancelled" if result_status in {"stopped", "cancelled"}
                else "failed"
            )
            route = {
                "network_route": route_summary.get("network_route"),
                "proxy_mode": result.get("proxy_mode") or getattr(account_route, "mode", None),
                "proxy_provider": result.get("proxy_provider") or getattr(account_route, "provider", None),
                "proxy_region": result.get("proxy_region") or getattr(account_route, "region", None),
                "proxy_used": route_summary.get("proxy_used"),
            }
            try:
                account_task_store.finish_task(
                    task_id,
                    status=task_status,
                    message=(
                        "Codex 补跑成功" if task_status == "success"
                        else "Codex 补跑已停止" if task_status == "cancelled"
                        else "账号已停用" if task_status == "deactivated"
                        else "Codex 补跑失败"
                    ),
                    error=None if task_status == "success" else str(result.get("message") or "Codex 补跑失败"),
                    result_summary={
                        "ok": bool(result.get("ok")),
                        "status": result_status,
                        "message": result.get("message"),
                        "credential_saved": bool(result.get("file_path")),
                        "oauth_driver": oauth_driver or None,
                    },
                    route=route,
                    validation_method=f"codex_oauth:{oauth_driver or 'unknown'}",
                )
            except Exception:
                logger.exception("[Codex 补跑] 写入任务实例失败：task_id=%s email=%s", task_id or "-", email)
            if sms_batch_bound:
                from core import sms_provider

                sms_provider.clear_sms_batch_context()


def run_worker(
    email: str,
    *,
    batch_label: str | None = None,
    clear_log: bool = True,
    target_log_path: str | Path | None = None,
    task_id: int | None = None,
    task_trigger: str = "manual",
) -> dict:
    """旧同步入口的兼容委托；业务执行统一由 Codex operation 协调器完成。"""
    from core import codex_operation_service, operation_task_store

    queued = codex_operation_service.submit(email, trigger=task_trigger)
    if not queued.get("accepted"):
        if queued.get("busy") and queued.get("run_id"):
            run_id = int(queued["run_id"])
        else:
            return {
                "status": "failed",
                "ok": False,
                "message": str(queued.get("error") or "Codex operation 入队失败"),
            }
    else:
        run_id = int(queued["run_id"])
    try:
        while True:
            run = operation_task_store.get_run(run_id) or {}
            status = str(run.get("status") or "")
            if status not in {"queued", "running", "cancelling", "settling"}:
                summary = run.get("result_summary") or {}
                return {
                    **summary,
                    "status": status or "failed",
                    "ok": status == "success",
                    "message": run.get("error_message") or summary.get("message") or status,
                }
            time.sleep(0.25)
    finally:
        # 兼容调用方可能在调用前执行过旧 reserve；它不再参与 Codex 并发事实。
        release(email)
